// 第 ⑤c 片的契约（迁移计划第 ⑤ 步）：回合审计。kit_hub.py 的 turn_cost_usd、stream_events、session_cut_short、
// claude_session_effort、claude_path_rule、audit_claude_stream、path_forms、pi_reach_problem、guard_config、audit_pi_stream、
// pi_flags_problem 交给 Python、Node、Bun，逐字比带标签的结果（崩溃比类型）。语料：
//   - tests/test_kit_hub.py 里不经 Engine 的审计用例：Python 探针跑一遍，记下它们对审计函数的每一次顶层调用，三边重放；
//   - guard.ts（第 106 轮的守卫扩展）用同一份 guard_config 判同一批调用，拦下的说明与 piReachProblem 逐字相同；
//   - 按种子生成、再随机换掉值的类型的 claude 与 pi 事件流，加坏行、断行字符与嵌套；手写的边界；
//   - 会话文件（临时的 USERPROFILE 与信箱）；pi 的 --help（假的 pi）；
//   - TS 独有（⑤e0）：piSupportedFlags 并发调同一个 pi 命令只起一次、非零退出缓存成 null、探的时候抛了异常不留缓存。
// 已知差异（迁移计划第 10 节）：Node 后备的 normcase 用 toLowerCase，带 İ、ẞ 的路径只比 Python 与 Bun；嵌套在 900 到 2997 层
// 之间时 Python 的结果随调用栈深度变，生成的嵌套避开这一段；NaN 不进 claude 的模型名（Python 的集合次序随散列变）。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pyTruthy } from "@themis/base/pyfmt";
import { guardConfig, piSupportedFlags } from "@themis/hub/audit";
import { GUARD_PREFIX, GUARD_SUFFIX } from "@themis/hub/constants";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { BUN, IMPLS, type Impl, PYTHON, type ProbeRequest, type ProbeResult, REPO, TS_BUN, prng, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const BS = ch(92);
const LF = ch(10);
const ROOT = scratchDir("audit");
// 临时目录带 8.3 短名（ADMINI~1）：path_forms 经 resolve 得到长名，命令里写短名对不上、不算碰主工作区。主工作区按长名搭，
// 短名的写法另作一种“不该被判违规”的写法（第 10 节）
const LONG = realpathSync.native(ROOT);
const MAIN = join(LONG, "Repo");
const WORK = join(MAIN, "wt");
mkdirSync(WORK, { recursive: true });
afterAll(() => removeDir(ROOT));

/** 字面量写成 Python 的值：整数是 int，带 F() 的是 float，对象是 dict。 */
class Float {
  readonly value: number;
  constructor(value: number) {
    this.value = value;
  }
}
const F = (value: number): Float => new Float(value);
function py(value: unknown): PyValue {
  if (value instanceof Float) return value.value;
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}
/** claude 与 pi 写事件流的样子：JSON.stringify 的紧凑写法，非 ASCII 原样。 */
const line = (value: unknown): string => dumps(py(value), { ensureAscii: false, separators: [",", ":"] });
const call = (fn: string, ...args: unknown[]): ProbeRequest => ({ op: "hub.audit", fn, args: args.map((arg) => toTagged(py(arg))) });

/** “'<' 不能比”里的两个类型名：只在排序的输入来自集合时换成占位（Python 的集合次序随 str 散列的盐变，谁先跟谁比不确定）。 */
const SET_SORT = /'<' not supported between instances of '[^']*' and '[^']*'/g;
const setSorted = (result: ProbeResult | undefined): string => JSON.stringify(result).replace(SET_SORT, "'<' not supported between instances of '<TYPE>' and '<TYPE>'");

/** setSort(at)：第 at 个请求的排序输入来自集合（models、levels），比之前照 setSorted 规整；别的逐字比。 */
function agree(requests: readonly ProbeRequest[], impls: readonly Impl[] = IMPLS, setSort: (at: number) => boolean = () => false): ProbeResult[] {
  const [python, ...others] = impls.map((impl) => runBatch(impl, requests));
  const shownAt = (results: readonly ProbeResult[] | undefined, at: number): string => (setSort(at) ? setSorted(results?.[at]) : JSON.stringify(results?.[at]));
  for (const [index, other] of others.entries()) {
    const bad = requests.map((_, at) => at).filter((at) => shownAt(python, at) !== shownAt(other, at));
    const shown = bad.slice(0, 2).map((at) => ({ at, fn: requests[at]?.["fn"], python: JSON.stringify(python?.[at]).slice(0, 1500), other: JSON.stringify(other[at]).slice(0, 1500) }));
    expect(shown, `${impls[index + 1]?.name} 与 Python 不同（共 ${bad.length} 处）`).toEqual([]);
  }
  return python as ProbeResult[];
}

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_claude_audit_rejects_advisor_and_tools_outside_the_allowlist", "test_refused_calls_outside_the_allowlist_only_warn",
  "test_claude_audit_checks_init_and_model", "test_pi_audit_rejects_tools_and_records_effective_level",
  "test_audits_name_model_api_errors_instead_of_blaming_the_output", "test_pi_refused_calls_outside_the_allowlist_only_warn",
  "test_audit_reads_when_a_rate_limit_lifts", "test_claude_path_rule_uses_the_absolute_form",
  "test_the_guard_extension_judges_every_call_like_the_audit", "test_calls_the_guard_blocked_are_warnings_not_violations",
  "test_pi_workers_load_the_guard_with_the_kernel_roots", "test_claude_workers_are_audited_for_the_main_worktree_too",
  "test_u2028_in_a_tool_call_cannot_hide_it_from_the_audit", "test_unreadable_stream_lines_are_violations",
  "test_the_pi_audit_takes_the_last_accepted_deliver", "test_unreadable_lines_are_not_counted_as_unreadable_deliveries",
  "test_a_deliver_that_quotes_the_main_worktree_is_not_a_reach", // ⑤d2 时补：它只调 audit_pi_stream，不经 TurnRunner
];
const FUNCTIONS = ["audit_claude_stream", "audit_pi_stream", "pi_reach_problem", "guard_config", "path_forms", "claude_path_rule", "stream_events",
  "jsonl_lines", "turn_cost_usd"];

