// collect --recover（迁移第 ④b7b 片）：调度器异常退出之后补收证据——事件摘要、执行报告、固定候选与往返校验、改动与范围判定、
// 忽略的新路径、主工作区在运行前后的变化、决策模型对执行报告的筛查、最终状态与 summary.md。每个场景按三份实现各建一份相同的
// 仓库（固定作者与时间，提交号相同）、worktree 与 attempt 证据，在 worktree 里真跑一遍 stub_pi 的剧本（改文件、写事件流），
// 再跑同一条 collect，比退出码、标准输出与标准错误、.agent/runs 下的全部证据与发给决策端点的请求。路径、时间、pid、延迟换成
// 占位符；崩溃只比退出码与证据。不写转义序列。
import { spawnSync } from "node:child_process";
import { realpathSync, rmSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { PYTHON, TS_CONTEXT, json, sha, treeOf } from "./attempt-fixtures.ts";
import { KEY_NAME, type Reply, startEndpoint } from "./endpoint-fixtures.ts";
import { REPO as KIT } from "./harness.ts";
import { type Json, jsonOf, mdOf } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

const savedKey = process.env[KEY_NAME];

beforeAll(() => {
  process.env[KEY_NAME] = "fake-key-for-contract";
});

afterAll(() => {
  if (savedKey === undefined) delete process.env[KEY_NAME];
  else process.env[KEY_NAME] = savedKey;
  removeCreated();
});

const STUB = join(KIT, "tests", "stub_pi.py");
const RUN_REL = ".agent/runs/t1/attempt-001";
const AT = "2026-01-01T00:00:00Z";
/**
 * 不存在的进程号：Windows 的进程号都是 4 的倍数，这个永远不会有；POSIX 上超过 pid_max。不取刚退出的子进程的号：用例一路
 * 起几十个进程，Windows 会很快把号重新分出去（实测 Python 那一边碰上过）。
 */
const DEAD_PID = 999999991;
/** stub_pi 的 commit 剧本照这个时间提交：三份实现的提交号才相同。 */
const FIXED_DATES = { GIT_AUTHOR_DATE: "2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-01T00:00:00+00:00" };
const NEW_FILES = ["src/normalize.py", "tests/test_normalize.py"];
const EXECUTOR = { provider: "step", model: "step-5-preview", thinking: "high", tools: ["read", "grep", "find", "ls", "edit", "write", "bash"], context_files: "project" };

interface At {
  readonly repo: string;
  readonly wt: string;
  readonly runDir: string;
  readonly head: string;
}

interface Fingerprint {
  readonly head: string;
  readonly content_tree: string;
}

interface Case {
  readonly label: string;
  readonly status: number;
  readonly text?: string | readonly string[];
  /** stub_pi 的剧本（缺省 ok）；null 不跑（Pi 还没启动）。 */
  readonly scenario?: string | null;
  /** run.json 已经写好（Pi 跑完、收集之前调度器退出）：在 run-started 之上补的字段。 */
  readonly finished?: Record<string, unknown>;
  readonly state?: string;
  readonly contract?: (data: Json) => void;
  readonly config?: Record<string, unknown>;
  readonly meta?: Record<string, unknown>;
  /** 证据文件：null 删掉，字符串原样写，其余写成 JSON。 */
  readonly files?: Record<string, unknown>;
  readonly mainBefore?: (fingerprint: Fingerprint) => unknown;
  /** 剧本跑完之后再动手（改 worktree、改主工作区）。 */
  readonly after?: (at: At) => void;
  readonly recover?: boolean;
  /** 有就起假端点，配置里补 decisions（on 模式、只启用 report-screen）。 */
  readonly replies?: readonly Reply[];
  /** 证据里应当出现的文字：文件的相对路径 → 片段。 */
  readonly shows?: Record<string, string | readonly string[]>;
  readonly crash?: boolean;
  /** 仓库目录名的前缀（缺省 col）。 */
  readonly prefix?: string;
  /** plan.md 的 Goal 一节。 */
  readonly goal?: string;
}

function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/"latency_ms": [0-9]+/gu, '"latency_ms": <MS>')
    .replace(/用时 [0-9]+ ms/gu, "用时 <MS> ms");
}

