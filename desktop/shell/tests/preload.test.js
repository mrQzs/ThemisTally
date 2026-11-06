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
        on: (...args) => listeners.push(args),
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, listeners, sends };
}

test("preload 只 require electron，且恰好一次 exposeInMainWorld(\"themisHost\")", () => {
  const { requires, exposes } = runPreload();
  assert.deepEqual(requires, ["electron"]);
  assert.equal(exposes.length, 1, JSON.stringify(exposes.map((e) => e[0])));
  assert.equal(exposes[0][0], "themisHost");
});

test("暴露面恰好五个函数、没有 openSettings", () => {
  const { exposes } = runPreload();
  const api = exposes[0][1];
  assert.deepEqual(Object.keys(api).sort(), ["notify", "openExternal", "openSecretWindow", "reauth", "reveal"]);
  assert.equal("openSettings" in api, false, "不许有 openSettings（留给外壳页那一片）");
});

test("五个通道与 src/ipc.js 的 HOST_CHANNELS 逐字一致", () => {
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
  ]);
});

test("preload 自包含：不 require 相对路径，也没有 ipcRenderer 的监听与发送", () => {
  const { source, requires, listeners, sends } = runPreload();
  assert.deepEqual(requires, ["electron"]);
  assert.equal(listeners.length, 0);
  assert.equal(sends.length, 0);
  assert.ok(!/require\(\s*['"]\./.test(source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(source), "不许 require node: 模块");
  assert.ok(!/ipcRenderer\s*\.\s*on\s*\(/.test(source), "不许有 ipcRenderer 的监听");
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(source), "不许有 ipcRenderer 的发送");
  assert.equal((source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
});
