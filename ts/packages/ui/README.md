# @themis/ui

桌面端的本机服务（`docs/themis-tally-3.0-桌面端.md`，第 7 版 §0.0a）：Bun 运行，只绑 127.0.0.1，是桌面端唯一的后端，也是安全边界（D4）。本片（D1-B 第 1 片）是服务骨架、安全基线与握手；数据路由（`/api/v1/meta`、`status`、`jobs`、SSE）与子进程、二道脱敏是第 2、3 片的事。

- 入口：`src/main.ts` 的 `runUi`（参数检查）转交 `src/server.ts` 的 `serveUi`。内核仓库里经 `pi_dispatch.py ui --desktop --assets <目录> …` 转交（调度器第 73 轮）；桌面应用里外壳直接起打包好的程序（T6）。
- 本包不在内核禁区里（迁移计划第 69 轮），经 hub 派给执行器；`package.json` 与 `bun.lock` 的登记由规划端维护（禁区里的工作区文件）。

## 结构

| 文件 | 职责 |
| --- | --- |
| `src/main.ts` | `UiArgs`、`checkArgs`、退出码；`runUi` 转交 `serveUi` |
| `src/server.ts` | 唯一出现 `Bun.serve` 的薄适配：拿锁、起服务、写握手行、起生命周期、关停 |
| `src/app.ts` | 请求管线：Host → 方法 → `/api/` 会话 → CSRF 与正文 → 处理函数 → 安全头 → 访问记录 |
| `src/routes.ts` | 路由表（本片四条：`bootstrap`、`control.bootstrap`、`api.ping.get`、`api.ping.post`） |
| `src/envelope.ts` | 信封七字段：`ok`、`exit_code`、`data`、`output`、`messages`、`command`、`elapsed_ms` |
| `src/static.ts` | 静态资源的目录边界（路径只解码一次）与 Content-Type 白名单 |
| `src/lockdir.ts` | 每仓库一个的锁目录 `<repo>/.agent/.ui.lock` |
| `src/lifecycle.ts` | 空闲时限、stdin EOF、信号的关停 |
| `src/localhttp/` | 不依赖 Bun 的安全基线：令牌、会话、控制门、Host/Origin/CSRF、安全头、正文上限、访问记录 |

`src/localhttp/` 只许导入 `node:*`、`@themis/base/*` 与它自己的相对路径，也不碰 Bun 的全局对象（源码卫生测试 `localhttpViolations` 强制）：迁移第 ③d 步整体搬进 `@themis/base/localhttp` 时只是机械地移动文件。

## 安全基线

- **只绑 127.0.0.1**：Host 必须整串等于 `127.0.0.1:<port>` 或 `localhost:<port>`，别的 Host 一律 403（防 DNS 重绑定）。
- **一次性引导地址**：握手行给出 `http://127.0.0.1:<port>/bootstrap/<nonce>`，60 秒内只能用一次；成功时 302 到 `/` 并带上会话 cookie `themis_session=<令牌>; HttpOnly; SameSite=Strict; Path=/`（没有 Max-Age、没有 Secure）。过期、用过、不存在三种拒绝返回同一个 404 响应。
- **控制接口**：`POST /control/bootstrap` 只认 `X-Themis-Control` 头里的令牌（从不看 cookie），恒定时间比较；连续 5 次失败锁 1 秒，之后翻倍、60 秒封顶，锁定期内对的令牌也回 429 并带 `Retry-After`，且不计数；成功之后计数清零。
- **CSRF**：POST 要 Origin 同源、`X-Themis-UI: 1`、`Content-Type` 的媒体类型是 `application/json`，分别不对时 403、403、415，处理函数不运行。
- **安全响应头**：每一份响应都带逐字固定的 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`；API、引导、控制与错误带 `Cache-Control: no-store`，静态资源带 `no-cache`；不开 CORS（`Access-Control-*` 一律删掉）。
- **请求体上限**：服务自己数到 64 KiB（65536 字节）加 1 就停，Content-Length 声明超限时一个字节也不读；坏 UTF-8、不是 JSON、空正文都是 400 且不回显原值。
- **静态资源边界**：原始路径上先拒绝 `%2f`、`%5c`、`%2e`、`%00`，之后 `decodeURIComponent` 只解一次；解码后再逐类查反斜杠、控制字符、空段（UNC）、`.`/`..`、盘符、冒号（ADS）、末尾的点或空格，再用目录边界、重解析点（junction）与 realpath 三道关口把 `--assets` 之外的字节挡住。
- **访问记录**：只有路由名、状态码与耗时，只在内存里；路由名不符合 `^[a-z][a-z0-9.-]*$` 的一律记成 `invalid-route-name`，所以 nonce、令牌、cookie 与请求正文都进不了日志。stdout 只有握手一行。

## 最小 API

```
GET  /bootstrap/<nonce>   一次性引导地址：302 到 / 并带会话 cookie（只验 Host）
POST /control/bootstrap   换引导地址：作废全部会话与 nonce，200 信封 data 为 { bootstrap }
GET  /api/v1/ping         要会话：200 信封 data 为 { posts }
POST /api/v1/ping         要会话、CSRF、JSON 对象正文（不超过 64 KiB）：posts 加 1
```

状态码：400 请求体不是合法的 JSON；401 未认证；403 请求被拒绝（Host、Origin、CSRF、控制令牌、静态越界）；404 没有这个接口（引导地址失效也回 404）；405 只支持 GET 与 POST（带 `Allow: GET, POST`）；413 请求体超过 64 KiB；415 只收 `application/json`；429 控制令牌失败次数过多（带 `Retry-After`）；500 服务内部错误。服务自己产生的错误一律走同一个错误信封。

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

Bun 自己生成的三种响应**不带安全头**（Content-Length 超过 `maxRequestBodySize` 的 413、畸形请求行的 400、分块传输超过 Bun 上限的 413）：这些是 Bun 生成的纯文本，没有攻击者能控制的 HTML，所以不额外处理。服务自己的计数（64 KiB 加 1 就停）先于 Bun 的上限触发，`maxRequestBodySize` 设成 131072（64 KiB 的两倍）作为第二道防线。
