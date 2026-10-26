# @themis/ui

桌面端的本机服务（`docs/themis-tally-3.0-桌面端.md`，第 7 版 §0.0a）：Bun 运行，只绑 127.0.0.1，是桌面端唯一的后端，也是安全边界（D4）。第 1 片是服务骨架、安全基线与握手；第 2 片加 19 条只读数据路由；第 3 片加桌面端本机服务的第 3 片：SSE 路由 `GET /api/v1/events`（实时通道）与作业路由 `POST /api/v1/jobs`、`GET /api/v1/jobs/<id>`、`POST /api/v1/jobs/<id>/cancel`（起内核子进程的作业），并把第 2 片复核留下的三条加固（输出上限边写边看、真内核拒绝越界路径、关停清队列并摘监听）落定；第 4 片给 file 路由加「跟随」（`follow=1`，见「日志跟随」一节）。第 5 片给本机服务接上「预览 → 确认号 → 带令牌执行 → 操作终态」这条写链路（`POST /api/v1/preview` 与 12 条写路由，见「写操作」一节）；T020 把 profile 与 runtime 的五条写路由接进这条链；凭据录入作业仍是后面几片的事。

- 入口：`src/main.ts` 的 `runUi`（参数检查）转交 `src/server.ts` 的 `serveUi`。内核仓库里经 `pi_dispatch.py ui --desktop --assets <目录> …` 转交（调度器第 73 轮）；桌面应用里外壳直接起打包好的程序（T6）。
- 本包不在内核禁区里（迁移计划第 69 轮），经 hub 派给执行器；`package.json` 与 `bun.lock` 的登记由规划端维护（禁区里的工作区文件）。

## 结构

| 文件 | 职责 |
| --- | --- |
| `src/main.ts` | `UiArgs`、`checkArgs`、退出码；`runUi` 转交 `serveUi` |
| `src/server.ts` | 唯一出现 `Bun.serve` 的薄适配：拿锁、起服务、写握手行、起生命周期、关停 |
| `src/app.ts` | 请求管线：Host → 方法 → `/api/` 会话（T17：先 `findRoute`，只有 `bootstrap` 与 `control.bootstrap` 公开）→ CSRF 与正文（`control.bootstrap` 除外）→ 处理函数 → 安全头 → 访问记录 |
| `src/routes.ts` | 路由表与 `Route` 形状（`public?: true` 是唯一不验会话的口子）；本片四条：`bootstrap`、`control.bootstrap`、`api.ping.get`、`api.ping.post` |
| `src/envelope.ts` | 信封七字段：`ok`、`exit_code`、`data`、`output`、`messages`、`command`、`elapsed_ms` |
| `src/static.ts` | 静态资源的目录边界（路径只解码一次）、Content-Type 白名单与「只读普通文件」（T18：设备与管道文件一律 404 `not-a-file`） |
| `src/lockdir.ts` | 每仓库一个的锁目录 `<repo>/.agent/.ui.lock`；`acquireUiLock` 是 async，pid 活着且有端口时先探 127.0.0.1 上的该端口（T19 防 pid 复用） |
| `src/lifecycle.ts` | 空闲时限、stdin EOF、信号的关停 |
| `src/kernelenv.ts` | 内核子进程的环境：从 `process.env` 按名字排序复制，一律去掉 `TYPESAFE_API_KEY`，设 `CODEKIT_ACTOR=user-ui`，保留 `NoDefaultCurrentDirectoryInExePath` |
| `src/kernel.ts` | 子进程执行器：`runSupervised`、并发上限 4、FIFO 队列 16、路由时限、手工合成的取消信号、临时目录与输出上限 |
| `src/kernelenvelope.ts` | 信封七字段的拼装：`messages` 只留 `ERROR`/`WARN` 开头的行、`command` 是显示用 argv（游标与 transcript 打码）、`data` 用 pyjson 写出 |
| `src/redaction.ts` | 每条路由的脱敏白名单（`/config`、`/profiles`、`/secrets`）与 `usedByShape`；不合约束的白名单值照样遮成 `<redacted>` |
| `src/readroutes.ts` | 19 条读路由的表：参数校验、时限、白名单登记、合成 `/secrets` 的编排 |
| `src/watch.ts` | SSE 的输入监视：从 `@themis/contracts/status-inputs.json` 取名单，只 stat 名单上的路径生成指纹，跳过重解析点 |
| `src/events.ts` | SSE 广播中枢 `EventHub` 与 SSE 路由 `eventRoutes()`：快照与序号、去抖与共享、心跳、连接上限、会话失效断流 |
| `src/jobs.ts` | 作业表 `JobTable`：43 位随机作业号、容量 100 与淘汰、四种终态、取消 |
| `src/jobroutes.ts` | 作业路由 `jobRoutes()`：六 kind 的严格校验、`JOB_ARGV`/`JOB_TIMEOUTS`/`JOB_ALLOW`、创建/查询/取消 |
| `src/cursors.ts` | file 路由的句柄表：43 个字符的随机不透明句柄，最多 1024 项、LRU 淘汰，服务退出全部失效 |
| `src/localhttp/` | 不依赖 Bun 的安全基线：令牌、会话、控制门、Host/Origin/CSRF、安全头、正文上限、访问记录 |

