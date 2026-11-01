"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseHandshake } = require("../src/handshake.js");

const TOKEN = "ctrl-tok-XYZ";
const NONCE = "nonceABC";
const ORIGIN = "http://127.0.0.1:8123";

function okLine(over) {
  const obj = Object.assign({
    themis_ui: 1,
    bootstrap: ORIGIN + "/bootstrap/" + NONCE,
    origin: ORIGIN,
    control: TOKEN,
    pid: 4242,
  }, over || {});
  for (const key of Object.keys(over || {})) {
    if (over[key] === undefined) delete obj[key];
  }
  return JSON.stringify(obj);
}

async function expectError(line, msg) {
  const r = await Promise.resolve().then(() => parseHandshake(line));
  assert.equal(r.ok, false, JSON.stringify(r));
  assert.equal(r.error, msg, JSON.stringify(r));
  // D04：错误不回显任何字段的值
  assert.ok(!r.error.includes(TOKEN), "错误回显了 control：" + r.error);
  assert.ok(!r.error.includes(NONCE), "错误回显了 nonce：" + r.error);
  assert.ok(!r.error.includes("4242"), "错误回显了 pid：" + r.error);
}

test("正例：合法握手（含行尾 \\r）", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine() + "\r"));
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.themis_ui, 1);
  assert.equal(r.value.bootstrap, ORIGIN + "/bootstrap/" + NONCE);
  assert.equal(r.value.origin, ORIGIN);
  assert.equal(r.value.control, TOKEN);
  assert.equal(r.value.pid, 4242);
});

test("多行输入只认第一行", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine() + "\n" + okLine({ themis_ui: 2, pid: 1 })));
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.themis_ui, 1);
  assert.equal(r.value.pid, 4242);
});

test("不是 JSON / 不是对象", async () => {
  await expectError("not json at all", "握手行不是 JSON 对象");
  await expectError("[1, 2]", "握手行不是 JSON 对象");
  await expectError("\"a string\"", "握手行不是 JSON 对象");
  await expectError("123", "握手行不是 JSON 对象");
});

test("缺字段：按 themis_ui、bootstrap、origin、control、pid 的次序", async () => {
  await expectError("{}", "握手缺字段：themis_ui、bootstrap、origin、control、pid");
  await expectError(okLine({ themis_ui: undefined, bootstrap: undefined }), "握手缺字段：themis_ui、bootstrap");
  await expectError(okLine({ control: undefined, pid: undefined }), "握手缺字段：control、pid");
});

test("协议版本不对", async () => {
  await expectError(okLine({ themis_ui: 2 }), "握手的协议版本不对");
  await expectError(okLine({ themis_ui: "1" }), "握手的协议版本不对");
});

test("origin 不严格匹配", async () => {
  await expectError(okLine({ origin: "http://localhost:8123" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "https://127.0.0.1:8123" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:8123/x" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:0" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:65536" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:99999" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
});

test("bootstrap 不在服务 origin 下", async () => {
  await expectError(okLine({ bootstrap: "http://127.0.0.1:9999/bootstrap/x" }), "握手的 bootstrap 不在服务 origin 下");
  await expectError(okLine({ bootstrap: "http://evil.example/bootstrap/x" }), "握手的 bootstrap 不在服务 origin 下");
  await expectError(okLine({ bootstrap: "not a url" }), "握手的 bootstrap 不在服务 origin 下");
});

test("control 不是非空字符串", async () => {
  await expectError(okLine({ control: "" }), "握手的 control 不是非空字符串");
  await expectError(okLine({ control: 123 }), "握手的 control 不是非空字符串");
});

test("pid 不是正整数", async () => {
  await expectError(okLine({ pid: 0 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: -5 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: 1.5 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: "4242" }), "握手的 pid 不是正整数");
});

test("边界端口照常通过", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine({ origin: "http://127.0.0.1:1", bootstrap: "http://127.0.0.1:1/bootstrap/x" })));
  assert.equal(r.ok, true, JSON.stringify(r));
});
