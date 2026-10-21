# 执行环境记录

<!-- 由 check-pi-env 技能生成或更新；不记录凭据或完整环境变量。 -->

- 记录时间：2026-10-21
- 记录者：Claude Code（规划端会话）
- 结论：可以派遣（`bb/step-5-preview` + high 在模型列表中，smoke 两步通过）。2026-10-21 本机的 step-5-preview 又从 `step` 回到 `bb` 提供商；决策模型的 key 在 Windows 凭据管理器里；控制台代码页是 cp1252。

## 规划端

| 字段 | 值 |
|---|---|
| 工具与版本 | Claude Code 2.1.303；Codex CLI 0.163.0（未作规划端） |
| 规划模型 | `claude-opus-5-5`（Opus 5.5） |
| 模型配置来源 | 会话缺省（本次核验未另行确认 `/model`） |
| 思考或推理强度 | 会话设置，本次核验未确认 |
| 读取的规则文件 | 仓库 `AGENTS.md`，已提交，14336 bytes；无 CLAUDE.md |
| 技能 | `.claude/skills` 与 `.agents/skills` 一致（doctor：无缺失、无漂移） |
| Codex 沙箱 / 审批 / 项目信任 | 不适用 |
| 登录 | `claude auth status`：claude.ai 登录、订阅 max（只记类型）。旧机器上的账号对 Claude Code 的后台进程返回 403 `oauth_not_allowed_for_organization`，本机没有这个问题 |

## 七端的 claude 后台进程（3.0 第三轮，`scripts/kit_hub.py`）

按 hub 的启动方式（`claude -p … --setting-sources project --strict-mcp-config --disable-slash-commands --permission-prompts none`）各发一句最小请求，2026-10-19：

| 工人 | 模型 · 档位 | 结果 |
|---|---|---|
| womovie-c8（协调人） | `claude-haiku-5-5` · max | 通过 |
| planner-opus | `claude-opus-5-5` · max | 通过 |
| gate-sonnet | `claude-sonnet-5-5` · high | 通过 |
| audit-sonnet | `claude-sonnet-5-5` · max | 通过 |

- init 仍报告 3 个插件（cc-plugin-agents-md、cc-plugin-telemetry、cc-plugin-plugin-authoring）；工具白名单生效，内核的事后审计拦白名单之外的调用。
- 权限实测：默认模式下工作目录里的 Write 也被拒；hub 已改为 `--add-dir <主工作区>`，有写工具的工人另加 `acceptEdits` 与主工作区的拒写规则（设计 §6.1）。

## 执行端（Pi）

| 字段 | 值 |
|---|---|
| pi 版本 | 1.3.0 |
| pi 调用方式 | `node …/@earendil-works/pi-coding-agent/dist/bundle/cli.js`（npm 全局安装，`~/AppData/Roaming/npm`） |
| 执行模型 | `bb/step-5-preview`（2026-10-21 `pi --list-models` 列出；`step/…` 已不存在） |
| 思考级别 | high；Pi 记录的 `thinkingLevel` 为 high，推理题有思考内容 |
| 思考预算设置 | 未设置（使用默认） |
| 凭据就绪 | `bb/step-5-preview` 与 `token/qwen3.7-plus` 的 smoke 两步通过（2026-10-21，`.agent/runs/_env/smoke-bb.json`、`smoke-token.json`） |
| 工具集 | read, bash, powershell, edit, write, grep, find, ls |
| Pi 可用的思考级别 | off, minimal, low, medium, high, xhigh, max |
| rg / fd | rg 14.1.1 已安装；fd 未安装（find 工具首次使用时会下载） |
| 七端的岗位（第 36 轮，用户 2026-10-21） | 规划端 Claude Code `claude-opus-5-5` max；审核端 `cc-switch-zhipu-glm/glm-5.3` max（Pi 静默降到 high：模型配置没有 xhigh / max 的映射）；门禁端 `bb/step-5-preview` high；合同端与协调人 `token/qwen3.7-plus` high；执行端 `bb/step-5-preview` high。站主列的 `minimax/MiniMax-M3.1-Flash` 不在本机 `pi --list-models` 里（多半是凭据没配），有了再给协调人 |
| pi 模型列表（2026-10-21） | bb/step-5-preview、cc-switch-zhipu-glm/glm-5.3、cc-switch-zhipu-glm/glm-5.3-flash、cpa/claude-opus-5-5-high、token/qwen3.7-plus |
| 注意 | 在 Git Bash 里直接跑 `pi -p` 要接 `< /dev/null`，否则它等标准输入，不会退出；调度器与 hub 都用 `stdin=DEVNULL`，不受影响 |

## 上下文与配置来源

| 来源 | 路径 | 说明 |
|---|---|---|
| 全局上下文文件 | 无 | doctor 未发现 |
| 全局 SYSTEM.md / APPEND_SYSTEM.md | 无 | doctor 未发现 |
| 全局 settings.json 的键 | lastChangelogVersion, theme | 只记录键名 |
| worktree 所在目录链上的上下文文件 | 仓库 `AGENTS.md`（scope：worktree） | 已提交 |
| 项目 `.pi/` 资源 | 无；`.agents/skills` 被 `--no-approve` 忽略 | 调度器用 `--no-approve` |
| 仓库 AGENTS.md（及 CLAUDE.md，如有） | AGENTS.md 已提交到 HEAD；无 CLAUDE.md | 执行器可加载 AGENTS.md |
| 决策模型（2.6.0） | 调度器里生效 off（not_configured）；环境变量名 `TYPESAFE_API_KEY` 未设置，key 来自凭据库（`secret_source: credential_store`，Windows 凭据管理器）；端点 `https://api.typesafe.ai`，模型 `jev-1.13.0`；三份题库内容锁 ok | `doctor --probe-decisions` 通过：202 毫秒，回复形状一致。hub 的 JEV 端经同一客户端读凭据库 |

