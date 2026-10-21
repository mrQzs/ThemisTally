# 复审记录：t008-desktop-diff attempt-002（七端信箱 hub）

- 合同：t008-desktop-diff.v2（base f17c849f5a96be3a576faff57137f2672728b892）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 1；变异检查退出码 None
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T008-7-audit-post 终审报告（audit-sonnet，第 2 轮，复审封板）

## 0. 结论

结论: 返工
退回: 执行端

- 上一轮：B1（R7）已解决；B4（白盒 s12）已解决；B2（换行开时表格仍 max-content）、B3（列表计数 --tt-mono-sm）原样未修。
- 门禁举证的两处候选缺陷都成立：缺陷 B 就是 B2；缺陷 A（分屏符号格没有加号/减号颜色）列为新的 B5。
- 阻塞项共 3 条，都归执行端：B2、B3、B5（第 9 节）。战后门禁没有阻塞项，本轮不退回门禁（门禁端返工次数停在 2）。
- 候选是整体重写，执行报告没有提到 B1–B3：B1 是重写后顺带成立的，B2、B3 照旧。DiffView.css 与基准测试里的参考样例 GOOD_DIFF_CSS（tests/test_gate_t008_baseline.py:3363–3413）几乎逐行相同，连出处注释都一样；样例里的三处缺陷（表格宽度无条件 max-content、列表计数没有字体规则、符号颜色只写在统一视图）原样进了候选。LogFollow.css 与 GOOD_LOG_CSS 也近乎相同，但那份样例没有缺陷。
- 能力限制：本回合只有 Read、Grep、Glob，没有 Bash，没有运行任何命令，没有看浏览器；没有读取或输出凭据。证据来自候选源码、内核检查记录、白盒存档文件与日志、合同、设计稿、基准测试。

## 1. 上一轮阻塞项逐条复核

| 项 | 结论 | 依据 |
|---|---|---|
| B1（R7） | 已解决 | parseDiff.ts 主循环：`diff --git ` 先于一切处理（:286–289）；片段还有剩余行数时，空格、加、减、反斜杠、空行按 R7 处理，其余行结束片段并交给文件头处理（:322–325）；剩余行数用完后，只有反斜杠行记给上一行、`@@` 开新片段，其余一律跳过（:327–336）。白盒 N01 在内核存档日志里是绿的（92 条里只有 s01b、s04 红）。有剩余行数时的行为没变（`--- ` 开头的内容行仍算删除）。 |
| B2 | 未解决 | DiffView.css:32 仍是无条件的 `.tt-diff__table { width: max-content; min-width: 100%; }`；:39 换行开只改文字；diff-css.test.ts 没有新断言（:37–41 只查了无条件写法）。见 2.2。 |
| B3 | 未解决 | DiffView.css 没有 `.tt-diff__file-item .tt-num` 之类的规则；:16 的 .tt-diff__file-item 没有 font；整个 src 的 css 里 `.tt-num` 只出现在 base.css:20（tabular-nums）和 Table.css。列表计数是只带 tt-num 的 span（DiffView.tsx:96–101），继承外层页面字体（.tt-app 是 --tt-text-md），不是 --tt-mono-sm。diff-css.test.ts 没有新断言。 |
| B4（白盒 s12） | 已解决 | 白盒 :504–519：基线内容是前缀；『第 7 片』注释在追加部分里；注释之后紧跟的前 4 项导出顺序、名字对（DiffView、DiffViewProps、LogFollow、LogFollowProps）；这 5 行里不出现 diff/、evidence、overlay；之后别的片再追加的导出不影响这条。没改名，是『放宽』的那个选项。 |

B1 的残留（不列阻塞项）：执行端自己的 diff-parse.test.ts:154–169 只测了『用完后多出来的行忽略』（` extra after…`、`-ignored`），没有上一轮要求的那条（读完的片段后面各跟 `--- `、`+++ `、new file mode、deleted file mode、Binary files … differ、rename from/to、GIT binary patch）。行为现在由白盒 N01 兜底，N01 留在仓库里当回归测试，所以不再拦；执行端返工时顺手补上更好。

