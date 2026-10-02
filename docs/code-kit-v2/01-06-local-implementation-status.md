# 01–06 离线实现状态

本记录对应基线 `f52dc20058b0997a2abce80711a372bb463f0558` 之后的离线实现提交。它只记录可复核的本地结果；真实 provider、Pi、Windows/macOS 原生进程和外部连接器仍需独立环境取证。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| 01 | `ccb64b6` | 公共协议导入探针在 Python 3.9/3.12 兼容；协议、基线、Git 探针和 legacy fixture 定向测试通过 | Pi、原生平台、真实外部输入未运行 |
| 02 | `52af491`, `a6f214a` | 严格 v2 配置/profile Schema、adapter registry、role 解析、policy 交集、受限 local 覆盖和语义快照；17 项边界测试及 WSL Schema 元校验通过 | 真实 CLI/认证/路径预检未运行 |
| 03 | `8546a4d`, `a6f214a` | approval/input-lock ledger、CAS、幂等、撤销、时间窗口、路径安全和精确输入绑定；12 项边界测试及 WSL Schema 元校验通过 | 真实持久化、并发进程、外部授权服务未运行 |
| 04 | `978a258`, `097d510`, `4b98152` | adapter descriptor/registry、Invocation identity、事件序列、未知事件保留、usage 和离线 adapter；7 项测试通过 | 真实 provider、Pi 模型和 CLI 事件未运行 |
| 05 | `d1c54cb`, `ee151c2` | argv/shell 互斥、Invocation、进程身份、生命周期 generation fence 和 START_UNKNOWN 对账；5 项测试通过 | Windows/macOS 原生进程树和 shell 未运行 |
| 06 | `358af12`, `8bd8b8c`, `df8f482` | manifest、ResourceRef、依赖拓扑、冲突、动态加载拒绝、manifest-bound lock 和七个离线插件 fixture；15 项测试及 WSL Schema 元校验通过 | 真实插件目录、跨平台资源锁和生产 prepare/run 未运行 |

## 门禁结论

01–06 当前只能标记为 `REVISE/BLOCKED`：新增模块覆盖了离线结构和最小 happy-path，但增强验收所需的权限交集、持久对账、事件原始证据、进程 fence、资源锁闭包和真实故障证据尚未齐全。08 的离线实现已按双门槛作为 `LOCAL_REFERENCE` 继续推进，但不能据此签发 01–06 阶段 PASS 或生产放行。任何 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED` 结果都不能转化为生产 PASS；真实连接器接入仍是后续生产门禁。
