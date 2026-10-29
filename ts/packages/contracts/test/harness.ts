// 契约测试与对照测试共用的探针驱动：同一个 JSON 请求交给每一套实现，比较 JSON 结果与磁盘上的结果。
// 实现不在本机（例如没装 Bun）时直接失败，不跳过：迁移期间三种运行方式都要能跑。
import { spawn, spawnSync } from "node:child_process";
import { closeSync, mkdtempSync, openSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { bunExecutable } from "@themis/base/native";

const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");

export interface Impl {
  readonly name: string;
  readonly argv: readonly string[];
}

export const PYTHON: Impl = { name: "python", argv: [process.env["THEMIS_PYTHON"] ?? "python", join(PROBES, "python_probe.py")] };
export const TS_NODE: Impl = { name: "ts-node", argv: ["node", join(PROBES, "ts_probe.ts")] };
// Bun 照启动器的来源找（THEMIS_BUN、装好戳记的 bun_path、PATH 上的 bun.exe 或 npm 垫片旁边那个），不按名字起：npm
// 全局装的 Bun 在 PATH 上只有 .cmd 垫片，Node 不经 shell 起不了（themistally-15 复核 ④a：照缺省的 PATH，24 条契约里
// 23 条报 spawn bun ENOENT）
export const BUN = bunExecutable();
export const TS_BUN: Impl = { name: "ts-bun", argv: [BUN, join(PROBES, "ts_probe.ts")] };
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

/** merged：标准输出与标准错误写进同一个文件（hub 读到的就是这样的次序，④b3），合并的字节放在 stdout。 */
function cliRun(command: string, args: readonly string[], cwd: string, merged = false): CliRun {
  if (merged) return mergedRun(command, args, cwd);
  const done = spawnSync(command, args, { cwd, timeout: 120_000, maxBuffer: 256 * 1024 * 1024 });
  if (done.error) throw new Error(`${command} 没能启动：${done.error.message}`);
  return { status: done.status ?? -1, stdout: done.stdout, stderr: done.stderr };
}

function mergedRun(command: string, args: readonly string[], cwd: string): CliRun {
  const dir = mkdtempSync(join(tmpdir(), "themis-merged-"));
  const file = join(dir, "out");
  const fd = openSync(file, "w");
  try {
    const done = spawnSync(command, args, { cwd, timeout: 120_000, stdio: ["pipe", fd, fd] });
    if (done.error) throw new Error(`${command} 没能启动：${done.error.message}`);
    closeSync(fd);
    return { status: done.status ?? -1, stdout: readFileSync(file), stderr: Buffer.alloc(0) };
  } finally {
    try {
      closeSync(fd);
    } catch {
      // 已经关过
    }
    rmSync(dir, { recursive: true, force: true });
  }
}

// 选择文件（迁移计划第 5 节）：提交的那份让 status、logs 转交给 TS，作对照基准的 Python 一边要钉成 python。
// 钉成 python 指向一个不存在的文件（等于全部 python）；走启动器指向一份 readonly 为 ts 的临时文件。
const SELECTOR_DIR = mkdtempSync(join(tmpdir(), "themis-selector-"));
const PYTHON_SELECTOR = join(SELECTOR_DIR, "absent.json");
const TS_SELECTOR = join(SELECTOR_DIR, "readonly-ts.json");
writeFileSync(TS_SELECTOR, JSON.stringify({ schema_version: 1, readonly: "ts", config: "python", dispatcher: "python", hub: "python" }));
const CONFIG_TS_SELECTOR = join(SELECTOR_DIR, "config-ts.json");
writeFileSync(CONFIG_TS_SELECTOR, JSON.stringify({ schema_version: 1, readonly: "ts", config: "ts", dispatcher: "python", hub: "python" }));
const DISPATCHER_TS_SELECTOR = join(SELECTOR_DIR, "dispatcher-ts.json");
writeFileSync(DISPATCHER_TS_SELECTOR, JSON.stringify({ schema_version: 1, readonly: "ts", config: "ts", dispatcher: "ts", hub: "python" }));
process.on("exit", () => rmSync(SELECTOR_DIR, { recursive: true, force: true }));

/** 独立的 Python 进程里改 pi_dispatch 的 KERNEL_IMPL_PATH 再调 pd.main(argv)。JSON 的字符串与数组照样是 Python
 * 的字面量（孤立代理项写成 \udXXX，Python 读回来仍是孤立代理项，与命令行上的 argv 一样）。 */
function pdProgram(selector: string, argv: readonly string[], kitRoot?: string): string {
  return [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO_ROOT, "scripts"))})`,
    "import pi_dispatch as pd",
    `pd.KERNEL_IMPL_PATH = pd.Path(${JSON.stringify(selector)})`,
    // 换 kit 根（插件夹具）：照 kit_plugins oracle 的做法改模块常量，TS 一侧经 pyargs 的 context 拿到同一个目录
    ...(kitRoot === undefined ? [] : [`pd.KIT_ROOT = pd.Path(${JSON.stringify(kitRoot)})`, 'pd.DECISIONS_PLUGIN_DIR = pd.KIT_ROOT / "plugins" / "decisions"']),
    `sys.exit(pd.main(${JSON.stringify(argv)}))`,
  ].join("\n");
}

function pdMain(selector: string, argv: readonly string[], cwd: string, kitRoot?: string, merged = false): CliRun {
  return cliRun(process.env["THEMIS_PYTHON"] ?? "python", ["-c", pdProgram(selector, argv, kitRoot)], cwd, merged);
}

/** 经真启动器、选择文件的 dispatcher 为 ts 的命令行（切换 b：中断用例给启动器的进程组发 CTRL_BREAK，由它转发给 TS）。 */
export function dispatcherLauncherCommand(argv: readonly string[]): string[] {
  return [process.env["THEMIS_PYTHON"] ?? "python", "-c", pdProgram(DISPATCHER_TS_SELECTOR, argv)];
}

/** 钉成 Python 实现的命令行（程序加参数）：自己起进程的用例用（④b3 的中断用例另起进程组）。 */
export function pythonCliCommand(argv: readonly string[]): string[] {
  return [process.env["THEMIS_PYTHON"] ?? "python", "-c", pdProgram(PYTHON_SELECTOR, argv)];
}

/** pi_dispatch 的 <argv>，钉成 Python 实现回答（对照的基准）。 */
export function runPythonCli(argv: readonly string[], cwd: string, merged = false): CliRun {
  return pdMain(PYTHON_SELECTOR, argv, cwd, undefined, merged);
}

/** 同 runPythonCli，kit 根换成 kitRoot（plugins/ 与决策插件都从那里读）。 */
export function runPythonCliAt(kitRoot: string, argv: readonly string[], cwd: string): CliRun {
  return pdMain(PYTHON_SELECTOR, argv, cwd, kitRoot);
}

/** pi_dispatch 的 <argv>，选择文件的 readonly 是 ts：经真的启动器转交给 TS（参数由启动器从 argparse 的结果生成，
 * 句柄继承、Job、退出码与输出次序都是真的）。 */
export function runLauncherCli(argv: readonly string[], cwd: string): CliRun {
  return pdMain(TS_SELECTOR, argv, cwd);
}

/** 第 ③ 步切换之后的写法：选择文件的 config 也是 ts，config、plugins 命令经真的启动器转交给 TS（pyargs 由
 * pi_dispatch.config_handoff 从 argparse 的结果生成）。kitRoot 同 runPythonCliAt。 */
export function runConfigLauncherCli(argv: readonly string[], cwd: string, kitRoot?: string): CliRun {
  return pdMain(CONFIG_TS_SELECTOR, argv, cwd, kitRoot);
}

/**
 * 第 ④ 步切换之后的写法：选择文件的 dispatcher 也是 ts，调度器命令经真的启动器转交给 TS（pyargs 由
 * pi_dispatch.dispatcher_handoff 从 argparse 的结果生成，context 是启动器自己的本机事实）。kitRoot 同 runPythonCliAt。
 */
export function runDispatcherLauncherCli(argv: readonly string[], cwd: string, merged = false, kitRoot?: string): CliRun {
  return pdMain(DISPATCHER_TS_SELECTOR, argv, cwd, kitRoot, merged);
}

/** 起子进程用的选择文件路径（并发用例自己起 pd.main）。 */
export const SELECTORS = { python: PYTHON_SELECTOR, configTs: CONFIG_TS_SELECTOR, dispatcherTs: DISPATCHER_TS_SELECTOR } as const;

/** TS 入口：参数是 Python 启动器解析好之后交来的那一份。 */
/** TS 入口的命令行（程序加参数），同 pythonCliCommand。 */
export function tsCliCommand(runtime: "node" | "bun", pyargs: Record<string, unknown>): string[] {
  // bigint 写成 JSON 整数原样（Python 的 int 不受 JS 数字精度限制）
  const json = JSON.stringify(pyargs, (_key, value: unknown) => (typeof value === "bigint" ? `\u0000big:${value}` : value))
    .replace(/"\\u0000big:(-?\d+)"/gu, "$1");
  const encoded = Buffer.from(json, "utf8").toString("base64");
  return [runtime === "bun" ? BUN : runtime, CLI_MAIN, "--pyargs-b64", encoded];
}

export function runTsCli(runtime: "node" | "bun", pyargs: Record<string, unknown>, cwd: string, merged = false): CliRun {
  const [command, ...args] = tsCliCommand(runtime, pyargs);
  return cliRun(command as string, args, cwd, merged);
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

// --- 第 ③ 步：配置中心 ----------------------------------------------------------------------

/** 仓库根：契约可以只读真实数据（例如 plugins/ 下提交的 manifest 与锁）。 */
export const REPO = REPO_ROOT;

export interface Mismatch {
  readonly impl: string;
  readonly index: number;
  readonly request: ProbeRequest;
  readonly python: ProbeResult | undefined;
  readonly other: ProbeResult | undefined;
}

/** 同一批请求交给每一套实现：以 Python 的结果为准，其余逐条比较（JSON 文本相同才算一致）。 */
export function runAgreeing(requests: readonly ProbeRequest[]): { python: ProbeResult[]; mismatches: Mismatch[] } {
  const [python = [], ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  const mismatches: Mismatch[] = [];
  others.forEach((results, position) => {
    requests.forEach((request, index) => {
      if (JSON.stringify(results[index]) !== JSON.stringify(python[index])) {
        mismatches.push({ impl: IMPLS[position + 1]?.name ?? "?", index, request, python: python[index], other: results[index] });
      }
    });
  });
  return { python, mismatches };
}
