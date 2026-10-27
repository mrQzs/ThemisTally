// pi_dispatch 的事件流摘要与 summary.md 的契约（迁移第 ④b6 片）：summarize_events、extract_report、review_hints、
// write_summary，以及 shell 命令扫描、歧义与自定解读的提及这几个小函数。语料：
//   - stub_pi 的剧本（tests/stub_pi.py）：写主仓库的三个剧本把 STUB_MAIN_REPO 指到临时目录，hang 与 commit 不跑；
//   - 按种子改坏的变体：删行、重复行、截断、插坏字节、BOM 与只有空白的行、CRLF、换值的类型（数字写成字符串、浮点、
//     布尔、null、NaN、超长整数）、插进构造的 shell 命令与说法；
//   - 主仓库 .agent/runs 下真实 attempt 的事件流（只读；没有时跳过这一条）。
// 每条先由 Python 回答，Node、Bun 逐字一致；写文件的函数另外逐字节比较写出的文件（每套实现之前删掉上一套写的）。
// 另断言每种结局都走到了。不写转义序列，特殊字符用 ch() 拼。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { IMPLS, REPO, type ProbeRequest, type ProbeResult, prng, removeDir, runAgreeing, runBatch, scratchDir } from "./harness.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = ch(10);
const CR = ch(13);
const BS = ch(92);
const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const STUB = join(REPO, "tests", "stub_pi.py");
const ROOT = scratchDir("events");
const MAIN = join(ROOT, "main");
const RUN = join(MAIN, ".agent", "runs", "normalize-query", "attempt-001");
const EXECUTOR = { provider: "step", model: "step-5-preview", thinking: "high" };
const SCENARIOS = [
  "ok", "scope", "error", "outside", "touchmain", "model", "noreport", "nosettle", "startfail", "readplan", "typo", "planner",
  "ambiguous", "conflict", "checkonly", "textcall", "tmpclean", "tempsequence",
];

afterAll(() => removeDir(ROOT));

mkdirSync(join(MAIN, ".agent", "plans"), { recursive: true });
mkdirSync(RUN, { recursive: true });
writeFileSync(join(MAIN, "README.md"), "# main" + LF);
const PLAN_TEXT = ["# TASK: normalize-query", "", "## Goal", "合同里的 ambiguous 状态（对齐任务的领域用语）出现两次：ambiguous。", "",
  "## Stop conditions", "合同前后矛盾时停止；歧义时停止。", ""].join(LF);
writeFileSync(join(RUN, "plan.md"), PLAN_TEXT);
writeFileSync(join(RUN, "instruction.md"), "执行说明：照合同做。" + LF);

// --- 带标签的值（与 src/tagged.ts 相同的编码）------------------------------------------------------

type Tag = { t: string; [key: string]: unknown };
const tagStr = (value: string): Tag => ({ t: "str", v: value });
function tagOf(value: unknown): Tag {
  if (value === null) return { t: "none" };
  if (typeof value === "boolean") return { t: "bool", v: value };
  if (typeof value === "string") return tagStr(value);
  if (typeof value === "number") return { t: "int", hex: (value < 0 ? "-" : "") + Math.abs(value).toString(16) };
  if (Array.isArray(value)) return { t: "list", v: value.map(tagOf) };
  return { t: "dict", v: Object.entries(value as Record<string, unknown>).map(([key, item]) => [tagStr(key), tagOf(item)]) };
}

// --- stub_pi 的剧本 -----------------------------------------------------------------------------

interface Stream {
  readonly name: string;
  readonly work: string;
  readonly events: Buffer;
  readonly stderr: Buffer;
}

/** 在自己的工作副本里跑一个剧本，交回事件流与 stderr 的字节。 */
function stubStream(scenario: string, env: Record<string, string> = {}): Stream {
  const work = join(ROOT, `work-${scenario}-${Object.keys(env).join("-") || "plain"}`);
  mkdirSync(work, { recursive: true });
  const done = spawnSync(
    PYTHON,
    [STUB, "--mode", "json", "--provider", EXECUTOR.provider, "--model", EXECUTOR.model, "--thinking", EXECUTOR.thinking,
      `@${join(RUN, "plan.md")}`, `@${join(RUN, "instruction.md")}`],
    { cwd: work, env: { ...process.env, STUB_SCENARIO: scenario, STUB_MAIN_REPO: MAIN, ...env }, timeout: 60_000 },
  );
  return { name: scenario, work, events: done.stdout, stderr: done.stderr };
}

const STREAMS: Stream[] = [
  ...SCENARIOS.map((scenario) => stubStream(scenario)),
  stubStream("ok", { STUB_PTL: "high" }),
  stubStream("ok", { STUB_PTL: "medium" }),
  stubStream("ok", { STUB_NOCOST: "1" }),
];

/** 事件流写进 attempt 目录（events.jsonl 与 stderr.log 换成这一份），交回 summarize 的请求。 */
function summarizeRequest(name: string, work: string, events: Uint8Array, stderr: Uint8Array, options: Record<string, unknown> = {}): ProbeRequest {
  const dir = join(ROOT, "streams", name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "events.jsonl"), events);
  writeFileSync(join(dir, "stderr.log"), stderr);
  return {
    op: "events.call",
    fn: "summarize",
    events: join(dir, "events.jsonl"),
    work_dir: work,
    executor: tagOf(EXECUTOR),
    stderr: join(dir, "stderr.log"),
    expects_settled: true,
    allowed_outside: [RUN],
    plan_text: PLAN_TEXT,
    protected_roots: [MAIN],
    ...options,
  };
}

