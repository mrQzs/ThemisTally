# 复审记录：t004-desktop-overlays attempt-003（七端信箱 hub）

- 合同：t004-desktop-overlays.v5（base 9f784056c5af4217835df20078abcacaae38178a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

候选：attempt-003（合同 v5，修了终审 B1 的返工版）。本报告覆盖 attempt-001 的终审报告（旧版内容在 .agent/reviews/t004-desktop-overlays/attempt-001-hub.md）。

# T004 终审（-7-audit-post，复审封板）

结论: 通过
阻塞项: 无

审核端 audit-sonnet，只读：没有运行命令、没有开浏览器。读了候选补丁与相关源码，核对内核的 checks.json、scope.json、observations.json、变异记录与白盒日志，并按关键字抽查了事件流。

## 0. 依据一句话
候选相对基线（9f78405，即 attempt-001 的候选，树 04047eea…，上一轮已审过）只有两处：Tooltip.tsx 两行条件改为无条件 hide()，icon-button.test.tsx 追加三条测试（+32/−0）。B1 闭合，本轮差异没有新问题；(d) 文档级、(e) 为 H1 目视项，均不阻塞。

## 1. B1 是否闭合：闭合
逐条对上次阻塞项：
- 位置一 Tooltip.tsx:54–57 onMouseLeave：现在是 hoveringRef.current = false; hide();（无条件）。通过。
- 位置二 Tooltip.tsx:63–66 onBlur：现在是 focusedRef.current = false; hide();（无条件）。通过。
- Esc 判断未改：补丁里 Tooltip.tsx 只有两个 hunk（candidate.stat：+2/−2）；onKeyDown（:70–78）与 onDocKeyDown（:80–86）没有动，hoveringRef、focusedRef 仍被后者读取，没有变成死状态。通过。
- 补测三条（icon-button.test.tsx:56–86）与阻塞项 (1)(2)(3) 逐步相同，沿用 mount 与 advance，fireEvent 取自 @testing-library/react，没有 waitFor、skip、only、todo。我按旧实现手推：
  (1) :56 聚焦后悬停 400ms 可见；移开时旧代码因 focusedRef 为真不 hide，:63 的 toBeNull 红。
  (2) :67 悬停 400ms 可见；聚焦再失焦，旧代码因 hoveringRef 为真不 hide，:74 红。
  (3) :77 聚焦后悬停 200ms 移开，旧代码不清计时器，再推 500ms 到点出现，:85 红。
  新代码下三条都过。两处回退各自单独也会被抓：onMouseLeave 回退红 (1)(3)，onBlur 回退红 (2)。
- 执行端自己反测过：事件流 :598 的命令把两处临时改回旧条件，输出 :603 为「3 failed | 6 passed (9)」，失败位置 :85 在第三条；同一条命令末尾 mv 还原并 rm .orig，grep -n "hide();" 打出 56、65、74、83，说明还原后两处是无条件 hide()；之后全量 npm test 75 passed（:680）。changes.json 只有两个 M，没有 .orig 残留。
- 门禁端独立证据：白盒 WB106–WB112 七条并存场景都过；内核变异 M16（B1a，回退 onMouseLeave）被 WB106、107、108、110、111、112 抓住，M17（B1b，回退 onBlur）被 WB109 抓住。我读了两份日志，失败是「expected <div class=tt-tooltip …> to be null」的真断言失败，不是语法错误带来的空红。
- 范围：scope.json ok=true，两个文件都是 M 且 in_scope，violations 0、warnings 0，head_after=基线。我另对了合同 v5：两个文件都在 allowed_modified_files（:59、:65），不在 forbidden_paths。attempt-002（合同 v4）曾因这两个文件的 M 不在允许集合被标越界 2，v5 已列入，本候选 0 越界。observations.json：skip_markers_added 空，assertion_lines_added 7（三条测试的 expect 数），assertion_lines_removed 0，main_repo_changed=false。
- 内核检查（checks/01，mode=fresh，候选树 fc8101777f2b…，检查前后树相同，modified_by_checks=false）：V01 22 passed、V03 7 passed、V02 170 passed，日志全是点，没有 s、x、F。V01 的 P1 在 fresh 工作区里跑了 npm ci、build、test、check:contract，且 npm test 没有失败、跳过、待办。
- (c) 悬停与聚焦并存：随 B1 关闭。

