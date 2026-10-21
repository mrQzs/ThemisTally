# 复审记录：t009-desktop-pages-a attempt-002（七端信箱 hub）

- 合同：t009-desktop-pages-a.v3（base b8df7382cd42bcbb1a6a932a9af1769578bf9ee0）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T009-7-audit-post 终审报告（attempt-002）

结论: 通过

## 摘要
attempt-002 只做 B1：`overview-OverviewView.tsx`、`roles-RolesView.tsx`、`runtimes-RuntimesView.tsx` 各自在组件 import 之后追加 `import './<前缀>-styles.css';`，并在 `tests/page-css.test.ts` 增加一条『三份页面样式表各被 src 下一个 .ts/.tsx 模块 import』的断言。候选补丁只有这 4 个文件（3 视图 + 1 测试），全在 Scope，无额外行为改动、无 CSS 取值/px/令牌改动。B2（门禁端基准热修补）与 B3（战后门禁白盒 + 变异）都在 `tests/test_gate_t009_*.py` 里补齐并已实跑：V01 56、V02 333、V03 7、白盒 464、变异 161/161 caught。上一轮 B1/B2/B3 三条阻塞项全部解决。五条遗留项（图标、.rt-cmd 行内、色调条位置、buildHash 重编码、aria-controls 悬空）在 attempt-002 里全部仍在，但都不是阻塞项，留给后续视觉修整任务。JEV 三处疑点逐条裁定，均不构成缺陷或已被 B1/B2 消解。

## 1. B1/B2/B3 是否已解决

### B1【执行端】三份页面样式表接线——已解决
- 接线：`overview-OverviewView.tsx:9` 追加 `import './overview-styles.css';`，`roles-RolesView.tsx:10` 追加 `import './roles-styles.css';`，`runtimes-RuntimesView.tsx:20` 追加 `import './runtimes-styles.css';`。三处都在最后一条组件 import 之后（overview 在 `overview-logic` 之后、roles 在 `roles-logic` 之后、runtimes 在 `runtimes-logic` 之后），满足『晚于 common-section.css 载入』。
- 级联顺序：`common-Section.tsx` 由子组件（AttemptList/ConfigChanges 等）间接引入，其 import 求值早于视图末尾的页面样式表；门禁在构建产物 `dist/assets/index-DacxdIbz.css` 复核 `.common-section{…}`（偏移 28403）先于 `.ov-judge{…}`（偏移 30038），同特异性下金色左边框不被 border 简写盖掉。执行端偏离说明『import 排序、不改 CSS 选择器』成立。
- `tests/page-css.test.ts`：新增 `sourcesUnder(process.cwd()/src)` 递归扫描 + 正则 `import\s+['"]\./<name>['"]` 的断言；原两条断言（§8 取值、只用令牌）逐字保留，未放宽。
- 范围：候选补丁只有 3 视图 + page-css.test.ts，均在 allowed_modified_files（page-css.test.ts 也在 allowed_new_files）；未碰 forbidden_paths、未碰其它 CSS/源码；CSS 取值、px 注释、令牌规则未动。
- 结论：B1 三项要改（视图 import、import 位置、page-css 断言）全部落实，且未引入额外行为改动。

