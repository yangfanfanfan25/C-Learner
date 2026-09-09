import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // 用 IPv4 字面量而非 localhost：Windows 上 localhost 优先解析为 IPv6 ::1，
        // 而后端只监听 IPv4（0.0.0.0:8000），会导致 Vite 代理 ECONNREFUSED。
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
