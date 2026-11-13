# TASK: t031-desktop-ui-hub-roles

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 7a3bd3f9e8412ee1b3941ea2198bcc73f3b611a1
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端本机服务（`ts/packages/ui`）接进七端六个岗位绑定的读路由与写路由：`GET /api/v1/hub/roles` 起内核子进程跑 `config hub show --json`（要会话、时限 30 秒、信封、二道脱敏，字段逐个登记白名单），`POST /api/v1/hub/roles/<岗位>` 与 `POST /api/v1/hub/roles/<岗位>/unset` 走既有的「预览 → 确认号 → 带令牌执行 → 操作终态」写链路（新增 action `hub.set`、`hub.unset`），「开放的写命令」集合从 12 条加到 14 条并与内核的 `--dry-run` 集合逐条相等，README 的路由表与条数同步。

## Non-goals
- 不做界面（`desktop/web`）：那是另一片；本片只动 `ts/packages/ui`。
- 不做 Quizs 的提供方档案与证书状态路由；不让 `runtime.add` 支持 quizs 适配器。
- 不改内核文件（`scripts/**`、`ts/packages/config/**`、`ts/packages/base/**`）、不改 `desktop/**`、不改 `docs/**`、不改 `ts/packages/ui/src/server.ts`（放宽空闲超时的那一批按 readRoutes 与 writeRoutes 判定，新路由自动进去）。
- 不改 `ts/packages/ui/package.json` 与 `ts/bun.lock`，不新增依赖：ui 包的依赖清单仍只许 `@themis/base` 与 `@themis/contracts`（T019 门禁查这一点），所以岗位名与适配器名另抄一份并在注释里注明出处。
- 不改 `ts/packages/ui/src/localhttp/**`、`src/routes.ts`（`public: true` 仍恰好两处，只落在 bootstrap 与 control.bootstrap 上）、`src/cursors.ts`、`src/confirmations.ts`、`src/operations.ts`、`src/kernelenv.ts`（审计 actor `user-ui` 是它定的，本片沿用）。
- 不动任何 `tests/test_gate_*.py`（站主已把钉死旧条数的七处断言放宽成「不少于」，本片只往表里加，不许改名或删）。
- 不改 `PREVIEW_ALLOW`（hub 的预览没有新的会被误遮的字段）、不改 `NOT_OPEN_WRITE_COMMANDS`、不改 `allowPreviewName` 的语义。

