# TASK: t052-desktop-web-bind-form-reopen

<!-- 合同 v1：T052「改绑定的两个表单每次打开都按当时的绑定预填」。
     改法（站主已定，规划端核实）：把字段状态、底部实时预览与表单对话框挪进一个**只在打开时挂载**的内层组件
     （{open && <内层 …/>}）；外层保留 useWriteFlow(reload) 与 <WriteFlow flow={flow} />。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片不改任何导出形态（导出名、props、逐字文案都不动），旧门禁与既有包内测试一个字都不用改——
     这一点在「兼容性」一节逐条列出了核查依据。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: f7c06d495764509ad569c8729f9470ec9d44266b
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「角色与模型」页上两个改绑定的表单（`HubBindForm` 的 [改绑定…]、`RoleBindForm` 的 [更改…]）**每次打开都按当时的 props 重新预填**：改过字段点 [取消] 再开回到现有绑定；别的写入口改了绑定、重读后 props 变了再开按新绑定预填；表单早已挂着、后来新增了候选再开也按当时的候选预填。写流程照旧：点 [确认…] 先关表单再 `start`，确认框、执行、重读、终态在表单关上之后照常走完；其余行为、文字、样式一个字不变。

## Non-goals
- 不做 [保存当前为方案…]（下一片 T053）；不改 ProfileForm、RuntimeForm（新建表单每次打开本来就清空，情形不同）。
- 不改入口文件 `roles-HubPosts.tsx`、`roles-RoleCard.tsx`、`roles-RolesView.tsx`、`RolesPage.tsx`；不改 `api.ts`、`useWriteFlow.ts`、`useLivePreview.ts`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`hubChangeLines.ts`、`components/**`、`shell/**`、`hub-bind-form.css`。
- 不改既有包内测试 `desktop/web/tests/writes-hub-bind.test.tsx`、`desktop/web/tests/writes-role-bind.test.tsx`；不改任何门禁基准测试文件（本片的 `tests/test_gate_t052_*.py` 与其余 50 份一律禁改）。
- 不改依赖与锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`）；不新增依赖、不新建 CSS 文件、不新增桩情景（`WriteScenario` 的值一个都不许加）。
- 不做「打开时按当时的 props 重置字段状态」那一种写法（站主已定第一种；本片只做一种，两个表单同一种）。

## Repository facts
以下事实都在本回合的工作目录（基线 `25012c98`）里逐条读过；行号按该基线。

### 两个要改的源文件（现状）
- `desktop/web/src/writes/HubBindForm.tsx`：
  - `HubBindDialog`（`:34`）拿到 `HubBindFormProps & { open: boolean; onClose: () => void }`；`:46` 是 `const { start, flow } = useWriteFlow(reload);`。
  - 预填：`:50-53` `initialMain`（配置行且现有主绑定在候选里 → 用它，否则第一个候选）、`:54-57` `initialFallback`（配置行且现有替补在该主选下的替补候选里 → 用它，否则空串）；`:58-59` 是 `useState(initialMain)` 与 `useState(initialFallback)`。
  - `:65` `const canPreview = open && main !== '';`；`:71` `useLivePreview('hub.set', buildArgs(), canPreview)`；`:72` `confirmEnabled = canPreview && current && result !== null && result.ok`。
  - `:87` `renderBottom()` 里 `if (!canPreview) return null;`、`:88` 「预览中…」、`:89` `if (!result || !current)`；`:121` `<Dialog open={open} onClose={onClose} title={`改绑定：${postLabel}`} …>`；`:144` `<WriteFlow flow={flow} />`。
  - `:150` `export function HubBindAction(props: HubBindFormProps)`：`:151` `const [open, setOpen] = useState(false);`，没有候选时渲染 `DisabledAction`，否则渲染 [改绑定…] 按钮并**一直挂** `<HubBindDialog {...props} open={open} onClose={() => setOpen(false)} />`；`:164` `export function HubUnsetAction({…})`。
  - 两个原因句常量在文件头部（`REASON_NO_CANDIDATES`、`REASON_UNSET_DEFAULT`），逐字内容见「写法钉死」。
- `desktop/web/src/writes/RoleBindForm.tsx`（T051）：
  - `:39` 模块级 `modeOptionsOf(modes, candidates)`（候选为空时从模式列表里拿掉「无头」）；`:45` `RoleBindDialog`；`:55` `useWriteFlow(reload)`；`:56` `options = modeOptionsOf(modes, candidates)`。
  - 预填：`:60` `initialMode`（现有模式在可选列表里就用它，否则第一个可选）、`:61-62` `initialProfile`（现有绑定 profile 在候选里就用它，否则第一个候选）；`:63-64` 是 `useState(initialMode)` 与 `useState(initialProfile)`。
  - `:68` `const canPreview = open && mode !== '' && (!headless || profile !== '');`；`:81` `useLivePreview('role.set', buildArgs(), canPreview)`；`:82` `confirmEnabled = canPreview && current && result !== null && result.ok`。
  - `:117` `<Dialog open={open} … title={`改绑定：${roleLabel}`} …>`；`:147` `<WriteFlow flow={flow} />`；`:154` `export function RoleBindAction(props: RoleBindFormProps)`（`:155` `useState(false)`，可选模式为空时渲染 `DisabledAction`，否则渲染 [更改…] 按钮并**一直挂** `<RoleBindDialog {...props} open={open} onClose={() => setOpen(false)} />`）。
  - 导出 `RoleBinding`（`{ mode; profile: string | null; host: string | null; cadenceSeconds: number | null }`）、`RoleBindAction`；`RoleBindFormProps` 不导出。

### 相关共享件（只读引用，本片不改）
- `desktop/web/src/writes/useLivePreview.ts`：`:7` `const DEBOUNCE_MS = 300;`；`:54` `const key = JSON.stringify(args);`；`:55` `const [result, setResult] = useState<LivePreview | null>(null);`——**结果只活在调用这个 hook 的组件里**：组件不卸载，`result` 跨开关保留；组件卸载，再开就是新的（`result` 为 `null`）。
- `desktop/web/src/components/Dialog.tsx`：`:29` `if (!open) return null;`——对话框关着时不渲染任何按钮与 select；`:27` `useOverlayFocus(open, dialogRef)`。
- `desktop/web/src/components/overlay/useOverlayFocus.ts`：打开时的 effect 记下打开前的焦点并同步聚焦到框内第一个可聚焦元素，cleanup 时把焦点还给打开前的元素；**卸载也走 cleanup**。所以「挂载即开、卸载即关」与原来的开关切换在焦点上等价。
- `desktop/web/src/pages/RolesPage.tsx`：`:63` `load={loadRoles}`、`:71` `<RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />`；`loadRoles`（`:26-27`）并行读 `getRoles/getProfiles/getPresets/getHubRoles`，**roles 与 profiles 来自同一次读，reload 一起刷新**；重读后 `RolesView` 按 `key={r.role}` 渲染同一批卡片（组件不卸载，只是 props 变了）。
- `desktop/web/src/pages/readonly1/roles-HubPosts.tsx`：`:209-215` 给每个岗位行渲染 `<HubBindAction post postLabel mainCandidates={allowedProfiles(…)} fallbackCandidatesFor={(id) => hubFallbackCandidates(…)} source mainProfile … />`。
- `desktop/web/src/pages/readonly1/roles-RoleCard.tsx`：卡片底部渲染 `<RoleBindAction … candidates={…} reload={reload} />`。

### 门禁与既有测试的核查结论（本片**不改**它们）
- `tests/test_gate_t045_baseline.py`：S03（`:347-409`）对 `HubBindForm.tsx` 只做**包含式**核对——从 `../api` 只 `import type`；运行时引 `hubChangeLines`；`import './hub-bind-form.css';` 之后不许再有 `import … from './…'`；导出 `export function HubBindAction(` 与 `export function HubUnsetAction(`；两个原因句逐字在位；按钮文字恰为「改绑定…」「恢复缺省…」；全文不出现 `aria-label`；出现「改绑定：」「主绑定」「替补」「不设替补」「useLivePreview(」「'hub.set'」「'hub.unset'」「<WriteFlow flow={flow} />」以及门控里的 `current`、`result.ok`、`onClose`；不跨层引 `src/pages`；代码（去注释）里不出现 `step-low`；禁词（`XMLHttpRequest`/`EventSource`/`WebSocket`/`dangerouslySetInnerHTML`/`innerHTML`/`outerHTML`/`insertAdjacentHTML`/`eval(`/`new Function`/`document.write`/`srcdoc`/`DOMParser`/`matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`/`role="status"`/`（UTC `）；不写死颜色。S10（`:741-766`）查禁词与颜色。**这两个文件都没有字节冻结**。
- `tests/test_gate_t051_baseline.py`：S07（`:565-625`）对 `RoleBindForm.tsx` 同样只做**包含式**核对——`export function RoleBindAction(`；原因句逐字；标题字面量 `改绑定：${roleLabel}`；`label="模式"`、`label="profile"`；按钮文字恰为「更改…」且有 `variant="secondary"` 与 `size="sm"`；`import './hub-bind-form.css';` 放在组件 import 之后且之后不再有 `../` 的 import；只引 `hub-bind-form.css` 这一个样式表；`DisabledAction`；`useLivePreview(`；`'role.set'`；`<WriteFlow flow={flow} />`；门控里的 `current`、`result.ok`、`onClose`；不跨层引 `src/pages`；禁词；不写死颜色；不写 `style={{`。**同样没有字节冻结**。
- 两份门禁的**探针**：T045 的探针每条 `it` 新挂载页面，没有「再开」（`:1277-1287` 只点一次 [取消]）；T051 的探针 `:1198-1237` 关着时没有下拉、`:1209-1237` 每轮 cleanup 后重挂；唯一的「再开」是 `:1437-1458`（planning_review 写完再开、切无头、断言 profile 预填第一个候选）——两次打开之间 props 不变，按当时的 props 重算结果相同。
- 既有包内测试：`desktop/web/tests/writes-role-bind.test.tsx:340-360`（与上面那条探针同形）与 `desktop/web/tests/writes-hub-bind.test.tsx`（没有再开）都不受本片影响；其余用例都是新挂载。
- 关键字搜索（`HubBindForm`、`RoleBindForm`、`HubBindDialog`、`RoleBindDialog`、`useState`、`改绑定：`，范围 `desktop/web/tests` 与 `tests/`）：命中的只有上面这些；`HubBindDialog`/`RoleBindDialog` 在测试与门禁里一次都没出现；`useState` 在门禁里的命中都与这两个文件无关。
- 字节冻结现状：`tests/test_gate_t047_baseline.py:86-94` 与 `tests/test_gate_t048_baseline.py:130-140` 的 `BASELINE_DIGESTS` 里**没有**本片要动的两个源文件，也没有新测试文件（`page-app.test.tsx` 与 `api.ts` 的冻结已在 T051 解除）。
- `tests/test_gate_t002_baseline.py:1496`：`desktop/web` 下所有 `*.test.*` 里不许 `skip`/`only`/`todo`——新测试文件要遵守。
- 过渡断言：任务书列出的 `test_transitional_*` 一条也不涉及 `src/writes` 的这两个文件；`desktop/web/tests/page-app.test.tsx`（写入口个数）与 `desktop/web/tests/readonly2-app.test.tsx`（夹具下的写入口）不推翻——按钮个数与禁用数不变，关着时 DOM 不变。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`。
- `desktop/web/tsconfig.json` 的 `include` 只有 `["src", "vite.config.ts"]`：`tests/` 里的文件不过 `tsc --noEmit`，但 vitest 会读到。
- 仓库门禁用 `python -m pytest`；本片不改任何依赖清单与锁文件（`dependency_changes: forbidden`）。

### 基线检查
- 本回合（合同端）只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 执行端动手前先在 `desktop/web` 跑一次 `npm test`（基线应全绿：T051 已结项），把结果记进执行报告；基线上本片要修的行为一个都不存在（取消后再开仍显示上次的值、外部改动后重读再开仍显示旧绑定、新增候选后 profile 初值仍是空串）。

## Scope
- allowed_modified_files:
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/RoleBindForm.tsx
- allowed_new_files:
  - desktop/web/tests/writes-bind-reopen.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t052_*.py
  - tests/test_gate_t001_baseline.py
  - tests/test_gate_t002_baseline.py
  - tests/test_gate_t003_baseline.py
  - tests/test_gate_t004_baseline.py
  - tests/test_gate_t005_baseline.py
  - tests/test_gate_t006_baseline.py
  - tests/test_gate_t007_baseline.py
  - tests/test_gate_t008_baseline.py
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t010_baseline.py
  - tests/test_gate_t011_baseline.py
  - tests/test_gate_t012_baseline.py
  - tests/test_gate_t013_baseline.py
  - tests/test_gate_t014_baseline.py
  - tests/test_gate_t015_baseline.py
  - tests/test_gate_t016_baseline.py
  - tests/test_gate_t017_baseline.py
  - tests/test_gate_t018_baseline.py
  - tests/test_gate_t019_baseline.py
  - tests/test_gate_t020_baseline.py
  - tests/test_gate_t021_baseline.py
  - tests/test_gate_t022_baseline.py
  - tests/test_gate_t023_baseline.py
  - tests/test_gate_t024_baseline.py
  - tests/test_gate_t025_baseline.py
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t027_baseline.py
  - tests/test_gate_t028_baseline.py
  - tests/test_gate_t030_baseline.py
  - tests/test_gate_t031_baseline.py
  - tests/test_gate_t032_baseline.py
  - tests/test_gate_t033_baseline.py
  - tests/test_gate_t034_baseline.py
  - tests/test_gate_t035_baseline.py
  - tests/test_gate_t036_baseline.py
  - tests/test_gate_t037_baseline.py
  - tests/test_gate_t038_baseline.py
  - tests/test_gate_t039_baseline.py
  - tests/test_gate_t040_baseline.py
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t042_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t051_baseline.py
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/mock/profiles.json
  - desktop/web/src/mock/quizs.ts
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/api.ts
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/tests/writes-hub-bind.test.tsx
  - desktop/web/tests/writes-role-bind.test.tsx
  - desktop/web/tests/roles-hub-logic.test.ts
  - desktop/web/tests/roles-hub-turns.test.ts
  - desktop/web/tests/live-api.test.ts
  - ts/package.json
  - ts/bun.lock
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/writeroutes.ts
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - **打开**：`HubBindAction` / `RoleBindAction` 的入口按钮点开对话框时，表单对话框（`Dialog`）、两个字段（`Select`）、底部实时预览与 [取消]／[确认…] 都在；关着时页面上只有那个入口按钮（`Dialog` 关着时 `return null`，DOM 与今天一样）。
  - **预填规则一个字不变**（照 T045 与 T051 的 D07）：
    - HubBindForm：主选——`source === 'config'` 且现有主绑定在 `mainCandidates` 里 → 用它，否则第一个候选；替补——`source === 'config'` 且现有替补在该主选下的替补候选里 → 用它，否则空串。
    - RoleBindForm：模式——现有模式在可选列表里 → 用它，否则第一个可选；profile——现有绑定 profile 在 `candidates` 里 → 用它，否则第一个候选。
    - RoleBindForm 的「无头」在没有候选时从模式列表里拿掉（`modeOptionsOf` 照旧），原因句照旧在 `Select` 的 `help` 里。
  - **每次打开都重算**：表单关闭（[取消]、Esc、点 [确认…]）后，表单里的未保存取值一律丢弃；再打开时按**当时**的 props 重新算预填。这三条情形都要对：
    1. 改了字段、点 [取消]，再开 → 回到现有绑定（现有绑定不在候选里时照规则落到第一个候选）。
    2. 别的写入口改了绑定、页面重读后 props 变了，再开 → 按新绑定预填。
    3. 表单早已挂着、后来新增了候选，再开 → 按当时的候选预填（现有绑定这时在候选里就用它）。
  - **表单开着时 props 变了**：不重置用户正在改的字段（与今天一样）；候选列表每次渲染照旧按 props 算。
  - **写流程照旧**：点 [确认…] 时**先关掉表单对话框**，再 `start(spec)`（同一批更新里）；确认框、执行、重读、终态在表单关上之后照常渲染与走完——因为 `useWriteFlow(reload)` 与 `<WriteFlow flow={flow} />` 留在**外层**组件里（表单关掉不卸载它们）。写参数与今天完全一样：HubBindForm 是 `{ post, profile }`（替补非空才带 `fallback`），RoleBindForm 是 `{ role, target }`（`host`／`cadence_seconds` 的原样传回规则照旧）。
  - **底部实时预览**：命令、岗位/角色的绑定前后、warnings、running_turns（HubBindForm）、错误原文——显示规则与今天一样（`useLivePreview('hub.set' | 'role.set', buildArgs(), canPreview)`，300ms 防抖，迟到的回应按序号丢弃）。[确认…] 的门控照旧：`canPreview && current && result !== null && result.ok`。
  - **有意的行为变化（本片唯一一处可见变化）**：再打开时底部先显示「预览中…」、[确认…] 灰着，等新的预览回来才可点——与第一次打开一样。原来参数没变时再开，会立刻显示上一次的预览结果并让 [确认…] 立刻可点；那是同一类「按旧数据显示」的问题，本片一并去掉。
- 边界输入：
  - 没有主选候选（`mainCandidates` 为空）：[改绑定…] 仍禁用并给出原因句（照旧），对话框不开。
  - 没有已登记的 profile（`candidates` 为空）：RoleBindForm 的模式列表里没有「无头」，原因句在 `help` 里；`execution` 角色的 [更改…] 仍禁用（照旧）。
  - 现有主绑定／profile 不在候选里：照预填规则落到第一个候选（不新增规则）。
  - 现有模式不在可选列表里：落到第一个可选模式（照旧）。
  - 对话框关着时：DOM 里没有这些表单的 `select`，也没有 [取消]／[确认…]（`Dialog` 关着时 `return null`；关着时表单组件根本不挂载，DOM 与今天一致）。
  - 预览失败（服务没回应／信封 `ok` 为假）：底部显示错误原文，[确认…] 不可点；不自动重试（照旧）。
  - 写流程失败（409／5xx／超时／拒绝／过期）：照既有 `useWriteFlow` 与 `WriteConfirmDialog` 的分支显示，不加新分支、不改既有文案；表单对话框已经关了，再开按当时的 props 预填（本片的新行为）。
- 并发、取消与状态变化：不适用——本片不加并发、不加网络调用、不加计时器；表单一次只开一个（关掉即丢弃未确认的取值，内层组件随之卸载）。
- 兼容性：
  - **导出与公开接口一个字不变**：`HubBindForm.tsx` 仍导出 `HubBindAction`、`HubUnsetAction`；`RoleBindForm.tsx` 仍导出 `RoleBindAction`、`RoleBinding`；两者的 props 名称、类型、可选性一个不改；不新增导出、不改签名、不改导出顺序。`RoleBinding` 的四个字段语义不变。
  - **文字与文案一个字不变**：两个原因句常量逐字保留；对话框标题、Select 标签、空值选项「不设替补」、按钮文字「改绑定…」「恢复缺省…」「更改…」「取消」「确认…」「预览中…」以及底部各类文案都照旧。
  - **样式一个字不变**：复用 `hub-bind-form.css` 的 `.hb-*` 类，不新建 CSS 文件、不改 `hub-bind-form.css`、不写内联 `style={{`、不写死颜色。
  - **本片不推翻任何旧断言**（逐条核查见「Repository facts → 门禁与既有测试的核查结论」）：T045 S03/S10 与 T051 S07 都是包含式核对，拆内外层后那些字面量仍在同一个文件里；两份门禁的探针与两份既有包内测试里唯一的「再开」用例两次打开之间 props 不变，按当时的 props 重算结果相同。**既有包内测试与门禁基准文件一个字都不用改**（不在 allowed_modified_files 里）。
  - **数据与格式不变**：请求路径与正文（`POST /api/v1/hub/roles/<post>`、`POST /api/v1/roles/<role>`）、`WriteArgs` 的键、预览与执行共用同一份 `writeArgs` 规则、`WriteScenario` 的值集合、`src/mock` 的 JSON 份数（14）、`src/pages` 顶层 `*Page.tsx` 份数（9）——一个都不变。
- **写法钉死**（门禁按源码文本查这几处，逐字照抄）：
  1. `desktop/web/src/writes/HubBindForm.tsx`：导出仍是 `export function HubBindAction(` 与 `export function HubUnsetAction(`；两个原因句常量逐字在位；标题仍是 `改绑定：${postLabel}`（变量名 `postLabel` 不改）；两个 `Select` 的 label 仍是「主绑定」与「替补」，空值选项仍是「不设替补」；`useLivePreview(` 与 `'hub.set'`、`'hub.unset'` 在位；`<WriteFlow flow={flow} />` 在位；[确认…] 的门控里能看到 `current`、`result.ok`、`onClose`；从 `../api` 只 `import type`；运行时引 `{ hubChangeLines } from './hubChangeLines'`；`import './hub-bind-form.css';` 之后**不再有任何** `import … from './…'`；全文不出现 `aria-label`；代码（去注释后）里不出现 `step-low`；不写死颜色；不出现禁词；不跨层引 `src/pages`。
  2. `desktop/web/src/writes/RoleBindForm.tsx`：导出仍是 `export function RoleBindAction(` 与 `export interface RoleBinding`；原因句常量逐字在位；标题仍是字面量 `改绑定：${roleLabel}`（变量名 `roleLabel` 不改）；`label="模式"`、`label="profile"`；按钮文字恰为「更改…」且有 `variant="secondary"` 与 `size="sm"`；`DisabledAction` 在位；`useLivePreview(` 与 `'role.set'` 在位；`<WriteFlow flow={flow} />` 在位；门控里能看到 `current`、`result.ok`、`onClose`；`import './hub-bind-form.css';` 之后**不再有任何** `import … from '../…'`；只引 `hub-bind-form.css` 这一个样式表；不写 `style={{`；不写死颜色；不出现禁词；不跨层引 `src/pages`。
  3. **两个文件都不新增 import**：既有的 import 行一行不动（内层组件与外层组件在同一个文件里，不另起文件）。
  4. **内层组件的名字**：HubBindForm 里内层叫 `HubBindFormDialog`，RoleBindForm 里内层叫 `RoleBindFormDialog`；两个都不导出。外层继续叫 `HubBindDialog` / `RoleBindDialog`（不导出，门禁与测试都没按名字找它们）。
  5. **内层与外层的分工**（两个文件同一种写法）：
     - 外层组件（`HubBindDialog` / `RoleBindDialog`）：只做三件事——`const { start, flow } = useWriteFlow(reload);`、渲染 `{open && <内层 … />}`、渲染 `<WriteFlow flow={flow} />`。**`useWriteFlow` 与 `<WriteFlow flow={flow} />` 必须在外层**（表单关掉时写流程还要继续渲染确认框、执行、重读、终态）。
     - 内层组件：接收与今天相同的字段 props 加 `onClose` 与 `onConfirm`；里面放预填计算、两个 `useState`、候选联动、参数组装、`useLivePreview`、门控、底部渲染与 `<Dialog open onClose={onClose} title={…} footer={…}>`。
     - `canPreview` 去掉 `open &&`（内层存在即表示表单开着），其余条件照旧。
     - [确认…] 的次序照旧：先 `onClose()`（内层随之卸载），再 `start(spec)`。
  6. **注释**：内层组件「只在打开时挂载、写流程留在外层」这一处不明显的约束值得一句注释；文件头原有的两行说明与各处的解释性注释照旧，不要为搬动代码改写注释的意思。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t052_baseline.py`（只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/writes/HubBindForm.tsx` 拆内外层**（照「写法钉死」第 5 条）：
   - 外层 `HubBindDialog`：`useWriteFlow(reload)` + `{open && <HubBindFormDialog … />}` + `<WriteFlow flow={flow} />`；[确认…] 的次序仍是先 `onClose()` 再 `start(spec)`。
   - 内层 `HubBindFormDialog`：把今天的预填计算（`initialMain`／`initialFallback`）、两个 `useState`、`fbCandidates`／`fbEnabled`、`buildArgs`、`useLivePreview('hub.set', buildArgs(), canPreview)`、`confirmEnabled`、`onMainChange`、`renderBottom` 与 `<Dialog …>` 原样搬进来；`canPreview` 去掉 `open &&`。
   - 出口不变：`HubBindAction` 照旧一直挂外层对话框（`open` 仍由入口的 `useState(false)` 管），`HubUnsetAction` 一个字不动；两个原因句常量、标题、标签、按钮文字、类名一个不动；不新增 import。
3. **`desktop/web/src/writes/RoleBindForm.tsx` 同样拆**（照「写法钉死」第 5 条）：
   - 外层 `RoleBindDialog`：`useWriteFlow(reload)` + `{open && <RoleBindFormDialog … />}` + `<WriteFlow flow={flow} />`。
   - 内层 `RoleBindFormDialog`：`options = modeOptionsOf(modes, candidates)`、`initialMode`／`initialProfile`、两个 `useState`、`headless`、`buildArgs`（`host` 与 `cadence_seconds` 的原样传回规则一字不改）、`useLivePreview('role.set', buildArgs(), canPreview)`、`confirmEnabled`、`renderBottom` 与 `<Dialog …>`；`canPreview` 去掉 `open &&`。
   - 模块级的 `modeOptionsOf` 留在模块层（`RoleBindAction` 判禁用时也要用）；`RoleBindAction` 的禁用分支与原因句规则一字不动；标题仍是 `改绑定：${roleLabel}`；不新增 import。
4. **新建 `desktop/web/tests/writes-bind-reopen.test.tsx`**（不许 `skip`/`only`/`todo`——`tests/test_gate_t002_baseline.py:1496` 会扫全部 `*.test.*`；测真实实现，不把业务逻辑抄一份进测试；不 mock 被测组件）：
   - 用 `@testing-library/react` 的 `render` 直接渲染 `HubBindAction` / `RoleBindAction`（不挂整页 App），用 `rerender` 换 props 来模拟「重读之后 props 变了」；用 `setLiveClientForTests` 注入假服务记录预览请求与写请求（照 `desktop/web/tests/writes-role-bind.test.tsx` 的写法）。
   - **HubBindForm 组**：
     - (a) 改了主选（改成非 quizs，替补清空并禁用）、点 [取消]、再开：主选与替补回到现有绑定，替补可选。
     - (b) `rerender` 把 `mainProfile` 换成另一个候选后再开：按新绑定预填，**发出的预览请求的 args 里 `profile` 是新绑定**。
     - (c) 现有主绑定原来不在候选里（预填的是第一个候选），`rerender` 把它加进候选后再开：预填现有主绑定；**断言预览请求的 args 里 `profile` 是现有主绑定，且 [确认…] 可点**。
     - (d) 点 [确认…]：表单关上、写确认框开上（标题 `改绑定 <post>？`），确认后发 `POST /api/v1/hub/roles/<post>`，出成功轻提示，`reload` 被调用；`rerender` 成新绑定后再开，按新绑定预填。
     - (e) 再开时底部先显示「预览中…」、[确认…] 灰着，新预览回来后才可点，预览请求次数比上次多一次。
   - **RoleBindForm 组**（同形，五条）：
     - (a) `execution` 把 profile 改成另一个、[取消]、再开：回到现有 profile；`planning_review` 把模式改成无头、[取消]、再开：回到交互式宿主（没有 profile 下拉）。
     - (b) `rerender` 把 `binding.profile` 换掉后再开：按新绑定预填，预览请求的 args 里 `target` 是新 profile。
     - (c) `planning_review` 起初 `candidates=[]`（模式里没有无头、help 是原因句）；`rerender` 给候选后再开，选「无头」，**预览请求的 args 里 `target` 是第一个候选，且 [确认…] 可点**。
     - (d) 点 [确认…]：表单关上、写确认框开上（标题 `改角色绑定 <role>？`），确认后发 `POST /api/v1/roles/<role>`，出成功轻提示，`reload` 被调用；`rerender` 成新绑定后再开，按新绑定预填。
     - (e) 同 HubBindForm 的 (e)。
   - **测试陷阱（必须照办）**：受控 `select` 的 value 不等于任何 option 时，react-dom 会把第一个未禁用的 option 设成 selected（DOM 上 `select.value` 读出第一项，组件状态其实还是空串）。所以 (c) 这类情形**不能只断言 `select.value`**——旧代码那样也过得去；必须断言**预览请求的 args** 与 **[确认…] 可点**。(a)(b) 的旧状态本来就是合法选项，断言 `select.value` 就能区分新旧代码。
   - **等防抖**：用真实计时器 `await sleep(450)` 再 `await flush()`（照现有表单测试的写法），不要用假计时器，也不要把等待拉长（T045／T051 门禁流水线里 `npm test` 的上限是 300 秒）。
   - **每条用例都要在基线代码上失败**（(e) 在基线上表现为立刻显示旧结果、(a)(b)(c) 表现为显示上次的值），在新代码上通过。
5. 跑 Validation commands 里的检查，顺序 **G01 → V04 → V01 → V02 → V03 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近 3000 秒上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
6. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t052_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t052_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V04（必要）：`npm test -- tests/writes-bind-reopen.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py -q` · cwd：仓库根 · 超时：3000s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：两个表单每次打开都按**当时**的 props 重新预填，三条情形都对（改字段取消后再开回到现有绑定；外部改了绑定、重读后 props 变了再开按新绑定预填；表单早已挂着、后来新增了候选再开按当时的候选预填）；目的：这是站主登记的三个情形，行为一个都不许漏；证据：V04、V01。
- D02：写流程一个字不变——点 [确认…] 先关表单再 `start`，确认框、执行、重读、终态在表单关上之后照常走完（`useWriteFlow` 与 `<WriteFlow flow={flow} />` 留在外层）；请求路径、正文与重读次数照旧；目的：表单关掉不能把写流程一起卸载；证据：V04、V01、G01、R01。
- D03：有意的行为变化落地：再打开时底部先显示「预览中…」、[确认…] 灰到新的预览回来才可点（与第一次打开一样）；表单开着时 props 变了仍不重置用户正在改的字段；目的：去掉「按旧数据显示」这一类问题，同时不动用户手下的输入；证据：V04、V01。
- D04：两个源文件的门禁字面量一个不少（T045 S03/S10 与 T051 S07 的逐条：导出、原因句、标题、标签、`useLivePreview(`、`'hub.set'`／`'role.set'`、`<WriteFlow flow={flow} />`、门控里的 `current`／`result.ok`／`onClose`、不出现 `aria-label`、代码里不出现 `step-low`、不写 `style={{`、css import 之后不再有 import、不写死颜色、不出现禁词、不跨层引 `src/pages`）；目的：这两份门禁是包含式核对，字面量一丢就红；证据：G01、R01。
- D05：其余行为、文字、样式与导出形态一个字不变（导出名与 props 不变；不改入口文件与共享件；不改依赖与锁文件；`src/mock` 仍 14 份 JSON、`src/pages` 顶层仍 9 个 `*Page.tsx`）；目的：这一片只修预填，不许顺手改别的片的地盘；证据：scope、R01、review。
- D06：新增 `desktop/web/tests/writes-bind-reopen.test.tsx`，覆盖 D01–D03 点名的每一项（两个表单各五条），测真实实现，不许 `skip`/`only`/`todo`；情形 (c) 断言预览请求的 args 与 [确认…] 可点（不能只断言 `select.value`）；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V04、V01、review。
- D07：所有修改都在允许集合内（可改 2 个源文件、可新增 1 个测试文件），没有碰 forbidden_paths（`tests/test_gate_t052_*.py` 与其余 50 份门禁基准、既有包内测试、`useWriteFlow.ts`、`useLivePreview.ts`、`components/**`、`shell/**`、`hub-bind-form.css`、入口文件、`package.json` 与锁文件、`ts/packages/ui/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D08：`npm test`、`npm run typecheck`、`npm run build` 全过，51 份既有门禁基准全过；目的：不能为了修预填把别处弄坏；证据：V01、V02、V03、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如两个源文件不是上面写的形状、`useLivePreview`／`useWriteFlow` 的接口变了、`Dialog` 关着时不再 `return null`、`useOverlayFocus` 的焦点语义变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动既有包内测试、任何门禁基准、`useLivePreview.ts`／`useWriteFlow.ts`、`hub-bind-form.css`、入口文件、`package.json` 与锁文件）。
- 门禁端交付的 `tests/test_gate_t052_baseline.py` 与本合同的「写法钉死」一节出现实质冲突（例如它要求标题变量名不是 `roleLabel`、或要求 `canPreview` 保留 `open &&`）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 门禁端交付的本片门禁基准断言了「再打开立刻显示上一次的预览」：停下并报告——那是本片有意去掉的行为（见 Behavior contract 的「有意的行为变化」）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id `t052-desktop-web-bind-form-reopen` 汇总，含返工版本；累计已用 0 次 → 本版留 2 次）
- max_wall_seconds_per_attempt: 9000
- max_wall_seconds_total: 18000（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 18000 秒 ≥ 本版 2 × 9000 = 18000 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 20 分钟；实现两个源文件的内外层拆分 30 分钟；新包内测试十条用例 35 分钟；必要检查（G01、V04、V01、V02、V03、R01；R01 约 40–60 分钟、可分批跑）60 分钟；最终报告 5 分钟；总计约 150 分钟，单轮时限 9000 秒（150 分钟）——总量 18000 秒覆盖本版与一次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D08，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
