# 08 离线实现状态

本记录对应 08 离线阶段在 `01–06` 离线参考门建立后完成的本地实现。01–06 正式阶段门仍为 `REVISE/BLOCKED`，本记录不把离线参考结果提升为阶段通过。它不替代 `.agent/plans/` 合同、调度器证据或独立复审；真实 Pi、provider、Windows/macOS 原生进程、09/10 外部连接器仍未接入。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| S0 | `065de9b` | 39 个合同、路线图、D08 追踪矩阵和环境边界已建立 | Pi 执行环境未就绪，未派遣 |
| S1 | `37c4d75`, `3347906` | 八类 artifact 公共 envelope、ResourceRef/SourceAnchor、canonical ResourceRef 去重、catalog/recipes Schema 与负例校验 | 只产生本地确定性记录，未登记核心 dispatcher |
| S2 | `511e56a`, `313b54f`, `1fb8c6e` | AnalysisReport、ChangeReport、范围/漂移校验、source anchor 与 source_refs 闭包、静态 CheckPlan/CompileReceipt；编译仅映射既有 `execute/freeze/check/verdict` | `dispatcher_submitted=false`；无生产执行 |
| S3 | `e7a10b1`, `a175417`, `3347906`, `1371ce6` | docs-change、CommonMark AST 本地链接检查、危险 scheme/越界/锚点分类、来源引用闭包与严格 payload 校验、固定内容 oracle 与 review bundle 观察记录闭合校验 | 外链不访问；语义复审只支持固定 oracle；离线插件拒绝生产 `PASS` |
| S4 | `4b7dcd7`, `6436a0b`, `f05fe2a`, `5a3ef84`, `c6599b0`, `be3de10`, `97a6c6f`, `ece2203`, `242a2f4`, `b396873` | regression/mutation artifacts、skip/xfail/零测试语义、重复结果归约、计划/summary 重算与非规范 derived array/输入拒绝、显式 argv 离线 runner、环境白名单和凭据覆盖拒绝、超时/启动/语法/导入分类、重复运行 flaky 记录 | 未接入真实 mutation dispatcher；runner 结果仍是 `REFERENCE_ONLY` |
| S5 | `4b7dcd7`, `6436a0b`, `5a3ef84`, `87d5e91`, `97a6c6f`, `ece2203`, `a414b04`, `2bdee7d`, `29ade8d` | deterministic_check evidence、receipt 身份/候选环境绑定与闭集、平台观察/失败归类与严格输入、超时/取消/丢失与 reconcile 边界、持久 cursor/outbox journal、fsync 发布、截断尾恢复和恢复态写入拒绝；候选分支入口复核 `integration.local_branch` 并先核对合同哈希 | evidence 标为 `REFERENCE_ONLY`；真实平台/provider 为 `NOT_RUN/BLOCKED` |
| S6 | `4b7dcd7`, `df8f482`, `6436a0b`, `a453f94`, `e5f89ef`, `f060b94`, `811ab7a`, `b2b9dff` | catalog/readiness、七个离线插件 manifest/lock、资源字节绑定、权限交集/平台阻断、插件 lock/权限输入规范化、recipe receipt 身份闭包、三份配方、state/brief/outbox/cursor 去重与严格输入、持久重建与 handoff generation fence | 只读投影；09/10 生产连接器未接线 |

## 证据与验证

01–06 边界与 08 聚焦测试合计 127 项通过；排除长生命周期调度器和 legacy 端到端模块后的其余测试共 870 项通过（跳过 34 项；Windows 缺少 `jsonschema` 的 7 项实例校验属于环境跳过）。`python -m compileall -q scripts/codekit scripts/pi_dispatch.py tests` 与 `git diff --check` 通过；WSL Python 3.12 的 Draft 2020-12 元校验和 7 个 catalog、7 个 lock、3 个 recipe 实例校验通过。新增 `993987b` 覆盖当前性 generation/hash fence、重复输入绑定拒绝及消费时间持久化回放；`be3de10` 覆盖离线 adapter 的终止与 tool 闭合边界；本批 `97a6c6f` 及其后续提交覆盖 Schema 项约束、插件/目录/锁严格校验、计划/summary 重算、receipt 身份与离线 runner mutation 边界。

`python tests/test_dispatch.py` 在 Windows 本地 stub 环境完成 258 项检查、0 failed；WSL Python 3.12 完成 263 项检查、0 failed。新增场景证明没有 `integration.local_branch` 时 branch 返回 `EXIT_BLOCKED` 且不创建分支；这些结果只证明调度器自测，不是 Pi 生产证据。`python -m unittest discover -s tests -q` 完成 1029 项，38 项跳过，3 项既有 legacy 源码字节锁定检查失败（本批有意修改 `scripts/pi_dispatch.py`，锁定的旧版 `a4fa199` 摘要因此不再匹配）；该结果不能宣称全量通过，也没有发现本批离线业务模块的新失败。39 个 v1 合同是旧基线上的规划草稿，不能作为当前派遣或阶段验收证据；真实执行器没有派遣。独立复审会话因本机 Codex rollout 不可用而 `BLOCKED`，没有伪造复审结论。

