# TASK: t064-desktop-repo-switch-shell

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 1cd1fbbcf85c823c1dc85b67f295c0eb3cbeaa55
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
外壳页分支做到单实例（同一 userData 只开一份，第二份在建任何窗口、起任何子进程之前以 0 退出），并在宿主接口 `window.themisHost` 上多三个函数：`listRepos()` 列出仓库（不带路径）、`switchRepo(id)` 不退出应用就切到另一个仓库、`addRepo()` 添加仓库。切换后首次启动页自动起新仓库的服务，应用不退出、过程中不出现服务状态页。

## Non-goals
- 前端一个文件都不改（T032 s09 冻结名单全在 `desktop/web/**`）：标题栏菜单、确认框、`hostRepos.ts` 留给 T062。
- 外壳 IPC 不变：`SHELL_CHANNELS` 九条、`shell-preload.js` 十一个成员、`createShellApi` 十个成员、`src/settings.js` 的 `PATCH_KEYS` 与 `SETTINGS_FILE_KEYS` 一律不动。
- 带参数起服务分支（`--repo …`）一字不改：不拿单实例锁、不注入三个新函数（那里回 `unavailable`）。
- 不同时跑几个服务；不做托盘、打包、通知；不做设置窗口里的「切换到此仓库」。
- 不新增依赖、不新增 `desktop/shell/tests/*.test.js` 文件（新增测试文件要改 `desktop/shell/package.json` 的 `scripts.test`，而 `dependency_changes` 是 forbidden）；新用例加进既有测试文件。

## Repository facts
- 基线：`9da7f2a3ce022d4619394ffa8c5edf2c00f8ec23`（T061 已合入）。下面每条行号与断言都在这个基线上核过（合同端逐份读过文件）。
- **宿主接口的个数是三套，不是规划报告说的「9 改 12」**：
  - `desktop/shell/preload.js`：`window.themisHost` 暴露 **9** 个成员（`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`、`openSettings`、`saveTheme`、`getAppearance`、`onAppearance`，preload.js:17-38），注释写「九个函数」（preload.js:7）→ 本片 **12**。
  - `desktop/shell/src/hostrelay.js`：`HOST_METHODS` **7** 项（:8）→ 本片 **10**。
  - `desktop/shell/src/ipc.js`：`HOST_CHANNELS`（:4-12）、`HOST_METHOD`（:15-23）、`HOST_ARITY`（:25-33）各 **7** 项 → 本片各 **10** 项。
  - `desktop/shell/src/host.js`：`createHost` 返回 **7** 个成员（:189-197），文件头注释「六个宿主函数的编排」（:29）已过时 → 本片 **10** 个成员。
  - `createShellApi` 返回 **10** 个成员（src/shellapi.js:308-319），本片一个不加；`shell-preload.js` 十一个成员不动；`desktop/web/src/shellpages/themisShell.ts` 的 `interface ThemisShell` 不动（T028 :1499-1502、`tests/shellapi.test.js`、`tests/shellshape.test.js` 三处钉着）。
