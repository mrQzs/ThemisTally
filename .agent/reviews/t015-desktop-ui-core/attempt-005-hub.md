# 复审记录：t015-desktop-ui-core attempt-005（七端信箱 hub）

- 合同：t015-desktop-ui-core.v6（base ad113e1b8193fbc5e3c74e0b6c89ec3dfb4672e0）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T015-7-audit-post 终审报告（第二轮，audit-sonnet）

## 0. 结论

**结论：通过。** 上一轮三条阻塞项 B1/B2/B3 全部落实，D01–D17 逐条满足，JEV 两条「需关注」经独立核对均不成立，战后门禁这一轮的成色可接受（162 条变异由内核真跑并全被抓住，两个 `unmutated` 夹具由 V03 覆盖，合同 Step 7 点名的 `resolve-asset.ts` 确实存在且被用）。未退回任何对象，无需站主追加预算，也无需先向站主核实 F9。

复审封板原则照办：本轮只对 B1/B2/B3、本轮新改动（5 个文件）以及会导致错误结果的严重问题下判断；上一轮的建议类意见（探针未存档等）本轮仍只作观察项，不升级为阻塞项。

## 1. B1 / B2 / B3 逐条复核

### B1（app.ts 管线第 4 步排除 control.bootstrap）——已解决
- 候选 `ts/packages/ui/src/app.ts` 第 4 步逐字是 `if (method === "POST" && match.route.name !== "control.bootstrap") {`，块内 `const rejection = csrfCheck(request);` 与 `const parsed = await readJsonBody(request);` 两行与上一轮一致、一字未动（candidate.patch 的 app.ts hunk 只有 3 行注释 + 1 行条件）。
- 我在 worktree 里读了 app.ts 全文复核次序：1 Host → 2 方法 → 3 `/api/` 会话 → `findRoute` → **`controlOriginAllowed`（在 POST 分支之前）** → 4 CSRF+正文（豁免控制）→ 5 处理函数 → 6 安全头 → 7 访问记录。外来 Origin 的 403 因此不进 ControlGate 的失败计数，与 D06「不计入限速」一致。
- `src/routes.ts` 的 `control.bootstrap` 处理函数只用 `state.control.check(input.request.headers)`，切片内不含 `input.body`；`sessions.revokeAll()` + `nonces.revokeAll()` + 新 nonce 的 200 信封照合同 v6.md:114。
- **豁免未外溢**：`/api/v1/ping` 的 POST 仍走 `csrfCheck`（403/403/415）与 `readJsonBody`（413/400），`guards.ts` 三查的取值与次序未改（门禁 W-G06/W-G07 变异均被抓住，即次序与取值都有 pin）。
- 没有为过测试开半吊子逻辑：不是「有正文才校验」，而是控制路由根本不进这两步；处理函数也不读正文，带了正文一样忽略（新增用例断言 `not json` / `""` / `[]` / `{"a":1}` 四种正文都 200）。
- 未采用「给 Route 加 readsBody 标记」的替代写法，白盒 `named_guard` 的形状耦合风险本轮不触发。

