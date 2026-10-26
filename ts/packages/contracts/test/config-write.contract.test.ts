// config 写命令的契约（迁移第 ③b 片）：set、unset、init、decisions、rollback 与写模式（--dry-run --json、--expect-state）。
// 交替写契约（迁移计划第 ③ 步）：同一个临时仓库里按种子生成一串写命令，每条随机交给 Python 或 TS（Node、Bun）执行；同一串命令
// 在另一个仓库里全交给 Python 跑一遍作对照。每一步之后比较：命令自己的退出码、stdout、stderr；配置文件与标记文件的字节；
// .agent/config-history/ 下的文件名与字节；history --json；审计逐行。比较口径：at、audit_id、txn 只比格式（换成按出现次序
// 编号的占位符），仓库路径换成 <REPO>，其余逐字。序列里有失败的命令：整份校验不过、--expect-state 对不上（退出 4）、
// 令牌格式不对（退出 2）、D8 该带 --yes 没带。
// 锁互斥契约：两套实现同时往同一份配置写不同的键，读改写不丢更新，审计每笔都有 intent 与 commit。
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { BUN, type CliRun, REPO, prng, removeDir, runPythonCli, runTsCli, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("config-write"));
const ENV: Record<string, string | undefined> = { CODEKIT_SECRET_STORE: "off", TYPESAFE_API_KEY: undefined, PI_DISPATCH_WORKTREE_ROOT: undefined, CODEKIT_ACTOR: "user" };
const SAVED: Record<string, string | undefined> = {};
beforeAll(() => {
  for (const [name, value] of Object.entries(ENV)) {
    SAVED[name] = process.env[name];
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});
afterAll(() => {
  for (const [name, value] of Object.entries(SAVED)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  removeDir(ROOT);
});

/** 临时 Git 仓库；running 时放一个在跑的 attempt（D8 用）。 */
function gitRepo(name: string, options: { ignoreHistory?: boolean; running?: boolean } = {}): string {
  const repo = join(ROOT, name);
  mkdirSync(join(repo, ".agent"), { recursive: true });
  const done = spawnSync("git", ["init", "-q", repo], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr}`);
  if (options.ignoreHistory ?? true) writeFileSync(join(repo, ".gitignore"), ".agent/config-history/\n.agent/audit/\n.agent/.config.lock/\n.agent/runs/\n");
  if (options.running) {
    mkdirSync(join(repo, ".agent", "runs", "t1", "attempt-001"), { recursive: true });
    writeFileSync(join(repo, ".agent", "runs", "t1", "attempt-001", "state.json"), '{"state": "RUNNING"}');
  }
  return repo;
}

/** 一条写命令：Python 的 argv（config 之后的部分）与 TS 的 pyargs（argparse 解析之后的值）。 */
interface Command {
  readonly label: string;
  readonly argv: string[];
  readonly args: (repo: string) => Record<string, unknown>;
}

const context = { kit_root: REPO, lock_wait_seconds: 5.0 };
const set = (key: string, value: string, yes = false): Command => ({
  label: `set ${key} ${value}${yes ? " --yes" : ""}`,
  argv: ["set", key, value, ...(yes ? ["--yes"] : [])],
  args: (repo) => ({ command: ["config", "set"], repo, key, value, yes, context }),
});
const unset = (key: string): Command => ({ label: `unset ${key}`, argv: ["unset", key], args: (repo) => ({ command: ["config", "unset"], repo, key, yes: false, context }) });
const decisions = (what: string, state: string | null = null): Command => ({
  label: `decisions ${what}${state ? ` ${state}` : ""}`,
  argv: ["decisions", what, ...(state ? [state] : [])],
  args: (repo) => ({ command: ["config", "decisions"], repo, what, state, context }),
});
interface RollbackFlags {
  readonly dry_run?: boolean;
  readonly json?: boolean;
  readonly expect_state?: string | null;
  readonly yes?: boolean;
}
const rollback = (number: number, flags: RollbackFlags = {}): Command => ({
  label: `rollback ${number} ${JSON.stringify(flags)}`,
  argv: [
    "rollback",
    String(number),
    ...(flags.yes ? ["--yes"] : []),
    ...(flags.dry_run ? ["--dry-run"] : []),
    ...(flags.json ? ["--json"] : []),
    ...(flags.expect_state ? [`--expect-state=${flags.expect_state}`] : []),
  ],
  args: (repo) => ({
    command: ["config", "rollback"],
    repo,
    number: BigInt(number),
    yes: Boolean(flags.yes),
    dry_run: Boolean(flags.dry_run),
    json: Boolean(flags.json),
    expect_state: flags.expect_state ?? null,
    context,
  }),
});
const init: Command = { label: "init", argv: ["init"], args: (repo) => ({ command: ["config", "init"], repo, context }) };

type Runner = "python" | "node" | "bun";

function run(runner: Runner, repo: string, command: Command): CliRun {
  if (runner === "python") return runPythonCli(["--repo", repo, "config", ...command.argv], repo);
  return runTsCli(runner, command.args(repo), repo);
}

/** 比较口径：仓库路径换成 <REPO>；审计号、txn 换成按出现次序编号的占位符，时间换成 <AT>。 */
function normalize(text: string, repo: string): string {
  const ids = new Map<string, string>();
  const slot =
    (prefix: string) =>
    (match: string): string => {
      if (!ids.has(match)) ids.set(match, `<${prefix}${ids.size}>`);
      return ids.get(match) as string;
    };
  const backslash = String.fromCharCode(92);
  return text
    .replaceAll(repo.replaceAll(backslash, backslash + backslash), "<REPO>")
    .replaceAll(repo, "<REPO>")
    .replace(/aud-[0-9a-f]{32}/gu, slot("aud"))
    .replace(/\b[0-9a-f]{32}\b/gu, slot("txn"))
    .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z/gu, "<AT>");
}

/** 一步之后的仓库状态：配置文件、标记文件、快照目录、history --json（经 Python 读）与审计。 */
function state(repo: string): Record<string, string> {
  const agent = join(repo, ".agent");
  const read = (path: string): string => (existsSync(path) ? readFileSync(path).toString("base64") : "<absent>");
  const historyDir = join(agent, "config-history");
  const snapshots = existsSync(historyDir)
    ? readdirSync(historyDir)
        .sort()
        .map((name) => `${name}:${readFileSync(join(historyDir, name)).toString("base64")}`)
    : [];
  const auditFile = join(agent, "audit", "management.jsonl");
  return {
    config: read(join(agent, "dispatch.config.json")),
    marker: read(join(agent, "DECISIONS_OFF")),
    lock: existsSync(join(agent, ".config.lock")) ? "<left>" : "<none>",
    snapshots: snapshots.join("\n"),
    history: normalize(runPythonCli(["--repo", repo, "config", "history", "--json"], repo).stdout.toString("utf8"), repo),
    audit: normalize(existsSync(auditFile) ? readFileSync(auditFile, "utf8") : "", repo),
  };
}

const PRICE = (source: string): string => JSON.stringify({ input: 1, output: 2, source, as_of: "2026-10-01" });
const RUNTIMES = JSON.stringify({ pi: { adapter: "pi" } });
const PROFILES = JSON.stringify({ exec: { runtime: "pi", model: { provider: "step", id: "step-5" } }, other: { runtime: "pi", model: { provider: "step", id: "step-4" } } });
const STALE = `v1;config=${"0".repeat(64)}`;

/** 种子决定的一串写命令；"<preview>" 表示用上一次预览给的 state 带令牌执行同一条 rollback。 */
type Step = Command | { readonly expectFromPreview: number } | { readonly external: string };

function commands(seed: number): Step[] {
  const next = prng(seed);
  const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
  const pool: (() => Step)[] = [
    () => set("kill_grace_seconds", pick(["20", "20.0", "0", "601", '"15"', "true"])),
    () => set("check_artifact_patterns", pick(['["dist/**"]', '["/abs"]', "[]"])),
    () => set(`pricing.s/m${Math.floor(next() * 3)}`, PRICE(pick(["page", " "]))),
    () => set("decisions.mode", pick(["on", "off", "shadow", "bogus"])),
    () => set("env_keep", pick(['["A"]', '["1X"]', "x"])),
    () => set("bogus_key", "1"),
    () => set("roles", JSON.stringify({ execution: { mode: "headless", profile: pick(["exec", "other"]) } }), next() < 0.5),
    () => unset(pick(["kill_grace_seconds", "pricing.s/m0", "decisions", "env_keep", "nope", "roles"])),
    () => decisions(pick(["off", "shadow", "on"])),
    () => decisions("marker", pick(["on", "off"])),
    () => rollback(1 + Math.floor(next() * 8)),
    () => rollback(1 + Math.floor(next() * 6), { dry_run: true, json: true }),
    () => ({ expectFromPreview: 1 + Math.floor(next() * 6) }),
    () => rollback(1 + Math.floor(next() * 6), { expect_state: pick([STALE, "v1;bogus", `v1;local=${"0".repeat(64)}`]) }),
    () => rollback(1, { json: true }),
    () => set("pricing.s/m.1", PRICE("page")),
    () => ({ external: pick(['{"kill_grace_seconds": 45}', '{"env_keep": ["Z"], "_note": "hand edited"}']) }),
  ];
  return [set("runtimes", RUNTIMES), set("profiles", PROFILES), ...Array.from({ length: 30 }, () => pick(pool)())];
}

const shown = (result: CliRun, repo: string): Record<string, unknown> => ({
  status: result.status,
  stdout: normalize(result.stdout.toString("utf8"), repo),
  stderr: normalize(result.stderr.toString("utf8"), repo),
});

describe("交替写契约", () => {
  for (const seed of [11, 12, 13]) {
    it(`种子 ${seed}：混跑的仓库与全 Python 的仓库每一步都一致`, () => {
      const mixed = gitRepo(`mixed-${seed}`, { running: true });
      const pure = gitRepo(`pure-${seed}`, { running: true });
      const next = prng(seed * 7);
      const problems: unknown[] = [];
      let lastPreview: string | null = null;
      for (const [index, item] of commands(seed).entries()) {
        if ("external" in item) {
          // 在配置中心之外改配置文件：之后的写入要补记 observed
          for (const repo of [mixed, pure]) writeFileSync(join(repo, ".agent", "dispatch.config.json"), `${item.external}${String.fromCharCode(10)}`);
          continue;
        }
        const command = "expectFromPreview" in item ? rollback(item.expectFromPreview, { expect_state: lastPreview ?? STALE }) : item;
        const runner = (["python", "node", "bun"] as const)[Math.floor(next() * 3)] as Runner;
        const left = run(runner, mixed, command);
        const right = run("python", pure, command);
        if (command.argv.includes("--dry-run") && right.status === 0) {
          lastPreview = (JSON.parse(right.stdout.toString("utf8")) as { state: string }).state;
        }
        const a = shown(left, mixed);
        const b = shown(right, pure);
        if (JSON.stringify(a) !== JSON.stringify(b)) problems.push({ step: index, runner, command: command.label, mixed: a, pure: b });
        const stateA = state(mixed);
        const stateB = state(pure);
        for (const key of Object.keys(stateA)) {
          if (stateA[key] !== stateB[key]) problems.push({ step: index, runner, command: command.label, field: key, mixed: stateA[key]?.slice(0, 600), pure: stateB[key]?.slice(0, 600) });
        }
        if (problems.length) break;
      }
      expect(problems.slice(0, 2)).toEqual([]);
    });
  }
});

describe("init 与几条单独的写法", () => {
  it("中断的事务（只有 intent）由下一次写入补判；审计末尾的半行单独成行；回滚到没有发布的那一条被拒", () => {
    const results = (["python", "node", "bun"] as const).map((runner) => {
      const repo = gitRepo(`interrupted-${runner}`);
      const before = '{"kill_grace_seconds": 20}' + String.fromCharCode(10);
      writeFileSync(join(repo, ".agent", "dispatch.config.json"), before);
      const sha = (text: string): string => createHash("sha256").update(text).digest("hex");
      const intent = {
        action: "config.set",
        actor: "user",
        after_ref: { kind: "config-snapshot", sha256: sha("{}"), stored: false },
        at: "2026-10-26T00:00:00Z",
        audit_id: `aud-${"1".repeat(32)}`,
        before_ref: { kind: "config-snapshot", sha256: sha(before), stored: false },
        confirmation: "none",
        invalidated_approvals: [],
        note: "P3 之前没有批准记录",
        phase: "intent",
        record_type: "management-audit",
        resource: "config",
        schema_version: 1,
        target: "kill_grace_seconds",
        txn: "2".repeat(32),
      };
      mkdirSync(join(repo, ".agent", "audit"), { recursive: true });
      writeFileSync(join(repo, ".agent", "audit", "management.jsonl"), JSON.stringify(intent).replaceAll('":', '": ').replaceAll(',"', ', "') + String.fromCharCode(10) + '{"half": ');
      const steps = [set("kill_grace_seconds", "25"), rollback(1), rollback(2, { dry_run: true, json: true })].map((command) => shown(run(runner, repo, command), repo));
      return { steps, state: state(repo) };
    });
    expect(results[1]).toEqual(results[0]);
    expect(results[2]).toEqual(results[0]);
  });

  it("每种运行方式各在一个新仓库里 init，再 init 一次被拒；结果与 Python 一致", () => {
    const results = (["python", "node", "bun"] as const).map((runner) => {
      const repo = gitRepo(`init-${runner}`);
      const first = shown(run(runner, repo, init), repo);
      const second = shown(run(runner, repo, init), repo);
      return { first, second, state: state(repo) };
    });
    expect(results[1]).toEqual(results[0]);
    expect(results[2]).toEqual(results[0]);
  });

  it("历史与审计目录没被忽略时提示 WARN；CODEKIT_ACTOR 不合格式时记 undeclared 并提示", () => {
    const results = (["python", "node", "bun"] as const).map((runner) => {
      const repo = gitRepo(`warn-${runner}`, { ignoreHistory: false });
      process.env["CODEKIT_ACTOR"] = "robot";
      try {
        return { run: shown(run(runner, repo, set("kill_grace_seconds", "30")), repo), state: state(repo) };
      } finally {
        process.env["CODEKIT_ACTOR"] = "user";
      }
    });
    expect(results[1]).toEqual(results[0]);
    expect(results[2]).toEqual(results[0]);
  });

  it("运行中：thinking 从显式 high 改成不写不算切换；预览报 needs_yes；令牌的哈希不是十六进制退出 2；删光子键连段删掉", () => {
    const profiles = (options: Record<string, string>): string =>
      JSON.stringify({ exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options }, other: { runtime: "pi", model: { provider: "step", id: "step-4" } } });
    const steps = [
      set("runtimes", RUNTIMES),
      set("profiles", profiles({ thinking: "high" })),
      set("roles", JSON.stringify({ execution: { mode: "headless", profile: "exec" } }), true),
      set("profiles", profiles({})),
      set("roles", JSON.stringify({ execution: { mode: "headless", profile: "other" } })),
      rollback(2, { dry_run: true, json: true }),
      rollback(2, { expect_state: `v1;config=${"g".repeat(64)}` }),
      set("pricing.s/only", PRICE("page")),
      unset("pricing.s/only"),
    ];
    const results = (["python", "node", "bun"] as const).map((runner) => {
      const repo = gitRepo(`switch-${runner}`, { running: true });
      return { steps: steps.map((command) => shown(run(runner, repo, command), repo)), state: state(repo) };
    });
    expect(results[0]?.steps.map((step) => step.status)).toEqual([0, 0, 0, 0, 1, 0, 2, 0, 0]);
    expect((JSON.parse(results[0]?.steps[5]?.stdout as string) as { needs_yes: boolean }).needs_yes).toBe(true);
    expect(results[1]).toEqual(results[0]);
    expect(results[2]).toEqual(results[0]);
  });
});

/** 起一个写命令的进程（不等它结束）。 */
function startWrite(runner: Runner, repo: string, command: Command): Promise<number> {
  const python = process.env["THEMIS_PYTHON"] ?? "python";
  const program = [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
    "import pi_dispatch as pd",
    `pd.KERNEL_IMPL_PATH = pd.Path(${JSON.stringify(join(ROOT, "absent-selector.json"))})`,
    `sys.exit(pd.main(${JSON.stringify(["--repo", repo, "config", ...command.argv])}))`,
  ].join("\n");
  const pyargs = JSON.stringify(command.args(repo), (_key, value: unknown) => (typeof value === "bigint" ? Number(value) : value));
  const encoded = Buffer.from(pyargs, "utf8").toString("base64");
  const main = join(REPO, "ts", "packages", "cli", "src", "main.ts");
  const [exe, args] =
    runner === "python" ? [python, ["-c", program]] : [runner === "bun" ? BUN : "node", [main, "--pyargs-b64", encoded]];
  return new Promise((done) => {
    const child = spawn(exe, args, { cwd: repo, stdio: "ignore" });
    child.on("close", (code) => done(code ?? -1));
  });
}

describe("锁互斥契约", () => {
  it("Python、Node、Bun 同时往同一份配置各写不同的键：读改写不丢更新，审计每笔都有 intent 与 commit", async () => {
    const repo = gitRepo("race");
    const runners: Runner[] = ["python", "node", "bun", "python", "node", "bun", "python", "node", "bun"];
    const codes = await Promise.all(runners.map((runner, index) => startWrite(runner, repo, set(`pricing.s/race${index}`, PRICE("race")))));
    expect(codes).toEqual(runners.map(() => 0));
    const config = JSON.parse(readFileSync(join(repo, ".agent", "dispatch.config.json"), "utf8")) as { pricing: Record<string, unknown> };
    expect(Object.keys(config.pricing).sort()).toEqual(runners.map((_runner, index) => `s/race${index}`).sort());
    const audit = readFileSync(join(repo, ".agent", "audit", "management.jsonl"), "utf8")
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line) as { phase: string; txn?: string });
    const intents = audit.filter((record) => record.phase === "intent").map((record) => record.txn);
    const commits = audit.filter((record) => record.phase === "commit").map((record) => record.txn);
    expect(intents.length).toBe(runners.length);
    expect(new Set(commits)).toEqual(new Set(intents));
    expect(existsSync(join(repo, ".agent", ".config.lock"))).toBe(false);
  });
});
