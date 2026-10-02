# 07-T1A 实施边界决策记录

## 当前事实

- 当前基线是 `d1e6358`；没有 `.agent/plans/`、`.agent/reviews/` 或 07 的执行记录。
- `docs/code-kit-v2/07-workflows-and-scheduling-审阅增强版.md` 已随文档基线提交，但文首仍明确它不是可派遣合同；配套结果为 `PASS_REFERENCE_ONLY`，82/82 只覆盖离线合成参考。
- 规划基线 `d1e6358` 没有 `scripts/codekit/workflow.py`、工作流 schema 或 07 测试实现；当前工作区已有未提交的 T1A/T2 纯模型与受限账本原型。
- `.agent/dispatch.config.json` 将 `scripts/codekit/**`、`schemas/**` 及现有协议测试列为额外受保护路径。普通 Pi 合同不能靠 Scope 扩大这些路径。
- 文档重命名、索引修复和 `.agent/environment.md` 已在 `d1e6358` 冻结；后续实现不能再依赖未提交的设计文件。

## 推荐决定

先以主模型直接完成 07-T1A 的静态设计与实现，范围限于无模型、无网络、无外部副作用的工作流定义解析、两层 DAG 拓扑校验、端口绑定与固定 schema 引用；使用纯离线 fixture 和回归测试证明拒绝/接受行为。不要在这一阶段接入真实调度、Git 基线授权、预算账本、进程 handoff、重试或恢复。

原因是 T1A 的目标路径本身受保护，且其行为仍需要把增强版中的建议收敛为仓库 API；直接写 Pi 合同会违反当前保护配置或把未提交文档误当基线。T1A 通过后，再以已接受的提交为基线拆 T1B/T1C 或由用户明确调整保护和派遣策略。

## 原待决定事项（已解决）

1. 是否将当前 02–10 增强版文档及 `.agent/environment.md` 作为一次独立的文档基线提交后，再开始 07 实现。
2. 若不先提交文档，是否授权主模型直接在受保护路径实现 07-T1A（仍不派遣 Pi、不调用真实模型、不联网、不提交）。

## 已作决定

用户已选择先提交当前文档重命名与环境记录，再从新的提交重新规划 07-T1A。此次提交只冻结文档和规划输入；它不代表 07 已实现，也不把参考验证报告改写成生产通过。新基线建立后，继续保留“由主模型处理受保护核心路径、普通 Pi 不扩权”的边界。

## 新基线上的 07-T1A 计划草案

规划基线：`d1e6358`（文档/环境准备提交）。

### 交付目标

把工作流定义的首版结构收敛为可执行的本地校验契约：严格解析 `workflow-definition` 记录，校验工作流/任务/阶段的身份与版本、两层显式依赖的结构、具名输入输出端口、固定 `ResourceRef` 形状、写入范围、子预算和重试形状。校验器只返回结构/静态领域诊断，不启动模型、CLI、Git、网络或调度进程。

### 首轮允许的文件

- `scripts/codekit/workflow.py`：受保护的纯解析与结构校验入口；不改变 `protocols.py` 的既有行为。
- `schemas/workflow-definition-v1.schema.json`：受保护的严格 JSON Schema；未知字段和未知版本拒绝。
- `tests/test_workflow.py` 与 `tests/fixtures/workflow/`：合法样例及最小反例。

这些路径受 `.agent/dispatch.config.json` 的额外保护，不能生成普通 Pi 派遣合同；由主模型在本地实施授权内直接修改，或在另行批准后调整保护策略。当前计划不允许修改调度器、预算账本、进程监督、既有 01 测试或任何依赖。

### 行为与验收矩阵

| 规则 | 合法基线 | 唯一变化/预期结果 |
|---|---|---|
| 记录家族 | `record_type=workflow-definition`、`schema_version=1` | 未知家族/版本拒绝，不能回退旧解释 |
| JSON 入口 | 单个 UTF-8 文档、无 BOM/重复键/非有限数 | 各自破坏一个条件，返回稳定结构错误 |
| 身份与集合 | 非空唯一节点、阶段、端口及正整数版本 | 重复/缺失/错误类型逐项拒绝；数组顺序不产生业务拓扑 |
| 依赖图 | 所有边指向已声明对象、无自边/重复边/环 | 各自引入一个悬空边、自边、重复边或最小环，拒绝并指出对象 |
| 端口绑定 | 必需端口逐项绑定；任务输出只来自显式依赖 | 缺绑定、额外绑定、非依赖来源或未知端口，拒绝 |
| 资源与范围 | 固定小写 SHA-256 `ResourceRef`，仓库相对安全路径 | 摘要/路径/类型各自改变，拒绝；不重算摘要“修复” |
| 预算/重试 | 有限整数、非负、货币上限值为非负十进制文本 | bool/浮点/负值/非法货币格式分别拒绝；跨节点账本上限留到后续调度实现 |

