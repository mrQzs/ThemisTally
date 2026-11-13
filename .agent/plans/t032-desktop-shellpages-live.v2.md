# TASK: t032-desktop-shellpages-live

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 5964712e488c98c560ff16da2b916a3354714fa9
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端前端的外壳页（`desktop/web/src/shellpages/`）在真外壳窗口里调真的外壳：在新的 `desktop/web/src/shellpages/shellBridge.ts` 里做**唯一**的 `window.themisShell` 读取点（核对接口里的十个成员，核不过当作没有），`useThemisShell` 的取实例顺序改成「Provider 注入 → bridge 给的真实例 → 夹具模式下的内存桩 → 真实模式下一个『外壳不可用』的实例」；真实模式下不创建桩、地址里的 `shell=` 不起作用；真实模式下没有外壳时，**首次启动页与服务状态页**显示「没有连上外壳」（设置页保持现状，见 Non-goals）；夹具模式（vitest 与开发服务器）下现有行为逐条不变。

## Non-goals
- 不改 `desktop/shell/**`（外壳页专用 preload 是 T030 的事）、`ts/**`、`scripts/**`、`docs/**`、`schemas/**`、任何 `tests/test_gate_*.py`。
- 不改 `desktop/web/src/pages/SettingsPage.tsx`（**本片一个字不改**）、`desktop/web/src/shellpages/themisShell.ts`（只放类型）、`shellStub.ts`、`ShellWindow.tsx`、`SettingsView.tsx`、`desktop/web/src/shell/PageFrame.tsx`、`desktop/web/src/App.tsx`。
- **已知不足（本片不做）**：真实模式下没有外壳时，设置页显示的是 PageFrame 的通用出错块（「没有收到服务的回应」），而不是「没有连上外壳」。这是已知不足，留给「主窗口经 `host.openSettings()` 打开设置窗口」的那一片处理。
- 不改 `desktop/web/src/live/**`（真实/夹具的判定只用 T027 已落地的那一处，不另写一套）；不新增 `.d.ts` 类型声明文件。
- 不做服务的真实启停（`startService`/`restartService` 仍是外壳侧的事）、不做 `host.openSettings()`、不做主窗口标题栏的外壳真实值。
- 不拆信封：外壳页 preload 自己拆信封（见「Behavior contract」第二节），前端不判断返回值像不像信封。
- 不新增或升级任何依赖；不改 `desktop/web/package.json` 与 `desktop/web/package-lock.json`。
- 不做真 Electron 窗口的冒烟（门禁端与站主手工做）；不要求构建产物里查不到桩的代码。

## Repository facts
- 基线：`344b5d09d69e47e7a29d4833bb65c2e1fab00332`（T027 已落地，`desktop/web/src/live/` 存在）。本片只动 `desktop/web/`。
- **模式判定（规划假设 1–4 的答案，已在新基线核对）**：
  - `desktop/web/src/live/mode.ts` 导出 `liveModeIsReal(): boolean`，实现是模块级常量 `BUILD_MODE`（取自构建期常量 `__THEMIS_LIVE_MODE__`，兜底值 `'unknown'`）比 `'themis-live-real'`；同文件还导出 `liveClient()`、`setLiveClientForTests()`、type `LiveClient`。
  - `desktop/web/vite.config.ts` 是函数形式 `defineConfig(({ command }) => ({ ... define: { __THEMIS_LIVE_MODE__: JSON.stringify(command === 'build' ? 'themis-live-real' : 'themis-live-fixture') } ... }))`：**只跟 command 走，不看 NODE_ENV，也不看页面由谁托管**。因此 vitest 与 dev server 判夹具；任何 `vite build` 产物判真实；`themis-shell://app/` 窗口里也判真实（规划假设 1 的隐患排除）。
  - `liveModeIsReal` 是**运行时函数**：桩的代码会留在产物里，**不要求产物里找不到桩**；「真实模式下不创建桩」由单元用例证明（规划假设 4 的答案）。
  - `desktop/web/tests/live-mode.test.ts`（T027 的）只测「缺省为夹具」与 `setLiveClientForTests` 注入，**没有**把判定切成真的的手法 → 本片用 `vi.mock` 局部替换 `liveModeIsReal`（规划假设 3 的答案）。
- **判定模块的导入路径**：`desktop/web/src/live/mode.ts`。从 `src/shellpages/` 引入写 `'../live/mode'`，**不以 `/api` 结尾**（规划假设 2 通过）。`mode.ts` 自己有 `import type { Envelope } from '../api'`（类型导入，在 `src/live/` 内），T012 的 `api_import_problems` 只看被点名文件的直接 `from '…'` 说明符，不追传递依赖 → 不撞 `api_import_problems` 与 `shellpages-static` 的 api 导入检查。
- **T030 尚未落地（本基线的实况）**：`desktop/shell/preload.js` 仍只有一次 `contextBridge.exposeInMainWorld("themisHost", …)`（五个成员），`desktop/shell` 下没有 `themis-shell://` 协议处理与外壳页专用 preload。外壳页 preload 的返回形状按站主定的约定成文（见「Behavior contract」第二节），**以 T030 落地为准**；T030 若改了约定，由协调人转告执行端，执行端把冲突写进执行报告的 `contract_conflicts`，不要越界改 `desktop/shell/**`。
- **站主已核实的仓库外事实（照事实用）**：真 electron 44.9.0 窗口，`contextIsolation` 与 `sandbox` 都开。① 暴露对象的函数成员在主世界里 `typeof` 是 `function`，`on` 返回的退订函数在主世界里也是函数、调用它会执行 preload 里的那个函数，主世界传进去的监听函数 preload 能调用；② 每次读到的是同一个对象，**这个对象是冻结的、不能往上挂缓存属性**，但可以当 WeakMap 的键；③ 被拒绝的 Promise 过桥后**只保留 Error 的 message**（不要指望 stack/name/code）。
- **设置页的既有断言与现状（本片一个字不改，已逐字核对）**：
  - `desktop/web/tests/shellpages-settings.test.tsx:106-112` 的用例名是「getState 被拒：通用出错块『没有收到服务的回应』」，断言 `data-page-state` 是 `error` 且页面文本含「没有收到服务的回应」。
  - `tests/test_gate_t012_baseline.py:2671-2678` 的过渡用例逐字同上（另外断言 `data-page="settings"` 为 null）。
  - `tests/test_gate_t012_baseline.py:3763` 的 docstring 里留着旧措辞「C1：不再断言占位文字」，那是 T012 自己的文档措辞，与上面那条实际断言不一致；**`tests/**` 本片禁改，不动它**（门禁端另发返工时再议）。
  - `desktop/web/src/pages/SettingsPage.tsx` 现状：`load` 是 `useCallback` 包的 `shell.getState().then(...)`（成功时包成 ok 信封），**reject 不接住、直接冒给 `PageFrame`**，由 PageFrame 显示通用出错块「没有收到服务的回应」。**本片保持这个现状**：不改该文件，不实现「拒绝转成 ok:false 信封」，也不让设置页显示「没有连上外壳」。