const scrubAll = (record: Record<string, string>): Record<string, string> =>
  Object.fromEntries(Object.entries(record).map(([key, value]) => [key, scrub(value)]));

const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

/** 一份中断了的 attempt：worktree 在仓库之外，Pi 的附件在另一个临时目录，stub_pi 在 worktree 里跑过剧本。 */
function buildAttempt(runner: Runner, item: Case, port: number | null): { repo: string; paths: Record<string, string> } {
  // 配置里有假端点的端口（三份实现各起一个），不进主工作区的指纹
  const ignored = [".agent/runs/", ".agent/dispatch.config.json", "build/", "*.log", ""];
  const { repo, head } = newRepo(`${item.prefix ?? "col"}-${runner}`, { ".gitignore": ignored.join(LF), "README.md": `# main${LF}` });
  put(repo, ".agent/plans/.keep", "");
  const decisions = port === null ? {} : { decisions: { mode: "on", base_url: `http://127.0.0.1:${port}`, api_key_env: KEY_NAME, points: ["report-screen"] } };
  put(repo, ".agent/dispatch.config.json", json({ kill_grace_seconds: 1, ...decisions, ...item.config }));
  const wtRoot = realpathSync.native(tempDir(`cwt-${runner}`));
  const wt = join(wtRoot, "wt");
  git(repo, "worktree", "add", "-q", "--detach", wt, head);
  const attach = realpathSync.native(tempDir(`catt-${runner}`));
  const data = jsonOf("t1", head);
  (data["scope"] as Json)["allowed_new_files"] = [...NEW_FILES];
  item.contract?.(data);
  const contractText = json(data);
  const planMd = mdOf("t1", head, { newFiles: NEW_FILES.join(", "), ...(item.goal === undefined ? {} : { goal: item.goal }) });
  const instruction = `执行说明：照合同做。${LF}`;
  put(attach, "plan.md", planMd);
  put(attach, "instruction.md", instruction);
  const fingerprint = { head, content_tree: treeOf(repo, head) };
  const started = {
    command: ["pi", "--mode", "json", `@${join(attach, "plan.md")}`, `@${join(attach, "instruction.md")}`], cwd: wt, timeout_seconds: 600,
    env_removed: [], started_at: AT, main_repo_before: item.mainBefore ? item.mainBefore(fingerprint) : fingerprint,
    expects_agent_settled: true, attachments_dir: attach,
  };
  const runDir = join(repo, ...RUN_REL.split("/"));
  const files: Record<string, unknown> = {
    "plan.md": planMd,
    "contract.json": contractText,
    "instruction.md": instruction,
    "meta.json": {
      task_id: "t1", plan_version: 1, plan_key: "t1.v1", attempt_no: 1, attempt_id: "t1.v1.a001", worktree: wt, base_sha: head, git_autocrlf: "false",
      plan_md_sha256: sha(planMd), contract_json_sha256: sha(contractText), kernel_protected: [], ...item.meta,
    },
    "executor.json": EXECUTOR,
    "claim/reservation.json": { timeout_seconds: 600, pid: DEAD_PID, at: AT },
    "ignored-before.json": [],
    "run-started.json": started,
    "state.json": { state: item.state ?? (item.finished ? "COLLECTING" : "RUNNING"), at: AT },
    "pid.txt": `${DEAD_PID}${LF}`,
    ...(item.finished ? { "run.json": { ...started, exit_code: 0, timed_out: false, interrupted: false, wall_seconds: 3.5, ended_at: AT, ...item.finished } } : {}),
    ...item.files,
  };
  for (const [rel, content] of Object.entries(files)) {
    if (content !== null) put(runDir, rel, typeof content === "string" ? content : json(content));
  }
  for (const [rel, content] of Object.entries(files)) if (content === null) rmSync(join(runDir, rel), { recursive: true, force: true });
  if (item.scenario !== null) {
    const stub = spawnSync(
      PYTHON,
      [STUB, "--mode", "json", "--provider", "step", "--model", "step-5-preview", "--thinking", "high", `@${join(attach, "plan.md")}`, `@${join(attach, "instruction.md")}`],
      { cwd: wt, env: { ...process.env, ...FIXED_DATES, STUB_SCENARIO: item.scenario ?? "ok", STUB_MAIN_REPO: repo }, timeout: 60_000 },
    );
    put(runDir, "events.jsonl", stub.stdout);
    put(runDir, "stderr.log", stub.stderr);
  }
  item.after?.({ repo, wt, runDir, head });
  return { repo, paths: { "<REPO>": repo, "<WT>": wt, "<WTROOT>": wtRoot, "<ATTACH>": attach } };
}

