# 复审记录：t037-desktop-web-writes attempt-001（七端信箱 hub）

- 合同：t037-desktop-web-writes.v1（base 51a41a994e526a2a4a7199377528301b2b8c2473）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T044141564484Z-1de3），终审报告如下

## 终审报告

# T037-7-audit-post 终审报告（audit-sonnet）

**结论：通过。** 候选（attempt-001）忠实实现了合同 `.agent/plans/t037-desktop-web-writes.v1.md` 的行为约定；范围、测试完整性、报告自述三方面都没有需要打回的问题。

## 一、材料与证据来源

- 合同：`.agent/plans/t037-desktop-web-writes.v1.md`（v1，站主两条硬要求附在末尾）。
- 候选补丁：`.agent/runs/t037-desktop-web-writes/attempt-001/candidate.patch`（6 个文件，全量读完）。
- 执行报告/概述：同目录 `executor-report.md`、`summary.md`、`scope.json`。
- 内核独立检查：同目录 `checks/01/checks.json` + `G01.log/R01.log/V01.log/V02.log`（fresh 验证工作区 `…-verify-d4ji6p66`，候选树 `385c7e5a…`，`modified_by_checks:false`，`all_required_passed:true`）。
- 战后门禁：`.agent/mailbox/tasks/T037-6-gate-post/report.md` + `evidence/whitebox-20261114T043640536333Z.py`（白盒探针）+ `evidence/mutate-…/mutations.json` 与工作目录里的 `mutation-spec.json`（38 条变异，逐条读过锚点）。
- JEV 判断：`.agent/mailbox/tasks/T037-6j-jev/report.md`（`no_opinion auth_failed`，无意见需处理）。
- 本回合没有「门禁端举证的候选缺陷」一节；门禁报告自述 `candidate_defects` 为空，故无候选缺陷需要逐条裁定。

## 二、实现忠实性（逐条核合同 Behavior contract）

**传输层 `desktop/web/src/live/transport.ts`**
- 抽出了唯一的内部请求函数 `request()`（取时限 → AbortController → 发请求 → 读正文 → 写连接状态），`get`/`post`/`getRaw` 三个公开方法都走它 ✓。
- `timedOut || (error as Error)?.name === 'AbortError'` 在全文恰好两处，都在 `request()` 内（源码核对 + 门禁静态断言 `count(ABORT_CHECK)==2`）；`setTimeout`/`clearTimeout` 仍在 ✓。
- `post` 的请求形状：`method:'POST'`、`credentials:'same-origin'`、带 `signal`、headers 只有 `Content-Type: application/json` 与 `X-Themis-UI: 1`、正文 `JSON.stringify(body)`；**不拼 `Origin`**、不带任何凭据头 ✓。
- `post`/`getRaw` 回 `{ status, body }`，状态码原样 ✓；`get` 仍 resolve 一个七字段信封、**绝不 reject** ✓。
- 合成规则：`envelopeOf()` —— 合法信封原样；否则 503 → `ERROR: 服务繁忙（排队过长），请 N 秒后重试`（N 读 `Retry-After`，缺省 2）、≥400 → `ERROR: 服务返回 HTTP <码>`、其余（含 200 坏 JSON）→ `ERROR: 服务的响应不是合法的 JSON（HTTP <码>）` ✓ 与合同逐字一致。
- 401：先 `runReauth()`（与 `get` 同一套并发去重，兑现后清空），再回 `{status:401, body:合成失败信封}`，`messages` 固定 `ERROR: 会话已失效` ✓（`post` 与 `getRaw` 都如此）。
- 「没有回应」（fetch 抛错且非我方中止、读体失败、我方超时）：`post`/`getRaw` **reject**，`Error` 文案沿用定稿文案（超时带秒数、断线固定句），连接状态写 `disconnected` ✓。
- 时限 = 服务端时限 + 5 秒；请求结束（成败都算）`clearTimeout` ✓（假计时器下 `vi.getTimerCount()===0` 有断言）。
- `get` 的六条定稿文案一字未改，分类顺序（401→503→≥400→200）与旧实现一致 ✓。

**`desktop/web/src/live/mode.ts`**：只给 `LiveClient` 类型加了 `post`/`getRaw` 两个成员；三个函数、`BUILD_MODE`、`declare const __THEMIS_LIVE_MODE__` 未动；导出集合仍是四个（`liveModeIsReal`/`liveClient`/`setLiveClientForTests`/`LiveClient`）✓ 站主第二条硬要求满足。

