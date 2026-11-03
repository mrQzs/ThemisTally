// 结项与落地（迁移第 ⑤h1 片）：kit_hub.py 的 landing_blockers、finalize、landing_records、undo_landing、landed_meanwhile、commit_records、
// on_branch、landing_chain、land_oracle、land_rework_chain、record_pass，以及结项后的收尾 remove_workspaces、retire_attempts、tidy_finished。
// 后台回归与落地预演在 sweep.ts（⑤h2）。deps 只给契约用（照 ⑤g2）：用例当时换掉的 run_pd、调度器的 _running_attempts，以及执行标记的
// pid_alive（标记记的是采样进程的 pid）照记录注入；生产调用方不传。执行标记、oracle、rework_chain、workspaces 与 meta.json 可以是任何 JSON 值：取键、迭代、格式化与报错照 Python。
import { statSync } from "node:fs";
import { utcNow } from "@themis/base/clock";
import { readText } from "@themis/base/fsutil";
import { pyCaught } from "@themis/base/pyexc";
import { PyCrash, pyGet, pyIntOf, pyItem, pyIter, pyPlus, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { purePathName, purePathStr, pyExists } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pidAlive } from "@themis/base/process";
import { pyEq } from "@themis/base/pyvalue";
import { globPaths } from "@themis/dispatcher/instruction";
import { runningAttempts } from "@themis/dispatcher/integrate";
import { DispatchError, Repo } from "@themis/dispatcher/repo";
import { pathArg } from "@themis/dispatcher/evidence";
import { getState } from "@themis/dispatcher/status";
import { type ContractDeps, REAL_DEPS } from "./accept.ts";
import { comparePaths, pyDictOf } from "./audit.ts";
import { tail } from "./contract.ts";
import { HubError } from "./errors.ts";
import { ATTEMPT_IN_FLIGHT, emptyCommit, pySliceHead } from "./exec.ts";
import { attemptBase } from "./gatepost.ts";
import { git, workspaceStatus } from "./kernel.ts";
import type { Hub } from "./mailbox.ts";
import { argText, execMarks, runGit, runMerged, writeReview } from "./runexec.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const WIN = process.platform === "win32";

/** 用例当时换掉、契约照记录注入的内层调用；缺省是真的。 */
export interface LandDeps extends ContractDeps {
  /** pd._running_attempts(pd.Repo(hub.repo))。 */
  readonly runningAttempts: (repo: Repo) => string[];
  /** pd.pid_alive：执行标记的持有进程还在不在（不知道是 None）。 */
  readonly pidAlive: (pid: number) => boolean | null;
}

export const REAL_LAND_DEPS: LandDeps = { ...REAL_DEPS, runningAttempts, pidAlive };

/** x or y。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);
/** value[:12]，再照 "%s" 格式化。 */
const short = (value: PyValue): string => pyStrValue(pySliceHead(value, 12));

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** Path.stem：最后一个点之前（点在开头或末尾时整个名字）。 */
function stem(path: string): string {
  const name = purePathName(path);
  const at = name.lastIndexOf(".");
  return at > 0 && at < name.length - 1 ? name.slice(0, at) : name;
}

/** Path.suffix。 */
function suffix(path: string): string {
  const name = purePathName(path);
  const at = name.lastIndexOf(".");
  return at > 0 && at < name.length - 1 ? name.slice(at) : "";
}

/** Path / value：value 不是字符串时照 Python 报 TypeError。 */
function joinPath(base: string, value: PyValue): string {
  if (typeof value !== "string") throw new PyCrash("TypeError", `unsupported operand type(s) for /: '${WIN ? "WindowsPath" : "PosixPath"}' and '${pyTypeName(value)}'`);
  return purePathStr(base, value);
}

/** record.clear(); record.update(before)：before 是 dict(record) 拷下的。 */
function restoreRecord(record: PyValue, before: PyDict): void {
  if (record instanceof Map) {
    record.clear();
    for (const [key, item] of before) record.set(key, item);
    return;
  }
  if (!Array.isArray(record)) throw new PyCrash("AttributeError", `'${pyTypeName(record)}' object has no attribute 'clear'`);
  record.length = 0;
  throw new PyCrash("AttributeError", "'list' object has no attribute 'update'");
}

