// status --json 的输入名单（contracts/status-inputs.json，桌面端设计第 7 版 T3）的守卫：Python 与 TS 的 status 在
// 夹具上实际碰过的路径（列目录、stat、读文件），归一之后与名单双向一致。本机服务的 SSE 只 stat 名单里的路径察觉
// 变化，status 多读一个文件而名单没跟上，那个文件变了就推不出去（themistally-15 起初指出 check、verdict 落定推不出去）。
//
// 追踪：Python 在子进程里改写 os.stat、os.lstat、os.listdir、os.scandir、io.open 与内置的 open（pathlib 经前几个，
// read_json 用内置的 open）；TS 在 Node
// 下以 `--import fixtures/trace-fs.mjs` 预载改写 node:fs 的钩子。两边都只看 .agent/runs 之下的路径。
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";
import { removeDir, scratchDir } from "./harness.ts";

type Kind = "stat" | "list" | "read";

interface Inputs {
  readonly attempt_pattern: string;
  readonly numbered_pattern: string;
  readonly list: readonly string[];
  readonly exists: readonly string[];
  readonly read: readonly string[];
  readonly read_when_running: readonly string[];
  readonly incidental_stat: Readonly<Record<string, string>>;
}

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTRACTS = resolve(HERE, "..");
const REPO_ROOT = resolve(CONTRACTS, "..", "..", "..");
const CLI_MAIN = resolve(CONTRACTS, "..", "cli", "src", "main.ts");
const HOOK = join(HERE, "fixtures", "trace-fs.mjs");
const INPUTS = JSON.parse(readFileSync(join(CONTRACTS, "status-inputs.json"), "utf8")) as Inputs;
const ATTEMPT = new RegExp(INPUTS.attempt_pattern, "u");
const NUMBERED = new RegExp(INPUTS.numbered_pattern, "u");
const PY = process.env["THEMIS_PYTHON"] ?? "python";

function put(root: string, rel: string, content: unknown): void {
  const file = join(root, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, typeof content === "string" ? content : JSON.stringify(content));
}

/** 夹具：一个已结束的 attempt（两份 check、一份 verdict）、一个运行中的 attempt，再加几样不该影响输出的条目。 */
function fixture(): string {
  const repo = scratchDir("status-inputs");
  const done = spawnSync("git", ["init", "-q", repo]);
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr.toString()}`);
  const runs = join(repo, ".agent", "runs");
  const finished = join(runs, "t1", "attempt-001");
  put(finished, "meta.json", { task_id: "t1", plan_version: 1, attempt_no: 1 });
  put(finished, "run.json", { exit_code: 0, wall_seconds: 12.5 });
  put(finished, "events-summary.json", { ok: true, usage: { totalTokens: 10 }, cost: { total: 0.1, status: "ok" } });
  put(finished, "scope.json", { violations: [] });
  put(finished, "state.json", { state: "PASS" });
  put(finished, "checks/01/checks.json", { mode: "full", results: [{ passed: true }] });
  put(finished, "checks/02/checks.json", { mode: "full", results: [{ passed: true }, { passed: false }] });
  put(finished, "verdicts/01.json", { verdict: "PASS", failure_class: null, human_minutes: 3 });
  mkdirSync(join(finished, "claim"));
  const running = join(runs, "t1", "attempt-002");
  put(running, "meta.json", { task_id: "t1", plan_version: 1, attempt_no: 2 });
  put(running, "state.json", { state: "RUNNING" });
  put(running, "run-started.json", { started_at: "2026-10-23T00:00:00Z" });
  put(running, "events.jsonl", '{"type":"tool_execution_end"}\n{"type":"message_update"}\n');
  mkdirSync(join(running, "claim"));
  put(runs, "t1/notes.txt", "不是 attempt");
  mkdirSync(join(runs, "t1", "attempt-x"));
  put(runs, "_env/doctor.json", {});
  put(runs, "README.txt", "runs 根下的文件");
  return repo;
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** 一条路径归一成名单的写法；不在 .agent/runs 之下时为 null。 */
function normalize(runs: string, logged: string): string | null {
  const bases = [runs, realpathSync.native(runs)].map((base) => base.replace(/\//gu, "\\").toLowerCase());
  const path = resolve(logged).replace(/\//gu, "\\");
  const base = bases.find((item) => path.toLowerCase() === item || path.toLowerCase().startsWith(`${item}\\`));
  if (base === undefined) return null;
  const rest = path.slice(base.length).replace(/^\\/u, "");
  const out: string[] = [];
  let actual = runs;
  for (const [index, segment] of (rest === "" ? [] : rest.split("\\")).entries()) {
    actual = join(actual, segment);
    if (index === 0) out.push(isDirectory(actual) ? "<task>" : "<other>");
    else if (index === 1) out.push(ATTEMPT.test(segment) && isDirectory(actual) ? "<attempt>" : "<other>");
    else if (index === 3 && out[2] === "verdicts" && segment.endsWith(".json")) out.push("<n>.json");
    else if (index === 3 && out[2] === "checks" && NUMBERED.test(segment)) out.push("<n>");
    else out.push(segment);
  }
  return out.join("/");
}

function touched(repo: string, trace: readonly (readonly [Kind, string])[]): Set<string> {
  const runs = join(repo, ".agent", "runs");
  const found = new Set<string>();
  for (const [kind, path] of trace) {
    const norm = normalize(runs, path);
    if (norm !== null) found.add(`${kind} ${norm}`);
  }
  return found;
}

function tracePython(repo: string): Set<string> {
  const out = join(repo, "..", `${repo.split(/[\\/]/u).pop() ?? "x"}-py-trace.json`);
  const program = [
    "import builtins, io, json, os, sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO_ROOT, "scripts"))})`,
    "import pi_dispatch as pd",
    `pd.KERNEL_IMPL_PATH = pd.Path(${JSON.stringify(join(repo, "absent-selector.json"))})`,
    "log = []",
    "original_open = io.open",
    "def wrap(kind, fn):",
    "    def inner(path, *args, **kwargs):",
    "        if not isinstance(path, int):",
    "            log.append([kind, os.fsdecode(os.fspath(path))])",
    "        return fn(path, *args, **kwargs)",
    "    return inner",
    "os.stat, os.lstat = wrap('stat', os.stat), wrap('stat', os.lstat)",
    "os.listdir, os.scandir = wrap('list', os.listdir), wrap('list', os.scandir)",
    "builtins.open = io.open = wrap('read', original_open)  # read_json 用内置的 open，pathlib 用 io.open",
    `code = pd.main(["--repo", ${JSON.stringify(repo)}, "status", "--json"])`,
    `with original_open(${JSON.stringify(out)}, "w", encoding="utf-8") as handle:`,
    "    json.dump(log, handle)",
    "sys.exit(code)",
  ].join("\n");
  const done = spawnSync(PY, ["-c", program], { cwd: repo, encoding: "utf8", timeout: 120_000 });
  expect(done.status, done.stderr).toBe(0);
  return touched(repo, JSON.parse(readFileSync(out, "utf8")) as [Kind, string][]);
}