- **门禁事实（`tests/test_gate_t012_baseline.py`，新基线上核对）**：
  - `SHELLPAGES_FILES` 19 个文件 + `mock/shellpages-scenarios.ts` 组成 `NEW_SOURCE_FILES`；`forbidden_api_problems` 扫的是 `NEW_SOURCE_FILES` 里的 ts/tsx + `App.tsx` + `SettingsPage.tsx`，禁止 `window.themisShell` 的读取与声明、`declare global`、`themisHost`（`strip_ts_comments` 剥注释，**字符串也算**）。**`shellBridge.ts` 不在这份名单里** → 全局声明放它那里。
  - `api_import_problems` 只查这些文件的直接导入说明符是否匹配 `(^|/)api(\.ts)?$`。
  - `settings_source_problems`（`test_d07_settings_page_and_view_source`）：`SettingsPage.tsx` 要用 `PageFrame`、title 是「设置」、description 是「设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置」、load 要 `useCallback` 且依赖只有 `[shell]`、**不许 `async`/`await`**、不传 `isEmpty`、`command` 里要有 `themisShell.getState`、要渲染 `<SettingsView`。**本片不改这个文件 → 这条照旧成立。**
  - 过渡断言（`test_transitional_` 开头）在新基线上仍是 **17 条**：`test_transitional_d01_scenario_fixture_values`、`d02_stub_fixture_values`、`d03_entry_addresses`、`d03_hashchange_between_windows`、`d03_navigate_shell_is_synchronous`、`d04_first_run_states`、`d05_first_run_errors_and_actions`、`d05_copy_results`、`d06_service_status_content`、`d06_service_status_restart_and_navigate`、`d07_settings_structure`、`d07_repos_group`、`d07_runtime_and_usage_groups`、`d07_load_is_a_stable_reference`、`d08_appearance_without_provider`、`d09_about_and_external_link`、`d08_theme_sync_through_app`。前端两条「（过渡）」用例：`desktop/web/tests/page-app.test.tsx:91`、`desktop/web/tests/readonly2-app.test.tsx:106`。**本片一条也不推翻**（vitest 是夹具模式，桩路径逐条不变；`d07_load_is_a_stable_reference` 靠引用稳定保住；设置页保持现状正是其中 `d07_settings_structure` 所断言的那条）。
  - `wiring_problems`（K20）只查 css 能不能从 `App.tsx` 或 `SettingsPage.tsx` 走到，以及点名的几条 import；多一条 `./shellBridge`（ts 文件）不影响结论。