// --- 构造的 shell 命令与说法 ---------------------------------------------------------------------

/** 一个路径在命令里的几种写法：原样、正斜杠、Git Bash 的 /c/…。 */
function writings(path: string): string[] {
  const slash = path.split(BS).join("/");
  const forms = [path, slash];
  if (/^[A-Za-z]:[/]/u.test(slash)) forms.push(`/${slash.slice(0, 1).toLowerCase()}${slash.slice(2)}`);
  return forms;
}

function pick<T>(next: () => number, items: readonly T[]): T {
  return items[Math.floor(next() * items.length)] as T;
}

const COMMAND_PIECES = [
  "cat ", "ls ", "cd ", "python -m pytest ", "pytest -q", "npm test", "tsc", "| tail -5", "| grep x", "|| true", "; exit 0", "; true",
  "set -o pipefail; ", "${PIPESTATUS[0]}", "rm -rf ", "rm -r -f ", "rm -f ", "rm --recursive ", "Remove-Item -Recurse ", "__pycache__",
  "src/__pycache__/", ".pytest_cache", "'.mypy_cache'", '"tests/.ruff_cache/"', "../__pycache__", "mktemp -d", "T=$(mktemp -d)", 'rm -rf "$T"',
  "tempfile.mkdtemp()", "from tempfile import mkdtemp", "/tmp/x", "/var/tmp/y", "/private/tmp", "$TMPDIR/a", "${TEMP}", "%TEMP%",
  "$env:TEMP", "os.environ['TMP']", "AppData/Local/Temp/z", "C:/Windows/Temp", "New-TemporaryFile", "GetTempFileName(", "/dev/null",
  "/dev/fd/3", "/usr/bin/env", "/c/Windows", "C:/Program Files", "~/x", "~", "/x/", "s/a/b/", "git push", "git stash list", "git stash",
  "git tag -l", "git checkout -- .", "git branch -D x", "curl https://x", "npm install", "pip install x", "uv add y", "go get z", "sudo x",
  "chmod +x f", "ssh host", "env", "printenv;", "Get-ChildItem env:", ".ssh/id_rsa", "auth.json", "<worktree>/x", " ", " ", " ", LF, LF,
  CR, ch(0x2028), ch(0x85), ch(0x0b), '"', "'", "`", ";", "&&", "|", "(", ")", "<", ">", ",", "=", BS, "$", "x", "y",
  "中文", ch(0x1f600), "İ", "ſ", "K",
];

function command(next: () => number, paths: readonly string[]): string {
  const forms = paths.flatMap(writings);
  let out = "";
  const count = 1 + Math.floor(next() * 12);
  for (let index = 0; index < count; index += 1) {
    const roll = next();
    if (roll < 0.3) out += pick(next, forms) + pick(next, ["", "/", BS, "/src/x.py", "-other", "/../x", "/$X", "/a b", BS + "a", "/../../y"]);
    else out += pick(next, COMMAND_PIECES);
  }
  return out;
}

const SAYING_PIECES = [
  "ambiguous", "ambiguity", "AMBİGUOUS", "contradiction", "contradicts", "inconsistent", "inconsistencies", "矛盾", "歧义", "含义不明",
  "前后不一致", "说法不一", "no ", "not ", "n't ", "without ", "un", "non-", "cannot be done without ", "not un", "并非没有", "没有", "不", "无",
  "任何", "obvious ", "found ", ": none found.", "：无。", "：未发现。", LF + "未发现。" + LF, ": no conflicts.", ": no. 4 requires A",
  " contract", " plan", " spec", " step 4", " DoD", "合同", "规范", "验收", " the ", " is ", ".", "，", "。", LF, LF + LF, " ", " ", " ",
  "judgment call", "I'll note this as an interpretation", "we will treat it as my interpretation", "I interpret", "my interpretation",
  "interpreting the spec", "I'll go with", "we'll assume", "我理解为", "按我的理解", "我把这里理解为", "自行裁定", "就按旧格式处理",
  ch(0x1f600), "x".repeat(120), "## 合同矛盾" + LF,
];

function saying(next: () => number): string {
  let out = "";
  const count = 1 + Math.floor(next() * 14);
  for (let index = 0; index < count; index += 1) out += pick(next, SAYING_PIECES);
  return out;
}

// --- 改坏事件流 ---------------------------------------------------------------------------------

const RAW_TOKENS = ["NaN", "Infinity", "-Infinity", "123456789012345678901234567890", "1e400", "-0.0", "1.5", "0"];

/** 把 JSON 里随便一个叶子换成别的类型；raw 标记的值在写出时换成 Python 认、JSON.stringify 写不出的原文。 */
function mutateValue(next: () => number, value: unknown, depth = 0): unknown {
  if (value !== null && typeof value === "object" && depth < 6) {
    if (Array.isArray(value)) {
      if (!value.length) return value;
      const copy = [...value];
      const index = Math.floor(next() * copy.length);
      copy[index] = mutateValue(next, copy[index], depth + 1);
      return copy;
    }
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return value;
    const index = Math.floor(next() * entries.length);
    const [key, item] = entries[index] as [string, unknown];
    if (next() < 0.1) return Object.fromEntries(entries.filter((_, position) => position !== index));
    return { ...(value as object), [key]: mutateValue(next, item, depth + 1) };
  }
  return pick(next, [
    null, true, false, 0, 7, -3, "x", "", "None", [], {}, [1, "a"], { a: 1 }, "@@RAW@@", "@@RAW@@",
    typeof value === "number" ? String(value) : 5, typeof value === "string" ? `${value}${value}` : "stop",
  ]);
}

