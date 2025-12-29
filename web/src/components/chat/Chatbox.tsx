/**
 * AI Chatbox 组件
 * 浮动聊天窗口，支持 MCP 工具调用
 */

import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Loader2,
  Trash2,
  Plug,
  PlugZap,
  AlertCircle,
  Bot,
  User,
  Wrench,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useChat } from '@/contexts/ChatContext';
import type { ChatMessage, ToolResult } from '@/types/chat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 消息气泡组件
function MessageBubble({ message }: { message: ChatMessage }) {
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const isUser = message.role === 'user';
  const hasToolResults = message.toolResults && message.toolResults.length > 0;

  return (
    <div className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* 头像 */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          isUser ? 'bg-primary' : 'chat-avatar-ai'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-primary-foreground" />
        ) : (
          <Bot className="w-4 h-4 text-ai-accent" />
        )}
      </div>

      {/* 消息内容 */}
      <div className={cn('flex flex-col gap-1 max-w-[80%]', isUser ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2',
            isUser ? 'chat-bubble-user' : 'chat-bubble-assistant'
          )}
        >
          {message.isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">思考中...</span>
            </div>
          ) : (
            <div className="ai-summary-content text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* 工具调用结果 */}
        {hasToolResults && (
          <div className="w-full">
            <button
              onClick={() => setToolsExpanded(!toolsExpanded)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Wrench className="w-3 h-3" />
              <span>工具调用结果 ({message.toolResults!.length})</span>
              {toolsExpanded ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
            {toolsExpanded && (
              <div className="mt-2 space-y-2">
                {message.toolResults!.map((result: ToolResult) => (
                  <ToolResultCard key={result.callId} result={result} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* 时间戳 */}
        <span className="text-xs text-muted-foreground">
          {message.timestamp.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </div>
  );
}

// 工具结果卡片
function ToolResultCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(false);
  const resultText = typeof result.result === 'string' ? result.result : JSON.stringify(result.result, null, 2);
  const isLong = resultText.length > 200;

  return (
    <div className={cn('chat-tool-result rounded-lg p-3', result.isError && 'chat-tool-error')}>
      <div className="flex items-center gap-2 mb-2">
        <Wrench className="w-3 h-3" />
        <span className="text-xs font-medium">{result.name}</span>
        {result.isError && <AlertCircle className="w-3 h-3 text-destructive" />}
      </div>
      <pre
        className={cn(
          'text-xs overflow-x-auto whitespace-pre-wrap',
          !expanded && isLong && 'max-h-24 overflow-hidden'
        )}
      >
        {resultText}
      </pre>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-primary hover:underline"
        >
          {expanded ? '收起' : '展开全部'}
        </button>
      )}
    </div>
  );
}

// 连接状态指示器（只显示状态，自动连接）
function ConnectionStatus() {
  const { state } = useChat();
  const { mcpStatus, availableTools } = state;

  const statusConfig: Record<
    string,
    {
      icon: typeof Plug;
      text: string;
      className: string;
      spin?: boolean;
      pulse?: boolean;
    }
  > = {
    disconnected: {
      icon: Plug,
      text: '连接中...',
      className: 'text-muted-foreground',
      pulse: true,
    },
    connecting: {
      icon: Loader2,
      text: '连接中...',
      className: 'text-warning',
      spin: true,
    },
    connected: {
      icon: PlugZap,
      text: `${availableTools.length} 个工具就绪`,
      className: 'text-success',
    },
    error: {
      icon: AlertCircle,
      text: '重连中...',
      className: 'text-warning',
      pulse: true,
    },
  };

  const config = statusConfig[mcpStatus];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <Icon
        className={cn(
          'w-3 h-3',
          config.className,
          config.spin && 'animate-spin',
          config.pulse && 'animate-pulse'
        )}
      />
      <span className={config.className}>{config.text}</span>
    </div>
  );
}

// Chatbox 主组件
export function Chatbox() {
  const [isOpen, setIsOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { state, sendMessage, clearMessages } = useChat();

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  // 聚焦输入框
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || state.isLoading) return;
    const message = inputValue;
    setInputValue('');
    await sendMessage(message);
  };

  // 键盘事件
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'fixed bottom-6 right-6 z-50',
          'w-14 h-14 rounded-full',
          'chat-fab',
          'flex items-center justify-center',
          'transition-all duration-300',
          isOpen && 'scale-0 opacity-0'
        )}
        aria-label="打开AI助手"
      >
        <Sparkles className="w-6 h-6" />
      </button>

      {/* 聊天窗口 */}
      <div
        className={cn(
          'fixed bottom-6 right-6 z-50',
          'w-[400px] h-[600px] max-h-[80vh]',
          'chat-window',
          'flex flex-col',
          'transition-all duration-300 origin-bottom-right',
          isOpen ? 'scale-100 opacity-100' : 'scale-0 opacity-0 pointer-events-none'
        )}
      >
        {/* 头部 */}
        <div className="chat-header flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="chat-header-icon w-8 h-8 rounded-full flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">AI 分析助手</h3>
              <ConnectionStatus />
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={clearMessages}
              className="p-2 rounded-md hover:bg-accent transition-colors"
              title="清空对话"
            >
              <Trash2 className="w-4 h-4 text-muted-foreground" />
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-md hover:bg-accent transition-colors"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-messages">
          {state.messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="chat-empty-icon w-16 h-16 rounded-full flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8" />
              </div>
              <h4 className="font-medium mb-2">开始对话</h4>
              <p className="text-sm text-muted-foreground max-w-[250px]">
                我可以帮你分析云厂商的产品更新动态，支持复杂的数据查询和对比分析。
              </p>
            </div>
          ) : (
            state.messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 错误提示 */}
        {state.error && (
          <div className="px-4 py-2 chat-error">
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{state.error}</span>
            </div>
          </div>
        )}

        {/* 输入区域 */}
        <div className="chat-input-area p-4">
          <div className="chat-input-container flex items-end gap-2 rounded-xl p-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题..."
              rows={1}
              className="flex-1 resize-none bg-transparent outline-none text-sm min-h-[36px] max-h-[120px] py-2 px-2"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
              }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || state.isLoading}
              className={cn(
                'chat-send-btn p-2 rounded-lg transition-all',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {state.isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