async function runCase(item: Case): Promise<void> {
  const results = [];
  for (const runner of RUNNERS as readonly Runner[]) {
    const endpoint = item.replies ? await startEndpoint(item.replies) : null;
    try {
      const { repo, paths } = buildAttempt(runner, item, endpoint?.port ?? null);
      const recover = item.recover ?? true;
      const argv = ["collect", RUN_REL, ...(recover ? ["--recover"] : [])];
      const result = runCommand(runner, repo, argv, { command: ["collect"], run_dir: RUN_REL, recover, context: TS_CONTEXT });
      const stderr = result.stderr.toString("utf8");
      results.push({
        status: result.status,
        stdout: item.crash ? "" : scrub(normalize(result.stdout.toString("utf8"), paths)),
        stderr: item.crash ? "" : scrub(normalize(stderr, paths)),
        crashed: item.crash ? crashed(stderr) : null,
        evidence: scrubAll(snapshotDir(join(repo, ".agent", "runs"), paths)),
        requests: endpoint ? scrub(normalize(JSON.stringify(endpoint.requests()), paths)) : "",
      });
    } finally {
      endpoint?.stop();
    }
  }
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify({ ...first, evidence: undefined })).toBe(item.status);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
  for (const [rel, wanted] of Object.entries(item.shows ?? {})) {
    const content = first.evidence[`t1/attempt-001/${rel}`];
    expect(content, `证据 ${rel}`).toBeDefined();
    for (const piece of typeof wanted === "string" ? [wanted] : wanted) expect(content, `证据 ${rel}`).toContain(piece);
  }
}

const SCREEN: Reply = {
  status: 200,
  body: JSON.stringify({
    answers: {
      claims_unsupported: { type: "noul", noul: 0.1 }, chose_interpretation: { type: "noul", noul: 0.8 }, scope_creep: { type: "noul", noul: 0.05 },
      weakened_tests: { type: "noul", noul: 0.02 }, severity: { type: "score", score: 2.5 },
    },
    usage: { input_tokens: 900, output_tokens: 12 }, model: "jev-test",
  }),
};
const ARABIC_VERSION = `pi ${String.fromCharCode(0x660)}.${String.fromCharCode(0x668, 0x660)}.${String.fromCharCode(0x664)}${LF}`;
const SUPERSCRIPT_TWO = String.fromCharCode(0xb2);
const NOT_STARTED = { "run-started.json": null, "pid.txt": null };
const RECOVERED = "（恢复收集；事件可能不完整）";

