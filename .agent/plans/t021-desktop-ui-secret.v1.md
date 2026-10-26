# TASK: t021-desktop-ui-secret

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: c4d7fa880fdfb86c7078fcdbc40bad2fecd22788
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端本机服务（`ts/packages/ui`）新增凭据录入作业（U18，`POST /api/v1/secrets/<name>/entry`）：以作业方式跑 `config secret set <name> --no-browser --timeout=600`，在子进程还活着时从 stderr 读一次性页面地址并严格核对，地址只活在这一条请求的局部变量里；并新增控制取消（U18b，`POST /control/jobs/<id>/cancel`），把控制门从「按路由名特判」改成按 `Route.control` 统一判断，一次过 Host、Origin、控制令牌三道，免 CSRF、不读正文。

## Non-goals
- 不做外壳侧（Electron 的 `host.openSecretWindow`、关窗调取消的链路，属 D3 的 E8）。
- 不改前端（`desktop/web` 的 api.ts 仍是夹具）。
- 不开放 `--verify`（花钱）与 `--tty`。
- 不改 `ts/packages/ui/src/localhttp/**`（含 `control.ts` 的 ControlGate、`guards.ts` 的 `controlOriginAllowed`）、`ts/packages/ui/src/kernelenv.ts`、`ts/packages/base/**`、`desktop/**`、`docs/**`、`scripts/**` 与内核 Python（`scripts/kit_config.py`、`scripts/codekit/secrets.py`）。
- 不改 `readroutes.ts` 的既有行为（只给 `secretCheckData` 加一个 `export` 关键字）。
- 不合并 `server.ts` 里 `extraRoutes` 与 `kernelAnsweredRoutes` 的两份构造（T020 终审的非阻断建议，另开一片）。
- 不给作业加 SSE 推送，不新增作业状态与失败原因（六种状态、五种 reason 照旧）。
- 不把 `secret-entry` 并进 `POST /api/v1/jobs` 的 kind 名单（`JOB_KINDS`、`JOB_ARGV`、`JOB_TIMEOUTS`、`JOB_ALLOW` 四张表仍是六项）。

