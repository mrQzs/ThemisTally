# themistally-desktop-shell

ThemisTally 的桌面外壳最小骨架（Electron 主进程）。它找 Python、起本机服务、校验握手、开一个安全设置的窗口；关窗口就以 stdin 的 EOF 结束服务，按约定的退出码退出。

本片只做骨架：找 Python → 校验命令行参数 → 起服务并校验握手 → 开窗口 → 关窗口收服务。没有外壳页、托盘、单实例、多仓库切换，也没有设置存盘与 `openSettings()`。控制令牌只留在主进程内存里，不传给任何页面。

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
| **1** | 找不到 Python、握手失败或超时、服务意外退出、关窗口后服务没有以 0 正常退出 |
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

自动化测试不起真 Electron 窗口，**真 Electron 不在自动化覆盖内**，真窗口只能手工冒烟：

1. kit 的 TS 依赖要装好（`ts/` 下装好并能跑本机服务）。
2. `desktop/web` 要先构建，产物在 `desktop/web/dist/`：
   ```bash
   npm --prefix ../web run build
   ```
3. 下载 Electron 本体（见上文「安装」）：
   ```bash
   node node_modules/electron/install.js
   ```
4. 照「运行」一节起外壳，例如：
   ```bash
   npm start -- --repo .. --kit ../.. --assets ../web/dist
   ```
5. 冒烟要点：
   - 窗口能开，页面照常加载、能用；
   - 关掉窗口，服务应随之退出，外壳以 0 退出；
   - 起一个凭据录入作业，凭据小窗口里 **Ctrl+V 能粘贴**。

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

## 安全设置

两种窗口走同一个建窗工厂（`new BrowserWindow` 只有一处）：用随机内存分区（不以 `persist:` 开头），权限请求与权限检查一律拒绝，`setWindowOpenHandler` 一律拒绝，`will-navigate` 只允许该窗口自己的 origin。

- 主窗口：`mainWebPreferences(分区, preload.js 的绝对路径)`——T025 的十键加 `preload`，`contextIsolation`、`sandbox` 开，`nodeIntegration`、`webSecurity` 等按设计文档关严。
- 凭据窗口：`webPreferences(另一个分区)`——十键、**没有** `preload`，也不该有：它只装服务给的一次性 HTML 表单。

控制令牌与引导地址只留在主进程内存，不写日志、不写磁盘、不进页面；带令牌的控制请求只发往 `127.0.0.1`。
