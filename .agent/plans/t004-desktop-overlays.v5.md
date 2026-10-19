# TASK: t004-desktop-overlays

## Identity
- plan_version: 5
- repository: ThemisTally
- base_sha: 9f784056c5af4217835df20078abcacaae38178a
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T004 第 3 片（桌面端前端浮层与焦点）。

在 `desktop/web/` 新增 6 个浮层组件（图标按钮、工具提示、菜单、对话框、抽屉、轻提示）与内部 overlay 模块，补两处状态补丁（`ACCEPTED_WITH_EXCEPTION` 的 warning 圆点、`INFRA_FAILURE` 图标改名 `ServerCrashIcon`），在陈列页页尾追加 5 节演示，并新增仓库根 pytest `tests/test_desktop_attempt_states.py`（W5）守住桌面端状态表与调度器 `ATTEMPT_STATES` 逐项相同；不改依赖、不改令牌、不改 `base.css`、不改 `package.json` 与锁文件。

## Non-goals
- T005 的表单与数据原子：分段选择、开关、复选框、页签、输入框与下拉、表格、键值列表、空状态、骨架屏、连接胶囊、面包屑。
- 对话框小 400、大 760 两档（只做 handoff 的 560）；写操作确认框的各状态（UI 文档 7.11，如执行中不能关闭，属 D2）。
- 抽屉拖动改宽与左缘拖拽区；菜单的单选项、分组标题与分隔线；多条轻提示堆叠。
- 背景 `inert` 与滚动锁定。
- 工具链升级；写操作、接本机服务、七端视图；Electron 外壳；字体、令牌、许可。

## Repository facts
- 入口：`desktop/web/src/main.tsx` 挂载 `desktop/web/src/App.tsx`（组件陈列页，根元素带 `tt-app`、`tt-content`、`showcase` 三个类）；主题按钮在页头；`desktop/web/src/components/index.ts` 统一导出 5 个原子组件。
- 调用关系与现有约定：
  - `desktop/web/src/domain/attemptStates.ts`：`ATTEMPT_STATES` 17 个键（:48–66），顺序与 PD 的 `ATTEMPT_STATES` 相同；`ACCEPTED_WITH_EXCEPTION` 用 `BadgeCheckIcon`（:56），`INFRA_FAILURE` 用 `ServerIcon`（:60）；`AttemptStateInfo` 有 label、tone、icon、spin（:39–46）；`resolveAttemptState` 用 `Object.hasOwn`，兜底 `FALLBACK_STATE`。
  - `desktop/web/src/icons/index.tsx`：`ServerIcon` 的 5 条路径（:119–127）与令牌板 :342 `s.ic.server` 那一块逐字相同（含 `m13 6-4 6h6l-4 6`，即 UI 文档 3.4 :161 的 `server-crash`）；所有图标 `fill=none`、`stroke=currentColor`、`aria-hidden`（:7–26）。
  - `desktop/web/src/components/StatusTag.tsx`：先渲染图标再渲染文字，`title` 为状态码，带 `data-tone`、`data-size`；`StatusTag.css` 中号高 22、小号高 20。
  - `desktop/web/src/components/Button.tsx` 没有 forwardRef（菜单复用按钮时用 id 找回节点或复用 `tt-btn` 类，不改 Button）。
  - `tokens.css`：`--tt-z-popover/drawer/dialog/toast/tooltip` 为 100–500（:48）；`--tt-tabbar-height: 56px`（:50）；`--tt-scrim`、`--tt-shadow-2/3`、`--tt-radius-sm/md/lg/xl/full`、`--tt-gray-900`、`--tt-gray-50`、`--tt-tone-warning-fg`、`--tt-tone-success-bg`、`--tt-space-*` 都在；没有对话框、抽屉、控件的尺寸令牌。
  - `base.css`：基础规则挂在 `.tt-app` 下（:4–23，含 `:focus-visible` 焦点环）；`.tt-enter`、`.tt-drawer-in` 与减少动效（:43–49）；`.tt-content` 的 `container-type`（:52）；`forced-colors` 下的 `.tt-fc`（:66–69）。
  - `main.tsx:3–6` 先 `import App` 再引入三份样式：产物里组件 CSS 排在 `base.css` 之前，同特异性时 `.tt-app` 的规则胜出；给浮层根元素直接加 `tt-app` 会被盖成 `--tt-bg`，所以用外包一层的挂载层。
  - `App.tsx`：页头 :44–51，样张 :53–82，Button :84，之后 Tag、StatusTag、Card，提示条 :156–172 在最后。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript strict + Vite 5.4.11 + Vitest 2.1.8；`@testing-library/react` 16.1.0、`@testing-library/dom` 10.4.0、jsdom 25.0.1，没有 `user-event`；`vite.config.ts` 的 `test.include` 含 `src`、`tests`、`gate-probe`；`tsconfig.json` 只含 `src` 与 `vite.config.ts`（测试文件不进 `tsc`）；锁文件 `desktop/web/package-lock.json`（lockfileVersion 3），`npm ci` 可复现。
