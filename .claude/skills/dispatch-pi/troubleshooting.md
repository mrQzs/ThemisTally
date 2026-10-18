# 派遣与执行排障

<!-- 3.0 第二轮（按角色写的合同）：
  以下 2、3 只在同一版本首次建立记录时出现；已有有效记录时沿用记录，当前绑定被删或未接通只打 NOTE。
  - “按角色写的合同需要 execution 角色的 headless 绑定”（退出 2）：config role set execution <profile>，或改成写死的合同；
  - “这个适配器本轮没有接通 execution”（退出 3）：绑定到 pi 适配器的 profile；
  - “角色绑定的配置无效”（退出 2）：config validate 看错误，修好再 prepare；
  - “版本记录无效 / 经过链接 / 合同 vN 的字节与首次派遣时不同”（退出 4，任何一次 prepare）：比的是冻结的合同 JSON；已派遣的版本不能改，出新版本合同；记录确认损坏时按提示处理，不要编辑 .agent/runs。 -->

先看 `<run-dir>/summary.md`，再按需看 `preflight/`、`stderr.log`、`events-summary.json`、`scope.json`。
进程退出码为 0 **不代表**任务成功：Pi 在 `--mode json` 下，即使最后一条 assistant 消息是 error 或 aborted，也会以 0 退出。

## 调度工具的提示