### 验证命令

实现后先运行 `python -m unittest tests.test_workflow -v`，再运行既有 `python -m unittest discover -s tests -v`；输出必须显示非零数量的新增测试和全量测试成功。另做只读链接/JSON 解析检查。真实 03/04/05/06 接线、Git 基线授权、预算账本、Pi/Provider、平台和恢复验证继续记 `NOT_RUN`，不由 T1A 提前宣称。

### 退出条件

T1A 只有在合法/非法 fixture 全部通过、既有测试无回归、范围只触及上述文件、且没有模型/网络/外部副作用时结束。通过后再决定是否为 T1B（两层 DAG 语义）与 T1C（端口/类型/锁）分别写正式合同；不把 T1A 的结构通过当作可派遣或生产就绪。

### 当前实施状态

- 本地原型已写入上述首轮文件：解析入口委托 `protocols.strict_json_loads`，校验器复用 01 的身份、路径、整数和摘要规则，并返回冻结视图与确定性任务拓扑。
- 定向检查为 19 项通过；schema JSON、Python 编译和 diff 检查通过。schema 与 Python 的端口键、严格正则结尾和阶段 profile 已做结构一致性校验；`ResourceRef.path` 的安全词法仍以 Python 运行时校验为准，Schema 只表达可移植的基础形状。
- 在当前 PowerShell `python`（3.9.23）下运行全仓发现 640 项中 609 项通过、30 项跳过、1 项失败，唯一失败是既有 `test_F049_import_has_no_side_effects` 使用 `sys.stdlib_module_names`，该属性要求 Python 3.10+；在 bash 的 Python 3.12.3 下定向 T1A 测试 19 项通过。全仓结果不能记为无条件通过。
- T1A 本地实现仍未提交；全程未派遣 Pi 或调用模型、网络和外部系统。后续 T2B-G 的 Git 访问限于固定 plan 的只读 probe，并单独记录为未授权、未覆盖当前性的观察事实。

## T1C 静态增量边界

T1A/P1 收尾后，继续在同一受保护核心模块内推进一个不接运行时的 T1C 小增量：

- `schema_ref_identity` 与 `schema_refs_compatible` 只按 `(kind, id, sha256)` 判断，`path` 只作定位信息；不加载资源、不重算摘要。
- `resource_conflicts` 只比较跨任务声明：同路径或 tree 覆盖后代路径产生 scope 冲突，file/file 的不同兄弟路径不冲突；相同 `resource_keys` 产生独占键冲突；结果按任务和冲突字段稳定排序且不修改输入。
- `amount_to_units` 只做调用方给定小数位的精确十进制转整数，并执行 0–9 scale、格式、精度和安全整数上限检查；不引入币种默认精度、汇率、预留、账本或重试策略。

这一步仍只修改 `scripts/codekit/workflow.py`、`tests/test_workflow.py` 与既有 workflow fixture；平台大小写/符号链接解析、锁获取和租约、跨任务调度、预算账本与真实并行性留到 T2/T3。当前 T1C 定向测试为 22 项通过。

## T2A 纯就绪投影边界

在 T1C 的静态声明检查之上，新增 `scripts/codekit/readiness.py` 作为合成事实投影器。它只接受上游已经取得的完整布尔事实集合，按固定顺序计算 `can_refine`、`can_execute` 和 `WAIT_*` 理由；不采集事实、不验证 Git、权限、预算或能力，也不把结果当作执行授权。对应 6 项回归与 T1A/T1C 合并定向测试共 28 项通过。

## T2B-S 基线绑定结构层

在 T2A 之上先落一个不执行 Git 的结构层：`scripts/codekit/baseline_binding.py` 与 `schemas/baseline-binding-v1.schema.json` 定义 `baseline-binding` v1。记录固定 repo/environment 身份、Git object format、完整 commit/tree OID、上游结果引用、三种覆盖模式（`exact_tree`、`pinned_artifact_set`、`revalidated_integration`）、授权引用、观察证据和 guard 版本；Git OID 始终与普通文件 `ResourceRef.sha256` 分开校验。

