// “Python 开跑、TS 收尾”（切换 c2；迁移计划 ④-切换 c）：切换那一刻，Python 已经 prepare 好的 attempt 由 TS 接着跑完。
// 每条链先用 Python 的 prepare 建 attempt（四边相同），之后的每一步都由同一种 runner 跑。四种 runner 比每一步的退出码、两路
// 输出与 .agent/runs 下的证据，以及最后的分支、提交与主工作区的 HEAD。每一步之后，再用 hub 在进程内调的 pi_dispatch 函数
// （get_state、budget_usage、_running_attempts；check 的输出用 _CHECK_LINE_RE）读一遍：第 ⑤ 步之前 hub 还是 Python，要读懂
// TS 写的证据。另一条链：Python 的 run 跑到一半，调度器被硬杀，由各 runner 的 collect --recover 收尾。pi 一律是 stub_pi。
// 不写转义序列。
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { PYTHON, json, sha } from "./attempt-fixtures.ts";
import { REPO as KIT, pythonCliCommand, runPythonCli } from "./harness.ts";
import { type Json, jsonOf, mdOf } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, pyargsOf, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const STUB = join(KIT, "tests", "stub_pi.py");
const RUN_REL = ".agent/runs/t1/attempt-001";
const NEW_FILES = ["src/normalize.py", "tests/test_normalize.py"];
const AGENT_DIR = realpathSync.native(tempDir("ch-agent"));
const IDENTITY = {
  GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-02T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-02T00:00:00+00:00",
};
const HUB_VIEW = [
  "import json, sys",
  `sys.path.insert(0, ${JSON.stringify(join(KIT, "scripts"))})`,
  "import pi_dispatch as pd",
  "repo = pd.Repo(pd.Path(sys.argv[1]))",
  "run_dir = repo.runs_dir / 't1' / 'attempt-001'",
  "lines = open(sys.argv[2], encoding='utf-8').read().splitlines()",
  "print(json.dumps({'state': pd.get_state(run_dir), 'budget': pd.budget_usage(repo, 't1'), 'running': pd._running_attempts(repo),",
  "                  'check_lines': [line.strip() for line in lines if pd._CHECK_LINE_RE.match(line.strip())]}, default=str))",
].join(LF);

function withEnv<T>(env: Record<string, string>, body: () => T): T {
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  Object.assign(process.env, env);
  try {
    return body();
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/"latency_ms": [0-9]+/gu, '"latency_ms": <MS>')
    .replace(/"log_sha256": "[0-9a-f]{64}"/gu, '"log_sha256": <SHA>')
    .replace(/用时 [0-9]+ ms/gu, "用时 <MS> ms")
    .replace(/用时 [0-9]+[.][0-9]+s/gu, "用时 <S>s")
    .replace(/ in [0-9.]+s/gu, " in <S>s")
    .replace(/pi-attach-[a-z0-9_]{8}/gu, "pi-attach-<R>")
    .replace(/-integrate-[a-z0-9_]{8}/gu, "-integrate-<R>") // integrate 验证副本的 mkdtemp 后缀
    .replace(/-verify-[a-z0-9_]{8}/gu, "-verify-<R>") // check --fresh 干净副本的 mkdtemp 后缀
    .replace(/(instruction[.]md",[^"]*"sha256": ")[0-9a-f]{64}/gu, "$1<SHA>")
    .replace(/^[0-9]+$/gmu, "<PID>");
}

/** Python 的 prepare 建好的 attempt：合同允许新建 stub_pi 写的两个文件、授权 local_branch 与 merge（integrate 才落地）；仓库根的 conftest.py 让 pytest 找得到 src。 */
interface Prepared {
  /** prepare 之前把仓库的 core.autocrlf 设成 true（meta 记下 git_autocrlf: "true"）。 */
  readonly autocrlf?: boolean;
  /** 按角色写的合同（role:execution），配置里有 execution 的 headless 绑定，prepare 发布版本记录。 */
  readonly role?: boolean;
}

const BOUND = {
  runtimes: { pi: { adapter: "pi" } },
  profiles: { exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options: { thinking: "high" }, credential_env: ["STEP_KEY"] } },
  roles: { execution: { mode: "headless", profile: "exec" } },
};

