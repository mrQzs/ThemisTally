# 复审记录：t007-desktop-evidence attempt-002（七端信箱 hub）

- 合同：t007-desktop-evidence.v2（base a56eec8a7752dbca3d599aa5c794b6a5ed3ba6dc）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T007-7-audit-post 终审报告（audit-sonnet）· 第二轮（复审封板）

- 结论: 通过
- 对象: t007-desktop-evidence 合同 v2 · attempt-002（候选树 7a9fc6fd5f16，基线 a56eec8）；基准锁定 d9a1b7f536；执行端预算：合同上限 3 次，已用 2 次。
- 方法: 先读候选补丁与源码（工作目录即候选），再对合同 v2、白盒存档 whitebox-20261020T133720126648Z.py 及其日志、内核检查记录（checks/01、scope.json、observations.json）、门禁报告与内核变异记录。审核端没有执行类工具，本回合没有运行任何命令；V01–V03、白盒 91 条、合并命令 124 条、变异 29/29 都采信内核与门禁的记录。标「推演」的是读代码得出的判断，没有实测。
- 不在范围: H1–H9（暗亮色视觉、真浏览器剪贴板与滚动、Windows 高对比度、读屏、外壳接入后的链接确认、大文档手感）留给人。

## 1. 总判

上一轮的 B1–B8 全部解决，我对每一条都回到源码行、白盒断言、执行端回归用例和变异记录核了一遍（第 2 节）。本轮新改动我通读了，没有发现需要升格的新问题（第 6 节），所以没有阻塞项。门禁提的两件事：B5 反引号不算合同缺陷；M27 由执行端测试抓住算数（第 3 节）。

## 2. B1–B8 逐条复核

合同行号指 .agent/plans/t007-desktop-evidence.v2.md；锚点指候选文件（工作树即候选）。