**`desktop/web/src/api.ts`**
- 501 分支与 `unwired<T>()` 已删，「ERROR: 写操作尚未接通」一句已删；文件内无四个网络整词（grep 复核：`fetch|XMLHttpRequest|EventSource|WebSocket` 零命中）✓。
- 15 个读函数、`getMetaNow`（仍是 `clone(metaJson)`）、既有类型与夹具分支一字未改；十个写函数仍是 `export function <名>(` 的写法，签名未变 ✓。唯一的内部改动是 `okEnvelope` 的 `data` 参数放宽成 `T | null`（执行端 interpretation 7，读函数调用点与返回值不变）✓。
- 参数整理 `writeArgs()` 一个函数，预览与执行共用：空串不传、空数组不传、名为 `number` 的键用 `Number()+isFinite` 转 JSON 数字（转不成就原样传）、数组按序原样 ✓ —— 合同要求的「同一份整理规则」（否则服务回 409 参数不符）满足 ✓。
- `preview`：POST `/api/v1/preview`，正文 `{action, args:整理后}`，时限 30 秒；成功条件 `status===200 && body.ok && data 是对象 && confirmation 是字符串 && preview 是对象`，映射出 `{role,from,to}`（显示规则 profile → provider/model → 单一 provider|model → mode → `—`）、`resources`（按服务次序不去重）、`notes` 后面接 `unreadable`、`warnings`/`running_attempts`/`needs_yes`、`command` 取**信封顶层**、`confirmation` 原样 ✓；不成时状态码与信封原样透传 ✓。
- `getOperation`：GET `/api/v1/operations/${encodeURIComponent(id)}`，走 `getRaw`，时限 30 秒；200 包成 `{ok:true, exit_code:0, data:八键视图, output:[], messages:[], command:[], elapsed_ms:0}`，`envelope` 非合法七字段取 `null`，正文非对象或缺 `state` 时 `data` 取 `null`；404 与其他状态码原样透传 ✓。
- 十个写函数逐条对上合同的表（路径、正文「路径参数以外的参数 + confirmation」、路径段 `encodeURIComponent`、时限 90 秒、没有回应时 reject）：`usePreset`/`setPluginEnabled`(enable|disable)/`removePreset`/`removeProfile`/`removeRuntime`/`rollback`(`String(number)`)/`addProfile`/`editProfile`/`setHubRole`(`profile`+`fallback?`)/`unsetHubRole` ✓ 全部一致。`setHubRole(args:{post,profile,fallback?}, confirmation)`、`unsetHubRole(post, confirmation)` 的签名与合同逐字相同 ✓。
- `WriteAction` 增 `'hub.set'`/`'hub.unset'`，其余九个成员未动 ✓。

**`desktop/web/src/mock/writes.ts`**：`baseArgv` 增 `config hub set <post> <profile> [--fallback=…]` 与 `config hub unset <post>`；`NEW_ACTIONS` 增两个 action；新增 `mockSetHubRole`/`mockUnsetHubRole`（走现有 `confirmWrite`）；`previewData` 给两个 hub action 一条分支（`binding_changes` 恒空、`resources:['hub']`）；`WriteScenario` 的 22 个值与其余 action 行为未动（grep 复核 22 项齐全）✓。

**结论：实现与合同一致，未发现越界实现。**

## 三、DoD → 测试 → 断言 映射（每条都有独立证据）

