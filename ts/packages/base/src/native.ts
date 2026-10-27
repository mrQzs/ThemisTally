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
//     GetFullPathNameW(lpFileName: UTF-16LE 以 0 结尾, nBufferLength: 字符数, lpBuffer, lpFilePart = NULL) -> DWORD
//       （写进的字符数，不含结尾的 0；缓冲区不够时交回需要的大小，失败为 0）：Python 的 ntpath.abspath 就调它。它会去掉段尾的点
//       与空格，把末段的 nul（可带结尾的点、空格、冒号）映射成 NUL 设备，规则随系统版本变，所以照调、不手写。
//     GetFileAttributesW(lpFileName: UTF-16LE 以 0 结尾) -> DWORD，INVALID_FILE_ATTRIBUTES 为 0xFFFFFFFF
//       不跟随重解析点，与 Python os.lstat 的 st_file_attributes 同一个值。pi_dispatch.is_link_or_junction 把带
//       FILE_ATTRIBUTE_REPARSE_POINT（0x400）的条目一律当链接；Node 的 lstat 只认符号链接与 junction（第 ② 步）。
//   进程监督（迁移计划第 8.2 节 ④a；kernel32，结构体按 x64 布局）
//     CreateJobObjectW(NULL, NULL) -> HANDLE；SetInformationJobObject(hJob, JobObjectExtendedLimitInformation = 9,
//       JOBOBJECT_EXTENDED_LIMIT_INFORMATION（144 字节，LimitFlags 在第 16 字节 = KILL_ON_JOB_CLOSE 0x2000）, 144) -> BOOL
//     QueryInformationJobObject(hJob, JobObjectBasicAccountingInformation = 1, 48 字节（ActiveProcesses 在第 40
//       字节）, 48, NULL) -> BOOL；AssignProcessToJobObject(hJob, hProcess) -> BOOL；TerminateJobObject(hJob, 1) -> BOOL
//     CreateFileW（同上；进程监督另用 SECURITY_ATTRIBUTES（24 字节，bInheritHandle 在第 16 字节 = TRUE）开可继承的
//       句柄：标准流的文件与空设备 NUL）
//     InitializeProcThreadAttributeList(list, 1, 0, &size) -> BOOL；UpdateProcThreadAttribute(list, 0,
//       PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x20002, 句柄数组, 8 × 个数, NULL, NULL) -> BOOL；
//       DeleteProcThreadAttributeList(list)：只让标准流这几个句柄被子进程继承
//     CreateProcessW(lpApplicationName = NULL, 命令行（可写的 UTF-16LE）, NULL, NULL, bInheritHandles = TRUE,
//       CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
//       环境块, 工作目录, STARTUPINFOEXW（112 字节：cb、dwFlags = STARTF_USESTDHANDLES 在第 60 字节，三个标准流句柄在
//       第 80、88、96 字节，属性表在第 104 字节）, PROCESS_INFORMATION（24 字节）) -> BOOL
//       lpApplicationName 传 NULL，与 Python 的 subprocess 相同：碰到 .cmd、.bat 照样隐式起 cmd.exe
//     ResumeThread(hThread) -> DWORD（0xFFFFFFFF 为失败）；TerminateProcess(hProcess, 1) -> BOOL
//     WaitForSingleObject(hProcess, 毫秒) -> DWORD（0 为已结束）；GetExitCodeProcess(hProcess, &code) -> BOOL
//     GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT = 1, 进程组号) -> BOOL
//     AttachConsole(调用方的进程号) -> BOOL：Node 后备的辅助进程以 DETACHED_PROCESS 起，再挂到调用方的控制台上
//       （调用方没有控制台就挂不上），控制台的有无与进程内调用一致，CTRL_BREAK 发不发得出去也一致
//     GetLastError() -> DWORD：失败之后立即取（bun:ffi 下实测可靠：2、267、193 都对）
//     FormatMessageW(FROM_SYSTEM | IGNORE_INSERTS, NULL, 错误码, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), 缓冲,
//       字符数, NULL) -> DWORD：与 CPython 给 OSError 取文字的调用相同
//     CompareStringOrdinal(a, 长度, b, 长度, bIgnoreCase = TRUE) -> int（1 小于、2 等于、3 大于）：环境块的排序与
//       大小写不同的同名变量，与 CPython 的 getenvironment 用同一个比较
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
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { closeSync, mkdirSync, openSync, readFileSync, statSync } from "node:fs";
import { delimiter, dirname, isAbsolute, join, resolve } from "node:path";
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

