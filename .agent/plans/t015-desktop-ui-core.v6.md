# TASK: t015-desktop-ui-core

## Identity
- plan_version: 6
- repository: ThemisTally
- base_sha: ad113e1b8193fbc5e3c74e0b6c89ec3dfb4672e0
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在 `ts/packages/ui` 里实现桌面端本机服务的第 1 片（服务骨架、安全基线、握手）：一个只绑 127.0.0.1 的 Bun 服务，stdout 只写一行握手 JSON；提供一次性引导地址与会话 cookie、控制接口（恒定时间比较加失败限速）、Host/Origin/CSRF 校验、安全响应头、64 KiB 请求体上限、静态资源的目录边界（路径只解码一次）、每仓库一个的锁目录，以及空闲超时与 stdin EOF 的关停。这些行为全部由 `ts/packages/ui/test` 下的 Vitest 用例钉住。

## Non-goals
- 不实现数据路由（`/api/v1/meta`、`status`、`jobs`、SSE 等）、不做子进程与二道脱敏（第 2、3 片的事）
- 不改 `desktop/**`、`tests/**`、`scripts/**`、`.gitignore`、`gitignore.append.txt`（忽略规则已由站主在基线 2a5c7213da 落地）
- 不改 `ts/packages/ui/package.json`、`ts/package.json`、`ts/bun.lock`、`ts/tsconfig.json`、`ts/vitest.config.ts`，不新增依赖
- 不改 `ts/packages/base/**`（`localhttp` 搬到 `@themis/base/localhttp` 是规划端在迁移第 ③d 步做的）
- 不写 `ts/mutations/ui-localhttp.ts.json` 与 `ts/mutations/ui-static.ts.json`（禁区；清单由门禁端写，合同里已写清条目与必须红的用例）
- 不改 `ts/packages/cli/**`、`ts/packages/contracts/**`（内核禁区）
- 不改 `ts/packages/ui/test/args.test.ts`（既有用例只读、不删不跳过）
- 前端 `desktop/web` 不在本片（接本机服务是另一片）

## Repository facts
基线 `2a5c7213da29413d9e80f3d47bcc3875663b1b34` 上的实际内容（行号已按该基线核对）。

- 入口：`ts/packages/ui/src/main.ts` 的 `runUi(args, io)`；`UiArgs`（`idle_timeout` 是 `number | bigint | null`）、`UiIo`、`EXIT_OK`/`EXIT_ERROR`/`EXIT_USAGE`、`checkArgs` 都在这个文件里。`ts/packages/cli/src/main.ts` 的 `case "ui"` 动态 `import("@themis/ui/main")` 之后 `await runUi(args)`；`ts/packages/ui/package.json` 的 `exports` 只有 `"./main"`（本片不改它，新模块之间用仓库内相对路径引入）。
- 调用关系与现有约定：
  - 进程靠事件循环排空才退出：`runUi` 返回之后必须把 server、计时器与 stdin 全部收掉，否则进程不退出。
  - `pyargs-v1` 的整数经 `@themis/base/pyjson` 变成 bigint，`idle_timeout` 可能是很大的 bigint（换算时封顶 `Number.MAX_SAFE_INTEGER`）。
  - 启动器 `scripts/pi_dispatch.py` 的 `ts_launch_command` 固定带 `--no-env-file --config=<ts>/bunfig.toml`；`run_handoff` 原样继承 stdin、stdout、stderr 句柄。
  - 源码卫生（`ts/packages/contracts/test/source-hygiene.test.ts` 的 `localhttpViolations`）跑的是**全文**正则：`localhttp/**` 只许导入 `node:*`、`@themis/base/*` 与 localhttp 内部的相对路径；import/require 的正则同样会匹配注释；`Bun` 后面紧跟 `.` 的字样写在注释里也判违规。所以 `src/localhttp/**` 的注释里不得出现这类字样，也不要写形似 import 语句的注释。
  - `ts/` 里没有 Bun 的类型声明：取本地接口用 `const bun = (globalThis as unknown as { Bun?: BunLike }).Bun`，`BunLike` 只声明用到的那几样，不加全局声明、不加依赖。
  - `@types/node` 声明了全局的 `Request`、`Response`、`Headers`，localhttp 按 WHATWG 写法就能过 `tsc`。
  - Vitest 跑在 Node 下（`ts/vitest.config.ts`：`include: packages/*/test/**/*.test.ts`、`testTimeout: 60_000`、按文件并行），所以 localhttp 的纯函数测试在 Node 下跑，正好证明它们不依赖 Bun。
  - `ts/tsconfig.json` 开了 `strict`、`noUncheckedIndexedAccess`、`exactOptionalPropertyTypes`、`erasableSyntaxOnly`、`verbatimModuleSyntax`、`allowImportingTsExtensions`、`noEmit`。
  - `pidAlive` 返回 true、false 或 null（`@themis/base/process`）；`fileAttributes` 在没有绑定时返回 null，调用方退回 `lstat`（`@themis/base/native`），绑定靠程序开头调一次 `initFileAttributes`（`ts/packages/cli/src/main.ts` 已调）。`@themis/base/fsutil` 有 `writeTextAtomic`。
  - 前端是 hash 路由（`desktop/web/src/shell/router.ts`），Vite `base: './'`；找不到的路径回 404，不回退到 index.html。
- 工具链与锁文件：Bun 1.4.2（`ts/package.json` 的 `packageManager: bun@1.4.2`；站主已实测 `bun --version` 是 1.4.2）；Node 24；`ts/bun.lock` 提交、`ts/node_modules` 不提交；装好戳记在 `ts/node_modules/.themis-installed`（含 `bun_path`、`bun_version`、`deps_sha256`，由 `ts/tools/stamp-install.mjs` 写）。测试起 Bun 进程时从戳记取可执行文件路径，取不到再退回 PATH 上的 `bun`。
- 基线检查：站主已在 2a5c7213da 上核实 Bun 与 Node 的行为（见下节）。本片执行前须确认：`ts/packages/ui/src` 只有 `main.ts`、`ts/packages/ui/test` 只有 `args.test.ts`、`ts/packages/ui/src/localhttp` 不存在、根 `.gitignore` 末行是 `.agent/.ui.lock/`、`ts/node_modules/.themis-installed` 里有 `bun_path`。不符即停并报告。

仓库外事实（站主 2026-10-23 实测，落在 `.agent/design/t015-事实核实.md`；合同按这些已定案的做法写）：

