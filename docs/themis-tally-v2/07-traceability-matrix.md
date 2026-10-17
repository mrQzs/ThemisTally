# Code-Kit v2 工作流与调度追踪矩阵

基线提交：175653ebbe3059c012166dacfbf13b7eac67b41f  
定向基线：195 项 unittest 通过；调度器回归：255 checks 通过。  
状态含义：LOCAL_PARTIAL 表示纯模型或 SQLite 原型已有可复核证据；NOT_RUN 表示真实接线、平台或 provider 证据尚未运行；PASS 只允许在 S6 独立复审后使用。

## A 需求

| 编号 | 验收要求摘要 | 当前证据 | 状态 | 后续子任务 |
|---|---|---|---|---|
| A01 | 图、悬空边、重复节点、类型和缺字段在派遣前拒绝 | tests/test_workflow.py | LOCAL_PARTIAL | S0.2, S5.3 |
| A02 | 人工合同可离线顺序调度，检查读取固定候选且不启动规划 CLI | workflow 静态测试 | LOCAL_PARTIAL | S2.3, S5.1 |
| A03 | 上游未接受、缺提交、无基线授权或审核过期时等待并给理由 | readiness/coverage/git probe | LOCAL_PARTIAL | S1.1, S1.2 |
| A04 | 重叠写范围串行，接口依赖不误并行 | parallel.py 路径/键模型 | LOCAL_PARTIAL | S1.3, S2.3 |
| A05 | 重复请求只领取一次，重启不因内存丢失重复启动 | claim/store/atomic 测试 | LOCAL_PARTIAL | S2.1, S4.2 |
| A06 | attempt 退出 0 但未验收时下游不启动 | acceptance/atomic 原型 | LOCAL_PARTIAL | S1.2, S5.1 |
| A07 | 同 request 跨角色、CLI、版本和重试累计消耗 | budget/retry 测试 | LOCAL_PARTIAL | S3.1, S3.2 |
| A08 | 并行预留不超卖，unknown 不按零处理，重试有上限 | budget/parallel/atomic 测试 | LOCAL_PARTIAL | S2.3, S3.2 |
| A09 | rebase/merge 后重新检查候选，旧 PASS 不复用 | acceptance/coverage | LOCAL_PARTIAL | S1.1, S1.2 |
| A10 | stop/resume 保留 attempt 历史，不自动提交或改写基线 | recovery/retry/atomic 原型 | LOCAL_PARTIAL | S4.3, S5.1 |
| A11 | 图和阶段命名空间独立，重排不改变依赖语义 | workflow 拓扑测试 | LOCAL_PARTIAL | S2.3 |
| A12 | Schema 精确校验和映射证明分离，不执行任意映射 | workflow/schema 测试 | LOCAL_PARTIAL | S0.2, S5.3 |
| A13 | 固定输入绑定回查接受版本、候选、输出端口和目标 Schema | acceptance.py | LOCAL_PARTIAL | S1.2 |
| A14 | commit、祖先、内容覆盖和使用授权分别验证，多上游不静默合流 | git probe/coverage | LOCAL_PARTIAL | S1.1, S1.2 |
| A15 | 活动 task 唯一性跨 plan_version 生效 | scheduler/parallel 原型 | LOCAL_PARTIAL | S2.1, S2.3 |
| A16 | 领取、资源、预算和 outbox 原子提交 | atomic ledger 原型 | LOCAL_PARTIAL | S2.1, S2.2 |
| A17 | 同键重放不新启动，内容冲突报错，旧操作不复活 | atomic idempotency 测试 | LOCAL_PARTIAL | S2.2, S4.2 |
| A18 | handoff 重新核验 guard、stop、generation 和额度 | scheduler/atomic 原型 | LOCAL_PARTIAL | S2.2, S4.2 |
| A19 | START_UNKNOWN/过期租约保留风险占用，不直接视为未启动 | atomic recovery 原型 | LOCAL_PARTIAL | S4.1, S4.2 |
| A20 | 同 repo 的模块、接口、文件和共享环境占用可见 | path/key 并行模型 | LOCAL_PARTIAL | S1.3, S2.3 |
| A21 | cumulative、mirror、final、correction、乱序修订分别处理 | budget reducer | LOCAL_PARTIAL | S3.1, S3.2 |
| A22 | 超预算实际费用入账并 stop，不双计已知和预留 | budget/atomic 测试 | LOCAL_PARTIAL | S2.1, S3.2 |
| A23 | unknown 结束调用保留敞口，缺 provider 可见性不宣称完整 | budget unknown 原型 | LOCAL_PARTIAL | S3.1 |
| A24 | 精度、溢出、币种和退款规则明确，不使用无来源汇率 | budget 整数/币种测试 | LOCAL_PARTIAL | S3.2, S3.3 |
| A25 | stop 禁止新业务调用但可封存迟到计量，resume 不清历史 | atomic/recovery 原型 | LOCAL_PARTIAL | S4.3, S5.2 |
| A26 | 接受只针对固定候选/检查集，撤销追加失效关系 | acceptance revocation | LOCAL_PARTIAL | S1.2, S5.1 |
| A27 | 重启使用受信代际并核对 boot/进程/账本，旧 owner 被 fencing | rollover/fencing 原型 | LOCAL_PARTIAL | S4.1, S4.3 |
| A28 | 09 细化无循环依赖，规划调用有独立授权和预算归属 | 当前无 09 接线 | NOT_RUN | S5.1, S5.3 |
| A29 | 10 投影可由权威事实重建，游标重复/丢失不重复收费或接受 | outbox 仅 append-only | NOT_RUN | S5.1, S5.2 |
| A30 | 数据库、资源和授权高水位不一致时隔离新派遣 | recovery 纯门禁 | LOCAL_PARTIAL | S4.3, S5.2 |

