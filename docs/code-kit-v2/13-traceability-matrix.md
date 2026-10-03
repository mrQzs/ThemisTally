# 13 可选摘要 Observer 追踪矩阵

基线：`cf44ae17fa2722cd998c5991722a0db7e373d7a8`。原 13 文档定义 A01–A09；下表将工程不变量扩展为可测试的 I01–I18。扩展项属于实施合同采用的验收设计，不改变原文授权边界。

## A 项原始验收

| A | 结果证据 | 阶段/合同 | 当前状态 |
|---|---|---|---|
| A01 | observer 关闭/缺 profile/预算不足/调用失败仍保留确定性 brief 与核心流程 | S3/S6 | PLANNED |
| A02 | facts 每条有输入内来源；hypotheses、risks、questions、actions 明确分层；缺引用拒绝或 invalid | S1/S2/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A03 | 摘要伪称 PASS、授权、规则变更不改变任务状态/确认决定 | S2/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A04 | 相同游标/输入、并发触发、自身完成事件去重，不形成循环 | S3/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A05 | 全局 request 与 observer 子预算共同计量；重试/切换不清零 | S3/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A06 | 超时、无结束事件、unknown 用量、来源冲突有可读降级 | S3/S4/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A07 | 保留实际游标；新事件到达后旧摘要不冒充最新全量 | S1/S5/S6 | OFFLINE_ACCEPTED_WITH_BOUNDARY |
| A08 | 无宿主推送时只宣称 pull；投递与阅读记录分离 | S5/S6 | PLANNED |
| A09 | 工具/输出受控；缺强隔离能力时拒绝用途；流程约束不冒称 OS 强制只读 | S2/S4/S6 | BLOCKED_REAL_CAPABILITY |

## I 项工程不变量

| I | 断言 | 证据合同 |
|---|---|---|
| I01 | ObserverRequest 必须绑定 request_id、起止游标、brief ref、来源集合和长度限制 | 13-s1-1 |
| I02 | 所有 ResourceRef 的 sha256 对应固定 UTF-8 字节；相对 path 不能越界 | 13-s1-2 |
| I03 | 输出 source_cursor/source_refs 必须落在输入闭包；缺引用不得成为有效建议 | 13-s1-3、13-s2-3 |
| I04 | facts、hypotheses、risks、open_questions、suggested_next_actions 是正交字段；建议不写回事实 | 13-s2-3 |
| I05 | 输入只读且按 allowlist 提供；observer 不能写 `.agent/runs/`、合同、规则、审核或决定 | 13-s2-1 |
| I06 | 敏感内容脱敏、数量/字节/深度受限；环境变量和巨型日志不进入上下文 | 13-s2-2 |
| I07 | 触发按阈值/阶段边界/显式请求；同一输入单飞并去重 | 13-s3-1 |
| I08 | 预算先 reserve 后 settle；未知费用保留 unknown；重试计入同一 request | 13-s3-2 |
| I09 | 超时、取消、响应丢失和 START_UNKNOWN 不重置账本，不无条件重跑 | 13-s3-3、13-s4-2 |
| I10 | 适配器只接受唯一可信完整结果；重复/截断/尾随 JSON/未知终止进入结构化失败 | 13-s4-1、13-s4-2 |
| I11 | 记录可由 source cursor 和 run_id 重建；重复重建使用新 run_id 并保留来源 | 13-s4-3、13-s5-3 |
| I12 | pull/push/read 状态分离；无 host 能力不假称通知已达 | 13-s5-1、13-s5-2 |
| I13 | 过期摘要标 stale，不能篡改游标或覆盖新事件 | 13-s5-3 |
| I14 | observer 的完成事件不能触发同一范围的新摘要循环 | 13-s3-1、13-s5-3 |
| I15 | 摘要与确定性 brief 冲突时保留事实并标记 untrusted，交主模型核对 | 13-s2-3、13-s5-1 |
| I16 | 关闭 observer 后停止新调用，历史建议可追溯，核心恢复不依赖摘要 | 13-s3-3、13-s6-3 |
| I17 | 价值评估比较固定输入和原证据，离线 fixture 不产生 token 节省或生产 PASS | 13-s6-1 |
| I18 | 真实 provider/平台/host push/外部连接器无证据即 NOT_RUN/BLOCKED，发布门保持关闭 | 13-s0-3、13-s6-2、13-s6-3 |

## 状态与证据约定

`PLANNED` 表示合同尚未执行；`PASS` 只允许在固定候选上有测试和证据；`NOT_RUN` 表示本地未运行；`BLOCKED` 表示能力或授权缺失；`STALE` 表示输入游标/来源已过期；`INVALID` 表示输出结构或引用失败。任何 observer 状态不得提升核心任务的 G0–G6、approval、budget、release 或 delivery 状态。

当前实现只覆盖严格协议、来源闭包校验和内存离线 runtime；`OFFLINE_ACCEPTED_WITH_BOUNDARY` 只表示这些边界有测试和独立复审。S5 宿主投影/通知、持久化记录与 10 outbox 接线、S6 价值评估和真实能力门仍未实现，不能作为生产发布依据。
