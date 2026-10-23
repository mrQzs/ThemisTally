# @themis/ui

桌面端的本机服务（`docs/themis-tally-3.0-桌面端.md`，第 7 版 §0.0a）：Bun 运行，只绑 127.0.0.1，是桌面端唯一的后端，也是安全边界（D4）。所有路由起子进程跑 `python <kernel> --repo <仓库> <argv…> --json`（T2），子进程由 `@themis/base/supervise` 监督（T4）。

- 入口：`src/main.ts` 的 `runUi`。内核仓库里经 `pi_dispatch.py ui --desktop --assets <目录> …` 转交（调度器第 73 轮）；桌面应用里外壳直接起打包好的程序（T6）。
- 本包不在内核禁区里（迁移计划第 69 轮），经 hub 派给执行器；`package.json` 与 `bun.lock` 的登记由规划端维护（禁区里的工作区文件）。
- 测试在 `test/`，Vitest 起真的服务进程发 HTTP 请求（T10）。