`src/localhttp/` 只许导入 `node:*`、`@themis/base/*` 与它自己的相对路径，也不碰 Bun 的全局对象（源码卫生测试 `localhttpViolations` 强制）：迁移第 ③d 步整体搬进 `@themis/base/localhttp` 时只是机械地移动文件。

## 安全基线

- **只绑 127.0.0.1**：Host 必须整串等于 `127.0.0.1:<port>` 或 `localhost:<port>`，别的 Host 一律 403（防 DNS 重绑定）。
- **一次性引导地址**：握手行给出 `http://127.0.0.1:<port>/bootstrap/<nonce>`，60 秒内只能用一次；成功时 302 到 `/` 并带上会话 cookie `themis_session=<令牌>; HttpOnly; SameSite=Strict; Path=/`（没有 Max-Age、没有 Secure）。过期、用过、不存在三种拒绝返回同一个 404 响应。
- **控制接口**：`POST /control/bootstrap` 只认 `X-Themis-Control` 头里的令牌（从不看 cookie），恒定时间比较；连续 5 次失败锁 1 秒，之后翻倍、60 秒封顶，锁定期内对的令牌也回 429 并带 `Retry-After`，且不计数；成功之后计数清零。这道门是穷举的三道（Host、`controlOriginAllowed`、令牌门）：**不读正文，也不做 CSRF 三查**——外壳发请求时带不带正文、`Content-Type`、`X-Themis-UI` 没有核实过（站主记录 F9），豁免之后两种外壳都能 reauth；Origin 是别的站点仍 403 且不计入限速。
- **CSRF**：POST 要 Origin 同源、`X-Themis-UI: 1`、`Content-Type` 的媒体类型是 `application/json`，分别不对时 403、403、415，处理函数不运行。这一条只管 API 的写路由（`POST /api/v1/ping`）；`POST /control/bootstrap` 豁免，理由见上面「控制接口」。
- **安全响应头**：每一份响应都带逐字固定的 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`；API、引导、控制与错误带 `Cache-Control: no-store`，静态资源带 `no-cache`；不开 CORS（`Access-Control-*` 一律删掉）。
- **请求体上限**：服务自己数到 64 KiB（65536 字节）加 1 就停，Content-Length 声明超限时一个字节也不读；坏 UTF-8、不是 JSON、空正文都是 400 且不回显原值。
- **静态资源边界**：原始路径上先拒绝 `%2f`、`%5c`、`%2e`、`%00`，之后 `decodeURIComponent` 只解一次；解码后再逐类查反斜杠、控制字符、空段（UNC）、`.`/`..`、盘符、冒号（ADS）、末尾的点或空格，再用目录边界、重解析点（junction）与 realpath 三道关口把 `--assets` 之外的字节挡住。
- **访问记录**：只有路由名、状态码与耗时，只在内存里；路由名不符合 `^[a-z][a-z0-9.-]*$` 的一律记成 `invalid-route-name`，所以 nonce、令牌、cookie 与请求正文都进不了日志。stdout 只有握手一行。

## 最小 API

```
GET  /bootstrap/<nonce>   一次性引导地址：302 到 / 并带会话 cookie（只验 Host）
POST /control/bootstrap   换引导地址：作废全部会话与 nonce，200 信封 data 为 { bootstrap }（只带对令牌，不读正文）
GET  /api/v1/ping         要会话：200 信封 data 为 { posts }
POST /api/v1/ping         要会话、CSRF、JSON 对象正文（不超过 64 KiB）：posts 加 1
```

本片加的 19 条只读数据路由：全部 GET、全部要会话，每条起一个内核子进程；查询参数与路径参数在起子进程之前校验，不合格回 400（所有位置参数都由正则保证不以 `-` 开头，选项的值一律写成 `--opt=值`）。括号里是该路由的时限。

```
GET /api/v1/meta                                          --version                                  （15 秒）
GET /api/v1/status                                        status --json                              （30 秒）
GET /api/v1/attempts[?task=<task>]                        logs list --json [--task=<task>]           （30 秒）
GET /api/v1/attempts/<task>/<attempt>                     logs show <task>/<attempt> --json           （30 秒）
GET /api/v1/attempts/<task>/<attempt>/file?path=&cursor=[&follow=1]  logs cat <task>/<attempt> <path> --json [--complete-lines]     （60 秒）
GET /api/v1/usage                                         logs usage --json [--transcript=…]          （120 秒）
GET /api/v1/config                                        config show --json                          （30 秒）
GET /api/v1/config/validate                               config validate --json                      （30 秒）
GET /api/v1/config/history                                config history --json                       （30 秒）
GET /api/v1/config/history/<n>                            config history show <n> --json              （30 秒）
GET /api/v1/roles                                         config role show --json                     （30 秒）
GET /api/v1/profiles                                      config profile show --json                  （30 秒）
GET /api/v1/presets                                       config preset list --json                   （30 秒）
GET /api/v1/presets/<a>/diff/<b>                          config preset diff <a> <b> --json            （30 秒）
GET /api/v1/runtimes                                      config runtime list --json                  （30 秒）
GET /api/v1/plugins                                       plugins list --json                         （30 秒）
GET /api/v1/plugins/<id>                                  plugins show <id> --json                    （30 秒）
GET /api/v1/secrets                                       合成：config show --json 与 config profile show --json 收名单，再逐条 config secret check（每条 30 秒、整条 120 秒）
GET /api/v1/secrets/<name>                                config secret check <name>                  （30 秒）
```

`meta` 与 `/secrets` 的 `data` 由服务合成（分别是 `{version, repo_name}` 与 `{"secrets":[…]}`），其余路由的 `data` 是内核 stdout 的 JSON。`/api/v1/attempts/<task>/<attempt>/file` 给界面的 `next_cursor` 是 43 个字符的随机不透明句柄，内核游标只存在服务内存里（服务退出全部失效）。

第 5 片加的预览与 12 条写路由：全部要会话、CSRF 与 JSON 对象正文，参数在起子进程之前校验，不合格回 400（提示固定、不回显请求里的值）。执行用同一个 `validateWriteArgs`/`buildWriteArgv`，起的命令行是基础 argv 加 `--expect-state=<state>`（`needs_yes` 为真才加 `--yes`）。

```
POST /api/v1/preview                       基础 argv 加 --dry-run --json（预览，30 秒；回 {preview, confirmation}）
POST /api/v1/roles/<role>                  config role set <role> <target>（90 秒）
POST /api/v1/presets/<name>/use            config preset use <name>（90 秒）
POST /api/v1/presets/<name>/save           config preset save <name>（90 秒）
POST /api/v1/presets/<name>/remove         config preset remove <name>（90 秒）
POST /api/v1/config/rollback/<n>           config rollback <n>（90 秒）
POST /api/v1/plugins/<id>/enable           plugins enable <id>（90 秒）
POST /api/v1/plugins/<id>/disable          plugins disable <id>（90 秒）
POST /api/v1/profiles/<id>/add             config profile add <id> --runtime=<r> --model=<m> [--thinking=<t>] [--credential-env=<名>]…（90 秒）
POST /api/v1/profiles/<id>/edit            config profile edit <id> [--runtime=] [--model=] [--thinking=] [--credential-env=<名>]…（90 秒）
POST /api/v1/profiles/<id>/remove          config profile remove <id>（90 秒）
POST /api/v1/runtimes/<id>/add             config runtime add <id> --adapter=<a> [--command=<JSON.stringify(command)>] [--force]（90 秒）
POST /api/v1/runtimes/<id>/remove          config runtime remove <id>（90 秒）
GET  /api/v1/operations/<id>               查询一次写操作的结果（八键操作记录，不套信封、不套 data）
```

预览与写操作的语义见下面「写操作」一节。

状态码：201 作业创建成功（创建动作产生了一个可寻址的新资源，语义上就是 201；作业失败一律走 4xx/5xx，201 只出现在这里）；400 请求体不是合法的 JSON、查询参数或路径参数不合格、作业参数不合格（都不起子进程）；401 未认证；403 请求被拒绝（Host、Origin、CSRF、控制令牌、静态越界）；404 没有这个接口或没有这个作业（引导地址失效也回 404）；405 只支持 GET 与 POST（带 `Allow: GET, POST`）；409 句柄无效或内核报「游标对应的文件已变化」（提示「游标无效或文件已变化，请从头读取」）、取消一个已结束的作业（提示「作业已经结束」）、确认号无效/已过期/已用过或与预览参数不符（提示见「写操作」）、写命令退出 4 的 stale（`exit_code` 是 4 的七字段信封）；413 请求体超过 64 KiB；415 只收 `application/json`；429 控制令牌失败次数过多（带 `Retry-After`）；500 服务内部错误（起不了子进程、要 JSON 的命令退出 0 但 stdout 不是合法 JSON、stdout 超过 32 MiB 或 stderr 超过 1 MiB、处理函数抛错）；503 队列满、服务正在关闭、作业表满、执行器收不了或 SSE 订阅数达到上限（都带 `Retry-After: 2`）；504 命令超时（信封的 `exit_code` 是 null，`messages` 只有一行「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」）。命令退出非 0 一律回 200（信封 `ok` 为 false、`exit_code` 原样）。服务自己产生的错误一律走同一个错误信封。

## 实时通道（SSE）

```
GET /api/v1/events   要会话：text/event-stream，先发一份全量快照并带序号，之后只在名单上的输入变了才推一份整份新信封
```

- **报文格式**：流一打开先写 `retry: 3000` 与一个空行；每条事件写 `id: <序号>`、`event: snapshot` 或 `event: update`，再写若干行 `data: <信封正文的一行>`，最后一个空行；心跳是一行 `: hb` 加一个空行。`data` 拼回来的文本与 `/api/v1/status` 的正文去掉末尾换行后逐字节相同（同一套脱敏）。
- **序号**：hub 内单调递增，服务启动后从 1 起；每产生一份内容不同的信封加 1，内容相同就不推也不加号。每次订阅（含重连、带 `Last-Event-ID`）第一条都是 snapshot，带当时的序号。
- **监视与去抖**：只 stat `@themis/contracts/status-inputs.json` 名单上的输入（`.agent/runs` 之下），每 2 秒一轮、去抖 300 毫秒、同一时刻最多一次 status，多个订阅者共用一次 status；没有订阅者就停。
- **心跳与订阅上限**：每 15 秒写一行 `: hb`。**订阅上限**：全局同时开着 16 个、每个会话 4 个；超限回 503 带 `Retry-After: 2`，不挤掉已有的订阅，关掉一条名额立刻还回来。会话作废（`revokeAll`，含控制令牌换发引导地址）、服务关停与空闲退出时主动关流并清定时器；心跳写失败（客户端消失）立刻清理。
- **连接空闲超时**：SSE 订阅，与由内核子进程应答的请求（19 条读路由、预览、12 条写路由）对这一条请求调 `server.timeout(req, 0)`，只关掉这条连接的空闲超时；全局 `idleTimeout` 生产路径保持缺省（服务端写数据不重置空闲计时）。

## 作业

```
POST /api/v1/jobs                     要会话、CSRF、JSON 对象正文：创建一个作业，回 201
GET  /api/v1/jobs/<id>                要会话：查询作业（正文是八键作业对象，不套信封）
POST /api/v1/jobs/<id>/cancel         要会话、CSRF、JSON 对象正文：取消作业
```

- **六类 kind 与 argv**（时限秒，前面由执行器补上 python、kernel、`--repo`、仓库）：`doctor` → `config doctor --json`（600）；`doctor-record` → `config doctor --record=<record> --json`（600）；`runtime-scan` → `config runtime scan --json`（150）；`runtime-probe` → `config runtime probe <runtime> --json`（150）；`models` → `config models <runtime> --json`（120）；`search` → `logs search --json [--task=<task>] [--max=<max>] -- <pattern>`（180，pattern 是唯一放在 `--` 之后的参数）。
- **严格校验**：正文必须是 JSON 对象、kind 在六个之内、键恰好、类型与取值都合格（record 过 `PLAN_KEY_RE`、runtime/task 过 `TASK_ID_RE`、max 是 1–1000 的整数、pattern 是 1–512 个码点且不含控制字符与孤立代理项）；每一类失败都回 400，提示固定、不回显请求里的值、不起子进程。pattern 的正则语法不由服务校验，语法错由内核报。
- **作业号与容量**：43 位 base64url 随机（不可猜）；内存表容量 100，满了淘汰最早结束的终态作业，没有可淘汰的回 503；创建之前先看执行器还能不能收，收不了回 503 且不建作业。
- **创建与查询的正文**：都是同一个八键作业对象 `{id, kind, state, reason, created_ms, started_ms, finished_ms, envelope}`，**不套七字段信封、不套 `data`**；创建成功的当下 `state` 是 `queued`，`reason`/`started_ms`/`finished_ms`/`envelope` 是 null（键都在）。
- **状态机与取消**：queued → running → 四种终态之一（`succeeded`/`failed`/`cancelled`/`timed_out`）；取消排队中的不起子进程，取消在跑的结束整棵进程树（CTRL_BREAK、宽限 2 秒、再 terminateJob），取消已结束的回 409。结果与读路由同一套二道脱敏，`JOB_ALLOW` 六类全是 undefined（一律遮）。

## 凭据录入与控制取消

```
POST /api/v1/secrets/<name>/entry   要会话、CSRF、JSON 对象正文（必须是空对象）：起一个凭据录入作业，回 201 与 { job, url }
POST /control/jobs/<id>/cancel     控制接口（只带对令牌，不读正文）：取消一个作业，回 200 与当时的八键作业对象
```

- **录入作业**（`src/secretentry.ts`）：argv 恰好是 `config secret set <name> --no-browser --timeout=600`（没有 `--verify`、没有 `--tty`，`--timeout` 恒为页面时限 600 秒，不被测试入口的时限覆盖改写）。校验次序是正文 → 凭据名 → 执行器 → 作业表，任何一关不过都不起子进程：正文不是对象回 400「请求体必须是 JSON 对象」、带任何键回 400「请求体含有未知键」、名字不过 `allowEnvName` 回 400「凭据名不合法」；执行器收不了回 503「服务繁忙，请稍后重试」、作业表满回 503「作业表已满，请稍后重试」（都带 `Retry-After: 2`，且都不建作业）。`secret-entry` **不并进** `POST /api/v1/jobs` 的 kind 名单（四张 `JOB_*` 表仍是六项，提交它回 400「kind 不合法」）。
- **一次性页面地址**：内核把地址以一行 JSON 写到 stderr，服务在子进程还活着的时候从 stderr 读它，只认整串匹配 `^http://127\.0\.0\.1:(\d{1,5})/([A-Za-z0-9_-]{32})$` 且端口在 1–65535 的第一条完整行（`@` 别处、带 `?` 或 `#`、多一段路径、31/33 个字符的令牌、`localhost`、端口 0/65536/99999 都不算握手）。地址只活在这一次请求的局部变量里，**不挂到 `JobRecord` 或任何表上**：`GET /api/v1/jobs/<id>`、SSE、`messages`/`command` 与访问日志都拿不到它；握手行以 `{` 开头，照 `messages` 的规则也进不去。
- **三种结束**：从请求到达起最多等 15 秒（排队时间算在内），到点先 `settle` 成 `timed_out` 再 abort 子进程，回 504；握手之前子进程就结束（退出码不论、起不了子进程、输出超限）回 502；服务关停中回 503；客户端先断开关乎作业终态 `cancelled`、不回响应。收到合格握手回 **201**，正文是 `{job, url}`（`job` 是八键作业对象，不套七字段信封、不套 `data`）。
- **终态与重查**：状态仍是 queued → running → 四种终态，「等待保存」就是 `running`，不加新状态。终态信封七字段齐全，`data` 一律是 `{set, check}`：`set` 是 `config secret set` stdout 的白名单投影（只留实际出现的 `name`/`stored`/`backend`/`error`，恒为 null 的 `verified` 丢掉），`check` 是 `config secret check <name>`（不带 `--json`）经 `secretCheckData` 的投影（`name`、`source`、`store_mode`、`system_backend`，没有 `file_dir`）。重查只在收到过合格握手的作业上做，用一个只跟服务关停走的信号（取消或超时之后也照样跑得完，界面可以再读 `GET /api/v1/secrets/<name>`）。
- **落盘**：stderr 文件在服务私有的临时目录里（读完删），地址在 `%TEMP%` 里待到作业结束；凭据落在内核的凭据库里（`CODEKIT_SECRET_STORE` 决定 file 还是系统后端），服务不经手值。
- **控制门按 `Route.control` 统一判断**：`routes.ts` 的 `Route` 加 `control?: true`，`app.ts` 的管线对 `control === true` 的路由一次过 Origin（`controlOriginAllowed`，不过 403 且不计入令牌限速）与控制令牌（`ControlGate`，403 或 429 带 `Retry-After`）两道，两道都过就跳过 CSRF 与读正文（`body` 传 `undefined`）。原来按路由名 `control.bootstrap` 的两处特判删掉了：后加的控制路由不会绕过令牌。`control.bootstrap` 仍是 `public: true` 加 `control: true`（`routes.ts` 里 `public: true` 恰好两处），处理函数只剩业务。

