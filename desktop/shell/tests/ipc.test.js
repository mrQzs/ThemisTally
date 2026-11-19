"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { HOST_CHANNELS, HOST_APPEARANCE_CHANNEL, HOST_APPEARANCE_EVENT, registerHostIpc } = require("../src/ipc.js");

const CHANNELS = [
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
  "themis-host:open-settings",
  "themis-host:save-theme",
];
const SECRET = "ipc-secret-" + crypto.randomBytes(8).toString("hex");
const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:8123/app" } };

function fakeIpcMain() {
  const handlers = {};
  let onCalls = 0;
  const ipcMain = {
    handle: (channel, fn) => {
      assert.ok(!(channel in handlers), "重复注册通道 " + channel);
      handlers[channel] = fn;
    },
    on: () => {
      onCalls += 1;
    },
  };
  return { ipcMain, handlers, onCalls: () => onCalls };
}

function okHost(calls) {
  return {
    reauth: async () => {
      calls.push(["reauth", []]);
      return { ok: true };
    },
    openSecretWindow: async (url, jobId) => {
      calls.push(["openSecretWindow", [url, jobId]]);
      return { ok: true };
    },
    openExternal: async (url) => {
      calls.push(["openExternal", [url]]);
      return { ok: true };
    },
    reveal: async (relPath) => {
      calls.push(["reveal", [relPath]]);
      return { ok: true };
    },
    notify: async (kind) => {
      calls.push(["notify", [kind]]);
      return { ok: true };
    },
    openSettings: async () => {
      calls.push(["openSettings", []]);
      return { ok: true };
    },
    saveTheme: async (pref) => {
      calls.push(["saveTheme", [pref]]);
      return { ok: true };
    },
  };
}

test("HOST_CHANNELS 冻结且恰好七个，save-theme 在末尾；外观常量逐字且不进 invoke 表", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS));
  assert.deepEqual([...HOST_CHANNELS], CHANNELS);
  assert.equal(HOST_APPEARANCE_CHANNEL, "themis-host:get-appearance");
  assert.equal(HOST_APPEARANCE_EVENT, "themis-host:appearance");
  assert.ok(!HOST_CHANNELS.includes(HOST_APPEARANCE_CHANNEL), "同步读取不进 invoke 表");
  assert.ok(!HOST_CHANNELS.includes(HOST_APPEARANCE_EVENT), "事件推送不进 invoke 表");
});

test("只用 ipcMain.handle 注册七个通道；来源不对回 forbidden 且不进 host", async () => {
  const { ipcMain, handlers, onCalls } = fakeIpcMain();
  const calls = [];
  let allowed = false;
  registerHostIpc(ipcMain, okHost(calls), (event) => allowed && event === EV);
  assert.equal(onCalls(), 0, "不许用 ipcMain 的 on");
  assert.deepEqual(Object.keys(handlers).sort(), CHANNELS.slice().sort());
  for (const channel of CHANNELS) {
    const r = await handlers[channel](EV);
    assert.deepEqual(r, { ok: false, reason: "forbidden" }, channel);
  }
  assert.equal(calls.length, 0, "来源不对不许进 host");
  allowed = true;
  assert.deepEqual(await handlers["themis-host:reauth"](EV), { ok: true });
  assert.deepEqual(calls, [["reauth", []]]);
});

test("来源对：转交 host，多余的实参丢掉", async () => {
  const { ipcMain, handlers } = fakeIpcMain();
  const calls = [];
  registerHostIpc(ipcMain, okHost(calls), () => true);
  assert.deepEqual(await handlers["themis-host:open-secret-window"](EV, "u", "j", "EXTRA"), { ok: true });
  assert.deepEqual(calls, [["openSecretWindow", ["u", "j"]]], "多余的实参要丢掉");
  assert.deepEqual(await handlers["themis-host:reveal"](EV, "a/b.txt", "EXTRA"), { ok: true });
  assert.deepEqual(calls[1], ["reveal", ["a/b.txt"]]);
  assert.deepEqual(await handlers["themis-host:reauth"](EV, "EXTRA"), { ok: true });
  assert.deepEqual(calls[2], ["reauth", []]);
  assert.deepEqual(await handlers["themis-host:open-settings"](EV, "EXTRA"), { ok: true });
  assert.deepEqual(calls[3], ["openSettings", []], "多余的实参要丢掉");
  assert.deepEqual(await handlers["themis-host:save-theme"](EV, "dark", "EXTRA"), { ok: true });
  assert.deepEqual(calls[4], ["saveTheme", ["dark"]], "save-theme 转交 saveTheme、多余实参丢掉");
});

test("host 抛错（同步与异步）：回 internal，错误消息不外传", async () => {
  const { ipcMain, handlers } = fakeIpcMain();
  const host = {
    reauth: () => {
      throw new Error("同步炸了 " + SECRET);
    },
    openSecretWindow: async () => {
      throw new Error("异步炸了 " + SECRET);
    },
    openExternal: async () => ({ ok: true }),
    reveal: async () => ({ ok: true }),
    notify: async () => ({ ok: true }),
    openSettings: async () => ({ ok: true }),
  };
  registerHostIpc(ipcMain, host, () => true);
  const r1 = await handlers["themis-host:reauth"](EV);
  assert.deepEqual(r1, { ok: false, reason: "internal" });
  const r2 = await handlers["themis-host:open-secret-window"](EV, "u", "j");
  assert.deepEqual(r2, { ok: false, reason: "internal" });
  assert.ok(!JSON.stringify(r1).includes(SECRET));
  assert.ok(!JSON.stringify(r2).includes(SECRET));
});

test("host 回拒绝的 Promise：同样不外传、不抛错", async () => {
  const { ipcMain, handlers } = fakeIpcMain();
  const host = {
    reauth: async () => ({ ok: true }),
    openSecretWindow: () => Promise.reject(new Error("拒绝 " + SECRET)),
    openExternal: async () => ({ ok: true }),
    reveal: async () => ({ ok: true }),
    notify: async () => ({ ok: true }),
    openSettings: async () => ({ ok: true }),
  };
  registerHostIpc(ipcMain, host, () => true);
  const r = await handlers["themis-host:open-secret-window"](EV, "u", "j");
  assert.deepEqual(r, { ok: false, reason: "internal" });
  assert.ok(!JSON.stringify(r).includes(SECRET));
});
