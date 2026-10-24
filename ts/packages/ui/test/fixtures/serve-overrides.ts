// 测试入口（桌面端 T16 第 2 片）：第 1 片的 serve-entry 只覆盖 nonce 有效期；本片的读路由用例要把并发上限、队列
// 长度、各路由时限与替身的 python/kernel 一起交给 serveUi，所以另起一个入口（--pyargs-b64 加可选的
// --overrides-b64）。这些覆盖项只给测试入口，CLI 与环境变量碰不到。
import { initFileAttributes } from "@themis/base/native";
import { serveUi } from "../../src/server.ts";

await initFileAttributes();
const at = process.argv.indexOf("--pyargs-b64");
const encoded = at >= 0 ? process.argv[at + 1] : undefined;
const ot = process.argv.indexOf("--overrides-b64");
const raw = ot >= 0 ? process.argv[ot + 1] : undefined;
if (encoded === undefined) {
  process.stderr.write("ERROR: serve-overrides 只接受 --pyargs-b64 <base64>\n");
  process.exitCode = 2;
} else {
  const args = JSON.parse(Buffer.from(encoded, "base64").toString("utf8")) as Parameters<typeof serveUi>[0];
  const overrides =
    raw === undefined ? {} : (JSON.parse(Buffer.from(raw, "base64").toString("utf8")) as Parameters<typeof serveUi>[2]);
  process.exitCode = await serveUi(args, { stdout: process.stdout, stderr: process.stderr }, overrides);
}
