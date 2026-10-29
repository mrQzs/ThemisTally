// prepare（迁移第 ④b7a 片）：合同校验、并行派遣的提示、执行模型的解析与按合同版本的记录、预算、attempt 编号、冻结合同对、
// worktree 与 setup。每个场景按三份实现各建一份相同的仓库（固定作者与时间，提交号相同）与合同对，跑同一条 prepare，比退出码、
// 标准输出与标准错误、.agent/runs 下的全部证据、worktree 的数目与检出的文件。meta.json 的 impl 按设计不同（python 对 ts），
// 单独断言；路径、时间、wall_seconds、pid 与 mkdtemp 的随机后缀换成占位符。崩溃只比退出码与证据。不写转义序列。
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, symlinkSync, utimesSync } from "node:fs";
import { basename, join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { BREAK_OUTER, PYTHON, TS_CONTEXT, json, sha } from "./attempt-fixtures.ts";
import { type Json, type MdOptions, jsonOf, mdOf, text } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, commandOf, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(() => removeCreated());

/** 本机的 platform.python_version()：启动器交给 TS 的 context 里就是它（迁移计划 D1）。 */
const PY_VERSION = spawnSync(PYTHON, ["-c", "import platform; print(platform.python_version())"], { encoding: "utf8" }).stdout.trim();
const CONTEXT = { ...TS_CONTEXT, python: PY_VERSION };
const ARGS = { command: ["prepare"], plan_key: "t1.v1", context: CONTEXT };

const RUNTIMES = { pi: { adapter: "pi" } };
const PROFILES = {
  exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options: { thinking: "high" }, credential_env: ["STEP_KEY"] },
  older: { runtime: "pi", model: { provider: "step", id: "step-4" }, options: { thinking: "high" }, credential_env: ["STEP_KEY"] },
};
const BOUND = { runtimes: RUNTIMES, profiles: PROFILES, roles: { execution: { mode: "headless", profile: "exec" } } };
const ROLE_MD: MdOptions = { executor: "role:execution" };
const roleJson = (data: Json): void => void (data["executor"] = { role: "execution", tools: ["read", "edit", "bash"], context_files: "project" });

/** 按合同版本的执行模型记录：合同哈希对得上这份合同的 JSON。 */
const record = (contractText: string, extra: Record<string, unknown> = {}): string => json({
  role: "execution", profile: "older", runtime: "pi", adapter: "pi", active_preset: null, provider: "step", model: "step-4", thinking: "high",
  contract_json_sha256: sha(contractText), created_at: "2026-01-01T00:00:00Z", created_by_attempt: "attempt-001", config_sha256: null, ...extra,
});

const setupItem = (id: string, code: string, extra: Record<string, unknown> = {}): Record<string, unknown> =>
  ({ id, argv: ["python", "-B", "-c", code], cwd: ".", timeout_seconds: 60, expected_exit_code: 0, ...extra });

interface At {
  readonly repo: string;
  readonly runs: string;
  readonly contractText: string;
}

interface Case {
  readonly label: string;
  readonly status: number;
  readonly text?: string | readonly string[];
  readonly md?: MdOptions;
  readonly json?: (data: Json) => void;
  readonly config?: Record<string, unknown>;
  readonly env?: Record<string, string>;
  readonly before?: (at: At) => void;
  readonly crash?: boolean;
  /** pi 的命令换成只写一个标记文件的探针，被拒的 prepare 不该调用它（K7、K8）。现在 prepare 的任何路径都不调 pi（只跑合同的
   * setup），这一项只当回归护栏；真正有区分力的是开 spy 时另断言的“不留 attempt”（themistally-15 复核 c1 时指出）。 */
  readonly spy?: boolean;
}

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

function scrub(value: string): string {
  return value
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/"impl": "(python|ts)"/gu, '"impl": <IMPL>');
}

const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

