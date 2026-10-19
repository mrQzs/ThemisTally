import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// 基址用相对路径，构建产物可原地打开；Vitest 用 jsdom，覆盖 src/tests/gate-probe 三处测试。
export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: [
      'src/**/*.test.{ts,tsx}',
      'tests/**/*.test.{ts,tsx}',
      'gate-probe/**/*.test.{ts,tsx}',
    ],
  },
});
