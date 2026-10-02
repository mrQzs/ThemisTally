# 08 离线实现状态

本记录对应 08 离线阶段在 `01–06` 门通过后完成的本地实现。它不替代 `.agent/plans/` 合同、调度器证据或独立复审；真实 Pi、provider、Windows/macOS 原生进程、09/10 外部连接器仍未接入。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| S0 | `065de9b` | 39 个合同、路线图、D08 追踪矩阵和环境边界已建立 | Pi 执行环境未就绪，未派遣 |
| S1 | `37c4d75` | 八类 artifact 公共 envelope、ResourceRef/SourceAnchor、catalog/recipes Schema 与负例校验 | 只产生本地确定性记录，未登记核心 dispatcher |
| S2 | `511e56a`, `313b54f` | AnalysisReport、ChangeReport、范围/漂移校验、静态 CheckPlan/CompileReceipt；编译仅映射既有 `execute/freeze/check/verdict` | `dispatcher_submitted=false`；无生产执行 |
| S3 | `e7a10b1`, `a175417` | docs-change、CommonMark AST 本地链接检查、危险 scheme/越界/锚点分类、固定内容 oracle 与 review bundle | 外链不访问；语义复审只支持固定 oracle |
| S4 | `4b7dcd7`, `6436a0b`, `f05fe2a`, `5a3ef84`, `c6599b0`, `be3de10`, `97a6c6f`, `ece2203` | regression/mutation artifacts、skip/xfail/零测试语义、重复结果归约、计划/summary 重算、显式 argv 离线 runner、环境白名单和凭据覆盖拒绝、超时/启动/语法/导入分类、重复运行 flaky 记录 | 未接入真实 mutation dispatcher；runner 结果仍是 `REFERENCE_ONLY` |
| S5 | `4b7dcd7`, `6436a0b`, `5a3ef84`, `87d5e91`, `97a6c6f`, `ece2203`, `a414b04` | deterministic_check evidence、receipt 身份/候选环境绑定、平台观察/失败归类、超时/取消/丢失与 reconcile 边界、持久 cursor/outbox journal、fsync 发布、截断尾恢复和恢复态写入拒绝；候选分支入口复核 `integration.local_branch` 并先核对合同哈希 | evidence 标为 `REFERENCE_ONLY`；真实平台/provider 为 `NOT_RUN/BLOCKED` |
| S6 | `4b7dcd7`, `df8f482`, `6436a0b`, `a453f94` | catalog/readiness、七个离线插件 manifest/lock、资源字节绑定、权限交集/平台阻断、三份配方、state/brief/outbox/cursor 去重、持久重建与 handoff generation fence | 只读投影；09/10 生产连接器未接线 |

## 证据与验证

01–06 边界与 08 聚焦测试合计 127 项通过；排除长生命周期调度器和 legacy 端到端模块后的其余测试共 870 项通过（跳过 34 项；Windows 缺少 `jsonschema` 的 7 项实例校验属于环境跳过）。`python -m compileall -q scripts/codekit scripts/pi_dispatch.py tests` 与 `git diff --check` 通过；WSL Python 3.12 的 Draft 2020-12 元校验和 7 个 catalog、7 个 lock、3 个 recipe 实例校验通过。新增 `993987b` 覆盖当前性 generation/hash fence、重复输入绑定拒绝及消费时间持久化回放；`be3de10` 覆盖离线 adapter 的终止与 tool 闭合边界；本批 `97a6c6f` 及其后续提交覆盖 Schema 项约束、插件/目录/锁严格校验、计划/summary 重算、receipt 身份与离线 runner mutation 边界。

`python tests/test_dispatch.py` 在 Windows 本地 stub 环境完成 258 项检查、0 failed；WSL Python 3.12 完成 263 项检查、0 failed。新增场景证明没有 `integration.local_branch` 时 branch 返回 `EXIT_BLOCKED` 且不创建分支；这些结果只证明调度器自测，不是 Pi 生产证据。`python -m unittest discover -s tests -q` 完成 1029 项，38 项跳过，3 项既有 legacy 源码字节锁定检查失败（本批有意修改 `scripts/pi_dispatch.py`，锁定的旧版 `a4fa199` 摘要因此不再匹配）；该结果不能宣称全量通过，也没有发现本批离线业务模块的新失败。39 个新增合同的 v1 文件已生成并通过规划期校验；真实执行器没有派遣。独立复审会话因本机 Codex rollout 不可用而 `BLOCKED`，没有伪造复审结论。

当前可复核状态为 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED`。这些结果只能证明离线边界和失败分类，不能转化为生产 `PASS`；下一阶段必须先获得真实执行模型、provider、原生平台和核心 dispatcher 的独立证据。
