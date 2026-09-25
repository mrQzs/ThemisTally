# 验收门禁、失败分类与结论

## 一、门禁：工具检查什么，复审者判断什么

| 门禁 | 调度工具的机械检查（`verdict` 时执行） | 复审者必须自己判断 |
|---|---|---|
| G0 输入一致 | plan.md / contract.json 的哈希与 prepare 时一致；基线提交存在 | 合同本身是否仍然正确，是否需要出新版本 |
| G1 执行完整 | 没有超时或取消；Pi 退出码 0；事件完整结束（支持 agent_settled 的版本必须以它结束）；最终 stopReason=stop；实际模型与合同一致；提供商回报的思考级别（若有）与合同一致；stderr 没有自定义模型 ID、无效思考级别或未知参数的警告 | 执行器的报告是否与证据相符（缺少报告只作为提示）；提供商未回报思考级别时，只能确认请求的级别 |
| G2 范围合规 | 没有越界：受保护路径、forbidden、不在允许集合、符号链接、子模块、依赖变更、未授权的 HEAD 移动 | 警告项：执行位变化、敏感配置、可疑命令、worktree 之外的路径、主工作区变化 |
| G3 行为正确 | 每个 DoD 引用的检查都已通过；引用 scope 的 DoD 没有越界 | 引用 review 的 DoD；检查用例是否真的覆盖了合同行为 |
| G4 回归检查 | 最近一次 check 针对当前候选、覆盖全部必要检查、全部通过；检查前没有候选之外的文件（否则 check 拒绝运行）；检查没有改动候选文件，也没有产生候选之外的新文件（缓存类文件除外） | 检查命令是否找到了预期的测试文件（不是 0 个测试）；在执行 worktree 中运行（in_place）时，被忽略的依赖或构建产物是否可能影响结果，必要时改用 `--fresh` |
| G5 质量复审 | 不做机械判断 | 测试是否弱化、是否造假，兼容性，残余风险（见第二节） |
| G6 可集成 | 当前 worktree 的候选文件与记录的候选一致；候选补丁存在、哈希未变且通过往返校验 | 集成目标分支与授权；是否需要在组合结果上重新检查 |

检查状态：`passed`、`failed`、`blocked`（无法运行）、`not_run`。必要检查处于 `blocked` 或 `not_run` 时不能算通过。

## 二、防止“虚假的绿色”（G3 / G5 复审清单）

- [ ] 检查真的运行了预期的文件和用例，数量合理，不是 0 个测试。
- [ ] 新增测试针对缺陷或新行为，断言有意义；测试调用次数的地方，断言的是次数而不只是结果。
- [ ] 修复类任务：回归测试在旧实现上会失败（必要时在基线 worktree 上运行一次确认）。
- [ ] 没有新增 skip、only、todo、xfail，没有删除或放宽断言，没有 try/catch 吞掉错误。summary 会列出自动识别到的线索，但仍需人工确认。
- [ ] 没有修改测试配置、锁文件、CI、lint 规则或快照（除非合同允许）。
- [ ] 没有为了让测试通过而写死值，也没有识别测试环境的特殊分支。
- [ ] 错误路径都能结束，不留下永不 resolve 的 promise；取消与并发路径与合同一致。
- [ ] 公开接口、数据格式、兼容性与 Non-goals 一致。
- [ ] 存在已知的基线失败时：比对具体用例与错误指纹，确认候选没有新增失败。不要笼统地写“原本就红”。
- [ ] UI 任务：截图或交互记录对应的是合同要求的业务路径。

只运行解决具体风险所需的检查，不要把每个小任务都升级成全仓库压力测试。

## 三、结论

| 结论 | 条件 | 工具要求 |
|---|---|---|
| `PASS` | G0–G6 全部通过，且复审没有发现需要修正的问题 | 门禁有任何失败都会被拒绝 |
| `ACCEPTED_WITH_EXCEPTION` | 某些门禁未通过，但决定者明确接受 | 每个失败门禁都要有 `--waive`，并提供 `--decided-by`；与 PASS 分开统计 |
| `REVISE` | 差异可以在合同范围内定点修正 | `--class` |
| `BLOCKED` | 缺少需求决定、环境或权限，不能继续 | `--class` |
| `ESCALATE` | 需要重新判断方案、模型能力或预算 | `--class` |

高影响的必要项被豁免时，一律用 ACCEPTED_WITH_EXCEPTION，不要记为 PASS。`metrics` 的通过率只计 PASS，豁免接受单独列出。

## 四、失败分类（`--class`）

| 分类 | 例子 | 下一步 | 是否计入代码失败 |
|---|---|---|---|
| `PLAN_ERROR` | 接口签名写错、验收项互相矛盾 | 规划器修订合同 | 单独统计 |
| `EXECUTION_ERROR` | 漏掉边界、实现与合同不符 | 定点返工 | 是 |
| `INFRA_FAILURE` | 限流、凭据、测试数据库未启动 | 修复环境；必要时有限退避 | 否 |
| `SCOPE_VIOLATION` | 修改调度脚本、增加依赖、写到 worktree 之外 | 停止并评估影响，再决定返工或终止 | 是，单独标记 |
| `REQUIREMENT_BLOCKED` | 合同没有定义的错误行为 | 先定清楚行为 | 否 |
| `TIMEOUT` / `BUDGET_EXCEEDED` | 达到运行上限 | 评估剩余工作：拆小或 ESCALATE | 单独统计 |
| `CANCELLED` | 用户取消或任务撤销 | 保留结果 | 否 |

不要因为网络失败就更换模型或提供商：这会改变费用、隐私与能力边界。

## 五、attempt 状态

| 状态 | 何时进入 | 之后可以到 |
|---|---|---|
| `PREPARING` | prepare 开始 | `PREPARED` / `PREPARE_FAILED`；prepare 中途崩溃时可 `mark … ABANDONED --force` |
| `PREPARED` | worktree 与 setup 就绪 | `RUNNING`（预检失败时保持 `PREPARED`，不计次数）/ `ABANDONED`；已领取但 Pi 未启动时，用 `collect --recover` 转为 `INFRA_FAILURE` |
| `PREPARE_FAILED` | setup 失败或改动了已跟踪文件 | `ABANDONED`（修正后重新 prepare） |
| `RUNNING` | attempt 已领取，Pi 在运行 | `COLLECTING`；调度器异常退出时用 `collect --recover`，确认进程已结束后也可 `mark … ABANDONED --force` |
| `COLLECTING` | Pi 已结束 | `NEEDS_REVIEW` / `TIMEOUT` / `CANCELLED` / `INFRA_FAILURE` |
| `NEEDS_REVIEW`、`TIMEOUT`、`CANCELLED`、`INFRA_FAILURE` | 证据已收集 | verdict 记录的五种结论 |
| `PASS` / `ACCEPTED_WITH_EXCEPTION` | verdict | `INTEGRATED` / `ABANDONED` |
| `REVISE` / `BLOCKED` / `ESCALATE` | verdict | `ABANDONED`；返工另建新版本合同与新 attempt |

每次重新执行都是新的 attempt，旧目录不清空、不覆盖。合同层面的 DRAFT / READY，由 `validate` 是否通过来体现。
