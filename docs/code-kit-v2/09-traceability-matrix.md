# Code-Kit v2：09 追踪矩阵

基线：`330d3716d65e068c38a5861e2a1a4bf4c84cf043`。附件 09 设计文档只作为需求参考；授权和执行范围以 `AGENTS.md` 与对应合同为准。

## 记录规则

- `A01–A28` 是离线可验收项；每个条目必须有代码/fixture、定向测试和 `.agent/runs/` 证据。
- `I01–I30` 是真实集成/故障矩阵；不能用 mock 或离线 PASS 伪装生产证据，缺少真实能力时填 `NOT_RUN` 或 `BLOCKED`。
- `LOCAL_REFERENCE` 表示可复核的离线实现或录制结果，不授予批准、执行、计费或发布权限。

## A 项追踪

| ID | 契约 | 验收主题 | 证据要求 | 状态 |
|---|---|---|---|---|
| A01 | `09-s0-1` | 来源感知与基线身份 | 实现 + 定向测试 + 复审摘录 | TODO |
| A02 | `09-s0-1` | v1 兼容登记 | 实现 + 定向测试 + 复审摘录 | TODO |
| A03 | `09-s0-1` | 旧合同/证据不可变 | 实现 + 定向测试 + 复审摘录 | TODO |
| A04 | `09-s0-1` | 规划请求幂等 | 实现 + 定向测试 + 复审摘录 | TODO |
| A05 | `09-s0-2` | 字段所有权 | 实现 + 定向测试 + 复审摘录 | TODO |
| A06 | `09-s0-2` | 状态正交性 | 实现 + 定向测试 + 复审摘录 | TODO |
| A07 | `09-s0-2` | 发布与投影边界 | 实现 + 定向测试 + 复审摘录 | TODO |
| A08 | `09-s0-3` | PlanningRequest 严格解析 | 实现 + 定向测试 + 复审摘录 | TODO |
| A09 | `09-s0-3` | ContextManifest 绑定 | 实现 + 定向测试 + 复审摘录 | TODO |
| A10 | `09-s0-3` | 真实能力门禁 | 实现 + 定向测试 + 复审摘录 | TODO |
| A11 | `09-s1-1` | 图优先两级规划 | 实现 + 定向测试 + 复审摘录 | TODO |
| A12 | `09-s1-1` | 唯一可信结果 | 实现 + 定向测试 + 复审摘录 | TODO |
| A13 | `09-s1-1` | 结构限制与负例 | 实现 + 定向测试 + 复审摘录 | TODO |
| A14 | `09-s1-1` | 严格 JSON/Unicode | 实现 + 定向测试 + 复审摘录 | TODO |
| A15 | `09-s1-2` | SourceAnchor 字节坐标 | 实现 + 定向测试 + 复审摘录 | TODO |
| A16 | `09-s1-2` | 事实等级与假设 | 实现 + 定向测试 + 复审摘录 | TODO |
| A17 | `09-s1-2` | 需求覆盖与问题 | 实现 + 定向测试 + 复审摘录 | TODO |
| A18 | `09-s1-3` | 任务/阶段 DAG | 实现 + 定向测试 + 复审摘录 | TODO |
| A19 | `09-s1-3` | 插件引用和类型 | 实现 + 定向测试 + 复审摘录 | TODO |
| A20 | `09-s1-3` | scope/check 静态边界 | 实现 + 定向测试 + 复审摘录 | TODO |
| A21 | `09-s2-1` | draft revision/CAS | 实现 + 定向测试 + 复审摘录 | TODO |
| A22 | `09-s2-1` | 版本槽与预算根 | 实现 + 定向测试 + 复审摘录 | TODO |
| A23 | `09-s2-2` | ContractIR 同源渲染 | 实现 + 定向测试 + 复审摘录 | TODO |
| A24 | `09-s2-2` | 字节冻结与合同校验 | 实现 + 定向测试 + 复审摘录 | TODO |
| A25 | `09-s2-3` | 候选双成员绑定 | 实现 + 定向测试 + 复审摘录 | TODO |
| A26 | `09-s3-1` | 审核/锁/currentness | 实现 + 定向测试 + 复审摘录 | TODO |
| A27 | `09-s3-2` | PublicationReceipt/登记事务 | 实现 + 定向测试 + 复审摘录 | TODO |
| A28 | `09-s3-3` | 全入口固定字节门禁 | 实现 + 定向测试 + 复审摘录 | TODO |

## I 项追踪

| ID | 契约 | 集成/故障主题 | 离线证据或环境记录 | 状态 |
|---|---|---|---|---|
| I01 | `09-s0-1` | v1 来源路由 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I02 | `09-s0-1` | 旧证据保护 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I03 | `09-s0-1` | 降级绕过拒绝 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I04 | `09-s0-2` | 字段状态投影 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I05 | `09-s0-2` | outbox 注册顺序 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I06 | `09-s0-2` | cursor 重建 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I07 | `09-s0-3` | 重复/截断终态 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I08 | `09-s0-3` | Invocation 资源允许集 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I09 | `09-s0-3` | 跨会话交接 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I10 | `09-s0-3` | 真实 provider 阻塞 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I11 | `09-s1-1` | 请求预算根 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I12 | `09-s1-1` | 绑定基线 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I13 | `09-s1-1` | 格式修复上限 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I14 | `09-s1-2` | SourceAnchor 错位 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I15 | `09-s1-2` | 尾随 JSON | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I16 | `09-s1-2` | 事实支持不足 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I17 | `09-s1-3` | 输入漂移 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I18 | `09-s1-3` | 只读能力边界 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I19 | `09-s1-3` | DAG 环检测 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I20 | `09-s2-1` | plan currentness | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I21 | `09-s2-1` | head CAS 竞争 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I22 | `09-s2-2` | 半合同成员 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I23 | `09-s2-2` | 渲染字节漂移 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I24 | `09-s2-3` | 候选摘要伪造 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I25 | `09-s3-1` | 撤销审核 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I26 | `09-s3-2` | 登记幂等 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I27 | `09-s3-3` | 响应丢失恢复 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I28 | `09-s4-3` | START_UNKNOWN | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I29 | `09-s4-3` | 未知终止 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I30 | `09-s5-3` | 原生平台/外部连接器 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |

## 门禁结论

- 只有 A 项离线证据齐全且 I 项逐项有故障注入或明确阻塞记录时，阶段才可进入独立复审。
- S6 之前不得迁移生产连接器；S6 也只能输出 release gate，不能把 `NOT_RUN/BLOCKED` 改成 PASS。
- 若合同 Scope、基线或接口变化，必须出新版本合同并保留旧版本。

## 当前离线证据状态

S1–S5 的协议、来源坐标、DAG、草稿/CAS、同源渲染、候选双成员、发布幂等、三门 readiness、修复/预算、离线交接和投影游标已有定向测试，相关 A 项可标记为 LOCAL_REFERENCE。S0 的来源感知兼容、S3 的真实 03 currentness 接线和全入口生产登记仍保留 PARTIAL；I01–I30 继续 NOT_RUN/BLOCKED。该状态只表示离线实现可复核，不改变真实 provider、原生平台或生产连接器门禁。
