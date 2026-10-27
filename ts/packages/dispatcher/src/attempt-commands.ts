// pi_dispatch 处理一个 attempt 的三条命令（迁移第 ④b2 片）：mark、cleanup、wait（--assess 属于 ④b4，这里不接）。
// 证据坏了（缺 meta.json、缺键、类型不对）时 Python 不接、命令崩溃，这里照样抛出（PyCrash 等），入口按崩溃处理。
import { readdirSync, statSync } from "node:fs";
import path from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import { PyCrash, type PyOut, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue } from "@themis/base/pyjson";
import { displayPath, normCase } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, isDigitChar, pyIntParse, pyLower, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pidAlive } from "@themis/base/process";
import { pyEq } from "@themis/base/pyvalue";
import {
  PASSING_VERDICTS, TERMINAL_STATES, artifactMatchers, candidatePatchOk, loadAttempt, logEvent, pathArg, removeWorktree, setState, splitExtras, strArg,
} from "./evidence.ts";
import { snapshotTree, treeDrift } from "./gitops.ts";
import { repoConfig } from "./kernel-config.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, gitChecked, readJsonOr } from "./repo.ts";
import { getState, latestVerdict, liveFacts, liveText, resolveRunDir } from "./status.ts";

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** dict.get：不是字典时照 Python 抛 AttributeError。 */
function dictGet(value: PyValue, key: string, fallback: PyValue = null): PyValue {
  if (!isDict(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'get'`);
  return value.has(key) ? (value.get(key) as PyValue) : fallback;
}

/** dict[key]：不是字典、没有这个键时照 Python 抛异常。 */
function dictItem(value: PyValue, key: string): PyValue {
  if (!isDict(value)) throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
  if (!value.has(key)) throw new PyCrash("KeyError", `'${key}'`);
  return value.get(key) as PyValue;
}

function exists(file: string): boolean {
  try {
    statSync(file);
    return true;
  } catch {
    return false;
  }
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

// --- mark -----------------------------------------------------------------------------------------

export interface MarkArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly state: "INTEGRATED" | "ABANDONED" | "SUPERSEDED";
  readonly ref: string | null;
  readonly reason: string | null;
  readonly force: boolean;
}

const ENDED_NOT_INTEGRATED = ["REVISE", "ESCALATE", "BLOCKED", "NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE"];

export function cmdMark(args: MarkArgs, out: PyOut): number {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const state = getState(runDir);
  if (args.state === "INTEGRATED") {
    const verdict = dictGet(latestVerdict(runDir), "verdict");
    if (!PASSING_VERDICTS.some((item) => pyEq(item, verdict))) {
      throw new DispatchError("只有通过验收的候选可以标记为 INTEGRATED；候选已并入后续提交（返工或规划器补齐）时用 SUPERSEDED");
    }
    if (!args.ref) throw new DispatchError("INTEGRATED 需要 --ref（提交、PR 或合并记录）", EXIT_USAGE);
  } else if (args.state === "SUPERSEDED") {
    // 候选没有单独通过验收，但已经并入后续提交：不再是“待集成”，也不是被放弃
    if (!ENDED_NOT_INTEGRATED.includes(state)) throw new DispatchError(`SUPERSEDED 只用于已结束、尚未集成的 attempt（当前 ${state}）`, EXIT_USAGE);
    if (!args.ref || !args.reason) throw new DispatchError("SUPERSEDED 需要 --ref（包含该候选的提交）与 --reason（由谁、怎样收尾）", EXIT_USAGE);
  } else if (["RUNNING", "COLLECTING", "PREPARING"].includes(state)) {
    // 调度器异常退出后可能停在这些状态；只有确认没有进程在运行时才允许放弃
    if (!args.force) throw new DispatchError(`attempt 处于 ${state}；如果确认调度器已退出，可加 --force 放弃`);
    const pidText = recordedPid(runDir);
    if (isDigits(pidText) && pidAlive(Number(pidOf(pidText))) === true) throw new DispatchError(`记录的 Pi 进程 ${pidText} 仍在运行，不能放弃`);
  }
  setState(runDir, args.state, [["ref", args.ref], ["reason", args.reason], ["previous_state", state]]);
  out.print(`${displayPath(runDir, repo.root)} 已标记为 ${args.state}。`);
  return EXIT_OK;
}

/** pid.txt 的内容去掉两头空白；没有这个文件时为空串。读不出、不是 UTF-8 时 Python 不接。 */
function recordedPid(runDir: string): string {
  const file = path.join(runDir, "pid.txt");
  return exists(file) ? pyStrip(pyReadText(file)) : "";
}

const isDigits = (text: string): boolean => text.length > 0 && codePoints(text).every(isDigitChar);

/** int(text)：isdigit 为真、int() 却不收的字符（例如 ²）照 Python 抛 ValueError。 */
function pidOf(text: string): bigint {
  const value = pyIntParse(text);
  if (value === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: '${text}'`);
  return value;
}

// --- cleanup --------------------------------------------------------------------------------------

export interface CleanupArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly force: boolean;
}

