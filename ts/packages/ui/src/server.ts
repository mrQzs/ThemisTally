// 服务入口（桌面端设计第 7 版 §5.1、§5.2）：整个包唯一出现 Bun.serve 的地方——一层薄适配，里面全是照 WHATWG 写的
// Request/Response。步骤：拿锁（被占就报错退出 1）→ 生成控制令牌 → 起服务（只绑 127.0.0.1、端口 0、请求体上限设成
// 两倍）→ 写 owner.json 再读回来核对 → 写握手行（stdout 只此一行）→ 起生命周期（stdin EOF、空闲时限、信号）→ 等
// 关停。关停只做一次，另设 3 秒看门狗强制退出。
import { pidAlive } from "@themis/base/process";
import { EXIT_ERROR, EXIT_OK, type UiArgs, type UiIo } from "./main.ts";
import { createApp, type App } from "./app.ts";
import { errorResponse } from "./envelope.ts";
import { withSecurityHeaders } from "./localhttp/headers.ts";
import { randomToken } from "./localhttp/tokens.ts";
import { acquireUiLock, busyMessage, type UiLock } from "./lockdir.ts";
import { idleMs, IdleTimer, watchSignals, watchStdinEof } from "./lifecycle.ts";
import { CursorTable } from "./cursors.ts";
import { KernelRunner } from "./kernel.ts";
import { readRoutes, type ReadRoutesState } from "./readroutes.ts";

/** 测试入口才会传的覆盖项（CLI 与环境变量都碰不到）。 */
export interface ServeOverrides {
  readonly nonceTtlMs?: number | undefined;
  /** 同时在跑的内核子进程上限（缺省 4）。 */
  readonly maxConcurrent?: number | undefined;
  /** FIFO 队列长度（缺省 16）。 */
  readonly maxQueue?: number | undefined;
  /** 各读路由的时限覆盖（路由名 → 秒）：测试用短的时限触发 504，不必等真时限。 */
  readonly timeouts?: Readonly<Record<string, number>> | undefined;
}

/** Bun.serve 用到的这几样（ts/ 里没有 Bun 的类型声明，只声明用到的）。 */
interface BunServeOptions {
  readonly hostname: string;
  readonly port: number;
  readonly maxRequestBodySize: number;
  readonly development: boolean;
  readonly fetch: (request: Request) => Response | Promise<Response>;
  readonly error: (error: unknown) => Response | Promise<Response>;
}

interface BunServer {
  readonly port: number;
  stop(closeActiveConnections?: boolean): void;
}

interface BunLike {
  serve(options: BunServeOptions): BunServer;
}

/** 看门狗：关停之后 3 秒进程还在就强制退出（退出码照关停的那一个）。 */
const WATCHDOG_MS = 3000;
/** 请求体上限的两倍（64 KiB * 2）：让服务自己的计数先起作用，Bun 这一层只是第二道防线。 */
const MAX_REQUEST_BODY_BYTES = 131072;

