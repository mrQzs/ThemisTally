# 复审记录：t017-desktop-ui-live attempt-003（七端信箱 hub）

- 合同：t017-desktop-ui-live.v4（base 88d95e56417d6e77aa80a412f7d90977766fb876）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261025T123055958242Z-c7c4），终审报告如下

## 终审报告

# T017 终审报告（-7-audit-post，attempt-003）

## 结论

**通过**。候选（tree 412de16，base 88d95e5）忠实于合同 v4：两条执行端自行解读逐行核实无行为偏差；内核独立复跑 G01/R01/V01–V10 全绿且未改动候选；白盒 32 条全绿、变异 38 条锚点全中、36 CAUGHT、M20/M21 的 equivalent 判定经逐条复核成立（且两条 DoD 在锁定基线 G01 里另有真钉子）；范围干净、无越界、无测试弱化。JEV 两处关注均被证据驳回。无阻塞项，4 条不阻塞观察见第六节。

## 一、重点裁定事项 1：执行端两条自行解读

### 1a. 脱敏从 completedEnvelope 移到 jobroutes.ts 内联 —— 忠实，产物逐字节一致

逐行比对候选 `jobroutes.ts` 的 runJob completed 分支与 `kernelenvelope.ts` 的 completedEnvelope：

| 环节 | completedEnvelope（原路径） | jobroutes 内联（新路径） | 一致 |
|---|---|---|---|
| stdout 解析 | `parseJsonData(outcome.stdout)` | 同一函数同一输入 | ✓ |
| invalid-json 判据 | `parsed === undefined && exit_code === 0` | 完全相同的表达式，settle 参数（failed/invalid-json/serviceErrorEnvelope 同文案）不变 | ✓ |
| data | `parsed === undefined ? null : redactJson(parsed, allow)` | 相同表达式，allow 仍来自 `JOB_ALLOW[kind]` | ✓ |
| messages | `messagesOf(stderr)`：split(/\r?\n/)、跳过空行、留 ERROR/WARN 前缀行、逐行 redactSecrets | `jobMessages(stderr)`：逐 token 相同的逻辑（`!startsWith("ERROR") && !startsWith("WARN")` ≡ `MESSAGE_PREFIXES.some(...)` 的否定） | ✓ |
| command | `displayArgv(argv)`（--cursor=/--transcript= 占位 + 逐项 redactSecrets，search 的 pattern 在内） | 同一函数 | ✓ |
| elapsed_ms | `elapsedMsOf(result.wall_seconds)` | 同一函数 | ✓ |
| 序列化 | `JSON.parse(envelopeBody(envelope))`，envelopeBody 手工按 ok/exit_code/data/output/messages/command/elapsed_ms 固定次序拼、data 走 pyjson dumps | 同一函数、同一固定次序（对象字面量键序无关，envelopeBody 决定字节） | ✓ |

- **六个 kind 都走得到**：validateJob 只放行六 kind；每 kind 经 buildArgv→table.create→`runJob(runner, record, argv, JOB_ALLOW[kind])`，completed 分支是唯一落信封路径；`JOB_ALLOW` 恰好六项、全 undefined（源码核实，站主拍板的「一律遮」不变）。
- **无字段/顺序/计时字段丢失**：信封七字段由 envelopeBody 统一拼装（未改动），elapsedMs 来源同一 wall_seconds。
- **动机正当**：锁定基线 `test_static_job_redaction`（tests/test_gate_t017_baseline.py:719-740）要求去注释后的 jobroutes.ts 或 jobs.ts 里出现 `redactJson`/`redactSecrets` 字面；attempt-002 委托 kernelenvelope.ts 的写法过不了该静态断言。内联是同时满足静态口径与 D19 行为契约（「与读路由同一套二道脱敏」）的最小改法，规则本身一字未变。
- **守护**：白盒 `test_jobs_redaction` + 变异 M37（data 不过 redactJson）/M38（messages 不过滤）均 CAUGHT——内联路径被钉住，不是为过静态检查而空转。

### 1b. 路由路径抽成 EVENTS_PATH / JOBS_PATH 再拼正则 —— 忠实，匹配语义零变化