| DoD | 由谁证明 | 具体断言 |
|---|---|---|
| D01 | `live-transport.test.ts`「post 的请求形状」+ 门禁探针「POST 的方法/两头/JSON 正文」 | `init.method==='POST'`、`credentials==='same-origin'`、`headers.get('content-type')==='application/json'`、`x-themis-ui==='1'`、`origin` 为 null、`authorization` 为 null、`init.body===JSON.stringify(body)`、带 signal |
| D02 | `live-transport.test.ts`「post：断线 → reject」「post：假计时器下的超时 → reject」「getRaw：断线 → reject」+ 门禁探针 | `rejects.toThrow('ERROR: 连不上本机服务（请求没有到达服务）')`、`rejects.toThrow('ERROR: 请求超时（35 秒），没有收到服务的回应')`、`getConnectionState()==='disconnected'`、同客户端 `get` 仍 `toEqual(failureEnvelope(...))` 不断言 reject |
| D03 | G01（T034 s09）+ 门禁静态 `test_w0` | `transport.count('timedOut || (error as Error)?.name === \'AbortError\')==2`；`setTimeout`/`clearTimeout` 仍在 |
| D04 | G01（T027 S03 / T034 s13 / T036） | `mode.ts` 导出集合恰好四个；白盒探针「注入取注入值、null/undefined 回到无注入」 |
| D05 | `live-api.test.ts`「preview：POST /api/v1/preview…」「preview 的参数整理…」「preview 成功：PreviewData 的映射…」「preview 不成…」「preview：200 且 ok 但 data 缺 confirmation…」 | `posts[0].path==='/api/v1/preview'`、`body` 逐字相等（`{action,args}`、`number:41`、`'x4?'` 原样、空串/空数组不传）、`timeoutSeconds===30`、`binding_changes` 三行 `{role,from,to}`、`resources===['roles','config','roles']`、`notes===['note-1','读取不到 roles/build']`、`command===PREVIEW_COMMAND`、`confirmation==='c12345'`、400/500/503/200-ok:false 与缺 confirmation 均 `toEqual(原信封)` |
| D06 | `live-api.test.ts`「getOperation：GET /api/v1/operations/<编码后的号>…」「envelope 不是合法七字段信封取 null…」「404 透传」+ 门禁探针 | `raws[0].path==='/api/v1/operations/op%201%2Fx'`、`timeoutSeconds===30`、`body.data` 等于八键视图、`envelope` 为 null、非对象/缺 `state` 时 `data` 为 null、404 时 `body` 原样 |
| D07 | `live-api.test.ts` 的 `WRITE_ROWS` 12 行（表驱动）+「执行回 409 且 exit_code null…没有回应 → reject」 | 每行断言 `posts[0].path`、正文逐字相等、`timeoutSeconds===90`；409 时 `status===409 && exit_code===null`；无回应时 `rejects.toThrow('连不上本机服务')` |
| D08 | G01（S06 的 `export function` 写法与 11 个路由前缀、S10 的四个网络整词扫描）+ `live-api.test.ts` 的「不再回 501」断言 | `expect(reply.status).toBe(200)`（不再是 501）、api.ts 内四个网络整词零命中、读函数与 `getMetaNow` 未动（diff 核对） |
| D09 | `live-api.test.ts` 夹具分支 describe（未改）+ 门禁探针「mock hub 桩」3 条 + T022/T024 门禁 | 22 个情景值未动；探针断言 `hub.set` argv 含 `--fallback=`、`resources===['hub']`、确认后 200、参数不符/跨 action 的确认号 409 且 `exit_code` 为 null |
| D10 | `live-api.test.ts` `WRITE_ROWS` 的 `setHubRole`/`unsetHubRole` 两行 + 白盒静态接线 | `posts[0].path==='/api/v1/hub/roles/build'`、`body` 为 `{confirmation, profile, fallback}`（路径参数 `post` 不进正文） |
| D11 | G01（T034 s10：`it(` 条数只增不减、无 `skip`/`only`/`todo`）+ diff 审阅 | 传输层 19→29 条静态 `it(`（grep 复核 29 处），既有 19 条一行未改（补丁只有一个追加 hunk）；`live-api.test.ts` 只替换 501 那一个 describe，其余 describe 一字未改（补丁只有 3 个 hunk） |
| D12 | `scope.json` + G01 的 digest 断言 | `A0 M6 D0 T0`、`violations:[]`、`ok:true`；改动文件正是合同的 6 个；禁改清单（含两份写入口过渡用例、`src/writes/**`、`ts/**`、锁文件）零改动 |
| D13 | 内核独立跑 V01/V02 | `checks/01/checks.json`：V01 exit 0（`Tests 1035 passed`/110 文件）、V02 exit 0（无输出） |
| D14 | 内核独立跑 G01/R01 | G01 exit 0（`10 passed`）、R01 exit 0（`903 passed`），两条的 `output_must_match` 均 `matched:true` |

无「只能人工审阅」的 DoD。

## 四、测试完整性（有没有靠弱化测试换绿）

- 传输层测试只**追加**一个 describe（10 条），既有 19 条逐条未改；`live-api.test.ts` 按合同允许替换了 501 那一个 describe，其余 describe 未动；两份文件均无 `skip`/`only`/`todo` ✓。
- 新断言不是空心断言：`live-api.test.ts` 断言的是 api.ts **实际发出的路径/正文/时限**与**实际做过的映射**（用假客户端记录调用参数），不是「文件里有这段文字」；传输层断言的是注入假 fetch 后**真实请求的 init** ✓。
- 没有把业务逻辑抄进测试：假客户端只回放编排好的返回值，映射与整理规则都在被测源码里执行 ✓。
- 没有为过测试而写的特判：api.ts 里没有按 action 分支的“测试专用”路径；`toPreviewData`/`toOperationView` 的容错与缺省值（畸形项跳过、`created_ms→0` 等）是执行端 interpretation 4 明写的取舍，行为可解释。
- 门禁端的白盒是**独立新增**的探针文件（`tests/test_gate_t037_whitebox.py`，31 条 it），不依赖执行端的两份测试；38 条变异（transport 12 / mode 2 / api 18 / mock 6，每个改动的源文件 ≥2 条）逐条被抓住，**无 equivalent、无 expect_missed、无 unmutated**；两条执行端测试文件不要求变异（它们是测试文件），这点合理。

## 五、执行报告自述核对（内核摘要的线索逐条对上）

