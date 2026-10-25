# TASK: t018-desktop-ui-follow

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: fe538fc14404dff32e6e0478f2a861fb5d933795
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
给桌面端本机服务的 file 路由（`GET /api/v1/attempts/<task>/<attempt>/file`）加「跟随」：请求带 `follow=1` 时只给已经写完的 JSONL 行（内核的 `logs cat … --complete-lines`），读到末尾也发句柄、没有新行时回空页并复用请求里的同一个句柄，文件被截短或改写时照旧回 409；非 JSONL 路径的跟随请求在起子进程之前回 400；跟随响应里给出轮询间隔的下限 `data.poll_after_ms`（2000 ms），轮询照样经执行器的并发上限与队列。

## Non-goals
- 不做前端的跟随界面、滚动图钉、预览、写路由、凭据录入作业、`operations`；不新增推送通道（SSE 与 WebSocket 都不做）。
- 不新增或修改内核的 CLI 命令与选项；跟随只给内核已有的 `logs cat` 加 `--complete-lines`（内核已有）。
- 不支持普通文本（`.txt`、`.json` 等）的跟随：只给明确的 400，不悄悄退化成从头读；也不改内核的文本游标。
- 不改 `ts/packages/ui/src/localhttp/**`（一个字不改）、不改 `UiArgs`、不改 `ts/packages/ui/package.json`，不加依赖。
- 不改句柄表 `ts/packages/ui/src/cursors.ts`（容量 1024、LRU 淘汰、`issue`/`take`/`drop` 照旧用）。
- 不新增路由：`readRoutes()` 里仍是 19 条读路由，路由名一条不动（`tests/test_gate_t016_baseline.py` 与 `tests/test_gate_t017_baseline.py` 钉住）。
- 不改既有的测试文件（`ts/packages/ui/test/cursors.test.ts`、`ts/packages/ui/test/argv-templates.test.ts`、`ts/packages/ui/test/routes-auth.test.ts`、`ts/packages/ui/test/kernel-real.test.ts` 等一个字不动）；本片的用例全部写在新文件里。
- 不推翻任何过渡断言：本片不碰 `desktop/**` 的前端与 `ts/packages/ui/src/localhttp/` 的常量。

## Repository facts
基线 `5913f5199d6f285e67fa80abb912a4b369cd953c` 上的实际内容。规划报告第 10 节的 A1–A4 与任务书另加的一条逐条核实过，都是定论。本节提到的文件一律写仓库根相对全路径。

- **A1（file 路由仍由一个处理函数组装 argv、换发句柄）**：成立。`ts/packages/ui/src/readroutes.ts` 的 `fileRoute`（第 340 行起）依次校验 task、attempt、path，查句柄表，拼 argv，跑子进程，判内核报的「游标对应的文件已变化」；`withHandle`（第 393 行起）把内核给的 `next_cursor` 换成句柄，`done` 为真时给 `null`；路由表里 `api.attempts.file` 的处理函数就是 `fileRoute`（第 470 行附近）。T017 落地后新增的 `ts/packages/ui/src/events.ts`、`ts/packages/ui/src/jobs.ts`、`ts/packages/ui/src/jobroutes.ts`、`ts/packages/ui/src/watch.ts` 没有动这条路由。结论：S1、S2 的落点就是 `ts/packages/ui/src/readroutes.ts` 里的 `fileRoute` 与 `withHandle`。
- **A2（仍经 `state.runner.run`）**：成立。`fileRoute` 调 `state.runner.run(argv, timeoutSeconds, input.request.signal)`（`ts/packages/ui/src/readroutes.ts` 第 358 行）；执行器 `ts/packages/ui/src/kernel.ts` 的 `KernelRunner` 是同时在跑 4 个（`DEFAULT_MAX_CONCURRENT`）、FIFO 队列 16 个（`DEFAULT_MAX_QUEUE`）、队列满时 `resolve({kind:"queue-full"})`。结论：跟随轮询与普通读取走**同一个**执行器、同一个并发上限与队列，不新开执行器。
- **A3（503 仍是 `Retry-After: 2`）**：成立。`ts/packages/ui/src/kernelenvelope.ts` 的 `retryLater(message)` 建响应后 `response.headers.set("retry-after", "2")`；`runResponse` 的 `queue-full` 与 `closing` 分支都调它。结论：跟随的轮询下限取 **2000 ms**，与 `Retry-After: 2` 一致；服务不强制下限（Q3），靠队列与 503 兜底。
- **A4（测试支架可用）**：成立。`ts/packages/ui/test/support.ts` 的 `startApp(overrides)` 仍接受 `maxConcurrent`、`maxQueue`、`stdoutLimitBytes`、`timeouts`、`repo`、`python`；`ts/packages/ui/test/harness.ts` 的 `startService(options)` 仍接受 `entry: "overrides"`（走 `ts/packages/ui/test/fixtures/serve-overrides.ts`）。替身用例**不需要**改 `ts/packages/ui/test/fixtures/fake-kernel.mjs`：`ts/packages/ui/test/cursors.test.ts` 已经给出「进程内 app + 替身 runner」的写法（`createApp` + `readRoutes(state)` + 自己实现 `RunKernel`），本片的替身用例照它写，能直接断言 argv、页内容、409 与句柄表。
- **A5（另查：有没有钉住「file 路由在 `done` 为真时一律给 null」的非过渡断言）**：**没有需要退役的断言**。`tests/test_gate_t017_baseline.py` 全文没有 `next_cursor` 这个词；它的 `test_static_route_batches` 只要求 `ts/packages/ui/src/readroutes.ts` 里 19 条既有路由名一条不动、不许出现 `api.events`/`api.jobs.*` 四个新路由名；`tests/test_gate_t016_baseline.py` 的 `test_static_cursors` 只查源码里出现过 `next_cursor` 这个词、`ts/packages/ui/src/cursors.ts` 里有 `randomToken`、1024、`task`/`attempt`/`path`/`cursor` 与 `Map`。真正把「`done` 为真给 `null`」钉成断言的是既有的白盒用例 `ts/packages/ui/test/cursors.test.ts:166`（**非跟随**请求的第二页 `next_cursor` 是 `null`）。结论：本片保持**非跟随**行为逐字节不变，那条既有用例继续成立，不许改它；门禁端也不需要为本片退役任何断言。
- **A6（内核的跟随语义，`scripts/kit_logs.py`，只读）**：
  - `cmd_cat`（第 845 行）调 `safe_page(_under(attempt_dir, …), rel, args.cursor, args.limit, final=not args.complete_lines)`；`--complete-lines` 是 argparse 的 `store_true`（第 1377 行）。
  - `_jsonl_records`（第 631 行）：`final` 为假时，末行没有换行就整行不给（`not ended and not final` 就 return）。
  - `_jsonl_resume`（第 745 行）：文件号相同、文件不变短（`size < c_size` 即失效）、长度不变而修改时间变了（原地改写）即失效、偏移必须是原始行首、偏移之前 4096 字节（`CURSOR_WINDOW`）的哈希不变；**文件只增长时游标一直有效**。
  - `_jsonl_page`（第 774 行）：`done = after >= size and after_char == 0`；`lines` 为空数组只出现在行内字符位置为 0 且没有可给的内容时；一行超过一页时按 `part`/`parts` 分片给出（`after_char` 不为 0）。
  - `safe_mode`（第 592 行）：`rel.lower().endswith(".jsonl")` → jsonl 模式，`.json` → json 模式，其余是 text 模式。结论：服务侧判定用 `path.toLowerCase().endsWith(".jsonl")`，与内核一致（不用带 `u` 标志的不分大小写正则）。
  - `StaleCursor`（第 585 行）：提示原文「游标对应的文件已变化：请从头读取」，退出码 2（`EXIT_USAGE`）；`kit_logs.main`（第 1405–1409 行）把它打印成 stderr 的一行 `ERROR: …`。
  - `SAFE_PAGE_CHARS = 256 * 1024`（第 66 行）、`SAFE_MAX_LINE_BYTES = 4 * 1024 * 1024`（第 68 行）。
  - `logs cat` 只认证据清单里的相对路径（不在清单里回退出码 2），真内核用例要把证据文件放进 `<repo>/.agent/runs/<task>/<attempt>/` 之下。
