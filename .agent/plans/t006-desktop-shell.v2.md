# TASK: t006-desktop-shell

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 50b823d744da48e3266fd3a6459057c8d8d943e0
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T006 第 6 片（桌面端前端应用框架与夹具数据层）。在 desktop/web/ 自写约二十行的 hash 路由（#/overview … #/settings 与 #/showcase），新增标题栏、底部 Tab 栏、快捷键、主题切换、页面框架与五态、9 个页面占位、src/api.ts 与 src/mock/ 夹具数据层，把根 App 从组件陈列页改成应用框架、陈列页移到 #/showcase 并按文件名自动收集 src/showcase/*Showcase.tsx；不改依赖、不改令牌、不改 src/components/**、与 T007 的文件不重叠。

## Non-goals
- 具体页面内容、七端视图（站主 Q1）、写操作、接本机服务、SSE 与重连（UI 文档 8.5）、作业（8.4）、Electron 外壳与标题栏拖动区、工具链升级。
- 主题偏好的持久化（由外壳的设置保存，架构文档 D3）；仓库切换的真实动作（属于外壳）；Ctrl+R、Ctrl+F、Alt+← 与 ? 快捷键。
- T005 终审第 10 节第 4 条（五项合同缺口与 S1、S2、S5）：站主已划给 T007，本片不做。
- api.ts 里 UI 文档第 9 节没有示例的读函数（listAttempts、getConfig、validateConfig、getHistoryEntry、getPlugin、checkSecret），以及 subscribeEvents、作业函数、preview 与写函数：后面的片按需补。

## Repository facts
- 入口：desktop/web/src/main.tsx 用 createRoot 挂载 desktop/web/src/App.tsx；当前 App.tsx 是组件陈列页（根元素带 tt-app、tt-content、showcase 三个类），main.tsx:3–6 先 import App 再 import fonts.css、tokens.css、base.css。index.html:6 的标题是 Themis Tally · 组件陈列（本片不改 index.html，运行时改写 document.title）。
- App.tsx 现状：applyTheme :18–25；页头三个主题按钮 :57–61；样张 :64–93；五个原子（Button、Tag、StatusTag、Card、Banner）:95–183；五节浮层演示 :185–255；:257 渲染 FormsShowcase。App.css:1–38 是陈列页规则（.showcase 带 min-height:100vh），:40–70 是样张规则。
- 组件与图标现状：
  - Menu.tsx 的 MenuProps 只有 label、items、onSelect（:13–20），触发钮固定是缺省 Button（:107–115）；Button 没有 forwardRef，缺省 primary、md，Button.css:14 的 sm 高 28、左右内边距 --tt-space-3（12）。
  - IconButton 把其余属性透传给 button（IconButton.tsx:23），永远包一层 Tooltip；Tooltip 用 cloneElement 设 aria-describedby（Tooltip.tsx:98–100），悬停或聚焦 400ms 后出现，包裹 span 是 inline-flex（Tooltip.css:3–5）。
  - ConnectionPill 属性为 state、attempt?、pid?、startedAt?、stream?（ConnectionPill.tsx:9–18），浮层绝对定位、右对齐、层级 popover（ConnectionPill.css:30–42）。
  - Banner 的 danger 是 role=alert，info 总有关闭钮，没有放操作钮的位置（Banner.tsx:13–38）。Skeleton 的挂载时延常量是 300（Skeleton.tsx:7）。EmptyState 属性为 icon?、title、description?、action?（EmptyState.tsx:6–13）。
  - icons/index.tsx 的 Svg 包装是模块内私有（:7–26），已有 ChevronDown、ChevronRight、Check、CircleX、ListChecks、Info 等图标；fill/stroke 只能 none 或 currentColor（G2 的 test_g8_icons_dir，现 :1232）。
