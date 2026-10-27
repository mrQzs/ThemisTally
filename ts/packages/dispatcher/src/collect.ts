// collect 与 collect --recover（迁移第 ④b7b 片）：事件摘要与执行报告的状态、固定候选（树对象加完整的二进制补丁，做往返
// 校验）、改动清单与范围判定、主工作区在运行前后的变化、决策模型对执行报告的筛查，最后定状态、写 summary.md。run 跑完时
// 调 collect；调度器异常退出之后由 collect --recover 补收。候选、改动与范围三份证据只写一次（文件已存在就失败）。
import { closeSync, openSync, statSync, writeFileSync, writeSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { pidAlive } from "@themis/base/process";
import { PyCrash, type PyOut, pyGet, pyItem, pyLenValue, pyRepr, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8Replace, pyOSErrorOf, pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue } from "@themis/base/pyjson";
import { PyWinError, pyRename } from "@themis/base/pyos";
import { pyExists } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, isDigitChar, pyIntParse, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { SHA_RE, mdSection } from "./contract.ts";
import { DECISIONS_RECORD } from "./decision-records.ts";
import { extractReport, reviewHints, summarizeEvents } from "./events.ts";
import { loadAttempt, logEvent, pathArg, setState, sha256File, strArg, writeJson } from "./evidence.ts";
import { plannerAttemptPublicationErrors } from "./gates.ts";
import { diffRaw, ignoredInventory, mainRepoFingerprint, snapshotTree, treeFromPatch, unindexablePaths } from "./gitops.ts";
import { extraProtectedPaths, plannerPaths, repoConfig } from "./kernel-config.ts";
import { attemptExecutor } from "./metrics.ts";
import { DEPENDENCY_PATTERNS, PROTECTED_PATTERNS, SENSITIVE_PATTERNS, compilePatterns, hasControlChars, matches } from "./patterns.ts";
import { expectsSettled } from "./pi-cli.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_OK, EXIT_USAGE, Repo, git, gitChecked, gitText, readJsonOr } from "./repo.ts";
import type { SessionFactory } from "./run-health.ts";
import { attemptInFlight, getState, resolveRunDir } from "./status.ts";
import { type SummaryContext, writeSummary } from "./summary.ts";

/** 交给决策模型的执行报告最多这么多个字符。 */
const DECISIONS_REPORT_CHARS = 12000;
const MAIN_REPO_COVERAGE = "HEAD 与已跟踪、未被忽略文件的内容；不含被忽略的文件与仓库之外的路径";
const NUL = String.fromCharCode(0);
const IS_WINDOWS = process.platform === "win32";

export interface CollectArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly recover: boolean;
}

const dict = (pairs: readonly (readonly [string, PyValue])[]): PyDict => new Map<string, PyValue>(pairs);
/** x or fallback。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);
const head = <T>(items: readonly T[], count: number): T[] => items.slice(0, count);
const firstChars = (text: string, count: number): string => codePoints(text).slice(0, count).join("");

/** read_text_or：读不了或不是 UTF-8 时交回缺省值。 */
function readTextOr(file: string, fallback = ""): string {
  try {
    return pyReadText(file);
  } catch (error) {
    if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return fallback;
    throw error;
  }
}

/** set(value) 里的字符串：列表的元素、字典的键、字符串的字符；不能迭代或元素不可哈希时照 Python 抛 TypeError。 */
function stringSet(value: PyValue): Set<string> {
  if (typeof value === "string") return new Set(codePoints(value));
  if (value instanceof Map) return new Set([...value.keys()].map(String));
  if (!Array.isArray(value)) throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not iterable`);
  const found = new Set<string>();
  for (const item of value) {
    if (Array.isArray(item) || item instanceof Map) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(item)}'`);
    if (typeof item === "string") found.add(item);
  }
  return found;
}

/** with open(path, "xb") 再 write(produce())：文件已存在就失败；先建出文件再求内容，求内容出错时留下空文件。 */
function writeNewBytes(file: string, produce: () => Buffer): void {
  let fd: number;
  try {
    fd = openSync(file, "wx");
  } catch (error) {
    throw pyOSErrorOf(error, file) ?? error;
  }
  try {
    const data = produce();
    let offset = 0;
    while (offset < data.length) offset += writeSync(fd, data, offset);
  } finally {
    closeSync(fd);
  }
}

