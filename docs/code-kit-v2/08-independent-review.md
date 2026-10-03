# 08 独立复审说明

## 范围

本说明记录规划端对固定离线候选的复核入口。它不构成 Pi attempt，也不替代 `review-pi` 要求的独立 `codex exec --sandbox read-only` 会话。

候选 `ffce46b5400d1688ecb25bc754c487db3a1f05dc` 的离线证据位于 `.agent/runs/`，当前复核报告为 `.agent/reviews/offline-acceptance-20261003-final.md`。报告逐项记录命令返回码、跳过项、既有 legacy source-lock 失败和取证限制。

## 结论规则

- `LOCAL_REFERENCE` 只表示固定源码和 fixture 在本地复核中可重复。
- `REFERENCE_ONLY`、`NOT_RUN`、`BLOCKED` 不得提升为生产 `PASS`。
- 真实 Pi/provider、Windows/macOS 原生进程和 09/10 连接器缺失时，相关行必须保留 `NOT_RUN` 或 `BLOCKED`。
- 合同必须绑定实际测试函数、输入和原始取证目录；不存在的测试文件和文件存在性检查不能作为行为覆盖证据。

## 下一次独立复审输入

独立复审者应读取对应 attempt 的 `plan.md`、`summary.md`、`scope.json`、`candidate.patch` 和最新 checks/mutations，并在固定候选上重新运行合同检查。当前没有符合这些条件的 Pi attempt，因此 08 阶段结论保持 `REVISE/BLOCKED`。