## 2. (d) 尺寸字面量 16：文档级，不阻塞
- IconButton.css:18 的 16px：合同第 2 条明写「图标 16」，而图标组件缺省是 24（icons/index.tsx:8），所以这条规则是合同要的；缺的只是出处注释。合同公共约定的清单没列 16，是合同自身的松动，不是执行端违约。
- Toast.css:35 的 16px：多余。Toast.tsx:78、:89 已经用 width、height 属性给图标写了 16；画布里关闭钮图标是 14（写操作页 :422）。
- 没有行为后果，基准、白盒、执行端测试都不断言。上一轮已判文档级，本轮返工范围又明确限定两个文件，这里不升级。建议 T005 顺手：IconButton.css:18 加一行出处注释（组件板 :340 图标 16），Toast.css:35 删掉或加注释。

## 3. (e) base.css 特异性：不阻塞，留 H1
- 推断（由 CSS 文本，未在浏览器验证）：base.css:12 的 `.tt-app button, … { font: inherit; color: inherit; margin: 0 }` 特异性 (0,1,1)，高于单类规则 (0,1,0)，与引入顺序无关。所以 `.tt-icon-btn`（IconButton.css:10）、`.tt-toast__close`（Toast.css:30）默认态的 color 会是继承值（通常是 --tt-text-1），不是 --tt-text-2；悬停 (0,3,0)、禁用 (0,2,0) 的规则更特异，不受影响。这两个按钮里没有文字，字体不涉及。工具提示、轻提示本体、菜单、对话框本体都是 div，不受影响。
- 为什么不阻塞：一，它是系统性遗留，T002 的 Button（.tt-btn--* 的 color、font）是同款写法，不是 B1 返工引入的；二，候选 CSS 符合合同写的样式，合同又禁改 base.css，执行端无路可走；三，后果是两类按钮静态颜色比画布深一档，对比度更高，没有功能、无障碍后果；四，jsdom 看不到层叠，只有浏览器能验。
- H1 要看的：DevTools 里图标按钮默认态的 computed color（应为 --tt-text-2）、轻提示关闭钮同；顺带看 T002 主按钮的字色（--tt-on-primary）与字重（medium）。被盖掉就起一个小任务（基础重置降到 :where()，或提高组件选择器特异性），不在 T004 里。

## 4. JEV 三条关注
### 4.1 自述完成而无证据（p=0.94）：不成立，薄在写法上
D01–D11 逐条对应到内核记录或测试，见 §7。没有 DoD 缺自动化证据；D01 在 attempt-001 缺的「并存时移开、失焦」这一句，本轮由三条新测试、基准 P2、白盒 WB106–WB112 补上。执行报告自身偏薄的地方：D02–D05、D07、D08 只写「本轮未改，既有 X.test.tsx N 项通过」，没贴命令输出；我数了测试文件的 it 个数（menu 4、dialog 7、drawer 4、toast 6、status-tag-patches 4、showcase-overlays 6）与报告相同，整套 75 passed 在事件流 :680，内核 fresh 复验（V01、V02、V03）一致。只能人工的部分是合同的人工验收项 H1–H6，以及 D08 里「能手动打开」的真浏览器部分。

### 4.2 误导程度（2.66/3）：不成立，没有隐藏冲突、越界或弱化测试
- 冲突：报告写 contract_conflicts、interpretations、unresolved_questions 都为 0。本轮改动没有自行取舍的余地：上次阻塞项把改法与三条测试都写死了。
- 越界：scope.json 0 违规。内核标的「可疑命令」（mv -f、rm -f Tooltip.tsx.orig）就是 AGENTS.md 允许的临时反测写法（备份在工作目录内，同一条命令里还原并删备份），还原后的文件内容与 changes.json 都核过。
- 弱化测试：icon-button.test.tsx 只增不减（+32/−0），assertion_lines_removed 为 0，没有 skip 标记。
- 报告偏薄或措辞不准的三处，不改变结论：一，「遗留：无」只覆盖本轮返工项，上轮已裁定的 (a)(b)(d)(e)、R2 没有重复（它们在上次的终审记录与本任务书的「已裁定」里）；二，「还原后重跑 9 passed」并不是还原后单独再跑一次 icon-button，还原后的证据是同一条命令的 grep 输出与整套 npm test 75 passed；三，npm 命令用管道 tail 没加 pipefail，reported_exit_code 是推断值（内核已提示），以内核 check 为准。

