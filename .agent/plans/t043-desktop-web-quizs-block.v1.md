# TASK: t043-desktop-web-quizs-block

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: ea073ee536993f73d5626e20bffd3396db33b875
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在「CLI 运行时」页加一块**只读**的「Quizs」（`desktop/web/src/api.ts` 新增读函数 `getQuizsProviders()`、`getQuizsLive()`，真实模式分别走 `GET /api/v1/quizs/providers`（60 秒）与 `GET /api/v1/quizs/live`（150 秒）；桩模式走新增的 `desktop/web/src/mock/quizs.ts`，用 `?quizs=` 选情景）：`RuntimesPage` 并行读三条（`getRuntimes`/`getQuizsProviders`/`getQuizsLive`），**只有 runtimes 失败才整页失败**，两个 Quizs 信封整个放进视图数据；视图在「就绪检查」之后渲染 `Quizs` 一块（提供方档案表 + live 套表，状态不是就绪的要醒目并写出下一步）。

## Non-goals
- 不做资格认证、续期、录凭据、改岗位绑定；不给任何写入口。
- 不做设计稿第 6 节的「凭据在不在」「快到期」「能力上限」（两条路由不给凭据在不在；快到期没有阈值出处；能力上限对应的字段未放行）。
- 区块里**不放任何按钮**（复制钮也不放），不给可复制的续期命令；下一步只写纯文字。
- 运行时表为空时页面照旧走空态、不渲染视图（Quizs 一块因此看不到）。
- 不改 `ts/packages/ui`（服务端）、不改 `scripts/`（内核）、不改任何门禁测试、不放宽任何门禁。
- 不改 `src/mock` 下的 JSON（仍恰 14 份）、不新增 `src/pages` 顶层的 `*Page.tsx`（仍恰 9 个）、不改 `mock/writes.ts` 的情景值、不改 `mock/scenario.ts`。
- 不改 `page-app.test.tsx`、`readonly2-app.test.tsx`；不改 `src/shell/`、`src/live/`、`src/shellpages/`、`src/pages/readonly2/`、`src/writes/`、`src/components/`。

## Repository facts
以下事实均在基线 `282f9229364bcaccf0e2e11c2f496d06850b0854` 的工作目录里核对过（行号按该基线；只读探查，未运行 npm/pytest）。
- 基线与文件名：合同 base_sha 是 `282f9229364b…`；核对事实时用的工作目录 HEAD 是 `26a99bf3bd26`（内核会说明两者关系，门禁提交后 base_sha 会改）。「CLI 运行时」的视图文件是 `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`、纯函数文件是 `desktop/web/src/pages/readonly1/runtimes-logic.ts`——这两个名字在前一片 T041（`.agent/plans/t041-desktop-web-runtime-add.v3.md` 的 forbidden_paths 含 `desktop/web/src/pages/readonly1/**`，一个字没动）与 T042（`.agent/plans/t042-desktop-web-quizs-facts.v2.md` 的 Non-goals 明写 `desktop/web/**` 一个字不改）之后没有变过。
- 服务端（T042 已落地，本片只读不改）：
  - `ts/packages/ui/src/readroutes.ts:45-48`：`QUIZS_PROVIDERS_TIMEOUT = 60`、`QUIZS_LIVE_TIMEOUT = 150`（注释写明内核每次调 Quizs 是 30 秒，live 每套各跑一次所以更长）。
  - `ts/packages/ui/src/readroutes.ts:117-118`、`:630-642`、`:673-674`：`api.quizs.providers.get` = `GET /api/v1/quizs/providers` → `['config','quizs','providers','--json']`，时限 60 秒；`api.quizs.live.get` = `GET /api/v1/quizs/live` → `['config','quizs','live','--json']`，时限 150 秒。
  - `ts/packages/ui/src/redaction.ts:120-128`：`QUIZS_THINKING_ENUM`（off/low/medium/high/xhigh/max）、`QUIZS_BILLING_ENUM`（none_test_only/step_plan_credits/deepseek_prepaid_balance）、`QUIZS_LIVE_SOURCE_ENUM`（mailbox/env）、`QUIZS_LIVE_STATE_ENUM`（ready/expired/build_mismatch/invalid/missing）、`QUIZS_LIVE_FILE_ENUM`（plan.json/profile.json/qualification.json）。
  - `ts/packages/ui/src/redaction.ts:150-161` `QUIZS_PROVIDERS_ALLOW`：逐行只放行 `provider`、`model`（名字形状，可为 null）、`thinking[*]`（枚举）、`billing`（枚举）。**`id`、`build_id` 未登记**（注释明写「build_id、id、credential_*、*_tokens 一类键不登记」）。
  - `ts/packages/ui/src/redaction.ts:163-176` `QUIZS_LIVE_ALLOW`：逐套放行 `source`、`provider`、`problem`（可空自由文字）、`status.problem`（可空）、`status.state`（枚举）、`status.missing[*]`（三个文件名）、`status.certificate.expires_at_ms`（毫秒整数或 null）、`status.profile.valid_until`（带毫秒的 ISO 8601 UTC 字符串或 null）。**`live_dir`、`plan.*`、`issued_at_ms`、`capabilities` 未登记**。
  - 越界的枚举值在响应里是字面量 `<redacted>`（`ts/packages/ui/test/quizs-routes.test.ts:122-163`）；未登记的普通字符串按默认口径透传，因此前端**只用白名单登记的字段**，其余一律不显示、不写进类型、夹具里也不带。
  - 出错信封（同文件 `:165-188`）：providers 退出 1 → HTTP 200、`ok:false`、`exit_code:1`、`messages` 一行 `ERROR: …`、`data:null`；超时 → HTTP 504、`ok:false`、`exit_code:null`、`data:null`、`messages` 一行超时提示。
