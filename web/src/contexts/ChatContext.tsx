/**
 * Chat Context
 * 管理 AI Chatbox 的对话状态
 */

import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from 'react';
import type {
  ChatMessage,
  ChatState,
  ChatConfig,
  McpTool,
  McpConnectionStatus,
  ToolCall,
  ToolResult,
} from '@/types/chat';
import { McpClient } from '@/api/mcp-client';

// API 基础路径（生产环境使用 /next/api/v1）
const API_BASE = import.meta.env.PROD ? '/next/api/v1' : '/api/v1';

// 提示词配置类型
interface PromptsConfig {
  system_prompt: string;
  summary_prompt: string;
  tools_description_template: string;
  vendor_names: Record<string, string>;
}

// 默认配置
const DEFAULT_CONFIG: ChatConfig = {
  mcpServers: [],
  maxMessages: 100,
};

// Chat Actions
type ChatAction =
  | { type: 'ADD_MESSAGE'; payload: ChatMessage }
  | { type: 'UPDATE_MESSAGE'; payload: { id: string; updates: Partial<ChatMessage> } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_MCP_STATUS'; payload: McpConnectionStatus }
  | { type: 'SET_TOOLS'; payload: McpTool[] }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'CLEAR_MESSAGES' }
  | { type: 'ADD_TOOL_RESULT'; payload: { messageId: string; result: ToolResult } };

// Initial state
const initialState: ChatState = {
  messages: [],
  isLoading: false,
  mcpStatus: 'disconnected',
  availableTools: [],
  error: null,
};

// Reducer
function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
      };
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.payload.id ? { ...msg, ...action.payload.updates } : msg
        ),
      };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_MCP_STATUS':
      return { ...state, mcpStatus: action.payload };
    case 'SET_TOOLS':
      return { ...state, availableTools: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'CLEAR_MESSAGES':
      return { ...state, messages: [] };
    case 'ADD_TOOL_RESULT':
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.payload.messageId
            ? {
                ...msg,
                toolResults: [...(msg.toolResults || []), action.payload.result],
              }
            : msg
        ),
      };
    default:
      return state;
  }
}

// Context type
interface ChatContextType {
  state: ChatState;
  config: ChatConfig;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  connectMcp: () => Promise<void>;
  disconnectMcp: () => void;
  callTool: (toolCall: ToolCall) => Promise<ToolResult>;
}

const ChatContext = createContext<ChatContextType | null>(null);

// Provider props
interface ChatProviderProps {
  children: ReactNode;
  config?: Partial<ChatConfig>;
}

// 生成唯一ID
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

