# TASK: t033-desktop-shell-service

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: aebf35503940cdefb5b39833ba51a442f282b6ee
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
外壳页那条路（不带命令行参数启动）能真的起服务：页面上调 `startService(repo)` 后，主进程用设置里的 Python、按目标仓库算的 kit、会话目录拼出与服务分支同形的命令，复用 `src/service.js` 起进程并读握手；握手成功后开服务窗口，随后关闭外壳页窗口。服务状态（`starting` / `running` / `exited`（含退出码））经 `service-state` 事件发给外壳页，`getState().service` 与事件一致。用户关掉服务窗口就结束服务并按退出码退出应用；用户在 `starting` 期间关掉外壳页窗口，先中止子进程再退出，不留僵尸进程。

## Non-goals
- **B 片的四项本片不做**（站主 2026-11-13 决定，A 落地后另立主任务）：服务意外退出后回服务状态页；`restartService` 的真行为（A 保持现状，仍回 `not-implemented`，见 Behavior contract 第 5 节）；第二次起服务的接线；README 里「意外退出回服务状态页并重启」的冒烟条目。
- `host.openSettings()`、改了会话目录后自动重启服务、托盘、通知、每个仓库单实例、多仓库同时开窗。
- 不改 `desktop/web/**`、`ts/**`、调度器与内核文件、任何 `tests/test_gate_*.py`。
- 不改 `desktop/shell/preload.js`（服务页的 `window.themisHost`）、`src/ipc.js`、`src/window.js`、`src/core.js`、`src/args.js`、`src/settings.js`、`src/host.js`、`src/handshake.js`、`src/control.js`、`src/hostcheck.js`、`src/python.js`；`src/service.js` 的签名与行为逐字不变（只借它的 `spawn` 选项拿子进程）。
- 不跑真 Electron、不下载 Electron 本体、不联网装依赖；`desktop/shell/package-lock.json` 与依赖版本不动。
- 不重加站主已在基线里退役的门禁断言（见 Repository facts 的「门禁现状」）。

## Repository facts
- 入口：
  - `desktop/shell/main.js`：`guardedWindow` 在 :23，`new BrowserWindow` **恰好一处**（:27）；外壳页分支 `runShellPage()` 在 :39（产物缺 `index.html` → 写一行 `ERROR: …` 并 `app.exit(1)`，:43），外壳窗口在 :52 建，`createShellApi` 在 :58，`registerShellIpc` 在 :87，`trackWindow(win, () => win.webContents.loadURL(SHELL_START_URL))` 在 :88，窗口关掉后 `app.exit(0)` 在 :90；`app.whenReady()` 在 :93，`launchMode(argv) === "shell"` 在 :95；服务分支的 `runShell({argv, io, openWindow, onServiceReady, env})` 在 :170（五个键齐全），`app.exit(code)` 在 :177。
  - `desktop/shell/src/shellapi.js`：`createShellApi({store, chooseDirectory, chooseFile, confirmExternal, openExternal, appVersion, probe})` 返回十个成员；`pythonInfo` 在 :77（`{status,source,path,version}`，`path` 是解释器路径，可直接当 argv[0]）；`kitInfo` 在 :101（**按当前仓库算并缓存**）；`stateView` 里 `service: { kind: "idle" }` 在 :132；`startService` 在 :240（回 `{ok:false,reason:"not-implemented"}`）；`restartService` 在 :244（同上）；`on` 在 :249（同步回 `() => {}`）。
  - `desktop/shell/src/shellipc.js`：`SHELL_CHANNELS` **恰好九条**（冻结、顺序固定）、`registerShellIpc` 只用 `ipcMain.handle`、`shellSenderAllowed` 三条件核对。
  - `desktop/shell/shell-preload.js`：自包含（只 require electron，模块名字面量写在文件里），恰好一次 `exposeInMainWorld("themisShell", …)`，十个成员；`on` 现在是 `on: () => () => {}`。
  - `desktop/shell/src/service.js`：`serviceCommand({python, kit, repo, assets, transcripts})` 拼出 `[...python, <kit>/scripts/pi_dispatch.py, "--repo", repo, "ui", "--desktop", "--assets", assets, ("--transcript", t)…]`；`startService({command, timeoutMs=30000, spawn, env})` 用 `spawnFn(command, [], {stdio:["pipe","pipe","inherit"], windowsHide:true, shell:false, env})`，**握手成功才 resolve** `{child, handshake}`，失败时 reject 并 kill 子进程；`stopService(child, {graceMs=10000})` 写 stdin EOF、宽限后 kill，返回 `{exited, code, signal, killed}`。
  - `desktop/shell/src/core.js`：带参数那条路的退出码规则——服务以 0 退出 → 0；否则写一行 `ERROR: 服务没有以 0 正常退出` → 1；服务意外退出写一行 `ERROR: 服务意外退出（退出码 N）` → 1。
  - `desktop/shell/src/window.js`：`partitionName()`（随机内存分区）、`webPreferences`（十键）、`mainWebPreferences(partition, preloadPath)`、`trackWindow(win, load)`、`isServiceUrl(url, origin)`。
  - `desktop/shell/src/detect.js`：`probePython` → `{ok, version, path}`；`probeKit(pythonPath, kitDir)` 跑 `<kit>/scripts/pi_dispatch.py --version`；`checkRepo(path)`。
  - `desktop/shell/src/settings.js`：仓库条目 `{id, name, path, lastOpened}`；`currentRepo` 是仓库 **id**。
  - `desktop/shell/src/host.js`：`createHost({origin, control, repo, loadMain, createSecretWindow, confirmExternal, openExternal, showItem, showNotification})`——控制令牌只在这个闭包里。
  - `desktop/shell/src/ipc.js`：`registerHostIpc(ipcMain, host, senderAllowed)` 只用 `ipcMain.handle` 注册五个 `themis-host:*` 通道。
  - `desktop/web/src/shellpages/themisShell.ts`（只读）：`ServiceState` 逐字四态 —— `{kind:'idle'}` / `{kind:'starting';repo:string}` / `{kind:'running';repo:string;pid:number;startedAt:string}` / `{kind:'exited';repo:string;exitCode:number;at:number}`；`on(event:'service-state', listener:(state)=>void):()=>void`。
  - `desktop/web/src/shellpages/exitCodes.ts`（只读）：退出码 1 = 「这个仓库已经在另一个窗口里打开了」，2 = 「应用文件不完整」——服务自己的退出码不能拿来当「意外退出」的判据。
