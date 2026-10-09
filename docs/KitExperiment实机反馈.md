# KitExperiment 实机反馈（2026-10-04 至 10-05）

KitExperiment 是 Code-Kit v2 合同的标准库参考实现（SentinelMesh）。两个仓库于 2026-10-04 从 Windows 迁到 macOS 后，由 Claude Code（claude-opus-5-5）担任规划端，按 Code-Kit 流程继续推进；下文记录对 Code-Kit 有价值的观察。

本文不把少量任务概括成模型通用能力或通过率，并区分执行器、合同设计与调度工具三类问题。

环境：
- macOS 15.7.9 x86_64，Bash 3.2.57；
- Claude Code 2.1.289；pi 1.0.2；执行模型 `step/step-5-preview`，请求 thinking high（提供商未回报实际级别，费用记 unknown）；
- 调度器 pi_dispatch 2.2.2（2026-10-06 起先后为 2.3.0 与 2.4.0，见下文“待改进”）；
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
| scheduler-supervised-transitions v1 a001 | fresh：oracle 10/10，全量 345 passed | 合起来 15/16（漏掉的是等价变异）；只用执行器测试 12/16 | REVISE / EXECUTION_ERROR：str 子类（含 `StrEnum`）通过 `isinstance` 检查，先改账本，再在事件编码时报错；一条测试顺序写反 |
| scheduler-supervised-transitions v2 a002 | fresh：探针 7/7，全量 357 passed | 合起来 22/23（漏掉的是等价变异）；只用执行器测试 19/23 | PASS；集成 `12ba34f`，规划端补测 `68b6e05`（`True` 代际、身份检查顺序、Python 3.10 的 `StrEnum` 回退） |
| supervised-operation-bridge v1 a001 | fresh：oracle 13/13，全量 386 passed | 合起来 14/15（漏掉的被另一条规则遮蔽）；只用执行器测试 10/15 | ACCEPTED_WITH_EXCEPTION（又一次经附件路径只读访问主仓库）；集成 `dc06d57`。独立复审发现子进程能伪造“未启动”的记录，由规划端在 `368b91a` 改为以监督器返回的事实为准并补测 |
| scheduler-exact-inputs v1 a001 | fresh：oracle 56/56，全量 463 passed | 合起来 36/36；只用执行器测试 4/36（合同让执行器测的 `None`、`5` 分辨不出精确类型） | REVISE / EXECUTION_ERROR：`observe` 收到不可哈希的 dimension 冒出 `TypeError`（违反合同第 2 条）；三处测试名不副实 |
| scheduler-exact-inputs v2 a002 | fresh：探针 2/2，全量 465 passed | 合起来 37/37（含“撤回修正”）；只用执行器测试 19/37 | PASS；连同 oracle、a001 与探针集成为 `3cd668d`…`44d9dd2` |
| adapter-protocol-port v1 a001 | fresh：参考 oracle 18、差分 oracle 9，全量 502 passed | 合起来 10/10；只用执行器测试 3/10（行为一致性由两份 oracle 把守） | PASS；逐字移植 Code-Kit 的 adapter 边界，集成 `928145a` |
| adapter-supervised-run v1 a001 | fresh：oracle 16/16，全量 534 passed | 合起来 17/18（漏掉的是检查顺序，只有多故障用例才看得出）；只用执行器测试 9/18 | PASS；集成 `bba63ec`。独立复审发现桥接遇到非 str 的 `evidence_dir` 会让操作停在 HANDOFF_ACCEPTED，由规划端在 `9726844` 修正并补测 |
| supervisor-stream-facts v1 a001 | fresh：oracle 16/16，全量 565 passed | 合起来 33/37（M05 是规划端写错的插入式变异，M14 等价，M10、M24 是测试缺口）；只用执行器测试 5/37 | REVISE / EXECUTION_ERROR：`streams_match` 对含 NUL 或孤立代理字符的路径抛出，违反“从不抛出”；身份不符时，回滚按路径删掉了别人的文件。独立复审另发现，子进程一次 `ftruncate` 就能让监督器去读任意大小的稀疏文件。这是规划缺口，v2 把摘要上限定为 256 MiB |
| scheduler-operation-view v1 a001 | fresh：oracle 8/8，全量 554 passed | 合起来 11/11；只用执行器测试 7/11（构造函数上限与 rollover 顺序由 oracle 把守） | PASS；集成 `88dff4b` |
| supervisor-stream-facts v2 a002 | fresh：规划端测试 10/10，全量 579 passed | 合起来 30/32，补跑 1/1。M19 是规划端写错的变异；M09 漏掉，是因为规划端的顺序用例只是概率性的，补全之后变成确定性的。只用执行器测试 13/32 | PASS；连同 oracle、a001 与规划端测试集成为 `c3d8728`…`6a10888`。规划端补全 `d69d45d`：把取身份放进回滚的保护之内，补测 `lstat` 与“超过上限不打开”，顺序用例改为由测试发信号 |
| verified-review v1 a001 | fresh：oracle 16/16，全量 620 passed | 合起来 22/24（漏掉的两个都是等价写法：不可达的 `lstat` 错误、状态为 ok 时摘要必然相同）；只用执行器测试 10/24 | PASS；集成 `5a2eae7`…`69ddefc`。独立复审建议 REVISE：流核对在保护之外，中断会让操作停在 RUNNING。合同没有要求这一点，由规划端在 `4fb0ceb` 补全，并补测多故障下的检查顺序 |
| durable-ledger v1 a001 | fresh：oracle 16/16，全量 648 passed | 合起来 20/21（M05 是测试缺口：只按每行自己的 `previous` 核对摘要）；只用执行器测试 12/21 | REVISE：内存调用期间的中断让实例继续可用，此后的日志无法重放（合同缺口）；打开失败不关连接、冒出非账本错误、可能新建文件；创建失败的清理按“0 字节”判断，会删掉另一个创建者的账本 |
| durable-ledger v2 a002 | fresh：规划端测试 10/10，全量 663 passed | 合起来 34/36（“重放的任何异常”只能靠注入来守；“清理不删除”是测试缺口）；只用执行器测试 15/36 | REVISE / PLAN_ERROR：v2 的连接用 `os.path.abspath` 按字面消去 `..`，而 `lstat`、`O_EXCL` 与删除跟随符号链接，`a/link/../ledger.db` 让创建把账本表写进了别的程序的库；合同措辞与规划端草稿同样如此。另有四处低严重度偏离。预算用尽，连同 oracle、a001 与规划端测试集成为 `0583619`…`f041d46`，规划端补全 `bcf57d6`（补全后 41 个变异抓住 40 个，漏掉的已成等价写法） |
| restart-recovery v1 a001 | fresh：oracle 12/12，全量 702 passed | 合起来 40/40；只用执行器测试 35/40（漏掉的 5 个由 oracle 把守，取消分支的错误处理反过来只有执行器测试把守） | PASS；集成 `8d9af39`…`49e40d4`。独立复审发现命令列表先检查后复制（只在调用方并发修改时可达）、两个测试缺口（中断推迟到循环结束、描述先于 guard 校验）与合同隐含的桥接变化，规划端补全 `b9a68be`（补全后 42 个变异抓住 41 个，漏掉的只在并发时有差别） |
| request-resume v1 a001 | fresh：两份 oracle 27/27，全量 739 passed | 合起来 29/30（漏掉的“运维名接受子类”与 `_runtime_text` 的精确类型检查重复，等价）；只用执行器测试 25/30 | PASS；集成 `6d4bb29`…`74b9e47`，规划端补全 `0419531`（五对检查顺序的用例）。独立复审发现两个合同缺口：恢复只比对第一个停止原因，后来叠加的显式暂停会被一并清掉（中）；账本记得已运行过的操作仍可判为未启动，未补记的用量按 0 计（低）。交给后续合同 |
| resume-holds v1 a001 | fresh：三份 oracle 36/36，全量 762 passed | 合起来 23/23；只用执行器测试 22/23（“先查冲突再查状态”由 oracle 守住） | PASS；集成 `9d2220e`…`2eb579a`，规划端补全 `84c9a57`（先复制再检查不为空、测试默认值每次新建）。独立复审发现用户决定的覆盖面不足：桥接事后才登记开始，运行中途崩溃的用量仍能判未启动归零；两次同文字的暂停合并成一项。交用户决定 |
| explicit-holds v1 a001 | fresh：四份 oracle 45/45，全量 785 passed | 合起来 9/9；只用执行器测试也是 9/9 | PASS；集成 `dd2d453`…`fe92d11`。独立复审发现规划端决定 P13（“`recover` 不改”）留下了绕过：换一代之后 `recover(NOT_STARTED)` 仍能把已判定的受监督运行判为未启动，执行器测试还把它当成了预期。规划端补全 `d26c986` 并更正为 P16 |
| ledger-cli v1 a001 | fresh：oracle 12/12，全量 832 passed | 合起来 17/18（“不关账本”两套测试都看不出：实例在函数返回时就被回收）；只用执行器测试 13/18 | PASS；用户先问“改成 TypeScript 怎么样”，规划端分析之后用户选定 Python。集成 `2fec83a`…`33eb841`，规划端补全 `2e303d0`：`resume` 预读改变了报错先后、空证据被换成算出来的摘要、提交之后的输出失败像参数错误、关闭与非最终用量没有测试。集成时一个只差换行符的本地文件挡住了多提交挑入，`--continue` 跳过了被挡的提交，`--abort` 后重挑 |

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
- **调度工具 2.3.0/2.4.0 的改动实机生效**（scheduler-exact-inputs 两轮）：
  - 附件改从中性临时目录附上之后，两轮都没有工作副本外路径，也没有访问主仓库；此前 reconcile-integration a001 与 bridge a001 都经附件路径读过主仓库。
  - 执行器截短输出时用的正是执行说明第 5 条的写法，`rm -rf "$T"` 之后没有再接命令。
