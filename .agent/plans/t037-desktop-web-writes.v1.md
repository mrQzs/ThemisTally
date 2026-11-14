# TASK: t037-desktop-web-writes

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 51a41a994e526a2a4a7199377528301b2b8c2473
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端 Web 渲染层（`desktop/web`）在真实模式下（`liveClient()` 非 null）把写操作接到本机服务的真实路由：`desktop/web/src/api.ts` 的写函数先 `POST /api/v1/preview` 取确认号与预览内容，再在现有确认框里确认，然后带确认号 `POST <写路由>` 执行，断线时用 `GET /api/v1/operations/<确认号>` 查终态；开发与测试模式（`liveClient()` 为 null）照旧走 `desktop/web/src/mock/writes.ts` 的桩。本片同时补齐七端岗位两条写路由（`hub.set`、`hub.unset`）的前端写函数与桩。

## Non-goals
- 不做界面上的「七端岗位」一组入口（M4，下一片）；不改任何页面、组件、写流程状态机（`desktop/web/src/writes/**` 一个字都不动）。
- 不做片 2：`useWriteFlow` 的真实模式门、`needs_yes` 与 `unreadable` 的显示、真实模式的流程集成测试（新测试文件）都不在本片。
- 不改服务端（`ts/**` 一个字都不动）：服务不缺写路由。
- 不改 `desktop/web/src/live/events.ts`、`desktop/web/src/live/useLiveStatus.ts`、`desktop/web/src/live/connection.ts`（事件流片的事）。
- 不改 `desktop/web/src/api.ts` 的 15 个读函数与 `getMetaNow`；不改 `desktop/web/src/mock/` 下的 JSON 夹具；不改 `desktop/web/vite.config.ts`、`desktop/web/package.json`、锁文件。
- 不新增凭据录入、不改 `ts/packages/ui`。
- 不推翻写入口：`desktop/web/tests/page-app.test.tsx:91` 与 `desktop/web/tests/readonly2-app.test.tsx:106` 两条过渡用例不推翻，本片不新开、不改动任何写入口。

