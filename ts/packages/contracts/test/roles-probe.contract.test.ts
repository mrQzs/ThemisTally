// 会运行本机 CLI 的配置中心命令的命令行契约（迁移第 ③d 片）：runtime scan [--add]、runtime probe、models、doctor [--record]。
//   - 假的 pi、claude、codex 与只留它们的 PATH 见 fake-cli.ts；场景改的是 BIN 里 fake-pi.json 的回答。
//   - 读命令：同一个仓库里 Python、Node、Bun 的 stdout、stderr、退出码与假 pi 的记录逐字节相同；scan --add 各用一个新仓库，
//     最后的配置、快照与审计也要相同。每个场景另断言 Python 的输出里有它要测的路径。
// 转义的反斜杠一律用 String.fromCharCode(92) 拼（源码里不写 \u 转义）。
import { copyFileSync, existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { type Command, CONTEXT, RUNNERS, type Runner, gitRepo, run, shown, state } from "./config-cli.ts";
import { installFakeCli } from "./fake-cli.ts";
import { removeDir, runPythonCli, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("roles-probe"));
const BIN = join(ROOT, "bin");
const LF = String.fromCharCode(10);
const ESC = String.fromCharCode(27);
const WIN = process.platform === "win32";

const SAVED: Record<string, string | undefined> = {};
beforeAll(() => {
  const env: Record<string, string | undefined> = {
    PATH: installFakeCli(BIN),
    CODEKIT_SECRET_STORE: "off",
    CODEKIT_ACTOR: "user",
    PI_DISPATCH_PI_CMD: undefined,
    PI_DISPATCH_WORKTREE_ROOT: undefined,
    FAKE_PI_LOG: undefined,
    FAKE_KEY: "k",
    GITHUB_TOKEN: "x",
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

// --- 命令 --------------------------------------------------------------------------------------------

const cmd = (path: string[], argv: string[], fields: Record<string, unknown>): Command => ({
  label: [...path, ...argv].join(" "),
  argv: [...path, ...argv],
  args: (repo) => ({ command: ["config", ...path], repo, ...fields, context: CONTEXT }),
});
const probe = (id: string, json = false): Command => cmd(["runtime", "probe"], [id, ...(json ? ["--json"] : [])], { runtime_id: id, json });
const models = (runtime: string, json = false): Command => cmd(["models"], [runtime, ...(json ? ["--json"] : [])], { runtime, json });
const doctor = (record: string | null = null, json = false): Command =>
  cmd(["doctor"], [...(record === null ? [] : ["--record", record]), ...(json ? ["--json"] : [])], { record, json });
const scan = (add = false, json = false, yes = false): Command =>
  cmd(["runtime", "scan"], [...(add ? ["--add"] : []), ...(json ? ["--json"] : []), ...(yes ? ["--yes"] : [])], { add, json, yes });

/** 用真实的 Python 命令搭配置（夹具，不在比较之列）。 */
function setup(repo: string, steps: string[][]): void {
  for (const step of steps) {
    const done = runPythonCli(["--repo", repo, "config", ...step], repo);
    if (done.status !== 0) throw new Error(`搭配置失败：${step.join(" ")}：${done.stderr.toString("utf8")}`);
  }
}

const BASE_STEPS = [
  ["runtime", "add", "pi", "--adapter", "pi"],
  ["runtime", "add", "cc", "--adapter", "claude-code", "--command", JSON.stringify(["node", join(BIN, "fake-pi.mjs")])],
  ["profile", "add", "exec", "--runtime", "pi", "--model", "step/step-5", "--thinking", "high", "--credential-env", "FAKE_KEY"],
  ["profile", "add", "con", "--runtime", "pi", "--model", "step/step-5", "--thinking", "max"],
  ["profile", "add", "sched", "--runtime", "cc", "--model", "step/step-5"],
  ["role", "set", "execution", "exec"],
  ["role", "set", "contract", "con"],
  ["role", "set", "scheduler_agent", "sched"],
];

const RECORD = {
  role: "execution", profile: "exec", runtime: "pi", adapter: "pi", provider: "step", model: "step-5", thinking: "high",
  contract_json_sha256: "ab".repeat(32), created_at: "2026-10-26T00:00:00Z", created_by_attempt: "attempt-001", active_preset: null, config_sha256: null,
};

function writeRecord(repo: string, task: string, version: number, record: unknown): void {
  mkdirSync(join(repo, ".agent", "runs", task), { recursive: true });
  writeFileSync(join(repo, ".agent", "runs", task, `binding-v${version}.json`), JSON.stringify(record));
}

// --- 假 pi 的回答 ------------------------------------------------------------------------------------

const RESOURCE = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp"];
const helpText = (levels: string, drop: string[] = []): string =>
  [
    "Usage: pi [options]",
    "  --provider <name>",
    "  --model <id>",
    `  --thinking <level>   Thinking level: ${levels}`,
    "  --mode <mode>",
    "  --no-session",
    "  --tools <list>",
    ...RESOURCE.map((flag) => `  ${flag}`),
    "  --no-context-files",
    "",
    "Built-in Tool Names:",
    "  read - Read",
    "",
  ]
    .filter((line) => !drop.some((flag) => line.trim() === flag))
    .join(LF);
const TABLE = ["provider  model           context", "step      step-5          256K", "step      step-5-preview  256K", "openai    sk-abcdefghijklmnop  1K", ""].join(LF);

interface Reply {
  readonly out?: string;
  readonly err?: string;
  readonly code?: number;
}
type Spec = Record<string, Reply>;

const GOOD: Spec = {
  version: { out: `${ESC}[1mpi 0.80.4${ESC}[0m${LF}build x${LF}`, err: "deprecation warning" },
  // --no-mcp 写在 stderr：解析的是 stdout 与 stderr 接起来的文字
  help: { out: helpText("off, minimal, low, medium, high, xhigh, max", ["--no-mcp"]), err: "  --no-mcp" },
  list: { out: TABLE },
  auth: { out: '{"ok": true}' },
};

// --- 场景 --------------------------------------------------------------------------------------------

interface Scenario {
  readonly name: string;
  readonly spec: Spec;
  /** 在共用仓库的基础配置上再跑的 Python 命令。 */
  readonly extra?: string[][];
  readonly env?: Record<string, string | undefined>;
  readonly commands: readonly Command[];
  /** Python 的输出里必须有的片段：场景确实走到了要测的路径。 */
  readonly expect: readonly string[];
  /** 在仓库根目录放一份 fake-pi.mjs（相对路径的命令用）。 */
  readonly localScript?: boolean;
}

const READS = [probe("pi"), probe("pi", true), probe("cc"), probe("cc", true), models("pi"), models("pi", true), doctor(), doctor(null, true)];

const SCENARIOS: readonly Scenario[] = [
  {
    name: "全部就绪：版本取第一行并去掉颜色、--help 齐全、模型在表里、登录成功；不接通的适配器与允许列表",
    spec: GOOD,
    extra: [["set", "allowed_executors", JSON.stringify([{ provider: "step", model: "step-5", thinking: "high" }])]],
    commands: [...READS, probe("ghost"), models("cc"), models("ghost")],
    expect: ["pi 0.80.4", "缺少的参数：无", "在允许列表", "<redacted>", "本轮没有接通 scheduler_agent", "的思考级别固定为 high，profile 是 max", "没有登记 runtime 'ghost'", "适配器列不出模型"],
  },
  {
    name: "缺参数、思考级别不支持、模型不匹配、登录失败、版本退出码不是 0、凭据被移除",
    spec: {
      version: { err: `boom sk-abcdefghijklmnop${LF}second`, code: 2 },
      help: { out: helpText("off, low", ["--no-mcp", "--no-context-files"]) },
      "list:step-5": { out: 'No models matching "step-5"' },
      list: { out: "No models available. Configure a provider." },
      auth: { err: "token expired sk-zzzzzzzzzzzzzzzz", code: 1 },
    },
    extra: [["set", "env_remove", JSON.stringify(["FAKE_KEY"])]],
    commands: READS,
    expect: ["--version 退出码 2", "pi 缺少参数：--no-mcp、--no-context-files", "思考级别 high 不受本机 pi 支持", "没有与 step-5 匹配的", "凭据未就绪", "凭据变量不可用", "没有可用的模型（no_models）"],
  },
  {
    name: "--list-models 执行失败：报错先脱敏再截取",
    // 前面是 300 多个字的普通文字、凭据在后面：截取的 200 个字看得出来，也看得出先脱敏
    spec: { ...GOOD, list: { err: `${"bad entry in models.json ".repeat(13)}api_key=sk-qqqqqqqqqqqqqqqq`, code: 1 } },
    commands: [models("pi"), models("pi", true), doctor(), doctor(null, true)],
    expect: ["--list-models 退出码 1", "pi --list-models 执行失败（退出码 1）"],
  },
  {
    name: "PI_DISPATCH_PI_CMD 指向批处理垫片：经 cmd.exe 运行",
    spec: GOOD,
    env: { PI_DISPATCH_PI_CMD: JSON.stringify([join(BIN, "pi.cmd")]) },
    commands: [probe("pi"), probe("pi", true), models("pi"), doctor(null, true)],
    expect: ["来源 env", "pi.cmd"],
  },
  {
    name: "PI_DISPATCH_PI_CMD 带批处理特殊字符、写错",
    spec: GOOD,
    env: { PI_DISPATCH_PI_CMD: JSON.stringify([join(BIN, "pi.cmd"), "a&b"]) },
    commands: [probe("pi"), models("pi"), doctor()],
    expect: ["含批处理特殊字符"],
  },
  {
    name: "PI_DISPATCH_PI_CMD 不是字符串数组",
    spec: GOOD,
    env: { PI_DISPATCH_PI_CMD: "[1]" },
    commands: [probe("pi"), models("pi"), doctor(), doctor(null, true)],
    expect: ["必须是 JSON 字符串数组", "找不到 runtime pi 的命令"],
  },
  {
    name: "命令里有相对路径",
    spec: GOOD,
    localScript: true,
    extra: [["runtime", "add", "rel", "--adapter", "pi", "--command", JSON.stringify(["node", "fake-pi.mjs"])], ["profile", "add", "relp", "--runtime", "rel", "--model", "step/step-5"], ["role", "set", "execution", "relp"]],
    commands: [probe("rel"), doctor(), doctor(null, true)],
    expect: ["命令里有相对路径（fake-pi.mjs）"],
  },
  {
    name: "--help 退出码不是 0（参数齐全）",
    spec: { ...GOOD, help: { ...GOOD.help, code: 1 } },
    commands: [probe("pi"), probe("pi", true), doctor()],
    expect: ["--help 退出码 1", '\\"ok\\": false'],
  },
  {
    name: "模型在别的 provider 下、凭据变量为空",
    spec: { ...GOOD, "list:step-5": { out: `provider model${LF}openrouter step-5${LF}` } },
    env: { FAKE_KEY: "" },
    commands: [doctor(), doctor(null, true)],
    expect: ["执行模型 step/step-5 不在可用模型列表中", "FAKE_KEY 不可用"],
  },
  {
    name: "doctor --record：记录在、格式不对、没有记录、记录无效",
    spec: GOOD,
    commands: [doctor("t-probe.v1"), doctor("t-probe.v1", true), doctor("nope"), doctor("t-probe.v2"), doctor("t-bad.v1")],
    expect: ["版本记录 .agent/runs/t-probe/binding-v1.json", "--record 写成 <task-id>.v<N>", "还没有版本记录", "字段不全或类型不对"],
  },
];

interface StepResult {
  readonly label: string;
  readonly result: Record<string, unknown>;
}

function runReads(scenario: Scenario, index: number): void {
  const repo = gitRepo(join(ROOT, "reads", `s${index}`));
  setup(repo, [...BASE_STEPS, ...(scenario.extra ?? [])]);
  writeRecord(repo, "t-probe", 1, RECORD);
  writeRecord(repo, "t-bad", 1, { ...RECORD, thinking: 3 });
  writeFileSync(join(BIN, "fake-pi.json"), JSON.stringify(scenario.spec));
  if (scenario.localScript) {
    copyFileSync(join(BIN, "fake-pi.mjs"), join(repo, "fake-pi.mjs"));
    copyFileSync(join(BIN, "fake-pi.json"), join(repo, "fake-pi.json"));
  }
  const saved = Object.fromEntries(Object.keys(scenario.env ?? {}).map((name) => [name, process.env[name]]));
  for (const [name, value] of Object.entries(scenario.env ?? {})) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  try {
    const results = RUNNERS.map((runner) => {
      const log = join(ROOT, "logs", `s${index}-${runner}.jsonl`);
      mkdirSync(dirname(log), { recursive: true });
      process.env["FAKE_PI_LOG"] = log;
      const steps: StepResult[] = scenario.commands.map((command) => ({ label: command.label, result: shown(run(runner, repo, command), repo) }));
      return { steps, log: existsSync(log) ? readFileSync(log, "utf8") : "" };
    });
    const python = results[0] as (typeof results)[number];
    const output = JSON.stringify(python.steps);
    for (const fragment of scenario.expect) expect(output, `${scenario.name}：${fragment}`).toContain(fragment);
    for (const [position, other] of results.slice(1).entries()) {
      const differ = other.steps.findIndex((step, at) => JSON.stringify(step) !== JSON.stringify(python.steps[at]));
      expect(differ === -1 ? null : { runner: RUNNERS[position + 1], python: python.steps[differ], other: other.steps[differ] }, scenario.name).toEqual(null);
      expect(other.log, `${scenario.name}：假 pi 收到的参数与环境`).toEqual(python.log);
    }
  } finally {
    delete process.env["FAKE_PI_LOG"];
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

describe.runIf(WIN)("runtime probe、models、doctor", () => {
  for (const [index, scenario] of SCENARIOS.entries()) {
    it(scenario.name, () => runReads(scenario, index));
  }

  it("配置无效、不在 Git 仓库里", () => {
    writeFileSync(join(BIN, "fake-pi.json"), JSON.stringify(GOOD));
    const invalid = gitRepo(join(ROOT, "invalid"));
    writeFileSync(join(invalid, ".agent", "dispatch.config.json"), JSON.stringify({ runtimes: { pi: { adapter: "nope" } } }));
    const plain = join(ROOT, "plain");
    mkdirSync(plain, { recursive: true });
    const problems: unknown[] = [];
    for (const repo of [invalid, plain]) {
      for (const command of [probe("pi"), models("pi"), doctor(), scan(), scan(true)]) {
        const python = shown(run("python", repo, command), repo);
        for (const runner of ["node", "bun", "launcher"] as const) {
          const other = shown(run(runner, repo, command), repo);
          if (JSON.stringify(other) !== JSON.stringify(python)) problems.push({ command: command.label, runner, python, other });
        }
      }
    }
    expect(problems.slice(0, 2)).toEqual([]);
  });
});

describe.runIf(WIN)("runtime scan", () => {
  it("三种实现各在一个新仓库里扫描、登记：每一步的输出与最后的状态都与 Python 一致", () => {
    writeFileSync(join(BIN, "fake-pi.json"), JSON.stringify(GOOD));
    const results = RUNNERS.map((runner: Runner) => {
      const repo = gitRepo(join(ROOT, "scan", runner));
      setup(repo, [["runtime", "add", "pi", "--adapter", "pi"]]);
      const steps = [scan(), scan(false, true), scan(true), scan(true, true), scan(true, false, true)].map((command) => ({ label: command.label, result: shown(run(runner, repo, command), repo) }));
      return { steps, state: state(repo) };
    });
    const python = results[0] as (typeof results)[number];
    const output = JSON.stringify(python.steps);
    for (const fragment of ["pi.CMD（", "pi 0.80.4", "claude 9.9.9 (fake)", "[WinError 216]", "PATH 上没有", "已登记：claude-code、codex", "已登记：没有新的"]) {
      expect(output, fragment).toContain(fragment);
    }
    for (const other of results.slice(1)) expect(other).toEqual(python);
  });
});