## 操作系统与仓库

| 字段 | 值 |
|---|---|
| 系统与架构 | Windows Server 2025（10.0.26100）x64，用户 Administrator |
| Shell | Git Bash（GNU bash 5.3.15）；PowerShell 7 可用 |
| 控制台编码 | cp1252（系统区域 en-US）：规划端自己的 Python 脚本输出中文前设 `PYTHONUTF8=1`；kit 脚本自己把输出改成 UTF-8 |
| Git | 2.55.0.windows.5；系统级 `core.autocrlf=true`；Git 作者身份可用 |
| Python（调度工具） | 3.12.10（`C:/Program Files/Python312`）；`tests` 解析到仓库，没有旧机器上那个遮挡的第三方包 |
| `.agent/runs/` 已被忽略 | 是 |
| kit 布局 | source（本仓库就是 kit），无缺失文件 |
| 仓库搬迁 | 经压缩包搬来，21 个中文文件名被按 GBK→CP437 弄乱，已按原名改回（16 个已跟踪文件与 HEAD 逐字节相同）。旧 worktree 的登记已 `git worktree prune` |

## 项目工具链

| 工具 | 版本 | 来源 |
|---|---|---|
| Python | 3.12.10 | PATH |
| pytest | 9.1.1 | 同上 |
| Node | 24.19.0 | pi 的运行时 |

## 验证记录

| 项目 | 结果 | 证据 |
|---|---|---|
| doctor（不调用模型） | ok，problems 与 notes 为空 | `.agent/runs/_env/doctor.json`（2026-10-19） |
| 无工具连通性 | 通过：Step high 13.5 秒、GLM 4.8 秒，都答 `PI_SMOKE_OK` | 本会话的 smoke 输出（未写 `--out`） |
| 最小工具任务（写文件并读回） | 通过：Step 6.7 秒、GLM 9.2 秒 | 同上 |
| 推理题（1000 以内被 7 整除、不被 11 整除的个数） | Step high：有思考内容，答 130，正确 | 本会话 |
| 决策模型探测 | 通过（`jev-1.13.0`，答 0.98） | 本会话的 doctor 输出 |
| 全量测试（themis-3.0 `13e3d58` 加未提交的 hub 修补，Python 3.12.10） | 1992 passed、6 skipped、5224 subtests passed、1 failed，用时 13 分 41 秒。失败的 `test_desktop_cli::test_cat_reads_are_bounded` 是测试夹具的平台假设：假的 lstat 缺 `st_reparse_tag`，而 3.12 在 Windows 上的 `os.path.isjunction` 是纯 Python 实现、要读它（旧机器跑全量用 3.13，走 C 实现）。夹具补上两个属性后该文件 18 passed。旧机器的记录是 1530 passed、41 skipped（`c4afa1d`，之后加了用例） | 本会话 |
| 代表性代码任务 | T001（七端的第一个任务，改桌面端文档）在本机恢复运行 | `.agent/mailbox/` |

## 变更记录

| 日期 | 变化 | 需要复评的内容 |
|---|---|---|
| 2026-09-29 | 首次记录；pi 0.87.0 / step-5-preview 核验 | Pi 或模型更换后重跑 doctor；模型调用前另行记录 smoke 状态 |
| 2026-10-02 | 重新核验发现 pi 1.0.0、step/step-5-preview 未列出且 auth check 未就绪；记录 Python 3.9/3.12 双运行时 | Pi 模型、凭据或运行时修复后重跑 doctor；不得据此派遣 |
| 2026-10-03 | doctor 2.2.2 / Codex 0.160.0 / Claude Code 2.1.288；`step/…` 未列出；另记 `bb/step-5-preview` 列出且 auth ready | 外部环境修复后重新核验 |
| 2026-10-17 | pi 升到 1.3.0；Claude Code 2.1.302、Codex 0.163.0；执行模型确定为 `bb/step-5-preview` + high；缺省 `python` 换成 conda `cell_gpu` 3.10.19（带遮挡的 `tests` 包）；规划端为 Claude Code + Opus 5.5 | 换解释器或 pi 再次升级后重跑 doctor；首轮派遣的结果写回“代表性代码任务” |
| 2026-10-19 | 换到新机器（Windows Server 2025）：执行模型 `step/step-5-preview` + high；Claude Code 2.1.303；Python 3.12.10；JEV 的 key 在凭据库；七端的四种 claude 工人配置与 GLM-5.3 实测可用 | 全量测试结果写回“验证记录”；T001 跑完后补“代表性代码任务” |
| 2026-10-21 | step-5-preview 回到 `bb` 提供商；七端只有规划端留在 Claude 上，协调人、合同端、门禁端、审核端换到 pi（第 36 轮）；qwen3.7-plus 与 bb/step-5-preview smoke 通过；MiniMax-M3.1-Flash 未列出 | MiniMax 配好后核验并换协调人；门禁端、审核端换模型后的头几片看回合作废率与终审质量 |
