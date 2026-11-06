"use strict";

const path = require("node:path");
const { app, BrowserWindow, session, Menu, ipcMain, shell, dialog, Notification } = require("electron");
const { runShell } = require("./src/core.js");
const { partitionName, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("./src/window.js");
const { createHost } = require("./src/host.js");
const { registerHostIpc } = require("./src/ipc.js");

Menu.setApplicationMenu(null);

// 两种窗口走同一个建窗工厂：权限拒绝、新窗口拒绝与 will-navigate 的规则靠同一段代码保证相同
function guardedWindow({ partition, origin, prefs, options }) {
  const userSession = session.fromPartition(partition);
  userSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  userSession.setPermissionCheckHandler(() => false);
  const win = new BrowserWindow({ ...options, webPreferences: prefs });
  const contents = win.webContents;
  contents.setWindowOpenHandler(() => ({ action: "deny" }));
  contents.on("will-navigate", (event, url) => {
    if (!isServiceUrl(url, origin)) {
      event.preventDefault();
    }
  });
  return win;
}

app.whenReady().then(async () => {
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
      origin,
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
          origin: pageOrigin,
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

  const argv = app.isPackaged ? process.argv.slice(1) : process.argv.slice(2);

  const code = await runShell({
    argv,
    io: { stdout: process.stdout, stderr: process.stderr },
    openWindow,
    onServiceReady,
    env: process.env,
  });
  app.exit(code);
});
