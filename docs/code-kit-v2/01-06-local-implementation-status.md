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