- **账本比较连同精确类型**：scheduler-exact-inputs 的 oracle 用一个把每个值的类型一起记下的函数比较整个账本，str 子类换掉同值的 str 也能发现。
  - 每个被拒绝的调用之后，还在同一账本上执行一次合法调用。
  - 17 份只修一部分的草稿，各自只让对应规则的用例失败。
- **逐字移植加差分 oracle 再次一次完成**：adapter-protocol-port 把 Code-Kit 的 adapter 边界冻结为参考。
  - 差分 oracle 加载冻结的源码，只改写包内 import，并断言每处改写恰好一次；
  - 在描述符、调用、规范化与穷举的结算序列上逐项比较，包括错误码与消息；
  - 候选与参考逐字一致，只差模块文档字符串与 `__all__` 的换行。

## 执行器反复出现的偏差

- **固定临时路径**：pi-acceptance a002 与 runtime-contract-port a002 都把检查输出写到 `/tmp/vNN.txt` 再删除。合同模板补上合规写法后，下一次不再出现。
- **自做变异检查**：posix-identity-env a001 把仓库复制到 `T=$(mktemp -d)`，在其中以子进程跑 pytest，三轮共套用约 20 个自拟变异。
  - 这违反执行说明第 5、7、8 条，用时 1124 s（三份合同中最长）。
  - 执行说明本来就写了“验收端会做变异检查”，执行器仍然做了。合同模板现在在 Validation 一节里重复这条禁令，因为执行器会逐字读合同。之后三次运行都没有再出现。
