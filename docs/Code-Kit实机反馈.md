# Code-Kit 实机反馈（Code-Kit 在自己身上派发）

本文件记录用 Code-Kit 给 Code-Kit 自己派 Pi 干活的轮次：任务、检查与变异结果、执行器与规划端的偏差、回流到 kit 的改动。KitExperiment 上的轮次记在 [KitExperiment实机反馈.md](KitExperiment实机反馈.md)。

## 2026-10-15：安装与更新（kit-install，第一轮实战）

环境：Windows Server 2025，Python 3.12.10，pi 1.1.0，step/step-5-preview（thinking high），调度工具 2.8.0。用户决定让 Code-Kit 先在自己身上实战（PLan 里其余仓库都是别人项目的克隆）。设计说明 → AskUserQuestion 四问（均选推荐项）→ 一份合同。

### 任务记录

| 任务 / attempt | 独立检查 | 变异结果 | 结论 |
| --- | --- | --- | --- |
| kit-install v1 a001（600 秒，0 个工具错误，越界 0，报告三条 limitations） | fresh：oracle 16/16，执行器 5/5，全量 1471 passed / 7 skipped，7/7 | 一份清单两条命令 38 条：oracle 加执行器测试 38/38；只用执行器测试 9/38，漏掉的 29 条全是事先标好的“合同留给 oracle”，意外 0 条 | PASS；集成 `9cc19ef`，规划端补全 `1b905bc` |

### 2.8 的新命令第一次实机

- **多命令变异清单**：一份清单两条命令，38 条变异各套用一次；29 条标了 `expect_missed: ["executor"]`。汇总直接给出“预期 29，意外 0”，这一轮没有一条需要手判（serve-loop 那轮要手判 20 条）。
- **`review-draft`**：复审记录里基线、候选、模型、用时、token、门禁的机械部分、DoD 的检查结果与目的、变异计数、执行器自述、摘要的关注项都已填好，剩 18 处判断；`review-brief.md` 直接交给独立复审子代理。
- **`integrate`**：第一次实机：在当前 master 末端（合同提交 `5f38569`）上用 `git merge-tree` 预演合并，在临时副本里跑合同的 7 项检查（含约 6 分钟的全量）全部通过后快进到 `9cc19ef`；自动标记 INTEGRATED（完整提交号）并清理执行 worktree，主工作区没有经过 cherry-pick 的中间状态。署名用 `--trailer` 加上。原来的 branch → cherry-pick → 全量 → mark → cleanup 五六条命令成了一条。

### 有效的做法

- **草稿树上的全量抓到了环境问题**：草稿只多两个新文件，全量却失败 6 项——v2 的测试按字节核对插件说明与探针证据，系统级 `core.autocrlf=true` 下新检出的 worktree 把它们转成 CRLF。主工作区里这些文件恰好是 LF，所以一直没暴露；不修的话，每一次 `check --fresh` 与 `integrate` 的全量都会失败。基线前用 `.gitattributes` 修好（`c2eb96b`）。
- **草稿阶段的变异要先问数据能不能区分**：35 条里 34 条抓住，漏掉的“复制 `__pycache__`”是 oracle 的缓存目录里只放了 `.pyc`，被 `.pyc` 规则先挡住；在缓存目录里再放一个非 `.pyc` 文件就分开了。
- **Windows 上先造 junction**：junction 不是符号链接，只认 `S_ISLNK` 的实现拦不住它；oracle 在 Windows 上先建 junction，“只认符号链接”这条变异才被抓住。

### 执行器的偏差（本轮）

- 无越界、无工具错误，600 秒（上限 1800）。467 行，比合同估计的 250 行长（文档串与 helper），功能没有扩大；三条 limitations 属实。
- **R1（中，规划问题）**：写入用的临时文件名不在写前检查里，独立复审发现、规划端实测确认——目标里一个同名的符号链接会让 kit 字节写到仓库外。合同规定了“先写临时文件再 `os.replace`”却没把临时文件名列进第 6 条，规划端草稿与 oracle 一样漏了，所以不算执行错误；规划端补全修正（`lexists` 先查、`O_EXCL` 新建），oracle 补用例。
- R2、R3、R5（低）：git 不在 PATH、记录嵌套过深、kit 缺文件时抛堆栈；AGENTS.md 标题只认行首 `## `（合同要求整行去空白比较）；文档串把 kit 叫成 PI-Kit。补全都已修正，前两类各有 oracle 用例。
- R4（报告纪律）：`kit_commit` 只在 kit 根是 Git 根时记录——取舍合理，但只在思考里决定，没写进 `unresolved_questions`；12 条测试命令经 `| tail` 掩盖了退出码（合同明确禁止）。
- R6：执行器拒绝用例的断言落在别的目录上，补全加了合法基线与“不存在的目标没被创建”。

### 规划端的教训（本轮）

- 推荐实战目标时说错了一件事实：把 hermes-jev-skills 说成“你自己的活跃项目”，它其实是别人项目的克隆。推荐项目之前先核对 `origin` 与本地有没有自己的提交。
- 合同的 Forbidden 写了“命令与探针里不另建临时目录”，与合同自己的检查说明（允许 `T=$(mktemp -d)` 截短输出）矛盾；执行器的两条安装探针照 AGENTS.md 的写法用了 `mktemp -d`。合同里不要另加与标准说明冲突的规则。
- `review-draft` 骨架开头的说明注释里本身写着占位记号，verdict 按行拒收，填完判断也交不上；端到端测试一次替换掉所有占位，正好掩盖了它。2.9.0 改了注释措辞，测试加了这条断言。
- heredoc 里的反斜杠又一次被吞（`b"\0"` 变成了 NUL）：补丁脚本里要写反斜杠时用 `chr(92)` 或 Write 工具。

### 回流（本轮）

- Code-Kit 2.9.0：`kit_install.py`、doctor 的 kit 检查、`.gitattributes` 的字节文件、README 的两种用法、check-pi-env 第 9 步。
