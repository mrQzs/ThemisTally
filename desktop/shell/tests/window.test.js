"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { partitionName, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("../src/window.js");

test("webPreferences 恰好十个键，没有 preload（凭据窗口用它）", () => {
  assert.deepEqual(webPreferences("sess-abc"), {
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    spellcheck: false,
    partition: "sess-abc",
  });
  assert.ok(!("preload" in webPreferences("sess-abc")));
});

test("mainWebPreferences：T025 的十键加 preload，其余不变（主窗口用它）", () => {
  const prefs = mainWebPreferences("sess-main", "C:/abs/path/preload.js");
  assert.deepEqual(prefs, {
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    spellcheck: false,
    partition: "sess-main",
    preload: "C:/abs/path/preload.js",
  });
  assert.equal(Object.keys(prefs).length, 11);
  assert.equal(Object.keys(webPreferences("sess-abc")).length, 10);
});

function fakeWin() {
  const win = new EventEmitter();
  win.destroyed = false;
  win.isDestroyed = () => win.destroyed;
  win.closeCalls = 0;
  win.close = () => {
    win.closeCalls += 1;
  };
  return win;
}

test("trackWindow：load 正常，closed 在 load 之前就挂好，返回 {closed, close}", async () => {
  const win = fakeWin();
  const tracked = await trackWindow(win, () => {
    assert.equal(win.listenerCount("closed"), 1, "load 运行时 closed 必须已挂上");
    return Promise.resolve();
  });
  assert.equal(typeof tracked.closed.then, "function");
  assert.equal(typeof tracked.close, "function");
  tracked.close();
  assert.equal(win.closeCalls, 1);
  win.destroyed = true;
  tracked.close();
  assert.equal(win.closeCalls, 1, "窗口已经没了就不再 close");
});

test("trackWindow：load 拒绝且 isDestroyed 为真 → 按窗口已关吞掉", async () => {
  const win = fakeWin();
  win.destroyed = true;
  await trackWindow(win, () => Promise.reject(new Error("boom")));
});

test("trackWindow：load 拒绝、closed 已触发而 isDestroyed 仍假 → 也吞掉", async () => {
  const win = fakeWin();
  await trackWindow(win, async () => {
    win.emit("closed");
    throw new Error("boom");
  });
});

test("trackWindow：load 拒绝、窗口还在且 closed 没触发 → 重新抛出同一个错误", async () => {
  const win = fakeWin();
  const boom = new Error("real-load-failure");
  await assert.rejects(
    () => trackWindow(win, () => Promise.reject(boom)),
    (err) => err === boom,
  );
});

test("partitionName：非空、不带 persist: 前缀、两次不同", () => {
  const a = partitionName();
  const b = partitionName();
  assert.equal(typeof a, "string");
  assert.ok(a.length > 0);
  assert.ok(!a.startsWith("persist:"), a);
  assert.notEqual(a, b);
});

test("isServiceUrl 正例", () => {
  assert.equal(isServiceUrl("http://127.0.0.1:8080/", "http://127.0.0.1:8080"), true);
  assert.equal(isServiceUrl("http://127.0.0.1:8080/app?x=1#h", "http://127.0.0.1:8080"), true);
});

test("isServiceUrl 反例：别的端口、localhost、https、userinfo、子域、特殊协议、非法串", () => {
  const origin = "http://127.0.0.1:8080";
  assert.equal(isServiceUrl("http://127.0.0.1:8081/", origin), false);
  assert.equal(isServiceUrl("http://localhost:8080/", origin), false);
  assert.equal(isServiceUrl("https://127.0.0.1:8080/", origin), false);
  assert.equal(isServiceUrl("http://127.0.0.1:8080@evil.example/", origin), false);
  assert.equal(isServiceUrl("http://127.0.0.1:8080.evil.example/", origin), false);
  assert.equal(isServiceUrl("javascript:alert(1)", origin), false);
  assert.equal(isServiceUrl("file:///C:/x", origin), false);
  assert.equal(isServiceUrl("data:text/html,hi", origin), false);
  assert.equal(isServiceUrl("about:blank", origin), false);
  assert.equal(isServiceUrl("not a url at all", origin), false);
});
