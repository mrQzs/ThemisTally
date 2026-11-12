# TASK: t028-desktop-shell-pages

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 1a2a57de5151123ce4cf6809bcd6021cafe60b6d
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在 `desktop/shell` 里补上外壳页的数据层：设置文件（`<userData>/settings.json`）的读、写、坏文件处理与补丁校验；三项校验（Git 仓库、Python ≥ 3.10、kit 的 `pi_dispatch.py --version`）与自动检测；`window.themisShell` 十个成员的主进程实现（七个真实方法 + 三个占位）；以及一条读 `desktop/web/src/shellpages/themisShell.ts` 做逐字段比对的测试，使返回值形状与该类型文件完全一致。本片不碰 `main.js`、协议与 preload。

## Non-goals
- 不改 `desktop/shell/main.js`、`desktop/shell/preload.js`、`desktop/shell/src/args.js`、`core.js`、`python.js`、`ipc.js`、`host.js`、`hostcheck.js`、`control.js`、`handshake.js`、`service.js`、`window.js`。
- 不改 `desktop/web/**`、`ts/**`、`scripts/**`、任何门禁测试文件。
- 不做协议处理（`themis-shell://`）、外壳页专用 preload、IPC 注册与来源检查、无参数启动流程、main.js 接线、README 的启动说明：这些是 T028b。
- 不做 `startService` / `restartService` / `on('service-state')` 的真实行为（只留占位），不做托盘、单实例、多仓库开窗、通知触发、Fuses、electron-builder。
- 不存任何凭据与控制令牌，不新增任何依赖。

## Repository facts
- 入口与只读参照：
  - `desktop/web/src/shellpages/themisShell.ts`（只读，唯一形状基准）：`RepoCheck = 'ok' | 'not-git' | 'no-agent'`；`PickProblem = 'not-git' | 'no-agent' | 'python-unusable' | 'kit-unusable'`；`PickOutcome = {kind:'cancelled'} | {kind:'saved'; path; id?; state} | {kind:'rejected'; problem; path}`；`RepoEntry = {id,name,path,lastOpened}`；`TranscriptDirEntry = {id,path}`；`ShellSettings = {repos,currentRepo,transcriptDirs,theme,density}`；`ShellState = {app:{version,homepage},settings,currentRepoCheck,python:{status,source,path,version},kit:{status,source,path,version},service}`；`SettingsPatch` 六个键 `theme,density,removeRepo,removeTranscriptDir,resetPython,resetKit`；`ServiceState` 四种 `idle/starting/running/exited`；`interface ThemisShell` 十个成员 `getState,pickRepo,pickPython,pickKit,pickTranscriptDir,saveSettings,startService,restartService,openExternal,on`。
  - `desktop/web/src/shellpages/shellStub.ts`（只读，行为参考：id 去重 `-2/-3`、`saveSettings` 的拒绝项、补丁键表）。
  - `desktop/web/src/mock/shellpages-scenarios.ts:30`：`app.homepage` 取 `https://github.com/mrQzs/ThemisTally`；`app.version` 由调用方注入。
- 调用关系与现有约定：
  - `desktop/shell/src/python.js`：`DEFAULT_PYTHON_CANDIDATES = [["python3"],["python"],["py","-3"]]`（冻结，只读引用，不得改）；`PYTHON_PROBE_CODE` 冻结，不改。
  - `scripts/dispatch-pi.sh:9-19`：候选顺序同样是 python3 → python → py -3。
  - `scripts/pi_dispatch.py:65,8629`：`TOOL_VERSION = "2.12.0"`；`--version` 是顶层 argparse 的 version 动作，不需要 `--repo`，输出 `pi_dispatch 2.12.0` 并以 0 退出。
  - `scripts/kit_install.py:198`：kit 装进目标仓库的是 `scripts/pi_dispatch.py`（`desktop/shell/src/args.js:65` 同口径：`<kit>/scripts/pi_dispatch.py`）。
  - `desktop/shell/src/hostcheck.js` 的 `isExternalUrl(url)`：只许 http/https、拒控制字符，是 `openExternal` 的判据（复用，不改该文件）。
  - `desktop/shell/src/host.js`：主进程侧的返回约定是 `{ok:true}` / `{ok:false,reason}`，失败不抛错；本片统一用信封 `{ok:true,value}` / `{ok:false,reason}`。
  - `desktop/shell/package.json`：`scripts.test` 是 `node --test --test-reporter=tap tests/....test.js ...`（逐个列出）；`devDependencies` 固定 `{electron: "44.9.0"}`，锁文件不动。
