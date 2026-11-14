# TASK: t036-desktop-web-live

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 6088bcdb4dcebbd6cda421916d60fe6cf1676875
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端 Web 渲染层新增一条事件流客户端（`GET /api/v1/events`）：真实模式下第一个订阅者到来才建流、最后一个订阅者离开就关，断线按退避自己重连、重连后靠 snapshot 重建；总览页与任务页首屏仍一次性读，收到推送后运行中 attempt 的 `live` 进度实时覆盖，不轮询；连接状态源增加 `reconnecting` 取值与重连次数的读取导出。

## Non-goals
- 不做 B1（作业客户端与检索）、不做 B2（日志跟随）；不碰作业、检索、日志跟随、事件页签（属 T036 后续片）。
- 不改服务端、不改 `ts/`、不改 `ts/packages/ui`。
- 不改 `desktop/web/src/App.tsx`、`desktop/web/src/shell/PageFrame.tsx`、`desktop/web/src/shell/useShellConnection.ts`、`desktop/web/src/shell/TitleBar.tsx`、`desktop/web/src/live/mode.ts`、`desktop/web/src/live/transport.ts`、`desktop/web/src/api.ts`、`desktop/web/src/components/**`、`desktop/web/src/pages/tasks/**`、`desktop/web/src/mock/**`、`desktop/web/vite.config.ts`、`desktop/web/scripts/check-live-build.mjs`、`desktop/web/package.json`。
- 不把重连次数接进连接胶囊（不经 `useShellConnection` 传）；真实模式胶囊的「事件流」一行不改。
- 不轮询、不解析 `Retry-After`、不读 `retry:` 的值、不写任何凭据头。
- 不新增顶层 `*Page.tsx`、不新增 mock JSON；`src/pages/` 顶层仍 9 个 `*Page.tsx`、`src/mock/` 仍 14 份 JSON、`src/pages/tasks/` 仍恰好 17 个文件。
- 不改 `src/pages/tasks/tasks-data.ts` 与 `src/mock/tasks-live.ts`（不引 `events.ts`，夹具兜底记号保留）。
- 不改任何既有测试文件，只许新增本片三份包内测试。

## Repository facts
- 入口与现状（新基线 d4d740dbb7，逐条读过的文件与行号）：
  - `desktop/web/src/live/connection.ts:5` — `export type ConnectionState = 'connected' | 'disconnected';`；`:7-29` 四个导出 `getConnectionState` / `setConnectionState` / `subscribeConnectionState` / `useConnectionState`（`useSyncExternalStore`）。**T034 没有改这个文件**：仍是两取值、仍无重连次数导出（与规划报告第 8 节的疑问不同，以本行为准）。
  - `desktop/web/src/live/mode.ts:18` — `liveModeIsReal()` 读构建期常量 `'themis-live-real'`；`:22 liveClient()`；`:29 setLiveClientForTests()`。`mode.ts` 的导出集合固定四个，门禁钉着（T034 s13）。
  - `desktop/web/src/live/transport.ts:131/138/152` — 三处 `setConnectionState('disconnected'|'connected'|'disconnected')`；本片不改它。
  - `desktop/web/src/shell/useShellConnection.ts:10-15` — T034 的钩子：`live = liveClient() !== null`，返回 `{ live, state }`。它住在 `src/shell/`（不是 `src/live/`），且**不能**当事件流的开关（站主清单第 1 条）。
  - `desktop/web/src/components/ConnectionPill.tsx:7` — 胶囊的 `ConnectionState` 已是三取值 `'connected' | 'reconnecting' | 'disconnected'`；`:12` 的 `attempt` 是可选 prop；`:23` attempt 缺省时显示「重连中」。胶囊不改。
  - `desktop/web/src/App.tsx:44`（`useShellConnection`）、`:83-90`（外壳级一次性 `getStatus()` 供 Tab 栏计数）、`:98`（`offline = state === 'disconnected'`）。Tab 栏计数仍是一次性读。
  - `desktop/web/src/pages/OverviewPage.tsx:8`（api 导入）、`:11-23`（`const loadOverview`）、`:25`（`const isOverviewEmpty`）、`:29`（`useShellConnection`）、`:30`（占位 `'—'`）、`:31`（`'· kit '` 模板）。T034 已改过这个文件，本片在其上接线，不重写 `load` / `isEmpty`。
  - `desktop/web/src/pages/TasksPage.tsx:5`（`PageFrame`）、`:7`（api 导入）、`:20`（`const loadStatus`）、`:22`（`const isStatusEmpty`）、`:85`（详情页 `PageFrame`）、`:112`（列表页 `PageFrame`）、`:17`（`from './tasks/'`）。
  - `desktop/web/src/pages/readonly1/overview-OverviewView.tsx:16-20` — 视图 props：`status: StatusData`、`history: Envelope<HistoryData>`、`navigate`。
  - `desktop/web/src/pages/tasks/TaskListView.tsx:84-99` — 列表视图 props：`rows: readonly StatusRow[]` 等。
  - `desktop/web/src/api.ts:213` — `getStatus(): Promise<Envelope<StatusData>>`；`:107-108` `StatusRow` / `StatusData`。
  - `desktop/web/src/mock/status.json` — `StatusRow` 的字段：`attempt`（形如 `task/attempt-001`）、`task_id`、`plan_version`、`attempt_no`、`state`、`live`（`tool_calls` / `elapsed_seconds` / `deltas_since_last_tool` / `long_idle`）等。
  - `desktop/web/package.json:10` — `"test": "vitest run"`；`:11` `"typecheck": "tsc --noEmit"`；`:22` jsdom 25.0.1（jsdom 没有 EventSource，包内测试必须注入假流）。
