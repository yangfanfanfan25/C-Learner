import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// 测试目录为仓库根 `test/`（spec 9.1 允许的范围）。setup 由各测试文件显式
// import（避免跨 Vite root 的 setupFiles /@fs/ 解析问题）。
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // 允许访问仓库根 `test/`（位于 Vite root apps/web 之外）
      allow: [path.resolve(__dirname, '../../')],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // 测试文件位于 Vite root 之外（仓库根 test/），裸导入需显式指向 apps/web 的
      // node_modules（root 之外的模块解析会向上找，找不到 apps/web/node_modules）。
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'react-router-dom': path.resolve(__dirname, 'node_modules/react-router-dom'),
      vitest: path.resolve(__dirname, 'node_modules/vitest'),
      '@testing-library/react': path.resolve(__dirname, 'node_modules/@testing-library/react'),
      '@testing-library/jest-dom': path.resolve(__dirname, 'node_modules/@testing-library/jest-dom'),
      '@testing-library/user-event': path.resolve(__dirname, 'node_modules/@testing-library/user-event'),
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    dir: path.resolve(__dirname, '../../test'),
    include: ['**/*.{test,spec}.{ts,tsx}'],
  },
});