/** TS 工作区的根（本文件在 ts/packages/base/src）。 */
const TS_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

/** pi_dispatch.find_bun：PATH 里的绝对路径上找 bun.exe，没有时取 PATH 上第一个 npm 垫片 bun.cmd 旁边的
 * node_modules/bun/bin/bun.exe；POSIX 找可执行的 bun。空项与相对路径跳过（当前目录里放一个 bun 就能顶替）。 */
export function findBunOnPath(env: NodeJS.ProcessEnv = process.env): string | null {
  const value = Object.entries(env).find(([name]) => (process.platform === "win32" ? name.toUpperCase() : name) === "PATH")?.[1] ?? "";
  const dirs = value.split(delimiter).filter((item) => item !== "" && isAbsolute(item));
  const isFile = (path: string): boolean => {
    try {
      return statSync(path).isFile();
    } catch {
      return false;
    }
  };
  if (process.platform !== "win32") return dirs.map((d) => join(d, "bun")).find(isFile) ?? null;
  const exe = dirs.map((d) => join(d, "bun.exe")).find(isFile);
  if (exe !== undefined) return exe;
  const shim = dirs.find((d) => isFile(join(d, "bun.cmd")));
  if (shim === undefined) return null;
  const candidate = join(shim, "node_modules", "bun", "bin", "bun.exe");
  return isFile(candidate) ? candidate : null;
}

/** 起 Bun 用哪一个可执行文件（与启动器同一个来源，themistally-15 复核 ④a）：环境变量 THEMIS_BUN；装好戳记里记的
 * bun_path（装依赖时用的那一个）；PATH 上照 find_bun 的规则找。不按名字起 "bun"：npm 全局装的 Bun 在 PATH 上只有
 * bun.cmd 之类的垫片，Node 不经 shell 起不了 .cmd。都找不到就报错。 */
export function bunExecutable(env: NodeJS.ProcessEnv = process.env): string {
  const configured = env["THEMIS_BUN"];
  if (configured) return configured;
  try {
    const stamp = JSON.parse(readFileSync(join(TS_ROOT, "node_modules", ".themis-installed"), "utf8")) as { bun_path?: unknown };
    if (typeof stamp.bun_path === "string" && statSync(stamp.bun_path).isFile()) return stamp.bun_path;
  } catch {
    // 没有戳记或戳记里的路径不在了：照 PATH 找
  }
  const found = findBunOnPath(env);
  if (found !== null) return found;
  throw new Error("找不到 Bun：没有设 THEMIS_BUN，装好戳记里没有可用的 bun_path，PATH 上也没有 bun.exe 或 npm 的 bun.cmd 垫片");
}

/** 辅助进程的命令：环境变量 THEMIS_NATIVE_CMD（JSON 数组）优先，缺省用 bunExecutable() 跑 native-helper.ts。 */
export function nativeHelperCommand(): string[] {
  const configured = process.env["THEMIS_NATIVE_CMD"];
  if (configured) return JSON.parse(configured) as string[];
  return [bunExecutable(), resolve(dirname(fileURLToPath(import.meta.url)), "native-helper.ts")];
}

/** 读辅助进程 stdout 的下一行（JSON）。辅助进程起不来（spawn 的 error 事件）时报清楚的错，不让调用方整个崩掉。 */
function nextLine(child: ChildProcessWithoutNullStreams, command: string): Promise<Record<string, unknown>> {
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
    const onError = (error: Error): void => {
      cleanup();
      fail(new Error(`起不了文件锁的辅助进程（${command}）：${error.message}`));
    };
    const cleanup = (): void => {
      child.stdout.off("data", onData);
      child.off("exit", onExit);
      child.off("error", onError);
    };
    child.stdout.on("data", onData);
    child.on("exit", onExit);
    child.on("error", onError);
  });
}

