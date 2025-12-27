/**
 * 前端配置
 * 所有可配置项集中管理，禁止硬编码
 */

import type { ChatConfig } from '@/types/chat';

// 从环境变量或默认值获取配置
export const config = {
  // API 基础路径
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  
  // AI Chatbox 配置
  chat: {
    mcpServers: [
      {
        name: 'cloudnetspy',
        url: import.meta.env.VITE_MCP_SERVER_URL || 'http://cnetspy.site:8089/sse',
      },
    ],
    maxMessages: 100,
  } as ChatConfig,
};

export default config;
