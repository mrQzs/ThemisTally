# 复审记录：t005-desktop-forms attempt-001（七端信箱 hub）

- 合同：t005-desktop-forms.v1（base 5640a2ce1db79333347c0c66f9b692f60d718cb5）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T005-7-audit-post 终审报告（audit-sonnet）

结论: 通过
退回: 无
阻塞项: 无

## 0. 结论与依据

- 候选 attempt-001（候选树 e7077fc4…，基线 5640a2ce…）忠实于合同 t005-desktop-forms.v1。D01–D12 都有可复核的独立证据（§5）；我读了全部新增与改动的源码，没有发现测试输入硬编码、空的异常处理、为过测试写的特判、弱化测试或悄悄扩大的范围。
- 门禁数字与内核检查记录逐项一致（§3）。变异实际是 276 条、全部被抓住（门禁报告与任务书写 273，以内核记录为准）。
- 门禁提出的五项都不是对合同字面的违反，记为非阻塞建议（§7）。
- 读源码时另发现 4 组合同没写死、但会影响人工验收 H2/H4 或后续片的点（§8 的 S1–S4）。不阻塞。S1、S2 建议站主验收前改掉。
- 不判返工的口径：阻塞项只收「违反合同字面或可判定的 DoD、越界、弱化测试」。S1 是合同没写的输入（rows 变化）；S2 在合同、基准、门禁三方的读法里都只管单元格；S3 在合同里写的是「建议」；S4 出在只能真浏览器看的演示布局。为这些再走一轮「新合同 + 新 attempt + 战后门禁 + 终审」，成本远高于约 15 行改动。协调人若另有口径，请明示，我按「退回: 执行端」重出阻塞项。

## 1. 做了什么，以及限制

- 读了：合同 md；执行报告、概述、事件流汇总；门禁战后报告与 state；JEV；一审报告；候选补丁的范围与关键片段；候选的全部源码（12 个组件、field/ 两个钩子、图标、index.ts、App.tsx、FormsShowcase.tsx、showcase-forms.css、base.css、Dialog.tsx、Toast.tsx、README）；13 份执行端测试；内核检查记录（checks/01、baseline/02）；变异记录（spec、mutations.json）；白盒文件的结构与关键探针；基准的 S/P 段；画布组件板 :413、任务页 :374–379。
- 限制：本回合只有 Read、Glob、Grep，Bash 被禁。没有运行任何测试，没有渲染页面，没有算哈希。门禁数字引用内核记录与白盒日志；§8 里的布局判断是读源码加令牌估算，未在真浏览器里验证。

## 2. 范围与纪律（审核要点 2）

