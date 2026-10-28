// integrate（迁移第 ④b8b 片）。每个场景按三份实现各建一份相同的仓库与 attempt（attempt-fixtures 的 fullAttempt），跑同一条
// integrate，比较退出码、两路输出、.agent/runs 下的全部证据、主工作区的 HEAD 与各分支、登记的 worktree 数。提交身份与时间固定，
// 候选提交与落地提交的 SHA 才三边相同；验证副本的路径与 mkdtemp 的随机后缀、用时换成占位符。崩溃只比退出码。不写转义序列。
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { FAIL, OK, TS_CONTEXT, fullAttempt, json, py, state, type AttemptOptions } from "./attempt-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const IDENTITY = {
  GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-02T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-02T00:00:00+00:00",
};

const EMPTY_GITCONFIG = join(tempDir("ig-gitconfig"), "empty.gitconfig");
put(join(EMPTY_GITCONFIG, ".."), "empty.gitconfig", "");
const NO_IDENTITY: Record<string, string | undefined> = {
  GIT_CONFIG_GLOBAL: EMPTY_GITCONFIG, GIT_CONFIG_NOSYSTEM: "1", GIT_AUTHOR_NAME: undefined, GIT_AUTHOR_EMAIL: undefined,
  GIT_COMMITTER_NAME: undefined, GIT_COMMITTER_EMAIL: undefined, EMAIL: undefined,
};

