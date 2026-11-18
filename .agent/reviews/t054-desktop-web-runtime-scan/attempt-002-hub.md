# 复审记录：t054-desktop-web-runtime-scan attempt-002（七端信箱 hub）

- 合同：t054-desktop-web-runtime-scan.v3（base ae9e6525cd968a2655bc616ddfad3b110ebff53a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261118T205201735762Z-49d1），终审报告如下

## 终审报告

# T054-7 终审报告（audit-sonnet）

**结论：通过。无阻塞项。**

## 一、材料与候选的实际形态

- 合同：`.agent/plans/t054-desktop-web-runtime-scan.v3.md` + 同名 `.json`（DoD 口径与 v2 逐字相同，只是 plan_version 变成 3）。
- 候选：`attempt-002/candidate.patch` 是 0 字节、`changes.json` 是 `[]`——基线 `ae9e6525` 里已经含 attempt-001 的全部改动（门禁端热修补 `7d61afb0` 也在里面）。所以本回合的候选内容 = 本回合快照里那 20 个文件（10 个源码 + 5 个包内测试 + 5 份门禁基准）。我按快照源码 + `attempt-001/candidate.patch` 的逐行改动核对，没有把空补丁当成无事发生。
- 执行报告：`attempt-002/executor-report.md`（DoD 逐项 + 自检表 + JSON），命令轨迹 `attempt-002/events-summary.json`；内核摘要：Pi 退出码 0、工具错误 0、无自动重试、报告 json_ok。
- 战后门禁：`T054-6-gate-post/report.md`、变异清单 `mutation-spec-20261118T202130271461Z.json`、内核变异记录 `mutations.json`、白盒文件与 22×2 条日志。
- JEV：`6j-jev` 报 `no_opinion auth_failed`，没有意见要采信。

## 二、候选源码逐项核对（实现是否忠实于合同）

1. 传输层：`transport.ts:222` 的 `postRaw` 复用内部 `request`（`new AbortController(` / `setTimeout(` / `credentials: 'same-origin'` 的计数未变），请求形状照 `post`（POST + Content-Type + X-Themis-UI + JSON.stringify），401 先 `runReauth()` 再回合成失败信封，拿不到回应 `throw result.missed`，正文原样交回。`mode.ts:18` 加了 `postRaw` 成员，导出集合仍是四个名字。
2. api.ts：新增 `JobKind` / `JobState` / `JobView`（八键）与 `toJobView`（envelope 用 `isEnvelope` 校验）；`startJob` / `getJob` / `cancelJob` 三个都是 `export function`，时限 15/15/30 以字面量写在各自函数体里（`api.ts:777`、`:791`、`:805`），创建正文恰 `{ kind }`、取消正文恰 `{}`，桩分支转 `mock/jobs.ts`；全文 grep 不到 fetch / XMLHttpRequest / EventSource / WebSocket。既有导出与既有函数一个没改（补丁里 api.ts 只有 4 个纯新增 hunk）。
3. jobStore：五个 `export function`；`ensureJob` 在途创建共用（inflight）、已有作业不重开；`setTimeout` 链每 1000 毫秒、卸载 `clearTimeout`、重开先查一次；已用秒数逐字 `Math.floor((Date.now() - t0) / 1000)`，t0 在创建回应到达时写入；查询 404 走 `commit(kind, { job: { ...cur.job, state: 'failed', envelope: reply.body ... } })`——错误信封并进同一个 JobView 的 envelope、状态落 failed、没新加模块字段；其它失败与 reject 只做空 commit，当暂时的。`resetJobStoreForTests` 只导出，`src/` 里除定义外没有别的调用点。
4. JobCard：`role="progressbar"`、「已用 ${elapsedSeconds} 秒」、[取消]（发过一次后禁用）；四种结局文字逐字（扫描失败 + 内核原文 / 已取消 / 超时（超过 150 秒），已停止）；时限表 `{ 'runtime-scan': 150 }` 与服务端 `ts/packages/ui/src/jobroutes.ts` 的 `JOB_TIMEOUTS` 里 `runtime-scan` = 150 一致；不渲染 `role="status"`；`import './job-card.css';` 放在组件 import 之后，是该样式表的唯一接线处。
5. RuntimeScan：唯一样式表 import（`./runtime-scan.css`）；外层按钮逐字「扫描 PATH」、secondary/md、SearchIcon 16×16、一直可点，点它先 `ensureJob` 再开框；内层对话框标题逐字「扫描 PATH」，脚注 [重新扫描]（`rescanDisabled = !(terminal || createError != null)`，即排队/运行时禁用）与 [关闭]；打开读一次 `getRuntimes()`，读失败显示「读不出已登记的 runtime，暂时不能登记」且不给 [登记…]；结果表四列列头逐字，行按服务给的次序；[登记…] 先 `setOpen(false)` 再 `start({ action: 'runtime.add', args: { runtime: adapter, adapter: adapter } })`，args 恰两个键。
6. RuntimesPage：只换了页头第一个按钮、删了 DisabledAction 与 SearchIcon 两个 import、改了文件头注释；并行三读、失败判定、children、`reload={reload}`、空态、Quizs 一块、页头说明一字未动（补丁只有 3 个 hunk）。
7. mock/jobs.ts：模块级 Map、五个开关、取消 200/409、查不到 404、五行夹具逐字；没用计时器、没有 WriteScenario、没引 JSON。
8. 两个样式表：只用 `--tt-*` 令牌，没有十六进制颜色、颜色函数或内联 style；job-card.css 有 `--tt-primary`、CSS 动画与 `prefers-reduced-motion: reduce` 停住。