## Repository facts
- 入口与现状（逐条读过的文件与行号，基线 9839e86e24）：
  - `desktop/web/src/live/transport.ts` — `createLiveClient(options)` 只回一个 `get` 方法；请求形状 `method: 'GET'`、`credentials: 'same-origin'`、带 `signal`、不带任何凭据头；响应一律归成七字段信封、**绝不 reject**；失败分类的超时文案是 `ERROR: 请求超时（N 秒），没有收到服务的回应`（N = 服务端时限 + 5 秒），断线是 `ERROR: 连不上本机服务（请求没有到达服务）`，401 是 `ERROR: 会话已失效`（并调一次 `reauth`），503 是 `ERROR: 服务繁忙（排队过长），请 N 秒后重试`（读 `Retry-After`，缺省 2），≥400 且正文不是合法信封是 `ERROR: 服务返回 HTTP <码>`，200 但正文不是合法信封是 `ERROR: 服务的响应不是合法的 JSON（HTTP <码>）`；响应状态码本身不外传。
  - `desktop/web/src/live/transport.ts:132` 与 `desktop/web/src/live/transport.ts:153` — `timedOut || (error as Error)?.name === 'AbortError'` **恰好两处**（一处是请求发出后 fetch 抛错，一处是响应体读失败）；T034 的 `test_s09_transport_host_at_call_time` 数这两处，T027 的变异锚点也钉着。
  - `desktop/web/src/live/mode.ts` — `LiveClient` 类型（`:12-14`）只有 `get`；导出集合恰好四个：`liveModeIsReal`、`liveClient`、`setLiveClientForTests`、`LiveClient`（T027 S03、T034 s13、T036 都查这个集合）。`mode.ts` 对 `../api` 只许 `import type`。
  - `desktop/web/src/live/connection.ts` — 三个取值 `'connected' | 'disconnected' | 'reconnecting'` + 重连次数导出（T036 落地后的样子）；本片不改它。
  - `desktop/web/src/api.ts:55` — `WriteAction` 九个成员：`preset.use`、`plugin.enable`、`plugin.disable`、`preset.remove`、`profile.remove`、`runtime.remove`、`config.rollback`、`profile.add`、`profile.edit`。
  - `desktop/web/src/api.ts:83` — 前端 `PreviewData` 八键：`binding_changes: {role,from,to}[]`、`resources: string[]`、`notes: string[]`、`warnings: string[]`、`running_attempts: string[]`、`needs_yes: boolean`、`command: string[]`、`confirmation: string`。
  - `desktop/web/src/api.ts:95` — 前端 `OperationView` 八键：`id`、`action`、`state`（六取值）、`reason`、`created_ms`、`started_ms`、`finished_ms`、`envelope`。
  - `desktop/web/src/api.ts:153` — `unwired<T>()`：真实模式下十个写函数与 `getOperation` 一律回 501 + 固定信封 `ERROR: 写操作尚未接通`（T027 里断言这两行的部分已随站主提交 5825e71 退役）。
  - `desktop/web/src/api.ts:369-449` — `preview`、`getOperation` 与八个写函数；`preview` 的参数是 `WriteArgs`（`Record<string, string | string[]>`）；`rollback(number: number, confirmation)` 的编号是 number；`addProfile`/`editProfile` 的参数是带类型的对象（`credential_env?: string[]`）。
  - `desktop/web/src/writes/useWriteFlow.ts` — 流程对 `api.ts` 的用法：`preview(spec.action, spec.args)` → 确认框内容取 `data.command`（去掉 `--dry-run --json`）、`data.binding_changes`、`data.warnings`、`data.running_attempts`、`data.notes`、`data.confirmation`；执行时 `proceed(classifyWrite(reply.status, reply.body), reply.body, my)`；`preview` 被拒 → 「预览失败：服务没有回应」；执行被拒 → 转去轮询 `getOperation(confirm)`；`getOperation` 的 404 → 「结果未知」。
  - `desktop/web/src/writes/writeOutcome.ts:49` — `classifyWrite(status, body)`：409 且 `exit_code === 4` → stale；409 其他 → expired；503 → busy；400/401/403/413 → rejected；504 → timeout；500 → 服务出错；200 且 ok → 成功（带 WARN 则 successWarn），200 且 ok:false → 按退出码归类。
  - `desktop/web/src/mock/writes.ts:58` — `baseArgv` 按 action 拼基础 argv（`preset.use` → `config preset use <name>`、`config.rollback` → `config rollback <number>`、`profile.add` → `config profile add <p> --runtime=… --model=… [--thinking=…] [--credential-env=…]` 等）。
  - `desktop/web/src/mock/writes.ts:100` — `NEW_ACTIONS` 六个：`preset.remove`、`profile.remove`、`runtime.remove`、`config.rollback`、`profile.add`、`profile.edit`（进 `NEW_ACTIONS` 的 action 才做确认号与参数核对）。
  - `desktop/web/src/mock/writes.ts:110` — `previewData` 按 action 给演示用的 `PreviewData`（`preset.use` 一条 binding 变化、`config.rollback` 最新一条为空、删除类恒空、`resources` 分别是 `roles`/`config`/`profiles`/`plugins`）。
  - `desktop/web/src/mock/writes.ts` 的情景值共 22 个（`ok`…`preview-invalid`），本片不增不减。
  - `desktop/web/tsconfig.json` — `include` 只有 `["src", "vite.config.ts"]`：**`desktop/web/tests/` 不参与 `tsc --noEmit`**，vitest 也不做类型检查；因此 `LiveClient` 的新成员可以是必需成员，`desktop/web/tests/live-mode.test.ts`、`desktop/web/tests/live-readers.test.ts` 里的假客户端不必补、也不许补（不在允许改动集合内）。
  - `desktop/web/package.json` — `"test": "vitest run"`、`"typecheck": "tsc --noEmit"`、`"build": "tsc --noEmit && vite build"`；依赖用 `desktop/web/package-lock.json`（npm）。
  - 服务端（只读，不改）：`ts/packages/ui/src/writeroutes.ts:39` `PREVIEW_TIMEOUT = 30`、`:41` `WRITE_TIMEOUT = 90`、`:525` `writeRoutes(...)` 的十六个路由：`POST /api/v1/preview`；`POST /api/v1/roles/<role>`；`POST /api/v1/presets/<name>/use|save|remove`；`POST /api/v1/config/rollback/<number>`；`POST /api/v1/plugins/<id>/enable|disable`；`POST /api/v1/profiles/<profile>/add|edit|remove`；`POST /api/v1/runtimes/<runtime>/add|remove`；`POST /api/v1/hub/roles/<post>`；`POST /api/v1/hub/roles/<post>/unset`；`GET /api/v1/operations/<id>`。
  - `ts/packages/ui/src/writeroutes.ts` — 预览正文顶层只许 `{action, args}`，多一个键回 400「参数含有未知键」；`args` 的形状由 `validateWriteArgs` 查（`config.rollback` 的 `number` 必须是 JSON 数字；`credential_env` 空数组不合法；`thinking` 只收七档）。执行时路径参数压正文里的同名键，正文里的 `confirmation` 被单独取走（`mergeArgs` 去掉它），服务按确认号记的 argv 与这次请求算出的 argv 逐项比对，不一致回 409「确认号与这次请求的参数不符」；`--expect-state` 与（`needs_yes` 为真时的）`--yes` 由服务自己加，前端不传。执行是同步的（`await op.run`），断开连接不取消执行。
  - `ts/packages/ui/src/operations.ts:134` — `operationView` 是八键投影（`id`、`action`、`state`、`reason`、`created_ms`、`started_ms`、`finished_ms`、`envelope`），不套信封；`GET /api/v1/operations/<id>` 找不到时回 404 的错误信封。
  - `ts/packages/ui/src/envelope.ts:46` — `errorResponse(status, message)` 的正文是七字段信封（`ok:false`、`exit_code:null`、`data:null`、`output:[]`、`messages:['ERROR: …']`、`command:[]`、`elapsed_ms:0`）。
  - `ts/packages/ui/src/kernelenvelope.ts:65` — 信封正文七键与前端 `Envelope` 逐字一致；`:40` `displayArgv` 会把 `--expect-state=` 的值换成占位符 `--expect-state=<state>`。
  - `ts/packages/ui/src/redaction.ts:126` — `PREVIEW_ALLOW`：预览 JSON 里 `binding_changes.*.before|after` 只放行 `profile`/`runtime`/`adapter`/`provider`/`model`/`thinking` 六个字段，另放行 `resources.*.changed_keys.*`、`notes.*`、`warnings.*`、`running_attempts.*`；其余字符串按 `redactSecrets` 处理（只有像凭据的值才变 `<redacted>`），键本身不删。
  - 内核预览 JSON 的键集合（`tests/test_kit_roles.py:1551` 钉死）：`action`、`binding_changes`、`changed`、`dry_run`、`needs_yes`、`notes`、`resources`、`running_attempts`、`state`、`unreadable`、`warnings`；服务把顶层的 `state` 拿掉再脱敏。
  - `ts/packages/ui/src/localhttp/guards.ts:60` — `csrfCheck`：POST 必须有 `Origin`（等于 `http://<Host>`）、`X-Themis-UI: 1`、`Content-Type: application/json`；`Origin` 由浏览器自带，前端只补后两个头。
  - `ts/packages/ui/src/app.ts:143` — POST 先过 CSRF 三查，再读正文（上限 64 KiB，超限 413、坏正文 400），然后交给路由处理函数。
  - 服务端**没有**推操作事件（`ts/packages/ui/src` 下的事件路由里没有 operation）：写操作终态不经事件流，只能查 `GET /api/v1/operations/<id>`。
