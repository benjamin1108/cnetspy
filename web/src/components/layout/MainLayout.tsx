/**
 * 主布局组件
 */

import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Chatbox } from '@/components/chat';
import { ChatProvider } from '@/contexts/ChatContext';
import config from '@/config';

export function MainLayout() {
  return (
    <ChatProvider config={config.chat}>
      <div className="min-h-screen bg-background">
        <Header />
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Outlet />
        </main>
        <Chatbox />
      </div>
    </ChatProvider>
  );
}