function serialize(next: () => number, value: unknown): string {
  return JSON.stringify(value).split('"@@RAW@@"').map((part, index) => (index ? pick(next, RAW_TOKENS) : "") + part).join("");
}

function bashEvent(next: () => number, id: string, text: string): string[] {
  const start = { type: "tool_execution_start", toolCallId: pick(next, [id, id, null, 5, "None"]), toolName: pick(next, ["bash", "bash", "powershell", "read"]), args: { command: text, path: pick(next, ["", "src/x.py", RUN, join(MAIN, "README.md"), "~/y", "../z", "C:x"]) } };
  const end = { type: "tool_execution_end", toolCallId: pick(next, [id, id, "None"]), isError: pick(next, [true, false, "yes", 0]) };
  return [JSON.stringify(start), JSON.stringify(end)];
}

function sayingEvent(next: () => number): string {
  const content = next() < 0.3
    ? saying(next)
    : [{ type: pick(next, ["text", "thinking", "toolCall"]), text: saying(next), thinking: saying(next) }, { type: "text", text: saying(next) }];
  return JSON.stringify({ type: "message_end", message: { role: "assistant", content, provider: "step", model: "step-5-preview", stopReason: "stop", usage: { totalTokens: 3, cost: { total: pick(next, [0, 0.5, -1, "1"]) } } } });
}

/** 一份事件流的变体：先按行做几次结构改动，再按字节做一次。 */
function variant(next: () => number, events: Buffer, stream: Stream): Buffer {
  let lines = events.toString("utf8").split(LF);
  const rounds = 1 + Math.floor(next() * 3);
  for (let round = 0; round < rounds; round += 1) {
    const at = Math.floor(next() * lines.length);
    const roll = next();
    if (roll < 0.12) lines.splice(at, 1);
    else if (roll < 0.2) lines.splice(at, 0, lines[at] ?? "");
    else if (roll < 0.45) {
      try {
        lines[at] = serialize(next, mutateValue(next, JSON.parse(lines[at] ?? "")));
      } catch {
        lines[at] = "{";
      }
    } else if (roll < 0.7) lines.splice(at, 0, ...bashEvent(next, `b${round}`, command(next, [stream.work, MAIN, RUN])));
    else if (roll < 0.85) lines.splice(at, 0, sayingEvent(next));
    else lines.splice(at, 0, pick(next, ["", " ", ch(0x0b), ch(0xa0), "[]", "null", "{}", ch(0xfeff) + "{}", '{"type": "agent_end", "willRetry": true}', '{"type": "agent_settled"}', '{"type": "auto_retry_end", "success": false, "finalError": "sk-' + "a".repeat(30) + '"}', '{"type": "compaction_end", "result": {"usage": {"input": 5}}}', '{"type": "entry_appended", "entry": {"type": "usage", "usage": {"output": 1.5, "totalTokens": "3"}}}']));
  }
  if (next() < 0.15) lines = lines.map((line) => line + CR);
  let bytes = Buffer.from(lines.join(LF), "utf8");
  const roll = next();
  if (roll < 0.15 && bytes.length) bytes = bytes.subarray(0, Math.floor(next() * bytes.length));
  else if (roll < 0.25) bytes = Buffer.concat([bytes, Buffer.from([0xff, 0xfe, 0x0a, 0xc3, 0x28, 0x0a])]);
  return bytes;
}

// --- 比较 -----------------------------------------------------------------------------------------

/** 两份结果的不同之处：摘要只列出不同的键与两边的值，其余截一段原文。 */
function difference(python: ProbeResult | undefined, other: ProbeResult | undefined): Record<string, unknown> {
  const a = python?.["summary"] as Summary | undefined;
  const b = other?.["summary"] as Summary | undefined;
  if (!a || !b) return { python: JSON.stringify(python).slice(0, 600), other: JSON.stringify(other).slice(0, 600) };
  const keyed = (summary: Summary): Map<unknown, string> => new Map(summary.v.map(([key, value]) => [key["v"], JSON.stringify(value)]));
  const [left, right] = [keyed(a), keyed(b)];
  const keys = [...left.keys()].filter((key) => left.get(key) !== right.get(key));
  return Object.fromEntries(keys.map((key) => [String(key), { python: left.get(key)?.slice(0, 700), other: right.get(key)?.slice(0, 700) }]));
}

/** 分批交给探针，汇总 Python 的结果与不一致（探针进程有 60 秒的时限）。 */
function agree(requests: readonly ProbeRequest[], size = 40): ProbeResult[] {
  const python: ProbeResult[] = [];
  const samples: unknown[] = [];
  let mismatches = 0;
  for (let start = 0; start < requests.length; start += size) {
    const batch = runAgreeing(requests.slice(start, start + size));
    python.push(...batch.python);
    mismatches += batch.mismatches.length;
    samples.push(...batch.mismatches.slice(0, 1).map((item) => ({ impl: item.impl, index: start + item.index, ...difference(item.python, item.other) })));
  }
  expect(samples.slice(0, 2), `共 ${mismatches} 条不一致`).toEqual([]);
  return python;
}

/** 写文件的请求：每套实现之前删掉 outputs，跑完读回字节；结果与文件都以 Python 为准。 */
/**
 * sorted() 遇到比不了的两种类型时，报错里两个类型名的先后取决于集合的迭代次序：字符串的散列随进程变，Python 自己每次运行
 * 都可能不同。只对这一种报错把两个类型名排好再比。
 */