- **推理正确，代码偏离，报告也不提**：supervisor a001 的推理中得出了第 8 条的正确读法（观察记录保留组长结局），代码与测试却写成相反的样子，报告没有列出合同问题。
- **上界断言与被测模块的常量比较**：supervisor a002 的轮询间隔用例拿每次休眠与 `_REAP_POLL_SECONDS` 比较，常量改大时用例照样通过。
- **执行报告的 JSON 写错**：supervisor a002 的报告末尾 JSON 多了一个值，调度器记为 json_invalid，门禁 G1 只作提示。正文与证据一致。
- **超出合同的解读写在 limitations 里，没有进 contract_conflicts**：reconcile-integration a001 自行加了内层类型校验，并把“删除 partial”解读为只删自己创建的。两处都在报告中如实说明了，但没有按 AGENTS.md 放进 `contract_conflicts`。
  - 之后合同在 Report back 里加了一句“任何解读写进 contract_conflicts 或 unresolved_questions”，接下来三次运行都照做了（例如 scheduler a001 把身份校验的先后写进了 `contract_conflicts`）。

- **工具名偶尔写成乱码**：durable-ledger a002 调用了 `ash_value`，resume-holds a001 调用了 `ash`，explicit-holds a001 调用了 `gash`——都是 `bash` 写坏了。每次都收到“Tool not found”，随即改用正确的工具，没有影响结果，只在 G1 记为工具错误。

## 待改进（调度工具）

