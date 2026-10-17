# Code-Kit v2：09 CLI 规划与合同发布执行路线图

## 基线与边界

本路线以完整提交 `330d3716d65e068c38a5861e2a1a4bf4c84cf043` 为唯一起点。09 的离线闭环目标是：

`PlannerRequest → PlanningBundle → draft revision → ContractCandidate → review binding → PublicationReceipt → validate/prepare/baseline/run 消费门禁`。

当前仓库已具备 03 的 approval/input-lock、04 的 adapter 事件、05 的 invocation/process observation、07 的统一账本、08 的离线 catalog/recipe 和 10 的投影基础，但没有独立 `planner.py`、PlanningBundle schema、草稿存储或发布账本。旧入口仍可能直接读取 `.agent/plans/<task>.md/.json`，因此实现必须同时改造所有消费入口；不得只增加 planner 端点。

本路线只授权离线可复核实现。真实 planner/provider、Pi、Windows/macOS 原生进程、外部 09/10 连接器与生产迁移均记录为 `NOT_RUN` 或 `BLOCKED`，离线 fixture 不构成生产 PASS。

## 阶段门与交付

| 阶段 | 子任务 | 主要交付 | 阶段门 |
|---|---|---|---|
| S0 规范、基线与追踪 | `09-s0-1` 路由与 v1 兼容；`09-s0-2` 接口/字段所有权/追踪矩阵；`09-s0-3` fixture、错误注入和环境门禁 | 本路线图、追踪矩阵、合同模板、证据边界 | 三份合同均通过 schema/文档自检，真实能力仍 NOT_RUN/BLOCKED |
| S1 严格规划协议 | `09-s1-1` PlannerRequest/ContextManifest/PlanningBundle；`09-s1-2` ResourceRef/SourceAnchor/事实谱系；`09-s1-3` DAG、类型、scope/check 校验 | 严格 JSON、上下文绑定和不可伪造的未绑定草稿 | 负例拒绝、深度/大小/任务数上限和事实等级证据完整 |
| S2 草稿、版本与候选 | `09-s2-1` draft revision/head CAS；`09-s2-2` ContractIR 同源渲染；`09-s2-3` ContractCandidate 双成员绑定 | 不可变草稿、单调版本槽、固定字节 MD/JSON | 同源字节相等、CAS 竞争和半成员拒绝 |
| S3 审核、发布与入口门禁 | `09-s3-1` approval/currentness；`09-s3-2` PublicationReceipt/登记事务；`09-s3-3` 全入口固定字节 loader | 登记先于投影，旧入口显式兼容登记 | 撤销、输入漂移、缺登记、响应丢失全部拒绝 |
| S4 两级细化、修复与预算 | `09-s4-1` 三个 readiness 判断；`09-s4-2` 有限格式修复；`09-s4-3` request 计量/STOP/START_UNKNOWN | 图→模板→完整草稿、单一预算账本和可恢复停止 | 修复与设计裁决分离，未知启动不盲重试 |
| S5 离线适配与交接 | `09-s5-1` 唯一可信结果提取；`09-s5-2` 04/05 只读接线；`09-s5-3` 独立规划/执行 stub | 可录制、可重放、跨会话的离线 planner 适配 | 重复终态歧义、截断、响应丢失和真实能力阻塞均有证据 |
| S6 兼容、投影、规则迁移与验收 | `09-s6-1` 来源感知 v1；`09-s6-2` 正交状态/10 outbox/cursor/规则迁移；`09-s6-3` 独立矩阵验收 | 09-A01–A28、I01–I30 报告、恢复操作册、release gate | 历史合同不退化，生产门禁仍闭合直到真实能力放行 |

S1 依赖 S0；S2 依赖 S1；S3 依赖 S2 和 03；S4 依赖 S1/S2/07；S5 依赖 S3/S4 及 04/05；S6 依赖全部前置。每个阶段内部先冻结接口，再并行实现 fixture/测试，最后独立复审和阶段提交。

## 公共记录和操作

新增记录：`PlannerRequest`、`ContextManifest`、`PlanningBundle`、`BundleValidationReport`、`ContractCandidate`、`PublicationReceipt`、`PlanningRevisionEvent`。新增核心操作：`request_planning`、`ingest_planning_result`、`allocate_contract_candidate`、`submit_plan_review`、`publish_contract`、`get_publication`、`recover_publication`。

