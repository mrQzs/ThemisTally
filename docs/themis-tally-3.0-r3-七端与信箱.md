# Themis Tally 3.0 第三轮：七端与信箱

> 状态：**边跑边改**。用户 2026-10-19 的决定：不走 2gate，“直接这一套流程在执行的时候不断迭代完善”。本文是实现依据；每跑完一轮，在 §10 补上发现与改动，正文随之更新。

## 0. 用户决定（2026-10-19）

| # | 决定 | 原话或出处 |
|---|---|---|
| 1 | 七端：规划端 Opus 5.5（max）；合同端 Pi + GLM-5.3（要求 max）；门禁端 claude + Sonnet 5.5（high）；调度代理端 claude + Haiku 5.5（max），兼任协调人；JEV 端（决策 API，按需激活）；审核端 claude + Sonnet 5.5（max）；执行端 Pi + Step-5（high） | 用户贴出的“七端自我迭代架构” |
| 2 | 每个 CLI 都以后台进程调度，不用会话内的子代理 | “使用后端进程来调用claude cli”“其他cli的方式也是后台进程调度” |
| 3 | 进程间通信参考 WoMovie 的信箱协议：以协调人为中心的星型总线，工人只和协调人通信 | 用户贴出的 womovie-mailbox-v2 提示词与改造方案 |
| 4 | 工人不常驻：内核监听信箱，来信时按会话号续接、只跑一个回合，交差后进程退出 | 拍板第 1 项 |
| 5 | 协调人发信驱动流转；内核在投递前按状态机与已有证据强校验，状态只由确定性代码写 | 拍板第 2 项 |
| 6 | GLM-5.3 在配置上仍要求 max；Pi 实际只给 high 时，如实记 `requested: max / effective: high` | 补充决定 |
| 7 | advisor 与插件两个口子：启动参数封堵，加内核事后审计（白名单外的工具调用使本回合作废） | 补充决定 |
| 8 | 不走 2gate，边跑边改 | “不走2gate”“直接这一套流程在执行的时候不断迭代完善” |
| 9 | 自我迭代时参考 `docs/实际问题/` 的七份文档 | “在自我迭代的时候,也可参考 docs\实际问题” |
| 10 | 协调人从 max 降到 high；JEV 由内核在上游交付通过后自动接着跑，不为它单独唤醒协调人（修订第 1、5 项：其余流转仍由协调人发信驱动） | “按你的建议来”（第 4 轮，§10） |

## 1. 与 3.0 四端设计的关系

四端设计：`docs/themis-tally-3.0-四端分层解耦架构.md`（下称 4E）。

**保留：**
- 4E §3.2 不变量 1–3（L177–179）：事实只由内核写；不自我授权、不自我审批；交接只经内核。协调人可以发信推动流程，但每封信都要过内核校验（§5），状态与证据仍只由内核写。4E §3.3 的理由（L184：模型记状态会误记或编造）照样成立。
- 2.10 的执行链路：`prepare` → 后台 `run` → `check --fresh` → `mutate` → `verdict` → `integrate`，门禁 G0–G6 不降。
- oracle 的基线提交（4E §4.7，L334）：`refs/themis/oracle/<task>/v<N>`，不移动任何分支；合同的 `base_sha` 就是这个提交，测试文件列进 `forbidden_paths`。

**改动：**

| 4E 原文 | 本轮 |
|---|---|
| 规划与审核是同一端（规划审核端） | 拆成规划端与审核端两个工人 |
| oracle 由合同端写（§4.7，L329） | 改由门禁端写（战前）；战后门禁端再追加白盒测试与变异清单 |
| 调度代理只把状态写成反馈，可以关闭（§3.3、§4.4.2） | 调度代理端兼任协调人：读信、写下一阶段的任务书、发信推动流转。它仍然不能写状态，所发的信由内核校验后才投递 |
| 每次角色调用都是新会话（§4.6，L321） | 同一工人在同一个阶段任务里续接会话，返工时上下文还在；跨工人、跨任务不共享 |
| 角色交接用内核登记的记录（§6） | 用信件。信件由内核编号、校验、投递并记账；信件就是“登记的记录” |

**本轮不做：**
- 配置中心（r2）的角色枚举仍只有四个（`kit_roles.py:29`）。本轮的工人名册放在 hub 自己的默认配置里（§2），接进配置中心留待后续。
- 4E 的 P2 状态账本、P3 合同端全流程、P5、P6 的完整版。

## 2. 拓扑与名册

```
                 站主（用户）
                     │ 任务 / 回复
                     ▼
   ┌──────────── womovie-c8（协调人 = 调度代理端）────────────┐
   │        │          │          │          │          │      │
planner-  contract-  gate-    audit-     exec-     jev-judge
 opus       glm      sonnet   sonnet     step     （内核代办）
```

