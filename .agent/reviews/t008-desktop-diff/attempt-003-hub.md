# 复审记录：t008-desktop-diff attempt-003（七端信箱 hub）

- 合同：t008-desktop-diff.v3（base edfec5ab1b2dc9a1d7ae1af42768aa1c7a72f42e）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T008-7-audit-post 终审报告（audit-sonnet，第 3 轮，复审封板）

结论: 通过

## 0. 摘要

- 上一轮阻塞项 B2、B3、B5 都已解决；diff-css.test.ts 的四处匹配器已补，三条新断言确实断言了对应规则（第 1 节）。
- 本轮没有新的阻塞项：门禁端没有举证候选缺陷；内核存档的白盒日志 93 过、0 红；变异清单 W1 十条全部抓到（第 6 节）。
- 必须修的阻塞项：无。可接受的披露项两条：(a) 执行端把 npm ci 日志写到 /tmp/npm-ci.log（第 3 节）；(b) 门禁端没跑的 15 条 Vitest 相关白盒，内核已实跑通过（第 4 节）。
- 能力限制：本回合只有 Read、Grep、Glob，没有运行任何命令，没有在浏览器里看渲染；没有读取或输出凭据。证据来自候选补丁与源码、内核的检查与存档记录、合同、设计稿。

## 1. 上一轮阻塞项复核（在 attempt-003 上）

候选相对 attempt-002 返工提交 edfec5ab1b 只改两个文件（scope.json：A0 M2 D0，全部 in_scope，违规 0）：DiffView.css（3 处）与 diff-css.test.ts。其余源码与上一轮审读的一致，不重审。

| 项 | 结论 | 依据 |
|---|---|---|
| B2 换行开时表格 max-content | 已解决 | DiffView.css:34 `.tt-diff[data-wrap='false'] .tt-diff__table { width: max-content; min-width: 100%; }`；:35 `.tt-diff[data-wrap='true'] .tt-diff__table { width: auto; }`。整个 src 的 css 里 `.tt-diff__table` 只有这两条规则；表格只在 DiffView.tsx:107、:134 渲染，一定在带 data-wrap 的根元素里（:165，取值 true 或 false）；两条特异性相同，互不覆盖。换行开时表格是块级 div、宽度自动，随文件主体（overflow-x: auto）宽度走，行是 grid、文字列 minmax(0, 1fr)，:42 的 pre-wrap 加 break-all 有了折行机会；行的 min-width 560 与 760 还在，容器更窄时由主体横向滚动。换行关仍是 max-content 加 min-width 100%，与合同 v3 §2（:248）一致；两种 white-space（:40、:42）没动。 |
| B3 列表计数 mono-sm | 已解决 | DiffView.css:19 `.tt-diff__file-item .tt-num { font: var(--tt-mono-sm); }`。计数 span 只来自 DiffView.tsx:96–101 的 counts()，用在列表项（:201）和文件头（:238）。规则要求祖先带 .tt-diff__file-item：列表项里的两个计数取 mono-sm；工具栏摘要里的计数是 .tt-diff__plus 与 .tt-diff__minus（:173、:175），不带 tt-num，不受影响；行号格（.tt-diff__no.tt-num，:113–114、:126）与文件头计数不在列表项里，不受影响（合同没给文件头计数定字体）。font 简写会把 base.css:20 的 tabular-nums 复位，但 mono 字体本来等宽，设计稿 :401 也是 tt-num 加 font: mono-sm 的写法，同效，不算问题。 |
| B5 分屏符号格颜色 | 已解决 | DiffView.css:55–56 `.tt-diff__sign[data-kind='add'] { color: var(--tt-tone-success-fg); }`，del 对应 --tt-tone-danger-fg。分屏符号格自带 data-kind（DiffView.tsx:127），被命中；统一视图的符号 span（:115）不带 data-kind，仍靠 :52–53 的行级规则（原样保留）；分屏的 context、empty 符号格没有颜色规则，取继承色，符合合同（只有 add、del 有色）。 |
| diff-css.test.ts 缺匹配器 | 已解决 | :57–60 四处现在是 `expect(hasRule(…)).toBe(true)`。我按现在的 CSS 逐条核：hunk 行（:39 同一条规则里有 surface-2 底与 text-3 字色）、empty（:47）、add 符号（:52）、del 符号（:53）都成立，补上不会变红。 |
| 新断言是否真断言 | 是 | :43–52（B2）：取出所有含 width: max-content 的规则，要求选择器带 data-wrap='false' 且同规则有 min-width: 100%，并要求换行开规则是 width: auto，对上一轮的无条件写法会红。:64–68（B5）、:70–73（B3）断言新规则的选择器与取值，对上一轮的 CSS 会红。旧断言 :37–41 一字未动，选择器收窄后正则（不锚定开头）仍匹配。 |

