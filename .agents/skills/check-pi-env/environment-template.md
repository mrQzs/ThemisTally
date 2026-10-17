# 执行环境记录

<!-- 由 check-pi-env 技能生成或更新。只记录事实，不写 API key、令牌或完整环境变量。
     本文件包含机器相关的信息，团队可以决定是否提交；提交前检查其中的路径。 -->

- 记录时间：【YYYY-MM-DD】
- 记录者：【会话或人员】
- 结论：【可以派遣 / 有阻塞：…】

## 规划端

<!-- 按实际使用的工具填写；Claude Code 与 Codex 都用时各填一列或各写一张表。 -->

| 字段 | 值 |
|---|---|
| 工具与版本 | 【Claude Code：claude --version / Codex：codex --version】 |
| 规划模型 | 【实际模型 ID，记录完整 ID，不要只记别名】 |
| 模型配置来源 | 【Claude Code：--model / /model / settings / ANTHROPIC_MODEL；Codex：~/.codex/config.toml / 项目 .codex/config.toml / 命令行】 |
| 思考或推理强度 | 【Claude Code 的 effort；Codex 的 model_reasoning_effort】 |
| 读取的规则文件 | 【AGENTS.md；仓库另有 CLAUDE.md 时写明是否含 @AGENTS.md】 |
| 技能 | 【Codex 读 .agents/skills；Claude Code 读 .claude/skills（sync-adapters 生成，是否一致）】 |
| Codex 沙箱 / 审批 / 项目信任 | 【如 workspace-write / on-request / trusted；不用 Codex 时写 不适用】 |

## 执行端（Pi）

| 字段 | 值 |
|---|---|
| pi 版本 | 【pi --version；建议 ≥ 0.84，最低 0.80.4】 |
| pi 调用方式 | 【doctor 输出的 pi_command，例如 node …/dist/bundle/cli.js】 |
| 执行模型 | 【provider/model，必须与 pi --list-models 的精确 ID 一致】 |
| 思考级别 | high。实际发送形式取决于协议：anthropic-messages 预算模式下为 thinking 预算 16384（可用 settings 的 `thinkingBudgets.high` 调整）；提供商不回报实际级别时，只能确认请求的级别 |
| 思考预算设置 | 【settings.json 中 thinkingBudgets 的值，或 未设置（使用默认）】 |
| 凭据就绪 | 【pi auth check 结果：ready / not_ready】 |
| 工具集 | 【合同默认 read,grep,find,ls,edit,write,bash】 |
| Pi 可用的思考级别 | 【doctor 的 pi_help.thinking_levels】 |
| rg / fd | 【已安装 / 缺失（grep、find 工具首次使用时会从 GitHub 下载）】 |

## 上下文与配置来源（只记路径与哈希，不记内容中的敏感信息）

| 来源 | 路径 | 说明 |
|---|---|---|
| 全局上下文文件 | 【~/.pi/agent/AGENTS.md 或 无】 | 会被执行器加载 |
| 全局 SYSTEM.md / APPEND_SYSTEM.md | 【路径或 无】 | 会改变执行器的系统提示词 |
| 全局 settings.json 的键 | 【如 defaultTools、shellPath、retry】 | 只列键名 |
| worktree 所在目录链上的上下文文件 | 【doctor 中 scope 为 ancestor 的文件，或 无】 | worktree 默认位于系统临时目录下 |
| 项目 .pi/ 资源 | 【有 / 无】 | 调度器用 --no-approve 忽略 |
| 仓库 AGENTS.md（及 CLAUDE.md，如有） | 【是否已提交到 HEAD】 | 未提交的规则不会出现在 worktree 中 |
| 决策模型（2.6.0） | 【doctor 的 decisions 块：模式与原因、环境变量名（不记值）、端点、模型】 | 配置是 on、实际 off 时写明原因 |

## 操作系统与仓库

| 字段 | 值 |
|---|---|
| 系统与架构 | 【如 Windows Server 2025 x64，原生终端，或 WSL / Linux / macOS】 |
| Shell | 【Git Bash 版本 / bash / zsh】 |
| Git | 【git --version】 |
| Python（调度工具） | 【版本；Windows 上 python3 可能是应用商店占位程序】 |
| `.agent/runs/` 已被忽略 | 【是 / 否】 |

## 项目工具链

| 工具 | 版本 | 来源 |
|---|---|---|
| 【Node / pnpm / Python / uv / JDK / Gradle …】 | 【】 | 【锁文件或配置文件路径】 |

## 验证记录

| 项目 | 结果 | 证据 |
|---|---|---|
| doctor（不调用模型） | 【ok / problems】 | .agent/runs/_env/doctor.json |
| 无工具连通性 | 【通过 / 未运行】 | .agent/runs/_env/smoke.json |
| 最小工具任务（写文件并读回） | 【通过 / 未运行】 | 同上 |
| 代表性代码任务 | 【任务 ID 与结论，或 未运行】 | .agent/runs/<task-id>/… |

## 变更记录

| 日期 | 变化 | 需要复评的内容 |
|---|---|---|
| 【YYYY-MM-DD】 | 【首次记录 / pi 升级 / 模型更换】 | 【升级 pi 或更换模型后，重新跑小样本任务】 |