function withEnv<T>(env: Record<string, string | undefined>, body: () => T): T {
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  const apply = (values: Record<string, string | undefined>): void => {
    for (const [key, value] of Object.entries(values)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  apply(env);
  try {
    return body();
  } finally {
    apply(saved);
  }
}

const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

interface Flags {
  readonly dryRun?: boolean;
  readonly skip?: string;
  readonly reason?: string;
  readonly recheck?: boolean;
  readonly name?: string;
  readonly trailer?: readonly string[];
  readonly noConfig?: boolean;
  readonly keepWorktree?: boolean;
  readonly keepWorkspace?: boolean;
  readonly whileRunning?: boolean;
}

interface Scenario {
  readonly label: string;
  /** attempt 的选项；要用到仓库路径的写成函数。 */
  readonly o: AttemptOptions | ((repo: string) => AttemptOptions);
  readonly flags: Flags;
  readonly status: number;
  readonly text?: string | readonly string[] | undefined;
  readonly crash?: boolean;
  readonly env?: Record<string, string | undefined>;
}

/** 一份可以落地的 attempt：合同授权 local_branch 与 merge，结论与状态都是 PASS。o 里的同名项覆盖。 */
function landable(o: AttemptOptions = {}, integration: readonly string[] = ["local_branch", "merge"]): AttemptOptions {
  return {
    ...o,
    meta: { attempt_id: "t1.v1.a001", ...o.meta },
    contract: { authorization: { executor: ["local_edit", "local_test"], integration: [...integration] }, ...o.contract },
    files: { "state.json": state("PASS"), "verdicts/1.json": { verdict: "PASS" }, ...o.files },
  };
}

const scenario = (label: string, o: Scenario["o"], flags: Flags, status: number, text?: string | readonly string[], extra: Partial<Scenario> = {}): Scenario =>
  ({ label, o, flags, status, text, ...extra });

function argvOf(flags: Flags): string[] {
  return [
    "integrate", "t1", ...(flags.dryRun ? ["--dry-run"] : []), ...(flags.skip !== undefined ? ["--skip", flags.skip] : []),
    ...(flags.reason !== undefined ? ["--reason", flags.reason] : []), ...(flags.recheck ? ["--recheck"] : []),
    ...(flags.name !== undefined ? ["--name", flags.name] : []), ...(flags.trailer ?? []).flatMap((item) => ["--trailer", item]),
    ...(flags.noConfig ? ["--no-config-trailers"] : []), ...(flags.keepWorktree ? ["--keep-worktree"] : []),
    ...(flags.keepWorkspace ? ["--keep-workspace"] : []), ...(flags.whileRunning ? ["--while-running"] : []),
  ];
}

function pyargsOf(flags: Flags): Record<string, unknown> {
  return {
    command: ["integrate"], run_dir: "t1", dry_run: flags.dryRun ?? false, skip: flags.skip ?? null, reason: flags.reason ?? null,
    recheck: flags.recheck ?? false, name: flags.name ?? null, trailer: [...(flags.trailer ?? [])], no_config_trailers: flags.noConfig ?? false,
    keep_worktree: flags.keepWorktree ?? false, keep_workspace: flags.keepWorkspace ?? false, while_running: flags.whileRunning ?? false,
    context: TS_CONTEXT,
  };
}

/** 主工作区在基线之后又提交了一个文件。 */
const commitInMain = (rel: string, content: string) => ({ repo }: { repo: string }): void => {
  put(repo, rel, content);
  git(repo, "add", rel);
  git(repo, "commit", "-q", "-m", `改 ${rel}`);
};

/** 一次干净的 check --fresh 记录（测的是这个候选树，必要检查全过），写在 checks/<number>。 */
function freshRecord(runDir: string, extra: Record<string, unknown> = {}, number = "02"): void {
  const tree = (JSON.parse(readFileSync(join(runDir, "candidate.json"), "utf8")) as { tree: string }).tree;
  put(runDir, `checks/${number}/checks.json`, json({
    run: 2, mode: "fresh", candidate_tree: tree, covers_all_required: true, all_required_passed: true, ended_at: "2026-01-01T00:00:01Z",
    results: [{ id: "V01", required: true, passed: true, status: "passed" }], modified_by_checks: [], unexpected_files_by_checks: [], ...extra,
  }));
}

const SCENARIOS: Scenario[] = [
  // --- 落地 ---
  scenario("落地：建分支、检查通过、快进、INTEGRATED、清理 worktree", landable(), {}, 0,
    ["分支 pi/t1-v1-a001 → ", "NOTE  在当前末端上重跑检查：没有 check --fresh 的记录", "CHECK V01 passed", "已集成 t1/attempt-001 → "]),
  scenario("--keep-worktree：落地后不清理", landable(), { keepWorktree: true }, 0, "已集成 "),
  scenario("--keep-workspace：验证副本留着", landable(), { keepWorkspace: true }, 0, "已集成 "),
  scenario("setup 也在验证副本里跑", landable({ setup: [py("S01", "print('setup ok')")] }), {}, 0, "已集成 "),
  scenario("--name 与 --trailer", landable({ config: { commit_trailers: ["Signed-off-by: t <t@example.invalid>"] } }), { name: "land/x", trailer: ["Reviewed-by: r"] }, 0,
    "分支 land/x → "),
  scenario("同名分支已指向这个候选：复用", landable({ after: ({ repo, runDir }) => {
    const tree = (JSON.parse(readFileSync(join(runDir, "candidate.json"), "utf8")) as { tree: string }).tree;
    const head = git(repo, "rev-parse", "HEAD");
    put(runDir, "reuse-message.txt", "x" + LF);
    git(repo, "branch", "pi/t1-v1-a001", git(repo, "commit-tree", tree, "-p", head, "-F", join(runDir, "reuse-message.txt")));
  } }), {}, 0, "（复用已有分支）"),
  scenario("同名分支指向别处：拒绝", landable({ after: ({ repo }) => void git(repo, "branch", "pi/t1-v1-a001") }), {}, 3, "（指向的不是这个候选）"),
  scenario("主工作区前进了一个不冲突的提交：落在新的末端上", landable({ after: commitInMain("docs/later.md", "x" + LF) }), {}, 0, "已集成 "),
  scenario("基线不在当前分支的历史里：照 cherry-pick 挑入", landable({ after: ({ repo }) => {
    git(repo, "checkout", "-q", "--orphan", "other");
    git(repo, "commit", "-q", "-m", "孤立的分支");
  } }), { dryRun: true }, 0, "不在当前分支的历史里：按“基线→候选”的改动挑入当前末端（等同 cherry-pick）"),
  // --- 只验证 ---
  scenario("--dry-run：不建分支、不建提交", landable(), { dryRun: true }, 0, "验证通过（dry-run，没有建提交、没有落地）"),
  scenario("合同没授权 merge：验证通过、建好提交、打印落地命令", landable({}, ["local_branch"]), {}, 3,
    ["但合同 integration 没有 merge：没有落地。", "  git merge --ff-only ", " INTEGRATED --ref "]),
  // --- 检查 ---
  scenario("检查不通过：什么都没落地", landable({ checks: [FAIL()] }), {}, 1, "+ 候选上的检查没有全部通过（0/1）：什么都没落地"),
  scenario("非必要的检查没过：照样落地", landable({ checks: [OK(), FAIL("V02", { required: false })] }), {}, 0, "检查 1/2"),
  scenario("检查跑完之后验证副本坏了：记下已经跑完的结果", landable({ checks: [py("V01", "import os; os.remove('.git')")] }), {}, 3,
    "无法在当前末端上验证（什么都没落地）："),
  scenario("检查产生了新文件：WARN，什么都没落地", landable({ checks: [py("V01", "open('made.txt', 'w').write('x')")] }), {}, 1, "WARN  检查产生了新文件：made.txt"),
  scenario("检查改了候选文件：WARN", landable({ checks: [py("V01", "open('src/a.ts', 'w').write('x')")] }), {}, 1, "WARN  检查修改了文件：src/a.ts"),
  scenario("--skip 加 --reason：豁免的记 skipped", landable({ checks: [OK(), FAIL("V02")] }), { skip: " V02 ,", reason: "只对基线成立" }, 0,
    ["CHECK V02 skipped（只对基线成立）", "，豁免 V02"]),
  scenario("--skip 不带 --reason：用法错误", landable(), { skip: "V01" }, 2, "--skip 需要 --reason"),
  scenario("--skip 有未知的检查：按码点排序报出", landable(), { skip: "V9,V01,V10", reason: "r" }, 2, "未知检查：V10, V9"),
  // --- 沿用 check --fresh ---
  scenario("沿用 check --fresh：树完全相同", landable({ after: ({ runDir }) => freshRecord(runDir) }), {}, 0,
    ["检查沿用 checks/02（check --fresh，<AT> 结束）：当前末端 + 候选与那次测过的树完全相同", "，沿用 checks/02"]),
  scenario("沿用 check --fresh：末端只多了规划文件", landable({ after: (at) => { freshRecord(at.runDir); commitInMain(".agent/plans/note.md", "x" + LF)(at); } }), {}, 0,
    "只差规划文件 .agent/plans/note.md"),
  scenario("末端多了规划路径之外的改动：重跑", landable({ after: (at) => { freshRecord(at.runDir); commitInMain("docs/x.md", "x" + LF)(at); } }), {}, 0,
    "当前末端相对候选多了规划路径之外的改动：docs/x.md"),
  scenario("--recheck：不沿用", landable({ after: ({ runDir }) => freshRecord(runDir) }), { recheck: true }, 0, "NOTE  在当前末端上重跑检查：加了 --recheck"),
  scenario("--skip 也不沿用", landable({ checks: [OK(), OK("V02")], after: ({ runDir }) => freshRecord(runDir) }), { skip: "V02", reason: "r" }, 0,
    "豁免只在重跑时成立"),
  scenario("check --fresh 测的不是这个候选树", landable({ after: ({ runDir }) => freshRecord(runDir, { candidate_tree: "0".repeat(40) }) }), {}, 0, "测的不是这个候选树"),
  scenario("check --fresh 中止了", landable({ after: ({ runDir }) => freshRecord(runDir, { aborted: "fresh_workspace_failed" }) }), {}, 0,
    "最近一次 check --fresh（checks/02）中止了：fresh_workspace_failed"),
  scenario("2.10.0 之前中止的记录没有 mode：照样认作 check --fresh", landable({ after: ({ runDir }) => freshRecord(runDir, { mode: null, aborted: "fresh_workspace_failed" }) }),
    {}, 0, "最近一次 check --fresh（checks/02）中止了"),
  scenario("两次 check --fresh：按编号取最新的", landable({
    after: ({ runDir }) => {
      freshRecord(runDir, { candidate_tree: "0".repeat(40) }, "02");
      freshRecord(runDir, {}, "10");
    },
  }), {}, 0, "检查沿用 checks/10"),
  scenario("check --fresh 少跑了检查", landable({ checks: [OK(), OK("V02")], after: ({ runDir }) => freshRecord(runDir) }), {}, 0, "checks/02 没有跑 V02"),
  scenario("check --fresh 的必要检查没过", landable({ after: ({ runDir }) => freshRecord(runDir, { all_required_passed: false }) }), {}, 0, "all_required_passed 为假"),
  scenario("check --fresh 改了文件", landable({ after: ({ runDir }) => freshRecord(runDir, { modified_by_checks: ["src/a.ts"] }) }), {}, 0, "的检查改动了候选文件或产生了新文件"),
  // --- 拒绝 ---
  scenario("结论是 REVISE：拒绝", landable({ files: { "verdicts/1.json": { verdict: "REVISE" } } }), {}, 3, "最新结论为 REVISE（状态 PASS）"),
  scenario("状态还是 NEEDS_REVIEW：拒绝", landable({ files: { "state.json": state("NEEDS_REVIEW") } }), {}, 3, "（状态 NEEDS_REVIEW）"),
  scenario("已经集成过：用法错误", landable({ files: { "state.json": { state: "INTEGRATED", at: "2026-01-01T00:00:00Z", ref: "abc" } } }), {}, 2, "attempt 已集成（ref abc）"),
  scenario("合同没授权 local_branch", landable({}, ["merge"]), {}, 3, "合同未授权动作：authorization.integration 缺少 local_branch"),
  scenario("合同改成 planner-v2：发布门禁拒绝", landable({ contract: { contract_family: "planner-v2" } }), {}, 3, "planner-v2 发布门禁拒绝集成："),
  scenario("冻结的 plan.md 被改过：G0 拒绝", landable({ after: ({ runDir }) => put(runDir, "plan.md", "改过" + LF) }), {}, 3, "输入不一致（G0）："),
  scenario("没有 Git 作者身份", landable({ after: ({ repo }) => void git(repo, "config", "user.useConfigOnly", "true") }), {}, 3,
    "没有可用的 Git 作者身份（GIT_AUTHOR_IDENT）", { env: NO_IDENTITY }),
  scenario("主工作区是游离 HEAD：用法错误", landable({ after: ({ repo }) => void git(repo, "checkout", "-q", "--detach") }), {}, 2, "主工作区是游离 HEAD"),
  scenario("另有 attempt 在运行、在收集：拒绝落地", landable({
    after: ({ runDir }) => {
      put(runDir, "../../t2/attempt-001/state.json", json(state("RUNNING")));
      put(runDir, "../../t3/attempt-001/state.json", json(state("COLLECTING")));
    },
  }), {}, 3, "有 attempt 正在运行或收集：t2/attempt-001, t3/attempt-001。"),
  scenario("另一个 attempt 正在运行，--while-running：照样落地", landable({ after: ({ runDir }) => put(runDir, "../../t2/attempt-001/state.json", json(state("COLLECTING"))) }),
    { whileRunning: true }, 0, "已集成 "),
  scenario("另一个 attempt 正在运行，--dry-run：不拦", landable({ after: ({ runDir }) => put(runDir, "../../t2/attempt-001/state.json", json(state("RUNNING"))) }),
    { dryRun: true }, 0, "验证通过（dry-run"),
  // --- 什么都没落地 ---
  scenario("与当前末端冲突：CONFLICT", landable({ after: commitInMain("src/a.ts", "export const a = 3;" + LF) }), {}, 1,
    ["CONFLICT 候选与当前末端 ", "冲突：src/a.ts", "什么都没落地（只多了本地分支 pi/t1-v1-a001）"]),
  scenario("setup 在验证副本里失败：无法验证", landable({ setup: [py("S01", "import sys; sys.exit(3)")] }), {}, 3, "无法在当前末端上验证（什么都没落地）：验证副本的 setup S01 失败："),
  scenario("验证期间主工作区的末端变了：什么都没落地", (repo) => landable({
    checks: [py("V01", `import subprocess; subprocess.run(['git', '-C', ${JSON.stringify(repo)}, 'commit', '--allow-empty', '-q', '-m', 'moved'], check=True)`)],
  }), {}, 1, "分支末端在验证期间变了"),
  // 本地改动要在快进之前出现：放在检查里改主工作区的 src/a.ts（验证副本不受影响）
  scenario("主工作区有会被覆盖的本地改动：快进被拒", (repo) => landable({
    checks: [py("V01", `open(${JSON.stringify(join(repo, "src", "a.ts"))}, 'w').write('local')`)],
  }), {}, 1, ["快进被拒：", "什么都没落地。提交 "]),
];

function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/-integrate-[a-z0-9_]{8}/gu, "-integrate-<R>")
    // 有两个场景的检查里写着各自的仓库路径：冻结合同的哈希三边不同（合同正文换成占位符之后另外比）
    .replace(/"contract_json_sha256": "[0-9a-f]{64}"/gu, '"contract_json_sha256": "<SHA>"');
}

