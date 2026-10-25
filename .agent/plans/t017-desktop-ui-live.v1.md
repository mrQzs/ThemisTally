# TASK: t017-desktop-ui-live

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 31493c12c11dab7b96b7b670618c9eb8a4036313
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在 `ts/packages/ui` 里加桌面端本机服务的第 3 片：SSE 路由 `GET /api/v1/events`（每次订阅先发一份全量快照并带序号，之后只在名单上的输入变了才推一份整份新信封；心跳、retry、去抖、多订阅者共用一次 status、没有订阅者就停、跳过链接与重解析点、会话失效即断流、Bun 的连接空闲超时按站主拍板用 `server.timeout(req, 0)` 只放宽这一条连接；连接管理：全局 16 个、每会话 4 个订阅的上限，超限回 503 带 Retry-After 且不挤掉已有订阅，会话作废、控制令牌换发引导地址、服务关停与空闲退出时主动关流并清定时器，心跳写失败立刻清理，开着的订阅算活动阻止空闲退出），作业路由 `POST /api/v1/jobs`、`GET /api/v1/jobs/<id>`、`POST /api/v1/jobs/<id>/cancel`（六类 kind、严格参数校验、随机不可猜的作业号、容量 100 的内存表、四种终态、取消结束整棵进程树），第 2 片复核留下的三条加固（输出上限边写边看、真内核拒绝越界路径、关停清队列并摘监听），以及第 1 片 D11/D12 的计时抖动（改成两段式发送，断言只加强不放宽）。

