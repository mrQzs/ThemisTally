# 复审记录：t056-desktop-web-runtime-doctor attempt-001（七端信箱 hub）

- 合同：t056-desktop-web-runtime-doctor.v1（base 7083e7aa1d3c0706df6e2354bfbd28ac72553723）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T031329127627Z-da00），终审报告如下

## 终审报告

# T056-7 终审报告（audit-sonnet · 2026-11-19）

结论：**通过**。无阻塞项，不退回。

## 一、核对材料
- 合同 `.agent/plans/t056-desktop-web-runtime-doctor.v1.md`（v1，全文 484 行读完）。
- 候选补丁 `.agent/runs/t056-desktop-web-runtime-doctor/attempt-001/candidate.patch`（16 文件，+834/−55；候选树 `7171d312f0528e5c96e85bb9028cffb5d85d0ee6`），以及快照里 8 个改动/新增源文件的原文。
- 执行报告与概述：`executor-report.md`、`summary.md`、`checks/01/checks.json` 与 G01/V01/V02/V03/V04/R01 六份日志。
- 战后门禁：`T056-6-gate-post/report.md`、`mutation-spec-…json`、`mutations.json`、白盒测试与日志。
- JEV：`T056-6j-jev/report.md` = no_opinion auth_failed（无意见，无可核项）。

## 二、忠实度：DoD → 实现落点 → 证据
| DoD | 实现落点（我读过的源码） | 证据 |
|---|---|---|
| D01 | RuntimeDoctor.tsx 按钮：文字「运行就绪检查」、secondary/md、`<PlayIcon width={16} height={16}/>`、`disabled={running}`；onRun→`ensureJob('doctor')`；api.ts:777 三元 `runtime == null` → 正文恰 `{kind}`；jobStore.doCreate→startJob | 包内测试 (a)：`creates[0] toEqual({kind:'doctor'})`、每秒查同一作业号、进度条 aria-label「就绪检查进行中」、「已用 N 秒」、[取消]；V01 11 passed、G01 13 passed |
| D02 | `running = creating \|\| queued \|\| running`；终态/创建失败走 `restartJob('doctor')`；`<JobCard key={job?.id ?? 'creating'}>` | 测试 (a)(f)(g)(h)：运行中禁用、结束后再点新作业、卸载重挂载不再创建、取消后再点新作业的[取消]可点；V02 1340 passed |
| D03 | DoctorResult/HeadlessCard/SimpleRow：汇总「全部就绪」/「有未就绪的角色（N 个）」、卡头「✓ 就绪 · 角色名 · profile X」、八个 `<dt>`（命令/版本/模型在列表中/登录/思考级别/允许列表/凭据/接通状态）、问题列表（danger）、说明行（--tt-text-3）、缺键「—」、allowed null「不限制」、凭据空「无」 | 测试 (b)(d) 逐值断言（`valuesOf` 对八个 dt 逐个 toEqual）；门禁 t056 S06 + 探针；G01 13 passed |
| D04 | `failedWithData` 分支只渲染 `<DoctorResult/>`、**不渲染 JobCard**（因此没有「就绪检查失败」与「内核报错」）；无 data 的失败仍走 JobCard | 测试 (c)(e)；G01 |
| D05 | `neverRan` → `p.rt-ready` 新句（去掉「运行入口在第二阶段接入」）；运行中另起一行「离开这个页面作业也会继续，回来时显示结果。」（rd-note，--tt-text-3） | 测试 (a)；t009 :2907 改后照过 → R01 1129 passed |
| D06 | api.ts:154 JobKind 四类（doctor 在末尾）；jobStore KINDS/snaps/subscribers 各一项；JobCard 三张表各一项（600 / 就绪检查失败 / 就绪检查进行中）；补丁对这三处只增行，既有扫描/探测/列模型三支一字未改 | R01 全量 1129 passed（含 t054/t055 与 T054/T055 包内测试）；变异 store-1/2/3、card-1/2/3 全被抓住 |
| D07 | mock/jobs.ts：400 判据改为只挡 probe/models；kindFailedEnvelope 加 doctor 支（无 data）；terminalEnvelope 加 doctor 支（奇数 failed 带 data / 偶数 succeeded）；doctorCounts 奇偶 | 门禁 stub 探针 (a)(b)(c)(d)；包内测试 (j-loading)(j-error)；变异 mock-1..5 全被抓住 |
| D08 | 视图只渲染 `<RuntimeDoctor />`，DisabledAction/PlayIcon 的 import 删净（DisabledAction 在别处仍在用，不是死文件），视图从 `../../api` 仍只 import type；新 CSS 类名全 `.rd-`、只用 `--tt-*` 令牌、唯一 px 字面量是 `1px`、无内联 style/role=status；`.rt-ready` 留 runtimes-styles.css 未动 | scope.json violations 空；白盒 W08；R01 |
| D09 | jobs-doctor-page.test.tsx 365 行 11 例覆盖 a–j，无 skip/only/todo，挂真实 RuntimesView、用假 LiveClient 注入真实响应（不 mock 被测组件） | V01 11 passed；白盒 W09；t002 扫描 |
| D10 | t009(:2895/:2904/:2907/:2970/:2974/:2975)、t023(:37/:805/:808-810/:1401)、t043(:491-492)、t045(:560/:563)、t054(:717-718)、t055(:109/:532-533/:749/:918-923/:926-929/:930-935/:889-893)、page-app(:93/:98)、page-runtimes(:115/:119) 逐处只改合同写明的那一处 | 我逐处与合同「兼容性」一节对照；R01 全量 1129 passed；t055 S09 的反向残留检查也过 |
| D11 | scope.json：13 改 + 3 新增，violations/warnings 空；无 forbidden_paths、无 dist/gate-probe 遗留进候选 | scope.json、changes.json、candidate.stat.txt |
| D12 | 内核在候选树上独立复跑六条必要检查全绿（tree_before=tree_after=候选树，modified_by_checks=false） | checks/01/checks.json + 六份日志 |