function preparedRepo(runner: Runner, o: Prepared = {}): { repo: string; paths: Record<string, string> } {
  const { repo, head } = newRepo(`ch-${runner}`, {
    ".gitignore": [".agent/runs/", ".agent/dispatch.config.json", "review.md", "__pycache__/", ".pytest_cache/", "child.pid", ""].join(LF),
    "conftest.py": ["import os", "import sys", "", "sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))", ""].join(LF),
  });
  const data = jsonOf("t1", head);
  (data["scope"] as Json)["allowed_new_files"] = NEW_FILES;
  (data["authorization"] as Json)["integration"] = ["local_branch", "merge"];
  if (o.role) data["executor"] = { role: "execution", tools: ["read", "edit", "bash"], context_files: "project" };
  put(repo, ".agent/plans/t1.v1.md", mdOf("t1", head, {
    newFiles: NEW_FILES.join(", "), integration: "local_branch, merge", ...(o.role ? { executor: "role:execution" } : {}),
  }));
  put(repo, ".agent/plans/t1.v1.json", json(data));
  const wtRoot = realpathSync.native(tempDir(`ch-wtr-${runner}`));
  // 配置里有各自的 worktree_root：按角色时版本记录与摘要里的配置哈希（全长与前 12 位）也各不相同
  const configText = json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...(o.role ? BOUND : {}) });
  put(repo, ".agent/dispatch.config.json", configText);
  if (o.autocrlf) git(repo, "config", "core.autocrlf", "true");
  put(repo, "review.md", `# 复审${LF}${LF}Verdict: PASS${LF}`);
  const prep = runPythonCli(["--repo", repo, "prepare", "t1.v1"], repo);
  if (prep.status !== 0) throw new Error(`prepare 失败：${prep.stdout.toString("utf8")}${prep.stderr.toString("utf8")}`);
  const wt = (JSON.parse(readFileSync(join(repo, RUN_REL, "meta.json"), "utf8")) as { worktree: string }).worktree;
  return { repo, paths: { "<REPO>": repo, "<WT>": wt, "<WTROOT>": wtRoot, "<AGENT>": AGENT_DIR, "<CONFIG_SHA>": sha(configText), "<CONFIG_SHA12>": sha(configText).slice(0, 12) } };
}

function envFor(repo: string, scenario: string): Record<string, string> {
  return { ...IDENTITY, PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, STUB]), PI_CODING_AGENT_DIR: AGENT_DIR, STUB_SCENARIO: scenario, STUB_MAIN_REPO: repo };
}

interface HubView {
  readonly state: string;
  readonly budget: Record<string, unknown>;
  readonly running: unknown;
  readonly check_lines: unknown;
}

/** hub 的眼光：Python 的函数读这一步之后的证据；stdout 里合格的 CHECK 行。已用墙钟（wall_seconds_used）每次不同，换成占位符。 */
function hubView(repo: string, stdout: string, paths: Record<string, string>): HubView {
  const file = join(tempDir("ch-out"), "stdout.txt");
  writeFileSync(file, stdout, "utf8");
  const done = spawnSync(PYTHON, ["-c", HUB_VIEW, repo, file], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`hub 的读法出错：${done.stderr}`);
  const view = JSON.parse(scrub(normalize(done.stdout, paths))) as HubView;
  return { ...view, budget: { ...view.budget, wall_seconds_used: "<S>" } };
}

