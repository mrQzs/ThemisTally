# TASK: t035-desktop-shell-service-b

<!-- 桌面端外壳第 6 片：服务意外退出回服务状态页、restartService、第二次起服务的接线（D3 之九 / T033 的 B 片）。
     基线：bdee39f8be895b752b0017d18ab014899c10ba62（站主已退役 T033 的 S05、P05 两条过渡断言并把基线挪过来）。
     只改 desktop/shell。 -->

## Identity
- plan_version: 5
- repository: ThemisTally
- base_sha: b5cb4c5d54193974250a693d56100e356df0dee7
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在同一个 Electron 外壳进程里，服务意外退出（不是外壳自己停的）时回到服务状态页 `themis-shell://app/index.html#/service-status` 并显示退出码；`restartService()` 能按当前设置重启刚才那个仓库；同一个外壳进程里第二次起服务能成功（宿主 IPC 只注册一次、调用转给当前 host、外壳 IPC 与选择框读当前外壳窗口、每个服务实例用新分区）；README 写清这些行为与手工冒烟。

## Non-goals
- 不做托盘、系统通知、单实例、多仓库切换、`openSettings`、在外壳页里改设置。
- 不改 `desktop/web/**`（前端只读：服务状态页已经会订阅 `service-state`、点「重启」调 `restartService()`、收到 running 才跳回总览）。
- 不改 `desktop/shell/preload.js`、`desktop/shell/shell-preload.js`、`desktop/shell/src/ipc.js`、`desktop/shell/src/host.js`、`desktop/shell/src/core.js`、`desktop/shell/src/service.js`、`desktop/shell/src/shellipc.js`、`desktop/shell/src/window.js` 的现有行为。
- 不改带参数那条服务分支（`main.js` 里 `runShell({...})` 那一路）的行为；本片只动外壳页分支（`runShellPage()`）。
- 不改 `desktop/shell/tests/fixtures/**`（直接用 T033 的 `fake-service.js` 与 `fake-service-exit.js`）。
- 不改门禁测试（仓库根的 `tests/` 目录），不为通过而 xfail/skip 任何用例。

## Repository facts
- 入口：`desktop/shell/main.js`（Electron 主进程，两个分支）。
  - 外壳页分支 `runShellPage()`：`main.js:41`。起手检查外壳页产物（构建产物根下的 `index.html`，构建命令见 README；缺失就写一行 ERROR 并以 1 退出，`:43-47`），建外壳窗口（`:48-60`，协议 handler 在 `:50` 挂在 `session.fromPartition(partition).protocol` 上），建 `createServiceFlow`（`:70`），`onRunning` 里 `createHost`（`:83`）→ `registerHostIpc(ipcMain, host, senderAllowed)`（`:120`）→ 开服务窗口（`:123-137`）→ 关外壳窗口（`:139`）；`flow.subscribe`（`:155`）发 `SERVICE_STATE_CHANNEL`（`:156`）并处理意外退出（`:157-163`，当前是 A 片过渡写法：写一行 ERROR、关服务窗口、`app.exit(1)`）；`createShellApi`（`:167-195`，注入 `service:` 与 `assets:`）；`registerShellIpc(ipcMain, api, (event) => shellSenderAllowed(event, win.webContents))`（`:196`）；起步加载 `SHELL_START_URL`（`:197`）；用户关外壳页的收尾（`:199-205`）。
  - 服务分支：`main.js:207-293`，`runShell({argv, io, openWindow, onServiceReady, env})`（`:280`）与 `app.exit(code)`（`:292`）——本片一字不改。
