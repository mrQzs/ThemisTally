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
  /** cli 走启动器同一条路；serve-entry 允许覆盖 nonce 有效期（T7a 的过期一条）。 */
  readonly entry?: "cli" | "serve-entry";
  readonly nonceTtlMs?: number;
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

/** 子进程的环境：去掉会让 Bun 与 Node 改行为的几项。 */
function childEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {};
  for (const [name, value] of Object.entries(process.env)) {
    if (value === undefined) continue;
    if (/^(?:BUN_OPTIONS|NODE_OPTIONS|NODE_PATH|BUN_INSPECT)/u.test(name)) continue;
    env[name] = value;
  }
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
    python: process.execPath,
    kernel: "pi_dispatch.py",
  };
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64");
}

/** 起任意一个进程，收它的 stdout/stderr，等 stdout 里出现握手行。 */
export async function startServiceProcess(argv: readonly string[], cwd: string, timeoutMs = 45_000): Promise<RunningService> {
  const [command, ...rest] = argv;
  if (command === undefined) throw new Error("空的命令");
  const child = spawn(command, rest, {
    cwd,
    env: childEnv(),
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
  const entry = options.entry === "serve-entry" ? SERVE_ENTRY : CLI_ENTRY;
  const argv = [bunPath(), "--no-env-file", `--config=${BUNFIG}`, entry, "--pyargs-b64", pyargs(options)];
  return startServiceProcess(argv, TS_ROOT, timeoutMs);
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

/** 分块发送 total 字节，边发边看服务是不是提前回响应。 */
export function chunkedWatch(
  port: number,
  method: string,
  target: string,
  headers: readonly (readonly [string, string])[],
  total: number,
  chunkSize = 8192,
): Promise<{ response: RawResponse; early: boolean; sent: number }> {
  const lines = [`${method} ${target} HTTP/1.1`, `Host: 127.0.0.1:${port}`, "Connection: close", "Transfer-Encoding: chunked"];
  for (const [name, value] of headers) lines.push(`${name}: ${value}`);
  const filler = Buffer.alloc(chunkSize, 0x78);
  return new Promise((done, reject) => {
    let sent = 0;
    let buffer = Buffer.alloc(0);
    let finished = false;
    const socket = connect(port, "127.0.0.1", () => {
      socket.write(`${lines.join("\r\n")}\r\n\r\n`, "latin1");
      const pump = (): void => {
        if (sent >= total) {
          socket.write("0\r\n\r\n", "latin1");
          return;
        }
        const size = Math.min(chunkSize, total - sent);
        socket.write(Buffer.concat([Buffer.from(`${size.toString(16)}\r\n`, "latin1"), filler.subarray(0, size), Buffer.from("\r\n", "latin1")]));
        sent += size;
        setTimeout(pump, 0);
      };
      pump();
    });
    socket.setTimeout(40_000, () => socket.destroy(new Error("分块请求超时")));
    const collect = (early: boolean): void => {
      if (finished) return;
      finished = true;
      const text = buffer.toString("latin1");
      const at = text.indexOf("\r\n\r\n");
      if (at < 0) {
        reject(new Error(`响应没有头：${text.slice(0, 200)}`));
        return;
      }
      const head = parseHead(text.slice(0, at));
      done({ response: { status: head.status, headers: head.headers, body: buffer.subarray(at + 4) }, early, sent });
    };
    socket.on("data", (chunk: Buffer) => {
      buffer = Buffer.concat([buffer, chunk]);
      collect(true);
    });
    socket.once("end", () => collect(false));
    socket.once("error", (error: Error) => reject(error));
  });
}

/** 系统临时目录里的一个空目录（不写进工作区，调用方负责删除）。 */
export function systemScratch(name: string): string {
  return mkdtempSync(join(tmpdir(), `themis-ui-${name}-`));
}
