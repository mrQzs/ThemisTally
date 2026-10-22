# 复审记录：t014-desktop-cleanup2 attempt-002（七端信箱 hub）

- 合同：t014-desktop-cleanup2.v2（base b820234a4c61867520aa896cf13796444abbd245）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T014-7 终审报告（audit-sonnet）

## 结论
通过。候选 attempt-002 忠实于合同 `t014-desktop-cleanup2.v2`，DoD D01–D08 逐条独立核对成立，无阻塞项，不返工。

## 我实际看了什么（不采信执行端自述）
- 候选补丁：`.agent/runs/t014-desktop-cleanup2/attempt-002/candidate.patch`（27 文件）
- 内核独立复跑：`attempt-002/checks/01/checks.json` + `G01.log`/`R01.log`/`V01.log`/`V02.log`/`V03.log`
- 内核范围核验：`attempt-002/scope.json`（27 文件、violations=[]、head_after=b820234a4c = 合同 base_sha）
- 门禁端：`T014-6-gate-post/report.md`、`evidence/whitebox-*.py`（9 条）、`evidence/mutate-*/mutations.json`（21 条）
- **现场源码**：post-attempt-002 工作树里的实际文件（不是补丁文本）——本次所有实现判断都基于现场文件
- 画布原文：`docs/ui-design/pages/05-attempt-详情-Themis-Tally.html`（summary.md 那一行）、`12-设置-Themis-Tally.html`（:427/:428）
- 合同与站主来信：`t014-desktop-cleanup2.v2.md`（含三封站主拍板原文）

## DoD → 实现 → 证据映射（每条 DoD 都有真实证据，没有只能人工审阅的项）

| DoD | 现场实现（我核对的） | 证明它的断言 | 证据来源 |
|---|---|---|---|
| **D01** 单一来源 | `copyText`/`COPY_RESULT_TEXT` 只在 `src/components/copyText.ts`；`CopyNote` 定义只在 `src/components/CopyNote.tsx`；`ArrowRightIcon/FileTextIcon/ExternalLinkIcon` 的 export const 只在 `src/icons/index.tsx`；六份重复件（tasks-copy.ts、tasks-icons.tsx、tasks/common-CopyNote.tsx、shellpages/copy.ts、shellpages/icons.tsx、readonly2/common-icons.tsx）现场 ls 确认都不在；全仓 grep 只命中新测试里的路径清单字符串，无人再从它们引入；`components/index.ts` 未动 | G01 `test_d01_copy_text_single_source`/`copy_note_single_source`/`icons_single_source`/`deleted_duplicates_gone_and_unimported`/`components_index_unchanged`（sha256 逐字比对）；执行端 `cleanup2-static.test.ts` 的 5 条（defsOf/字面量唯一性/存在性/引入解析扫描） | G01.log 17 passed；我的 grep 复核一致 |
| **D02** 图标合并 | `icons/index.tsx` 末尾（ArrowRightIcon 之后）追加：出处注释 + `FileTextIcon`(5 path) + `ExternalLinkIcon`(3 path)；path 与合并前逐字相同（我逐条比对了补丁里被删的三份重复件的 path）；沿用 `<Svg {...props}>` 与 `IconProps`，块内无 fill/stroke；注释含 Lucide/ISC/file-text/external-link/summary.md/:427/:428 且无 `<path`/`<circle`/`<polygon`/`<rect` 字样；四处调用方宽高 14/16/16/14/16 未变 | G01 `test_d02_icons_appended_to_shared_only`（基线前缀 sha256 + path 逐字 + 注释词 + 注释无标签字样）、`test_d02_icon_render_sites_unchanged`；白盒 `test_icons_shared_paths_verbatim_and_reuse_svg`、`test_icon_callers_from_shared`；执行端 `cleanup2-render` 的 DOM 断言（class tt-i / width / height / viewBox / fill / stroke / stroke-width / aria-hidden + path 列表）；`tasks-static` 保留的画布逐字比对 | G01 + 白盒 + 我的画布人工比对 |
| **D03** 共用 CopyNote | `components/CopyNote.tsx`：`result==null → return null`；`<p className="tt-copy-note">{COPY_RESULT_TEXT[result]}</p>`；无 role、无 toast；从 `../components` 引入；顶部 `import './CopyNote.css'`；全文（含注释）无三条结果文字。`CopyNote.css`：margin 0 / font var(--tt-text-caption) / color var(--tt-text-3)。`readonly1/common-CopyNote.tsx` 只转出 CopyNote 与 CopyNoteProps | G01 `test_d03_shared_copy_note_module`、`test_d03_copy_note_css`（含「样式表被 import」）、`test_transitional_d03_readonly1_reexport_and_overview_import`；白盒 `test_copy_note_structure`/`copy_note_css_rule`/`readonly1_reexport_only`；执行端 `cleanup2-shared` 的 DOM 断言（null → `container.innerHTML==''`、P 标签、className、无 role、无内联 style） | G01 + 白盒 + V02.log（cleanup2-shared 5 例真跑） |
| **D04** 复制结果文字一致 | 五处调用方都从 components 取：`TaskListView:7/:25`、`AttemptDetailView:5/:16`、`tab-Report:4/:7`、`overview-AttemptList`（经 readonly1 转出）、`FirstRunView:13` + `span.tt-fr__copyres` 结构与 `COPY_RESULT_TEXT[copyResult]` 照旧 | G01 `test_d04_copy_wiring_merged_sites`；白盒 `test_t011_copy_callers_from_shared`/`test_first_run_copy_from_components`；执行端 `cleanup2-render` 的 5 个用例 × 3 种剪贴板状态 = 15 次断言，期望值全部取自 `COPY_RESULT_TEXT`（无字面量） | G01 + 白盒 + V02.log（cleanup2-render 7 例真跑） |
| **D05** 首启页值单行省略 | `first-run.css:52`：`.tt-fr__val { flex: 1; min-width: 0; font: var(--tt-mono-md); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }` | G01 `test_d05_first_run_val_single_line_ellipsis`（一条规则同时满足六项 + 样式表仍被 FirstRunView import）+ G01 的 D07 构建层（`dist/assets/*.css` 里 `.tt-fr__val` 必须带 `--tt-mono-md` 与 `text-overflow: ellipsis`）；白盒 `test_first_run_val_single_line_ellipsis`（M21 变异） | G01.log + 白盒 |
| **D06** 遗留注释一致 | `shellStub.ts` 头注释第 4 行改为「openExternal 只校验协议（http 与 https），不打开任何东西。」；实现仍是 `/^https?:\/\//` 校验、reject 非 http/https、不记录网址 | G01 `test_d06_shellstub_comment_matches_impl`（注释子句 + 实现体双向查）；白盒 `test_shellstub_comment_and_impl`（M19 注释、M20 实现） | 合同给 D06 的证据就是 review；我人工核对了注释与实现（两处都读过） |
| **D07** 回归与构建 | — | 内核 `checks.json`：G01 exit 0、R01 exit 0、V01 exit 0、V02 exit 0、V03 exit 0，`covers_all_required=true`、`all_required_passed=true`、`modified_by_checks=false`、`candidate_files_modified=[]`、`unexpected_files_by_checks=[]` | G01.log「17 passed」、R01.log「532 passed」、V01「built in 1.01s」、V02.log「Test Files 90 passed / Tests 811 passed」、V03.log「契约检查：通过，无违规。」 |
| **D08** 范围与测试完整性 | `scope.json`：A5 M16 D6 T0，27 个文件全部 in_scope，violations=[]、warnings=[]；八份测试在位；五份旧测试用例数未降；无 skip/only/todo/xit/xtest/xdescribe/.fails | G01 `test_d08_executor_tests_present_and_clean`、`test_d08_old_test_intents_moved_to_shared`；V02.log 实测：tasks-static 9、shellpages-static 8、readonly2-static 8、cleanup1-static 9、cleanup1-merge 7，cleanup2-render 7、cleanup2-shared 5、cleanup2-static 7 | G01.log + V02.log + scope.json |