该层只做严格字段、路径、引用和 OID 形状检查，并返回脱离输入且不可变的视图；不执行 `git`，不证明对象存在、祖先关系、tree/产物覆盖、授权、当前性或多上游合流。Python 运行时校验是安全路径与 object-format 交叉约束的规范入口；JSON Schema 保持结构闭合并表达可移植的基础形状，不能单独替代这些运行时约束（例如 `ResourceRef.path` 的保守路径规则和 `object_format` 对 OID 长度的关联）。后续 T2B-G 才能在明确仓库身份与无 fetch 的只读边界下接入 Git probe；无法核验的 replacement/grafts、浅克隆、promisor、submodule、LFS 和跨环境 common dir 情况保持阻塞。T2B-S 新增 10 项测试，与 T1A/T1C/T2A 合计 38 项定向测试在 PowerShell Python 3.9.23 与 Git Bash Python 3.12.3 下通过；Draft 2020-12 schema 在 Git Bash Python 3.12.3 下完成元校验并接受合法样例。既有 `tests.test_baseline_tool` 长测启动后超过两分钟无输出，已中止，未将其记为通过或失败。

## T2B-G 只读 probe 计划与解释层

`scripts/codekit/git_probe.py` 先实现纯的 `build_probe_plan` / `interpret_probe`。前者只接受已验证的 `BaselineBinding` 与独立登记的 `TrustedRepositoryIdentity`，生成固定 `git -C` argv、8 项重定向环境清理策略、禁止替换对象和 lazy fetch 的环境标记、超时与输出上限；不从路径或 `repo_id` 自行推导仓库身份。后者只解释注入的有界字节结果，分别保留 verified、blocked、unknown，检查仓库/对象格式、commit/tree 类型与 tree 一致性，并将 replacement refs、grafts、shallow、promisor、alternates、gitlink/.gitmodules、LFS 未知或存在列为阻塞/未知。

纯解释层不启动 Git runner，不证明接受、授权、内容 coverage 或 currentness，也不写 `can_execute`。受控 adapter 只执行固定 plan；当前 16 项 Git probe 测试与前述测试合计 54 项在两个 Python 运行时通过。

T2B-G 已补上受控 adapter：`run_probe` 使用固定 plan、`shell=False`、`stdin=DEVNULL`、登记 worktree cwd、环境清理和超时/输出截断；runner 可注入以便隔离测试。当前仓库只读试跑核对了提交/树对象和仓库身份，结果为 `repository_identity_match=true`、`object_format_match=true`、`base_commit_present=true`、`base_tree_present=true`、`base_tree_matches_binding=true`，但因 LFS 状态未接入而返回 `verified=false`、`unknown_reasons=[lfs_status_unknown]`；没有写入 Git 元数据。T2B-G 新增 adapter 与 LFS 证据扫描测试后，定向测试总数为 53 项，两个 Python 运行时均通过。


LFS 边界单独由 `inspect_lfs_evidence` 处理：调用方必须提供固定 tree 对应的 `.gitattributes` 和 blob 字节以及 complete 标记；发现 `filter=lfs` 或规范 pointer 则阻塞，扫描不完整、超限或格式不可读则保持 unknown，只有完整且无标记才返回 clean。adapter 不调用 `git-lfs`，默认仍把 LFS 事实留给受信上游，因此本机 probe 继续保持 `lfs_status_unknown`。

## T2B-C 固定内容覆盖与授权事实归约

新增 `scripts/codekit/coverage.py` 与 7 项测试，把 `exact_tree`、`pinned_artifact_set` 和 `revalidated_integration` 三种覆盖模式归约为固定事实检查。精确树要求候选 tree 与绑定 tree 相同；固定产物集要求路径、Git blob OID、文件摘要和 mode 的完整集合相同，拒绝临时删减或新增未声明路径；重新集成要求候选存在、集成接受和检查当前性都明确为真。祖先关系、授权和检查事实的 `false` 与 `unknown` 分开诊断，任何未知都保持 `BLOCK`；该层不执行 Git、不创建提交，也不自行授予授权。相关测试使当前定向集合达到 191 项，双 Python 运行时均通过。

## T2B-G-A 祖先关系只读探针