/** 一个场景的仓库：合同对 t1.v1、配置（worktree_root 在仓库之外）。交回比较口径要换的路径。 */
function buildRepo(runner: Runner, item: Case): { repo: string; wtRoot: string; paths: Record<string, string> } {
  const { repo, head } = newRepo(`prep-${runner}`);
  const wtRoot = realpathSync.native(tempDir(`pwt-${runner}`));
  const data = jsonOf("t1", head);
  item.json?.(data);
  const contractText = text(data);
  put(repo, ".agent/plans/t1.v1.md", mdOf("t1", head, item.md));
  put(repo, ".agent/plans/t1.v1.json", contractText);
  const configText = json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...item.config });
  put(repo, ".agent/dispatch.config.json", configText);
  item.before?.({ repo, runs: join(repo, ".agent", "runs"), contractText });
  return { repo, wtRoot, paths: { "<REPO>": repo, "<WTROOT>": wtRoot, "<CONFIG_SHA>": sha(configText) } };
}

/** worktree_root 下建出来的 worktree（mkdtemp 的随机后缀因实现而异）。 */
function worktreesIn(wtRoot: string): string[] {
  return existsSync(wtRoot) ? readdirSync(wtRoot).sort().map((name) => join(wtRoot, name)) : [];
}

function metaImpls(runs: string): string[] {
  const found: string[] = [];
  const t1 = join(runs, "t1");
  if (!existsSync(t1)) return found;
  for (const name of readdirSync(t1).sort()) {
    const meta = join(t1, name, "meta.json");
    if (existsSync(meta)) found.push((JSON.parse(readFileSync(meta, "utf8")) as { impl: string }).impl);
  }
  return found;
}

function runCase(item: Case): void {
  const results = (RUNNERS as readonly Runner[]).map((runner) => {
    const { repo, wtRoot, paths } = buildRepo(runner, item);
    const marker = join(tempDir(`pspy-${runner}`), "ran");
    const spy = item.spy ? { PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, "-c", `open(${JSON.stringify(marker)}, 'a').write('x')`]) } : {};
    const result = withEnv({ ...item.env, ...spy }, () => runCommand(runner, repo, ["prepare", "t1.v1"], ARGS));
    const worktrees = worktreesIn(wtRoot);
    worktrees.forEach((wt, index) => void (paths[index ? `<WT${index}>` : "<WT>"] = wt));
    const runs = join(repo, ".agent", "runs");
    const stderr = result.stderr.toString("utf8");
    expect(metaImpls(runs).every((impl) => impl === (runner === "python" ? "python" : "ts")), `${runner} 的 meta.json 的 impl`).toBe(true);
    return {
      status: result.status,
      stdout: item.crash ? "" : scrub(normalize(result.stdout.toString("utf8"), paths)),
      stderr: item.crash ? "" : scrub(normalize(stderr, paths)),
      crashed: item.crash ? crashed(stderr) : null,
      evidence: Object.fromEntries(Object.entries(snapshotDir(runs, paths)).map(([key, value]) => [key, scrub(value)])),
      registered: git(repo, "worktree", "list", "--porcelain").split(LF).filter((line) => line.startsWith("worktree ")).length,
      checkedOut: worktrees.map((wt) => readdirSync(wt).filter((name) => name !== ".git").sort()),
      // mkdtemp 的前缀：仓库目录名的前 16 个码点、任务号、编号（整个路径在比较里换成了占位符）
      cliRan: existsSync(marker),
      prefixed: worktrees.every((wt) => basename(wt).startsWith(`${Array.from(basename(realpathSync.native(repo))).slice(0, 16).join("")}-t1-a`)),
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify(first)).toBe(item.status);
  expect(first.prefixed, "worktree 目录名的前缀").toBe(true);
  expect(first.cliRan, "被拒的 prepare 不调用 pi 的 CLI").toBe(false);
  if (item.spy) expect(Object.keys(first.evidence).filter((rel) => rel.includes("attempt-")), "分配 attempt 之前就拒绝，不留 attempt").toEqual([]);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
}

