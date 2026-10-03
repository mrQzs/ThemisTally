# Code-Kit v2：11 第二 CLI 接入分阶段路线图

基线：`62ef7021e3d8df711ecde0a4ee1b3f0a1a5148e2`。附件 `11-second-cli-adapter.md` 只作为需求与设计参考；不替代 `AGENTS.md`、合同或复审结论。

## 目标与边界

11 验证调度核心可以通过 adapter/profile 接入第二种 CLI，而不依赖 Pi 命令、事件或会话格式。首轮只完成候选能力模型、通用协议、离线第二 CLI stub、跨角色隔离、异常证据和 09 交接边界；不选择品牌、不安装依赖、不读取凭据、不调用真实 provider/CLI。

真实版本、help、模型、平台、shell、取消、用量和端到端异构链路必须经过独立授权与真实证据；离线通过只记 `LOCAL_REFERENCE`，真实项记 `NOT_RUN/BLOCKED`。

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

## 所有权与验证

`scripts/codekit/**`、`schemas/**` 由主模型直接维护；Pi 合同只接收测试、脱敏 fixture、文档和适配层外围范围。11 adapter 不拥有 approval、publication、budget、dispatch、进程清理或发布权限；这些继续由 03/07/09/05/核心调度器负责。

每个阶段至少执行相关定向测试、`python -m compileall -q scripts/codekit tests`、Schema JSON 校验和 `git diff --check`。阶段复审写入 `.agent/reviews/`；不手写 `.agent/runs/`。

真实 provider、第二 CLI、Pi、Windows/macOS 原生进程和外部连接器保持 `NOT_RUN/BLOCKED`，不以 stub、配置值或模型自述替代实际证据。