新增 `scripts/codekit/git_ancestor.py` 与 5 项测试，生成只包含完整 OID 的固定 `git merge-base --is-ancestor` 命令。解释器把退出码 0 归为 `ANCESTOR`、退出码 1 归为 `NOT_ANCESTOR`，把超时、截断、异常退出和非空标准输出归为 `UNKNOWN`；它不执行 fetch/commit，也不把祖先关系当作内容覆盖或使用授权。该结果可作为 `coverage.py` 的受信输入之一。

## T2C-S 纯领取与 handoff 边界模型

根据 07 的 4.3.4–4.3.7，新增 `scripts/codekit/claim_model.py` 与 9 项测试，先把不依赖存储和操作系统的边界固定下来：统一领取门禁合并幂等、活动 task、request/stop、代际、guard、合同、基线、上游接受、资源和预算事实；同一 `(repo, request, task)` 的活动操作在任何 plan version 下都阻止第二次领取；同键同指纹只允许 replay，同键不同指纹返回冲突；handoff 必须同时看到 request、stop、controller/claim generation、guard、租约、预算和资源事实为当前且明确；任何 unknown 都阻塞，不按 false 处理。进程释放采用三值 liveness，监督范围另行三值判断：handoff 后没有完整 NOT_STARTED 证据时保持 `START_UNKNOWN`，残留进程或监督范围不明时保持 `RECOVERY_REQUIRED`，只有明确的身份匹配、fencing、未启动证明和空范围证据才能进入 `CANCELLED_NOT_STARTED` 或 `RELEASE`。

这一步不接 `pi_dispatch.py`、SQLite、PID、OS 启动或外部授权，也不宣称目录 claim 已成为生产账本。当前审计记录的运行时缺口包括过期锁接管后旧 owner 可能删除新锁、同 task 活动 attempt 未形成持久唯一约束、`pid_alive=None` 被恢复入口当作可释放，以及重复 recovery 的幂等性不足；这些需要后续绑定 03–05 的真实事务与 handoff 接口后另立合同。T2C-S 新增 9 项后，T1A/T1C/T2A/T2B-S/T2B-G/T2B-G-A/T2B-C/T2C-S 定向测试共 75 项，在 PowerShell Python 3.9.23 与 Git Bash Python 3.12.3 下通过。

## T2C-L 受限 SQLite 账本原型

在纯模型之后新增 `scripts/codekit/scheduler_store.py`，只实现一个专用 SQLite 文件上的受限事实账本：显式 `BEGIN IMMEDIATE`、`foreign_keys=ON`、DELETE journal、`synchronous=FULL`；`claim` 在同一事务内写 operation、资源占用和 outbox，按数据库内的 controller/stop/guard 当前事实重新核验；活动 task 的部分唯一索引跨 plan version 生效；同键同指纹在作用域和预留/资源载荷一致时 replay，载荷变化冲突；handoff 只记录 `HANDOFF_ACCEPTED`，不声明 OS 进程已启动；可靠的未启动状态才可取消并释放占用。

该原型不实现真实授权、G0–G6、Git、预算计算、PID、OS handoff、usage 对账、恢复接管或生产迁移；预算、合同、基线和资源可用性仍由调用方以受限事实传入，缺省 handoff 事实保持 unknown。`tests/test_scheduler_store.py` 的 13 项测试覆盖事务回滚无部分占用、幂等/作用域冲突、跨 plan 活动唯一性、资源冲突、代际 fencing、stop、租约、outbox 一致性以及部分/无约束 schema 拒绝、坏行/损坏 JSON 检测以及同键新代际防重放。T2C-L 后，T1A/T1C/T2A/T2B-S/T2B-G/T2B-G-A/T2B-C/T2C-S/T2C-L 定向测试共 88 项，在两个 Python 运行时通过。
## T2D 受限并行 admission 模型

在 T2C-L 之后新增 `scripts/codekit/parallel.py` 与 11 项测试，先把并行入口限制在纯事实归约：资源声明按 repo、path/key 和 read/write/exclusive/unknown 模式规范化；路径只做分段前缀重叠判断，不解析平台别名、glob、符号链接或实际目录。当前 v1 工作流的 `write_scope` 映射为 write、`resource_keys` 映射为 exclusive；未知模式一律等待资源核对。

`admit_candidates` 按 priority 降序、admission sequence 升序、task/request/repo 稳定排序；对活动 hold 和同 repo 跨 request 的占用逐项检查；候选的 claims 全部可取时才加入结果，冲突或容量不足不会留下部分 hold。`REVIEW_PENDING` 等活动状态仍占 task 槽；相同 request/task 即使没有重叠资源也返回 `WAIT_TASK_ACTIVE`。并行度大于 1 且声明了资源时，需要与精确 scope_refs、guard_version 绑定的 `IndependenceProof`，否则保持 `WAIT_RESOURCE`。

