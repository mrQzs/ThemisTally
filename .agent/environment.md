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
| 执行模型 | `cc-switch-step-fun/step-5-preview`（2026-10-22 第 63 轮：站主重配 pi 的提供方，`bb` 改名为 `cc-switch-step-fun`，同一个 StepFun 套餐端点、同一个模型；`bb/…`、`step/…` 都已不存在） |
| 思考级别 | high；Pi 记录的 `thinkingLevel` 为 high，推理题有思考内容 |
| 思考预算设置 | 未设置（使用默认） |
| 凭据就绪 | 2026-10-22 smoke 两步通过：`cc-switch-step-fun/step-5-preview` high（`.agent/runs/_env/smoke-step-fun.json`）；`minimax/MiniMax-M3.1-Flash` max（`smoke-minimax-MiniMax-M3.1-Flash-max.json`）；`minimax/MiniMax-M3` high（`smoke-minimax-MiniMax-M3-high.json`）；`minimax/MiniMax-M3.1-Flash` high 第一次“工具”一步没过、重跑通过（`…-high.json`、`…-high-2.json`）：模型把 write 与 read 并行发出，read 在写盘之前执行报 ENOENT，参数本身没问题。thinking 的实际档位端点不回报，effort_effective 照实记为未确认。更早的 bb、token 的 smoke 只作历史记录 |
| 工具集 | read, bash, powershell, edit, write, grep, find, ls |
| Pi 可用的思考级别 | off, minimal, low, medium, high, xhigh, max |
| rg / fd | rg 14.1.1 已安装；fd 未安装（find 工具首次使用时会下载） |
| 七端的岗位（第 65 轮，2026-10-22，站主授权 themistally-15 联网调研、出题实测之后分配） | 规划端 Claude Code `claude-opus-5-5` max；审核端 `minimax/MiniMax-M3.1-Flash` max（实测 pi 回报 thinkingLevel=max，不再静默降级）；合同端 `minimax/MiniMax-M3` high（pi 把它的 max 压成 high）；协调人 `minimax/MiniMax-M3.1-Flash` high；门禁端、执行端 `cc-switch-step-fun/step-5-preview` high。依据：7 道自动判分题（协调路由、合同范围路径、找 bug、审查 diff 违规、推理、只读写文件修 bug、写能抓住变异的测试），step-5 7/7，三个 MiniMax 模型前 6 题全对、写测试那道多半写坏；公开数据 step-5 Terminal-Bench 2.1 85.0、MCP-Atlas 85.6，M3.1-Flash 的 AA 智能指数 42.7 高于 M3 的 29.2，M3 的 IFBench 82.9。审核端（MiniMax）与执行端、门禁端（StepFun）不是同一家；合同端与审核端同一家、不同模型，JEV 的 contract-screen 再补一层 |
| 七端的岗位（历史：第 63 轮，2026-10-22） | 规划端 Claude Code `claude-opus-5-5` max；门禁端、执行端 `cc-switch-step-fun/step-5-preview` high（bb 改名）。协调人（`token/qwen3.7-plus`）、合同端与审核端（`cc-switch-zhipu-glm/glm-5.3`）**停用、待重新分配**：百炼编程套餐的条款禁止自动化调用；cc-switch-zhipu-glm 是第三方中转、明文 HTTP，已从 pi 删除。站主让 themistally-15 测评之后分配，分配到了再走一轮。在那之前不给这三个岗位起新回合（不回会唤醒协调人的信、不开新任务） |
| 七端的岗位（历史：第 36 轮，用户 2026-10-21） | 规划端 Claude Code `claude-opus-5-5` max；审核端 `cc-switch-zhipu-glm/glm-5.3` max（Pi 静默降到 high：模型配置没有 xhigh / max 的映射）；门禁端 `bb/step-5-preview` high；合同端 `cc-switch-zhipu-glm/glm-5.3` high（第 46 轮从 qwen 换过来）；协调人 `token/qwen3.7-plus` high；执行端 `bb/step-5-preview` high。站主列的 `minimax/MiniMax-M3.1-Flash` 不在本机 `pi --list-models` 里（多半是凭据没配），有了再给协调人 |
| pi 模型列表（2026-10-22 第 65 轮） | cc-switch-qianwenai-token-plan/qwen3.8-max、cc-switch-step-fun/step-5-preview、cpa/claude-opus-5-5-high、minimax/MiniMax-M2.7、minimax/MiniMax-M2.7-highspeed、minimax/MiniMax-M3、minimax/MiniMax-M3.1-Flash、token/qwen3.7-plus。不给 hub 用的（名册、备用链、smoke、夹具里都不出现）：`token/…` 与 `cc-switch-qianwenai-token-plan/…`（阿里 Coding Plan、Token Plan 明文禁止自动化脚本、非交互与后台调用，违规封 key、不退款；Token Plan 个人版的数据还会拿去训练）、`cpa/…`（本机 CLIProxyAPI）、`minimax/MiniMax-M2.7` 与 `-highspeed`（10-19 起已路由到 M3.1-Flash，11-18 下线）。`cc-switch-zhipu-glm` 已删（第三方中转、明文 HTTP） |
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
| Node | 24.19.0 | pi 的运行时；TS 工作区的后备运行时（直接跑 `.ts`，类型擦除）与 Vitest 的运行时；自带 `node:sqlite` 为 SQLite 3.53.3 |
| Bun | 1.4.2（固定） | TS 迁移的主运行时与包管理器（站主 2026-10-22 授权安装）。`npm install -g bun@1.4.2` 装在 `~/AppData/Roaming/npm`；`bun.exe` 在 `~/AppData/Roaming/npm/node_modules/bun/bin`，已加进用户 PATH（子进程不经 shell 启动时认不出 `bun.cmd`）。内置 SQLite 3.53.2（`select sqlite_version()` 实测），满足 3.51.3 及以上 |
| TypeScript | 6.0.3 | `ts/` 工作区的类型检查（`tsc --noEmit`，strict、ESM、`erasableSyntaxOnly`）；锁在 `ts/bun.lock` |
| Vitest | 2.1.8 | `ts/` 工作区的唯一测试框架，与 `desktop/web` 同版本 |

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
| 2026-10-21 | 合同端从 `token/qwen3.7-plus` 换到 `cc-switch-zhipu-glm/glm-5.3` high（第 46 轮）：qwen 写合同接连出错，T011 返工五次，T013 四次没过、Scope 路径全少了 `desktop/web/` | 合同端与审核端同为 glm-5.3，少了一层独立性：看一审能不能照样查出合同的问题 |
| 2026-10-22 | TS 迁移第一步：装 Bun 1.4.2（内置 SQLite 3.53.2），新建 `ts/` 工作区（TypeScript 6.0.3、Vitest 2.1.8、@types/node 24.19.0，`bun.lock`）；`bun build --compile` 在本机能打出单文件程序（实测 86 MB） | 升级 Bun 前重跑 `select sqlite_version()` 与契约测试；执行模型与思考级别不因迁移改变 |
| 2026-10-22 | 第 63 轮：站主重配 pi 的提供方。`bb` 改名为 `cc-switch-step-fun`，门禁端、执行端跟着改，smoke 通过；`cc-switch-zhipu-glm` 删除（第三方中转、明文 HTTP，合同端与审核端的提示词与 key 都明文经过它）；`token/qwen3.7-plus` 是百炼编程套餐，条款禁止自动化调用。协调人、合同端、审核端停用，等 themistally-15 测评后的分配；T014 停在门禁端事后检查（bb 不在之后连续作废），不回信 | 分配到了走一轮换岗位、smoke、重发 T014 的门禁端事后检查；账本核对切换之后没有回合用到 cc-switch-zhipu-glm 或 token |
| 2026-10-22 | 第 65 轮：协调人、合同端、审核端换到 MiniMax（协调人 M3.1-Flash high、合同端 M3 high、审核端 M3.1-Flash max），三个新绑定 smoke 通过；门禁端、执行端仍是 step-5-preview。分配由站主授权 themistally-15 测评后定 | 要盯的风险：(1) MiniMax 的数组参数：有用户报告工具调用里的数组参数会被包进一个虚构的 item 键（返回 200 不报错），并行工具结果可能对错号；三个 MiniMax 岗位都是只读，影响应该小，但 read 之类的参数异常、交付块结构怪时先往这里查。smoke 里已见到并行的 write 与 read 先后颠倒。(2) Step Plan 达到限额时“可能切换至其他模型”，峰时扣 2 倍额度：回合审计报“实际模型与要求不一致”先查这个。(3) 头三片切片盯合同返工率（M3 写合同的质量）、一审与终审能不能查出问题、回合作废率、effort_effective（端点不回报，记为未确认）。(4) MiniMax 的 key 若是 M Plan 订阅 key，官方定位是个人交互式，M3 是否在套餐内没写明，由 themistally-15 跟站主确认 |