### 4.3 自行解读合同（p=0.14）：「解读：无」属实
本轮差异只有 B1 指定的两处条件与三条测试，没有合同未写死而需要自己定的地方。上一轮的三条解读（tone、轻提示关闭钮、菜单点击选中）属于基线，已裁定，站主也已就 (b) 决定。

## 5. 门禁端的偏离
- 白盒重写、没有逐条对照旧文件：这是风险，但有客观补偿。内核变异清单 153 条（上次 140 条原样保留 + 新增 13 条）全部针对重写后的白盒跑过：caught 152、missed 1、skipped 0、error 0，unexpected_missed、unexpected_caught、files_left_modified 都为空；153 份日志都有 pytest 汇总行，没有超时，同时红得最多的一条是 17 条（没有整体崩溃式的空红）；我抽读 M16、M17、M101 都是真断言失败。上次 140 条里每条非等价变异仍被抓，说明重写没有丢掉清单覆盖的强度。
- 手动只跑 26 条：以内核结果为准，已核对。
- 唯一漏网 M126（F1，button:not([disabled]) 改成 button）：门禁端声明等价。复核成立：focusable.ts:6 是选择器，:16 的第二道筛 !el.hasAttribute('disabled') 对选择器选中的每个元素再筛一遍，所以去掉 :6 的 :not([disabled]) 只会让带 disabled 的 button 先被选中再被筛掉；querySelectorAll 返回文档顺序，与选择器列表顺序无关；经 fieldset 禁用的按钮没有 disabled 属性，两种写法都包含。没有输入能区分两者。（input、select、textarea 的 :not([disabled]) 同理冗余，门禁端没建变异，不影响结论。）
- 内核对 B1a、B1b 的「只插入新代码」警告：这两条插入的是 if (focusedRef.current) return; 这类提前返回，确实改变行为，且都被抓住，警告可忽略。
- 没有「门禁端举证的候选缺陷」一节；门禁记录也写「候选缺陷：无」。
- 本轮没有门禁端声明「没法变异」的新改动文件；上轮提过的两处（Dialog 的空列表分支、useOverlayFocus 的守卫）代码未动，上次裁定不变。

## 6. 执行报告的局限
「人工验收项 H1–H6 按合同不由执行端代做，未运行」是合同原文（合同 v5「人工验收项（H1–H6，不由门禁或执行端代做）」），不是遗漏。H1–H6 没有人做过，都不算通过，站主在结项时做。

## 7. DoD → 证据（本候选）
| DoD | 证据 | 缺口 / 只能人工 | 结论 |
|---|---|---|---|
| D01 | V01：S1、S6、P2；icon-button.test.tsx 9 条（:56–86 为本轮并存三条）；白盒 WB101–WB118；变异 M16、M17 | 位置与配色看 H1 | 成立 |
| D02 | V01：S1、S6、P3；menu.test.tsx 4 条；本补丁未动 Menu 相关文件 | 真浏览器键盘 H2；点击选中仍无仓库内测试（建议类） | 成立 |
| D03 | V01：S1、S3、S6、P4；dialog.test.tsx 7 条；未动 | 点遮罩后 Tab、Esc 后焦点环 H2；560 不溢出 H5 | 成立 |
| D04 | V01：S1、S4、P5；drawer.test.tsx 4 条；未动 | H1、H2、H5 | 成立 |
| D05 | V01：S1、S5、P6；toast.test.tsx 6 条；未动 | H1 | 成立 |
| D06 | V03 7 passed（内核 fresh）；V01：S7 | 无 | 成立 |
| D07 | V01：S2、S6、P7；status-tag-patches.test.tsx 4 条；未动 | 圆点位置与描边 H1 | 成立 |
| D08 | V01：P8；showcase-overlays.test.tsx 6 条；未动 | 真浏览器手动打开 H1、H2 | 成立 |
| D09 | V02 170 passed（fresh）；V01：P1（npm ci、build、test、check:contract 全 0，npm test 无失败、跳过、待办） | 无 | 成立 |
| D10 | scope.json（M2、A0、D0、违规 0）；V01：P9；补丁文件清单 | 无 | 成立 |
| D11 | 补丁：测试文件只增不减；observations：skip 标记 0、断言删除 0；V02 内 test_d03_new_tests_not_skipped；我 grep tests/ 无 skip、only、todo、xit | 无 | 成立 |