- 门禁口径（新基线上读到的，执行端必须守住）：
  - `tests/test_gate_t027_baseline.py:305-347`（S03）：`desktop/web/src/live/mode.ts` 的导出集合恰好四个、不许 `export *`、对 `../api` 只许 `import type`。
  - `tests/test_gate_t027_baseline.py:350-381`（S04）：`desktop/web/src/live/transport.ts` 要有 `createLiveClient`、`fetch`/`host`/`timeoutMs`/`reauth` 四个选项名、`URLSearchParams`、`AbortController`、`credentials: 'same-origin'`、`Retry-After`、六条定稿文案、`exit_code: null`；对 `./mode` 只许 `import type`。
  - `tests/test_gate_t027_baseline.py:395-414`（S06）：`desktop/web/src/api.ts` 的 13+2 个读函数与十个写函数仍要是 `export function <名>(` 的写法（**不是 `export async function`**），`liveClient` 的用法、`currentMock`、`export interface Envelope` 与十一个路由前缀字符串都要在。
  - `tests/test_gate_t027_baseline.py:471-488`（S10）：`desktop/web/src/` 下（除 `desktop/web/src/live/`）任何文件都不许出现 `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词（**注释与字符串也算**）；`desktop/web/src/live/` 下不许出现注入词。
  - `tests/test_gate_t034_baseline.py:297-309`（s09）：`desktop/web/src/live/transport.ts` 里 `timedOut || (error as Error)?.name === 'AbortError'` **恰好两处**，且 `setTimeout`/`clearTimeout` 仍在。
  - `tests/test_gate_t034_baseline.py:312-323`（s10）：`desktop/web/tests/live-transport.test.ts` 的 `it(` 条数只增不减、要有 `window.themisHost`、不许 `skip`/`only`/`todo`。
  - `tests/test_gate_t034_baseline.py:366-389`（s13）与 `tests/test_gate_t036_baseline.py:390`：`desktop/web/src/live/mode.ts` 的导出集合恰好四个；`desktop/web/src/api.ts` 的 `getMetaNow` 仍是同步的 `export function` 且函数体是 `clone(metaJson)`。
  - `tests/test_gate_t022_baseline.py:361-366` 与 `tests/test_gate_t024_baseline.py:240-253`：`desktop/web/src/mock/writes.ts` 的 `WriteScenario` 成员不少于 22 个、`preview-warn` 与 `preview-invalid` 在、两个 profile action 在 `NEW_ACTIONS` 附近——本片不删不改这些，只加两个 hub action。
  - 站主已退役的断言（提交 5825e71，含在基线里）：T027 的 s32、p6 的写函数那一半、s06 里查「写操作尚未接通」与 `\b501\b` 的两行、s01c 的「写操作尚未接通」记号、T032 的 s09 的 `desktop/web/src/live/mode.ts` 与 `desktop/web/src/live/transport.ts` 两项。**本片不再要求任何退役。**

## Scope
- allowed_modified_files:
  - desktop/web/src/live/transport.ts
  - desktop/web/src/live/mode.ts
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-api.test.ts
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t037_*.py
  - desktop/web/src/writes/**
  - desktop/web/src/pages/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/live/events.ts
  - desktop/web/src/live/useLiveStatus.ts
  - desktop/web/src/live/connection.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/tests/*.test.tsx
  - desktop/web/tests/writes-flow.test.tsx
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/live-readers.test.ts
  - desktop/web/tests/live-connection.test.ts
  - desktop/web/tests/live-events.test.ts
  - desktop/web/tests/live-events-hook.test.tsx
  - desktop/web/tests/live-pages-live.test.tsx
  - desktop/web/tests/live-app.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/vite.config.ts
  - desktop/web/scripts/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/tsconfig.json
  - ts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 补充规则（写在范围里，路径同上）：`desktop/web/tests/` 下**除上面列出的两份以外**的测试文件一个都不许修改或删除（`desktop/web/tests/page-app.test.tsx`、`desktop/web/tests/readonly2-app.test.tsx` 的两条写入口过渡用例不推翻、不改写）。

## Behavior contract
- 正常输入：
  - **传输层（`desktop/web/src/live/transport.ts`）**：`createLiveClient` 回的对象在现有 `get` 之外多两个方法，`LiveClient` 类型（`desktop/web/src/live/mode.ts`）同步多这两个成员（**只加类型成员，不新增任何导出**；导出集合仍是 `liveModeIsReal`、`liveClient`、`setLiveClientForTests`、`LiveClient` 四个）：
    - `post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: T }>`
    - `getRaw<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }>`
    - `post` 的请求形状：`method: 'POST'`、`credentials: 'same-origin'`、带 `signal`、headers 里 `Content-Type: application/json` 与 `X-Themis-UI: 1`（`Origin` 由浏览器自带，**前端不拼**）、正文是 `JSON.stringify(body)`；不带任何凭据头。
    - `getRaw` 的请求形状与现有 `get` 一样（`method: 'GET'`、`credentials: 'same-origin'`、查询用 `URLSearchParams` 拼），只是**不把正文归成信封**，而是把解析出来的 JSON 原样交回去。
    - 时限：客户端中止时刻 = 传入的服务端时限 + 5 秒（与现有 `get` 同一套机制）；请求结束（成功或失败）后不留计时器。
    - 连接状态：拿到任何 HTTP 响应（含 4xx/5xx）写 `'connected'`；连接不上或读体失败写 `'disconnected'`（与现有 `get` 同一套）。
    - `post`/`getRaw` 的**状态码原样返回**（这是与现有 `get` 最大的不同：`get` 只给信封，写流程要靠状态码分类）。
    - 正文是合法七字段信封时，body 就是这个信封；正文不是合法信封时，合成一个失败信封（`ok:false`、`exit_code:null`、`data:null`、`output:[]`、`messages:['ERROR: 服务返回 HTTP <状态码>']`（≥400）或 `['ERROR: 服务的响应不是合法的 JSON（HTTP <状态码>）']`（200））、`command:[]`、`elapsed_ms:0`），状态码仍是服务给的那个。
    - 401：先调一次 `reauth`（与现有 `get` 同一套并发去重：在一途的大家共用，兑现后清空），然后返回 `{ status: 401, body: 合成失败信封，messages 固定为 ['ERROR: 会话已失效'] }`。
    - 503：状态码 503 原样返回；正文是合法信封就原样用（服务自己的话，如「服务繁忙，请稍后重试」「服务正在关闭」），否则合成 `messages: ['ERROR: 服务繁忙（排队过长），请 N 秒后重试']`（N 读 `Retry-After`，缺失或不是非负整数时 2）。
    - **没有回应**（fetch 抛错且不是我方中止、或读体失败、或我方超时中止）：`post` 与 `getRaw` **reject**（`Error`，文案沿用现有定稿文案：超时 `ERROR: 请求超时（N 秒），没有收到服务的回应`、断线 `ERROR: 连不上本机服务（请求没有到达服务）`）；现有 `get` 的行为**一字不变**（照样 resolve 一个失败信封、绝不 reject）。
    - 实现办法（硬要求）：把「取时限 → AbortController → 发请求 → 读正文 → 写连接状态」抽成**一个内部请求函数**，`get`、`post`、`getRaw` 三个公开方法都走它；`timedOut || (error as Error)?.name === 'AbortError'` 在整个 `desktop/web/src/live/transport.ts` 里**恰好两处**（都在这个内部函数里），不得为 `post`/`getRaw` 复制或新加这一段判定；内部函数不引入新的超时路径（要另加超时路径先问站主）。
  - **`desktop/web/src/live/mode.ts`**：只改 `LiveClient` 类型（加上面两个成员）；三个函数与 `declare const __THEMIS_LIVE_MODE__`、`BUILD_MODE` 一字不改；不新增导出、不 `export *`；对 `../api` 仍只许 `import type`。
  - **`desktop/web/src/api.ts` 的真实分支**（`liveClient()` 非 null 时；`liveClient()` 为 null 时一律照旧走 `desktop/web/src/mock/writes.ts` 的桩，桩的行为本片不改）：
    - **参数整理**（一个函数，预览与执行共用）：`WriteArgs` 的每个键——值是数组且为空 → 不传这个键；值是空串 → 不传这个键；键名是 `number` → 值转成 JSON 数字（转不成就原样传，服务会回 400）；其余键值原样传（数组按顺序原样传，不拼成字符串）。
    - **预览** `preview(action, args)`：`POST /api/v1/preview`，正文 `{ action, args: 整理后的参数 }`，服务端时限 30 秒。成功（200 且 `ok` 为真且 `data` 是对象且 `data.confirmation` 是字符串）时，把 `data.preview` 映射成前端的 `PreviewData` 并保留信封其余字段：
      - `binding_changes`：服务的每项是 `{ role, before, after }`，`before`/`after` 是 `null` 或 `{ mode, profile, runtime, adapter, provider, model, thinking }`；映射成 `{ role, from, to }`，`from` = `before` 的显示值、`to` = `after` 的显示值。
      - 显示值规则：值是 `null` → `—`；否则 `profile` 非空 → `profile`；否则 `provider` 与 `model` 都非空 → `provider/model`；只有一个非空 → 那一个；否则 `mode` 非空 → `mode`；再否则 → `—`。
      - `resources`：取服务每项的 `resource` 字符串，按服务给的次序，不去重。
      - `notes`：服务的 `notes` 后面接 `unreadable`（`unreadable` 并进 `notes`；前端形状里没有单独的 `unreadable` 键）。
      - `warnings`、`running_attempts`、`needs_yes`：服务给什么就是什么。
      - `command`：取**信封顶层**的 `command`（带 `--dry-run --json`），不取预览 JSON 里的东西。
      - `confirmation`：服务的 `data.confirmation` 原样。
      - 预览不成（状态码不是 200、`ok` 为假、`data` 缺 `preview` 或 `confirmation`、正文不是合法信封）时，状态码与信封原样透传（只把 `ok:false` 的合成信封按上一条的合成规则补上），不签发确认号、不改写成 501。
    - **操作查询** `getOperation(id)`：`GET /api/v1/operations/<encodeURIComponent(id)>`，服务端时限 30 秒，用 `getRaw` 走。200 时把正文按八键取成 `OperationView`（`id`、`action`、`state`、`reason`、`created_ms`、`started_ms`、`finished_ms`、`envelope`；`envelope` 不是合法七字段信封就取 `null`；正文不是对象或缺 `state` 就 `data` 取 `null`），并包成 `{ ok: true, exit_code: 0, data: 该视图, output: [], messages: [], command: [], elapsed_ms: 0 }`；404 时状态码与信封原样透传；其他状态码原样透传。
    - **十个写函数**（`usePreset`、`setPluginEnabled`、`removePreset`、`removeProfile`、`removeRuntime`、`rollback`、`addProfile`、`editProfile`、`setHubRole`、`unsetHubRole`）：真实模式下发 POST，路径与正文按下表；服务端时限 90 秒；正文是「路径参数以外的参数 + `confirmation`」，路径参数**不重复传**（服务从路径取值并压过正文）；路径段一律 `encodeURIComponent`；返回 `{ status: 服务给的状态码, body: 服务给的信封 }` 原样（服务给的正文已是七字段信封）；**没有回应时 reject**（与桩的 `drop-*` 同一约定，`useWriteFlow` 的分类不改）：
      | 前端函数 | action | 预览参数 | 执行路由 | 执行正文（除 confirmation） |
      |---|---|---|---|---|
      | `usePreset(name, confirmation)` | `preset.use` | `{name}` | `POST /api/v1/presets/<name>/use` | 无 |
      | `setPluginEnabled(id, enabled, confirmation)` | `plugin.enable` / `plugin.disable` | `{id}` | `POST /api/v1/plugins/<id>/enable` 或 `/disable` | 无 |
      | `removePreset(name, confirmation)` | `preset.remove` | `{name}` | `POST /api/v1/presets/<name>/remove` | 无 |
      | `removeProfile(profile, confirmation)` | `profile.remove` | `{profile}` | `POST /api/v1/profiles/<profile>/remove` | 无 |
      | `removeRuntime(runtime, confirmation)` | `runtime.remove` | `{runtime}` | `POST /api/v1/runtimes/<runtime>/remove` | 无 |
      | `rollback(number, confirmation)` | `config.rollback` | `{number: number}` | `POST /api/v1/config/rollback/<number>` | 无 |
      | `addProfile(args, confirmation)` | `profile.add` | `{profile, runtime, model, thinking?, credential_env?}` | `POST /api/v1/profiles/<profile>/add` | `runtime`、`model`、`thinking?`、`credential_env?` |
      | `editProfile(args, confirmation)` | `profile.edit` | `{profile, runtime?, model?, thinking?, credential_env?}` | `POST /api/v1/profiles/<profile>/edit` | `runtime?`、`model?`、`thinking?`、`credential_env?` |
      | `setHubRole(args, confirmation)` | `hub.set` | `{post, profile, fallback?}` | `POST /api/v1/hub/roles/<post>` | `profile`、`fallback?` |
      | `unsetHubRole(post, confirmation)` | `hub.unset` | `{post}` | `POST /api/v1/hub/roles/<post>/unset` | 无 |
      - 预览与执行**必须用同一份整理规则**，否则服务按确认号记的 argv 与执行的 argv 对不上，回 409「确认号与这次请求的参数不符」。
      - 两个新增的 hub 写函数的签名：`setHubRole(args: { post: string; profile: string; fallback?: string }, confirmation: string)`、`unsetHubRole(post: string, confirmation: string)`（名字照上面表；站主只说了两个写路由，没定前端函数名）。
    - **`WriteAction` 增两个成员** `'hub.set'` 与 `'hub.unset'`（其余成员不动）。
    - 真实模式下**不再有 501**：`desktop/web/src/api.ts` 里 `unwired<T>()` 这个 501 的分支删掉（连同那句「ERROR: 写操作尚未接通」）；真实模式的十个写函数与 `getOperation` 一律走真实路由。
    - `desktop/web/src/api.ts` 的其余部分（15 个读函数、`getMetaNow`、`Envelope`/`HttpReply`/`PreviewData`/`OperationView`/`BindingChange`/`WriteArgs`/`WriteAction` 的既有形状、夹具分支）一字不改；该文件里**不许出现** `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词（注释与字符串也算，T027 S10）。
  - **桩（`desktop/web/src/mock/writes.ts`）**：加七端岗位两条，桩模式行为与 22 个情景值不变：
    - `baseArgv`：`hub.set` → `['config','hub','set',<post>,<profile>]`（`fallback` 传了才加 `--fallback=<值>`）；`hub.unset` → `['config','hub','unset',<post>]`。
    - `NEW_ACTIONS` 加 `'hub.set'`、`'hub.unset'`（这两个 action 的确认号与参数核对照 B 片那套生效：对象/action/数组顺序/丢项/多了项/号不存在都回 409 且 `exit_code` 为 `null`）。
    - 新增 `mockSetHubRole(args, confirmation)`、`mockUnsetHubRole(post, confirmation)`，走现有的 `confirmWrite`。
    - `previewData` 给两个 hub action 一条分支：`binding_changes` 恒空、`resources` 为 `['hub']`、其余照旧。
    - 其余（`WriteScenario` 的 22 个值、`opActions`/`opArgs`/`opPolls`、其余 action 的预览与执行）不改。