async function acquireThroughHelper(path: string, waitSeconds: number): Promise<FileLock> {
  const [command, ...args] = nativeHelperCommand();
  const child = spawn(command ?? "bun", [...args, "__native"], { stdio: ["pipe", "pipe", "pipe"] });
  child.on("error", () => undefined); // 起不来时由 nextLine 报错；之后的 error 事件不再让进程崩掉
  child.stdin.on("error", () => undefined); // 辅助进程起不来时写 stdin 会 EPIPE
  let alive = true;
  child.on("exit", () => {
    alive = false;
  });
  child.stdin.write(`${JSON.stringify({ op: "lock", path, wait: waitSeconds })}\n`);
  const answer = await nextLine(child, command ?? "bun");
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
      await nextLine(child, command ?? "bun").catch(() => ({}));
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

// ---------------------------------------------------------------------------
// 文件属性（Windows，Bun FFI）
// ---------------------------------------------------------------------------

export const FILE_ATTRIBUTE_REPARSE_POINT = 0x400;
const INVALID_FILE_ATTRIBUTES = 0xffffffff;

/** undefined 或 null：没有绑定（还没初始化、Node 后备、非 Windows）。 */
let fullPathName: ((path: string) => string | null) | null | undefined;

/** GetFullPathNameW：没有绑定、路径里有 NUL 字符或调用失败时为 null（调用方退回自己的算法）。 */
export function win32FullPathName(value: string): string | null {
  if (!fullPathName || value.includes(String.fromCharCode(0))) return null;
  return fullPathName(value);
}

/** undefined：还没初始化；null：没有绑定（Node 后备、非 Windows）。 */
let getFileAttributes: ((path: string) => number) | null | undefined;

/** 程序开头调一次：Bun 在 Windows 上绑定 GetFileAttributesW，之后 fileAttributes 同步可用。 */
export async function initFileAttributes(): Promise<void> {
  if (getFileAttributes !== undefined) return;
  if (!isBun || process.platform !== "win32") {
    getFileAttributes = null;
    fullPathName = null;
    win32Files = null;
    win32Message = null;
    return;
  }
  const ffi = await import("bun:ffi");
  const T = ffi.FFIType;
  const kernel32 = ffi.dlopen("kernel32.dll", {
    GetFileAttributesW: { args: [T.ptr], returns: T.u32 },
    GetFullPathNameW: { args: [T.ptr, T.u32, T.ptr, T.ptr], returns: T.u32 },
    MoveFileExW: { args: [T.ptr, T.ptr, T.u32], returns: T.i32 },
    CreateDirectoryW: { args: [T.ptr, T.ptr], returns: T.i32 },
    GetLastError: { args: [], returns: T.u32 },
    FormatMessageW: { args: [T.u32, T.ptr, T.u32, T.u32, T.ptr, T.u32, T.ptr], returns: T.u32 },
  });
  const call = kernel32.symbols as unknown as {
    GetFileAttributesW(name: number): number;
    GetFullPathNameW(name: number, size: number, buffer: number, part: null): number;
    MoveFileExW(src: number, dst: number, flags: number): number;
    CreateDirectoryW(path: number, security: null): number;
    GetLastError(): number;
    FormatMessageW(flags: number, source: null, id: number, language: number, buffer: number, size: number, args: null): number;
  };
  const wide = (text: string): Buffer => Buffer.from(`${text}\0`, "utf16le");
  getFileAttributes = (path) => call.GetFileAttributesW(ffi.ptr(wide(path)));
  fullPathName = (path) => {
    const name = wide(path); // 调用期间一直被引用
    for (let size = 1024; ; ) {
      const buffer = new Uint16Array(size);
      const written = call.GetFullPathNameW(ffi.ptr(name), size, ffi.ptr(buffer), null);
      if (written === 0) return null;
      if (written < size) return Buffer.from(buffer.buffer, 0, written * 2).toString("utf16le");
      size = written + 1;
    }
  };
  win32Message = (winerror) => {
    const buffer = new Uint16Array(2048);
    const n = call.FormatMessageW(0x1000 | 0x200, null, winerror, 0x0400, ffi.ptr(buffer), buffer.length, null);
    return Buffer.from(buffer.buffer, 0, n * 2).toString("utf16le");
  };
  const failure = (): Win32Failure => {
    const winerror = call.GetLastError(); // 失败之后立即取
    return { winerror, message: (win32Message as (code: number) => string)(winerror) };
  };
  win32Files = (request) => {
    // 缓冲区放在局部变量里，调用期间一直被引用
    if (request.op === "mkdir") {
      const path = wide(request.path);
      return call.CreateDirectoryW(ffi.ptr(path), null) ? null : failure();
    }
    const [src, dst] = [wide(request.src), wide(request.dst)];
    return call.MoveFileExW(ffi.ptr(src), ffi.ptr(dst), request.op === "replace" ? MOVEFILE_REPLACE_EXISTING : 0) ? null : failure();
  };
}

// ---------------------------------------------------------------------------
// Win32 的文件操作（迁移第 ③ 步补，themistally-15 复核查出）：配置中心会把 os.replace、os.rename、os.mkdir 的报错原样
// 写进输出，CPython 在 Windows 上直接调 Win32，文字是 [WinError N] 加 FormatMessageW。libuv 把错误码映射成 EPERM、
// EACCES 之类，反推不回原来的码（5 与 32 都会映射走），所以这里也直接调：Bun 下由 initFileAttributes 一起绑好、
// 同步调用；Node 下（后备，或入口没有先 init）每次同步起一个辅助进程问一次。
//   MoveFileExW(src, dst, flags) -> BOOL：os.replace 带 MOVEFILE_REPLACE_EXISTING，os.rename 不带
//   CreateDirectoryW(path, NULL) -> BOOL：os.mkdir
// ---------------------------------------------------------------------------

const MOVEFILE_REPLACE_EXISTING = 0x1;

export type Win32FileOp = { readonly op: "replace" | "rename"; readonly src: string; readonly dst: string } | { readonly op: "mkdir"; readonly path: string };

/** 失败时的 Windows 错误码与 FormatMessageW 的原文（未去掉末尾的换行与句点）。 */
export interface Win32Failure {
  readonly winerror: number;
  readonly message: string;
}

let win32Files: ((request: Win32FileOp) => Win32Failure | null) | null | undefined;
let win32Message: ((winerror: number) => string) | null | undefined;

/** 同步问一次辅助进程（Node 后备）：发一行 JSON，等它回一行再退出。 */
function askHelperSync(request: Record<string, unknown>): Record<string, unknown> {
  const [command, ...args] = nativeHelperCommand();
  const done = spawnSync(command ?? "bun", [...args, "__native"], { input: `${JSON.stringify(request)}\n`, encoding: "utf8", windowsHide: true });
  const line = (done.stdout ?? "").split("\n").find((text) => text.trim() !== "");
  if (done.error || !line) throw new Error(`辅助进程没有回答（${String(request["op"])}）：${done.error?.message ?? done.stderr}`);
  const answer = JSON.parse(line) as Record<string, unknown>;
  if (answer["error"] !== undefined) throw new Error(`辅助进程出错（${String(request["op"])}）：${String(answer["error"])}`);
  return answer;
}

/** 做一次 Win32 文件操作：成功为 null，失败给出错误码与文字。只在 Windows 上调用。 */
export function win32FileOp(request: Win32FileOp): Win32Failure | null {
  if (win32Files) return win32Files(request);
  return (askHelperSync({ op: "file", request })["failure"] as Win32Failure | null | undefined) ?? null;
}

/** FormatMessageW 给这个错误码的原文（未去掉末尾的换行与句点；跟着系统界面的语言）。只在 Windows 上调用。 */
export function win32ErrorMessage(winerror: number): string {
  if (win32Message) return win32Message(winerror);
  return String(askHelperSync({ op: "message", winerror })["message"]);
}

/** GetFileAttributesW 的值；没有绑定、或取不到（路径不存在等）时为 null，调用方退回 lstat。 */
export function fileAttributes(path: string): number | null {
  if (!getFileAttributes) return null;
  const value = getFileAttributes(path) >>> 0;
  return value === INVALID_FILE_ATTRIBUTES ? null : value;
}

// ---------------------------------------------------------------------------
// Windows 凭据管理器（迁移第 ③a2 片：config show、secret check、secret remove；advapi32，Bun FFI，Node 后备经辅助进程）
//   CredReadW(TargetName: UTF-16LE 以 0 结尾, Type = CRED_TYPE_GENERIC, Flags = 0, &PCREDENTIALW) -> BOOL
//   CredFree(PCREDENTIALW)；CredDeleteW(TargetName, CRED_TYPE_GENERIC, 0) -> BOOL
//   CREDENTIALW（x64）：Flags 0、Type 4、TargetName 8、Comment 16、LastWritten 24、CredentialBlobSize 32、CredentialBlob 40…
// 配置中心只要知道“这一项在不在、值是不是空的”：只取 CredentialBlobSize，不读、不拷贝凭据的内容。
// ---------------------------------------------------------------------------

const CRED_TYPE_GENERIC = 1;

interface CredentialApi {
  blobSize(target: string): number | null;
  remove(target: string): boolean;
}

let credentialApi: Promise<CredentialApi> | undefined;

async function bindCredentialApi(): Promise<CredentialApi> {
  const ffi = await import("bun:ffi");
  const { FFIType } = ffi;
  const advapi32 = ffi.dlopen("advapi32.dll", {
    CredReadW: { args: [FFIType.ptr, FFIType.u32, FFIType.u32, FFIType.ptr], returns: FFIType.i32 },
    CredDeleteW: { args: [FFIType.ptr, FFIType.u32, FFIType.u32], returns: FFIType.i32 },
    CredFree: { args: [FFIType.ptr], returns: FFIType.void },
  });
  const call = advapi32.symbols as unknown as {
    CredReadW(target: number, type: number, flags: number, out: number): number;
    CredDeleteW(target: number, type: number, flags: number): number;
    CredFree(credential: number): void;
  };
  return {
    blobSize(target) {
      const name = Buffer.from(`${target}\0`, "utf16le");
      const out = new BigUint64Array(1);
      if (!call.CredReadW(ffi.ptr(name), CRED_TYPE_GENERIC, 0, ffi.ptr(out))) return null;
      const credential = Number(out[0]);
      try {
        return ffi.read.u32(credential, 32);
      } finally {
        call.CredFree(credential);
      }
    },
    remove(target) {
      const name = Buffer.from(`${target}\0`, "utf16le");
      return call.CredDeleteW(ffi.ptr(name), CRED_TYPE_GENERIC, 0) !== 0;
    },
  };
}

/** 问一次辅助进程（Node 后备）：发一行 JSON，读一行回答。 */
async function askHelper(request: Record<string, unknown>): Promise<Record<string, unknown>> {
  const [command, ...args] = nativeHelperCommand();
  const child = spawn(command ?? "bun", [...args, "__native"], { stdio: ["pipe", "pipe", "pipe"] });
  child.on("error", () => undefined);
  child.stdin.on("error", () => undefined);
  child.stdin.write(`${JSON.stringify(request)}\n`);
  try {
    return await nextLine(child, command ?? "bun");
  } finally {
    child.stdin.end();
  }
}

/** 凭据管理器里 target 这一项的 CredentialBlobSize（字节数）；没有这一项、或不在 Windows 上时为 null。 */
export async function credentialBlobSize(target: string): Promise<number | null> {
  if (process.platform !== "win32") return null;
  if (!isBun) {
    const answer = await askHelper({ op: "cred_size", target });
    return typeof answer["size"] === "number" ? answer["size"] : null;
  }
  credentialApi ??= bindCredentialApi();
  return (await credentialApi).blobSize(target);
}

/** 删掉凭据管理器里 target 这一项；删掉了为 true。 */
export async function credentialDelete(target: string): Promise<boolean> {
  if (process.platform !== "win32") return false;
  if (!isBun) return (await askHelper({ op: "cred_delete", target }))["deleted"] === true;
  credentialApi ??= bindCredentialApi();
  return (await credentialApi).remove(target);
}

// ---------------------------------------------------------------------------
// 进程监督（迁移计划第 8.2 节 ④a；Windows，Bun FFI）
// 这里只做最薄的一层：每个调用照 Win32 的语义，失败时带 GetLastError 的错误码抛 Win32Error。run_supervised 的
// 语义（环境块、命令行、宽限、残留进程）在 supervise.ts。
// ---------------------------------------------------------------------------

/** Win32 调用失败：带 GetLastError 的错误码。 */
export class Win32Error extends Error {
  override readonly name = "Win32Error";
  readonly winerror: number;

  constructor(call: string, winerror: number) {
    super(`${call} 失败（错误码 ${winerror}）`);
    this.winerror = winerror;
  }
}

/** 交给子进程的三个标准流句柄（都要可继承）。 */
export interface StdHandles {
  readonly stdin: bigint;
  readonly stdout: bigint;
  readonly stderr: bigint;
}

export interface Spawned {
  readonly process: bigint;
  readonly thread: bigint;
  readonly pid: number;
}

/** 可继承句柄的打开方式：新建（已存在就失败，同 Python 的 "xb"）、清空重写、追加、只读（空设备 NUL）。 */
export type OpenHow = "create-new" | "truncate" | "append" | "read";

export interface WinProcessApi {
  createKillOnCloseJob(): bigint;
  openInheritable(path: string, how: OpenHow): bigint;
  /** 挂起创建、另起进程组；只让 std 这几个句柄被继承。environment 为 null 时继承本进程的环境。 */
  spawnSuspended(cmdline: string, environment: Buffer | null, cwd: string | null, std: StdHandles): Spawned;
  assign(job: bigint, process: bigint): boolean;
  resume(thread: bigint): boolean;
  terminateProcess(process: bigint): void;
  /** 等最多 milliseconds 毫秒；进程已结束为 true。 */
  exited(process: bigint, milliseconds: number): boolean;
  exitCode(process: bigint): number;
  /** 给进程组发 CTRL_BREAK：成功为 null，失败为错误码。 */
  ctrlBreak(pid: number): number | null;
  /** 挂到 pid 的控制台上（本进程须没有控制台）；挂上为 true。 */
  attachConsole(pid: number): boolean;
  terminateJob(job: bigint): void;
  /** Job 里还活着的进程数；查不到为 -1。 */
  activeProcesses(job: bigint): number;
  close(handle: bigint): void;
  /** CompareStringOrdinal(a, b, 不分大小写)：小于为负、等于为 0、大于为正。 */
  compareIgnoreCase(a: string, b: string): number;
  /** FormatMessageW 的原文（未去掉末尾的换行与句点）。 */
  message(winerror: number): string;
}

const CREATE_SUSPENDED = 0x4;
const CREATE_NEW_PROCESS_GROUP = 0x200;
const CREATE_UNICODE_ENVIRONMENT = 0x400;
const EXTENDED_STARTUPINFO_PRESENT = 0x80000;
const STARTF_USESTDHANDLES = 0x100;
const PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x20002n;
const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
const JOB_EXTENDED_LIMIT_INFORMATION = 9;
const JOB_BASIC_ACCOUNTING_INFORMATION = 1;
const FILE_APPEND_DATA = 0x4;
const CREATE_NEW = 1;
const CREATE_ALWAYS = 2;
const OPEN_EXISTING = 3;
const CTRL_BREAK_EVENT = 1;
const WAIT_OBJECT_0 = 0;
const INVALID_HANDLE = -1n;

let processApi: Promise<WinProcessApi> | undefined;

/** 让缓冲区活到这里：存进模块级变量（可观察的写入，JIT 不会删掉），下一次调用时才换掉。 */
let retained: unknown = null;
function retain(value: unknown): void {
  retained = value;
}

/** 进程监督要用的 Win32 调用（只在 Bun、Windows 下可用；进程里只绑定一次）。 */
export function winProcessApi(): Promise<WinProcessApi> {
  processApi ??= bindWinProcessApi();
  return processApi;
}

async function bindWinProcessApi(): Promise<WinProcessApi> {
  if (!isBun || process.platform !== "win32") throw new Error("进程监督的 Win32 调用只在 Bun、Windows 下可用");
  const ffi = await import("bun:ffi");
  const { FFIType: T } = ffi;
  const kernel32 = ffi.dlopen("kernel32.dll", {
    CreateJobObjectW: { args: [T.ptr, T.ptr], returns: T.i64 },
    SetInformationJobObject: { args: [T.i64, T.i32, T.ptr, T.u32], returns: T.i32 },
    QueryInformationJobObject: { args: [T.i64, T.i32, T.ptr, T.u32, T.ptr], returns: T.i32 },
    AssignProcessToJobObject: { args: [T.i64, T.i64], returns: T.i32 },
    TerminateJobObject: { args: [T.i64, T.u32], returns: T.i32 },
    CreateFileW: { args: [T.ptr, T.u32, T.u32, T.ptr, T.u32, T.u32, T.ptr], returns: T.i64 },
    InitializeProcThreadAttributeList: { args: [T.ptr, T.u32, T.u32, T.ptr], returns: T.i32 },
    UpdateProcThreadAttribute: { args: [T.ptr, T.u32, T.i64, T.ptr, T.i64, T.ptr, T.ptr], returns: T.i32 },
    DeleteProcThreadAttributeList: { args: [T.ptr], returns: T.i32 },
    CreateProcessW: { args: [T.ptr, T.ptr, T.ptr, T.ptr, T.i32, T.u32, T.ptr, T.ptr, T.ptr, T.ptr], returns: T.i32 },
    ResumeThread: { args: [T.i64], returns: T.u32 },
    TerminateProcess: { args: [T.i64, T.u32], returns: T.i32 },
    WaitForSingleObject: { args: [T.i64, T.u32], returns: T.u32 },
    GetExitCodeProcess: { args: [T.i64, T.ptr], returns: T.i32 },
    GenerateConsoleCtrlEvent: { args: [T.u32, T.u32], returns: T.i32 },
    AttachConsole: { args: [T.u32], returns: T.i32 },
    CloseHandle: { args: [T.i64], returns: T.i32 },
    GetLastError: { args: [], returns: T.u32 },
    FormatMessageW: { args: [T.u32, T.ptr, T.u32, T.u32, T.ptr, T.u32, T.ptr], returns: T.u32 },
    CompareStringOrdinal: { args: [T.ptr, T.i32, T.ptr, T.i32, T.i32], returns: T.i32 },
  });
  // 指针参数一律直接传 TypedArray（Bun 在调用期间保活它），不先换成 ffi.ptr() 的数字：数字不受 GC 追踪，长时间运行、
  // 被 JIT 优化的进程（本机服务）里缓冲区可能在调用之前就被回收（themistally-15 复核 ④a 的加固）。地址被嵌进结构体、
  // 要活过这一次调用的缓冲区另见 spawnSuspended 的 keep。
  type Buf = ArrayBufferView;
  const k = kernel32.symbols as unknown as {
    CreateJobObjectW(a: null, n: null): bigint;
    SetInformationJobObject(job: bigint, kind: number, info: Buf, size: number): number;
    QueryInformationJobObject(job: bigint, kind: number, info: Buf, size: number, ret: null): number;
    AssignProcessToJobObject(job: bigint, process: bigint): number;
    TerminateJobObject(job: bigint, code: number): number;
    CreateFileW(name: Buf, access: number, share: number, security: Buf, disposition: number, flags: number, template: null): bigint;
    InitializeProcThreadAttributeList(list: Buf | null, count: number, flags: number, size: Buf): number;
    UpdateProcThreadAttribute(list: Buf, flags: number, attribute: bigint, value: Buf, size: bigint, previous: null, returned: null): number;
    DeleteProcThreadAttributeList(list: Buf): number;
    CreateProcessW(app: null, cmdline: Buf, pa: null, ta: null, inherit: number, flags: number, env: Buf | null, cwd: Buf | null, si: Buf, pi: Buf): number;
    ResumeThread(thread: bigint): number;
    TerminateProcess(process: bigint, code: number): number;
    WaitForSingleObject(handle: bigint, milliseconds: number): number;
    GetExitCodeProcess(process: bigint, code: Buf): number;
    GenerateConsoleCtrlEvent(event: number, group: number): number;
    AttachConsole(pid: number): number;
    CloseHandle(handle: bigint): number;
    GetLastError(): number;
    FormatMessageW(flags: number, source: null, id: number, language: number, buffer: Buf, size: number, args: null): number;
    CompareStringOrdinal(a: Buf, la: number, b: Buf, lb: number, ignoreCase: number): number;
  };
  const wide = (text: string): Buffer => Buffer.from(`${text}\0`, "utf16le");
  const fail = (call: string): never => {
    throw new Win32Error(call, k.GetLastError());
  };
  // SECURITY_ATTRIBUTES（x64，24 字节）：nLength、lpSecurityDescriptor = NULL、bInheritHandle = TRUE
  const inheritable = new Uint8Array(24);
  new DataView(inheritable.buffer).setUint32(0, 24, true);
  new DataView(inheritable.buffer).setUint32(16, 1, true);
  return {
    createKillOnCloseJob() {
      const job = k.CreateJobObjectW(null, null);
      if (job === 0n) fail("CreateJobObjectW");
      const limit = new Uint8Array(144);
      new DataView(limit.buffer).setUint32(16, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, true);
      if (!k.SetInformationJobObject(job, JOB_EXTENDED_LIMIT_INFORMATION, limit, 144)) {
        const error = k.GetLastError();
        k.CloseHandle(job);
        throw new Win32Error("SetInformationJobObject", error);
      }
      return job;
    },
    openInheritable(path, how) {
      const access = how === "read" ? GENERIC_READ : how === "append" ? FILE_APPEND_DATA : GENERIC_WRITE;
      const disposition = how === "create-new" ? CREATE_NEW : how === "truncate" ? CREATE_ALWAYS
        : how === "append" ? OPEN_ALWAYS : OPEN_EXISTING;
      const handle = k.CreateFileW(wide(path), access, FILE_SHARE_READ | FILE_SHARE_WRITE, inheritable, disposition,
        FILE_ATTRIBUTE_NORMAL, null);
      if (handle === INVALID_HANDLE || handle === 0n) fail("CreateFileW");
      return handle;
    },
    spawnSuspended(cmdline, environment, cwd, std) {
      const handles = [...new Set([std.stdin, std.stdout, std.stderr])];
      const size = new BigUint64Array(1);
      k.InitializeProcThreadAttributeList(null, 1, 0, size); // 先问要多大（这一次照例失败）
      const list = new Uint8Array(Number(size[0]));
      if (!k.InitializeProcThreadAttributeList(list, 1, 0, size)) fail("InitializeProcThreadAttributeList");
      // 属性表里存的是句柄数组的地址，STARTUPINFOEXW 里存的是属性表的地址：这两块要活到 DeleteProcThreadAttributeList
      // 之后，不能只靠调用期间的保活
      const inherited = new BigUint64Array(handles);
      try {
        if (!k.UpdateProcThreadAttribute(list, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited, BigInt(8 * handles.length),
          null, null)) fail("UpdateProcThreadAttribute");
        const startup = new Uint8Array(112); // STARTUPINFOEXW
        const view = new DataView(startup.buffer);
        view.setUint32(0, 112, true);
        view.setUint32(60, STARTF_USESTDHANDLES, true);
        view.setBigUint64(80, BigInt.asUintN(64, std.stdin), true);
        view.setBigUint64(88, BigInt.asUintN(64, std.stdout), true);
        view.setBigUint64(96, BigInt.asUintN(64, std.stderr), true);
        view.setBigUint64(104, BigInt(ffi.ptr(list)), true);
        const info = new Uint8Array(24); // PROCESS_INFORMATION
        const flags = CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | EXTENDED_STARTUPINFO_PRESENT
          | (environment === null ? 0 : CREATE_UNICODE_ENVIRONMENT);
        // 命令行给一份可写的（CreateProcessW 可能改写它）；环境块、工作目录、两个结构体都直接传，调用期间保活
        if (!k.CreateProcessW(null, wide(cmdline), null, null, 1, flags, environment, cwd === null ? null : wide(cwd),
          startup, info)) {
          fail("CreateProcessW");
        }
        const out = new DataView(info.buffer);
        return { process: out.getBigInt64(0, true), thread: out.getBigInt64(8, true), pid: out.getUint32(16, true) };
      } finally {
        k.DeleteProcThreadAttributeList(list);
        retain([list, inherited]);
      }
    },
    assign: (job, child) => k.AssignProcessToJobObject(job, child) !== 0,
    resume: (thread) => k.ResumeThread(thread) >>> 0 !== 0xffffffff,
    terminateProcess: (child) => void k.TerminateProcess(child, 1),
    exited: (child, milliseconds) => k.WaitForSingleObject(child, Math.max(0, Math.floor(milliseconds))) === WAIT_OBJECT_0,
    exitCode(child) {
      const code = new Uint32Array(1);
      if (!k.GetExitCodeProcess(child, code)) fail("GetExitCodeProcess");
      return code[0] as number;
    },
    ctrlBreak: (pid) => (k.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid) ? null : k.GetLastError()),
    attachConsole: (pid) => k.AttachConsole(pid) !== 0,
    terminateJob: (job) => void k.TerminateJobObject(job, 1),
    activeProcesses(job) {
      const accounting = new Uint8Array(48);
      if (!k.QueryInformationJobObject(job, JOB_BASIC_ACCOUNTING_INFORMATION, accounting, 48, null)) return -1;
      return new DataView(accounting.buffer).getUint32(40, true);
    },
    close: (handle) => void k.CloseHandle(handle),
    compareIgnoreCase(a, b) {
      return k.CompareStringOrdinal(wide(a), a.length, wide(b), b.length, 1) - 2;
    },
    message(winerror) {
      const buffer = new Uint16Array(2048);
      const n = k.FormatMessageW(0x1000 | 0x200, null, winerror, 0x0400, buffer, buffer.length, null);
      return Buffer.from(buffer.buffer, 0, n * 2).toString("utf16le");
    },
  };
}
