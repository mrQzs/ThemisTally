# Codex 审查报告（原文）

> 审查工具：OpenAI Codex CLI 0.156.0（模型 gpt-6-astra，reasoning effort high，只读沙箱），2026-09-22。
> 以下为原文，行号对应修复前的版本；逐条处理结果见《审阅意见.md》第八节。
> 收入 PI-Kit 仓库时，原文中指向审查时本机文件的链接改成了纯文本路径（文字与行号未改，行号仍对应 1.0.0 修复前的版本）。

审查结论：套件比原方案的附录脚本完善，但仍有会导致错误验收、预算失效和数据丢失的问题，不能将“58 项断言通过”视为这些保证已经成立。

本次没有修改、创建或删除文件，没有安装软件，也没有运行自测或调用模型。除阅读源码、文档外，仅做了不写文件的语法解析和内存中的函数核对。下文套件路径均相对于 `claude-pi-kit/`。

**1. 发现列表**

1. **高｜新增文件不算候选漂移，可能验收通过一个无法独立工作的候选。把握：确定。**

   位置：`scripts/pi_dispatch.py:2190`、`:2217`、`:2301`。

   证据：检查前后仅对 `drift["modified"]` 阻断，任意新增文件都只提示。假设候选引用了遗漏的模块，复审者补上该模块后运行检查，检查可以通过；新模块却不属于候选树，`branch` 不会包含它。新增测试配置也可能改变测试行为。《审阅意见.md》M8 和 README 第 162 行把这种放宽当成了修复。

   修正：在干净的候选副本上验收；默认拒绝检查前新增的未跟踪文件。检查产物应有明确、有限的允许范围，不能把所有新增文件都视为缓存。

