# 复审记录：t004-desktop-overlays attempt-001（七端信箱 hub）

- 合同：t004-desktop-overlays.v3（base e4b6955de3fca840a8179f2be66c097994128848）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T004-7-audit-post 终审报告（attempt-001 · 合同 t004-desktop-overlays v3）

结论: 返工
退回: 执行端
阻塞项: 1 条（B1，见 §0）

- 对象：候选补丁 attempt-001（候选树 04047eea3108…，30 个文件，A23 M7 D0 T0，补丁约 1950 行）；合同 v3（base e4b6955de3fc…）；战前基准 22 条、T001–T003 回归 170 条、V03 共 7 条（W5 的 4 条加 tests/test_attempt_states.py 的 3 条）、战后白盒 80 条、140 条变异的内核记录。
- 方式：只读（Read、Grep、Glob），没有运行任何命令；V01、V02、V03、白盒、变异的结果引自内核与门禁的记录。时间是推算值（工具里没有时钟）。candidate.patch 读了全文，正文引用的行号都在工作区文件里核对过。
- 一句话：实现总体忠实于合同，范围干净，D01–D11 都有独立证据；但工具提示的「移开、失焦」在悬停与聚焦并存时不消失，违背合同第 3 条与 D01，在陈列页里「悬停、点图标按钮、移开」就能看到。这个场景没有任何测试覆盖，所以全绿没有拦住它。其余事项（门禁端 (a)(b)(d)(e)、执行端四条偏离）都不阻塞。

## 0. 阻塞项（原样可发）

B1 工具提示在「悬停与聚焦并存」时，移开、失焦不消失（违背合同第 3 条与 D01）
- 位置：desktop/web/src/components/Tooltip.tsx 第 54–57 行 onMouseLeave 里的 `if (!focusedRef.current) hide();`（:56），第 63–66 行 onBlur 里的 `if (!hoveringRef.current) hide();`（:65）。
- 合同条款：第 3 条「移开、失焦立即消失并取消计时」；D01「移开、失焦、Esc 都让它消失」。两句都没有「另一边还在就不消失」的例外。
- 现象：陈列页图标按钮演示里，悬停 400ms 出现提示 → 点按钮（Chromium 里点按钮会让它获得焦点）→ 鼠标移出：提示留在原地，直到按钮失焦。计时中（例如悬停 200ms 时点击）移开，提示仍会在到点后出现，计时没有被取消。
- 期望：onMouseLeave 清掉 hoveringRef 后无条件 hide()；onBlur 清掉 focusedRef 后无条件 hide()。Esc 相关的判断（onKeyDown、onDocKeyDown 里对 hoveringRef、focusedRef 的使用）不要改。
- 补测：在 desktop/web/tests/icon-button.test.tsx 里增加三条，沿用文件里的 mount 与 advance：(1) fireEvent.focus 后 fireEvent.mouseEnter，advance(400) 后可见；fireEvent.mouseLeave 后立即没有 role=tooltip，按钮上没有 aria-describedby；(2) fireEvent.mouseEnter，advance(400) 后可见，再 fireEvent.focus、fireEvent.blur，立即没有 role=tooltip；(3) fireEvent.focus 后 fireEvent.mouseEnter，advance(200)，fireEvent.mouseLeave，再 advance(500)，仍没有 role=tooltip。三条在现有实现上都应失败，改后通过。
- 范围：只改 Tooltip.tsx 的这两处与 icon-button.test.tsx；不改基准测试，不动其它文件，不改其它行为。

## 1. 门禁端提的 (a)–(e)：逐条裁定

- (a) 遮罩的 mousedown 冒泡：字面符合合同，不构成候选缺陷，不进阻塞项；作为 T005 风险交站主（§7 R1）。
  合同第 5 条原文是「遮罩上 mousedown 阻止默认（点遮罩不把焦点移走）」；候选把处理器挂在 .tt-dialog-scrim 上（Dialog.tsx:57），字面成立；基准 P4 对遮罩本身触发 mouseDown 并要求返回 false，白盒 WB44 同样，都过。副作用是框内任何位置的 mousedown 冒泡上来也被阻止默认：对话框是遮罩的子元素，合同没写「只拦遮罩本身」，这是合同措辞留下的缺口，不是执行端违反了合同里的哪一句。本片的对话框内容只有文字与按钮，没有可见症状。我不能以字面不违背的事为由打回；站主若希望本轮一并改，请规划端在返工合同里补一句，见 §8-1。