/** 每条记下的调用：(用例, 函数名, 参数)。 */
/** 采样当时的结果与 Python 重放对不上的用例：重放读的是用例跑完时的文件、用例改过的全局已经撤销，这几条不算重放过那个场景。 */
function drifted(calls: readonly { test: string; result: string }[], python: readonly ProbeResult[]): string[] {
  return [...new Set(calls.filter((item, at) => JSON.stringify(JSON.parse(item.result)) !== JSON.stringify(python[at])).map((item) => item.test))].sort();
}

function pytestCalls(): { test: string; fn: string; args: PyValue[]; result: string }[] {
  const tmp = join(ROOT, "samples");
  mkdirSync(tmp, { recursive: true });
  const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, tmp });
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  return (value.get("calls") as PyDict[]).map((item) => ({ test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: item.get("result") as string }));
}

describe("第 ⑤c 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  const calls = pytestCalls();

  it("每条用例都记到了调用；三边重放逐字相同，都正常返回", () => {
    expect(new Set(calls.map((item) => item.test))).toEqual(new Set(TESTS));
    const requests = calls.map((item) => ({ op: "hub.audit", fn: item.fn, args: item.args.map(toTagged) }));
    const python = agree(requests);
    expect(python.filter((result) => !result.ok)).toEqual([]);
    expect(drifted(calls, python), "当时的结果与 Python 重放").toEqual([]);
  });

  it("guard.ts 与 Python、TS 的审计用同一份 guard_config，判同一批调用逐条一致（Node 与 Bun 各跑一次扩展）", () => {
    const reach = calls.filter((item) => item.test === "test_the_guard_extension_judges_every_call_like_the_audit" && item.fn === "pi_reach_problem");
    expect(reach.length).toBeGreaterThan(20);
    const [, , workspace, repo] = reach[0]?.args as [string, PyValue, string, string];
    // pi 交给守卫的参数总是对象；不是对象的参数 Python 的审计会崩，守卫不必对照
    const cases = [...reach.map((item) => [item.args[0], item.args[1]] as [string, PyValue]), ...randomReachCases(prng(51), 160)]
      .filter(([, args]) => args instanceof Map);
    const config = guardConfig(workspace, repo);
    expect(valueOf(runBatch(PYTHON, [call("guard_config", workspace, repo)])[0])).toBe(config);
    const python = agree(cases.map(([name, args]) => call("pi_reach_problem", name, args, workspace, repo)));
    const expected = cases.map(([name], index) => {
      const [level, note] = valueOf(python[index]) as [string, string];
      return name !== "deliver" && level === "violation" ? { block: true, reason: GUARD_PREFIX + note + GUARD_SUFFIX } : null;
    });
    expect(expected.filter(Boolean).length).toBeGreaterThan(20);
    for (const runtime of ["node", BUN]) {
      expect(runGuard(runtime, cases, config), `guard.ts 在 ${runtime} 下`).toEqual(expected);
    }
  });
});

