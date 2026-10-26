// 测试共用的起进程与发请求的工具（桌面端 T10）：服务跑在单独的 Bun 进程里，客户端在 Node 一侧（Vitest 本来就跑在
// Node 上），全部用原始套接字发 HTTP——客户端不做任何规范化，自定义 Host、Origin、Cookie、原始路径与分块正文都照原样
// 发出去。测试从不发控制台信号：收进程靠关 stdin 的写端（stdin EOF）与 kill。
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { connect, type Socket } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { bunExecutable } from "@themis/base/native";

const HERE = dirname(fileURLToPath(import.meta.url));
export const TS_ROOT = resolve(HERE, "..", "..", "..");
/** 仓库根（scripts/pi_dispatch.py 就在这儿）。 */
export const REPO_ROOT = resolve(TS_ROOT, "..");
export const CLI_ENTRY = join(TS_ROOT, "packages", "cli", "src", "main.ts");
export const SERVE_ENTRY = join(HERE, "fixtures", "serve-entry.ts");
/** 第 2 片的测试入口：pyargs 之外还能传 ServeOverrides（并发、队列、时限）与替身的 python/kernel。 */
export const OVERRIDES_ENTRY = join(HERE, "fixtures", "serve-overrides.ts");
export const BUNFIG = join(TS_ROOT, "bunfig.toml");
export const RESOLVE_ASSET_PROBE = join(HERE, "fixtures", "resolve-asset.ts");

/** 起 Bun 用的可执行文件（装好戳记里的 bun_path，取不到再退回 PATH）。 */
export function bunPath(): string {
  return bunExecutable();
}

/** 握手行：stdout 唯一的那一行 JSON。 */
export interface Handshake {
  readonly themis_ui: unknown;
  readonly bootstrap: string;
  readonly origin: string;
  readonly control: string;
  readonly pid: number;
}

export interface StartOptions {
  readonly repo: string;
  readonly assets: string;
  /** 用法错误（不带 --desktop）用。 */
  readonly desktop?: boolean;
  /** 空闲秒数；null 是缺省的 1800。 */
  readonly idleTimeout?: number | null | undefined;
  /** cli 走启动器同一条路；serve-entry 允许覆盖 nonce 有效期（T7a 的过期一条）；overrides 走第 2 片的入口。 */
  readonly entry?: "cli" | "serve-entry" | "overrides";
  readonly nonceTtlMs?: number;
  /** 起内核子进程用的 Python（第 2 片：替身是 node 跑的 fake-kernel.mjs）。 */
  readonly python?: string;
  /** 内核 CLI 的入口（第 2 片：替身的路径）。 */
  readonly kernel?: string;
  /** 传给 serveUi 的覆盖项（maxConcurrent、maxQueue、timeouts；CLI 与环境变量碰不到）。 */
  readonly overrides?: Readonly<Record<string, unknown>>;
  /** 只合进服务子进程环境的变量（不改 vitest 进程的 process.env）：慢请求用例经它把替身的门文件与睡眠时长传给服务。 */
  readonly env?: Readonly<Record<string, string>>;
}

export interface RunningService {
  readonly child: ChildProcess;
  readonly handshake: Handshake;
  readonly port: number;
  /** 关掉 stdin 等退出；没退出就杀进程树。 */
  stop(timeoutMs?: number): Promise<{ code: number | null; timedOut: boolean; killed: boolean }>;
  kill(): void;
  stdout(): string;
  stderr(): string;
}

/** 子进程的环境：去掉会让 Bun 与 Node 改行为的几项；extra 只合进这一次的子进程（慢请求用例的替身变量用）。 */
function childEnv(extra?: Readonly<Record<string, string>>): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {};
  for (const [name, value] of Object.entries(process.env)) {
    if (value === undefined) continue;
    if (/^(?:BUN_OPTIONS|NODE_OPTIONS|NODE_PATH|BUN_INSPECT)/u.test(name)) continue;
    env[name] = value;
  }
  for (const [name, value] of Object.entries(extra ?? {})) env[name] = value;
  return env;
}

