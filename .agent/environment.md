# 执行环境记录

<!-- 由 check-pi-env 技能生成或更新；不记录凭据或完整环境变量。 -->

- 记录时间：2026-10-17
- 记录者：Claude Code（规划端会话）
- 结论：可以派遣（`bb/step-5-preview` + high 在模型列表中、auth 就绪，doctor 无问题）。注意本机缺省 `python` 的环境里有一个第三方 `tests` 包，全量测试要换解释器（见“项目工具链”）。

## 规划端

| 字段 | 值 |
|---|---|
| 工具与版本 | Claude Code 2.1.302；Codex CLI 0.163.0（本轮只用于 2gate 的对抗审核，经 openai-codex 插件的 codex-companion，不作规划端） |
| 规划模型 | `claude-opus-5-5`（Opus 5.5） |
| 模型配置来源 | 会话开始时用户执行 `/model`，选 Opus 5.5 并保存为新会话的缺省 |
| 思考或推理强度 | max（仅本会话） |
| 读取的规则文件 | 仓库 `AGENTS.md`，已提交，12174 bytes；无 CLAUDE.md |
| 技能 | `.claude/skills` 与 `.agents/skills` 一致（doctor：无缺失、无漂移） |
| Codex 沙箱 / 审批 / 项目信任 | 不适用（Codex 不作规划端；审核任务为只读） |
| 子代理 | 本环境 `general-purpose` 子代理的缺省模型是 `claude-haiku-5-5`（与主会话不同）；会话记录在 `<会话目录>/subagents/agent-<id>.jsonl` |

## 执行端（Pi）

| 字段 | 值 |
|---|---|
| pi 版本 | 1.3.0 |
| pi 调用方式 | `node …/@earendil-works/pi-coding-agent/dist/bundle/cli.js`（npm 全局安装） |
| 执行模型 | `bb/step-5-preview`（`pi --list-models` 命中 1 行）；`step/step-5-preview` 不在列表、auth 未就绪 |
| 思考级别 | high（请求级别；提供商不回报实际级别时只能确认请求的级别） |
| 思考预算设置 | 未设置（使用默认） |
| 凭据就绪 | ready（`pi auth check --no-refresh`：provider `bb`，authType `api_key`） |
| 工具集 | read, bash, powershell, edit, write, grep, find, ls |
| Pi 可用的思考级别 | off, minimal, low, medium, high, xhigh, max |
| rg / fd | rg 14.1.1 已安装；fd 未安装（find 工具首次使用时会下载） |

## 上下文与配置来源

| 来源 | 路径 | 说明 |
|---|---|---|
| 全局上下文文件 | 无 | doctor 未发现 |
| 全局 SYSTEM.md / APPEND_SYSTEM.md | 无 | doctor 未发现 |
| 全局 settings.json 的键 | lastChangelogVersion, theme | 只记录键名 |
| worktree 所在目录链上的上下文文件 | 仓库 `AGENTS.md`（scope：worktree） | 已提交 |
| 项目 `.pi/` 资源 | 无；`.agents/skills` 被 `--no-approve` 忽略 | 调度器用 `--no-approve` |
| 仓库 AGENTS.md（及 CLAUDE.md，如有） | AGENTS.md 已提交到 HEAD；无 CLAUDE.md | 执行器可加载 AGENTS.md |
| 决策模型（2.6.0） | 生效 off（configured off，原因 not_configured）；环境变量名 `TYPESAFE_API_KEY` 已设置（来源 env，不记值） | 未启用 |

## 操作系统与仓库

| 字段 | 值 |
|---|---|
| 系统与架构 | Windows 10.0.26200 x64 |
| Shell | Git Bash（GNU bash 5.2.37）；PowerShell 可用 |
| Git | 2.52.0.windows.1；系统级 `core.autocrlf=true`；Git 作者身份可用 |
| Python（调度工具） | Git Bash 下 `python` 为 3.10.19（conda 环境 `cell_gpu`） |
| `.agent/runs/` 已被忽略 | 是 |
| kit 布局 | source（本仓库就是 kit），无缺失文件 |

## 项目工具链

| 工具 | 版本 | 来源 |
|---|---|---|
| Python（缺省 `python`） | 3.10.19，conda 环境 `cell_gpu` | PATH；其 site-packages 里有一个第三方 `tests` 包，会遮住仓库的 `tests/`，依赖 `from tests.… import` 的旧测试在它下面收集失败（README 已提示） |
| Python（全量测试用） | 3.13.16，miniconda 基础环境（`~/miniconda3/python`），`tests` 解析到仓库 | 合同检查只跑具体测试文件，不受上一行影响 |

## 验证记录

| 项目 | 结果 | 证据 |
|---|---|---|
| doctor（不调用模型） | ok，problems 与 notes 为空 | `.agent/runs/_env/doctor.json`（2026-10-17T10:41:51Z） |
| 无工具连通性 | 未运行 | 用户未单独要求 smoke |
| 最小工具任务（写文件并读回） | 未运行 | 同上 |
| 全量测试（themis-3.0 分支 `c4afa1d`，基础环境 Python 3.13.16） | 1530 passed、41 skipped、4893 subtests passed，用时 9 分 4 秒 | 本会话的测试输出 |
| 代表性代码任务 | 首轮 T1（kit-logs.v1）即将派遣 | `.agent/runs/kit-logs/…` |

## 变更记录

| 日期 | 变化 | 需要复评的内容 |
|---|---|---|
| 2026-09-29 | 首次记录；pi 0.87.0 / step-5-preview 核验 | Pi 或模型更换后重跑 doctor；模型调用前另行记录 smoke 状态 |
| 2026-10-02 | 重新核验发现 pi 1.0.0、step/step-5-preview 未列出且 auth check 未就绪；记录 Python 3.9/3.12 双运行时 | Pi 模型、凭据或运行时修复后重跑 doctor；不得据此派遣 |
| 2026-10-03 | doctor 2.2.2 / Codex 0.160.0 / Claude Code 2.1.288；`step/…` 未列出；另记 `bb/step-5-preview` 列出且 auth ready | 外部环境修复后重新核验 |
| 2026-10-17 | pi 升到 1.3.0；Claude Code 2.1.302、Codex 0.163.0；执行模型确定为 `bb/step-5-preview` + high；缺省 `python` 换成 conda `cell_gpu` 3.10.19（带遮挡的 `tests` 包）；规划端为 Claude Code + Opus 5.5 | 换解释器或 pi 再次升级后重跑 doctor；首轮派遣的结果写回“代表性代码任务” |
