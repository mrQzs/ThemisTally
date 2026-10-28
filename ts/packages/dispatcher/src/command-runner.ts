// pi_dispatch 的命令运行器（迁移第 ④b3 片）：合同的检查项与 setup 怎么跑、记录怎么写；baseline 与 check --fresh 的干净副本；
// worktree 根与 checks/、baseline/、verdicts/ 的编号。④b5 mutate、④b7 prepare、④b8 integrate 也用它。
// 记录字段的次序照 Python 的字典；整数一律是 bigint（写进 JSON 时与 Python 的 int 一致）。
import { statSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, pyFloatOf, pyGet, pyIntOf, pyItem, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyReadTextReplace } from "@themis/base/pyio";
import { pathMkdir } from "@themis/base/pyos";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { expanduser, isWithin, ntIsabs, purePathStr, pyResolve } from "@themis/base/pypath";
import { FLAG_MULTILINE, compilePy } from "@themis/base/pyregex";
import { codePoints, isDigitChar, pyIntParse } from "@themis/base/pyre";
import { pyWhich } from "@themis/base/pyshutil";
import { pyGettempdir, pyMkdtemp } from "@themis/base/pytempfile";
import { type SuperviseResult, runSupervised } from "@themis/base/supervise";
import { ensureArgvSafe } from "./argv.ts";
import { childEnv } from "./pi-cli.ts";
import { sha256File, strArg } from "./evidence.ts";
import { snapshotTree } from "./gitops.ts";
import { DispatchError, EXIT_USAGE, type Repo, gitChecked } from "./repo.ts";
import { latestNumbered } from "./status.ts";

const WIN = process.platform === "win32";
const ESC = String.fromCharCode(27);
const BEL = String.fromCharCode(7);
const BS = String.fromCharCode(92);

/**
 * ANSI_ESCAPE_RE：CSI（ESC [ … 终止字节，颜色、光标）与 OSC（ESC ] … BEL 或 ESC 反斜杠，标题、超链接）。全是 ASCII 的字符类，
 * JS 的正则与 sre 同义。检查的输出模式对着去掉它们之后的文本匹配（第 76 轮）。
 */
const ANSI_ESCAPE = new RegExp(`${ESC}${BS}[[0-?]*[ -/]*[@-~]|${ESC}${BS}][^${BEL}${ESC}]*(?:${BEL}|${ESC}${BS}${BS})`, "g");

export const stripAnsiEscapes = (text: string): string => text.replace(ANSI_ESCAPE, "");

/** "%03d" % n：负号算在宽度里。 */
export const pad3 = (n: bigint): string => (n < 0n ? `-${String(-n).padStart(2, "0")}` : String(n).padStart(3, "0"));
export const firstPoints = (text: string, count: number): string => codePoints(text).slice(0, count).join("");