/** guard.ts 的 guardDecision：写一个驱动脚本，由 node 或 bun 加载扩展（pi 在 Node 里加载它）。 */
function runGuard(runtime: string, cases: readonly [string, PyValue][], config: string): unknown[] {
  const driver = join(ROOT, "guard-driver.ts");
  const guard = pathToFileURL(join(REPO, "scripts", "hub", "guard.ts")).href;
  writeFileSync(driver, [
    `import { guardDecision } from ${JSON.stringify(guard)};`,
    'import { readFileSync } from "node:fs";',
    'const input = JSON.parse(readFileSync(0, "utf8"));',
    "console.log(JSON.stringify(input.cases.map(([name, args]) => guardDecision(name, args, input.config) ?? null)));",
    "",
  ].join(LF));
  const plain = (value: PyValue): unknown => JSON.parse(dumps(value));
  const done = spawnSync(runtime, [driver], {
    input: JSON.stringify({ cases: cases.map(([name, args]) => [name, plain(args)]), config: JSON.parse(config) }), encoding: "utf8", timeout: 120_000,
  });
  expect(done.status, done.stderr).toBe(0);
  return JSON.parse(done.stdout) as unknown[];
}

// --- 二、按种子生成、再改坏的事件流 ----------------------------------------------------------------------------

const pick = <T>(next: () => number, items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
/** 嵌套 depth 层的列表（只取 600：避开 Python 结果随调用栈变的那一段；更深的直接拼成文字，见 deepLine）。 */
const nested = (depth: number): unknown => {
  let value: unknown = "底";
  for (let index = 0; index < depth; index += 1) value = [value];
  return value;
};
/** 4000 层的 JSON 文字：两边都读不出来（Python 报 RecursionError，base 的 loads 在 1000 层报同一种），算坏行。 */
const deepLine = (depth: number): string => `${"[".repeat(depth)}0${"]".repeat(depth)}`;
const SEPARATORS = [ch(0x2028), ch(0x2029), ch(0x85), ch(0x0b), ch(0x1e)];

/** 路径的各种写法：工作目录里外、主工作区与它的依赖、输入目录、大小写与分隔符换过的、相对路径。 */
function somePath(next: () => number): string {
  const main = MAIN.split(BS).join("/");
  const bases = [WORK, MAIN, join(MAIN, "ts", "node_modules", "x"), join(MAIN, "desktop", "web", "node_modules"), join(LONG, "inputs"), LONG, join(ROOT, "Repo"), main,
    `/${main[0]}${main.slice(2)}`, MAIN.toUpperCase(), "..", "../wtx", "a.py", ".", ""];
  const base = pick(next, bases);
  return next() < 0.5 ? base : `${base}${pick(next, ["/", BS])}${pick(next, ["scripts", ".agent", "README.md", "中文.md", ".."])}`;
}

function randomArgs(next: () => number): unknown {
  const roll = next();
  if (roll < 0.3) return { path: somePath(next) };
  if (roll < 0.6) return { command: `${pick(next, ["cat", "ls", "git -C", "cd", "python"])} ${somePath(next)}${pick(next, ["", " && ls", ` ${somePath(next)}`])}` };
  if (roll < 0.75) return { pattern: "x", path: somePath(next), extra: [somePath(next), { deep: somePath(next) }] };
  if (roll < 0.85) return { file_path: somePath(next) };
  return pick(next, [{}, { path: null }, { path: 7 }, [["path", somePath(next)]], "ab", [somePath(next)], { report: `见 ${somePath(next)}` }]);
}

function randomReachCases(next: () => number, count: number): [string, PyValue][] {
  return Array.from({ length: count }, () => [pick(next, ["read", "grep", "find", "ls", "write", "edit", "bash", "deliver"]), py(randomArgs(next))] as [string, PyValue]);
}

/** 换掉值的类型：数字写成字符串、布尔、null、超大整数、浮点、空的与非空的列表和字典、深的嵌套。 */
function mutate(next: () => number, value: unknown, depth = 0): unknown {
  if (next() < 0.06) {
    return pick(next, [null, true, false, 0, -1, 2n ** 70n, F(1), F(1.5), F(Number.POSITIVE_INFINITY), "", "x", [], {}, [1, "a"], { a: [] }, nested(600),
      `a${pick(next, SEPARATORS)}b`]);
  }
  if (Array.isArray(value)) return value.map((item) => mutate(next, item, depth + 1));
  if (value !== null && typeof value === "object" && !(value instanceof Float)) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, mutate(next, item, depth + 1)]));
  }
  return value;
}

