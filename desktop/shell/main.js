"use strict";

const { app, BrowserWindow, session, Menu } = require("electron");
const { runShell } = require("./src/core.js");
const { partitionName, webPreferences, isServiceUrl } = require("./src/window.js");

Menu.setApplicationMenu(null);

app.whenReady().then(async () => {
  const partition = partitionName();
  const userSession = session.fromPartition(partition);
  userSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  userSession.setPermissionCheckHandler(() => false);

  const openWindow = async ({ bootstrap, origin }) => {
    const win = new BrowserWindow({
      webPreferences: webPreferences(partition),
    });
    const contents = win.webContents;
    contents.setWindowOpenHandler(() => ({ action: "deny" }));
    contents.on("will-navigate", (event, url) => {
      if (!isServiceUrl(url, origin)) {
        event.preventDefault();
      }
    });
    // 窗口一建好就注册 closed：页面加载完成前用户关窗时，'closed' 不能因为挂得晚而漏掉
    const closed = new Promise((resolve) => {
      win.on("closed", resolve);
    });
    try {
      await contents.loadURL(bootstrap);
    } catch (err) {
      // 加载期间窗口被关掉时 loadURL 会 reject：此时按「窗口已关」走正常收尾，
      // 让 runShell 去关 stdin、收服务，而不是把拒绝抛成未捕获的退出
      if (!win.isDestroyed()) {
        throw err;
      }
    }
    return {
      closed,
      close: () => {
        if (!win.isDestroyed()) {
          win.close();
        }
      },
    };
  };

  const argv = app.isPackaged ? process.argv.slice(1) : process.argv.slice(2);

  const code = await runShell({
    argv,
    io: { stdout: process.stdout, stderr: process.stderr },
    openWindow,
    env: process.env,
  });
  app.exit(code);
});
