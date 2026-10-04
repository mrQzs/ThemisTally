# KitExperiment 实机反馈（2026-10-04 至 10-05）

KitExperiment 是 Code-Kit v2 合同的标准库参考实现（SentinelMesh）。两个仓库于 2026-10-04 从 Windows 迁到 macOS 后，由 Claude Code（claude-opus-5-5）担任规划端，按 Code-Kit 流程继续推进；下文记录对 Code-Kit 有价值的观察。

本文不把少量任务概括成模型通用能力或通过率，并区分执行器、合同设计与调度工具三类问题。

环境：
- macOS 15.7.9 x86_64，Bash 3.2.57；
- Claude Code 2.1.289；pi 1.0.2；执行模型 `step/step-5-preview`，请求 thinking high（提供商未回报实际级别，费用记 unknown）；
- 调度器 pi_dispatch 2.2.2；
- 检查用共享 venv（Python 3.12.14 + pytest 9.1.1）。

## 任务记录

| 任务 / attempt | 独立检查 | 变异结果 | 结论 |
| --- | --- | --- | --- |
| pi-runtime-contract-port v1 a001（Windows 派遣，macOS 复审） | fresh 120 passed | 未运行（行为缺陷已定） | REVISE / EXECUTION_ERROR：reconcile 对空、缺失与不成形的观察放行重放；合同只给了意译接口 |
| pi-runtime-contract-port v2 a002 | fresh 158 passed | 合起来 26/26 + 追加 1/1；执行器文件单独 19/26 | ACCEPTED_WITH_EXCEPTION（固定 `/tmp` 文件，第二次）；集成 `2c3c115`，规划端补测 `8e09793` |
| runner-posix-cleanup v1 a001 | fresh 171 passed | 合起来 9/13；漏掉的 4 个由规划端补测，补后 6/6 | PASS；集成 `136657c`，规划端补测 `fd57f49` |
| posix-identity-env v1 a001 | fresh 215 passed | 22 个抓住 21 个（漏掉的是等价变异） | REVISE / EXECUTION_ERROR：`file_sha256(True)` 把 1 号描述符当作文件读完并关闭；含 NUL 的路径冒出 ValueError；执行器在临时副本里自做变异 |
| posix-identity-env v2 a002 | fresh 237 passed；规划端探针 4/4 | 只用执行器测试 11/16，加探针 12/16；漏掉的 3 个被另一条规则遮蔽，1 个等价 | REVISE / EXECUTION_ERROR（测试隔离）；预算用尽后由规划端补全 `2191050`（含独立复审发现的违反协议的映射），a001/a002 标记 SUPERSEDED |
| posix-supervisor v1 a001 | fresh：oracle 11 passed，全量 269 passed | oracle 加执行器测试 17/19；漏掉的 2 个是测试缺口 | REVISE / EXECUTION_ERROR：观察记录改写成 START_UNKNOWN，执行器测试也照此断言；发信号的 PermissionError 冒出（macOS 对只剩僵尸进程的组返回 EPERM）；第二次中断冒出 |
| posix-supervisor v2 a002 | fresh：探针 7/7，全量 282 passed | 合起来 29/30，追加 0/2；只用执行器测试 15/30（其中 14 个按分工由 oracle 与探针把守） | REVISE / EXECUTION_ERROR：中断落在截止时刻时，已被 CPython 回收的组长仍被判为未退出；轮询间隔用例与模块常量比较。预算用尽后由规划端补全 `cd7c918`，a001/a002 标记 SUPERSEDED |
| posix-reconcile-integration v1 a001 | fresh：oracle 11/11，全量 310 passed | 合起来 25/27（漏掉的是不可观察的 fsync 与被遮蔽的普通文件检查）；只用执行器测试 18/27 | ACCEPTED_WITH_EXCEPTION（内层类型校验超出合同、越出 worktree 的只读访问）；集成 `a2c0e71`。独立复审发现合同遗漏导致的失败开放（旧观察记录放行重放），由规划端在 `c12a88f` 修正并补测 |

## 有效的做法

- **逐项移植时，把参考实现做成 oracle**。runtime 移植的前四份合同都只给意译接口，执行器读不到参考，四个候选都与参考不同。v2 改为：
  - 基线里放冻结的参考源码与参考测试；
  - 规划端提交三个 oracle：逐字移植的参考测试、失败关闭用例、与参考逐项比较的差分测试；
  - 派遣前确认 oracle 在参考实现上全部通过、在基线上失败。

  结果一次完成，canonical 层与参考逐个定义的 AST 相同。写入 plan-task。