- `EVENTS_PATH = "/api/v1/events"`、`JOBS_PATH = "/api/v1/jobs"`：路径字面量不含任何正则元字符，`new RegExp("^" + path + "$", "u")` 与 `/^\/api\/v1\/events$/u` 编译结果等价（`\/` 与 `/` 在 RegExp 中同义；u 标志保留；无 i 标志，大小写敏感不变；^…$ 锚点不变）。
- 边界逐一推演：`/api/v1/events/extra`（$ 锚点拒）、`/api/v1/jobs/`（`([^/]+)` 至少一字符，拒）、`/api/v1/jobsX`（创建路由 $ 锚点拒；查询路由 `([^/]+)$` 要求斜杠，拒）、`/api/v1/jobs/<id>/cancel` 与 `/api/v1/jobs/<id>` 互不串（cancel 后缀锚定）。
- 三条作业路由与 SSE 路由的构造都在 jobRoutes()/eventRoutes() 内一次性完成，非每请求编译，无性能回退。
- **动机正当**：锁定基线 `test_static_route_batches`（:377-406）要求去注释源码里出现 `/api/v1/events`、`/api/v1/jobs` 字面量；转义写法让字面量消失。常量化是满足静态口径且不动语义的唯一类做法。
- **守护**：白盒 `test_jobs_routing_edges`、G01 流水线路由检查（tests/test_gate_t017_baseline.py:1447-1450 四条命中 + 未命中 /api/ 路径 401/404 语义）在内核复跑中全绿。
- **没有为过静态检查偷改匹配语义**：结论成立。

## 二、重点裁定事项 2：JEV 两处关注

**(a) 「执行端选了一种读法却没当成冲突/提问」（p=0.65，置信 0.30）—— 不成立。**
执行报告把两条读法都写进了 `interpretations` 字段（带合同引文、adopted、reason），`contract_conflicts: []`。这不是隐瞒：合同的两组要求（静态字面量口径 + D19/D01 行为口径）本就同时可满足，不存在真冲突，走 interpretations 通道如实披露正是执行说明规定的做法。终审逐行核实两条解读均未改变行为（见第一节）。

**(b) 「DoD 自述完成而无证据」（p=0.92，置信 0.84；误导程度 2.13/3）—— 不成立。**
执行报告的 D01–D31 表每条都注明命名用例与检查号；合同 DoD 原文本身逐条规定「用例 + 证据」；内核在独立 verify 工作区（ThemisTally-t017-desktop-ui-live-a003-verify-znnld2zk，candidate_tree 与 candidate.json 一致）复跑全部检查：G01 exit 0、R01 597 passed、V01–V10 全 exit 0（V02=223 ui 用例、V04=625 passed/55 files、V05 tsc 干净、V07 范围断言、V09 STABLE20、V10 STABLE3），`covers_all_required=true`、`modified_by_checks=false`、`candidate_files_modified=[]`。我另抽查了被引用的用例真实在位（events-service.test.ts 的 U17/U18/U19+U20/U21/D10 各 describe、锁定哨兵 test_static_locked_test_files 强制要点齐备）。白盒 32 条与变异 38 条记录再补一层。没有任何一条 DoD 是「只有自述」；误导程度评分不被支持。

## 三、重点裁定事项 3：门禁结论可信度（M20/M21 逐条）

前提核实：mutations.json 记录 38 条锚点全 `count_found=1`（零 MISMATCH，CRLF 根因修复后）、baseline 32 passed、`files_left_modified: []`、36 CAUGHT、2 预期漏（unexpected_missed=[]）。一审第六节点名的 4 条必含变异全在清单且全 CAUGHT：D11→M35（test_live_d11_d12）、D21→M36（test_d21_service_side）、M24 窄化→M32（test_sse_write_failure_cleanup）、M25 空闲分支→M34（test_live_idle）。两条 WARN（M10/M16 插入式变异）均 CAUGHT，警告失效条件（无害插入）不存在。

