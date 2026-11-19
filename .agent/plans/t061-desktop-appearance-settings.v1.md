# TASK: t061-desktop-appearance-settings

<!-- 片 A（外壳侧）。合同正文里的接口名、通道字面量、文案都是定死的做法，执行端照抄即可；
     片 B（T063，前端侧）照抄「片 B 照抄」一节。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: bc756ad2a839ed323b20e9e15bd072600d0eaaa5
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
外壳侧（片 A）让外观设置真的生效：设置里缺省主题改成暗；主进程在两个启动分支都提供**同步**外观读取，页面在第一次渲染前就能拿到已保存的 `{ theme, density }`；任何一次成功保存只要改了主题或密度，所有还开着的窗口当场收到外观事件；服务窗口新增一个保存主题的宿主函数；建窗时按当前外观设置窗口背景色（暗 `#0C111A`、亮 `#F3F5F9`、跟随系统按 `nativeTheme.shouldUseDarkColors`）。

## Non-goals
- 不碰 `desktop/web` 下的任何文件：前端的 `applyTheme`/`applyDensity`、`App.tsx`、`SettingsView.tsx`、`Table.css`、`themisShell.ts`、`shellBridge.ts` 都在片 B（T063）。
- 不改 `desktop/web/src/shellpages/SettingsView.tsx`（站主 2026-11-19 拍板）：保存失败照现有行为——本窗口照切、提示「主题已切换，但没能保存：…」、不广播、别的窗口不跟。
- 不退役 `tests/test_gate_t032_baseline.py` 的 `UNTOUCHED_REL`（`shellpages/SettingsView.tsx` 那一条保留），不退役 `tests/test_gate_t012_baseline.py` 的 `test_transitional_d08_appearance_without_provider`。
- 不动 `tests/test_gate_t012_baseline.py` 的 `test_transitional_d08_theme_sync_through_app`（只牵涉前端，留给片 B 核实）。
- 不迁移已经存成 `"system"` 的旧设置文件（照旧跟随系统，站主已接受）。
- 主题设为跟随系统时，标题栏不显示解析后的「暗 / 亮」。
- 不改成「先隐藏窗口、画好再显示」，只设背景色；凭据窗口不设背景色。
- 不碰多仓库、托盘、单实例、打包、日志检索轮询；不改依赖与锁文件。

## Repository facts
- 入口：`desktop/shell/main.js`（`runShellPage` 外壳分支、`app.whenReady` 的带参数起服务分支）、`desktop/shell/preload.js`（`window.themisHost`）、`desktop/shell/shell-preload.js`（`window.themisShell`）、`desktop/shell/src/{settings,shellapi,ipc,shellipc,host,hostrelay,window}.js`。
- 现有约定（逐条已读，签名与基线一致）：
  - `src/settings.js:9-17`：`DEFAULT_SETTINGS` 冻结，`theme` 现为 `"system"`、`density` 为 `"standard"`；`THEME_VALUES = ["system","light","dark"]`、`DENSITY_VALUES = ["standard","compact"]`、`PATCH_KEYS` 六键、`SETTINGS_FILE_KEYS` 八键；`createSettingsStore` 有 `load()`/`save()`，坏文件另存 `settings.bad-*` 副本。
  - `src/shellapi.js`：`createShellApi(options)` 返回**十个**成员（`getState … on`），注入项全是可选；`saveSettings` 走 `applyPatch` → `persist`（写盘失败回 `write-failed` 且内存回滚）；`current()` 第一次用到时才 `store.load()`。
  - `src/ipc.js`：`HOST_CHANNELS` 六个（冻结）、`HOST_METHOD`/`HOST_ARITY` 同长；`registerHostIpc` 只用 `ipcMain.handle`，来源不对回 `forbidden`，host 抛错回 `internal`。
  - `src/shellipc.js`：`SHELL_CHANNELS` 九个（invoke，冻结）、`SERVICE_STATE_CHANNEL = "themis-shell:service-state"` 是单向推送常量、不进 `SHELL_CHANNELS`；`shellSenderAllowed` 三条件（sender 一致、frame 非空、frame 地址是外壳页）。
  - `src/hostrelay.js`：`HOST_METHODS` 六项；没有当前 host 时每个方法回 `{ok:false,reason:"forbidden"}`。
  - `src/host.js`：`createHost(options)` 依赖全注入、返回六个函数；`openSettings` 未注入建窗函数时回 `unavailable`。
  - `src/window.js`：`webPreferences`（十键）、`mainWebPreferences`（十键加 preload）、`trackWindow`、`isServiceUrl`；**不 require electron**。
  - `main.js`：唯一一处 `new BrowserWindow`（`guardedWindow`，:36-45）、唯一一处 `.protocol.handle(`（:104，`createShellPageWindow` 内）；外壳页窗口 `options: { title }`（:110）、服务窗口 `options: {}`（:206-212）、带参数分支主窗口 `options: {}`（:394-399）；`registerHostIpc` 只在外壳分支注册一次（经 relay）；`registerShellIpc` 的来源检查认 `shellWin` 与 `settingsWin`。
  - `preload.js:15-22`：`window.themisHost` 六个函数，各自把声明实参原样转交固定通道，不做校验；不 require 相对路径或 `node:` 模块。
  - `shell-preload.js:17-22`（模块级一个 `ipcRenderer.on("themis-shell:service-state")` + `Set` 订阅，退订只删自己那一条）、`:35-50`（`window.themisShell` 十个成员；`on` 只认 `service-state`）。
  - 门禁钉住的位置（本片要改的，逐条在 Steps 里写死改法）：`tests/test_gate_t026_baseline.py:134`（`LOCATION_RULES` 的 `ipcMain.on`）、`:341-409`（P01 preload 探针）、`:1228-1262`（ipc 探针）；`tests/test_gate_t030_baseline.py:137`（`IPC_BANS`）、`:722-727`（`registerShellIpc` 只用 handle）、`:802-943`（P04 shell-preload 探针）；`tests/test_gate_t033_baseline.py:123`（`IPC_BANS`）、`:926-942`（P04）；`tests/test_gate_t035_baseline.py:121`（`IPC_BANS`）与 `HOST_METHODS` 断言；`tests/test_gate_t060_baseline.py:290`（S01「六个函数」）、`:376-378`（S04 禁 `settingsWin.webContents.send`）、`:542-551`（P01 host 暴露面）、`:656-731`（P02 通道 / hostrelay / preload）；`tests/test_gate_t028_baseline.py:308`（P01 `DEFAULTS.theme`）、`:1028` 与 `:1375`（P04 缺省与回滚）、`:125-129`（`ALL_RULES`，**已随 S04 于 2026-11-13 退役、无活用例引用 → 本片不改**）、`:270-272`（退役说明）；`tests/test_gate_t032_baseline.py:117-128`（`UNTOUCHED_REL`，本片不退）。
  - 外壳单测：`desktop/shell/tests/{preload,ipc,hostrelay,host,shellpreload,shellipc,settings,shellapi,shellshape,window}.test.js`（`shellshape.test.js:150-153` 比的是 **createShellApi 的返回成员** 与 `themisShell.ts` 的 `interface ThemisShell`）。
  - 工具链：`desktop/shell/package.json` 的 `scripts.test` = `node --test --test-reporter=tap <22 个 tests/*.test.js 逐个点名>`；Node 自带 `node --test`，报告固定 tap（输出有 `# pass N` / `# fail N`）；纯逻辑测试不 require electron 本体。
  - 仓库外事实（站主 2026-11-19 在 Electron 44.9.0 上实测，合同按事实写）：sandbox + contextIsolation 的 preload 里 `ipcRenderer.sendSync` 能同步拿到 `ipcMain.on` 里设的 `e.returnValue`（两次共 4 ms），经 contextBridge 交给页面的是拷贝；**发到没有监听的通道不会回 undefined——主进程只打一条告警，渲染进程卡住（实测 5 秒无返回）**；`backgroundColor` 设成 `#0C111A` / `#F3F5F9` 时空页面中心取样正是这两个色；`nativeTheme.shouldUseDarkColors` 反映系统当前是否暗色；sandbox preload 的 `process.argv` 里的 `additionalArguments` 在 reload 后不更新（additionalArguments 方案已被否）。