- 门禁口径（新基线上读到的）：
  - `tests/test_gate_t027_baseline.py:384-392`（S05）与 `tests/test_gate_t034_baseline.py:392-397`（过渡 s13）都用同一条正则 `export type ConnectionState = ['\"]connected['\"]\s*\|\s*['\"]disconnected['\"]`，**没有尾锚** → 在 union 末尾追加 `| 'reconnecting'` 仍然匹配，这两条不挡本片。
  - `tests/test_gate_t027_baseline.py` 里已搜不到 `only_two_states` → T027 的 s30 过渡断言**已退役**；`tests/test_gate_t032_baseline.py:114-131` 的禁改名单**已不含** `src/live/connection.ts`、`App.tsx`、`shell/PageFrame.tsx`、`live/transport.ts`、`live/mode.ts`（`:115-116` 注明是站主 2026-11-13 按名字退的）→ 本片**不写任何退役要求**。
  - `tests/test_gate_t009_baseline.py:136-137` — 三页可从 api 取的读函数白名单：`getStatus`、`getHistory`、`getMeta`、`getMetaNow`、`getRoles`、`getProfiles`、`getPresets`、`diffPresets`、`getRuntimes`；`:864-893` — `load` 与 `isEmpty` 必须是命名的模块级函数、只用读函数。
  - `tests/test_gate_t034_baseline.py:284-296`（s08 总览页接线）、`:339-363`（s12 源码守卫：OverviewPage.tsx 等文件里不许有四个浏览器网络接口名、注入词、`role=status`、内联 style、十六进制颜色）。
  - `tests/test_gate_t034_baseline.py:114-117`（s09）、`:258-266`（s06 胶囊三取值）、`:366-397`（s13 mode.ts 导出四个 + getMetaNow 不变）。
  - `tests/test_gate_t011_baseline.py:2989-2995`（S2：网络词只许出现在 `src/live/`，注入词到处都不许有）、`:2069-2100`（事件跟随探针：夹具模式卸载后 `vi.getTimerCount()` 为 0）。
  - `desktop/web/tests/tasks-static.test.ts` — `src/pages/tasks/` 恰 17 个文件、TasksPage 保留 `PageFrame` 与 `from './tasks/'` 与默认导出；TasksPage.tsx 也在「禁网络词/注入词/内联 style」扫描名单里（按原文扫，注释也算）。
