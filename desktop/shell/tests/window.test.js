"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { partitionName, webPreferences, isServiceUrl } = require("../src/window.js");

test("webPreferences 恰好十个键，没有 preload", () => {
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
