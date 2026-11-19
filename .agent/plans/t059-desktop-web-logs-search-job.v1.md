# TASK: t059-desktop-web-logs-search-job

<!-- 合同 v1：T059「日志页的检索在真实模式下走服务的 search 作业」。
     规划报告：.agent/mailbox/tasks/T059-1-plan/report.md；站主任务书：.agent/mailbox/tasks/T059/brief.md；
     站主答复 20261119T153033194620Z-owner-27bd97（选 (b)：t027 门禁进 allowed_modified_files，四处改法逐处写死）。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照抄。
     本片只动三份文件：common-readers.ts（真实分支）、live-readers.test.ts（包内用例）、tests/test_gate_t027_baseline.py（四处旧断言）。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: fcff2f84aa2439afe58289e20d7c652a91e521ad
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端「日志与用量」页的 [检索] 在真实模式（装进应用、连本机服务）下不再回「ERROR: 检索尚未接通」：`desktop/web/src/pages/readonly2/common-readers.ts` 的 `searchLogs(q, task, max)` 真实模式那一支改成建一个服务的 `search` 作业（`POST /api/v1/jobs`），每 1000 毫秒查一次作业（`GET /api/v1/jobs/<id>`），到终态（succeeded、failed、cancelled、timed_out）时交回作业的七字段信封，或一个固定文案的报错信封；包内测试 `desktop/web/tests/live-readers.test.ts` 改成真检索的用例；`tests/test_gate_t027_baseline.py` 里写明「作业/检索片会推翻」的四处随之改掉或退役。

## Non-goals
- 不做检索的作业卡、取消按钮，也不做离开页面再回来接着看同一个作业（要动 `src/jobs/jobStore.ts`，另排）。
- 不动 `desktop/web/src/api.ts`（`JobKind`、`startJob`、`getJob`、`cancelJob` 一个字不改）、不动 `src/jobs/jobStore.ts`、`JobCard`（T054–T057 的门禁钉着）。
- 不动日志页界面、`logs-SearchPanel.tsx`、`logs-SearchResults.tsx`、`logs-logic.ts`、查看器；不动服务端的作业路由（`ts/packages/ui/src/jobroutes.ts`）。
- 夹具模式那一支（`common-readers.ts` 里 `read(...)` 的调用、`searchCommand`、`missingEnvelope`、`errorEnvelope`、`ERROR_MESSAGE`、`okEnvelope`、`clone`）逐字不动。
- 不新增导出：模块仍只导出 `searchLogs`、`getHistoryEntry`、`getPlugin` 三个（T022 `:707` 给每个函数导出包一层 spy）。
- 不改包内其它测试，不改任何别的门禁基准。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 492c643f）。

