"use strict";

// sandbox 下的 preload 只能用 CommonJS 载入 electron 的 contextBridge 与 ipcRenderer，也不能拆成多个文件，
// 所以这里自包含：只 require electron，不 require 任何相对路径或 node: 模块。
const { contextBridge, ipcRenderer } = require("electron");

// 只暴露这一次：五个函数各自把声明的实参原样转交给固定通道，不做任何校验——参数越界由主进程判。
// 控制令牌只留在主进程，渲染进程经 IPC 也拿不到它。
contextBridge.exposeInMainWorld("themisHost", {
  reauth: () => ipcRenderer.invoke("themis-host:reauth"),
  openSecretWindow: (url, jobId) => ipcRenderer.invoke("themis-host:open-secret-window", url, jobId),
  openExternal: (url) => ipcRenderer.invoke("themis-host:open-external", url),
  reveal: (relPath) => ipcRenderer.invoke("themis-host:reveal", relPath),
  notify: (kind) => ipcRenderer.invoke("themis-host:notify", kind),
});
