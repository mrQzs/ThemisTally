// run 之前几步的契约（迁移第 ④b7c1 片）：执行说明（render_instruction 与 setup_facts_text、self_check_command、
// machine_summary）、measured_check_seconds、shlex.quote、context_evidence、pi_preflight。每条先由 Python 回答，Node、Bun
// 逐字一致；pi_preflight 另外逐字节比较写进 preflight/ 的文件（三套实现各写各的目录，checked_at 抹掉）。语料是手写的边界
// 加按种子拼的组合；context_evidence 一律设 PI_CODING_AGENT_DIR，不读真实的 ~/.pi/agent。特殊字符用 ch() 拼，不写转义。
import { mkdirSync, readFileSync, readdirSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { loads } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { toTagged } from "../src/tagged.ts";
import { FAKE_PI } from "./fake-cli.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, prng, removeDir, runAgreeing, runBatch, scratchDir } from "./harness.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = ch(10);
const CR = ch(13);
const CRLF = CR + LF;
const TAB = ch(9);
const BS = ch(92);
const ESC = ch(27);
const SHORT_ROOT = scratchDir("run-pre");
const ROOT = realpathSync.native(SHORT_ROOT);
afterAll(() => removeDir(ROOT));

const tag = (value: unknown): unknown => toTagged(loads(JSON.stringify(value)));
const tagText = (text: string): unknown => toTagged(loads(text));
const call = (fn: string, fields: Record<string, unknown> = {}): ProbeRequest => ({ op: "run.call", fn, ...fields });

function agree(requests: readonly ProbeRequest[]): ProbeResult[] {
  const { python, mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
}

function put(file: string, text: string | Buffer): void {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, text);
}

// --- 执行说明 ---------------------------------------------------------------------------------------

const V01 = { id: "V01", argv: ["python", "-m", "pytest", "tests", "-q"], cwd: ".", timeout_seconds: 300, required: true, expected_exit_code: 0, expect_on_base: "fail" };
const V02 = {
  id: "V02",
  argv: ["node", "--test", "a b.mjs", 'say "hi"', "it's", "", `tail${BS}`, "中文"],
  cwd: "web app",
  env: { NODE_ENV: "test", A_KEY: "x y", Q: "it's" },
  timeout_seconds: 120,
  required: false,
  expected_exit_code: 2,
  expect_on_base: "pass",
};
const V03 = { id: "V03", argv: ["bash", "-c", "exit 0"], timeout_seconds: 60, expect_on_base: "any" };
const SCOPE = { allowed_modified_files: ["src/a.ts", "src/b c.ts"], allowed_new_files: [], allowed_deleted_files: ["old.ts"], forbidden_paths: ["secrets/"], dependency_changes: "forbidden" };
const META = { task_id: "t1", plan_version: 2, attempt_id: "t1.v2.a003", worktree: "C:/wt/{base}{timeout}/x", base_sha: "0123456789abcdef0123456789abcdef01234567" };
const TOOLS = [["read", "bash", "edit", "write"], ["read", "edit"], ["powershell", "read"], ["bash", "powershell"], []];
const ACTIONS = [["local_edit", "local_test"], ["local_edit"], ["local_edit", "local_test", "local_commit"], ["local_commit"]];
const CHECK_SETS = [[], [V01], [V01, V02, V03]];
const DODS = [[], [{ id: "D01", text: "a" }, { text: "没有 id" }], [{ id: "D01" }, { id: "D02" }]];
const SETUPS: unknown[] = [
  [],
  [{ id: "S01", argv: ["npm", "ci"], cwd: ".", passed: true, exit_code: 0 }],
  [{ id: "S02", argv: ["py", "a b", 'q"t', `x${BS}${BS}`], cwd: "sub", passed: false, exit_code: null }, {}],
  null,
];
const MEASURED: unknown[] = [null, { V01: 12 }, { V02: 905, V09: 3 }];

function contractOf(actions: unknown, checks: unknown, dod: unknown, scope: unknown = SCOPE): unknown {
  return { scope, authorization: { executor: actions }, checks, definition_of_done: dod };
}

function renderRequest(tools: unknown, actions: unknown, checks: unknown, dod: unknown, setup: unknown, measured: unknown, extra: string[] = [], meta: unknown = META, timeout = 1800): ProbeRequest {
  return call("render", {
    meta: tag(meta),
    contract: tag(contractOf(actions, checks, dod)),
    executor: tag({ tools }),
    timeout: tag(timeout),
    extra,
    setup: setup === null ? null : tag(setup),
    measured: measured === null ? null : tag(measured),
  });
}

describe("执行说明", () => {
  it("render_instruction：工具、授权、检查、DoD、setup 与实测用时的组合", () => {
    const random = prng(7301);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(random() * items.length)] as T;
    const requests: ProbeRequest[] = [];
    for (const tools of TOOLS) for (const actions of ACTIONS) requests.push(renderRequest(tools, actions, [V01, V02], DODS[1], [], { V01: 12 }));
    for (let index = 0; index < 60; index += 1) {
      requests.push(renderRequest(pick(TOOLS), pick(ACTIONS), pick(CHECK_SETS), pick(DODS), pick(SETUPS), pick(MEASURED), pick([[], [".agent/", "ts/"]]), META, pick([1, 60, 1800, 86400])));
    }
    // 有 shell 与自检授权、合同没有检查；带 setup 与实测用时
    requests.push(renderRequest(TOOLS[0], ACTIONS[0], [], DODS[0], SETUPS[2], null));
    requests.push(renderRequest(TOOLS[2], ACTIONS[2], [V02], DODS[2], SETUPS[1], { V02: 31 }, [".agent/"]));
    // 填进去的值里有花括号与占位符的名字：不再替换
    requests.push(renderRequest(TOOLS[0], ACTIONS[0], [V01], DODS[2], [], null, [], { ...META, task_id: "{attempt_id}", attempt_id: "{task_id}{{x}}" }));
    requests.push(renderRequest(TOOLS[0], ACTIONS[0], [{ ...V01, id: "{dod_ids}" }], [{ id: "{machine_summary}" }], [], null));
    // 合同版本与时限不是整数时照 str()
    requests.push(renderRequest(TOOLS[0], ACTIONS[0], [V01], DODS[2], [], null, [], { ...META, plan_version: "2" }, 1800));
    const python = agree(requests);
    expect(python.every((result) => result.ok)).toBe(true);
    expect(String(python[0]?.["value"])).toContain("自检照抄：`set -o pipefail; ");
  });

  it("render_instruction：DoD 的 id 不是字符串、缺 authorization 时照 Python 崩", () => {
    const python = agree([
      renderRequest(TOOLS[0], ACTIONS[0], [V01], [{ id: 1 }], [], null),
      call("render", { meta: tag(META), contract: tag({ scope: SCOPE, checks: [V01], definition_of_done: [] }), executor: tag({ tools: ["read"] }), timeout: tag(60) }),
      call("render", { meta: tag({ task_id: "t1" }), contract: tag(contractOf(["local_edit"], [], [])), executor: tag({ tools: ["read"] }), timeout: tag(60) }),
    ]);
    expect(python.map((result) => result.error)).toEqual(["TypeError", "KeyError", "KeyError"]);
  });

  it("machine_summary：期望退出码、必要与否、基线说明、cwd、超时与实测用时的写法", () => {
    const checks = [
      { ...V01, expected_exit_code: 0.0 },
      { ...V01, id: "V04", expected_exit_code: false, required: 0 },
      { ...V01, id: "V05", expected_exit_code: "0", required: "" },
      { ...V01, id: "V06", expected_exit_code: 3, expect_on_base: null, timeout_seconds: 300.5 },
      { ...V01, id: "V07", expect_on_base: "FAIL", cwd: "", argv: [""] },
      { id: "V08", argv: ["x"], timeout_seconds: 1 },
    ];
    const requests = [
      call("machine_summary", { contract: tagText(JSON.stringify(contractOf(["local_edit", "local_test"], checks, [])).replace('"expected_exit_code":0,', '"expected_exit_code":0.0,')), tools: ["bash"], measured: tag({ V01: 7, V06: 0 }) }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [V02], [], { ...SCOPE, allowed_modified_files: [], forbidden_paths: [], dependency_changes: "allowed" })), extra: ["a b", "中文/"], tools: ["powershell"] }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [V03], [])), tools: [] }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [], [], { ...SCOPE, allowed_new_files: [1, null, true] })) }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [], [], { allowed_modified_files: [] })) }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [{ ...V01, argv: ["x", 2] }], [])), tools: ["bash"] }),
      call("machine_summary", { contract: tag(contractOf(["local_edit"], [{ id: "V09", argv: ["x"] }], [])) }),
    ];
    const python = agree(requests);
    expect(python.map((result) => result.ok)).toEqual([true, true, true, true, false, false, false]);
    expect(python.slice(-2).map((result) => result.error)).toEqual(["TypeError", "KeyError"]);
  });

  it("self_check_command：bash、PowerShell、没有 shell，env 与 cwd 的各种写法", () => {
    const checks = [
      V01,
      V02,
      { ...V01, cwd: "" },
      { ...V01, cwd: "./" },
      { ...V01, cwd: "it's dir" },
      { ...V01, env: {} },
      { ...V01, env: null },
      { ...V01, env: { B: 2, A: true, C: null } },
      { ...V01, argv: ["", "@%+=:,./-_", "a*b", "$HOME", `x${TAB}y`, "é"] },
    ];
    const toolSets = [["bash"], ["powershell"], ["read", "edit"], [], ["powershell", "bash"]];
    agree(checks.flatMap((check) => toolSets.map((tools) => call("self_check", { check: tag(check), tools }))));
  });

  it("setup_facts_text：空、缺字段、失败与需要引号的参数", () => {
    const setups: unknown[] = [[], null, {}, [{}], [{ argv: [] }], [{ argv: ["a b", 'x"y', "", `c${BS}`, `d${BS}${BS}"`], cwd: "sub dir", passed: 1, exit_code: 0 }], ...SETUPS, [{ argv: ["a", 1] }], [{ argv: "ab c" }], { S01: 1 }];
    const python = agree(setups.map((setup) => call("setup_facts", { setup: setup === null ? null : tag(setup) })));
    expect(python.slice(-3).map((result) => result.error)).toEqual(["TypeError", undefined, "AttributeError"]);
  });

  it("shlex.quote：手写的边界与按种子拼的字符串", () => {
    const texts = ["", "abc", "a b", "it's", "''", "@%+=:,./-_", "é", `a${TAB}b`, `a${LF}b`, "$x", "*", "~", "中文", "-", "--flag=1", "a'b'c", BS];
    const random = prng(911);
    const alphabet = ["a", "Z", "0", "_", "-", ".", "/", "'", '"', " ", "$", "é", "中", BS, "@", "=", ":", ","];
    for (let index = 0; index < 200; index += 1) {
      texts.push(Array.from({ length: Math.floor(random() * 8) }, () => alphabet[Math.floor(random() * alphabet.length)]).join(""));
    }
    agree(texts.map((text) => call("shlex_quote", { text })));
  });
});

