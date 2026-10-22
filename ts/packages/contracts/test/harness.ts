// 契约测试与对照测试共用的探针驱动：同一个 JSON 请求交给每一套实现，比较 JSON 结果与磁盘上的结果。
// 实现不在本机（例如没装 Bun）时直接失败，不跳过：迁移期间三种运行方式都要能跑。
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");

export interface Impl {
  readonly name: string;
  readonly argv: readonly string[];
}

export const PYTHON: Impl = { name: "python", argv: [process.env["THEMIS_PYTHON"] ?? "python", join(PROBES, "python_probe.py")] };
export const TS_NODE: Impl = { name: "ts-node", argv: ["node", join(PROBES, "ts_probe.ts")] };
export const TS_BUN: Impl = { name: "ts-bun", argv: ["bun", join(PROBES, "ts_probe.ts")] };
export const IMPLS: readonly Impl[] = [PYTHON, TS_NODE, TS_BUN];

export interface PublishRequest {
  readonly op: "publish_new";
  readonly path: string;
  readonly data_b64: string;
  readonly barrier?: string;
}

export type ProbeResult = { readonly ok: true; readonly published: boolean } | { readonly ok: false; readonly error: string };

export function runProbe(impl: Impl, request: PublishRequest): ProbeResult {
  const [command, ...args] = impl.argv;
  const done = spawnSync(command ?? "", args, { input: JSON.stringify(request), encoding: "utf8", timeout: 30_000 });
  if (done.error) throw new Error(`${impl.name} 探针没能启动：${done.error.message}`);
  if (done.status !== 0) throw new Error(`${impl.name} 探针退出码 ${done.status}：${done.stderr}`);
  return JSON.parse(done.stdout) as ProbeResult;
}

export interface RacingProbe {
  readonly impl: Impl;
  readonly ready: Promise<void>;
  readonly result: Promise<ProbeResult>;
  /** 用例失败或超时时收掉还在等起跑的探针，不留空转的子进程。 */
  readonly stop: () => void;
}

/** 并发用例：探针起来之后先报就绪，等起跑文件出现再动手。 */
export function startProbe(impl: Impl, request: PublishRequest): RacingProbe {
  const [command, ...args] = impl.argv;
  const child = spawn(command ?? "", args, { stdio: ["pipe", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  let markReady: () => void = () => {};
  const ready = new Promise<void>((resolveReady) => {
    markReady = resolveReady;
  });
  child.stdout.setEncoding("utf8").on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.setEncoding("utf8").on("data", (chunk: string) => {
    stderr += chunk;
    if (stderr.includes("ready")) markReady(); // Windows 上 Python 的 stderr 是文本模式，换行写成 \r\n
  });
  const result = new Promise<ProbeResult>((resolveResult, reject) => {
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(`${impl.name} 探针退出码 ${code}：${stderr}`));
      else resolveResult(JSON.parse(stdout) as ProbeResult);
    });
  });
  child.stdin.end(JSON.stringify(request));
  return { impl, ready, result, stop: () => void child.kill() };
}

export function b64(data: Uint8Array): string {
  return Buffer.from(data).toString("base64");
}

export function scratchDir(prefix: string): string {
  return mkdtempSync(join(tmpdir(), `themis-contract-${prefix}-`));
}

export function removeDir(path: string): void {
  rmSync(path, { recursive: true, force: true });
}

/** 目录里每个条目：名字 → 文件字节（base64）或 "<dir>"。按名字排序，便于整份比较。 */
export function snapshot(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of readdirSync(dir).sort()) {
    const full = join(dir, name);
    out[name] = statSync(full).isDirectory() ? "<dir>" : readFileSync(full).toString("base64");
  }
  return out;
}

/** 可复现的伪随机字节（mulberry32）：对照测试的输入要能按种子重放。 */
export function seededBytes(seed: number, length: number): Uint8Array {
  let state = seed >>> 0;
  const next = (): number => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const out = new Uint8Array(length);
  for (let index = 0; index < length; index += 1) out[index] = Math.floor(next() * 256);
  return out;
}
