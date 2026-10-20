# TASK: t007-desktop-evidence

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: a56eec8a7752dbca3d599aa5c794b6a5ed3ba6dc
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T007 第 5 片（桌面端前端证据组件）。

在 desktop/web/ 新增 6 个证据组件（文本查看器 TextViewer、安全 Markdown SafeMarkdown、思考档位 EffortPair、遮蔽值 MaskedValue、命令行 CommandLine、下一步 NextStep）与配套 CSS、3 个内部纯函数模块（components/evidence/ 下的 ansi.ts、viewerLines.ts、markdown.ts）、3 个图标（LockIcon、CopyIcon、EyeOffIcon），修 T005 终审的 S1–S6 与三处合同缺口，给 Banner 加可选 action，新建演示 EvidenceShowcase（不挂到陈列页）；差异视图拆到下一片；不改依赖、不改令牌、不改 App.css、不接服务。

## Non-goals
- 差异视图（目标 5）拆到下一片：本片不含其文件与测试。
- Ctrl+F 查找、虚拟滚动；日志跟随（7.15）、作业进度卡（7.17）；页面（任务列表、attempt 详情）；接本机服务、写操作、应用框架、工具链升级。
- 文本查看器不取数据、不翻页、不处理游标：页由调用方给。
- 「下一步」按 attempt 状态选文案（UI 文档 6.3 的表）留给页面那一片。
- Markdown 不支持下列语法，原样当文字：引用块、分隔线、Setext 标题、缩进代码块；图片、HTML、自动链接、删除线、脚注、任务列表；带标题的链接、引用式链接；列表项里除段落与子列表以外的块。
- T005 终审 S7（base-reset.test.ts 第 4 条空壳）与 S8（文档订正）：任务书没列，不做。
- README 的目录说明（任务书禁改），留给之后的片。

## Repository facts
- 入口：desktop/web/src/main.tsx 挂载 desktop/web/src/App.tsx（陈列页）；desktop/web/src/components/index.ts 统一导出四片组件；图标在 desktop/web/src/icons/index.tsx（Svg 包装为模块内私有，:7–26）；陈列页在 desktop/web/src/showcase/（现只有 FormsShowcase.tsx 与 showcase-forms.css）。
- 调用关系与现有约定（本片要改的点，均为规划报告 §10 已核实）：
  - Table.tsx:39–45 用下标 state 记当前行、:92 用它算 tabIndex；Table.css:20 表头左对齐、:38 只有 td.tt-num 右对齐，无 scroll-padding、无行焦点规则。
  - SegmentedControl.tsx:20–21 已算出 active、:54 tabIndex 只看 checked；Tabs.tsx:23 已算出 activeIndex、:64 每个页签都带 aria-controls 指向面板、:65 tabIndex 只看 selected。
  - useToggle.tsx:26–32 空格总 preventDefault、repeat 不切换；ConnectionPill.tsx:42–47 只在打开时处理 Esc（stopPropagation，不 preventDefault）。
  - Banner.tsx:13–39 没有放操作钮的位置，info 总有关闭钮；G2:410–460 钉住提示条行为。
  - showcase-forms.css:3–4 的 240px、560px 无注释；FormsShowcase.tsx:264–268 三个胶囊在 showcase__row 里左对齐。
  - App.css 有 showcase__section、showcase__h2、showcase__row、showcase__stack、showcase__muted、showcase__label 等类，EvidenceShowcase 复用，不改 App.css。
  - tokens.css 有 §2.10 列出的颜色、字体、圆角、间距、层级令牌；无 §2.10 之外的缺口。
  - THIRD_PARTY_NOTICES.md 记 Lucide 1.59.0（ISC）。
  - tests/conftest.py:33–41：带 pipeline 夹具的前端流水线在全量 pytest 里默认跳过，点名运行文件或设 TT_FRONTEND_TESTS=1 才跑；门禁必须点名运行。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD = base_sha = 40ed8f5049df7261413d5ba294c8ee208d15e8b1，git status 干净。tests/test_gate_t007_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在；T001–T005 门禁 tests/test_gate_t00{1,2,3,4,5}_baseline.py 都在，基线上应通过（回归）。
- 8214a1f 核对结果（站主要求）：8214a1f（T006 准备：退役 T003–T005 门禁里只在陈列页是根 App 时成立的过渡断言）是 base_sha 40ed8f5 的子提交——主仓库 reflog 记为 40ed8f5 → 8214a1f commit，即它在 base_sha 之后提交，不在 base_sha 之前。据此：base_sha 上仍存在 5 条过渡断言（tests/test_gate_t003_baseline.py:945、:956、:1024 共 3 条，tests/test_gate_t004_baseline.py:1885 1 条，tests/test_gate_t005_baseline.py:3057 1 条，已逐一核对仍在），按报告 §7.1 本片不碰它们、也不推翻它们（回归门禁要求它们仍绿）。合同不依赖 T006 的动作。
- 仓库外事实（已核实，以站主/内核记录为准）：
  - jsdom 25.0.1 没有 navigator.clipboard：复制只能走 onCopy 回调，测试不用打桩（Navigator-impl.js:12–27 只混入 ID/Language/OnLine/Cookies/Plugins/ConcurrentHardware）。
  - jsdom 25.0.1 的 KeyboardEvent 认 init 字典里的 repeat（测空格带 repeat 用）。
  - react-dom 18.3.1 把字符串子节点写成文本节点（createTextNode/textContent），不当 HTML 解析：W1、W2 的安全前提。
  - npm 上有 lucide 1.59.0，许可 ISC，与 THIRD_PARTY_NOTICES.md 一致（tarball sha256 d447a4c48f45a43d6e34bcf8981fd1036ed03ffddefe03342ba5a121a481c0e8）。
  - Lucide 1.59.0 eye-off 四条 path（站主 20261020T070452691698Z-owner-efbc3e 核实）：见 Behavior contract 第 1 条。

