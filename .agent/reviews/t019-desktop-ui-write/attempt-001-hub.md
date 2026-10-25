# 复审记录：t019-desktop-ui-write attempt-001（七端信箱 hub）

- 合同：t019-desktop-ui-write.v2（base 7a5aaf42eff61b0a84a2e0fe33f297b3ba3092b8）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261025T223017790845Z-722f），终审报告如下

## 终审报告

# T019-7-audit-post 终审（第 5 片：写配置的预览、确认号与操作终态）

结论：**通过**。候选树 `03d6389f`（base `7a5aaf42`），13 个文件（7 个非测试 + 6 个测试），全部落在 `ts/packages/ui/`。

## 1. 审阅次序

按岗位说明：先读候选源码（不是先看绿记录），再核对内核的 check 记录、战后门禁的白盒与变异记录，最后逐条对 DoD。

读过的源码：`writeroutes.ts`（全文）、`confirmations.ts`（全文）、`operations.ts`（全文）、`kernelenvelope.ts`（全文）、`redaction.ts`（全文）、`server.ts`（接线与空闲判定相关段）、`candidate.patch` 的 README 与 server/kernelenvelope/redaction 差异；测试侧读了 `write-routes.test.ts`（全文）、`fake-write-kernel.mjs`（全文）、`write-argv.test.ts`（W1–W3 与 W2 的枚举程序）、`confirmations.test.ts`/`operations.test.ts`（用例名）、`write-real.test.ts`（结构与真内核入口）。

## 2. 实现是否忠实于合同（逐条对 §1–§9）

