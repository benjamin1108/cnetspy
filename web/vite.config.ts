import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? '/next/' : '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Markdown 渲染
          'vendor-markdown': ['react-markdown', 'remark-gfm'],
          // 工具库
          'vendor-utils': ['axios', 'date-fns', '@tanstack/react-query'],
        },
      },
    },
    // 提高警告阈值（可选，如果分割后仍有大文件）
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8088',
        changeOrigin: true,
      },
      '/sse': {
        target: 'http://localhost:8089',
        changeOrigin: true,
      },
      '/messages': {
        target: 'http://localhost:8089',
        changeOrigin: true,
      },
    },
  },
}));
