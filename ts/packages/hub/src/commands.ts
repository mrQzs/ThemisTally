// 站主命令（迁移第 ⑤j1 片）：kit_hub.py 的 find_repo、cmd_init、uncommitted_references、cmd_task_new、close、rebase、after、unstick、budget、
// cleanup 与 raise_budget，cmd_send、cmd_exec_recheck、cmd_take、cmd_status、turn_metrics、recorded_sum、exec_metrics、cmd_metrics，以及共用的
// pause_marker、task_quiet、supervisor_alive、lock_alive、configured_parallel（⑤j2 的 cmd_run、supervise 也用）。
// 参数是启动器交来的 pyargs（键同 argparse 的 Namespace，⑤j 设计稿第 2 节）；输出走 CommandOut（缺省 PyOut），报错照 Python 抛 HubError，
// 由入口写“ERROR: …”。deps 只给契约用：用例换掉的内层函数（run_pd、tidy_finished、pid_alive 之类）照记录注入；生产调用方不传。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { utcNow } from "@themis/base/clock";
import { UnicodeDecodeError, readText, writeTextAtomic } from "@themis/base/fsutil";
import { jsonlLines } from "@themis/base/jsonl";
import { PyCrash, PyOut, pyFixed, pyFloatOf, pyGet, pyIntOf, pyItem, pyIter, pyPercentD, pyRepr, pyRound, pyStrValue, pySum, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyKey, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { PyUnicodeDecodeError, pyReadText } from "@themis/base/pyio";
import { purePathRelativePosix, purePathStr } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyRstrip, pySplitlines, pyStrip } from "@themis/base/pyre";
import { compilePy } from "@themis/base/pyregex";
import { pyEq } from "@themis/base/pyvalue";
import { getState } from "@themis/dispatcher/status";
import { Repo } from "@themis/dispatcher/repo";
import { bumpContractVersion } from "./accept.ts";
import {
  COORDINATOR, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, FIELDS, KERNEL, MAX_OWNER_CHARS, MIN_ATTEMPTS_LEFT, OWNER, ROSTER, STAGE_ORDER, STAGE_WORKER,
} from "./constants.ts";
import { answersQuestion, contractPaths } from "./contract.ts";
import { Engine, type EngineDeps, REAL_ENGINE_DEPS, releaseDependents } from "./engine.ts";
import { HubError } from "./errors.ts";
import { ATTEMPT_IN_FLIGHT, attemptsLeft } from "./exec.ts";
import { git } from "./kernel.ts";
import { landingBlockers } from "./land.ts";
import { letterErrors, stageOf } from "./letters.ts";
import { DirLock, Hub } from "./mailbox.ts";
import { budgetUsage } from "./prompt.ts";
import { runnerLock } from "./requeue.ts";
import { execMarks } from "./runexec.ts";
import { moveBase, newTaskState, stageBusy, stageStatusTable } from "./taskstate.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const TICK = String.fromCharCode(96);
const NUL = String.fromCharCode(0);
const SEP = process.platform === "win32" ? BS : "/";

const MAIN_TASK_RE = compilePy(`^T${BS}d{3,6}$`);
const SLUG_RE = compilePy("^[a-z0-9][a-z0-9-]{0,40}$");
const BRIEF_PATH_RE = compilePy(`${TICK}([^${TICK}${BS}n]+)${TICK}`);
const SHA_RE = new RegExp("^[0-9a-f]{40}$");
/** 站主的命令等主任务的 runner 让出锁的上限（有 supervisor 时；没有就是 1 秒）。 */
export const OWNER_WAIT_SECONDS = 3600;

/** 命令的输出：print 照 Python 的 print（PyOut 在 Windows 上写 CRLF），契约换成截下来的那一份。 */
export interface CommandOut {
  print(text?: string): void;
  printErr(text?: string): void;
}

/** 启动器交来的参数：键同 argparse 的 Namespace，值是 pyjson 的值。 */
export type CommandArgs = Readonly<Record<string, PyValue>>;

const text = (args: CommandArgs, key: string): string => pyStrValue(args[key] ?? null);
const optional = (args: CommandArgs, key: string): string | null => (args[key] === null || args[key] === undefined ? null : pyStrValue(args[key] as PyValue));
const head = (value: string, size: number): string => codePoints(value).slice(0, size).join("");