const UNORDERABLE = /^'<' not supported between instances of '([A-Za-z]+)' and '([A-Za-z]+)'$/u;
function settled(result: ProbeResult | undefined): string {
  const message = typeof result?.["message"] === "string" ? (result["message"] as string) : "";
  const pair = UNORDERABLE.exec(message);
  if (!pair) return JSON.stringify(result);
  return JSON.stringify({ ...result, message: [pair[1], pair[2]].sort().join(" ") });
}

function agreeOnFiles(requests: readonly ProbeRequest[], outputs: (index: number) => readonly string[]): ProbeResult[] {
  const seen = IMPLS.map((impl) => {
    requests.forEach((_, index) => outputs(index).forEach((file) => rmSync(file, { force: true })));
    const results: ProbeResult[] = [];
    for (let start = 0; start < requests.length; start += 40) results.push(...runBatch(impl, requests.slice(start, start + 40)));
    const files = requests.map((_, index) => outputs(index).map((file) => (existsSync(file) ? readFileSync(file).toString("base64") : null)));
    return { impl: impl.name, results, files };
  });
  const [python, ...others] = seen as [(typeof seen)[0], ...typeof seen];
  for (const other of others) {
    const bad = requests.map((_, index) => index).filter((index) =>
      settled(other.results[index]) !== settled(python.results[index]) || JSON.stringify(other.files[index]) !== JSON.stringify(python.files[index]));
    expect(bad.slice(0, 3).map((index) => ({ impl: other.impl, index, python: JSON.stringify(python.results[index]).slice(0, 400), other: JSON.stringify(other.results[index]).slice(0, 400) })), `${other.impl} 共 ${bad.length} 条不一致`).toEqual([]);
  }
  return python.results;
}

type Summary = { t: string; v: [Tag, Tag][] };
function field(result: ProbeResult, key: string): Tag | undefined {
  const summary = result["summary"] as Summary | undefined;
  return summary?.v.find(([name]) => name["v"] === key)?.[1];
}
const nonEmpty = (tag: Tag | undefined): boolean => Array.isArray(tag?.["v"]) && (tag?.["v"] as unknown[]).length > 0;
const truthy = (tag: Tag | undefined): boolean => tag?.["v"] === true;

describe("生成的正则表", () => {
  it("event-patterns.ts 与 pi_dispatch 的正则一致（生成脚本 --check）", () => {
    const done = spawnSync(PYTHON, [join(REPO, "ts", "packages", "dispatcher", "tools", "gen_event_patterns.py"), "--check"], {
      cwd: REPO, encoding: "utf8", env: { ...process.env, PYTHONUTF8: "1" }, timeout: 60_000,
    });
    expect(done.status, `${done.stdout}${done.stderr}`).toBe(0);
  });
});

describe("summarize_events", () => {
  it("stub_pi 的剧本：三种 expects_settled、几种要求的执行模型", () => {
    const requests = STREAMS.flatMap((stream, index) => [
      ...[true, false, null].map((settled) => summarizeRequest(`s${index}-${String(settled)}`, stream.work, stream.events, stream.stderr, { expects_settled: settled })),
      summarizeRequest(`s${index}-low`, stream.work, stream.events, stream.stderr, { executor: tagOf({ ...EXECUTOR, thinking: "medium" }) }),
      summarizeRequest(`s${index}-none`, stream.work, stream.events, stream.stderr, { executor: tagOf({ provider: 1, model: null }), stderr: null, expects_settled: false }),
    ]);
    // stderr 的几种警告（带 ANSI 颜色、CRLF、坏字节）：stub 自己的 stderr 里没有
    const noisy = Buffer.concat([Buffer.from(`${ch(0x1b)}[33mWarning: Using custom model id x${ch(0x1b)}[0m${CR}${LF}Invalid thinking ${ch(0x1b)}[1mlevel${CR}Unknown option: --zz${LF}`, "utf8"), Buffer.from([0xff, 0xfe]), Buffer.from(`Extension error${LF}`, "utf8")]);
    requests.push(summarizeRequest("noisy", STREAMS[0]?.work ?? ROOT, STREAMS[0]?.events ?? Buffer.alloc(0), noisy));
    const python = agree(requests);
    expect(python.every((result) => result.ok)).toBe(true);
    expect(python.some((result) => truthy(field(result, "ok")))).toBe(true);
    expect(python.some((result) => !truthy(field(result, "ok")))).toBe(true);
    for (const key of ["suspicious_commands", "temp_path_uses", "cache_dir_cleanups", "outside_worktree_paths", "own_run_paths", "ambiguity_mentions", "temp_dirs_without_cleanup", "provider_thinking_levels", "stderr_flags"]) {
      expect(python.some((result) => nonEmpty(field(result, key))), key).toBe(true);
    }
  });

  it("按种子改坏的变体：删行、重复、截断、坏字节、换类型、插命令与说法", () => {
    const next = prng(4206);
    const requests: ProbeRequest[] = [];
    for (let round = 0; round < 12; round += 1) {
      STREAMS.forEach((stream, index) => {
        requests.push(summarizeRequest(`v${round}-${index}`, stream.work, variant(next, stream.events, stream), stream.stderr, { expects_settled: pick(next, [true, false, null]) }));
      });
    }
    const python = agree(requests, 30);
    expect(python.some((result) => !result.ok)).toBe(true); // 有的变体让 Python 崩溃（例如 totalTokens 写成字符串）
    for (const key of ["parse_error_lines", "auto_retries", "interpretation_mentions", "masked_exit_commands"]) {
      expect(python.some((result) => nonEmpty(field(result, key))), key).toBe(true);
    }
    expect(python.some((result) => truthy(field(result, "truncated")))).toBe(true);
  });

  it("手写的事件流：同一行重复的临时路径、usage 里的布尔、重复的工作副本外路径、float 加超大 int、行尾多个回车", () => {
    const work = STREAMS[0]?.work ?? ROOT;
    const bash = (id: string, text: string): string[] => [
      JSON.stringify({ type: "tool_execution_start", toolCallId: id, toolName: "bash", args: { command: text } }),
      JSON.stringify({ type: "tool_execution_end", toolCallId: id, isError: false }),
    ];
    const usage = (value: string): string => `{"type": "message_end", "message": {"role": "assistant", "content": "x", "usage": ${value}}}`;
    const streams: [string, string[]][] = [
      ["temp-twice", bash("t1", "cat /tmp/a; cat /tmp/a")],
      ["bool-usage", [usage('{"input": true, "output": false, "totalTokens": true, "cost": {"total": true}}'), usage('{"input": 2, "cacheRead": true}')]],
      ["outside-twice", [...bash("o1", "type C:/Windows/win.ini"), ...bash("o2", "type C:/Windows/win.ini"), ...bash("o3", "more C:/Windows/win.ini")]],
      ["float-then-huge", [usage('{"input": 0.5}'), usage(`{"input": 1${"0".repeat(400)}}`)]],
      ["huge-then-float", [usage(`{"input": 1${"0".repeat(400)}}`), usage('{"output": 2, "input": 3}')]],
    ];
    const requests = streams.flatMap(([name, lines]) => [
      summarizeRequest(`hand-${name}`, work, Buffer.from(lines.join(LF) + LF, "utf8"), Buffer.alloc(0)),
      summarizeRequest(`hand-${name}-crcr`, work, Buffer.from(lines.join(CR + CR + LF) + CR + CR + LF, "utf8"), Buffer.alloc(0)),
    ]);
    const python = agree(requests);
    expect(python.some((result) => !result.ok && result.error === "OverflowError")).toBe(true);
  });

  it("主仓库里真实 attempt 的事件流（只读）", () => {
    const runs = mainRuns();
    if (!runs.length) return;
    const requests = runs.map((dir, index) => {
      const meta = readJson(join(dir, "meta.json"));
      const executor = readJson(join(dir, "executor.json"));
      return {
        op: "events.call",
        fn: "summarize",
        events: join(dir, "events.jsonl"),
        work_dir: typeof meta["worktree"] === "string" ? meta["worktree"] : dir,
        executor: tagOf(Object.fromEntries(Object.entries(executor).filter(([, value]) => typeof value === "string"))),
        stderr: join(dir, "stderr.log"),
        expects_settled: index % 2 === 0,
        allowed_outside: [dir],
        plan_text: existsSync(join(dir, "plan.md")) ? readFileSync(join(dir, "plan.md"), "utf8") : "",
        protected_roots: [join(dir, "..", "..", "..", "..")],
      };
    });
    const python = agree(requests, 1);
    expect(python.every((result) => result.ok)).toBe(true);
  });
});

