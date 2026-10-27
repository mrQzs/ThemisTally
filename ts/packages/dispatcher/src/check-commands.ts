// check、baseline、verdict 三条命令（迁移第 ④b3 片）。输出照 Python 的 stdout 块缓冲（PyOut 的 bufferStdout）：
// hub 把标准错误并进标准输出，ERROR 行会排在还没冲出的 NOTE、GATE 前面；只有 CHECK、BASELINE 两行是 flush=True。
// 本机的 platform.platform() 由启动器放进 context（迁移计划 D1）。
import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFloatOf, pyGet, pyItem, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorOf, pyReadBytes, pyReadText, pyReadTextReplace } from "@themis/base/pyio";
import { PyWinError, pathMkdir } from "@themis/base/pyos";
import { PyJsonError, type PyDict, type PyValue } from "@themis/base/pyjson";
import { displayPath, purePathStr, pyExists, pyResolve } from "@themis/base/pypath";
import { FLAG_IGNORECASE, FLAG_MULTILINE, compilePy } from "@themis/base/pyregex";
import { cmpCodePoints, codePoints, pyLen, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pyMkdtemp } from "@themis/base/pytempfile";
import { pyEq } from "@themis/base/pyvalue";
import { ProtocolError } from "@themis/base/protocols";
import { prepareFreshWorkspace, runCommandItem, nextNumber, worktreeRoot } from "./command-runner.ts";
import { type PlanContext, loadFixedContractPair, planKeyFromArg, printMessages, validatePlan } from "./contract-plan.ts";
import { PLACEHOLDER_RE } from "./contract.ts";
import {
  VERDICTS, artifactMatchers, candidatePatchOk, loadAttempt, logEvent, pathArg, removeWorktree, setState, sha256File, splitExtras, strArg, writeJson,
} from "./evidence.ts";
import { FAILURE_CLASSES, GATES, attemptOriginNotes, evaluateGates, plannerAttemptPublicationErrors } from "./gates.ts";
import { snapshotTree, treeDrift } from "./gitops.ts";
import { repoConfig } from "./kernel-config.ts";
import { childEnv } from "./pi-cli.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, gitChecked, readJsonOr } from "./repo.ts";
import { getState, resolveRunDir } from "./status.ts";

export const EXIT_DRIFT = 4;
export const REVIEWABLE_STATES = ["NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE", ...VERDICTS];

export interface CheckArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly only: string | null;
  readonly fresh: boolean;
  readonly keep_workspace: boolean;
}

export interface BaselineArgs {
  readonly repo: string | null;
  readonly plan_key: string;
  readonly only: string | null;
  readonly keep_workspace: boolean;
}

export interface VerdictArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly verdict: string;
  readonly review: string;
  readonly failure_class: string | null;
  readonly waive: readonly string[] | null;
  readonly decided_by: string | null;
  readonly human_minutes: number | null;
  readonly note: string | null;
}