/** 有一个就交回 null 的 dict.get：值不是 dict 时照 Python 抛 AttributeError。 */
function getOf(value: PyValue, key: string): PyValue {
  if (!(value instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'get'`);
  return pyGet(value, key);
}

/** Python 的 except ValueError 接得住的：json.loads 的 JSONDecodeError，与 read_text 读到不是 UTF-8 的文件时的 UnicodeDecodeError。 */
const isValueError = (error: unknown): boolean => error instanceof PyJsonError || error instanceof UnicodeDecodeError;

/** subprocess.run(argv, cwd=…, stdin=…) 的退出码：stdout、stderr 照 Python 继承，不截。起不来照 Python 抛 FileNotFoundError。 */
function runCode(argv: readonly string[], cwd: string, stdin: "inherit" | "ignore"): number {
  const done = spawnSync(argv[0] as string, argv.slice(1), { cwd, stdio: [stdin, "inherit", "inherit"], windowsHide: true });
  if (done.error) throw new PyCrash("FileNotFoundError", `[WinError 2] 系统找不到指定的文件。`);
  return done.status ?? 1;
}

export function findRepo(arg: string | null): string {
  return Repo.discover(arg).root;
}

export function pauseMarker(hub: Hub, task: string): string {
  return purePathStr(hub.root, ".pause", task);
}

/** DirLock 有没有活着的持有者。 */
export function lockAlive(path: string, deps: EngineDeps = REAL_ENGINE_DEPS): boolean {
  if (!isDirectory(path)) return false;
  let owner: PyValue;
  try {
    owner = loads(readText(purePathStr(path, "owner.json")) || "{}");
  } catch (error) {
    if (isValueError(error)) return true; // 刚建、owner.json 还没写完（读不出、不是 UTF-8 也一样，Python 的 except ValueError）
    throw error;
  }
  const pid = getOf(owner, "pid");
  return !(pyTruthy(pid) && deps.pidAlive(Number(pyIntOf(pid))) === false);
}

export function supervisorAlive(hub: Hub, deps: EngineDeps = REAL_ENGINE_DEPS): boolean {
  const path = runnerLock(hub, null);
  return lockAlive(path, deps) && pyStrip(readText(purePathStr(path, "mode"))) === "supervisor";
}

/** 并行的主任务数：命令行的 --parallel 优先，否则读信箱里的 runner.json，都没有就是 1。 */
export function configuredParallel(hub: Hub, args: CommandArgs): number {
  let value: PyValue = args["parallel"] ?? null;
  if (value === null) {
    try {
      value = getOf(loads(readText(purePathStr(hub.root, "runner.json")) || "{}"), "parallel");
    } catch (error) {
      if (!isValueError(error)) throw error; // runner.json 不是 UTF-8（PowerShell 5.1 缺省写 UTF-16）也当成没写
      value = null;
    }
  }
  try {
    const parsed = pyIntOf(pyTruthy(value) ? value : 1n);
    return Number(parsed > 1n ? parsed : 1n);
  } catch (error) {
    if (error instanceof PyCrash && (error.kind === "TypeError" || error.kind === "ValueError")) return 1;
    throw error;
  }
}

/**
 * 站主的命令要改某个主任务的状态：这个主任务此刻不能有 runner 在办信（kit_hub.task_quiet）。先挂暂停标记，拿它的 runner 锁；没有 supervisor
 * 时再拿总锁。命令办完撤掉标记。
 */
export async function withTaskQuiet<T>(hub: Hub, task: string, out: CommandOut, deps: EngineDeps, body: () => Promise<T>, wait: number | null = null): Promise<T> {
  const seconds = wait ?? (supervisorAlive(hub, deps) ? OWNER_WAIT_SECONDS : 1.0);
  const marker = pauseMarker(hub, task);
  mkdirSync(dirname(marker), { recursive: true });
  writeTextAtomic(marker, `${dumps(new Map<string, PyValue>([["pid", BigInt(process.pid)], ["at", utcNow()]]))}${LF}`);
  try {
    if (lockAlive(runnerLock(hub, task), deps)) out.print(`等 ${task} 的 runner 办完手上这一步（最长 ${pyPercentD(seconds)} 秒）……`);
    const lock = new DirLock(runnerLock(hub, task), seconds).acquire();
    try {
      if (supervisorAlive(hub, deps)) return await body();
      const all = new DirLock(runnerLock(hub, null), 1.0).acquire();
      try {
        return await body();
      } finally {
        all.release();
      }
    } finally {
      lock.release();
    }
  } finally {
    try {
      unlinkSync(marker);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }
}

/** 拿着信箱的总状态锁（hub.root/.lock）办 body。 */
async function withStateLock<T>(hub: Hub, body: () => Promise<T>): Promise<T> {
  const lock = new DirLock(purePathStr(hub.root, ".lock")).acquire();
  try {
    return await body();
  } finally {
    lock.release();
  }
}

export function cmdInit(args: CommandArgs, out: CommandOut = new PyOut()): number {
  const hub = new Hub(findRepo(optional(args, "repo")));
  hub.ensure();
  const ignored = runCode(["git", "check-ignore", "-q", [".agent", "mailbox", "x"].join(SEP)], hub.repo, "inherit") === 0;
  out.print(`信箱：${hub.root}${ignored ? "" : `${LF}WARN  .agent/mailbox/ 没有被 .gitignore 忽略`}`);
  return EXIT_OK;
}

/** 任务书里用反引号写的仓库路径，工作区里有、任务基线里没有或有未提交改动的。被 Git 忽略的不算。 */
export function uncommittedReferences(repo: string, brief: string): string[] {
  const problems: string[] = [];
  const found = [...new Set(BRIEF_PATH_RE.finditer(brief).map((match) => match.group.slice(1, -1)))].sort(cmpCodePoints);
  for (const raw of found) {
    let path = pyStrip(raw);
    while (path.endsWith("/")) path = path.slice(0, -1); // str.rstrip("/")
    if (!path.includes("/") || path.includes("://") || path.startsWith("/") || path.startsWith("-") || path.startsWith("~")) continue;
    if (path.includes(NUL) || !existsSync(purePathStr(repo, path))) continue;
    if (runCode(["git", "check-ignore", "-q", "--", path], repo, "ignore") === 0) continue;
    if (!pyStrip(git(["ls-tree", "HEAD", "--", path], repo, false))) problems.push(`${path} 没有提交`);
    else if (pyStrip(git(["status", "--porcelain", "--", path], repo, false))) problems.push(`${path} 有未提交的改动`);
  }
  return problems;
}

const fieldsOf = (summary: string): Map<string, PyValue> =>
  new Map<string, PyValue>([["摘要", summary], ["提交", "无"], ["验证", "无"], ["偏离", "无"], ["需协调人决定", "无"]]);
const meta = (sender: string, to: string, taskId: string, kind: string, replyTo = "none"): Map<string, string> =>
  new Map([["from", sender], ["to", to], ["task-id", taskId], ["in-reply-to", replyTo], ["type", kind]]);

export async function cmdTaskNew(args: CommandArgs, out: CommandOut = new PyOut()): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  hub.ensure();
  const task = text(args, "task");
  if (!MAIN_TASK_RE.match(task)) throw new HubError("主任务号要像 T001", EXIT_USAGE);
  if (!SLUG_RE.match(text(args, "slug"))) throw new HubError("--slug 只能是小写字母、数字与连字符", EXIT_USAGE);
  const brief = pyReadText(text(args, "brief"));
  const base = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const unseen = uncommittedReferences(hub.repo, brief);
  if (unseen.length > 0) {
    throw new HubError(`任务书引用的路径工人看不到（工人在任务基线 ${head(base, 10)} 的 worktree 里干活）：${unseen.join("；")}。先提交再登记`, EXIT_USAGE);
  }
  const [state, msg] = await withStateLock(hub, async () => {
    const loaded = hub.loadState();
    const tasks = loaded.tasks();
    if (tasks.has(task)) throw new HubError(`主任务 ${task} 已存在`, EXIT_USAGE);
    const after = (optional(args, "after") || "").split(",").map((item) => pyStrip(item)).filter(Boolean);
    const unknown = after.filter((item) => !tasks.has(item));
    if (unknown.length > 0) throw new HubError(`--after 里的主任务没有登记过：${unknown.join("、")}`, EXIT_USAGE);
    const ts = newTaskState(task, text(args, "slug"), text(args, "title"), base, !pyTruthy(args["no_jev"] ?? false), utcNow());
    tasks.set(task, ts);
    const waiting = after.filter((item) => !pyEq(getOf(tasks.get(item) as PyValue, "status"), "done"));
    if (waiting.length > 0) ts.set("after", waiting);
    writeTextAtomic(purePathStr(hub.taskDir(task), "brief.md"), `${pyRstrip(brief)}${LF}`);
    await hub.saveState(loaded);
    await hub.appendEvent("task.created", [["task", task], ["slug", text(args, "slug")], ["base_head", base], ["after", pyGet(ts, "after")]]);
    const fields = fieldsOf(text(args, "title"));
    fields.set("证据", `.agent/mailbox/tasks/${task}/brief.md`);
    return [loaded, await hub.deliver(meta(OWNER, COORDINATOR, task, "任务"), fields)] as const;
  });
  const waiting = pyGet(state.tasks().get(task) as PyDict, "after");
  const note = pyTruthy(waiting) ? `；合同端等 ${pyIter(waiting).map(pyStrValue).join("、")} 结项` : "";
  out.print(`已登记 ${task}（基线 ${head(base, 10)}${note}），任务信 ${msg} 已投给 ${COORDINATOR}`);
  return EXIT_OK;
}

/** 站主接手结项：工作已经由站主落在当前分支上。 */
export async function cmdTaskClose(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const note = pyStrip(pyReadText(text(args, "file")));
  if (!note) throw new HubError("--file 要写明站主怎样接手、怎样验收", EXIT_USAGE);
  const ref = text(args, "ref");
  const sha = pyStrip(git(["rev-parse", "--verify", `${ref}^{commit}`], hub.repo, false));
  if (!SHA_RE.test(sha) || runCode(["git", "merge-base", "--is-ancestor", sha, "HEAD"], hub.repo, "ignore") !== 0) {
    throw new HubError(`--ref ${ref} 不是当前分支上的提交：先把接手的工作落到分支上再结项`, EXIT_USAGE);
  }
  const leftover = await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    if (pyEq(getOf(ts, "status"), "done")) throw new HubError(`主任务 ${task} 已经结项`, EXIT_USAGE);
    const path = purePathStr(hub.taskDir(task), "closed-by-owner.md");
    writeTextAtomic(path, `${note}${LF}`);
    ts.set("status", "done");
    ts.set("closed_by_owner", new Map<string, PyValue>([["ref", sha], ["note", purePathRelativePosix(path, hub.repo) as string], ["at", utcNow()]]));
    await hub.saveState(state);
    await hub.appendEvent("task.closed_by_owner", [["task", task], ["ref", sha]]);
    const left = await deps.tidyFinished(hub, ts, `${task} 已由站主接手结项（${head(sha, 12)}）：这一轮没有复审结论`, deps);
    await releaseDependents(hub, state, task); // 站主接手结项也算结项：依赖它的主任务照样放行
    await hub.saveState(state);
    return left;
  }));
  out.print(`${task} 已由站主接手结项（${head(sha, 12)}）`);
  for (const item of leftover) out.print(`结项收尾没做完：${item}`);
  return EXIT_OK;
}

/** 合同端开工之前把主任务的基线挪到当前末端。 */
export async function cmdTaskRebase(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const reason = pyStrip(optional(args, "reason") || "");
  if (!reason) throw new HubError("--reason 要写明为什么挪基线（协调人会把它写进合同端的 brief）", EXIT_USAGE);
  const now = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const previous = await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    if (!pyEq(getOf(ts, "status"), "active")) throw new HubError(`主任务 ${task} 不在进行中`, EXIT_USAGE);
    if (contractStarted(ts)) {
      throw new HubError(`${task} 的合同端已经开工：合同的 base_sha 与基准测试都钉在旧基线上，不能再挪。要换基线就让合同端出新版本`, EXIT_BLOCKED);
    }
    if (pyEq(pyItem(ts, "base_head"), now)) {
      out.print(`${task} 的基线已经是当前末端 ${head(now, 10)}`);
      return null;
    }
    const before = pyStrValue(moveBase(ts, now));
    listOf(ts, "rebases").push(new Map<string, PyValue>([["at", utcNow()], ["head", now], ["previous", before], ["reason", reason]]));
    await hub.saveState(state);
    await hub.appendEvent("task.rebased", [["task", task], ["head", now], ["previous", before]]);
    await hub.deliver(meta(KERNEL, COORDINATOR, task, "核验"), new Map<string, PyValue>([
      ["摘要", `站主把 ${task} 的基线从 ${head(before, 10)} 挪到当前末端 ${head(now, 10)}`], ["提交", now], ["验证", "站主的 task rebase"], ["偏离", reason],
      ["需协调人决定", "合同端在新基线上写合同；brief 里写明挪基线的原因，并提醒合同端在新基线上核对规划引用的路径与接口"],
      ["证据", `.agent/mailbox/tasks/${task}-1-plan/report.md`],
    ]));
    return before;
  }));
  if (previous !== null) out.print(`${task} 的基线：${head(previous, 10)} → ${head(now, 10)}`);
  return EXIT_OK;
}

/** 合同端开工之前给主任务补依赖（规划之后才发现的）。 */
export async function cmdTaskAfter(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const reason = pyStrip(optional(args, "reason") || "");
  if (!reason) throw new HubError("--reason 要写明为什么要等（协调人会把它写进合同端的 brief）", EXIT_USAGE);
  const on = text(args, "on").split(",").map((item) => pyStrip(item)).filter(Boolean);
  const after = await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const tasks = state.tasks();
    const ts = pyGet(tasks, task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    if (!pyEq(getOf(ts, "status"), "active")) throw new HubError(`主任务 ${task} 不在进行中`, EXIT_USAGE);
    const unknown = on.filter((item) => !tasks.has(item) || item === task);
    if (on.length === 0 || unknown.length > 0) throw new HubError(`--on 要写别的已登记主任务：${unknown.join("、") || "没写"}`, EXIT_USAGE);
    const cyclic = on.filter((item) => pyIter(orList(getOf(tasks.get(item) as PyValue, "after"))).some((name) => pyEq(name, task)));
    if (cyclic.length > 0) throw new HubError(`${cyclic.join("、")} 已经在等 ${task}：互相等就谁也开不了合同端`, EXIT_USAGE);
    if (contractStarted(ts)) {
      throw new HubError(`${task} 的合同端已经开工：合同钉在当前基线上。要等别的片，就让合同端出新版本，或者先停下这一片`, EXIT_BLOCKED);
    }
    const waiting = on.filter((item) => !pyEq(getOf(tasks.get(item) as PyValue, "status"), "done"));
    if (waiting.length === 0) {
      out.print(`${on.join("、")} 都已结项，不用等；要换到它们落地后的基线，用 task rebase`);
      return null;
    }
    const merged = [...new Set([...pyIter(orList(getOf(ts, "after"))).map(pyStrValue), ...waiting])].sort(cmpCodePoints);
    ts.set("after", merged);
    ts.delete("after_released"); // 以前的依赖放行过了：新加的这几个还没有
    listOf(ts, "after_added").push(new Map<string, PyValue>([["at", utcNow()], ["on", waiting], ["reason", reason]]));
    await hub.saveState(state);
    await hub.appendEvent("task.after_added", [["task", task], ["on", waiting], ["after", merged]]);
    await hub.deliver(meta(KERNEL, COORDINATOR, task, "核验"), new Map<string, PyValue>([
      ["摘要", `站主让 ${task} 等 ${waiting.join("、")} 结项再开工合同端`], ["提交", "无"], ["验证", "站主的 task after"], ["偏离", reason],
      ["需协调人决定", `规划照常；合同端先不开工。${waiting.join("、")} 结项后内核把基线挪到新末端、写信通知你，再开工合同端，brief 里写明为什么等`],
      ["证据", `.agent/mailbox/tasks/${task}-1-plan/report.md`],
    ]));
    return merged;
  }));
  if (after !== null) out.print(`${task} 的合同端等 ${after.join("、")} 结项`);
  return EXIT_OK;
}

/** 把卡在“已经开工”、其实没人在办的阶段标成 failed。 */
export async function cmdTaskUnstick(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const suffix = text(args, "stage");
  const reason = pyStrip(optional(args, "reason") || "");
  if (!reason) throw new HubError("--reason 要写明阶段为什么卡住（协调人会照它重新开工）", EXIT_USAGE);
  if (!STAGE_ORDER.includes(suffix)) throw new HubError(`阶段写后缀，例如 5-exec：${STAGE_ORDER.join("、")}`, EXIT_USAGE);
  await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    const stage = pyItem(pyItem(ts, "stages"), suffix) as PyDict;
    if (!stageBusy(stage)) throw new HubError(`${task}-${suffix} 是 ${pyStrValue(pyItem(stage, "status"))}，没有卡在“已经开工”`, EXIT_USAGE);
    if (suffix === "5-exec") {
      const pid = markPid(hub, task);
      const runs = purePathStr(hub.repo, ".agent", "runs", pyStrValue(pyItem(ts, "contract_task")));
      const flying = isDirectory(runs)
        ? readdirSync(runs).filter((name) => ATTEMPT_DIR.test(name) && ATTEMPT_IN_FLIGHT.includes(getState(purePathStr(runs, name))))
        : [];
      if ((pyTruthy(pid) && deps.pidAlive(Number(pyIntOf(pid))) !== false) || flying.length > 0) {
        throw new HubError(`${task} 的执行端还在跑（${flying.join("、") || "执行标记"}）：等它跑完`, EXIT_BLOCKED);
      }
    }
    stage.set("status", "failed").set("note", `站主标成 failed：${reason}`);
    await hub.saveState(state);
    await hub.appendEvent("stage.unstuck", [["task", task], ["suffix", suffix], ["reason", reason]]);
    await hub.deliver(meta(KERNEL, COORDINATOR, task, "核验"), new Map<string, PyValue>([
      ["摘要", `站主把卡住的 ${task}-${suffix} 标成了 failed：它不在办，可以重新开工或返工`], ["提交", "无"], ["验证", "站主的 task unstick"],
      ["偏离", reason], ["需协调人决定", `照原来的安排给 ${STAGE_WORKER[suffix] as string} 重发开工（或返工），brief 照抄上一封`],
      ["证据", ".agent/mailbox/ledger/events.jsonl（stage.unstuck）"],
    ]));
  }));
  out.print(`${task}-${suffix} 已标成 failed`);
  return EXIT_OK;
}

const ATTEMPT_DIR = new RegExp("^attempt-[0-9][0-9][0-9]$");

/** 执行标记（ledger/exec-active/<task>.json）里的 pid；标记不在时 null。 */
function markPid(hub: Hub, task: string): PyValue {
  const mark = purePathStr(execMarks(hub), `${task}.json`);
  return isFile(mark) ? getOf(loads(readText(mark) || "{}"), "pid") : null;
}

/** 合同出下一版，max_attempts_total 改成 attempts；累计墙钟不够再跑 MIN_ATTEMPTS_LEFT 次时一并补足。交回（改动，问题）。 */
export async function raiseBudget(hub: Hub, ts: PyDict, attempts: bigint, deps: EngineDeps = REAL_ENGINE_DEPS): Promise<[PyDict, string[]]> {
  const budget = orMap(getOf(loads(readText(contractPaths(hub, ts)[1]) || "{}"), "budget"));
  const used = budgetUsage(hub, ts);
  const need = BigInt(used.attempts_started + MIN_ATTEMPTS_LEFT);
  const total = pyGet(budget, "max_attempts_total");
  if (attempts < need || attempts <= pyIntOf(pyTruthy(total) ? total : 0n) || attempts > 20n) {
    return [new Map(), [`--attempts 要大于现在的 ${pyStrValue(total)}、不超过 20，而且至少 ${need}（已用掉 ${used.attempts_started} 次，返工之后还要留一次）`]];
  }
  const perAttempt = pyGet(budget, "max_wall_seconds_per_attempt");
  const wallTotal = pyGet(budget, "max_wall_seconds_total");
  const wanted = pyIntOf(used.wall_seconds_used + MIN_ATTEMPTS_LEFT * pyFloatOf(pyTruthy(perAttempt) ? perAttempt : 0n));
  const current = pyIntOf(pyTruthy(wallTotal) ? wallTotal : 0n);
  const wall = current > wanted ? current : wanted;
  if (pyTruthy(getOf(pyItem(ts, "contract"), "dispatched"))) {
    const problems = await bumpContractVersion(hub, ts);
    if (problems.length > 0) return [new Map(), problems];
  }
  const [md] = contractPaths(hub, ts);
  let contract = readText(md);
  for (const [key, value] of [["max_attempts_total", attempts], ["max_wall_seconds_total", wall]] as const) {
    const [replaced, count] = subn(compilePy(`(?m)^- ${key}:${BS}s*${BS}d+${BS}s*$`), `- ${key}: ${value}`, contract);
    if (count !== 1) return [new Map(), [`合同 Budget 里找不到唯一的“- ${key}:”行`]];
    contract = replaced;
  }
  writeFileSync(md, contract, "utf8");
  const change = new Map<string, PyValue>([
    ["key", pyItem(pyItem(ts, "contract"), "key")], ["attempts", [total, attempts]], ["wall_total", [wallTotal, wall]],
  ]);
  return [change, await deps.revalidateContract(hub, ts, deps)];
}

/** re.subn(pattern, 字面的替换文字, text)：只用于不会空匹配、替换文字里没有反向引用的模式。 */
function subn(pattern: ReturnType<typeof compilePy>, replacement: string, value: string): [string, number] {
  const points = codePoints(value);
  const found = pattern.finditer(value);
  let result = "";
  let at = 0;
  for (const match of found) {
    result += points.slice(at, match.start).join("") + replacement;
    at = match.end;
  }
  return [result + points.slice(at).join(""), found.length];
}

/** 合同的 attempt 预算用完了：出新版本合同追加预算。 */
export async function cmdTaskBudget(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const reason = pyStrip(optional(args, "reason") || "");
  if (!reason) throw new HubError("--reason 要写明为什么追加（会记进事件）", EXIT_USAGE);
  const attempts = pyIntOf(args["attempts"] ?? null);
  const change = await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    const status = getOf(ts, "status");
    const key = getOf(pyItem(ts, "contract"), "key");
    if (pyEq(status, "done") || pyEq(status, "stopped") || !pyTruthy(key)) {
      throw new HubError(`${task} 是 ${pyStrValue(status)}、合同 ${pyTruthy(key) ? pyStrValue(key) : "还没写"}：没有可追加预算的执行阶段`, EXIT_USAGE);
    }
    const pid = markPid(hub, task);
    if (stageBusy(pyItem(pyItem(ts, "stages"), "5-exec")) || (pyTruthy(pid) && deps.pidAlive(Number(pyIntOf(pid))) !== false)) {
      throw new HubError(`${task} 的执行端正在办：等它交付再追加`, EXIT_BLOCKED);
    }
    const [raised, problems] = await raiseBudget(hub, ts, attempts, deps);
    if (raised.size > 0) {
      (pyItem(ts, "exec") as PyDict).set("attempts_left", attemptsLeft(hub, ts));
      await hub.saveState(state); // 新版本合同已经写下：问题也要记在状态里，不然下一次升版撞上同名文件
      await hub.appendEvent("budget.raised", [["task", task], ["reason", reason], ...[...raised].map(([name, value]) => [String(name), value] as const)]);
    }
    if (problems.length > 0) throw new HubError(`预算没有追加成：${problems.join("；")}`, EXIT_BLOCKED);
    return raised;
  }));
  out.print(`${task} 的预算追加到 ${attempts} 次（合同 ${pyStrValue(pyItem(change, "key"))}）。接着用 send 回复协调人，让它给执行端重发返工`);
  return EXIT_OK;
}

/** 已结项的主任务：补做结项收尾。 */
export async function cmdTaskCleanup(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const leftover = await withTaskQuiet(hub, task, out, deps, () => withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    if (!pyEq(getOf(ts, "status"), "done")) throw new HubError(`主任务 ${task} 还没结项：进行中的阶段要用这些 worktree`, EXIT_USAGE);
    const left = await deps.tidyFinished(hub, ts, `${task} 已结项：这一轮没有复审结论，由后面的 attempt 取代`, deps);
    await hub.saveState(state);
    return left;
  }));
  for (const item of leftover) out.print(`没做完：${item}`);
  out.print(`${task} 的结项收尾：${leftover.length === 0 ? "已完成" : `${leftover.length} 处没做完`}`);
  return leftover.length === 0 ? EXIT_OK : EXIT_FAIL;
}

/** 站主给协调人发信（回复、停止）。stdin 是 --file - 时读的文字（缺省读本进程的标准输入）。 */
export async function cmdSend(args: CommandArgs, out: CommandOut = new PyOut(), stdin: () => string = readStdin): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const kind = text(args, "type");
  const rework = optional(args, "rework");
  const factsChecked = pyTruthy(args["facts_checked"] ?? false);
  const body = text(args, "file") !== "-" ? pyReadText(text(args, "file")) : stdin();
  const summary = pyStrip(body);
  if (codePoints(summary).length > MAX_OWNER_CHARS) {
    throw new HubError(`信有 ${codePoints(summary).length} 字，超过 ${MAX_OWNER_CHARS} 字：压缩一下，或把细节写进仓库里的文件、在信里给路径`, EXIT_USAGE);
  }
  const fields = new Map<string, PyValue>(FIELDS.map((key) => [key, "无"]));
  fields.set("摘要", summary || "无");
  const replyTo = optional(args, "reply_to");
  const letter = meta(OWNER, COORDINATOR, task, kind, replyTo || "none");
  if (rework) {
    if (kind !== "回复" || !STAGE_ORDER.includes(rework) || rework === "3j-jev" || rework === "6j-jev") {
      throw new HubError("--rework 只能随“回复”发，写阶段后缀（例如 2-contract；JEV 不用返工）", EXIT_USAGE);
    }
    fields.set("需协调人决定", `站主要求 ${task}-${rework} 返工：给它发“返工”，brief 写清站主要改的地方`);
  }
  if (factsChecked) {
    if (kind !== "回复") throw new HubError("--facts-checked 只能随“回复”发", EXIT_USAGE);
    fields.set("需协调人决定", "站主已核实规划依赖的仓库外事实（结果见摘要）：开工合同端时把核实结果写进 brief");
  }
  let decision = pyTruthy(args["decision"] ?? false);
  const noDecision = pyTruthy(args["no_decision"] ?? false);
  if ((decision || noDecision) && kind !== "回复") throw new HubError("--decision、--no-decision 只能随“回复”发", EXIT_USAGE);
  const errors = letterErrors(letter, fields, pySplitlines(fields.get("摘要") as string).length + 5);
  if (errors.length > 0) throw new HubError(errors.join("；"), EXIT_USAGE);
  const msg = await withStateLock(hub, async () => {
    const state = hub.loadState();
    const ts = pyGet(state.tasks(), task) as PyDict | null;
    if (decision && ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    // 第 50 轮：合同写出来之前，站主对“提问”的答复就是规划的决定，默认记下、附进之后的合同
    decision = decision || (!noDecision && ts !== null && kind === "回复" && !rework
      && !pyTruthy(getOf(orMap(getOf(ts, "contract")), "version")) && answersQuestion(hub, replyTo));
    if (rework && ts === null) throw new HubError(`没有登记主任务 ${task}`, EXIT_USAGE);
    if (factsChecked && !pyTruthy(getOf(orMap(getOf(ts ?? new Map(), "external_facts")), "pending"))) {
      const early = ts !== null && !pyEq(pyItem(pyItem(pyItem(ts, "stages"), "1-plan"), "status"), "delivered");
      throw new HubError(`${task} 没有待核实的仓库外事实${early
        ? "：规划端还没交付，事实在交付时才登记。这次先不带 --facts-checked 回复（核实结果写进正文），交付后内核会再来信" : ""}`, EXIT_USAGE);
    }
    const delivered = await hub.deliver(letter, fields);
    if (ts !== null && kind === "停止") ts.set("status", "stopped");
    else if (ts !== null && pyEq(getOf(ts, "status"), "blocked")) ts.set("status", "active").set("coordinator_rejections", 0n);
    if (rework) {
      (ts as PyDict).set("owner_rework", new Map<string, PyValue>([
        ["suffix", rework], ["msg", delivered], ["requested_at", utcNow()], ["text", fields.get("摘要") as string],
      ]));
      await hub.appendEvent("owner_rework.requested", [["task", task], ["suffix", rework], ["msg", delivered]]);
    }
    if (factsChecked) {
      const record = pyItem(ts as PyDict, "external_facts") as PyDict;
      const pending = popItem(record, "pending");
      record.set("checked", pending).set("pending", []).set("checked_at", utcNow()).set("checked_msg", delivered);
      await hub.appendEvent("external_facts.checked", [["task", task], ["count", BigInt(lenOf(pyItem(record, "checked")))], ["msg", delivered]]);
    }
    if (decision) {
      listOf(ts as PyDict, "decisions").push(new Map<string, PyValue>([["msg", delivered], ["text", fields.get("摘要") as string], ["at", utcNow()]]));
      await hub.appendEvent("owner.decision_recorded", [["task", task], ["msg", delivered]]);
    }
    if (ts !== null && kind === "回复" && pyTruthy(getOf(orMap(getOf(ts, "exec")), "gate_claim"))) {
      (pyItem(ts, "exec") as PyDict).set("gate_claim", false); // 站主看过了：热修补还是返工执行端，按站主的答复办
      await hub.appendEvent("exec.gate_claim_answered", [["task", task], ["msg", delivered]]);
    }
    await hub.saveState(state);
    return delivered;
  });
  out.print(`已投递 ${msg}`);
  if (decision) out.print("已记为站主决定：之后合同端交的合同末尾会附上这封信的原文（不想附就带 --no-decision）");
  return EXIT_OK;
}

/** 对最近一次 attempt 重新核验（不重跑执行端）。 */
export async function cmdExecRecheck(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const task = text(args, "task");
  const result = await withTaskQuiet(hub, task, out, deps, () => new Engine(hub, null, null, deps).recheckExec(task));
  const ok = pyTruthy(pyItem(result, "check_ok"));
  out.print(`${task} 执行阶段重新核验：${ok ? "通过" : "未通过"}（attempt 状态 ${pyStrValue(pyGet(result, "status"))}，check --fresh 退出码 `
    + `${pyStrValue(pyGet(result, "check_exit"))}，范围违规 ${pyStrValue(pyGet(result, "scope_violations"))}）`);
  return ok ? EXIT_OK : EXIT_FAIL;
}

/** 站主收信：逐封打印，不是 --peek 就挪进 cur。 */
export async function cmdTake(args: CommandArgs, out: CommandOut = new PyOut()): Promise<number> {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const letters = hub.unread(OWNER);
  for (const path of letters) {
    out.print(readText(path));
    if (!pyTruthy(args["peek"] ?? false)) await hub.take(path);
  }
  if (letters.length === 0) out.print("（站主没有未读信）");
  return EXIT_OK;
}

/** 主任务与信箱概况。 */
export function cmdStatus(args: CommandArgs, out: CommandOut = new PyOut(), deps: EngineDeps = REAL_ENGINE_DEPS): number {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const state = hub.loadState();
  const unread = new Map<string, PyValue>([...Object.keys(ROSTER), OWNER].map((agent) => [agent, BigInt(hub.unread(agent).length)]));
  if (pyTruthy(args["json"] ?? false)) {
    out.print(dumps(new Map<string, PyValue>([["tasks", state.tasks()], ["unread", unread]]), { ensureAscii: false, indent: 2 }));
    return EXIT_OK;
  }
  for (const ts of state.tasks().values()) {
    out.print(`## ${pyStrValue(pyItem(ts, "task"))} ${pyStrValue(pyItem(ts, "title"))}（${pyStrValue(pyItem(ts, "status"))}）`);
    out.print(stageStatusTable(ts as PyDict));
    out.print();
  }
  const shown = [...unread].filter(([, count]) => count !== 0n).map(([agent, count]) => `${agent} ${count}`);
  out.print(`未读：${shown.join("、") || "无"}`);
  const runner = purePathStr(hub.root, ".runner");
  out.print(`运行中的 hub：${isDirectory(runner) ? pyStrip(readText(purePathStr(runner, "owner.json"))) : "无"}`);
  const runnersDir = purePathStr(hub.root, ".runners");
  const runners = isDirectory(runnersDir)
    ? readdirSync(runnersDir).filter((name) => lockAlive(purePathStr(runnersDir, name), deps)).sort(cmpCodePoints)
    : [];
  const executing = landingBlockers(hub, new Map<string, PyValue>([["task", null], ["contract_task", NUL]]), true, deps).map(pyStrValue);
  out.print(`并行：最多 ${configuredParallel(hub, { parallel: null })} 个主任务；在跑的主任务 runner：${runners.join("、") || "无"}；`
    + `在跑的执行端：${executing.join("、") || "无"}`);
  return EXIT_OK;
}

/**
 * 回合读进去的上下文：每次模型调用的新输入、缓存读、缓存写之和（pi 的 usage 键名）。pi 岗位不回报花费，配额花在哪只看得到这几项；
 * claude 回合的记录里没有 usage，记为没有。
 */
const USAGE_PROMPT_KEYS = ["input", "cacheRead", "cacheWrite", "cacheWrite1h"];

/** 每个工人回合一行：主任务、工人、用时、这一回合的花费（第 16 轮之前的 claude 记录按会话依次相减换算回这一回合的）、token 用量。 */
export function turnMetrics(hub: Hub): PyDict[] {
  const records: PyValue[] = [];
  for (const path of resultFiles(purePathStr(hub.root, "turns"))) {
    try {
      records.push(loads(pyReadText(path)));
    } catch (error) {
      if (error instanceof PyJsonError || error instanceof PyUnicodeDecodeError) continue; // 都是 ValueError
      throw error;
    }
  }
  const keyOf = (record: PyValue): string => { const id = getOf(record, "turn_id"); return pyTruthy(id) ? pyStrValue(id) : ""; };
  const keys = records.map(keyOf); // 先算全部的键：record.get 报错照 Python 在排序之前抛
  const order = records.map((_, index) => index).sort((a, b) => cmpCodePoints(keys[a] as string, keys[b] as string) || a - b);
  const lastTotal = new Map<string, number>();
  const rows: PyDict[] = [];
  for (const record of order.map((index) => records[index] as PyDict)) {
    let cost = pyGet(record, "cost_usd");
    const legacy = !record.has("session_cost_usd");
    if (legacy && cost !== null) {
      const total = pyFloatOf(cost);
      const session = pyStrValue(pyGet(record, "session_id"));
      const previous = lastTotal.get(session);
      cost = previous === undefined || total < previous ? total : pyRound(total - previous, 6);
      lastTotal.set(session, total);
    }
    const sessionKey = pyGet(record, "session_key");
    const wall = pyGet(record, "wall_seconds");
    const usage = pyGet(record, "usage");
    const tokens = (...keys: string[]): PyValue => usage instanceof Map
      ? keys.map((key) => usage.get(key)).filter((value): value is bigint => typeof value === "bigint").reduce((a, b) => a + b, 0n)
      : null;
    rows.push(new Map<string, PyValue>([
      ["task", stageOf(pyTruthy(sessionKey) ? pyStrValue(sessionKey) : "")[0] || "?"], ["agent", pyGet(record, "agent")],
      ["seconds", pyFloatOf(pyTruthy(wall) ? wall : 0n)], ["cost_usd", cost], ["deliver_refusals", pyGet(record, "deliver_refusals")],
      ["thinking_chars", pyGet(record, "thinking_chars")], ["thinking_tokens", pyGet(record, "thinking_tokens")],
      ["prompt_tokens", tokens(...USAGE_PROMPT_KEYS)], ["cache_read_tokens", tokens("cacheRead")], ["output_tokens", tokens("output")],
    ]));
  }
  return rows;
}

/** turns 下两层目录里的 result.json（Python 用两层通配的 glob 找），照 sorted(Path)：逐段比，Windows 上每段先转小写。 */
function resultFiles(turns: string): string[] {
  const found: string[][] = [];
  for (const agent of listDir(turns)) {
    for (const turn of listDir(purePathStr(turns, agent))) {
      if (isFile(purePathStr(turns, agent, turn, "result.json"))) found.push([agent, turn]);
    }
  }
  const fold = (part: string): string => (process.platform === "win32" ? part.toLowerCase() : part);
  found.sort((a, b) => cmpCodePoints(fold(a[0] as string), fold(b[0] as string)) || cmpCodePoints(fold(a[1] as string), fold(b[1] as string)));
  return found.map(([agent, turn]) => purePathStr(turns, agent as string, turn as string, "result.json"));
}

/** 回合记录里有这一项的加总；全都没有写“未记”。 */
export function recordedSum(rows: readonly PyDict[], key: string): string {
  const values = rows.filter((row) => pyGet(row, key) !== null).map((row) => pyItem(row, key));
  return values.length > 0 ? pyStrValue(pySum(values)) : "未记";
}

/** token 用量的加总，以万为单位；记录里都没有时写“未记”。 */
export function tokenSum(rows: readonly PyDict[], key: string): string {
  const values = rows.filter((row) => pyGet(row, key) !== null).map((row) => pyItem(row, key));
  return values.length > 0 ? `${pyFixed(pyFloatOf(pySum(values)) / 10000, 1)} 万` : "未记";
}

/** 执行端每个主任务的 attempt 数与墙钟，读账本里的 exec.started / exec.finished。 */
export function execMetrics(hub: Hub): PyDict {
  const started = new Map<PyKey, [PyValue, PyValue]>();
  const totals: PyDict = new Map();
  const ledger = hub.ledger();
  for (const line of existsSync(ledger) ? jsonlLines(readText(ledger)) : []) {
    let event: PyValue;
    try {
      event = loads(line);
    } catch (error) {
      if (error instanceof PyJsonError) continue;
      throw error;
    }
    const kind = getOf(event, "event");
    if (pyEq(kind, "exec.started")) {
      const runDir = hashable(getOf(event, "run_dir"));
      const key = [...started.keys()].find((item) => pyEq(item, runDir));
      started.set(key === undefined ? runDir : key, [getOf(event, "task"), getOf(event, "at")]);
      continue;
    }
    if (!pyEq(kind, "exec.finished")) continue;
    const runDir = hashable(getOf(event, "run_dir"));
    const key = [...started.keys()].find((item) => pyEq(item, runDir));
    if (key !== undefined) {
      const [task, at] = started.get(key) as [PyValue, PyValue];
      started.delete(key);
      const seconds = (secondsOf(pyItem(event, "at")) - secondsOf(at));
      const name = hashable(task);
      const found = [...totals.keys()].find((item) => pyEq(item, name));
      if (found === undefined) totals.set(name, new Map<string, PyValue>([["attempts", 0n], ["seconds", 0.0]]));
      const entry = totals.get(found === undefined ? name : found) as PyDict;
      entry.set("attempts", (entry.get("attempts") as bigint) + 1n);
      entry.set("seconds", (entry.get("seconds") as number) + seconds);
    }
  }
  return totals;
}

/** 当字典键用的值：列表、字典照 Python 抛 TypeError（unhashable）。 */
function hashable(value: PyValue): PyKey {
  if (Array.isArray(value) || value instanceof Map) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(value)}'`);
  return value;
}

