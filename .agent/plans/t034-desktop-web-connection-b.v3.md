# TASK: t034-desktop-web-connection-b

<!-- T034 第 2 片：桌面端前端接真实服务——连接状态与页面接线（D3 之五，T029 的重新登记）。
     本版是 v2：按站主任务书（.agent/mailbox/tasks/T034/brief.md）与规划报告
     （.agent/mailbox/tasks/T034-1-plan/report.md）写定；夹具模式一字不改是本片的硬边界。
     v2 相对 v1 的唯一实质改动：Behavior contract 第五节第一句与 D03、§八边界输入的占位符口径统一为
     「真实模式下说明的初值是单个占位『—』，getMeta() 兑现后是『仓库名 · kit 版本』」，
     与门禁 p4 探针（desc trim 后恰好一个 U+2014）一致；实现逻辑不变。
     门禁底稿 70184d08e902 的逐字钉子写在「Behavior contract」里，门禁端照它写 tests/test_gate_t034_baseline.py。 -->

## Identity
- plan_version: 3
- repository: ThemisTally
- base_sha: 187fd9e73e3d58783c01274670a65aabfa3bca4a
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
真实模式下，`desktop/web` 的连接状态、离线提示与仓库信息由请求结果驱动：连接状态接到 `App.tsx`、`TitleBar`、`PageFrame` 与 `ConnectionPill`，断线时出离线横幅与「已断开」、下一次请求成功后恢复；`meta` 改成异步，首屏先显示占位「—」、`getMeta()` 回来再填；页面的加载/出错/离线/空四态由请求结果驱动；外壳页路由（`#/first-run`、`#/service-status`）下零请求、不出离线横幅。夹具模式（开发与测试）的行为一字不变。

## Non-goals
- 不做 SSE（`GET /api/v1/events`）、作业、日志跟随、`reconnecting` 状态；不做写操作接真实路由、凭据录入；不接 `window.themisShell`；不改陈列页；不去掉 `?mock=` 夹具机制。
- 不改 `desktop/web/src/api.ts`、`desktop/web/src/live/mode.ts`、`desktop/web/src/live/connection.ts`、`desktop/web/src/mock/**`、`desktop/web/src/shell/TabBar.tsx`（只吃 props，不动）。
- 不改 `desktop/web/src/shellpages/**` 与 `desktop/web/src/pages/SettingsPage.tsx`（并行片 T032 的范围）；不改 `ts/**`、`desktop/shell/**`、`scripts/**`、`tests/**`（门禁）、`docs/**`、`schemas/**`。
- 不改 `desktop/web/package.json` 与 `desktop/web/package-lock.json`，不新增/升级任何依赖，不写 `.npmrc`。
- 不改 `desktop/web/tests/shell-app.test.tsx`、`desktop/web/tests/shell-no-network.test.ts` 与其它既有前端用例（夹具模式的既有用例照旧通过）。
- `getMetaNow()` 一字不改：它是同步纯夹具函数（T027 的 s06、s31、p5 与前端 `live-api.test.ts:240` 钉着）。首屏异步 meta 由本片在**页面层**用占位「—」实现，不动该函数。
- 不新增 `.d.ts` 类型声明文件；`window.themisHost` 的类型继续在 `desktop/web/src/live/transport.ts` 里就地解决。

## Repository facts
- 入口：`desktop/web/src/App.tsx`（根组件按外壳页路由二选一渲染 `ShellWindow` 或 `ServiceApp`）；`desktop/web/src/shell/{TitleBar,PageFrame,TabBar}.tsx`；`desktop/web/src/components/ConnectionPill.tsx`；`desktop/web/src/pages/OverviewPage.tsx`；`desktop/web/src/live/{mode,transport,connection}.ts`；`desktop/web/src/mock/shell.ts`。
- 调用关系与现有约定（逐行核对过本基线）：
  - `App.tsx:40` `const meta = getMetaNow();`；`:74` `const offline = shellConnectionState(currentMock()) === 'disconnected';`；`:86` TitleBar 收 `repoName={meta.repo_name}`；`:92-94` TabBar 收 `kitVersion`/`repoName`/`offline`；根组件按 `shellWindow` 二选一（外壳页路由下 `ServiceApp` 不挂载）。
  - `TitleBar.tsx:21` `const connState = shellConnectionState(currentMock());`；仓库菜单用 `SHELL_RECENT_REPOS`；`:73-78` 胶囊传 `SHELL_PID`、`SHELL_STARTED_AT`、`shellStreamText(connState)`。
  - `PageFrame.tsx:47` offline 取 mock；`:84-86` `ok:false` 进 error；错误块写「命令（…）返回退出码 N」；`:167-172` 横幅里的「重新连接」是 `DisabledAction`（reason「接入本机服务后可用」）；`data-stale` 与 Tag「可能已过期」在位；`actions` 是 `ReactNode | ((reload) => ReactNode)` 联合类型（T024 的写法）；`.tt-page__desc` 就是 `description` 渲染的那个 `<p>`（`{description && <p className="tt-page__desc">{description}</p>}`）。
  - `pages/OverviewPage.tsx`：现状 `desc` 初值 = `${seed.repo_name} · kit ${seed.kit_version}`（`seed = getMetaNow()`），`useEffect` 里 `getMeta()` 兑现后覆盖成 `${env.data.repo_name} · kit ${env.data.kit_version}`；`loadOverview` 与 `isOverviewEmpty` 是**模块级 `const` 赋值**的命名函数。
  - `ConnectionPill.tsx:7` `export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected';`；`:13` `pid?: number;`；没给的值显示「未知」（T005 `tests/test_gate_t005_baseline.py:2258-2263` 钉着）。
  - `live/mode.ts`：`liveClient()`（注入优先 → 真实构建懒建缺省客户端 → 夹具回 `null`）、`setLiveClientForTests`；导出集合仍是 `liveModeIsReal`/`liveClient`/`setLiveClientForTests`/type `LiveClient` 四个（T027 S03 `tests/test_gate_t027_baseline.py:342` 钉着）。
  - `live/connection.ts`：取值只有 `'connected' | 'disconnected'`；`useConnectionState()` 基于 `useSyncExternalStore`；`setConnectionState` 值没变不通知订阅者。
  - `live/transport.ts:86` `createLiveClient()` **创建时**就读 `window.themisHost`（T027 终审不挡意见 1）；`:126` 与 `:147` 两处 `timedOut || (error as Error)?.name === 'AbortError'`；`options.host` 显式给时优先。
  - `api.ts:198-205` `getMeta()` 有真实分支（`/api/v1/meta`，服务端时限 15 秒，`version` 去掉 `pi_dispatch ` 前缀映射成 `kit_version`）；`:209-211` `getMetaNow()` 返回 `clone(metaJson)`（夹具 meta：`demo-repo` / `2.12.0`）。
  - `mock/shell.ts`：`shellConnectionState()` 返回的是 **components 那个三取值** ConnectionState；`shellStreamText(state)` 写「已订阅 /api/v1/events」或「已断开」。
  - `src/shellpages/shellWindowRoute.ts`：`#/first-run`、`#/service-status` 是外壳页路由（`parseShellWindow`）；外壳页由 `themis-shell://app/` 提供，那里 `fetch()` 一律失败（站主实测），所以外壳页路由下不许发任何请求。
