# 复审记录：t002-desktop-web attempt-002（七端信箱 hub 终审，站主接手）

- 合同：t002-desktop-web.v3（base a7193dc7b2b38bc1ec5c9dc8c823224cdd2edfe2）
- 内核 check --fresh：通过；范围违规 0
- 战后门禁：白盒 58 passed、3 xfailed（xfail 标的是合同违反，见终审 §3）；变异 15 条全部抓住
- 复审者：audit-sonnet（claude-sonnet-5-5，max）。结论返工，退回执行端，阻塞项 B1–B6。
- 后续：attempt-003 没有带上本轮的候选与阻塞项（七端内核第 10 轮修复的漏洞），预算用完；站主改由规划端在本 attempt 的返工提交上补完 B1–B5，见 attempt-003-owner.md 与 T002 的 closed-by-owner.md。

## 终审报告

# T002-7-audit-post 终审报告（attempt-002 · 合同 v3）

## 1. 判定

- 结论：**返工**；退回：**执行端**（exec-step · T002-5-exec）。
- 一句话依据：候选在 V01（75 passed）与战后白盒（58 passed、3 xfailed）下是绿的，范围也干净；但门禁用 xfail(strict=True) 标出的 3 处缺陷，在合同 v3 里都是明确要求的行为，不属于「合同本身不确定」，不能放过，缺陷都在执行端。另有 2 处较小偏离（B4、B5）和 1 条报告如实性要求（B6）。
- 这是第 3 个、也是最后一个 attempt（max_attempts_total=3）。阻塞项在 §2 一次列全；下一轮只复核 B1–B6 与新改动（复审封板）。
- 顺序提醒：战后门禁里的 3 处 xfail 必须在 attempt-003 的战后门禁运行之前去掉（§8）。strict 的 xfail 会让已修好的候选变红、让没修好的候选变绿；去掉之后门禁在现候选上是红的，变异检查（要求基线绿）也跑不起来——这正说明现候选不能合入。
- 我没有把「退回门禁」「退回执行」拆成两次判定：xfail 用错是事实，但挡住合入的是候选自身的缺陷，所以退回值取执行端，门禁要改的地方单列在 §8，由协调人转交。

## 2. 阻塞项（执行端必须改；一次列全）

**B1 StatusTag / 状态表对 Object.prototype 同名的状态码崩溃**
- 位置：desktop/web/src/domain/attemptStates.ts:83-87（resolveAttemptState 用 ATTEMPT_STATES[code] 取值再 if (known)）；后果出在 desktop/web/src/components/StatusTag.tsx:16、:26（info.icon 为 undefined，React 抛 Element type is invalid）。
- 合同：Behavior contract「边界与错误」StatusTag（17 个已知状态以外的任意状态码…）与「组件接口」StatusTag；UI 文档 §3.4 兜底行写明「不报错」。
- 要改：改用自有属性判定（如 Object.hasOwn(ATTEMPT_STATES, code)）。导出名与形状不变：ATTEMPT_STATES 仍是普通对象、自有键恰为 17 个状态码；FALLBACK_STATE、resolveAttemptState 保留（白盒按这些名字读）。
- 验收：state 为 constructor、toString、hasOwnProperty、valueOf、__proto__（以及 isPrototypeOf、toLocaleString）时不抛错，文本与 title 为状态码原样，data-tone 为 neutral，图标为 circle-help。

