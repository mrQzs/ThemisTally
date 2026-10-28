// integrate（迁移第 ④b8b 片）：验证后落地（2.8.0）。建分支 → 在对象库里预演合并到当前分支末端 → 干净副本上跑合同检查
// （或沿用最近一次 check --fresh，2.10.0）→ 快进 → 标记 INTEGRATED → 清理。
//   - 主工作区从头到尾不停在 cherry-pick 的中间状态：合并用 git merge-tree 预演，检查在临时 worktree 里跑（末端 + 候选改动
//     未暂存，与 check --fresh 同一布局），主工作区只做最后一步 git merge --ff-only，有会被覆盖的本地改动时 git 拒绝。
//   - 落地要合同 integration 含 merge（建分支要 local_branch）；没有 merge 时做到验证为止，建好提交并打印落地命令，退出码 3。
//   - 尾注规则在 config 包，由 cli 交进来（同 branch）。
import { readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { type PyOut, pyFloatOf, pyGet, pyIntOf, pyItem, pyIter, pyJoinStrings, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, pyDecodeUtf8, pyDecodeUtf8Replace } from "@themis/base/pyio";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { PyWinError, pathMkdir } from "@themis/base/pyos";
import { displayPath, purePathStr, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, isDigitChar, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pyMkdtemp } from "@themis/base/pytempfile";
import { pyEq } from "@themis/base/pyvalue";
import { cmdCleanup } from "./attempt-commands.ts";
import { type BranchArgs, type TrailerRules, branchTrailers, candidateCommit } from "./branch.ts";
import { firstPoints, headOf, nextNumber, pad3, runCommandItem, worktreeRoot } from "./command-runner.ts";
import { SHA_RE } from "./contract.ts";
import { gitIdentityProblem } from "./doctor.ts";
import { PASSING_VERDICTS, artifactMatchers, loadAttempt, logEvent, removeWorktree, setState, splitExtras, writeJson } from "./evidence.ts";
import { plannerAttemptPublicationErrors, requireAuthorizedAction, verifyInputs } from "./gates.ts";
import { snapshotTree, treeDrift } from "./gitops.ts";
import { plannerPaths, repoConfig } from "./kernel-config.ts";
import { compilePatterns, matches } from "./patterns.ts";
import { childEnv } from "./pi-cli.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, git, gitChecked, gitText, readJsonOr } from "./repo.ts";
import { getState, latestVerdict, resolveRunDir, taskAttempts } from "./status.ts";

const WIN = process.platform === "win32";
const s = pyStrValue;
const head12 = (text: string): string => firstPoints(text, 12);

export interface IntegrateArgs extends Pick<BranchArgs, "repo" | "run_dir" | "name" | "trailer" | "no_config_trailers"> {
  readonly dry_run: boolean;
  readonly skip: string | null;
  readonly reason: string | null;
  readonly recheck: boolean;
  readonly keep_worktree: boolean;
  readonly keep_workspace: boolean;
  readonly while_running: boolean;
}

/** 沿用的 check --fresh：哪次记录、几时结束、只差的规划路径、那次的结果。 */
interface Reuse {
  readonly record: string;
  readonly endedAt: PyValue;
  readonly plannerPaths: string[];
  readonly results: PyDict[];
}

/** cmd_integrate：落地返回 0；冲突、检查没过、末端变了、快进被拒返回 1；验证通过而合同没授权 merge 返回 3。 */
export async function cmdIntegrate(args: IntegrateArgs, out: PyOut, rules: TrailerRules): Promise<number> {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const publication = plannerAttemptPublicationErrors(repo, runDir, contract);
  if (publication.length) throw new DispatchError(`planner-v2 发布门禁拒绝集成：${publication.join("；")}`, EXIT_BLOCKED);
  const problems = verifyInputs(runDir, meta, repo);
  if (problems.length) throw new DispatchError(`输入不一致（G0）：${problems.join("；")}`);
  requireAuthorizedAction(contract, "local_branch", true);
  const mayLand = (pyItem(pyItem(contract, "authorization"), "integration") as PyValue[]).includes("merge");
  const state = getState(runDir);
  const verdict = pyGet(latestVerdict(runDir), "verdict");
  if (state === "INTEGRATED") {
    throw new DispatchError(`attempt 已集成（ref ${s(pyGet(readJsonOr(path.join(runDir, "state.json"), new Map()), "ref"))}）`, EXIT_USAGE);
  }
  if (!(typeof verdict === "string" && PASSING_VERDICTS.includes(verdict)) || !PASSING_VERDICTS.includes(state)) {
    throw new DispatchError(`最新结论为 ${s(verdict)}（状态 ${state}）：只有 PASS / ACCEPTED_WITH_EXCEPTION 可以 integrate；返工或` +
      "规划端补完的候选照旧 branch --rework、手工集成，再 mark SUPERSEDED", EXIT_BLOCKED);
  }
  const checks = pyIter(pyItem(contract, "checks")) as PyDict[];
  const skip = checkSkips(args, checks);
  const symbolic = git(["symbolic-ref", "-q", "HEAD"], repo.root);
  if (symbolic.status !== 0) throw new DispatchError("主工作区是游离 HEAD：integrate 只落到当前分支，先切到要集成的分支", EXIT_USAGE);
  const target = pyStrip(pyDecodeUtf8Replace(symbolic.stdout));
  const head = gitText(["rev-parse", "HEAD"], repo.root);
  if (mayLand && !args.dry_run && !args.while_running) {
    const running = runningAttempts(repo);
    if (running.length) {
      throw new DispatchError(`有 attempt 正在运行或收集：${running.slice(0, 5).join(", ")}。落地会改动主工作区，它们的复审会把这次改动列为主工作区` +
        "变化；等它们结束再集成（调度器已退出的先 collect --recover），或加 --while-running 明确接受", EXIT_BLOCKED);
    }
  }
  const identity = gitIdentityProblem(repo.root);
  if (identity) throw new DispatchError(identity);
  const trailers = branchTrailers(repo, args, rules);
  const branch = candidateCommit(repo, runDir, meta, verdict, { name: args.name, rework: false, trailers, createRef: !args.dry_run, reuse: true });
  const branchName = branch.get("branch") ?? null;
  const candidate = branch.get("commit") as string;
  if (pyTruthy(branchName)) out.print(`分支 ${s(branchName)} → ${head12(candidate)}${branch.get("reused") ? "（复用已有分支）" : ""}`);
  const base = pyItem(meta, "base_sha") as string;
  if (git(["merge-base", "--is-ancestor", base, head], repo.root).status !== 0) {
    out.print(`NOTE  基线 ${head12(base)} 不在当前分支的历史里：按“基线→候选”的改动挑入当前末端（等同 cherry-pick）`);
  }
  const integrations = path.join(runDir, "integrations");
  pathMkdir(integrations, false, true);
  const number = nextNumber(integrations);
  const outDir = path.join(integrations, String(number).padStart(2, "0"));
  pathMkdir(outDir, false, false);
  const record = new Map<string, PyValue>([
    ["run", number], ["started_at", utcNow()], ["target", target], ["head", head], ["base_sha", base], ["branch", branchName],
    ["candidate_commit", candidate], ["candidate_tree", branch.get("tree") ?? null], ["merge_authorized", mayLand], ["dry_run", Boolean(args.dry_run)],
    ["skipped_checks", skip], ["skip_reason", skip.length ? args.reason : null], ["landed", false],
  ]);
  const finish = (outcome: string, extra: [string, PyValue][] = []): void => {
    for (const [key, value] of [...extra, ["outcome", outcome], ["ended_at", utcNow()]] as [string, PyValue][]) record.set(key, value);
    writeJson(path.join(outDir, "integration.json"), record, true);
    logEvent(runDir, "integration", [["run", number], ["outcome", outcome], ["head", head], ["commit", record.get("commit") ?? null], ["target", target]]);
  };
  const [mergedTree, conflicts] = mergePreview(repo, base, head, candidate);
  if (mergedTree === null) {
    finish("conflict", [["conflicts", conflicts]]);
    out.print(`CONFLICT 候选与当前末端 ${head12(head)} 冲突：${conflicts.slice(0, 20).join(", ")}`);
    out.print(`什么都没落地${pyTruthy(branchName) ? `（只多了本地分支 ${s(branchName)}）` : ""}。以当前末端为基线出返工合同，或规划端手工合并后 mark SUPERSEDED。`);
    return EXIT_FAIL;
  }
  record.set("merged_tree", mergedTree);
  const config = repoConfig(repo);
  const [env, removed] = childEnv(config);
  const grace = pyFloatOf(pyGet(config, "kill_grace_seconds", 15n));
  const artifacts = artifactMatchers(config);
  let reuse: Reuse | null = null;
  let reuseReason: string;
  if (args.recheck) reuseReason = "加了 --recheck";
  else if (skip.length) reuseReason = "加了 --skip：豁免只在重跑时成立";
  else [reuse, reuseReason] = freshCheckReuse(repo, runDir, checks, branch.get("tree") as string, mergedTree);
  // 照 Python 往同一个列表里追加：验证中途出错时，记录里有已经跑完的那几项
  const results: PyDict[] = [];
  let workspace: string | null = null;
  let modified: string[] = [];
  let unexpected: string[] = [];
  if (reuse !== null) {
    // 2.10.0：要落地的树与最近一次 check --fresh 测过的树只差规划文件，沿用那次的结果，不再把全量重跑一遍
    const from = reuse.record;
    results.push(...reuse.results.map((item) => new Map([...item, ["reused_from", from]])));
    record.set("checks_reused", new Map<string, PyValue>([["record", from], ["ended_at", reuse.endedAt], ["planner_paths", reuse.plannerPaths]]));
    const only = reuse.plannerPaths.length ? `只差规划文件 ${reuse.plannerPaths.slice(0, 5).join("、")}` : "完全相同";
    out.print(`检查沿用 ${from}（check --fresh，${pyTruthy(reuse.endedAt) ? s(reuse.endedAt) : "时间未知"} 结束）：当前末端 + 候选与那次测过的树${only}`, { flush: true });
  } else {
    out.print(`NOTE  在当前末端上重跑检查：${reuseReason}`, { flush: true });
    const root = worktreeRoot(repo, config);
    pathMkdir(root, true, true);
    const prefix = `${firstPoints(path.basename(repo.root), 16)}-${headOf(pyItem(meta, "task_id"), 24)}-a${pad3(pyIntOf(pyItem(meta, "attempt_no"), "%d format"))}-integrate-`;
    workspace = pyResolve(purePathStr(pyMkdtemp(prefix, root)));
    const verified = workspace;
    try {
      await verifyOnTip(repo, verified, head, mergedTree, meta, contract, checks, skip, args.reason, outDir, env, grace, out, results);
      const after = snapshotTree(verified, head, outDir, "integrate-after", pyGet(meta, "git_autocrlf"));
      const drift = treeDrift(verified, mergedTree, after);
      unexpected = splitExtras(drift.added, artifacts)[1];
      modified = drift.modified;
    } catch (error) {
      if (!(error instanceof DispatchError || error instanceof PyOSError || error instanceof PyWinError)) throw error;
      finish("workspace_failed", [["error", error.message], ["results", results]]);
      throw new DispatchError(`无法在当前末端上验证（什么都没落地）：${error.message}`);
    } finally {
      if (!args.keep_workspace) removeWorktree(repo, verified);
    }
  }
  const ran = results.filter((item) => pyItem(item, "status") !== "skipped");
  const checksOk = ran.every((item) => !pyTruthy(pyGet(item, "required", true)) || pyTruthy(pyItem(item, "passed")));
  const passed = checksOk && !modified.length && !unexpected.length;
  const shown = `${ran.filter((item) => pyTruthy(pyItem(item, "passed"))).length}/${ran.length}${skip.length ? `，豁免 ${skip.join(",")}` : ""}` +
    `${reuse ? `，沿用 ${reuse.record}` : ""}`;
  for (const [key, value] of [
    ["results", results], ["checks_passed", checksOk], ["modified_by_checks", modified], ["unexpected_files_by_checks", unexpected.slice(0, 200)],
    ["workspace", workspace], ["workspace_kept", Boolean(args.keep_workspace && workspace)], ["env_removed", removed],
  ] as [string, PyValue][]) record.set(key, value);
  const shownRecord = displayPath(path.join(outDir, "integration.json"), repo.root);
  if (!passed) {
    finish("checks_failed");
    if (modified.length) out.print(`WARN  检查修改了文件：${modified.slice(0, 10).join(", ")}`);
    if (unexpected.length) out.print(`WARN  检查产生了新文件：${unexpected.slice(0, 10).join(", ")}（缓存或报告类加入 .gitignore 或 check_artifact_patterns）`);
    out.print(`当前末端 ${head12(head)} + 候选上的检查没有全部通过（${shown}）：什么都没落地 · ${shownRecord}`);
    return EXIT_FAIL;
  }
  if (args.dry_run) {
    finish("verified");
    out.print(`验证通过（dry-run，没有建提交、没有落地）：当前末端 ${head12(head)} + 候选，检查 ${shown} · ${shownRecord}`);
    return EXIT_OK;
  }
  const messageFile = path.join(outDir, "message.txt");
  writeFileSync(messageFile, commitMessageBytes(repo, candidate));
  const commit = gitText(["commit-tree", mergedTree, "-p", head, "-F", messageFile], repo.root);
  record.set("commit", commit);
  const shownRun = displayPath(runDir, repo.root);
  if (!mayLand) {
    finish("verified_not_authorized");
    out.print(`验证通过（检查 ${shown}），但合同 integration 没有 merge：没有落地。提交 ${head12(commit)} 已建好，落地命令：`);
    out.print(`  git merge --ff-only ${commit}`);
    out.print(`  bash scripts/dispatch-pi.sh mark ${shownRun} INTEGRATED --ref ${commit}`);
    return EXIT_BLOCKED;
  }
  const nowTarget = pyStrip(pyDecodeUtf8Replace(git(["symbolic-ref", "-q", "HEAD"], repo.root).stdout));
  const nowHead = pyStrip(pyDecodeUtf8(git(["rev-parse", "--verify", "--quiet", "HEAD"], repo.root).stdout));
  if (nowTarget !== target || nowHead !== head) {
    finish("head_moved", [["now_head", nowHead], ["now_target", nowTarget]]);
    out.print(`分支末端在验证期间变了（${head12(head)} → ${head12(nowHead || "?")}）：什么都没落地，重跑 integrate。`);
    return EXIT_FAIL;
  }
  const ff = git(["merge", "--ff-only", commit], repo.root);
  if (ff.status !== 0) {
    const error = pyStrip(pyDecodeUtf8Replace(ff.stderr) || pyDecodeUtf8Replace(ff.stdout));
    finish("ff_refused", [["error", tailPoints(error, 2000)]]);
    out.print(`快进被拒：${tailPoints(error, 600)}`);
    out.print(`什么都没落地。提交 ${head12(commit)} 已建好：处理主工作区（例如只差换行符的文件按约定统一）之后 git merge --ff-only ${commit}，` +
      `再 mark ${shownRun} INTEGRATED --ref ${commit}`);
    return EXIT_FAIL;
  }
  record.set("landed", true);
  finish("landed");
  setState(runDir, "INTEGRATED", [["ref", commit], ["reason", `integrate ${String(number).padStart(2, "0")}`], ["previous_state", state]]);
  const shownTarget = target.startsWith("refs/heads/") ? target.slice("refs/heads/".length) : target;
  out.print(`已集成 ${displayPath(runDir, repo.runsDir)} → ${shownTarget} ${head12(commit)}（基于 ${head12(head)}，检查 ${shown}，分支 ${s(branchName)}）`);
  if (!args.keep_worktree) {
    try {
      cmdCleanup({ repo: args.repo, run_dir: runDir, force: false }, out);
    } catch (error) {
      if (!(error instanceof DispatchError)) throw error;
      out.print(`NOTE  集成已完成；attempt 的 worktree 没有清理：${error.message}`);
    }
  }
  return EXIT_OK;
}

/** --skip 与 --reason：去空白、去空项；不是合同里的检查报“未知检查”（按码点排序），有 --skip 就要有 --reason。 */
function checkSkips(args: IntegrateArgs, checks: readonly PyDict[]): string[] {
  const skip = (args.skip ?? "").split(",").map(pyStrip).filter(Boolean);
  const ids = checks.map((item) => pyItem(item, "id"));
  const unknown = [...new Set(skip)].filter((item) => !ids.some((id) => pyEq(id, item))).sort(cmpCodePoints);
  if (unknown.length) throw new DispatchError(`未知检查：${unknown.join(", ")}`, EXIT_USAGE);
  if (skip.length && !pyStrip(args.reason ?? "")) {
    throw new DispatchError("--skip 需要 --reason：写明这项检查为什么在当前末端上不成立（例如只对基线成立）", EXIT_USAGE);
  }
  return skip;
}

/** 在验证副本里：末端 + 合并结果的改动（未暂存），setup，再逐项跑检查（豁免的记 skipped），结果追加进 results。 */
async function verifyOnTip(
  repo: Repo, workspace: string, head: string, mergedTree: string, meta: PyValue, contract: PyDict, checks: readonly PyDict[], skip: readonly string[],
  reason: string | null, outDir: string, env: ReadonlyMap<string, string>, grace: number, out: PyOut, results: PyDict[],
): Promise<void> {
  gitChecked(["worktree", "add", "--detach", workspace, head], repo.root);
  const patch = path.join(outDir, "integration.patch");
  writeFileSync(patch, gitChecked(["diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--full-index", "--src-prefix=a/", "--dst-prefix=b/",
    head, mergedTree], repo.root).stdout);
  if (statSync(patch).size > 0) gitChecked(["apply", "--binary", "--whitespace=nowarn", patch], workspace);
  const autocrlf = pyGet(meta, "git_autocrlf");
  if (snapshotTree(workspace, head, outDir, "integrate", autocrlf) !== mergedTree) throw new DispatchError(`验证副本与合并结果不一致：${workspace}`);
  const setup = pyIter(pyItem(contract, "setup")) as PyDict[];
  if (setup.length) {
    const setupDir = path.join(outDir, "setup");
    pathMkdir(setupDir, false, false);
    for (const item of setup) {
      const result = await runCommandItem(item, workspace, env, setupDir, grace);
      if (!result.get("passed")) throw new DispatchError(`验证副本的 setup ${s(pyItem(item, "id"))} 失败：${s(result.get("reason") ?? null)}`);
    }
    if (snapshotTree(workspace, head, outDir, "integrate-setup", autocrlf) !== mergedTree) {
      throw new DispatchError("setup 改动了验证副本中的文件或产生了未忽略的新文件");
    }
  }
  for (const item of checks) {
    const id = pyItem(item, "id");
    if (typeof id === "string" && skip.includes(id)) {
      results.push(new Map<string, PyValue>([["id", id], ["required", pyGet(item, "required", true)], ["status", "skipped"], ["passed", null], ["reason", reason]]));
      out.print(`CHECK ${id} skipped（${s(reason)}）`, { flush: true });
      continue;
    }
    out.print(`CHECK ${s(id)} ...`, { flush: true });
    const result = await runCommandItem(item, workspace, env, outDir, grace);
    results.push(result);
    out.print(`CHECK ${s(id)} ${s(result.get("status") ?? null)} ${pyTruthy(result.get("reason") ?? null) ? s(result.get("reason") as PyValue) : ""}`, { flush: true });
  }
}

/** _running_attempts：正在运行或收集的 attempt（落地会改动主工作区，它们的复审会把这次改动列为主工作区变化）。 */
function runningAttempts(repo: Repo): string[] {
  const found: string[] = [];
  for (const task of listDirNames(repo.runsDir).sort(cmpCodePoints)) {
    for (const attempt of taskAttempts(repo, task)) {
      if (["RUNNING", "COLLECTING"].includes(getState(attempt))) found.push(displayPath(attempt, repo.runsDir));
    }
  }
  return found;
}

/** _merge_preview：在对象库里预演“基线→候选”合并到 head，不碰任何工作区。返回（合并后的树或 null, 冲突文件）。 */
function mergePreview(repo: Repo, base: string, head: string, commit: string): [string | null, string[]] {
  const proc = git(["merge-tree", "--write-tree", "--name-only", `--merge-base=${base}`, head, commit], repo.root);
  const lines = pySplitlines(pyDecodeUtf8Replace(proc.stdout));
  if (![0, 1].includes(proc.status) || !lines.length || !SHA_RE.test(pyStrip(lines[0] as string))) {
    throw new DispatchError(`git merge-tree --write-tree 失败（需要 Git 2.40 以上）：${pyStrip(pyDecodeUtf8Replace(proc.stderr)) || proc.status}`);
  }
  if (proc.status === 0) return [pyStrip(lines[0] as string), []];
  const conflicts: string[] = [];
  for (const line of lines.slice(1)) {
    if (!pyStrip(line)) break;
    conflicts.push(pyStrip(line));
  }
  return [null, [...new Set(conflicts)].sort(cmpCodePoints)];
}

/** _commit_message_bytes：提交说明的原始字节（cat-file，不经 log 的格式化，末尾换行不多不少）。 */
function commitMessageBytes(repo: Repo, commit: string): Buffer {
  const raw = gitChecked(["cat-file", "commit", commit], repo.root).stdout;
  const at = raw.indexOf(Buffer.from([10, 10]));
  return at < 0 ? Buffer.alloc(0) : raw.subarray(at + 2);
}

/**
 * _fresh_check_reuse（2.10.0）：能否沿用最近一次 check --fresh 的结果。那次记录要干净：没有中止，测的是同一棵候选树，合同的
 * 每条检查都跑过，必要检查全过，没有改动候选文件或产生新文件；合并后的树相对候选树只能在规划路径下有差异。返回（沿用信息, 不能沿用的原因）。
 */
function freshCheckReuse(repo: Repo, runDir: string, checks: readonly PyDict[], candidateTree: string, mergedTree: string): [Reuse | null, string] {
  const root = path.join(runDir, "checks");
  // sorted(…, key=int(name), reverse=True)：倒序但相等的键保持原来的次序
  const numbered = listDirNames(root).filter((name) => name.length > 0 && codePoints(name).every(isDigitChar))
    .map((name, index) => ({ name, index, value: pyIntOf(name, "int()") }))
    .sort((a, b) => (a.value === b.value ? a.index - b.index : a.value < b.value ? 1 : -1));
  let latest: [string, PyDict] | null = null;
  for (const { name } of numbered) {
    const data = readJsonOr(path.join(root, name, "checks.json"), null);
    if (!(data instanceof Map)) continue;
    // 2.10.0 之前中止的记录没有 mode：建不起干净副本的那种只会出自 --fresh
    if (pyEq(pyGet(data, "mode"), "fresh") || (!pyTruthy(pyGet(data, "mode")) && pyEq(pyGet(data, "aborted"), "fresh_workspace_failed"))) {
      latest = [name, data];
      break;
    }
  }
  if (latest === null) return [null, "没有 check --fresh 的记录"];
  const [name, data] = latest;
  const label = `checks/${name}`;
  if (pyTruthy(pyGet(data, "aborted"))) return [null, `最近一次 check --fresh（${label}）中止了：${s(pyItem(data, "aborted"))}`];
  if (!pyEq(pyGet(data, "candidate_tree"), candidateTree)) return [null, `${label} 测的不是这个候选树`];
  const results = pyIter(pyTruthy(pyGet(data, "results")) ? pyGet(data, "results") : []).filter((item): item is PyDict => item instanceof Map);
  const ran = results.map((item) => pyGet(item, "id"));
  const missing = checks.map((item) => pyItem(item, "id")).filter((id) => !ran.some((value) => pyEq(value, id)));
  if (missing.length) return [null, `${label} 没有跑 ${pyJoinStrings(", ", missing)}`];
  const failed = results.filter((item) => pyTruthy(pyGet(item, "required", true)) && !pyTruthy(pyGet(item, "passed"))).map((item) => s(pyGet(item, "id")));
  if (failed.length || !pyTruthy(pyGet(data, "all_required_passed"))) return [null, `${label} 的必要检查没有全过（${failed.join(", ") || "all_required_passed 为假"}）`];
  if (pyTruthy(pyGet(data, "modified_by_checks")) || pyTruthy(pyGet(data, "unexpected_files_by_checks"))) return [null, `${label} 的检查改动了候选文件或产生了新文件`];
  let extra: string[] = [];
  if (mergedTree !== candidateTree) {
    const raw = gitChecked(["diff-tree", "-r", "--no-renames", "--name-only", "-z", candidateTree, mergedTree], repo.root).stdout;
    extra = pyDecodeUtf8Replace(raw).split(String.fromCharCode(0)).filter(Boolean);
    const compiled = compilePatterns(plannerPaths(repoConfig(repo)), WIN);
    const outside = extra.filter((file) => !matches(compiled, file));
    if (outside.length) {
      return [null, `当前末端相对候选多了规划路径之外的改动：${outside.slice(0, 5).join("、")}${outside.length > 5 ? ` 等 ${outside.length} 个` : ""}`];
    }
  }
  return [{ record: label, endedAt: pyGet(data, "ended_at"), plannerPaths: extra.slice(0, 200), results }, ""];
}

/** text[-count:]（按码点）。 */
const tailPoints = (text: string, count: number): string => codePoints(text).slice(-count).join("");

/** 目录下的子目录名，照 Path.iterdir 的次序（是目录才列，不是目录时为空）。 */
function listDirNames(dir: string): string[] {
  if (!isDir(dir)) return [];
  return readdirSync(dir).filter((name) => isDir(path.join(dir, name)));
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