- `desktop/shell/main.js` 现状：`runShellPage`（:52 起）；外壳分支的第一次 `createHost(`（:190，在 `flow` 的 `onRunning` 里，带 `createSettingsWindow` 注入），带参数分支的第二次 `createHost(`（无建窗注入）；两处 `ipcMain.on`（T061 放开的外观同步读取）；发 `SERVICE_STATE_CHANNEL` 的订阅回调（:265 起）；服务窗口的 `tracked.closed.then(async`（:253）。**当前文件里没有** `requestSingleInstanceLock`、`second-instance`、`flow.reset`、`settings.selectRepo`、`shellapi.listRepos/selectRepo`。
- `src/detect.js` 的 `checkRepo`（:84-101）只给三种结果：`not-git` / `no-agent` / `ok`；路径不是非空字符串也算 `not-git`。
- `src/shellapi.js` 的 `pickRepo`（:186-197）返回**外壳信封**：`{ok:true, value:{kind:"cancelled"}}` / `{ok:true, value:{kind:"rejected", problem, path}}` / `{ok:true, value:{kind:"saved", path, id, state}}`，写盘失败时是 `{ok:false, reason:"write-failed"}`（`persist` :166-176 原样回）。`state` 里含全部仓库的路径。
- 前端自动起服务的规则（**不改**，只依赖）：`desktop/web/src/shellpages/FirstRunView.tsx:63-74`——`service.kind === 'exited'` 不自动起；`idle` 或 `svcRepo !== repoToStart` 时调一次 `startService(repoToStart)`，每个仓库只请求一次（`requestedRef`）。`desktop/web/src/shellpages/firstRunModel.ts:73-88`——没有选仓库时 `repoToStart` 取 `state.settings.currentRepo`。
- 词面与 IPC 禁令（`tests/test_gate_t030_baseline.py:128-133`、`:141-148`；`tests/test_gate_t035_baseline.py:107-113`）：`src/**` 里不许出现 `dialog`、`Notification`、`showItemInFolder`、`shell.openExternal`（连注释一起扫）；`ipcMain.on` 只许 main.js 里那两条外观读取通道；`ipcRenderer.send` 全仓禁；`src/**` 不许有 fs 写函数（`settings.js` 除外，它只许窄写集）。
- 要改的旧门禁（行号在本基线上核过）：
  - `tests/test_gate_t026_baseline.py`：模块常量 `HOST_CHANNELS`（:101，七项）；preload 探针的 `CHANNELS`（:373-381）；用例标题「恰好七个通道」（:383）；preload 真跑的键表（:412-414，九项）；ipc 探针的 `CHANNELS`（:1267-1276）；用例标题「恰好七个」（:1279）。
  - `tests/test_gate_t035_baseline.py`：模块常量 `HOST_METHODS`（:136-137，七项，**全文件无人引用**）；hostrelay 探针的 `METHODS`（:872，七项，**有用**）；:900、:906 两处标题写「七个方法」。
  - `tests/test_gate_t060_baseline.py`：模块常量 `HOST_CHANNELS`（:80-87，六项，**无人引用**）与 `HOST_METHODS`（:88，六项，**无人引用**）；S01 断言 preload 注释含「九个函数」（:290）；P01 的 `Object.keys(host)`（:542-547，七键）；P02 探针的 `CHANNELS`（:638-645，七条）、`HOST_METHODS`（:691-694，七项）、preload 键表（:705-724，九项）。
  - `tests/test_gate_t061_baseline.py`：模块常量 `HOST_METHODS`（:108，七项）、`HOST_KEYS_SORTED`（:109-118，九项）、通道表 `HOST_LIST`（:119-124，七项）；静态记号（:347、:350）；P03 的 host 暴露面（:814-820，七键）；P04 的 `HOST_METHODS`（:866-870，七项）；P05 的通道表（:940、:959，七条）；P06 的 preload 键表（:1042、:1049-1050，九项）。
  - `tests/test_gate_t028_baseline.py:1499-1502`（`createShellApi` 十个成员）：**不动**。
  - `tests/test_gate_t039_baseline.py:132-152`（`serviceflow` 的 `afterRunning` 约定，全文件不许出现 `afterRunning: false`）：只读约束，代码写法要满足。
  - `tests/test_gate_t032_baseline.py:117-128`（冻结的前端文件名单，全在 `desktop/web/**`）：本片不碰那些文件。
- 工具链与锁文件：`desktop/shell` 用 Node 自带 `node --test --test-reporter=tap`（`package.json` 的 `scripts.test` 点名 23 个既有测试文件）；`electron@44.9.0` 只是 devDependency，纯逻辑测试不需要 Electron 本体；`desktop/shell/package.json` 与 `package-lock.json` 本片不动。
- 站主已核实、可直接当事实写：Electron 44.9.0 上，同一 userData 下第二份在 `whenReady` 之后调 `app.requestSingleInstanceLock()` 返回 false，随即 `app.exit(0)`，退出码 0；持锁的那一份恰好收到一次 `second-instance`；换一个 userData 目录照样拿到锁；ready 之前拿锁的对照组结论相同。证据目录 `C:/Code/Quizs/.quizs/tt-replay/work/eprobe/app8/`（`run8.mjs`、`run8-single-after-ready.log`、`run8-single.log`）。
- 基线检查：内核在基线提交上跑过 R01（全绿）与 G01（红）；合同端在基线上逐份读过上面列出的源码与门禁，核对了行号、断言文本与模块导出。执行端不必再跑一遍整套测试，按 Validation commands 跑改动相关的检查即可。

