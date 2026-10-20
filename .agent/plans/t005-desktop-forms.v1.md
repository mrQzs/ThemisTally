# TASK: t005-desktop-forms

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 5640a2ce1db79333347c0c66f9b692f60d718cb5
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T005 第 4 片（桌面端前端表单与数据原子）。在 desktop/web/ 新增 12 个表单与数据原子组件（分段选择、开关、复选框、页签、输入框、下拉、表格、键值列表、空状态、骨架屏、连接胶囊、面包屑）与配套 CSS、4 个新图标，修 T004 留下的四处（对话框遮罩、轻提示关闭钮工具提示、两处 16px、基础重置特异性），并在陈列页追加 11 节演示；不改依赖、不改令牌、不改 App.css、不移动陈列页。

## Non-goals
- 多行文本与标签输入（D2）；输入框里的图标与清除钮；下拉的多选、分组、搜索。
- 表格的排序、多选、列宽拖动、虚拟滚动、单元格里的可聚焦控件、空表格占位、页面级表头吸顶。
- 复选框半选；页签关闭钮与溢出滚动。
- T004 终审的建议类（菜单点击选中测试、Tooltip 的 suppressedRef 死代码、cloneElement 覆盖 aria-describedby、IconButton 的 {...rest} 顺序、focusable.ts 注释；轻提示关闭钮圆角与图标尺寸）。
- 应用框架、证据组件、写操作、接本机服务、七端视图、工具链升级、Electron 外壳。

## Repository facts
- 入口：desktop/web/src/main.tsx 挂载 desktop/web/src/App.tsx（组件陈列页，根元素带 tt-app、tt-content、showcase 三个类）；主题按钮在页头；desktop/web/src/components/index.ts 统一导出 T002 的 5 个原子组件与 T004 的 6 个浮层组件。
- 调用关系与现有约定：
  - base.css:12 是 .tt-app button, .tt-app input, .tt-app select, .tt-app textarea { font: inherit; color: inherit; margin: 0 }（特异性 (0,1,1)）；:13–14 是 cursor 规则、:15 是 a、:16 是 table、:17 是占位符，也都是元素重置；:22–23 是 :focus-visible 焦点规则；:39–40 的 tt-pulse 只改不透明度、.tt-skel 用它；:47–49 减少动效时 .tt-skel 静止。
  - main.tsx:3–6 先 import App 再引入 fonts、tokens、base 三份样式，产物里 base.css 排在组件 CSS 之后，同特异性时它胜出。
  - Dialog.tsx:57 遮罩 onMouseDown 无条件 preventDefault（e.target === e.currentTarget 之外也拦）；:64 对话框根 tabIndex=-1；overlay/useOverlayFocus.ts 打开时聚焦第一个可聚焦元素；overlay/focusable.ts 的选择器包括 tabindex 不为 -1 的元素。
  - Toast.tsx 关闭钮是裸 button、aria-label 为「关闭提示」，两个图标用 width/height 属性写 16；Toast.css:35 是 .tt-toast__close svg { width:16px; height:16px }（重复）。
  - IconButton.css:18 的 .tt-icon-btn svg { width:16px; height:16px } 没有出处注释；icons/index.tsx:8 图标缺省 24；Tooltip.tsx 用 cloneElement 设 aria-describedby；Tooltip.css 不换行、pointer-events: none；Menu.tsx 触发钮固定是 Button。
  - styles/tokens.css:48 有 --tt-z-sticky 10、--tt-z-popover 100；§5 用到的颜色、字体、圆角、阴影、间距令牌都在；尺寸令牌只有 --tt-tabbar-height。
  - App.tsx 现有 5 节演示的 data-demo 依次为 icon-button、menu、dialog、drawer、toast，toast 一节在最后（页尾）。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，没有 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试文件不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD 2a86c37，git status 干净。T005 门禁 tests/test_gate_t005_baseline.py 是 V01 的目标文件，由门禁端稍后写好、内核做成基线提交，基线上不存在。T001–T004 门禁 tests/test_gate_t00{1,2,3,4}_baseline.py 都在，基线上应通过（回归）。
