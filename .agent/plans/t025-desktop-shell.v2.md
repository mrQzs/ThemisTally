# TASK: t025-desktop-shell

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: a99cb77ad204d657065ffb3881b1b88a8775be92
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
新建 npm 包 `desktop/shell`（与 `desktop/web` 并列），做桌面外壳的最小骨架：找 Python → 校验命令行参数 → 起本机服务并校验握手 → 开一个安全设置的窗口 → 关窗口就以 stdin 的 EOF 结束服务并按约定的退出码退出。

## Non-goals
- 不做外壳页（首次启动、设置、服务状态与恢复）、托盘、通知、在资源管理器中显示、单实例、多仓库切换。
- 不做宿主接口与 preload、不做凭据小窗口；控制令牌本片只留在主进程内存里，不使用、不传给任何页面。
- 不做 Electron Fuses、electron-builder 与安装包、自动更新、外部链接交给系统浏览器。
- 不起真 Electron 窗口的端到端测试；`main.js` 没有自动化测试（靠纯模块与 README 的手工冒烟）。
- 不改本机服务（`ts/packages/ui`）、不改 `desktop/web`、`docs/**`、`scripts/**`、调度器与内核文件；服务的行为与本片的要求对不上时写进执行报告，不自己改服务。
- 不新增除 `electron` 以外的任何依赖；不新增 TypeScript、Vitest、测试框架。

## Repository facts
- 入口（本片新建）：`desktop/shell/main.js` 是 Electron 主进程入口，也是**唯一**允许 `require('electron')` 的文件；纯逻辑拆在 `desktop/shell/src/` 的六个模块里（见「Behavior contract」），测试在 `desktop/shell/tests/`。
- 服务侧握手行（只读参照，`ts/packages/ui/src/server.ts:196-205`）：stdout 写**一行** JSON，字段与次序是 `themis_ui`（1）、`bootstrap`（`${origin}/bootstrap/${nonce}`）、`origin`（`http://127.0.0.1:<port>`）、`control`、`pid`（TS 进程自己的 pid），以 `\n` 结尾，之后不再向 stdout 写任何内容。
- 服务的退出（只读参照）：`server.ts:242` 读 stdin 的 EOF 就 `shutdown(EXIT_OK)`；`server.ts:74` 的 `WATCHDOG_MS = 3000` 是关停开始后的看门狗（`server.ts:224`）；`ts/packages/ui/src/lifecycle.ts:103` 是 `watchStdinEof`。
- 启动器与参数（只读参照，`scripts/pi_dispatch.py`）：`--repo` 是**顶层**选项（`:8626`），必须写在子命令之前；`ui` 的选项是 `--desktop`、`--assets`、`--transcript`（可重复）、`--idle-timeout`（`:8727-8731`）；`cmd_ui`（`:7868`）经 `run_handoff` 转交给 TS。
- Python 的查找顺序（只读参照，`scripts/dispatch-pi.sh:9-19` 与设计文档 §2.7，`docs/themis-tally-3.0-桌面端.md:241`）：依次试 `python3`、`python`、`py -3`，每个都试运行版本检查；本片的版本门槛是 **3.10**（设计文档的宿主接口表）。
- 窗口安全设置（只读参照，`docs/themis-tally-3.0-桌面端.md:638` 与 §10.4 的 E1，`:948`）：`contextIsolation: true`、`sandbox: true`、`nodeIntegration: false`、`webSecurity: true`、`allowRunningInsecureContent: false`、不开 `webviewTag`；不配 preload；`setWindowOpenHandler` 一律拒绝；`will-navigate` 只允许服务自己的 origin；权限请求与权限检查一律拒绝；应用不向 127.0.0.1 以外的任何地址发请求。
- 服务行为（只读参照）：前端资源目录不存在或没有 `--desktop` 时服务以 **2** 退出（`ts/packages/ui/src/main.ts:41-45`）；空闲 1800 秒后服务以 **0** 退出（`desktop/web` 现在是夹具，页面加载完不再发请求）——外壳照「服务意外退出」处理，以 1 退出，这是本片预期的行为。
- 工具链与锁文件：门禁机 Node 24.19.0（`.agent/environment.md`）；`desktop/web` 用 npm + Vite 5 + Vitest 2（`desktop/web/package.json`），本片**没有** TypeScript 与 Vitest，测试用 Node 自带的 `node --test`；Node 24.19.0 的 `node --test` **默认 reporter 是 `spec`，只输出 `ℹ pass N`，不含 `# pass`**；加 `--test-reporter=tap` 才输出 `# tests N` / `# pass N` / `# fail N`（执行端 attempt-001 的 V01.log 实测 `# tests 55` / `# pass 55`）——所以本片的 `scripts.test` 必须带这个开关，V01 的 `# pass [1-9]\d*` 才判得过；`.gitignore:15-16` 已有 `desktop/**/node_modules/` 与 `desktop/**/dist/`，`node_modules` 与 `dist` 不提交，锁文件提交。
- 依赖事实（内核已核实，可当事实用）：`electron@44.9.0`，MIT，2026-10-17T05:50:07.885Z 发布（是至少两周前发布的稳定版里最新的一个）；它的 `package.json` **没有 scripts**（没有 postinstall），所以 `npm ci` 不下载 Electron 本体，单元测试不能 `require('electron')`；`engines.node >= 22.12.0`；`main` 是 `index.js`、`bin` 有 `electron: cli.js` 与 `install-electron: install.js`；直接依赖 `@types/node ^24.9.0`、`@electron/get ^5.0.0`、`@electron-internal/extract-zip ^1.0.1`（这三个会进锁文件，不算新增直接依赖）。
- 基线检查：基线上 `desktop/shell` 不存在；`tests/test_gate_t001_baseline.py` … `tests/test_gate_t024_baseline.py` 全过（本片的回归检查 R01 就是它们）；本片的门禁 `tests/test_gate_t025_baseline.py` 已锁定（基线 3fa66038309dae08a18594d518b7462591b295bd，11 条用例：5 条静态 + 6 条探针），它要求 `scripts.test` 含子串 `node --test`、`tests/` 下每个 `*.test.js` 都被 `scripts.test` 列出、夹具目录里没有 `*.test.js`；`PROBE_CORE` 用假 spawn（第一个参数收**完整 command**），`PROBE_SERVICE` 用真 spawn。