function runScenario(item: Scenario): void {
  const results = RUNNERS.map((runner: Runner) => {
    const { repo, head } = newRepo(`ig-${runner}`);
    const options = typeof item.o === "function" ? item.o(repo) : item.o;
    const paths = { "<REPO>": repo, ...fullAttempt(repo, head, runner, options) };
    const result = withEnv({ ...IDENTITY, ...item.env }, () => runCommand(runner, repo, argvOf(item.flags), pyargsOf(item.flags)));
    const stderr = result.stderr.toString("utf8");
    const show = (text: string): string => scrub(normalize(text, paths));
    const evidence = item.crash ? {} : Object.fromEntries(Object.entries(snapshotDir(join(repo, ".agent", "runs"), paths)).map(([key, value]) => [scrub(key), scrub(value)]));
    return {
      status: result.status,
      stdout: item.crash ? "" : show(result.stdout.toString("utf8")),
      stderr: item.crash ? "" : show(stderr),
      crashed: item.crash ? crashed(stderr) : null,
      evidence,
      head: git(repo, "rev-parse", "HEAD"),
      refs: git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/").split(LF).filter(Boolean),
      worktrees: git(repo, "worktree", "list", "--porcelain").split(LF).filter((line) => line.startsWith("worktree ")).length,
      status_lines: git(repo, "status", "--porcelain").split(LF).filter(Boolean).sort(),
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, first.stdout + first.stderr).toBe(item.status);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
}

describe("integrate", () => {
  for (const item of SCENARIOS) it(item.label, () => runScenario(item), 240_000);
});
