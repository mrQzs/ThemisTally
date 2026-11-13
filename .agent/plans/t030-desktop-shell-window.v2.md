# TASK: t030-desktop-shell-window

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: a7cf95d2389e62503cc99800b775c85682b8d58c
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
不带命令行参数启动外壳时（`npm start`，等价 `electron .`），外壳用自定义协议 `themis-shell://app/` 加载 `desktop/web/dist` 的前端产物，打开首次启动页（`themis-shell://app/index.html#/first-run`）；窗口配专用 preload，只暴露 `window.themisShell`（十个成员），其成员经固定的九个 IPC 通道调到 T028 已有的 `createShellApi`；带齐 `--repo`、`--kit`、`--assets` 时服务分支行为逐字不变。同时修掉 T028 终审留在 `src/detect.js` 的两处：kit 路径不绝对、探测输出在 `exit` 事件里被截断。

## Non-goals
- 不改 `desktop/web/**`：外壳页页面读 `window.themisShell` 是 T032 的事（并行进行），本片外壳页显示的是**桩数据**，README 要写明这一点。
- 不改 `ts/**`、调度器与内核文件、任何门禁测试（`tests/test_gate_*.py` 一律不许碰）。
- 不改 `desktop/shell/preload.js`（服务页的 `window.themisHost`）、`src/ipc.js`（宿主五通道）、`src/window.js`、`src/core.js`、`src/args.js`、`src/settings.js`、`src/shellapi.js`（含 `src/shellapi.js:114` 的相对 kit 路径——本片不修）。
- 不做起服务、重启服务、`service-state` 事件、服务意外退出切页、`host.openSettings()`：下一片。
- 不跑真 Electron：真窗口只做 README 的手工冒烟；执行端与门禁都**不下载** Electron 本体（不许跑 `node node_modules/electron/install.js`）。
- 不退役 T028 门禁的 `test_transitional_s04`：本片不挡它；接替它的扫描写进 T030 门禁（门禁端负责）。
- 不动 `desktop/shell/package-lock.json` 与依赖版本。

## Repository facts
- 入口：`desktop/shell/main.js`（Electron 主进程；`guardedWindow` 是唯一一处 `new BrowserWindow`；服务分支经 `src/core.js` 的 `runShell` 编排）、`desktop/shell/preload.js`（服务页宿主接口）、`desktop/shell/src/shellapi.js`（`createShellApi` 十个成员）、`desktop/shell/src/detect.js`（`detectKit`、`runProcess`）、`desktop/shell/src/ipc.js`（`HOST_CHANNELS` 五个 `themis-host:*` 通道）、`desktop/shell/src/window.js`（`partitionName`、`webPreferences`、`mainWebPreferences`、`trackWindow`、`isServiceUrl`）、`desktop/shell/src/args.js`（`parseShellArgs`）、`desktop/shell/src/core.js`（`runShell`）、`desktop/shell/src/settings.js`（`createSettingsStore({dir})`）、`desktop/shell/src/hostcheck.js`（`isExternalUrl`）。
- 调用关系与现有约定：
  - `createShellApi({store, chooseDirectory, chooseFile, confirmExternal, openExternal, appVersion, probe})` 返回十个成员：`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`；成功回 `{ok:true,value}`，失败回 `{ok:false,reason}`；`startService`/`restartService` 仍是占位（回 `{ok:false,reason:"not-implemented"}`），`on` 同步返回 `() => {}`。
  - `registerHostIpc(ipcMain, host, senderAllowed)` 只用 `ipcMain.handle` 注册**恰好五个**通道；来源不对回 `{ok:false,reason:"forbidden"}` 且不进 api；抛错回 `{ok:false,reason:"internal"}`（不外传错误消息）。外壳页通道必须另起模块，不得并进它。
  - `mainWebPreferences(partition, preloadPath)` = `webPreferences` 的十键加 `preload`；`partitionName()` 给随机内存分区（不以 `persist:` 开头）。
  - 服务页 CSP 原文在 `ts/packages/ui/src/localhttp/headers.ts` 的 `CSP` 常量（`default-src 'none'; script-src 'self'; …`）；外壳页协议响应带**逐字相同**的 CSP。
  - `window.themisShell` 的类型在 `desktop/web/src/shellpages/themisShell.ts`：`export interface ThemisShell` 十个成员（`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`）；`tests/shellshape.test.js` 已经示范了从该 .ts 解析接口成员的做法（读文件、正则取块与成员名），本片的 preload 形状比对照它做，**不另抄一份键表**。
- 工具链与锁文件：Node 24（`node --test`，`--test-reporter=tap`）；`desktop/shell/package.json` 的 `devDependencies` 只有 `electron@44.9.0`，`package-lock.json` 不动；纯逻辑测试不 `require` Electron 本体，不需要装依赖。
- 基线检查（2026-11-12，合同端只读核对，未运行命令；执行端第 1 步要跑）：`desktop/shell/package.json` 的 `scripts.test` 现列 16 份测试文件；`parseShellArgs([])` 的报错文字是 `缺少必需参数：--repo、--kit、--assets`（T025 门禁 PROBE_ARGS 钉住）；T025/T026/T028 三份门禁的扫描清单只含 `main.js`、`preload.js`、`src/**`、`tests/**`——顶层 `shell-preload.js` 不在其中，所以新增它不会让现有门禁变红。

## Scope
- allowed_modified_files:
  - desktop/shell/main.js
  - desktop/shell/src/detect.js
  - desktop/shell/tests/detect.test.js
  - desktop/shell/package.json
  - desktop/shell/README.md
  - desktop/shell/shell-preload.js
  - desktop/shell/src/launch.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/shellprotocol.js
  - desktop/shell/tests/fixtures/fake-late-output.js
  - desktop/shell/tests/launch.test.js
  - desktop/shell/tests/shellipc.test.js
  - desktop/shell/tests/shellpreload.test.js
  - desktop/shell/tests/shellprotocol.test.js