- (b) tone=info 的图标：合理解读，执行端已在 interpretations 申报；不阻塞，请站主确认取舍。
  合同第 7 条「只管图标颜色，缺省 success，图标 circle-check」可读成两种：所有 tone 都用 circle-check（只换颜色）；或缺省情形配 circle-check。前一种更贴「只管图标颜色」的字面，候选取了后一种，info 配 InfoIcon（Toast.tsx:71）。画布（组件板 :431–432、写操作页 :420）只有 success 轻提示，没有 info 轻提示可对照；陈列页只用缺省 success，info 没有使用点；基准 P6 与白盒 WB90 只断言缺省与 success 是 circle-check。和 (c) 的区别：(b) 有两种成立的读法、已申报、无使用点、无行为后果；(c) 的句子没有例外、没申报、陈列页上直接可见。
- (c) 悬停与聚焦并存：违背合同，成立为候选缺陷 → 阻塞项 B1，退回执行端。
  依据见 §0。补充三点：一，Tooltip.tsx:56、:65 是执行端自加的条件，合同和 D01 都没有；二，基准 P2 每次只用一种触发，白盒报告说明为避免过度断言去掉了这条，执行端测试也没写，整个仓库里没有任何测试挡住它；三，提示是固定定位，位置按渲染时的矩形算（Tooltip.tsx:94–96），提示留着时触发元素之后滚动或移动，提示不会跟着走。执行端没有把这个选择写进 interpretations。
- (d) 尺寸字面量 16：不阻塞；文档级瑕疵，建议顺手补（§8-2）。
  IconButton.css:18 与 Toast.css:35 的 16px 没有出处注释。合同清单没有 16，但第 2 条明写「图标 16」，所以 IconButton 的 16 是合同要的，缺的只是行内出处；Toast 关闭钮的 16 没有出处（画布的关闭钮图标是 14：写操作页 :422、组件板 :431），而且 Toast.tsx:78、:89 已经用 width、height 属性写了 16，CSS 这条是多余的。没有行为后果，基准与白盒都不断言。
- (e) 特异性：H1 目视项，兼系统性遗留；不构成候选缺陷。
  base.css:12 的 `.tt-app button, … { font: inherit; color: inherit }` 特异性是 (0,1,1)，高于 .tt-icon-btn、.tt-toast__close（以及 T002 的 .tt-btn--*）的单类规则 (0,1,0)，与引入顺序无关；所以按 CSS 文本推断，这些按钮默认态的 color 与 font 会是继承值（带 :hover、:disabled 的规则特异性更高，不受影响）。候选的 CSS 逐字符合合同写的样式；base.css 是合同禁改的文件；jsdom 看不到层叠；视觉验收合同交给 H1。这是由 CSS 文本推断的，我没有在浏览器里验证。H1 时在 DevTools 看图标按钮默认态的 computed color：应是 --tt-text-2，若是 --tt-text-1 就是被盖了。T002 的 Button 是同款写法，若当时目视没发现问题，请以浏览器为准，我的推断可能漏了别的规则。要处理，需要一个允许改 base.css（基础规则降到 :where()）或提高组件选择器特异性的小任务，不在本片返工里。

## 2. 执行端四条偏离的裁定

1. tone 解读：见 (b)，合理解读，不阻塞。
2. 轻提示关闭钮做成 24px 普通按钮、aria-label 为「关闭提示」：合理。合同第 7 条把 24 单列，IconButton 只有 28、32 两档，按 IconButton 做反而要加第三档。两点留给站主与规划端：(i) 合同第 2 条引的 UI 文档 7.2 要求只用图标的按钮有工具提示，这个关闭钮只有 aria-label；合同第 7 条没要求、门禁没断言，要补需另出合同。(ii) 画布的关闭钮圆角是 --tt-radius-sm、图标 14，候选是 --tt-radius-md、16，合同没写，H1 看。
3. 菜单点击选中：超出合同（合同只写键盘路径），但不违背合同、不削弱任何断言；菜单点不动才是缺陷，合理，不是候选缺陷。仓库内没有对应测试：menu.test.tsx 没有点击用例，基准也没有；白盒 WB26 是证据、不入库。建议补一条（§8-3）。
4. npm ci 提示：已核实，非阻塞。内核在全新工作区（checks.json 的 mode=fresh）里跑的 V01、V02 都通过，V01 的流水线包含 npm ci、build、test、check:contract。