/** 主仓库（git 的公共目录的上一级）.agent/runs 下有事件流的 attempt：最小的 6 个与最大的 2 个。 */
function mainRuns(): string[] {
  const common = spawnSync("git", ["rev-parse", "--path-format=absolute", "--git-common-dir"], { cwd: REPO, encoding: "utf8" }).stdout.trim();
  const runs = join(common, "..", ".agent", "runs");
  if (!common || !existsSync(runs)) return [];
  const found: [string, number][] = [];
  for (const task of readdirSync(runs)) {
    if (!statSync(join(runs, task)).isDirectory()) continue;
    for (const attempt of readdirSync(join(runs, task)).filter((name) => name.startsWith("attempt-"))) {
      const events = join(runs, task, attempt, "events.jsonl");
      if (existsSync(events) && statSync(events).size > 0) found.push([join(runs, task, attempt), statSync(events).size]);
    }
  }
  found.sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1));
  return [...found.slice(0, 6), ...found.slice(-2)].map(([dir]) => dir);
}

function readJson(file: string): Record<string, unknown> {
  try {
    const value = JSON.parse(readFileSync(file, "utf8")) as unknown;
    return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

describe("shell 命令扫描与提及", () => {
  it("构造的命令：屏蔽、主仓库路径、工作副本外路径、缓存清理、掩盖退出码、没清理的临时目录", () => {
    const next = prng(77);
    const work = STREAMS[0]?.work ?? ROOT;
    const own = writings(work).concat(writings(RUN));
    const protectedForms = writings(MAIN);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 600; index += 1) {
      requests.push({ op: "events.call", fn: "scan", command: command(next, [work, MAIN, RUN, join(ROOT, "other")]), own, protected: protectedForms });
    }
    // 只删缓存目录的写法（随机拼很难拼全），以及差一点就算的几种
    for (const text of [
      "rm -rf src/__pycache__ tests/.pytest_cache && git status --porcelain", "rm -r -f 'a/b/.mypy_cache/'", "rm -rf ./__pycache__; rm -f .ruff_cache",
      "rm -rf ../__pycache__", "rm -rf a/../__pycache__", "rm -rf __pycache__ /tmp", "rm -rf", 'rm -rf "__pycache__' + "'", "rm -rf .hypothesis//",
      "Remove-Item -Recurse __pycache__; rm -rf __pycache__", "rm -rf $X/__pycache__", "rm -rf -- __pycache__", "rm -rf x/__pycache__/y",
      'type a,"C:/Windows/win.ini"', "echo b,'C:/Program Files/x' c", 'x="C:/Windows/win.ini"', 'y"C:/Windows/win.ini"',
    ]) {
      requests.push({ op: "events.call", fn: "scan", command: text, own, protected: protectedForms });
    }
    const python = agree(requests, 150);
    for (const key of ["protected", "outside"]) expect(python.some((result) => (result[key] as unknown[]).length > 0), key).toBe(true);
    for (const key of ["cache", "exit", "leak"]) expect(python.some((result) => Boolean(result[key])), key).toBe(true);
    expect(python.some((result) => result["masked"] !== requests[python.indexOf(result)]?.["command"])).toBe(true);
  });

  it("_match_excerpt 的窗口与省略号、_path_forms", () => {
    const next = prng(9);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 200; index += 1) {
      const text = command(next, [MAIN]) + "y".repeat(Math.floor(next() * 400)) + saying(next);
      const length = Array.from(text).length;
      const start = Math.floor(next() * length);
      requests.push({ op: "events.call", fn: "excerpt", text, start, end: Math.min(length, start + Math.floor(next() * 30)) });
    }
    // 等长的写法按码点排（第 124 轮）：路径里放补充平面字符与 U+E000 以上的字符，UTF-16 码元的次序在这里会反过来
    requests.push({ op: "events.call", fn: "path_forms", paths: [MAIN, RUN, "C:" + BS + "x", "ab", REPO, join(ROOT, `a${ch(0x1f600)}b`), join(ROOT, `a${ch(0xe000)}b`), "C:" + BS + ch(0xff21) + BS + "y"] });
    const python = agree(requests);
    expect(python.every((result) => result.ok)).toBe(true);
  });

  it("歧义与自定解读的提及、合同的领域用语", () => {
    const next = prng(31);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 500; index += 1) {
      const blocks = Array.from({ length: 1 + Math.floor(next() * 3) }, () => ({ type: pick(next, ["text", "thinking", "toolCall", 5]), text: next() < 0.1 ? pick(next, [5, null, ["x"]]) : saying(next), thinking: saying(next) }));
      const message = { role: "assistant", content: next() < 0.25 ? saying(next) : pick(next, [blocks, blocks, blocks, null, 7]) };
      requests.push({ op: "events.call", fn: "mentions", message: tagOf(message), line: index + 1, skip: next() < 0.2 ? ["ambiguous", "矛盾"] : [] });
      requests.push({ op: "events.call", fn: "message_text", message: tagOf(message) });
      requests.push({ op: "events.call", fn: "domain_words", text: [saying(next), "## Stop conditions", saying(next), "## Goal", saying(next) + saying(next)].join(LF) });
    }
    // 卡在窗口边界上的两句：否定词在关键词之前 25–30 个字符（窗口是 24）；否定答案之后 70 个字符处才有别的字（窗口是 80）
    for (const content of ["the contract: no real obvious actual major ambiguity here", `contract inconsistencies: none${" ".repeat(60)}xyz`]) {
      requests.push({ op: "events.call", fn: "mentions", message: tagOf({ role: "assistant", content }), line: 1, skip: [] });
    }
    const python = agree(requests, 300);
    expect(python.some((result) => nonEmpty(result["ambiguity"] as Tag))).toBe(true);
    expect(python.some((result) => nonEmpty(result["interpretation"] as Tag))).toBe(true);
    expect(python.some((result) => !result.ok)).toBe(true); // message_text：text 不是字符串时 join 抛 TypeError
  });
});