| 提示 | 原因 | 处理 |
|---|---|---|
| `计划标识不合法` | 不是 `task-id.vN`，也不是 `.agent/plans/` 下合同文件的路径 | 检查文件名与参数 |
| `合同文件必须位于 .agent/plans 下` | 传入的合同路径在其他目录 | 把合同放进 `.agent/plans/`，或直接传 `task-id.vN` |
| `… 第 N 行含不可见格式字符 U+200E …` | 编辑工具把转义序列（如 `\u200e`）写成了实际字符；Markdown 看起来与 JSON 一致，逐项比对却对不上 | 把字符改回转义文本；探针里需要这类字符时用 `chr(0x200E)` |
| `与未集成的 … 改动范围重叠` | 另一个任务最新的 attempt 尚未集成，且允许修改的文件与本合同重叠（同一任务较早的 REVISE attempt 不计入） | 把本任务放到下一批，等对方集成后以新 HEAD 为基线；确需并行时由后集成的一方负责合并。<br>那个 attempt 的候选若其实已经并入后续提交（例如由规划器补齐后集成），用 `mark … SUPERSEDED --ref … --reason …` 记录，提示随之消失 |
| `baseline` 提示“基线上已通过” | 探针在修复前就能通过，区分不了修复前后 | 改写探针，让它断言修复后的新行为；并标注 `expect_on_base: fail` |
| `Markdown 中 Vxx 的基线期望（…）与 JSON 的 expect_on_base（…）不一致` | 改了 Markdown 检查行的“基线应失败 / 基线应通过”，没有同步 JSON（2.4.0 起为错误） | 用 `derive-json --force` 重新生成 JSON，或手工同步；只在 JSON 写了的是警告，按约定在 Markdown 补上 |
| `Repository facts 提到的规划文件在基线 … 中不存在` | 合同引用的上一轮合同、复审记录或设计说明在基线之后才提交（2.4.0 起提示） | 改用包含它们的提交作为基线，或把需要的内容写进合同；执行器不得去主仓库读 |
| `attempt 在另一台机器上派遣`（`check` / `verdict` 的 NOTE） | attempt 在别的机器或别处仓库 prepare，执行 worktree 不在本机 | 用 `check --fresh`；verdict 的 G6 只凭候选补丁的往返校验，门禁备注会写明 |
| `合同无效：…ERROR…` | Markdown 与 JSON 不一致、占位符残留、受保护路径等 | 按错误修改合同；已派遣过的版本改为出新版本 |
| `请先把 .agent/runs/ 加入 .gitignore` | 运行证据可能被提交 | 追加 `gitignore.append.txt` 中的规则；装进目标仓库时 `kit_install.py install` 会自动追加（2.9.0） |
| `base_sha 在本仓库中不存在` | 示例或旧合同的基线 | 用 `git rev-parse HEAD` 核对后更新 |
| `基线提交中没有 AGENTS.md` | worktree 从基线创建，执行器看不到规则 | 先提交 AGENTS.md，再以新提交为基线 |
| `PREPARE_FAILED` | setup 失败，或 setup 改了已跟踪文件（如锁文件） | 读 `setup/*.log`；锁文件漂移要先在主仓库解决 |
| `PREFLIGHT 本机 pi 不支持参数` | pi 版本过旧 | 升级 pi（建议 ≥ 0.84，最低 0.80.4）后重跑 run |
| `PREFLIGHT 思考级别 … 不在本机 pi 支持列表` | 合同 thinking 值无效 | Pi 对无效值只警告并忽略，所以预检会拒绝；修正合同 |
| `PREFLIGHT 本机 pi 没有这些内置工具` | 工具名写错 | Pi 会静默丢弃未知工具名；修正合同 |
| `PREFLIGHT 模型 … 不在本机可用模型列表中` | 模型 ID 拼写错误、provider 缺少凭据，或未在 models.json 定义 | 运行 `pi --list-models step` 核对精确 ID；不要猜相近的 ID |
| `PREFLIGHT pi auth check 未就绪` | 凭据缺失或过期 | 按 provider 配置 API key 或登录；不要把密钥写进合同或报告 |
| `…与合同 executor.… 冲突` | 设置了 `PI_EXEC_*` 环境变量 | 以审阅过的合同为准，移除环境变量 |
| `不在 … allowed_executors 中` / `思考级别固定为 high` | 合同与 `.agent/dispatch.config.json` 的允许列表不符 | 修改合同，或经用户同意后修改允许列表 |
| `BUDGET_EXCEEDED` | 次数或累计墙钟达到上限 | ESCALATE；需要追加预算时由用户决定，并在新版本合同中写明 |
| `该 attempt 已被领取` | 重复运行同一个 attempt | 每次运行都要新建 attempt（prepare） |
| `候选文件已被修改` | 记录候选后，worktree 中的候选文件被改动 | 找出原因（后台进程、手工修改、检查写文件）；需要时重新派遣，得到新候选 |
| `参数 … 含批处理特殊字符` | Windows 上命令解析到 `.cmd` / `.bat` | 改用 node 或可执行文件的直接路径，或用 `PI_DISPATCH_PI_CMD` 指定 pi 的 node 入口 |
| `Markdown … 与 JSON … 不一致` | 两份合同中与执行相关的内容不同（命令、预算、授权、路径、执行模型） | 改到一致；已派遣过的版本出新版本 |
| `至少需要一个 required 为 true 的检查` | 合同只有人工复审点 | 补一条能自动运行的检查；做不到时这项任务不适合委派 |
| `任务锁被占用` | 同一 task 的另一个 run 正在领取 | 稍后重试；超过 5 分钟未释放会被视为过期；确认没有 run 时可删除 `.agent/runs/<task-id>/.task.lock` |
| `工作副本与候选不一致，检查结果无法代表候选` | check 前 worktree 出现候选之外的新文件，或候选文件被改动 | 查明来源：属于实现的，走返工；只是缓存或报告的，加入 `.gitignore` 或 `check_artifact_patterns`；也可以用 `check --fresh` |
| `检查产生了候选之外的新文件` | 检查命令写出了报告、快照或生成文件，G4 会失败 | 加入 `.gitignore` 或 `check_artifact_patterns`；写快照的检查要改为只读模式（如 `CI=1`） |
| `无法建立干净的验收副本` | `--fresh` 时补丁无法应用，或 setup 在干净副本中失败 | 读 `checks/NN/setup/*.log`；合同的 setup 要能在全新副本中准备依赖 |
| `LOSS …` 与 `拒绝清理` | worktree 里有候选之外的改动，或候选补丁不可用 | 先保存需要的内容；确认放弃后再 `cleanup --force` |
| `--out 只能指向 …` | 输出文件只能写到 `.agent/runs/_env/` 或 `.agent/runs/_reports/` | 改用这两个目录下的路径 |

## 执行完整性问题（events-summary.json 的 problems）

