import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// 基址用相对路径，构建产物可原地打开；Vitest 用 jsdom，覆盖 src/tests/gate-probe 三处测试。
// 模式开关是构建期常量、只跟 command 走：build 走真实服务，dev server 与 vitest 走夹具。
// 刻意不跟环境变量走——预设 development 或 test 时 vite build 照样成功、产物里的生产标记却是假的，
// 读函数会整个退回夹具。
export default defineConfig(({ command }) => ({
  base: './',
  plugins: [react()],
  define: {
    __THEMIS_LIVE_MODE__: JSON.stringify(command === 'build' ? 'themis-live-real' : 'themis-live-fixture'),
  },
  test: {
    environment: 'jsdom',
    include: [
      'src/**/*.test.{ts,tsx}',
      'tests/**/*.test.{ts,tsx}',
      'gate-probe/**/*.test.{ts,tsx}',
    ],
  },
}));
