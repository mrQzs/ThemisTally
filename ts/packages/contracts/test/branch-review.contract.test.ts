// branch 与 review-draft（迁移第 ④b8a 片）。每个场景按三份实现各建一份相同的仓库与 attempt（attempt-fixtures 的 fullAttempt：
// 提交号相同，工作树的路径换成占位符），跑同一条命令，比较退出码、两路输出、跑完之后 .agent/runs 与 .agent/reviews 下的全部证据，
// 以及各分支指向的提交与提交说明。提交身份与时间固定（GIT_AUTHOR_*、GIT_COMMITTER_*），候选提交的 SHA 才三边相同。
// 崩溃只比退出码。不写转义序列。
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { TS_CONTEXT, fullAttempt, json, sha, state, type AttemptOptions } from "./attempt-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const IDENTITY = {
  GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-02T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-02T00:00:00+00:00",
};
const EMPTY_GITCONFIG = join(tempDir("br-gitconfig"), "empty.gitconfig");
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

interface Scenario {
  readonly label: string;
  readonly o: AttemptOptions;
  readonly argv: readonly string[];
  readonly args: Record<string, unknown>;
  readonly status: number;
  readonly text?: string | readonly string[] | undefined;
  readonly crash?: boolean;
  readonly env?: Record<string, string | undefined>;
}

const ID_META = { attempt_id: "t1.v1.a001" };
const AUTH = (...integration: string[]) => ({ authorization: { executor: ["local_edit", "local_test"], integration } });

// --- branch ------------------------------------------------------------------------------------------

interface BranchFlags {
  readonly name?: string;
  readonly rework?: boolean;
  readonly trailer?: readonly string[];
  readonly noConfig?: boolean;
}

/** 一份可以建分支的 attempt：合同授权 local_branch，最新结论是 verdict。o 里的同名项覆盖。 */
/**
 * 生产里的组合（切换 c3b，themistally-15 建议）：Git for Windows 的系统默认 core.autocrlf=true，本机真实 attempt 的 meta 全记 true；
 * 候选树没有引用指着，过了 gc 期限被清掉，给旧 attempt 建分支就按补丁重建。候选树照生产用 autocrlf=true 快照（CRLF 存成 LF），
 * 一个 CRLF 文件、一个 LF 文件；重写候选记录、补丁与检查记录里的候选树，再 prune。实测 apply --cached 不做行尾转换，记下的
 * autocrlf 不影响重建结果：这条守的是两边在这个组合下一致。
 */
const CR = String.fromCharCode(13);

function crlfCandidate({ repo, wt, runDir, head }: { repo: string; wt: string; runDir: string; head: string }): void {
  const env = { ...process.env, GIT_INDEX_FILE: join(tempDir("br-crlf-idx"), "candidate.index") };
  const snap = (...args: string[]): string => spawnSync("git", ["-c", "core.autocrlf=true", ...args], { cwd: wt, env, encoding: "utf8" }).stdout.trim();
  snap("read-tree", head);
  snap("add", "-A");
  const tree = snap("write-tree");
  const patch = spawnSync("git", ["diff", "--binary", "--full-index", head, tree], { cwd: repo }).stdout;
  put(runDir, "candidate.patch", patch);
  put(runDir, "candidate.json", json({ tree, patch_roundtrip_verified: true, patch_sha256: sha(patch) }));
  put(runDir, "checks/01/checks.json", json({ run: 1, mode: "in_place", candidate_tree: tree, covers_all_required: true,
    results: [{ id: "V01", required: true, passed: true, status: "passed" }] }));
  git(repo, "prune", "--expire=now");
}
function branchable(verdict: string | null, o: AttemptOptions = {}): AttemptOptions {
  return {
    ...o,
    meta: { ...ID_META, ...o.meta },
    contract: { ...AUTH("local_branch"), ...o.contract },
    files: { ...(verdict === null ? {} : { "verdicts/1.json": { verdict } }), ...o.files },
  };
}

const branch = (label: string, o: AttemptOptions, flags: BranchFlags, status: number, text?: string | readonly string[], extra: Partial<Scenario> = {}): Scenario => ({
  label,
  o,
  argv: [
    "branch", "t1", ...(flags.name !== undefined ? ["--name", flags.name] : []), ...(flags.rework ? ["--rework"] : []),
    ...(flags.trailer ?? []).flatMap((item) => ["--trailer", item]), ...(flags.noConfig ? ["--no-config-trailers"] : []),
  ],
  args: {
    command: ["branch"], run_dir: "t1", name: flags.name ?? null, rework: flags.rework ?? false, trailer: [...(flags.trailer ?? [])],
    no_config_trailers: flags.noConfig ?? false, context: TS_CONTEXT,
  },
  status,
  text,
  ...extra,
});

