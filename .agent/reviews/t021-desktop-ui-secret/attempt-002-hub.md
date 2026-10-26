# 复审记录：t021-desktop-ui-secret attempt-002（七端信箱 hub）

- 合同：t021-desktop-ui-secret.v3（base 67ee624029f439423f4571bf57125b1528626648）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261026T081102125713Z-9a62），终审报告如下

## 终审报告

# T021-7-audit-post 终审报告（audit-sonnet）

## 一、审阅对象与方法

- 候选：attempt-002（返工轮，执行端未新增编辑；候选树 2748364 = 工作目录，基线 67ee624 已含 a001 全部改动，candidate.patch 为空是返工轮的正常形态）。改动实体以 a001 的 candidate.stat.txt 为准：14 文件、+1483/−31。
- 方法：先通读候选源码（secretentry.ts 307 行全文、kernel.ts、jobs.ts、jobroutes.ts、routes.ts、app.ts、server.ts 接线段、readroutes.ts 的 export），再读四个测试文件与替身全文，最后核内核检查记录（checks.json）、变异记录（mutations.json 27 条逐条）、白盒测试 py 全文与执行报告。
- JEV（T021-6j）：自行解读合同 p=0.06、无证据自述 p=0.07、越界 p=0.06、弱化测试 p=0.04，均低；与我的独立核查一致。

## 二、实现忠实性（合同 §一–§九 逐节）

- §一 录入路由：`api.secrets.entry`、POST、`^/api/v1/secrets/([^/]+)/entry$`、不标 public；校验次序（正文对象→无键→allowEnvName→canAccept→表满）与三句 400 提示、两种 503 带 `Retry-After: 2` 且不建作业，逐字对上；201/504/502/503 的正文形状 `{job, url}`、job 恒八键。
- §二 常量：600/30/630/15/30 全在；`--timeout=${SECRET_ENTRY_PAGE_SECONDS}` 恒 600、不受 timeouts 覆盖；覆盖项只有 `job.secret-entry` 与 `secret-entry.handshake` 两处。
- §三 握手：PAGE_URL_RE 两头锚定、定长 32、端口 1–65535 整数核；只认完整行（`endsWith("\n") ? lines : slice(0,-1)`）；`decided` 标志收住四事件竞态，只认第一个。
- §四 地址去向：url 只存在 EntryAttempt 闭包；jobView 八键无 url；访问日志 `accessLog.record(name, status, ms)` 只记路由名；messages 走 `messagesOf`（与 jobroutes 的 jobMessages 同一规则：ERROR/WARN 前缀 + redactSecrets，kernelenvelope.ts:29 核实）；command 用 displayArgv(argv)，令牌不在 argv。
- §五 到点次序：handshakeDeadline 先 `settle(timed_out)` 再 `controller.abort()`，次序正确（settle 只认第一次，后到的 interrupted 映射覆盖不了 timed_out）。
- §六 kind 放宽恰好两处字面（JobRecord.kind、JobTable.create）；四张 JOB_* 表六项未动；`exited` 初值 Promise.resolve()、录入作业在子进程结束时落定、六类作业 exited=run；重查只在 `attempt.url !== null` 时做，用新的 recheckController 信号、`secretCheckData` 投影无 file_dir；八种终态映射（succeeded/exit/invalid-json/cancelled/timed_out/spawn-error/output-too-large/closing）逐条对上，data 一律 Map 构造的 `{set, check}`；set 白名单 `["name","stored","backend","error"]` 只留实际出现的键、丢 verified、不写死键数。
- §七 控制门：Route.control 统一判定；Origin 先于令牌（外来 Origin 不计限速）、429 带 Retry-After、过门后 `body: undefined` 免 CSRF 免正文；app.ts 里按路由名 `control.bootstrap` 的特判删净（白盒断言 + 全文核实）；control.bootstrap 保留 public:true 再加 control:true，处理函数只剩 revokeAll×2 + 发 nonce；control.jobs.cancel 标 control、不标 public、只调 cancelJob；未做空闲超时放宽。
- §八 cancelJob 共用：404→409→abort→`await record.exited`→200 当时八键；api.jobs.cancel 仍验正文、control.jobs.cancel 不读正文。
- §九 server.ts 两批构造各自并进 `secretEntryRoutes(runner, jobs, timeouts)`、未合并（T020 非阻断建议照规划留待另片）；readroutes 只加 export；README 纯追加 14 行；routes-auth.test.ts 纯追加 49 行（entry 不带 cookie 401）。

无对测试输入硬编码、无空异常处理（openEvents 的空 catch 是测试内 SSE 关闭清理，有注释）、无为过测试的特判、无悄悄扩大的范围。

## 三、DoD → 证据 终审映射