没有发现为迁就测试而写的特判、硬编码测试输入、空异常处理或悄悄扩大的范围：`src/` 里没有 `process.env` / `import.meta.env` / 测试标记，没有为凑记号的注释或死分支；`cancelJob` 吞掉 reject 是合同写明的「409 不当失败、终态由下一次查询给」。

## 三、DoD → 实现 → 证据

| DoD | 实现（文件） | 证据 |
|---|---|---|
| D01 页头入口 | pages/RuntimesPage.tsx 只换页头第一个按钮，次序不变 | 门禁 S06、t009/t041/t049、page-app.test.tsx、result 探针 |
| D02 作业接口 | live/transport.ts postRaw、live/mode.ts、api.ts 三个 export function、mock/jobs.ts 五开关 | 白盒 W02/W03/W04、门禁 S03/S04/S05、包内 jobs-api.test.ts (a)–(e) |
| D03 作业状态模块 | jobs/jobStore.ts 五个导出、setTimeout 链 1000ms、404 落 failed | 白盒 W05、门禁 S02、包内 jobs-store.test.ts (a)–(f) |
| D04 作业卡与两个样式表接线 | jobs/JobCard.tsx + job-card.css（import 在组件 import 之后） | 白盒 W07/W08/W12、门禁 S03、包内 jobs-scan-page.test.tsx (b)(c) |
| D05 结果表 | writes/RuntimeScan.tsx 的 ScanResult | 白盒 W09、包内 jobs-scan-page.test.tsx (d)、result 探针 |
| D06 [登记…] | RuntimeScan.tsx 的 onRegister → 既有 useWriteFlow 的 runtime.add | 白盒 W09、包内 jobs-scan-page.test.tsx (e)、result 探针 |
| D07 三份新测试 | tests/jobs-api.test.ts(5) / jobs-store.test.ts(6) / jobs-scan-page.test.tsx(8)，无 skip/only/todo | V01/V02、门禁 S07 |
| D08 旧断言逐处改 | t009 :2877/:2881/:2974、t041 :320/:326/:592/:597、t043 :459、t045 :560/:563、t049 :270-271/:472/:586、page-app :93/:98、page-runtimes-empty :110 | 补丁 hunk 逐行核对、G01/R01 |
| D09 范围 | 20 个文件全在 allowed_modified/allowed_new 内，forbidden_paths 未碰 | changes.json + 补丁 + 本回合快照 |
| D10 全绿 | npm test / typecheck / build 与 52 份门禁基准 | 执行端自述（本回合未独立复跑）；门禁 W2 基线 12 passed |
| D11 postRaw 行为面 | tests/jobs-api.test.ts 的 (e)：createLiveClient + 假 fetch 直调 postRaw | V01/V02 |

## 四、战后门禁声明的 4 条「这条命令预期抓不住」：逐条复核

结论：四条都成立，声明是诚实的（不是等价变异，而是确实只有 W1 抓得住），各条都还有至少一条命令抓住。