## F 故障要求

| 编号 | 注入与预期 | 当前状态 | 归属 |
|---|---|---|---|
| F01 | 合同/工作流引用哈希不一致，prepare/run 拒绝 | NOT_RUN | S1.1, S5.3 |
| F02 | 可细化但无执行合同，只允许起草不执行 | NOT_RUN | S5.1 |
| F03 | 上游退出 0 但无接受，下游等待 | NOT_RUN | S1.2, S5.1 |
| F04 | 单任务候选未 PASS，同一固定候选可检查且无自等待 | NOT_RUN | S1.2, S5.3 |
| F05 | 未提交补丁无提交许可，等待且不创建 commit | NOT_RUN | S1.1 |
| F06 | 后代基线关键 blob 修改，coverage 失败或重验收 | NOT_RUN | S1.1 |
| F07 | A/B 合流后生成新 candidate，旧 PASS 不复用 | NOT_RUN | S1.1, S1.2 |
| F08 | 同 task 两个 plan 轮询，最多一个活动 attempt | NOT_RUN | S2.2 |
| F09 | 同键双进程且响应丢失，恢复不重启 | NOT_RUN | S2.1, S2.2, S4.2 |
| F10 | claim 中资源占用后故障，不留下部分事实 | NOT_RUN | S2.1, S2.2 |
| F11 | reserve 后 handoff 前撤销，拒绝且不启动 OS | NOT_RUN | S1.2, S2.2 |
| F12 | handoff 已提交但 STARTED 丢失，进入 START_UNKNOWN | NOT_RUN | S4.1, S4.2 |
| F13 | owner 过期但子进程仍活，保留占用不重派 | NOT_RUN | S4.1, S4.2 |
| F14 | 旧 controller 接管后写入被 fencing 拒绝 | NOT_RUN | S4.1, S4.3 |
| F15 | PID 复用或 boot 变化，不杀错进程 | NOT_RUN | S4.1, S4.3 |
| F16 | 不同文件但同模块/接口，串行或要求独立性证明 | NOT_RUN | S1.3, S2.3 |
| F17 | 不同 request 共享端口/产物，正确冲突 | NOT_RUN | S1.3, S2.3 |
| F18 | Windows 别名/junction 与 macOS 路径差异被锁定 | NOT_RUN | S1.3, S4.1 |
| F19 | 并行各申请超过一半余额，不得超卖 | NOT_RUN | S2.1, S3.3 |
| F20 | 单 run 隐藏多 provider 调用，coverage 如实且能力阻塞 | NOT_RUN | S3.1, S5.3 |
| F21 | message/summary/brief 重复费用只计一次 | NOT_RUN | S3.1, S5.2 |
| F22 | provider final 更正乱序，保留旧事实且不相加 | NOT_RUN | S3.2 |
| F23 | 结束/取消后费用缺失，保留 unknown 敞口 | NOT_RUN | S3.1, S3.2 |
| F24 | 晚到费用超过 cap，照实入账并 stop | NOT_RUN | S3.2, S5.2 |
| F25 | 多币种/未知币种隔离，不默认 USD 或 FX | NOT_RUN | S3.2 |
| F26 | stop 与新 handoff 竞争，后提交者受 stop 约束 | NOT_RUN | S2.2, S4.2 |
| F27 | stop 后日志/账单迟到，可封存记账但不重启 | NOT_RUN | S3.2, S4.3, S5.2 |
| F28 | 接受撤销后继已排队/运行，待运行阻塞并留证 | NOT_RUN | S1.2, S5.1, S5.3 |
| F29 | outbox 重复投递或 cursor 丢失，不重复收费/接受 | NOT_RUN | S2.1, S5.2 |
| F30 | 旧备份缺新撤销，进入 RECOVERING 隔离 | NOT_RUN | S4.3, S5.2 |

## 证据规则

- LOCAL_PARTIAL 只说明当前局部实现可复核，不代表真实 provider、OS、跨平台或 03–10 接线已通过。
- NOT_RUN 不得通过重新描述 fixture、日志或模型自述改成 PASS。
- S6 每个条目必须绑定候选 commit、命令、输入摘要、输出摘要和原始证据路径。
