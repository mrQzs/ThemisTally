"use strict";

const crypto = require("node:crypto");

function partitionName() {
  return crypto.randomUUID();
}

// 建窗背景色：暗 #0C111A、亮 #F3F5F9；跟随系统（"system"）与任何非法值（含 undefined）按 systemDark 取。
// systemDark 由调用方传 nativeTheme.shouldUseDarkColors。
function backgroundFor(theme, systemDark) {
  if (theme === "dark") return "#0C111A";
  if (theme === "light") return "#F3F5F9";
  return systemDark ? "#0C111A" : "#F3F5F9";
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

module.exports = { partitionName, backgroundFor, webPreferences, mainWebPreferences, trackWindow, isServiceUrl };