- 令牌现状（desktop/web/src/styles/tokens.css）：--tt-text-caption-strong 是 600 12px/16px；--tt-radius-sm 是 4px；Tab 栏用 --tt-sidebar、--tt-sidebar-hover、--tt-sidebar-text、--tt-sidebar-text-muted、--tt-sidebar-text-active、--tt-sidebar-dot-info；金条与计数用 --tt-accent、--tt-on-accent；Tab 栏高 --tt-tabbar-height 56px；Logo 用 --tt-logo-mark、--tt-logo-tally。尺寸令牌只有 --tt-tabbar-height，没有 11px 字体令牌，也没有 2px 圆角令牌。
- base.css 现状：:24 是 :focus-visible 焦点环；:54 是 .tt-content 的容器查询；:63 是 @media (max-width: 1179px) 下 .tt-hide-narrow { display: none }（S5 依赖它仍在）。
- README.md 现状：有「## 命令」一节（G2 的 test_g1_readme_documents_commands，现 :655，要求仍含 npm ci、npm run build、npm test、check:contract、--tt-）；有目录约定与令牌规则。本片只增补目录约定、路由与 ?mock=、陈列页收集与排序、不连服务检查，命令一节不动。
- 三份既有执行端测试渲染根 App 找陈列页（Q2 批准后只改挂载）：tests/font-specimen.test.tsx（render(<App />) 自 :26 起）、tests/showcase-overlays.test.tsx（自 :25 起）、tests/showcase-forms.test.tsx（自 :26 起）。showcase-forms.test.tsx:27–36 断言 11 节表单演示都在轻提示之后，:44 断言整页只有一个 role=status。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD = base_sha = e4be51f0bd5d6e1469256d3d382bedd197aaf49b，git status 干净。站主已在 e4be51f 退役 tests/test_gate_t002_baseline.py 里 G10 探针「App 陈列页」两条用例（原 :462–505），模块说明与 G10 说明一并改；本片不再把它们当待改项。T001–T005 门禁 tests/test_gate_t00{1,2,3,4,5}_baseline.py 都在，基线上应通过（回归）；本片门禁 tests/test_gate_t006_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在。G2 删去那两条用例后行号整体前移约 41 行，本片引用的 G2 位置已按内容重定位：test_g1_project_files_exist :610、test_g1_vite_config_and_entry :643、test_g1_readme_documents_commands :655、test_g8_icons_dir :1232、test_g10_component_probe :1476、test_d03_new_tests_not_skipped :1493。
- 其他门禁位置：G3 的 test_d01_main_imports_fonts_css :638（要求 main.tsx 先 import fonts.css 再 tokens.css）；G5 的源码守卫 :989–1010（不渲染 role=status、不调 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver）、受监视文件摘要 :2397、令牌与 px 注释守卫 :2630–2661；tests/conftest.py:30–41（pipeline 为会话级夹具，全量 pytest 默认跳过，点名运行或设 TT_FRONTEND_TESTS=1 才跑）。
- 仓库外事实（内核记录、已核实）：
  - jsdom 25.0.1：写 location.hash 时同步改文档地址，hashchange 经 window.setTimeout(…, 0) 异步派发；点 <a href> 时整个导航放在 setTimeout(…, 0) 里，地址不同步变。
  - Vite 5.4.11：import.meta.glob 加 eager:true 时展开成逐个 import * as 的静态导入；相对写法的键是 ./相对路径；匹配到的文件排序、排除导入者自己、跳过 node_modules；import-glob 插件在构建与开发服务器下都启用；带模块类型参数时返回 Record<string, M>。
  - Vitest 2.1.8：用 Vite 的 createServer 起开发服务器，经 vite-node 的 transformRequest 转换测试模块，测试里 import.meta.glob 照样展开；vi.useFakeTimers() 缺省只假 setTimeout、clearTimeout、setInterval、clearInterval、setImmediate、clearImmediate、Date，不假 Promise 与微任务。
  - @testing-library/dom 10.4.0：fireEvent 返回 element.dispatchEvent(event) 的结果，可据此断言 keydown 被 preventDefault；@testing-library/react 16.1.0 的 fireEvent 包装了它。
  - jsdom 25.0.1：带可解析 tabindex 的元素都可以聚焦（ShellMenu 的项靠 focus() 移动焦点）。

