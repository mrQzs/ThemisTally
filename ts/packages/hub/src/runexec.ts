// 执行端的代办里改状态的部分（迁移第 ⑤g2 片）：kit_hub.py 的 run_exec、dispatch_attempt、start_rework、rebase_candidate、scratch_worktree、
// rework_added_files、ensure_rework_scope、start_retry、finish_exec、write_review、final_audit_turn、exec_marks、exec_window、LandBusy、
// EXEC_LAND_WAIT_SECONDS、EXEC_LAND_RETRY_SECONDS、load_contract_screen、run_jev。只读与纯文字的部分在 exec.ts（⑤g1）。
// deps 只给契约用（themistally-15 定的，⑤g 设计稿第 12、13 节）：用例当时换掉的内层函数，以及两边各起一次就不一样的几样，照记录注入；
// 生产调用方不传。执行报告、scope.json、observations.json、终审回合的记录与决策端点的回答可以是任何 JSON 值，语义与报错照 Python。
import { closeSync, existsSync, mkdtempSync, openSync, readFileSync, rmSync, rmdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { mtimeUtcSeconds, utcCompact, utcNow } from "@themis/base/clock";
import { readText, writeText, writeTextAtomic } from "@themis/base/fsutil";
import { pyCaught } from "@themis/base/pyexc";
import { PyCrash, pyFixed, pyGet, pyIntOf, pyItem, pyIter, pyJoin, pyLenValue, pyPercentD, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyDecodeUtf8, pyDecodeUtf8Replace } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { purePathName, purePathParent, purePathStr, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyStrip } from "@themis/base/pyre";
import { compilePy, fromPoints, toPoints } from "@themis/base/pyregex";
import { pyWinErrorMessage } from "@themis/base/supervise";
import { type Battery, batteryDict, loadBatteries, loadLockedBatteries, type Settings, settingsFromConfig } from "@themis/config/decisions";
import { Session } from "@themis/config/decisions-client";
import { mdScopeLists, mdSection } from "@themis/dispatcher/contract";
import { answerValue } from "@themis/dispatcher/decision-records";
import { globPaths } from "@themis/dispatcher/instruction";
import { compilePatterns, matches } from "@themis/dispatcher/patterns";
import { getState } from "@themis/dispatcher/status";
import { type ContractDeps, REAL_DEPS, bumpContractVersion, setContractBase, syncExecutorLine } from "./accept.ts";
import { EXIT_BLOCKED } from "./constants.ts";
import { contractPaths, tail } from "./contract.ts";
import { HubError } from "./errors.ts";
import {
  addModifiedFiles, attemptsLeft, carrySource, cutOff, emptyCommit, failedAttempt, failedChecksBrief, failureLines, gateClaims, jevFlag, pySliceHead,
  reportLeftovers, retrySection, returnedBlockers, reworkSection, unreportedGateClaims,
} from "./exec.ts";
import { REAL_GATE_POST_DEPS, addWorktree, attemptBase } from "./gatepost.ts";
import { TEMPLATE_DIR, git } from "./kernel.ts";
import { DirLock, type Hub } from "./mailbox.ts";
import { relativeTo } from "./taskstate.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);

/** 执行端开工前等落地锁多久；等不到就把信扣 EXEC_LAND_RETRY_SECONDS 秒再办（第 35 轮）。 */
export const EXEC_LAND_WAIT_SECONDS = 60.0;
export const EXEC_LAND_RETRY_SECONDS = 120;

/** 执行端开工时落地锁被占（有主任务正在落地，或站主的 exclusive 在等执行端跑完）：过一会儿再试，不是出错。 */
export class LandBusy extends HubError {}

/** 用例当时换掉、或这一片要录下来的内层调用（契约照记录注入）；缺省是真的。 */
export interface ExecDeps extends ContractDeps {
  readonly reworkAddedFiles: (hub: Hub, ts: PyDict) => PyValue | Promise<PyValue>;
  readonly worktreeRoot: (repo: string) => string | Promise<string>;
  readonly mkdtemp: (prefix: string, dir: string) => string | Promise<string>;
  readonly loadLockedBatteries: (pluginDir: string) => PyValue | Promise<PyValue>;
  /** decisions.Session(settings, ledger).ask(battery, state, context)。 */
  readonly ask: (settings: Settings, ledger: string, battery: PyValue, state: PyValue, context: PyDict) => Promise<PyValue>;
  readonly landWaitSeconds: number;
}

export const REAL_EXEC_DEPS: ExecDeps = {
  ...REAL_DEPS,
  reworkAddedFiles,
  worktreeRoot: REAL_GATE_POST_DEPS.worktreeRoot,
  mkdtemp: REAL_GATE_POST_DEPS.mkdtemp,
  loadLockedBatteries: (pluginDir) => new Map([...loadLockedBatteries(pluginDir)].map(([name, battery]) => [name, batteryDict(battery)])),
  ask: (settings, ledger, battery, state, context) => askSession(settings, ledger, battery, state, context),
  landWaitSeconds: EXEC_LAND_WAIT_SECONDS,
};

/** decisions.Session(settings, ledger).ask(battery, state, context)：Session.ask 照字典取这几个键。options 只给契约换传输层与环境变量。 */
export function askSession(settings: Settings, ledger: string, battery: PyValue, state: PyValue, context: PyDict,
  options: ConstructorParameters<typeof Session>[2] = {}): Promise<PyValue> {
  const given = { id: pyItem(battery, "id"), version: pyItem(battery, "version"), sha256: pyItem(battery, "sha256"), questions: pyItem(battery, "questions"),
    thresholds: pyItem(battery, "thresholds") } as unknown as Pick<Battery, "id" | "version" | "sha256" | "questions" | "thresholds">;
  return new Session(settings, ledger, options).ask(given, state, context);
}

/** x or y。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);

/** 交给 subprocess 或 Path() 的值要是字符串：别的照 os.fsdecode 报 TypeError。 */
function argText(value: PyValue): string {
  if (typeof value !== "string") throw new PyCrash("TypeError", `expected str, bytes or os.PathLike object, not ${pyTypeName(value)}`);
  return value;
}

function dict(value: PyValue): PyDict {
  if (!(value instanceof Map)) throw new PyCrash("TypeError", `'${pyTypeName(value)}' object does not support item assignment`);
  return value;
}

/** value[index]，index 是 0 或 -1：列表取项、字符串取字符、字典按整数键查；空的与不能下标的照 Python 报错。 */
function pyIndexAt(value: PyValue, index: 0 | -1): PyValue {
  if (Array.isArray(value) || typeof value === "string") {
    const items = Array.isArray(value) ? value : codePoints(value);
    if (!items.length) throw new PyCrash("IndexError", `${Array.isArray(value) ? "list" : "string"} index out of range`);
    return items.at(index) as PyValue;
  }
  if (value instanceof Map) throw new PyCrash("KeyError", String(index));
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
}

/** ts.setdefault(key, [])。 */
function setDefault(ts: PyDict, key: string): PyValue {
  if (!ts.has(key)) ts.set(key, []);
  return ts.get(key) as PyValue;
}

/** value.append(item) / value.extend(items)：不是列表时照 Python 报 AttributeError。 */
function pyListOf(value: PyValue, method: string): PyValue[] {
  if (!Array.isArray(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute '${method}'`);
  return value;
}

/** text.rstrip(LF)。 */
function rstripLf(text: string): string {
  let end = text.length;
  while (end > 0 && text[end - 1] === LF) end -= 1;
  return text.slice(0, end);
}

/** 没有开始派遣时交差信的六个字段。 */
const notStarted = (summary: string, problem: string, evidence: PyValue): PyDict =>
  new Map<string, PyValue>([["摘要", summary], ["提交", "无"], ["验证", problem], ["偏离", "无"], ["需协调人决定", "给站主发提问"], ["证据", evidence]]);

/**
 * 执行端的一个 attempt：prepare → run（同步等待）→ check --fresh；从执行报告生成交付信的正文。终审退回执行端、上一轮跑满时限、检查没过
 * （越界 0、补丁非空）或门禁热修补之后，先建返工版本（start_rework），执行端从上一轮的候选接着改。
 */
export async function runExec(hub: Hub, ts: PyDict, deps: ExecDeps = REAL_EXEC_DEPS): Promise<PyDict> {
  const left = attemptsLeft(hub, ts);
  if (left !== null && left <= 0n) {
    // 先于任何副作用：返工版本与 REVISE 结论都不该留给一个派不出去的 attempt
    const problem = `预算用完：${pyStrValue(pyItem(ts, "contract_task"))} 各版本已经领取到合同的 max_attempts_total。执行端派不出去，请站主决定：`
      + "出新版本合同追加预算，或站主接手（kit_hub.py task close）";
    ts.set("exec", new Map<string, PyValue>([["run_dir", null], ["check_ok", false], ["error", problem], ["attempts_left", 0n]]));
    return new Map<string, PyValue>([["摘要", "预算用完，执行端没有开始"], ["提交", "无"], ["验证", problem], ["偏离", "无"], ["需协调人决定", "给站主发提问"], ["证据", "无"]]);
  }
  const stop = (problem: string): void => void ts.set("exec", new Map<string, PyValue>([["run_dir", null], ["check_ok", false], ["error", problem]]));
  // 第 35 轮：先挂执行标记、再建返工版本与重派合同。落地锁等不到时（LandBusy）还没有任何副作用，信扣一会儿再办
  return execWindow(hub, ts, async () => {
    const carry = carrySource(hub, ts);
    if (carry !== null) {
      const problem = await startRework(hub, ts, carry[0], carry[1], deps);
      if (problem) {
        stop(problem);
        return notStarted("返工版本没有建成，执行端没有开始", problem, carry[0]);
      }
    }
    const failed = carry === null ? failedAttempt(ts) : null;
    if (failed !== null) {
      const problems = await startRetry(hub, ts, failed, deps);
      if (problems.length) {
        const problem = `重派合同没有建成：${problems.join("；")}`;
        stop(problem);
        return notStarted("重派合同没有建成，执行端没有开始", problem, failed);
      }
    }
    let problems = await ensureReworkScope(hub, ts, deps);
    if (problems.length) {
      const problem = `返工合同的范围没有补成：${problems.join("；")}`;
      stop(problem);
      return notStarted("返工合同的范围没有补成，执行端没有开始", problem, pyItem(pyItem(ts, "contract"), "md"));
    }
    // 第 39 轮：没派遣过的版本，派遣前再对一次名册
    if ((await syncExecutorLine(hub, ts)) !== null) {
      problems = await deps.revalidateContract(hub, ts, deps);
      if (problems.length) {
        const problem = `合同的执行模型改成名册的之后没有通过校验：${problems.join("；")}`;
        stop(problem);
        return notStarted("合同的执行模型没有对上名册，执行端没有开始", problem, pyItem(pyItem(ts, "contract"), "md"));
      }
    }
    return dispatchAttempt(hub, ts, deps);
  }, deps);
}

/** prepare 输出里的 attempt 目录（照 Python 原式编：整式就是第 1 组，数字类认 Unicode 数字）。 */
const ATTEMPT_PATH = compilePy(`(${BS}.agent[${BS}${BS}/]runs[${BS}${BS}/][a-z0-9-]+[${BS}${BS}/]attempt-${BS}d{3})`);

export async function dispatchAttempt(hub: Hub, ts: PyDict, deps: ExecDeps = REAL_EXEC_DEPS): Promise<PyDict> {
  const key = pyItem(pyItem(ts, "contract"), "key");
  const [code, out] = await deps.runPd(hub, ["prepare", key as string], 1800);
  const match = ATTEMPT_PATH.search(out);
  if (code !== 0 || match === null) {
    ts.set("exec", new Map<string, PyValue>([["run_dir", null], ["check_ok", false], ["error", `prepare 失败：${tail(out, 15n)}`]]));
    return new Map<string, PyValue>([["摘要", "prepare 失败，执行端没有开始"], ["提交", "无"], ["验证", tail(out, 15n)], ["偏离", "无"], ["需协调人决定", "无"], ["证据", "无"]]);
  }
  const runDir = pyResolve(purePathStr(hub.repo, match.group));
  dict(pyItem(ts, "contract")).set("dispatched", true); // 这个版本派遣过了：之后再改（热修补）就要出新版本
  let budget = 1800n;
  try {
    const contract = loads(readText(contractPaths(hub, ts)[1]));
    budget = pyIntOf(pyGet(or(pyGet(contract, "budget"), new Map()), "max_wall_seconds_per_attempt", 1200n)) + 900n;
  } catch (error) {
    if (!pyCaught(error, ["ValueError", "TypeError"])) throw error;
  }
  await hub.appendEvent("exec.started", [["task", pyItem(ts, "task")], ["run_dir", runDir]]);
  const [runCode] = await deps.runPd(hub, ["run", runDir], Number(budget));
  return finishExec(hub, ts, runDir, BigInt(runCode), deps);
}

/**
 * 返工版本（第 10 轮）：上一轮记 REVISE、建返工提交；合同复制成下一版，base_sha 指向返工提交，末尾追加终审的阻塞项。第 35 轮：上一轮跑满
 * 时限或门禁热修补之后也走这里；候选建在旧的基准测试上时由 rebase_candidate 搬到当前基准测试上，之前的返工链随之作废。
 */
export async function startRework(hub: Hub, ts: PyDict, previous: string, why: PyValue = "audit", deps: ExecDeps = REAL_EXEC_DEPS): Promise<string | null> {
  const state = getState(previous);
  if (state !== "REVISE") {
    const review = writeReview(hub, ts, previous, "REVISE");
    const [code, out] = await deps.runPd(hub, ["verdict", previous, "--verdict", "REVISE", "--class", state === "TIMEOUT" ? "TIMEOUT" : "EXECUTION_ERROR", "--review", review]);
    if (code !== 0) return `verdict REVISE 被调度器拒绝：${LF}${tail(out, 15n)}`;
  }
  const base = attemptBase(ts, previous);
  // 退出码 1 才是“不是祖先”；提交不存在等错误（128）照旧走 branch --rework，由调度器报错
  const rebuilt = runGit(["merge-base", "--is-ancestor", argText(pyItem(pyItem(ts, "oracle"), "sha")), argText(base)], hub.repo, "ignore").status === 1;
  let sha: string;
  if (rebuilt) {
    const [made, problem] = await rebaseCandidate(hub, ts, previous, base as string, deps);
    if (made === null) return problem;
    sha = made;
  } else {
    const [code, out] = await deps.runPd(hub, ["branch", previous, "--rework"]);
    const match = /commit=([0-9a-f]{40})/u.exec(out);
    if (code !== 0 || match === null) return `branch --rework 没有建出返工提交：${LF}${tail(out, 15n)}`;
    sha = match[1] as string;
  }
  // 第 60 轮：上一轮接着返工提交改、一行没动，branch --rework 建出的提交与基线同树。接着从原来的基线改，返工链上不记这个空提交
  const reused = !rebuilt && emptyCommit(hub, sha);
  if (reused) sha = base as string;
  let blockers: PyValue;
  if (why === "audit") {
    const hit = [...pyIter(or(pyGet(ts, "audit_history"), []))].reverse().find((item) => pyGet(item, "stage") === "7-audit-post");
    blockers = hit === undefined ? "" : pyGet(hit, "blockers");
  } else if (why === "upstream") {
    blockers = returnedBlockers(ts, previous);
  } else {
    blockers = failureLines(previous);
  }
  // 第 120 轮：执行端写进报告的剩余工作。failed 这条路不经终审；upstream 接上的候选，终审未必看过这份报告
  const leftovers = why === "failed" || why === "upstream" ? reportLeftovers(previous) : "";
  const number = BigInt(pyLenValue(or(pyGet(ts, "rework_chain"), []))) + 1n;
  // 终审返工照旧一律升版（prepare 失败过的返工版本也不就地改）；超时、热修补之后的版本没派遣过就就地改
  let problems = pyTruthy(pyGet(pyItem(ts, "contract"), "dispatched")) || why === "audit" ? await bumpContractVersion(hub, ts) : [];
  if (!problems.length) {
    const [md] = contractPaths(hub, ts);
    // 之前的重派说明写着“从 base_sha 重新开始”，和这一节矛盾；它列的失败是旧候选、旧门禁上的
    const text = rstripLf(dropRetrySections(readText(md)));
    writeText(md, `${text}${LF}${LF}${reworkSection(previous, sha, blockers, number, why, rebuilt, state === "TIMEOUT", leftovers)}`, false);
    problems = await setContractBase(hub, ts, sha, deps);
  }
  if (problems.length) return `返工合同没有建成：${problems.join("；")}`;
  if (rebuilt && pyTruthy(pyGet(ts, "rework_chain"))) {
    const superseded = pyListOf(setDefault(ts, "rework_chain_superseded"), "extend");
    const chain = ts.get("rework_chain") as PyValue;
    ts.delete("rework_chain");
    superseded.push(...pyIter(chain));
  }
  if (!reused) {
    pyListOf(setDefault(ts, "rework_chain"), "append").push(new Map<string, PyValue>([["from", purePathName(previous)], ["commit", sha],
      ["contract", pyItem(pyItem(ts, "contract"), "key")], ["at", utcNow()], ["why", why], ["rebuilt", rebuilt]]));
  }
  await hub.appendEvent("exec.rework_based", [["task", pyItem(ts, "task")], ["previous", purePathName(previous)], ["commit", sha],
    ["contract", pyItem(pyItem(ts, "contract"), "key")], ["why", why], ["rebuilt", rebuilt], ["reused", reused]]);
  return null;
}

/** 内核追加过的重派说明（RETRY_SECTION_RE）。 */
export const RETRY_SECTION_RE = compilePy(`(?ms)^## Retry（重派第 ${BS}d+ 次，内核追加）${BS}n.*?(?=^## |${BS}Z)`);

/** RETRY_SECTION_RE.sub("", text)。 */
function dropRetrySections(text: string): string {
  const points = toPoints(text);
  let out = "";
  let at = 0;
  for (const match of RETRY_SECTION_RE.finditer(points)) {
    out += fromPoints(points, at, match.start);
    at = match.end;
  }
  return out + fromPoints(points, at);
}

/**
 * 候选建在旧的基准测试上（门禁热修补之后）：在当前基准测试上重放它，返回（返工提交, 问题）。重放的是分叉点到候选树的全部改动（含之前的
 * 返工链），基准测试文件除外：它们以当前基准测试为准。
 */
export async function rebaseCandidate(hub: Hub, ts: PyDict, previous: string, base: string, deps: ExecDeps = REAL_EXEC_DEPS): Promise<[string | null, string]> {
  const oracle = pyItem(pyItem(ts, "oracle"), "sha");
  const tree = pyGet(loads(readText(purePathStr(previous, "candidate.json")) || "{}"), "tree");
  if (!pyTruthy(tree)) return [null, `${purePathName(previous)} 的候选记录里没有 tree`];
  const fork = pyStrip(git(["merge-base", base, argText(oracle)], hub.repo));
  const excludes = pyIter(or(pyGet(pyItem(ts, "oracle"), "files"), [])).map((path) => `:(exclude)${pyStrValue(path)}`);
  const diff = runGit(["diff", "--binary", "--no-renames", fork, argText(tree), "--", ".", ...excludes], hub.repo, "pipe");
  if (diff.status !== 0 || isBlankBytes(diff.stdout)) {
    return [null, `算不出 ${purePathName(previous)} 的改动：${codePoints(pyDecodeUtf8Replace(diff.stderr)).slice(0, 300).join("") || "差异为空"}`];
  }
  const patch = purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-5-exec`), "evidence", `carry-${purePathName(previous)}-${utcCompact()}.patch`);
  pathMkdir(purePathParent(patch), true, true);
  writeFileSync(patch, diff.stdout);
  const short = codePoints(oracle as string).slice(0, 10).join("");
  const made = await scratchWorktree(hub, "carry", oracle as string, (work): [string | null, string] => {
    const [code, out] = runMerged(["git", "apply", "--3way", "--whitespace=nowarn", patch], work);
    if (code !== 0) return [null, `${purePathName(previous)} 的候选放不到基准测试 ${short} 上：${LF}${tail(pyDecodeUtf8Replace(out), 15n)}`];
    git(["commit", "-q", "-m", `返工基线：${purePathName(previous)} 的候选搬到基准测试 ${short} 上（hub）`], work);
    return [pyStrip(git(["rev-parse", "HEAD"], work)), ""];
  }, deps);
  if (made[0] === null) return made;
  git(["update-ref", `refs/themis/rework/${pyStrValue(pyItem(ts, "contract_task"))}/${purePathName(previous)}`, made[0]], hub.repo);
  return made;
}

/** bytes.strip() 之后是空的：只去 ASCII 空白（空格、TAB、LF、VT、FF、CR）。 */
const isBlankBytes = (data: Buffer): boolean => data.every((byte) => byte === 0x20 || (byte >= 0x09 && byte <= 0x0d));

/** 内核直接起的 git（不经 git()：没有时限、不核退出码）。找不到 git 照 Python 报 FileNotFoundError。 */
function runGit(args: readonly string[], cwd: string, output: "pipe" | "ignore"): { status: number | null; stdout: Buffer; stderr: Buffer } {
  const done = spawnSync("git", [...args], { cwd, stdio: ["ignore", output, output], maxBuffer: Infinity, windowsHide: true });
  if (done.error) throw spawnFailure(done.error);
  return { status: done.status, stdout: done.stdout ?? Buffer.alloc(0), stderr: done.stderr ?? Buffer.alloc(0) };
}

function spawnFailure(error: Error): Error {
  return (error as NodeJS.ErrnoException).code === "ENOENT" ? new PyCrash("FileNotFoundError", pyWinErrorMessage(2)) : error;
}

/** stderr 并进 stdout（Python 的 stderr=STDOUT）：两路接同一个临时文件，交错的次序与 Python 一样。 */
function runMerged(argv: readonly string[], cwd: string): [number | null, Buffer] {
  const dir = mkdtempSync(join(tmpdir(), "themis-merged-"));
  const file = join(dir, "output");
  try {
    const fd = openSync(file, "w");
    let done;
    try {
      done = spawnSync(argv[0] as string, argv.slice(1), { cwd, stdio: ["ignore", fd, fd], windowsHide: true });
    } finally {
      closeSync(fd);
    }
    if (done.error) throw spawnFailure(done.error);
    return [done.status, readFileSync(file)];
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** 内核自己用的临时 worktree（合入后回归、落地预演、搬候选）：用完就收掉，不碰主工作区。 */
export async function scratchWorktree<T>(hub: Hub, label: string, commit: string, fn: (path: string) => T | Promise<T>, deps: ExecDeps = REAL_EXEC_DEPS): Promise<T> {
  const prefix = `${codePoints(purePathName(hub.repo)).slice(0, 16).join("")}-hub-${label}-`;
  const path = purePathStr(await deps.mkdtemp(prefix, purePathStr(await deps.worktreeRoot(hub.repo))));
  rmdirSync(path);
  await addWorktree(hub, path, commit);
  try {
    return await fn(path);
  } finally {
    runGit(["worktree", "remove", "--force", path], hub.repo, "ignore");
  }
}

/** 返工基线（最近一个返工提交）里由前几轮 attempt 新增的文件，相对基准测试提交；没有返工时为空。 */
export function reworkAddedFiles(hub: Hub, ts: PyDict): PyValue {
  const chain = or(pyGet(ts, "rework_chain"), []);
  if (!pyTruthy(chain)) return [];
  const out = git(["diff", "--name-only", "-z", "--no-renames", "--diff-filter=A", argText(pyItem(pyItem(ts, "oracle"), "sha")),
    argText(pyItem(pyIndexAt(chain, -1), "commit"))], hub.repo);
  return out.split(String.fromCharCode(0)).filter((path) => path);
}

/**
 * 返工基线里已经有前几轮新增的文件：新 attempt 再改它们是“修改”，合同却只“允许新增”（第 18 轮）。把这些文件加进 allowed_modified_files；
 * 合同已经派遣过就先出下一版。返回问题（空表示合同可以派遣）。
 */
export async function ensureReworkScope(hub: Hub, ts: PyDict, deps: ExecDeps = REAL_EXEC_DEPS): Promise<string[]> {
  let added: PyValue;
  try {
    added = await deps.reworkAddedFiles(hub, ts);
  } catch (error) {
    if (error instanceof HubError) return [`读不出返工基线里新增了哪些文件：${error.message}`];
    throw error;
  }
  if (!pyTruthy(added)) return [];
  let [md] = contractPaths(hub, ts);
  const allowed = compilePatterns(pyIter(or(mdScopeLists(readText(md)).get("allowed_modified_files") ?? null, [])) as string[]);
  const missing = pyIter(added).filter((path) => !matches(allowed, path as string)) as string[];
  if (!missing.length) return [];
  if (pyTruthy(pyGet(pyItem(ts, "contract"), "dispatched"))) {
    const problems = await bumpContractVersion(hub, ts);
    if (problems.length) return problems;
    [md] = contractPaths(hub, ts);
  }
  const [text, problems] = addModifiedFiles(readText(md), missing);
  if (problems.length) return problems;
  writeText(md, text, false);
  await hub.appendEvent("contract.scope_widened", [["task", pyItem(ts, "task")], ["key", pyItem(pyItem(ts, "contract"), "key")], ["files", missing]]);
  return deps.revalidateContract(hub, ts, deps);
}

/**
 * 检查没过之后重派同一份合同，执行端什么也不知道（第 19 轮）：出下一版合同，末尾附上一轮没过的检查与范围违规。上一轮的候选不当基线。
 * 第 120 轮起只剩越界或补丁为空的走这里。
 */
export async function startRetry(hub: Hub, ts: PyDict, failed: string, deps: ExecDeps = REAL_EXEC_DEPS): Promise<string[]> {
  if (pyTruthy(pyGet(pyItem(ts, "contract"), "dispatched"))) {
    const problems = await bumpContractVersion(hub, ts);
    if (problems.length) return problems;
  }
  const [md] = contractPaths(hub, ts);
  const notes = setDefault(ts, "retry_notes");
  writeText(md, `${rstripLf(readText(md))}${LF}${LF}${retrySection(failed, ts, BigInt(pyLenValue(notes)) + 1n)}`, false);
  pyListOf(notes, "append").push(purePathName(failed));
  await hub.appendEvent("exec.retry_noted", [["task", pyItem(ts, "task")], ["previous", purePathName(failed)], ["contract", pyItem(pyItem(ts, "contract"), "key")]]);
  return deps.revalidateContract(hub, ts, deps);
}

/** str(v.get("text") if isinstance(v, dict) and v.get("text") else v)。 */
const textOf = (item: PyValue): string => pyStrValue(item instanceof Map && pyTruthy(pyGet(item, "text")) ? pyGet(item, "text") : item);

/**
 * attempt 跑完之后的核验：check --fresh、范围门禁与 attempt 状态；从执行报告生成交付信的正文。exec-recheck 也走这里：内核中途停下或判定逻辑
 * 修过之后，对已有的 attempt 重新核验，不占新的尝试次数。
 */
export async function finishExec(hub: Hub, ts: PyDict, runDir: string, runCode: bigint | null, deps: ExecDeps = REAL_EXEC_DEPS): Promise<PyDict> {
  const status = getState(runDir);
  const [checkCode, checkOut] = await deps.runPd(hub, ["check", runDir, "--fresh"], 3600);
  const scope = loads(readText(purePathStr(runDir, "scope.json")) || "{}");
  const violations = or(pyGet(scope, "violations"), []);
  const report = loads(readText(purePathStr(runDir, "executor-report.json")) || "{}");
  const rel = relativeTo(pyResolve(runDir), pyResolve(hub.repo));
  const exec = new Map<string, PyValue>([["run_dir", runDir], ["status", status], ["run_exit", runCode], ["check_exit", BigInt(checkCode)]]);
  exec.set("scope_violations", BigInt(pyLenValue(violations)));
  exec.set("check_ok", status === "NEEDS_REVIEW" && checkCode === 0 && !pyTruthy(violations));
  exec.set("check_tail", tail(checkOut, 20n));
  exec.set("conflicts", BigInt(pyLenValue(or(pyGet(report, "contract_conflicts"), []))));
  exec.set("attempts_left", attemptsLeft(hub, ts));
  ts.set("exec", exec);
  await hub.appendEvent("exec.finished", [["task", pyItem(ts, "task")], ["run_dir", runDir], ["status", status], ["check_exit", BigInt(checkCode)],
    ["scope_violations", BigInt(pyLenValue(violations))]]);
  let claims = checkCode !== 0 ? gateClaims(report) : [];
  const unreported = checkCode !== 0 && !pyTruthy(report) ? unreportedGateClaims(runDir) : [];
  if (!claims.length) claims = unreported;
  if (claims.length) {
    exec.set("gate_claim", true); // 门禁热修补或站主答复之前不能返工执行端（_guard_rework）
    exec.set("gate_claims", claims.slice(0, 8).map((claim) => codePoints(claim).slice(0, 600).join(""))); // 热修补时交给门禁端
    await hub.appendEvent("exec.gate_claimed", [["task", pyItem(ts, "task")], ["run_dir", runDir], ["claims", BigInt(claims.length)]]);
  }
  const listing = (name: string): string => pyIter(or(pyGet(report, name), [])).map(textOf).join("；") || "无";
  const done = pyIter(or(pyGet(report, "dod"), [])).filter((item) => item instanceof Map)
    .map((item) => `${pyStrValue(pyGet(item, "id"))}:${pyStrValue(pyGet(item, "status"))}`).join("、") || "（报告没有 DoD）";
  let verdictLine = `内核 check --fresh：${checkCode === 0 ? "通过" : `失败（退出码 ${checkCode}）`}；范围违规 ${pyLenValue(violations)} 条；attempt 状态 ${status}`;
  const failed = checkCode !== 0 ? failedChecksBrief(runDir) : "";
  if (failed) verdictLine += `；没过的检查：${failed}`;
  if (exec.get("attempts_left") !== null) {
    // T012 的协调人数 attempt 目录，说“预算已耗尽”；预检失败的那一次没领取预算，其实还剩 1 次（第 39 轮）
    verdictLine += `；合同预算还剩 ${pyPercentD(exec.get("attempts_left"))} 次 attempt`;
  }
  // 改动按候选数，不按执行报告（第 39 轮）
  const files = pyGet(scope, "files");
  const changed = Array.isArray(files) ? files.length : pyLenValue(or(pyGet(report, "changed_files"), []));
  exec.set("stalled", status === "TIMEOUT" && changed === 0); // 第 55 轮
  // 第 104 轮：候选没收上来时不能写“改动 0 个文件”
  const collectErrors = or(pyGet(loads(readText(purePathStr(runDir, "observations.json")) || "{}"), "collect_errors"), []);
  exec.set("collect_failed", pyTruthy(collectErrors));
  const said = pyGet(report, "executor_status");
  const saidText = pyTruthy(said) ? pyStrValue(said)
    : cutOff(runDir) ? "没交执行报告（模型最后一条输出被截断：stopReason=length）" : "未知（没有可读的执行报告）";
  let deviation = `解读：${listing("interpretations")}；局限：${listing("limitations")}`;
  if (unreported.length) {
    deviation += `；执行器没交报告，思考里说门禁有错（共 ${unreported.length} 处，摘录前 3 处）：`
      + unreported.slice(0, 3).map((claim) => codePoints(claim).slice(0, 240).join("")).join("；");
  }
  let stalled = exec.get("stalled") === true
    ? "这一轮跑满时限、候选一处没改：给站主发提问（拆小合同、换执行模型或站主接手），站主指定之前内核不放行执行端返工。" : "";
  if (pyTruthy(collectErrors)) {
    stalled = `候选没收上来（调度器收集出错：${pyStrValue(pySliceHead(pyIndexAt(collectErrors, 0), 300))}）：执行端的改动还在 attempt 的工作区里，`
      + "从头重派会丢掉它们。给站主发提问，站主指定之前内核不放行执行端返工。";
  }
  const changedText = pyTruthy(collectErrors) ? "没收上来（收集出错）" : `${changed} 个文件`;
  // 第 111 轮：没有待决项就写“无”
  const pending: [string, string][] = [["合同矛盾", listing("contract_conflicts")], ["未决问题", listing("unresolved_questions")]];
  const decide = (claims.length ? "执行端说门禁测试有错（原话见下面与“偏离”）：给 gate-sonnet 发返工（热修补），或给站主发提问；门禁重新交付或站主答复之前，"
    + "内核不放行执行端返工。" : "") + stalled + pending.filter(([, text]) => text !== "无").map(([name, text]) => `${name}：${text}`).join("；");
  return new Map<string, PyValue>([
    ["摘要", codePoints(`执行端自述 ${saidText}；DoD：${done}；候选改动 ${changedText}`).slice(0, 400).join("")],
    ["提交", `无（候选补丁 ${rel}/candidate.patch）`], ["验证", verdictLine], ["偏离", deviation], ["需协调人决定", decide || "无"],
    ["证据", `${rel}/summary.md、${rel}/executor-report.md、${rel}/checks/`],
  ]);
}

/** 这个 attempt 交付之后的最后一个终审回合记录（输出合格、没有违规）；没有终审过时为 None。 */
export function finalAuditTurn(hub: Hub, ts: PyDict, runDir: string): PyValue {
  const marker = purePathStr(runDir, "candidate.patch");
  const since = mtimeUtcSeconds(isFile(marker) ? marker : runDir);
  const key = `${pyStrValue(pyItem(ts, "task"))}-7-audit-post`;
  let best: PyValue = null;
  // glob 不排序：finished_at 相同时 max 取先遇到的，次序就是目录的原始次序
  for (const path of globPaths(purePathStr(hub.root, "turns", "audit-sonnet"), ["*", "result.json"])) {
    let record: PyValue;
    try {
      record = loads(pyDecodeUtf8(readFileSync(path)));
    } catch (error) {
      if (pyCaught(error, ["OSError", "ValueError"])) continue;
      throw error;
    }
    if (pyGet(record, "session_key") === key && cmpCodePoints(pyStrValue(or(pyGet(record, "finished_at"), "")), since) >= 0
      && !pyTruthy(pyGet(record, "output_error")) && !pyTruthy(pyGet(record, "violations"))) {
      if (best === null || cmpCodePoints(pyStrValue(pyGet(record, "finished_at")), pyStrValue(pyGet(best, "finished_at"))) > 0) best = record;
    }
  }
  return best;
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** 终审报告写成调度器的复审记录（verdict 要求的 “Verdict:” 行）。 */
export function writeReview(hub: Hub, ts: PyDict, runDir: string, verdict: string): string {
  const reviewDir = purePathStr(hub.repo, ".agent", "reviews", pyStrValue(pyItem(ts, "contract_task")));
  pathMkdir(reviewDir, true, true);
  let reviewPath = purePathStr(reviewDir, `${purePathName(runDir)}-hub.md`);
  // 第 84 轮：复审者从终审那一回合的记录取；内核自己记的 REVISE 根本没有终审
  const turn = finalAuditTurn(hub, ts, runDir);
  let reviewer: string;
  let auditReport: string;
  if (turn === null) {
    reviewer = "- 复审者：没有终审回合（内核按 check 与运行状态记这一结论）";
    auditReport = "（这个 attempt 没有终审）";
  } else {
    reviewer = `- 复审者：audit-sonnet（${pyJoin(",", or(pyGet(turn, "models"), [pyStrValue(pyGet(turn, "model_requested"))]))}，思考档位要求 `
      + `${pyStrValue(pyGet(turn, "effort_requested"))}、生效 ${pyStrValue(or(pyGet(turn, "effort_effective"), "未回报"))}；回合 ${pyStrValue(pyGet(turn, "turn_id"))}），终审报告如下`;
    auditReport = readText(purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-7-audit-post`), "report.md"));
  }
  const gate = pyItem(ts, "gate_post");
  const body = [`# 复审记录：${pyStrValue(pyItem(ts, "contract_task"))} ${purePathName(runDir)}（七端信箱 hub）`, ""];
  body.push(`- 合同：${pyStrValue(pyItem(pyItem(ts, "contract"), "key"))}（base ${pyStrValue(attemptBase(ts, runDir))}）`);
  body.push(`- 内核 check --fresh：退出码 ${pyStrValue(pyGet(pyItem(ts, "exec"), "check_exit"))}；范围违规 ${pyStrValue(pyGet(pyItem(ts, "exec"), "scope_violations"))}`);
  body.push(`- 战后门禁：白盒测试退出码 ${pyStrValue(pyGet(gate, "whitebox_exit"))}；变异检查退出码 ${pyStrValue(pyGet(gate, "mutate_exit"))}`);
  const jevStatus = (stage: string): string => pyStrValue(pyGet(or(pyGet(pyItem(ts, "jev"), stage), new Map()), "status"));
  body.push(`- JEV：一审前 ${jevStatus("3j-jev")}；终审前 ${jevStatus("6j-jev")}`);
  body.push(reviewer, "", "## 终审报告", "", pyStrip(auditReport) || "（终审报告为空）", "", `Verdict: ${verdict}`, "");
  if (existsSync(reviewPath)) reviewPath = purePathStr(reviewDir, `${purePathName(runDir)}-hub-${utcCompact()}.md`);
  writeText(reviewPath, body.join(LF), false);
  return reviewPath;
}

