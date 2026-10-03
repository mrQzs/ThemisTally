# 11 本机 Codex CLI 免费探针记录

日期：2026-10-04

## 范围

本次只执行本机 CLI 的版本和帮助查询，用于候选能力调查；没有发送 prompt，没有读取凭据，没有启动模型请求，也没有写入外部系统。

## 观察结果

- `codex --version` 返回 `codex-cli 0.160.0`。
- `codex exec --help` 暴露非交互入口、`--model`、`--json`、`--output-schema`、sandbox 和审批参数。
- 帮助文本本身只能证明可执行入口和声明的输出选项；它不能证明认证、实际模型身份、结构化事件内容、工具闭合、usage 或平台进程生命周期。

## 分类

| 能力 | 状态 | 证据边界 |
|---|---|---|
| 可执行文件和版本 | `LOCAL_REFERENCE` | 版本命令退出 0 |
| 帮助面和候选参数 | `LOCAL_REFERENCE` | `exec --help` 输出 |
| 真实模型调用 | `NOT_RUN` | 本次未发送 prompt |
| provider/认证 | `NOT_RUN` | 未检查凭据 |
| 事件/模型/usage 实际协议 | `NOT_RUN` | 帮助文本不足以证明 |
| 原生进程、取消、清理 | `BLOCKED` | 未接入 05 runner |

## 结论

当前仍优先使用已完成离线协议夹具的 Claude Code 适配器；Codex CLI 仅保留为第二候选。要把 Codex 接入 11，必须另立合同，绑定精确模型、真实调用预算和结构化输出证据；本探针不构成生产能力或发布门禁通过。