### 入口 `desktop/web/src/pages/readonly2/common-readers.ts`（共 93 行）
- `:1-6` 文件头注释：描述三个读函数的信封与 `?mock=` 规则；`:7` `import type { Envelope } from '../../api';`（**只许 import type**：T010 `:544-549`、T027 `api_import_problems` `:237-250`、包内 `readonly2-static.test.ts:123-128` 三处都查这条）；`:8` `import { liveClient } from '../../live/mode';`；`:9` `import { currentMock, type MockMode } from '../../mock/scenario';`；`:10` `import { SEARCH_FIXTURE, SEARCH_PATTERN, type SearchData } from '../../mock/readonly2-search';`。
- `:12` `export { getHistoryEntry, getPlugin } from '../../api';`——逐字保留；**它前一条语句要以分号结尾**（T027 S07 `:425-430` 查这一条，让 T010 的 `[^;]*?` 跨不过去）。
- `:15` `ERROR_MESSAGE`、`:17-19` `clone`、`:21-23` `okEnvelope`、`:25-34` `missingEnvelope`、`:36-38` `errorEnvelope`、`:41-43` `pending`、`:46-50` `read`、`:52-57` `searchCommand`（`['logs','search',q]`，task 为真值时追加 `'--task', task`，再追加 `'--max', String(max)`）：**逐字不动**。
- `:60-75` `export function searchLogs(q: string, task: string | null, max: number): Promise<Envelope<SearchData>>`：`:62` `const command = searchCommand(q, task, max);`、`:63` `const client = liveClient();`、`:64-74` 真实分支（现在直接 resolve 一个固定信封，`messages` 是 `['ERROR: 检索尚未接通']`）、`:76-91` 夹具分支（`read(command, …)`，含 empty、`q !== SEARCH_PATTERN` 报缺、按 task 过滤、按 max 截断与 truncated）。
- 全文件没有 `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词，也不得出现（T027 S10 `:471-488`、T010 `source_guard`、包内 `page-static.test.ts:31` 与 `cleanup1-static.test.ts` 的 FORBIDDEN 都算注释与字符串）。

### 传输层 `desktop/web/src/live/transport.ts` 与 `desktop/web/src/live/mode.ts`
- `mode.ts:16-20` `LiveClient` 四个方法：`get`、`post`、`getRaw`、`postRaw`；`getRaw<T>(path, query?, timeoutSeconds?)` 与 `postRaw<T>(path, body, timeoutSeconds?)` 都回 `Promise<{ status: number; body: T }>`，状态码与正文原样交回。
- `transport.ts:206-236`：`postRaw` 拿不到回应（断线、超时）时 **reject**；401 先 reauth 再回一个 `failure(MSG_401)` 信封（正文是合法七字段信封，messages 是「ERROR: 会话已失效」）；正文不是合法 JSON 时按状态码合成一个失败信封（`envelopeOf`：503 → 「ERROR: 服务繁忙（排队过长），请 N 秒后重试」，≥400 → 「ERROR: 服务返回 HTTP <状态码>」，其它 → 「ERROR: 服务的响应不是合法的 JSON（HTTP <状态码>）」）。
- `transport.ts:44-56` `export function isEnvelope(value: unknown): value is Envelope<unknown>`：七字段严格校验（ok 布尔、exit_code 数字或 null、data 任意或 null、output/messages/command 三个字符串数组、elapsed_ms 数字）。
- `api.ts:46` 就是 `import { isEnvelope } from './live/transport';`（**运行时**引入，不是 import type）——本片照这个先例。

### 服务端作业（`ts/packages/ui/src/jobroutes.ts`、`ts/packages/ui/src/jobs.ts`）
- `jobroutes.ts:31` `JOB_KINDS` 含 `search`；`:74` search 的必填键是 `pattern`、可选键是 `task`、`max`；`:145-152` 正文多一个键回 400「请求体含有未知键」；`:120-136` pattern 要 1–512 码点且不含控制字符、max 要 1–1000 的整数（字符串、小数、布尔都不行）；`:160-161` task 要符合 `TASK_ID_RE`；`:54` search 的时限是 180 秒；`:113-118` 创建与查询的正文都是**不套信封的八键作业对象**。
- `jobs.ts:138-149` `jobView` 的八个键：`id`、`kind`、**`state`**、`reason`、`created_ms`、`started_ms`、`finished_ms`、`envelope`。**作业的状态字段名是 `state`，不是 `status`。**
- `jobroutes.ts:233-246` 终态：`succeeded`（退出 0）、`failed`（退出非 0、invalid-json、spawn-error、output-too-large、closing）、`timed_out`（envelope 是 `timeoutEnvelope`）、`cancelled`（**envelope 为 null**）；`:236` 超时的 envelope 是 `timeoutEnvelope`（`kernelenvelope.ts:83-92` → `envelopeBody` `:64-72` 拼出七字段：`ok`/`exit_code`/`data`/`output`/`messages`/`command`/`elapsed_ms`，**能过 `isEnvelope`**）。
- `jobroutes.ts:63-68` 六类作业的结果白名单全是 undefined（search 也是），所以 `redactJson(parsed, undefined)` 走 `ts/packages/base/src/secrets.ts:259-262` 的 `redactJsonPlain`（`:129-140`）：**只遮敏感键的值，不改键**（只有像令牌的键名才改名，检索结果的 task/attempt/path/line/text 不在其列）。
- `jobroutes.ts:113-118` 创建成功回 **201**；`:269`、`:273` 作业表满或执行器收不了回 **503**；`:289` 查不到作业回 **404**「没有这个作业」（正文是 `errorResponse` 的信封，`messages` 一行「ERROR: 没有这个作业」）。

### 轮询节奏的参照 `desktop/web/src/jobs/jobStore.ts:145-155`
`setTimeout` 链，每次 1000 毫秒，不用 `setInterval`；`:147-149` 终态之后不再排下一次。本片照这个节奏。

### 现有包内测试 `desktop/web/tests/live-readers.test.ts`（共 96 行）
- `:1-2` 文件头注释写着「searchLogs 真实模式回「检索尚未接通」」；`:3-6` 引 vitest、`common-readers` 的三个函数、`setLiveClientForTests` 与 `LiveClient` 类型。
- `:8-21` 假客户端**只写了 `get`**（本片要写全四个方法）；`:23-26` `beforeEach` 设 hash 并注入假客户端；`:28-31` `afterEach` 清注入。
- `:32-51` `describe('searchLogs 真实模式回「检索尚未接通」')` 两条用例（整块要换掉）。
- `:53-95` `describe('转出后的 getHistoryEntry/getPlugin：夹具分支与原来逐字一致')` 三条用例：**原样保留**；记号「夹具里没有这份数据」就在里面（T027 `:111` 认这个记号）。

### 旧门禁 `tests/test_gate_t027_baseline.py`（本片要改的就是这份）
- `:111` `EXECUTOR_TEST_TOKENS` 里 `"live-readers.test.ts": ("searchLogs", "检索尚未接通", "夹具里没有这份数据"),`。
- `:237-250` `api_import_problems`（对 `../api` 只许 import type）；`:417-436` `test_s07_common_readers_reexport`（转出语句、前一条语句以分号结尾、只许 import type、`export function searchLogs(` 在、`:433` 「ERROR: 检索尚未接通」在、夹具报缺文案、ERROR_MESSAGE、SEARCH_PATTERN）。
- `:521-525` `test_transitional_s33_searchlogs_unwired_message`；`:1069-1123` `PROBE_UNWIRED`；`:1201-1209` `PROBE_SPECS` 与 `PROBE_ORDER`；`:1475-1477` `test_transitional_p6_probe_unwired`；`:1370-1373` 流水线按 `PROBE_ORDER` 逐份跑探针（份数是动态的，没有写死的计数）；`:1418-1421` 探针的通过条数按源码里的 `it(` 条数动态算。
- 模块 docstring：`:48-49` 探针清单里的 unwired 一条、`:55`（`:56` 是 s31）`:57` 已退役条目的写法是「（站主 2026-11-13 为 T036 退役）」「（站主 2026-11-13 为 T037 退役）」、`:58` s33 一条、`:60` 探针版的过渡断言一条。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（2.1.8）、`npm run typecheck` = `tsc --noEmit`、`npm run build` = `tsc --noEmit && vite build`（vite 5.4.11）、`npm ci` 装依赖。仓库门禁用 `python -m pytest`。
- `desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动（`dependency_changes: forbidden`；t043/t044/t046/t047/t048/t049/t050 按字节冻结前两份）。
- vitest 2.1.8 的缺省假计时器（`vi.useFakeTimers()` 不带参数）替换 setTimeout、clearTimeout、setInterval、clearInterval、setImmediate、clearImmediate、Date，**不替换微任务**；所以 promise 链照常在微任务里走，测试推进轮询要用 `vi.advanceTimersByTimeAsync`（仓库里已有 46 处 `useFakeTimers`/`advanceTimersByTimeAsync` 在用，t027 门禁 `PROBE_TASKS :1190` 也是这么写的）。

### 冻结检查（规划第 5 节 A1，合同端复核）
按 `scripts/kit_hub.py:3042-3068` 的 `FREEZE_ENTRY_RE`（`键: (字节数, "sha256")`）grep 了 `tests/` 下全部命中，冻结的文件是：`desktop/web/package.json`、`desktop/web/package-lock.json`（t043/t044/t046/t049/t050）、`desktop/web/src/mock/profiles.json` 与 `desktop/web/src/writes/hubChangeLines.ts`（t045）、`desktop/web/src/pages/readonly1/roles-styles.css`、`desktop/web/tests/roles-hub-logic.test.ts`、`desktop/web/tests/roles-hub-turns.test.ts`、`ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/writeroutes.ts`、`ts/package.json`、`ts/bun.lock`（t047）、`desktop/web/src/mock/quizs.ts`、`desktop/web/src/mock/hub-roles.ts`、`desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts`、`desktop/web/tests/live-api.test.ts`（t048）、`desktop/web/src/components/index.ts`、`desktop/web/src/icons/index.tsx`（t009/t013/t014）。**没有任何一条指向 `common-readers.ts` 或 `live-readers.test.ts`**——本片改这两份文件不会让旧门禁的字节冻结变红。

### 基线检查
- 合同端只读、没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的（核对点与行号如上）。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）：本片门禁基准文件（门禁端稍后交付、内核做成基线提交，见 Validation commands 的 G01）在基线上应当失败（断言失败，不是收集失败），既有门禁基准照旧通过；**执行端不必在动手前再跑一遍整套测试**，直接按 Steps 实现，最后跑 Validation commands。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/readonly2/common-readers.ts
  - desktop/web/tests/live-readers.test.ts
  - tests/test_gate_t027_baseline.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t059_*.py
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
  - tests/test_gate_t052_baseline.py
  - tests/test_gate_t053_baseline.py
  - tests/test_gate_t054_baseline.py
  - tests/test_gate_t055_baseline.py
  - tests/test_gate_t056_baseline.py
  - tests/test_gate_t057_baseline.py
  - tests/test_gate_t058_baseline.py
  - desktop/web/src/api.ts
  - desktop/web/src/live/**
  - desktop/web/src/jobs/**
  - desktop/web/src/mock/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/writes/**
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/logs-*.ts
  - desktop/web/src/pages/readonly2/logs-*.tsx
  - desktop/web/src/pages/readonly2/logs-*.css
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/readonly2-logs.test.tsx
  - desktop/web/tests/readonly2-static.test.ts
  - desktop/web/tests/page-static.test.ts
  - desktop/web/tests/cleanup1-static.test.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-connection.test.ts
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 真实模式的 `searchLogs`（`desktop/web/src/pages/readonly2/common-readers.ts`）
- `searchLogs(q: string, task: string | null, max: number): Promise<Envelope<SearchData>>` 的签名与返回类型不变；模块仍只导出 `searchLogs`、`getHistoryEntry`、`getPlugin` 三个（不新增导出；helper 全部留在模块内部、不导出）。
- 夹具模式那一支（`liveClient()` 为 null 时）**逐字不动**：`searchCommand`、`missingEnvelope`、`errorEnvelope`、`ERROR_MESSAGE`、`okEnvelope`、`clone`、`pending`、`read`、五个开关与夹具规则一个字都不改。
- 真实模式那一支（`liveClient()` 不为 null 时）按下面四步：
  1. **建作业**：`client.postRaw('/api/v1/jobs', body, 15)`。`body` 是扁平对象，键恰好是 `{ kind: 'search', pattern: q, max }`；`task` **不为 null** 时才再加一个 `task` 键（值就是那个非空串；`task` 为 null 时正文里没有 `task` 键）；`max` 传**数字**（不是字符串）。除这几个键外正文里不许有别的键（服务对多一个键回 400「请求体含有未知键」）。
  2. **建作业不是 201**：立刻交回报错信封并停止（不发查询、不排计时器）：
     `{ ok: false, exit_code: null, data: null, output: [], messages: <见下>, command: searchCommand(q, task, max), elapsed_ms: 0 }`
     其中 `messages` = 回应正文是合法七字段信封（用 `isEnvelope` 判）时**它的 messages 原样**；否则是 `['ERROR: 服务返回 HTTP <状态码>']`（状态码就是回应的 status）。
  3. **建作业是 201**：从回应正文里取 `id`（作业对象的 `id` 键），查询路径是 `'/api/v1/jobs/' + encodeURIComponent(String(id))`；**第一次查询在 201 之后 1000 毫秒**（`setTimeout` 链，不用 `setInterval`；照 `src/jobs/jobStore.ts:145-155` 的节奏）。每次查询是 `client.getRaw(path, undefined, 15)`。
     - **查询不是 200**：立刻交回与第 2 步同一个形状的报错信封并停止（`messages` 取回应正文里信封的 messages，正文不是信封时是 `['ERROR: 服务返回 HTTP <状态码>']`）。**503、401 一律按这一条停，不当暂时的**（服务 503 是作业表满/执行器收不了，401 是会话失效）。
     - **查询是 200**：读作业对象的 **`state`** 字段（字段名是 `state`，不是 `status`）。
       - `state` 是终态（`succeeded`、`failed`、`cancelled`、`timed_out` 四个之一）：**停止轮询**（不再排计时器，计时器数归零）。
         - 作业对象的 `envelope` 是合法七字段信封（`isEnvelope` 为真）→ **原样交回那个对象**（不拷贝、不改它的 `command`、不改它的 `messages`、不改 `elapsed_ms`）。成功时它的 `data` 就是 `logs search --json` 的输出。
         - `envelope` 为 null 或不是合法信封 → 交回固定报错信封 `{ ok: false, exit_code: null, data: null, output: [], messages: [<固定一句>], command: searchCommand(q, task, max), elapsed_ms: 0 }`，固定一句按 `state` 取（**逐字**）：
           - `succeeded` → `ERROR: 检索作业没有交回结果`
           - `failed` → `ERROR: 检索作业失败`
           - `cancelled` → `ERROR: 检索作业已取消`
           - `timed_out` → `ERROR: 检索作业超时`
       - `state` 不是终态（`queued`、`running` 以及任何其它取值）→ 再排一次 1000 毫秒的 `setTimeout`，继续查；**不设次数上限**（服务的 180 秒时限保证作业会到终态）。
  4. **reject**：`postRaw` 或 `getRaw` reject（断线、超时）时 `searchLogs` 跟着 reject——**不重试、不吞、不再排下一次查询**（`logs-SearchPanel.tsx` 已有 `.catch`）。
- **不发取消请求**（全程没有对作业的取消调用）；**不调 `client.get`**；**不从 `../../api` 引 `startJob`/`getJob`/`cancelJob`/`JobKind`**（作业的建与查直接用 `liveClient()`）。
- `isEnvelope` 从 `'../../live/transport'` **运行时**引入（照 `api.ts:46` 的先例；不是 `import type`），这一行以分号结尾。
- `export { getHistoryEntry, getPlugin } from '../../api';` 那一行**逐字保留**，它前一条语句以分号结尾；对 `../../api` 仍然**只许 `import type`**（T010 `:544-549`、T027 `api_import_problems`、包内 `readonly2-static.test.ts:123-128` 三处口径）。
- 文件头注释（`:1-6`）与真实分支那一行注释（`:64`）改成新行为（不再说「还没接通」）；文件里不再出现 `ERROR: 检索尚未接通` 这句文案。
- 文件里（注释与字符串都算）不许出现：`fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个整词；T010 的 FORBIDDEN_WORDS（`innerHTML`、`eval(`、`new Function`、`DOMParser` 等）与 FORBIDDEN_CALLS（`matchMedia` 等）；**井号加 3、4、6 或 8 位十六进制**（注释里写「#1000」也会红）；颜色函数名加括号；T023 的 BAD_ENTRY_FRAGMENTS（「已删除」「已回滚」「删除方案」等）。

### 包内测试 `desktop/web/tests/live-readers.test.ts`
- 文件头注释（`:1-2`）改成新行为（真实模式走服务的 search 作业）。
- 假客户端写全四个方法（`get`、`post`、`getRaw`、`postRaw`），记下每次调用的路径、查询、正文与时限，按用例编排 `postRaw`/`getRaw` 的回应（`postRaw` 回 `{ status, body }`，`getRaw` 同）。
- 假计时器：需要轮询的用例用 `vi.useFakeTimers()`（结束时 `vi.useRealTimers()`）；推进用 **`vi.advanceTimersByTimeAsync`**（vitest 2.1.8 的缺省假计时器不替换微任务，同步推进会冲掉 promise 链）；终态之后断言 `vi.getTimerCount()` 为 0。
- 把 `describe('searchLogs 真实模式回「检索尚未接通」')`（`:32-51`）**整块换成**真检索的用例，至少覆盖这十条（逐条写死）：
  1. **带 task 与 max**：`postRaw` 的路径是 `/api/v1/jobs`、时限 15、正文恰好四键 `{ kind: 'search', pattern: 'logs[_ ]cat', max: 5, task: 't1' }`（`max` 是数字）；先 `queued`、再 `running`、再 `succeeded`；交回作业的 `envelope` 原样；`getRaw` 的路径是 `/api/v1/jobs/<id>`、时限 15；终态后计时器数为 0；全程没有取消请求。
  2. **task 为 null**：正文恰好三键、没有 `task` 键。
  3. **failed 带内核信封**：原样交回（`toEqual` 那个信封）。
  4. **cancelled 且 envelope 为 null**：整个固定信封 `toEqual`，`command` 是 `searchCommand` 的数组，`messages` 逐字 `['ERROR: 检索作业已取消']`。
  5. **timed_out 且 envelope 为 null**：固定信封，`messages` 逐字 `['ERROR: 检索作业超时']`。
  6. **建作业回 400**：`messages` 是服务那句（例如 `['ERROR: task 不合法']`），**没有查询发生**。
  7. **建作业回 503**：同上（`messages` 取回应信封的 messages）。
  8. **查询回 404**：报错信封带 `['ERROR: 没有这个作业']`，之后不再查询（再推进时间也没有新的查询）。
  9. **getRaw reject**：`searchLogs` reject，不留计时器。
  10. **succeeded 但 envelope 不合法**：固定信封，`messages` 逐字 `['ERROR: 检索作业没有交回结果']`。
- `describe('转出后的 getHistoryEntry/getPlugin：夹具分支与原来逐字一致')`（`:53-95`）**原样保留**（记号「夹具里没有这份数据」就在里面）。
- 文件里要有这三个记号：`searchLogs`、`/api/v1/jobs`、`夹具里没有这份数据`（T027 `:111` 认）。**不许 skip / only / todo**。

### 旧门禁 `tests/test_gate_t027_baseline.py`（逐处写死，只改下面写明的地方，其余一个字不动）
- **第 1 处 `:111`**：`EXECUTOR_TEST_TOKENS` 里那一项换成
  `    "live-readers.test.ts": ("searchLogs", "/api/v1/jobs", "夹具里没有这份数据"),`
  （去掉「检索尚未接通」，换成 `/api/v1/jobs`；`searchLogs` 与「夹具里没有这份数据」照旧。同一字典里 `live-api.test.ts` 那一项**不动**。）
- **第 2 处 S07（`:417-436`）**：删掉 `:433` 那一行
  `    assert "ERROR: 检索尚未接通" in text, "searchLogs 真实模式应回「ERROR: 检索尚未接通」"`
  并把 docstring（`:418-419`）里「、searchLogs 保留并回「检索尚未接通」」这半句删掉（改成「、searchLogs 保留」）。S07 别的断言照旧：转出语句、前一条语句以分号结尾、`api_import_problems` 为空、`export function searchLogs(` 在、夹具报缺文案、`ERROR_MESSAGE`、`SEARCH_PATTERN`。
- **第 3 处 `:521-525`**：`test_transitional_s33_searchlogs_unwired_message` **整条删掉**（函数体三行 + docstring）。模块 docstring `:58` 那条改成
  `- ``test_transitional_s33_*``：searchLogs「检索尚未接通」——作业/检索片推翻（站主 2026-11-19 为 T059 退役）。`
- **第 4 处探针**：`**PROBE_UNWIRED**`（`:1069-1123`，连同它前面的空行）**整份删掉**；`PROBE_SPECS` 里 `"unwired": (PROBE_UNWIRED, (MODE_REL, API_REL, READERS_REL)),`（`:1206`）那一项删掉；`PROBE_ORDER`（`:1209`）改成 `PROBE_ORDER = ("mode", "transport", "connection", "api", "tasks")`；`test_transitional_p6_probe_unwired`（`:1475-1477`）**整条删掉**。`READERS_REL`、`MODE_REL`、`API_REL` 三个常量**保留**（别处还在用）。
  模块 docstring 两处跟着改：
  - `:48-49` 那一整条（现在是「- unwired（过渡）：写函数与 getOperation 真实模式回 501 固定信封、不发读请求（站主 2026-11-13 为 T037 退役）；searchLogs 回 / 「检索尚未接通」且夹具分支照旧（D09、D10）。」两行）换成一行
    `- unwired（过渡）：searchLogs「检索尚未接通」的探针整份随 T059 退役（站主 2026-11-19 为 T059 退役）；写函数与 getOperation 真实模式回 501 固定信封那一半站主 2026-11-13 为 T037 退役。`
  - `:60` 那一行（现在是「- ``test_transitional_p3_probe_unwired`` / ``test_transitional_p4_probe_tasks``：同上的探针版。」）换成
    `- ``test_transitional_p6_probe_unwired``：searchLogs 探针，随 T059 退役（站主 2026-11-19 为 T059 退役）；``test_transitional_p7_probe_tasks``：SSE 片会推翻。`
- **退役注记的措辞**：照这份门禁里 `:55`、`:57` 已退役条目的写法，一律写「（站主 2026-11-19 为 T059 退役）」。
- 模块 docstring `:1-9` 对 T027 基线的历史描述（提到「`searchLogs` 回「检索尚未接通」」那一行）**照旧不动**——那是历史说明，不是断言。

### 边界输入
- `task` 是 null：正文三键；`task` 是非空串：正文四键。`searchCommand` 的真值判断照旧（不因正文的 null 判断而改）。
- `max` 是 0 或超过 1000：前端照旧把数字发给服务，由服务回 400；前端把服务那句提示原样交回。
- 作业在 `queued`/`running` 停很久：一直查到终态为止（不设上限），期间不发取消。
- 服务重启导致作业不在表里（查询 404）：按「查询不是 200」交报错信封并停止。

### 错误与重试
- 建作业非 201、查询非 200：一律交报错信封并**立即停止**（不重试、不再查询）。
- `postRaw`/`getRaw` reject：`searchLogs` reject，往外抛（`SearchPanel` 的 `.catch` 显示错误）。
- 不重试任何一步。

### 并发、取消与状态变化
- 本片不引入取消：用户离开日志页或重新检索时**不取消**作业（服务的 180 秒时限兜底；`SearchPanel` 用 `reqRef`/`mountedRef` 丢掉过时的结果）。轮询本身是单条 `setTimeout` 链，同一个 `searchLogs` 调用只有一条链在跑。
- 作业状态由服务端推进（`queued` → `running` → 终态），前端只读不改。

### 兼容性（公开 API、数据与格式）
- `searchLogs` 的签名、返回类型与三个导出名字不变；页面（`logs-SearchPanel.tsx`）的调用方式不变。
- 夹具模式（`?mock=` 五个取值）的行为与现在逐字相同（T010 的 readers 探针照旧全过）。
- 真实模式下返回的信封仍是七字段（`ok`/`exit_code`/`data`/`output`/`messages`/`command`/`elapsed_ms`），`data` 在成功时是 `logs search --json` 的输出（与夹具 `SearchData` 逐键一致）。
- 旧门禁里被本片推翻的只有 `tests/test_gate_t027_baseline.py` 的四处（见上），逐处改法写死；**不推翻**任何包内测试（`page-app.test.tsx:91`、`readonly2-app.test.tsx:106`、`readonly2-logs.test.tsx` 都是夹具模式或注入 reader，与本片无关），也不推翻 T006–T058 里的其余过渡断言。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。
2. **`desktop/web/src/pages/readonly2/common-readers.ts`**：新增 `import { isEnvelope } from '../../live/transport';`（运行时引入，以分号结尾，放在 import 组里；`export { getHistoryEntry, getPlugin } from '../../api';` 那一行逐字保留，它前一条语句以分号结尾）；把 `:64-74` 的真实分支换成上面「真实模式的 searchLogs」的四步（建作业 → 201 之后 1000 毫秒轮询 → 终态交回 → reject 往外抛），helper（轮询、终态判定、固定信封）**留在模块内部、不导出**，主函数只写正常流程；夹具分支（`:76-91`）与 `searchCommand`、`missingEnvelope`、`errorEnvelope`、`ERROR_MESSAGE`、`okEnvelope`、`clone`、`pending`、`read` 一个字不动；改写文件头注释与真实分支那行注释（去掉「还没接通」的说法）。文件里不许出现四个网络整词、FORBIDDEN_WORDS/FORBIDDEN_CALLS、井号加 3/4/6/8 位十六进制、颜色函数名加括号、T023 的 BAD_ENTRY_FRAGMENTS。
3. **`desktop/web/tests/live-readers.test.ts`**：改写文件头注释；假客户端写全四个方法并记录调用；把 `:32-51` 那个 describe 整块换成上面写死的十条用例（假计时器 + `vi.advanceTimersByTimeAsync` 推进，终态后 `vi.getTimerCount()` 为 0）；`:53-95` 那个 describe 原样保留；记号 `searchLogs`、`/api/v1/jobs`、`夹具里没有这份数据` 都在；不许 skip/only/todo。
4. **逐处改旧门禁**（照「兼容性」一节逐条只改那一处）：`tests/test_gate_t027_baseline.py` 的 `:111`、S07 的 `:433` 与 docstring、`:521-525` 整条、`:48-49`、`:58`、`:60`、`:1069-1123` 整份探针、`:1206`、`:1209`、`:1475-1477`。改完把仍钉着旧口径的地方再搜一遍（关键字：`检索尚未接通`、`unwired`、`PROBE_UNWIRED`），确认没有漏网的旧断言（模块 docstring `:1-9` 的历史描述除外）。
5. 跑 Validation commands 里与改动相关的检查（顺序 **V03 → V04 → V01 → V02 → V05 → G01 → R01**；本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
6. 写执行报告；遇到合同未定义的行为，停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- V01（必要）：`npm test -- tests/live-readers.test.ts` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V05（必要）：`python -m pytest tests/test_gate_t027_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t022_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t059_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py -q` · cwd：仓库根 · 超时：3420s · 期望退出码：0 · 输出须匹配：`\d+ passed`

上面每条检查的「输出须匹配」为什么在门禁机上成立（逐条说明；门禁检查与回归检查都用 pytest 的 `-q`，成功时最后一行是「N passed」，与已验收的 T055–T058 合同里同一种调用配同一个匹配，已在门禁机上成立过）：
- 前端那两条 vitest 检查是 `npm test`（= `vitest run`，desktop/web 已装 vitest 2.1.8），vitest 2.x 成功时打印「Tests  N passed」；同一个匹配在 T055、T056、T057、T058 合同的同一种调用上验收通过过。只跑指定文件的那一条另加 `不得出现 No test files found`（vitest 找不到文件时会这么写，防止「0 个用例也是绿色」）。
- 类型检查那条是 `npm run typecheck`（= `tsc --noEmit`），成功时无输出、退出码 0；这条不写输出须匹配（没有输出可匹配），只看退出码。
- 构建那条是 `npm run build`（= `tsc --noEmit && vite build`），vite 5.4.11 成功时打印「✓ built in …」；同一个匹配在 T055–T058 合同里验收通过过。构建产物在 `desktop/web/dist/`，已被 `.gitignore` 忽略，不会算成候选之外的新文件。
- 点名跑的三份门禁会起 npm 流水线（t027 的 `PIPELINE_BUDGET` 是 1500 秒、t010 是 570 秒），超时给到 2400 秒；t027 的流水线里 `npm test` 会连本片改过的 `live-readers.test.ts` 一起跑。
- 门禁检查那条（本片门禁基准文件）由门禁端稍后写好、内核做成基线提交；基线上它应当失败（断言失败，不是收集失败），本片做完之后它必须通过。

## Definition of done
- D01：真实模式的 `searchLogs` 建作业：`postRaw('/api/v1/jobs', body, 15)`，正文键恰好 `{ kind: 'search', pattern: q, max }`（`task` 不为 null 时才加 `task`），`max` 是数字；目的：这是服务认的那份请求（多一个键就 400）；证据：V01、V05、G01、R01。
- D02：201 之后第一次查询在 1000 毫秒，路径 `/api/v1/jobs/<id>`（`encodeURIComponent` 编码）、时限 15；非终态继续查（不设上限），终态之后计时器数为 0；全程没有取消请求、没有 `client.get` 调用；目的：检索要作为作业跑（设计文档 D7），界面「正在检索…」期间有节奏地查；证据：V01、V05、G01。
- D03：终态 `succeeded`/`failed`/`cancelled`/`timed_out` 时，作业的 `envelope` 是合法信封就**原样交回**；为 null 或不合法就交回固定报错信封，四句文案逐字（已取消 / 超时 / 失败 / 没有交回结果），`command` 是 `searchCommand(q, task, max)`；目的：成功要拿到命中，失败要看得懂出了什么事；证据：V01、G01。
- D04：建作业非 201、查询非 200（含 503、401）时交回报错信封（`ok:false`、`exit_code:null`、`data:null`、`output:[]`、`command` 是 `searchCommand`、`elapsed_ms:0`），`messages` 取回应信封的 messages、正文不是信封时是「ERROR: 服务返回 HTTP <状态码>」，并**立即停止**；目的：不把服务的话丢掉，也不假装还在查；证据：V01、G01。
- D05：`postRaw`/`getRaw` reject 时 `searchLogs` reject，不重试、不吞、不再排查询；目的：断线要看得见（`SearchPanel` 的 `.catch` 已经接好）；证据：V01、G01。
- D06：夹具模式逐字不变（T010 的 readers 探针照旧全过）；导出仍是 `searchLogs`、`getHistoryEntry`、`getPlugin` 三个、不新增导出；对 `../../api` 仍只许 `import type`，转出语句前一条语句以分号结尾；文件里没有四个网络整词、FORBIDDEN_WORDS/FORBIDDEN_CALLS、井号加 3/4/6/8 位十六进制、颜色函数名加括号、T023 的 BAD_ENTRY_FRAGMENTS；目的：不推翻旧门禁钉着的形状与扫描；证据：V02、V03、V05、R01、review。
- D07：`desktop/web/tests/live-readers.test.ts` 覆盖 D01–D05（上面写死的十条用例），记号 `searchLogs`、`/api/v1/jobs`、`夹具里没有这份数据` 都在，没有 skip/only/todo；夹具那一个 describe 原样保留；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D08：`tests/test_gate_t027_baseline.py` 的四处逐处改到位（`:111` 的记号三项、S07 `:433` 一行与 docstring 那半句、`test_transitional_s33_searchlogs_unwired_message` 整条退役、`PROBE_UNWIRED` 整份退役且 `PROBE_SPECS`/`PROBE_ORDER` 去掉 `"unwired"`、`test_transitional_p6_probe_unwired` 整条退役），退役注记逐字写「（站主 2026-11-19 为 T059 退役）」，**每处只改合同写明的那一处**，其余一个字不动；目的：这些旧断言钉的是「检索尚未接通」，本片必然推翻，改法不许顺手改别的断言；证据：V05、G01、R01、scope、review。
- D09：所有修改都在允许集合内（可改 3 个文件、无新增、无删除），没有碰 forbidden_paths（本片门禁 `tests/test_gate_t059_*.py`、其余门禁基准、`api.ts`、`live/**`、`jobs/**`、`mock/**`、日志页组件与 `readonly2` 里除本文件外的其它文件、包内其它测试、`package.json` 与锁文件、`ts/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope。
- D10：`npm test`、`npm run typecheck`、`npm run build` 全过；既有门禁基准（t001–t058）照旧通过；目的：不能为了接通检索把别处弄坏；证据：V01、V02、V03、V04、V05、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `LiveClient` 没有 `postRaw`/`getRaw`、作业对象的状态字段不叫 `state`、`isEnvelope` 不再从 `../../live/transport` 导出、夹具分支与写好的不同、`common-readers.ts` 被改名或挪了位置），特别是这些文件被整体挪位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `api.ts`、`live/**`、`jobs/**`、`mock/**`、日志页组件、包内其它测试、其它门禁基准、`package.json` 与锁文件、`ts/packages/**`）。
- 服务端作业路由与本合同的形状对不上（正文键、状态码、终态集合、作业对象的键名变了）：停下并报告实际形状，不要在客户端猜。
- 改完之后夹具模式的包内用例或 T010 的 readers 探针红了：停下并报告，不要改旧断言来凑。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t059-desktop-web-logs-search-job` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读源码与门禁文件、核对事实 30 分钟；common-readers.ts 真实分支 40 分钟；live-readers.test.ts 十条用例 45 分钟；t027 四处逐处改 25 分钟；必要检查（V03、V04、V01、V02、V05、G01、R01；V05 约 20–40 分钟、R01 约 30–40 分钟、可分批跑）95 分钟；最终报告 10 分钟；总计约 245 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与一次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261119T153033194620Z-owner-27bd97：

> 摘要: 选 (b)：合同把 tests/test_gate_t027_baseline.py 列进 allowed_modified_files，照规划报告第 6 节第 4 步逐处写死改法；第 8 节 D1–D10 的默认细节照用
> 提交: 无
> 验证: 读了规划报告第 6–10 节；四处改法与 T059 任务书一致（:111 换记号 "/api/v1/jobs"、S07 删 :433 一行与 docstring 那半句、s33 整条退役并注明 T059、PROBE_UNWIRED 与 p6 整份退役并去掉 PROBE_SPECS/PROBE_ORDER 里的 "unwired"）
> 偏离: 无
> 需协调人决定: 无。合同端照 (b) 开工：
> - 退役注记的措辞由合同逐字写死，照这份门禁里 :55、:57 已退役条目的写法注明“T059 退役”；
> - D1 写死成“task 不为 null 才加 task 键”（与任务书逐字一致）；
> - D6 的四句固定文案照规划建议：已取消、超时、失败、没有交回结果；timed_out 的包内用例 envelope 置 null；
> - D7 查询不是 200 一律停（含 503、401），照任务书；
> - 执行端的检查里点名跑 t027、t010、t022 三份门禁（会起 npm 流水线，时限按门禁机预算定），其余旧门禁由内核回归跑。
> 证据: .agent/mailbox/tasks/T059-1-plan/report.md 第 6 节第 4 步、第 7 节、第 8 节
