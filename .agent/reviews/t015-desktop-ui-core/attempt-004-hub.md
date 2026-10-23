# 复审记录：t015-desktop-ui-core attempt-004（七端信箱 hub）

- 合同：t015-desktop-ui-core.v5（base 2db233a13eb982bc89fbc138a4259393e3e60019）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 1；变异检查退出码 None
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T015-7-audit-post 终审报告

## 0. 结论
**返工**，退回**执行端**。D01–D05、D07–D17 判满足；**D06 不满足**（门禁端举证的缺陷成立）。阻塞项 3 条，全归执行端；另有 2 条给下一轮战后门禁的注意事项（§5.4），本轮不作为退回对象。

## 1. 那处候选缺陷的裁定：**成立**

### 1.1 以哪一处说法为准
以**合同路由表（v5.md:114）+ D06 DoD（v5.md:274）**为准，管线第 4 步（v5.md:122）不适用于 `control.bootstrap`。理由三条：
1. **专条压通条**。v5.md:118–125 的管线是 `createApp` 的**通用**次序描述；v5.md:112–117 的路由表是**逐条路由**的规定，其中 control.bootstrap 那条写的是「要 Host、`controlOriginAllowed`、`ControlGate`，**不读正文**」——这是一个穷举的门列表（同一段里 api.ping.post 那条则明写「要会话、CSRF、JSON 正文不超过 64 KiB 且必须是 JSON 对象」，可见合同是**按路由**分配 CSRF 与正文要求的，不是所有 POST 一刀切）。既然 control.bootstrap 那条列了三个门并明写不读正文，就没有第四个门（csrfCheck）的位置。
2. **DoD 是验收标准，而候选与它相冲**。D06 原文：「不带令牌、令牌错、只带 cookie 都是 403；**对的令牌是 200** 并给出新的引导地址」。候选把 200 的前提扩到「同源 Origin + `X-Themis-UI: 1` + `Content-Type: application/json` + 合法 JSON 对象正文」四项，只带对令牌的请求回 403/403/415/400。这不是措辞分歧，是行为不达标。
3. **D06 的目的句**：「只有外壳能换引导地址，网页不能把外壳的重新认证锁死」。候选让 reauth 依赖一套页面侧（浏览器 fetch）才会自然带上的头，恰好把「换引导地址」这条命脉绑在最不可靠的假设上。

### 1.2 外壳风险：**成立**（这是裁定的决定因素）
- docs/themis-tally-3.0-桌面端.md:404：「外壳带着控制令牌 `POST /control/bootstrap`（头 `X-Themis-Control`），向服务要一个新的一次性引导地址」——**只提控制令牌头，没有正文、没有 Content-Type、没有 X-Themis-UI**；:778 的路由表、:902 的 U16 用例同样只提控制令牌；:623 的 `host.reauth()` 也只说「外壳用控制令牌要新的引导地址」。
- 外壳的请求发自 **Electron 主进程**（docs:741：外壳只把 `control` 留在主进程里）。主进程的 `net`/`fetch` 发无正文 POST 时不会带 `Content-Type`，也不会带页面侧注入的 `X-Themis-UI: 1`，`Origin` 亦可能缺。
- 因此候选下真实外壳的 reauth 会先撞 **403（缺 X-Themis-UI）→ 415（缺 Content-Type）→ 400（无正文）**，会话 401 之后页面永远换不到新引导地址，落到 UI 设计 :999 的兜底「切到服务状态外壳页」。站主实测记录 F9 已说 Electron 的请求头未核实——**在这一点未核实之前，唯一稳妥的实现就是让控制接口不依赖正文与 CSRF 头**，因为它在两种可能的外壳实现下都能工作，而候选只在其中一种下工作。
- 反向核对：把 control.bootstrap 豁免掉 CSRF 三查**不削弱安全**。控制令牌是 32 字节 base64url、恒定时间比较（两份 SHA-256 摘要 + timingSafeEqual，缺头/长度不同不抛错）、只留在外壳主进程、从不写进日志（D08）；`controlOriginAllowed` 仍挡外来站点且不计入限速；`ControlGate` 的 5 次失败锁 1 秒/翻倍/60 秒封顶照旧。页面拿不到令牌，`X-Themis-UI: 1` 这种「自定义头」相对令牌只是弱得多的凭据。

