# 复审记录：t055-desktop-web-runtime-probe attempt-001（七端信箱 hub）

- 合同：t055-desktop-web-runtime-probe.v1（base c92d1db1564b10052de20b2bdf497ebb852a5074）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261118T232701933351Z-65d8），终审报告如下

## 终审报告

# T055-7 终审报告（audit-sonnet，审核端）

## 一、结论

**通过**。候选补丁（18 个文件：11 改 + 7 增）与合同 v1 逐条对得上，D01–D12 都有「实现 + 测试」两头的证据；内核六条检查全过且输出须匹配全部命中；战后门禁 24 条变异全被抓住（missed 0 / skipped 0 / equivalent 0）。执行端自陈的三处取舍逐条判定**都不构成候选缺陷**。无阻塞项。

## 二、我读了什么（只读，未跑命令）

- 候选：`candidate.patch`（18 文件）与工作目录里的成品源码逐个读完：`desktop/web/src/api.ts`（startJob/getJob/cancelJob）、`src/jobs/jobStore.ts`、`src/jobs/JobCard.tsx`、`src/mock/jobs.ts`、`src/pages/readonly1/runtimes-RuntimesView.tsx`、新建的 `src/writes/RuntimeProbe.tsx` / `RuntimeModels.tsx` / `runtime-probe.css` / `runtime-models.css`、新建的三份测试、两份包内测试的改动、四份门禁基准的改动。
- 合同：` .agent/plans/t055-desktop-web-runtime-probe.v1.md`（Behavior contract / 写法钉死 / 兼容性 / D01–D12）。
- 内核检查：`checks/01/checks.json` 与六份日志；执行概述 `summary.md`、执行报告 `executor-report.md`、`changes.json`、`scope.json`。
- 战后门禁：`T055-6-gate-post/report.md`、白盒日志（11 passed）、`mutations.json`（24 条逐条结果）；JEV（`6j-jev`）= no_opinion（auth_failed）。

## 三、DoD 逐条核对

| DoD | 实现（文件:位置） | 证据 | 结论 |
|---|---|---|---|
| D01 | RuntimeProbe.tsx:157-160 / RuntimeModels.tsx:133-136（ghost/sm 按钮，文字逐字「探测」「模型」，点它先 ensureJob 再开框）；api.ts:startJob 正文 `{ kind, runtime }`（键数 2）；标题 `探测 ${runtime}` / `模型 ${runtime}`；JobCard 的 kind 传对 | jobs-probe-page (a)、jobs-models-page (a)（含 data-variant/data-size、正文键数 2）；门禁探针；G01 | ✓ |
| D02 | RuntimeProbe.tsx 的 probeData/ProbeResult/ProbeFailedItems；JobCard.tsx:82-86 先 failedDetail 再 `<pre>` 内核原文 | probe (b)(c)(d)（有 data / ok 为假 / 无 data 三支，断言「没过项在内核原文之前」）；门禁 W06 | ✓ |
| D03 | RuntimeModels.tsx ModelsResult（三列列头、是/否/不限制、说明句、空数组「没有列出模型」、`<redacted>` 原样） | jobs-models-page (b)(c)；门禁 W07 | ✓ |
| D04 | jobStore.ensureJob 三分支（inflight 共用/本 runtime 直接返回/别的 runtime 未终态不建）+ useBusyRuntime；两个入口组件的 DisabledAction reason 逐字 | jobs-store-runtime (b)(c)(d)（store 层真断言：返回 null 且 creates 仍 1）；jobs-models-page (e)（禁用 + 悬停「正在列 pi 的模型」）；门禁 W04/W11 | ✓ |
| D05 | KINDS 三类、槽加 runtime、useSubscriber（行内入口也算订阅者）、scheduleNext 的 `if (s.job == null) return;` | jobs-store-runtime (a)–(g)；门禁探针 (j) 用 setTimeout 间谍钉住「没有作业时不排 1000ms 计时器」；T054 三份包内测试与 t054 探针原样过（R01 里 t054 passed） | ✓ |
| D06 | JobCard.tsx 三张按 kind 的表（150/150/120）、kind 缺省 runtime-scan、failedDetail 可选；RuntimeScan.tsx / runtime-scan.css / job-card.css 未改 | 门禁 W01（按字节冻结）+ W05；R01；scope | ✓ |
| D07 | RuntimeScan.tsx 未进补丁；runtimes-RuntimesView 其余照旧（版本列「—」、[删除…]、运行就绪检查仍禁用、Quizs、空态、两节标题）；运行时页禁用数 4→1 | page-app.test.tsx `toBe(1)`；t009/t023/t045；R01 | ✓ |
| D08 | mock/jobs.ts：缺 runtime/空串 → 400；同一 runtime 奇数次 ok:false（version_exit_code:1、missing_flags:['--no-context-files']）、偶数次正常；非 pi 正常份；列模型四行含一行 allowed:false 与 `<redacted>` | 门禁 W08/W11（桩 data 开关下奇偶两态）；桩模式用例 (i)(j)；变异 M09/M10/M11 全被抓住 | ✓ |
| D09 | jobs-store-runtime.test.ts(7) + jobs-probe-page.test.tsx(10) + jobs-models-page.test.tsx(6) = 23 例，无 skip/only/todo（我全目录搜过），测真实组件（渲染 RuntimesView，未 mock 被测组件） | V01「Tests 23 passed」 | ✓ |
| D10 | 六处旧断言逐处改：t023 :297-298/:783/:793、t009 :2854/:2861/:2970/:2974、t045 :560/:563、t054 :717、page-app :93/:98、page-runtimes :101/:109 —— 补丁逐行核对与合同「兼容性」一一对应，无顺手改别的断言 | 门禁 W02（删掉的15 行全是合同点名的旧断言）；R01 1115 passed；V02 | ✓ |
| D11 | 改动集合恰 18 个文件（11 改 + 7 增），与 Scope 一致；forbidden_paths 一个没碰 | changes.json / scope.json（越界 0、警告 0）；门禁 W01 | ✓ |
| D12 | — | checks.json：G01 14 passed、V01 23 passed、V02 138 文件/1329 例、V03 退出 0、V04「built in」、R01 1115 passed；六条的 output_must_match 全部 matched，无 must_not_match 命中；tree_before == tree_after ==候选树 | ✓ |

