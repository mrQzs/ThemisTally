# REVIEW：kit-logs v2 · attempt-002

Verdict: REVISE

<!-- review-draft 生成（2026-10-17T12:25:18Z，调度工具 2.10.0）：事实取自 .agent/runs/kit-logs/attempt-002；标着“待填”的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`9368e8cd540b6d4c4440e1bae633d7f3085304ab`
- 候选树：`3e401d4a56725da37642ae4e184261f345dd27c0`（补丁往返校验通过；2 files changed, 121 insertions(+), 66 deletions(-)）
- 要求的执行模型：bb/step-5-preview · thinking high
- 实际模型：bb/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 0 · 用时 637.11 s / 上限 1800 s · 正常结束 · 工具错误 4
- token：输入 104752 · 输出 34222 · 缓存读 2496256 · 缓存写 0；费用 unknown（unknown）
- 复审者：Claude Code 规划端会话（Opus 5.5）；独立复审：pi-reviewer 子代理（`claude-opus-5-5`，只读，按 independent-review.md）。整轮另由 Codex 在闸二审核。

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | passed | 工具：通过；提供商未回报思考级别：只能确认请求的级别（high） |
| G2 范围合规 | passed | 工具：通过 |
| G3 行为正确 | 未通过（复审） | 工具：通过；F1、F2、F5、F6 完整，F3 的分层正确，但 `_collect_attempts` 先 `_listable(attempt_dir)`、过滤后再 `_evidence(attempt_dir, …)`：两次列举之间目录变得列不出来时 `_evidence` 返回 None，`len(None)` 抛 TypeError 冒出堆栈（候选 `scripts/kit_logs.py` 第 472、478、484 行；违反 B11(a)“list 跳过该 attempt”与 B11(c)“不得冒出堆栈”）。规划端发现、独立复审核实（事件流第 5734 行的版本没有这个窗口，第 8084 行为保住解读 #4 的顺序改成了两次列举） |
| G4 回归检查 | passed | 工具：通过；检查记录：checks/01（fresh，4/4 通过）；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | 通过（附规划端补测） | 自测只按合同 Steps 第 6 条删改；变异 31 个抓住 30（M31 为标明的等价变异）。合同 Steps 第 6 条的前提有误（规划问题）：被删的 `test_bad_task_id_is_a_usage_error_for_every_subcommand` 还覆盖 search、usage 的 `--task` 校验，oracle 只测了 list——执行器在 limitations 里如实报告；另外 search、usage 在 attempt 目录列不出来时的行为没有 oracle 用例（独立复审）。都由规划端补测 |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | 部分满足（F2 点名的三类都已处理；但上述竞态会冒出 TypeError 堆栈） | V01 passed | F2。任何输入都不冒出堆栈：正则的溢出与深嵌套、时间换算溢出、深嵌套 JSON 都按 B11(c) 处理；目的：调用方靠退出码与 ERROR 行区分用法错误与证据缺失，不会看到堆栈（V01 中 `ReworkV2` 的 F2 用例） |
| D02 | 满足（`_check_within_runs` 在唯一出口覆盖 A–D；`resolve()` 异常按找不到） | V01 passed | F1。所有形式（A、B、C、D）的目标目录都过 B5.5 的兜底，且兜底不依赖链接检查；目的：指向 runs 之外的 junction 不能被 `show task-x`、`show task-x.v1`、`show task-x/attempt-001` 读到（V01 中 `ReworkV2` 的 F1 用例） |
| D03 | 部分满足（分层正确，五个 `_scan` 调用点都处理了 None；list 有两次列举之间的竞态） | V01 passed | F3。列举失败按 B11(a)、(b) 分层：runs 根退出码 1；目标解析中找不到退出码 2；其余目录跳过且不计数；`--transcript` 目录列不出来计入 `unreadable_files` 并标部分；目的：一个目录列不出来不能拖垮整条命令，也不能让它的内容被计入（V01 中 `ReworkV2` 的 F3 用例） |
| D04 | 满足 | 复审 | F6。`has_summary` 先判断链接再 lstat；目的：与 B0.8 的顺序一致，链接不会被 lstat 之后再判断 |
| D05 | 满足（删改只限 Steps 第 6 条；.5Z 改为 (2,2,2) 经核算正确） | V02 passed、复审 | F5。执行器自测不随 Python 版本变化，不照抄 oracle 的辅助函数，并删除了 Steps 第 6 条指定的两个重复用例；目的：自测不随解释器版本变化，也不与 oracle 重复 |
| D06 | 满足（88 passed） | V01 passed | 回归。基线上的 71 项既有用例与 v1 的行为不变，新增的 17 项也通过；目的：修正不改变已接受的行为 |
| D07 | 满足 | V01 passed | 链接判断只调用 `pi_dispatch` 的 `is_link_or_junction`、`first_link_component`、`is_within`，不复用 `resolve_run_dir` 与 `task_attempts`，源码中不出现 B0.7 列出的直接判断写法；目的：D11 要求单一实现，不许另写同类判断 |
| D08 | 满足（越界 0） | scope（越界 0） | 范围：只修改 `scripts/kit_logs.py` 与 `tests/test_kit_logs.py`；目的：不改调度器、配置、oracle 与其它模块，接入由规划端在集成后做 |
| D09 | 满足（Steps 第 6 条的异议写在 limitations 而不是 interpretations，信息级） | 复审 | 执行报告列出所有 `interpretations` 与 `contract_conflicts`（格式见执行说明），每条写出合同原文与采用的做法。报告里必须写明：目标 attempt 的证据目录列不出来时退出码 2（B11(a)）是合同的哪一条规定；目的：验收端能核对每个未经合同规定的取舍 |
| D10 | 满足 | 复审 | 不弱化。`tests/test_kit_logs.py` 只允许按 Steps 第 6 条删除两个重复用例、改写一处版本依赖断言、替换 `run_logs` 副本；oracle 中任何用例与辅助函数都不得改动；目的：修正不能靠删测试或改 oracle 来通过 |
| D11 | 满足（没有新建临时目录，未访问工作目录之外） | 复审 | 过程。没有使用固定临时路径（例如 `/tmp/dbgkit`），临时目录只用 `T=$(mktemp -d)` … `rm -rf "$T"` 的写法；报告中披露每条临时目录命令；目的：遵守 AGENTS.md 的临时目录规定，事后可以核对 |
| D12 | 满足 | V03 passed、V04 passed | 可导入与可运行。`py_compile` 与 `--help` 通过；目的：模块不会在导入或命令行入口处就失败 |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 88 项（基线上 13 项失败，即 ReworkV2 的 F1–F3 用例）、执行器自测 12 项，无 skip。变异 31 个：all 抓住 30，唯一漏掉的 M31（去掉 main 的兜底）事先标为等价；M18（上一轮漏掉）现由 `FileLevelLinks` 抓住；M19–M30 逐条对应 F1–F3 的修法，全部抓住。执行器自测只抓住 M10，其余预期内留给 oracle。
- 变异检查：
  - mutations/01：31 条，命令 all、executor
    - all：抓住 30，漏掉 1（意外 0），跳过 0，出错 0
    - executor：抓住 1，漏掉 30（意外 0），跳过 0，出错 0
    - `M31 main 的兜底改成不捕获` → 归因：等价变异（兜底只在合同点名的三处之外生效；oracle 的 F2 用例都由各处的具体捕获处理，去掉兜底观察不到） → 处理：注明
    - 预期内的漏掉（expect_missed：合同交给其他命令覆盖的规则）：M01 M02 M03 M04 M05 M06 M07 M08 M09 M11 M12 M13 M14 M15 M16 M17 M18 M19 M20 M21 M22 M23 M24 M25 M26 M27 M28 M29 M30 → 处理：注明