describe("extract_report 与 review_hints", () => {
  it("最终消息里的 ```json 块：缺失、多块、空白里的换行、坏 JSON、孤立代理项", () => {
    const next = prng(55);
    const pieces = ["```json", "```", "```json ", LF, LF, " ", ch(0x2028), ch(0x0b), "{", "}", '"executor_status": "completed"', ",", '"contract_conflicts": [1, 2]',
      '"interpretations": {}', '"interpretations": []', '"unresolved_questions": ["q"]', "[1,", "NaN", "报告", ch(0xd800), "x", '{"a": 1}', '"' + "9".repeat(5000) + '"'];
    const requests: ProbeRequest[] = [];
    const dirs: string[] = [];
    for (let index = 0; index < 160; index += 1) {
      let text = "";
      for (let count = Math.floor(next() * 16); count > 0; count -= 1) text += pick(next, pieces);
      if (index % 7 === 0) text = ["## 执行报告", "", "```json", JSON.stringify({ executor_status: "completed", interpretations: index % 2 ? [] : null }), "```", ""].join(LF);
      // 贪婪的空白里有两个换行，中间夹着 JSON 不认的空白（0x0b）：从最后一个换行起算的块才解得开
      if (index === 1) text = `x ${"```"}json${LF}${ch(0x0b)}${LF}{"executor_status": "done"}${LF}${"```"}`;
      const dir = join(ROOT, "reports", String(index));
      mkdirSync(dir, { recursive: true });
      dirs.push(dir);
      requests.push({ op: "events.call", fn: "extract_report", text, run_dir: dir });
    }
    const python = agreeOnFiles(requests, (index) => ["executor-report.md", "executor-report.json"].map((name) => join(dirs[index] as string, name)));
    const statuses = new Set(python.map((result) => (result.ok ? ((result["value"] as Summary).v.find(([key]) => key["v"] === "status")?.[1]["v"] as string) : result.error)));
    for (const status of ["missing", "no_json", "json_invalid", "json_ok", "UnicodeEncodeError"]) expect(statuses.has(status), status).toBe(true);
  });

  it("补丁里的跳过标记与断言行：坏字节、各种行界、20 MiB 截断", () => {
    const next = prng(12);
    const lines = ["+", "-", "+++ b/x", "--- a/x", " ", "+  expect(x).toBe(1)", "-assert y", "+should", "+it.skip(", "+  xit(", "+@pytest.mark.skip", "+#[ignore]",
      "+@Disabled", "-    self.assertEqual(a, b)", "+t.Skip()", "+.only (", "+中文 assert_called", "-x"];
    const breaks = [LF, LF, CR + LF, CR, ch(0x0b), ch(0x1c), ch(0x85), ch(0x2028)];
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 80; index += 1) {
      const parts: Buffer[] = [];
      for (let count = Math.floor(next() * 40); count > 0; count -= 1) {
        parts.push(Buffer.from(pick(next, lines) + pick(next, breaks), "utf8"));
        if (next() < 0.1) parts.push(Buffer.from([pick(next, [0xff, 0xc3, 0xe2, 0x80, 0xed])]));
      }
      const file = join(ROOT, "patches", `${index}.patch`);
      mkdirSync(join(ROOT, "patches"), { recursive: true });
      writeFileSync(file, Buffer.concat(parts));
      requests.push({ op: "events.call", fn: "review_hints", patch: file });
    }
    // 恰好 20 MiB（也算截断）与多一个字节、截在多字节字符中间
    const limit = 20 * 1024 * 1024;
    for (const extra of [0, 1, -1]) {
      const file = join(ROOT, "patches", `big${extra}.patch`);
      const body = Buffer.alloc(limit + extra, 0x41);
      Buffer.from("+expect(" + LF + "+.skip(" + LF, "utf8").copy(body, 0);
      Buffer.from([0xe4, 0xb8, 0xad]).copy(body, limit - 2);
      writeFileSync(file, body.subarray(0, limit + extra));
      requests.push({ op: "events.call", fn: "review_hints", patch: file });
    }
    requests.push({ op: "events.call", fn: "review_hints", patch: join(ROOT, "patches", "missing.patch") });
    const python = agree(requests, 30);
    expect(python.some((result) => !result.ok)).toBe(true);
  });
});

