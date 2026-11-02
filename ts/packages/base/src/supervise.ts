// run_supervised 的 TS 实现（迁移计划第 8.2 节 ④a）：在独立进程组与 Job Object 里运行命令，执行墙钟时限，结束后
// 清理残留进程。与 pi_dispatch.run_supervised（第 70 轮）逐项一致，契约见 contracts/test/supervise.contract.test.ts。
//
// Windows（Bun FFI，native.ts）：挂起创建（CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP）、加入带 KILL_ON_JOB_CLOSE 的
// Job 之后再恢复，子进程的任何子孙都在 Job 里，没有监督的空窗；加入失败就终止子进程、拒绝运行。调用方意外死掉时 Job
// 句柄随进程关闭，整棵树一起结束。
//   - 命令行照 subprocess.list2cmdline 拼，lpApplicationName 传 NULL：碰到 .cmd、.bat 照样隐式起 cmd.exe，与 Python
//     相同。批处理的参数注入由调用方先过 ensure_argv_safe（@themis/dispatcher），这里不拒绝；
//   - 环境块照 CPython 3.12 的 getenvironment（实测）：按 CompareStringOrdinal（不分大小写）稳定排序，大小写不同的
//     同名变量留最后插入的那一个；键或值含 NUL 报 ValueError("embedded null character")，键在第 1 个字符之后含 =
//     报 ValueError("illegal environment variable name")；空键交给 CreateProcessW，由它报错误码 87；
//   - 只让三个标准流句柄被继承（PROC_THREAD_ATTRIBUTE_HANDLE_LIST），stdin 接空设备 NUL；
//   - 超时或中断：先给子进程组发 CTRL_BREAK。发出去了（"sent"）就最多等 grace 秒；发送失败（"failed"，记错误码）
//     或者进程已经回收、什么都没发（null），就不等，直接结束 Job；
//   - 启动失败的报错照 CPython 的 OSError：类名由错误码映射（PC/errmap.h），文字是 FormatMessageW 去掉末尾空白与句点。
// Node 后备：Node 调不了 Win32，经 Bun 辅助进程（native-helper.ts 的 supervise）运行；调用方死掉时辅助进程读到 stdin 的
// EOF 就退出，Job 句柄随之关闭。
// POSIX：新会话（进程组），超时先给进程组 SIGTERM、宽限后 SIGKILL；没有 PR_SET_PDEATHSIG。未实机验证。
import { spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { createInterface } from "node:readline";
import { type OpenHow, type WinProcessApi, Win32Error, nativeHelperCommand, win32ErrorMessage, winProcessApi } from "./native.ts";
import { PyCrash, pyRepr } from "./pyfmt.ts";

/** 标准输出、标准错误写到哪个文件、怎么开（"create-new" 同 Python 的 "xb"）。 */
export interface OutputTarget {
  readonly path: string;
  readonly how: Exclude<OpenHow, "read">;
}

export interface SuperviseOptions {
  readonly cwd: string;
  /** 环境变量（按插入次序；Python 的 dict 次序决定大小写不同的同名变量留哪个）。 */
  readonly env: readonly (readonly [string, string])[];
  readonly stdout: OutputTarget;
  /** "stdout"：标准错误并进标准输出的同一个句柄（Python 的 stderr=subprocess.STDOUT；检查命令的日志就是这样写的，④b3）。 */
  readonly stderr: OutputTarget | "stdout";
  /** 墙钟时限（秒）；null 或 0 不限。 */
  readonly timeout: number | null;
  readonly grace?: number;
  readonly onSpawn?: (pid: number) => void;
  /** 从外部取消这一次运行（本机服务：客户端断开、服务关闭），照中断处理（interrupted、结束整棵树）。 */
  readonly signal?: AbortSignal;
  /** 运行期间在 process 上装 SIGINT、SIGTERM、SIGHUP、SIGBREAK 监听器，与 run_supervised 一样（缺省 true）。本机服务
   * 设 false：Ctrl+C 要停掉服务本身，由服务经 signal 把取消传给每一次运行。 */
  readonly handleSignals?: boolean;
}

/** 与 run_supervised 返回的字典同名、同序。 */
export interface SuperviseResult {
  exit_code: number | null;
  timed_out: boolean;
  interrupted: boolean;
  spawn_error: string | null;
  wall_seconds: number;
  stray_processes: boolean | null;
  kill_method: string | null;
  pid: number | null;
  ctrl_break: "sent" | "failed" | null;
  ctrl_break_winerror: number | null;
}

const isBun = typeof (globalThis as { Bun?: unknown }).Bun !== "undefined";

function sleep(milliseconds: number): Promise<void> {
  return new Promise((done) => setTimeout(done, milliseconds));
}

function newResult(): SuperviseResult {
  return {
    exit_code: null, timed_out: false, interrupted: false, spawn_error: null, wall_seconds: 0, stray_processes: null,
    kill_method: null, pid: null, ctrl_break: null, ctrl_break_winerror: null,
  };
}

function elapsed(start: number): number {
  return Math.round(performance.now() - start) / 1000;
}

// ---------------------------------------------------------------------------
// 命令行与环境块（纯函数）
// ---------------------------------------------------------------------------

/** subprocess.list2cmdline（CPython 3.12 Lib/subprocess.py）逐行移植。 */
export function list2cmdline(args: readonly string[]): string {
  const result: string[] = [];
  for (const arg of args) {
    let backslashes: string[] = [];
    if (result.length > 0) result.push(" ");
    const needQuote = arg.includes(" ") || arg.includes("\t") || arg === "";
    if (needQuote) result.push('"');
    for (const char of arg) {
      if (char === "\\") {
        backslashes.push(char);
      } else if (char === '"') {
        result.push("\\".repeat(backslashes.length * 2));
        backslashes = [];
        result.push('\\"');
      } else {
        if (backslashes.length > 0) {
          result.push(...backslashes);
          backslashes = [];
        }
        result.push(char);
      }
    }
    if (backslashes.length > 0) result.push(...backslashes);
    if (needQuote) {
      result.push(...backslashes);
      result.push('"');
    }
  }
  return result.join("");
}

/** CPython 3.12 的 getenvironment：校验、排序、去重，给出 CREATE_UNICODE_ENVIRONMENT 要的 UTF-16LE 环境块。 */
export function environmentBlock(
  env: readonly (readonly [string, string])[],
  compare: (a: string, b: string) => number,
): Buffer {
  // 先照 Python 的 dict 收拢完全同名的键：位置是第一次出现的位置，值是最后一次的值（Map 的语义相同）
  const dict = new Map<string, string>();
  for (const [key, value] of env) dict.set(key, value);
  const sorted = [...dict].map(([key, value], index) => ({ key, value, index }))
    .sort((a, b) => compare(a.key, b.key) || a.index - b.index);
  const kept: { key: string; value: string }[] = [];
  for (let i = 0; i < sorted.length; i += 1) {
    const item = sorted[i] as { key: string; value: string };
    const next = sorted[i + 1];
    if (next !== undefined && compare(item.key, next.key) === 0) continue; // 同名变量留最后插入的那一个
    if (item.key.includes("\0") || item.value.includes("\0")) throw new PyCrash("ValueError", "embedded null character");
    if (item.key.indexOf("=", 1) !== -1) throw new PyCrash("ValueError", "illegal environment variable name");
    kept.push(item);
  }
  const text = kept.length === 0 ? "\0" : kept.map(({ key, value }) => `${key}=${value}\0`).join("");
  return Buffer.from(`${text}\0`, "utf16le");
}

// CPython PC/errmap.h：winerror → errno 的名字（只列 errno 有对应异常子类的那些；其余都是 OSError）
const ERRNO_OF_WINERROR = new Map<number, string>([
  [2, "ENOENT"], [3, "ENOENT"], [15, "ENOENT"], [18, "ENOENT"], [53, "ENOENT"], [67, "ENOENT"], [161, "ENOENT"],
  [206, "ENOENT"],
  [5, "EACCES"], [12, "EACCES"], [16, "EACCES"], [32, "EACCES"], [33, "EACCES"], [65, "EACCES"], [82, "EACCES"],
  [83, "EACCES"], [108, "EACCES"], [132, "EACCES"], [158, "EACCES"], [167, "EACCES"],
  ...Array.from({ length: 18 }, (_, i) => [19 + i, "EACCES"] as [number, string]),
  [80, "EEXIST"], [183, "EEXIST"],
  [267, "ENOTDIR"],
  [109, "EPIPE"],
  [128, "ECHILD"], [129, "ECHILD"],
  [89, "EAGAIN"], [164, "EAGAIN"], [215, "EAGAIN"],
]);
const CLASS_OF_ERRNO = new Map<string, string>([
  ["ENOENT", "FileNotFoundError"], ["EACCES", "PermissionError"], ["EEXIST", "FileExistsError"],
  ["ENOTDIR", "NotADirectoryError"], ["EPIPE", "BrokenPipeError"], ["ECHILD", "ChildProcessError"],
  ["EAGAIN", "BlockingIOError"],
]);

/** CPython 给 Windows 错误码构造的 OSError：类名（由错误码映射）与 strerror（FormatMessageW 去掉末尾的空白与句点）。 */
export function windowsOSError(winerror: number, message: string): { name: string; strerror: string } {
  const name = CLASS_OF_ERRNO.get(ERRNO_OF_WINERROR.get(winerror) ?? "") ?? "OSError";
  let end = message.length;
  while (end > 0 && ((message.codePointAt(end - 1) as number) <= 0x20 || message[end - 1] === ".")) end -= 1;
  return { name, strerror: message.slice(0, end) };
}

/**
 * str(OSError) 的 "[WinError N] <系统的文字>"（只在 Windows 上调用）：文字取 FormatMessageW、照 windowsOSError 去掉末尾的空白与句点，跟着
 * 系统界面的语言；带文件名时接 ": " 与 repr（scandir、listdir 一类带，CreateProcess 的 cwd 不在时不带）。
 */
export function pyWinErrorMessage(winerror: number, filename?: string): string {
  const { strerror } = windowsOSError(winerror, win32ErrorMessage(winerror));
  return filename === undefined ? `[WinError ${winerror}] ${strerror}` : `[WinError ${winerror}] ${strerror}: ${pyRepr(filename)}`;
}

/** CPython 给 Windows 错误码构造的 OSError 的 "类名: 文字"（PyErr_SetExcFromWindowsErr）。 */
export function windowsErrorText(winerror: number, message: string): string {
  const { name, strerror } = windowsOSError(winerror, message);
  return `${name}: [WinError ${winerror}] ${strerror}`;
}

// ---------------------------------------------------------------------------
// Windows（Bun FFI）
// ---------------------------------------------------------------------------

/** 中断：照 run_supervised 的 _install_interrupt_handlers，运行期间接住这几个信号。 */
const INTERRUPTS = ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"] as const;

/** pi_dispatch.JOB_SETTLE_SECONDS（第 74 轮）：主进程刚退出时 Job 的活动进程数可能还没减下来，大于 0 时先等这么久，
 * 仍大于 0 才算残留。 */
const JOB_SETTLE_MS = 2000;

/** 中断请求：信号处理器或辅助进程的 interrupt 请求置位，运行循环下一轮看到就照 _Interrupted 处理。 */
export interface InterruptFlag {
  interrupted: boolean;
}

async function superviseWindows(
  cmd: readonly string[],
  options: SuperviseOptions,
  api: WinProcessApi,
  flag: InterruptFlag = { interrupted: false },
): Promise<SuperviseResult> {
  const result = newResult();
  const grace = options.grace ?? 15;
  let job: bigint;
  try {
    job = api.createKillOnCloseJob();
  } catch (error) {
    const code = error instanceof Win32Error ? error.winerror : 0;
    const call = error instanceof Win32Error && error.message.startsWith("SetInformationJobObject") ? "SetInformationJobObject" : "CreateJobObjectW";
    result.spawn_error = `无法创建 Windows Job Object，拒绝在没有进程树监督的情况下运行：[Errno ${code}] ${call} failed`;
    return result;
  }
  result.kill_method = "job-object";
  const onSignal = (): void => {
    flag.interrupted = true;
  };
  const listens = options.handleSignals ?? true;
  if (listens) for (const name of INTERRUPTS) process.on(name, onSignal);
  options.signal?.addEventListener("abort", onSignal);
  if (options.signal?.aborted) flag.interrupted = true;
  const start = performance.now();
  let child: { process: bigint; thread: bigint; pid: number } | null = null;
  let exited = false;
  const waitExit = async (milliseconds: number): Promise<boolean> => {
    const until = performance.now() + milliseconds;
    while (!(exited = exited || api.exited((child as { process: bigint }).process, 0))) {
      const left = until - performance.now();
      if (left <= 0) return false;
      await sleep(Math.min(25, left));
    }
    return true;
  };
  const terminateTree = async (graceSeconds: number): Promise<void> => {
    // CPython 的 send_signal：returncode 已知（已经观察到退出）时什么都不发
    if (!exited) {
      const failed = api.ctrlBreak((child as { pid: number }).pid);
      result.ctrl_break = failed === null ? "sent" : "failed";
      result.ctrl_break_winerror = failed;
    }
    if (result.ctrl_break === "sent") await waitExit(graceSeconds * 1000);
    api.terminateJob(job);
    await waitExit(30_000);
  };
  try {
    let std: { stdin: bigint; stdout: bigint; stderr: bigint };
    const opened: bigint[] = [];
    try {
      const stdin = api.openInheritable("NUL", "read");
      opened.push(stdin);
      const stdout = api.openInheritable(options.stdout.path, options.stdout.how);
      opened.push(stdout);
      const stderr = options.stderr === "stdout" ? stdout : api.openInheritable(options.stderr.path, options.stderr.how);
      if (stderr !== stdout) opened.push(stderr);
      std = { stdin, stdout, stderr };
      if (flag.interrupted) {
        // 开始之前就取消了（themistally-15 复核 ④a）：不起子进程。与 Python 一样：_Interrupted 发生在 Popen 之前时
        // proc 是 None，结果是 interrupted、没有 pid 与退出码；输出文件照样建好（Python 由调用方先打开）
        result.interrupted = true;
        return result;
      }
      const environment = environmentBlock(options.env, api.compareIgnoreCase);
      child = api.spawnSuspended(list2cmdline(cmd), environment, options.cwd, std);
    } catch (error) {
      if (error instanceof Win32Error) {
        result.spawn_error = windowsErrorText(error.winerror, api.message(error.winerror));
        return result;
      }
      throw error;
    } finally {
      for (const handle of opened) api.close(handle); // 子进程已经继承了自己的那份
    }
    result.pid = child.pid;
    if (!api.assign(job, child.process) || !api.resume(child.thread)) {
      api.terminateProcess(child.process);
      result.spawn_error = "进程未能加入 Job Object，已在启动前终止";
      return result;
    }
    options.onSpawn?.(child.pid);
    const deadline = options.timeout ? start + options.timeout * 1000 : null;
    for (;;) {
      if (flag.interrupted) {
        result.interrupted = true;
        await terminateTree(grace);
        break;
      }
      if (deadline !== null && performance.now() >= deadline) {
        result.timed_out = true;
        await terminateTree(grace);
        break;
      }
      if (api.exited(child.process, 0)) {
        exited = true;
        break;
      }
      await sleep(deadline === null ? 25 : Math.max(1, Math.min(25, deadline - performance.now())));
    }
  } catch (error) {
    if (child !== null) await terminateTree(Math.min(grace, 5));
    throw error;
  } finally {
    if (listens) for (const name of INTERRUPTS) process.off(name, onSignal);
    options.signal?.removeEventListener("abort", onSignal);
    if (child !== null) {
      await waitExit(30_000);
      let count = api.activeProcesses(job);
      const settle = performance.now() + JOB_SETTLE_MS;
      while (count > 0 && performance.now() < settle) {
        await sleep(10);
        count = api.activeProcesses(job);
      }
      if (count > 0) api.terminateJob(job);
      result.stray_processes = count > 0 ? true : count === 0 ? false : null;
      result.exit_code = exited ? api.exitCode(child.process) : null;
      api.close(child.thread);
      api.close(child.process);
    }
    result.wall_seconds = elapsed(start);
    api.close(job);
  }
  return result;
}

// ---------------------------------------------------------------------------
// Node 后备（Windows）：经 Bun 辅助进程
// ---------------------------------------------------------------------------

async function superviseThroughHelper(cmd: readonly string[], options: SuperviseOptions): Promise<SuperviseResult> {
  const [command, ...args] = nativeHelperCommand();
  // DETACHED_PROCESS：辅助进程先不带控制台，再自己挂到调用方的控制台上（helperSupervise）。不这样的话，调用方没有控制台
  // 时 Windows 会给辅助进程另配一个，CTRL_BREAK 就发得出去了，与进程内调用（发不出去）不一致
  const helper = spawn(command ?? "bun", [...args, "__native"], { stdio: ["pipe", "pipe", "inherit"], detached: true });
  // 辅助进程起不来（找不到 Bun 等）：spawn 的 error 事件没人接会让调用方整个崩掉（themistally-15 复核 ④a），记下来报清楚
  let spawnError: Error | null = null;
  helper.on("error", (error) => {
    spawnError ??= error;
  });
  // 起不来时 stdout 可能先于 error 事件关闭；close 在 error 之后：读完 stdout 先等它，再看是不是起不来
  const closed = new Promise<void>((done) => helper.once("close", () => done()));
  helper.stdin.on("error", () => undefined); // 起不来时写 stdin 会 EPIPE，原因由上面的 error 交代
  const { onSpawn, signal, handleSignals, ...request } = options;
  // 开始之前就取消了：随请求一起交代，辅助进程不起子进程（另发一行 interrupt 会与起子进程赛跑）
  const aborted = signal?.aborted === true;
  helper.stdin.write(`${JSON.stringify({ op: "supervise", cmd, options: request, interrupted: aborted })}\n`);
  const interrupt = (): void => {
    if (spawnError === null && !helper.stdin.destroyed) helper.stdin.write(`${JSON.stringify({ op: "interrupt" })}\n`);
  };
  const listens = handleSignals ?? true;
  if (listens) for (const name of INTERRUPTS) process.on(name, interrupt);
  signal?.addEventListener("abort", interrupt);
  try {
    const lines = createInterface({ input: helper.stdout });
    for await (const line of lines) {
      const message = JSON.parse(line) as { spawned?: number; result?: SuperviseResult; error?: { kind: string; message: string } };
      if (message.spawned !== undefined) onSpawn?.(message.spawned);
      if (message.error !== undefined) throw new PyCrash(message.error.kind, message.error.message);
      if (message.result !== undefined) return message.result;
    }
    // 兜底的 5 秒不拖住事件循环（unref）：close 迟迟不来也不让命令行晚退出
    await Promise.race([closed, new Promise<void>((done) => setTimeout(done, 5000).unref())]);
    if (spawnError !== null) throw new Error(`起不了进程监督的辅助进程（${command}）：${(spawnError as Error).message}`);
    throw new Error("进程监督的辅助进程没有交回结果就退出了");
  } finally {
    if (listens) for (const name of INTERRUPTS) process.off(name, interrupt);
    signal?.removeEventListener("abort", interrupt);
    helper.stdin.end();
  }
}

// ---------------------------------------------------------------------------
// POSIX（未实机验证）
// ---------------------------------------------------------------------------

function killGroup(pid: number, signal: NodeJS.Signals | 0): boolean | null {
  try {
    process.kill(-pid, signal);
    return true;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    return code === "ESRCH" ? false : null;
  }
}

async function supervisePosix(cmd: readonly string[], options: SuperviseOptions): Promise<SuperviseResult> {
  const result = newResult();
  result.kill_method = "process-group";
  const grace = options.grace ?? 15;
  const flags = (how: OutputTarget["how"]): string => (how === "create-new" ? "wx" : how === "truncate" ? "w" : "a");
  const out = openSync(options.stdout.path, flags(options.stdout.how));
  const err = options.stderr === "stdout" ? out : openSync(options.stderr.path, flags(options.stderr.how));
  const start = performance.now();
  let exitCode: number | null = null;
  let finished = false;
  const flag: InterruptFlag = { interrupted: options.signal?.aborted ?? false };
  const onSignal = (): void => {
    flag.interrupted = true;
  };
  const listens = options.handleSignals ?? true;
  if (listens) for (const name of INTERRUPTS) process.on(name, onSignal);
  options.signal?.addEventListener("abort", onSignal);
  try {
    if (flag.interrupted) {
      result.interrupted = true; // 开始之前就取消了：不起子进程（同 Windows）
      return result;
    }
    const child = spawn(cmd[0] as string, cmd.slice(1), {
      cwd: options.cwd, env: Object.fromEntries(options.env), stdio: ["ignore", out, err], detached: true,
    });
    const spawned = await new Promise<number | null>((done) => {
      child.once("spawn", () => done(child.pid ?? null));
      child.once("error", (error) => {
        result.spawn_error = `${(error as NodeJS.ErrnoException).code === "ENOENT" ? "FileNotFoundError" : "OSError"}: ${error.message}`;
        done(null);
      });
    });
    if (spawned === null) return result;
    result.pid = spawned;
    child.on("exit", (code, signal) => {
      finished = true;
      exitCode = code ?? (signal === null ? null : -1);
    });
    options.onSpawn?.(spawned);
    const deadline = options.timeout ? start + options.timeout * 1000 : null;
    const terminate = async (): Promise<void> => {
      killGroup(spawned, "SIGTERM");
      const until = performance.now() + grace * 1000;
      while (!finished && performance.now() < until) await sleep(25);
      killGroup(spawned, "SIGKILL");
    };
    while (!finished) {
      if (flag.interrupted) {
        result.interrupted = true;
        await terminate();
        break;
      }
      if (deadline !== null && performance.now() >= deadline) {
        result.timed_out = true;
        await terminate();
        break;
      }
      await sleep(25);
    }
    const until = performance.now() + 30_000;
    while (!finished && performance.now() < until) await sleep(25);
    const alive = killGroup(spawned, 0);
    if (alive) killGroup(spawned, "SIGKILL");
    result.stray_processes = alive;
    result.exit_code = exitCode;
  } finally {
    if (listens) for (const name of INTERRUPTS) process.off(name, onSignal);
    options.signal?.removeEventListener("abort", onSignal);
    closeSync(out);
    if (err !== out) closeSync(err);
    result.wall_seconds = elapsed(start);
  }
  return result;
}

// ---------------------------------------------------------------------------
// 对外接口
// ---------------------------------------------------------------------------

/** pi_dispatch.run_supervised：stdin 固定接空设备；返回的字段与 Python 的字典同名、同序。 */
export async function runSupervised(cmd: readonly string[], options: SuperviseOptions): Promise<SuperviseResult> {
  if (process.platform !== "win32") return supervisePosix(cmd, options);
  if (!isBun) return superviseThroughHelper(cmd, options);
  return superviseWindows(cmd, options, await winProcessApi());
}

/** 辅助进程一侧：只在 Bun 下运行（native-helper.ts 调用）；flag 由辅助进程收到 interrupt 请求时置位。辅助进程以
 * DETACHED_PROCESS 起，先挂到调用方（父进程）的控制台上：调用方有控制台就共用它，没有就照样没有。 */
export async function helperSupervise(cmd: readonly string[], options: SuperviseOptions, flag: InterruptFlag): Promise<SuperviseResult> {
  const api = await winProcessApi();
  api.attachConsole(process.ppid);
  return superviseWindows(cmd, options, api, flag);
}

/** 测试用：换一套 Win32 调用（注入失败）。 */
export function superviseWith(api: WinProcessApi, cmd: readonly string[], options: SuperviseOptions): Promise<SuperviseResult> {
  return superviseWindows(cmd, options, api);
}