// --- 实测用时 ---------------------------------------------------------------------------------------

const ARGV = V01.argv;
const item = (id: unknown, wall: unknown, extra: Record<string, unknown> = {}): Record<string, unknown> => ({
  id,
  argv: ARGV,
  cwd: ".",
  timed_out: false,
  exit_code: 0,
  expected_exit_code: 0,
  wall_seconds: wall,
  ...extra,
});
const results = (...items: unknown[]): string => JSON.stringify({ results: items });

function runsTree(name: string, files: Record<string, string | null>): string {
  const runs = join(ROOT, "measured", name);
  mkdirSync(runs, { recursive: true });
  for (const [rel, text] of Object.entries(files)) {
    const file = join(runs, ...rel.split("/"));
    if (text === null) mkdirSync(file, { recursive: true });
    else put(file, text);
  }
  return runs;
}

describe("measured_check_seconds", () => {
  it("baseline 与 attempt 的 checks.json：同 id、argv、cwd，没超时、退出码等于期望的取最长", () => {
    // V03 不写 cwd：按 "." 比
    const checks = tag([V01, { ...V02, argv: ARGV, cwd: "." }, { id: "V03", argv: ARGV, timeout_seconds: 60 }]);
    const cases: [string, Record<string, string | null>][] = [
      ["empty", {}],
      ["basic", { "baseline/b1/checks.json": results(item("V01", 12.4)), "attempt-001/checks/c1/checks.json": results(item("V01", 15.5), item("V02", 2.5)) }],
      ["half-even", { "baseline/b1/checks.json": results(item("V01", 3.5), item("V02", 0.5)) }],
      ["mismatch", {
        "baseline/b1/checks.json": results(
          item("V01", 99, { argv: ["python"] }),
          item("V01", 98, { cwd: "sub" }),
          item("V01", 97, { cwd: null }),
          item("V01", 96, { timed_out: true }),
          item("V01", 95, { exit_code: 1 }),
          item("V02", 94, { exit_code: undefined, expected_exit_code: undefined }),
          item("V01", null),
          item("V01", undefined),
          item("V03", 93),
          item(1, 92),
        ),
      }],
      ["cwd-missing", { "baseline/b1/checks.json": results({ ...item("V01", 4), cwd: undefined }) }],
      ["types", { "attempt-002/checks/a/checks.json": results(item("V01", "7.5"), item("V02", true), item("V01", -3)) }],
      ["exit-float", { "attempt-002/checks/a/checks.json": results(item("V01", 6, { exit_code: 0.0 })) }],
      ["case", { "Baseline/B1/CHECKS.JSON": results(item("V01", 41)), "ATTEMPT-009/Checks/x/checks.json": results(item("V02", 42)) }],
      ["noise", {
        "attempt-003": "not a dir",
        "attempt-004/checks/x.json": results(item("V01", 50)),
        "attempt-005/checks/c/checks.json": null,
        "attempt-006/checks/c/checks.json": "{broken",
        "attempt-007/checks/c/checks.json": JSON.stringify({ results: null }),
        "attempt-008/checks/c/checks.json": JSON.stringify({ other: 1 }),
        "baseline/file.txt": "x",
        "attempt-010/checks/c/checks.json": results(item("V01", 8)),
      }],
    ];
    const requests = cases.map(([name, files]) => call("measured", { runs: runsTree(name, files), checks }));
    requests.push(call("measured", { runs: join(ROOT, "measured", "no-such"), checks }));
    const python = agree(requests);
    expect(python.every((result) => result.ok)).toBe(true);
  });

  it("NaN、无穷与写坏的类型：照 Python 的值或崩", () => {
    const checks = tag([V01]);
    const cases: [string, string][] = [
      ["nan", `{"results": [${JSON.stringify(item("V01", 0)).replace('"wall_seconds":0', '"wall_seconds":NaN')}]}`],
      ["nan-later", `{"results": [${JSON.stringify(item("V01", 5))}, ${JSON.stringify(item("V01", 0)).replace('"wall_seconds":0', '"wall_seconds":NaN')}]}`],
      ["inf", `{"results": [${JSON.stringify(item("V01", 0)).replace('"wall_seconds":0', '"wall_seconds":1e400')}]}`],
      ["bad-float", results(item("V01", "abc"))],
      ["list-wall", results(item("V01", [1]))],
      ["list-id", results(item(["V01"], 3))],
      ["dict-id", results(item({ a: 1 }, 3))],
      ["results-dict", JSON.stringify({ results: { V01: 1 } })],
      ["results-str", JSON.stringify({ results: "V01" })],
      ["results-int", JSON.stringify({ results: 3 })],
      ["top-list", JSON.stringify([1])],
      ["item-str", JSON.stringify({ results: ["V01"] })],
    ];
    const python = agree(cases.map(([name, text]) => call("measured", { runs: runsTree(`bad-${name}`, { "baseline/b/checks.json": text }), checks })));
    expect(python.filter((result) => !result.ok).length).toBeGreaterThan(5);
  });
});

