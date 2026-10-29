// native-lasterror.test.ts 的压力场景，单独一个 Bun 进程：带着分配压力反复起一个不存在的程序，数各个错误码。
// 修之前偶尔有一次取到 0（r3 §10 第 130 轮）。结果以一行 JSON 写到 stdout。
import { Win32Error, winProcessApi } from "../../src/native.ts";

const times = Number(process.argv[2] ?? "3000");
const api = await winProcessApi();
const nul = api.openInheritable("NUL", "read");
const std = { stdin: nul, stdout: nul, stderr: nul };
const counts: Record<string, number> = {};
let junk: unknown[] = [];
for (let i = 0; i < times; i += 1) {
  junk.push(Array.from({ length: 10_000 }, (_, x) => ({ x, s: String(x) })));
  if (junk.length > 50) junk = [];
  let key = "started";
  try {
    api.terminateProcess(api.spawnSuspended("C:/themis-no-such-dir/none.exe", null, null, std).process);
  } catch (error) {
    key = error instanceof Win32Error ? String(error.winerror) : "other";
  }
  counts[key] = (counts[key] ?? 0) + 1;
}
api.close(nul);
process.stdout.write(JSON.stringify(counts));
