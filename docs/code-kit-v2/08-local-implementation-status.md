# 08 离线实现状态

本记录对应 08 离线阶段在 `01–06` 门通过后完成的本地实现。它不替代 `.agent/plans/` 合同、调度器证据或独立复审；真实 Pi、provider、Windows/macOS 原生进程、09/10 外部连接器仍未接入。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| S0 | `065de9b` | 39 个合同、路线图、D08 追踪矩阵和环境边界已建立 | Pi 执行环境未就绪，未派遣 |
| S1 | `37c4d75`, `3347906` | 八类 artifact 公共 envelope、ResourceRef/SourceAnchor、canonical ResourceRef 去重、catalog/recipes Schema 与负例校验 | 只产生本地确定性记录，未登记核心 dispatcher |
| S2 | `511e56a`, `313b54f`, `1fb8c6e` | AnalysisReport、ChangeReport、范围/漂移校验、source anchor 与 source_refs 闭包、静态 CheckPlan/CompileReceipt；编译仅映射既有 `execute/freeze/check/verdict` | `dispatcher_submitted=false`；无生产执行 |
| S3 | `e7a10b1`, `a175417`, `3347906`, `1371ce6` | docs-change、CommonMark AST 本地链接检查、危险 scheme/越界/锚点分类、来源引用闭包与严格 payload 校验、固定内容 oracle 与 review bundle 观察记录闭合校验 | 外链不访问；语义复审只支持固定 oracle；离线插件拒绝生产 `PASS` |
| S4 | `4b7dcd7`, `6436a0b`, `f05fe2a`, `5a3ef84`, `c6599b0`, `be3de10`, `97a6c6f`, `ece2203`, `242a2f4` | regression/mutation artifacts、skip/xfail/零测试语义、重复结果归约、计划/summary 重算与非规范 derived array 拒绝、显式 argv 离线 runner、环境白名单和凭据覆盖拒绝、超时/启动/语法/导入分类、重复运行 flaky 记录 | 未接入真实 mutation dispatcher；runner 结果仍是 `REFERENCE_ONLY` |
| S5 | `4b7dcd7`, `6436a0b`, `5a3ef84`, `87d5e91`, `97a6c6f`, `ece2203`, `a414b04`, `2bdee7d` | deterministic_check evidence、receipt 身份/候选环境绑定、平台观察/失败归类与严格输入、超时/取消/丢失与 reconcile 边界、持久 cursor/outbox journal、fsync 发布、截断尾恢复和恢复态写入拒绝；候选分支入口复核 `integration.local_branch` 并先核对合同哈希 | evidence 标为 `REFERENCE_ONLY`；真实平台/provider 为 `NOT_RUN/BLOCKED` |
| S6 | `4b7dcd7`, `df8f482`, `6436a0b`, `a453f94`, `e5f89ef` | catalog/readiness、七个离线插件 manifest/lock、资源字节绑定、权限交集/平台阻断、三份配方、state/brief/outbox/cursor 去重与严格输入、持久重建与 handoff generation fence | 只读投影；09/10 生产连接器未接线 |

## 证据与验证

01–06 边界与 08 聚焦测试合计 127 项通过；排除长生命周期调度器和 legacy 端到端模块后的其余测试共 870 项通过（跳过 34 项；Windows 缺少 `jsonschema` 的 7 项实例校验属于环境跳过）。`python -m compileall -q scripts/codekit scripts/pi_dispatch.py tests` 与 `git diff --check` 通过；WSL Python 3.12 的 Draft 2020-12 元校验和 7 个 catalog、7 个 lock、3 个 recipe 实例校验通过。新增 `993987b` 覆盖当前性 generation/hash fence、重复输入绑定拒绝及消费时间持久化回放；`be3de10` 覆盖离线 adapter 的终止与 tool 闭合边界；本批 `97a6c6f` 及其后续提交覆盖 Schema 项约束、插件/目录/锁严格校验、计划/summary 重算、receipt 身份与离线 runner mutation 边界。

`python tests/test_dispatch.py` 在 Windows 本地 stub 环境完成 258 项检查、0 failed；WSL Python 3.12 完成 263 项检查、0 failed。新增场景证明没有 `integration.local_branch` 时 branch 返回 `EXIT_BLOCKED` 且不创建分支；这些结果只证明调度器自测，不是 Pi 生产证据。`python -m unittest discover -s tests -q` 完成 1029 项，38 项跳过，3 项既有 legacy 源码字节锁定检查失败（本批有意修改 `scripts/pi_dispatch.py`，锁定的旧版 `a4fa199` 摘要因此不再匹配）；该结果不能宣称全量通过，也没有发现本批离线业务模块的新失败。39 个新增合同的 v1 文件已生成并通过规划期校验；真实执行器没有派遣。独立复审会话因本机 Codex rollout 不可用而 `BLOCKED`，没有伪造复审结论。

本批 `3347906` 的文档与 artifact 定向回归共 93 项通过；覆盖 source_refs 与文档源路径一一闭包、重复路径拒绝、payload 状态重算、跨平台路径规范化去重，以及 docs-check/docs-change/review-bundle 的生产 `PASS` 门禁。该批仍只验证离线构造器与输入边界，未产生 dispatcher receipt 或真实连接器证据。

后续 `1fb8c6e` 将 AnalysisReport 的 SourceAnchor 以及 docs-change 的 anchor 引用限制在已声明的 `source_refs` 闭包内，并以 100 项跨插件定向回归复核。该校验仍不等价于读取真实文件字节或生产审查结论。

`1371ce6` 进一步固定 review oracle 的 observation、binding、check/test ID 与结果状态的闭合结构和数量上限；malformed/unhashable 输入均归类为明确的 `E_CHECK_*`，没有把异常输入当作 readiness。`739cc91` 补齐 list/set 类型负例，避免集合参数回归到宽松接受。

`242a2f4` 补齐 regression plan 的 derived array 规范性校验，重复、乱序或非文本目标现在在归约前失败；30 项 regression/mutation 边界回归通过。

`2bdee7d` 约束平台观察、失败分类与 deterministic-check evidence 的布尔值、摘要、receipt 和输入闭包；S4/S5 定向回归现为 31 项通过，仍不生成真实 dispatcher receipt。

`e5f89ef` 约束内存投影的事件 payload、canonical JSON、source cursor、state/brief 字段和问题列表类型；S6 投影定向回归现为 17 项通过，仍只属于只读离线投影。

当前可复核状态为 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED`。这些结果只能证明离线边界和失败分类，不能转化为生产 `PASS`；下一阶段必须先获得真实执行模型、provider、原生平台和核心 dispatcher 的独立证据。