## Repository facts
- 入口：`ts/packages/ui/src/readroutes.ts`（`READ_ROUTE_SPECS` 19 条、`READ_ROUTE_ARGV`、`readRoutes(state, timeouts)`、`jsonRoute(state, argv, timeoutSeconds, input, allow)`、`DEFAULT_TIMEOUT = 30`）、`ts/packages/ui/src/writeroutes.ts`（`WRITE_ACTIONS` 12 个、`WRITE_ARGV` 13 行、`OPEN_WRITE_COMMAND_PATHS` 12 条、`PENDING_WRITE_COMMAND_PATHS`（现为 `["config hub set","config hub unset"]`）、`NOT_OPEN_WRITE_COMMANDS` 8 条、`validValue`、`validateWriteArgs`、`buildWriteArgv`、`mergeArgs`（路径参数压正文）、`previewRoute`、`executeWrite`、`writeRoutes(state, timeouts)`）、`ts/packages/ui/src/redaction.ts`（`CONFIG_ALLOW`/`PROFILES_ALLOW`/`SECRETS_ALLOW`/`SECRET_SHOW_ALLOW`/`PREVIEW_ALLOW`、`allowEnum`/`allowId`/`allowPreviewName`/`allowPreviewText`）。
- 调用关系与现有约定：写链路是「预览（`POST /api/v1/preview`，正文 `{action, args}`）→ 43 位确认号 → 带 `--expect-state=<state>` 的执行（`needs_yes` 为真才加 `--yes`）→ 操作表 `GET /api/v1/operations/<id>`」；预览要内核的 `dry_run`/`action`/`state`/`needs_yes` 都合格才发号（`checkPreview` 把 `action` 与请求逐字比）；`mergeArgs` 里路径参数压过正文同名键；`kernelEnv()` 给每个内核子进程设 `CODEKIT_ACTOR=user-ui`（审计 actor）。
- 内核侧事实（只读参照，已在新基线上核对）：`scripts/kit_roles.py` 的 `HUB_POST_ADAPTERS`（六个岗位 coordinator、planner、contract、gate、audit、exec；各自允许的适配器是 coordinator→quizs/pi、planner→claude-code、其余→pi）与 `HUB_POSTS`；`_hub_rows` 的行形状（缺省行 = `post`、`source="default"`、`allowed_adapters` 数组、`adapter`、`provider`、`model`、`thinking`、`fallback`（coordinator 是四键对象，其余 null）、`profile=null`、`runtime=null`；配置行 = `post`、`source="config"`、`allowed_adapters`、`profile`、`runtime`、`adapter`、`provider`、`model`、`thinking`、`fallback`（六字段对象或 null））；`_hub_show` 输出 `{"posts":[…]}`；`_hub_set`/`_hub_unset` 的事务名是 `hub.set`/`hub.unset`。`scripts/kit_config.py`：`config hub show --json`；`config hub set <post> <profile> [--fallback=<profile>]` 与 `config hub unset <post>`，两者都带 `--yes` 与 `--dry-run`/`--json`/`--expect-state`。`ts/packages/config/src/roles-commands.ts` 的 `withConfigTransaction(ctx, "hub.set", …)`/`"hub.unset"` 与 `hubRows`（与 Python 同形状）。岗位名与适配器名的**可引出处**是 `scripts/kit_roles.py` 的 `HUB_POST_ADAPTERS` 与 `HUB_DEFAULTS`（TS 一份在 `ts/packages/config/src/roles-check.ts` 的 `HUB_POST_ADAPTERS`/`HUB_DEFAULTS`）；ui 包不许 import `@themis/config`（依赖清单只许 base 与 contracts），所以另抄一份并在注释里注明出处。
- 脱敏语义（`ts/packages/base/src/secrets.ts` 的 `redactJson`）：对登记了校验函数的路径，值为 `null` 时**照样**调校验函数，不合格就把 `null` 换成 `<redacted>`。所以凡是内核会给 `null` 的字段，白名单的校验函数都必须接受 `null`，否则 U9 的逐字段一致用例会红。
- 被锁定的基准测试（只许按本合同第四节改那几处）：`ts/packages/ui/test/routes-auth.test.ts`（`READ_ROUTE_EXAMPLES` 19 条、`expect(listed.length).toBe(19)`）、`ts/packages/ui/test/kernel-runner.test.ts`（`CASES` 覆盖 19 条、时限数组 19 个值、`waitForBegin` 等假内核真的起来）、`ts/packages/ui/test/argv-templates.test.ts`（`expect(READ_ROUTE_SPECS).toHaveLength(19)`）、`ts/packages/ui/test/write-argv.test.ts`（W1–W4，W2 的 `expect(open).toHaveLength(12)` 与 `known`＝开放＋`PENDING`、W4 的 `Object.keys(WRITE_ACTIONS).sort()` 名单 12 个）、`ts/packages/ui/test/write-config.test.ts`（「令牌不外泄：12 行 × 4 查法」的 `ROWS` 12 行）、`ts/packages/ui/test/fixtures/fake-write-kernel.mjs`（`SUBACTIONS` 与 `deriveAction`；T019 点名的记号 `FAKE_KERNEL_REPORT`、`FAKE_WRITE_PREVIEW`、`FAKE_WRITE_PLAN`、`FAKE_WRITE_GATE`、`FAKE_WRITE_BEGIN`、`--dry-run`、`--expect-state`、`ok`、`stale`、`audit-fail`、`pause` 一个都不许少）。
- 门禁现状（站主已放宽，只许加不许减）：T018/T019 的读路由条数断言是「不少于 19 条」并逐条查名字；T020 的 `WRITE_ACTIONS` 是「不少于 12 个」、`WRITE_ARGV` 是「不少于 13 行」、README「写操作」一节只认写明了条数；T016 的 `public: true` 恰好两处在 `src/routes.ts`；T019 的 `readroutes.ts` 去注释后不许出现 `WRITE`、也不许出现写路由名，ui 包依赖清单只许 base 与 contracts。
- 工具链与锁文件：`ts/` 下 Bun + Vitest（`node node_modules/vitest/vitest.mjs run packages/ui/test`）、类型检查 `node node_modules/typescript/bin/tsc -p tsconfig.json`；依赖用 `bun install --frozen-lockfile` 装；`ts/bun.lock` 与 `ts/packages/ui/package.json` 不许改。真内核是 `scripts/pi_dispatch.py`（Python），替身是 `ts/packages/ui/test/fixtures/fake-write-kernel.mjs` 与 `fake-kernel.mjs`（Node 跑）。
- 基线检查：站主已在新基线上把 `config hub set`/`config hub unset` 记进 `PENDING_WRITE_COMMAND_PATHS`，`write-argv.test.ts` 的 W2 现在是绿的（两张表合起来与内核的 14 条 `--dry-run` 命令逐条相等、互不相交）。本片做的是把这两条**挪进** `OPEN_WRITE_COMMAND_PATHS`（12 → 14），`PENDING_WRITE_COMMAND_PATHS` 导出保留、值变空数组；W2 的写法（两张表合起来与内核集合相等、互不相交）保留。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/redaction.ts
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/ui/README.md
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/test/kernel-runner.test.ts
  - ts/packages/ui/test/argv-templates.test.ts
  - ts/packages/ui/test/write-argv.test.ts
  - ts/packages/ui/test/write-config.test.ts
  - ts/packages/ui/test/fixtures/fake-write-kernel.mjs