- 仓库外事实（站主 2026-11-13T11:31Z 已核实，本合同当事实用）：
  1. 浏览器读不到 `retry:` 的值，也读不到非 200 响应（如 503）的状态码与 `Retry-After`；503 之后 `readyState` 为 CLOSED、不自动重连（断开的 200 流会照 retry 自己重连，带 `Last-Event-ID`）。
  2. 同源请求自动带 HttpOnly 会话 cookie，客户端不写凭据头。
  3. `event: snapshot` / `event: update` 只派发给同名的 `addEventListener`，不触发 `onmessage`；`lastEventId` 是 `id:` 行的值。
  → 退避下限写成常量 3000ms（对齐服务端的 `retry: 3000`，也覆盖 503 的 `Retry-After: 2` 秒），不做 `Retry-After` 解析。
- 规划报告与新基线不一致之处（以新基线为准）：规划报告第 8 节问「T034 是否已改 `connection.ts`、是否已加 `reconnecting` 与次数」——新基线上**都没有改**（见上），所以本片第 2 步是「在末尾追加 + 加导出」，不是「并入已有实现」；规划报告第 5.1 节说要退 T027 s30 与 T032 s09 的 `connection.ts` 项——新基线上**已经退了**，本片不再要求退役。

## Scope
- allowed_modified_files:
  - desktop/web/src/live/connection.ts
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
- allowed_new_files:
  - desktop/web/src/live/events.ts
  - desktop/web/src/live/useLiveStatus.ts
  - desktop/web/tests/live-events.test.ts
  - desktop/web/tests/live-events-hook.test.tsx
  - desktop/web/tests/live-pages-live.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t036_*.py
  - desktop/web/src/App.tsx
  - desktop/web/src/api.ts
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/shell/useShellConnection.ts
  - desktop/web/src/shell/TitleBar.tsx
  - desktop/web/src/shell/TabBar.tsx
  - desktop/web/src/live/mode.ts
  - desktop/web/src/live/transport.ts
  - desktop/web/src/components/**
  - desktop/web/src/pages/tasks/**
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/mock/**
  - desktop/web/vite.config.ts
  - desktop/web/scripts/check-live-build.mjs
  - desktop/web/package.json
  - ts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 补充规则（写在范围里，路径同上）：`desktop/web/tests/` 下**已有的**测试文件一个都不许修改或删除（只许新增上面列的三份新测试）。

## Behavior contract
- 正常输入：
  - **事件流客户端 `desktop/web/src/live/events.ts`**（对外接口按此写死，执行端可调整内部实现，不得改这些名字与语义）：
    - `export interface LiveStreamEvent { readonly type: 'snapshot' | 'update'; readonly lastEventId: string; readonly data: string; }`
    - `export interface LiveStreamHandle { addEventListener(type: 'snapshot' | 'update', listener: (event: LiveStreamEvent) => void): void; removeEventListener(type: 'snapshot' | 'update', listener: (event: LiveStreamEvent) => void): void; close(): void; }`
    - `export interface LiveEventsOptions { createStream: () => LiveStreamHandle; setTimer?: (fn: () => void, delayMs: number) => unknown; clearTimer?: (handle: unknown) => void; random?: () => number; }`
    - `export interface LiveEvents { subscribe(listener: () => void): () => void; getStatus(): StatusData | null; getReconnectCount(): number; }`
    - `export function createLiveEvents(options: LiveEventsOptions): LiveEvents` —— 纯逻辑、可注入假流与假计时器，**不看真实模式**（真实模式的判断在默认实例里）。
    - `export const liveEvents: LiveEvents` —— 默认实例：`createStream` 默认建 `new EventSource('/api/v1/events')`（同源相对路径，不带凭据头）；`subscribe` 在 `liveModeIsReal()` 为假时**直接返回空操作**（不登记监听者、不建流、不排计时器）；`liveModeIsReal()` 为真时才登记监听者并在**第一个订阅者**到来时建流。
    - `export function setEventStreamFactoryForTests(factory: (() => LiveStreamHandle) | undefined): void` —— 只给包内测试换掉默认实例的建流方式；传 `undefined` 恢复默认。**它不参与开关判断**：开关永远只有 `liveModeIsReal()`。
    - 收事件只用 `addEventListener('snapshot' | 'update')`（不用 `onmessage`）；序号取事件的 `lastEventId`。
    - `snapshot`：整份替换 `status`（不比较序号大小，服务重启后序号变小也照样替换），把序号基线设为该事件的序号，重连次数清零，连接状态写 `'connected'`，通知全部订阅者。
    - `update`：序号（`lastEventId` 解析成的整数）**不大于**已见基线 → 丢弃（不改数据、不推进基线、不通知）；**还没收到过 snapshot** → 丢弃；否则整份替换 `status`、基线设为该序号、通知全部订阅者。
    - 序号解析不出非负整数 → 丢弃该事件（不改数据、不推进基线、不通知）。
    - `ok:false` 的推送（服务超时的七字段信封）：**不覆盖已显示的数据**，序号照常推进，不通知订阅者。
    - 流上 `error` 事件：不论 `readyState` 是 CLOSED 还是 CONNECTING，都 `close()` 掉这条原生流，自己排重连（不与浏览器自带的重连叠加）。
    - 退避：第 n 次重连（n 从 1 起）的等待 = `min(3000 × 2^(n-1), 30000) + floor(random() × 1000)` 毫秒；**永远不小于 3000ms**，抖动只往后加，最大 31000ms。等待期间连接状态写 `'reconnecting'`，重连次数写 n。
    - 重连成功（收到 `snapshot`）：重连次数清零，连接状态写 `'connected'`。
    - 最后一个订阅者离开：关流、清掉待跑的重连计时器、重连次数清零；若离开时连接状态正是 `'reconnecting'`，写 `'disconnected'`（已经没有流在维持连接）；否则不改连接状态。
    - 与 `transport.ts` 对连接状态的写入**以最后一次为准，不加仲裁**（站主定的默认取舍）。
    - 模块加载时无副作用：不建流、不排计时器、不读 `window`。
  - **钩子 `desktop/web/src/live/useLiveStatus.ts`**：
    - `export function useLiveStatus(initial: StatusData): StatusData`
    - 夹具模式（`liveModeIsReal()` 为假）：原样返回 `initial`，不订阅、不建流、不起计时器。
    - 真实模式：订阅事件流；有 `ok:true` 的推送时返回最新的 `StatusData`；还没有推送时返回 `initial`（`initial` 每次渲染都取最新值，不缓存旧值）。内部用 `useSyncExternalStore`，订阅与快照读取都取 `liveEvents` 的稳定引用。
  - **页面接线**：
    - `OverviewPage.tsx`：`loadOverview`、`isOverviewEmpty` 仍是模块级命名函数；`from '../api'` 只引白名单读函数（`getStatus`、`getHistory`、`getMeta`、`getMetaNow`）；不出现带引号的状态码字面量；保留记号 `'—'`、`· kit `、`getMetaNow`、`useShellConnection(`、`const loadOverview`、`const isOverviewEmpty`。首屏仍由 `PageFrame` 一次性读；渲染时把首屏读到的 `status` 用实时的 `status` 覆盖（`history` 仍用首屏读的）；实时值由一个同文件内的小组件承载（组件里调 `useLiveStatus`，不许在 `PageFrame` 的 children 回调里直接调钩子）。
    - `TasksPage.tsx`：保留 `PageFrame`、`from './tasks/'`、默认导出；列表页的 `rows` 用实时 `status` 覆盖；详情页的 `row` 在实时 `status` 里有同 `attempt` 的行时用实时行覆盖，否则保留首屏读到的行；不多加 section；`src/pages/tasks/` 仍恰好 17 个文件。
- 边界输入：
  - 推送的 `data` 不是合法 JSON → 丢弃该事件（不改数据、不推进基线、不通知）。
  - 推送的 `data` 不是七字段信封 → 按 `ok:false` 处理（不覆盖数据、序号照常推进）。
  - 服务重启后序号变小 → `snapshot` 照样整份替换（`snapshot` 不比较大小），基线随之重置。
  - 多个订阅者 → 只有一条流；最后一个订阅者离开才关流。
  - 首屏 `getStatus()` 与事件流同时在跑 → 事件流只覆盖显示，不重复发请求、不轮询。
  - 页面卸载（最后一个订阅者离开）→ 不留计时器、不留流。
- 错误与重试：
  - 流断开（`error` 事件）→ 自己排重连，退避下限常量 3000ms（不解析 `Retry-After`、不读 `retry:` 值）；重连次数按连续失败次数累计，收到 `snapshot` 后清零。
  - 503（订阅数超限）浏览器读不到状态码与 `Retry-After`，客户端只当普通断线处理，走同一套退避。
  - 推送里的 `ok:false` 信封不是错误，是「服务这一次没读到 status」：不覆盖已显示的数据。
- 并发、取消与状态变化：
  - 订阅引用计数：第一个订阅者建流，最后一个退订关流；退订函数必须可重复调用且不抛。
  - 退订即取消：清掉该订阅者的通知；最后一个订阅者离开时清掉待跑的重连计时器。
  - 连接状态写入方有两个（`transport.ts` 与 `events.ts`），以最后一次为准，不加仲裁。
- 兼容性：
  - `connection.ts` 的四个原有导出与 `useSyncExternalStore` 原样保留；`useConnectionState()` 仍返回字符串，值没变不通知。
  - `ConnectionState` 从两取值变三取值：`'reconnecting'` 追加在 union **同一行的末尾**（顺序仍是 `'connected' | 'disconnected' | 'reconnecting'`）。
  - `connection.ts` 新增导出：`getReconnectCount(): number`、`setReconnectCount(next: number): void`、`subscribeReconnectCount(listener: () => void): () => void`（值没变不通知）。重连次数只在这里读，**不经 `useShellConnection` 传给胶囊**。
  - `api.ts` 的读函数、`PageFrame` 的 props、`TabBar` 的计数来源都不变；各页首屏仍一次性读。
  - `src/live/` 下的新文件：网络接口名只许出现在代码里（`src/live/` 是唯一放行网络词的目录），**注释里不写** `fetch` / `XMLHttpRequest` / `EventSource` / `WebSocket` 四个词；注入词（`dangerouslySetInnerHTML`、`innerHTML`、`outerHTML`、`insertAdjacentHTML`、`eval(`、`new Function`、`document.write`、`srcdoc`、`createContextualFragment`、`DOMParser`）在新文件里一处都不许出现（连注释都不许）。
  - `OverviewPage.tsx`、`TasksPage.tsx` 里四个网络接口名与注入词一处都不许出现（连注释都不许），不许 `role=status`、不许内联 `style`、不许十六进制颜色。

## Steps
1. 读 Repository facts 里列的文件（`desktop/web/src/live/{connection,mode,transport}.ts`、`desktop/web/src/shell/{useShellConnection,PageFrame}.tsx`、`desktop/web/src/components/ConnectionPill.tsx`、`desktop/web/src/pages/{OverviewPage,TasksPage}.tsx`、`desktop/web/src/api.ts`），确认签名与基线一致；不一致就停止并报告。
2. 新建 `desktop/web/src/live/events.ts`：按 Behavior contract 写事件流客户端（`LiveStreamEvent` / `LiveStreamHandle` / `LiveEventsOptions` / `LiveEvents` / `createLiveEvents` / `liveEvents` / `setEventStreamFactoryForTests`）。默认实例的 `subscribe` 只用 `liveModeIsReal()` 判断开关；夹具模式返回空操作。
3. 改 `desktop/web/src/live/connection.ts`：`ConnectionState` 的 union 在**同一行末尾**追加 `| 'reconnecting'`（保持 `'connected' | 'disconnected'` 在前）；保留四个原有导出与 `useSyncExternalStore`；新增 `getReconnectCount` / `setReconnectCount` / `subscribeReconnectCount`（值没变不通知）。文件其余部分不动。
4. 新建 `desktop/web/src/live/useLiveStatus.ts`：`useLiveStatus(initial: StatusData): StatusData`，夹具模式原样返回 `initial` 且不订阅，真实模式用 `useSyncExternalStore` 订阅 `liveEvents`。
5. 接线 `desktop/web/src/pages/OverviewPage.tsx`：保留 `loadOverview` / `isOverviewEmpty` 与 api 白名单导入与 T034 s08 的记号；加一个同文件内的小组件承载 `useLiveStatus`，渲染时用实时 `status` 覆盖首屏的 `status`。
6. 接线 `desktop/web/src/pages/TasksPage.tsx`：保留 `PageFrame` / `from './tasks/'` / 默认导出；列表页 `rows` 与详情页 `row` 按实时 `status` 覆盖；不加 section、不动 `src/pages/tasks/`。
7. 新增三份包内测试（假流 + 假计时器，不靠固定等待、不用真实等待）：
   - `desktop/web/tests/live-events.test.ts`：`createLiveEvents` 的纯逻辑用例（序号去重与过期丢弃、服务重启后 snapshot 变小整份替换、退避不低于 3000ms 且抖动只往后加、重连靠 snapshot 重建、多订阅者只一条连接且最后一个离开就关、`ok:false` 推送不覆盖数据、夹具模式不建流不起计时器）。
   - `desktop/web/tests/live-events-hook.test.tsx`：`useLiveStatus` 的用例（夹具模式原样返回 initial 且不订阅；真实模式（mock `../src/live/mode` 的 `liveModeIsReal` 为真）收到推送后返回新 status）。
   - `desktop/web/tests/live-pages-live.test.tsx`：总览页与任务页的接线用例（mock `../src/live/mode`：`liveModeIsReal` 为真、`liveClient` 为 null，使 `api` 走夹具分支；用 `setEventStreamFactoryForTests` 注入假流；推送一条 `update` 后页面上的数字跟着变）。
   - 三份测试都不许出现 `skip` / `only` / `todo`，不许改动任何既有测试文件。
8. 跑 Validation commands 里 V01、V02（必要时加跑 G01 的门禁文件），记录命令与结果。
9. 写执行报告：逐项说明 D01…D14，列出自检命令与结果、遗留问题。

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t036_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`$`

## Definition of done
- D01：事件流只由 `liveModeIsReal()` 决定开不开；夹具模式下订阅不建流、不排计时器；模块加载时无副作用。证据：V01 中 `live-events.test.ts` 的「夹具模式不建流、计时器计数为 0」用例；目的：门禁探针与夹具模式下绝不发请求（T011 :2094 的卸载后计时器为 0 仍成立）。
- D02：第一个订阅者到来才建流，最后一个订阅者离开就关流，多订阅者只有一条流。证据：V01 中 `live-events.test.ts` 的引用计数用例；目的：服务端的订阅数上限（全局 16、每会话 4）不被前端自己撞破。
- D03：`snapshot` 整份替换并重置序号基线；`update` 序号不大于基线就丢弃；服务重启后序号变小照样整份替换。证据：V01 中 `live-events.test.ts` 的序号用例；目的：重复与过期推送不把界面带回旧数据。
- D04：`ok:false` 的推送不覆盖已显示的数据，序号照常推进。证据：V01 中 `live-events.test.ts` 的超时信封用例；目的：服务一次读不到 status 时界面不闪空。
- D05：出错后自己排重连，等待不小于 3000ms、抖动只往后加、上限 31000ms；等待期间连接状态为 `'reconnecting'`、重连次数为 n；收到 `snapshot` 后清零并写 `'connected'`。证据：V01 中 `live-events.test.ts` 的退避用例（假计时器）；目的：不给服务端补 Retry-After 解析也能退避，且界面能说出在重连。
- D06：重连后靠 `snapshot` 重建（整份替换，不合并旧数据）。证据：V01 中 `live-events.test.ts` 的重连用例；目的：重连期间错过的事件不会造成两份数据混在一起。
- D07：`connection.ts` 的 `ConnectionState` 是三取值且 `'reconnecting'` 写在同一行末尾；四个原有导出与 `useSyncExternalStore` 保留；`useConnectionState()` 仍返回字符串、值没变不通知；新增重连次数的读取导出。证据：G01 的静态断言与 V01；目的：不推翻 T027 S05 / T034 s13 的无尾锚正则，也不改坏既有连接状态语义。
- D08：`useLiveStatus` 在夹具模式原样返回 `initial` 且不订阅；真实模式有推送时返回推送的 status。证据：V01 中 `live-events-hook.test.tsx`；目的：夹具模式与首屏行为完全照旧。
- D09：总览页首屏仍一次性读，收到推送后视图里的数字跟着变；`load` / `isEmpty` 仍是模块级命名函数；api 导入仍在白名单内；T034 s08 的记号（`'—'`、`· kit `、`getMetaNow`、`useShellConnection(`、`const loadOverview`、`const isOverviewEmpty`）保留。证据：V01 中 `live-pages-live.test.tsx` 与 G01；目的：接实时不拆掉 T034 已落地的接线。
- D10：任务页列表的 `rows` 与详情页的 `row` 按实时 `status` 覆盖；`PageFrame`、`from './tasks/'`、默认导出保留；`src/pages/tasks/` 仍恰好 17 个文件；不多加 section。证据：V01 与 G01；目的：任务页的运行中进度也是实时的，页结构与文件数不动。
- D11：禁改清单里的文件一个都没动；现有测试文件一个都没改。证据：scope；目的：不越权、不削弱别人的门禁。
- D12：两个页面文件与两个新 `src/live/` 文件里没有四个浏览器网络接口名（连注释）、没有注入词、没有 `role=status`、没有内联 `style`、没有十六进制颜色；`src/live/` 新文件的注释里不写网络接口名。证据：G01 的源码守卫扫描与 V01；目的：不让事件流的实现从页面上漏出去，也不引入注入面。
- D13：三份新测试没有 `skip` / `only` / `todo`；既有测试一个都没删改。证据：scope 与 review；目的：不靠削弱测试换绿。
- D14：`npm test`、`npm run typecheck`、门禁 G01、回归 R01 全绿。证据：V01、V02、G01、R01；目的：改动不破坏既有前端行为与既有门禁。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `connection.ts` 的 union 形状、`mode.ts` 的导出集合、`OverviewPage.tsx` 的 `loadOverview` 与 api 导入与事实里写的对不上）。
- 必须修改允许范围之外的文件才能继续（例如要让总览页接实时就必须动 `PageFrame.tsx` 或 `App.tsx`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 5400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查与复核基线 240s、实现（events.ts + connection.ts + 钩子 + 两个页面接线）900s、补三份包内测试 420s、跑 V01/V02 与回归 180s、写执行报告 60s；总计 1800s，单轮时限 1800s。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261113T101437103779Z-owner-c0c64e：

> 一、本片（T036）只做 A：事件流客户端加实时状态。B1（作业客户端加检索）、B2（日志跟随）站主以后另登记；作业列表走哪条路（只列本窗口建过的，或先补服务端的 GET /jobs），登记 B1 时再定。
>
> 二、两条仓库外事实站主已用真 Electron 44.9.0 实测，都成立（全文 .agent/mailbox/owner-notes/t036-facts-01.md）：EventSource 读不到 retry 与非 200 响应的头，503 之后 readyState 是 CLOSED、不重连；同源请求自动带 HttpOnly 会话 cookie。正式的“已核实”回复（带 --facts-checked）随门禁准备一起发。
>
> 三、A 片的门禁准备等 T034 落地之后在新末端上做：T027 门禁的 test_transitional_s30_connection_only_two_states 站主会退役（T034 的合同明写不做 reconnecting，它不会退这条）；T032 的 p3、T010 的 readers 探针、T011 的 events 探针，以及报告第 5 节只看了计数的文件，站主逐条读过再定。做完、基线挪好之后站主回复；在那之前不开合同端（内核也会挡着）。

站主来信 20261113T113131261665Z-owner-07a6d2：

> 一、已核实（--facts-checked）：规划依赖的 3 条仓库外事实，站主用真 Electron 44.9.0 的 Chromium 实测，全部成立，逐条结果在 .agent/mailbox/owner-notes/t036-facts-01.md：① EventSource 读不到 retry: 的值，也读不到 503 的状态码与 Retry-After；503 之后 readyState 为 CLOSED、不重连（断开的 200 流会照 retry 自己重连，带 Last-Event-ID）；② 同源请求自动带 HttpOnly 会话 cookie；③ event: snapshot / update 只派发给同名的 addEventListener，不触发 onmessage，lastEventId 是 id 行的值。
>
> 二、门禁准备已合入主分支（提交 5825e71）：T027 的 test_transitional_s30_connection_only_two_states 退役；T032 s09 的禁改名单退掉 src/live/connection.ts（同批也为 T034、T037 退了 App.tsx、PageFrame.tsx、transport.ts、mode.ts）。T034 门禁里的 test_transitional_s13_connection_two_states 站主等 T034 落地后退役；它的正则没有尾锚，追加 reconnecting 不会让它红，不挡本片。
>
> 三、站主把规划报告第 9 节只看了计数的命中逐条读过，没有别的必红项；但有一串写法会让门禁变红，见 .agent/mailbox/owner-notes/t036-gate-notes-01.md。请合同端把它们写成硬要求，最要紧的是：事件流只用 liveModeIsReal() 判断开不开、第一个订阅者到来才建、模块加载时不起计时器；connection.ts 的新取值写在同一行末尾；总览页 load/isEmpty 仍是单个标识符；mode.ts、transport.ts、vite.config.ts 不动。
>
> 四、合同端照样等 T034 结项、内核把基线挪到新末端后再开（新末端带上述门禁准备）。

站主来信 20261113T113340823962Z-owner-36c788：

> 你的快照里确实没有 owner-notes。要点贴在下面；合同端能读主工作区，请把两份笔记的路径（.agent/mailbox/owner-notes/t036-facts-01.md、t036-gate-notes-01.md）原样写进给合同端的 brief，让它读全文、照行号复核。
>
> 事实（都成立）：EventSource 读不到 retry 值与非 200 的状态码、头；503 之后 CLOSED、不重连，所以退避下限写常量；同源自动带 HttpOnly cookie；snapshot/update 只派发给同名 addEventListener，lastEventId 是 id 行。
>
> 会让门禁变红、要写成硬要求的写法：
> 1. 事件流只用 liveModeIsReal() 判断开不开；第一个订阅者来了才建 EventSource，最后一个走了就关；模块加载时无副作用、不起计时器；夹具模式不起计时器（T011 :2094 断言卸载后计时器为 0）。不用 liveClient()!==null、T034 钩子的 live、typeof EventSource 判断（T034 p3/p4 注入假客户端、零网络探针数 EventSource 调用）。
> 2. connection.ts 的 'reconnecting' 写在同一行末尾；useConnectionState() 仍返回字符串、值没变不通知。
> 3. 钩子放 src/live/，注释里也不写注入词与网络词。
> 4. OverviewPage：load、isEmpty 仍是单个标识符；从 ../api 只引白名单读函数；不出现带引号的状态码；T034 s08 要的记号（'—'、· kit 、getMetaNow、useShellConnection(、const loadOverview、const isOverviewEmpty）保留。
> 5. TasksPage：保留 PageFrame、from './tasks/'、默认导出；src/pages/tasks/ 恰好 17 个文件；不多加 section。
> 6. 不动 mode.ts（导出恰好 4 个）、transport.ts、vite.config.ts；不新增顶层 *Page.tsx；tasks-data.ts 与 mock/tasks-live.ts 不引 events.ts。
> 7. 重连次数不经 useShellConnection 传给胶囊；真实模式胶囊的“事件流”一行若要改，先问站主（T034 的 p7 要先退役）。
> 8. 新测试不写 skip、only、todo。
