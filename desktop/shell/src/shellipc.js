"use strict";

const { isShellPageUrl } = require("./shellprotocol.js");

// 通道白名单：与顶层 shell-preload.js 逐字一致，冻结之后不许增改（恰好九个，顺序固定）
const SHELL_CHANNELS = Object.freeze([
  "themis-shell:get-state",
  "themis-shell:pick-repo",
  "themis-shell:pick-python",
  "themis-shell:pick-kit",
  "themis-shell:pick-transcript-dir",
  "themis-shell:save-settings",
  "themis-shell:start-service",
  "themis-shell:restart-service",
  "themis-shell:open-external",
]);

// 服务状态事件（主进程 → 页面的单向推送）：与顶层 shell-preload.js 里的字面量同值。
// 它不进 SHELL_CHANNELS——不是 invoke 通道，不注册 ipcMain.handle。
const SERVICE_STATE_CHANNEL = "themis-shell:service-state";

// 外壳外观读取（同步读）与外观事件（主进程 → 页面推送，webContents.send）：
// 都不是 invoke 通道，不进 SHELL_CHANNELS、不注册 ipcMain.handle。接线在 main.js。
const SHELL_APPEARANCE_CHANNEL = "themis-shell:get-appearance";
const SHELL_APPEARANCE_EVENT = "themis-shell:appearance";

// 每个通道转交的主进程方法与它的实参个数：多余的参数丢掉（preload 已按声明转发，这里是第二道）
const SHELL_METHOD = {
  "themis-shell:get-state": "getState",
  "themis-shell:pick-repo": "pickRepo",
  "themis-shell:pick-python": "pickPython",
  "themis-shell:pick-kit": "pickKit",
  "themis-shell:pick-transcript-dir": "pickTranscriptDir",
  "themis-shell:save-settings": "saveSettings",
  "themis-shell:start-service": "startService",
  "themis-shell:restart-service": "restartService",
  "themis-shell:open-external": "openExternal",
};
const SHELL_ARITY = {
  "themis-shell:get-state": 0,
  "themis-shell:pick-repo": 0,
  "themis-shell:pick-python": 0,
  "themis-shell:pick-kit": 0,
  "themis-shell:pick-transcript-dir": 0,
  "themis-shell:save-settings": 1,
  "themis-shell:start-service": 1,
  "themis-shell:restart-service": 0,
  "themis-shell:open-external": 1,
};

// 来源三条件都满足才放行：发送者就是这个窗口的 webContents、frame 非空、frame 当前显示的确实是外壳页地址
function shellSenderAllowed(event, contents) {
  if (event.sender !== contents) return false;
  const frame = event.senderFrame;
  if (frame === null || frame === undefined) return false;
  return isShellPageUrl(frame.url);
}

// 处理器一律不抛错（与 src/ipc.js 同款）：来源不对的请求根本不进 api，api 抛错也不外传错误消息
function registerShellIpc(ipcMain, api, senderAllowed) {
  for (const channel of SHELL_CHANNELS) {
    ipcMain.handle(channel, async (event, ...args) => {
      if (!senderAllowed(event)) return { ok: false, reason: "forbidden" };
      const name = SHELL_METHOD[channel];
      try {
        return await api[name](...args.slice(0, SHELL_ARITY[channel]));
      } catch {
        return { ok: false, reason: "internal" };
      }
    });
  }
}

module.exports = {
  SHELL_CHANNELS,
  SERVICE_STATE_CHANNEL,
  SHELL_APPEARANCE_CHANNEL,
  SHELL_APPEARANCE_EVENT,
  registerShellIpc,
  shellSenderAllowed,
};