| 合同条款 | 实现 | 判定 |
|---|---|---|
| §1 七个 action 与取值要求 | `WRITE_ACTIONS` 七个键与必填/可选逐条对上；`validValue` 里 role/target/host/cadence_seconds（整数、60–86400，布尔与小数被 `typeof`+`Number.isInteger` 挡掉）/name/description（1–200 码点、无 C0/DEL/孤立代理）/roles（非空、互不相同、都在 ROLES）/force（只 `true`）/number（1–999999999）/id（PLUGIN_ID_RE）/allow_permission（数组、互不相同、每项 1–256 码点）都按表实现 | 忠实 |
| §1 五类 400、提示固定不回显 | `validateWriteArgs` 五类分支与提示原文逐字一致；`${key} 不合法` 里的 key 只可能来自 spec 的 required/optional（未知键在此之前已被拒），**不回显用户输入**；不合格路径全部在 `runner.run` 之前 return | 忠实 |
| §1 基础 argv 与四个开关 | `buildWriteArgv` 与表格逐条一致，选项一律 `--opt=值`，`--force` 是不取值开关；函数体内没有那四个开关（W3 也钉住） | 忠实 |
| §1 T020 只登记不实现 | `T020_WRITE_COMMANDS` 恰好五条命令路径；五个 action 名不在 `WRITE_ACTIONS`，请求它们走 `spec === undefined` → 400「action 不合法」 | 忠实 |
| §2 预览 | 基础 argv + `--dry-run --json`；`PREVIEW_TIMEOUT = 30`，覆盖键 `api.preview`；用 `input.request.signal`；不拿锁；`checkPreview` 核 `dry_run===true`、`action` 相同、`state` 过 STATE_RE、`needs_yes` 是布尔，任一不满足 → 500「内核的预览不合格」且在 `issue` 之前 return（不发号） | 忠实 |
| §2 成功信封 | `dropState` 拿掉顶层 `state`，再过 `redactJson(…, PREVIEW_ALLOW)`；`data` 是 `{preview, confirmation}` 两键的 Map；走 `envelopeStatusResponse`，仍是七字段 | 忠实 |
| §2 退出非 0 | 走 `completedResponse({json:true})`：200、`ok` 假、stdout 不合法时 data 为 null、messages 带 ERROR；`issue` 没被调用，两表不变（S11 断言 size 都是 0） | 忠实 |
| §2.1 变换期望 | `PREVIEW_ALLOW` 16 条与表格逐条对上；`allowPreviewName` 放行 null、1–128 码点 `A-Za-z0-9._:/-`、`tokenShaped` 为假；`allowPreviewText` 是 `redactSecrets(v)===v`；S14 的 10 条断言与 §2.1 表格逐格一致（含 `before.profile` 为 `null` 而不是 `<redacted>`、`api_key`/`notes[1]`/`binding_changes[1].after.profile` 恰为 `<redacted>`），另加令牌原文全文搜索与 43 位确认号 | 忠实 |
| §3 unreadable/mode 不进白名单 | 白名单里没有 `unreadable`、没有 `mode`；`adapter` 进白名单（见 §6 裁定） | 忠实 |
| §4 确认号 | TTL 60_000（`expired` 用 `> ttlMs`，正好 60 秒仍有效）、容量 100、`randomBytes(32).toString("base64url")`；`makeRoom` 先清全部过期、再挤 `issued_ms` 最小的未用号；记录绑 `{action, argv, state, needsYes, issued_ms}`，不绑会话；`now` 可注入，生产路径不设；`ServeOverrides.confirmationTtlMs` 只给测试入口，server.ts 里没有 TTL 数字字面量 | 忠实 |
| §4 核对次序 | `executeWrite`：校验(400) → confirmation 形状/在表(409) → `argvMatches`(409，**不**消耗) → `canAccept()`(503+retry-after，**不**消耗) → `operations.create`(null → 503，**不**消耗) → `confirmations.consume` → `runner.run`。canAccept 到 run 之间没有 `await`，S5 的并发原子性成立 | 忠实（§6 括注的次序也对：先探操作表容量再消耗号） |
| §5 八条路由 | 路由名、方法、路径、路径参数与表格逐条一致；`rollbackArgs` 先过 `HISTORY_N_RE` 再转整数，不合格给 NaN 走 400；`mergeArgs` 去掉 `confirmation`、路径参数压正文 | 忠实 |
| §5 执行 argv | `[...argv, "--expect-state=<state>", ...(needsYes?["--yes"]:[])]`，不带 `--json`；plugins 无特例（needs_yes 恒假）；`WRITE_TIMEOUT = 90`，七条共用键 `api.write` | 忠实 |
| §5 私有信号 | `runWrite` 自建 `new AbortController()` 且从不 abort，`request.signal` 只出现在预览那一处；`op.run` 挂在记录上，处理函数 await 它再回响应 | 忠实 |
| §5 结果映射表 | 退出 0→succeeded/200；4→stale/409（`envelopeStatusResponse(envelope,409)`，是七字段信封不是 errorResponse）；其他非 0→failed(exit)/200；timeout→timed_out/504（`timeoutEnvelope`）；spawn-error→failed(spawn-error)/500；output-too-large→failed(output-too-large)/500；其余→failed(closing)/503。服务侧信封 `ok:false、exitCode:null、data:null、output:[]`、一行 ERROR | 忠实 |
| §5 信封内容 | `writeEnvelope`：data 恒 null、`outputOf(stdout)` 非空行逐行 `redactSecrets`、`messagesOf(stderr)`、`displayArgv(实际 argv)`、exit_code 原样、elapsed_ms = wall×1000 取整 | 忠实 |
| §6 操作记录 | MAX 100；`markRunning`/`settle` 各自只走一次；reason 四种；`evictOldestTerminal` 按 `finished_ms` 最小淘汰，无可淘汰回 null → 503（`operationFull` 带 retry-after:2）；`operationView` 恰好八键；GET 正文就是它、不套信封不套 data；格式不对与查不到同一个 404「没有这个操作」 | 忠实 |
| §7 信封 output 与占位 | `KernelEnvelope.output?`，`envelopeBody` 把 `output` 写在第四位、缺省 `[]`（读路由逐字节不变，`kernel-real.test.ts` 继续过 → R01/V04 绿）；`displayArgv` 加 `--expect-state=` → `--expect-state=<state>`，之后每项仍过 `redactSecrets` | 忠实 |
| §8 接线 | 建两表；`writeRoutes` 进第四批 `extraRoutes`；`readRoutes`/`eventRoutes`/`jobRoutes` 三记号与 IdleTimer 位置未动（V06 静态钉子 49 passed）；空闲判定加 `operations.active() > 0`；`ServeOverrides.confirmationTtlMs` 已加；关停仍先 `hub.close()` 再 `runner.shutdown()`；新 src 文件里没有 `<task>/` 字面量 | 忠实 |
| §9 兼容性 | 19 条读路由、`READ_ROUTE_SPECS`/`READ_ROUTE_ARGV`、`cursors.ts`、`readroutes.ts`、`localhttp/**`、`package.json`、`bun.lock` 一字未改（V07 只出现 `ts/packages/ui/`，R01 640 passed，V06 49 passed） | 忠实 |

## 3. 有没有「为过测试而写的特判」或悄悄扩大的范围