/** "%s" % value[:count]（mkdtemp 的前缀）：字符串按码点截，列表截了照 str() 写，其余照 Python 崩（手改的 meta 才会出现）。 */
export function headOf(value: PyValue, count: number): string {
  if (typeof value === "string") return firstPoints(value, count);
  if (Array.isArray(value)) return pyStrValue(value.slice(0, count));
  if (value instanceof Map) throw new PyCrash("KeyError", `slice(None, ${count}, None)`);
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** _next_number：目录里最新一个编号加一；还没有为 1。 */
export function nextNumber(directory: string): bigint {
  const latest = latestNumbered(directory);
  if (latest === null) return 1n;
  const digits = codePoints(path.basename(latest));
  let end = 0;
  while (end < digits.length && isDigitChar(digits[end] as string)) end += 1;
  return (pyIntParse(digits.slice(0, end).join("")) as bigint) + 1n;
}

/** Repo.worktree_root：配置或 PI_DISPATCH_WORKTREE_ROOT，缺省是系统临时目录下的 pi-worktrees；不能在仓库里面。 */
export function worktreeRoot(repo: Repo, config: PyDict): string {
  const fromConfig = config.get("worktree_root") ?? null;
  const configured = pyTruthy(fromConfig) ? fromConfig : process.env["PI_DISPATCH_WORKTREE_ROOT"] || null;
  const root = pyResolve(configured ? purePathStr(expanduser(pyStrValue(configured as PyValue))) : purePathStr(pyGettempdir(), "pi-worktrees"));
  if (isWithin(root, repo.root)) throw new DispatchError(`worktree_root 不能位于仓库内部：${root}`, EXIT_USAGE);
  return root;
}

/** _resolve_argv：带分隔符的程序按 cwd 拼成路径；只有名字的按子进程环境的 PATH 找（找不到就原样交给系统）。 */
export function resolveArgv(argv: readonly string[], cwd: string, env: ReadonlyMap<string, string>): string[] {
  const program = argv[0] as string;
  if (program.includes("/") || program.includes(BS)) {
    const absolute = WIN ? ntIsabs(program) : program.startsWith("/");
    return [absolute ? purePathStr(program) : purePathStr(cwd, program), ...argv.slice(1)];
  }
  const found = pyWhich(program, env.get("PATH") || env.get("Path") || null);
  return [found ?? program, ...argv.slice(1)];
}

/** run_supervised 的结果照 Python 的字典：整数是 bigint，wall_seconds 是 float。 */
export function supervisedRecord(result: SuperviseResult): [string, PyValue][] {
  const int = (value: number | null): bigint | null => (value === null ? null : BigInt(value));
  return [
    ["exit_code", int(result.exit_code)],
    ["timed_out", result.timed_out],
    ["interrupted", result.interrupted],
    ["spawn_error", result.spawn_error],
    ["wall_seconds", result.wall_seconds],
    ["stray_processes", result.stray_processes],
    ["kill_method", result.kill_method],
    ["pid", int(result.pid)],
    ["ctrl_break", result.ctrl_break],
    ["ctrl_break_winerror", int(result.ctrl_break_winerror)],
  ];
}

/**
 * _run_command_item：在 work_dir 下跑合同的一项检查或 setup，标准输出与标准错误进同一个日志（out_dir/<id>.log）。
 * cwd 跳出工作副本、argv 不安全、起不来都记 blocked；超时与取消记 failed；其余按退出码与输出模式判定。
 */
export async function runCommandItem(item: PyDict, workDir: string, env: ReadonlyMap<string, string>, outDir: string, grace: number): Promise<PyDict> {
  const cid = pyStrValue(item.get("id") as PyValue);
  const cwdRel = pyGet(item, "cwd", ".");
  // work_dir / cwd：不是字符串时 Python 抛 TypeError（冻结合同被手改才会出现）
  if (typeof cwdRel !== "string") throw new PyCrash("TypeError", `unsupported operand type(s) for /: '${WIN ? "WindowsPath" : "PosixPath"}' and '${pyTypeName(cwdRel)}'`);
  const cwd = pyResolve(purePathStr(workDir, cwdRel));
  const record: PyDict = new Map<string, PyValue>([
    ["id", item.get("id") as PyValue],
    ["argv", item.get("argv") as PyValue],
    ["cwd", cwdRel],
    ["required", pyGet(item, "required", true)],
    ["expected_exit_code", pyGet(item, "expected_exit_code", 0n)],
    ["log", `${path.basename(outDir)}/${cid}.log`],
    ["started_at", utcNow()],
  ]);
  const blocked = (reason: string): PyDict => {
    record.set("status", "blocked").set("passed", false).set("reason", reason);
    return record;
  };
  if (!isWithin(cwd, workDir) || !isDir(cwd)) return blocked("cwd 不存在或位于工作副本之外");
  const runEnv = new Map(env);
  if (!runEnv.has("CI")) runEnv.set("CI", "1");
  for (const [key, value] of (pyGet(item, "env", new Map()) as PyDict)) runEnv.set(key as string, value as string);
  const argv = resolveArgv((item.get("argv") as string[]).map(String), cwd, runEnv);
  try {
    ensureArgvSafe(argv);
  } catch (error) {
    if (error instanceof DispatchError) return blocked(error.message);
    throw error;
  }
  const logPath = path.join(outDir, `${cid}.log`);
  const result = await runSupervised(argv, {
    cwd,
    env: [...runEnv],
    stdout: { path: logPath, how: "create-new" },
    stderr: "stdout",
    timeout: Number(item.get("timeout_seconds")),
    grace,
  });
  const text = stripAnsiEscapes(pyReadTextReplace(logPath));
  const patterns = (key: string): PyDict[] =>
    (pyGet(item, key, []) as string[]).map((pattern) =>
      new Map<string, PyValue>([["pattern", pattern], ["matched", compilePy(pattern, FLAG_MULTILINE).search(text) !== null]]));
  const must = patterns("output_must_match");
  const mustNot = patterns("output_must_not_match");
  for (const [key, value] of supervisedRecord(result)) record.set(key, value);
  record
    .set("ended_at", utcNow())
    .set("log_sha256", sha256File(logPath))
    .set("log_bytes", BigInt(statSync(logPath).size))
    .set("output_must_match", must)
    .set("output_must_not_match", mustNot)
    .set("resolved_argv0", argv[0] as string);
  const exitCode = record.get("exit_code") as bigint | null;
  const expected = record.get("expected_exit_code") as PyValue;
  if (result.spawn_error) {
    record.set("status", "blocked").set("passed", false).set("reason", result.spawn_error);
  } else if (result.timed_out || result.interrupted) {
    record.set("status", "failed").set("passed", false).set("reason", result.timed_out ? "超时" : "被取消");
  } else {
    const exitOk = sameNumber(exitCode, expected);
    const ok = exitOk && must.every((m) => m.get("matched")) && !mustNot.some((m) => m.get("matched"));
    const reasons: string[] = [];
    if (!exitOk) reasons.push(`退出码 ${pyStrValue(exitCode)} ≠ 期望 ${pyStrValue(expected)}`);
    for (const m of must) if (!m.get("matched")) reasons.push(`输出未匹配 ${m.get("pattern") as string}`);
    for (const m of mustNot) if (m.get("matched")) reasons.push(`输出命中禁止模式 ${m.get("pattern") as string}`);
    record.set("status", ok ? "passed" : "failed").set("passed", ok).set("reason", reasons.join("; "));
  }
  return record;
}

/** Python 的 ==：int、bool 与 float 按数值比（True == 1）。 */
function sameNumber(left: PyValue, right: PyValue): boolean {
  const numeric = (value: PyValue): number | bigint | null =>
    typeof value === "bigint" || typeof value === "number" ? value : typeof value === "boolean" ? (value ? 1n : 0n) : null;
  const [a, b] = [numeric(left), numeric(right)];
  if (a === null || b === null) return left === right;
  return typeof a === typeof b ? a === b : Number(a) === Number(b);
}

/** _run_setup：合同的 setup 依次跑在 run_dir/setup 里，失败就停。 */
export async function runSetup(runDir: string, workDir: string, contract: PyDict, config: PyDict): Promise<PyDict[]> {
  const results: PyDict[] = [];
  const setup = contract.get("setup") as PyDict[];
  if (!setup.length) return results;
  const setupDir = path.join(runDir, "setup");
  pathMkdir(setupDir, false, false);
  const [env] = childEnv(config);
  for (const item of setup) {
    results.push(await runCommandItem(item, workDir, env, setupDir, pyFloatOf(pyGet(config, "kill_grace_seconds", 15n))));
    if (!(results[results.length - 1] as PyDict).get("passed")) break;
  }
  return results;
}

/**
 * prepare_fresh_workspace：干净的验收副本，基线 + 候选补丁 + 合同 setup，不含执行 worktree 里的任何其他文件。
 * 中途失败照 Python 不删已经建好的 worktree（调用方的 finally 只在建成之后才清理）。
 */
export async function prepareFreshWorkspace(
  repo: Repo, runDir: string, meta: PyDict, contract: PyDict, candidate: PyDict, config: PyDict, outDir: string,
  env: ReadonlyMap<string, string>, grace: number,
): Promise<string> {
  const root = worktreeRoot(repo, config);
  pathMkdir(root, true, true);
  const prefix = `${firstPoints(path.basename(repo.root), 16)}-${headOf(pyItem(meta, "task_id"), 24)}-a${pad3(pyIntOf(pyItem(meta, "attempt_no"), "%d format"))}-verify-`;
  const workspace = pyResolve(purePathStr(pyMkdtemp(prefix, root)));
  const base = strArg(pyItem(meta, "base_sha"));
  gitChecked(["worktree", "add", "--detach", workspace, base], repo.root);
  const patch = path.join(runDir, "candidate.patch");
  if (statSync(patch).size > 0) gitChecked(["apply", "--binary", "--whitespace=nowarn", patch], workspace);
  const autocrlf = meta.get("git_autocrlf") ?? null;
  if (snapshotTree(workspace, base, outDir, "fresh", autocrlf) !== candidate.get("tree")) {
    throw new DispatchError(`干净副本与候选树不一致：${workspace}`);
  }
  const setup = contract.get("setup") as PyDict[];
  if (setup.length) {
    const setupDir = path.join(outDir, "setup");
    pathMkdir(setupDir, false, false);
    for (const item of setup) {
      const record = await runCommandItem(item, workspace, env, setupDir, grace);
      if (!record.get("passed")) throw new DispatchError(`干净副本的 setup ${pyStrValue(item.get("id") as PyValue)} 失败：${pyStrValue(record.get("reason") ?? null)}`);
    }
    if (snapshotTree(workspace, base, outDir, "fresh-setup", autocrlf) !== candidate.get("tree")) {
      throw new DispatchError("setup 改动了干净副本中的候选文件或产生了未忽略的新文件");
    }
  }
  return workspace;
}