/** "%02d" % n。 */
const pad2 = (n: bigint): string => (n < 0n ? `-${String(-n)}` : String(n).padStart(2, "0"));
const firstPoints = (text: string, count: number): string => codePoints(text).slice(0, count).join("");
const ljust = (text: string, width: number): string => text + " ".repeat(Math.max(0, width - pyLen(text)));
/** float(config.get("kill_grace_seconds", 15))。 */
const graceOf = (config: PyDict): number => pyFloatOf(pyGet(config, "kill_grace_seconds", 15n));

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** Path.is_file()：不存在一类的错误为 false，其余照 Python 抛出（pyExists 已经照做）。 */
function isFile(file: string): boolean {
  if (!pyExists(file)) return false;
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** --only 选出的检查：未知的 id 报错，选出来的照合同的次序；一项都没有也报错。 */
function selectChecks(checks: PyDict[], only: string | null): PyDict[] {
  let selected = checks;
  if (only) {
    const wanted = only.split(",").map(pyStrip).filter((item) => item !== "");
    const ids = checks.map((check) => check.get("id") as PyValue);
    const unknown = wanted.filter((item) => !ids.some((id) => pyEq(id, item)));
    if (unknown.length) throw new DispatchError(`未知检查：${unknown.join(", ")}`, EXIT_USAGE);
    selected = checks.filter((check) => wanted.some((item) => pyEq(check.get("id") as PyValue, item)));
  }
  if (!selected.length) throw new DispatchError("合同没有可运行的检查", EXIT_USAGE);
  return selected;
}

/** str(exc)：prepare_fresh_workspace 接住的 DispatchError 与 OSError。 */
function freshFailure(error: unknown): string | null {
  if (error instanceof DispatchError || error instanceof PyOSError || error instanceof PyWinError) return error.message;
  const os = pyOSErrorOf(error, "");
  return os === null ? null : os.message;
}

export async function cmdCheck(args: CheckArgs, out: PyOut, here: string): Promise<number> {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const publicationErrors = plannerAttemptPublicationErrors(repo, runDir, contract);
  if (publicationErrors.length) throw new DispatchError(`planner-v2 发布门禁拒绝验收检查：${publicationErrors.join("；")}`, EXIT_BLOCKED);
  const state = getState(runDir);
  if (!REVIEWABLE_STATES.includes(state)) throw new DispatchError(`状态 ${state} 不能运行验收检查`);
  const originNotes = attemptOriginNotes(repo, meta, here);
  for (const note of originNotes) out.print(`NOTE  ${note}`);
  const candidate = readJsonOr(path.join(runDir, "candidate.json"), new Map());
  if (!pyTruthy(pyGet(candidate, "tree"))) throw new DispatchError("没有候选记录（candidate.json），无法把检查绑定到确切内容");
  const candidateTree = (candidate as PyDict).get("tree") as PyValue;
  const checks = selectChecks(contract.get("checks") as PyDict[], args.only);
  const config = repoConfig(repo);
  const [env, removed] = childEnv(config);
  const grace = graceOf(config);
  const artifacts = artifactMatchers(config);
  const checksRoot = path.join(runDir, "checks");
  pathMkdir(checksRoot, false, true);
  const number = nextNumber(checksRoot);
  const outDir = path.join(checksRoot, pad2(number));
  pathMkdir(outDir, false, false);
  const mode = args.fresh ? "fresh" : "in_place";
  let freshWorkspace: string | null = null;
  let workDir: string;
  if (args.fresh) {
    if (!candidatePatchOk(runDir, candidate)) throw new DispatchError("候选补丁缺失、被改动或未通过往返校验，不能建立干净副本");
    try {
      freshWorkspace = await prepareFreshWorkspace(repo, runDir, meta as PyDict, contract, candidate as PyDict, config, outDir, env, grace);
    } catch (error) {
      const message = freshFailure(error);
      if (message === null) throw error;
      writeJson(path.join(outDir, "checks.json"), new Map<string, PyValue>([
        ["aborted", "fresh_workspace_failed"], ["mode", "fresh"], ["error", message], ["at", utcNow()],
      ]), true);
      throw new DispatchError(`无法建立干净的验收副本：${message}`);
    }
    workDir = freshWorkspace;
  } else {
    workDir = pathArg(pyItem(meta, "worktree"));
    if (!isDir(workDir)) {
      throw new DispatchError(`worktree 已不存在：${workDir}${originNotes.length ? "（attempt 不在本机派遣）" : ""}；可用 --fresh 在干净副本上验收`);
    }
  }
  const autocrlf = pyGet(meta, "git_autocrlf");
  const results: PyDict[] = [];
  let started: string;
  let treeBefore: string;
  let treeAfter: string;
  let preArtifacts: string[];
  let postArtifacts: string[];
  let postUnexpected: string[];
  let modifiedAfter: string[];
  try {
    const base = strArg(pyItem(meta, "base_sha"));
    treeBefore = snapshotTree(workDir, base, outDir, "before", autocrlf);
    const driftBefore = treeDrift(workDir, strArg(candidateTree), treeBefore);
    let preUnexpected: string[];
    [preArtifacts, preUnexpected] = splitExtras(driftBefore.added, artifacts);
    if (driftBefore.modified.length || preUnexpected.length) {
      writeJson(path.join(outDir, "checks.json"), new Map<string, PyValue>([
        ["aborted", "candidate_drift"], ["mode", mode], ["tree_now", treeBefore], ["candidate_tree", candidateTree],
        ["modified", driftBefore.modified], ["unexpected_files", preUnexpected], ["at", utcNow()],
      ]), true);
      const listed = (items: string[]): string => (items.length ? pyStrValue(items.slice(0, 10)) : "无");
      throw new DispatchError(
        `工作副本与候选不一致，检查结果无法代表候选：被修改的候选文件 ${listed(driftBefore.modified)}；候选之外的新文件 ${listed(preUnexpected)}。` +
          "删除这些额外文件、重新派遣以固定新候选，或用 --fresh 在干净副本上验收。",
        EXIT_DRIFT,
      );
    }
    started = utcNow();
    for (const item of checks) {
      const id = pyStrValue(item.get("id") as PyValue);
      out.print(`CHECK ${id} ...`, { flush: true });
      const record = await runCommandItem(item, workDir, env, outDir, grace);
      results.push(record);
      out.print(`CHECK ${id} ${pyStrValue(record.get("status") as PyValue)} ${pyStrValue(pyTruthy(record.get("reason") ?? null) ? (record.get("reason") as PyValue) : "")}`, { flush: true });
    }
    treeAfter = snapshotTree(workDir, base, outDir, "after", autocrlf);
    const driftAfter = treeDrift(workDir, strArg(candidateTree), treeAfter);
    [postArtifacts, postUnexpected] = splitExtras(driftAfter.added, artifacts);
    modifiedAfter = driftAfter.modified;
  } finally {
    if (freshWorkspace !== null && !args.keep_workspace) removeWorktree(repo, freshWorkspace);
  }
  const requiredIds = (contract.get("checks") as PyDict[]).filter((check) => pyTruthy(pyGet(check, "required", true))).map((check) => check.get("id") as PyValue);
  const ranIds = results.map((record) => record.get("id") as PyValue);
  const requiredOk = results.every((record) => !pyTruthy(record.get("required") as PyValue) || pyTruthy(record.get("passed") as PyValue));
  const coversAll = requiredIds.every((id) => ranIds.some((ran) => pyEq(ran, id)));
  const payload: PyDict = new Map<string, PyValue>([
    ["run", number], ["mode", mode], ["workspace", workDir], ["workspace_kept", Boolean(args.fresh && args.keep_workspace)],
    ["started_at", started], ["ended_at", utcNow()], ["candidate_tree", candidateTree],
    ["tree_before", treeBefore], ["tree_after", treeAfter],
    ["modified_by_checks", modifiedAfter.length > 0],
    ["candidate_files_modified", modifiedAfter],
    ["unexpected_files_by_checks", postUnexpected.slice(0, 200)],
    ["artifact_files", [...new Set([...preArtifacts, ...postArtifacts])].sort(cmpCodePoints).slice(0, 200)],
    ["covers_all_required", coversAll], ["all_required_passed", requiredOk],
    ["env_removed", removed], ["results", results],
  ]);
  writeJson(path.join(outDir, "checks.json"), payload, true);
  logEvent(runDir, "checks", [["run", number], ["mode", mode], ["passed", requiredOk], ["covers_all_required", coversAll]]);
  if (modifiedAfter.length) out.print(`WARN  检查修改了候选文件：${modifiedAfter.slice(0, 10).join(", ")}（结果不能作为 PASS 证据）`);
  if (postUnexpected.length) {
    out.print(`WARN  检查产生了候选之外的新文件：${postUnexpected.slice(0, 10).join(", ")}。确属缓存或报告时，加入 .gitignore 或 ` +
      "dispatch.config.json 的 check_artifact_patterns。");
  }
  out.print(`检查结果（${mode}）：${requiredOk ? "全部必要检查通过" : "存在失败的必要检查"} · ${displayPath(path.join(outDir, "checks.json"), repo.root)}`);
  return requiredOk && !modifiedAfter.length && !postUnexpected.length ? EXIT_OK : EXIT_FAIL;
}

/** MISSING_TARGET_PATTERNS：检查日志里这些话说明“目标不存在”，而不是“行为不对”。只改写 baseline 的说明文字。 */
const MISSING_TARGET_PATTERNS = [
  "Could not find", "no such file", "ENOENT", "no tests? (?:found|ran|collected)",
  "No test files found", "collected 0 items", "is not recognized", "cannot find module",
  "找不到", "不存在",
].map((pattern) => compilePy(pattern, FLAG_IGNORECASE));

/** _looks_like_missing_target：基线上失败的检查，其日志是否只是在说“文件 / 用例不存在”。 */
function looksLikeMissingTarget(outDir: string, record: PyDict): boolean {
  let text: string;
  try {
    text = pyReadTextReplace(path.join(outDir, `${pyStrValue(record.get("id") ?? null)}.log`));
  } catch (error) {
    if (error instanceof PyOSError) return false;
    throw error;
  }
  return MISSING_TARGET_PATTERNS.some((pattern) => pattern.search(text) !== null);
}

/** _load_fixed_contract_pair 那一步的 `except (OSError, ValueError, UnicodeDecodeError)`。 */
function fixedPairError(error: unknown): boolean {
  if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError || error instanceof ProtocolError) return true;
  if (error instanceof PyJsonError) return error.kind !== "RecursionError";
  return error instanceof PyCrash && (error.kind === "ValueError" || error.kind === "UnicodeDecodeError");
}