`pi_dispatch.py` 原来锁定在 a4fa199（2.2.2）。2026-10-06 用户同意解锁，2.3.0 与 2.4.0 处理了下面全部各项，每项标注版本；做法与回放结果见 CHANGELOG。

- **范围扫描漏报工作目录外的读取**（2.3.0 修了主仓库路径；2.4.0 修完：shell 命令里系统目录、家目录、其他仓库或 worktree 的绝对路径也记为工作副本外路径，只作提示）。runner a001 的一条命令 `ls /usr/bin/python3* /usr/local/bin/python3* …` 列出了系统目录，`outside_worktree_paths` 为空，没有提示。
  - 原来的扫描只看临时路径写法与工具调用的路径参数，shell 命令里的绝对路径读取不在范围内。用 2.4.0 回放这次运行，命令里的三个路径都会列出。
- **执行说明第 5 条**原来只要求“保留真实退出码”，没有给出合规写法，靠合同模板补充（2.4.0 已修：执行说明写进合规的截短写法）。
- **“rm -rf "$T" 必须是最后一步”的形式偏差**：执行器在删除之后追加只读命令（`date`、`git status`、`ps`），可疑命令扫描照常列出，复审只能人工判断。
  - 可以考虑把“删除之后只有不涉及 `$T` 的只读命令”标为备注而不是可疑命令；判断要保守，避免被构造的命令骗过。
  - 2.4.0 的处理：扫描不放宽，执行说明写明删除之后不再接任何命令。2.1.0 的 Codex 审查表明，这类“安全清理”判断能被构造的命令骗过；“删除之后只剩只读命令”同样要靠 shell 解析。
- **`validate` 没有核对 Repository facts 中的 `.agent/` 文件是否在基线里**：posix-identity-env v2 要求执行器读取 v1 合同与上一轮复审，但侧分支基线中没有这两个文件，`validate` 没有提示；执行器只能在报告中说明。2.2.1 的“Repository facts 文件不在基线”核对可能跳过了规划路径。
  - 2.4.0 已修：路径规则原来要求首字符是字母或数字，点目录下的路径从未核对。现在不在基线里的规划文件单独提示；用全部合同回放，只在 posix-identity-env v2 上提示。
- **`derive-json` 不覆盖已有 JSON，`validate` 也不比较“基线应失败”**。改了 Markdown 中检查行的“基线应失败”标注后，重新 derive 会因 JSON 已存在而拒绝（需要 `--force`）。`validate` 不比较 `expect_on_base`，于是 Markdown 与 JSON 的标注可以不一致而不被发现。
  - 本次影响只限 `baseline` 的期望标注，执行器看到的摘要相同。
  - 建议 `validate` 把检查行的“基线应失败”与 JSON 的 `expect_on_base` 一并比较。
  - 2.4.0 已修：Markdown 写了而 JSON 不同是错误，只有 JSON 写了是警告，错误信息提示用 `derive-json --force` 重新生成。posix-identity-env v2 的 V06 现在报错。
- **跨机器复审可以运行，但没有提示**。在 macOS 上复审 Windows 派遣的 attempt 时：
  - in_place 检查因 worktree 不在本机而拒绝；
  - `check --fresh` 按记录的 `core.autocrlf=true` 快照，结果正确；
  - `verdict` 在 worktree 不存在时跳过重新快照，G6 只凭补丁往返校验，但没有在门禁备注里说明。

  建议补一条备注，并在 summary 中标出 attempt 来自另一台机器（`meta.json` 的 platform 与 repository 路径）。
  - 2.4.0 已修：
    - summary 记下派遣环境；
    - `check` 与 `verdict` 打印来源提示，G0 留备注；
    - worktree 不存在时，G6 写明只凭补丁往返校验。
- **`mutate` 把 pytest 会话中断也记为 caught**（2.3.0 已修：记为出错并写明原因）。supervisor a002 只用执行器测试时，变异让 KeyboardInterrupt 冒出测试，pytest 以退出码 2 结束，日志里只跑了 7 个用例，工具仍记为 caught。
  - 建议把退出码 2，或日志中的 `!!! KeyboardInterrupt !!!`，单独标为“会话中断”，不计入 caught。
  - 现在靠 mutation-check.md 提醒人工读日志。