function pyargs(options: StartOptions): string {
  const payload = {
    command: ["ui"],
    repo: options.repo,
    desktop: options.desktop ?? true,
    assets: options.assets,
    transcript: [],
    idle_timeout: options.idleTimeout ?? null,
    python: options.python ?? process.execPath,
    kernel: options.kernel ?? "pi_dispatch.py",
  };
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64");
}

/** ServeOverrides 的 base64（overrides 入口用）。 */
function overridesB64(options: StartOptions): string | null {
  if (options.overrides === undefined) return null;
  return Buffer.from(JSON.stringify(options.overrides), "utf8").toString("base64");
}

/** 起任意一个进程，收它的 stdout/stderr，等 stdout 里出现握手行。 */
export async function startServiceProcess(argv: readonly string[], cwd: string, timeoutMs = 45_000, extraEnv?: Readonly<Record<string, string>>): Promise<RunningService> {
  const [command, ...rest] = argv;
  if (command === undefined) throw new Error("空的命令");
  const child = spawn(command, rest, {
    cwd,
    env: childEnv(extraEnv),
    stdio: "pipe",
  });
  let out = "";
  let err = "";
  child.stdout?.setEncoding("utf8");
  child.stderr?.setEncoding("utf8");
  child.stdout?.on("data", (chunk: string) => {
    out += chunk;
  });
  child.stderr?.on("data", (chunk: string) => {
    err += chunk;
  });
  const deadline = Date.now() + timeoutMs;
  let handshake: Handshake | null = null;
  while (handshake === null) {
    for (const line of out.split("\n")) {
      const text = line.trim();
      if (text === "") continue;
      try {
        const parsed = JSON.parse(text) as Record<string, unknown>;
        if ("themis_ui" in parsed) {
          handshake = parsed as unknown as Handshake;
          break;
        }
      } catch {
        // 不是 JSON：忽略
      }
    }
    if (handshake !== null) break;
    if (child.exitCode !== null || child.signalCode !== null) break;
    if (Date.now() > deadline) break;
    await new Promise((done) => setTimeout(done, 50));
  }
  if (handshake === null) {
    child.kill();
    throw new Error(`服务没有写出握手行（退出码 ${child.exitCode}）：${err.slice(0, 800)}`);
  }
  const port = Number(new URL(handshake.origin).port);
  const stop = async (timeout = 15_000): Promise<{ code: number | null; timedOut: boolean; killed: boolean }> => {
    child.stdin?.end();
    const code = await new Promise<number | null>((done) => {
      const timer = setTimeout(() => done(null), timeout);
      child.once("exit", (value) => {
        clearTimeout(timer);
        done(value);
      });
    });
    if (code === null) {
      child.kill();
      return { code: null, timedOut: true, killed: true };
    }
    return { code, timedOut: false, killed: false };
  };
  return {
    child,
    handshake,
    port,
    stop,
    kill: () => child.kill(),
    stdout: () => out,
    stderr: () => err,
  };
}

/** 起一个服务进程（Bun 入口），等它写出握手行。 */
export async function startService(options: StartOptions, timeoutMs = 45_000): Promise<RunningService> {
  const entry = options.entry === "overrides" ? OVERRIDES_ENTRY : options.entry === "serve-entry" ? SERVE_ENTRY : CLI_ENTRY;
  const argv = [bunPath(), "--no-env-file", `--config=${BUNFIG}`, entry, "--pyargs-b64", pyargs(options)];
  const encoded = overridesB64(options);
  if (encoded !== null) argv.push("--overrides-b64", encoded);
  return startServiceProcess(argv, TS_ROOT, timeoutMs, options.env);
}

/** 跑一个应当立刻退出的进程（用法错误、锁被占），收齐全再返回。 */
export function runBrief(argv: readonly string[], timeoutMs = 60_000): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((done, fail) => {
    const [command, ...rest] = argv;
    if (command === undefined) throw new Error("空的命令");
    const child = spawn(command, rest, { cwd: TS_ROOT, env: childEnv(), stdio: "pipe" });
    let out = "";
    let err = "";
    child.stdout?.setEncoding("utf8");
    child.stderr?.setEncoding("utf8");
    child.stdout?.on("data", (chunk: string) => {
      out += chunk;
    });
    child.stderr?.on("data", (chunk: string) => {
      err += chunk;
    });
    const timer = setTimeout(() => {
      child.kill();
      fail(new Error(`进程没有在 ${timeoutMs} 毫秒内退出：${err.slice(0, 400)}`));
    }, timeoutMs);
    child.once("exit", (code) => {
      clearTimeout(timer);
      done({ code, stdout: out, stderr: err });
    });
    child.stdin?.end();
  });
}