`ContractCandidate` 恰好包含 MD/JSON 两个成员，分别绑定来源和目标 `ResourceRef`；审核后的合同字节不得回填 `approval_id` 或 `publication_id`。planner 不分配持久身份、路径、版本，不写 `.agent/plans/`/`.agent/runs/`，不执行草稿命令，不登记 approval。`unbound` 草稿不得携带假 SHA。

发布顺序固定为“登记成功 → 精确字节投影”。所有 `validate`、`derive-json`、`prepare`、`baseline`、`run` 消费入口必须通过固定字节 loader，并要求登记、完整双格式、当前审核和输入闭包；半文件、撤销审核、旧 candidate、输入 A→B→A 漂移、响应丢失均拒绝。版本槽单调分配、不复用，旧记录不可变；幂等由 request/event key 和 head CAS 保证。

## 文件所有权与执行约束

`schemas/**`、`scripts/codekit/**`、`scripts/pi_dispatch.py` 和调度器边界由主规划模型直接维护；Pi 仅接收合同明确的外围测试、fixture、文档和适配层范围。任何合同都禁止修改 `AGENTS.md`、代理规则、`.agent/` 原始证据、权限/CI 和依赖。真实调用仍需另行环境核验与授权。

## 验证与证据

每个合同至少运行：

```text
python -B -m unittest tests.test_dispatch -q
python -B -m compileall -q scripts/codekit tests
git diff --check
```

实现阶段另加合同列出的定向 fixture/Schema 检查；证据写入 `.agent/runs/`（原始文件不可编辑），复审写入 `.agent/reviews/`。A01–A28 必须各有实现/测试/证据，I01–I30 必须有离线故障注入或明确 `NOT_RUN/BLOCKED` 记录。全量历史测试中的 legacy source-lock 失败和环境 skip 单独归类，不宣称生产 PASS。

## 提交顺序

每阶段通过定向测试和独立复审后，仅暂存该阶段 Scope 内文件，创建阶段提交并推送；后续阶段以新的完整 SHA 为基线。当前 21 份合同均先固定在上述基线，执行前若基线变化必须重新生成版本，不得隐式漂移。

## 当实现记录

当前实现按阶段保留真实边界：

- S0：路线图、追踪矩阵和 21 份合同已提交；合同基线仍是 `330d3716d65e068c38a5861e2a1a4bf4c84cf043`，后续核心修补以新的提交继续推进。
- S1：PlannerRequest/ContextManifest/PlanningBundle 的严格解码、ResourceRef/SourceAnchor 字节核验、任务图闭环、上下文条目与合同草稿绑定已补齐离线负例。插件锁和完整 06/08 catalog 语义仍是 PARTIAL。
- S2：DraftStore CAS/单调版本槽、ContractIR 同源 MD/JSON、双成员候选、重复输入/同源目标拒绝已实现；跨 request 的持久 task owner 仍是 PARTIAL。
- S3：ApprovalLedger 的 `publish_contract` 动作、时间窗、input lock 和 generation 检查，发布 ID 冲突拒绝、持久 outbox、固定字节门禁和跨进程精确 pair 恢复已实现。外部独立 ledger 重查仍不能由离线 dispatcher 自己伪造为 PASS。
- S4：三个 readiness 判断和面向 07 `BudgetState` 的 `PlanningBudgetLedger` 适配已实现；旧 `RequestBudget` 兼容层、复杂修复语义和真实 START_UNKNOWN 仍为 PARTIAL/BLOCKED。
- S5：离线结果唯一性、响应丢失/截断拒绝和 planner adapter 已有；真实 planner/provider/Pi 与原生进程仍 `NOT_RUN/BLOCKED`。
- S6：`PUBLISHED` 正交投影和 validate/prepare/baseline/run/check/collect/mutate/branch 的 planner-v2 固定字节发布门已接线；10 的真实 outbox/cursor 外部连接器和生产发布仍未接入。

本轮可复核提交为 `c13560e`、`45ce853`；测试证据和剩余缺口见 `docs/themis-tally-v2/09-implementation-status.md`。任何离线 PASS 都不等于真实 planner/provider、Pi、原生平台或外部连接器生产放行。