const CASES: Case[] = [
  // --- 最终状态 ---
  { label: "Pi 跑完、run.json 已写：NEEDS_REVIEW", status: 0, finished: {}, text: `NEEDS_REVIEW${RECOVERED}`,
    shows: {
      "state.json": '"state": "NEEDS_REVIEW"', "scope.json": ['"ok": true', '"head_after": '],
      "candidate.json": ['"patch_roundtrip_verified": true', '"unindexable_skipped": []'],
      "observations.json": ['"main_repo_changed": false', '"review_hints"', '"new_ignored_paths": []'],
      "history.jsonl": '"event": "recovered_collection"', "summary.md": "NEEDS_REVIEW",
    } },
  { label: "run.json 没写：按 run-started 补一份，CANCELLED", status: 0, text: `CANCELLED${RECOVERED}`,
    shows: { "run.json": ['"command": [', '"interrupted": true', '"recovered": true', '"spawn_error": null', '"expects_agent_settled": true'] } },
  { label: "超时：TIMEOUT", status: 0, finished: { timed_out: true, exit_code: null }, text: `TIMEOUT${RECOVERED}` },
  { label: "模型从未回复（启动失败）：INFRA_FAILURE", status: 0, scenario: "startfail", finished: { exit_code: 1 }, text: `INFRA_FAILURE${RECOVERED}` },
  { label: "领取之后还没启动 Pi：INFRA_FAILURE；pi 0.80.3 不发 agent_settled", status: 0, scenario: null, state: "PREPARED",
    files: { ...NOT_STARTED, "preflight/pi-version.txt": `pi 0.80.3${LF}` }, text: `INFRA_FAILURE${RECOVERED}`,
    shows: { "run.json": ['"spawn_error": "领取后调度器退出，未启动 Pi"', '"expects_agent_settled": false'] } },
  { label: "pi 的版本号用别的文字的数字写：照样认出 0.80.4", status: 0, scenario: null, files: { ...NOT_STARTED, "preflight/pi-version.txt": ARABIC_VERSION },
    shows: { "run.json": '"expects_agent_settled": true' } },
  { label: "读不出 pi 的版本：不知道会不会发 agent_settled", status: 0, scenario: null, files: NOT_STARTED,
    shows: { "run.json": '"expects_agent_settled": null' } },
  // --- 不能恢复 ---
  { label: "已经结束的 attempt：用法错误", status: 2, scenario: null, state: "NEEDS_REVIEW", text: "（当前 NEEDS_REVIEW）。" },
  { label: "没领取的 PREPARED：用法错误", status: 2, scenario: null, state: "PREPARED", files: { claim: null }, text: "（当前 PREPARED）。" },
  { label: "没加 --recover：用法错误", status: 2, recover: false, text: "collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）且指定 --recover（当前 RUNNING）。" },
  { label: "planner-v2 的合同没有发布记录", status: 3, scenario: null, contract: (data) => void (data["contract_family"] = "planner-v2"),
    text: "planner-v2 发布门禁拒绝恢复收集" },
  { label: "pid.txt 不是数字：当作没有记录", status: 0, finished: {}, files: { "pid.txt": `abc${LF}` }, text: `NEEDS_REVIEW${RECOVERED}` },
  { label: "记录的 Pi 进程还活着", status: 3, files: { "pid.txt": `${process.pid}${LF}` }, text: "可能仍在运行；确认终止后再恢复。" },
  { label: "pid.txt 是上标数字：照 Python 崩", status: 1, files: { "pid.txt": SUPERSCRIPT_TWO }, crash: true },
  { label: "run.json 是列表：照 Python 崩", status: 1, files: { "run.json": [] }, crash: true },
  // --- 上次收集留下的半成品 ---
  { label: "半成品改名成 .partial 再重收", status: 0, finished: {},
    files: { "candidate.json": { tree: "x" }, "scope.json": { ok: false }, "candidate.patch": "old" },
    shows: { "candidate.json.partial": '"tree": "x"', "scope.json.partial": '"ok": false', "candidate.patch.partial": "old" } },
  { label: ".partial 已经有了：照 Python 崩", status: 1, files: { "candidate.json": { tree: "x" }, "candidate.json.partial": { tree: "y" } }, crash: true },
  // --- 范围 ---
  { label: "越界、依赖与敏感文件（scope 剧本）", status: 0, scenario: "scope", finished: {},
    shows: { "scope.json": ['"kind": "out_of_scope"', '"kind": "dependency_change"', '"kind": "sensitive_file"', '"ok": false'] } },
  { label: "合同点名允许 package.json：依赖变更只提醒", status: 0, scenario: "scope", finished: {},
    contract: (data) => void ((data["scope"] as Json)["allowed_new_files"] = [...NEW_FILES, "package.json"]),
    shows: { "scope.json": '"kind": "dependency_manifest_changed"' } },
  { label: "执行器提交了：HEAD 移动是违规", status: 0, scenario: "commit", finished: {}, shows: { "scope.json": ['"kind": "head_moved"', '"ok": false'] } },
  { label: "合同授权 local_commit：HEAD 移动只提醒", status: 0, scenario: "commit", finished: {},
    contract: (data) => void ((data["authorization"] as Json)["executor"] = ["local_edit", "local_test", "local_commit"]),
    shows: { "scope.json": ['"kind": "head_moved"', '"ok": true'] } },
  { label: "禁区、受保护（不分大小写）、内核禁区、删除与二进制文件", status: 0, finished: {},
    config: { extra_protected_paths: ["notes/**", "Docs2/**"] }, meta: { kernel_protected: ["ts/**"] },
    contract: (data) => void ((data["scope"] as Json)["forbidden_paths"] = ["docs/**"]),
    after: ({ wt }) => {
      put(wt, "docs/x.md", "x");
      put(wt, "docs2/y.md", "y");
      put(wt, "AGENTS.md", "changed");
      put(wt, "notes/n.md", "n");
      put(wt, "ts/k.ts", "k");
      put(wt, "src/img.bin", Uint8Array.from({ length: 256 }, (_, index) => index));
      rmSync(join(wt, "src", "a.ts"));
    },
    shows: {
      "scope.json": ['"kind": "forbidden_path"', '"kind": "protected_path"', '"path": "notes/n.md"', '"path": "ts/k.ts"', '"path": "docs2/y.md"', '"detail": "状态 D 不在允许集合"'],
      "candidate.json": '"patch_roundtrip_verified": true', "candidate.patch": "GIT binary patch",
    } },
  { label: "合同允许依赖变更：package.json 不算违规", status: 0, scenario: "scope", finished: {},
    contract: (data) => void ((data["scope"] as Json)["dependency_changes"] = "allowed"), shows: { "scope.json": '"path": "package.json"' } },
  { label: "extra_protected_paths 写错：collect_errors，INFRA_FAILURE", status: 0, finished: {}, config: { extra_protected_paths: "notes" },
    text: `INFRA_FAILURE${RECOVERED}`, shows: { "observations.json": '"collect_errors": [' } },
  // --- 主工作区 ---
  { label: "执行器改了主工作区已跟踪的文件", status: 0, scenario: "touchmain", finished: {},
    shows: { "observations.json": ['"main_repo_changed": true', '"M README.md"'] } },
  { label: "规划端在运行期间写了新合同", status: 0, scenario: "planner", finished: {}, shows: { "observations.json": '"A .agent/plans/next-task.v1.md"' } },
  { label: "主工作区在运行期间有了新提交", status: 0, finished: {},
    after: ({ repo }) => {
      put(repo, "c.txt", "c");
      git(repo, "add", "c.txt");
      git(repo, "commit", "-q", "-m", "c");
    },
    shows: { "observations.json": ['"head_changed": true', '"A c.txt"'] } },
  { label: "主工作区新增了未跟踪的文件", status: 0, finished: {}, after: ({ repo }) => put(repo, "new.txt", "n"),
    shows: { "observations.json": ['"main_repo_changed": true', '"A new.txt"'] } },
  { label: "主工作区只动了被忽略的文件：不算变化", status: 0, finished: {}, after: ({ repo }) => put(repo, "build/x.txt", "x"),
    shows: { "observations.json": '"main_repo_changed": false' } },
  { label: "仓库目录名带中文", status: 0, finished: {}, prefix: "收集", scenario: "touchmain", text: `NEEDS_REVIEW${RECOVERED}`,
    shows: { "observations.json": '"M README.md"' } },
  { label: "运行前的指纹不完整", status: 0, scenario: "touchmain", finished: {}, mainBefore: (fp) => ({ ...fp, content_tree: "error: x" }),
    shows: { "observations.json": "指纹不完整，无法列出变化的路径" } },
  { label: "运行期间主工作区的 HEAD 变了", status: 0, finished: {}, mainBefore: (fp) => ({ ...fp, head: "0".repeat(40) }),
    shows: { "observations.json": '"head_changed": true' } },
  { label: "planner_paths 在 Windows 上不分大小写", status: 0, finished: {}, config: { planner_paths: ["Docs/**"] },
    after: ({ repo }) => put(repo, "docs/p.md", "p"), shows: { "observations.json": '"A docs/p.md"' } },
  { label: "planner_paths 写错：只记 diff_error", status: 0, scenario: "touchmain", finished: {}, config: { planner_paths: "docs" },
    shows: { "observations.json": '"diff_error": ' } },
  // --- 忽略的新路径 ---
  { label: "运行期间新出现的被忽略路径", status: 0, finished: {}, files: { "ignored-before.json": ["x.log"] },
    after: ({ wt }) => {
      put(wt, "build/out.txt", "o");
      put(wt, "x.log", "x");
      put(wt, "y.log", "y");
    },
    shows: { "observations.json": ['"build/"', '"y.log"'] } },
  { label: "ignored-before.json 是 null：照 Python 崩", status: 1, finished: {}, files: { "ignored-before.json": null }, after: ({ runDir }) => put(runDir, "ignored-before.json", "null"), crash: true },
  { label: "worktree 已经不在：照 Python 崩", status: 1, finished: {}, after: ({ repo, wt }) => void git(repo, "worktree", "remove", "--force", wt), crash: true },
  // --- 事件 ---
  { label: "执行器读附件里的 plan.md：不算越界", status: 0, scenario: "readplan", finished: {}, shows: { "events-summary.json": '"outside_worktree_paths": []' } },
  { label: "合同自己两次提到 ambiguous：执行器说 ambiguous 不算歧义提示", status: 0, scenario: "ambiguous", finished: {},
    goal: "把 ambiguous 的旧写法改成新写法，ambiguous 这个词本身保留。",
    shows: { "events-summary.json": ['"ambiguity_mention_count": 0', '"ambigu"'] } },
  { label: "旧版 pi 不发 agent_settled：按 agent_end 判断", status: 0, scenario: "nosettle", finished: { expects_agent_settled: false }, text: `NEEDS_REVIEW${RECOVERED}` },
  // --- 决策 ---
  { label: "决策 on：筛查执行报告（报告里有矛盾）", status: 0, scenario: "conflict", finished: {}, replies: [SCREEN],
    contract: (data) => void (data["definition_of_done"] = [{ id: "D01", text: "行为正确", evidence: ["V01"], intent: "空白归一" }]),
    shows: { "observations.json": '"report_screen": "answered"', "decisions.jsonl": '"point": "report-screen"' } },
  { label: "决策端点 500：记 no_opinion", status: 0, finished: {}, replies: [{ status: 500, body: "{}" }],
    shows: { "observations.json": '"report_screen": "no_opinion"' } },
  { label: "决策配置写错：只记 decisions_error", status: 0, finished: {}, config: { decisions: { mode: "loud" } },
    shows: { "observations.json": '"decisions_error": ' } },
];

describe("collect --recover", () => {
  for (const item of CASES) it(item.label, () => runCase(item), 240_000);
});