/** record_candidate：固定候选——树对象 ID 加完整的二进制补丁，并用补丁在基线上重建一遍做往返校验。 */
function recordCandidate(repo: Repo, runDir: string, workDir: string, base: string): PyDict {
  const autocrlf = pyGet(readJsonOr(path.join(runDir, "meta.json"), new Map()), "git_autocrlf");
  const tree = snapshotTree(workDir, base, runDir, "candidate", autocrlf);
  const patchPath = path.join(runDir, "candidate.patch");
  writeNewBytes(patchPath, () => gitChecked(["diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--full-index", base, tree], workDir).stdout);
  const stat = gitChecked(["diff", "--stat", "--no-ext-diff", "--no-textconv", "--no-renames", base, tree], workDir).stdout;
  const statPath = path.join(runDir, "candidate.stat.txt");
  try {
    writeFileSync(statPath, stat);
  } catch (error) {
    throw pyOSErrorOf(error, statPath) ?? error;
  }
  let roundtrip: string;
  let verified: boolean;
  try {
    roundtrip = treeFromPatch(repo.root, base, patchPath, runDir, autocrlf);
    verified = roundtrip === tree;
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    [roundtrip, verified] = [`error: ${error.message}`, false];
  }
  return dict([
    ["tree", tree], ["base", base], ["patch", "candidate.patch"], ["patch_sha256", sha256File(patchPath)],
    ["patch_bytes", BigInt(statSync(patchPath).size)], ["patch_roundtrip_verified", verified], ["roundtrip_tree", roundtrip],
    ["recorded_at", utcNow()], ["unindexable_skipped", unindexablePaths(workDir)],
  ]);
}

/** attempt_protected_paths：仓库配置的 extra_protected_paths，加上 prepare 时冻结进 meta.json 的内核 TS 禁区。 */
function attemptProtectedPaths(config: PyDict, meta: PyValue): string[] {
  return [...extraProtectedPaths(config), ...((or(pyGet(meta, "kernel_protected"), []) as string[]))];
}

const issue = (file: string, kind: string, detail: string): PyDict => dict([["path", file], ["kind", kind], ["detail", detail]]);