## 2. 执行端解读核对（独立核对）

- B2「同时采用两种写法」：合同 v3 §2（:248）原文是「换行关：表格 width max-content、min-width 100%，文字 white-space pre；换行开：文字 white-space pre-wrap、word-break break-all」，没有写换行开时的表格宽度；我上一轮阻塞项给的是用『或』并列的两种改法。同时采用的效果是：换行关 max-content 加 min-width 100%，换行开 width: auto（块级 div 本来就是 auto，显式写出多余但无害；门禁端把删掉它判为等价变异，我同意，见第 6 节）。与合同不冲突，已写进执行报告的 interpretations。
- B5「不按 mode 收窄」：合同 §2（:250）「符号：……add --tt-tone-success-fg，del --tt-tone-danger-fg」没有限定统一视图；同一段里凡要区分模式的地方（统一视图的新行号格右边框、文字右内边距、底色）合同都明说了，所以不收窄是对的。统一视图的符号 span 不带 data-kind，新规则碰不到它，不会和行级规则叠出别的颜色。与合同不冲突，已写进 interpretations。
- 没有发现没写进 interpretations 的解读：B3 的选择器就是任务书里的示例；内核在事件流里标出的那 1 处宣布的解读（第 4429 行）就是 B2。
- 过程：执行端曾试图 grep 白盒文件（事件流第 220–223 行），文件不在它的 worktree（No such file），没有读到白盒内容，修复依据只有任务书里的阻塞项文字。

## 3. /tmp 日志披露：裁定为可接受的披露项，不是阻塞项

- 事实：事件流第 5834–5843 行，一条命令：在 desktop/web 下跑 npm ci，输出重定向到 /tmp/npm-ci.log，再用 tail 读回末 5 行；只此一次。执行端在随后的推理里（第 5910 行）自己发现违规，之后的检查都改用 `set -o pipefail; … | tail` 的照抄写法，并在报告的 limitations 里披露。另有一处小出入：self_checks 里 npm-ci 的命令写成了不带重定向的 `cd desktop/web && npm ci`，与实际命令不完全一致，由 limitations 里的披露补上了。
- 性质：字面违反执行说明第 5 条（固定路径、在工作目录之外），属实；内核的摘要也只把它列为『事后扫描线索』，不是违规裁定。
- 为什么不拦：(1) 对候选没有影响：scope.json 只有两个 in_scope 文件，摘要里新增的忽略路径（.pytest_cache、dist、node_modules）都在工作目录内。(2) 这份日志不是任何验收证据：npm ci 的结果由内核 V01 的 P1 在新环境重新跑；日志内容只是 npm ci 输出，没有凭据，也没有读取别处的文件。(3) 它是已发生的过程事件，不是候选缺陷，退回执行端也改不了候选；执行端预算已用尽，内核会拒收。
- 我没能核实 /tmp/npm-ci.log 现在是否还在、之前是否已有同名文件：我试读系统临时目录与 Git 安装目录，两次都因超出允许目录被权限系统自动拒绝，没有重试也没有绕过；这不影响结论。
- 建议（不进阻塞项）：协调端把它记入过程记录，向站主汇报时带一句；以后需要截短输出的命令继续用『机器合同摘要』里的照抄写法。