## 三、范围与「有没有弱化测试」
- 补丁只动 16 个文件，恰是合同 allowed_modified_files(13) + allowed_new_files(3)；forbidden_paths 一个没碰。
- 六份门禁基准的改动逐处对照合同「兼容性」一节，**都是「把旧口径改成新口径」那一处**，没有顺手放宽别的断言：t009 :2975 是 `toBeGreaterThan(0)`→`toBe(0)`（合同写明）、:2974 白名单在「'模型'」后加「'运行就绪检查'」且保留「'扫描 PATH', '探测', '模型'」连写；t023 只删悬停提示两行（合同写明）；t043 两个记号换成 `"RuntimeDoctor"`（合同写明）；t045/t054/t055 按合同给的「含这几类」改法，并加了对旧口径的残留检查（变强不是变弱）。
- 包内两份测试只改标题与一个 true/false（page-app :98 `toBe(1)`→`toBe(0)`），断言强度未降。
- 桩的 400 判据从 `kind !== 'runtime-scan'` 改成 `(kind === 'runtime-probe' || kind === 'models')`：语义等价地放行 doctor，三支既有行为不变（t055 S04 照过）。
- 没有把实现抄进测试：新包内测试断言的是渲染出来的 DOM 文本与发出去的请求正文。

## 四、执行报告自述 vs 内核线索（逐条对上）
- **临时路径**：events-summary.json `temp_path_uses=[]`、`temp_path_use_count=0`、`temp_dirs_without_cleanup=[]` —— 与执行端自述一致，没有往系统临时目录写固定路径的做法。
- **可疑命令**：内核摘要点了 1 条「退出码被管道掩盖」的命令（对门禁 S07 的诊断：`… | grep -A20 … | head -30`）与 22 条探索命令。逐条对上：这些都不是报告里的六条自检；六条自检的退出码由内核在同一候选树上独立复跑确认为真（全 0），没有任何一条 DoD 证据依赖被掩盖的命令。**未发现自述不实**。
- **R01 覆盖面**：执行端只跑了 18 份相关子集并已在 limitations 披露（与合同要求的 54 份有差距）；内核已按合同跑完全量（1129 passed），缺口已补齐。
- **13 处解读 / 30 处合同歧义提法**：报告里的 3 条 interpretations 与事件流被标出的关键词逐条对上——核心是 t009 :2970 标题「、T055」与「与 T055」不一致，落盘代码按合同「保留『与 T055 接上的 [探测]、[模型]』」写成「…[探测]、[模型] 与 T056 接上的 [运行就绪检查]」；t045 :560/:563 最终按合同改成「运行时页 0」（不是事件流里犹豫的 1）。两处思考级别解读与门禁探针口径一致。
- **JEV**：6j 为 no_opinion auth_failed，无意见需要核。