- 边界输入：
  - 预览正文 400（参数不合法/未知键）：状态码与信封原样透传；界面（`useWriteFlow`）按「预览失败 + 内核原文」显示。
  - 预览 500（内核的预览不合格）：原样透传。
  - 预览 503（服务队列满）：原样透传；`useWriteFlow` 按 503 显示「服务繁忙，请稍后重试」。
  - 执行 409 且 `exit_code === 4`（状态已变）：原样透传，`classifyWrite` 认成 stale（要求重新预览）。
  - 执行 409 且 `exit_code` 为 `null`（确认号无效、已过期或已用过）：原样透传，认成 expired。
  - 执行 409「确认号与这次请求的参数不符」：原样透传（同样是 expired）。
  - 执行 503（队列满或服务在关停）：原样透传，认成 busy。
  - 执行 500（起不了内核子进程 / 输出超限）：原样透传，认成「服务出错」。
  - 执行 504（服务侧 90 秒超时）：原样透传，认成 timeout。
  - 操作查询 404（没有这个操作，或号已过期）：状态码 404 与信封原样透传（`useWriteFlow` 认成「结果未知」）。
  - 服务返回的正文不是合法七字段信封：按传输层规则合成失败信封，状态码不变。
  - `credential_env` 是空数组、`thinking` 是空串：不传这个键（服务侧空数组与空串都不合法）。
  - `config.rollback` 的编号：预览与执行都用同一个 JSON 数字（路径段写这个数字的十进制写法）。
