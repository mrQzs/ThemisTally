# 复审记录：t003-desktop-fonts attempt-001（七端信箱 hub）

- 合同：t003-desktop-fonts.v1（base 69970b0151cf656f01b2bddaf745f79dc04cd2c3）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T003-7-audit-post 终审报告（attempt-001 · 合同 t003-desktop-fonts v1）

结论: 通过

- 对象：候选补丁 attempt-001（候选树 e05918905f4c…，8 个文件，A3 M5 D0 T0）；合同 v1；战前基准 40 条、T002 回归 71 条、战后白盒 17 条、30 条变异的记录。
- 方式：只读（Read、Grep、Glob）。没有运行任何命令；V01、V02、白盒、变异的结果引自内核与门禁的记录。时间是推算值（工具里没有时钟，按开工信 14:45:32Z 起算）。
- 无阻塞项。有 1 处合同字面偏离（notices 版权格末尾的括号注释，§4.1），裁定为不阻塞；建议见 §7。

## 1. D01–D07 逐条核对

| DoD | 独立证据（执行端之外） | 我读到、核对的 | 结论 |
|---|---|---|---|
| D01 | V01：S1 test_d01_fonts_css_two_font_faces、S2 test_d01_main_imports_fonts_css、S3 test_d01_fonts_only_via_fonts_css、P4；白盒 test_fonts_css_two_faces_exact_descriptors、test_main_tsx_imports_in_order；变异 M01–M10 全抓 | desktop/web/src/styles/fonts.css:1-17 与合同第 1 条建议全文逐字相同；src/main.tsx:4 的 import './styles/fonts.css' 紧在 tokens.css（:5）之前，其余行没动；src、index.html、vite.config.ts 里没有 data:、http(s)://、@import、local(、unicode-range、?url、FontFace、document.fonts、preload | 成立 |
| D02 | V01：P2、P3、P4、P5（前置 P1、守卫 P7），内核在 fresh 工作区复验，候选树与检查前后一致 | public/ 下只有 Lucide 许可与 OFL.txt，没有字体；fonts/ 仍是 5 个文件；构建与字节比对由 P2、P4 机械证明（我没自己算 sha256） | 成立 |
| D03 | V01：S5、S6、S7、P6；白盒 test_ofl_copy_*、test_notices_*（3 条）；变异 M11–M15；review（本节） | public/licenses/OFL.txt 与 fonts/OFL.txt 都是 113 行；事件流 8993 行起的命令是 cp fonts/OFL.txt public/licenses/OFL.txt（符合合同「文件复制，不手抄、不从 git show 生成」）；notices 逐字段对 SOURCE.md、OFL.txt：版本 0.36.0（:24）、许可 SIL Open Font License 1.1、来源与压缩包名、wawoff2 2.0.1 默认参数、两个 woff2 路径、许可原文路径，版权 4 行逐字等于 OFL.txt 前 4 行（H4 由此完成）；Lucide 一节原文保留，只有许可原文的链接目标改成 public/licenses/lucide-1.59.0-LICENSE.txt（:15，文件存在） | 成立；1 处字面偏离见 §4.1 |
| D04 | V01：S8、S9、P8（7 条探针）、P1；白盒 test_specimen_*（4 条）、test_app_css_*（2 条）；执行端 Vitest 4 条；变异 M16–M28 | App.tsx:53-82 样张节在 `</header>`（:51）之后、Button 节（:84）之前；3 组 × 4 行；组旁标签「Regular 400」「500 按 Regular」「SemiBold 600」；我手算去掉两端竖线后的列数：13 个汉字 = 26，26 个字母，26 个数字，4+1+11+1+6+1+2 = 26；整节没有 button、a、input；App.css:56-70 三条规则各自 font: var(--tt-text-md / --tt-text-md-medium / --tt-title-sm)，其后紧接 white-space: pre、font-variant-ligatures: none；外框 1px solid var(--tt-border)、底色 var(--tt-surface-1)、padding 与 gap 取 --tt-space-*；没有 letter-spacing 与字面量颜色 | 成立；对齐、字重外观仍待人看（H1、H2） |
| D05 | V02：内核 fresh 工作区复验 71 passed（checks.json：all_required_passed、covers_all_required） | 日志是 71 个点，没有 s、x、F | 成立 |
| D06 | 内核 scope.json | ok；A3 M5 D0 T0；violations、warnings 为空；head_after 等于 base_sha；candidate.patch 里没有 fonts/、tokens.css、base.css、package.json、锁文件、index.html、vite.config.ts、scripts、既有组件与测试、门禁、docs | 成立 |
| D07 | review（本节）+ V02 的 test_d03_new_tests_not_skipped + 白盒 test_executor_vitest_file_is_not_weakened | 差异里没有删除，没有改既有测试；新增的只有 tests/font-specimen.test.tsx（72 行，4 条 it，无 skip、only、todo，没有被注释掉的断言） | 成立 |

