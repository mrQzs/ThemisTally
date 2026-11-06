"use strict";

// 通道白名单：与 desktop/shell/preload.js 逐字一致，冻结之后不许增改
const HOST_CHANNELS = Object.freeze([
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
]);

// 每个通道转交的宿主函数与它的实参个数：多余的参数丢掉（preload 已按声明转发，这里是第二道）
const HOST_METHOD = {
  "themis-host:reauth": "reauth",
  "themis-host:open-secret-window": "openSecretWindow",
  "themis-host:open-external": "openExternal",
  "themis-host:reveal": "reveal",
  "themis-host:notify": "notify",
};
const HOST_ARITY = {
  "themis-host:reauth": 0,
  "themis-host:open-secret-window": 2,
  "themis-host:open-external": 1,
  "themis-host:reveal": 1,
  "themis-host:notify": 1,
};

// 处理器一律不抛错（invoke 的处理器抛错时错误可能被打到日志，也顺带把地址与令牌带出去），
// 来源不对的请求根本不进 host
function registerHostIpc(ipcMain, host, senderAllowed) {
  for (const channel of HOST_CHANNELS) {
    ipcMain.handle(channel, async (event, ...args) => {
      if (!senderAllowed(event)) return { ok: false, reason: "forbidden" };
      const name = HOST_METHOD[channel];
      try {
        return await host[name](...args.slice(0, HOST_ARITY[channel]));
      } catch {
        return { ok: false, reason: "internal" };
      }
    });
  }
}

module.exports = { HOST_CHANNELS, registerHostIpc };