- **包内静态测试（`desktop/web/tests/shellpages-static.test.ts`，扫整个 `src/shellpages/`，新文件也算）**：
  - 网络词那条**逐行扫原文、不剥注释**：`fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词一律不许出现 → `shellBridge.ts` **连注释里都不能写这四个词**。
  - 危险 HTML、禁用调用、`role=status`、`data-theme`、内联 style、`localStorage`/`sessionStorage`/`themisHost`/`ServerIcon` 那条**剥了注释再扫**（字符串算）→ 错误文案里不能写 `themisHost`。
  - api 导入那条按 `from '…'` 的说明符匹配 `(^|/)api(\.ts)?$` → 从 `src/live` 引入的路径不能以 `/api` 结尾。
  - 文件名不许叫 `*Page.tsx`、`*Showcase.tsx`、`DiffView*`、`LogFollow*`；`SettingsView` 不许拆分。
- **`desktop/web/tests/cleanup2-static.test.ts`**：`copyText` 与 `COPY_RESULT_TEXT` 的定义只在 `src/components/copyText.ts`、`CopyNote` 只在 `src/components/CopyNote.tsx`、三个共用图标（`ArrowRightIcon`/`FileTextIcon`/`ExternalLinkIcon`）只在 `src/icons/index.tsx`；三条禁用文字「这个环境没有剪贴板接口」「已复制」「复制失败」不许出现在别处 → 新文件不得定义这些名字、不得含这些文字。
- **T027 的构建核对（既有脚本，不改）**：`desktop/web/scripts/check-live-build.mjs` 用本地 vite 按 `NODE_ENV` 未设 / `development` / `test` 三种取值各构建一次，断言产物含 `themis-live-real`、不含 `themis-live-fixture`、含传输层特征串 `same-origin`，全过打印 `LIVE_BUILD_OK 3/3`。T027 的门禁（`tests/test_gate_t027_baseline.py`）钉着这个脚本与 `vite.config.ts` 的写法 → 本片一个字都不改这两处。
- **工具链与锁文件**：`desktop/web/package.json` —— vite 5.4.11、vitest 2.1.8、react 18.3.1、typescript 5.6.3；`scripts`：`test` = `vitest run`、`build` = `tsc --noEmit && vite build`、`check:contract` = `node scripts/token-contract.mjs`；锁文件 `desktop/web/package-lock.json`（不动）。`desktop/web/tsconfig.json` 的 `include` 只有 `src` 与 `vite.config.ts`（`strict: true`）→ **新写的 `src/` 代码要过 `tsc --noEmit`**；`tests/` 下的测试文件不在 tsconfig 的 include 里（不被构建的类型检查覆盖，但自己写对）。
- **基线检查（执行端在 Step 1 复核，合同不代跑）**：`npm test`（cwd `desktop/web`）在基线上应当全过；`python -m pytest tests/test_gate_t032_baseline.py -q` 在基线上应当失败（门禁文件由门禁端写、内核做成基线提交）；`python -m pytest tests/test_gate_t001_baseline.py … tests/test_gate_t028_baseline.py -q` 在基线上应当全过。**规划端与合同端都没有实跑过这些命令**（工作区没有 `desktop/web/node_modules`），不要把它们当成已验证的事实。
- **上一轮 attempt-001 的产物（执行端在本版接着做）**：attempt-001 改了 `desktop/web/src/pages/SettingsPage.tsx`、`FirstRunView.tsx`、`ServiceStatusView.tsx`、`shellContext.tsx`，新增 `shellBridge.ts` 与两份新测试。**本版要撤销的只有设置页那一块**（见 Steps 第 0 步）；其余实现保留。

## Scope
- allowed_modified_files:
  - desktop/web/src/shellpages/shellContext.tsx
  - desktop/web/src/shellpages/FirstRunView.tsx
  - desktop/web/src/shellpages/ServiceStatusView.tsx
- allowed_new_files:
  - desktop/web/src/shellpages/shellBridge.ts
  - desktop/web/tests/shellpages-live-bridge.test.tsx
  - desktop/web/tests/shellpages-live-bridge-static.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t032_*.py
  - tests/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/shellpages/themisShell.ts
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/live/**
  - desktop/web/tests/shellpages-static.test.ts
  - desktop/web/tests/cleanup2-static.test.ts
  - desktop/shell/**
  - ts/**
  - scripts/**
  - docs/**
  - schemas/**
- dependency_changes: forbidden（不新增、不升级、不删除依赖；`desktop/web/package.json` 与 `package-lock.json` 一个字节都不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、模式判定只用 T027 那一处

- 真实与夹具的判定只用 `desktop/web/src/live/mode.ts` 的 `liveModeIsReal()`，从 `src/shellpages/shellContext.tsx` 用 `'../live/mode'` 引入（路径不以 `/api` 结尾）。
- `liveModeIsReal()` **每次调用 `useThemisShell` 时调用一次**，判定结果**不在模块加载时缓存**（这样 `vi.mock` 局部替换它才生效，行为也跟构建期常量一致）。
- 语义：vitest 与开发服务器里为假（夹具）；任何 `vite build` 产物里为真（真实），与 `NODE_ENV`、与页面由谁托管都无关。

### 二、`desktop/web/src/shellpages/shellBridge.ts`（唯一读取点）

- 全局声明只放这一个文件：`declare global { interface Window { themisShell?: unknown } }`（属性可选、类型 `unknown`；不许放 `.d.ts` 文件里）。
- 导出（名字照此，不要另起）：
  - `SHELL_MEMBERS`：十个成员名的只读数组，逐字是 `getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`。
  - `shellBridgeInstance(): ThemisShell | null`——见下。
  - `unavailableShell(): ThemisShell`——「外壳不可用」实例，模块级单例。
  - `resetShellBridge(): void`——清掉包装缓存，给测试用（不清单例；不清也由 WeakMap 的键自然失效）。
- `shellBridgeInstance()` 的行为：
  1. **每次调用都重新读一次** `window.themisShell`（不在模块加载时缓存「有没有外壳」这个结论；缓存的是包装）。
  2. 读到的值不是对象（`undefined`、`null`、非对象）→ 返回 `null`。
  3. 十个成员里**任何一个不在**，或者**不是函数**（`typeof !== 'function'`）→ 返回 `null`（当作没有外壳）。
  4. 十个成员齐全 → 返回该对象对应的**包装实例**。
- 包装与缓存：
  - 包装用 `WeakMap` 按**原对象**缓存（站主核实：原对象被冻结，不能往上挂属性；可以当 WeakMap 的键）。同一个原对象**永远返回同一个包装引用**；不同的原对象返回不同的包装。
  - 不许把缓存挂在 `window.themisShell` 或任何原对象上（它可能被冻结）。
  - 包装**只做转发，不拆信封、不包一层**：九个方法原样调用原对象的同名方法并把返回的 Promise 原样交出去。**不做「返回值像不像信封」的判断**——外壳页 preload 自己拆信封（`ok` 为真时 resolve `value`，否则 reject `new Error(reason)`）。T030 若改成别的约定，由协调人转告，执行端把冲突写进执行报告的 `contract_conflicts`，不要越界改 `desktop/shell/**`。
  - `on(event, listener)`：转发给原对象的 `on`；它返回函数时，包一层「调用它即退订」的函数返回；返回的不是函数时返回空退订函数（不抛错、不返回 Promise）。
  - `openExternal(url)`：转发原对象的 `openExternal`；**若被拒且 `Error.message` 逐字是 `cancelled`，当作正常结束**（resolve，不显示错误、不算失败）；其它错误原样 reject。
  - 错误文案只用 `Error.message`（过桥后只剩 message；不要指望 stack/name/code，也不要自己拼前缀）。
- 「外壳不可用」实例（`unavailableShell()`）：
  - 九个方法（`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`）都返回**被拒的 Promise**，被拒的 `Error` 的 `message` 逐字是 **`没有连上外壳`**。
  - `on` **同步**返回空退订函数（`() => {}`）：不调 listener、不抛错、不返回 Promise（页面挂载时就会调它）。
  - **模块级单例**：多次调用返回同一个引用（引用稳定）。

### 三、`desktop/web/src/shellpages/shellContext.tsx`

- `useThemisShell(windowDefault: string): ThemisShell` 的顺序**逐条照此**：
  1. 有 `ThemisShellProvider` 注入的实例 → 用它（现有行为不变）。
  2. 否则 `shellBridgeInstance()` 非 `null` → 用它（真实例；**夹具模式下也一样优先**）。
  3. 否则 `liveModeIsReal()` 为假（夹具模式）→ `stubFor(scenarioFromHash(windowDefault))`（现有桩，场景与缓存行为一字不改）。
  4. 否则（真实模式且没有外壳）→ `unavailableShell()`。
- 真实模式下**不调用 `stubFor`**（不创建桩）、**不读地址里的 `shell=`**（场景参数不生效）。
- 导出名与行为不变：`ThemisShellProvider`、`useThemisShell`、`resetShellStubs`；`resetShellStubs` 仍负责 dispose 桩并清空桩缓存。
- 本文件的代码与字符串里**不许**出现 `window.themisShell`、`globalThis.themisShell`、`declare global`、`themisHost`（注释不算，字符串算）。

### 四、`desktop/web/src/pages/SettingsPage.tsx`（**本片不改**）

- **这个文件一个字都不改**（在 `forbidden_paths` 里）。设置页的现状照旧：
  - `load` 仍是 `useCallback` 包的 `shell.getState().then(...)`，依赖只有 `[shell]`，**不用 `async`/`await`**，不传 `isEmpty`，`command` 仍是 `['themisShell.getState']`，仍渲染 `<SettingsView>`（T012 的 `settings_source_problems` 照旧通过）。
  - 成功时照旧返回 `{ ok: true, exit_code: 0, data, output: [], messages: [], command: ['themisShell.getState'], elapsed_ms: 0 }`。
  - **`getState` 被拒时不接住**：reject 照旧冒给 `PageFrame`，由 PageFrame 显示通用出错块「没有收到服务的回应」（`desktop/web/tests/shellpages-settings.test.tsx:106-112` 与 `tests/test_gate_t012_baseline.py:2671-2678` 逐字断言的就是这个）。
- **本片不做**：把拒绝转成 ok:false 信封（`exit_code: 1`、`data: null`、`command: ['themisShell.getState']`、错误消息塞进 `messages`）、设置页侧的 `操作失败` 兜底、让设置页显示「没有连上外壳」、改 `PageFrame.tsx`。**`PageFrame.tsx` 一个字没改。**

### 五、`desktop/web/src/shellpages/FirstRunView.tsx`

- `shell.getState()` 被拒时：记下错误消息（`state` 保持 `null`，步骤列表照旧为空），在步骤列表 `<ol className="tt-fr__steps">` **之后、底栏之前**渲染一个错误块：`<div className="tt-fr__err" role="alert">{错误消息}</div>`。
  - **复用既有的 `tt-fr__err` 类，不新增 css 类**；**不加 `data-step-error` 属性**（避免与门禁探针的四步序号混淆）；不加 `role=status`。
  - 错误消息 = `Error.message`；为空或不是字符串时用 `操作失败`；外壳不可用时逐字是 `没有连上外壳`。
- 所有对外壳的调用都要**接住拒绝**，不许产生未处理的 reject：`startService`（两处：自动启动与「重新启动」）、`pickRepo`/`pickPython`/`pickKit`（三处）。失败时把错误消息显示在上面的同一个错误块位置（自动启动失败也显示）。
- 夹具模式（桩从不 reject）下**现有行为逐条不变**：四步状态、六种错误、自动启动恰一次、[进入] 的禁用态、复制三种结果、退出码 1 的禁用按钮都不动；`role="alert"` 的个数在夹具下不变（桩不 reject，错误块不渲染）。

### 六、`desktop/web/src/shellpages/ServiceStatusView.tsx`

- `shell.getState()` 被拒时：把错误消息显示在**说明行的位置**——`<p className="tt-ss__note">` 有错误时用错误消息替换默认说明（`stoppedNote(...)`）。
  - **不加 `role="alert"`**（照这个文件的头注释）；**不新增 css 类**；不加 `role=status`。
  - 错误消息 = `Error.message`；为空或不是字符串时用 `操作失败`；外壳不可用时逐字是 `没有连上外壳`。
- `shell.restartService()` 被拒时：**复位「正在重启…」**（`restarting` 置回 `false`，按钮不再显示 loading），并把错误消息显示在上面的说明行位置。
- `shell.on('service-state', …)` 的退订函数照旧在卸载时被调用（视图的 effect 仍 `return off`）。
- 夹具模式下的现有行为逐条不变（退出码 1/2/3、重启后跳回、推送 exited 换新）。

### 七、事件与退订

- 真实例的 `on('service-state', listener)` 返回的退订函数在组件卸载时被调用（首启页与服务状态页的 effect 都 `return off`）。
- 桩的退订行为不变（现有 `shellpages-*.test.*` 照旧通过）。
- 「外壳不可用」实例的 `on` 同步返回空退订函数，页面挂载与卸载都不崩。

### 八、静态约束（自检清单，逐条都能被现有门禁与新增静态用例核到）

- `shellBridge.ts` 里**连注释都不许**出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个整词。
- `src/shellpages/**` 不导入 api 模块（从 `src/live` 引入的路径不以 `/api` 结尾）。
- 新文件名不叫 `*Page.tsx`。
- `shellContext.tsx`、`ShellWindow.tsx`、`SettingsPage.tsx`、`FirstRunView.tsx`、`ServiceStatusView.tsx` 的代码与字符串里不出现 `window.themisShell`、`globalThis.themisShell`、`declare global`、`themisHost`（剥注释后扫，字符串也算）。
- `themisShell` 的全局声明**只**在 `shellBridge.ts`（`src/live/transport.ts` 里现有的 `declare global` 是给 `themisHost` 的，不许动，也不在本条的判定面内——静态用例只判「`themisShell` 的全局声明」与「`window.themisShell` 的读取」）。
- `cleanup2-static` 的禁用文字（`这个环境没有剪贴板接口`、`已复制`、`复制失败`）与 `copyText`/`COPY_RESULT_TEXT`/`CopyNote`/三个共用图标的定义唯一性不受影响（新文件不得定义它们）。
- T014 钉着 `desktop/web/tests/shellpages-static.test.ts` 的用例数下限 → **本片不改那份测试**。

### 九、并发、取消与兼容性

- 并发：外壳实例的取用没有并发写；`WeakMap` 缓存与桩缓存都不是并发敏感的。
- 取消：本片没有可取消的长请求；用户取消 `openExternal` 是 `cancelled`（当作正常结束）。
- 兼容性：`ThemisShell` 接口的十个成员与类型**一个字不改**；`useThemisShell` 的签名与导出名不变；现有 `shellpages-*.test.*` 一条不改、全过；`?mock=` 与 `shell=` 在夹具模式下行为不变；**设置页的既有行为与既有断言一条不动**。

### 十、测试（本片新增两份文件）

- `desktop/web/tests/shellpages-live-bridge.test.tsx`（行为）：
  1. **假外壳优先于桩**：往 `window` 上放一个十成员齐全的假 `themisShell`，经 App 打开首次启动页与服务状态页、单独渲染 `SettingsPage` → 调到的是**假对象**（假对象的 `getState` 被调用），**桩没有被创建**（用 `vi.mock` 包住 `../src/shellpages/shellStub` 的 `createShellStub` 计调用次数，为 0；手法照 `shellpages-isolation.test.tsx` 包 api 的样子）。
  2. **成员不全当作没有**：假对象缺一个成员、或某个成员不是函数 → 当作没有，回到夹具桩（`createShellStub` 被调用，页面显示桩的内容）。
  3. **卸载退订**：卸载组件时，假 `on` 返回的退订函数被调用一次。
  4. **真实模式下没有外壳**：把 `liveModeIsReal` 局部替换成真（`vi.mock('../src/live/mode')`，工厂里保留其余导出原样、把 `liveModeIsReal` 换成受用例控制的开关、把 `liveClient` 换成 `() => null` 以保证零请求）→ **不创建桩**（`createShellStub` 调用次数 0）、地址里的 `shell=` 不起作用、**首启页与服务状态页显示 `没有连上外壳`**；设置页不在本片的断言面内（它的 `getState` 被拒时照旧由 PageFrame 显示通用出错块，**不要断言它显示「没有连上外壳」，也不许写任何设置页信封断言**）。
  5. 引用稳定：同一个假对象两次取到的实例是同一个引用；「外壳不可用」实例两次取到也是同一个引用。
  6. `afterEach` 删掉 `window.themisShell`、复位模式开关、`resetShellStubs()`、`cleanup()`。
  - 不许写 `skip`/`only`/`todo`；不许把业务逻辑抄一份进测试（断言页面行为与调用次数，不复制实现）。
- `desktop/web/tests/shellpages-live-bridge-static.test.ts`（静态）：递归扫 `desktop/web/src` 下的 `.ts`/`.tsx`，剥掉注释后断言 `window.themisShell` / `globalThis.themisShell` 的读取与 `themisShell` 的全局声明**只出现在** `src/shellpages/shellBridge.ts`；并断言 `shellBridge.ts` 里没有那四个网络词整词。
  - 只断言「`themisShell` 的声明与读取」，**不断言别的文件没有 `declare global`**（`src/live/transport.ts` 里有一份给 `themisHost` 的）。

## Steps
0. **撤销上一轮设置页那一块（本版的唯一增量）**：若工作区里已经有上一轮 attempt-001 的改动，把 `desktop/web/src/pages/SettingsPage.tsx` 恢复成基线内容（`load` 是 `useCallback` 包的 `shell.getState().then(...)`、依赖 `[shell]`、不接住 reject），并把新增测试里**设置页信封那几条断言**删掉（首启页/服务状态页/bridge 的其余用例与实现全部保留）。若工作区是干净的基线，就直接做下面第 1–8 步，**不要**实现设置页信封那件事。
1. **读基线**：读 `desktop/web/src/live/mode.ts`、`desktop/web/vite.config.ts`、`desktop/web/src/shellpages/{themisShell.ts,shellContext.tsx,shellStub.ts,ShellWindow.tsx,FirstRunView.tsx,ServiceStatusView.tsx,SettingsView.tsx}`、`desktop/web/src/pages/SettingsPage.tsx`（只读，不改）、`desktop/web/src/shell/PageFrame.tsx`、`desktop/web/tests/{shellpages-static.test.ts,cleanup2-static.test.ts,shellpages-isolation.test.tsx,live-mode.test.ts,shellpages-settings.test.tsx}`、`desktop/web/scripts/check-live-build.mjs`、`desktop/web/package.json`、`desktop/web/tsconfig.json`、`tests/test_gate_t012_baseline.py`（禁词名单、`api_import_problems`、`settings_source_problems`、`wiring_problems`、17 条 `test_transitional_*`）、`tests/test_gate_t027_baseline.py`（`vite.config.ts` 与构建脚本的钉法）。确认符号与形状与本文一致；**不一致就停下并报告**，不要照抄本文的行号。
2. **写 `desktop/web/src/shellpages/shellBridge.ts`**：照「Behavior contract」第二节实现（全局声明、十成员核对、WeakMap 包装缓存与转发、`cancelled` 当正常结束、「外壳不可用」单例、`resetShellBridge`）。注意：文件里**连注释都不许**出现 `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket`；不写 `declare global` 之外的任何全局类型；不导入 api 模块。
3. **改 `desktop/web/src/shellpages/shellContext.tsx`**：照第三节改 `useThemisShell` 的四条路径；引入 `'../live/mode'` 的 `liveModeIsReal` 与 `'./shellBridge'` 的 `shellBridgeInstance`/`unavailableShell`；导出名与 `resetShellStubs` 行为不变；文件里不出现 `window.themisShell`/`declare global`/`themisHost`。
4. **改 `desktop/web/src/shellpages/FirstRunView.tsx`**：照第五节加错误块（`tt-fr__err` + `role="alert"`、不加 `data-step-error`）并给所有外壳调用接住拒绝。
5. **改 `desktop/web/src/shellpages/ServiceStatusView.tsx`**：照第六节在说明行位置显示错误、`restartService` 被拒时复位「正在重启…」、不加 `role=alert`、不新增 css 类。
6. **写两份新测试**：照「Behavior contract」第十节写 `desktop/web/tests/shellpages-live-bridge.test.tsx` 与 `desktop/web/tests/shellpages-live-bridge-static.test.ts`；不写 `skip`/`only`/`todo`；测试里不复制实现；**不写设置页信封相关的断言**。
7. **跑检查**：跑 Validation commands 里与改动相关的每一条（V01–V04 至少各跑一次，G01/R01 按时间跑），把命令与结果写进执行报告。
   - **两条硬规矩**：① 遇到合同与既有测试（或门禁）冲突时**不要越界改范围外的文件**：把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），然后继续做范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`，也不许改 `desktop/web/src/pages/SettingsPage.tsx` 或现有的 `desktop/web/tests/shellpages-*.test.*`。② 临时文件不许写到 `/tmp` 这类固定路径：照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；构建产物 `dist/` 已被 `.gitignore` 忽略，不要提交。
8. **写执行报告**：逐项说明 D01–D13，末尾附执行说明规定的 JSON 代码块。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V03（必要）：`node scripts/check-live-build.mjs` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`LIVE_BUILD_OK 3/3`
- V04（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t032_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：G01 的 `tests/test_gate_t032_baseline.py` 由门禁端写好、内核做成基线提交（基线提交已含该文件），纯基线 `344b5d09d6` 上不存在（G01 在纯基线上应失败；在内核做的基线提交上应失败于「实现没做」的那些断言）。**门禁端另发返工**：凡是断言「设置页把拒绝渲染成信封里的命令与消息」的（T032 门禁的 s06 与 views 探针里设置页那几条）改成断言现状（PageFrame 的通用出错块），s09 的逐字比对名单不动。R01 是 T001–T028 的门禁回归（基线应通过）。V01–V04 需要 `desktop/web/node_modules`，由 Setup 的 `npm ci` 装好；若 Setup 因无网络失败，在执行报告里写明，V01 仍可由 G01/R01 内部的 npm 流水线覆盖。V02 的 `npm run build` 含 `tsc --noEmit`，新代码必须过严格类型检查。V03 是 T027 已有的三取值构建检查脚本（本片不改它），它证明产物在三种 `NODE_ENV` 下都是真实模式；「真实模式下不创建桩」由 V01 的单元用例证明。

## Definition of done
- D01：唯一的读取点与唯一的声明点：整个 `desktop/web/src` 里，`window.themisShell` / `globalThis.themisShell` 的读取与 `themisShell` 的全局声明**只出现在** `src/shellpages/shellBridge.ts`；`shellContext.tsx`、`ShellWindow.tsx`、`SettingsPage.tsx`、`FirstRunView.tsx`、`ServiceStatusView.tsx` 的代码与字符串里都不出现 `window.themisShell`、`globalThis.themisShell`、`declare global`、`themisHost`；`themisShell.ts` 一个字没改；证据：V01（新增静态用例）、G01；目的：外壳接口只有一个入口，将来换 preload 或加第二处读取都能被这条静态用例立刻逮住。
- D02：十成员核对：`window.themisShell` 是 `undefined`/`null`/非对象、缺任一成员、或任一成员不是函数时，`shellBridgeInstance()` 返回 `null`（当作没有外壳）；十成员齐全时返回可用实例；证据：V01、G01；目的：半成品的外壳不能把页面带崩。
- D03：引用稳定与缓存方式：同一个 `window.themisShell` 对象两次读到返回**同一个**实例引用；不同对象返回不同实例；缓存用 `WeakMap`（**不在原对象上挂任何属性**——它可能被冻结）；「外壳不可用」实例是模块级单例，两次取到是同一引用；证据：V01；目的：设置页的 `load` 依赖 `[shell]`，实例变了就会反复重读（`d07_load_is_a_stable_reference` 这条过渡断言也靠它）。
- D04：取实例的顺序：Provider 注入 → bridge 真实例 → 夹具模式的内存桩 → 真实模式的「外壳不可用」实例；**真实模式下不创建桩**（`createShellStub` 调用次数 0）、地址里的 `shell=` 不起作用；夹具模式下 `shell=` 与场景桩的行为逐条不变；证据：V01、G01；目的：装进应用之后任何情况下都不拿桩冒充真数据，而开发与测试环境照旧用桩。
- D05：「外壳不可用」实例：九个方法都返回被拒的 Promise，`Error.message` 逐字是 `没有连上外壳`；`on` **同步**返回空退订函数、不调 listener、不抛错、不返回 Promise；证据：V01、G01；目的：页面挂载时就会调 `on`，它抛错会让首启页与服务状态页直接崩掉。
- D06：「外壳不可用」实例的提示与两个外壳视图的提示（收窄成两件事）：(a) 「外壳不可用」实例本身的行为按 D05：九个方法都以 `Error` 拒绝、`Error.message` 逐字是 `没有连上外壳`；`on` 同步返回空的退订函数、不调用监听、不抛错、不返回 Promise；多次取到是同一个引用。(b) **首次启动页与服务状态页**在真实模式没有外壳时显示这句话（首启页是错误块 `tt-fr__err` + `role="alert"`；服务状态页是说明行 `tt-ss__note`；与 D07 一致）。**设置页不在本条内**：`desktop/web/src/pages/SettingsPage.tsx` 一个字不改，`getState` 被拒时照旧由 `PageFrame` 显示通用出错块「没有收到服务的回应」；本片不做设置页的 ok:false 信封（不做 `exit_code: 1`、`data: null`、`command: ['themisShell.getState']` 的错误信封，也不做设置页侧的 `操作失败` 兜底），**`PageFrame.tsx` 一个字没改**；证据：V01、G01；目的：真实模式下没有外壳时，两个外壳视图要说得清楚是「没连上外壳」；设置页的不足已知并留给主窗口经 `host.openSettings()` 打开设置窗口的那一片（见 Non-goals）。
- D07：两个外壳视图的出错状态：`getState` 被拒时首启页显示错误块（`tt-fr__err` + `role="alert"`、不加 `data-step-error`、不加 `role=status`）、服务状态页在说明行位置显示错误消息（**不加 `role="alert"`**）；`restartService` 被拒时复位「正在重启…」；两个视图里所有对外壳的调用都接住拒绝，**不产生未处理的 reject**；不新增 css 类；证据：V01、G01；目的：接真实外壳后失败要看得见、看得懂，而不是静默吞掉。
- D08：事件：真实例 `on('service-state', …)` 返回的退订函数在组件卸载时被调用（假外壳用例断言退订被调一次）；桩的退订行为不变；证据：V01；目的：窗口关掉后不留悬挂订阅。
- D09：夹具行为逐条不变：现有 `desktop/web/tests/shellpages-*.test.*` 一条不改、全过；桩的场景取值、`resetShellStubs` 的 dispose 与清缓存行为不变；**T012 的 17 条过渡断言与前端两条「（过渡）」用例一条也没推翻**；证据：V01、R01、G01；目的：本片是加一条真实路径，不是把夹具路径换掉。
- D10：静态约束自查：`shellBridge.ts` 连注释里都没有 `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词；`src/shellpages/**` 不导入 api 模块；新文件名不叫 `*Page.tsx`；cleanup2-static 的禁用文字与图标定义唯一性不受影响；`desktop/web/tests/shellpages-static.test.ts` 一个字没改（T014 的用例数下限不受影响）；证据：V01、G01、R01；目的：外壳页与陈列页共用同一套静态规矩，新文件不许开后门。
- D11：构建核对：三种 `NODE_ENV` 取值（未设、`development`、`test`）各构建一次都成功，产物含真实模式标记（`LIVE_BUILD_OK 3/3`），`npm run build`（含 `tsc --noEmit`）与 `npm run check:contract` 都过；**产物里含桩的代码不算失败**（判定是运行时函数）；「真实模式下不创建桩」由单元用例证明；证据：V02、V03、V04；目的：`NODE_ENV` 预设成 development/test 时构建照样成功，产物里的生产标记却是假的——判定不许跟环境变量走。
- D12：门禁与回归：G01 通过、R01 全绿；既有的门禁基准测试文件一条没删没改；证据：G01、R01；目的：别的片的契约不许被这一片削弱。
- D13：范围与卫生：所有改动都在允许集合内（改 3 个文件、新增 3 个文件），`desktop/web/src/pages/SettingsPage.tsx`、`desktop/web/package.json`、`package-lock.json`、`src/live/**`、`desktop/shell/**`、`ts/**`、`scripts/**`、`tests/**` 一个字没动；新测试里没有 `skip`/`only`/`todo`；临时文件照 AGENTS.md 用 `T=$(mktemp -d)` 并在同一命令里 `rm -rf "$T"`；`dist/` 不提交；证据：scope、review；目的：越界改文件会让范围检查直接判负。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `themisShell.ts` 的十个成员变了、`src/live/mode.ts` 不再导出 `liveModeIsReal`、`vite.config.ts` 的模式开关写法变了、门禁的禁词名单变了）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/**`、`desktop/shell/**`、`src/live/**`、`PageFrame.tsx`、`App.tsx`、`themisShell.ts`、`shellStub.ts`、`SettingsView.tsx`、`desktop/web/src/pages/SettingsPage.tsx`、依赖清单）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 设置页的既有断言（`desktop/web/tests/shellpages-settings.test.tsx:106-112`、`tests/test_gate_t012_baseline.py:2671-2678`）失败，或 T032 门禁里仍有断言「设置页把拒绝渲染成信封」的探针没过：那是范围外的文件（`tests/**` 与设置页），**不要改它们**，写进 `contract_conflicts` 并报告。
- T030 落地后外壳页 preload 的返回形状与本合同的约定不一致（信封是否已拆、`cancelled` 的处理）：不要改 `desktop/shell/**`，写进 `contract_conflicts` 并停下报告。
- 需要新增或升级依赖、写 `.npmrc`、联网装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（3600 秒）。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；截至本版已用掉 1 次，本版起留 2 次）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（累计口径；截至本版已用掉约 3376 秒，剩约 11000 秒，够本版两次单次时限 2×3600=7200 秒并留出余量）
- cost_budget: 12 USD（只统计；调度器强制的是次数与墙钟）
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：读基线与核对门禁 20 分钟；写 shellBridge 与改 shellContext 30 分钟；改两个视图 25 分钟；写两份新测试 35 分钟；跑 V01–V04 15 分钟；写报告 10 分钟；总计约 135 分钟，单轮上限 60 分钟——按「shellBridge+shellContext → 两个视图 → 两份测试 → 检查与报告」的次序推进，到时限就把没做完的写进执行报告。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D13，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：两份新测试各覆盖了哪些条目；夹具模式下现有 `shellpages-*.test.*` 全过；三种 `NODE_ENV` 取值下构建的判定结果；`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`desktop/web/src/pages/SettingsPage.tsx`、`src/live/**`、`desktop/shell/**`、`ts/**`、`scripts/**`、`docs/**`、`schemas/**`、`desktop/web/package.json`、`desktop/web/package-lock.json` 的改动。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；新测试里不写 skip / only / todo。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/**`、`desktop/shell/**`、`ts/**`、`scripts/**`、`docs/**`、`schemas/**`、`desktop/web/package.json`、`desktop/web/package-lock.json`、`desktop/web/src/live/**`、`desktop/web/src/shell/PageFrame.tsx`、`desktop/web/src/App.tsx`、`desktop/web/src/pages/SettingsPage.tsx`、`desktop/web/src/shellpages/{themisShell.ts,shellStub.ts,ShellWindow.tsx,SettingsView.tsx}`。
- 不在 `desktop/web/src/shellpages/**` 的任何文件里出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个整词（连注释与字符串都不许）。
- 不在 `shellContext.tsx`、`ShellWindow.tsx`、`SettingsPage.tsx`、`FirstRunView.tsx`、`ServiceStatusView.tsx` 里出现 `window.themisShell`、`globalThis.themisShell`、`declare global`、`themisHost`。
- 不在 `window.themisShell` 这个对象上挂任何缓存属性（它可能被冻结）；缓存只用 `WeakMap` 或模块级变量。
- 不在 `shellBridge.ts` 里拆信封、不判断返回值像不像信封；错误文案只用 `Error.message`。
- 不新增 `.d.ts` 类型声明文件；`themisShell` 的全局声明就地写在 `src/shellpages/shellBridge.ts` 里。
- 不新增依赖，不写 `.npmrc`。
- 不把设置页的 `getState` 拒绝转成 ok:false 信封、不改设置页让它显示「没有连上外壳」（本片不做，见 Non-goals）。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261112T193657130324Z-owner-ccc9e3：

> 那 1 条仓库外事实已实测，成立；规划第 3 节的缺口一并定了。全文在 `.agent/mailbox/owner-notes/t032-facts-01.md`（合同端、门禁端开工前读它）。
>
> 事实 1（真 electron 44.9.0 窗口，contextIsolation 与 sandbox 都开）：成立。暴露对象的函数成员在主世界里 `typeof` 是 `function`；`on` 返回的退订函数在主世界里也是函数，调用它会执行 preload 里的那个函数；主世界传进去的监听函数 preload 能调用。另量到三条写包装要用的：每次读到的是同一个对象；这个对象是冻结的，不能往上挂缓存属性；可以当 WeakMap 的键。被拒绝的 Promise 过桥后只保留 Error 的 message。
>
> 决定：
> 1. G1：T030 的外壳页 preload 自己拆信封（`ok` 为 true 时 resolve `value`，否则 reject `new Error(reason)`）。shellBridge 只核对十个成员，不包一层，不做“像不像信封”的判断。`openExternal` 被用户取消时 reject 的 message 是 `cancelled`，前端当作正常结束、不显示错误。T030 那边若改了约定，协调人转告合同端。
> 2. G2、G4、G5、G6、G7 照规划的默认做法。G3 照默认做法，`exit_code` 填 1，不改 PageFrame。
> 3. 规划第 5 节的假设我照 T027 attempt-003 的候选预核过（落地后合同端在新基线上复核）：判定是 `src/live/mode.ts` 的 `liveModeIsReal()`，取自构建期常量，只跟 vite 的 command 走，不看页面由谁托管，在 `themis-shell://app/` 下也是真实；引入路径 `../live/mode` 不以 `/api` 结尾。T027 的测试里没有把它切成真的手法：本片用 `vi.mock` 局部替换 `liveModeIsReal`。判定是运行时函数，桩的代码会留在产物里：不要求产物里找不到桩，构建核对照 T027 的做法，“真实模式下不创建桩”由单元用例证明。
> 4. T029 登记时我会写明它不改 `src/shellpages/**` 与 `SettingsPage.tsx`；本片不改 `PageFrame.tsx`、`App.tsx`。

站主来信 20261112T230411562406Z-owner-b6e8d2：

> 选 B：保 D09，本片撤掉“设置页把 getState 被拒转成信封”这一条。旧门禁不用改，基线不用挪。
>
> 事实我核过，属实：`desktop/web/tests/shellpages-settings.test.tsx:106-112` 与 `tests/test_gate_t012_baseline.py:2671-2678` 都逐字断言“getState 被拒时设置页交给 PageFrame 的通用出错块（没有收到服务的回应）”。合同 Repository facts 里“T012 的 settings 探针不再断言占位文字”是错的。G3 是规划的默认做法，站主回信时照准了，没去包内测试里查“拒绝”这条路：这是站主的失误，不是执行端的。
>
> 走法（返工 2-contract，合同端出 v2）：
> 1. `desktop/web/src/pages/SettingsPage.tsx` 不改，从允许修改范围里去掉。设置页的 getState 被拒时照旧走 PageFrame 的通用出错块；现有用例与 T012 那条断言都不动。
> 2. D06 收窄成两件事：“外壳不可用”实例本身的行为（九个函数都以 Error 拒绝，message 是“没有连上外壳”；`on` 同步返回空的退订函数、不调用监听）；首次启动页与服务状态页照规划 G2 显示这句话。
> 3. 真实模式下没有外壳时，设置页显示的是通用出错块而不是“没有连上外壳”：这是已知的不足，写进合同的“不做”，留给主窗口经 `host.openSettings()` 打开设置窗口的那一片。
> 4. D09 原样保留（现有 `shellpages-*.test.*` 一条不改、全过）；Repository facts 那句改正。
> 5. 门禁端：T032 门禁里凡是断言“设置页把拒绝渲染成信封里的命令与消息”的（协调人点的 s06 与 views 探针里设置页那几条），改成断言现状；s09 的逐字比对名单不动；别的不动。
> 6. 执行端在上一轮改动上接着做：撤掉 `SettingsPage.tsx` 的改动和新测试里设置页信封那几条，其余保留。
> 7. attempt 预算不追加（剩 1 次）。这一次若又因为合同或门禁自身的原因失败，不要返工执行端，写“提问”给站主。