- 补丁 50 个文件（A41 M9 D0 T0），scope.json 的 violations 为空。逐个对过合同的 allowed 清单：9 个改动（README、App.tsx、Dialog.tsx、IconButton.css、Toast.css、Toast.tsx、index.ts、icons/index.tsx、base.css）、24 个组件文件（12 个组件各 tsx + css）、field/ 两个 tsx、showcase/ 的 tsx + css、13 份新测试，全在允许清单里。
- 禁改清单一个都没碰：tokens.css、fonts.css、main.tsx、App.css、package.json、锁文件、index.html、vite.config.ts、tsconfig.json、scripts/**、Button/Tag/Card/Banner/StatusTag/Tooltip/Menu/Drawer、Dialog.css、IconButton.tsx、overlay/**、domain/**、既有测试、tests/test_gate_*、docs/**。
- 白盒不在补丁里：对补丁 Grep whitebox 与 test_gate_t005，0 处。工作区里的 tests/test_gate_t005_whitebox.py 是内核放进来的未跟踪文件，不在那 50 个里。集成时请按 AGENTS.md 点名暂存这 50 个，不要 git add -A。
- base.css 只动了原第 12–17 行（换成 6 行 :where() 加 2 行注释），焦点规则、减少动效、容器查询等其余规则未动。README 的「命令」一节未动。
- 测试纪律：13 份新测试没有 skip、only、todo、each、mock；既有测试一个没改。新源码里没有 console、debugger、@ts-ignore、any、dangerouslySetInnerHTML、fetch、本地存储，没有 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver、rAF、performance；除既有的 Toast 区域外没有 role=status。
- 事件流汇总（events-summary.json）：shell 命令 25 条，suspicious_commands 为空，没有越出工作区的路径。

## 3. 门禁结果可信性（审核要点 6）

| 项 | 门禁报告 / 任务书 | 内核记录 | 一致 |
|---|---|---|---|
| V01 | 37 passed | checks/01/V01.log：37 passed in 40.62s，退出 0 | 是 |
| V02 | 192 passed | V02.log：192 passed in 83.22s，退出 0 | 是 |
| V03 | 7 passed | V03.log：7 passed in 0.14s，退出 0 | 是 |
| 基线 V01 | 基线应失败 | baseline/02/checks.json：V01 退出 1（组件还不存在），V02、V03 通过 | 是 |
| 白盒 | 158 passed，无 skip、xfail | whitebox-…log：158 passed in 4.27s；变异基线 4.7s 同 | 是 |
| 变异 | 273 条全抓住 | mutations.json：276 条，caught 276、missed 0、skipped 0、error 0 | 条数差 3，结论一致 |
| 检查环境 | — | 全新克隆，candidate_tree e7077fc4 与 candidate.json 一致，modified_by_checks=false | 是 |

- 基准：candidate.json 的 base 是 5640a2ce1db7…，补丁没有碰 tests/；内核的 V01 就在这个基准加候选的树上跑。我算不了哈希，锁定以内核的提交为准。
- 白盒 4 秒跑完不是空转：它的会话夹具只启动一次 Vitest（node_modules 已在），把约 140 条探针一次跑完，再逐条参数化回 pytest；test_wb_probe_selfcheck_counts 核对条数并要求全部 passed，test_wb_probe_source_has_no_skip_markers 查 skip 类写法。
- 变异覆盖：spec 里 276 条的 file 字段覆盖了全部 25 个非测试改动文件（组件 tsx/css、field 钩子、Dialog、Toast、IconButton.css、base.css、index.ts、icons、README、App.tsx、FormsShowcase.tsx、showcase-forms.css）。门禁说没有 unmutated、没有 equivalent，我核对属实，没有等价变异或「没法变异的文件」需要裁定。4 条只插入不删的变异（M10、M97、M174、M234，内核发了警告）也被抓住，说明插入的代码确实改变了行为。

## 4. 读源码的结论

- 12 个组件、2 个钩子、陈列页、T004 四处修补，我逐个对过合同：结构、键盘、aria、样式取值与合同一致（DoD 逐条见 §5）。
- 没有测试输入硬编码、空的异常处理、为过测试写的特判。与探针形状最近的实现选择是 Table 行的 onFocus 同步（偏离 3），它是 roving tabindex 的通用做法，不依赖探针数据；它的副作用见 S1。
- 执行端自带测试与门禁探针同形（类名 gate-limit、helper 命名都一样），是照着基准写的。没有弱化，但对独立性没有增益；独立信号来自门禁白盒与变异。
- 一处名实不符：base-reset.test.ts 第 4 条「组件单类规则压得过 base 的重置（交叉核对）」没有读 Button.css、IconButton.css、Toast.css，只比较了 base.css 的最大特异性和写死的 `.tt-btn--primary`。合同 7.4 要求这条测试与三个组件的单类规则交叉核对。真正的交叉核对在基准 S2（cross_check_problems 读真实文件），长期留在仓库里，覆盖不丢，所以不阻塞（S7）。

## 5. DoD → 证据（审核要点 1）

| DoD | 证据 | 结论 |
|---|---|---|
| D01 | 执行端 segmented-control.test.tsx（3 条）；V01 的 S1、S5、P4、P12；白盒 WB201–210 与 CSS 精确比对；变异覆盖 SegmentedControl.tsx/css | 成立；value 不在选项里见 S5 |
| D02 | 执行端 switch-checkbox.test.tsx（开关、复选框各 6 条）；V01 的 S5、P5、P12；白盒 WB301–321；变异覆盖 useToggle、Switch、Checkbox | 成立 |
| D03 | 执行端 tabs.test.tsx（3 条）；V01 的 S5、P6、P12；白盒 WB401–412；变异覆盖 Tabs.tsx/css | 成立；其余页签也带 aria-controls 见 §7-1 |
| D04 | 执行端 text-field-select.test.tsx（4 条）；V01 的 S4、S5、P7、P12；白盒 WB101–125；变异覆盖 useFieldA11y、TextField、Select | 成立 |
| D05 | 执行端 table.test.tsx（4 条）；V01 的 S5、P8、P12；白盒 WB501–524；变异覆盖 Table.tsx/css | 合同字面成立；另见 S1、S2、S3 |
| D06 | 执行端 data-atoms.test.tsx（3 条）；V01 的 S4、S5、P9、P12；白盒 WB601–625 | 成立 |
| D07 | 执行端 skeleton.test.tsx（2 条）；V01 的 S5、P10、P12；白盒 WB701–708、WB1009、WB1013 | 成立 |
| D08 | 执行端 connection-pill.test.tsx（4 条）；V01 的 S5、P11、P12；白盒 WB801–816 | 成立；演示布局见 S4(b) |
| D09 | 见下 | 成立 |
| D10 | 见下 | 文字与结构成立；布局两处见 S4 |
| D11 | 见下 | 成立 |
| D12 | V01 的 test_d12_*（令牌、出处注释、禁用 API、流水线前后 git status）；内核范围门禁 scope.json（0 违规）；我对 50 个文件的核对（§2） | 成立 |

重点三条（JEV 指出自述完成而无证据）：执行报告只写了「证据 V01（P4/S5）」之类，没贴输出，5 条检查命令的退出码还被 | tail 掩盖（内核已标注）；这些自述我不当证据。下面每条都另有独立证据：

- D09（T004 修补）：
  - 遮罩：Dialog.tsx:61–63 只在 e.target === e.currentTarget 时 preventDefault，文件头注释同步；执行端 dialog-scrim.test.tsx 3 条；V01 P2；白盒 WB901–902。
  - 轻提示关闭钮：Toast.tsx:81–93 外包 Tooltip（content=关闭提示），名称仍是 aria-label；执行端 toast-close-tooltip.test.tsx 3 条；V01 P3；白盒 WB903–905（含 399/400ms 边界、5000ms 自动关闭照旧、工具提示不在 role=status 区域里）。
  - 16px：IconButton.css:18 同一行加了「组件板 :340，图标 16」并保留；Toast.css 删了 svg 规则（补丁 -1 行）；V01 S3；白盒 test_wb_css_t004_patches。
  - 基础重置：base.css:14–19 与合同建议写法一字不差；执行端 base-reset.test.ts 4 条（自检样本、真实 base.css、正向检查、交叉核对——最后一条是空壳，见 S7）；V01 S2（含对 Button.css、IconButton.css、Toast.css 真实单类规则的交叉核对）与 P1（dist 保留 :where(）；白盒 test_wb_base_css_*。
  - Button.css 不变：补丁里没有 Button.*（scope.json）；V02 192 passed。
  - 变异：Dialog.tsx、Toast.tsx、Toast.css、IconButton.css、base.css 共 23 条，全部抓住。
- D10（陈列页）：
  - 11 个 data-demo 节的顺序、复用类、标题不含 Button、无文字按钮都有 aria-label、整页只有轻提示一个 role=status、表格三档、「上次打开」、骨架屏 299/300ms 与短加载、胶囊三态：V01 P12（过渡断言 test_transitional_d10_showcase_form_demos，docstring 第一行与合同一致，另查 showcase CSS 有限高声明）；白盒 WB1001–1013；执行端 showcase-forms.test.tsx 6 条；变异覆盖 FormsShowcase.tsx、App.tsx、showcase-forms.css。
  - 表单对话框里输入框 mousedown 不被阻止、能聚焦：证据是 jsdom 层面的 fireEvent.mouseDown 返回 true 与 focus 成功（P12、WB1003、showcase-forms.test.tsx）。真浏览器里拖选文字属 H2，没有证据，也不是门禁能给的。
  - 我的 review：节标题、按钮文字、无井号与颜色函数、无主题字样都对过合同 §13。差两处布局，只在真浏览器里可见、基准不测：S4(a)「容器比表窄」按估算没达成，S4(b) 第一个胶囊的浮层按估算会被视口左缘裁掉大半。
- D11（回归）：V02 192、V03 7、V01 的 test_d11_pipeline_steps_pass（npm ci、npm run build、npm test、npm run check:contract 都退出 0，npm test 无 failed、skipped、todo）；内核在候选树的全新克隆里独立重跑，三条都过。执行端自述 130 passed（23 files）与测试文件数相符（10 个既有 + 13 个新增），但属自述，不作证据。T001–T004 的 4 条过渡断言在 V02 里，仍通过。

## 6. 执行端的偏离（审核要点 3）

| # | 偏离 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 重连中且未给 attempt 时显示「重连中」 | 接受 | 合同第 11 条只写了带次数的形态；字面「没给的值显示未知」套到这里会得到「第 未知 次」，不通顺；候选取不含计数的回退，已列入 interpretations，白盒 WB802 钉住。不违背字面 |
| 2 | 胶囊浮层用普通 div、不设 role | 接受 | 合同没指定 role 且禁止 role=status；关联靠 aria-expanded、aria-controls；WB805、WB808 |
| 3 | 表格行 onFocus 同步 active，selectedKey 变化时重新派生 | 接受，另见 S1 | 满足「方向键移动时同时移真实焦点、改 tabIndex」与「起点是选中行」；不依赖探针数据。下标 state 只在 selectedKey 变时重算，是 S1 的根源 |
| 4 | Select.tsx 引入 TextField.css | 接受 | allowed 里没有 field/*.css，复用基类合理；Select.css 的 (0,2,0) 选择器与 import 顺序无关 |
| 5 | 面包屑分隔用 aria-hidden 的 li | 接受 | 合同「项之间是 ChevronRightIcon 14、aria-hidden」；ol 只含 li，结构合法；aria-hidden 的 li 不进辅助技术树；WB621、WB624 |
| 6 | 表格焦点环画在 tr 上，未加单元格 inset 阴影 | 不违字面，另见 S3 | 合同写的是「建议」；执行报告没提同一段里的另一条建议 scroll-padding-top 也没做，属漏报 |
| 7 | 合同矛盾：Repository facts 的旧快照与 base_sha 不一致 | 裁定正确 | 以 base_sha 与工作区为准；V01 要的门禁文件已在基线里；已派遣的合同不改，下一版顺手修正（S8） |

执行端没列、但属于「选了一种读法」的 3 处，都不与合同字面冲突：Tabs 每个页签都带 aria-controls（§7-1）；Table 表头不随数字列右对齐（S2）；ConnectionPill 的 data-state 写在里面的 button 上而不是外层包裹 span 上（合同写「根上带 data-state」；基准与门禁的参考 CSS 都按 .tt-pill[data-state] 写，读法一致）。

## 7. 门禁提出的五项（审核要点 4）

**7-1 Tabs 每个页签都带 aria-controls（Tabs.tsx:64）**
- 裁定：不是候选缺陷，是合同缺口。不收紧。
- 理由：合同第 6 条写「当前页签带 aria-controls 指向面板」，没写其余页签不带；D03、基准 P6、白盒 WB403 都只钉当前页签。单面板的设计里面板 id 始终存在，所有页签指向同一个面板不产生悬空引用，读屏不受影响。
- 去向：下一份合同的公共约定里写明即可，不需要改候选。

**7-2 showcase-forms.css 的 240px、560px 没有出处注释**
- 裁定：合同缺口，候选缺陷的成分很轻；非阻塞（S6）。
- 理由：公共约定「尺寸字面量同一行带出处注释（文档节号或画布行号）」没写适用范围，基准的检查限定在 12 份组件 CSS（test_d12_new_css_tokens_and_source_comments）。这两个值是演示自定的布局值，画布上没有出处可引。
- 去向：补一行说明（演示自定，见合同 §13、H4）即可；合同下次写明演示 CSS 是否适用。另：560 这个值本身有问题，见 S4(a)。

**7-3 value 不在选项里时没有 tabIndex=0 的元素（SegmentedControl.tsx:20、:54；Tabs.tsx:23、:65）**
- 裁定：合同缺口，非阻塞（S5）。
- 理由：合同没有定义这种输入；D01、D03「只有选中段、当前页签 tabIndex=0」的字面在这种输入下恰好得出零个。但候选自己已经为方向键算了 active（缺省 0），只是 tabIndex 没跟着用，前后不一致。
- 去向：一行修法见 S5；合同下次写明「value 无效时第一项可 Tab」。

**7-4 Table：表头数字列不右对齐（Table.css:20）；rows 变少时 active 越界（Table.tsx:39–45、:92）**
- 裁定：合同缺口，两条都建议修（S2、S1），非阻塞。
- 理由（表头）：合同第 7 条写「数字列右对齐、带 tt-num」，出现在行样式一段，没提表头；基准与门禁都只测单元格。但合同引用的画布（组件板 :413 的用时、token 表头，任务页 :374、:378、:379 的 th）都是 text-align: right，所以我建议修。
- 理由（越界）：合同的 Roving 只定义了起点，没有定义 rows 变化；D05「恰一行 tabIndex=0」在静态输入下成立。当前演示的 rows 是常量，不触发；应用框架那一片接真实列表时会触发，表现是键盘用户 Tab 不进表格。
- 去向：S1、S2。

**7-5 空格 repeat 时仍 preventDefault；关闭态胶囊按 Esc 不被吞**
- 裁定：都不是缺陷，是合理的行为，建议写进合同。
- 理由：公共约定「组件处理了的键都 preventDefault」，空格被处理了，repeat 时只是不切换，仍要拦住默认（否则按住空格会滚页面）。关闭态胶囊没有可关的东西，不吞 Esc 才能让外层对话框处理它；合同的「Esc 关闭并 stopPropagation」限定在「浮层打开时」。另查：胶囊的 Esc 处理没有 preventDefault，与公共约定字面有出入，但合同对胶囊只写了 stopPropagation，T004 的 Dialog.tsx:30–34 也是同样写法，不算缺陷。
- 去向：合同下次写明这两点。

## 8. 其他发现（非阻塞建议，按优先级）

**S1（高）Table 的当前行不随 rows 变化重算**（Table.tsx:39–45、:92）
- 现状：active 是下标 state，只在首次渲染和 selectedKey 变化时算。后果：(a) rows 变少到 active 之后，没有 tabIndex=0 的行，Tab 键跳过整个表；(b) rows 晚于 selectedKey 到达（先空后载入）时，当前行停在第一行而不是选中行；(c) 排序或插入后，下标指向另一行。演示里 rows 是常量，现在不触发。
- 最小修法：渲染时把 active 夹到 [0, rows.length - 1] 再用于 tabIndex。稳妥修法：state 存当前行的 key，找不到时回到选中行或第一行。

**S2（中）数字列的表头也应右对齐**（Table.css:20、:38）
- 现状：th 一律 text-align: left，只有 td.tt-num 右对齐。画布的数字列表头是右对齐（组件板 :413；任务页 :374、:378、:379）。H1 对照画布会看到表头与数字错位。
- 最小修法：Table.tsx 给 numeric 列的 th 加一个类，Table.css 加 `.tt-table th.<类> { text-align: right; }`。

**S3（中，合同写作「建议」）scroll-padding-top 与焦点环**（Table.css；偏离 6）
- 现状：容器没有 scroll-padding-top；焦点环画在 tr 上（base.css 的 :focus-visible 轮廓）。预计 H4「键盘移到上面的行时不被表头挡住、行的焦点环看得见」不过：向上移动时 focus() 把行滚到容器上沿，会被 32 高的吸顶表头盖住；tr 的轮廓（宽 2、外偏 2）超出行盒，容器 overflow: auto 估计会裁掉左右两段。
- 最小修法：`.tt-table-wrap { scroll-padding-top: 32px; }` 加同行出处注释；焦点环按合同建议改成单元格的 inset 阴影。

**S4（中）陈列页两处布局，预计 H4、H2 会发现**（均为按令牌估算，未渲染）
- (a) showcase-forms.css:4 的 `.showcase-table { max-height: 240px; max-width: 560px; }`：合同 §13 要求「容器限高、比表窄」。四列表按等距字体估算自然宽度约 330px（正文中文 13px 宽、数字 6.5px，表头 14px，单元格左右各 12px），容器在 showcase__stack（flex 列、align-items: flex-start）里按内容收缩，宽约等于表宽、小于 560，不会比表窄，横向滚动在演示里出不来；视口窄到容器的 min-content 以下时容器还可能不收缩、把整页撑出横向滚动。修法：max-width 取低于表自然宽度的值（例如 280px）。
- (b) FormsShowcase.tsx:264–268 三个胶囊在左对齐的一行里，浮层按合同右对齐、宽 240：第一个胶囊（已连接）左缘约在 x=24、宽约 66，浮层左缘约落在 -150，约 150px 在视口左缘外，值列大半被裁掉。修法：该行加 `justify-content: flex-end` 的类，或给行留出左边距。

**S5（低）value 不在选项里时没有可 Tab 的元素**（即 §7-3）：SegmentedControl.tsx:20 已算 active，:54 的 tabIndex 只看 checked；Tabs.tsx:23、:65 同理。一行修法：tabIndex 改看 active 下标。

**S6（低）showcase-forms.css 的 240px、560px 无注释**（即 §7-2）。

**S7（低）base-reset.test.ts 第 4 条交叉核对是空壳**（base-reset.test.ts:158–169）：没读 Button.css、IconButton.css、Toast.css。可补成读真实文件、查 .tt-btn--primary 的 color、.tt-btn--sm/md/lg 的 font、.tt-icon-btn 的 color、.tt-toast__close 的 color 的特异性高于重置。覆盖不丢（基准 S2 有）。

**S8（文档）**
- 门禁报告与任务书的变异条数 273，内核记录 276，请订正。
- 合同 Repository facts 里「worktree HEAD 2a86c37、T005 门禁基线上不存在」是旧快照，与 base_sha 5640a2c 不符；执行端按 base_sha 裁定是对的。已派遣的合同不改，下一版修正。
- 执行报告叙述里「9 modified + 37 new」与 JSON 清单（50 个）和调度器统计（M9 A41）不符，以后者为准。

## 9. JEV 关注点（审核要点 1）

- 自述完成而无证据（0.90）：对一半。执行报告确实没贴输出，5 条检查退出码被管道掩盖；但 D01–D12 的事实另有独立证据（内核全新克隆重跑、白盒 158、变异 276），不影响结论。
- 误导程度（2.15）：执行报告漏报了合同建议的 scroll-padding-top 没做、演示容器没达到「比表窄」、Tabs 与表头的两处读法。这几处独立检查查不出，我已补在 S1–S4 与 §6，它们不改变判定。
- 自行解读合同（0.68）：执行端列了 6 条 interpretations，另有 3 处没列（§6 末），都不与合同字面冲突。
- 超出范围（0.41）：不成立。50 个文件全在 allowed；多出的只有 README 开头一句更新、Skeleton 的可选 className、Tabs 面板 padding-top，无害。
- 弱化测试（0.05）：不成立，既有测试一个没改。

## 10. 需协调人决定

1. S1–S4 共约 15 行（Table.tsx、Table.css、showcase-forms.css、FormsShowcase.tsx）是否在站主做 H1–H8 之前由规划端直接小改。我的建议：改 S1、S2；S3、S4 与 H4、H2 直接相关，建议一并改。改后重跑 V01（37）、V02（192）、V03（7）即可；白盒对这几个文件的精确比对会过期，但白盒不入库。
2. 若不改：请在给站主的验收说明里提前写明，H4 要看到完整效果需要 S2、S3、S4(a)，H2 的第一个胶囊浮层会被视口左缘裁掉。
3. 不判返工的口径见 §0。若要按「退回: 执行端」处理，请明示，我只重出 S1–S4 为阻塞项，下一轮只复核它们和新改动。
4. 五项合同缺口与 S1、S2、S5 请写进应用框架那一片的合同。
5. 集成时只暂存补丁的 50 个文件，不带 tests/test_gate_t005_whitebox.py。

## 11. 人工项

H1–H8 本回合未做，也不阻塞。H3 的 computed 值变化属预期。预计 H4 需要 S2、S3、S4(a)，H2 的胶囊演示需要 S4(b)。

Verdict: PASS