- 内核摘要标出的「退出码被管道掩盖（6 条，如 `npx tsc --noEmit 2>&1 | head -n 30`）」：执行器确实没看到那些探索命令的退出码，但**四项必跑检查由内核独立复核过**（`checks/01/checks.json` 里 V01/V02/G01/R01 全部 `exit_code:0`、`passed:true`、`output_must_match.matched:true`，且跑在 fresh 验证工作区上）。报告自检表里的四条结果属实 ✓，不是推断值冒充实测。
- 内核摘要标出的「2 处提到合同的歧义」：报告把两处都落在 `interpretations`（第 1 条 getRaw 非法正文、第 2 条 getRaw 的 401），`contract_conflicts` 为空。**我逐条核对了这 8 条 interpretation 与源码，全部相符**：关键一条是第 1 条 —— `parseJson()` 在 JSON 解析失败时返回 `undefined`（不是抛错），`getRaw` 用 `result.json === undefined` 判定「正文不是合法 JSON」并按状态码合成失败信封，与报告描述一致 ✓（这一点与内核引用的事件流第 4897 行那段推理不矛盾）。
- 报告里唯一的小笔误：说 `live-api.test.ts` 的新 describe 是「21 条」，实际是 22 条（10 条静态 `it(` + `WRITE_ROWS` 12 行）；同句的「总计 46 条」与 V01 日志的 46 一致 ✓。不影响任何 DoD 结论。
- 内核摘要标出的新增被 Git 忽略路径（`.pytest_cache/`、`desktop/web/dist/`、`node_modules/`）：均为忽略项、不进候选；执行器在报告里也写明跑 V01/V02 前做过一次 `npm ci`，依赖清单与锁文件一字节未动（G01 的 digest 断言确认）✓，属 `local_test` 范围。
- 没有发现「自述与实现不符」的情形；D01…D14 的自述状态与源码、测试、检查记录逐条对得上。

## 六、不挡的意见（交站主决定，不构成打回）

1. **`get` 的 401/503 现在也先读正文**：旧实现对 401/503 直接回固定文案、**不读正文**；新实现因合同要求三个公开方法共用一个内部请求函数（该函数按约定「读正文」），会先读正文。触发路径：本地服务在**已发出响应头、尚未写完正文**的窗口里被关停/重启 → `response.text()` 抛错 → `get` 回 `ERROR: 服务返回 HTTP 401`（且**不调 reauth**）或 `ERROR: 服务返回 HTTP 503`，而旧实现会回 `ERROR: 会话已失效`（并 reauth 一次）/ `ERROR: 服务繁忙…`。概率：本地服务在亚毫秒窗口里被停掉的概率极低；后果是错误文案不对、会话不自动续期，不是数据或安全问题。要完全对齐旧行为约需 6~10 行（在内部函数里把 401/503 的固定文案提前判掉，或读体失败时按状态码优先取固定文案），但会与合同「唯一一条超时路径/共享内部函数」的写法更复杂。**按罕见边界处理，不挡。**
2. **`writeArgs` 的 `number` 转换用 `Number()`**：`'0x10'`→16、`'1e3'`→1000 也算「转成」。合同只说「转成 JSON 数字（转不成就原样传）」，UI 的编号来自十进制输入，风险极低。已由门禁探针钉住（`' 41 '`→41、`'0'`→0、其余键的数字样字符串保持字符串）✓。
3. **`api.ts` 注释里留着「不改写成 501」字样**：当前 `\b501\b` 的门禁断言已退役（T027 s06 两行，提交 5825e71），R01 全绿；若将来恢复该断言，这行注释会误伤。建议顺手改措辞。
4. **真实模式的 CSRF 三查只验到两头**：`Origin` 由浏览器自带，本片证据是注入假 fetch 的探针，只能上真机联调验证。

## 七、给片 2 的提醒

- `useWriteFlow` 的 `confirm()` 分派链末尾兜底仍是 `setPluginEnabled`，`hub.set`/`hub.unset` 没有分支；`readSnapshot` 在真实模式下仍认 `?write=reread-fail`（合同的 Non-goals 与合同端下游须知第 5 条）。
- `useWriteFlow` 现有代码对 `preview` 的 reject、`503`、`!body.ok`、以及 `getOperation` 的 404/reject 都有分支，真实模式接上后不会因为 `data` 为 null 而崩（`r.body.data` 有非空判断）；但 `needs_yes`/`unreadable` 的显示与真实模式的流程集成测试仍待片 2。
- `api.ts` 里 `setHubRole`/`unsetHubRole` 的函数名与桩名已定（合同端下游须知第 6 条），片 2 直接对齐。

## 八、最终判定

实现忠实、范围干净、测试没被削弱、内核独立检查与门禁记录一致、报告自述属实。**结论：通过**，不退回任何对象。

Verdict: PASS