- 基线检查：事实基线 `13a69af025ec8cc06d4903bd690581f4e434a5c1`（`git status` 干净）；此后这些路径无改动：`desktop/web/`、`tests/`、`scripts/`、`docs/`（`.agent/plans/` 仅新增本任务的合同草稿，属 .agent，不影响仓库事实；详见交付信「偏离」）。T004 门禁 `tests/test_gate_t004_baseline.py` 是 V01 的目标文件，由门禁端在战前门禁阶段产出，基线上不存在。按 T003 终审记录，T002 门禁基线 71 passed、T003 门禁基线 40 passed，本片作为回归必须仍通过。

## Scope
- allowed_modified_files:
  - desktop/web/src/components/index.ts
  - desktop/web/src/components/StatusTag.tsx
  - desktop/web/src/components/StatusTag.css
  - desktop/web/src/domain/attemptStates.ts
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/README.md
  - desktop/web/src/components/Dialog.css
  - desktop/web/src/components/Dialog.tsx
  - desktop/web/src/components/Drawer.css
  - desktop/web/src/components/Drawer.tsx
  - desktop/web/src/components/IconButton.css
  - desktop/web/src/components/IconButton.tsx
  - desktop/web/src/components/Menu.css
  - desktop/web/src/components/Menu.tsx
  - desktop/web/src/components/Toast.css
  - desktop/web/src/components/Toast.tsx
  - desktop/web/src/components/Tooltip.css
  - desktop/web/src/components/Tooltip.tsx
  - desktop/web/src/components/overlay/MountLayer.tsx
  - desktop/web/src/components/overlay/focusable.ts
  - desktop/web/src/components/overlay/useOverlayFocus.ts
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/toast.test.tsx
  - tests/test_desktop_attempt_states.py