该层还固定 `WAIT_RESOURCE`、`WAIT_BUDGET`、`WAIT_UPSTREAM`、`WAIT_CONCURRENCY`、`RECOVERY_REQUIRED` 和 `WAIT_NO_READY` 的局部理由；`no_progress_reason` 只有在调用方明确给出 `required_remaining=false` 时才返回 `COMPLETE_PROVEN`。它尚未接入 `scheduler_store`，也不证明 OS/worktree 锁、平台路径身份、动态接口或生产独立性。T2D 后定向测试为 99 项，在两个 Python 运行时通过；T3A 纯预算与计量投影随后补入。

## T3A 纯预算与计量投影

新增 `scripts/codekit/budget.py` 与 34 项回归测试，先把 07 的预算边界固定为不可变纯状态：`BudgetPolicy` 同时表达 request 上限与可选 task 上限，`reserve_for_operation` 原子地检查预留，`record_usage_observation` 只接受一条受信的 cumulative/final 序列，保留历史修订并要求显式 correction；未实现的 delta、provider alias、invoice 分摊和宽松 unknown 策略会拒绝。`settle_operation` 区分已闭合与 `unknown_liability`，`release_proven_unstarted` 只在明确给出未启动证明时释放。`BudgetSnapshot` 分别报告每个维度的 `known`、活动/未结 `held`、未知操作、`exposure=known+held`、`raw_remaining` 与 coverage；未知不补零，超限和未知责任会形成持久 stop reason，停止后仍可接收迟到事实。

观测的 request/task/operation 绑定、币种维度、修订冲突、同观测重放和稳定指纹均在纯层检查；`request_stop` 保留首个 stop epoch 并追加后续原因，实际超限仍保留原始事实并标记 `INTEGER_OVERFLOW`/预算停止。该层不调用 provider、Git、PID、OS 或 SQLite，不实现授权、真实账单、汇率、生产迁移，也未把 `protocols.usage_view()` 当作账本。T3A 定向测试在 PowerShell Python 3.9.23 与 Git Bash Python 3.12.3 均为 120 项通过（其中 T3A 新增 34 项）；后续仍需把纯投影接入受限 ledger，并在真实监督/恢复边界补集成验收。

## T3B 纯有限重试与 stop 归约

新增 `scripts/codekit/retry.py` 与 18 项回归测试。`RetryPolicy` 只登记机械尝试上限、整数退避、明确允许的 failure code 和事实序列截止点；`AttemptFact` 按稳定 request/task 跨 plan 累计 operation，`RetryContext` 要求在新领取前重新核验 request stop、预算、资源、上游、授权、恢复和 guard。`decide` 固定返回 `RETRY_ALLOWED`、`WAIT`、`STOP`、`NO_RETRY` 或 `EXHAUSTED`，未知的 stop/recovery/副作用/授权事实关闭处理；`START_UNKNOWN`、活动/已接受操作、不可重试故障、合同/基线/scope 缺陷和超限不会自动重跑。退避仅用有界整数，不改变模型、CLI、工具或合同。

这一步不分配 attempt/run ID，不写 SQLite，不启动或清理进程，也不提供 resume；正向结果只是交给独立 allocator 的授权事实。模型同时分开 task attempt 上限与 request dispatch 上限。T3B 定向测试在 PowerShell Python 3.9.23 与 Git Bash Python 3.12.3 均为 18 项通过。

## T3A-S SQLite 预算事实适配器

新增 `scripts/codekit/budget_store_v2.py` 与 12 项测试，作为独立的 schema v2 预算账本原型。它在 `BEGIN IMMEDIATE`、外键、DELETE journal 和 FULL synchronous 下保存 policy、operation、不可变 observation、current projection、stop reason 与 outbox；`reserve`、`observe`、`settle`、`release_unstarted`、`snapshot` 和 `stop` 都在同一事务内完成，支持重放/冲突、历史 revision、unknown、超限、迟到事实和原子回滚。schema 会拒绝缺表、坏约束、损坏 JSON、破坏不可变 observation 的已有数据库。