function junk(next: () => number): string {
  return pick(next, ["坏行", "[1]", "1", "  ", "{", `{"type":"agent_end"`, line(nested(600)), deepLine(4000), `${ch(0xfeff)}{"type":"agent_end"}`]);
}

const PI_SPEC = { tools: ["read", "grep", "find", "ls", "deliver"], provider: "p", model: "m" };

function piEvent(next: () => number): unknown {
  const id = pick(next, ["c1", "c2", "c3"]);
  const roll = next();
  if (roll < 0.3) return { type: "tool_execution_start", toolName: pick(next, ["read", "grep", "write", "edit", "bash", "deliver", "web"]), toolCallId: id, args: randomArgs(next) };
  if (roll < 0.55) {
    const name = pick(next, ["read", "bash", "deliver", "web"]);
    const text = pick(next, [`Tool ${name} not found`, `${GUARD_PREFIX}write 写到了工作目录之外：x${GUARD_SUFFIX}`, "ok", ` Tool bash not found${LF}`, ""]);
    return { type: "tool_execution_end", toolName: name, toolCallId: id, isError: next() < 0.6,
      result: { content: [{ type: "text", text }, { type: "image" }], details: pick(next, [{}, { report: "交了" }, null, [], "x"]) } };
  }
  if (roll < 0.85) {
    return { type: "message_end", message: { role: pick(next, ["assistant", "assistant", "user"]), provider: pick(next, ["p", "q", 1]), model: pick(next, ["m", "n", null]),
      thinkingLevel: pick(next, ["high", "max", "", null, 3]), stopReason: pick(next, ["stop", "error", "toolUse", null, "length"]), errorMessage: pick(next, ["429", "", null]),
      content: [{ type: "thinking", thinking: pick(next, ["嗯", "", null, F(2.5)]) }, { type: "text", text: pick(next, ["做完了", "  ", ""]) }],
      usage: { input: pick(next, [10, F(1.5), true, 2n ** 70n]), output: pick(next, [3, F(Number.NaN), "x"]), reasoning: pick(next, [5, F(0.5)]) } } };
  }
  return { type: pick(next, ["agent_settled", "agent_end", "turn_end"]) };
}

const CLAUDE_SPEC = { tools: ["Read", "Grep", "Glob", "LS"], model: "claude-sonnet-5-5" };

function claudeEvent(next: () => number): unknown {
  const id = pick(next, ["t1", "t2", "t3"]);
  const roll = next();
  if (roll < 0.12) {
    return { type: "system", subtype: "init", tools: pick(next, [["Read", "Grep", "Glob", "LS"], ["Read"], "Read", ["LS", "Read", "Grep", "Glob"], [1, "a"]]),
      mcp_servers: pick(next, [[], [{ name: "docs" }, "x"], 1, "ab"]), memory_paths: pick(next, [null, { auto: "x" }, [nested(600)]]),
      model: pick(next, ["claude-sonnet-5-5", "claude-haiku-5-5", null]), session_id: "s1" };
  }
  if (roll < 0.45) {
    const blocks = [
      { type: "tool_use", id, name: pick(next, ["Read", "Bash", "StructuredOutput", "Write", "Glob"]), input: randomArgs(next) },
      { type: pick(next, ["text", "server_tool_use"]), text: "ok", name: "advisor" },
    ];
    return { type: "assistant", error: pick(next, [null, "rate_limit", ""]), is_api_error_message: next() < 0.2, api_error_status: pick(next, [403, null]),
      api_error_code: pick(next, ["oauth", null]), message: { model: pick(next, ["claude-sonnet-5-5", "<synthetic>", "claude-haiku-5-5", 7]), content: blocks } };
  }
  if (roll < 0.7) {
    return { type: "user", message: { content: [{ type: "tool_result", tool_use_id: id, is_error: next() < 0.6,
      content: pick(next, ["No such tool available: Bash", [{ type: "text", text: "No such tool available" }], "Permission denied", null, nested(600)]) }] } };
  }
  if (roll < 0.8) return { type: "rate_limit_event", rate_limit_info: { status: pick(next, ["rejected", "allowed"]), resetsAt: pick(next, [1761900000, true, "x", F(1.5), null]) } };
  return { type: "result", result: pick(next, ["ok", 7, null, ""]), terminal_reason: pick(next, [null, "api_error"]), is_error: next() < 0.3, total_cost_usd: pick(next, [F(0.5), null]),
    structured_output: pick(next, [{ report: "交了" }, null, [1]]), usage: { output_tokens_details: { thinking_tokens: pick(next, [12, null]) } } };
}