- **合同附件名暴露主仓库的绝对路径**（2.3.0 已修：附件放在中性的临时目录；访问主仓库判 G2 不通过）。执行器收到的是 `<file name="/…/KitExperiment/.agent/runs/<task>/attempt-001/plan.md">`。reconcile-integration a001 据此做了三件事：
  - 读取了主仓库的设计说明；
  - `cd` 到主仓库，执行 `git log`、`ls`、`wc`、`git branch -a`、`git status --short`；
  - 把主仓库约 30 个未提交文件的名称与全部分支名发给了提供商。

  主仓库没有被修改，读到的设计说明与基线相同。之前的运行没有这样做，说明执行器会用到它看到的任何路径。
  - 建议附件只用 `plan.md` 这样的相对名称，或者把合同复制到 worktree 里被忽略的位置；
  - 执行说明写明“只读写 worktree 内的路径”；
  - 范围扫描把 shell 命令里的 `cd <绝对路径>` 也计入 `outside_worktree_paths`。这一次只有 read 工具那一条被记录。
  - **第二次（bridge a001）**：合同的 Forbidden 已经明文写“不访问工作副本以外的路径（包括主仓库）”，执行器仍在会话开头用主仓库路径读了设计说明与一个模块，之后才改用相对路径。这说明光在合同里禁止不够，需要在调度器里修：解锁 `pi_dispatch.py` 后，附件改用相对名称，并把读主仓库的工具调用标为违规。

- **`mutate` 的日志按清单位置编号**（2.4.1 已修：每行结果写出位置编号与日志路径）：日志名是 `M01.log`…（按位置），清单名称里自带的编号与它无关。在清单中间插入一项后，名称里写着 M37 的变异，日志是 `M17.log`；抽查时容易看错文件。CAUGHT/MISSED 行也不打印日志文件名。建议每行结果附上日志文件名。
- **只插入代码的变异**（2.4.2 已修：开头给出 WARN，结果行与记录都标出）：supervisor-stream-facts 复审时，一条“回收之前计算事实”的变异在回收之前多算了一次，回收之后的计算还在。结果是漏掉，规划端几乎把它当成测试缺口。`new` 包含完整的 `old` 就是这种情况。这类变异不能一律拒绝，因为“在前面插入一个提前返回”是正当的变异，所以只提示。
- **修这些问题时发现的回归**（2.4.0 已修）：bbe0121（2026-10-03）起，validate 与 prepare 不再显示合同校验本身的警告，例如必要检查没有被 DoD 引用。这与 KitExperiment 无关，是给 `expect_on_base` 加“只有 JSON 写了”的警告时发现的。

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
- **“是 str / dict / int”要写成精确类型**：scheduler 合同只写“是 str”，执行器用了 `isinstance`。str 子类（包括 `StrEnum`）通过检查后先改了账本，再在事件规范化时报错，违反“被拒绝的调用不改变账本”。v2 写明 `type(x) is str`。同时，测试用到 `StrEnum` 这类 3.11 才有的标准库特性时，要对照项目声明的最低 Python 版本（3.10）给出回退。写入 plan-task。
- **被监督进程能写证据目录**：bridge 合同规定“由落盘记录决定”，子进程却能伪造“未启动”的观察记录，或删掉交接记录再锁住目录，让一次确实运行过的进程被释放。实时路径应以监督器返回的事实为准，并要求落盘记录与之一致；只有恢复路径只能看记录，在同账户环境下要写明“记录只是关联证据”。写入 plan-task。
- **一条规则覆盖多个参数时，测试清单要逐个参数列出**：scheduler-exact-inputs 合同写“不可哈希的值也照常报表中的 code”。
  - oracle 只对 operation id 用了不可哈希的值，Step 3 也没有点名其他参数。
  - 结果 `observe` 先用 dimension 查字典，list 冒出 `TypeError`；变异检查没发现，是规划端自查与独立复审确认的。
  - v2 要求表中每个参数各一个 list 用例。写入 plan-task 的 test-design.md。
