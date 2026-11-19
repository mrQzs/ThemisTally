# 复审记录：t059-desktop-web-logs-search-job attempt-001（七端信箱 hub）

- 合同：t059-desktop-web-logs-search-job.v1（base fcff2f84aa2439afe58289e20d7c652a91e521ad）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T175217484610Z-1c50），终审报告如下

## 终审报告

# T059-7-audit-post 终审报告（audit-sonnet）

## 结论

通过。候选 attempt-001（基线 fcff2f84 + 三份文件改动）逐行对照合同 v1，D01–D10 全部忠实；没有为过测试写的特判、没有空的异常处理、没有悄悄扩大的范围、没有弱化测试。执行报告的 DoD 自述与内核的检查记录对得上，JEV 的三条线索逐条查清后都不构成缺陷。战后门禁的 16 条变异全抓住、无等价变异，白盒文件只用于本次核验。以下是核对过程与 4 条不挡意见，无阻塞项。

## 一、材料与方法

读的东西：候选补丁（3 个文件）、工作树里改后的 common-readers.ts 与 live-readers.test.ts 全文、内核 checks.json 与七份检查日志、基线 G01 日志、战后门禁报告与白盒文件与变异记录、合同 v1（json 与 md）、JEV 报告、events-summary.json、仓库事实文件（live/mode.ts、live/transport.ts、ts/packages/ui/src/jobroutes.ts、ts/packages/ui/src/jobs.ts、api.ts、logs-SearchPanel.tsx）。

顺序：先读改后的源码，再看检查与门禁记录，最后对照合同与仓库事实定判定。本回合只有只读工具，没有跑任何命令；所有「跑过」的证据都取自内核独立跑的日志（候选树 e670f80f 的新工作树），不是执行端的自述。

## 二、候选源码逐条核对（合同 v1）

- **D01 建作业**：`common-readers.ts:117` 是 `client.postRaw<unknown>('/api/v1/jobs', jobBody(q, task, max), 15)`；`:63-68` 的 jobBody 返回扁平对象 `{ kind: 'search', pattern: q, max }`，`if (task !== null) body.task = task;`，max 是数字。与合同 D01 逐字一致。仓库事实复核：`ts/packages/ui/src/jobroutes.ts:74` 是 `search: { required: [pattern], optional: [task, max] }`，`:145-152` 多一个键回 400，`:164-165` max 必须是数字，`:186-189` 服务端把三者拼成 `logs search --json [--task=…] [--max=…] -- <pattern>`——键集与类型都对得上，不是客户端猜的形状。
- **D02 轮询**：`:88-108` 的 pollJob 用 setTimeout 链，`setTimeout(query, 1000)` 恰好两处（`:107` 首查、`:99` 续查），没有 setInterval；`:91` 是 `client.getRaw<unknown>(path, undefined, 15)`；路径在 `:119` 是 `'/api/v1/jobs/' + encodeURIComponent(String(id))`；非终态继续查、不设上限；终态在 `:102-104` resolve 后不再排计时器（终态后计时器数归零）；全程只有 postRaw/getRaw，没有 client.get、没有取消。
- **D03 终态**：`:96-98` 读的是作业对象的 `state`（不是 status），终态集合四个；`:102-104` 是 `resolve(isEnvelope(job.envelope) ? (job.envelope as Envelope<SearchData>) : failureEnvelope(command, [terminalMessage(state)]))`——合法信封同一引用原样交回（不拷贝、不改字段），为 null 或不合法走 `:79-85` 的四句固定文案（已取消 / 超时 / 失败 / 没有交回结果，逐字）；`:70-72` 的 failureEnvelope 形状是 ok:false、exit_code:null、data:null、output:[]、messages、command、elapsed_ms:0，command 是 `searchCommand(q, task, max)`（`:113`）。仓库事实复核：`jobs.ts:138-149` 的作业八键投影里字段名确为 `state`；`jobroutes.ts:233-246` 终态四态、cancelled 的 envelope 为 null、timed_out 的 envelope 是七字段的 timeoutEnvelope（能过 isEnvelope，于是原样交回）。
- **D04 非 2xx**：`:118` 建作业非 201 立刻交 failureEnvelope 并停（不发查询、不排计时器）；`:92-94` 查询非 200 同样立刻停（503、401 都在内）；`:74-76` 的 replyMessages 用 isEnvelope 判，正文是合法信封就取它的 messages，否则给 `ERROR: 服务返回 HTTP <状态码>`。传输层事实：postRaw/getRaw 对 401 先 reauth 再回 401（落到 D04），断线/超时 reject（落到 D05）。
- **D05 reject**：`:91-105` 用 `.then(onFulfilled, reject)` 把 getRaw 的 reject 直通外层 Promise；建作业那侧 `:117` 的 `.then` 没有第二个参数，postRaw 的 reject 直接冒泡。两条 reject 路径都不重试、不吞、不再排查询。
- **D06 夹具不变**：候选补丁的 diff 里，夹具分支、七个 helper、ERROR_MESSAGE、五个开关一行未动（补丁逐字可证）；模块仍是两条 export 语句、三个导出名；对 ../../api 仍只 `import type`；转出语句前一条语句以分号结尾；全文没有四个网络整词与禁词集合。
- **D07 包内测试**：真检索用例 12 条（合同写死的十条 + getRaw reject + postRaw reject），夹具那个 describe 在补丁里根本没有出现（说明字节未变）；记号 searchLogs、/api/v1/jobs、夹具里没有这份数据 都在；skip/only/todo/xit/xtest 精确 grep 零命中。
- **D08 t027 退役**：:111 记号换成三项新记号；S07 删掉那行 assert 并改 docstring；s33 整条退役；PROBE_UNWIRED 整份退役、PROBE_SPECS 去掉 unwired 键、PROBE_ORDER 去掉 unwired、p6 整条退役；「（站主 2026-11-19 为 T059 退役）」出现 3 处。改动只落在合同点名的那些位置（:111、S07、s33、docstring :48-49/:58/:60、PROBE_UNWIRED、:1206、:1209、:1475-1477），其余断言未动。
- **D09 范围**：内核 scope.json 是 A0 M3 D0 T0、violations 空、warnings 空；三份文件都在 allowed_modified_files 内；forbidden_paths 未碰。执行期间出现的 .pytest_cache/、dist/、node_modules/ 都是被忽略路径，不在候选里。
- **D10 全绿**：内核在候选树上独立跑 V01（15 passed）、V02（140 files / 1368 passed）、V03、V04（built in）、V05（69 passed）、G01（7 passed）、R01（1160 passed），全部 exit 0；基线 G01 是 6 failed 1 passed（红点落在断言上，不是空心基线）。