/** 流里有没有进 models 集合的、不是字符串的 model（assistant 事件的 message.model 为真才进）：有的话 sorted 报哪一对不确定。 */
function oddModel(lines: readonly string[]): boolean {
  return lines.some((text) => {
    let event: PyValue;
    try {
      event = loads(text);
    } catch {
      return false;
    }
    const message = event instanceof Map && event.get("type") === "assistant" ? event.get("message") : null;
    const model = message instanceof Map ? (message.get("model") ?? null) : null;
    return pyTruthy(model) && typeof model !== "string";
  });
}

function randomStream(next: () => number, event: (next: () => number) => unknown): string[] {
  return Array.from({ length: 1 + Math.floor(next() * 10) }, () => (next() < 0.08 ? junk(next) : line(mutate(next, event(next)))));
}

describe("第 ⑤c 片：按种子生成、再改坏的事件流", () => {
  it.each([1, 2, 3])("pi 的事件流，种子 %i：150 份 × 有无工作目录", (seed) => {
    const next = prng(seed);
    const requests = Array.from({ length: 150 }, () => {
      const lines = randomStream(next, piEvent);
      const spec = next() < 0.1 ? mutate(next, PI_SPEC) : PI_SPEC;
      return next() < 0.7 ? call("audit_pi_stream", lines, spec, WORK, MAIN) : call("audit_pi_stream", lines, spec, null, null);
    });
    const results = agree(requests);
    expect(results.filter((result) => result.ok).length).toBeGreaterThan(60); // 不是一路崩到底
    expect(results.some((result) => !result.ok)).toBe(true);
  });

  it.each([1, 2, 3])("claude 的事件流，种子 %i：150 份 × 有无工作目录", (seed) => {
    const next = prng(100 + seed);
    const odd: boolean[] = [];
    const requests = Array.from({ length: 150 }, () => {
      const lines = randomStream(next, claudeEvent);
      odd.push(oddModel(lines));
      return next() < 0.7 ? call("audit_claude_stream", lines, CLAUDE_SPEC, WORK, MAIN) : call("audit_claude_stream", lines, CLAUDE_SPEC, null, null);
    });
    const results = agree(requests, IMPLS, (at) => odd[at] === true); // 只有 models 这个集合混了类型的才打占位
    expect(results.filter((result) => result.ok).length).toBeGreaterThan(40);
    expect(results.some((result) => !result.ok)).toBe(true);
  });

  it("碰没碰主工作区：随机调用 400 个，三边逐字相同", () => {
    agree(randomReachCases(prng(7), 400).map(([name, args]) => call("pi_reach_problem", name, args, WORK, next7() < 0.9 ? MAIN : null)));
  });

  it("逐行解析：坏行、断行字符、BOM、只有空白的行、深的嵌套", () => {
    const lines = ["{}", "[1]", "1", "  ", "", `{"a":1}${ch(0x2028)}`, ch(0xfeff) + "{}", `${ch(0x85)}{}${ch(0x85)}`, line(nested(600)), deepLine(4000), "{", "NaN", `{"x":NaN}`];
    agree([call("stream_events", lines), call("jsonl_lines", lines.join(LF)), call("jsonl_lines", `a${ch(0x2028)}b${LF}c${ch(13)}${LF}`)]);
  });
});

const seven = prng(77);
const next7 = (): number => seven();

// --- 三、手写的边界 ----------------------------------------------------------------------------------------------

