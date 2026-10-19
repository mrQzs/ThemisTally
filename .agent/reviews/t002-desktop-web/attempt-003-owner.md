# 复审记录：t002-desktop-web attempt-003（站主）

- 合同：t002-desktop-web.v3（base a7193dc7b2b38bc1ec5c9dc8c823224cdd2edfe2），预算的第 3 次、也是最后一次 attempt。
- 内核 check --fresh：通过；范围违规 0。
- 问题：本 attempt 拿到的 plan.md 与 attempt-002 逐字节相同，执行说明里也没有终审的阻塞项；执行端从基线整份重写，改了导出名（lookupState、UNKNOWN_STATE），终审的 B1、B2、B4、B5 仍在。
- 战后门禁（gate-sonnet，白盒 108 条）：88 passed、20 failed，失败全部落在 B1、B2、B4、B5；B3 已满足。B1 是真崩溃：StatusTag 遇到 constructor 等 7 个与 Object.prototype 同名的状态码时 Element type is invalid。
- 结论：返工。预算用完，不再派遣；本 attempt 不并入，标记 ABANDONED。站主改由规划端在 attempt-002 的返工提交上补完。

## 战后门禁报告（摘录开头）

# T002-6-gate-post 门禁报告（attempt-003，终审后的第二轮）

## 1. 结论

- 新增文件：tests/test_gate_t002_whitebox.py（唯一改动；不改合同、基准、scripts、desktop/web）。
- 上一轮白盒不在本工作树里（工作树是基线 + attempt-003 候选），所以整份重写，而不是在旧文件上改。用例数 108 条（上一轮 58 + 3 xfail），数字不可直接对比。3 处 xfail 的断言都已写成普通断言（B1、B2、B3）。
- 候选上全量：python -m pytest tests/test_gate_t002_whitebox.py -q → 退出 1，20 failed、88 passed，25.75 秒。红的 20 条全部是终审 B1、B2、B4、B5。
- attempt-003 的候选是一份独立实现：状态表用 lookupState / UNKNOWN_STATE（没有 resolveAttemptState / FALLBACK_STATE），契约脚本的结构也与终审引用的 attempt-002 不同；执行报告完全没有提到 B1–B6。也就是说候选没有带终审要求的修复。
- 因此“白盒在候选上全部通过”这一条做不到，原因在候选，不在测试；变异检查要求基线绿，内核的 mutate --tree 在这个候选上跑不起来。
- 门禁没有在 desktop/web 留下未忽略文件：探针 gate-probe/probe-<uuid>.test.tsx 用 try/finally 删除并删空目录，末尾用例对比 git 状态，通过。node_modules 与 dist 是被忽略的。

## 2. 断言与终审 B1–B6 的对应（命令与退出码照抄）

全量命令：python -m pytest tests/test_gate_t002_whitebox.py -q → 退出 1（20 failed, 88 passed）。契约类断言在临时目录里直接跑：node scripts/token-contract.mjs --src <临时>/src --tokens <临时>/src/styles/tokens.css，不经管道。