**M20（空闲判定去掉 hub.subscribers）—— equivalent 判定成立。**
- 实验证据是决定性的：变异体上 `idle-open` 全绿——该检查在 idle_timeout=3 秒下开着订阅观察 6.5 秒，循环内每轮断言 `svc3.child.exitCode === null`（进程级断言，与流缓冲无关；harness 的 waitFor 语义我已核对，即便流断开也掩盖不了 exitCode 断言）。变异体既不提前退出（idle-open 绿）、又在断开后 15 秒内退出（idle-exit 绿），唯一自洽的解释是：SSE 流开着期间另有活动信号（inflight 计数，app.ts:94/148）在每次定时器到期时使条件为真——即 hub.subscribers 与 inflight 两条机制在「订阅开着」这一状态上完全重叠，去掉其一不可观察。这正是等价变异的定义。
- 我对 app.ts 的静态读码（async 函数返回流式 Response 时 finally 应先递减）与上述实验结论存在张力，但实验是真实进程行为的直接记录，且 36 条 CAUGHT 证明变异机制本身工作正常；张力只能出在 Bun 运行时的请求生命周期细节上，不影响等价结论（详见第六节观察 1）。
- **D30 并未因此失去守护**：锁定基线 G01 的 `test_static_idle_counts_subscription`（:570-585）静态要求 IdleTimer→createApp 判定窗口内含 hub 与 job（文本上删掉 hub.subscribers 即红），流水线 idle 检查（3 秒空闲下订阅开着 6.5 秒心跳不断且进程不退、断开后自退）黑盒钉住行为；U21 与白盒 test_live_idle 在干净候选上全绿（内核复跑 G01 exit 0、V02 exit 0）。要破坏 D30 行为需同时拆掉两条重叠机制，任何单点删除都会被现有钉子抓住或本就不可观察。

**M21（不调 server.timeout(req, 0)）—— equivalent 判定在套件范围内成立，D10 的真钉子在锁定基线里，成立。**
- 白盒 m21-sse 的配置（全局 idleTimeout=2 秒、心跳 500 毫秒）下，心跳写本身足以让连接不空闲，timeout(req,0) 行为冗余——变异体上 SSE 活过 6.5 秒、心跳 ≥6 次，实验直接证明套件测不出差异。m21-keepalive 在变异体上仍绿，证明全局 idleTimeout 没被放宽的另一面有守护。
- 但等价是有配置边界的：生产缺省下心跳 15 秒 > Bun 缺省空闲超时（约 10 秒，站主实测记录），此时 timeout(req,0) 是承重的。锁定基线对此有两颗真钉子：`test_static_bun_idle_timeout`（:553-567）静态要求 server.ts 里 `.timeout(<req>, 0)` 调用在位、生产路径禁 idleTimeout 数字字面量；G01 流水线 sse 检查断言连接活过 12 秒（大于缺省 10 秒）。候选上内核复跑 G01 exit 0；源码核实调用在位（server.ts:98 `if (isEventsRequest(request)) bunServer.timeout(request, 0);`），isEventsRequest 精确匹配 GET /api/v1/events。一审报告观察 1 早已言明「M21 的真正钉子仍是流水线的 12 秒存活加 timeout 传 0 的静态断言」。
- 门禁端把 equivalent 判定「留给终审复核」并附完整实验证据，处理得当；判定成立。

**白盒 32 条支撑「零候选缺陷」的可信度**：32 条覆盖五个探针（指纹/中枢/作业/内核 H1H3/活服务 D11+D10+D30），与 DoD 的行为面对应（见第四节表）；叠加锁定 G01 的 24 静态 + 8 流水线（内核独立复跑绿）与 625 条 vitest（V04 绿、V10 三遍稳定），三层证据一致。我在候选源码里未发现对测试输入硬编码、空异常吞噬、为过测试的特判或悄悄扩大的范围（jobMessages 的 try/catch 面、write() 的 catch 返回 false 都有明确语义与对应钉子 M24/M32）。

## 四、D01–D31 证据核对表

强度：G01=锁定基线（内核复跑 exit 0）；V02/V09/V10=vitest（内核复跑 exit 0）；WB=白盒 32 条（干净候选全绿）；M#=变异条目（C=CAUGHT）。

