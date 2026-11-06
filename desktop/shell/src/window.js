"use strict";

const crypto = require("node:crypto");

function partitionName() {
  return crypto.randomUUID();
}

function webPreferences(partition) {
  return {
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    spellcheck: false,
    partition,
  };
}

// 主窗口比凭据窗口多一个 preload（宿主接口的入口）；凭据窗口仍用 webPreferences，十键、没有 preload
function mainWebPreferences(partition, preloadPath) {
  return { ...webPreferences(partition), preload: preloadPath };
}

// 先挂 closed（并记下它是否已触发），再加载：页面加载完成前用户关窗时，
// loadURL 的拒绝里带着整条引导地址，此时按「窗口已关」吞掉，别把地址抛成未捕获的退出
async function trackWindow(win, load) {
  let closedFired = false;
  const closed = new Promise((resolve) => {
    win.on("closed", () => {
      closedFired = true;
      resolve();
    });
  });
  const close = () => {
    if (!win.isDestroyed()) {
      win.close();
    }
  };
  try {
    await load();
  } catch (err) {
    if (win.isDestroyed() || closedFired) {
      return { closed, close };
    }
    throw err;
  }
  return { closed, close };
}

function isServiceUrl(url, origin) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return parsed.origin === origin;
}

module.exports = { partitionName, webPreferences, mainWebPreferences, trackWindow, isServiceUrl };