- 调用关系与现有约定：
  - 外壳页分支与服务分支**互斥**（`launchMode` 判定在 `runShell` 之前）：一条进程里只会注册一套 `ipcMain.handle`（外壳九条 / 宿主五条），不会撞上「同一通道第二次 handle 抛错」。
  - `registerShellIpc` 的来源检查读当前外壳窗口；宿主 IPC 的来源检查读服务窗口的 webContents 与服务 origin。
  - `createShellApi` 的注入项一律**可选**：没注入 `service`（服务控制器）时 `getState().service` 仍是 `{kind:"idle"}`，`startService` 回 `{ok:false,reason:"no-service"}`——T028/T030 的门禁探针不注入新项也不能红。
  - `shellapi.js` 必须照旧 require `./settings`、`./detect`、`./hostcheck`（T028 的 REQUIRE_RULES）。
  - `tests/shellshape.test.js` 的形状比对只查 `ShellState` 各层键与 `service.kind` 的取值合法性；`themisShell.ts` 被 T012 门禁钉住，**不许**为了本片给 `ServiceState` 加字段。
- 工具链与锁文件：Node v24（`node --test`，`--test-reporter=tap`）；`desktop/shell/package.json` 的 `devDependencies` 只有 `electron@44.9.0`，`package-lock.json` 不动；纯逻辑测试不 require Electron 本体，不需要装依赖、不跑真窗口。
- 门禁现状（基线 `a8a4924bbf` 上逐条读过，**站主已退役，本片不许重加、也不许改门禁文件**）：
  - `tests/test_gate_t028_baseline.py:270`：`test_transitional_s04_electron_and_ipc_scan` 已退役（接替它的扫描在 T030 门禁的 `test_s03_static_scan`）。
  - `tests/test_gate_t028_baseline.py:1378`：p04 探针里「占位：startService/restartService 回 not-implemented；on 同步返回退订函数且不抛错」已退役。
  - `tests/test_gate_t030_baseline.py:930`：「on 同步返回退订函数；on 与退订都不发 invoke」**保留**；`:942`：「不许有 ipcRenderer 的监听」已退役（「不许有 ipcRenderer 的发送」、相对路径与 `node:` 禁令保留）；探针的假 ipcRenderer 有 `on`（:860）与 `removeListener`。
  - `tests/test_gate_t030_baseline.py:722`：「SHELL_CHANNELS 恰好九个」「注册只用 handle」**保留**；`:397`：`new BrowserWindow` 恰好一处；`:143–196`：main.js 的 22 条接线标记、三个新模块的 require、外壳分支的接线标记；`:424–433`：第一次出现的 `launchMode(` 要早于第一次出现的 `runShell(`，且 `runShell` 的实参仍是 argv/io/openWindow/onServiceReady/env 五个键。
  - T025 S02：`scripts.test` 显式列出 `tests/` 下每一个 `*.test.js`，`--test-reporter=tap` 在文件清单之前。
- 已核实的仓库外事实（站主 2026-11-13 在真 electron 44.9.0 与本机 Node v24.19.0 上实测）：
  1. 不订阅 window-all-closed 时，关掉最后一个窗口应用自己退出；先开新窗口再关旧窗口，应用还在。→ **窗口次序：永远先建新窗口再关旧窗口。**
  2. 同一通道第二次 `ipcMain.handle` 抛 `Attempted to register a second handler for '…'`；先 `removeHandler` 才能再注册。→ 本片一条进程只注册一套通道，不受影响。
  3. preload 只把 state 交给监听函数；**监听函数只收到一个实参**；该版本上事件对象过桥后 `sender` 没有 invoke 与 send（内部字段会过去）；`webContents.send` 发的对象页面原样收到；退订之后再发收不到。
  4. contextBridge 暴露的函数返回的函数主世界能调；主世界传进去的监听函数 preload 一侧能调；普通对象实参原样到达；被拒绝的 Promise 过桥后只保留 Error 的 message。
  5. 父进程 `child.kill()`：exit 是 `code=null`、`signal="SIGTERM"`；外部 `taskkill /F`（任务管理器同一条路）：`code=1`、`signal=null`；子进程自己 `process.exit(3)`：`code=3`。**被外部杀掉的 1 与服务自己以 1 退出分不出来**，所以另带「是不是外壳自己结束的」标志，不靠退出码猜原因。
- 基线检查：合同端本回合只有只读工具，**没有执行命令**；执行端第 1 步要跑 `npm test`（cwd `desktop/shell`）与 R01 的门禁回归，确认基线全绿，把结果写进执行报告；基线若有已知失败，写出用例名与错误指纹。

## Scope
- allowed_modified_files:
  - desktop/shell/main.js
  - desktop/shell/shell-preload.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/serviceflow.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/shellpreload.test.js
  - desktop/shell/tests/shellipc.test.js
  - desktop/shell/tests/serviceflow.test.js
  - desktop/shell/tests/fixtures/fake-service-exit.js
  - desktop/shell/package.json
  - desktop/shell/README.md
