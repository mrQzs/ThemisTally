# TASK: t027-desktop-web-live

<!-- v4：按站主 2026-11-12 的拍板（选 A）改三处：
     1) Scope 的 allowed_modified_files 增 desktop/web/tests/readonly2-static.test.ts；
     2) D10 补这份旧测试里那一条断言的改法，Steps 新增对应的执行动作；
     3) Budget：attempt 3（累计已用 1 次、还剩 2）、wall total 21600（累计已用 3512 秒）、per-attempt 7200、花费 12 美元。
     其余条款、allowed_new_files、base_sha（680cf82dc6…）、D10 的转出写法一律不动。

     v3（由 v2 递进）：按一审退回意见改。
     - B2（合同端）：第二节失败分类补「状态码优先」的优先级（第 5/7 条不再互斥）。
     - B3（合同端）：G01 时限 600s → 1800s。
     - B1（归门禁端）：合同侧补齐实现侧要求（mode.ts 运行时引入 transport 的 createLiveClient、
       传输层特征串进产物检查、mode.ts 导出集合固定），并把 G01/V03 挂进 D01/D02。 -->

## Identity
- plan_version: 5
- repository: ThemisTally
- base_sha: d54160087c806cdcd95f9b8e6d8bae5078ecb55a
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
生产构建（`desktop/web` 的 `npm run build` 产物）里，15 个读函数改走同源请求本机服务 `/api/v1/…`（新增 `desktop/web/src/live/{mode,transport,connection}.ts` 三个模块），写操作与 `getOperation` 在真实模式回 501「写操作尚未接通」；开发服务器与测试环境照旧走夹具，`?mock=` 五个取值行为不变；浏览器网络接口只出现在 `desktop/web/src/live/` 下。

## Non-goals
- 不做 SSE（`GET /api/v1/events`）、作业（`POST /api/v1/jobs`，含 `searchLogs` 的真检索）、写路由、凭据录入、`window.themisShell`。
- 不改页面与组件（`App.tsx`、`TitleBar.tsx`、`PageFrame.tsx`、`TabBar`、`OverviewPage` 等）；不改 `ts/packages/ui`、`desktop/shell`、`scripts/**`、`tests/**`、`docs/**`、`schemas/**`。
- 不改夹具：`desktop/web/src/mock/` 下 14 份 JSON 与 `mock/*.ts` 的夹具内容一个字节都不动（`mock/tasks-live.ts` 只许改「真实模式不模拟」这一处行为）。
- `getMetaNow()` 不动：它是同步函数，真实模式拿不到值；首屏异步 meta 属 B 片（规划第 6 节第 8 步）。
- 不做对真服务的冒烟（规划第 9 节），由站主手工跑，不进门禁也不进 DoD。
- 不改 `desktop/web/package.json` 与 `desktop/web/package-lock.json`，不新增任何依赖，不写 `.npmrc`。
- 不改 `desktop/web/tests/cleanup1-static.test.ts`，不改任何 `tests/test_gate_*.py`。
- 不新增 `.d.ts` 类型声明文件（`allowed_new_files` 是封闭清单）；`window.themisHost` 的类型在 `src/live/transport.ts` 里就地解决。