- 错误与重试：
  - 传输层不做自动重试；`post`/`getRaw` 遇「没有回应」一律 reject，由 `useWriteFlow` 决定（预览失败 / 转去轮询操作终态）。
  - 401 触发一次 `reauth`（并发去重），`reauth` 的返回值与异常都不冒泡。
  - 前端不解析 `Retry-After` 以外的响应头，不读 `retry:` 的值，不写任何凭据头。
- 并发、取消与状态变化：
  - 传输层：每次请求一个 `AbortController` 与一个计时器，请求结束（无论成败）都 `clearTimeout`；不共享控制器。
  - `post` 与 `getRaw` 的 Promise 只兑现一次；`get` 的既有语义（永不 reject）不变。
  - 本片不改任何并发/取消语义（轮询在 `useWriteFlow` 里，本片不动它）。
- 兼容性：
  - `desktop/web/src/live/mode.ts` 的导出集合仍是四个（T027 S03 / T034 s13 / T036 都查）；`LiveClient` 的 `get` 签名不变；`get` 的返回值形状不变（仍是七字段信封）。
  - `desktop/web/src/api.ts` 的十个写函数与 `getOperation` 的**签名不变**（仍是 `export function <名>(`，不是 `export async function`），只是真实模式下的返回值从 501 变成真实路由的结果；`HttpReply<T>`、`Envelope<T>`、`PreviewData`、`OperationView`、`BindingChange`、`WriteArgs` 的形状不变。
  - 桩模式（`liveClient()` 为 null）的返回值与状态码一字不变：22 个 `?write=` 情景、`mockPreview`/`mockGetOperation`、十个桩写函数的行为照旧；`desktop/web/tests/` 里除那两份以外的用例照旧通过。
  - 前端 `PreviewData.binding_changes` 的 `{role, from, to}` 形状不变（服务那套 `{role, before, after}` 只在 `desktop/web/src/api.ts` 内部映射掉）。
  - `desktop/web/tests/page-app.test.tsx:91` 与 `desktop/web/tests/readonly2-app.test.tsx:106` 两条写入口过渡用例不推翻、不改写（本片不新开、不改动任何写入口）。