- **由被测对象控制的上界不是上界**：supervisor-stream-facts v1 合同只写了“摘要读到 `fstat` 报告的大小为止”。可是子进程拿到的写描述符不带 `O_APPEND`，一次 `ftruncate` 就能把输出文件变成任意大小的稀疏文件，自己什么都不写。监督器随后要读满它，内存也随之增长，“在有界时间内报告”的保证就没有了。v2 由规划端写死上限（256 MiB，超过时不做摘要）。写入 plan-task 的 test-design.md。
- **“从不抛出”要点名路径参数**：含 NUL 或孤立代理字符的 str，会让 `os.open` 抛出 `ValueError` 或 `UnicodeEncodeError`，而不是 `OSError`。posix-identity-env a001 与 supervisor-stream-facts a001 两次漏在这里。写入 test-design.md 的类型矩阵。
- **检测到替换之后按路径回滚，删的是别人的文件**：钉住时发现路径上已经不是自己创建的文件，这恰恰说明此时按路径 `unlink` 会删掉替换上来的文件。回滚与清理要先用 `lstat` 核对身份，一致才删除。
- **往“出错必须落定”的序列里加步骤，要写明它也受保护**：verified-review 合同在 `mark_running` 之后加了一步流核对，却只列出钩子、`candidate_hash` 与 `finish` 抛出时的处理。核对要把两个流各重读一遍，中断落在这里，操作就停在 RUNNING。执行器照合同字面实现，问题在合同，所以由规划端补全，结论判 PASS。写入 plan-task。
- **分给执行器的用例要能分辨规则**：v1 让执行器测 `None`、`5` 这类非 str 值，它们在旧实现上就会被拒绝，测不出“`isinstance` 改成 `type is`”。
  - 只用执行器测试时，36 个变异只抓住 4 个。
  - v2 改用不可哈希的值，能抓住“查字典之前没有检查类型”，执行器测试抓住 19 个。
- **返工合同的基线常常不含上一版合同与复审记录**：v2 基线建在上一轮候选上，v1 合同与复审记录却在 master 上，晚于基线提交。
  - 调度工具 2.4.0 的 validate 会提示这种情况，执行器也不得去主仓库读。
  - 做法：v2 照录 v1 的全部规则，把复审发现写进 Repository facts。
- **跨模块的结算时机要先在草稿上跑通**：adapter-supervised-run 最初的设计是运行结束后再记用量。草稿跑 oracle 才发现，`finish()` 检查预算时用量不是最终值，会把整个 request 永久停止。
  - 改为借桥接的 `candidate_hash` 挂钩：它只在结束复审的路径上、操作还是 RUNNING 时被调用。
  - 合同把这条事实与挂钩的时机写进 Repository facts，执行器一次写对。
  - 只读模块文档、不跑端到端，看不出这类问题。
- **被遮蔽的守卫要单独构造输入**：这一轮有三处检查一开始测不出来。
  - 链接指向 `/dev/null` 时，普通文件检查也会拒绝，测不出 `O_NOFOLLOW`；改为指向伪造的完整事件流。
  - adapter 对未结算的结果本来就清空用量，测不出“只在已结算且完整时记用量”；改用返回指定结果的子类 adapter。
  - 交接前的入口检查后面还有一道精确类型检查，单点出错时观察不到差别；要用多故障用例锁住合同写明的顺序。
  - 写入 plan-task 的 test-design.md。
- **设计说明与合同要一起改**：durable-ledger 的设计说明写着“排序键”“幂等重放的 claim 不记”，合同写的正相反，执行器按合同实现并指出了矛盾。写入 plan-task。
- **“先执行、后记录”的第一步也要受保护**：持久账本先调内存 Scheduler 再追加日志。v1 只让追加失败使实例失效，内存调用期间的中断却让实例继续可用，之后的日志无法重放。写入 plan-task。
- **路径不能按字面规范化**：`os.path.abspath` 按字面消去 `..`，内核却先跟随符号链接再处理 `..`；同一个路径交给两套解析，检查、创建、删除的与实际打开的可能不是一个文件。v2 合同只写“先转成绝对路径”，执行器与规划端草稿都用了 `abspath`，是独立复审发现的。写入 plan-task 与 test-design.md 的路径矩阵。
- **对现有代码等价的兜底规则，用注入钉住**；**重复的检查要变异它们共用的东西**。写入 review-pi 的 mutation-check.md。
- **测“吞掉错误”要让错误出在最后一个元素上**；**测“出错时关闭连接”要留住真实对象**，否则垃圾回收会替实现关掉它。写入 test-design.md。
- **独立复审中断时续跑**：这一轮复审代理先后被限流和一次认证错误打断，两次都用 SendMessage 续跑，它从中断处接着读完候选并给出结论。
- **集成之后在真代码上重验草稿**：restart-recovery 的草稿建在 durable-ledger 的规划端草稿上。durable-ledger 集成之后，把草稿移植到 master，重跑 oracle、全量与偏差清单，合同里的数字（682 passed、38 个偏差）才对得上实际代码。
- **测“出错即停”要让其余元素真实执行**：执行器与 oracle 的中断用例都看不出“循环结束再抛出”，是独立复审用变异体证明的。写入 test-design.md。
- **恢复路径只处理旧控制器没来得及判定的操作**：已判为 `START_UNKNOWN` 的不按记录重判，因为那个判断用到了监督器在内存中的观察，记录却是子进程也能写的。写入 plan-task。
- **比对式的守卫要比对完整的状态**：恢复只比对第一个停止原因，叠加的显式暂停被一并清掉，是独立复审发现的。写入 plan-task。
- **检查顺序要两两组合地测**：合同写明了顺序，就为每一对相邻检查配一个两个错误同时出现的用例。写入 test-design.md。
- **把用户决定写成合同前，先查清决定里每个条件在代码里何时成立**：“账本见过运行”取决于账本何时登记开始，而桥接是事后补登记，最常见的崩溃恰好不在覆盖面内。写入 plan-task。
- **写“X 不改”之前，列出所有能产生同一结果的入口**：explicit-holds 的“`recover` 不改”留下了第二条路，是独立复审发现的。写入 plan-task。
- **多提交挑入被本地改动挡住时不要 `--continue`**：它会把被挡住的提交当作已处理跳过。先处理那个文件，再 `--abort` 完整重挑。写入 review-pi。
- **关闭类规则要留住实例来测**；**入口的必填参数要查下游是否把空值当缺省**；**提交之后的失败不能与参数错误共用退出码**。写入 test-design.md 与 plan-task。