- **A7（脱敏不影响新增的键）**：`@themis/base/secrets` 的 `redactJson(value, allow)`（`ts/packages/base/src/secrets.ts` 第 259 行）只对「键名像凭据」的位置改值；`poll_after_ms` 不是敏感键，值是数字，不被改。file 路由登记的白名单是 `EVIDENCE_ALLOW`（`ts/packages/ui/src/redaction.ts` 里是 `undefined`），data 原样过 `redactJson`。结论：`data.poll_after_ms` 会原样出现在响应里。
- **A8（既有断言不许破）**：`tests/test_gate_t016_baseline.py` 的 19 条读路由哨兵、`ts/packages/ui/test/argv-templates.test.ts` 的「模板里每个以 `--` 开头的项都含 `=`（`--version`、`--json` 除外）」与「位置参数不以 `-` 开头」、`ts/packages/contracts/test/source-hygiene.test.ts` 的「`ts/packages` 与 `ts/mutations` 里没有看不见的字符」、`ts/packages/contracts/test/ui.contract.test.ts` 都照旧成立。结论：`FOLLOW_ARGV` **不并进 `READ_ROUTE_ARGV`**（`--complete-lines` 是开关、不含 `=`，并进去就要改被锁定的用例）；真内核解析器的那条用例写在本片的新测试文件里，另起一条 describe。
- **A9（工具链与锁文件）**：`ts/bun.lock` 提交在库里，`ts/node_modules` 不提交；worktree 里各自 `bun install --frozen-lockfile`，不做目录链接。起 Bun 用 `ts/packages/ui/test/harness.ts` 的 `bunPath()`（内部调 `@themis/base/native` 的 `bunExecutable()`）；真内核用 `scripts/pi_dispatch.py` 与 `process.env["THEMIS_PYTHON"] ?? "python"`（照 `ts/packages/ui/test/kernel-real.test.ts` 的写法）。合同不依赖任何具体版本号。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/README.md
- allowed_new_files:
  - ts/packages/ui/test/follow.test.ts
  - ts/packages/ui/test/follow-real.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/src/cursors.ts
  - ts/packages/ui/package.json
  - ts/packages/ui/test/app.test.ts
  - ts/packages/ui/test/args.test.ts
  - ts/packages/ui/test/argv-templates.test.ts
  - ts/packages/ui/test/cursors.test.ts
  - ts/packages/ui/test/events-service.test.ts
  - ts/packages/ui/test/events.test.ts
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/jobs-service.test.ts
  - ts/packages/ui/test/jobs.test.ts
  - ts/packages/ui/test/kernel-env.test.ts
  - ts/packages/ui/test/kernel-real.test.ts
  - ts/packages/ui/test/kernel-runner.test.ts
  - ts/packages/ui/test/launcher.e2e.test.ts
  - ts/packages/ui/test/lifecycle.test.ts
  - ts/packages/ui/test/localhttp-accesslog.test.ts
  - ts/packages/ui/test/localhttp-body.test.ts
  - ts/packages/ui/test/localhttp-control.test.ts
  - ts/packages/ui/test/localhttp-guards.test.ts
  - ts/packages/ui/test/localhttp-headers.test.ts
  - ts/packages/ui/test/localhttp-session.test.ts
  - ts/packages/ui/test/lockdir.test.ts
  - ts/packages/ui/test/redaction-routes.test.ts
  - ts/packages/ui/test/redaction.test.ts
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/test/service.test.ts
  - ts/packages/ui/test/static-paths.test.ts
  - ts/packages/ui/test/support.ts
  - ts/packages/ui/test/fixtures/fake-kernel.mjs
  - ts/packages/ui/test/fixtures/resolve-asset.ts
  - ts/packages/ui/test/fixtures/serve-entry.ts
  - ts/packages/ui/test/fixtures/serve-overrides.ts
  - ts/packages/base/**
  - ts/packages/cli/**
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
  - tests/test_gate_t018_*.py
  - tests/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - **请求形式**：同一条路由 `GET /api/v1/attempts/<task>/<attempt>/file?path=<p>[&cursor=<句柄>][&follow=1]`。`follow` 用 `url.searchParams.get("follow")` 取（与 `path`、`cursor` 同样的取法；不另查重复参数，重复时取第一个）。不带 `follow` 就是普通翻页，行为与现在逐字节相同。
  - **参数校验次序**（全在起子进程之前，顺序固定）：
    1. task 不合法 → 400「任务 ID 不合法」（原文照旧）。
    2. attempt 不合法 → 400「attempt 编号不合法」（原文照旧）。
    3. path 不合法 → 400「证据路径不合法」（原文照旧）。
    4. `follow` 存在但不是字面 `"1"`（含 `0`、`true`、空串、`2`、`yes`、`01`）→ 400「follow 参数不合格（只接受 1）」，**不起子进程**，不回显请求里的值。
    5. `follow=1` 且 path 不是 `.jsonl`（判定：`path.toLowerCase().endsWith(".jsonl")`，大小写不敏感，`LOG.JSONL` 放行）→ 400「只有 JSONL 文件支持跟随」，**不起子进程**，不回显路径。
    6. 句柄：格式不对（不是 43 个 base64url 字符）、不在表里、绑定的 task/attempt/path 与本次请求不一致 → 409「游标无效或文件已变化，请从头读取」（原文照旧），**不起子进程**。
    7. 之后才起子进程。
  - **跟随的 argv**（次序写死，用例逐项比对）：
    - 不带游标：`["logs", "cat", "<task>/<attempt>", "<path>", "--json", "--complete-lines"]`
    - 带游标：`["logs", "cat", "<task>/<attempt>", "<path>", "--json", "--complete-lines", "--cursor=<内核游标>"]`（`--cursor=` 在最后）
    - 普通翻页的 argv 一条不改：不变时是 `["logs","cat",…,"--json"]`，带游标时末尾加 `["--cursor=<内核游标>"]`。
  - **`FOLLOW_ARGV` 登记表**（导出在 `ts/packages/ui/src/readroutes.ts`，示例值照 `READ_ROUTE_ARGV` 的约定：task=demo-task、attempt=attempt-001、path=events.jsonl、游标=fake-cursor-0001）：
    - `api.attempts.file.follow` → `["logs","cat","demo-task/attempt-001","events.jsonl","--json","--complete-lines"]`
    - `api.attempts.file.follow.cursor` → `["logs","cat","demo-task/attempt-001","events.jsonl","--json","--complete-lines","--cursor=fake-cursor-0001"]`
    - **不并进 `READ_ROUTE_ARGV`**（既有断言要求每个以 `--` 开头的项都含 `=`，`--complete-lines` 是开关）。
  - **跟随的响应**：data 的键序是内核给的键的原序，`next_cursor` 就地换成句柄，末尾追加 `poll_after_ms`（值 2000）。`done` 原样透传（跟随时 `done` 为真表示「读到末尾而且末行完整」，为假且页空表示「有一条半行在等」；服务不据此改变行为）。
  - **末尾也发句柄**：跟随时只要内核给了非空的字符串游标，`next_cursor` **一律是句柄**，不看 `done`（非跟随照旧：`done` 为真时给 `null`）。
  - **空页复用请求里的句柄**：跟随请求带了句柄 H，而这一页的 `lines` 是空数组 → `next_cursor` 原样给 H，**不发新句柄，句柄表项数不变**（H 已被 `take` 挪到表的最新端）。这是「没有新内容时不另发新句柄」的实现方式，`ts/packages/ui/src/cursors.ts` 一个字不改。
  - **不带句柄的跟随请求**：这一页为空时照常发一个句柄（第一次读空文件、或文件里只有一条半行）；之后的轮询就复用它。
  - **有内容的一页**：发一个新句柄（`state.cursors.issue`）。**旧句柄留在表里**（站主 Q1：不 drop）；旧句柄被 LRU 淘汰之后回 409。
  - **轮询下限**：`data.poll_after_ms = 2000`，常量 `FOLLOW_MIN_INTERVAL_MS = 2000` 写在并导出自 `ts/packages/ui/src/readroutes.ts`（不复用 SSE 的常量；数值与 503 的 `Retry-After: 2` 一致）。**只在跟随响应里出现**：非跟随响应的 data 里没有这个键。
  - **服务不强制下限**（站主 Q3）：不按句柄记时间、不回 429；轮询太快由执行器的队列与 503（`Retry-After: 2`）兜底。
- 边界输入：
  - **普通文本（以及 `.json`）的跟随**：400「只有 JSONL 文件支持跟随」，不起子进程。不悄悄退化成从头读（退化后每次轮询都要整份脱敏，最多 64 MiB）；不用 409（界面对 409 的约定是「从头读」，等于还是悄悄退化）。
  - **409 的四种情形**（沿用 T016，跟随不新增情形）：句柄格式不对 / 不在表里（伪造、被淘汰、服务重启前）/ 绑定与本次请求不一致——服务自己判，不起子进程；文件被替换、截短、原地改写、游标之前的字节被改——内核退出 2 且 stderr 含「游标对应的文件已变化」，服务丢掉这个句柄并回 409（起了子进程，一次）。
  - **已知的第四种 409**：普通翻页拿到的句柄若停在一条没写完的超长末行中间（行内位置不为 0），之后改用跟随，内核判游标失效 → 409。界面收到 409 就从头跟随，不用另外处理（写进 README）。
  - **分片**：一行超过一页（`SAFE_PAGE_CHARS = 256 * 1024` 个字符）时内核按 `part`/`parts` 分片给出（`done` 为假）；跟随时照样每次给一片、发一个新句柄，直到最后一片；最后一片之后的句柄指向下一行的行首。写完之前的那一行在跟随时整行不给（`--complete-lines`），写完之后从第 1 片起给。
  - **空页与「没有可给的内容」**：内核的 `lines` 为空数组只出现在行内位置为 0 且没有可给的内容时，所以「空页」等价于「位置没动、没有可给的内容」，复用句柄的规则靠这一条成立。
  - **并发轮询同一个句柄**：两次请求可能给出同样的行（内核游标是按文件位置记的）。前端要串行轮询；服务不加锁（README 写明）。
- 错误与重试：
  - HTTP 状态：400（`follow` 取值不合格、非 JSONL 的跟随、以及既有的参数不合格）、401（未认证）、409（句柄无效或文件已变化）、503（队列满或服务正在关闭，带 `Retry-After: 2`）、504（命令超时）、500（起不了子进程等）。命令退出非 0 一律回 200 信封（`ok` 为 false、`exit_code` 原样），与既有路由一致。
  - 服务自己产生的错误一律走 `errorResponse` 的形状（`ok` 为 false、`exit_code` 为 null、`data` 为 null、`output` 与 `command` 是空数组、`messages` 只有一行 `ERROR: …`）。
  - 服务不重试任何请求，也不回 429。503 时句柄不受影响（`take` 在起子进程之前已经把它挪到表的最新端，排队失败不丢句柄）；前端照 `Retry-After: 2` 等一会儿，带同一个句柄重试，不会丢行也不会重复。
- 并发、取消与状态变化：
  - 跟随轮询与普通读路由共用同一个执行器：同时在跑 4 个、FIFO 队列 16 个，第 21 个在途请求立刻回 503 带 `Retry-After: 2`（不起子进程）。
  - 一个跟随者在前端串行轮询（等上一次响应回来再排下一次）的前提下，同时最多 1 个在途请求；按 2000 ms 的下限，每分钟最多 60000 / 2000 = 30 次轮询，每次起 1 个 `logs cat` 子进程。
  - 句柄表：容量 1024、最近最少用先淘汰（`ts/packages/ui/src/cursors.ts` 不改）。空闲跟随（空页）表项数不变；活跃跟随每一页有内容 +1 个句柄。每个跟随者每分钟最多 +30 个，约 34 分钟写满 1024；之后每发一个新句柄淘汰一个最旧的，被淘汰的旧句柄回 409（界面从头读）。
  - 客户端断开（请求的 signal abort）由执行器处理：排队中的出队不起子进程，在跑的结束整棵进程树——与既有读路由一致，跟随不另加逻辑。
- 兼容性：
  - **非跟随的 file 路由逐字节不变**：argv 不变、`done` 为真时 `next_cursor` 仍是 `null`、data 里没有 `poll_after_ms`、既有的 400/409 提示原文不变。既有白盒用例 `ts/packages/ui/test/cursors.test.ts`（含第 166 行的 `next_cursor` 为 `null`）与 `ts/packages/ui/test/kernel-real.test.ts` 的「data 与 CLI stdout 逐字节一致」继续成立，不许改。
  - 路由表仍是 19 条，路由名与超时一条不动；信封七字段与次序不动；`poll_after_ms` 只在 data 里多一个键。
  - `ts/packages/ui/src/main.ts` 的 `UiArgs` 不改；`ts/packages/ui/package.json` 不改，不加依赖。

## Steps
1. 预检（只读）：核对 Repository facts 里的行号与签名（`ts/packages/ui/src/readroutes.ts` 的 `fileRoute`/`withHandle`、`ts/packages/ui/src/cursors.ts` 的 `issue`/`take`/`drop`/`size`、`ts/packages/ui/src/kernelenvelope.ts` 的 `retryLater`、`ts/packages/ui/test/support.ts` 的 `startApp`、`ts/packages/ui/test/harness.ts` 的 `startService`）；跑 `python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py -q` 确认基线绿；在 `ts` 里跑 `bun install --frozen-lockfile`。不符即停并报告。
2. 跟随的请求与 argv（改 `ts/packages/ui/src/readroutes.ts`）：加常量 `FOLLOW_MIN_INTERVAL_MS = 2000`（导出）；加导出 `FOLLOW_ARGV`（两条，示例值见 Behavior contract）；在 `fileRoute` 里按 Behavior contract 的次序做 `follow` 的校验（取值不合格 → 400；非 `.jsonl` → 400），组装跟随的 argv（带 `--complete-lines`，`--cursor=` 在最后）。**校验与分支判断放进小函数，主函数只走正常流程**。
3. 跟随的响应（改 `ts/packages/ui/src/readroutes.ts`）：`withHandle` 增加跟随分支——跟随时 `next_cursor` 一律是句柄（不看 `done`）；空页且请求带了句柄时原样回那个句柄、不发新句柄；有内容时发新句柄（旧句柄留在表里，不 drop）；跟随的 data 末尾追加 `poll_after_ms`（2000）。非跟随分支一个字不改。
4. 替身用例（新建 `ts/packages/ui/test/follow.test.ts`）：照 `ts/packages/ui/test/cursors.test.ts` 的写法（进程内 `createApp` + 自己实现 `RunKernel` 的替身），逐条对上下面覆盖矩阵里的 F1–F12。队列那条用 `startApp({maxConcurrent: 1, maxQueue: 0})` 加一个睡着的替身（照 `ts/packages/ui/test/kernel-runner.test.ts` 里 503 那条的写法：靠在途计数，不靠睡眠长短）。ui 测试目录里不许出现 skip、only、todo。
5. 真内核用例（新建 `ts/packages/ui/test/follow-real.test.ts`）：照 `ts/packages/ui/test/kernel-real.test.ts` 的夹具与 `startService({entry:"overrides"})` 起真服务与真内核（`scripts/pi_dispatch.py`）；证据文件放在 `<repo>/.agent/runs/demo-task/attempt-001/events.jsonl`；文件增长一律用 `appendFileSync`，截短用 `truncateSync`，只靠文件大小与内容判定，不靠修改时间，也不睡眠；同一文件里用 `kit_logs.build_parser()`（剥掉组名 `logs`）解析 `FOLLOW_ARGV` 的两条，断言 `json` 与 `complete_lines` 都为真。客户端在 Node 一侧，收进程靠关 stdin 与 kill，不发控制台信号，不写 `nul`、`con` 这类名字。
6. README（改 `ts/packages/ui/README.md`）：加「## 日志跟随」一节——`follow=1` 的参数形式、只认字面 `1`、两种 400（提示原文照写）、JSONL 判定大小写不敏感、末尾也发句柄、空页复用句柄、`poll_after_ms`（2000，与 `Retry-After: 2` 一致）、服务不强制下限、409 的已知情形（普通翻页停在半行中间之后改用跟随会 409）、并发轮询同一个句柄可能重复给行；既有的段落（D13 那几段、T016 钉住的那几段、状态码那一段）逐字保留。
7. 跑 Validation commands 里与改动相关的检查（V01–V09），记录命令与结果；确认 `git status --porcelain --untracked-files=all` 只出现允许范围内的路径；写执行报告；遇到合同未定义的行为，停止并报告。

基准测试文件清单（门禁端据此锁定；执行端不许删改既有用例）：

- `ts/packages/ui/src/readroutes.ts`（既有，追加跟随的请求、argv、响应与两个常量）
- `ts/packages/ui/test/follow.test.ts`（新；F1–F12）
- `ts/packages/ui/test/follow-real.test.ts`（新；R1–R3）
- `ts/packages/ui/README.md`（既有，追加「日志跟随」一节）

覆盖矩阵（用例文件 → 断言的内容）：

- **F1**（`ts/packages/ui/test/follow.test.ts`）：跟随交给内核的 argv 逐项等于 `FOLLOW_ARGV` 的两条（不带游标、带游标）；普通翻页的 argv 一条不变（不带游标、带游标各一条）。
- **F2**（`ts/packages/ui/test/follow.test.ts`）：内核回 `done: true` 并带游标 → 跟随给句柄（43 个字符）；同样的内核输出走非跟随 → `next_cursor` 是 `null`（钉住非跟随不被带坏）。
- **F3**（`ts/packages/ui/test/follow.test.ts`）：带句柄 H 跟随、内核回 `lines: []` → `next_cursor === H`，句柄表项数不变；连做 5 次也一样。
- **F4**（`ts/packages/ui/test/follow.test.ts`）：不带句柄跟随、内核回空页 → 发一个句柄；拿它再轮询（仍是空页）→ 还是同一个句柄，表项数不变。
- **F5**（`ts/packages/ui/test/follow.test.ts`）：内核回有内容的一页 → 新句柄 ≠ H，句柄表 +1；**H 仍可用**（带 H 再请求一次不是 409）。
- **F6**（`ts/packages/ui/test/follow.test.ts`）：内核退出 2 且 stderr 含「游标对应的文件已变化」→ 409，句柄被丢掉；再用它 → 409 且不再起子进程。
- **F7**（`ts/packages/ui/test/follow.test.ts`）：`notes.txt`、`a.json`、`a.jſonl` 带 `follow=1` → 400，不起子进程；`LOG.JSONL` 带 `follow=1` → 正常起子进程。
- **F8**（`ts/packages/ui/test/follow.test.ts`）：`follow=0`、`follow=true`、`follow=`（空串）→ 400，不起子进程。
- **F9**（`ts/packages/ui/test/follow.test.ts`）：跟随响应的 data 有 `poll_after_ms` 且值为 2000；非跟随响应的 data 里没有这个键。
- **F10**（`ts/packages/ui/test/follow.test.ts`）：队列满（`startApp({maxConcurrent: 1, maxQueue: 0})` 加睡着的替身）→ 跟随请求回 503 且带 `retry-after: 2`；之后带同一个句柄重试成功。
- **F11**（`ts/packages/ui/test/follow.test.ts`）：发满 `CURSOR_CAPACITY`（1024）个句柄之后，最早那个跟随句柄回 409。
- **F12**（`ts/packages/ui/test/follow.test.ts`）：内核回 `part: 1, parts: 2, done: false` → 跟随给一个新句柄，下一次请求的 argv 带它的内核游标。
- **R1**（`ts/packages/ui/test/follow-real.test.ts`）：`FOLLOW_ARGV` 的两条用内核的 `kit_logs.build_parser()` 解析（剥掉组名 `logs`），断言解析成功、`json` 为真、`complete_lines` 为真。
- **R2**（`ts/packages/ui/test/follow-real.test.ts`，真实增长的 `events.jsonl`）：先写 `{"a": 1}\n{"b": 2`（半行）→ 不带游标跟随只给 a，拿到 H1；再跟随 → `lines` 为空、`next_cursor === H1`；补上 `}\n` → 给 b（行号 2），拿到 H2，`done` 为真；再跟随 → 空页、`next_cursor === H2`（b 只给一次）；追加 `{"c": 3}\n` → 给 c，拿到 H3，`done` 为真；`truncateSync` 截到 `{"a": 1}\n` 的长度 → 用 H3 回 409，再用 H3 回 409（已丢、不起子进程）；不带游标跟随 → 从头给 a。每一步都断言 `poll_after_ms === 2000`。
- **R3**（`ts/packages/ui/test/follow-real.test.ts`）：写一行超过一页（大于 256 Ki 个字符，例如 300 KiB 的字符串值）的完整 JSONL 加换行 → 跟随第 1 页是 `part 1/2` 且带句柄；第 2 页是 `part 2/2`、`done` 为真、仍带句柄；第 3 页空、句柄不变。

变异清单（每条都要有会变红的用例）：

- **M1**：跟随的 argv 不带 `--complete-lines` → R2 的半行那条（半行会被给出）与 R1（解析出的 `complete_lines` 为假）。
- **M2**：半行被给出（跟随时仍按 `final=True` 读）→ R2 的第一步。
- **M3**：补上换行之后重复给同一行（游标没越过它）→ R2 的第四步（b 只给一次）。
- **M4**：跟随在末尾给 `null`（`done` 为真就不发句柄）→ F2 与 R2 的第三步。
- **M5**：没有新内容也换发新句柄（空页不复用请求里的句柄）→ F3、F4 与 R2 的第二步。
- **M6**：截短不报 409（把内核报「游标对应的文件已变化」当普通结果放过去，或不丢句柄）→ F6 与 R2 的第六步。
- **M7**：普通文本被当成跟随（不判 `.jsonl` 就放行）→ F7。
- **M8**：不给轮询下限（跟随响应里没有 `poll_after_ms`，或值不是 2000）→ F9 与 R2 的每一步。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t018_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`bun install --frozen-lockfile` · cwd：ts · 超时：900s · 期望退出码：0
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V04（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V05（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0
- V06（必要）：`python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V07（必要）：`git status --porcelain --untracked-files=all` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：`ts/packages/ui/`，不得出现：`(?m)^\s*\S+\s+(?!ts/packages/ui/)`
- V08（必要）：`node -e "const fs=require('fs');const s=fs.readFileSync('packages/ui/README.md','utf8');const need=['follow','poll_after_ms','--complete-lines','2000','409','503','Retry-After','已知限制'];const miss=need.filter((x)=>!s.includes(x));if(miss.length){console.error('README missing: '+miss.join(','));process.exit(1)}console.log('README ok')"` · cwd：ts · 超时：120s · 期望退出码：0 · 输出须匹配：`README ok`
- V09（必要）：`node -e "const {spawnSync}=require('child_process');for(let i=0;i<5;i++){const r=spawnSync(process.execPath,['node_modules/vitest/vitest.mjs','run','packages/ui/test/follow.test.ts','packages/ui/test/follow-real.test.ts'],{stdio:'inherit'});if(r.status===0){continue}console.error('run '+(i+1)+' failed');process.exit(1)}console.log('STABLE5')"` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`STABLE5`

## 检查清单
合同里被引用的检查 id 只有下面这些。Definition of done 的「证据」字段只允许填这里定义的 id，不得填 F/R 编号，也不得填未定义的 id。

| id | 检查什么 | 命令（见 Validation commands） | 通过判据 |
|---|---|---|---|
| G01 | T018 的门禁基准测试（基线应失败；门禁端写好后由内核做成基线提交） | `python -m pytest tests/test_gate_t018_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| R01 | T001–T017 的门禁回归（基线应通过） | `python -m pytest tests/test_gate_t001_baseline.py … tests/test_gate_t017_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| V01 | 依赖按锁文件装好 | `bun install --frozen-lockfile`（cwd：ts） | 退出码 0 |
| V02 | ui 包自己的用例全过（含本片 F1–F12 与 R1–R3） | vitest `packages/ui/test`（cwd：ts） | 退出码 0 且输出匹配 `Tests[^\n]*[1-9]\d*[^\n]*passed` |
| V03 | 内核契约相关的三个用例文件全过 | vitest `packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts`（cwd：ts） | 同上 |
| V04 | 全量 vitest 全过 | vitest 全量（cwd：ts） | 同上 |
| V05 | 类型检查 | `tsc -p tsconfig.json`（cwd：ts） | 退出码 0 |
| V06 | T016/T017 门禁里的长期断言没破（19 条读路由、既有白盒用例清单、README 结构） | `python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py -q`（cwd：仓库根） | 退出码 0 且输出匹配 `\d+ passed` |
| V07 | 改动范围：只出现允许范围内的路径 | `git status --porcelain --untracked-files=all`（cwd：仓库根） | 只出现 `ts/packages/ui/` 下的路径 |
| V08 | README 写到了跟随的关键结论（follow、poll_after_ms、--complete-lines、2000、409、503、Retry-After、已知限制） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `README ok` |
| V09 | 稳定性：本片两个新用例文件连跑 5 次都过（全量并行下也稳） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `STABLE5` |

## Definition of done
- D01：`follow` 的参数校验——只认字面 `1`；`follow=0`、`follow=true`、`follow=`（空串）一律回 400「follow 参数不合格（只接受 1）」，不起子进程、不回显请求里的值；不带 `follow` 的请求行为逐字节不变；用例：`ts/packages/ui/test/follow.test.ts` 的 F8；证据：V02；目的：不合格的取值到不了内核，也不给攻击者反馈。
- D02：非 JSONL 的跟随请求——`notes.txt`、`a.json`、`a.jſonl` 带 `follow=1` 回 400「只有 JSONL 文件支持跟随」（不起子进程、不回显路径），判定大小写不敏感（`LOG.JSONL` 放行）；用例：`ts/packages/ui/test/follow.test.ts` 的 F7；证据：V02；目的：普通文本的跟随要么内核支持、要么明确拒绝，不悄悄退化成从头读。
- D03：跟随的 argv——不带游标与带游标两条逐项等于 `FOLLOW_ARGV`（`--json --complete-lines`，`--cursor=` 在最后），普通翻页的 argv 一条不变；`FOLLOW_ARGV` 不并进 `READ_ROUTE_ARGV`；用例：`ts/packages/ui/test/follow.test.ts` 的 F1 与 `ts/packages/ui/test/follow-real.test.ts` 的 R1；证据：V02；目的：跟随与普通翻页在内核那里是两条明确的命令行，只给已经写完的行靠的就是 `--complete-lines`。
- D04：末尾也发句柄——内核回 `done: true` 并带游标时，跟随的 `next_cursor` 是 43 个字符的句柄；非跟随的同一份内核输出仍是 `null`；用例：`ts/packages/ui/test/follow.test.ts` 的 F2；证据：V02；目的：界面拿着句柄才能继续要新行，而普通翻页的「没有下一页就是 null」不能被带坏。
- D05：空页复用请求里的句柄——带句柄 H 跟随、内核回空页时 `next_cursor === H`，句柄表项数不变，连做 5 次也一样；不带句柄的跟随空页发一个句柄，之后的轮询一直复用它；用例：`ts/packages/ui/test/follow.test.ts` 的 F3、F4；证据：V02；目的：空闲的长时间跟随不会把句柄表撑爆。
- D06：有内容时发新句柄、旧句柄仍可用——有内容的一页发新句柄（表 +1），旧句柄 H 不被丢掉，带 H 再请求不是 409；用例：`ts/packages/ui/test/follow.test.ts` 的 F5；证据：V02；目的：请求被取消或响应丢了，带旧句柄重试照样接着给，不会从头读。
- D07：409 的情形沿用 T016——句柄格式不对、不在表里、绑定不符都不起子进程就回 409；内核退出 2 且 stderr 含「游标对应的文件已变化」时回 409 并丢掉这个句柄（再用它回 409 且不起子进程）；跟随不新增情形；用例：`ts/packages/ui/test/follow.test.ts` 的 F6 与 `ts/packages/ui/test/follow-real.test.ts` 的 R2 的截短那两步；证据：V02；目的：文件被替换、截短、改写时界面能从头读，而不是静默地给错内容。
- D08：轮询下限——跟随响应的 data 里有 `poll_after_ms`，值为 2000（与 503 的 `Retry-After: 2` 一致）；非跟随响应的 data 里没有这个键；服务不强制下限、不回 429；用例：`ts/packages/ui/test/follow.test.ts` 的 F9 与 `ts/packages/ui/test/follow-real.test.ts` 的 R2 的每一步；证据：V02；目的：界面知道该等多久，同时服务不替界面记时间表。
- D09：轮询照样经执行器——队列满时跟随请求回 503 且带 `retry-after: 2`，之后带同一个句柄重试成功（不丢行也不重复）；用例：`ts/packages/ui/test/follow.test.ts` 的 F10；证据：V02；目的：跟随不绕过并发上限与队列，不把机器压垮。
- D10：句柄表有上界——发满 1024 个句柄之后，最早那个跟随句柄回 409；空闲跟随不涨表；用例：`ts/packages/ui/test/follow.test.ts` 的 F11；证据：V02；目的：长时间跟随不会把服务内存吃光，被淘汰的句柄按既有约定回 409。
- D11：分片按片接着给——内核回 `part: 1, parts: 2, done: false` 时跟随给一个新句柄，下一次请求的 argv 带它的内核游标；用例：`ts/packages/ui/test/follow.test.ts` 的 F12 与 `ts/packages/ui/test/follow-real.test.ts` 的 R3；证据：V02；目的：一行超过一页时跟着读完，不丢片也不重片。
- D12：真内核解析器——`FOLLOW_ARGV` 的两条用内核的 `kit_logs.build_parser()` 解析，解析成功、`json` 为真、`complete_lines` 为真；用例：`ts/packages/ui/test/follow-real.test.ts` 的 R1；证据：V02；目的：跟随的命令行是内核真认的写法，不是照着猜的。
- D13：真内核上的增长全程——半行不给；补上换行后给且只给一次；再追加接着给；截短回 409（且句柄被丢）；每一步 `poll_after_ms === 2000`；用例：`ts/packages/ui/test/follow-real.test.ts` 的 R2；证据：V02；目的：D7「跟随时只追加已经写完的新行」是真的，不是服务自己假装。
- D14：非跟随行为逐字节不变——既有 `ts/packages/ui/test/cursors.test.ts`（含 `next_cursor` 为 `null` 那条）与 `ts/packages/ui/test/kernel-real.test.ts` 的「data 与 CLI stdout 逐字节一致」照旧通过，一个字不改；用例：`ts/packages/ui/test/cursors.test.ts` 与 `ts/packages/ui/test/kernel-real.test.ts`（既有）；证据：V02、V06；目的：跟随是加法，不许把翻页的语义带坏。
- D15：README——加「日志跟随」一节，写明 `follow=1` 的形式与只认字面 `1`、两种 400 的提示原文、JSONL 判定大小写不敏感、末尾也发句柄、空页复用句柄、`poll_after_ms`（2000，与 `Retry-After: 2` 一致）、服务不强制下限、409 的已知情形（普通翻页停在半行中间之后改用跟随会 409）、并发轮询同一个句柄可能重复给行；既有的段落逐字保留；证据：V08；目的：界面前端拿这份 README 就能把跟随接上。
- D16：范围与依赖——改动只落在 `ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/README.md` 与两个新测试文件上；`ts/packages/ui/src/localhttp/**`、`ts/packages/ui/src/cursors.ts`、`ts/packages/ui/package.json`、`ts/bun.lock`、`ts/package.json` 一个字未改；没有新增、升级或删除依赖；证据：scope、V07、review；目的：内核禁区与本机 HTTP 的安全基线不受本片影响。
- D17：门禁与回归——G01、R01、V01–V09 全部通过；既有用例未删未跳未弱化（ui 测试目录里没有 skip、only、todo）；M1–M8 每条都有会变红的用例；证据：G01、R01、V01、V02、V03、V04、V05、V06、V07、V08、V09、review；目的：不靠削弱测试过关，也不破坏已有门禁。
- D18：稳定性——本片两个新用例文件连跑 5 次都通过（全量并行下也稳）；证据：V09；目的：偶发红不能靠重跑蒙过去。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `fileRoute`/`withHandle` 不在 `ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/cursors.ts` 没有 `take`/`drop`/`size`、503 不再带 `Retry-After: 2`）。
- 必须修改允许范围之外的文件才能继续（例如必须改 `ts/packages/ui/src/cursors.ts` 才能实现空页复用、必须改 `ts/packages/ui/src/localhttp/**` 才能加响应头、必须改 `scripts/kit_logs.py` 才能拿到「只给写完的行」）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 内核的 `logs cat --complete-lines` 在新基线上不再认这个选项、或不再有「末行没有换行就不给」的语义：停下报告，不许自己改成别的做法。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；本任务此前已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（已用 0 秒；= 3 倍单次时限，给这一版留足 2 次 attempt）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：预检 300s、请求与 argv 600s、响应与句柄复用 600s、替身用例 900s、真内核用例 1200s、README 300s、必要检查（含稳定性）900s、最终报告 200s；总计 5000s，不超过单轮时限 5400s

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D18，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261025T085631061551Z-owner-bb8910：

> T018 规划的 Q1–Q4，规划端（本会话）代定，用户没有逐条看过，四条都照规划报告第 9 节的推荐：
>
> - Q1 跟随读到新行、发了新句柄之后，旧句柄留着，不 drop。理由：与翻页一致；请求被取消或响应丢了，带旧句柄重试照样接着给。表的增长由 1024 的 LRU 上限兜住，被淘汰的回 409。
> - Q2 轮询下限放在跟随响应的 data.poll_after_ms，不用自定义响应头（localhttp 不能改）。
> - Q3 服务不强制下限，不回 429：第 2 片的队列与 503 已经兜底，不为它加一张按句柄记时间的表。
> - Q4 下限取 2000 ms，与 503 的 Retry-After: 2 一致。
>
> 另：合同端开工时以 T017 落地之后的代码为准，规划报告第 10 节的 A1–A4 逐条在新基线上核对；规模按报告第 6 节，不拆。
