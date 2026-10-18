---
name: dispatch-pi
description: 用固定调度工具把已审阅的任务合同派遣给 Pi 执行器：校验合同、建立独立 worktree、预检模型与参数、在时限内运行并收集证据，然后转入 review-pi 验收。用于“派遣/执行合同”“交给 Pi 跑”，或 plan-task 完成后用户明确要求执行时。
argument-hint: "<task-id>.vN"
---

# 派遣任务合同

请求派遣的计划标识（原始文本，先校验再使用）：$ARGUMENTS

（上一行在 Claude Code 中会替换为调用参数；在 Codex 中保持原样，此时参数就是用户调用本技能时附带的文字。）

## 规则

- 计划标识必须完整匹配 `^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]*$`，否则停止。校验通过后，才能把它代入下面命令中的 `<plan-key>`；调度工具会再校验一次。
- 派遣会把合同与相关代码发给执行模型提供商，并产生费用。只有用户在本对话中明确要求执行（或直接调用本技能）时才继续。
- 只通过 `bash scripts/dispatch-pi.sh <子命令>`（等同 `python scripts/pi_dispatch.py`）操作。不要手写 pi 命令，不要改脚本绕过预检，不要删除 `claim/`，不要编辑 `.agent/runs/` 中的任何文件。
- 不要自行更换模型、provider 或思考级别（默认 Step，`high`）。需要更换时，先征得用户同意，再出新版本合同。

## 步骤

1. **校验合同**：`bash scripts/dispatch-pi.sh validate <plan-key>`（也可以传 `.agent/plans/<plan-key>.md` 的路径）。
   - 有 ERROR：停止，回到 plan-task。
   - 有 WARN：逐条判断。尤其注意：
     - “基线中没有 AGENTS.md”；
     - base_sha 不是当前 HEAD；
     - “含不可见格式字符”，通常是转义序列被写成了实际字符，先修正。
1a. **确认探针能区分修复前后**：`bash scripts/dispatch-pi.sh baseline <plan-key>`。
   - 在基线副本上运行全部检查，不创建 attempt，也不计入预算。
   - 用来证明修复的探针应当在基线上失败。在合同 JSON 的检查项中写 `"expect_on_base": "fail"`（Markdown 写“基线应失败”），工具会核对这一点。
   - 在基线上就已通过的探针区分不了修复前后，先改写探针再派遣。
2. **确认前提**：
   - `.agent/environment.md` 存在，且记录的 pi 版本和执行模型与现在一致。否则先运行 check-pi-env。
   - `.agent/runs/` 已被 .gitignore 忽略。
3. **准备**：`bash scripts/dispatch-pi.sh prepare <plan-key>`。输出中有 attempt 目录（下称 `<run-dir>`）与 worktree 路径。
   - 按角色写的合同（`role:execution`，3.0 第二轮）：同一版本第一次 prepare 时把当前绑定记进 `.agent/runs/<task>/binding-v<N>.json`，之后的 attempt 沿用记录；绑定改了或被删了只打 NOTE，不挡。
     - 首次建立记录时：没有绑定、绑定无效或与 manual 冲突退出 2，绑定到本轮未接通的适配器退出 3；
     - 任何一次：记录损坏、经过链接，或冻结的合同 JSON 与记录里的哈希不符（已派遣版本的 JSON 被改过；只改 Markdown 说明不触发）退出 4；
     - 见 [troubleshooting.md](troubleshooting.md)。
   - 合同有 `setup` 时，依赖在这一步准备。
   - 合同没有 `setup`、但测试需要依赖时，出新版本合同补上 `setup`。不要在 worktree 里手工改源码。
   - `PREPARE_FAILED`：读 `<run-dir>/setup/*.log` 修正原因，再重新 prepare。失败的 attempt 不计入次数。