本批 `3347906` 的文档与 artifact 定向回归共 93 项通过；覆盖 source_refs 与文档源路径一一闭包、重复路径拒绝、payload 状态重算、跨平台路径规范化去重，以及 docs-check/docs-change/review-bundle 的生产 `PASS` 门禁。该批仍只验证离线构造器与输入边界，未产生 dispatcher receipt 或真实连接器证据。

后续 `1fb8c6e` 将 AnalysisReport 的 SourceAnchor 以及 docs-change 的 anchor 引用限制在已声明的 `source_refs` 闭包内，并以 100 项跨插件定向回归复核。该校验仍不等价于读取真实文件字节或生产审查结论。

`1371ce6` 进一步固定 review oracle 的 observation、binding、check/test ID 与结果状态的闭合结构和数量上限；malformed/unhashable 输入均归类为明确的 `E_CHECK_*`，没有把异常输入当作 readiness。`739cc91` 补齐 list/set 类型负例，避免集合参数回归到宽松接受。

`242a2f4` 补齐 regression plan 的 derived array 规范性校验，重复、乱序或非文本目标现在在归约前失败；30 项 regression/mutation 边界回归通过。

`2bdee7d` 约束平台观察、失败分类与 deterministic-check evidence 的布尔值、摘要、receipt 和输入闭包；S4/S5 定向回归现为 31 项通过，仍不生成真实 dispatcher receipt。

`e5f89ef` 约束内存投影的事件 payload、canonical JSON、source cursor、state/brief 字段和问题列表类型；S6 投影定向回归现为 17 项通过，仍只属于只读离线投影。

`f060b94` 要求插件 lock 的 plugin/resource 行保持 canonical 顺序，并拒绝重复授权权限或非文本平台输入；插件边界与 manifest/lock 样例共 23 项通过（Windows 缺少 `jsonschema` 的结构实例仍按环境跳过）。

`29ade8d` 要求 deterministic-check artifact 的 evidence 字段闭集、身份字段非空且类型明确，并限制 output/reason 的大小；S5 定向回归现为 17 项通过，仍没有可信 dispatcher receipt。

`811ab7a` 收紧持久 projection 的 cursor、source vector、verification/as-of、issues 与布尔字段，S6 投影回归继续保持通过；该实现仍是只读离线投影，不代表 09/10 生产接线。

`b2b9dff` 收紧 catalog 输入、recipe compile receipt 身份与版本、以及 projection 事件序列边界；相关 S4/S5/S6 回归 37 项通过。它们仍是主模型维护的离线实现，未形成 Pi attempt 证据。

`b396873` 进一步拒绝 regression inventory、plan、summary 和 result 中的错误类型或非序列输入；S4 regression/mutation 边界仍保持通过。

