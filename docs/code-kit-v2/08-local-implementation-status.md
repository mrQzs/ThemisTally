# 08 离线实现状态

本记录对应 08 离线阶段在 `01–06` 门通过后完成的本地实现。它不替代 `.agent/plans/` 合同、调度器证据或独立复审；真实 Pi、provider、Windows/macOS 原生进程、09/10 外部连接器仍未接入。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| S0 | `065de9b` | 39 个合同、路线图、D08 追踪矩阵和环境边界已建立 | Pi 执行环境未就绪，未派遣 |
| S1 | `37c4d75` | 八类 artifact 公共 envelope、ResourceRef/SourceAnchor、catalog/recipes Schema 与负例校验 | 只产生本地确定性记录，未登记核心 dispatcher |
| S2 | `511e56a`, `313b54f` | AnalysisReport、ChangeReport、范围/漂移校验、静态 CheckPlan/CompileReceipt；编译仅映射既有 `execute/freeze/check/verdict` | `dispatcher_submitted=false`；无生产执行 |
| S3 | `e7a10b1`, `a175417` | docs-change、CommonMark AST 本地链接检查、危险 scheme/越界/锚点分类、固定内容 oracle 与 review bundle | 外链不访问；语义复审只支持固定 oracle |
| S4 | `4b7dcd7` | regression/mutation artifacts、skip/xfail/零测试语义、重复结果归约，不使用 best-of | 未启动真实 runner 或 mutation dispatcher |
| S5 | `4b7dcd7` | deterministic_check evidence、平台观察/失败归类、超时/取消/丢失与 reconcile 边界 | evidence 标为 `REFERENCE_ONLY`；真实平台/provider 为 `NOT_RUN/BLOCKED` |
| S6 | `4b7dcd7`, `df8f482` | catalog/readiness、七个离线插件 manifest/lock、三份配方、state/brief/outbox/cursor 去重、缺口和重建投影 | 只读投影；09/10 生产连接器未接线 |

## 证据与验证

01–06 边界与 08 聚焦测试合计 80 项通过，`python -m compileall -q scripts/codekit tests` 与 `git diff --check` 通过；14 份 Schema 在 WSL Python 3.12 的 Draft 2020-12 元校验通过。七个 plugin fixture 的 manifest/lock 和三份 recipe 可被离线 loader 校验。

`python tests/test_dispatch.py` 在 WSL Python 3.12 的本地 stub 环境完成 260 项检查、0 failed；该结果只证明调度器自测，不是 Pi 生产证据。`python -m unittest discover -s tests -q` 进入既有生命周期/调度 fixture 后耗时过长，本轮停止，不能据此宣称全量通过。39 个新增合同的 v1 文件已生成并通过规划期校验；真实执行器没有派遣。独立复审会话因本机 Codex rollout 不可用而 `BLOCKED`，没有伪造复审结论。

当前可复核状态为 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED`。这些结果只能证明离线边界和失败分类，不能转化为生产 `PASS`；下一阶段必须先获得真实执行模型、provider、原生平台和核心 dispatcher 的独立证据。