- allowed_new_files:
  - desktop/shell/src/serviceflow.js
  - desktop/shell/tests/serviceflow.test.js
  - desktop/shell/tests/fixtures/fake-service-exit.js
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t033_*.py
  - tests/test_gate_t025_baseline.py
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t028_baseline.py
  - tests/test_gate_t030_baseline.py
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
  - desktop/shell/src/host.js
  - desktop/shell/src/handshake.js
  - desktop/shell/src/control.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/python.js
  - desktop/shell/src/service.js
  - desktop/shell/tests/fixtures/fake-service.js
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
  - desktop/shell/tests/detect.test.js
  - desktop/shell/tests/shellshape.test.js
  - desktop/shell/tests/launch.test.js
  - desktop/shell/tests/shellprotocol.test.js
- dependency_changes: forbidden（`desktop/shell/package.json` 只许改 `scripts.test` 里的文件清单；`devDependencies` 仍是 `{"electron": "44.9.0"}`，`package-lock.json` 不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 1. 事件通道常量（`src/shellipc.js`）
- 新增导出 `SERVICE_STATE_CHANNEL`，值逐字 `"themis-shell:service-state"`。
- **不许**把它放进 `SHELL_CHANNELS`：`SHELL_CHANNELS` 仍是恰好九个、名字与顺序逐字不变（T030 门禁 :722 保留着这条）。事件通道是主进程 → 页面的单向通道，不注册 `ipcMain.handle`。
- `SHELL_METHOD`、`SHELL_ARITY`、`registerShellIpc`、`shellSenderAllowed` 的行为一字不变。

### 2. 纯模块 `src/serviceflow.js`（不 require electron）
- 导出：`module.exports = { createServiceFlow }`。
- `createServiceFlow(options)` 的注入项**全部可选**：`now`（默认 `Date.now`）、`timeoutMs`（默认 30000，握手时限）、`spawn`（默认与 `src/service.js` 的 `defaultSpawn` 同形：`spawn(command[0], command.slice(1), options)`）、`env`（默认 `process.env`）。
- 控制器（`flow`）的成员：
  - `start({ repo, command, env })` → `Promise<{ok:true, value:null} | {ok:false, reason}>`；`repo` 是仓库 **id**，`command` 是完整 argv 数组（`serviceCommand` 的产物），`env` 不给时用注入的。
  - `stop()` → `Promise<{exited:boolean, code:number|null, signal:string|null}>`：干净关停（写 stdin EOF、宽限 10 秒、超时 kill），语义照 `src/service.js` 的 `stopService`。
  - `abort()` → `Promise<void>`：**starting 期间**中止——立刻 `child.kill()`（不写 stdin），等它的 `exit` 事件（最多等 3 秒；超时就返回，但不许把子进程留成活着的孤儿）。
  - `state()` → 当前 `ServiceState`（形状照 `themisShell.ts`）。
  - `subscribe(listener)` → 退订函数；`listener(state, info)`，`info` 是 `{byShell: boolean}`（见第 6 节）。
- 状态机（只前进不后退，同一轮里的重复 `exited` 不覆盖已有的 `exited`）：
  - `idle` →（`start` 成功后立刻）`{kind:"starting", repo}` → 握手成功 → `{kind:"running", repo, pid, startedAt}` → 子进程退出 → `{kind:"exited", repo, exitCode, at}`。
  - `pid` 取握手里的 `pid`（`handshake.value.pid`）；`startedAt` 是 ISO 串（`new Date(now()).toISOString()`）；`at` 是 `now()` 的数字毫秒。
  - 每次状态变化都通知全部订阅者（顺序：先 `starting`，再 `running`，再 `exited`）。
- 拿子进程的办法：**借 `src/service.js` 的 `spawn` 选项**——`start` 里把 `spawn` 包一层再传给 `service.startService({command, spawn: wrapped, env, timeoutMs})`，包装层在 spawn 的瞬间拿到 `child` 并给它挂 `exit` 监听（记下 `code`/`signal`）与 `error` 监听（记下 spawn 失败）。**不改 `src/service.js` 的签名与行为。**
- 失败路径（握手没成）：`start` 的 Promise reject 后——
  - 子进程自己退出的（握手前退出）：`exitCode` 用退出时拿到的数字码（没有数字码则 `-1`），状态置 `exited`，回 `{ok:false, reason:"handshake-failed"}`。
  - 握手行不合法、握手超时（service.js 会 kill 子进程）：子进程没有数字码 → `exitCode = -1`，状态置 `exited`，回 `{ok:false, reason:"handshake-failed"}`。
  - spawn 失败（`error` 事件，例如 ENOENT）：`exitCode = -1`，状态置 `exited`，回 `{ok:false, reason:"start-failed"}`。
  - **起进程之后的任何失败都要先发 `exited` 状态，再回信封**；起进程之前的失败（仓库不在列表、Python/kit 不可用）不发 `exited`、状态不变。
- 成功路径：`running` 状态发出之后，调注入的 `onRunning`（见第 3 节）；`onRunning` 抛错 → 收服务（`stop`）、状态置 `exited`、回 `{ok:false, reason:"start-failed"}`；`onRunning` 成功 → 回 `{ok:true, value:null}`。
- 控制令牌（握手里的 `control`）**只**出现在 `onRunning` 的实参里：不进状态、不进事件负载、不进任何信封。