export function ChatProvider({ children, config: userConfig }: ChatProviderProps) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const config = { ...DEFAULT_CONFIG, ...userConfig };
  const mcpClientRef = useRef<McpClient | null>(null);
  const promptsRef = useRef<PromptsConfig | null>(null);

  // 初始化时获取提示词配置
  useEffect(() => {
    async function fetchPrompts() {
      try {
        const response = await fetch(`${API_BASE}/chat/prompts`);
        if (response.ok) {
          promptsRef.current = await response.json();
        }
      } catch (error) {
        console.error('Failed to fetch prompts:', error);
      }
    }
    fetchPrompts();
  }, []);

  // 连接 MCP
  const connectMcp = useCallback(async () => {
    if (config.mcpServers.length === 0) {
      dispatch({ type: 'SET_ERROR', payload: 'No MCP servers configured' });
      return;
    }

    const serverConfig = config.mcpServers[0];
    dispatch({ type: 'SET_MCP_STATUS', payload: 'connecting' });

    try {
      const client = new McpClient(serverConfig, {
        onConnect: () => {
          dispatch({ type: 'SET_MCP_STATUS', payload: 'connected' });
        },
        onDisconnect: () => {
          dispatch({ type: 'SET_MCP_STATUS', payload: 'disconnected' });
        },
        onError: (error) => {
          dispatch({ type: 'SET_ERROR', payload: error.message });
          dispatch({ type: 'SET_MCP_STATUS', payload: 'error' });
        },
        onToolsUpdate: (tools) => {
          dispatch({ type: 'SET_TOOLS', payload: tools });
        },
      });

      await client.connect();
      mcpClientRef.current = client;
    } catch (error) {
      dispatch({ type: 'SET_MCP_STATUS', payload: 'error' });
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : 'Connection failed',
      });
    }
  }, [config.mcpServers]);

  // 断开 MCP
  const disconnectMcp = useCallback(() => {
    mcpClientRef.current?.disconnect();
    mcpClientRef.current = null;
  }, []);

  // 调用工具
  const callTool = useCallback(async (toolCall: ToolCall): Promise<ToolResult> => {
    if (!mcpClientRef.current?.isConnected()) {
      return {
        callId: toolCall.id,
        name: toolCall.name,
        result: 'MCP not connected',
        isError: true,
      };
    }

    return mcpClientRef.current.callTool(toolCall);
  }, []);

  // 发送消息
  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      // 添加用户消息
      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content,
        timestamp: new Date(),
      };
      dispatch({ type: 'ADD_MESSAGE', payload: userMessage });
      dispatch({ type: 'SET_LOADING', payload: true });

      // 添加 AI 消息占位
      const assistantMessageId = generateId();
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      };
      dispatch({ type: 'ADD_MESSAGE', payload: assistantMessage });

      try {
        // 构建工具列表
        const tools = state.availableTools;
        const toolsList = tools.map(t => {
          const params = t.inputSchema?.properties 
            ? Object.entries(t.inputSchema.properties).map(([k, v]: [string, any]) => `${k}: ${v.description || v.type}`).join(', ')
            : '';
          return `- ${t.name}(${params}): ${t.description}`;
        }).join('\n');
        
        // 使用配置的工具描述模板
        const toolsDescTemplate = promptsRef.current?.tools_description_template || '';
        const toolsDescription = tools.length > 0 && toolsDescTemplate
          ? toolsDescTemplate.replace(/\$\{toolsList\}/g, toolsList)
          : '';

        // 构建系统提示（从配置模板生成）
        const now = new Date();
        const currentDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        
        // 使用配置的提示词模板，替换变量
        const promptTemplate = promptsRef.current?.system_prompt || '你是 CloudNetSpy 的 AI 助手。';
        const systemPrompt = promptTemplate
          .replace(/\$\{currentDate\}/g, currentDate)
          .replace(/\$\{toolsDescription\}/g, toolsDescription);

        // 调用后端 AI 接口
        const requestBody = {
          messages: [
            {
              role: 'system',
              content: systemPrompt,
            },
            ...state.messages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            { role: 'user', content },
          ],
        };
        
        const response = await fetch(`${API_BASE}/chat/completions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error('AI request failed');
        }

        const data = await response.json();
        
        // 处理响应
        if (data.choices?.[0]?.message) {
          const aiMessage = data.choices[0].message;
          const responseText = aiMessage.content || '';
          
          // 解析 JSON 格式的工具调用
          const jsonMatch = responseText.match(/```json\s*\n?([\s\S]*?)\n?```/);
          
          if (jsonMatch && mcpClientRef.current?.isConnected()) {
            try {
              const toolCallData = JSON.parse(jsonMatch[1]);
              const toolName = toolCallData.tool;
              const toolParams = toolCallData.params || {};
              
              // 显示 AI 的回复（去掉 JSON 部分）
              const displayText = responseText.replace(/```json[\s\S]*?```/g, '').trim();
              
              dispatch({
                type: 'UPDATE_MESSAGE',
                payload: {
                  id: assistantMessageId,
                  updates: {
                    content: displayText || `正在调用 ${toolName}...`,
                    isLoading: true,
                  },
                },
              });
              
              // 通过 MCP 执行工具调用
              const toolCall: ToolCall = {
                id: `call_${Date.now()}`,
                name: toolName,
                arguments: toolParams,
              };
              
              const result = await callTool(toolCall);
              
              dispatch({
                type: 'ADD_TOOL_RESULT',
                payload: { messageId: assistantMessageId, result },
              });
              
              // 将结果发送给 AI 生成最终回复
              const summaryPrompt = promptsRef.current?.summary_prompt || '请根据工具返回的数据，用中文用户友好的方式总结和展示结果。';
              const summaryResponse = await fetch(`${API_BASE}/chat/completions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  messages: [
                    {
                      role: 'system',
                      content: summaryPrompt,
                    },
                    { role: 'user', content: `用户问题: ${content}\n\n工具 ${toolName} 返回的数据:\n${typeof result.result === 'string' ? result.result : JSON.stringify(result.result, null, 2)}` },
                  ],
                }),
              });
              
              if (summaryResponse.ok) {
                const summaryData = await summaryResponse.json();
                const summaryText = summaryData.choices?.[0]?.message?.content || '数据已获取，请查看上方工具结果。';
                
                dispatch({
                  type: 'UPDATE_MESSAGE',
                  payload: {
                    id: assistantMessageId,
                    updates: {
                      content: summaryText,
                      isLoading: false,
                    },
                  },
                });
              } else {
                dispatch({
                  type: 'UPDATE_MESSAGE',
                  payload: {
                    id: assistantMessageId,
                    updates: {
                      content: '数据已获取，请查看上方工具结果。',
                      isLoading: false,
                    },
                  },
                });
              }
            } catch (parseError) {
              // JSON 解析失败，显示原始回复
              dispatch({
                type: 'UPDATE_MESSAGE',
                payload: {
                  id: assistantMessageId,
                  updates: {
                    content: responseText,
                    isLoading: false,
                  },
                },
              });
            }
          } else {
            // 没有工具调用，直接显示回复
            dispatch({
              type: 'UPDATE_MESSAGE',
              payload: {
                id: assistantMessageId,
                updates: {
                  content: responseText || '抱歉，我无法处理您的请求。',
                  isLoading: false,
                },
              },
            });
          }
        }
      } catch (error) {
        dispatch({
          type: 'UPDATE_MESSAGE',
          payload: {
            id: assistantMessageId,
            updates: {
              content: `请求失败: ${error instanceof Error ? error.message : '未知错误'}`,
              isLoading: false,
            },
          },
        });
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [state.messages, state.availableTools, callTool]
  );

  // 清空消息
  const clearMessages = useCallback(() => {
    dispatch({ type: 'CLEAR_MESSAGES' });
  }, []);

  // 组件卸载时断开连接
  useEffect(() => {
    return () => {
      disconnectMcp();
    };
  }, [disconnectMcp]);

  const value: ChatContextType = {
    state,
    config,
    sendMessage,
    clearMessages,
    connectMcp,
    disconnectMcp,
    callTool,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

// Hook
export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
