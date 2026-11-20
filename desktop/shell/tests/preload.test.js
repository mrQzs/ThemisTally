"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { HOST_CHANNELS } = require("../src/ipc.js");

// preload 跑在 sandbox 里，只能用注入的 require 载入 electron；测试文件里因此不出现
// 「require electron」这个字面串（T025 门禁 S03 扫 tests/**），模块名字面量写成 "electron"。
function runPreload() {
  const source = fs.readFileSync(path.join(__dirname, "..", "preload.js"), "utf8");
  const requires = [];
  const exposes = [];
  const invokes = [];
  const syncs = [];
  const listeners = [];
  const sends = [];
  const fakeRequire = (name) => {
    requires.push(name);
    assert.equal(name, "electron", "preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: {
        exposeInMainWorld: (apiName, api) => exposes.push([apiName, api]),
      },
      ipcRenderer: {
        invoke: async (...args) => {
          invokes.push(args);
          return { ok: true };
        },
        sendSync: (...args) => {
          syncs.push(args);
          return { theme: "light", density: "compact" };
        },
        on: (...args) => listeners.push(args),
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, syncs, listeners, sends };
}

test("preload 只 require electron，且恰好一次 exposeInMainWorld(\"themisHost\")", () => {
  const { requires, exposes } = runPreload();
  assert.deepEqual(requires, ["electron"]);
  assert.equal(exposes.length, 1, JSON.stringify(exposes.map((e) => e[0])));
  assert.equal(exposes[0][0], "themisHost");
});

test("暴露面恰好十二个函数、含 openSettings 与三个新成员", () => {
  const { exposes } = runPreload();
  const api = exposes[0][1];
  assert.deepEqual(Object.keys(api).sort(), [
    "addRepo", "getAppearance", "listRepos", "notify", "onAppearance", "openExternal",
    "openSecretWindow", "openSettings", "reauth", "reveal", "saveTheme", "switchRepo",
  ]);
  assert.equal(typeof api.openSettings, "function");
});

test("十个通道与 src/ipc.js 的 HOST_CHANNELS 逐字一致", () => {
  const { source } = runPreload();
  for (const channel of HOST_CHANNELS) {
    assert.ok(source.includes(`"${channel}"`) || source.includes(`'${channel}'`), "preload 缺通道 " + channel);
  }
});

test("每个函数只把声明的实参原样转交给固定通道，多余实参丢掉", () => {
  const { exposes, invokes } = runPreload();
  const api = exposes[0][1];
  const url = "http://127.0.0.1:8123/" + "a".repeat(32);
  const jobId = "b".repeat(43);
  api.reauth();
  api.reauth("EXTRA");
  api.openSecretWindow(url, jobId);
  api.openSecretWindow(url, jobId, "EXTRA");
  api.openExternal("https://x.example/a");
  api.openExternal("https://x.example/a", "EXTRA");
  api.reveal("a/b.txt");
  api.reveal("a/b.txt", "EXTRA");
  api.notify("attempt-finished");
  api.notify("awaiting-review", "EXTRA");
  api.openSettings();
  api.openSettings("EXTRA");
  api.saveTheme("dark");
  api.saveTheme("light", "EXTRA");
  assert.deepEqual(invokes, [
    ["themis-host:reauth"],
    ["themis-host:reauth"],
    ["themis-host:open-secret-window", url, jobId],
    ["themis-host:open-secret-window", url, jobId],
    ["themis-host:open-external", "https://x.example/a"],
    ["themis-host:open-external", "https://x.example/a"],
    ["themis-host:reveal", "a/b.txt"],
    ["themis-host:reveal", "a/b.txt"],
    ["themis-host:notify", "attempt-finished"],
    ["themis-host:notify", "awaiting-review"],
    ["themis-host:open-settings"],
    ["themis-host:open-settings"],
    ["themis-host:save-theme", "dark"],
    ["themis-host:save-theme", "light"],
  ]);
});

test("三个新成员（T064）：只把声明的实参转交固定通道，实参个数 0/1/0、多余实参丢掉", async () => {
  const { exposes, invokes } = runPreload();
  const api = exposes[0][1];
  await api.listRepos();
  await api.listRepos("EXTRA");
  await api.switchRepo("repo-b");
  await api.switchRepo("repo-b", "EXTRA");
  await api.addRepo();
  await api.addRepo("EXTRA");
  assert.deepEqual(invokes.slice(-6), [
    ["themis-host:list-repos"],
    ["themis-host:list-repos"],
    ["themis-host:switch-repo", "repo-b"],
    ["themis-host:switch-repo", "repo-b"],
    ["themis-host:add-repo"],
    ["themis-host:add-repo"],
  ], "实参个数照声明：0 / 1 / 0，多余的丢掉");
});

test("saveTheme：只转交这一个实参到固定通道，返回信封不拆", async () => {
  const { exposes, invokes } = runPreload();
  const api = exposes[0][1];
  const r = await api.saveTheme("dark");
  assert.deepEqual(r, { ok: true }, "与既有六函数同款：不拆信封");
  assert.deepEqual(invokes.slice(-1), [["themis-host:save-theme", "dark"]], "只转交一个实参");
});

test("getAppearance：走 sendSync、载入时不发、回值原样返回", () => {
  const { exposes, syncs } = runPreload();
  const api = exposes[0][1];
  assert.deepEqual(syncs, [], "preload 载入时不许发 sendSync");
  const got = api.getAppearance();
  assert.deepEqual(syncs, [["themis-host:get-appearance"]]);
  assert.deepEqual(got, { theme: "light", density: "compact" }, "回值原样返回");
});

test("onAppearance：同步返回退订函数、监听只收外观一个实参、退订只删自己那条", () => {
  const { exposes, listeners } = runPreload();
  const api = exposes[0][1];
  assert.equal(listeners.length, 1, "模块级恰好一个 ipcRenderer.on");
  const [channel, internal] = listeners[0];
  assert.equal(channel, "themis-host:appearance");
  assert.equal(typeof internal, "function");
  const a = [];
  const b = [];
  const offA = api.onAppearance((...args) => a.push(args));
  assert.equal(typeof offA, "function");
  api.onAppearance((...args) => b.push(args));
  internal({ marker: "electron-event" }, { theme: "dark", density: "standard" });
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  assert.equal(a[0].length, 1, "监听只收外观对象一个实参");
  assert.deepEqual(a[0][0], { theme: "dark", density: "standard" });
  assert.ok(!JSON.stringify(a[0]).includes("electron-event"), "不许把事件对象交给页面");
  offA();
  internal({}, { theme: "light", density: "compact" });
  assert.equal(a.length, 1, "退订之后不再收");
  assert.equal(b.length, 2, "另一条订阅不受影响");
});

test("preload 自包含：只 require electron；恰好一个 ipcRenderer.on(外观事件)、没有 ipcRenderer 的发送", () => {
  const { source, requires, listeners, sends } = runPreload();
  assert.deepEqual(requires, ["electron"]);
  assert.equal(listeners.length, 1, "模块级恰好一个 ipcRenderer.on（外观事件分发）");
  assert.equal(listeners[0][0], "themis-host:appearance");
  assert.equal(sends.length, 0, "不许有 ipcRenderer 的发送");
  assert.ok(!/require\(\s*['"]\./.test(source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(source), "不许 require node: 模块");
  assert.equal((source.match(/ipcRenderer\s*\.\s*on\s*\(/g) || []).length, 1, "只许一个 ipcRenderer.on");
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(source), "不许有 ipcRenderer 的发送");
  assert.equal((source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
});