describe("第 ⑤c 片：手写的边界", () => {
  it("turn_cost_usd：恰好一半取偶、累计变小、float() 的各种写法与报错", () => {
    const results = agree([
      call("turn_cost_usd", "claude", { cost_usd_total: F(0.5) }, F(0.5078125)), call("turn_cost_usd", "claude", { cost_usd_total: F(2) }, F(1)),
      call("turn_cost_usd", "claude", {}, F(1)), call("turn_cost_usd", "pi", {}, " 1_0.5 "), call("turn_cost_usd", "pi", {}, ch(0x661, 0x662)),
      call("turn_cost_usd", "pi", {}, "abc"), call("turn_cost_usd", "pi", {}, null), call("turn_cost_usd", "claude", { cost_usd_total: "x" }, F(1)),
      call("turn_cost_usd", "claude", [], F(1)), call("turn_cost_usd", "pi", {}, true), call("turn_cost_usd", "pi", {}, { a: 1 }),
      call("turn_cost_usd", "claude", { cost_usd_total: F(Number.POSITIVE_INFINITY) }, F(Number.POSITIVE_INFINITY)),
    ]);
    expect(valueOf(results[0])).toEqual([0.007812, 0.5078125]);
    expect(results.map((result) => result.error ?? "")).toEqual(["", "", "", "", "", "ValueError", "", "ValueError", "AttributeError", "", "TypeError", ""]);
  });

  it("path_forms、guard_config、pi_reach_problem：中文目录、大小写写错的主工作区、/c/ 写法（三边）", () => {
    const work = join(ROOT, "中文目录", "工作");
    const main = join(ROOT, "中文目录");
    agree([
      call("path_forms", work), call("guard_config", work, main), call("pi_reach_problem", "read", { path: join(main, "a.md") }, work, main),
      call("pi_reach_problem", "bash", { command: `cat ${main.toUpperCase()}/a` }, work, main),
      call("pi_reach_problem", "bash", { command: `cat /${main[0]?.toLowerCase()}${main.slice(2).split(BS).join("/")}/a` }, work, main),
    ]);
  });

  it("带 İ、ẞ、词尾 Σ 的目录：normcase 走 LCMapStringEx，只比 Python 与 Bun（Node 后备是已知差异）", () => {
    const dir = join(ROOT, `${ch(0x130)}stanbul${ch(0x1e9e)}${ch(0x391, 0x3a3)}`);
    const work = join(dir, "wt");
    agree([
      call("guard_config", work, dir), call("path_forms", work), call("pi_reach_problem", "read", { path: join(dir, "x") }, work, dir),
      call("pi_reach_problem", "write", { path: join(dir, "x") }, work, dir), call("pi_reach_problem", "read", { path: join(work, "x") }, work, dir),
    ], [PYTHON, TS_BUN]);
  });

  it("claude_path_rule：8.3 短名、大小写写错、相对路径、不存在的路径（Path.resolve 给出磁盘上的写法）", () => {
    const short = process.env["TEMP"] ?? ROOT;
    agree([call("claude_path_rule", short.toUpperCase()), call("claude_path_rule", WORK.toLowerCase()), call("claude_path_rule", "relative/dir"),
      call("claude_path_rule", join(ROOT, "gone", "x"))]);
  });

  it("审计的崩溃与 Python 同型：不是字典的消息、不可散列的编号、混了类型的工具表、spec 缺键", () => {
    const pi = (event: unknown): ProbeRequest => call("audit_pi_stream", [line(event)], PI_SPEC, WORK, MAIN);
    const claude = (...events: unknown[]): ProbeRequest => call("audit_claude_stream", events.map(line), CLAUDE_SPEC, WORK, MAIN);
    const init = { type: "system", subtype: "init", tools: ["Read", "Grep", "Glob", "LS"], model: "claude-sonnet-5-5" };
    const results = agree([
      pi({ type: "message_end", message: { role: "assistant", usage: [1] } }),
      call("audit_pi_stream", [F(1.5), 2n ** 1100n].map((input) => line({ type: "message_end", message: { role: "assistant", provider: "p", model: "m", usage: { input } } })), PI_SPEC, WORK, MAIN),
      call("audit_pi_stream", [line({ type: "tool_execution_start", toolName: "write", args: [1] })], { ...PI_SPEC, tools: [...PI_SPEC.tools, "write"] }, WORK, MAIN), pi({ type: "tool_execution_start", toolName: "bash", args: [1, [2, "x"]] }),
      pi({ type: "tool_execution_end", toolName: "deliver", result: { content: [{ text: 5 }] } }),
      claude(init, { type: "assistant", message: { content: [{ type: "tool_use", name: "StructuredOutput", id: [1] }] } }),
      claude(init, { type: "assistant", message: { model: [1] } }), claude(init, { type: "assistant", message: "x" }),
      claude({ ...init, tools: ["Read", 1] }), claude({ ...init, tools: [[1]] }), claude({ ...init, tools: 5 }),
      claude(init, { type: "user", message: { content: [{ type: "tool_result", tool_use_id: { a: 1 }, is_error: true }] } }),
      claude(init, { type: "assistant", message: { model: 1 } }, { type: "assistant", message: { model: "a" } }),
      claude(init, { type: "assistant", message: { content: [{ type: "tool_use", name: "Read", id: "t", input: [["path", "a"], ["b"]] }] } }),
      claude(init, { type: "assistant", message: { content: [{ type: "tool_use", name: "Read", id: "t", input: [[[1], "a"]] }] } }),
      claude(init, { type: "assistant", message: { content: [{ type: "tool_use", name: "Read", id: "t", input: "ab" }] } }),
      claude(init, { type: "rate_limit_event", rate_limit_info: [1] }),
      call("audit_pi_stream", [], { tools: ["read"] }, null, null), call("audit_claude_stream", [], { tools: 1, model: "m" }, null, null),
      // 不崩的三例：说明截到 200 个字；1 与 1.0 在集合里是同一个；dict() 把长度为 2 的字符串当成一对
      call("pi_reach_problem", "bash", { command: `${"x".repeat(250)} cat ${MAIN}` }, WORK, MAIN),
      claude(init, { type: "assistant", message: { model: 1 } }, { type: "assistant", message: { model: F(1) } }),
      claude(init, { type: "assistant", message: { content: [{ type: "tool_use", name: "Read", id: "t", input: ["fp", ["path", join(MAIN, "x")]] }] } }),
    ], IMPLS, (at) => at === 12); // 第 12 条：models 是集合，里面有 1 与 "a"；第 8 条的工具表是列表，照样逐字比
    expect(results.map((result) => result.error ?? "")).toEqual([
      "AttributeError", "OverflowError", "AttributeError", "", "TypeError", "TypeError", "TypeError", "AttributeError", "TypeError", "TypeError", "TypeError",
      "TypeError", "TypeError", "ValueError", "TypeError", "ValueError", "AttributeError", "KeyError", "TypeError", "", "", "",
    ]);
  });
});