## Scope
- allowed_modified_files:
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/README.md
  - desktop/web/tests/font-specimen.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/src/api.ts
  - desktop/web/src/icons/frame.tsx
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/shell/*.ts
  - desktop/web/src/shell/*.tsx
  - desktop/web/src/shell/*.css
  - desktop/web/src/pages/*Page.tsx
  - desktop/web/src/showcase/ShowcasePage.tsx
  - desktop/web/src/showcase/showcase.css
  - desktop/web/src/showcase/BaseShowcase.tsx
  - desktop/web/src/showcase/ShellShowcase.tsx
  - desktop/web/src/showcase/showcase-shell.css
  - desktop/web/tests/shell-*.test.ts
  - desktop/web/tests/shell-*.test.tsx
- allowed_new_files:
  - desktop/web/src/api.ts
  - desktop/web/src/icons/frame.tsx
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/shell/*.ts
  - desktop/web/src/shell/*.tsx
  - desktop/web/src/shell/*.css
  - desktop/web/src/pages/*Page.tsx
  - desktop/web/src/showcase/ShowcasePage.tsx
  - desktop/web/src/showcase/showcase.css
  - desktop/web/src/showcase/BaseShowcase.tsx
  - desktop/web/src/showcase/ShellShowcase.tsx
  - desktop/web/src/showcase/showcase-shell.css
  - desktop/web/tests/shell-*.test.ts
  - desktop/web/tests/shell-*.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/components/**
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/showcase/FormsShowcase.tsx
  - desktop/web/src/showcase/showcase-forms.css
  - desktop/web/src/showcase/EvidenceShowcase.tsx
  - desktop/web/src/showcase/showcase-evidence.css
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/public/**
  - desktop/web/fonts/**
  - desktop/web/THIRD_PARTY_NOTICES.md
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/component-css.test.ts
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/segmented-control.test.tsx
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
  - tests/test_gate_t006_*.py
  - tests/conftest.py
  - tests/test_attempt_states.py
  - tests/test_desktop_attempt_states.py
  - .gitignore
  - .gitattributes
  - scripts/**
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定
- 组件名、属性名、类名、data-*、data-demo 取值与按钮文字在本合同定下后，门禁按它写探针、解析 CSS，执行端不再改。
- 键盘一律看 event.key；处理了的键都 preventDefault（ShellMenu 的 Esc 例外：stopPropagation，见第 3 条）。
- 不可信文字与夹具文字只作 React 的文本子节点；内联 style 只用于运行时算出的数值。
- 框架、页面占位与新演示都不渲染 role=status；整页只留 Toast 常驻的那一个（showcase-forms.test.tsx:44 断言整页只有一个）。
- 不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver（G5 :989–1010 守卫扫 showcase/*.tsx，jsdom 也没有前三个）。
- data-demo 的取值不能与已有的 16 个重复，也不能与 T007 的 7 个重复。
- W4 的坑：token-contract.mjs 对全文查十六进制颜色与颜色函数，只剥块注释。所以字符串与行注释里不写井号加 3/4/6/8 位十六进制字符；不写 rgb( 这类颜色函数名加括号；不拼接 --tt- 前缀。夹具是 JSON，W4 不扫。
- 层级、圆角、阴影、字体只用令牌；除 0 与 1px 以外的 px 字面量，同一行带出处注释（画布行号或文档节号；演示用的尺寸写「演示自定」）。

### 站主拍板（Q1–Q3）
- Q1：站主已在 e4be51f 退役 G2 里「App 陈列页」两条用例（原 tests/test_gate_t002_baseline.py:462–505）。原覆盖由本片门禁接手：P11 在 #/showcase 上验陈列页内容（原 App 用例一：17 个状态的 title、8 种色调、4 种按钮变体与 3 种尺寸、加载按钮、role=alert、关闭提示），P5 验主题切换、P6 验标题栏主题菜单。合同不把 G2 那两条当待改项。
- Q2：允许修改 3 份既有执行端测试的挂载：desktop/web/tests/font-specimen.test.tsx、showcase-overlays.test.tsx、showcase-forms.test.tsx。只许把「渲染根 App」改成「先把 location.hash 设为 #/showcase 再渲染 App」（可用 beforeEach 或辅助函数），用例与断言一条不改；终审按差异核对。
- Q3：计数胶囊的字用 --tt-text-caption-strong（画布原值 600 11/16）；金条下方两角的圆角用 --tt-radius-sm（画布原值 2）。两处各加一行注释写明画布原值。

### 与 T007 的文件边界
- 本片不改 src/components/**（含 index.ts、evidence/）、不改 src/icons/index.tsx（也不往里加再导出）；新建 src/icons/frame.tsx；不改 src/showcase/FormsShowcase.tsx、showcase-forms.css，不建 EvidenceShowcase.tsx、showcase-evidence.css（这两个名字留给 T007）；不改 main.tsx（允许但用不着）；不改 package.json、锁文件、index.html、vite.config.ts、tsconfig.json、scripts/**、public/**、fonts/**、THIRD_PARTY_NOTICES.md。
- T007 不碰 src/shell/**、src/pages/**、src/mock/**、src/api.ts、src/App.tsx、src/App.css、src/main.tsx、src/styles/**、src/domain/**、src/vite-env.d.ts、README.md。
- 两片合并后互相扫到对方源码，两边都要守：
  - T007 的禁用词检查扫 src/**/*.{ts,tsx}（注释与字符串都算）：dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser。本片源码一个都不写。
  - 本片的不连服务检查扫 src 下全部文件（注释与字符串都算）：fetch、XMLHttpRequest、EventSource、WebSocket。T007 的源码里也不要出现这四个词。
- EvidenceShowcase 落地后由 ShowcasePage 自动收进（第 11 条），不用改公共文件；它排在 BaseShowcase 与 FormsShowcase 之间。

### 1. 路由（src/shell/router.ts、routes.ts）
- 自写 hash 路由，不装 react-router（G2 :95 的 FORBIDDEN_DEP_PREFIXES 也禁止它）。路由表：#/overview 总览、#/tasks 任务、#/roles 角色与模型、#/runtimes CLI 运行时、#/secrets 凭据、#/logs 日志与用量、#/plugins 插件、#/history 历史与审计、#/settings 设置、#/showcase 组件陈列。
- 解析：去掉开头 #，按 ? 切成路径与查询；路径第一段决定页面，其余段原样交给页面；空、#、#/ 与未知路径都显示总览，不改写地址；查询里只认 mock（第 7 条）。
- 导航：navigate 先同步更新路由状态，再写 location.hash；同时监听 hashchange 接住后退、前进与手改地址（jsdom 写 location.hash 时同步改地址、hashchange 经 setTimeout(0) 派发；点 <a href> 时整个导航在 setTimeout(0) 里）。
- Tab 与状态段计数都是 <a href> 链接：无修饰键左键点击先 preventDefault 再自己导航；带修饰键走默认行为。链接与快捷键导航时保留当前 ?mock=。
- routes.ts 导出有序的 9 个 Tab，每项有 id、标题、路径、图标、快捷键与页面组件。当前路由是某 Tab 时该 Tab 为当前项；在 #/showcase 时没有当前项。换路由时内容区滚回顶部（给内容区按路由加 key）。document.title 写成 页面标题 · Themis Tally；陈列页写 组件陈列 · Themis Tally。