## 4. Vitest 未实跑：不影响结论，内核实跑记录确实存在

门禁端的 15 条（test_vitest_wb 7、test_vitest_baseline_probe_replay 6、ran_clean、gate_probe 清理）因 worktree 没有 node_modules 被 deselect，这是门禁环境的限制，不是候选问题。Vitest 的实跑结果在内核记录里有，三处互相印证：

1. checks/01/V01：29 passed、退出码 0、all_required_passed 为真、候选树前后一致、没有改动候选文件。V01 里的 test_d13_p1_pipeline_steps_pass（基准 :3279–3289）要求 npm ci、npm run build、npm test、npm run check:contract 都退出 0，npm test 输出有 Tests … N passed、没有 failed、skipped、todo，Test Files 行没有 failed；pipeline 夹具（:2960–3034）在没有 npm 或 npm ci 失败时这条会红，所以 29 passed 说明全量 Vitest（含执行端 diff-css.test.ts）在内核环境里实跑通过。同一夹具还把各探针写进 gate-probe/ 用 npm test 逐份跑，探针用例（test_d01、test_d02_d04_d06、test_d07、test_d08、test_d09、test_transitional_p9）也在这 29 条里。
2. 白盒存档日志 whitebox-20261021T073118014265Z.log：93 passed in 80.08s，没有 deselected。93 = 门禁端跑的 78 + 没跑的 15，所以那 15 条在内核环境里实跑且全过（白盒的 pipeline 夹具在没有 node_modules 时自己跑 npm ci，:1184–1188）。
3. 执行端自述的 38 文件、360 例与此一致：diff-css.test.ts 现有 12 条 it，比上一轮多 3 条（B2、B5、B3 各一），上一轮的 357 加 3 正好 360，文件数不变。这条只当一致性核对，不当独立证据。

本轮候选只动 CSS 与 diff-css.test.ts，门禁端推断『探针行为输入没变』成立，内核实跑又把推断变成了实测。不需要额外环境，不列阻塞项。

## 5. JEV 需关注项的判定

| 项 | 判定 | 依据 |
|---|---|---|
| 自述完成而无证据（p=0.90） | 不成立 | D01–D14 逐条有证据，见第 7 节。本轮动到的三条（D02 的 B3、D03 的 B5、D06 的 B2）各有白盒用例（s04b、s01b、s04，在内核存档的 93 条里全过）和执行端新断言（V01 的 P1 里全量 npm test 通过）；没动的 D01、D04、D05、D07–D11：补丁不碰它们的文件（scope.json），上一轮我读源码的结论仍然成立，内核对本候选复跑了 V01、V02、V03（29、255、7 条全过）。执行报告里部分 DoD 的说明偏短（如『上轮成果』），是写法问题，证据在内核记录里。 |
| 误导程度（2.46/3，置信 0.46） | 没有发现会改变结论而独立检查又揭示不了的说法 | 我对照补丁、scope.json、checks 逐条核了执行报告的陈述：只改 2 个文件、V01 29、V02 255、V03 7、diff-css 12 条、补 4 处匹配器且未改既有断言语义，全部属实；B3、B5、B2 的修法与描述一致。唯一的出入是 self_checks 里 npm-ci 的命令写法与实际不完全一致（第 3 节），已由 limitations 披露。 |
| 弱化测试（p=0.57，置信 0.14） | 不成立（摘要里『删除了 4 行含断言的代码』是误报） | (a) 执行端测试：被删的 4 行就是 diff-css.test.ts 里缺匹配器的 `expect(hasRule(…));`，原样换成带 `.toBe(true)` 的同一表达式，是加强，不是削弱（之前没有匹配器，等于没断言）；没有删 it，没有 skip、only、todo。(b) 门禁白盒：与上一轮存档（…064930684359Z.py）对比，总行数 1289→1303，恰好多出 s04b 的 14 行；断言行 123→126，多出的 3 行都在 s04b；其余断言行的文字逐条相同，只整体后移 14 行；DIFF_EXPECT、LOG_EXPECT、选择器匹配器（:100–299）逐字相同；内嵌 JS 里 expect、check 等断言记号的数量 169 = 169，it 与 describe 数量 9 = 9。没有删除或放宽任何已有断言。 |
| 自行解读合同（p=0.69，置信 0.38） | 不成立 | 两处解读（B2 的两种写法、B5 不收窄）都写进了 interpretations，并经第 2 节核对与合同不冲突；没有发现没披露的解读。 |