| 项 | 结果 | 候选锚点 | 证据 |
|---|---|---|---|
| B1 行号关时左内边距 | 解决 | TextViewer.tsx:72-74（行号关时根上加 tt-viewer--no-num）；TextViewer.css:70-71（.tt-viewer--no-num .tt-viewer__text 左内边距 var(--tt-space-3)）；行号开时没有无条件规则，布局不变 | test_wb_s01（含类名与 tsx 字面量联动）、WB-V19；执行端用例「行号关掉时文字有左内边距…（返工 B1）」；变异 M01–M04 被抓 |
| B2 行内代码规则盖到代码块 | 解决 | SafeMarkdown.css:24-31 改为 .tt-md :not(pre) > code，取值一条没动；:32-41 的 .tt-md pre 仍是 mono-md、surface-2、1px border、radius-md、padding space-2、overflow-x auto、white-space pre | test_wb_s02、基准 test_s5_d03_safe_markdown_css_values；执行端用例（返工 B2）；M28、M29 被抓。真浏览器字体族见第 8 节观察 1 |
| B3 关提示条后钮恢复可点 | 解决 | TextViewer.tsx:67-68（showBanner 只管提示条）、:136 行尾 disabled={changed || loadingMore}、:154 底栏 disabled={changed}（loadingMore 时底栏走 Button 的 loading）；loadBusy 已删 | WB-V01、V02（StrictMode 循环）、V04；执行端用例（返工 B3：关闭后两处仍禁用，changed 变假才恢复，点一次调一次）；M05–M10 被抓 |
| B4 jsonl 分片逐片去 ANSI | 解决 | viewerLines.ts:85 改为 line.text += entry.text；:93-95 循环结束后对每行 stripAnsi 一次；text 模式 :57-:64 未动 | WB-V05（a+ESC+[3 与 1mb 得 ab，显示与复制一致）；执行端用例（返工 B4）；M25 被抓 |
| B5 缩进的围栏、标题截断列表 | 解决（反引号见 3.1） | markdown.ts:404-417：围栏/标题行先判缩进；从最深层向外找第一个缩进不小于项文字起始列的层，先收深层段落并截栈，再把去掉项文字列前缀的行并入该层段落，找不到才 break；惰性续行 :425-427 与块层「围栏、标题能打断段落」:489 未动 | WB-M01、M07、M08；执行端用例（返工 B5，四种形状）；基准列表、惰性续行、围栏、打断段落用例仍绿（V01 33 passed）；M11–M15 被抓 |
| B6 N 个 [ 共用 ]( 的平方时间 | 解决 | markdown.ts:156-177 nextSpaces 与 matchedCloseParens 各一次线性扫描；:186-189 只在出现 ]( 时才算；:267-281 每个 [ 只做 O(1) 查表，没有重扫 | WB-M02（128 KiB）、WB-M03（另外 14 种 256 KiB 形状）、基准 test_d03_probe_markdown_performance（合同列出的 7 种）都在 2 秒内；执行端用例用 384 KiB 限 2 秒。上一轮的联动提醒也满足：「[a]( 重复」没有变平方 |
| B7 带括号的网址不成链接 | 解决 | markdown.ts:270-278：链接成立当且仅当 ]( 的那个 ( 在栈配对里有 )，且 ) 在最近空白之前；javascript:alert(1)、data:text/html,f(1)、vbscript:msgbox(1) 配对后过不了 URL_RE，只剩链接文字；https://h/a_(b) 成链接 | WB-M06、M20、M21、M27、M28；执行端用例（返工 B7）；基准 13 种被拒网址与放行用例仍绿；M16–M24 被抓 |
| B8 演示露出 javascript 链接 | 解决 | EvidenceShowcase.tsx:94 的链接随 B7 只渲染「这一条被拒」；:197 说明文字改为「不安全协议的链接只留文字」 | WB-E05（收窄到 .tt-md：按钮数 1、不含 javascript:、含「这一条被拒」）；执行端用例（整节文字不含 javascript:、含「这一条被拒」）；M26、M27 被抓 |

## 3. 门禁提的两件事

### 3.1 B5 反引号：不算合同缺陷，不列阻塞项

- 复现（我手工追踪 parseList、closePara、parseInlines，未实测）：「- a」、缩进两格的三反引号围栏三行（开、x、关）、「- b」得一个 ul、两个 li；第一项是一个段落，文字「a」加换行后接一个 code 节点，内容是「换行 x 换行」，两处三反引号被行内规则配成代码段，围栏标记本身不显示。开头写了信息串（例如 bash）时，bash 会成为代码段内容的第一行。只有开头围栏、没有闭合围栏时，三个反引号是字面字符，照常显示。所有非标记字符都在，没有元素逃出允许集合，无安全后果。
- 依据:
  1. 合同 :252「项里只有段落与子列表」「其余语法都当段落文字」：项里的这些行就是段落行；段落文字过行内规则（:253 代码段：反引号串配同长度串）是合同自己的统一规则，不是执行端加的。基准里别的「原样当文字」用例（引用块、删除线、任务列表等）逐字相同，是因为输入里没有行内记号；含行内记号的文字同样要过行内规则。
  2. 合同没有写「原样」是否要绕过行内规则，也没给这类行单独的规则。要保留围栏记号就得新增规则，那是规划端改合同的事，不是执行端可以自选的。
  3. B5 的要求原文是我写的「并入项的文字」，执行端照做。复审封板的口径是新阻塞项只能来自本轮新改动或严重错误；把我自己要求的后果升格，等于改验收口径。
  4. 一致性反而更好：此前同一个项里缩进 1–3 格的围栏被移出列表、缩进 4 格以上的当续行文字（正是 B5 的缺陷），现在两种写法结果一致。
  5. 执行端在 interpretations 第 2 条已写明这个后果，没有隐瞒。
- 建议（不阻塞）：规划端在合同或下一片补一句预期，二选一：列表项里的围栏、标题行照行内规则处理；或保留记号原样显示。选后者是新工作（这些行要绕过行内规则）。

### 3.2 M27：算数，执行端的测试足够具体

- 事实：内核变异命令是白盒加基准合成的 W1。M27 被基准 test_d13_p1_pipeline_steps_pass 抓住：npm test 失败在 tests/evidence-showcase.test.tsx:144 的 expect(textOf(sec)).not.toContain('javascript:')，M27.log 里整节文字能看到说明文字「…；javascript: 之类的链接只留文字；…」。29 条变异在这条命令下全部 caught，unexpected 为空。
- 为什么算数:
  (a) 这条断言属于候选交付物（9 个文件之一）；它的存在由基准 test_d14_executor_tests_in_place 守住（8 份执行端测试在、无 skip/only/todo），npm test 由 test_d13_p1 在每次门禁里重跑，所以这个杀手不是一次性的。
  (b) 断言对象是整节可见文字，同时覆盖两个来源：B7 没修时渲染区露出的整段被拒链接，以及说明文字；配套的 toContain('这一条被拒') 防止靠删掉演示链接来通过。失败信息直接给出行号与全文。
  (c) 它杀死的是真实可观察的输出变化，不是靠对测试输入的硬编码。
- 两点保留（不阻塞）：它比合同严——合同没有禁止说明文字提到这个协议名，这条断言把「说明文字不写 javascript:」固化了（这是我在 B8 里要求改说明文字的结果），将来要写这个词需同步改这条测试；它区分大小写，大写开头的写法抓不住，对本演示无影响。另外 M26（被拒链接换成 https）不是它抓的，是 WB-E05（按钮数 1）抓的，两条各管一边。

## 4. 变异清单审查

- 版本: 内核实际运行的是 mutation-spec-20261020T133729946958Z.json（单命令 W1 = 白盒 + 基准，超时 300 秒，spec_sha256 c3bba17b…）。任务书列的 …130714706566Z 是上一版（W1/W2 分开、超时 60 秒），已被取代；我审的是新版。命令合并协调人已接受、内核核验通过，我不再裁定。
- 结果: baseline 绿（退出码 0，53.3 秒）；29 条 caught，missed 0，skipped 0，error 0；每条 count_found=1；files_left_modified 为空。
- 等价变异: 门禁声明没有。我逐条看了 29 条，没有一条行为等价（都改变可观察的输出、属性或 CSS 取值）。
- 「没法变异的改动文件」: 门禁声明没有。核对：6 个源码文件各至少一条变异被抓（TextViewer.css M01–M02；TextViewer.tsx M03–M10；markdown.ts M11–M24；viewerLines.ts M25；EvidenceShowcase.tsx M26–M27；SafeMarkdown.css M28–M29）；3 个测试文件不需要变异。
- 没纳入的: 性能类变异（把线性预算表改回每个 [ 重算）。可接受：WB-M02 在 attempt-001（平方实现）上实测 5.5 秒红、在 attempt-002 绿，已有前后对照；基准、白盒、执行端三处都有 2 秒上限用例。我读到的另一处未单独变异的细节是 stack.length = target + 1（截栈）：删掉它会让回到外层之后的续行把列表拦腰截断，执行端用例 afterSub（「- a」、缩进两格的「- b」、缩进两格的围栏三行、「- c」，要求 1 个列表、3 个 li）会红（推演）；不要求补。

## 5. 执行端解读与 JEV 需关注项

- 自行解读合同（p=0.96）: 执行报告 interpretations 4 条（B3 标题与要求句、B5 前缀去除、B1 类名、B2 选择器写法），contract_conflicts 与 unresolved_questions 均为 0。内核从事件流抓到的 6 处「歧义/矛盾」提及全部指向 B3 标题与要求句——那是我上一轮 B3 标题措辞不清（标题写的是缺陷现象，执行端一度读成期望），不是合同矛盾；执行端按合同「changed 真时两处都禁用」与我写的要求句实现，并列进了 interpretations 第 1 条。其余 3 条都在合同沉默处，与合同字面相容（:248 没规定钩子名；:257 没规定选择器写法；前缀去除与已有惰性续行 line.slice(top.contentCol) 一致）。我没有发现未列出的解读：B5 的找层规则、B6/B7 的括号配对都是我在阻塞项里写明的要求。
- 自述完成而无证据（p=0.88）: 不成立。D01–D14 每条都有内核或门禁的运行记录（第 7 节）。D04–D10 报「本轮未改」，证据是同一候选上的基准与白盒。执行端自报的 V01–V03 退出码是推断值（命令被管道掩盖），以内核 checks/01 为准（三条退出码都是 0），两者一致。
- 误导程度（1.94，低）: 一处不精确——B2 说明里「代码块靠 .tt-md pre 的 --tt-mono-md 继承」，字体族在真浏览器里不一定继承（第 8 节观察 1）；这条出自我自己提的方案。其余自述与证据一致。
- 弱化测试（p=0.04）: 不成立。observations.json：assertion_lines_added 47、removed 0，skip_markers_added 为空；3 份测试文件的补丁只有新增行；没有基准与白盒的改动；候选源码里没有 catch、没有特判。

## 6. 新改动审读

- 我通读了补丁全部行和周边代码，查了测试输入硬编码、空异常处理、为过测试写的特判、悄悄扩大范围：都没有。
- 范围: scope.json 9 个 in_scope、violations 为空；HEAD 仍为基线；无依赖变更。
- B5 分支: 手工追踪/推演了这些栈形状——围栏在子列表之后（回到外层）、围栏之后再来子项、有序列表 contentCol=3、缩进 3 的围栏落在 contentCol=4 的内层之外、找不到层时 break、空段落层。每行成本 O(层数 ≤ 8)，不影响 2000 行逐层缩进的性能形状。
- B6/B7: 括号栈只在出现 ]( 时算；未配对的 ( 不会吞掉后面的链接（后面的 ) 总是先配最近的 (）；括号不配对就不成链接，与 attempt-001 对括号不配对网址的结果一致；多行网址、含空白的网址不成链接（WB-M27）。网址里的反斜杠转义与代码段里的括号会被一起计入栈，与 attempt-001 一样不处理，不属于本轮要求。每个 [ 处的 src.slice 在 V8 里是共享视图，不是 N×M；WB-M02 实测通过佐证。
- B4: 隐藏行 text 为空串，stripAnsi 对它无影响；text 模式未动。
- 回归用例: B1–B8 每条都有（7 个新 it，B8 在既有用例里加 2 条断言），我逐条比对过，它们能被对应的变异杀死，不是空壳。

## 7. DoD → 证据 → 终审判断

| DoD | 证据（基准 / 白盒 / 执行端 / 内核） | 终审判断 |
|---|---|---|
| D01 | 基准 test_d01_probe_strip_ansi、test_d01_probe_w1_text_only；白盒 WB-V05（分片被转义序列切开仍得 ab）、WB-V12–V15；执行端用例 jsonl 分片先拼后去（返工 B4）；M25 | PASS：B4 已修，W1 样例成立 |
| D02 | 基准 test_d02_probe_pages_pieces_and_conflict；白盒 WB-V01（关闭提示条后仍禁用）、V02、V03、V04、V06–V11、V16–V19；执行端用例（返工 B3）；M05–M10 | PASS：B3 已修，分页、分片、隐藏行、409 都成立 |
| D03 | 基准 test_d03_probe_safe_markdown、test_d03_probe_markdown_performance、test_s3_d03_markdown_module_is_pure、test_s5_d03_safe_markdown_css_values；白盒 WB-M01–M08、M10–M14、M20–M28、test_wb_s02、test_wb_s04；执行端用例（返工 B2、B5、B6、B7）；M11–M24、M28、M29 | PASS：B2、B5、B6、B7 已修 |
| D04 | 基准 test_d04_probe_effort_pair、test_s5_d04_effort_pair_css_values；白盒 WB-S01–S04 | PASS（本轮未改） |
| D05 | 基准 test_d05_d06_d07_probe_atoms、test_s5_d05_d06_atom_css_values；白盒 WB-S10–S11 | PASS（本轮未改） |
| D06 | 同上；白盒 WB-S20–S23 | PASS（本轮未改） |
| D07 | 同上加 test_s4_d07_new_icons_match_contract；白盒 WB-S30–S32 | PASS（本轮未改） |
| D08 | 基准 test_d08_probe_table_keyed_current_row、test_s6_d08_table_css、test_s6_d08_table_tsx_no_scroll_into_view；白盒 WB-T01–T10、test_wb_s03 | PASS（本轮未改） |
| D09 | 基准 test_d09_probe_s5_and_gaps；白盒 WB-G01–G05 | PASS（本轮未改） |
| D10 | 基准 test_transitional_s7_showcase_forms_css_and_pill_row、test_s8_d10_showcase_forms_css_px_comments | PASS（本轮未改） |
| D11 | 基准 test_transitional_p9_evidence_showcase_probe；白盒 WB-E01–E07（E05 对应 B8）；执行端用例（整节文字不含 javascript:）；M26、M27 | PASS：B8 已修 |
| D12 | 基准 test_s1_d12_files_and_exports、test_s2_d12_no_forbidden_words_in_src、test_s3_d12_new_sources_rules、test_s5_d01_text_viewer_css_values、test_s5_d12_new_css_tokens_and_px_comments、test_s5_d12_w4_pitfalls_in_new_sources；npm run check:contract（含在 test_d13_p1）；白盒 test_wb_s01（B1）、test_wb_s02（B2）、test_wb_s04–s08；执行端用例（B1、B2） | PASS；真浏览器视觉（H1）只能人工审阅 |
| D13 | 内核 checks/01：V01、V02、V03 退出码 0（候选树 7a9fc6fd5f16，all_required_passed）；门禁 V02 229 passed、V03 7 passed；基准 test_d13_p1_pipeline_steps_pass、test_p10_d13_worktree_unchanged_by_pipeline | PASS |
| D14 | scope.json（9 个 in_scope，violations 为空）；observations.json（断言行删 0，无 skip）；基准 test_d14_executor_tests_in_place；补丁里没有 tests/test_gate_*.py | PASS |

## 8. 不升格的观察与给规划端的提示（均不阻塞）

1. （我上一轮提的方案留下的坑；推演，未实测）B2 选了 :not(pre) > code 之后，代码块里的 code 元素没有自己的字体规则。浏览器自带样式表对 code 设了 font-family: monospace，作用在 code 元素本身，会盖过从 pre 继承来的字体族——真浏览器里代码块文字可能用系统等宽字体，而不是令牌 --tt-font-mono；字号与行高仍继承 pre 的 --tt-mono-md。jsdom 测不到。这是我上一轮给的两条路之一，当时我没提这一点；属视觉层，归 H1。需要处理的话，加一条 .tt-md pre code { font: inherit; }（白盒 test_wb_s02 接受 pre code 设 inherit 或 mono-md）。
2. 演示里的小坑（B3 修复的后果，合同 :277 如此规定）：演示关掉提示条后，[继续加载] 仍禁用，而 [从头读取] 只在提示条里、「模拟文件已变化」只会置真，页面刷新前恢复不了。真实使用不受影响（changed 由调用方控制）；演示改版时处理即可。
3. 空行加子列表后回到外层缩进的续行（推演，未实测；非本轮改动）：「- a」、缩进两格的「- b」、空行、缩进两格的 more，空行后的判断用最深一层的项文字列（4），缩进 2 不够，列表在空行处结束，more 成了列表外的段落。合同「空行后若列表项或缩进够的行列表继续」没说按哪一层，建议规划端写明。
4. 上一轮第 6 节的观察（Banner 假值 action、pages=[] 显示一行行号 1、OSC 嵌 ESC、演示第 1 页少一个空行、pagesToLines 平方量级、Table 焦点跟随 effect、EffortPair 数组空串）本轮没有变化，仍不升格。

## 9. 给协调人的提示

- 白盒文件 tests/test_gate_t007_whitebox.py 随集成进仓库当回归测试；test_transitional_wb_s09_* 已按过渡断言标注（陈列页演示改版时推翻）；与基准合起来约 51 秒，需要 npm ci（联网）。
- 门禁上一份报告第 7 节提过合同 v2 的 base_sha 与 Repository facts 的 HEAD 可能不一致；我没有核对，仍请协调人知悉。
- 执行端预算：合同上限 3 次，已用 2 次，本次通过，无需第 3 次。

Verdict: PASS
