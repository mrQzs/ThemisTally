# themistally-desktop-shell

ThemisTally 的桌面外壳最小骨架（Electron 主进程）。它找 Python、起本机服务、校验握手、开一个安全设置的窗口；关窗口就以 stdin 的 EOF 结束服务，按约定的退出码退出。

本片只做骨架：找 Python → 校验命令行参数 → 起服务并校验握手 → 开窗口 → 关窗口收服务。外壳页在本片就位（界面接线在下一片）；托盘、单实例、多仓库切换与 `openSettings()` 仍没有；设置文件与三项校验的数据层已经就位（见下文「设置与校验」），外壳页的界面与接线在后面一片。控制令牌只留在主进程内存里，不传给任何页面。

主窗口配 preload（`preload.js`，暴露 `window.themisHost` 给服务页调用系统能力），凭据小窗口不配 preload。

## 安装

```bash
npm ci
```

> **注意**：`electron@44.9.0` 的 `package.json` 没有 `scripts`（没有 postinstall），所以 `npm ci` **不会**下载 Electron 本体，只装它的 npm 依赖。要跑真窗口，先执行下面这条下载本体并写 `path.txt`：
>
> ```bash
> node node_modules/electron/install.js
> ```
>
> 这是 `electron@44.9.0` 的 `bin.install-electron` 指向的 `install.js`。纯逻辑的单元测试（`npm test`）不 `require('electron')`，不需要本体。

## 运行

```bash
npm start -- --repo <仓库> --kit <ThemisTally 目录> --assets <desktop/web 的构建产物>
```

`npm start` 等价于 `electron .`。参数：

| 参数 | 必需 | 说明 |
|---|---|---|
| `--repo <路径>` | 是 | 仓库根目录（必须是目录） |
| `--kit <路径>` | 是 | ThemisTally 目录，其下要有 `scripts/pi_dispatch.py` |
| `--assets <路径>` | 是 | `desktop/web` 的构建产物目录，其下要有 `index.html` |
| `--python <命令>` | 否 | 指定 Python 命令或路径；不给则按 `python3`、`python`、`py -3` 顺序找 |
| `--transcript <记录>` | 否 | 用量路由的会话记录，可重复给出，按顺序原样传给服务 |

## 退出码

| 退出码 | 含义 |
|---|---|
| **0** | 正常关窗口，且服务以 0 退出 |
| **1** | 找不到 Python、握手失败或超时、服务意外退出、关窗口后服务没有以 0 正常退出、外壳分支找不到产物 index.html |
| **2** | 命令行参数错（缺必需项、未知选项、位置参数、路径不对） |

每种失败都会先往 stderr 写一行以 `ERROR: ` 开头的说明，再按上表退出。

## 时限

- Python 探测：每个候选 **10 秒**。
- 服务握手：**30 秒**内没有合法的握手行就放弃。
- 关窗口后收服务：关 stdin 后宽限 **10 秒**，服务仍不退才 kill（服务自带 3 秒看门狗，正常情况下 3 秒内就退）。

## 测试

```bash
npm test
```

用 Node 自带的 `node --test`（带 `--test-reporter=tap`），覆盖参数解析、找 Python、握手、起服务与收服务、窗口安全设置、宿主接口的校验与编排、IPC 通道与 preload；不需要 Electron 本体。

## 手工冒烟

自动化测试不起真 Electron 窗口，**真 Electron 不在自动化覆盖内**（自动化测试与门禁都不跑真 Electron），真窗口只能手工冒烟。先 `npm ci`、构建前端产物（`npm --prefix ../web run build`）、下载本体（见上文「安装」的 `node node_modules/electron/install.js`）。冒烟降为三条：

1. 不带参数 `npm start`：打开首次启动页 `themis-shell://app/index.html#/first-run`（此时显示的是桩数据）。
2. 带齐 `--repo` / `--kit` / `--assets` 起服务分支，行为与现在相同：窗口能开、页面能用；关掉窗口服务随之退出、外壳以 0 退出；起一个凭据录入作业，凭据小窗口里 **Ctrl+V 能粘贴**。
3. 关掉外壳页窗口，外壳以 **0** 退出。

## 宿主接口 `window.themisHost`

preload 只把五个函数原样转交给主进程的固定 IPC 通道，参数怎么填、会不会越界，一律由主进程校验；控制令牌只留在主进程，页面经 IPC 也拿不到它。每个函数成功回 `{ ok: true }`，失败回 `{ ok: false, reason: "…" }`——`reason` 是下表的固定词，错误消息（可能带着引导地址、一次性页面令牌或正文片段）一律不外传。