| 名字 | 角色 | 载体 | 模型 | 思考 | 工具 | 工作目录 |
|---|---|---|---|---|---|---|
| `womovie-c8` | 调度代理端兼协调人 | claude | `claude-haiku-5-5` | high（§0 第 10 项；原为 max） | Read、Grep、Glob | 任务基线 worktree（只读） |
| `planner-opus` | 规划端 | claude | `claude-opus-5-5` | max | Read、Grep、Glob | 任务基线 worktree（只读） |
| `contract-glm` | 合同端 | pi | `cc-switch-zhipu-glm/glm-5.3` | 要求 max | read、grep、find、ls | 任务基线 worktree（只读） |
| `gate-sonnet` | 门禁端 | claude | `claude-sonnet-5-5` | high | Read、Grep、Glob、Edit、Write、Bash（只允许跑 pytest） | 战前：门禁草稿 worktree；战后：候选 worktree |
| `audit-sonnet` | 审核端 | claude | `claude-sonnet-5-5` | max | Read、Grep、Glob | 一审：门禁草稿 worktree；终审：候选 worktree（只读） |
| `exec-step` | 执行端 | 调度器（pi） | `bb/step-5-preview` | high | 按合同 | 调度器的 attempt worktree |
| `jev-judge` | JEV 端 | 内核代办（决策 API） | `jev-1.13.0` | — | — | — |

- 站主就是用户：最终拍板人，经 `kit_hub.py send` 发任务与回复，经 `kit_hub.py take --as 站主` 收信。
- 名字照用户给的；改名只改名册，不改协议。

## 3. 信箱

### 3.1 目录（`.agent/mailbox/`，Git 忽略）

```
.agent/mailbox/
  inbox/<名字>/new/<msg-id>.md     未读
  inbox/<名字>/cur/<msg-id>.md     已读（内核把信放进某回合的输入时移过来，移动即回执）
  tasks/<task-id>/brief.md         任务书（内核按协调人信里的内容写，旧版本另存 brief.<n>.md）
  tasks/<task-id>/state.md         工人的进度断点（内核按工人的输出写）
  tasks/<task-id>/report.md        工人的交付报告（同上）
  tasks/<task-id>/evidence/        附件
  turns/<名字>/<turn-id>/          每个回合：prompt.md、stream.jsonl、stderr.log、result.json
  agents/<名字>.json               会话号、最近回合、状态
  ledger/events.jsonl              内核的事件账本（只追加）
  ledger/state.json                状态投影（可由账本重建）
  .lock/                           hub 单写者锁（mkdir 加 owner.json，照 ConfigLock，kit_config.py:441）
```

- 只有内核写这个目录。工人看不到它（工作目录是 worktree），也不需要看到。
- 投递用 `publish_new` 的做法（`pi_dispatch.py:573`）：O_EXCL 建临时文件，Windows 上 `os.rename`（目标已存在就失败）、POSIX 上 `os.link`，所以“永不覆盖”。new→cur 是同盘改名。

### 3.2 信件格式

```
---
msg-id: <内核生成：UTC 时间-发信人-随机串>
from: <名字>
to: <名字>
task-id: <阶段任务目录名>
in-reply-to: <msg-id 或 none>
type: <见下>
---
摘要: 一两句话说清做了什么、结论是什么
提交: <分支或提交@前 8 位>（没有写「无」）
验证: 跑了哪些检查、结果如何
偏离: 和任务书或合同不一致的地方及理由（没有写「无」）
需协调人决定: （没有写「无」）
证据: .agent/ 下的相对路径
```

- 正文不超过 40 行；长内容进 `report.md` 或正式产物。
- 工人 → 协调人：`交付 | 返工完成 | 提问 | 阻塞 | 交接 | 进度`。
- 协调人 → 工人：`开工 | 返工 | 通过 | 等待 | 停止`。
- 站主 ↔ 协调人：站主发 `任务 | 回复 | 停止`；协调人发 `汇报 | 提问`。
- 审核端的 `交付` 另带 `结论: 通过 | 返工` 与 `退回: 合同端 | 门禁端 | 执行端 | 规划端`（返工时）。

### 3.3 与 WoMovie 协议的差别：工人不自己调 mail-send

**做法：**
- 内核把新信直接放进本回合的输入，代替 `mail-take`。
- 工人的最后一条消息末尾带一个 JSON 代码块：信件字段、`report`、`state`，以及角色产物，例如合同全文、审核结论。
- 内核解析、校验之后，以这一回合的工人名义投递。

