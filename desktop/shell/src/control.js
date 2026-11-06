"use strict";

const http = require("node:http");

// 控制接口的请求：只连 127.0.0.1（端口取自已校验的服务源），POST 带控制令牌头，不写正文、
// 不带 Origin 与 Cookie——控制路由不读正文、不做 CSRF，缺 Origin 放行，Node 自动写的 Host 是
// 127.0.0.1:<端口>，正好是服务认得的形状。agent:false 不留长连接，免得拖住服务关停与测试退出。
function postControl(options) {
  const { origin, control, path, timeoutMs = 10000 } = options;
  return new Promise((resolve, reject) => {
    let port;
    try {
      port = Number(new URL(origin).port);
    } catch {
      reject(new Error("控制请求的服务源不是合法的地址"));
      return;
    }
    const request = http.request(
      {
        host: "127.0.0.1",
        port,
        method: "POST",
        path,
        headers: { "x-themis-control": control },
        agent: false,
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          clearTimeout(timer);
          resolve({ status: response.statusCode, body: Buffer.concat(chunks).toString("utf8") });
        });
      },
    );
    const timer = setTimeout(() => {
      request.destroy(new Error("控制请求超时"));
    }, timeoutMs);
    request.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    request.end();
  });
}

module.exports = { postControl };