// --- 上下文取证 -------------------------------------------------------------------------------------

interface Layout {
  readonly agent?: Record<string, string | null>;
  readonly outer?: Record<string, string | null>;
  readonly wt?: Record<string, string | null>;
}

function layout(name: string, spec: Layout): { agent: string; wt: string } {
  const base = join(ROOT, "ctx", name);
  const agent = join(base, "agent");
  const wt = join(base, "outer", "wt");
  mkdirSync(wt, { recursive: true });
  const fill = (dir: string, files: Record<string, string | null> | undefined): void => {
    for (const [rel, text] of Object.entries(files ?? {})) {
      const file = join(dir, ...rel.split("/"));
      if (text === null) mkdirSync(file, { recursive: true });
      else put(file, text);
    }
  };
  if (spec.agent) {
    mkdirSync(agent, { recursive: true });
    fill(agent, spec.agent);
  }
  fill(join(base, "outer"), spec.outer);
  fill(wt, spec.wt);
  return { agent, wt };
}

describe("context_evidence", () => {
  it("全局、祖先与 worktree 里的上下文文件，系统提示词文件，设置的键与项目资源", () => {
    const full = layout("full", {
      agent: { "AGENTS.md": "global rules" + LF, "SYSTEM.md": "sys", "APPEND_SYSTEM.md": "", "settings.json": JSON.stringify({ b: 1, a: 2, 中: 3 }) },
      outer: { "CLAUDE.md": "outer" + CRLF },
      wt: { "AGENTS.override.md": "override", "AGENTS.md": "plain", ".pi/settings.json": "{}", ".pi/skills": null, ".agents/skills/x.md": "x" },
    });
    const upper = layout("upper", { agent: { "CLAUDE.MD": "g", "settings.json": "[1, 2]", "SYSTEM.md": null }, wt: { "claude.md": "lower case name" } });
    const broken = layout("broken", { agent: { "settings.json": "{broken" }, outer: { "AGENTS.MD": "x" } });
    const empty = layout("empty", {});
    const requests: ProbeRequest[] = [];
    for (const mode of ["project", "none", "other"]) {
      requests.push(call("context_evidence", { work_dir: full.wt, mode, agent_dir: full.agent }));
      requests.push(call("context_evidence", { work_dir: upper.wt, mode, agent_dir: upper.agent }));
    }
    requests.push(call("context_evidence", { work_dir: broken.wt, mode: "project", agent_dir: broken.agent }));
    requests.push(call("context_evidence", { work_dir: empty.wt, mode: "project", agent_dir: empty.agent }));
    // 正斜杠、结尾的分隔符、8.3 短名（work_dir 不解析，祖先目录是解析过的长路径）
    requests.push(call("context_evidence", { work_dir: full.wt.replaceAll(BS, "/") + "/", mode: "project", agent_dir: full.agent.replaceAll(BS, "/") + "/" }));
    requests.push(call("context_evidence", { work_dir: join(SHORT_ROOT, "ctx", "full", "outer", "wt"), mode: "project", agent_dir: full.agent }));
    // ~ 展开（一个不存在的目录：只看路径怎么写，不读家目录里的东西）
    requests.push(call("context_evidence", { work_dir: empty.wt, mode: "none", agent_dir: "~/themis-contract-no-such-agent-dir" }));
    const python = agree(requests);
    expect(python.every((result) => result.ok)).toBe(true);
    expect(JSON.stringify(python[0])).toContain("ancestor");
  });
});

