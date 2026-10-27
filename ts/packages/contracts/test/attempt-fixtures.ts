// 命令行契约用的 attempt 夹具（迁移第 ④b3 片写在 check 的契约里，④b5b 挪出来给 mutate 共用）：一份各门禁都能通过的
// attempt（真的 git worktree、候选树与做过往返校验的补丁、合同与执行的证据），检查项的写法，本机的 platform.platform()。
// 不写转义序列。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { realpathSync, rmSync } from "node:fs";
import { join } from "node:path";
import { jsonOf, mdOf } from "./plan-fixtures.ts";
import { CONTEXT, LF, type Runner, git, put, tempDir } from "./repo-fixtures.ts";

export const json = (value: unknown): string => `${JSON.stringify(value, null, 2)}${LF}`;

export const sha = (data: string | Uint8Array): string => createHash("sha256").update(data).digest("hex");

export const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";

/** 本机的 platform.platform()：启动器交给 TS 的 context 里就是它（迁移计划 D1）。 */
export const PLATFORM = spawnSync(PYTHON, ["-c", "import platform; print(platform.platform())"], { encoding: "utf8" }).stdout.trim();
export const TS_CONTEXT = { ...CONTEXT, platform: PLATFORM };

export const state = (value: string): Record<string, unknown> => ({ state: value, at: "2026-01-01T00:00:00Z" });

/** 检查项：python -c 的一段程序。 */
export function py(id: string, code: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { id, argv: ["python", "-c", code], cwd: ".", timeout_seconds: 60, required: true, expected_exit_code: 0, expect_on_base: "any", ...extra };
}

export const OK = (id = "V01", extra: Record<string, unknown> = {}): Record<string, unknown> => py(id, "print('ok')", extra);

export const FAIL = (id = "V01", extra: Record<string, unknown> = {}): Record<string, unknown> => py(id, "import sys; print('boom'); sys.exit(1)", extra);

export interface AttemptOptions {
  readonly checks?: readonly Record<string, unknown>[];
  readonly setup?: readonly Record<string, unknown>[];
  readonly dod?: readonly Record<string, unknown>[];
  readonly contract?: Record<string, unknown>;
  readonly meta?: Record<string, unknown>;
  /** 证据文件：null 删掉，字符串原样写，其余写成 JSON。 */
  readonly files?: Record<string, unknown>;
  readonly config?: Record<string, unknown>;
  /** 证据写好之后再动手（改工作树、改补丁）。 */
  readonly after?: (at: { repo: string; wt: string; runDir: string; head: string }) => void;
  readonly review?: string;
  /** 候选里另外改动或新加的文件（算进候选树与补丁）。 */
  readonly candidateFiles?: Record<string, string | Uint8Array>;
}