当前可复核状态为 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED`。这些结果只能证明离线边界和失败分类，不能转化为生产 `PASS`；下一阶段必须先获得真实执行模型、provider、原生平台和核心 dispatcher 的独立证据。

最新候选 `1caeb6e` 增加了 regression/mutation artifact 加载重算、candidate path 绑定、未知 connector 阶段阻断、offline runner 完整输出稳定性，以及持久 budget/scheduler ledger 对 NaN/Infinity 的拒绝。相关复合定向套件与 01–06 恢复/账本套件合计 279 项通过；完整调度器回归仍 `NOT_RUN`，真实生产接线仍 `BLOCKED`。

当前候选已推进到 `e94056a`：插件清单 canonical JSON、数组/深度/控制字符限制和身份哈希循环/Unicode 边界已补齐；这些仍是离线结构证据，未改变真实 Pi/provider/平台/09/10 的阻塞状态。

当前候选推进到 `98a4ed5`：adapter、runtime lease、provider economics 与 unified ledger 的输入和指纹边界继续收紧；相关组合回归 137 项通过，验收矩阵组合命令 303 项通过、1 项跳过。该候选仍只提供 `LOCAL_REFERENCE`，没有可信 dispatcher receipt、真实 provider、原生平台或 09/10 生产连接器证据。

候选随后推进到 `9980f27`：授权 journal 与 scheduler SQLite 的协议文本边界拒绝 C0/C1、DEL 和孤立代理字符，并覆盖写入、重放、输入和重开路径；验收矩阵组合命令现为 305 项通过、1 项跳过。该候选仍只提供 `LOCAL_REFERENCE`，没有可信 dispatcher receipt、真实 provider、原生平台或 09/10 生产连接器证据。

候选随后推进到 `137dae4`：provider economics、unified ledger 和 usage settlement 的 canonical 指纹拒绝不安全整数、数值子类、循环、代理、非有限数和未知对象；验收矩阵组合命令现为 311 项通过、1 项跳过。该候选仍只提供 `LOCAL_REFERENCE`，没有可信 dispatcher receipt、真实 provider、原生平台或 09/10 生产连接器证据。

候选随后推进到 `1e1363a`：三套 canonical helper 对代理对象键统一返回结构化拒绝，验收矩阵计数不变；仍没有可信 dispatcher receipt、真实 provider、原生平台或 09/10 生产连接器证据。

合同基线已更新：`aa82aaf` 新增 39 对当前合同 `v2`（01–06 各 3 个、08 的 S0–S6 各 3 个），统一绑定前一提交 `9a75389`，并补齐 Inputs/Outputs、Failure handling、Rollback boundary 以及全局验证命令。39 份合同均通过 `python scripts/pi_dispatch.py validate <task>.v2`；这只是合同结构校验，没有生成 Pi attempt 或阶段验收证据。旧版 39 对 `v1` 仍是历史草稿，`07-roadmap.v1.md` 仍无配套 JSON，均不可直接派遣。

代码基线随后推进到 `7a29008`，39 对 v2 合同已重新绑定该提交；插件目录/配方边界与统一账本 v3 重开校验的定向回归仍属于 `LOCAL_REFERENCE`。合同校验不产生执行器或生产接线证据。

当前代码基线推进到 `b3f40aa`：运行时、适配器和 provider 观察边界完成离线收紧；39 对 v2 合同已绑定该基线并通过结构校验。新增结果仍是 `LOCAL_REFERENCE`，没有 Pi attempt、真实 provider、原生平台或 09/10 连接器证据。

当前离线代码基线推进到 `86a92fc`，39 对 v2 合同已重新绑定并通过校验；新增配置与 Git 来源边界仍只证明本地输入防护，不改变真实 provider、Pi、原生平台和 09/10 连接器的 `NOT_RUN/BLOCKED` 状态。

当前离线候选推进到 `86a92fc`：授权账本、scheduler hold、projection journal 和 acceptance binding 完成边界收紧；结果仍是 `LOCAL_REFERENCE`，不能代替真实 dispatcher、provider、原生平台或 09/10 连接器验收。


当前候选 `cf3a1cd` 补齐投影事件 canonical JSON、严格重建输入、截断尾 repair CAS、09/10 健康/来源向量一致性，以及运行时进程身份和恢复租约边界。相关定向套件 62 项通过，统一验收命令 348 项通过、1 项跳过；没有 dispatcher receipt、Pi attempt、真实 provider、原生平台或 09/10 生产连接器证据。


最新环境复核已确认 `bb/step-5-preview` 可用且认证 ready；本轮仍未运行 smoke、Pi、provider 或外部连接器，S5/S6 生产证据继续为 `NOT_RUN/BLOCKED`。


当前候选 `a64f3a8` 收紧八类业务 artifact、插件 manifest/lock、ResourceRef 路径摘要和离线 recipe 命令边界，并补齐 outbox 连续性与请求/操作闭包校验。新增组合验收结果为 398 项通过、8 项环境跳过；没有 Pi attempt、provider call、原生平台或 09/10 外部连接器证据。

Git Bash Python 3.12.3 对同一组合套件复核为 398 项通过、1 项跳过，schema 实例 7 项全部通过；这仍不生成 Pi/provider/连接器证据。


最新离线候选 `dda848ddfadd28bb06ac8c5b603623f06a54c767` 同步刷新 39 对 v2 合同基线，并记录 adapter/config/identity/authorization 严格边界回归；105 项定向边界测试和 398 项组合套件通过（Windows 8 项环境跳过）。这仍是 `LOCAL_REFERENCE`，不产生 Pi/provider、原生平台或 09/10 连接器证据。


最新离线候选 `24760ceec4c3350327a0cf194c58a48a9d9cabf2` 重绑定 39 对 v2 合同，并加固统一账本、结算、builtin projection、持久 journal 和 runtime generation fence；扩展组合套件 474 项通过、8 项环境跳过。仍为 `LOCAL_REFERENCE`，没有 Pi/provider、原生平台或 09/10 连接器证据。


最新离线候选 `ef5ff25e9f41cea1096f75d31b027ef4dafcb66b` 继续收紧旧 projections readiness/outbox 投影的文本、游标、代际与 event_id 边界；扩展组合套件 478 项通过、8 项环境跳过。仍为 `LOCAL_REFERENCE`，没有 Pi/provider、原生平台或 09/10 连接器证据。


## 2026-10-03 当前离线候选（5d141298）

`5d141298d052b291c1dba3fe35075d6303f0bbc8` 补齐 analysis/docs-change 的冻结 SourceAnchor 字节接线，并将 authorization store 的锁回执探针切换到 strict JSON。新增组合验收为 552 项收集、544 项通过、8 项环境跳过；插件全集为 107 项收集、100 项通过、7 项环境跳过。39 对最新合同已绑定该候选并通过结构校验。结果仍为 `LOCAL_REFERENCE`，没有 Pi/provider、原生平台或 09/10 连接器证据。

## 2026-10-03 Full Discover Timeout Update

Candidate \`5d141298d052b291c1dba3fe35075d6303f0bbc8\` remains the last implementation candidate; publication commit is \`99bda89b9f61754b7bbdc206f4a1ed97425e16a5\`. The fresh capture \`.agent/runs/offline-01-06-08-20261003-full-discover-09/\` attempted \`python -B -m unittest discover -s tests -q\` under the supervisor for 900.031 seconds. It timed out with \`returncode=null\`, \`timed_out=true\`, \`termination_confirmed=true\`, \`stray_processes=false\`, empty stdout/stderr, and no baseline drift. \`execution_status=complete\` only means the capture itself is complete; the test result is \`TIMEOUT/BLOCKED\`, not PASS. The 01–06 and 08 stage gates therefore remain \`REVISE/BLOCKED\`, with real Pi/provider/native platform/09/10 connector evidence still \`NOT_RUN/BLOCKED\`.

## 2026-10-03 当前 08 离线候选与新合同

08 离线代码候选为 `eae9bfca4cf7351b02b7b5eafd6f101664b418ee`，39 对 01–06/08 合同的新版本随 `db46200d75ff1462837996bab7450e09a9a88f46` 发布；合同执行器记录统一为 `bb/step-5-preview`，未派遣真实 Pi。插件全集 capture `.agent/runs/offline-01-06-08-20261003-builtin-contracts-eae9bfc/` 为 117/109/8（收集/通过/跳过），扩展 capture `.agent/runs/offline-01-06-08-20261003-expanded-contracts-eae9bfc/` 为 1040 收集、1 个既有 `scripts/pi_dispatch.py` source-lock 失败、35 个环境跳过，返回码 1；两者均无 drift。

本轮离线边界修复覆盖 source snapshot portable collision、fixed content oracle closed shape、candidate/environment binding、zero cursor reopen、attempt plan version、rejected handoff 和 CommonMark first-definition 语义。定向回归 114 项通过、1 项跳过；这些结果仍为 `LOCAL_REFERENCE`，不能授予批准、运行、计费或发布权限。真实 provider、Pi、Windows/macOS 原生进程、核心 dispatcher 和 09/10 连接器保持 `NOT_RUN/BLOCKED`，S6 独立验收与生产门禁继续关闭。

## 2026-10-03 当前修复候选（08-S2/S3 报告边界）

代码候选已推进到 `a1e15c157734af1ec84ce46ce8bc6ef1e2455c0a` 并推送。AnalysisReport validator 重新执行 synthetic/offline `READY` 禁止；ChangeReport validator 重新校验 change mode、路径安全和变更事实闭包；ReviewBundle 的 `READY` 必须绑定 `REFERENCE_ONLY` 且 `SATISFIED` 的 docs-check。相关 08-S2/S3 定向回归已纳入 113 项通过结果。

本批仍只提供离线构造器与输入边界，未生成 dispatcher receipt、Pi attempt、真实 provider/native 或 09/10 连接器证据；S4–S6 和生产发布门禁继续 `NOT_RUN/BLOCKED`。

## 2026-10-03 当前修复候选（08-S4～S6 边界）

代码候选已推进到 `35b550fb7b49e55f502c56a011db9a648be0a897` 并推送。S6 离线投影现拒绝 event_id 换序列重放和超过 indexed cursor 的 source vector；S4 regression/mutation/offline runner 与 S5 deterministic evidence/persistent store 审计未发现可安全落地的更高优先级离线修复。

S4/S5 的真实 mutation dispatcher、provider/OS receipt 仍未接入，S6 的 09/10 consumer 仍未连接；以上能力保持 `NOT_RUN/BLOCKED`，不能形成生产 PASS。

## 2026-10-03 当前修复候选（S4 runner 边界）

代码候选已推进到 `f38df44` 并推送。offline runner 对 cwd/path/environment/target 的非法类型、控制字符和 surrogate 输入统一拒绝；S4 定向回归已覆盖这些失败分类。真实 mutation dispatcher、provider/OS receipt 和 09/10 consumer 仍为 `NOT_RUN/BLOCKED`。

随后候选推进到 `ea25ed2`：S6 brief 禁止在 source 或 budget coverage 不完整、或存在 issues 时宣称 `healthy`；投影/集成定向回归 28 项通过。该修复仍是离线边界，不改变 09/10 连接器的 `NOT_RUN/BLOCKED` 状态。
