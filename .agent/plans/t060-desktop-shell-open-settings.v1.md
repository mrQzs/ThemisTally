# TASK: t060-desktop-shell-open-settings

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: cb0a742ac2179fd9f7af0fab1c48d990d656de7e
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
宿主接口加第六个函数 `openSettings()`（不带参数）：服务窗口里的「设置」页签经它打开**唯一一个**设置外壳窗口（`themis-shell://app/index.html#/settings`，窗口标题「设置」），已经开着就 restore + 聚焦，不另开第二个；关掉设置窗口应用不退出、服务不停、焦点回到服务窗口；服务窗口被关掉时设置窗口跟着关，应用照旧按服务的退出码退出。

## Non-goals
- 主题读回不在本片：设置页的主题单选每次新开显示「暗」（ThemePref 在 App 内存里、缺省暗，不读 `settings.theme`），本片只验收**密度**读回。站主另排一片处理「已保存的主题在启动时生效、设置页读回」。
- 本片不碰 `desktop/web/src/shellpages/SettingsView.tsx`（T032 s09 冻结）、`desktop/web/src/App.tsx`、`desktop/web/src/shellpages/themePref.tsx`、`desktop/web/src/live/transport.ts` 的全局声明。
- 不做多仓库切换、托盘、单实例、打包；不在设置窗口里起服务；主题与密度不实时推给服务窗口；改设置之后不提示重启服务（本片只保存，不重启服务）。
- 不改既有的五个宿主函数与九个外壳通道的语义、名字、顺序与文案。

## Repository facts
- 入口：
  - 外壳主进程 `desktop/shell/main.js`：`runShellPage`（外壳页分支）、`app.whenReady` 里的带参数分支（`--repo/--kit/--assets`）。
  - 宿主接口四处接线：`desktop/shell/preload.js`（`contextBridge.exposeInMainWorld("themisHost", …)`）、`desktop/shell/src/ipc.js`（`HOST_CHANNELS` / `HOST_METHOD` / `HOST_ARITY`）、`desktop/shell/src/hostrelay.js`（`HOST_METHODS`）、`desktop/shell/src/host.js`（`createHost` 返回的对象）。
  - 外壳页地址常量 `desktop/shell/src/shellprotocol.js`（`SHELL_START_URL`、`SHELL_STATUS_URL`）。
  - 服务窗口来源检查 `main.js` 的 `senderAllowed`；外壳 IPC 来源检查 `desktop/shell/src/shellipc.js` 的 `shellSenderAllowed(event, contents)`（三条件：发送者就是该窗口的 webContents、frame 非空、frame 是外壳页地址）。
  - 前端页面 `desktop/web/src/pages/SettingsPage.tsx`（`useThemisShell('ready')` + `PageFrame` + `SettingsView`）；宿主接口在前端的全局声明在 `desktop/web/src/live/transport.ts`（`declare global { interface Window { themisHost?: { reauth?: () => unknown } | null } }`）。
- 调用关系与现有约定：
  - `host.js` 的 `openSecretWindow`（`src/host.js:95-118`）是本片 `openSettings` 的写法蓝本：占位在**第一个 await 之前**同步记下；已开就 `focus()`；`once("closed")` 时清空占位；`await win.loadURL(url)` 失败就关窗并回 `{ ok: false, reason: "load-failed" }`；成功回 `{ ok: true }`。
  - `main.js` 的 `openShellWindow`（:75-98）每次现取 `partitionName()`，在该 session 上 `protocol.handle` 一次，用 `guardedWindow` 建窗（`shell-preload.js`），再赋给 `shellWin`、把 `closedByShell` 复位成 false；它的 `tracked.closed` 在「仍是当前窗口、且不是外壳自己关的」时兑现 `userClosedShell`（→ 停服务、`app.exit(0)`，:270-276）。
  - `main.js` 的窗口次序铁律：**先建新窗口、再关旧窗口**，任何时刻都不出现零窗口（:174-175、:205-215）。
  - `trackWindow`（`src/window.js`）返回 `{ closed, close }`，不返回窗口对象；窗口本身的引用要自己留着。
  - `preload.js` 只 require `electron`、不 require 相对路径；`src/**` 里不许 `require('electron')`（T026 S03 / T035 S03）。
  - 前端约定：`shellBridge.ts` 是 `window.themisShell` 的唯一读取点；`SettingsPage.tsx` 不 import `api`（`desktop/web/tests/shellpages-static.test.ts`）。
- 工具链与锁文件：
  - 外壳：`node --test --test-reporter=tap`（`desktop/shell/package.json` 的 `scripts.test` **显式列出 `tests/` 下每个 `*.test.js`**；T026 S02 钉着这一点，本片不加新的外壳测试文件，`package.json` 一个字不改）。
  - 前端：vitest 2.1.8（`npm --prefix desktop/web test` = `vitest run`）、tsc 5.6.3 `strict: true` + `noEmit`（`npm --prefix desktop/web run build` = `tsc --noEmit && vite build`）。
  - Electron 44.9.0 只在 `desktop/shell` 的 devDependencies；**真 Electron 不在自动化覆盖内**，真窗口行为靠人工冒烟（执行端不为冒烟安装依赖）。