- 前端现状：
  - `desktop/web/src/api.ts:50-57`：`Envelope<T>` 七字段，`exit_code: number | null`；`:346-358` 的 `read(command, produce)` 统一处理 `?mock=`：`loading` 挂起、`error` 回错误信封、其余模式回 `produce(mode)` 的信封；真实分支用 `liveClient()`（非 null 即真实模式）；`client.get<T>(path, query, timeoutSeconds)`（`desktop/web/src/live/transport.ts:177`）。
  - `desktop/web/src/api.ts:444-450`（`getHubRoles`）与 `:466-472`（`getRuntimes`）是读函数的样板；`getHubRoles` 用 `clone(HUB_ROLES_POSTS)` 深拷贝夹具。
  - `desktop/web/src/pages/RolesPage.tsx:23-41`：`Promise.all` 并行读四个、第一个坏的整页返回那个失败信封、好信封整个放进 `data.hub` 的样板。
  - `desktop/web/src/pages/RuntimesPage.tsx`（全篇 27 行）：`loadRuntimes`、`isRuntimesEmpty` 是命名的模块级函数；`load` 只读 `getRuntimes`；`isEmpty` 只看 `runtimes.length === 0`；`children` 是 `(data, reload) =>`；页头两个按钮（`[扫描 PATH]` 禁用、`[手动登记…]` 由 `AddRuntimeAction` 接上）。
  - `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx:46-49`：`RuntimesViewProps` 是 `{ runtimes; reload? }`；`:83-110` 渲染 `已登记`（表 `aria-label="已登记的 runtime"`，className `rt-table`）与 `就绪检查` 两节，节里没有别的 section。
  - `desktop/web/src/pages/readonly1/runtimes-logic.ts`：纯函数文件，只 `import type` 自 `../../api`（`canServe`/`sourceLabel`/`sourceTone`/`commandText`/`canProbe`/`canModels` 等）。
  - `desktop/web/src/pages/readonly1/runtimes-styles.css:5-7`：`.rt-table` 的三条规则（容器去圆角、`.tt-table` 最小宽 900px、最后一列右对齐）——Quizs 的表**不用** `rt-table` 类。
  - `desktop/web/src/components/RelativeTime.tsx:30-40`：`formatLocalUtc(iso)` → `YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）`，解析不了返回 null；「（UTC 」这串字面量只许出现在这一份文件里（T013 D02）。
  - `desktop/web/src/components/Tag.tsx`：`tone` 取值 `neutral|info|attention|success|warning|danger|escalate|brand`；`desktop/web/src/components/Table.tsx` 要 `columns`/`rows`/`rowKey`/`aria-label`，`className` 加在 `.tt-table-wrap` 滚动容器上；`.tt-table` 本身没有 min-width。
  - `desktop/web/src/pages/readonly1/common-Section.tsx`：`Section` 渲染 `section` + `aria-labelledby` 指 h2（`useId`），可给 `description`/`className`。
  - `desktop/web/src/mock/scenario.ts`：只认 hash 里的 `mock` 键（五个取值，认不出按 data）；`desktop/web/src/mock/writes.ts:36-49`：`writeScenario()` 只认 `write` 键——新键 `quizs` 与两者都不冲突（没有门禁钉 hash 查询键的全集）。
  - `desktop/web/src/mock/hub-roles.ts`：`src/mock` 下的夹具写法样板（纯类型导入 `import type { … } from '../api'`，导出一个常量）。
  - `desktop/web/src/mock/` 下现有 JSON 恰 14 份（T011/T012/T022/T023/T024 都钉这个数），`src/pages` 顶层恰 9 个 `*Page.tsx`；夹具只能是 `.ts`。
  - `desktop/web/tsconfig.json:17`：`include` 只有 `["src","vite.config.ts"]`——`tests/` 不过 `tsc --noEmit`。
  - `desktop/web/package.json`：`npm test` = `vitest run`；`npm run typecheck` = `tsc --noEmit`；`npm run build` = `tsc --noEmit && vite build`；`npm run check:contract` = `node scripts/token-contract.mjs`。
  - `desktop/web/tests/live-api.test.ts:72-117`：读函数表 `ROWS` 有 16 行，`:119` 的 describe 标题写「api.ts 的 16 个读函数（注入 fake client）」。
  - `desktop/web/tests/page-runtimes.test.tsx`：四处 `render(<RuntimesView runtimes={RUNTIMES} />)`（第 47、66、77、88 行附近）；`desktop/web/tests/writes-remove.test.tsx:221` 一处 `render(<RuntimesView runtimes={RUNTIMES} />)`。这是全仓库仅有的两处直接渲染视图的地方。
  - `desktop/web/tests/page-app.test.tsx:91-99`：运行时页禁用钮计数是 **5**（`[扫描 PATH]`、`[运行就绪检查]` 与行内禁用钮），本片加按钮就会红。
  - `desktop/web/tests/page-static.test.ts:31` 的 `FORBIDDEN` 按**子串**查（`fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`、`dangerouslySetInnerHTML`、`innerHTML`、`outerHTML`、`insertAdjacentHTML`、`eval(`、`new Function`、`document.write`、`srcdoc`、`DOMParser`、`ServerIcon`），且该文件的 FILES 里有 `pages/readonly1/runtimes-RuntimesView.tsx` 与 `pages/readonly1/runtimes-logic.ts`；同文件 `:41-50` 查 `role=status` 与内联 style。
