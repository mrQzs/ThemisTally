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
    await contents.loadURL(bootstrap);
    const closed = new Promise((resolve) => {
      win.on("closed", resolve);
    });
    return {
      closed,
      close: () => win.close(),
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