const ARABIC_007 = `attempt-${String.fromCharCode(0x660, 0x660, 0x667)}`;
const HOUR_AGO = new Date(Date.now() - 3_600_000);
const MANY_NEW = Array.from({ length: 11 }, (_, index) => `src/f${String(index).padStart(2, "0")}.ts`);

const CASES: Case[] = [
  // --- 正常 ---
  { label: "没有 setup：PREPARED，提示补 setup", status: 0,
    text: ["PREPARED t1.v1.a001", "Run directory: <REPO>", "Worktree: <WT>", "合同没有 setup。", "下一步（在后台运行）：bash scripts/dispatch-pi.sh run .agent/runs/t1/attempt-001"] },
  { label: "setup 通过：记 setup.json 与日志", status: 0, json: (data) => void (data["setup"] = [setupItem("S01", "print('setup ok')")]), text: "PREPARED t1.v1.a001" },
  { label: "setup 失败：PREPARE_FAILED，不计入尝试次数", status: 1,
    json: (data) => void (data["setup"] = [setupItem("S01", "import sys; print('boom'); sys.exit(2)"), setupItem("S02", "print('never')")]),
    text: "setup 失败：S01（日志 .agent/runs/t1/attempt-001/setup/S01.log）。修正后重新 prepare；本 attempt 未领取，不计入尝试次数。" },
  { label: "setup 改动了 worktree：PREPARE_FAILED", status: 1, json: (data) => void (data["setup"] = [setupItem("S01", "open('new.txt', 'w').write('x')")]),
    text: ["setup 修改了受版本管理的文件或产生了未忽略的新文件：", "?? new.txt"] },
  { label: "setup 的 cwd 不在 worktree 里：被拦下", status: 1, json: (data) => void (data["setup"] = [setupItem("S01", "print(1)", { cwd: "nope" })]), text: "setup 失败：S01" },
  // --- 校验与前置条件 ---
  { label: "JSON 合同不是合法 JSON：合同校验失败，不建 attempt", status: 2, before: ({ repo }) => put(repo, ".agent/plans/t1.v1.json", "{"), text: "合同校验失败，未创建 attempt。" },
  { label: ".agent/runs/ 没被忽略", status: 3, before: ({ repo }) => put(repo, ".gitignore", ""), text: "请先把 .agent/runs/ 加入 .gitignore" },
  { label: "worktree_root 在仓库里", status: 2, config: { worktree_root: "inside" }, text: "worktree_root 不能位于仓库内部：<REPO>" },
  { label: "决策配置写错：分配 attempt 之前就报", status: 2, config: { decisions: { mode: "bogus" } }, text: "decisions" },
  // --- 并行派遣的提示 ---
  { label: "其他任务未集成且范围重叠、另有正在运行的 attempt", status: 0,
    before: ({ runs }) => {
      put(runs, "t2/attempt-001/state.json", json({ state: "NEEDS_REVIEW" }));
      put(runs, "t2/attempt-001/contract.json", json({ scope: { allowed_modified_files: ["src/a.ts", "src/b.ts"], allowed_new_files: [7, "src/a.ts"] } }));
      put(runs, "t3/attempt-001/state.json", json({ state: "RUNNING" }));
      put(runs, "t4/attempt-001/state.json", json({ state: "INTEGRATED" }));
      put(runs, "t4/attempt-001/contract.json", json({ scope: { allowed_modified_files: ["src/a.ts"] } }));
    },
    text: ["NOTE  有 1 个 attempt 正在运行（t3/attempt-001）", "与未集成的 t2/attempt-001（NEEDS_REVIEW）改动范围重叠：src/a.ts；"] },
  { label: "重叠的文件超过 10 个：只列排在前面的 10 个", status: 0,
    md: { newFiles: MANY_NEW.join(", ") },
    json: (data) => void ((data["scope"] as Json)["allowed_new_files"] = [...MANY_NEW]),
    before: ({ runs }) => {
      put(runs, "t2/attempt-001/state.json", json({ state: "NEEDS_REVIEW" }));
      put(runs, "t2/attempt-001/contract.json", json({ scope: { allowed_modified_files: ["src/a.ts"], allowed_new_files: [...MANY_NEW].reverse() } }));
    },
    text: `改动范围重叠：src/a.ts、${MANY_NEW.slice(0, 9).join("、")}；并行派遣` },
  // --- 预算与编号 ---
  { label: "尝试次数用完", status: 3,
    before: ({ runs }) => ["attempt-001", "attempt-002"].forEach((name) => put(runs, `t1/${name}/claim/reservation.json`, json({ timeout_seconds: 1 }))),
    text: "BUDGET_EXCEEDED：任务 t1 已运行 2 次，达到 max_attempts_total=2。" },
  { label: "累计用时用完：%.0f 在中点取偶", status: 3,
    before: ({ runs }) => { put(runs, "t1/attempt-001/claim/x", ""); put(runs, "t1/attempt-001/run.json", json({ wall_seconds: 2400.5 })); },
    text: "BUDGET_EXCEEDED：累计运行 2400s，达到 max_wall_seconds_total=2400。" },
  { label: "还没有 run.json：按预留的时限计入（字符串照 float() 解析）", status: 3,
    before: ({ runs }) => put(runs, "t1/attempt-001/claim/reservation.json", json({ timeout_seconds: " 2401 " })),
    text: "BUDGET_EXCEEDED：累计运行 2401s" },
  { label: "run.json 是列表：照 Python 崩", status: 1, crash: true,
    before: ({ runs }) => { put(runs, "t1/attempt-001/claim/x", ""); put(runs, "t1/attempt-001/run.json", "[1]"); } },
  // 目录按名字列出来时 Unicode 数字排在最后：编号要取最大的，不是最后一个。本任务自己的 attempt 范围重叠也不提示
  { label: "编号接着已有的最大号（Unicode 数字也算），没领取的不算预算", status: 0,
    before: ({ runs }) => {
      put(runs, `t1/${ARABIC_007}/state.json`, json({ state: "PREPARE_FAILED" }));
      put(runs, "t1/attempt-003/state.json", json({ state: "PREPARED" }));
      put(runs, "t1/attempt-009/state.json", json({ state: "PREPARED" }));
      put(runs, "t1/attempt-009/contract.json", json({ scope: { allowed_modified_files: ["src/a.ts"] } }));
      put(runs, "t1/attempt-12/state.json", json({ state: "PREPARED" }));
      put(runs, "t1/attempt-099", "不是目录");
    },
    text: "PREPARED t1.v1.a010" },
  // --- 写死模型的合同 ---
  { label: "环境变量与合同冲突", status: 2, env: { PI_EXEC_MODEL: "other-model" },
    text: "PI_EXEC_MODEL=other-model 与合同 executor.model=step-5-preview 冲突；以审阅过的合同为准，请移除环境变量" },
  { label: "环境变量与合同一致：照常", status: 0, env: { PI_EXEC_PROVIDER: "step" }, text: "PREPARED t1.v1.a001" },
  { label: "不在 allowed_executors 里", status: 3, config: { allowed_executors: [{ provider: "step", model: "other" }] },
    text: "执行模型 step/step-5-preview 不在 .agent/dispatch.config.json 的 allowed_executors 中" },
  { label: "allowed_executors 钉了别的思考级别", status: 3, config: { allowed_executors: [{ provider: "step", model: "step-5-preview", thinking: "low" }] },
    text: "该执行模型的思考级别固定为 low，合同为 high" },
  { label: "execution 绑定与合同不同：NOTE，meta 记 executor_binding_note", status: 0, config: BOUND,
    text: "NOTE  合同写死执行模型 step/step-5-preview · thinking high；execution 绑定是 step/step-5 · thinking high（profile exec），本次按合同" },
  { label: "execution 绑定与合同相同：不提示", status: 0,
    config: { ...BOUND, profiles: { exec: { ...PROFILES.exec, model: { provider: "step", id: "step-5-preview" } } } }, text: "PREPARED t1.v1.a001" },
  // --- 按角色写的合同 ---
  { label: "按角色：第一次 prepare 发布版本记录", status: 0, md: ROLE_MD, json: roleJson, config: BOUND, text: "PREPARED t1.v1.a001" },
  { label: "按角色：没有绑定，分配 attempt 之前就拒绝", status: 2, md: ROLE_MD, json: roleJson, spy: true, text: "按角色写的合同需要 execution 角色的 headless 绑定" },
  { label: "按角色：已有记录、绑定已改：NOTE，沿用记录", status: 0, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs, contractText }) => put(runs, "t1/binding-v1.json", record(contractText)),
    text: "NOTE  execution 绑定已改为 step/step-5 · thinking high（profile exec）；本版本沿用 step/step-4 · thinking high；要用新绑定，出新版本合同" },
  { label: "按角色：已有记录、当前没有绑定：照样沿用", status: 0, md: ROLE_MD, json: roleJson, config: { runtimes: RUNTIMES, profiles: PROFILES },
    before: ({ runs, contractText }) => put(runs, "t1/binding-v1.json", record(contractText)),
    text: "NOTE  当前没有可用的 execution 绑定；本版本沿用版本记录（step/step-4 · thinking high）" },
  { label: "按角色：记录的合同哈希不对：PREPARE_FAILED，退出码 4", status: 4, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs, contractText }) => put(runs, "t1/binding-v1.json", record(contractText, { contract_json_sha256: "0".repeat(64) })),
    text: "ERROR: prepare 失败（t1.v1.a001 已标记 PREPARE_FAILED）：合同 v1 的字节与首次派遣时不同（版本记录 .agent/runs/t1/binding-v1.json）" },
  { label: "按角色：记录无效", status: 4, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs }) => put(runs, "t1/binding-v1.json", json({ role: "execution" })), text: "版本记录无效（.agent/runs/t1/binding-v1.json）：字段不全或类型不对" },
  { label: "按角色：环境变量与记录冲突", status: 2, md: ROLE_MD, json: roleJson, config: BOUND, env: { PI_EXEC_PROVIDER: "zz" },
    text: "PI_EXEC_PROVIDER=zz 与execution 角色绑定的版本记录的 provider=step 冲突；以它为准，请移除环境变量" },
  // 覆盖审计的缺口（切换 c1）：r2 文档 9.4 节的 K7、K8、K10、K16
  { label: "按角色：合同角色是 manual：分配 attempt 之前就拒绝，不调用 CLI", status: 2, spy: true,
    md: { executor: "role:contract" }, json: (data) => void (data["executor"] = { role: "contract", tools: ["read", "edit", "bash"], context_files: "project" }),
    config: { runtimes: RUNTIMES, profiles: PROFILES, roles: { contract: { mode: "manual" } } }, text: "manual" },
  { label: "按角色：绑定的适配器没有接通：退出 3，不调用 CLI", status: 3, md: ROLE_MD, json: roleJson, spy: true,
    config: {
      runtimes: { ...RUNTIMES, oc: { adapter: "opencode" } },
      profiles: { ...PROFILES, "oc-x": { runtime: "oc", model: { provider: "oc", id: "x-1" } } },
      roles: { execution: { mode: "headless", profile: "oc-x" } },
    }, text: "没有接通" },
  { label: "按角色：PI_EXEC_MODEL 与记录冲突", status: 2, md: ROLE_MD, json: roleJson, config: BOUND, env: { PI_EXEC_MODEL: "other-model" },
    text: "PI_EXEC_MODEL=other-model 与execution 角色绑定的版本记录" },
  { label: "按角色：PI_EXEC_THINKING 与记录冲突", status: 2, md: ROLE_MD, json: roleJson, config: BOUND, env: { PI_EXEC_THINKING: "low" },
    text: "PI_EXEC_THINKING=low 与execution 角色绑定的版本记录" },
  { label: "按角色：记录不是 JSON：退出 4，原样留着", status: 4, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs }) => put(runs, "t1/binding-v1.json", "{not json"), text: "版本记录无效" },
  { label: "按角色：记录经过 junction：退出 4", status: 4, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs, contractText }) => {
      const elsewhere = join(runs, "elsewhere"); // 清理时就算顺着 junction 走，删的也是这个仓库自己的东西
      put(elsewhere, "binding-v1.json", record(contractText));
      mkdirSync(runs, { recursive: true });
      symlinkSync(elsewhere, join(runs, "t1"), "junction");
    }, text: "经过链接" },
  { label: "按角色：任务锁过期就接管", status: 0, md: ROLE_MD, json: roleJson, config: BOUND,
    before: ({ runs }) => {
      put(runs, "t1/.task.lock/owner.json", json({ pid: 1, at: "2026-01-01T00:00:00Z" }));
      utimesSync(join(runs, "t1", ".task.lock"), HOUR_AGO, HOUR_AGO);
    },
    text: "PREPARED t1.v1.a001" },
];

