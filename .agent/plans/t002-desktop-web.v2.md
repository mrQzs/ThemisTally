# TASK: t002-desktop-web

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 30f8624448165d94f13ec6a7ef5fe71773ebcb08
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T002 第 1 片：`desktop/web/` 工程骨架、设计令牌、W4 契约检查与 5 个原子组件。目标是让 `desktop/web/` 能 `npm ci`、`npm run build`、`npm test`、`npm run check:contract` 全部通过；令牌与画布逐项相等；组件陈列页列出全部变体供人工对照。

## Non-goals
- 不做随包字体：`src/styles/fonts.css`、字体依赖（`@fontpkg/*` 或其他字体包）、OFL 原文与 `dist` 里的字体文件都移出本片，另立一片「随包字体」（依据站主 2026-10-19 答复 msg-id `20261019T092117759962Z-owner-b9ad32`）。字体片落地前，`tokens.css` 的 `--tt-font-sans` / `--tt-font-mono` 首项 `"TT Sarasa Mono SC"` 解析不到，自动落到后面的系统字体。
- 不做应用框架与底部 Tab 栏、标题栏、Logo、页面、`src/api.ts` 与夹具数据（第 3 片）。
- 不做对话框、图标按钮、工具提示、分段选择、开关、复选框、页签、输入框、下拉、表格、抽屉等交互原子（第 2 片）。
- 不做 W1、W2、W5、W6、W7。
- 不改 `desktop/shell/`、`.agent/.ui.lock/` 与 `gitignore.append.txt`（属于 `kit_ui`/D13）。
- 不接本机服务、不发网络请求、不做 Electron 外壳、写操作与确认流程。

## Repository facts
- 入口：新建 `desktop/web/`；`src/main.tsx` 挂载 `src/App.tsx`（组件陈列页）；`src/components/index.ts` 统一导出 `Button`、`Tag`、`StatusTag`、`Card`、`Banner`；`src/domain/attemptStates.ts` 放 17 状态映射；`desktop/web/scripts/token-contract.mjs` 是 W4 契约检查。
- 调用关系与现有约定：第 1 片只有陈列页，不接本机服务、不用 `src/api.ts`；所有组件只用 `--tt-*` 令牌；设计依据 `docs/ui-design/pages/01-设计令牌-Themis-Tally.html`、`docs/ui-design/pages/02-基础组件-Themis-Tally.html` 与 `docs/ui-design/handoff.md`。
- 工具链与锁文件：Node 24.19.0、npm 11.17.0（`.agent/environment.md`）；React 18 + TypeScript strict + Vite + Vitest（D9）；锁文件 `desktop/web/package-lock.json`（`lockfileVersion` 为 3），`npm ci` 可复现。
- 基线检查：基线 HEAD `e76da22`，`desktop/web/` 尚不存在，无既有前端测试；全量 pytest 有 1 个已知失败（`test_desktop_cli::test_cat_reads_are_bounded` 的平台假设，见 `.agent/environment.md`），本片不动 Python，不跑全量。战前门禁 `tests/test_gate_t002_baseline.py` 由门禁端稍后写、内核做成基线提交，在基线上应失败。

## Scope
- allowed_modified_files:
  - .gitignore
