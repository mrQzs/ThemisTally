# TASK: t026-desktop-shell-host

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 038688fe7e55c16a5aa5413155fbcdb264e10887
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在 `desktop/shell` 里做出服务页用的宿主接口 `window.themisHost`（五个函数：`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`）：preload 把它暴露给渲染进程，主进程经 IPC 处理并调用本机服务与系统能力，控制令牌只留在主进程；同时修 T025 终审留下的三处小问题（`stopService` 对已退出的子进程挂死、窗口加载失败的判定、`core.test.js` 三条用例缺时限）。

## Non-goals
- 不做外壳页、`window.themisShell`、设置存盘、`openSettings()`；不做托盘、单实例、多仓库切换；不做 Electron Fuses、electron-builder、安装包、自动更新。
- 不改 `desktop/web`、`ts/**`、`scripts/**`、`docs/**`、`tests/**`；不改 `desktop/shell/package-lock.json`；不新增任何依赖。
- 不起真 Electron 窗口、不起真本机服务、不用真凭据；真窗口只能手工冒烟。
- 不做 reauth 的在途合并、`will-redirect` 拦截、窗口标题带凭据名、`busy` 时替页面取消作业。
- 不改 `desktop/shell` 已有六个纯模块的既有行为与既有测试（`src/args.js`、`src/python.js`、`src/handshake.js` 一行不动）。

## Repository facts
- 入口：`desktop/shell/main.js` 是 Electron 主进程入口，也是唯一允许 `require('electron')` 的 `src/**` 之外的文件；纯逻辑在 `desktop/shell/src/`（现有 `args.js`、`python.js`、`handshake.js`、`service.js`、`window.js`、`core.js`），测试在 `desktop/shell/tests/`（现有七份 `*.test.js` 与 `tests/fixtures/`）。
- 现有模块与符号（本片要改的四个）：
  - `src/window.js`：导出 `partitionName()`、`webPreferences(partition)`、`isServiceUrl(url, origin)`。`webPreferences` 恰好十键（`contextIsolation`、`sandbox`、`nodeIntegration`、`webSecurity`、`allowRunningInsecureContent`、`webviewTag`、`nodeIntegrationInWorker`、`nodeIntegrationInSubFrames`、`spellcheck`、`partition`），**没有** `preload` 键。
  - `src/core.js`：导出 `runShell({ argv, io, openWindow, spawn, env })`，兑现退出码 0/1/2；`openWindow` 的入参**只有** `{ bootstrap, origin }`；`io` 缺省是 `{ stdout: process.stdout, stderr: process.stderr }`。
  - `src/service.js`：导出 `serviceCommand`、`startService`、`stopService`。`stopService`（`src/service.js:90-129`）只 `child.stdin.end()` 后等 `exit`/`close` 事件，**不查** `child.exitCode`/`child.signalCode`：子进程已经退出时事件早已错过，Promise 永远不兑现（外壳挂死）。
  - `src/main.js`（`desktop/shell/main.js`）：窗口一建好就注册 `closed`，`loadURL` 的 reject 只看 `win.isDestroyed()`。
- T025 门禁（`tests/test_gate_t025_baseline.py`，R01 会跑）的硬约束，全部照旧有效：
  - `webPreferences("sess-abc")` 恰好十键（探针 P04）→ `webPreferences` 不改，留给凭据窗口；主窗口走新函数 `mainWebPreferences(partition, preloadPath)`（十键加 `preload`）。
  - `openWindow` 的参数恰好 `bootstrap`、`origin`（探针 P06 与 `tests/core.test.js:173-174`）→ 控制令牌走新的**可选**回调 `onServiceReady`，不传时照旧工作。
  - `require('electron')` 在 `main.js`、`src/**`、`tests/**` 里只许出现在 `main.js`（S03）→ preload 放**包根** `desktop/shell/preload.js`（不在 S03 的扫描范围内），放 `src/` 必红；新测试文件里也不许出现 `require('electron')` 这个字面串（用注入的假 require，模块名字面量写成 `"electron"`）。
  - `src/**` 与 `main.js` 里不许出现 `persist:`、`shell: true`、fs 的写函数、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`（S03 收窄后剩这 7 条；`http(s).request` 与 `openExternal` 两条已由站主在 4357dca 删除，本片由 T026 门禁按文件收紧）。**注释里也不许出现这些字样**（门禁扫的是文件全文）。
  - `main.js` 保留 15 个接线标记与两个 require（`src/core.js`、`src/window.js`）（S04）：`setApplicationMenu(null)`、`setPermissionRequestHandler`、`setPermissionCheckHandler`、`setWindowOpenHandler`、`"deny"`、`will-navigate`、`isServiceUrl`、`loadURL`、`session.fromPartition`、`new BrowserWindow`、`webPreferences`、`app.isPackaged`、`slice(2)`、`slice(1)`、`app.exit`。
  - README 的要点与 10 秒 / 30 秒时限不删（S05）：`npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、`退出码`、`install.js`、`node_modules/electron`、`冒烟`、10 秒、30 秒。
  - `scripts.test` 带 `--test-reporter=tap` 且显式列出 `tests/` 下每一个 `*.test.js`（S01/S02；开关写在文件清单之前）。
- 服务一侧的事实（只读参照，本片要用）：
  - 头名 `x-themis-control`（`ts/packages/ui/src/localhttp/control.ts:7`）；连续 5 次失败才锁定。
  - `POST /control/bootstrap`（`ts/packages/ui/src/routes.ts:12`、`:67-76`）作废旧会话与旧 nonce，回七字段信封（`ts/packages/ui/src/envelope.ts:5-30`），其中 `data.bootstrap` 是 `<origin>/bootstrap/<nonce>`。
  - 控制门（`ts/packages/ui/src/app.ts:126-138`）：Host → Origin（缺 Origin 放行，`ts/packages/ui/src/localhttp/guards.ts:47-50`；Host 认 `127.0.0.1:<port>`，`guards.ts:13-21`）→ 令牌；控制路由**不读正文**、不做 CSRF。
  - `POST /control/jobs/<id>/cancel`（`ts/packages/ui/src/jobroutes.ts:305-309`）：404 没有这个作业、409 作业已经结束、200 取消并等子进程结束（`jobroutes.ts:82-103`）。
  - 一次性页面地址形状：`^http://127\.0\.0\.1:(\d{1,5})/([A-Za-z0-9_-]{32})$`（`ts/packages/ui/src/secretentry.ts:32`），端口 1–65535（`:33-35`）；作业号 43 个 base64url 字符（`ts/packages/ui/src/jobs.ts:11`）。
  - 一次性页面是纯 HTML 表单、标题「Code-Kit 凭据」（`scripts/kit_config.py:1368-1392`、`:1402`、`:1467`）；页面手里的 url 与 jobId 由服务页给出，外壳不依赖 entry 的响应。