## 日志跟随

```
GET /api/v1/attempts/<task>/<attempt>/file?path=<p>&follow=1[&cursor=<句柄>]   logs cat <task>/<attempt> <p> --json --complete-lines [--cursor=<内核游标>]   （60 秒）
```

- **只认字面 `1`**：`follow` 与 `path`、`cursor` 同样从查询参数取（不另查重复参数，重复时取第一个）。取值不是字面 `1`（`0`、`true`、空串、`2`、`yes`、`01`）→ 400「follow 参数不合格（只接受 1）」，不起子进程、不回显请求里的值。不带 `follow` 就是普通翻页，行为逐字节不变。
- **只给 JSONL**：`follow=1` 而路径不是 `.jsonl`（判定大小写不敏感，`LOG.JSONL` 放行）→ 400「只有 JSONL 文件支持跟随」，不起子进程、不回显路径。普通文本（`.txt`、`.json`）不支持跟随：不悄悄退化成从头读（退化后每次轮询都要整份脱敏，最多 64 MiB），也不用 409（界面对 409 的约定是「从头读」）。
- **只给已经写完的行**：内核的 `--complete-lines` 把「最后一行还没有换行」的半行整行扣下，写完之后才从第 1 片起给。一行超过一页（256 KiB 个字符）时照样每次给一片、发一个新句柄，直到最后一片。
- **末尾也发句柄**：跟随时只要内核给了非空的游标，`next_cursor` 一律是 43 个字符的随机不透明句柄，不看 `done`——界面拿着它才能继续要新行。非跟随（普通翻页）照旧：`done` 为真时 `next_cursor` 是 `null`。
- **空页复用句柄**：没有新行时内核回空页（`lines` 是空数组），这时原样发回请求里的那个句柄，不发新句柄、句柄表项数不变——空闲的长时间跟随不会把句柄表撑爆（表仍是 1024 项、LRU 淘汰，被淘汰的旧句柄回 409）。有内容的一页才发新句柄，旧句柄留在表里（不丢）：请求被取消或响应丢了，带旧句柄重试照样接着给。
- **轮询下限**：跟随响应的 `data` 末尾多一个键 `poll_after_ms`，值 2000（毫秒），与 503 的 `Retry-After: 2` 一致；非跟随的 `data` 里没有这个键。**服务不强制下限**：不按句柄记时间、不回 429；轮询太快由执行器兜底——同时在跑 4 个、FIFO 队列 16 个，队列满回 503 带 `Retry-After: 2`，前端照它等一会儿、带同一个句柄重试（句柄在排队失败时不受影响，不丢行也不重复）。
- **409 的已知情形**：句柄格式不对、不在表里、绑定与本次请求不一致，以及内核报「游标对应的文件已变化」（文件被替换、截短、原地改写）都回 409「游标无效或文件已变化，请从头读取」，界面从头跟随。已知的一种：普通翻页拿到的句柄停在一条没写完的半行中间（行内位置不为 0），之后改用跟随，内核判这个游标失效 → 409，界面收到就从头跟随即可。
- **并发轮询同一个句柄可能重复给行**：内核游标按文件位置记，两次并发的请求可能给出同样的行；界面要串行轮询（等上一次响应回来再排下一次），服务不加锁。按 2000 毫秒的下限，一个跟随者每分钟最多 30 次轮询、每次起 1 个 `logs cat` 子进程。