/** datetime.strptime(at[:19], "%Y-%m-%dT%H:%M:%S") 的秒数（照 UTC 算；只拿来相减）。 */
function secondsOf(at: PyValue): number {
  if (typeof at !== "string") throw new PyCrash("TypeError", `'${pyTypeName(at)}' object is not subscriptable`);
  const value = head(at, 19);
  const ms = strptimeSeconds(value);
  if (ms === null) throw new PyCrash("ValueError", `time data ${pyRepr(value)} does not match format '%Y-%m-%dT%H:%M:%S'`);
  return ms;
}

const ISO_SECONDS = new RegExp("^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})$");

/** 内核写的 at 都是 utc_now 的“YYYY-MM-DDTHH:MM:SS”加 Z：只认两位的月日时分秒（别的写法照 Python 报 ValueError，不细分报错文字）。 */
function strptimeSeconds(value: string): number | null {
  const match = ISO_SECONDS.exec(value);
  if (match === null) return null;
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number) as [number, number, number, number, number, number];
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 61) return null;
  const date = new Date(Date.UTC(2000, 0, 1));
  date.setUTCFullYear(year, month - 1, day);
  if (date.getUTCMonth() !== month - 1 || day < 1) return null;
  if (second > 59) return null;
  date.setUTCHours(hour, minute, second, 0);
  return date.getTime() / 1000;
}