/** evaluate_scope：逐个改动的路径对照合同的范围与内置禁区，记违规与提醒。 */
export function evaluateScope(changes: readonly PyDict[], contract: PyDict, headAfter: string, base: string, extraProtected: readonly string[] = []): PyDict {
  const scope = contract.get("scope") as PyDict;
  const list = (key: string): string[] => scope.get(key) as string[];
  const exactAllowed = new Set([...list("allowed_modified_files"), ...list("allowed_new_files")]);
  const allowedNew = compilePatterns(list("allowed_new_files"));
  const allowedDeleted = compilePatterns(list("allowed_deleted_files"));
  const allowedModified = compilePatterns(list("allowed_modified_files"));
  const forbidden = compilePatterns(list("forbidden_paths"));
  const protectedPaths = compilePatterns([...PROTECTED_PATTERNS, ...extraProtected], true);
  const dependency = compilePatterns(DEPENDENCY_PATTERNS);
  const sensitive = compilePatterns(SENSITIVE_PATTERNS);
  const violations: PyDict[] = [];
  const warnings: PyDict[] = [];
  const files: PyDict[] = [];
  for (const change of changes) {
    const file = change.get("path") as string;
    const status = change.get("status") as string;
    const [oldMode, newMode] = [change.get("old_mode"), change.get("new_mode")];
    let verdict = "in_scope";
    if (pyTruthy(change.get("path_decode_error") ?? null) || hasControlChars(file)) {
      // 替换解码之后的名字不能拿来做授权判断
      violations.push(issue(pyRepr(file), "invalid_path", "路径含控制字符或不是合法 UTF-8"));
      files.push(dict([["path", pyRepr(file)], ["status", status], ["scope", "violation"]]));
      continue;
    }
    if (matches(protectedPaths, file)) {
      violations.push(issue(file, "protected_path", "合同、证据、代理规则或调度器文件"));
      verdict = "violation";
    } else if (matches(forbidden, file)) {
      violations.push(issue(file, "forbidden_path", "命中 forbidden_paths"));
      verdict = "violation";
    } else if (!matches(status === "A" ? allowedNew : status === "D" ? allowedDeleted : allowedModified, file)) {
      violations.push(issue(file, "out_of_scope", `状态 ${status} 不在允许集合`));
      verdict = "violation";
    }
    if (newMode === "120000") {
      violations.push(issue(file, "symlink", "新增或改为符号链接"));
      verdict = "violation";
    }
    if (newMode === "160000" || oldMode === "160000") {
      violations.push(issue(file, "submodule", "子模块或嵌入仓库变化"));
      verdict = "violation";
    }
    if ((status === "M" || status === "T") && oldMode !== newMode && oldMode !== "120000" && newMode !== "120000") {
      warnings.push(issue(file, "mode_changed", `${String(oldMode)} -> ${String(newMode)}`));
    }
    if (matches(dependency, file) && scope.get("dependency_changes") === "forbidden") {
      if (exactAllowed.has(file)) {
        warnings.push(issue(file, "dependency_manifest_changed", "合同允许修改此文件，但禁止依赖变更：需人工确认"));
      } else {
        violations.push(issue(file, "dependency_change", "合同禁止依赖变更"));
        verdict = "violation";
      }
    }
    if (matches(sensitive, file)) warnings.push(issue(file, "sensitive_file", "测试/CI/构建或环境配置被修改"));
    files.push(dict([["path", file], ["status", status], ["scope", verdict]]));
  }
  const actions = (contract.get("authorization") as PyDict).get("executor") as PyValue[];
  if (headAfter !== base) {
    (actions.includes("local_commit") ? warnings : violations).push(issue("HEAD", "head_moved", `执行器改变了 HEAD（${firstChars(headAfter, 12)}）`));
  }
  const counts = dict(["A", "M", "D", "T"].map((status) => [status, BigInt(changes.filter((change) => change.get("status") === status).length)]));
  return dict([["files", files], ["counts", counts], ["violations", violations], ["warnings", warnings], ["ok", violations.length === 0]]);
}

/** SHA_RE.match(value)：不是字符串时照 Python 抛 TypeError。 */
function shaLike(value: PyValue): boolean {
  if (typeof value !== "string") throw new PyCrash("TypeError", `expected string or bytes-like object, got '${pyTypeName(value)}'`);
  return SHA_RE.test(value);
}

/**
 * main_repo_changes：比较运行前后的主工作区指纹，列出变化的路径，规划端自己的路径与其他路径分开。两次指纹都完整时才比
 * 内容树；HEAD 变化单独报（并行批次提前集成、越界提交都会导致）。
 */
function mainRepoChanges(repoRoot: string, before: PyValue, after: PyDict, planner: readonly string[]): PyDict {
  const result = dict([
    ["changed", pyTruthy(before) && !pyEq(before, after)],
    ["head_before", pyGet(before, "head")], ["head_after", after.get("head") ?? null],
    ["head_changed", pyTruthy(before) && !pyEq(pyGet(before, "head"), after.get("head") ?? null)],
    ["planner_paths", []], ["other_paths", []], ["diff_error", null],
  ]);
  const treeBefore = or(pyGet(before, "content_tree"), "");
  const treeAfter = or(after.get("content_tree") ?? null, "");
  if (!result.get("changed") || pyEq(treeBefore, treeAfter)) return result;
  if (!shaLike(treeBefore) || !shaLike(treeAfter)) {
    result.set("diff_error", "指纹不完整，无法列出变化的路径");
    return result;
  }
  const proc = git(["diff-tree", "-r", "--no-renames", "--name-status", "-z", treeBefore as string, treeAfter as string], repoRoot);
  if (proc.status !== 0) {
    result.set("diff_error", firstChars(pyStrip(pyDecodeUtf8Replace(proc.stderr)), 300) || "git diff-tree 失败");
    return result;
  }
  const fields = pyDecodeUtf8Replace(proc.stdout).split(NUL);
  const compiled = compilePatterns(planner, IS_WINDOWS);
  const [plannerChanged, otherChanged]: [string[], string[]] = [[], []];
  for (let index = 0; index < fields.length - 1; index += 2) {
    const [status, file] = [fields[index] as string, fields[index + 1] as string];
    if (!status || !file) continue;
    (matches(compiled, file) ? plannerChanged : otherChanged).push(`${status} ${file}`);
  }
  result.set("planner_paths", head(plannerChanged, 200));
  result.set("other_paths", head(otherChanged, 200));
  return result;
}