## 五、战后门禁的声明逐条判断
- 白盒 9 条用例（W01–W09）：W06/W07 是把**候选文件里的纯函数原文**抽出来交给 node 执行（抽原文，不是抄进测试的副本），断言的是合同边界输入的实际输出；W01–W05/W08/W09 是接线与字面核对。就绪卡八个键值行的值是 W06 真跑出来的，不是「只读源文件文本就算生效」的空心断言。
- 变异清单 33 条覆盖 7 个非测试文件（api 2、jobStore 4、JobCard 3、mock 5、视图 2、RuntimeDoctor 15、CSS 2），其中 11 条是接线类（删 import / 删挂载 / 删分支），不只是改文本取值。mutations.json：caught 33 / missed 0 / skipped 0 / error 0，每条锚点 count_found=1。
- 门禁端**没有**声明等价变异，也**没有**声明「某文件没法变异」，所以没有需要我裁定放行的项；33 条声称等价的断言一条也没有。
- 门禁端对执行端三处解读的结论（t009 :2970 标题、思考级别双缺键写「—」、DOCTOR_CARD_LABELS 留逐字记号）我逐条对过合同：前两条在合同口径内；第三条是合同「写法钉死」要求「就绪检查失败」「就绪检查进行中」逐字出现在 RuntimeDoctor.tsx（功能由 JobCard 的表给出），属合同要求，不构成候选缺陷。
- 战后门禁的白盒文件与变异清单按本回合口径只用于核验，不当仓库回归测试提意见。

## 六、不挡的意见（交站主定夺，不构成打回）
1. **R01 覆盖面**：执行端只跑 18 份相关子集（已披露），内核已跑全量 54 份。若站主要求执行端每轮自跑全量，建议在合同里把 R01 拆成两批并写进执行说明的时限预算。
2. **`DOCTOR_CARD_LABELS` 是死代码**（不渲染进 DOM）：它是合同「写法钉死」要求这两个逐字出现在 RuntimeDoctor.tsx 的产物；功能上的文案由 JobCard 的表给出。将来改这两条文案要同时改两处。
3. **三个理论边界的取值**：`allowed` 整个键缺失时写「不限制」而不是「—」；`connected` 缺失时写「未接通」；`data.ready` 缺失时汇总会写「有未就绪的角色（0 个）」。内核的 doctor 行恒带这三个键（roles-probe 的契约），现实路径走不到；要更严可以改成缺键写「—」。
4. **桩里 doctor 的奇偶份**用一个只放 'doctor' 一个键的 Map，功能上与计数器等价，可读性略绕。

## 七、结论
实现忠实于合同、范围没有越界、旧断言按合同逐处改到位、内核在候选树上独立复跑六条必要检查全绿、战后门禁 33 条变异全抓住、门禁端未举证任何候选缺陷。**结论：通过**，无阻塞项，不退回。

Verdict: PASS