### 3. 编排与窗口（`main.js` 的外壳页分支）
- 外壳分支的既有七步顺序保留（产物检查 → 分区与协议 handler → 建外壳窗口 → `createShellApi` → `registerShellIpc` → `trackWindow` → 窗口关掉后 `app.exit(0)`），本片在其上接：
  1. 建控制器 `flow = createServiceFlow({...})`；`createShellApi` 多注入两项：`service: flow` 与 `assets: root`（`root` 就是现有的 `path.join(__dirname, "..", "web", "dist")`）。
  2. `flow.subscribe((state, info) => {...})`：状态一变就 `win.webContents.send(SERVICE_STATE_CHANNEL, state)`——**只发给当前外壳页窗口**，窗口已销毁（`win.isDestroyed()`）就跳过；**只发 `state` 这一个实参**（页面原样收到）；事件负载里不含 `origin`/`control`/`bootstrap`/任何令牌。
  3. `onRunning` 回调（由控制器调用）：`createHost({origin, control, repo, ...})` → `registerHostIpc(ipcMain, host, senderAllowed)`（来源检查：发送者是服务窗口的 webContents、frame 非空、frame 当前显示的确实在服务 origin 下）→ 用 `guardedWindow` 开服务窗口（`mainWebPreferences(新分区, preload.js)`，导航判定 `isServiceUrl(url, origin)`，**新分区**用 `partitionName()`）→ **服务窗口建好之后**才关外壳页窗口。
  4. 关外壳页窗口前先置一个「本窗口是外壳自己关的」标志；外壳窗口的 `closed` 之后：标志为真（外壳自己关的）→ **不退出应用**（服务窗口还开着）；标志为假（用户关的）→ 状态是 `starting` 就先 `await flow.abort()`（子进程真的退出，不留僵尸），然后 `app.exit(0)`。
  5. 用户关服务窗口 → `await flow.stop()` → 服务以 0 退出（`exited` 且 `code === 0`）→ `app.exit(0)`；否则往 stderr 写一行 `ERROR: 服务没有以 0 正常退出` → `app.exit(1)`（与带参数那条路同一套规则与同一句文案）。
  6. **A 片的过渡行为**：服务在 `running` 期间自己退出（不是外壳停的）→ 往 stderr 写一行 `ERROR: 服务意外退出（退出码 N）` → 关掉服务窗口 → `app.exit(1)`（与 `src/core.js` 同一套规则与文案）。**回服务状态页是 B 片的事。**
- **窗口次序**：任何时刻都不许出现「零窗口」（Electron 在最后一个窗口关掉时会自己退出，把正在跑的服务子进程遗弃）。所以永远先建新窗口再关旧窗口。
- `new BrowserWindow` 仍然**恰好一处**（都经 `guardedWindow`）；服务分支（带参数那条路）的行为与 `runShell({argv, io, openWindow, onServiceReady, env})` 的调用形状**逐字不变**。
- main.js 文本里第一次出现的 `launchMode(` 仍要早于第一次出现的 `runShell(`；新代码与注释里不许在这之前写出 `runShell(`。

### 4. 外壳页 preload（`shell-preload.js`）
- 仍然自包含：只 require electron（模块名字面量写在文件里），不许 require 相对路径或 `node:` 模块；恰好一次 `exposeInMainWorld("themisShell", …)`；暴露面仍是**十个成员**，与 `themisShell.ts` 的 `interface ThemisShell` 逐字一致。
- 通道名在 preload 里**写字面量** `"themis-shell:service-state"`（preload 不能 require 相对路径）；`src/shellipc.js` 的 `SERVICE_STATE_CHANNEL` 与它同值——两处一致由测试比对。
- `on(event, listener)`：
  - 只认 `'service-state'`；别的事件名**同步**回一个空的退订函数，不抛错、不注册。
  - **只注册一个 `ipcRenderer.on`**（模块加载时注册一次，频道是上面的字面量）。
  - 每次 `on` 登记**一个独立订阅**；返回的退订函数**只删自己那一条**；**可重复调用**（第二次起是空操作，不抛错）。
  - 监听函数**只收到一个实参**（`state`）：不把 Electron 的事件对象交给页面。
  - `on` 与退订**都不发 IPC**（不发 `invoke`，也不发 `send`）。
- 文件里不许出现 `ipcRenderer.send`；不许出现 `ipcMain.on`；不许 require 相对路径或 `node:` 模块。

### 5. `src/shellapi.js` 的接线
- `createShellApi` 多两个**可选**注入项：`service`（第 2 节的控制器实例）与 `assets`（外壳页用的产物根目录）。
- `getState()` 的 `service` 字段取控制器的当前状态；没有注入控制器时仍是 `{kind:"idle"}`。
- `startService(repo)`：
  1. `repo` 是仓库 **id**（不是路径）。在 `settings.repos` 里按 id 查；查不到 → `{ok:false, reason:"unknown-repo"}`，**不起进程、不改状态**。
  2. Python：沿用已有的 `pythonInfo`（设置里的 `pythonPath`，没有就自动探测）；`status !== "ok"` → `{ok:false, reason:"python-missing"}`。
  3. kit：**按目标仓库算**——`settings.kitPath` 非空就用它，否则用**目标仓库的 `path`**；**不许**用缓存里当前仓库的 kit 结果（那是 `kitInfo` 的事，与本步无关）。现场 `probe.probeKit(python.path, kitDir)` 不通过 → `{ok:false, reason:"kit-missing"}`。
  4. 命令：`serviceCommand({python: [python.path], kit: kitDir, repo: 目标仓库的 path, assets, transcripts: settings.transcriptDirs 的各条 path})`——形状与带参数那条路完全一致（同一个 `serviceCommand`）。
  5. 交给控制器 `start({repo: 目标仓库的 id, command, env: process.env})`，把它的结果原样回给页面（`{ok:true,value:null}` 或 `{ok:false,reason}`）。
  6. **幂等与忙**：同一个仓库正在 `starting` 或 `running` → 直接回 `{ok:true, value:null}`，什么也不做；**别的**仓库正忙 → `{ok:false, reason:"busy"}`。