// --- write_summary --------------------------------------------------------------------------------

/** 一个 attempt 目录：证据文件按种子取典型值，少数字段换成别的类型（Python 在那里崩溃，两边要报同一种异常）。 */
function attemptDir(next: () => number, index: number): string {
  const dir = join(MAIN, ".agent", "runs", "summaries", `attempt-${String(index).padStart(3, "0")}`);
  mkdirSync(dir, { recursive: true });
  const odd = (value: unknown): unknown => (next() < 0.025 ? pick(next, [null, 3, "s", [1], { a: 1 }, 1.5, true]) : value);
  const write = (name: string, value: unknown): void => {
    if (next() < 0.04) return; // 文件不在：read_json_or 给缺省值
    writeFileSync(join(dir, name), next() < 0.02 ? "{" : serialize(next, value));
  };
  const mention = (): unknown => odd({ line: odd(3), excerpt: odd(saying(next)), kind: "text" });
  const role = next() < 0.4;
  write("contract.json", { executor: role ? { role: "execution" } : next() < 0.5 ? EXECUTOR : { provider: "step" } });
  write("executor.json", odd(next() < 0.7 ? { ...EXECUTOR, tools: odd(["read", "bash"]) } : null));
  write("meta.json", {
    task_id: odd("normalize-query"), plan_version: odd(2), attempt_id: odd("attempt-001"), base_sha: odd("a".repeat(40)), platform: "Windows", python: "3.12.10",
    repository: odd(MAIN), executor_binding: odd(role ? { role: "execution", profile: "p", runtime: "pi", active_preset: odd(null), config_sha256: odd("b".repeat(64)), record_path: "r", provider: "step", model: "m", thinking: "high" } : null),
    executor_binding_note: odd(next() < 0.5 ? { role: "execution", profile: "q", binding: odd({ provider: "x", model: "y", thinking: "low" }) } : null),
  });
  write("state.json", { state: pick(next, ["NEEDS_REVIEW", "FAILED", "COLLECTING"]) });
  write("run.json", odd({ exit_code: odd(0), wall_seconds: odd(12.5), timeout_seconds: 3600, timed_out: odd(false), interrupted: false, stray_processes: odd([]) }));
  const tempUses = Array.from({ length: Math.floor(next() * 3) }, () => odd({ event_line: 4, match: odd("mktemp `x`"), match_line: 1 }));
  write("events-summary.json", odd({
    problems: odd(next() < 0.5 ? ["事件流为空", "x"] : []), actual_models: odd([odd({ provider: "step", model: odd("m") })]), provider_thinking_levels: odd(next() < 0.5 ? ["high"] : []),
    model_match: odd(true), complete: odd(next() < 0.5), terminal_event: "agent_settled", lines: odd(12), final_stop_reason: "stop", tool_errors: 0, auto_retries: odd([{ attempt: 1 }]),
    compactions: 0, usage: odd({ input: odd(10), output: 2.5, cacheRead: 0, cacheWrite: 0 }), cost: odd({ total: odd(next() < 0.5 ? null : 0.123456), status: "estimated" }),
    suspicious_commands: odd(Array.from({ length: Math.floor(next() * 3) }, () => odd({ label: "git 写操作", match: odd(next() < 0.5 ? "git push `x`" : ""), match_line: 1, command_lines: 2, command: odd("git push"), event_line: 9 }))),
    temp_path_uses: odd(tempUses), temp_path_use_count: odd(next() < 0.5 ? tempUses.length + 3 : tempUses.length),
    cache_dir_cleanups: odd(next() < 0.3 ? [odd({ event_line: 3, command: odd("rm -rf __pycache__") })] : []),
    outside_worktree_paths: odd(Array.from({ length: Math.floor(next() * 3) }, () => odd({ tool: odd("bash"), path: odd("/usr/`x`"), main_repo: odd(next() < 0.5), failed: pick(next, [true, false, null, 1]), exists: pick(next, [false, true, null]), event_line: odd(7), occurrences: odd(pick(next, [1, 3, null, 2.5])) }))),
    own_run_paths: odd(Array.from({ length: Math.floor(next() * 9) }, () => odd({ tool: "read", path: odd(pick(next, ["plan.md", "b", "a", "plan.md", "c", "d", "e", "f"])) }))),
    stderr_flags: odd(next() < 0.3 ? ["custom_model_id"] : []), masked_exit_commands: odd(next() < 0.5 ? [odd({ event_line: 2, match: odd("| tail"), check: odd(next() < 0.5) })] : []),
    temp_dirs_without_cleanup: odd(next() < 0.3 ? [odd({ event_line: 5, match: odd("mktemp") })] : []),
    interpretation_mention_count: odd(next() < 0.4 ? 2 : 0), interpretation_mentions: odd(next() < 0.8 ? [mention()] : []),
    ambiguity_mention_count: odd(next() < 0.4 ? 1 : 0), ambiguity_mentions: odd(next() < 0.8 ? [mention()] : []),
  }));
  write("report-status.json", odd({ status: "json_ok", executor_status: odd("completed"), contract_conflicts: odd(pick(next, [0, 0, 2])), unresolved_questions: odd(0), interpretations: odd(pick(next, [0, 1])), interpretations_missing: odd(next() < 0.2) }));
  write("candidate.json", odd({ tree: odd("c".repeat(40)), patch_roundtrip_verified: odd(true) }));
  write("scope.json", odd({
    counts: odd({ A: 1, M: 2, D: 0, T: 0 }), files: odd(next() < 0.6 ? [odd({ status: "M", path: odd("src/x.py"), scope: "allowed" })] : []),
    violations: odd(next() < 0.3 ? [odd({ path: "README.md", kind: "out_of_scope", detail: "x" })] : []), warnings: odd(next() < 0.3 ? [odd({ path: ".env", kind: "sensitive_file", detail: "y" })] : []),
  }));
  write("observations.json", odd({
    new_ignored_paths: odd(next() < 0.3 ? ["dist/"] : []), unindexable_skipped: odd(next() < 0.2 ? ["nul"] : []), main_repo_changed: odd(next() < 0.3),
    main_repo_changes: odd(next() < 0.6 ? { head_changed: odd(next() < 0.4), head_before: odd(pick(next, ["d".repeat(40), null, ""])), head_after: odd("e".repeat(40)), other_paths: odd(next() < 0.4 ? ["a", "b"] : []), planner_paths: odd(next() < 0.4 ? [".agent/plans/x.md"] : []), diff_error: odd(next() < 0.2 ? "git 出错" : null) } : null),
    review_hints: odd({ skip_markers_added: odd(next() < 0.3 ? ["it.skip(`a`)"] : []), assertion_lines_removed: odd(pick(next, [0, 2])), assertion_lines_added: 1 }),
  }));
  if (next() < 0.5) {
    const answer = (): unknown => odd(pick(next, [
      { type: "noul", noul: odd(pick(next, [0.9, 0.2, "0.75", 1])) },
      { type: "score", score: odd(pick(next, [2.5, 0.5])), levels: odd(pick(next, [5, "3", 2.7])), confidence: 0.8 },
      { type: "choice", choice: "a", confidence: odd(0.6) },
    ]));
    const record = {
      point: "report-screen", mode: pick(next, ["on", "shadow"]), model: "jev", status: pick(next, ["answered", "answered", "no_opinion"]), reason: pick(next, ["timeout", "battery_drift"]),
      detail: odd(pick(next, ["", "x"])), battery_version: "1.0.0", battery_sha256: odd(pick(next, ["f".repeat(64), null])), latency_ms: 120, usage: odd({ input_tokens: 33 }),
      answers: odd({ misleading: answer(), severity: answer(), unknown_name: answer() }),
    };
    writeFileSync(join(dir, "decisions.jsonl"), [JSON.stringify({ point: "run-health" }), serialize(next, record), "{"].join(LF) + LF);
  }
  return dir;
}

