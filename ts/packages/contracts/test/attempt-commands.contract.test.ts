// mark、cleanup、wait 的命令行契约（迁移第 ④b2 片）。每个场景按三份实现各建一份相同的仓库与证据目录（提交号相同，
// 工作树路径各不相同、换成占位符），跑同一条命令，比较退出码、输出与跑完之后的证据目录；崩溃只比退出码。
// cleanup 的场景用真的 git worktree：干净的、改过文件的、多了新文件与缓存的、没有候选记录的、补丁缺失的、配置有疑似凭据的、
// 目录在却没登记的、已经不在的，以及保留下来的验收副本。不写转义序列。
import { createHash } from "node:crypto";
import { mkdirSync, realpathSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { jsonOf } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, type Shown, git, newRepo, put, removeCreated, runCommand, shownOf, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const json = (value: unknown): string => `${JSON.stringify(value, null, 2)}${LF}`;
const EMPTY_SHA = createHash("sha256").update("").digest("hex");

interface Built {
  readonly repo: string;
  readonly paths: Record<string, string>;
}

interface Scenario {
  readonly label: string;
  readonly build: (repo: string, head: string, runner: Runner) => Record<string, string>;
  readonly argv: readonly string[];
  readonly args: Record<string, unknown>;
  readonly status: number;
  readonly crash?: boolean;
  /** 输出里必须有的文字：证明走到了要测的分支，不是碰巧状态码对上。 */
  readonly text?: string;
}

/** .agent/runs/<task>/attempt-001：以 / 结尾的键建空目录，字符串原样写，其余写成 JSON。 */
function attempt(repo: string, files: Record<string, unknown>, task = "t1"): string {
  const dir = join(repo, ".agent", "runs", task, "attempt-001");
  mkdirSync(dir, { recursive: true });
  for (const [rel, content] of Object.entries(files)) {
    if (rel.endsWith("/")) mkdirSync(join(dir, rel), { recursive: true });
    else put(dir, rel, typeof content === "string" ? content : json(content));
  }
  return dir;
}

const state = (value: string): Record<string, unknown> => ({ state: value, at: "2026-01-01T00:00:00Z" });

function meta(head: string, worktree: string): Record<string, unknown> {
  return { task_id: "t1", plan_version: 1, attempt_no: 1, worktree, base_sha: head, git_autocrlf: "false" };
}

/** 在 HEAD 上建一个登记的工作树（路径在仓库之外；用长路径：git worktree list 打印的是长路径，8.3 短名对不上）。 */
function worktree(repo: string, head: string, label: string): string {
  const dir = realpathSync.native(tempDir(label));
  git(repo, "worktree", "add", "-q", "--detach", dir, head);
  return dir;
}

/** 一个干净工作树的 attempt：候选就是基线的树，补丁为空并做过往返校验。 */
function cleanAttempt(repo: string, head: string, label: string, extra: Record<string, unknown> = {}): string {
  const wt = worktree(repo, head, label);
  attempt(repo, {
    "meta.json": meta(head, wt), "state.json": state("PASS"), "contract.json": jsonOf("t1", head),
    "candidate.json": { tree: git(repo, "rev-parse", `${head}^{tree}`), patch_roundtrip_verified: true, patch_sha256: EMPTY_SHA },
    "candidate.patch": "", ...extra,
  });
  return wt;
}

const mark = (label: string, files: (head: string) => Record<string, unknown>, flags: { state: string; ref?: string; reason?: string; force?: boolean; runDir?: string },
  status: number, crash = false): Scenario => ({
  label,
  build: (repo, head) => {
    attempt(repo, { "meta.json": meta(head, ""), "contract.json": jsonOf("t1", head), ...files(head) });
    return {};
  },
  argv: ["mark", flags.runDir ?? "t1", flags.state, ...(flags.ref ? ["--ref", flags.ref] : []), ...(flags.reason ? ["--reason", flags.reason] : []),
    ...(flags.force ? ["--force"] : [])],
  args: { command: ["mark"], run_dir: flags.runDir ?? "t1", state: flags.state, ref: flags.ref ?? null, reason: flags.reason ?? null, force: flags.force ?? false },
  status,
  crash,
});

const cleanup = (label: string, build: Scenario["build"], status: number, force = false, crash = false): Scenario => ({
  label, build, argv: ["cleanup", "t1", ...(force ? ["--force"] : [])], args: { command: ["cleanup"], run_dir: "t1", force }, status, crash,
});

const wait = (label: string, files: Record<string, unknown>, timeout: number, status: number): Scenario => ({
  label,
  build: (repo) => {
    attempt(repo, files);
    return {};
  },
  argv: ["wait", "t1", "--timeout", String(timeout), "--interval", "0.3"],
  args: { command: ["wait"], run_dir: "t1", timeout: BigInt(timeout), interval: 0.3, assess: false, assess_interval: 60.0 },
  status,
});

const EVENTS = ['{"type":"tool_execution_end"}', '{"type":"message_update"}', '{"type":"tool_execution_end"}', '{"type":"message_update"}'].join(LF);

const SCENARIOS: Scenario[] = [
  mark("INTEGRATED，验收通过", () => ({ "state.json": state("PASS"), "verdicts/01.json": { verdict: "PASS" } }), { state: "INTEGRATED", ref: "abc123" }, 0),
  mark("INTEGRATED，验收没通过", () => ({ "state.json": state("REVISE"), "verdicts/01.json": { verdict: "REVISE" } }), { state: "INTEGRATED", ref: "abc" }, 3),
  mark("INTEGRATED，缺 ref", () => ({ "state.json": state("PASS"), "verdicts/02.json": { verdict: "ACCEPTED_WITH_EXCEPTION" } }), { state: "INTEGRATED" }, 2),
  mark("INTEGRATED，结论文件是列表", () => ({ "state.json": state("PASS"), "verdicts/01.json": [] }), { state: "INTEGRATED", ref: "x" }, 1, true),
  mark("SUPERSEDED", () => ({ "state.json": state("REVISE") }), { state: "SUPERSEDED", ref: "r1", reason: "返工后一起集成" }, 0),
  mark("SUPERSEDED，状态不对", () => ({ "state.json": state("PASS") }), { state: "SUPERSEDED", ref: "r1", reason: "x" }, 2),
  mark("SUPERSEDED，缺 reason", () => ({ "state.json": state("TIMEOUT") }), { state: "SUPERSEDED", ref: "r1" }, 2),
  mark("放弃 RUNNING，不加 force", () => ({ "state.json": state("RUNNING") }), { state: "ABANDONED" }, 3),
  mark("放弃 RUNNING，记录的进程还活着", () => ({ "state.json": state("RUNNING"), "pid.txt": `${process.pid}${LF}` }), { state: "ABANDONED", force: true }, 3),
  mark("放弃 RUNNING，记录的进程不在", () => ({ "state.json": state("COLLECTING"), "pid.txt": "99999999" }), { state: "ABANDONED", force: true, reason: "调度器已退出" }, 0),
  mark("放弃 RUNNING，pid 是 0 与非数字", () => ({ "state.json": state("PREPARING"), "pid.txt": "pid?" }), { state: "ABANDONED", force: true }, 0),
  mark("放弃 RUNNING，pid 是上标数字", () => ({ "state.json": state("RUNNING"), "pid.txt": String.fromCodePoint(0xb2) }), { state: "ABANDONED", force: true }, 1, true),
  mark("放弃 PREPARED，路径写法", () => ({ "state.json": state("PREPARED") }), { state: "ABANDONED", runDir: ".agent/runs/t1/attempt-001" }, 0),
  mark("找不到 attempt", () => ({ "state.json": state("PASS") }), { state: "ABANDONED", runDir: "nope" }, 2),

  cleanup("RUNNING 不能清理", (repo, head) => {
    attempt(repo, { "meta.json": meta(head, "x"), "state.json": state("RUNNING"), "contract.json": jsonOf("t1", head) });
    return {};
  }, 3),
  cleanup("PREPARED 不加 force", (repo, head) => {
    attempt(repo, { "meta.json": meta(head, "x"), "state.json": state("PREPARED"), "contract.json": jsonOf("t1", head) });
    return {};
  }, 3),
  cleanup("干净的工作树", (repo, head, runner) => ({ "<WT>": cleanAttempt(repo, head, `cl-clean-${runner}`) }), 0),
  cleanup("改过候选里的文件", (repo, head, runner) => {
    const wt = cleanAttempt(repo, head, `cl-mod-${runner}`);
    put(wt, "src/a.ts", `export const a = 2;${LF}`);
    return { "<WT>": wt };
  }, 3),
  cleanup("改过候选里的文件，force", (repo, head, runner) => {
    const wt = cleanAttempt(repo, head, `cl-modf-${runner}`);
    put(wt, "src/a.ts", `export const a = 2;${LF}`);
    return { "<WT>": wt };
  }, 0, true),
  cleanup("多了新文件与缓存", (repo, head, runner) => {
    const wt = cleanAttempt(repo, head, `cl-new-${runner}`);
    put(wt, "notes/x.txt", "x");
    put(wt, "pkg/__pycache__/m.cpython-312.pyc", "c");
    return { "<WT>": wt };
  }, 3),
  cleanup("没有候选记录", (repo, head, runner) => {
    const wt = worktree(repo, head, `cl-nocand-${runner}`);
    attempt(repo, { "meta.json": meta(head, wt), "state.json": state("REVISE"), "contract.json": jsonOf("t1", head) });
    return { "<WT>": wt };
  }, 3),
  cleanup("补丁缺失", (repo, head, runner) => {
    const wt = cleanAttempt(repo, head, `cl-nopatch-${runner}`);
    put(join(repo, ".agent", "runs", "t1", "attempt-001"), "candidate.patch", "changed");
    return { "<WT>": wt };
  }, 3),
  cleanup("配置有疑似凭据", (repo, head, runner) => {
    const wt = cleanAttempt(repo, head, `cl-secret-${runner}`);
    put(repo, ".agent/dispatch.config.json", JSON.stringify({ github_token: "abc" }));
    return { "<WT>": wt };
  }, 3),
  cleanup("目录在，却不是登记的工作树", (repo, head, runner) => {
    const dir = tempDir(`cl-stray-${runner}`);
    put(dir, "keep.txt", "k");
    attempt(repo, { "meta.json": meta(head, dir), "state.json": state("PASS"), "contract.json": jsonOf("t1", head) });
    return { "<WT>": dir };
  }, 3),
  cleanup("工作树已经不在，保留的验收副本一并移除", (repo, head, runner) => {
    const ws = worktree(repo, head, `cl-ws-${runner}`);
    const gone = join(tempDir(`cl-gone-${runner}`), "gone");
    attempt(repo, {
      "meta.json": meta(head, gone), "state.json": state("PASS"), "contract.json": jsonOf("t1", head),
      "checks/01/checks.json": { workspace: ws, workspace_kept: true }, "checks/02/checks.json": { workspace: ws, workspace_kept: false },
    });
    return { "<WT>": gone, "<WS>": ws };
  }, 0),
  cleanup("缺 meta.json", (repo, head) => {
    attempt(repo, { "state.json": state("PASS"), "contract.json": jsonOf("t1", head) });
    return {};
  }, 1, false, true),

  wait("已经结束", { "state.json": state("PASS"), "summary.md": "# 摘要" }, 5, 0),
  wait("还在跑，到时", { "state.json": state("RUNNING"), "events.jsonl": EVENTS }, 1, 3),
  wait("PREPARED 没有开始", { "state.json": state("PREPARED") }, 1, 3),
  wait("状态未知", { "run.json": {} }, 1, 1),
  { ...wait("timeout 不是正数", { "state.json": state("PASS") }, 0, 2) },
];

/** 各场景输出里必须有的文字（证明走到了要测的分支）。 */
const TEXTS: Record<string, string> = {
  "INTEGRATED，验收通过": "已标记为 INTEGRATED",
  "INTEGRATED，验收没通过": "只有通过验收的候选可以标记为 INTEGRATED",
  "SUPERSEDED": "已标记为 SUPERSEDED",
  "放弃 RUNNING，记录的进程还活着": "仍在运行，不能放弃",
  "放弃 RUNNING，记录的进程不在": "已标记为 ABANDONED",
  "干净的工作树": "已移除 worktree：<WT>",
  "改过候选里的文件": "LOSS  候选记录之后被修改的文件：src/a.ts",
  "改过候选里的文件，force": "已移除 worktree：<WT>",
  "多了新文件与缓存": "LOSS  候选之外的新文件：notes/x.txt" + String.fromCharCode(13) + "",
  "没有候选记录": "LOSS  没有候选记录",
  "补丁缺失": "LOSS  候选补丁缺失",
  "配置有疑似凭据": "LOSS  无法核对 worktree 内容",
  "目录在，却不是登记的工作树": "存在但不是本仓库登记的 worktree",
  "工作树已经不在，保留的验收副本一并移除": "已移除验收副本：<WS>",
  "已经结束": "摘要：.agent/runs/t1/attempt-001/summary.md",
  "还在跑，到时": "· RUNNING · live:2t",
  "PREPARED 没有开始": "attempt 仍是 PREPARED",
  "状态未知": "无法确定 attempt 的状态（UNKNOWN）",
};

describe("mark、cleanup、wait", () => {
  for (const scenario of SCENARIOS) {
    it(scenario.label, () => {
      const results = RUNNERS.map((runner) => {
        const { repo, head } = newRepo(`att-${runner}`);
        const paths = { "<REPO>": repo, ...scenario.build(repo, head, runner) };
        const result = runCommand(runner, repo, scenario.argv, scenario.args);
        const shown: Shown = shownOf(result, paths, scenario.crash);
        const evidence = scenario.crash ? {} : snapshotDir(join(repo, ".agent", "runs"), paths);
        const worktrees = scenario.crash ? "" : git(repo, "worktree", "list", "--porcelain").split(LF).filter((line) => line.startsWith("worktree ")).length;
        return { ...shown, evidence, worktrees };
      });
      for (const result of results.slice(1)) expect(result).toEqual(results[0]);
      expect((results[0] as Shown).status, JSON.stringify(results[0])).toBe(scenario.status);
      const text = scenario.text ?? TEXTS[scenario.label];
      if (text) expect(`${(results[0] as Shown).stdout}${(results[0] as Shown).stderr}`).toContain(text);
    });
  }
});