### 2. 标题栏（src/shell/TitleBar.tsx，照 Main 画布 :19–37 与 UI 文档 5.2）
- header：高 40，底色 --tt-titlebar，下边框 1px --tt-border；左内边距 --tt-space-3，元素间距 --tt-space-2，右内边距 140（UI 文档 5.2 :352）；不设 overflow:hidden、不建低于内容区的层叠上下文（胶囊浮层与两个菜单要盖在内容之上）。
- Logo（src/shell/Logo.tsx）：内联 svg，viewBox 0 0 937 1079，尺寸 18×20，role=img，aria-label 为 Themis Tally 标识；两条 path 的 d 逐字取 Main 画布 :20，盾与天平那条带 fill-rule evenodd；填色写在 CSS 类里，用 --tt-logo-mark 与 --tt-logo-tally；不放进 src/icons/（G2 :1232 要求那里 fill 只能 none 或 currentColor），也不用 tt-i 类。
- 产品名 Themis Tally（--tt-title-sm、--tt-text-1），后面一条 1×18 的竖线（--tt-border，左右外边距 --tt-space-0_5）。
- 仓库切换：触发钮用 Button variant=ghost size=sm（高 28），内容依次是 FolderOpenIcon 16、仓库名、ChevronDownIcon 14（--tt-text-3），title 为 切换仓库；菜单用 ShellMenu 左对齐、aria-label 为 仓库：分组标题「最近的仓库」；单选项为 src/mock/shell.ts 的最近仓库 demo-repo 与 docs-site，当前仓库（getMeta 的 repo_name）带勾、仓库名用 --tt-mono-sm；一条分隔线；[添加仓库…]（FolderPlusIcon 14）禁用、右侧小字「第二阶段接入」。选别的仓库只关菜单、界面不变。
- 连接胶囊：用 T005 的 ConnectionPill。state 来自夹具开关：offline 时为 disconnected，其余 connected；pid 18244、启动于 2026-10-18 09:41:07、事件流为「已订阅 /api/v1/events」或「已断开」；值都在 src/mock/shell.ts。
- 主题：触发钮用 IconButton size=sm，名称与提示依次是 主题：暗、主题：亮、主题：跟随系统，图标对应 MoonIcon、SunIcon、MonitorIcon；菜单用 ShellMenu 右对齐、aria-label 为 主题，三个单选项：跟随系统、亮、暗。

### 3. ShellMenu（src/shell/ShellMenu.tsx）
- 触发钮由调用方渲染；ShellMenu 提供 id、aria-haspopup=menu、aria-expanded、打开时的 aria-controls 与 onClick（IconButton 与 Button 都透传其余属性）。
- 面板 role=menu、带 aria-label。项三种：单选项 role=menuitemradio 带 aria-checked；普通项 role=menuitem；禁用项在上面基础上加 aria-disabled=true。分组标题是普通文字、分隔线 role=separator，两者都不可聚焦。
- 键盘与鼠标照 T004 的 Menu：打开后焦点到第一项；ArrowDown/ArrowUp 移动并循环，Home/End 到首尾；Enter 或点击选中、关菜单、焦点回触发钮；Esc 关菜单、焦点回触发钮、stopPropagation；Tab 关菜单；在菜单与触发钮之外按下鼠标关菜单。禁用项照 WAI-ARIA 可以聚焦，但 Enter 与点击都不选、菜单也不关。
- 样式照组件板 :455–460 与 Menu.css：面板宽 240、内边距 --tt-space-1、底 --tt-surface-1、1px --tt-border、--tt-radius-lg、--tt-shadow-2、层级 --tt-z-popover，位于触发钮下方 --tt-space-1、左或右对齐；项高 32、左右 --tt-space-2、--tt-radius-md、--tt-text-sm，悬停与聚焦 --tt-surface-3；选中的单选项底 --tt-surface-selected、前面 CheckIcon 14（--tt-tone-success-fg），没勾的项左侧留图标位；禁用项 --tt-text-disabled；分组标题 --tt-text-caption、--tt-text-3。类名用 tt-shell-menu*，不复用 tt-menu*。

### 4. Tab 栏（src/shell/TabBar.tsx，照 handoff :65–70 与 Main 画布 :40–58）
- 外框：nav，aria-label 为 主导航；高 --tt-tabbar-height、底 --tt-sidebar、上边框 1px --tt-sidebar-hover、左右内边距 --tt-space-2；DOM 顺序照画布放在内容区之前，用 order 排到最下面。
- 9 项依次总览、任务、角色与模型、CLI 运行时、凭据、日志与用量、插件、历史与审计、设置；图标 18 在上文字在下；最小宽 72；字 --tt-text-caption、--tt-sidebar-text；悬停 --tt-sidebar-hover；每项是 <a href=#/id data-tab=id>，title 为 标题（Ctrl+N），设置一项为 设置（Ctrl+,）。历史与审计与设置之间是一条 1px 竖线（--tt-sidebar-hover、aria-hidden、带 data-tab-divider）。
- 当前项：aria-current=page；底 --tt-sidebar-hover；字 --tt-sidebar-text-active 与 --tt-text-caption-strong；顶部一条 3px 的 --tt-accent 指示条（aria-hidden、左右各缩进 10、下方两角圆角见 Q3），只在当前项。
- 计数胶囊只在任务一项：数值是 getStatus 里属于「待验收」与「要你决定」两组的行数（分组照 UI 文档 3.4 :169–177）；为 0 或未读到时渲染；叠在图标右上（距顶 5、水平位置 50% + 5）；高 16、最小宽 18、左右 --tt-space-1、--tt-radius-full、底 --tt-accent、字色 --tt-on-accent、字体见 Q3；外圈用 0 0 0 2px var(--tt-sidebar) 的阴影；带 data-tab-count；所在链接 aria-label 写明数量，例如 任务（3 项需要你判断）。
- 状态段在最右，是 aria-live=polite 容器，title 为 kit 版本 · 仓库名。依次是：运行中 N（--tt-sidebar-dot-info 的 8px 圆点）与 需要你判断 N（--tt-accent 的 8px 圆点），两项都是指向 #/tasks 的链接，N 未读到时显示 —；上次更新（带 tt-hide-narrow 与 aria-live=off，文字随第 8 条的页面状态走：首次加载「正在读取…」、有数据「上次更新 X 前」、出错「读取失败 · 时:分:秒」，X 每秒刷新，断线时后面接「· 可能已过期」，不在页面框架里的路由（如陈列页）不渲染这一项）；kit 版本（带 tt-hide-narrow，文字 kit 2.12.0）。两个计数不带 tt-hide-narrow（窄窗口靠 base.css:63 现成规则隐藏）。状态段字 --tt-text-caption、--tt-sidebar-text-muted；两个计数链接用 --tt-sidebar-text，悬停加下划线。