const lenOf = (value: PyValue): bigint => BigInt(pyLenValue(value));

/** decide_report_screen：把执行报告、合同要点与调度器自己的观察交给决策模型筛查。只记录，summary 再读记录。 */
async function decideReportScreen(
  repo: Repo, runDir: string, contract: PyDict, events: PyDict, finalText: string, scope: PyValue, observations: PyDict, sessions: SessionFactory,
): Promise<PyDict | null> {
  const session = sessions(repoConfig(repo), repo.agentDir, path.join(runDir, DECISIONS_RECORD), "report-screen");
  if (session === null) return null;
  const read = readJsonOr(path.join(runDir, "executor-report.json"), new Map());
  const report = read instanceof Map ? read : new Map<string, PyValue>();
  const planMd = readTextOr(path.join(runDir, "plan.md"));
  const dod = (pyGet(contract, "definition_of_done", []) as PyValue[]).map((item) => {
    const entry = dict([["id", pyGet(item, "id")], ["text", pyGet(item, "text")], ["evidence", pyGet(item, "evidence")]]);
    if (pyTruthy(pyGet(item, "intent"))) entry.set("intent", pyItem(item, "intent"));
    return entry;
  });
  const scopeSpec = contract.get("scope") instanceof Map ? (contract.get("scope") as PyDict) : new Map<string, PyValue>();
  const scopeKeys = ["allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"];
  const changedFile = (file: PyValue): PyDict => dict([["status", pyGet(file, "status")], ["path", pyGet(file, "path")], ["scope", pyGet(file, "scope")]]);
  const interpretations = report.get("interpretations");
  const state = dict([
    ["contract_goal", firstChars(pyStrip(mdSection(planMd, "Goal") || ""), 2000)],
    ["contract_scope", dict(scopeKeys.map((key) => [key, scopeSpec.get(key) ?? null]))],
    ["definition_of_done", dod],
    ["executor_report", dict([
      ["text", firstChars(finalText, DECISIONS_REPORT_CHARS)],
      ["executor_status", report.get("executor_status") ?? null],
      ["contract_conflicts", lenOf(or(report.get("contract_conflicts") ?? null, []))],
      ["unresolved_questions", lenOf(or(report.get("unresolved_questions") ?? null, []))],
      ["interpretations", Array.isArray(interpretations) ? BigInt(interpretations.length) : 0n],
    ])],
    ["observations", dict([
      ["changed_files", head((pyGet(scope, "files", []) as PyValue[]).map(changedFile), 100)],
      ["scope_violations", lenOf(pyGet(scope, "violations", []))],
      ["shell_commands", (or(events.get("shell_commands") ?? null, []) as PyValue[]).slice(-40)],
      ["review_hints", or(observations.get("review_hints") ?? null, new Map())],
      ["masked_exit_commands", lenOf(or(events.get("masked_exit_commands") ?? null, []))],
      ["interpretation_mentions", head((or(events.get("interpretation_mentions") ?? null, []) as PyValue[]).map((item) => pyGet(item, "excerpt")), 10)],
    ])],
  ]);
  const battery = session.batteries.get("report-screen");
  if (battery === undefined) throw new PyCrash("KeyError", "'report-screen'");
  return session.ask(battery, state, dict([["attempt", path.basename(runDir)]]));
}