## 三、全绿不等于对：四项排查

1. **对测试输入硬编码**：实现里没有为过测试写的特判。四句固定文案、正文键集、1000/15/201/200 都来自合同与仓库事实；terminalMessage 的 default 分支是「没有交回结果」，不是给某条测试兜底；jobBody 与 searchCommand 的两个 task 口径按合同写成 `!== null` 与真值，没有互相迁就。
2. **空的异常处理**：实现里没有 try/catch，也没有空 catch。错误路径只有两条（reject 直通、非 2xx 的固定信封），都不是静默吞掉。
3. **悄悄扩大的范围**：scope.json 与 candidate.patch 一致（三份文件、无新增无删除）；执行报告自述的 git status 与内核 scope 一致。
4. **弱化测试**：JEV 在这条上给了 0.72。逐条查：被删掉的两个用例正是合同第 3 步命令整块替换掉的「检索尚未接通」describe（旧口径本片必然推翻）；夹具那个 describe 在候选补丁里没出现，字节未变；新文件 12 条用例多于合同要求的 10 条，且逐条对应 D01–D05。判定：没有弱化。

## 四、执行报告 DoD 自述与内核记录对账（JEV 三条线索）

- **临时路径与可疑命令**：events-summary.json 的 temp_path_uses、suspicious_commands、outside_worktree_paths、own_run_paths、temp_dirs_without_cleanup 全空，problems 空、ok 为真。执行报告里也没有任何写到工作树之外的写法，两边无冲突，没有需要指出的自述不实。
- **JEV「自行解读合同」0.94**：执行端列了 3 条 interpretations，逐条看都不违反合同：①正文键按 `task !== null`（空串也加 task 键），而 searchCommand 仍按真值判——这正是合同「不因正文的 null 判断而改」写明的两个口径；②合同写的是「至少覆盖这十条」，补一条 postRaw reject 是加强；③合同没钉 helper 排版。三条都在报告里如实披露，合同矛盾一栏为空是恰当的。
- **JEV「自述完成而无证据」0.82**：唯一没写测试编号的是 D04 的备注。实际证据在：内核 V01.log（15 passed，含建作业 400/503/500 与查询 404 四条用例）与 G01.log（7 passed，探针 12 条 it 含同款场景）。这是执行报告 DoD 备注格式不齐，不是候选缺证据。
- **JEV「误导程度」1.62/3**：执行报告里的数字与内核日志逐项对得上（15/15、1368、69、7、1160；耗时 123.67s 与 1160.45s 和执行端自述同量级）；内核 checks.json 里每条检查的 candidate_files_modified 与 unexpected_files_by_checks 都为空。未见虚报。