function traceTs(repo: string): Set<string> {
  const out = join(repo, "..", `${repo.split(/[\\/]/u).pop() ?? "x"}-ts-trace.json`);
  const pyargs = Buffer.from(JSON.stringify({ command: ["status"], repo, task_id: null, json: true }), "utf8").toString("base64");
  const done = spawnSync(process.execPath, ["--import", pathToFileURL(HOOK).href, CLI_MAIN, "--pyargs-b64", pyargs], {
    cwd: repo, encoding: "utf8", timeout: 120_000, env: { ...process.env, THEMIS_TRACE_OUT: out },
  });
  expect(done.status, done.stderr).toBe(0);
  return touched(repo, JSON.parse(readFileSync(out, "utf8")) as [Kind, string][]);
}

/** 名单之外碰了什么（按种类各自的许可范围）。 */
function outsideTheList(found: ReadonlySet<string>): string[] {
  const reads = new Set([...INPUTS.read, ...INPUTS.read_when_running]);
  const lists = new Set(INPUTS.list);
  const stats = new Set([...INPUTS.list, ...INPUTS.exists, ...reads, ...Object.keys(INPUTS.incidental_stat)]);
  return [...found].filter((entry) => {
    const [kind, path] = [entry.slice(0, entry.indexOf(" ")), entry.slice(entry.indexOf(" ") + 1)];
    return kind === "read" ? !reads.has(path) : kind === "list" ? !lists.has(path) : !stats.has(path);
  }).sort();
}

/** 名单里有、却没有碰到的（夹具里每一样都在，所以每一样都该被碰到）。 */
function missingFromTrace(found: ReadonlySet<string>): string[] {
  const expected = [
    ...INPUTS.read.map((path) => `read ${path}`), ...INPUTS.read_when_running.map((path) => `read ${path}`),
    ...INPUTS.list.map((path) => `list ${path}`), ...INPUTS.exists.map((path) => `stat ${path}`),
  ];
  return expected.filter((entry) => !found.has(entry)).sort();
}

describe("status --json 的输入名单", () => {
  it("归一的规则", () => {
    const repo = fixture();
    try {
      const runs = join(repo, ".agent", "runs");
      expect(normalize(runs, join(runs, "t1", "attempt-001", "checks", "02", "checks.json"))).toBe("<task>/<attempt>/checks/<n>/checks.json");
      expect(normalize(runs, join(runs, "t1", "attempt-001", "verdicts", "01.json"))).toBe("<task>/<attempt>/verdicts/<n>.json");
      expect(normalize(runs, join(runs, "t1", "attempt-x"))).toBe("<task>/<other>");
      expect(normalize(runs, join(runs, "t1", "notes.txt"))).toBe("<task>/<other>");
      expect(normalize(runs, join(runs, "README.txt"))).toBe("<other>");
      expect(normalize(runs, runs)).toBe("");
      expect(normalize(runs, join(repo, ".agent", "dispatch.config.json"))).toBeNull();
    } finally {
      removeDir(repo);
    }
  });

  it.each([["Python", tracePython], ["TS（Node）", traceTs]] as const)("%s 的 status 碰过的路径都在名单里，名单里的也都碰到了", (_name, trace) => {
    const repo = fixture();
    try {
      const found = trace(repo);
      expect(outsideTheList(found), "名单之外碰了这些：status 多读了文件就把它加进 status-inputs.json").toEqual([]);
      expect(missingFromTrace(found), "名单里有却没碰到：status 不再读它了就从 status-inputs.json 删掉").toEqual([]);
    } finally {
      removeDir(repo);
      for (const suffix of ["-py-trace.json", "-ts-trace.json"]) removeDir(join(repo, "..", `${repo.split(/[\\/]/u).pop() ?? "x"}${suffix}`));
    }
  });

  it("追踪真的看得见：多读一个文件就出现在名单之外", () => {
    const extra = new Set(["read <task>/<attempt>/new-file.json", "list <task>/<attempt>/checks"]);
    expect(outsideTheList(extra)).toEqual(["read <task>/<attempt>/new-file.json"]);
    expect(missingFromTrace(extra)).toContain("read <task>/<attempt>/meta.json");
  });
});