## 6. 门禁记录核对

- 门禁报告：白盒 78 过、0 红、15 deselected（无 xfail、skip、xpassed），没有候选缺陷；s01b、s04 转绿；新增 s04b 覆盖 B3。s04b 的构造合理：列表项里的 span.tt-num 的 font 必须算出 var(--tt-mono-sm)；统一视图行号格（.tt-diff__no.tt-num）不单独设 font（防止规则不带列表项作用域）。不会在正确实现上误报，也不绑规则的写法（选择器按结构位置匹配）。
- 变异 W1（mutations.json）：10 条全部 caught，missed 0、skipped 0、error 0，没有改动残留（files_left_modified 为空）。M01–M02 对应 B3，M03–M05 对应 B2，M06–M09 对应 B5 与统一视图符号色，M10 是 560px 的最小宽。候选改动的唯一非测试文件是 DiffView.css，三处改动都有变异覆盖。
- 等价变异：门禁端没有列等价变异，只在报告里说明『删掉 :35 的 width: auto 不会被抓，行为等价，所以没列』。我同意：该规则只是重述块级 div 的默认值，删掉后换行开时表格宽度仍是 auto、不是 max-content，行为不变；执行端自己的 diff-css.test.ts 会因此变红，是额外的严格，不是缺口。
- 『没法变异的改动文件』：门禁端没有声明。候选改的另一个文件是测试 diff-css.test.ts，本身是测试，不需要变异。
- 我上一轮建议放进变异清单的『折叠钮图标尺寸』（上轮报告第 7 节第 3 条、第 10 节）这次没放，也没有对应测试。这是建议类意见，不升级为阻塞项：候选取值正确（DiffView.tsx:232 两个图标都是 width/height 14，合同『图标 14』），本轮补丁没碰 DiffView.tsx，门禁返工次数也已到 2。留给协调端决定要不要另派。
- 基准测试 tests/test_gate_t008_baseline.py 没有改动（git status 里没有它；锁定 f17c849f5a）。

## 7. DoD → 证据

| DoD | 证据 | 本轮结论 |
|---|---|---|
| D01 解析纯函数 | V01 test_d01_probe_parse_diff；白盒 node 电池 N01–N27、性能 16 条、s14；执行端 diff-parse.test.ts | 补丁不碰 parseDiff.ts，上一轮 R7 已核，仍成立 |
| D02 统一视图、摘要、文件头 | V01 test_d02_d04_d06_probe_diff_view；白盒 WB-D02、s09、s01、s01c；B3：s04b 与 diff-css 新断言 | 与 §2 一致；列表计数字体已修 |
| D03 分屏 | V01 view 探针；白盒 N26、N27、s01b、s01c；B5：diff-css 新断言 | 与 §2 一致；分屏符号色已修 |
| D04 折叠与列表 | V01 view 探针；白盒 WB-D01、WB-D04 | 一致 |
| D05 只按文本显示 | V01 view 与 showcase 探针；test_s3_d05_diff_text_goes_through_strip_ansi_only | 一致 |
| D06 模式与换行 | V01 view 探针与 test_s4_d02_d03_d06_diff_view_css_values（两种 white-space 等）；B2：白盒 s04 与 diff-css 新断言 | 一致；换行开表宽已修 |
| D07 跟随状态机 | V01 test_d07_probe_log_follow_state_machine；白盒 s07、s08 | 一致 |
| D08 过滤 | V01 test_d08_probe_log_filter；白盒 WB-T01、WB-T02 | 一致 |
| D09 TextViewer 可选属性 | V01 test_d09_probe_text_viewer_slots、test_s6_d09；V02（T007 回归）；白盒 s10 | 一致 |
| D10 图标与导出 | V01 test_s1_d10_files_and_exports、test_s2_d10_new_icons_match_contract；白盒 s11、s12 | 一致 |
| D11 演示 | V01 test_transitional_p9_diff_showcase_probe；白盒 s03、s13、s16 | 一致 |
| D12 静态 | V01 的 test_s3_*、test_s5_*，P1 里的 check:contract；白盒 s06、s15；diff-css.test.ts | 一致 |
| D13 回归 | V01 的 test_d13_p1_pipeline_steps_pass 与 test_p10；V02 255 passed；V03 7 passed | 一致 |
| D14 范围 | scope.json（A0 M2 D0，全部 in_scope）；V01 test_d14_executor_tests_in_place | 一致；新测试无 skip、only、todo |