## 内核子进程

- **命令行**：`[python, kernel, "--repo", repo, ...argv]`，argv 是列表、不经 shell，cwd 是仓库目录；`python` 与 `kernel` 取自 `UiArgs`。
- **环境**（`src/kernelenv.ts`）：从 `process.env` 按名字排序整份复制，然后一律去掉名字大写后等于 `TYPESAFE_API_KEY` 的变量（不给任何路由开例外），设 `CODEKIT_ACTOR=user-ui`，保留 `NoDefaultCurrentDirectoryInExePath`（Windows 上没有就补成 `1`），其余原样。不加 `PYTHONUTF8=1`：内核的四个入口（`pi_dispatch`、`kit_logs`、`kit_config`、`kit_plugins`）都已把 stdout 与 stderr `reconfigure(encoding="utf-8", errors="replace")`，子进程 stdout 就是 UTF-8。
- **执行器**（`src/kernel.ts`）：`runSupervised`，`handleSignals: false`、`grace: 2`；同时最多 4 个子进程在跑，FIFO 队列最多 16 个在等，队列满回 503 带 `Retry-After: 2`；排队中被取消的请求直接出队、不起子进程。取消用手工合成的 AbortSignal（请求的 signal 与服务关停的 controller，任一 abort 就取消）；客户端断开时结束整棵树，不再写响应。超时由 `runSupervised` 处理：先 CTRL_BREAK，宽限 2 秒之后 terminateJob，整棵树结束（Job 带 KILL_ON_JOB_CLOSE）。服务关停时先拒绝新请求、清空队列，再取消在跑的，最后删掉临时根目录。
- **临时目录**：服务启动时在系统临时目录下 `mkdtemp` 一个 `themis-ui-` 前缀的服务私有根目录，每次运行在其下再 `mkdtemp` 一个子目录放 stdout 与 stderr，读完删子目录，关停删整个根目录。不写进 `.agent/runs/_tmp`。
- **二道脱敏**：响应先过 `redactJson(data, 该路由的白名单)`，再把 `output`、`messages`、`command` 里的每个文本过 `redactSecrets`。`messages` 只留 stderr 里以 `ERROR` 或 `WARN` 开头的行，其余行一律丢掉；`command` 是显示用 argv（不含 python、kernel、`--repo` 与仓库路径，`--cursor=` 与 `--transcript=` 的值打码）。

