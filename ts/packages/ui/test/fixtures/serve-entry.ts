// 测试入口（桌面端 T10）：先绑定 Windows 上的文件属性（junction 要靠它认出来），再起服务。只有 nonce 有效期可以被
// 覆盖（T7a 的「过期」一条要等 1.5 秒，不能等 60 秒）；CLI 与环境变量都碰不到这个覆盖项。
import { initFileAttributes } from "@themis/base/native";
import { serveUi } from "../../src/server.ts";

await initFileAttributes();
const at = process.argv.indexOf("--pyargs-b64");
const encoded = at >= 0 ? process.argv[at + 1] : undefined;
if (encoded === undefined) {
  process.stderr.write("ERROR: serve-entry 只接受 --pyargs-b64 <base64>\n");
  process.exitCode = 2;
} else {
  const args = JSON.parse(Buffer.from(encoded, "base64").toString("utf8")) as Parameters<typeof serveUi>[0];
  process.exitCode = await serveUi(args, { stdout: process.stdout, stderr: process.stderr }, { nonceTtlMs: 1500 });
}