**理由：**
1. 只读的角色（规划、合同、审核、协调人）不需要 shell，工具面更小。
2. 身份由“这一回合是内核为谁启动的”决定，不需要令牌，也就没有冒名的问题。
3. 回合审计（§6.3）不过，这一回合的信件就不投递。不存在“信已经发出、事后才发现越权”的窗口。

**沿用：**
- 心跳由内核按进程存活与回合记录给出；
- 回合结束只有一种合法方式：交出这个 JSON 代码块；
- “同一思路连续失败 3 次就换思路或提问”；
- 正文 40 行上限。

## 4. 阶段与任务目录

主任务号 `T<NNN>` 加阶段后缀，每个阶段一个任务目录（用户的冲突解法 1），后一阶段的任务书只引用前一阶段产物的路径：

| 序 | 阶段任务 | 工人 | 交付物 |
|---|---|---|---|
| 1 | `T001-1-plan` | planner-opus | 概要步骤（report.md） |
| 2 | `T001-2-contract` | contract-glm | 合同 Markdown；内核写入 `.agent/plans/<key>.v<N>.md`，再 `derive-json`、`validate` |
| 3 | `T001-3-gate-pre` | gate-sonnet | 黑盒基准测试（门禁草稿 worktree 里的新文件）；内核跑 `baseline`，做基线提交并锁定 |
| 3j | `T001-3j-jev` | jev-judge | 合同概述的 JEV 判断（题库 `contract-screen`） |
| 4 | `T001-4-audit-pre` | audit-sonnet | 一审结论：通过，或返工给合同端或门禁端 |
| 5 | `T001-5-exec` | exec-step | 调度器的 attempt；内核随后跑 `check --fresh` |
| 6 | `T001-6-gate-post` | gate-sonnet | 白盒边界测试（只增不改）与变异清单；内核运行 |
| 6j | `T001-6j-jev` | jev-judge | 执行概述的 JEV 判断（题库 `report-screen`） |
| 7 | `T001-7-audit-post` | audit-sonnet | 终审结论：通过，或返工给执行端（或回溯到合同端） |

## 5. 状态机与内核校验

内核为每个主任务维护一个阶段记录（`ledger/state.json`），只由内核按事件更新。协调人的每封信在投递前过下表的前置条件；不满足就拒收，并把原因写回给协调人。

| 协调人发的信 | 前置条件（内核核对） |
|---|---|
| `开工` → planner-opus（`-1-plan`） | 站主的 `任务` 已登记 |
| `开工` → contract-glm（`-2-contract`） | 规划端的 `交付` 已被接受 |
| `开工` → gate-sonnet（`-3-gate-pre`） | 合同已写入 `.agent/plans/`，`validate` 通过 |
| `开工` → jev-judge（`-3j-jev`） | 合同端的 `交付` 已被接受。通常不用发：合同交付通过时内核自动跑 JEV（§0 第 10 项），判断和交付信一起送到协调人；6j 同理，在战后门禁通过时自动跑 |
| `开工` → audit-sonnet（`-4-audit-pre`） | 基准测试已做基线提交并锁定：`baseline` 显示测试在基线上失败；合同的 `base_sha` 是基线提交；测试路径在 `forbidden_paths` 里；JEV 启用时已有本阶段的 JEV 记录（无意见也算） |
| `开工` → exec-step（`-5-exec`） | 一审结论为 `通过`；一审之后合同与基线提交都没变 |
| `开工` → gate-sonnet（`-6-gate-post`） | 执行端的 attempt 已结束，内核的 `check --fresh` 全部通过 |
| `开工` → jev-judge（`-6j-jev`） | 战后门禁的白盒测试与变异清单已由内核运行并全部通过 |
| `开工` → audit-sonnet（`-7-audit-post`） | 同上；JEV 启用时已有本阶段的 JEV 记录 |
| `返工` → 执行端 | 存在失败记录：`check --fresh`、白盒测试或变异检查失败，或终审 `返工` 退回执行端 |
| `返工` → 合同端或门禁端 | 一审 `返工` 退回该端，或内核核验失败（合同 `validate` 失败、合同里留着“待确认”标注；基准测试收集失败或在基线上没有失败）；终审退回合同端也算 |
| `返工` → 门禁端（`-6-gate-post`） | 白盒测试或变异检查失败，或终审 `返工` 退回“战后门禁”（白盒测试或变异清单不够） |
| `返工` → 任一工人阶段（站主指定） | 站主 `send --type 回复 --rework <阶段>`：内核记下 `owner_rework`，只放行这一个阶段的一次返工，协调人投出之后作废（第 4 轮） |
| `返工` → 规划端 | 一审连续 3 次没有通过，或终审退回规划端 |
| `返工` → 门禁端（热修补，执行之后） | 执行端报了合同矛盾（`contract_conflicts` 非空），或终审退回门禁端。合同版本已派遣时，内核把它复制成下一版再改 `base_sha`；测试差异写进 `tasks/<T>-3-gate-pre/evidence/hotfix-*.diff`。依赖 3-gate-pre 的一审、执行、战后与终审一并作废：一审重做（只看差异），执行端必须重跑 |
| `通过`（结项） | 终审结论为 `通过`；内核随后 `verdict PASS` 并按授权 `integrate`（本地分支，不推送） |
| `等待`、`停止`、`汇报`、`提问` | 不设前置条件 |