### 决策 API 的 key：`/secrets` 与 `/config` 显示的不是 env

服务不把 `TYPESAFE_API_KEY` 传给内核（照 T5 一律去掉，与路由无关），所以 `/secrets` 与 `/config` 里这把 key 的 source **不会**是 env——这与用户在终端里跑同一条 `config secret check` 看到的结果不一样。

原因：桌面应用从开始菜单或资源管理器起，它的环境来自登录时的用户与系统环境变量；用户在终端里临时设的、或写在 PowerShell profile 里的变量，桌面应用看不到。所以「这把 key 在不在环境变量里」的权威说法，只有用户在自己的终端里跑 `config secret check` 给出的那一个；服务即使不去掉它，两边也对不上。

因此：界面上这把 key 显示成「环境变量：服务不检查，以终端为准」（这段文案属于前端，不在本片），要确认它的真实来源请以终端里 `config secret check` 的输出为准。

## 写操作

预览 → 确认号 → 带令牌执行 → 操作终态（`POST /api/v1/preview` 与 12 条写路由）。服务只校验参数形状，组合规则（该给哪些权限、缺什么、能不能切）全交给内核；提示固定、不回显请求里的值，不合格不起子进程。`profile` 与 `runtime` 的五条写路由（T020）与本片七条走同一条链：同样的预览 → 确认号 → 带令牌执行 → 操作终态。

