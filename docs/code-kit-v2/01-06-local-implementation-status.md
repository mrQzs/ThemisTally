# 01–06 离线实现状态

本记录对应基线 `f52dc20058b0997a2abce80711a372bb463f0558` 之后的离线实现提交。它只记录可复核的本地结果；真实 provider、Pi、Windows/macOS 原生进程和外部连接器仍需独立环境取证。

| 阶段 | 实现提交 | 离线结果 | 生产/平台状态 |
|---|---|---|---|
| 01 | `ccb64b6` | 公共协议导入探针在 Python 3.9/3.12 兼容；协议、基线、Git 探针和 legacy fixture 定向测试通过 | Pi、原生平台、真实外部输入未运行 |
| 02 | `52af491` | 严格 v2 配置/profile Schema、adapter registry、role 解析、local 受限覆盖和语义快照；8 项测试及 WSL Schema 元校验通过 | 真实 CLI/认证/路径预检未运行 |
| 03 | `8546a4d` | approval/input-lock ledger、CAS、幂等、撤销、动作与输入精确绑定；5 项测试及 WSL Schema 元校验通过 | 真实持久化、并发进程、外部授权服务未运行 |
| 04 | `978a258` | adapter descriptor/registry、Invocation、事件序列、identity、usage 和离线 adapter；5 项测试通过 | 真实 provider、Pi 模型和 CLI 事件未运行 |
| 05 | `d1c54cb` | argv/shell 互斥、Invocation、进程身份、生命周期和 START_UNKNOWN 对账；4 项测试通过 | Windows/macOS 原生进程树和 shell 未运行 |
| 06 | `358af12` | manifest、ResourceRef、依赖拓扑、冲突、动态加载拒绝和 lock 漂移；5 项测试及 WSL Schema 元校验通过 | 真实插件目录、跨平台资源锁和生产 prepare/run 未运行 |

## 门禁结论

01–06 离线门允许开始 08 的离线 S1–S4 实现。任何 `LOCAL_REFERENCE`、`NOT_RUN` 或 `BLOCKED` 结果都不能转化为生产 PASS；真实连接器接入仍是后续生产门禁。