相对 attempt-001 的改动范围：attempt-002 不是在 attempt-001 上改，而是从基线重写 18 个文件（A15 M3，全部 in_scope，无越界，无依赖变动）。它没有覆盖 B2、B3 的修复。重写还带来三处和 attempt-001 不同的新情况：(a) 分屏符号格没有颜色（B5）；(b) 片段头不再是带 grid-column 的 span，改成行本身带 grid-column（无效），统一视图的片段头文字落进 44px 首列（第 7 节）；(c) diff-css.test.ts:46–49 四处断言没有匹配器（并入 B5）。LogFollow、TextViewer 差异、图标、导出、演示与合同一致（第 8 节）。

## 2. 门禁举证的两处候选缺陷

### 2.1 缺陷 A（分屏符号格没有颜色）：成立，列为 B5

- 合同依据：v2.md:235『符号：居中、字重 600（详情页 :419）、不可选中；add --tt-tone-success-fg，del --tt-tone-danger-fg』没有限定统一视图。同一段里凡要区分模式的地方合同都明说了（『统一视图的新行号格右边框』『文字：右内边距统一 --tt-space-3、分屏 --tt-space-2』『底色：统一视图……分屏按格……』），符号颜色没有限定，就是两种模式都要。v2.md:221 写明分屏每格带 data-side 与 data-kind、符号 add 为加号、del 为 −。设计稿 docs/ui-design/pages/05-attempt-详情-Themis-Tally.html:432、:435 的分屏符号格也上色（左 danger、右 success）。
- 候选：DiffView.css:49–50 的颜色规则选择器是 `.tt-diff__row[data-kind='add'] .tt-diff__sign`（del 同），只匹配统一视图（行自己带 data-kind）；分屏的行是 data-kind='pair'（DiffView.tsx:139），符号格自带 data-kind（:127），没有任何规则给它上色。
- 白盒公平：test_wb_s01b（:311–324）对统一视图的要求候选本来就满足；对分屏只要求符号格的 color 算出对应令牌，选择器匹配器按结构位置算，`.tt-diff__sign[data-kind='add']`、`.tt-diff__row [data-kind='add'].tt-diff__sign` 等写法都能过，伪类保守地当作不匹配。基准 S4 不受影响。

### 2.2 缺陷 B（换行开时表格仍是 max-content）：成立，就是 B2，仍违反合同

- 依据同上一轮：v2.md:233 把 max-content 只写在『换行关』一侧；规划端 T008-1-plan/report.md:119『换行开时表格宽度自动』；设计稿 :414 的外壳只有 min-width。功能推演（按 CSS 规则，没有在浏览器里看）：行是 grid、文字列 minmax(0, 1fr)，表格 width: max-content 时表宽等于最长一行不换行的宽度，pre-wrap 与 break-all 没有折行的机会，『自动换行』开关没有可见效果。
- 候选 DiffView.css:32 无条件；:39 换行开只改文字。仍违反。
- 白盒公平：test_wb_s04（:384–392）对换行关要求 max-content 与 min-width 100%（同基准 S4），对换行开只要求 width 不是 max-content；限定选择器、换行开覆盖成 auto 或 100% 都能过（自检 :1278–1289 覆盖这几种写法）。基准 S4 与 diff-css.test.ts:39（正则不锚定选择器开头）在修好之后照样通过。
- 备注：基准测试自检用的 GOOD_DIFF_CSS（:3390）写的也是无条件规则，所以基准全绿；它是门禁自检样例，不是合同。

## 3. 白盒重写是否放宽了合同写明的取值

结论：没有发现会放过错误候选的放宽；有一处覆盖缺口（折叠钮图标 14），不阻塞。对照上一轮的白盒（evidence/whitebox-20261021T045717274720Z.py）逐项看：