- 工具链与锁文件：门禁机 Node 24.19.0，`node --test` 默认 reporter 是 spec、只输出 `ℹ pass N`，**必须**带 `--test-reporter=tap` 才有 `# pass N`（`desktop/shell/package.json` 的 `scripts.test` 已带）；electron `44.9.0`（`desktop/shell/package.json`、`package-lock.json`），它没有 postinstall，单元测试不 `require('electron')`。
- 仓库外事实（站主 2026-11-06 已核实，照事实用）：
  1. sandbox 下 preload 只能 `require` electron 的 `contextBridge`、`crashRenderer`、`ipcRenderer`、`nativeImage`、`webFrame`、`webUtils`（以及 events/timers/url），**不能**用 CommonJS 把 preload 拆成多个文件；新版官方文档已收窄到只有 electron → preload 只 require electron 的写法在升级后仍成立。
  2. `electron@44.9.0` 的 `electron.d.ts`：`IpcMainInvokeEvent` 有 `sender: WebContents` 与 `readonly senderFrame: WebFrameMain | null`（`WebFrameMain.url`）；`shell.openExternal(url, options?)` 返回 `Promise<void>`；`shell.showItemInFolder(fullPath): void`；`dialog.showMessageBox(window, options)` 返回 `Promise<MessageBoxReturnValue>`（`response: number`）；`new Notification({ title, body }).show()`（构造参数可选，`show(): void`）；`BaseWindowConstructorOptions.parent?: BaseWindow`；`BrowserWindow` 有 `loadURL`（`Promise<void>`）、`focus()`、`isDestroyed()`；`webPreferences.preload` 是脚本的**绝对路径**；`Menu.setApplicationMenu(null)` 合法。
  3. Windows 上 `fs.realpathSync.native` 跟随 junction（`.agent` 里指到外面的 junction 解析到外面的真实路径）；`fs.realpathSync` 结果相同；`lstat` 把 junction 报成符号链接。
  4. 真 Electron 的运行时行为**未核实**（要起真窗口才知道）→ 只进 README 的手工冒烟，**不进 DoD**。
- 基线检查：基线 `4357dcacf07859bffca9ebd7348c133e924e8e69` 上 `desktop/shell` 已有 T025 的实现与七份测试；T025 attempt-003 的记录是 V01 `# tests 65 / # pass 65 / # fail 0`、R01 `753 passed`、G01 `11 passed`（出自 `.agent/reviews/t025-desktop-shell/attempt-003-hub.md`）。本片的门禁 `tests/test_gate_t026_baseline.py` 由门禁端写、内核做成基线提交，**基线上不存在**（G01 在基线上应失败）。

## Scope
- allowed_modified_files:
  - desktop/shell/README.md
  - desktop/shell/main.js
  - desktop/shell/package.json
  - desktop/shell/src/core.js
  - desktop/shell/src/service.js
  - desktop/shell/src/window.js
  - desktop/shell/tests/core.test.js
  - desktop/shell/tests/service.test.js
  - desktop/shell/tests/window.test.js
  - desktop/shell/preload.js
  - desktop/shell/src/control.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/ipc.js
  - desktop/shell/tests/control.test.js
  - desktop/shell/tests/fixtures/fake-control-server.js
  - desktop/shell/tests/host.test.js
  - desktop/shell/tests/hostcheck.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/preload.test.js
