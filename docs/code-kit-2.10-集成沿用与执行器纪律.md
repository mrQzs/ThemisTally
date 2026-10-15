# Code-Kit 2.10 设计说明：integrate 沿用检查结果，执行器的自检写法与解读清单

状态：设计中（2026-10-15）。

## 1. 为什么做

2026-10-15 的评估（用户回复“就按照你推荐的来”）选了两类小改动：每轮都省时间、少返工。端到端并行、v2 测试分级、CI 各自另立方向。

- **两遍全量测的是同一棵树**：kit-install 那一轮，`check --fresh` 用了 368 秒，`integrate` 用了 370 秒，两次跑的都是全部 7 条检查。integrate 时分支末端只比基线多了合同（`.agent/plans/kit-install.v1.*`），要落地的树和干净副本测过的树只差这两个规划文件。KitExperiment 的习惯是先提交复审记录再集成，末端多出的也只是 `.agent/reviews/` 下的文件。
- **掩盖测试退出码**：有记录的两轮都出现了。serve-loop 15 条掩盖退出码的命令里 7 条是 pytest；kit-install 20 条里 12 条是 pytest。写法几乎都是照抄合同里的检查命令，再接 `2>&1 | tail -N`。执行说明第 5 条与 AGENTS.md 早就写了合规的截短写法，没有挡住。
- **自定的解读不进报告**：pi-native-events 的执行器写了“I'll note this as an interpretation”，kit-install 的执行器写了“I'll go with toplevel check”（事件流第 6100 行），两次报告的 `unresolved_questions` 都是空的。报告格式里也没有放这类内容的字段：`contract_conflicts` 要两处互相矛盾的原文，`unresolved_questions` 是没解决的问题，`limitations` 是没做到的事；“合同没写死、我自己定了”不属于其中任何一个。
- **旧名**：AGENTS.md 第一句还是“本仓库用 PI-Kit 协作”，执行器照抄进了 `kit_install.py` 的文档串（kit-install 复审 R5）。这个文件会随 `kit_install` 装进别的仓库。

## 2. 现状（2026-10-15 核对）

- **integrate**（2.8.0）：每次都新建临时 worktree（末端 H，加上 H→T 的未暂存差异），跑合同的 setup 与全部检查，不读 `checks/` 下已有的记录。
- **check --fresh**：记录在 `<run-dir>/checks/NN/checks.json`，含 `mode`、`candidate_tree`、每条检查的结果、`covers_all_required`、`all_required_passed`、`modified_by_checks`、`unexpected_files_by_checks`。`covers_all_required` 只看必要检查，`--only` 跑一部分时也可能为真。
- **规划路径**：`planner_paths`，缺省是 `.agent/plans/**`、`.agent/reviews/**`、`.agent/design/**`、`.agent/publications/**`、`.agent/*.md`。目前只用来给运行期间主工作区的变化归类。Code-Kit 与 KitExperiment 的测试都不读真实仓库里的这些路径：测试里的 `.agent/plans` 都建在临时仓库里。
- **执行说明**：
  - 第 5 条给的截短写法是 `T=$(mktemp -d); <命令> > "$T/out" 2>&1; echo "exit=$?"; tail -n 20 "$T/out"; rm -rf "$T"`；AGENTS.md 的“Pi 执行器”一节写的是同一句。
  - 机器合同摘要按 argv 列出每条检查。
  - 摘要把“测试或检查命令的退出码被管道掩盖”列为复审关注（2.6.1）；开了 `pipefail` 或读了 `PIPESTATUS` 的命令不算。
- **执行报告**：
  - JSON 字段有 `self_checks`、`dod`、`contract_conflicts`、`unresolved_questions`、`limitations`。
  - 事件流里的解读线索由 `INTERPRETATION_RE`（2.5.0）抓取，写进 `events-summary.json` 的 `interpretation_mentions`。
  - 摘要只在 `contract_conflicts` 与 `unresolved_questions` 都为空时，才把线索列为关注。
  - `review-draft` 原文照录三处字段，不列线索。
- **旧名**：
  - 出现在 AGENTS.md 第 3 行、`.codex/config.example.toml` 第 1 行，以及 `pi_dispatch.py` 的两处文档串和一条提示。
  - `kit_install` 只在目标仓库没有 AGENTS.md 时放入，已有的永不改写。

## 3. 方案草图

### 3.1 integrate 沿用干净副本的检查结果

- **条件**（全部满足才沿用）：
  1. 没有 `--recheck`，也没有 `--skip`（豁免只在重跑时有意义）。
  2. 最近一次 `check --fresh` 的记录是干净的：
     - 没有中止；
     - 测的是这个 attempt 的候选树；
     - 合同里的每一条检查都跑过，包括非必要的；
     - 必要检查全部通过；
     - 没有改动候选文件，也没有候选之外的新文件。
  3. 预演合并得到的树 T 与候选树相比，只在规划路径下有差异：`git diff-tree` 列出的每个路径都匹配 `planner_paths`。两棵树完全相同时自然满足。条件的宽严是用户定的（第 6 节问题 1）。
- **沿用时**：
  - 不建临时 worktree，不跑 setup 与检查。
  - `integration.json` 记 `checks_reused`：沿用的是哪份记录、它的检查时间，以及 T 相对候选树多出的规划路径。`results` 抄自那份记录，并标明出处。
  - 输出写明沿用了哪一次、多出哪些规划文件。