- allowed_new_files:
  - desktop/web/**
- allowed_deleted_files: 无
- forbidden_paths:
  - docs/**
  - scripts/**
  - .agent/**
  - .agents/**
  - .claude/**
  - .codex/**
  - .pi/**
  - tests/test_gate_t002_*.py
- dependency_changes: allowed（在 desktop/web 里装 npm 依赖并提交锁文件，npm ci 可复现）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
### 正常输入与输出
- 在 `desktop/web/` 里 `npm ci` 按锁文件装依赖；`npm run build` 先 `tsc --noEmit` 再 `vite build` 生成 `dist/index.html` 与资源；`npm test`（`vitest run`）全部通过；`npm run check:contract`（`node scripts/token-contract.mjs`）退出 0。
- `App` 渲染组件陈列页，列出 5 个原子组件的全部变体与状态；页面上有三个按钮切换根元素的 `data-theme`：去掉即暗色、`light` 亮色、`system` 跟随系统。

### 边界与错误
- `StatusTag` 遇到 17 个已知状态以外的任意状态码：原样显示状态码文本、`neutral` 色调、`circle-help` 图标，`title` 为状态码。
- `Button` 处于 `loading`：渲染转圈图标与加载文字、`disabled`、`aria-busy` 为 `true`。
- `Banner`：只有 `info` 渲染关闭按钮（`aria-label` 为「关闭提示」）；`warning`、`danger` 不渲染关闭按钮；`danger` 根元素 `role` 为 `alert`，`info` 与 `warning` 无此 role。
- 契约检查：有违规时每条一行 `路径:行号: 规则: 片段` 并退出 1；无违规退出 0；`--src` 或 `--tokens` 指向的目录或文件不存在时以非 0 退出并给出可读错误。

### 并发、取消
不适用：本片是纯静态只读前端，没有异步业务状态；组件里的「加载」只是展示态，不发起请求。

### 兼容性
- 只新增 `desktop/web/**`，只向根 `.gitignore` 追加内容；不改仓库其它工具链、不写 `.npmrc`、不装全局包。
- `desktop/web/package.json` 与 `desktop/web/package-lock.json` 里没有任何字体包依赖（无 `@fontpkg/*`，也无其他字体包）；不建 `src/styles/fonts.css`；`public/licenses/` 与 `THIRD_PARTY_NOTICES.md` 只记 Lucide（名称、版本、ISC 许可原文、来源），不记任何字体。
- 运行时不从网络加载任何资源；`index.html` 不写内联脚本与内联样式，只有一个外部 module 脚本。
- 构建与测试不得在未忽略位置留下文件（`.tsbuildinfo`、临时配置、覆盖率目录都不入库）。

### 设计令牌（`src/styles/tokens.css`）
- 文件里只有 `--tt-*` 自定义属性与 `color-scheme`；不含 `@font-face` 与基础样式（基础样式在 `base.css`；本片不建 `fonts.css`）。
- 取值与画布 `docs/ui-design/pages/01-设计令牌-Themis-Tally.html` 的 `tokens.css` 逐项相等（空白归一化后相同），含 handoff「Token 补充」的 7 项新增与 2 项修正。
- `--tt-font-sans` / `--tt-font-mono` 照 handoff「字体与品牌 › 字体」的整条字体栈写：`"TT Sarasa Mono SC"`, `"Sarasa Mono SC"`, `"等距更纱黑体 SC"`, `"Sarasa Term SC"`, `"Maple Mono NF CN"`, `"Cascadia Mono"`, `"Noto Sans Mono CJK SC"`, `monospace`；`--tt-font-mono` 取 `var(--tt-font-sans)`。首项 `"TT Sarasa Mono SC"` 由随包字体片提供，本片落地前它解析不到，自动落到后面的系统字体；`base.css` 照旧用这两个令牌。
- 按选择器分块：`:root`（原色、字号、间距、圆角、时长、层级、`--tt-tabbar-height` 与暗色语义色，暗色为缺省）；`:root[data-theme=light]`（亮色）；`@media (prefers-color-scheme: light)` 内的 `:root[data-theme=system]`（跟随系统）；`@media (prefers-reduced-motion: reduce)`（三个时长置 0ms）。
- 画布的 `.tt-theme-dark`、`.tt-theme-light` 两个类是实现手段，可保留也可不保留，不影响取值。

### 基础样式（`src/styles/base.css`）
- 搬画布基础规则：`.tt-app` 的字体、颜色、底色与 `font-variant-ligatures: none`；`box-sizing`；`:focus-visible` 焦点环；`.tt-num`；`.tt-i`；动画关键帧与减少动效时静止；`.tt-content` 容器查询与 `forced-colors`。

### 契约检查（`desktop/web/scripts/token-contract.mjs`，W4）
- Node，零依赖。扫描 `src/**/*.{css,ts,tsx}`，排除令牌文件 `src/styles/tokens.css` 与 `*.test.*`。
- 规则 1（未定义变量）：源码里出现的每个 `--tt-…` 都必须在令牌文件里定义；在组件里用 `--tt-x:` 自行定义也算违规。
- 规则 2（写死颜色）：十六进制 `#` 后接 3、4、6、8 位十六进制字符；颜色函数 `rgb(`、`rgba(`、`hsl(`、`hsla(`、`hwb(`、`lab(`、`lch(`、`oklab(`、`oklch(`、`color(`；CSS 命名颜色（148 个）作为颜色类属性（`color`、`background`、`background-color`、`border` 及各边与 `-color`、`outline` 与 `outline-color`、`box-shadow`、`fill`、`stroke`、`text-decoration-color`、`caret-color` 等）的取值。
- 允许：`transparent`、`currentColor`、CSS 全局关键字（`inherit`、`initial`、`unset`、`revert`、`revert-layer`）、CSS 系统颜色（`Canvas`、`CanvasText`、`Highlight`、`ButtonText` 等）。
- TSX：命名颜色只在 `style={{…}}` 对象里、且键为颜色类属性时判定；十六进制在 TS/TSX 字符串里同样识别（因此组件里不要写以 `#` 开头的锚点，例如 `href` 为 `#add`）。
- 命令行：`node scripts/token-contract.mjs --src <目录> --tokens <文件>`，缺省 `--src src --tokens src/styles/tokens.css`。输出每条违规一行 `路径:行号: 规则: 片段`，有违规退出 1，无违规退出 0。