export async function cmdBaseline(args: BaselineArgs, out: PyOut, ctx: PlanContext): Promise<number> {
  const repo = Repo.discover(args.repo);
  const key = planKeyFromArg(repo, args.plan_key);
  const [validated, errors, warnings] = validatePlan(repo, key, ctx);
  printMessages(out, errors, warnings);
  if (errors.length || validated === null) throw new DispatchError("合同校验失败，无法运行基线检查。", EXIT_USAGE);
  // 校验之后重新读一次、按这份字节再校验：两步之间被换掉的合同不能变成一份没人审过的、照样运行的合同
  let contract: PyDict | null;
  let frozenErrors: string[];
  try {
    const frozenMd = pyReadBytes(path.join(repo.plansDir, `${key}.md`));
    const frozenJson = pyReadBytes(path.join(repo.plansDir, `${key}.json`));
    [contract, frozenErrors] = loadFixedContractPair(repo, key, frozenMd, frozenJson, pyDecodeUtf8(frozenMd), [], ctx);
  } catch (error) {
    if (!fixedPairError(error)) throw error;
    throw new DispatchError(`基线合同固定字节无法重新校验：${(error as Error).message}`, EXIT_DRIFT);
  }
  if (frozenErrors.length || contract === null) throw new DispatchError(`基线合同固定字节未通过校验：${frozenErrors.join("；")}`, EXIT_DRIFT);
  if (!pyEq(contract, validated)) throw new DispatchError("合同在校验后发生变化，拒绝运行基线检查。", EXIT_DRIFT);
  const checks = selectChecks(contract.get("checks") as PyDict[], args.only);
  const config = repoConfig(repo);
  const [env, removed] = childEnv(config);
  const grace = graceOf(config);
  const taskId = pyStrValue(contract.get("task_id") as PyValue);
  const outRoot = path.join(repo.runsDir, taskId, "baseline");
  pathMkdir(outRoot, true, true);
  const number = nextNumber(outRoot);
  const outDir = path.join(outRoot, pad2(number));
  pathMkdir(outDir, false, false);
  const root = worktreeRoot(repo, config);
  pathMkdir(root, true, true);
  const workspace = pyResolve(purePathStr(pyMkdtemp(`${firstPoints(path.basename(repo.root), 16)}-${firstPoints(taskId, 24)}-baseline-`, root)));
  const base = pyStrValue(contract.get("base_sha") as PyValue);
  const results: PyDict[] = [];
  const started = utcNow();
  try {
    gitChecked(["worktree", "add", "--detach", workspace, base], repo.root);
    for (const item of contract.get("setup") as PyDict[]) {
      const record = await runCommandItem(item, workspace, env, outDir, grace);
      if (!pyTruthy(record.get("passed") as PyValue)) {
        throw new DispatchError(`基线副本的 setup ${pyStrValue(item.get("id") as PyValue)} 失败：${pyStrValue(record.get("reason") ?? null)}`);
      }
    }
    for (const item of checks) {
      out.print(`BASELINE ${pyStrValue(item.get("id") as PyValue)} ...`, { flush: true });
      results.push(await runCommandItem(item, workspace, env, outDir, grace));
    }
  } finally {
    if (!args.keep_workspace) removeWorktree(repo, workspace);
  }
  const mismatches: PyValue[] = [];
  const rows: [string, string, string, string][] = [];
  const expectations = (contract.get("checks") as PyDict[]).map((check): [PyValue, PyValue] => [check.get("id") as PyValue, pyGet(check, "expect_on_base", "any")]);
  for (const record of results) {
    const id = record.get("id") as PyValue;
    const expect = pyStrValue(expectations.filter(([key]) => pyEq(key, id)).pop()?.[1] ?? "any");
    const passed = pyTruthy(record.get("passed") as PyValue);
    const outcome = passed ? "passed" : pyStrValue(record.get("status") as PyValue);
    let note: string;
    if (expect === "fail" && passed) {
      note = "不符：期望在基线上失败，实际已通过——这个探针区分不了修复前后";
      mismatches.push(id);
    } else if (expect === "pass" && !passed) {
      note = "不符：期望在基线上通过（回归保护），实际未通过——检查本身或基线有问题";
      mismatches.push(id);
    } else if (expect === "any" && passed) {
      note = "基线上已通过（回归保护属正常；若用来证明修复，标注 expect_on_base: fail 并改写）";
    } else {
      note = expect !== "any" ? "符合预期" : "基线上未通过（修复后应通过）";
      if (expect === "any" && looksLikeMissingTarget(outDir, record)) {
        note = "基线上未通过：输出显示找不到文件或用例——只新增测试文件的合同在基线上本就如此，属正常；有效性改用变异检查证明";
      }
    }
    rows.push([pyStrValue(id), expect, outcome, note]);
  }
  writeJson(path.join(outDir, "checks.json"), new Map<string, PyValue>([
    ["plan_key", key], ["base_sha", base], ["started_at", started], ["ended_at", utcNow()],
    ["workspace", workspace], ["workspace_kept", Boolean(args.keep_workspace)], ["env_removed", removed],
    ["mismatches", mismatches], ["results", results],
  ]), true);
  const header = ["CHECK", "EXPECT", "BASE"];
  const widths = [0, 1, 2].map((i) => Math.max(...[...rows, [...header, ""]].map((row) => pyLen(row[i] as string))));
  out.print(`${header.map((title, i) => ljust(title, widths[i] as number)).join("  ")}  NOTE`);
  for (const row of rows) out.print(`${[0, 1, 2].map((i) => ljust(row[i] as string, widths[i] as number)).join("  ")}  ${row[3]}`);
  out.print(`基线检查记录：${displayPath(path.join(outDir, "checks.json"), repo.root)}`);
  return mismatches.length ? EXIT_FAIL : EXIT_OK;
}