## 2. 候选源码审读（全绿不等于对）

- 没有迎合门禁的写法：8 个文件里搜 gate、probe、whitebox、baseline、process.env、@ts-ignore、TODO、skip、only，无命中；没有空的异常处理；没有按测试输入写的特判。
- 样张文字就是合同建议的四行，不是为过测试调出来的；12 行逐行写出，有重复，但不是缺陷。
- font 简写会把 font-variant-ligatures 重置为 normal（base.css:9 的 .tt-app 虽设了 none，样张行的 font 声明会覆盖继承）。候选在三条行规则里 font 之后各自再写一次 none，顺序正确——这是我一审第 10 节点名要看的一条。
- 样张行没有被 base.css 其它规则覆盖：.tt-app button/input… 的 font: inherit 不涉及 span；行规则（属性加类）的特异性高于 .tt-app。
- 500 组落在 300–500 的 Regular 区间，600 组落在 600–800 的 SemiBold 区间，不会合成粗体（静态推演，H2 由人确认）。
- data-font-specimen、data-specimen-row 不带值：React 对 data-* 渲染为 'true'，属性选择器照常匹配；P8 与执行端 Vitest 都通过。

## 3. JEV 两条「需关注」

### 3.1 自行解读合同：不成立，不要求改动

- 判据：AGENTS.md 把两种情形分开。合同内部矛盾 → 写进 contract_conflicts 并把相关 DoD 标 blocked；合同没写死、有不止一种读法 → 按最合理的读法继续，写进 interpretations，命名、函数拆分这类实现细节不用写。
- 执行报告的 contract_conflicts 为空，interpretations 有 2 条。逐条判断：
  1. README 目录行的位置（fonts/ 行在 public/ 块之后、THIRD_PARTY_NOTICES.md 之前；fonts.css 行在 base.css 之后）：合同第 6 条只写「加两行」和两行的文字，没给位置。没写死，不是矛盾；位置合理。属 interpretations。
  2. 版权格用 <br> 分行：合同第 4 条要求「各一张表」，又要求「版权：照抄 fonts/OFL.txt 的前 4 行」。两者不冲突：表格单元格里放多行本来就得用 <br>；空格连接或放在表后的引用块也合规，合同没选。门禁自己的正确样本（good_notices）和我一审第 2 节第 5 条都按 <br> 读。属 interpretations。
- 事件流 19788–19991 行：执行端先列了 4 条候选解读，再按「实现细节不用写」主动去掉 2 条（样张包裹元素的类名；data-font-specimen、data-specimen-row 写成不带值的属性），只留 2 条有实质分叉的。去掉的 2 条确属实现细节。
- 另有几处同类细节没列：notices 末尾那句说明放在表外；三条字重规则各自重复 white-space 与 ligatures 声明；12 行样张逐行写出。都不需要列。
- 一处瑕疵：版权格末尾的括号注释不是「解读」，是多写了合同没要的字，执行报告没有披露。并入 §4.1 裁定，不单独要求改报告。

### 3.2 自述完成而无证据：不成立