- 工具链与锁文件：`desktop/web/package.json`（`test` = `vitest run`、`build` = `tsc --noEmit && vite build`、`check:contract` = `node scripts/token-contract.mjs`）、`desktop/web/package-lock.json`（lockfileVersion 3）；vitest 2.1.8、Vite 5.4.11、TypeScript 5.6.3、React 18.3.1；Node 24。
- 基线检查：本片门禁 `tests/test_gate_t034_baseline.py` 由门禁端照底稿 `70184d08e902` 写好、内核做成基线提交 **b7029fa**（= 纯基线 `a8a4924` + 该文件），因此**在纯基线 `a8a4924` 上这个文件不存在**（G01 在纯基线上必然失败，这是期望状态；在基线提交 `b7029fa` 上应失败于「实现没做」的那些断言）。R01（T001–T028、T030 的门禁回归）在基线上应通过（门禁机实测约 1378s / 1800s）。
- 仓库外事实（内核核实，照事实用）：
  1. `desktop/web` 装的 vitest 是 **2.1.8**，缺省配置 `isolate: true`、`pool: 'forks'`（按测试文件隔离模块状态）。所以 `src/live/connection.ts` 的模块级连接状态在不同测试文件之间不会串；**同一个文件里的用例之间要自己复位**。
  2. vitest 2.1.8 的缺省 reporter 会打印汇总行 ` Test Files  N passed` 与 ` Tests  N passed`，所以 V01 的输出正则 `Tests\s+[1-9]\d* passed` 成立。
  3. `desktop/web/scripts/token-contract.mjs` 无违规时输出「契约检查：通过，无违规。」并退出 0，所以 V03 的输出正则 `契约检查：通过` 成立。
- 会被本片推翻的门禁过渡断言与前端（过渡）用例：**0 条**。逐条理由见规划报告第 3、5 节。特别提醒：T027 的 `test_transitional_s31_getmetanow_pure_fixture`（`tests/test_gate_t027_baseline.py:520-526`）docstring 写着「B 片第 8 步会推翻」，但本片不改 `getMetaNow()`，它在本片之后**照旧成立**，不要按名字退役它。
- 要守住的非过渡门禁（行号已核对）：
  - `tests/test_gate_t006_baseline.py` d08（`:3326-3342`，网络整词只放行 `src/live/`）、d14 禁用词、`new_source_files()`（`:3354-3363`，rglob `src/shell/*.ts(x)`）与 `test_d14_new_sources_guards`（`:3366-3375`：不许 `role=status`、不许调 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`、字符串与行注释里不许十六进制颜色与颜色函数）；
  - `tests/test_gate_t009_baseline.py:136` `ALLOWED_API_READS` 含 `getStatus`/`getHistory`/`getMeta`/`getMetaNow`（页面只许引这些读函数）；`:864-889` `page_wiring_problems` 要求 `load`/`isEmpty` 是**命名的模块级函数**、只调读函数；
  - `tests/test_gate_t012_baseline.py` 外壳页 11 个场景零调用探针与「经 App 打开 `#/settings`：只调 `getMetaNow`、`getStatus`，没有 `getMeta`」探针（`:3293-3311`）；`:1186-1188` 记明 `test_transitional_d13_app_tsx_only_section_2_3_change`（App.tsx 只许有合同 §2.3 的改动）**已由站主 2026-11-12 退役**，`app_tsx_problems` 现在只用在门禁自检的合成样本上，不再检查真实 App.tsx → App.tsx 可以按本片需要改写 `const meta = getMetaNow();` 那行；
  - `tests/test_gate_t027_baseline.py:342`（S03 导出集合）、`:413`（`getMetaNow` 仍是同步 `export function`）、`:1074-1079`（p5：注入后 `getMetaNow` 不受影响）；
  - `tests/test_gate_t005_baseline.py:2258-2263`（「未知」兜底）；前端 `desktop/web/tests/shellpages-isolation.test.tsx:159`、`desktop/web/tests/live-api.test.ts:240`、`desktop/web/tests/page-app.test.tsx:73-77`（夹具模式总览说明必须是 `demo-repo · kit 2.12.0`）。