/** 用临时索引求工作树的完整内容（已跟踪 + 未忽略的新文件），照 snapshot_tree。 */
export function treeOf(wt: string, head: string): string {
  const env = { ...process.env, GIT_INDEX_FILE: join(tempDir("idx"), "candidate.index") };
  const run = (...args: string[]): string => {
    const done = spawnSync("git", ["-c", "core.autocrlf=false", ...args], { cwd: wt, env, encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
    return done.stdout.trim();
  };
  run("read-tree", head);
  run("add", "-A");
  return run("write-tree");
}

/**
 * 一份各门禁都能通过的 attempt：工作树在基线上把 src/a.ts 改成 a = 2，候选就是它，补丁做过往返校验；合同、执行、
 * 范围、检查记录的证据齐全。工作树与 worktree_root 在仓库之外（长路径）；仓库里另有复审报告 review.md。
 */
export function fullAttempt(repo: string, head: string, runner: Runner, o: AttemptOptions = {}): Record<string, string> {
  const wtRoot = realpathSync.native(tempDir(`wtr-${runner}`));
  const wt = join(wtRoot, "wt");
  git(repo, "worktree", "add", "-q", "--detach", wt, head);
  put(wt, "src/a.ts", `export const a = 2;${LF}`);
  for (const [rel, content] of Object.entries(o.candidateFiles ?? {})) put(wt, rel, content);
  const tree = treeOf(wt, head);
  const patch = spawnSync("git", ["diff", "--binary", "--full-index", head, tree], { cwd: repo }).stdout;
  const contract = {
    ...jsonOf("t1", head), checks: o.checks ?? [OK()], setup: o.setup ?? [],
    definition_of_done: o.dod ?? [{ id: "D01", text: "行为正确", evidence: ["V01"] }], ...o.contract,
  };
  const planMd = mdOf("t1", head);
  const contractJson = json(contract);
  const runDir = join(repo, ".agent", "runs", "t1", "attempt-001");
  const files: Record<string, unknown> = {
    "plan.md": planMd,
    "contract.json": contractJson,
    "meta.json": {
      task_id: "t1", plan_version: 1, attempt_no: 1, worktree: wt, base_sha: head, git_autocrlf: "false",
      plan_md_sha256: sha(planMd), contract_json_sha256: sha(contractJson), platform: PLATFORM, repository: realpathSync.native(repo), ...o.meta,
    },
    "state.json": state("NEEDS_REVIEW"),
    "run.json": { exit_code: 0, timed_out: false, interrupted: false },
    "events-summary.json": { problems: [], provider_thinking_levels: ["high"], requested_model: { thinking: "high" }, outside_worktree_paths: [], ambiguity_mention_count: 0 },
    "report-status.json": { status: "json_ok" },
    "scope.json": { violations: [] },
    "observations.json": { main_repo_changes: { head_changed: false, other_paths: [] } },
    "candidate.json": { tree, patch_roundtrip_verified: true, patch_sha256: sha(patch) },
    "candidate.patch": patch,
    "checks/01/checks.json": { run: 1, mode: "in_place", candidate_tree: tree, covers_all_required: true, results: [{ id: "V01", required: true, passed: true, status: "passed" }] },
    ...o.files,
  };
  for (const [rel, content] of Object.entries(files)) {
    if (content === null) continue;
    put(runDir, rel, typeof content === "string" || content instanceof Uint8Array ? content : json(content));
  }
  for (const [rel, content] of Object.entries(files)) if (content === null) rmSync(join(runDir, rel), { recursive: true, force: true });
  put(repo, ".agent/dispatch.config.json", json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...o.config }));
  put(repo, "review.md", o.review ?? `# 复审${LF}${LF}Verdict: PASS${LF}`);
  o.after?.({ repo, wt, runDir, head });
  return { "<WT>": wt, "<WTROOT>": wtRoot };
}

/**
 * D2（迁移计划第 ④ 步）：命令跑到一半，它的进程组收到 CTRL_BREAK。照 supervise 契约的 S10：外层以 CREATE_NO_WINDOW
 * 起一个不显示窗口的控制台，内层另起进程组跑命令，读到标记那一行（第三个参数）、再等一秒，给命令的进程组发 CTRL_BREAK。
 * Python 的 run_supervised 与 TS 的 runSupervised 都把它当中断。
 */
export const BREAK_INNER = [
  "import json, signal, subprocess, sys, time",
  "marker = sys.argv[3].encode('utf-8')",
  "p = subprocess.Popen(json.loads(sys.argv[1]), cwd=sys.argv[2], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x200)",
  "deadline = time.monotonic() + 60",
  "seen = b''",
  "while marker not in seen:",
  "    line = p.stdout.readline()",
  "    if not line or time.monotonic() > deadline:",
  "        p.kill(); sys.exit('没等到 ' + sys.argv[3])",
  "    seen += line",
  "time.sleep(1)",
  "p.send_signal(signal.CTRL_BREAK_EVENT)",
  "out, err = p.communicate()",
  "sys.stdout.write(json.dumps({'status': p.returncode, 'stdout': (seen + out).decode('utf-8', 'replace'), 'stderr': err.decode('utf-8', 'replace')}))",
].join(LF);
export const BREAK_OUTER = [
  "import os, subprocess, sys",
  "p = subprocess.Popen([sys.executable, '-c'] + sys.argv[1:], stdout=subprocess.PIPE, creationflags=0x08000000)",
  "try:",
  "    out, _ = p.communicate(timeout=120)",
  "except subprocess.TimeoutExpired:",
  "    taskkill = os.path.join(os.environ['SystemRoot'], 'System32', 'taskkill.exe')",
  "    subprocess.run([taskkill, '/T', '/F', '/PID', str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
  "    p.communicate()",
  "    sys.exit('内层 120 秒没结束，已结束整棵树')",
  "sys.stdout.buffer.write(out)",
].join(LF);