### 5. 快捷键（src/shell/shortcuts.ts）
- 在 window 上监听 keydown；同时满足 ctrlKey 真、altKey/shiftKey/metaKey 都假、isComposing 假、事件未被 preventDefault 才处理：key 为 1 到 8 依次切前 8 个 Tab；key 为逗号切设置；处理了就 preventDefault，其余键不管。文档里有 role=dialog 且 aria-modal=true 的元素时不处理。Esc 不处理，各浮层自己关。

### 6. 主题（src/shell/theme.ts）
- 应用主题只改 html 元素的 data-theme：暗去掉属性；亮写 light；跟随系统写 system。不加类、不写内联样式、不动 body。缺省暗，偏好只存内存。applyTheme(pref) 是唯一写 data-theme 的地方，App 的偏好一变就调用。菜单三项「跟随系统、亮、暗」，当前偏好带勾。触发钮名称与提示随偏好（主题：暗/主题：亮/主题：跟随系统），不按实际明暗（不用 matchMedia）。

### 7. 数据层（src/api.ts、src/mock/）
- 夹具：src/mock/ 下 14 份 JSON，内容与 UI 文档第 9 节代码块逐值相等：meta.json(9.1)、status.json(9.2)、attempt.json(9.3)、file-executor-report.json 与 file-events.json(9.4 两块)、roles.json(9.5)、profiles.json/presets.json/preset-diff.json(9.6 三块)、runtimes.json(9.7)、plugins.json(9.9)、history.json(9.10)、usage.json(9.11)、secrets.json(9.12)。9.8、9.13、9.14 属于作业与写操作，本片不用。
- api.ts 声明第 9 节有示例的 13 个读函数：getMeta、getStatus、getAttempt(task, attempt)、readFile(task, attempt, path, cursor?)、getRoles、getProfiles、getPresets、diffPresets(a, b)、getRuntimes、getPlugins、getHistory、getUsage、listSecrets。返回 Promise<信封>；信封字段为 ok、exit_code、data、output、messages、command、elapsed_ms（8.9 :1093–1095）。
- 返回哪份夹具：getMeta→meta、getStatus→status；getAttempt(logs-cat, attempt-002)→attempt；readFile(logs-cat, attempt-002, executor-report.md 或 events.jsonl, 不带 cursor)→对应页；getRoles/getProfiles/getPresets/getRuntimes/getPlugins/getHistory/getUsage/listSecrets→各自夹具；diffPresets(default, economy)→preset-diff。夹具之外的参数（别的 task/attempt/path、带 cursor、别的方案对）一律返回 ok:false，exit_code 2，data null，messages 一条 ERROR「夹具里没有这份数据：…」。
- 信封：ok 真时 exit_code 0，data 是夹具，output 与 messages 都是空数组，elapsed_ms 0；command 照架构文档 5.2（:721–735）写 CLI 参数数组，不带程序名、不带 --json（例如 [status]、[logs, show, logs-cat/attempt-002]、[logs, cat, logs-cat/attempt-002, executor-report.md]、[config, role, show]、[config, preset, diff, default, economy]、[plugins, list]，参数顺序照 kit_logs.py:1288–1306）；合成的路由（meta、secrets）写第一条命令。
- 每次调用返回夹具的新深拷贝（JSON 往返）；用已兑现的 Promise 返回，不用计时器（开着假计时器也能在微任务里拿到结果）。
- 夹具开关（src/mock/scenario.ts）每次调用时读 location.hash 里的 mock：data 与 offline 照上面返回；loading 返回永不兑现的 Promise；error 返回 ok:false、exit_code 2、data null、command 照常、messages 为「ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied」（Main 画布 :237–238）；empty 时 getStatus/getRuntimes/listSecrets/getPlugins/getHistory 返回 src/mock/empty.ts 的空形状（status []；runtimes 空列表；secrets 空列表；plugins 的 plugins/not_installed/problems 都空、plugins_root_link false；history 的 entries/broken_lines 空、external_before_first 0），其余照常；getMeta 不受开关影响。
- 连接状态与最近仓库列表放在 src/mock/shell.ts：offline 时连接状态 disconnected，其余 connected。这两样不在 8.9 里，是外壳的事，标明是示意。