- 基线检查（内核在执行前跑过；这里只记合同端核对的仓库现状与硬约束）：
  - 现状行位：`main.js` `runShellPage` :44-277、`openShellWindow` :75-98、服务窗口来源检查 :147-152、建服务窗口后才关外壳窗口 :174-175、关服务窗口的收尾 :178-190、意外退出三条分支 :194-219、`createShellApi` :221-264、`registerShellIpc` :265-269、带参数分支 :279-364（:314 的 `createHost` 不注入任何建窗函数）；`src/host.js` `createHost` :39-158；`src/ipc.js` 三张表各五条；`src/hostrelay.js:7` 五个方法名；`preload.js:9-15` 五个函数；`src/shellprotocol.js:8,10` 两个地址常量、:133-142 导出；`desktop/web/src/pages/SettingsPage.tsx` 36 行；`desktop/web/src/App.tsx:59-63` 把 `document.title` 设成「设置 · Themis Tally」（`index.html` 的 `<title>` 是「Themis Tally」）。
  - 硬约束一（必须绕开）：`tests/test_gate_t032_baseline.py:109-110` 的 `POINTED_FILES`（**含 `desktop/web/src/pages/SettingsPage.tsx`**）与 `POINTED_FORBIDDEN`（含 `"themisHost"`）、以及 `test_s04_unique_read_point`（:268-296）：这五个点名文件剥注释后不许出现 `themisHost` 字样（字符串与类型标注也算）。所以宿主接口的读取不能写在 `SettingsPage.tsx` 里。
  - 硬约束二（必须绕开）：`tests/test_gate_t035_baseline.py:353-372`（S04）：`registerShellIpc` 的第三个实参文本里要有 `shellSenderAllowed` 与 `isDestroyed`，且正则要匹配到 `shellSenderAllowed(event, X.webContents)`；取出的变量名要在 `createShellApi` 的实参文本里出现（或实参里含 `isDestroyed`）。
  - 硬约束三：`tests/test_gate_t026_baseline.py:231-254`（S02）：`desktop/shell/package.json` 的 `scripts.test` 必须显式列出 `tests/` 下每个 `*.test.js`，`devDependencies` 仍是 `{"electron": "44.9.0"}` —— 本片不改 `package.json`。
  - 硬约束四：`tests/test_gate_t006_baseline.py:3285-3287`：`src/pages/` 下恰有 9 个 `*Page.tsx`（本片不加新的 `*Page.tsx`）；`tests/test_gate_t002_baseline.py:1496-1500`：前端测试不许 `skip`/`only`/`todo`。
  - 仓库外事实（站主 2026-11-19 在本机 Electron 44.9.0 / chrome 152.0.7977.167 实测，可直接依赖）：
    - 页面加载约 300 毫秒后把 `document.title` 改成「设置 · Themis Tally」，`page-title-updated` 发两次；不处理该事件的窗口 `getTitle()` 会被页面标题盖掉；**在该窗口上对 `page-title-updated` 调 `event.preventDefault()` 之后，构造时、加载完、1.5 秒后 `getTitle()` 都是「设置」**（事件照发、页面里的 `document.title` 照改）。
    - 一个窗口都不剩、又没有 `window-all-closed` 处理时，应用按 Windows 缺省开始退出，正在加载的窗口报 `ERR_FAILED`；外壳靠「先开新窗口、再关旧窗口」避开。设置窗口关掉时服务窗口还在，不受影响。
  - 规划第 6 节六条假设的核实结果（全部成立，写进本合同的约束）：① T026/T035 门禁写死「五个宿主函数」的地方只有本片要改的三处探针与 T035 的模块常量；② 外壳包内写死「五」的只有 `tests/preload.test.js`、`tests/ipc.test.js`、`tests/hostrelay.test.js`（另有 `tests/host.test.js` 的 D12 文案与 fake host 要跟着改）；③ `(window as unknown as { … }).themisHost` 的就地转型在 tsc strict 下能过，不必改 `src/live/transport.ts` 的全局声明（仓库里已有同样写法：`desktop/web/tests/live-transport.test.ts:359`）；④ 新的前端测试文件会被 vitest 默认 include 收进，且没有门禁按文件名或文件数枚举 `desktop/web/tests`（T006 只 glob `shell-*.test.ts(x)`）；⑤ vitest 里 `window.themisHost` 只在 `live-transport.test.ts` 设过（只有 `reauth`，用完就删），所以新分支在既有用例里不会触发，既有断言不受影响；⑥ 外壳不加新测试文件 → `scripts.test` 不用动。

## Scope
- allowed_modified_files:
  - desktop/shell/main.js
  - desktop/shell/preload.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostrelay.js
  - desktop/shell/src/ipc.js
  - desktop/shell/src/shellprotocol.js
  - desktop/shell/README.md
  - desktop/shell/tests/preload.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/hostrelay.test.js
  - desktop/shell/tests/host.test.js
  - desktop/web/src/pages/SettingsPage.tsx
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t032_baseline.py
  - tests/test_gate_t035_baseline.py