| 终审 | 测试 | 候选上的结果 |
|---|---|---|
| B1 | test_status_tag_prototype_property_names_are_unknown_states[constructor/toString/hasOwnProperty/valueOf/__proto__/isPrototypeOf/toLocaleString]：不抛错；文本与 title 为状态码原样；data-tone=neutral；图标含 circle-help 特征路径 M9.09 9a3 3 0 0 1，且不同于 17 个已知状态的图标 | 7 条全红：Element type is invalid（lookupState 用 ATTEMPT_STATES[state] ?? 兜底，原型链上的函数/对象被当成已知状态） |
| B2 放行 | test_contract_b2_primitive_color_token_reference_is_not_a_named_color[8 个样本]：color:var(--tt-gray-1)、background:var(--tt-navy-500)、border:1px solid var(--tt-gold-500)、两层 box-shadow、多行 CSS、TSX 单行 color/border、TSX 多行 background 的 var 引用，均应退出 0 | 8 条全红：退出 1，输出 a.css:1: 规则2-写死颜色: gray（或 navy、gold）。原因：取值里按 [a-zA-Z]+ 取词，把变量名里的 gray/navy/gold 当成命名颜色 |
| B2 防偷懒 | test_contract_b2_named_color_in_fallback_is_still_flagged[5 个样本]：var(--tt-a, red)、var(--tt-gray-1, gray)、box-shadow 第二层 black、var(--tt-navy-500, navy)、TSX 的 var(--tt-a, red) 均应退出 1 并报该色 | 5 条全绿（退出 1，报对） |
| B3 TSX | test_contract_b3_tsx_multiline_style_object_named_color_is_flagged：style={{⏎ color: 'red',⏎ width: 3,⏎ }} 退出 1，行号取 style 起始行或命名颜色所在行（3 或 4） | 绿 |
| B3 CSS | test_contract_b3_css_multiline_box_shadow_named_color_is_flagged：box-shadow:⏎ 0 0 0 1px red; 退出 1，行号 3 或 4；另有 background:⏎ red、三行 border 的用例，以及多行 font-family/transition 不误报、多行 style 里非颜色键不误报的反面用例 | 全绿（候选按语句扫描声明，多行能判） |
| B4 | test_contract_b4_component_css_defining_a_token_is_flagged[defined-in-tokens-compact: .a{--tt-bg:1px}、multiline、alias-of-another-token、not-defined-anywhere]；test_contract_b4_definition_is_flagged_but_reference_in_same_file_is_not（只报重写那一行）；test_contract_b4_var_reference_to_defined_token_is_clean（.a{color:var(--tt-bg)} 退出 0）；test_contract_b4_tokens_file_itself_may_define_tokens | 令牌里已定义的三种写法与同文件用例共 4 条红（退出 0，输出 契约检查通过）；not-defined-anywhere、引用放行、令牌文件自己定义 绿 |
| B5 | test_component_css_spacing_literals_do_not_equal_any_space_token：src/components/*.css 与 src/App.css 里 padding、margin 及各边写法、gap、row-gap、column-gap 的 px 字面量，不等于令牌里任何 --tt-space-* 的值；令牌值从 tokens.css 读出，并校验包含 2/4/8/12/16/20/24/32/40/48/64；无同值令牌的值（6、10、14px）、高度、1px 边框不在此限 | 红：Banner、Button、Card、StatusTag、App 共 20 处（例如 Card.css padding:16px、gap:8px，App.css padding:24px、gap:12px） |
| B6 | 不是测试，见 §4 | — |

注意 B5 的范围：候选里 Card.css 与 App.css 也全是字面量，比终审写的 6 处多（终审基于 attempt-002 的代码）。

## 3. 其余断言（候选自己的写法与边界，全部绿）

- 契约脚本：十六进制位数 1–10（只有 3/4/6/8 判）、大写与 ts/tsx 字符串、href 的 #add 锚点、10 个颜色函数（含大写）与 calc 等不误判、允许值（transparent、currentColor、全局关键字、系统颜色）在 9 个颜色类属性里放行、20 个 CSS 颜色类属性与 20 个 TSX 颜色键逐个判且行号对、非颜色位置的颜色单词放行、变量整名比对（含下划线名）、ts/tsx 里的未定义变量、块注释与 // 注释不判且行号不变（URL 里的 // 不吞掉同行真违规）、CRLF 行号、输出格式与排序、同行两处违规两行输出、排除 *.test.*、令牌文件与非 css/ts/tsx 文件、--src/--tokens 不存在时以 0、1 之外的非零码退出且错误里写出路径、无 JS 堆栈。
- 静态 CSS：Button 高 28/32/36 与四个变体取令牌；Tag 高 20、内边距 0 6px、圆角 sm、字体、mono、八色调取 --tt-tone-<tone>-bg/-fg；StatusTag 高 22/20 与八色调；Card 底、边、圆角 lg、内边距解析为 16px、标题 --tt-title-sm；Banner 三色调取令牌；组件 CSS 引用的 --tt-* 都已定义，字体、圆角、时长取令牌；.tt-spin 的关键帧与减少动效时静止。
- 组件探针（vitest，node 直接调，不经 npm）：index 只导出五个组件；StatusTag 的边界输入（空串、空白、前后空格、大小写、HTML 字样、200 字符、中文，原样显示且不当 HTML）、默认 size 为 md、只有 RUNNING 的图标转动；Tag 默认值与 mono；Button 默认值与 type=button、加载文字替换 children / 无加载文字时回退 children / 非加载时忽略、转圈图标 aria-hidden、点击拦截；Card 只有 children 无头部、只有标题、只有操作、空卡片；Banner 的 info 关闭按钮（无 onClose 不抛错、有 onClose 点击一次触发一次）、role=alert 只在 danger；陈列页点击所有按钮也不发 fetch/XHR，主题按钮幂等且可逆。自检：探针里的用例恰为声明的那些、探针目录跑完不存在。
- 带 npm 的用例（变异检查跳过）：原地 npm ci 后 package.json 与锁文件摘要不变、无 .npmrc；npm test 通过；npm run check:contract 退出 0；npm run build 退出 0、有 dist/index.html、无 .tsbuildinfo。四条在候选上都通过。
- 收尾：git 状态与会话开始时一致，gate-probe 不存在。

## 4. B6：执行报告自检结论的核对

- D04 写「对合成样本逐类判违规、合法放行……证据 V01 G9」。V01 的 G9 清洁样本里没有 var(--tt-gray-*)/navy/gold 这类合法写法，所以这条“放行”结论覆盖不到 B2；B2 的 8 个合法写法在候选上全部退出 1（见 §2），“对合法写法放行”不成立。同样，“组件内自定义 var 判违规”只对令牌里未定义的名字成立，对已定义名字（B4）退出 0。
- D01 写「5 个原子组件……就位」，而 StatusTag 对 7 个原型属性名状态码会抛错（B1）。
- 执行报告里没有 B2–B4 的修复记录，也没有对应的测试名与命令输出，所以核对不了，视为无证据。
- 执行报告自称 npm test 为 9 个用例，npm test 在候选上通过，但这 9 个用例里没有 B2–B4 的合法写法用例。

## 5. 变异清单（mutation_spec）

命令 W1（唯一）：python -m pytest tests/test_gate_t002_whitebox.py -q -k 'not npm'。依赖全量运行已在原地装好 node_modules。不含 npm ci；总数 15；变异的 old 片段都是单行（工作树文件是 CRLF，多行片段会匹配不上）；没有声明 equivalent 的变异。

| # | 文件 | 变异 | 预期被谁抓住 |
|---|---|---|---|
| 1 | token-contract.mjs | 6 位十六进制改成 5 位 | test_contract_excludes_test_files…、test_contract_hex_is_also_found… 等 6 条 |
| 2 | token-contract.mjs | 4 位十六进制不再识别 | test_contract_hex_lengths…[4] |
| 3 | token-contract.mjs | 十六进制去掉位数边界 | test_contract_hex_lengths…[5/10/…] 共 4 条 |
| 4 | token-contract.mjs | 有违规也退出 0 | 35–39 条契约用例 |
| 5 | token-contract.mjs | *.test.* 不再排除 | test_contract_excludes_test_files… |
| 6 | token-contract.mjs | 行号按回车计数 | b3 多行与行号用例共 7–8 条 |
| 7 | token-contract.mjs | tsx 的 // 注释不再剥掉 | test_contract_tsx_line_comments_are_stripped_too |
| 8 | token-contract.mjs | TSX 的 boxShadow 不再算颜色类键 | test_contract_named_color_is_flagged_in_every_tsx_style_key |
| 9 | Button.tsx | 加载文字不再替换 children | probe button:loading_text_replaces_children |
| 10 | Button.tsx | 加载时不再 disabled | probe button:click_blocked…、button:loading_without_text… |
| 11 | StatusTag.tsx | RUNNING 图标不再转动 | probe status:only_running_icon_spins |

Verdict: REVISE