const BRANCH: Scenario[] = [
  branch("PASS：建 pi/t1-v1-a001，HEAD 仍是基线", branchable("PASS"), {}, 0,
    ["已创建本地分支 pi/t1-v1-a001 → ", "（未推送）。", "集成：HEAD 仍是基线，可以 git merge --ff-only pi/t1-v1-a001"]),
  branch("ACCEPTED_WITH_EXCEPTION 也可以", branchable("ACCEPTED_WITH_EXCEPTION"), {}, 0, "commit="),
  branch("REVISE 不带 --rework：拒绝", branchable("REVISE"), {}, 3, "最新结论为 REVISE：只有 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）可以建分支。"),
  branch("REVISE 带 --rework：建 pi-rework/", branchable("REVISE"), { rework: true }, 0, ["pi-rework/t1-v1-a001", "返工合同可把 base_sha 设为 "]),
  branch("PASS 带 --rework：照样建 pi-rework/", branchable("PASS"), { rework: true }, 0, "pi-rework/t1-v1-a001"),
  branch("还没有结论：最新结论为 None", branchable(null), {}, 3, "最新结论为 None："),
  branch("结论按编号的数值取最新的：10 比 9 新", branchable(null, { files: { "verdicts/9.json": { verdict: "REVISE" }, "verdicts/10.json": { verdict: "PASS" } } }), {}, 0,
    "已创建本地分支 "),
  branch("结论记录是列表：照 Python 崩", branchable(null, { files: { "verdicts/1.json": [] } }), {}, 1, undefined, { crash: true }),
  branch("--name 自己起名", branchable("PASS"), { name: "feature/x" }, 0, "已创建本地分支 feature/x → "),
  branch("--name 不合法：用法错误", branchable("PASS"), { name: "bad..name" }, 2, "分支名不合法：bad..name"),
  branch("--name 是空串：照缺省起名", branchable("PASS"), { name: "" }, 0, "pi/t1-v1-a001"),
  branch("同名分支已在、指向别处：拒绝", branchable("PASS", { after: ({ repo, head }) => void git(repo, "branch", "pi/t1-v1-a001", head) }), {}, 3,
    "分支已存在：pi/t1-v1-a001（指向的不是这个候选）"),
  branch("合同没有授权 local_branch", branchable("PASS", { contract: AUTH() }), {}, 3, "合同未授权动作：authorization.integration 缺少 local_branch"),
  branch("合同只授权 merge：不拿相近的动作代替", branchable("PASS", { contract: AUTH("merge") }), {}, 3, "缺少 local_branch"),
  branch("authorization.integration 不是字符串数组", branchable("PASS", { contract: { authorization: { executor: [], integration: ["local_branch", 1] } } }), {}, 3,
    "合同授权无效：authorization.integration 必须是字符串数组"),
  branch("冻结的 plan.md 被改过：G0 拒绝", branchable("PASS", { after: ({ runDir }) => put(runDir, "plan.md", "改过" + LF) }), {}, 3, "输入不一致（G0）："),
  branch("合同改成 planner-v2：发布门禁拒绝", branchable("PASS", { contract: { ...AUTH("local_branch"), contract_family: "planner-v2" } }), {}, 3,
    "planner-v2 发布门禁拒绝创建分支："),
  branch("没有 Git 作者身份", branchable("PASS", { after: ({ repo }) => void git(repo, "config", "user.useConfigOnly", "true") }), {}, 3,
    "没有可用的 Git 作者身份（GIT_AUTHOR_IDENT）", { env: NO_IDENTITY }),
  branch("配置的 commit_trailers 与 --trailer 都写进提交说明", branchable("PASS", { config: { commit_trailers: ["Signed-off-by: t <t@example.invalid>"] } }),
    { trailer: ["Reviewed-by: r", "Co-Authored-By: x <x@example.invalid>"] }, 0, "已创建本地分支 "),
  branch("--trailer 不是 Key: value：用法错误", branchable("PASS"), { trailer: ["Reviewed-by: r", "不合格"] }, 2, "--trailer 必须是单行 "),
  branch("--trailer 里有换行：用法错误", branchable("PASS"), { trailer: ["Reviewed-by: a" + LF + "b"] }, 2, "--trailer 必须是单行 "),
  branch("配置的 commit_trailers 不合格：用法错误", branchable("PASS", { config: { commit_trailers: ["不合格"] } }), {}, 2, "commit_trailers 必须是单行"),
  branch("--no-config-trailers：不读配置里不合格的尾注", branchable("PASS", { config: { commit_trailers: ["不合格"] } }), { noConfig: true }, 0, "已创建本地分支 "),
  branch("合同没有标题：主题行写 Pi 候选 v1 attempt 001", branchable("PASS", { contract: { ...AUTH("local_branch"), title: "" } }), {}, 0, "已创建本地分支 "),
  branch("标题以 task-id 加冒号开头：不再加前缀", branchable("PASS", { contract: { ...AUTH("local_branch"), title: "t1：多行" + LF + "标题" } }), {}, 0, "已创建本地分支 "),
  branch("候选树对象被清掉：按补丁重建", branchable("PASS", { after: ({ repo }) => void git(repo, "prune", "--expire=now") }), {}, 0, "已创建本地分支 "),
  branch("autocrlf=true 下候选树对象被清掉：按补丁重建", branchable("PASS", {
    candidateFiles: { "src/crlf.txt": `a${CR}${LF}b${CR}${LF}`, "src/lf.txt": `a${LF}b${LF}` }, meta: { git_autocrlf: "true" }, after: crlfCandidate,
  }), {}, 0, "已创建本地分支 "),
  branch("候选树对象不在、补丁重建出来的不一样：拒绝", branchable("PASS", { files: { "candidate.json": { tree: "1".repeat(40), patch_roundtrip_verified: true } } }), {}, 3,
    "候选树对象已丢失，且补丁重建结果不一致"),
  branch("没有候选记录", branchable("PASS", { files: { "candidate.json": { patch_roundtrip_verified: true } } }), {}, 3, "缺少候选记录"),
  branch("候选树是数字：照 Python 崩", branchable("PASS", { files: { "candidate.json": { tree: 5 } } }), {}, 1, undefined, { crash: true }),
  branch("meta 没有 attempt_id：照 Python 崩", branchable("PASS", { meta: { attempt_id: undefined } }), {}, 1, undefined, { crash: true }),
  branch("HEAD 已比基线前进：提示 integrate 或 cherry-pick", branchable("PASS", {
    after: ({ repo }) => {
      put(repo, "later.txt", "x" + LF);
      git(repo, "add", "later.txt");
      git(repo, "commit", "-q", "-m", "later");
    },
  }), {}, 0, ["已比基线前进，用 integrate 在当前末端上验证后落地（2.8.0），或 git cherry-pick "]),
];