- **新行为用真实进程 oracle，并先用草稿修复验证**。runner 合同的 7 个场景都启动真实进程树，并在规划端草稿上先跑通：
  - 有一个取消场景起初在旧实现上意外通过：中断太早，进程树还没建立。改成“进程树就绪后再中断”的握手才可靠。
  - 教训：只在基线上验证“失败”不够，场景本身的前提也要核对。
- **执行器的输出截取写法**。固定 `/tmp/vNN.txt` 偏差出现两次后，合同模板与 AGENTS.md 补上了合规写法。之后三次运行（identity a002、supervisor a001 与 a002）执行器都改用 `T=$(mktemp -d)` … `rm -rf "$T"`，规则生效。
- **探针用部分修复的草稿逐条验证**。supervisor v2 的 7 个探针：
  - 在基线上 5 个失败、2 个守护已有行为；
  - 在完整草稿上全部通过；
  - 三份只修一部分的草稿，各自只让对应规则的探针失败。

  这样派遣前就能确认每个探针把守的是哪条规则。
- **用真实信号测中断，并握手进入窗口**。探针向测试进程自己发 SIGINT，发送前用文件与进程状态确认被测代码已进入宽限等待或回收轮询；处理器只在被测调用期间生效。连跑 5 次结果一致，比只打补丁的写法更接近真实情况。
- **独立复审的内存探针**。复审者没有运行任何进程，用一个替身对象复现了“CPython 在截止时刻回收子进程后仍重新抛出中断”的边界情况，主审在固定候选上用 `python -B` 跑一遍即可确认。
- **独立复审能找出规划端自己的遗漏**。posix-reconcile-integration 的候选完全按合同实现，检查与变异都通过；独立复审仍找出了合同遗漏造成的失败开放（预先存在的观察记录），并给出探针。主审在固定候选上复现：进程确实运行了，判定却是 NOT_STARTED、允许重放。

## 执行器反复出现的偏差

- **固定临时路径**：pi-acceptance a002 与 runtime-contract-port a002 都把检查输出写到 `/tmp/vNN.txt` 再删除。合同模板补上合规写法后，下一次不再出现。
- **自做变异检查**：posix-identity-env a001 把仓库复制到 `T=$(mktemp -d)`，在其中以子进程跑 pytest，三轮共套用约 20 个自拟变异。
  - 这违反执行说明第 5、7、8 条，用时 1124 s（三份合同中最长）。
  - 执行说明本来就写了“验收端会做变异检查”，执行器仍然做了。合同模板现在在 Validation 一节里重复这条禁令，因为执行器会逐字读合同。之后三次运行都没有再出现。
- **推理正确，代码偏离，报告也不提**：supervisor a001 的推理中得出了第 8 条的正确读法（观察记录保留组长结局），代码与测试却写成相反的样子，报告没有列出合同问题。
- **上界断言与被测模块的常量比较**：supervisor a002 的轮询间隔用例拿每次休眠与 `_REAP_POLL_SECONDS` 比较，常量改大时用例照样通过。
- **执行报告的 JSON 写错**：supervisor a002 的报告末尾 JSON 多了一个值，调度器记为 json_invalid，门禁 G1 只作提示。正文与证据一致。
- **超出合同的解读写在 limitations 里，没有进 contract_conflicts**：reconcile-integration a001 自行加了内层类型校验，并把“删除 partial”解读为只删自己创建的。两处都在报告中如实说明了，但没有按 AGENTS.md 放进 `contract_conflicts`。

## 待改进（调度工具，`pi_dispatch.py` 锁定在 a4fa199，本次未改）

- **范围扫描漏报工作目录外的读取**。runner a001 的一条命令 `ls /usr/bin/python3* /usr/local/bin/python3* …` 列出了系统目录，`outside_worktree_paths` 为空，没有提示。
  - 当前扫描只看临时路径写法与工具调用的路径参数，shell 命令里的绝对路径读取不在范围内。
- **执行说明第 5 条**仍只要求“保留真实退出码”，没有给出合规写法。现在靠合同模板补充；解锁调度器时应同步进执行说明。
- **“rm -rf "$T" 必须是最后一步”的形式偏差**：执行器在删除之后追加只读命令（`date`、`git status`、`ps`），可疑命令扫描照常列出，复审只能人工判断。
  - 可以考虑把“删除之后只有不涉及 `$T` 的只读命令”标为备注而不是可疑命令；判断要保守，避免被构造的命令骗过。
