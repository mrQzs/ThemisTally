# 07 工作流与调度分阶段路线图 v1

基线：175653ebbe3059c012166dacfbf13b7eac67b41f
当前定向基线：195 项通过；Pi doctor 阻塞，模型与凭据未就绪。

本路线图按 S0–S6 七阶段组织，每阶段三个子任务。S0 先固化追踪矩阵、接口责任和证据基线；S1–S5 可按依赖并行；S6 汇总验收。受保护的 scripts/codekit/** 与 schemas/** 由主模型直接实现，Pi 只接外围测试、夹具、文档和适配层。

## 依赖图

S0 → (S1.1, S1.2, S1.3, S3.1, S3.3)
S1.3 + S2.1 → S2.2 → S2.3
S1.3 + S2.2 → S4.1 → (S4.2, S4.3)
S2.3 + S3.3 + S4.1 → (S5.1, S5.2, S5.3)
S1–S5 → S6

## 合同清单

01. [07-s0-1-traceability.v1](./07-s0-1-traceability.v1.md) — S0.1 A/F 追踪矩阵 — docs-only
02. [07-s0-2-contract-boundaries.v1](./07-s0-2-contract-boundaries.v1.md) — S0.2 接口与责任边界 — planner
03. [07-s0-3-fixtures-environment.v1](./07-s0-3-fixtures-environment.v1.md) — S0.3 Fixture 与环境预检 — docs-tests
04. [07-s1-1-git-currentness.v1](./07-s1-1-git-currentness.v1.md) — S1.1 Git 来源与当前性 — main-model
05. [07-s1-2-authorization-lineage.v1](./07-s1-2-authorization-lineage.v1.md) — S1.2 内容授权与接受链 — main-model
06. [07-s1-3-identity-locks.v1](./07-s1-3-identity-locks.v1.md) — S1.3 平台与资源身份锁 — main-model
07. [07-s2-1-unified-ledger.v1](./07-s2-1-unified-ledger.v1.md) — S2.1 统一账本迁移 — main-model
08. [07-s2-2-atomic-admission.v1](./07-s2-2-atomic-admission.v1.md) — S2.2 原子准入与幂等 — main-model
09. [07-s2-3-attempt-allocator.v1](./07-s2-3-attempt-allocator.v1.md) — S2.3 Attempt 分配与公平调度 — main-model
10. [07-s3-1-provider-identity.v1](./07-s3-1-provider-identity.v1.md) — S3.1 Provider 身份与隐藏调用 — main-model
11. [07-s3-2-usage-settlement.v1](./07-s3-2-usage-settlement.v1.md) — S3.2 Usage 修订与结算 — main-model
12. [07-s3-3-offline-provider.v1](./07-s3-3-offline-provider.v1.md) — S3.3 离线 Provider 适配 — tests-fixtures
13. [07-s4-1-process-identity.v1](./07-s4-1-process-identity.v1.md) — S4.1 进程身份与 OS 锁 — main-model
14. [07-s4-2-handoff-reconcile.v1](./07-s4-2-handoff-reconcile.v1.md) — S4.2 交接、取消与 reconcile — main-model
15. [07-s4-3-resume-recovery.v1](./07-s4-3-resume-recovery.v1.md) — S4.3 Resume 与高水位恢复 — main-model
16. [07-s5-1-projections.v1](./07-s5-1-projections.v1.md) — S5.1 09/10 投影 — main-model
17. [07-s5-2-outbox-cursors.v1](./07-s5-2-outbox-cursors.v1.md) — S5.2 Outbox 游标与重建 — main-model
18. [07-s5-3-integration-gates.v1](./07-s5-3-integration-gates.v1.md) — S5.3 跨阶段接线与生产门禁 — main-model
19. [07-s6-1-acceptance-matrix.v1](./07-s6-1-acceptance-matrix.v1.md) — S6.1 A 项逐项验收 — planner
20. [07-s6-2-fault-matrix.v1](./07-s6-2-fault-matrix.v1.md) — S6.2 F 项故障矩阵 — planner
21. [07-s6-3-independent-review.v1](./07-s6-3-independent-review.v1.md) — S6.3 独立复审与发布门禁 — planner

## 阶段门禁

- 每个子任务必须先核对 base_sha 和 Scope，再运行定向检查。
- 任何 NOT_RUN、BLOCKED 或未绑定证据的 A/F 项不得标为 PASS。
- 每阶段通过审阅后提交并推送；并行子任务必须在同一基线、范围不重叠后再集成。
- Pi 环境未就绪前不派遣；主模型直接修改 protected core 时保留同样的合同、测试和复审证据。
