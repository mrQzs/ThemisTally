# KitExperiment 实机反馈（2026-10-04）

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

## 有效的做法

- **逐项移植时，把参考实现做成 oracle**。runtime 移植的前四份合同都只给意译接口，执行器读不到参考，四个候选都与参考不同。v2 改为：
  - 基线里放冻结的参考源码与参考测试；
  - 规划端提交三个 oracle：逐字移植的参考测试、失败关闭用例、与参考逐项比较的差分测试；
  - 派遣前确认 oracle 在参考实现上全部通过、在基线上失败。

  结果一次完成，canonical 层与参考逐个定义的 AST 相同。写入 plan-task。
- **新行为用真实进程 oracle，并先用草稿修复验证**。runner 合同的 7 个场景都启动真实进程树，并在规划端草稿上先跑通：
  - 有一个取消场景起初在旧实现上意外通过：中断太早，进程树还没建立。改成“进程树就绪后再中断”的握手才可靠。
  - 教训：只在基线上验证“失败”不够，场景本身的前提也要核对。
- **执行器的输出截取写法**。固定 `/tmp/vNN.txt` 偏差出现两次后，合同模板与 AGENTS.md 补上了合规写法。下一次执行器全部改用 `T=$(mktemp -d)` … `rm -rf "$T"`，规则生效。

## 待改进（调度工具，`pi_dispatch.py` 锁定在 a4fa199，本次未改）

- **范围扫描漏报工作目录外的读取**。runner a001 的一条命令 `ls /usr/bin/python3* /usr/local/bin/python3* …` 列出了系统目录，`outside_worktree_paths` 为空，没有提示。
  - 当前扫描只看临时路径写法与工具调用的路径参数，shell 命令里的绝对路径读取不在范围内。
- **执行说明第 5 条**仍只要求“保留真实退出码”，没有给出合规写法。现在靠合同模板补充；解锁调度器时应同步进执行说明。
- **“rm -rf "$T" 必须是最后一步”的形式偏差**：执行器在删除之后追加只读命令（`date`、`git status`、`ps`），可疑命令扫描照常列出，复审只能人工判断。
  - 可以考虑把“删除之后只有不涉及 `$T` 的只读命令”标为备注而不是可疑命令；判断要保守，避免被构造的命令骗过。
- **跨机器复审可以运行，但没有提示**。在 macOS 上复审 Windows 派遣的 attempt 时：
  - in_place 检查因 worktree 不在本机而拒绝；
  - `check --fresh` 按记录的 `core.autocrlf=true` 快照，结果正确；
  - `verdict` 在 worktree 不存在时跳过重新快照，G6 只凭补丁往返校验，但没有在门禁备注里说明。

  建议补一条备注，并在 summary 中标出 attempt 来自另一台机器（`meta.json` 的 platform 与 repository 路径）。

## 合同设计的教训（规划端）

- **草稿验证统计失败用例时要算子测试**：pytest 的子测试失败显示为 `SUBFAILED`，只 grep `FAILED` 会漏掉。合同写“20 个函数失败”，实测为 34 个。
- **“至少包括：- X”的列表会被读成目标语义**：列出要改掉的旧断言时，要写明“下列旧断言是错的”。
- **合同测试清单要覆盖每条规则**：runner 合同把多数规则交给 oracle，变异检查发现 oracle 也没覆盖 4 条（组级 SIGTERM、PermissionError 视为存活、回收组长、优雅超时不重复输出），由规划端补测。