- **`validate` 没有核对 Repository facts 中的 `.agent/` 文件是否在基线里**：posix-identity-env v2 要求执行器读取 v1 合同与上一轮复审，但侧分支基线中没有这两个文件，`validate` 没有提示；执行器只能在报告中说明。2.2.1 的“Repository facts 文件不在基线”核对可能跳过了规划路径。
- **`derive-json` 不覆盖已有 JSON，`validate` 也不比较“基线应失败”**。改了 Markdown 中检查行的“基线应失败”标注后，重新 derive 会因 JSON 已存在而拒绝（需要 `--force`）。`validate` 不比较 `expect_on_base`，于是 Markdown 与 JSON 的标注可以不一致而不被发现。
  - 本次影响只限 `baseline` 的期望标注，执行器看到的摘要相同。
  - 建议 `validate` 把检查行的“基线应失败”与 JSON 的 `expect_on_base` 一并比较。
- **跨机器复审可以运行，但没有提示**。在 macOS 上复审 Windows 派遣的 attempt 时：
  - in_place 检查因 worktree 不在本机而拒绝；
  - `check --fresh` 按记录的 `core.autocrlf=true` 快照，结果正确；
  - `verdict` 在 worktree 不存在时跳过重新快照，G6 只凭补丁往返校验，但没有在门禁备注里说明。

  建议补一条备注，并在 summary 中标出 attempt 来自另一台机器（`meta.json` 的 platform 与 repository 路径）。
- **`mutate` 把 pytest 会话中断也记为 caught**。supervisor a002 只用执行器测试时，变异让 KeyboardInterrupt 冒出测试，pytest 以退出码 2 结束，日志里只跑了 7 个用例，工具仍记为 caught。
  - 建议把退出码 2，或日志中的 `!!! KeyboardInterrupt !!!`，单独标为“会话中断”，不计入 caught。
  - 现在靠 mutation-check.md 提醒人工读日志。
- **合同附件名暴露主仓库的绝对路径**。执行器收到的是 `<file name="/…/KitExperiment/.agent/runs/<task>/attempt-001/plan.md">`。reconcile-integration a001 据此做了三件事：
  - 读取了主仓库的设计说明；
  - `cd` 到主仓库，执行 `git log`、`ls`、`wc`、`git branch -a`、`git status --short`；
  - 把主仓库约 30 个未提交文件的名称与全部分支名发给了提供商。

  主仓库没有被修改，读到的设计说明与基线相同。之前的运行没有这样做，说明执行器会用到它看到的任何路径。
  - 建议附件只用 `plan.md` 这样的相对名称，或者把合同复制到 worktree 里被忽略的位置；
  - 执行说明写明“只读写 worktree 内的路径”；
  - 范围扫描把 shell 命令里的 `cd <绝对路径>` 也计入 `outside_worktree_paths`。这一次只有 read 工具那一条被记录。

## 合同设计的教训（规划端）

- **草稿验证统计失败用例时要算子测试**：pytest 的子测试失败显示为 `SUBFAILED`，只 grep `FAILED` 会漏掉。合同写“20 个函数失败”，实测为 34 个。
- **“至少包括：- X”的列表会被读成目标语义**：列出要改掉的旧断言时，要写明“下列旧断言是错的”。
- **合同测试清单要覆盖每条规则**：runner 合同把多数规则交给 oracle，变异检查发现 oracle 也没覆盖 4 条（组级 SIGTERM、PermissionError 视为存活、回收组长、优雅超时不重复输出），由规划端补测。
- **进程与信号类合同要写明平台语义与中断语义**。supervisor v1 合同有两处遗漏，都在复审时才发现：
  - 没写 macOS 的 EPERM：只剩未回收僵尸进程的组，`killpg` 返回 EPERM。这在规划端实测后才确认，已集成的旧 runner 也有同一缺陷（`74b4d62` 修正）。
  - 没定义清理阶段的第二次中断。

  v2 补上后，纯 Python 吸收中断的残留窗口也应在合同里写明。写入 plan-task。
- **时间规则要两侧把守**：v2 探针只断言了“中断后没有提前结束”，“中断后重置截止时间”的两个变异因此存活，由规划端补测。写入 plan-task。
- **落盘与重放判定类合同要核对“失败时判为 X”是否与判定规则一致**。reconcile-integration 合同第 3 条写“观察记录写入失败判为 START_UNKNOWN”，但第 4 条的判定规则遇到预先存在的旧观察记录时会读它，结果是失败开放。草稿与 oracle 都没覆盖这个前提，是独立复审发现的。同一合同还漏了 FIFO 阻塞、读写上限与 close 错误，以及监督器 `worktree_id` 的字符规则与 `ProcessIdentity` 不一致。写入 plan-task。