## Non-goals
- 不做日志跟随（内核要先给 `logs cat` 补「只给已经写完的行」的开关，那是内核改动）、预览、写路由、凭据录入作业、`/control/jobs/*`（D2）、`operations`、脱敏结果的缓存。
- 不新增或修改内核的 CLI 命令与选项；六个作业 kind 都用现成的内核写法（见路由表）。
- 不改 `ts/packages/ui/src/localhttp/**`（一个字不改）、不改 `UiArgs`、不改 `ts/packages/ui/package.json`，不加依赖。
- 不把并发上限、队列长度、作业时限、SSE 订阅上限开放给用户（只开放给测试入口 `ServeOverrides`）。
- 不改 Bun 的全局 `idleTimeout`（生产路径保持缺省），不改 Bun.serve 的其他行为，不改别的包的任何文件（见 Scope 的 forbidden_paths）。
- 不改 `ts/packages/base/**`、`ts/packages/cli/**`、`ts/packages/config/**`、`ts/packages/contracts/**`（含 `status-inputs.json`）、`ts/packages/dispatcher/**`、`ts/packages/hub/**`、`ts/package.json`、`ts/bun.lock`、`ts/tsconfig.json`、`ts/vitest.config.ts`、`ts/tools/**`、`ts/mutations/**`、`scripts/**`、`desktop/**`、`docs/**`、`tests/**`。
- 不改 `ts/packages/ui/test/args.test.ts`；既有 19 条读路由的表与断言一条不动（既有用例只许追加，不许删改）。
- 不推翻任何过渡断言：名单里的过渡断言都在 desktop/** 的前端或 localhttp 的常量里，本片两样都不碰。

## Repository facts
基线 `d329e518ef340509e699b14849257882c834158f` 上的实际内容。规划报告 §2 的 A1–A10 逐条核实结论如下，逐条核实过，都是定论。

- **A1（名单怎么导入）**：`ts/packages/ui/package.json` 依赖 `@themis/contracts`；`ts/packages/contracts/package.json` 的 exports 里有 `"./status-inputs.json": "./status-inputs.json"`；`ts/tsconfig.json` 的 `module` 是 NodeNext、`resolveJsonModule` 为 true。结论：ui 包从 `@themis/contracts/status-inputs.json` 这一份文件取名单，**一个字都不许抄进 ui 包**（抄了就会与内核名单漂移）。写法定：用 ESM 的导入属性 `import STATUS_INPUTS from "@themis/contracts/status-inputs.json" with { type: "json" };`（TypeScript 6.0.3 与 Bun 1.4.2 都支持这个写法）；若 V05（类型检查）报这个写法不被接受，改成运行时解析同一份文件（`createRequire(import.meta.url).resolve("@themis/contracts/status-inputs.json")` 之后 `readFileSync` + `JSON.parse`），仍然是同一份文件而不是抄一份，并在执行报告的偏离一节写明。两条路都不许把名单的值写进 ui 包。
- **A2（安全头不缓冲正文）**：`ts/packages/ui/src/localhttp/headers.ts` 的 `withSecurityHeaders` 用 `new Response(response.body, …)` 原样转交正文流，所以 SSE 的 ReadableStream 套上安全头之后仍然是流。结论：SSE 走既有管线即可，不必改 headers.ts。
- **A3（SSE 长连接不计入 inflight）**：`ts/packages/ui/src/app.ts` 在处理函数返回之后于 `finally` 里 `inflightCount -= 1`，所以 SSE 的长连接不算进行中的请求。结论：空闲退出要另外看 hub 的订阅者数与作业表（见 Behavior contract）。
- **A4（会话）**：`ts/packages/ui/src/localhttp/session.ts` 有 `Sessions.valid(token)` 与 `Sessions.revokeAll()`；`readSessionCookie` 由 `ts/packages/ui/src/localhttp/index.ts` 导出。结论：SSE 订阅时取一次会话令牌，每次推送与心跳之前查 `valid`，失效就关流。
- **A5（重解析点）**：`ts/packages/ui/src/static.ts` 已导出 `isReparsePoint(path)`（先用 `fileAttributes` 的 FFI，取不到再退回 `lstat`）。结论：SSE 的监视直接复用它，不另写一套。
- **A6（内核的 logs 解析器与转发）**：`scripts/kit_logs.py` 的 search 子解析器把 pattern 记成位置参数，另有 `--task`、`--max`（int）与 `--json`，长选项关掉了缩写（`pd.no_abbrev`）；`scripts/pi_dispatch.py` 在 argparse 之前截获 `logs`，其后的参数原样转交给 `kit_logs.main`；readonly 选 ts 时也用同一个 `kit_logs.build_parser` 解析。结论：`logs search` 的 argv 模板照 `logs search --json [--task=<task>] [--max=<max>] -- <pattern>` 写，pattern 是唯一放在 `--` 之后的参数。
- **A7（内核的 config 写法与两个正则）**：`scripts/kit_config.py` 里 `config doctor [--record TASK.vN] [--json]`、`config runtime scan [--add] [--json] [--yes]`、`config runtime probe <runtime_id> [--json]`、`config models <runtime> [--json]`；`scripts/pi_dispatch.py` 的 `PLAN_KEY_RE` 是 `^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]{0,3}$`，`TASK_ID_RE` 是 `^[a-z0-9][a-z0-9-]{0,63}$`。结论：作业的 record 过 PLAN_KEY_RE，runtime 与 task 过 TASK_ID_RE。
- **A8（内核内部的时限）**：`scripts/kit_roles.py` 的 `--version` 探测 30 秒、`--help` 探测 90 秒、`--list-models` 90 秒；`scripts/pi_dispatch.py` 的 `pi_model_readiness` 里模型列表与 auth check 各 90 秒；`runtime scan` 对四个适配器各跑一次 `--version`（内部上界 120 秒），`runtime probe` 是 30 + 90 = 120 秒，`models` 是 90 秒；`doctor` 对每个 headless 的 pi 角色做版本、帮助、模型列表与登录检查，两个 headless 角色（execution 与 contract）各一个模型时最坏 30 + 90 + 2 × (90 + 90) = 480 秒。结论：doctor 与 doctor-record 的作业时限从规划报告的 300 秒放宽到 **600 秒**（照 A8 的「核对出更长的内部时限就按比例放宽」）；runtime-scan 150 秒、runtime-probe 150 秒、models 120 秒、search 180 秒照规划报告。
- **A9（越界路径由谁拒绝）**：服务自己的 `validPath`（`ts/packages/ui/src/readroutes.ts`）只拒绝以 `-` 或 `/` 开头、含控制字符与含反斜杠的路径，所以 `../x`、`C:/x`、`a/../../x` 会过服务这一关；内核的 `logs cat` 只认证据清单里的相对路径（`scripts/kit_logs.py`），不在清单里就抛 `LogsError`，退出码 2（EXIT_USAGE）。结论：H2 那条用例的期望是 200 信封、`ok` 为 false、`exit_code` 为 2、`data` 为 null、正文不含夹具仓库之外的金丝雀内容；`..\x` 由服务自己回 400（反斜杠）。
- **A10（既有门禁与 README 的约束）**：`tests/test_gate_t015_baseline.py` 钉住 README 的 D13 已知限制（413、400、畸形、分块、不带安全头、纯文本、64 KiB/65536、131072 这些原句）；`tests/test_gate_t016_baseline.py` 钉住 README 的结构、Retry-After、409/503/504、已知限制、`config secret check`、`TYPESAFE_API_KEY` 与终端口径那几段，还钉住 readroutes.ts 的 19 条路由名与时限、`ServeOverrides` 只增不减、ui 测试目录里没有 skip/only/todo、新源文件要从 `main.ts` 顺 import 到达。两份门禁里**没有任何一条**钉死「连接约 10 秒空闲断开」（t015 里的 10 秒说的是锁目录的年龄，与 Bun 的连接空闲超时无关）。结论：改 README 时把上面这些原句逐字保留；本片按站主拍板不设全局 `idleTimeout`，所以既有用例不受影响；两份 pytest 由执行端在 V06 里跑。
- **A11（会话作废的时机与 SSE 的关系）**：`ts/packages/ui/src/routes.ts` 的 `control.bootstrap` 处理函数在控制令牌校验通过后调 `state.sessions.revokeAll()` 与 `state.nonces.revokeAll()`，旧会话立刻作废；`ts/packages/ui/src/localhttp/session.ts` 的 `Sessions` 只有 `create`、`valid`、`revokeAll`，**没有按时间的过期**。结论：SSE 订阅时记下这次请求的会话令牌，hub 在每一次心跳与每一次推送之前查 `valid`；一旦为 false 就是会话作废（含换发引导地址那条路），立刻关流并清掉这个订阅者的定时器与计数。
- **A12（空闲计时与服务关停的接缝）**：`ts/packages/ui/src/server.ts` 的 `IdleTimer` 回调现在只看 `app.inflight()`；`ServeOverrides` 现在只有 `nonceTtlMs`、`maxConcurrent`、`maxQueue`、`timeouts` 四项；`shutdown()` 里先 `running.stop(true)`、再 `timer.stop()`、再 `runner.shutdown()`。结论：空闲判定要加上「hub 订阅者为 0」与「没有在等或在跑的作业」；`hub.close()` 必须排在 `runner.shutdown()` 之前；`ServeOverrides` 只增不减（门禁钉住），新增项一律可选、缺省有值。

其他事实：

- 入口：`ts/packages/ui/src/main.ts` 的 `runUi` 动态导入 `./server.ts` 的 `serveUi(args, io, overrides)`；`ServeOverrides` 现在只有 `nonceTtlMs`、`maxConcurrent`、`maxQueue`、`timeouts`。
- 路由与管线：`src/routes.ts` 的 `Route {name, method, pattern, handle}` 与 `findRoute(method, pathname, extra)`；`src/app.ts` 的管线次序是 Host → 方法白名单 → `/api/` 验会话 → findRoute → POST 的 CSRF 与正文 → 处理函数 → `withSecurityHeaders` → 访问记录。`extraRoutes` 是加路由的接缝，`createApp` 只收一批 extraRoutes（server.ts 传 `readRoutes(...)` 的结果）。
- **既有断言不许破**：`tests/test_gate_t016_baseline.py` 与 `ts/packages/ui/test/routes-auth.test.ts` 都要求「读路由表正好是 19 条，一条不多一条不少」；`ts/packages/ui/test/argv-templates.test.ts` 要求「模板里每个以 `--` 开头的项都含 `=`（`--version`、`--json` 除外）」且「位置参数不以 `-` 开头」。结论：SSE 与作业的新路由**不放进 `readRoutes()`**，另建 `eventRoutes()` 与 `jobRoutes()`，由 `server.ts` 把三批 extraRoutes 合成一批交给 `createApp`；`routes-auth.test.ts` 里另立一张四行新表（既有的 19 条表与断言一个字不动）；`JOB_ARGV` 另立一张表与另立一条 describe（不并进 `READ_ROUTE_ARGV` 的既有断言），JOB_ARGV 的示例 pattern 用不以 `-` 开头的普通值，那四个以 `-` 开头的 pattern 走独立用例。
- 信封：`src/envelope.ts` 的七字段 `ok、exit_code、data、output、messages、command、elapsed_ms`；`src/kernelenvelope.ts` 的 `envelopeBody`、`timeoutEnvelope`（超时那行原文是「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」）、`displayArgv`（`--cursor=` 显示成 `<cursor>`）、`messagesOf`（只留 `ERROR`/`WARN` 开头的行）。
- 脱敏：`@themis/base/secrets` 的 `redactJson(value, allow?)`（allow 为空或缺省时一律遮）与 `redactSecrets(text)`；`TASK_ID_RE` 在 base 的 secrets 里也有一份，含义与内核一致。
- 执行器：`src/kernel.ts` 的 `KernelRunner`（并发 4、队列 16、`runSupervised`、临时目录、输出上限事后查）、`RunOutcome` 的七种（completed/timeout/interrupted/spawn-error/output-too-large/queue-full/closing）；`release`（摘监听）是 `run()` 里的局部闭包，没有挂在 Entry 上——H3 要把它挂到 Entry 上，关停清队列时才摘得到。
- 服务层：`src/server.ts` 的 `BunServeOptions.fetch` 现在只收一个 Request，`BunServer` 只有 `port` 与 `stop`——要接 `server.timeout(req, 0)` 就得把 fetch 的第二个参数（server）与 `timeout(request, seconds)` 补进这两个本地接口。
- 内核侧（只读）：`scripts/pi_dispatch.py` 是入口；`logs search` 的 pattern 是位置参数；`config` 的子命令如 A7。
- 工具链与锁文件：Bun 1.4.2、Node 24、Python 3.12.10、TypeScript 6.0.3、Vitest 2.1.8；`ts/bun.lock` 提交、`ts/node_modules` 不提交；worktree 里各自 `bun install --frozen-lockfile`，不做目录链接。
- 仓库外事实（站主 2026-10-24 实测，Bun 1.4.2 / Python 3.12.10 / Windows；合同按这些已定案的事实写）：
  1. 服务端往外写数据**不**重置 Bun 的连接空闲计时；只给某一条请求关掉空闲超时可以用 `server.timeout(req, 0)`（fetch 的第二个参数就是 server）。
  2. Python 的 argparse 把 `--` 之后的词一律当位置参数、只剥掉第一个 `--`：`logs search --json -- -x`、`-- --`、`-- --json`、`--task t --max 5 -- -1` 解析出的 pattern 依次是 `-x`、`--`、`--json`、`-1`，`--json`/`--task`/`--max` 照传。
  3. 带未读数据关闭会发 RST（RFC 1122 4.2.2.13）；合同只写「响应头到了之后的 ECONNRESET 不算失败、仍要证明 413 先于读完」，不依赖「客户端丢数据」那一半。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/kernel.ts
  - ts/packages/ui/src/kernelenvelope.ts
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/README.md
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/support.ts
  - ts/packages/ui/test/service.test.ts
  - ts/packages/ui/test/argv-templates.test.ts
  - ts/packages/ui/test/kernel-runner.test.ts
  - ts/packages/ui/test/kernel-real.test.ts
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/test/fixtures/fake-kernel.mjs
  - ts/packages/ui/test/fixtures/serve-overrides.ts
- allowed_new_files:
  - ts/packages/ui/src/watch.ts
  - ts/packages/ui/src/events.ts
  - ts/packages/ui/src/jobs.ts
  - ts/packages/ui/src/jobroutes.ts
  - ts/packages/ui/test/events.test.ts
  - ts/packages/ui/test/events-service.test.ts
  - ts/packages/ui/test/jobs.test.ts
  - ts/packages/ui/test/jobs-service.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/package.json
  - ts/packages/ui/test/args.test.ts
  - ts/packages/base/**
  - ts/packages/cli/**
  - ts/packages/config/**
  - ts/packages/contracts/**
  - ts/packages/dispatcher/**
  - ts/packages/hub/**
  - ts/package.json
  - ts/bun.lock
  - ts/tsconfig.json
  - ts/vitest.config.ts
  - ts/tools/**
  - ts/mutations/**
  - scripts/**
  - desktop/**
  - docs/**
  - tests/test_gate_t017_*.py
  - tests/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - **SSE 路由**：路由名 `api.events`，方法 GET，路径 `/api/v1/events`，**不标 public**（照 T17 走会话检查，没有会话 cookie 回 401）。响应头由既有管线照常套上（CSP、nosniff、no-referrer、same-origin、`Cache-Control: no-store`），另加 `content-type: text/event-stream; charset=utf-8`。
  - **SSE 的报文格式**（每段以换行结尾，事件之间空一行）：流一打开先写 `retry: 3000` 与一个空行；每条事件写 `id: <序号>`、`event: snapshot` 或 `event: update`，再写若干行 `data: <信封正文的一行>`，最后一个空行。心跳是一行 `: hb` 加一个空行。`data` 的内容是把信封正文按行拆开、每行前面加 `data: `；前端按 SSE 规范拼回来的文本与 `/api/v1/status` 的正文去掉末尾换行后逐字节相同。
  - **SSE 的序号**：hub 内单调递增，服务启动后从 1 起。每产生一份**内容不同**的信封（按 data 文本比较）加 1；内容相同就不推、也不加序号。snapshot每次订阅（含重连）都是第一条，带当时的序号；update 之后每产生一份新内容推一条，推的是整份新信封（不做逐 attempt 的差分）。请求带 `Last-Event-ID` 也照样发 snapshot（重连不续传）。
  - **SSE 的 stat 名单**：根目录是 `<repo>/.agent/runs`。名单从 `@themis/contracts/status-inputs.json` 导入（见 A1），**禁止把名单抄进 ui 包**。占位符只认 `''`、`<task>`、`<attempt>`、`<n>` 四种；遇到不认识的占位或段就抛错让服务起不来（不悄悄跳过）。名单里的四类输入各按下列取法生成指纹：
    - `list ''`：列根目录，只收「是目录」且「不是重解析点」的条目名（`_env`、`_reports` 也算 task）。
    - `list '<task>'`：列每个 task 目录，只收名字匹配 `attempt_pattern`（`^attempt-\d{3,}$`）、是目录、又不是重解析点的条目；名字不是 attempt-NNN 的条目不进指纹（对应名单的 incidental_stat 那一条）。
    - `list '<task>/<attempt>/checks'`：列 checks 目录，只收名字匹配 `numbered_pattern`（`^\d{2,}(\.json|\.md)?$`）的条目（目录 01 或文件 01.json 都算）。
    - `list '<task>/<attempt>/verdicts'`：列 verdicts 目录，只收名字以 `.json` 结尾的条目（名单的 about 写着 verdicts 下的 `<n>.json` 是任意 .json）。
    - `exists '<task>/<attempt>/claim'`：在不在，两态。
    - `read` 与 `read_when_running` 的每一项：用 `stat(…, {bigint: true})` 取 size、mtimeNs、ino。`checks/<n>/checks.json` 只对 checks 下是目录的 `<n>` 取；`verdicts/<n>.json` 对 verdicts 列表里的每一项取；`read_when_running` 的两项（events.jsonl 与 run-started.json）对每个 attempt 都 stat（不读内容就判断不了在不在运行）。
  - **跳过链接与重解析点**：每一层的条目先过 `isReparsePoint`（复用 `src/static.ts` 导出的那一个），是重解析点就当它不存在，不进去也不 stat 它的目标。根目录本身是重解析点时，整轮指纹记成固定的一行 `root-reparse`，不再往里走。深度只到名单写的那几层，不递归。
  - **只认 attempt-NNN**：`_tmp` 下的变化、名单之外的文件（例如 attempt 下的 notes.txt、verdicts 下的 readme.txt）、服务自己的临时目录（在系统临时目录里，本来就不在 runs 下）都不进指纹。
  - **节奏、去抖与共享**：整个服务一个 EventHub。第一个订阅者到来时起 stat，每轮间隔 `STAT_INTERVAL_MS = 2000`（setTimeout 链，各轮不重叠）。某一轮发现指纹变了就排一次刷新，等 `DEBOUNCE_MS = 300` 再起 status；同一时刻最多一次 status 在跑，在跑期间又有变化就记一个 dirty 标记，跑完只补跑一次。一次 status 的结果交给全部订阅者（不按订阅者各跑一次）。status 走第 2 片的执行器（`runner.run(['status','--json'], 30, hub 的信号)`，与读路由共用同一个并发上限与队列）。遇到 queue-full 或 closing 不推送，记下 retryPending，下一轮即使指纹没变也重试；遇到 timeout，推出去的是超时信封（ok 为 false，与 `/api/v1/status` 的 504 正文同一份）。
  - **起与停**：订阅者减到 0 时停掉 stat、取消在跑的那次 status（中止 hub 自己的 AbortController）、丢掉缓存的快照与指纹；下一个订阅者到来时从头跑一次 status，不会拿到过期的快照。
  - **心跳与 retry**：`RETRY_MS = 3000`（比 stat 的 2 秒节奏长；服务给的等待时间是下限）；`HEARTBEAT_MS = 15000` 写一行 `: hb`。hub 用一个定时器给全部订阅者写，订阅者为 0 时停。这四个常量（2000、300、15000、3000）由一条单元测试钉住。
  - **断开与关停**：请求的 signal abort 与 ReadableStream 的 cancel 任一发生，就摘掉这个订阅者；写入失败（客户端消失）同样摘掉并关流（不依赖 Bun 的 request.signal 语义，心跳写失败这条路就够了）。服务关停时 `hub.close()`：关掉全部流、清全部定时器、中止在跑的 status；`server.ts` 的 shutdown 里在 `runner.shutdown()` 之前调它。
  - **Bun 的连接空闲超时**（站主拍板 B）：SSE 订阅时对**这一条请求**调 `server.timeout(req, 0)`，只关掉这条连接的空闲超时；**全局 `idleTimeout` 保持缺省，不设 30**（服务端写数据不重置空闲计时，设 30 秒照样断）。做法：`server.ts` 的 `Bun.serve` 的 fetch 第二个参数就是 server，收到 `GET /api/v1/events` 的请求时对它调 `timeout(request, 0)`；其余请求不动；全局 idleTimeout 只有测试入口能覆盖（`ServeOverrides.bunIdleTimeoutSeconds`），生产路径不设。客户端消失靠心跳写失败释放；关停时照旧全部结束。
  - **SSE 的连接上限**（站主拍板，数值规划端定）：全局同时开着的订阅数上限 `MAX_SUBSCRIPTIONS = 16`，同一个会话的订阅数上限 `MAX_SUBSCRIPTIONS_PER_SESSION = 4`。两个数只由测试入口 `ServeOverrides.maxSubscriptions` 与 `ServeOverrides.maxSubscriptionsPerSession` 覆盖（CLI 与环境变量碰不到），缺省就是 16 与 4。订阅时先查上限：全局满了或这个会话的订阅数满了，就**不建订阅**，回 **503** 并带 `Retry-After: 2`，正文是服务自己的错误信封（`ok` 为 false、`exit_code` 为 null、`data` 为 null、`output` 与 `command` 是空数组、`messages` 一行 `ERROR: SSE 订阅数已达上限`；会话级的那条写 `ERROR: 该会话的 SSE 订阅数已达上限`）。**不挤掉已有的订阅**：已有的流照旧开着、心跳照旧写、已有的推送照旧收到。上限数的是「同时开着的订阅」，任何一条订阅关掉（客户端断开、心跳写失败、会话作废、关停）都立刻把名额还给计数。
  - **SSE 的主动断开**：下列四种情况一律主动关流并清掉各自的定时器（这个订阅者的心跳定时器与清理句柄），全局与该会话的订阅计数同时减一：
    1. **会话作废**：hub 在每一次心跳与每一次推送之前查 `Sessions.valid(token)`（见 A11、A4），一旦为 false 立刻关流。服务里会话没有按时间的过期，会话作废就是 `revokeAll` 之后 `valid` 为 false，所以发现作废的最坏延迟不超过一个心跳间隔（心跳间隔可由测试入口缩短，见 A2 的 `ServeOverrides.heartbeatMs`）。
    2. **控制令牌换发引导地址**：`control.bootstrap` 校验通过后调 `sessions.revokeAll()`，旧会话当场作废（见 A11），走上一条同一段判定代码，这个会话名下的订阅一并关掉。
    3. **服务关停**：`hub.close()` 关掉全部流、清全部定时器、中止在跑的 status；`server.ts` 的 shutdown 里在 `runner.shutdown()` 之前调它（见 A12）。
    4. **空闲退出**：空闲计时器到期、服务决定退出之前，先 `hub.close()` 再退出，订阅不留到进程结束之后。
  - **SSE 的心跳写失败**：给某个订阅者写心跳失败（客户端已经走了）就**立刻**清理这个订阅者——清掉它的定时器、关掉它的流、把全局与该会话的订阅计数各减一，**不等空闲超时**（这条连接的超时早就关掉了）。写失败这条路与请求 signal 的 abort 是两条独立的释放路径，两条都要能把名额还回去。
  - **订阅算活动**：只要还有订阅开着，空闲计时器就 `touch()`，服务不会因为没人点页面而退出（与下面「空闲退出」那条一致）。
  - **空闲退出**：server.ts 的 IdleTimer 回调改成——inflight 为 0、hub 的订阅者为 0、作业表里没有在等或在跑的作业，三者都满足才退出；否则照旧 `timer.touch()`。订阅开着就算活动，不算空闲。
  - **作业路由**：
    - `POST /api/v1/jobs`（`api.jobs.create`）：要会话、CSRF 三查、JSON 正文（正文必须是 JSON 对象），都走既有管线。
    - `GET /api/v1/jobs/<id>`（`api.jobs.get`）：要会话。
    - `POST /api/v1/jobs/<id>/cancel`（`api.jobs.cancel`）：要会话与 CSRF，正文必须是 JSON 对象（可以是空对象 `{}`）。
    - 路径里的 `<id>` 不是 43 位 base64url（`^[A-Za-z0-9_-]{43}$`），或者表里没有，一律回 404「没有这个作业」，两种情况的响应相同（不泄露作业号在不在）。
  - **作业的严格参数校验**（每一类失败都回 400，提示固定，不回显请求里的值，不起子进程）：
    - 正文不是 JSON 对象（数组、null、字符串、数字）→ 400。
    - 没有 kind、kind 不是字符串、kind 不在六个之内 → 400。
    - 键必须恰好是该 kind 的键：多一个未知键 → 400；少一个必填键 → 400。
    - 类型不对（字符串字段给了数字、数组或 null；max 给了布尔、小数或字符串）→ 400。
    - 取值规则：record 匹配 `PLAN_KEY_RE`；runtime 与 task 匹配 `TASK_ID_RE`；max 是 1 到 1000 的整数；pattern 是 1 到 512 个码点，不含 U+0000–U+001F 与 U+007F，不含孤立的代理项。不满足任何一条 → 400。
    - pattern 的正则语法不由服务校验：语法错由内核报，作业终态是失败，消息照 messages 的规则过滤。
  - **六个 kind 的 argv 模板与时限**（argv 交给执行器，前面由执行器补上 python、kernel、`--repo`、仓库）：

    | kind | 正文的键 | argv | 时限（秒） |
    |---|---|---|---|
    | doctor | kind | `config doctor --json` | 600 |
    | doctor-record | kind、record | `config doctor --record=<record> --json` | 600 |
    | runtime-scan | kind | `config runtime scan --json`（不带 `--add` 与 `--yes`） | 150 |
    | runtime-probe | kind、runtime | `config runtime probe <runtime> --json` | 150 |
    | models | kind、runtime | `config models <runtime> --json` | 120 |
    | search | kind、pattern；可选 task、max | `logs search --json [--task=<task>] [--max=<max>] -- <pattern>` | 180 |

    时限的来历见 A8。位置参数（record 以外的 runtime 等）都由正则保证不以 `-` 开头；选项的值一律写成 `--opt=值`；search 的 pattern 是唯一放在 `--` 后面的参数。`JOB_ARGV` 登记表（填示例值：record 用 `demo-task.v1`、runtime 用 `demo-runtime`、task 用 `demo-task`、max 用 50、pattern 用 `token`）供真内核用例与替身用例逐条对照，写法照 `READ_ROUTE_ARGV`；**JOB_ARGV 另立一张表、另立一条 describe，不并进 `READ_ROUTE_ARGV` 的既有断言**（既有断言要求每个以 `--` 开头的项都含 `=`，而 `--` 分隔符不含 `=`；且位置参数不许以 `-` 开头，而 pattern 可以是 `-x`）。测试入口的 `timeouts` 里，作业用 `job.<kind>` 作键覆盖时限。
  - **作业的结果与白名单**：结果是第 2 片的七字段信封。data 是 stdout 的 JSON 过 `redactJson(data, 该 kind 的白名单)`；messages 只留 stderr 里以 `ERROR` 与 `WARN` 开头的行，逐行过 `redactSecrets`；command 是显示用的 argv（search 的 pattern 也过 `redactSecrets`）。`JOB_ALLOW` 登记表恰好六项、全是 undefined（**六类作业的结果一律不登记白名单，一律遮**）：doctor 与 doctor-record 的输出里有按名字取值的映射、形状没有逐字核对过；runtime-scan、runtime-probe、models 的键名都不是敏感键；search 的结果是证据内容，证据永远不进白名单。以后要登记必须改合同。退出 0 而 stdout 不是合法 JSON → 失败，reason 为 `invalid-json`。
  - **作业表**（`src/jobs.ts` 的 JobTable）：作业号是 `crypto.randomBytes(32)` 转 base64url，43 个字符（与 cursors 的句柄同一种写法），随机、不可猜，不含序号或时间。容量 `MAX_JOBS = 100`；插入时满了就淘汰最早结束的终态作业；表里没有终态作业可淘汰时回 503 并带 `Retry-After: 2`（实际上在等加在跑的作业最多只有执行器的 4 加 16 个，100 个满表时总有终态的可以淘汰）。创建之前先看执行器还能不能收（`KernelRunner` 加一个 `canAccept()`：在跑的少于上限，或者队列没满），收不了就回 503 并带 `Retry-After: 2`，不建作业。作业只在内存里，服务退出就丢，不写 `.agent/`。
  - **状态机与四种终态**：状态从 queued 到 running，再到下面四种终态之一，每一步只走一次——`succeeded`（退出码 0）、`failed`（退出码非 0，reason 为 `exit`；服务这一侧出错也记 failed，reason 为 `spawn-error`、`output-too-large`、`invalid-json` 或 `closing`）、`cancelled`、`timed_out`。queued 变 running 靠执行器通知：`RunKernel.run` 加一个可选的第 4 个参数 `hooks.onStart`，读路由不传。结果来自 RunOutcome：completed 且退出 0 → succeeded；completed 且退出非 0 → failed（exit）；timeout → timed_out，信封是 `timeoutEnvelope`（data 为 null，messages 只有「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」这一行）；interrupted 并且是用户取消 → cancelled，信封为 null。**search 在平方级耗时的脱敏输入上卡住时，终态必须是 timed_out**，不能记成 failed 或 succeeded，也不能带出任何匹配。`GET /api/v1/jobs/<id>` 返回 `{id, kind, state, reason, created_ms, started_ms, finished_ms, envelope}`，envelope 是那份已经脱敏的七字段信封。
  - **取消**：每个作业有自己的 AbortController（作业比创建它的 POST 请求活得久，不用请求的 signal）。cancel 时：在排队 → 执行器出队、不起子进程，终态 cancelled；在跑 → 中止信号，`runSupervised` 先发 CTRL_BREAK、宽限 2 秒、再 terminateJob，整棵树结束，终态 cancelled；已经是终态 → 回 409「作业已经结束」。服务关停时没结束的作业由 `runner.shutdown()` 结束子进程树，作业表随进程消失。
  - **加固 H1（输出上限边写边看，`src/kernel.ts`）**：子进程跑着的时候，每 `OUTPUT_POLL_MS = 100` 毫秒用 `statSync` 看 stdout.txt 与 stderr.txt 的大小；任一超过上限就记 overflow = true，并中止这次运行自己的 controller（`runSupervised` 照中断处理，整棵树结束）；结束后**先判 overflow 返回 output-too-large，再判 timed_out 与 interrupted**；保留结束后的那次检查（两次轮询之间就写完退出的情况也要兜住）；轮询定时器在 `finally` 里清掉。磁盘的上界大约是上限加上写速度乘以（轮询间隔加 2 秒宽限），写进 README 的已知限制。
  - **加固 H2（真内核拒绝越界路径）**：file 路由的 path 给 `../x`、`C:/x`、`a/../../x` 时，过了服务自己的校验、由内核拒绝：200 信封，`ok` 为 false，`exit_code` 为 2，`data` 为 null，正文不含夹具仓库之外金丝雀文件的内容；`..\x` 由服务自己回 400（反斜杠），同一条用例一起写明。
  - **加固 H3（关停时清空队列并摘监听，`src/kernel.ts`）**：shutdown 清队列时，对每个被清掉的条目调用它的 release（同时摘掉请求 signal 上的 onRequestAbort 与关停 signal 上的 onShutdown），再交代 closing。`release` 现在是 `run()` 里的局部闭包，要挂到 Entry 上（Entry 上存 release）关停时才摘得到。
  - **D11/D12 的抖动（`test/harness.ts` 与 `test/service.test.ts`）**：`chunkedWatch` 改成两段——先分块发到正文累计 65537 字节（8 块 8192 再加 1 块 1 字节），每块之间用 setTimeout 让出 5 毫秒；然后停下来，不发余下的块，也不发结尾的 0 块，等服务的响应头，最多等 20 秒；返回 `heldBack`（停发时收到了头）、`sent`（实际发出的正文字节数）与响应。断言强度不降：D11 仍断言 413、`early` 为真、`sent` 小于 total；另加 `heldBack` 为真（结尾块没发，服务不可能已经读完正文，所以「413 在读完之前回来」不再取决于机器快慢）。ECONNRESET：头已经收齐之后收到的 error（ECONNRESET、EPIPE）照收到的响应算；头没到就出错，照旧判失败，不放宽。客户端停发之后不再写，就不会在服务关连接之后再写；只发恰好越过上限的字节，尽量不让服务关连接时还有没读走的数据。D12 的 413-chunked 样本照旧用改过的 chunkedWatch；另加一个声明 Content-Length 65537 的 413 样本，两种 413 都要带同一套安全头。
- 边界输入：
  - 作业的六类参数不合格一律 400，不起子进程（见上面的校验清单）；`<id>` 格式不对与不在表里回同一个 404。
  - SSE 订阅时没有会话 cookie → 401；有会话但会话已被 `revokeAll` 作废 → 流被关掉（推送前查 `sessions.valid`）。
  - SSE 订阅数达到上限（全局 16 或该会话 4）→ 503 带 `Retry-After: 2`，不建订阅、**不挤掉已有的订阅**（已有的流照旧开着并继续收心跳）。
  - 心跳写失败（客户端已经走了）→ 立刻清理：全局与该会话的订阅计数各减一、该订阅者的定时器清掉、流关掉，不等空闲超时。
  - 内核退出非 0：作业终态是 failed，reason 为 exit，信封 `ok` 为 false、`exit_code` 原样。
  - 作业表满且没有终态作业可淘汰 → 503 带 `Retry-After: 2`；执行器收不了 → 503 带 `Retry-After: 2`，且不建作业（GET 查不到这个作业号）。
  - stdout 上限 32 MiB、stderr 上限 1 MiB：超限回 500（读路由）或作业终态 failed（reason 为 output-too-large），临时子目录照样删掉。
- 错误与重试：
  - HTTP 状态与错误信封的对应：400 参数不合格；401 未认证；404 没有这个接口或没有这个作业；409 作业已经结束（取消一个已结束的作业）、句柄无效或文件已变化；413 请求体超过 64 KiB；415 不是 JSON 的媒体类型；500 起不了子进程、要 JSON 的命令退出 0 但 stdout 不是合法 JSON、输出超限、处理函数抛错；503 队列满或服务正在关闭或作业表满或 SSE 订阅数达到上限（都带 `Retry-After: 2`）；504 命令超时。
  - 超时（504）的信封：`ok` 为 false、`exit_code` 为 null、`command` 是显示用的 argv、`messages` 只有一行「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」、`data` 为 null、`output` 为空数组。SSE 推的 timeout 信封与它同一份。
  - 服务自己产生的错误一律是 `errorResponse` 的形状（ok 为 false、exit_code 为 null、data 为 null、output 与 command 是空数组、messages 一行 `ERROR: …`）。
  - 服务不重试任何请求；SSE 的 retry 只由 `retry: 3000` 告诉客户端。SSE 订阅被拒（503）时客户端按 `Retry-After: 2` 的下界再来。
- 并发、取消与状态变化：
  - 同时最多 4 个内核子进程在跑，FIFO 队列最多 16 个在等；队列满回 503 并带 `Retry-After: 2`。作业与读路由共用这一个执行器与它的并发上限。
  - SSE 的 status 最多一次在跑；同一时刻最多一次 status；去抖 300 毫秒；在跑期间再来变化只补跑一次。
  - SSE 同时开着的订阅全局最多 16 个、每个会话最多 4 个；超限时新的订阅请求回 503 带 `Retry-After: 2`，**不挤掉已有的订阅**。
  - 客户端断开（请求的 signal abort、流被 cancel、或心跳写失败）→ 摘掉这个订阅者、把它的心跳定时器清掉、全局与该会话的订阅计数各减一；订阅者降到 0 就停 stat。
  - 会话作废（`revokeAll` 之后 `valid` 为 false，含换发引导地址那条路）→ 该会话名下的订阅主动关流并清定时器。
  - 服务关停 → 先关 hub（全部流、全部定时器、在跑的 status），再 `runner.shutdown()`（拒绝新请求、清空队列、取消在跑的、删临时根目录）。空闲退出走同一条路（先 `hub.close()` 再退出）。
  - 作业取消在跑时结束整棵进程树（CTRL_BREAK，宽限 2 秒，之后 terminateJob）。
  - 会话、nonce、句柄表、作业表、并发计数都在内存里，进程结束即丢；`ServeOverrides` 的 `maxConcurrent`、`maxQueue`、各路由时限覆盖、`statIntervalMs`、`debounceMs`、`heartbeatMs`、`bunIdleTimeoutSeconds`、`maxSubscriptions`、`maxSubscriptionsPerSession` 与 `job.<kind>` 时限覆盖只给测试入口，CLI 与环境变量碰不到。
- 兼容性：
  - 握手行、引导地址路径、会话 cookie 名、控制头名、信封七字段与次序、第 1、2 片的 HTTP 状态码都不改。
  - `/api/v1/status` 的响应正文与本片改动前逐字节一致（既有用例不许改）。
  - `ts/packages/ui/src/main.ts` 的 `UiArgs` 不改；`serveUi` 的 `ServeOverrides` 只增不减（新增项一律可选、缺省有值）。
  - `ts/packages/ui/package.json` 不改；新模块之间用仓库内相对路径引入。

## Steps
1. 预检（只读）：核对 Repository facts 里的签名与形状；跑 `python -m pytest tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py -q` 确认基线绿；确认 `bun install --frozen-lockfile` 装好。不符即停并报告。
2. 执行器加固（改 `src/kernel.ts`）：H1 的边写边看轮询（`OUTPUT_POLL_MS = 100`）、overflow 先于 timed_out 与 interrupted 判定、结束后那次检查保留、轮询定时器在 finally 里清掉；H3 把 `release` 挂到 Entry 上、shutdown 清队列时逐个调用；加 `canAccept()`；`RunKernel.run` 加可选的第 4 个参数 `hooks.onStart`（读路由不传）。配套用例写在 `test/kernel-runner.test.ts`（洪泛输出 10 秒内得到 output-too-large、孙进程也不在了；关停后监听器为 0，事后 abort 不会再次交代结果）。
3. 替身扩展（改 `test/fixtures/fake-kernel.mjs`）：加 `FAKE_KERNEL_PLAN`（按 argv 前缀给行为：sleep、hang、flood（洪泛输出）、spawn-grandchild（起孙进程并写 pid 文件）、按文件给 status 输出）；既有的 `FAKE_KERNEL_JSON`、`FAKE_KERNEL_STDERR`、`FAKE_KERNEL_EXIT`、`FAKE_KERNEL_SLEEP_MS` 与报告行格式保持不变（既有用例靠它们）。
4. 抖动（改 `test/harness.ts` 与 `test/service.test.ts`）：`chunkedWatch` 改成两段式并返回 `heldBack` 与 `sent`；D11 加 `heldBack` 断言；D12 加 Content-Length 65537 的 413 样本；ECONNRESET 的判定按 Behavior contract（头到之后不算失败、头到之前照旧判失败）。
5. 越界路径（改 `test/kernel-real.test.ts`）：加 H2 那条（`../x`、`C:/x`、`a/../../x` 由内核拒绝、`..\x` 由服务回 400）。
6. 监视器（新建 `src/watch.ts`）：从 `@themis/contracts/status-inputs.json` 导入名单（见 A1 的两种写法），按 Behavior contract 的四类取法生成指纹，跳过重解析点与链接，只认 attempt-NNN，fs 一律用 node:fs/promises 的异步调用且各轮不重叠。单元用例写在 `test/events.test.ts`。
7. 广播（新建 `src/events.ts` 的 EventHub）：起停、去抖、共享、序号、心跳、retry、会话检查、关停；**连接管理**：全局 16 个与每会话 4 个的上限（超限不建订阅、由路由回 503 带 `Retry-After: 2`）、会话作废时主动关流、心跳写失败时立刻清理（清定时器、关流、计数各减一）、关停时关掉全部流并清全部定时器。单元用例写在 `test/events.test.ts`。
8. 共用 status 信封（改 `src/kernelenvelope.ts` 与 `src/readroutes.ts`）：把 `/api/v1/status` 的信封正文拼装抽成一个共用函数（`/api/v1/status` 与 SSE 都调它），SSE 的 data 由它产出；`/api/v1/status` 的响应正文逐字节不变，既有断言不许改。SSE 路由新建 `src/eventroutes.ts`（或放在 `src/events.ts` 里），**不并进 `readRoutes()`**。
9. 作业表（新建 `src/jobs.ts`）：作业号、容量与淘汰、四种终态、状态机、取消。
10. 作业路由（新建 `src/jobroutes.ts`）：四条校验规则、`JOB_ARGV`、`JOB_TIMEOUTS`、`JOB_ALLOW`（恰好六项、全是 undefined）；**不并进 `readRoutes()`**。
11. 接线（改 `src/server.ts` 与 `test/fixtures/serve-overrides.ts`）：建 hub 与作业表，把 `readRoutes`、`eventRoutes`、`jobRoutes` 三批 extraRoutes 合成一批交给 `createApp`；SSE 请求调 `server.timeout(request, 0)`（只这一条连接），全局 idleTimeout 生产路径不设、只由 `ServeOverrides.bunIdleTimeoutSeconds` 覆盖；空闲判定加上「订阅者为 0 且没有在等或在跑的作业」（订阅开着算活动）；关停次序 hub.close() 在 runner.shutdown() 之前，空闲退出也先 hub.close()；`ServeOverrides` 加 `statIntervalMs`、`debounceMs`、`heartbeatMs`、`bunIdleTimeoutSeconds`、`maxSubscriptions`（缺省 16）、`maxSubscriptionsPerSession`（缺省 4），全部可选、只增不减。
12. 测试（新建 `test/events.test.ts`、`test/events-service.test.ts`、`test/jobs.test.ts`、`test/jobs-service.test.ts`；改 `test/argv-templates.test.ts`、`test/kernel-runner.test.ts`、`test/kernel-real.test.ts`、`test/routes-auth.test.ts`、`test/support.ts`）：逐条对上下面「覆盖矩阵」里的用例（含 U18–U21 的 SSE 连接管理四条）。ui 测试目录里不许出现 skip、only、todo。
13. 文档（改 `ts/packages/ui/README.md`）：写新路由、SSE 报文格式与序号规则、**SSE 订阅上限（全局 16、每会话 4）与超限时的 503 带 `Retry-After`、会话作废与关停时主动关流、心跳写失败的清理**、作业的 kind/argv/时限/终态/取消/容量、状态码（409、503 带 Retry-After、504）、已知限制（H1 的磁盘上界、SSE 的 stat成本、作业表只在内存），并逐字保留 D13 那几段与 T016 钉住的那几段（见 A10）。README 里要出现「订阅上限」四个字（V08 按这条查）。
14. 稳定性验收：把 `test/service.test.ts` 单跑 20 次（V09），再把全量 vitest 跑 3 遍（V10），都通过。
15. 跑 Validation commands 中与改动相关的检查；确认 `git status --porcelain --untracked-files=all` 只出现允许范围内的路径；写执行报告；遇到合同未定义的行为，停止并报告。

基准测试文件清单（门禁端据此锁定；执行端不许删改既有用例）：

- `ts/packages/ui/src/watch.ts`（新）
- `ts/packages/ui/src/events.ts`（新）
- `ts/packages/ui/src/jobs.ts`（新）
- `ts/packages/ui/src/jobroutes.ts`（新）
- `ts/packages/ui/test/events.test.ts`（新）
- `ts/packages/ui/test/events-service.test.ts`（新；追加 U18–U21 的 SSE 连接管理用例：上限、主动断开、心跳写失败清理、订阅算活动）
- `ts/packages/ui/test/jobs.test.ts`（新）
- `ts/packages/ui/test/jobs-service.test.ts`（新）
- `ts/packages/ui/test/harness.ts`（既有，追加 chunkedWatch 两段式与 SSE 客户端辅助）
- `ts/packages/ui/test/support.ts`（既有，追加起 hub/作业表的应用辅助与订阅计数的心跳写失败替身客户端）
- `ts/packages/ui/test/service.test.ts`（既有，追加 D11 的 heldBack 断言与 D12 的 Content-Length 413 样本）
- `ts/packages/ui/test/argv-templates.test.ts`（既有，追加 JOB_ARGV 过真内核解析器与 4.4 的四个 pattern）
- `ts/packages/ui/test/kernel-runner.test.ts`（既有，追加 H1、H3、canAccept 与 hooks.onStart）
- `ts/packages/ui/test/kernel-real.test.ts`（既有，追加 H2 与 U10 的真内核那条）
- `ts/packages/ui/test/routes-auth.test.ts`（既有，追加新路由不带 cookie 一律 401 的新表）
- `ts/packages/ui/test/fixtures/fake-kernel.mjs`（既有，追加 FAKE_KERNEL_PLAN）
- `ts/packages/ui/test/fixtures/serve-overrides.ts`（既有，追加新覆盖项：statIntervalMs、debounceMs、heartbeatMs、bunIdleTimeoutSeconds、maxSubscriptions、maxSubscriptionsPerSession）
- `ts/packages/ui/README.md`（既有，追加新路由、订阅上限与限制）

覆盖矩阵（用例文件 → 断言的内容）：

- **U17**（`test/events-service.test.ts`，替身 status 读夹具文件，stat 用导入的名单，在真实的文件变化上测）：订阅后第一条是 snapshot（state 为 RUNNING）；断开连接；改 attempt 的 state.json 与替身的 status 输出（变成 NEEDS_REVIEW）；重连后第一条是 snapshot，state 为 NEEDS_REVIEW，序号大于断开之前的。再加一条：带 Last-Event-ID 重连，第一条仍是 snapshot。
- **U18（订阅上限）**（`test/events-service.test.ts`）：把全局上限覆盖成 2，开 2 条订阅都成功，第 3 条回 503、`Retry-After: 2`、正文是错误信封（`ok` 为 false、`exit_code` 为 null、`data` 为 null、`messages` 一行 `ERROR: SSE 订阅数已达上限`），并且**已有的两条订阅照旧开着、照旧收到心跳**（不挤掉）；把每会话上限覆盖成 1，同一个会话的第 2 条回 503、正文是 `ERROR: 该会话的 SSE 订阅数已达上限`，另一个会话的第 1 条仍然成功；关掉一条之后名额还回来，再订阅成功。
- **U19（主动断开）**（`test/events-service.test.ts`）：订阅开着时调 `sessions.revokeAll()`（会话作废，含换发引导地址那条路：走 `POST /control/bootstrap` 换引导地址后旧会话作废），该订阅的流在一个心跳间隔内被关掉（心跳间隔由 `ServeOverrides.heartbeatMs` 覆盖到 200 毫秒来观察）、订阅计数归零、心跳定时器清掉。
- **U20（心跳写失败即清理）**（`test/events-service.test.ts`）：替身客户端连上之后直接断开（不发 abort），服务下一次写心跳失败 → 立刻清理：这个订阅者的流被关掉、订阅计数（全局与该会话）各减一归零、它的心跳定时器被清掉（此后不再有写心跳的动作）。
- **U21（订阅算活动）**（`test/events-service.test.ts`）：把空闲时限覆盖成很短，服务里有订阅开着时空闲时限到了也不退出（`/api/v1/ping` 仍回 200）；把订阅全部断开之后，空闲时限到了服务才退出。
- **U9 的 SSE 一半**（`test/events-service.test.ts`）：file 路由的子进程超时期间与之后，SSE 照常收到心跳与 update，`/control/bootstrap` 照常回 200。
- **U10**（`test/jobs-service.test.ts` 用替身，`test/kernel-real.test.ts` 用真内核）：doctor 作业被取消，以及超时：替身起孙进程，事后用 pidAlive 证明孙进程也不在了，终态分别是 cancelled 与 timed_out。search 作业：替身卡住，以及真内核在 3.2 万字符的 tokentoken 证据上跑、时限覆盖成 2 秒：终态都是 timed_out，没有匹配，messages 是超时那一行。期间与之后 SSE、`/control/bootstrap`、`/api/v1/ping` 与一条读路由照常响应。
- **T3 的各条**（`test/events.test.ts` 与 `test/events-service.test.ts`）：名单之外的变化不触发（`_tmp/x`、`<attempt>/notes.txt`、`verdicts/readme.txt`、非 attempt-NNN 的目录）；名单上的变化触发（checks 下新增 02/checks.json、verdicts 下新增 1.json、claim 出现、events.jsonl 变长）；junction 不跟随（在 runs 下建一个指向外部目录的 junction，往外部目录写东西不触发）；多个订阅者共用一次 status（3 个订阅者，改一次文件，报告里只记到 1 次 status）；去抖（2 秒内写 20 次文件，status 不超过 2 次）；没有订阅者就停（全部断开之后改文件，没有 status 被起）；订阅时起（第一个订阅者到来才起第一次 status）；心跳（缩短心跳间隔之后收到注释行）；retry 一行恒为 3000；推送的 data 拼回来之后与 `/api/v1/status` 的正文逐字节一致；会话：不带 cookie 回 401，revokeAll 之后流被关掉；四个常量（2000、300、15000、3000）被钉住。
- **Bun空闲超时**（`test/events-service.test.ts`）：测试入口把全局 idleTimeout 设成 2 秒、心跳设成 500 毫秒，订阅保持 6 秒以上并收到至少 6 次心跳；另加一条：同一服务上非 SSE 的空闲 keep-alive 连接仍在约 2 到 4 秒内被关（证明没有改全局）。
- **作业**（`test/jobs.test.ts` 与 `test/jobs-service.test.ts`）：4.2 的每一类失败各一例，都回 400，且没有起子进程；六个 kind 交给执行器的 argv 与 `JOB_ARGV` 逐条一致；作业号是 43 位、彼此不同、不连号；不在表里与格式不对的回同一个 404；101 个作业之后最早结束的终态作业被淘汰；没有可淘汰的时回 503 带 Retry-After；取消排队中的不起子进程；取消已结束的回 409；四种终态各一例；`JOB_ALLOW` 恰好六项、全是 undefined；doctor 输出里带敏感键的值被遮成 `<redacted>`；执行器收不了时回 503 且不建作业。
- **真内核解析器**（`test/argv-templates.test.ts`）：`JOB_ARGV` 逐条过内核真正的解析器（照 U4 的做法；`--` 分隔符与以 `-` 开头的 pattern 走这条 describe 自己的断言，不走既有那条「每个 `--` 项都含 `=`」的断言），加上 4.4 的四个 pattern（`-x`、`--json`、`--`、`-1`）逐个断言解析出的 pattern 与原值相等、json 为真、task 与 max 照传；再加一条走完整的 pi_dispatch 转发：在 git 夹具仓库上跑 `logs search --json -- -x`，退出码 0、stdout 是合法 JSON。
- **加固**：H1（kernel-runner 用例，替身洪泛输出，上限 1 MiB，时限 60 秒，10 秒内就得到 output-too-large，事后孙进程也不在了）；H2（kernel-real 的越界路径用例）；H3（kernel-runner 用例，用一个会数监听器的 EventTarget 当请求的 signal，排队中的条目经过关停之后监听器为 0，事后再 abort 也不会再次交代结果）。
- **抖动**：D11 与 D12 照第 6 节的写法与验收。

变异清单（每条都要有会变红的用例；U编号只是用例编号，不进任何证据字段）：

- M1：订阅后不先发 snapshot（直接等变化）→ U17、订阅时起的那条。
- M2：重连时续传、不发 snapshot（照 Last-Event-ID 续）→ U17 的 Last-Event-ID 那条。
- M3：名单之外的变化也进指纹（`<task>` 那一层不过滤 attempt_pattern；verdicts 不过滤 .json；不跳过 `_tmp`）→ 名单之外不触发的那条。
- M4：跟随重解析点 → junction 那条。
- M5：每个订阅者各跑一次 status → 共用一次的那条。
- M6：没有订阅者也不停 stat → 没有订阅者就停的那条。
- M7：不去抖（每轮都跑，或在跑期间又起一次）→ 去抖那条。
- M8：心跳缺失（不发，或间隔乘以 10）→ 心跳那条与 Bun 空闲超时那条。
- M9：retry 一行缺失或小于 3000 → retry 那条。
- M10：SSE 不查会话或不再验证（标成 public，或 revokeAll 之后不关流）→ routes-auth 那条与会话那条。
- M11：SSE 推送的信封不过 redactJson → 与 `/api/v1/status` 逐字节一致的那条（夹具里带一个敏感键）。
- M12：作业参数校验，每一类各一个变异：接受未知键、不查必填、不查类型、不查 record 的格式、不查 runtime 的格式、max 不查范围、pattern 不查控制字符、pattern 不查长度、kind 不在六个之内也接受 → 对应的 400 用例。
- M13：search 的模板去掉 `--` → 4.4 的真内核用例（pattern 为 `--json` 或 `-x` 时解析失败或被当成选项）。
- M14：搜索超时记成失败（timeout 映射成 failed）→ U10 的 search 那条。
- M15：取消不结束进程树（cancel 只改状态、不中止信号）→ U10 取消用例里的孙进程检查。
- M16：作业表不淘汰（满了直接拒绝，或无限增长）→ 淘汰那条。
- M17：作业号可猜（自增或用时间）→ 作业号那条。
- M18：输出上限只在结束后查（去掉轮询）→ H1 洪泛那条（会拖到超时，得不到 output-too-large）。
- M19：关停时不摘监听（shutdown 不调 release）→ H3 那条。
- M20：空闲判定不看作业或订阅者 → 服务用例：有作业在跑时空闲时限到了也不退出；U21 的「订阅开着时不退出」那条。
- M21：不调 `server.timeout(req, 0)`（SSE 仍用 Bun 的默认空闲超时）→ Bun 空闲超时那条（全局设成 2 秒时订阅会被掐断）。
- M22：不设订阅上限（全局或每会话的上限不去查，来多少接多少）→ U18 的两条503 用例（第三条订阅会成功而不是 503）。
- M23：会话作废不断开（不查 `Sessions.valid`，或查了也不关流）→ U19 的会话作废那条（流不会被关掉）。
- M24：心跳写失败不清理（写失败只记日志，不清定时器、不关流、计数不减）→ U20 那条（订阅计数不会归零，定时器还在）。
- M25：关停与空闲退出时不关流、不清定时器（`hub.close()` 不关流，或关流顺序在 `runner.shutdown()` 之后）→ U21 与关停那条（关停后仍有订阅开着、心跳定时器还在跑）。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t017_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`bun install --frozen-lockfile` · cwd：ts · 超时：900s · 期望退出码：0
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V04（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V05（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0
- V06（必要）：`python -m pytest tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V07（必要）：`git status --porcelain --untracked-files=all` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：`ts/packages/ui/`，不得出现：`(?m)^\s*\S+\s+(?!ts/packages/ui/)`
- V08（必要）：`node -e "const fs=require('fs');const s=fs.readFileSync('packages/ui/README.md','utf8');const need=['events','jobs','Retry-After','409','503','504','config secret check','TYPESAFE_API_KEY','已知限制','131072','订阅上限'];const miss=need.filter((x)=>!s.includes(x));if(miss.length){console.error('README missing: '+miss.join(','));process.exit(1)}console.log('README ok')"` · cwd：ts · 超时：120s · 期望退出码：0 · 输出须匹配：`README ok`
- V09（必要）：`node -e "const {spawnSync}=require('child_process');for(let i=0;i<20;i++){const r=spawnSync(process.execPath,['node_modules/vitest/vitest.mjs','run','packages/ui/test/service.test.ts'],{stdio:'inherit'});if(r.status===0){continue}console.error('run '+(i+1)+' failed');process.exit(1)}console.log('STABLE20')"` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`STABLE20`
- V10（必要）：`node -e "const {spawnSync}=require('child_process');for(let i=0;i<3;i++){const r=spawnSync(process.execPath,['node_modules/vitest/vitest.mjs','run'],{stdio:'inherit'});if(r.status===0){continue}console.error('pass '+(i+1)+' failed');process.exit(1)}console.log('STABLE3')"` · cwd：ts · 超时：3000s · 期望退出码：0 · 输出须匹配：`STABLE3`

## 检查清单
合同里被引用的检查 id 只有下面这些。Definition of done 的「证据」字段只允许填这里定义的 id，不得填 U 编号，也不得填未定义的 id。

| id | 检查什么 | 命令（见 Validation commands） | 通过判据 |
|---|---|---|---|
| G01 | T017 的门禁基准测试（基线应失败；门禁端写好后由内核做成基线提交） | `python -m pytest tests/test_gate_t017_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| R01 | T001–T016 的门禁回归（基线应通过） | `python -m pytest tests/test_gate_t001_baseline.py … tests/test_gate_t016_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| V01 | 依赖按锁文件装好 | `bun install --frozen-lockfile`（cwd：ts） | 退出码 0 |
| V02 | ui 包自己的用例全过（本片新用例都在这里，含 U18–U21 的连接管理用例） | vitest `packages/ui/test`（cwd：ts） | 退出码 0 且输出匹配 `Tests[^\n]*[1-9]\d*[^\n]*passed` |
| V03 | 内核契约相关的三个用例文件全过 | vitest `packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts`（cwd：ts） | 同上 |
| V04 | 全量 vitest 全过 | vitest 全量（cwd：ts） | 同上 |
| V05 | 类型检查 | `tsc -p tsconfig.json`（cwd：ts） | 退出码 0 |
| V06 | T015/T016 门禁里与 README、读路由表、既有源文件相关的长期断言没破 | `python -m pytest tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py -q`（cwd：仓库根） | 退出码 0 且输出匹配 `\d+ passed` |
| V07 | 改动范围：只出现允许范围内的路径 | `git status --porcelain --untracked-files=all`（cwd：仓库根） | 只出现 `ts/packages/ui/` 下的路径 |
| V08 | README 写到了关键结论（新路由、SSE、订阅上限、作业、状态码与 D13/T016 钉住的那几段） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `README ok` |
| V09 | 稳定性：D11/D12 所在的 service.test.ts 单跑 20 次 | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `STABLE20` |
| V10 | 稳定性：全量 vitest 跑 3 遍 | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `STABLE3` |

## Definition of done
- D01：SSE 路由与鉴权——`GET /api/v1/events` 要会话（不带 cookie 一律 401），响应带 `content-type: text/event-stream; charset=utf-8`、既有那套安全头与 `Cache-Control: no-store`；用例：`ts/packages/ui/test/routes-auth.test.ts` 的新表与 `ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：SSE 是界面的实时通道，不能绕过会话。
- D02：SSE 的快照与序号——每次订阅（含重连）的第一条都是 snapshot 并带序号；序号从 1 起单调递增、内容相同不推不加号；重连后第一条仍是 snapshot 且序号大于断开之前；带 Last-Event-ID 重连也一样；用例：`ts/packages/ui/test/events-service.test.ts` 的 U17 那几条；证据：V02；目的：断线重连之后界面拿得到当前状态，而不是等着下一次变化。
- D03：SSE 推的内容与 `/api/v1/status` 一致——拼回来的 data 与 `/api/v1/status` 的正文（去掉末尾换行）逐字节相同，同一套脱敏（敏感键被遮成 `<redacted>`）；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：实时通道与轮询接口给界面的是同一份数据，脱敏口径也只有一套。
- D04：SSE 的心跳与 retry——流一打开先写 `retry: 3000`；每 15 秒写一行 `: hb`；四个常量（2000、300、15000、3000）由一条单元测试钉住；用例：`ts/packages/ui/test/events.test.ts`；证据：V02；目的：客户端知道该等多久，连着的连接不会因为静默被当成断了。
- D05：SSE 只 stat 名单上的输入——名单从 `@themis/contracts/status-inputs.json` 导入（一个字都不许抄进 ui 包）；名单之外的变化（`_tmp/x`、`<attempt>/notes.txt`、`verdicts/readme.txt`、非 attempt-NNN 的目录）不触发；名单上的变化（checks 下新增 02/checks.json、verdicts 下新增 1.json、claim 出现、events.jsonl 变长）触发；用例：`ts/packages/ui/test/events.test.ts` 与 `ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：服务只跟着内核的 status 输入走，名单改了监视自动跟上。
- D06：SSE 跳过链接与重解析点——runs 下的 junction 不跟随（往外部目录写东西不触发）；根目录本身是重解析点时整轮指纹是固定的一行；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：监视不许跑出 `.agent/runs/`。
- D07：SSE 的去抖与共享——2 秒内写 20 次文件，status 不超过 2 次；3 个订阅者改一次文件只跑 1 次 status；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：一阵连续写入只惊动内核一次，几个页面看的是同一份结果。
- D08：SSE 的起与停——第一个订阅者到来才起第一次 status；全部断开之后改文件没有 status 被起；关停时 hub 关掉全部流与定时器；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：没人看的时候别费机器。
- D09：SSE 的会话失效即断流——`revokeAll` 之后流被关掉；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：会话作废之后旧窗口不该继续收到推送。
- D10：Bun 的连接空闲超时——订阅时对这一条请求调 `server.timeout(req, 0)`，全局 `idleTimeout` 生产路径保持缺省；测试入口把全局设成 2 秒、心跳 500 毫秒时，订阅保持 6 秒以上并收到至少 6 次心跳；同一服务上非 SSE 的空闲 keep-alive 连接仍在约 2 到 4 秒内被关；用例：`ts/packages/ui/test/events-service.test.ts` 的 Bun 空闲超时那两条；证据：V02；目的：SSE 不会被 Bun 的默认空闲超时掐断，同时没有把全局的空闲保护一起放宽。
- D11：SSE 不拖慢别的接口——file 路由的子进程超时期间与之后，SSE 照常收到心跳与 update，`/control/bootstrap` 照常回 200（U9 的 SSE 一半）；用例：`ts/packages/ui/test/events-service.test.ts`；证据：V02；目的：一个慢命令不该把实时通道与控制接口一起拖住。
- D12：作业路由与鉴权——`POST /api/v1/jobs`、`GET /api/v1/jobs/<id>`、`POST /api/v1/jobs/<id>/cancel` 要会话；两个 POST 还要 CSRF 与 JSON 对象正文；不带 cookie 一律 401；用例：`ts/packages/ui/test/routes-auth.test.ts` 的新表与 `ts/packages/ui/test/jobs-service.test.ts`；证据：V02；目的：作业会起子进程，入口必须与别的路由一样验会话。
- D13：作业的严格参数校验——正文不是对象、kind 不对、键多一个或少一个、类型不对、record/runtime/task 的格式不对、max 不在 1–1000、pattern 超长或含控制字符，每一类都回 400 且不起子进程；用例：`ts/packages/ui/test/jobs.test.ts` 的每一类一条；证据：V02；目的：不合格的参数到不了内核，也回显不了攻击者给的值。
- D14：作业的 argv 与时限——六个 kind 交给执行器的 argv 与 `JOB_ARGV` 逐条一致；时限照表（doctor 与 doctor-record 600 秒、runtime-scan 150 秒、runtime-probe 150 秒、models 120 秒、search 180 秒）；用例：`ts/packages/ui/test/jobs.test.ts`（替身逐条对照 argv）与 `ts/packages/ui/test/argv-templates.test.ts`（真内核解析器）；证据：V02；目的：路由与内核的命令行一一对应，不靠猜。
- D15：pattern 用 `--` 传——`-x`、`--json`、`--`、`-1` 四个 pattern 过内核真正的解析器，解析出的 pattern 与原值相等、json 为真、task 与 max 照传；在 git 夹具仓库上跑完整的 `logs search --json -- -x` 退出码 0、stdout 是合法 JSON；用例：`ts/packages/ui/test/argv-templates.test.ts`；证据：V02；目的：以 `-` 开头的搜索词也要能传得进去。
- D16：作业表——作业号是 43 位随机、彼此不同、不连号；不在表里与格式不对的回同一个 404「没有这个作业」；101 个作业之后最早结束的终态作业被淘汰；没有可淘汰的终态作业时回 503 带 `Retry-After: 2`；执行器收不了时回 503 带 `Retry-After: 2` 且不建作业；用例：`ts/packages/ui/test/jobs.test.ts` 与 `ts/packages/ui/test/jobs-service.test.ts`；证据：V02；目的：作业号不可猜，内存里的表不会无限长。
- D17：作业的状态机与四种终态——succeeded、failed、cancelled、timed_out 各一例；search 在平方级耗时的脱敏输入上超时后终态是 timed_out（不是 failed 或 succeeded），messages 是超时那一行、data 是 null、没有匹配；用例：`ts/packages/ui/test/jobs-service.test.ts` 与 `ts/packages/ui/test/kernel-real.test.ts`；证据：V02；目的：读不出结果的作业要老实说超时，不能报成成功或失败。
- D18：作业的取消——取消排队中的作业不起子进程；取消在跑的作业结束整棵进程树（孙进程也不在了）；取消已经结束的作业回 409「作业已经结束」；用例：`ts/packages/ui/test/jobs-service.test.ts` 与 `ts/packages/ui/test/kernel-real.test.ts`；证据：V02；目的：取消要真的停掉机器上的活儿。
- D19：作业结果的脱敏与白名单——`JOB_ALLOW` 恰好六项、全是 undefined；doctor 输出里带敏感键的值被遮成 `<redacted>`；messages 只留 `ERROR`/`WARN` 开头的行并逐行过 `redactSecrets`；用例：`ts/packages/ui/test/jobs.test.ts`；证据：V02；目的：作业结果与读路由同一套二道脱敏，白名单不登记就是不登记。
- D20：H1 输出上限边写边看——替身洪泛输出、上限 1 MiB、时限 60 秒时，10 秒内就得到 output-too-large（不是拖到超时），事后孙进程也不在了；结束后那次检查仍兜住「两次轮询之间就写完退出」；轮询定时器在 finally 里清掉；用例：`ts/packages/ui/test/kernel-runner.test.ts`；证据：V02；目的：临时目录的磁盘也要有上界，不能等到进程结束才发现。
- D21：H2 越界路径由真内核拒绝——`../x`、`C:/x`、`a/../../x` 时是 200 信封、`ok` 为 false、`exit_code` 为 2、`data` 为 null、正文不含夹具仓库之外的金丝雀内容；`..\x` 由服务回 400；用例：`ts/packages/ui/test/kernel-real.test.ts`；证据：V02；目的：越界的兜底不只靠内核的说法，要有用例写明。
- D22：H3 关停清队列并摘监听——用一个会数监听器的 EventTarget 当请求的 signal，排队中的条目经过关停之后监听器为 0，事后再 abort 也不会再次交代结果；用例：`ts/packages/ui/test/kernel-runner.test.ts`；证据：V02；目的：关停之后不留悬挂的监听器。
- D23：D11/D12 的稳定化——`chunkedWatch` 两段式；D11 仍断言 413、`early` 为真、`sent` 小于 total，并加 `heldBack` 为真；D12 的两种 413（分块与声明 Content-Length 65537）都带同一套安全头；头已经收齐之后的 ECONNRESET 照收到的响应算，头没到就出错照旧判失败（不放宽断言）；用例：`ts/packages/ui/test/service.test.ts` 的 D11 与 D12；证据：V02、V09；目的：负载下也稳定，而且「413 在读完之前回来」这件事不再取决于机器快慢。
- D24：稳定性验收——D11、D12 所在的 `service.test.ts` 单跑 20 次、全量 vitest 跑 3 遍都通过；证据：V09、V10；目的：偶发红不能靠重跑蒙过去。
- D25：README 与门禁——README 补新路由、SSE 报文格式与序号规则、**SSE 订阅上限（全局 16、每会话 4）与超限时的 503 带 `Retry-After`**、作业的 kind/argv/时限/终态/取消/容量、状态码（409、503 带 Retry-After、504）、已知限制（H1 的磁盘上界、SSE 的 stat 成本、作业表只在内存），并逐字保留 D13 那几段与 T016 钉住的那几段；G01、R01、V01–V10 全部通过；改动只落在允许范围内的路径；既有用例未删未跳未弱化；M1–M25 每条都有会变红的用例；新增的四个源文件都能从 `main.ts` 顺 import 到达；证据：G01、R01、V01、V02、V03、V04、V05、V06、V07、V08、V09、V10、review；目的：不破坏已有门禁，也不靠削弱测试过关。
- D26：范围与依赖——依赖清单与锁文件未改（`dependency_changes: forbidden`）；没有新增、升级或删除任何依赖；`ts/packages/ui/src/localhttp/**` 一个字未改；证据：scope、review；目的：内核禁区与本机 HTTP 的安全基线不受本片影响。
- D27：SSE 的订阅上限——同时开着的订阅全局最多 16 个、同一个会话最多 4 个（两个数只由 `ServeOverrides.maxSubscriptions` 与 `ServeOverrides.maxSubscriptionsPerSession` 覆盖）；超限时新的订阅请求回 503、带 `Retry-After: 2`、正文是错误信封（`ok` 为 false、`exit_code` 为 null、`data` 为 null、`messages` 一行 `ERROR: SSE 订阅数已达上限`，会话级写 `ERROR: 该会话的 SSE 订阅数已达上限`），**已有的订阅不挤掉**（照旧开着、照旧收心跳）；关掉一条之后名额立刻还回来；用例：`ts/packages/ui/test/events-service.test.ts` 的 U18；证据：V02；目的：服务自己管住连接数，不会被一堆窗口撑爆，也不把别人的连接踢掉。
- D28：SSE 的主动断开——会话作废（`revokeAll` 之后 `valid` 为 false，含控制令牌换发引导地址那条路）、服务关停、空闲退出时，这些订阅一律被关流并清掉各自的定时器，订阅计数同时减一；用例：`ts/packages/ui/test/events-service.test.ts` 的 U19 与关停那条；证据：V02；目的：会话作废之后旧窗口不该继续挂着连接，服务退出时不留悬挂的流与定时器。
- D29：SSE 的心跳写失败立刻清理——写心跳失败（客户端已经走了）就清定时器、关流、订阅计数各减一，不等空闲超时；用例：`ts/packages/ui/test/events-service.test.ts` 的 U20（替身客户端直接断开，订阅计数归零、定时器清掉）；证据：V02；目的：走了的客户端要立刻把名额还回来，不能占着上限。
- D30：订阅算活动——有订阅开着时空闲计时器不退出（`timer.touch()`），订阅全部断开之后空闲时限到了才退出；用例：`ts/packages/ui/test/events-service.test.ts` 的 U21；证据：V02；目的：界面开着的时候服务不该自己跑掉。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 内核的解析器不认 `logs search --json -- <pattern>`（4.4 那条真内核用例红了）：停下报告，不许自己改成「以 `-` 开头一律 400」的方案。
- `@themis/contracts/status-inputs.json` 的导入方式在 tsc 下不被接受且运行时解析也不可用：停下报告，不许把名单抄进 ui 包。
- 实现「主动关流」或「心跳写失败清理」必须改动 `ts/packages/ui/src/localhttp/**` 或 Bun 的全局 `idleTimeout` 才能做成：停下报告（这两处是明确排除的），并在报告里写清卡在哪一步。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；本任务此前已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（已用 0 秒；= 3 倍单次时限）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：预检 300s、执行器加固与替身 600s、SSE（监视器、广播、连接管理、接线）1500s、作业（表、路由、状态机）1200s、抖动与补测 900s、必要检查（含稳定性验收）1000s、最终报告 200s；总计不超过单轮时限

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D30，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261024T154633569568Z-owner-89e061：

> 摘要: 规划端（本会话）核实了 3 条事实，第 2 条与规划的假设相反；据此第 9 节第 1 项改选 B，其余 4 项照建议。报告不用复制：留在信箱，合同端照常把合同写进 .agent/plans。
>
> 一、事实（规划端实测，本机 Python 3.12.10、Bun 1.4.2）
> 1. 成立。kit_logs.build_parser 解析 search --json -- -x、-- --、-- --json、--task t --max 5 -- -1，pattern 依次是 -x、--、--json、-1，json 为真，task、max 照传。
> 2. 后半句不成立：服务端写数据不会重置空闲计时。探针：Bun.serve 设 idleTimeout 2，SSE 流每 500 毫秒写一行心跳，Node 客户端收到 7 次心跳，连接照样在 4.0 秒被断开，与一个字也不写的流（3.98 秒断开）一样。流式响应可以长时间往外写这一半成立：同一条请求先调 server.timeout(req, 0)，8 秒不断，收到 15 次心跳。
> 3. 按 RFC 1122 4.2.2.13 成立：带未读数据关闭会发 RST。客户端丢掉没读走的数据这一半，是 Winsock 的常见表现，规划端没有实测。合同只写“响应头到了之后的 ECONNRESET 不算失败、仍要证明 413 先于读完”，不依赖这一半。
>
> 二、第 9 节（规划端代定）
> 1. 选 B，不选 A：订阅时对这条请求调 server.timeout(req, 0)，只关掉 SSE 连接的空闲超时；全局 idleTimeout 保持缺省，不设 30。A 不成立：心跳不重置计时，30 秒一到照样断。用例照第 3.7 节：测试入口把全局空闲超时设成 2 秒、心跳 500 毫秒，订阅保持 6 秒以上、至少 6 次心跳；另加一条：同一服务上，非 SSE 的空闲 keep-alive 连接仍在约 2 到 4 秒内被关，证明没有改全局。变异加一条“不调 server.timeout”。客户端消失靠心跳写失败释放；关停时照旧全部结束。
> 2. 照建议 A：有变化推整份新信封。
> 3. 照建议：开着的 SSE 连接算活动，阻止空闲退出。
> 4. 照建议：六类作业的结果一律不登记白名单。
> 5. 照建议：取消已结束的作业回 409。
>
> 三、pattern 用 -- 传、不对以 - 开头的回 400：同意。第 4.4 节两条用例照写。

站主来信 20261024T160143816010Z-owner-830d15：

> 摘要: 规划端（本会话）代定，补上一封第 9 节第 1 项：SSE 关掉了空闲超时，服务就要自己管住连接。请转给合同端写进 v1（已经交了就出下一版），与上一封一起附在合同末尾。（themistally-15 复核 F7b 时提出，规划端采纳。）
>
> 1. 上限：全局的 SSE 订阅数、每个会话的订阅数各有上限（数值规划端定：全局 16、每个会话 4，测试入口可覆盖）；超过时回 503 带 Retry-After，不挤掉已有的订阅。
> 2. 主动断开：会话过期、控制令牌换发引导地址（旧会话作废）、服务关停与空闲退出时，这些会话的订阅一律主动关流，并清掉各自的定时器。
> 3. 心跳写失败（客户端已经走了）就立刻清理：清定时器、关流、订阅数减一，不等空闲超时（它已经关了）。
> 4. 活动：照上一封第 3 项，开着的订阅算活动，阻止空闲退出。所以窗口关了订阅一定要断：客户端断开（req.signal）、心跳写失败两条路都要释放，各有用例。
>
> 用例至少：超过全局上限、超过每会话上限各回 503；会话作废后订阅被关；心跳写失败后订阅数归零、定时器清掉（替身客户端直接断开）；关停时所有订阅被关。变异各一条：不设上限、会话作废不断开、写失败不清理。