## Scope
- allowed_modified_files:
  - desktop/shell/src/settings.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/serviceflow.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostrelay.js
  - desktop/shell/src/ipc.js
  - desktop/shell/preload.js
  - desktop/shell/main.js
  - desktop/shell/README.md
  - desktop/shell/tests/settings.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/serviceflow.test.js
  - desktop/shell/tests/host.test.js
  - desktop/shell/tests/preload.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/hostrelay.test.js
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t035_baseline.py
  - tests/test_gate_t060_baseline.py
  - tests/test_gate_t061_baseline.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths: tests/test_gate_t064_*.py, desktop/web/**, ts/**, docs/**, desktop/shell/package.json, desktop/shell/package-lock.json, desktop/shell/shell-preload.js, desktop/shell/src/shellipc.js, desktop/shell/src/shellprotocol.js, desktop/shell/src/window.js, desktop/shell/src/detect.js, desktop/shell/src/core.js, desktop/shell/src/service.js, desktop/shell/src/control.js, desktop/shell/src/hostcheck.js, desktop/shell/src/launch.js, desktop/shell/src/args.js, desktop/shell/src/handshake.js, desktop/shell/src/python.js
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### `src/settings.js` 的纯函数 `selectRepo(settings, id, at)`
- 签名：`selectRepo(settings, id, at)` → `{ok:false, reason:"unknown-repo"}` 或 `{ok:true, settings: next}`。
- `id` 不是非空字符串，或不在 `settings.repos` 里 → `{ok:false, reason:"unknown-repo"}`，入参一个字节都不改。
- 命中：`next = copySettings(settings)`；`next.currentRepo = id`；`next.repos` 里该 id 那一条的 `lastOpened = new Date(at).toISOString()`；其余条目与键一字不动；入参不被修改（深比较相等）。
- `at` 是毫秒数；纯函数里不读当前时间。
- 导出：`module.exports` 里加 `selectRepo`。`PATCH_KEYS` 与 `SETTINGS_FILE_KEYS` 一字不动。

### `src/shellapi.js` 的两个内部函数（经注入回调交出去）
- `createShellApi` 接受一个可选注入 `onRepoOps`；建好时**同步调一次**，把 `{ listRepos, selectRepo }` 交出去；不注入就不调。`createShellApi` 的返回对象仍**十个成员**（不加 `listRepos`/`selectRepo`）。
- `listRepos(runningId)`：读内存设置（`current()`），返回数组 `[{id, name, current}]`；`current` 为 `id === runningId`；**不带 `path`**；`runningId` 不是字符串时视为没有正在跑的服务（没有哪一条 `current` 为 true）。
- `selectRepo(id, runningId, at)`：依次
  1. `id` 不是非空字符串 → `{ok:false, reason:"bad-args"}`；
  2. `id` 不在仓库列表 → `{ok:false, reason:"unknown-repo"}`；
  3. `id === runningId` → `{ok:false, reason:"current-repo"}`；
  4. 调纯函数 `selectRepo(current(), id, at)`；不成 → `{ok:false, reason:"unknown-repo"}`；
  5. `dropCache()`；
  6. `persist(next)`：写盘失败 → `{ok:false, reason:"write-failed"}`，**内存设置保持原样**；成功 → `{ok:true}`。
- `at` 必须是毫秒数；不是有限数字时用 `Date.now()` 兜底。
- 这两个函数**不进外壳 IPC**；`SHELL_CHANNELS` 仍九条。

### `src/serviceflow.js` 的 `reset()`
- `reset()`：只在 `current.kind === "exited"` 时把状态置为 `{kind:"idle"}`，并以 `{byShell:false}` 通知订阅者（订阅者签名是 `(state, info)`）；`idle`/`starting`/`running` 下什么都不做、不发通知。
- **不经 `moveTo`**（`moveTo` 一字不改）：直接赋值再通知。
- `run` 计数、`child`、`stopping`、`aborting` 都不动；下一次 `start` 自己会重置。
- 「只前进不后退」那段注释（src/serviceflow.js:38-40）要写明：`reset` 是第二个例外（`exited` → `idle`）。
- 全文件不许出现 `afterRunning: false`（T039 S01）。

### `src/host.js` 的三个新成员
- `createHost` 新增三个可选注入项，解构时改名照既有写法（`saveTheme: saveThemeImpl` 的样式）：`listRepos: listReposImpl`、`switchRepo: switchRepoImpl`、`addRepo: addRepoImpl`。
- 返回对象在现有七个成员之后依次加 `listRepos`、`switchRepo`、`addRepo`（共十个）。
- `listRepos()`：注入项不是函数 → `{ok:false, reason:"unavailable"}`；否则调注入项，拿到仓库数组后**只取 `{id, name, current}` 三个键**（注入物带了 `path` 也剥掉），回 `{ok:true, repos:[...]}`。
- `switchRepo(id)`：`id` 不是非空字符串 → `{ok:false, reason:"bad-args"}`，**不进注入项**；注入项不是函数 → `{ok:false, reason:"unavailable"}`；否则**原样回**注入项的结果：`{ok:true}` 或 `{ok:false, reason}`，`reason` 只会是 `unknown-repo` / `current-repo` / `write-failed`。
- `addRepo()`：注入项不是函数 → `{ok:false, reason:"unavailable"}`；否则调注入项，注入项的返回值是下面四种形状之一，主进程**映射**成宿主信封：
  | 注入项返回 | 宿主回 |
  |---|---|
  | `{kind:"cancelled"}` | `{ok:false, reason:"cancelled"}` |
  | `{kind:"rejected", problem}` | `{ok:false, reason: problem}`（`problem` 只会是 `not-git` 或 `no-agent`） |
  | `{ok:false, reason:"write-failed"}` | 原样回 `{ok:false, reason:"write-failed"}` |
  | `{kind:"saved", id}` | `{ok:true, id}` |
  - 不认识的其他形状 → `{ok:false, reason:"internal"}`。
  - 结果**不带 `path`**，也不带 `state`。
- 注入物抛错时 host 里不另包（`src/ipc.js` 的外层会回 `internal`）。
- 文件头注释「六个宿主函数的编排」改成「十个宿主函数」。

### 接线（preload、`src/ipc.js` 三张表、`src/hostrelay.js`）
- 三条新通道，接在 T061 的表尾：`themis-host:list-repos`（实参 0）、`themis-host:switch-repo`（实参 1）、`themis-host:add-repo`（实参 0）。
- `HOST_CHANNELS` 10 项、`HOST_METHOD` 10 项、`HOST_ARITY` 10 项、`HOST_METHODS` 10 项，三张表/`HOST_METHODS` 的顺序都是「旧七项 + 新三项」。
- `preload.js`：`window.themisHost` 暴露 12 个成员；三个新成员的写法与既有成员同款：
  - `listRepos: () => ipcRenderer.invoke("themis-host:list-repos")`
  - `switchRepo: (id) => ipcRenderer.invoke("themis-host:switch-repo", id)`
  - `addRepo: () => ipcRenderer.invoke("themis-host:add-repo")`
  - 注释「九个函数」改成「十二个函数」（preload.js:7）；preload 仍然只 `require("electron")`，不加 `ipcRenderer.send`。
- `src/hostrelay.js`：没有当前 host 时，三个新函数都回 `{ok:false, reason:"forbidden"}`（既有兜底自动覆盖）。

### `main.js`：单实例
- 在 `runShellPage` 的**开头**（`root` 计算与 `index.html` 检查之前）调 `app.requestSingleInstanceLock()`。
- 拿不到锁：`app.exit(0); return;` —— 不建 store、不建 relay、不注册 IPC、不建窗、不起子进程。
- 拿到锁：注册 `app.on("second-instance", …)`：优先取还活着的 `serviceWindow`（`!== null && !isDestroyed()`），没有就取还活着的 `shellWin`，都没有就什么都不做；**先 `restore()`（最小化时）再 `focus()`**。
- 带参数分支一字不改：那里不调 `requestSingleInstanceLock`、不注册 `second-instance`。

### `main.js`：切换编排
- `createShellApi` 的注入项 `onRepoOps`：建好时把 `{listRepos, selectRepo}` 存进 `runShellPage` 里的一个变量（`let repoOps = null;`）。
- 外壳分支的第一次 `createHost(` 注入三个实现：
  - `listRepos`：调 `repoOps.listRepos(repo)`（`repo` 是 `onRunning` 那个参数，即正在跑的服务的仓库 id），回 `{ok:true, repos:[{id,name,current}]}`；`repoOps` 为 null 时回 `{ok:false, reason:"unavailable"}`。
  - `switchRepo`：调下面的切换入口；`repoOps` 为 null 时回 `{ok:false, reason:"unavailable"}`。
  - `addRepo`：调 `api.pickRepo()`，**先拆外壳信封**——返回 `result.ok === true` 时回 `result.value`，否则回 `result` 本身（即 `{ok:false, reason:"write-failed"}`）；拆出来的四种内层形状交给 `host.js` 映射。
  - 带参数分支的第二次 `createHost(` **不注入**这三个（那里回 `unavailable`）。
- 切换入口（`runShellPage` 里的**独立函数**，不写进发 `SERVICE_STATE_CHANNEL` 的订阅回调，也不写进服务窗口 `tracked.closed.then(async` 的收尾）：
  1. `await repoOps.selectRepo(id, runningId, Date.now())`；结果 `ok !== true` 就**原样回**（`unknown-repo` / `current-repo` / `write-failed`），**什么都不动**（不停服务、不关窗、不开页）。
  2. 记下旧服务窗口的引用 → `relay.clear()` → `serviceWindow = null`。
  3. **不等收尾**，立刻回 `{ok:true}`；收尾在后台跑，promise 自己接住错误（不留未处理的 rejection）。
  4. 收尾次序固定：`await flow.stop()` → `flow.reset()` → `await openShellWindow(SHELL_START_URL)` → 关还活着的 `settingsWin` → 关第 2 步记下的旧服务窗口（不读 `serviceWindow` 变量）。
  5. `openShellWindow(SHELL_START_URL)` 失败：往 stderr 写一行 `ERROR: …`（说明是切换后首次启动页开不出来），然后 `app.exit(1)`。
- `current` 与 `current-repo` 都用**正在跑的服务的仓库 id**（`onRunning` 的 `repo`），不用 `settings.currentRepo`；切换之后两者重新一致。
- 切换期间用户手动关掉旧服务窗口：窗口清零后 Electron 会退出应用，但设置已存成 B，下次直接起 B——不加代码处理这种少见情况。

### `main.js`：选目录对话框的父窗口
- `chooseDirectory` 的父窗口依次取：还活着的 `shellWin` → 还活着的 `settingsWin` → 还活着的 `serviceWindow` → 不带窗口调用。
- `chooseFile` 与 `confirmExternal` 不改。

### 边界输入
- `switchRepo(undefined)` / `switchRepo("")` / `switchRepo(123)` / `switchRepo({})` → `{ok:false, reason:"bad-args"}`，不进注入项。
- `listRepos()` 在没有正在跑的服务时：返回设置里的全部仓库，`current` 全为 false。
- `addRepo()` 在用户取消 → `cancelled`；目录不是 git 仓库 → `not-git`；目录没有 `.agent` 目录 → `no-agent`；写盘失败 → `write-failed`；成功（重复添加同一路径也算成功）→ `{ok:true, id}`，重复时给已有那一条的 id。
- `reset()` 在 `idle`/`starting`/`running` 下：状态不变、不发通知。

### 错误与重试
- 写盘失败（`persist` 抛错）：内存设置不变，`selectRepo` 回 `write-failed`，切换入口原样回，什么都不动。
- `flow.stop()` 失败或抛错：收尾 promise 自己接住错误，不影响已经回给调用方的 `{ok:true}`。
- 首次启动页开不出来：`ERROR:` 一行 + `app.exit(1)`。

### 并发、取消与状态变化
- `switchRepo` 连点两次：第二次回 `forbidden`（`relay.clear()` 紧跟存盘之后同步执行，IPC 插不进来）——不加 busy 标志。
- 服务在 `running` 期间自己退出 → 走既有的服务状态页那条路，与本片无关。
- 切换期间 `flow.stop()` 发出的 `exited` 带 `byShell:true`，且此时 `serviceWindow === null`，订阅回调直接返回，不进服务状态页；旧服务窗口迟到的 `closed` 被 `main.js` 里既有的身份检查（`if (serviceWindow !== opened) return;`）挡掉。

### 兼容性（公开 API、数据与格式）
- 外壳 IPC 冻结：`SHELL_CHANNELS` 九条、`shell-preload.js` 十一个成员、`createShellApi` 十个成员、`src/settings.js` 的 `PATCH_KEYS`/`SETTINGS_FILE_KEYS`——一律不动。
- `desktop/web/**` 与 `ts/**` 一个文件都不改（T032 s09）。
- 本片**故意推翻**的旧断言（逐处改法见 Steps 第 11 步）：
  - T026：preload 键表九项 → 十二项；`HOST_CHANNELS` 七项 → 十项（两处探针各一份清单）。
  - T035：`HOST_METHODS` 七项 → 十项（模块常量与探针清单各一份）。
  - T060：preload 注释「九个函数」→「十二个函数」；host 暴露面七键 → 十键；`HOST_CHANNELS` 七条 → 十条；`HOST_METHODS` 七项 → 十项；preload 键表九项 → 十二项。
  - T061：同上四组（`HOST_METHODS` 七项 → 十项、`HOST_KEYS_SORTED` 九项 → 十二项、通道表七条 → 十条、host 暴露面七键 → 十键、preload 键表九项 → 十二项）。
- 不改的：`tests/test_gate_t028_baseline.py`（`createShellApi` 十个成员）、`tests/test_gate_t030_baseline.py`、`tests/test_gate_t032_baseline.py`、`tests/test_gate_t033_baseline.py`、`tests/test_gate_t039_baseline.py`（只被我们的写法满足，不改门禁）。

## Steps
1. 读 Repository facts 里列的文件与门禁，确认签名、个数与行号一致；不一致就停下并报告（Stop conditions）。
2. **`src/settings.js` 加纯函数 `selectRepo`**：按 Behavior contract 实现；`module.exports` 加 `selectRepo`；`PATCH_KEYS`/`SETTINGS_FILE_KEYS` 不动。在 `desktop/shell/tests/settings.test.js` 加用例：未知 id → `{ok:false, reason:"unknown-repo"}` 且入参深比较不变；命中 → 只改 `currentRepo` 与目标条目的 `lastOpened`（`new Date(at).toISOString()`），别的条目的 `lastOpened` 不变，入参深比较不变；`id` 不是字符串 → `unknown-repo`。
3. **`src/shellapi.js` 加两个内部函数**：`createShellApi` 接受可选注入 `onRepoOps`（建好时同步调一次，交出 `{listRepos, selectRepo}`）；实现 `listRepos(runningId)` 与 `selectRepo(id, runningId, at)`（次序与错误词见 Behavior contract）；返回对象仍十个成员。在 `desktop/shell/tests/shellapi.test.js` 加用例：注入回调被调一次且交出两个函数；返回对象仍十个成员；`listRepos` 的结果里没有 `path`、只有 `runningId` 那一条 `current` 为 true；`selectRepo` 的 `bad-args`/`unknown-repo`/`current-repo`/`write-failed` 四种拒绝与成功都覆盖（成功时读回 `settings.json` 核对 `currentRepo` 与 `lastOpened`）；写盘失败（假 store 让 `save` 抛错）后内存里的 `currentRepo` 仍是旧值；成功后下一次 `getState` 会重新探测（用计数的 probe 验证缓存已清）。
4. **`src/serviceflow.js` 加 `reset()`**：按 Behavior contract 实现；`moveTo` 一字不改；改「只前进不后退」那段注释写明 `reset` 是第二个例外；全文件不许出现 `afterRunning: false`。在 `desktop/shell/tests/serviceflow.test.js` 加三点用例：`exited` → `idle` 且订阅者收到 `{kind:"idle"}` 与 `info.byShell === false`；`idle`/`starting`/`running` 下状态不变、不发通知；`reset` 之后能再 `start` 一个新 run（用 `tests/fixtures/fake-service.js`）。
5. **`src/host.js` 加三个成员**：按 Behavior contract 实现（注入项名 `listRepos`/`switchRepo`/`addRepo`，解构时改名为 `*Impl`）；返回对象在旧七项之后依次加三个；文件头注释改成「十个宿主函数」。在 `desktop/shell/tests/host.test.js` 加用例：三个函数没注入时都回 `unavailable`；`switchRepo` 的 `bad-args` 覆盖 undefined、空串、数字、对象（这几种都不进注入项）；`addRepo` 的四种映射逐一测，结果的 JSON 里没有路径也没有 `state`；`listRepos` 剥掉 `path`；返回对象的键序是旧七项 + 新三项（顺序逐名相等）。
6. **接线**：`src/ipc.js` 三张表各加三项（通道 `themis-host:list-repos` / `themis-host:switch-repo` / `themis-host:add-repo`，实参 0/1/0）；`src/hostrelay.js` 的 `HOST_METHODS` 加三项（共十项）；`desktop/shell/preload.js` 加三个成员（共十二个），注释「九个函数」→「十二个函数」。在 `desktop/shell/tests/ipc.test.js`、`tests/hostrelay.test.js`、`tests/preload.test.js` 里把个数与清单改成 10/10/12，并补三个新通道的转交与「没有 host 回 forbidden」的用例。
7. **`main.js` 单实例**：在 `runShellPage` 开头（`root` 与 `index.html` 检查之前）拿锁；拿不到就 `app.exit(0); return;`；拿到就注册 `app.on("second-instance", …)`（先 restore 再 focus）。带参数分支一字不改。
8. **`main.js` 注入与切换编排**：`runShellPage` 里加 `let repoOps = null;`；`createShellApi` 传 `onRepoOps`；外壳分支的第一次 `createHost(` 注入 `listRepos`/`switchRepo`/`addRepo`（`addRepo` 的注入物先拆外壳信封）；加切换入口的独立函数与收尾（次序见 Behavior contract），带参数分支不注入。
9. **`main.js` 选目录父窗口**：`chooseDirectory` 的父窗口补上 `serviceWindow` 一级（`shellWin` → `settingsWin` → `serviceWindow` → 不带窗口）；`chooseFile`、`confirmExternal` 不动。
10. **`desktop/shell/README.md`**：
    - 第 5 行那句「托盘、单实例、多仓库切换仍没有」改成只留「托盘」（单实例与多仓库切换本片做了）；**「外壳页在本片就位」必须留着**（T035/T039/T060 的 needle）。
    - 「宿主接口 `window.themisHost`」一节首句「preload 只把九个函数原样转交……」改成「十二个函数」；表里加三行 `listRepos()` / `switchRepo(id)` / `addRepo()`，各写清说明与失败时的 `reason` 词表（`listRepos`：`unavailable`、`forbidden`；`switchRepo`：`bad-args`、`unknown-repo`、`current-repo`、`write-failed`、`unavailable`、`forbidden`；`addRepo`：`cancelled`、`not-git`、`no-agent`、`write-failed`、`unavailable`、`forbidden`）。
    - 「宿主接口（`createHost` 建的五个函数）」改成「十个函数」。
    - 退出码表：`**0**` 那行补「同一 userData 下起的第二份（单实例）以 0 退出」；`**1**` 那行补「切换仓库时首次启动页开不出来」（**不许在这一行出现「服务意外退出」**，T039 钉着）。
    - 「手工冒烟」一节加两条：单实例（同一 userData 再起一份 → 以 0 退出、不另起服务、第一份的窗口还在）与切换（`switchRepo` → 首次启动页 → 新服务窗口，过程中没有服务状态页，应用没退出）。
11. **改旧门禁**（逐处，只改个数与清单，不删用例、不弱化断言）：
    - `tests/test_gate_t026_baseline.py`：模块常量 `HOST_CHANNELS`（:101）加三项 → 十项；preload 探针 `CHANNELS`（:373-381）加三项；用例标题「恰好七个通道」→「恰好十个通道」（:383）；preload 真跑的键表（:412-414）加 `addRepo`、`listRepos`、`switchRepo` → 十二项；ipc 探针 `CHANNELS`（:1267-1276）加三项；标题「恰好七个」→「恰好十个」（:1279）。
    - `tests/test_gate_t035_baseline.py`：模块常量 `HOST_METHODS`（:136-137）加三项 → 十项（注释「host 的七个方法名」一并改）；hostrelay 探针 `METHODS`（:872）加三项 → 十项；:900、:906 的标题「七个方法」→「十个方法」。
    - `tests/test_gate_t060_baseline.py`：模块常量 `HOST_CHANNELS`（:80-87）与 `HOST_METHODS`（:88）各自改成十项（这两个常量无人引用，改成与现状一致）；:290 断言 `assert "九个函数" in preload` 改成 `assert "十二个函数" in preload`（断言消息同步改）；P01 的 `Object.keys(host)`（:542-547）加三项 → 十键；P02 探针 `CHANNELS`（:638-645）加三项 → 十条；P02 探针 `HOST_METHODS`（:691-694）加三项 → 十项；preload 真跑的键表（:705-724）加三项 → 十二项。
    - `tests/test_gate_t061_baseline.py`：模块常量 `HOST_METHODS`（:108）加三项 → 十项；`HOST_KEYS_SORTED`（:109-118）加 `addRepo`、`listRepos`、`switchRepo` → 十二项（按 JS 默认排序插到正确位置）；通道表 `HOST_LIST`（:119-124）加三条 → 十条；P03 的 host 暴露面（:814-820）加三项 → 十键；P04 的 `HOST_METHODS`（:866-870）加三项 → 十项；P05 的通道条数（:940、:959）随 `HOST_LIST` 自动变，标题里的「七个通道」改成「十个通道」；P06 的 preload 键表（:1042、:1049-1050）加三项 → 十二项。
    - `tests/test_gate_t028_baseline.py`、`t030`、`t032`、`t033`、`t039`：**不改**。
12. **自检**：跑 Validation commands 里与改动相关的检查（V01 与 R01；G01 由门禁端合入基准后跑），记录命令与结果；写执行报告。

## Validation commands

- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t064_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py tests/test_gate_t059_baseline.py tests/test_gate_t060_baseline.py tests/test_gate_t061_baseline.py -q` · cwd：仓库根 · 超时：3600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：宿主接口多三个函数——`window.themisHost` 十二个成员、`HOST_METHODS` 十项、`src/ipc.js` 三张表十项、`createHost` 返回十个成员，三条新通道名与实参个数如上；证据：V01、G01、R01；目的：T062 的前端能直接调 `listRepos`/`switchRepo`/`addRepo`，既有七个宿主函数的形状一个字没变。
- D02：`settings.selectRepo` 是纯函数——只改 `currentRepo` 与目标条目的 `lastOpened`，入参不变，未知 id 回 `unknown-repo`；证据：V01、review；目的：切换的存盘动作可单测、不会顺手改别的仓库（用例写在 `desktop/shell/tests/settings.test.js`）。
- D03：shellapi 的两个内部函数经注入回调交给 main.js，`createShellApi` 仍十个成员、外壳 IPC 仍九条；证据：V01、R01、review；目的：T028 :1499-1502 与 T030/T033 冻结的外壳接口面不被破坏。
- D04：`serviceflow.reset()` 只在 `exited` 时回 `idle` 并以 `{byShell:false}` 通知，`moveTo` 一字不改，全文件无 `afterRunning: false`；证据：V01、R01；目的：切换后首次启动页能自动起新仓库的服务（T039 的 `afterRunning` 约定不被破坏）。
- D05：host 的三个新成员按 Behavior contract 编排——`unavailable`、`bad-args`、`addRepo` 四种映射、结果不带路径与 state；证据：V01、review；目的：失败原因是固定词，页面能照词表显示（用例写在 `desktop/shell/tests/host.test.js`）。
- D06：同一 userData 下只开一份——拿不到锁的那份在建任何窗口、起任何子进程之前以 0 退出；持锁那份收到 `second-instance` 后先 restore 再 focus；带参数分支不拿锁；证据：G01、review；目的：同一仓库起两份服务撞锁的老问题不再发生。
- D07：切换次序固定为「存盘 → `relay.clear()` 且 `serviceWindow = null` → `flow.stop()` → `flow.reset()` → 开首次启动页 → 关设置窗口与旧服务窗口」；校验或存盘失败原样回且什么都不动；`switchRepo` 在存盘过了就回 `{ok:true}` 不等收尾；收尾自己接住错误；首次启动页开不出来写一行 `ERROR:` 并以 1 退出；证据：G01、review；目的：切换过程中任何时刻至少有一个窗口、不出现服务状态页、应用不退出。
- D08：选目录对话框的父窗口是 `shellWin` → `settingsWin` → `serviceWindow` → 不带窗口；`chooseFile` 与 `confirmExternal` 不变；证据：G01；目的：服务窗口里点「添加仓库」时对话框挂在正确的父窗口上。
- D09：README 第 5 行不再把单实例与多仓库切换列进「仍没有」（「托盘」留着、「外壳页在本片就位」留着），宿主接口表首句改成十二个函数并加三行，退出码表补 0/1 两种新情形，冒烟加单实例与切换两条；证据：R01、review；目的：文档与实际行为一致、站主能照 README 冒烟（T026/T030/T035/T039/T060/T061 的 README 断言由 R01 覆盖）。
- D10：所有修改都在 Scope 的允许集合内，没有新增测试文件、没有改 `desktop/shell/package.json`；证据：scope；目的：候选补丁可被独立复跑（依赖清单与锁文件一字不动）。
- D11：没有删除、跳过或弱化既有测试；旧门禁只改个数与清单，用例一条没删；证据：review；目的：回归保护仍在（改动前后的断言强度可比）。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `createHost` 的返回成员不是七个、`pickRepo` 的返回不是外壳信封、`createShellApi` 的成员不是十个）。
- 必须修改允许范围之外的文件才能继续（尤其是 `desktop/shell/package.json`、`desktop/web/**`、`ts/**`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 2400
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读源码与门禁 20 分钟；实现 9 个改动点 60 分钟；补测试与改旧门禁 40 分钟；跑 V01/R01 与写报告 30 分钟；总计约 150 分钟，单轮上限 2400 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