- 每条 DoD 都有执行端之外的独立记录（§1 表）。执行报告对 D01–D04 逐条点了 V01 的测试编号（S1/S2/S3，P2–P5，S5/S6/S7/P6，S8/S9/P8），编号与 test_gate_t003_baseline.py 的 docstring 一一对得上；D05 引 V02；V01 的 40 passed、V02 的 71 passed 被内核 fresh 工作区复验。
- D06 的证据按合同是 scope，D07 的证据是 review，执行端没有命令可贴；独立记录是内核 scope.json 与本报告。报告里 D06 只有叙述、没贴 git status 输出，这不算无据。内核备注的 8 条掩盖退出码的写法都不是测试或检查命令（内核已判明）。
- D05：V02 71 passed，内核复验。D07：差异里没有删除、没改既有测试（D0；既有两份测试与 tests/test_gate_*.py 都不在补丁里）；新增测试文件无 skip、only、todo（我读了全文；V02 的 test_d03_new_tests_not_skipped 通过；白盒 test_executor_vitest_file_is_not_weakened 通过）。两条证据齐全。
- 报告里的描述性数字（cmp 相同、4820 字节、npm test 35 passed）是自述：cp 命令在事件流里、两份 OFL 都是 113 行，可以印证；35 passed 我没有独立印证，但它不是任何 DoD 的依据（P1 另查 npm test 通过）。
- H1–H6：报告把它们列为「人工验收项，不由执行端代做」，H5 按 Non-goals 留给设置页那一片，H1–H3 写明需浏览器核对；没有一条写成通过。
- 结论：没有证据不足的 DoD，不阻塞。

## 4. 门禁留给终审的两条事项

### 4.1 版权格末尾的括号注释：字面违反，不违反意图；不阻塞

- 事实：THIRD_PARTY_NOTICES.md:26 版权格第 4 行末尾有「（照抄 `fonts/OFL.txt` 前 4 行）」。这是合同第 4 条给执行端的指令用语，被带进了成品；SOURCE.md 和 OFL.txt 里没有它，合同写的是「只写 SOURCE.md 与 OFL.txt 里有的内容」，所以字面违反。执行报告只披露了 <br> 分行，没提这句。
- 不阻塞的理由：(1) 内容属实，只是指向 fonts/OFL.txt 的出处说明，没有新增任何版权、许可、版本、来源事实，H4 的一致性不受影响；(2) 四行版权声明逐字完整，OFL 的随包义务（版权声明加许可原文）由 public/licenses/OFL.txt 履行；(3) 没有 DoD、门禁断言或下游依赖这句话（白盒显式容许第 4 行末尾的全角括号，基准 S6 只做包含判断）；(4) notices 在 desktop/web/ 根下，不进 dist；(5) 返工要用掉第 2/3 次 attempt（执行约 26 分钟，外加两份门禁复跑和再审），代价远大于收益，还可能带进新的偏离。
- 可选：规划端集成时顺手删掉这句，或设置页那一片重写 notices 时删；删与不删，基准与白盒都过。

### 4.2 S6 对版本号偏宽：接受，只作提示；不改基准，不退回门禁

- 对本片的影响为零：候选的「版本」格（:24）恰为 0.36.0；白盒 sarasa['版本'] == '0.36.0' 通过；M12（版本格换成『未标注』）被白盒抓住。
- 残余只在将来：基准留在仓库里而白盒不入库时，有人删掉版本行、只留来源里的 v0.36.0，基准抓不到。这是下次热修补或新基准顺手补的事，不是本片通过的前提。

## 5. 任务书 C 部分的其余核对

- Scope：补丁只含合同允许的 8 个文件（改 5：README、THIRD_PARTY_NOTICES、App.css、App.tsx、main.tsx；增 3：fonts.css、public/licenses/OFL.txt、tests/font-specimen.test.tsx）。forbidden_paths 都没出现；scope.json ok。执行端工作目录里新增的 .pytest_cache、dist、node_modules 被 .gitignore 忽略，不在补丁里。
- 依赖：package.json、package-lock.json 不在补丁里；不写 .npmrc（V02 的 test_g1_no_npmrc_anywhere 随 71 passed 通过）。
- 令牌：tokens.css 不在补丁里；App.css 新增的样式只引用令牌，用到的 --tt-space-1、--tt-space-3、--tt-border、--tt-surface-1、--tt-text-md、--tt-text-md-medium、--tt-title-sm 在 tokens.css 里都有定义；check:contract 在 P1 里退出 0。
- 字体：只经 fonts.css 引用；public/ 没有字体；fonts/ 仍是 5 个文件；dist 恰两个 woff2 逐字节相同、用 ./ 开头的相对地址、无 data: 与外部地址（P2–P5 通过）。
- 许可：见 §1 D03；dist/licenses/OFL.txt 与副本逐字节相同（P6）；Lucide 一节与链接修正在合同范围内。
- 样张：见 §1 D04；字符只含汉字和可打印 ASCII，避开 #、->、=>。
- README：只动三处（目录约定加 fonts.css 与 fonts/ 两行，main.tsx 一行，licenses 一行）；命令节、令牌规则、门禁探针目录节原样；T002 的 G1 通过。
- 站主范围：没做设置页「关于」的许可列表（notices 里只有合同要求的那一句说明）；没改字体栈与令牌；没碰 Electron。

