// branch（迁移第 ④b8a 片）：给验收通过的候选建本地分支（不推送）。候选提交的父提交是基线，提交说明带 attempt、执行模型、
// 候选树与结论，再接仓库级与命令行给的尾注。candidateCommit 由 branch 与 integrate 共用。
//   - 尾注的校验在 config 包（validate.ts 的 commit_trailers 与 valid_trailer），由 cli 交进来：本包不依赖 config。
//   - 授权、结论与 Git 身份由调用方先核对；之后才会按补丁重建候选树、写 Git 对象、建分支。
import { writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyGet, pyItem, pyPercentD, pyPlus, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyDecodeUtf8, pyDecodeUtf8Replace } from "@themis/base/pyio";
import { type PyDict, type PyValue, encodeUtf8 } from "@themis/base/pyjson";
import { pyStrip } from "@themis/base/pyre";
import { branchSubject } from "./contract.ts";
import { gitIdentityProblem } from "./doctor.ts";
import { PASSING_VERDICTS, loadAttempt, logEvent, writeJson } from "./evidence.ts";
import { plannerAttemptPublicationErrors, requireAuthorizedAction, verifyInputs } from "./gates.ts";
import { treeFromPatch } from "./gitops.ts";
import { repoConfig } from "./kernel-config.ts";
import { attemptExecutor } from "./metrics.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_OK, EXIT_USAGE, Repo, git, gitChecked, gitText, readJsonOr } from "./repo.ts";
import { latestVerdict, resolveRunDir } from "./status.ts";

const LF = String.fromCharCode(10);
const BT = String.fromCharCode(96);

export interface BranchArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly name: string | null;
  readonly rework: boolean;
  readonly trailer: readonly string[];
  readonly no_config_trailers: boolean;
}

/** config 包的尾注规则：commit_trailers（取配置里的，不合格报用法错误）与 valid_trailer。 */
export interface TrailerRules {
  readonly commitTrailers: (config: PyDict) => string[];
  readonly validTrailer: (value: PyValue) => boolean;
}

/** cmd_branch：只给最新结论是 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）的候选建分支。 */
export function cmdBranch(args: BranchArgs, out: PyOut, rules: TrailerRules): number {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const publication = plannerAttemptPublicationErrors(repo, runDir, contract);
  if (publication.length) throw new DispatchError(`planner-v2 发布门禁拒绝创建分支：${publication.join("；")}`, EXIT_BLOCKED);
  const problems = verifyInputs(runDir, meta, repo);
  if (problems.length) throw new DispatchError(`输入不一致（G0）：${problems.join("；")}`);
  requireAuthorizedAction(contract, "local_branch", true);
  const verdict = pyGet(latestVerdict(runDir), "verdict");
  const passing = typeof verdict === "string" && PASSING_VERDICTS.includes(verdict);
  if (!passing && !(args.rework && verdict === "REVISE")) {
    throw new DispatchError(`最新结论为 ${pyStrValue(verdict)}：只有 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）可以建分支。`);
  }
  const identity = gitIdentityProblem(repo.root);
  if (identity) throw new DispatchError(identity);
  const trailers = branchTrailers(repo, args, rules);
  const record = candidateCommit(repo, runDir, meta, verdict, { name: args.name, rework: Boolean(args.rework), trailers });
  const [name, commit] = [record.get("branch") as string, record.get("commit") as string];
  out.print(`已创建本地分支 ${name} → ${commit}（未推送）。`);
  out.print(`commit=${commit} branch=${name}`);
  if (args.rework) {
    out.print(`返工合同可把 base_sha 设为 ${commit}，从该候选继续。`);
  } else {
    const head = gitText(["rev-parse", "HEAD"], repo.root);
    if (head === pyItem(meta, "base_sha")) {
      out.print(`集成：HEAD 仍是基线，可以 git merge --ff-only ${name}；或用 integrate 在当前末端上验证后落地（2.8.0）`);
    } else {
      out.print(`集成：HEAD（${head.slice(0, 12)}）已比基线前进，用 integrate 在当前末端上验证后落地（2.8.0），` +
        `或 git cherry-pick ${commit.slice(0, 12)}（父提交是基线，不能 ff-only）`);
    }
  }
  return EXIT_OK;
}

/** _branch_trailers：dispatch.config.json 的 commit_trailers（--no-config-trailers 去掉，也就不读配置）加上 --trailer。 */
export function branchTrailers(repo: Repo, args: Pick<BranchArgs, "trailer" | "no_config_trailers">, rules: TrailerRules): string[] {
  const trailers = args.no_config_trailers ? [] : rules.commitTrailers(repoConfig(repo));
  for (const extra of args.trailer ?? []) {
    if (!rules.validTrailer(extra)) {
      throw new DispatchError(`--trailer 必须是单行 ${BT}Key: value${BT}，不能含回车、换行等控制字符：${pyRepr(extra)}`, EXIT_USAGE);
    }
    trailers.push(extra);
  }
  return trailers;
}

export interface CandidateCommitOptions {
  readonly name: string | null;
  readonly rework: boolean;
  readonly trailers: readonly string[];
  /** 建本地分支并留记录（integrate 的 --dry-run 只要提交）。 */
  readonly createRef?: boolean;
  /** 同名分支已指向这个候选（树相同、父提交是基线）时直接复用。 */
  readonly reuse?: boolean;
}