| 函数 | 说明 | 失败时的 `reason` |
|---|---|---|
| `reauth()` | 带控制令牌 `POST /control/bootstrap` 换新的引导地址，校验通过才重新加载主窗口 | `rate-limited`（60 秒内第 4 次）、`request-failed`（连不上、超时）、`bad-response`（非 200、非 JSON、`ok` 不是 true、`data.bootstrap` 不是字符串或不在服务 origin 下）、`load-failed` |
| `openSecretWindow(url, jobId)` | 开一个 560×480 的凭据小窗口装服务给的一次性 HTML 表单；关窗即取消该作业 | `bad-args`（地址形状不对、作业号形状不对）、`busy`（已经有一个凭据窗口且是别的作业）、`load-failed` |
| `openExternal(url)` | 先弹确认框，确认后交给系统浏览器 | `bad-url`（不是 http/https，或带首尾空白与换行）、`cancelled`（用户取消）、`open-failed`（打不开） |
| `reveal(relPath)` | 在系统文件管理器里显示 `<仓库>/.agent/` 下的一个文件或目录 | `bad-path`（路径不合格、不存在、或经重解析点跑到 `.agent` 外） |
| `notify(kind)` | 发一条系统通知 | `bad-kind`（不是下表里的类型名） |

两种情形对所有函数通用：来源不是主窗口、或主窗口当前显示的不是服务 origin 下的页面 → `forbidden`；其余没列出的意外 → `internal`。

- **凭据窗口同时最多 1 个**：同一个 `jobId` 再调聚焦并回 `{ ok: true }`，别的 `jobId` 回 `busy` 并聚焦；两者都不开新窗口、不发取消（被拒的作业由页面自己调 `/api/v1/jobs/<id>/cancel`）。窗口关掉之后可以再开。
- **限速**：`reauth` 每 60 秒最多 3 次（滑动窗口），失败的也占名额。
- **relPath 的基准是 `<仓库>/.agent/`**，参数不带 `.agent/` 前缀（例如填 `runs/t026/attempt-001/summary.md`）。
- **通知类型名与文案写死在主进程**，渲染进程给的额外参数不进文案：

| 类型名 | 标题 | 正文 |
|---|---|---|
| `attempt-finished` | ThemisTally | attempt 已结束 |
| `awaiting-review` | ThemisTally | 有 attempt 等待验收 |

## 设置与校验

外壳页的数据层：`src/settings.js`（设置文件）、`src/detect.js`（三项校验与自动检测）、`src/shellapi.js`（`window.themisShell` 十个成员的主进程实现，七个真方法加三个占位）。本片不碰 `main.js`、协议与 preload，也不起服务。

### 设置文件

位置是 `<userData>/settings.json`（Electron 的 userData 目录由调用方注入，模块不自己找）。字段固定，写盘只写这些键、按这个顺序：

| 字段 | 取值 |
|---|---|
| `version` | 固定 `1` |
| `repos` | 仓库条目数组，每项 `{id, name, path, lastOpened}` |
| `currentRepo` | 当前仓库的 id，没有为 `null` |
| `transcriptDirs` | 会话记录目录数组，每项 `{id, path}` |
| `theme` | `system` / `light` / `dark` |
| `density` | `standard` / `compact` |
| `pythonPath` | 指定的 Python 路径，没有为 `null` |
| `kitPath` | 指定的 ThemisTally 目录，没有为 `null` |

- 文件不存在 → 用缺省设置起来。
- 文件是坏 JSON、顶层不是对象、或任一已知键取值不合法（例如 `theme: "neon"`）→ **整份当坏文件**：用缺省设置起来，并把坏文件的原始字节另存成同目录下的 `settings.bad-<UTC 时刻>.json`（时刻格式 `YYYYMMDDTHHMMSSmmmZ`）。副本**不覆盖**已有同名文件，依次试 `-2`、`-3`……直到没人占用的名字。
- 未知键忽略，下次写盘自然丢掉；写盘是原子写：先写 `settings.json.tmp`，再换名覆盖正式文件。写失败就删掉临时文件并抛出错误，正式文件一个字节都不动。
- **设置文件里不存凭据，也不存控制令牌**：设置模块根本不接收这两个字段，控制令牌只留在主进程内存里。

`saveSettings` 只认六个键——`theme`、`density`、`removeRepo`、`removeTranscriptDir`、`resetPython`、`resetKit`——**不接受任何路径**（路径只能来自系统选择框）。整包合格才应用并写盘；任一项不合格（补丁形状不对、取值不在表里、id 不存在、要移除的正是当前仓库）就整体拒绝，设置与文件的字节都不变。三个失败原因：`bad-patch` / `unknown-id` / `current-repo`。

### 三项校验

| 校验 | 判据 |
|---|---|
| 仓库 | 只看文件系统：`<仓库>/.git` 存在（目录或文件都算，worktree 是文件）且 `<仓库>/.agent` 是目录 |
| Python | 能跑起来且版本 ≥ 3.10；自动检测按 `python3` → `python` → `py -3` 的顺序，第一个可用即用 |
| kit | 用可用的 Python 跑 `<kit>/scripts/pi_dispatch.py --version`，退出码为 0 并取到 `x.y.z` 版本号 |