4. **运行（必须在后台）**：`bash scripts/dispatch-pi.sh run <run-dir>`。单轮时限可能长达半小时以上，超过任何前台命令的时限。先告诉用户任务已启动、最长运行多久。
   - **Claude Code**：用 Bash 工具的 `run_in_background: true` 运行，然后等完成通知，不要用 sleep 轮询。
     - 非交互模式（`claude -p`）下，后台命令会随会话结束被终止。这种情况改用前台运行并给足 timeout，或在 Claude Code 之外运行。
   - **Codex**：
     - 在后台终端中运行，或请用户在另一个终端运行。
     - 然后反复运行 `bash scripts/dispatch-pi.sh wait <run-dir>`：它最多阻塞 9 分钟（可用 `--timeout` 调整）；attempt 结束时退出 0，仍在运行时退出 3 并打印进度。在 PowerShell 中后面加 `; exit $LASTEXITCODE`，否则退出码 3 可能显示成 1。
     - `run` 要写仓库之外的 worktree 与 Git 元数据，还要联网调用执行模型。`workspace-write` 沙箱中 `.git` 是只读的，所以要按提示批准它在沙箱外运行。`prepare`、`check`、`baseline`、`mutate`、`verdict`、`branch`、`cleanup`、`collect` 同样如此；`smoke` 在系统临时目录中运行并联网，也要在沙箱外运行。
   - 运行中可以用 `status <task-id>` 查看进度；决策模式开着时加 `--assess`（2.6.0）让决策模型判断一次运行健康（推进 / 被挡 / 打转 / 完成，建议 keep_waiting / prepare_next_contract / collect）。Codex 的 `wait` 加 `--assess` 则每 60 秒判断一次。代码先算没有新事件多久、尾部是否重复，静默超过 180 秒时事实优先于模型；建议只用来决定要不要提前准备下一版合同，**运行永远不会被它停止**。
5. **读摘要**：完成后先读 `<run-dir>/summary.md`，不要把整个 events.jsonl 读进上下文。
6. **按结果分流**：

| 输出 / 状态 | 含义 | 下一步 |
|---|---|---|
| `PREFLIGHT …` 且退出码 3 | 预检失败：参数、思考级别、工具名、模型不在列表、凭据未就绪 | 按 [troubleshooting.md](troubleshooting.md) 修正环境后，再对同一 `<run-dir>` 运行 run（attempt 仍是 PREPARED，不计次数） |
| `BUDGET_EXCEEDED` | 次数或累计时长已达合同上限 | 停止，向用户报告，按 ESCALATE 处理 |
| `NEEDS_REVIEW` | 证据已收集（执行器可能成功，也可能自述失败） | 用 review-pi 验收 `<run-dir>` |
| `TIMEOUT` / `CANCELLED` | 被时限或中断终止，证据保留 | 用 review-pi 判断剩余工作与下一步 |
| `INFRA_FAILURE` | 模型没有产生任何回复，或证据收集失败 | 读 `stderr.log` 与 `preflight/`，修正后重新 prepare |

7. **同一前提反复失败时不要重复派遣。** 把原因分成环境、合同、能力三类，再决定下一步。

## 决策模型（2.6.0）

`dispatch.config.json` 的 `decisions.mode` 为 shadow / on 时，调度器在收集证据（报告筛查）、变异检查（等价判断）与 `--assess`（运行健康）三处向决策模型提问。规则来自 hermes-jev-skills 在真实机队上的教训：

- **先 shadow**：付全价、记全日志、不改任何输出；跑两三轮后 `decisions replay` 对照 verdict 与复审记录，分得开的问题再开 on。没人会复审自己认为已经对的策略，所以复审要发生在策略还不起作用的时候。
- **日志安静证明不了功能在跑**：用 `doctor` 看生效的模式与原因；配置是 on、实际 off 的四种原因（标记文件、插件未启用、权限缺失、插件目录缺失）doctor 都会写出来。
- **在它真正运行的地方验证**：`doctor --probe-decisions`（要用户批准）从规划端会话发一次最小请求；通过的单元测试证明不了这个会话里环境变量可见。
- **按时钟不按条数**：每条命令的决策调用总时长有上限（`budget_seconds`，默认 20 秒），到点后剩下的都是“无意见”，命令照常完成。
- **一切 fail-open，门禁不读它**：无 key、超时、限流、畸形或自相矛盾的回复都记为“无意见”；G0–G6、verdict、变异计数、退出码与它无关。标记文件 `.agent/DECISIONS_OFF` 一票否决（给内容不能出机器的仓库）。
- **只发脱敏后的相关片段**：凭据只认环境变量名（环境变量没有时问凭据库，2.7.0）；看起来含凭据的片段整段不发；记录里不存 state 原文。
- **开关都走配置管理器**：`bash scripts/dispatch-pi.sh config decisions shadow|on|off`、`config decisions marker on|off`（标记文件一票否决）、`config secret set <环境变量名>`（用户在一次性本机网页里粘贴）。