## 站主拍板 Q1–Q5 落实情况（全 A，均已落实）
- **Q1**：新建 `src/components/CopyNote.tsx` + `CopyNote.css`（类名 tt-copy-note、margin 0、--tt-text-caption、--tt-text-3、不设 role）✔；删 `pages/tasks/common-CopyNote.tsx` ✔；`readonly1/common-CopyNote.tsx` 改成只转出 ✔；任务页复制结果照 T011 §7 改正（原来 `tasks-copy-note` 且无 CSS 规则，现走共用件）✔。
- **Q2**：`FirstRunView` 的 span 照旧（`span.tt-fr__copyres` + `COPY_RESULT_TEXT[copyResult]`），只改引入 ✔。
- **Q3**：六份重复件直接删，不留转出壳 ✔（唯一例外 `readonly1/common-CopyNote.tsx` 是站主 Q1 明确要求的只转出件）。
- **Q4**：`components/index.ts` 一字未动（G01 sha256 逐字比对通过），CopyNote 按路径引入 ✔。
- **Q5**：`.tt-fr__val` 改 `font: var(--tt-mono-md)` 并加单行省略，保留 flex 1 / min-width 0 ✔。

## 仓库外事实核对（站主 13:27 那封 `--facts-checked`）
- 我直接读了画布原文：05-attempt 画布 summary.md 那一行的五条 path 与 12-设置画布 :427（FileTextIcon 五条）、:428（ExternalLinkIcon 三条）与候选 `icons/index.tsx` **逐字相同**。
- FileTextIcon 用的是**早期非圆角**写法（`M15 2H6a2 2 0 0 0-2 2v16...`、`M14 2v4a2 2 0 0 0 2 2h4`），**没有**改成 lucide 1.59.0 的圆角写法 ✔（站主原话「验收比的是画布与合并前」）。
- ExternalLinkIcon 三条与 lucide external-link 逐字相同 ✔。
- 出处注释写明 Lucide / ISC / file-text / external-link 与画布行号 ✔；THIRD_PARTY_NOTICES 的版本号未动 ✔（不在 Scope，也确实没改）。