### 8. 页面框架（src/shell/PageFrame.tsx，照 Main 画布 :63–84、:205–241 与 UI 文档 5.5、6、8.1、8.2）
- 属性：title、description?、actions?、refreshLabel?（缺省 刷新）、load（返回 Promise<信封>）、isEmpty?、empty（空态标题与说明）、children(data)。
- 页面头：第一行 h1（--tt-title-lg）加右侧操作；第二行说明（--tt-text-sm、--tt-text-2）；刷新钮 Button secondary，内容 RefreshCwIcon 16 加文字。
- 挂载时调用 load；根元素带 data-page-state，取 loading/data/empty/error：首次加载渲染 T005 的 Skeleton（满 300ms 才出现）；ok 真且 isEmpty(data) 真时渲染 EmptyState，否则 children(data)；ok 假时渲染出错块（CircleXIcon 20 加「没能读到数据」用 --tt-danger-text；一段「命令（command 用空格连起来）返回退出码 N。内核报错如下（纯文本，已脱敏）：」；messages 用换行连起来放 pre 里按纯文本显示；[重试] Button primary 带 RefreshCwIcon，点击再调 load）；Promise 被拒时出错块只写「没有收到服务的回应」。
- 刷新：已有数据时保留数据，刷新钮进入加载态（Button loading：转圈、禁用、aria-busy）；结果回来后按上面规则重新判断。
- 断线（连接状态 disconnected）时：页面头下方一条 danger Banner（role=alert），文字「与本机服务的连接断开。下面是断开前的数据，可能已过期。」，后面接一个 DisabledAction [重新连接]（提示「接入本机服务后可用」）；有数据时标题旁加 neutral Tag「可能已过期」；数据照常显示，根元素带 data-stale=true。
- 只认最近一次请求的结果；卸载后不再写状态。向 Tab 栏状态段报告首次加载、有数据的时间与出错的时间。

### 9. 页面占位（src/pages/*Page.tsx，每页一个文件）
- 每页用 PageFrame；有数据时显示一行「夹具数据已读到」再写函数名（列表数据写条数）。
- 各页加载函数、说明与空态：总览、任务→getStatus，空态「还没有 attempt」说明「在规划端用 /dispatch-pi 派遣第一个任务」（UI 文档 6.2 :488）；角色与模型→getRoles，说明「四个角色各用哪个 CLI 与模型；方案可以一键切换」（6.4 :558）；CLI 运行时→getRuntimes，空态「还没有登记的 runtime」；凭据→listSecrets，说明「这里只显示每个环境变量在哪一层找到，从不显示值」（10.3），刷新钮叫「重新检查」，空态「还没有要检查的凭据变量」；日志与用量→getUsage；插件→getPlugins，空态「还没有插件」；历史与审计→getHistory，空态「还没有配置历史」；设置→getMeta。没写空态的页不传 isEmpty。总览说明是「仓库名 · kit 版本」（来自 getMeta）。

### 10. 禁用的写操作入口（src/shell/DisabledAction.tsx）
- 用 Tooltip 包一个 disabled 的 Button；Button 带一个设 pointer-events:none 的类，让悬停落到 Tooltip 的包裹 span 上。属性：label、reason（缺省「第二阶段接入」）、variant、size、icon?。