工人的信由内核代发（§3.3），投递前核对三件事：
- 发信人就是这一回合的工人；
- `task-id` 是它被唤醒的阶段任务；
- 回合审计通过。

`交付` 另做这一阶段的核验，例如合同 `validate`、门禁文件都在允许的测试目录内。核验失败照样投递给协调人，但信上附内核的核验结果，阶段记录仍是“未交付”。这样协调人发 `返工` 就有了前置条件。

**短路**：执行之后，内核的 `check --fresh`、白盒测试或变异检查只要有一项没过，协调人只能发 `返工` 给执行端。`开工` → jev-judge 或 audit-sonnet 在内核这一层就过不去。

## 6. 回合：一封信，一个进程

### 6.1 claude 工人（设计阶段实测过的启动方式）

```
claude -p --model <模型> --effort <档位>
  --output-format stream-json --verbose
  --setting-sources project
  --settings '{"autoMemoryEnabled": false, "advisorModel": ""}'
  --strict-mcp-config --disable-slash-commands
  --tools <白名单> [--allowedTools <Bash 规则>]
  --add-dir <主工作区>
  [--permission-mode acceptEdits --disallowedTools "Edit(//<主工作区>/**)" "Write(//<主工作区>/**)"]  # 有 Edit/Write 的工人
  --permission-prompts none
  --append-system-prompt <角色提示词>
  (--session-id <uuid> | --resume <uuid>)  "<本回合输入>"
```

| 开关 | 实测结果（2026-10-19，claude 2.1.302） |
|---|---|
| `--tools Read,Grep,Glob` | init 的 tools 恰好是这三个 |
| `--strict-mcp-config` | 不加载 claude.ai 连接器（Claude Docs 等） |
| `--disable-slash-commands` | 技能为 0 |
| `--setting-sources project` | 不读用户级设置：advisor 不可用，用户装的插件（claude-security）不加载 |
| `"advisorModel": ""` | 单独使用也能让 advisor 不可用（第二道保险） |
| `"autoMemoryEnabled": false` | init 不再报告记忆目录。不关的话，在本仓库 worktree 里跑的工人用的是本项目的记忆目录 |
| `--disallowedTools advisor` | **无效**：advisor 是服务端工具（`server_tool_use`），照样能调 |
| `--append-system-prompt` | 能覆盖 AGENTS.md 的“角色判定”：审核端被问到时，自报“审核端、不派遣、不改文件” |
| `--session-id` + `--resume` | 第二回合答出了第一回合让它记的暗号 |
| 会话文件位置 | `~/.claude/projects/<按工作目录换算>/<会话号>.jsonl`，按 worktree 路径存放，不混进规划端的用量 |
| 会话文件的 `effort` 字段 | 每条 assistant 记录都带 `effort` 与 `perTurnEffort`：可以读出实际生效的档位 |
| `--append-system-prompt-file` | 文件内容进了系统提示（角色提示词不占命令行） |
| `--allowedTools "Bash(python -m pytest:*)"` 加 `--permission-prompts none` | pytest 能跑，`del` 被拒；`git status` 这类只读命令被内置规则放行 |
| 默认权限模式 + `--permission-prompts none`（新环境，claude 2.1.303） | 工作目录里的 Write 也被拒（“没有人能答权限提示”）；工作目录之外的 Read 被拒。门禁端按旧的启动方式根本写不了测试 |
| `--add-dir <主工作区>` | 主工作区可读：合同（`.agent/plans/`）、信箱、长输入文件、执行证据都只在主工作区里，worktree 里没有 |
| `--permission-mode acceptEdits` + `--disallowedTools "Write(//c/…/主工作区/**)"` | 工作目录里的写入放行，主工作区的写入被拒（“denied by your permission settings”）。绝对路径写成 `//` 加小写盘符、正斜杠 |
| `--tools` 等变长参数 | 后面紧跟非选项参数会被吞掉（`--disallowedTools advisor "$P"` 把提示词当成了工具名）。拼命令时让它们后面紧跟另一个选项 |

### 6.2 pi 工人

