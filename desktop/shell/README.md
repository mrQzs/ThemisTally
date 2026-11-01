# themistally-desktop-shell

ThemisTally 的桌面外壳最小骨架（Electron 主进程）。它找 Python、起本机服务、校验握手、开一个安全设置的窗口；关窗口就以 stdin 的 EOF 结束服务，按约定的退出码退出。

本片只做骨架：找 Python → 校验命令行参数 → 起服务并校验握手 → 开窗口 → 关窗口收服务。没有外壳页、托盘、通知、单实例、多仓库切换，也没有 preload 与凭据小窗口。控制令牌只留在主进程内存里，不传给任何页面。

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

用 Node 自带的 `node --test`（带 `--test-reporter=tap`），覆盖参数解析、找 Python、握手、起服务与收服务、窗口安全设置与编排；不需要 Electron 本体。

## 手工冒烟

自动化测试不起真 Electron 窗口，真窗口只能手工冒烟：

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
   关掉窗口，服务应随之退出，外壳以 0 退出。

## 安全设置

窗口用固定的一套 `webPreferences`（`contextIsolation`、`sandbox` 开，`nodeIntegration`、`webSecurity` 等按设计文档关严），**不配 preload**；用随机内存分区（不以 `persist:` 开头），权限请求与权限检查一律拒绝，`setWindowOpenHandler` 一律拒绝，`will-navigate` 只允许服务自己的 origin。控制令牌与引导地址只留在主进程内存，不写日志、不写磁盘、不进页面。