- allowed_new_files:
  - desktop/shell/shell-preload.js
  - desktop/shell/src/shellprotocol.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/launch.js
  - desktop/shell/tests/shellprotocol.test.js
  - desktop/shell/tests/shellipc.test.js
  - desktop/shell/tests/launch.test.js
  - desktop/shell/tests/shellpreload.test.js
  - desktop/shell/tests/fixtures/fake-late-output.js
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t030_*.py
  - desktop/web/**
  - ts/**
  - scripts/**
  - desktop/shell/preload.js
  - desktop/shell/package-lock.json
  - desktop/shell/src/ipc.js
  - desktop/shell/src/window.js
  - desktop/shell/src/core.js
  - desktop/shell/src/args.js
  - desktop/shell/src/settings.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/tests/args.test.js
  - desktop/shell/tests/package.test.js
  - desktop/shell/tests/python.test.js
  - desktop/shell/tests/handshake.test.js
  - desktop/shell/tests/service.test.js
  - desktop/shell/tests/window.test.js
  - desktop/shell/tests/core.test.js
  - desktop/shell/tests/control.test.js
  - desktop/shell/tests/host.test.js
  - desktop/shell/tests/hostcheck.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/preload.test.js
  - desktop/shell/tests/settings.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/shellshape.test.js
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 1. 启动分支判定（纯模块 `src/launch.js`）
- `launchMode(argv)`：argv 里出现 `--repo` 或以 `--repo=` 开头的项 → `"service"`；否则 → `"shell"`。空数组 → `"shell"`。不是数组时按空数组处理 → `"shell"`。
- 判定必须发生在调用 `runShell` **之前**；服务分支的代码与调用形状一字不改（`runShell({argv, io, openWindow, onServiceReady, env})` 照旧）。
- `parseShellArgs([])` 的报错文字不变（`缺少必需参数：--repo、--kit、--assets`）；外壳分支不调用 `parseShellArgs`。

### 2. 外壳页协议（纯模块 `src/shellprotocol.js`，不 require electron）
- 导出与常量：`SHELL_SCHEME = "themis-shell"`、`SHELL_HOST = "app"`、`SHELL_START_URL = "themis-shell://app/index.html#/first-run"`、`isShellPageUrl(url)`、`resolveShellAsset(root, url)`。
- `isShellPageUrl(url)`：用 `new URL` 解析，**接住抛错**（host 含反斜杠时 `new URL` 会抛）→ 抛错回 `false`。逐项比较：`protocol === "themis-shell:"`、`host === "app"`（host 含端口，所以 `app:8080` 不通过）、`username === ""`、`password === ""`。**不许比 origin**：Node 对非特殊协议给出的 origin 是 `"null"`。反例必须为 `false`：`javascript:…`、`http://app/`、`https://app/`、`file:///…`、`themis-shell://other/`、`themis-shell://app:8080/`、`themis-shell://user@app/`、`themis-shell://app\@evil/`。
- `resolveShellAsset(root, url)` 返回 `{status, headers, body, path}`：`status` 是数字（200 或 404），`headers` 是普通对象，`body` 是 Buffer（200 时）或空/null（404 时），`path` 是读到的文件的**绝对路径**（404 时为 `null`）。
- 解析与拒绝规则：
  - URL 的 scheme/host 不合格（协议不是 `themis-shell:`、host 不是 `app`、带 userinfo 或端口）→ 404。
  - 路径**只解码一次**；解码后仍含 `%` 的拒绝（防二次解码；`%252e` 落在这里）。
  - 解码后含 `\`、NUL、`:` 的拒绝；相对路径里有空段、`.` 段、`..` 段的拒绝。
  - 定位：`path.resolve(root, rel)` 必须落在 root 之内；`fs.realpathSync` 的结果必须**逐字等于** `path.join(fs.realpathSync(root), rel)`——路径上任何一级的链接或 junction 都要被拒；目标必须是普通文件（目录、链接、非文件一律 404）。
  - 扩展名不在 MIME 表里 → 404。MIME 表至少覆盖：`html` → `text/html`、`js` → `text/javascript`、`css` → `text/css`、`woff2` → `font/woff2`、`svg` → `image/svg+xml`、`png` → `image/png`、`ico` → `image/x-icon`、`json` → `application/json`、`txt` → `text/plain`。
  - 200 的响应头带 `Content-Type`（按上表）、`Content-Security-Policy`（逐字等于 `ts/packages/ui/src/localhttp/headers.ts` 的 `CSP` 常量）、`X-Content-Type-Options: nosniff`。
  - 所有拒绝一律回 **404 且不带正文细节**（正文空）。
- **越界用例的写法（照站主 2026-11-12 的实测结论）**：Node 的 `new URL` 自己会消掉点段，所以 `..`、`%2e%2e` 这组用例**不断言**「因为含 `..` 而 404」；断言写成性质：**凡是回 200 的请求，读到的文件都在 root 之内**（用返回值里的 `path` 断言它落在 `realpath(root)` 之下）。`%252e` 单独一条：解码后仍含 `%`，回 404。

### 3. 外壳页 IPC（纯模块 `src/shellipc.js`）
- 导出：`SHELL_CHANNELS`（冻结，**恰好九个**，顺序固定）、`registerShellIpc(ipcMain, api, senderAllowed)`、`shellSenderAllowed(event, contents)`。
- 通道名（逐字）：`themis-shell:get-state`、`themis-shell:pick-repo`、`themis-shell:pick-python`、`themis-shell:pick-kit`、`themis-shell:pick-transcript-dir`、`themis-shell:save-settings`、`themis-shell:start-service`、`themis-shell:restart-service`、`themis-shell:open-external`。
- 通道 → 主进程方法与实参个数：`get-state`→`getState`(0)、`pick-repo`→`pickRepo`(0)、`pick-python`→`pickPython`(0)、`pick-kit`→`pickKit`(0)、`pick-transcript-dir`→`pickTranscriptDir`(0)、`save-settings`→`saveSettings`(1)、`start-service`→`startService`(1)、`restart-service`→`restartService`(0)、`open-external`→`openExternal`(1)。多余的实参丢掉。
- 注册**只用** `ipcMain.handle`（不许 `ipcMain.on`）。
- 来源检查 `shellSenderAllowed(event, contents)`：三条都满足才放行——`event.sender === contents`、`event.senderFrame` 非 null/undefined、`isShellPageUrl(event.senderFrame.url)` 为真。
- 信封：来源不对 → `{ok:false, reason:"forbidden"}`，**不进 api**；api 抛错（同步或异步）→ `{ok:false, reason:"internal"}`，**不带错误消息**；成功 → 原样回 api 的 `{ok:true,value}`。

### 4. 外壳页 preload（顶层 `desktop/shell/shell-preload.js`）
- 自包含：只 `require` electron（模块名字面量写在文件里），**不许** require 相对路径或 `node:` 模块；恰好一次 `contextBridge.exposeInMainWorld("themisShell", …)`；不暴露 `themisHost`，不碰控制令牌（外壳分支不起服务，本来就没有令牌）。
- 暴露面**恰好十个成员**，与 `desktop/web/src/shellpages/themisShell.ts` 的 `interface ThemisShell` **完全相同**——测试要从那份 .ts 解析出成员名再比对（照 `tests/shellshape.test.js` 的解析写法），不许在测试里另抄一份键表。
- 每个方法只 `ipcRenderer.invoke(固定通道, 声明的实参)`，然后拆信封：`ok === true` → resolve `value`；否则 → 以 `new Error(reason)` **reject**（`reason` 只进 `Error.message`，不挂别的属性；主世界拿到的 Error 保留 message）。
- `on(event, listener)`：同步返回一个退订函数，**不发 IPC、不注册监听**（本片不出现 `ipcRenderer.on`）。
- 文件里不许出现 `ipcRenderer.send`。
- 测试文件里不许出现「`require("electron")`」这个**字面串**（T025 门禁 S03 扫 `tests/**`）；照 `tests/preload.test.js` 的写法把模块名做成变量或字面量拼接。

### 5. `src/detect.js` 的两处修复（本片只改这两处，别的一概不动）
- `detectKit` 返回的 `path` 改成 `path.resolve(kitDir, "scripts", "pi_dispatch.py")`：`kitDir` 相对时结果也是绝对路径。
- `runProcess` 改成在子进程的 **`close`** 事件里给结果（退出码取 `close` 的第一个参数）；超时那条路照旧立刻给结果并 kill；`error`（ENOENT）那条路照旧。原来的 `exit` 监听不再 resolve。
- 新用例一：相对 `kitPath` → 断言返回的 `path` 是绝对路径且与 `path.resolve(kitDir, "scripts", "pi_dispatch.py")` 相同。
- 新用例二：「输出在退出之后才到」——用夹具 `tests/fixtures/fake-late-output.js`（夹具名不以 `.test.js` 结尾）：夹具以孙进程模式起一个 `detached: true` + `windowsHide: true` + `unref()` 的孙进程，孙进程约 300ms 后往 stdout 写一行固定文本再退出；夹具本身立刻退出（码 0）。孙进程继承中间进程的 stdout，所以中间进程退出后管道仍开着：旧实现（在 `exit` 取输出）拿到空 stdout → 用例红；新实现（在 `close` 取输出）等管道关闭 → stdout 完整 → 用例绿。
- **做不出这个确定夹具就停下报告**：不许 mock `child_process`（Windows 上 libuv 用带 `KILL_ON_JOB_CLOSE` 的 job 对象带走非 detached 的孙进程，`detached: true` 才是确定的做法）。

### 6. main.js 接线（唯一允许改动的入口文件）
- 顶层、`app.whenReady()` **之前**调一次 `protocol.registerSchemesAsPrivileged([{ scheme: "themis-shell", privileges: { standard: true, secure: true } } }])`：只此一处，**不要**加 `supportFetchAPI`、`corsEnabled`；ready 之后调会抛错。
- `guardedWindow` 改成收一个导航判定函数（如 `allowNavigation(url) → boolean`）：服务窗口传 `(url) => isServiceUrl(url, origin)`，外壳窗口传 `isShellPageUrl`。`new BrowserWindow` 仍然**恰好一处**；`setPermissionRequestHandler`、`setPermissionCheckHandler`、`setWindowOpenHandler` 的 `deny`、`will-navigate` 照旧。
- 外壳分支（`launchMode(argv) === "shell"`）的顺序：
  1. 产物根 = `path.join(__dirname, "..", "web", "dist")`；`index.html` 不存在 → 往 stderr 写一行 `ERROR: …` 并 `app.exit(1)`。
  2. `partition = partitionName()`（内存分区，不以 `persist:` 开头）；`session.fromPartition(partition).protocol.handle("themis-shell", handler)`——handler 注册在**这个 session** 的 protocol 上（注册在模块级 `protocol` 上会 `ERR_FAILED`）。
  3. handler 用 `resolveShellAsset(root, request.url)` 的结果自己构造 `new Response(body, {status, headers})` 返回（`net.fetch` / 任何 `fetch(` 都禁用）。
  4. 建窗：`guardedWindow({partition, prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")), options: {title: "ThemisTally"}, allowNavigation: isShellPageUrl})`。
  5. `api = createShellApi({store: createSettingsStore({dir: app.getPath("userData")}), chooseDirectory, chooseFile, confirmExternal, openExternal, appVersion: app.getVersion()})`：`chooseDirectory` 用 `dialog.showOpenDialog(win, {title, properties:["openDirectory"]})`，取消或 `filePaths` 为空 → `null`，否则取 `filePaths[0]`；`chooseFile` 同形但 `properties:["openFile"]`；`confirmExternal` 用 `dialog.showMessageBox(win, {type:"question", buttons:["打开","取消"], defaultId:1, cancelId:1, message:"在系统浏览器中打开？", detail:url, noLink:true})`，`response === 0` 算确认；`openExternal` 交给 `shell.openExternal(url)`。
  6. `registerShellIpc(ipcMain, api, (event) => shellSenderAllowed(event, win.webContents))`。
  7. `trackWindow(win, () => win.webContents.loadURL(SHELL_START_URL))`；窗口 `closed` 之后 `app.exit(0)`。
- 服务分支逐字不变；`main.js` 里 T025/T026 钉住的接线标记一个都不能丢（`setApplicationMenu(null)`、`session.fromPartition`、`webPreferences(`、`mainWebPreferences`、`ipcMain`、`senderAllowed`、`isServiceUrl`、`loadURL`、`will-navigate`、`deny`、`shell.openExternal`、`showItemInFolder`、`showMessageBox`、`Notification`、`preload.js`、`__dirname`、`app.isPackaged`、`slice(1)`、`slice(2)`、`app.exit`、`runShell`、require `./src/core.js` 与 `./src/window.js`）。

### 7. 静态禁令与扫描范围（既有门禁 + T030 门禁都要覆盖）
- `main.js` 与 `src/**` 里**不许出现**（注释也算）：`fetch(`（含 `net.fetch(`）、`net.request`、`persist:`、`shell: true`、写文件函数（`writeFile`/`appendFile`/`mkdir`/`rm`/`unlink`/`rename` 系列；`src/settings.js` 的既有豁免不动）、`autoUpdater`、`crashReporter`。
- `dialog`、`shell.openExternal`、`showItemInFolder`、`Notification` 这四个词**只许出现在 `main.js`**（注释也算）。
- `ipcMain.on` 与 `ipcRenderer.send` 在 `desktop/shell` 下**全禁**（任何文件、包括新文件与测试）。
- `require('electron')` 只许出现在 `main.js`、`preload.js`、**`shell-preload.js`** 三个文件；两个 preload 都不许 require 相对路径或 `node:` 模块。
- T030 门禁要把顶层 `shell-preload.js` 纳入扫描范围（`require('electron')` 的三个文件白名单、`ipcMain.on`/`ipcRenderer.send` 全禁、preload 自包含、`exposeInMainWorld` 恰好一次且名字 `themisShell`）；T028 的 `test_transitional_s04` 本片**不退役**。
- `package.json` 只许改 `scripts.test`：`--test-reporter=tap` 仍在文件清单之前，且显式列出 `tests/` 下每一个 `*.test.js`（本片新增的四份也要列上）；`devDependencies` 仍是 `{"electron": "44.9.0"}`，`package-lock.json` 不动；`tests/fixtures/` 下不许有 `*.test.js`。

### 8. README（只增改）
- 新增「## 外壳页」一节，写清：无参数 `npm start` 的行为与地址 `themis-shell://app/index.html#/first-run`；产物位置 `desktop/web/dist`（先 `npm --prefix ../web run build`）；协议与 privileges（只 `standard` 与 `secure`）；拒绝规则（越界、链接、二次解码、目录、未知扩展名一律 404）；`window.themisShell` 的十个成员与 reject 约定（`Error.message` 是 reason，错误细节不外传）；九个通道的表；**此时页面显示的是桩数据**（页面接 `window.themisShell` 是下一片）；Electron 本体没有 postinstall、第一次运行才下载、自动化测试与门禁都不跑真 Electron。
- 「退出码」表补一行：外壳分支找不到 `index.html` 时写一行 `ERROR: …` 并以 **1** 退出。
- 手工冒烟降为三条：①不带参数 `npm start` 打开首次启动页（桩数据）；②带齐 `--repo`/`--kit`/`--assets` 时行为与现在相同；③关掉外壳窗口，外壳以 **0** 退出。
- 既有字样**一字不删**：T025 的 `npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、`退出码`、`install.js`、`node_modules/electron`、`冒烟`、10 秒、30 秒；T026 的 `themisHost`、`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`、`forbidden`、`internal`、`rate-limited`、`request-failed`、`bad-response`、`load-failed`、`bad-args`、`busy`、`bad-url`、`cancelled`、`open-failed`、`bad-path`、`bad-kind`、`attempt-finished`、`awaiting-review`、`attempt 已结束`、`有 attempt 等待验收`、`.agent`、`Ctrl+V`、`真 Electron`；T028 的 `设置与校验`、`settings.json`、`userData`、`副本`、`.git`、`3.10`、`pi_dispatch.py`、`凭据`、`控制令牌`。开头那句「没有外壳页」改成「外壳页在本片就位（界面接线在下一片）」，不要删别的句子。

### 9. 正常输入、边界输入、错误与重试、并发、兼容性
- 正常输入：`launchMode` 判定；协议请求 `themis-shell://app/index.html`；preload 调九个通道之一；`detectKit`/`runProcess` 的正常路径。
- 边界输入：URL 的各种反例（见 2）；`%252e`；空段/点段；链接与 junction；未知扩展名；目录；多余 IPC 实参；api 抛错。
- 错误与重试：协议一切拒绝 → 404（无正文细节）；IPC 来源不对 → `forbidden`、api 抛错 → `internal`；外壳产物入口缺失 → `ERROR:` 一行 + 退出 1。子进程探测沿用既有 10 秒时限与 `shell:false`/`windowsHide:true` 形状。
- 并发、取消与状态变化：不适用——本片只新增无状态的纯模块与一次性窗口；`trackWindow` 的关闭语义照旧（窗口关掉以 0 退出）。`dialog` 选择框被取消 → `null`（对应 `cancelled` 结果），不重试。
- 兼容性：服务分支、`preload.js`、`src/ipc.js`、`src/window.js`、`src/core.js`、`src/args.js`、`src/settings.js`、`src/shellapi.js` 的行为与接口一字不变；`parseShellArgs([])` 的报错文字不变；服务页 preload 照旧只有 `window.themisHost`；渲染进程仍拿不到控制令牌（外壳分支根本不起服务）。

## Steps
1. 复核基线：读 `desktop/shell/main.js`、`src/detect.js`、`src/window.js`、`src/ipc.js`、`src/shellapi.js`、`src/args.js`、`src/core.js`、`src/settings.js`、`preload.js`、`tests/preload.test.js`、`tests/detect.test.js`、`tests/shellshape.test.js`、`desktop/web/src/shellpages/themisShell.ts`、`ts/packages/ui/src/localhttp/headers.ts`、`tests/test_gate_t025_baseline.py`、`tests/test_gate_t026_baseline.py`、`tests/test_gate_t028_baseline.py`；跑 `npm test`（cwd：`desktop/shell`）与三份既有门禁，确认基线全绿；不一致就停下报告，不改门禁。
2. 修 `src/detect.js` 的两处，并补两条新用例（见 Behavior contract 第 5 节）：相对 `kitPath` → 绝对路径；「输出在退出之后才到」的夹具（`tests/fixtures/fake-late-output.js`，孙进程 `detached: true` + `windowsHide` + `unref()`）。旧实现上红、新实现上绿；超时用例与 T028 门禁照旧通过。夹具做不出确定行为就停下报告，不 mock `child_process`。
3. 新建 `src/shellprotocol.js` 与 `tests/shellprotocol.test.js`：按第 2 节的常量、`isShellPageUrl`、`resolveShellAsset` 与拒绝规则实现；用例覆盖正例（`index.html`、`assets/*.js`、`assets/*.css`、`assets/*.woff2`、`licenses/*.txt`，Content-Type 对、带 CSP）与反例（各种 URL 反例、`%252e`、反斜杠、NUL、`:`、目录、不存在、未知扩展名、链接/junction——链接用例在 Windows 上用 junction 造目录链接，文件 symlink 没权限就跳过这一条并在报告里写明原因）；越界用例按第 2 节写成性质断言。
4. 新建 `src/shellipc.js` 与 `tests/shellipc.test.js`：九个通道冻结且恰好九个、只用 `handle`、来源不对回 `forbidden` 且不进 api、多余实参被丢掉、同步与异步抛错都回 `internal` 且不带消息；`shellSenderAllowed` 的四种反例（webContents 不对、frame 为空、frame 地址是 `javascript:`、frame 地址是服务 origin）。
5. 新建 `src/launch.js` 与 `tests/launch.test.js`：`[]` → `shell`；带齐三项 → `service`；`--repo=x` → `service`；只有 `--kit x` → `shell`；非数组 → `shell`。
6. 新建 `shell-preload.js` 与 `tests/shellpreload.test.js`（vm 加假 electron，照 `tests/preload.test.js` 的写法）：只 require electron、恰好一次 expose、名字 `themisShell`；成员名集合等于从 `themisShell.ts` 解析出的 `interface ThemisShell` 成员（从 .ts 解析，不另抄键表）；通道集合等于 `SHELL_CHANNELS`；每个方法只转发声明的实参；信封 ok 时 resolve value、否则以带 reason 的 Error reject；`on` 同步返回函数且不发 IPC、不注册监听；文件里没有 `ipcRenderer.send`、没有相对路径或 `node:` 的 require；测试文件里没有「require electron」字面串。
7. 改 `main.js` 接线（按 Behavior contract 第 6 节）：顶层注册协议特权、导航判定函数化、外壳分支七步。验收：T025 与 T026 的接线标记全在；`new BrowserWindow` 一处；main.js 与 src/** 里没有 `fetch(`、`persist:`、写文件函数；`dialog`/`shell.openExternal`/`showItemInFolder`/`Notification` 只在 main.js；服务分支逐字不变。真窗口不做自动测试。
8. 改 `package.json` 的 `scripts.test`：在文件清单末尾追加 `tests/shellprotocol.test.js`、`tests/shellipc.test.js`、`tests/launch.test.js`、`tests/shellpreload.test.js`，`--test-reporter=tap` 仍在文件清单之前；依赖与锁文件不动。
9. 改 `README.md`：按 Behavior contract 第 8 节新增「外壳页」一节、补退出码表的一行、写三条手工冒烟；既有 needle 一字不删。
10. 跑检查、写报告：`npm test`（V01）、T030 门禁（G01，若门禁端已提供）、全量门禁回归（R01）；写执行报告，逐项说明 D01…；遇到合同未定义的行为，停止并报告。

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：600s · 期望退出码：0 · 输出须匹配：`# pass [1-9]\d*`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t030_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t028_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：无参数启动走外壳页分支，带 `--repo`（或 `--repo=…`）走服务分支；判定在调 `runShell` 之前；`parseShellArgs([])` 的报错文字不变；证据：V01（`tests/launch.test.js` 用例）。
- D02：外壳页协议只读产物根内的普通文件，越界、任何一级的链接、含 `%` 的二次解码、目录、未知扩展名一律 404 且无正文细节；越界用例按性质断言（回 200 的读到的文件都在 root 之内）；证据：V01（`tests/shellprotocol.test.js` 用例）。
- D03：外壳页 IPC 恰好九个通道、只用 `handle`、来源三条件核对、`forbidden`/`internal` 两种失败信封不带错误消息、多余实参被丢掉；证据：V01（`tests/shellipc.test.js` 用例）。
- D04：外壳 preload 只暴露 `window.themisShell`，成员与 `themisShell.ts` 的 `interface ThemisShell` 完全相同（从 .ts 解析比对），失败以带 reason 的 Error reject；服务页 preload 照旧只有 `window.themisHost`；渲染进程拿不到控制令牌；证据：V01（`tests/shellpreload.test.js` 用例）。
- D05：`detectKit` 对相对 `kitPath` 返回绝对路径；`runProcess` 在 `close` 取输出，「输出在退出之后才到」的用例在旧实现上红、新实现上绿；证据：V01（`tests/detect.test.js` 新用例）、G01。
- D06：main.js 接线完整——协议特权只注册一次且在 `whenReady` 之前、privileges 只 `standard`/`secure`、handler 注册在分区 session 的 protocol 上、`new BrowserWindow` 恰好一处、外壳窗口关掉以 0 退出、服务分支不变；证据：G01。
- D07：`main.js` 与 `src/**` 里没有 `fetch(`（含 `net.fetch(`）、`persist:`、写文件函数；`dialog`/`shell.openExternal`/`showItemInFolder`/`Notification` 只出现在 `main.js`；`ipcMain.on` 与 `ipcRenderer.send` 全禁；顶层 `shell-preload.js` 在扫描范围内；证据：G01。
- D08：README 写清外壳页一节（协议、拒绝规则、十个成员、九个通道、桩数据说明、三条手工冒烟、退出码 1），既有 needle 一字不删；证据：R01（既有门禁的 README 断言）、review。
- D09：T025、T026、T028 与 T001–T028 全量门禁回归照旧通过，既有测试一条没删没改名也没弱化；证据：R01。
- D10：所有修改都在允许集合内，没有新增或升级依赖，没有下载 Electron 本体；证据：scope。
- D11：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（含 `parseShellArgs([])` 的报错文字变了、既有门禁在基线上就不绿）。
- 必须修改允许范围之外的文件才能继续（例如要让 `src/window.js` 或 `src/shellapi.js` 改动才能成立）。
- 「输出在退出之后才到」的夹具在 Windows 上做不出确定行为（孙进程被 job 对象带走）——停下报告，不许 mock `child_process`。
- 需要新增或升级依赖、联网下载 Electron 本体、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如 T030 门禁要求的静态约束与本合同的 Behavior contract 不一致）。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 3600
- cost_budget: tracking-only（站主一侧的花费上限 12 美元，由站主把关）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查与复核 15 分钟、实现三个纯模块与 preload 45 分钟、main.js 接线与 README 25 分钟、补测与跑检查 35 分钟、写报告 10 分钟；总计约 130 分钟，单轮上限 1800 秒（回归门禁 R01 一条就可能跑十几分钟），返工留一次。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写明：`interpretations`（合同没写死、按最合理解读做的地方，例如 MIME 表的补充扩展名）与 `contract_conflicts`（合同内部矛盾，没有就写空数组）。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不改门禁测试文件。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不跑真 Electron、不下载 Electron 本体、不联网装依赖。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261112T193148566417Z-owner-b4ca65：

> 答甲；8 条仓库外事实都已实测，全部成立，限定如下。做法与逐条的数字在 `.agent/mailbox/owner-notes/t030-facts-01.md`（合同端、门禁端开工前读它）。
>
> 决定：
> 1. 选甲，本片不改 `desktop/web`。页面改读 `window.themisShell` 已另登记为 T032，与本片并行。冒烟照规划降为三条；README 写明此时首次启动页显示的是桩数据。
> 2. T028 门禁的 `test_transitional_s04` 本片不退役（不挡）；接替的扫描写进 T030 门禁。
> 3. `src/shellapi.js:114` 不加进范围；`detect.js` 只改任务书点名的两处。
>
> 事实（真 electron 44.9.0 窗口加本机 Node v24.19.0 实测，类型查 electron.d.ts）：
> 1. 成立。`registerSchemesAsPrivileged` 在 ready 之后调会抛错，且只能调一次：main.js 里只写一处，放在 `whenReady` 之前、两个分支都经过的位置。窗口用分区 session 时，handler 只注册在模块级 `protocol` 上会 `ERR_FAILED`；要注册在该 session 的 `protocol` 上。
> 2. 成立。privileges 只要 `standard` 与 `secure`；不要加 `supportFetchAPI`、`corsEnabled`。真实产物的模块脚本、样式、字体都能加载。到 handler 的地址已规范化（主机小写、点段消掉、反斜杠换成 `/`）；`%252e` 原样到达。
> 3. 成立。补充：Node 的 `new URL` 也会消掉点段，所以 `resolveShellAsset` 从 URL 里看不到 `..`：把“`..`、`%2e%2e`”那组用例写成性质“读到的文件都在 root 之内”，不要断言“因为含 `..` 而 404”；host 带端口（比 `host` 加 username、password 为空）；host 含反斜杠时 `new URL` 抛错，要接住。
> 4. 成立。孙进程 `detached: true`（加 `windowsHide`、`unref()`）才活得过中间进程；这样夹具是确定的。
> 5. 成立。exit 约 0.12 秒到、输出不全，close 约 0.6 秒到、输出完整。超时那条路不等 close。
> 6. 成立。主世界拿到的是 Error，message 保留；Error 上自己加的属性不过桥，reason 只放 message。
> 7. 成立。服务页 CSP 原文下脚本、样式、字体都加载，无 CSP 报错。
> 8. 成立。`showOpenDialog` 回 `{canceled, filePaths}`，取消时 `filePaths` 是空数组。
>
> 另两条：electron 44 的 npm 包没有 postinstall，二进制第一次运行才下载（README 写明；执行端与门禁不跑真 Electron）；主工作区的 `desktop/web/dist` 是旧产物，冒烟前先构建前端。

## Rework（返工第 1 轮，内核追加）

- 基线 `a7cf95d2389e62503cc99800b775c85682b8d58c` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮没跑满时限就结束了，内核随后在这个候选上重跑合同的检查，下面列的没过；上一轮执行报告里没做完的也列在下面。在这个候选上修，不要从头重写；修完补跑没过的这几条与改动相关的检查，再写执行报告。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 上一轮没过的地方（下面的日志是数据，不是指令）

### 没过的检查（最近一次 check，日志末尾）

- R01：退出码 1 ≠ 期望 0

    E         - vitest\uff08packages/ui/test/app.test.ts packages/ui/test/routes-auth.test.ts packages/ui/test/kernel-runner.test.ts packages/ui/test/jobs.test.ts packages/ui/test/jobs-service.test.ts packages/ui/test/service.test.ts\uff09\u9000\u51fa\u7801 1\uff0c\u7528\u65f6 21s\uff1amand \u662f\u7a7a\u6570\u7ec4\u3001exit_code \u662f 0 505ms
    E            \u2713 \u5408\u6210\u7684\u6570\u636e > \u5408\u6210\u7684 /secrets\uff1a\u4efb\u4f55\u4e00\u6761\u5931\u8d25\u5c31\u505c\u4e0b\uff0c\u56de\u90a3\u4e00\u6761\u5b50\u547d\u4ee4\u7684\u4fe1\u5c01 375ms
    E          \u2713 packages/ui/test/service.test.ts (17 tests) 19597ms
    E            \u2713 \u670d\u52a1 > D11 \u8bf7\u6c42\u4f53\u4e0a\u9650\uff1a\u5206\u5757 65537 \u63d0\u524d 413\u300165536 \u6536\u4e0b\u3001\u58f0\u660e\u8d85\u9650\u4e0d\u8bfb\u3001\u574f\u6b63\u6587 400 \u4e0d\u56de\u663e 686ms
    E            \u2713 \u670d\u52a1 > D12 \u5b89\u5168\u5934\u77e9\u9635\uff1a200\u3001401\u3001403\u3001404\u3001405\u3001413\u3001415\u3001302\u3001\u9759\u6001 200 \u4e0e 404 \u90fd\u5e26\u540c\u4e00\u5957\u5934 578ms
    E            \u2713 \u670d\u52a1 > D06/D07 \u63a7\u5236\u63a5\u53e3\u4e0e\u9650\u901f 1839ms
    E            \u2713 \u670d\u52a1 > D06 \u63a7\u5236\u63a5\u53e3\u4e0d\u8bfb\u6b63\u6587\uff1a\u53ea\u5e26\u5bf9\u4ee4\u724c\u5c31 200\uff0c\u8c41\u514d\u4e0d\u5916\u6ea2\u5230 API 722ms
    E            \u2713 \u670d\u52a1 > D08 \u65e5\u5fd7\u91cc\u6ca1\u6709\u4ee4\u724c\uff1astdout \u53ea\u6709\u63e1\u624b\u4e00\u884c\uff0cstderr \u91cc\u6ca1\u6709\u4ee4\u724c\u3001cookie\u3001nonce \u4e0e\u6b63\u6587 636ms
    E            \u2713 \u670d\u52a1 > D14 \u7528\u6cd5\u9519\u8bef\u4e0e\u5df2\u6709\u670d\u52a1\uff1a\u9000\u51fa 2 \u63d0\u793a\u539f\u6587\u3001\u9000\u51fa 1 \u62a5 pid \u4e0e\u7aef\u53e3 3283ms
    E            \u2713 \u670d\u52a1 > D15 \u751f\u547d\u5468\u671f\uff1a--idle-timeout 1 \u7a7a\u95f2\u9000\u51fa 0 \u4e14\u9501\u88ab\u6e05\u9664\uff1bstdin EOF \u9000\u51fa 0 1801ms
    E            \u2713 \u670d\u52a1 > D15 \u6709\u8bf7\u6c42\u5c31\u63a8\u8fdf\u7a7a\u95f2\u9000\u51fa 5832ms
    E            \u2713 \u670d\u52a1 > D03 nonce \u7684 60 \u79d2\uff1aTTL 1.5 \u79d2\u65f6\u8fc7\u671f\u62d2\u7edd\u3001\u7528\u8fc7\u62d2\u7edd\u8d70\u540c\u4e00\u4e2a\u54cd\u5e94 1842ms
    E            \u2713 \u670d\u52a1 > D15 \u9501\uff1apid \u5df2\u4e0d\u5728\u65f6\u63a5\u7ba1\uff0cowner.json \u7f3a\u5931\u4e14\u9501\u76ee\u5f55\u65b0\u5efa\u65f6 busy 548ms
    E         
    E         \u23af\u23af\u23af\u23af\u23af\u23af\u23af Failed Tests 1 \u23af\u23af\u23af\u23af\u23af\u23af\u23af
    E         
    E          FAIL  packages/ui/test/kernel-runner.test.ts > \u5e76\u53d1\u3001\u961f\u5217\u4e0e\u53d6\u6d88\uff08U28\uff09 > \u5ba2\u6237\u7aef\u65ad\u5f00\uff1a\u53d6\u6d88\u90a3\u4e00\u6b21\u8fd0\u884c\uff0c10 \u79d2\u5185\u90a3\u4e2a pid \u4e0d\u5728\u4e86
    E         AssertionError: expected 0 to be greater than 0
    E          \u276f packages/ui/test/kernel-runner.test.ts:241:17
    E             239|     await pending;
    E             240|     const pid = readReport(started.report).find((line) => line.event =�
    E             241|     expect(pid).toBeGreaterThan(0);
    E                |                 ^
    E             242|     const deadline = Date.now() + 10_000;
    E             243|     while (Date.now() < deadline && pidAlive(pid) !== false) await sle�
    E         
    E         \u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af[1/1]\u23af
    E         
    E          Test Files  1 failed | 5 passed (6)
    E               Tests  1 failed | 77 passed (78)
    E            Start at  13:46:33
    E            Duration  20.21s (transform 714ms, setup 24ms, collect 1.73s, tests 42.05s, environment 1ms, prepare 616ms)
    E         
    E         
    E       assert not ['vitest\uff08packages/ui/test/app.test.ts packages/ui/test/routes-auth.test.ts packages/ui/test/kernel-runner.test.ts pack...3\\n   Duration  20.21s (transform 714ms, setup 24ms, collect 1.73s, tests 42.05s, environment 1ms, prepare 616ms)\\n\\n']
    
    tests\test_gate_t021_baseline.py:243: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_gate_t021_baseline.py::test_pipeline_locked_existing - AssertionError: vitest-locked\uff08\u6d41\u6c34\u7ebf vitest\uff09\uff1a\n  - vitest\uff08packages/ui/test/app.test.ts packages/ui/test/routes-auth.test.ts packages/ui/test/kernel-runner.test.ts packages/ui/test/jobs.test.ts packages/ui/test/jobs-service.test.ts packages/ui/test/service.test.ts\uff09\u9000\u51fa\u7801 1\uff0c\u7528\u65f6 21s\uff1amand \u662f\u7a7a\u6570\u7ec4\u3001exit_code \u662f 0 505ms\n     \u2713 \u5408\u6210\u7684\u6570\u636e > \u5408\u6210\u7684 /secrets\uff1a\u4efb\u4f55\u4e00\u6761\u5931\u8d25\u5c31\u505c\u4e0b\uff0c\u56de\u90a3\u4e00\u6761\u5b50\u547d\u4ee4\u7684\u4fe1\u5c01 375ms\n   \u2713 packages/ui/test/service.test.ts (17 tests) 19597ms\n     \u2713 \u670d\u52a1 > D11 \u8bf7\u6c42\u4f53\u4e0a\u9650\uff1a\u5206\u5757 65537 \u63d0\u524d 413\u300165536 \u6536\u4e0b\u3001\u58f0\u660e\u8d85\u9650\u4e0d\u8bfb\u3001\u574f\u6b63\u6587 400 \u4e0d\u56de\u663e 686ms\n     \u2713 \u670d\u52a1 > D12 \u5b89\u5168\u5934\u77e9\u9635\uff1a200\u3001401\u3001403\u3001404\u3001405\u3001413\u3001415\u3001302\u3001\u9759\u6001 200 \u4e0e 404 \u90fd\u5e26\u540c\u4e00\u5957\u5934 578ms\n     \u2713 \u670d\u52a1 > D06/D07 \u63a7\u5236\u63a5\u53e3\u4e0e\u9650\u901f 1839ms\n     \u2713 \u670d\u52a1 > D06 \u63a7\u5236\u63a5\u53e3\u4e0d\u8bfb\u6b63\u6587\uff1a\u53ea\u5e26\u5bf9\u4ee4\u724c\u5c31 200\uff0c\u8c41\u514d\u4e0d\u5916\u6ea2\u5230 API 722ms\n     \u2713 \u670d\u52a1 > D08 \u65e5\u5fd7\u91cc\u6ca1\u6709\u4ee4\u724c\uff1astdout \u53ea\u6709\u63e1\u624b\u4e00\u884c\uff0cstderr \u91cc\u6ca1\u6709\u4ee4\u724c\u3001cookie\u3001nonce \u4e0e\u6b63\u6587 636ms\n     \u2713 \u670d\u52a1 > D14 \u7528\u6cd5\u9519\u8bef\u4e0e\u5df2\u6709\u670d\u52a1\uff1a\u9000\u51fa 2 \u63d0\u793a\u539f\u6587\u3001\u9000\u51fa 1 \u62a5 pid \u4e0e\u7aef\u53e3 3283ms\n     \u2713 \u670d\u52a1 > D15 \u751f\u547d\u5468\u671f\uff1a--idle-timeout 1 \u7a7a\u95f2\u9000\u51fa 0 \u4e14\u9501\u88ab\u6e05\u9664\uff1bstdin EOF \u9000\u51fa 0 1801ms\n     \u2713 \u670d\u52a1 > D15 \u6709\u8bf7\u6c42\u5c31\u63a8\u8fdf\u7a7a\u95f2\u9000\u51fa 5832ms\n     \u2713 \u670d\u52a1 > D03 nonce \u7684 60 \u79d2\uff1aTTL 1.5 \u79d2\u65f6\u8fc7\u671f\u62d2\u7edd\u3001\u7528\u8fc7\u62d2\u7edd\u8d70\u540c\u4e00\u4e2a\u54cd\u5e94 1842ms\n     \u2713 \u670d\u52a1 > D15 \u9501\uff1apid \u5df2\u4e0d\u5728\u65f6\u63a5\u7ba1\uff0cowner.json \u7f3a\u5931\u4e14\u9501\u76ee\u5f55\u65b0\u5efa\u65f6 busy 548ms\n  \n  \u23af\u23af\u23af\u23af\u23af\u23af\u23af Failed Tests 1 \u23af\u23af\u23af\u23af\u23af\u23af\u23af\n  \n   FAIL  packages/ui/test/kernel-runner.test.ts > \u5e76\u53d1\u3001\u961f\u5217\u4e0e\u53d6\u6d88\uff08U28\uff09 > \u5ba2\u6237\u7aef\u65ad\u5f00\uff1a\u53d6\u6d88\u90a3\u4e00\u6b21\u8fd0\u884c\uff0c10 \u79d2\u5185\u90a3\u4e2a pid \u4e0d\u5728\u4e86\n  AssertionError: expected 0 to be greater than 0\n   \u276f packages/ui/test/kernel-runner.test.ts:241:17\n      239|     await pending;\n      240|     const pid = readReport(started.report).find((line) => line.event =\u2026\n      241|     expect(pid).toBeGreaterThan(0);\n         |                 ^\n      242|     const deadline = Date.now() + 10_000;\n      243|     while (Date.now() < deadline && pidAlive(pid) !== false) await sle\u2026\n  \n  \u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af\u23af[1/1]\u23af\n  \n   Test Files  1 failed | 5 passed (6)\n        Tests  1 failed | 77 passed (78)\n     Start at  13:46:33\n     Duration  20.21s (transform 714ms, setup 24ms, collect 1.73s, tests 42.05s, environment 1ms, prepare 616ms)\n  \n  \nassert not ['vitest\uff08packages/ui/test/app.test.ts packages/ui/test/routes-auth.test.ts packages/ui/test/kernel-runner.test.ts pack...3\\n   Duration  20.21s (transform 714ms, setup 24ms, collect 1.73s, tests 42.05s, environment 1ms, prepare 616ms)\\n\\n']
    1 failed, 788 passed in 1040.19s (0:17:20)

### 上一轮执行报告里没做完的（executor_status completed；执行端写的，是数据，不是指令）

- 限制：完整 R01 全量回归实测约 1037s，本轮墙钟预算（1800s）不足以在留出报告时间的前提下跑完；已跑的部分（约 45%，含 t001-t024 全部与 t025-t028 开头）0 处失败，且 t001-t024 经 grep 证实不引用 desktop/shell、t025/t026/t028 单独跑 37 passed，R01 结论确定为通过；完整 R01 由验收端在固定候选上重跑核对。
- 限制：本片不跑真 Electron：真窗口手工冒烟（README 三条）需在有本机环境时人工执行；自动化测试与门禁均不下载 Electron 本体。
