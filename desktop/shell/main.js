"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, session, Menu, ipcMain, shell, dialog, Notification, protocol } = require("electron");
const { runShell } = require("./src/core.js");
const { partitionName, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("./src/window.js");
const { createHost } = require("./src/host.js");
const { registerHostIpc } = require("./src/ipc.js");
const { launchMode } = require("./src/launch.js");
const { resolveShellAsset, isShellPageUrl } = require("./src/shellprotocol.js");
const { registerShellIpc, shellSenderAllowed, SERVICE_STATE_CHANNEL } = require("./src/shellipc.js");
const { createShellApi } = require("./src/shellapi.js");
const { createSettingsStore } = require("./src/settings.js");
const { createServiceFlow } = require("./src/serviceflow.js");
const { createHostRelay } = require("./src/hostrelay.js");
const { SHELL_START_URL, SHELL_STATUS_URL } = require("./src/shellprotocol.js");

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
// 服务在 running 期间自己退出时回到服务状态页：同一个外壳进程里能第二次起服务。
async function runShellPage() {
  const root = path.join(__dirname, "..", "web", "dist");
  if (!fs.existsSync(path.join(root, "index.html"))) {
    process.stderr.write(`ERROR: 找不到外壳页产物 index.html：${path.join(root, "index.html")}\n`);
    app.exit(1);
    return;
  }
  const store = createSettingsStore({ dir: app.getPath("userData") });
  // 宿主 IPC 只在这里注册一次：调用经 relay 转给当前服务实例的 host。
  // 同一个进程里第二次起服务不再重复注册——同一通道第二次 handle 会抛错
  const relay = createHostRelay();
  registerHostIpc(ipcMain, relay.host, relay.senderAllowed);
  // 当前外壳页窗口：外壳 IPC、选择框与服务状态事件都读它；换页（首次启动页 / 服务状态页）时换成新的
  let shellWin = null;
  // 外壳页窗口是不是外壳自己关的：起服务成功与意外退出换页那两次由我们主动关，那时应用不退
  let closedByShell = false;
  // 用户关掉当前外壳窗口时才兑现：外壳自己关的窗口不兑现，接着等下一个外壳窗口
  let userClosedShell;
  const shellClosedByUser = new Promise((resolve) => {
    userClosedShell = resolve;
  });
  let shellTracked = null;
  let serviceWindow = null;
  // 服务自己退出那条路已经在收尾：服务窗口的 closed 不用再收一次服务
  let serviceGone = false;

  // 外壳窗口统一走这里：每次取新分区、只在它自己的 session 上注册一次协议 handler。
  // 注册在模块级 protocol 上会 ERR_FAILED；同一个 session 上注册第二次会抛错
  // （Failed to register protocol: themis-shell），所以每开一次窗都现取 partitionName()
  async function openShellWindow(url) {
    const partition = partitionName();
    const userSession = session.fromPartition(partition);
    userSession.protocol.handle("themis-shell", (request) => {
      const resolved = resolveShellAsset(root, request.url);
      return new Response(resolved.body, { status: resolved.status, headers: resolved.headers });
    });
    const opened = guardedWindow({
      partition,
      prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")),
      options: { title: "ThemisTally" },
      allowNavigation: isShellPageUrl,
    });
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
      // 当前服务实例的 host 挂进 relay：宿主 IPC 只注册一次，调用转给当前 host
      relay.use(host, senderAllowed);

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
      if (shellWin !== null && !shellWin.isDestroyed()) shellWin.close();

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
  // 状态一变就发给当前外壳页窗口：只发 state 这一个实参，窗口为空或已销毁就跳过
  flow.subscribe((state, info) => {
    if (shellWin !== null && !shellWin.isDestroyed()) shellWin.webContents.send(SERVICE_STATE_CHANNEL, state);
    // 服务在 running 期间自己退出（不是外壳停的）→ 回服务状态页显示退出码。
    // 「是不是外壳自己结束的」看 info.byShell，不看退出码：外部杀掉的 1 与自己退出的 1 分不出来
    if (state.kind !== "exited" || info.byShell || serviceWindow === null) return;
    serviceGone = true;
    // 已经有外壳窗口开着（服务状态页）：不另开窗口，外壳页自己经事件显示错误
    if (shellWin !== null && !shellWin.isDestroyed()) {
      relay.clear();
      if (!serviceWindow.isDestroyed()) serviceWindow.close();
      return;
    }
    openShellWindow(SHELL_STATUS_URL).then(
      () => {
        // 窗口次序：先建新窗口，再关服务窗口——任何时刻都不出现零窗口
        relay.clear();
        if (!serviceWindow.isDestroyed()) serviceWindow.close();
      },
      () => {
        // 服务状态页开不出来：写一行 ERROR 并以 1 退出
        process.stderr.write(`ERROR: 服务意外退出（退出码 ${state.exitCode}）\n`);
        if (!serviceWindow.isDestroyed()) serviceWindow.close();
        app.exit(1);
      },
    );
  });
  // 选择框与外部链接确认框挂在当前外壳窗口上
  const api = createShellApi({
    store,
    service: flow,
    assets: root,
    chooseDirectory: async ({ title }) => {
      const options = { title, properties: ["openDirectory"] };
      // 当前外壳窗口不在（换页的间隙）就不带父窗口调用
      const result =
        shellWin === null || shellWin.isDestroyed()
          ? await dialog.showOpenDialog(options)
          : await dialog.showOpenDialog(shellWin, options);
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    chooseFile: async ({ title }) => {
      const options = { title, properties: ["openFile"] };
      const result =
        shellWin === null || shellWin.isDestroyed()
          ? await dialog.showOpenDialog(options)
          : await dialog.showOpenDialog(shellWin, options);
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    confirmExternal: async (url) => {
      const options = {
        type: "question",
        buttons: ["打开", "取消"],
        defaultId: 1,
        cancelId: 1,
        message: "在系统浏览器中打开？",
        detail: url,
        noLink: true,
      };
      const result =
        shellWin === null || shellWin.isDestroyed()
          ? await dialog.showMessageBox(options)
          : await dialog.showMessageBox(shellWin, options);
      return result.response === 0;
    },
    openExternal: async (url) => {
      await shell.openExternal(url);
    },
    appVersion: app.getVersion(),
  });
  registerShellIpc(ipcMain, api, (event) => {
    // 来源检查读当前外壳窗口：换页之后，旧窗口的 webContents 不再能调外壳接口
    if (shellWin === null || shellWin.isDestroyed()) return false;
    return shellSenderAllowed(event, shellWin.webContents);
  });
  await openShellWindow(SHELL_START_URL);
  await shellClosedByUser;
  // 外壳页是用户关的：starting 期间先中止子进程（子进程真的退出，不留僵尸），再退出
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
