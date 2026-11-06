"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const crypto = require("node:crypto");
const { postControl } = require("../src/control.js");
const { createFakeControlServer } = require("./fixtures/fake-control-server.js");

const TOKEN = "ctrl-tok-" + crypto.randomBytes(12).toString("hex");

test("postControl：POST、路径、令牌头、无 Origin 无 Cookie、不发正文、不留长连接；状态与正文原样带回", async (t) => {
  const server = createFakeControlServer();
  t.after(() => server.close());
  const origin = await server.listen();
  server.state.bootstrapStatus = 201;
  server.state.bootstrapBody = "raw-body-XYZ";
  const r = await postControl({ origin, control: TOKEN, path: "/control/bootstrap", timeoutMs: 5000 });
  assert.equal(r.status, 201);
  assert.equal(r.body, "raw-body-XYZ");
  assert.equal(server.hits.length, 1, JSON.stringify(server.hits));
  const hit = server.hits[0];
  assert.equal(hit.method, "POST");
  assert.equal(hit.url, "/control/bootstrap");
  assert.equal(hit.headers["x-themis-control"], TOKEN);
  assert.equal(hit.headers.origin, undefined, "不许带 Origin 头：" + JSON.stringify(hit.headers));
  assert.equal(hit.headers.cookie, undefined, "不许带 Cookie");
  assert.equal(hit.body, "", "控制路由不读正文，客户端也不许写正文");
  assert.equal(hit.headers.host, "127.0.0.1:" + new URL(origin).port);
  assert.equal(hit.headers.connection, "close", "agent:false 的可观侧表现是 Connection: close");
});

test("postControl：连不上时 reject，错误里没有令牌", async (t) => {
  const gone = http.createServer(() => {});
  const port = await new Promise((resolve) => gone.listen(0, "127.0.0.1", () => resolve(gone.address().port)));
  await new Promise((resolve) => gone.close(() => resolve()));
  await assert.rejects(
    () => postControl({ origin: "http://127.0.0.1:" + port, control: TOKEN, path: "/x", timeoutMs: 3000 }),
    (err) => {
      const text = String(err && err.message ? err.message : err);
      assert.ok(!text.includes(TOKEN), "错误消息带令牌：" + text);
      return true;
    },
  );
});

test("postControl：超时按 timeoutMs 提前 reject，错误里没有令牌", async (t) => {
  const server = createFakeControlServer();
  t.after(() => server.close());
  const origin = await server.listen();
  server.state.bootstrapHang = true;
  const started = Date.now();
  await assert.rejects(
    () => postControl({ origin, control: TOKEN, path: "/control/bootstrap", timeoutMs: 300 }),
    (err) => {
      const text = String(err && err.message ? err.message : err);
      assert.ok(!text.includes(TOKEN), "错误消息带令牌：" + text);
      return true;
    },
  );
  assert.ok(Date.now() - started < 3000, "超时要按 timeoutMs 提前返回，不是等系统超时");
});
