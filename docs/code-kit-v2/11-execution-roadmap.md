# Code-Kit v2：11 第二 CLI 接入分阶段路线图

规划基线：`62ef7021e3d8df711ecde0a4ee1b3f0a1a5148e2`；当前实现头：`60dffbb`（文档更新随后单独提交）。附件 `11-second-cli-adapter.md` 只作为需求与设计参考；不替代 `AGENTS.md`、合同或复审结论。

## 目标与边界

11 验证调度核心可以通过 adapter/profile 接入第二种 CLI，而不依赖 Pi 命令、事件或会话格式。按用户选择，候选优先使用本机已安装且支持结构化输出的 CLI：本机已完成 `claude --version`/`claude --help` 免费探针（Claude Code 2.1.288），并保留 `codex --version`/`codex exec --help` 作为第二候选（codex-cli 0.160.0）。探针只证明可执行文件和帮助面可观察；没有启动模型请求，精确模型、认证、费用和生产能力仍未验证。

真实模型、平台进程、shell、取消、用量和端到端异构链路必须经过独立授权与真实证据；离线通过只记 `LOCAL_REFERENCE`，真实项记 `NOT_RUN/BLOCKED`。本轮已实现 provider-neutral 注册/路由、调用摘要绑定、只读跨会话 handoff、取消/响应丢失恢复分类和共享预算门禁；这些仍是离线协议实现，不构成生产接线。

## 阶段与子任务

| 阶段 | 子任务 | 主要出口 | 依赖 |
|---|---|---|---|
| S0 规范与基线 | `11-s0-1-baseline-owners`；`11-s0-2-traceability`；`11-s0-3-fixtures-env-gates` | 所有权、矩阵、夹具和能力门禁 | 09/10 当前提交 |
| S1 候选与能力协议 | `11-s1-1-candidate-matrix`；`11-s1-2-capability-schema`；`11-s1-3-profile-binding` | 候选选择条件、能力 Schema、角色/profile 匹配 | S0 |
| S2 离线适配器 | `11-s2-1-second-cli-offline-adapter`；`11-s2-2-event-normalization-fixtures`；`11-s2-3-identity-usage-evidence` | 不启动进程的第二 CLI adapter、事件和身份/用量证据 | S1 |
| S3 运行时边界 | `11-s3-1-invocation-isolation`；`11-s3-2-platform-shell-locks`；`11-s3-3-cancel-collect-recovery` | Invocation、会话隔离、平台声明、取消与恢复 | S2 |
| S4 09 交接 | `11-s4-1-planner-handoff`；`11-s4-2-executor-handoff`；`11-s4-3-budget-role-gates` | planner/executor 双 profile 交接和准入边界 | S3、09 |
| S5 Pi 兼容 | `11-s5-1-pi-regression`；`11-s5-2-profile-routing`；`11-s5-3-error-recovery` | Pi 历史行为保护、注册表路由、失败回退 | S2–S4 |
| S6 独立验收 | `11-s6-1-real-capability-preflight`；`11-s6-2-heterogeneous-matrix`；`11-s6-3-independent-gate` | 真实能力清单、异构矩阵和发布门禁 | 全部 |

## 当前阶段状态（2026-10-04）

- S0：已建立路线图、追踪矩阵、21 份合同草案和离线环境门禁；合同仍是规划材料，不能替代实现证据。
- S1：已实现能力 Schema、必须绑定 capability snapshot 的严格 profile routing、本机版本/help fixture/manifest 和 `PreflightResult`；版本不兼容、认证缺失、模型缺失/不匹配以及未观察 capability evidence 会分别阻塞或保持 `NOT_RUN`，模型调用与平台能力仍未观察。
- S2：已实现 Claude stream-json 离线事件归一化、原始记录引用、闭合 `CliEvent` 映射、终态/模型/用量/工具闭合检查和 replay 冲突拒绝。
- S3：已实现统一 facade、argv/no-shell 调用快照、必须绑定且校验 capability/platform 的 invocation executor gate、平台/环境/能力/环境名快照、stdin/资源闭包摘要、可验证的 raw byte fixture、事件上下文/终态/工具审计和取消/响应丢失分类；尚未接入真实 05 进程 runner。
- S4：已实现只读 planner→executor 跨会话 handoff、`validate_run_context(for_executor_dispatch=True)` 绑定、03 `ApprovalLedger` currentness/input-lock 校验、generation 校验、共享 `PlanningBudgetLedger` role gate 和 executor start gate；尚未接入 09 PlanningService 的真实启动入口。
- S5：已补 provider-neutral `ProfileRouter`、旧 `OfflineAdapter` 回归覆盖、保守取消状态（含 `CANCEL_AFTER_EXIT`）、幂等恢复账本、malformed fallback/recovery 输入拒绝和显式 fallback/re-review 门禁；尚未接入 Pi dispatcher、真实进程清理或重试协调。
- S6：已实现离线 `PreflightResult`、executor start gate 的 ready/profile/digest 绑定和 machine-checkable independent release gate；真实异构链路、平台矩阵和独立发布门禁仍继续 `NOT_RUN/BLOCKED`。

## 所有权与验证

`scripts/codekit/**`、`schemas/**` 由主模型直接维护；Pi 合同只接收测试、脱敏 fixture、文档和适配层外围范围。11 adapter 不拥有 approval、publication、budget、dispatch、进程清理或发布权限；这些继续由 03/07/09/05/核心调度器负责。

每个阶段至少执行相关定向测试、`python -m compileall -q scripts/codekit tests`、Schema JSON 校验和 `git diff --check`。阶段复审写入 `.agent/reviews/`；不手写 `.agent/runs/`。

真实 provider、第二 CLI、Pi、Windows/macOS 原生进程和外部连接器保持 `NOT_RUN/BLOCKED`，不以 stub、配置值或模型自述替代实际证据。