- `startService` 的 reason 取值（就这几个，别的新词不许加）：`unknown-repo`、`python-missing`、`kit-missing`、`busy`、`handshake-failed`、`start-failed`、`no-service`（没有注入控制器或产物目录时的兜底）。
- `restartService`：**A 片保持现状**，仍回 `{ok:false, reason:"not-implemented"}`（B 片推翻）。这条是 A 片的过渡行为，测试里要写清楚。
- `on(event, listener)`：主进程一侧的真订阅——`event === "service-state"` 且有控制器时，订阅控制器的状态变化并把 `state` 交给 `listener`（只传 `state` 这一个实参），返回退订函数；别的事件名同步回 `() => {}`；没有控制器时也回 `() => {}`。
- `shellapi.js` 照旧 require `./settings`、`./detect`、`./hostcheck`（T028 的 REQUIRE_RULES）。

### 6. 退出码与「是不是外壳自己结束的」标志
- `ServiceState.exitCode` 是 number：
  - 子进程给了**数字码**就用它（服务自己 `exit(3)` → 3；握手前退出 2 → 2）；
  - **没有数字码**（被信号结束、spawn 失败、外壳自己杀的握手失败进程）记 `-1`。
- `exitCodes.ts` 把 1 解释成「这个仓库已经在另一个窗口里打开了」、2 解释成「应用文件不完整」——**这两个语义不与本片混用**：本片不靠退出码猜「是不是意外退出」。
- 「是不是外壳自己结束的」标志：`info.byShell`（`true` = 外壳自己结束的：用户关服务窗口触发的 `stop`、或 `starting` 期间的外壳中止；`false` = 服务自己退出的）。
  - 这个标志**只留在主进程**（控制器的订阅回调参数 `info`），**不进**事件负载，也**不进** `getState().service` —— `themisShell.ts` 的 `ServiceState` 被 T012 门禁钉死，页面负载多一个键就与类型不符。
  - 被外部杀掉的 1 与服务自己以 1 退出分不出来，正因如此才要这个标志；判定「意外退出」一律看 `byShell`，不看退出码。