## Scope
- allowed_modified_files:
  - desktop/web/src/components/Table.tsx
  - desktop/web/src/components/Table.css
  - desktop/web/src/components/SegmentedControl.tsx
  - desktop/web/src/components/Tabs.tsx
  - desktop/web/src/components/Banner.tsx
  - desktop/web/src/components/Banner.css
  - desktop/web/src/components/index.ts
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/showcase/FormsShowcase.tsx
  - desktop/web/src/showcase/showcase-forms.css
  - desktop/web/src/components/TextViewer.tsx
  - desktop/web/src/components/TextViewer.css
  - desktop/web/src/components/SafeMarkdown.tsx
  - desktop/web/src/components/SafeMarkdown.css
  - desktop/web/src/components/EffortPair.tsx
  - desktop/web/src/components/EffortPair.css
  - desktop/web/src/components/MaskedValue.tsx
  - desktop/web/src/components/MaskedValue.css
  - desktop/web/src/components/CommandLine.tsx
  - desktop/web/src/components/CommandLine.css
  - desktop/web/src/components/NextStep.tsx
  - desktop/web/src/components/NextStep.css
  - desktop/web/src/components/evidence/ansi.ts
  - desktop/web/src/components/evidence/viewerLines.ts
  - desktop/web/src/components/evidence/markdown.ts
  - desktop/web/src/showcase/EvidenceShowcase.tsx
  - desktop/web/src/showcase/showcase-evidence.css
  - desktop/web/tests/evidence-text-viewer.test.tsx
  - desktop/web/tests/evidence-markdown.test.tsx
  - desktop/web/tests/evidence-effort.test.tsx
  - desktop/web/tests/evidence-atoms.test.tsx
  - desktop/web/tests/evidence-showcase.test.tsx
  - desktop/web/tests/evidence-static.test.ts
  - desktop/web/tests/forms-patches.test.tsx
  - desktop/web/tests/forms-patches-css.test.ts