## 3. JEV 关注的核实

- 自行解读合同（p=0.96）：部分属实。interpretations 有 3 条（tone、关闭钮、点击选中），加上 limitations 里的 npm ci 提示，与 summary 说的「4 处」对得上。未申报且有实质后果的只有一条：Tooltip 的「并存时不消失」（B1）。其余没列的选择（Toast 关闭钮的圆角与图标尺寸、Menu 触发钮用 Button 缺省的 primary 变体、Esc 抑制标志）属实现细节，按 AGENTS.md 不要求申报。
- 自述完成而无证据（p=0.88）：不成立。D01–D11 每条都对应到命令或测试（§4），报告里的 22 / 170 / 7 与内核 checks.json 逐个相同。唯一证据不足的是 D01 里「移开、失焦」在并存场景的那一句，没有任何测试，正是 B1。报告里「npm test 72 passed」是管道取尾的自述，内核没有单存；P1 在 fresh 工作区复核了 npm test 没有失败、跳过、待办，不影响结论。
- 超出范围（p=0.28）：不成立。scope.json：30 个文件全部 in_scope，violations 与 warnings 为空，head_after 等于 base。我逐条对了合同允许清单：改的 7 个、新增的 23 个都在清单内；App.css 允许但没改；package.json、锁文件、tokens.css、base.css、main.tsx 都不在补丁里。
- 弱化测试（p=0.05）：不成立。既有测试文件没有 M 或 D；新增的 7 个 vitest 文件与 W5 里没有 skip、only、todo、xit、xfail（我 grep 过）；没有断言被放宽。沾边的只有 focusable.ts:2 的注释「选择器与门禁探针一致」：选择器是通用的可聚焦列表，不是按测试输入的特判，建议改写注释（§8-4）。
- 误导程度（1.78/3）：报告里的数字都与内核记录一致；不全的只有上面那条未申报的选择，以及「遗留问题：无」。

## 4. D01–D11：DoD → 测试 → 断言

行号指 tests/test_gate_t004_baseline.py；S1–S7、P1–P9 沿用合同第 12 条与基准 docstring 的编号。