/** collect：收集一次运行的证据，定状态（INFRA_FAILURE、TIMEOUT、CANCELLED、NEEDS_REVIEW），写 summary.md。 */
export async function collect(
  repo: Repo, runDir: string, meta: PyValue, contract: PyDict, executor: PyDict, runInfo: PyValue, sessions: SessionFactory, summary: SummaryContext,
): Promise<string> {
  const workDir = pathArg(pyItem(meta, "worktree"));
  const base = pyItem(meta, "base_sha");
  const [events, finalText] = summarizeEvents(path.join(runDir, "events.jsonl"), workDir, executor, {
    stderrPath: path.join(runDir, "stderr.log"),
    expectsSettled: pyGet(runInfo, "expects_agent_settled"),
    allowedOutside: [runDir, ...(pyTruthy(pyGet(runInfo, "attachments_dir")) ? [pathArg(pyItem(runInfo, "attachments_dir"))] : [])],
    planText: readTextOr(path.join(runDir, "plan.md")),
    protectedRoots: [repo.root],
  });
  writeJson(path.join(runDir, "events-summary.json"), events);
  writeJson(path.join(runDir, "report-status.json"), extractReport(finalText, runDir));
  let candidate: PyDict = new Map();
  const collectErrors: string[] = [];
  try {
    candidate = recordCandidate(repo, runDir, workDir, strArg(base));
    writeJson(path.join(runDir, "candidate.json"), candidate, true);
    const headAfter = gitText(["rev-parse", "HEAD"], workDir);
    const changes = diffRaw(workDir, base as string, candidate.get("tree") as string);
    writeJson(path.join(runDir, "changes.json"), changes, true);
    const scope = evaluateScope(changes, contract, headAfter, base as string, attemptProtectedPaths(repoConfig(repo), meta));
    scope.set("head_after", headAfter);
    writeJson(path.join(runDir, "scope.json"), scope, true);
  } catch (error) {
    // worktree 不在时 git 抛的 NotADirectoryError 在 Python 里也算 OSError，但紧接着 ignored_inventory 照样崩：这里不接
    if (!(error instanceof DispatchError || error instanceof PyOSError || error instanceof PyWinError)) throw error;
    collectErrors.push(error.message);
  }
  const observations = dict([["collect_errors", collectErrors], ["unindexable_skipped", or(candidate.get("unindexable_skipped") ?? null, [])]]);
  try {
    const before = readJsonOr(path.join(runDir, "ignored-before.json"), []);
    const after = new Set(ignoredInventory(workDir));
    const known = stringSet(before);
    observations.set("new_ignored_paths", head([...after].filter((item) => !known.has(item)).sort(cmpCodePoints), 200));
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    observations.set("new_ignored_paths_error", error.message);
  }
  const mainAfter = mainRepoFingerprint(repo.root, runDir);
  const mainBefore = or(pyGet(runInfo, "main_repo_before"), new Map());
  const mainChanged = pyTruthy(mainBefore) && !pyEq(mainBefore, mainAfter);
  observations.set("main_repo_after", mainAfter);
  observations.set("main_repo_changed", mainChanged);
  observations.set("main_repo_coverage", MAIN_REPO_COVERAGE);
  try {
    observations.set("main_repo_changes", mainRepoChanges(repo.root, mainBefore, mainAfter, plannerPaths(repoConfig(repo))));
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    observations.set("main_repo_changes", dict([["changed", mainChanged], ["diff_error", error.message]]));
  }
  if (pyTruthy(candidate.get("tree") ?? null) && pyExists(path.join(runDir, "candidate.patch"))) {
    observations.set("review_hints", reviewHints(path.join(runDir, "candidate.patch")));
  }
  try {
    const scope = readJsonOr(path.join(runDir, "scope.json"), new Map());
    const decision = await decideReportScreen(repo, runDir, contract, events, finalText, scope, observations, sessions);
    if (decision !== null) observations.set("decisions", dict([["report_screen", pyGet(decision, "status")], ["reason", pyGet(decision, "reason")]]));
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    observations.set("decisions_error", error.message);
  }
  writeJson(path.join(runDir, "observations.json"), observations);
  const state = finalState(runInfo, collectErrors, candidate, events);
  setState(runDir, state, [
    ["exit_code", pyGet(runInfo, "exit_code")], ["events_ok", events.get("ok") ?? null],
    ["scope_ok", pyGet(readJsonOr(path.join(runDir, "scope.json"), new Map()), "ok")],
  ]);
  writeSummary(runDir, repo, summary);
  return state;
}