const BS = String.fromCharCode(92);
const VERDICT_LINE = compilePy(`^${BS}s*Verdict:${BS}s*([A-Z_]+)${BS}s*$`, FLAG_MULTILINE);

export async function cmdVerdict(args: VerdictArgs, out: PyOut, here: string): Promise<number> {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const state = getState(runDir);
  if (!REVIEWABLE_STATES.includes(state)) throw new DispatchError(`状态 ${state} 不能记录验收结论`);
  const verdict = args.verdict;
  const reviewPath = purePathStr(args.review);
  if (!isFile(reviewPath) || statSync(reviewPath).size === 0) throw new DispatchError(`找不到复审报告：${reviewPath}`, EXIT_USAGE);
  const reviewText = pyReadText(reviewPath);
  const unfilled = pySplitlines(reviewText).filter((line) => PLACEHOLDER_RE.test(line)).map(pyStrip);
  if (unfilled.length) {
    throw new DispatchError(
      `复审报告还有 ${unfilled.length} 处【待填】（review-draft 生成的骨架要填完再交），第一处：${firstPoints(unfilled[0] as string, 160)}`, EXIT_USAGE);
  }
  if (declaredVerdict(reviewText) !== verdict) throw new DispatchError(`复审报告中的 'Verdict:' 行必须恰好是 ${verdict}`, EXIT_USAGE);
  const waivers = new Map<string, PyValue>();
  for (const item of args.waive ?? []) {
    const at = item.indexOf("=");
    const gate = at < 0 ? item : item.slice(0, at);
    const reason = at < 0 ? "" : item.slice(at + 1);
    if (!(GATES as readonly string[]).includes(gate) || !pyStrip(reason)) throw new DispatchError("--waive 格式应为 G2=原因", EXIT_USAGE);
    waivers.set(gate, pyStrip(reason));
  }
  const evaluation = evaluateGates(repo, runDir, meta, contract, here);
  const gates = evaluation.get("gates") as PyDict;
  const gateInfo = (name: string, field: string): PyValue[] => (gates.get(name) as PyDict).get(field) as PyValue[];
  const failed = [...gates.keys()].filter((name) => !(gates.get(name) as PyDict).get("passed")) as string[];
  for (const gate of ["G0", "G3", "G6"]) for (const note of gateInfo(gate, "notes")) out.print(`NOTE  ${gate} ${pyStrValue(note)}`);
  if (verdict === "PASS") {
    if (failed.length) {
      for (const gate of failed) for (const problem of gateInfo(gate, "problems")) out.print(`GATE ${gate} ${pyStrValue(problem)}`);
      throw new DispatchError(`PASS 被拒绝：门禁 ${failed.join(", ")} 未通过。修正后重新验收，或按授权使用 ACCEPTED_WITH_EXCEPTION 并逐项豁免。`, EXIT_FAIL);
    }
    if (waivers.size) throw new DispatchError("PASS 不接受豁免；有豁免时使用 ACCEPTED_WITH_EXCEPTION", EXIT_USAGE);
  } else if (verdict === "ACCEPTED_WITH_EXCEPTION") {
    const missing = failed.filter((gate) => !waivers.has(gate));
    if (missing.length) throw new DispatchError(`以下失败门禁没有豁免理由：${missing.join(", ")}`, EXIT_USAGE);
    if (!waivers.size || !args.decided_by) throw new DispatchError("ACCEPTED_WITH_EXCEPTION 需要至少一项 --waive 与 --decided-by", EXIT_USAGE);
  } else if (!args.failure_class) {
    throw new DispatchError(`${verdict} 需要 --class（${FAILURE_CLASSES.join(", ")}）`, EXIT_USAGE);
  }
  const verdictDir = path.join(runDir, "verdicts");
  pathMkdir(verdictDir, false, true);
  const number = nextNumber(verdictDir);
  const reviewCopy = path.join(verdictDir, `${pad2(number)}.md`);
  copyfile(reviewPath, reviewCopy);
  const record: PyDict = new Map<string, PyValue>([
    ["number", number], ["verdict", verdict], ["failure_class", args.failure_class], ["decided_by", args.decided_by],
    ["waivers", waivers], ["human_minutes", args.human_minutes], ["note", args.note], ["review_source", reviewPath],
    ["review_sha256", sha256File(reviewCopy)], ["candidate_tree", pyGet(readJsonOr(path.join(runDir, "candidate.json"), new Map()), "tree")],
    ["gates", gates], ["state_before", state], ["recorded_at", utcNow()],
  ]);
  const recordPath = path.join(verdictDir, `${pad2(number)}.json`);
  writeJson(recordPath, record, true);
  setState(runDir, verdict, [["verdict_no", number], ["failure_class", args.failure_class]]);
  out.print(`${verdict} 已记录（${displayPath(recordPath, repo.root)}）。`);
  if (failed.length && verdict !== "PASS") out.print(`未通过的门禁：${failed.join(", ")}`);
  return EXIT_OK;
}

/**
 * cmd_verdict 的 Verdict 行（re.M，“Verdict:”与组的两边都允许空白）的第 1 组：sre 的移植不记捕获组，取整段匹配之后去掉
 * “Verdict:”之前的部分与两头的空白（组里没有空白）。
 */
function declaredVerdict(text: string): string | null {
  const match = VERDICT_LINE.search(text);
  if (match === null) return null;
  return pyStrip(match.group.slice(match.group.indexOf("Verdict:") + "Verdict:".length));
}

/** shutil.copyfile：只复制内容。 */
function copyfile(source: string, target: string): void {
  let data: Buffer;
  try {
    data = readFileSync(source);
  } catch (error) {
    throw pyOSErrorOf(error, source) ?? error;
  }
  try {
    writeFileSync(target, data);
  } catch (error) {
    throw pyOSErrorOf(error, target) ?? error;
  }
}