// --- 四、会话文件与 pi 的 --help ---------------------------------------------------------------------------------

describe("第 ⑤c 片：会话文件与 pi 的 --help", () => {
  const home = join(ROOT, "home");
  const projects = join(home, ".claude", "projects");
  const write = (path: string, lines: readonly string[]): void => {
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, lines.join(LF));
  };
  const toolUse = line({ type: "assistant", message: { stop_reason: "tool_use", content: [{ type: "tool_use", name: "Read" }] } });
  const answered = line({ type: "user", message: { content: [{ type: "tool_result", content: "ok" }] } });
  // 一个目录名是另一个的前缀：Path 逐段比时 C--Code-ThemisTally 在前，整串比时 -kb3 在前（'-' 小于分隔符）
  write(join(projects, "C--Code-ThemisTally", "s1.jsonl"), [toolUse]);
  write(join(projects, "C--Code-ThemisTally-kb3", "s1.jsonl"), [toolUse, answered]);
  write(join(projects, "c--code-other", "S2.jsonl"), [line({ type: "assistant", effort: "high" }), line({ type: "assistant", effort: 3 }), "{"]);
  write(join(projects, "x", "s3.jsonl"), [line({ type: "assistant", message: [1] })]);
  // test_ledger_session_and_decision_records_with_u2028_are_read_back 的会话文件原样：第一行不是对象，第二行带 U+2028
  write(join(projects, "c--repo", "sid-1.jsonl"), ["7", dumps(py({ type: "assistant", effort: "max", text: `a${ch(0x2028)}b` }), { ensureAscii: false }), ""]);
  write(join(projects, "y", "s4.jsonl"), [line({ type: "assistant", message: { content: "abc", stop_reason: "end_turn" } }), "  "]);
  const sessions = join(MAIN, ".agent", "mailbox", "sessions", "gate-sonnet");
  write(join(sessions, "20261030_p1.jsonl"), [line({ type: "message", message: { role: "assistant", stopReason: "toolUse" } })]);
  write(join(sessions, "20261031_p1.jsonl"), [line({ type: "message", message: { role: "assistant", stopReason: "stop" } })]);
  write(join(sessions, "20261031_p2.jsonl"), [line({ type: "message", message: { role: "assistant", stopReason: "toolUse" } }), `{"type":"mess`]);

  it("session_cut_short 与 claude_session_effort：取哪个文件、半截的判法、读不出的最后一行、不是字典的消息", () => {
    const at = (request: ProbeRequest): ProbeRequest => ({ ...request, home });
    const results = agree([
      at(call("session_cut_short", MAIN, "planner-opus", "claude", "s1")), at(call("session_cut_short", MAIN, "planner-opus", "claude", "S1")),
      at(call("session_cut_short", MAIN, "planner-opus", "claude", "s2")), at(call("session_cut_short", MAIN, "planner-opus", "claude", "s3")),
      at(call("session_cut_short", MAIN, "planner-opus", "claude", "s4")), at(call("session_cut_short", MAIN, "planner-opus", "claude", "none")),
      at(call("session_cut_short", MAIN, "gate-sonnet", "pi", "p1")), at(call("session_cut_short", MAIN, "gate-sonnet", "pi", "p2")),
      at(call("session_cut_short", MAIN, "gate-sonnet", "pi", "p3")),
      at(call("claude_session_effort", "s2")), at(call("claude_session_effort", "s1")), at(call("claude_session_effort", "none")), at(call("claude_session_effort", "sid-1")),
    ]);
    expect(results.map((result) => (result.ok ? JSON.stringify(valueOf(result)) : result.error))).toEqual([
      "false", "false", "true", "AttributeError", "false", "false", "false", "true", "false", JSON.stringify("3"), "null", "null", JSON.stringify("max"),
    ]);
  });

  it("pi_flags_problem：读不出 --help、不认识的参数、都认识", () => {
    const fake = join(ROOT, "fake_pi.py");
    writeFileSync(fake, [
      "import sys",
      "if sys.argv[1] == 'fail':",
      "    sys.exit(1)",
      "print('Usage: pi [options]')",
      "print('  --model <id>      model')",
      "print('  --tools <names>   tools')",
      "print('  --no-mcp --no-skills --thinking <level>')",
      "",
    ].join(LF));
    const python = process.env["THEMIS_PYTHON"] ?? "python";
    const results = agree([
      call("pi_flags_problem", [python, fake, "fail"], ["--model", "x"]), call("pi_flags_problem", [python, fake, "ok"], ["--model", "m", "--tools", "read", "--mode", "--x", "--x"]),
      call("pi_flags_problem", [python, fake, "ok"], ["--model", "m", "-p", "--no-mcp"]),
    ]);
    expect(results.map((result) => valueOf(result) === null)).toEqual([false, false, true]);
  });
});

