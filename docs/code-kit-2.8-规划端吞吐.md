# Code-Kit 2.8 设计说明：规划端吞吐与两处保护缺口

状态：2.8.0 已做完（2026-10-15）。

## 1. 为什么做

2026-10-14 的评估（用户回复“按你的建议来”）：执行端已经稳定，KitExperiment 最近 14 轮里 13 轮首轮 PASS；每轮的成本主要在规划端的手工步骤。另有两处保护缺口是 2.6/2.7 漏下的。本版只做这两类；CI、安装与更新、v2 去留、第二种执行 CLI 各自另立方向。

以 serve-loop 一轮为例，规划端每轮手工做的事：

- **集成**：`branch` → 在主工作区 `git cherry-pick` → 另建干净 worktree 跑全量 → `mark INTEGRATED --ref <手抄的提交号>` → `cleanup`，五六条命令。cherry-pick 碰到主工作区里有本地改动的文件时，会停在 sequencer 中间（ledger-cli 实机）。
- **变异**：同一批变异写两份清单，一份跑 oracle 加执行器测试，一份只跑执行器测试，32 条各跑两轮。第二轮漏掉 20 条，其中 18 条是“合同留给 oracle 的规则”，只能逐条手判。
- **复审记录**：基线、候选树、模型、用时、检查结果、变异计数、漏掉的条目、执行器自述、摘要里的关注项，全部从证据目录手抄。规划端临时目录里每轮都有一份 `attempt-001-*-draft.md`。
- **指标**：metrics 只按 verdict 记结果。8 个“未通过”的任务里，7 个其实已经由返工或规划端补完后集成（SUPERSEDED，带提交号），只有 1 个放弃。执行费用 45 轮全是 unknown：Step 不报价格，但 token 数都有。

## 2. 现状（2026-10-14 核对）

- **branch**：`cmd_branch` 要求合同的 `authorization.integration` 含 `local_branch`。它建 `pi/<task>-v<N>-a<NNN>`（父提交是基线），并打印 `merge --ff-only` 或 `cherry-pick` 的提示；之后的落地、全量、`mark`、`cleanup` 都靠手工。
- **授权与做法不一致**：KitExperiment 合同的 `integration` 只写了 `local_branch`。规划端落到 master，凭的是用户 2026-09-23 的长期授权，工具看不到这一层；而 review-pi 第 9 步写的是“只做合同 integration 中已授权的动作”。
- **检查**：`check --fresh` 在“基线 + 候选补丁 + setup”的临时 worktree 上跑，`baseline` 在基线上跑。没有命令在“当前分支末端 + 候选”上跑。
- **mutate**：一份清单只有一条 `command`。`--check-anchors` 只报出现次数，不说锚点该往哪里改。
- **verdict**：只核对复审记录的 `Verdict:` 行，不检查 `【待填` 占位。
- **metrics**：最终结果只看 verdict（PASS / 豁免 / 未通过），不读 `state.json` 里的 INTEGRATED / SUPERSEDED / ABANDONED 与 ref。费用只用 Pi 自己的估算（`events-summary.json` 的 `cost`）；`usage` 里的 input / output / cacheRead / cacheWrite 没有用上。
- **保护路径**：`PROTECTED_PATTERNS` 有 `scripts/pi_dispatch.py` 和 `scripts/dispatch-pi.sh`，没有 2.6/2.7 起调度器实际加载的文件：`scripts/kit_config.py`；`scripts/codekit/` 下的 `__init__.py`、`decisions.py`、`secrets.py`、`planner.py`、`planner_protocol.py`、`protocols.py`；`plugins/decisions/`。KitExperiment 不受影响，因为 kit 不在它的仓库里。但如果目标仓库把 kit 复制进了 `scripts/`，合同只要写一个 `scripts/**` 范围，执行器就能改这些文件，而 G2 不报。
- **问题清单**：`decisions.load_batteries` 直接读问题清单 JSON。`plugins/decisions/lock.json` 记着每份清单的 sha256，但运行时没人核对。生成锁的脚本只在规划端的临时目录里（`gen_decisions_plugin.py`），kit 里没有。

## 3. 方案草图

### 3.1 `integrate <run-dir>`：验证后落地

1. **前置**：最新 verdict 是 PASS 或 ACCEPTED_WITH_EXCEPTION；G0 发布门禁与输入一致性同 `branch`；授权见第 6 节问题 1；主工作区的 HEAD 在某个分支上（不是游离 HEAD），记下分支末端 H。
2. **建分支**：同 `branch`。已有同名分支、且指向同一候选时，直接复用。
3. **预演合并**：`git merge-tree --write-tree --merge-base <基线> H <候选提交>` 得到合并后的树 T，不碰任何工作区。有冲突就停，列出冲突文件；这时仓库里只多了一个本地分支。
4. **干净副本验证**：
   - 临时 worktree 停在 H，把 H→T 的差异作为未暂存改动写进去。这与 `check --fresh` 的布局相同，`git diff --check` 一类检查看到的仍是候选的改动。写完后快照必须等于 T。
   - 跑合同的 setup 与全部检查，记录在 `<run-dir>/integrations/NN/`。
   - 检查之后快照仍须等于 T，产物规则同 `check`。
   - 只对基线成立的检查（例如“这些文件与基线逐字相同”）在并行批次里可能失败，可以用 `--skip <ID> --reason <理由>` 豁免，豁免写进记录。