### 1.3 为什么内核的九项检查没测出来
`tests/test_gate_t015_baseline.py:1333–1420` 的控制组（check_control）每一次请求都发 `Origin + X-Themis-UI: 1 + Content-Type: application/json + body=b"{}"`（:1338–1341、:1358–1361），ASSUMPTIONS ②（:90）也明写「照两种读法都成立的方式发」。所以 G01 全绿与该缺陷并存是**设计使然**，不是漏测；能测出它的只有战后白盒那条按合同读法钉的用例。这也说明：G01 绿不能作为 D06 的完整证据。

## 2. D01–D17 逐条结论

证据基准：`.agent/runs/t015-desktop-ui-core/attempt-004/checks/01/checks.json` —— 内核在独立 worktree 自跑，`all_required_passed: true`、`covers_all_required: true`、`modified_by_checks: false`、`candidate_files_modified: []`、`unexpected_files_by_checks: []`、tree_before == tree_after == f647c9d…（候选树未被检查改动）。九条 exit_code 全 0：G01 25.7s、R01 510.6s、V01 0.1s、V02 2.1s、V03 11.8s、V04 87.0s、V05 0 字节日志（tsc 无输出）、V06 9.3s、V07 0.03s，`output_must_match` 全 matched，V07 的 `must_not_match`（范围外改动）未命中。**这些是权威退出码**；执行端 self_checks 里的 reported_exit_code 因 17 条命令被管道掩盖（summary.md「复审需要关注」）只能当参考，本报告的结论一律以 checks.json 为准。