// --- review-draft ------------------------------------------------------------------------------------

interface DraftFlags {
  readonly out?: string;
  readonly force?: boolean;
}

const draft = (label: string, o: AttemptOptions, flags: DraftFlags, status: number, text?: string | readonly string[], extra: Partial<Scenario> = {}): Scenario => ({
  label,
  o,
  argv: ["review-draft", "t1", ...(flags.out !== undefined ? ["--out", flags.out] : []), ...(flags.force ? ["--force"] : [])],
  args: { command: ["review-draft"], run_dir: "t1", out: flags.out ?? null, force: flags.force ?? false, context: TS_CONTEXT },
  status,
  text,
  ...extra,
});

/** 两轮变异：一轮两条命令，有意外漏掉、等价、预期内与标了预期却被抓住的；一轮中途停了。 */
const MUTATIONS = {
  "mutations/02-b/mutations.json": {
    commands: [{ id: "unit" }, { id: "e2e" }],
    results: [
      { id: "M01", name: "M01 改坏比较", file: "src/a.ts", status: "caught", commands: { unit: { status: "caught" }, e2e: { status: "caught" } } },
      { id: "M02", name: "去掉校验", file: "src/a.ts", status: "missed", commands: { unit: { status: "missed" }, e2e: { status: "caught" } } },
      { id: "M03", name: "M03 等价改写", file: "src/a.ts", status: "missed", equivalent: "只换了变量名", commands: { unit: { status: "missed" }, e2e: { status: "missed" } }, unexpected: [] },
      { id: "M04", name: "M04 交给 e2e", file: "src/b.ts", status: "missed", expect_missed: true, unexpected: ["e2e"], commands: { unit: { status: "missed" }, e2e: { status: "caught" } } },
      { id: "M05", name: "M05 跳过", file: "src/b.ts", status: "skipped", commands: { unit: { status: "skipped" }, e2e: { status: "error" } } },
      "不是字典的记录",
    ],
  },
  "mutations/01-a/mutations.json": { aborted: "用户中断" },
  "mutations/03-c/mutations.json": "不是 JSON {",
  "mutations/04-d/mutations.json": {
    results: [
      { id: "M01", name: "改坏边界", file: "src/a.ts", status: "missed" },
      { id: "M02", name: "M02 改坏顺序", file: "src/a.ts", status: "caught" },
    ],
  },
};