```
pi --provider <p> --model <m> --thinking <档位> --mode json
   --no-approve --no-extensions --no-skills --no-prompt-templates --no-themes --no-context-files
   --tools <白名单> --append-system-prompt <角色提示词>
   --session-dir .agent/mailbox/sessions/<名字> --session-id <阶段任务>-<名字>  "<本回合输入>"
```

- 实测：同一个 `--session-id` 的第二回合答出了第一回合的暗号。第一次用某个会话号时，stderr 有一行“creating a new session”，属于正常现象。
- 实际档位读事件里 assistant 消息的 `thinkingLevel`。GLM-5.3 要求 max，生效 high：Pi 的 `clampThinkingLevel` 只在模型配置写了 xhigh 或 max 的映射时才开放这两档。

### 6.3 回合审计（内核，确定性）

回合结束后，内核读**自己截下的事件流**（`turns/<名字>/<turn-id>/stream.jsonl`）。会话文件由 CLI 写，有写权限的工人能改动它，所以以内核截下的流为准，会话文件只用来补读档位。逐项核对：
- 每个 `tool_use` **和** `server_tool_use` 的名字都在白名单里（advisor 的调用是 `server_tool_use`）。
- init 的 tools 与白名单一致，没有 MCP 服务器，没有记忆目录，模型与要求一致。
- 档位：claude 读会话文件的 `effort`，pi 读 `thinkingLevel`。记下 `requested` 与 `effective`，不一致时标出来，不作废。

任何一项违规，本回合的信件一律不投递，内核另发一封 `阻塞` 给协调人，附违规明细。

例外（第 4 轮）：白名单之外的**客户端**调用，如果它的 `tool_result` 是 CLI 当场拒绝（`No such tool available`），这次调用没有任何效果，只记进回合的 `warnings`，不作废回合。T001 的终审为一次被拒的 Bash 白白作废了 16 分钟。服务端工具（advisor）没有这个例外。

### 6.4 输出与重试