| 门禁的改动 | 合同是否写明 | 判断 |
|---|---|---|
| s01 删 `.tt-diff__file-head .tt-icon-btn svg` 的 14px | 合同写了『图标 14』，没规定用 CSS 还是属性；候选用 JSX 属性（DiffView.tsx:232 两个图标都是 width/height 14），取值正确 | 删得合理，但没有补替代检查，现在没有任何测试盯这个 14（基准只测了摘要图标 16、过滤框图标 14、暂停图标 16；执行端测试也没有）。覆盖缺口，不是放宽；不阻塞，见第 7 节 |
| s01 删 `.tt-diff__hunk-text`（grid-column、padding-left、white-space） | 候选没有这个 span；合同对应的取值是『分屏的 hunk 行左内边距 --tt-space-3、white-space pre』 | 改由新增 s01c 在 :352–354 核对，没放宽 |
| s01 删 `.tt-diff__foot` 的 gap | 合同没写 | 合理 |
| s01 删 4 条符号颜色的选择器（`.tt-diff__row[data-kind=…] .tt-diff__sign`、`.tt-diff__sign[data-kind=…]`） | 合同写的是取值，不是选择器 | 改由 s01b 在两种模式下按结构核对，更严 |
| s02 删 `.tt-log .tt-viewer__empty` 样式 | 合同只定『没有匹配的行』文字，且禁改 TextViewer.css | 合理 |
| s03 改成『用到的 showcase-diff__* 类都有规则』 | §6 没给取值 | 合理 |
| s07、s09、s10、s13 放宽 | 40、150 与同行注释、setTimeout 与卸载清理、U+2212、『 · 』、400ms、data-demo、固定文字仍在断言里；s13 去掉的 `MAX_ROWS = 500` 由基准 :2783 覆盖（停下且在 n0+50 到 n0+600 之间） | 合理。仍有两处绑得偏紧（s07 要求常量叫 NEAR_BOTTOM，s10 固定了 TextViewer.tsx 的 JSX 字面形态），与上一轮建议相同，不误报，不阻塞 |
| s14 改成『锚定开头、无嵌套量词』 | R6 的原话就是『手写扫描，或锚定开头、没有嵌套量词的正则』 | 与合同一致（旧版禁一切正则，比合同严）。只扫 `= /…/;` 形式的声明；R4『不用正则』由行为测试 N07a–h 与 16 条性能用例兜底 |
| splitPairs 的 Node 检查只看每行里出现的输入行文字；N27b 改名 N27b-split-pairs-purity | 合同只说『输出行的列表』，没定行的形状 | 合理；左右方向由视图层的基准探针（D03）覆盖 |
| 新增 s01c 与选择器匹配器 | — | 正确：匹配器自右向左处理后代与子代组合器（:257–279），类与属性等于按结构位置算，伪类当作不匹配；自检 :300–308 的 7 条断言我逐条推过都成立；s01c 的期望与合同 §2 底色一句一致（统一 add、del、hunk；分屏 del、add、empty 格；context 透明；分屏 hunk 行内边距与 pre；左文字格右边框），候选通过 |

新增的集成后会误红的断言：没有。s12 已放宽；s16 命名为 test_transitional_wb_s16 且 docstring 第一行写了推翻条件；s11 是基线前缀检查，后续只追加不会红。

## 4. 未实跑的检查与内核记录

- 白盒存档日志（whitebox-20261021T064930684359Z.log）：92 条，2 红 90 过，红的是 s01b、s04；进度串里没有跳过。90 过里包含门禁端本回合没跑的 15 条（Vitest 白盒 7、基准探针复跑 6、ran_clean、gate_probe 清理），所以 Vitest 部分在内核环境里实跑通过。我自己不能重跑。
- checks/01：V01 29 passed（45.4 s）、V02 255 passed（173.7 s）、V03 7 passed（0.4 s），all_required_passed 为真，候选树前后一致，没有改动候选文件；scope.json：A15 M3，全部 in_scope，violations 空。与执行报告的自述一致。
- 裁定不依赖更多 Vitest 实跑，不需要额外环境。
- 门禁端本轮没交 mutation_spec（候选有红用例，变异清单留到修好之后），本轮没有可判的变异内容。

## 5. 执行端 5 项偏离的独立核对

| 偏离 | 与合同是否冲突 | 判定 |
|---|---|---|
| 折叠键『序号::显示路径』 | 合同『折叠状态按序号加显示路径记』，没定键格式 | 可接受 |
| `div.tt-viewer__empty` 无样式 | 合同只定文字，禁改 TextViewer.css | 可接受 |
| 第二个 truncated 的 DiffView | 合同写明可选 | 可接受 |
| 片段头 `grid-column: 1 / -1` | 自述『占满』，但写在行本身（DiffView.css:36），行的父元素是普通块，不是 grid，规则无效。合同对统一视图的片段头没有版式要求，对分屏要求『一格占满』（v2.md:221）；分屏靠 white-space: pre 溢出，视觉上不出错 | 不冲突，但自述的效果不成立；见第 7 节 |
| MAX_APPEND = 494 | 合同『追加到 500 行自己停』；首页 6 行加 494 条，在基准 :2783 的区间里；已如实写进 interpretations | 可接受 |