5. **落地**：
   - 必要检查全部通过后，`git commit-tree T -p H` 建提交，提交说明沿用分支提交的说明，含 `Pi-Dispatch-Attempt` 等尾注。
   - 再次确认分支末端仍是 H，然后在主工作区 `git merge --ff-only`。
   - 主工作区有会被覆盖的本地改动时，git 会拒绝快进：干净地失败，什么都没落地。主工作区从头到尾不会停在 cherry-pick 的中间状态。
6. **收尾**：
   - `mark INTEGRATED --ref <新提交>`，并写 `integration.json`（H、T、新提交、检查结果）。
   - 然后做 `cleanup`：worktree 里有候选之外的内容（LOSS）时照旧拒绝清理；集成已经完成，只提示。
   - `--keep-worktree` 跳过清理。`--dry-run` 只做 1–4 步，相当于“在当前末端上跑检查”。
7. **退出码**：0 表示已落地（或 dry-run 通过）；1 表示冲突、检查失败或快进被拒，都没有落地；3 表示授权或结论不允许。
8. **并行批次**：逐个 integrate，后一个的 H 就是前一个落地后的末端。候选之间冲突时，停在第 3 步。

本版不做：REVISE 或 TIMEOUT 之后由规划端补完再集成（SUPERSEDED）的路径，仍然手工；任何推送。

### 3.2 `mutate`：一份清单多条命令，变异带预期

- **多条命令**：清单可以写 `commands`，例如 `[{"id": "all", "argv": [...]}, {"id": "executor", "argv": [...]}]`。旧的 `command` 仍可用，等于一条 id 为 `main` 的命令。每条变异只套用一次，依次跑每条命令；不做变异的基线，每条命令各跑一次，都要通过。
- **预期**：每条变异可以标两种预期。
  - `"expect_missed": ["executor"]`：列出的命令预期会漏掉，例如合同留给 oracle 的规则。
  - `"equivalent": "<理由>"`：预期所有命令都漏掉。
- **结果**：按命令记 caught / missed / skipped / error，并标 `expected`。汇总行把预期与意外分开，例如 `executor：抓住 12，漏掉 20（预期 18，意外 2：M07 M14）`。标了等价、却被抓住的，也列为意外：说明等价的判断错了。
- **决策模型**（D2）只问意外漏掉的条目。
- **`--check-anchors`**：出现 0 次时，列出文件里最相近的至多 3 行（带行号）；出现多次时，列出每一处的行号和下一行，方便补上下文、让锚点唯一。
- run-dir 与 `--tree` 两种模式都支持。

### 3.3 `review-draft <run-dir>`：复审记录骨架与复审简报

- **复审记录骨架**：按 review-template 写 `.agent/reviews/<task>/<attempt>.md`，能从证据里取的都填好。
  - 基本信息：基线、候选树、要求与实际的模型、退出码、用时与上限、token 与费用状态。
  - 门禁表：机械部分（G0 / G1 / G2 / G4 / G6）写工具的结果与原因；G3 / G5 留 `【待填】`。
  - DoD：每行带检查 ID、最新检查结果与“目的”原文，结论留 `【待填】`。
  - 变异：每轮、每条命令的计数。意外漏掉的逐条写成固定格式，归因留 `【待填】`；预期内的预填“等价变异：<理由>”或“合同留给 oracle”。
  - 原文照录：执行报告的 `contract_conflicts`、`limitations`、`unresolved_questions`，以及摘要的“复审需要关注”。
- **复审简报**：同时写 `<run-dir>/review-brief.md`，内容是给独立复审的提示：RUN 的绝对路径、关注项、意外漏掉的变异、每条 DoD 的目的。交给 pi-reviewer，或另一家厂商的只读 CLI。
- **verdict**：拒收仍含 `【待填` 的复审记录（见问题 2）。

### 3.4 `metrics`：最终结果与估算费用

- **最终结果**：每个任务读各 attempt 的 `state.json`，分四类。
  - 直接集成：有 attempt 为 INTEGRATED。
  - 补完后集成：有 SUPERSEDED 且带 ref，没有 INTEGRATED。
  - 放弃：ABANDONED。
  - 未定：其余。

  表里加“最终”列与 ref，汇总加“最终集成率”。现有的首轮 PASS 率、有限重试内 PASS 率，口径不变。