### B2（仓库内行为证据）——已解决，且证据由内核独立跑过
- `test/app.test.ts` 新增「控制接口不读正文：只带对令牌就 200，正文与 CSRF 头全都无关」：8 组请求头（只带令牌 / +同源 Origin / +X-Themis-UI / Content-Type 为 application/json、text/plain、application/jsonp / 只带 cookie / 全套）逐组断言 **200**（不是「不 400」）、`data.bootstrap` 匹配 `^/bootstrap/[A-Za-z0-9_-]{43}$`，并且**用新地址 GET 断言 302 与逐字 Set-Cookie**；再断言 4 种正文一律 200；令牌缺失/错/只带 cookie → 403；外来 Origin 连 6 次 403 后对的令牌仍 200；连续 5 次失败后对的令牌 429 且 `Retry-After ≥ 1`；末尾 4 条 API 断言（缺 X-Themis-UI 403、缺 Origin 403、text/plain 415、坏 JSON 400）。
- `test/service.test.ts` 新增「D06 控制接口不读正文：…豁免不外溢到 API」：走**真 Bun 服务**，7 组请求头用新 `requestNoBody`（连 Content-Length 都不带）+ 3 种正文用 `request`，同样断言 200/新地址可建会话/API 403·403·415/令牌门 403/外来 Origin 不计速/5 次失败 429 带 Retry-After。
- `test/harness.ts` 的改动是纯重构：`request` 现在转调 `send(..., declareLength=true)`，Content-Length 的注入条件与原来逐字相同，既有 chunked / 413 用例语义未变；新增 `requestNoBody` 只是 `declareLength=false`。
- **既有用例未删未跳未放宽**：candidate.patch 里 app.test.ts / service.test.ts 全是新增块，harness.ts 只有重构；无 `it.skip`/`xit`；`args.test.ts` 未改（V03 日志显示 3 tests 仍在）。G01 控制组仍绿（内核 `checks/01/G01.log` exit 0，27 passed）。
- **证据成色**：内核 `check --fresh` 独立跑了 V03（`vitest run packages/ui/test`）exit 0、`Test Files 13 passed / Tests 114 passed`，其中 app.test.ts 14 tests、service.test.ts 17 tests 全绿；V04（全量 vitest）exit 0、V05（tsc）exit 0。所以这些新断言**在核心里真跑过**，不是门禁端自证。门禁端因工作目录无 `ts/node_modules` 没跑 Vitest，但它的 Bun 进程内探针 49 项与仓库新用例一一对应，两条独立路径结论一致。

### B3（executor-report.json 如实改写）——已解决
- D06 的 note 写明了 B1 的具体条件改动、B2 的「只带对令牌（无正文、无 Content-Type、无 X-Themis-UI、无 Origin）即 200 且 data.bootstrap 能 302 建会话」，并点名两个新用例，另附令牌门/外来 Origin/429 三项。
- `contract_conflicts` 只剩一条，结论是「以路由表/D06 为准，管线第 4 步不适用于 control.bootstrap」，上一轮那句「两种读法下都无害、无需标 blocked」已删除，并如实标注该条来自终审阻塞项 B1。
- `limitations` 第一条逐字包含 F9 与「本实现按不依赖正文与 CSRF 头处理，外壳无论带不带正文都能 reauth」。

## 2. D01–D17 逐条结论（重新核，不只核 D06）

权威依据：内核 `checks/01/checks.json`（九项 exit_code 全 0、output_must_match 全 matched、V07 must_not_match 未命中、`modified_by_checks=false`、`candidate_files_modified=[]`、`tree_before==tree_after==630616e`）。执行端 self_checks 的 `reported_exit_code` 因管道掩盖不可信，本表一律以 checks.json 与源码为准。