- **M12**（jobStore 轮询 1000 改 500）：W2 的 S02 只查 `re.search(r'\b1000\b', code)`（已用秒数公式里的 1000 仍在）与「不用 setInterval」，探针只断言 `queries.length` 大于等于 2、不数次数 → W2 真看不见；W1 的 W05 钉住字面量 `  }, 1000);` → 抓住。日志 M12-W2.log = 12 passed，M12-W1.log 退出码 1。
- **M15**（mockGetJob 查不到的作业号改回 200）：S05 的静态检查只查文案串「没有这个作业」在文件里，而同一串在 `mockCancelJob` 里还有一份，变异后仍通过；三份探针与包内测试都不查不存在的作业号（包内测试用注入的假客户端，桩模式只查自己建出来的作业号）→ W2 真看不见；W1 的 W06 钉住 mockGetJob 那两行 404 序列 → 抓住。
- **M21**（job-card.css 的 reduced-motion 不停动画）：S03 只查 job-card.css 里有没有 `prefers-reduced-motion` 三个字，变异把 `animation: none;` 改成 `animation: inherit;` 后该串还在；jsdom 不跑 CSS、不模拟 prefers-reduced-motion → W2 真看不见；W1 的 W08 钉 `animation: none;` → 抓住。
- **M22**（runtime-scan.css 读失败提示写死颜色）：基准门禁里 `RUNTIMESCAN_CSS_REL` 定义了但没有任何用例读它（grep 确认只有定义那一处），jsdom 也不加载 CSS → W2 真看不见；W1 的 W10 钉 `color: var(--tt-tone-attention-fg);` 并禁十六进制 → 抓住。

其余 18 条在 `mutations.json` 里都是 W1 与 W2 双双 exit_code 1（caught），没有漏报。变异覆盖了本片全部 10 个被改的源码文件（transport / mode / api / RuntimesPage / JobCard / jobStore / mock jobs / RuntimeScan / job-card.css / runtime-scan.css）；被改的 10 个测试文件未作变异对象（正常）。门禁端没有提「没法变异的改动文件」。门禁端声明「候选缺陷：无」——我逐条核过候选源码，同意这个判断。

## 五、不挡的意见（建议类，不进阻塞项）

1. 重新扫描的过渡窗口：「已用 N 秒」沿用上一个作业的 t0。`doCreate` 的第一次 commit 只清 job 与 createError，不清 t0，所以点 [重新扫描] 后到创建回应到达前（几百毫秒到 15 秒）进度卡显示的是上一个作业的秒数。合同只规定「已用秒数从创建回应到达时算起」，新 t0 确实在回应到达时写入，不违反合同；只是显示上跳一下。要消掉的话，在 doCreate 的第一次 commit 里带上 `t0: null`。
2. [取消] 的「只发一次」只在本组件挂载期成立：`cancelSent` 是 JobCard 的局部 state，关掉对话框再打开后 [取消] 又可点，会再发一次 cancel（服务端对已结束的作业回 409，不影响状态）。合同写的是「取消请求在途时 [取消] 禁用」，不违反；真要严格「只发一次」，得把「已发过 cancel」记进 jobStore 的模块状态。
3. 桩的 mockGetJob「查不到作业号 → 404」这一支没有行为面用例（只被静态文案检查与白盒 W06 钉住）。合同第 11 步只要求 store 层的 404 用例（已用注入的假客户端测了），不挡验收；想更稳可在包内测试补一条「桩里查一个不存在的 id → 404」。
4. 几处旧断言的失败消息文案仍写着「照旧禁用」「仍禁用」，断言值却已改成 false（t041 :597、t049 :472/:586、page-runtimes-empty.test.tsx :110）。合同要求「每处只改写明的那一处、其余一个字不动」，所以这是按合同改的；只是读起来别扭，以后清理门禁时可一并改文案。
5. 门禁端新增的白盒文件 `tests/test_gate_t054_whitebox.py` 目前在本回合快照里。按规则它只用于本次核验（不进候选），集成时要不要留在仓库由集成端与协调人定。

## 六、我没有独立复跑的部分（如实写）

R01（52 份门禁基准 1103 passed）与 V01–V04（npm test 1306 passed、typecheck、build）的数字是执行端自述；本回合我没有执行工具，不能独立复跑。我能核到的是：门禁端在同一棵候选树上跑过 W1/W2（各 12 passed，见 baseline-W1/W2.log）、22 条变异的日志与记录，与执行端自述不冲突；内核摘要显示执行事件流完整、无工具错误、无自动重试，检查命令都带 `set -o pipefail`（内核标出的 12 条「掩盖退出码」命令全是 grep / wc / ls 一类读命令，不是检查命令）。

Verdict: PASS