| DoD | 命名用例 | 机械证据 | 变异钉子 |
|---|---|---|---|
| D01 SSE 路由与鉴权 | routes-auth 新表、events-service | G01 静态 route_batches/routes_auth_19_intact + 流水线 auth（无 cookie 401）+ sse 响应头 | M10(C) |
| D02 快照与序号 | events-service U17（snapshot/reconnect/Last-Event-ID） | G01 流水线 sse（首块 retry 3000、首条 snapshot id=1）+ 锁定要点（reconnect/update token、序号递增正则） | M1/M2(C) |
| D03 与 status 逐字节一致 | events-service（逐字节 token） | G01 流水线 sse data 七字段；WB test_sse_shared_status/test_sse_redaction | M11(C) |
| D04 心跳与 retry 四常量 | events.test.ts | G01 静态 event_stream_shape + 流水线 sse | M8/M9(C) |
| D05 只 stat 名单 | events.test.ts、events-service | G01 静态 roster_source/watch_details；WB test_watch_fingerprint | M3(C) |
| D06 junction/重解析点 | events-service | WB test_watch_fingerprint；G01 静态 watch_details | M4(C) |
| D07 去抖与共享 | events-service（20 写 ≤2 次、3 订阅 1 次） | WB test_sse_debounce/test_sse_shared_status | M5/M7(C) |
| D08 起与停 | events-service | WB test_sse_stop_when_empty/test_sse_close | M6/M25(C) |
| D09 会话失效断流 | events-service revokeAll | G01 流水线 disconnect；WB test_sse_revoke | M23(C) |
| D10 timeout(req,0)+全局不改 | events-service D10 两条 | **G01 静态 bun_idle_timeout（.timeout(req,0) 字面 + 禁数字字面量）+ 流水线 sse 12 秒存活**；WB test_live_bun_idle | M21 等价（套件内），真钉子=G01 静态+流水线（候选上绿） |
| D11 file 超时不拖慢 | events-service | WB test_live_d11_d12（d11-not-slow：心跳/update/control 200）；V09 STABLE20 | M35(C，一审点名项 1) |
| D12 作业路由鉴权 | routes-auth 新表、jobs-service | G01 流水线 auth（401/403/415/400） | — |
| D13 严格校验九类 | jobs.test.ts 每类一条 | G01 静态 job_validation + 流水线 jobs 11 类 400；WB test_jobs_validation | M12a–i 九条全(C) |
| D14 argv 与时限 | jobs.test.ts + argv-templates | G01 静态 job_argv；WB test_jobs_argv | M13(C) |
| D15 pattern 用 -- 传 | argv-templates 四 pattern 过真内核 | V02；G01 静态 token | M13(C) |
| D16 作业表 43 位/100/503 | jobs.test.ts + jobs-service | G01 静态 job_table + 流水线 404 同文；WB test_jobs_table/ids/saturation | M16/M17(C) |
| D17 四终态/search 超时 | jobs-service + kernel-real | G01 静态 job_states + 流水线终态八键；WB test_jobs_timeout | M14(C) |
| D18 取消三种 | jobs-service + kernel-real（进程树） | G01 流水线 cancel 409；WB test_jobs_cancel/cancel_queued | M15(C) |
| D19 脱敏与白名单 | jobs.test.ts | G01 静态 job_redaction；WB test_jobs_redaction；内联产物与 completedEnvelope 逐字节一致（本报告 §1a） | M37/M38(C) |
| D20 H1 边写边看 | kernel-runner | G01 静态 h1_output_polling；WB test_kernel_h1 | M18(C) |
| D21 H2 越界路径 | kernel-real + 服务 400 | WB test_d21_service_side | M36(C，一审点名项 2) |
| D22 H3 摘监听 | kernel-runner | G01 静态 h3_release_on_entry；WB test_kernel_h3 | M19(C) |
| D23 抖动稳定化 | service.test.ts D11/D12（heldBack） | G01 静态 jitter_harness（断言只加强未放宽）；V02+V09 | — |
| D24 稳定性验收 | — | V09 STABLE20 + V10 STABLE3（内核复跑） | — |
| D25 README 与门禁 | — | V08 README ok；G01/R01/V01–V10 全绿（内核复跑）；import_graph 可达 | 36C+2 等价（§3） |
| D26 范围与依赖 | — | V01 frozen-lockfile、V07 范围断言、G01 静态 localhttp_and_deps（地基原样）；scope.json violations=[] | — |
| D27 订阅上限 16/4 | events-service U18 | G01 静态 subscription_limits + 流水线 limits/session-limit；WB test_sse_limits | M22(C) |
| D28 主动断开 | events-service U19+关停 | G01 静态 disconnect_and_close + 流水线；WB test_sse_revoke/close | M23/M25(C) |
| D29 心跳写失败清理 | events-service U20 | G01 流水线 disconnect 名额归还；WB test_sse_write_failure_cleanup | M24 窄化(C，一审点名项 3) |
| D30 订阅算活动 | events-service U21 | **G01 静态 idle_counts_subscription + 流水线 idle（3 秒空闲/6.5 秒心跳/断开自退）**；WB test_live_idle | M20 等价（inflight 重叠，实验证明）；M25 空闲分支(C，一审点名项 4) |
| D31 创建 201+八键 | jobs-service 创建/查询 | G01 流水线 jobs（只认 201、恰好八键、data/ok 不在、id 43 位、queued+四 null）+ README 201（V08） | — |