## 门禁端举证是否可信（逐条判断）
- **白盒 9 条**：源码文本级断言，覆盖图标 path 逐字与 Svg/IconProps 复用、CopyNote 结构与 CSS 三声明、readonly1 只转出、T011/FirstRunView 复制接线、四处图标接线与宽高、.tt-fr__val 省略、shellStub 注释与实现。**不空心**：每条都有可失败的具体断言，且 `mutations.json` 里 21 条变异逐条「caught」，count_found 均为 1（锚点唯一，没被多份文本撑成假绿）。
- **变异覆盖**：13 个改动非测试文件每个至少一条变异（icons 3、CopyNote.tsx 3、CopyNote.css 2、readonly1 2、shellStub 2、tab-Summary 2，其余 6 个调用方各 1）——与 candidate.stat.txt 的非测试改动清单逐一对上，无漏网文件。
- **「没法变异的改动文件」**：六份已删文件——已不存在，无法变异，合理；它们的「已删且无人引入」由黑盒 G01 与执行端 `cleanup2-static` 的存在性 + 引入解析扫描双重守护，不算缺口。
- **结论：门禁端举证可信，无「等价变异测不出来」的情况。**

## JEV 两条需关注项的独立裁定
1. **「自行解读合同」p=0.90**：逐条看执行端的 4 条 interpretations，都不是未声明的解读——①`tasks-static` 的 FileTextIcon 断言改读共用件是合同 Step 9 明文要求；SearchIcon 断言从「已删文件里不重写」改成「共用件里恰一条」，是保留原意图的必要改写，且额外补了 tab-Summary 从 icons 引入 FileTextIcon 的断言；②tab-Report 复制钮用 TextViewer 的 aria-label「复制已显示的文字」是**事实**（`components/TextViewer.tsx:122` 我读过），不是为过测试而特判；③新文件 LF 行尾是仓库 autocrlf 归一化后的外观差异；④readonly1 保留两行说明注释不违反「只转出」（门禁与黑盒都按去注释后的代码断言转出集合）。JEV 这条判据在此不成立。
2. **「自述完成而无证据」p=0.86**：执行报告的 DoD 条目确实偏自述（没有逐条附命令与输出），但证据链是独立存在的：内核 checks.json 复跑了全部五项检查并留存日志，门禁端在隔离副本上跑了黑盒 + 白盒 + 21 条变异。我逐条回到源码核对后确认每条 DoD 都有真实证据（见上表），没有「只写了个 done」的项。这条不构成打回理由。

## 关于「空心断言 / 空心基线 / 回归护栏」的专项检查
- **空心基线**：G01 在基线上是「16 failed, 1 passed」，失败原因都写在断言消息里（文件不存在、规则不符），不是导入失败或收集错误 ✔。
- **空心断言**：CSS 类断言都有接线证据——`CopyNote.css` 被 `CopyNote.tsx` import（白盒 M05 删掉 import 会被抓），G01 的 D07 构建层要求 `dist/assets/*.css` 里出现 `.tt-copy-note`；`first-run.css` 要求 `dist` 里 `.tt-fr__val` 带 `--tt-mono-md` 与 `text-overflow: ellipsis` ✔。
- **弱化测试**：内核提示「删了 4 行含断言的代码」，我逐条比对是 `tasks-static` 的 SearchIcon 负向断言、`readonly2-static` 的 ExternalLinkIcon 断言、以及 `cleanup1-merge` 的两处 `.common-copy-note` 查询——全部被**等价或更强**的断言替换（同数量、无 skip/only/todo、旧用例数未降）✔。
- **为过测试的特判 / 空异常处理 / 悄悄扩范围**：未见。`scope.json` 零越界、零警告，`head_after` 仍是合同 base_sha；候选里没有对门禁文件的改动（tests/test_gate_* 本片不改，合同 forbidden_paths 已覆盖）。

## 非阻塞建议（不进阻塞项，仅供站主知悉）
1. `icons/index.tsx` 的出处注释用「与」连接 file-text 与 external-link，合同 Step 2 原文是「、」；语义相同、门禁只查关键词，未要求逐字，建议后续片统一措辞。
2. `readonly1/common-section.css` 里的 `.common-copy-note` 规则已成死代码（该文件按合同 Non-goals 本片不改，且新样式声明与旧规则等价，外观不变）；建议后续片清理。
3. `tasks-static` 的 SearchIcon 断言覆盖面略窄（只查 `src/icons/index.tsx` 里恰一条 `export const SearchIcon`；别的文件再定义一个不会被这条抓到）；建议后续片在 `cleanup2-static` 的图标单一来源扫描里把 SearchIcon 一并纳入。
4. `components/CopyNote.tsx` 从 `../components` 桶引入（合同 Step 4 原文如此，当前无环，因为 `components/index.ts` 不导出 CopyNote）；后续片若把 CopyNote 加进桶文件，注意形成环。

## 最终结论
**通过。** 不返工，无需退回任何对象。DoD D01–D08 全部成立，范围零越界，回归护栏未缩水，站主拍板与外部事实一致。

Verdict: PASS
