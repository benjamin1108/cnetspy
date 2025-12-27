/**
 * MCP SSE 客户端
 * 处理与 MCP 服务器的 SSE 连接和工具调用
 */

import type { McpTool, McpServerConfig, ToolCall, ToolResult } from '@/types/chat';

type McpEventHandler = {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  onToolsUpdate?: (tools: McpTool[]) => void;
};

interface McpMessage {
  jsonrpc: '2.0';
  id?: string | number;
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: { code: number; message: string };
}

export class McpClient {
  private config: McpServerConfig;
  private eventSource: EventSource | null = null;
  private handlers: McpEventHandler;
  private tools: McpTool[] = [];
  private sessionId: string | null = null;
  private pendingRequests: Map<string, {
    resolve: (value: unknown) => void;
    reject: (error: Error) => void;
  }> = new Map();
  private requestId = 0;

  constructor(config: McpServerConfig, handlers: McpEventHandler = {}) {
    this.config = config;
    this.handlers = handlers;
  }

  /**
   * 连接到 MCP 服务器
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        // 创建 SSE 连接
        this.eventSource = new EventSource(this.config.url);

        this.eventSource.onopen = () => {
          console.log('[MCP] Connected to:', this.config.url);
          this.handlers.onConnect?.();
          resolve();
        };

        this.eventSource.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.eventSource.addEventListener('endpoint', (event: MessageEvent) => {
          // 处理 endpoint 事件，获取 session 信息
          const data = event.data;
          console.log('[MCP] Endpoint event:', data);
          // 解析 endpoint URL 获取 session_id
          if (data && typeof data === 'string') {
            const match = data.match(/session_id=([^&]+)/);
            if (match) {
              this.sessionId = match[1];
              console.log('[MCP] Session ID:', this.sessionId);
              // 初始化连接
              this.initialize();
            }
          }
        });

        this.eventSource.onerror = (error) => {
          console.error('[MCP] Connection error:', error);
          this.handlers.onError?.(new Error('MCP connection failed'));
          reject(new Error('MCP connection failed'));
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.sessionId = null;
      this.tools = [];
      this.handlers.onDisconnect?.();
    }
  }

  /**
   * 初始化 MCP 会话
   */
  private async initialize(): Promise<void> {
    try {
      // 发送初始化请求
      await this.sendRequest('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {
          tools: {},
        },
        clientInfo: {
          name: 'cloudnetspy-web',
          version: '1.0.0',
        },
      });

      // 发送 initialized 通知
      await this.sendNotification('notifications/initialized', {});

      // 获取可用工具列表
      await this.listTools();
    } catch (error) {
      console.error('[MCP] Initialize failed:', error);
    }
  }

  /**
   * 获取工具列表
   */
  async listTools(): Promise<McpTool[]> {
    try {
      const response = await this.sendRequest('tools/list', {}) as { tools: McpTool[] };
      this.tools = response.tools || [];
      this.handlers.onToolsUpdate?.(this.tools);
      return this.tools;
    } catch (error) {
      console.error('[MCP] List tools failed:', error);
      return [];
    }
  }

  /**
   * 调用工具
   */
  async callTool(toolCall: ToolCall): Promise<ToolResult> {
    try {
      const response = await this.sendRequest('tools/call', {
        name: toolCall.name,
        arguments: toolCall.arguments,
      }) as { content: Array<{ type: string; text?: string }> };

      // 提取结果
      const textContent = response.content?.find(c => c.type === 'text');
      const resultText = textContent?.text || JSON.stringify(response);

      return {
        callId: toolCall.id,
        name: toolCall.name,
        result: resultText,
        isError: false,
      };
    } catch (error) {
      return {
        callId: toolCall.id,
        name: toolCall.name,
        result: error instanceof Error ? error.message : 'Unknown error',
        isError: true,
      };
    }
  }

  /**
   * 发送 JSON-RPC 请求
   */
  private async sendRequest(method: string, params: unknown): Promise<unknown> {
    const id = `req_${++this.requestId}`;
    
    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });

      const message: McpMessage = {
        jsonrpc: '2.0',
        id,
        method,
        params,
      };

      this.postMessage(message);

      // 超时处理
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error(`Request timeout: ${method}`));
        }
      }, 30000);
    });
  }

  /**
   * 发送通知（无需响应）
   */
  private async sendNotification(method: string, params: unknown): Promise<void> {
    const message: McpMessage = {
      jsonrpc: '2.0',
      method,
      params,
    };
    this.postMessage(message);
  }

  /**
   * 发送消息到服务器
   */
  private async postMessage(message: McpMessage): Promise<void> {
    if (!this.sessionId) {
      console.error('[MCP] No session ID, cannot send message');
      return;
    }

    const baseUrl = this.config.url.replace('/sse', '');
    const url = `${baseUrl}/messages/?session_id=${this.sessionId}`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(message),
      });

      if (!response.ok) {
        console.error('[MCP] Post message failed:', response.statusText);
      }
    } catch (error) {
      console.error('[MCP] Post message error:', error);
    }
  }

  /**
   * 处理收到的消息
   */
  private handleMessage(data: string): void {
    try {
      const message: McpMessage = JSON.parse(data);

      // 处理响应
      if (message.id && this.pendingRequests.has(String(message.id))) {
        const { resolve, reject } = this.pendingRequests.get(String(message.id))!;
        this.pendingRequests.delete(String(message.id));

        if (message.error) {
          reject(new Error(message.error.message));
        } else {
          resolve(message.result);
        }
      }
    } catch (error) {
      console.error('[MCP] Parse message error:', error);
    }
  }

  /**
   * 获取当前可用工具
   */
  getTools(): McpTool[] {
    return this.tools;
  }

  /**
   * 检查是否已连接
   */
  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN && this.sessionId !== null;
  }
}