- **预览**（`POST /api/v1/preview`）：正文 `{action, args}`，起基础 argv 加 `--dry-run --json`（30 秒，用请求自己的 signal，不拿锁、不写任何文件）。退出 0 时核对内核预览的 `dry_run`/`action`/`state`/`needs_yes`，拿掉 `state` 令牌、剩下的过 `PREVIEW_ALLOW` 二道脱敏，回 200、`data` 是 `{preview, confirmation}`（`confirmation` 是 43 位 base64url 确认号）；预览不合格（`action` 对不上、`state` 形状不对等）回 500「内核的预览不合格」、不发号；内核退出非 0 回 200、`ok` 为假、不发号。
- **确认号**：有效期 60 秒（从签发算起），只在内存里、不绑会话，服务退出即失效；容量 100，满了先清过期的、再挤掉最早发出还没用的那个。执行时把 `confirmation` 带回：缺失、不是字符串、格式不对、不在表里、已过期或用第二次 → 409「确认号无效、已过期或已用过：请重新预览」；与预览时的参数不符 → 409「确认号与这次请求的参数不符：请重新预览」且**不**消耗这个号。
- **执行**：12 条写路由共用同一个 `validateWriteArgs`/`buildWriteArgv`，起的命令行是基础 argv 加 `--expect-state=<state>`（预览给的 state 令牌原样带上；界面从 `command` 看到的只是占位 `--expect-state=<state>`，令牌不外泄），预览的 `needs_yes` 为真才加 `--yes`（plugins 的 `needs_yes` 恒为假），不带 `--json`；时限 90 秒。退出 0 → 200；退出 4（内核报「在预览之后被改过」）→ 409 七字段信封（`exit_code` 是 4，界面据此重新预览）、操作记 `stale`；其他非 0 → 200、`ok` 为假、操作记 `failed`；起不了子进程或输出超限 → 500。
- **操作记录**（`GET /api/v1/operations/<id>`）：每次执行落一条八键操作记录 `{id, action, state, reason, created_ms, started_ms, finished_ms, envelope}`（`id` 就是确认号，`envelope` 是已脱敏的完整信封），不套信封、不套 `data`；格式不对与查不到回同一个 404「没有这个操作」；容量 100，满了淘汰最早结束的终态记录，没有可淘汰的回 503。
- **profile 与 runtime 的五条**（T020）：路径参数 `<id>` 压过正文里的同名键（`mergeArgs`），正文里的 `confirmation` 不进 args。`profile.add` 必填 `runtime` 与 `model`、可选 `thinking` 与 `credential_env`；`profile.edit` 只必填路径 `profile`（一个可选项都不给时服务照形状放行，内核预览退出 2、提示「至少给一项」，回 200、`ok` 为假、不发确认号）；`profile.remove` 只必填 `profile`；`runtime.add` 必填 `adapter`、可选 `command` 与 `force`；`runtime.remove` 只必填 `runtime`。选项的值一律写成 `--opt=值`、次序固定；`--command` 的值是 `JSON.stringify(command)`；`--force` 是不取值的开关。校验：`profile`/`runtime` 过 `TASK_ID_RE`，`model` 在第一个 `/` 处切成两段都过 `MODEL_TOKEN_RE`，`thinking` 七选一，`adapter` 四选一（`pi`/`claude-code`/`codex`/`opencode`），`command` 每项 1–1024 码点，`credential_env` 每项过 `allowEnvName`；绝对路径与疑似凭据交给内核判定。
- **两资源令牌**：`runtime add` 带 `--command` 与 `runtime remove` 的 state 令牌带 config 与 local 两段（`v1;config=<C>;local=<L>`，本机文件不存在时是 `local=absent`），`runtime add` 不带 `--command` 与其余十条只有 config 段；令牌形状由内核给，服务按 `STATE_RE` 核对。改本机文件 `.agent/dispatch.local.json` 会让 local 段失效，执行回 409。
- **`credential_env` 的三种写法**：缺省（args 里没有这个键）时 argv 不带 `--credential-env`、内核不改这一项；非空数组时每项一个 `--credential-env=<名>`、内核整份替换（保持请求次序、不去重、不设个数上限）；空数组回 400「credential_env 不合法」、不起子进程（内核没有清空的写法，见「已知限制」）。
- **断开不取消**：写运行用服务私有的 AbortController，客户端的 `request.signal` 不传给执行器——界面断线时子进程不被杀、终态照记，界面靠操作号把结果读回来（写入可能已部分完成，按「结果未知」重读）。
- **503 与 504**：队列满或服务正在关停回 503 带 `Retry-After: 2`（不消耗确认号，重试不丢号）；超时回 504、操作记 `timed_out`（整棵进程树被结束）。有写在跑时服务不因空闲退出（空闲判定看 `operations.active()`）。

