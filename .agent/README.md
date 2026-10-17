# .agent 目录

| 路径 | 内容 | 版本管理 |
|---|---|---|
| `plans/<task-id>.vN.md` / `.json` | 任务合同，人读与机读成对出现 | 提交 |
| `reviews/<task-id>/attempt-NNN.md` | 复审报告，`verdict` 时会复制进证据目录 | 建议提交，作为审计记录 |
| `runs/<task-id>/attempt-NNN/` | 调度器生成的原始证据，只读 | **不提交**（已在 .gitignore 中） |
| `runs/_env/`、`runs/_reports/` | `doctor`、`smoke`、`metrics` 的 `--out` 输出（`--out` 只允许写到这两个目录） | 不提交 |
| `environment.md` | 环境事实（check-pi-env 技能生成） | 团队决定；包含机器相关信息 |
| `dispatch.config.json` | 执行模型允许列表、worktree 位置、环境变量过滤 | 提交；参考 `dispatch.config.example.json` |

## attempt 目录中的文件

| 文件 | 含义 |
|---|---|
| `meta.json` | 任务、版本、attempt 编号、基线、worktree 路径、合同哈希 |
| `plan.md` / `contract.json` | 派遣时的合同副本（哈希见 meta.json） |
| `state.json` / `history.jsonl` | 当前状态与状态历史（只追加） |
| `setup.json`、`setup/` | 准备命令的结果与日志 |
| `preflight/` | pi 帮助、版本、模型列表、凭据检查、上下文文件清单 |
| `claim/`、`claim/reservation.json` | 已领取标记（防止重复运行）与领取时预留的本轮时限；领取在 task 级锁 `.task.lock` 内完成 |
| `executor.json`、`instruction.md` | 实际使用的执行器配置，以及传给 Pi 的执行说明 |
| `run-started.json`、`run.json`、`pid.txt` | 命令、时限、移除的环境变量名、退出码、墙钟、是否超时或取消 |
| `events.jsonl`、`stderr.log` | Pi 的原始 JSON 事件流与标准错误 |
| `events-summary.json` | 完整性、最终 stopReason、实际模型、思考级别、用量与费用、可疑命令（含命中所在的行）、临时目录清理 |
| `executor-report.md` / `.json` | 执行器最后一条消息（自述，不是证据） |
| `candidate.json`、`candidate.patch`、`candidate.stat.txt` | 候选树 ID、完整二进制补丁（已做往返校验）、统计 |
| `changes.json`、`scope.json` | 变更列表与范围判定 |
| `observations.json` | 新增的被忽略文件、主工作区是否变化、测试弱化线索 |
| `summary.md` | 给复审者看的摘要 |
| `checks/NN/` | 每次独立检查的结果与日志；`mode` 为 in_place（执行 worktree）或 fresh（干净副本） |
| `verdicts/NN.json` / `.md` | 每次记录的结论、门禁结果与复审报告副本 |

证据目录与主工作区属于同一个操作系统账户，同账户的进程可以修改它们。无人值守或需要追责时，应由执行器无法写入的账户或服务保存证据（方案第 5.4、11.1 节）。
