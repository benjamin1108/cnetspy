/**
 * AI Chatbox 类型定义
 */

// 聊天消息角色
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

// 聊天消息
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  toolResults?: ToolResult[];
  isLoading?: boolean;
}

// MCP 工具定义
export interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties?: Record<string, unknown>;
    required?: string[];
  };
}

// 工具调用
export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

// 工具执行结果
export interface ToolResult {
  callId: string;
  name: string;
  result: unknown;
  isError?: boolean;
}

// MCP 服务器配置
export interface McpServerConfig {
  name: string;
  url: string;
}

// MCP 连接状态
export type McpConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// Chat 上下文状态
export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  mcpStatus: McpConnectionStatus;
  availableTools: McpTool[];
  error: string | null;
}

// Chat 配置
export interface ChatConfig {
  mcpServers: McpServerConfig[];
  aiEndpoint?: string;
  maxMessages?: number;
}