| DoD | 结论 | 证据出处 |
|---|---|---|
| D01 握手与绑定 | 满足 | G01 handshake 组（checks.json G01 passed；baseline :1084 断言五字段与次序、:1086 断言 origin）；候选 server.ts 握手行（patch:1298 `themis_ui: 1,`，取值与 docs:741 一致）；V03 service/launcher |
| D02 会话与引导地址 | 满足 | G01 session 组；候选 readSessionCookie 重复 cookie 返回 null（白盒 test_whitebox_session_and_cookie 钉住）；V03 app/service |
| D03 一次性与 60 秒 | 满足 | G01 rejection 组；白盒钉 `NONCE_TTL_MS = 60000` 与「先无条件删再判 `now() - issuedAt < ttlMs`」（59999 可用/60000 拒绝）；三种拒绝共用同一个 404 |
| D04 Host 校验 | 满足 | G01 host 组（baseline :1109–1115 含 evil Host 下引导地址未被消耗）；白盒钉 hostAllowed 整串比对与端口自解 |
| D05 CSRF | 满足 | G01 csrf 组；候选 app.ts POST 分支 csrfCheck 三查（patch:199–206）+ routes.ts api.ping.post 只在通过后才 `posts.value += 1`（patch:1160–1167） |
| **D06 控制接口** | **不满足** | §1。候选 app.ts:199 的 `if (method === "POST") {` 对控制路由一并跑 csrfCheck + readJsonBody；门禁 Bun 1.4.2 进程内实测：不带正文→400、空/坏 JSON→400、不带 Content-Type→415、合法 JSON 对象→200（whitebox .log:545–556 与 gate report §4） |
| D07 恒定时间比较与限速 | 满足 | G01 control 组（baseline :1388–1420 含 5 次失败锁 1 秒、429 带 Retry-After、翻倍到 2 秒、成功清零、外来 Origin 不计数）；白盒钉 `CONTROL_MAX_FAILURES = 5`、锁定期内不比较、只看 X-Themis-Control 不看 cookie、`TOKEN_BYTES = 32` 与双摘要 timingSafeEqual |
| D08 日志无令牌 | 满足 | G01 logs 组；白盒钉每项只有 route/status/ms、`invalid-route-name`、entries() 给副本；候选 app.ts catch 只写 `error.name` 不写 message（patch:214）；静态错误只给类别文字（staticMessage，patch:129–136，不含 `${reason}`/路径回显） |
| D09 静态资源边界 | 满足 | G01 assets 组；白盒钉 14 类 reason 逐类、Content-Type 白名单、isWithin/重解析点/realpath 三道边界；V03 static-paths + fixtures/resolve-asset.ts |
| D10 只解码一次与 HTTP 负面 | 满足 | G01 assets 组的五条 HTTP 负面路径（baseline ASSUMPTIONS ④）；白盒钉预解码拒绝 `%2f`/`%5c`/`%2e`/`%00`、只解码一次、rawPathOf 不规范化 |
| D11 请求体上限 | 满足 | G01 body 组（413-chunked 样本）；白盒钉 `MAX_BODY_BYTES = 65536`、声明超限一个字节不读、流式超限 `reader.cancel()`、fatal UTF-8、空正文 400；server.ts `maxRequestBodySize: 131072`（patch:1250）作第二道防线 |
| D12 安全头 | 满足 | G01 headers 组（11 类样本）；白盒钉 CSP 逐字、nosniff、no-referrer、noStore/no-cache 二选一、删所有 `Access-Control-*`、正文仍走原流；withSecurityHeaders 在 respond() 里对所有出口统一加（patch:163–166） |
| D13 范围与已知限制 | 满足（成色见 §5.3） | 合同给 D13 的证据本就是「review、V03」；README 三种 Bun 响应不带安全头 + 理由 + 64 KiB 先停 + 131072（patch:34–49 一带）；「64 KiB 先于 Bun 上限触发」的行为面由 D11 的 G01 body 组与 V03 localhttp-body.test.ts 覆盖 |
| D14 参数与已有服务 | 满足 | G01 usage 组；候选 main.ts 只改 runUi 尾部（动态 import serveUi）与注释，checkArgs 三条提示原文未动（patch:1035–1067）；`ts/packages/ui/test/args.test.ts` 不在 changed_files 里（未改未删） |
| D15 生命周期与锁 | 满足 | G01 lifecycle/launcher 组；白盒钉 1800 秒缺省、MAX_SAFE_INTEGER 封顶、setTimeout 每段 2^31-1、hold/release、stdin EOF 不轮询 ppid、三信号、`LOCK_TAKEOVER_ATTEMPTS = 3`、owner.json 缺失 10 秒判据、pidAlive 三态、只删自己的锁、三条被占提示原文 |
| D16 只有 GET 与 POST | 满足 | G01 methods 组（405-put 样本）；白盒钉 methodAllowed 与 `Allow: GET, POST` |
| D17 门禁/范围/测试完整性 | 满足 | checks.json 九项全 passed（权威）；changes.json 与 summary.md：A31 M2 **D0 T0**、越界 0、警告 0；V07 的 must_not_match 未命中 → 改动只在 ts/packages/ui/ 下；M2 是 README.md 与 main.ts（都不是测试文件），既有测试**未删**（D0）、**未跳过**（候选测试里 grep 不到 `it.skip`/`describe.skip`/`xit(`）；V01 `bun install --frozen-lockfile` exit 0 且 summary「Checked 63 installs across 106 packages (no changes)」→ 依赖清单与锁文件未改 |

## 3. JEV 三条提示的核对结论

### 3.1「自述完成而无证据」p=0.90、置信 0.80 —— **部分成立，已并入 B3**
逐条核 dod[]：17 条 note 都点了 V03 的测试文件与 G01 的组名，且这些检查经内核自跑全 passed，所以**不是「零证据」**。真正的毛病在 D06 与 D13：
- **D06**：note 写「控制接口 403/200、换引导地址、旧会话 401、外来 Origin 不计限速；V03、G01 control」，**没有任何一处提到「200 需要合法 JSON 正文 + 全套 CSRF 头」这个附加前提**，也没把 contract_conflicts 与 D06 的 status 关联起来（明明报了矛盾却仍标 done、还写「无需标 blocked」）。这就是 JEV 抓到的那条：DoD 标 done，而支撑它的检查（G01 control 组）从未走过「只带对令牌」这条路。→ B3 要求如实改写。
- **D13**：note 只给「G01 readme 断言」，那是**文件内容**层面的证据；合同给 D13 的证据栏本就写「review、V03」，且「64 KiB 先停」的行为面在 D11 有 G01/V03 覆盖，所以不判缺证据，但 note 的写法容易让人误以为 README 那几条限制经行为验证过。→ 归入 B3 的如实性要求，不单列阻塞项。
- **D17**：证据充分（§2 表末），且以 checks.json 为准而非执行端自报的退出码。