/** record.update(landed_at=…, landed_by=…)。 */
function markLanded(record: PyValue, how: string): void {
  if (!(record instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(record)}' object has no attribute 'update'`);
  record.set("landed_at", utcNow());
  record.set("landed_by", how);
}

/**
 * 挡着本主任务落地的：别的主任务挂着的执行标记（持有进程还在），后台在跑的门禁回归（第 62 轮；sweeps=False 时不算），以及调度器记着
 * 在跑的别的 attempt（站主手动派的也算；integrate 自己也会因为它们拒绝落地）。
 */
export function landingBlockers(hub: Hub, ts: PyDict, sweeps: PyValue = true, deps: LandDeps = REAL_LAND_DEPS): PyValue[] {
  const found: PyValue[] = [];
  const marks = execMarks(hub);
  for (const path of isDir(marks) ? globPaths(marks, ["*.json"]).map((item) => purePathStr(item)).sort(comparePaths) : []) {
    let mark: PyValue;
    try {
      mark = loads(readText(path) || "{}");
    } catch (error) {
      if (!pyCaught(error, ["ValueError"])) throw error;
      mark = new Map();
    }
    const task = pyGet(mark, "task");
    if (pyEq(task, pyItem(ts, "task")) || (pyTruthy(pyGet(mark, "sweep")) && !pyTruthy(sweeps))) continue;
    // 进程已经不在：标记作废。不知道（None）照样算挡着
    if (pyTruthy(pyGet(mark, "pid")) && deps.pidAlive(Number(pyIntOf(pyItem(mark, "pid")))) === false) continue;
    found.push(or(pyGet(mark, "label"), `${pyStrValue(or(pyGet(mark, "task"), stem(path)))} 的执行端`));
  }
  let running: string[];
  try {
    running = deps.runningAttempts(new Repo(hub.repo));
  } catch (error) {
    if (!(error instanceof DispatchError) && !pyCaught(error, ["OSError"])) throw error;
    running = [];
  }
  const own = pyPlus(pyItem(ts, "contract_task"), "/") as string;
  found.push(...running.filter((item) => !item.replaceAll(BS, "/").startsWith(own)).map((item) => `attempt ${item}`));
  return found;
}

/** 结项：把终审报告写成复审记录，verdict PASS，再 integrate（本地分支，ff-only，不推送）。可以重试：attempt 已经是 PASS 就不再记一次结论。 */
export async function finalize(hub: Hub, ts: PyDict, deps: LandDeps = REAL_LAND_DEPS): Promise<[boolean, string]> {
  const runDir = pathArg(pyItem(pyItem(ts, "exec"), "run_dir"));
  if (getState(runDir) !== "PASS") {
    const problem = await recordPass(hub, ts, runDir, deps);
    if (problem) return [false, problem];
  }
  const headBefore = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const recordsBefore = landingRecords(ts).map((record) => pyDictOf(record).toDict());
  let problem = (await landOracle(hub, ts)) || (await landReworkChain(hub, ts));
  let out = "";
  if (!problem) {
    const [code, text] = await deps.runPd(hub, ["integrate", runDir], 3600);
    out = text;
    ts.set("integrated", new Map<string, PyValue>([["exit", BigInt(code)], ["tail", tail(out, 15n)], ["at", utcNow()]]));
    if (code !== 0) problem = `integrate 没有落地（退出码 ${code}）：${LF}${tail(out, 15n)}${landedMeanwhile(hub, ts, headBefore)}`;
  }
  if (problem) return [false, problem + (await undoLanding(hub, ts, headBefore, recordsBefore))];
  let detail = tail(out, 6n);
  const [sha, recordProblem] = await commitRecords(hub, ts);
  detail += LF + (recordProblem || (sha ? `合同与复审记录已提交 ${short(sha)}` : "合同与复审记录没有新改动"));
  if (!pyEq(headBefore, pyItem(ts, "base_head"))) {
    // 任务期间分支前进了（并行的主任务先落地了）：integrate 只跑了本合同的检查，别的主任务的门禁没跑。
    // 回归在放开落地锁之后跑（Engine.after_land），不挡别的主任务开始执行
    ts.set("regression", new Map<string, PyValue>([["pending", true], ["head_before", headBefore]]));
    detail += `${LF}任务期间分支前进了（${short(pyItem(ts, "base_head"))} → ${short(headBefore)}）：放开落地锁之后在新末端上跑全部门禁回归`;
  }
  return [true, detail];
}

/** 结项前要带上分支的提交的记录：门禁的基准测试，以及返工链上的每一轮。 */
export function landingRecords(ts: PyDict): PyValue[] {
  return [pyItem(ts, "oracle"), ...pyIter(or(pyGet(ts, "rework_chain"), []))];
}

/**
 * 结项没落地：撤回这次带上分支的基准测试与返工提交，记录也恢复原样（第 29 轮）。T006 的 integrate 没过，挑上去的两个提交却留在了
 * 分支上：分支上是终审打回过的 attempt-001 的代码，后落地的 T008 又压在上面，合入后的门禁回归也跟着红。返回追加到问题后面的说明。
 */
export async function undoLanding(hub: Hub, ts: PyDict, headBefore: string, recordsBefore: readonly PyDict[]): Promise<string> {
  const head = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  if (head === headBefore) return "";
  if (runGit(["merge-base", "--is-ancestor", headBefore, "HEAD"], hub.repo, "inherit").status !== 0) {
    return `${LF}分支已经不在结项开始时的末端 ${short(headBefore)} 之上，这次带上分支的提交没有撤回（站主处理）`;
  }
  try {
    git(["reset", "-q", "--keep", headBefore], hub.repo);
  } catch (error) {
    if (!(error instanceof HubError)) throw error;
    return `${LF}这次带上分支的提交没能撤回（站主处理）：${error.message}`;
  }
  const records = landingRecords(ts);
  for (let index = 0; index < Math.min(records.length, recordsBefore.length); index += 1) {
    restoreRecord(records[index] as PyValue, recordsBefore[index] as PyDict);
  }
  await hub.appendEvent("landing.undone", [["task", pyItem(ts, "task")], ["head", head], ["back_to", headBefore]]);
  return `${LF}已把这次带上分支的基准测试与返工提交撤回（${short(head)} → ${short(headBefore)}）：分支上不留半截的结项`;
}

/**
 * integrate 的检查在候选上过了、在末端上没过：多半是任务期间先落地的提交与本候选合不到一起（第 29 轮，T007 的 TextViewer 带
 * aria-pressed，T006 门禁查陈列页上任何 aria-pressed）。列出这些提交，站主好找。
 */
export function landedMeanwhile(hub: Hub, ts: PyDict, headBefore: string): string {
  if (!pyTruthy(pyGet(pyItem(ts, "exec"), "check_ok"))) return "";
  const range = `${pyStrValue(pyItem(ts, "base_head"))}..${headBefore}`;
  const log = pySplitlines(pyStrip(git(["log", "--no-merges", "--format=%h %s", "-n", "11", range], hub.repo, false)));
  if (!log.length) return "";
  const more = log.length > 10 ? `${LF}  …` : "";
  return `${LF}本候选在 attempt 的基线上 check 通过过；任务期间分支上先落地了这些提交，没过的检查多半是它们与本候选合不到一起`
    + `（门禁断言写得太宽，或两边真的冲突）：${LF}${log.slice(0, 10).map((line) => `  ${line}`).join(LF)}${more}`;
}

/**
 * 结项时把本主任务的合同（各版本）与复审记录提交到当前分支（第 20 轮）：并行时站主手动提交会撞上别的主任务正在跑的执行端（调度器把
 * 主工作区 HEAD 的变化列进复审的注意事项），放在持落地锁的结项里做。只提交这两处路径（git commit --only），站主暂存区里别的东西
 * 不会被带上。返回（提交, 问题）。
 */
export async function commitRecords(hub: Hub, ts: PyDict): Promise<[string | null, string | null]> {
  const plans = purePathStr(hub.repo, ".agent", "plans");
  // 合同族名照 SLUG_RE 只有小写字母、数字与连字符，模式里唯一的通配符是 .v* 的 *：globPaths 只认 *，对这个范围与 pathlib 的 glob 一样
  const paths = globPaths(plans, [`${pyStrValue(pyItem(ts, "contract_task"))}.v*`]).map((path) => purePathStr(path))
    .filter((path) => suffix(path) === ".md" || suffix(path) === ".json")
    .map((path) => `.agent/plans/${purePathName(path)}`)
    .sort(cmpCodePoints);
  const reviews = joinPath(purePathStr(hub.repo, ".agent", "reviews"), pyItem(ts, "contract_task"));
  if (isDir(reviews)) paths.push(relativePosix(reviews, hub.repo));
  if (!paths.length) return [null, null];
  if (!pyStrip(git(["status", "--porcelain", "--", ...paths], hub.repo))) return [null, null];
  try {
    git(["add", "--", ...paths], hub.repo);
    const message = `agent: ${pyStrValue(pyItem(ts, "task"))}（${pyStrValue(pyItem(ts, "title"))}）的合同与 hub 的复审记录`;
    git(["commit", "-q", "--only", "-m", message, "--", ...paths], hub.repo);
  } catch (error) {
    if (!(error instanceof HubError)) throw error;
    return [null, `合同与复审记录没有提交成（站主手动提交）：${error.message}`];
  }
  const sha = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  await hub.appendEvent("records.committed", [["task", pyItem(ts, "task")], ["sha", sha], ["paths", [...paths]]]);
  return [sha, null];
}

/** path.relative_to(root).as_posix()：path 是在 root 上拼出来的。 */
function relativePosix(path: string, root: string): string {
  return codePoints(path).slice(codePoints(purePathStr(root)).length + 1).join("").replaceAll(BS, "/");
}

/**
 * 提交已经在当前分支（或 where 这个 worktree 的 HEAD）上：是祖先（ff 过），或者分支上有它挑过来的提交（cherry-pick -x 的标记）。
 * 第 29 轮：以前基准测试按文件内容判断“挑过了”，站主之后在分支上退役或收窄了其中的断言，重试结项时内容对不上，就会再挑一次而冲突；
 * 返工链只看 landed_at，分支被撤回之后记录就不准了。
 */
export function onBranch(hub: Hub, sha: PyValue, where: string | null = null): boolean {
  const cwd = where || hub.repo;
  if (runGit(["merge-base", "--is-ancestor", argText(sha), "HEAD"], cwd, "inherit").status === 0) return true;
  const grep = `--grep=(cherry picked from commit ${pyStrValue(sha)})`;
  return Boolean(pyStrip(git(["log", "--format=%H", "-n", "1", "--fixed-strings", grep, "HEAD"], cwd, false)));
}

/**
 * 返工链上要先带上分支的那几轮：attempt 的基线里有的（基线就是它，或是它的后代）。第 60 轮补：门禁热修补之后执行端从新的基准测试
 * 从头开工，返工链还记着热修补之前的两轮；照旧挑上去，候选补丁新增的文件就撞上链上的同名文件。判断不了（提交不存在等）的照旧算进去，
 * 由挑的那一步报错。
 */
export function landingChain(hub: Hub, ts: PyDict, runDir: string | null): PyValue[] {
  const chain = or(pyGet(ts, "rework_chain"), []);
  if (runDir === null) return [...pyIter(chain)];
  const base = attemptBase(ts, runDir);
  return pyIter(chain).filter((link) => runGit(["merge-base", "--is-ancestor", argText(pyItem(link, "commit")), argText(base)], hub.repo, "ignore").status !== 1);
}

/** 能 ff 就 ff，不能就挑到末端（cherry-pick -x）；挑不上先 --abort，交回 git 的输出（合在一起解码）。 */
function bringOnto(hub: Hub, sha: string): ["ff" | "cherry-pick", null] | [null, string] {
  try {
    git(["merge", "--ff-only", sha], hub.repo);
    return ["ff", null];
  } catch (error) {
    if (!(error instanceof HubError)) throw error;
  }
  const [code, out] = runMerged(["git", "cherry-pick", "-x", sha], hub.repo);
  if (code === 0) return ["cherry-pick", null];
  runGit(["cherry-pick", "--abort"], hub.repo, "ignore");
  return [null, pyDecodeUtf8Replace(out)];
}

/**
 * 把门禁的基准测试带上当前分支；返回问题（成功或不需要时为 None）。候选以基准测试提交为基线：它不在当前分支上时，integrate 只挑
 * “基线→候选”的改动，当前末端上没有基准测试，合同检查跑不通（T001 第一次结项就卡在这里）。它是一审审过、锁定的验收测试，先带上：
 * 能 ff 就 ff；任务进行期间分支前进了，就把它挑到末端（它只新增门禁测试文件），这样任务期间也能往分支上提交。
 */
export async function landOracle(hub: Hub, ts: PyDict): Promise<string | null> {
  const oracle = pyGet(pyItem(ts, "oracle"), "sha");
  if (!pyTruthy(oracle) || onBranch(hub, oracle)) return null;
  const files = or(pyGet(pyItem(ts, "oracle"), "files"), []);
  const same = (file: PyValue): boolean => pyStrip(git(["rev-parse", `HEAD:${pyStrValue(file)}`], hub.repo, false))
    === pyStrip(git(["rev-parse", `${pyStrValue(oracle)}:${pyStrValue(file)}`], hub.repo, false));
  if (pyTruthy(files) && pyIter(files).every(same)) return null; // 末端上已经有同样内容的基准测试（重试时挑入过了）
  const [how, out] = bringOnto(hub, oracle as string);
  if (how === null) return `基准测试提交 ${short(oracle)} 既不能 ff，也不能干净地挑到当前分支：${tail(out, 8n)}`;
  markLanded(pyItem(ts, "oracle"), how);
  await hub.appendEvent("oracle.landed", [["task", pyItem(ts, "task")], ["sha", oracle], ["how", how]]);
  return null;
}

/**
 * 返工链上的提交按顺序带上当前分支（第 10 轮）：每一轮的返工提交以上一轮的基线为父提交，integrate 只挑最后一轮“基线→候选”的改动，
 * 前几轮的改动要先在末端上。能 ff 就 ff，不能就挑到末端；重试时跳过已落地的。只带 attempt 的基线里有的那几轮（landing_chain，第 60 轮补）。
 */
export async function landReworkChain(hub: Hub, ts: PyDict): Promise<string | null> {
  const runDir = pyGet(pyItem(ts, "exec"), "run_dir");
  for (const link of landingChain(hub, ts, pyTruthy(runDir) ? pathArg(runDir) : null)) {
    const sha = pyItem(link, "commit");
    let how: string;
    if (onBranch(hub, sha)) {
      if (pyTruthy(pyGet(link, "landed_at"))) continue;
      how = "already";
    } else if (emptyCommit(hub, sha as string)) {
      if (pyTruthy(pyGet(link, "landed_at"))) continue;
      how = "empty"; // 什么也没改，没东西可挑（第 60 轮）
    } else {
      const [made, out] = bringOnto(hub, sha as string);
      if (made === null) {
        return `返工提交 ${short(sha)}（${pyStrValue(pyGet(link, "from"))} 的候选）既不能 ff，也不能干净地挑到当前分支：${tail(out, 8n)}`;
      }
      how = made;
    }
    markLanded(link, how);
    await hub.appendEvent("rework.landed", [["task", pyItem(ts, "task")], ["sha", sha], ["how", how]]);
  }
  return null;
}

/** 把终审报告写成复审记录，记 verdict PASS；返回问题（成功时为 None）。 */
export async function recordPass(hub: Hub, ts: PyDict, runDir: string, deps: LandDeps = REAL_LAND_DEPS): Promise<string | null> {
  const reviewPath = writeReview(hub, ts, runDir, "PASS");
  const [code, out] = await deps.runPd(hub, ["verdict", runDir, "--verdict", "PASS", "--review", reviewPath]);
  if (code !== 0) return `verdict PASS 被门禁拒绝：${LF}${tail(out, 20n)}`;
  return null;
}

/** 结项后清掉主任务的阶段 worktree（第 12 轮：T001–T003 结项后留下 10 个）。证据此前已经存进信箱；删不掉的如实返回，不影响结项。 */
export async function removeWorkspaces(hub: Hub, ts: PyDict): Promise<string[]> {
  const problems: string[] = [];
  const workspaces = pyItem(ts, "workspaces");
  if (!(workspaces instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(workspaces)}' object has no attribute 'items'`);
  for (const [kind, record] of [...workspaces].sort(([a], [b]) => cmpCodePoints(a as string, b as string))) {
    const path = pyGet(record, "path");
    if (!pyTruthy(path) || pyTruthy(pyGet(record, "removed_at"))) continue;
    if (pyExists(pathArg(path))) {
      const done = runGit(["worktree", "remove", "--force", path as string], hub.repo, "pipe");
      if (done.status !== 0) {
        problems.push(`${path as string}：${codePoints(pyStrip(pyDecodeUtf8Replace(done.stderr))).slice(0, 200).join("")}`);
        continue;
      }
    }
    (record as PyDict).set("removed_at", utcNow()); // record.get 已经过了：是 dict
    await hub.appendEvent("workspace.removed", [["task", pyItem(ts, "task")], ["kind", kind], ["path", path]]);
  }
  return problems;
}

/**
 * 结项后收尾同一合同族的 attempt（第 12 轮）：没有结论的记成 ABANDONED，再用 cleanup 删掉 worktree。hub 换下一个 attempt 时（内核检查
 * 没过、上游返工出了新版本合同），上一个停在 NEEDS_REVIEW，worktree 一直留着（T001、T002 的 attempt-001）。cleanup 发现会丢内容就拒绝，原样报告。
 */
export async function retireAttempts(hub: Hub, ts: PyDict, reason: string, deps: LandDeps = REAL_LAND_DEPS): Promise<string[]> {
  const problems: string[] = [];
  const runs = joinPath(purePathStr(hub.repo, ".agent", "runs"), pyItem(ts, "contract_task"));
  for (const runDir of isDir(runs) ? globPaths(runs, ["attempt-*"]).map((item) => purePathStr(item)).sort(comparePaths) : []) {
    const name = purePathName(runDir);
    const state = getState(runDir);
    // 第 47 轮：T012 的 attempt-001 预检失败、从没开跑（没有 run-started.json），一直停在 PREPARED；主任务结项之后它不会再跑，照没有结论的收尾
    const neverRan = state === "PREPARED" && !pyExists(purePathStr(runDir, "run-started.json"));
    if (ATTEMPT_IN_FLIGHT.includes(state) && !neverRan) {
      problems.push(`${name} 还处在 ${state}，没有动`);
      continue;
    }
    if (state === "NEEDS_REVIEW" || neverRan) {
      const [code, out] = await deps.runPd(hub, ["mark", runDir, "ABANDONED", "--reason", reason]);
      if (code !== 0) {
        problems.push(`${name} 没能记成 ABANDONED：${tail(out, 3n)}`);
        continue;
      }
    }
    const worktree = pyGet(loads(readText(purePathStr(runDir, "meta.json")) || "{}"), "worktree");
    if (pyTruthy(worktree) && pyExists(pathArg(worktree))) {
      // 没开跑的没有候选记录，cleanup 怕丢改动拒绝；worktree 里确实没有改动才强制删
      const clean = neverRan && !workspaceStatus(purePathStr(worktree as string)).length;
      const [code, out] = await deps.runPd(hub, ["cleanup", runDir, ...(clean ? ["--force"] : [])]);
      if (code !== 0) problems.push(`${name} 的 worktree 没删掉：${tail(out, 3n)}`);
    }
  }
  return problems;
}

/** 主任务结项之后的收尾：阶段 worktree 与 attempt 的 worktree，没有结论的 attempt 记成 ABANDONED。 */
export async function tidyFinished(hub: Hub, ts: PyDict, reason: string, deps: LandDeps = REAL_LAND_DEPS): Promise<string[]> {
  return [...(await removeWorkspaces(hub, ts)), ...(await retireAttempts(hub, ts, reason, deps))];
}
