// 内核子进程的执行器（桌面端设计第 7 版 §5.2、D08–D10）：每一条读路由起一个子进程跑内核 CLI，命令行是
// [python, kernel, "--repo", repo, ...argv]（argv 是列表、不经 shell），cwd 是仓库目录，环境照 kernelenv。
// 同时最多 4 个在跑（DEFAULT_MAX_CONCURRENT），FIFO 队列最多 16 个在等（DEFAULT_MAX_QUEUE），每条路由各有时限
// （超时由 runSupervised 处理：先 CTRL_BREAK、宽限 2 秒之后结束 Job，整棵树一起完）；客户端断开（请求的 signal）
// 与服务关停（shutdownController）任一发生就取消那一次运行——取消经手工合成的 AbortSignal 传给 runSupervised
// （handleSignals: false：Ctrl+C 停的是服务本身，由服务把取消传给每一次运行）。stdout 与 stderr 写到服务私有的
// 临时根目录（系统临时目录下 themis-ui- 前缀的 mkdtemp）里每次运行一个子目录，读完删子目录，关停删根目录。
import { mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runSupervised, type SuperviseResult } from "@themis/base/supervise";
import { kernelEnv } from "./kernelenv.ts";

/** 同时在跑的子进程上限。 */
export const DEFAULT_MAX_CONCURRENT = 4;
/** FIFO 队列里最多等多少个。 */
export const DEFAULT_MAX_QUEUE = 16;
/** stdout 上限 32 MiB。 */
export const MAX_STDOUT_BYTES = 32 * 1024 * 1024;
/** stderr 上限 1 MiB。 */
export const MAX_STDERR_BYTES = 1024 * 1024;
/** 服务私有的临时根目录前缀（系统临时目录下）。 */
export const TEMP_PREFIX = "themis-ui-";
/** H1：子进程跑着的时候每隔这么久用 statSync 看一次输出文件的大小（边写边看，不等结束）。 */
export const OUTPUT_POLL_MS = 100;

/** 一次运行的结果：completed 是进程跑完了（退出码可能非 0），其余都是服务这一侧的判定。 */
export type RunOutcome =
  | { readonly kind: "completed"; readonly result: SuperviseResult; readonly stdout: string; readonly stderr: string }
  | { readonly kind: "timeout"; readonly result: SuperviseResult }
  | { readonly kind: "interrupted"; readonly result: SuperviseResult | null }
  | { readonly kind: "spawn-error"; readonly result: SuperviseResult }
  | { readonly kind: "output-too-large"; readonly result: SuperviseResult }
  | { readonly kind: "queue-full" }
  | { readonly kind: "closing" };

export interface KernelRunnerOptions {
  /** 仓库根目录（cwd 与 --repo 都用它）。 */
  readonly repo: string;
  /** 内核用的 Python 解释器（UiArgs.python）。 */
  readonly python: string;
  /** 内核 CLI 的入口（UiArgs.kernel）。 */
  readonly kernel: string;
  /** 同时在跑的上限（只给测试入口）。 */
  readonly maxConcurrent?: number;
  /** 队列长度（只给测试入口）。 */
  readonly maxQueue?: number;
  readonly stdoutLimitBytes?: number;
  readonly stderrLimitBytes?: number;
}

/** 一次运行可选的钩子：queued 变 running 的那一刻由执行器调一次 onStart（读路由不传，作业用它记 started_ms）。 */
export interface RunHooks {
  readonly onStart?: (() => void) | undefined;
}

/** 一次运行在队列里或在跑的表项：状态在 queued → running → settled 之间只走一次。 */
interface Entry {
  readonly argv: readonly string[];
  readonly timeoutSeconds: number;
  /** 手工合成的信号：请求的 signal 与服务关停任一 abort 它就 abort。 */
  readonly controller: AbortController;
  /** 请求自己的 signal（客户端断开）。 */
  readonly signal: AbortSignal;
  readonly onRequestAbort: () => void;
  readonly onShutdown: () => void;
  /** 摘掉请求 signal 与关停 signal 上的监听（H3：挂到 Entry 上，关停清队列时才摘得到）。 */
  readonly release: () => void;
  /** 本次运行的钩子（queued 变 running 时通知）。 */
  readonly hooks: RunHooks | undefined;
  resolve: (outcome: RunOutcome) => void;
  state: "queued" | "running" | "settled";
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((done) => setTimeout(done, milliseconds));
}

/** 读一个输出文件：不存在或读不出当空串。 */
function readOutput(path: string): string {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return "";
  }
}

