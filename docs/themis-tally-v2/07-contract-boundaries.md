# Code-Kit v2 工作流与调度接口责任边界

## 权威事实层

| 层 | 权威内容 | 允许产生的结论 | 不允许推断 |
|---|---|---|---|
| workflow | 图、阶段、端口、资源声明和版本 | 结构合法、拓扑可执行 | Git、授权、预算或 OS 已就绪 |
| readiness | 上游、合同、基线、审核和恢复事实 | READY / WAIT / BLOCK 原因 | 真实提交或 provider 调用存在 |
| baseline/git | repo identity、commit/tree/blob、祖先和 probe 结果 | 来源、当前性、覆盖证据 | 使用授权、接受或费用 |
| acceptance | 固定 candidate、check set、output port、schema、撤销链 | BOUND / BLOCK | 任何 mutable latest 或未来候选 |
| claim/ledger | request、task、attempt、resource、reservation、lease、outbox | 原子准入、幂等、fencing | PID 单独代表进程归属 |
| provider/economics | provider/account/endpoint、economic call、usage、adjustment、visibility | 已知金额、unknown 敞口、mirror 去重 | message/summary 等于完整 provider calls |
| process/runtime | host、boot、environment、worktree、PID、group/Job、launch/cleanup evidence | MATCH / MISMATCH / UNKNOWN | PID 复用后可安全接管 |
| projection | outbox cursor、09 readiness、10 brief | 可重建读模型 | 自动接受、自动收费或放宽准入 |

## 状态与证据

- UNKNOWN 是一等状态，不得当作 false、零费用或“未启动”。
- 所有外部观察先在事务外形成不可变 evidence，再在账本事务内校验 hash、版本、代际和有效期。
- HANDOFF_ACCEPTED、START_UNKNOWN、STARTED、REVIEW_PENDING、FINISHED 和财务 settlement 分开记录。
- stop、撤销和 resume 只追加事实；resume 只开放新准入，不删除旧 attempt、旧费用或旧预算。

## 路径责任

- scripts/codekit/**、schemas/**：主模型维护，保留公共接口与兼容迁移。
- tests/**、tests/fixtures/**：可由独立执行器补充；fixture 只产生离线证据。
- docs/themis-tally-v2/**：规划、追踪和验收记录。
- .agent/plans/**、.agent/reviews/**：规划端与复审端维护，Pi 不得修改。

## 生产能力门禁

能力声明拆为 identity_verified、call_visibility_complete、billing_reconciled、budget_refund_effective 四个独立布尔/未知投影。离线适配器最多证明接口和 reducer 行为；没有 03/04/05/06/09/10 的真实证据时，生产能力保持 NOT_RUN 或 BLOCKED。