| DoD | 结论 | 证据出处 |
| --- | --- | --- |
| D01 握手与绑定 | 满足（本轮未改相关文件） | V03 `service.test.ts` D01 用例（日志可见「D01 握手与绑定…」✓ 417ms）、`launcher.e2e.test.ts` ✓；`server.ts` 握手字段与次序有白盒 pin（W-SV09–W-SV13 变异全被抓住） |
| D02 会话与引导地址 | 满足 | V03（service/app/localhttp-session 全绿）；`session.ts` 常数与 302/404 逐字 pin（W-SS01–W-SS08 caught） |
| D03 一次性与 60 秒 | 满足 | V03 `service.test.ts` D03（serve-entry，TTL 1.5s）✓ 1788ms；`consume` 先查后删再判的次序 pin（W-SS02 交换次序被抓住） |
| D04 Host 校验 | 满足 | V03（localhttp-guards 8 tests）；`allowedHost` 两串 pin（W-G02 caught） |
| D05 CSRF | 满足，且本轮**加强** | 既有 V03 用例 + 新增 API 未外溢断言（app.test.ts / service.test.ts 各 4 条 / 3 条）；`csrfCheck` 三查取值与次序 pin（W-G06/W-G07 caught） |
| **D06 控制接口** | **满足**（本轮由缺→足） | 只带对令牌（无正文/无 Content-Type/无 X-Themis-UI/无 Origin）→ 200 且 `data.bootstrap` 为 43 位新地址、新地址 GET 302 带逐字 Set-Cookie：`app.test.ts` 新用例（V03 真跑）+ `service.test.ts` 新用例（真 Bun 服务）；令牌错/不带/只带 cookie → 403；外来 Origin → 403 且 6 次后对的令牌仍 200；5 次失败后对的令牌 → 429 带 `Retry-After`。源码依据 `app.ts` 第 4 步豁免 + `routes.ts:63-79` |
| D07 恒定时间比较与限速 | 满足 | V03 `localhttp-control.test.ts` 5 tests + 新用例又走一遍限速；`control.ts` 常数、`constantTimeEqual` 接线、锁判定先于令牌比较的次序 pin（W-CT01–W-CT08 caught，含 W-CT07 交换次序） |
| D08 日志无令牌 | 满足 | V03 `app.test.ts`「访问记录只有路由名…」+ `service.test.ts` D08；`accesslog.ts` 的 `ROUTE_NAME_RE` 与 `invalid-route-name` pin（W-AL01–W-AL05 caught） |
| D09 静态资源边界 | 满足，**含 Step 7 探针** | V03 `static-paths.test.ts` 20 tests ✓ 440ms，其中「GetFileAttributesW 认得 junction（探针在 Bun 里跑）」✓ 391ms 真起了 `test/fixtures/resolve-asset.ts`（我在 worktree 里核到该文件存在，且 `harness.ts:19` 导出 `RESOLVE_ASSET_PROBE`、`static-paths.test.ts:9,177,179` 使用）；`static.ts` 各类 reason pin（W-ST01–W-ST16 caught） |
| D10 只解码一次与 HTTP 负面 | 满足 | V03 static-paths + service 静态负面用例；`decodeURIComponent` 只调一次 pin（W-ST03 双解码被抓住）、NUL 与编码分隔符的拒绝次序（W-ST02 caught） |
| D11 请求体上限 | 满足 | V03 `localhttp-body.test.ts` 8 tests + service 用例；`MAX_BODY_BYTES=65536`、`>` 边界、fatal TextDecoder、`JSON.parse` pin（W-BD01–W-BD05 caught）；`server.ts` `maxRequestBodySize: 131072` pin（W-SV03 caught） |
| D12 安全头 | 满足 | V03 service 覆盖各状态码 + `localhttp-headers.test.ts` 4 tests；CSP 逐字、nosniff、no-referrer、no-store/no-cache、删 `Access-Control-*`、`new Response(response.body,…)` 不缓冲 pin（W-HD01–W-HD06 caught） |
| D13 范围与已知限制 | 满足 | README 已知限制段原样（白盒 pin「Bun 自己生成的三种响应**不带安全头**」「没有攻击者能控制的 HTML」「设成 131072（64 KiB 的两倍）作为第二道防线」「（64 KiB 加 1 就停）先于 Bun 的上限触发」）；本轮另补三处豁免说明，pin 随之更新（W-RM01–W-RM04 caught）。合同 D13 的证据本就是「review、V03」，README 文本 pin + 人工 review 是合规证据，不是空心断言 |
| D14 参数与已有服务 | 满足 | V03 `args.test.ts` 3 tests（既有用例未改未删）、`lifecycle.test.ts`、`service.test.ts` D14 ✓、`launcher.e2e.test.ts` ✓；`main.ts` 退出码与三条提示原文 pin（W-MN01–W-MN09 caught） |
| D15 生命周期与锁 | 满足 | V03 `lifecycle.test.ts` 11 tests、`lockdir.test.ts` 8 tests、service D15 两条 ✓、launcher.e2e ✓；`lockdir.ts`/`lifecycle.ts` 常数、接管规则、`idleMs` 封顶、不轮询 ppid pin（W-LK01–W-LK11、W-LC01–W-LC11 caught） |
| D16 只有 GET 与 POST | 满足 | V03 service 用例；`methodAllowed` pin（W-G01 加 HEAD 被抓住）、`Allow: GET, POST` pin（W-A07 caught） |
| D17 门禁/范围/测试完整性 | 满足 | 内核 checks.json：G01 27 passed、R01 exit 0（549 passed，落地预演 576 passed）、V01–V07 全 exit 0；V07 输出只有 5 个 `ts/packages/ui/` 路径，must_not_match 未命中 → 范围违规 0；`bun install --frozen-lockfile` exit 0 且 `changed_files` 无 package.json/锁文件 → 依赖与锁文件未改；candidate.patch 全为新增/重构，无删除、无 skip |

## 3. JEV 两条「需关注」的核对结论