function finalState(runInfo: PyValue, collectErrors: readonly string[], candidate: PyDict, events: PyDict): string {
  if (pyTruthy(pyGet(runInfo, "spawn_error")) || collectErrors.length || !pyTruthy(candidate.get("tree") ?? null)) return "INFRA_FAILURE";
  if (pyTruthy(pyGet(runInfo, "timed_out"))) return "TIMEOUT";
  if (pyTruthy(pyGet(runInfo, "interrupted"))) return "CANCELLED";
  // 模型从未产生回复：启动、凭据或模型配置的问题
  if (!pyTruthy(events.get("assistant_messages") ?? null)) return "INFRA_FAILURE";
  return "NEEDS_REVIEW";
}

/** cmd_collect：调度器异常退出之后恢复证据收集（只认 --recover，Pi 进程要已经不在）。 */
export async function cmdCollect(args: CollectArgs, out: PyOut, sessions: SessionFactory, summary: SummaryContext): Promise<number> {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const publicationErrors = plannerAttemptPublicationErrors(repo, runDir, contract);
  if (publicationErrors.length) throw new DispatchError(`planner-v2 发布门禁拒绝恢复收集：${publicationErrors.join("；")}`, EXIT_BLOCKED);
  const state = getState(runDir);
  if (!attemptInFlight(runDir) || !args.recover) {
    throw new DispatchError(
      `collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）且指定 --recover（当前 ${state}）。`, EXIT_USAGE,
    );
  }
  const started = readJsonOr(path.join(runDir, "run-started.json"), new Map());
  const pid = recordedPid(runDir);
  if (pidAlive(pid)) throw new DispatchError(`记录的 Pi 进程 ${String(pid)} 可能仍在运行；确认终止后再恢复。`);
  let runInfo = readJsonOr(path.join(runDir, "run.json"), null);
  if (runInfo === null) {
    runInfo = recoveredRunInfo(runDir, started);
    writeJson(path.join(runDir, "run.json"), runInfo, true);
  }
  const executor = attemptExecutor(runDir, pyItem(contract, "executor"));
  for (const name of ["candidate.json", "changes.json", "scope.json", "candidate.patch"]) {
    const file = path.join(runDir, name);
    if (pyExists(file)) pyRename(file, path.join(runDir, `${name}.partial`));
  }
  const collected = await collect(repo, runDir, meta, contract, executor as PyDict, runInfo, sessions, summary);
  logEvent(runDir, "recovered_collection");
  out.print(`${collected}（恢复收集；事件可能不完整）`);
  return EXIT_OK;
}

/** pid.txt 里记的进程号；不是纯数字时为 null（str.isdigit 认的数字 int() 未必认，那时照 Python 抛 ValueError）。 */
function recordedPid(runDir: string): number | null {
  const file = path.join(runDir, "pid.txt");
  const text = pyExists(file) ? pyStrip(pyReadText(file)) : "";
  if (!text || !codePoints(text).every(isDigitChar)) return null;
  const pid = pyIntParse(text);
  if (pid === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: ${pyRepr(text)}`);
  return Number(pid);
}

/** 没有 run.json 时按 run-started.json 补一份：记成被中断、已恢复；没有 run-started.json 说明领取之后还没启动 Pi。 */
function recoveredRunInfo(runDir: string, started: PyValue): PyDict {
  const versionFile = path.join(runDir, "preflight", "pi-version.txt");
  const settled = expectsSettled(pyExists(versionFile) ? pyReadText(versionFile) : "");
  const endedAt = utcNow();
  const spawnError = pyTruthy(started) ? null : "领取后调度器退出，未启动 Pi";
  const expects = pyGet(started, "expects_agent_settled", settled);
  const info: PyDict = new Map(started as PyDict);
  const fields: [string, PyValue][] = [
    ["exit_code", null], ["timed_out", false], ["interrupted", true], ["recovered", true], ["ended_at", endedAt],
    ["wall_seconds", null], ["spawn_error", spawnError], ["expects_agent_settled", expects],
  ];
  for (const [key, value] of fields) info.set(key, value);
  return info;
}