/** 一步：runner 跑 argv，交回比较用的结果。 */
function step(runner: Runner, repo: string, paths: Record<string, string>, argv: readonly string[], scenario = "ok"): Record<string, unknown> {
  const result = withEnv(envFor(repo, scenario), () => runCommand(runner, repo, argv, pyargsOf(repo, argv)));
  const stdout = result.stdout.toString("utf8");
  return {
    argv: argv.join(" "),
    status: result.status,
    stdout: scrub(normalize(stdout, paths)),
    stderr: scrub(normalize(result.stderr.toString("utf8"), paths)),
    evidence: Object.fromEntries(Object.entries(snapshotDir(join(repo, ".agent", "runs"), paths)).map(([key, value]) => [key, scrub(value)])),
    reviews: existsSync(join(repo, ".agent", "reviews")) ? snapshotDir(join(repo, ".agent", "reviews"), paths) : {},
    hub: hubView(repo, stdout, paths),
  };
}

function gitState(repo: string): Record<string, unknown> {
  const refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/").split(LF).filter(Boolean);
  const messages = refs.map((line) => git(repo, "log", "-1", "--format=%P%n%T%n%B", line.split(" ")[0] as string));
  return { refs, messages, head: git(repo, "rev-parse", "HEAD") };
}

describe("Python 开跑、TS 收尾", () => {
  it("Python prepare 之后，run、check、verdict PASS、integrate 由各 runner 接着做", () => {
    const STEPS = [["run", RUN_REL], ["check", "t1"], ["verdict", "t1", "--verdict", "PASS", "--review", "review.md"], ["integrate", "t1"]];
    const results = RUNNERS.map((runner) => {
      const { repo, paths } = preparedRepo(runner);
      const steps = STEPS.map((argv) => step(runner, repo, paths, argv));
      return { steps, git: gitState(repo) };
    });
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const first = results[0] as (typeof results)[number];
    expect(first.steps.map((one) => one.status), JSON.stringify(first.steps.map((one) => [one.argv, one.stdout, one.stderr]))).toEqual([0, 0, 0, 0]);
    expect(first.steps.map((one) => (one.hub as HubView).state)).toEqual(["NEEDS_REVIEW", "NEEDS_REVIEW", "PASS", "INTEGRATED"]);
  }, 600_000);

  it("core.autocrlf=true：prepare 记下 true，check 通过；之后改回 false，verdict PASS 与 branch 照记下的值重建树", () => {
    const results = RUNNERS.map((runner) => {
      const { repo, paths } = preparedRepo(runner, { autocrlf: true });
      const steps = [step(runner, repo, paths, ["run", RUN_REL]), step(runner, repo, paths, ["check", "t1"])];
      git(repo, "config", "core.autocrlf", "false");
      // 记下 true、仓库当前 false：干净副本与验证副本这两条写工作区的路径（themistally-15 复核 c3b 时提出）。integrate 带 --recheck，
      // 不沿用 check --fresh 的结果，才会真的建验证副本
      steps.push(step(runner, repo, paths, ["check", "t1", "--fresh"]));
      steps.push(step(runner, repo, paths, ["verdict", "t1", "--verdict", "PASS", "--review", "review.md"]));
      steps.push(step(runner, repo, paths, ["branch", "t1"]));
      steps.push(step(runner, repo, paths, ["integrate", "t1", "--dry-run", "--recheck"]));
      return { steps, git: gitState(repo) };
    });
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const first = results[0] as (typeof results)[number];
    expect(first.steps.map((one) => one.status), JSON.stringify(first.steps.map((one) => [one.argv, one.stdout, one.stderr]))).toEqual([0, 0, 0, 0, 0, 0]);
    const integrate = first.steps[5] as Record<string, unknown>;
    expect(String(integrate["stdout"]), "没有沿用 check --fresh 的结果").not.toContain("沿用");
    expect((integrate["evidence"] as Record<string, string>)["t1/attempt-001/integrations/01/integration.json"], "建了验证副本").toContain("workspace");
    expect((first.steps[0]?.evidence as Record<string, string>)["t1/attempt-001/meta.json"]).toContain('"git_autocrlf": "true"');
  }, 600_000);

  it("反过来：prepare 记下 false，之后仓库改成 true：干净副本建不起来（两边共有的缺陷）", () => {
    const results = RUNNERS.map((runner) => {
      const { repo, paths } = preparedRepo(runner);
      const steps = [step(runner, repo, paths, ["run", RUN_REL]), step(runner, repo, paths, ["check", "t1"])];
      git(repo, "config", "core.autocrlf", "true");
      steps.push(step(runner, repo, paths, ["check", "t1", "--fresh"]));
      steps.push(step(runner, repo, paths, ["verdict", "t1", "--verdict", "PASS", "--review", "review.md"]));
      steps.push(step(runner, repo, paths, ["integrate", "t1", "--dry-run", "--recheck"]));
      return { steps, git: gitState(repo) };
    });
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const first = results[0] as (typeof results)[number];
    // 两边共有的缺陷（迁移计划 10.1）：干净副本由当前配置检出、打补丁，却按记下的值快照，记下 false、当前 true 时树对不上；
    // 没有有效的独立检查记录，PASS 被 G3、G4 拒绝，integrate 走不到验证副本。修好之前守住两边一致
    expect(first.steps.map((one) => one.status)).toEqual([0, 0, 3, 1, 3]);
    expect(String(first.steps[2]?.stderr)).toContain("干净副本与候选树不一致");
  }, 600_000);

  it("K13：按角色写的合同领取之后、还没有 executor.json 就崩了，collect --recover 与 review-draft 用版本记录里的模型", () => {
    const results = RUNNERS.map((runner) => {
      const { repo, paths } = preparedRepo(runner, { role: true });
      const runDir = join(repo, ...RUN_REL.split("/"));
      mkdirSync(join(runDir, "claim"), { recursive: true });
      put(runDir, "state.json", json({ state: "RUNNING", at: "2026-01-01T00:00:00Z" }));
      return [step(runner, repo, paths, ["collect", "t1", "--recover"]), step(runner, repo, paths, ["review-draft", "t1"])];
    });
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const [recover, draft] = results[0] as Record<string, unknown>[];
    expect((recover?.evidence as Record<string, string>)["t1/attempt-001/executor.json"], "没有 executor.json").toBeUndefined();
    expect((recover?.evidence as Record<string, string>)["t1/attempt-001/summary.md"]).toContain("要求的执行模型：step/step-5 · thinking=high");
    expect([draft?.status, Object.values(draft?.reviews as Record<string, string>).join("").includes("step-5")]).toEqual([0, true]);
  }, 600_000);

  it("Python 的 run 跑到一半调度器被硬杀，由各 runner 的 collect --recover 收尾", async () => {
    const results = [];
    for (const runner of RUNNERS) {
      const { repo, paths } = preparedRepo(runner);
      await crashedPythonRun(repo, paths["<WT>"] as string);
      results.push({ crashed: hubView(repo, "", paths), recover: step(runner, repo, paths, ["collect", "t1", "--recover"], "hang") });
    }
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const first = results[0] as (typeof results)[number];
    expect(first.crashed.state, "硬杀之后停在 RUNNING").toBe("RUNNING");
    expect((first.recover.hub as HubView).state).not.toBe("RUNNING");
  }, 600_000);
});

/** Python 的 run（stub_pi 的 hang 剧本）起到 pi 已经在跑，再连进程树硬杀调度器：attempt 停在 RUNNING。 */
function crashedPythonRun(repo: string, wt: string): Promise<void> {
  const [command, ...args] = pythonCliCommand(["--repo", repo, "run", RUN_REL]);
  const child = withEnv(envFor(repo, "hang"), () => spawn(command as string, args, { cwd: repo, stdio: "ignore" }));
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + 60_000;
    const poll = (): void => {
      if (existsSync(join(wt, "child.pid"))) {
        const taskkill = join(process.env["SystemRoot"] ?? "C:/Windows", "System32", "taskkill.exe");
        spawnSync(taskkill, ["/T", "/F", "/PID", String(child.pid)], { stdio: "ignore" });
        child.on("exit", () => resolve());
        if (child.exitCode !== null) resolve();
        return;
      }
      if (Date.now() > deadline || child.exitCode !== null) {
        child.kill();
        reject(new Error("没等到 pi 起来"));
        return;
      }
      setTimeout(poll, 200);
    };
    poll();
  });
}