- 工具链与锁文件：Node（`node --test`，CommonJS，`desktop/shell/package.json` 的 `type: commonjs`）；不新增依赖、不改 `package-lock.json`。
- 基线检查（执行端在 Step 1 复核，合同不代跑）：`npm test`（cwd `desktop/shell`）在基线上应当全过；`python -m pytest tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py -q`（cwd 仓库根）在基线上应当全过；本片的新门禁基线测试由门禁端稍后提供，在本基线上应当失败（本片的功能还不存在）。
- 门禁事实（新基线 `0592200dd4` 上核对过，`tests/test_gate_t025_baseline.py:199-200`、`tests/test_gate_t026_baseline.py:289-290`）：
  - `fs 写函数`禁令对 `desktop/shell/src/settings.js` 放行 `writeFileSync`、`renameSync`、`mkdirSync`、`unlinkSync` 四个；该文件里别的写函数（`writeFile(`、`appendFile(`、`appendFileSync(`、`mkdir(`、`rm(`、`rmSync(`、`unlink(`、`rename(`、异步 `fs.promises.writeFile(`）照旧不许；别的文件（`main.js` 与 `src/**`）一个写函数都不许。
  - `src/**` 与 `main.js` 里不许出现 `fetch(`、`shell: true`、`persist:`、`net.request`、`autoUpdater`、`crashReporter`（注释也算）。
  - `dialog`、`shell.openExternal`、`showItemInFolder`、`Notification` 只许出现在 `main.js`；`require('electron')` 在 `desktop/shell` 下任何 `.js` 都不许（`tests/**` 也算）；`ipcMain.on`、`ipcRenderer.send` 在 `desktop/shell` 下任何 `.js` 都不许。
  - `main.js` 里 `new BrowserWindow` 恰好一处（本片不改 `main.js`，也不要新增建窗代码）。
  - `scripts.test` 必须带 `--test-reporter=tap` 且开关在文件清单之前，必须显式列出 `tests/` 下每一个 `*.test.js`；`tests/fixtures/` 下不许有 `*.test.js`；`devDependencies` 须仍是 `{electron: "44.9.0"}`。
  - README 的既有字样（`npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、退出码、`install.js`、`node_modules/electron`、冒烟、10 秒、30 秒）必须全部保留。
- 仓库外事实（内核已核实，可当事实用）：Node 的 `fs.rename`/`fs.renameSync` 在目标路径已存在时会覆盖它（目标是目录时报错）——原子写依赖这一点。

## Scope
- allowed_modified_files:
  - desktop/shell/package.json
  - desktop/shell/README.md
  - desktop/shell/src/detect.js
  - desktop/shell/src/settings.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/tests/detect.test.js
  - desktop/shell/tests/fixtures/fake-echo-argv.js
  - desktop/shell/tests/fixtures/fake-kit-fail.js
  - desktop/shell/tests/fixtures/fake-kit-hang.js
  - desktop/shell/tests/fixtures/fake-kit-no-version.js
  - desktop/shell/tests/fixtures/fake-kit-version-stderr.js
  - desktop/shell/tests/fixtures/fake-kit-version.js
  - desktop/shell/tests/fixtures/fake-py-info-oneline.js
  - desktop/shell/tests/fixtures/fake-py-info.js
  - desktop/shell/tests/settings.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/shellshape.test.js
- allowed_new_files:
  - desktop/shell/src/settings.js
  - desktop/shell/src/detect.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/tests/settings.test.js
  - desktop/shell/tests/detect.test.js
  - desktop/shell/tests/shellapi.test.js
  - desktop/shell/tests/shellshape.test.js
  - desktop/shell/tests/fixtures/**
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/shell/main.js
  - desktop/shell/preload.js
  - desktop/shell/src/args.js
  - desktop/shell/src/core.js
  - desktop/shell/src/python.js
  - desktop/shell/src/ipc.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/control.js
  - desktop/shell/src/handshake.js
  - desktop/shell/src/service.js
  - desktop/shell/src/window.js
  - desktop/web/**
  - ts/**
  - scripts/**
  - tests/test_gate_t028_*.py
  - tests/test_gate_t025_baseline.py
  - tests/test_gate_t026_baseline.py
- dependency_changes: forbidden（只改 `scripts.test`，不增删依赖，不动 `package-lock.json`）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 模块与接口（照此实现，不要另起名字）

**`desktop/shell/src/settings.js`（设置存盘；本文件是 `desktop/shell` 里唯一允许出现写文件函数的地方）**

导出：
- `DEFAULT_SETTINGS`：冻结的缺省设置，值恰为 `{version:1, repos:[], currentRepo:null, transcriptDirs:[], theme:"system", density:"standard", pythonPath:null, kitPath:null}`。
- `SETTINGS_FILE_KEYS`：`["version","repos","currentRepo","transcriptDirs","theme","density","pythonPath","kitPath"]`（写盘时只写这些键，顺序照此）。
- `THEME_VALUES`：`["system","light","dark"]`；`DENSITY_VALUES`：`["standard","compact"]`。
- `PATCH_KEYS`：`["theme","density","removeRepo","removeTranscriptDir","resetPython","resetKit"]`。
- `createSettingsStore({dir, now})`：`dir` 是存放设置文件的目录（调用方注入；T028b 里是 Electron 的 userData 目录），`now` 是返回 `Date` 的函数，默认 `() => new Date()`。返回 `{dir, filePath, load(), save(settings)}`：
  - `filePath` = `path.join(dir, "settings.json")`。
  - `load()` 返回 `{settings, badCopy}`：
    - 文件不存在 → `{settings: 缺省设置的深拷贝, badCopy: null}`。
    - 文件存在但 JSON 解析失败、顶层不是普通对象、或任一**已知键**取值不合法 → `{settings: 缺省设置的深拷贝, badCopy: <副本路径>}`；副本内容是坏文件的原始字节，副本路径为 `path.join(dir, "settings.bad-<UTC 时刻>.json")`，时刻格式 `YYYYMMDDTHHMMSSmmmZ`（由 `now()` 给出）；该路径已存在时不覆盖，依次尝试 `-2`、`-3`… 直到不存在的路径为止。
    - 已知键的合法取值：`version` 是数字 `1`；`repos` 是数组，每项是 `{id: string, name: string, path: string, lastOpened: string | null}`；`currentRepo` 是 `string | null`；`transcriptDirs` 是数组，每项是 `{id: string, path: string}`；`theme` ∈ `THEME_VALUES`；`density` ∈ `DENSITY_VALUES`；`pythonPath` 与 `kitPath` 是 `string | null`。
    - 未知键忽略，读出来的 `settings` 里没有它们（下次写盘自然丢掉）。
  - `save(settings)`：先按 `SETTINGS_FILE_KEYS` 的顺序拼出对象（只保留这些键），序列化成 `JSON.stringify(obj, null, 2) + "\n"`；然后 `mkdirSync(dir, {recursive:true})` → `writeFileSync(<filePath>.tmp, 数据)` → `renameSync(<filePath>.tmp, filePath)`。`renameSync` 覆盖已有的正式文件（Node 的行为已核实）。写失败时用 `unlinkSync` 删掉临时文件（忽略删除失败）后抛出错误。写出的文件里不含任何未知键。
- `normalizeSettings(raw)`：返回 `{ok:true, settings}` 或 `{ok:false}`；规则同 `load()` 里的“已知键取值不合法”判定，非法即 `ok:false`（不产副本，副本是 `load()` 的事）。
- `applyPatch(settings, patch)`：返回 `{ok:true, settings}`（新对象，不改入参）或 `{ok:false, reason}`，`reason` ∈ `bad-patch` / `unknown-id` / `current-repo`：
  - `patch` 不是普通对象（`null`、数组、其它类型）→ `bad-patch`。
  - 出现 `PATCH_KEYS` 之外的键 → `bad-patch`。
  - `theme` 不在 `THEME_VALUES`、`density` 不在 `DENSITY_VALUES`、`resetPython`/`resetKit` 不严格等于 `true`、`removeRepo`/`removeTranscriptDir` 不是字符串 → `bad-patch`。
  - `removeRepo` 的 id 不在 `settings.repos` 里，或 `removeTranscriptDir` 的 id 不在 `settings.transcriptDirs` 里 → `unknown-id`。
  - `removeRepo` 的 id 等于 `settings.currentRepo` → `current-repo`。
  - 校验顺序固定：先 `bad-patch`（形状与未知键），再 `unknown-id`（id 存在性），再 `current-repo`；任一项不合格就整体拒绝，**不改状态、不写盘**。
  - 全部合格时的应用：`theme`/`density` 覆盖；`removeRepo` 从 `repos` 里删掉该项（`currentRepo` 因为被拒过，不会指向它）；`removeTranscriptDir` 从 `transcriptDirs` 里删掉该项；`resetPython` 把 `pythonPath` 置 `null`；`resetKit` 把 `kitPath` 置 `null`。
- `addRepo(settings, repoPath)`：返回 `{ok:true, settings, id, reused}`。路径比较用 `path.resolve` 后的结果，Windows 下再转小写比较（其它平台区分大小写）；相同路径已存在 → `reused:true`、沿用原 `id`、不新增条目；否则新增 `{id, name, path, lastOpened: null}`，`name` 是 `path.basename`（去掉尾部斜杠，为空时用 `"repo"`），`id` 由 `name` 生成，撞了就依次试 `name-2`、`name-3`…。**只有 `settings.currentRepo` 为 `null` 时**才把新 id 设成 `currentRepo`。
- `addTranscriptDir(settings, dirPath)`：返回 `{ok:true, settings, id, reused}`；路径去重规则同上；id 基名是 `"dir"`，撞了依次 `"dir-2"`、`"dir-3"`…。

**`desktop/shell/src/detect.js`（校验与自动检测；不写任何文件）**

导出：
- `PYTHON_INFO_CODE`：字符串 `"import sys; print(sys.version.split()[0]); print(sys.executable); sys.exit(0 if sys.version_info >= (3, 10) else 1)"`。
- `KIT_VERSION_RE`：`/\d+\.\d+\.\d+/`。
- `runProcess(command, args, {timeoutMs = 10000})`：`spawn(command, args, {stdio:["ignore","pipe","pipe"], shell:false, windowsHide:true})`；把 stdout 与 stderr 按 utf8 收成字符串；`timeoutMs` 到点就 `child.kill()` 并返回 `{code:null, stdout, stderr, timedOut:true}`；正常结束返回 `{code, stdout, stderr, timedOut:false}`；进程起不来（ENOENT 等）返回 `{code:null, stdout:"", stderr:"", timedOut:false, error:<错误码>}`。**不得使用 `shell: true`。**
- `checkRepo(repoPath)`：只看文件系统，返回 `"ok"` / `"not-git"` / `"no-agent"`：`<repoPath>/.git` 不存在（目录或文件都不算）→ `"not-git"`；`<repoPath>/.agent` 不是目录 → `"no-agent"`；否则 `"ok"`。路径不存在时按 `"not-git"` 处理。不起子进程。
- `probePython(commandArgs, {timeoutMs = 10000, code = PYTHON_INFO_CODE})`：`commandArgs` 是数组（如 `["python3"]`、`["py","-3"]`），执行 `commandArgs + ["-c", code]`；退出码 0 且 stdout 至少两行 → `{ok:true, version: 第一行, path: 第二行}`；退出码 0 但行数不够 → `{ok:false, reason:"bad-output"}`；退出码非 0 → `{ok:false, reason:"version-too-old"}`；超时 → `{ok:false, reason:"timeout"}`；起不来 → `{ok:false, reason:"no-command"}`。
- `probeKit(pythonPath, kitDir, {timeoutMs = 10000})`：没有 `pythonPath` → `{ok:false, reason:"python-unusable"}`；否则执行 `[pythonPath, path.join(kitDir,"scripts","pi_dispatch.py"), "--version"]`，退出码 0 → `{ok:true, version: 第一个 KIT_VERSION_RE 匹配}`（stdout 与 stderr 合起来找），退出码非 0 → `{ok:false, reason:"kit-unusable"}`，超时 → `{ok:false, reason:"timeout"}`，起不来 → `{ok:false, reason:"no-command"}`；输出里找不到版本号 → `{ok:false, reason:"kit-unusable"}`。
- `detectPython({timeoutMs = 10000})`：按 `DEFAULT_PYTHON_CANDIDATES`（从 `./python.js` 只读引用）的顺序逐个 `probePython`，第一个成功就返回 `{status:"ok", source:"auto", path: 该 Python 的 sys.executable, version}`；全失败返回 `{status:"missing", source:"auto", path:"", version:""}`。
- `detectKit({pythonPath, repoPath, kitPath, timeoutMs = 10000})`：`kitPath` 非空时按 external 探测（`kitDir = kitPath`），`repoPath` 非空时按 repo 探测（`kitDir = repoPath`，脚本是 `<repoPath>/scripts/pi_dispatch.py`）；返回 `{status:"ok"|"missing", source:"repo"|"external", path, version}`，`path` 是**被验证的那个 `pi_dispatch.py` 的绝对路径**（`<kitDir>/scripts/pi_dispatch.py`），`version` 是探测到的版本串；探测失败时 `status:"missing"`、`path:""`、`version:""`。

**`desktop/shell/src/shellapi.js`（`window.themisShell` 的主进程实现）**

导出 `createShellApi(options)`，`options`：
- `store`（必填）：上面 `createSettingsStore` 的返回值。
- `chooseDirectory({title})`：`Promise<string | null>`，取消时回 `null`（系统选择框由调用方注入，本模块不碰 Electron）。
- `chooseFile({title})`：`Promise<string | null>`，取消时回 `null`。
- `confirmExternal(url)`：`Promise<boolean>`。
- `openExternal(url)`：`Promise<void>`。
- `appVersion`（字符串，缺省 `""`）、`homepage`（字符串，缺省 `"https://github.com/mrQzs/ThemisTally"`）。
- `now`（`() => Date`，缺省 `() => new Date()`）。
- `probe`（可选）：`{probePython, probeKit, detectPython, detectKit}`，测试注入用；缺省用本模块的实现。

返回对象的成员名**恰好十个**，与 `themisShell.ts` 的 `interface ThemisShell` 一致：`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`。

- 信封约定：主进程一侧一律回 `{ok:true, value}` 或 `{ok:false, reason}`，**不抛错**。`reason` 的取值集合：`bad-patch`、`unknown-id`、`current-repo`、`write-failed`、`bad-url`、`cancelled`、`open-failed`、`internal`、`not-implemented`。
- `getState()`：`{ok:true, value: ShellState}`。`ShellState` 的构造：
  - `app`：`{version: appVersion, homepage: homepage}`。
  - `settings`：只含 `ShellSettings` 的五个字段 `repos`、`currentRepo`、`transcriptDirs`、`theme`、`density`（`pythonPath` 与 `kitPath` 只留在设置文件里，**不出现在 state 里**）。
  - `currentRepoCheck`：`currentRepo` 为 `null` → `null`；否则按 id 找到仓库条目，用 `checkRepo(entry.path)` 得 `"ok"` / `"not-git"` / `"no-agent"`；id 找不到 → `null`。
  - `python`：设置里的 `pythonPath` 非空 → 用 `probePython([pythonPath])`，成功 `{status:"ok", source:"custom", path: sys.executable, version}`，失败 `{status:"missing", source:"custom", path:"", version:""}`；`pythonPath` 为空 → 用 `detectPython()`，得到 `{status, source:"auto", path, version}`。
  - `kit`：设置里的 `kitPath` 非空 → source `"external"`，用 `python.path`（没有可用 Python 时直接 `status:"missing"`）跑 `probeKit`；否则当前仓库路径可用时 source `"repo"`，`kitDir` = 仓库路径；两处 `path` 都是被验证的 `pi_dispatch.py` 的绝对路径，失败时 `status:"missing"`、`path:""`、`version:""`。
  - `service`：恒为 `{kind:"idle"}`。
  - `getState` 不起子进程以外的副作用；检测结果有缓存（见下）。
- `pickRepo()`：`{ok:true, value: PickOutcome}`。调 `chooseDirectory`；回 `null` → `{kind:"cancelled"}`；拿到路径后 `checkRepo`：不是 `"ok"` → `{kind:"rejected", problem: checkRepo 的结果（"not-git" 或 "no-agent"）, path}`，**不写盘**；是 `"ok"` → `addRepo` 存盘（写盘失败 → `{ok:false, reason:"write-failed"}`）→ `{kind:"saved", path, id, state}`，`state` 是存盘后的 `ShellState`。
- `pickPython()`：调 `chooseFile`；`null` → `{kind:"cancelled"}`；`probePython([选中路径])` 成功 → 把 `pythonPath` 设为该路径并存盘 → `{kind:"saved", path, state}`（**没有 `id` 字段**）；失败 → `{kind:"rejected", problem:"python-unusable", path}`，不写盘。
- `pickKit()`：调 `chooseDirectory`；`null` → `{kind:"cancelled"}`；先取可用 Python（设置里的 `pythonPath`，没有就自动检测一次）；没有可用 Python → `{kind:"rejected", problem:"python-unusable", path}`；`probeKit(python, 选中目录)` 成功 → `kitPath` 设为该目录并存盘 → `{kind:"saved", path, state}`；失败 → `{kind:"rejected", problem:"kit-unusable", path}`，不写盘。
- `pickTranscriptDir()`：调 `chooseDirectory`；`null` → `{kind:"cancelled"}`；`addTranscriptDir` 后存盘 → `{kind:"saved", path, id, state}`；路径已存在时沿用原 id（`reused`），条目不重复。这一项**不会**返回 `rejected`。
- `saveSettings(patch)`：`applyPatch` 不合格 → `{ok:false, reason}`（`bad-patch` / `unknown-id` / `current-repo`），状态与文件都不变；合格 → 应用并写盘（写盘失败 → `{ok:false, reason:"write-failed"}`，且**内存状态也要回滚成补丁前的值**）→ `{ok:true, value: ShellState}`。
- `openExternal(url)`：`isExternalUrl(url)`（复用 `./hostcheck.js`）为假 → `{ok:false, reason:"bad-url"}`；`confirmExternal(url)` 回假 → `{ok:false, reason:"cancelled"}`，抛错 → `{ok:false, reason:"internal"}`；`openExternal(url)` 抛错 → `{ok:false, reason:"open-failed"}`；成功 → `{ok:true, value: null}`。
- `startService(repo)` 与 `restartService()`：占位，回 `{ok:false, reason:"not-implemented"}`，不起服务。
- `on(event, listener)`：占位，**同步**返回一个空的退订函数 `() => {}`；不调用 listener，不抛错，不返回信封（页面挂载时就会调它，抛错会让页面崩）。

### 正常输入
- 设置文件不存在 → 用缺省设置起来，`getState` 给出缺省的 `settings`。
- 用户在选择框里选了一个合法的 Git 仓库（有 `.git` 且 `.agent` 是目录）→ `pickRepo` 存盘并回 `{kind:"saved", path, id, state}`；`currentRepo` 为空时它被设成这个仓库。
- 用户选了一个能跑且 ≥ 3.10 的 Python → `pickPython` 存 `pythonPath` 并回 `{kind:"saved", path, state}`。
- 用户选的 ThemisTally 目录里有能跑通的 `scripts/pi_dispatch.py` → `pickKit` 存 `kitPath` 并回 `{kind:"saved", path, state}`。
- `saveSettings({theme:"dark"})` → 主题改成 dark，写盘，回新的 `ShellState`。
- `openExternal("https://example.com")` 且用户确认 → `{ok:true, value:null}`。

### 边界输入
- 设置文件是坏 JSON、顶层不是对象、或已知键取值非法（例如 `theme:"neon"`）→ 整份文件当坏文件：用缺省设置，坏文件另存副本，副本不覆盖已有同名文件。
- 设置文件里有未知键 → 忽略，写盘时丢掉。
- `saveSettings` 收到未列出的键、路径值、非对象的补丁、`removeRepo` 指向不存在的 id、`removeTranscriptDir` 指向不存在的 id、`removeRepo` 指向当前仓库 → 整体拒绝，`reason` 分别是 `bad-patch` / `bad-patch` / `bad-patch` / `unknown-id` / `unknown-id` / `current-repo`；拒绝后设置文件字节不变。
- 选择框取消 → `{kind:"cancelled"}`，不写盘。
- 选中的仓库不是 Git 仓库 → `{kind:"rejected", problem:"not-git", path}`；没有 `.agent` 目录 → `{kind:"rejected", problem:"no-agent", path}`；都不写盘。
- 选中的 Python 跑不起来或版本低于 3.10 → `{kind:"rejected", problem:"python-unusable", path}`；选中的 kit 目录没有可用的 Python → `{kind:"rejected", problem:"python-unusable", path}`；kit 的 `pi_dispatch.py --version` 跑不通 → `{kind:"rejected", problem:"kit-unusable", path}`。
- `openExternal` 收到非 http/https、带控制字符或带首尾空白的地址 → `{ok:false, reason:"bad-url"}`。
- 子进程超时（10 秒）→ 探测回失败原因（`timeout`），不挂住。
- 仓库路径不存在 → `checkRepo` 回 `"not-git"`。

### 错误与重试
- 主进程一侧不抛错：所有失败都变成 `{ok:false, reason}` 或 `PickOutcome` 的 `rejected`。
- 写盘失败（目录不可写等）→ `{ok:false, reason:"write-failed"}`，并把内存状态回滚成写盘前的值。
- 子进程超时、起不来、退出码非 0 都按失败处理，不重试（自动检测按候选顺序各试一次）。
- 探测类的失败原因词（模块内部用）：`version-too-old`、`bad-output`、`timeout`、`no-command`、`python-unusable`、`kit-unusable`。

### 并发、取消与状态变化
- `createShellApi` 内部持有一份设置状态，第一次用到时从 `store.load()` 读入；每次写盘成功后更新这份内存状态。
- 检测结果（Python 与 kit）缓存在 `createShellApi` 内部：`getState` 不重复起子进程；`pickPython`、`pickKit`、`saveSettings`（含 `resetPython` / `resetKit`）之后清掉缓存，下次 `getState` 重新探测。`pickRepo` 之后要重算 `currentRepoCheck`。
- 选择框取消就是取消：不写盘、不改状态。
- 本片不涉及真 Electron 窗口，无并发建窗问题。

### 兼容性
- 设置文件是 JSON，键固定为 `SETTINGS_FILE_KEYS`；`version` 固定为 `1`。
- 不存凭据、不存控制令牌：设置模块根本不接收令牌字段。
- `desktop/web/src/shellpages/themisShell.ts` 的形状是唯一基准，本片不改它；形状比对测试读它做比对。
- 现有外壳行为不变：带 `--repo/--kit/--assets` 启动的路径、`parseShellArgs`、`runShell`、`preload.js` 的 `themisHost`、IPC 通道表都不动。

## Steps
1. 读 `desktop/shell/src/python.js`、`src/hostcheck.js`、`src/host.js`、`desktop/shell/package.json`、`desktop/web/src/shellpages/themisShell.ts`、`tests/test_gate_t025_baseline.py` 与 `tests/test_gate_t026_baseline.py` 的静态扫描段，确认签名与门禁事实与本合同的「Repository facts」一致；不一致就停下报告，不要改门禁。
2. 写 `desktop/shell/src/settings.js`：`DEFAULT_SETTINGS`、`SETTINGS_FILE_KEYS`、`THEME_VALUES`、`DENSITY_VALUES`、`PATCH_KEYS`、`createSettingsStore`、`normalizeSettings`、`applyPatch`、`addRepo`、`addTranscriptDir`，行为照「Behavior contract」。写盘只用 `mkdirSync`、`writeFileSync`、`renameSync`、`unlinkSync` 四个（这是 `desktop/shell` 里唯一允许出现写文件函数的文件；`rmSync(`、`writeFile(`、`fs.promises.writeFile(` 一律不许出现，注释里也不许写这些词形）。坏文件副本用 `readFileSync` 读原始字节再 `writeFileSync` 写副本。
3. 写 `desktop/shell/src/detect.js`：`PYTHON_INFO_CODE`、`KIT_VERSION_RE`、`runProcess`、`checkRepo`、`probePython`、`probeKit`、`detectPython`、`detectKit`；候选顺序从 `./python.js` 只读引用 `DEFAULT_PYTHON_CANDIDATES`（不改 `python.js`）；子进程一律 `shell:false`、`windowsHide:true`、10 秒时限。
4. 写 `desktop/shell/src/shellapi.js`：`createShellApi(options)` 返回十个成员，行为照「Behavior contract」；不 `require("electron")`，不引入 `dialog`、`shell.openExternal`、`showItemInFolder`、`Notification` 这些词（连注释里也不要出现）。
5. 写四个测试文件（`tests/settings.test.js`、`tests/detect.test.js`、`tests/shellapi.test.js`、`tests/shellshape.test.js`）：
   - `settings.test.js` 覆盖：文件不存在用缺省；坏 JSON 与坏取值走缺省并另存副本；副本同名不覆盖（追加 `-2`）；未知键被忽略且写盘后消失；写出的文件只有 `SETTINGS_FILE_KEYS` 里的键；原子写（先写 `.tmp` 再 `renameSync`）；补丁的六类拒绝（非对象、未知键、错值、id 不存在、移除当前仓库、路径值）且拒绝后文件字节不变；仓库与目录的 id 去重与 `-2`、`-3`；`currentRepo` 只在为 `null` 时被设置。
   - `detect.test.js` 覆盖：仓库检查的三个结果（`.git` 是目录、`.git` 是文件、缺 `.agent`、两者都缺）；Python 探测（正常、版本过低、缺文件、挂住超时）；kit 探测（正常取版本号、`--version` 跑不通、脚本缺失、没有 Python）；子进程不经 shell（断言 spawn 选项里 `shell` 不是 `true`）；自动检测按 `python3 → python → py -3` 的顺序。子进程替身放在 `tests/fixtures/` 下，用 `process.execPath` 运行，文件名不以 `.test.js` 结尾（例如 `fake-python-ok.js`、`fake-python-old.js`、`fake-python-hang.js`、`fake-kit-version.js`）；需要共用辅助代码也放 `tests/fixtures/` 下。
   - `shellapi.test.js` 覆盖：四个选择器各自的取消、保存、被拒；保存时写盘，被拒与取消不写盘；`saveSettings` 的拒绝路径与未列出的键；`openExternal` 的三种原因；检测缓存在选择与两个 reset 之后刷新；三个占位成员的形状（`startService`/`restartService` 回 `not-implemented`，`on` 返回退订函数且不抛错）。
   - `shellshape.test.js`（形状比对）：读 `desktop/web/src/shellpages/themisShell.ts`（路径 `path.resolve(__dirname, "../../web/src/shellpages/themisShell.ts")`），用正则取出 `ThemisShell` 的成员名、`ShellState` / `ShellSettings` / `RepoEntry` / `TranscriptDirEntry` / `SettingsPatch` 的字段名与 `RepoCheck` / `PickProblem` / `ServiceState` / `theme` / `density` 的字面量取值，然后与真实实现比对：
     - `createShellApi` 返回对象的键集合 == 类型文件里 `ThemisShell` 的成员名集合（十个，逐名相等）；
     - `getState()` 返回值的键 == `ShellState` 的字段名；`value.app` 的键 == `app` 的内联字段名；`value.settings` 的键 == `ShellSettings` 的字段名；`value.settings.repos[0]` 的键 == `RepoEntry` 的字段名；`value.settings.transcriptDirs[0]` 的键 == `TranscriptDirEntry` 的字段名；`value.python` 与 `value.kit` 的键 == 各自内联字段名；`value.service.kind` ∈ `ServiceState` 的取值；`value.currentRepoCheck` ∈ `RepoCheck` 的取值 ∪ `{null}`；`value.settings.theme` / `density` ∈ 类型文件里的对应字面量；
     - 选择器被拒时的 `problem` ∈ `PickProblem` 的取值；
     - `settings.js` 导出的 `PATCH_KEYS` == 类型文件里 `SettingsPatch` 的字段名；`THEME_VALUES` / `DENSITY_VALUES` == 类型文件里 `theme` / `density` 的字面量；`SETTINGS_FILE_KEYS` 包含 `ShellSettings` 的全部字段名；
     - 解析规则写死：接口块按 `export interface <名字> {` 到行首 `}` 之间逐行取 `^\s*(\w+)(\?)?\s*:` 的字段名；类型别名按 `export type <名字> =` 到行尾 `;` 取其中所有 `'…'` 字面量；内联对象类型（如 `app: { version: string; homepage: string };`）在该行里再取一次 `(\w+)\s*:`；解析不到预期的块时**断言失败**（格式变了要报警，不许静默通过）。
     - 测试里**不许另抄一份键表**：期望值只能来自类型文件与实现模块的导出，不许在测试里硬写第二份字段清单。
6. 改 `desktop/shell/package.json` 的 `scripts.test`：把四个新测试文件按现有顺序追加到文件清单末尾（`--test-reporter=tap` 必须在文件清单之前，保持不变）；不改 `devDependencies`、不改 `package-lock.json`。
7. 改 `desktop/shell/README.md`：新增一节「设置与校验」，写清设置文件位置（`<userData>/settings.json`，目录由调用方注入）、文件里的字段、坏文件怎么处理（用缺省设置 + 另存副本，副本不覆盖）、三项校验的判据（仓库看 `.git` 与 `.agent`、Python ≥ 3.10、kit 跑 `pi_dispatch.py --version`）、子进程 10 秒时限与不经 shell、设置文件里不存凭据与控制令牌。**原有的所有字样保留**（`npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、退出码表、`install.js`、`node_modules/electron`、冒烟、10 秒、30 秒一字不动）；本片不写启动流程与外壳页的使用说明（那是 T028b）。
8. 运行 Validation commands 里与改动相关的检查（`npm test` 与两条 pytest），记录命令与结果；写执行报告。

## Validation commands

- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass [1-9][0-9]*`，不得出现：`# fail [1-9]`
- V02（必要）：`python -m pytest tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t028_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配:`\d+ passed``
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配:`\d+ passed``

## Definition of done
- D01：设置存盘可用：文件不存在用缺省；坏 JSON 或已知键取值非法时用缺省并把坏文件另存一份带 UTC 时刻的副本且不覆盖已有副本；未知键被忽略并在写盘时丢掉；写盘是 `mkdirSync` → `writeFileSync` 临时文件 → `renameSync` 替换，写出的文件只有声明的键；证据：V01；目的：设置文件坏了不能让外壳起不来，也不能悄悄覆盖用户的旧文件。
- D02：`saveSettings` 只认 `theme`、`density`、`removeRepo`、`removeTranscriptDir`、`resetPython`、`resetKit` 六键，整包合格才应用并写盘，任一项不合格整体拒绝（`bad-patch` / `unknown-id` / `current-repo`）且文件字节不变；证据：V01；目的：设置接口不接受任何路径，坏补丁不能把已有设置写坏。
- D03：三项校验与自动检测成立：仓库只看文件系统（`.git` 存在且 `.agent` 是目录），Python 要能跑且 ≥ 3.10，kit 要能跑 `<kit>/scripts/pi_dispatch.py --version` 并取到版本号；子进程带 10 秒时限、`shell:false`、`windowsHide:true`；自动检测按 `python3 → python → py -3` 的顺序；证据：V01；目的：起服务前必须先确认这三样可用，超时不能把外壳挂死。
- D04：四个选择器各有取消、保存、被拒三种结果；只有保存才写盘，被拒与取消不写盘；`pickRepo` 只在 `currentRepo` 为空时设当前仓库；`pickKit` 没有可用 Python 时回 `python-unusable`；`pickTranscriptDir` 不回 `rejected`；证据：V01；目的：路径只能来自系统选择框，校验不过的路径不能进设置。
- D05：返回值形状与 `desktop/web/src/shellpages/themisShell.ts` 逐字段一致，由读该类型文件的比对测试钉住（测试里不另抄键表）；证据：V01；目的：前端拿到的字段名与取值必须就是类型文件里写的那一套，类型文件变了测试要红。
- D06：`openExternal` 复用 `isExternalUrl` 与注入的确认框，失败原因是 `bad-url` / `cancelled` / `open-failed`；证据：V01；目的：外壳页不能打开非 http/https 的地址。
- D07：现有 `npm test` 全过、T025/T026 门禁与全量门禁回归全过，本片的新门禁基线测试全过；既有测试一条没删没改；证据：V01、V02、G01、R01；目的：外壳页的数据层不能碰坏 T025/T026 已经钉住的行为。
- D08：所有改动都在允许集合内（只改 `desktop/shell/package.json` 与 `desktop/shell/README.md`，只新增本片点名的文件与 `tests/fixtures/**`），`desktop/web`、`ts/`、门禁测试、`main.js`、`preload.js` 与冻结的 `src/*.js` 一字未动；证据：scope。
- D09：README 新增「设置与校验」一节且原有字样全保留；`package.json` 只改了 `scripts.test`（依赖与锁文件未动）；证据：V01、V02、review；目的：文档与门禁要求的字样不许被这次改动抹掉。
- D10：任务书列出的过渡断言与两条前端过渡用例一条也没推翻（`desktop/web/**` 未改）；证据：V01、R01、scope；目的：本片只加不改。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `python.js` 的候选变了、`themisShell.ts` 的形状变了、门禁的收窄没有生效）。
- 必须修改允许范围之外的文件才能继续（包括必须改 `main.js`、`preload.js`、`desktop/web` 或门禁测试）。
- 需要新增或升级依赖、联网、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- `desktop/web/src/shellpages/themisShell.ts` 被别的任务改动导致形状比对测试红：不要改那份类型文件，停下并在报告里写明（这是预期的报警）。
- 达到单轮时限（3600 秒）。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200
- cost_budget: 12 USD（只统计；调度器强制的是次数与墙钟）
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：调查与读门禁 10 分钟；写三个模块 25 分钟；写四个测试与夹具 20 分钟；改 package.json 与 README 5 分钟；跑检查与写报告 10 分钟；总计 70 分钟，单轮上限 60 分钟，模块与测试里可并行的部分提前做。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不改门禁测试（`tests/test_gate_t028_*.py` 等）、不改 `desktop/web/**`、`ts/**`、`scripts/**`。
- 不在 `desktop/shell/src/settings.js` 之外的任何文件里出现写文件的函数调用（含注释里的词形）；不用 `rmSync(`、`writeFile(`、`fs.promises.writeFile(` 绕门禁。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261112T131951815813Z-owner-1188f2：

> 两件事都拍板，另答复转告的事。
>
> 1. 门禁：照规划第 6 节的建议收窄，已提交 0592200，T028 的基线已挪到它（314227e → 0592200）。T025、T026 门禁的 test_s03_static_scan 现在是：
>    - desktop/shell/src/settings.js 里许用 writeFileSync、renameSync、mkdirSync、unlinkSync 四个；
>    - 别的写函数（writeFile、appendFile、appendFileSync、mkdir、rm、rmSync、unlink、rename）在 settings.js 里照旧不许，异步的 fs.promises.writeFile 也命中；
>    - 别的文件照旧一个都不许；其余禁令没动。
>    所以写盘只能放在 src/settings.js，文件名就定这个。站主在临时工作区里成对核过：settings.js 里用这四个，两条都过；同样四个放进别的 src 文件、settings.js 里用 rmSync、settings.js 里用异步 writeFile，两条都红。
> 2. 拆片：确认。T028 只做数据层（规划第 1 节“本片”：设置存盘、三项校验与自动检测、七个真实方法的主进程实现、与 themisShell.ts 的形状比对；纯模块，node --test 覆盖，不碰 main.js）。后一半（协议、外壳页专用 preload、IPC 与来源检查、无参数启动、main.js 接线、README 与手工冒烟）等 T028 落地后由站主另登记一个主任务，不在 T028 里做。attempt 预算 2，花费上限照旧 12 美元。规划第 9 节那几条 Electron 的事实留给后一半的规划核实。
> 3. 转告 T027：不用转。T027 这一片的范围是 src/live/、api.ts、common-readers、tasks 的数据文件与前端测试，不含 src/shellpages/。站主审它的合同时会看 Scope 里有没有 themisShell.ts。本片的比对测试若因为那份文件变了而红，发“阻塞”给站主。

## Rework（返工第 1 轮，内核追加）

- 基线 `1a2a57de5151123ce4cf6809bcd6021cafe60b6d` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

1)（执行端·src/detect.js）probePython 必须认合同写明的 code 选项：合同的 Behavior contract 明写 `probePython(commandArgs, {timeoutMs = 10000, code = PYTHON_INFO_CODE})`，实现把 code 写死成 PYTHON_INFO_CODE，调用方按合同传 {code: ...} 时被静默忽略（detect.js:105 的 `[...commandArgs, "-c", PYTHON_INFO_CODE]`）。要求：读 options.code，缺省仍是 PYTHON_INFO_CODE，`-c` 后面传这个 code；补一条断言自定义 code 到达 argv 的测试；默认路径不许变（门禁探针断言 args[1] === PYTHON_INFO_CODE 仍要过）。
2)（执行端·desktop/shell/tests/shellapi.test.js）补 openExternal 的用例：合同 Step 5 点名 shellapi.test.js 要覆盖 openExternal 的三种原因，候选里一条都没有（harness 里的 confirmExternal/openExternal 钩子从没被调用过，只有成员名清单里出现过这个名字）；D06 的证据写的是 V01，而 V01 现在对 openExternal 什么也证明不了。行为本身我逐行读过是对的，且门禁探针 test_p06_probe_openexternal 覆盖了它，但执行端自己的回归套件里必须要有：非 http/https、带控制字符、带首尾空白 → bad-url 且不进确认框；确认框回 false → cancelled；确认框抛错 → internal；openExternal 抛错 → open-failed；成功 → {ok:true, value:null}。
3)（执行端·desktop/shell/tests/shellapi.test.js）补 saveSettings({resetKit: true}) 之后 kit 缓存刷新的断言：合同 Step 5 点名「检测缓存在选择与两个 reset 之后刷新」，候选只测了 pickPython/pickKit 与 saveSettings(resetPython)，resetKit 这条没有任何断言（门禁探针也只测了 resetPython）。实现是对的（saveSettings 成功后无条件 dropCache），但仓库里没有断言钉住它。