## 四、候选缺陷裁定（执行端自陈的三处）

1. **dismissible={!running}**（作业在跑时禁用头部关闭钮与 Esc，脚注 [关闭] 照旧能关）——**不成立**。`components/Dialog.tsx:20` 的 prop 注释就是这个语义（「false 时 Esc 仍 stopPropagation 但不调 onClose、头部关闭钮禁用（命令已发出，不能假装取消）」），仓库的 WriteConfirmDialog 对「命令已发出」是同一口径；合同没有规定这两个对话框的头部关闭钮与 Esc，只钉了脚注 [关闭]「关框不取消作业」，实现逐字符合。关框不取消作业、关掉再开是同一作业（creates 仍 1）、终态/创建失败后头部与 Esc 恢复——门禁白盒探针③逐条验过；悬停文字「正在探测 pi」「正在列 pi 的模型」经 aria-describedby 独立验过。动机里确有「让探针按它自己的取法观察到」的成分，但实现本身合规、也不依赖探针取法（探针改走 aria-describedby 同样过），故不作缺陷。
2. **`<redacted>` 单元格的 title**（「疑似凭据，内核已脱敏」）——**不成立**。可见文字与单元格文本仍原样（白盒探针⑤），不改合同「原样显示」的落点。
3. **桩的 source:'path' / command:[runtime] / error 示意措辞**——**不成立**。门禁 ASSUMPTIONS 明写不钉；扫描那一支的产出逐字未变。

本回合输入没有「门禁端举证的候选缺陷」一节，战后门禁报告的 candidate_defects 为空 → 无待裁定的候选缺陷。

## 五、门禁端声明的逐条判断

- 变异 24 条：caught 24、missed 0、skipped 0、error 0，无 unmutated/equivalent → 「无 unmutated、无 equivalent」的声明**成立**。
- M11（桩奇数份 ok:false→true）只有白盒探针抓得住：**成立**。静态 W 系列与执行端三份新测试都用注入的假客户端 / ?mock= 开关，不碰桩的奇偶份；这条确实只有门禁端自己能验。
- M03（去掉 startJob import）、M05（去掉 useBusyRuntime 的订阅）被 W04 抓住：**成立**（W04 逐条查记号）。
- W01「改动集合恰 18 个文件、旧地盘按字节未动」：与 changes.json、scope.json 一致，**成立**。

