// 原生调用（FFI）：TS 迁移里唯一调操作系统原语的模块。设计文档 §3.3 要求 FFI 单列审计：
// 外部函数只在本文件声明，改动时在提交说明里点名。
//
// 外部函数与约定
//   Windows（kernel32.dll；句柄按 64 位整数传，INVALID_HANDLE_VALUE 为 -1）
//     CreateFileW(lpFileName: UTF-16LE 以 0 结尾, dwDesiredAccess = GENERIC_READ | GENERIC_WRITE,
//                 dwShareMode = FILE_SHARE_READ | FILE_SHARE_WRITE, lpSecurityAttributes = NULL,
//                 dwCreationDisposition = OPEN_ALWAYS, dwFlagsAndAttributes = FILE_ATTRIBUTE_NORMAL,
//                 hTemplateFile = NULL) -> HANDLE
//       不申请 DELETE 访问：Python 的 open(path, "a+b") 不带共享删除，带了它 Python 开着文件时这边打不开。
//     LockFileEx(hFile, dwFlags = LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY, dwReserved = 0,
//                nNumberOfBytesToLockLow = 1, nNumberOfBytesToLockHigh = 0, lpOverlapped: 32 字节、Offset = 0) -> BOOL
//       锁第 0 个字节、长度 1，与 Python 的 msvcrt.locking(fd, LK_NBLCK, 1)（_locking 即 LockFile）锁同一个区间，互斥。
//     UnlockFileEx(hFile, dwReserved = 0, 1, 0, lpOverlapped) -> BOOL
//     CloseHandle(hObject) -> BOOL
//   POSIX（libc；未实机验证，见迁移计划第 8.2 节）
//     flock(fd: int, operation = LOCK_EX | LOCK_NB 或 LOCK_UN) -> int，0 为成功
//
// 文件锁的语义与 kit_hub.file_lock（kit_hub.py:303-335）逐项一致：同一个哨兵文件（不存在就建，父目录也建），
// 第 0 字节、长度 1，非阻塞，每 10ms 重试，FILE_LOCK_SECONDS 秒超时，超时报“等文件锁超时：<路径>”。
// 持有锁的进程退出时操作系统自动放锁。
//
// 运行方式：Bun 下在本进程里经 bun:ffi 调用；Node 下（后备）每次拿锁起一个辅助进程（native-helper.ts，
// 第 ⑥ 步之后是单文件程序的隐藏子命令 __native）替本进程持锁。辅助进程用 stdin/stdout 每行一个 JSON 通信，
// stdin 一关就退出、由操作系统放锁；辅助进程意外退出时本进程把锁当作已丢，assertHeld 报错，不再开始新的写入。
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { closeSync, mkdirSync, openSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** kit_hub.FILE_LOCK_SECONDS：拿锁的都是几毫秒的读写，等这么久说明有进程卡死。 */
export const FILE_LOCK_SECONDS = 60;
const RETRY_MS = 10;

/** 等满了还没拿到：文字与 Python 的 HubError 相同。 */
export class FileLockTimeout extends Error {
  override readonly name = "FileLockTimeout";
  constructor(path: string) {
    super(`等文件锁超时：${path}`);
  }
}

/** 持锁的辅助进程意外退出：锁已经不在了，不能再开始新的写入。 */
export class FileLockLost extends Error {
  override readonly name = "FileLockLost";
}

export interface FileLock {
  /** 写入之前调用：锁已丢就报 FileLockLost。 */
  assertHeld(): void;
  release(): Promise<void>;
  /** 经辅助进程拿的锁：辅助进程的编号（进程内拿的没有）。 */
  readonly helperPid?: number;
}

const isBun = typeof (globalThis as { Bun?: unknown }).Bun !== "undefined";

function sleep(milliseconds: number): Promise<void> {
  return new Promise((done) => setTimeout(done, milliseconds));
}

// ---------------------------------------------------------------------------
// 进程内（Bun FFI）
// ---------------------------------------------------------------------------

interface PlatformLock {
  tryLock(): boolean;
  unlock(): void;
}

const GENERIC_READ = 0x80000000;
const GENERIC_WRITE = 0x40000000;
const FILE_SHARE_READ = 0x1;
const FILE_SHARE_WRITE = 0x2;
const OPEN_ALWAYS = 4;
const FILE_ATTRIBUTE_NORMAL = 0x80;
const LOCKFILE_FAIL_IMMEDIATELY = 0x1;
const LOCKFILE_EXCLUSIVE_LOCK = 0x2;
const LOCK_EX = 2;
const LOCK_NB = 4;
const LOCK_UN = 8;

async function openPlatformLock(path: string): Promise<PlatformLock> {
  const ffi = await import("bun:ffi");
  const { FFIType } = ffi;
  if (process.platform === "win32") {
    const kernel32 = ffi.dlopen("kernel32.dll", {
      CreateFileW: { args: [FFIType.ptr, FFIType.u32, FFIType.u32, FFIType.ptr, FFIType.u32, FFIType.u32, FFIType.ptr], returns: FFIType.i64 },
      LockFileEx: { args: [FFIType.i64, FFIType.u32, FFIType.u32, FFIType.u32, FFIType.u32, FFIType.ptr], returns: FFIType.i32 },
      UnlockFileEx: { args: [FFIType.i64, FFIType.u32, FFIType.u32, FFIType.u32, FFIType.ptr], returns: FFIType.i32 },
      CloseHandle: { args: [FFIType.i64], returns: FFIType.i32 },
    });
    const call = kernel32.symbols as unknown as {
      CreateFileW(name: number, access: number, share: number, security: null, disposition: number, flags: number, template: null): bigint;
      LockFileEx(handle: bigint, flags: number, reserved: number, low: number, high: number, overlapped: number): number;
      UnlockFileEx(handle: bigint, reserved: number, low: number, high: number, overlapped: number): number;
      CloseHandle(handle: bigint): number;
    };
    const name = Buffer.from(`${path}\0`, "utf16le");
    const handle = call.CreateFileW(
      ffi.ptr(name),
      GENERIC_READ | GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE,
      null,
      OPEN_ALWAYS,
      FILE_ATTRIBUTE_NORMAL,
      null,
    );
    if (handle === -1n || handle === 0n) {
      kernel32.close();
      throw new Error(`打不开锁文件：${path}`);
    }
    // OVERLAPPED（x64，32 字节）：Internal 0–7、InternalHigh 8–15、Offset 16–19、OffsetHigh 20–23、hEvent 24–31，全 0
    const overlapped = new Uint8Array(32);
    return {
      tryLock: () => call.LockFileEx(handle, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, ffi.ptr(overlapped)) !== 0,
      unlock: () => {
        call.UnlockFileEx(handle, 0, 1, 0, ffi.ptr(overlapped));
        call.CloseHandle(handle);
        kernel32.close();
      },
    };
  }
  const libc = ffi.dlopen(process.platform === "darwin" ? "libc.dylib" : "libc.so.6", {
    flock: { args: [FFIType.i32, FFIType.i32], returns: FFIType.i32 },
  });
  const flock = (libc.symbols as unknown as { flock(fd: number, operation: number): number }).flock;
  const fd = openSync(path, "a+");
  return {
    tryLock: () => flock(fd, LOCK_EX | LOCK_NB) === 0,
    unlock: () => {
      flock(fd, LOCK_UN);
      closeSync(fd);
      libc.close();
    },
  };
}

async function acquireInProcess(path: string, waitSeconds: number): Promise<FileLock> {
  mkdirSync(dirname(path), { recursive: true });
  const lock = await openPlatformLock(path);
  const deadline = performance.now() + waitSeconds * 1000;
  while (!lock.tryLock()) {
    if (performance.now() >= deadline) {
      lock.unlock();
      throw new FileLockTimeout(path);
    }
    await sleep(RETRY_MS);
  }
  let held = true;
  return {
    assertHeld: () => {
      if (!held) throw new FileLockLost(`文件锁已经释放：${path}`);
    },
    release: async () => {
      if (!held) return;
      held = false;
      lock.unlock();
    },
  };
}

// ---------------------------------------------------------------------------
// 辅助进程（Node 后备）
// ---------------------------------------------------------------------------

/** 辅助进程的命令：环境变量 THEMIS_NATIVE_CMD（JSON 数组）优先，缺省用 bun 跑 native-helper.ts。 */
function helperCommand(): string[] {
  const configured = process.env["THEMIS_NATIVE_CMD"];
  if (configured) return JSON.parse(configured) as string[];
  return ["bun", resolve(dirname(fileURLToPath(import.meta.url)), "native-helper.ts")];
}

/** 读辅助进程 stdout 的下一行（JSON）。 */
function nextLine(child: ChildProcessWithoutNullStreams): Promise<Record<string, unknown>> {
  return new Promise((done, fail) => {
    let buffer = "";
    const onData = (chunk: Buffer): void => {
      buffer += chunk.toString("utf8");
      const end = buffer.indexOf("\n");
      if (end < 0) return;
      cleanup();
      done(JSON.parse(buffer.slice(0, end)) as Record<string, unknown>);
    };
    const onExit = (code: number | null): void => {
      cleanup();
      fail(new FileLockLost(`文件锁的辅助进程退出了（退出码 ${String(code)}）`));
    };
    const cleanup = (): void => {
      child.stdout.off("data", onData);
      child.off("exit", onExit);
    };
    child.stdout.on("data", onData);
    child.on("exit", onExit);
  });
}

async function acquireThroughHelper(path: string, waitSeconds: number): Promise<FileLock> {
  const [command, ...args] = helperCommand();
  const child = spawn(command ?? "bun", [...args, "__native"], { stdio: ["pipe", "pipe", "pipe"] });
  let alive = true;
  child.on("exit", () => {
    alive = false;
  });
  child.stdin.write(`${JSON.stringify({ op: "lock", path, wait: waitSeconds })}\n`);
  const answer = await nextLine(child);
  if (answer["ok"] !== true) {
    child.stdin.end();
    if (answer["error"] === "timeout") throw new FileLockTimeout(path);
    throw new Error(`文件锁的辅助进程报错：${String(answer["message"] ?? answer["error"])}`);
  }
  let held = true;
  return {
    ...(child.pid === undefined ? {} : { helperPid: child.pid }),
    assertHeld: () => {
      if (!held) throw new FileLockLost(`文件锁已经释放：${path}`);
      if (!alive) throw new FileLockLost(`持有文件锁的辅助进程退出了，锁已丢：${path}`);
    },
    release: async () => {
      if (!held) return;
      held = false;
      if (!alive) return;
      child.stdin.write(`${JSON.stringify({ op: "unlock" })}\n`);
      await nextLine(child).catch(() => ({}));
      child.stdin.end();
    },
  };
}

// ---------------------------------------------------------------------------
// 对外接口
// ---------------------------------------------------------------------------

/** 拿 path 上的文件锁（kit_hub.file_lock）。Bun 下进程内拿，Node 下经辅助进程拿。 */
export async function acquireFileLock(path: string, waitSeconds: number = FILE_LOCK_SECONDS): Promise<FileLock> {
  return isBun ? acquireInProcess(path, waitSeconds) : acquireThroughHelper(path, waitSeconds);
}

/** 拿着文件锁做一件事，做完（或出错）释放。 */
export async function withFileLock<T>(
  path: string,
  action: (lock: FileLock) => T | Promise<T>,
  waitSeconds: number = FILE_LOCK_SECONDS,
): Promise<T> {
  const lock = await acquireFileLock(path, waitSeconds);
  try {
    lock.assertHeld();
    return await action(lock);
  } finally {
    await lock.release();
  }
}

/** 辅助进程一侧：只在 Bun 下运行，进程内拿锁（native-helper.ts 调用）。 */
export const helperAcquire = acquireInProcess;
