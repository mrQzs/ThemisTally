# Code-Kit v2：11 第二 CLI 追踪矩阵

规划基线：`62ef7021e3d8df711ecde0a4ee1b3f0a1a5148e2`；当前实现头：`943278d`（文档更新随后单独提交）。附件需求矩阵不自动授予真实调用或费用权限。

## 11-A01–A08

| ID | 覆盖阶段 | 验收主题 | 当前状态 |
|---|---|---|---|
| A01 | S1/S2/S5 | 注册表和 profile 接入无需核心品牌分支 | PARTIAL：已实现 provider-neutral facade/profile router，并要求 capability snapshot；未接入生产 dispatcher |
| A02 | S1/S6 | 精确版本、模型、平台能力有来源；不支持组合预检阻塞 | PARTIAL：版本/help 有本机证据；未观察 capability evidence 或 `READY` preflight 时 start gate 拒绝，精确模型/原生平台仍未观察 |
| A03 | S2/S3 | 畸形、截断、无结束、非零退出不能正常成功 | PARTIAL：离线归一化/收集拒绝已覆盖 |
| A04 | S2/S4 | 实际模型缺失/不符不由配置值填补 | PARTIAL：模型身份需事件证据，executor gate 还需当前 ApprovalBinding；真实调用未运行 |
| A05 | S2/S3 | 原始记录与统一事件可互相定位，工具审计缺口保留 | PARTIAL：raw ref、半开范围、闭合事件映射、handoff/invocation resource closure 和嵌套工具审计已实现，持久 spool 未接入 |
| A06 | S4/S6 | 至少一组真实不同 CLI 规划→审核→执行→验收链路 | BLOCKED |
| A07 | S3/S6 | 真实入口、shell、取消和环境锁经核验 | BLOCKED：离线 gate 已核对具体 invocation、capability/platform digest、argv/no-shell、环境/平台快照和 READY preflight，真实入口仍未运行 |
| A08 | S2/S5/S6 | unknown 用量、认证缺失、版本不兼容有明确状态和恢复路径 | PARTIAL：unknown、认证缺失、版本不兼容、模型漂移、malformed recovery/fallback 输入和审批撤销有机器状态；真实认证/版本回退未运行 |

`PARTIAL` 仅表示已有通用/离线原语；`BLOCKED` 表示真实能力未授权或不可用；`GAP` 表示尚未建立实现与证据。

## 11-F01–F10 与能力门禁

| 范围 | 状态 | 说明 |
|---|---|---|
| F01–F10 | NOT_RUN/BLOCKED | 真实第二 CLI、平台进程、模型、费用、取消和宿主接线尚未执行；离线错误流只能记 `LOCAL_REFERENCE`。 |

11 不因离线 adapter 通过而关闭 G1、范围、独立检查或原始证据保留门禁；真实 release gate 继续阻塞。