/** 起 cli 入口（runBrief 用）。 */
export function cliArgv(options: StartOptions): string[] {
  return [bunPath(), "--no-env-file", `--config=${BUNFIG}`, CLI_ENTRY, "--pyargs-b64", pyargs(options)];
}

// ---------------------------------------------------------------------------
// HTTP 客户端（原始套接字）
// ---------------------------------------------------------------------------

export interface RawResponse {
  readonly status: number;
  readonly headers: Map<string, string>;
  readonly body: Buffer;
}

/** 取头（大小写不敏感）。 */
export function header(response: RawResponse, name: string): string | null {
  const want = name.toLowerCase();
  for (const [key, value] of response.headers) {
    if (key.toLowerCase() === want) return value;
  }
  return null;
}

function parseHead(text: string): { status: number; headers: Map<string, string> } {
  const lines = text.split("\r\n");
  const first = lines[0] ?? "";
  const status = Number(first.split(" ")[1]);
  const headers = new Map<string, string>();
  for (const line of lines.slice(1)) {
    if (line === "") continue;
    const at = line.indexOf(":");
    if (at < 0) continue;
    headers.set(line.slice(0, at).trim(), line.slice(at + 1).trim());
  }
  return { status, headers };
}

function readAll(socket: Socket): Promise<Buffer> {
  return new Promise((done, reject) => {
    const chunks: Buffer[] = [];
    socket.on("data", (chunk: Buffer) => chunks.push(chunk));
    socket.once("end", () => done(Buffer.concat(chunks)));
    socket.once("error", (error: Error) => {
      if (chunks.length > 0) done(Buffer.concat(chunks));
      else reject(new Error(`连接出错：${error.message}`));
    });
  });
}

/** 发一个请求（客户端不做规范化）：target 原样进请求行，headers 原样发出去。 */
export function request(
  port: number,
  method: string,
  target: string,
  headers: readonly (readonly [string, string])[] = [],
  body: Buffer = Buffer.alloc(0),
  host?: string,
): Promise<RawResponse> {
  return send(port, method, target, headers, body, host, true);
}

/**
 * 发一个连 Content-Length 都不带的 POST：正文长度按 HTTP/1.1 的缺省规则是 0。控制接口「不读正文」的用例用它——
 * 只带对令牌、别的什么都没有，服务也必须 200。
 */
export function requestNoBody(
  port: number,
  method: string,
  target: string,
  headers: readonly (readonly [string, string])[] = [],
  host?: string,
): Promise<RawResponse> {
  return send(port, method, target, headers, Buffer.alloc(0), host, false);
}

function send(
  port: number,
  method: string,
  target: string,
  headers: readonly (readonly [string, string])[],
  body: Buffer,
  host: string | undefined,
  declareLength: boolean,
): Promise<RawResponse> {
  const lines = [`${method} ${target} HTTP/1.1`, `Host: ${host ?? `127.0.0.1:${port}`}`, "Connection: close", "Accept: */*"];
  for (const [name, value] of headers) lines.push(`${name}: ${value}`);
  if (declareLength && method === "POST" && !headers.some(([name]) => name.toLowerCase() === "transfer-encoding")) {
    lines.push(`Content-Length: ${body.byteLength}`);
  }
  const raw = `${lines.join("\r\n")}\r\n\r\n`;
  return new Promise((done, fail) => {
    const socket = connect(port, "127.0.0.1", () => {
      // 只写、不急着半关闭：请求和 FIN 进同一个包时 Bun 会直接收掉连接不回应（实测），而响应是
      // Connection: close，服务写完自己会关，靠那一端的 end 收尾。
      socket.write(Buffer.concat([Buffer.from(raw, "latin1"), body]));
    });
    socket.setTimeout(30_000, () => socket.destroy(new Error("请求超时")));
    readAll(socket).then((buffer) => {
      const text = buffer.toString("latin1");
      const at = text.indexOf("\r\n\r\n");
      if (at < 0) {
        fail(new Error(`响应没有头：${text.slice(0, 200)}`));
        return;
      }
      const head = parseHead(text.slice(0, at));
      done({ status: head.status, headers: head.headers, body: buffer.subarray(at + 4) });
    }, fail);
  });
}

