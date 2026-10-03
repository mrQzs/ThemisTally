# 07 验收矩阵（候选提交）

当前固定候选已推进至 `8c16333ff8d3b80eda8c95216d1236d9f3fe23cf`；文档中的早期候选和计数均保留为历史映射，最新离线取证见本文末尾。

历史候选提交：`ef5ff25e9f41cea1096f75d31b027ef4dafcb66b`（下文早期 v1 行保留为历史映射）。该矩阵只记录可复核的离线候选；没有 Pi attempt、真实 provider、真实 OS 进程或 09/10 生产连接证据时，不得使用 `PASS`。

## 统一验证命令

定向命令：

```text
python -m unittest tests.test_workflow tests.test_readiness tests.test_baseline_binding tests.test_git_probe tests.test_git_ancestor tests.test_coverage tests.test_claim_model tests.test_scheduler_store tests.test_parallel tests.test_budget tests.test_budget_store_v2 tests.test_retry tests.test_atomic_claim_budget tests.test_acceptance tests.test_recovery tests.test_identity tests.test_provider_economics tests.test_offline_provider tests.test_unified_ledger tests.test_currentness tests.test_baseline_use tests.test_projections tests.test_runtime tests.test_runtime_lease tests.test_resume_recovery tests.test_builtin_s4_s6 tests.test_builtin_artifacts tests.test_plugins tests.test_plugin_validation_boundaries tests.test_builtin_recipe_compiler tests.test_builtin_schema_instances tests.test_attempt_allocator tests.test_integration_gates tests.test_usage_settlement tests.test_adapters tests.test_config_profiles tests.test_config_policy_boundaries tests.test_authorization tests.test_authorization_boundaries tests.test_authorization_store -q
```

当前结果：478 项通过，8 项跳过。早期结果保留在历史记录中。通用门禁：`python -m compileall -q scripts/codekit tests`、`git diff --check` 通过；当前 `python tests/test_dispatch.py` 未形成新通过证据，历史 255 checks 记录仅供参考。旧候选全量结果 895 项、31 项跳过、1 项环境失败也仅保留为历史记录。

原始调度器证据目录只有 `.agent/runs/_env/` 的 doctor 记录；本轮没有生成 Pi attempt。因此下表的“证据”列是可定位的源文件/测试和本审计报告，而不是伪造的运行证据。

## 合同与实际范围

S6 v1 合同仍记录 `contract_base_sha=175653e`，而本候选是 `candidate_sha=a2357b0`；本表是对候选的本地审计，不修改已派遣合同。实际实现文件与 v1 预期文件名有少量差异：例如 S1.1 使用 `currentness.py`/`test_currentness.py`，S1.2 使用 `baseline_use.py`/`test_baseline_use.py`，S1.3 使用 `identity.py`/`test_identity.py`，S5.2 使用 `projections.py`/`test_projections.py`。这些差异只作为审计映射记录，不扩大合同 Scope；Pi 环境恢复后必须以当前候选为基线创建合同 v2。

## A 项

每行的证据记录采用同一字段：`row_id`（A01–A30）、`contract_ref`（对应 `.agent/plans/07-*.v1.md`）、`contract_base_sha=175653e`、`candidate_sha=a2357b0`（历史 v1 映射）、`command`（上面的统一命令或明确的定向命令）、`input_summary`（固定候选和离线事实）、`output_summary`（表内状态及测试入口）、`raw_evidence`（`.agent/runs/<task>/attempt-*` 路径及 SHA-256）。本轮没有 Pi attempt，故每行 `raw_evidence` 都是 `NONE/NO_ATTEMPT`；这是真实证据缺口，也是所有 `LOCAL_PARTIAL`/`NOT_RUN` 状态的原因。