## 6. 门禁与变异记录

- 内核 check（checks.json）：fresh 工作区，候选树 e05918905f4c…，检查前后树一致；V01 40 passed（约 22 秒）、V02 71 passed（约 24 秒），日志全是点，没有 s、x、F，所以 P 系列没有被 conftest 跳过。
- 战后门禁：白盒 17 passed；30 条变异 30 caught、0 missed、0 skipped、0 error，old 片段各恰一次；没有声明等价的变异，没有 candidate_defects 要裁定。M29 的返工只是变异清单的问题，不涉及候选。
- 变异覆盖 7 个改动文件；没有 dist 侧变异，靠基准 P2–P6 和自检的 17 种合成变异，不算缺口，不退回战后门禁。

## 7. 非阻塞建议（不进阻塞项）

1. （可选）删掉版权格末尾的括号注释，见 §4.1。
2. 白盒入库风险：test_notices_structure_and_sarasa_fields 断言 notices 恰两节，test_app_css_frame_and_tokens_only 断言样张规则恰 5 条，test_specimen_* 钉死 12 行，test_readme_directory_convention_lines 钉 README 行序。若并入仓库，下一片加第三方条目或把陈列页移出根路由时会变红。仓库里没有 T002 的白盒文件，先例是不并入；建议照旧不并入，要并入就按 test_transitional_ 命名并放宽 notices 的节数。
3. S6 松紧见 §4.2：下次动基准时把「版本一格恰为 0.36.0」并进去。
4. tokens.css 第 3 行的注释「本片不随包字体，也没有任何字体引入规则」现在读起来过时（本片指 T002）。tokens.css 一字不改是合同要求，所以留给以后有权改令牌的片。
5. H1 的线索，未验证：较新的 Chromium 对汉字与拉丁字母、数字紧邻处有 text-autospace 的自动间距，我不能在本环境确认默认值，也不知道它对 white-space: pre 的等宽对齐有没有影响。样张行的汉字与 ASCII 之间都隔着空格，不会触发；真实数据里（如『共12项』）可能触发。H1 时可以多看一行中英文直接相连的文字；若错位，后续片在 base.css 里加 text-autospace: no-autospace（本片 base.css 禁改）。
6. 结项汇报向站主交代：Lucide 许可链接修正（任务书之外的小改）、许可副本沿用站主原名 OFL.txt、README 纳入、H1–H6 留给人。

## 8. 留给人（H1–H6），都不算通过

- H1 对齐：样张各行右端竖线是否在同一条竖线上（Regular、SemiBold 各看一组，暗色、亮色各一次）。
- H2 字重与字体来源：SemiBold 明显比 Regular 粗；500 组与 400 组一样、不是假粗体；Rendered Fonts 里汉字与英文都是 TT Sarasa Mono SC。
- H3 网络：两个 woff2 从同源相对地址加载，没有外部请求。
- H4 许可记录：本报告 §1 D03 已读（与 SOURCE.md、OFL.txt 一致，唯一偏离是 §4.1）。
- H5：「设置 › 关于」列出 Sarasa Gothic，本片不做，是设置页那一片的待办。
- H6 体验：首屏 swap 换字体的闪动是否可接受；产物多约 17 MB（站主已接受）。

## 9. 没验证到的

- 没有运行 V01、V02、白盒、变异，没有 npm、pytest、git；结果引自内核与门禁记录。
- 没有浏览器渲染：H1、H2、H3、H6 全部没看。
- 没有自己计算 woff2 的 sha256 与 OFL 副本的字节；靠 S4、P2、P7、S5、P6，以及我对两份 OFL 的行数核对（都是 113 行）。
- 事件流只读了与解读有关的段落（19770–20009 行）和按关键字的抽查（风险命令、凭据、工具错误），不是通读。

Verdict: PASS