/**
 * _candidate_commit：按候选树建提交（父提交是基线），createRef 时再建本地分支、写 branch-<名字>.json、记 branch_created。
 * meta 的各项照 Python 用到时才取（缺键时报的 KeyError 相同）。
 */
export function candidateCommit(repo: Repo, runDir: string, meta: PyValue, verdict: PyValue, options: CandidateCommitOptions): PyDict {
  const createRef = options.createRef ?? true;
  const baseSha = (): string => pyItem(meta, "base_sha") as string;
  const tree = pyGet(readJsonOr(path.join(runDir, "candidate.json"), new Map()), "tree");
  if (!pyTruthy(tree)) throw new DispatchError("缺少候选记录");
  if (git(["cat-file", "-e", pyPlus(tree, "^{tree}") as string], repo.root).status !== 0) {
    const rebuilt = treeFromPatch(repo.root, baseSha(), path.join(runDir, "candidate.patch"), runDir, pyGet(meta, "git_autocrlf"));
    if (rebuilt !== tree) throw new DispatchError("候选树对象已丢失，且补丁重建结果不一致");
  }
  const prefix = options.rework ? "pi-rework" : "pi";
  const name = options.name || defaultBranchName(prefix, meta);
  if (git(["check-ref-format", "--branch", name], repo.root).status !== 0) throw new DispatchError(`分支名不合法：${name}`, EXIT_USAGE);
  const existing = git(["rev-parse", "--verify", "--quiet", `refs/heads/${name}`], repo.root);
  if (createRef && existing.status === 0) {
    const commit = pyStrip(pyDecodeUtf8Replace(existing.stdout));
    const same = gitText(["rev-parse", `${commit}^{tree}`], repo.root) === tree &&
      pyStrip(pyDecodeUtf8(git(["rev-parse", "--verify", "--quiet", `${commit}^`], repo.root).stdout)) === baseSha();
    if (options.reuse && same) {
      return new Map<string, PyValue>([
        ["branch", name], ["commit", commit], ["tree", tree], ["verdict", verdict], ["rework", options.rework], ["reused", true],
      ]);
    }
    throw new DispatchError(`分支已存在：${name}${same ? "" : "（指向的不是这个候选）"}`);
  }
  const rawContract = readJsonOr(path.join(runDir, "contract.json"), new Map());
  const title = rawContract instanceof Map ? (rawContract.get("title") ?? null) : null;
  const executor = attemptExecutor(runDir, new Map());
  const lines = [
    subjectOf(meta, title),
    "",
    `Pi-Dispatch-Attempt: ${pyStrValue(pyItem(meta, "attempt_id"))}`,
    `Pi-Executor: ${pyStrValue(pyGet(executor, "provider"))}/${pyStrValue(pyGet(executor, "model"))} (thinking ${pyStrValue(pyGet(executor, "thinking"))})`,
    `Candidate-Tree: ${pyStrValue(tree)}`,
    `Verdict: ${pyStrValue(verdict)}`,
  ];
  if (options.trailers.length) lines.push("", ...options.trailers);
  const messageFile = path.join(runDir, "branch-message.txt");
  // 以字节写入：文本模式会把换行写成 CRLF，commit-tree 会原样写进提交说明
  writeFileSync(messageFile, encodeUtf8(lines.join(LF) + LF));
  const commit = gitText(["commit-tree", tree as string, "-p", baseSha(), "-F", messageFile], repo.root);
  const record = new Map<string, PyValue>([
    ["branch", createRef ? name : null], ["commit", commit], ["tree", tree], ["verdict", verdict], ["rework", Boolean(options.rework)],
    ["created_at", utcNow()], ["reused", false],
  ]);
  if (createRef) {
    gitChecked(["branch", name, commit], repo.root);
    writeJson(path.join(runDir, `branch-${name.replace(/[^A-Za-z0-9._-]/gu, "_")}.json`), record);
    logEvent(runDir, "branch_created", [...record]);
  }
  return record;
}

/**
 * branch_subject(meta["task_id"], title, meta["plan_version"], meta["attempt_no"])：有标题时 task_id 要是字符串（startswith），
 * 没有标题时才对 attempt_no 做 %03d（照 %d 取整，不是数字时报 TypeError）。
 */
function subjectOf(meta: PyValue, title: PyValue): string {
  const [taskId, version, attemptNo] = [pyItem(meta, "task_id"), pyItem(meta, "plan_version"), pyItem(meta, "attempt_no")];
  const titled = typeof title === "string" && pyStrip(title) !== "";
  if (titled && typeof taskId !== "string") throw new PyCrash("TypeError", `startswith first arg must be str or a tuple of str, not ${pyTypeName(taskId)}`);
  return branchSubject(pyStrValue(taskId), title, version, titled ? 0n : BigInt(pyPercentD(attemptNo)));
}

/** "%s/%s-v%s-a%03d" % (prefix, task_id, plan_version, attempt_no)：三项依次取，%03d 的负号算在宽度里（-1 写成 -01）。 */
function defaultBranchName(prefix: string, meta: PyValue): string {
  const [taskId, version, attemptNo] = [pyItem(meta, "task_id"), pyItem(meta, "plan_version"), pyItem(meta, "attempt_no")];
  const digits = pyPercentD(attemptNo);
  const padded = digits.startsWith("-") ? `-${digits.slice(1).padStart(2, "0")}` : digits.padStart(3, "0");
  return `${prefix}/${pyStrValue(taskId)}-v${pyStrValue(version)}-a${padded}`;
}