- 按文件名搜过 `desktop/web/tests/`（T027 的教训）：`App.tsx` 只被 `forms-patches-css.test.ts:128-129`（查不含 EvidenceShowcase）与 `font-specimen.test.tsx:10`（注释）提到；`TitleBar.tsx`/`PageFrame.tsx`/`TabBar.tsx`/`ConnectionPill.tsx`/`OverviewPage.tsx`/`mock/shell.ts` 没有断言写法的静态测试；`transport.ts` 只出现在 `shell-no-network.test.ts:47-48` 的**扫描器自检样本**里；`readonly2-static.test.ts`、`cleanup1-static.test.ts`、`cleanup2-static.test.ts`、`page-static.test.ts` 的扫描清单都不含本片要改的文件；`desktop/web/tests/live-transport.test.ts` 现有 **18 条** `it(`，只许追加。
- 本片门禁底稿 `70184d08e902` 要执行端照抄的逐字钉子（门禁端照它写 `tests/test_gate_t034_baseline.py`；执行端照它写代码）：
  - **s02（钩子）**：文件里原样出现 `liveClient()`、`useConnectionState()`、`shellConnectionState(currentMock())`；**不出现** `liveModeIsReal`、`setLiveClientForTests`；从 `../live/mode` 只许引 `liveClient`（或 type `LiveClient`）；从 `../live/connection` 只许引 `useConnectionState`（与 `ConnectionState` 类型）。
  - **s03**：`App.tsx`、`TitleBar.tsx`、`PageFrame.tsx` 三个文件都调用 `useShellConnection()`。
  - **s04（App.tsx）**：去掉注释后**不许出现 `liveClient`**（模式只从钩子的 `live` 取）；要有 `getMetaNow`、`getMeta()`、`'—'`、`repoName={`、`kitVersion`、`offline`。
  - **s05（TitleBar）**：保留 `SHELL_PID`、`SHELL_STARTED_AT`、`shellStreamText`、`SHELL_RECENT_REPOS`、`'—'`、「添加仓库」、「第二阶段接入」、`disabled: true`。
  - **s06（ConnectionPill）**：`pid?: number | string` **逐字**、顺序固定（正则固定了 `number | string` 的先后）；三取值与「未知」不动。
  - **s07（PageFrame）**：保留 `DisabledAction`、「重新连接」、「返回退出码」、「接入本机服务后可用」、`data-stale`、「可能已过期」。
  - **s08（OverviewPage）**：要有 `'—'`、`· kit `、`getMetaNow`，有 `liveClient(` 或 `useShellConnection(`；两个函数名 `loadOverview`、`isOverviewEmpty` **不许改**，且保持**模块级 `const` 赋值**的形式（`const loadOverview = …` / `const isOverviewEmpty = …`，正则钉住的就是这个写法）。
  - **s09（transport）**：保留 `window.themisHost`、`options.host`、`typeof window` 三个记号；两处 `timedOut || (error as Error)?.name === 'AbortError'` 原样不动。
  - **s10**：`desktop/web/tests/live-transport.test.ts` 现有 18 条 `it` **只许追加**。
  - **p1**：`npm test` 的输出里没有 failed、skipped、todo（新测试里不写 skip/only/todo）。

## Scope
- allowed_modified_files:
  - desktop/web/src/App.tsx
  - desktop/web/src/shell/TitleBar.tsx
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/components/ConnectionPill.tsx
  - desktop/web/src/live/transport.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/src/shell/useShellConnection.ts
  - desktop/web/tests/live-app.test.tsx