/** 执行标记的目录（第 20 轮）。 */
export function execMarks(hub: Hub): string {
  return purePathStr(hub.root, "ledger", "exec-active");
}

/**
 * 执行端从 prepare 到 check 跑完都挂一份标记（第 20 轮）：落地要等别的主任务的标记都撤掉。挂标记之前先过落地锁：有主任务正在落地，
 * 等它落完再开始。
 */
export async function execWindow<T>(hub: Hub, ts: PyDict, fn: () => Promise<T>, deps: ExecDeps = REAL_EXEC_DEPS): Promise<T> {
  const marks = execMarks(hub);
  pathMkdir(marks, true, true);
  const path = purePathStr(marks, `${pyStrValue(pyItem(ts, "task"))}.json`);
  try {
    const lock = new DirLock(purePathStr(hub.root, ".land"), deps.landWaitSeconds).acquire();
    try {
      writeTextAtomic(path, `${dumps(new Map<string, PyValue>([["pid", BigInt(process.pid)], ["task", pyItem(ts, "task")], ["at", utcNow()]]))}${LF}`);
    } finally {
      lock.release();
    }
  } catch (error) {
    if (error instanceof HubError) throw new LandBusy(error.message, EXIT_BLOCKED);
    throw error;
  }
  try {
    return await fn();
  } finally {
    try {
      unlinkSync(path);
    } catch (error) {
      if (!pyCaught(error, ["OSError"])) throw error;
    }
  }
}

