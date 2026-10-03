# 01–06 离线实现状态

本记录对应基线 `f52dc20058b0997a2abce80711a372bb463f0558` 之后的离线实现提交。它只记录可复核的本地结果；真实 provider、Pi、Windows/macOS 原生进程和外部连接器仍需独立环境取证。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| 01 | `ccb64b6` | 公共协议导入探针在 Python 3.9/3.12 兼容；协议、基线、Git 探针和 legacy fixture 定向测试通过 | Pi、原生平台、真实外部输入未运行 |
| 02 | `52af491`, `a6f214a` | 严格 v2 配置/profile Schema、adapter registry、role 解析、policy 交集、受限 local 覆盖和语义快照；17 项边界测试及 WSL Schema 元校验通过 | 真实 CLI/认证/路径预检未运行 |
| 03 | `8546a4d`, `a6f214a`, `4d2b2b3`, `c6599b0`, `0aa19dc`, `993987b` | approval/input-lock ledger、CAS、幂等、撤销、时间窗口、路径安全和精确输入绑定；追加日志、截断尾恢复、恢复态写入拒绝、严格 v2 authorization envelope、当前性 generation/hash fence、一次消费 fence、重复输入拒绝、消费时间持久化和持久回放；23 项相关测试及 WSL Schema 元校验通过 | 真实并发进程、外部授权服务未运行 |
| 04 | `978a258`, `097d510`, `4b98152`, `be3de10` | adapter descriptor/registry、Invocation identity、事件序列、未知事件保留、usage 和离线 adapter；终止事件唯一且位于末尾、tool 成对闭合、重复 start 拒绝；9 项测试通过 | 真实 provider、Pi 模型和 CLI 事件未运行 |
| 05 | `d1c54cb`, `ee151c2` | argv/shell 互斥、Invocation、进程身份、生命周期 generation fence 和 START_UNKNOWN 对账；5 项测试通过 | Windows/macOS 原生进程树和 shell 未运行 |
| 06 | `358af12`, `8bd8b8c`, `df8f482` | manifest、ResourceRef、依赖拓扑、冲突、动态加载拒绝、manifest-bound lock 和七个离线插件 fixture；插件 ID/版本、数组、lock 行和目录输入严格校验；15 项测试及 WSL Schema 元校验通过 | 真实插件目录、跨平台资源锁和生产 prepare/run 未运行 |

后续离线收紧提交包括 `ebdc0c2`（currentness 类型错误统一为结构化 `ProtocolError`）、`7a29008`（插件可变别名/非序列输入、配方计划状态、目录 fixture 错误边界，以及统一账本 v3 schema/持久行恢复校验）。插件与账本组合定向测试通过；这些提交仍不提供 Pi、真实进程、provider 或外部连接器证据。

## 门禁结论