## Steps
1. 读 Repository facts 里列的文件（`desktop/web/src/live/{transport,mode}.ts`、`desktop/web/src/api.ts`、`desktop/web/src/mock/writes.ts`、`desktop/web/src/writes/{useWriteFlow,writeOutcome}.ts`、`desktop/web/tests/{live-transport,live-api}.test.ts`、`ts/packages/ui/src/{writeroutes,operations,envelope,kernelenvelope,redaction}.ts`、`ts/packages/ui/src/localhttp/guards.ts`），确认签名与基线一致；不一致就停止并报告。
2. 改 `desktop/web/src/live/transport.ts`：把「取时限 → AbortController → 发请求 → 读正文 → 写连接状态」抽成一个内部请求函数，`get`/`post`/`getRaw` 三个公开方法都走它；`post` 与 `getRaw` 回 `{ status, body }`，`get` 的现有行为一字不变；中止判定仍是恰好两处（站主硬要求）。
3. 改 `desktop/web/src/live/mode.ts`：`LiveClient` 类型加 `post` 与 `getRaw` 两个成员；不新增导出、不改三个函数。
4. 改 `desktop/web/src/api.ts`：写一个参数整理函数（预览与执行共用）；`preview` 与 `getOperation` 接真实路由并做形状映射；十个写函数接真实路由（表在 Behavior contract 里）；`WriteAction` 加 `'hub.set'`、`'hub.unset'`；删掉 501 的 `unwired` 分支与那句「ERROR: 写操作尚未接通」；读函数、`getMetaNow`、夹具分支一字不动；文件里不出现四个网络整词。
5. 改 `desktop/web/src/mock/writes.ts`：`baseArgv` 加两条 hub argv、`NEW_ACTIONS` 加两个 action、新增 `mockSetHubRole`/`mockUnsetHubRole`、`previewData` 给 hub 一条分支；22 个情景值与别的 action 不动。
6. 改 `desktop/web/tests/live-transport.test.ts`：**只追加**新的 describe 块（既有 19 条用例一字不改、不删、不 skip/only/todo）：`post` 的请求形状（POST、`credentials: 'same-origin'`、两个头、正文是 JSON 字符串）、200 与合法信封、401（reauth 恰好一次、固定文案）、503（服务自己的信封原样）、504 原样、正文不是合法信封时的合成信封、断线 reject、假计时器下的超时 reject（文案带秒数）、`getRaw` 的 200 八键对象与 404 信封。
7. 改 `desktop/web/tests/live-api.test.ts`：把「写函数与 getOperation 回 501」那一个 describe 换成真实分支的用例（假客户端记录 `post`/`getRaw` 的路径、正文、时限，并可编排返回值）：预览的请求路径/正文/参数整理规则（`number` 变数字、空串与空数组不传）、预览成功后的 `PreviewData` 映射（`from`/`to` 的显示格式、`resources`、`notes` 并入 `unreadable`、`command` 取信封顶层、`confirmation`）、预览失败的透传（400/500/503）、`getOperation` 的 200 八键视图与 404 透传、十个写函数的路径/正文/时限（90 秒）、真实模式不再回 501；文件里其余 describe（15 个读函数、归一化、夹具分支）一字不改。
8. 跑 Validation commands 里的 V01、V02（必要时加跑 G01 的门禁文件），记录命令与结果。
9. 写执行报告：逐项说明 D01…D14，列出自检命令与结果、遗留问题。

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t037_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t036_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`$`