- 新 src 文件 grep `FAKE|process.env|NODE_ENV|if (false)`：只有既有的 `kernelenv.ts` 命中（本片未改），新增三个源文件里没有任何测试专用分支、没有读环境变量、没有对特定输入硬编码的旁路。
- 没有空的 catch：`writeroutes.ts`/`operations.ts`/`confirmations.ts` 里唯一的 try 是 `parseJsonData`（既有函数，返回 undefined 由调用方判 500）。`operations.ts` 的 `envelopeRecord` 用 `JSON.parse(envelopeBody(...))`，信封正文由本包自己拼，不是外部输入。
- 范围：`candidate.stat.txt`/`changes.json` 与 summary 的 13 个文件一致，越界 0、警告 0；`.pytest_cache/`、`desktop/web/dist`、`node_modules` 是被忽略的产物，白盒 `test_candidate_tree_scope_and_artifacts` 已核 git 索引里没有它们。
- 替身是否诚实：`fake-write-kernel.mjs` 的 `DEFAULT_PREVIEW` 与合同 §2.1 的 JSON 逐键一致（含令牌原文与 64 个 0 的 state），四支计划（ok/stale/audit-fail/pause）各自按退出码与 stdout/stderr 行事，报告记 begin/end 与 `expect_state`——不是「测试要什么就回什么」的回声装置。S14 的期望值全部来自合同表格而不是从实现反推。
- 用例是否弱化：ui 测试目录 grep `.skip(`/`.only(`/`.todo(`/`xit(` → 0 命中；`write-real.test.ts` 真跑（V02 里 5 tests 14093ms），用 `THEMIS_PYTHON ?? "python"` 起真内核，白盒 `test_write_real_no_masking` 另核它没有 catch 吞失败。

## 4. 内核的 check 与门禁记录

- `checks/01/checks.json`：11 条全 passed；`tree_before == tree_after == 03d6389f`，`modified_by_checks=false`，`candidate_files_modified=[]`，`unexpected_files_by_checks=[]`，`covers_all_required=true`。V07 的 `output_must_not_match`（非 `ts/packages/ui/` 的行）`matched=false`，即范围断言真的生效了。
- summary 提到「19 条命令的退出码被管道掩盖」——那是执行器自述阶段的探索命令；最终判定用的是 check 独立实跑的 `exit_code`（checks.json 里逐条有 `exit_code: 0` 与 `log_sha256`），不受影响。
- summary 列的 7 条「可疑命令（递归或强制删除）」逐条看原文：都是 `T=$(mktemp -d) … && rm -rf "$T"` 的自清临时目录，符合 AGENTS.md 给执行器的写法，删的是自己刚建的目录，没有碰主工作区或既有内容。
- 变异：`mutations.json` baseline passed、caught 26 / missed 0 / skipped 0 / errored 0；全文 grep `equivalent|expect_missed|noop|anchor` → 0 命中，即门禁这一轮**没有声明任何等价变异、也没有说哪个改动文件没法变异**。对照 mutation-spec 的 file 字段，7 个非测试改动文件（confirmations.ts、writeroutes.ts、operations.ts、kernelenvelope.ts、server.ts、redaction.ts、README.md）都被覆盖，无 unmutated——所以「逐条判断声明等价是否真的测不出来」与「逐条判断没法变异的改动是否真的不用测」这两项本轮无对象。
- 变异内容含接线类（M18 空闲接线、M24 去 import）与取值类，抓手与合同 v2 的 23 条对应关系（S14 抓 22/23、S15+R1 抓 7）没有变。M18/M26 只被门禁静态测试抓（vitest 抓不到）是预期，聚合命令已把两者并进同一判定——判定语义我核过：单命令清单下顶层 status 就是唯一判定，26 caught / 0 missed 在任何读法下都成立。
- 白盒：11 passed，覆盖协调人点名的 10 处（S6 两号语义、needsYes 命名一致性、预览 output 为空而写命令 output 非空、R3 的配置比对范围、路径参数压正文、adapter 白名单、write-real 无掩盖、T020 登记不实现、候选树范围与产物、先探操作表再消耗号、写运行私有信号），无 candidate_defects 需要我裁定。

## 5. JEV 的两处「需关注」

- **自述完成而无证据 p=0.87**：不成立。19 条 DoD 每条都引用了 checks.json 里真实存在的检查 id，11 条检查都有独立实跑的退出码、日志字节数与 sha256；V02/V04 的用例数（282/689）与日志一致，write-real 的 5 条真内核用例在日志里逐条列出。执行报告没有「declared done with no supporting evidence」的项。
- **自行解读合同 p=0.43**：执行端确实自行解读了 6 处（1 个 conflict + 5 个 interpretations），但**全部写在报告的 contract_conflicts / interpretations 里**，且我逐条核过都站得住（详见信里的「偏离」栏）。这属于「留了记录的合理取舍」，不是「暗中选一种读法」。