### B2【门禁端，热修补】基准证明样式表被应用——已解决
- 新增 `test_d13_css_files_are_imported_into_app`（静态 import 图：从 `src/main.tsx` 顺 import 可达每一份 CSS；`css_wiring_problems`/`reachable_from`/`import_specs`/`resolve_import`）与 `test_d13_css_classes_in_built_bundle`（流水线：`npm run build` 后 dist/assets/*.css 含每份源 CSS 一个独有类，`css_classes` 从文件解析，不写死类名）。
- 自检：`test_gate_selfcheck_css_wiring`（含删 import、切断路由、import type/?inline/注释不算、动态 import/绑定 import 算、目录 index）与 `test_gate_selfcheck_built_css_problems`（含独有类缺失、共享类顶替、前缀相近类顶替）都在。
- 红/绿：新候选上两条随 V01 绿（56 passed 含它们，构建产物含 .ov-metric/.rl-card/.rt-ready）；旧候选（attempt-001 三份样式表无人 import）上，静态图到不了、构建产物无这些类，必红——逻辑成立。
- 未放宽：既有的 `css_value_problems`、`test_d13_css_values_match_section_8`、`test_d13_css_tokens_px_comments_and_w4`、`test_d01_tone_stripe_colors` 仍在、仍按 css_text 读文本，是『补充』而非替换。不写死类名（从文件解析）。
- 限制：本端无 shell、且 attempt-001 的基准测试副本未在 .agent 归档，无法做逐字节 diff；以上为结构性核对 + 门禁报告『只增不改』互证。

### B3【战后门禁】白盒与变异补接线——已解决
- 白盒新增两条：`test_wb_b3_page_stylesheets_are_imported_by_src_modules`（三份样式表各被 src 下 .ts/.tsx import，且必须在对应视图文件；common-section.css 有对照）与 `test_wb_b3_page_stylesheet_import_is_the_last_import_in_its_view`（页面样式表 import 是视图最后一条 import，且视图能到达 common-section.css）。
- 变异清单新增 4 条接线变异：`css.wiring-overview-import`、`css.wiring-roles-import`、`css.wiring-runtimes-import`（删 import）、`css.wiring-overview-import-before-components`（把 overview 样式表 import 插到组件 import 之前）。证据 `mutate-20261021T182815953687Z/mutations.json`：M130–M133 全部 status=caught，counts caught=161 / missed=0 / skipped=0 / error=0。M133 为 insertion_only（保留原 import 再插一条靠前的），但被『import 必须是最后一条』断言抓住（exit 1），仍覆盖了顺序语义。
- 白盒日志 `whitebox-20261021T182814602486Z.log`：464 passed。
- V01/V02/V03：以战后门禁报告第一节为准——V01 56、V02 333、V03 7，均 0 failed。

## 2. 五条遗留项的存留（attempt-001 终审第 5 节）

1. 指标卡图标——仍在。`overview-MetricCard.tsx` 渲染 `ov-metric__bar`/`ov-metric__label`/`ov-metric__num`，没有图标；合同 §4 写『图标同色』但未指定图标，属合同未写清。非阻塞。
2. `.rt-cmd` 行内 span 的 max-width/overflow——仍在。`runtimes-RuntimesView.tsx:62` 是 `<span className="rt-cmd">`（行内），`runtimes-styles.css:9` 的 `max-width: 280px; overflow: hidden` 对非替换行内框不生效（`white-space: nowrap` 有效）。非阻塞。
3. 色调条位置——仍在。`overview-styles.css` 里 `.ov-metric` 是 `display:flex`，`.ov-metric__bar` 是普通 flex 子项（width:3px, align-self:stretch），落在 20px 左内边距之后，不贴卡左缘；设计稿是绝对定位 `left:0;top:0;bottom:0;width:3px`。非阻塞。
4. `buildHash` 经 URLSearchParams 重编码——仍在。`router.ts` 的 `buildHash` 用 `new URLSearchParams(currentQuery)` 合并后 `toString()`，与『保留 mock 与其它参数、path 覆盖同名』的合并语义相符；重新序列化对 mock/group/tab 值无影响。非阻塞。
5. `aria-controls` 悬空——仍在。`roles-PresetsTable.tsx:89` `aria-controls={`rl-diff-${p.name}`}`，面板只在展开时存在（收起时指向不存在的 id），方案名含空格时 id 不合法；合同公共约定是『id 用 useId』。非阻塞。

另：`overview-styles.css` 的 `.ov-row__name` 只有省略、无 `font: var(--tt-mono-sm)`，与合同 §4『名称……等宽省略』的等宽缺一项（上一轮建议 S2），仍为非阻塞建议。

## 3. 对照画布的视觉差异：消失与残留
设计稿：`docs/ui-design/screens/Main.dc.html`（暗/亮主题、1024 窄窗口）。

### 已消失（B1 修复后样式表进构建、真实生效）
- 总览：`.ov-metrics` 四列网格、`.ov-metric` 卡外观（surface-1、1px border、radius-lg、overflow hidden、悬停 surface-2、内边距 3/4/3/5）、`.ov-pill` 计数胶囊、`.ov-judge` 金色左边框（3px accent，构建产物已证先于/后于顺序正确）、`.ov-row` 四列网格与悬停、`.ov-change` 五列网格、下一步/复制结果外边距——这些规则此前不打包，现在随 import 进入构建。
- 角色与模型：`.rl-*` 当前方案条（flex wrap）、角色卡两列网格与内边距、键值两列 64px、表格容器压过 .tt-table-wrap、profile/方案表最小宽（860/760）、差异面板（surface-2/radius-md/四列/减加底色）、最后一列靠右——全部生效。
- CLI 运行时：`.rt-*` 表格最小宽 900、最后一列靠右、命令单元格单行、就绪检查虚线空框（padding space-5、居中、1px dashed border-strong、radius-md）——生效。

### 仍在（五条遗留项，非阻塞，留给后续视觉修整）
- 总览指标卡：横向排列（设计稿纵向：标签行在上、大数字在下）、无 16px 图标、色调条是 flex 子项不贴左缘（设计稿绝对定位 left:0 宽 3px）。
- CLI 运行时命令单元格：`.rt-cmd` 行内 span 的 max-width/overflow 不生效，只靠码点截断（前 22 + ' … ' + 后 15）控宽。
- 角色页方案表：`aria-controls` 在收起时悬空、名称含空格时 id 不合法（可访问性小问题）。
- attempt 行名称：缺等宽字体。

以上残留不作为阻塞，写明留给之后的视觉修整任务。

## 4. JEV 疑点裁定
- 自行解读合同（p=0.77）：不成立为缺陷。执行端偏离『采用 import 排序方案、不改 CSS 选择器』，理由『构建产物已验证 .common-section 先于 .ov-judge，级联正确』。B1 原文明确给了两个选项（import 写在组件 import 之后 / 把选择器抬成 .common-section.ov-judge），选其一是按合同明列的菜单做，不是合同自相矛盾。已写入 interpretations。
- 自述完成而无证据（p=0.92）：B1/B2 后已消解。D01–D13 的 done 均有证据指向（V01 探针 + 战后门禁实跑；D01/D13 的样式生效现在由 B2 的 import 图 + 构建产物两条断言实证，不再是空心）。D14 执行端标 partial（V02 未自跑，因超时上限），但战后门禁已实跑 V02 333 passed，故 D14 也被覆盖。
- 误导（2.00/3）：不成立。候选补丁未改任何 CSS 文件，CSS 取值/px 注释/令牌规则确实未动（白盒 464 + V01 的取值/令牌/W4 断言佐证）；执行端报告声称的 dist 哈希 `index-DacxdIbz.css` 与门禁独立构建一致，无可被独立检查掩盖的误导性声称。
- 超出范围（p=0.23）：不成立。补丁仅 4 文件，均 in_scope（3 视图 allowed_modified + page-css.test.ts）。
- 弱化测试（p=0.07）：不成立。本轮测试改动只有 page-css.test.ts 一条新增断言（增强）；未改基准测试、未改 T001–T008 既有测试；shell-app.test.tsx 本轮未动。

## 5. 其余核对
- T006 加法：`router.ts` 的 `parseHash`、`useHashRoute`（返回 {route,navigate}）签名与行为不变，`navigate` 对无 `?` 的 path 行为不变；新增 `buildHash`、`activeNavigate`、登记 effect、`useAppNavigate` 为纯加法。`attemptGroups.ts` 的 `countByGroup`/`StatusCounts` 原样，新增 `AttemptGroup`/`ATTEMPT_GROUPS`/`groupOfState` 映射与合同 §1 一致。
- 写入口：三页所有写入口（保存为方案、新建 profile、切换、更改、编辑、删除、使用、扫描 PATH、手动登记、探测、模型、运行就绪检查）都经 `DisabledAction`；`src/pages` 下无 fetch/XMLHttpRequest/EventSource/WebSocket（grep 只命中 DisabledAction）。无网络调用、无本机服务接入。
- V01/V03 以战后门禁报告为准（V01 56、V03 7）；V02 由战后门禁实跑 333 passed。

## 6. 人工项（不算阻塞）
视觉对照（暗/亮主题、1024 窄窗口）、悬停手感、读屏、真浏览器里的点击导航（含 Ctrl 或中键点指标卡）；另加：指标卡色调条与图标、attempt 行名称字体、命令单元格宽度的目视。

## 7. 结论
通过。B1/B2/B3 全部解决，候选补丁干净、范围正确、未弱化测试，五条遗留项与若干视觉小差异仍存但不阻塞。建议内核 verdict=PASS 并合入本地分支，同时给站主汇报；残留视觉项（指标卡图标/纵向布局/色调条贴边、.rt-cmd inline-block、aria-controls 用 useId、.ov-row__name 等宽、命令单元格宽度目视）留给后续视觉修整任务。

## 8. 本端的限制
没有 shell 工具：没跑 `npm run build`、没看 dist、没重跑 V01/V02/V03；B1 的构建产物结论依赖战后门禁报告的独立复核与候选补丁/源码文本。没做基准测试的逐字节 diff（attempt-001 副本未归档），B2『未放宽』为结构性核对。没读 events.jsonl 全文。悬停/读屏等 DOM 行为依赖门禁与 JEV 记录，未独立复现。

Verdict: PASS