| 项 | 当前结论 | 可复核证据 | 仍缺的证据或限制 |
|---|---|---|---|
| A01 | LOCAL_PARTIAL | `tests/test_workflow.py`；定向命令 | 需固定候选 attempt 证据 |
| A02 | LOCAL_PARTIAL | `tests/test_workflow.py`、`scripts/codekit/workflow.py` | 未接入生产规划 CLI |
| A03 | LOCAL_PARTIAL | `tests/test_readiness.py`、`tests/test_coverage.py`、`scripts/codekit/currentness.py` | 未运行真实当前性探针 |
| A04 | LOCAL_PARTIAL | `tests/test_parallel.py`、`scripts/codekit/parallel.py` | 未运行跨平台路径适配器 |
| A05 | LOCAL_PARTIAL | `tests/test_claim_model.py`、`tests/test_scheduler_store.py`、`tests/test_atomic_claim_budget.py` | 未做真实重启与数据库部署验证 |
| A06 | LOCAL_PARTIAL | `tests/test_acceptance.py`、`tests/test_atomic_claim_budget.py` | 未接生产下游调度 |
| A07 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_retry.py` | 未覆盖真实 provider 隐藏调用 |
| A08 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_parallel.py`、`tests/test_atomic_claim_budget.py` | 未做并发进程压力验证 |
| A09 | LOCAL_PARTIAL | `tests/test_acceptance.py`、`tests/test_coverage.py` | 未接真实 rebase/merge 回查 |
| A10 | LOCAL_PARTIAL | `tests/test_recovery.py`、`tests/test_resume_recovery.py` | 未做崩溃故障注入 |
| A11 | LOCAL_PARTIAL | `tests/test_workflow.py` | 未做生产重排回放 |
| A12 | LOCAL_PARTIAL | `tests/test_workflow.py`、`tests/test_baseline_binding.py` | Schema 与映射仍为离线边界 |
| A13 | LOCAL_PARTIAL | `tests/test_acceptance.py`、`scripts/codekit/baseline_use.py` | 未验证外部接受记录服务 |
| A14 | LOCAL_PARTIAL | `tests/test_git_probe.py`、`tests/test_git_ancestor.py`、`tests/test_coverage.py` | 未完成真实 HEAD/dirty/untracked 接线 |
| A15 | LOCAL_PARTIAL | `tests/test_scheduler_store.py`、`tests/test_parallel.py` | 未做多进程唯一性证明 |
| A16 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 持久 schema/迁移尚非生产部署 |
| A17 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 未做跨进程响应丢失故障注入 |
| A18 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 未接 OS handoff |
| A19 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_runtime_lease.py` | 未核验真实 lease/进程 |
| A20 | LOCAL_PARTIAL | `tests/test_identity.py`、`tests/test_parallel.py` | 未做 Windows junction 与 macOS 路径适配 |
| A21 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_budget_store_v2.py`、`tests/test_usage_settlement.py` | provider 账单来源仍为离线输入 |
| A22 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_atomic_claim_budget.py`、`tests/test_usage_settlement.py` | 未做真实超预算入账 |
| A23 | LOCAL_PARTIAL | `tests/test_provider_economics.py`、`tests/test_offline_provider.py`、`tests/test_usage_settlement.py` | 未发现隐藏 provider 调用 |
| A24 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_provider_economics.py`、`tests/test_usage_settlement.py` | 未接真实汇率或结算系统，未知币种必须隔离 |
| A25 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 未做迟到生产账单接线 |
| A26 | LOCAL_PARTIAL | `tests/test_acceptance.py`、`scripts/codekit/baseline_use.py` | 未接撤销传播链 |
| A27 | LOCAL_PARTIAL | `tests/test_recovery.py`、`tests/test_runtime_lease.py` | 未做真实 boot/PID fencing |
| A28 | NOT_RUN | `scripts/codekit/projections.py` 仅有离线 readiness | 未连接 09 规划调用、独立授权和预算归属 |
| A29 | NOT_RUN | `tests/test_projections.py`、`scripts/codekit/projections.py` | 未部署 10 consumer/cursor 与权威重建 |
| A30 | LOCAL_PARTIAL | `tests/test_resume_recovery.py`、`tests/test_unified_ledger.py` | 未做数据库/资源/授权高水位生产恢复 |

## 证据规则

- `LOCAL_PARTIAL` 表示源码与定向单测可复核，不代表真实接线或独立 S6 通过。
- `NOT_RUN` 表示当前没有合格输入、生产连接或 Pi attempt 证据。
- 本矩阵的早期历史行绑定候选提交 `a2357b0`；当前候选为 `ef5ff25e9f41cea1096f75d31b027ef4dafcb66b`，变更候选后必须重新生成命令输出和审计报告，不能沿用旧结论。


## 当前候选增量

前一候选 `a64f3a836f5f5c0ca5f405c2b21efb210086b3e4` 的统一命令包含账本、插件、配方和 schema 边界套件，结果为 398 项通过、8 项跳过。对应 39 对 v2 合同已绑定该完整代码提交并通过 `pi_dispatch validate`；没有 Pi attempt，生产门禁仍为 `REVISE/BLOCKED`。

当前候选 `ef5ff25e9f41cea1096f75d31b027ef4dafcb66b` 在扩展组合回归保持 478 项通过、8 项环境跳过，并覆盖适配器、配置、身份和授权边界定向回归；39 对 v2 合同均已绑定该代码基线并通过 `pi_dispatch validate`。

