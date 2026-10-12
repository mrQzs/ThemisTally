# 设计说明：把 KitExperiment 的教训回流成 Code-Kit 2.5（回流）

状态：用户 2026-10-12 决定第 5 节四项均选推荐项；规划端直接做 2.5.0。
前置：Code-Kit 2.4.2（`02aa096`）；KitExperiment 自 2.4.2 之后又跑了 13 轮（pi-native-events → task-done），教训只进了 `docs/KitExperiment实机反馈.md` 与几条技能文本，调度器一行未改。

## 1. 为什么做

- KitExperiment 的意义是给 Code-Kit 当试验田：每轮的"待改进（调度工具）"与"规划端的教训"都应落成 kit 的脚本或技能改动。2.3.0/2.4.0 做过一次清账（2026-10-06）；之后 13 轮积累的条目没有再清，其中 `mutate --tree` 在三轮反馈里被点名"规划端最想要的"，每轮仍用临时脚本（本会话的 `mutate_draft.py`）跑草稿变异，判定口径还与 kit 不一致过一次（任何非零退出码都算抓住，掩盖了会话中断）。
- 流程上没有"回流"这一步：review-pi 技能第 9–10 步到"回复用户"就结束，教训回流靠规划端自觉，所以只记录不改动。

## 2. 现状（2026-10-12 核对）

反馈文档里 2.4.2 之后仍开着的调度工具条目（按出现次数与轮次）：

| 条目 | 来源轮次 | 现状 |
| --- | --- | --- |
| `mutate --tree <路径>`：对任意树（规划端草稿工作树）跑变异，不要求 attempt 目录 | ledger-reference、ledger-compaction、ledger-events（三次） | 未做；`cmd_mutate` 的判定逻辑（只认退出码 1、会话中断记为出错、只插入代码提示、锚点计数）都在，只是入口绑定在 attempt 与候选补丁上 |
| summary 标出自检命令里 `| tail`、`| head` 这类掩盖退出码的管道 | ledger-compaction | 未做；`shell_commands` 已在事件摘要里 |
| summary 标出 `mkdtemp()` 之后没有 `rmtree`/`rm -rf` 的命令 | ledger-events | 未做；临时路径扫描只列命中 |
| `validate`/`prepare` 把"时间分配"合计与 `max_wall_seconds_per_attempt` 比，超过 70% 警告 | ledger-events | 未做；预算字段已解析，时间分配只在 Markdown 模板里 |
| 歧义提示把执行器自己宣布裁定的短语（"judgment call""I'll note this as an interpretation"）单独标出 | pi-native-events | 未做；`AMBIGUITY_RE` 只找"歧义/矛盾"一类词 |
| `doctor` 不带 `--provider/--model` 时在 `notes` 里写"未检查执行器" | pi-native-events | 未做 |
| DoD 解析把一行里第一个"证据"当分隔词（D05 文本以"证据一半"开头被解析成空串） | win-supervise | 未做；`partition("证据")`（`pi_dispatch.py:1494`） |

技能里已落地的（grep 核对）：探针/草稿变异、重锚、argv 不经 shell、两两组合、数据要能区分、时间分配、先跑单个用例、漏掉三分法、`\u` 转义提示。未落地的：**码名与事件名在草稿上跑一遍再写 Repository facts**（run-cli-recover、run-cli-pi 两轮）、**oracle harness 同时照顾进程内与持久对象**（task-done）、**写设计说明前先用探针量钉住面**（task-done；SKILL 第 3 节只写了"数字先量"）、**heredoc 里的反斜杠会被折叠**（review-verdict；SKILL 第 137 行只写了 Write 工具的 `\u`）、**锚点先 `grep -c`**（只在 mutation-check 的轮次记录里，不在规则段）。

kit 的自测：`tests/test_dispatch.py`（2210 行，`test_mutate`、`test_v241_*`、`test_v242_*` 各钉一个版本的行为），`tests/stub_pi.py` 锁定。版本号 `TOOL_VERSION = "2.4.2"`，CHANGELOG 每版一节。

## 3. 方案草图（2.5.0）