describe("prepare", () => {
  for (const item of CASES) it(item.label, () => runCase(item), 180_000);
});

// ---------------------------------------------------------------------------
// D2：setup 跑到一半，prepare 的进程组收到 CTRL_BREAK
// ---------------------------------------------------------------------------

/** 内层：另起进程组跑 prepare，等 worktree 里出现 started.flag（setup 开始了）、再等一秒，给 prepare 的进程组发 CTRL_BREAK。 */
const BREAK_ON_FLAG = [
  "import glob, json, os, signal, subprocess, sys, time",
  "p = subprocess.Popen(json.loads(sys.argv[1]), cwd=sys.argv[2], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x200)",
  "deadline = time.monotonic() + 60",
  "while not glob.glob(os.path.join(sys.argv[3], '*', 'started.flag')):",
  "    if p.poll() is not None or time.monotonic() > deadline:",
  "        p.kill(); sys.exit('没等到 setup 开始')",
  "    time.sleep(0.2)",
  "time.sleep(1)",
  "p.send_signal(signal.CTRL_BREAK_EVENT)",
  "out, err = p.communicate()",
  "sys.stdout.write(json.dumps({'status': p.returncode, 'stdout': out.decode('utf-8', 'replace'), 'stderr': err.decode('utf-8', 'replace')}))",
].join(LF);