/** 文件有多大：取不到当 0。 */
function sizeOf(path: string): number {
  try {
    return statSync(path).size;
  } catch {
    return 0;
  }
}

/** 执行器自己出事时的结果（照 spawn_error 的形状：起不了子进程 → 500）。 */
function internalError(detail: string): SuperviseResult {
  return {
    exit_code: null, timed_out: false, interrupted: false, spawn_error: detail, wall_seconds: 0,
    stray_processes: null, kill_method: null, pid: null, ctrl_break: null, ctrl_break_winerror: null,
  };
}

/** 执行器对外的那一点（读路由只用它跑命令；测试可以换替身）。 */
export interface RunKernel {
  run(argv: readonly string[], timeoutSeconds: number, signal: AbortSignal, hooks?: RunHooks): Promise<RunOutcome>;
  readonly isClosing: boolean;
}

/** 内核子进程的执行器：一个服务一个实例（并发计数、队列、临时根目录、关停都在它身上）。 */
export class KernelRunner implements RunKernel {
  private readonly repo: string;
  private readonly python: string;
  private readonly kernel: string;
  private readonly maxConcurrent: number;
  private readonly maxQueue: number;
  private readonly stdoutLimitBytes: number;
  private readonly stderrLimitBytes: number;
  private readonly root: string;
  private readonly queue: Entry[] = [];
  private readonly shutdownController = new AbortController();
  private active = 0;
  private closing = false;

  constructor(options: KernelRunnerOptions) {
    this.repo = options.repo;
    this.python = options.python;
    this.kernel = options.kernel;
    this.maxConcurrent = Math.max(1, options.maxConcurrent ?? DEFAULT_MAX_CONCURRENT);
    this.maxQueue = Math.max(0, options.maxQueue ?? DEFAULT_MAX_QUEUE);
    this.stdoutLimitBytes = options.stdoutLimitBytes ?? MAX_STDOUT_BYTES;
    this.stderrLimitBytes = options.stderrLimitBytes ?? MAX_STDERR_BYTES;
    this.root = mkdtempSync(join(tmpdir(), TEMP_PREFIX));
  }

  /** 服务私有的临时根目录（系统临时目录下，服务退出即删）。 */
  get tempRoot(): string {
    return this.root;
  }

  /** 在跑加在等的个数（测试观察用）。 */
  get pending(): number {
    return this.active + this.queue.length;
  }

  /** 服务是不是正在关停（关停中新的读路由回 503）。 */
  get isClosing(): boolean {
    return this.closing;
  }

  /** 还能不能再收一次运行：在跑的小于上限，或者队列没满（创建作业之前先看它，收不了就不建作业）。 */
  canAccept(): boolean {
    return !this.closing && (this.active < this.maxConcurrent || this.queue.length < this.maxQueue);
  }

  /**
   * 跑一次内核命令：argv 是路由给的模板（不含 python、kernel、--repo 与仓库路径）。取消看 signal（请求的
   * signal）与服务关停；排队中被取消的直接出队、不起子进程；开始之前就已取消的不起子进程。hooks.onStart 在
   * queued 变 running 的那一刻调一次（读路由不传）。
   */
  run(argv: readonly string[], timeoutSeconds: number, signal: AbortSignal, hooks?: RunHooks): Promise<RunOutcome> {
    if (this.closing) return Promise.resolve({ kind: "closing" });
    if (signal.aborted) return Promise.resolve({ kind: "interrupted", result: null });
    const controller = new AbortController();
    let entry: Entry;
    const onRequestAbort = (): void => {
      if (entry.state === "queued") {
        // 排队中被取消：出队、不起子进程
        entry.state = "settled";
        const at = this.queue.indexOf(entry);
        if (at >= 0) this.queue.splice(at, 1);
        entry.resolve({ kind: "interrupted", result: null });
        release();
      } else if (entry.state === "running") {
        controller.abort(); // 在跑：取消这一次运行（结束整棵树）
      }
    };
    const onShutdown = (): void => {
      if (entry.state === "running") controller.abort();
    };
    const release = (): void => {
      signal.removeEventListener("abort", onRequestAbort);
      this.shutdownController.signal.removeEventListener("abort", onShutdown);
    };
    entry = {
      argv,
      timeoutSeconds,
      controller,
      signal,
      onRequestAbort,
      onShutdown,
      release,
      hooks,
      resolve: () => {},
      state: "queued",
    };
    signal.addEventListener("abort", onRequestAbort, { once: true });
    this.shutdownController.signal.addEventListener("abort", onShutdown, { once: true });
    return new Promise<RunOutcome>((resolve, reject) => {
      entry.resolve = resolve;
      if (this.active < this.maxConcurrent) {
        void this.start(entry).catch(reject);
      } else if (this.queue.length < this.maxQueue) {
        this.queue.push(entry);
      } else {
        entry.state = "settled"; // 队列满：503
        release();
        resolve({ kind: "queue-full" });
      }
    });
  }