**B2 契约检查把 var(--tt-gray-*、--tt-navy-*、--tt-gold-*) 当成命名颜色（误报）**
- 位置：desktop/web/scripts/token-contract.mjs:37（NAMED_COLOR_RE，按单词边界在整个取值里找）、:109（CSS 取值）、:134（TSX style 取值）。
- 合同：规则 1（定义过的 --tt-… 是合法引用）与规则 2（命名颜色指取值里的颜色关键字，变量名不是）；D04「对合法写法放行」。
- 要改：判命名颜色前，先把取值里的自定义属性名（以 -- 开头的标识符）屏蔽掉。不要因为取值里有 var( 就整体跳过——回退值里的命名颜色仍是写死颜色。
- 验收：令牌里定义了 --tt-gray-1、--tt-navy-500、--tt-gold-500 时，CSS 的 color:var(--tt-gray-1)、background:var(--tt-navy-500)、border:1px solid var(--tt-gold-500)，以及 TSX 的 style={{ color: 'var(--tt-gray-1)' }} 退出 0 且无违规行；color:var(--tt-a, red) 退出 1。

**B3 契约检查按行扫描，多行写法里的命名颜色漏判（漏报）**
- 位置：token-contract.mjs:127（styleRe 只匹配同一行里的 style={{…}}）、:105（CSS 声明正则也是按行）、:189-195（先 split 成行再逐行扫）。
- 合同：规则 2「TSX：命名颜色只在 style={{…}} 对象里、且键为颜色类属性时判定」与「CSS 命名颜色作为颜色类属性的取值」，都没有「单行」限制。
- 要改：style={{ … }} 对象与 CSS 声明按语句跨行扫描（做法提示：对整份文本匹配，再按偏移量换算行号）。单行时的现有行为、行号、输出格式、退出码都不变；多行时行号取命名颜色所在行或声明起始行，必须是真实行号。
- 验收：style={{⏎ color: 'red',⏎ width: 3,⏎ }} 退出 1 并有输出行；CSS 的 box-shadow:⏎ 0 0 0 1px red; 退出 1。（后者是我静态推演的，门禁暂未测；与 TSX 同根因，一并修。）

**B4 组件里重写令牌文件已定义的变量不判违规（漏报）**
- 位置：token-contract.mjs:143-152（scanUndefined 只看 defined.has(名字)）。
- 合同：规则 1「……；在组件里用 --tt-x: 自行定义也算违规」。后半句不以「令牌里未定义」为条件；若只判未定义名，这半句与前半句重复。（这是审核裁定，见 §4。）
- 要改：对令牌文件以外的文件，凡 CSS 里 --tt-<名字> 后紧跟冒号的声明，不论令牌里是否定义，都输出一行违规（规则名沿用「未定义变量」，片段为变量名）。var(--tt-x) 引用不受影响；TS/TSX 里带引号的键可以不判。
- 验收：令牌里定义 --tt-bg 时，组件 CSS 的 .a{--tt-bg:1px} 退出 1 并报 --tt-bg；.a{color:var(--tt-bg)} 仍退出 0。

**B5 组件 CSS 的间距字面量，令牌里有同值的 --tt-space-***
- 位置与应换成的令牌：StatusTag.css:5 gap:4px→var(--tt-space-1)；StatusTag.css:9 padding:0 8px→0 var(--tt-space-2)；Button.css:14 padding:0 12px→0 var(--tt-space-3)；Button.css:15、:16 padding:0 16px→0 var(--tt-space-4)；Banner.css:6 padding:10px 12px 10px 14px 里的 12px→var(--tt-space-3)。
- 合同：Steps 9「每个组件一份 CSS 只用令牌」、Repository facts「所有组件只用 --tt-* 令牌」；执行端自己的解读 #2 也只允许「无对应令牌的尺寸」用字面量，代码与之不符（Card.css、App.css 同样的值就用了令牌）。
- 要改：上面 6 处换成令牌。无同值令牌的值（6px、10px、14px、88px）、合同写死的高度（20/22/28/32/36）、1px 边框保持字面量。范围只限 src/components/*.css 与 src/App.css 的 padding / gap / margin；base.css（搬自画布）与宽高不在内。
- 验收：上述范围内 padding / gap / margin 的 px 字面量不再等于任何 --tt-space-* 的值（2/4/8/12/16/20/24/32/40/48/64px）。

**B6 执行报告如实**
- 解读 #2 的措辞改成与代码一致；D01、D04 不得再写「对合法写法放行」之类的结论，除非 B2–B4 已修，并附对应的测试名与命令输出（用执行说明给的自检照抄写法，不要让管道掩盖退出码）。B2–B4 的回归用例补进 desktop/web/tests/token-contract.test.ts（Steps 7）；B1 建议补一条组件回归用例。
- 其它：除上述外不改其它文件；不碰 tests/test_gate_t002_*.py（门禁端的事，见 §8）；V01 仍须 75 passed。

## 3. 门禁 xfail 三处的逐条判断

### (a) StatusTag 遇到与 Object.prototype 同名的状态码崩溃：合同违反，应为红
- 合同：「17 个已知状态以外的任意状态码：原样显示、neutral、circle-help、title 为状态码」；UI 文档 §3.4 兜底行「不报错」。
- 事实：attemptStates.ts:83-87 用普通对象取值，constructor 等命中原型链上的函数/对象，被当成已知状态；{...known} 拷不出 icon，StatusTag.tsx:16 的 Icon 为 undefined，:26 渲染时 React 抛错。main.tsx 没有错误边界，整棵树会白屏。（静态推演，与门禁 --runxfail 的结论一致。）
- 判断：不是可接受的边界。「任意」已经把这类输入包含在内；状态码来自内核数据，兜底存在的意义就是对没见过的字符串不崩。xfail 的前提不成立。缺陷在执行端，修法一行。门禁的探针用例对正确实现是成立的（我逐个推演了 5 个码在修好后的文本、title、data-tone、图标 innerHTML，都与断言一致），不会误报。

### (b) 契约检查把 var(--tt-gray|navy|gold-*) 判成命名颜色：执行端缺陷，应为红
- 合同：规则 2 的命名颜色是「颜色类属性的取值」；规则 1 要求每个 --tt-… 在令牌文件里定义（定义过的就是合法引用）；D04「对合法写法放行」；战前基准 test_g9_clean_samples_pass 的文档也把「已定义的 var」列为合法写法。
- 事实：token-contract.mjs:37 的 NAMED_COLOR_RE 按单词边界在整个取值里找，连字符是非单词字符，令牌名里的 gray / navy / gold 因此命中；:109（CSS）与 :134（TSX）都用它。
- 判断：脚本和它的测试都是执行端的交付（Steps 7），误报算执行端缺陷。现有源码没触发（我 grep 过：组件里没有引用原色令牌），但下一片必踩：设计稿里 var(--tt-gray-* / navy-* / gold-*) 共 42 行、5 个文件，例如 02-基础组件 346 行 background: var(--tt-gray-900); color: var(--tt-gray-50)、screens/Logs.dc.html 163–166 行 background: var(--tt-navy-500)，照搬就会被脚本拒。合同没有任何一句禁止引用原色令牌，所以不是「合同不确定」。

### (c) 契约检查对多行 style={{…}} 里的命名颜色漏判：规则 2 覆盖，应为红
- 合同：「TSX：命名颜色只在 style={{…}} 对象里、且键为颜色类属性时判定」，没有「单行」限制。
- 事实：token-contract.mjs:189-195 先 split 成行再逐行扫，:127 的 styleRe 只能匹配同一行里的 style={{…}}。Prettier 对放不进一行的对象就是拆成多行，所以这条规则对真实代码基本不起作用。
- 判断：覆盖，执行端缺陷。同根因的补充（我静态推演，未实跑，门禁也没测）：CSS 声明同样按行扫描（:105），box-shadow: 换行后写 0 0 0 1px red; 的命名颜色也漏判。已并入 B3。

小结：三处都是「合同明确要求而候选不满足」，xfail 不能接受，门禁应为红；缺陷在执行端，所以退回执行端。

## 4. 门禁的 2 项建议决定

- (b) 间距字面量：属于执行端的偏离（B5）。合同「只用令牌」；合同自己写死的数值（高 20/22/28/32/36、Tag 内边距 0 6）没有同值令牌，只能用字面量，其余有同值令牌的应当用令牌。执行端的解读 #2 自己也只允许「无对应令牌的尺寸（6/10/14/20/22/28/32/36px）」用字面量，但代码里 4/8/12/16px 的 padding / gap 也是字面量（StatusTag.css:5、:9，Button.css:14–16，Banner.css:6），而 Card.css、App.css 同样的值用了令牌——不是做不到，是不一致，代码与自述不符。范围我限定在 padding / gap / margin，不扩到宽高。
- (c) 组件里重写已定义变量：合同字面覆盖（我的裁定，把握约七成），需要门禁补断言，候选也要改（B4）。理由：规则 1 的后半句「在组件里用 --tt-x: 自行定义也算违规」不以「令牌里未定义」为条件；若只判未定义名，它与前半句重复。现状：scanUndefined（:143-152）只看 defined.has(名字)，所以令牌里已有 --tt-bg 时 .a{--tt-bg:1px} 不会被报；战前基准的 var-defined-in-component 用例与战后白盒的 --tt-own 用的都是未定义名，抓不到（静态推演，未实跑）。后果：组件里 --tt-surface-1: var(--tt-surface-2) 这类重写不含颜色字面量，别的规则拦不住，W4 的「令牌单一来源」被绕过。协调人若认为合同在此不明确，可同时从返工任务书（B4）和门禁补断言（§8）里去掉，不影响其余阻塞项。

## 5. 执行端 6 处解读的核对

| # | 解读 | 判断 |
|---|---|---|
| 1 | tsconfig 的 include 不含 tests/ | 合理。Steps 3 只要求 strict、noEmit；开发依赖清单没有 @types/node，测试要用 node:fs 等，纳入 tsc 会失败。代价（tests 不做类型检查）已如实写进报告。 |
| 2 | 尺寸用字面量 | 原则合理，但代码与自述不符，见 §4(b) / B5。 |
| 3 | RUNNING 的 loader-circle 加 tt-spin | 合理，且其实是 UI 文档 §3.4 的明文要求（loader-circle，转动；减少动效时静止）；base.css 的 prefers-reduced-motion 里 .tt-spin 为 animation: none。 |
| 4 | Banner 的 info 总是渲染关闭按钮 | 合理，就是合同原文（只有 info 渲染）。 |
| 5 | 锁文件已生成、未提交 | 合理。Forbidden 与 authorized_actions 都不含提交，已按 contract_conflicts 如实记录。注意：package-lock.json（3214 行）在候选补丁里（A），集成时随补丁一并提交，Steps 4 的「提交锁文件」由集成端完成。 |
| 6 | esbuild postinstall 未执行 | 合理。门禁已验：@esbuild/win32-x64 来自 optionalDependencies，npm ci 之后直接转译成功；V01 在干净副本上也通过。 |

## 6. JEV（战后）两条

**「自述完成而无证据」（p=0.84）——逐项核对 D01–D05：**

| DoD | 报告声称 | 证据 | 判断 |
|---|---|---|---|
| D01 | 四步通过、令牌与画布逐项相等、5 组件与陈列页就位 | 报告列了 npm ci / build / test / check:contract 与 V01；令牌逐块比对在事件流 33972–33979 行有实跑（5 块 78/56/56/48/3，cmp exit: 0；33580–33584 行有一次 exit 1，修正后复跑通过）；白盒 test_tokens_equal_canvas_in_every_context_both_ways 独立再验；V01 在干净副本上 75 passed | 有证据；但「5 组件就位」被 B1 打折 |
| D02 | 只改 .gitignore、只新增 desktop/web/** | 内核 scope.json：violations 为空，A29 M1 | 有证据 |
| D03 | 无删除、跳过或弱化 | candidate.stat 无删除；新增 token-contract.test.ts 13 例，无 skip / only | 有证据 |
| D04 | 契约检查对各类违规判违规、对合法写法放行 | tests/token-contract.test.ts 13 例 + V01 的 G9 合成样本 | 有证据，但覆盖不足：没有 var(--tt-gray-*) 合法写法、没有多行、没有组件重写已定义变量 → B2–B4 |
| D05 | 无字体文件、无 @font-face、无字体包 | V01 + 白盒 license / build 用例；我 grep 了锁文件，没有 font 字样 | 有证据 |

结论：没有哪个 DoD 是「毫无证据」的，「无证据」在字面上不成立。成立的是另一件事——报告把 D01 的「5 个组件就位」与 D04 的「对合法写法放行」写成 done，而事实上有 B1–B4；几条 reported_exit_code 是管道推断值（内核概述已指出），靠 V01 才算证实。这是自述过强（对应 JEV 误导程度 1.74/3 的一部分），不是造假。要求写进 B6。

**「自行解读合同」（p=0.49，留意）：** 任务书点名的 6 处都已在报告里披露（4 条 interpretations、1 条 contract_conflicts、limitations）。未披露的选择有 3 处，都是小事：(i) 工具链固定在较旧的「已知可用」版本（vite 5.4.11、vitest 2.1.8、typescript 5.6.3、jsdom 25.0.1、@vitejs/plugin-react 4.3.4），事件流 10009 行的推理凭印象挑版本，没核对当前稳定版，也没按 Steps 4 在报告里说明；(ii) UI 文档 §3.4 的 ACCEPTED_WITH_EXCEPTION「右上角 warning 色小圆点」没做；(iii) INFRA_FAILURE 的图标跟画布（server-crash 形状），合同写的是 server。三处都不单独构成打回理由（见 §9），但应让站主知道。JEV 的「超出范围」（0.17）「弱化测试」（0.04）与我的核对一致：没有越界，没有弱化。

## 7. 范围、越界与门禁核对

- 范围：scope.json ok，A29 M1 D0，越界 0；.gitignore 只追加（空行 + 注释 + 3 行），原有行不变；没有碰 docs/、scripts/、.agent/、tests/test_gate_t002_baseline.py；没有 .npmrc、字体包、@font-face、fonts.css、.tsbuildinfo。
- 无特判迎合门禁：grep 过 gate-probe / whitebox / baseline / process.env / NODE_ENV，只有 vite.config.ts 里合同要求的 gate-probe include 与 README 的说明；src 与 tests 里没有 @ts-ignore、any、skip、only、TODO。
- 来源：17 个状态图标 + circle-help 的路径与画布 01-设计令牌 §3.4 的 SVG 目视对照一致（未做机械比对；info / triangle-alert / x 未核对）；许可原文来自 npm pack lucide@1.59.0（事件流 27146 行起的 npm view 与 27233 行的 npm pack，Copyright 行出现在 11 行事件流里），不是凭记忆写的。图标与 Lucide 1.59.0 的逐字一致无离线来源，仍是人工项。
- 战后门禁文件：tests/test_gate_t002_whitebox.py 是唯一新增文件，基准测试未改。
- 变异：1 条命令（W1：pytest 加 -k 'not npm'），不含 npm ci；15 条全部 caught，0 missed / skipped / error；没有声明 equivalent 的变异。我看了 M05（8 个用例失败，原因正是定义过的变量被误报）、M12（兜底用例失败）、M13（3 个探针用例失败）——都是因预期原因被抓，不是脚本语法崩溃。清单宽度偏窄（Tag、Card、base.css、主题切换、图标没有变异），不是错误，不退回。
- 白盒的问题只有 xfail（§3）；文件头 docstring 写「两处真缺陷」，实际 3 处。

## 8. 门禁端要改的地方（供协调人转交 gate-sonnet · T002-6-gate-post；须在 attempt-003 的战后门禁运行前完成）

1. 去掉 3 处 xfail：test_probe_case 的参数 status_tag_prototype_property_names_are_unknown_states、test_contract_var_reference_to_primitive_color_token_is_not_a_hardcoded_color、test_contract_tsx_multiline_style_object_named_color_is_flagged；断言保持原样。今后合同明确要求的行为不得再用 xfail，xfail 只留给「合同本身不确定」。
2. 补断言（候选未修时应红）：
   - B3 的 CSS 多行：box-shadow:⏎ 0 0 0 1px red; 退出 1。
   - B4：令牌定义 --tt-bg 时，组件 CSS 里 .a{--tt-bg:1px} 退出 1 并报 --tt-bg；同文件的 var(--tt-bg) 引用不报。
   - B2 的防偷懒修法：color:var(--tt-a, red) 退出 1（回退值里的命名颜色仍判违规）；box-shadow: 0 0 0 1px var(--tt-a), 0 1px black 报 black。
   - B5：src/components/*.css 与 src/App.css 里 padding / gap / margin 的 px 字面量不得等于任何 --tt-space-* 的值（2/4/8/12/16/20/24/32/40/48/64px）；Tag / StatusTag 的 0 6px、Button 的 gap 6px、Banner 的 10px / 14px 因无同值令牌放行。同时把 test_component_css_uses_tokens_for_font_radius_and_motion 的 docstring「尺寸字面量可接受」改成「无同值令牌的尺寸可接受」。
3. 文件头 docstring 的「两处真缺陷」按实际情况改；缺陷修好后不应再有「已知缺陷」说明。
4. 可选的变异：把 resolveAttemptState 改回普通取值；去掉 B2 的屏蔽。

## 9. 非阻塞观察与需协调人决定

- 本次是最后一个 attempt。attempt-003 若仍不过，需站主定夺（出 v4 合同 / 追加 attempt / 规划端直接修）。
- ACCEPTED_WITH_EXCEPTION 的 warning 色小圆点：UI 文档 §3.4（第 157 行）与画布都有，合同 v3 的状态表只写 badge-check，候选没做、报告没提。按合同字面不算违规，所以没进阻塞项；是否并入返工范围请协调人决定（并入时在返工任务书里补一句即可：圆点用 --tt-tone-warning-fg，描边用 --tt-tone-success-bg，aria-hidden；白盒的图标比对看 svg 子节点，不受外层包装影响）。
- 工具链版本偏旧（见 §6）：功能无影响（V01 全绿）。我无法离线核对这些版本有无已公开的安全公告。建议本片接受、另片处理——升级会动锁文件与全部检查，风险会落在最后一个 attempt 上。请协调人让站主知情。
- 合同措辞：INFRA_FAILURE 合同写 server，UI 文档写 server-crash，画布用 server-crash 形状，候选跟画布并命名为 ServerIcon。这是合同与设计文档之间的出入，不是执行端的错；后续合同版本请对齐。
- 低优先级建议（不进阻塞项）：Banner / StatusTag / Button 在固定属性之后展开 rest，调用方可以覆盖 role、title、aria-busy，从而破坏合同的不变量；Banner.css 的关闭按钮 24px 可用 --tt-space-6；tokens.css 用了两个 :root 块（合同写一个），语义相同。

## 10. 核对范围与局限

- 只读静态审阅，没有运行任何测试或命令。读了：合同 v3；候选补丁除 package-lock.json 外的全部源码（并核对工作树里的文件与补丁一致，变异后已还原）；战前基准 G9 段；战后白盒关键段；15 条变异记录与 M05 / M12 / M13 日志；白盒日志（58 passed、3 xfailed，20.32 s）；V01 日志（75 passed，24.75 s）；执行报告、概述、scope.json；事件流里的令牌比对与许可来源；UI 文档 §3.4 与画布。
- 凡「静态推演、未实跑」的结论已逐处标出：B3 的 CSS 多行、B4 的重写已定义变量、B1 修好后的预期输出。

Verdict: REVISE