## 并行批次

只有在接口稳定、范围不重叠、基线明确时，才并行派遣多个任务。每个任务有自己的 attempt 与 worktree。实机上，同一基线上 3–4 个任务并行运行良好。按批次操作：

1. **成批规划**：
   - 写好本批所有合同，逐个 validate 与 baseline；
   - 各合同的 allowed 文件互不重叠，同一文件的任务放到后续批次；
   - 本批所有合同用同一个 base_sha。
2. **成批准备**：逐个 prepare。
   - prepare 会提示与其他未集成 attempt 的范围重叠（WARN），遇到就调整批次。
   - prepare 也会提示当前有多少 attempt 正在运行。
3. **并行运行**：每个 run 各自一个后台命令。
4. **运行中查看进度**：`status` 对运行中的 attempt 显示 `live:<已完成的工具调用次数>t <已用秒数>`。上次工具调用之后的消息增量达到 6000 个时，另外提示“长时间没有工具调用”（按 45 次实机运行标定：正常运行最长的一段在 4200 个以内）：执行器在长时间思考或输出，可能来不及在时限内完成。运行中无法干预，但可以据此提前准备收尾方式或下一版合同。
5. **运行期间不改主工作区**：
   - 调度器在运行前后比对主工作区。规划路径（默认 `.agent/plans/**`、`.agent/reviews/**`、`.agent/design/**`、`.agent/*.md`，可用 `planner_paths` 配置）的变化只记为备注。
   - 合并、提交、编辑源码都会出现在“复审需要关注”中。
   - 下一批的合同与复审记录可以先写；合并等本批全部结束后再做。
6. **全部结束后逐个复审**，然后集成：
   - 2.8.0 起逐个 `bash scripts/dispatch-pi.sh integrate <run-dir>`（合同 integration 要有 `merge`）：每个都在当前末端上验证后才快进，后一个的末端就是前一个落地后的提交；候选之间冲突时停在预演合并，什么也不落地。下面是手工集成的做法：
   - HEAD 仍是基线时，第一个候选可以 `git merge --ff-only`；按「先提交合同再派遣」的流程 HEAD 通常已经比基线多了合同提交，这时每个候选都用 `git cherry-pick`（`branch` 会按当前 HEAD 打印合适的命令）；
   - 其余候选同样 `git cherry-pick`（它们的父提交是同一基线）；
   - `mark INTEGRATED --ref` 记录实际集成的提交。
7. **在组合结果上重跑全量测试**，并写进执行记录，然后以新 HEAD 作为下一批的基线。用 integrate 时每次落地前都已在当时的末端上跑过合同检查（合同检查含全量时就是这一步）；手工集成时照旧单独跑。

`status` 可以查看运行中 attempt 的进度（已完成的工具调用次数与已用时间）。参数可以是 task-id、task-id.vN、task-id/attempt-NNN 或 attempt 路径。

## 调度器异常退出后

如果 `status` 显示 attempt 停在 RUNNING、COLLECTING，或者已领取（有 `claim/`）却仍是 PREPARED：

1. 确认没有残留的 pi 进程。Windows 上调度器被强制结束时，Job Object 会连同 Pi 一起回收；Linux 与 macOS 上可能有残留。
2. 运行 `bash scripts/dispatch-pi.sh collect <run-dir> --recover`，补做证据收集。恢复的证据可能不完整，只能用于判断，不能直接作为 PASS 依据。
3. 停在 PREPARING（prepare 中途崩溃）时，用 `mark <run-dir> ABANDONED --force --reason …` 放弃，再重新 prepare。

同一 task 的领取由任务锁串行化：提示“任务锁被占用”时，说明另一个 run 正在领取，稍后重试；长时间不释放才按提示处理。