- 工人最后一条消息里**最后一个** ```json 代码块就是输出。
- 解析或校验不过时，内核续接同一会话再给一次机会，附上错误原因。第二次仍不过，就代发 `阻塞`。
- **模型接口报错不算工人的错，也不重试**：claude 把接口错误合成为一条 `<synthetic>` 消息（带 `error`、`api_error_status`），结果的 `terminal_reason` 是 `api_error`；pi 的最后一条 assistant 消息 `stopReason` 为 `error`。内核把它记进回合的 `api_error`，阶段标为 failed，主任务转 blocked，`阻塞` 信直接给站主（协调人也会撞上同样的错）。站主处理好环境后发 `回复` 恢复。
- **返工时干净重启**（用户评审建议 2，`docs/优化.md`）：唤醒工人的信里有 `返工` 时，内核不续接旧会话，换一个新会话，输入只有任务书、state 与这封返工信。旧会话里失败的历史不再带着走。同一阶段里的重试仍然续接。

### 6.5 执行端与 JEV 端由内核代办

- **exec-step**：收到 `开工` 后，内核依次跑：
  1. `pi_dispatch.py prepare <key>`；
  2. `run <run-dir>`（hub 本身就在后台，run 在 hub 里同步等待）；
  3. `check <run-dir> --fresh`。

  然后从执行报告与检查结果生成 `交付`：
  - 摘要：报告；
  - 验证：自检与内核检查；
  - 偏离：`interpretations` 与 `limitations`；
  - 需协调人决定：`contract_conflicts` 与 `unresolved_questions`。
- **jev-judge**：收到 `开工` 后，内核取被评对象那封信正文的四个字段（摘要、验证、偏离、需协调人决定），用对应题库调用决策 API。调用以 shadow 语义进行，只作审核端的参考，门禁永远不读。结果写进阶段任务的 `report.md`，并回信给协调人。

## 7. 门禁与短路

**战前（`-3-gate-pre`）：**
1. 门禁端在门禁草稿 worktree（任务基线的分离 HEAD）里新增测试文件。
2. 内核核对：改动只在合同允许的测试路径里，而且只是新增；再跑 `pytest --collect-only`，收集失败（语法错误、模块级导入失败、没有用例）直接拒收。否则这种测试在基线上也会“失败”，被当成合格的基准锁进禁改路径（空心基线）。
3. 内核在这个 worktree 里提交，更新 `refs/themis/oracle/<T>/v<N>`，不移动任何分支。
4. 内核按 `baseline` 的做法在基线上跑这些测试：它们必须失败。
5. 内核把合同的 `base_sha` 改成这个提交，测试路径加进 `forbidden_paths`，重新 `validate`。合同版本号不变：此时还没有派遣。

**战后（`-6-gate-post`）：**
1. 内核的 `check --fresh` 先跑；不过就短路。
2. 门禁端在候选 worktree 里只增不改：追加白盒测试与变异清单（`mutate --spec` 的格式）。
3. 内核在候选上跑白盒测试（`run_supervised`：Job Object 监督，输出进 `evidence/whitebox-*.log`），并跑 `mutate --tree`。
4. **变异的判定读 `mutations.json`，不看退出码**：`mutate --tree` 在变异漏网时退出码也是 0（`pi_dispatch.py` 的 `cmd_mutate`）。意外漏网、没生效（skipped）或出错（error）都不通过，至少要抓住一条。门禁端声明 `equivalent` 的漏网算预期内，终审逐条复核。
5. 任何一项失败都短路：只能 `返工` 给执行端。

**执行端改了基准测试**：调度器的范围门禁 G2 会直接拦下（`forbidden_paths`），内核的检查也会失败。用户的冲突解法 3 要求的 `git diff <基准测试提交> -- <测试路径>` 也由内核在战后先跑一遍。

## 8. JEV

- **合同概述**：新题库 `plugins/decisions/questions/contract-screen.json`。问题包括：
  - 与规划的方向是否一致；
  - 是否扩大范围；
  - 验收能否机械检查；
  - 风险等级。
- **执行概述**：沿用 `report-screen`（`decisions.py` 的题库格式，`:247–275`）。
- 题库改动后用 `decisions.py --write-lock plugins/decisions` 重算内容锁。
- 生效方式：hub 自己构造 shadow 设置（与 `probe` 同法，`decisions.py:903`），不改 `dispatch.config.json` 的 `decisions` 段。全局的 off、shadow、on 只管调度器自己的三处提问。

## 9. 提示词模板

用户给出的两套模板（模板 A：工人；模板 B：协调人）收在 `scripts/hub/worker.md` 与 `scripts/hub/coordinator.md`。按 §3.3 改了三处：
- 不调用 mail-take / mail-send；
- 回合结束交出 JSON 代码块；
- 产物写在 JSON 里，由内核落盘。

内核渲染时代入名字、角色、阶段任务、允许路径与输出格式，并把模板的 sha256 记进每个回合的 `result.json`。

工人模板里各角色的职责段用 `<!-- 角色:x -->…<!-- /角色 -->` 标出，渲染时只保留当前角色那一段（用户评审建议 4）：执行端看不到审核端的规则，省 token，也少“越界操心”。

## 10. 迭代记录

### 第 0 轮：设计阶段实测（2026-10-19）
- 后台 `claude -p`：Sonnet 5.5（high、max）与 Haiku 5.5（max）都能跑，模型由事件流与用量确认。init 不报告档位，会话文件里有。
- 隔离：见 §6.1 的实测表。advisor 只能靠“不读用户级设置”或“清空 advisorModel”关掉；`--disallowedTools` 无效。
- Pi：GLM-5.3 high 与 Step-5 high 的 smoke 两步都过。GLM 要求 max 时生效 high（被静默降档，stderr 无提示）。补测一道推理题，GLM 返回了思考过程，答案正确。
- JEV：`doctor --probe-decisions` 一次最小请求通过（358 毫秒，`jev-1.13.0`）。

### 第 1 轮：内核最小可用版（2026-10-19）
- `scripts/kit_hub.py`：信箱、信件、状态机校验、回合启动与审计、执行端与 JEV 端的内核代办、结项（verdict PASS 与 integrate）。
- 提示词模板 `scripts/hub/worker.md`、`scripts/hub/coordinator.md`；合同筛查题库 `scripts/hub/questions/contract-screen.json`（放在 hub 自己的目录，不动决策插件的锁）。
- `tests/test_kit_hub.py` 32 条。变异检查 22 个（状态机每一行前置条件、审计的每一项、投递不覆盖、下游作废的传递闭包）全部抓住；第一次只抓住 21 个，漏掉的“下游作废只看直接依赖”补了断言。

### 第 2 轮：门禁热修补（2026-10-19，T001 运行期间，未提交）
- `hotfix_reason`、`bump_contract_version`，`accept_gate_pre` 在合同已派遣时出新版本并留下测试差异；模板补热修补的流程。
- 回合记录里的 `hub_sha256` 改为进程载入时算一次：运行中改了源文件，记录里的仍是正在跑的那一份。
- 测试 36 条；变异 28 个全部抓住（新增：热修补不认执行端举证、不认终审退回门禁端、不出新版本、不留测试差异、不记旧基线、门禁可以改别的文件）。
- T001 合入之前不往 `themis-3.0` 提交：基准测试的基线提交以 T001 的基线为父，`integrate` 是 ff-only。

### 第 3 轮：换到新环境（2026-10-19）
- 旧机器上 T001 停在规划阶段：所有 claude 后台进程都收到 `403 oauth_not_allowed_for_organization`（“Your organization has disabled Claude subscription access for Claude Code”），规划端已用掉约 5 分钟、2.27 美元（按标价）。内核却报成“最后一条消息里没有 json 代码块”，还白白重试了一次。
- 新环境核验：claude 2.1.303 登录有效，Haiku max、Sonnet high/max、Opus max 按 hub 的启动方式都能答；Pi 的 Step 现在登记为 `step/step-5-preview`（旧机器上是 `bb`），smoke 两步都过，推理题有思考内容、答案正确；GLM-5.3 要求 max 仍生效 high；JEV 的 key 在 Windows 凭据管理器里，`doctor --probe-decisions` 通过（202 毫秒，`jev-1.13.0`）。
- 新环境的坑：仓库是经压缩包搬过来的，21 个中文文件名被按 GBK→CP437 弄乱（16 个已跟踪的文件内容与 HEAD 逐字节相同），已按原名改回；控制台代码页是 cp1252，`kit_hub.py --help` 输出中文时抛错。
- 修补：
  - 接口报错单独识别，不重试，直接给站主（§6.4）；
  - claude 工人加 `--add-dir <主工作区>`；有 Edit/Write 的工人加 `acceptEdits` 与主工作区的拒写规则（§6.1）。不修的话，门禁端写不了测试，审核端也读不到合同与证据；
  - 执行端的 provider 只在名册里写一处，合同的 executor 行与核对都从名册来；
  - `main()` 把标准输入、输出改成 UTF-8，与其他 kit 脚本一致（站主用管道 `send` 中文回复时，cp1252 会把它读成乱码）。
- 测试 44 条；新代码的变异 17 个全部抓住（接口报错的识别与“报错后又恢复”的复位、不重试、直接给站主、`--add-dir`、`acceptEdits`、拒写规则与它的路径写法、provider 的核对、UTF-8 的输入与输出）。
- T001 在新机器上恢复：站主发 `回复`（`20261019T032952415555Z-owner-7e0d00`），请协调人给规划端发 `返工`；旧 worktree 的登记已 `git worktree prune`，内核按需重建。

### 第 4 轮：按 `docs/实际问题/` 与 T001 的实测加固（2026-10-19，T001 运行期间在隔离 worktree 里做）
- 用户让迭代时参考 `docs/实际问题/` 的七份文档。逐条分诊之后，只做改动小、收益明确、不破不变量的几项：
  - 让 JEV 一票否决或指挥下游：不采纳，违反 shadow 语义；
  - 小范围扩权免一审：不采纳，违反热修补不免一审；
  - 对执行端遮蔽测试源码：不采纳，执行端要跑合同检查自检。
- **缺陷**：战后门禁只看 `mutate` 的退出码，变异漏网也算通过。改为读记录判定（§7）。
- **合同里的未决标注**：T001 的合同把 4 个待站主确认的问题写成 13 处“【待站主确认】”留在正文里。现在内核拒收这类合同，合同端要先发 `提问`；协调人模板写明：站主没回复之前，不开工依赖答案的阶段。
- **站主指定返工**：此前一审之前站主没办法让合同改版（只有审核退回或核验失败才放行）。新增 `send --rework`（§5）。
- **审核端**：
  - 终审退回合同端原来是死路（前置条件只看一审的退回），已打通；新增退回目标“战后门禁”。
  - 一审不能退回执行端或战后门禁（还没有执行）。
  - 返工必须写“阻塞项”。结论进 `audit_history`，不随下游作废清掉；下一轮同一阶段的审核拿到上一轮的阻塞项，只复核它们和新改动（复审封板）。
  - `report.md`、`brief.md` 覆盖前都留档成 `report.N.md`、`brief.N.md`。
  - 一审报告要有“DoD → 测试 → 断言”映射，内核核对每个 DoD 的 id 都在。
  - 终审先读源码再看绿灯，复核每条等价声明。
- **JEV**：报告按题库阈值标出“留意”（≥ review）与“需关注”（≥ action，或风险分 ≥ severity_action），附上那一档的判据，不再只有四个数。执行 JEV 的输入补上客观指纹：改动的文件、`review_hints`（断言增删）、白盒测试的退出码、变异计数。仍是 shadow，门禁不读。
- **门禁端**：战前先跑 `--collect-only`；内核跑 pytest 时不写字节码与缓存。
- **站主同意的两项**（“按你的建议来”）：
  - 协调人降到 high。它在 T001 里每回合 1–4.5 分钟，大头是 max 档的思考输出。
  - JEV 由内核自动接着跑：合同交付通过就跑 3j，战后门禁通过就跑 6j。判断和交付信一起进协调人信箱，协调人一个回合处理。T001 里 04:15→04:16 那个协调人回合只是在等 JEV。
- **缺陷（T001 的执行阶段撞上）**：内核从 attempt 的 `state.json` 读 `status` 键，调度器写的是 `state` 键（`pi_dispatch.get_state`），读出来恒为空，执行阶段永远判不过。T001 的两个 attempt 文档改动与自检都通过，却都被短路；第一次协调人当成执行报告的问题去返工，白跑了一个 attempt。第二次协调人查出了原因，报给站主。修法：改用 `pd.get_state`。
- **站主命令 `exec-recheck <主任务>`**：对最近一次 attempt 重新核验（`check --fresh`、范围、状态），不重跑执行端、不占新的尝试次数。只在执行阶段判为失败、attempt 目录还在时可用；拿 hub 的运行锁，结果照常作为执行端的交付信送给协调人。内核中途停下、或判定逻辑修过之后，用它接着走。T001 用它救回了 attempt-002，合同的尝试次数（2）已经用完。
- **结项（T001 第一次结项卡住）**：候选以门禁的基准测试提交为基线，这个提交不在 `themis-3.0` 上。`integrate` 于是只挑“基线→候选”的改动，在当前末端上重跑合同检查时找不到基准测试，什么都没落地。修法：结项时如果基准测试提交不在当前分支的历史里，先 `git merge --ff-only` 把它带上（它是一审审过、锁定的验收测试），再 integrate；分叉了不能 ff 就如实报告，不 integrate。结项可以重试：attempt 已经是 PASS 就不再记结论。
- **代价**：基准测试随结项进了仓库。它们断言 T001 改过的文档里有哪些句子。以后再改这两份文档的任务，合同里要允许它同步改 `tests/test_gate_t001_*.py`。
- **变异记录放进信箱**：`mutate --out` 原来指向系统临时目录，终审读不到（T001 终审的意见）。现在放在 `tasks/<T>-6-gate-post/evidence/mutate-*`，终审的本回合输入里列出它与白盒测试输出的路径。
- 测试 63 条；本轮新代码的变异 46 个全部抓住。第一次漏了两个：“交付时不留档旧报告”和“`tail_file` 整份读”，都补了断言。
- 正在跑的 T001 用的仍是第 3 轮的代码（hub 进程启动时载入）。它的战后门禁由规划端手工核对 `mutations.json`。本轮改动在 T001 合入后带回主工作区。

## 11. 已知缺口与下一步

**用户评审（`docs/优化.md`）的四条建议：**

| # | 建议 | 处理 |
|---|---|---|
| 1 | 基准测试本身有错时的“门禁热修补”：执行端举证后，协调人直接唤醒门禁端修测试，免去重走合同与一审 | **已做，按推荐（用户 2026-10-19：“按你的推荐来”）**：不免掉一审，但一审只看测试差异；合同出新版本；执行端必须重跑（§5 的热修补一行）。这样门禁端没法悄悄把测试改得迁就错误的实现：差异要过审核端 |
| 2 | 返工时干净重启会话 | 已做（§6.4） |
| 3 | 流水线分级（L1 极速 / L2 标准 / L3 严苛） | **按推荐暂缓（用户 2026-10-19）**：先跑完 T001，量出各阶段的耗时，再定 L1 能跳过哪些阶段 |
| 4 | 模板按角色裁剪 | 已做（§9） |

- 调度器的摘要只核对提供商回报的档位（`pi_dispatch.py:3186`），看不出 Pi 的静默降档；本轮在 hub 的回合审计里补读 `thinkingLevel`。调度器本身的修补另做。
- 执行端的返工：本轮按调度器现有做法，开新 attempt，会话不续接；返工要点经合同新版本传达。要不要让执行端续接会话，跑过再定。
- 并发：本轮 hub 串行处理，一次只跑一个回合；并行留到后续迭代。
- 配置中心：工人名册与模型暂不进 `dispatch.config.json`。
- 桌面端：任务 1 只改文档，界面接入不在本轮。
- **站主排定的第二个任务（2026-10-19）**：T001 结项之后，按 `docs/Themis Tally UI设计/` 实现界面。
- **以后再做**：
  - 规划报告的路径与行号由内核核对；
  - 合同端把任务退回规划端的路由；
  - 执行端返工次数的上限；
  - 换异构模型（换模型要站主同意）；
  - 单条用例的超时（要装 pytest-timeout）。
- 插件仍会加载（`--setting-sources project` 只挡住用户级设置里的插件；新环境里 init 仍报告 3 个插件）。插件没有在白名单里的工具，内核的事后审计照样拦得住调用。