// --- 预检 -------------------------------------------------------------------------------------------

const RESOURCE = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp"];
const HELP = [
  "Usage: pi [options] [prompt]",
  "",
  "Options:",
  "  --provider <name>        Provider",
  "  --model <id>             Model ID",
  "  --thinking <level>       Thinking level: off, minimal, low, medium, high, xhigh",
  "  --mode <mode>            Output mode",
  "  --no-session             Do not save the session",
  "  --tools <list>           Allowed tools",
  ...RESOURCE.map((flag) => `  ${flag}`),
  "  --no-context-files       Skip AGENTS.md",
  "  --list-models [search]   List models",
  "",
  "Commands:",
  "  pi auth check            Check credentials",
  "",
  "Built-in Tool Names:",
  "  read     - Read file contents",
  "  bash     - Run commands",
  "  edit     - Edit files",
  "  write    - Write files",
  "",
].join(LF);
const TABLE = ["provider   model            context", "step       step-5           256K", "step       step-5-preview   256K", ""].join(LF);
const KEY = "sk-THEMISCONTRACTabcdefghijklmnop";
const GOOD = {
  help: { out: HELP },
  version: { out: "0.87.1" + LF },
  list: { out: TABLE },
  auth: { out: JSON.stringify({ status: "ok" }) + LF },
};
const EXECUTOR = { provider: "step", model: "step-5-preview", thinking: "high", tools: ["read", "bash", "edit", "write"], context_files: "project" };