01–06 当前只能标记为 `REVISE/BLOCKED`：新增模块覆盖了离线结构和最小 happy-path，但增强验收所需的权限交集、持久对账、事件原始证据、进程 fence、资源锁闭包和真实故障证据尚未齐全。08 的离线实现已按双门槛作为 `LOCAL_REFERENCE` 继续推进，但不能据此签发 01–06 阶段 PASS 或生产放行。任何 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED` 结果都不能转化为生产 PASS；真实连接器接入仍是后续生产门禁。

`8df094a` 收紧 InvocationSpec、ProcessIdentity、Lifecycle 及 START_UNKNOWN 对账的类型和 generation 边界；`b3f40aa` 收紧 adapter descriptor/invocation 向量与 provider 观察的跨 run MIRROR 语义。运行时/适配器 22 项、provider/结算 28 项定向测试通过；全量离线回归仍保留 3 项既有 legacy source-lock 失败，真实运行时与 provider 证据继续为 `NOT_RUN/BLOCKED`。

`fbe94d5` 收紧配置输入与平台/占位符边界；`5da5e6a`、`e6bac39` 收紧 Git 探针计划、环境覆盖、LFS/ancestor 观测类型。配置 19 项、Git 探针/ancestor 25 项定向测试通过；这些仍是 `LOCAL_REFERENCE`，真实仓库授权、跨平台环境和 Pi 证据未运行。

`c57c016` 进一步固定 Git probe 的 RawResult/result mapping 字段闭集，拒绝未知观测键并保持 malformed 事实为 `UNKNOWN`；Git 来源相关离线复核扩大到 51 项通过，仍不等价于真实仓库授权或平台接线。

`d456361` 加固 authorization journal candidate-commit、WRITE_UNKNOWN fencing、scheduler resource hold 闭包；`061900a` 加固 projection journal durable publish、cursor/checkpoint 连续性与 acceptance ResourceRef path 绑定。授权/调度 70 项、投影/验收 64 项、配置/Git/adapter/runtime 68 项定向测试通过；生产连接器和独立 Pi 证据仍为 `BLOCKED/NOT_RUN`。

`86a92fc` 将 projection journal 中非法 JSON 值统一映射为 `E_JOURNAL`，避免私有持久化输入泄漏业务层错误；投影定向回归保持通过。

`1caeb6e` 继续收紧离线账本与运行边界：atomic claim/budget、attempt allocator、usage settlement、resume recovery、scheduler/budget store 拒绝非规范 JSON 常量、控制字符、越界整数和不完整持久化闭包；offline runner 保留空 argv 参数、固定环境白名单并按完整可观察证据识别重复运行漂移；回归/变异 artifact 在加载时重算 summary/status，candidate ResourceRef 保留 path 绑定，未知 connector 阶段阻断。该阶段定向套件随后扩展为 87、69、123 项通过（279 项合计）；这些结果仍为 `LOCAL_REFERENCE`，不产生 Pi、provider、原生平台或外部连接器证据。

`e94056a` 收紧插件清单的严格 JSON、深度/数组上限、控制字符、路径和检查 argv 边界，并使身份哈希拒绝循环值与非法 Unicode 标量；插件/身份定向回归继续通过，合同基线已刷新到该提交。

`98a4ed5` 继续收紧 adapter 事件与 payload、runtime lease 的身份/代际/token/时间边界，以及 provider economics 和 unified ledger 的 canonical JSON、循环、Unicode、有限数和安全整数边界；本轮相关组合回归 137 项通过，验收矩阵组合命令 303 项通过、1 项跳过，compileall 和 diff check 通过。结果仍为 `LOCAL_REFERENCE`，真实 Pi、provider、原生平台和外部连接器证据继续为 `BLOCKED/NOT_RUN`。

`9980f27` 收紧授权 journal 与 scheduler SQLite 的协议文本边界，拒绝 C0/C1、DEL 和孤立代理字符，并覆盖写入、重放和重开路径；相关组合回归 112 项通过，验收矩阵组合命令 305 项通过、1 项跳过。结果仍为 `LOCAL_REFERENCE`，真实授权服务、Pi、provider、原生平台和外部连接器证据继续为 `BLOCKED/NOT_RUN`。

`137dae4` 将 provider economics、unified ledger 和 usage settlement 的指纹输入统一收紧为严格 JSON，拒绝不安全整数、数值子类、循环、代理、非有限数和未知对象；相关定向回归 74 项通过，验收矩阵组合命令 311 项通过、1 项跳过。结果仍为 `LOCAL_REFERENCE`，真实 provider、计费系统、Pi、原生平台和外部连接器证据继续为 `BLOCKED/NOT_RUN`。

`1e1363a` 补齐三套 canonical helper 对代理对象键的拒绝，避免 Unicode 编码异常越过结构化错误边界；相关定向回归 44 项通过，验收矩阵计数不变。结果仍为 `LOCAL_REFERENCE`。


`cf3a1cd` 补齐 05 运行时的进程身份闭包、`START_UNKNOWN`/`NOT_STARTED` 对账、安全整数和租约异常边界，并加固 08 投影/09/10 离线投影的 strict JSON、截断尾修复、generation/cursor CAS 与健康/来源一致性。运行时与投影定向套件 62 项通过，统一验收命令 348 项通过、1 项跳过；结果仍为 `LOCAL_REFERENCE`，真实 Pi、provider、原生平台和外部连接器继续为 `BLOCKED/NOT_RUN`。


最新环境复核已确认 `bb/step-5-preview` 可用且认证 ready，但本轮按双门槛与生产隔离约束未运行真实 Pi/provider；因此执行器证据仍为 `NOT_RUN`，不把环境可用性误写成阶段 PASS。


`a64f3a8` 收紧 atomic/budget/scheduler outbox 的严格 JSON、连续序列、请求/操作闭包和数据库范围 high-water；账本定向套件与 01–06/08 组合验收共 398 项通过、8 项环境跳过。插件/配方边界也完成离线收紧；真实 Pi/provider、原生平台和外部连接器仍未运行。

Git Bash Python 3.12.3 对同一组合套件复核为 398 项通过、1 项跳过，7 项 schema 实例不再跳过；Windows Python 3.9.23 的跳过保持为环境事实。


`dda848ddfadd28bb06ac8c5b603623f06a54c767` 继续收紧 adapter 事件闭集与安全整数、离线未知/错误终止语义、配置 canonical JSON/平台覆盖边界、ResourceClaim 身份文本，以及授权 ResourceRef/严格 JSON/输入引用上限；适配器、身份、配置、授权和接受边界定向回归 105 项通过，全量组合回归 398 项通过、8 项环境跳过。真实 Pi/provider、原生平台和外部连接器仍为 `NOT_RUN/BLOCKED`。


`24760ceec4c3350327a0cf194c58a48a9d9cabf2` 继续收紧统一账本 attempt/migration 状态、refund call_key 幂等与跨 operation 归属，并强化 builtin projection/journal 的安全整数、文本和 generation/CAS 边界；扩展组合回归 474 项通过、8 项环境跳过。真实 Pi/provider、原生平台和外部连接器仍为 `NOT_RUN/BLOCKED`。


`ef5ff25e9f41cea1096f75d31b027ef4dafcb66b` 对旧 projections readiness/outbox 接口补齐 C1/代理字符、generation/cursor 安全整数、event_id 和状态文本闭集；扩展组合回归 478 项通过、8 项环境跳过。真实 Pi/provider、原生平台和外部连接器仍为 `NOT_RUN/BLOCKED`。

## 2026-10-03 当前离线候选

`8c16333ff8d3b80eda8c95216d1236d9f3fe23cf` 收紧授权/配置 canonical JSON 的编码后字节上限、approval subject/input 闭包、空 option schema，并补充 docs/plugin artifact 的 scope、生产状态和 review readiness 重放校验。01–06/08 扩展组合为 542 项收集、534 项通过、8 项环境跳过；插件全集为 102 项收集、95 项通过、7 项环境跳过。该结果是规划端离线 `LOCAL_REFERENCE`，没有 Pi attempt、真实 provider、原生平台或 09/10 连接器证据，阶段门继续 `REVISE/BLOCKED`。


## 2026-10-03 Latest Offline Candidate (SourceAnchor and InvocationSpec hardening)

The code candidate is `296135cb8eef4cbf54585d755f3ca437f7e74a51`. `d44a7a9` binds SourceAnchor to frozen resource bytes, the complete resource digest, a half-open range, and the excerpt digest. `296135c` freezes InvocationSpec argv as an immutable tuple so a caller cannot change the digest after construction.

Latest raw captures:

- `.agent/runs/offline-01-06-08-20261003-builtin-all-06/`: 103 collected, 96 executed passes, 7 skips because optional Schema dependencies are unavailable on Windows; return code 0, `baseline_consistent=true`, no drift.
- `.agent/runs/offline-01-06-08-20261003-expanded-all-06/`: 544 collected, 536 executed passes, 8 skips for the same environment condition; return code 0, `baseline_consistent=true`, no drift.

These remain offline `LOCAL_REFERENCE` results. No Pi attempt, real provider, Windows/macOS native process, external 09/10 consumer, or production dispatcher was run. The 01-06 and 08 gates remain `REVISE/BLOCKED`, and the production release gate stays closed.


## 2026-10-03 Latest Offline Candidate (runtime reconciliation and journal replay hardening)

The code candidate is `8348af691d33e08f111b5cebbe852cb66f31a80b`. `8348af6` hardens persisted platform reconciliation (closed observation, connected/execution-mode consistency, safe command and environment digest) and authorization journal replay (strict JSON duplicate-key, byte, depth, and non-finite rejection while preserving truncated-tail durable-prefix recovery).

Latest raw captures:

- `.agent/runs/offline-01-06-08-20261003-builtin-all-07/`: 105 collected, 98 executed passes, 7 optional Schema dependency skips; return code 0, `baseline_consistent=true`, no drift.
- `.agent/runs/offline-01-06-08-20261003-expanded-all-07/`: 549 collected, 541 executed passes, 8 optional Schema dependency skips; return code 0, `baseline_consistent=true`, no drift.

These remain offline `LOCAL_REFERENCE` results. Real Pi/provider, native process, external consumer, billing, and recovery evidence remains `NOT_RUN/BLOCKED`; the stage and production gates remain closed.


## 2026-10-03 当前离线候选（SourceAnchor 构建器与严格回执探针）

`5d141298d052b291c1dba3fe35075d6303f0bbc8` 要求 analysis/docs-change 构建器在生成 SourceAnchor 时提供冻结资源字节，并校验 ResourceRef、半开字节区间和 excerpt 摘要；授权锁回执探针统一使用 strict JSON。新增 builder 级漂移、缺少快照和重复键回归。插件全集取证为 107 项收集、100 项通过、7 项可选 Schema 依赖跳过；01–06/08 扩展取证为 552 项收集、544 项通过、8 项跳过。结果仍是 `LOCAL_REFERENCE`；真实 Pi/provider、原生平台和外部连接器为 `NOT_RUN/BLOCKED`，阶段门继续 `REVISE/BLOCKED`。

## 2026-10-03 Full Discover Timeout Update

Candidate \`5d141298d052b291c1dba3fe35075d6303f0bbc8\` remains the last implementation candidate; publication commit is \`99bda89b9f61754b7bbdc206f4a1ed97425e16a5\`. The fresh capture \`.agent/runs/offline-01-06-08-20261003-full-discover-09/\` attempted \`python -B -m unittest discover -s tests -q\` under the supervisor for 900.031 seconds. It timed out with \`returncode=null\`, \`timed_out=true\`, \`termination_confirmed=true\`, \`stray_processes=false\`, empty stdout/stderr, and no baseline drift. \`execution_status=complete\` only means the capture itself is complete; the test result is \`TIMEOUT/BLOCKED\`, not PASS. The 01–06 and 08 stage gates therefore remain \`REVISE/BLOCKED\`, with real Pi/provider/native platform/09/10 connector evidence still \`NOT_RUN/BLOCKED\`.