### ①「自述完成而无证据」p=0.86（置信 0.72）——**本轮不成立**
逐条核 executor-report.json 的 17 条 DoD：每条都落在 `self_checks` 里的一项具名检查上（G01/R01/V01–V07，含命令与结果摘要），而这些检查**由内核在 `check --fresh` 里独立重跑并全部 exit 0**（checks.json 为权威）。
- **D06**：note 现在有 B3 要求的两个用例名与「只带对令牌即 200」的明确结论，用例在 V03 里真跑过（114 passed 含 service.test.ts 17 tests）→ 有证据。
- **D13**：证据是 README 文本 + review，这是合同 D13 自己规定的证据形式（「证据：review、V03」）；且 README 那几段有 4 条变异 pin 兜底 → 不算「无证据」。
- **D17**：note 列了 G01/R01/V01–V07 全过、范围、依赖与锁文件未改、未删未跳未弱化，逐条都能在 checks.json（V07 输出、V01 frozen-lockfile）与 candidate.patch（纯新增）里独立验到 → 有证据。
- D01–D05、D07–D12、D14–D16 的 note 是「未改；V03 通过」，本轮候选确实只改了 app.ts 管线的一个分支条件与三个测试文件 + README，未触碰这些 DoD 的实现文件；V03/V04 全量绿 → 判为有证据（引用具名检查即证据，不要求每条 DoD 单独贴输出）。

### ②「误导程度」2.10/3（置信 0.32）——**本轮不成立**
上一轮成立的两处（D06 note 隐去附加前提、`contract_conflicts` 的「两种读法下都无害」+ `limitations:[]`）都已按 B3 改掉。逐句复核剩下的表述：
- `limitations` 现在是两条，第一条如实写 F9 未核实 + 本实现的取舍；第二条「README 已随 B1 补写…除此之外本轮未扩大改动」与 candidate.patch（5 个文件、181 insertions / 8 deletions，全部在 B1/B2/B3 要求范围内）一致。
- 唯一措辞瑕疵：D13 的 note 以「未改」开头，随后又写「另补两句与控制接口豁免相关的描述」。README 本轮确实被改（3 个 hunk），但同一条 note 里已披露改动内容，且 `changed_files` 里 README 在列、V07 也列了它 → 不构成「独立检查揭示不了、且会改变结论」的陈述。属观察项，不进阻塞项。
- 与独立检查的其他比对：changed_files 与 V07 输出、candidate.stat.txt 完全一致（5 M / 0 A / 0 D / 0 T，越界 0）；无 `process.env`、无空 catch、无对测试输入硬编码、无「为过测试而写的特判」（豁免是按合同路由表的专条，不是绕开某条断言）。

### ③「自行解读合同」p=0.27（置信 0.46）——两条新解读均不与合同明写相冲
- 「不带正文」的两种形态（连 Content-Length 都不带的 POST；`Content-Length: 0` 且无 Content-Type）：合同只写「不读正文」，没规定客户端形态；两种都覆盖是**从严**，且 `harness.ts` 的 `requestNoBody` 未改 `request` 的既有语义（我逐字核过 `send` 的 Content-Length 注入条件）→ 成立。
- 「只带 cookie」用刚拿到的新会话 cookie：D06 要求「只带 cookie 都是 403」，用**有效**会话 cookie 比用已作废的 nonce 更强（证明门从不看 cookie，符合 v6.md:106「只用 `constantTimeEqual` 比较 `X-Themis-Control` 头（从不看 cookie）」）；reason 里说明握手 nonce 已被前面的成功调用 `revokeAll` 作废，属实（`routes.ts:76-78`）→ 成立。
- 上一轮那 7 条解读本轮未变，仍不与合同明写相冲。

## 4. 门禁成色