/** 分块发送：两段式（D23）。先分块发到正文累计 65537 字节（8 块 8192 加 1 块 1 字节），每块之间让出 5 毫秒；
 * 然后停下来，不发余下的块，也不发结尾的 0 块，等服务的响应头（最多 20 秒）。返回 heldBack（停发时收到了头）、
 * early（响应头在发完 0 块之前就到了）、sent（实际发出的正文字节数）与响应。响应头到了之后收到的 error
 * （ECONNRESET、EPIPE）照收到的响应算；头没到就出错，照旧判失败（不放宽）。 */
export function chunkedWatch(
  port: number,
  method: string,
  target: string,
  headers: readonly (readonly [string, string])[],
  total: number,
  chunkSize = 8192,
): Promise<{ response: RawResponse; early: boolean; sent: number; heldBack: boolean }> {
  const HOLD_AT = 65537; // 64 KiB 加 1：服务自己的计数器在这一步就回 413
  const lines = [`${method} ${target} HTTP/1.1`, `Host: 127.0.0.1:${port}`, "Connection: close", "Transfer-Encoding: chunked"];
  for (const [name, value] of headers) lines.push(`${name}: ${value}`);
  const filler = Buffer.alloc(chunkSize, 0x78);
  return new Promise((done, reject) => {
    let sent = 0;
    let buffer = Buffer.alloc(0);
    let finished = false;
    let completed = false; // 有没有发过结尾的 0 块
    const socket = connect(port, "127.0.0.1", () => {
      socket.write(`${lines.join("\r\n")}\r\n\r\n`, "latin1");
      const pump = (): void => {
        if (sent >= total) {
          completed = true;
          socket.write("0\r\n\r\n", "latin1");
          return;
        }
        // 只发恰好越过上限的字节就停（尽量不让服务关连接时还有没读走的数据）
        const capped = Math.min(chunkSize, total - sent, HOLD_AT - sent);
        if (capped <= 0) return; // 已到停发点：不发余下的块，也不发结尾的 0 块
        socket.write(Buffer.concat([Buffer.from(`${capped.toString(16)}\r\n`, "latin1"), filler.subarray(0, capped), Buffer.from("\r\n", "latin1")]));
        sent += capped;
        setTimeout(pump, 5);
      };
      pump();
    });
    socket.setTimeout(20_000, () => socket.destroy(new Error("分块请求超时")));
    const hasHead = (): boolean => buffer.includes("\r\n\r\n");
    const collect = (): void => {
      if (finished || !hasHead()) return;
      finished = true;
      const text = buffer.toString("latin1");
      const at = text.indexOf("\r\n\r\n");
      const head = parseHead(text.slice(0, at));
      const heldBack = !completed && total > HOLD_AT && sent >= HOLD_AT;
      done({ response: { status: head.status, headers: head.headers, body: buffer.subarray(at + 4) }, early: !completed, sent, heldBack });
    };
    socket.on("data", (chunk: Buffer) => {
      buffer = Buffer.concat([buffer, chunk]);
      collect();
    });
    socket.once("end", () => collect());
    socket.once("error", (error: Error) => {
      // 头已经收齐之后收到的 ECONNRESET/EPIPE 照收到的响应算；头没到就出错，照旧判失败
      if (hasHead()) collect();
      else if (!finished) reject(error);
    });
  });
}

/** 系统临时目录里的一个空目录（不写进工作区，调用方负责删除）。 */
export function systemScratch(name: string): string {
  return mkdtempSync(join(tmpdir(), `themis-ui-${name}-`));
}

// ---------------------------------------------------------------------------
// SSE 客户端（原始套接字）：连上 GET /api/v1/events，把头解析一次，正文由后台线程收进缓冲区
// ---------------------------------------------------------------------------

