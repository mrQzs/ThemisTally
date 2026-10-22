// 文件锁的辅助进程（Node 后备用）：只在 Bun 下运行，`bun native-helper.ts __native`；第 ⑥ 步之后是单文件程序的
// 隐藏子命令 __native。协议：stdin、stdout 每行一个 JSON。
//   {"op":"lock","path":…,"wait":秒}  → {"ok":true} 或 {"ok":false,"error":"timeout"|"error","message":…}
//   {"op":"unlock"}                    → {"ok":true}，然后退出
//   stdin 关闭（父进程退出）            → 立即退出，由操作系统放锁
// 外部函数都在 native.ts，本文件不直接调 FFI。
import { createInterface } from "node:readline";
import { type FileLock, FileLockTimeout, helperAcquire } from "./native.ts";

function reply(message: Record<string, unknown>): void {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

let held: FileLock | null = null;
const lines = createInterface({ input: process.stdin });
lines.on("line", (line) => {
  const request = JSON.parse(line) as { op: string; path?: string; wait?: number };
  if (request.op === "lock" && held === null) {
    helperAcquire(String(request.path), Number(request.wait ?? 60)).then(
      (lock) => {
        held = lock;
        reply({ ok: true });
      },
      (error: unknown) => {
        reply(
          error instanceof FileLockTimeout
            ? { ok: false, error: "timeout", message: error.message }
            : { ok: false, error: "error", message: String((error as Error).message) },
        );
        process.exit(0);
      },
    );
  } else if (request.op === "unlock") {
    const lock = held;
    held = null;
    void (lock?.release() ?? Promise.resolve()).then(() => {
      reply({ ok: true });
      process.exit(0);
    });
  } else if (request.op === "__test_keepalive") {
    // 测试专用：挂一个活动句柄，验证 stdin 关闭时照样退出（④a 的辅助程序会持有子进程句柄，事件循环不会自己空下来）
    setInterval(() => undefined, 1 << 30);
    reply({ ok: true });
  } else {
    reply({ ok: false, error: "error", message: `不认识的请求：${line}` });
  }
});
// 父进程退出：stdin 关闭。必须显式退出，不能等事件循环空下来：辅助进程手上有活动句柄（例如 ④a 起的子进程）时，
// 它不会自己退出，锁就一直不放。退出后由操作系统放锁。
lines.on("close", () => process.exit(0));