/** 各主任务、各端的回合数、用时与花费。 */
export function cmdMetrics(args: CommandArgs, out: CommandOut = new PyOut()): number {
  const hub = new Hub(findRepo(optional(args, "repo")));
  const rows = turnMetrics(hub);
  const executions = execMetrics(hub);
  if (pyTruthy(args["json"] ?? false)) {
    out.print(dumps(new Map<string, PyValue>([["turns", rows], ["exec", executions]]), { ensureAscii: false, indent: 2 }));
    return EXIT_OK;
  }
  const tasks = sortedValues([...rows.map((row) => pyItem(row, "task")), ...executions.keys()]);
  for (const task of tasks) {
    out.print(`## ${pyStrValue(task)}`);
    out.print("| 工人 | 回合 | 分钟 | 美元 | 交差退回 | 思考字数 | 思考 token | 读上下文 token | 其中缓存读 | 输出 token |");
    out.print("|---|---|---|---|---|---|---|---|---|---|");
    const theirs = rows.filter((row) => pyEq(pyItem(row, "task"), task));
    for (const agent of sortedValues(theirs.map((row) => pyItem(row, "agent")))) {
      const mine = theirs.filter((row) => pyEq(pyItem(row, "agent"), agent));
      const costs = mine.map((row) => pyItem(row, "cost_usd")).filter((cost) => cost !== null);
      const minutes = pyFloatOf(pySum(mine.map((row) => pyItem(row, "seconds")))) / 60;
      out.print(`| ${pyStrValue(agent)} | ${mine.length} | ${pyFixed(minutes, 1)} | ${costs.length > 0 ? pyFixed(pySum(costs), 2) : "未回报"} | `
        + `${recordedSum(mine, "deliver_refusals")} | ${recordedSum(mine, "thinking_chars")} | ${recordedSum(mine, "thinking_tokens")} | `
        + `${tokenSum(mine, "prompt_tokens")} | ${tokenSum(mine, "cache_read_tokens")} | ${tokenSum(mine, "output_tokens")} |`);
    }
    const found = [...executions.keys()].find((item) => pyEq(item, task));
    if (found !== undefined) {
      const entry = executions.get(found) as PyDict;
      out.print(`| 执行端（调度器 run） | ${pyPercentD(pyItem(entry, "attempts"))} 个 attempt | ${pyFixed(pyFloatOf(pyItem(entry, "seconds")) / 60, 1)} | 见 pi_dispatch metrics |`);
    }
    out.print();
  }
  const known = rows.map((row) => pyItem(row, "cost_usd")).filter((cost) => cost !== null);
  const minutes = pyFloatOf(pySum(rows.map((row) => pyItem(row, "seconds")))) / 60;
  out.print(`工人回合合计：${rows.length} 个，${pyFixed(minutes, 1)} 分钟，${pyFixed(pySum(known), 2)} 美元（回报了花费的部分），`
    + `token：读上下文 ${tokenSum(rows, "prompt_tokens")}、输出 ${tokenSum(rows, "output_tokens")}（回报了用量的部分）`);
  return EXIT_OK;
}