- 门禁事实：
  - `tests/test_gate_t009_baseline.py:137-139`：`ALLOWED_API_READS` **已含** `getQuizsProviders`、`getQuizsLive`（站主的门禁准备已落地）→ 不需要退役任何断言。
  - `tests/test_gate_t009_baseline.py:2901-2903`：D10 改成 `qa(r,'section').map(sectionTitle).slice(0,2)` 只钉前两节（已落地）。
  - `tests/test_gate_t009_baseline.py:1055-1067`：探针的 api 替身默认**转调真实函数** → 运行时页探针里 Quizs 一块显示的是桩数据（`?mock=` 的 data 情景）；`:1114-1119` 要求每个 section 都有 `aria-labelledby` 指 h2；`:2936-2941` 可用按钮白名单只有 刷新/radio/查看差异/复制命令；`:2945-2952` 禁用钮都要有悬停提示。
  - `tests/test_gate_t006_baseline.py:3310-3318`：`api.ts` 的 13 个读函数按**包含**核对，多导出不红；`:317-326` 与 `:3354-3362`：新源码（`src/api.ts`、`src/mock/**`、`src/pages/**`）不许渲染 `role=status`，不许调 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`，不许写十六进制颜色与颜色函数。
  - `tests/test_gate_t009_baseline.py:478-499`：CSS 里除 `0` 与 `1px` 外的 px 字面量，所在行要带出处注释；`:3623-3638`：四份 CSS 合并后逐条核对 §8 的取值，且每份 CSS 要有独有类名出现在构建产物里。
  - `tests/test_gate_t013_baseline.py:681-686`：「（UTC 」只许出现在 `desktop/web/src/components/RelativeTime.tsx`。
  - `tests/test_gate_t023_baseline.py:361-369`、`tests/test_gate_t024_baseline.py:348-356`：`src/mock` 恰 14 份 JSON、`src/pages` 顶层恰 9 个 `*Page.tsx`。
  - `tests/test_gate_t032_baseline.py:119-129` 的 `UNTOUCHED_REL`（禁改清单）不含 api.ts、RuntimesPage.tsx、readonly1/*、mock/*。
  - `tests/test_gate_t037_baseline.py:240-247`：`src/live/transport.ts` 里 `new AbortController(` 与 `setTimeout(` 各只许一处 → **本片不动 transport.ts**，读函数只调 `client.get(path, undefined, 秒数)`。
- 已核实的仓库外事实（只写这四条，其余不写进合同）：
  - providers 每行的 `billing` 是字符串枚举（只有 none_test_only / step_plan_credits / deepseek_prepaid_balance 三种），`thinking` 是档位字符串数组（取值在 off/low/medium/high/xhigh/max 内）；实测 stepfun 是 `step_plan_credits` + `[low, medium, high]`，deepseek 是 `deepseek_prepaid_balance` + `[low, high]`。
  - live 的 `status` 是 null 或对象；`certificate.expires_at_ms`、`plan.expires_at_ms` 是毫秒整数，`profile.valid_until` 是带毫秒的 ISO 8601 UTC 字符串（形如 `2026-11-20T08:00:00.000Z`），三者类型上都可以是 null。
  - 没设 `QUIZS_CMD` 时 providers 退出 1（一行 ERROR），live 的每一套 problem 写「quizs live status 失败（退出码 127）：…」，live 命令照常退出 0。
  - 本机 PATH 上没有 quizs；`QUIZS_CMD` 与三个 `QUIZS_LIVE_*` 变量在用户级环境变量里（只影响合入后在真窗口里的验收）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/src/pages/readonly1/runtimes-styles.css
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/writes-remove.test.tsx
- allowed_new_files:
  - desktop/web/src/mock/quizs.ts
  - desktop/web/src/pages/readonly1/runtimes-QuizsBlock.tsx
  - desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts
  - desktop/web/tests/page-quizs.test.tsx
  - desktop/web/tests/quizs-logic.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t043_*.py
  - ts/packages/ui/**
  - scripts/**
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/components/**
  - desktop/web/src/writes/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/live/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - 真实模式（`liveClient()` 非 null）：`getQuizsProviders()` 走 `client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60)`，`getQuizsLive()` 走 `client.get<QuizsLiveData>('/api/v1/quizs/live', undefined, 150)`；**不回落桩**，服务回的信封原样透传。
  - 桩模式：两个读函数都走 `read(command, produce)`，命令分别是 `['config','quizs','providers','--json']` 与 `['config','quizs','live','--json']`；`?mock=loading` 挂起、`?mock=error` 回错误信封（`read()` 的既有行为，不另写）；其余模式由 `?quizs=` 选情景（缺省或认不出按 `ok`）。
  - 页面：`loadRuntimes` 用 `Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])` **并行**发三个读；`runtimes` 的信封失败（`!ok || data == null`）时**整页**返回那个信封（命令与退出码原样，页面级出错块照旧写出来）；成功时 `data` 形如 `{ runtimes: RuntimesData; quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> } }`——两个 Quizs 信封**整个**放进去，不参与整页失败判定。`isEmpty` 仍只看 `runtimes.length === 0`；`load` 与 `isEmpty` 仍是命名的模块级函数；`children` 仍是 `(data, reload) =>`。
- 边界输入（类型与显示；类型只写白名单登记且区块要用的字段）：
  - `QuizsProviderRow`：`provider: string | null`、`model: string | null`、`thinking: string[]`、`billing: string`（枚举外的值会是 `<redacted>`，按普通字符串处理）。
  - `QuizsProvidersData`：`{ providers: QuizsProviderRow[] }`。
  - `QuizsLiveStatus`：`state: string`（五个枚举之一，枚举外是 `<redacted>`）、`problem: string | null`、`missing: string[]`、`certificate: { expires_at_ms: number | null } | null`、`profile: { valid_until: string | null } | null`。
  - `QuizsLiveRow`：`source: 'mailbox' | 'env'`、`provider: string | null`、`problem: string | null`、`status: QuizsLiveStatus | null`。
  - `QuizsLiveData`：`{ live: QuizsLiveRow[] }`。
  - 字段为 null / 缺键 / 不是预期形状时一律按兜底显示（「—」或「未知」），不抛错、不整页崩。
- 逐字表（文案写死，测试照它断言）：
  - 计费（`billingLabel`）：`none_test_only` → 「仅测试」；`step_plan_credits` → 「套餐额度」；`deepseek_prepaid_balance` → 「预付余额」；认不出（含 `<redacted>`）→ 原样显示原值。
  - 状态（`liveStateLabel`）：`ready` → 「就绪」（tone `success`）；`expired` → 「已过期」（tone `danger`）；`build_mismatch` → 「构建不一致」（tone `warning`）；`invalid` → 「无效」（tone `danger`）；`missing` → 「缺文件」（tone `warning`）；`status` 为 null → 「读不出」（tone `danger`）；`status.state` 认不出（含 `<redacted>`）→ 「未知」（tone `neutral`）。只有「就绪」不是醒目的，其余四种色调都醒目。
  - 来源（`liveSourceLabel`）：`mailbox` → 「信箱」；`env` → 「环境变量」。
  - 下一步（`liveNextStep`，纯文字，不含可复制命令）：`ready` → 「不用动」；`expired` → 「续期后再看」；`build_mismatch` → 「重新构建这一套」；`invalid` → 「换一套能用的」；`missing` → 「补齐缺的文件」；`status` 为 null → 「看这一套自己的问题」；状态认不出 → 「按这一套的说明处理」。状态是 `missing` 时，下一步后面追加「缺 <文件名>」（文件名照 `status.missing` 原样，多个用「、」连接）；其它状态**不显示** missing 列表。
  - 逐套的 `problem`（自由文字）与 `status.problem` 都显示在「问题」列里（两个都有就都写，用「；」隔开）；只有 `problem` 时写它，只有 `status.problem` 时写它，都没有就不写这一列（列里显示「—」）。
  - 时刻：毫秒整数先转 ISO 字符串再经 `components/RelativeTime.tsx` 的 `formatLocalUtc` 显示（格式「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」）；`profile.valid_until` 直接经 `formatLocalUtc`；null、不是数、解析不了的一律显示「—」。**「（UTC 」这串字面量不许出现在本片任何文件里**（只能经 `formatLocalUtc`）。
- 区块与 DOM：
  - `Section` 标题是「Quizs」，放在「就绪检查」之后；区块里**不放任何按钮**；不渲染 `role=status`；不写内联 style；**不嵌 section**（要分区就用 `Section`）；每个 section 都要有 `aria-labelledby` 指 h2。
  - 提供方档案表：`aria-label="Quizs 提供方档案"`，列恰好四列——提供方、模型、思考档位、计费；**没有「档案 id」列**（服务白名单未登记 id），**没有操作列**。思考档位列把数组逐项用「、」连接（如「low、medium、high」），空数组显示「—」。
  - live 套表：`aria-label="Quizs live 套"`，列恰好六列——提供方、来源、状态、证书到期、档案有效期、下一步；**没有操作列、没有按钮**。到期两列各显示自己的时刻；套餐到期（`plan.expires_at_ms`）未放行，**不显示**。
  - 两张表都用 `Table` 组件，`className` 用自己的类（`rt-quizs-table`），**不加 `rt-table`**（那三条规则会让最后一列右对齐、表最小宽 900px）。
  - 空列表文案：提供方档案为空 → 「还没有 Quizs 提供方档案」；live 为空 → 「还没有 Quizs live 套」。
- 错误与重试：
  - **「Quizs 跑不起来」由 providers 信封失败认定**（`!ok || data == null`）：区块顶部写「Quizs 跑不起来」，下面写「命令 config quizs providers --json 返回退出码 N」（退出码为 null 时写「命令 config quizs providers --json 没有返回退出码」），再把 `messages` 逐行原样写出来。此时 live 表照它自己的信封显示。
  - live 信封失败（`!ok || data == null`）时：只在 live 套表的位置写「没能读到 Quizs 的 live 套：命令 config quizs live --json 返回退出码 N」（退出码为 null 同上），并把 `messages` 逐行写出；提供方档案表照常显示。
  - 两封都坏（例如没设 `QUIZS_CMD`）：区块顶部写「Quizs 跑不起来」，live 表里每一套状态写「读不出」，问题列写它自己的 `problem`。
  - live 每一套 `status` 为 null 时状态写「读不出」，**不解析 problem 的文字**来判定状态。
  - 不做重试（与现有读函数一致）；Quizs 读失败**不影响**整页，页面其余部分照常（`data` 态）；`runtimes` 失败仍整页出错。
- 并发、取消与状态变化：不适用——本片没有取消、没有并发写；三个读一次性并行，渲染顺序固定（已登记 → 就绪检查 → Quizs）。桩模式的 `?mock=loading` 挂起时整页仍是「加载中」。
- 兼容性：`api.ts` **只新增**导出（`QuizsProviderRow`、`QuizsProvidersData`、`QuizsLiveStatus`、`QuizsLiveRow`、`QuizsLiveData`、`getQuizsProviders`、`getQuizsLive`），既有导出与签名一个不改；`Envelope` 不变；`WriteAction` 不变；`mock/writes.ts` 的 22 个情景值不变；`src/mock` 仍恰 14 份 JSON；`src/pages` 顶层仍恰 9 个 `*Page.tsx`；`live-api.test.ts` 只加两行不改既有断言；`page-runtimes.test.tsx`、`writes-remove.test.tsx` 只补视图属性参数，不改既有断言。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。
2. **api.ts 加类型与读函数**（照 `getHubRoles`/`getRuntimes` 的写法，不新造机制）：
   - 加五个类型（字段见 Behavior contract「边界输入」）：`QuizsProviderRow`、`QuizsProvidersData`、`QuizsLiveStatus`、`QuizsLiveRow`、`QuizsLiveData`。枚举值用 `string` 收（服务端会把越界的枚举遮成 `<redacted>`），不要用字面量联合类型把 `<redacted>` 挡在类型外。
   - 加两个读函数：
     ```ts
     export function getQuizsProviders(): Promise<Envelope<QuizsProvidersData>> {
       const client = liveClient();
       if (client) return client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60);
       return read(['config', 'quizs', 'providers', '--json'], () =>
         okEnvelope(['config', 'quizs', 'providers', '--json'], clone(QUIZS_PROVIDERS)),
       );
     }
     export function getQuizsLive(): Promise<Envelope<QuizsLiveData>> {
       const client = liveClient();
       if (client) return client.get<QuizsLiveData>('/api/v1/quizs/live', undefined, 150);
       return read(['config', 'quizs', 'live', '--json'], () =>
         okEnvelope(['config', 'quizs', 'live', '--json'], clone(QUIZS_LIVE)),
       );
     }
     ```
     真实分支**不**回落桩；桩分支用 `clone()` 深拷贝。
   - 桩的情景（broken / expired / missing / empty）由 `mock/quizs.ts` 按 `?quizs=` 给出，所以读函数改成 `read(command, () => quizsProvidersEnvelope())` / `read(command, () => quizsLiveEnvelope())` 这类**按情景取信封**的写法（信封的 `command` 字段照上例，`ok:true` 时 `exit_code:0`；broken 时 providers 的信封是 `ok:false`、`exit_code:1`、`data:null`、`messages` 一行以「ERROR: 」开头）。信封的其余字段照 `api.ts` 里既有 `okEnvelope`/错误信封的形状。
   - `import { … } from './mock/quizs';`（照其它夹具的 import 写法）。
3. **`desktop/web/src/mock/quizs.ts`（新文件，只能 .ts）**：纯类型导入 `import type { Envelope, QuizsProvidersData, QuizsLiveData } from '../api';`。导出：
   - `export type QuizsScenario = 'ok' | 'expired' | 'missing' | 'broken' | 'empty';`
   - `export function quizsScenario(): QuizsScenario` —— 读 `location.hash` 的查询串里的 `quizs` 键（写法照 `mock/writes.ts:36-49` 的 `writeScenario`，只认 `quizs` 这一个键）；缺省或认不出按 `ok`。
   - `export function quizsProvidersEnvelope(): Envelope<QuizsProvidersData>` 与 `export function quizsLiveEnvelope(): Envelope<QuizsLiveData>` —— 按 `quizsScenario()` 给对应情景的信封。
   - 夹具内容（形状只写真内核交得出的字段，见 Repository facts 的白名单）：
     - **ok**（缺省）：providers 两行——`{ provider:'stepfun', model:'step-5-preview', thinking:['low','medium','high'], billing:'step_plan_credits' }`、`{ provider:'deepseek', model:'deepseek-chat', thinking:['low','high'], billing:'deepseek_prepaid_balance' }`（取值出处：已核实的仓库外事实第一条）。live 两套，都 `status.state = 'ready'`、`problem: null`、`status.problem: null`、`missing: []`：一套 `source:'mailbox'`、一套 `source:'env'`，`provider` 都是 `'deepseek'`；`certificate.expires_at_ms` 用一个未来的毫秒整数（`1790000000000`），`profile.valid_until` 用 `'2026-11-20T08:00:00.000Z'`。
     - **expired**：providers 同 ok；live 里 mailbox 那一套 `status.state = 'expired'`、`certificate.expires_at_ms` 用一个过去的毫秒整数（`1700000000000`），env 那一套仍是 ready。
     - **missing**：providers 同 ok；live 里 mailbox 那一套 `status.state = 'missing'`、`status.missing = ['qualification.json']`，env 那一套仍是 ready。
     - **broken**：providers 的信封是 `ok:false`、`exit_code:1`、`data:null`、`messages` 恰好一行、以「ERROR: 」开头（内核原文不在已核实事实里，不许编造原文）；live 的信封 `ok:true`、`exit_code:0`，两套各自 `source`（一 mailbox 一 env）、`provider:'deepseek'`、`status:null`、`problem` 以「quizs live status 失败（退出码 127）：」开头。
     - **empty**：providers 的 `providers` 是空数组，live 的 `live` 是空数组（两个信封都是 `ok:true`）。
4. **`RuntimesPage.tsx`**：
   - `import { getQuizsProviders, getQuizsLive, getRuntimes, type Envelope, type QuizsLiveData, type QuizsProvidersData, type RuntimesData } from '../api';`（两个新读函数已在 T009 的 `ALLOWED_API_READS` 里）。
   - `loadRuntimes` 改成并行三个读（写法照 `RolesPage.tsx:23-41`）：`Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])`；`runtimes` 失败时整页返回它的信封（`!ok || data == null`）；成功时返回 `{ ok:true, exit_code:0, data:{ runtimes, quizs:{ providers, live } }, output:[], messages:[], command: runtimes.command, elapsed_ms:0 }`。
   - `isRuntimesEmpty` 仍只看 `runtimes.length === 0`；页头说明、页头两个按钮、`PageFrame` 的用法、`children` 签名都不动。
   - 视图数据的类型定义放哪都行（放在 `RuntimesPage.tsx` 里导出，或放在视图文件里），只要 `RuntimesView` 的 `quizs` 属性类型与之逐字一致（见第 5 步）。
5. **`readonly1/runtimes-RuntimesView.tsx`**：`RuntimesViewProps` 加**必填**属性 `quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> }`（`Envelope` 用 `import type` 从 `../../api` 引入）；在「就绪检查」一节之后渲染 `<QuizsBlock quizs={quizs} />`；「已登记」「就绪检查」两节的标题与内容**一字不改**；视图仍不调 api（从 `../../api` 只许 `import type`）；`useWriteFlow(reload)`、`[探测][模型]`、`[删除…]` 照旧。
6. **`readonly1/runtimes-QuizsBlock.tsx`（新文件）**：
   - `Section title="Quizs"`（不加 description、不加次级标签）；内容是两张 `Table`。
   - 提供方档案表：`aria-label="Quizs 提供方档案"`，列头依次 提供方、模型、思考档位、计费；`className="rt-quizs-table"`；每行 `rowKey` 用提供方名（相同就加序号）。
   - live 套表：`aria-label="Quizs live 套"`，列头依次 提供方、来源、状态、证书到期、档案有效期、下一步；`className="rt-quizs-table"`。
   - 文案、标签色调、空态与错误显示照 Behavior contract 的逐字表；状态用 `Tag`（tone 见表）；时刻经 `formatLocalUtc`。
   - 视图只收数据：从 `../../api` 只许 `import type`；纯函数放 `runtimes-quizs-logic.ts`。
7. **`readonly1/runtimes-quizs-logic.ts`（新文件，纯函数）**：从 `../../api` 只 `import type`；导出：
   - `billingLabel(billing: string): string`（逐字表；认不出原样返回）。
   - `liveStateLabel(state: string | null): { label: string; tone: TagTone }`（逐字表；`null` → 「读不出」；认不出 → 「未知」）。
   - `liveSourceLabel(source: string): string`（mailbox → 「信箱」、env → 「环境变量」；认不出原样返回）。
   - `liveNextStep(state: string | null, missing: readonly string[]): string`（逐字表；状态是 `missing` 时追加「缺 …」）。
   - `formatMsUtc(ms: number | null | undefined): string`（毫秒整数 → `formatLocalUtc(new Date(ms).toISOString())`；null / 不是数 / 解析不了 → 「—」）。
   - `formatIsoUtc(iso: string | null | undefined): string`（经 `formatLocalUtc`；null / 解析不了 → 「—」）。
   - `providersUnavailable(env: Envelope<QuizsProvidersData>): boolean`（`!ok || data == null`）。
   - `liveUnavailable(env: Envelope<QuizsLiveData>): boolean`（同上）。
   - 纯函数不碰 DOM、不引计时器。
8. **`readonly1/runtimes-styles.css`**：只在文件末尾追加 `.rt-quizs*` 规则，不改现有规则。规矩：只用令牌（不写十六进制颜色、不写颜色函数、不拼接 `--tt-` 令牌名）；除 `0` 与 `1px` 外的 px 字面量，所在行要带出处注释（照现有写法 `/* 画布：… */`）；`border-radius` 只用令牌。至少要有 `.rt-quizs-table`（表的容器覆盖，照 `.rt-table` 那三条但去掉 min-width 900px 与最后一列右对齐）与两处文字/提示的类（如 `.rt-quizs-err`、`.rt-quizs-empty`）。**不要复用 `rt-table` 类**。
9. **测试**：
   - `desktop/web/tests/live-api.test.ts`：`ROWS` 加两行 `{ name:'getQuizsProviders', run:()=>api.getQuizsProviders(), path:'/api/v1/quizs/providers', timeout:60 }`、`{ name:'getQuizsLive', run:()=>api.getQuizsLive(), path:'/api/v1/quizs/live', timeout:150 }`；把 describe 标题里的读函数个数从 16 改成 18；**既有断言一条不改、不删**。
   - `desktop/web/tests/page-runtimes.test.tsx`：四处 `render(<RuntimesView runtimes={RUNTIMES} />)` 补上 `quizs` 属性（用本文件里新加的一个小夹具：两个 `ok` 信封，内容照 `mock/quizs.ts` 的 ok 情景）；既有断言一条不改。
   - `desktop/web/tests/writes-remove.test.tsx:221`：同样补 `quizs` 属性；既有断言一条不改。
   - `desktop/web/tests/page-quizs.test.tsx`（新）：桩模式下挂载 `#/runtimes?quizs=<情景>`（或直接渲染 `QuizsBlock`），断言：
     - 区块存在、标题是「Quizs」；两张表的 `aria-label` 分别是「Quizs 提供方档案」「Quizs live 套」；
     - 提供方档案表四列（提供方、模型、思考档位、计费），两行的内容逐字对上（stepfun 行：模型 step-5-preview、思考档位「low、medium、high」、计费「套餐额度」；deepseek 行：计费「预付余额」）；
     - live 表六列，ok 情景里两套的状态是「就绪」、来源是「信箱」/「环境变量」、下一步是「不用动」、到期两列非「—」；
     - expired 情景：那一套状态是「已过期」、下一步是「续期后再看」；
     - missing 情景：那一套状态是「缺文件」、下一步含「缺 qualification.json」；
     - empty 情景：两张表各显示空态文案；
     - broken 情景：区块里出现「Quizs 跑不起来」，live 表两套状态都是「读不出」，问题列含「quizs live status 失败（退出码 127）」；
     - providers 失败（用替身 api 或 `setLiveClientForTests` 注入失败信封）时：只有 Quizs 一块显示失败，已登记表与就绪检查照常，整页仍是 data 态；
     - runtimes 失败时整页出错；
     - 区块里**没有按钮**（`querySelectorAll('button')` 为空）、没有 `role=status`、没有内联 `style`；
     - 时刻断言只比 UTC 那一段或用 `formatLocalUtc` 算期望值，不写死本地时间。
   - `desktop/web/tests/quizs-logic.test.ts`（新）：`billingLabel` 三值与认不出、`liveStateLabel` 五个状态 + null + 认不出、`liveSourceLabel`、`liveNextStep` 各状态与 missing 追加、`formatMsUtc`/`formatIsoUtc` 的 null 与非法值、`providersUnavailable`/`liveUnavailable` 的真假。
   - 新测试不用 `skip`/`only`/`todo`；不新增依赖；不改 `page-app.test.tsx`、`readonly2-app.test.tsx`。
10. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → R01**（G01 的流水线会先在验证工作区的 `desktop/web` 里 `npm ci`，排在它前面的 `npm test`、`npm run typecheck` 找不到 vitest、tsc，基线上也是红的），记录命令与结果。
11. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t043_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`getQuizsProviders()` 与 `getQuizsLive()` 两条分支都成立：真实模式分别是 `GET /api/v1/quizs/providers`（60 秒）与 `GET /api/v1/quizs/live`（150 秒）、失败不回落桩；桩模式命令是 `config quizs providers --json` 与 `config quizs live --json`，`?mock=loading` 挂起、`?mock=error` 回错误信封。证据：V01、G01；目的：真实模式下页面不能拿桩当真实档案显示。
- D02：类型与夹具只用 T042 白名单登记的字段（providers：provider/model/thinking/billing；live：source/provider/problem/status.problem/state/missing/certificate.expires_at_ms/profile.valid_until）；没有「档案 id」列，不显示 live_dir、plan.*、issued_at_ms。证据：V01、G01、R01；目的：服务只放行这些字段，前端不该显示拿不到或不该显示的东西。
- D03：页面并行发出三个读；只有 runtimes 失败才整页失败（错误块照旧写命令与退出码）；两个 Quizs 信封整个放进视图数据；`isEmpty` 仍只看 runtimes 的长度；`?mock=` 五态下的页面状态与现在一样。证据：V01、G01；目的：Quizs 读不出来时这一页仍然可用。
- D04：Quizs 区块在「就绪检查」之后，标题「Quizs」；提供方档案表四列（提供方、模型、思考档位、计费）、live 套表六列（提供方、来源、状态、证书到期、档案有效期、下一步）；区块里没有按钮、没有 `role=status`、没有内联 style、不嵌没有标题的 section。证据：V01、G01、V03；目的：这一块是只读展示，不提前开写入口，也不撞 T009 的按钮白名单与悬停提示断言。
- D05：逐字表落地：计费三值「仅测试 / 套餐额度 / 预付余额」（认不出原样）；状态「就绪 / 已过期 / 构建不一致 / 无效 / 缺文件 / 读不出 / 未知」且只有「就绪」不醒目；来源「信箱 / 环境变量」；下一步「不用动 / 续期后再看 / 重新构建这一套 / 换一套能用的 / 补齐缺的文件 / 看这一套自己的问题 / 按这一套的说明处理」，missing 状态追加「缺 <文件名>」；空列表文案「还没有 Quizs 提供方档案」「还没有 Quizs live 套」。证据：V01、G01；目的：文案没有出处可依，由合同写死才能被断言与复审。
- D06：错误路径：providers 失败 → 区块写「Quizs 跑不起来」+ 命令 + 退出码 + messages，live 表照自己的信封显示；live 失败 → 只在 live 表位置写读失败；两封都坏 → 顶部「Quizs 跑不起来」且每套状态「读不出」并写自己的 problem；Quizs 失败不影响整页与另两节。证据：V01、G01；目的：没设 QUIZS_CMD 时只有这一块坏，页面其余照常。
- D07：时刻经 `components/RelativeTime.tsx` 的 `formatLocalUtc` 显示（毫秒整数先转 ISO）；null、非法值显示「—」；本片任何文件都不出现「（UTC 」字面量（这条只由 T013 的单一来源断言负责）。证据：V01、R01；目的：本地时间随机器时区变，写死会红，且「（UTC 」只能有一份。
- D08：新代码守既有源码规矩：`src/mock/quizs.ts` 与 `src/pages/readonly1/**` 不渲染 `role=status`、不调 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver、不写十六进制颜色与颜色函数；`src` 下不出现网络词与危险 HTML 写入/动态求值类词（注意 `page-static.test.ts` 按子串查，命名避开 refetch/prefetch 之类）；CSS 只用令牌、带 px 的行有出处注释、不用 `rt-table` 类。证据：G01、R01、V02；目的：不破 T006/T009/T023 的长期门禁。
- D09：既有测试没被删、跳过或弱化：`page-app.test.tsx` 运行时页禁用钮仍是 5 个（区块里不加按钮）、`readonly2-app.test.tsx` 不改、`live-api.test.ts` 只加两行、另两处既有测试只补视图属性参数；新测试不用 skip/only/todo。证据：V01、review；目的：既有断言是长期保护，不能为了新功能放松。
- D10：所有修改都在允许集合内（7 个可改文件、5 个可新增文件），没有碰 forbidden_paths；`src/mock` 仍恰 14 份 JSON、`src/pages` 顶层仍恰 9 个 `*Page.tsx`；`package.json` 与锁文件不变。证据：scope、G01、R01、V03；目的：这一片不许顺手改别的片的地盘，也不许新增依赖。
- D11：纯函数 `billingLabel`、`liveStateLabel`、`liveSourceLabel`、`liveNextStep`、`formatMsUtc`、`formatIsoUtc`、`providersUnavailable`、`liveUnavailable` 都有测试（含 null、非法值与认不出的枚举值）。证据：V01；目的：文案与兜底的边界先钉住，视图只负责摆。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `ALLOWED_API_READS` 里没有 `getQuizsProviders`/`getQuizsLive`、或服务回的字段形状与合同写的类型对不上），特别是：基线上「CLI 运行时」的视图文件不叫 `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`、或其纯函数文件不叫 `desktop/web/src/pages/readonly1/runtimes-logic.ts`（这两处由 T041、T042 两片合同佐证未改名；若基线上被改名，停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `ts/packages/ui`、`scripts/`、`src/mock/*.json`、`src/components/`、既有门禁测试或 `page-app.test.tsx`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在本片加写入口或显示未放行的字段）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，含返工版本；累计已用 0 次——本版留 2 次实现与定点返工，余量 1 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（3 次 × 5400；累计已用 0 秒，本版可用 16200 秒 ≥ 2×5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与核对事实 25 分钟；实现（api.ts、桩、页面、视图、区块、纯函数、CSS）70 分钟；补测 45 分钟；必要检查（G01、V01、V02、V03、R01）50 分钟；最终报告 15 分钟；总计约 205 分钟，单轮时限 5400 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