## 测试

```
cd ts
node node_modules/vitest/vitest.mjs run packages/ui/test   # 本包（含起真 Bun 进程的黑盒用例）
node node_modules/typescript/bin/tsc -p tsconfig.json      # 类型
```

纯函数（`localhttp-*.test.ts`、`static-paths.test.ts`、`app.test.ts`、`lockdir.test.ts`、`lifecycle.test.ts`）在 Node 下跑，正好证明它们不依赖 Bun；`service.test.ts` 与 `launcher.e2e.test.ts` 起真的服务进程，用原始套接字发 HTTP 请求。测试从不发控制台信号，收进程靠关 stdin（stdin EOF）或 kill。

## 不是安全沙箱

本服务是桌面端的本地后端，不是隔离边界：它只保证「本机响应不给浏览器别的能力」与「静态资源出不了 `--assets`」。跑什么样的代码、能读哪些文件，由操作系统与桌面应用的外壳决定。

## 已知限制

- 读路由的子进程并发上限 4、队列 16、各路由时限与输出上限（stdout 32 MiB、stderr 1 MiB）**不给用户配**：只开放给测试入口 `ServeOverrides`，对用户可配留给后面一片。SSE 的订阅上限（全局 16、每会话 4）、stat 间隔、去抖、心跳与作业的并发/队列/时限同样只开放给测试入口，CLI 与环境变量碰不到。
- 本片不做凭据录入作业，也不缓存脱敏结果。写路由覆盖 12 条（role set、preset use|save|remove、config rollback、plugins enable|disable、profile add|edit|remove、runtime add|remove）；`credential_env` 清不空——内核没有清空的写法（给空串会变成 `[""]` 被整份校验拒掉），服务对空数组回 400「credential_env 不合法」，真要清空由站主另开一轮给内核加选项。确认号表与操作表只在内存里，服务退出（含空闲退出）即失效，界面要按「结果未知」重读。file 路由的跟随只给 JSONL（`follow=1`），普通文本明确回 400，见「日志跟随」一节。
- `file` 路由的句柄只在内存里：服务重启之后旧句柄一律 409（「游标无效或文件已变化，请从头读取」），界面要重新从头读取。
- `/secrets` 与 `/config` 里 `TYPESAFE_API_KEY` 的 source 不会是 env（原因见上一节），与终端里同一条命令不同。
- **输出上限的磁盘上界（H1）**：执行器边写边看，子进程跑着的时候每 100 毫秒看一次 stdout/stderr 的大小，超限就中止整棵树；两次轮询之间写完的由结束后的兜底检查抓住。临时目录里单个输出文件的磁盘上界约为「上限 + 写速度 ×（轮询间隔 100 毫秒 + 宽限 2 秒）」，不是硬上限。
- **SSE 的 stat 成本**：有订阅开着时每 2 秒对 `.agent/runs` 之下的名单路径做一次 stat/列目录（不递归、跳过重解析点），名单很大时这一轮有成本；没有订阅者就停。
- **作业表只在内存里**：服务退出（含空闲退出）作业表随进程消失，不写 `.agent/`；关停时没结束的作业由执行器结束子进程树。
- Bun 自己生成的三种响应**不带安全头**（Content-Length 超过 `maxRequestBodySize` 的 413、畸形请求行的 400、分块传输超过 Bun 上限的 413）：这些是 Bun 生成的纯文本，没有攻击者能控制的 HTML，所以不额外处理。服务自己的计数（64 KiB 加 1 就停）先于 Bun 的上限触发，`maxRequestBodySize` 设成 131072（64 KiB 的两倍）作为第二道防线。