## Repository facts
- 基线：`c1192f038cce877c5b60d7c84eda010f5702fa4e`（站主把 T027 基线从 `734c6b71` 挪到它）。这次提交退役了 T022/T023/T024 三份 api 探针里的 `FORBIDDEN` 名单与检查循环（连同 T024 那条「不许导出 saveProfile、addRuntime、setRole、savePreset」的静态检查），其余断言没动：`desktop/web/`、`ts/packages/ui/`、`scripts/` 在 `734c6b71` 与 `c1192f0` 之间没有变化。**因此 `desktop/web/src/api.ts` 可以导出 `getHistoryEntry`、`getPlugin`。**
- 本片的门禁文件 `tests/test_gate_t027_baseline.py` 由门禁端写（25 条用例 + 6 份自包含探针），内核会把它做成基线提交（在 `c1192f0` 之上，基线提交里已含该文件）；执行端跑 G01 时它必须存在并通过。
- 前端读函数的写法是门禁钉死的：`tests/test_gate_t022_baseline.py:117-118` 的 `API_READS` 是 13 个名字（`getMeta`、`getStatus`、`getAttempt`、`readFile`、`getRoles`、`getProfiles`、`getPresets`、`diffPresets`、`getRuntimes`、`getPlugins`、`getHistory`、`getUsage`、`listSecrets`），`:236` 用正则 `export function {name}\(` 逐个查「原样保留」；写函数的正则允许 async（`:230` 的 `export (?:async )?function {name}\(`）。`getMetaNow` 不在这 13 个之列（它是同步的）。
- 现有实现（`desktop/web/src/api.ts`）：13 个读函数都走 `read(command, produce)` 这条夹具路径（`loading` 返回永不兑现的 Promise、`error` 返回 `ok:false/exit_code:2` 的报错信封、`empty` 走 `mock/empty.ts`）；写函数与 `getOperation` 走 `src/mock/writes.ts`；`Envelope<T>` 的七字段是 `ok/exit_code/data/output/messages/command/elapsed_ms`，`exit_code` 已是 `number | null`（`:44-52`）。
- `desktop/web/src/pages/readonly2/common-readers.ts`：`searchLogs`（:59）、`getHistoryEntry`（:80）、`getPlugin`（:90），夹具是 `mock/readonly2-history-entries.ts`（`HISTORY_ENTRIES`）与 `mock/readonly2-plugin-show.ts`（`PLUGIN_SHOWS`）。T010 的三条规则：`tests/test_gate_t010_baseline.py:544-549` 只拦「从 `../api` 的非 type 引入」（转出语句不以 import 开头，不违规）；`:705-717` 要求页面从 `./readonly2/common-readers` 引入这三个函数；`:785-789` 接受 `export { … }` 的转出写法。T010 的 HOIST（`:1061-1085`）把 `../src/api` 与 `../src/pages/readonly2/common-readers` 各 mock 一次，同名函数登记两个 spy，后登记的（common-readers 的）是页面调用的那个。
- `desktop/web/tests/readonly2-static.test.ts:130-133` 只接受 `export function` / `export const` 的**声明**；`tests/test_gate_t010_baseline.py:785-788` 两种都接受（声明，或 `export { … }` 转出里含这个名字）。这份前端测试是 T010 执行端照着门禁抄的、抄窄了——本片把 D10 的转出写法落地时必须同步放宽它（只许放宽那一条断言，见 D10 与 Steps 第 6 步）。
- `desktop/web/tests/shell-no-network.test.ts:36-45`：递归扫 `src/` 下所有文件，按整词找 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`（注释与字符串都算），命中即失败。`tests/test_gate_t006_baseline.py:3325-3341`（d08）要求这个文件里保留自检样本 `prefetchAll`、`fetchedAt`、`globalThis` 并提到那四个网络接口名；`:3332` 的整树扫描已放行 `src/live/`。`tests/test_gate_t011_baseline.py:2982-2999`（S2）扫 `src/` 下所有 `.ts`：网络词只许出现在 `src/live/` 下，注入词（`SINK_WORDS`）到处都不许有。
- 服务侧（`ts/packages/ui/src/readroutes.ts`）：19 条读路由在 `:75-93` 登记，时限常量在 `:22-32`——`META_TIMEOUT=15`、`DEFAULT_TIMEOUT=30`、`FILE_TIMEOUT=60`、`USAGE_TIMEOUT=120`、`SECRETS_TOTAL_TIMEOUT=120`；路由实现在 `:465-631`。客户端中止时限一律取「服务端时限 + 5 秒」，让服务的 504 信封先到（规划第 5.2 节）。
- meta 路由（`readroutes.ts:337-345`）合成 `{version, repo_name}`；`version` 是内核 `--version` 的输出，`scripts/pi_dispatch.py:8629` 是 `version="pi_dispatch %s" % TOOL_VERSION`，`:65` 是 `TOOL_VERSION = "2.12.0"` → 输出一行 `pi_dispatch 2.12.0`。
- file 路由（`readroutes.ts:395-455`）：查询参数 `path`（必填）与 `cursor`（不透明句柄）；服务把内核游标换成随机句柄（`ts/packages/ui/src/cursors.ts:22-40`，43 个 base64url 字符），句柄用一次就失效；内核 409 时回 `CURSOR_409_MESSAGE`（`游标无效或文件已变化，请从头读取`）。前端只把 `next_cursor` 原样带回，不校验形状。
- 十条路由的键核对结果（我核过，出处见「Behavior contract」第四节的表）：服务给的数据与夹具同形，只有两处形状差异——`GET /api/v1/config/history/{n}` 的 config 条目给 `{number, state, note, diff}`（**没有** `resource`），本机文件条目给 `{number, resource, state, before_sha256, after_sha256, note}`（**没有** `diff`）（`scripts/kit_config.py:1312-1341`）；`GET /api/v1/plugins/{id}` 的 `config.allowed_permissions` 在配置里没有 allowed 权限时是 `null`（`scripts/kit_plugins.py:461-516`）。两处都在 api.ts 里归一化，页面结构不动。
- 写流程遇 501：`desktop/web/src/writes/writeOutcome.ts:49-56` 的 `classifyWrite` 没有 501 分支 → 落到末尾的 `{kind:'checkOperation'}`（通用失败），**不走** 409（重新预览/过期）、**不走** 503（繁忙）；`desktop/web/src/writes/useWriteFlow.ts:365-380` 里 `preview` 的 `status !== 200` → `previewFailed`，文案取信封 messages（`errorText`）。
- UI 文档 8.5（`docs/themis-tally-3.0-桌面端-UI设计.md:1050-1056`）：断流后按 1、2、4、8、16、30 秒退避重连（加 0–20% 随机延后）、连续 3 次失败后显示 danger 提示条「与本机服务的连接断开」附 [重新连接]、旧数据保留并标「可能已过期」。这些属事件流与页面接线（B 片与后续 SSE 片），本片一条都不实现，也不削弱它们。
- 工具链与锁文件：Node 24.19.0；`desktop/web` 用 npm + Vite 5.4.11 + Vitest 2.1.8 + TypeScript 5.6.3（`desktop/web/package.json`）；锁文件 `desktop/web/package-lock.json`（lockfileVersion 3），`npm ci` 可复现；`npm test` = `vitest run`，`npm run build` = `tsc --noEmit && vite build`；`vite.config.ts` 的 `test.include` 含 `src`、`tests`、`gate-probe`；`tsconfig.json` 只含 `src` 与 `vite.config.ts`，**不含** `vite/client` 类型（所以 `import.meta.env` 没有类型，要用环境变量必须另加类型声明——本片不用它）。`.gitignore` 已忽略 `desktop/**/node_modules/`、`desktop/**/dist/`、`desktop/web/gate-probe/`。
- 仓库外事实（站主 2026-11-12 在临时工程里实测，照事实用）：
  1. vitest 里缺省 `import.meta.env.PROD` 是布尔 `false`（`MODE` 为 `"test"`）；vite 开发服务器里 `PROD` 为 `false`、`DEV` 为 `true`、`MODE` 为 `"development"`；`vite build` 的产物里 `PROD` 为 `true`，**但只在 NODE_ENV 没设或等于 `production` 时成立**——预设 `development` 或 `test` 时构建照样成功、产物里 `PROD` 为假。
  2. 因此**模式开关不能跟着环境里的 NODE_ENV 走**。仓库内证据：`node_modules/vite/dist/node/chunks/dep-CB_7IfJ-.js:66221` 是 `const isProduction = process.env.NODE_ENV === "production";`，`:66222` 是 `const isBuild = command === "build";`——`command` 与 NODE_ENV 无关。本合同据此把开关定成 vite 配置里的构建期常量（见「Behavior contract」第一节）。
- 基线检查：基线 `c1192f0` 上 `desktop/web` 的既有前端用例与门禁都应通过（R01）；本片的门禁 `tests/test_gate_t027_baseline.py` 由门禁端写、内核做成基线提交，**在纯基线 `c1192f0` 上不存在**（G01 在纯基线上应失败；在内核做的基线提交上应失败于「实现没做」的那些断言）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/pages/readonly2/common-readers.ts
  - desktop/web/src/pages/tasks/tasks-data.ts
  - desktop/web/src/mock/tasks-live.ts
  - desktop/web/tests/shell-no-network.test.ts
  - desktop/web/vite.config.ts
  - desktop/web/tests/readonly2-static.test.ts
  - desktop/web/scripts/check-live-build.mjs
  - desktop/web/src/live/connection.ts
  - desktop/web/src/live/mode.ts
  - desktop/web/src/live/transport.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-connection.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/live-readers.test.ts
  - desktop/web/tests/live-transport.test.ts
- allowed_new_files:
  - desktop/web/src/live/mode.ts
  - desktop/web/src/live/transport.ts
  - desktop/web/src/live/connection.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-connection.test.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-readers.test.ts
  - desktop/web/scripts/check-live-build.mjs
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t027_*.py
  - tests/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/tests/cleanup1-static.test.ts
  - desktop/web/src/mock/*.json
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

### 一、模式机制（`desktop/web/src/live/mode.ts` 与 `desktop/web/vite.config.ts`）

- **开关的定义**：`desktop/web/vite.config.ts` 改成函数形式，按 `command` 定义一个构建期常量：

  ```ts
  export default defineConfig(({ command }) => ({
    base: './',
    plugins: [react()],
    define: {
      __THEMIS_LIVE_MODE__: JSON.stringify(command === 'build' ? 'themis-live-real' : 'themis-live-fixture'),
    },
    test: { /* 原样保留 */ },
  }));
  ```

  两个标记串**逐字**是 `themis-live-real` 与 `themis-live-fixture`。**不许**改成 `import.meta.env.PROD`、`process.env.NODE_ENV` 或任何跟环境变量走的判据（vite 的 `PROD` 就是 `NODE_ENV === 'production'` 算出来的，见 Repository facts）。
- `desktop/web/src/live/mode.ts` 的内容：
  - `declare const __THEMIS_LIVE_MODE__: string | undefined;`（本工程没有 `vite/client` 类型，不能用 `import.meta.env`）。
  - 模块内求值一次：`const BUILD_MODE = typeof __THEMIS_LIVE_MODE__ === 'string' ? __THEMIS_LIVE_MODE__ : 'unknown';`——兜底值**不许**是 `themis-live-fixture`（否则产物里会出现这个串，三取值构建检查就分不出真伪）。
  - **必须运行时引入传输层**：`import { createLiveClient } from './transport';`（运行时导入，不是 `import type`）。真实模式下 `liveClient()` 返回的缺省客户端**由 `createLiveClient()` 创建**——不许在 `mode.ts` 里另写一份请求逻辑，也不许 `liveClient()` 在真实模式下恒返回 `null` 或别的空实现。传输层因此会进生产构建的产物。
  - 反向依赖只许走类型：`desktop/web/src/live/transport.ts` 对 `LiveClient` 的引用用 `import type { LiveClient } from './mode';`（**只许 type 导入**），避免 mode ↔ transport 的运行时循环。
  - 导出 `liveModeIsReal(): boolean`：`BUILD_MODE === 'themis-live-real'`。
  - 导出 `liveClient(): LiveClient | null`：
    - 有显式注入就用注入的（**显式注入优先**）：注入值为 `null` 时返回 `null`（明确表示「不发请求」），注入值为 `undefined` 时视为「没有注入」。
    - 没有注入时：`liveModeIsReal()` 为真 → 返回**缺省客户端**（`createLiveClient()` 懒建，第一次用到时才建，模块加载时不碰 `window`）；为假 → 返回 `null`。
  - 导出 `setLiveClientForTests(client: LiveClient | null | undefined): void`：设置/清除测试注入；传 `undefined` 清除。
  - `LiveClient` 的形状：`get<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>>`。`Envelope` 用 `import type { Envelope } from '../api';`（**只许 type 导入**，避免运行时循环依赖）。
  - **`mode.ts` 的导出集合固定为这四个**（`liveModeIsReal`、`liveClient`、`setLiveClientForTests`、type `LiveClient`）：不许多导出别的符号（门禁的 `tasks` 探针会 mock 掉 `../src/live/mode`，多导出会让它的 mock 工厂缺符号）。
- 行为结果：开发服务器（`vite`）与 vitest 里 `liveModeIsReal()` 为假、`liveClient()` 为 `null` → 全部读函数走夹具，零请求；生产构建里为真 → 走真实服务，**`?mock=` 的五个取值一律不生效**。
- **不许**在 `src/live/` 以外的任何文件里出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 这四个整词（连注释与字符串都不许；T011 S2 与 T006 d08 照旧扫整个 `src/`，只放行 `src/live/`）。`src/live/` 下也不许出现注入词（`dangerouslySetInnerHTML`、`innerHTML`、`outerHTML`、`insertAdjacentHTML`、`eval(`、`new Function` 等）。

### 二、传输层（`desktop/web/src/live/transport.ts`）

- 导出 `createLiveClient(options: { fetch?: typeof fetch; host?: { reauth?: () => unknown } | null; timeoutMs?: number }): LiveClient`。
  - `fetch` 缺省取 `globalThis.fetch`，`host` 缺省取 `window.themisHost`——**调用时才取**，模块加载时不取（测试环境没有 `window.themisHost` 也不能炸）。
  - `window.themisHost` 没有类型声明（工程里没有 `window.themisHost` 的 `.d.ts`，也不许新增）：在 `transport.ts` 里用 `declare global { interface Window { themisHost?: … } }` 或 `as any` 之类的方式就地解决，`tsc --noEmit` 要过。
  - `timeoutMs` 给了就用它当本次请求的中止时限；没给就用「路由时限 + 5 秒」。
- `get<T>(path, query, timeoutSeconds)`：
  - `timeoutSeconds` 是**服务端时限**（15/30/60/120，见第四节的表），**+5 秒在传输层做**；调用方（api.ts）传的是服务端时限，不许把「客户端中止」那一列（20/35/65/125）传进来。
  - URL 是**同源相对路径**：`path` 原样（如 `/api/v1/meta`），查询用 `URLSearchParams` 拼（值为 `undefined` 的键不拼）。路径段在 api.ts 侧先 `encodeURIComponent`。
  - 请求：方法 `GET`，`credentials: 'same-origin'`，**不自己拼任何凭据头**（GET 不需要 CSRF 头，cookie 由浏览器自带），带 `AbortController` 的 `signal`。
  - 时限：`AbortController` + 定时器；中止时刻 = `timeoutMs ?? (timeoutSeconds + 5) * 1000` 毫秒；请求结束（成功或失败）都要清掉定时器。
  - **一律 resolve 成 `Envelope<T>`，绝不 reject**（调用方不用补 catch）。
- 失败分类（文案逐字定稿；合成信封一律是 `{ok:false, exit_code:null, data:null, output:[], messages:[<原文>], command:[], elapsed_ms:0}`）：
  - **优先级（先看状态码，再看正文）**：状态码 ≥ 400 的响应**一律不进第 7 条**——401 走第 3 条、503 走第 4 条、其余 4xx/5xx 走第 5 条；第 6 条与第 7 条只用于 2xx 响应。照此判定：500 + 正文 `internal error`（不是合法 JSON）→ `ERROR: 服务返回 HTTP 500`；500 + JSON 但不是七字段信封 → `ERROR: 服务返回 HTTP 500`；200 + 坏 JSON → `ERROR: 服务的响应不是合法的 JSON（HTTP 200）`。
  1. **我方中止（超时）**：`ERROR: 请求超时（N 秒），没有收到服务的回应`，N = 中止秒数（= 路由时限 + 5，例如一般路由 35）。连接状态置 `disconnected`。
  2. **断线**（`fetch` 抛错且不是我方中止）：`ERROR: 连不上本机服务（请求没有到达服务）`。连接状态置 `disconnected`。
  3. **401**：调用宿主的 `reauth()`（见下）后返回 `ERROR: 会话已失效`。**不重发原请求**。没有宿主接口、`reauth` 不存在、`reauth` 抛错或返回 `{ok:false}` 时，同样返回 `ERROR: 会话已失效`（文案一个，不区分原因）。
  4. **503**：读响应头 `Retry-After`（秒）；返回 `ERROR: 服务繁忙（排队过长），请 N 秒后重试`，N = `Retry-After` 的值；`Retry-After` 缺失或不是非负整数时 N = `2`。**不自动重试**。
  5. **其他 4xx/5xx**：正文是合法七字段信封就**原样返回**该信封（服务自己的提示，例如 504 的超时信封、409 的 `游标无效或文件已变化，请从头读取`）；不是合法信封就返回 `ERROR: 服务返回 HTTP <状态码>`（`<状态码>` 是十进制状态码）。
  6. **200 且 `ok:false`**：原样返回该信封（内核报错原文）。
  7. **2xx 且正文不是合法 JSON，或 JSON 但不是七字段信封**：`ERROR: 服务的响应不是合法的 JSON（HTTP <状态码>）`。
- **信封校验**（七字段）：`ok` 是布尔；`exit_code` 是数字或 `null`；`data` 是任意值或 `null`；`output`、`messages`、`command` 是字符串数组；`elapsed_ms` 是数字。七个键**齐全**才算合法。
- **连接状态上报**：收到任何 HTTP 响应（哪怕是 4xx/5xx）都置 `connected`；断线与超时置 `disconnected`。
- **401 的 reauth 去重**：模块内一份「在途 reauth」——并发多个 401 **只调一次** `reauth()`（都等同一个 Promise）；它兑现后清空，下一次 401 再起一次新的。`reauth()` 的返回值与异常都不许冒泡到调用方。

### 三、连接状态（`desktop/web/src/live/connection.ts`）

- 状态取值只有 `'connected' | 'disconnected'`（`'reconnecting'` 留给事件流那一片）。
- 导出：
  - `getConnectionState(): ConnectionState`——初值 `connected`；
  - `subscribeConnectionState(listener: () => void): () => void`——订阅，返回退订函数；状态变化时通知全部订阅者；
  - `useConnectionState(): ConnectionState`——`useSyncExternalStore` 钩子；
  - `setConnectionState(state: ConnectionState): void`——传输层上报用；值没变时不通知订阅者。
- 断线后是 `disconnected`，下一次成功（收到 HTTP 响应）恢复 `connected`。
- 本片**不改任何页面**：胶囊、横幅、TabBar 的 offline 状态都还是走 `shellConnectionState(currentMock())`（那是 B 片的事）。

### 四、`desktop/web/src/api.ts`

- 13 个门禁钉住的读函数**保持 `export function 名字(` 的写法**，真实分支写在原函数体里（不许改成 `export async function` 或 `export const`）；写函数可以写成 `export (async )?function`。
- 每个读函数的体长成：`const client = liveClient(); if (client) { …真实分支… } return read(…夹具分支…);`——夹具分支**逐字保留**原行为（`command` 数组、`loading`/`error`/`empty` 三种开关、深拷贝、报错原文）。
- 真实模式下**一律不读夹具**（不回退到夹具，`?mock=` 的五个取值在真实模式不生效）。
- 路由与时限表（服务端时限取 `readroutes.ts:22-32`；客户端中止 = 服务端时限 + 5 秒，**+5 秒在传输层做**，api.ts 传给 `client.get` 的是**服务端时限**那一列）：

  | 函数 | 路由 | 服务端时限 | 客户端中止 | 归一化 |
  |---|---|---|---|---|
  | `getMeta` | `GET /api/v1/meta` | 15 | 20 | `{version, repo_name}` → `{kit_version, repo_name}`：`version` 以 `pi_dispatch ` 开头就去掉这段前缀，对不上这个格式就原样放进 `kit_version` |
  | `getMetaNow` | — | — | — | **不动**（同步函数，真实模式无值；见 Non-goals） |
  | `getStatus` | `GET /api/v1/status` | 30 | 35 | 原样（真实行里没有 `effort_requested`/`effort_effective` 时前端按「未知」显示，不用改） |
  | `getAttempt` | `GET /api/v1/attempts/{task}/{attempt}` | 30 | 35 | 原样；两个路径段各 `encodeURIComponent` |
  | `readFile` | `GET /api/v1/attempts/{task}/{attempt}/file`（查询 `path`、`cursor`） | 60 | 65 | 原样（`next_cursor` 是不透明句柄，原样带回）；`cursor` 有值才拼 |
  | `getRoles` | `GET /api/v1/roles` | 30 | 35 | 原样 |
  | `getProfiles` | `GET /api/v1/profiles` | 30 | 35 | 原样（`provider`/`model` 可能是 `null`） |
  | `getPresets` | `GET /api/v1/presets` | 30 | 35 | 原样 |
  | `diffPresets` | `GET /api/v1/presets/{a}/diff/{b}` | 30 | 35 | 原样；两段各 `encodeURIComponent` |
  | `getRuntimes` | `GET /api/v1/runtimes` | 30 | 35 | 原样 |
  | `getPlugins` | `GET /api/v1/plugins` | 30 | 35 | 原样 |
  | `getHistory` | `GET /api/v1/config/history` | 30 | 35 | 原样 |
  | `getUsage` | `GET /api/v1/usage` | 120 | 125 | 原样 |
  | `listSecrets` | `GET /api/v1/secrets` | 120 | 125 | 原样（真实项多 `store_mode`、`system_backend` 两键；前端只用 `name`/`used_by`/`source`） |
  | `getHistoryEntry`（新并入） | `GET /api/v1/config/history/{n}` | 30 | 35 | `resource` = 服务给的原值，没有就补 `'config'`；`diff` = 服务给的原值，没有就补 `null`；`before_sha256`/`after_sha256` 有就带 |
  | `getPlugin`（新并入） | `GET /api/v1/plugins/{id}` | 30 | 35 | 原样，但 `config.allowed_permissions` 为 `null` 时归一化成 `[]` |

- `getHistoryEntry` 与 `getPlugin` 的**夹具分支逐字保留** `common-readers.ts` 原来的行为：`command` 分别是 `['config','history','show', String(n)]` 与 `['plugins','show', id]`；报缺时是 `ok:false`、`exit_code:2`、`messages:['ERROR 夹具里没有这份数据：<detail>']`；夹具数据深拷贝。T010 的 readers 探针依赖这些细节。
- 写函数与 `getOperation`（`preview`、`usePreset`、`setPluginEnabled`、`removePreset`、`removeProfile`、`removeRuntime`、`rollback`、`addProfile`、`editProfile`、`getOperation`）在真实模式一律返回 `HttpReply`：`status` 为 `501`，`body` 是 `{ok:false, exit_code:null, data:null, output:[], messages:['ERROR: 写操作尚未接通'], command:[], elapsed_ms:0}`；**不读夹具**。`preview` 的 `data` 恒为 `null`。
- 真实模式的分支怎么判断：`liveClient()` 非 `null` 即真实模式（注入也算）。真实分支里**不许**出现 `currentMock()`。

### 五、`desktop/web/src/pages/readonly2/common-readers.ts`

- 改成转出写法：`export { getHistoryEntry, getPlugin } from '../../api';`
  - **前一条语句必须以分号结尾**（T010 的正则会一路匹配到下一个分号为止）。
  - 本文件里 `searchLogs` 保留原样（夹具分支逐字不动）。
  - `searchLogs` 在真实模式返回「尚未接通」的信封：`{ok:false, exit_code:null, data:null, output:[], messages:['ERROR: 检索尚未接通'], command:<原 command 数组>, elapsed_ms:0}`；**不读夹具**。
- 本文件里也不许出现四个网络接口名。

### 六、`desktop/web/src/pages/tasks/tasks-data.ts` 与 `desktop/web/src/mock/tasks-live.ts`

- `tasks-data.ts`：`readAttempt` 与 `readAttemptFile` 在**真实模式**下**不取夹具兜底**（api.ts 报缺就原样把 api.ts 的信封返回出去）；夹具模式的兜底行为逐字不动。判断真实模式用 `liveModeIsReal()`（从 `../../live/mode` 导入）。
- `mock/tasks-live.ts`：`subscribeMockEvents` 在真实模式**直接返回空函数**（不模拟事件行）；夹具模式逐字不动。
- 这两个文件里不许出现四个网络接口名（T011 S2 扫它们）。

### 七、网络扫描规则（`desktop/web/tests/shell-no-network.test.ts`）

- 只改这一个文件。`:36-45` 的整树扫描改成：**`src/live/` 下的文件放行**（不报），别处照旧照报。
- 补**成对**的自检样本：同一段带网络词的文本，放在 `live/` 路径下不报、放在别处照报（例如 `'src/live/transport.ts'` 与 `'src/api.ts'` 两条）。
- 保留 T006 d08 要求的样本与词：`prefetchAll`、`fetchedAt`、`globalThis` 三个样本不报；`fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个网络接口名仍要在文件里出现（自检与规则都靠它们）。
- `desktop/web/tests/cleanup1-static.test.ts` **不动**。

### 八、并发、取消与兼容性

- 并发：传输层对 401 的 `reauth` 全局去重（并发只调一次）；`get` 之间互不影响。
- 取消：本片没有可取消的长请求；时限到了就用合成信封收场。
- 兼容性：13 个读函数的**名字、参数、返回类型、夹具分支行为**一律不变；`Envelope` 的七字段与 `exit_code: number | null` 不变；页面对 `api.ts` 的调用点一行不改；`common-readers.ts` 对页面仍然导出同样三个函数。

## Steps
1. **读基线**：读 `desktop/web/src/api.ts`、`desktop/web/src/pages/readonly2/common-readers.ts`、`desktop/web/src/pages/tasks/tasks-data.ts`、`desktop/web/src/mock/tasks-live.ts`、`desktop/web/src/writes/writeOutcome.ts`、`desktop/web/src/writes/useWriteFlow.ts`、`desktop/web/src/mock/{scenario,readonly2-history-entries,readonly2-plugin-show}.ts`、`desktop/web/tests/shell-no-network.test.ts`、`desktop/web/vite.config.ts`、`desktop/web/package.json`、`desktop/web/tsconfig.json`、`ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/cursors.ts`、`scripts/kit_roles.py`、`scripts/kit_config.py`、`scripts/kit_plugins.py`、`scripts/pi_dispatch.py:65,8629`、`docs/themis-tally-3.0-桌面端-UI设计.md:1050-1056`、`tests/test_gate_t006_baseline.py:3325-3341`、`tests/test_gate_t010_baseline.py:538-552,705-717,785-789,1061-1085`、`tests/test_gate_t011_baseline.py:2982-2999`、`tests/test_gate_t022_baseline.py:117-118,230,236`、`desktop/web/tests/readonly2-static.test.ts:118-140`、`tests/test_gate_t014_baseline.py:85-93,775-795`。确认符号与形状与本文一致；**不一致就停下并报告**，不要照抄本文的行号。
2. **模式开关**：改 `desktop/web/vite.config.ts`（函数形式 + `define` 常量，两个标记串逐字照抄），新建 `desktop/web/src/live/mode.ts`（第一节：含 `import { createLiveClient } from './transport';` 与固定的四个导出）。
3. **传输层**：新建 `desktop/web/src/live/transport.ts`（第二节，`LiveClient` 用 type-only 导入）与 `desktop/web/src/live/connection.ts`（第三节）。传输层把状态报给连接 store。
4. **api.ts**：按第四节的表给 15 个读函数加真实分支与归一化，meta 映射 `kit_version`，并入 `getHistoryEntry`、`getPlugin`（夹具分支逐字保留）；写函数与 `getOperation` 真实模式回 501。
5. **common-readers.ts**：改成 `export { getHistoryEntry, getPlugin } from '../../api';`（前一条语句以分号结尾），`searchLogs` 保留并加真实模式的「尚未接通」。
6. **旧测试里那一条断言的放宽（只许这一处）**：只改 `desktop/web/tests/readonly2-static.test.ts:130-133` 那个 `for (const name of ['searchLogs', 'getHistoryEntry', 'getPlugin'])` 循环里的**一条断言**——把
   `expect(readers, name).toMatch(new RegExp(`export\\s+(?:async\\s+)?(?:function|const)\\s+${name}\\b`));`
   放宽成与 `tests/test_gate_t010_baseline.py:786-787` **同一条规则**：`searchLogs`、`getHistoryEntry`、`getPlugin` 三个名字按「按声明出现（`export (async )?(function|const) 名字`）」**或者**「`export { … }` 转出里含这个名字」判定，**二者其一即算通过**（例如 `export\\s+(?:async\\s+)?(?:function|const)\\s+${name}\\b` 命中，或 `export\\s*\\{[^}]*\\b${name}\\b` 命中）。
   - 同一用例里其余断言（`data-page-state`、`h1`、`Intl`、对 `api.ts` 只 `import type`）**一字不动**；不删用例、不跳过、不加 skip/only/todo；不动这份文件里的别的用例，也不动别的测试文件。
   - 放宽的是**写法口径**，不是**存在性**：三个名字一个都没导出时仍然必须红；改完自测一次（把三个名字从 `common-readers.ts` 里去掉应当红——若不允许为此改源文件，就在草稿副本上自测后删掉草稿）。
   - 这份文件还有两条门禁约束别踩到（T014：`tests/test_gate_t014_baseline.py:89-93,775-777`）：用例数不得低于 8（不许删用例），文件里必须仍含 `src/icons/index.tsx` 的图标断言。
7. **夹具兜底**：`tasks-data.ts` 真实模式不取夹具；`mock/tasks-live.ts` 真实模式不模拟。
8. **网络扫描**：只改 `desktop/web/tests/shell-no-network.test.ts`（放行 `live/`、成对样本、保留 T006 d08 的样本与四个词）。
9. **补测**（新建，都在 `desktop/web/tests/` 下）：
   - `live-mode.test.ts`：默认（测试环境）`liveModeIsReal()` 为假、`liveClient()` 为 `null`；`setLiveClientForTests(fake)` 后 `liveClient()` 是 fake；`setLiveClientForTests(null)` 后是 `null`；`setLiveClientForTests(undefined)` 后回到缺省（`null`）；**显式注入优先于构建模式**。
   - `live-transport.test.ts`：用注入的假 `fetch` 覆盖——成功（200 + 合法信封）、路径与查询的拼法（含 `encodeURIComponent` 的例子）、时限（假 `fetch` 收到 `signal`，断言中止时刻 = 路由时限 + 5 秒）、断线、超时、401（并发两个 401 只调一次 `reauth`）、没有宿主、reauth 失败、503 带 `Retry-After`、503 不带 `Retry-After`、500 带信封、500 不带信封（→ `ERROR: 服务返回 HTTP 500`）、200 且 `ok:false`、200 + 坏 JSON（→ `ERROR: 服务的响应不是合法的 JSON（HTTP 200）`）、JSON 但不是七字段信封、非法信封（七字段缺一个 / `ok` 不是布尔 / `exit_code` 是字符串 / `messages` 不是数组）——**每条都断言返回的是信封而不是 reject**；另断言 500 + 非 JSON 正文回 `ERROR: 服务返回 HTTP 500`（状态码优先）。
   - `live-connection.test.ts`：初值 `connected`；断线后 `disconnected`；成功一次后 `connected`；订阅者在变化时被通知、没变化时不通知；退订后不再通知。
   - `live-api.test.ts`：注入 fake client，逐个读函数断言**请求的路径、查询与传给 client 的时限是服务端时限**（表驱动的 15 行）；`getMeta` 的 `kit_version` 映射（`pi_dispatch 2.12.0` → `2.12.0`；`3.1` → 原样 `3.1`）；`getHistoryEntry` 的 `resource`/`diff` 归一化两种；`getPlugin` 的 `allowed_permissions: null` → `[]`；写函数与 `getOperation` 真实模式回 501 且信封逐字是 `messages:['ERROR: 写操作尚未接通']`；注入后 `#/…?mock=error` 不影响真实结果。
   - `live-readers.test.ts`：`searchLogs` 真实模式回「尚未接通」；`common-readers` 转出后 `getHistoryEntry`/`getPlugin` 的夹具分支与原来逐字一致（command 数组、报错原文、深拷贝）。
10. **三取值构建检查**：新建 `desktop/web/scripts/check-live-build.mjs`——依次用三种环境构建（NODE_ENV **未设**、`development`、`test`），每次用本地 vite 构建（`node node_modules/vite/bin/vite.js build`），读 `dist/assets/` 下的产物，断言 ① 含 `themis-live-real`、② 不含 `themis-live-fixture`、③ 含 `same-origin`（传输层的特征串，证明传输层进了产物，不是只有 mode.ts 的标记串在）；三种都过就打印一行 `LIVE_BUILD_OK 3/3`，否则非零退出并说明是哪一种取值失败、哪一条断言不成立。构建产物 `dist/` 已被 `.gitignore` 忽略，不要提交。
11. **跑检查并写报告**：跑 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下并报告。
    - **两条硬规矩**：
      1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`。
      2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；测试草稿用完立刻删掉，别留在候选里。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t027_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V03（必要）：`node scripts/check-live-build.mjs` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`LIVE_BUILD_OK 3/3`

说明：G01 的 `tests/test_gate_t027_baseline.py` 由门禁端写好、内核做成基线提交（基线提交已含该文件），纯基线 `c1192f0` 上不存在（纯基线应失败）。G01 会拉起门禁自己的整条流水线（装依赖、跑前端用例、构建、三取值检查、6 份探针），门禁内部给的预算是 1500 秒、最坏路径约 2000 秒，所以它的时限给 **1800 秒**（不要按 600 秒设，机器一慢会被内核按超时杀掉，候选被判负而与实现无关）。R01 是 T001–T026 的门禁回归（基线应通过，门禁机实测约 1100 秒），其中 T006/T010/T011/T022/T023/T024 的前端流水线会自己跑 `npm ci` 与构建。V01/V02/V03 需要 `desktop/web/node_modules`，由 Setup 的 `npm ci` 装好；若 Setup 因无网络失败，在执行报告里写明，V01 仍可由 G01/R01 内部的 npm 流水线覆盖。V02 的 `npm run build` 含 `tsc --noEmit`，新代码必须过严格类型检查。

## Definition of done
- D01：模式开关与 NODE_ENV 无关：`desktop/web/vite.config.ts` 用 `command === 'build'` 定义 `__THEMIS_LIVE_MODE__`（值逐字是 `themis-live-real` / `themis-live-fixture`），代码里没有 `import.meta.env.PROD`、`process.env.NODE_ENV` 之类的环境判据；NODE_ENV 未设、`development`、`test` 三种取值各构建一次，三份产物都含 `themis-live-real` 且都不含 `themis-live-fixture`；**并且三份产物都含传输层的特征串 `same-origin`（证明传输层进了生产产物，不只是 mode.ts 的标记串在）**；证据：V03、V02、G01；目的：站主要求「不管 NODE_ENV 怎么设，`npm run build` 的产物都走真实服务」；只跑一次构建看不出这一点，所以必须是三种取值各一次；产物里若只有标记串而没有传输层代码，说明真实模式没有接上传输层，等于本片 Goal 第一句落空。
- D02：模式语义正确：测试环境与开发服务器里 `liveModeIsReal()` 为假、`liveClient()` 为 `null`、全部读函数走夹具且**零请求**；显式注入（`setLiveClientForTests`）优先于构建模式，注入 `null` 表示不发请求，`undefined` 清除注入；**真实模式下 `liveClient()` 返回的缺省客户端由 `createLiveClient()` 创建**（`mode.ts` 运行时 `import { createLiveClient } from './transport';`，不许恒返回 `null`，不许在 mode.ts 里另写一份请求逻辑）；`mode.ts` 的导出集合只有 `liveModeIsReal`、`liveClient`、`setLiveClientForTests`、type `LiveClient` 四个；证据：V01、G01、V03；目的：既有 nonet 探针（T006/T010/T011）继续成立，真实模式只能由显式注入打开；而真实模式的缺省客户端必须真的来自传输层，否则生产构建里的 15 个读函数仍然走夹具。
- D03：传输层成功路径：同源相对路径、查询用 `URLSearchParams`、方法 GET、`credentials: 'same-origin'`（该字符串出现在生产产物里）、不带任何自定义凭据头；时限 = 服务端时限 + 5 秒（用假 `fetch` 观察 `signal` 与中止时刻；api.ts 传给 `client.get` 的是**服务端时限** 15/30/60/120）；任何情况下都 resolve 成七字段信封，绝不 reject；证据：V01、G01；目的：同源请求不被 CSP `connect-src 'self'` 拦（`ts/packages/ui/src/localhttp/headers.ts:8`），且调用方不用补 catch。
- D04：失败分类逐条可测，且**状态码优先于正文**（≥400 的响应一律不进「不是合法的 JSON」那条；401 走会话失效、503 走繁忙、其余 4xx/5xx 走 `ERROR: 服务返回 HTTP <状态码>`；「不是合法的 JSON」只用于 2xx）：断线、超时（文案带中止秒数）、401（含并发两个 401 只调一次 `reauth`、没有宿主、reauth 失败都回 `ERROR: 会话已失效`）、503（读 `Retry-After`，缺失时 N=2）、其他 4xx/5xx 带合法信封原样返回、不带信封回 `ERROR: 服务返回 HTTP <状态码>`、200 且 `ok:false` 原样返回、200 + 坏 JSON 与非七字段 JSON 回 `ERROR: 服务的响应不是合法的 JSON（HTTP 200）`；证据：V01、G01；目的：每种失败都有确定文案，页面不用猜；两种读法都判不红，执行端不会为了变绿去改代码形状。
- D05：信封校验严格：七字段齐全、`ok` 是布尔、`exit_code` 是数字或 `null`、`output`/`messages`/`command` 是字符串数组、`elapsed_ms` 是数字；任一条不满足就按「非信封」处理；证据：V01；目的：服务改了信封形状时要能立刻看出来，而不是把坏数据当正常数据渲染。
- D06：连接状态：状态只有 `connected`/`disconnected`，初值 `connected`；收到任何 HTTP 响应（含 4xx/5xx）置 `connected`，断线与超时置 `disconnected`；订阅者在变化时被通知、值没变时不通知、退订后不再通知；`useConnectionState()` 用 `useSyncExternalStore`；证据：V01；目的：B 片接页面时有稳定的连接状态源，本片不碰页面。
- D07：15 个读函数的真实分支：注入 fake client 后逐个断言请求的路径、查询与时限（表驱动 15 行），含 `getAttempt('a/b','x?y')` 得到 `/api/v1/attempts/a%2Fb/x%3Fy`、`readFile` 的 `path` 与 `cursor` 进查询、`cursor` 不带时不拼该键；真实模式下不读夹具、`?mock=` 不影响结果；证据：V01；目的：路径与编码错了，服务会回 400 或 404，逐条钉死才看得出来。
- D08：meta 映射：真实模式的 `getMeta()` 把 `{version, repo_name}` 映射成 `{kit_version, repo_name}`，`pi_dispatch 2.12.0` → `2.12.0`，对不上 `pi_dispatch ` 格式时原样放进 `kit_version`；`getMetaNow()` 一字未改；证据：V01；目的：页面读的是 `kit_version`（`App.tsx`、`OverviewPage.tsx`），不改页面就靠这一步对齐。
- D09：写操作与 `getOperation` 在真实模式一律回 `status 501` + `{ok:false, exit_code:null, data:null, output:[], messages:['ERROR: 写操作尚未接通'], command:[], elapsed_ms:0}`，不读夹具；写流程遇 501 走通用失败（`classifyWrite` 的 `checkOperation`），不走 409 重新预览、不走 503 繁忙（`preview` 501 → `previewFailed`，文案是那句报错原文）；证据：V01；目的：写操作这一片还没接，别让用户以为写成功了。
- D10：`common-readers.ts` 改成 `export { getHistoryEntry, getPlugin } from '../../api';`（前一条语句以分号结尾），两个函数的夹具分支逐字保留原行为（command 数组、报错原文、深拷贝），`searchLogs` 保留且真实模式回「ERROR: 检索尚未接通」；T010 的 readers 探针（`:705-717`、`:785-789`、`:544-549`）照旧通过；**并且** `desktop/web/tests/readonly2-static.test.ts:130-133` 那个循环里**只放宽一条断言**——`searchLogs`、`getHistoryEntry`、`getPlugin` 三个名字按「按声明出现（`export (async )?(function|const) 名字`）」**或者**「`export { … }` 转出里含这个名字」判定，二者其一即通过，与 `tests/test_gate_t010_baseline.py:786-787` 同一条口径（放宽的是写法口径，导出存在性仍要查）；同一用例里其余断言（`data-page-state`、`h1`、`Intl`、对 `api.ts` 只 `import type`）一字不动，不删用例、不跳过、不加 skip/only/todo，不动这份文件里的别的用例，也不动别的测试文件；证据：V01、R01；目的：页面仍从 `./readonly2/common-readers` 取这三个函数，页内读法不变，前端那份旧静态用例是照门禁抄窄的，不放宽它就会把既定写法判红。
- D11：`tasks-data.ts` 在真实模式不取夹具兜底（api.ts 报缺就原样返回它的信封），`mock/tasks-live.ts` 在真实模式不模拟事件行；夹具模式的既有行为逐字不变；证据：V01、R01；目的：真实模式下夹具不能冒充真实数据。
- D12：网络扫描规则改成「`src/live/` 放行、别处照报」，并有成对的自检样本；T006 d08 要求的 `prefetchAll`、`fetchedAt`、`globalThis` 三个样本与四个网络接口名仍在文件里；`cleanup1-static.test.ts` 一字未动；`src/live/` 以外没有任何文件出现那四个整词（连注释都不许）；证据：V01、R01、G01；目的：规则变了不是断言变弱——传输层之外的浏览器网络接口仍然一个都不许有。
- D13：门禁与回归全绿：G01 通过；R01 全绿；13 个读函数仍是 `export function 名字(`（门禁 `export function {name}\(` 的正则照旧命中）；`desktop/web/package.json` 与 `package-lock.json` 一个字节没动；`git diff --stat` 里没有任何 `tests/test_gate_*`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**` 的改动；证据：G01、R01、scope；目的：既有门禁是别的片的契约，本片不许削弱。
- D14：范围与卫生：所有修改都在允许集合内（新增的 `src/live/*.ts`、`desktop/web/tests/live-*.test.ts`、`desktop/web/scripts/check-live-build.mjs` 都在 `allowed_new_files`）；没有删除、跳过或弱化既有测试（新测试里不写 skip/only/todo，`desktop/web/tests/readonly2-static.test.ts` 只许改本节写明的那一条断言、用例数不得低于 8、图标断言不得丢）；临时文件照 AGENTS.md 用 `T=$(mktemp -d)` 并在同一命令里 `rm -rf "$T"`；构建产物 `dist/` 不提交；遇到合同与既有测试或门禁冲突时不越界改文件，写进 `contract_conflicts`；证据：scope、review；目的：越界改文件会让范围检查直接判负。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如服务的路由与时限变了、`pi_dispatch --version` 的格式变了、T010/T011/T022 的门禁规则变了）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/**`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`desktop/web/package.json`、`desktop/web/package-lock.json`、`cleanup1-static.test.ts`、夹具 JSON）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 需要新增或升级依赖、写 `.npmrc`、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（本版单次 7200 秒）。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；累计已用 1 次——attempt-001 已跑、内核 check 未过；还剩 2 次）
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600（累计已用 3512 秒；21600 ≥ 3512 + 2×7200 = 17912，留足两次返工）
- cost_budget: 12 USD（只统计；调度器强制次数与墙钟，费用不强制）
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：读基线与核对事实 20 分钟；mode/transport/connection 70 分钟；api.ts 60 分钟；common-readers/tasks-data/tasks-live/网络扫描 25 分钟；五份新测试 70 分钟；三取值构建检查与脚本 20 分钟；必要检查（V01–V03、G01、R01）25 分钟；最终报告 15 分钟；总计约 305 分钟（超过单次时限 120 分钟的部分按「mode/transport → api.ts → 其余」的次序压缩；到时限就把没做完的写进执行报告）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：五份新测试各覆盖了哪些条目、15 个读函数各自的请求路径与时限实测值、三种 NODE_ENV 取值下构建产物的判定结果（含「产物含 `same-origin`」这一条）、`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`、`desktop/web/package.json`、`desktop/web/package-lock.json`。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；新测试里不写 skip / only / todo。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/**`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`；不改 `desktop/web/package.json` 与 `desktop/web/package-lock.json`；不加任何依赖。
- 不在 `desktop/web/src/live/` 以外的任何 `src/**` 文件里出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 整词（注释和字符串都算）；`src/live/` 下不许出现注入词。
- 不把模式开关挂在 `import.meta.env.PROD`、`process.env.NODE_ENV` 或任何环境变量上。
- 不改 `desktop/web/tests/cleanup1-static.test.ts`，不改夹具 JSON，不改 `desktop/web/src/mock/` 下夹具文件的既有内容。
- 不在 `src/live/` 以外发请求；请求只发往同源相对路径，不带自定义凭据头。
- 不新增 `.d.ts` 类型声明文件；`window.themisHost` 的类型在 `src/live/transport.ts` 里就地解决。
- 不许让 `liveClient()` 在真实模式下恒返回 `null`、不许把传输层写成死代码；`mode.ts` 必须运行时引入 `createLiveClient`。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261112T131652124876Z-owner-4b07d9：

> 拍板四件事，并逐条核实了两条仓库外事实。
>
> 1. 拆片：T027 只做 A 片（规划第 6 节第 1–6 步：mode、transport、connection、api.ts 的读函数与写函数的“尚未接通”、common-readers、前端网络扫描改规则）。B 片（第 7–10 步）等 A 片落地后由站主另登记一个主任务，不在 T027 里做。A 片的 attempt 预算 2，花费上限照旧 12 美元。
> 2. 两条过渡断言都已退役，提交 734c6b7，T027 的基线已挪到它（314227e → 734c6b7）：
>    - T006 的 test_transitional_d06_api_only_thirteen_functions：后一半“不许提前声明 LATER_API 里的函数”整份退役（不只是 getHistoryEntry、getPlugin 两个名字；后面的片补订阅、作业与写函数时不用再回来退役），前一半“13 个读函数都在”照旧；
>    - T012 的 test_transitional_d13_app_tsx_only_section_2_3_change：整条退役，app_tsx_problems 与它的门禁自检留着。
> 3. 其余过渡断言（T006 的 d02、p10、d06/d07 探针，T009 的 trans1–3，T010 两条探针，T011 五条）不退役：同意规划的判断，它们测的是夹具模式，开发与测试环境不变。合同端照规划第 10 节逐条核对，真有要推翻的再发“提问”。
> 4. 模式开关不能跟着环境里的 NODE_ENV 走（下面第 2 条事实实测出来的）：合同里写明——不管构建时 NODE_ENV 没设、是 development 还是 test，`npm run build` 的产物都走真实服务；并加一条检查：三种取值各构建一次，产物都是真实模式。机制由合同端定（例如 vite.config 按 command 是不是 build 定义一个常量，或者构建脚本自己固定生产模式），测试环境照旧缺省走夹具、只靠显式注入打开真实模式。
>
> 仓库外事实逐条核实（在仓库外的临时工程里照 desktop/web 的 package-lock 装依赖实测：vite 5.4.11、vitest 2.1.8、jsdom 环境）：
> 1. 成立，并补全了没跑过的那一半。vitest 里缺省 import.meta.env.PROD 是布尔 false、DEV 是布尔 true、MODE 是 "test"；vi.stubEnv('PROD', true) 之后 import.meta.env.PROD 读回来是布尔 true，process.env.PROD 是字符串 "1"；vi.unstubAllEnvs() 之后回到 false。规划不依赖 stubEnv、只靠显式注入，这个设计不用改。
> 2. 前半成立，后半的前提实测会出事。NODE_ENV 没设或等于 production 时，vite build 的产物里 import.meta.env.PROD 为真；NODE_ENV 预先设成 development 或 test 时，vite build 照样成功、不报任何提示，产物里 PROD 为假（只剩夹具那一支）。所以有上面第 4 条。

站主来信 20261112T133711343180Z-owner-63895f：

> 答甲，并核实了那一条仓库外事实。
>
> 1. 选甲（规划第 0.3 节第 1 条的推荐做法）：T022、T023、T024 三份 api 探针的 FORBIDDEN 名单连同检查循环整份退役，不只是删 getHistoryEntry、getPlugin 两个名字；T024 的静态检查“不许导出 saveProfile、addRuntime、setRole、savePreset”一并退役（后面接写操作的片要补它们，不再回来退役）。提交 c1192f0，T027 的基线已挪到它。三条探针其余的断言都没动：13 个读函数与已有写函数“应保留”的检查照旧。站主在临时工作区里用门禁自己的流水线核过：原样三条都过；api.ts 多导出 getHistoryEntry、getPlugin，三条都过；去掉一个读函数（getUsage 改名），T022 那条照旧红。
> 2. A 片照规划把 getHistoryEntry、getPlugin 并进 api.ts。规划第 0.3 节第 4 条（13 个读函数不能改成 async 或 const，真实分支写在原函数体里）写进合同。
>
> 仓库外事实核实（临时工程照 desktop/web 的 package-lock 装依赖：vite 5.4.11、vitest 2.1.8）：
> 1. 成立，带一个限定。vitest 里 import.meta.env.PROD 是布尔 false（MODE 为 "test"）；vite 开发服务器里是 false（实测开发服务器给出的模块里 PROD 为 false、DEV 为 true、MODE 为 "development"）；vite build 的产物里为 true，但只在 NODE_ENV 没设或等于 production 时成立——预设成 development 或 test 时构建照样成功、产物里为 false。所以上一封回复的第 4 条照旧有效：模式开关不能跟着环境里的 NODE_ENV 走，合同里加三种取值各构建一次的检查。

站主来信 20261112T172249548855Z-owner-abd398：

> 选 (A)：合同出第 3 版，只改下面三处，其余条款、base_sha（c1192f038c）、允许新建的文件一律不动。
>
> 事实我核对过了，与来信一致：
> - `desktop/web/tests/readonly2-static.test.ts:130-133` 只接受 `export function` 或 `export const` 的声明；`tests/test_gate_t010_baseline.py:785-788` 两种都接受（声明，或者 `export { … }` 里含这个名字）。这份前端测试是 T010 的执行端照着门禁抄的，抄窄了。
> - `common-readers.ts` 自己的文件头写着“接本机服务后这三个函数并入 api.ts”，所以 D10 的转出写法是原定方向，要改的是这份旧测试，不是 D10。
> - V01 红的只有这一条（1 failed、955 passed）；G01 的 P1 与 R01 的 16 条都是各门禁流水线里的 `npm test` 跟着红，没有别的用例。
>
> 第 3 版合同要改的三处：
> 1. `allowed_modified_files` 加上 `desktop/web/tests/readonly2-static.test.ts`。
> 2. D10 补一句对这份测试的改法，并写进步骤：只改 :130-133 那个循环里的一条断言，让三个名字（searchLogs、getHistoryEntry、getPlugin）都按 `tests/test_gate_t010_baseline.py:786-787` 的同一条规则判定，即“声明或者 `export { … }` 转出里含这个名字，二者其一”。同一个用例里的其余断言（data-page-state、h1、Intl、对 api.ts 只 import type）一字不动；不删用例、不跳过、不动这份文件里别的用例，也不动别的测试文件。
> 3. attempt 预算改为 3（已用 1，还剩 2）；花费上限照旧 12 美元。
>
> 另外两点：
> - s31 的正则：知悉，同意按热修补只改这一条正则。我核对过基线 `desktop/web/src/api.ts:166` 是 `export function getMetaNow(): MetaData {`，原正则不允许右括号与左花括号之间有返回类型。断言的意思不变（同步、签名原样、函数体仍是 clone(metaJson)），不要顺手放宽别的。
> - 候选上重跑检查时，T009 探针的“Test timed out in 5000ms”仍按上一封回复说的已知噪声处理。
>
> 给规划与合同两端的一条提醒（不用为它返工）：以后合同要改某个源文件的导出形态时，先在 `desktop/web/tests/` 里按文件名搜一遍，把断言这个文件写法的测试文件一并列进事实与允许修改范围。门禁里的同一条规则放宽了，不代表前端测试里抄的那一份也放宽了。

## Rework（返工第 1 轮，内核追加）

- 基线 `d54160087c806cdcd95f9b8e6d8bae5078ecb55a` 是 attempt-002 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

B1（执行端）：传输层 `get()` 在「响应头已到、响应体未读完」这一段没有兜底 —— `desktop/web/src/live/transport.ts` 的第二个 try 只有 `finally { clearTimeout(timer) }`、没有 catch，`const body = parseJson(await response.text())` 抛错时异常直接穿出 `get()`，**reject**，而不是合同 §2 与 D03 明写的「一律 resolve 成 Envelope<T>，绝不 reject（调用方不用补 catch）」。
- 具体触发路径（两条，都不罕见）：① 本机服务在写响应体途中被关闭/崩溃（用户重启服务、桌面端拆服务、连接被重置）→ 读体中断，`response.text()` 以 TypeError 拒绝；② 响应头先到、响应体迟迟不到，我方 `timeoutMs`（服务端时限 + 5 秒）到点 → `controller.abort()` 会同时中止响应体流，正在进行的 `response.text()` 以 AbortError 拒绝 → 走不到合同第 1 条「我方中止（超时）」的文案分支。
- 后果：页面拿到的是 PageFrame 的通用错误态（`catch` 分支把 `err` 置 null，界面显示「没有收到服务的回应」），丢掉合同定稿的失败文案；且连接状态在 `setConnectionState('connected')` 之后没有机会改回 `disconnected`，B 片的离线胶囊会显示「已连接」而服务其实已经不在。执行报告里「一律 resolve 成七字段信封，绝不 reject」这句自述因此不成立。
- 现有测试与门禁都测不到：执行端 `tests/live-transport.test.ts` 的假响应是 `text: async () => body`（永不抛错）；战后门禁白盒的 `res()`（whitebox-…py:254-260）同样是 `text: async () => body`；38 条变异里没有一条打这一段，所以「38 抓住 / 0 漏掉」不代表这一段被覆盖。
- 要求（只改这一处，不许放宽别的）：读体失败必须收场成七字段信封、绝不 reject —— 我方中止/AbortError → 合同第 1 条文案 `ERROR: 请求超时（N 秒），没有收到服务的回应`；其余读体错误 → 合同第 2 条文案 `ERROR: 连不上本机服务（请求没有到达服务）`（状态码 ≥ 400 时也可按第 5 条回 `ERROR: 服务返回 HTTP <码>`，但必须 resolve 成信封）；两种都要把连接状态置 `disconnected`。并补用例：假 fetch 的 `text()` 抛错一条、让中止计时器在读体期间到点一条，断言返回的是信封而不是 reject。