/**
 * sorted(set(values))：去重后照 Python 的 < 排；None 与文字混在一起时照 Python 抛 TypeError。全是同一种非文字的值时不排（Python 会照数值排）：
 * 只有手改过的台账、exec.started 写了整数主任务号才碰得到（themistally-04 复核时指出，接受）。
 */
function sortedValues(values: readonly PyValue[]): PyValue[] {
  const unique: PyValue[] = [];
  for (const value of values) if (!unique.some((item) => pyEq(item, value))) unique.push(value);
  if (unique.some((item) => typeof item !== "string") && unique.length > 1) {
    const kinds = [...new Set(unique.map(pyTypeName))];
    if (kinds.length > 1) throw new PyCrash("TypeError", `'<' not supported between instances of '${kinds[1]}' and '${kinds[0]}'`);
  }
  return unique.sort((a, b) => (typeof a === "string" && typeof b === "string" ? cmpCodePoints(a, b) : 0));
}

/** 合同端开工了没有：ts["contract"] 有内容，或 2-contract 不是 idle。 */
function contractStarted(ts: PyDict): boolean {
  return pyTruthy(pyItem(ts, "contract")) || !pyEq(pyItem(pyItem(pyItem(ts, "stages"), "2-contract"), "status"), "idle");
}

/** ts.setdefault(key, [])：交回那个列表。 */
function listOf(ts: PyDict, key: string): PyValue[] {
  if (!ts.has(key)) ts.set(key, []);
  const value = ts.get(key);
  if (!Array.isArray(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value as PyValue)}' object has no attribute 'append'`);
  return value;
}