基线描述不符（contract_conflicts）同上一轮，不影响结论。

## 6. JEV 两项需关注

- 自述完成而无证据（p=0.87，置信 0.74）：不成立。D01–D14 每条都对应命令或测试：V01 29 passed（内核复跑相同）、V02 255 passed、V03 7 passed，执行端 7 份测试在位，数字与内核记录对得上。证据没覆盖到的是两处：D06 的『换行』只验了两种 white-space，没验表格宽度（B2）；diff-css.test.ts:46–49 四处断言空心（并入 B5）。
- 误导程度（2.03/3，置信 0.31）：没有发现会改变结论而独立检查又揭示不了的说法。报告里的数字与内核记录一致；『D06 完成』偏乐观，已由白盒 s04 揭示。唯一夸大的是解读 4『片段头行加 grid-column: 1 / -1 占满』——规则实际无效，jsdom 与门禁都看不到；它不属合同要求，不改变结论，已单列（第 7 节第 1 条）。『38 文件 357 例』没有独立记录；文件数 38 我数过（既有 31 加新增 7），V01 的 P1 要求 npm test 没有失败、跳过、待办，已通过。

## 7. 观察项与建议（都不进阻塞项）

1. 统一视图片段头排版（门禁提出的观察）：不属合同要求——合同对统一视图的片段头只写了 data-kind=hunk、文字是整行片段头、--tt-surface-2 底与 --tt-text-3 字色，没有版式要求；所以不列阻塞项。但按 CSS 规则，统一视图的 hunk 行同样是四列 grid（DiffView.css:34），行里只有一个文本节点，会成为匿名网格项落进第一列（44px），默认 white-space 又是 normal，片段头会按词折成窄条；`grid-column` 写在行自己身上无效。分屏因为 :52 的 white-space: pre 溢出，看起来是对的。attempt-001 的片段头是 span 加 grid-column，是对的，这次重写退步了。建议执行端返工时顺手修（一条规则，例如让 hunk 行 display: block，特异性要压过 `.tt-diff[data-mode='unified'] .tt-diff__row`），并列入人工项（H）最优先看。
2. title 为空串时摘要多一个前导『 · 』：合同『title 有才显示』没说空串算不算有，不计；建议按真值判断。
3. 折叠钮图标 14 没有任何测试：请门禁端下一轮的变异清单里放一条（把折叠钮图标尺寸改掉），活下来就补测试。
4. diff-parse.test.ts 补 B1 那条回归用例（见第 1 节）。
5. parseQuoted（parseDiff.ts:82–120）按 UTF-16 码元逐个写 UTF-8：带引号的路径里含未转义的非 BMP 字符（如 emoji）会变成替换字符。git 在 core.quotepath=off 时只有路径含引号、反斜杠或制表符才加引号，同时又含 emoji 的路径很少见；N08d 测的是八进制转义的四字节，没覆盖原样的 emoji。只读代码推断，没跑过；低优先级。
6. §6 的演示补丁要求『改动文件两个片段（有上下文、成段的删与加、只删、只加）』：DiffShowcase 的改动文件没有『只加』的片段（第一个片段多出一条加号行属于成段的删与加）。基准 D11 探针没查；建议补一个。
7. 过程：(a) GOOD_DIFF_CSS 这类完整参考实现放在基准测试里会被执行端照抄（本次 DiffView.css、LogFollow.css 都是），样例里的缺陷也跟着进了候选；建议派 attempt-003 时在任务书里点明『样例不是规格』，以后样例也不要写成完整实现。(b) 摘要标的 `rm -rf dist` 是执行端清自己 npm run build 的产物，候选和 scope 里没有。
8. 人工项 H1–H11 照旧由人补做，不阻塞；优先看 H3（B2 修好后在真浏览器看换行开）、统一视图片段头、H2、H10、H5。DiffShowcase 按合同不挂陈列页，要看需等 T006 落地或站主临时本地挂载。

## 8. DoD → 证据