结论：31 条 DoD 每条都有内核复跑 exit 0 的机械证据；一审认定的三处 G01 无独立判据项（D11/D21/D24）分别由白盒变异（M35/M36 CAUGHT）与 V09/V10 补足，与一审的处置要求一致。

## 五、边界与完整性

- **累计范围**：attempt-002（21 文件）+ attempt-003（3 文件）全部落在 ts/packages/ui/{src,test,README.md}；src 下动到的 events/jobroutes/jobs/kernel/kernelenvelope/readroutes/server/watch 均在允许面，localhttp/** 零改动（G01 静态 localhttp_and_deps 绿）；main.ts（UiArgs）未动；package.json/锁文件未动（V01 frozen-lockfile 绿、V07 must_not_match 非 ui 路径为 false、scope.json violations=[]）。tests/（Python 门禁）零改动——基准测试锁定（f62eeac1b3）未被触碰。
- **D11 未放宽**：attempt-003 未动 service.test.ts；G01 静态 jitter_harness 哨兵（heldBack/sent/65537/ECONNRESET/无 skip-only-todo）在内核复跑中绿。
- **G01 静态断言未靠改测试适配**：attempt-003 唯一测试改动是 jobs.test.ts 第 74 行 `"a\x01b"`→`"a\u0001b"`（字面 U+0001 改为转义写法），运行时字符串值不变、仍覆盖「pattern 含控制字符回 400」，系 source-hygiene（V03）对不可见字符的要求所致；锁定哨兵对该文件的要点检查全部保持。不存在为过静态检查而放宽断言的情形。
- **执行报告与内核记录一致**：G01 32 passed、R01 597 passed、V04 625 passed/55 files 等与内核 checks.json 逐项相符（唯一口径差是任务书里「预演 629」，见观察 3）。

## 六、不阻塞的观察（供站主与后续片参考）

1. **M20 的机理表述**：门禁端引用「SSE 请求在 app.ts 的 inflight 计数里直到流结束才递减（app.ts:94/148）」。按 async/finally 的静态读法，处理函数返回流式 Response 时计数即应递减；但变异实验（idle-open 在变异体上以进程级断言观察 6.5 秒全绿）只在与该引用一致的运行时行为下自洽。等价结论由实验直接支撑、不受机理表述影响；建议后续片若要复用该结论，以实验为准并可加一条直接断言 inflight 的用例把机理钉死。
2. **M21 与仓库外事实的张力**：变异体上心跳 500 毫秒使连接在 idleTimeout=2 秒下活过 6.5 秒，说明所测 Bun 版本里服务端写数据会重置空闲计时；而规划期记录的站主实测事实是「服务端写数据不重置空闲计时」。两者必有一处随 Bun 版本变化。候选代码是安全侧（timeout(req,0) 在位、锁定 G01 静态钉住），无需改动；建议把这条张力记入仓库外事实表备查，Bun 升级时复核 G01 流水线 12 秒存活检查的语义。另：白盒套件如想直接抓住 M21，可加一条心跳间隔 > idleTimeout 的配置（现行 hb500ms<idle2s 配置由合同 D10 原文指定，门禁端照写无过）。
3. **口径差异**：任务书摘要「预演 629 passed」与内核 V04 记录的 625 passed（执行报告同 625）不一致，疑为汇总口径差；以内核 checks.json 为准，不影响结论。
4. **一审 3 条旧观察**（idleTimeout 空值合并正则口子、「八键」散文词、名单模板全局否定）维持原状，按封板纪律不升级；本片未使其恶化。

## 七、裁定汇总

- 实现忠实于合同 v4：是（§1、§4、§5）。
- 越界或弱化测试：无（§5）。
- 门禁端声明的等价变异：M20、M21 均成立（§3）。
- 门禁端说没法变异的改动文件：无此类声明。
- 门禁端举证的候选缺陷：本节输入无此清单。
- JEV 两处关注：均不成立（§2）。
- 执行预算已用尽：本裁定不触发执行端返工，无需追加预算。

**最终结论：通过。**

Verdict: PASS