- 基线检查：本回合只读核对了上面列出的文件与行号；整套检查在基线上的结果由内核在执行之前跑过并记入「基线检查记录」，执行端不必再跑一遍。

## Scope
- allowed_modified_files:
  - desktop/shell/main.js
  - desktop/shell/preload.js
  - desktop/shell/shell-preload.js
  - desktop/shell/README.md
  - desktop/shell/src/settings.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/ipc.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostrelay.js
  - desktop/shell/src/window.js
  - desktop/shell/tests/preload.test.js
  - desktop/shell/tests/ipc.test.js
  - desktop/shell/tests/hostrelay.test.js
  - desktop/shell/tests/host.test.js
  - desktop/shell/tests/shellpreload.test.js
  - desktop/shell/tests/shellipc.test.js
  - desktop/shell/tests/settings.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/window.test.js
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t028_baseline.py
  - tests/test_gate_t030_baseline.py
  - tests/test_gate_t033_baseline.py
  - tests/test_gate_t035_baseline.py
  - tests/test_gate_t060_baseline.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths: tests/test_gate_t061_*.py, desktop/web/**, desktop/shell/package.json, desktop/shell/package-lock.json
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - **缺省值**：`src/settings.js` 的 `DEFAULT_SETTINGS.theme` 改成 `"dark"`（`density` 仍 `"standard"`）。没有 `settings.json` 时 `load()` 读出 `{ theme: "dark", density: "standard" }`。已存成 `"system"` 的文件照旧读出 `"system"`（不做迁移）。
  - **通道字面量**（五个，逐字写死，preload 里硬写、`src/*.js` 里是常量，两处一致由单测逐字比对）：
    - 宿主侧保存主题：`"themis-host:save-theme"`（invoke 通道，进 `HOST_CHANNELS` 末尾第七项）
    - 宿主外观读取：`"themis-host:get-appearance"`（同步读，`ipcMain.on`，**不进** `HOST_CHANNELS`）
    - 宿主外观事件：`"themis-host:appearance"`（主进程 → 页面推送，`webContents.send`）
    - 外壳外观读取：`"themis-shell:get-appearance"`（同步读，`ipcMain.on`，**不进** `SHELL_CHANNELS`）
    - 外壳外观事件：`"themis-shell:appearance"`（主进程 → 页面推送，`webContents.send`）
  - **宿主接口 `window.themisHost`（九个）**：`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`、`openSettings`（原六个，行为不变）+ 三个新成员：
    - `saveTheme(pref)` → `ipcRenderer.invoke("themis-host:save-theme", pref)`，只转交这一个实参，返回**信封对象**（不拆信封，与既有六个函数同款）。
    - `getAppearance()` → `ipcRenderer.sendSync("themis-host:get-appearance")`，**同步**返回外观对象 `{ theme, density }`；主进程答 `null` 时返回 `null`。调用时才取，preload 载入时不调用 `sendSync`。
    - `onAppearance(listener)` → 同步返回一个退订函数；模块级只注册**一个** `ipcRenderer.on("themis-host:appearance", (_event, appearance) => …)`，监听函数只收到外观对象**一个**实参；退订只删自己那一条；不依赖 `removeListener`/`off`。
  - **外壳接口 `window.themisShell`（十一个）**：原十个成员行为不变 + `getAppearance()` → `ipcRenderer.sendSync("themis-shell:get-appearance")`（同步返回外观对象或 `null`，调用时才取）；`on(event, listener)` 现在认两个事件名：`"service-state"`（照旧）与 `"appearance"`（新，监听函数只收到外观对象一个实参）；别的事件名同步回空退订函数。模块级共**两个** `ipcRenderer.on`（`themis-shell:service-state`、`themis-shell:appearance`），各自一个 `Set`。
  - **外观对象**：形状固定 `{ theme, density }`，两个字段都在（`theme ∈ {"system","light","dark"}`，`density ∈ {"standard","compact"}`）。主进程答 `null` 表示「此刻没有可读的外观」，页面据此用缺省暗、标准。
  - **`saveTheme` 的信封与错误码**（片 B 照抄）：
    - 成功：`{ ok: true, value: { theme, density } }`（`value` 是刚存下的外观对象；`density` 是当前密度）。
    - 失败：`{ ok: false, reason: "…" }`，`reason` 取值固定为 `bad-args`（`pref` 不在 `THEME_VALUES`）、`unavailable`（这条分支没有注入保存能力）、`forbidden`（来源检查不通过 / 当前没有服务实例）、`write-failed`（写盘失败）、`internal`（注入的实现抛错）。
  - **`src/host.js` 的 `saveTheme` 编排**：`createHost` 新增可选注入项 `saveTheme`（函数）；`saveTheme(pref)` 的顺序固定为：① `pref` 不在 `THEME_VALUES` → `{ok:false,reason:"bad-args"}`；② 没注入 `saveTheme` → `{ok:false,reason:"unavailable"}`；③ 否则调注入的 `saveTheme(pref)`，把它回的信封原样返回；④ 注入的实现抛错 → `{ok:false,reason:"internal"}`。`createHost` 的返回值变成**七个**成员，`saveTheme` 在末尾。
  - **`src/hostrelay.js`**：`HOST_METHODS` 变**七项**，末尾加 `"saveTheme"`；relay 的 `saveTheme` 转给当前 host；没有当前 host 时回 `{ok:false,reason:"forbidden"}`（与其余六个同款兜底）。
  - **`src/ipc.js`**：`HOST_CHANNELS` 变**七个**（末尾 `"themis-host:save-theme"`）、`HOST_METHOD["themis-host:save-theme"] = "saveTheme"`、`HOST_ARITY["themis-host:save-theme"] = 1`；`registerHostIpc` 仍只 `ipcMain.handle`（七个通道），多余实参丢掉，来源不对回 `forbidden`，host 抛错回 `internal`。另导出两个常量：`HOST_APPEARANCE_CHANNEL = "themis-host:get-appearance"`、`HOST_APPEARANCE_EVENT = "themis-host:appearance"`。
  - **`src/shellipc.js`**：`SHELL_CHANNELS` 仍**恰好九个**、顺序不变（外观读取与外观事件都不是 invoke 通道）；另导出两个常量：`SHELL_APPEARANCE_CHANNEL = "themis-shell:get-appearance"`、`SHELL_APPEARANCE_EVENT = "themis-shell:appearance"`。
  - **`src/shellapi.js`**：`createShellApi` 新增**可选注入项** `onAppearanceChange(appearance)`；**返回对象仍是十个成员**（不给它加 `appearance()` 之类的新成员——`tests/shellshape.test.js:150-153` 与 T028 的 P05 探针要求返回成员与 `themisShell.ts` 的 `interface ThemisShell` 逐名相等，而 `themisShell.ts` 属片 B）。另新增**可选注入项** `initialSettings`（已读出的设置）：给了就用它当内存初值（深拷贝），没给才 `store.load()`。
    - `saveSettings`：整包合格且**写盘成功**之后，若 `theme` 或 `density` 与写之前不同 → 调用一次 `onAppearanceChange({ theme, density })`；写盘失败、外观没变、只改仓库等其余情况**一律不调用**。
    - 注入的回调不存在或自己抛错 → 不影响 `saveSettings` 的返回值（吞掉异常，仍回 `{ok:true,value}`）。
    - 另在 `src/settings.js` 导出纯函数 `appearanceOf(settings)`：返回 `{ theme, density }` 的**新对象**（不返回入参本身）。
  - **`src/window.js`**：新增并导出纯函数 `backgroundFor(theme, systemDark)`：`theme === "dark"` → `"#0C111A"`；`theme === "light"` → `"#F3F5F9"`；`theme === "system"`（以及任何不是 dark/light 的值）→ `systemDark` 为真取 `"#0C111A"`，否则 `"#F3F5F9"`。
  - **`main.js` 的接线**：
    - electron 的解构里加 `nativeTheme`。
    - **同步外观读取（`ipcMain.on`）共三处注册，通道字面量只有上面那两个**：
      1. 外壳分支 `runShellPage` 内：`ipcMain.on(HOST_APPEARANCE_CHANNEL, …)`——来源只认当前服务窗口 `serviceWindow` 的 `webContents`（窗口为 `null` 或已销毁一律不认）。
      2. 外壳分支 `runShellPage` 内：`ipcMain.on(SHELL_APPEARANCE_CHANNEL, …)`——来源只认当前外壳页窗口 `shellWin` 或设置窗口 `settingsWin` 的 `webContents`（窗口为 `null` 或已销毁不认）。
      3. 带参数起服务分支（`app.whenReady` 里 `launchMode(argv) !== "shell"` 的那条）内：`ipcMain.on(HOST_APPEARANCE_CHANNEL, …)`——这条分支没有设置存储，**一律答 `null`**（来源不认也是 `null`）。
      - 每个处理函数的形状固定：先把 `event.returnValue = null`（缺省），再 `try { … }`，只有来源被认时才把 `event.returnValue` 覆盖成当前外观对象；`catch` 里 `event.returnValue = null`。**每条路径都设过 `returnValue`**（来源不认、没有可读的外观、读出错，三条都回 `null`）。
      - `desktop/shell` 下除 `main.js` 外**任何** `.js` 文件都不许出现 `ipcMain.on`（含测试与夹具）；`main.js` 里 `ipcMain.on` 只许与上面两个读取通道的字面量同现。
    - **当前外观的持有**：外壳分支启动时 `const initialSettings = store.load().settings;`（只读这一次；坏文件因此最多写一份 `settings.bad-*` 副本），`createShellApi` 传 `initialSettings`；主进程另持一份 `currentAppearance`（初值 `appearanceOf(initialSettings)`），它只在 `onAppearanceChange` 回调里被更新。带参数分支没有 store，恒为 `null`。
    - **广播**：`createShellApi` 的 `onAppearanceChange` 注入 → 主进程把新外观发给还活着的窗口：服务窗口（外壳分支的 `serviceWindow`、带参数分支的 `mainWindow`）发 `HOST_APPEARANCE_EVENT`，外壳页窗口 `shellWin` 与设置窗口 `settingsWin` 发 `SHELL_APPEARANCE_EVENT`；**每个窗口发之前查 `isDestroyed()`**，窗口为 `null` 或已销毁就跳过；负载只有外观对象一个实参。写盘失败不广播（回调根本不会被调用）。带参数分支没有 `createShellApi`，因此没有广播点（那条分支也没有能改外观的界面）。
    - **宿主 `saveTheme` 的注入**：只在外壳分支的 `createHost({ … })` 里注入 `saveTheme`，实现是调 `api.saveSettings({ theme: pref })` 并把结果转成 `saveTheme` 的信封（成功 → `{ok:true,value:{theme,density}}`，失败 → `{ok:false,reason}`，`reason` 沿用 `saveSettings` 的 `bad-patch`/`write-failed` 等）。带参数分支**不注入** → 那里 `saveTheme` 回 `unavailable`。
    - **建窗背景色**：`createShellPageWindow`（外壳页窗口与设置窗口）与两个分支的服务窗口，建窗 `options` 里加 `backgroundColor: backgroundFor(theme, nativeTheme.shouldUseDarkColors)`；`theme` 取当前外观的 `theme`（带参数分支没有当前外观 → 用 `"dark"`）。凭据窗口**不设**。`new BrowserWindow` 仍恰好一处、`.protocol.handle(` 仍恰好一处。
- 边界输入：
  - `pref` 不是字符串、不是 `THEME_VALUES` 里的值（`"neon"`、`null`、数字）→ `bad-args`，不写盘、不广播。
  - 外观读取的来源不认（别的窗口、已销毁的窗口、没有外壳页窗口）→ `null`，不抛错。
  - 读设置时抛错（坏文件、权限）→ `null`，不抛错、不崩渲染进程。
  - `theme` 为 `"system"` 时，背景色按 `nativeTheme.shouldUseDarkColors` 取；`shouldUseDarkColors` 为 `false` → `#F3F5F9`。
  - 保存的补丁里只有仓库相关键（`removeRepo` 等）→ 外观没变 → 不广播。
  - 保存的补丁里 `theme`/`density` 与写之前相同 → 不广播。
  - 写盘失败（磁盘满、目录被占）→ `write-failed`，内存回滚，**不广播**。
  - 一次保存同时改主题与密度 → 只广播**一次**，广播里的外观对象两个字段都是新值。
- 错误与重试：
  - 所有 IPC 处理函数都不抛错：invoke 通道失败回 `{ok:false,reason}`，同步读取通道失败回 `null`。
  - 同步读取**没有重试**：渲染进程会卡住等主进程答复，所以主进程必须保证「有监听就一定答、每条路径都答」。两个分支都必须注册（见上）。
  - 广播失败（窗口在 `isDestroyed` 检查之后被关掉）不重试、不抛错。
- 并发、取消与状态变化：
  - 外观读与写都经同一份设置存储；写盘成功后才更新内存设置，失败回滚（既有行为照旧）。
  - 两个窗口同时保存：各写各的，后写覆盖；广播按实际写盘成功的那一次发。
  - 窗口关闭与广播并发：以 `isDestroyed()` 检查为准，检查后被关掉的窗口收不到事件（不重试）。
  - 服务重启（`reauth` 整页重载）后，preload 重跑，页面再次调 `getAppearance()` 拿到当前值（所以不用 `additionalArguments`）。
- 兼容性：
  - 既有六个宿主函数、既有十个外壳成员、既有九个外壳 invoke 通道、六个宿主 invoke 通道（变七个，见上）的既有行为**不变**；`createShellApi` 的返回成员仍是十个（与 `themisShell.ts` 逐名相等）。
  - `tests/test_gate_t032_baseline.py` 的 `UNTOUCHED_REL`（含 `shellpages/SettingsView.tsx`）与 `tests/test_gate_t012_baseline.py` 的 `test_transitional_d08_appearance_without_provider` **不退役**；`test_transitional_d08_theme_sync_through_app` 本片不动。
  - `tests/test_gate_t028_baseline.py` 的 `ipcMain.on` 禁令**已随 S04 于 2026-11-13 退役**（该文件 `:270-272` 有退役说明、`ALL_RULES` 已无活用例引用），本片不改那一处；T028 只改缺省主题三处。
  - `window.themisShell` 的暴露面本片是十一个成员，而 `themisShell.ts` 的 `interface ThemisShell` 仍是十个（片 B 才加 `getAppearance`）：因此 T030 的 P04 与 `desktop/shell/tests/shellpreload.test.js` 的成员集合断言本片放宽为「解析出的成员 **+ `getAppearance`**」，并在断言旁写明「T063 片 B 起 `themisShell.ts` 加 `getAppearance` 后恢复逐字相等」。这是本片唯一一处放宽既有断言。
  - 已存成 `"system"` 的旧设置文件升级后跟随系统（站主已接受，不迁移）。
  - `desktop/shell/README.md` 的既有 needle（T026/T028/T030/T035/T039/T060 钉的那些）**一条不许丢**；外观的新说法另起段落。

**片 B 照抄（T063 逐字照抄本节，不许改名字与字面量）**
- preload 新成员名：`getAppearance`、`onAppearance`、`saveTheme`；外壳页经 `on('appearance')` 订阅。
- 五个新通道字面量：`"themis-host:save-theme"`、`"themis-host:get-appearance"`、`"themis-host:appearance"`、`"themis-shell:get-appearance"`、`"themis-shell:appearance"`。
- 外观对象形状：`{ theme, density }`（`theme ∈ {"system","light","dark"}`、`density ∈ {"standard","compact"}`）。
- 外观事件实参：`onAppearance(cb)` 与 `on('appearance', cb)` 收到的实参**只一个**外观对象（不是 `{appearance: …}` 之类）。
- `saveTheme` 的信封：成功 `{ ok: true, value: { theme, density } }`；失败 `{ ok: false, reason }`，`reason ∈ {bad-args, unavailable, forbidden, write-failed, internal}`。
- `getAppearance()` 返回外观对象或 `null`（没有可读的外观时是 `null`），页面据此用缺省暗、标准。
- 缺省主题：暗（`"dark"`）；缺省密度：标准（`"standard"`）。

## Steps
1. 读 Repository facts 里的文件，确认签名与基线一致；不一致就停止并报告。
2. `src/settings.js`：`DEFAULT_SETTINGS.theme` 改成 `"dark"`；导出纯函数 `appearanceOf(settings)`（返回 `{ theme, density }` 新对象）。`THEME_VALUES`/`DENSITY_VALUES`/`PATCH_KEYS`/`SETTINGS_FILE_KEYS` 不动。
3. `src/window.js`：新增并导出纯函数 `backgroundFor(theme, systemDark)`（暗 `#0C111A`、亮 `#F3F5F9`、跟随系统按 `systemDark`）。
4. `src/ipc.js`：`HOST_CHANNELS` 末尾加 `"themis-host:save-theme"`（共七个）、`HOST_METHOD`/`HOST_ARITY` 各加一项（`saveTheme`、1）；导出 `HOST_APPEARANCE_CHANNEL = "themis-host:get-appearance"`、`HOST_APPEARANCE_EVENT = "themis-host:appearance"`；`registerHostIpc` 的逻辑不动（七个通道照旧只用 handle）。
5. `src/shellipc.js`：导出 `SHELL_APPEARANCE_CHANNEL = "themis-shell:get-appearance"`、`SHELL_APPEARANCE_EVENT = "themis-shell:appearance"`；`SHELL_CHANNELS` 仍九个、顺序不变。
6. `src/hostrelay.js`：`HOST_METHODS` 末尾加 `"saveTheme"`（共七项）。
7. `src/host.js`：`createHost` 新增可选注入项 `saveTheme` 与 `saveTheme(pref)` 编排（顺序：`bad-args` → `unavailable` → 转交 → 注入抛错回 `internal`）；返回对象末尾加 `saveTheme`（共七个成员）。
8. `src/shellapi.js`：`createShellApi` 新增可选注入项 `onAppearanceChange` 与 `initialSettings`；`saveSettings` 写盘成功且 `theme`/`density` 变了才调一次 `onAppearanceChange({theme, density})`；返回成员仍是十个。**不要**给返回对象加新成员。
9. `preload.js`：`window.themisHost` 从六个函数变九个（加 `saveTheme`、`getAppearance`、`onAppearance`）；模块级一个 `ipcRenderer.on("themis-host:appearance", …)` + `Set` 订阅；`getAppearance` 用 `sendSync`、调用时才取；`onAppearance` 返回退订函数、监听只收一个实参；preload 仍自包含（只 require electron）、仍恰好一次 `exposeInMainWorld`。
10. `shell-preload.js`：`window.themisShell` 从十个成员变十一个（末尾加 `getAppearance`，用 `sendSync`、调用时才取）；模块级共两个 `ipcRenderer.on`（`themis-shell:service-state`、`themis-shell:appearance`），各带一个 `Set`；`on` 认 `"service-state"` 与 `"appearance"` 两个事件名，别的名字回空退订函数；仍恰好一次 `exposeInMainWorld`、仍自包含。
11. `main.js`：
    - electron 解构加 `nativeTheme`；
    - 外壳分支：`const initialSettings = store.load().settings;`；`createShellApi` 传 `initialSettings` 与 `onAppearanceChange` 注入（注入里更新 `currentAppearance` 并广播：服务窗口发 `HOST_APPEARANCE_EVENT`，`shellWin`/`settingsWin` 发 `SHELL_APPEARANCE_EVENT`，每个窗口发前查 `isDestroyed()`）；
    - 外壳分支注册两个同步读取（`HOST_APPEARANCE_CHANNEL`、`SHELL_APPEARANCE_CHANNEL`），带参数分支注册一个（`HOST_APPEARANCE_CHANNEL`，恒答 `null`）；每个处理函数先 `event.returnValue = null` 再 `try/catch`，每条路径都设过 `returnValue`；
    - 外壳分支的 `createHost` 注入 `saveTheme`（调 `api.saveSettings({theme: pref})` 并转成 `saveTheme` 信封）；带参数分支不注入；
    - 建窗：`createShellPageWindow` 与两个分支的服务窗口，`options` 加 `backgroundColor: backgroundFor(theme, nativeTheme.shouldUseDarkColors)`；凭据窗口不设；`new BrowserWindow` 与 `.protocol.handle(` 仍各一处。
12. 外壳单测（改现有文件，不新增文件，`desktop/shell/package.json` 的 `scripts.test` 不用动）：
    - `tests/settings.test.js`：`DEFAULTS.theme` 改 `"dark"`；补一条「没有文件时 load 出 dark/standard」。
    - `tests/shellapi.test.js`：缺省值三处 `"system"` → `"dark"`（`:121`、`:477`、`:582`）；补：改 theme/density 且写盘成功 → `onAppearanceChange` 调一次并带 `{theme,density}`；写盘失败 → 不调；外观没变 → 不调；只改仓库 → 不调。
    - `tests/window.test.js`：补 `backgroundFor` 的纯函数用例（dark → `#0C111A`、light → `#F3F5F9`、system × `shouldUseDarkColors` 真/假两种）。
    - `tests/preload.test.js`：暴露面键表改成九个（`["getAppearance","notify","onAppearance","openExternal","openSecretWindow","openSettings","reauth","reveal","saveTheme"]`）；「六个通道与 `HOST_CHANNELS` 逐字一致」那条改成七个；`saveTheme` 只转交一个实参到固定通道；`getAppearance` 走 `sendSync` 并把回值原样返回；`onAppearance` 返回退订函数、只把外观对象一个实参交给监听、退订只删自己那条；模块级恰好一个 `ipcRenderer.on`（频道 `themis-host:appearance`）；假 electron 补 `sendSync`。
    - `tests/shellpreload.test.js`：成员集合断言改成「解析出的 `interface ThemisShell` 成员 **+ `getAppearance`**」（并写明 T063 恢复逐字相等）；「暴露面仍是十个成员」改成十一个；补 `getAppearance` 走 `sendSync`、`on('appearance')` 的订阅/退订/单实参、模块级恰好两个 `ipcRenderer.on`（两个频道各一个）；假 electron 补 `sendSync`。
    - `tests/ipc.test.js`：`HOST_CHANNELS` 断言改七个（末尾 `themis-host:save-theme`）；「只用 `ipcMain.handle` 注册六个通道」改七个；补两个新常量的逐字断言；补 `save-theme` 转交 `saveTheme`、多余实参丢掉。
    - `tests/shellipc.test.js`：补两个新常量的逐字断言；断言它们**不进** `SHELL_CHANNELS`（仍九个）。
    - `tests/host.test.js`：「暴露面：六个函数」改七个（末尾 `saveTheme`）；补 `saveTheme` 的 `bad-args` / `unavailable` / 转交 / 注入抛错回 `internal`。
    - `tests/hostrelay.test.js`：`HOST_METHODS` 七项（末尾 `saveTheme`）；没有当前 host 时 `saveTheme` 回 `forbidden`。
    - `tests/shellshape.test.js`：**不改**（`createShellApi` 的返回成员仍是十个，与 `themisShell.ts` 逐名相等）。
13. 旧门禁逐处改法（只改下列各处，别的用例一个不许删、一个不许弱化）：
    - `tests/test_gate_t026_baseline.py`
      1) `LOCATION_RULES` 里 `ipcMain.on` 那一条（`:134`，scope `"all"`）：改成只许出现在 `main.js`；并在同一处加一条断言——`main.js` 里 `ipcMain.on` 注册的通道字面量只许是 `"themis-host:get-appearance"` 与 `"themis-shell:get-appearance"`；`desktop/shell` 下其他 `.js`（含 `tests/**`）一律不许出现 `ipcMain.on`。`ipcRenderer.send` 那一条不动。
      2) P01 探针（`:341-409`）：`CHANNELS` 列表末尾加 `"themis-host:save-theme"`；「`HOST_CHANNELS` 恰好六个通道、冻结」改七个；「键恰好六个」改九个并换成上面的逐字键表；「preload 不许有 `ipcRenderer.on`」改成「恰好一个 `ipcRenderer.on`，频道是 `themis-host:appearance`」；假 electron 的 `ipcRenderer` 补 `sendSync`（记录通道与回值）。
      3) 文件头说明里与「六个函数」「五通道」直接冲突的那几句，改成与新形状一致；其余描述不动。
    - `tests/test_gate_t028_baseline.py`（**只改缺省主题三处**）
      1) P01 探针的 `DEFAULTS`（`:308`）：`theme: "system"` → `theme: "dark"`。
      2) P04 探针的 `getState` 期望（`:1028`）：`theme: "system"` → `theme: "dark"`。
      3) P04 探针的写盘失败回滚期望（`:1375`）：`"system"` → `"dark"`。
      4) `:127` 的 `ipcMain.on` 禁令**不改**（已随 S04 退役，无活用例引用）；P05 探针（`:1500-1502`）**不改**（`createShellApi` 的返回成员仍是十个）。
    - `tests/test_gate_t030_baseline.py`
      1) `IPC_BANS` 里 `ipcMain.on` 那一条（`:137`）：按 T026 同一口径改（只许 `main.js`、通道只许那两个读取字面量）；`ipcRenderer.send` 不动。
      2) P04 探针（`:879-885`）：成员集合断言改成「`Object.keys(暴露面).sort()` 等于解析出的 `interface ThemisShell` 成员 **加 `getAppearance`**」（`expected.length` 仍断言 10），并在断言旁写明「T063 片 B 起 `themisShell.ts` 加 `getAppearance` 后恢复逐字相等」。
      3) 「九个方法各用一条通道，合起来恰好等于 `SHELL_CHANNELS`」与「`registerShellIpc` 仍只注册九个 handle、一次 `ipcMain.on` 都没有」两条**不改**（同步读取注册在 `main.js`，不进 `registerShellIpc`；`getAppearance` 走 `sendSync`，不进 `SHELL_CHANNELS`）。
    - `tests/test_gate_t033_baseline.py`
      1) `IPC_BANS` 里 `ipcMain.on` 那一条（`:123`）：按 T026 同一口径改。
      2) P04 探针（`:926-942`）：`internalListener` 改成**按频道找**监听（模块级现在注册两个 `ipcRenderer.on`：`themis-shell:service-state` 与 `themis-shell:appearance`），service-state 那条仍断言「只收 state 一个实参」；「暴露面仍是十个成员」改成十一个（末尾 `getAppearance`）。
      3) 「别的事件名同步回空退订函数」那条：若它用的名字是 `"appearance"`，换成别的名字（例如 `"other-event"`），别的事件名仍回空退订函数。
    - `tests/test_gate_t035_baseline.py`
      1) `IPC_BANS` 里 `ipcMain.on` 那一条（`:121`）：按 T026 同一口径改。
      2) `HOST_METHODS` 的断言：六项改**七项**（末尾 `saveTheme`）。
    - `tests/test_gate_t060_baseline.py`
      1) S01（`:290`）：`preload.js` 注释里的「六个函数」改「九个函数」；`openSettings` 的三条断言不动。
      2) S04（`:376-378`）：`settingsWin.webContents.send` 的禁令**收窄**成「只禁 `settingsWin.webContents.send(SERVICE_STATE_CHANNEL…)`」——服务状态事件仍只发外壳页窗口，外观事件发设置窗口是允许的。
      3) P01（`:542-551`）：host 暴露面六个改**七个**（末尾 `saveTheme`）。
      4) P02（`:656-731`）：`HOST_CHANNELS` 恰好六条改**七条**（末尾 `themis-host:save-theme`）；`hostrelay` 六项改**七项**；preload「键恰好六个」改**九个**；「preload 不许有 `ipcRenderer.on`」改成「恰好一个 `ipcRenderer.on`、频道是 `themis-host:appearance`」；假 electron 补 `sendSync`。
      5) S05（生命周期）与 S03（建窗）里的断言**不改**（本片没动窗口次序与建窗 helper 的形状）。
    - `tests/test_gate_t032_baseline.py` 与 `tests/test_gate_t012_baseline.py`：**不改**。
14. `desktop/shell/README.md`：新增「外观」相关段落（缺省暗、外观对象 `{theme, density}`、五个通道字面量、`saveTheme` 的信封与 `reason` 词表、同步读取的语义「没有可读的外观就是 `null`」、背景色取值）；既有 needle 一条不许丢；与新形状冲突的旧句子（如「暴露面恰好六个函数」「十个成员」）改写成新数字。
15. 运行 Validation commands 里与改动相关的检查，记录命令与结果。
16. 写执行报告；遇到合同未定义的行为，停止并报告。

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：600s · 期望退出码：0 · 输出须匹配：`# pass \d+`，不得出现：`# fail [1-9]`
- V02（必要）：`python -m pytest tests/test_gate_t026_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t060_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t061_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py tests/test_gate_t059_baseline.py tests/test_gate_t060_baseline.py -q` · cwd：仓库根 · 超时：3540s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：缺省主题是暗——没有 `settings.json` 时 `load()` 读出 `{theme:"dark", density:"standard"}`（设置单测与 shellapi 单测各有一条）；证据：V01；目的：外观的缺省值与设计交接一致，别让「缺省暗」只停在页面的内存里。
- D02：两个启动分支都注册了同步外观读取，且每个处理函数每条路径都设过 `event.returnValue`（来源不认、没有可读的外观、读出错都回 `null`），各有单测；证据：V01、G01；目的：渲染进程在通道无人应答时会卡住，这条是首帧能读到外观的前提。
- D03：保存成功且 `theme` 或 `density` 变了才广播一次外观事件；写盘失败、外观没变、只改仓库都不广播；广播前每个窗口查 `isDestroyed()`；证据：V01、G01；目的：别的窗口要当场跟着变，而保存失败时不该有窗口跟着变。
- D04：`saveTheme` 的四种结局各有单测：`bad-args`（pref 非法）、`unavailable`（没注入保存能力）、`forbidden`（来源不认 / 没有当前 host）、成功 `{ok:true,value:{theme,density}}`（走既有 `saveSettings` 并触发广播）；证据：V01；目的：服务窗口标题栏的主题菜单要能存下来，且失败原因词固定。
- D05：建窗背景色纯函数 `backgroundFor(theme, systemDark)` 有单测（暗 `#0C111A`、亮 `#F3F5F9`、跟随系统按 `shouldUseDarkColors`），服务窗口与外壳页窗口都用它设 `backgroundColor`，凭据窗口不设；证据：V01、G01；目的：首帧不闪白/不闪黑。
- D06：外壳单测全过（输出有 `# pass` 且无 `# fail`）；证据：V01；目的：外壳侧的行为有回归保护。
- D07：本片改过的旧门禁全绿（T026、T028、T030、T033、T035、T060），全套回归也绿；T032 的 `UNTOUCHED_REL` 与 T012 的两条过渡断言未退役且仍绿；证据：V02、R01；目的：本片放开的 `ipcMain.on` 只是个口，不得顺手放宽别的禁令。
- D08：所有修改都在允许集合内，没有碰 `desktop/web/**`、没有新增文件、没有改依赖与锁文件；证据：scope；目的：片 A 与片 B 的边界不越。
- D09：没有删除、跳过或弱化既有测试；唯一放宽的两处成员集合断言（T030 的 P04 与外壳单测里那条）都写明了「T063 恢复逐字相等」；证据：review；目的：门禁的强度不因拆片而悄悄下降。
- D10：README 的既有 needle 一条不少，并写清外观相关的通道字面量、信封与缺省值；几份门禁各自的 README 段断言仍绿；证据：V02、review；目的：下一片照 README 就能对齐名字与字面量。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（特别是 `createShellApi` 的返回成员数、`HOST_CHANNELS`/`SHELL_CHANNELS` 的现形状、门禁探针里的逐字键表与本合同不一致）。
- 必须修改允许范围之外的文件才能继续（例如必须改 `desktop/web/**`、`desktop/shell/package.json` 或新增 `tests/*.test.js` 才能过门禁）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如发现「保存失败要不要回退界面」在片 A 里需要动 `SettingsView.tsx`——那是站主已作废的条款，遇到就停下报告）。
- 达到单轮时限（1200 秒）。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读代码与门禁定位 3 分钟；实现（settings/window/ipc/shellipc/host/hostrelay/shellapi/main/两份 preload/README）9 分钟；补与改外壳单测 5 分钟；跑 V01 与 V02 必要检查 2 分钟；写执行报告 1 分钟；总计 20 分钟（不超过单轮时限 1200 秒）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（唯一放宽的两处成员集合断言按 Steps 13 的写法写，并写明恢复条件）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不碰 `desktop/web/**`、不新增文件、不改 `desktop/shell/package.json` 与锁文件。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261119T200051871799Z-owner-150ec7：

> 答复 T061（记为站主决定）。五条仓库外事实已在 Electron 44.9.0 上实测（探针 C:/Code/Quizs/.quizs/tt-replay/work/eprobe/app7/，结果 out7-appearance.json）。
>
> 一、事实
> 1. 成立。sandbox 加 contextIsolation 的 preload 里，sendSync 同步拿到 ipcMain.on 设的 e.returnValue（两次共 4 ms）。经 contextBridge 交给页面的是拷贝：页面改了它，再取仍是原值。
> 2. **不成立**。发到没有监听的通道，主进程只打一条告警，**渲染进程卡住**（5 秒无返回），不是返回 undefined。因此合同写进 DoD 并配单测：
>    - 两个分支都必须注册同步读取；
>    - 处理函数每条路径都设 e.returnValue：来源不认、没有设置可读、读出错都回 null。先设缺省值再覆盖，或用 try/finally；
>    - 单测覆盖来源不认、读出错这两条也设了 returnValue。
> 3. 成立。backgroundColor 设成 #0C111A、#F3F5F9 时，空页面中心取样正是这两个色。
> 4. 成立。本机 AppsUseLightTheme=0x1，shouldUseDarkColors 为 false。themeSource 强制 dark、light 时分别为 true、false，设回 system 又是 false。
> 5. 成立。sandbox preload 的 process.argv 带着 additionalArguments，reload 后仍是建窗时的值，否掉它的理由成立。
>
> 二、拍板
> 1. **SettingsView 不改，两条过渡断言都不退**。我收回任务书第 3 条“保存失败时界面回到已保存的值”。保存失败照现有行为：本窗口照切，提示「主题已切换，但没能保存：…」，不广播，别的窗口不跟。这只在写盘失败时出现，不值得为它动冻结文件。所以：
>    - T032 冻结名单里的 SettingsView.tsx 不退；
>    - T012 的 test_transitional_d08_appearance_without_provider 不退；
>    - 规划第 11 步取消；
>    - d08_theme_sync_through_app（假设 2）只牵涉前端，留给片 B 核实。
> 2. **放开 ipcMain.on，只放 main.js 那两个外观读取通道的字面量**。T026、T030、T033、T035 的 IPC_BANS 照这个口径改，其余禁令照旧。T028 :127 由合同端核实，仍生效就照改。
> 3. **拆片同意**。
>    - T061 只做片 A（外壳侧，规划第 1–7 步，不碰 desktop/web）；片 B 我另登记 T063（--after T061）；T062 改成等 T063。
>    - 片 A 的合同逐字写死片 B 要照抄的东西：preload 新成员名（getAppearance、onAppearance、saveTheme、on('appearance')），新通道字面量，外观对象 {theme, density}，事件实参，saveTheme 的信封与错误码。
>    - 验收以外壳单测和改过的旧门禁为准，我另用 devtools 在真窗口核读值、背景色、事件。
>    - 合同端若判断 A 仍超一次 attempt，先来信再定。
