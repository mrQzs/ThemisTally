# 执行环境记录

<!-- 由 check-pi-env 技能生成或更新；不记录凭据或完整环境变量。 -->

- 记录时间：2026-09-29
- 记录者：Codex
- 结论：可以派遣

## 规划端

| 字段 | 值 |
|---|---|
| 工具与版本 | Codex CLI 0.159.0；Claude Code 2.1.284（doctor 记录） |
| 规划模型 | 当前 Codex 会话模型由宿主配置；未覆盖执行模型 |
| 思考或推理强度 | 由当前 Codex 会话配置 |
| 读取的规则文件 | AGENTS.md（已提交） |
| 技能 | `.agents/skills`；Claude 适配器已安装且无漂移 |
| Codex 沙箱 / 审批 / 项目信任 | danger-full-access；approval never |

## 执行端（Pi）

| 字段 | 值 |
|---|---|
| pi 版本 | 0.87.0 |
| pi 调用方式 | `node .../@earendil-works/pi-coding-agent/dist/bundle/cli.js` |
| 执行模型 | `step/step-5-preview` |
| 思考级别 | high |
| 思考预算设置 | 未设置（使用默认） |
| 凭据就绪 | ready（仅记录状态） |
| 工具集 | read, bash, powershell, edit, write, grep, find, ls |
| Pi 可用的思考级别 | off, minimal, low, medium, high, xhigh, max |
| rg / fd | 已安装/可用（仓库调查使用 rg） |

## 上下文与配置来源

| 来源 | 路径 | 说明 |
|---|---|---|
| 全局上下文文件 | 无额外 AGENTS.md | doctor 未发现 |
| 全局 SYSTEM.md / APPEND_SYSTEM.md | 无 | doctor 未发现 |
| 全局 settings.json 的键 | lastChangelogVersion, theme | 只记录键名 |
| worktree 所在目录链上的上下文文件 | 仓库 `AGENTS.md` | 已提交 |
| 项目 `.pi/` 资源 | 无 | 调度器 `--no-approve` 不依赖 |

## 操作系统与仓库

| 字段 | 值 |
|---|---|
| 系统与架构 | Windows Server 2025 x64 |
| Shell | PowerShell；调度脚本可用 Python 等价入口 |
| Git | 2.55.0.windows.5 |
| Python（调度工具） | 3.12.10 |
| `.agent/runs/` 已被忽略 | 是（本次补齐 `.gitignore`） |

## 项目工具链

| 工具 | 版本 | 来源 |
|---|---|---|
| Python | 3.12.10 | 运行时 |

## 验证记录

| 项目 | 结果 | 证据 |
|---|---|---|
| doctor（不调用模型） | ok；初次运行发现并修复 runs 忽略规则 | `.agent/runs/_env/doctor.json` |
| 无工具连通性 | 未运行 | 用户未要求单独 smoke |
| 最小工具任务 | 未运行 | 用户未要求单独 smoke |
| 代表性代码任务 | 未运行 | 待 07 合同派遣 |

## 变更记录

| 日期 | 变化 | 需要复评的内容 |
|---|---|---|
| 2026-09-29 | 首次记录；Pi 0.87.0 / step-5-preview 核验 | Pi 或模型更换后重跑 doctor；模型调用前另行记录 smoke 状态 |