const orList = (value: PyValue): PyValue => (pyTruthy(value) ? value : []);
const orMap = (value: PyValue): PyValue => (pyTruthy(value) ? value : new Map());

function popItem(map: PyDict, key: string): PyValue {
  if (!map.has(key)) throw new PyCrash("KeyError", pyRepr(key));
  const value = map.get(key) as PyValue;
  map.delete(key);
  return value;
}

function lenOf(value: PyValue): number {
  if (typeof value === "string") return codePoints(value).length;
  if (Array.isArray(value)) return value.length;
  if (value instanceof Map) return value.size;
  throw new PyCrash("TypeError", `object of type '${pyTypeName(value)}' has no len()`);
}

/**
 * sys.stdin.read()：main 已把标准输入重设成 UTF-8（errors="replace"），通用换行。经启动器、管道送字节的情形由 hub-handoff 契约的命令表
 * 场景核（3883，⑤j3）；j1 的契约换成采样时读到的文字。
 */
function readStdin(): string {
  const CR = String.fromCharCode(13);
  // ignoreBOM：Python 的 utf-8（不是 utf-8-sig）留下开头的 U+FEFF，strip() 也不去它；TextDecoder 缺省会吃掉（Node、Bun 实测）
  const decoded = new TextDecoder("utf-8", { ignoreBOM: true }).decode(readFileSync(0));
  return decoded.split(CR + LF).join(LF).split(CR).join(LF);
}

function listDir(path: string): string[] {
  return isDirectory(path) ? readdirSync(path) : [];
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