| DoD | 证明它的测试与断言 | 缺口或只能人工 | 结论 |
|---|---|---|---|
| D01 | S1 test_d01_components_exported（:1731）；S6 test_d07_layer_and_dot_css_tokens（:1772，Tooltip 底、字、z-index）；P2 test_d01_probe_icon_button_tooltip（:1841，10 条：aria-label 等于 label、type=button、svg aria-hidden、按钮无文字；悬停 399ms 无、400ms 有且 aria-describedby 指向、移开立即消失；计时中移开取消；聚焦同样、失焦消失；悬停 Esc、聚焦 Esc（消费）、计时中 Esc；tooltip 属性；挂载层与 tt-fc；单独 Tooltip 与卸载）；执行端 icon-button.test.tsx 6 条 | 悬停与聚焦并存时的「移开、失焦」没有任何测试 → B1 | 并存场景除外，成立 |
| D02 | S1；S6（Menu z-popover）；P3 test_d02_probe_menu_keyboard（:1849，6 条：aria-haspopup、aria-expanded、aria-controls、aria-labelledby、tt-fc、tabindex=-1；焦点在第一项、再点关；方向键循环与 Home、End；Enter 调 onSelect(b) 一次、菜单消失、焦点回触发钮、aria-expanded=false；Esc 关闭、回焦、不调 onSelect、外层收不到 Escape；菜单外 mousedown 关、菜单内不关）；执行端 menu.test.tsx 4 条 | 点击选中（偏离 3）没有仓库内测试 | 成立 |
| D03 | S1；S3 test_d03_dialog_css_and_scrim（:1753，560、max-width、radius-xl、shadow-3、scrim 固定四边 0、z-dialog、scrim 底色）；S6；P4 test_d03_probe_dialog_w6（:1857，10 条：open=false 不渲染；role、aria-modal=true、aria-labelledby 指向 h2、类名；遮罩与框在 body 下的挂载层；焦点进第一个可聚焦元素（关闭（Esc））；末元素 Tab 回首、首元素 Shift+Tab 到末且 preventDefault；Esc 一次 onClose、回焦、不外传；关闭钮；遮罩 mousedown 被阻止默认且点遮罩不关；卸载回焦；StrictMode）；执行端 dialog.test.tsx 7 条 | 只能人工：点遮罩后 Tab 仍在框内、Esc 后焦点环（H2）、宽 560 不溢出（H5） | 成立 |
| D04 | S1；S4 test_d04_drawer_css_geometry（:1760，520、max-width 60%、固定、right 0、bottom 取 tabbar、z-drawer）；P5 test_d04_probe_drawer_nonmodal（:1865，8 条：open=false；role、aria-modal=false、labelledby、类名、无遮罩；挂载层；焦点进入；Tab 两端不拦；Esc 关闭回焦不外传；外点不关与关闭钮；StrictMode）；执行端 drawer.test.tsx 4 条 | 顶边不断言（合同如此） | 成立 |
| D05 | S1；S5 test_d05_toast_css_position（:1766，固定、right、bottom calc、z-toast）；P6 test_d05_probe_toast_timing（:1872，8 条：常驻 role=status 与 aria-live；可见时图标 aria-hidden、关闭提示；4999 无、5000 一次；3000ms 移入暂停、移出后 2000ms；关闭钮立即；重开重计 5000ms；卸载清计时；tone 缺省 success、info 都显示）；执行端 toast.test.tsx 6 条 | tone=info 的图标没有断言（(b)） | 成立 |
| D06 | S7 test_d06_w5_passes_and_catches_changes（:1786：子进程跑 W5 通过；tmp_path 最小副本原样通过；两边各删一个、各加一个状态四种改法都失败）；V03 7 passed；W5 自带解析器自检（多一个、少一个、注释假键、展开、计算键、重复、缺声明、空） | 无 | 成立 |
| D07 | S2 test_d07_infra_failure_icon_is_server_crash（:1741，ServerCrashIcon 在、ServerIcon 不在、路径等于令牌板、INFRA_FAILURE 用它）；S6（圆点令牌）；P7 test_d07_probe_status_patches（:1879，4 条：中小号恰一个圆点、aria-hidden、无文字、在 svg 之后；第一个 svg 是 badge-check、文字不变、包在 tt-status__icon；其余 16 与未知码无圆点；INFRA_FAILURE 路径）；执行端 status-tag-patches.test.tsx 4 条 | 圆点位置与描边的外观只能 H1 | 成立 |
| D08 | P8 test_transitional_d08_showcase_overlay_demos（:1885，6 条：5 节顺序；无文字按钮都有 aria-label；菜单、对话框、抽屉、轻提示各自能打开）；执行端 showcase-overlays.test.tsx 6 条 | 「能手动打开」在 jsdom 里用 click 模拟，真浏览器看 H1、H2 | 成立 |
| D09 | P1 test_d09_pipeline_steps_pass（:1829，npm ci、build、test、check:contract 退出 0，Tests passed 且无失败、跳过、待办）；V02 170 passed（内核 fresh 复验） | 无 | 成立 |
| D10 | scope.json（ok，violations 空，A23 M7 D0 T0）；P9 test_d10_worktree_unchanged_by_pipeline（:1894，package.json、锁、tokens、base、main、index.html、vite、tsconfig 摘要前后不变）；补丁文件清单里没有这些文件 | 无 | 成立 |
| D11 | scope.json 既有测试无 M、D；V02 内 T002 的 test_d03_new_tests_not_skipped；我 grep 7 个 vitest 文件与 W5：无 skip、only、todo、xit、xfail | 无 | 成立 |

## 5. 候选源码审读（全绿不等于对）