// --- 五、探针的 home 只在调用期间设 -------------------------------------------------------------------------------

describe("第 ⑤e1b 片：hub.audit 的 home 只在调用期间设、调用完还原", () => {
  it("同一批里先一条带 home、再一条不带：后一条看到的是进程原来的 home（读不到那个会话号）", () => {
    const home = join(ROOT, "audit-home");
    const session = `audit-home-${process.pid}-${Date.now()}`;
    mkdirSync(join(home, ".claude", "projects", "C--x"), { recursive: true });
    writeFileSync(join(home, ".claude", "projects", "C--x", `${session}.jsonl`), JSON.stringify({ type: "assistant", effort: "max" }) + LF);
    const results = agree([{ ...call("claude_session_effort", session), home }, call("claude_session_effort", session)]);
    expect(results.map(valueOf)).toEqual(["max", null]);
  });
});

// --- 六、TS 独有：piSupportedFlags 的缓存 ---------------------------------------------------------------------------

describe("第 ⑤e0 片：piSupportedFlags 缓存进行中的那一次（TS 独有，对等契约看不到）", () => {
  // 假 pi：每起一次往计数文件里记一行，按第二个参数退出
  const fake = join(ROOT, "fake_pi_count.py");
  writeFileSync(fake, ["import sys", "open(sys.argv[1], 'a').write('x' + chr(10))", "print('Usage: pi [options]')", "print('  --model <id>      model')",
    "sys.exit(int(sys.argv[2]))", ""].join(LF));
  const python = process.env["THEMIS_PYTHON"] ?? "python";
  const env = new Map(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
  const starts = (count: string): number => (existsSync(count) ? readFileSync(count, "utf8").split(LF).filter(Boolean).length : 0);
  const restore = (name: string, value: string | undefined): void => {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  };

  it("同一个 pi 命令并发调两次只起一次；非零退出缓存成 null，再调也不重探", async () => {
    const count = join(ROOT, "pi-starts-ok");
    const cmd = [python, fake, count, "0"];
    const [first, second] = await Promise.all([piSupportedFlags(cmd, env), piSupportedFlags(cmd, env)]);
    expect(first?.has("--model")).toBe(true);
    expect(second).toBe(first);
    expect(starts(count)).toBe(1);
    const failing = [python, fake, join(ROOT, "pi-starts-fail"), "1"];
    expect(await piSupportedFlags(failing, env)).toBeNull();
    expect(await piSupportedFlags(failing, env)).toBeNull();
    expect(starts(failing[2] as string)).toBe(1);
  });

  it("探的时候抛了异常（临时目录建不出来）不留缓存：下一次照样重探", async () => {
    const count = join(ROOT, "pi-starts-retry");
    const cmd = [python, fake, count, "0"];
    const [temp, tmp] = [process.env["TEMP"], process.env["TMP"]];
    process.env["TEMP"] = process.env["TMP"] = join(ROOT, "no-such-dir");
    try {
      await expect(piSupportedFlags(cmd, env)).rejects.toThrow();
    } finally {
      restore("TEMP", temp);
      restore("TMP", tmp);
    }
    expect(starts(count), "第一次没起来 pi").toBe(0);
    expect((await piSupportedFlags(cmd, env))?.has("--model")).toBe(true);
    expect(starts(count)).toBe(1);
  });
});