- allowed_new_files:
  - desktop/web/src/components/TextViewer.tsx
  - desktop/web/src/components/TextViewer.css
  - desktop/web/src/components/SafeMarkdown.tsx
  - desktop/web/src/components/SafeMarkdown.css
  - desktop/web/src/components/EffortPair.tsx
  - desktop/web/src/components/EffortPair.css
  - desktop/web/src/components/MaskedValue.tsx
  - desktop/web/src/components/MaskedValue.css
  - desktop/web/src/components/CommandLine.tsx
  - desktop/web/src/components/CommandLine.css
  - desktop/web/src/components/NextStep.tsx
  - desktop/web/src/components/NextStep.css
  - desktop/web/src/components/evidence/ansi.ts
  - desktop/web/src/components/evidence/viewerLines.ts
  - desktop/web/src/components/evidence/markdown.ts
  - desktop/web/src/showcase/EvidenceShowcase.tsx
  - desktop/web/src/showcase/showcase-evidence.css
  - desktop/web/tests/evidence-text-viewer.test.tsx
  - desktop/web/tests/evidence-markdown.test.tsx
  - desktop/web/tests/evidence-effort.test.tsx
  - desktop/web/tests/evidence-atoms.test.tsx
  - desktop/web/tests/evidence-showcase.test.tsx
  - desktop/web/tests/evidence-static.test.ts
  - desktop/web/tests/forms-patches.test.tsx
  - desktop/web/tests/forms-patches-css.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/shell/**
  - desktop/web/src/pages/**
  - desktop/web/src/mock/**
  - desktop/web/src/api.ts
  - desktop/web/README.md
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/public/**
  - desktop/web/fonts/**
  - desktop/web/THIRD_PARTY_NOTICES.md
  - desktop/web/src/components/Button.*
  - desktop/web/src/components/Tag.*
  - desktop/web/src/components/StatusTag.*
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Tooltip.*
  - desktop/web/src/components/Menu.*
  - desktop/web/src/components/Dialog.*
  - desktop/web/src/components/Drawer.*
  - desktop/web/src/components/Toast.*
  - desktop/web/src/components/IconButton.*
  - desktop/web/src/components/Switch.*
  - desktop/web/src/components/Checkbox.*
  - desktop/web/src/components/TextField.*
  - desktop/web/src/components/Select.*
  - desktop/web/src/components/KeyValueList.*
  - desktop/web/src/components/EmptyState.*
  - desktop/web/src/components/Skeleton.*
  - desktop/web/src/components/ConnectionPill.*
  - desktop/web/src/components/Breadcrumb.*
  - desktop/web/src/components/SegmentedControl.css
  - desktop/web/src/components/Tabs.css
  - desktop/web/src/components/overlay/**
  - desktop/web/src/components/field/**
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/component-css.test.ts
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/font-specimen.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/toast-close-tooltip.test.tsx
  - desktop/web/tests/toast.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - tests/test_gate_*.py
  - tests/test_gate_t007_*.py
  - tests/conftest.py
  - tests/test_attempt_states.py
  - tests/test_desktop_attempt_states.py
  - .gitignore
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- src/showcase/ 下只有 FormsShowcase.tsx、showcase-forms.css、EvidenceShowcase.tsx、showcase-evidence.css 四个文件可动，其余不许动（其余不在允许列表，自动越界）。

## Behavior contract

### 公共约定
- 组件名、属性名、类名、data-*、data-demo 取值与按钮文字在本合同定下后，门禁按它写探针、解析 CSS，执行端不得再改。
- 键盘一律看 event.key；处理了的键都 preventDefault，Esc 例外（见第 4 条）。
- Roving TabIndex：组内恰一个 tabIndex=0；受控组件（value/checked + onChange）。
- 颜色、字体、圆角、阴影、层级只用 --tt-* 令牌；间距有对应 --tt-space-* 时用令牌，就近取刻度、平局取小。
- 尺寸字面量同一行带出处注释（画布行号或文档节号）；演示用尺寸写「演示自定」。
- 新组件、components/evidence/ 与 EvidenceShowcase 都不渲染 role=status；都不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。
- 不可信文字只作 React 的文本子节点；证据文字不进 title 以外的任何属性。
- 禁用词（静态检查扫 desktop/web/src/**/*.{ts,tsx} 全文，含注释与字符串）：dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser。基线上一个都没有。
- 六个新组件源码里不出现 href、src=、target=。
- W4 的坑：token-contract.mjs 只剥块注释、字符串也扫；演示文字与代码里不出现井号加 3/4/6/8 位十六进制字符、不出现 rgb(、color(、lab( 这类函数名加括号、不拼接 --tt- 前缀、不写 role 等于 status 的属性写法。

### 1. 图标（desktop/web/src/icons/index.tsx 末尾追加，沿用 Svg 包装，不动已有图标）
- LockIcon：rect width=18 height=11 x=3 y=11 rx=2 ry=2；path d=M7 11V7a5 5 0 0 1 10 0v4（领域板 :404）。
- CopyIcon：rect width=14 height=14 x=8 y=8 rx=2 ry=2；path d=M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2（领域板 :409）。
- EyeOffIcon：四条 path，依次为 M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49；M14.084 14.158a3 3 0 0 1-4.242-4.242；M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143；m2 2 20 20（站主核实，与 Lucide 1.59.0 dist/esm/icons/eye-off.mjs 一致）。
- 文本查看器的「行号」「换行」用文字按钮，不加图标。

### 2. Banner 的可选 action（§2.5）
- BannerProps 加 action?: ReactNode。有 action 时在文字之后、关闭钮之前渲染 span.tt-banner__action（flex: none）；没有时结构与现在完全相同（G2 的提示条用例都不传，照常通过）。
- info 提示条照旧总有关闭钮。「文件已变化」的提示条点关闭先藏起来，changed 从假再变真时重新出现。

### 3. 表格修补 S1–S3（§2.8）
- S1 当前行按 key 记：state 存当前行的 key，不存下标；渲染时依次找当前 key、选中行、第一行，找到的那一行 tabIndex=0；selectedKey 变化时清掉当前 key（当前行回到选中行）；rows 为空时没有行。覆盖 rows 变少、rows 晚于 selectedKey 到达、排序或插入三种情形。
- S2 数字列表头：数字列的 th 也带 tt-num；Table.css 加 `.tt-table th.tt-num { text-align: right; }`（特异性 (0,2,1) 高于 `.tt-table th` 的 (0,1,1)）。不与 G5 P8、table.test.tsx、component-css.test.ts 冲突。
- S3 表格焦点环：`.tt-table-wrap { scroll-padding-top: 32px; }`（同行注释「表头高 32（组件板 :411）」）；`.tt-table tbody tr:focus-visible { outline: none; }`；单元格画 2px inset 阴影、颜色 --tt-focus（每格画上下两条，首格加左边、末格加右边，只有一格时画四边）；补 `@media (forced-colors: active) { .tt-table tbody tr:focus-visible { outline: 2px solid Highlight; outline-offset: -2px; } }`（W4 允许系统颜色）；带 px 的每一行同一行注释（G5 D12 也查 Table.css）；只用 CSS 不调 scrollIntoView；选中行的 inset 2px 0 0 var(--tt-primary) 留在 tr 上。

### 4. S5 与三处缺口（§2.7、§2.8）
- S5：SegmentedControl 与 Tabs 的 tabIndex 改看已经算好的 active 下标；value 不在选项里时第一项可 Tab 到；aria-checked、aria-selected 仍只看 value；value 有效时与现状完全相同。
- 缺口 1 页签 aria-controls：每个页签都给、指向同一个面板（现状 Tabs.tsx:64 如此，不改代码，只补测试）。
- 缺口 2 空格带 repeat：照样 preventDefault，但不切换（现状 useToggle.tsx:28–31，只补测试）。
- 缺口 3 关闭态胶囊按 Esc：放过，既不 stopPropagation 也不 preventDefault；打开时照旧（关闭、stopPropagation、焦点留胶囊，不要求 preventDefault）（现状 ConnectionPill.tsx:42–47，只补测试）。

### 5. 陈列页 S4、S6（§2.8）
- S4a：`.showcase-table { max-height: 240px; max-width: 280px; }`，两项都注释「演示自定」，280 那项写明小于表的自然宽度（约 330）；限高仍在，G5 的 showcase_table_limit_problems 照常通过。
- S4b：连接胶囊那一行加类 showcase-pill-row（justify-content: flex-end）；只加类、不改结构。
- S6：showcase-forms.css 的 240px、560px（改 280px）与新的 showcase-evidence.css，每个 px 字面量同一行注释「演示自定」或出处。

### 6. 导出 index.ts
- 追加 6 个组件、它们的 Props 类型与 2 个函数（isMaskedPlaceholder、dispatchCommand）的导出；原来 23 个组件仍在；文件头注释改成五片；去掉注释后不出现 overlay。

### 7. 内部纯函数 components/evidence/
- ansi.ts 的 stripAnsi：去 CSI（ESC 加 [ 或 0x9B 开头，参数字节 0x30–0x3F、中间 0x20–0x2F、结束 0x40–0x7E）、去 OSC（ESC 加 ] 到 BEL 或到 ESC 加反斜杠）、去其余 ESC 双字符序列、最后剩下的 ESC(U+001B) 与 U+009B 一律去掉；正则不能有嵌套量词；256 KiB 病态输入 1 秒内完成。
- viewerLines.ts 的页转行：text 模式把各页 text 依次接起来再按换行切行；每页开头落在第几行，把该页的 part、parts 记到那一行（后来的页覆盖先前的）；文本以换行结束时末尾空串不算一行；每行去掉末尾回车。jsonl 模式同一 n 的分片按到达顺序拼接、记最后一片的 part/parts；行号用 n；text 模式行号按切出顺序从 1 数。
- markdown.ts 的 parseMarkdown：纯函数、不引入 React、输出纯数据块节点与行内节点；解析规则见第 9 条。

### 8. TextViewer（文本查看器，7.12）
- API：title?；pages: readonly ViewerPage[]；hasMore: boolean；onLoadMore?；loadingMore?；changed?；onReload?；onCopy(text)（必填）；defaultLineNumbers?（缺省 true）；defaultWrap?（缺省 false）；className?。
- ViewerPage 两种：{mode:'text'; text; part?; parts?} 与 {mode:'jsonl'; lines: ({n; text; part?; parts?} | {n; hidden})[]}；多出的字段忽略。
- 结构：根 div.tt-viewer；头部标题 + 两个文字按钮「行号」「换行」（button type=button，带 aria-pressed）+ 复制钮（IconButton size sm，CopyIcon，名称「复制已显示的文字」，提示「复制」）。
- 行：每行一个元素；行号开着时行号带 aria-hidden、user-select:none、tt-num；文字只作文本子节点；分片行在文字前显示「第 k/n 片」（k 取已加载的最大片号、n 取 parts，加载完也显示第 n/n 片；caption 字号、text-3、user-select:none）；行尾 [继续加载] 是 Button（secondary、sm，文字「继续加载」），只在 k<n、这一行是最后一行、且还有下一页时出现。
- 隐藏行：EyeOffIcon 14（aria-hidden）+ 斜体 text-3 说明；not_json → 「这一行不是合法 JSON，已隐藏」；too_long → 「这一行超过 4 MiB，已隐藏」；其他 → 「这一行已隐藏：<原值>」；没有按钮/链接/tabindex，点击无反应；行号照常显示。
- 换行：关时 white-space: pre、主体 overflow-x: auto、只在查看器里横向滚动；开时 white-space: pre-wrap; word-break: break-all。
- 复制：回调字符串是各文字行（分片拼好、ANSI 去掉）用换行连接；隐藏行跳过，末尾不加换行。
- 底栏：显示「已显示 N 页」（N=pages.length）；hasMore 假时另显示「已到末尾」；hasMore 真且给了 onLoadMore 时有 [继续加载]，loadingMore 时用 Button 的 loading（转圈、文字「正在加载…」）。
- 文件已变化：changed 真时头部与行之间显示 info Banner 文字「文件已变化」，action 是 [从头读取]（给了 onReload 才有），点关闭藏起来、changed 从假再变真时重新出现；changed 真时两处 [继续加载] 都禁用。
- 样式（领域板 :351–363、Attempt 画面 :320–337）：根 --tt-surface-1、1px --tt-border、--tt-radius-lg、overflow:hidden；头高 40、左 --tt-space-3 右 --tt-space-2、下边框，标题 --tt-mono-sm 单行省略；切换钮高 28、左右 --tt-space-2、--tt-radius-md、透明底、--tt-text-2、--tt-text-sm，按下态底 --tt-surface-3；主体上下 --tt-space-2；行 --tt-mono-md，行号列 44 右对齐右内边距 --tt-space-3、--tt-text-3，文字最小高 20、右内边距 --tt-space-3，行号关时左内边距 --tt-space-3；隐藏行说明 --tt-text-3 斜体、与图标间距 --tt-space-1；底栏 --tt-surface-2、上边框、内边距 --tt-space-2 与 --tt-space-3、--tt-text-caption、--tt-text-3，按钮靠右；提示条外边距 --tt-space-2 与 --tt-space-3。

### 9. SafeMarkdown（安全 Markdown，7.12）
- API：source: string；onOpenLink(url)（必填）；className?。
- 块解析（逐行；先把 CRLF/CR 换成 LF；行首制表符按 4 空格缩进）：围栏代码块（行首 ≤3 空格、≥3 个反引号或波浪号开头、反引号围栏信息串不能有反引号，到同种字符且长度不短于开头的行为止，内容原样、信息串忽略）；ATX 标题（1–6 个井号后跟空格或行尾，去结尾空格加井号，井号后非空格不是标题）；GFM 表格（表头含未转义竖线、下一行对齐行格数相同；各行去首尾各一竖线后按未转义竖线切格，反斜杠加竖线是字面竖线，多的格丢掉、少的补空；对齐 :- 左、-: 右、:-: 居中、- 不设；表格可打断段落）；列表（标记行首空格后 -/*/+ 或 1–9 位数字加 . 或 ) 后跟空格或行尾；缩进不小于当前项文字起始列的是子列表，同缩进是兄弟，更小退回上一层；同层有序无序换了另起一个；有序首数字非 1 带 start；最多 8 层、更深当第 8 层兄弟；项里只有段落与子列表；空行后若列表项或缩进够的行列表继续，否则结束）；段落（其余连续非空行，每行去首尾空白用换行连接，渲染 white-space: pre-wrap）；其余语法都当段落文字。
- 行内（从左到右扫）：反斜杠加 ASCII 标点是字面字符；代码段（反引号串配同长度串、内容原样，两头有空格且内容不全空格各去一空格，配不上是字面字符）；链接（判定见下）；粗体 **…**/__…__、斜体 *…*/_…_（开头定界符后非空白、结尾定界符前非空白；下划线开头前、结尾后不能是字母或数字按 Unicode 判，蛇形名不变斜体；只看后面最近同种定界符，配不上开头当字面字符不再往后找）；其余字符含 < > & 都是文字、不解码实体。
- 链接判定：网址按原样判定（不解码实体、不补协议），用正则判以 http:// 或 https:// 开头（不分大小写）后至少一个非空白字符才放行；不用 new URL。放行的渲染成 button type=button（文字为链接文字）+ 紧跟 span（网址），点击调 onOpenLink(原网址)，不渲染 a href；被拒的（javascript:、data:、mailto:、相对地址、//host 等）只渲染链接文字、网址不出现；链接文字为空、![…](…) 形式不算链接、整段当文字。
- 性能：parseMarkdown 对 256 KiB 病态输入 2 秒内返回（病态：全 *、全 _、全 [、全反引号、[a]( 重复、**a 重复、每行多缩进两格的 - x 共 2000 行）；预先算最近 ]、最近同长度反引号串、定界符位置；嵌套最多 8 层、更深当文字。
- 渲染：标题渲染 h(级别+1)、h6 封顶（一级 --tt-title-lg、二级 --tt-title-md、三级以下 --tt-title-sm）；段落 p；列表 ul 或带 start 的 ol，项 li，项里段落也是 p（外边距 0）；代码块 pre>code；行内代码 code；粗体 strong；斜体 em；表格外套横向滚动 div、里 table>thead>tr>th[scope=col] 与 tbody>tr>td，对齐用类不用内联样式；放行链接 button + span。允许元素只有 div、span、p、h2–h6、ul、ol、li、pre、code、strong、em、table、thead、tbody、tr、th、td、button；允许属性只有 class、type、start、scope、aria-*、data-*，不出现 style、href、src 与 on 开头属性。
- 样式（Attempt 画面 :105–118）：根 --tt-text-md、--tt-text-1、块间距 --tt-space-2、标题外边距 0；列表左内边距 --tt-space-5、项间距 --tt-space-1；行内代码 --tt-mono-sm、内边距 1px 与 --tt-space-1、--tt-radius-sm、--tt-surface-2、1px --tt-border；代码块 --tt-mono-md、--tt-surface-2、1px --tt-border、--tt-radius-md、内边距 --tt-space-2、overflow-x:auto、white-space:pre；表格 --tt-text-sm、格内边距 --tt-space-1 与 --tt-space-3、1px --tt-border、表头 --tt-surface-2/--tt-title-sm/--tt-text-2；链接钮 --tt-link、透明底、无边框、无内边距、继承字体、悬停下划线；网址 --tt-mono-sm、--tt-text-3、左外边距 --tt-space-1。

### 10. EffortPair（思考档位，7.24）
- API：requested?: string | null；effective?: string | readonly string[] | null。
- 读法：要求与生效逐字相同才算一致；生效有多个原样列出、任一不同即不一致；生效缺失（null/undefined/空数组/空串）是「未知」，不算一致也不显示成要求的档位；没有要求（null/undefined/空串）时整格显示「—」。
- 文字形态（空白折叠成一个空格后的整段，门禁按它断言）：一致「要求 high · 生效 high」；不同「要求 max · 生效 high 与要求不同」；未知「要求 high · 生效 未知」；没有要求「—」；多个有不同「要求 max · 生效 high、max 与要求不同」；多个都相同「要求 high · 生效 high、high」。
- 结构：根 span.tt-effort 带 data-state（same/differs/unknown/none）；「要求」「生效」标签 --tt-text-3；档位名 --tt-mono-sm；「未知」「—」--tt-text-3；「与要求不同」用 Tag tone=warning、title「内核记下的生效档位与要求不同」，不用金色。
- 样式：display:inline-flex、align-items:center、间距 --tt-space-1、--tt-text-sm、可换行。

### 11. MaskedValue（遮蔽值，7.13）
- API：children: string（后端给的占位，原样显示）。另导出 isMaskedPlaceholder(value)：值等于「（含疑似凭据，不显示）」「（值不显示）」「<redacted>」「（疑似凭据的键名）」之一时为真，逐字比较，括号全角。
- 结构：span，title=内核已遮蔽；LockIcon 14 在前；inline-flex、间距 --tt-space-1、--tt-text-3；先写 font: var(--tt-text-sm) 再写 font-style: italic（font 简写会重置字形）。

### 12. CommandLine（7.16）与 NextStep（7.21）
- CommandLine：API command: string；size?: 'md'|'sm'（缺省 md）；onCopy(text)（必填）。另导出 dispatchCommand(args)：返回 bash scripts/dispatch-pi.sh 加空格再加空格连接的参数；无参数就是 bash scripts/dispatch-pi.sh，末尾没有空格；参数原样拼接不加引号不转义。结构 code 里是命令文字；复制钮 IconButton（size sm，CopyIcon，名称「复制命令」，提示「复制」），点击调 onCopy(command)。md 样式：flex 垂直居中、间距 --tt-space-1、最小高 36、内边距 --tt-space-1 左边 --tt-space-2、--tt-radius-md、--tt-surface-2、1px --tt-border，code --tt-mono-md/--tt-text-1/flex:1/min-width:0/white-space:pre-wrap/word-break:break-all。sm 样式：inline-flex、高 28、间距 --tt-space-0_5、内边距上下 0 右 --tt-space-0_5 左 --tt-space-2、底/边框/圆角同 md，code --tt-mono-sm，复制钮缩成 24、圆角 sm、图标 14（选择器 .tt-cmd--sm .tt-icon-btn 特异性 (0,2,0) 高于 IconButton 单类规则）。
- NextStep：API children（说明文字）；title?；command? 与 onCopy?（类型上要么都给要么都不给）。结构 InfoIcon 16（aria-hidden）、可选 strong 标题、说明文字、可选 CommandLine size=sm；不设 role、不是提示条。样式：flex 垂直居中可换行、间距 --tt-space-2、内边距 --tt-space-2 左边 --tt-space-3、--tt-radius-md、--tt-tone-info-bg/--tt-tone-info-fg/--tt-text-sm、标题 --tt-title-sm。

### 13. EvidenceShowcase（演示）
- 默认导出组件，渲染若干 section.showcase__section[data-demo]，每节一个 h2.showcase__h2；样式在 showcase-evidence.css，复用 App.css 的 showcase__* 类，不改 App.css；不挂到陈列页。
- 七节，data-demo 依次：text-viewer、text-viewer-jsonl、safe-markdown、effort、masked-value、command-line、next-step。
- text-viewer：text 模式三页（第 1 页 UI 文档 9.4 :1196–1197 的执行报告原文含 <img src=x onerror=alert(1)> 行，再加 <script>alert(1)</script>、一行带 ANSI 颜色、一行网址；第 2、3 页是长行两片 part 1/2、2/2 加几行普通文字；[继续加载] 依次加页；「模拟文件已变化」把 changed 置真；[从头读取] 回第 1 页；复制按第 8 条显示结果文字）。
- text-viewer-jsonl：UI 文档 9.4 :1203–1210 的 events 页（含 not_json、too_long 与第 6 行第 1/2 片）；[继续加载] 给第 6 行第 2/2 片与后面几行，最后一页 done。
- safe-markdown：UI 文档 9.3 :1186 摘要原文；再加带对齐的表、代码块、粗体斜体、蛇形名、一个 https 链接、一个 javascript: 链接、几段原始 HTML；点链接只在旁边显示「上次请求打开：<网址>」，不弹框。
- effort：第 10 条六种情形；masked-value：四种占位；command-line：md 用 dispatchCommand(['config','preset','use','economy'])、sm 用 /plan-task logs-cat；next-step：带命令与不带命令各一个。
- 满足 §2.12：不渲染 role=status、对话框、菜单；没有文字的按钮都有 aria-label；data-demo 不与已有的 16 个重复；节标题不含 Button、按钮文字不含「亮」「暗」「跟随系统」；样式尺寸写「演示自定」，摘要最大宽 880 注释 handoff :165。

### 14. 过渡断言（§2.11、§7.4）
- 新增 S7 与 P9 两条按 test_transitional_ 命名，docstring 第一行写「陈列页的演示改版（整理陈列页或换成真实页面）时推翻」。
- 长期断言：组件行为、CSS 取值、静态检查、S1–S3、S5、三处缺口、S6 的注释规则。
- 本片不推翻现有的 5 条过渡断言（见 Repository facts 的 8214a1f 核对结果）。

### 门禁断言对照（§7.3，门禁端定稿）
- 静态 S1：六个新组件 tsx/css 与 evidence/ 三模块都在；index.ts 导出六组件、Props 类型与两函数，原 23 个仍在。
- S2：desktop/web/src/**/*.{ts,tsx} 全文无 §5.0 禁用词。
- S3：六组件与 evidence/ 源码无 href、src=、target=、role=status，也不调四个禁用接口。
- S4：LockIcon、CopyIcon 的 rect 属性与 path d 等于领域板 :404/:409；EyeOffIcon 的 path d 等于第 1 条的值。
- S5：新组件 CSS 取值（§5）；层级、圆角、阴影、字体只用令牌；除 0 与 1px 外的 px 字面量都带同一行注释。
- S6：Table.css 有 th.tt-num 右对齐、容器 scroll-padding-top 32px、tr:focus-visible outline none、单元格 --tt-focus inset 阴影、forced-colors 兜底。
- S7（过渡）：showcase-forms.css 的 .showcase-table max-width 280px、max-height 仍在；胶囊行带约定类且 justify-content: flex-end。
- S8：showcase-forms.css 与 showcase-evidence.css 的 px 字面量都带同一行注释。
- P1：npm 四步退出 0；npm test 没有失败、跳过、待办。
- P2：W1（D01 探针，含复制字符串逐字比较）。P3：分页、分片、隐藏行、409（D02）。P4：W2 与性能（D03）。P5：W7 六种情形整段文字与 data-state（D04）。P6：遮蔽值、命令行、下一步、提示条 action（D05、D06、D07）。P7：S1、S2（D08）。P8：S5 与三处缺口（D09）。P9（过渡）：渲染 EvidenceShowcase 七节都在、data-demo 不与已有 16 个重复、W1 样例、无 role=status/对话框/菜单、无文字按钮都有 aria-label、节标题不含 Button（D11）。P10：流水线前后 git status 不变、gate-probe 清掉、受监视文件摘要不变。
- 探针沿用 T002–T005 做法；组件探针与演示探针分开跑。

### 执行端测试（§7.2）
- 写法沿用 T005：render/act/fireEvent/cleanup 从 @testing-library/react 导入，不加 user-event；按 id 用 getElementById；样式断言读 CSS 文本、用 process.cwd() 定位文件；性能用例用 Date.now() 计时不开假计时器。
- 文件：evidence-text-viewer.test.tsx、evidence-markdown.test.tsx、evidence-effort.test.tsx、evidence-atoms.test.tsx、evidence-showcase.test.tsx、evidence-static.test.ts、forms-patches.test.tsx、forms-patches-css.test.ts。

## Steps
1. 预检（只读）：核对 §10 的假设与基线；不符就停。范围：不改文件。
2. 表格修补 S1–S3（Table.tsx、Table.css、tests/forms-patches.test.tsx、tests/forms-patches-css.test.ts）。
3. S5 与三处缺口（SegmentedControl.tsx、Tabs.tsx、tests/forms-patches.test.tsx）。
4. 陈列页修补 S4、S6（FormsShowcase.tsx、showcase-forms.css）。
5. 图标与提示条（icons/index.tsx、Banner.tsx、Banner.css）。
6. 遮蔽值、命令行、下一步（MaskedValue、CommandLine、NextStep 各一对）。
7. 思考档位（EffortPair 一对）。
8. 文本查看器（evidence/ansi.ts、evidence/viewerLines.ts、TextViewer 一对）。
9. 安全 Markdown（evidence/markdown.ts、SafeMarkdown 一对）。
10. 导出（index.ts）。
11. 演示（EvidenceShowcase.tsx、showcase-evidence.css、tests/evidence-showcase.test.tsx）。
12. 执行端测试与自检：desktop/web 下 npm ci（要网络）、npm run build、npm test、npm run check:contract；仓库根点名跑 V01–V03；git status 没有新的未忽略文件。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与执行端自检里跑（与 T002–T005 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t007_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py -q` · cwd：仓库根 · 超时：9000s · 期望退出码：0 · 输出须匹配：`\d+ passed`，不得出现 `failed|error`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：V01 的 tests/test_gate_t007_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）；V02 合并 T001–T005 五份门禁回归，点名运行以让前端流水线不被 conftest 跳过（每份各跑一遍 npm ci 与构建）；V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。门禁要点名运行，conftest 才不会跳过前端流水线（tests/conftest.py:33–41）。

## Definition of done
- D01：文本查看器只按文本显示（W1）——输入含 <img src=x onerror=alert(1)>、<script>alert(1)</script>、带 ESC[31m 与 ESC[0m 的红色文字、一个网址；DOM 里没有 img、script、a 元素，行里没有带 style 属性的元素；文字原样出现；ESC 字符与 [31m 都不出现；行号与换行两个开关的 aria-pressed 与样式都对；复制回调收到的字符串逐字等于约定值；目的：W1 的内容不可信，只当文本显示；证据：V01。
- D02：分页与分片——已显示 N 页；已到末尾；[继续加载] 调 onLoadMore；text 与 jsonl 两种模式的分片拼接与第 k/n 片；行尾 [继续加载] 只在最后一行没加载完且还有下一页时出现；以换行开头的页不多出空行；隐藏行三种说明、不能展开；changed 时有提示条与 [从头读取]、关闭后能再出现、[继续加载] 禁用；证据：V01。
- D03：安全 Markdown（W2）——八种元素结构；原始 HTML 原样当文字；javascript: 等被拒只剩链接文字、没有按钮与网址；http(s) 渲染成按钮加网址、点击调一次 onOpenLink(原网址)；元素与属性都在允许集合里；蛇形名不变斜体；256 KiB 病态输入 2 秒内完成；目的：不可信 Markdown 不执行、不卡死；证据：V01。
- D04：思考档位（W7）——§2.6 六种情形的文字与 data-state；不同时有 warning 标签与 title；未知时不显示成要求的档位；没有要求时只有「—」；证据：V01。
- D05：遮蔽值——结构、title、lock 图标 14、斜体 text-3；isMaskedPlaceholder；证据：V01。
- D06：命令行与下一步——dispatchCommand；复制钮名称与回调；sm 与 md 两种尺寸；下一步的结构与可选命令；证据：V01。
- D07：图标与提示条——三个图标路径；Banner 不传 action 时结构不变、传了时操作钮在文字与关闭钮之间；证据：V01、V02。
- D08：S1–S3——rows 变少、晚到、排序之后恰一行 tabIndex=0 且是约定那一行；数字列 th 带 tt-num、右对齐；Table.css 有 scroll-padding-top、焦点环与强制颜色兜底；证据：V01、V02。
- D09：S5 与三处缺口——value 无效时恰一个 tabIndex=0 是第一项；每个页签的 aria-controls 都指向面板；空格 repeat 被 preventDefault 不切换；关闭态胶囊的 Esc 往外传不被 preventDefault；证据：V01、V02。
- D10：S4、S6——showcase-forms.css 的取值与注释；胶囊行靠右；证据：V01。
- D11：演示——七节都在、data-demo 不与已有重复；W1 样例在 DOM 里只是文字；没有 role=status、对话框、菜单；没有文字的按钮都有 aria-label；证据：V01。
- D12：静态检查——§5.0 禁用词；新组件源码无 href、src=、target=；新 CSS 只用令牌、px 字面量带同一行注释；W4 通过；证据：V01。
- D13：回归——T001–T005 门禁全绿（含现有 5 条过渡断言）；W5 通过；npm 四步都退出 0；证据：V02、V03、V01。
- D14：范围——只改允许的文件；不改依赖；既有测试不改；新测试不用 skip、only、todo；证据：scope、V02。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 App.tsx、App.css、main.tsx、tokens.css、package.json、锁文件、门禁测试 tests/test_gate_t007_*.py）。
- 需要新增或升级依赖、写 .npmrc、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）。
- 时间分配：调查约 15 分钟、实现与补测约 65 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。

## Rework（返工第 1 轮，内核追加）

- 基线 `a56eec8a7752dbca3d599aa5c794b6a5ed3ba6dc` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面终审列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

退回对象均为执行端。依据条款指 .agent/plans/t007-desktop-evidence.v1.md 的行号；锚点指候选文件；复现名指 tests/test_gate_t007_whitebox.py 里的用例。
B1（D-01）行号关时文字缺左内边距。合同 :248「行号关时左内边距 --tt-space-3」。锚点 TextViewer.css:64-68、TextViewer.tsx:72（根类没有行号状态的钩子）。复现 test_wb_s01。要求：给行号关一个样式钩子，行号关时 .tt-viewer__text 左内边距取 var(--tt-space-3)，行号开时不变。
B2（D-02）行内代码规则盖到代码块里。合同 :257「代码块 --tt-mono-md」。锚点 SafeMarkdown.css:24-30（.tt-md code 无 :not(pre) 限定）。复现 test_wb_s02。要求：行内规则限定到非 pre 内，或在 pre code 里还原字体、边框、底色、内边距、圆角；行内代码样式不变。
B3（D-03）关掉提示条后 [继续加载] 恢复可点。合同 :247「changed 真时两处 [继续加载] 都禁用」，藏提示条与禁用是两件独立的事。锚点 TextViewer.tsx:67、:69、:134、:152（禁用只看 changed && !dismissed）。复现 WB-V01。要求：禁用改看 changed（行尾 changed 或 loadingMore，底栏 changed），关闭只管提示条显示。
B4（D-04）jsonl 分片逐片去 ANSI 再拼，被分片边界切开的转义序列去不净。合同 :235、:245「分片拼好、ANSI 去掉」。锚点 viewerLines.ts:85（text 模式 :57-:64 先拼后去，是对的）。复现 WB-V05：a+ESC+[3 与 1mb 得 a31mb，应为 ab。要求：同一 n 的分片先按到达顺序拼好原文，再对每行去一次 ANSI，显示与复制都对。
B5（D-05）列表项里缩进到项文字列的围栏、标题被移出列表。合同 :22、:252「列表项里除段落与子列表以外的块原样当文字；项里只有段落与子列表」。锚点 markdown.ts:375（围栏/标题判断先于 :377 的缩进判断）。复现 WB-M01：「- a」、缩进两格的围栏三行、「- b」得两个 ul 夹一个 pre；缩进两格的「# x」得 h2。要求：缩进不小于项文字起始列的围栏/标题行并入项的文字（含子列表之后回到外层项文字列的情形），列表不被拦腰截断；缩进更小的才结束列表；基准的惰性续行与「围栏、标题能打断段落」用例不变。
B6（D-06）N 个 [ 共用一个 ]( 加长网址时是平方时间。合同 :255 与 D03「256 KiB 病态输入 2 秒内、不卡死」；列出的 7 种是代表形状，不是豁免。锚点 markdown.ts:241-255（循环 :243-244 每个 [ 都从同一处重扫到文末）。复现 WB-M02：65536 个 [ 加 ]( 加 65534 个 y 共 128 KiB，门禁实测 5.5 s，256 KiB 推算约 22 s。要求：网址终点的计算整体线性。与 B7 联动：朴素的括号计数会让合同列出的「[a]( 重复」也变平方（基准 V01 会超时）；建议预算两张表——每个位置之后最近的空白、一次栈扫描配好的全文括号——链接成立当且仅当 ]( 的那个 ( 有配对的 )，且 ) 在最近空白之前。验收：WB-M02、WB-M03 与基准 7 种形状都在 2 秒内。
B7（D-07）网址扫描遇 ( 就停，带括号的网址整段当文字露出。合同 :254、D03「被拒的只渲染链接文字、网址不出现」。锚点 markdown.ts:244-246。复现 WB-M06：[这一条被拒](javascript:alert(1))、data:text/html,f(1)、vbscript:msgbox(1) 应得「点 这一条被拒 试试」，实际整段原样显示。同源旁证：[w](https://h/a_(b)) 这样的合法网址也成不了链接。要求：网址认括号配对；基准 13 种被拒网址与 https 放行用例不变。
B8（D-08）演示的 javascript 链接露出网址。合同 :279、D11。锚点 EvidenceShowcase.tsx:94（演示源码，随 B7 转正）。复现 WB-E05。另：WB-E05 对整节文字断言不含「javascript:」，而 :197 的说明文字自己写了该词，所以光修 B7 它仍红；合同没有禁止说明文字提这个词，断言偏宽，但请顺手把 :197 改成不含该字面的说法（例如「不安全协议的链接只留文字」），免得再走一轮。
建议类（不阻塞）：每条修复在执行端自带测试里补一条回归用例，不删、不弱化既有测试；改动范围越小越好，复审封板只看 B1–B8 与新改动。