- 兼容性与残余风险：只改 `scripts/kit_logs.py` 与执行器自测；兜底（解读 #2）不改变任何已测退出码（M21–M24 仍以退出码 1 被抓住）。残余：独立复审推断，计数值是接近递归上限的深嵌套数组时 `_canonical` 的 `json.dumps` 可能递归溢出，经兜底得到退出码 1 而不是 0（只有一行 ERROR，没有堆栈；输入本身不合理，未验证，记录在案）。
- 执行器自述与证据是否一致：检查结果与 fresh 一致；报告的“用时约 570 秒”与 summary 的 637 秒不同（自述，以 summary 为准）；解读 #4 报告了列举顺序但没有意识到竞态；limitations 里关于被删用例覆盖面的说法属实（只是把 `list --state` 缺值误说成 `--task` 缺值）。过程干净：没有临时目录与固定路径，被管道掩盖的 7 条都是探索命令。
  - 执行报告：json_ok（executor_status completed）
  - 合同矛盾：无
  - 自定解读（5，原文）：
    - {"quote": "B11(a) attempt 目录列不出来：list、search 跳过该 attempt", "adopted": "用 _scan 探针/_evidence 返回 None 表达该层，list 跳过、search 跳过、show 目标 attempt 退出码 2", "reason": "形式 A/B/C 解析时只 lstat 不列目录，需要一个机制区分 list/search 与 show 的处理"}
    - {"quote": "B11(c) 本命令的任何路径都不得冒出堆栈", "adopted": "main 命令级再加 except (RecursionError, OverflowError)，一行 ERROR: 加退出码 1", "reason": "点名之处之外仍可能有未预料的递归/溢出，退出码 1 对应 B9 的运行错误"}
    - {"quote": "B11(a) 任务目录列不出来：list、search、usage 跳过它的全部 attempt", "adopted": "_attempt_entries 列举失败返回空列表，三个命令共用", "reason": "三种命令的枚举都经过 _attempt_entries，一处实现行为一致"}
    - {"quote": "B3 的 --state 过滤与 B11(a) 的跳过该 attempt", "adopted": "先查 attempt 目录可列举性，再 --state 过滤，最后扫证据", "reason": "B11(a) 的跳过无条件；同时保持 v1 顺序，被过滤掉的 attempt 不扫证据、不计链接"}
    - {"quote": "B7.1 --since/--until 的 fromisoformat 解析", "adopted": "fromisoformat 本身也捕获 OverflowError", "reason": "与 astimezone 溢出同属换算类溢出，按同一规则处理"}
  - 限制与取舍（3，原文）：
    - Steps 6 称 oracle 的 test_unknown_subcommand_and_bad_task_id_are_usage_errors 已覆盖被选用例；实际它只用 list 校验 --task，未覆盖 search/usage。已按合同指令删除，仅记录覆盖面收窄。
    - main 的兜底捕获没有专门用例，只在合同点名的三处之外生效。
    - 本机 Python 3.10.19；3.11+ 的 fromisoformat 额外写法未实测，自测已不再依赖版本相关写法。
  - 未决问题：无
  - 事件流里的解读线索：无