## 6. adapter 进 PREVIEW_ALLOW 的裁定（执行端报的唯一合同矛盾）

合同 §3 表格把 `binding_changes.*.before|after.adapter` 列进 `allowPreviewName`，同节文字又说「`role`/`mode`/`adapter` 这类枚举值不进白名单」。执行端采用**进白名单**，理由：门禁 `test_static_redaction_preview_allow` 的 `BINDING_FIELDS` 要求 `"adapter"` 出现在 `PREVIEW_ALLOW` 块里。我同意这个裁定，且它没有安全后果：`adapter` 的合法取值只有 `claude-code`/`codex`/null，走白名单（`allowPreviewName` 通过、原样）与走 `redactSecrets`（非凭据形状、原样）结果相同；非法/凭据形状的值两条路都会被遮成 `<redacted>`（`tokenShaped` 挡住）。§2.1 的十格期望在两种读法下都不变，S14 的断言也就无法区分——这正是「矛盾不影响可观察行为」的情形，不必退回合同端。建议下一版合同把 §3 那句文字里的 `adapter` 删掉，与表格统一（不挡本轮）。

## 7. 不挡的意见（不影响本轮结论，后续片可酌情处理）

1. **`writeRoutes` 的实参形状**：实现是 `writeRoutes({runner, confirmations, operations}, timeouts)`，合同 §8 的示意是四个位置参数。接线位置、第四批 `extraRoutes`、三记号与 IdleTimer 都对，功能无差别；只是与合同字面不同。已与 `ReadRoutesState` 的既有写法对称，我倾向保留现状。
2. **预览正文的未知顶层键被忽略**：§2 说「正文恰好两个键」，实现只读 `action`/`args`，多出来的键不拒（写路由那侧因为要合成 args，未知键会被 400 拒）。没有安全后果（未知键进不了 argv、也进不了内核），但严格读法下是个宽松点。T020 若要在预览侧也拒未知顶层键，加一行即可。
3. **`runWrite` 的兜底 else 把三种出口都记 `closing`**：`interrupted`（服务关停）与 `closing` 记 closing 是对的；`queue-full` 理论上也落这里，会记成「服务正在关闭」而其实没关停。实际到不了——`canAccept()` 与 `runner.run` 之间没有 `await`，且合同的四种 reason 里本来就没有 queue-full。若以后在这两步之间插入 `await`，这里会变成误记，值得留一行注释或单独分支。
4. **`runner.run` 若 reject，操作会永远停在 queued**：`KernelRunner.start()` 内部 try/catch 已把 spawn 异常转成 `spawn-error` outcome，`entry.resolve` 也总会被交代，所以 reject 实际到不了；但万一发生，`executeWrite` 的 `await op.run` 会抛出（app 管线回 500），而该记录不会 settle，`active()` 永远 > 0，服务从此不再空闲退出。要说触发路径只能是 runner 内部逻辑改动，概率极低，加防护要在 `runWrite` 外面包一层 try/catch 并 settle 成 failed（约 5 行）。**由站主决定做不做**，本轮不挡。
5. **README 的两段是扩写而非逐字保留**：D16 说「既有的段落逐字保留」，但「状态码」段必须补上新增的两种 409、「已知限制」里「本片不做预览、写路由」那句已过时（一审已指出）。执行端的处理是最小扩写：原文一字不删、只在句中插入新分句，另起「## 写操作」一节。我认为符合 D16 的目的（界面前端拿这份 README 能接上），不算违反。
6. **只有静态/白盒证明的两处，我已人工审阅**（一审留下的终审作业）：D08 的 spawn-error 与 output-too-large → `runWrite` 两个分支各自 `serviceErrorEnvelope` + settle(failed, 对应 reason) + 500，与合同表格一致；D13 的空闲行为面 → `server.ts:160` 的四个条件里 `operations.active() > 0` 在位，`active()` 数的是非终态记录（O4 钉住），写请求期间 `inflight` 也 > 0，两层保护都在。

## 8. 结论

实现忠实于合同 v2，没有越界、没有弱化测试、没有对测试输入硬编码或为过测试写特判；11 条检查独立实跑全绿且候选树未被检查改动；26 条变异全抓住、无声明等价、无 unmutated 文件；白盒 11 条全过、无候选缺陷需要裁定；JEV 的两处「需关注」经核实都不成立。

**结论：通过。**

Verdict: PASS