## 五、战后门禁的声明逐条裁定

- 本回合输入没有「门禁端举证的候选缺陷」一节，战后门禁报告也写明 candidate_defects 为空，无可裁定的候选缺陷条目。
- 白盒 5 条是静态断言（把源码关键语句逐字钉住），门禁端自己写明了这一点，没有拿静态断言冒充行为证据；行为证据在 G01 的流水线探针（12 条 it，真跑 Vitest）与执行端包内测试。这与一审时的判断一致，不重开。
- 抽查 M13（终态信封改成深拷贝）与 M15（reject 不再外抛）的日志：都是白盒断言失败（1 failed, 4 passed），不是收集错误。
- 等价性逐条裁定：16 条变异改的都是合同写死的字面（时限 15 改 10/5、201 改 200、非 200 判定收窄、state 改 status、终态集合去掉 timed_out、1000 改 500/1500、id 不编码、信封深拷贝、文案改字、task 真值判断、正文多一个键、去掉 isEnvelope 引入、reject 不直通、非 2xx 文案丢前缀），没有一条是「改了但行为不变」的等价变异，所以「0 漏、0 等价」的结论成立。
- 白盒文件与 mutation-spec 只用于本次核验、不进仓库：核验过该约定成立，但工作树里确实留着未跟踪的 tests/test_gate_t059_whitebox.py，集成时按补丁取文件即可（见下游须知）。

## 六、不挡意见（不退回，写给站主与下一片）

1. **轮询正文为 null 时 Promise 会悬挂**（common-readers.ts:91-98）：GET /api/v1/jobs/<id> 回 200 但正文是 null 时，`job.state` 抛 TypeError；这个抛出发生在 getRaw().then 的 onFulfilled 里，外层 Promise 既不 resolve 也不 reject，界面会一直停在「正在检索…」，同时多一个未处理的 rejection。触发路径具体，但概率很低（服务端这条路由始终回八键作业对象，传输层在 JSON 解析失败时才会给 null 以外的合成信封）。要修大约 3 行（先判正文是不是对象，不是就当终态失败交固定信封）。合同第 ⑦ 条本来就把「回应不是作业」交给服务端的 404 处理，所以不改也说得过去。
2. **200 但正文不是作业对象时会一直查下去**（`:96-99`）：传输层在正文不是合法 JSON 时会合成一个失败信封当 body 返回，那里面没有 state 字段，String(undefined) 不在终态集合里，于是每秒继续查、不设上限（服务端 search 作业 180 秒上限管不到这种「根本没有作业」的情况）。同样只在正文非 JSON 时出现，概率很低，与第 1 条同一处可一并修。
3. **t027 模块 docstring :48-49 那条被重写成一行**，T037 那半句的「、不发读请求」与「（D09、D10）」没有保留（语义不变、断言未动、门禁也不逐字钉这两行）；:60 那条把原本已过时的 p3/p4 改成了真实存在的 p6/p7。属于「合同点名的那个地方里多改了几个字」，若站主要求历史描述逐字保留，可改成追加式写法。
4. **界面上没有作业进度**：queued/running 期间不显示状态，离开页面再回来也不接着看同一个作业——合同 Non-goals 明确不做，本片不算缺陷。

## 七、集成提醒

- 集成只取 candidate.patch 的三份文件：common-readers.ts、live-readers.test.ts、test_gate_t027_baseline.py。
- 工作树里多出的未跟踪文件 tests/test_gate_t059_whitebox.py 命中 forbidden_paths 里的 tests/test_gate_t059_*.py，不能进仓库；不要按工作树整棵提交。
- 门禁基准 tests/test_gate_t059_baseline.py 是基线提交里已有的，不属本片候选。

Verdict: PASS
