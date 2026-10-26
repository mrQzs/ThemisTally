// kit_roles 配置中心命令的命令行契约（迁移第 ③c 片）：runtime list|add|remove、profile show|add|edit|remove、role show|set、
// preset list|show|save|use|diff|remove。
//   - 读命令：同一个仓库里，Python、Node、Bun 的 stdout、stderr、退出码逐字节相同。
//   - 写命令：同一串命令在三个新仓库里各由一种实现执行，每一步的输出与最后的配置、本机文件、快照、history 与审计都与
//     Python 那一份一致（比较口径见 config-cli.ts）。序列里有各种被拒的写法、--dry-run --json 的预览、过期的令牌、
//     本机文件的写与删、preset use 列出的合同版本记录。
// PATH 前面放临时目录里的假 pi、claude（只解析、不运行），后面接原来的 PATH（git、python 要用）。凭据库设 off。
import { chmodSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { type Command, CONTEXT, RUNNERS, gitRepo, run, shown, state } from "./config-cli.ts";
import { removeDir, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("roles-cmd"));
const BIN = join(ROOT, "bin");
mkdirSync(BIN, { recursive: true });
writeFileSync(join(BIN, "pi.exe"), "");
writeFileSync(join(BIN, "claude.cmd"), "@echo off");
const TOKEN = `sk-${"c3".repeat(12)}`;

const SAVED: Record<string, string | undefined> = {};
beforeAll(() => {
  const env: Record<string, string | undefined> = {
    CODEKIT_SECRET_STORE: "off",
    PI_DISPATCH_PI_CMD: undefined,
    PI_DISPATCH_WORKTREE_ROOT: undefined,
    NoDefaultCurrentDirectoryInExePath: undefined,
    CODEKIT_ACTOR: "user",
    PATH: `${BIN};${process.env["PATH"] ?? ""}`,
  };
  for (const [name, value] of Object.entries(env)) {
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

const WRITE_FLAGS = { yes: false, dry_run: false, json: false, expect_state: null };

/** 一条 kit_roles 命令：path 是 config 之后的两段，fields 是 argparse 的 Namespace（含缺省值）。 */
function roles(path: [string, string], argv: string[], fields: Record<string, unknown>): Command {
  return { label: [...path, ...argv].join(" "), argv: [...path, ...argv], args: (repo) => ({ command: ["config", ...path], repo, ...fields, context: CONTEXT }) };
}

interface WriteOptions {
  readonly yes?: boolean;
  readonly dryRun?: boolean;
  readonly expectState?: string;
}
const flags = (options: WriteOptions): { argv: string[]; fields: Record<string, unknown> } => ({
  argv: [...(options.yes ? ["--yes"] : []), ...(options.dryRun ? ["--dry-run", "--json"] : []), ...(options.expectState ? [`--expect-state=${options.expectState}`] : [])],
  fields: { ...WRITE_FLAGS, yes: Boolean(options.yes), dry_run: Boolean(options.dryRun), json: Boolean(options.dryRun), expect_state: options.expectState ?? null },
});

const runtimeList = (json = false): Command => roles(["runtime", "list"], json ? ["--json"] : [], { json });
const runtimeAdd = (id: string, adapter: string, extra: { command?: string; force?: boolean } & WriteOptions = {}): Command => {
  const { argv, fields } = flags(extra);
  return roles(
    ["runtime", "add"],
    [id, "--adapter", adapter, ...(extra.command !== undefined ? ["--command", extra.command] : []), ...(extra.force ? ["--force"] : []), ...argv],
    { runtime_id: id, adapter, command_option: extra.command ?? null, force: Boolean(extra.force), ...fields },
  );
};
const runtimeRemove = (id: string, options: WriteOptions = {}): Command => {
  const { argv, fields } = flags(options);
  return roles(["runtime", "remove"], [id, ...argv], { runtime_id: id, ...fields });
};
const profileShow = (id: string | null = null, json = false): Command =>
  roles(["profile", "show"], [...(id === null ? [] : [id]), ...(json ? ["--json"] : [])], { profile_id: id, json });
interface ProfileOptions extends WriteOptions {
  readonly runtime?: string;
  readonly model?: string;
  readonly thinking?: string;
  readonly credentials?: string[];
}
const profileWrite = (action: "add" | "edit", id: string, options: ProfileOptions): Command => {
  const { argv, fields } = flags(options);
  const args = [
    ...(options.runtime !== undefined ? ["--runtime", options.runtime] : []),
    ...(options.model !== undefined ? ["--model", options.model] : []),
    ...(options.thinking !== undefined ? ["--thinking", options.thinking] : []),
    ...(options.credentials ?? []).flatMap((name) => ["--credential-env", name]),
  ];
  return roles(["profile", action], [id, ...args, ...argv], {
    profile_id: id,
    runtime: options.runtime ?? null,
    model: options.model ?? null,
    thinking: options.thinking ?? null,
    credential_env: options.credentials ?? null,
    ...fields,
  });
};
const profileRemove = (id: string, options: WriteOptions = {}): Command => {
  const { argv, fields } = flags(options);
  return roles(["profile", "remove"], [id, ...argv], { profile_id: id, ...fields });
};
const roleShow = (json = false): Command => roles(["role", "show"], json ? ["--json"] : [], { json });
const roleSet = (role: string, target: string, extra: { host?: string; cadence?: number } & WriteOptions = {}): Command => {
  const { argv, fields } = flags(extra);
  const args = [...(extra.host !== undefined ? ["--host", extra.host] : []), ...(extra.cadence !== undefined ? ["--cadence-seconds", String(extra.cadence)] : [])];
  return roles(["role", "set"], [role, target, ...args, ...argv], {
    role,
    target,
    host: extra.host ?? null,
    cadence_seconds: extra.cadence === undefined ? null : BigInt(extra.cadence),
    ...fields,
  });
};
const presetList = (json = false): Command => roles(["preset", "list"], json ? ["--json"] : [], { json });
const presetShow = (name: string, json = false): Command => roles(["preset", "show"], [name, ...(json ? ["--json"] : [])], { name, json });
const presetSave = (name: string, extra: { description?: string; roles?: string; force?: boolean } & WriteOptions = {}): Command => {
  const { argv, fields } = flags(extra);
  const args = [
    ...(extra.description !== undefined ? ["--description", extra.description] : []),
    ...(extra.roles !== undefined ? ["--roles", extra.roles] : []),
    ...(extra.force ? ["--force"] : []),
  ];
  return roles(["preset", "save"], [name, ...args, ...argv], { name, description: extra.description ?? null, roles: extra.roles ?? null, force: Boolean(extra.force), ...fields });
};
const presetUse = (name: string, options: WriteOptions = {}): Command => {
  const { argv, fields } = flags(options);
  return roles(["preset", "use"], [name, ...argv], { name, ...fields });
};
const presetDiff = (a: string, b: string, json = false): Command => roles(["preset", "diff"], [a, b, ...(json ? ["--json"] : [])], { a, b, json });
const presetRemove = (name: string, options: WriteOptions = {}): Command => {
  const { argv, fields } = flags(options);
  return roles(["preset", "remove"], [name, ...argv], { name, ...fields });
};
/** kit_config 的 set（第 ③b 片已移植），序列里用来改 allowed_executors。 */
const configSet = (key: string, value: string): Command => ({
  label: `set ${key} ${value}`,
  argv: ["set", key, value],
  args: (repo) => ({ command: ["config", "set"], repo, key, value, yes: false, context: CONTEXT }),
});

const STALE = `v1;config=${"0".repeat(64)}`;

/** 写命令的序列：每一步都在三个仓库里各跑一次（每个仓库只用一种实现）。 */
const SEQUENCE: readonly Command[] = [
  runtimeList(),
  runtimeAdd("pi", "pi"),
  runtimeAdd("pi", "claude-code"),
  runtimeAdd("pi", "pi", { command: '["C:/tools/pi.exe", "--x"]' }),
  runtimeAdd("pi", "pi", { command: '["C:/tools/pi.exe", "--x"]' }),
  runtimeAdd("Bad", "pi"),
  runtimeAdd("x", "nope"),
  runtimeAdd("y", "pi", { command: "[]" }),
  runtimeAdd("y", "pi", { command: `["${TOKEN}"]` }),
  runtimeAdd("y", "pi", { command: "not json" }),
  runtimeAdd("cc", "claude-code"),
  runtimeAdd("oc", "opencode", { command: '["C:/tools/oc.exe"]', dryRun: true }),
  runtimeAdd("oc", "opencode", { command: '["C:/tools/oc.exe"]', expectState: STALE }),
  runtimeAdd("oc", "opencode", { command: '["C:/tools/oc.exe"]' }),
  runtimeList(),
  runtimeList(true),
  profileWrite("add", "exec", { runtime: "pi", model: "step/step-5", thinking: "high", credentials: ["STEP_KEY", "STEP_ALT"] }),
  profileWrite("add", "exec", { runtime: "pi", model: "step/step-5" }),
  profileWrite("add", "Bad", { runtime: "pi", model: "step/step-5" }),
  profileWrite("add", "p2", { runtime: "pi", model: "nomodel" }),
  profileWrite("add", "p3", { runtime: "ghost", model: "step/step-4" }),
  profileWrite("add", "hostp", { runtime: "cc", model: "anthropic/claude-x" }),
  profileWrite("add", "plain", { runtime: "pi", model: "step/step-4" }),
  profileWrite("edit", "exec", { thinking: "low" }),
  profileWrite("edit", "exec", { thinking: "low" }),
  profileWrite("edit", "exec", {}),
  profileWrite("edit", "ghost", { thinking: "low" }),
  profileWrite("edit", "plain", { model: "step/step-5", credentials: ["K1"], dryRun: true }),
  profileShow(),
  profileShow("exec", true),
  profileShow("ghost"),
  profileShow(TOKEN),
  roleShow(),
  roleSet("execution", "exec"),
  roleSet("contract", "hostp"),
  roleSet("planning_review", "interactive_host", { host: "codex" }),
  roleSet("planning_review", "manual"),
  roleSet("boss", "exec"),
  roleSet("scheduler_agent", "exec", { cadence: 120 }),
  roleSet("execution", "manual", { host: "x" }),
  roleSet("execution", "plain", { cadence: 60 }),
  roleSet("scheduler_agent", "disabled", { cadence: 60 }),
  roleShow(),
  roleShow(true),
  presetSave("day", { description: "白天" }),
  presetSave("day"),
  presetSave("night", { roles: " execution , contract ,", force: true }),
  presetSave("Bad"),
  presetSave("x", { roles: "execution,boss" }),
  presetSave("x", { roles: "scheduler_agent,planning_review" }),
  configSet("allowed_executors", '[{"provider": "step", "model": "step-4"}]'),
  roleSet("execution", "plain"),
  roleSet("execution", "exec"),
  configSet("allowed_executors", '[{"provider": "step", "model": "step-5", "thinking": "high"}]'),
  roleSet("execution", "exec"),
  presetList(),
  presetList(true),
  presetShow("day"),
  presetShow("night", true),
  presetShow("ghost"),
  presetShow("_x"),
  presetDiff("day", "night"),
  presetDiff("day", "night", true),
  presetUse("night"),
  presetUse("night"),
  roleSet("execution", "plain"),
  roleShow(),
  presetShow("night"),
  presetUse("day", { dryRun: true }),
  presetList(),
  roleShow(),
  presetRemove("night"),
  presetUse("day"),
  presetRemove("night"),
  presetRemove("ghost"),
  profileRemove("exec"),
  profileRemove("ghost"),
  runtimeRemove("pi"),
  runtimeRemove("ghost"),
  runtimeRemove("oc"),
  runtimeList(),
  profileRemove("p3"),
  roleSet("contract", "manual"),
  profileRemove("hostp"),
  runtimeRemove("cc"),
];

describe("写命令序列", () => {
  it("三种实现各在一个新仓库里跑同一串命令：每一步的输出与最后的状态都与 Python 一致", () => {
    const results = RUNNERS.map((runner) => {
      const repo = gitRepo(join(ROOT, `seq-${runner}`));
      // preset use 列出按角色写的合同版本：一份有记录、一份没有、一份记录坏了、一份不是按角色写的
      const plans = join(repo, ".agent", "plans");
      mkdirSync(plans, { recursive: true });
      const contract = (task: string, executor: unknown): string => JSON.stringify({ task_id: task, plan_version: 1, executor });
      writeFileSync(join(plans, "t1.v1.json"), contract("t1", { role: "execution" }));
      writeFileSync(join(plans, "t2.v1.json"), contract("t2", { role: "contract" }));
      writeFileSync(join(plans, "T3.V1.JSON"), contract("t3", { role: "execution" }));
      writeFileSync(join(plans, "t4.v1.json"), contract("t4", { provider: "step", model: "step-5" }));
      writeFileSync(join(plans, "broken.v1.json"), "{");
      mkdirSync(join(repo, ".agent", "runs", "t1"), { recursive: true });
      writeFileSync(join(repo, ".agent", "runs", "t1", "binding-v1.json"), JSON.stringify({
        role: "execution", profile: "exec", runtime: "pi", adapter: "pi", provider: "step", model: "step-5", thinking: "high",
        contract_json_sha256: "a".repeat(64), created_at: "2026-10-26T00:00:00Z", created_by_attempt: "attempt-001", active_preset: null, config_sha256: null,
      }));
      mkdirSync(join(repo, ".agent", "runs", "t3"), { recursive: true });
      writeFileSync(join(repo, ".agent", "runs", "t3", "binding-v1.json"), "{");
      const steps = SEQUENCE.map((command) => ({ command: command.label, ...shown(run(runner, repo, command), repo) }));
      return { steps, state: state(repo) };
    });
    const python = results[0] as (typeof results)[number];
    const statuses = python.steps.map((step) => (step as Record<string, unknown>)["status"]);
    expect(statuses.filter((status) => status !== 0).length, "序列里要有被拒的写法").toBeGreaterThan(15);
    // 序列确实走到了这些路径（Python 的输出里有）
    const output = JSON.stringify(python.steps);
    for (const fragment of [
      "已登记 runtime pi（adapter pi）",
      "改 adapter 要加 --force",
      "命令写进了 .agent/dispatch.local.json",
      "--command 里有疑似凭据",
      "--command 必须是非空的 JSON 字符串数组",
      "needs_yes",
      "--expect-state",
      "也删去了 .agent/dispatch.local.json 里的命令",
      "影响（写入之前）",
      "t1.v1（execution）：沿用版本记录",
      "t2.v1（contract）：还没有记录，会用新绑定",
      "版本记录无效",
      "WARN  contract 绑定到 claude-code",
      "不在 allowed_executors 里",
      "的思考级别固定为 high",
      "正在用：先 preset use 别的方案",
      "被 profile",
      "被 roles.execution",
      "← 与方案",
      "相同",
    ]) {
      expect(output, fragment).toContain(fragment);
    }
    for (const [index, other] of results.slice(1).entries()) {
      const differ = other.steps.findIndex((step, position) => JSON.stringify(step) !== JSON.stringify(python.steps[position]));
      expect(differ === -1 ? null : { runner: RUNNERS[index + 1], python: python.steps[differ], other: other.steps[differ] }).toEqual(null);
      expect(other.state).toEqual(python.state);
    }
  });
});

describe("读命令", () => {
  it("没有配置、配置无效、不在 Git 仓库里", () => {
    const empty = gitRepo(join(ROOT, "empty"));
    const invalid = gitRepo(join(ROOT, "invalid"));
    writeFileSync(join(invalid, ".agent", "dispatch.config.json"), JSON.stringify({ runtimes: { pi: { adapter: "nope" } } }));
    const plain = join(ROOT, "plain");
    mkdirSync(plain, { recursive: true });
    const reads = [runtimeList(), runtimeList(true), profileShow(), profileShow(null, true), roleShow(), roleShow(true), presetList(), presetList(true)];
    const problems: unknown[] = [];
    for (const [repo, commands] of [
      [empty, reads],
      [invalid, reads],
      [plain, [roleShow(), runtimeAdd("pi", "pi"), roleSet("execution", "x"), presetSave("day")]],
    ] as const) {
      for (const command of commands) {
        const python = shown(run("python", repo, command), repo);
        for (const runner of ["node", "bun"] as const) {
          const other = shown(run(runner, repo, command), repo);
          if (JSON.stringify(other) !== JSON.stringify(python)) problems.push({ command: command.label, runner, python, other });
        }
      }
    }
    expect(problems.slice(0, 2)).toEqual([]);
  });
});

describe("本机文件写不进去", () => {
  // 两资源事务的第二步：配置已经写了，本机文件的替换失败（MoveFileExW，[WinError 5] …: '临时文件' -> '本机文件'）
  it.runIf(process.platform === "win32")("本机文件只读时 runtime add --command 报写入失败；恢复之后的写入补判中断的事务", () => {
    const results = RUNNERS.map((runner) => {
      const repo = gitRepo(join(ROOT, `readonly-local-${runner}`));
      const local = join(repo, ".agent", "dispatch.local.json");
      const steps = [shown(run(runner, repo, runtimeAdd("pi", "pi", { command: '["C:/tools/a.exe"]' })), repo)];
      chmodSync(local, 0o444);
      try {
        steps.push(shown(run(runner, repo, runtimeAdd("pi", "pi", { command: '["C:/tools/b.exe"]' })), repo));
      } finally {
        chmodSync(local, 0o644);
      }
      steps.push(shown(run(runner, repo, runtimeAdd("pi", "pi", { command: '["C:/tools/c.exe"]' })), repo));
      return { steps, state: state(repo) };
    });
    const python = results[0] as (typeof results)[number];
    expect(python.steps.map((step) => step["status"])).toEqual([0, 1, 0]);
    expect(String(python.steps[1]?.["stderr"])).toContain("写入失败：[WinError 5] Access is denied: ");
    expect(results[1]).toEqual(python);
    expect(results[2]).toEqual(python);
  });
});