- allowed_new_files:
  - desktop/web/src/live/hostSettings.ts
  - desktop/web/tests/host-settings-open.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t060_*.py
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/shellWindowRoute.ts
  - desktop/web/src/shellpages/themePref.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/live/transport.ts
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/vite.config.ts
  - desktop/web/scripts/check-live-build.mjs
  - desktop/web/tests/shellpages-static.test.ts
  - desktop/web/tests/cleanup2-static.test.ts
  - desktop/web/tests/shellpages-stub.test.ts
  - desktop/web/tests/shellpages-route.test.ts
  - desktop/web/tests/shellpages-first-run.test.tsx
  - desktop/web/tests/shellpages-settings.test.tsx
  - desktop/web/tests/shellpages-app.test.tsx
  - desktop/web/tests/shellpages-isolation.test.tsx
  - desktop/web/tests/shellpages-static.test.ts
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/shell/package.json
  - desktop/shell/package-lock.json
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/serviceflow.js
  - desktop/shell/src/window.js
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - 服务窗口（服务 origin 下的页面）调 `window.themisHost.openSettings()`（无参）：经通道 `themis-host:open-settings` 进主进程，转给当前服务实例的 `host.openSettings()`。
  - 外壳页分支（`runShellPage`）里：`openSettings()` 返回 `{ ok: true }`；若已开着设置窗口，先 `restore()`（仅当 `isMinimized()` 为真）再 `focus()`，仍返回 `{ ok: true }`，**不建第二个窗口**。
  - 新建时：开一个外壳页窗口（新内存分区、`shell-preload.js`、导航判定 `isShellPageUrl`、**不设 parent**），窗口标题「设置」，加载 `themis-shell://app/index.html#/settings`；在该窗口上拦 `page-title-updated` 并 `event.preventDefault()`，使窗口标题保持「设置」。
  - 设置窗口里的外壳接口（`themis-shell:*` 九个通道）放行：来源检查接受「当前外壳窗口」**或**「还活着的设置窗口」，两者都按 `shellSenderAllowed(event, X.webContents)` 的三条件判。
  - 带参数起服务的那条分支（`--repo/--kit/--assets`）**不注入**建窗函数，`openSettings()` 回 `{ ok: false, reason: "unavailable" }`。
- 边界输入：
  - 额外实参丢掉：`HOST_ARITY["themis-host:open-settings"] = 0`，`openSettings("EXTRA")` 与 `openSettings()` 转交的内容一样。
  - 来源不对（不是服务窗口，或服务窗口当前显示的不是服务 origin 下的页面）→ `{ ok: false, reason: "forbidden" }`（既有规则不变）。
  - 设置窗口加载失败 → 关掉那个窗口、回 `{ ok: false, reason: "load-failed" }`，不抛错、不外传错误消息。
  - 设置窗口已关 → 占位清空，再调一次能重新开一个新窗口。
- 错误与重试：所有宿主接口都不抛错；未列出的意外 → `{ ok: false, reason: "internal" }`（既有规则）。加载失败不重试，用户再点一次重新开窗。
- 并发、取消与状态变化：
  - 占位在 `openSettings()` 的**第一个 await 之前**同步记下，并发两次调用只建一个窗口（第二个看到占位就 restore + focus 后回 `{ ok: true }`）。
  - `once("closed")` 时清空占位（只清自己的那一个；迟到的旧窗口 `closed` 不误伤新窗口）。
  - 关掉设置窗口：**不兑现 `userClosedShell`**（不���服务、不退出应用）；服务窗口还活着就 `focus()` 它。
  - 服务窗口被用户关掉：先关设置窗口，再 `flow.stop()`，再按既有规则 `app.exit(0)`（退出码 0）或写 `ERROR: 服务没有以 0 正常退出` 并 `app.exit(1)`；退出码语义不变。
  - 服务在设置窗口开着时意外退出：先开出服务状态页（`SHELL_STATUS_URL`），开好之后才关服务窗口与设置窗口；开不出来就写 `ERROR: 服务意外退出（退出码 N）`、关服务窗口与设置窗口、`app.exit(1)`。
  - **任何时刻不出现零窗口**：先建新窗口、再关旧窗口。
- 兼容性：
  - 既有的五个宿主函数（`reauth` / `openSecretWindow` / `openExternal` / `reveal` / `notify`）、九个外壳通道与它们的名字、顺序、实参个数、文案一字不改；新增的第六个函数排在最后。
  - `desktop/web/src/pages/SettingsPage.tsx` 里**不许出现 `themisHost` 字样**（T032 `test_s04_unique_read_point` 点名该文件）；它不读 `window.themisShell`、不 import `api`。
  - 外壳页窗口里（有 `window.themisShell`）与开发、测试的桩模式下，设置页照旧渲染原来的设置页（同样的 hook、同样的 JSX、同样的文案、同样的「没有收到服务的回应」通用出错块）。
  - `HOST_CHANNELS` 仍是冻结数组，只是多一项；`src/hostrelay.js` 的 `HOST_METHODS` 顺序不变、新项加在末尾。
  - 门禁形状（T026 S03/S04/S05、T030 S04、T033 S04、T035 S03/S04/S05、T030/T033 S03、T039 S06）全部照旧为绿；T032 的 `test_transitional_s06_settings_page_untouched` 按本片退役（见 Steps 第 11 步）。

## Steps
1. 读 `desktop/shell/main.js`、`src/{host,ipc,hostrelay,shellprotocol,shellipc,window}.js`、`preload.js`，以及 `desktop/web/src/pages/SettingsPage.tsx`、`src/App.tsx`、`src/live/transport.ts`、`src/shell/PageFrame.tsx`。确认上面的 Repository facts 与实际一致；不一致就停下报告，不要自己改设计。
2. **地址常量**（`desktop/shell/src/shellprotocol.js`）：在 `SHELL_STATUS_URL` 之后加一行常量
   `const SHELL_SETTINGS_URL = "themis-shell://app/index.html#/settings";`
   并在 `module.exports` 里把它加在 `SHELL_STATUS_URL` 之后。注释写明它是设置外壳页的地址。`isShellPageUrl` 不改（它按协议与主机判，这个地址自然为真）。
3. **宿主接口的四处接线**：
   - `desktop/shell/preload.js`：在 `exposeInMainWorld("themisHost", {…})` 里，`notify` 之后加
     `openSettings: () => ipcRenderer.invoke("themis-host:open-settings"),`
     并把文件里「五个函数」那句注释改成「六个函数」。
   - `desktop/shell/src/ipc.js`：`HOST_CHANNELS` 末尾加 `"themis-host:open-settings"`；`HOST_METHOD` 加 `"themis-host:open-settings": "openSettings"`；`HOST_ARITY` 加 `"themis-host:open-settings": 0`。
   - `desktop/shell/src/hostrelay.js`：`HOST_METHODS` 末尾加 `"openSettings"`（共六项，顺序照旧）。
   - 通道顺序固定为：`reauth`、`open-secret-window`、`open-external`、`reveal`、`notify`、`open-settings`（新项在末尾，门禁探针按这个顺序比对）。
