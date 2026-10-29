// 决策端点的替身（④b4b 的命令行契约用）：单独一个进程，测试用同步的 spawnSync 起被测命令时它照样能回话。
// node fake_endpoint.mjs <目录>：读 <目录>/replies.json（[{status, body}]，按次序回，用完了一直回最后一条），把端口写进
// <目录>/port，每个请求的正文作一行追加到 <目录>/requests.jsonl，Authorization 头（JSON，没有是 null）另追加到 <目录>/auth.jsonl。
// 只听 127.0.0.1；契约里的凭据都是假值。
import { appendFileSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";

const dir = process.argv[2];
const replies = JSON.parse(readFileSync(path.join(dir, "replies.json"), "utf8"));
let next = 0;
const server = http.createServer((request, response) => {
  const chunks = [];
  request.on("data", (chunk) => chunks.push(chunk));
  request.on("end", () => {
    appendFileSync(path.join(dir, "requests.jsonl"), `${Buffer.concat(chunks).toString("utf8")}${String.fromCharCode(10)}`);
    appendFileSync(path.join(dir, "auth.jsonl"), `${JSON.stringify(request.headers.authorization ?? null)}${String.fromCharCode(10)}`);
    const reply = replies[Math.min(next, replies.length - 1)];
    next += 1;
    const body = Buffer.from(reply.body, "utf8");
    response.writeHead(reply.status, { "Content-Type": "application/json", "Content-Length": body.length });
    response.end(body);
  });
});
server.listen(0, "127.0.0.1", () => {
  // 先写临时文件再改名：测试读到 port 时内容已经完整
  writeFileSync(path.join(dir, "port.tmp"), String(server.address().port));
  renameSync(path.join(dir, "port.tmp"), path.join(dir, "port"));
});