- 纯模块与既有约定：
  - `desktop/shell/src/serviceflow.js`：`createServiceFlow({spawn, env, timeoutMs, now, onRunning})` → `{start, stop, abort, state, subscribe}`。状态机 idle → starting → running → exited。关键行：`child`（`:54`）、`stopping`（`:56`）、`aborting`（`:57`）都是**控制器级**变量；`moveTo` 的终态判定 `if (current.kind === "exited") return;`（`:62`）；忙判定 `if (current.kind !== "idle") return { ok: false, reason: "busy" };`（`:71`）；子进程 exit 监听推 exited（`:86`）；握手失败推 exited（`:101`）；`stop()` 置 `stopping = true`（`:129`）并补发 exited（`:133`）；`abort()` 置 `aborting = true`（`:145`）并补发 exited（`:160`）。
  - `desktop/shell/src/shellapi.js`：`createShellApi({store, chooseDirectory, chooseFile, confirmExternal, openExternal, appVersion, probe, service, assets})` → 十个成员 `{getState, pickRepo, pickPython, pickKit, pickTranscriptDir, saveSettings, startService, restartService, openExternal, on}`（`:296-307`）。`serviceState()`（`:128`）读控制器的当前状态；`startService(repoId)`（`:253`）按 id 查设置 → Python → kit（按目标仓库算）→ `serviceCommand` → `service.start(...)`；`restartService`（`:282-284`）现在是占位 `{ok:false, reason:"not-implemented"}`。
  - `desktop/shell/src/ipc.js`：`registerHostIpc(ipcMain, host, senderAllowed)`，五条通道（reauth / open-secret-window / open-external / reveal / notify），来源检查不过回 `{ok:false, reason:"forbidden"}`，host 方法抛错回 `internal`。本片不改它。
  - `desktop/shell/src/host.js`：`createHost({origin, control, repo, loadMain, createSecretWindow, confirmExternal, openExternal, showItem, showNotification})` → 五个方法 `{reauth, openSecretWindow, openExternal, reveal, notify}`。每次调用都是新闭包。
  - `desktop/shell/src/shellprotocol.js`：`SHELL_SCHEME`/`SHELL_HOST`/`SHELL_START_URL`（`:8`）、`isShellPageUrl`（`:29`，认任何 `themis-shell://app/` 地址，带 hash 也认）、`resolveShellAsset`；导出在 `:131-136`。
  - `desktop/shell/src/shellipc.js`：`SHELL_CHANNELS` 冻结九个、`SERVICE_STATE_CHANNEL = "themis-shell:service-state"`、`registerShellIpc(ipcMain, api, senderAllowed)`、`shellSenderAllowed(event, contents)`。
  - `desktop/shell/src/window.js`：`partitionName()`（randomUUID）、`webPreferences`、`mainWebPreferences`、`trackWindow(win, load)`（返回 `{closed, close}`）、`isServiceUrl`。
- 调用关系：`shell-preload.js`（页面侧）→ IPC → `main.js` → `shellapi.js`（外壳页十个成员）/ `serviceflow.js`（状态机）→ `service.js`（起停子进程）→ `host.js` + `ipc.js`（宿主接口）。
- 工具链与锁文件：`desktop/shell/package.json`（private、commonjs、devDependencies 只有 `electron: 44.9.0`、`scripts.test` 是 `node --test --test-reporter=tap` 并逐个列出 `tests/*.test.js`）、`desktop/shell/package-lock.json`（electron 44.9.0，锁文件与依赖一字不动）。门禁机：Node 24 + Python/pytest；仓库根的 `tests/` 目录里是各片的门禁。
- 基线检查（合同端本回合没有 shell 权限，只读探查，**没有执行** `npm test` 与 `pytest`）：基线是 `bdee39f8be895b752b0017d18ab014899c10ba62`，站主已退役 T033 门禁里的 `test_transitional_s05_unexpected_exit_error_line` 与 `test_transitional_p05_probe_restart_service`（该门禁文件头 `:42`、`:61` 有退役说明，其余 9 条照过），这**两条退役不在本片范围，也不要为它们保留兼容写法**。Validation commands 里 G01 指向的那份门禁文件由门禁端稍后写、在本基线上尚不存在（所以 G01 在基线上跑不起来，属预期）；R01 在基线上的预期是全过。

## Scope
- allowed_modified_files:
  - desktop/shell/src/serviceflow.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/shellprotocol.js
  - desktop/shell/main.js
  - desktop/shell/tests/serviceflow.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/shellprotocol.test.js
  - desktop/shell/package.json
  - desktop/shell/README.md
  - desktop/shell/src/hostrelay.js
  - desktop/shell/tests/hostrelay.test.js