/** 一审前的 JEV 题库（模板目录里的 contract-screen）。 */
export function loadContractScreen(): PyValue {
  const battery = loadBatteries(purePathStr(TEMPLATE_DIR, "questions")).get("contract-screen");
  if (battery === undefined) throw new PyCrash("KeyError", pyRepr("contract-screen"));
  return batteryDict(battery);
}

/** JEV 端：取被评对象那封信正文的四个字段，用题库调用决策 API（shadow 语义：只给审核端参考）。 */
export async function runJev(hub: Hub, ts: PyDict, suffix: string, deps: ExecDeps = REAL_EXEC_DEPS): Promise<PyDict> {
  const subject = or(pyGet(pyItem(pyItem(ts, "stages"), suffix === "3j-jev" ? "2-contract" : "5-exec"), "fields"), new Map());
  const summary = new Map<string, PyValue>(["摘要", "验证", "偏离", "需协调人决定"].map((key) => [key, pyGet(subject, key, "")]));
  let contract: PyValue = new Map();
  let goal = "";
  try {
    const [mdPath, jsonPath] = contractPaths(hub, ts);
    contract = loads(readText(jsonPath));
    goal = codePoints(pyStrip(mdSection(readText(mdPath), "Goal") ?? "")).slice(0, 4000).join("");
  } catch (error) {
    if (!pyCaught(error, ["ValueError", "KeyError"])) throw error;
  }
  let battery: PyValue;
  let state: PyDict;
  if (suffix === "3j-jev") {
    battery = loadContractScreen();
    const planReport = codePoints(readText(purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-1-plan`), "report.md"))).slice(0, 4000).join("");
    state = new Map<string, PyValue>([["planned_goal", planReport], ["contract_summary", summary], ["contract_scope", pyGet(contract, "scope")],
      ["definition_of_done", pyGet(contract, "definition_of_done")]]);
  } else {
    battery = pyItem(await deps.loadLockedBatteries(purePathStr(hub.repo, "plugins", "decisions")), "report-screen");
    const runDir = purePathStr(argText(pyItem(pyItem(ts, "exec"), "run_dir")));
    const report = loads(readText(purePathStr(runDir, "executor-report.json")) || "{}");
    const scope = loads(readText(purePathStr(runDir, "scope.json")) || "{}");
    const observed = loads(readText(purePathStr(runDir, "observations.json")) || "{}");
    // 客观指纹与执行端的自述放在一起；目标取合同的 Goal 一节（第 12 轮）
    state = new Map<string, PyValue>([
      ["contract_goal", goal ? goal : pyGet(contract, "title")], ["contract_scope", pyGet(contract, "scope")], ["definition_of_done", pyGet(contract, "definition_of_done")],
      ["executor_report", new Map<string, PyValue>([["text", dumps(summary, { ensureAscii: false })],
        ["contract_conflicts", BigInt(pyLenValue(or(pyGet(report, "contract_conflicts"), [])))],
        ["unresolved_questions", BigInt(pyLenValue(or(pyGet(report, "unresolved_questions"), [])))]])],
      ["observations", new Map<string, PyValue>([["check_exit", pyGet(pyItem(ts, "exec"), "check_exit")], ["scope_violations", pyGet(pyItem(ts, "exec"), "scope_violations")],
        ["changed_files", pyIter(or(pyGet(scope, "files"), [])).filter((item) => item instanceof Map).map((item) => pyGet(item, "path"))],
        ["review_hints", pyGet(observed, "review_hints")], ["whitebox_exit", pyGet(pyItem(ts, "gate_post"), "whitebox_exit")],
        ["mutation_counts", pyGet(pyItem(ts, "gate_post"), "mutation_counts")]])],
    ]);
  }
  const settings = settingsFromConfig(new Map()); // decisions.Settings() 的缺省值
  settings.mode = "shadow";
  settings.configured_mode = "shadow";
  settings.reason = "hub";
  settings.points = [pyItem(battery, "id") as string];
  const result = await deps.ask(settings, purePathStr(hub.root, "ledger", "decisions.jsonl"), battery, state,
    new Map<string, PyValue>([["task", pyItem(ts, "task")], ["stage", suffix]]));
  const lines: string[] = [];
  const questions = or(pyGet(battery, "questions"), new Map());
  const answers = or(pyGet(result, "answers"), new Map()) as PyDict;
  for (const name of ([...answers.keys()] as string[]).sort(cmpCodePoints)) {
    const answer = answers.get(name) as PyValue;
    const [text, confidence] = answerValue(answer);
    const question = or(pyGet(questions, name), new Map());
    const label = pyGet(or(pyGet(battery, "labels"), new Map()), name, name);
    lines.push(`${pyStrValue(label)}：${text}（置信 ${pyFixed(confidence, 2)}）${jevFlag(answer, question, or(pyGet(battery, "thresholds"), new Map()))}`);
  }
  const record = new Map<string, PyValue>([["status", pyItem(result, "status")], ["reason", pyGet(result, "reason")], ["answers", pyGet(result, "answers")],
    ["battery", pyItem(battery, "id")], ["battery_version", pyItem(battery, "version")], ["at", utcNow()]]);
  dict(pyItem(ts, "jev")).set(suffix, record);
  const reportMd = `# JEV 判断（${suffix}）${LF}${LF}- 题库：${pyStrValue(pyItem(battery, "id"))} ${pyStrValue(pyItem(battery, "version"))}${LF}`
    + `- 结果：${pyStrValue(pyItem(result, "status"))} ${pyStrValue(or(pyGet(result, "reason"), ""))}${LF}${LF}`
    + `${lines.map((line) => `- ${line}`).join(LF) || "- （无意见）"}${LF}`;
  writeTextAtomic(purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-${suffix}`), "report.md"), reportMd);
  const verdict = lines.length ? lines.join("；") : `无意见（${pyStrValue(or(pyGet(result, "reason"), pyItem(result, "status")))}）`;
  return new Map<string, PyValue>([
    ["摘要", codePoints(`JEV（${pyStrValue(pyItem(battery, "id"))}）：${verdict}`).slice(0, 600).join("")], ["提交", "无"],
    ["验证", `决策 API ${pyStrValue(pyItem(result, "status"))}，${pyStrValue(pyGet(result, "latency_ms"))} ms`], ["偏离", "无"],
    ["需协调人决定", "无（JEV 只是参考，门禁不读）"], ["证据", `.agent/mailbox/tasks/${pyStrValue(pyItem(ts, "task"))}-${suffix}/report.md`],
  ]);
}
