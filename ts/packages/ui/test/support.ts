// 读路由用例共用的起应用工具（桌面端 T16 第 2 片）：不起真服务，直接在进程内建 app（ Bun 的 Request/Response 照
// WHATWG 写），内核子进程用替身 fake-kernel.mjs（python 是跑测试的这个 Node）。替身把每次调用的 argv 与环境三问
// 写进 FAKE_KERNEL_REPORT 指向的文件，用例据此断言 argv、时限与取消。
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createApp, type App } from "../src/app.ts";
import { CursorTable } from "../src/cursors.ts";
import { KernelRunner } from "../src/kernel.ts";
import { readRoutes, type ReadRoutesState } from "../src/readroutes.ts";
import { TS_ROOT } from "./harness.ts";

/** 子进程替身（node 跑的 fake-kernel.mjs）。 */
export const FAKE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-kernel.mjs");
/** 替身每次调用记在报告文件里的一行。 */
export interface ReportLine {
  readonly kind: string;
  readonly event: string;
  readonly pid: number;
  readonly argv: readonly string[];
  readonly at: number;
  readonly has_typesafe_api_key: boolean;
  readonly codekit_actor: string | null;
  readonly has_no_cwd_in_path: boolean;
  readonly exit?: number | null;
}

/** 读报告文件（替身的一次调用记 begin 与 end 两行）。 */
export function readReport(path: string): ReportLine[] {
  let text = "";
  try {
    text = readFileSync(path, "utf8");
  } catch {
    return [];
  }
  const out: ReportLine[] = [];
  for (const line of text.split("\n")) {
    if (line.trim() === "") continue;
    out.push(JSON.parse(line) as ReportLine);
  }
  return out;
}

/** 替身只跑过一次的那些 argv（begin 行，去重保持次序）。 */
export function argvsOf(path: string): string[][] {
  const seen: string[][] = [];
  for (const line of readReport(path)) {
    if (line.event !== "begin") continue;
    if (!seen.some((item) => item.length === line.argv.length && item.every((part, index) => part === line.argv[index]))) {
      seen.push([...line.argv]);
    }
  }
  return seen;
}

export interface StartedApp {
  readonly app: App;
  readonly runner: KernelRunner;
  readonly state: ReadRoutesState;
  readonly report: string;
  /** 带会话的 GET。 */
  get(target: string): Promise<Response>;
  /** 不带会话的 GET。 */
  getAnon(target: string): Promise<Response>;
  /** 带 AbortController 的 GET（断开取消用：调用方自己决定何时 abort）。 */
  getAbortable(target: string): { request: Request; controller: AbortController; send: () => Promise<Response> };
  dispose(): Promise<void>;
}

export interface AppOverrides {
  readonly maxConcurrent?: number;
  readonly maxQueue?: number;
  readonly stdoutLimitBytes?: number;
  readonly transcript?: readonly string[];
  readonly repo?: string;
  /** 各读路由的时限覆盖（路由名 → 秒；只给测试入口）。 */
  readonly timeouts?: Readonly<Record<string, number>>;
  /** 起内核子进程用的解释器（起不了子进程的用例指向一个不存在的文件）。 */
  readonly python?: string;
}

/** 建一个进程内的应用（会话经引导地址拿），内核子进程走替身。 */
export async function startApp(overrides: AppOverrides = {}): Promise<StartedApp> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-read-"));
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_REPORT"] = report;
  const repo = overrides.repo ?? TS_ROOT;
  const runner = new KernelRunner({
    repo,
    python: overrides.python ?? process.execPath,
    kernel: FAKE_KERNEL,
    ...(overrides.maxConcurrent === undefined ? {} : { maxConcurrent: overrides.maxConcurrent }),
    ...(overrides.maxQueue === undefined ? {} : { maxQueue: overrides.maxQueue }),
    ...(overrides.stdoutLimitBytes === undefined ? {} : { stdoutLimitBytes: overrides.stdoutLimitBytes }),
  });
  const state: ReadRoutesState = { repo, runner, cursors: new CursorTable(), transcript: overrides.transcript ?? [] };
  const app = createApp({
    port: 1,
    assets: dir,
    controlToken: "t".repeat(43),
    extraRoutes: readRoutes(state, overrides.timeouts ?? {}),
  });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  return {
    app,
    runner,
    state,
    report,
    get: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie } })),
    getAnon: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1" } })),
    getAbortable: (target) => {
      const controller = new AbortController();
      const request = new Request(`http://127.0.0.1:1${target}`, {
        headers: { host: "127.0.0.1:1", cookie },
        signal: controller.signal,
      });
      return { request, controller, send: () => app.fetch(request) };
    },
    dispose: async () => {
      delete process.env["FAKE_KERNEL_REPORT"];
      await runner.shutdown();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** 信封的正文（JSON 对象）。 */
export async function envelopeOf(response: Response): Promise<Record<string, unknown>> {
  return (await response.json()) as Record<string, unknown>;
}
