"use strict";

// 外壳页的 preload：sandbox 下只能用注入的 require 载入 electron，也不能拆成多个文件，所以这里自包含——
// 只 require electron，不 require 任何相对路径或 node: 模块。只暴露 window.themisShell（不碰服务页的宿主接口）；
// 外壳分支不起服务，本来就没有控制令牌，页面经 IPC 也拿不到。
const { contextBridge, ipcRenderer } = require("electron");

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
  // 本片不发事件：on 同步回退订函数，不发 IPC、不注册监听（服务状态在下一片接真行为）
  on: () => () => {},
});