describe("write_summary", () => {
  it("证据文件的各种组合与类型错误：summary.md 逐字节一致，崩溃时异常一致", () => {
    const next = prng(2026);
    const dirs = Array.from({ length: 220 }, (_, index) => attemptDir(next, index));
    const outside = join(ROOT, "outside-attempt");
    mkdirSync(outside, { recursive: true });
    dirs.push(outside); // 不在仓库里：下一步一节写绝对路径
    const requests = dirs.map((dir) => ({ op: "events.call", fn: "write_summary", run_dir: dir, root: MAIN, kit_root: REPO }));
    const python = agreeOnFiles(requests, (index) => [join(dirs[index] as string, "summary.md")]);
    const okCount = python.filter((result) => result.ok).length;
    expect(okCount).toBeGreaterThan(50);
    expect(okCount).toBeLessThan(python.length);
    const text = dirs.filter((dir) => existsSync(join(dir, "summary.md"))).map((dir) => readFileSync(join(dir, "summary.md"), "utf8")).join(LF);
    for (const heading of ["## 执行完整性问题", "## 变更文件", "## 越界与警告", "## 复审需要关注", "## 备注", "## 决策", "临时路径摘录已截断", "可疑命令（", "工作副本外路径（", "决策模型提示（", "无意见："]) {
      expect(text.includes(heading), heading).toBe(true);
    }
  });
});