### 3.2「误导程度」2.22/3、置信 0.41 —— **成立，具体就是这一句**
executor-report.json 的 contract_conflicts[0].reason：「门禁端 ASSUMPTIONS 已记明两种读法，且其控制请求带合法 JSON 正文与全套头，两种读法下都无害；相关 DoD（D06/D07）在候选上均通过，**无需标 blocked**」。
- 「两种读法下都无害」只对**门禁的探针**成立，对**真实外壳**不成立（§1.2）：把「现有检查测不出差别」当成「没有差别」，正是会改变结论而独立检查（G01 全绿）掩盖不掉的那类表述。
- 「D06 在候选上通过」也误导：G01 的 control 组带全套头与 `{}` 正文，恰好绕开了两种读法的分歧点，通过≠D06 达标。
- 配合 `limitations: []`（明明有一条仓库外事实未核实：外壳请求头）与 `unresolved_questions: []`，整体给人「无遗留」的印象。→ B3。
- 另：summary.md 记了 17 条命令退出码被管道掩盖、13 条 `rm -rf` 线索，我抽查了它们的上下文（都是 `T=$(mktemp -d)`/`./.smoke-t015` 临时目录与一次性探针 `.smoke-*-probe.ts` 的自清理，以及 `rm -f packages/ui/test/zz-debug.test.ts` 删自己的调试文件）；V07 与 checks.json 的 `unexpected_files_by_checks: []`、D0（删除 0 个文件）共同表明没有误删仓库内容。`.pytest_cache/` 等 6 条被忽略路径是工具产物，不在 V07 的范围内，也不影响 D17。

### 3.3「自行解读合同」p=0.57、置信 0.14 —— **7 条解读均不与合同明写相冲；有 1 条要改判**
1. `originAllowed`/`csrfCheck`/`controlOriginAllowed` 不接 port、端口从 Host 自解 —— 合同 v5.md:107 的签名就是这三个形状，**一致**。
2. 盘符只查第一段、冒号查任何段 —— 合同 v5.md（静态资源那条）原文即如此区分，**一致**；`a:b` 归 drive-letter 是合理次序。
3. 锁接管 3 次耗尽按「正在启动」报告 —— 合同 v5.md:137 只写「最多试 3 次」，D15 未涉及耗尽，**合同空白**，解读可接受（且这种情况只可能是双方抢同一把死锁）。
4. 握手行 `themis_ui` 取 1 —— 合同 v5.md:133 只规定字段与次序；docs:741 明写 `{"themis_ui": 1, …}`，**与上位设计一致**。
5. 静态 400/403/404 只给类别文字、不回显路径 —— 与「不回显原值」「stderr 不写 message」同源，**一致**。
6. IdleTimer hold/release 语义 —— 合同只列了三个方法名，**空白**，解读可接受。
7. 非 API 非控制路径的 POST 按静态资源处理 —— 合同管线第 3 步只把 `/api/` 与会话绑定，未禁静态路径的 POST，**不冲突**（副作用是 `POST /` 返回 index.html 200；无写入、无副作用，可接受，留作建议）。

**要改判的一条不在 interpretations 里，而在 contract_conflicts 里**：执行端对「管线第 4 步 vs 路由表」的取舍（对所有 POST 一律跑 csrfCheck + readJsonBody）与合同明写的「不读正文」相冲 → 阻塞项 B1。这也解释了 JEV 为什么给「自行解读合同」打到 0.57：执行端确实做了取舍，只是把它归到 conflicts 而非 interpretations。