### 11. 陈列页（src/showcase/）
- ShowcasePage.tsx 用 import.meta.glob 急切导入 ./*Showcase.tsx（只同一目录、不含子目录），取各模块默认导出渲染，没有默认导出组件的模块跳过；ShowcasePage 自己的文件名不以 Showcase.tsx 结尾，收不到自己（Vite 本来也排除导入者自己）。排序按文件名 ASCII 编码顺序（JS 默认 sort，大写在前）。每个模块包在 div[data-showcase=文件名去掉 .tsx] 里，用 display:contents 不改变节间距。排序结果：BaseShowcase、EvidenceShowcase（T007 落地后）、FormsShowcase、ShellShowcase。
- 根 App 原来的内容原样搬进 BaseShowcase.tsx：样张（App.tsx:64–93）、Button/Tag/StatusTag/Card/Banner（:95–183）、图标按钮/菜单/对话框/抽屉/轻提示（:185–255）；顺序、文字、已有 data-* 都不变；只给五节原子加 data-demo，依次 button、tag、status-tag、card、banner；页头三个主题按钮（:57–61）去掉。
- showcase__* 类名不改；规则从 App.css 搬到 src/showcase/showcase.css 由 ShowcasePage 引入；去掉 .showcase 的 min-height:100vh；搬过去的 px 字面量补注释「演示自定」。
- ShellShowcase.tsx 两节：data-demo=page-states（五个链接分别打开 #/overview?mock=loading、data、empty、error、offline）；data-demo=disabled-action（四个禁用的写操作入口 [切换…]、[更改…]、[删除]、[启用…]）。
- ShowcasePage 的根元素是 div.showcase，页头 h1「组件陈列」加一行说明；不放主题按钮，不用 PageFrame。

### 12. 不连服务的静态检查（tests/shell-no-network.test.ts）
- 递归读 desktop/web/src 下全部文件（不论扩展名），按整词找 fetch、XMLHttpRequest、EventSource、WebSocket（前后不是字母、数字、下划线或美元符；注释与字符串都算）；找到就失败并报 路径:行号。自检样本：要报 window.fetch(、new WebSocket(、在 globalThis 上用方括号与字符串取 fetch 的写法；不报 prefetchAll、fetchedAt。

### 13. README
- 增补：目录约定（shell/、pages/、mock/、api.ts、icons/frame.tsx）；showcase/ 的收集与排序规则以及怎样加一节演示；路由表与 #/showcase；?mock= 的五个取值；不连服务的检查；主题改由标题栏的菜单切换。命令一节不动（G2 :655）。

### 边界与错误
- 构建：npm run build 里的 tsc --noEmit 必须过。check:contract 扫 TSX 全文（只剥块注释），演示文字与行注释不写井号加 3/4/6/8 位十六进制字符、不写 rgb( 这类函数名加括号；App.css 不出现 letter-spacing、不用 [data-font-weight] 选择器。
- jsdom 里写 location.hash 同步改地址、hashchange 异步；导航要同步更新状态（第 1 条）。
- 计时用 setTimeout（不用 rAF/performance）；夹具用已兑现的 Promise。

### 并发、取消与状态变化
- PageFrame 只认最近一次请求；卸载后不再写状态。主题偏好是内存状态。计数与状态段随夹具开关与页面状态变化。

### 兼容性
- 只改允许的文件；不改 src/components/**、src/icons/index.tsx、src/styles/**、src/domain/**、src/main.tsx、src/vite-env.d.ts、src/showcase 的 T007 文件、package.json、锁文件、index.html、vite.config.ts、tsconfig.json、scripts/**、public/**、fonts/**、THIRD_PARTY_NOTICES.md、除 Q2 三份外的既有测试；不新增依赖。
- T001–T005 门禁、W4、W5 照常通过；不推翻现有过渡断言。

### 过渡断言
- 本片门禁里按过渡命名的断言（后面的片会推翻）：页面占位的内容与空态文案；api 返回夹具与 ?mock= 开关（接本机服务那一片推翻）；App 级的五态（经 ?mock= 演示）；陈列页里各演示的内容。
- 长期断言：路由与 Tab 栏、快捷键、计数显示规则、状态段、主题、标题栏结构；页面框架的五态（用注入的加载函数测）、禁用入口的写法、不连服务；夹具 JSON 与 UI 文档逐值相等；陈列页的收集与排序规则。

### 人工验收项（H1–H10，不由门禁或执行端代做）
- H1 视觉对照 Main 画布与各页主稿的标题栏、Tab 栏、页面头，暗色亮色各一次；H2 1024×640 与缩放 80%–200%；H3 窗口宽 1179 与 1180 两侧；H4 暗/亮/跟随系统各看一次；H5 真浏览器（npm run dev 带 StrictMode，再 vite preview）；H6 浮层（标题栏胶囊与两个菜单盖在内容之上；陈列页抽屉/轻提示/对话框遮罩）；H7 禁用入口悬停出提示；H8 读屏抽查（可选）；H9 五态在真实框架里 #/overview?mock= 各看一次；H10 更纱 11–12px 在 Windows 100%/150% 缩放下是否清楚。

## Steps
1. 预检（只读）：核对 Repository facts 与规划 §10 的 A1–A13 假设，不符就停；跑一次 npm ci、build、test 记下基线结果。风险低。
2. 夹具与数据层：src/mock/ JSON（逐字拷 UI 文档第 9 节）、scenario.ts、empty.ts、shell.ts；src/api.ts；测试 shell-api、shell-no-network。验收意图 S1、S2、P9。
3. 路由与快捷键：router.ts、routes.ts、shortcuts.ts；测试 shell-router、shell-shortcuts。P2、P3。
4. 主题：theme.ts；测试 shell-theme。P5。
5. ShellMenu：ShellMenu 一对文件；测试 shell-menu。P6。
6. 标题栏：Logo、icons/frame.tsx、TitleBar；测试 shell-titlebar。S3、P6。
7. Tab 栏：attemptGroups.ts、relativeTime.ts、TabBar；测试 shell-tabbar。S4、P4。
8. 页面框架与禁用入口：PageFrame、DisabledAction；测试 shell-page-frame。P7、P8。
9. 页面占位与框架装配：src/pages/ 的 9 页；App.tsx、App.css；测试 shell-app。P10、P12。
10. 陈列页：ShowcasePage、showcase.css、BaseShowcase（原样搬）、ShellShowcase；Q2 批准后改 3 份测试的挂载；测试 shell-showcase。P11、S6。
11. README：第 13 条。
12. 执行端测试与自检：desktop/web 下依次 npm ci（要网络）、npm run build、npm test、npm run check:contract；仓库根点名跑 V01–V03；确认 git status 没有新的未忽略文件。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与第 12 步自检里跑（与 T002–T005 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t006_baseline.py -q` · cwd：仓库根 · 超时：1200s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py -q` · cwd：仓库根 · 超时：9000s · 期望退出码：0 · 输出须匹配 `\d+ passed`，不得出现 `failed|error`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`

说明：V01 的 tests/test_gate_t006_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）；V02 合并 T001–T005 五份门禁回归，点名运行以让前端流水线不被 conftest 跳过（每份各跑一遍 npm ci 与构建，9000s 充裕）；V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。门禁要点名运行，conftest 才不会跳过前端流水线（tests/conftest.py:30–41）。

## Definition of done
- D01：路由——空 hash 是总览；9 个 Tab 的顺序、文字、title 与分隔线正确；点击切页后地址、当前项、h1 同步变；未知路由回总览；#/tasks/x/y 归任务；#/showcase 没有当前项并渲染陈列页；document.title 随页面变；证据：V01；目的：页面都能用地址打开，陈列页离开根路由。
- D02：标题栏——Logo、产品名、连接胶囊都在；仓库菜单当前项 aria-checked=true、禁用项 aria-disabled=true 且选不了；主题菜单在；两个菜单键盘操作正确、Esc 后焦点回触发钮；右内边距 140；证据：V01；目的：标题栏四样东西都在且键盘可用。
- D03：Tab 栏——9 项顺序与图标、最小宽 72、当前项 aria-current=page 加 3px 金条；计数为 0 或未读时不渲染、为 3 时有 data-tab-count 且文字是 3；状态段 aria-live=polite，上次更新与 kit 版本带 tt-hide-narrow 且上次更新 aria-live=off；证据：V01；目的：导航与状态一眼可见，计数只数要你处理的。
- D04：快捷键——Ctrl+1…8 与 Ctrl+, 切页且 keydown 被 preventDefault；带 Alt/Shift/Meta 不切；Ctrl+9 不切；模态对话框打开时不切；证据：V01；目的：键盘能切页又不误伤别的组合键与模态框。
- D05：主题——缺省无 data-theme；经菜单选亮、跟随系统、暗，data-theme 依次 light、system、去掉；html 与 body 其余属性不变、无内联样式；触发钮名称随偏好变；证据：V01；目的：主题只经 data-theme 切换。
- D06：数据层——13 个函数 data 与 UI 文档第 9 节 JSON 逐值相等、信封字段齐全；改返回值不影响下一次；夹具外参数返回 ok:false；证据：V01；目的：后面的页面照真实接口编码。
- D07：夹具开关——五个取值（data/loading/empty/error/offline）效果都对；getMeta 不受开关影响；empty 只对 5 个列表资源生效；证据：V01；目的：五态能在真实框架里看到。
- D08：不连服务——递归扫 desktop/web/src 全文件按整词找 fetch/XMLHttpRequest/EventSource/WebSocket，一个都没有；自检样本行为正确；证据：V01；目的：运行时不发任何网络请求。
- D09：页面框架——299ms 无骨架、300ms 有；有数据、空两态正确；出错块的命令、退出码、报错原文都是纯文本、点重试再调一次；断线时保留数据、有 role=alert Banner 与「可能已过期」、data-stale=true；刷新保留数据、按钮 aria-busy；先发后回的结果被丢弃；证据：V01；目的：五态与刷新只实现一处。
- D10：页面占位——9 页各自加载函数、说明与空态；有数据时显示「夹具数据已读到」加函数名（列表写条数）；总览说明是仓库名 · kit 版本；证据：V01。
- D11：禁用入口——Tooltip 包 disabled Button、Button 带 pointer-events:none 的类；悬停包裹元素 399ms 无提示、400ms 出现 role=tooltip；证据：V01；目的：站主 Q7 的写法后续可直接用。
- D12：陈列页——data-showcase 的值与顺序等于目录里 *Showcase.tsx 文件名的排序结果（每次现读目录）；BaseShowcase 原样搬、五节原子带 data-demo；ShellShowcase 两节；整页只有一个 role=status、无文字按钮都有 aria-label；3 份既有测试只改挂载后照常通过；证据：V01、review；目的：陈列页自动收集、原有演示一个不丢。
- D13：回归——T001–T005 门禁全绿（Q1 处理之后，含现有过渡断言）；W5 通过；npm ci、build、test、check:contract 都退出 0；证据：V02、V03、V01。
- D14：范围与纪律——只改允许的文件；不改依赖；既有测试只按 Q2 改挂载；新测试不用 skip、only、todo；遵守禁用词与 W4；证据：scope、review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 src/components/**、src/icons/index.tsx、src/styles/**、src/main.tsx、package.json、锁文件、门禁测试 tests/test_gate_t006_*.py）。
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

- 基线 `50b823d744da48e3266fd3a6459057c8d8d943e0` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面终审列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

B1（退回执行端）desktop/web/src/pages/RolesPage.tsx:5（定义 isRolesEmpty）与 :13（isEmpty={isRolesEmpty}）：删除这两处，让 getRoles 返回空的 roles 列表时 data-page-state 仍为 data、正文含「夹具数据已读到」。依据：合同第 9 条（.agent/plans/t006-desktop-shell.v1.md:218）「没写空态的页不传 isEmpty」，角色与模型一项只写了说明、没写空态；UI 设计文档 6.4 也没有角色列表的空状态；门禁 WB53 可复现（python -m pytest tests/test_gate_t006_whitebox.py -q -k WB53，报 expected 'empty' to be 'data'）。只改这一个文件；不要给角色页补 empty 文案；RolesData 类型导入仍被 PageFrame<RolesData> 使用，保留；其余文件一律不动。