- allowed_new_files:
  - ts/packages/ui/test/hub-routes.test.ts
  - ts/packages/ui/test/hub-routes-real.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t031_*.py
  - tests/test_gate_*.py
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/src/routes.ts
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/src/kernelenv.ts
  - ts/packages/ui/package.json
  - ts/bun.lock
  - ts/packages/base/**
  - ts/packages/contracts/**
  - ts/packages/config/**
  - desktop/**
  - docs/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 既有测试文件的处置口径（站主已批准，只照下面第四节逐条改）：`routes-auth.test.ts`、`kernel-runner.test.ts`、`argv-templates.test.ts`、`write-argv.test.ts` 四份**只许**改本合同第四节点名的那几处（加一行/加名、条数 19→20 与 12→14、注释里的条数）；`write-config.test.ts` 与 `test/fixtures/fake-write-kernel.mjs` 只**追加**（令牌表加两行、替身的 action 映射加两条）。除此之外不删、不改、不弱化任何既有用例（不许出现 skip/only/todo）。新用例一律写在新建的两份 `hub-routes*.test.ts` 里。

## Behavior contract

### 一、读路由 `GET /api/v1/hub/roles`

- 路由名 `api.hub.roles.get`，路径 `/api/v1/hub/roles`，方法 GET，时限 30 秒（`DEFAULT_TIMEOUT`）；要会话（不标 `public`）。
- 登记为 `READ_ROUTE_SPECS` 的**第 20 条**（追加在表末，顺序即路由表顺序）：`{ name: "api.hub.roles.get", path: "/api/v1/hub/roles", timeoutSeconds: DEFAULT_TIMEOUT }`。
- `READ_ROUTE_ARGV` 加一项：`"api.hub.roles.get": ["config", "hub", "show", "--json"]`。
- 处理函数：`jsonRoute(state, ["config","hub","show","--json"], at("api.hub.roles.get", DEFAULT_TIMEOUT), input, HUB_ROLES_ALLOW)`；与其它读路由一样：退出非 0 也回 200（信封里 `ok` 为假）、stdout 解析不了 JSON 且退出 0 回 500「内核输出不是合法的 JSON」。
- `readroutes.ts` 去注释后**不许**出现字符串 `WRITE`，也不许出现写路由名（`api.hub.roles.set`/`api.hub.roles.unset`/`hub.set`/`hub.unset`）；文件头注释里的「19 条读路由」改成「20 条读路由」。
- 响应 `data` 的形状是内核 `config hub show --json` 的 `{"posts":[…]}`，每行是第二节那张表的字段。

### 二、脱敏白名单 `HUB_ROLES_ALLOW`（放 `ts/packages/ui/src/redaction.ts`）

`HUB_ROLES_ALLOW` 是一个导出的 `AllowList`（路径是 `posts` 之下的一行行岗位）。下表逐条给出路径与约束；**「可空」列说「是」的字段，校验函数必须接受 `null`**（否则内核给 null 时该值会被换成 `<redacted>`，U9 的逐字段一致就会红）。

| 白名单路径 | 约束 | 可空 |
|---|---|---|
| `posts.*.post` | 枚举：coordinator、planner、contract、gate、audit、exec | 否 |
| `posts.*.source` | 枚举：`default`、`config` | 否 |
| `posts.*.allowed_adapters.*` | 枚举：pi、claude-code、codex、opencode、quizs | 否 |
| `posts.*.adapter` | 五个适配器的枚举 | 是 |
| `posts.*.provider` | `allowBindingName` | 是 |
| `posts.*.model` | `allowBindingName` | 是 |
| `posts.*.thinking` | 枚举：off、minimal、low、medium、high、xhigh、max | 是 |
| `posts.*.profile` | `allowId` | 是 |
| `posts.*.runtime` | `allowId` | 是 |
| `posts.*.fallback.adapter` | 五个适配器的枚举 | 是 |
| `posts.*.fallback.provider` | `allowBindingName` | 是 |
| `posts.*.fallback.model` | `allowBindingName` | 是 |
| `posts.*.fallback.thinking` | 七个档位的枚举 | 是 |
| `posts.*.fallback.profile` | `allowId` | 是 |
| `posts.*.fallback.runtime` | `allowId` | 是 |

- `allowBindingName` 是 `redaction.ts` 里**新增**的导出函数，规则写死成一条：值为 `null` 直接放行；否则必须是字符串，正则 `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$`，并且 `tokenShaped` 为假（不像凭据）。`provider`、`model` 与 fallback 里的同名字段统一用它。
- `allowPreviewName` 是既有白名单在用的函数，本片不许改它的语义，也不许拿它顶替 `allowBindingName`（它的字符集更窄，不带 `@` 与 `+`）。
- 五个适配器名是 `pi`、`claude-code`、`codex`、`opencode`、`quizs`（`quizs` 是 coordinator 的缺省载体，只进这个枚举，不进 `runtime.add` 用的四值 `ADAPTERS`——那四个值本片不动）。
- `posts.*.fallback` 本身（对象或 null）**不登记**；`posts` 这个键下也不登记别的路径。
- 岗位名与适配器名的出处要写在注释里：岗位六个名字抄 `scripts/kit_roles.py` 的 `HUB_POST_ADAPTERS`（TS 一份在 `ts/packages/config/src/roles-check.ts`），五个适配器名抄同一处的 `HUB_POST_ADAPTERS` 与 `ADAPTERS`。
- 白名单之外的字段一律按 `redactJson` 的默认口径处理（敏感键下的值遮掉）；本片不许给白名单开口子放凭据。

### 三、两条写路由

| action（逐字） | 路由名 | 路径 | 方法 | 路径参数键 | 必填 | 可选 | 基础 argv |
|---|---|---|---|---|---|---|---|
| `hub.set` | `api.hub.roles.set` | `/api/v1/hub/roles/<post>` | POST | `post` | `post`、`profile` | `fallback` | `["config","hub","set",post,profile]`，给了 `fallback` 再加 `--fallback=<fallback>`（放最后） |
| `hub.unset` | `api.hub.roles.unset` | `/api/v1/hub/roles/<post>/unset` | POST | `post` | `post` | 无 | `["config","hub","unset",post]` |

- 路由名与 action 名不是一回事：路由名照既有风格起（`api.hub.roles.set`/`api.hub.roles.unset`），action 名必须逐字是 `hub.set`/`hub.unset`——预览要内核回的 `action` 与请求的 action 逐字相等（`checkPreview`），内核的事务名就是这两个。
- 两条路由与既有十二条走同一条链：预览 → 43 位确认号 → 带 `--expect-state=<state>` 的执行（`needs_yes` 为真才加 `--yes`）→ 操作表落一条八键记录。要会话、要 CSRF、正文是 JSON 对象；时限 90 秒（`api.write`），预览 30 秒（`api.preview`）。
- 路径参数压过正文里的同名键（`mergeArgs` 照旧）：正文里的 `confirmation` 不进 args。
- 校验（加在 `validValue` 里）：
  - `post`：字符串，且是六个岗位名之一（coordinator、planner、contract、gate、audit、exec）；不合格 → 400「post 不合法」。
  - `fallback`：字符串，过 `TASK_ID_RE`（与 `profile` 同一规则）；不合格 → 400「fallback 不合法」。
  - `profile`：照既有规则（`TASK_ID_RE`），本片不改。
  - 提示固定、不回显请求里的值；不合格不起子进程（替身报告里没有对应的 begin 行）。
- 组合规则（该 profile 登记没有、适配器许不许用在这个岗位、替补合不合规）全交给内核：预览退出非 0 → 回 200、`ok` 为假、`messages` 是内核原文、不发确认号；配置不变。
- 不许的绑定（适配器不能用在这个岗位、profile 没登记）由内核整份校验拒掉（`txn.publish` 的整份校验），信封 `ok: false`、messages 是内核原文、配置与审计逐字节不变。

### 四、四份锁定的基准测试与两份只追加的文件（逐条只改这些）

1. `ts/packages/ui/test/routes-auth.test.ts`：
   - `READ_ROUTE_EXAMPLES` 加一行 `"api.hub.roles.get": "/api/v1/hub/roles"`（放在表末，与登记顺序一致）。
   - `expect(listed.length).toBe(19)` 改成 20；同一行的注释「19 条，一条不多一条不少」改成「20 条，…」。
   - 文件头注释里的两处「19 条读路由」、describe 标题「19 条读路由都要会话（T17）」、用例名「「路由名 → 示例路径」表正好是路由表里的 19 条读路由」、以及第 3 片与第 7 片两个 describe 注释里的「既有的 19 条表」都改成 20 条。
   - 其余断言（逐条 401、逐条 503、顺序与 `READ_ROUTE_SPECS` 一致、`api.secrets.list` 的例外）一字不改。
2. `ts/packages/ui/test/kernel-runner.test.ts`：
   - `CASES` 加一行 `{ name: "api.hub.roles.get", path: "/api/v1/hub/roles", argv: READ_ROUTE_ARGV["api.hub.roles.get"] ?? [] }`（放在表末）。
   - 时限数组 `expect(READ_ROUTE_SPECS.map((spec) => spec.timeoutSeconds)).toEqual([...])` 的末尾补一个 `30`（现在 19 个值，改成 20 个，最后一个是新路由的 30）。
   - 文件头注释与 describe 标题里的「19 条」改成 20 条。
   - 其余不动（两条取消用例照站主改好的 `waitForBegin` 写法，本片不改它们）。
3. `ts/packages/ui/test/argv-templates.test.ts`：
   - `expect(READ_ROUTE_SPECS).toHaveLength(19)` 改成 20。
   - 用例名与文件头注释里的「19 条」改成 20 条。
   - 其余不动（新模板 `["config","hub","show","--json"]` 由「每条模板都解析得了」那条用例自动覆盖：它过内核真正的解析器 `kit_config.build_parser()`）。
4. `ts/packages/ui/test/write-argv.test.ts`：
   - W2：`expect(open).toHaveLength(12)` 改成 14；用例名与注释里的「12 条」改成「14 条」；**W2 的写法保留**：仍断言「开放集合 + `PENDING_WRITE_COMMAND_PATHS` 与内核的 `--dry-run` 集合逐条相等」且「两张表互不相交」（挪完之后 `PENDING` 是空数组，两张表合起来仍等于内核的 14 条）。
   - W4 的 action 名单断言 `expect(Object.keys(WRITE_ACTIONS).sort()).toEqual([...])` 加两个名字：`"hub.set"`、`"hub.unset"`（共 14 个，按字典序：`config.rollback`、`hub.set`、`hub.unset`、`plugin.disable`、`plugin.enable`、`preset.remove`、`preset.save`、`preset.use`、`profile.add`、`profile.edit`、`profile.remove`、`role.set`、`runtime.add`、`runtime.remove`）。
   - W3 的 `examples` 表补两条：`"hub.set": { post: "coordinator", profile: "demo-profile", fallback: "demo-fallback" }`、`"hub.unset": { post: "coordinator" }`。
   - 只许**新增**用例（W4 里 `post`/`fallback` 的取值：`post` 不认识、`profile`/`fallback` 以 `-` 开头、`fallback` 不合格；以及 `buildWriteArgv` 两条逐项断言）；不许删改其余既有用例。
5. `ts/packages/ui/test/write-config.test.ts`（只追加）：「令牌不外泄：12 行 × 4 查法」的 `ROWS` 加两行——`hub.set`（`path: "/api/v1/hub/roles/coordinator"`、`body: { profile: "demo-profile" }`）与 `hub.unset`（`path: "/api/v1/hub/roles/coordinator/unset"`、`body: {}`）；该 describe 名与文件头注释里的「12 行」改成「14 行」。表的其余行与四查法一字不改。
6. `ts/packages/ui/test/fixtures/fake-write-kernel.mjs`（只追加）：`SUBACTIONS` 加 `hub: { set: "hub.set", unset: "hub.unset" }`，让 `deriveAction` 把 `config hub set`/`config hub unset` 推成 `hub.set`/`hub.unset`（预览一支的 `action` 与请求逐字相同，否则服务回 500）。T019 点名的记号与 `DEFAULT_PREVIEW`、`stateFor` 的两段规则、`ok`/`stale`/`audit-fail`/`pause` 四种计划一律不动。

### 五、`OPEN_WRITE_COMMAND_PATHS` 与 `PENDING_WRITE_COMMAND_PATHS`

- `OPEN_WRITE_COMMAND_PATHS` 加两条 `"config hub set"`、`"config hub unset"`，共 14 条；既有十二条一条不改、不改名、不删。
- `PENDING_WRITE_COMMAND_PATHS` **导出保留**，值变成空数组 `[]`（这个导出是给后续片留的位置；内核再加可预览的写命令时照旧会被 W2 拦下来）。
- `NOT_OPEN_WRITE_COMMANDS` 不动。
- `WRITE_ARGV` 加两行示例（既有十三行不动，共 15 行，命令路径去重 14 条）：
  - `"hub.set": ["config", "hub", "set", "coordinator", "demo-profile", "--fallback=demo-fallback"]`
  - `"hub.unset": ["config", "hub", "unset", "coordinator"]`
- 这两条示例要过内核真正的解析器（`kit_config.build_parser()`）：`config hub set <post> <profile> --fallback=<profile>` 与 `config hub unset <post>` 都带 `--dry-run --json`、`--expect-state=`、`--yes`（`config` 组有 `--yes`），W1 会逐条验。

### 六、新用例（写在新建的两份文件里）

#### `ts/packages/ui/test/hub-routes.test.ts`（替身用例，进程内建 app，照 `write-config.test.ts` 的写法；内核子进程走 `fake-write-kernel.mjs`）

- 读路由：GET `/api/v1/hub/roles` 的 argv 恰为 `["config","hub","show","--json"]`；不带会话一律 401；`data` 过 `HUB_ROLES_ALLOW` 后，越界的枚举值/凭据形状的值变成 `<redacted>`，合格的原样返回。
- 写路由：`hub.set`/`hub.unset` 的四种 400（岗位不认识、`profile`/`fallback` 以 `-` 开头、`fallback` 不合格、未知键）且不起子进程（替身报告里没有 begin 行）。
- U6 的四种 409：确认号缺失、过期、用第二次、换了参数——四种都回 409，**命令没有运行**（报告里没有带 `--expect-state=` 的 begin 行）；前三种的提示是「确认号无效、已过期或已用过：请重新预览」，换参数那一种是「确认号与这次请求的参数不符：请重新预览」。
- 只有预览说 `needs_yes` 时执行 argv 才带 `--yes`；执行 argv 带 `--expect-state=<state>`，令牌不出现在响应正文里。
- 新写的用例凡是要等子进程起来，一律照 `kernel-runner.test.ts` 的 `waitForBegin` 写法（等替身报告里出现 `begin` 行），**不许固定睡几百毫秒**。

#### `ts/packages/ui/test/hub-routes-real.test.ts`（真内核用例，照 `write-real-config.test.ts` 的写法：git 夹具仓库 + `startService` + 真内核 `scripts/pi_dispatch.py`；不许改 `write-real-config.test.ts`）

- U9：夹具仓库上 `GET /api/v1/hub/roles` 的 `data` 与直接跑 `config hub show --json` 的结果**逐字段相等**（六个岗位逐行比：post、source、allowed_adapters、profile、runtime、adapter、provider、model、thinking、fallback 及其六个子字段）。
- U7：夹具里登记一个 pi 的 runtime 与 profile，经预览 + 确认号执行一次 `hub set` 回 200，审计的 actor 是 `user-ui`；再读 `/api/v1/hub/roles` 能看到 `source` 变成 `config`、profile 是新值。
- U6b：预览之后另起一个内核进程改配置，再执行 → 回 409、`exit_code` 是 4、操作记 `stale`，配置与审计逐字节不变。
- 不许的绑定：把岗位绑到不能用的适配器上、绑一个没登记的 profile → 信封 `ok: false`、messages 是内核原文、配置不变。

### 七、README（`ts/packages/ui/README.md`）

- 「最小 API」一节的读路由表加一行 `GET /api/v1/hub/roles`（`config hub show --json`，30 秒）；写路由表加两行 `POST /api/v1/hub/roles/<post>`（`config hub set <post> <profile> [--fallback=<profile>]`，90 秒）与 `POST /api/v1/hub/roles/<post>/unset`（`config hub unset <post>`，90 秒）。
- 「本片加的 19 条只读数据路由」改成 20 条；「12 条写路由」的各处说法改成 14 条；「写操作」一节写明 14 条写路由，并补一条讲 hub 的两条（必填可选、基础 argv、岗位名只有六个、校验规则、组合规则交给内核）。
- 「连接空闲超时」那一条改成「20 条读路由、预览、14 条写路由」。
- 「已知限制」里「写路由覆盖 12 条（…）」改成 14 条，并把 `hub set`/`hub unset` 列进去。
- README 里至少保留一处「T020」（T019 门禁查这个词），既有段落（`## 日志跟随`、`状态码：201 作业创建成功`、`**作业表只在内存里**` 等）一字不动。

## Steps
1. **读基线**：读 `ts/packages/ui/src/{readroutes,redaction,writeroutes}.ts`、`test/{write-argv,routes-auth,kernel-runner,argv-templates,write-config}.test.ts`、`test/fixtures/fake-write-kernel.mjs`、`test/support.ts`、`test/harness.ts`、`README.md`，以及 `scripts/kit_roles.py`、`scripts/kit_config.py`、`ts/packages/config/src/roles-commands.ts`；确认本合同的符号与形状一致，**不一致就停下报告，不要照抄本文的行号**。
   - 验收：Repository facts 每一项都能对上；目的：不按旧基线的行号改代码；风险：低。
2. **`redaction.ts`**：加 `allowBindingName` 与 `HUB_ROLES_ALLOW`（第二节）；`allowPreviewName` 一字不改。
   - 验收：新用例里越界的枚举值与凭据形状的值变成 `<redacted>`，内核给 null 的字段原样是 null；风险：漏写可空性（A6）。
3. **`readroutes.ts`**：加第 20 条登记项、argv 模板与处理函数（第一节）；文件头注释的条数改成 20；去注释后不许出现 `WRITE`。
   - 验收：`routes-auth.test.ts`（401/503/顺序）、`kernel-runner.test.ts`（argv 与时限）、`argv-templates.test.ts`（真解析器）三条都过；风险：`READ_ROUTE_SPECS` 与 `READ_ROUTE_EXAMPLES` 的顺序不一致（登记表顺序即路由表顺序）。
4. **`writeroutes.ts`**：两个 action 进 `WRITE_ACTIONS`、`validValue` 加 `post` 与 `fallback`、`buildWriteArgv` 加两个分支、`WRITE_ARGV` 加两行、`OPEN_WRITE_COMMAND_PATHS` 加两条、`PENDING_WRITE_COMMAND_PATHS` 变空数组、写路由表加两条（第三节、第五节）；文件头注释的条数与说明改成 14 条。
   - 验收：`write-argv.test.ts` 的 W1–W4 全绿（W2 的集合比对与内核相等、14 条）；风险：把 `PENDING` 导出删掉（必须保留）。
5. **改四份锁定的基准测试与两份只追加的文件**（第四节，逐条只改点名的地方）。
   - 验收：`write-argv.test.ts`、`routes-auth.test.ts`、`kernel-runner.test.ts`、`argv-templates.test.ts`、`write-config.test.ts` 全绿；风险：改动超出点名范围（不许改别的断言）。
6. **替身补两条 action 映射**（第四节第 6 条）。
   - 验收：新写的替身用例里 `hub.set`/`hub.unset` 的预览拿到确认号（预览不合格会回 500）；风险：`deriveAction` 的分支顺序。
7. **替身用例**（新文件 `ts/packages/ui/test/hub-routes.test.ts`）：第二节的白名单、第三节的四种 400、U6 的四种 409、`--yes`/`--expect-state`、令牌不外泄。
   - 验收：每条都有断言；等子进程用 `waitForBegin` 写法；风险：把 409 的两种提示原文写成一样。
8. **真内核用例**（新文件 `ts/packages/ui/test/hub-routes-real.test.ts`）：U9 的逐字段一致、U7 的审计 actor、U6b 的 409/stale、不许的绑定。
   - 验收：四条都过；只在临时夹具仓库里写文件；风险：中（真内核会写配置与审计）。
9. **README**（第七节）。
   - 验收：README 的条数与路由表和实现一致；既有段落一字不动；至少保留一处「T020」。
10. **跑检查并写报告**：跑 Setup 与 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同没有定义的行为就停下报告。
    - 两条硬规矩：① 遇到合同与既有测试或门禁冲突时，不要越界改范围外的文件——把冲突写进执行报告的 `contract_conflicts`，继续做范围内能做的部分；② 临时文件不许写到 `/tmp` 这类固定路径，照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t031_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`

## Definition of done
- D01：读路由 `api.hub.roles.get` 存在且是 `READ_ROUTE_SPECS` 的第 20 条：GET `/api/v1/hub/roles`、时限 30 秒、argv 恰为 `["config","hub","show","--json"]`、不带会话 401、处理器交出的 argv 与 `READ_ROUTE_ARGV` 一致；证据：V01（`routes-auth.test.ts`、`kernel-runner.test.ts`、`argv-templates.test.ts`）、G01；目的：读路由与 argv 模板不漂移。
- D02：`HUB_ROLES_ALLOW` 逐字段登记第二节那 15 条路径，**每一个内核会给 null 的字段都接受 null**；越界的枚举值与凭据形状的值变成 `<redacted>`，合格的值原样返回；证据：V01（替身用例的白名单断言）、V01（真内核用例的 U9 逐字段一致）；目的：二道脱敏既不遮掉合法绑定，也不放过越界值。
- D03：两条写路由存在且走同一条链：`hub.set` → `["config","hub","set",post,profile]`（有 `fallback` 再加 `--fallback=<fallback>`）、`hub.unset` → `["config","hub","unset",post]`；路径参数键是 `post`、路径参数压正文；预览要内核回的 `action` 逐字等于 `hub.set`/`hub.unset`；证据：V01（替身用例的 argv 逐项断言与 W1）、G01；目的：拼错的 argv 内核会拒收，而错在“差不多”上最难发现。
- D04：参数校验按第三节：`post` 只认六个岗位名、`profile`/`fallback` 过 `TASK_ID_RE`、未知键与缺必填键都回固定提示且不起子进程；证据：V01（W4 与替身用例）；目的：服务在起子进程之前挡住形状不对的请求。
- D05：U4：`OPEN_WRITE_COMMAND_PATHS` 恰好 14 条（既有十二条一条不改不加名，两条新的加进去）、`PENDING_WRITE_COMMAND_PATHS` 导出保留且是空数组、开放集合与内核的 `--dry-run` 集合逐条相等且两张表互不相交、`NOT_OPEN_WRITE_COMMANDS` 不动；证据：V01（W2）、G01；目的：开放的写命令必须真的能预览与比对令牌。
- D06：U6——确认号缺失、过期、用第二次、换了参数四种都回 409，且命令没有运行（报告里没有带 `--expect-state=` 的 begin 行）；两种提示原文分别是「确认号无效、已过期或已用过：请重新预览」与「确认号与这次请求的参数不符：请重新预览」；证据：V01（替身用例）；目的：确认号是写命令的一次性闸门。
- D07：U6b——预览之后配置被别的进程改了，执行回 409、`exit_code` 是 4、操作记 `stale`，配置与审计逐字节不变；证据：V01（真内核用例）；目的：令牌比对是防「预览到执行之间被人改了配置」的唯一闸门。
- D08：U7——经本机服务执行 `hub set` 回 200，审计的 actor 是 `user-ui`；再读 `/api/v1/hub/roles` 能看到 `source` 是 `config`、profile 是新值；证据：V01（真内核用例）；目的：界面能读到并改掉岗位绑定。
- D09：U9——真内核上 `GET /api/v1/hub/roles` 的 `data` 与 `config hub show --json` 的结果逐字段相等（六个岗位逐行、十个字段加 fallback 的六个子字段）；证据：V01（真内核用例）；目的：读路由是内核口径的忠实映射，不多不少。
- D10：令牌不外泄的回归保护把新路由算进去：`write-config.test.ts` 的「令牌不外泄」表从 12 行加到 14 行（`hub.set`、`hub.unset` 两行），四查法（预览正文、执行正文、操作正文逐段与整条都不出现、替身报告的 `expect_state` 与整条令牌逐字相同）逐行成立；证据：V01；目的：令牌进了响应正文就等于凭据外泄。
- D11：既有断言一条不推翻——四份锁定的基准测试只改了第四节点名的那几处（19→20、12→14、名单加两个名字、示例补齐），`write-config.test.ts` 与替身只追加；`tests/test_gate_*` 一个字都没动；`readroutes.ts` 去注释后没有 `WRITE`；ui 包依赖清单仍只许 base 与 contracts；`public: true` 仍恰好两处；证据：V01、R01、G01、scope；目的：本片只许加，不许借机改别人的口径。
- D12：README 与行为同步——路由表有三条新路由、条数是 20 条读路由与 14 条写路由、「连接空闲超时」那一条与「已知限制」都对得上、既有段落一字不动、至少保留一处「T020」；证据：V01、G01、R01；目的：README 是这一片的对外说明，不许与实现对不上。
- D13：所有修改都在允许集合内（新增的两份文件在 `allowed_new_files`，没有删文件，`tests/test_gate_*`、`server.ts`、`routes.ts`、`localhttp/**`、`package.json`、`ts/bun.lock` 一个都没动，依赖没变）；证据：scope；目的：越界改文件会让范围检查直接判负。
- D14：没有删除、跳过或弱化既有测试（新写的用例不许出现 skip/only/todo；改断言的那几处是照新事实改数字与名单，不是删断言）；证据：review、V01、R01；目的：既有测试是别的片的契约，不能借机削弱。
- D15：规划与站主点名的设计都落在实现里，合同正文与实现逐条对得上（不留悬着未定的地方）：action 名逐字 `hub.set`/`hub.unset`；`HUB_ROLES_ALLOW` 与 `allowBindingName` 在 `redaction.ts`；岗位名与适配器名的出处写在注释里；`server.ts` 不改；`PREVIEW_ALLOW` 与 `allowPreviewName` 不改；新用例等子进程用 `waitForBegin` 写法；证据：review、V01；目的：合同与实现对得上，下游不用再猜。

D15 附带的变异对照（每条都要有用例杀掉）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | 白名单漏一个字段（例如 `fallback.model`），内核给的值被遮成 `<redacted>` | 真内核 U9 的逐字段一致 |
| M2 | 白名单的某个可空字段不接受 null，缺省行的 null 被遮 | 真内核 U9（缺省行 profile/runtime 是 null、provider 是 null） |
| M3 | 读路由不登记白名单（或登记成别的路径），值被遮 | 替身用例的白名单断言 |
| M4 | `post` 接受任意字符串，坏岗位进了内核 | W4 的 `post` 取值用例与替身用例的 400 |
| M5 | `fallback` 不用 `TASK_ID_RE`，`-x` 进了 argv | W4 的 `fallback` 取值用例 |
| M6 | `buildWriteArgv` 的 hub.set 少给 `--fallback=` 或把它写成两个参数 | 替身用例的 argv 逐项断言 |
| M7 | `hub.unset` 的 argv 写成 `config hub unset --post=` | 替身用例的 argv 逐项断言 |
| M8 | `PENDING_WRITE_COMMAND_PATHS` 没清空，开放集合仍是 12 条 | W2 的 14 条断言与集合比对 |
| M9 | `OPEN_WRITE_COMMAND_PATHS` 改名或删掉既有条目 | W2 的集合比对（与内核逐条相等） |
| M10 | 预览要求 `action` 逐字相等这条被放松（改了 `checkPreview`） | 替身用例：预览的 action 与请求不同时回 500 |
| M11 | 确认号核对被放松（过期或用过还能用） | U6 的四种 409 |
| M12 | 执行时漏带 `--expect-state=` | 令牌表的 `expect_state` 逐字比对 |
| M13 | `needs_yes` 为真时不带 `--yes` | 替身用例的 `--yes` 断言 |
| M14 | 写路由的路径参数不压正文（正文里的 post 覆盖路径） | 替身用例：正文给错 post 时回 409 参数不符 |
| M15 | 读路由的时限不是 30 秒 | `kernel-runner.test.ts` 的时限数组 |
| M16 | 读路由的 argv 与 `READ_ROUTE_ARGV` 不一致 | `kernel-runner.test.ts` 的 argv 断言 |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `READ_ROUTE_SPECS` 不再是 19 条、`writeRoutes` 的形状变了、`redactJson` 对 null 不再调校验函数、`config hub set` 的解析器不接受 `--fallback=`）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/test_gate_*`、`server.ts`、`routes.ts`、`localhttp/**`、`package.json`、`ts/bun.lock`、内核代码或 `desktop/**`）。遇到这种冲突：不要越界改，写进执行报告的 `contract_conflicts`，继续做范围内能做的部分。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如内核的 `config hub show --json` 形状与本合同的行形状对不上，且改动要越过允许范围）。
- 真内核的行为与合同写的不一致（例如预览回的 `action` 不是 `hub.set`），且修正要越过允许范围。
- 达到单轮时限（本版单次 3600 秒）。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本；累计已用 0 次，本版留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200（累计已用 0 秒，7200 秒 ≥ 2 倍单次时限）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 8 分钟；实现（redaction、readroutes、writeroutes）25 分钟；改四份锁定测试与两份只追加文件 10 分钟；写替身用例与真内核用例 25 分钟；README 8 分钟；必要检查（V01–V03、R01、G01）10 分钟；最终报告 4 分钟；总计 90 分钟，不超过单轮时限（3600 秒）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D15，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：16 条变异各自由哪条用例杀掉；`hub.set` 与 `hub.unset` 的完整 argv（逐项）；U9 逐字段一致的比较口径与结果；四种 409 的实测提示原文；真内核用例里审计 actor 的实测值；`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`server.ts`、`routes.ts`、`package.json`、`ts/bun.lock`。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（改断言的那几处是照新事实改数字与名单，不是删断言）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/test_gate_*.py`（含 `tests/test_gate_t031_*.py`）、`ts/packages/ui/src/server.ts`、`ts/packages/ui/src/routes.ts`、`ts/packages/ui/src/localhttp/**`、`ts/packages/ui/package.json`、`ts/bun.lock`、`desktop/**`、`docs/**`、`scripts/**`、`ts/packages/base/**`、`ts/packages/contracts/**`、`ts/packages/config/**`；不改 `ts/packages/ui/test/write-real-config.test.ts` 与 `ts/packages/ui/test/{write-routes,confirmations,operations,write-real,redaction,redaction-routes,cursors,kernel-real}.test.ts`。
- 不在 `ts/packages/ui/src/readroutes.ts` 里出现字符串 `WRITE`（去注释后）；不把 `public: true` 加到任何新路由上；不删掉 `PENDING_WRITE_COMMAND_PATHS` 这个导出；不改 `PREVIEW_ALLOW`、`NOT_OPEN_WRITE_COMMANDS` 与 `allowPreviewName`。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261112T231526521787Z-owner-648ba7：

> 两件事都批准，基线红也属实、已由站主修掉。基线已挪到新末端（见 task rebase 的信），合同端在新基线上写。
>
> 1. 七条钉旧条数的门禁断言：站主已处理（提交“T031 准备：T017–T021 门禁里钉死旧条数的七处，从‘恰好’放宽成‘不少于’”）。做法是放宽，不是整条删掉：读路由表不少于 19 条、WRITE_ACTIONS 不少于 12 个、WRITE_ARGV 不少于 13 行、routes-auth 的条数断言只认还在、README 只认写明了条数；逐条的名字检查都留着（19 条读路由一条不许少，12 个 action 一个不许少）。所以本片只许往这些表里加，不许改名或删。
> 2. 四份锁定的基准测试：批准照规划第 5 节列的改法改既有用例，只限这些——`routes-auth.test.ts` 的 19 改 20、名表加一行、文字里的条数；`kernel-runner.test.ts` 的路由表加一行、时限数组补一个 30；`argv-templates.test.ts` 的 19 改 20；`write-argv.test.ts` 的 12 改 14、W4 的 action 名单加 `hub.set` 与 `hub.unset`、W3 的示例补齐。除此之外不删、不改既有用例；合同把这四份文件列进允许修改范围，并逐条写明只改哪里。
> 3. 基线红：属实。第 154 轮给内核加了两条带 `--dry-run` 的写命令，`write-argv.test.ts` 的 W2 就红了；这是站主合入内核时漏跑 ui 包测试造成的。站主已修（提交“本机服务：内核已有预览、路由还没做的两条写命令单独记一张表”）：`writeroutes.ts` 新增 `PENDING_WRITE_COMMAND_PATHS`（现在是 `config hub set`、`config hub unset`），W2 核对“开放的加上这张表 = 内核的集合”。新基线上 W2 是绿的。本片要做的：把这两条从 `PENDING_WRITE_COMMAND_PATHS` 挪进 `OPEN_WRITE_COMMAND_PATHS`（开放集合 12 变 14），`PENDING_WRITE_COMMAND_PATHS` 留着、变成空数组，W2 的写法（两张表合起来与内核的集合逐条相等、互不相交）保留。规划第 5 节里按“基线是红的”写的那几句，合同照这一条改。
> 4. `kernel-runner.test.ts` 里两条取消用例站主已改成等假内核真的起来再取消（`waitForBegin`）；本片新写的用例要等子进程起来时照这个写法，不要固定等几百毫秒。