- 三项校验都不写任何文件。
- 子进程一律不经 shell（`shell: false`、`windowsHide: true`，stdio 只收两路输出），**每个子进程 10 秒**时限：到点杀进程并按失败处理，不把外壳挂死。
- 探测失败的原因词（模块内部用）：`version-too-old`、`bad-output`、`timeout`、`no-command`、`python-unusable`、`kit-unusable`。

### 选择器与返回值

四个选择器（`pickRepo` / `pickPython` / `pickKit` / `pickTranscriptDir`）各有三种结果：取消 → `{kind: "cancelled"}`；校验不过 → `{kind: "rejected", problem, path}`（不写盘）；校验通过 → `{kind: "saved", path, id?, state}`（写盘，`id` 只有仓库与会话目录有）。只有保存才写盘，被拒与取消都不碰设置文件。`getState` 的返回值形状与 `desktop/web/src/shellpages/themisShell.ts` 逐字段一致，由 `tests/shellshape.test.js` 读那份类型文件比对钉住。`startService` / `restartService` / `on('service-state')` 仍是占位。

## 外壳页

不带命令行参数启动时（`npm start`，等价 `electron .`）走外壳页分支：用自定义协议 `themis-shell://app/` 加载 `desktop/web/dist` 的前端产物，打开首次启动页 `themis-shell://app/index.html#/first-run`。分支判定在起服务之前——argv 里出现 `--repo`（或 `--repo=…`）才走服务分支，否则走这里；外壳分支不解析参数、也不起服务。

- 产物在 `desktop/web/dist`，先构建前端：
  ```bash
  npm --prefix ../web run build
  ```
- 协议只登记 `standard` 与 `secure` 两个 privileges（不加 `supportFetchAPI`、`corsEnabled`）；协议 handler 注册在窗口自己的分区 session 上。响应头带与服务页逐字相同的 CSP，外加 `X-Content-Type-Options: nosniff`。
- 协议只读产物根内的普通文件：越界、路径上任一级的链接/junction、二次解码（解码后仍含 `%`）、目录、未知扩展名，一律回 **404** 且不带正文细节。

`window.themisShell` 由顶层 `shell-preload.js` 暴露（只 require electron、自包含，恰好一次 `exposeInMainWorld`），成员恰好十个，与 `desktop/web/src/shellpages/themisShell.ts` 的 `interface ThemisShell` 一致：`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`。每个方法只把声明的实参转交一条固定 IPC 通道，再拆信封：`{ok:true,value}` → resolve `value`；`{ok:false,reason}` → 以 `new Error(reason)` reject（`reason` 只进 `Error.message`，错误细节不外传）。`on` 同步返回退订函数，本片不发事件。

九条通道都在主进程经 `ipcMain.handle` 注册（不用 `ipcMain.on`），来源三条件核对：发送者是外壳窗口的 webContents、frame 非空、frame 当前显示的是 `themis-shell://app/` 页面；来源不对回 `forbidden`，api 抛错回 `internal`，都不外传错误消息。

| 通道 | 方法 |
|---|---|
| `themis-shell:get-state` | `getState()` |
| `themis-shell:pick-repo` | `pickRepo()` |
| `themis-shell:pick-python` | `pickPython()` |
| `themis-shell:pick-kit` | `pickKit()` |
| `themis-shell:pick-transcript-dir` | `pickTranscriptDir()` |
| `themis-shell:save-settings` | `saveSettings(patch)` |
| `themis-shell:start-service` | `startService(repo)` |
| `themis-shell:restart-service` | `restartService()` |
| `themis-shell:open-external` | `openExternal(url)` |

**此时首次启动页显示的是桩数据**：页面接 `window.themisShell` 在下一片；本片不起服务、不发 `service-state` 事件，`startService` / `restartService` / `on` 仍是占位。外壳分支根本不起服务，渲染进程经 IPC 也拿不到控制令牌。关掉外壳窗口，外壳以 0 退出。

Electron 本体没有 postinstall，第一次运行才下载；自动化测试与门禁都不跑真 Electron，纯逻辑测试也不需要本体。

## 安全设置

两种窗口走同一个建窗工厂（`new BrowserWindow` 只有一处）：用随机内存分区（不以 `persist:` 开头），权限请求与权限检查一律拒绝，`setWindowOpenHandler` 一律拒绝，`will-navigate` 只允许该窗口自己的 origin。

- 主窗口：`mainWebPreferences(分区, preload.js 的绝对路径)`——T025 的十键加 `preload`，`contextIsolation`、`sandbox` 开，`nodeIntegration`、`webSecurity` 等按设计文档关严。
- 凭据窗口：`webPreferences(另一个分区)`——十键、**没有** `preload`，也不该有：它只装服务给的一次性 HTML 表单。

控制令牌与引导地址只留在主进程内存，不写日志、不写磁盘、不进页面；带令牌的控制请求只发往 `127.0.0.1`。