4. **`src/host.js` 的 `openSettings`**：
   - 文件头加 `const { SHELL_SETTINGS_URL } = require("./shellprotocol.js");`。
   - `createHost` 的解构里加 `createSettingsWindow`（可选注入项）。
   - 闭包里加 `let settingsWindow = null;`（占位）。
   - 新增 `async function openSettings()`，写法照 `openSecretWindow`：
     - 没有注入建窗函数（`createSettingsWindow` 不是函数）→ 直接回 `{ ok: false, reason: "unavailable" }`；
     - 已有窗口：`if (win.isMinimized()) win.restore();` 然后 `win.focus();` 回 `{ ok: true }`；
     - 没有：`const win = createSettingsWindow();` **立刻**（第一个 await 之前）记下 `settingsWindow = win`；`win.once("closed", () => { if (settingsWindow === win) settingsWindow = null; })`；`await win.loadURL(SHELL_SETTINGS_URL)`，失败就 `if (!win.isDestroyed()) win.close();` 并回 `{ ok: false, reason: "load-failed" }`；成功回 `{ ok: true }`。
   - `createHost` 返回的对象末尾加 `openSettings`。
5. **`main.js`：建窗 helper 拆两层**：
   - 把 `openShellWindow` 里「取分区 + 在该 session 上注册协议 handler + `guardedWindow`」这三步抽成一个同步函数 `createShellPageWindow(title)`，返回 `BrowserWindow`：
     ```js
     // 外壳页窗口的底层建窗：新分区、在该 session 上注册一次协议 handler、用 shell-preload 建窗。
     // 设置窗口也走这里，但它不碰 shellWin / closedByShell / userClosedShell。
     function createShellPageWindow(title) {
       const partition = partitionName();
       const userSession = session.fromPartition(partition);
       userSession.protocol.handle("themis-shell", (request) => {
         const resolved = resolveShellAsset(root, request.url);
         return new Response(resolved.body, { status: resolved.status, headers: resolved.headers });
       });
       return guardedWindow({
         partition,
         prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")),
         options: { title },
         allowNavigation: isShellPageUrl,
       });
     }
     ```
     `.protocol.handle(` 全文仍恰好一处；它前面 160 字内要有 `fromPartition`、前面 600 字内要有 `partitionName(` —— 上面三行的先后顺序照抄，不要调换。
   - `openShellWindow(url)` 改成用这个 helper，其余语义逐字保留：
     ```js
     async function openShellWindow(url) {
       const opened = createShellPageWindow("ThemisTally");
       shellWin = opened;
       closedByShell = false;
       const tracked = await trackWindow(opened, () => opened.webContents.loadURL(url));
       tracked.closed.then(() => {
         // 只看当前这一个外壳窗口：被换掉的旧窗口什么时候退都不管
         if (shellTracked !== tracked || closedByShell) return;
         userClosedShell();
       });
       shellTracked = tracked;
       return tracked;
     }
     ```
6. **`main.js`：设置窗口**：
   - `runShellPage` 里加 `let settingsWin = null;`。
   - 加建窗函数：
     ```js
     // 设置窗口：只此一个。标题「设置」；页面加载后 ServiceApp 会把 document.title 设成
     // 「设置 · Themis Tally」，那会盖掉窗口标题——在这个窗口上拦 page-title-updated 并
     // preventDefault，窗口标题保持「设置」（站主 2026-11-19 实测：拦了之后构造时、加载完、
     // 1.5 秒后 getTitle() 都是「设置」，页面里的 document.title 照改）。
     function createSettingsWindow() {
       const opened = createShellPageWindow("设置");
       opened.webContents.on("page-title-updated", (event) => {
         event.preventDefault();
       });
       settingsWin = opened;
       opened.once("closed", () => {
         if (settingsWin === opened) settingsWin = null;
         // 关掉设置窗口：应用不退出、服务不停，焦点回到服务窗口
         if (serviceWindow !== null && !serviceWindow.isDestroyed()) serviceWindow.focus();
       });
       return opened;
     }
     ```
     这里**不**兑现 `userClosedShell`（设置窗口不是外壳页窗口）；**不**设 `options.parent`（parent 会让它总压在服务窗口上面）。
7. **`main.js`：注入**：`runShellPage` 的 `onRunning` 里 `createHost({…})` 的实参里加 `createSettingsWindow: () => createSettingsWindow(),`；带参数那条分支（`app.whenReady` 里的 `onServiceReady`）**不加**（那里没有外壳页、没有外壳 IPC，`openSettings()` 因此回 `unavailable`）。
8. **`main.js`：外壳 IPC 的来源检查与对话框父窗口**：
   - `registerShellIpc` 的第三个实参改成：
     ```js
     registerShellIpc(ipcMain, api, (event) => {
       // 来源检查读当前外壳窗口；设置窗口开着时也放行（设置窗口里的外壳接口照外壳页窗口的规则）
       if (shellWin !== null && !shellWin.isDestroyed() && shellSenderAllowed(event, shellWin.webContents)) return true;
       if (settingsWin !== null && !settingsWin.isDestroyed() && shellSenderAllowed(event, settingsWin.webContents)) return true;
       return false;
     });
     ```
     第一个 `shellSenderAllowed(event, shellWin.webContents)` 的写法必须逐字保留（T035 S04 用正则取这个变量名）。
   - `createShellApi` 的三个注入（`chooseDirectory`、`chooseFile`、`confirmExternal`）各自**内联**同一段父窗口表达式（不要抽 helper——T035 S04 要求 `createShellApi` 的实参文本里出现上面那个外壳窗口变量名或 `isDestroyed`）：
     ```js
     const parent =
       shellWin !== null && !shellWin.isDestroyed()
         ? shellWin
         : settingsWin !== null && !settingsWin.isDestroyed()
           ? settingsWin
           : null;
     ```
     然后 `parent === null ? await dialog.showOpenDialog(options) : await dialog.showOpenDialog(parent, options)`；`confirmExternal` 同形，用 `dialog.showMessageBox`。