## 4. 越界、弱化测试、硬编码与特判的独立核查
- **越界**：changed_files 33 条全在 `ts/packages/ui/{src,test,README.md}`；M2 是 README.md、main.ts；D0/T0；V07 must_not_match 未命中；checks.json 的 `candidate_files_modified: []`。**无越界**。
- **弱化测试**：删除 0 个文件；`args.test.ts` 未出现在 changed_files（D14 要求）；候选测试里 grep 不到 `it.skip`/`describe.skip`/`xit(`/`expect(true).toBe(true)`；G01 与 R01（549 passed）全绿 → 既有门禁未被削弱。
- **对测试输入硬编码 / 空 catch / 为过测试的特判**：src 里 grep 不到 `process.env`（只有 test/harness.ts 用 `THEMIS_PYTHON` 找解释器、并显式构造干净 env，属测试基础设施）；没有 `catch {}` 空处理（app.ts 的 catch 写 stderr 并回 500 信封，server.ts 的看门狗 `setTimeout(() => process.exit(exitCode), WATCHDOG_MS)` + unref 照合同 v5.md:135）；`staticMessage` 是 reason→类别的映射，不是针对某个测试样本的特判；`findRoute` 用 `[...ROUTES, ...extra]`，第 2/3 片的接缝照合同保留。**未发现为过测试而写的特判**。
- **范围悄悄扩大**：没有新增依赖（V01 frozen-lockfile 无变化）、没有新文件落在范围外、没有动内核禁区。

## 5. 门禁记录的成色

### 5.1 静态 vs 行为的分布（我的核算）
白盒 19 条**全部是静态文本断言**（门禁自报「不起服务、不装依赖」，模块级只 import `re` 与 `pathlib.Path`，一遍 0.09–0.10 秒——这个耗时本身就证明它没起过服务）。因此**74 条变异全部是被静态断言抓住的，行为层 0 条**。变异清单度量的是「白盒对文本改动的敏感度」，不是「行为覆盖」。
真正危险的行为面由两处覆盖，且都在仓库/内核侧可复现：
- **G01 的黑盒流水线**（内核自跑 passed）：会话 401/404、CSRF 403/403/415、Host 403、方法 405+Allow、413 分块、429+Retry-After+翻倍+清零、302+Set-Cookie 逐字、引导地址一次性、静态 200/404/400、11 类样本的安全头、握手五字段与次序、logs 无令牌、usage/lifecycle/launcher。
- **V03（112 条）与 V04（509 条）**（内核自跑 passed）。
白盒钉住的常量与形状（NONCE_TTL_MS=60000、MAX_BODY_BYTES=65536、CONTROL_MAX_FAILURES=5、TOKEN_BYTES=32、CSP 逐字、`themis_ui`/握手次序、`maxRequestBodySize: 131072`、管线七步的 order 断言、import 接线 8 条）与上述行为面**是对齐的**，会话、CSRF、限速、正文上限、握手字段与次序、bootstrap 一次性与 60 秒都被钉住了；bootstrap 的「一次性 + 60 秒」在文本层钉的是 `consume` 的「先无条件删再判 `< ttlMs`」这行代码形状，加上 G01 rejection 组的行为验证，两者合起来够。

### 5.2 变异清单可信度
- **锚点**：清单本身**没有存进 evidence**（该目录只有 whitebox-*.py 与 .log），所以 74 条的 `old`/`new` 原文无法逐条复核。我抽查了 7 个代表性锚点，在 candidate.patch 里各**恰好出现 1 次**（`MAX_BODY_BYTES = 65536`、`CONTROL_MAX_FAILURES = 5`、`NONCE_TTL_MS = 60000`、`TOKEN_BYTES = 32`、`LOCK_TAKEOVER_ATTEMPTS = 3`、`maxRequestBodySize: 131072`、`themis_ui: 1,`），与门禁「每条 old 恰好出现 1 次、且不跨行（不受 CRLF 影响）」的自述相符 → **锚点可信**。
- **`new` 是否真改坏行为**：报告 §3.5 列的 66 条取值/行为类描述（绑 0.0.0.0、stderr 回显 message、`ok: true` 的错误信封、nonce 可重复使用、TTL 边界改 `<=`、比较不走 timingSafeEqual、锁定期内照样比较、解码两次、isWithin 恒真……）逐条看都是**语义上确实变坏**的改动，不是同义改写；8 条接线类（改 import 路径、去掉 acquireUiLock、去掉汇总出口再导出）方向也对。但**「74/74 被抓」这个结论只有门禁自己跑过，内核因候选红而没跑**，evidence 里也没有逐条的运行日志 → 本轮**只能记为「自证、未经内核复核」**。
- **覆盖面**：18 个非测试文件每个 ≥1 条（static.ts 10、guards.ts 7、control.ts 6、server.ts 6、session.ts 6、body.ts 5……），满足任务书「每个非测试文件至少一条」。

