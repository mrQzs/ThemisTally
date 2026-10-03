# 11 候选 CLI 能力调查与离线证据

记录时间：2026-10-04。本文是 11 S0/S1 的证据说明，不授予真实模型调用、费用或生产接线权限。

本机选择第一个候选为 `claude`，因为它可执行、能返回版本和帮助，并在帮助面声明 `--print --output-format stream-json`。本次只运行了：

```text
claude --version
claude --help
```

结果为 Claude Code 2.1.288；脱敏原始字节和 SHA-256 在 [tests/fixtures/11](../../tests/fixtures/11/) 中。帮助输出被当作声明证据，不能证明模型身份、工具执行、用量或原生进程生命周期。

当前支持边界：

| 维度 | 状态 | 证据或限制 |
|---|---|---|
| Windows/native 可执行文件 | `OBSERVED_EXECUTABLE` | 版本/help fixture，退出码均为 0 |
| planner/executor profile 形状 | `LOCAL_REFERENCE` | adapter capability/profile binding 离线测试 |
| stream-json 解析 | `LOCAL_REFERENCE` | 脱敏事件 fixture 和终态/工具/用量测试 |
| 实际模型身份 | `NOT_RUN` | 未启动 `--print` 模型请求 |
| provider/认证 | `NOT_RUN` / `NOT_INSPECTED` | 未读取凭据、未执行 auth 或 provider 请求 |
| 05 进程启动、取消、清理 | `BLOCKED` | 尚未接入真实 runner |
| Linux、WSL、macOS 原生组合 | `NOT_RUN` | 当前环境没有对应实测证据 |
| Pi/09/10 外部连接器 | `NOT_RUN` | 仅完成离线协议和 start gate |

`require_observed=True` 会拒绝仅有版本/help 声明的 profile。真实能力通过前，所有 planner/executor 运行均保持 `NOT_RUN/BLOCKED`，不得把 fixture PASS 写成生产 PASS。