| DoD | 证据 | 判定 |
|---|---|---|
| D01–D03 | secret-entry.test.ts：argv 逐字（对照导出常量+字面双断言）、三类 400 均断言 begins==[]（不起子进程）、两种 503 带 retry-after 且不建作业；反例表 10 条全断言非 201 且 url null，另有同应用同链路的正面对照 201（防「根本没读到」的假阴性） | 忠实 |
| D04 | 五处搜令牌（作业查询/SSE/messages/command/accessLog）+ 断言 accessLog 里确有 api.secrets.entry 条目（防「日志没记」假阴性）；白盒 jobView 八键无 url | 忠实 |
| D05 | 504 三种；waitDead 用 pidAlive 轮询带上限；排队占位断言 started_ms null 且 begins==1 | 忠实 |
| D06 | 终态五例映射 + set 白名单断言「键都在白名单、无 verified」（不写死键数，照一审须知）+ check 四键无 file_dir + 取消/超时后 check 不为 null | 忠实 |
| D07 | kind=secret-entry→400 + 四表六项 + begins==[] | 忠实 |
| D08 | server.ts 源码核实两批都含 secretEntryRoutes(；白盒按块断言；M24 变异杀掉 | 忠实 |
| D09 | control-routes 表驱动三条 control 路由×三种拒绝 + probeRan=false + 注入时钟的 429/恢复 + 外来 Origin 不计限速 + /control/ 双向不变量用例；白盒钉 Origin 先于令牌（下标比较） | 忠实 |
| D10 | 404/409/200 八键；「取消不等重查」门文件卡先后：响应先到、作业仍 running、放行后 cancelled 且 check 非 null | 忠实 |
| D11 | 取消后 pidAlive false + waitDead；服务一侧超时 timed_out 且 check 非 null | 忠实 |
| D12 | secret-entry-real.test.ts：前置 store_mode==file、system_backend==null 是硬 expect（不符即失败、不录入，一审要求满足）；假值 25 个可打印字符无空白（过 looks_like_secret）、字段名 value；env 只经 startService({env})；录入后 succeeded、check.source=file、临时 XDG 下文件内容逐字核对 | 忠实 |
| D13 | R01 677 passed（checks.json 独立复核）、G01 15 passed、V02 13 passed；public:true 恰好两处（routes.ts 源码核实） | 忠实 |
| D14 | 变异记录 27 条 26 抓 1 预期漏；合同 M1–M22 逐条有对应（见第四节） | 忠实 |
| D15 | a001 stat：14 文件全在 allowed 集合；四个禁改测试文件与门禁 py 不在其中；依赖与锁文件未动；checks.json 的 scope/violations 为空 | 忠实 |
| D16 | routes-auth 49 行纯追加（stat 无 −，且新增段自带「既有 19 条一字不动」注释，T017 门禁 G01 过）；新测试文件 grep 无 skip/only/todo | 忠实 |

## 四、expect_missed 逐条裁定（任务书点名的 6 条）

1. **se-incomplete-line（M06）vitest 漏**：成立。替身握手行恒带 `\n` 且一次写完，行为面构造不出不完整尾行；只有白盒的切片行锚点能杀。已杀。
2. **jobs-kind-narrow（M13）vitest 漏**：成立。纯类型收窄，vitest 只转译不类型检查；tsc（V03，候选上通过）与白盒都能杀。已杀。
3. **jr-cancel-no-abort（M17）vitest 漏**：**声明不成立但方向保守**——记录里 vitest 实际抓到（unexpected_caught）：「取消不等重查」用例在子进程自然退出后作业会落 succeeded 而非 cancelled，断言失败。变异被杀，无需动作，记录在案。
4. **server-entry-out-of-relaxed（M24）vitest 漏**：成立。变异命令只跑三个进程内文件，都不建真 Bun server；secret-entry-real 不在该命令内且其握手即刻到达、空闲超时碰不到。白盒按赋值块断言，已杀。
5. **readme-ctrl-path（M26）vitest 漏**：成立。vitest 不读 README，白盒已杀。
6. **fixture-never-handshake（M27）whitebox 漏**：成立。白盒是纯静态、九个锚点文件里没有替身（读 py 全文核实），vitest 的 201 用例杀掉。

无 equivalent 声明；「没法变异的改动文件」无——27 条覆盖全部 9 个非测试改动文件加替身，测试文件按岗位口径不出变异，口径正确。

## 五、检查与门禁记录核对

- checks.json（独立 verify 工作区）：G01 15 passed / R01 677 passed / V01 332 passed / V02 13 passed / V03 空输出，五项 exit 0、output_must_match 全 matched；tree_before==tree_after、candidate_files_modified 为空——检查没有改候选。
- 变异基线：whitebox 9 passed、vitest 40 passed（21s）；干跑后 files_left_modified 为空、git status 干净（门禁报告§四）。
- 门禁报告声明与 mutations.json 逐条相符（26 抓 1 预期漏、counts_by_command 的 expected_missed 4+1）。
- 执行报告：summary.md 提示的 3 处「歧义提及」核了事件流摘录——是执行器在看上一轮 REVISE 判决时的自查，报告 interpretations/contract_conflicts/unresolved_questions 均空，与候选一致；掩盖退出码的 4 条命令均为 git show/head 类只读命令，不是测试或检查命令，不影响结论。

## 六、非阻断意见（不影响结论，站主酌定）

1. 「请求先断开→不回响应」实现为客户端已走后写一个到不了的 503 占位（app.fetch 必须返回 Response），测试断言 503 占位；语义等价，建议 D3 外壳侧对接时知悉。
2. recheckController 本身没有挂关停中止，但 runner.run 在 closing 时直接回 closing、关停会 abort 在跑的 entry，重查不可能活过关停——「只跟服务关停走」的意图实质满足，无需改。
3. M17 的 expect_missed 声明与实际不符（保守方向），下轮门禁出 spec 时可把「取消用例的子进程无门文件自然退出」这条理由改准：无 abort 时终态断言（cancelled）会失败，vitest 其实抓得住。

## 七、结论

**通过**。实现忠实于合同 v3，无越界、无弱化测试、无候选缺陷；门禁端无 candidate_defects 上报，变异清单与白盒锚点足以守住本片的全部关键边界。

Verdict: PASS
