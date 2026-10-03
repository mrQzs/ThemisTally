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


## Current Candidate Review Update (5d141298)

The current candidate is `5d141298d052b291c1dba3fe35075d6303f0bbc8`. Raw captures are `.agent/runs/offline-01-06-08-20261003-builtin-all-08/` and `.agent/runs/offline-01-06-08-20261003-expanded-all-08/`; they report 107/100/7 and 552/544/8 (collected/passed/skipped), return code 0, `baseline_consistent=true`, and no drift.

SourceAnchor builder wiring and the strict authorization receipt probe are covered by new offline tests. The latest 39 contract pairs validate with 0 warnings. This remains planning-side `LOCAL_REFERENCE` evidence only: there is no Pi attempt, `review-pi` verdict, real provider, native process, or 09/10 consumer evidence, so the independent conclusion remains `REVISE/BLOCKED`.

## 2026-10-03 Full Discover Timeout Update

Candidate \`5d141298d052b291c1dba3fe35075d6303f0bbc8\` remains the last implementation candidate; publication commit is \`99bda89b9f61754b7bbdc206f4a1ed97425e16a5\`. The fresh capture \`.agent/runs/offline-01-06-08-20261003-full-discover-09/\` attempted \`python -B -m unittest discover -s tests -q\` under the supervisor for 900.031 seconds. It timed out with \`returncode=null\`, \`timed_out=true\`, \`termination_confirmed=true\`, \`stray_processes=false\`, empty stdout/stderr, and no baseline drift. \`execution_status=complete\` only means the capture itself is complete; the test result is \`TIMEOUT/BLOCKED\`, not PASS. The 01–06 and 08 stage gates therefore remain \`REVISE/BLOCKED\`, with real Pi/provider/native platform/09/10 connector evidence still \`NOT_RUN/BLOCKED\`.
## 2026-10-03 修复候选复核补充

候选 `a1e15c157734af1ec84ce46ce8bc6ef1e2455c0a` 已推送。新增修复覆盖取消 operation 后 stale attempt 复活、attempt/outbox 重开绑定、provider 跨 task/request 经济去重、已释放未启动预算的 unknown 误判，以及 AnalysisReport/ChangeReport/ReviewBundle 的 READY 组合边界。定向回归 113 项通过；全量 discover 的 3 项失败仍是既有 `a4fa199` legacy source-lock，不产生新的业务失败结论。

本补充仍是规划端离线复核，未产生 Pi attempt、`review-pi` verdict、真实 provider/native/09/10 或生产 dispatcher receipt，因此总体结论保持 `REVISE/BLOCKED`。

## 2026-10-03 05/06 与 08-S6 复核补充

候选 `35b550fb7b49e55f502c56a011db9a648be0a897` 已推送。runtime identity fence、plugin resource path alias fence、projection event/cursor fence 的离线回归已通过；S4/S5 审计没有将 reference-only 结果升级为生产证据。

仍不存在 Pi attempt、`review-pi` verdict、真实 OS/provider、mutation dispatcher 或 09/10 consumer receipt，因此独立结论保持 `REVISE/BLOCKED`。

## 2026-10-03 S4 runner 复核补充

候选 `f38df44` 的 offline runner 输入边界修复已通过定向回归。该结果只证明离线错误分类与确定性边界；仍不存在真实 mutation dispatcher、Pi/provider/native 或 09/10 receipt，独立结论保持 `REVISE/BLOCKED`。

候选随后推进到 `ea25ed2`，S6 healthy brief 的 coverage/issues 一致性回归通过；没有新增真实连接器或 dispatcher 证据，独立结论仍为 `REVISE/BLOCKED`。

候选随后推进到 `addfab1`，09/10 wiring gate 的 state 输入类型边界回归通过；没有新增真实连接器或 dispatcher 证据，独立结论仍为 `REVISE/BLOCKED`。

## Current Candidate Review Update (eae9bfc / db46200)

The fixed code candidate is `eae9bfca4cf7351b02b7b5eafd6f101664b418ee`; the 39-contract publication is `db46200d75ff1462837996bab7450e09a9a88f46`. New raw captures are `.agent/runs/offline-01-06-08-20261003-builtin-contracts-eae9bfc/` and `.agent/runs/offline-01-06-08-20261003-expanded-contracts-eae9bfc/`. The builtin suite is 117 collected / 109 passed / 8 optional skips with return code 0. The expanded matrix is 1040 collected / 1 known legacy source-lock failure / 35 environment skips with return code 1. Both captures are complete, `baseline_consistent=true`, and drift-free.

The candidate hardens offline provider allocation scope, catalog/recipe fixture file boundaries, docs-change portable path and hash shapes, fixed content-oracle closure, review-bundle candidate/environment binding, runtime rejected-handoff behavior, and unified-ledger zero-cursor reopen and attempt plan-version binding. These are planning-side `LOCAL_REFERENCE` results. There is no Pi attempt, `review-pi` verdict, trusted dispatcher receipt, real provider, native OS process, or 09/10 consumer evidence; the independent stage conclusion remains `REVISE/BLOCKED` and the production gate stays closed. The detailed review is `.agent/reviews/offline-acceptance-20261003-final-v7.md`.