### 组件接口（`src/components/index.ts` 统一导出）
- `Button`：属性 `variant`（`primary` | `secondary` | `ghost` | `danger`）、`size`（`sm` | `md` | `lg`，高 28/32/36）、`loading`（布尔）、加载文字、`disabled`。加载时渲染转圈图标与加载文字并 `disabled`、`aria-busy` 为 `true`；根元素为 `button`，带 `data-variant`、`data-size`。
- `Tag`：属性 `tone`（`neutral` | `info` | `attention` | `success` | `warning` | `danger` | `escalate` | `brand`）、`mono`（布尔）。高 20、内边距 0 6、圆角 sm；`mono` 用 `--tt-mono-sm`，否则 `--tt-text-caption-strong`；底色与字色取 `--tt-tone-<tone>-bg` / `--tt-tone-<tone>-fg`；根元素带 `data-tone`。
- `StatusTag`：属性 `state`（字符串）、`size`（`md` | `sm`，高 22/20）。已知状态显示中文标签、色调与图标，`title` 为状态码；未知状态原样显示状态码、`neutral`、`circle-help` 图标、`title` 为状态码。根元素带 `data-tone`、`data-size`、`title`。
- `Card`：属性 `title`（节点）、`actions`（节点）。根元素 div：`surface-1` 底、`border` 边、圆角 lg 8、内边距 16；头部为标题（`--tt-title-sm`）与右侧操作。
- `Banner`：属性 `tone`（`info` | `warning` | `danger`）、`onClose`（仅 `info` 用）。`info` 用 `info` 图标并渲染关闭按钮（`aria-label` 为「关闭提示」）；`warning`、`danger` 用 `triangle-alert` 图标且不渲染关闭按钮；`danger` 根元素 `role` 为 `alert`；根元素带 `data-tone`。

### 状态表（`src/domain/attemptStates.ts`）
- 导出 17 个已知状态到 `{ label(中文), tone, icon }` 的映射，另含未知状态的兜底（原样显示状态码、`neutral`、`circle-help`）。取自画布「3.4 attempt 的 17 个状态 + 兜底」与 UI 文档 §3.4。
- 状态码到中文/色调/图标（Lucide）：PREPARING 准备中 info hourglass；PREPARED 待运行 neutral circle-dashed；PREPARE_FAILED 准备失败 danger circle-x；RUNNING 运行中 info loader-circle；COLLECTING 收集证据 info archive；NEEDS_REVIEW 待验收 attention scale；PASS 通过 success circle-check；ACCEPTED_WITH_EXCEPTION 带豁免通过 success badge-check；REVISE 返工 warning rotate-ccw；BLOCKED 阻塞 danger octagon-x；ESCALATE 升级 escalate circle-arrow-up；INFRA_FAILURE 基础设施故障 danger server；TIMEOUT 超时 warning timer-off；CANCELLED 已取消 neutral ban；INTEGRATED 已集成 brand git-merge；ABANDONED 已放弃 neutral archive-x；SUPERSEDED 已被取代 neutral layers；兜底（未知状态码）原样显示状态码 neutral circle-help。

### 图标（`src/icons/`）
- 放第 1 片组件用到的图标：上表 17 个状态图标与 `circle-help`，加 `loader-circle`、`info`、`triangle-alert`、`x`。
- 24×24 viewBox、`stroke` 为 `currentColor`、`aria-hidden` 为 `true`；路径取自 Lucide；把 Lucide 版本、来源与 ISC 许可原文记到 `public/licenses/` 与 `THIRD_PARTY_NOTICES.md`。

### 门禁组件探针目录（Q4）
- 目录：`desktop/web/gate-probe/`，被根 `.gitignore` 忽略（追加一行 `desktop/web/gate-probe/`）。
- 文件名规则：`probe-<唯一标识>.test.tsx`，每次运行唯一。
- Vitest 能跑到：`vite.config.ts` 的 `test.include` 含 `gate-probe/**/*.test.{ts,tsx}`，另含 `src/**/*.test.{ts,tsx}` 与 `tests/**/*.test.{ts,tsx}`；`environment` 为 `jsdom`。
- 门禁运行：在 `desktop/web` 下 `npm test -- gate-probe/<文件名>`，用 `try/finally` 删除临时文件（并删空目录）。
- 探针断言：17 个状态各自的中文与 `title`、未知状态兜底、加载按钮 `disabled` 且 `aria-busy`、三种提示条关闭按钮的有无与 `danger` 的 `role` 为 `alert`。

