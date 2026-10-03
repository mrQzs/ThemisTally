# Code-Kit v2：12 集成验收与迁移交付分阶段路线图

规划基线：`c71014517e3579e5bb465d277a6712c214e565b4`；当前现场核验头同为该提交。附件 `12-integration-and-migration-审阅增强版.md` 只作为需求矩阵和设计参考，不替代 `AGENTS.md`、已接受合同或独立复审结论。

## 目标与状态边界

12 的目标是把 01–11 的固定候选、证据、平台/CLI 能力与迁移操作汇总为可复算的集成交付结论，并保留 v1 历史字节、旧入口和用户工作。当前先建立阶段合同、离线证据和门禁；附录合成测试不能替代目标仓库、原生平台、真实异构 CLI、维护授权、备份恢复或生产迁移证据。

当前现场工作区干净。目标仓库的真实 G0–G6 全链路、三平台原生验收、第二 CLI 真实调用、Pi 执行、生产迁移、凭据/权限/预算、OS 强杀/断电和外部 CI 仍为 `NOT_RUN` 或 `BLOCKED`。`.agent/environment.md` 含历史 Pi ready/not_ready 记录，派遣前必须重新核验；本轮不读凭据、不安装依赖、不调用真实外部服务。

## 阶段与子任务

| 阶段 | 子任务 | 主要出口 | 依赖 |
|---|---|---|---|
| S0 规范、基线与合同 | `12-s0-1-baseline-owners`；`12-s0-2-traceability-matrix`；`12-s0-3-fixtures-environment-gates` | B/C/U 身份、责任边界、A/I/IT 矩阵、夹具与环境门禁 | 当前基线 |
| S1 集成候选与接口冻结 | `12-s1-1-integration-target`；`12-s1-2-interface-compatibility`；`12-s1-3-scope-input-freeze` | IntegrationTarget、01–11 接口交接、输入闭包与候选冻结 | S0 |
| S2 检查与证据聚合 | `12-s2-1-check-catalog`；`12-s2-2-check-observation`；`12-s2-3-coverage-reduction` | CheckCatalog/Observation、状态来源、无遗漏归约和失败可见性 | S1 |
| S3 证据与交付决定 | `12-s3-1-evidence-manifest`；`12-s3-2-delivery-decision`；`12-s3-3-no-omission-stale` | 受信证据清单、部分/完整决定、旧失败/过期/缺项保护 | S2 |
| S4 模块交接与离线工作流 | `12-s4-1-module-handoff-matrix`；`12-s4-2-plugin-workflow-offline`；`12-s4-3-legacy-regression-history` | 01–11 交接、三工作流离线检查、旧入口/历史回归 | S1–S3 |
| S5 迁移预检与操作协议 | `12-s5-1-migration-preflight-plan`；`12-s5-2-operation-receipt-cas`；`12-s5-3-history-integrity-rollback` | 只读盘点、逐字段预览、备份/切换 CAS、幂等、回退与冲突 | S3；05/07/10 当前接口 |
| S6 独立验收与发布门禁 | `12-s6-1-a01-a09-matrix`；`12-s6-2-fault-platform-blockers`；`12-s6-3-independent-gate` | A01–A29、I01–I12、IT01–IT36 独立复审、恢复操作册、发布结论 | S1–S5 |

S0 先冻结事实和合同。S1 通过后，S2 与 S5 的只读预检可并行；S3 等 S2 的检查归约；S4 需要模块交接证据；S6 等全部实现和复审完成。阶段通过后以新提交作为下游基线，不能把不同候选、不同环境或不同检查集拼成一条通过链。

## 所有权与禁止事项

`scripts/codekit/**`、`schemas/**`、核心调度器以及 03/05/07/09/10 生产真相源由主模型直接维护。普通 Pi 合同只接收外围测试、脱敏 fixture、文档和适配层验证，不能通过扩大 Scope 获取核心修改权限。`.agent/plans/` 合同成对固定；`.agent/runs/` 只由调度器生成且只读；`.agent/reviews/` 由规划端复审。

真实 provider、Pi、原生 Windows/macOS/WSL 组合、外部连接器、用户现场迁移和生产发布继续 `NOT_RUN/BLOCKED`。离线 fixture 只能标 `LOCAL_REFERENCE`，不能填写真实通过、费用、授权或回退完成。

## 阶段门与验证

每个子任务至少执行相关定向测试、`python -B -m compileall -q scripts/codekit tests`、JSON/Schema 校验和 `git diff --check`。阶段验收需核对 A 项证据、I 项不变量、IT 故障分类、Scope 闭包和未记录假设；迁移写操作还需维护授权、备份和用户现场确认。预览不得执行 setup/check、CLI 探测、模型调用、安装或外部写入。

基线核验记录见 `.agent/reviews/12-s0-baseline-20261004.md`。当前目标相关定向回归为 56 tests（通过），compileall 和 diff check 通过；全量 unittest 曾因长时间无输出中断，不能宣称全量 PASS。
