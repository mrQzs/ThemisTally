"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, session, Menu, ipcMain, shell, dialog, Notification, protocol } = require("electron");
const { runShell } = require("./src/core.js");
const { partitionName, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("./src/window.js");
const { createHost } = require("./src/host.js");
const { registerHostIpc } = require("./src/ipc.js");
const { launchMode } = require("./src/launch.js");
const { resolveShellAsset, isShellPageUrl, SHELL_START_URL } = require("./src/shellprotocol.js");
const { registerShellIpc, shellSenderAllowed, SERVICE_STATE_CHANNEL } = require("./src/shellipc.js");
const { createShellApi } = require("./src/shellapi.js");
const { createSettingsStore } = require("./src/settings.js");
const { createServiceFlow } = require("./src/serviceflow.js");

Menu.setApplicationMenu(null);

// themis-shell 协议登记成特权 scheme：只此一处、放在两个分支都经过的位置；privileges 只要 standard 与 secure
protocol.registerSchemesAsPrivileged([{ scheme: "themis-shell", privileges: { standard: true, secure: true } }]);

// 两种窗口走同一个建窗工厂：权限拒绝、新窗口拒绝与 will-navigate 的规则靠同一段代码保证相同。
// 导航判定由调用方给：服务窗口按 origin，外壳窗口按 isShellPageUrl。
function guardedWindow({ partition, prefs, options, allowNavigation }) {
  const userSession = session.fromPartition(partition);
  userSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  userSession.setPermissionCheckHandler(() => false);
  const win = new BrowserWindow({ ...options, webPreferences: prefs });
  const contents = win.webContents;
  contents.setWindowOpenHandler(() => ({ action: "deny" }));
  contents.on("will-navigate", (event, url) => {
    if (!allowNavigation(url)) {
      event.preventDefault();
    }
  });
  return win;
}

// 外壳页分支：用 themis-shell://app/ 加载 desktop/web/dist 的产物，打开首次启动页（此时显示的是桩数据）。
// 页面调 startService(repo) 之后由这里起真服务：握手成功先开服务窗口、再关外壳页窗口。
async function runShellPage() {
  const root = path.join(__dirname, "..", "web", "dist");
  if (!fs.existsSync(path.join(root, "index.html"))) {
    process.stderr.write(`ERROR: 找不到外壳页产物 index.html：${path.join(root, "index.html")}\n`);
    app.exit(1);
    return;
  }
  const partition = partitionName();
  // 协议 handler 注册在这个分区 session 的 protocol 上（注册在模块级 protocol 上会 ERR_FAILED）
  session.fromPartition(partition).protocol.handle("themis-shell", (request) => {
    const resolved = resolveShellAsset(root, request.url);
    return new Response(resolved.body, { status: resolved.status, headers: resolved.headers });
  });
  const win = guardedWindow({
    partition,
    prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")),
    options: { title: "ThemisTally" },
    allowNavigation: isShellPageUrl,
  });
  const store = createSettingsStore({ dir: app.getPath("userData") });
  // 外壳页窗口是不是外壳自己关的：服务窗口建好之后才由我们主动关它，那时应用不退
  let closedByShell = false;
  let serviceWindow = null;
  // 服务自己退出那条路已经在收尾：服务窗口的 closed 不用再收一次服务
  let serviceGone = false;

  // 握手成功后开服务窗口：控制令牌只经 onRunning 的实参进 createHost 的闭包，不进状态、不进事件
  const flow = createServiceFlow({
    onRunning: async ({ origin, control, repo, bootstrap }) => {
      // createHost 要的是仓库路径，控制器那边只有仓库 id：路径按 id 从设置里查回来
      const settings = store.load().settings;
      const entry = settings.repos.find((item) => item.id === repo) || null;
      const host = createHost({
        origin,
        control,
        repo: entry === null ? repo : entry.path,
        loadMain: async (url) => {
          if (serviceWindow === null || serviceWindow.isDestroyed()) return;
          await serviceWindow.webContents.loadURL(url);
        },
        createSecretWindow: ({ origin: pageOrigin }) => {
          // 凭据窗口另取一个内存分区，用不带 preload 的十键设置：它只装服务给的一次性 HTML 表单
          const credentialPartition = partitionName();
          return guardedWindow({
            partition: credentialPartition,
            allowNavigation: (url) => isServiceUrl(url, pageOrigin),
            prefs: webPreferences(credentialPartition),
            options: { parent: serviceWindow, width: 560, height: 480, title: "录入凭据" },
          });
        },
        confirmExternal: async (url) => {
          const result = await dialog.showMessageBox(serviceWindow, {
            type: "question",
            buttons: ["打开", "取消"],
            defaultId: 1,
            cancelId: 1,
            message: "在系统浏览器中打开？",
            detail: url,
            noLink: true,
          });
          return result.response === 0;
        },
        openExternal: async (url) => {
          await shell.openExternal(url);
        },
        showItem: (fullPath) => {
          shell.showItemInFolder(fullPath);
        },
        showNotification: ({ title, body }) => {
          new Notification({ title, body }).show();
        },
      });
      // 来源检查：只有服务窗口、且它当前显示的确实是服务 origin 下的页面，才准调宿主接口
      const senderAllowed = (event) => {
        const frame = event.senderFrame;
        if (serviceWindow === null || event.sender !== serviceWindow.webContents) return false;
        if (frame === null || frame === undefined) return false;
        return isServiceUrl(frame.url, origin);
      };
      registerHostIpc(ipcMain, host, senderAllowed);

      // 窗口次序：先建服务窗口，再关外壳页窗口——Electron 关掉最后一个窗口时会自己退出
      const servicePartition = partitionName();
      const opened = guardedWindow({
        partition: servicePartition,
        prefs: mainWebPreferences(servicePartition, path.join(__dirname, "preload.js")),
        options: {},
        allowNavigation: (url) => isServiceUrl(url, origin),
      });
      serviceWindow = opened;
      let tracked;
      try {
        tracked = await trackWindow(opened, () => opened.webContents.loadURL(bootstrap));
      } catch {
        if (!opened.isDestroyed()) opened.close();
        throw new Error("服务窗口加载失败");
      }
      closedByShell = true;
      if (!win.isDestroyed()) win.close();

      // 用户关掉服务窗口就结束服务：以 0 退出才让应用以 0 退出（与带参数那条路同一套规则）
      tracked.closed.then(async () => {
        if (serviceGone) return;
        const stop = await flow.stop();
        if (stop.exited && stop.code === 0) {
          app.exit(0);
          return;
        }
        process.stderr.write("ERROR: 服务没有以 0 正常退出\n");
        app.exit(1);
      });
    },
  });
  // 状态一变就发给外壳页窗口：只发 state 这一个实参，窗口已销毁就跳过
  flow.subscribe((state, info) => {
    if (!win.isDestroyed()) win.webContents.send(SERVICE_STATE_CHANNEL, state);
    // A 片过渡：服务在 running 期间自己退出（不是外壳停的）→ 写一行 ERROR、关服务窗口、以 1 退出。
    // 「是不是外壳自己结束的」看 info.byShell，不看退出码：外部杀掉的 1 与自己退出的 1 分不出来
    if (state.kind !== "exited" || info.byShell || serviceWindow === null) return;
    serviceGone = true;
    process.stderr.write(`ERROR: 服务意外退出（退出码 ${state.exitCode}）\n`);
    if (!serviceWindow.isDestroyed()) serviceWindow.close();
    app.exit(1);
  });
  const api = createShellApi({
    store,
    service: flow,
    assets: root,
    chooseDirectory: async ({ title }) => {
      const result = await dialog.showOpenDialog(win, { title, properties: ["openDirectory"] });
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    chooseFile: async ({ title }) => {
      const result = await dialog.showOpenDialog(win, { title, properties: ["openFile"] });
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    confirmExternal: async (url) => {
      const result = await dialog.showMessageBox(win, {
        type: "question",
        buttons: ["打开", "取消"],
        defaultId: 1,
        cancelId: 1,
        message: "在系统浏览器中打开？",
        detail: url,
        noLink: true,
      });
      return result.response === 0;
    },
    openExternal: async (url) => {
      await shell.openExternal(url);
    },
    appVersion: app.getVersion(),
  });
  registerShellIpc(ipcMain, api, (event) => shellSenderAllowed(event, win.webContents));
  const tracked = await trackWindow(win, () => win.webContents.loadURL(SHELL_START_URL));
  await tracked.closed;
  // 外壳页是我们自己关的（服务窗口还开着）：应用不退
  if (closedByShell) return;
  // 用户关的：starting 期间先中止子进程（子进程真的退出，不留僵尸），再退出
  const state = flow.state();
  if (state.kind === "starting") await flow.abort();
  else if (state.kind === "running") await flow.stop();
  app.exit(0);
}

app.whenReady().then(async () => {
  const argv = app.isPackaged ? process.argv.slice(1) : process.argv.slice(2);
  if (launchMode(argv) === "shell") {
    await runShellPage();
    return;
  }

  const partition = partitionName();
  const preloadPath = path.join(__dirname, "preload.js");
  let mainWindow = null;
  let serviceOrigin = null;

  // 来源检查：只有主窗口、且它当前显示的确实是服务 origin 下的页面，才准调宿主接口
  const senderAllowed = (event) => {
    const frame = event.senderFrame;
    if (mainWindow === null || event.sender !== mainWindow.webContents) return false;
    if (frame === null || frame === undefined) return false;
    return isServiceUrl(frame.url, serviceOrigin);
  };

  const openWindow = async ({ bootstrap, origin }) => {
    serviceOrigin = origin;
    const win = guardedWindow({
      partition,
      allowNavigation: (url) => isServiceUrl(url, origin),
      prefs: mainWebPreferences(partition, preloadPath),
      options: {},
    });
    mainWindow = win;
    return trackWindow(win, () => win.webContents.loadURL(bootstrap));
  };

  // 控制令牌只经这里进主进程，之后只在 createHost 的闭包里，不进任何页面
  const onServiceReady = ({ origin, control, repo }) => {
    serviceOrigin = origin;
    const host = createHost({
      origin,
      control,
      repo,
      loadMain: async (bootstrap) => {
        await mainWindow.webContents.loadURL(bootstrap);
      },
      createSecretWindow: ({ origin: pageOrigin }) => {
        // 凭据窗口另取一个内存分区，用不带 preload 的十键设置：它只装服务给的一次性 HTML 表单
        const credentialPartition = partitionName();
        return guardedWindow({
          partition: credentialPartition,
          allowNavigation: (url) => isServiceUrl(url, pageOrigin),
          prefs: webPreferences(credentialPartition),
          options: { parent: mainWindow, width: 560, height: 480, title: "录入凭据" },
        });
      },
      confirmExternal: async (url) => {
        const result = await dialog.showMessageBox(mainWindow, {
          type: "question",
          buttons: ["打开", "取消"],
          defaultId: 1,
          cancelId: 1,
          message: "在系统浏览器中打开？",
          detail: url,
          noLink: true,
        });
        return result.response === 0;
      },
      openExternal: async (url) => {
        await shell.openExternal(url);
      },
      showItem: (fullPath) => {
        shell.showItemInFolder(fullPath);
      },
      showNotification: ({ title, body }) => {
        new Notification({ title, body }).show();
      },
    });
    registerHostIpc(ipcMain, host, senderAllowed);
  };

  const code = await runShell({
    argv,
    io: { stdout: process.stdout, stderr: process.stderr },
    openWindow,
    onServiceReady,
    env: process.env,
  });
  app.exit(code);
});