- 摘要里的“复审需要关注”（原文）：
  - 新增被 Git 忽略的路径：`.pytest_cache/`
  - 新增被 Git 忽略的路径：`.pytest_cache/.gitignore`
  - 新增被 Git 忽略的路径：`.pytest_cache/CACHEDIR.TAG`
  - 新增被 Git 忽略的路径：`.pytest_cache/README.md`
  - 新增被 Git 忽略的路径：`.pytest_cache/v/`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`
  - 删除了 9 行含断言的代码（新增 1 行）
  - 测试或检查命令的退出码被管道掩盖（1 条，例如事件流第 8200 行 `ls workflows; grep -rn "mypy" --include="*.cfg" --include="*.toml" --include="*.ini" --include="*.yml" --include="*.yaml" . 2>/dev/null | head -5`；另有 6 条探索命令也如此）：执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准（2.10.0 起执行说明给了每条检查的自检照抄写法）

## 结论理由
返工把复审列出的 F1、F2、F5、F6 完整修好，F3 的分层也对，fresh 检查 4/4、变异 30/30（除标明的等价变异）。剩下一处小缺陷：`list` 为保住 `--state` 过滤前不扫证据的顺序（解读 #4），先试列一次、再正式列一次，两次之间目录变得列不出来时冒出 TypeError 堆栈，违反 B11(a)、B11(c)。分类 EXECUTION_ERROR。
本 task 的预算已用完（2/2），剩余部分小而明确：按 rework.md 第四节与 review-pi 第 9 步，由规划端在返工提交上直接补齐（先过滤、只列一次、None 即跳过，删去 `_listable`），作为单独的提交，并按同样的标准验收（V01–V04、补测、变异检查、全量测试）；同时补上合同 Steps 第 6 条误删造成的 `--task` 覆盖缺口，以及独立复审建议的 search、usage 与 `resolve()` 异常用例。之后 `mark SUPERSEDED`。

## 后续动作
- 需要修正的具体差异（REVISE）：由规划端补齐，不再派遣（预算 2/2）：
  - `_collect_attempts`：先读 state、按 `--state` 过滤，再 `_evidence` 只列一次，None 即跳过；删除不再使用的 `_listable`。
  - oracle 补测（规划端，单独的类）：两次列举之间变得列不出来不崩溃；search 跳过列不出来的 attempt；usage 照常读列不出来的 attempt 的 `events-summary.json`；search、usage 的 `--task` 校验；目标 `resolve()` 抛异常时退出码 2。
  - 补齐后在合并结果上跑 V01–V04、针对补齐部分的变异与全量测试，再 `mark SUPERSEDED --ref <补齐提交>`。
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无
- 已授权且可以继续的集成动作：local_branch、merge：本 attempt 判 REVISE，不用 integrate；`branch --rework` 建返工提交（父提交即当前末端 9368e8c），快进 themis-3.0，再加规划端的补齐提交，验收后 `mark SUPERSEDED`。
- 人工介入：0（复审与补齐由规划端会话完成，用户未介入）