## 2026-10-08 至 10-09：回到 Windows，Pi 原生事件转换

两个仓库于 2026-10-08 从 macOS 整体复制回 Windows（Windows Server 2025，Administrator 账户），规划端换成 Claude Code 2.1.295（claude-fable-5-1）。

环境：
- pi 0.99.2（macOS 上最后是 1.0.4）；执行模型仍是 `step/step-5-preview` · high；doctor 与两步 smoke 通过；
- 系统 Python 3.12.10 + pytest 9.1.1，没有 venv；Git 2.55，`core.autocrlf=true`，工作区干净；
- 调度器 pi_dispatch 2.4.2。

### 迁移后的基线

- 全量在本机第一次跑：557 passed / 251 skipped / 33 failed。33 个失败没有一个是产品语义问题：`process_identity` 按 `:` 切 PATH、boot id 没有 Windows 分支、chmod 0 在 Windows 上挡不住读取；`durable_ledger` 的测试用 `/dev/fd` 数描述符、用 `SIGKILL`、用只读目录拒写、依赖符号链接后 `..` 的内核语义、依赖 NTFS 不接受孤立代理字符；`adapter_run.read_stream` 用 `O_NOFOLLOW`。规划端按监督器测试已有的写法给 19 处加了 `@unittest.skipIf(os.name != "posix", …)`（两个类、一个类、十六个方法），单独提交；之后 551 passed / 286 skipped。写入 check-pi-env。
- 规划端自己的两个失误：把 pytest 的 `--basetemp` 放进仓库，`test_baseline_rejects_non_repository` 因此失败（它要求临时目录不在任何仓库里）；Windows 控制台是 cp1252，打印非 ASCII 的 Python 一行脚本直接报错，要设 `PYTHONUTF8=1`。写入 AGENTS.md 模板与 check-pi-env。

### 任务记录

| 任务 / attempt | 独立检查 | 变异结果 | 结论 |
| --- | --- | --- | --- |
| pi-native-events v1 a001（pi 0.99.2，Windows，912 s，0 工具错误） | fresh：oracle 26/26，执行器 22/22，全量 599 passed / 288 skipped | 合起来 35/36（漏掉的“交给父类的是拷贝”是执行器的空断言，规划端补全后 36/36）；只用执行器测试 26/36（10 个按分工由 oracle 把守） | ACCEPTED_WITH_EXCEPTION（豁免 G5：合同点名的拷贝用例写成空断言，实现正确）；集成 `0ab0211`…`301857c`，规划端补全 `a97f3cd`。独立复审另找出四处合同没写明的读法（畸形首头算不算头、终止后非对象帧的检查先后、超长标识符由归约器拒绝、摘要的二次退路），记为规划端决定并钉进 oracle。规划端在本机对 31 次完整流复核，与调度器全部一致 |