  /** 起一个子进程并等它结束；结束时腾出名额、开跑队列里最早的一个。 */
  private async start(entry: Entry): Promise<RunOutcome> {
    entry.state = "running";
    this.active += 1;
    entry.hooks?.onStart?.(); // queued 变 running：通知这一次（作业记 started_ms）
    const dir = mkdtempSync(join(this.root, "run-"));
    const stdoutPath = join(dir, "stdout.txt");
    const stderrPath = join(dir, "stderr.txt");
    let outcome: RunOutcome;
    // H1：边写边看。子进程跑着的时候每隔 OUTPUT_POLL_MS 看一次输出大小，任一超限就记 overflow 并中止这次运行
    let overflow = false;
    const poll = setInterval(() => {
      if (sizeOf(stdoutPath) > this.stdoutLimitBytes || sizeOf(stderrPath) > this.stderrLimitBytes) {
        overflow = true;
        entry.controller.abort(); // runSupervised 照中断处理，整棵树结束
      }
    }, OUTPUT_POLL_MS);
    poll.unref?.();
    try {
      const result = await runSupervised([this.python, this.kernel, "--repo", this.repo, ...entry.argv], {
        cwd: this.repo,
        env: kernelEnv(),
        stdout: { path: stdoutPath, how: "create-new" },
        stderr: { path: stderrPath, how: "create-new" },
        timeout: entry.timeoutSeconds,
        grace: 2, // 宽限 2 秒：CTRL_BREAK 之后结束 Job（站主实测：Python 子进程收到 CTRL_BREAK 立即退出）
        signal: entry.controller.signal,
        handleSignals: false,
      });
      // overflow 先于 timed_out 与 interrupted 判定（边写边看超限要记成 output-too-large，不是超时/中断）
      if (result.spawn_error !== null) outcome = { kind: "spawn-error", result };
      else if (overflow) outcome = { kind: "output-too-large", result };
      else if (result.timed_out) outcome = { kind: "timeout", result };
      else if (result.interrupted) outcome = { kind: "interrupted", result };
      else if (sizeOf(stdoutPath) > this.stdoutLimitBytes || sizeOf(stderrPath) > this.stderrLimitBytes) {
        // 结束后那次兜底：两次轮询之间就写完退出的情况也要抓住
        outcome = { kind: "output-too-large", result };
      } else {
        outcome = { kind: "completed", result, stdout: readOutput(stdoutPath), stderr: readOutput(stderrPath) };
      }
    } catch (error) {
      outcome = { kind: "spawn-error", result: internalError(error instanceof Error ? error.message : "未知错误") };
    } finally {
      clearInterval(poll); // 轮询定时器在 finally 里清掉
      this.active -= 1;
      entry.release(); // 摘掉请求 signal 与关停 signal 上的监听（H3）
      entry.state = "settled";
      rmSync(dir, { recursive: true, force: true });
      this.pump();
    }
    entry.resolve(outcome);
    return outcome;
  }

  /** 有名额就开跑队列里最早的几个。 */
  private pump(): void {
    while (!this.closing && this.active < this.maxConcurrent) {
      const entry = this.queue.shift();
      if (entry === undefined) return;
      if (entry.state !== "queued") continue;
      void this.start(entry).catch(() => undefined); // 结果已经过 entry.resolve 交代
    }
  }

  /**
   * 关停：先拒绝新请求（closing 之后 run 直接回 closing）、清空队列（排队中的回 closing），再取消在跑的
   * （结束整棵树），等它们都结束，最后删掉临时根目录。
   */
  async shutdown(): Promise<void> {
    this.closing = true;
    const drained = this.queue.splice(0, this.queue.length);
    for (const entry of drained) {
      if (entry.state !== "queued") continue;
      entry.state = "settled";
      entry.release(); // H3：清队列时逐个摘掉请求 signal 与关停 signal 上的监听
      entry.resolve({ kind: "closing" });
    }
    this.shutdownController.abort();
    const deadline = Date.now() + 30_000;
    while (this.active > 0 && Date.now() < deadline) await sleep(25);
    rmSync(this.root, { recursive: true, force: true });
  }
}