## Repository facts
- 入口：`ts/packages/ui/src/kernel.ts`（`RunHooks` 只有 `onStart`、`KernelRunner.run(argv, timeoutSeconds, signal, hooks?)`、`start()` 里 `OUTPUT_POLL_MS = 100` 的轮询只查输出大小、`readOutput` 读不到文件就返回空串、`grace: 2`）、`ts/packages/ui/src/jobs.ts`（`JobKind` 六项、`JobRecord` 无 `exited`、`jobView` 八键、`JobTable.create(kind: JobKind, ...)`）、`ts/packages/ui/src/jobroutes.ts`（`JOB_KINDS`/`JOB_ARGV`/`JOB_TIMEOUTS`/`JOB_ALLOW` 各六项、`runJob` 的终态映射、`api.jobs.cancel` 现在 `await record.run`）、`ts/packages/ui/src/routes.ts`（`Route` 只有 `public?: true`、`ROUTES` 四条、`control.bootstrap` 的处理函数里做令牌比对与 429/`Retry-After`、`findRoute(method, pathname, extra)`）、`ts/packages/ui/src/app.ts`（四步管线：Host → 方法 → 会话 → POST 的 CSRF 与读正文；第 124、131 行两处按路由名 `control.bootstrap` 的特判）、`ts/packages/ui/src/server.ts`（`extraRoutes` 四批合成一批、`kernelAnsweredRoutes` 另建一批、`ServeOverrides.timeouts` 传进各批路由）、`ts/packages/ui/src/readroutes.ts`（`secretCheckData` 在第 184 行附近，未导出；`SECRET_ITEM_TIMEOUT` 30 秒）、`ts/packages/ui/src/localhttp/control.ts`（`ControlGate.check`：恒定时间比较，第 5 次失败起锁定，锁定期内 429 带 `retryAfterSeconds`）、`ts/packages/ui/src/localhttp/guards.ts`（`controlOriginAllowed`：缺 Origin 或同源放行，外来 Origin 拒）。
- 调用关系与现有约定：`server.ts` 把四批 extraRoutes 合成一批交给 `createApp`；作业表的取消靠 `record.controller.abort()`；信封七字段由 `kernelenvelope.ts` 的 `envelopeBody` 手工拼，`data` 走 `@themis/base/pyjson` 的 `dumps`（**只认 `Map` 与数组，普通 JS 对象不可序列化**，本片的 `data` 一律用 `Map` 构造）；`jobView` 的八键是 `id/kind/state/reason/created_ms/started_ms/finished_ms/envelope`；访问日志只记路由名。
- 内核侧事实（只读）：`scripts/kit_config.py` 的 `run_page` 把一次性地址以一行 JSON `{"url","note"}` 写到 **stderr**（`flush=True`），地址是 `http://127.0.0.1:<port>/<token>`、令牌是 `token_urlsafe(24)`（32 个 base64url 字符）；`secret set` 的 stdout 是一行 JSON，键为 `name`、`stored`、`backend`，失败时多一个 `error`，另外恒有 `verified: null`；退出 0 表示已保存、退出 1 表示没存；`--timeout` 是 `type=float`，`--no-browser`、`--verify`、`--tty` 都是开关；`config secret check <name>`（不带 `--json`）打一行 JSON，键为 `name`、`source`、`store_mode`、`system_backend`、`file_dir`；`scripts/codekit/secrets.py` 的 `store_mode` 认不出的值静默退回 `system`，`CODEKIT_SECRET_STORE=off` 时 `cmd_secret` 在起页面之前就报错退出。
- 工具链与锁文件：`ts/` 下 Bun + Vitest（`node node_modules/vitest/vitest.mjs run packages/ui/test`），类型检查 `node node_modules/typescript/bin/tsc -p tsconfig.json`；依赖用 `bun install --frozen-lockfile` 装，锁文件 `ts/bun.lock` 不许改；真内核是 `scripts/pi_dispatch.py`（Python），替身是 Node 跑的 `ts/packages/ui/test/fixtures/*.mjs`；`test/harness.ts` 的 `startService({ env })` 已能把环境变量只合进服务子进程（T020 落地）。
- 基线检查：R01 的二十个门禁文件在 `1a58dd3` 上全过（站主核实）；本片的新门禁 `tests/test_gate_t021_baseline.py` 由门禁端稍后写好并做成基线提交，基线上不存在，基线应失败（G01）。
- 仓库外事实（站主 2026-10-26 实测，本合同按事实写，不做分支）：
  1. Bun 1.4.2 与 Node 24.19.0 下，**读一个还在被写的 stderr 文件不会被共享冲突拦住**（子进程的写句柄带 `FILE_SHARE_READ|FILE_SHARE_WRITE`）；唯一的异常是 stderr 文件尚未创建时读会得到 ENOENT——**实现必须容忍这一次 ENOENT：跳过这一轮，不算失败、不中止运行**。因此「kernel.ts 的轮询里读 stderr 交全文」这条方案成立，不需要改 base。
  2. Bun 1.4.2 缺省 `Bun.serve` 选项下的连接空闲超时：**带非空正文的 POST 不会被断开**（读不读正文都一样）；GET、空正文 POST、不带 Content-Length 的 POST 会被断开，实测落点 9.0–12.7 秒（8 秒是推算下限）。控制取消只等宽限 2 秒加一次轮询，远早于 9 秒，**因此不放宽空闲超时，也不在取消的处理函数里做重查**。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/kernel.ts
  - ts/packages/ui/src/jobs.ts
  - ts/packages/ui/src/jobroutes.ts
  - ts/packages/ui/src/routes.ts
  - ts/packages/ui/src/app.ts
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/README.md
- allowed_new_files:
  - ts/packages/ui/src/secretentry.ts
  - ts/packages/ui/test/secret-entry.test.ts
  - ts/packages/ui/test/secret-entry-real.test.ts
  - ts/packages/ui/test/control-routes.test.ts
  - ts/packages/ui/test/fixtures/fake-secret-kernel.mjs
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t021_*.py
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/src/kernelenv.ts
  - ts/packages/base/**
  - ts/packages/contracts/**
  - desktop/**
  - docs/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、录入路由（新增）

- 路由名 `api.secrets.entry`，方法 POST，路径正则 `^/api/v1/secrets/([^/]+)/entry$`（捕获组是凭据名；名字里不许有 `/`）。**不标 `public`**：它在 `/api/` 下，必须有会话；走 POST 的 CSRF 三查与读正文两步（`Origin` 同源、`X-Themis-UI: 1`、`content-type: application/json`）。
- 路由实现放在新文件 `ts/packages/ui/src/secretentry.ts`，导出 `secretEntryRoutes(runner: KernelRunner, jobs: JobTable, timeouts: Readonly<Record<string, number>> = {}): readonly Route[]`。
- 校验次序（前一关不过就不进下一关，**任何一关不过都不起子进程**）：
  1. 正文必须是不带键的 JSON 对象：正文不是对象 → 400「请求体必须是 JSON 对象」；是对象但带任何键 → 400「请求体含有未知键」。提示固定，不回显正文。
  2. 凭据名用 `@themis/base/secrets` 的 `allowEnvName`（`ts/packages/base/src/secrets.ts:265`，即 `ENV_NAME_RE` 且不像令牌）判断；不合格 → 400「凭据名不合法」。
  3. `runner.canAccept()` 为假 → 503「服务繁忙，请稍后重试」并带 `Retry-After: 2`；作业表满（`JobTable.create` 返回 null）→ 503「作业表已满，请稍后重试」并带 `Retry-After: 2`。这两种情形**不建作业**（与 `api.jobs.create` 一致）。
- argv 恰好是 `["config", "secret", "set", <name>, "--no-browser", "--timeout=600"]`：没有 `--verify`、没有 `--tty`；`--timeout` 的值恒为 600（页面时限），**不被测试覆盖项改写**。把它登记成导出常量 `SECRET_ENTRY_ARGV`（示例名 `EXAMPLE_KEY`：`["config","secret","set","EXAMPLE_KEY","--no-browser","--timeout=600"]`），供替身用例与真内核用例逐条对照。
- 响应（正文是普通 JSON 对象，不套七字段信封、不套 `data`）：
  - 收到核对过的握手 → **201**，正文 `{"job": <八键作业对象，state 为 running>, "url": "<地址>"}`。
  - N 秒内没有合格的握手（排队没轮到也算）→ **504**，正文 `{"job": <终态八键>, "url": null}`，作业终态 `timed_out`。
  - 握手之前子进程就结束（退出码不论、spawn-error、输出超限）→ **502**，正文 `{"job": <终态八键>, "url": null}`。
  - 服务关停中 → **503**，正文 `{"job": <终态八键 failed/closing>, "url": null}`。
  - 请求先断开（客户端断开）→ 不回响应（客户端已走），作业终态 `cancelled`。
  - `job` 一律是 `jobView` 的八键，不加第九个键。

### 二、常量与时限（`secretentry.ts` 导出）

| 常量 | 值 | 用途 |
|---|---|---|
| `SECRET_ENTRY_PAGE_SECONDS` | 600 | 传给内核的 `--timeout`（页面等待秒数） |
| `SECRET_ENTRY_MARGIN_SECONDS` | 30 | 作业时限的余量（盖住冷启动、关停 0.5 秒、写库与打结果） |
| `SECRET_ENTRY_JOB_SECONDS` | 630 | 作业时限（600 + 30） |
| `SECRET_ENTRY_HANDSHAKE_SECONDS` | 15 | 等握手的上限（从请求到达起算，排队时间算在内） |
| `SECRET_ENTRY_RECHECK_SECONDS` | 30 | 重查 `config secret check` 的时限 |

- 测试入口可覆盖两处，CLI 与环境变量碰不到：`timeouts["job.secret-entry"]` 覆盖作业时限，`timeouts["secret-entry.handshake"]` 覆盖等握手的上限。argv 里的 `--timeout=600` 不可覆盖。
- 取消的宽限是执行器既有的 2 秒（`kernel.ts` 的 `grace: 2`），本片不改。

### 三、握手：怎么读、怎么核对

- `kernel.ts` 的 `RunHooks` 加 `onStderr?: (text: string) => void`：在 `start()` 现有的轮询（`OUTPUT_POLL_MS = 100`）里调用，条件是**子进程还在跑**且 **stderr 文件比上次读到的长大**。每次把「到目前为止的全文」交给钩子，**不交路径**（临时目录的路径不出 `kernel.ts`）。
  - 读文件用 `readOutput`；**文件尚未创建（ENOENT）或读不出来时跳过这一轮**：不算失败、不中止运行、不调用钩子。站主已实测这种读法不会被共享冲突拦住。
  - 不传钩子时行为完全不变（读路由与六类作业照旧）。
- 解析（`secretentry.ts`）：
  - 只看**完整的行**（以 `\r?\n` 结尾）；逐行 `JSON.parse`，解析失败就跳过这一行。
  - 取对象里字符串类型的 `url`，用 `^http://127\.0\.0\.1:(\d{1,5})/([A-Za-z0-9_-]{32})$` **整串**匹配（两头锚定、令牌定长 32），再核端口数值在 **1–65535** 之间。
  - **第一条合格的才算握手**；不合格的行一律忽略，继续等到 N 秒或子进程结束。下列形状都要被挡住（都不回 201）：`127.0.0.1:80@别处`、带 `?` 或 `#`、多一段路径、31 或 33 个字符的令牌、`localhost`、端口 0、端口 65536、端口 `99999`。
  - 同一作业只认第一个事件（握手到达、N 到点、请求断开、子进程结束四者中最先发生的那个）：用一个「已决」标志收住，后到的都不改变结局。

### 四、地址的去向

- 地址只放在 entry 处理函数闭包里的一个**局部 Promise** 里，连同作业号回给这一次 entry 请求。
- **不挂到 `JobRecord` 或任何表上**：于是 `GET /api/v1/jobs/<id>`、`GET /api/v1/events`（SSE）、信封的 `messages`/`output`/`command`、以及访问日志（只记路由名）都拿不到它。
- 握手行之外的 stderr 照常过 `messages` 的规则：只留以 `ERROR` 或 `WARN` 开头的行，逐行过 `redactSecrets`（`jobroutes.ts` 的 `jobMessages`）。握手行以 `{` 开头，不会进 `messages`；用例另外断言 `messages` 里没有那 32 个字符。
- 落盘：stderr 文件在服务私有的临时目录里（读完删），地址在 `%TEMP%` 里待到作业结束——按用户 ACL 令牌一次性；**执行端不改管道**（base 禁改）。

### 五、等握手的上限与三种结束

- 从请求到达起最多等 `SECRET_ENTRY_HANDSHAKE_SECONDS`（15 秒），排队时间算在内。
- 到点时：作业还在排队 → 出队、不起子进程（`record.controller.abort()`，执行器把排队项出队）；已经在跑 → abort，整棵树结束，宽限 2 秒。等它落到终态之后回 **504**。
- 请求的 `signal` 先 abort（客户端断开）→ 结束作业，终态 `cancelled`，不回响应。
- 子进程先结束（退出码不论、spawn-error、output-too-large、closing）→ 按第二节的 502/503 回。

### 六、作业状态机、终态与重查

- 状态沿用 `queued → running → 终态`，每一步只走一次（`settle` 只认第一次）。「等待保存」就是 `running`，**不加新状态**（门禁 T017 钉着六种状态、五种 reason）。
- `JobRecord` 的 `kind` 放宽成 `JobKind | "secret-entry"`；`JobTable.create` 的 kind 参数同样放宽。`JOB_KINDS`、`JOB_ARGV`、`JOB_TIMEOUTS`、`JOB_ALLOW` **四张表仍是六项**（`secret-entry` 不进去）。
- `JobRecord` 加一个字段 `exited: Promise<void>`：
  - 六类作业的 `exited` 就是 `run`，行为不变。
  - 录入作业的 `exited` 在子进程结束（`runner.run` 落定）时结束；`run` 要等到重查跑完、`settle` 之后才结束。
- 重查：**只在收到合格握手的作业上做**（没握手就没人拿到过地址，不可能存进值）。
  - 命令 `config secret check <name>`，**不带 `--json`**；时限 30 秒（`SECRET_ENTRY_RECHECK_SECONDS`）。
  - 用一个**新的、只跟服务关停走的信号**（不用作业自己那个可能已经 abort 的 `record.controller.signal`）。
  - 投影用 `readroutes.ts` 的 `secretCheckData`（给它加一个 `export` 关键字，行为一个字不改），**不带 `file_dir`**。
  - 重查没跑成、退出非 0、或输出解析不了 → `check` 为 null（界面可以再读 `GET /api/v1/secrets/<name>`）。
- 终态信封：七字段齐全（`ok`、`exit_code`、`data`、`output`、`messages`、`command`、`elapsed_ms`），**`data` 一律是 `{"set": <投影或 null>, "check": <投影或 null>}`**，用 `Map` 构造（`new Map([["set", …], ["check", …]])`，键序 set、check；内层投影也是 `Map`）。

| runner 的结果 | 终态 / reason | 信封要点 |
|---|---|---|
| completed，退出 0，stdout 解析得出 JSON | `succeeded` / null | ok=true；`set` 有值；`check` 是重查的投影 |
| completed，退出非 0 | `failed` / `exit` | ok=false；exit_code 是子进程的退出码；`set` 有值（`stored` 为 false，带 `error`） |
| completed，退出 0，stdout 解析不了 | `failed` / `invalid-json` | ok=false；exit_code=0；`set` 为 null |
| interrupted（取消或客户端断开） | `cancelled` / null | ok=false；exit_code=null；`set` 为 null；`check` 照写（收到过握手才有） |
| timeout（服务一侧时限） | `timed_out` / null | `timeoutEnvelope` 的字段（ok=false、exit_code=null、一行 ERROR 的 messages），**`data` 换成 `{set: null, check}`** |
| spawn-error | `failed` / `spawn-error` | ok=false；exit_code=null；`set` 为 null；messages 一行「ERROR: 起不了内核子进程」 |
| output-too-large | `failed` / `output-too-large` | 同上，messages 一行「ERROR: 内核输出超过上限」 |
| closing（服务关停） | `failed` / `closing` | 同上，messages 一行「ERROR: 服务正在关闭」；重查跑不了，`check` 为 null |

- **`set` 的 stdout 白名单投影**：只留 `name`、`stored`、`backend`、`error` 这几个键里**实际出现**的（键序照这个顺序），**丢掉恒为 null 的 `verified`**。`error` 只可能是内核的短码（`timeout` 或 SecretError 的 code：`name`、`credential_store`、`shape`、`store_off`）。不透出 stdout 的其它内容，不过 `redactJson`（只放这几个键，值本来就不在 stdout 上）。
- **`check` 的投影**：`secretCheckData` 的结果（键 `name`、`source`、`store_mode`、`system_backend`；没有 `file_dir`），拿不到时为 null。

### 七、控制门（`Route.control`）

- `routes.ts` 的 `Route` 加 `control?: true`。
- `app.ts` 的管线改成：命中的路由 `control === true` 时，**一次过三道**（Host 是第 1 步，对所有路径都查）：
  1. **Origin**：`controlOriginAllowed(request.headers)`；不过 → 403「请求被拒绝」，**不计入令牌限速**（这一步在令牌门之前）。
  2. **控制令牌**：`state.control.check(request.headers)`；403 → 403「请求被拒绝」；429 → 429「控制令牌失败次数过多」并带 `Retry-After: <verdict.retryAfterSeconds>`（秒）。
  3. 两道都过了 → **跳过 CSRF 与读正文**（`body` 传 `undefined` 给处理函数），直接交给处理函数。
- 删掉 `app.ts` 里两处按路由名 `control.bootstrap` 的特判（Origin 那处与 CSRF/读正文那处）。
- 会话那一步不动：`/control/` 不在 `/api/` 下，本来就不验会话。
- `routes.ts` 的 `control.bootstrap`：**保留 `public: true`**（T016 门禁要求 `routes.ts` 里 `public: true` 恰好两处，落在 `bootstrap` 与 `control.bootstrap` 上），**再加 `control: true`**；它的处理函数只剩业务：`state.sessions.revokeAll()`、`state.nonces.revokeAll()`、发新的 nonce。令牌比对、429 与 `Retry-After` 全部搬进 `app.ts`。
- 新路由 `control.jobs.cancel` 加在 `jobroutes.ts` 的 `jobRoutes()` 里：`POST ^/control/jobs/([^/]+)/cancel$`，**标 `control: true`、不标 `public`**，处理函数只调 `cancelJob`（不读正文、不做 CSRF、不再调 `control.check`——门只在 `app.ts` 一处）。
- **控制路由不做空闲超时放宽**：取消的处理函数最多等宽限 2 秒加一次轮询，短于 Bun 最早实测落点 9 秒。

### 八、两条取消路由共用 `cancelJob`

- `jobroutes.ts` 导出 `cancelJob(table: JobTable, id: string): Promise<Response>`，`api.jobs.cancel` 与 `control.jobs.cancel` 都用它：
  - 作业号格式不对或不在表里 → 404「没有这个作业」。
  - 已经是终态 → 409「作业已经结束」。
  - 否则 `record.controller.abort()`（排队中出队、在跑中止信号、整棵树结束），**`await record.exited`**（子进程树结束），回 **200** 与**当时的八键作业对象**。
- 录入作业这时可能还是 `running`（重查没跑完）：终态与 `check` 要另外经 `GET /api/v1/jobs/<id>` 拿。
- 六类既有作业照旧：它们的 `exited` 就是 `run`，所以 `api.jobs.cancel` 的既有行为（等终态、回终态的八键对象）**逐字不变**。
- `api.jobs.cancel` 的正文仍然必须是 JSON 对象（否则 400「请求体必须是 JSON 对象」）；`control.jobs.cancel` 不读正文（控制路由免正文）。

### 九、兼容性与不变的

- `server.ts` 把 `secretEntryRoutes(...)` **同时并进 `extraRoutes` 与 `kernelAnsweredRoutes`**（entry 是内核应答、要等握手 N 秒的请求，必须在放宽批次里；用白盒断言守住 `server.ts` 的 `kernelAnsweredRoutes` 表达式里有 `secretEntryRoutes(`）。**不合并** `extraRoutes` 与 `kernelAnsweredRoutes` 的两份构造。
- `JOB_KINDS`/`JOB_ARGV`/`JOB_TIMEOUTS`/`JOB_ALLOW` 仍是六项；`POST /api/v1/jobs {"kind":"secret-entry"}` → 400「kind 不合法」（新用例守住）。
- 六种作业状态与五种 reason 一个不增不减；`jobView` 仍是八键。
- T015 `test_static_envelope_and_routes`、T016 `test_static_routes_public_flag`（`routes.ts` 里 `public: true` 恰好两处）、T015 `test_static_localhttp_constants`、T017 三个静态断言（六个 kind、五种 reason、六种状态；`test_static_routes_auth_19_intact` 要求 `routes-auth.test.ts` 只追加）、T019 `test_static_server_wiring`、T020 `test_static_server_timeout_relief` 与 `test_static_harness_env_option` **一条也不推翻**。
- README 只追加：录入路由与控制门两条（既有被门禁逐字钉住的句子一个字不动）。
- `routes-auth.test.ts` 只追加：entry 路由不带 cookie 回 401。

## Steps

1. **读基线**：读 `ts/packages/ui/src/kernel.ts`、`jobs.ts`、`jobroutes.ts`、`routes.ts`、`app.ts`、`server.ts`、`readroutes.ts`、`localhttp/control.ts`、`localhttp/guards.ts`、`ts/packages/ui/test/harness.ts`、`test/routes-auth.test.ts`、`test/support.ts`、两个替身 `test/fixtures/fake-kernel.mjs` 与 `fake-write-kernel.mjs`、`ts/packages/ui/README.md`，以及 `scripts/kit_config.py`、`scripts/codekit/secrets.py`、`ts/packages/base/src/secrets.ts`、`ts/packages/base/src/pyjson.ts`；确认本合同的符号与形状一致；**不一致就停下报告，不要照抄本文的行号**。
   - 意图：不按旧基线的行号改代码。验收：Repository facts 里每一项都能对上。风险：低。
2. **`kernel.ts` 的 `onStderr` 钩子**：`RunHooks` 加 `onStderr?: (text: string) => void`；在 `start()` 现有的 100 毫秒轮询里，当 stderr 文件比上次大时用 `readOutput` 读出全文交给钩子；**读不到（文件尚未创建、ENOENT）就跳过这一轮**，不算失败、不中止运行；不传钩子时行为不变。
   - 验收：`kernel-runner.test.ts` 追加一例——替身先往 stderr 写一行握手 JSON 再等门文件，钩子在**子进程退出之前**就收到那一行；不传钩子的既有用例全绿。
   - 风险：站主已实测读还在写的文件不会被共享冲突拦住（事实 1），实现只要容忍 ENOENT 即可。
3. **`jobs.ts` 放宽 kind、加 `exited`**：`JobRecord.kind` 与 `JobTable.create` 的 kind 参数放宽成 `JobKind | "secret-entry"`；`JobRecord` 加 `exited: Promise<void>`（六类作业的 `exited` 就是 `run`）；`JOB_KINDS`/`JOB_ARGV`/`JOB_TIMEOUTS`/`JOB_ALLOW` 一项不动。
   - 验收：`jobs.test.ts`、`jobs-service.test.ts` 的既有用例全绿；新用例断言四张表仍是六项、`jobView` 仍是八键。
   - 风险：`jobs.test.ts` 钉着 `JOB_ALLOW` 恰好六项，别把新 kind 并进去。
4. **`readroutes.ts`**：给 `secretCheckData` 加一个 `export` 关键字，**一个字都不改**。
   - 验收：`readroutes` 的既有用例全绿。风险：低。
5. **新文件 `src/secretentry.ts`**：按 Behavior contract 的一到六节实现路由、校验、argv、握手解析、等握手的上限、各种结局的映射、重查与信封。
   - 验收：第七节与变异表里标「替身用例」的每一条。
   - 风险：握手到达、N 到点、请求断开、子进程结束四件事可能同时发生——每个作业只认第一个事件（用一个已决标志收住）。
6. **`jobroutes.ts`**：抽出导出的 `cancelJob(table, id)`，`api.jobs.cancel` 改用它（正文校验与既有响应逐字不变）；加 `control.jobs.cancel`（`control: true`、不标 `public`、只调 `cancelJob`）。
   - 验收：`api.jobs.cancel` 的既有用例不变；控制取消的用例见第七节与变异表。
   - 风险：低。
7. **`routes.ts` 与 `app.ts`**：照 Behavior contract 第七节搬门——`Route` 加 `control?: true`；`control.bootstrap` 保留 `public: true` 再加 `control: true`，处理函数只剩业务；`app.ts` 里按 `control === true` 一次过 Origin 与令牌两道、免 CSRF、不读正文；删掉两处按路由名的特判。
   - 验收：T015/T016/T017 的控制接口黑盒全绿，包括「只带令牌、不带正文回 200」（`routes-auth.test.ts` 里既有的那一条）；新加的表驱动用例见第七节。
   - 风险：README 的「控制接口」一段若被门禁钉住，只追加、不改原句。
8. **`server.ts`**：`secretEntryRoutes(runner, jobs, timeouts)` 同时并进 `extraRoutes` 与 `kernelAnsweredRoutes`（后者是另建的一份判定用批次；两份构造照旧各自建，不合并）。
   - 验收：白盒断言 `server.ts` 的 `kernelAnsweredRoutes` 表达式里有 `secretEntryRoutes(`；T019/T020 的记号不动。风险：低。
9. **替身与替身用例**：新替身 `test/fixtures/fake-secret-kernel.mjs`（Node 跑，不改已锁的两个替身）：
   - 演 `secret set`：把一行握手 JSON 写到 **stderr**（照环境变量给的地址；默认给一个合格地址），把 pid 写进文件，等门文件或一直等，最后在 stdout 打结果 JSON（默认 `{"name":…,"stored":true,"backend":"file","verified":null}`）。
   - 演 `secret check`：可以卡在门文件上（等测试放行）。
   - 照旧记 begin/end 与退出码；**不回显握手里的令牌**（除非要测的形状反例）。
   - 新用例 `test/secret-entry.test.ts`（进程内 `createApp` + `extraRoutes: secretEntryRoutes(...)`，照 `write-routes.test.ts` 的写法）与 `test/control-routes.test.ts`。
   - 验收：第七节与变异表里标「替身用例」的每一条。
   - 风险：计时相关的用例一律用门文件卡先后，不靠睡眠时长或墙钟；pid 是否还活着用 `pidAlive` 轮询并带上限。
10. **真内核用例 `test/secret-entry-real.test.ts`**：照 `write-real.test.ts` 起真服务（`startService({ entry: "overrides", overrides: {}, python: process.execPath, kernel: <真内核>, env: { CODEKIT_SECRET_STORE: "file", XDG_CONFIG_HOME: <临时目录> } })`）：
    - 录入**之前**先经同一个服务调 `GET /api/v1/secrets/<name>`，断言 `store_mode` 是 `file`、`system_backend` 是 null；不符就失败、不录入。
    - 名字用 `THEMIS_UI_TEST_<hex>`，值用假的；测试自己当浏览器 POST `value=<假值>` 到一次性页面。
    - 结束后断言临时 XDG 目录下有文件，且重查的 `source` 是 `file`、作业终态 `succeeded`、`set.backend` 是 `file`。
    - **绝不写进本机真正的凭据库**：环境变量只经 harness 的 `startService({ env })` 传给服务子进程，不改 vitest 进程的 `process.env`。
    - 验收：上面三条断言全过。
    - 风险：中（真内核会写文件），必须用临时 `XDG_CONFIG_HOME`。
11. **`routes-auth.test.ts` 只追加**：entry 路由不带 cookie 回 401（既有的 19 条表与断言一字不动）。
    - 验收：T017 门禁 `test_static_routes_auth_19_intact` 仍过。风险：低。
12. **README 只追加**：加凭据录入路由与控制门两条（照既有小节的写法；被门禁钉住的句子不动）。
    - 验收：README 的既有关键词仍在。风险：低。
13. **跑检查并写报告**：跑 Setup 与 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t021_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`

## Definition of done

- D01：录入路由可用——`POST /api/v1/secrets/<name>/entry` 走完校验、起作业、读握手、回 201 与 `{"job": …, "url": …}`；名字不合格、正文带键、正文不是对象都回 400 且不起子进程；执行器收不了或作业表满回 503 且带 `Retry-After: 2`；证据：V01（`secret-entry.test.ts`）、G01；目的：接口的形状与错误语义是这一片对外的契约。
- D02：argv 恰好是 `["config","secret","set",<name>,"--no-browser","--timeout=600"]`（无 `--verify`、无 `--tty`，`--timeout` 恒 600）；证据：V01（替身记下 argv 逐字比对）、V01（真内核用例证明内核解析器接受这组参数）；目的：多一个 `--verify` 就会花钱，少一个 `--no-browser` 就会弹浏览器。
- D03：握手严格核对——只有整串匹配 `^http://127\.0\.0\.1:(\d{1,5})/([A-Za-z0-9_-]{32})$` 且端口在 1–65535 的地址才算握手；计划列出的反例（`@别处`、`?`/`#`、多一段路径、31/33 个字符、`localhost`、端口 0、端口 65536、端口 99999）都不回 201；证据：V01；目的：地址形状写死是这一片唯一的防注入手段。
- D04：地址只活在这一次请求的局部变量里——`GET /api/v1/jobs/<id>` 的正文、SSE 的一条、作业的 `messages` 与 `command`、`app.accessLog.entries()` 里都找不到那 32 个字符；证据：V01；目的：令牌进了作业记录就等于凭据外泄。
- D05：等握手有上限——15 秒（可被 `timeouts["secret-entry.handshake"]` 覆盖）内没有合格握手就回 504，作业 `timed_out`，子进程已经不在（pid 不在）；排队没轮到时同样 504 且子进程从没起来；请求先断开时作业 `cancelled`、pid 不在；证据：V01；目的：不能让子进程占着名额等满时限。
- D06：终态与重查——各终态的 reason 映射照 Behavior contract 第六节；`data` 一律 `{set, check}`；`set` 是白名单投影（只有实际出现的 `name`/`stored`/`backend`/`error`，没有 `verified`，恰好三个键）；`check` 是 `secretCheckData` 的投影（没有 `file_dir`）；收到过握手的作业在取消与超时之后 `check` 仍不为 null；没收到过握手的作业不重查；证据：V01；目的：界面以重查为准，取消与超时也要能读回结果。
- D07：`secret-entry` 不在 `POST /api/v1/jobs` 的名单里——`{"kind":"secret-entry"}` 回 400「kind 不合法」，四张表仍是六项；证据：V01、G01；目的：否则能绕过 entry 起一个谁也拿不到地址的页面。
- D08：entry 在空闲超时的放宽批次里——`server.ts` 的 `kernelAnsweredRoutes` 表达式里有 `secretEntryRoutes(`；证据：V01（白盒断言）、G01；目的：放宽批次漏了它，慢请求会被 Bun 掐断。
- D09：控制门统一——`Route.control` 是唯一的判断依据：表里所有 `control === true` 的路由（`control.bootstrap` 与 `control.jobs.cancel`）逐条断言令牌错 403、只带 cookie 403、外来 Origin 403，处理函数都没跑；5 次令牌错之后第 6 次 429 带 `Retry-After`；外来 Origin 的失败不计入限速；控制路由免 CSRF、不读正文（只带令牌、不带正文回 200）；`/control/` 开头的路由都是 control、control 路由都在 `/control/` 下；用 extraRoutes 注入的 control 探针路由同样走三道；证据：V01（`control-routes.test.ts`）；目的：门只对路由名特判时，后来加的控制路由会绕过令牌。
- D10：两条取消路由共用 `cancelJob`——不存在 404、已终态 409、正常 200 回当时的八键作业对象；`control.jobs.cancel` 不读正文；控制取消不等重查（`secret check` 卡在门文件上时，先拿到取消响应 200、作业仍是 running，再放行后终态 `cancelled` 且 `check` 不为 null）；证据：V01；目的：外壳在凭据小窗口关掉时要立刻拿到回执。
- D11：控制取消之后子进程已经结束（pid 不在），服务一侧超时的作业 `timed_out` 且 `check` 不为 null；证据：V01；目的：取消不杀干净就会占着名额。
- D12：真内核链路成立——`CODEKIT_SECRET_STORE=file` 与临时 `XDG_CONFIG_HOME` 经 `startService({ env })` 传进内核；录入前断言 `store_mode` 是 `file`、`system_backend` 是 null；保存之后作业 `succeeded`、`check.source` 是 `file`、临时 XDG 目录下有文件；本机真正的凭据库里没有多出东西；证据：V01（`secret-entry-real.test.ts`）；目的：这一片绝不能写进本机真的凭据库。
- D13：既有断言一条不推翻——T015/T016/T017/T019/T020 的门禁全过；`routes.ts` 里 `public: true` 恰好两处；六个 kind、五种 reason、六种状态不变；`routes-auth.test.ts` 只追加；README 只追加；证据：R01、G01、review；目的：本片只许加，不许借机改别人的口径。
- D14：规划 §7 的变异清单两表（录入 14 条、控制门 7 条）每条都有能杀它的用例（下表逐条列出）；证据：V01、review；目的：过了检查不等于目标——用例没断言到点就等于没测。
- D15：所有修改都在允许集合内（新增文件在 `allowed_new_files`，没有删文件，依赖与锁文件没动）；证据：scope。
- D16：没有删除、跳过或弱化既有测试（`routes-auth.test.ts` 只追加；不许出现 skip/only/todo）；证据：review、R01。

D14 的变异与用例对照（每条都要有用例）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | argv 加上 `--verify` | 替身用例：argv 逐字等于 `SECRET_ENTRY_ARGV`；真内核用例（内核解析器接受这组参数） |
| M2 | argv 去掉 `--no-browser` | 同上（argv 逐字比对，替身断言收到了 `--no-browser`） |
| M3 | 握手正则只核前缀，或去掉 `$`、去掉定长 | 握手反例（`?`/`#`、多一段路径、31/33 个字符、`@别处`）都不回 201 |
| M4 | 不核端口范围 | 端口 0 与端口 65536、端口 99999 三个反例 |
| M5 | 地址挂到 `JobRecord` 上，或并进 `jobView` | 作业查询、SSE、`messages`、`command`、访问日志五处都搜不到那 32 个字符 |
| M6 | `messages` 改成收 stderr 的所有行 | `messages` 里没有那 32 个字符 |
| M7 | 访问日志记录路径 | 访问日志里没有那 32 个字符 |
| M8 | `set` 不做白名单投影（透出 `verified` 或塞进 stderr 的内容） | `set` 恰好三个键（`name`/`stored`/`backend`），没有 `verified` |
| M9 | 等握手不设上限 | 504 那条在用例时限内不回就失败 |
| M10 | 超时之后不结束子进程（去掉 abort） | 504 之后 pid 不在 |
| M11 | 取消或超时之后不重查 | 取消/超时之后 `check` 不为 null |
| M12 | 重查用作业已经 abort 的那个信号 | 取消之后 `check` 仍不为 null（被抓住） |
| M13 | 录入 kind 并进 `JOB_KINDS` | `POST /api/v1/jobs {"kind":"secret-entry"}` → 400「kind 不合法」 |
| M14 | entry 从 `kernelAnsweredRoutes` 里拿掉 | 白盒断言 `server.ts` 的 `kernelAnsweredRoutes` 表达式里有 `secretEntryRoutes(` |
| M15 | 取消的处理函数改成 `await record.run`（等重查） | 门文件那条：取消响应必须在放行之前到（先 200、作业仍 running） |
| M16 | 只带 cookie 也能过控制门 | 表驱动的 403 |
| M17 | 令牌错也能过控制门 | 表驱动的 403 |
| M18 | 去掉限速（不走 `ControlGate` 的锁定） | 第 6 次 429 带 `Retry-After` |
| M19 | 去掉 `controlOriginAllowed` | 外来 Origin 回 403 |
| M20 | 取消之后子进程还活着 | 取消之后 pid 不在 |
| M21 | 门只对路由名 `control.bootstrap` 生效，或某条 control 路由跳过令牌这一道 | 表驱动 + extraRoutes 注入的 control 探针路由 |
| M22 | control 路由也读正文、做 CSRF | `control.bootstrap` 只带令牌、不带正文回 200；`control.jobs.cancel` 不带正文可用 |

目标与用例的对照：

| 目标 | 替身用例（`secret-entry.test.ts` / `control-routes.test.ts`） | 真内核用例（`secret-entry-real.test.ts`） |
|---|---|---|
| 录入路由、校验、argv | argv 逐字比对；名字不合格与正文带键的 400（不起子进程）；`kind` 不合法的 400 | 内核解析器接受这组 argv |
| 握手与地址 | 握手正例（201）与全部反例；四处的令牌搜不到 | 真实的一次性页面地址 |
| 等握手的上限 | 504（不打握手行）、排队占位时的 504、请求断开的 cancelled | — |
| 终态与重查 | 保存成功（`set` 三个键、`check` 有值）；握手前退出 1 → 502 与 `messages`；取消不等重查；服务一侧超时 | 保存之后 `succeeded`、`check.source` 是 `file` |
| 控制门与取消 | 全表逐条 403/429、外来 Origin 不计限速、探针路由、取消 404/409/200、pid 不在 | — |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `kernel.ts` 的 `RunHooks` 不是只有 `onStart`、`readroutes.ts` 的 `secretCheckData` 形状变了、`app.ts` 的管线次序不是四步）。
- 必须修改允许范围之外的文件才能继续（例如要动 `localhttp/**`、`kernelenv.ts`、`base/**`、内核 Python 或 `docs/**`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如必须让 entry 在 `/api/` 之外才能免 CSRF）。
- 真内核的行为与合同写的不一致（例如 `config secret set` 不接受 `--timeout=600` 或 `--no-browser`），且改动要越过允许范围。
- 读一个还在被写的 stderr 文件在真机上被共享冲突拦住（站主已实测不成立；若真机上出现），停下报告，**不要**擅自改 base。
- 达到单轮时限（本版单轮 3600 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（至少 2 倍单次时限，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 10 分钟；实现（kernel 钩子、jobs、secretentry、jobroutes、routes/app、server）25 分钟；替身与三个用例文件 20 分钟；README 与 routes-auth 追加 3 分钟；必要检查（V01–V03 与 R01）10 分钟；最终报告 2 分钟；总计 70 分钟，不超过单轮时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D16，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。
- 报告里要写清：22 条变异各自由哪条用例杀掉、握手反例逐条的返回码、四处（作业查询、SSE、messages、访问日志）搜不到令牌的断言结果、真内核用例的 `store_mode`/`system_backend`/`check.source` 三个断言、控制门表驱动逐条的结果。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（`routes-auth.test.ts` 只追加）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `localhttp/**`、`kernelenv.ts`、`base/**`、`docs/**`、`scripts/**` 与内核 Python；不改 `JOB_KINDS`/`JOB_ARGV`/`JOB_TIMEOUTS`/`JOB_ALLOW` 四张表；不增删作业状态与失败原因。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261026T040101945076Z-owner-2528ff：

> 摘要: 规划端（本会话）代定，站主代理：两条仓库外事实都已实测核实，成立；第 2 条的区间按实测补了精度，不影响设计。合同端可以开工。
> 提交: 无
> 验证: 事实 1 成立：探针用仓库的 runSupervised（base/src/supervise.ts）起 python 子进程，先往 stderr 写一行握手 JSON 并 flush、睡 3 秒、再写第二行、再睡 2 秒；子进程存活期间本进程每 100 毫秒 readFileSync 一次 stderr 文件。Bun 1.4.2 下两次：握手行在第 121、109 毫秒读到，第二行在第 3088、3078 毫秒读到，子进程约 5.05 秒退出；Node 24.19.0 下（Windows 上经 Bun 辅助进程监督，句柄同样由 CreateFileW 以 FILE_SHARE_READ|FILE_SHARE_WRITE 打开）：第 112、3165 毫秒读到。除了第一次轮询时文件还没建好报过一次 ENOENT，没有任何共享冲突（EBUSY、EPERM）。事实 2 成立：Bun 1.4.2、缺省 Bun.serve 选项、不调 timeout、处理函数睡 15 秒，带非空正文的 POST（读不读正文都一样）15 秒完整拿到 200、request.signal 不 abort；GET（带不带正文）、正文长度 0 的 POST、不带长度头的 POST 都被断开，规划端两次实测分别在 12.5、12.7 秒 abort，themistally-15 一次在 12.0 秒，2026-10-25 规划端对 GET 两次实测在 9 秒与 12 秒。
> 偏离: 事实 2 的区间写的是“第 8 到 12 秒之间”，实测落点是 9.0 到 12.7 秒：12 秒之后的零点几秒是事件循环的延迟；8 秒是 uSockets 4 秒一档推出来的下限，没有实测到 9 秒以下。控制取消只等宽限 2 秒加一次轮询，离最早的实测落点（9 秒）与推算下限（8 秒）都有余量，设计不用改。
> 需协调人决定: 无
> 证据: 探针在规划端会话的 scratchpad：stderr-probe/probe.ts（事实 1，bun 与 node 各跑过）；bun-idle/servepost.ts 与 post.log、post2.log（事实 2）；themistally-15 的探针 bun-idle/probe.ts（它的会话 scratchpad）。
