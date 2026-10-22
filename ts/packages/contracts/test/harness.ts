// 契约测试与对照测试共用的探针驱动：同一个 JSON 请求交给每一套实现，比较 JSON 结果与磁盘上的结果。
// 实现不在本机（例如没装 Bun）时直接失败，不跳过：迁移期间三种运行方式都要能跑。
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
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

/** 探针请求：op 加各自的参数；op 为 "batch" 时 items 是一串请求，一个进程办完（对照测试一次送几百个值）。 */
export interface ProbeRequest {
  readonly op: string;
  readonly barrier?: string;
  readonly [key: string]: unknown;
}

/** 探针结果：ok 为 false 时 error 是错误码（ENOENT…）或 Python 的异常类名（TypeError…）。 */
export interface ProbeResult {
  readonly ok: boolean;
  readonly error?: string;
  readonly [key: string]: unknown;
}

export function runProbe(impl: Impl, request: ProbeRequest): ProbeResult {
  const [command, ...args] = impl.argv;
  const done = spawnSync(command ?? "", args, {
    input: JSON.stringify(request),
    encoding: "utf8",
    timeout: 60_000,
    maxBuffer: 256 * 1024 * 1024,
  });
  if (done.error) throw new Error(`${impl.name} 探针没能启动：${done.error.message}`);
  if (done.status !== 0) throw new Error(`${impl.name} 探针退出码 ${done.status}：${done.stderr}`);
  return JSON.parse(done.stdout) as ProbeResult;
}

/** 一批请求交给一个探针进程，按顺序返回各自的结果。 */
export function runBatch(impl: Impl, items: readonly ProbeRequest[]): ProbeResult[] {
  const result = runProbe(impl, { op: "batch", items });
  if (!result.ok || !Array.isArray(result["results"])) throw new Error(`${impl.name} 批量请求失败：${JSON.stringify(result)}`);
  return result["results"] as ProbeResult[];
}

export interface RacingProbe {
  readonly impl: Impl;
  readonly ready: Promise<void>;
  readonly result: Promise<ProbeResult>;
  /** 用例失败或超时时收掉还在等起跑的探针，不留空转的子进程。 */
  readonly stop: () => void;
}

/** 并发用例：探针起来之后先报就绪，等起跑文件出现再动手。 */
export function startProbe(impl: Impl, request: ProbeRequest): RacingProbe {
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

// --- 命令行对照（第 ② 步）：Python 走真实的 argv，TS 走启动器交来的规整参数（--pyargs-b64） ---------------

const REPO_ROOT = resolve(PROBES, "..", "..", "..", "..");
const CLI_MAIN = resolve(PROBES, "..", "..", "cli", "src", "main.ts");

export interface CliRun {
  readonly status: number;
  readonly stdout: Buffer;
  readonly stderr: Buffer;
}

function cliRun(command: string, args: readonly string[], cwd: string): CliRun {
  const done = spawnSync(command, args, { cwd, timeout: 120_000, maxBuffer: 256 * 1024 * 1024 });
  if (done.error) throw new Error(`${command} 没能启动：${done.error.message}`);
  return { status: done.status ?? -1, stdout: done.stdout, stderr: done.stderr };
}

// 选择文件（迁移计划第 5 节）：提交的那份让 status、logs 转交给 TS，作对照基准的 Python 一边要钉成 python。
// 钉成 python 指向一个不存在的文件（等于全部 python）；走启动器指向一份 readonly 为 ts 的临时文件。
const SELECTOR_DIR = mkdtempSync(join(tmpdir(), "themis-selector-"));
const PYTHON_SELECTOR = join(SELECTOR_DIR, "absent.json");
const TS_SELECTOR = join(SELECTOR_DIR, "readonly-ts.json");
writeFileSync(TS_SELECTOR, JSON.stringify({ schema_version: 1, readonly: "ts", config: "python", dispatcher: "python", hub: "python" }));
process.on("exit", () => rmSync(SELECTOR_DIR, { recursive: true, force: true }));

/** 独立的 Python 进程里改 pi_dispatch 的 KERNEL_IMPL_PATH 再调 pd.main(argv)。JSON 的字符串与数组照样是 Python
 * 的字面量（孤立代理项写成 \udXXX，Python 读回来仍是孤立代理项，与命令行上的 argv 一样）。 */
function pdMain(selector: string, argv: readonly string[], cwd: string): CliRun {
  const program = [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO_ROOT, "scripts"))})`,
    "import pi_dispatch as pd",
    `pd.KERNEL_IMPL_PATH = pd.Path(${JSON.stringify(selector)})`,
    `sys.exit(pd.main(${JSON.stringify(argv)}))`,
  ].join("\n");
  return cliRun(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program], cwd);
}

/** pi_dispatch 的 <argv>，钉成 Python 实现回答（对照的基准）。 */
export function runPythonCli(argv: readonly string[], cwd: string): CliRun {
  return pdMain(PYTHON_SELECTOR, argv, cwd);
}

/** pi_dispatch 的 <argv>，选择文件的 readonly 是 ts：经真的启动器转交给 TS（参数由启动器从 argparse 的结果生成，
 * 句柄继承、Job、退出码与输出次序都是真的）。 */
export function runLauncherCli(argv: readonly string[], cwd: string): CliRun {
  return pdMain(TS_SELECTOR, argv, cwd);
}

/** TS 入口：参数是 Python 启动器解析好之后交来的那一份。 */
export function runTsCli(runtime: "node" | "bun", pyargs: Record<string, unknown>, cwd: string): CliRun {
  // bigint 写成 JSON 整数原样（Python 的 int 不受 JS 数字精度限制）
  const json = JSON.stringify(pyargs, (_key, value: unknown) => (typeof value === "bigint" ? `\u0000big:${value}` : value))
    .replace(/"\\u0000big:(-?\d+)"/gu, "$1");
  const encoded = Buffer.from(json, "utf8").toString("base64");
  return cliRun(runtime, [CLI_MAIN, "--pyargs-b64", encoded], cwd);
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

/** 可复现的伪随机数（mulberry32），取值 [0, 1)：对照测试的输入要能按种子重放。 */
export function prng(seed: number): () => number {
  let state = seed >>> 0;
  return (): number => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 可复现的伪随机字节。 */
export function seededBytes(seed: number, length: number): Uint8Array {
  const next = prng(seed);
  const out = new Uint8Array(length);
  for (let index = 0; index < length; index += 1) out[index] = Math.floor(next() * 256);
  return out;
}
