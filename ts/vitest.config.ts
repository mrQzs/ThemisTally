import { defineConfig } from "vitest/config";

// 契约测试要起 Python、Node、Bun 子进程，单个用例给足时间；按文件并行，文件内串行
export default defineConfig({
  test: {
    include: ["packages/*/test/**/*.test.ts"],
    environment: "node",
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
});