- allowed_new_files:
  - desktop/shell/src/hostrelay.js
  - desktop/shell/tests/hostrelay.test.js
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/**
  - tests/test_gate_t035_*.py
  - desktop/web/**
  - ts/**
  - scripts/**
  - desktop/shell/preload.js
  - desktop/shell/shell-preload.js
  - desktop/shell/src/ipc.js
  - desktop/shell/src/host.js
  - desktop/shell/src/core.js
  - desktop/shell/src/service.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/settings.js
  - desktop/shell/src/detect.js
  - desktop/shell/src/window.js
  - desktop/shell/src/launch.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/control.js
  - desktop/shell/src/args.js
  - desktop/shell/src/handshake.js
  - desktop/shell/src/python.js
  - desktop/shell/package-lock.json
  - desktop/shell/tests/fixtures/**
- dependency_changes: forbidden（只改 `desktop/shell/package.json` 的 `scripts.test`；依赖与锁文件一字不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、serviceflow 按 run 记状态（`desktop/shell/src/serviceflow.js`）
- 对外接口与返回形状一字不变：`start` / `stop` / `abort` / `state` / `subscribe`；`start` 的信封仍是 `{ok:true, value:null}` 或 `{ok:false, reason:"busy"|"start-failed"|"handshake-failed"}`。
- **准入**：`state().kind` 是 `starting` 或 `running` → `{ok:false, reason:"busy"}`，不起进程、不开新 run。`idle` 或 `exited` → 开一个新 run（run 计数自增）。
- **新 run 重置**：`stopping`、`aborting`、`child`、本 run 的「已退出」标记一律重置；`repo` 记为本次 `start` 的 repo。控制令牌仍然只经 `onRunning` 的实参出去，不进状态、不进事件负载、不进信封。
- **同一 run 内 `exited` 是终态**：已经 exited 的 run 不再改状态（保住 T033「重复的 exited 不覆盖」的语义）。
- **旧 run 的回调一律丢弃**：子进程 exit 监听、`stop()` 的补发、`abort()` 的补发，只有在它所属的 run 仍是当前 run 时才改状态；否则不改状态、不发事件。
- **`byShell` 按 run 算**：exited 事件的 `info.byShell` = **该 run** 的 `stopping || aborting`；上一个 run 的标志不继承到下一个 run。
- **`stop()` / `abort()` 只作用于当前 run 的 child**：当前 run 没有 child 时，`stop()` 回 `{exited:false, code:null, signal:null}`，`abort()` 直接返回。
- 状态机形状不变：idle → starting → running → exited；exited →（再 start）→ starting → running。

### 二、`restartService()`（`desktop/shell/src/shellapi.js`）
按 `serviceState()` 的当前状态决定，**不新增控制器方法**（门禁 P02 的假控制器只有 `start/stop/abort/state/subscribe`，照样兼容）：

| 情形 | 返回 | 是否起进程 |
|---|---|---|
| 没注入控制器（`service === null`） | `{ok:false, reason:"no-previous"}` | 否 |
| `state.kind` 是 `starting` 或 `running` | `{ok:true, value:null}` | 否（幂等，什么也不做） |
| `state.kind` 是 `exited` | 走 `startService(state.repo)`：同一条路、**按当前设置**重新拼命令；信封原样回传 | 是（由 startService 决定） |
| 其余（`idle`） | `{ok:false, reason:"no-previous"}` | 否 |

- `exited` 那条路上 `startService` 的失败 reason 与 `startService` 完全一致：`unknown-repo`（仓库已从设置里移除）、`python-missing`、`kit-missing`、`no-service`，以及控制器原样回传的 `handshake-failed`、`start-failed`。
- 重启的是 **exited 状态里那个 repo id**，不是 `currentRepo`。
- `startService` 本身不改：幂等与 busy 的判定、`serviceCommand` 的形状、失败时的 reason 一律照旧。

### 三、宿主 relay（新增 `desktop/shell/src/hostrelay.js`，纯模块、不 require electron）
- `createHostRelay()` 返回 `{ host, senderAllowed, use(host, senderAllowed), clear() }`：
  - `host`：`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify` 五个方法，把实参**原样**转给当前 host；没有当前 host 时回 `{ok:false, reason:"forbidden"}`（不抛错）。
  - `senderAllowed(event)`：没有当前 host → `false`；有 → 当前那份来源检查的结果（检查抛错按 `false`）。
  - `use(host, senderAllowed)`：把当前 host 与来源检查换成新的（替换，不是叠加）。
  - `clear()`：丢掉当前 host 与来源检查（回到「没有当前 host」）。
- `registerHostIpc` 由 `main.js` 调用**一次**（`registerHostIpc(ipcMain, relay.host, relay.senderAllowed)`），调用次数在整个外壳分支里恒为 1；第二次起服务不再重复注册。

### 四、外壳分支接线（`desktop/shell/main.js`，只动 `runShellPage()`）
- **宿主 IPC**：外壳分支开头注册一次（上面的写法）。每次服务起来（`onRunning` 里）`createHost(...)` 之后调 `relay.use(host, 服务窗口的来源检查)`；服务窗口被外壳关掉时 `relay.clear()`。
- **外壳窗口统一走一个 helper**（名字自取，例如 `openShellWindow(url)`）：每次取**新分区**（`partitionName()`）→ 在该分区 session 的 `protocol` 上**注册一次** `themis-shell` handler → `guardedWindow` + `shell-preload.js` → `trackWindow` 加载给定地址。
  - 协议 handler 的写法固定为：`const userSession = session.fromPartition(partition);` 紧接 `userSession.protocol.handle("themis-shell", (request) => {…})`，**同一个 session 绝不注册第二次**（第二次注册会抛错）。
  - 起步地址用 `SHELL_START_URL`，意外退出换页用 `SHELL_STATUS_URL`；两者都走这一个 helper。
- **当前外壳窗口**用一个变量记（例如 `shellWin`）：`registerShellIpc` 仍**只调一次**，来源检查读当前外壳窗口（`shellWin` 非空 → `!shellWin.isDestroyed()` → `shellSenderAllowed(event, shellWin.webContents)`）。
- **选择框与外部链接确认框**（`chooseDirectory`、`chooseFile`、`confirmExternal`）挂在当前外壳窗口上：当前外壳窗口存在且未销毁时作为父窗口，否则不带父窗口调用。
- **服务状态事件**只发给当前外壳窗口；窗口为空或已销毁就跳过。
- **意外退出**（`state.kind === "exited"` 且 `!info.byShell`）三条分支：
  1. 当前已经有外壳窗口开着（`shellWin` 非空且未销毁）→ **不另开窗口**：把服务窗口标成「服务那边已经收尾」、关掉服务窗口；外壳页自己经事件显示错误。
  2. 没有外壳窗口 → 用 helper 开一个新的外壳窗口，地址 `SHELL_STATUS_URL`；**开好之后**（`trackWindow` 兑现）再：把服务窗口标成外壳关、`relay.clear()`、关掉服务窗口。窗口次序永远是先建新窗口再关旧窗口。
  3. 新窗口开不出来（`trackWindow` 抛错）→ 往 stderr 写一行 `ERROR: 服务意外退出（退出码 N）`、关掉服务窗口、`app.exit(1)`。
- **用户关外壳窗口**（不是外壳自己关的）：`starting` → `flow.abort()` 再 `app.exit(0)`；`running` → `flow.stop()` 再 `app.exit(0)`；`idle` 或 `exited` → 直接 `app.exit(0)`。外壳自己关的窗口（起服务成功后的那次、意外退出换页后的那次）不做这些收尾。
- **用户关服务窗口**：`flow.stop()`；服务以 0 退出 → `app.exit(0)`；否则往 stderr 写一行 `ERROR: 服务没有以 0 正常退出` 并 `app.exit(1)`。
- 服务分支（带参数那条路）一字不改。

### 五、服务状态页地址（`desktop/shell/src/shellprotocol.js`）
- 新增并导出常量 `SHELL_STATUS_URL = "themis-shell://app/index.html#/service-status"`；`isShellPageUrl(SHELL_STATUS_URL)` 为真；`SHELL_SCHEME`、`SHELL_HOST`、`SHELL_START_URL`、`CSP`、`MIME`、`isShellPageUrl`、`resolveShellAsset` 一律不变。

### 六、兼容性与不变的东西
- `src/shellapi.js` 的 require 仍是 `./settings`、`./detect`、`./hostcheck`（另加原有的 `./service.js`）。
- `src/ipc.js`、`src/host.js`、`preload.js`、`shell-preload.js`、`src/core.js`、`src/service.js` 的现有行为与导出不变。
- `window.themisShell` 的十个成员与名字不变；`getState().service` 的形状不变（`{kind:"idle"}` / `{kind:"starting",repo}` / `{kind:"running",repo,pid,startedAt}` / `{kind:"exited",repo,exitCode,at}`），`info.byShell` 不外传。
- `SHELL_CHANNELS` 仍恰好九个、顺序不变；`SERVICE_STATE_CHANNEL` 不进白名单。
- 门禁要守住的既有形状（一条都不许丢）：`main.js` 里 `new BrowserWindow` **恰好一处**；每处 `.protocol.handle(` 前 160 字以内要有 `fromPartition`；不许裸的模块级 `protocol.handle(`；`registerSchemesAsPrivileged` 恰好一次且在 `app.whenReady` 之前、privileges 只有 `standard`/`secure`；第一处 `launchMode(` 早于第一处 `runShell(`，`runShell(` 的实参仍带 `argv`/`io`/`openWindow`/`onServiceReady`/`env` 五个键；`registerHostIpc(`、`createHost(`、`registerShellIpc(`、`isShellPageUrl`、`resolveShellAsset(`、`new Response(`、`shell-preload.js`、`SHELL_START_URL`、`app.exit(1)`、`ERROR`、`byShell`、`.abort()`、`.stop()`、`服务没有以 0 正常退出`、`webContents.send(`、`isDestroyed()`、`createShellApi` 的注入项里有 `service:` 与 `assets:`、`require ./src/serviceflow` 并调用 `createServiceFlow(` —— 一个都不许丢。
  - **新代码与注释里不许出现 `runShell(` 这个写法**（`runShellPage(` 不算），也不许在 `launchMode(` 之前写它。
- 词面禁令：`desktop/shell` 下任何 `.js`（含测试、注释、断言文案）不许出现 `ipcMain.on`、`ipcRenderer.send`；`src/**` 与 `main.js` 不许出现 `dialog`、`Notification`、`showItemInFolder`、`shell.openExternal`、`fetch(`、`net.request`、`persist:`、`shell: true`、写文件函数（`writeFile`/`appendFile`/`mkdir`/`rm`/`unlink`/`rename` 等）、`autoUpdater`、`crashReporter`。测试里假 ipcMain 的变量名用 `im`；测试文件里不许出现 `require('electron')` 这个字面串。

### 七、README（`desktop/shell/README.md`，只增改）
- 「退出码」表（`:39-47`）：退出码 **1** 的含义里去掉「服务意外退出」，改成「服务状态页开不出来」这一条兜底；退出码 0 与 2 的行照旧。
- 「设置与校验」一节（`:136` 附近）与「外壳页」一节（`:173` 附近）：`restartService` 不再是占位——写清真行为与 reason 词表（`no-previous`；`unknown-repo`/`python-missing`/`kit-missing` 与 `startService` 同；starting/running 时幂等回 ok）。
- 「外壳页」一节（`:180` 附近）：「服务在 `running` 期间自己退出」从「写一行 ERROR、以 1 退出」改成「回到服务状态页并显示退出码；服务状态页开不出来才写一行 ERROR 并以 1 退出」。
- 「手工冒烟」（`:63-70`）：第 4 条改写为——不带参数 `npm start` → 首次启动页选好仓库/Python/kit → 点「启动」（**T032 已落地，点得动**；`T032` 这个词要留着）→ 服务起来、主窗口打开 → 在任务管理器里结束服务进程 → 回到服务状态页、显示退出码 → 点「重启服务」→ 主窗口重新出现 → 关掉主窗口 → 服务随之结束、外壳以 0 退出。写明要先 `npm ci`、`npm --prefix ../web run build`、`node node_modules/electron/install.js`。
- 一个 needle 都不许删（各片门禁继续钉住下列字样）：`npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、`退出码`、`install.js`、`node_modules/electron`、冒烟、`10 秒`、`30 秒`、`themisHost`、`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`、`forbidden`、`internal`、`rate-limited`、`request-failed`、`bad-response`、`load-failed`、`bad-args`、`busy`、`bad-url`、`cancelled`、`open-failed`、`bad-path`、`bad-kind`、`attempt-finished`、`awaiting-review`、`attempt 已结束`、`有 attempt 等待验收`、`.agent`、`Ctrl+V`、`真 Electron`、`设置与校验`、`settings.json`、`userData`、`副本`、`.git`、`3.10`、`pi_dispatch.py`、`凭据`、`控制令牌`、`## 外壳页`、`themis-shell://app/index.html#/first-run`、`desktop/web/dist`、`npm --prefix ../web run build`、`themisShell`、`桩数据`、`standard`、`secure`、`404`、`themis-shell:get-state`、`外壳页在本片就位`、`on('service-state'`、`T032`。

## Steps
1. 读 `desktop/shell/main.js`、`src/serviceflow.js`、`src/shellapi.js`、`src/shellprotocol.js`、`src/ipc.js`、`src/host.js`、`src/window.js`、`tests/serviceflow.test.js`、`tests/shellapi.test.js`、`tests/shellprotocol.test.js`、`tests/fixtures/fake-service.js`、`tests/fixtures/fake-service-exit.js`，确认签名与上面「Repository facts」一致；不一致就停止并报告。
2. `src/serviceflow.js` 改成按 run 记状态（Behavior contract 一）。验收意图（真起子进程，不 mock child_process）：
   - run1 用 `fake-service-exit`（握手后 60ms 以码 3 退出）→ `starting` → `running` → `exited`（码 3、`byShell=false`）；随后 run2 用 `fake-service`（`FAKE_SERVICE_MODE=ok`）→ `starting` → `running`（证明 exited 之后可再 start，状态不被旧 run 卡住）。
   - run1 走 `stop()`（`byShell=true`）之后，run2 意外退出 → `byShell` 必须是 **false**（标志不继承）。
   - run1 握手超时（`FAKE_SERVICE_MODE=silent` + 短 `timeoutMs`）之后立刻起 run2：run1 的子进程随后退出**不许**把 run2 的状态改成 `exited`（旧 run 回调丢弃）。
   - `starting` / `running` 时再 `start` 仍回 `{ok:false, reason:"busy"}` 且不起第二个进程（把 `tests/serviceflow.test.js:254` 的标题从「不是 idle 时再 start → busy」改成「starting/running 时再 start → busy」，断言本身照留）。
   - 子进程真的退出用轮询 `exitCode`/`signalCode`（照现有 `waitFor` 写法），不要固定等几百毫秒；令牌不进任何状态。
3. `src/shellapi.js` 实现 `restartService`（Behavior contract 二）。验收意图（照 `tests/shellapi.test.js` 现有写法，假控制器 + 假 probe）：
   - `idle` → `{ok:false, reason:"no-previous"}` 且不起进程；没注入控制器 → 同样 `no-previous`。
   - `starting` / `running` → `{ok:true, value:null}` 且不起进程。
   - `exited` 且仓库已从设置里移除 → `unknown-repo`；Python 不可用 → `python-missing`；kit 不可用 → `kit-missing`；都不起进程。
   - `exited` 且条件齐 → 控制器收到一次 `start`，命令与 `serviceCommand` 按**当前**设置算的一致（先改 `kitPath` 再重启，命令跟着变）。
   - 把 `tests/shellapi.test.js:585` 的用例标题改成真行为（例如「startService 按仓库 id 真起服务；restartService 按当前设置重启；on 真订阅」），把 `:750-754` 那段占位断言换成上面的真行为断言；这个大用例的其余断言（`:788-802` 的十个成员等）照留。
4. 新增 `desktop/shell/src/hostrelay.js`（纯模块，不 require electron）与 `desktop/shell/tests/hostrelay.test.js`。验收意图：
   - `use(host1, allow1)` 之后五个方法都进 host1；`use(host2, allow2)` 之后只进 host2；`clear()` 之后回 `{ok:false, reason:"forbidden"}`。
   - 没有当前 host 时 `senderAllowed(event)` 为 `false`。
   - **重入用例**：真 `createServiceFlow`，`onRunning` 里 `relay.use(新的假 host)`；先用 `fake-service-exit` 起服务、等它意外退出，再用 `fake-service`（ok）起第二次：`registerHostIpc` 的注册次数**仍是 5**、第二次 `start` 回 `{ok:true, value:null}`、调用进第二个 host；最后 `stop()` 收尾。假 ipcMain 的变量名用 `im`，`handle` 遇到重复通道就抛错（照 Electron 的行为）。
5. `src/shellprotocol.js` 加 `SHELL_STATUS_URL` 并导出；在 `tests/shellprotocol.test.js` 补一条：值逐字等于 `themis-shell://app/index.html#/service-status`，且 `isShellPageUrl` 对它为真。
6. 改 `desktop/shell/main.js` 的外壳分支（Behavior contract 四）：宿主 IPC 只注册一次（经 relay）、外壳窗口统一 helper（每次新分区 + 该 session 上注册一次协议 handler）、`shellWin` 记当前外壳窗口、外壳 IPC 与选择框读它、意外退出三条分支、用户关窗的收尾。既有标记一个都不许丢（见 Behavior contract 六）。
7. 改 `desktop/shell/README.md`（Behavior contract 七）。
8. 改 `desktop/shell/package.json` 的 `scripts.test`：把新增的 `tests/hostrelay.test.js` 加进去（`--test-reporter=tap` 仍写在文件清单之前，既有 21 个文件一条不删、顺序照旧，依赖与锁文件不动）。
9. 跑 Validation commands 中与改动相关的检查（V01、G01、R01），记录命令与结果；写执行报告。遇到合同未定义的行为，停止并报告。

## Validation commands

- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass \d+`、`# fail 0`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t035_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：serviceflow 按 run 记状态——exited 之后能再 start（starting → running）；旧 run 的 exit/stop/abort 回调只在仍是当前 run 时改状态；`byShell` 按 run 算（上一 run 被 stop 过，下一 run 意外退出仍是 false）；starting/running 时再 start 仍回 busy 且不起第二个进程。证据：V01、G01；目的：真把「第二次起服务」的状态机前提做实，而不是靠 main.js 绕。
- D02：`restartService()` 按 Behavior contract 二工作——idle 或没控制器 → `no-previous` 且不起进程；starting/running → `{ok:true, value:null}` 且不起进程；exited → 走 `startService(state.repo)` 同一条路、按当前设置拼命令，失败 reason 与 startService 一致（`unknown-repo`/`python-missing`/`kit-missing`/`no-service`/控制器原样回传）。证据：V01、G01；目的：让页面上「重启服务」真的能按当前设置重启，而不是回一个占位 reason。
- D03：宿主 IPC 只注册一次、调用转给当前 host——`registerHostIpc(ipcMain, relay.host, relay.senderAllowed)` 在整个外壳分支只调一次；没有当前 host 时 `senderAllowed` 为 false、调用回 `forbidden`；重入用例里注册次数仍是 5、第二次 start 成功、调用进第二个 host。证据：V01、G01；目的：Electron 44.9.0 里同一通道第二次 `ipcMain.handle` 会抛错，第二次起服务因此失败——这是本片风险最高的一处，必须有独立证据。
- D04：外壳 IPC 与选择框读当前外壳窗口——`registerShellIpc` 只调一次，来源检查读当前 `shellWin`（非空、未销毁、`shellSenderAllowed`）；选择框与外部链接确认框挂在当前外壳窗口上。证据：G01、review；目的：重开外壳窗口后，旧窗口的 webContents 不再能调外壳接口。
- D05：重开的外壳窗口每次取新分区，并在该 session 的 `protocol` 上注册一次 `themis-shell` handler；同一个 session 绝不注册第二次；`main.js` 里 `.protocol.handle(` 只有一个调用点，且它前 160 字以内有 `fromPartition`。证据：G01、review；目的：站主实测在同一个 session 上第二次注册会抛错（`Failed to register protocol: themis-shell`），而新分区新 session 连开三次都成功。
- D06：意外退出（`exited` 且 `!byShell`）先开服务状态页、开好之后才关服务窗口；已经有外壳窗口开着时不另开窗口；服务状态页开不出来时才写一行 `ERROR: 服务意外退出（退出码 N）` 并以 1 退出；用户关窗的收尾（`abort()`/`stop()`/退出码）保持不变。证据：G01、review；目的：Electron 在最后一个窗口关掉时会退出应用，窗口次序错了就会带着服务一起退出；真窗口行为由 README 冒烟覆盖。
- D07：README 写清新的退出码表、`restartService` 的真行为与 reason 词表、意外退出回服务状态页，以及手工冒烟（选仓库 → 启动 → 主窗口 → 结束服务进程 → 回服务状态页显示退出码 → 重启 → 关主窗口 → 以 0 退出），并写明要先构建前端、`T032` 已落地；各片门禁钉住的 needle 一个不删（清单见 Behavior contract 第七节）。证据：G01、R01、review；目的：真窗口行为只能靠人工冒烟，README 是唯一的验收凭据；needle 少一个就会让别的片门禁变红。
- D08：所有修改都在允许集合内（`allowed_modified_files` / `allowed_new_files`），没有碰仓库根的 `tests/`、`desktop/web/**`、`preload.js`、`shell-preload.js`、`src/ipc.js`、`src/host.js`、夹具与锁文件。证据：scope。
- D09：没有删除、跳过或弱化既有测试——`desktop/shell/tests/` 下既有 21 个测试文件一条不删，既有断言照留（只改 `tests/shellapi.test.js:585` 的标题与 `:750-754` 的占位断言、`tests/serviceflow.test.js:254` 的标题），`package.json` 的 `scripts.test` 仍列出每一个 `tests/*.test.js`；不许 xfail/skip。证据：V01、scope、review。

## Stop conditions
- 基线、接口或必要文件与「Repository facts」不符（例如 `serviceflow.js` 的导出形状、`registerHostIpc` 的签名、`isShellPageUrl` 的判定与门禁不一致）。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- G01 指向的门禁文件在基线上还不存在、导致 G01 跑不起来时：照常跑 V01 与 R01，并在执行报告里写明 G01 未跑（不要自己写门禁文件）。
- 达到单轮时限。

## Budget
- max_attempts_total: 6（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 2400
- max_wall_seconds_total: 12027
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读代码与设计 15 分钟、实现与补测 30 分钟、跑 V01/G01/R01 与自检 10 分钟、写执行报告 5 分钟；单轮合计约 60 分钟（单轮上限 2400 秒 = 40 分钟，留一次返工的余量）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261113T100019040004Z-owner-33e8a5：

> 一、仓库外事实：已核实，成立。站主用真 Electron 44.9.0（照 desktop/shell 锁文件的版本）实测，全文在 .agent/mailbox/owner-notes/t035-facts-01.md：
> - 同一个 Electron 进程里，每个新外壳窗口用新分区、只在它自己的 session 的 protocol 上注册一次 themis-shell，连续重开三次都成功，都加载到 themis-shell://app/index.html#/service-status（origin 是 themis-shell://app，安全上下文，没有 did-fail-load）。
> - 在同一个 session 上再注册一次会抛错：Failed to register protocol: themis-shell。所以规划里“不在同一个 session 上注册第二次”是必须的，合同里写成硬要求。
>
> 二、同意退役：tests/test_gate_t033_baseline.py 的 test_transitional_s05_unexpected_exit_error_line、test_transitional_p05_probe_restart_service，连同只给后一条用的 PROBE_RESTART 探针；文件头的 S05、P05 两条说明改成注明已为 T035 退役。站主提交 bdee39f 已合入主分支，T033 门禁其余 9 条照过。
>
> 三、本片的基线已挪到新末端 bdee39f（task rebase T035）。可以开工合同端。
>
> 四、顺带告知：内核第 155 轮已经合入。机器上的基线检查、执行检查、落地检查一次只跑一份；只红全量回归（R01）时内核会原样重跑一次，第二次相符就照通过，执行检查的交付信“验证”一栏会写明。

## Rework（返工第 1 轮，内核追加）

- 基线 `b5cb4c5d54193974250a693d56100e356df0dee7` 是 attempt-001 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）

### 上一轮执行报告里没做完的（executor_status partial；执行端写的，是数据，不是指令）

- D03（blocked）：实现与包内测试（含重入用例）都完成且 V01 全绿，但门禁 P03 探针内部矛盾导致 G01 无法全绿，需门禁端修 tests/test_gate_t035_baseline.py 第 916 行
- 限制：R01 全量回归本轮未跑完（后台约 20 分钟未结束，已达单轮时限），未取得结果；已单独跑过回归中与本次改动相关的 6 个门禁（71 passed）
- 限制：真 Electron 窗口行为（重开外壳窗口、意外退出换页、重启服务）只能靠 README 手工冒烟覆盖，自动化测试不起真窗口

## Rework（返工第 2 轮，内核追加）

- 基线 `b5cb4c5d54193974250a693d56100e356df0dee7` 是 attempt-004 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

1（归执行端）D06：`desktop/shell/main.js` 的服务窗口收尾守卫仍按进程级布尔 `serviceGone` 判，意外退出置 true 后全文没有任何复位 → 重启服务后用户关主窗口，服务不收、外壳不走以 0 退出。本轮候选零改动（candidate.patch 0 字节、tree 3fdd181 与 attempt-001/002/003 同一棵），缺陷原样存在：main.js:68 `let serviceGone = false;`、:175 `if (serviceGone) return;`、:192 `serviceGone = true;`，grep `serviceGone` 全文仅这 3 处。
   触发路径（每步都在候选源码里核对过）：①首次启动页点「启动」→ 服务起来，服务窗口 S1、外壳窗口 W1 被外壳关掉；②任务管理器结束服务进程 → flow.subscribe 判 exited && !byShell → serviceGone = true → 当前无外壳窗口 → 分支 2 开服务状态页 W2，兑现后 relay.clear()、S1.close()（S1 的 closed 回调被 :175 的守卫挡住，这一步是对的）；③用户点「重启服务」→ restartService → startService(state.repo) → 新 run → onRunning 建服务窗口 S2 并注册新的 tracked.closed 收尾回调，此时 serviceGone 仍是 true；④用户关掉 S2 → 收尾回调第一句直接 return：flow.stop() 不调用、退出码判定不执行、app.exit(0) 不调用。结果：服务子进程留成孤儿（占端口），外壳靠 Electron「最后一个窗口关掉就退出」的默认行为结束，不再走「收服务 → 以 0 退出」。
   违反：行为合同四「用户关服务窗口：flow.stop()；服务以 0 退出 → app.exit(0)；否则往 stderr 写一行 ERROR: 服务没有以 0 正常退出 并 app.exit(1)」；DoD D06「用户关窗的收尾（abort()/stop()/退出码）保持不变」；README.md:70 冒烟第 4 条最后一步「关掉主窗口 → 服务随之结束、外壳以 0 退出」与 README.md:185 描述的行为。合同四的措辞是「把服务窗口标成『服务那边已经收尾』」——标的是那个窗口/那次服务实例，不是进程级布尔。
   要求：把「服务窗口已收尾」改成按窗口/run 身份计算，使重启后的服务窗口关掉时仍走 flow.stop() → app.exit(0)。不得只加 `serviceGone = false`（旧窗口 S1 迟到的 closed 回调会越过守卫停掉新 run 的服务并 app.exit(0)，比现在更糟）；稳妥做法是在收尾回调里比对当前 serviceWindow 是不是自己那一个窗口，必要时再辅以按 run 的标志。执行端必须让 D06 的自述与实现一致（本轮报 done，与实现不符）。