### 4.1 162 条变异是否掩盖了问题
- **是内核真跑的，不是门禁自证**：`evidence/mutate-20261023T225603447429Z/mutations.json` 的 `tree` 就是本候选 worktree，`command` 为 `python -m pytest tests/test_gate_t015_whitebox.py -q`，baseline exit 0（0.25s），`counts` = caught 162 / missed 0 / skipped 0 / error 0，`not_run` 为空，`files_left_modified` 为空（变异后现场已还原）。每条结果里 `count_expected: 1` 且 `count_found: 1` → **`old` 在候选里逐字唯一**，锚点可信。这是上一轮我提的「清单未存档、74/74 只是自证」的实质修复。
- **接线类 30 条不是重复也不是纯形式化**：去掉 import 15 条各打不同文件/不同符号（W-A15/16/17/18、W-RT11、W-SS08、W-TK04、W-CT08、W-ST16、W-LK11、W-LC10、W-MN09、W-SV20/21/22），去掉 `localhttp/index.ts` 再导出 6 条各打不同的导出块/符号（W-IX01–W-IX06，其中 W-IX04/W-IX05/W-IX06 精确到 `controlOriginAllowed`、`ControlGate`、`BootstrapNonces` 三个符号），交换次序 4 条打的是真有安全含义的次序（W-G06 csrfCheck 三查 415 提前、W-CT07 锁判定移到令牌比较之后、W-SS02 nonce 先删后查、W-ST02 NUL 与编码分隔符拒绝顺序），W-LC11 引入 `process.ppid`。无两条打在同一个 `old` 上。
  - 观察项（不阻塞）：去掉 import 那 15 条有一部分是「形状类」——真发生时 tsc（V05）也会红，白盒抓住它更多证明 pin 完整而非行为正确；W-LC11 是 insertion-only（内核 `warnings` 已标出），被抓只说明白盒有「不得出现 `process.ppid`」的静态禁令，这与合同「不轮询 ppid」一致，可接受。
- **行为面钉得够不够**：白盒本体仍以静态 pin + order 为主（19 条 0.25s，未起服务），但**这一轮危险行为面的证据不再只靠白盒**：会话、CSRF、限速、请求体上限、握手字段与次序、bootstrap 一次性与 60 秒、以及本轮新增的「控制接口不读正文 + 豁免不外溢」都由**留在仓库里的 Vitest 用例**（V03 114 tests、V04 511 tests，内核独立跑过 exit 0）与**黑盒门禁 G01 27 passed** 覆盖；门禁端另用 Bun 进程内探针实测 49 项作交叉验证。三者结论一致，行为面不是空白。
  - 观察项（上一轮已提，本轮仍不升级为阻塞）：门禁端那 49 项探针只写进了白盒 docstring，脚本与输出未作为独立文件存档，事后不可复现；但同等断言现已固化进 `app.test.ts`/`service.test.ts` 并由 V03 常态跑，可复现性由仓库测试提供，缺口的实际影响已消失。

### 4.2 两个 `unmutated` 夹具
- `ts/packages/ui/test/fixtures/serve-entry.ts`：被 `harness.ts:17` 导出为 `SERVE_ENTRY`、`harness.ts:156` 在 `entry: "serve-entry"` 时用作启动入口，`service.test.ts:500`（D03 TTL 1.5s 用例）真起它 → 由 V03 覆盖，内核跑过。
- `ts/packages/ui/test/fixtures/resolve-asset.ts`：**文件确实存在**（我在 worktree 里读了全文：`bun resolve-asset.ts <root> <pathname>`，打印 `resolveAsset` 的 JSON），被 `harness.ts:19` 导出为 `RESOLVE_ASSET_PROBE`，`static-paths.test.ts:9` 导入、`:177`/`:179` 用 `execFileSync(bunPath(), [RESOLVE_ASSET_PROBE, …])` 断言 junction → `{ok:false,status:403,reason:"reparse-point"}`、正常资源 → ok。V03 日志里「GetFileAttributesW 认得 junction（探针在 Bun 里跑）」✓ 391ms 就是它真跑了的证据。
- 结论：两个夹具**都被独立检查（V03，内核跑过）覆盖**，门禁端「静态白盒覆盖不到故不变异」的理由成立且不构成缺口。合同 Step 7 点名的探针没有缺席——执行端 attempt-002 说的「没建」在当前候选里已不成立（D09 的 junction 行为由 `static-paths.test.ts` 的 Node 侧 `resolveAsset`/`isReparsePoint` 用例 + Bun 侧探针两路覆盖）。