interface PreflightCase {
  readonly name: string;
  readonly spec?: Record<string, unknown>;
  readonly executor?: Record<string, unknown>;
  readonly piCmd?: string[];
}

const PREFLIGHT: PreflightCase[] = [
  { name: "good" },
  { name: "help-fails", spec: { ...GOOD, help: { err: `boom api_key=${KEY}${LF}`, code: 2 } } },
  { name: "help-fails-both", spec: { ...GOOD, help: { out: HELP, err: `${"warn ".repeat(80)}${LF}`, code: 1 } } },
  { name: "no-mcp", spec: { ...GOOD, help: { out: HELP.replace("  --no-mcp" + LF, "") } } },
  { name: "context-none", spec: { ...GOOD, help: { out: HELP.replace("  --no-context-files       Skip AGENTS.md" + LF, "") } }, executor: { ...EXECUTOR, context_files: "none" } },
  { name: "thinking", executor: { ...EXECUTOR, thinking: "max" } },
  { name: "tools", executor: { ...EXECUTOR, tools: ["read", "grep", "find"] } },
  { name: "no-tool-list", spec: { ...GOOD, help: { out: HELP.slice(0, HELP.indexOf("Built-in Tool Names:")) } }, executor: { ...EXECUTOR, tools: ["grep"] } },
  { name: "version-text", spec: { ...GOOD, version: { out: `pi version unknown ${"z".repeat(250)}${LF}` } } },
  { name: "version-both", spec: { ...GOOD, version: { out: "0.87.1" + LF, err: "warning: 0.1.0" + LF } } },
  { name: "version-err", spec: { ...GOOD, version: { err: "0.90.0" + LF, code: 1 } } },
  { name: "version-old", spec: { ...GOOD, version: { out: "pi 0.80.3" + LF } } },
  { name: "version-min", spec: { ...GOOD, version: { out: "0.80.4" } } },
  { name: "version-digits", spec: { ...GOOD, version: { out: `pi ${ch(0x660)}.${ch(0x668, 0x667)}.${ch(0x661)}` } } },
  { name: "list-fails", spec: { ...GOOD, list: { err: `${"models.json broken ".repeat(20)}token=${KEY}`, code: 1 } } },
  { name: "list-fails-both", spec: { ...GOOD, list: { out: TABLE, err: "rate limited" + LF, code: 1 } } },
  { name: "list-missing", spec: { ...GOOD, list: { out: TABLE.replace("step-5-preview", "step-5-other  ") } } },
  { name: "no-auth", spec: { ...GOOD, help: { out: HELP.replace("  pi auth check            Check credentials", "  pi login") } } },
  { name: "auth-word", spec: { ...GOOD, help: { out: HELP.replace("  pi auth check            Check credentials", "  pi authorize            Authorize; api auth") } } },
  { name: "auth-fails", spec: { ...GOOD, auth: { out: JSON.stringify({ status: "missing", detail: `api_key=${KEY} ${"x".repeat(400)}` }), err: "ignored", code: 1 } } },
  { name: "auth-err-only", spec: { ...GOOD, auth: { err: "no credentials" + LF, code: 3 } } },
  { name: "ansi-crlf", spec: { ...GOOD, help: { out: HELP.replaceAll("--provider", `${ESC}[1m--provider${ESC}[0m`).replaceAll(LF, CRLF) }, list: { out: TABLE.replaceAll(LF, CRLF) + CR + "tail" } } },
  { name: "secret-in-help", spec: { ...GOOD, help: { out: HELP + `token: ${KEY}${LF}` } } },
  // strip_ansi 不幂等：去掉中间一段之后又拼出新的色码。pi-help.txt 先 strip_ansi 再 redact_secrets（里面又去一遍），一共去两遍
  { name: "ansi-nested", spec: { ...GOOD, help: { out: HELP + `${ESC}${ESC}[0m[1mnested${LF}` }, list: { out: TABLE + `${ESC}${ESC}[0m[1mnested${LF}` } } },
  { name: "no-program", piCmd: [join(ROOT, "no-such-pi.exe")] },
  // pi 的命令里带着凭据（例如 PI_DISPATCH_PI_CMD 写进了 key）：preflight.json 的 pi_command 要脱敏
  { name: "key-in-cmd", piCmd: [process.execPath, join(ROOT, "pre", "key-in-cmd", "bin", "fake-pi.mjs"), `--api-key=${KEY}`] },
];

