"use strict";

// sandbox 下的 preload 只能用 CommonJS 载入 electron 的 contextBridge 与 ipcRenderer，也不能拆成多个文件，
// 所以这里自包含：只 require electron，不 require 任何相对路径或 node: 模块。
const { contextBridge, ipcRenderer } = require("electron");

// 只暴露这一次：九个函数各自把声明的实参原样转交给固定通道，不做任何校验——参数越界由主进程判。
// 控制令牌只留在主进程，渲染进程经 IPC 也拿不到它。
// 外观事件的订阅：模块级只注册一个 ipcRenderer.on，每次 onAppearance 登记的是这条订阅里的一份，
// 退订只删自己那一条（用订阅集合，不依赖事件对象的移除接口），退订之后再发自然收不到。
const appearanceSubscriptions = new Set();
ipcRenderer.on("themis-host:appearance", (_event, appearance) => {
  for (const listener of [...appearanceSubscriptions]) listener(appearance);
});

contextBridge.exposeInMainWorld("themisHost", {
  reauth: () => ipcRenderer.invoke("themis-host:reauth"),
  openSecretWindow: (url, jobId) => ipcRenderer.invoke("themis-host:open-secret-window", url, jobId),
  openExternal: (url) => ipcRenderer.invoke("themis-host:open-external", url),
  reveal: (relPath) => ipcRenderer.invoke("themis-host:reveal", relPath),
  notify: (kind) => ipcRenderer.invoke("themis-host:notify", kind),
  openSettings: () => ipcRenderer.invoke("themis-host:open-settings"),
  // 保存主题：只转交 pref 这一个实参，返回信封对象（不拆信封，与既有六个函数同款）
  saveTheme: (pref) => ipcRenderer.invoke("themis-host:save-theme", pref),
  // 同步读当前外观：调用时才 sendSync，载入时不发；主进程答 null 时原样返回 null
  getAppearance: () => ipcRenderer.sendSync("themis-host:get-appearance"),
  // 订阅外观事件：同步返回退订函数，监听函数只收到外观对象一个实参
  onAppearance: (listener) => {
    appearanceSubscriptions.add(listener);
    return () => {
      appearanceSubscriptions.delete(listener);
    };
  },
});