### 4.3 上一轮留给门禁端的两条待裁定
- **「变异条数是否偏多」**：162 条不掩盖问题。判据是每条 `old` 在候选里唯一（内核逐条核到 `count_found: 1`）、每条真被套用并真跑白盒（162 条 exit_code 全为 1）、`files_left_modified` 为空、无 `equivalent` 声明（也就没有「声明等价故不测」的逃避口）。条数多只是覆盖密，反而让「哪一行改动没被测到」的空间变小。可接受。
- **`themis_ui` 取值**：本轮**不是**「只 pin 不变异」——W-SV09 就是 `themis_ui: 1` → `themis_ui: 2`，状态 caught。取值本身合同未规定，但 `docs:741` 与外壳约定用 1，pin 住 1 并变异它，是合适的处理，不构成覆盖缺口。

## 5. F9（真实外壳请求头未核实）的取舍是否站得住

**站得住，且不必在结项前先向站主核实。** 理由：
1. 上一轮的缺陷本质是「实现依赖了一组未经核实的外壳请求头（正文、Content-Type、X-Themis-UI）」，一旦外壳不带就 reauth 失败。本轮改成**不依赖**这些头：`control.bootstrap` 的门是穷举三道（Host、`controlOriginAllowed`、ControlGate），外壳带不带正文/Content-Type/X-Themis-UI 都 200。不确定性被设计消掉了，而不是被假设掩盖。
2. 安全没有弱化：仍是 32 字节随机令牌（`TOKEN_BYTES = 32`，base64url 43 字符）+ `timingSafeEqual` 恒定时间比较 + 从不看 cookie + `controlOriginAllowed`（外来 Origin 403 且不计入限速，网页无法把外壳锁死）+ ControlGate（5 次失败锁 1s、翻倍、60s 封顶、锁定期对的令牌 429）。CSRF 三查对 API 写路由（`POST /api/v1/ping`）一字未减。
3. 文档如实：README 三处写明豁免范围与理由（F9 未核实），executor-report `limitations` 第一条同样写明。第 2、3 片不会误读。
4. 残余风险与归属：F9 只影响 D3（Electron 外壳片）自己发请求时要不要带 `X-Themis-Control`（这一条是确定的，令牌来自握手行）；到那一片落地时再核实即可，不影响本片结项。

## 6. 独立复核过的「隐性作弊」面

- 对测试输入硬编码：无（新用例的令牌用 `"t".repeat(43)` / `running.handshake.control`，断言的是状态码与形状，不是把期望值抄进实现）。
- 空的异常处理 / 吞错：`app.ts` 的 catch 仍写 stderr 并回 500 信封，未改；候选无新增 try/catch。
- 为过测试而写的特判：豁免条件是合同路由表的专条落地，不是「if 测试环境 then …」；`src` 里无 `process.env`。
- 悄悄扩大的范围：`scope.json` 越界 0，V07 只列 5 个 `ts/packages/ui/` 路径，A0 M5 D0 T0；`package.json`/锁文件未改（V01 `--frozen-lockfile` exit 0）。
- 弱化测试：无删除、无 skip、`args.test.ts` 三条既有用例未动；G01/R01/V02/V03/V04/V05/V06 全绿。
- summary.md 提到的「可疑命令」`cd ts && bun install --frozen-lockfile`：这是 V01 的原命令，`--frozen-lockfile` 不改锁文件，checks.json 的 `modified_by_checks=false` 与 `unexpected_files_by_checks=[]` 佐证现场未被改。

## 7. 观察项（建议，不进阻塞项）

1. 门禁端把 Bun 进程内探针脚本与输出作为独立文件存进 evidence（本轮只写在白盒 docstring 里）。同等断言已进仓库测试，影响已很小。
2. 白盒 `named_guard` 只认三种文本形状（`match.route.name !== "control.bootstrap"` / `routeName !== …` / `== …`）。若第 2、3 片改成「Route 上加 `readsBody` 标记」这类等价写法，这条会红——届时属白盒形状耦合，应改断言而非改实现。
3. executor-report.json 的 D13 note 以「未改」开头但同一句里写了「另补两句」，措辞自相矛盾；建议以后直接写「README 已知限制段未改，另补三处豁免说明」。
4. 控制路由现在不消费请求正文。真服务用例（`service.test.ts` 带 `{"a":1}` 正文的 200）已通过，Bun 侧无残留问题；若第 3 片引入 keep-alive 复用连接，建议顺手确认未读的正文不会影响下一条请求（当前测试全用 `Connection: close`）。

Verdict: PASS