## Definition of done
- D01：传输层有 `post` 与 `getRaw` 两个方法，`post` 的请求形状是 POST + `credentials: 'same-origin'` + `Content-Type: application/json` + `X-Themis-UI: 1` + JSON 正文，不带凭据头；两者都回 `{ status, body }`（状态码原样）。证据：V01；目的：服务的 CSRF 三查（Origin + X-Themis-UI + Content-Type）过得去，写请求不会在门口被 403/415 拦下。
- D02：传输层把「没有回应」（断线、读体失败、我方超时）表达成 `post`/`getRaw` 的 reject，`get` 仍回失败信封、绝不 reject；超时文案与连接状态（disconnected）照现有定稿文案。证据：V01、G01；目的：`useWriteFlow` 的「预览失败：服务没有回应」与「转去轮询操作终态」这两条路在真实模式下走得通。
- D03：`desktop/web/src/live/transport.ts` 里 `timedOut || (error as Error)?.name === 'AbortError'` 恰好两处，`setTimeout`/`clearTimeout` 仍在，`get` 的六条定稿文案一字不改。证据：G01、V01；目的：不推翻既有门禁对这两处的计数与写法要求（T027 的变异锚点钉着这两处）。
- D04：`desktop/web/src/live/mode.ts` 只改了 `LiveClient` 类型的成员，导出集合仍是四个，三个函数一字不改。证据：G01、V01；目的：不推翻三处门禁对导出集合的断言（探针会 mock 掉整个模块，多导出会缺符号）。
- D05：真实模式下 `preview` 发 `POST /api/v1/preview`，正文是 `{action, args}`，参数按整理规则（`number` 变数字、空串与空数组不传）；成功时 `data` 映射成前端的 `PreviewData`（`binding_changes` 的 `{role, from, to}` 与显示格式、`resources`、`notes` 并入 `unreadable`、`warnings`、`running_attempts`、`needs_yes`、`command` 取信封顶层、`confirmation`）。证据：V01；目的：确认框里显示的是服务真的预览，不是桩编的。
- D06：真实模式下 `getOperation` 走 `GET /api/v1/operations/<id>`，200 时 `data` 是八键 `OperationView`，404 与失败状态码原样透传。证据：V01；目的：断线后的终态查得到，「结果未知」与「过期」两条路分得开。
- D07：真实模式下十个写函数各走自己的真实路由（路径、正文、时限 90 秒照 Behavior contract 的表），路径段 `encodeURIComponent`，预览与执行用同一份整理规则；没有回应时 reject。证据：V01；目的：确认过的操作真的在服务上执行，且参数与预览时逐项一致（否则服务回 409「参数不符」）。
- D08：`desktop/web/src/api.ts` 里不再有 501 分支与「ERROR: 写操作尚未接通」；15 个读函数、`getMetaNow`、既有类型与夹具分支一字不改；十个写函数仍是 `export function <名>(` 的写法；文件里没有四个网络整词。证据：G01、V01；目的：不推翻既有门禁对 api.ts 形状与网络词扫描的断言，也不动既有读路径。
- D09：桩模式照旧：`desktop/web/src/mock/writes.ts` 的 22 个情景值与既有 action 的行为不变；新增 `hub.set`/`hub.unset` 的 argv、`NEW_ACTIONS` 成员、两个桩写函数与预览分支。证据：V01、G01；目的：开发与测试模式不受影响（既有门禁对情景数与新增 action 的断言仍成立），同时七端岗位两条在桩里也能走通。
- D10：`WriteAction` 增 `'hub.set'`、`'hub.unset'` 两个成员，其余成员不动；`desktop/web/src/api.ts` 导出 `setHubRole`、`unsetHubRole` 两个写函数。证据：V01、G01；目的：七端岗位的写路由有前端写函数可调（界面入口是下一片的事）。
- D11：`desktop/web/tests/live-transport.test.ts` 只追加用例、既有 19 条一条不改不删；`desktop/web/tests/live-api.test.ts` 里 501 那个 describe 换成真实分支用例、其余 describe 一字不改；两份文件都没有 `skip`/`only`/`todo`。证据：V01、G01、scope；目的：不靠削弱测试换绿（既有门禁对传输层用例条数与禁用词的断言仍成立）。
- D12：改动的文件都在允许集合内（只有那 6 个文件）；禁改清单里的文件一个都没动；没有新增、删除或重命名文件；依赖清单与锁文件没变。证据：scope、review；目的：不越权、不惊动别片。
- D13：`npm test` 与 `npm run typecheck` 全绿。证据：V01、V02；目的：前端既有行为没被写操作接线碰坏，类型也自洽（`LiveClient` 加了成员，`desktop/web/src/` 仍能过 `tsc --noEmit`）。
- D14：门禁 G01 与回归 R01 全绿。证据：G01、R01；目的：既有门禁（尤其对 mode 与 transport 的断言）不被本片推翻。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `desktop/web/src/live/transport.ts` 里中止判定不是两处、`desktop/web/src/live/mode.ts` 的导出集合不是四个、`desktop/web/src/api.ts` 的写函数不是 `export function` 写法、服务路由与表里写的不一样）。
- 必须修改允许范围之外的文件才能继续（例如要让 `useWriteFlow` 认识真实模式、或要让界面显示 `needs_yes`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如预览 JSON 里出现合同没列的键、服务多回一种状态码）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 10800
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与门禁 600s、传输层与 mode.ts 480s、api.ts 的真实分支与映射 900s、桩的 hub 两条 240s、两份包内测试 720s、跑 V01/V02 与门禁 420s、写执行报告 120s；总计 3480s，单轮时限 3600s。

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