当前候选 `ef5ff25e9f41cea1096f75d31b027ef4dafcb66b` 另加入旧 projections readiness/outbox 接口的 C1/代理/安全整数/event_id 边界回归；`tests.test_projections` 与集成套件通过，扩展组合共 478 项通过、8 项环境跳过。

## 2026-10-03 最新固定候选

最新候选为 `ffce46b5400d1688ecb25bc754c487db3a1f05dc`，由 `fix: harden claim retry and workflow boundaries` 提交并已推送。扩展组合取证目录为 `.agent/runs/offline-01-06-08-20261003-final-expanded-01/`；命令实际结果为 `Ran 484 tests`、`OK (skipped=8)`，即 476 项执行通过、8 项因 Windows 环境缺少可选 Schema 依赖而跳过。取证记录确认命令已执行、返回码为 0、前后输入清单无漂移。

新增边界覆盖包括 claim receipt 与 SQLite lease 的非负安全整数范围、并行资源键的公共路径规则及容量上限、retry attempt/sequence 饱和与溢出等待、workflow currency cap 的运行时与 Schema 上限。相关定向取证目录为 `.agent/runs/offline-01-06-08-20261003-targeted-02/` 与 `.agent/runs/offline-01-06-08-20261003-expanded-05/`；完整发现取证为 `.agent/runs/offline-01-06-08-20261003-full-discover-01/`，结果 `Ran 1164 tests`、`FAILED (failures=3, skipped=38)`，三项均为既有 `a4fa199` legacy source-lock，不是本提交新增失败。

compileall、`git diff --check`、WSL Python 3.12 Schema 7 项和 stub dispatch 取证均通过，分别见 `.agent/runs/offline-01-06-08-20261003-compile-01/`、`diffcheck-01/`、`schema-wsl-01/` 和 `dispatch-01/`。这些是本地离线/fixture 证据；没有 Pi attempt、真实 provider、原生 macOS/Windows 进程或 09/10 外部连接器证据，因此 A/F 与生产门禁仍不能标记 PASS。

## 2026-10-03 最终离线候选复核

最终候选为 `e8935e84f9b6c196394ac576115317ef3b2e1d1d`，已推送到 `origin/master`。插件全集取证目录为 `.agent/runs/offline-01-06-08-20261003-builtin-all-03/`，实际 `Ran 102 tests`、`OK (skipped=7)`，即 95 项执行通过、7 项因 Windows 环境缺少可选 Schema 依赖而跳过。01–06/08 扩展组合取证目录为 `.agent/runs/offline-01-06-08-20261003-expanded-all-03/`，实际 `Ran 542 tests`、`OK (skipped=8)`，即 534 项执行通过、8 项跳过。两份 capture 均记录返回码 0、命令已执行、前后输入清单无漂移。

本轮新增证据覆盖授权/配置编码后字节上限、approval subject/input 闭包、空 adapter option schema、三 recipe 的 catalog 版本与闭合 DAG、docs-change scope/生产状态重验证，以及 review readiness 的闭合绑定。它们仍是离线 `LOCAL_REFERENCE`；没有当前候选的 Pi attempt、真实 provider、原生 Windows/macOS 进程、09/10 连接器或独立 `review-pi` verdict，因此阶段和生产发布门禁继续为 `REVISE/BLOCKED`。

## 2026-10-03 最终候选（C1 边界修复后）

`8c16333ff8d3b80eda8c95216d1236d9f3fe23cf` 已推送。新的 capture 为 `.agent/runs/offline-01-06-08-20261003-builtin-all-04/`（102 收集、95 通过、7 跳过）和 `.agent/runs/offline-01-06-08-20261003-expanded-all-04/`（542 收集、534 通过、8 跳过）；两者返回码均为 0，且 `baseline_consistent=true`、无漂移。C1 控制字符负例已纳入 docs-change、docs-check 和 review oracle。Pi/provider/native/09/10 仍未运行，门禁继续 `REVISE/BLOCKED`。


## 2026-10-03 Current Candidate (296135c)

The current code candidate is `296135cb8eef4cbf54585d755f3ca437f7e74a51`. The runtime and artifact boundary fixes were re-captured: `.agent/runs/offline-01-06-08-20261003-builtin-all-06/` contains 103 collected, 96 passed, and 7 skipped; `.agent/runs/offline-01-06-08-20261003-expanded-all-06/` contains 544 collected, 536 passed, and 8 skipped. Both captures returned 0, completed fully, and show no input drift.

SourceAnchor byte binding and InvocationSpec argv freezing improve offline verifiability only. There is still no Pi attempt or independent `review-pi` verdict, so A/F rows remain `LOCAL_REFERENCE`, `NOT_RUN`, or `BLOCKED` and cannot become a stage PASS.