describe("D2：setup 跑到一半，prepare 的进程组收到 CTRL_BREAK", () => {
  it("setup 记被取消，attempt 标 PREPARE_FAILED", () => {
    const item: Case = {
      label: "D2", status: 1,
      json: (data) => void (data["setup"] = [setupItem("S01", "open('started.flag', 'w').close(); import time; time.sleep(30)")]),
    };
    const results = RUNNERS.map((runner) => {
      const { repo, wtRoot, paths } = buildRepo(runner, item);
      const command = commandOf(runner, repo, ["prepare", "t1.v1"], ARGS);
      const done = spawnSync(PYTHON, ["-c", BREAK_OUTER, BREAK_ON_FLAG, JSON.stringify(command), repo, wtRoot], { encoding: "utf8", timeout: 150_000 });
      if (done.status !== 0) throw new Error(`${runner} 中断用例的包装进程退出码 ${String(done.status)}：${done.stderr}`);
      const run = JSON.parse(done.stdout) as { status: number; stdout: string; stderr: string };
      worktreesIn(wtRoot).forEach((wt) => void (paths["<WT>"] = wt));
      return {
        status: run.status, stdout: scrub(normalize(run.stdout, paths)), stderr: scrub(normalize(run.stderr, paths)),
        evidence: Object.fromEntries(Object.entries(snapshotDir(join(repo, ".agent", "runs"), paths)).map(([key, value]) => [key, scrub(value)])),
      };
    });
    for (const result of results.slice(1)) expect(result).toEqual(results[0]);
    const first = results[0] as (typeof results)[number];
    expect(first.status, JSON.stringify(first)).toBe(1);
    expect(first.stdout).toContain("setup 失败：S01");
    expect(first.evidence["t1/attempt-001/setup.json"]).toContain('"reason": "被取消"');
    expect(first.evidence["t1/attempt-001/state.json"]).toContain('"reason": "setup S01 失败：被取消"');
  }, 300_000);
});