## 8. 观察项与仍待人工的事项（都不进阻塞项）

1. 统一视图片段头排版：本轮仍未改，沿用上一轮第 7 节第 1 条（合同对统一视图片段头没有版式要求；按 CSS 规则，hunk 行是四列 grid，单个文本节点落进 44px 首列，默认 white-space 会按词折成窄条）。列入人工项最优先看；要修只需一条 CSS 规则。
2. 合同缺口（规划端，不是候选缺陷）：设计稿 :401 的列表计数与 :410 的文件头计数都带颜色（加号取 --tt-tone-success-fg，减号取 --tt-tone-danger-fg）并取 mono-sm。合同 v3 只给列表计数写了 mono-sm（:243），文件头计数什么都没写（:245），颜色两处都没写；候选的两处计数都没有颜色。人工对照画布时看一眼，要补由规划端出新版合同。
3. 折叠钮图标 14 仍没有测试（见第 6 节），取值正确。
4. 沿用上一轮第 7 节：title 为空串时摘要多一个前导『 · 』；diff-parse.test.ts 缺 B1 那条回归用例（行为由白盒 N01 兜底）；parseQuoted 对非 BMP 字符的处理只读代码推断；DiffShowcase 没有『只加』片段。
5. 人工项 H1–H3、H5、H10（真浏览器）仍待人补做，不阻塞；优先看 H3（换行开关在真浏览器里是否有可见效果，B2 修好后第一次能看）、统一视图片段头、H2、H10、H5。DiffShowcase 按合同不挂陈列页，要看需等 T006 落地或站主临时本地挂载。

## 9. 阻塞项

无。必须修的阻塞项没有；可接受的披露项见第 3、4 节。退回对象：无。

## 10. 给协调端

- 通过：可给执行端发『通过』（T008-5-exec），并给站主汇报。
- 汇报时建议带上：/tmp 日志的披露与裁定；人工项（H1–H3、H5、H10、统一视图片段头）；观察项 2（设计稿计数颜色）。
- 没有需要退回任何一端的事项，门禁返工次数不再增加。

## 11. 限制

- 只读：只有 Read、Grep、Glob，没有 Bash；没有运行 pytest、vitest、npm，没有重跑白盒，没有在浏览器里看换行效果与片段头排版（按 CSS 规则推演）。
- 白盒存档日志是否正好对应本候选树，按任务书的说明（就是跑出下面结果的那一份）采信，未独立核实。
- 事件流 events.jsonl 只用 Grep 看了 /tmp 命令、白盒 grep、解读线索，没有逐条读。
- 为核实 /tmp/npm-ci.log 是否留存，我试读了系统临时目录与 Git 安装目录，两次都被权限系统自动拒绝（超出允许目录），没有重试、没有绕过；不影响结论。
- 没有读取或输出任何凭据。

Verdict: PASS
