# Code-Kit v2：10 追踪矩阵

基线：`bbe0121c15ad9ac3b78f34c1683a08f7f81f9178`。A01–A09 是附件原文验收，A10–A30 是审阅增强建议；合同编号只表示覆盖关系，不表示已通过。

## A01–A30 离线验收

| ID | 覆盖阶段 | 原始验收主题 | 当前状态 |
|---|---|---|---|
| A01 | S2 | 重复事件/来源记录不增加完成次数和累计用量 | PARTIAL |
| A02 | S3/S4 | 投影写入中断后恢复与不中断有效投影一致 | PARTIAL |
| A03 | S3 | 原始证据先落盘后补录且仅一次 | GAP |
| A04 | S1/S3 | 未完整/冲突来源保留待恢复或阻塞，不推定 PASS/集成 | PARTIAL |
| A05 | S3/S4 | 删除投影后从持久来源恢复依赖、阻塞、基线和预算 | GAP |
| A06 | S4/S5 | brief 逐条追溯事实并标明假设、未知、过期、截断 | GAP |
| A07 | S2/S5 | 相关规则变化使审核失效，无关进度不撤销审核 | GAP |
| A08 | S5/S6 | 无通知接口使用 pull，关闭 observer 后确定性功能仍可用 | PARTIAL |
| A09 | S2/S5 | 新会话区分待审、已验收、已集成、被替代 | PARTIAL |
| A10 | S1/S2 | 同 attempt 的准备/运行/验收/集成来源分别登记 | PARTIAL |
| A11 | S1/S2 | 同 SourceKey 不同 hash/位置产生持久冲突 | GAP |
| A12 | S2/S3 | 迟到旧版本不覆盖撤销，缺前驱/fork/跨范围替代阻塞 | GAP |
| A13 | S1 | 未知 schema/type、重复键、非有限数、无效 ID 先拒绝 | PARTIAL |
| A14 | S1/S3 | 缺口、错误 event_id、物理重复、无 LF 尾部分类不同 | PARTIAL |
| A15 | S3/S6 | 尾部修复维护权限、预期 hash、锁和原字节副本 | GAP |
| A16 | S1/S3 | 扫描有范围、分页、固定截止；局部不冒充完整 | GAP |
| A17 | S3/S4 | 重建新 generation 不等价旧游标，消费者 RESET | PARTIAL |
| A18 | S4 | state/brief/manifest 用一个 current 指针消费 | GAP |
| A19 | S2/S4 | 同输入规则重放字节一致，观察变化独立记录 | PARTIAL |
| A20 | S2/S3 | 最新接受/预算/审核损坏不回退旧成功 | GAP |
| A21 | S2/S5 | PASS/接受/例外接受/集成/替代独立展示 | GAP |
| A22 | S4 | 必需 brief 项放不下时明确拒绝正常简报 | GAP |
| A23 | S4 | 展示/省略、来源清单和 UTF-8 字节数可复核 | GAP |
| A24 | S4/S5 | 读取回执绑定精确 brief/manifest/游标且幂等 | GAP |
| A25 | S4/S6 | 读取/投递遥测不自激刷新，Observer 不自动成决定 | PARTIAL |
| A26 | S6 | 可见范围、转义、脱敏和外发权限在宿主接线验证 | BLOCKED |
| A27 | S2/S5 | 预算快照替换不重复相加，未知/多币种保留 | PARTIAL |
| A28 | S1/S2/S5 | request 映射不靠摘要相似度，缺字段保留 unknown | GAP |
| A29 | S6 | Windows/macOS/Linux 锁替换权限中断单独验收 | BLOCKED |
| A30 | S3/S5/S6 | 回退保留新证据和旧语义，不模型/派遣/commit/PID 清理 | PARTIAL |

`PARTIAL` 表示已有离线原语或局部实现但未满足 10 全部边界；`GAP` 表示当前缺少实现；`BLOCKED` 表示真实平台/宿主能力不可用。附录合成报告的 `PASS` provenance 是 `offline-synthetic-reference`，只能记 `LOCAL_REFERENCE`。

## F01–F30 真实故障/集成门禁

| 范围 | 状态 | 说明 |
|---|---|---|
| F01–F30 | NOT_RUN/BLOCKED | 真实 attempt/verdict/approval 来源、跨进程/断电、Windows/macOS、网络盘、宿主投递和 provider 仍未接线；离线同类注入单独标 LOCAL_REFERENCE。 |

## 记录家族与所有权

- 10 负责 ProjectEvent、SourceScanReport、SourceVerificationSnapshot、ProjectState、DecisionRecord、ProjectViewManifest、BriefReadReceipt、DeliveryReceipt、RecoveryReport 的只读登记和投影。
- 01 负责 ResourceRef/严格字节边界；03 负责 approval/currentness/input lock；07 负责 readiness/acceptance/budget/stop；09 负责 planning/publication；05 负责进程观察；10 不代办这些动作。
- `state.json`、`brief.md` 和通知都是派生或读取产物；任何动作仍回到权威模块。

## 阶段门

- S0–S5 只能在对应定向测试、Schema/compileall、diff check 和范围复审后提交。
- S6 必须逐项列出 A/F 证据、缺口和环境阻塞；任何真实能力 `NOT_RUN/BLOCKED` 都阻止生产 release gate。