| 现象 | 优先检查 | 处理 |
|---|---|---|
| 最终 `stopReason=error` | `final_error`、`auto_retries`，以及 stderr 中的限流或鉴权信息 | 环境问题归为 INFRA_FAILURE，不算代码失败次数；不要因为网络问题就换模型 |
| `stopReason=length` | 输出被截断 | 任务过大：拆小，或减少上下文 |
| 最终消息的正文里有未执行的工具调用 | 模型把工具调用写成了文本（如 `<tool_call><function=edit>…`），Pi 没有执行，回合随之结束 | 这是模型输出格式问题，不是代码问题，候选只做了一部分。<br>- 用 `check --fresh` 看做到哪一步；<br>- 判 REVISE（EXECUTION_ERROR），出只收尾的新版本；<br>- 预算用完时，由规划器直接完成剩余的小部分，或 ESCALATE |
| 没有完整的结束事件 | 是否超时或被取消、事件流是否被截断 | 标为未完成，不能 PASS |
| 没有 agent_settled | pi ≥ 0.80.4 必须以它结束；只有 agent_end 说明事件流被截断或运行被中断 | 标为未完成，不能 PASS |
| 实际模型与要求不一致 | `actual_models`，以及 stderr 的 `custom_model_id` | 修正 provider/model；不采信这一轮的结果 |
| 提供商报告的思考级别与要求不一致 | 模型不支持该级别，被 Pi 或提供商调整 | 确认模型的思考级别映射，必要时更换模型并记录 |
| 思考级别“未回报” | 该协议或配置不回报 `providerThinkingLevel`（本机 Step 配置即如此），不是错误 | 只能确认请求的级别；anthropic-messages 预算模式下 high 对应 thinking 预算 16384 |
| 大量 `tool_errors` | 执行器命令用法、依赖缺失 | 缺依赖就补 setup；命令用法问题在合同 Steps 中说明 |
| `suspicious_commands` | git 写操作、依赖安装、网络下载、读取环境变量 | 结合 scope 与合同判断是否越权。`git stash list`、`git tag -l` 等只读命令不再计入 |
| `outside_worktree_paths` | 执行器访问了 worktree 之外的路径 | 看摘要标注的结果：<br>- “调用失败，路径不存在”多是执行器手写绝对路径时拼错（实机见过 `pi-worktres`），没有写入；<br>- “调用成功”的写入要立即检查目标路径，并按 SCOPE_VIOLATION 处理；<br>- “位于主仓库，G2 不通过”：执行器碰了主仓库（2.3.0 起），只能显式豁免；<br>- bash 记录带事件流行号（2.4.0 起）：命令里出现的系统目录、家目录、其他仓库或 worktree 路径，只作提示。多是测试数据里的字面量，按行号确认是否真的读写了。<br>读取随消息附上的 plan.md 或 instruction.md 属于正常行为，只记在“备注”中 |
| 执行过程中有 N 处提到合同的歧义、矛盾或一致性（摘要“复审需要关注”） | 执行器在推理或回复中提到合同的歧义或矛盾，但报告的 `interpretations`、`contract_conflicts` 与 `unresolved_questions` 都为空 | 读 `ambiguity_mentions` 摘录。<br>- 确属合同矛盾：由规划器裁定，必要时出新版本合同；<br>- 只是在检查、并没有发现问题，或只是领域用语（如对齐状态 ambiguous）：忽略。<br>关键词后面直接跟着独立否定答案的说法（如“inconsistencies: none found.”“矛盾：无。”），以及合同正文（停止条件与禁止事项除外）出现两次以上的词，会自动排除；只是在检查的句子仍会提示 |
| 执行器自行宣布了 N 处解读（摘要“复审需要关注”或“备注”） | 执行器在推理里写了“I'll go with…”“我理解为…”一类的裁定。报告的 `interpretations`（2.10.0）、`contract_conflicts`、`unresolved_questions` 都为空时进“复审需要关注”，否则是备注 | 用 `review-draft` 的骨架对照：报告的自定解读与事件流线索并排列出。逐条确认每处线索都已报告、做法在合同允许的范围内；没报告的写进复审。执行报告没有 `interpretations` 列表（旧格式，或写成了字符串）时摘要只有一句备注，只能从事件流核对 |
| 测试或检查命令的退出码被管道掩盖（摘要“复审需要关注”） | 执行器把检查命令接上 tail、head 这类管道，看到的是管道末尾命令的退出码；报告里的 `reported_exit_code` 是推断值 | 以 `check` 的结果为准，复审记录写明条数。2.10.0 起执行说明在每条检查下面给了“自检照抄”写法（`set -o pipefail;` 开头）；仍然出现时，在下一份合同的 Report back 里点名要求照抄 |
| 执行器在命令中创建或使用了系统临时目录（摘要“复审需要关注”） | 执行器用 tempfile、mktemp、`/tmp`、`$TEMP` 等在工作目录之外建了目录或读写了文件 | 按事件流行号看命令，先核对写法是否符合 AGENTS.md：只允许测试框架管理的临时目录，或在同一条命令里用 `T=$(mktemp -d)` 新建、以 `rm -rf "$T"` 作为最后一步。这种写法里的 `rm -rf "$T"` 也会列为可疑命令。<br>- 写法符合、只存放中间产物、也确实删除了：记为备注即可；<br>- 用 tempfile 等其他方式自建目录、留下目录、切换进去运行命令，或读写了其他工作目录之外的路径：按 SCOPE_VIOLATION 处理 |
| 执行器报告了 N 处合同矛盾 | 执行器按执行说明声明了合同矛盾，并写明暂时采用的做法 | 逐条裁定。采用的做法与裁定一致时可以 PASS；不一致时判 REVISE（PLAN_ERROR），在新版本合同中把两处写一致 |
| `main_repo_changes`（摘要“复审需要关注”） | 运行期间主工作区 HEAD 或规划路径之外的文件变化 | 先确认是否是规划器或用户自己的操作，例如在批次运行期间合并了其他候选；无法解释的变化按 SCOPE_VIOLATION 处理。规划路径（`planner_paths`）的变化只记为备注 |

