"use strict";

const http = require("node:http");
const crypto = require("node:crypto");

// 假的本地控制服务：只在本机 127.0.0.1 上监听（端口由系统分配），记下每个请求的方法、路径、头与正文，
// 行为由 state 切换。供 tests/control.test.js 与 tests/host.test.js 驱动 src/control.js 与 src/host.js。
// 文件名不叫 *.test.js：node --test 只跑 *.test.js，夹具不能混进去。
function createFakeControlServer() {
  const hits = [];
  const sockets = new Set();
  const nonce = crypto.randomBytes(16).toString("hex");
  const state = {
    bootstrapStatus: 200,
    // null → 回正确的信封；否则原样回这个正文（用来喂非 JSON、ok 不是 true、坏 data.bootstrap）
    bootstrapBody: null,
    bootstrapHang: false,
    cancelStatus: 200,
    cancelDestroy: false,
  };

  const api = {
    hits,
    state,
    origin: "",
    bootstrapUrl: "",
    reset() {
      state.bootstrapStatus = 200;
      state.bootstrapBody = null;
      state.bootstrapHang = false;
      state.cancelStatus = 200;
      state.cancelDestroy = false;
      hits.length = 0;
    },
    cancels() {
      return hits.filter((h) => h.url.indexOf("/cancel") !== -1);
    },
    async listen() {
      await new Promise((resolve) => {
        api.server.listen(0, "127.0.0.1", resolve);
      });
      api.origin = `http://127.0.0.1:${api.server.address().port}`;
      api.bootstrapUrl = `${api.origin}/bootstrap/${nonce}`;
      return api.origin;
    },
    async close() {
      for (const socket of Array.from(sockets)) socket.destroy();
      await new Promise((resolve) => {
        api.server.close(() => resolve());
      });
    },
  };

  api.server = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      hits.push({
        method: req.method,
        url: req.url,
        headers: req.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      });
      if (req.url === "/control/bootstrap") {
        if (state.bootstrapHang) return; // 不回：让客户端按自己的时限超时
        res.writeHead(state.bootstrapStatus, { "content-type": "application/json" });
        res.end(
          state.bootstrapBody === null
            ? JSON.stringify({ ok: true, data: { bootstrap: api.bootstrapUrl } })
            : state.bootstrapBody,
        );
        return;
      }
      if (state.cancelDestroy) {
        res.destroy();
        return;
      }
      res.writeHead(state.cancelStatus, { "content-type": "text/plain" });
      res.end("cancel-done");
    });
  });
  api.server.on("connection", (socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
  });

  return api;
}

module.exports = { createFakeControlServer };