A. **`mutate --tree <路径>`**：`mutate --tree <树> --spec <清单> [--out <目录>]`，不要求 attempt；在给定树上原地套用变异（每条之后恢复原文件，结束时核对树没有残留改动），判定与 attempt 模式同一段代码（基线先过、只认退出码 1、会话中断记为出错、只插入代码 WARN、锚点计数不符记跳过）；记录写到 `--out`（默认系统临时目录，结束时打印路径），不写进被变异的树。另加 `--check-anchors`：只核对每条 `old` 的出现次数，不运行命令，给规划端在重锚后先验锚点。
B. **`validate`**：时间分配合计（Budget 段 "约 N 分钟" 求和）超过 `max_wall_seconds_per_attempt` 的 70% 时警告；DoD 解析改为只认"；证据"或行首以外的"证据："分隔（兼容既有合同：全部历史合同回放结果不变，D05 那种以"证据"开头的文本不再被截空）。
C. **summary**：自检命令与事件流命令里 `| tail`/`| head`/`|| true` 掩盖退出码的写法标为备注；`mkdtemp(`/`TemporaryDirectory(` 之后同一命令里没有 `rmtree`/`rm -rf` 的标为备注；执行器自宣裁定的短语（"judgment call"、"I'll note this as an interpretation"、"I'll interpret"、"我理解为"、"按……解读"）与一般歧义提示分开列。
D. **`doctor`**：没有 `--provider/--model` 时 `notes` 写"未检查执行模型与凭据"。
E. **技能**：plan-task 加"码名/事件名跑一遍"、"探针量钉住面"、"harness 两种对象"；review-pi 的 mutation-check 把"锚点先 `grep -c`/`--check-anchors`"与"草稿用 `mutate --tree`"写进规则段；review-pi SKILL 第 10 步之后加第 11 步**回流**：每轮结束时把本轮教训落成 kit 的脚本或技能改动并提交，或在反馈文档写明"本轮无需改动"及理由——没有这一步不算收尾。
F. **自测与版本**：每项 A–D 在 `tests/test_dispatch.py` 加检查（A 用 stub 树与清单覆盖抓住/漏掉/跳过/中断/锚点预检；B 用历史合同回放 + D05 用例；C 用构造的事件流；D 直接调用）；`TOOL_VERSION` 2.5.0，CHANGELOG 一节；`sync-adapters`。

## 4. 证据边界

- 只跑 kit 自己的测试与历史 attempt 回放；不调用真实 provider、不读凭据、不联网；`tests/stub_pi.py` 不改。
- 全部改动由规划端直接做（执行器不得改 `pi_dispatch.py`），用 KitExperiment 的真实清单（本轮 29 条）与草稿工作树验收 A。

## 5. 用户决定（2026-10-12，均选推荐项）

1. **范围**：A–F 一起做成 2.5.0（推荐；条目都小，一次清账）还是只做 A（`mutate --tree`）先发 2.5.0，其余留 2.5.x。
2. **谁做**：规划端直接改（推荐；`pi_dispatch.py` 本就不给执行器改，测试与技能同批）还是技能与测试部分用 kit 派给 Pi（dogfood，但要为 Code-Kit 写合同与 oracle，一轮 30 分钟以上）。
3. **回流规则的强度**：写成 review-pi 的必做步骤，没有回流提交或"无需改动"记录不算收尾（推荐）还是只在反馈文档模板里加一栏。
4. **`mutate --tree` 的记录位置**：默认系统临时目录并打印路径（推荐；不污染被变异的树，草稿树通常是临时 worktree）还是写进树内 `.agent/runs/_mutate/NN/`。

## 6. 规划端决定

- A 复用 `cmd_mutate` 的循环体，拆成 `_mutation_loop(workspace, spec, out_dir, env, grace)` 供两个入口调用；attempt 模式行为与记录格式不变（2.4.1/2.4.2 的测试照旧通过）。
- B 的 DoD 解析用全部历史合同（KitExperiment 的 `.agent/plans/*.md`、kit 的 examples）回放，证明只有 D05 那类文本变化。
- C 只作备注，不列为可疑命令（2.1.0 的教训：启发式豁免会被构造的命令骗过，这里反过来——只提示、不判定）。

## 7. 拆分

一批改动、一个版本（2.5.0），按 A → B → C → D → E → F 的顺序提交，每项一个提交，CHANGELOG 最后。

## 8. 不做

- 不改执行说明、门禁判定与范围扫描的口径；不放宽任何可疑命令规则。
- 不做并发变异、不做变异体自动生成。
- 不改 `stub_pi.py`。

## 9. 进度与遗留

- 2026-10-12：核对第 2 节；用户决定第 5 节四项均选推荐项。
