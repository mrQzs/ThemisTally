# 07 故障矩阵（离线候选）

当前固定候选为 `8c16333ff8d3b80eda8c95216d1236d9f3fe23cf`；顶部早期候选记录保留为历史，最新故障证据见文末。

候选提交：`a2357b0`。`LOCAL_PARTIAL` 只表示已有纯 Python/SQLite 故障式单测或明确门禁；真实进程、provider、跨平台和外部系统故障仍为 `NOT_RUN`。

| 故障 | 当前状态 | 可复核入口 | 生产/环境缺口 |
|---|---|---|---|
| F01 | LOCAL_PARTIAL | `tests/test_integration_gates.py` | 未做固定候选 prepare/run 哈希注入 |
| F02 | LOCAL_PARTIAL | `tests/test_integration_gates.py` | 未接 09 readiness 生产入口 |
| F03 | LOCAL_PARTIAL | `tests/test_baseline_use.py`、`tests/test_readiness.py` | 未运行真实下游 |
| F04 | LOCAL_PARTIAL | `tests/test_integration_gates.py`、`tests/test_acceptance.py` | 未做固定候选 attempt |
| F05 | LOCAL_PARTIAL | `tests/test_integration_gates.py` | 未做提交许可真实门禁 |
| F06 | LOCAL_PARTIAL | `tests/test_coverage.py` | 未对真实后代 blob 变更注入 |
| F07 | LOCAL_PARTIAL | `tests/test_baseline_use.py`、`tests/test_acceptance.py` | 未做真实合流候选 |
| F08 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 未做多进程轮询 |
| F09 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py` | 未做响应丢失与重启 |
| F10 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py` | 未做 OS 资源故障 |
| F11 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py` | 未接真实 handoff |
| F12 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_runtime_lease.py` | 未运行真实 START_UNKNOWN 生命周期 |
| F13 | LOCAL_PARTIAL | `tests/test_runtime_lease.py` | 未核验真实子进程存活 |
| F14 | LOCAL_PARTIAL | `tests/test_runtime_lease.py`、`tests/test_resume_recovery.py` | 未做旧 controller 真实写入 |
| F15 | NOT_RUN | `tests/test_identity.py` 仅验证模型 | 未做 PID 复用/boot 变化 |
| F16 | LOCAL_PARTIAL | `tests/test_parallel.py`、`tests/test_attempt_allocator.py` | 未做真实模块锁 |
| F17 | LOCAL_PARTIAL | `tests/test_parallel.py` | 未接共享端口/产物锁 |
| F18 | NOT_RUN | — | Windows junction/macOS 路径适配器缺失 |
| F19 | LOCAL_PARTIAL | `tests/test_attempt_allocator.py`、`tests/test_budget.py` | 未做并行进程压力 |
| F20 | NOT_RUN | `tests/test_provider_economics.py` | 无真实隐藏调用观测能力 |
| F21 | NOT_RUN | — | 未接 message/summary/brief 费用去重 consumer |
| F22 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_budget_store_v2.py`、`tests/test_usage_settlement.py` | 未接真实 provider final/correction |
| F23 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_usage_settlement.py` | 未覆盖真实取消后的计量缺失 |
| F24 | LOCAL_PARTIAL | `tests/test_budget.py`、`tests/test_usage_settlement.py` | 未接真实 cap 超额账单 |
| F25 | LOCAL_PARTIAL | `tests/test_provider_economics.py`、`tests/test_budget.py`、`tests/test_usage_settlement.py` | 未接多币种结算服务 |
| F26 | LOCAL_PARTIAL | `tests/test_atomic_claim_budget.py`、`tests/test_unified_ledger.py` | 未做并发 stop/handoff |
| F27 | LOCAL_PARTIAL | `tests/test_unified_ledger.py`、`tests/test_budget.py` | 未接迟到生产日志/账单 |
| F28 | NOT_RUN | `tests/test_acceptance.py` | 未传播至排队/运行任务 |
| F29 | LOCAL_PARTIAL | `tests/test_projections.py`、`tests/test_unified_ledger.py` | 未运行真实 outbox consumer |
| F30 | LOCAL_PARTIAL | `tests/test_resume_recovery.py` | 未对真实旧备份做恢复演练 |

## 解释