function preflightRequests(impl: string): ProbeRequest[] {
  const env = ["SystemRoot", "PATH", "TEMP", "TMP"].filter((name) => process.env[name] !== undefined).map((name) => [name, process.env[name]]);
  return PREFLIGHT.map((item) => {
    const bin = join(ROOT, "pre", item.name, "bin");
    put(join(bin, "fake-pi.mjs"), FAKE_PI);
    put(join(bin, "fake-pi.json"), JSON.stringify(item.spec ?? GOOD));
    return call("preflight", {
      pi_cmd: item.piCmd ?? [process.execPath, join(bin, "fake-pi.mjs")],
      cwd: bin,
      executor: tag(item.executor ?? EXECUTOR),
      out_dir: join(ROOT, "pre", item.name, impl, "preflight"),
      env,
    });
  });
}

const scrubAt = (text: string): string =>
  text.replace(/("v":"checked_at"[}],[{]"t":"str","v":")[0-9T:Z-]+/gu, "$1<AT>").replace(/"checked_at": "[0-9T:Z-]+"/gu, '"checked_at": "<AT>"');

function filesOf(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of readdirSync(dir).sort()) out[name] = Buffer.from(scrubAt(readFileSync(join(dir, name)).toString("latin1")), "latin1").toString("hex");
  return out;
}

describe("pi_preflight", () => {
  it("参数、思考级别、工具、版本、模型与凭据：结果与 preflight/ 下的文件逐字节一致", () => {
    const [python, ...others] = IMPLS.map((impl) => ({ impl: impl.name, results: runBatch(impl, preflightRequests(impl.name)) }));
    PREFLIGHT.forEach((item, index) => {
      const want = scrubAt(JSON.stringify(python?.results[index]));
      const wantFiles = filesOf(join(ROOT, "pre", item.name, "python", "preflight"));
      for (const other of others) {
        expect(scrubAt(JSON.stringify(other.results[index])), `${item.name} · ${other.impl}`).toBe(want);
        expect(filesOf(join(ROOT, "pre", item.name, other.impl, "preflight")), `${item.name} · ${other.impl} 的文件`).toEqual(wantFiles);
      }
    });
    const good = JSON.stringify(python?.results[0]);
    expect(good).toContain('"v":"ok"},{"t":"bool","v":true}');
    expect(readFileSync(join(ROOT, "pre", "ansi-crlf", "python", "preflight", "pi-help.txt"), "latin1")).toContain(CR + CR + LF);
    expect(readFileSync(join(ROOT, "pre", "secret-in-help", "python", "preflight", "pi-help.txt"), "utf8")).not.toContain(KEY);
    expect(readFileSync(join(ROOT, "pre", "key-in-cmd", "python", "preflight", "preflight.json"), "utf8")).not.toContain(KEY);
    for (const name of ["pi-help.txt", "list-models.txt"]) expect(readFileSync(join(ROOT, "pre", "ansi-nested", "python", "preflight", name), "utf8")).not.toContain(ESC);
  });
});
