// 文件锁的辅助进程（Node 后备用）：只在 Bun 下运行，`bun native-helper.ts __native`；第 ⑥ 步之后是单文件程序的
// 隐藏子命令 __native。协议：stdin、stdout 每行一个 JSON。
//   {"op":"lock","path":…,"wait":秒}  → {"ok":true} 或 {"ok":false,"error":"timeout"|"error","message":…}
//   {"op":"unlock"}                    → {"ok":true}，然后退出
//   stdin 关闭（父进程退出）            → 立即退出，由操作系统放锁
//   {"op":"supervise","cmd":[…],"options":{…},"interrupted":布尔}（迁移计划第 8.2 节 ④a）
//                                      → 起子进程之后 {"spawned":pid}，结束之后 {"result":{…}}；interrupted 为真
//                                        （调用方开始之前就取消了）时不起子进程，直接交回 interrupted 的结果；
//                                        参数错误（Python 会抛 ValueError 的）给 {"error":{"kind","message"}}
//   {"op":"interrupt"}                 → 正在运行的 supervise 照中断处理（调用方收到 Ctrl+C 之类的信号时转发）
//   {"op":"cred_size","target":…}      → {"size":字节数或 null}，然后退出（凭据管理器，迁移第 ③a2 片；不读内容）
//   {"op":"cred_delete","target":…}    → {"deleted":布尔}，然后退出
//   {"op":"cred_read","target":…}      → {"blob":base64 或 null}，然后退出（决策会话的凭据，④b4；只经管道交回调用方）
//   {"op":"file","request":{…}}        → {"failure":null 或 {"winerror","message"}}，然后退出（Win32 的 MoveFileExW、
//                                        CreateDirectoryW，迁移第 ③ 步补；调用方同步等这一行）
//   {"op":"message","winerror":N}      → {"message":FormatMessageW 的原文}，然后退出（同上）
//   stdin 关闭（调用方死了）            → 立即退出：Job 句柄随进程关闭，KILL_ON_JOB_CLOSE 带走整棵树
// 外部函数都在 native.ts，本文件不直接调 FFI。
import "./harden.ts"; // 第一个 import：按名字起程序不查当前目录（第 77 轮）
import { createInterface } from "node:readline";
import { type FileLock, FileLockTimeout, type Win32FileOp, credentialBlobSize, credentialDelete, credentialRead, helperAcquire, initFileAttributes, win32ErrorMessage, win32FileOp } from "./native.ts";
import { PyCrash } from "./pyfmt.ts";
import { type InterruptFlag, type SuperviseOptions, helperSupervise } from "./supervise.ts";

function reply(message: Record<string, unknown>): void {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

let held: FileLock | null = null;
const interrupt: InterruptFlag = { interrupted: false };
const lines = createInterface({ input: process.stdin });
lines.on("line", (line) => {
  const request = JSON.parse(line) as {
    op: string; path?: string; wait?: number; cmd?: string[]; options?: SuperviseOptions; interrupted?: boolean;
  };
  if (request.op === "supervise") {
    if (request.interrupted === true) interrupt.interrupted = true; // 调用方开始之前就取消了：不起子进程
    const options: SuperviseOptions = { ...(request.options as SuperviseOptions), onSpawn: (pid) => reply({ spawned: pid }) };
    helperSupervise(request.cmd ?? [], options, interrupt).then(
      (result) => {
        reply({ result });
        process.exit(0);
      },
      (error: unknown) => {
        reply({
          error: error instanceof PyCrash
            ? { kind: error.kind, message: error.message }
            : { kind: "Error", message: String((error as Error).message) },
        });
        process.exit(0);
      },
    );
  } else if (request.op === "interrupt") {
    interrupt.interrupted = true;
  } else if (request.op === "file" || request.op === "message") {
    initFileAttributes().then(
      () => {
        const ask = request as { request?: Win32FileOp; winerror?: number };
        reply(request.op === "file" ? { failure: win32FileOp(ask.request as Win32FileOp) } : { message: win32ErrorMessage(Number(ask.winerror)) });
        process.exit(0);
      },
      (error: unknown) => {
        reply({ error: String((error as Error).message) });
        process.exit(0);
      },
    );
  } else if (request.op === "cred_size" || request.op === "cred_delete" || request.op === "cred_read") {
    const target = String((request as { target?: string }).target);
    const work: Promise<Record<string, unknown>> =
      request.op === "cred_size"
        ? credentialBlobSize(target).then((size) => ({ size }))
        : request.op === "cred_read"
          ? credentialRead(target).then((blob) => ({ blob: blob === null ? null : blob.toString("base64") }))
          : credentialDelete(target).then((deleted) => ({ deleted }));
    work.then(
      (answer) => {
        reply(answer);
        process.exit(0);
      },
      (error: unknown) => {
        reply({ error: String((error as Error).message) });
        process.exit(0);
      },
    );
  } else if (request.op === "lock" && held === null) {
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