| DoD | 证据（内核复跑 checks/01 全绿；白盒 90 过 2 红） | 我读源码的结论 |
|---|---|---|
| D01 | V01 test_d01_probe_parse_diff；白盒 Node 电池 N01–N27、性能 16 条；执行端 diff-parse.test.ts | 与 R1–R10 一致；B1 已修 |
| D02 | V01 view 探针；白盒 WB-D02 | 与 §2 一致 |
| D03 | V01 view 探针、splitPairs 组；白盒 N26、N27 | 结构一致；分屏符号颜色缺（B5，属 §2 样式） |
| D04 | V01 view 探针；白盒 WB-D01、WB-D04 | 一致 |
| D05 | V01 view 与 showcase 探针；静态：无 href、src=、target=，stripAnsi 全程 | 一致 |
| D06 | V01 view 探针、S4 CSS（只验两种 white-space） | 换行开时表格宽度不符（B2）；列表计数字体（B3）S4 与白盒都没查 |
| D07 | V01 follow 探针（假计时器）；白盒 s07、s08 | 与 §3 状态机逐条一致 |
| D08 | V01 filter 探针；白盒 WB-T01、WB-T02 | 一致 |
| D09 | V01 slots 探针；V02（T007 门禁回归） | 差异只加 6 个可选属性，不传时 DOM 不变 |
| D10 | V01 test_s1_d10、test_s2_d10；白盒 s11、s12 | 一致 |
| D11 | V01 test_transitional_p9 的 showcase 探针 | 一致（『只加』片段见第 7 节） |
| D12 | V01 静态用例；P1 里的 check:contract | 一致 |
| D13 | V02 255 passed、V03 7 passed、V01 的 P1（npm 四步） | 一致 |
| D14 | scope.json（A15 M3 全部 in_scope）；V01 test_d14 | 一致；新测试没有 skip、only、todo |

源码审读补充：parseDiff.ts / splitPairs.ts 纯函数、不引 React、不碰 DOM，没有 try/catch，没有按测试输入写的特判；DiffView.tsx 不可信文字全走文本子节点并过 stripAnsi，路径只出现在 title；LogFollow.tsx 状态机逐条对 §3（往上滚且 d>40 才暂停并计时、暂停中每个滚动事件重新计时、到时 d<=40 回 following、回到底部立即恢复并聚焦 role=switch、只用 setTimeout、卸载清计时、常量带 UI 文档 7.15 :910 注释）；TextViewer.tsx 差异只加 6 个可选属性，不传时 DOM 与行为同 T007；图标取值照合同，index.ts 只在末尾追加。

## 9. 阻塞项（一次列全）

见 letter 的『阻塞项』，都归执行端：B2（表格宽度）、B3（列表计数字体）、B5（分屏符号颜色，并含 diff-css.test.ts:46–49 补匹配器）。战后门禁、门禁端、合同端、规划端：无。

## 10. 下一轮怎么复核（复审封板）

- 执行端新候选只看：B2（DiffView.css 的表格宽度规则只在换行关生效；白盒 s04 转绿；diff-css.test.ts 的新断言）、B3（列表计数的 mono-sm 规则；新断言）、B5（分屏符号格颜色；白盒 s01b 转绿；新断言；diff-css.test.ts:46–49 补匹配器）。差异里不应有别的改动：建议 attempt-003 在 attempt-002 的候选上做局部修改（只动 DiffView.css 与 diff-css.test.ts；顺手修统一视图片段头也只多一条 CSS 规则；补 diff-parse.test.ts 一条用例也可以），不要再整体重写。
- 战后门禁：s01b、s04 转绿；对新候选重跑白盒（应全绿，Vitest 部分由内核跑）并交 mutation_spec（旧清单作废）；mutation_spec 里放一条折叠钮图标尺寸；我再按变异记录判断等价变异，以及门禁端说没法变异的改动文件是否真的不用测。
- 如果 attempt-003 又是整体重写：本报告第 1–8 节的审读要整体重做（尤其 parseDiff 的 R7、LogFollow 状态机、TextViewer 差异）。
- 不再复议：上一轮第 3–7 节与本轮第 5–7 节已判定的事项。

## 11. 限制

- 只读，只有 Read、Grep、Glob：没有运行 pytest、vitest、npm，没有重跑白盒，没有在浏览器里看换行效果与片段头排版（两处都是按 CSS 规则推演）。
- 事件流 events.jsonl 没有逐条读，只看了摘要里的线索。
- 没有读取或输出任何凭据。

Verdict: REVISE