- **价格表**：
  - 配置新键 `pricing`，按 `<provider>/<model>` 给每百万 token 的 input / output / cache_read / cache_write 单价，以及币种、来源与日期。
  - Pi 自己的费用未知时，metrics 用 `usage` 乘单价估算，注明“按配置价格估算（来源、日期）”；没有价格的模型仍是 unknown。
  - kit 不内置任何价格，也不联网去查（见问题 4）。用 `config set pricing.<键> …` 写入，`config validate` 校验。

### 3.5 保护 kit 自己加载的文件

- **加进 `PROTECTED_PATTERNS`**：
  - `scripts/kit_config.py`；
  - `scripts/codekit/` 下的 `__init__.py`、`decisions.py`、`secrets.py`、`planner.py`、`planner_protocol.py`、`protocols.py`；
  - `plugins/decisions/**`。
- **只保护调度器实际加载的文件**，不保护整个 `scripts/codekit/`。v2 参考实现另有 70 多个模块，执行器以后还做不做它们，是另一个待定方向，不在这里一刀切。
- 调度器加载的文件以后有增减时，测试核对这份清单与实际的 import 一致。

### 3.6 问题清单核对内容锁

- **核对**：`load_batteries` 读 `plugins/decisions/lock.json`。
  - 锁自身的 `lock_sha256` 必须对得上，用与 `codekit/plugins.py` 相同的规范 JSON。
  - 每份清单的 sha256 必须等于锁里同一路径的记录；目录里多出或缺少的清单，都算不符。
  - 不符时抛 `DecisionError("battery_drift")`。
- **处理**：沿用 2.6 的失败开放。
  - `prepare`、`doctor`、`config validate` 把它当错误报出；决策模式是 shadow / on 时，`prepare` 拒绝，规划端当场修。
  - `collect`、`mutate`、`wait --assess` 遇到时，本次不问决策模型，在输出和 summary 里写明原因，不阻断命令。
- **生成锁的脚本进 kit**：`python scripts/codekit/decisions.py --write-lock plugins/decisions`。改了问题清单后，用它重算 manifest 的资源哈希与锁；`compiler_sha256` 沿用其他插件的。

### 3.7 技能与文档

- **review-pi**：第 4–9 步改用 `review-draft`、多命令变异与 `integrate`；mutation-check.md 写新的清单字段；review-template 与 review-draft 的输出对齐。
- **plan-task**：合同模板的 `integration_actions` 写明问题 1 的结论。
- **dispatch-pi**：并行批次逐个 `integrate`。
- **文档**：CHANGELOG、README 一行、本说明的进度；KitExperiment 实机反馈文档的回流小节。

## 4. 证据边界

全部离线。测试用临时仓库与 `stub_pi.py`，不联网，不调用真实的 Pi 或 Jev。`integrate` 只动本地分支和当前分支的快进，永不推送。

## 5. 不做

- 推送、开 PR、合并到当前分支以外的分支；SUPERSEDED 路径的自动化。
- 单独的 `check --ref` 命令。“在当前末端上跑检查”由 `integrate --dry-run` 提供；草稿阶段量钉住面本来就在草稿 worktree 里做，不需要另建副本。
- 评估里列出的其他方向：CI、安装与更新、v2 去留、第二种执行 CLI、Jev 实数据。各自另立。

## 6. 用户决定（2026-10-14，均选推荐项）

1. **integrate 落地要什么授权**：合同 `integration` 写了 `merge` 才落地；没写时只做到第 4 步验证，并打印落地命令。plan-task 模板注明：用户已长期授权集成的仓库，写 `local_branch, merge`。
2. **复审记录草稿**：直接写 `.agent/reviews/<task>/<attempt>.md`，已存在就拒绝（`--force` 覆盖），判断处留 `【待填】`；verdict 拒收仍有 `【待填` 的记录。
3. **变异预期**：多命令，加 `expect_missed` / `equivalent`，结果分预期与意外，退出码不变。
4. **执行费用**：配置里的价格表由用户填，kit 不内置，也不联网去查。

## 7. 进度与遗留

- 2026-10-14：核对现状，写成本说明；用户决定第 6 节四项（均选推荐项）。
- 2026-10-15：2.8.0 做完（见 CHANGELOG）。实施中的两处补充：`plugins/decisions/**` 进 `.gitattributes` 的 `-text`（系统级 autocrlf 会让新克隆的清单哈希失配）；`config set` 的键路径只在第一个点处分开（模型名可以含点）。KitExperiment 的真实记录上，新 metrics 的最终集成率 97%（直接集成 30、补完后集成 7、放弃 1）。
- 遗留：SUPERSEDED 路径（返工或规划端补完之后集成）仍手工；价格表等用户填单价；下一轮 KitExperiment 合同写 `local_branch, merge` 后第一次实机用 integrate。