/**
 * K4（r2 文档 9.4 节，themistally-15 复核切换 c 时建议）：同一个按角色写的合同版本，同时起 8 个首次 prepare。发布在任务锁里，
 * 8 个进程到那一步是排队的，完全串行也会 8 个都成功：这里测的是“同时起步”时的不变量——版本记录只有一份、内容完整；成功的
 * attempt 记下同一份绑定；没有崩溃；不留半截的临时文件；成功的个数与 PREPARED 的个数相同。进程层面确实并发由起止时间核对
 * （区间两两重叠）。发布时发现别人已经发布（publish_new 返回 False）那条路另在 publish-binding.test.ts 里直接调出来。四种 runner 各一组，另有一组四种混跑（各 2 个）：切换的
 * 那一刻 Python 与 TS 会在同一个仓库里各自 prepare。
 */
function concurrentPrepares(runners: readonly Runner[]): Promise<{ status: number; stderr: string }[]> {
  const item: Case = { label: "K4", status: 0, md: ROLE_MD, json: roleJson, config: BOUND };
  const { repo } = buildRepo(runners[0] as Runner, item);
  return Promise.all(runners.map((runner) => new Promise<{ status: number; stderr: string; start: number; end: number }>((resolve) => {
    const [command, ...args] = commandOf(runner, repo, ["prepare", "t1.v1"], ARGS);
    const start = performance.now();
    const child = spawn(command as string, args, { cwd: repo, stdio: ["ignore", "ignore", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk: Buffer) => void (stderr += chunk.toString("utf8")));
    child.on("close", (code) => resolve({ status: code ?? -1, stderr, start, end: performance.now() }));
  }))).then((results) => {
    expect(Math.max(...results.map((one) => one.start)), "各进程的起止区间两两重叠").toBeLessThan(Math.min(...results.map((one) => one.end)));
    const runs = join(repo, ".agent", "runs", "t1");
    const record = JSON.parse(readFileSync(join(runs, "binding-v1.json"), "utf8")) as Record<string, unknown>;
    expect(record["model"], "版本记录完整").toBe("step-5");
    const metas = readdirSync(runs).filter((name) => name.startsWith("attempt-")).sort()
      .map((name) => [JSON.parse(readFileSync(join(runs, name, "state.json"), "utf8")) as { state: string }, join(runs, name, "meta.json")] as const);
    const prepared = metas.filter(([state]) => state.state === "PREPARED").map(([, meta]) => JSON.parse(readFileSync(meta, "utf8")) as Record<string, unknown>);
    expect(prepared.length, "成功的个数与 PREPARED 的个数相同").toBe(results.filter((one) => one.status === 0).length);
    for (const meta of prepared) expect(meta["executor_binding"], "成功的 attempt 记下同一份绑定").toEqual(prepared[0]?.["executor_binding"]);
    expect(readdirSync(runs).filter((name) => name.includes(".tmp") || name.endsWith(".partial")), "不留临时文件").toEqual([]);
    for (const one of results) expect(crashed(one.stderr), one.stderr).toBe(false);
    return results;
  });
}

describe("K4：同一版本同时起步的首次 prepare（概率性压力：记录只有一份且完整、不崩、不留临时文件）", () => {
  const groups: [string, readonly Runner[]][] = [
    ...RUNNERS.map((runner): [string, readonly Runner[]] => [runner, Array.from({ length: 8 }, () => runner)]),
    ["四种混跑", RUNNERS.flatMap((runner) => [runner, runner])],
  ];
  for (const [label, runners] of groups) {
    it(label, async () => {
      for (let round = 0; round < 2; round += 1) {
        const results = await concurrentPrepares(runners);
        expect(results.some((one) => one.status === 0), "至少一个成功").toBe(true);
      }
    }, 600_000);
  }
});