/** 跑服务：返回进程退出码（0 正常关闭，1 已有服务在运行或起不来）。 */
export async function serveUi(args: UiArgs, io: UiIo, overrides: ServeOverrides = {}): Promise<number> {
  const bun = (globalThis as unknown as { Bun?: BunLike }).Bun;
  if (bun === undefined) {
    io.stderr.write("ERROR: 本机服务只能在 Bun 下运行\n");
    return EXIT_ERROR;
  }
  const acquired = await acquireUiLock(args.repo, { pid: process.pid, pidAlive });
  if (!("lock" in acquired)) {
    io.stderr.write(`ERROR: ${busyMessage(acquired.busy)}\n`);
    return EXIT_ERROR;
  }
  const lock: UiLock = acquired.lock;
  const assets = args.assets ?? "";

  let app: App | null = null;
  let server: BunServer | null = null;
  try {
    server = bun.serve({
      hostname: "127.0.0.1",
      port: 0,
      maxRequestBodySize: 131072,
      development: false,
      fetch: (request: Request) => (app === null ? Promise.resolve(notReady()) : app.fetch(request)),
      error: () => withSecurityHeaders(errorResponse(500, "服务内部错误"), { noStore: true }),
    });
  } catch (error) {
    lock.release();
    io.stderr.write(`ERROR: 起不了本机服务：${error instanceof Error ? error.name : "未知错误"}\n`);
    return EXIT_ERROR;
  }
  const running = server;

  const controlToken = randomToken();
  // 第 2 片：19 条只读数据路由各起一个内核子进程；执行器、句柄表与临时根目录都归服务所有，关停时收干净
  const runner = new KernelRunner({
    repo: args.repo,
    python: args.python,
    kernel: args.kernel,
    ...(overrides.maxConcurrent === undefined ? {} : { maxConcurrent: overrides.maxConcurrent }),
    ...(overrides.maxQueue === undefined ? {} : { maxQueue: overrides.maxQueue }),
  });
  const readState: ReadRoutesState = { repo: args.repo, runner, cursors: new CursorTable(), transcript: args.transcript };
  const extraRoutes = readRoutes(readState, overrides.timeouts ?? {});
  const appOptions = {
    port: running.port,
    assets,
    controlToken,
    extraRoutes,
    onActivity: () => timer.touch(),
    ...(overrides.nonceTtlMs === undefined ? {} : { nonceTtlMs: overrides.nonceTtlMs }),
  };
  const timer = new IdleTimer(idleMs(args.idle_timeout), () => {
    if (app === null || app.inflight() === 0) shutdown(EXIT_OK);
    else timer.touch(); // 有请求在进行中：不算空闲
  });
  app = createApp(appOptions);

  // owner.json 写完之后再读回来核对令牌：不一致就是锁被抢走了
  try {
    lock.writeOwner(running.port);
  } catch (error) {
    running.stop(true);
    timer.stop();
    lock.release();
    io.stderr.write(`ERROR: 写不了锁的持有者信息：${error instanceof Error ? error.name : "未知错误"}\n`);
    return EXIT_ERROR;
  }
  const owner = lock.readOwner();
  if (owner === null || owner.token !== lock.token) {
    running.stop(true);
    timer.stop();
    io.stderr.write("ERROR: 锁目录被别的进程抢走了（.agent/.ui.lock）\n");
    return EXIT_ERROR;
  }

  // 握手行：stdout 只此一行，字段与次序照合同
  const nonce = app.issueBootstrap();
  io.stdout.write(
    `${JSON.stringify({
      themis_ui: 1,
      bootstrap: `${app.origin}/bootstrap/${nonce}`,
      origin: app.origin,
      control: controlToken,
      pid: process.pid,
    })}\n`,
  );

  const stopStdin = (): void => {
    const stream = process.stdin as unknown as { destroy?: () => void } | null | undefined;
    try {
      stream?.destroy?.();
    } catch {
      // 已经关了
    }
  };

  let exitCode = EXIT_OK;
  let finished = false;
  let finish: () => void = () => {};
  const shutdown = (code: number): void => {
    if (finished) return;
    finished = true;
    exitCode = code;
    // 看门狗只在关停开始时设：3 秒还没退完就强制退出（不挂住外壳）
    const watchdog = setTimeout(() => process.exit(exitCode), WATCHDOG_MS);
    watchdog.unref();
    try {
      running.stop(true);
    } catch {
      // 已经停了
    }
    timer.stop();
    stopStdin();
    // 取消在跑的内核子进程、清空队列、删掉临时根目录（看门狗 3 秒兜底，不拖住外壳）
    void runner.shutdown().catch(() => undefined);
    lock.release();
    finish();
  };

  const detachSignals = watchSignals(() => shutdown(EXIT_OK));
  void watchStdinEof(process.stdin, () => shutdown(EXIT_OK)).finally(() => {
    detachSignals();
  });
  timer.touch();

  await new Promise<void>((resolve) => {
    finish = resolve;
  });
  detachSignals();
  return exitCode;
}

/** 服务还没建好时的占位响应（只可能出现在起服务与建应用之间的几毫秒里）。 */
function notReady(): Response {
  return withSecurityHeaders(errorResponse(503, "服务正在启动"), { noStore: true });
}