- 没有迎合门禁的写法：src 下搜 gate、门禁、probe、探针、whitebox、baseline、基准、@ts-ignore、@ts-expect-error、eslint-disable、TODO、FIXME、process.env、import.meta.env、NODE_ENV、any，只命中 focusable.ts:2 那句注释。没有空的 catch；没有按测试输入写的特判；固定文案（「关闭（Esc）」「关闭提示」）都是合同写定的。
- 焦点返回与 StrictMode：useOverlayFocus 每次清理都把 openerRef 置空，下一次 effect 才重新记，所以「只在为空时记」的守卫恒真，记与还都幂等；打开前焦点在 body 或已被移除时不抛错。Hook 都在早返回之前，顺序稳定。
- Toast 计时：用 deadline 加剩余时间，暂停、恢复幂等；onClose 走 ref；重新打开与卸载都清；关闭钮先清再调。
- Menu：外点监听只在打开时注册；Esc stopPropagation；空菜单与单项不抛错。Dialog：Esc、Tab 都在对话框根上处理，覆盖两端与焦点在根上的情形。
- 没有悄悄扩大的范围：除 B1、(a) 的冒泡副作用（合同措辞所致）、点击选中（已申报），没有合同之外的行为。README 只加了目录行与 W5 一节，命令节没动；icons 只改了导出名，5 条路径一字未动（补丁里只有这一行变化）；attemptStates 只加 dot 字段与改名。
- 小瑕疵（不阻塞）：Tooltip.tsx 的 suppressedRef 只写不读（:22、:51、:60、:75、:84）；Tooltip.tsx:98–100 的 cloneElement 会把子元素自带的 aria-describedby 覆盖成 undefined；IconButton.tsx:23 的 {...rest} 在 aria-label 之后，调用方能覆盖名称；Menu 触发钮用 Button 缺省的 primary 变体，陈列页其余触发钮都显式写了 secondary。

## 6. 门禁与变异记录；等价声明复核

- 内核 check（checks/01/checks.json）：mode=fresh，候选树 04047eea3108…，检查前后树一致，modified_by_checks=false；V01 22 passed（33.67s）、V03 7 passed、V02 170 passed（46.64s），日志全是点，没有 s、x、F，P 系列没有被 conftest 跳过。V01 的 22 = S 系列 7 + P 系列 9 + 门禁自检 6，与执行报告一致。
- 白盒 80 passed，无 skip、xfail。变异 140 条（命令 W1 = 白盒一条 pytest）：caught 139、missed 1、skipped 0、error 0，unexpected_missed 与 files_left_modified 都为空。我抽读了 M67（抽屉拦 Tab，WB60 红）、M113（留 ServerIcon 别名，静态用例与 WB104 红）的日志，都是真断言失败，不是语法错误带来的空红；M116 的日志是 80 passed。
- 等价声明 F1（内核编号 M116；focusable.ts 里 `button:not([disabled])` 改成 `button`）：复核成立，是真等价。getFocusable 在选择器之后还有第二道筛 `!el.hasAttribute('hidden') && !el.hasAttribute('disabled')`（:16）；去掉选择器里的 :not([disabled]) 只会让带 disabled 属性的 button 多被选中，随即被第二道筛掉；querySelectorAll 按文档顺序返回，与选择器顺序无关；CSS 的 [disabled] 与 HTML 元素上的 hasAttribute('disabled') 等价；经 fieldset 禁用的按钮没有 disabled 属性，两种写法都包含。没有输入能区分两者。同理 input、select、textarea 的 :not([disabled]) 也是冗余，门禁端没给它们建变异，不影响结论。门禁端写的位置是「第 8 行」，实际是第 6 行（第 8 行是 select 的选择器），笔误。
- 门禁端说变异不到的两处：Dialog 的 getFocusable 为空分支（list.length 为 0）不可达，因为头部的关闭钮永远渲染且可聚焦；useOverlayFocus 里 `openerRef.current === null` 的守卫恒真，`document.contains(opener)` 的守卫在浏览器与 jsdom 里都冗余（对已脱离文档的元素 focus() 是空操作；白盒 WB46 守「不抛错」）。两处都不需要测试。
- 一处覆盖缺口，不退回战后门禁：变异清单里没有任何一条改 Tooltip 的 onMouseLeave、onBlur 的消失逻辑（清单里只有 Toast 的 onMouseLeave={resume}；T 系列缺 T5、T6，M 系列缺 M11，原因我不清楚）。这两处由基准 P2 与执行端测试守；并存场景（B1）在基准、白盒、执行端测试里都没有。B1 返工后的战后门禁请补，见 §9。

## 7. 风险（交站主，结项时一并交）