## 环境问题

| 现象 | 处理 |
|---|---|
| doctor 报“pi --list-models 执行失败”或“pi 没有任何可用模型”，而平时正常 | 多半是在 Codex 等沙箱中运行，pi 读不到 `~/.pi/agent` 的配置或凭据。改在沙箱外运行 doctor 再判断；`executor_model_list` 中有退出码与脱敏后的 stderr |
| pi 长时间无输出 | 调度器已把 stdin 设为空设备（Pi 在 stdin 不是终端时会一直读到 EOF）。仍然挂起就查看 stderr.log 与网络 |
| Windows 上找不到 pi | npm 全局安装会生成 `pi.cmd`；调度器会自动改用 node 直接运行入口脚本。也可以用 `PI_DISPATCH_PI_CMD='["node","…/cli.js"]'` 指定 |
| `python3` 在 Windows 上打开应用商店 | 使用 `bash scripts/dispatch-pi.sh`（会跳过占位程序），或用 `python` / `py -3` |
| grep/find 工具首次使用很慢 | 本机缺少 rg/fd 时，Pi 会从 GitHub 下载；可以预先安装 ripgrep 与 fd |
| worktree 缺依赖 | worktree 不带 node_modules 或虚拟环境；在合同 setup 中显式安装 |
| 执行器看到奇怪的规则 | 查看 `preflight/context-files.json`：worktree 之外（例如用户主目录）的 AGENTS.md，以及 `~/.pi/agent` 下的 AGENTS.md、SYSTEM.md 也会被加载 |
| 费用突然升高 | 看 `auto_retries`、`compactions` 与 thinking 级别；按任务汇总成本（`bash scripts/dispatch-pi.sh metrics`） |
| 第二轮重复旧错误 | 新合同只写了“再试一次”；改为写明验收差异与失败输出 |
| 执行器打印中文时 `UnicodeEncodeError`（Windows） | 控制台是 cp1252 / gbk。在项目 AGENTS.md 写明临时运行 `python -c` 时先设 `PYTHONIOENCODING=utf-8`；调度器已为执行器与检查设置 `PYTHONDONTWRITEBYTECODE=1` |
| 流中断后自动重试（`auto_retries` 中有 `terminated`） | 通常是网络或服务端中断，Pi 会自动重试；一次重试成功不影响结果，频繁出现时检查网络与限流 |
| `TIMEOUT`，但候选看起来已经写完 | 执行器常在动手前长时间推理，写完代码后来不及自检和写报告。运行中 `status` 显示“长时间没有工具调用”时，多半就是这种情况。<br>先 `check --fresh` 验证候选，再复审补丁。超时的 attempt 不能 PASS（G1）：判 REVISE（`--class TIMEOUT`），用 `branch --rework` 取得返工提交，然后二选一：<br>- 还有剩余工作：出一个只收尾的 vN+1，写明剩余差异，并提示先动手再验证；<br>- 候选已经完整（fresh 检查全部通过，逐项复审没有遗留），缺的只是执行报告：由规划器的逐项复审代替报告（写进复审记录），直接集成返工提交，再 `mark … SUPERSEDED --ref … --reason …`，不必为一份报告再派一轮。<br>剩余预算不足、又有剩余工作时按 ESCALATE 处理 |

两个运行环境的规则互相冲突时，先弄清规则的适用角色与实际加载了哪些文件。不要在提示词末尾继续叠加互相否定的“最高优先级”。
