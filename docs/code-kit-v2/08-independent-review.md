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

最新固定候选为 `e8935e84f9b6c196394ac576115317ef3b2e1d1d`，最终规划端复核报告为 `.agent/reviews/offline-acceptance-20261003-final-v2.md`；早期候选和报告保留作历史证据。

最新复核文件已更新至候选 `8c16333ff8d3b80eda8c95216d1236d9f3fe23cf`，证据目录为 `offline-01-06-08-20261003-builtin-all-04` 和 `offline-01-06-08-20261003-expanded-all-04`；结论仍为 `REVISE/BLOCKED`。


## Current Candidate Review Update

The current candidate is `296135cb8eef4cbf54585d755f3ca437f7e74a51`; raw captures are `.agent/runs/offline-01-06-08-20261003-builtin-all-06/` and `.agent/runs/offline-01-06-08-20261003-expanded-all-06/`. Both returned 0, have `baseline_consistent=true`, and show no drift. The latest contract pairs are rebound to this SHA and 39 pairs pass `pi_dispatch validate`.

This proves only repeatable offline reference behavior on the fixed worktree. There is no Pi attempt, `review-pi` verdict, real provider, native process, or 09/10 consumer evidence; the independent stage conclusion remains `REVISE/BLOCKED`.


## Current Candidate Review Update (8348af6)

The current candidate is `8348af691d33e08f111b5cebbe852cb66f31a80b`; raw captures are `.agent/runs/offline-01-06-08-20261003-builtin-all-07/` and `.agent/runs/offline-01-06-08-20261003-expanded-all-07/`. Both returned 0, completed fully, have `baseline_consistent=true`, and show no drift. The current 39 contract pairs are rebound to this code SHA and validate successfully.

This is repeatable offline reference evidence only. No Pi attempt, `review-pi` verdict, real provider, native process, or 09/10 consumer evidence exists; the independent conclusion remains `REVISE/BLOCKED`.