9. **`main.js`：生命周期**：
   - 用户关服务窗口（`tracked.closed.then` 里）：在两处身份检查（`serviceWindow !== opened`、`serviceGone`）之后、`const stop = await flow.stop();` 之前加
     `if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();`
     （注释写清：服务窗口没了，设置窗口跟着关；关完最后一个窗口应用才退出，退出码规则照旧）。
   - 意外退出（`flow.subscribe` 回调）的三条分支：在关服务窗口的同一处关设置窗口 —— 分支一（`shellWin` 还活着）在 `relay.clear()` 之后、`serviceWindow.close()` 之前；分支二（`openShellWindow(SHELL_STATUS_URL)` 成功后的 `then`）在 `serviceWindow.close()` 之前（新页面开好之后才关旧窗口）；分支三（开不出来）在 `app.exit(1)` 之前关设置窗口与服务窗口。
   - 服务状态事件照旧只发给 `shellWin`，不发设置窗口。
10. **前端**：
    - 新增 `desktop/web/src/live/hostSettings.ts`：
      ```ts
      // 宿主接口的「打开设置」入口：服务窗口的 preload 暴露 window.themisHost，其中 openSettings
      // 开设置外壳窗口。SettingsPage 只调这个函数——SettingsPage.tsx 里不许出现 themisHost 字样
      // （T032 的静态断言点名那个文件不许出现那四类词）。
      export interface HostEnvelope {
        ok?: boolean;
        reason?: string;
      }

      export function hostOpenSettings(): Promise<HostEnvelope> | null {
        const host = (window as unknown as { themisHost?: { openSettings?: () => Promise<HostEnvelope> } | null }).themisHost;
        const open = host?.openSettings;
        if (typeof open !== 'function') return null;
        return open();
      }
      ```
      不许 `declare global`（不必改 `src/live/transport.ts` 的全局声明），不许 import `api`，不许出现 `window.themisShell`。
    - 改 `desktop/web/src/pages/SettingsPage.tsx`：
      - 默认导出的组件先取 `const open = hostOpenSettings();`（非 hook 调用），是函数就走**新分支**，否则走**旧分支**。旧分支的渲染与 hook 一字不改（可以把它搬进同文件的另一个组件 `ShellSettingsPage`，默认导出不变）。
      - 新分支：仍用 `PageFrame`（`title="设置"`，`description` 照旧那句「设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置」），`load` 直接回一个成功信封（字段与旧分支同样的七个：`ok`/`exit_code`/`data`/`output`/`messages`/`command`/`elapsed_ms`；`data` 用本页自己声明的小类型；**`command` 里不许出现 `themisHost` 字样**，写 `['host.openSettings']`），`children` 里放一句说明与一个 **[打开设置]** 按钮。
      - 新分支的行为：挂载时调一次 `openSettings()`；点 [打开设置] 再调一次；返回信封 `ok` 不是 true 时显示一行 `role="alert"`，带上 `reason`；新分支**不调** `getState`，页面上**不出现**「没有收到服务的回应」。
      - `SettingsPage.tsx` 里不许出现 `themisHost` 字样（含注释、字符串与类型标注；文件头注释也别提它），不许 import `api`，不许读 `window.themisShell`。
    - 新增 `desktop/web/tests/host-settings-open.test.tsx`（文件名不许以 `shell-` 或 `shellpages-` 开头；不用 `skip`/`only`/`todo`）：用假的宿主接口覆盖
      - 挂载调一次、点 [打开设置] 再调一次；
      - `getState` 一次都不调；页面里没有「没有收到服务的回应」；
      - 返回 `{ ok: false, reason: "unavailable" }`（或其它 reason）时显示 `role="alert"` 且带 reason；
      - 没有宿主接口时（删掉 `window.themisHost`）照旧渲染旧设置页（h1「设置」、五组 `data-settings-group`）；
      - 测完把 `window.themisHost` 删掉（照 `desktop/web/tests/live-transport.test.ts:359` 的转型写法）。