- 仓库外事实（站主已核实，以 20261020T022919695213Z-owner-f33b69 的答复为准，合同按已核实写）：
  - F7 :where() 的浏览器支持成立：本机 Chrome 155 headless 实测 CSS.supports('selector(:where(a))') 为 true；:where(.tt-app) button { color: inherit } 生效，.tt-icon-btn 的 --tt-text-2 取到令牌色，现行 .tt-app button 会把图标按钮盖成继承色；最低版本 Chromium 88（公开支持数据，未逐版实测；将来的 Electron 只会用更新的 Chromium）。
  - F8 构建后 dist 保留 :where(：用 desktop/web 的 vite 5.4.11（esbuild 0.21.5）在临时目录构建最小项目，dist 的 CSS 原样保留 :where( 选择器；target chrome87 的转换结果相同，无警告。门禁 P1 仍会在真构建产物上再查一遍。

## Scope
- allowed_modified_files:
  - desktop/web/src/components/Dialog.tsx
  - desktop/web/src/components/Toast.tsx
  - desktop/web/src/components/Toast.css
  - desktop/web/src/components/IconButton.css
  - desktop/web/src/styles/base.css
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/components/index.ts
  - desktop/web/src/App.tsx
  - desktop/web/README.md
  - desktop/web/src/components/SegmentedControl.tsx
  - desktop/web/src/components/SegmentedControl.css
  - desktop/web/src/components/Switch.tsx
  - desktop/web/src/components/Switch.css
  - desktop/web/src/components/Checkbox.tsx
  - desktop/web/src/components/Checkbox.css
  - desktop/web/src/components/Tabs.tsx
  - desktop/web/src/components/Tabs.css
  - desktop/web/src/components/TextField.tsx
  - desktop/web/src/components/TextField.css
  - desktop/web/src/components/Select.tsx
  - desktop/web/src/components/Select.css
  - desktop/web/src/components/Table.tsx
  - desktop/web/src/components/Table.css
  - desktop/web/src/components/KeyValueList.tsx
  - desktop/web/src/components/KeyValueList.css
  - desktop/web/src/components/EmptyState.tsx
  - desktop/web/src/components/EmptyState.css
  - desktop/web/src/components/Skeleton.tsx
  - desktop/web/src/components/Skeleton.css
  - desktop/web/src/components/ConnectionPill.tsx
  - desktop/web/src/components/ConnectionPill.css
  - desktop/web/src/components/Breadcrumb.tsx
  - desktop/web/src/components/Breadcrumb.css
  - desktop/web/src/components/field/*.tsx
  - desktop/web/src/showcase/*.tsx
  - desktop/web/src/showcase/*.css
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/toast-close-tooltip.test.tsx
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/tests/component-css.test.ts
- allowed_new_files:
  - desktop/web/src/components/SegmentedControl.tsx
  - desktop/web/src/components/SegmentedControl.css
  - desktop/web/src/components/Switch.tsx
  - desktop/web/src/components/Switch.css
  - desktop/web/src/components/Checkbox.tsx
  - desktop/web/src/components/Checkbox.css
  - desktop/web/src/components/Tabs.tsx
  - desktop/web/src/components/Tabs.css
  - desktop/web/src/components/TextField.tsx
  - desktop/web/src/components/TextField.css
  - desktop/web/src/components/Select.tsx
  - desktop/web/src/components/Select.css
  - desktop/web/src/components/Table.tsx
  - desktop/web/src/components/Table.css
  - desktop/web/src/components/KeyValueList.tsx
  - desktop/web/src/components/KeyValueList.css
  - desktop/web/src/components/EmptyState.tsx
  - desktop/web/src/components/EmptyState.css
  - desktop/web/src/components/Skeleton.tsx
  - desktop/web/src/components/Skeleton.css
  - desktop/web/src/components/ConnectionPill.tsx
  - desktop/web/src/components/ConnectionPill.css
  - desktop/web/src/components/Breadcrumb.tsx
  - desktop/web/src/components/Breadcrumb.css
  - desktop/web/src/components/field/*.tsx
  - desktop/web/src/showcase/*.tsx
  - desktop/web/src/showcase/*.css
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/toast-close-tooltip.test.tsx
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/tests/component-css.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/styles/tokens.css
  - desktop/web/src/styles/fonts.css
  - desktop/web/src/main.tsx
  - desktop/web/src/App.css
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
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Banner.*
  - desktop/web/src/components/StatusTag.*
  - desktop/web/src/components/Tooltip.*
  - desktop/web/src/components/Menu.*
  - desktop/web/src/components/Drawer.*
  - desktop/web/src/components/Dialog.css
  - desktop/web/src/components/IconButton.tsx
  - desktop/web/src/components/overlay/**
  - desktop/web/src/domain/**
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/font-specimen.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/toast.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - tests/test_gate_*.py
  - tests/test_gate_t005_*.py
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
- 组件名、属性名、类名、data-*、data-demo 取值与按钮文字在本合同定下后，门禁按它写探针、解析 CSS，执行端不得再改。
- 键盘一律看 event.key：ArrowLeft、ArrowRight、ArrowUp、ArrowDown、Home、End、Enter、Escape、空格（' '）。组件处理了的键都 preventDefault，测试可断言 fireEvent.keyDown 返回 false。
- Roving TabIndex：组内恰一个元素 tabIndex=0（当前项），其余 -1；方向键移动时同时移真实焦点、改 tabIndex。
- 受控组件：value 或 checked 加 onChange；测试用一个持有状态的小外壳。
- 颜色、字体、圆角、阴影、层级只用 --tt-* 令牌；间距有对应 --tt-space-* 时用令牌，就近取刻度、平局取小（10 取 8、6 取 4）；尺寸字面量同一行带出处注释（文档节号或画布行号）。
- 新组件都不渲染 role=status；不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。

### 1. TextField（输入框）
- API：label、help?、error?、mono?（值用等宽），其余透传给 input（value、onChange、placeholder、disabled 等）。
- 结构：label 用 htmlFor 关联；出错与帮助文字各有 id；aria-describedby 依次放出错、帮助的 id，只放渲染了的；有 error 时 aria-invalid=true；两者都给时都显示。
- 样式（组件板 :356–360、UI 文档 7.3 :782–785）：高 32；1px --tt-border-strong；--tt-radius-md；底 --tt-surface-1；字 --tt-text-1、--tt-text-md（等宽用 --tt-mono-md）；左右 --tt-space-2；聚焦用 base.css:23 现成规则；出错边框 --tt-danger-text，出错文字 --tt-text-sm 加 --tt-danger-text；帮助文字 --tt-text-caption 加 --tt-text-3；标签 --tt-text-caption-strong 加 --tt-text-3，与控件间距 --tt-space-1；禁用：底 --tt-surface-2、字 --tt-text-disabled、边框 --tt-border。

### 2. Select（下拉）
- API：与 TextField 相同的 label、help、error；options: { value, label }[]；value、onChange、disabled。
- 原生 select，appearance: none，右内边距 32（--tt-space-8）；右侧 ChevronDownIcon 16，aria-hidden、pointer-events: none、--tt-text-3，右边距 --tt-space-2，垂直居中。其余样式与关联同第 1 条。

### 3. SegmentedControl（分段选择）
- API：options: { value, label }[]、value、onChange(value)、aria-label。
- 结构（组件板 :369）：role=radiogroup；段是 button type=button role=radio aria-checked。
- 键盘：ArrowRight、ArrowLeft 选中下一段、上一段并移焦点，到头循环（同原生单选组）；只处理左右；点击选中。
- 样式（UI 文档 7.4、handoff :146）：轨道 --tt-surface-2、1px --tt-border、--tt-radius-md、内边距 --tt-space-0_5；段高 28、左右 --tt-space-3、--tt-radius-sm、--tt-text-sm-medium、--tt-text-2、透明底；选中段 --tt-surface-1、--tt-shadow-1、--tt-text-1。

### 4. Switch（开关）
- API：checked、onChange(next)、label（可见文字）、disabled?。
- 结构：一个 role=switch 的 span，不是 button（避免浏览器在 keyup 再点一次导致切两次）；aria-checked；可用时 tabIndex=0；里面是轨道与文字，名称来自文字。
- 键盘与鼠标：空格的 keydown 切换一次并 preventDefault，event.repeat 为真时不切换；点击整个控件切换；禁用时 aria-disabled=true、不可聚焦，点击与空格都不切换。
- 样式（组件板 :374–377、UI 文档 7.5、handoff :146）：轨道 32×18、--tt-radius-full；关：底 --tt-surface-2、边框 1px --tt-border-strong、圆点 --tt-border-strong；开：底与边框 --tt-primary、圆点 --tt-on-primary；圆点 12，上 2，关时左 2、开时左 16；禁用：底 --tt-surface-2、边框 --tt-border、圆点与文字 --tt-text-disabled；文字 --tt-text-sm，与轨道间距 --tt-space-2。焦点环用 base.css 的 :focus-visible（会包住轨道与文字，画布只包轨道）。

### 5. Checkbox（复选框）
- 选 ARIA 自绘：role=checkbox 的 span，aria-checked；键盘、鼠标、禁用同开关，只认空格，不认 Enter（同 WAI-ARIA 复选框模式）。
- 理由：jsdom 只在 click 上跑激活行为，原生复选框的空格在门禁里测不到；与开关同一套写法；本片筛选都是受控状态。
- 样式（组件板 :378–379、handoff :146）：框 16、--tt-radius-sm；未选：1px --tt-border-strong、底 --tt-surface-1；已选：底 --tt-primary、CheckIcon 12 用 --tt-on-primary、描边 3；文字 --tt-text-sm，间距 --tt-space-2。

### 6. Tabs（页签）
- API：items: { id, label }[]、value、onChange(id)、aria-label、children（当前面板的内容）。
- 结构：role=tablist；页签 button type=button role=tab aria-selected，当前页签带 aria-controls 指向面板；面板 role=tabpanel、aria-labelledby 指向当前页签。
- 键盘：ArrowRight、ArrowLeft 切换并移焦点，到头循环；Home、End 到首尾；选中跟着焦点走（自动激活）。
- 样式（组件板 :381–385、UI 文档 7.6、handoff :146）：列表下边框 1px --tt-border、页签间距 --tt-space-1；页签高 38、左右 --tt-space-3、--tt-text-md-medium、--tt-text-2；当前 --tt-text-1、下边 2px --tt-primary、margin-bottom: -1px；悬停 --tt-surface-3、上两角 --tt-radius-md。

### 7. Table（表格）
- API：columns: { key, header, numeric?, mono? }[]、rows、rowKey(row)、rowHeight?: 40 | 44 | 52（缺省 40）、onRowOpen?(key)、selectedKey?、aria-label、className?（加在滚动容器上，调用方用它限高；不用内联 style）。
- 结构：滚动容器 div 里一个原生 table；th scope=col；行 tr 带 tabIndex；表上带 data-row-height；选中行带 data-selected。
- 键盘：Roving，起点是选中行，没有就第一行；ArrowDown、ArrowUp 移动，到头不循环；Home、End 到首尾；Enter 调一次 onRowOpen(当前行的 key)；点击行等于让它成为当前行并调 onRowOpen。表格与容器本身不进 Tab 序列。
- 吸顶与滚动：容器 overflow: auto，单元格不换行（宽度不够时在容器里横向滚动，不撑开页面）；表头 position: sticky、top: 0，以容器为参照（容器限高时在容器里吸顶，不限高时随页面滚走；页面级吸顶留给应用框架那一片）；建议容器加 scroll-padding-top 等于表头高。
- 样式（组件板 :411–418、任务页 :367–391、UI 文档 7.9、handoff :142）：容器 --tt-surface-1、1px --tt-border、--tt-radius-lg；表头高 32、position: sticky、top: 0、z-index: var(--tt-z-sticky)、--tt-surface-2、--tt-title-sm、--tt-text-2、左右 --tt-space-3；行高 40/44/52、上边框 1px --tt-border、--tt-text-sm；悬停 --tt-surface-3；选中 --tt-surface-selected 加左侧 2px --tt-primary（inset 阴影）；数字列右对齐、带 tt-num；mono 列 --tt-mono-sm。焦点环建议画在单元格上（inset 阴影）。

### 8. KeyValueList（键值列表）
- API：items: { label, value, mono? }[]。
- 结构：dl，每项一对 dt、dd。
- 样式（组件板 :451、UI 文档 7.23 :971）：两列网格，标签列 minmax(96px, max-content)、值列 minmax(0, 1fr)；行距 --tt-space-1、列距 --tt-space-3；--tt-text-sm；标签 --tt-text-3；值 --tt-text-1；等宽值 --tt-mono-sm、行高 20。

### 9. EmptyState（空状态）
- API：icon?（缺省 ListChecksIcon）、title、description?、action?（没有就不渲染操作区）。
- 样式（组件板 :465–470、UI 文档 7.23 :969）：纵向居中、文字居中，间距 --tt-space-1；内边距 --tt-space-6 与 --tt-space-4；1px --tt-border、--tt-radius-lg；图标 32（CSS 给 svg 定尺寸）、--tt-text-3、aria-hidden；标题 --tt-title-sm；说明 --tt-text-sm 加 --tt-text-2；操作区上边距 --tt-space-1。

### 10. Skeleton（骨架屏）
- API：没有必填属性；挂载即开始计时，卸载即消失。页面写 loading && <Skeleton />。
- 时序：挂载后 300ms 内不渲染任何骨架元素，满 300ms 出现：299ms 没有、300ms 有；300ms 前卸载，计时器清掉，什么都不出现。300 写成具名常量，用 setTimeout（不能用 rAF 或 performance，fake timers 推不动）。
- 结构与样式（组件板 :474–480、handoff :154）：容器 aria-busy=true、纵向间距 --tt-space-2、内边距 --tt-space-4、1px --tt-border、--tt-radius-lg；条 tt-skel、aria-hidden、--tt-surface-3、--tt-radius-sm，高 14、20、20、20，宽 40%、100%、82%、64%。不写动画、过渡、渐变，不做扫光；tt-pulse 与减少动效用 base.css 现成的。

### 11. ConnectionPill（连接胶囊）
- API：state: connected | reconnecting | disconnected、attempt?（重连第几次）、pid?、startedAt?（已格式化的文字）、stream?（事件流那一行）。没给的值显示「未知」。
- 文字（断线页 :448）：已连接；重连中（第 N 次）；已断开。根上带 data-state。
- 色调（组件板 :435–437、断线页 :449–450、UI 文档 7.20）：圆点 已连接 --tt-tone-success-fg、重连中 --tt-tone-warning-fg、已断开 --tt-tone-danger-fg；文字 --tt-text-2、--tt-tone-warning-fg、--tt-danger-text。
- 结构：胶囊是 button type=button，带 aria-expanded、aria-controls；里面是圆点（aria-hidden）与状态文字（aria-live=polite）。
- 交互：点一下打开、再点关闭；浮层在胶囊下方、右对齐、宽 240、层级 --tt-z-popover，里面一个小键值表：pid、启动于、事件流。浮层打开时焦点在胶囊上按 Esc：关闭并 stopPropagation，焦点留在胶囊；在胶囊与浮层之外按下鼠标：关闭。浮层里没有可聚焦元素，焦点不移进去；它在 DOM 里紧跟胶囊。
- 样式（handoff :148）：高 24、左右 --tt-space-2、间距 --tt-space-1、1px --tt-border、--tt-radius-full、--tt-surface-1、--tt-text-caption；悬停 --tt-surface-3；圆点 8。浮层（断线页 :292–297）：绝对定位、右对齐、在胶囊下方、宽 240、内边距 --tt-space-2 与 --tt-space-3、--tt-surface-1、1px --tt-border、--tt-radius-lg、--tt-shadow-2、--tt-z-popover、tt-enter；里面的 dl 标签列 64、--tt-text-sm；pid 用 --tt-mono-sm 加 tt-num；三行标签：pid、启动于、事件流。

### 12. Breadcrumb（面包屑）
- API：items: { label, href?, onClick? }[]，最后一项是当前页。
- 结构：nav aria-label 为「面包屑」里一个 ol；前面的项有 href 就渲染 a，否则渲染 button type=button（样式像链接）；最后一项是带 aria-current=page 的 span，既不是链接也不是按钮；项之间是 ChevronRightIcon 14、aria-hidden。
- 样式（组件板 :449）：--tt-text-sm、--tt-text-3、间距 --tt-space-1；链接与按钮 --tt-link、不加下划线；当前项 --tt-text-2。

### 13. 导出、陈列页与 README
- components/index.ts：导出 12 个新组件与 Props 类型，原来 11 个仍在，不出现 overlay 字样；文件头注释改成四片的总述。
- 陈列页：新演示放在 src/showcase/，App.tsx 在 data-demo 为 toast 的一节之后渲染它们；样式写在新的 CSS 里，复用 App.css 已有的 showcase__section、showcase__h2、showcase__row，不改 App.css。
- 11 节，data-demo 取值与顺序：text-field（默认、带帮助、出错、禁用各一个输入框，加一个下拉）、form-dialog（按钮「打开表单对话框」，框里一个输入框与一个下拉，底栏「取消」「确定」）、segmented、switch-checkbox、tabs、table、key-value、empty-state、skeleton、connection、breadcrumb。每节恰一个 data-demo。
- 表格演示：一个分段选择切 40、44、52 三档；有数字列（用时、token）；行数列数够多，容器限高、比表窄，人工看吸顶与横向滚动；Enter 或点击后旁边显示「上次打开：…」。
- 骨架屏演示：两个按钮「加载 2 秒」「加载 0.2 秒」，后者用来看短加载不闪骨架。
- 连接胶囊演示：三态并排，各自能点开浮层。
- 演示文字避开井号（尤其 href）与 rgb( 这类「函数名加括号」的写法；节标题里不写 Button；「亮、暗、跟随系统」这几个字只留在页头的主题按钮上。
- README.md：目录约定加新组件与 showcase/；一句话写基础重置的约定与检查；命令一节不动。

### T004 修补（目标 7）
- 7.1 对话框遮罩：Dialog.tsx:57 改成只在 e.target === e.currentTarget 时 preventDefault，文件头注释同步。新测试两条：在对话框内容上 mousedown 不被阻止（fireEvent.mouseDown 返回 true），在遮罩本身上仍被阻止（返回 false）。
- 7.2 轻提示关闭钮工具提示：Toast.tsx 的关闭钮外包 T004 的 Tooltip，提示文字与名称同为「关闭提示」。
- 7.3 两处 16px：删 Toast.css:35 的 .tt-toast__close svg；IconButton.css:18 的 svg 16px 加出处注释（组件板 :340，图标 16），保留。
- 7.4 基础重置特异性：base.css 第 12–17 行的元素重置一律包进 :where()（特异性降到 0），建议写法：
  - :where(.tt-app) :where(button, input, select, textarea) { font: inherit; color: inherit; margin: 0; }
  - :where(.tt-app) :where(button) { cursor: pointer; }
  - :where(.tt-app) :where(button:disabled) { cursor: not-allowed; }
  - :where(.tt-app) :where(a) { color: var(--tt-link); }
  - :where(.tt-app) :where(table) { border-collapse: collapse; border-spacing: 0; }
  - :where(.tt-app) :where(input)::placeholder { color: var(--tt-text-3); }
  - 焦点规则（:22–23）与其余规则不动。配静态测试 tests/base-reset.test.ts：特异性计算器（#id 记 a、类/属性/伪类记 b、元素/伪元素记 c、:where() 记 0、:is()/:not()/:has() 取参数最大、选择器列表按顶层逗号切）；自检样本（.tt-app button 为 (0,1,1)、:where(.tt-app) :where(button, input, select, textarea) 为 (0,0,0)、:where(.tt-app) :where(input)::placeholder 为 (0,0,1)、.tt-icon-btn:hover:not(:disabled) 为 (0,3,0)）；对真实 base.css 检查凡主体含 button/input/select/textarea/a/table 且不含 :focus-visible 的规则，特异性都低于 (0,1,0)；正向检查仍有一条同时声明 font: inherit、color: inherit、margin: 0 且覆盖四种元素的规则；与 Button/IconButton/Toast 的单类规则交叉核对。门禁另在 dist 的 CSS 查 :where(。

### 边界与错误
- 构建：npm run build 里的 tsc --noEmit 必须过。
- 契约检查 check:contract 扫 TSX 全文（只剥块注释）：演示文字与行注释不能出现井号加 3/4/6/8 位十六进制字符，也不能出现 rgb(、lab(、color( 这类「函数名 + 括号」；App.css 不能出现 letter-spacing，不能用 [data-font-weight] 选择器。
- jsdom 里已连接、带可解析 tabindex 的元素都可聚焦；空格的切换必须由组件自己处理（jsdom 不把按键变点击）。
- 计时用 setTimeout；不用 rAF、performance（fake timers 推不动）。

### 并发、取消与状态变化
- 骨架屏挂载计时、卸载清计时器；StrictMode 下 effect 跑两遍，计时幂等。连接胶囊的开合是同步状态。

### 兼容性
- 只改允许的文件；tokens.css、fonts.css、main.tsx、App.css、package.json、锁文件、index.html、vite.config.ts、tsconfig.json、scripts/**、Button/Tag/Card/Banner/StatusTag/Tooltip/Menu/Drawer 组件、Dialog.css、IconButton.tsx、overlay/**、domain/**、既有测试都不动；不新增依赖（dependency_changes: forbidden）。
- T001–T004 门禁、W4、W5 照常通过；不推翻现有 4 条过渡断言。

### 禁止的做法
- npm install 或升级依赖；在 tokens.css 加令牌；改 base.css 第 12–17 行以外的规则。
- 新组件渲染 role=status；陈列页上出现没有文字也没有 aria-label 的 button。
- 调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；单元格里放可聚焦元素。
- 把带 aria-describedby 的输入框包进 Tooltip；把菜单或连接胶囊放进对话框。

### 过渡断言
- 门禁里只有 P12 一条按 test_transitional_ 命名（test_transitional_d10_showcase_form_demos）；docstring 第一行写：「应用框架那一片（T002 规划里的第 3 片『应用框架与夹具数据层』）把陈列页移出根路由时推翻」。
- 本任务不推翻仓库里现有的 4 条过渡断言（T003 的 3 条、T004 的 1 条）。

### 人工验收项（H1–H8，不由门禁或执行端代做）
- H1 视觉（对照组件板 :354–481、断线页 :289–298、任务页 :367–391，暗色、亮色各一次）：各组件各态；就近取刻度带来的 2px 差；轻提示关闭钮圆角 md 与图标 16（画布 sm 与 14）。
- H2 真浏览器（npm run dev 带 StrictMode；再 build 后 npx vite preview 看一次）：在对话框里点进输入框、拖选文字；下拉用键盘与鼠标；开关、复选框按空格；分段、页签方向键；表格上下键、Home、End、Enter、Tab 只停一次；胶囊点开、Esc、点外面。
- H3 DevTools 的 computed 值：图标按钮与轻提示关闭钮默认态 color 应是 --tt-text-2；T002 主按钮 color 是 --tt-on-primary，危险按钮是 --tt-on-danger，小号 13px，中号、大号字重 500；分段、页签按钮字色。这几处修好前后会变，属预期。同时证实 :where() 生效。
- H4 表格吸顶与横向滚动：容器限高时表头吸顶；窄容器横向滚动，整页不出现横向滚动；键盘移到上面的行时不被表头挡住；行的焦点环看得见。
- H5 减少动态效果：骨架屏静止，胶囊浮层没有入场动画。
- H6 Windows 高对比度：分段的选中段、表格的选中行只靠底色与阴影区分，forced-colors 下可能看不出来，不行就补系统颜色的边框。
- H7 读屏抽查（可选）：开关、复选框读出名称与状态；页签；表格的行；胶囊状态变化的播报。
- H8 1024 × 640 与缩放 80%–200%：新演示不撑出整页的横向滚动。

## Steps
1. 预检（只读）：核对 Repository facts 与规划 §10 的 A1–A6 假设，不符就停。范围：不改文件。
2. 对话框遮罩（目标 7.1）：Dialog.tsx:57 改成只在 e.target === e.currentTarget 时 preventDefault；新测试 tests/dialog-scrim.test.tsx 两条（内容上 mousedown 不被阻止、遮罩本身仍被阻止）。
3. 轻提示关闭钮的工具提示（7.2）与两处 16px（7.3）：Toast.tsx 外包 Tooltip；删 Toast.css:35；IconButton.css:18 加注释；测试 tests/toast-close-tooltip.test.tsx。
4. 基础重置（7.4）：base.css 第 12–17 行包 :where()；静态测试 tests/base-reset.test.ts。
5. 图标：icons/index.tsx 新增 ChevronDownIcon（组件板 :360，m6 9 6 6 6-6）、ChevronRightIcon（:449，m9 18 6-6-6-6）、CheckIcon（:378，M20 6 9 17l-5-5）、ListChecksIcon（:466 的五条路径），只从画布拷，沿用 Svg 包装。
6. 输入框与下拉：Behavior contract 第 1、2 条；测试 tests/text-field-select.test.tsx。
7. 分段选择、开关、复选框：第 3、4、5 条；测试 tests/segmented-control.test.tsx、tests/switch-checkbox.test.tsx。
8. 页签：第 6 条；测试 tests/tabs.test.tsx。
9. 表格：第 7 条；测试 tests/table.test.tsx。
10. 其余数据原子与连接胶囊：第 8–12 条；测试 tests/data-atoms.test.tsx、tests/skeleton.test.tsx、tests/connection-pill.test.tsx。
11. 导出、陈列页与 README：第 13 条；测试 tests/showcase-forms.test.tsx、tests/component-css.test.ts。
12. 执行端测试与自检：在 desktop/web 下按锁文件 npm ci（要网络），再 npm run build、npm test、npm run check:contract；仓库根跑 V03，再点名跑 V01、V02；git status 没有新的未忽略文件。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与第 12 步自检里跑（与 T002–T004 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t005_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py -q` · cwd：仓库根 · 超时：7200s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`

说明：V01 的 tests/test_gate_t005_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在；V02 合并 T001–T004 四份门禁回归，点名运行以让前端流水线不被 conftest 跳过（每份各跑一遍 npm ci 与构建，实测 T004 三份合计约 47 秒，7200s 充裕）；V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。

## Definition of done
- D01：分段选择 role=radiogroup，段 role=radio、aria-checked；只有选中段 tabIndex=0；ArrowRight、ArrowLeft 选中下一段、上一段并移焦点，到头循环，onChange 收到新值；样式见 Behavior contract 第 3 条；证据：V01；目的：分段对键盘与读屏可用（UI 文档 7.4）。
- D02：开关 role=switch、复选框 role=checkbox，aria-checked 随状态变；名称来自可见文字；可用时可聚焦；空格切换一次（keydown 被 preventDefault，repeat 不切换），点击切换；禁用时 aria-disabled=true、不可聚焦、不切换；样式见第 4、5 条；证据：V01；目的：表单控件可访问、不重复切换。
- D03：页签 role=tablist、role=tab、aria-selected；只有当前页签 tabIndex=0；左右循环切换，Home、End 到首尾，焦点随之移动；面板 role=tabpanel、aria-labelledby 指向当前页签；高 38，当前页签 2px --tt-primary 下划线；证据：V01。
- D04：输入框与下拉高 32；标签关联；有出错时 aria-invalid=true、边框 --tt-danger-text；aria-describedby 依次含出错与帮助文字的 id；帮助文字 --tt-text-3；下拉是原生 select，同样的关联；禁用态；证据：V01。
- D05：表格表头高 32 且吸顶（sticky、--tt-z-sticky）；rowHeight 40/44/52 对应行高；数字列右对齐、等宽数字；恰一行 tabIndex=0；上下移动不循环，Home、End 到首尾，Enter 调一次 onRowOpen(key)；容器 overflow: auto、单元格不换行；证据：V01。
- D06：键值列表、空状态、面包屑的结构与取值见第 8、9、12 条；空状态没有 action 时不渲染操作区；面包屑末项 aria-current=page，不是链接也不是按钮；证据：V01。
- D07：骨架屏挂载后 299ms 没有、300ms 出现；300ms 前卸载不出现；条带用 tt-skel；Skeleton.css 不写动画、过渡、渐变；base.css 的减少动效规则含 .tt-skel；证据：V01。
- D08：连接胶囊三态的文字与 data-state；圆点与文字的色调；点击开合浮层（aria-expanded、aria-controls），浮层里有 pid 与启动于；Esc 关闭、焦点在胶囊、不往外传；点外面关闭；证据：V01。
- D09：T004 修补——遮罩只在点到自身时 preventDefault，两条测试；轻提示关闭钮悬停或聚焦 400ms 出现「关闭提示」的工具提示；IconButton.css 的 16px 有出处注释，Toast.css 没有 svg 尺寸规则；base.css 的元素重置特异性低于一个类，静态测试通过；Button.css 不变，其单类规则胜出；证据：V01、V02。
- D10：陈列页在轻提示一节之后有 11 节演示，每个 data-demo 恰一个；表格能切三档行高；骨架屏能手动触发；胶囊三态；表单对话框里的输入框上 mousedown 不被阻止、能聚焦；证据：V01（过渡断言）、review。
- D11：回归——T001–T004 门禁全绿，含 T003、T004 的 4 条过渡断言；W5 通过；npm ci、npm run build、npm test、npm run check:contract 都退出 0；证据：V02、V03、V01。
- D12：范围与测试纪律——只改允许的文件；不改依赖；既有测试不改；新增测试不用 skip、only、todo；证据：scope、review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 tokens.css、fonts.css、App.css、package.json、锁文件、vite.config.ts、门禁测试 tests/test_gate_t005_*.py）。
- 需要新增或升级依赖、写 .npmrc、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计。
- 时间分配：调查约 15 分钟、实现与补测约 65 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。