- F1：Bun 是 1.4.2。
- F2：交给 fetch 的 `req.url` 是**规范化过**的：`..` 与 `%2e%2e` 已被解析掉，反斜杠换成 `/`，只有 `%2f` 保留编码。所以 HTTP 层的负面测试只断言「拿不到 `--assets` 之外的文件」，不断言「服务看到了原始 `..` 并拒绝」；原始形式的拒绝由路径解析的纯函数负责、逐类覆盖。
- F3：Bun 自己拒掉三类请求且都不带安全头——Content-Length 超过 `maxRequestBodySize` 时 Bun 自回 413（不调 fetch）；畸形请求行时 Bun 自回 400（不调 fetch）；分块传输且正文超 Bun 上限时 fetch 被调用，但 Bun 自回 413，处理函数给出的响应发不出去。所以服务自己的计数（64 KiB 加 1 就停）必须先于 Bun 的上限触发，`maxRequestBodySize` 设 131072（2 倍）。
- F4：`server.stop(true)` 3 毫秒内收掉保活连接；同一个 Bun 进程里的 `node:net` 客户端收不到 close 事件，所以测试客户端放在 Node 一侧（Vitest 本来就跑在 Node 上），服务在单独的 Bun 进程里。
- F5：Bun 会自动加 Date 头；HEAD 会交给 fetch。测试不依赖 Date；HEAD 与其余方法一律回 405 并带安全头（站主决定）。
- F6：Bun 1.4.2 下 `process.stdin` 是管道时，写端一关 `for await` 就结束（读到 EOF）；经一层 Python 起（`run_handoff` 原样继承 stdin）同样成立。
- F7：每条连接的空闲超时实测约 10 秒（Bun 文档默认 10 秒，可用 `idleTimeout` 设，上限 255）；与服务的空闲退出（1800 秒）无关。本片不设 `idleTimeout`，显式设置留给第 3 片的 SSE。
- F8：Node 24 与 Bun 1.4.2 下 `lstat` 一个 junction 都是 `isSymbolicLink()` 为 true、`isDirectory()` 为 false；`readdir` 的 withFileTypes 条目 `isSymbolicLink()` 也是 true。
- F9：Electron 主进程发请求带不带 Origin 未核实；本片不依赖，照 `controlOriginAllowed`（没有 Origin 或同源都接受；别的站点 403 且不计入限速）两种情况都成立。
- 另外三条已核实：`node:http` 客户端能自定义 Host 头；Vitest 2.1.8 的 `vi.mock` 能包住 `node:crypto`（具名导入被换掉、调用次数可断言）；`fs.symlinkSync(target, path, "junction")` 在 Windows 上不需要管理员权限。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/**
  - ts/packages/ui/README.md
  - ts/packages/ui/test/app.test.ts
  - ts/packages/ui/test/fixtures/serve-entry.ts
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/launcher.e2e.test.ts
  - ts/packages/ui/test/lifecycle.test.ts
  - ts/packages/ui/test/localhttp-accesslog.test.ts
  - ts/packages/ui/test/localhttp-body.test.ts
  - ts/packages/ui/test/localhttp-control.test.ts
  - ts/packages/ui/test/localhttp-guards.test.ts
  - ts/packages/ui/test/localhttp-headers.test.ts
  - ts/packages/ui/test/localhttp-session.test.ts
  - ts/packages/ui/test/lockdir.test.ts
  - ts/packages/ui/test/service.test.ts
  - ts/packages/ui/test/static-paths.test.ts
  - ts/packages/ui/test/fixtures/resolve-asset.ts
- allowed_new_files:
  - ts/packages/ui/src/**
  - ts/packages/ui/test/**
- allowed_deleted_files: 无
- forbidden_paths:
  - ts/packages/ui/package.json
  - ts/packages/ui/test/args.test.ts
  - ts/packages/base/**
  - ts/packages/cli/**
  - ts/packages/contracts/**
  - ts/mutations/**
  - ts/package.json
  - ts/bun.lock
  - ts/tsconfig.json
  - ts/vitest.config.ts
  - desktop/**
  - tests/**
  - tests/test_gate_t015_*.py
  - scripts/**
  - .gitignore
  - gitignore.append.txt
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - 常量（`src/localhttp/`）：`NONCE_TTL_MS = 60000`、`TOKEN_BYTES = 32`（base64url 编码后 43 个字符）、`SESSION_COOKIE = "themis_session"`、`CONTROL_HEADER = "x-themis-control"`、`CONTROL_MAX_FAILURES = 5`、`CONTROL_LOCK_BASE_MS = 1000`、`CONTROL_LOCK_MAX_MS = 60000`、`MAX_BODY_BYTES = 65536`、`ACCESS_LOG_MAX = 1000`。
  - CSP 逐字：`default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`。
  - `src/localhttp/tokens.ts`：`randomToken(): string` 用 `randomBytes(32).toString("base64url")`；`constantTimeEqual(given: string | null, expected: string): boolean` 总是先算 `timingSafeEqual(sha256(given ?? ""), sha256(expected))`（两份 32 字节摘要），再与 `given !== null` 相与；长度不同、缺头都不抛错，走同一条路。
  - `src/localhttp/session.ts`：`BootstrapNonces(now = Date.now, ttlMs = NONCE_TTL_MS)` 的 `issue(): string` 发一个新 nonce；`consume(nonce): boolean` 先查并无条件删掉，再判断 `now() - issuedAt < ttlMs`（59999 毫秒可用，60000 毫秒拒绝）；`revokeAll(): void` 清空；issue 与 consume 时顺带清理过期项。`Sessions` 的 `create(): string`、`valid(token: string | null): boolean`（null 与空串为 false）、`revokeAll(): void`。
  - `bootstrapAccepted(token): Response`：302，`Location: /`，`Set-Cookie` 逐字是 `themis_session=<令牌>; HttpOnly; SameSite=Strict; Path=/`（不带 Max-Age、不带 Secure）。`bootstrapRejected(): Response`：404，`text/plain; charset=utf-8`，正文固定为「引导地址无效」加换行；过期、用过、不存在都返回**同一个**响应。
  - `src/localhttp/cookie.ts`：`sessionSetCookie(token): string` 逐字上面那串；`readSessionCookie(headers: Headers): string | null` 只在 Cookie 头里恰好有一个 `themis_session` 时返回它的值，没有或重复都返回 null。
  - `src/localhttp/control.ts`：`ControlGate(token: string, now = Date.now)` 的 `check(headers: Headers)` 返回 `{ ok: true }`、`{ ok: false, status: 403 }` 或 `{ ok: false, status: 429, retryAfterSeconds }`。规则：锁定期内直接 429（不比较、不计数）；否则只用 `constantTimeEqual` 比较 `X-Themis-Control` 头（从不看 cookie）；失败时计数加 1，第 5 次起锁定 `min(1000 * 2^(n-5), 60000)` 毫秒，这一次本身仍回 403；成功则计数清零。
  - `src/localhttp/guards.ts`：`methodAllowed(method): boolean` 只认 GET 与 POST；`hostAllowed(headers, port): boolean` 要求 Host 整串（ASCII 小写之后）等于 `127.0.0.1:<port>` 或 `localhost:<port>`，缺 Host、缺端口、端口不对、`localhost.` 末尾带点、`[::1]` 都不认；`originAllowed(headers): boolean` 要求 Origin 等于 `http://` 加上已经过校验的 Host，缺 Origin、值为 `null`、端口不同都不认；`csrfCheck(request: Request)` 的次序是——Origin 不对 403，`X-Themis-UI` 不是 1 则 403，Content-Type 的媒体类型（取分号之前、去空白、转小写）不是 application/json 则 415；`controlOriginAllowed(headers): boolean` 在没有 Origin 或同源时通过，有但是别的站点时 403（不计入限速）。
  - `src/localhttp/headers.ts`：`withSecurityHeaders(response, { noStore })` 新建一个 Response（正文仍用原来的流，不缓冲，第 3 片的 SSE 要用），设 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`，noStore 时再设 `Cache-Control: no-store`，并删掉所有 `Access-Control-*` 头（不开 CORS）。
  - `src/localhttp/body.ts`：`readBodyLimited(request, limit = MAX_BODY_BYTES)` 返回 `{ ok: true, bytes }` 或 `{ ok: false, status: 413 }`——Content-Length 声明超过上限时直接 413 且一个字节也不读；否则边读流边数，累计超过上限（第 65537 个字节）就 `reader.cancel()` 再回 413。`readJsonBody(request, limit?)` 返回 `{ ok: true, value }` 或 `{ ok: false, status: 400 | 413 }`——空正文、坏的 UTF-8（TextDecoder 的 fatal 模式）、JSON 解析失败都是 400，不回显原值。
  - `src/localhttp/accesslog.ts`：`AccessLog(max = 1000)` 的 `record(route, status, ms)` 与 `entries()`；每条只有 `{ route, status, ms }` 三项，只存在内存里；route 不符合 `^[a-z][a-z0-9.-]*$` 时一律记成 `invalid-route-name`（这样含 nonce 的引导地址进不了记录）。
  - `src/envelope.ts`：信封七个字段，次序是 `ok`、`exit_code`、`data`、`output`、`messages`、`command`、`elapsed_ms`。服务自己产生的错误：ok 为 false、exit_code 为 null、data 为 null、output 与 command 是空数组，messages 只有一行固定的 `ERROR: …` 文字。
  - `src/routes.ts`：本片只登记四条路由。
    - `bootstrap`：GET `/bootstrap/<nonce>`，模式 `^/bootstrap/([A-Za-z0-9_-]{1,128})$`，只验 Host；消耗 nonce、建会话，302 到 `/` 并带 Set-Cookie；失败回 `bootstrapRejected()`。
    - `control.bootstrap`：POST `/control/bootstrap`，要 Host、`controlOriginAllowed`、`ControlGate`，不读正文；sessions 与 nonces 全部 `revokeAll`，再发一个新 nonce；200 信封，data 为 `{ bootstrap: <新地址> }`。
    - `api.ping.get`：GET `/api/v1/ping`，要会话；200 信封，data 为 `{ posts: <计数> }`。
    - `api.ping.post`：POST `/api/v1/ping`，要会话、CSRF、JSON 正文不超过 64 KiB 且正文必须是 JSON 对象（否则 400，不回显）；计数加 1；200 信封，data 为 `{ posts: <计数> }`。
    - 计数只在内存里，用来证明 CSRF 被拒时处理函数没有运行。
  - `src/app.ts`：`createApp(options)` 的 options 是 `port`、`assets`、`controlToken`、`now?`、`nonceTtlMs?`、`extraRoutes?`（第 2 片的接缝）、`onActivity?`；返回 `{ fetch(request: Request): Promise<Response>, issueBootstrap(): string, accessLog, inflight(): number }`。管线次序固定：
    1. Host 不对 → 403（对所有路径，包括静态、引导、控制）；
    2. 方法不是 GET 或 POST → 405，带 `Allow: GET, POST`；
    3. 路径以 `/api/` 开头 → 先验会话，没有会话一律 401（不存在的路径也是 401，免得被探测）；有会话但找不到路由 → 404；
    4. POST → `csrfCheck`（403、403、415），再 `readJsonBody`（413、400）；
    5. 交给处理函数；
    6. `withSecurityHeaders`：API、引导、控制与所有错误都带 noStore；静态资源改带 `Cache-Control: no-cache`；
    7. `accessLog.record(路由名, 状态, 耗时)`。
    - 处理函数抛错 → 500 信封；stderr 只写「处理请求时出错（<路由名>）：<错误类名>」，不写 message（message 里可能有路径或头的值）。
    - 静态资源不验会话，只验 Host：前端是公开的构建产物；D4 只规定 API 要 cookie；会话失效之后页面得先能加载出来，才能走 host.reauth()。
  - `src/server.ts`（唯一出现 Bun.serve 的文件）：`serveUi(args: UiArgs, io: UiIo, overrides?: { nonceTtlMs?: number }): Promise<number>`，overrides 只有测试入口会传，CLI 与环境变量都碰不到它。步骤：
    1. 取锁；被占就在 stderr 报告并返回 1。
    2. 生成控制令牌，`createApp`。
    3. `bun.serve({ hostname: "127.0.0.1", port: 0, maxRequestBodySize: 131072, development: false, fetch: (req) => app.fetch(req), error: () => 500 信封 })`；131072 是 64 KiB 的两倍，作为第二道防线，让服务自己的计数先起作用；起不来就释放锁、写 ERROR、返回 1。
    4. owner.json 写入 pid 与端口，再读回来核对令牌；不一致就是锁被抢走：停服务、返回 1。
    5. 写握手行：一行 JSON 加换行，字段次序 `themis_ui`、`bootstrap`、`origin`、`control`、`pid`（`bootstrap` 是 `http://127.0.0.1:<port>/bootstrap/<nonce>`，`origin` 是 `http://127.0.0.1:<port>`）；之后不再碰 stdout。
    6. 启动生命周期（stdin、空闲计时、信号），等关停。
    7. 关停：`server.stop(true)`、清计时器、停 stdin、释放锁，返回 0；另设一个 unref 的看门狗，3 秒后进程还在就 `process.exit(code)`。
    - 拿不到 Bun 时写「ERROR: 本机服务只能在 Bun 下运行」，返回 1。
  - `src/lockdir.ts`：`acquireUiLock(repo, { pid, pidAlive, now })` 返回 `{ lock }` 或 `{ busy: { pid, port | null, why } }`。先 `mkdir <repo>/.agent`（递归），再非递归 mkdir `.agent/.ui.lock`，靠它的原子性拿锁；拿到之后由 server 写 owner.json（pid、port、token、at，用 `writeTextAtomic`）。锁已存在（EEXIST）时按 owner.json 判断：pidAlive 为 true 则 busy；为 null 也 busy（判断不了就不接管）；为 false 则删掉重建，最多试 3 次；owner.json 缺失或读不出而锁目录建立不到 10 秒则 busy（对方正在启动），超过 10 秒则接管。`lock.writeOwner(port)`；`lock.release()` 只在 owner.json 的令牌是自己的时才删。
    - 被占时的提示原文（stderr，退出 1）：「ERROR: 本仓库已有本机服务在运行（pid N，端口 P）」、「ERROR: 本仓库已有本机服务正在启动（.agent/.ui.lock）」、「ERROR: 无法确认 .agent/.ui.lock 的持有者（pid N）是否还在运行」。
  - `src/lifecycle.ts`：`idleMs(idle_timeout: number | bigint | null): number`——null 为 1800 秒，其余按 `Number(x) * 1000` 换算并封顶 `Number.MAX_SAFE_INTEGER`；`IdleTimer` 的 `touch()`、`hold()`、`release()`（有进行中的请求时不算空闲），用 setTimeout 反复重设，每段不超过 2^31-1 毫秒，否则 Node 与 Bun 会立刻触发；`watchStdinEof(stream, onEof)` 用 `for await` 把 stdin 读空并丢弃数据，循环结束（EOF）或读出错都调一次 onEof，不轮询 ppid；信号 SIGINT、SIGTERM（Windows 另加 SIGBREAK）都走同一个关停并退出 0（测试不发控制台信号）。

- 边界输入：
  - 静态资源路径（`src/static.ts`）——**只解码一次**，顺序固定：
    1. 原始 pathname 里含 `%2f`、`%5c`、`%2e`、`%00`（不分大小写）就拒绝：前三个 reason 是 `encoded-dot-or-separator`，`%00` 的 reason 是 `control-char`；一律 400。
    2. 之后**只解码一次**：逐段 `decodeURIComponent`，抛 URIError 时 400，reason 是 `bad-encoding`。
    3. 解码后再交给 T13 的边界规则（下面第 4 步起），**不得再解第二次**：`%252e%252e` 解码一次是字面的 `%2e%2e`，纯函数不能再解第二次，当成一个不存在的文件名处理，回 404 `not-found`。
    4. 解码后的段检查，每类一行，reason 各不相同：含反斜杠 → 400 `backslash`；含控制字符（含 NUL）→ 400 `control-char`；空段（含 `//server/share` 这种 UNC 写法）→ 400 `empty-segment`；段是 `.` 或 `..` → 400 `dot-segment`；第一段形如盘符（字母加冒号）→ 400 `drive-letter`；任何段含冒号（ADS）→ 400 `colon`；段末尾是点或空格 → 400 `trailing-dot-or-space`。
    5. 拼成路径之后 `isWithin(root, full)` 为假 → 403 `outside-root`。
    6. 从 root 往下逐级（含目标本身）是重解析点 → 403 `reparse-point`；判断用 `fileAttributes` 的 `FILE_ATTRIBUTE_REPARSE_POINT` 位，拿不到时退回 `lstat` 的 `isSymbolicLink`。
    7. realpath 不在 realpath(root) 之内 → 403 `outside-root`。
    8. 不存在 → 404 `not-found`；是目录 → 404 `directory`（不列目录）。
    9. 后缀不在白名单 → 404 `type-not-allowed`。
    - `/` 映射到 index.html；找不到的路径回 404，不回退到 index.html。
    - Content-Type 白名单：html → `text/html; charset=utf-8`；js、mjs → `text/javascript; charset=utf-8`；css → `text/css; charset=utf-8`；json → `application/json; charset=utf-8`；txt → `text/plain; charset=utf-8`；woff2 → `font/woff2`；woff → `font/woff`；svg → `image/svg+xml`；png → `image/png`；ico → `image/x-icon`。
    - 经 HTTP 的负面测试（原始套接字，客户端不做规范化）至少放这几条：`/..%2f..%2f<文件>`、`/%2e%2e%2f<文件>`、`/x%5c..%5c<文件>`、带 `%00` 的路径、`/%252e%252e%252f<文件>`；每条都断言拿不到 assets 之外的文件（正文里没有金丝雀文件的内容）；明确拒绝的几种（含 `%2f`、`%5c`、`%00` 与解码出错）断言回 400 且带安全头。
  - 请求体：Content-Length 声明超过 65536 → 413（一个字节也不读）；分块传输正文读到第 65537 个字节 → 413 并 `reader.cancel()`；正好 65536 字节的合法 JSON → 200。
  - 引导地址：59999 毫秒可用、60000 毫秒拒绝；用过的 nonce 一律 404。
  - 锁：owner.json 里的 pid 已死 → 接管；pidAlive 为 null → busy（不接管）。
  - 空闲时限：null 为 1800 秒；bigint 与很大的值换算之后不让 setTimeout 溢出。

- 错误与重试：
  - HTTP 状态与错误信封的对应：400 请求体不是合法的 JSON；401 未认证；403 请求被拒绝（Host、Origin、CSRF、控制令牌、静态越界）；404 没有这个接口（引导地址失效也回 404）；405 只支持 GET 与 POST（带 `Allow: GET, POST`）；413 请求体超过 64 KiB；415 请求体只收 application/json；429 控制令牌失败次数过多（带 `Retry-After`）；500 服务内部错误。
  - 服务自己产生的错误一律走同一个错误信封（ok 为 false、exit_code 为 null、data 为 null、output 与 command 是空数组、messages 一行 `ERROR: …`）。
  - 已知限制（写进 README，本片不把它当缺陷）：Bun 自己给出的三种响应不带安全头——Content-Length 超过 `maxRequestBodySize` 的 413、畸形请求行的 400、分块传输超过 Bun 上限的 413；理由是这些是 Bun 生成的纯文本，没有攻击者能控制的 HTML。
  - 服务不重试任何请求；测试里的有限重试只允许用于计时类用例的宽松阈值。

- 并发、取消与状态变化：
  - 服务是单进程，请求并发交给 Bun；`inflight()` 记进行中的请求数，有请求时不算空闲。
  - 计数（ping 的 posts、会话、nonce、控制令牌失败次数）都在内存里，进程结束即丢；`POST /control/bootstrap` 会把全部会话与 nonce 作废。
  - 锁目录：同一仓库同时只允许一个服务；写完 owner.json 再读回来核对令牌，窗口缩小但不能消除（两个进程同时接管同一把死锁，与 DirLock 的已知竞争相同）。
  - 关停只做一次：server、计时器、stdin、锁各收一次；看门狗 3 秒后强制退出。

- 兼容性：
  - `ts/packages/ui/src/main.ts` 的 `UiArgs`、`checkArgs`、`EXIT_*` 不改；`runUi` 在 `checkArgs` 通过之后 `return serveUi(args, io)`。
  - `ts/packages/ui/package.json` 的 `exports` 只有 `"./main"`，本片不改它：新模块之间用仓库内相对路径引入，`src/localhttp/index.ts` 是服务层唯一的汇总出口。
  - `ts/packages/ui/test/args.test.ts` 的三条既有用例不改、不删、不跳过。
  - 对外协议（握手行、引导地址路径、会话 cookie 名、控制头名、信封七字段、HTTP 状态码）如上；第 2、3 片在此之上加路由，不改这些约定。

## Steps
1. 预检（只读）：核对 Repository facts；确认 `ts/packages/ui/src` 只有 `main.ts`、`ts/packages/ui/test` 只有 `args.test.ts`、`src/localhttp` 不存在、根 `.gitignore` 末行是 `.agent/.ui.lock/`、`ts/node_modules/.themis-installed` 里有 `bun_path`。不符即停并报告。
2. 令牌、会话与 cookie：`src/localhttp/tokens.ts`、`src/localhttp/session.ts`、`src/localhttp/cookie.ts`，以及 `src/localhttp/index.ts` 的汇总出口；配套 `test/localhttp-session.test.ts`。
3. 控制令牌：`src/localhttp/control.ts` 与 `test/localhttp-control.test.ts`（恒定时间比较用 `vi.mock` 包住 `node:crypto`，断言 `timingSafeEqual` 的调用次数）。
4. Host、Origin、CSRF 与响应头：`src/localhttp/guards.ts`、`src/localhttp/headers.ts` 与 `test/localhttp-guards.test.ts`、`test/localhttp-headers.test.ts`。
5. 请求体与访问记录：`src/localhttp/body.ts`、`src/localhttp/accesslog.ts` 与 `test/localhttp-body.test.ts`、`test/localhttp-accesslog.test.ts`。
6. 信封、路由表与请求管线：`src/envelope.ts`、`src/routes.ts`、`src/app.ts` 与 `test/app.test.ts`（进程内直接 `app.fetch(new Request(...))`，不起服务）。
7. 静态资源：`src/static.ts` 与 `test/static-paths.test.ts`、`test/fixtures/resolve-asset.ts`（在 Bun 下调 `resolveAsset` 的探针，测 junction）。
8. 锁目录：`src/lockdir.ts` 与 `test/lockdir.test.ts`。
9. 生命周期：`src/lifecycle.ts` 与 `test/lifecycle.test.ts` 的纯函数部分。
10. 服务入口：`src/server.ts`，并改 `src/main.ts`（`runUi` 接上 `serveUi`）。
11. 起真进程的测试：`test/harness.ts`、`test/fixtures/serve-entry.ts`、`test/service.test.ts`、`test/lifecycle.test.ts` 的真进程部分。
12. 端到端：`test/launcher.e2e.test.ts`（经真的 `python scripts/pi_dispatch.py ui --desktop --assets …`）。
13. README：写结构、安全基线、最小 API、测试的跑法、「不是安全沙箱」，以及上面三条已知限制（Bun 自己回的 413 与 400 不带安全头）。
14. 自检：跑 Validation commands 中与改动相关的检查，记录命令与结果；确认 `git status --porcelain` 只出现允许范围内的路径。

测试夹具的约定（写 `test/harness.ts` 时照此）：

- 起服务进程：`bunExecutable() --no-env-file --config=ts/bunfig.toml ts/packages/cli/src/main.ts --pyargs-b64 <b64>`，与启动器走同一条路；只有 T7a 的「过期」一条起 `test/fixtures/serve-entry.ts`（先 `initFileAttributes`，再 `serveUi(args, io, { nonceTtlMs: 1500 })`）。
- 子进程：stdio 都用管道；环境去掉 `BUN_OPTIONS`、`NODE_OPTIONS`、`NODE_PATH`、`BUN_INSPECT*`。
- HTTP 客户端：一般请求用 `node:http`（可以自定义 Host、Origin、Cookie，不跟随重定向）；T13 的原始路径与 T15 的分块正文用 `node:net` 原始套接字，客户端不做规范化。客户端在 Node 一侧（Vitest 跑在 Node 上），服务在单独的 Bun 进程里。
- afterEach：关掉 stdin 的写端，最多等 10 秒退出；没退出就 `child.kill()`，并让这条用例失败，不留进程。
- 测试从不发控制台信号（SIGINT、CTRL_BREAK），只靠关 stdin 与 kill 收进程。

变异清单（清单文件 `ts/mutations/ui-localhttp.ts.json` 与 `ts/mutations/ui-static.ts.json` 属禁区，由门禁端写；本片只把条目与「哪条用例必须红」钉在这里，执行端不落盘）：

- LH01 consume 不删 nonce → 必须红：T7a nonce 只能用一次；U1 引导地址第二次 404。
- LH02 过期判断放宽（`<` 改成 `<=` 或去掉过期判断）→ 必须红：T7a 60 秒（60000 毫秒拒绝）；service 的 T7a 过期。
- LH03 `NONCE_TTL_MS` 改成 600000 → 必须红：T7a 60 秒。
- LH04 过期与用过两种拒绝的响应变得不同 → 必须红：T7a 过期与用过走同一个响应；service 的 T7a 逐字节相同。
- LH05 `constantTimeEqual` 改成 `given === expected` → 必须红：T7c 恒定时间比较（`timingSafeEqual` 没被调用）。
- LH05b 长度不同时提前返回 false → 必须红：同一条（长度不同那一行）。
- LH05c 不先取摘要、直接比较原串 → 必须红：同一条（长度不同抛 RangeError）。
- LH06 `CONTROL_MAX_FAILURES` 改成 50，或去掉锁定判断 → 必须红：T7c 连续 5 次失败之后锁定；service 的 T7c。
- LH07 成功之后不清零 → 必须红：成功之后失败计数清零。
- LH08 锁定时长不翻倍，或去掉 60 秒的封顶 → 必须红：T7c 锁定 1 秒、翻倍、封顶 60 秒。
- LH09 锁定期内照样比较 → 必须红：T7c 锁定期内对的令牌也回 429。
- LH09b 不看 `X-Themis-Control`、改读 cookie → 必须红：只看 X-Themis-Control 一条；U16 只带 cookie 403。
- LH10 Host 改成只看结尾的 `:端口` → 必须红：U2 两条（纯测试与 service）。
- LH11 Host 不看端口 → 必须红：U2 端口不对 403。
- LH12 POST 跳过 Origin 检查 → 必须红：U3 Origin 不同或缺 403。
- LH13 缺 Origin 时放行 → 必须红：U3 缺 Origin 那一行。
- LH14 不要求 `X-Themis-UI` → 必须红：U3 X-Themis-UI 必须是 1；service 的 U3。
- LH15 Content-Type 任意都收 → 必须红：U3 只认 application/json；service 的 415。
- LH15b 改成「含 json 就行」→ 必须红：同一条（application/jsonp、text/json 两行）。
- LH16 去掉边读边数、只看 Content-Length → 必须红：T15 分块 65537 字节 413（纯测试与 service）。
- LH17 上限放宽到 65537 或 131072 → 必须红：T15 65536 收、65537 拒的边界。
- LH18 超限之后不 cancel、继续读 → 必须红：T15 之后不再读。
- LH19a、LH19b、LH19c、LH19d 分别去掉 CSP、nosniff、no-referrer、no-store → 必须红：U12 两条。
- LH20a、LH20b、LH20c 分别去掉 HttpOnly、SameSite=Strict、Path=/ → 必须红：Set-Cookie 逐字；U1 的 Set-Cookie。
- LH21 `Sessions.revokeAll` 不清空 → 必须红：Sessions 用例；U16 旧会话 401。
- LH22 record 记路径而不是路由名，或去掉路由名校验 → 必须红：T7b 访问记录只有路由名、状态码与耗时。
- LH23 允许 PUT、DELETE、OPTIONS、HEAD → 必须红：只有 GET 与 POST 一条。
- LH24 不删 `Access-Control-*`，或加上 `Access-Control-Allow-Origin: *` → 必须红：不开 CORS 一条。
- LH25 `randomBytes(32)` 改成 16 → 必须红：令牌 32 字节（43 个字符）。
- LH26 `controlOriginAllowed` 恒返回 true → 必须红：U16 Origin 是别的站点 403。
- ST01 去掉 `..` 段检查 → 必须红：T13-1。
- ST02 去掉 `%2e` 检查 → 必须红：T13-2。
- ST03 去掉 `%2f` 检查 → 必须红：T13-3。
- ST04 去掉 `%5c` 检查 → 必须红：T13-4。
- ST05 去掉反斜杠检查 → 必须红：T13-5。
- ST06 去掉盘符检查 → 必须红：T13-6。
- ST07 去掉空段（UNC）检查 → 必须红：T13-7。
- ST08 去掉冒号（ADS）检查 → 必须红：T13-8。
- ST09 去掉末尾的点检查 → 必须红：T13-9。
- ST10 去掉末尾的空格检查 → 必须红：T13-10。
- ST11 去掉重解析点检查 → 必须红：T13-11。
- ST12 `isWithin` 恒返回真 → 必须红：T13-12。
- ST13 目录不再回 404，或列出目录 → 必须红：T13-13。
- ST14 白名单之外的后缀按 octet-stream 给出 → 必须红：T13-14。
- ST15 坏的编码不拒绝 → 必须红：T13-15。
- ST16 去掉控制字符检查 → 必须红：T13-16。
- ST17 静态资源不带安全头 → 必须红：U12（静态那一行）。
- ST18 不先拒绝编码过的分隔符（`%2f`、`%5c`）→ 必须红：static-paths.test.ts 的「预解码拒绝 `%2f` 与 `%5c`」用例；service.test.ts 的 T13-HTTP `/..%2f..%2f<文件>` 与 `/x%5c..%5c<文件>` 两行。
- ST19 解码两次 → 必须红：static-paths.test.ts 的「`%252e%252e` 只解码一次、回 404」用例。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t015_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`bun install --frozen-lockfile` · cwd：ts · 超时：900s · 期望退出码：0
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V04（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V05（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0
- V06（必要）：`python -m pytest tests/test_kernel_impl.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V07（必要）：`git status --porcelain --untracked-files=all` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：`ts/packages/ui/`，不得出现：`(?m)^\s*\S+\s+(?!ts/packages/ui/)`

## Definition of done
- D01：握手与绑定——stdout 只有一行 JSON，字段与次序是 `themis_ui`、`bootstrap`、`origin`、`control`、`pid`，`origin` 是 `http://127.0.0.1:<port>`；只绑 127.0.0.1，同一端口在 ::1 上连不上；证据：V03（service.test.ts 的握手用例与 ::1 用例、launcher.e2e.test.ts）；目的：外壳能凭这一行找到服务，别的一概不写进 stdout。
- D02：U1 会话与引导地址——不带 cookie、cookie 错、cookie 重复时 GET 与 POST `/api/v1/ping` 都是 401 且 data 为 null；引导地址第一次 302 到 `/` 且 Set-Cookie 逐字，第二次 404 且没有 Set-Cookie；`/api/` 下不存在的路径没有会话 401、有会话 404；证据：V03（service.test.ts 与 app.test.ts）；目的：会话是唯一的 API 入口凭证，不泄露资源是否存在。
- D03：T7a 一次性与 60 秒——nonce 只能用一次；59999 毫秒可用、60000 毫秒拒绝；过期与用过两种拒绝走同一个响应（状态、头除 Date、正文逐字节相同）；证据：V03（localhttp-session.test.ts 与 service.test.ts 的 serve-entry 用例，TTL 1.5 秒）；目的：引导地址是一次性的，猜不到也用不了第二次。
- D04：U2 Host 校验——只认 `127.0.0.1:<port>` 与 `localhost:<port>`；`evil.example:<port>`、端口不对、不带端口、`localhost.` 末尾带点一律 403；Host 不对时引导地址没有被消耗；证据：V03（service.test.ts 与 localhttp-guards.test.ts）；目的：防 DNS 重绑定。
- D05：U3 CSRF——POST 不带 `X-Themis-UI` 是 403；Origin 不同或缺是 403；Content-Type 不是 application/json 是 415；这三种情况下处理函数没有运行（posts 仍为 0）；合格的 POST 是 200 且 posts 变成 1；证据：V03（service.test.ts 与 localhttp-guards.test.ts）；目的：网页不能借外壳的浏览器发写请求。
- D06：U16 控制接口——不带令牌、令牌错、只带 cookie 都是 403；对的令牌是 200 并给出新的引导地址，旧会话 401、旧引导地址 404、新引导地址可用；Origin 是别的站点是 403 且不计入限速；证据：V03（service.test.ts 与 localhttp-control.test.ts）；目的：只有外壳能换引导地址，网页不能把外壳的重新认证锁死。
- D07：T7c 恒定时间比较与限速——比较走 `timingSafeEqual` 的两份 32 字节摘要，长度不同与缺头都走同一条路且不抛错；连续 5 次失败之后锁定 1 秒，再失败翻倍，封顶 60 秒；锁定期内对的令牌也回 429 并带 Retry-After，且不计数；成功之后失败计数清零；证据：V03（localhttp-control.test.ts 与 service.test.ts）；目的：令牌不能靠时序或暴力试出来。
- D08：T7b 日志里没有令牌——访问记录只有路由名、状态码与耗时，不含引导地址、控制令牌、cookie 与请求正文；不像名字的路由名记成 `invalid-route-name`；服务的 stdout 与 stderr 里也没有引导地址、控制令牌、cookie 与请求正文；证据：V03（app.test.ts、service.test.ts、localhttp-accesslog.test.ts）；目的：令牌不能从日志流出去。
- D09：T13 静态资源边界——纯函数逐类给出 reason：`..` 段 dot-segment、`%2e`/`%2f`/`%5c` encoded-dot-or-separator、反斜杠 backslash、盘符 drive-letter、UNC empty-segment、ADS colon、末尾的点或空格 trailing-dot-or-space、坏编码 bad-encoding、控制字符 control-char、junction 跑出目录 reparse-point、`isWithin` 目录外为假、目录 directory、不在白名单的后缀 type-not-allowed；`rawPathOf` 不做规范化；`/` 给 index.html，`/assets/app.js` 的 Content-Type 照白名单并带 nosniff；证据：V03（static-paths.test.ts 与 test/fixtures/resolve-asset.ts）；目的：静态资源永远出不了 `--assets` 目录。
- D10：T13 只解码一次与 HTTP 负面测试——原始 pathname 里先拒绝 `%2f`、`%5c`、`%2e`、`%00`（不分大小写）并回 400，之后只解码一次，`decodeURIComponent` 出错回 400，`%252e%252e` 解码一次是字面文件名、回 404；经 HTTP 的负面测试至少覆盖 `/..%2f..%2f<文件>`、`/%2e%2e%2f<文件>`、`/x%5c..%5c<文件>`、带 `%00` 的路径、`/%252e%252e%252f<文件>`，每条都断言拿不到 assets 之外的文件，明确拒绝的几种断言 400 且带安全头；证据：V03（static-paths.test.ts 与 service.test.ts 的静态资源负面用例）；目的：编码过的分隔符不能绕过目录边界，第二次解码不能把 `%252e%252e` 变成 `..`。
- D11：T15 请求体上限——分块传输 65537 字节是 413 且之后不再读，65536 字节收下；Content-Length 声明超过 65536 是 413 且一个字节也不读；坏的 UTF-8、不是 JSON、空正文都是 400 且不回显原值；证据：V03（localhttp-body.test.ts 与 service.test.ts）；目的：请求体是有限的一行，坏正文也不回显。
- D12：U12 安全头——经服务处理函数的响应都带 CSP（逐字照 D4）、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`；API、引导、控制与错误响应带 `Cache-Control: no-store`；静态资源带 `Cache-Control: no-cache`；响应里没有任何 `Access-Control-*` 头；证据：V03（service.test.ts 覆盖 200、401、403、404、405、413、415、429、302、静态 200 与 404、400；localhttp-headers.test.ts）；目的：本机响应不给浏览器别的能力。
- D13：U12 的范围与已知限制——README 写明 Bun 自己给出的三种响应（Content-Length 超过上限的 413、畸形请求行的 400、分块传输超过 Bun 上限的 413）不带安全头，并写明理由（纯文本，没有攻击者可控的 HTML）；服务自己的计数（64 KiB 加 1 就停）先于 Bun 的上限触发，`maxRequestBodySize` 是 131072；证据：review、V03；目的：已知限制写清楚，别被当成漏洞，也别让服务依赖 Bun 那一层。
- D14：U11 参数与已有服务——不带 `--desktop`、找不到前端资源都退出 2 且提示原文、stdout 为空；已有服务在运行时退出 1、stderr 报出 pid 与端口、stdout 为空、原来的服务照常响应；握手行之外 stdout 没有别的输出；`ts/packages/ui/test/args.test.ts` 的三条既有用例未改未删；证据：V03（args.test.ts、lifecycle.test.ts、service.test.ts、launcher.e2e.test.ts）；目的：用法错误与占用各有各的退出码，不静默。
- D15：U13 与 T14 生命周期、锁——`--idle-timeout 1` 时退出 0 且锁目录被清除；有请求就推迟空闲退出；stdin 管道关闭（EOF）时退出 0、锁目录被清除、stdout 仍只有握手一行；锁里的 pid 已经不在时接管，持有者活着或判断不了时 busy，owner.json 缺失且锁目录不到 10 秒时 busy、超过 10 秒时接管；释放只删自己的锁；空闲时限 null 为 1800 秒，bigint 与很大的值不让 setTimeout 溢出；经启动器起再走一遍 stdin EOF；证据：V03（lifecycle.test.ts、lockdir.test.ts、launcher.e2e.test.ts）；目的：服务不残留、不留锁、不占端口。
- D16：只有 GET 与 POST——PUT、DELETE、OPTIONS、HEAD 都是 405，带 `Allow: GET, POST` 与安全头，响应里没有 `Access-Control-*` 头；证据：V03（service.test.ts）；目的：方法白名单是 CSRF 的一半，HEAD 也不例外。
- D17：门禁、范围与测试完整性——G01、R01、V01 到 V07 全部通过；改动只落在 `ts/packages/ui/src/**`、`ts/packages/ui/test/**`、`ts/packages/ui/README.md`；不删、不跳过、不弱化既有测试；依赖清单与锁文件未改；证据：G01、R01、V01、V02、V03、V04、V05、V06、V07、scope、review；目的：不破坏已有门禁，也不靠削弱测试过关。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 5（按 task-id 汇总，包括返工版本；本任务此前已用 3 次）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 18000（已用 7200 秒，加 2 次单次时限 7200 秒后仍留有余量）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查 300s、实现与补测 2400s、必要检查 700s、最终报告 200s；总计不超过单轮时限

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D17，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261023T131019430268Z-owner-b9f3bb：

> 摘要: 九条仓库外事实已逐条实测，结果写在 .agent/design/t015-事实核实.md（提交 2a5c721，T015 的基线已挪到这里），合同端照它写合同。Q1、Q3 取 (a)；Q2 取 (a)，站主已补上忽略规则。
>
> 【一、事实（详情见上面那份文件）】
> - F1：已核实，Bun 1.4.2。
> - F2：实情相反。req.url 是规范化过的：`..`、`%2e%2e` 已解析掉，反斜杠换成 `/`，只有 `%2f` 保留编码。
>   - HTTP 的 T13 负面测试断言“拿不到 assets 之外的文件”；
>   - 原始形式的拒绝由路径解析的纯函数负责、逐类测；
>   - `%2f`、`%5c` 到得了 fetch，HTTP 层必须拒绝。
> - F3：部分属实。Content-Length 超限、畸形请求行，都不调 fetch，Bun 回 413 或 400，不带安全头。分块传输超限时 fetch 会被调用，但 Bun 自己回 413，处理函数给的响应发不出去。所以服务自己的计数必须先于 Bun 的上限触发（2 倍）。
> - F4：已核实，stop(true) 3 毫秒内收掉保活连接。测试客户端放在 Node 一侧：同一个 Bun 进程里的 node:net 客户端收不到 close。
> - F5：部分属实。GET 自动加 Date；HEAD 交给 fetch，但响应里没有 Date。测试不依赖 Date。
> - F6：已核实，写端一关就读到 EOF；经 Python 原样继承 stdin 也一样。
> - F7：约 10 秒，可用 idleTimeout 设，上限 255。
> - F8：已核实。Node 与 Bun 的 lstat 都认得出 junction（isSymbolicLink() 为 true）。
> - F9：未核实，本片不依赖：照 controlOriginAllowed，两种情况都成立；D3 外壳时实测。
> - 另外三条：
>   - node:http 能自定义 Host：已核实；
>   - vi.mock 能包住 node:crypto：已核实；
>   - 建 junction 不要管理员：环境本身就是管理员，测试照常建。
>
> 【二、拍板】
> - Q1：(a)，/api/v1/ping 长期保留。
> - Q2：(a)，已落地（2a5c721）：根 .gitignore 与 kit 的 gitignore.append.txt 都加了 `.agent/.ui.lock/`。
> - Q3：(a)。README 写明 Bun 自己给出的三种响应（413 两种、400 一种）不带安全头。
> - 新加一条：照 D4“只有 GET 与 POST”，HEAD 与其他方法一律回 405，带安全头。
> - 规划里自己定了的几件事，都同意。

站主来信 20261023T131150720366Z-owner-356a88：

> 摘要: 站主补充三条验收要点（themistally-15 复核事实核实之后提出，站主采纳），合同端写进合同与验收：静态路径只解码一次；Bun 自己回的 413、400 不带安全头记为已知限制；其余方法 405。
>
> 1. 静态资源路径只解码一次。
>    - 顺序：在原始 pathname 里先拒绝 `%2f`、`%5c`、`%00`（不分大小写），回 400；之后只解码一次，decodeURIComponent 抛 URIError 时回 400；解码后再交给 T13 的边界规则。
>    - 原因：`/..%2f..%2fsecret` 在 Bun 看来是普通的一段，不是 `..`，规范化之后原样留着，解码一次就成了 `../../secret`。
>    - 双重编码的 `%252e%252e` 解码一次是字面的 `%2e%2e`。纯函数不能再解第二次，当成一个不存在的文件名处理，回 404。
>    - 经 HTTP 的负面测试至少放这几条：`/..%2f..%2f<文件>`、`/%2e%2e%2f<文件>`、`/x%5c..%5c<文件>`、带 `%00` 的路径、`/%252e%252e%252f<文件>`。
>      - 每条都断言拿不到 assets 之外的文件；
>      - 明确拒绝的几种（含 `%2f`、`%5c`、`%00`、解码出错）断言回 400 且带安全头。
>    - 静态资源的变异清单加两条：不先拒绝编码过的分隔符；解码两次。
> 2. Bun 自己回的 413（Content-Length 超限）、400（请求行畸形）不带安全头，作为已知限制写进 README。理由：这些是 Bun 生成的纯文本，没有攻击者能控制的 HTML。服务自己数到 64 KiB 加 1 先触发、Bun 的上限设成 2 倍，照规划不变。
> 3. HEAD 与其余方法一律回 405 并带安全头；`/control/*` 的 Origin 照 controlOriginAllowed，有无两种情况都成立。这两条同上一封信。

## Rework（返工第 2 轮，内核追加）

- 基线 `ad113e1b8193fbc5e3c74e0b6c89ec3dfb4672e0` 是 attempt-004 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

【执行端 B1】ts/packages/ui/src/app.ts 管线第 4 步：把 control.bootstrap 排除在 csrfCheck 与 readJsonBody 之外。依据：合同 v5.md:114「control.bootstrap：POST /control/bootstrap，要 Host、controlOriginAllowed、ControlGate，不读正文」（穷举门，不含 CSRF 三查与正文解析）与 v5.md:274 D06「对的令牌是 200 并给出新的引导地址」。期望：POST /control/bootstrap 只要 Host 合法、controlOriginAllowed 通过（缺 Origin 或同源即通过）、ControlGate 放行，就必须 200 且 data.bootstrap 是新引导地址，与「有没有正文、正文是不是 JSON、有没有 Content-Type、有没有 X-Themis-UI」全部无关；控制处理函数仍不读正文（routes.ts 已如此，不用改）。建议改法：把分支条件写成 `if (method === "POST" && match.route.name !== "control.bootstrap") {`，内部两行 `const rejection = csrfCheck(request);` 与 `const parsed = await readJsonBody(request);` 一字不动——这样白盒 test_whitebox_app_pipeline 的 pin 与 order 断言、以及 test_control_bootstrap_no_body_matches_contract 的 named_guard 都能过。/api/v1/ping 的 POST 行为一字不改（D05：403/403/415 且 posts 仍为 0；D11：65537→413、65536→收下；正文必须是 JSON 对象否则 400 不回显）。
【执行端 B2】ts/packages/ui/test/ 里补行为证据（不得删、不得 skip、不得放宽既有 D05/D06/D07 用例；G01 的控制组带全套头与 {} 正文，修完必须仍绿）。至少覆盖：正确令牌 + 不带正文 → 200 且 data.bootstrap 能 302 建会话；正确令牌 + 不带 Content-Type → 200；正确令牌 + 不带 X-Themis-UI → 200；正确令牌 + 不带 Origin → 200；正确令牌 + 坏 JSON 正文 → 200（正文被忽略）；正确令牌 + 合法 JSON 对象正文 → 200（回归）；令牌错/不带令牌/只带 cookie → 403；外来 Origin → 403 且不计入限速；连续 5 次失败后正确令牌 → 429 带 Retry-After。同时在 app.test.ts 或 service.test.ts 里断言 POST /api/v1/ping 缺 X-Themis-UI/缺 Origin/Content-Type 不是 JSON 时仍是 403/403/415（证明豁免没有外溢到 API）。
【执行端 B3】executor-report.json 如实改写：D06 的 note 不得再写「控制接口 403/200」了事，要写明「只带对令牌（无正文、无 Content-Type、无 X-Themis-UI）即 200」并给出上面新增用例的名字；contract_conflicts 那条删掉「两种读法下都无害、无需标 blocked」的结论，改写为「以路由表/D06 为准，管线第 4 步不适用于 control.bootstrap」；limitations 补一条「真实外壳（D3 Electron）发 /control/bootstrap 的请求头未核实（站主记录 F9），本实现按不依赖正文与 CSRF 头处理，外壳无论带不带正文都能 reauth」。