/** _registered_worktrees：git worktree list --porcelain 里登记的路径。 */
function registeredWorktrees(repo: Repo): string[] {
  const listing = new TextDecoder("utf-8").decode(gitChecked(["worktree", "list", "--porcelain"], repo.root).stdout);
  return pySplitlines(listing).filter((line) => line.startsWith("worktree ")).map((line) => line.slice("worktree ".length));
}

export function cmdCleanup(args: CleanupArgs, out: PyOut): number {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta] = loadAttempt(runDir);
  const state = getState(runDir);
  if (state === "RUNNING" || state === "COLLECTING") {
    throw new DispatchError(`attempt 正在运行或收集（${state}），不能清理；调度器已退出时先 collect --recover`);
  }
  if ((state === "PREPARED" || state === "PREPARING") && !args.force) throw new DispatchError(`attempt 尚未运行（${state}）；确定放弃请加 --force`);
  const registered = registeredWorktrees(repo);
  const isRegistered = (worktree: string): boolean => registered.some((item) => normCase(item) === normCase(worktree));
  const workDir = pathArg(dictItem(meta, "worktree"));
  const lost: string[] = [];
  if (isRegistered(workDir)) {
    lost.push(...lostContent(repo, runDir, meta, workDir));
    if (lost.length && !args.force) {
      for (const item of lost) out.print(`LOSS  ${item}`);
      throw new DispatchError("拒绝清理：以上内容不在已保存的候选中，删除 worktree 会丢失它们。先保存需要的内容；确认放弃请加 --force。");
    }
    gitChecked(["worktree", "remove", "--force", workDir], repo.root);
    out.print(`已移除 worktree：${workDir}`);
  } else if (exists(workDir) && hasEntries(workDir)) {
    throw new DispatchError(`${workDir} 存在但不是本仓库登记的 worktree，拒绝删除`);
  } else {
    out.print(`worktree 已不存在或未创建：${workDir}`);
  }
  // 保留下来的干净验收副本（check --fresh --keep-workspace）不含独有内容，一并移除
  for (const checksFile of keptCheckRecords(runDir)) {
    const record = readJsonOr(checksFile, new Map());
    const workspace = pyTruthy(dictGet(record, "workspace_kept")) ? pathArg(dictGet(record, "workspace", "")) : null;
    if (workspace !== null && isRegistered(workspace)) {
      removeWorktree(repo, workspace);
      out.print(`已移除验收副本：${workspace}`);
    }
  }
  logEvent(runDir, "cleanup", [["worktree", workDir], ["state", state], ["forced", args.force], ["discarded", lost]]);
  return EXIT_OK;
}

/** 删除登记的 worktree 会丢掉的内容：没有候选记录、补丁核对不过、候选之后改过的文件、候选之外的新文件。 */
function lostContent(repo: Repo, runDir: string, meta: PyValue, workDir: string): string[] {
  const lost: string[] = [];
  const candidate = readJsonOr(path.join(runDir, "candidate.json"), new Map());
  if (!pyTruthy(dictGet(candidate, "tree"))) return ["没有候选记录：worktree 中的全部改动都会丢失"];
  if (!candidatePatchOk(runDir, candidate)) lost.push("候选补丁缺失、被改动或未通过往返校验：删除后无法重建候选");
  try {
    const now = snapshotTree(workDir, strArg(dictItem(meta, "base_sha")), runDir, "cleanup", dictGet(meta, "git_autocrlf"));
    const drift = treeDrift(workDir, strArg(dictItem(candidate, "tree")), now);
    const [, unexpected] = splitExtras(drift.added, artifactMatchers(repoConfig(repo)));
    if (drift.modified.length) lost.push(`候选记录之后被修改的文件：${drift.modified.slice(0, 20).join(", ")}`);
    if (unexpected.length) lost.push(`候选之外的新文件：${unexpected.slice(0, 20).join(", ")}`);
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    lost.push(`无法核对 worktree 内容：${error.message}`);
  }
  return lost;
}