export interface SseClient {
  readonly status: number;
  readonly headers: Map<string, string>;
  header(name: string): string | null;
  /** 目前的正文缓冲（UTF-8）。 */
  buffer(): string;
  /** 等缓冲里出现 needle（最多 timeoutMs 毫秒）；订阅被关且仍没有就抛错。 */
  waitFor(needle: string, timeoutMs: number): Promise<void>;
  /** 把缓冲按空行拆成 SSE 块（retry / 心跳 / 事件）。 */
  blocks(): Record<string, unknown>[];
  /** 直接断开（不发 abort）：服务下一次写心跳会失败。 */
  close(): void;
  /** 等服务把流关掉（会话作废、关停）。 */
  waitClosed(timeoutMs: number): Promise<boolean>;
}

/** 连一条 SSE 订阅。 */
export async function openSse(port: number, cookie: string, lastEventId?: string): Promise<SseClient> {
  const head: [string, string][] = [
    ["Host", `127.0.0.1:${port}`],
    ["Connection", "close"],
    ["Accept", "text/event-stream"],
    ["Cookie", cookie],
  ];
  if (lastEventId !== undefined) head.push(["Last-Event-ID", lastEventId]);
  const raw = (`GET /api/v1/events HTTP/1.1\r\n` + head.map(([n, v]) => `${n}: ${v}`).join("\r\n") + "\r\n\r\n").toString();
  const socket = connect(port, "127.0.0.1");
  let buf = "";
  let closed = false;
  let status = 0;
  let headers = new Map<string, string>();
  await new Promise<void>((done, reject) => {
    const onData = (chunk: Buffer): void => {
      buf += chunk.toString("utf8");
      const at = buf.indexOf("\r\n\r\n");
      if (at >= 0 && status === 0) {
        const parsed = parseHead(buf.slice(0, at));
        status = parsed.status;
        headers = parsed.headers;
        buf = buf.slice(at + 4);
        socket.off("data", onData);
        socket.on("data", (more: Buffer) => {
          buf += more.toString("utf8");
        });
        done();
      }
    };
    socket.once("error", reject);
    socket.on("data", onData);
    socket.once("connect", () => socket.write(raw, "latin1"));
  });
  socket.on("close", () => {
    closed = true;
  });
  socket.on("error", () => {
    closed = true;
  });
  return {
    status,
    headers,
    header: (name) => header({ status, headers, body: Buffer.alloc(0) }, name),
    buffer: () => buf,
    waitFor: async (needle, timeoutMs) => {
      const deadline = Date.now() + timeoutMs;
      for (;;) {
        if (buf.includes(needle)) return;
        if (closed) throw new Error(`订阅被关掉了，没等到 ${JSON.stringify(needle)}（末尾：${buf.slice(-160)}）`);
        if (Date.now() > deadline) throw new Error(`${timeoutMs} 毫秒内没等到 ${JSON.stringify(needle)}（末尾：${buf.slice(-160)}）`);
        await new Promise((r) => setTimeout(r, 30));
      }
    },
    blocks: () => {
      const out: Record<string, unknown>[] = [];
      for (const block of buf.replace(/\r\n/g, "\n").split("\n\n")) {
        const lines = block.split("\n").filter((l) => l !== "");
        if (lines.length === 0) continue;
        const item: Record<string, unknown> = {};
        const data: string[] = [];
        for (const line of lines) {
          if (line.startsWith("id: ")) item["id"] = line.slice(4);
          else if (line.startsWith("event: ")) item["event"] = line.slice(7);
          else if (line.startsWith("data: ")) data.push(line.slice(6));
          else if (line.startsWith("retry: ")) item["retry"] = line.slice(7);
          else if (line.startsWith(":")) item["comment"] = line;
        }
        if (data.length > 0) item["data"] = data.join("\n");
        out.push(item);
      }
      return out;
    },
    close: () => socket.destroy(),
    waitClosed: async (timeoutMs) => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        if (closed) return true;
        await new Promise((r) => setTimeout(r, 30));
      }
      return closed;
    },
  };
}