## 六、不挡的意见（写进报告，不进阻塞项）

1. **创建在途窗口里的跨 runtime 显示**：触发路径——点 A行的 [探测] 后、创建请求回来之前（live 模式最多15 秒，桩模式一个微任务），此刻 useBusyRuntime 返回 null（合同把 busy 定义成「未到终态的作业所占的 runtime」，创建在途时还没有作业），别的行按钮仍可点；点 B 行会开一个标题为「探测 B」的框，而槽里装的是 A 的作业，框里显示的是 A 的探测结果。store 仍挡住第二个创建（ensureJob 返回 null，不发请求），所以不会真起两个作业，后果只是显示串行。根因在合同的 useBusyRuntime 定义，不在实现；要修需在槽里另记「创建在途的 runtime」并让 useBusyRuntime 在创建在途时返回它（约 5 行 + 一条断言），代价是别的行的按钮在 15 秒窗口里全灰。建议交站主决定，本片不改。
2. **执行报告的自述不完整**：内核摘要里的「临时路径」线索（事件流第 18182 行 `cp src/writes/RuntimeProbe.tsx /tmp/keep-probe.tsx`）在执行报告里没有对应交代（报告只提了仓库内的临时探针目录与临时用例已删）。该文件写在工作目录之外、不进候选、不影响仓库内容，按规矩只算一条发现，不挡。
3. **执行端测试 (e) 的断言不够锋利**：jobs-store-runtime.test.ts 的 (e) 只断言「没有作业时 1.3 秒内没发查询」，而 doQuery 在没有作业号时本来就不发请求——删掉 scheduleNext 里那句 `if (s.job == null) return;`，这条用例照样绿。真正钉住「没有作业时不排计时器」的是门禁探针的 (j)（spy setTimeout、数1000 的调用为 0），而门禁基准会留在仓库里当回归测试，所以规则本身有测试护着；只是执行端自写的那条属于空心断言的味道。
4. **门禁探针的 hoverTip 取法脆**：它取「文档里第一个 [role=tooltip]」，而 Dialog 打开时会把焦点给头部关闭钮、那个钮自带 tooltip，于是先读到「关闭（Esc）」——执行端为了让探针读到行内入口的 reason，才把作业在跑时的关闭钮禁掉。建议后续片照 t023 的 tipOf 走 aria-describedby 取，别让实现迁就探针的取法。
5. **桩的奇偶计数是模块级**：`probeCounts` 无复位导出，同一文件里先建过几个同 runtime 的探测作业就决定下一份是奇是偶（vitest 按文件隔离，当前三份新测试不受影响）；后续片往 mock/jobs.ts 加用例时要留意。
6. **mock 的扫描一支被搬进了 terminalEnvelope()**：合同写的是 runtime-scan 那一支「一字不改」，实现把成功信封的调用点搬进了新 helper（行为逐字相同：扫描仍是 scanEnvelope()，error 支仍是 scanFailedEnvelope()，t054 的静态记号与探针照过）。字面上与「一字不改」有出入，功能上没有出入，记在这里备查。
7. **t009 :2974 行尾多了半句注释**（「；T055 接上 [探测] 与 [模型]（2026-11-16）」）：与该行原有的注释风格一致，无害。

## 七、证据与数字

- 内核六条检查（checks.json，全部 required、全部 passed）：G01 `14 passed in 68.45s`；V01 `Tests 23 passed`；V02 `Test Files 138 passed / Tests 1329 passed`；V03 退出 0（无输出）；V04 含「built in」；R01 `1115 passed in 1028.58s`。六条的 output_must_match 全部 matched=true，无 must_not_match 命中；candidate_files_modified 为空、tree_before == tree_after == baec09cb…（检查没有改动候选）。
- 战后门禁：白盒 `11 passed in 26.72s`；变异 caught 24 / missed 0 / skipped 0 / error 0；files_left_modified 为空。
- 范围：changes.json 18 个文件（11 M + 7 A），无 mode 变化、无越界；执行报告自述「未提交、未推送、未改依赖」，与候选树状态一致。
- JEV：no_opinion（auth_failed），无意见。

Verdict: PASS
