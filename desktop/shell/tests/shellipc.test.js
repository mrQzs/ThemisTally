"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const shellipc = require("../src/shellipc.js");
const { SHELL_CHANNELS, SERVICE_STATE_CHANNEL, registerShellIpc, shellSenderAllowed } = shellipc;

const CHANNELS = [
  "themis-shell:get-state",
  "themis-shell:pick-repo",
  "themis-shell:pick-python",
  "themis-shell:pick-kit",
  "themis-shell:pick-transcript-dir",
  "themis-shell:save-settings",
  "themis-shell:start-service",
  "themis-shell:restart-service",
  "themis-shell:open-external",
];
const SPEC = {
  "themis-shell:get-state": ["getState", 0],
  "themis-shell:pick-repo": ["pickRepo", 0],
  "themis-shell:pick-python": ["pickPython", 0],
  "themis-shell:pick-kit": ["pickKit", 0],
  "themis-shell:pick-transcript-dir": ["pickTranscriptDir", 0],
  "themis-shell:save-settings": ["saveSettings", 1],
  "themis-shell:start-service": ["startService", 1],
  "themis-shell:restart-service": ["restartService", 0],
  "themis-shell:open-external": ["openExternal", 1],
};

test("SHELL_CHANNELS 冻结、恰好九个、名字与顺序逐字", () => {
  assert.ok(Object.isFrozen(SHELL_CHANNELS), "SHELL_CHANNELS 必须冻结");
  assert.deepEqual([...SHELL_CHANNELS], CHANNELS);
});

test("SERVICE_STATE_CHANNEL：值逐字、不进 SHELL_CHANNELS，与 shell-preload.js 里的字面量一致", () => {
  assert.equal(SERVICE_STATE_CHANNEL, "themis-shell:service-state");
  assert.ok(!SHELL_CHANNELS.includes(SERVICE_STATE_CHANNEL), "事件通道是主进程 → 页面的单向推送，不进 invoke 白名单");
  assert.deepEqual([...SHELL_CHANNELS], CHANNELS, "九个 invoke 通道的名字与顺序不变");
  // preload 不能 require 相对路径，通道名只能写字面量：两处一致由这里比对
  const preload = fs.readFileSync(path.resolve(__dirname, "..", "shell-preload.js"), "utf8");
  assert.ok(preload.includes('"themis-shell:service-state"'), "shell-preload.js 里要写字面量通道名");
});

function makeIpcMain() {
  const handlers = new Map();
  const onCalls = [];
  return {
    handlers,
    onCalls,
    handle: (ch, fn) => {
      if (handlers.has(ch)) throw new Error("通道被重复注册：" + ch);
      handlers.set(ch, fn);
    },
    on: (ch, fn) => onCalls.push([ch, fn]),
  };
}

function makeApi() {
  const calls = [];
  const behavior = {};
  const api = {};
  for (const [ch, [name]] of Object.entries(SPEC)) {
    api[name] = (...args) => {
      calls.push([name, args]);
      const b = behavior[name];
      if (b && b.throwSync) throw new Error("sync-boom-" + name);
      return Promise.resolve().then(() => {
        const b2 = behavior[name];
        if (b2 && b2.reject) throw new Error("async-boom-" + name);
        return (b2 && b2.result) || { ok: true, value: "value-of-" + name };
      });
    };
  }
  return { api, calls, behavior };
}

test("注册只用 handle：恰好九个通道，且没有注册任何 on 监听", () => {
  const im = makeIpcMain();
  const { api } = makeApi();
  registerShellIpc(im, api, () => true);
  assert.deepEqual([...im.handlers.keys()].sort(), [...CHANNELS].sort());
  assert.equal(im.onCalls.length, 0, "不许注册 on 监听：" + JSON.stringify(im.onCalls));
});

test("来源不对 → {ok:false,reason:forbidden}，一个 api 方法都不进", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => false);
  for (const ch of CHANNELS) {
    assert.deepEqual(await im.handlers.get(ch)({ marker: "event" }, "x"), { ok: false, reason: "forbidden" }, ch);
  }
  assert.equal(h.calls.length, 0, "被拒的请求不许进 api");
});

test("每个通道转交的方法与实参个数正确，多余实参丢掉", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  const payload = { theme: "dark" };
  for (const ch of CHANNELS) {
    const arity = SPEC[ch][1];
    const args = ["A0", "A1", "A2"];
    const r = await im.handlers.get(ch)({ marker: "event" }, ...args);
    assert.equal(r.ok, true, ch);
    const [name, got] = h.calls[h.calls.length - 1];
    assert.equal(name, SPEC[ch][0], ch + " 要转交给 " + SPEC[ch][0] + "，却调了 " + name);
    assert.equal(got.length, arity, ch + " 只许转交 " + arity + " 个实参，得到 " + got.length);
    for (let i = 0; i < arity; i += 1) assert.equal(got[i], "A" + i, ch);
  }
  assert.equal(h.calls.length, CHANNELS.length);
  h.calls.length = 0;
  await im.handlers.get("themis-shell:save-settings")({}, payload, "EXTRA");
  assert.deepEqual(h.calls[0][1], [payload]);
});

test("api 抛错（同步与异步）→ {ok:false,reason:internal}，不带错误消息", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  h.behavior.getState = { throwSync: true };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), { ok: false, reason: "internal" });
  h.behavior.getState = { reject: true };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), { ok: false, reason: "internal" });
  const raw = await im.handlers.get("themis-shell:get-state")({});
  assert.ok(!JSON.stringify(raw).includes("boom"), "错误消息不许外传：" + JSON.stringify(raw));
});

test("成功原样回 api 的 {ok:true,value}", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  const deep = { ok: true, value: { nested: [1, 2, { k: "v" }] } };
  h.behavior.getState = { result: deep };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), deep);
});

test("shellSenderAllowed：三条件都满足才放行", () => {
  const wc = { id: 7 };
  const frame = { url: "themis-shell://app/index.html#/first-run" };
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: frame }, wc), true);
});

test("shellSenderAllowed 四种反例", () => {
  const wc = { id: 7 };
  const other = { id: 8 };
  const frame = { url: "themis-shell://app/index.html#/first-run" };
  assert.equal(shellSenderAllowed({ sender: other, senderFrame: frame }, wc), false, "webContents 不对");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: null }, wc), false, "frame 为 null");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: undefined }, wc), false, "frame 为 undefined");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: { url: "javascript:alert(1)" } }, wc), false, "javascript: 地址");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: { url: "http://127.0.0.1:8123/page" } }, wc), false, "服务 origin 地址");
});