每行的故障记录字段为：`row_id`（F01–F30）、`contract_ref`、`contract_base_sha=175653e`、`candidate_sha=a2357b0`、`injection_method`（表中可复核入口或 `NONE`）、`expected_state`（相应 F 规则要求）、`actual_evidence`（离线状态与测试入口）、`environment_blocker`（生产状态及缺口）、`raw_evidence`（`.agent/runs/<task>/attempt-*` 路径及 SHA-256）。本轮没有 Pi attempt，所有行的 `raw_evidence` 均为 `NONE/NO_ATTEMPT`；因此离线状态不会被解释成生产通过。

上述 LOCAL_PARTIAL 项不能升级为 PASS：本轮没有 `.agent/runs/<task>/attempt-*` 原始执行证据，也没有独立复审在固定候选上运行 `mutate`。Pi 环境证据见 `.agent/environment.md` 与 `.agent/runs/_env/`；其中执行模型和凭据未就绪，故真实执行器故障矩阵保持阻塞。

## 当前固定候选的新增离线证据

固定候选为 `ffce46b5400d1688ecb25bc754c487db3a1f05dc`。以下条目使用 `.agent/runs/offline-01-06-08-20261003-final-expanded-01/` 和 `.agent/runs/offline-01-06-08-20261003-dispatch-01/` 的原始取证；它们仍是 `LOCAL_REFERENCE`，不会覆盖真实环境状态：

| 故障 | 当前离线结果 | 故障输入/测试入口 | 限制 |
|---|---|---|---|
| F06 | LOCAL_REFERENCE | `S4MutationTests.test_mutation_requires_baseline_and_kills_every_mutant` | 没有固定候选真实 dispatcher mutate |
| F09、F11、F12 | LOCAL_REFERENCE | `S5ExecutionTests.test_platform_failures_reconcile_conservatively`；`test_deterministic_evidence_is_reference_only_without_dispatcher` | 无真实响应丢失、handoff 或 START_UNKNOWN 进程 |
| F16、F17 | LOCAL_REFERENCE | `tests.test_parallel` 资源冲突、Unicode 路径和容量边界测试 | 无多进程共享锁压力 |
| F20–F25 | NOT_RUN | `tests.test_provider_economics`、`tests.test_usage_settlement` 仅离线 fixture | 无真实 provider 隐藏调用和账单 |
| F18、F21、F28–F30 | BLOCKED/NOT_RUN | — | 原生平台、外部 consumer、真实恢复演练不可用 |

三项完整发现失败仍是 `a4fa199` legacy source-lock，不属于上述新增故障路径；详见固定候选复审报告。

## 2026-10-03 最终离线故障证据

插件故障/边界取证使用 `.agent/runs/offline-01-06-08-20261003-builtin-all-03/`（102 收集、95 通过、7 跳过），组合取证使用 `.agent/runs/offline-01-06-08-20261003-expanded-all-03/`（542 收集、534 通过、8 跳过）。新增 scope 伪造、生产 `PASS` 重放、READY 绑定不一致、授权 subject/input 闭包和编码后超限负例均在离线测试中执行。它们只能标记 `LOCAL_REFERENCE`；真实 PID/boot、provider 账单、跨平台进程、handoff/响应丢失和外部 consumer 故障继续 `NOT_RUN/BLOCKED`。

## 2026-10-03 最终候选（C1 边界修复后）

`8c16333ff8d3b80eda8c95216d1236d9f3fe23cf` 的两组 raw capture 均无漂移；C1 控制字符拒绝覆盖 docs path、local target、scope 和 review text。对应故障只可记为 `LOCAL_REFERENCE`，真实平台/provider/handoff/consumer 故障继续 `NOT_RUN/BLOCKED`。


## 2026-10-03 Current Candidate (296135c)

Fault and boundary captures for `296135cb8eef4cbf54585d755f3ca437f7e74a51` use `.agent/runs/offline-01-06-08-20261003-builtin-all-06/` and `.agent/runs/offline-01-06-08-20261003-expanded-all-06/`. SourceAnchor resource drift, out-of-range spans, forged excerpt digests, and post-construction InvocationSpec argv mutation have regression coverage; these results are `LOCAL_REFERENCE` only. Real PID/boot, cross-platform process, provider billing, handoff, external consumer, and recovery drills remain `NOT_RUN/BLOCKED`.
