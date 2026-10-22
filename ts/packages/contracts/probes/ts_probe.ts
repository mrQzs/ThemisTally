// 契约探针（TS 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果，与 python_probe.py 收发同样的 JSON。
// 同一份源码由 `node`（类型擦除）与 `bun` 各跑一遍。
import { existsSync } from "node:fs";
import { publishNew } from "@themis/base/publish";

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

/** 并发用例：先报“就绪”，等测试建好起跑文件再一起动手。 */
function waitFor(barrier: string): void {
  process.stderr.write("ready\n");
  const pause = new Int32Array(new SharedArrayBuffer(4));
  while (!existsSync(barrier)) Atomics.wait(pause, 0, 0, 1);
}

const request = JSON.parse(await readStdin()) as { op: string; path: string; data_b64: string; barrier?: string };
if (request.barrier) waitFor(request.barrier);
if (request.op !== "publish_new") {
  process.stdout.write(JSON.stringify({ ok: false, error: "UNKNOWN_OP" }));
  process.exitCode = 2;
} else {
  try {
    const published = publishNew(request.path, Buffer.from(request.data_b64, "base64"));
    process.stdout.write(JSON.stringify({ ok: true, published }));
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: (error as NodeJS.ErrnoException).code ?? "EUNKNOWN" }));
  }
}