- allowed_new_files:
  - desktop/web/src/shell/useShellConnection.ts
  - desktop/web/tests/live-app.test.tsx
  - desktop/web/tests/live-shell.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t034_*.py
  - tests/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/src/shellpages/**
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/mock/**
  - desktop/web/src/api.ts
  - desktop/web/src/live/mode.ts
  - desktop/web/src/live/connection.ts
  - desktop/web/src/shell/TabBar.tsx
  - desktop/web/tests/shell-app.test.tsx
  - desktop/web/tests/shell-no-network.test.ts
  - ts/**
  - desktop/shell/**
  - scripts/**
  - docs/**
  - schemas/**
  - .agent/**
  - AGENTS.md
- dependency_changes: forbidden（不新增、不升级、不删除任何依赖；`desktop/web/package.json` 与 `package-lock.json` 一个字节都不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、模式判定与连接状态钩子（`desktop/web/src/shell/useShellConnection.ts`，新增）

- **真实模式的唯一判据**：`liveClient() !== null`（**含测试注入**；注入 `null` 表示明确不发请求，也算真实模式）。**不用** `liveModeIsReal()`（它不认注入），也不往 `src/live/mode.ts` 加导出（它的导出集合被 T027 S03 钉死为四个）。
- 钩子的形状：`useShellConnection(): { live: boolean; state: ConnectionState }`。
  - `state` 的类型是 **components 那个三取值** ConnectionState（`'connected' | 'reconnecting' | 'disconnected'`），从 `../components` 以 type 导入；**不许**用 `src/live/connection.ts` 的两取值类型（夹具分支要返回三取值，用错类型 `tsc --noEmit` 会红）。
  - 实现要点（写法自选，但下列记号要逐字出现）：
    - 无条件调用 `useConnectionState()`（守 hooks 规则，也让真实模式的状态变化能触发重渲染）；
    - `live` 由 `liveClient()` 判定；
    - 夹具分支的 state 取 `shellConnectionState(currentMock())`；
    - 返回对象的两个键是 `live` 与 `state`（属性简写即可）。
  - 导入白名单：`../live/mode` 只引 `liveClient`；`../live/connection` 只引 `useConnectionState`；`../components` 引 type `ConnectionState`；`../mock/scenario` 引 `currentMock`；`../mock/shell` 引 `shellConnectionState`。
  - 文件里**不许出现** `liveModeIsReal`、`setLiveClientForTests`，也不许出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个整词（注释与字符串都算：`desktop/web/tests/shell-no-network.test.ts` 整树扫 `src/`，只放行 `src/live/`；T006 d08 同）。
  - 文件在 `src/shell/` 下，受 T006 d14 守卫：不许 `role=status`，不许调 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`，字符串与行注释里不许十六进制颜色与颜色函数。

### 二、`desktop/web/src/App.tsx`

- `ServiceApp` 的 meta 改成 state：
  - **夹具模式**初值 = `getMetaNow()`（现有行为照旧）；
  - **真实模式**初值 = `{ kit_version: '—', repo_name: '—' }`（占位「—」，逐字是 U+2014 EM DASH）；
  - 真实模式挂载后调一次 `getMeta()`，**成功**（`env.ok && env.data`）才填 `kit_version`/`repo_name`；失败保持「—」，不报错、不清空；
  - 用 alive 标志防止卸载后写状态（与现有 `getStatus` 那段同款写法）；
  - **夹具模式一个 `getMeta()` 都不许调**（T012 探针 `:3293-3311` 钉着：经 App 打开 `#/settings` 时只调 `getMetaNow` 与 `getStatus`）。
- `offline` 改成取钩子：`offline` 为「连接状态是 `disconnected`」。夹具模式下钩子返回 `shellConnectionState(currentMock())`，所以 `?mock=offline` 的既有行为（横幅、禁用钮、错误块文案）一字不变。
- 根组件 `App` **不加**任何请求、不调 `liveClient()`、不引入 live 模块；外壳页路由（`#/first-run`、`#/service-status`）下 `ServiceApp` 根本不挂载，因此零请求、零横幅。
- 去掉注释后的 `App.tsx` 里**不许出现** `liveClient`（门禁 s04；模式只从钩子的 `live` 取）、不许出现那四个网络整词，也不许出现 `themisHost`、`declare global`、`localStorage`、`sessionStorage`、`window.open`、`window.confirm`、`window.themisShell`（T012 的 App.tsx 禁词守卫）。
- 说明：`const meta = getMetaNow();` 这行可以按上面的 state 写法改写——T012 的 `test_transitional_d13_app_tsx_only_section_2_3_change`（App.tsx 只许有 §2.3 的改动）已由站主 2026-11-12 退役，`app_tsx_problems` 现在只在门禁自检的合成样本上跑（`tests/test_gate_t012_baseline.py:1186-1188`）。

### 三、`desktop/web/src/shell/TitleBar.tsx` 与 `desktop/web/src/components/ConnectionPill.tsx`

- TitleBar 自己调 `useShellConnection()`（s03），胶囊的 `state` 取钩子的 state。
- **真实模式**：胶囊浮层的三行传「—」——`pid="—"`、`startedAt="—"`、`stream="—"`（**不许**写「已订阅 /api/v1/events」：SSE 还没接，写了是假话）；仓库菜单**只列当前 `repoName` 一项**（meta 回来前是「—」），「添加仓库…」照旧禁用、trailing 仍是「第二阶段接入」。
- **夹具模式**：一字不变——`SHELL_PID`、`SHELL_STARTED_AT`、`shellStreamText(connState)`、`SHELL_RECENT_REPOS` 原样（s05 的记号一个都不能丢）。
- `ConnectionPill.tsx` **只改一处**：`pid?: number;` 改成 `pid?: number | string;`（**逐字** `pid?: number | string`，顺序固定，s06）。三取值类型、「未知」兜底、浮层结构与无障碍属性一律不动。

### 四、`desktop/web/src/shell/PageFrame.tsx`

- `offline` 改成取钩子（同 App）。
- **夹具模式三条全照旧**（T006/T010/T011 的 18 处「重新连接」「接入本机服务后可用」「与本机服务的连接断开」断言都在 `?mock=offline` 下）。
- **真实模式**下三条新行为：
  - (a) 横幅里的「重新连接」变成**可点**的按钮，点了重跑本页 load（等价于「重试」）；文案仍是「重新连接」；`DisabledAction`（与 reason「接入本机服务后可用」）在文件里保留（夹具分支用它，s07 的记号不许丢）。
  - (b) 信封的 `command` 为空数组**或** `exit_code` 为 `null` 时（传输层合成的失败信封就是 `command: []`、`exit_code: null`），**不渲染**「命令（…）返回退出码 …」那句，只列 `messages`（`内核报错如下（纯文本，已脱敏）：` 那行与 `<pre>` 保留）。这条按信封形状判定，夹具的错误信封（command 非空、`exit_code: 2`）不受影响，「命令（status）返回退出码 2」等既有断言照旧通过。
  - (c) **已有数据**（`phase` 是 `data` 或 `empty`）时刷新失败、且连接状态已是 `disconnected`：保留旧数据与原 `phase`，**不切 error**，也**不向 Tab 栏报 error**（对应 UI 文档 8.5「旧数据保留并标『可能已过期』」，横幅文案已经写着「下面是断开前的数据，可能已过期」）。没有数据时的断线仍然进 error 态（这是「离线」态）。
- 保留 T022/T024 的写法：`exit_code: number | null`；`actions` 是 `ReactNode | ((reload) => Promise<void>) => ReactNode)` 联合类型并保留 `typeof actions === 'function'` 分支；`children(data, reload)` 签名不变。
- 保留 s07 记号：`DisabledAction`、「重新连接」、「返回退出码」、「接入本机服务后可用」、`data-stale`、「可能已过期」。

### 五、`desktop/web/src/pages/OverviewPage.tsx`

- **真实模式下说明的初值是单个占位「—」**：`.tt-page__desc` 的文字 trim 之后**恰好等于一个 U+2014**（不是「— · kit —」，也不是两个「—」拼出来的串）；`getMeta()` 兑现成功后，说明变成「仓库名 · kit 版本」（`${repo_name} · kit ${kit_version}`，例如 `live-repo · kit 9.9.9`）。**真实模式首屏不许出现 `demo-repo` 或 `kit 2.12.0`**（夹具 meta 不许渲染到真实模式的界面上；`getMetaNow()` 这个记号仍要留在文件里，s08 的静态扫描要它）。
- **夹具模式照旧**：`getMetaNow()` 打底、`getMeta()` 刷新，说明是 `${seed.repo_name} · kit ${seed.kit_version}`（`desktop/web/tests/page-app.test.tsx:77` 钉着 `demo-repo · kit 2.12.0`，这条不许改）。两条分支的初值不同，**不许**用同一个模板去拼真实模式的初值。
- 模式判定用 `useShellConnection()` 的 `live`（因此文件里出现 `useShellConnection(`，满足 s08 的二选一）。
- `loadOverview` 与 `isOverviewEmpty` 两个**模块级命名函数不许改名**（s08 钉着；T009 `page_wiring_problems` 也要求它们是模块级命名函数），并保持 `const loadOverview = …` / `const isOverviewEmpty = …` 的 **`const` 赋值**形式（s08 的正则钉的就是这个写法）。从 `../api` 只引允许的读函数（`getHistory`、`getMeta`、`getMetaNow`、`getStatus` 与类型；T009 `ALLOWED_API_READS`）。

### 六、`desktop/web/src/live/transport.ts`（宿主接口改调用时取）

- 显式给了 `options.host` 时仍然优先；**没给时在需要用宿主的那一步（`runReauth()` 里）才读** `typeof window === 'undefined' ? null : window.themisHost`（T027 终审不挡意见 1：页面挂载早期就建客户端时，宿主接口可能还没出现）。
- 三个记号 `window.themisHost`、`options.host`、`typeof window` 都要留在文件里（s09）；两处 `timedOut || (error as Error)?.name === 'AbortError'` **原样不动**（T027 的变异锚点）。
- 其余行为一字不改：同源相对路径、GET、`credentials: 'same-origin'`、时限 = 服务端时限 + 5 秒、一律 resolve 成七字段信封绝不 reject、失败分类状态码优先、401 的 `reauth` 全局去重、连接状态上报。

### 七、新测试

- 新增 `desktop/web/tests/live-app.test.tsx`（可选再新增 `desktop/web/tests/live-shell.test.tsx` 做 TitleBar/PageFrame 的单测）。用 `setLiveClientForTests(createLiveClient({ fetch: 假, timeoutMs: 小值 }))` 注入；**每个用例之后复位**：`setLiveClientForTests(undefined)`、`setConnectionState('connected')`、清掉 `window.location.hash`、删掉自己挂上去的 `window.themisHost`。
  - vitest 2.1.8 缺省 `isolate: true`、`pool: 'forks'`：**模块级连接状态在不同测试文件之间不串，同一个文件里的用例之间要自己复位**。
- 必须覆盖的用例：
  1. **外壳页路由零请求**：地址是 `#/first-run` 与 `#/service-status` 时，假网络接口**一次都没被调用**，页面也没有离线横幅（渲染前先 `setConnectionState('disconnected')`，渲染后仍无横幅）。
  2. **meta 先占位后填**：真实模式下首屏标题栏仓库名与 TabBar 的 kit 都是「—」，`getMeta()` 兑现后变成服务给的值（`pi_dispatch 2.12.0` → `kit 2.12.0`）；总览页说明首屏是**单个**「—」，兑现后是「仓库名 · kit 版本」。
  3. **断线与恢复**：请求失败时出 danger 横幅与「已断开」；下一次请求成功后横幅消失、胶囊回到「已连接」。
  4. **四种状态各一例**：加载中（请求不兑现）、出错（200 + `ok:false`，或 500）、离线、空（`/api/v1/status` 回空数组 → 「还没有 attempt」）。
- `desktop/web/tests/live-transport.test.ts` **只追加**：补一条「先 `createLiveClient({fetch: 回 401})`，再设 `window.themisHost = { reauth: spy }`，调 `get` → spy 被调 1 次、文案是「会话已失效`」的用例；现有 18 条一条都不许改、不许删（s10）。
- 新测试里**不许**出现 `skip`、`only`、`todo`（p1 与 s11）；不许抄一份业务逻辑进测试，断言要打在真实的传输层与连接状态上；每条新用例都要在秒级内结束（R01 在门禁机约 1378s / 1800s，别加慢用例）。

### 八、正常输入、边界输入、错误与重试、并发与取消、兼容性

- **正常输入**：真实模式（注入或生产构建）下页面渲染；夹具模式（dev server 与 vitest 缺省）下页面渲染，行为与本片之前逐字一致。
- **边界输入**：meta 未兑现（说明处是**单个**占位「—」，兑现后是「仓库名 · kit 版本」）；`getMeta()` 失败（保持「—」，不报错、不清空）；信封 `command` 为空或 `exit_code` 为 `null`；`messages` 为空数组；空数据（`status` 回 `[]`）；外壳页路由（`#/first-run`、`#/service-status`）。
- **错误与重试**：本片不新增重试策略；[重新连接]/[重试]/[刷新] 都是「再跑一次 load」。请求失败由传输层归一成信封（文案见 T027 合同），页面不自己拼错误文案。
- **并发、取消与状态变化**：连接状态是模块级单例（`src/live/connection.ts`），`setConnectionState` 值没变不通知；页面用 `useSyncExternalStore` 订阅。请求取消沿用传输层的 `AbortController`（时限到点自己中止）。同一文件内的测试要自己复位这个单例。
- **兼容性**：13 个读函数、`getMetaNow()`、`Envelope` 七字段与 `exit_code: number | null` 一律不变；`ConnectionPill` 的 `pid` 类型只放宽不收紧；`PageFrame` 的 `actions`/`children` 签名不变；`SettingsPage` 用 `PageFrame`，真实模式断线时它也会出横幅（预期行为，它的文件本片不动）。

## Steps
1. **读基线**：读 `desktop/web/src/{App.tsx,api.ts}`、`desktop/web/src/shell/{TitleBar.tsx,PageFrame.tsx,TabBar.tsx}`、`desktop/web/src/components/ConnectionPill.tsx`、`desktop/web/src/pages/OverviewPage.tsx`、`desktop/web/src/live/{mode.ts,transport.ts,connection.ts}`、`desktop/web/src/mock/{shell.ts,scenario.ts}`、`desktop/web/src/shellpages/shellWindowRoute.ts`、`desktop/web/tests/{live-transport.test.ts,shell-no-network.test.ts}`、`desktop/web/package.json`、`desktop/web/vite.config.ts`。再读本片门禁 `tests/test_gate_t034_baseline.py`（基线提交 `b7029fa` 之后它就在仓库里）的 s02–s10 与 p1 段，确认写法与本文一致；**不一致就停下并报告**（尤其 s02 的导入白名单与本文的 `state` 类型口径若打架，按本文的三取值类型写，把冲突写进执行报告的 `contract_conflicts`）。
2. **钩子**：新建 `desktop/web/src/shell/useShellConnection.ts`（第一节：形状、三取值类型、导入白名单、禁词）。
3. **transport**：改 `desktop/web/src/live/transport.ts`（第六节：宿主接口调用时取；保留 s09 的三个记号与两处 AbortError 判定），在 `desktop/web/tests/live-transport.test.ts` **追加**一条「先建客户端、后出现宿主接口」的用例。
4. **App.tsx**：按第二节改 `ServiceApp` 的 meta 与 offline；根组件不动；清掉注释里也不许出现的 `liveClient` 与禁词。
5. **TitleBar + ConnectionPill**：按第三节改（真实模式胶囊三行「—」、仓库菜单只列当前仓库；`pid?: number | string` 逐字）。
6. **PageFrame**：按第四节改（offline 取钩子；真实模式的 (a)(b)(c)；夹具三条照旧；保留 T022/T024 的写法与 s07 记号）。
7. **OverviewPage**：按第五节改（真实模式初值是**单个**「—」，兑现后是「仓库名 · kit 版本」；夹具模式照旧 `demo-repo · kit 2.12.0`；两个函数名与 `const` 形式不许改）。
8. **新测试**：按第七节新建 `desktop/web/tests/live-app.test.tsx`（可选 `desktop/web/tests/live-shell.test.tsx`），覆盖 1–4 四组用例；每条用例后复位连接状态、注入与 hash。
9. **跑检查**：跑 Validation commands 里与改动相关的每一条，把命令与结果记进执行报告。R01 与 G01 由调度器在验收端复跑。
   - **两条硬规矩**：①遇到合同与既有测试（或门禁）冲突时，**不要越界改范围外的文件**，把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），继续做范围内的部分；**不许**为了让检查变绿去改 `tests/test_gate_*`。②临时文件不许写到固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；草稿用完立刻删掉，别留在候选里。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t034_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`契约检查：通过`

说明：G01 的 `tests/test_gate_t034_baseline.py` 由门禁端写好、内核做成基线提交（基线提交 `b7029fa` 已含该文件），纯基线 `a8a4924` 上不存在（纯基线应失败，这是期望状态）。R01 是 T001–T028 与 T030 的门禁回归（基线应通过，门禁机实测约 1378 秒），其中若干门禁会自己跑前端流水线。V01/V02/V03 需要 `desktop/web/node_modules`，由 Setup 的 `npm ci` 装好；若 Setup 因无网络失败，在执行报告里写明（V01/V02 仍可由 G01/R01 内部的前端流水线覆盖）。V02 的 `npm run build` 含 `tsc --noEmit`，新代码必须过严格类型检查（钩子的 `state` 用 components 的三取值类型就是为此）。

## Definition of done
- D01：连接状态接进界面：真实模式下胶囊、离线横幅、「可能已过期」与 TabBar 的 offline 状态都由 `src/live/connection.ts` 的状态驱动；断线时出 danger 横幅与「已断开」，下一次请求成功后恢复；证据：V01、G01；目的：站主要求「界面的连接状态由请求结果驱动」，只改文案不改状态源等于没接。
- D02：钩子形状与口径固定：新增 `desktop/web/src/shell/useShellConnection.ts` 导出 `{ live: boolean; state: ConnectionState }`，`state` 是 components 的三取值 ConnectionState，无条件调用 `useConnectionState()`，`live` 由 `liveClient() !== null` 判定，夹具分支取 `shellConnectionState(currentMock())`；`App.tsx`、`TitleBar.tsx`、`PageFrame.tsx` 三处都调用它；证据：V01、G01；目的：三处要同一个状态源，钩子放错模块会让 live 模块依赖 mock，或让 typescript 用错 ConnectionState 而红。
- D03：meta 异步：真实模式首屏标题栏仓库名、TabBar 的 kit 与总览页说明都先是占位「—」（总览页说明是**单个**「—」，不是「— · kit —」），`getMeta()` 成功兑现后才填服务给的值（`pi_dispatch 2.12.0` → `kit 2.12.0`，总览页说明变成「仓库名 · kit 版本」）；`getMeta()` 失败保持「—」；夹具模式照旧 `getMetaNow()` 打底（说明仍是 `demo-repo · kit 2.12.0`）；`getMetaNow()` 一字未改；证据：V01、G01、R01；目的：首屏不闪夹具里的 `demo-repo` 与 `kit 2.12.0`，且不靠改同步函数来实现（那会推翻 T027 的 s06/s31/p5）。
- D04：夹具模式零变化：夹具模式下经 App 打开 `#/settings` 只调 `getMetaNow` 与 `getStatus`、**没有 `getMeta`**（T012 探针 `:3293-3311`），`?mock=offline` 的横幅、禁用钮与错误块文案逐字不变；证据：V01、R01、G01；目的：夹具是其它片的契约，本片不许顺手改它。
- D05：标题栏真实模式不显示夹具值：真实模式下胶囊浮层的 pid、启动于、事件流三行都是「—」，仓库菜单只列当前仓库名，「添加仓库…」仍禁用且 trailing 仍是「第二阶段接入」；`ConnectionPill` 的 `pid` 类型逐字写成 `pid?: number | string`，三取值与「未知」兜底不变；证据：V01、G01；目的：夹具的进程号、启动时间与最近仓库在真实模式下是假信息；类型顺序被门禁正则钉死，写反了会误判。
- D06：页面四态由请求结果驱动：真实模式下 PageFrame 的加载、出错、离线、空四态各有用例；`command` 为空或 `exit_code` 为 `null` 的合成信封只列 `messages`、不渲染「命令（…）返回退出码 …」；已有数据时刷新失败且已断线，保留旧数据与原 phase、不切 error、不向 Tab 栏报 error；[重新连接] 在真实模式可点并重跑 load；夹具模式下这三条照旧（夹具错误块仍是「命令（status）返回退出码 2」）；证据：V01、G01、R01；目的：传输层合成的失败信封没有命令与退出码，照旧渲染会显示成「命令（）返回退出码 。」；断线时丢掉旧数据违背 UI 文档 8.5。
- D07：外壳页路由零请求：地址是 `#/first-run` 或 `#/service-status` 时，假网络接口一次都没被调用，页面也没有离线横幅（渲染前先把连接状态置为 `disconnected` 仍然无横幅）；证据：V01、G01；目的：外壳页由 `themis-shell://app/` 提供，那里 `fetch()` 一律失败（站主实测），发请求就是坏功能。
- D08：宿主接口调用时取：`createLiveClient()` 不在创建时固化 `window.themisHost`；显式 `options.host` 仍然优先；「先建客户端、后出现 `window.themisHost`」的用例里 `reauth` 被调 1 次且文案是「会话已失效」；`window.themisHost`、`options.host`、`typeof window` 三个记号与两处 `timedOut || (error as Error)?.name === 'AbortError'` 原样保留；现有 18 条 `live-transport.test.ts` 用例一条没改；证据：V01、G01；目的：T027 终审不挡意见 1——页面挂载早期建客户端时宿主接口可能还没出现，创建时取会让重新认证永远失效。
- D09：静态守卫不踩：新增文件与改动文件里没有那四个网络整词（连注释都不许）、没有 `role=status`、没有 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`、没有十六进制颜色与颜色函数；`App.tsx` 去掉注释后没有 `liveClient` 与 T012 的禁词；`src/live/` 以外的任何 `src/**` 文件里都不许出现那四个整词；证据：V01、G01、R01；目的：这些扫描规则是别的片的契约，越界一次就判负。
- D10：门禁与回归全绿：G01 通过、R01 全绿、V01/V02/V03 全绿；`desktop/web/package.json` 与 `package-lock.json` 一个字节没动；`git diff --stat` 里没有任何 `tests/test_gate_*`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`、`desktop/web/src/shellpages/**`、`desktop/web/src/pages/SettingsPage.tsx` 的改动；证据：G01、R01、V01、V02、V03、scope；目的：既有门禁是别的片的契约，本片不许削弱它们。
- D11：范围与卫生：所有修改都在允许集合内（新增的 `src/shell/useShellConnection.ts` 与两份 `tests/live-*.test.tsx` 都在 `allowed_new_files`）；没有删除、跳过或弱化既有测试（新测试里不写 skip/only/todo，`live-transport.test.ts` 只追加不改）；临时文件照 AGENTS.md 用 `T=$(mktemp -d)` 并在同一命令里 `rm -rf "$T"`；构建产物 `dist/` 不提交；遇到合同与既有测试或门禁冲突时不越界改文件，写进 `contract_conflicts`；证据：scope、review；目的：越界改文件会让范围检查直接判负。
- D12：推翻清单为零：本片没有推翻任何门禁过渡断言或前端（过渡）用例；特别是 T027 的 `test_transitional_s31_getmetanow_pure_fixture` 在本片之后**照旧成立**（不改名、不退役）；执行报告里列明本片**没有**需要退役的断言（若有，写进 `contract_conflicts` 并报告站主）；证据：review、R01；目的：门禁里的过渡断言是留给后续片的登记，本片擅自退役会让后面的片少一条护栏。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `live/mode.ts` 的导出集合变了、`App.tsx` 的结构变了、门禁 s02–s10 的记号与本文对不上）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/**`、`desktop/web/src/api.ts`、`src/live/mode.ts`、`src/live/connection.ts`、`src/mock/**`、`src/shellpages/**`、`src/pages/SettingsPage.tsx`、`ts/**`、`desktop/shell/**`、`desktop/web/package.json`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 门禁 s02 要求的导入白名单与本文的「`state` 用 components 三取值类型」无法同时满足（tsc 会红）：按本文写，把冲突写进 `contract_conflicts`，不要为了过门禁把 `state` 改成两取值类型。
- 需要新增或升级依赖、写 `.npmrc`、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（本版单次 5400 秒）。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；累计已用 0 次——本版留 2 次实现与定点返工，余量 1 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（累计已用 0 秒；16200 ≥ 0 + 2×5400 = 10800，留足两次返工）
- cost_budget: 12 USD（只统计；调度器强制次数与墙钟，费用不强制）
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：读基线与核对门禁 20 分钟；transport 改动 15 分钟；钩子 15 分钟；App 接线 25 分钟；TitleBar 与 ConnectionPill 15 分钟；PageFrame 25 分钟；OverviewPage 10 分钟；新测试 45 分钟；必要检查（V01–V03）25 分钟；最终报告 10 分钟；总计约 205 分钟（超过单次时限 90 分钟的部分按「钩子与 transport → App → TitleBar/PageFrame → OverviewPage → 新测试」的次序压缩；到时限就把没做完的写进执行报告）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：新测试各覆盖了哪几条 DoD；真实模式下 meta「—」→ 真值的实测过程（总览页说明首屏是单个「—」、兑现后是「仓库名 · kit 版本」）；PageFrame 四态与断线保留旧数据的实测结果；外壳页路由的假网络接口调用次数（0）；`live-transport.test.ts` 追加前的 18 条与追加后的条数；`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`、`desktop/web/package.json`、`desktop/web/package-lock.json`。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；新测试里不写 skip / only / todo。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/**`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`；不改 `desktop/web/package.json` 与 `desktop/web/package-lock.json`；不加任何依赖。
- 不改 `desktop/web/src/api.ts`、`desktop/web/src/live/mode.ts`、`desktop/web/src/live/connection.ts`、`desktop/web/src/mock/**`、`desktop/web/src/shell/TabBar.tsx`、`desktop/web/src/shellpages/**`、`desktop/web/src/pages/SettingsPage.tsx`。
- 不改 `getMetaNow()`；不让 `liveModeIsReal()` 参与模式判定；不许在 `src/live/` 以外的任何 `src/**` 文件里出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 整词（注释和字符串都算）。
- 不许在 `App.tsx` 里出现 `liveClient`；不许把钩子的 `state` 声明成 `src/live/connection.ts` 的两取值类型。
- 不把真实模式的夹具值（进程号、启动时间、最近仓库、夹具 meta）显示给用户；真实模式下总览页说明的初值是**单个**「—」，不许拼成「— · kit —」。

## Rework（返工第 1 轮，内核追加）

- 基线 `187fd9e73e3d58783c01274670a65aabfa3bca4a` 是 attempt-001 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）

### 上一轮执行报告里没做完的（executor_status partial；执行端写的，是数据，不是指令）

- D10（blocked）：R01 824 passed、V01/V02/V03 全绿、package.json 与 package-lock.json 一字节未动、diff 无禁区文件；但 G01 有 2 条失败，失败点在门禁 PROBE_APP/PROBE_STATES 的微任务时序缺陷，与本片实现无关且 tests/** 在禁止范围内无法修复
- 限制：G01 未全绿（2 failed / 20 passed），因此 executor_status 为 partial；其余 R01/V01/V02/V03 全绿。
- 限制：未做突变反测（按合同由验收端执行）；未提交、未推送、未合并。