- R1（门禁端 (a)，对 T005 表单有影响）：Dialog.tsx:57 把 preventDefault 挂在遮罩上，框内任何位置的 mousedown 冒泡上来都被阻止。浏览器里 mousedown 的默认动作包括移动焦点、开始选中文字、（取决于浏览器）打开下拉，所以按推断：对话框里点文本框不会聚焦、不放光标，拖选文字不行；按钮点击与复选框切换不受影响（click 照常触发）。UI 文档 7.11 的「将运行的命令」「内核的报错」都是用户可能想选中的文字，虽有 [复制] 钮。本片的陈列页对话框只有文字与按钮，看不到；jsdom 测试直接 .focus()、不模拟 mousedown 的默认动作，也抓不到；T005 一放表单就暴露。这是推断，没在浏览器验证。建议：T005 合同把 Dialog.tsx 列进 allowed_modified_files，改成只在 e.target === e.currentTarget 时 preventDefault，并加断言：对框内元素触发 mouseDown 返回 true，对遮罩本身返回 false；基准 P4 与白盒 WB44 是直接对遮罩触发，改完仍过。
- R2（H2 会遇到，合同如此规定，不是实现缺陷）：打开对话框后焦点落在头部关闭钮，400ms 后弹出「关闭（Esc）」；此后第一次 Esc 被工具提示消费（Tooltip 可见时 stopPropagation），对话框不关，第二次才关。门禁端读代码得出，我读 Tooltip.tsx:70–78 与 Dialog 的 onKeyDown 后同意。H2 测「Esc 后焦点回触发按钮」时，若停留超过 400ms，请按两次。要改需出合同（例如初始聚焦不触发提示）。
- R3（门禁端 (e)）：H1 要专门看图标按钮、轻提示关闭钮默认态的 computed color，以及菜单触发钮、对话框按钮的字重；若被 .tt-app button 盖掉，需要一个小任务，见 (e)。
- R4（H1 小项）：Menu 触发钮是 primary 变体（陈列页其余触发钮是 secondary）；轻提示关闭钮没有工具提示；关闭钮圆角与图标尺寸与画布差 sm/md、14/16。
- R5（推演，未验证）：菜单面板是原地绝对定位（合同如此），放进对话框体里会被 .tt-dialog__body（overflow: auto）与 .tt-dialog（overflow: hidden）裁掉或撑出滚动条；以后在对话框里放菜单要先处理。
- H1–H6 全部没有做，都不算通过。

## 8. 非阻塞建议（不进阻塞项）

1. (a) 的修法：Dialog.tsx:57 改成 `onMouseDown={(e) => { if (e.target === e.currentTarget) e.preventDefault(); }}`，dialog.test.tsx 加一条：框内元素 mouseDown 返回 true，遮罩本身返回 false。
2. (d)：IconButton.css:18 加一行出处注释（组件板 :340 图标 16）；Toast.css:35 删掉（Toast.tsx 已用属性写 16），或加注释。
3. menu.test.tsx 补一条点击菜单项选中的用例（onSelect 一次、关闭、焦点回触发钮）。
4. focusable.ts:2 的注释改成只讲选择器的来源（通用的可聚焦列表），不提门禁探针。
5. 删掉 Tooltip.tsx 里只写不读的 suppressedRef；cloneElement 合并子元素自带的 aria-describedby；IconButton 把 {...rest} 放在 aria-label 之前或明说允许覆盖。
6. Menu 触发钮在陈列页用 secondary，与其它触发钮一致（H1 再定）。

## 9. 复审封板范围；给下一轮战后门禁的话

- 下一轮复审只核：B1（Tooltip.tsx 两处无条件 hide()；icon-button.test.tsx 的 3 条新用例，旧实现上会红、新实现上绿）；补丁相对本候选的新增改动是否只在这两个文件；V01、V02、V03、白盒、变异的新结果。其余我不再重审。
- 给战后门禁：补两条变异（去掉 onMouseLeave 的 hide、去掉 onBlur 的 hide）和并存场景的白盒用例。现有白盒 WB03、WB05 都只用一种触发，B1 的改动不会让它们变红；基准 P2 同样。

## 10. 没验证到的

- 没有运行 V01、V02、V03、白盒、变异，没有 npm、pytest、git；结果引自内核与门禁记录。
- 没有浏览器渲染：H1–H6 全部没看；(a)、(e)、R2 都是读代码和 CSS 文本得出的推断。
- 事件流 events.jsonl 只按关键字抽查了执行端关于 Esc 与并存标志的推理，没有通读。

Verdict: REVISE