- allowed_new_files:
  - desktop/shell/preload.js
  - desktop/shell/src/control.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/ipc.js
  - desktop/shell/tests/control.test.js
  - desktop/shell/tests/fixtures/fake-control-server.js
  - desktop/shell/tests/host.test.js
  - desktop/shell/tests/hostcheck.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/preload.test.js
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t026_*.py
  - tests/**
  - desktop/shell/package-lock.json
  - desktop/web/**
  - ts/**
  - scripts/**
  - docs/**
  - .agent/**
  - AGENTS.md
  - CLAUDE.md
- dependency_changes: forbidden（`desktop/shell/package.json` 只许改 `scripts.test`，`devDependencies` 仍是 `{"electron": "44.9.0"}`，锁文件一个字节都不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、宿主接口 `window.themisHost`（五个函数）

- 名字是 `themisHost`，键**恰好**五个：`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`（**没有** `openSettings`；留给外壳页那一片）。
- 返回值统一：成功是 `{ ok: true }`，失败是 `{ ok: false, reason: "<固定词>" }`。成功时除 `ok` 外没有别的字段；失败时除 `ok` 与 `reason` 外没有别的字段。
- **任何错误消息都不外传**（Electron 的 `loadURL` 拒绝消息带整条引导地址，Node 的 `JSON.parse` 错误带正文片段）。
- reason 词表（固定、小写连字符，逐字）：
  - 全部：`forbidden`（来源不对）、`internal`（兜底）。
  - `reauth`：`rate-limited`、`request-failed`（连不上、超时）、`bad-response`（非 200、非 JSON、`ok` 不是 true、`data.bootstrap` 不是字符串、不在服务 origin 下）、`load-failed`。
  - `openSecretWindow`：`bad-args`、`busy`、`load-failed`。
  - `openExternal`：`bad-url`、`cancelled`、`open-failed`。
  - `reveal`：`bad-path`（所有拒绝共用这一个词，不区分「不存在」与「跑出去」）。
  - `notify`：`bad-kind`。

### 二、`desktop/shell/preload.js`（包根，自包含）

- sandbox 下 preload 只能 require electron、不能用 CommonJS 拆成多个文件 → preload **自包含**，只 require electron 的 `contextBridge` 与 `ipcRenderer`，不许 require 任何相对路径、不许 require `node:fs` 等其它模块。
- 只调**一次** `contextBridge.exposeInMainWorld("themisHost", { … })`；对象里的键恰好是那五个函数。
- 每个函数**只**把它声明的实参原样转交给固定通道的 `ipcRenderer.invoke`，不做任何校验、不改实参。
- 通道名（字面量，与 `src/ipc.js` 的 `HOST_CHANNELS` 逐字一致；preload 里不能 require `src/ipc.js`）：
  - `themis-host:reauth`
  - `themis-host:open-secret-window`
  - `themis-host:open-external`
  - `themis-host:reveal`
  - `themis-host:notify`
- preload 里不许出现第二个 `exposeInMainWorld`、不许有 `ipcRenderer.on`/`send`。

### 三、`desktop/shell/src/hostcheck.js`（纯校验，不 require electron）

- `isSecretPageUrl(url)`：是字符串，且**整串**匹配 `/^http:\/\/127\.0\.0\.1:(\d{1,5})\/([A-Za-z0-9_-]{32})$/u`（照 `secretentry.ts:32`），且端口数值在 1–65535（照 `secretentry.ts:33-35`）。
- `isJobId(id)`：是字符串，且匹配 `/^[A-Za-z0-9_-]{43}$/u`（照 `jobs.ts:11`）。
- `isExternalUrl(url)`：是字符串；先用正则 `/^https?:\/\/[^\s\u0000-\u001f\u007f]+$/i` 卡一遍；再用 `new URL` 解析（解析失败为否）；协议必须是 `http:` 或 `https:`。**正则不可省**：`new URL` 会吞掉首尾空白与内部换行，也会把 `http:\\x` 解析成 `http://x/`，而打开时传的是原串，校验与打开不能看两个东西。
- `isRevealLiteralOk(relPath)`：非空字符串；无控制字符（含 NUL）；无反斜杠；无 `:`；按 `/` 切段后每段非空、不是 `.`、不是 `..`、不以 `.` 结尾、不以空格结尾。绝对路径、UNC、盘符、ADS、空段（含末尾的 `/`）都被这几条覆盖。
- `resolveReveal({ repo, relPath, realpath = fs.realpathSync.native, stat = fs.statSync })`：先字面检查（不过就当拒绝）→ `root = realpath(join(repo, ".agent"))` → `full = realpath(join(root, relPath))` → 判断 `full` 是否在 `root` 之内（写法照 `ts/packages/ui/src/static.ts:52-55`，不能用字符串前缀比较，`..foo` 这样的文件名会误判）→ `stat(full)` 只放行**文件或目录**（设备、管道等不放行）→ 返回 `full`。任何一步抛错都按拒绝处理。
- `NOTIFY_TEXT`：用 `Map` 或 `Object.hasOwn` 查表（`constructor`、`__proto__`、`toString` 这类键不许命中）。两个类型名与文案写死：
  - `attempt-finished` → 标题 `ThemisTally`，正文「attempt 已结束」
  - `awaiting-review` → 标题 `ThemisTally`，正文「有 attempt 等待验收」
- `createRateLimiter({ max = 3, windowMs = 60000, now = Date.now })`：滑动窗口；`take()` 返回布尔；被拒的调用**不计数**；第 1 次之后正好 60000 毫秒放行。

### 四、`desktop/shell/src/control.js`（带控制令牌的 POST，只连 127.0.0.1）

- 导出 `postControl({ origin, control, path, timeoutMs = 10000 })`，返回 `Promise<{ status, body }>`；连接失败或超时**reject**（错误信息里不许出现令牌）。
- 用 `node:http` 的 `http.request`：`host` 是 `127.0.0.1`，端口取自**已校验**的 origin，`method` 是 `POST`，头 `x-themis-control: <control>`，`agent: false`（不留长连接，免得拖住服务关停与测试退出），**不写正文**，**不带** `Origin`、**不带** `Cookie`。
- 为什么这样能过服务的门：控制路由不读正文、不做 CSRF（`app.ts:126-138`），缺 Origin 放行（`guards.ts:47-50`），Node 自动写的 Host 是 `127.0.0.1:<port>`（`guards.ts:13-21`）。
- `body` 是响应正文的原样字符串（不解析）；状态码原样带回。

### 五、`desktop/shell/src/host.js`（五个函数的编排，依赖全注入）

- 导出 `createHost({ origin, control, repo, loadMain, createSecretWindow, confirmExternal, openExternal, showItem, showNotification, now, controlTimeoutMs })`，返回**恰好**五个函数的对象（`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`）。
- `reauth()`：
  1. 限速：`take()` 为假 → `{ ok: false, reason: "rate-limited" }`，**不发请求、不加载**。占名额发生在**发请求之前**，失败也算占名额。
  2. `postControl({ origin, control, path: "/control/bootstrap", timeoutMs: controlTimeoutMs })`；reject → `request-failed`。
  3. 校验信封：状态码 200、正文是 JSON、`ok` 为 `true`、`data.bootstrap` 是非空字符串、`new URL(data.bootstrap).origin === origin`；任一不过 → `bad-response`，**不加载**。
  4. `await loadMain(data.bootstrap)`；失败 → `load-failed`。
  5. 成功 → `{ ok: true }`。
  - 返回值、错误与任何输出里都不许出现控制令牌与 bootstrap 的 nonce。
- `openSecretWindow(url, jobId)`：
  1. `isSecretPageUrl(url)` 与 `isJobId(jobId)` 任一不过 → `bad-args`，**不开窗口、不发取消**。
  2. 已经有窗口：`focus()`；**同一** jobId 再调 → `{ ok: true }`；**别的** jobId → `busy`。这两种都**不开新窗口、不发取消**（被拒的作业由页面自己用 `/api/v1/jobs/<id>/cancel` 取消）。
  3. 否则 `win = createSecretWindow({ origin: new URL(url).origin })`，并**同步**记下 `current = { win, jobId }`（必须在第一个 `await` 之前，否则一上来并发会开两个窗口）。
  4. `win.once("closed", …)`：清空 `current`，用控制令牌 `POST /control/jobs/<jobId>/cancel`，**吞掉一切结果与错误**（404、409 都是常态，见 `jobroutes.ts:96-103`）。用 `once` 不用 `on`，再触发一次不重发。
  5. `await win.loadURL(url)`；失败时窗口还在就 `close()`（`closed` 照常触发取消），回 `load-failed`；成功回 `{ ok: true }`。
- `openExternal(url)`：`isExternalUrl` 不过 → `bad-url`（**确认框不弹**）→ `await confirmExternal(url)` 为否 → `cancelled` → `await openExternal(url)`（参数**原样**传），失败 → `open-failed`；成功 `{ ok: true }`。
- `reveal(relPath)`：`resolveReveal` 通过才 `showItem(full)`（调**一次**），不过 → `bad-path`。
- `notify(kind)`：查 `NOTIFY_TEXT`；不在表里 → `bad-kind`（不发通知）；在表里 → `showNotification({ title, body })` 一次，`{ ok: true }`。渲染进程给的**额外参数不进文案**。

### 六、`desktop/shell/src/ipc.js`（通道白名单）

- `HOST_CHANNELS`：冻结的五个通道名（与 preload 逐字一致）。
- `registerHostIpc(ipcMain, host, senderAllowed)`：
  - **只用** `ipcMain.handle`；不许 `ipcMain.on`、不许 `ipcRenderer.send`。
  - handler 的**首行**同步判 `senderAllowed(event)`；不过 → `{ ok: false, reason: "forbidden" }`，**不进** host。
  - `try { return await host[name](…) } catch { return { ok: false, reason: "internal" } }`：处理器**一律不抛错**（Electron 的 invoke 处理器抛错时可能把错误打到日志）。
  - 按函数显式取实参个数，**多余的参数丢掉**。
- `senderAllowed`（在 `main.js` 侧实现）：`event.sender === 主窗口的 webContents`，且 `event.senderFrame` 不为 null，且 `isServiceUrl(event.senderFrame.url, origin)`。

### 七、`desktop/shell/src/window.js`（加两个函数，不改 `webPreferences`）

- `webPreferences(partition)` **一字不改**：仍然恰好十键、没有 `preload`（凭据窗口用它；T025 门禁 P04 钉住）。
- `mainWebPreferences(partition, preloadPath)` = `{ ...webPreferences(partition), preload: preloadPath }`（十键加 `preload`；`preload` 是**绝对路径**）。
- `trackWindow(win, load)`：先挂 `closed`（并记下 closed 是否已触发），**再** `await load()`；load reject 时，`win.isDestroyed()` 为真**或** closed 已触发 → 当作「窗口已关」吞掉；否则重新抛出。返回 `{ closed, close }`。`main.js` 里写 `trackWindow(win, () => contents.loadURL(bootstrap))`，`loadURL` 标记仍在。

### 八、`desktop/shell/src/core.js`（令牌走新的可选回调）

- `runShell` 增加**可选**的 `onServiceReady({ origin, control, repo })`：在 `openWindow` **之前**调用，放进 `openWindow` 所在的**同一个 try** 里；抛错 → 走「打开窗口失败」那条路（一行 `ERROR: `、收服务、退出码 1）。
- `openWindow` 的入参**不变**，仍然只有 `{ bootstrap, origin }`（T025 门禁 P06 与 `tests/core.test.js:173-174` 钉住）；不传 `onServiceReady` 时一切照旧。
- 控制令牌**只**经 `onServiceReady` 进主进程，绝不经过 `openWindow`、绝不进页面。

### 九、`desktop/shell/src/service.js`（`stopService` 对已退出的子进程）

1. 进来**先查退出态**：`typeof child.exitCode === "number"` 或 `child.signalCode` 有值 → 立即兑现 `{ exited: true, code, signal, killed: false }`，**不碰 stdin**、不等宽限期。
2. 没退出时：`child.stdin.end()` **之前**先挂 `child.stdin.on("error", () => {})`，接住 end 与子进程退出撞车时的 EPIPE。
3. 其余照旧：宽限 `graceMs`（默认 10000）内退出 → `{ exited: true, code, signal, killed: false }`；到期 → `child.kill()`，等到它真的没了 → `{ exited: false, code: null, signal, killed: true }`。

### 十、`desktop/shell/main.js`（唯一碰 Electron API 的地方）

- 仍 require electron，并用到 `app`、`BrowserWindow`、`session`、`Menu`、`ipcMain`、`shell`、`dialog`、`Notification`。
- **两个窗口走同一个工厂** `guardedWindow({ partition, origin, prefs, options })`：`session.fromPartition(partition)` → `setPermissionRequestHandler` 一律 `callback(false)`、`setPermissionCheckHandler` 一律返回 `false`；`new BrowserWindow({ ...options, webPreferences: prefs })`（`new BrowserWindow` 恰好一处）；`webContents.setWindowOpenHandler(() => ({ action: "deny" }))`；`webContents.on("will-navigate", (event, url) => { if (!isServiceUrl(url, origin)) event.preventDefault(); })`。
- 主窗口：`partition = partitionName()`；`prefs = mainWebPreferences(partition, path.join(__dirname, "preload.js"))`；`loadURL` 走 `trackWindow`。
- 凭据窗口：`partition` 另取一个（`partitionName()` 再调一次，与主窗口**不同**）；`prefs = webPreferences(thatPartition)`（十键、**没有** `preload`）；`options = { parent: 主窗口, width: 560, height: 480, title: "录入凭据" }`；`origin` 是凭据页**自己的** origin。
- 凭据窗口的 `closed` → 取消作业，由 `host.js` 的 `createSecretWindow` 包装负责（`main.js` 只负责建窗、返回带 `once("closed")` 与 `loadURL` 的对象）。
- `senderAllowed`：`event.sender === 主窗口.webContents` 且 `event.senderFrame` 不为 null 且 `isServiceUrl(event.senderFrame.url, origin)`。
- `confirmExternal`：`dialog.showMessageBox(主窗口, { type: "question", buttons: ["打开", "取消"], defaultId: 1, cancelId: 1, message: "在系统浏览器中打开？", detail: url, noLink: true })`；`response === 0` 算确认（文案照 UI 文档 8.7）。
- `openExternal`：`shell.openExternal(url)`（返回 Promise）；`showItem`：`shell.showItemInFolder(fullPath)`（同步）；`notify`：`new Notification({ title, body }).show()`。
- `Menu.setApplicationMenu(null)` 照旧；T025 的 15 个接线标记与两个 require（`src/core.js`、`src/window.js`）都保留。
- 静态禁令（见「Definition of done」的 D15）：`require('electron')` 只在 `main.js` 与 `preload.js`；`http.request` 只在 `src/control.js`；`shell.openExternal`、`showItemInFolder`、`dialog`、`Notification` 只在 `main.js`；`ipcMain.on`、`ipcRenderer.send` 不出现；`main.js` 与 `src/**` 里（**注释里也不许**）没有 `persist:`、`shell: true`、fs 的写函数、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`；请求只发往 `127.0.0.1`。

### 十一、`desktop/shell/package.json` 与 `README.md`

- `package.json`：只改 `scripts.test`——保留 `--test-reporter=tap` 且开关仍在文件清单**之前**，并把本片新增的五份测试（`tests/control.test.js`、`tests/host.test.js`、`tests/hostcheck.test.js`、`tests/ipc.test.js`、`tests/preload.test.js`）**显式**列进去；`scripts.test` 仍要显式列出 `tests/` 下**每一个** `*.test.js`；`devDependencies` 仍是 `{"electron": "44.9.0"}`；`package-lock.json` 一个字节都不动。
- `README.md`：只增改，不删 T025 的要点（装法、跑法、参数、退出码、10 秒与 30 秒时限、`npm ci` 不下载 Electron 本体与 `node node_modules/electron/install.js`、`冒烟`）。新增：五个函数与各自的失败 reason 词表、凭据窗口同时最多 1 个（同一作业再调聚焦、别的作业回 busy）、通知类型名与文案、relPath 的基准是 `<仓库>/.agent/`（不带 `.agent/` 前缀）、**真 Electron 不在自动化内**这一已知缺口与手工冒烟步骤（窗口能开、页面照常、关窗退 0、凭据小窗口里 Ctrl+V 能粘贴）、T025 那句「不配 preload」要改成主窗口**配** preload、凭据窗口不配。

### 十二、并发、取消与兼容性

- 并发：凭据窗口同时最多 1 个（`current` 占位在第一个 `await` 之前同步记下）；`reauth` 的并发**不合并**，各算一次（UI 文档 8.2 是「自动调用一次」；即使并发也是后到的 nonce 胜出，无永久伤害）。
- 取消：凭据窗口关闭 → 主进程用控制令牌 `POST /control/jobs/<id>/cancel`，恰好一次；取消请求的结果与错误一律吞掉。
- 限速：reauth 每 60 秒最多 3 次（滑动窗口），失败的也占名额。
- 兼容性：`webPreferences(partition)` 的十键与形状不变；`openWindow` 的入参不变；`runShell` 的退出码 0/1/2 与既有三段文案不变；`desktop/web` 与 `ts/**` 一字不动；既有七份测试只许改不许删（`tests/window.test.js:7` 的断言对象按 D14 改成凭据窗口，另加主窗口的 `deepEqual`）。

## Steps
1. **读基线**：读 `desktop/shell/src/{window,core,service}.js`、`desktop/shell/main.js`、`desktop/shell/tests/{window,core,service}.test.js`、`desktop/shell/package.json`、`desktop/shell/README.md`、`tests/test_gate_t025_baseline.py`；再读 `ts/packages/ui/src/{secretentry,jobs,routes,jobroutes,guards,app,envelope}.ts` 与 `scripts/kit_config.py` 的相关片段。确认本合同的符号与形状一致，**不一致就停下并报告**（不要照抄本文的行号）。
2. **T025 三处（一）**：`desktop/shell/tests/core.test.js` 的第 208 行（「窗口在 openWindow 返回前就关了」）、第 265 行（「服务在开窗口之前就已经没了」）、第 345 行（「不传 io」）三条补 `{ timeout: 5000 }`；已带 timeout 的 240、292、315 三条**照旧不动**。理由：实现回退时这三条会挂住而不是变红。
3. **T025 三处（二）**：`desktop/shell/src/window.js` 加 `mainWebPreferences` 与 `trackWindow`（见第七节），`desktop/shell/tests/window.test.js` 补四种情形的用例（load 正常、load 拒绝且 `isDestroyed` 为真、load 拒绝且 closed 已触发但 `isDestroyed` 仍为假、load 拒绝且窗口还在且 closed 没触发 → 重新抛出）。
4. **T025 三处（三）**：`desktop/shell/src/service.js` 的 `stopService` 按第九节改（先查退出态 → 立即兑现；stdin 的 error 被接住），`desktop/shell/tests/service.test.js` 补两条用例：真子进程已退出时立即兑现（带时限，不等宽限期）、假子进程发 EPIPE 不抛。
5. **E1 快照**：`mainWebPreferences(p, q)` 是 T025 的十键加 `preload`，其余不变；`webPreferences(p)` 仍恰好十键、没有 `preload`；`desktop/shell/tests/window.test.js:7` 的断言对象改成凭据窗口的（十键、无 `preload`），另加主窗口的 `deepEqual`（十键加 `preload`）。
6. **纯校验**：`desktop/shell/src/hostcheck.js` + `desktop/shell/tests/hostcheck.test.js`。每个校验都有正反例；含一条「出处对齐」用例：读 `ts/packages/ui/src/secretentry.ts`、`jobs.ts`、`localhttp/control.ts`，断言正则与头名**字面量**还在（服务改了外壳的测试就红）。写完扫一遍文件里的 `\u0000`、`\u001f` 一类转义有没有被写成真字符。
7. **控制请求**：`desktop/shell/src/control.js` + `desktop/shell/tests/fixtures/fake-control-server.js` + `desktop/shell/tests/control.test.js`。假服务记下方法、路径、头、次数；断言没有 Origin、没有 Cookie；状态码与正文原样带回；连不上与超时都 reject，错误里没有令牌。假服务文件**不叫** `*.test.js`（T025 门禁 S02 会红）。
8. **reauth**：`desktop/shell/src/host.js` + `desktop/shell/tests/host.test.js`（见第五节与 D03、D04）。
9. **openSecretWindow**：同文件（见 D05、D07）。窗口用 EventEmitter 假对象；取消请求打到本机假服务。
10. **openExternal、reveal、notify**：同文件（见 D08–D11）。reveal 的 junction 用例用真 `fs.symlinkSync(target, path, "junction")`（Windows 上不要管理员权限）。
11. **IPC 与 preload**：`desktop/shell/src/ipc.js`、`desktop/shell/preload.js`、`desktop/shell/tests/ipc.test.js`、`desktop/shell/tests/preload.test.js`。preload 的测试用 `vm.runInNewContext(源码, { require: fakeRequire })` 真跑一遍 preload 源码，记录 `exposeInMainWorld` 与 `invoke` 的调用；**测试文件里不许出现 `require('electron')` 这个字面串**（T025 门禁 S03 扫 `tests/**`），用注入的假 require，模块名字面量写成 `"electron"`。
12. **编排与接线**：`desktop/shell/src/core.js` 加 `onServiceReady`（可选、在 `openWindow` 之前、抛错走一行 ERROR + 收服务 + 退出码 1），`desktop/shell/tests/core.test.js` 补用例（次序、收到三键、抛错、可选）；`desktop/shell/main.js` 按第十节接线（一个建窗工厂、主窗口带 preload、凭据窗口不带、`senderAllowed`、`confirmExternal`、`openExternal`、`showItem`、`notify`）；`desktop/shell/package.json` 的 `scripts.test` 追加五个新测试文件；`desktop/shell/README.md` 按第十一节改。
13. **跑检查并写报告**：跑 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。
    - **两条硬规矩**：
      1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`。
      2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；测试草稿用完立刻删掉，别留在候选里。

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t026_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：600s · 期望退出码：0 · 输出须匹配：`# pass [1-9]\d*`

## Definition of done
- D01：`desktop/shell/preload.js` 自包含：只 require electron 的 `contextBridge` 与 `ipcRenderer`；只调一次 `exposeInMainWorld`，名字是 `themisHost`；键恰好是 `reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`，没有 `openSettings`；每个函数只把声明的实参转交给固定通道的 `ipcRenderer.invoke`，不做校验；`tests/preload.test.js` 用 `vm` 真跑一遍 preload 源码；证据：V01、G01；目的：E3：暴露面与 D10 的表一致，参数越界由主进程校验，渲染进程拿不到控制令牌。
- D02：`src/ipc.js`：`HOST_CHANNELS` 恰好五个、与 preload 逐字一致；只用 `ipcMain.handle`；来源不对回 `forbidden` 且不进 host；host 抛错回 `internal`，错误信息不外传；多余实参被丢掉；证据：V01、G01；目的：没有通用 IPC 接口，处理器不抛错，错误里的地址与令牌出不去。
- D03：`reauth`：发到 `POST /control/bootstrap`，头 `x-themis-control` 正确，没有 Origin 与 Cookie；只有 200、`ok` 为 true、`data.bootstrap` 是字符串且在服务 origin 下才加载，且只加载一次；成功返回恰好 `{ok:true}`；连不上回 `request-failed`；非 200、非 JSON、缺字段、别的 origin 回 `bad-response` 且不加载；加载失败回 `load-failed`；证据：V01、G01；目的：D4 的重新认证：别的 origin 的地址不能进主窗口。
- D04：`reauth` 限速（时钟注入）：60 秒内最多 3 次，第 4 次回 `rate-limited` 且假服务收到的请求数不变、不加载；失败的也占名额；第 1 次之后 60000 毫秒放行；证据：V01、G01；目的：防 401 循环；令牌门连续失败也有自己的锁定。
- D05：`openSecretWindow`：url 照 `secretentry.ts:32-35` 的形状与端口范围、jobId 照 `jobs.ts:11`，各配正反例（端口 0 与 65536、令牌 31 与 33 位、localhost、https、多余路径、查询串、末尾换行、作业号 42 与 44 位、非字符串）；不合格回 `bad-args` 且不开窗口；同时最多 1 个窗口：同一 jobId 再调回 `{ok:true}` 并聚焦，别的 jobId 回 `busy` 并聚焦，都不开新窗口、不发取消；窗口关闭后能再开；加载失败回 `load-failed` 并关窗；有一条用例核对服务源码里的正则字面量还在；证据：V01、G01；目的：外壳与服务的形状一致；任务书把窗口个数交给规划端定。
- D06：凭据窗口：`webPreferences` 恰好十键、没有 `preload`；分区由 `partitionName()` 另取，与主窗口不同；`createSecretWindow` 收到的 origin 是该 url 自己的 origin；`main.js` 只有一个建窗工厂（`new BrowserWindow` 恰好一处），两种窗口走同一套权限拒绝、新窗口拒绝与 `will-navigate`；证据：V01、G01、review；目的：E1、E2：拒绝规则靠结构保证相同。
- D07：关窗取消（窗口用 EventEmitter 假对象，请求用本机假服务）：触发 `closed` 后假服务恰好收到一次 `POST /control/jobs/<jobId>/cancel`，jobId 与头都对；再触发一次不重发；假服务回 404、409、500、断连或没在监听时，外壳不崩、没有未处理的拒绝；证据：V01、G01；目的：E8：服务页卸载之后关窗仍能取消，取消靠主进程不靠页面。
- D08：`openExternal`（确认与打开都注入）：确认为否时打开函数没被调用，回 `cancelled`；确认为是时打开函数被调一次、参数原样，回 `{ok:true}`；打开失败回 `open-failed`；非 http、https（`javascript:`、`file:`、`data:`、`ftp:`、`mailto:`）以及带首尾空白、换行的串、`http:\\x`、非字符串一律回 `bad-url` 且确认框没弹；证据：V01、G01；目的：校验与打开看的是同一个串。
- D09：`reveal` 字面检查：非字符串、空串、绝对路径、盘符、UNC、`..`、`.`、反斜杠、空段（含末尾的 `/`）、含 `:` 的名字、段尾的点或空格、控制字符（含 NUL）一律回 `bad-path`，且不碰文件系统、不调显示函数；relPath 相对 `<仓库>/.agent/`；证据：V01、G01；目的：T13；单点段与控制字符是规划端核对后补的。
- D10：`reveal` 的 realpath：比较对象是 `<仓库>/.agent` 的 realpath；`.agent` 里指到外面的 junction，无论它本身还是经它的路径都拒绝；指到 `.agent` 内部的 junction 放行；不存在、`.agent` 缺失、realpath 落在 root 本身、不是文件也不是目录（注入 stat）都拒绝；通过时显示函数被调一次，参数是 realpath 之后的路径；`..foo` 这样的合法文件名不被误判；证据：V01、G01；目的：T13 的不跟随重解析点跑出目录、T18 的只认普通文件；正反成对。
- D11：`notify`：`attempt-finished` 与 `awaiting-review` 两类，标题与正文逐字写死在主进程模块；其余（`constructor`、`__proto__`、`toString`、空串、数字、null、对象）回 `bad-kind` 且不发通知；渲染进程给的额外参数不进文案；证据：V01、G01；目的：文案不接受渲染进程给的文字。
- D12：控制令牌（测试里随机生成）不出现在五个函数任何路径的返回值、错误与 stdout、stderr 里，也不出现在 `JSON.stringify(createHost(...))` 里；bootstrap 的 nonce 与一次性页面的 32 位令牌同样不出现在返回值与输出里，包括假的 `loadURL` 拒绝消息带着它们的情形；证据：V01、G01；目的：D4 的红线；在全部输出里搜令牌，不靠人读。
- D13：T025 留下的三处：`tests/core.test.js` 第 208、265、345 三条补 `{ timeout: 5000 }`（已带 timeout 的 240、292、315 照旧）；`trackWindow` 在 load 拒绝时，`isDestroyed` 为真或 closed 已触发都按窗口已关处理，窗口还在且 closed 没触发才抛出，closed 在 load 之前就挂好（各一条用例，其中「closed 已触发而 `isDestroyed` 仍假」是新情形）；`stopService` 对**已退出**的子进程立即兑现 `{exited:true, code, killed:false}` 且不等宽限期（真子进程用例，带时限），stdin 发 EPIPE 不抛（假子进程用例）；证据：V01、G01；目的：T025 终审第 6 节第 1–3 条；已退出的子进程上旧实现是永远挂起。
- D14：E1 快照：`mainWebPreferences(p, q)` 是 T025 的十键加 `preload`，其余不变；`webPreferences(p)` 仍恰好十键、没有 `preload`；`main.js` 主窗口用前者、凭据窗口用后者，preload 路径由 `__dirname` 拼出绝对路径；`runShell` 的 `onServiceReady` 可选，在 `openWindow` 之前调用，收到 `origin`、`control`、`repo`，抛错时一行 ERROR、收服务、退出码 1；`openWindow` 仍只收 `bootstrap` 与 `origin`；`tests/test_gate_t025_baseline.py`（S03 收窄后）照旧全过；证据：V01、R01、G01；目的：`tests/window.test.js:7` 那条是设计要求的改动，不算削弱断言。
- D15：静态禁令：`require('electron')` 只在 `main.js` 与 `preload.js`（`src/**` 与 `tests/**` 里一个都不许，测试里用注入的假 require，模块名字面量写成 `"electron"`）；`http.request` 只在 `src/control.js`；`shell.openExternal`、`showItemInFolder`、`dialog`、`Notification` 只在 `main.js`；`ipcMain.on`、`ipcRenderer.send` 不出现；主窗口用 `mainWebPreferences`、凭据窗口用 `webPreferences`；`main.js`、`src/**` 里（注释里也不许）没有 `persist:`、`shell: true`、fs 写函数、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`；请求只发往 `127.0.0.1`；证据：G01、R01；目的：T025 的静态禁令按文件收紧，应用不向 127.0.0.1 以外发请求。
- D16：`scripts.test` 显式列出所有 `tests/*.test.js`（含本片新增的五份），带 `--test-reporter=tap` 且开关在文件清单之前；`devDependencies` 与锁文件不变；README 写清五个函数与失败 reason、凭据窗口上限、通知类型名与文案、relPath 基准、**不起真窗口的已知缺口**与手工冒烟步骤（窗口能开、页面照常、关窗退 0、在凭据小窗口里 Ctrl+V 能粘贴），T025 的要点还在；证据：V01、R01、review；目的：真窗口只能手工冒烟，README 是唯一凭据。
- D17：所有修改都在允许集合内；没有删除、跳过或弱化既有测试（`tests/window.test.js:7` 的改动见 D14）；新测试没有 skip、only、todo；用例不等真时限（时限一律用可覆盖的毫秒参数或注入时钟）；令牌与 key 都是测试里随机生成的假值；临时文件照 AGENTS.md 用 `T=$(mktemp -d)` 并在同一命令里 `rm -rf "$T"`；遇到合同与既有测试或门禁冲突时不越界改文件，写进 `contract_conflicts`；证据：scope、V01、R01、G01、review；目的：既有测试是别的片的契约。

D13 与 D15 附带的变异对照（每条都要有用例杀掉；门禁端照这张表设计变异）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | 主窗口少 `preload`，或凭据窗口带 `preload` | `tests/window.test.js` |
| M2 | `sandbox`、`contextIsolation` 改松 | `tests/window.test.js` |
| M3 | preload 多暴露一个函数或换通道名 | `tests/preload.test.js` |
| M4 | handler 去掉来源检查或 try/catch | `tests/ipc.test.js` |
| M5 | reauth 不校验 origin，或错误带回 bootstrap | `tests/host.test.js` |
| M6 | 限速改成 4 次、窗口改短、超限仍发请求 | `tests/host.test.js` |
| M7 | 页面正则放宽（端口、令牌长度、去掉整串锚定）、去掉端口范围 | `tests/hostcheck.test.js` |
| M8 | `once` 改 `on`、关窗不发取消、jobId 取错 | `tests/host.test.js` |
| M9 | 取消的错误不接，出现未处理的拒绝 | `tests/host.test.js` |
| M10 | 上限判断去掉，或占位放到 await 之后 | `tests/host.test.js` |
| M11 | openExternal 先弹框再校验、取消也打开、协议放行 file | `tests/host.test.js` |
| M12 | 去掉 `isExternalUrl` 的正则，只靠 `new URL` | `tests/hostcheck.test.js` |
| M13 | 字面检查每类各去掉一条 | `tests/hostcheck.test.js` |
| M14 | 去掉 realpath 比较，或与未 realpath 的 `.agent` 比 | `tests/host.test.js`（junction） |
| M15 | `isWithin` 写成 `startsWith("..")` | `tests/hostcheck.test.js`（`..foo`） |
| M16 | notify 用普通对象直接取键 | `tests/hostcheck.test.js`（`constructor`） |
| M17 | 令牌或 nonce 进返回值 | `tests/host.test.js` |
| M18 | `trackWindow` 只看 `isDestroyed` | `tests/window.test.js` |
| M19 | `stopService` 去掉退出态检查，或去掉 stdin 监听 | `tests/service.test.js` |
| M20 | `onServiceReady` 放到 `openWindow` 之后，或把 control 塞进 `openWindow` | `tests/core.test.js` |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如服务侧的 `x-themis-control` 头名、`data.bootstrap` 的形状、控制取消路由的路径或方法、`secretentry.ts` / `jobs.ts` 的正则变了）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`、`desktop/shell/package-lock.json`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 需要新增或升级依赖、需要改 `package.json` 的 `devDependencies`、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（本版单次 5400 秒）。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；累计已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（累计已用 0 秒；16200 ≥ 0 + 2×5400 = 10800，留足两次返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 15 分钟；T025 三处与 E1 快照 15 分钟；纯校验与控制请求 25 分钟；reauth 与 openSecretWindow 20 分钟；openExternal/reveal/notify 15 分钟；IPC 与 preload 15 分钟；编排与 main.js 接线 20 分钟；README 与 `scripts.test` 5 分钟；必要检查（V01、G01、R01）10 分钟；最终报告 5 分钟；总计 145 分钟（超过单次时限 90 分钟的部分按“先做 T025 三处与纯校验、其余按 DoD 权重排后”的次序压缩；到时限就把没做完的写进执行报告）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D17，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：五份新测试各覆盖了哪些条目、二十条变异各由哪条用例杀掉、`webPreferences` 的实际十个键与 `mainWebPreferences` 的第十一个键、reauth 与取消请求的实际方法/路径/头、README 新增的段落、`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`、`desktop/shell/package-lock.json`。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；新测试里不写 skip / only / todo。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`；不改 `desktop/shell/package-lock.json`；不加任何依赖。
- 不在 `desktop/shell/src/**` 与 `desktop/shell/main.js` 里写 `persist:`、`shell: true`、fs 的写函数、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`（注释里也不行）；`require('electron')` 只许出现在 `desktop/shell/main.js` 与 `desktop/shell/preload.js`。
- 不把控制令牌、引导地址、nonce 或整条握手行写进 stdout、stderr、日志或文件。
- 不在 `desktop/shell/preload.js` 里 require 相对路径或 electron 以外的模块；不把 preload 拆成多个文件。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261106T051606506408Z-owner-3b44e7：

> 拍板：照规划第 10 节的建议收窄 T025 门禁 S03。已提交 4357dca：SRC_FORBIDDEN 只删 http(s).request 与 openExternal 两条，其余 7 条与“只有 main.js 可以 require('electron')”照旧；test_gate_t025_baseline.py 11 passed。已 task rebase，T026 基线 0961ab6 → 4357dca。preload 放包根 desktop/shell/preload.js、由 T026 门禁收紧 require electron 的位置与五个通道，同意。
>
> 仓库外事实逐条核实：
> 1. 成立。Electron v44.9.0 标签下的 docs/tutorial/sandbox.md 原文：sandbox 的 preload 里 require 只能载入 electron 的 contextBridge、crashReporter、ipcRenderer、nativeImage、webFrame、webUtils，与 events、timers、url（含 node: 前缀写法）；另把 Buffer、process、clearImmediate、setImmediate 补成全局；不能用 CommonJS 把 preload 拆成多个文件。注意：electronjs.org 最新版文档已改成只能载入 electron、没有 Node 全局。所以 preload 只 require electron、不用 events/timers/url/Buffer，照规划的写法，升级后也成立。
> 2. 成立。核对的是 npm pack 取到的 electron@44.9.0 的 electron.d.ts（主工作区 desktop/shell 没装 node_modules）：
>    - IpcMainInvokeEvent 有 sender: WebContents 与 readonly senderFrame: WebFrameMain | null；WebFrameMain 有 readonly url；
>    - shell.openExternal(url, options?) 返回 Promise<void>；shell.showItemInFolder(fullPath): void；
>    - dialog.showMessageBox(window: BaseWindow, options) 返回 Promise<MessageBoxReturnValue>，其中 response: number；
>    - Notification 的构造参数可选，title?、body? 是 string，show(): void；
>    - BaseWindowConstructorOptions.parent?: BaseWindow；BrowserWindow 有 loadURL（返回 Promise<void>）、focus()、isDestroyed()；
>    - webPreferences.preload?: string，文档写明是脚本的绝对路径；Menu.setApplicationMenu(null) 合法。
> 3. 成立。本机 Node v24.19.0 实测：.agent 里放一个指到外面的 junction，经它的路径 realpathSync.native 解析到外面的真实路径，判在 .agent 内为假；普通路径仍在内；fs.realpathSync 结果相同；lstat 把 junction 报成符号链接。
> 4. 未核实：要起真 Electron 才知道。照规划写进 README 的手工冒烟，不进 DoD，落地后手工冒烟时核。凭据窗口关闭取消作业靠的是 closed 事件；主窗口关掉时整个外壳退出、服务按 stdin EOF 结束，不依赖子窗口的 closed。

## Rework（返工第 1 轮，内核追加）

- 基线 `038688fe7e55c16a5aa5413155fbcdb264e10887` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

1.（归执行端）DoD D12 的 stdout/stderr 证据缺失：合同 D12 明写「控制令牌…不出现在五个函数任何路径的返回值、错误与 stdout、stderr 里」「bootstrap 的 nonce 与一次性页面的 32 位令牌同样不出现在返回值与输出里…在全部输出里搜令牌，不靠人读」，并把它列为证据要求；一审的下游须知也点名要求「执行端必须在自己的 host.test.js 里捕获 stdout/stderr 并搜令牌与 nonce」。但候选里没有任何一处捕获 stdout/stderr：tests/host.test.js 只断言了返回值、JSON.stringify(host) 与错误消息（grep 全 tests/ 目录，只有 core.test.js 的既有 T025 用例碰 process.stderr，且它覆盖的是 core.js 的 io，不是五个宿主函数）。执行报告的 D12 行写「令牌与 bootstrap 地址…不在任何返回值、JSON.stringify(host) 与输出里」并标 done——这一条自述比证据宽：输出（stdout/stderr）这一路没有任何断言。补法：在 tests/host.test.js 里加一条用例，在调用五个函数的成功与各失败分支期间接管 process.stdout.write 与 process.stderr.write，把捕获到的内容收集起来，断言控制令牌、bootstrap nonce、一次性页面令牌都不在其中；并把执行报告的 D12 一行改回合同原文（返回值、错误、stdout、stderr、JSON.stringify(host) 五处都写上）。既有断言不要删改，范围仍限 desktop/shell 的测试与报告。