### 有效的做法

- **调度器录下的真实流就是录得证据**。`.agent/runs/*/attempt-*/events.jsonl` 是 Pi `--mode json` 的 stdout 原样（`run` 以 `xb` 打开它作为子进程 stdout），本机有 30 次真实 Step 运行（pi 1.0.1/1.0.2/1.0.4，两个平台）。Pi 原生事件转换这条线因此不需要调用 provider：
  - 仓库里放缩减脚本 `tests/fixtures/pi_native/reduce.py`，从 attempt 目录生成缩减流与 meta（来源、pi 版本、平台、原文件 sha256，以及调度器的汇总）；每一帧与全部结构字段保留，只省略流式更新帧（每条消息、每次工具调用各保留首尾两条）并截短长字符串；
  - `events-summary.json` 里调度器自己算的用量、消息数、工具调用数、工具错误数、终止事件，是另一份代码的独立结果，oracle 拿它当差分对照；
  - 规划端专用测试 `tests/test_pi_events_captured.py`：有 `.agent/runs` 时对 30 次完整流复核，并断言完整流与缩减流翻译结果相同（除带行号的事件 id）；执行器的 worktree 里它只会跳过，合同写明这是预期；
  - 体积：缩减后每份 97–356 KB，主要是结构而不是文本，原拟的 300 KB 上限按实测改成 400 KB。写入 plan-task。
- **草稿上的偏差检查**：`mutate` 只接受 attempt 目录，规划端用同一种清单格式写了一个小脚本在草稿上跑，32 个偏差 31 个抓住，漏掉的“空工具名”当场补进 oracle 再跑到 32/32。写入 mutation-check.md。

### 执行器的偏差（本轮）

- **合同点名的用例写成空断言**：合同 Step 3 写了“`run` 传给父类的是事件的拷贝”，执行器的用例把父类收到的事件与**另一次** `translate()` 的结果比身份，永远不同，什么都测不出；fresh 检查看不出，只用执行器测试的变异检查也看不出（对应变异在两轮里都存活），是独立复审读了变异日志才指出的。写入 test-design.md。
- **裁定留在思考里**：事件流第 27093 行执行器自己裁定了合同第 7 条（终止之后的帧都是未知帧）与第 9 条（不是对象的帧是畸形帧）对同一输入的先后，报告的 `unresolved_questions` 却是空的，`contract_conflicts` 只写了字段顺序。合同 Report back 已经写了“任何解读写进 contract_conflicts 或 unresolved_questions”，这是第二次出现“推理里裁定、报告不提”（上一次是 supervisor a001）。调度器的备注抓到了 8 处歧义提及并提示核对，这次靠独立复审读事件流才确认。
- 其余都好：范围干净，没有临时路径，没有自做变异，报告 JSON 合法，执行器指出了设计说明与合同的字段顺序不一致并按合同实现。

### 规划端的教训（本轮）

- **合同里两条规则对同一输入都适用时要写明先后**：“终止之后的任何帧都是未知帧”与“不是对象的帧是畸形帧”都没说谁先，执行器只能自己选。写入 plan-task。
- **设计说明和 oracle 要一起提交**：oracle 提交进基线后又改了设计说明（缩减阈值 96/80 → 64/48），基线里的设计说明因此落后，执行器据实指出。写合同之前核对基线里的设计说明就是最新的。
- **错误原因文字用全等**：oracle 自己也用了前缀匹配，“assistant content” 同时匹配两种 reason。写入 test-design.md。
- **变异漏掉的归因要在复审里再想一遍**：主审先把 M33 归为“等价变异（父类不改输入，拷贝与否不可观察）”，独立复审指出这是执行器用例写错了：用 mock 截获 `run` 内部那次翻译就能观察。“不可观察”多半是“测试没找对观察点”。

### 待改进（调度工具）

- `mutate` 可以接受一个树（`--tree <路径>`）而不只是 attempt 目录，规划端验证草稿时就不用另写脚本。
- 歧义提及的备注可以把“judgment call”“I'll note this as an interpretation”这类执行器自己宣布裁定的短语单独标出，和一般的“在检查一致性”分开。
- `doctor` 不带 `--provider/--model` 时不做执行模型与凭据检查（`executor_*` 三个键不出现），输出里也没有提示“未检查执行器”；技能写了要带参数，但容易漏。建议在 `notes` 里写一句。