### 5.3 白盒 18 绿 1 红、内核没跑变异检查——对结论的影响
1. **对本轮裁定没有影响**：缺陷成立与否由合同原文（v5.md:114/274）+ 门禁的 Bun 实测（400/415/200 四种组合）+ docs:404/741 的外壳事实决定，不依赖变异清单。
2. **对「实现的其余部分是否忠实」有影响，但可接受**：18 条绿只证明源码里存在合同要求的文本与次序，不证明运行期行为；运行期由内核自跑的 G01/R01/V03/V04 兜住（全 passed），所以其余 16 条 DoD 我判满足是有独立证据的，不是采信白盒。
3. **必须记的两个缺口（下一轮补）**：①74 条变异从未在**绿候选**上被内核跑过，「无漏网」这一说法本轮不可核实；②门禁的行为探针（Bun 进程内实测）**没有存档**——它恰恰是本次唯一发现真缺陷的手段，却不可复现。→ 见 §5.4。

### 5.4 给下一轮战后门禁的注意事项（本轮不作退回对象，不进阻塞项）
- **退役 `test_control_bootstrap_actual_wiring_pinned`**：它 `pin(APP_REL, '      let body: unknown;\n      if (method === "POST") {')`，钉的正是被判为错的接线；B1 一改必红，属预期，不要再报成 candidate_defect。
- **保留 `test_control_bootstrap_no_body_matches_contract` 作回归**：它的断言是形状/名字二选一（`guarded is not None or named_guard`），B1 建议的写法（分支条件加 `&& match.route.name !== "control.bootstrap"`）能让它转绿；但它是**文本形状**断言，绿了不等于行为对，下一轮应另加一条**行为**断言（起真进程或进程内调 `createApp().fetch`）覆盖「只带对令牌、无正文 → 200」，并把探针脚本与输出**存进 evidence**。
- **重新导出变异清单**：B1 会改动 app.ts 的分支条件文本，锚点落在该行上的条目需要重新取锚；清单本体请一并存进 evidence，好让内核真跑一遍变异检查。
- `test_transitional_localhttp_import_paths` 的过渡标记（迁移 ③d 之后退役）写清楚了，无异议。

## 6. 退回对象的理由
- **退回执行端**：缺陷是实现层与合同明写相冲（§1），改法明确、范围只在 `ts/packages/ui/src/app.ts` + 测试 + 执行报告，不需要改合同、不需要改基线门禁（G01 的控制组带全套头与 `{}` 正文，B1 之后仍应全绿）。
- **不退回合同端**：合同两处说法虽需澄清，但路由表 + D06 已经把结论定死（穷举门 + 「不读正文」+「对的令牌是 200」），不需要站主先改合同才能修实现。若站主要求控制接口也强制 CSRF 三头，那必须先核实外壳请求头（§1.2、需协调人决定 ①），届时才走合同端。
- **不退回门禁端（战前）**：基线 G01 按 ASSUMPTIONS ② 采取「两种读法都成立」的发法，是合理的保守设计，没有错；它测不出这处缺陷是合同歧义所致，不是门禁失职。
- **不退回战后门禁**：白盒把合同读法钉成一条红用例、把候选实际接线钉成一条绿用例、并把矛盾如实举证给终审，这正是任务书要的行为，成色合格（§5.3 的两个缺口记为下一轮注意事项）。
- **不退回规划端**：仓库外事实（外壳请求头未核实）已由站主记录 F9 在案，规划端已把它标为未核实，不构成规划缺陷。

## 7. 建议（不进阻塞项）
1. `POST /` 等静态路径返回 200 与文件内容，语义上略怪（POST 通常不该当 GET 用）；第 2/3 片加数据路由时可考虑对静态路径的非 GET 一律 405，但那要改合同，本轮不动。
2. README 的「已知限制」建议补一句「控制接口不要求正文与 CSRF 三头，只要求控制令牌 + 同源或缺 Origin」，免得第 2/3 片的实现者照管线第 4 步又把它加回去。
3. 第 2 片接 `extraRoutes` 时，`RouteInput.body` 对控制路由是 `undefined`；建议在第 2 片给 Route 加一个显式的 `readsBody` 标记，而不是靠路由名硬判——本次 B1 用路由名判是为了不动白盒 pin 的最小改法，长期看标记更干净。

Verdict: REVISE