const MENTIONS = Array.from({ length: 12 }, (_, i) => ({ line: i + 3, kind: "interpretation", excerpt: `我理解为第 ${i} 种读法 | 带竖线${LF}  和换行` }));

const RICH: AttemptOptions = {
  contract: AUTH("local_branch", "merge"),
  dod: [
    { id: "D01", text: "行为正确", intent: "a 变成 2", evidence: ["V01", "scope", "review", "V09", "V02"] },
    { id: "D02", text: "", evidence: [] },
    // 目的很长：表格里截到 400 个码点，简报里截到 600 个
    { id: "D03", text: "长目的", intent: "长".repeat(700), evidence: ["V01"] },
    // 恰好比表格单元的上限多一个码点：要截
    { id: "D04", text: "边".repeat(401), evidence: [] },
  ],
  files: {
    "checks/01/checks.json": { run: 1, mode: "in_place", results: [{ id: "V01", passed: true, status: "passed" }, { id: "V02", passed: false, status: "failed" }] },
    "events-summary.json": {
      problems: [], provider_thinking_levels: ["high", 3], requested_model: { thinking: "high" }, outside_worktree_paths: [], ambiguity_mention_count: 0,
      actual_models: [{ provider: "step", model: "step-5-preview" }, { provider: "step" }], tool_errors: 2,
      usage: { input: 1000, output: 200, cacheRead: 5, cacheWrite: 0 }, cost: { total: 0.00043, status: "estimated" },
      interpretation_mentions: [...MENTIONS, "不是字典"], interpretation_mention_count: 15,
    },
    "run.json": { exit_code: 0, timed_out: false, interrupted: true, wall_seconds: 12.5 },
    "executor-report.json": {
      executor_status: "done", contract_conflicts: ["合同两处说法不同", { where: "DoD", note: "中文" }], interpretations: ["取了第二种读法"],
      limitations: [], unresolved_questions: "一个字符串",
    },
    "summary.md": ["# 摘要", "", "## 复审需要关注", "", "- 看一下 src/a.ts  ", "   ", "- 第二条", "## 别的", "- 不算"].join(LF),
    "candidate.stat.txt": [" src/a.ts | 2 +-", " 1 file changed, 1 insertion(+), 1 deletion(-)", ""].join(LF),
    "scope.json": { violations: [{ kind: "modified_outside", path: "docs/x.md" }], warnings: ["w1", "w2"] },
    ...MUTATIONS,
  },
};

const DRAFT: Scenario[] = [
  draft("骨架与简报：证据很少的 attempt", {}, {}, 0, ["已写复审记录骨架：.agent/reviews/t1/attempt-001.md（", "独立复审简报："]),
  draft("证据齐全：模型、用时、token、费用、门禁、DoD、变异、自述、解读线索、关注项", RICH, {}, 0, "处【待填】"),
  draft("还在运行：用法错误", { files: { "state.json": state("RUNNING") } }, {}, 2, "attempt 处于 RUNNING：运行结束、证据收集完之后再生成复审骨架"),
  draft("已有复审记录：不加 --force 拒绝", { after: ({ repo }) => put(repo, ".agent/reviews/t1/attempt-001.md", "旧的" + LF) }, {}, 2,
    ".agent/reviews/t1/attempt-001.md 已存在：确认要覆盖（例如重新生成骨架）时加 --force"),
  draft("已有复审记录：--force 覆盖", { after: ({ repo }) => put(repo, ".agent/reviews/t1/attempt-001.md", "旧的" + LF) }, { force: true }, 0, "已写复审记录骨架："),
  draft("--out 写到别处", {}, { out: "notes/review.md" }, 0, "已写复审记录骨架：notes/review.md（"),
  draft("合同只授权 local_branch：集成动作写 integrate 只验证、或 branch", { contract: AUTH("local_branch") }, {}, 0),
  draft("执行报告的 interpretations 不是列表（json_ok）", { files: { "executor-report.json": { interpretations: "没写成列表" } } }, {}, 0),
  draft("工作树已清理：简报提示用 git show 对照", { after: ({ repo, wt }) => void git(repo, "worktree", "remove", "--force", wt) }, {}, 0),
  draft("检查记录中途停了：没有有效的检查记录", { files: { "checks/01/checks.json": { aborted: "中断", results: [] } } }, {}, 0),
  draft("没有费用：unknown（状态）", { files: { "events-summary.json": { problems: [], cost: { total: null } }, "run.json": { timed_out: true } } }, {}, 0),
  draft("范围记录是列表：照 Python 崩", { files: { "scope.json": ["x"] } }, {}, 1, undefined, { crash: true }),
  draft("变异记录的命令 id 不是字符串：照 Python 崩", { files: { "mutations/01-a/mutations.json": { commands: [{ id: 1 }, { id: "e2e" }], results: [] } } }, {}, 1, undefined,
    { crash: true }),
  draft("变异记录目录名大小写不同：按小写排序", { files: { "mutations/B-round/mutations.json": { results: [] }, "mutations/a-round/mutations.json": { results: [] } } }, {}, 0),
];