/** any(path.iterdir())：不是目录时 Python 抛 NotADirectoryError。 */
function hasEntries(dir: string): boolean {
  if (!isDir(dir)) throw new PyCrash("NotADirectoryError", `[WinError 267] 目录名称无效。: '${dir}'`);
  return readdirSync(dir).length > 0;
}

/**
 * run_dir/checks 下各子目录里的 checks.json（Python 是 sorted 加 glob）：子目录里有 checks.json 的（Windows 上文件名不分大小写，交回的路径按
 * 模式的写法），按 Path 的次序排：前面几段相同，只比子目录名（Windows 上转成小写再比），按码点。
 */
function keptCheckRecords(runDir: string): string[] {
  const checks = path.join(runDir, "checks");
  if (!isDir(checks)) return [];
  const key = (name: string): string => (process.platform === "win32" ? pyLower(name) : name);
  return readdirSync(checks)
    .filter((name) => isDir(path.join(checks, name)) && exists(path.join(checks, name, "checks.json")))
    .sort((a, b) => cmpCodePoints(key(a), key(b)))
    .map((name) => path.join(checks, name, "checks.json"));
}

// --- wait -----------------------------------------------------------------------------------------

export interface WaitArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly timeout: bigint;
  readonly interval: number;
}

const WAIT_ACTIVE_STATES = ["PREPARING", "RUNNING", "COLLECTING"];

/** Python 的 min、max：比较不成立时留第一个（NaN 不会传染）。 */
const pyMin = (a: number, b: number): number => (b < a ? b : a);
const pyMax = (a: number, b: number): number => (b > a ? b : a);

/**
 * wait：进入明确的结束状态时打印状态并退出 0；到时仍在运行时打印进度并退出 3。刚在后台启动的 run 可能还没领取，PREPARED
 * 最多再等 min(60, timeout) 秒。state.json 缺失、损坏或状态未知时退出 1。
 */
export function cmdWait(args: WaitArgs, out: PyOut): number {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  if (args.timeout < 1n) throw new DispatchError("--timeout 必须是正整数（秒）", EXIT_USAGE);
  const timeout = Number(args.timeout);
  const started = performance.now();
  const shown = displayPath(runDir, repo.root);
  for (;;) {
    const state = getState(runDir);
    const elapsed = (performance.now() - started) / 1000;
    if (WAIT_ACTIVE_STATES.includes(state) || (state === "PREPARED" && elapsed < pyMin(60, timeout))) {
      if (elapsed >= timeout) {
        const progress = state === "RUNNING" ? liveText(liveFacts(runDir)) : "";
        out.print(`仍在运行：${shown} · ${state}${progress ? ` · ${progress}` : ""}。再次运行 wait 继续等待。`);
        return EXIT_BLOCKED;
      }
      sleepSync(pyMax(0.2, pyMin(args.interval, timeout - elapsed)) * 1000);
      continue;
    }
    if (state === "PREPARED") {
      out.print(`attempt 仍是 PREPARED：run 没有开始（或启动前就失败了）。检查后台命令的输出：${shown}`);
      return EXIT_BLOCKED;
    }
    if (!TERMINAL_STATES.includes(state)) {
      out.print(`无法确定 attempt 的状态（${state}）：state.json 缺失、损坏或状态未知。检查 ${shown}`);
      return EXIT_FAIL;
    }
    out.print(`已结束：${shown} · ${state}`);
    const summary = path.join(runDir, "summary.md");
    if (isFile(summary)) out.print(`摘要：${displayPath(summary, repo.root)}`);
    return EXIT_OK;
  }
}