## 8. 候选源码审读（本轮差异）
- 没有迎合门禁的写法：差异里没有按测试输入写的特判、没有空的异常处理、没有硬编码。
- 副作用推演：hide() 幂等（clearTimer、visibleRef 置 false、setVisible(false)），本来就没显示时无条件调用是空操作；卸载仍清计时器（:92）；StrictMode 下两遍 effect 不受影响。提示是 pointer-events: none（Tooltip.css:16），鼠标不会「移到提示上」，所以没有「移开触发元素却想留住提示」的合理场景。
- 行为后果（合同如此，不是缺陷）：键盘聚焦出现的提示，鼠标只要经过再移开就会消失，直到重新悬停或重新聚焦；见 R6。

## 9. 风险与登记（供站主做 T005 登记与结项目视）
- R1（已决定，T005）：Dialog.tsx:57 遮罩 mousedown：只在 e.target === e.currentTarget 时 preventDefault，并补断言（框内 mouseDown 返回 true、遮罩本身返回 false）。
- R2（H2 会遇到，合同如此）：对话框、抽屉打开后焦点落在头部关闭钮，超过 400ms 弹出「关闭（Esc）」，第一次 Esc 只收提示，第二次才关浮层。H2 测「Esc 后焦点回触发按钮」时超过 400ms 请按两次。
- R3（H1）：(e) 的 computed color / 字重，见 §3。
- R4（已决定，T005）：轻提示关闭钮没有工具提示。H1 小项：关闭钮圆角（md，画布 sm）与图标 16（画布 14）；Menu 触发钮是 primary，陈列页其余触发钮是 secondary。
- R5（推演，未验证）：菜单面板是原地绝对定位（合同如此），放进对话框体会被 .tt-dialog__body 的 overflow: auto 与 .tt-dialog 的 overflow: hidden 裁掉；T005 在对话框里放菜单前要先处理。
- R6（B1 的后果，H2 留意）：见 §8。
- R7：H1–H6 无人做过，都不算通过。
- 建议类，不阻塞（T005 顺手）：(d) 的出处注释；menu.test.tsx 补一条点击选中；Tooltip.tsx 的 suppressedRef 只写不读（:22、:51、:60、:75、:84），可删；Tooltip.tsx:98–100 的 cloneElement 会把子元素自带的 aria-describedby 覆盖成 undefined；IconButton.tsx:23 的 {...rest} 在 aria-label 之后，调用方可覆盖名称；focusable.ts:2 注释里「与门禁探针一致」的字样建议改写。

## 10. 过程说明
- 我只有读取类工具：没有运行命令、没有开浏览器，没有通读 events.jsonl（按关键字抽查了 :188、:400 的两次编辑、13 条 bash 命令的头部、:598–:604 的反测）。结论依据是源码、补丁、内核记录。
- 无写权限，没能把上一版 report.md 复制成 report-attempt-001.md；旧版内容已存在 .agent/reviews/t004-desktop-overlays/attempt-001-hub.md，请协调人确认内核是否已归档（同目录有 brief.1.md，疑似按惯例归档成 report.1.md）。
- 本报告也请协调人落到 .agent/reviews/t004-desktop-overlays/attempt-003-hub.md（我没有写权限）。

Verdict: PASS
