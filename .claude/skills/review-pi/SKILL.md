---
name: review-pi
description: 独立验收 Pi 执行器的一次 attempt：核对执行证据与范围，在固定候选上重跑合同检查，复审代码与测试质量，用调度工具记录 PASS / ACCEPTED_WITH_EXCEPTION / REVISE / BLOCKED / ESCALATE，再按既有授权集成或准备返工。用于派遣完成后，或用户要求“验收/复审 Pi 的结果”时。
argument-hint: "<run-dir | task-id | task-id.vN>"
---

# 验收 Pi 执行结果

验收对象：$ARGUMENTS

（上一行在 Claude Code 中会替换为调用参数；在 Codex 中保持原样，此时参数就是用户调用本技能时附带的文字。）

参数可以是（attempt 目录、task-id，或 task-id.vN；后两者取最新 attempt）

**证据优先级**（从高到低）：

1. 在固定候选上独立运行的检查
2. 调度器记录的事实（事件、范围、候选补丁）
3. 源码审查与行为推理
4. 执行器自述

进程结束不等于任务通过。命令统一写作 `bash scripts/dispatch-pi.sh <子命令>`。

## 步骤

1. **定位**：`bash scripts/dispatch-pi.sh status <task-id>` 找到 `<run-dir>`，然后读 `<run-dir>/summary.md` 与 `<run-dir>/plan.md`（这是当时派遣的合同副本）。
2. **G0 / G1 执行完整性**：看 summary 的“执行完整性问题”。
   - 需要确认：事件流是否完整，最终 stopReason，实际模型，stderr 标记。
   - 思考级别：本机 Step 配置不会回报 providerThinkingLevel，只能确认请求的是 high（Pi 会把它映射为 thinking 预算）；提供商回报了其他级别时，按问题处理。
   - TIMEOUT / CANCELLED / INFRA_FAILURE 不能 PASS。