站主来信 20261113T110715183469Z-owner-b2b307：

> 一、按两片派：本任务（T037）只做片 1（transport 加 post 与读原始 JSON、mode.ts 的 LiveClient 类型、api.ts 的真实分支与 8 个写函数、七端岗位的两个写函数与 WriteAction 成员、mock/writes.ts 的桩、live-transport 与 live-api 测试）。片 2（useWriteFlow 的真实模式、needs_yes 与 unreadable 的显示、真实模式流程集成测试）等片 1 落地后站主另登记。
>
> 二、门禁准备由站主做，和 T036 的一起，在 T034 落地之后一次提交：T027 的 s32 整条退役；p6 拆开，写函数 501 那一半退役、searchLogs 那一半保留；s06 删掉查“ERROR: 写操作尚未接通”与 \b501\b 的两行；s01c 删掉“写操作尚未接通”这一个记号；T032 s09 名单退掉 src/live/mode.ts 与 transport.ts 两项。站主还会在 T034 落地后的新基线上，把 T034 门禁里管 transport.ts 的断言核一遍。
>
> 三、合同端照样要等 T036 结项、内核挪基线；那时的新基线已经带上门禁准备。站主做完门禁准备会再回一封，在那之前不开合同端。

站主来信 20261113T203010805275Z-owner-975c86：

> 站主补两条硬要求（T034 落地后对着它的门禁核的），请原样写进给合同端的任务书：
>
> 1. `desktop/web/src/live/transport.ts` 里中止判定的这段写法 `timedOut || (error as Error)?.name === 'AbortError'` 要保持恰好两处：新写的 post 走现有的内部请求函数，不复制这段判定。T034 门禁的 `test_s09_transport_host_at_call_time` 数着这两处，T027 的变异锚点也钉着这两处。真要另加一条超时路径，先来问站主（要放宽那条断言）。
> 2. `desktop/web/src/live/mode.ts` 只改 `LiveClient` 类型的成员（加 post），不新增导出：T034 门禁的 `test_s13_live_mode_and_api_untouched` 与 T027 的 S03 都要求导出恰好四个（liveModeIsReal、liveClient、setLiveClientForTests、LiveClient）。
>
> T027 与 T032 门禁里写操作会推翻的过渡断言已经退役（5825e71），基线也已包含。