- **不满足时**：照旧重跑，并先打印一行原因，例如“末端相对候选多了 `README.md`（不是规划路径）：重跑检查”。
- **其余不变**：预演冲突、建提交、快进、标记、清理照旧；`--dry-run` 也按同样的条件判断。
- **沿用只看内容，不看时间**：两次都在本机跑。环境变了（例如升级了 Python）要重测时，用 `--recheck`。

### 3.2 执行说明给出每条检查的自检写法

- **每条检查的自检写法**：机器合同摘要里每条检查下面多一行“自检照抄”（执行器有 shell 时才写）。
  - 有 bash：`set -o pipefail; <命令> 2>&1 | tail -n 40`。cwd 不是 `.` 时前面加 `cd <cwd> &&`，有 env 时写成 `变量=值 <命令>`。`pipefail` 让管道的退出码就是测试自己的退出码，工具返回的也就是真实退出码；摘要的检测本来就把开了 `pipefail` 的命令算作合规。
  - 只有 powershell：`<命令> 2>&1 | Select-Object -Last 40; "exit=$LASTEXITCODE"`。
  - 期望退出码不是 0 的检查，在同一行写明期望值。
- **截短规则**：执行说明第 5 条和 AGENTS.md 关于截短的那句改成：截短时照抄摘要里的写法；自己临时写的测试命令接管道时，开头同样加 `set -o pipefail;`。KitExperiment 的 AGENTS.md 同步这一句。
- **摘要**：“退出码被掩盖”这一关注项的判定不变，文字里指向执行说明的自检写法。

### 3.3 执行报告加“自定解读”清单

- **新字段**：报告 JSON 加必填字段 `interpretations`。
  - 每一项写成 `{"quote": "合同原文或条目号", "adopted": "采用的做法", "reason": "理由"}`；没有就写空列表。
  - 只收合同没有写死、由执行器自己定下的做法，例如某个边界算不算、出错时走哪条路。
  - 命名、函数拆分这类实现细节不算。合同前后矛盾的，仍写进 `contract_conflicts`。
- **执行说明与 AGENTS.md**：报告格式里加上这个字段并举一个例子；“Pi 执行器”一节加一句同样的要求。
- **调度器**：
  - `report-status.json` 记 `interpretations` 的条数；字段缺失时另记一笔。
  - 摘要：
    - 事件流里有解读线索、而报告的四处字段（含 `interpretations`）都为空时，列为复审关注（同现在）；
    - 报告列了解读时，在备注里提示核对线索是否都在报告里；
    - 字段缺失时，在备注里写一句。
  - `review-draft`：“执行器自述与证据是否一致”下面加两块原文，由复审逐条对照：
    - 报告的 `interpretations`；
    - 事件流里的解读线索（行号与摘录，最多 10 条）。

    独立复审简报同样列出。
- **门禁**：不挡（第 6 节问题 2）。缺字段、线索没报告都只进摘要与复审骨架。

### 3.4 旧名

- AGENTS.md、`.codex/config.example.toml`，以及 `pi_dispatch.py` 的文档串与提示，改成 Code-Kit。CHANGELOG 与历史设计说明不改。
- 已经装进别的仓库的 AGENTS.md 不会被改写（kit_install 的 MANUAL）；改名只影响新装的仓库与 Code-Kit 自己。

### 3.5 技能与文档

- review-pi：integrate 一步写明沿用的条件与 `--recheck`；复审时对照解读清单与线索。
- dispatch-pi 的排错表：执行器仍然掩盖退出码时，怎么核对它的自检结论。
- plan-task 的合同说明：提一句执行器会拿到每条检查的自检写法。
- README、CHANGELOG 2.10.0。

## 4. 这一轮怎么跑

- **由规划端直接改**：改动都在调度器、规则文件与技能里，按约定不派执行器。
- **测试**：
  - 端到端，新加一个场景：
    - 末端只多了规划文件时沿用；
    - 多了 README 时重跑；
    - 加 `--recheck` 时重跑；
    - 最近一次 `check --fresh` 只跑了一部分时重跑；
    - 执行说明里的自检写法覆盖 bash、cwd、powershell 三种。
  - 单元测试：报告字段的计数与缺失、摘要的三种情况、`review-draft` 列出的解读与线索。测试桩是锁定的，不改它输出的报告。
- **验证**：端到端全过；pytest 全量通过；legacy check 只剩那条常年存在的 DIFF；release-check 干净；技能两份同步。
- **效果**：要等下一轮实战来测：执行器还掩盖几条测试退出码，解读清单有没有被填写。

## 5. 不做

- 端到端场景并行；v2 测试分成慢速套件（后者等 v2 去留的决定）；CI。
- 改写已装仓库里的 AGENTS.md。

## 6. 用户决定（2026-10-15，均选推荐项）

1. **integrate 沿用检查结果的条件**：只差规划文件即沿用。末端相对候选只多了 `planner_paths` 下的文件，且最近一次 `check --fresh` 跑了全部检查、必要检查全过、没有留下改动时沿用；`--recheck` 强制重跑。另两个选项是“树完全相同才沿用”（kit-install 与 KitExperiment 的轮次都省不下来）和“不自动沿用，加 `--reuse-check` 才沿用”。
2. **两类纪律问题**：只提示，不挡门禁。掩盖测试退出码、解读没写进报告，都列进摘要的“复审需要关注”与复审骨架，由复审决定是否返工。验收证据是调度器自己跑的检查，执行器的自述本来就是最低优先级的证据。

## 7. 进度与遗留

- 2026-10-15：核对现状，写成本说明；用户决定第 6 节两项（均选推荐项）。
