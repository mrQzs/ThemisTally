# .agent 目录

| 路径 | 内容 | 版本管理 |
|---|---|---|
| `plans/<task-id>.vN.md` / `.json` | 任务合同，人读与机读成对出现 | 提交 |
| `reviews/<task-id>/attempt-NNN.md` | 复审报告，`verdict` 时会复制进证据目录 | 建议提交，作为审计记录 |
| `design/` | 规划端的设计笔记与进度；属于规划路径，运行中改动只记为备注 | 提交 |
| `runs/<task-id>/attempt-NNN/` | 调度器生成的原始证据，只读 | **不提交**（已在 .gitignore 中） |
| `runs/<task-id>/binding-v<N>.json` | 按角色写的合同第一次 prepare 时记下的执行模型（3.0 第二轮），同一版本之后的 attempt 都沿用它 | 不提交（在 `runs/` 下）；不编辑，无效时按报错的提示处理 |
| `runs/_env/`、`runs/_reports/` | `doctor`、`smoke`、`metrics` 的 `--out` 输出（`--out` 只允许写到这两个目录） | 不提交 |
| `runs/_tmp/` | 规划端跑测试时 pytest 的临时目录（见 AGENTS.md） | 不提交 |
| `environment.md` | 环境事实（check-pi-env 技能生成） | 团队决定；包含机器相关信息 |
| `dispatch.config.json` | 执行模型允许列表、角色绑定（`runtimes`、`profiles`、`roles`、`presets`、`active_preset`）、worktree 位置、环境变量过滤、插件与决策模型的设置；只写环境变量名，不写凭据 | 提交；参考 `dispatch.config.example.json`；用 `config` 子命令修改 |
| `dispatch.local.json` | 本机 CLI 的命令路径（`config runtime add --command`），只对按角色写的合同与配置中心生效 | **不提交**；被跟踪、没被忽略或经过链接时不读也不写 |
| `config-history/`、`audit/` | 配置写入的快照与审计记录（`config history`、`config rollback`） | 不提交，不编辑 |
| `.config.lock/` | 配置锁 | 不提交 |
| `DECISIONS_OFF` | 存在时决策插件一票否决，相当于关闭 | 团队决定 |
| `kit-install.json`、`kit-backup/` | `kit_install` 的安装记录（每个文件的 sha256），以及 `--force` 覆盖之前的备份 | 团队决定 |

## attempt 目录中的文件

| 文件 | 含义 |
|---|---|
| `meta.json` | 任务、版本、attempt 编号、基线、worktree 路径、合同哈希；按角色写的合同另有执行模型的绑定副本（`executor_binding`） |
| `source-status.z` | prepare 时主工作区的 `git status -z` 输出 |
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
| `report-status.json` | 执行报告的解析结果 |
| `candidate.json`、`candidate.patch`、`candidate.stat.txt` | 候选树 ID、完整二进制补丁（已做往返校验）、统计 |
| `changes.json`、`scope.json` | 变更列表与范围判定 |
| `ignored-before.json` | 运行前已被忽略的文件，用来找出运行中新增的被忽略文件 |
| `observations.json` | 新增的被忽略文件、主工作区是否变化、测试弱化线索 |
| `summary.md` | 给复审者看的摘要 |
| `decisions.jsonl` | 决策模型的问答记录（`decisions.mode` 为 shadow / on 时） |
| `checks/NN/` | 每次独立检查的结果与日志；`mode` 为 in_place（执行 worktree）或 fresh（干净副本） |
| `mutations/` | 变异检查（`mutate`），每次一个子目录 |
| `review-brief.md` | `review-draft` 生成的独立复审简报 |
| `verdicts/NN.json` / `.md` | 每次记录的结论、门禁结果与复审报告副本 |
| `branch-message.txt` | 为候选建提交（`branch`、`integrate`）时用的提交信息 |
| `integrations/NN/` | `integrate` 每次的验证记录（`integration.json`） |

证据目录与主工作区属于同一个操作系统账户，同账户的进程可以修改它们。无人值守或需要追责时，应由执行器无法写入的账户或服务保存证据（方案第 5.4、11.1 节）。