3. **G2 范围**：读 `scope.json` 与 summary 的“复审需要关注”。
   - 任何越界都要先查清影响，尤其是：受保护路径、HEAD 移动、worktree 之外的路径、主工作区变化、新增被忽略的文件（如 `.env`）。
   - 可疑命令一项写明命中所在的行与事件流行号，完整命令按行号到 `events.jsonl` 中查看。
     - 删除本条命令用 mktemp 新建的临时路径（例如 `TMPD=$(mktemp -d)` 之后 `rm -rf "$TMPD"`）也照常列为可疑命令：2.1.0 起不再豁免。按行号核对变量来自这条命令的 mktemp、中间没有被改写，删除的是它本身而不是子路径（mktemp 失败时变量为空，`"$TMPD"/x` 会落到根目录）。
     - 删除工作副本内的缓存目录（`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`.hypothesis`，相对路径且不含 `..`）同样记在“备注”；混有其他目标时仍会列出。
   - **运行时才生成的路径**：
     - 执行器在命令中用 tempfile、mktemp、`/tmp`、`$TEMP` 等创建或使用系统临时目录时，摘要列入“复审需要关注”。这些路径在工作目录之外，自动范围检查看不到其中的读写。扫描前先屏蔽工作目录本身：默认的 worktree 就建在系统临时目录下。
     - 按 AGENTS.md 核对写法：只允许测试框架管理的目录，或同一条命令里 `T=$(mktemp -d)` 新建、并以 `rm -rf "$T"` 作为最后一步。调度器不替你判断是否已清理：四轮审查表明，这类判断总能被构造的命令骗过。
     - “越界 0”不等于过程中没有访问工作目录之外，要按事件流行号核对它们的用途，并确认没有留下目录。
   - **工作副本外路径**：
     - 工具参数里的路径照常列出。
     - 调度工具 2.4.0 起，shell 命令里系统目录、家目录、其他仓库或 worktree 的绝对路径也会列出；同一路径只列一次，带第一次出现的事件流行号与命令条数。
     - 主仓库里的路径判 G2 不通过（2.3.0 起）。其他路径只作提示，常见的是测试数据里的字面量（例如 `'PATH': '/usr/bin:/bin'`）。
     - 按行号确认是否真的读写了，例如用 `ls /usr/bin/python3*` 查找解释器就是越出工作副本的读取。
     - 摘要逐命中片段列出临时路径；同一命令开头的合法 mktemp 不代表后续固定 `/tmp` 路径也合法。超过50条摘录时，按截断提示继续读原事件。清理成功的输出或路径当前不存在，也不能证明此前未覆盖既有内容。
     - 实机：Codex 规划端的第一次试跑中，执行器用 `tempfile.mkdtemp()` 建目录并切换进去，当时的版本没有提示，是复审时人工发现的，判 REVISE（SCOPE_VIOLATION）。
4. **独立检查**：`bash scripts/dispatch-pi.sh check <run-dir>`。
   - 中高风险任务加 `--fresh`：在干净副本（基线 + 候选补丁 + 合同 setup）上运行，不受执行 worktree 里被忽略的依赖或构建产物影响。
   - 在另一台机器上复审时（`check` 与 `verdict` 会打印“attempt 在另一台机器上派遣”，summary 的“派遣环境”一行写着派遣时的系统与仓库路径）：
     - 执行 worktree 不在本机，只能用 `--fresh`；
     - verdict 不重新快照 worktree，G6 只凭候选补丁的往返校验，门禁备注会写明。
   - 结果用于 PASS 时不要加 `--only`。
   - 失败时读 `checks/NN/<ID>.log`。
   - 工具报告候选漂移（候选文件被改动，或出现候选之外的新文件）时，不要删文件凑通过。先查明来源：属于实现的，要回到返工；只是缓存或报告的，加入 `.gitignore` 或配置 `check_artifact_patterns`。
5. **G3 / G5 复审代码**：读 `candidate.patch` 与必要的源码上下文。按 [gates.md](gates.md) 的清单逐条核对 Behavior contract 与每个 DoD，重点看测试是否可信、是否被弱化。实机复审得到的经验：
   - **逐条对照合同中列出的每个输入形态**。执行器容易只覆盖主要写法，例如只校验标准键、漏掉合同同时列出的别名键；测试也会随之遗漏。挑一两个合同点名、但测试没有覆盖的形态，在 worktree 里用探针实际运行。
   - **看完整文件时用不重叠的范围**。`sed -n 1,60p` 接着 `sed -n 60,140p` 会把第 60 行打印两次，曾经被误读成“重复定义”。也可以直接读 worktree 中的文件或 `git show <tree>:<path>`。
   - **记录 nit 之前先核实**。写进复审报告的问题要能复现；误报要在报告里更正，不要静默删除。
   - 合同本身有疏漏时，在报告中写明是规划问题，不要算作执行错误。
   - **中高风险任务做一轮变异检查**：`bash scripts/dispatch-pi.sh mutate <run-dir> --spec <清单.json>`。
     - 对合同的每条规则各做一个最小变异，在干净副本上只跑相关测试，看测试能否抓住；清单格式与结果处理见 [mutation-check.md](mutation-check.md)。
     - 漏掉的变异就是测试缺口。合同测试清单遗漏的，由规划端补测试并单独提交；执行器少写的，记入复审。
     - 实机：export-command 11 个变异抓住 10 个，negation-coverage 9 个抓住 8 个。漏掉的“相对路径”“去重”都是 fresh 检查看不出的缺口。
   - **合同矛盾要逐条裁定**：
     - 执行报告的 `contract_conflicts` 非空时，逐条写明以哪一处为准；执行器暂时采用的做法与裁定一致才能 PASS。
     - 摘要提示“执行过程中提到合同的歧义、矛盾或一致性”、而报告没有列出时，读 `events-summary.json` 的 `ambiguity_mentions` 摘录，确认执行器是否自行选定了某种解释。
     - limitations 中出现“按合同……”一类的说法、而相关 DoD 标为 done 时，也要对照合同原文。
     - 实机上出现过这样的情况：执行器发现“按 finding_id 去重”与“该 cue 只有一条”互相矛盾，自行选了前者，把测试写成断言两条，并把 DoD 标为 done；报告只在 limitations 里写了一句“按合同不去重”。
6. **中高风险任务做独立复审**：复审者看不到本对话，只按 [independent-review.md](independent-review.md) 读证据。把 `<run-dir>` 的绝对路径和需要重点看的风险交给它，再把它的发现纳入判断。
   - **Claude Code**：交给 `pi-reviewer` 子代理（`.claude/agents/pi-reviewer.md`）。
   - **Codex**：另开只读会话，例如：
     ```bash
     codex exec --sandbox read-only -o .agent/reviews/<task-id>/<attempt>-independent.md "按 .agents/skills/review-pi/independent-review.md 复审 <run-dir 的绝对路径>；重点：<风险>"
     ```
     它读完证据后只输出结论与发现，由你决定是否采纳。
7. **写复审报告**：按 [review-template.md](review-template.md) 写到 `.agent/reviews/<task-id>/<attempt>.md`，其中 `Verdict:` 一行只写一个结论。
8. **记录结论**：
   ```bash
   bash scripts/dispatch-pi.sh verdict <run-dir> --verdict <结论> --review <报告路径> [--class <失败分类>] [--human-minutes <分钟>]
   ```
   - 工具会执行 G0–G6 机械门禁，并把报告复制、计算哈希。
   - PASS 被拒绝时不要绕过。只有用户（或已有的授权）明确接受某项缺口时，才改用 `ACCEPTED_WITH_EXCEPTION --waive G<n>=<理由> --decided-by <决定者>`。
   - REVISE / BLOCKED / ESCALATE 必须带 `--class`。分类见 gates.md。
9. **后续动作**：
   - **PASS / ACCEPTED_WITH_EXCEPTION**：只做合同 `integration` 中已授权的动作。
     - `local_branch`：`bash scripts/dispatch-pi.sh branch <run-dir>`，会基于候选树创建提交与本地分支，不推送。
       - 它需要 Git 作者身份：没有配置 user.name / user.email 时，先提供 GIT_AUTHOR_* 与 GIT_COMMITTER_* 环境变量。doctor 会提前提示身份缺失。
       - dispatch.config.json 的 `commit_trailers` 是仓库级的固定尾注。本次规划端与其中的署名不符时，用 `--no-config-trailers` 去掉它们，再用 `--trailer "Key: value"`（可重复）写上实际的署名。
     - commit / open_pr / push / merge / deploy：只在已授权时做。核对暂存文件列表与候选补丁一致，不要 `git add -A`。
     - 主分支已前进或需要解决冲突时，要在组合结果上重新运行受影响的检查。
     - 并行批次：
       - HEAD 仍是基线时第一个候选可以 `git merge --ff-only`；HEAD 已因合同提交前进时每个候选都 `git cherry-pick`（它们的父提交是同一基线；`branch` 的输出会给出合适的命令）；
       - 全部集成后在组合结果上跑一次全量测试并记录；
       - 本批所有 run 结束之前不要合并，见 dispatch-pi 技能的“并行批次”。
     - 挑入之前先确认要挑入的提交不碰工作区里有本地改动的文件（例如只差换行符的文件）。git 会在那个提交之前停下，只留下 `.git/sequencer`，没有 `CHERRY_PICK_HEAD`；这时 `git cherry-pick --continue` 会把被挡住的提交当作已处理跳过，接着去挑下一个，结果冲突。做法：先处理那个文件（只差换行符时，按约定统一它的换行符），再 `git cherry-pick --abort` 回到起点，完整重挑。KitExperiment ledger-cli 实机。
     - 完成后运行 `bash scripts/dispatch-pi.sh mark <run-dir> INTEGRATED --ref <提交或 PR>`，ref 写实际集成的提交（cherry-pick 后的新提交）。
   - **REVISE**：按 [rework.md](rework.md) 决定从原基线重做，还是在候选上继续，然后用 plan-task 出 vN+1。
     - 预算用尽、剩余部分又小而明确时，可以由规划器在返工提交上直接补齐，作为单独的提交，并按同样的验收标准检查（检查、全量测试、必要时变异检查）。
     - 超时（TIMEOUT）而候选已经完整时，缺的只是执行报告：规划器逐项复审代替报告，写进复审记录，直接集成返工提交，不必为一份报告再派一轮（见 dispatch-pi 技能的 [troubleshooting.md](../dispatch-pi/troubleshooting.md)）。
     - 集成后运行 `bash scripts/dispatch-pi.sh mark <run-dir> SUPERSEDED --ref <集成提交> --reason "<由谁、怎样收尾>"`。这样这个 attempt 不再显示为待集成，其他任务 prepare 时也不会再提示范围重叠。
   - **BLOCKED / ESCALATE**：向用户说明阻塞点与需要的决定，不要自行扩大授权或更换模型。
   - 不再需要 worktree 时：`bash scripts/dispatch-pi.sh cleanup <run-dir>`。证据保留在 `.agent/runs/`。
     worktree 里有候选之外的改动时，cleanup 会列出（`LOSS …`）并拒绝执行。先保存需要的内容，确认放弃后才加 `--force`。
10. **回复用户**：结论、每个 DoD 的证据（检查 ID 与结果）、越界与残余风险、已做和待做的集成动作。

指标汇总：`bash scripts/dispatch-pi.sh metrics`（方案第 13 节口径）。