11. **外壳包内测试与 README**：
    - `desktop/shell/tests/preload.test.js`：用例「暴露面恰好五个函数、没有 openSettings」改成「暴露面恰好六个函数、含 openSettings」——键集合改成 `["notify", "openExternal", "openSecretWindow", "openSettings", "reauth", "reveal"]`（按这个顺序写进 `Object.keys(api).sort()` 的期望），并把「不许有 openSettings」那句断言删掉（改成 `assert.equal(typeof api.openSettings, "function")`）；用例「每个函数只把声明的实参原样转交给固定通道」里加 `api.openSettings();` 与 `api.openSettings("EXTRA");`，期望的 `invokes` 末尾加两条 `["themis-host:open-settings"]`；用例名里的「五个通道」改成「六个通道」。
    - `desktop/shell/tests/ipc.test.js`：`CHANNELS` 末尾加 `"themis-host:open-settings"`；用例名里的「恰好五个」「注册五个通道」改成「六个」；三个假 host 各加一个 `openSettings`（第一个假 host 往 `calls` 里记 `["openSettings", []]`）；在「来源对：转交 host，多余的实参丢掉」里加一条：`handlers["themis-host:open-settings"](EV, "EXTRA")` 回 `{ ok: true }` 且 `calls` 里是 `["openSettings", []]`（多余实参丢掉）。
    - `desktop/shell/tests/hostrelay.test.js`：`METHODS` 末尾加 `"openSettings"`；把写死「5」的地方（注册次数与 `handlers.size`）改成 6，文案里的「五条」改成「六条」。
    - `desktop/shell/tests/host.test.js`：新增 `openSettings` 的用例（照该文件既有的假窗口写法，假窗口要补 `isMinimized()`（返回 false）与 `restore()`）——没注入建窗函数回 `{ ok: false, reason: "unavailable" }`；首次调用建一个窗并 `loadURL` 收到 `themis-shell://app/index.html#/settings`；并发两次只建一个；已开时 `restore` + `focus` 并回 `{ ok: true }`；`closed` 之后能再开；加载失败关窗并回 `{ ok: false, reason: "load-failed" }`；返回值里不含控制令牌。该文件里写死「五个函数」的文案（D12 那条用例名）与假 host 形状一并改成六个。
    - `desktop/shell/README.md`：
      - 第 5 行那句里的「与 `openSettings()` 仍没有」删掉（「托盘、单实例、多仓库切换仍没有」保留），**「外壳页在本片就位」这几个字必须留着**（T035 S05 与 T039 S06 的 needle）。
      - 宿主接口一节：「preload 只把五个函数原样转交」改成「六个」；表里加一行
        `| `openSettings()` | 开设置外壳窗口（`themis-shell://app/index.html#/settings`，标题「设置」）；已经开着就聚焦，不另开第二个 | `unavailable`（这条分支不提供设置窗口，例如带参数起服务）、`load-failed`（设置窗口加载失败） |`
        （表格三列：函数、说明、失败时的 `reason`；`forbidden` 与 `internal` 照旧是通用情形，不写进这一行）。
      - 写清设置窗口的行为：只此一个、聚焦、随服务窗口一起关、**只保存不重启服务**（Python、kit、会话目录的改动下次起服务才生效）。
      - 手工冒烟加一条（第 5 条）：服务起来后点「设置」页签 → 出现标题为「设置」的第二个窗口，显示仓库列表、Python、kit、主题、密度；再点 [打开设置] 不出现第三个窗口；关掉设置窗口后服务窗口与服务进程还在，再点又能打开；在设置窗口里改**密度**，关掉再打开读回改过的值（主题读回不在本片）。
      - 既有 needle 一个不许删：T026 S05 的「npm ci」「npm start」「--repo」「--kit」「--assets」「退出码」「install.js」「node_modules/electron」「冒烟」与 10 秒字样；T035 S05 的「T032」「on('service-state'」「桩数据」「外壳页在本片就位」「npm --prefix ../web run build」「themis-shell://app/index.html#/first-run」「desktop/web/dist」「themisShell」「no-previous」「重启服务」「服务状态页」（≥2 处）、退出码表里 `| **0** |`、`| **1** |`（那一行里仍不许出现「服务意外退出」，要写「服务状态页」）、`| **2** |`；T039 S06 的冒烟第 4 条（「并显示退出码」之后要有「本机服务意外退出」，且「themis-shell://app/index.html#/service-status」「重启服务」「T032 已落地，页面点得动」都在）、「afterRunning」、「byShell」、以及「多一个键就与类型不符」那句照旧要改掉。
12. **旧门禁的逐处改法**（三个文件都在 `allowed_modified_files` 里；只改下面写死的地方，别的一律不动）：
    - `tests/test_gate_t026_baseline.py`：
      - `PROBE_PRELOAD`：`CHANNELS` 末尾加 `"themis-host:open-settings"`；用例名「HOST_CHANNELS 恰好五个通道、冻结」改成「恰好六个通道、冻结」；用例名「preload 真跑一遍：只 require electron、恰好一次 exposeInMainWorld、键恰好五个」改成「键恰好六个」；`assert.deepEqual(Object.keys(api).sort(), […])` 的期望改成 `["notify", "openExternal", "openSecretWindow", "openSettings", "reauth", "reveal"]`；把 `assert.equal("openSettings" in api, false, "不许有 openSettings（留给外壳页那一片）");` 换成 `assert.equal(typeof api.openSettings, "function", "openSettings 必须是函数");`；在现有调用之后加 `api.openSettings(); api.openSettings("EXTRA");`，期望的 `invokes` 末尾加两条 `["themis-host:open-settings"]`。
      - `PROBE_IPC`：`CHANNELS` 末尾加 `"themis-host:open-settings"`；用例名「HOST_CHANNELS 冻结且恰好五个」改成「恰好六个」；用例名「只用 ipcMain.handle 注册五个通道；来源不对回 forbidden 且不进 host」改成「注册六个通道」；三个假 host 各加 `openSettings`（第一个往 `calls` 记 `["openSettings", []]`）；在「来源对：转交 host，多余的实参丢掉」里加：`assert.deepEqual(await handlers["themis-host:open-settings"](EV, "EXTRA"), { ok: true });` 与 `assert.deepEqual(calls[calls.length - 1], ["openSettings", []], "多余的实参要丢掉");`。
      - 文件头 docstring 里描述暴露面个数的地方（「五个函数」「五个固定通道」「恰好五个」「与五个通道逐字一致」）改成「六个」。
    - `tests/test_gate_t035_baseline.py`：
      - 模块常量 `HOST_METHODS`（约在 L128-129）加 `"openSettings"`，上面的注释「host 的五个方法名」改成「六个方法名」。
      - `PROBE_HOSTRELAY`：`METHODS` 末尾加 `"openSettings"`；用例名「形状：{host, senderAllowed, use, clear}，host 是那五个方法」改成「那六个方法」；用例名「没有当前 host：五个方法都回 forbidden 不抛错；senderAllowed 为 false」改成「六个方法」；`assert.equal(registrations, 5, "registerHostIpc 注册五条通道")` 与 `assert.equal(handlers.size, 5)` 改成 6（文案改「六条」）；用例「重入：第一次意外退出、第二次起服务成功，注册次数仍是 5、调用进第二个 host」里的两处 5 改成 6（用例名与断言）。
    - `tests/test_gate_t032_baseline.py`（**只退役 s06 这一条**，别的过渡断言与两条前端过渡用例不动）：
      - 删掉 `def test_transitional_s06_settings_page_untouched():` 那个函数（含它的 docstring 与断言体），在原位置放这段注释（逐字）：
        ```python
        # test_transitional_s06_settings_page_untouched（SettingsPage.tsx 与基线 344b5d0 逐字一致）由站主退役
        # （2026-11-19，T060）：T060 让服务窗口的「设置」页签经 host.openSettings() 打开设置外壳窗口，
        # 本片合法改了 desktop/web/src/pages/SettingsPage.tsx（没有宿主接口时旧的通用出错块照旧留着）。
        ```
      - 文件头 docstring 里那条 bullet 改成：
        `- ``test_transitional_s06_settings_page_untouched``：T060 退役（2026-11-19）——本片改了 SettingsPage.tsx（服务窗口的「设置」页签经 host.openSettings() 打开设置外壳窗口）；该条随本片退役。`
      - `test_transitional_s09_baseline_files_untouched` 与它的 `UNTOUCHED_REL` 名单一个字不改（本片不碰那些文件）。
13. **全量检查**：跑完 Validation commands 里与本次改动相关的检查（V01、V02、V03），再跑 R01 的旧门禁回归；把命令与结果写进执行报告。**不要**跑真 Electron（本仓库的自动化不覆盖真窗口，冒烟由验收端做）；**不要**动 `desktop/shell/package.json`、`desktop/web/package.json` 与任何锁文件。

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t060_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py -q` · cwd：仓库根 · 超时：3420s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm --prefix desktop/shell test` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass`
- V02（必要）：`npm --prefix desktop/web test` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm --prefix desktop/web run build` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`

## Definition of done
- D01：宿主接口有第六个函数 `openSettings()`：preload 暴露面恰好六个（含 `openSettings`）、`HOST_CHANNELS` 恰好六条且冻结、`HOST_METHODS` 六项、多余实参丢掉、`HOST_ARITY` 为 0；证据：V01、G01；目的：接口面与既有五个函数一字不差地并存。
- D02：设置窗口只此一个：没有时开一个（`themis-shell://app/index.html#/settings`、标题「设置」、新分区、`shell-preload.js`、不设 parent），已经开着就 restore + focus，不开第二个；并发两次调用只建一个；证据：V01（包内 host 用例）、G01；目的：用户在设置页签上点几次都只有一个设置窗口。
- D03：设置窗口的标题在页面加载完与 1.5 秒后仍是「设置」（该窗口上 `page-title-updated` 被 `preventDefault`）；证据：G01、review（真窗口冒烟由验收端做）；目的：用户认得出这是设置窗口，而不是被页面标题改成「设置 · Themis Tally」。
- D04：设置窗口里的外壳接口放行（来源检查接受还活着的设置窗口），选择框与确认框在有窗口时挂父窗口；证据：G01、review；目的：设置窗口里能选目录、能确认外链。
- D05：关掉设置窗口时应用不退出、服务不停，焦点回到服务窗口（不兑现 `userClosedShell`）；服务窗口被关掉时设置窗口跟着关，退出码规则与现在相同（0 → `app.exit(0)`，否则写 `ERROR: 服务没有以 0 正常退出` 并 `app.exit(1)`）；服务在设置窗口开着时意外退出照旧切服务状态页；任何时刻不出现零窗口；证据：G01、review；目的：加一个窗口不改变既有退出行为。
- D06：带参数起服务的那条分支不注入建窗函数，`openSettings()` 回 `{ ok: false, reason: "unavailable" }`；证据：V01、G01；目的：那条路上没有外壳页，不假装能开设置窗口。
- D07：服务窗口的「设置」页签在有宿主接口时走新分支：挂载开一次设置窗口、[打开设置] 再开一次（聚焦已有窗口）、不调 `getState`、不出现「没有收到服务的回应」、失败时有一行 `role="alert"` 带 reason；证据：V02、G01；目的：服务窗口的设置页签真的能开设置窗口。
- D08：没有宿主接口时（外壳页窗口、桩模式、开发模式）设置页逐字照旧：同样的 h1「设置」、同样的五组、同样的「没有收到服务的回应」通用出错块；证据：V02、R01（`desktop/web/tests/shellpages-settings.test.tsx` 与 `tests/test_gate_t012_baseline.py` 的既有断言照旧绿）；目的：不改既有分支的行为。
- D09：主题读回不在本片（本片只验收密度读回）；`SettingsView.tsx`、`App.tsx`、`themePref.tsx`、`src/live/transport.ts` 一个字没改；证据：scope、review；目的：站主另排的那一片不被本片抢跑。
- D10：三个旧门禁的改法与合同逐字一致（T026 的 p01/p05、T035 的 p03 与模块常量、T032 的 s06 退役与退役注释），没有顺手改别的断言；证据：R01、G01；目的：门禁的改动可复核，不靠弱化断言换绿。
- D11：门禁形状全绿：T026 的 S03/S04/S05、T030 S04、T033 S04、T035 的 S03/S04/S05、T030/T033 S03（`shell-preload.js` 里不出现 `themisHost`）、T039 S06、前端静态约束（`SettingsPage.tsx` 不读 `window.themisShell`、不 import `api`；只有 `shellBridge.ts` 读 `window.themisShell`）；证据：R01、G01；目的：不破坏别的片钉住的形状。
- D12：README 的宿主接口表有 `openSettings()` 一行（`unavailable`、`load-failed`），第 5 行不再说它「仍没有」但保留「外壳页在本片就位」，写清唯一窗口、聚焦、随服务窗口关、只保存不重启服务，冒烟条目按验收三条补上；既有 needle 一个没删；证据：R01、review；目的：文档与实现一致。
- D13：外壳包内测试与前端新测试覆盖新行为（外壳：不可用、首次建窗、并发只建一个、已开聚焦、关掉再开、加载失败；前端：挂载/按钮各一次、不调 `getState`、alert 带 reason、无宿主接口时照旧）；证据：V01、V02；目的：新行为有独立的回归保护。
- D14：所有修改都在允许集合内，没有新增依赖、锁文件与 `package.json` 一个字没动；证据：scope。
- D15：没有删除、跳过或弱化既有测试；证据：review。
- D16：真窗口冒烟（验收端做，执行端不跑真 Electron）：服务起来后点「设置」页签出标题「设置」的第二个窗口并显示仓库列表、Python、kit、主题、密度；再点 [打开设置] 不出第三个窗口；关掉设置窗口后服务窗口与服务进程还在，再点又能打开；设置窗口里改密度、关掉再打开读回改过的值；首次启动页、服务状态页与关服务窗口退出应用的行为与现在相同；证据：review（人工冒烟）。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `main.js` 的 `runShellPage` 形状、`HOST_CHANNELS` 的内容、T032/T035 的断言与合同写的对不上）。
- 必须修改允许范围之外的文件才能继续（例如需要改 `SettingsView.tsx`、`App.tsx`、`transport.ts`、`shellapi.js` 或任何 `package.json`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 5400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：读代码与核实门禁形状 15 分钟；外壳实现（Steps 2-9）45 分钟；前端实现（Step 10）20 分钟；测试与 README（Step 11）20 分钟；旧门禁改法（Step 12）15 分钟；全量检查与执行报告 25 分钟；余量 20 分钟。总计不超过单轮时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D16，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。执行端看不到真窗口，冒烟项（D16）如实写「未跑，留给验收端」。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不改门禁里与本片无关的断言。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不动 `desktop/shell/package.json`、`desktop/web/package.json` 与任何锁文件；不新增依赖。
- 不在 `desktop/web/src/pages/SettingsPage.tsx` 里出现 `themisHost` 字样，不读 `window.themisShell`，不 import `api`。
- 不碰 T032 s09 冻结的那 15 个前端文件（见 Scope 的 forbidden_paths）。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261119T153909643867Z-owner-76399c：

> 摘要: 仓库外事实已实测核实、成立；① 确认退役 T032 的 test_transitional_s06_settings_page_untouched，由合同把 tests/test_gate_t032_baseline.py 列进 allowed_modified_files、写死退役改法；② 选 A：本片只验收密度读回，主题读回另排一片
> 提交: 无
> 验证: 用本机 Electron 44.9.0（chrome 152.0.7977.167）写探针实测（两个窗口加载同一页：<title>Themis Tally</title>，300 毫秒后 document.title 改成「设置 · Themis Tally」）：
> - 不处理 page-title-updated 的窗口：构造时 title「设置」，加载完 getTitle() 是「Themis Tally」，1.5 秒后是「设置 · Themis Tally」；page-title-updated 发了两次（explicitSet 都是 true）。
> - 在窗口上对 page-title-updated 调 event.preventDefault()：构造时、加载完、1.5 秒后 getTitle() 都是「设置」；事件照样发两次，页面里的 document.title 照样变成「设置 · Themis Tally」。
> - 规划依赖的那条事实成立：设置窗口要保持标题「设置」，就在这个窗口上 preventDefault page-title-updated。
> - 顺带一条相关事实（探针第一遍踩到）：一个窗口都不剩、又没有 window-all-closed 处理时，应用按 Windows 缺省开始退出，正在加载的窗口报 ERR_FAILED。外壳现在靠“先开新窗口、再关旧窗口”避开；设置窗口关掉时服务窗口还在，不受影响。服务窗口被关掉、设置窗口跟着关的那条路，合同照现有的退出码规则写清次序即可。
> 偏离: 无
> 需协调人决定: 无。合同端开工：
> - ① T032 门禁的 test_transitional_s06_settings_page_untouched 退役（它是过渡断言，本片必改 SettingsPage.tsx），照这份门禁里已退役条目的写法注明“T060 退役”，退役措辞由合同逐字写死；别的过渡断言与两条前端过渡用例不动。
> - ② 选 A：验收第 2 条只验收密度读回；主题单选每次新开显示「暗」是已有行为（ThemePref 在 App 内存里、缺省暗，不读 settings.theme），本片不碰 T032 s09 冻结的 SettingsView，也不改 App.tsx、themePref.tsx。站主另排一片处理“已保存的主题在启动时生效、设置页读回”。
> 证据: 探针 C:/Code/Quizs/.quizs/tt-replay/work/eprobe/app6/main.js，结果 out6-title.json（同目录）