## Steps
1. 预检（只读）：记 `node -v`、`npm -v`、`npm config get registry`。node、npm 版本与 `.agent/environment.md` 不符，或 registry 不是 `https://registry.npmjs.org/` 时停止并报告。
2. 先写忽略规则：在任何 npm 命令之前，向根 `.gitignore` 末尾追加注释与三行 `desktop/**/node_modules/`、`desktop/**/dist/`、`desktop/web/gate-probe/`；原有行不变；用 `git check-ignore` 确认。
3. 工程骨架：建 `desktop/web/`：`package.json`（`private` 为 true、`type` 为 module；scripts 含 `dev`、`build`、`test`、`typecheck`、`check:contract`，`build` 先 `tsc --noEmit` 再 `vite build`，`test` 为 `vitest run`）；`tsconfig.json`（`strict` 为 true、`noEmit`，纯 JSON 无注释）；`vite.config.ts`（React 插件，`base` 为 `./`；Vitest 用 jsdom，`include` 含 `src/**/*.test.{ts,tsx}`、`tests/**/*.test.{ts,tsx}`、`gate-probe/**/*.test.{ts,tsx}`）；`index.html`（`lang` 为 `zh-CN`，只一个外部 module script，无内联脚本与样式，不写 `data-theme`）；`src/main.tsx`、`src/App.tsx`。
4. 安装依赖、提交锁文件：在 `desktop/web/` 用 `npm install --save-exact` 装运行时 `react@18`、`react-dom@18`，开发 `typescript`、`vite`、`@vitejs/plugin-react`、`vitest`、`jsdom`、`@testing-library/react`、`@testing-library/dom`、`@types/react@18`、`@types/react-dom@18`；不装任何字体包（无 `@fontpkg/*` 或其他字体包）。若当前稳定版不支持 Node 24.19.0 或 Windows，选最近的受支持版本并在执行报告里说明。锁文件 `lockfileVersion` 为 3、`resolved` 全在 registry.npmjs.org；删 `node_modules` 后 `npm ci` 成功且不改锁文件。不写 `.npmrc`。
5. 令牌 `src/styles/tokens.css`：见 Behavior contract「设计令牌」。
6. 基础样式 `src/styles/base.css`：见「基础样式」。
7. 契约检查 `desktop/web/scripts/token-contract.mjs` 与 `desktop/web/tests/token-contract.test.ts`：见「契约检查」；测试在临时目录造样本，覆盖合法写法通过、逐类违规失败。
8. 图标 `src/icons/`：见「图标」；Lucide 的 ISC 许可原文取不到就停止报告，不凭记忆写。
9. 首批原子组件与状态表：见「组件接口」与「状态表」；每个组件一份 CSS 只用令牌；`src/components/index.ts` 统一导出。
10. 组件陈列页：`App` 渲染陈列页，列出全部变体与状态；三个按钮切换根元素 `data-theme`（暗、亮、跟随系统）。
11. 自检与说明：依次跑 `npm ci`、`npm run build`、`npm test`、`npm run check:contract`，确认 `git status` 没有新的未忽略文件；写 `desktop/web/README.md`（命令、目录约定、令牌规则）。

## Setup
无。本合同的 prepare setup 为空；`npm ci` 只在门禁 pytest 里跑（见报告 §4.5）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t002_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：desktop/web 能 npm ci、build、test、check:contract 四步全部通过，令牌与画布逐项相等，5 个原子组件与陈列页就位；证据：V01；目的：门禁黑盒从干净副本跑通四步并核对产物、令牌、契约与组件行为，确保这一片真能用。
- D02：所有改动都在允许集合内，只新增 desktop/web/** 并只追加根 .gitignore，未触碰 docs、scripts 与门禁测试；证据：scope。
- D03：没有删除、跳过或弱化任何既有测试；证据：review。
- D04：契约检查脚本在合成样本上对十六进制、rgba()、命名颜色、未定义 var、TSX 颜色写法都判违规并退出非 0，对合法写法放行；证据：V01；目的：保证 W4 是真检查而不是空跑。
- D05：`dist`、`desktop/web/src`、`desktop/web/public` 里没有任何字体文件（woff2、woff、ttf、otf），也没有 `@font-face`；证据：V01；目的：确认随包字体确实移出本片，第 1 片产物与源码里不残留任何字体文件或 @font-face。

## Stop conditions
- 基线与 Repository facts 不符：`desktop/web` 已存在、Node/npm 版本不符、registry 不是 `https://registry.npmjs.org/`。
- 必须修改允许范围之外的文件才能继续（尤其 `docs/**`、`scripts/**`、门禁测试 `tests/test_gate_t002_*.py`）。
- 需要写 `.npmrc`、安装全局包、或从非 registry.npmjs.org 拉依赖。
- Lucide 的 ISC 许可原文取不到。
- 需要引入与 D9 技术栈冲突的依赖（Tailwind、framer-motion、图标库、路由库）。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 时间分配：调查约 8 分钟、实现与补测约 16 分钟、必要检查约 10 分钟、最终报告约 4 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D05，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。