该适配器尚未接入 `scheduler_store.py` 的 claim/resource hold；两套账本之间仍存在 crash/超卖窗口，不能宣称 07 的生产调度原子性。现有 v1 store 没有迁移路径，不能直接 ALTER；下一步必须另立版本化的 claim+budget 同事务合同，补齐并发领取、资源 hold、attempt/run、handoff 和恢复接管的集成验收。T3A/T3B 与适配器合并定向测试在 PowerShell Python 3.9.23 与 Git Bash Python 3.12.3 均为 150 项通过。

## T3A/T2C-L 联合原子账本最小原型

在独立预算适配器之后新增 `scripts/codekit/atomic_claim_budget.py` 与 20 项回归测试，验证一个版本化 SQLite 账本可以在短 `BEGIN IMMEDIATE` 事务中同时保存 request/task/policy、operation、资源 hold、不可变 usage observation 与 outbox。`claim` 会在同一事务内重核对 controller/stop/guard、活动 task、request 并发上限和资源键，再由纯预算模型检查完整 reservation；任一预算或写入失败都会回滚 operation、hold 和事件。相同作用域、代际、guard、预留和资源载荷的 idempotency key 只 replay，一处变化返回冲突；不同 plan 不能绕过活动 task 唯一约束。

该原型不把财务 `final` 当作进程结束：usage observation 只更新预算投影，operation 与资源 hold 必须等待带 owner、generation 和 `cleanup_proven=True` 的显式 `finish_operation`；未启动取消仍要求独立证明。unknown、超限和取消后迟到事实分别保留 exposure、持久 stop 或 `RECOVERY_REQUIRED`。新增的 `handoff` 只在租约、owner、controller/claim generation、guard、stop、预算和资源事实仍有效时记录 `HANDOFF_ACCEPTED`，不启动进程；`mark_start_unknown` 会先确认内部资源 hold 完整，再停止 request 并保留资源风险占用，直到后续恢复裁决。已有半成品 schema、缺约束/外键/不可变触发器的数据库会拒绝打开；启动时还会逐行校验 JSON、观察指纹、资源 hold 与 stop reason 一致性，坏账本进入 `E_SCHEMA_INVALID`。资源键、观察载荷和 claim facts 仍按现有纯模型做边界校验。新增后，前述 T1A/T1C/T2A/T2B-S/T2B-G/T2C-S/T2C-L/T2D/T3A/T3B/T3A-S 与本原型的定向测试在 PowerShell Python 3.9.23 与 Codex bundled Python 3.12.14 均为 187 项通过；验收绑定层另有 8 项固定引用、上游闭包和追加撤销测试，恢复门禁另有 4 项，合计 195 项；环境记录的 Git Bash `python3` 为 3.12.3。

## T3A-A 固定验收与输入绑定

新增 `scripts/codekit/acceptance.py` 与 8 项测试，定义不可变 `accepted-result`、`input-binding-receipt` 和追加式 `acceptance-revocation` 记录。所有 candidate、check set、verdict、output 与 target schema 引用都要求固定 `(kind,id,sha256)`，拒绝 `latest`/`head`/`current` 别名；绑定时重新核对 request/task/plan/guard、source port 和上游 acceptance 闭包，缺失、冲突、环、跨请求、跨任务、跨版本或任一上游撤销均阻塞。该层只证明结构和引用关系，不执行检查、Git、授权或调度。

## T3C 纯恢复开放门禁

新增 `scripts/codekit/recovery.py` 与 4 项测试。`resume_decision` 要求 request 停止状态、当前 controller 代际、权限、未知启动、预算、锁、基线、接受链、资源/外部 scope 和显式 resume 授权全部为明确真值，并按固定顺序返回阻塞理由；它只投影受信事实，不清除 stop、不提高额度、不复活旧 attempt，也不执行进程清理。真实恢复仍需在权威账本中以 expected generation 做 CAS。

这是集成证据原型，不是生产调度器：它没有 PID 或 OS/worktree 锁、Git/currentness probe、provider/billing 认证、attempt/run 分配、boot identity、迁移工具或 crash recovery。账本现在提供受证明的 controller rollover、全局 outbox 高水位和 `reconcile_not_started` 最小接管路径，恢复模块也提供纯门禁投影，但仍没有真实进程身份、OS 清理或 resume CAS；`scheduler_store.py` 与 `budget_store_v2.py` 仍未迁移到该 schema。provider 经济身份/退款仍是后续边界。后续若继续推进，应把真实启动/恢复事实接入同一账本，并在固定候选上复审并发、故障恢复和权限边界。