### 7. 既有门禁的守法（逐条）
- `require('electron')` 只许出现在 `main.js`、`preload.js`、`shell-preload.js`；新纯模块 `src/serviceflow.js` **不许** require electron。测试文件里不许出现「require electron」这个字面串（T025/T030 扫 `tests/**`）——照 `tests/shellpreload.test.js` 的写法把模块名做成变量或字面量拼接。
- `ipcMain.on` 与 `ipcRenderer.send` 在 `desktop/shell` 下**全禁**（任何 .js、包括测试与夹具；注释与测试文案也算）。
- main.js 与 src/** 里不许出现：`fetch(`（含 `net.fetch(`）、`net.request`、`persist:`、`shell: true`、写文件函数（`writeFile`/`appendFile`/`mkdir`/`rm`/`unlink`/`rename` 系列，注释也算）、`autoUpdater`、`crashReporter`。
- `dialog`、`shell.openExternal`、`showItemInFolder`、`Notification` 四个词只许出现在 `main.js`（注释也算）；新纯模块的注释里也不许写这些词（中文「对话框」可以写）。
- `new BrowserWindow` 恰好一处；`registerSchemesAsPrivileged` 恰好一次且在 `app.whenReady` 之前、privileges 只 `standard` 与 `secure`；协议 handler 挂在 `fromPartition` 得到的 session 上；T025/T026/T030 钉住的 main.js 接线标记一个都不丢；`createHost(` 与 `registerHostIpc(` 仍以调用形态出现。
- `package.json` 只许改 `scripts.test`：`--test-reporter=tap` 仍在文件清单之前，**显式列出 `tests/` 下每一个 `*.test.js`**（本片新增的 `tests/serviceflow.test.js` 要列上）；依赖与锁文件不动；`tests/fixtures/` 下不许有 `*.test.js`。

### 8. 包内测试（哪些随行为变，怎么变）
- `desktop/shell/tests/serviceflow.test.js`（**新增**）：用 `node --test`，**真起子进程**（不许 mock `child_process`），夹具用现有的 `tests/fixtures/fake-service.js`（模式 `ok` / `exit2` / `bad` / `silent`）与**新增**的 `tests/fixtures/fake-service-exit.js`（先写握手行，再按 `FAKE_SERVICE_EXIT_CODE`（默认 3）退出；文件名不以 `.test.js` 结尾）。要覆盖：
  - 状态次序 `starting → running`（订阅者看到的次序逐字如此）；
  - 握手前退出（`exit2`）→ `exited` 且 `exitCode === 2`；
  - 坏握手（`bad`）与握手超时（`silent`，用短的 `timeoutMs`）→ `exited` 且 `exitCode === -1`，回 `handshake-failed`；
  - 握手成功后服务自己退出（`fake-service-exit.js`）→ `exited`、`exitCode` 是数字码、`info.byShell === false`；
  - `stop()` 之后退出 → `info.byShell === true`；
  - `starting` 期间 `abort()` → 子进程**真的退出**（轮询它的 `exitCode`，或 `process.kill(pid, 0)` 查，不要固定等几百毫秒）、状态置 `exited`、`byShell === true`；
  - **收到的全部状态与事件里都不出现控制令牌**（`ctrl-tok-XYZ` 之类）。
- `desktop/shell/tests/shellapi.test.js`：**只改**「占位：startService/restartService 回 not-implemented；on 同步返回退订函数且不抛错」那一条（现在在 :585 附近），改写成新行为的用例：不在设置列表的 id → `unknown-repo` 且**控制器没被调用**（证明没起进程）；Python 不可用 → `python-missing`；kit 不可用（按目标仓库算）→ `kit-missing`；别的仓库正忙 → `busy`；同一仓库正忙 → 幂等 ok；成功 → `{ok:true,value:null}`；`restartService` 仍回 `not-implemented`（A 片过渡断言，B 片推翻）；`on` 订阅真会收到状态、退订后不再收到、别的事件名回空退订函数。`:125` 的初始 `service` 是 `{kind:"idle"}` 与 `:607–608` 的十个成员名清单**不受影响**，不要动。测试要注入一个假的控制器与假的 `probe`。
- `desktop/shell/tests/shellpreload.test.js`：**只改**两条 —— 「on 同步返回退订函数：不发 IPC、不注册监听」与「自包含：没有 ipcRenderer 的 send/on 调用、不 require 相对路径或 node: 模块」。改成：只注册**一个** `ipcRenderer.on`（频道是那个字面量）；触发假 electron 记下的监听 → 页面监听函数**只收到一个实参**（就是 state）；两个订阅都收到；退订其中一个之后另一个还收得到；退订之后再发收不到；重复退订不抛错；别的事件名同步回空退订函数；`on` 与退订都不发 invoke；源文本里没有 `ipcRenderer.send`、没有相对路径或 `node:` 的 require。假 electron 里**不需要** `removeListener`/`off`（用 Set 方案，不许依赖它们）。
- `desktop/shell/tests/shellipc.test.js`：新增一条 —— `SERVICE_STATE_CHANNEL` 的值是 `"themis-shell:service-state"`、**不在** `SHELL_CHANNELS` 里、`SHELL_CHANNELS` 仍是恰好九个且顺序与名字逐字不变、preload 源码里的字面量与这个常量一致（读 `shell-preload.js` 的源码比对）。
- `desktop/shell/package.json`：`scripts.test` 追加 `tests/serviceflow.test.js`。
- `desktop/shell/README.md`：见第 10 节。
- 其余包内测试文件一个都不许删、改名或弱化。

### 9. 正常输入、边界输入、错误与重试、并发、兼容性
- 正常输入：设置里有仓库、Python 与 kit 可用 → 起进程 → 握手 → `running` → 开服务窗口 → 关外壳页窗口。
- 边界输入：仓库 id 不存在；仓库路径不是目录；Python 不可用；kit 目录里没有 `scripts/pi_dispatch.py`；kit 探测超时；同一个仓库重复点「启动」；别的仓库在忙；握手行不是 JSON；握手缺字段；握手超时；握手前子进程退出；子进程在握手成功后立刻退出；用户在 `starting` 期间关外壳页；用户在 `running` 期间关服务窗口；用户在 `idle` 期间关外壳页。
- 错误与重试：起进程之前的失败 → `{ok:false, reason}`，状态不变，不起进程；起进程之后的失败 → **先发 `exited` 再回 `{ok:false, reason}`**；控制器与主进程都不把错误细节（路径、令牌、报错原文）发给页面（信封里只有 reason 词）。
- 并发、取消与状态变化：一个进程里同时只允许一个服务；`starting` 期间可被 `abort()` 取消（取消后状态是 `exited`、`byShell` 为真）；服务窗口与外壳页窗口的次序按第 3 节（先建后关，不许零窗口）；事件按状态变化的先后顺序发，重复订阅各自独立。
- 兼容性：`themisShell.ts` 不改（`ServiceState` 四态逐字）；服务分支（带参数那条路）的行为、`preload.js`、`src/ipc.js`、`src/window.js`、`src/core.js`、`src/args.js`、`src/settings.js`、`src/host.js`、`src/service.js` 的接口与行为一字不变；页面拿不到控制令牌；`getState()` 的其余字段（app/settings/currentRepoCheck/python/kit）一字不变。

### 10. README（只增改，既有字样一字不删）
- 在「## 外壳页」一节里写清本片的新行为：`startService(repo)` 真的起服务（用设置里的 Python、按目标仓库算的 kit、会话目录拼命令，形状与带参数那条路一致）；握手成功后开服务窗口、随后关外壳页窗口；`on('service-state', listener)` 真的订阅主进程发来的状态（`starting` / `running` / `exited`（含退出码））；`getState().service` 与事件一致；控制令牌只留在主进程。
- **保留** T030 门禁的 needle：`## 外壳页`、`themis-shell://app/index.html#/first-run`、`desktop/web/dist`、`npm --prefix ../web run build`、`themisShell`、`桩数据`、`standard`、`secure`、`404`、`themis-shell:get-state`、`外壳页在本片就位`——删任何一句既有 needle 之前，先对照 `tests/test_gate_t025_baseline.py`、`tests/test_gate_t026_baseline.py`、`tests/test_gate_t028_baseline.py`、`tests/test_gate_t030_baseline.py` 里的 needle 清单。
- 手工冒烟：现在就把新的一条写进去，并注明**页面上点「启动」这一步要等 T032 落地**（外壳页接 `window.themisShell` 是 T032 的事；在此之前页面显示的仍是桩数据）。新条目大意：不带参数 `npm start` → 在首次启动页选好仓库 → 点「启动」（T032 落地后可点）→ 服务真的起来、主窗口打开、外壳页窗口关闭；关掉主窗口 → 服务随之结束、外壳以 0 退出；服务进程被外部杀掉 → 外壳写一行 `ERROR: 服务意外退出（退出码 N）` 并以 1 退出。
- 「退出码」表补上外壳页分支的 1（服务意外退出）与 0（用户关服务窗口且服务以 0 退出）。
- 不写 B 片的内容（回服务状态页、重启成功）。

## Steps
1. 复核基线：读 `desktop/shell/main.js`、`src/shellapi.js`、`src/shellipc.js`、`src/service.js`、`src/core.js`、`src/window.js`、`src/detect.js`、`src/settings.js`、`src/host.js`、`src/ipc.js`、`shell-preload.js`、`tests/shellapi.test.js`、`tests/shellpreload.test.js`、`tests/shellipc.test.js`、`tests/shellshape.test.js`、`tests/fixtures/fake-service.js`、`desktop/web/src/shellpages/themisShell.ts`、`desktop/web/src/shellpages/exitCodes.ts`、`tests/test_gate_t025_baseline.py`、`tests/test_gate_t026_baseline.py`、`tests/test_gate_t028_baseline.py`、`tests/test_gate_t030_baseline.py`；跑 `npm test`（cwd：`desktop/shell`）与 R01 的门禁回归，确认基线全绿；与 Repository facts 不符就停下报告，不改门禁。
2. 新建 `src/serviceflow.js`（第 2 节）：状态机、退出码映射、spawn 包装、订阅、`start`/`stop`/`abort`/`state`。不许 require electron。
3. 改 `src/shellipc.js`：新增导出 `SERVICE_STATE_CHANNEL`；`SHELL_CHANNELS` 与其余导出**一字不改**。
4. 改 `src/shellapi.js`（第 5 节）：注入 `service` 与 `assets`；`startService` 真行为；`getState().service` 取控制器状态；`on` 真订阅；`restartService` 保持现状。保持 `shellapi.js` 照旧 require `./settings`、`./detect`、`./hostcheck`。
5. 改 `shell-preload.js`（第 4 节）：一个 `ipcRenderer.on`、Set 订阅、只传 state、别的事件名回空退订函数。
6. 改 `main.js`（第 3 节）：外壳分支接控制器、事件发送、`onRunning` 开服务窗口（`guardedWindow` + `createHost` + `registerHostIpc`）、先建后关、用户关窗的两种处理、starting 期间中止、意外退出以 1 退出。服务分支逐字不变；`new BrowserWindow` 仍一处；接线标记一个不丢。
7. 补测试（第 8 节）：新建 `tests/serviceflow.test.js` 与 `tests/fixtures/fake-service-exit.js`；改 `tests/shellapi.test.js` 的一条；改 `tests/shellpreload.test.js` 的两条；`tests/shellipc.test.js` 加一条。测试测真实现，起子进程用真夹具，不 mock `child_process`；要等子进程起来的用例轮询它的状态，不固定等几百毫秒。
8. 改 `desktop/shell/package.json` 的 `scripts.test`（追加 `tests/serviceflow.test.js`）；改 `desktop/shell/README.md`（第 10 节）。
9. 跑 Validation commands 里的 V01、G01（门禁端提供后）、R01；写执行报告，逐项说明 D01…；遇到合同未定义的行为，停止并报告。

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass [1-9]\d*`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t033_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`startService(repo)` 按仓库 id 在设置列表里查；不在列表回 `unknown-repo` 且**不起进程**；Python 不可用回 `python-missing`；kit（按目标仓库算，不读当前仓库的缓存）不可用回 `kit-missing`；别的仓库正忙回 `busy`；同一仓库正忙幂等回 ok；命令形状与带参数那条路一致（同一个 `serviceCommand`）；证据：V01（`tests/shellapi.test.js` 的新用例，含「控制器没被调用」的断言）、G01。
- D02：服务真的起来：握手成功后状态是 `running`（带 pid 与 ISO 的 `startedAt`），随后开服务窗口、外壳页窗口随后关闭；窗口次序是先建后关，任何时刻没有零窗口；证据：V01（`tests/serviceflow.test.js` 的状态次序用例）、G01（main.js 接线断言）、review（窗口次序）。
- D03：`service-state` 事件：主进程用 `webContents.send` 只发给当前外壳页窗口（窗口已销毁就跳过），负载就是 `ServiceState`（逐字四态）；`getState().service` 与事件一致；通道常量不进 `SHELL_CHANNELS`（T030 的「恰好九个」不破），preload 里通道名字面量、由测试比对两处一致；证据：V01（`tests/shellipc.test.js` 新增用例）、G01。
- D04：preload 的 `on`：只认 `'service-state'`；只注册一个 `ipcRenderer.on`；每次 `on` 登记独立订阅，退订只删自己那条、可重复退订不抛错；别的事件名同步回空退订函数；监听函数只收到 state 一个实参；`on` 与退订都不发 IPC；证据：V01（`tests/shellpreload.test.js` 改写的两条）。
- D05：退出码：有数字码用数字码；没有数字码（信号结束、spawn 失败、外壳自己杀的握手失败进程）记 `-1`；1/2 的既有语义不与本片混用；「是不是外壳自己结束的」标志只留主进程（`info.byShell`），不进事件负载与 `getState().service`；证据：V01（`tests/serviceflow.test.js` 的退出码用例）、review。
- D06：用户关服务窗口 → 收服务 → 服务以 0 退出就以 0 退出应用，否则写一行 `ERROR:` 并以 1 退出；服务在 `running` 期间自己退出 → 写一行 `ERROR: 服务意外退出（退出码 N）`、关服务窗口、以 1 退出（A 片过渡行为）；证据：G01、review。
- D07：`starting` 期间用户关外壳页 → 先中止子进程（子进程真的退出，不留僵尸）再以 0 退出；证据：V01（`tests/serviceflow.test.js` 的 abort 用例，轮询子进程状态）、G01、review。
- D08：控制令牌只在主进程：只进 `createHost` 的闭包，不出现在事件负载、`getState()`、任何信封与任何日志；证据：V01（`tests/serviceflow.test.js` 断言状态与事件里没有令牌）、review。
- D09：既有门禁的守法：`require('electron')` 只在三个文件；`ipcMain.on` 与 `ipcRenderer.send` 全禁；main.js 与 src/** 的词面禁令；`new BrowserWindow` 恰好一处；T025/T026/T030 钉住的 main.js 接线标记一个不丢；`launchMode(` 早于 `runShell(` 且 `runShell` 的五个实参不变；`package.json` 的 `scripts.test` 列出每一个 `tests/*.test.js`（含新增的 `tests/serviceflow.test.js`）；证据：G01、R01。
- D10：包内测试与行为同步：`tests/shellapi.test.js` 只改那一条占位用例、`tests/shellpreload.test.js` 只改那两条、`tests/shellipc.test.js` 新增一条、新增 `tests/serviceflow.test.js` 与夹具；既有测试一条没删没改名没弱化；证据：V01、R01、review。
- D11：README 写清外壳页的新行为与新的手工冒烟条目（注明页面上点「启动」要等 T032 落地），既有 needle 一字不删；证据：R01（既有门禁的 README 断言）、review。
- D12：所有修改都在允许集合内；没有新增或升级依赖；没有下载 Electron 本体、没有联网；证据：scope。
- D13：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `src/service.js` 的 `spawn` 选项形状变了、`themisShell.ts` 的 `ServiceState` 变了、既有门禁在基线上就不绿）。
- 必须修改允许范围之外的文件才能继续（例如要改 `src/window.js`、`src/service.js` 的签名或 `desktop/web/**` 才能成立）。
- 现有门禁（尤其 T025/T026/T030）在本基线上就不绿，且原因不在本片范围内。
- 起子进程的用例在 Windows 上做不出确定行为（子进程被 job 对象带走、杀不掉）——停下报告，不许 mock `child_process`。
- 需要新增或升级依赖、联网下载 Electron 本体、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如 B 片的四项被要求在本片实现）。
- 达到单轮时限。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400
- cost_budget: tracking-only（站主一侧的花费上限 12 美元，由站主把关）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：复核基线与读源码 20 分钟、实现 `src/serviceflow.js` 与 shellapi 40 分钟、preload 与 main.js 接线 45 分钟、补测与 README 35 分钟、跑检查与写报告 40 分钟；总计约 180 分钟，单轮上限 3600 秒（回归门禁 R01 一条就要十几分钟），返工留两次。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D13，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写明：`interpretations`（合同没写死、按最合理解读做的地方，例如 `startService` 的 reason 词表与 `no-service` 的兜底、README 的具体措辞）与 `contract_conflicts`（合同内部矛盾，没有就写空数组）。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不改门禁测试文件（`tests/test_gate_t033_*.py` 由门禁端写）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不跑真 Electron、不下载 Electron 本体、不联网装依赖；不碰主工作区与本任务书以外的路径。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261113T010802163338Z-owner-b14fb8：

> 三件事的决定，加 5 条事实的核实结果。事实的做法与数字在 `.agent/mailbox/owner-notes/t033-facts-01.md`（合同端、门禁端开工前读它）。
>
> 决定：
> 1. 拆。本片只做 A（起服务、service-state 事件、getState、preload 的 on、开服务窗口并关外壳页、用户关窗结束服务、starting 期间中止）。A 的过渡行为可以接受：服务意外退出时照带参数那条路以 1 退出。B（意外退出回服务状态页、restartService、第二次起服务的接线）由站主在 A 落地后另登记成新的主任务。
> 2. 三条探针用例站主已处理，并一起退役了 T028 的 `test_transitional_s04`；基线已挪到这次提交（见 task rebase 的信）。T028 那条“占位”整条退役；T030 的“on 不发 IPC、不注册监听”留下“同步返回函数、on 与退订都不发 invoke”；“自包含”只去掉 ipcRenderer.on 的两处，send 禁令照留。T030 探针的假 ipcRenderer 现在有 `removeListener` 与 `off`。事件通道照规划单设，不进 SHELL_CHANNELS。
> 3. 不等 T032。README 的手工冒烟现在就写，写明“页面上的点击要等 T032 落地”；站主落地后用真 Electron 跑能跑的部分。
>
> 事实（真 electron 44.9.0 与本机 Node v24.19.0 实测）：
> 1. 成立。不订阅 window-all-closed 时，关掉最后一个窗口应用自己退出；先开新窗口再关旧窗口，应用还在。
> 2. 成立。同一通道第二次 `ipcMain.handle` 抛 `Attempted to register a second handler for '…'`；先 `removeHandler` 就能再注册。
> 3. 规则成立：preload 只把 state 交给监听函数，合同加一条用例断言监听函数只收到一个实参。这个版本上事件对象过桥后 `sender` 没有 invoke 与 send，没复现出能发 IPC，但内部字段过去了。另量到：`webContents.send` 发的对象页面原样收到；退订之后再发收不到。
> 4. 成立（核实 T030、T032 时量过）。
> 5. 父进程 `child.kill()`：exit 是 code=null、signal="SIGTERM"；外部 `taskkill /F`（任务管理器同一条路）：code=1、signal=null；子进程自己 `process.exit(3)`：code=3。被外部杀掉的 1 与服务自己以 1 退出分不出来：状态里另带“是不是外壳自己结束的”标志，不靠退出码猜原因。