2. **高｜Windows 子进程在加入 Job Object 前已经运行，存在监督空窗。把握：确定。**

   位置：`scripts/pi_dispatch.py:482`，相关 `:489–501`、`:2056`。

   证据：顺序是 `Popen` → 写 PID 回调 → `job.assign` → 安装中断处理。此期间程序可以创建子进程；PID 文件写入失败还会直接跳过 Job 分配和清理。Windows 的自动 Job 继承适用于父进程**加入 Job 后创建**的子进程，不追溯此前的子进程。分配失败后继续降级，正常退出路径又不清理无 Job 的残留进程。[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

   修正：以挂起方式创建进程，成功加入 Job 后恢复执行；将创建、回调、等待和清理全部纳入外层 `try/finally`。要求可靠监督时，Job 分配失败应停止执行。

3. **高｜普通 cleanup 会强制删除未保存的新工作。把握：确定。**

   位置：`scripts/pi_dispatch.py:2433`，尤其 `:2450–2452`。

   证据：只要 `candidate.json` 存在，就直接执行 `git worktree remove --force`，没有比较当前内容与候选，也没有检查补丁是否仍存在、有效。候选收集后的人工修改、新增文件或检查产物会被删除，即使调用者没有传 `--force`。这不满足原方案第 900 行“清理前确认新增文件和最终候选已保存”。

   修正：清理前核验候选和补丁，并检查当前全部差异；有未留存内容时拒绝普通 cleanup，明确列出将丢弃的内容后才允许强制清理。

4. **高｜task-id 的预算检查与领取不是原子操作。把握：确定。**

   位置：`scripts/pi_dispatch.py:2013`、`:2024`、`:2035`。

   证据：预算先计算，随后进行较长的预检，最后只创建**当前 attempt** 的 `claim/`。两个同 task-id 的 PREPARED attempt 可以同时读到相同剩余预算，随后各自成功领取，突破次数和累计时限。已有 `claim` 只能阻止同一 attempt 重复运行。

   修正：使用 task-id 级锁，把预算重读、额度预留与领取放入同一个临界区；预检结束后重新核验。增加不同 attempt 并发争用最后一次额度的覆盖。

5. **高｜Markdown 与 JSON 的“一致性校验”没有校验实际执行内容。把握：确定。**

   位置：`scripts/pi_dispatch.py:991`，相关 `:1857`、`:2047`。

   证据：只比较三个 Identity 字段，并检查路径、编号是否在 Markdown 中出现；不比较检查命令、setup、预算、授权、禁止路径等。内存核对中，保持示例 Markdown 不变，将 JSON 的 V01 改为 `python -c pass`、次数改为 20、集成授权改为 `deploy`，校验仍无错误。Pi 读取 Markdown，调度器执行 JSON，两端可能遵循不同合同。

   修正：确定一个结构化事实来源，自动生成 Markdown 的机器字段；或者严格解析并比较两份合同。同步收窄 README 第 118 行“必须一致”的保证。

6. **高｜“只读子命令”的预授权包含任意文件覆盖能力。把握：确定。**

   位置：`.claude/settings.example.json:6`、`scripts/pi_dispatch.py:2543`、`:2626`。

   证据：`doctor *`、`metrics *` 被预授权，但二者支持任意 `--out`，直接调用 `Path(...).write_text()` 覆盖文件。例如 `metrics --out README.md` 属于该允许规则。`Edit(/.agent/runs/**)` 也不能阻止 Python 内部直接打开证据文件。[Claude Code 权限规则](https://code.claude.com/docs/en/permissions)

   修正：拆分纯读取和导出命令；导出限定目录、拒绝覆盖。权限示例只预授权真正没有写入能力的入口，并修正文档中的“只读”描述。

7. **中｜异常路径会留下现有命令无法恢复的状态。把握：确定。**

   位置：`scripts/pi_dispatch.py:1961`、`:2035`、`:2127`。

   证据：prepare 异常退出可以永久停在 `PREPARING`，而 collect、mark ABANDONED、cleanup 都不接受该状态。run 创建 `claim/` 后，仍可能在说明写入、文件盘点或批处理参数校验阶段失败，此时状态仍是 `PREPARED`，重跑却因 claim 存在被拒绝，也不能 collect。

   修正：增加领取中、准备中异常的恢复流程；保存监督者身份，确认相关进程终止后才能恢复或放弃。可提前完成的参数校验应放在领取前。

8. **中｜关于本机 Step 的 high 和 `providerThinkingLevel`，文档与真实 Pi 路径不符。把握：确定。**

   位置：`README.md:86`、`scripts/pi_dispatch.py:1369`、`tests/stub_pi.py:87`。

   证据：本机配置使用 `anthropic-messages`，没有 `forceAdaptiveThinking` 或 `supportsMidConvoEffort`。本机 Pi 的 `@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/anthropic-messages.js:676` 会走预算式 thinking；默认 high 对应 16384 token，而不是原样发送字符串 high。该实现仅在特定 compat 条件下写 `providerThinkingLevel`。桩程序却总是填入该字段。

   此外，调度器只收集这个字段，没有检查其是否匹配；内存输入实际级别 `low`，摘要仍可 `ok=true`。

   修正：区分请求的 Pi 级别、协议映射和服务端实际行为。按当前协议记录可获得的证据，不要求不存在的响应字段，也不要宣称已证明服务端实际使用 high。

9. **中｜缺少 `agent_settled` 时，不论 Pi 版本都会降级判定完成。把握：确定。**

   位置：`scripts/pi_dispatch.py:1341`、`:1358`。

   证据：只要存在 `agent_end` 且 `willRetry=false`，没有 settled 也能完成；解析器没有接收预检版本。内存核对确认，这种事件流会得到 `complete=true`。因此 0.87 的日志即使恰好在一个完整的 `agent_end` 行后丢失尾部，也不会被判为缺少最终事件。

   修正：将预检版本或协议能力传给解析器。支持 settled 的版本必须出现相应结束事件；仅对明确不支持的旧版本启用降级。

10. **中｜实际变更路径没有执行严格校验，非法编码和控制字符可能被放行。把握：确定。**

    位置：`scripts/pi_dispatch.py:623`、`:725`、`:1467`。

    证据：非 UTF-8 路径被替换解码并标记 `path_decode_error`，但范围检查忽略该标记。正则以 `$` 结尾，Python 允许它匹配末尾换行之前的位置。内存核对中，实际路径 `src/search/normalize.test.ts\n` 匹配了无换行的确切允许路径；带解码错误标记的路径也被判为 in_scope。

    修正：对实际路径拒绝控制字符及解码错误；采用 `fullmatch()`。如果需要支持非 UTF-8 文件名，应保留原始字节身份，不能用替换后的名称作授权判断。

11. **中｜部分错误合同会触发未捕获异常，而不是返回合同错误。把握：确定。**

    位置：`scripts/pi_dispatch.py:874`，另见 `:879`、`:890`、`:935`、`:949`。

    证据：尚未确认数组元素类型便使用 `set()` 或集合成员操作。`authorization.executor=[{}]` 在内存核对中直接抛出 `TypeError: unhashable type: 'dict'`。顶层 main 只捕获 `DispatchError` 和 `KeyboardInterrupt`。当前测试仅检查了 executor 顶层类型错误。

    修正：先验证各元素是合法字符串，再建立集合；同样处理检查 ID、DoD ID 和 evidence。错误应统一返回退出码 2。

12. **中｜主工作区指纹无法发现对已有脏文件的继续修改。把握：确定。**

    位置：`scripts/pi_dispatch.py:651`。

    证据：指纹只有 HEAD 和 porcelain 状态字节。一个运行前已经显示 ` M file` 的文件，在运行期间被再次改写，状态字节可以完全不变；已有未跟踪文件内容被覆盖也一样。因此 `main_repo_changed=false` 不代表用户工作未被改动。当前 outside 场景只测试新增路径。

    修正：至少记录已有脏文件和未跟踪文件的内容摘要，或建立合适的内容快照；明确报告检测覆盖范围。

13. **中｜允许纯人工复审的合同，却没有使其正常 PASS 的路径。把握：确定。**

    位置：`scripts/pi_dispatch.py:933`、`:2183`、`:2269`。

    证据：`checks=[]`、DoD 仅引用 `review` 的合同可以通过校验，只产生建议警告；check 随后拒绝运行，verdict 又因没有独立检查记录固定失败 G3/G4。这与委派清单允许“人工复审点”的描述冲突。

    修正：明确选择：校验阶段要求至少一个检查；或者支持纯人工验收，通过结构化复审证据完成相应门禁。

14. **中｜指标将豁免接受计为普通通过。把握：确定。**

    位置：`scripts/pi_dispatch.py:2511`。

    证据：首次及最终通过率都使用 `PASSING_VERDICTS`，包含 `ACCEPTED_WITH_EXCEPTION`。但原方案第 625 行和 gates.md 第 37 行明确要求与 PASS 分开统计。全部依赖豁免接受的任务也能显示首次通过率 100%。

    修正：分别统计严格 PASS、豁免接受和未通过；指标名称与分母保持明确。

15. **中｜费用未知仍被写成数值 0，并进入费用合计。把握：确定。**

    位置：`scripts/pi_dispatch.py:1420`、`:2518`、`:2531`。

    证据：未获得价格时生成 `{"total":0.0,"status":"unknown"}`，metrics 又将缺失费用按 0 求和。虽然另有完整性提示，仍违反 README 第 133 行和原方案第 944 行“未知不填 0”的要求。

    修正：未知金额使用 `null`；将已知费用合计标为部分金额或下界，并列出未知轮次数。

16. **中｜自测每次启动都会删除上次 `--keep` 保留的现场，并且不能安全并行。把握：确定。**

    位置：`tests/test_dispatch.py:23`、`:469`。

    证据：所有运行共用固定的 `%TEMP%/pi-dispatch-e2e`，入口无条件 `remove_tree(WORK)`。上次保留的调试现场在下次启动时被删除；两个测试进程会互删仓库和 worktree。

    修正：每次运行用唯一临时根目录，只清理本次创建的目录。保留现场的清理由单独、明确的操作处理。

17. **中｜401 示例仍缺少跨会话的失败与迟到响应语义，原审阅没有指出。把握：很可能。**

    位置：`examples/auth-refresh-401.v1.md:48`、`:52`、`:68`；原方案第 823、827、844 行。

    证据：示例明确保护刷新成功时的 token 写回，但 refresh 401 时无条件要求 `markSessionExpired()`；迟到 401 的重放判断只写 tokenVersion。没有明确处理“账户切换后旧刷新失败”和“账户切换后旧普通请求才收到 401”。按字面实施，可能使新会话失效或使用新账户凭据重放旧请求。这是合同缺口，尚不能断言真实实现存在漏洞。

    修正：每个原请求记录 sessionGeneration，在刷新、会话失效和重放前统一核验；补充旧会话迟到失败、新会话并发刷新等验收场景。

18. **低｜允许本地提交的配置与执行器规则冲突。把握：确定。**

    位置：`AGENTS.md:29`、`scripts/pi_dispatch.py:1730`。

    证据：校验器支持 `local_commit`，生成说明也明确允许本地提交；AGENTS.md 却无条件写“不提交、推送、合并或部署”，合同模板 Forbidden 同样禁止提交。默认 project 上下文会同时提供这些要求。

    修正：将禁止提交写成“未获合同授权时不得提交”，并让模板随授权生成相应规则；或者删除不打算支持的 `local_commit`。

**2. 确认正确的要点**

- 临时索引快照、禁用重命名检测、NUL 分隔 raw diff、二进制补丁往返校验，整体设计正确；没有发现常规 raw diff 字段拆分错误。
- Windows Job 的指针类型、主要结构字段和 `KILL_ON_JOB_CLOSE` 常量与官方定义相符；问题主要在生命周期管理。[结构定义](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
- stdin 使用 DEVNULL、stdout/stderr 分开，以及优先绕过 npm `.cmd` 包装，方向正确。
- 本机 Pi 源码支持原审阅关于 JSON 模式不能只看退出码、上下文文件优先级、worktree 不是沙箱等主要判断。
- 四个 Skill、代理和规则文件的 frontmatter 均通过 YAML 解析；所有 JSON 可解析；两个示例通过内存中的合同校验。Skill 的 description 基本清楚，职责划分合理。
- `@AGENTS.md` 导入方式正确；原审阅对 `allowed-tools` 属于预授权、Fable 别名需要核对实际模型的判断有官方依据。[Memory](https://code.claude.com/docs/en/memory)、[Skills](https://code.claude.com/docs/en/skills)、[模型配置](https://code.claude.com/docs/en/model-config)

《审阅意见.md》的主要问题定位总体成立，但“这些问题都已处理”的总结过强；其中候选漂移的修正引入了第 1 项问题，Step 思考级别和统计保证也需要修订。

**3. 无法验证的内容**

- **58 项实际通过记录**：未运行测试，交付目录也没有可独立核验的完整测试结果。
- **真实 Step 执行**：未调用模型，不能确认服务端接受、执行了哪些 thinking 参数，也不能确认真实费用和工具调用表现。
- **进程回收的动态效果**：未创建或终止测试进程；Windows 极端时序、Job 降级、连续中断，以及 Linux/macOS 分支均未实测。
- **Python 3.8 完整兼容性**：通过了 3.8 语法解析，但本机运行时是 3.12，不能替代 3.8 实际验证。
- **完整编码与路径矩阵**：未创建中文、特殊字符、非 UTF-8 文件名或不同 CRLF/Git 配置的测试仓库；`.cmd` 参数转义也未动态验证。
- **Claude Code 实际加载与权限匹配**：核对了格式和官方语义，未在真实会话中调用这些 Skill、子代理或权限示例。
- **Pi 0.87.1 发布及历史外部核验声明**：本次 Pi 行为以本机 0.87.0 文件为依据，没有复核另一位审查者的历史网络核验记录。