- allowed_new_files:
  - desktop/web/src/components/IconButton.tsx
  - desktop/web/src/components/IconButton.css
  - desktop/web/src/components/Tooltip.tsx
  - desktop/web/src/components/Tooltip.css
  - desktop/web/src/components/Menu.tsx
  - desktop/web/src/components/Menu.css
  - desktop/web/src/components/Dialog.tsx
  - desktop/web/src/components/Dialog.css
  - desktop/web/src/components/Drawer.tsx
  - desktop/web/src/components/Drawer.css
  - desktop/web/src/components/Toast.tsx
  - desktop/web/src/components/Toast.css
  - desktop/web/src/components/overlay/*.ts
  - desktop/web/src/components/overlay/*.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/toast.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - tests/test_desktop_attempt_states.py
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/fonts/**
  - desktop/web/src/styles/**
  - desktop/web/src/main.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/public/**
  - desktop/web/THIRD_PARTY_NOTICES.md
  - desktop/web/src/components/Button.*
  - desktop/web/src/components/Tag.*
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Banner.*
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - desktop/web/tests/font-specimen.test.tsx
  - tests/test_attempt_states.py
  - tests/conftest.py
  - tests/test_gate_*.py
  - tests/test_gate_t004_*.py
  - .gitignore
  - .gitattributes
  - scripts/**
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定
- 组件名、属性名、类名、`data-demo` 取值与按钮文字在本合同定下后，门禁按它写探针、解析 CSS，执行端不得再改。
- 键盘一律看 `event.key`：`Tab`、`Escape`、`ArrowDown`、`ArrowUp`、`Home`、`End`、`Enter`。
- 颜色、圆角、阴影、层级、字体只用 `--tt-*` 令牌；间距有对应 `--tt-space-*` 时必须用令牌（padding、gap、margin、inset 都算），画布上不在刻度上的间距（如 10、14）就近取刻度令牌。
- 尺寸字面量只允许下列清单里的值，每个字面量 px 在组件 CSS 里带一行出处注释（UI 文档节号或画布板名）：对话框宽 560（handoff :144；写操作页 :357）、抽屉宽 520（handoff :150；插件页 :133）、图标按钮边长 28/32（UI 文档 7.2 :778；写操作页 :360）、对话框与抽屉关闭钮 28、轻提示关闭钮 24（写操作页 :422）、菜单宽 240 与菜单项高 32（组件板 :455–457）、状态圆点直径 6 与描边 1.5 与外偏 2（令牌板 :342）。标题栏高 40 本片不用（抽屉顶边取 0）。`tokens.css` 不动、不加令牌，令牌板与 `tokens.css` 逐项相等（W4）不能破。
- 挂到 body 的浮层（工具提示、对话框、抽屉、轻提示）都放进第 1 条的挂载层。
- 各浮层的外框加 `tt-fc` 类（`base.css` :66–69 在 Windows 高对比度下给边框）。
- Esc 由焦点所在的最上层处理，处理了就 `stopPropagation`：React 合成事件沿组件树冒泡、会穿过 portal，不拦的话在对话框里关菜单会连对话框一起关。
- `open` 为 false 时对话框、抽屉不渲染；只有入场动效（`.tt-enter` / `.tt-drawer-in`），没有退场动效（与画布一致）。

### 1. 浮层内部模块（`src/components/overlay/`，不从 index 导出）
- 挂载层：`createPortal` 到 `document.body`，外包一层带 `tt-app` 类、不占位的 div。浮层才吃得到 `base.css` 的基础规则与焦点环；因为 `main.tsx` 先 `import App` 再引三份样式，产物里组件 CSS 排在 `base.css` 之前，同特异性时 `.tt-app` 规则胜出，所以不能给浮层根直接加 `tt-app`（底色会被盖成 `--tt-bg`）。
- 可聚焦元素：按选择器与 `disabled`、`hidden` 等属性筛，不按布局（`offsetParent`、`getClientRects`）筛——jsdom 里布局全为 0 会全筛掉。
- 焦点返回：打开时记下 `document.activeElement`，关闭时还回去（元素还在文档里才还）；记与还都幂等（StrictMode 下 effect 跑两遍）。
- 在 effect 里同步聚焦，不用 rAF 或 setTimeout 延后聚焦（会和 fake timers 搅在一起）。

### 2. IconButton（`IconButton.tsx` / `.css`）
- API：`label: string`（必填，`aria-label` 与缺省提示文字）；`icon: ReactNode`；`size?: 'sm' | 'md'`（边长 28 / 32，缺省 32）；`tooltip?: ReactNode`（提示文字与名称不同时用）；其余透传给 `<button type=button>`。
- `label` 必填由类型保证：漏写 `label`，`npm run build` 里的 `tsc --noEmit` 过不了。
- 永远包一层 Tooltip（UI 文档 7.2：只用图标的按钮必须有工具提示与 `aria-label`）。
- 样式（组件板 :340–344）：透明底、`--tt-text-2`；悬停 `--tt-surface-3` 与 `--tt-text-1`；禁用 `--tt-text-disabled`；`--tt-radius-md`；图标 16、`aria-hidden`；焦点环用 `base.css` 的 `:focus-visible`。边长 28 / 32 为字面量，各带出处注释。

### 3. Tooltip（`Tooltip.tsx` / `.css`）
- API：`content: ReactNode`；`children: ReactElement`（单个可聚焦元素）。
- 时序：悬停（mouseenter）或聚焦（focus）开始计时，400ms 后出现；移开、失焦立即消失并取消计时；可见或计时中按 Esc 消失或取消，在下一次重新悬停、聚焦之前不再出现。400 写成具名常量。
- 可见时：提示元素 `role=tooltip`、有 `id`；触发元素加 `aria-describedby` 指向它，消失时去掉。
- Esc 监听：聚焦时在触发元素上监听、可见时消费掉；只悬停没聚焦时另在 document 上监听。
- 实现：用一个 `display: inline-flex` 的包裹元素接鼠标与焦点事件、量位置；`aria-describedby` 用 `cloneElement` 加到子元素，不要求子元素转发 ref；挂到 body、固定定位，出现时按包裹元素 `getBoundingClientRect()` 放正上方居中（`style` 只写算出的 top、left；UI 文档 0.2 第 3 条允许）。jsdom 里位置都是 0，门禁不查位置。
- 样式（handoff :147、组件板 :346）：底 `--tt-gray-900`、字 `--tt-gray-50`、内边距 `var(--tt-space-1) var(--tt-space-2)`、`--tt-radius-sm`、`--tt-text-caption`、不换行、`z-index: var(--tt-z-tooltip)`。

### 4. Menu（`Menu.tsx` / `.css`）
- API：`label: ReactNode`（触发按钮文字）；`items: { id: string; label: ReactNode }[]`；`onSelect(id: string)`。
- 触发按钮：复用 `Button` 的样式；带 `aria-haspopup=menu`、`aria-expanded`，打开时 `aria-controls` 指向菜单。点它开、再点关。`Button` 没有 forwardRef：用 `id` 找回节点，或另写按钮复用 `tt-btn` 的类，不改 Button。
- 键盘：打开后焦点到第一项；`ArrowDown`、`ArrowUp` 移动，到头循环；`Home`、`End` 到首尾；`Enter` 调一次 `onSelect(id)`、关闭、焦点回触发按钮；`Escape` 关闭、焦点回触发按钮、不调 `onSelect`、`stopPropagation`；`Tab` 关闭、焦点照常移走（可选）。
- 在菜单与触发按钮之外按下鼠标（mousedown）：关闭，不强行还焦点。
- 结构：面板 `role=menu`、`aria-labelledby` 指向触发按钮；项 `role=menuitem`、`tabIndex=-1`，用 div，用真实焦点移动（不用 `aria-activedescendant`）。
- 样式（组件板 :455–460）：面板在触发按钮下方、原地绝对定位、`z-index: var(--tt-z-popover)`；`--tt-surface-1` 底、1px `--tt-border`、`--tt-radius-lg`、`--tt-shadow-2`、内边距 `--tt-space-1`、宽 240（字面量）；项高 32（字面量）、左右 `--tt-space-2`、`--tt-radius-md`、`--tt-text-sm`，悬停与聚焦 `--tt-surface-3`。

### 5. Dialog（W6，`Dialog.tsx` / `.css`）
- API：`open`、`onClose()`、`title: ReactNode`、`children`、`footer?: ReactNode`。
- 结构（写操作页 :356–413）：遮罩 `tt-dialog-scrim`，里面是 `tt-dialog`：`role=dialog`、`aria-modal=true`、`aria-labelledby` 指向标题 `h2`，带 `tt-enter`；头：标题（`--tt-title-md`）与关闭钮（IconButton 28，名称照画布「关闭（Esc）」）；体：内容多时自身滚动；底栏（可选）：上边框 1px `--tt-border`，按钮右对齐。
- 焦点：打开时先记下 `document.activeElement`，再把焦点放到对话框里第一个可聚焦元素；没有就放到对话框本身（`tabIndex=-1`）。对话框根上的 keydown：末元素 `Tab` → `preventDefault` 并聚焦首元素；首元素 `Shift+Tab` → `preventDefault` 并聚焦末元素；焦点在对话框本身时 `Tab` 去首元素、`Shift+Tab` 去末元素。关闭（`open` 变 false 或卸载）时把焦点还给记下的元素。遮罩上 `mousedown` 阻止默认（点遮罩不把焦点移走）。建议做（门禁不强制）：document 上的 `focusin` 发现焦点跑到对话框外，拉回首元素。
- 关闭途径：Esc（对话框根 keydown，调 `onClose()` 并 `stopPropagation`）、关闭钮、底栏按钮。点遮罩不关闭。
- 遮罩盖满窗口：挂到 body；`position: fixed; inset: 0; z-index: var(--tt-z-dialog); background: var(--tt-scrim)`；网格居中，内边距 `--tt-space-6`。
- 尺寸与样式（handoff :144）：宽 560（字面量）、`max-width: 100%`、`max-height: calc(100vh - var(--tt-space-12))`；`--tt-surface-1`、`--tt-radius-xl`、`--tt-shadow-3`；头 `padding: var(--tt-space-4) var(--tt-space-4) var(--tt-space-2) var(--tt-space-5)`，体 `var(--tt-space-1) var(--tt-space-5) var(--tt-space-5)`，底栏 `var(--tt-space-3) var(--tt-space-5)`、按钮间距 `--tt-space-2`。

### 6. Drawer（`Drawer.tsx` / `.css`）
- API：同 Dialog。
- 结构（插件页 :133–174）：`tt-drawer`，`role=dialog`、`aria-modal=false`、`aria-labelledby`，带 `tt-drawer-in`；头（标题与关闭钮 28，下边框）、可滚动的体、可选底栏。没有遮罩。
- 焦点：打开时进入（第一个可聚焦元素），关闭后回触发元素；不困焦点，Tab 不拦；焦点在抽屉里按 Esc：关闭并 `stopPropagation`。点抽屉外不关闭（非模态）。
- CSS：`position: fixed; top: 0; right: 0; bottom: var(--tt-tabbar-height); width: 520px; max-width: 60%; z-index: var(--tt-z-drawer)`（520 为字面量）；`--tt-surface-1`、左边框 1px `--tt-border`、只有左侧两角 `--tt-radius-xl`、`--tt-shadow-3`。
- 顶边取 0（本片没有标题栏）；门禁不断言顶边。

### 7. Toast（`Toast.tsx` / `.css`）
- API：`open`、`onClose()`、`children`（文字）、`tone?: 'success' | 'info'`（只管图标颜色，缺省 success，图标 `circle-check`）。
- 结构（写操作页 :419–423、组件板 :431）：常驻一个 `role=status`、`aria-live=polite` 的区域，没有轻提示时也渲染（空的）；可见时里面是图标、文字与关闭钮（名称「关闭提示」，24，字面量）。
- 计时：`open` 变 true 时开始 5000ms，到点调一次 `onClose()`；鼠标移入暂停、记下剩余时间，移出后按剩余时间接着走；关闭钮立即调 `onClose()`；卸载与重新打开都清计时器；5000 写成具名常量。
- 读法：「悬停时暂停计时」按「暂停、移开后接着走剩余时间」做，不是移开后重新计 5 秒。
- CSS：`position: fixed; right: var(--tt-space-6); bottom: calc(var(--tt-tabbar-height) + var(--tt-space-4)); z-index: var(--tt-z-toast)`；`--tt-surface-1`、1px `--tt-border`、`--tt-radius-lg`、`--tt-shadow-2`、`--tt-text-sm`；`tt-enter` 入场。

### 8. 两处状态补丁（`attemptStates.ts`、`StatusTag.tsx`、`StatusTag.css`、`icons/index.tsx`）
- 小圆点：`AttemptStateInfo` 加一个可选的角标字段（例如 `dot?: 'warning'`），只给 `ACCEPTED_WITH_EXCEPTION`；`resolveAttemptState` 原样带出；兜底状态没有。`StatusTag` 有角标时，把图标包进相对定位的 `tt-status__icon`，图标之后放 `tt-status__dot`：`aria-hidden=true`、不带文字；第一个 svg 仍是 badge-check。CSS（令牌板 :342）：直径 6、右上外偏 2、描边 1.5（字面量）；`background: var(--tt-tone-warning-fg)`；`box-shadow: 0 0 0 1.5px var(--tt-tone-success-bg)`；`border-radius: var(--tt-radius-full)`。中号、小号都显示。圆点不进 `src/icons/`。
- server-crash：`src/icons/index.tsx` 的 `ServerIcon` 改名 `ServerCrashIcon`，5 条路径一字不改；`attemptStates.ts` 的导入与 `INFRA_FAILURE` 条目跟着改；不留 `ServerIcon` 别名。合同里这个图标写 `server-crash`（UI 文档 3.4 :161）。T002 门禁按子串找图标名（`server` 的写法含 `Server`），`ServerCrashIcon` 照样过。

### 9. 导出、陈列页与 README
- `components/index.ts`：导出 6 个新组件与它们的 Props 类型；文件头注释改成两片的总述。
- `App.tsx`：在提示条一节之后（页尾）追加 5 节，顺序：图标按钮 · 工具提示、菜单、对话框、抽屉、轻提示。每节根带 `data-demo`：`icon-button`、`menu`、`dialog`、`drawer`、`toast`。触发按钮文字写死：「更多操作」「打开对话框」「打开抽屉」「弹出轻提示」。菜单演示旁显示「上次选择：…」；对话框演示有底栏 [取消] [确定]；抽屉演示有几行说明与底栏按钮。图标按钮演示用已有图标（x、info、circle-help）：28、32 各一个，另一个禁用。
- 不新增图标；确要新增时从画布拷路径（组件板 :340 的 copy、:360 的 chevron-down），不凭记忆写。
- `App.css`：只加新节的布局；不写 `letter-spacing`；不用 `[data-font-weight]` 选择器。
- 演示文字与行注释避开 `#`，避开「函数名 + 括号」的写法（`rgb(`、`color(` 等）：W4 只剥块注释，行注释、字符串、文字都扫。
- `README.md`：目录约定加新组件与 `overlay/`；写明 W5 在仓库根 `tests/test_desktop_attempt_states.py`，改了 `attemptStates.ts` 或 PD 的 `ATTEMPT_STATES` 之后跑 `python -m pytest tests/test_desktop_attempt_states.py -q`；命令一节不动。

### 10. W5 测试文件（`tests/test_desktop_attempt_states.py`）
- 只用标准库与 pytest：照 `tests/test_attempt_states.py:7–9` 把 `scripts/` 加进 `sys.path`，`import pi_dispatch`，取 `ATTEMPT_STATES`。
- 读 `desktop/web/src/domain/attemptStates.ts`：路径由 `Path(__file__).resolve().parents[1]` 推出，不依赖 cwd；找到 `export const ATTEMPT_STATES` 的对象字面量，跳过字符串与注释，按源码顺序取第一层的键。
- 第一层出现展开（`...`）或计算键（`[…]`）、找不到声明、一个键也没有、键重复：直接失败并说明原因。
- 断言键的列表等于 `list(pd.ATTEMPT_STATES)`（同样的状态、同样的顺序）；失败信息分列「桌面端缺」「桌面端多」「顺序不同」。
- 解析器自检：用合成的 TS 片段证明多一个键、少一个键看得出来，注释里的假键不算，展开写法与缺声明会报错。
- 不写死 17；不导入 `tests/` 里别的模块（门禁要把它拷进临时目录单独跑）。

### 11. 执行端 Vitest 测试写法
- 导入：从 `@testing-library/react` 导入 `render`、`act`、`fireEvent`、`cleanup`（与 T002 门禁探针相同）；从 `vitest` 导入 `vi` 等。不加 `user-event`。
- 悬停与聚焦的用例必须从 `@testing-library/react` 导入 `fireEvent`：它给 React 打了补丁，mouseEnter/mouseLeave 另发 mouseover/mouseout，focus/blur 另发 focusin/focusout；直接从 `@testing-library/dom` 导入的 `fireEvent` 没有这层补丁，测不到 React 的 onMouseEnter/onFocus。
- 计时：`beforeEach` 里 `vi.useFakeTimers()`，`afterEach` 里 `cleanup()` 与 `vi.useRealTimers()`；推进时间包在 `act(() => { vi.advanceTimersByTime(n); })` 里；不用 `waitFor`、`findBy*`。
- 焦点：真实焦点用 `act(() => el.focus())`，看 `document.activeElement`；「焦点回到触发按钮」的用例先 `trigger.focus()` 再 `fireEvent.click(trigger)`；工具提示的「聚焦后出现」用 `fireEvent.focus`、`fireEvent.blur`。
- 键盘：`fireEvent.keyDown(document.activeElement, { key: 'Tab' })`；Shift+Tab 加 `shiftKey: true`；Esc、方向键、Enter 同理。jsdom 不按 Tab 移动焦点，焦点陷阱只测两个边界；可顺带断言边界处的 keydown 被 `preventDefault`（`fireEvent` 返回 false）。
- 悬停：`fireEvent.mouseEnter`、`fireEvent.mouseLeave`。
- 样式与几何：jsdom 不排版，宽、位置、层级读 CSS 文件的文本来断言（照 `tests/token-contract.test.ts` 用 `process.cwd()` 定位），不读 `getComputedStyle`。
- 不写快照测试；不往仓库里写文件。
- 建议的文件（allowed_new_files 照此清单）：`tests/icon-button.test.tsx`（含工具提示）、`tests/menu.test.tsx`、`tests/dialog.test.tsx`、`tests/drawer.test.tsx`、`tests/toast.test.tsx`、`tests/status-tag-patches.test.tsx`、`tests/showcase-overlays.test.tsx`（渲染 App）。

### 12. 门禁要点（门禁端定稿，S1–S7、P1–P8）
静态 S 系列不用流水线；流水线 P 系列用会话级 `pipeline` 夹具：`npm ci` → `npm run build` → `npm test` → `npm run check:contract` → 各探针，前后各取一次 `git status`。
- S1 `test_d01_components_exported`：6 个组件文件都在；`components/index.ts` 导出 6 个新名字与原来 5 个。D01–D05。
- S2 `test_d07_infra_failure_icon_is_server_crash`：`icons/index.tsx` 有 `ServerCrashIcon`、没有 `ServerIcon`；它的 `d` 列表等于令牌板 :342 `s.ic.server` 那一块；`attemptStates.ts` 的 `INFRA_FAILURE` 用它。D07。
- S3 `test_d03_dialog_css_and_scrim`：`tt-dialog` 宽 560、`max-width: 100%`、`--tt-radius-xl`、`--tt-shadow-3`；`tt-dialog-scrim` 固定定位、四边为 0、`z-index: var(--tt-z-dialog)`、`background: var(--tt-scrim)`，底部不让位。D03。
- S4 `test_d04_drawer_css_geometry`：`tt-drawer` 宽 520、`max-width: 60%`、固定定位、`right: 0`、`bottom: var(--tt-tabbar-height)`、`z-index: var(--tt-z-drawer)`；不断言顶边。D04。
- S5 `test_d05_toast_css_position`：固定定位、`right: var(--tt-space-6)`、`bottom: calc(var(--tt-tabbar-height) + var(--tt-space-4))`、`z-index: var(--tt-z-toast)`。D05。
- S6 `test_d07_layer_and_dot_css_tokens`：圆点 `background: var(--tt-tone-warning-fg)`、描边（`box-shadow` 或 `border`）用 `var(--tt-tone-success-bg)`、圆角 `var(--tt-radius-full)` 或 50%；工具提示 `--tt-gray-900`、`--tt-gray-50`、`z-index: var(--tt-z-tooltip)`；菜单 `z-index: var(--tt-z-popover)`。D01、D02、D07。
- S7 `test_d06_w5_passes_and_catches_changes`：子进程跑 `python -m pytest tests/test_desktop_attempt_states.py -q` 通过；在 `tmp_path` 搭最小副本，原样通过，四种改法（两边各删一个、各加一个状态）各跑一次都失败。D06。
- P1 `test_d09_pipeline_steps_pass`：四步退出 0；`npm test` 没有失败、跳过、待办。D09（守卫）。
- P2 `test_d01_probe_icon_button_tooltip`：`aria-label` 等于 `label`；svg `aria-hidden`；按钮里没有文字；悬停 399ms 没有 `role=tooltip`、400ms 有且文字对、`aria-describedby` 指向它；移开立即消失；聚焦同样 400ms，失焦消失；可见时 Esc 消失，之后再推 1000ms 仍不出现；计时中 Esc 取消。D01。
- P3 `test_d02_probe_menu_keyboard`：点按钮 `aria-expanded=true`、`role=menu` 出现、焦点在第一项；ArrowDown 到第二项；末项 ArrowDown 回第一项；首项 ArrowUp 到末项；Enter：`onSelect` 收到该项 id 一次、菜单消失、焦点回按钮、`aria-expanded=false`；再开、Esc：消失、焦点回按钮、`onSelect` 没被调。D02。
- P4 `test_d03_probe_dialog_w6`：先聚焦再点触发按钮；`role=dialog`、`aria-modal=true`、`aria-labelledby` 指向标题；焦点在框内；末元素 Tab 到首元素；首元素 Shift+Tab 到末元素；Esc 对话框消失、焦点回触发按钮；关闭钮同；遮罩不在渲染容器里、在 body 下。D03。
- P5 `test_d04_probe_drawer_nonmodal`：`role=dialog`、`aria-modal=false`；没有遮罩；焦点进入；末元素 Tab 不被拦（keydown 没有被 preventDefault）；焦点在抽屉里 Esc：消失、焦点回触发按钮。D04。
- P6 `test_d05_probe_toast_timing`：`role=status`；4999ms 时 `onClose` 没调、5000ms 调一次；第 3000ms 移入再推 10000ms 不调；移出后 1999ms 不调、2000ms 调；关闭钮立即调。D05。
- P7 `test_d07_probe_status_patches`：`ACCEPTED_WITH_EXCEPTION` 恰一个 `tt-status__dot`、`aria-hidden=true`、在第一个 svg 之后、标签文字仍是「带豁免通过」；其余 16 个与未知状态码没有圆点；`INFRA_FAILURE` 的 svg `d` 列表等于令牌板。D07。
- P8 `test_transitional_d08_showcase_overlay_demos`：渲染 App：5 个 `data-demo` 节都在、都在样张之后；点各自触发按钮，对话框、抽屉、菜单、轻提示分别出现；页面上没有文字的按钮都有非空 `aria-label`。D08。
- 探针沿用 T002、T003：写进 `desktop/web/gate-probe/probe-<唯一标识>.test.tsx`，用 `npm test -- gate-probe/<文件名>` 跑，`finally` 里删；组件探针（P2–P7）与陈列页探针（P8）分开写、分开跑；对话框、抽屉探针也开 fake timers。

### 边界与错误
- 构建：`npm run build` 里的 `tsc --noEmit` 必须过（`label` 必填靠它兜）。
- 契约检查 `check:contract` 扫 TSX 全文（只剥块注释）：演示文字与行注释不能出现 `#` 加 3/4/6/8 位十六进制字符，也不能出现 `rgb(`、`lab(`、`color(` 这类「函数名 + 括号」；`App.css` 不能出现 `letter-spacing`，不能用 `[data-font-weight]` 选择器。
- 浮层挂在 body 下的挂载层（脱离 App 根与 `.tt-content` 的 `container-type`），遮罩才盖满窗口、固定定位参照才对。
- 组件卸载与重新打开都清计时器。

### 并发、取消与状态变化
- 不适用异步业务状态：浮层是同步的开关与计时；轻提示与工具提示的计时器在卸载时清；StrictMode 下 effect 跑两遍，记焦点与还焦点幂等。

### 兼容性
- 只改允许的文件；`tokens.css`、`base.css`、`fonts/`、`package.json`、锁文件、`index.html`、`vite.config.ts`、`tsconfig.json`、`scripts/**`、T002 的四个组件、既有测试都不动；不新增依赖（`dependency_changes: forbidden`）。
- T002 门禁的其余断言与 T003 门禁（含三条过渡断言）是回归，不能变红。

### 禁止的做法
- `npm install` 或升级依赖；
- 在 `tokens.css` 加令牌；
- 改 `base.css`；
- 把圆点画进 `src/icons/`；
- 用原生 `<dialog>` 的 `showModal()` 代替手写的焦点陷阱（任务书要测焦点陷阱的两个边界，手写的才测得到）。

### 过渡断言
- 门禁里只有 P8 `test_transitional_d08_showcase_overlay_demos`；docstring 第一行写：「应用框架那一片（T002 规划里的第 3 片『应用框架与夹具数据层』）把陈列页移出根路由时推翻」。
- 本任务不推翻仓库里现有的三条 T003 过渡断言（S8、S9、P8）。
- 执行端的 `tests/showcase-overlays.test.tsx` 不是门禁测试，不受这条规则管；应用框架那一片移陈列页时改它的 import，不必删。

### 人工验收项（H1–H6，不由门禁或执行端代做）
- H1 视觉（对照组件板 :338–350、:455–460，写操作页 :356–423，插件页 :133–174，令牌板 :342；暗色、亮色各一次）：图标按钮 28/32 各态；工具提示位置与配色；菜单面板与项；对话框标题/关闭钮/底栏/遮罩/入场；抽屉靠右/两角/阴影/底边；轻提示右下；圆点位置与描边；间距就近取刻度后与画布差 2px 以内。
- H2 真浏览器键盘（`npm run dev` 带 StrictMode；再 `npx vite preview` 看一次）：对话框 Tab/Shift+Tab 循环不出框、点遮罩后 Tab 仍在框内、Esc 后焦点环回触发按钮；抽屉 Tab 能离开、关闭后焦点回触发按钮；菜单方向键/Enter/Esc、点外面关闭。
- H3 读屏抽查（可选）：图标按钮名称、提示作描述；菜单/对话框/轻提示的读法。
- H4 减少动态效果：系统开启后对话框、抽屉、轻提示没有入场动画（`base.css` :47–49 已处理）。
- H5 1024 × 640 与缩放 80%–200%：对话框 560、抽屉 520（最多 60%）不溢出；对话框内容多时自身滚动，高不超过窗口高减 48。
- H6 Windows 高对比度：各浮层外框可见（`tt-fc`）。

## Steps
1. 预检（只读）：确认基线事实（报告 §10 的 A1–A6、A16），不符就停。范围：不改文件。
2. 两处状态补丁：`attemptStates.ts`、`StatusTag.tsx`、`StatusTag.css`、`icons/index.tsx`；细则见 Behavior contract 第 8 条。
3. 浮层的内部模块：`src/components/overlay/`，见第 1 条。
4. 图标按钮与工具提示：`IconButton.tsx/.css`、`Tooltip.tsx/.css`，见第 2、3 条。
5. 菜单：`Menu.tsx/.css`，见第 4 条。
6. 对话框（W6）：`Dialog.tsx/.css`，见第 5 条。
7. 抽屉：`Drawer.tsx/.css`，见第 6 条。
8. 轻提示：`Toast.tsx/.css`，见第 7 条。
9. 导出、陈列页与 README：`components/index.ts`、`App.tsx`、`App.css`、`README.md`，见第 9 条。
10. W5：`tests/test_desktop_attempt_states.py`，见第 10 条。
11. 执行端 Vitest 测试：写法见第 11 条；不用 skip、only、todo。
12. 自检：在 `desktop/web` 下按锁文件 `npm ci`（要网络），再 `npm run build`、`npm test`、`npm run check:contract`；仓库根跑 V03，最后点名跑 V01、V02；`git status` 没有新的未忽略文件。

## Setup
无。本合同的 prepare setup 为空；`npm ci` 只在门禁 pytest 与第 12 步自检里跑（与 T002、T003 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t004_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V03（必要，基线应失败）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V02（必要，回归，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py -q` · cwd：仓库根 · 超时：7200s · 期望退出码：0 · 输出须匹配 `\d+ passed`，不得出现 `failed|error`

说明：V01 的 `tests/test_gate_t004_baseline.py` 由门禁端稍后写好、内核做成基线提交；V02 合并 T001、T002、T003 三份门禁回归，点名运行以让前端流水线不被 conftest 跳过，按三份终审记录基线上应分别 59、71、40 passed（合计 170，仅作参考、不作硬性数字）；V03 基线上第一个文件不存在，pytest 报错退出。V02 一次跑三份门禁，每份各跑一遍 `npm ci` 与构建，故超时取 7200s（三份各 2400s）。

## Definition of done
- D01：IconButton 的 `label` 必填，渲染成 `aria-label`，图标 `aria-hidden`；工具提示悬停或聚焦 400ms 后出现（399ms 时没有），`role=tooltip`，触发元素的 `aria-describedby` 指向它；移开、失焦、Esc 都让它消失；证据：V01；目的：只用图标的按钮对读屏与键盘都可用（UI 文档 7.2、7.23）。
- D02：菜单由按钮触发，`aria-haspopup`、`aria-expanded` 正确；打开后焦点在第一项；上下键移动并循环；Enter 选中、关闭、焦点回按钮；Esc 关闭、焦点回按钮、不选中；证据：V01。
- D03：对话框 `role=dialog`、`aria-modal=true`、有可读的标题；打开后焦点在框内；末元素 Tab 回首元素，首元素 Shift+Tab 到末元素；Esc 或关闭钮关闭后焦点回到触发按钮；遮罩挂在 body 下、固定定位铺满窗口、层级 `--tt-z-dialog`；宽 560；证据：V01；目的：W6。
- D04：抽屉 `aria-modal=false`、没有遮罩、不困焦点；宽 520、`max-width: 60%`、`bottom: var(--tt-tabbar-height)`、层级 `--tt-z-drawer`；打开时焦点进入、关闭后回到触发元素；证据：V01。
- D05：轻提示 `role=status`；5000ms 后关闭（4999ms 时还在）；悬停期间不计时，移开后接着走剩余时间；关闭钮立即关闭；右下、距底 `calc(var(--tt-tabbar-height) + var(--tt-space-4))`、层级 `--tt-z-toast`；证据：V01。
- D06：`tests/test_desktop_attempt_states.py` 通过；两边任一边增删一个状态它就失败；证据：V03、V01（S7）、战后变异；目的：W5。
- D07：只有 `ACCEPTED_WITH_EXCEPTION` 带 warning 小圆点（`aria-hidden`，填色与描边取令牌）；`INFRA_FAILURE` 的图标是 `ServerCrashIcon`，路径与令牌板相同，`ServerIcon` 不再存在；证据：V01。
- D08：陈列页页尾有 5 节演示，能手动打开对话框、抽屉、菜单，弹出轻提示；页面上只用图标的按钮都有名称；证据：V01（过渡断言）、review。
- D09：T001、T002、T003 门禁全部通过（含 T003 的三条过渡断言）；`npm run check:contract` 退出 0；证据：V02、V01（P1）。
- D10：只改允许的文件；`package.json`、锁文件、`tokens.css`、`base.css` 不变；不新增依赖；证据：scope。
- D11：既有测试不改；新增测试不用 skip、only、todo；证据：review（机械部分由 V02 的 `test_d03_new_tests_not_skipped` 查）。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 `tokens.css`、`base.css`、`package.json`、锁文件、`vite.config.ts`、门禁测试 `tests/test_gate_t004_*.py`）。
- 需要新增或升级依赖、写 `.npmrc`、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200
- cost_budget: tracking-only
- 时间分配：调查约 12 分钟、实现与补测约 30 分钟、必要检查约 14 分钟、最终报告约 5 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。

## Rework（返工第 1 轮，内核追加）

- 基线 `9f784056c5af4217835df20078abcacaae38178a` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面终审列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

B1 工具提示在「悬停与聚焦并存」时，移开、失焦不消失（违背合同第 3 条与 D01）。
位置：desktop/web/src/components/Tooltip.tsx 第 54–57 行 onMouseLeave 里的 `if (!focusedRef.current) hide();`（:56），第 63–66 行 onBlur 里的 `if (!hoveringRef.current) hide();`（:65）。
合同条款：第 3 条「移开、失焦立即消失并取消计时」；D01「移开、失焦、Esc 都让它消失」。两句都没有「另一边还在就不消失」的例外。
现象：陈列页图标按钮演示里，悬停 400ms 出现提示 → 点按钮（Chromium 里点按钮会让它获得焦点）→ 鼠标移出：提示留在原地，直到按钮失焦。计时中（例如悬停 200ms 时点击）移开，提示仍会在到点后出现，计时没有被取消。
期望：onMouseLeave 清掉 hoveringRef 后无条件 hide()；onBlur 清掉 focusedRef 后无条件 hide()。Esc 相关的判断（onKeyDown、onDocKeyDown 里对 hoveringRef、focusedRef 的使用）不要改。
补测：在 desktop/web/tests/icon-button.test.tsx 增加三条，沿用文件里的 mount 与 advance：(1) fireEvent.focus 后 fireEvent.mouseEnter，advance(400) 后可见；fireEvent.mouseLeave 后立即没有 role=tooltip，按钮上没有 aria-describedby；(2) fireEvent.mouseEnter，advance(400) 后可见，再 fireEvent.focus、fireEvent.blur，立即没有 role=tooltip；(3) fireEvent.focus 后 fireEvent.mouseEnter，advance(200)，fireEvent.mouseLeave，再 advance(500)，仍没有 role=tooltip。三条在现有实现上都应失败，改后通过。
范围：只改 Tooltip.tsx 的这两处与 icon-button.test.tsx；不改基准测试，不动其它文件，不改其它行为。
