# @themis/ui

桌面端的本机服务（`docs/themis-tally-3.0-桌面端.md`，第 7 版 §0.0a）：Bun 运行，只绑 127.0.0.1，是桌面端唯一的后端，也是安全边界（D4）。第 1 片是服务骨架、安全基线与握手；本片（D1-B 第 2 片）加 19 条只读数据路由：每条起一个内核 CLI 子进程（`<python> <kernel> --repo <仓库> <argv…>`，argv 是列表、不经 shell），响应先过 `redactJson` 再按路由登记的白名单做约束校验，file 路由给界面的是随机不透明句柄（内核游标只存在服务内存里）。SSE、作业、跟随、预览与写路由是后面几片的事。

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
GET /api/v1/attempts/<task>/<attempt>/file?path=&cursor=  logs cat <task>/<attempt> <path> --json     （60 秒）
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

状态码：400 请求体不是合法的 JSON、查询参数或路径参数不合格（不起子进程）；401 未认证；403 请求被拒绝（Host、Origin、CSRF、控制令牌、静态越界）；404 没有这个接口（引导地址失效也回 404）；405 只支持 GET 与 POST（带 `Allow: GET, POST`）；409 句柄无效或内核报「游标对应的文件已变化」（提示「游标无效或文件已变化，请从头读取」）；413 请求体超过 64 KiB；415 只收 `application/json`；429 控制令牌失败次数过多（带 `Retry-After`）；500 服务内部错误（起不了子进程、要 JSON 的命令退出 0 但 stdout 不是合法 JSON、stdout 超过 32 MiB 或 stderr 超过 1 MiB、处理函数抛错）；503 队列满或服务正在关闭（都带 `Retry-After: 2`）；504 命令超时（信封的 `exit_code` 是 null，`messages` 只有一行「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」）。命令退出非 0 一律回 200（信封 `ok` 为 false、`exit_code` 原样）。服务自己产生的错误一律走同一个错误信封。

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

- 读路由的子进程并发上限 4、队列 16、各路由时限与输出上限（stdout 32 MiB、stderr 1 MiB）**不给用户配**：只开放给测试入口 `ServeOverrides`，对用户可配留给后面一片。
- 本片不做 SSE（`/api/v1/events`）、作业（`/api/v1/jobs`）、跟随、预览、写路由与凭据录入，也不缓存脱敏结果。
- `file` 路由的句柄只在内存里：服务重启之后旧句柄一律 409（「游标无效或文件已变化，请从头读取」），界面要重新从头读取。
- `/secrets` 与 `/config` 里 `TYPESAFE_API_KEY` 的 source 不会是 env（原因见上一节），与终端里同一条命令不同。
- Bun 自己生成的三种响应**不带安全头**（Content-Length 超过 `maxRequestBodySize` 的 413、畸形请求行的 400、分块传输超过 Bun 上限的 413）：这些是 Bun 生成的纯文本，没有攻击者能控制的 HTML，所以不额外处理。服务自己的计数（64 KiB 加 1 就停）先于 Bun 的上限触发，`maxRequestBodySize` 设成 131072（64 KiB 的两倍）作为第二道防线。