// --- 运行与比较 ---------------------------------------------------------------------------------------

function scrub(text: string): string {
  return text.replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>');
}

function runScenario(scenario: Scenario): void {
  const results = RUNNERS.map((runner: Runner) => {
    const { repo, head } = newRepo(`br-${runner}`);
    const paths = { "<REPO>": repo, ...fullAttempt(repo, head, runner, scenario.o) };
    const result = withEnv({ ...IDENTITY, ...scenario.env }, () => runCommand(runner, repo, scenario.argv, scenario.args));
    const stderr = result.stderr.toString("utf8");
    const show = (text: string): string => scrub(normalize(text, paths));
    const evidence = scenario.crash ? {} : {
      ...snapshotDir(join(repo, ".agent", "runs"), paths),
      ...Object.fromEntries(Object.entries(snapshotDir(join(repo, ".agent", "reviews"), paths)).map(([rel, text]) => [`reviews/${rel}`, text])),
      ...(scenario.args["out"] ? { out: show(readFileSync(join(repo, scenario.args["out"] as string), "utf8")) } : {}),
    };
    const refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/").split(LF).filter(Boolean);
    const messages = refs.filter((line) => !line.startsWith("refs/heads/master ") && !line.startsWith("refs/heads/main "))
      .map((line) => git(repo, "log", "-1", "--format=%P%n%T%n%B", line.split(" ")[0] as string));
    return {
      status: result.status,
      stdout: scenario.crash ? "" : show(result.stdout.toString("utf8")),
      stderr: scenario.crash ? "" : show(stderr),
      crashed: scenario.crash ? crashed(stderr) : null,
      evidence: Object.fromEntries(Object.entries(evidence).map(([key, value]) => [key, scrub(value as string)])),
      refs,
      messages,
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, first.stdout + first.stderr).toBe(scenario.status);
  if (scenario.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof scenario.text === "string" ? [scenario.text] : scenario.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
}

describe("branch", () => {
  for (const scenario of BRANCH) it(scenario.label, () => runScenario(scenario), 240_000);
});

describe("review-draft", () => {
  for (const scenario of DRAFT) it(scenario.label, () => runScenario(scenario), 240_000);
});

describe("branch 的现场", () => {
  it("候选提交的父提交是基线、树是候选树，说明里带尾注", () => {
    const { repo, head } = newRepo("br-direct");
    fullAttempt(repo, head, "node", branchable("PASS", { config: { commit_trailers: ["Signed-off-by: t <t@example.invalid>"] } }));
    const result = withEnv(IDENTITY, () => runCommand("node", repo, ["branch", "t1"], {
      command: ["branch"], run_dir: "t1", name: null, rework: false, trailer: ["Reviewed-by: r"], no_config_trailers: false, context: TS_CONTEXT,
    }));
    expect(result.status, result.stderr.toString("utf8")).toBe(0);
    const candidate = JSON.parse(readFileSync(join(repo, ".agent", "runs", "t1", "attempt-001", "candidate.json"), "utf8")) as { tree: string };
    expect(git(repo, "rev-parse", "pi/t1-v1-a001^")).toBe(head);
    expect(git(repo, "rev-parse", "pi/t1-v1-a001^{tree}")).toBe(candidate.tree);
    const message = git(repo, "log", "-1", "--format=%B", "pi/t1-v1-a001");
    expect(message).toContain("t1: 改一个文件。");
    expect(message).toContain("Signed-off-by: t <t@example.invalid>" + LF + "Reviewed-by: r");
  }, 120_000);
});