## Scope
- allowed_modified_files: 无
- allowed_new_files:
  - desktop/shell/package.json
  - desktop/shell/package-lock.json
  - desktop/shell/README.md
  - desktop/shell/main.js
  - desktop/shell/src/args.js
  - desktop/shell/src/python.js
  - desktop/shell/src/handshake.js
  - desktop/shell/src/service.js
  - desktop/shell/src/window.js
  - desktop/shell/src/core.js
  - desktop/shell/tests/args.test.js
  - desktop/shell/tests/package.test.js
  - desktop/shell/tests/python.test.js
  - desktop/shell/tests/handshake.test.js
  - desktop/shell/tests/service.test.js
  - desktop/shell/tests/window.test.js
  - desktop/shell/tests/core.test.js
  - desktop/shell/tests/fixtures/fake-python-ok.js
  - desktop/shell/tests/fixtures/fake-python-old.js
  - desktop/shell/tests/fixtures/fake-python-fail.js
  - desktop/shell/tests/fixtures/fake-python-hang.js
  - desktop/shell/tests/fixtures/fake-service.js
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t025_*.py
  - tests/**
  - desktop/web/**
  - ts/**
  - scripts/**
  - docs/**
  - .agent/**
  - AGENTS.md
  - CLAUDE.md
- dependency_changes: allowed（只允许在**新建**的 `desktop/shell/package.json` 与 `desktop/shell/package-lock.json` 里加 `electron@44.9.0` 这一个 devDependency；`desktop/web` 的 `package.json` 与 `package-lock.json` 一个字节都不许动；别的包一律不加依赖）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 静态扫描范围（门禁与执行端都照这个范围扫）：`desktop/shell/main.js`、`desktop/shell/src/**`、`desktop/shell/tests/**`。`README.md` 与 `package.json` 不在扫描范围内（README 里可以解释为什么不配 preload、为什么不带 `persist:`）。

## Behavior contract
- 正常输入：`node_modules/.bin/electron . --repo <仓库> --kit <ThemisTally 目录> --assets <desktop/web 的构建产物>` 起外壳；外壳找 Python、起服务、读握手、开窗口；关窗口 → 关 stdin → 服务以 0 退出 → 外壳以 0 退出。
- 边界输入：缺必需参数、路径不对、Python 版本太旧或不存在、握手字段缺失或 origin 不对、握手超时、服务在握手前退出、服务意外退出、关窗口后服务赖着不走——每一种都有确定的退出码与 stderr 说明，见下面各条。
- 错误与重试：本片没有重试；每种失败都是「写一行 stderr（以 `ERROR: ` 开头）→ 结束子进程 → 以约定的退出码退出」。
- 并发、取消与状态变化：一次只起一个服务；关窗口是唯一的取消信号（关 stdin 写端 → 服务读到 EOF 自己退出 → 宽限 10 秒后仍未退出才 kill）；服务意外退出时反过来关窗口。握手之后不再读、不记服务的 stdout 内容。
- 兼容性：不改任何既有接口、既有文件与既有测试；`desktop/web` 与 `ts/**` 一字不动。

### 一、包与依赖（`desktop/shell/package.json`、`package-lock.json`）

- `package.json`：`name` 为 `themistally-desktop-shell`；`private: true`；`version: "0.0.0"`；`type: "commonjs"`；`main: "main.js"`；`scripts` 有两个：
  - `test`：`node --test --test-reporter=tap tests/args.test.js tests/package.test.js tests/python.test.js tests/handshake.test.js tests/service.test.js tests/window.test.js tests/core.test.js`
  - `start`：`electron .`
  - `scripts.test` **必须带 `--test-reporter=tap`**：门禁机 Node 24.19.0 的 `node --test` 默认 reporter 是 `spec`，只输出 `ℹ pass N`，**不含** `# pass`；V01 按 `# pass [1-9]\d*` 判定，不带这个开关就必然失败。`tap` reporter 输出 `# tests N` / `# pass N` / `# fail N`，正好满足 V01。开关写在文件清单**之前**，整条命令照抄上面那一行，不许改写。
  - `scripts.test` **必须显式列出 `tests/` 下的每一个 `*.test.js`**（Node 的默认匹配有把 `tests/fixtures/` 里的夹具当测试文件执行的风险，显式列表消除它）；以后新增测试文件要同步加进 `scripts.test`。
- `devDependencies` **只有** `{"electron": "44.9.0"}`（精确版本，不带 `^`、`~` 或任何范围）；`dependencies` 不存在或为空对象。
- 锁文件用 `npm install --save-dev --save-exact electron@44.9.0` 在 `desktop/shell` 下生成（本片唯一需要联网的动作，授权动作里有 `network`）；锁文件里 `packages[""].devDependencies.electron` 是 `44.9.0`，`packages["node_modules/electron"].version` 是 `44.9.0`。
- `node_modules` 不提交（`.gitignore` 已覆盖）。

### 二、命令行参数（`desktop/shell/src/args.js`）

- 导出 `parseShellArgs(argv)`，返回 `{ ok: true, value }` 或 `{ ok: false, error }`。
- 用 `node:util` 的 `parseArgs`，`strict: true`、`allowPositionals: false`；选项：`--repo`（字符串）、`--kit`（字符串）、`--assets`（字符串）、`--python`（字符串）、`--transcript`（字符串，可重复）。
- 必需：`--repo`、`--kit`、`--assets`。可选：`--python`、`--transcript`（可给多个，按给出的顺序原样保留）。
- 校验（失败一律 `{ ok: false, error }`，`error` 是中文说明，不含令牌之类的秘密）：
  - 缺必需项：`缺少必需参数：--repo`（缺多个时用「、」连接，按 `--repo`、`--kit`、`--assets` 的次序）；
  - 未知选项：`未知参数：--foo`；
  - 多余的位置参数：`不接受位置参数：xxx`；
  - `--repo` 不是目录：`--repo 不是目录：<绝对路径>`；
  - `--kit` 不是目录：`--kit 不是目录：<绝对路径>`；
  - `--kit` 下没有 `scripts/pi_dispatch.py`：`--kit 下没有 scripts/pi_dispatch.py：<绝对路径>`；
  - `--assets` 不是目录：`--assets 不是目录：<绝对路径>`；
  - `--assets` 下没有 `index.html`：`--assets 下没有 index.html：<绝对路径>`。
- 成功时的 `value`：`repo`、`kit`、`assets` 是**绝对路径**（`path.resolve` 之后）；`python` 是原样字符串（命令名或路径都可以，`null` 表示没给）；`transcripts` 是原样字符串数组（不检查存在、不转绝对路径）。
- 参数解析是纯逻辑，不起进程、不读环境。

### 三、找 Python（`desktop/shell/src/python.js`）

- 导出 `PYTHON_PROBE_CODE`、`DEFAULT_PYTHON_CANDIDATES`、`findPython(options)`。
- `PYTHON_PROBE_CODE` 恰好是：`import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)`。
- `DEFAULT_PYTHON_CANDIDATES` 恰好是：`[["python3"], ["python"], ["py", "-3"]]`（顺序照 `scripts/dispatch-pi.sh:9-19`）。
- `findPython(options)` 返回 Promise，兑现 `{ ok: true, command }`（`command` 是数组，例如 `["py", "-3"]`）或 `{ ok: false, error, tried }`（`tried` 是 `[{ command, reason }]`，`reason` 是 `命令不存在` / `退出码 N` / `超时` 这类说明）。
- 探测：起 `command + ["-c", PYTHON_PROBE_CODE]`，不经 shell，`windowsHide: true`；退出码 0 才算这个候选可用；探测的 stdout 与 stderr 一律丢弃，不打印、不转发。
- 候选按顺序试，第一个可用的就赢，不再试后面的；命令不存在（ENOENT）、退出码非 0、10 秒内没退出（超时就把子进程结束掉再继续）都算这个候选不可用。
- `options` 允许覆盖：`candidates`（候选数组）、`timeoutMs`（默认 10000）、`probe`（注入用的探测函数，签名 `(command, timeoutMs) => Promise<{ ok: boolean, reason: string }>`；测试用它替掉真的起进程）、`python`（字符串，来自 `--python`）。测试用的时限一律用毫秒参数覆盖，不等真时限。
- 给了 `--python`（即 `options.python` 有值）时，候选**只有它一个**（`[[options.python]]`），**失败不回退**到默认候选；失败时的 `error` 是 `指定的 Python 不可用：<command>`。`core` 必须把 `parseShellArgs` 得到的 `python` 传给 `findPython`（形如 `findPython({ python })`）；`python` 为 `null`/未给时走默认候选。
- 都没成功时的 `error` 是 `找不到可用的 Python（要求 ≥ 3.10）`。

### 四、握手（`desktop/shell/src/handshake.js`）

- 导出 `parseHandshake(line)`，返回 `{ ok: true, value }` 或 `{ ok: false, error }`；`value` 是 `{ themis_ui, bootstrap, origin, control, pid }`。
- 输入是第一行（末尾的 `\r` 要去掉）；多行输入只认第一行。
- 校验（`error` 是中文说明，**不回显原行，也不回显任何字段的值**）：
  - 不是 JSON 或不是 JSON 对象：`握手行不是 JSON 对象`；
  - 缺字段：`握手缺字段：control`（缺多个时用「、」连接，字段次序照 `themis_ui`、`bootstrap`、`origin`、`control`、`pid`）；
  - `themis_ui` 不是 1：`握手的协议版本不对`；
  - `origin` 不严格匹配 `^http://127\.0\.0\.1:(\d{1,5})$` 或端口不在 1–65535：`握手的 origin 不是 http://127.0.0.1:<端口>`；
  - `bootstrap` 不是合法 URL，或它的 origin 不等于 `origin`：`握手的 bootstrap 不在服务 origin 下`；
  - `control` 不是非空字符串：`握手的 control 不是非空字符串`；
  - `pid` 不是正整数：`握手的 pid 不是正整数`。
- `pid` **只校验是正整数**，不要求等于外壳起的子进程的 pid（中间隔着 Python 启动器与 TS 服务，握手里的 pid 是 TS 进程自己的）。

### 五、起服务与收服务（`desktop/shell/src/service.js`）

- 导出 `serviceCommand(options)`、`startService(options)`、`stopService(child, options)`。
- `serviceCommand({ python, kit, repo, assets, transcripts })` 返回**参数列表**（不是拼好的命令行）：
  `[...python, <kit>/scripts/pi_dispatch.py, "--repo", <repo>, "ui", "--desktop", "--assets", <assets>, ...transcripts.flatMap(t => ["--transcript", t])]`
  （`--repo` 在子命令 `ui` 之前；每个 `--transcript` 单独一项，按给出的顺序。）
- `startService({ command, timeoutMs = 30000, spawn, env })` 返回 Promise，兑现 `{ child, handshake }`：
  - `spawn(command, [], { stdio: ["pipe", "pipe", "inherit"], windowsHide: true, shell: false })`：不经 shell；stdin 是管道；stdout 是管道；**stderr 用 inherit**（启动器「TS 没装好」之类的报错要能被看到）；`env` 传下去（测试用来切换夹具的行为）。
  - **调用形状固定为 `spawn(command, [], options)`**：`command` 是**完整 argv 数组**（首元素是可执行文件，其余是参数）；注入的 `spawn` 收到的第一个参数就是这个完整数组、第二个参数恒为 `[]`；默认实现必须自己拆包，即 `child_process.spawn(command[0], command.slice(1), options)`——不许改成 `spawn(file, args, options)` 的调用形状。
  - stdin 的写端一直握着，**一个字节都不写**。
  - stdout 只解析**第一行**：读到第一个 `\n` 就把那行交给 `parseHandshake`；之后的 stdout 继续抽干但**一律丢弃、不记、不打印**（不能让子进程堵在写 stdout 上）。
  - 握手成功 → 兑现 `{ child, handshake }`；握手行不合法 → 结束子进程并以该 `error` 拒绝；30 秒内没有握手 → 结束子进程并以 `握手超时` 拒绝；子进程在握手前退出 → 立刻以 `服务在握手前退出（退出码 N）` 拒绝。
- `stopService(child, { graceMs = 10000 })` 返回 Promise，兑现 `{ exited, code, signal, killed }`：
  - 先关 stdin 的写端（结束管道），等子进程退出；退出码 0 且是正常退出 → `{ exited: true, code: 0, signal: null, killed: false }`；
  - 10 秒（`graceMs`）内没退出 → `child.kill()`，等到它真的没了为止，兑现 `{ exited: false, code: null, signal: null, killed: true }`（被信号打死时 `signal` 是信号名）；
  - 退出码非 0 → `{ exited: true, code: N, signal: null, killed: false }`。

### 六、窗口的安全设置与判定函数（`desktop/shell/src/window.js`）

- 导出 `partitionName()`、`webPreferences(partition)`、`isServiceUrl(url, origin)`。这个模块**不许** `require('electron')`。
- `partitionName()`：随机名（可用 `crypto.randomUUID()`），**不以 `persist:` 开头**，两次调用结果不同。
- `webPreferences(partition)` 返回的对象**恰好**是这十个键（多一个、少一个、松一个都算失败）：
  `contextIsolation: true`、`sandbox: true`、`nodeIntegration: false`、`webSecurity: true`、`allowRunningInsecureContent: false`、`webviewTag: false`、`nodeIntegrationInWorker: false`、`nodeIntegrationInSubFrames: false`、`spellcheck: false`、`partition: <partition>`。
  **没有 `preload` 键**（本片不配 preload）。
- `isServiceUrl(url, origin)`：用 `new URL(url)` 解析，解析失败返回 `false`；解析成功时返回 `url.origin === origin`（`about:blank`、`data:`、`javascript:`、`file:` 的 origin 是 `null`，自然为 `false`）。反例必须挡住：别的端口、`localhost`、`https`、`http://127.0.0.1:8080@evil`、`http://127.0.0.1:8080.evil.com`、非法串。

### 七、编排（`desktop/shell/src/core.js`）与 Electron 入口（`desktop/shell/main.js`）

- `core.js` 导出 `runShell({ argv, io, openWindow, spawn, env })`，返回 Promise，兑现**退出码**。
- `io` 是 `{ stdout, stderr }` 两个可写流（默认 `process.stdout` / `process.stderr`）；`openWindow` 是 `async ({ bootstrap, origin }) => { closed: Promise<void>, close: () => void }`：`closed` 在窗口关闭时兑现，`close()` 用来在服务意外退出时关掉窗口。
- 流程：
  1. `parseShellArgs(argv)` 失败 → stderr 写 `ERROR: <error>`，**不开窗口**，退出码 **2**。
  2. `findPython` 失败 → stderr 写 `ERROR: <error>`，退出码 **1**。
  3. `startService` 失败 → stderr 写 `ERROR: <error>`（子进程已由 `startService` 结束），退出码 **1**。
  4. `openWindow({ bootstrap, origin })` —— **只给引导地址与 origin，不给 `control`**。
  5. 等两件事之一：窗口关闭，或服务退出。
     - 窗口先关 → `stopService`：服务以 0 正常退出 → 退出码 **0**；服务以非 0 退出或被 kill → stderr 写 `ERROR: 服务没有以 0 正常退出`，退出码 **1**。
     - 服务先退（意外退出，含服务以 0 退出的空闲超时）→ stderr 写 `ERROR: 服务意外退出（退出码 N）`，`openWindow` 返回对象的 `close()` 关掉窗口，退出码 **1**。
- 所有写到 stdout 与 stderr 的内容都**不许**出现控制令牌、引导地址里的 nonce 或整条握手行；错误说明里也不许回显字段的值。
- `main.js`（唯一允许 `require('electron')` 的文件）：
  - 启动时 `Menu.setApplicationMenu(null)`（去掉缺省菜单里指向外部网站的链接）；
  - `app.whenReady` 之后：`session.fromPartition(partitionName())`，`setPermissionRequestHandler` 一律 `callback(false)`、`setPermissionCheckHandler` 一律返回 `false`；
  - 建 `BrowserWindow`，`webPreferences` 用第六节的结果（`partition` 是同一个分区名），窗口不配 preload；
  - `webContents.setWindowOpenHandler(() => ({ action: "deny" }))`；
  - `webContents.on("will-navigate", …)`：目标不满足 `isServiceUrl(url, origin)` 就 `event.preventDefault()`；
  - `loadURL(bootstrap)`；
  - 用户参数取法：打包后 `process.argv.slice(1)`，未打包（开发模式）`process.argv.slice(2)`（用 `app.isPackaged` 判断）；
  - `runShell` 兑现退出码后 `app.exit(code)`；
  - `main.js` 没有自动化测试（本片不要求端到端），它的选项与判定函数都由第六节的纯模块测。
- 静态禁令（扫描范围见 Scope 末条）：`src/**` 与 `main.js` 里**不许**出现 `require("electron")` 以外的 electron 引用方式之外的 `require('electron')`——即**只有 `main.js` 可以 `require('electron')`**；不许出现 `persist:`、`shell: true`；不许出现 fs 的写函数（`writeFile`、`writeFileSync`、`appendFile`、`mkdir`、`rm`、`unlink`、`rename` 等）；不许出现 `fetch`、`net.request`、`http.request`、`https.request`、`autoUpdater`、`crashReporter`、`openExternal`。

### 八、README（`desktop/shell/README.md`）

- 写清：怎么装（`npm ci`）、怎么跑（`npm start` 与参数）、参数与退出码、时限（探测 10 秒 / 握手 30 秒 / 关停 10 秒）、`electron` 本体怎么下载（`npm ci` **不会**下载 Electron 本体——44.9.0 没有 postinstall；要跑真窗口先执行 `node node_modules/electron/install.js` 下载本体并写 `path.txt`，这是 `electron@44.9.0` 的 `bin.install-electron` 指向的 `install.js`）；
- 手工冒烟步骤：kit 的 TS 要装好、`desktop/web` 要先 build（产物在 `desktop/web/dist/`），然后照参数起外壳；
- README 里的命令要跟 `package.json` 的 `scripts` 一致。

### 九、时限、退出码与不变量（汇总）

- 时限：Python 探测每个候选 10 秒；握手 30 秒；关窗口后等服务退出 10 秒（服务自带 3 秒看门狗，所以正常情况下 3 秒内就退）。三个时限在实现里都是可覆盖的毫秒参数，测试不许等真时限。
- 退出码：**0** = 正常关窗口且服务以 0 退出；**1** = 找不到 Python、握手失败或超时、服务意外退出、关窗口后服务没有以 0 正常退出；**2** = 命令行参数错（缺必需项、未知选项、位置参数、路径不对）。
- 不变量：控制令牌与引导地址不进页面、不写日志、不写磁盘；错误不回显握手行与字段值；只读 stdout 的第一行；子进程一律用参数列表、不经 shell；一次只起一个服务。

## Steps
1. **读基线**：读 `ts/packages/ui/src/server.ts`（`:74`、`:196-205`、`:224`、`:242`）、`ts/packages/ui/src/lifecycle.ts:103`、`ts/packages/ui/src/main.ts:33-45`、`scripts/pi_dispatch.py`（`:7868`、`:8626`、`:8727-8731`）、`scripts/dispatch-pi.sh:9-19`、`docs/themis-tally-3.0-桌面端.md`（`:241`、`:638`、`:749-760`、`:948`）、`.gitignore:15-16`；确认本合同的符号与形状一致，**不一致就停下并报告，不要照抄本文的行号**。
2. **包骨架**：写 `desktop/shell/package.json`（第一节的字段逐条照抄；`scripts.test` 的字面命令照抄第一节那一行，含 `--test-reporter=tap`，开关在文件清单之前）与 `.gitignore` 不动；在 `desktop/shell` 下跑 `npm install --save-dev --save-exact electron@44.9.0` 生成 `package-lock.json`（本片唯一联网的动作）；核对锁文件里 electron 是 `44.9.0`。
3. **`src/args.js`**（第二节）：`parseShellArgs` 与七条错误文案。
4. **`src/python.js`**（第三节）：探测代码、默认候选、`findPython` 与超时/ENOENT/非 0 退出三种跳过、`python` 选项只试一个且失败不回退。
5. **`src/handshake.js`**（第四节）：七条错误文案，一个字段的值都不许回显。
6. **`src/service.js`**（第五节）：`serviceCommand`（参数列表）、`startService`（只读第一行、stderr inherit、握手超时 30 秒、`spawn(command, [], options)` 的形状）、`stopService`（关 stdin → 等 10 秒 → kill）。
7. **`src/window.js`**（第六节）：`partitionName`、`webPreferences`（十个键）、`isServiceUrl`。
8. **`src/core.js`**（第七节）：编排与三种退出码；`openWindow` 只收 `{ bootstrap, origin }`；把 `parseShellArgs` 得到的 `python` 传给 `findPython`。
9. **`main.js`**（第七节）：菜单、分区与权限、窗口、新窗口拒绝、`will-navigate`、`loadURL`、`app.exit`。
10. **测试**（七份测试 + 五个夹具，见下面各文件的覆盖面）：`tests/args.test.js`、`tests/package.test.js`、`tests/python.test.js`、`tests/handshake.test.js`、`tests/service.test.js`、`tests/window.test.js`、`tests/core.test.js`；夹具 `tests/fixtures/fake-python-ok.js`（退出 0）、`fake-python-old.js`（退出 1）、`fake-python-fail.js`（退出 9009）、`fake-python-hang.js`（不退出）、`fake-service.js`（假服务：按环境变量切换行为——写一行握手 / 不写握手 / 握手前以 2 退出 / 忽略 stdin 的 EOF / 握手后再写一行带标记的内容；并把收到的 argv 写到环境变量指定的文件里）。Windows 上不经 shell 起不了 `.cmd`/`.bat`，所以假程序都是 Node 脚本，用 `[process.execPath, 脚本路径]` 当命令前缀注入。测试不许出现 skip / only / todo；时限相关的用例一律用可覆盖的毫秒参数，不等真时限。
11. **`README.md`**（第八节）。
12. **跑检查并写报告**：跑 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。
    - **两条硬规矩**：
      1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`。
      2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；测试草稿用完立刻删掉，别留在候选里。

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t025_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：600s · 期望退出码：0 · 输出须匹配：`# pass [1-9]\d*`
- V02（必要）：`npm ci --no-audit --no-fund` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`added [1-9]\d* packages?`

## Definition of done
- D01：`desktop/shell` 是一个新的 npm 包，`package.json` 的 `private` 为真、`main` 是 `main.js`、`type` 是 `commonjs`，`devDependencies` **只有** `electron` 且值恰好是 `44.9.0`（没有 `^`、`~` 或任何范围），没有 `dependencies`；`package-lock.json` 已提交，里面 electron 是 44.9.0；`scripts.test` 显式列出了 `tests/` 下的每一个 `*.test.js`，并且带 `--test-reporter=tap`（Node 24 默认 spec reporter 的输出不含 `# pass`，不带这个开关 V01 必失败）；证据：V01、V02、G01；目的：依赖与测试入口固定下来，后面的门禁探针与执行端都照它跑。
- D02：`parseShellArgs` 照第二节工作：三个必需项缺一即报错、未知选项与位置参数报错、`repo`/`kit`/`assets` 三种路径不对各有自己的说明、`kit` 下缺 `scripts/pi_dispatch.py` 与 `assets` 下缺 `index.html` 各自报错、多个 `--transcript` 按给定顺序保留、`repo`/`kit`/`assets` 是绝对路径、`--python` 原样透传；证据：V01；目的：参数错时不许起进程、不许开窗口。
- D03：找 Python 照第三节工作：候选顺序恰好是 `python3`、`python`、`py -3`；探测代码的版本门槛是 3.10；第一个可用的候选就赢；命令不存在、退出码非 0、超时三种都算不可用且超时会把子进程结束掉；给了 `--python` 时只试它一个、失败不回退；`findPython` 的时限是可覆盖的毫秒参数；证据：V01；目的：Windows 上 `python3` 可能是应用商店的占位程序，必须试运行而不是只看命令在不在。
- D04：握手照第四节工作：只认第一行；五个字段缺一即报错；`origin` 必须严格是 `http://127.0.0.1:<端口>`；`bootstrap` 必须在同一个 origin 下；`control` 是非空字符串；`pid` 只校验是正整数（不要求等于子进程 pid）；**所有错误说明都不含握手行、不含任何字段的值**；证据：V01；目的：握手是外壳与服务之间唯一的凭据面，不能因为报错把令牌漏出去。
- D05：服务命令行是参数列表：`[...python, <kit>/scripts/pi_dispatch.py, "--repo", <repo>, "ui", "--desktop", "--assets", <assets>, ...("--transcript", t)…]`，不经 shell，参数里的空格、`&`、`"`、`%` 原样到达；证据：V01；目的：不经 shell 是外壳不起注入的最硬的一道闸。
- D06：起服务照第五节工作：stdin 是管道且一个字节都不写、stdout 是管道、stderr 用 inherit、`windowsHide` 为真；stdout 只解析第一行，之后的内容抽干丢弃、不出现在任何输出里；握手分两段写也能拼成一行；不写握手时 30 秒超时被拒且子进程被结束；握手前以 2 退出时立刻被拒且错误里有退出码；证据：V01；目的：只读第一行、不记服务输出，是「服务输出里可能有秘密」的防线。
- D07：收服务照第五节工作：关掉 stdin 写端后服务以 0 退出且没有走到 kill；服务忽略 EOF 时宽限期一到就被结束、进程真的没了；证据：V01；目的：关窗口必须收干净服务，不留僵尸。
- D08：`webPreferences` 恰好是第六节那十个键（多一个、少一个、松一个都不行），没有 `preload` 键；`partitionName()` 两次不同且不以 `persist:` 开头；`isServiceUrl` 的正例通过，反例（别的端口、`localhost`、`https`、`http://127.0.0.1:8080@evil`、`javascript:`、`file:`、`data:`、`about:blank`、非法串）全部被拒；证据：V01；目的：这是设计文档 §10.4 的 E1（窗口的安全选项被改松）。
- D09：编排照第七节工作：参数错 → 退出码 2 且不开窗口；找不到 Python → 1；握手失败或超时 → 1 且子进程被结束；服务意外退出 → 1、stderr 里有服务的退出码、窗口被关掉；正常关窗口且服务以 0 退出 → 0；关窗口后服务没有以 0 退出 → 1；证据：V01；目的：退出码是这一片对外的唯一契约。
- D10：控制令牌与引导地址只留在主进程内存里：`openWindow` 收到的参数只有 `{ bootstrap, origin }`（序列化后不含 `control`），所有路径上 stdout 与 stderr 都不含控制令牌、不含引导地址里的 nonce；证据：V01；目的：D4 的红线——渲染进程拿不到控制令牌。
- D11：`main.js` 是唯一 `require('electron')` 的文件；菜单置空；分区与权限处理器一律拒绝；新窗口一律拒绝；`will-navigate` 只放行服务 origin；用户参数在开发模式取 `process.argv.slice(2)`、打包后取 `slice(1)`；`src/**` 与 `main.js` 里没有 `persist:`、`shell: true`、fs 的写函数、`fetch`、`net.request`、`http(s).request`、`autoUpdater`、`crashReporter`、`openExternal`；证据：V01、G01；目的：静态禁令把「顺手加一行 fetch」这类改松挡在门外。
- D12：README 写清装法、跑法、参数、退出码、三个时限、`npm ci` 不下载 Electron 本体以及 `node node_modules/electron/install.js` 的下载办法、手工冒烟步骤；README 里的命令与 `package.json` 的 `scripts` 一致；证据：review、G01；目的：真窗口只能靠手工冒烟，README 是那一段唯一的凭据。
- D13：所有修改都在允许集合内（新增文件都在 `allowed_new_files`，没有删文件、没有改既有文件，`forbidden_paths` 里的 `tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**` 一个都没动，`desktop/web` 的 `package.json` 与 `package-lock.json` 一个字节没动）；证据：scope；目的：越界改文件会让范围检查直接判负。
- D14：没有删除、跳过或弱化既有测试；`tests/test_gate_t001` … `t024` 照旧全过；新测试里没有 skip / only / todo；临时文件没有写到 `/tmp` 这类固定路径（用 `T=$(mktemp -d)` 并在同一条命令里删掉）；遇到合同与既有测试或门禁冲突时没有越界改文件（冲突写进执行报告的 `contract_conflicts`）；证据：V01、R01、G01、review；目的：既有测试是别的片的契约，不能借机削弱。

D14 附带的变异对照（每条都要有用例杀掉）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | `webPreferences` 少一个键、或把 `sandbox`/`contextIsolation` 改成 false、或多出 `preload` | `window.test.js`：与快照字面量 `deepStrictEqual`（键集合也相同） |
| M2 | `isServiceUrl` 放行 `localhost`、别的端口或 `http://127.0.0.1:8080@evil` | `window.test.js` 的反例清单 |
| M3 | `partitionName()` 带 `persist:` 前缀或两次相同 | `window.test.js`：前缀与两次不同 |
| M4 | 握手只校验字段在、不校验 origin/bootstrap | `handshake.test.js`：origin 非 127.0.0.1、bootstrap 在别的主机或端口 |
| M5 | 握手的错误里回显了控制令牌或整条握手行 | `handshake.test.js`：错误文本不含字段值 |
| M6 | 服务 stdout 的第二行（带标记）被读进来或被打出来 | `service.test.js`：标记不出现在任何输出里 |
| M7 | 服务不经 shell 起（拼成字符串）或参数被 shell 改写 | `service.test.js`：参数里的空格、`&`、`"`、`%` 原样到达 |
| M8 | 关窗口后不关 stdin，服务赖着不走 | `service.test.js`：忽略 EOF 的夹具在宽限期后被结束 |
| M9 | Python 探测只看命令存不存在（不试运行），或版本门槛写成 3.8 | `python.test.js`：退出 1 与退出 9009 的夹具都被跳过；探测代码里有 3.10 |
| M10 | 给了 `--python` 还回退到默认候选 | `python.test.js`：显式失败不回退 |
| M11 | 令牌或 nonce 出现在 stderr / stdout / `openWindow` 的参数里 | `core.test.js`：所有路径的输出不含令牌与 nonce；`openWindow` 的参数序列化后不含 `control` |
| M12 | 服务意外退出时外壳以 0 退出，或没关窗口 | `core.test.js`：退出码 1、stderr 有退出码、窗口被关掉 |
| M13 | 参数错时开了窗口，或退出码不是 2 | `core.test.js`：退出码 2 且没调 `openWindow` |
| M14 | `src/**` 里出现 `require('electron')`、`persist:`、`shell: true`、fs 写函数或 `fetch` | 静态扫描用例（扫 `main.js`、`src/**`、`tests/**`） |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如握手行的字段与次序变了、`pi_dispatch.py ui` 的选项名变了、`dispatch-pi.sh` 的 Python 顺序变了）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 需要新增除 `electron` 以外的依赖、需要改 `desktop/web` 的依赖或锁文件、远程写入、访问凭据或提升权限。
- `npm install --save-dev --save-exact electron@44.9.0` 装不出锁文件（例如网络不通、registry 不可达）：停下报告，不要改版本凑合，也不要手写锁文件。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（本版单次 5400 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；累计已用 1 次，本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（累计已用 2316 秒；16200 ≥ 2316 + 2×5400 = 13116，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 8 分钟；包骨架与锁文件 8 分钟；六个模块的实现 28 分钟；七份测试与五个夹具 24 分钟；README 4 分钟；必要检查（V01、V02、R01、G01）8 分钟；最终报告 5 分钟；总计 85 分钟，不超过单次时限 90 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：七份测试各覆盖了哪些条目、十四条变异各由哪条用例杀掉、`webPreferences` 的实际十个键、三种退出码各自走到时的 stderr 原文、`npm install` 生成的锁文件里 electron 的版本、`git diff --stat` 里**没有**任何 `tests/test_gate_*`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件；这一项不许留空。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不写 skip / only / todo。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`；不改 `desktop/web` 的依赖与锁文件；不加 `electron` 以外的依赖。
- 不在 `desktop/shell/src/**` 与 `desktop/shell/main.js` 里写 `persist:`、`shell: true`、fs 的写函数、`fetch`、`net.request`、`http(s).request`、`autoUpdater`、`crashReporter`、`openExternal`；`require('electron')` 只许出现在 `desktop/shell/main.js`。
- 不把控制令牌、引导地址或整条握手行写进 stdout、stderr、日志或文件。
