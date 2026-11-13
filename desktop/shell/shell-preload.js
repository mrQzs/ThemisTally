"use strict";

// 外壳页的 preload：sandbox 下只能用注入的 require 载入 electron，也不能拆成多个文件，所以这里自包含——
// 只 require electron，不 require 任何相对路径或 node: 模块。只暴露 window.themisShell（不碰服务页的宿主接口）。
const { contextBridge, ipcRenderer } = require("electron");

// 服务状态事件的通道：与 src/shellipc.js 的 SERVICE_STATE_CHANNEL 同值（preload 不能 require 相对路径，
// 只能在这里写字面量，两处一致由 tests/shellipc.test.js 比对）。
// 只注册一个 ipcRenderer.on：每次 on 登记的是这条订阅里的一份，退订只删自己那一条（不依赖
// removeListener/off），退订之后再发自然收不到。
const subscriptions = new Set();
ipcRenderer.on("themis-shell:service-state", (_event, state) => {
  for (const listener of [...subscriptions]) listener(state);
});

// 每个方法只把声明的实参转交固定通道，再拆信封：ok === true → resolve value；
// 否则 → 以 new Error(reason) reject（reason 只进 Error.message，不挂别的属性，主世界拿到的 Error 保留 message）
function call(channel, ...args) {
  return ipcRenderer.invoke(channel, ...args).then((envelope) => {
    if (envelope.ok === true) return envelope.value;
    throw new Error(envelope.reason);
  });
}

// 只暴露这一次：十个成员与 desktop/web/src/shellpages/themisShell.ts 的 interface ThemisShell 逐字一致
contextBridge.exposeInMainWorld("themisShell", {
  getState: () => call("themis-shell:get-state"),
  pickRepo: () => call("themis-shell:pick-repo"),
  pickPython: () => call("themis-shell:pick-python"),
  pickKit: () => call("themis-shell:pick-kit"),
  pickTranscriptDir: () => call("themis-shell:pick-transcript-dir"),
  saveSettings: (patch) => call("themis-shell:save-settings", patch),
  startService: (repo) => call("themis-shell:start-service", repo),
  restartService: () => call("themis-shell:restart-service"),
  openExternal: (url) => call("themis-shell:open-external", url),
  // 只认 service-state：别的事件名同步回一个空的退订函数，不注册、不抛错。
  // 监听函数只收到 state 一个实参（Electron 的事件对象不过桥），on 与退订都不发 IPC。
  on: (event, listener) => {
    if (event !== "service-state" || typeof listener !== "function") return () => {};
    subscriptions.add(listener);
    return () => {
      subscriptions.delete(listener);
    };
  },
});
