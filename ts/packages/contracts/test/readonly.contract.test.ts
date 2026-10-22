// 第 ②a 步的契约与对照：pi_dispatch status（文本与 --json）、logs list、logs show。
// 夹具全是合成的：每个用例建一个临时 Git 仓库，按用例写 .agent/runs 下的文件，不复制任何真实证据。
// Python 走真实的命令行，TS 走启动器交来的规整参数；stdout、stderr 逐字节比较，退出码相同。
// 例外：(1) 现取的 elapsed_seconds 只比较格式与范围；(2) Python 会打堆栈的“崩溃”只比较退出码。
// 每个用例先断言 Python 的输出落在要测的那条路上（防止夹具写错、两边一起走了别的路）。特殊字符用码点拼。
import { spawnSync } from "node:child_process";
import { mkdirSync, realpathSync, symlinkSync, writeFileSync } from "node:fs";
import { dirname, join, sep } from "node:path";
import { describe, expect, it } from "vitest";
import { type CliRun, removeDir, runPythonCli, runTsCli, scratchDir } from "./harness.ts";
import { schemaErrors } from "./schemas.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const RUNTIMES = ["node", "bun"] as const;

function makeRepo(name: string): string {
  const dir = scratchDir(name);
  const done = spawnSync("git", ["init", "-q", dir]);
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr.toString()}`);
  return dir;
}

/** 写一个文件：字符串原样写、Buffer 按字节写、其余写成 JSON（JSON.stringify，键序照写的次序）。 */
function put(root: string, rel: string, content: unknown): void {
  const file = join(root, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, typeof content === "string" || Buffer.isBuffer(content) ? content : JSON.stringify(content));
}

const runs = (repo: string, rel = ""): string => join(repo, ".agent", "runs", rel);
const lowerDrive = (value: string): string => value.replace(/^[A-Z]:/u, (drive) => drive.toLowerCase());

function junction(target: string, link: string): void {
  mkdirSync(dirname(link), { recursive: true });
  symlinkSync(target, link, "junction");
}

const text = (run: CliRun): string => run.stdout.toString("utf8");
const ELAPSED = /("elapsed_seconds": |live:\d+t )(\d+)/gu;

/** 现取的秒数换成占位，同时检查两边相差不超过 5 秒。 */
function withoutElapsed(python: CliRun, other: CliRun): [string, string] {
  const a = [...text(python).matchAll(ELAPSED)].map((m) => Number(m[2]));
  const b = [...text(other).matchAll(ELAPSED)].map((m) => Number(m[2]));
  expect(b.length).toBe(a.length);
  a.forEach((value, index) => expect(Math.abs(value - (b[index] as number))).toBeLessThanOrEqual(5));
  return [text(python).replace(ELAPSED, "$1<n>"), text(other).replace(ELAPSED, "$1<n>")];
}

interface Case {
  readonly name: string;
  readonly setup: (repo: string) => void;
  readonly argv: readonly string[] | ((repo: string) => readonly string[]); // pi_dispatch 的子命令与参数（--repo 由用例补上）
  readonly pyargs: Record<string, unknown> | ((repo: string) => Record<string, unknown>); // 启动器交给 TS 的（repo 由用例补上）
  readonly check: (python: CliRun, repo: string) => void; // 先对 Python 断言
  readonly crash?: boolean;
  readonly elapsed?: boolean;
  readonly repoAt?: (repo: string) => string; // --repo 与当前目录不是临时仓库本身时（例如它的 worktree）
}

function compare(item: Case): void {
  const repo = makeRepo(item.name.slice(0, 3));
  try {
    item.setup(repo);
    const argv = typeof item.argv === "function" ? item.argv(repo) : item.argv;
    const pyargs = typeof item.pyargs === "function" ? item.pyargs(repo) : item.pyargs;
    const at = item.repoAt ? item.repoAt(repo) : repo;
    const python = runPythonCli(["--repo", at, ...argv], at);
    item.check(python, repo);
    const forSchema = JSON.parse(JSON.stringify({ ...pyargs, repo: at }, (_key, value: unknown) => (typeof value === "bigint" ? Number(value) : value)));
    expect(schemaErrors("pyargs-v1", forSchema), "启动器参数过 Schema").toEqual([]);
    if (pyargs["json"] === true && python.status === 0) {
      const schema = { status: "status-v1", "logs list": "logs-list-v1", "logs show": "logs-show-v1", "logs cat": "logs-cat-v1",
        "logs search": "logs-search-v1" }[
        (pyargs["command"] as string[]).join(" ") as "status"];
      expect(schemaErrors(schema, JSON.parse(text(python))), `${schema} 过 Schema`).toEqual([]);
    }
    for (const runtime of RUNTIMES) {
      const other = runTsCli(runtime, { ...pyargs, repo: at }, at);
      expect(other.status, `${runtime} 退出码`).toBe(python.status);
      if (item.crash) continue;
      expect(other.stderr.toString("utf8"), `${runtime} stderr`).toBe(python.stderr.toString("utf8"));
      if (item.elapsed) {
        const [a, b] = withoutElapsed(python, other);
        expect(b, `${runtime} stdout`).toBe(a);
      } else {
        expect(other.stdout.equals(python.stdout), `${runtime} stdout 逐字节\n--- python\n${text(python)}\n--- ${runtime}\n${text(other)}`).toBe(true);
      }
    }
  } finally {
    removeDir(repo);
  }
}

const status = (task: string | null, json: boolean): Pick<Case, "argv" | "pyargs"> => ({
  argv: ["status", ...(task === null ? [] : [task]), ...(json ? ["--json"] : [])],
  pyargs: { command: ["status"], task_id: task, json },
});
const list = (extra: { task?: string; state?: string }, json: boolean): Pick<Case, "argv" | "pyargs"> => ({
  argv: ["logs", "list", ...(extra.task === undefined ? [] : ["--task", extra.task]),
    ...(extra.state === undefined ? [] : ["--state", extra.state]), ...(json ? ["--json"] : [])],
  pyargs: { command: ["logs", "list"], task: extra.task ?? null, state: extra.state ?? null, json },
});
const cat = (target: string, file: string, options: { cursor?: string; limit?: number | bigint; json?: boolean } = {}): Pick<Case, "argv" | "pyargs"> => {
  const limit = options.limit ?? 262144;
  const json = options.json ?? true;
  return {
    argv: ["logs", "cat", target, file, ...(options.cursor ? ["--cursor", options.cursor] : []), "--limit", String(limit), ...(json ? ["--json"] : [])],
    pyargs: { command: ["logs", "cat"], target, path: file, cursor: options.cursor ?? null, limit, json },
  };
};
const search = (pattern: string, options: { task?: string; max?: number | bigint; json?: boolean } = {}): Pick<Case, "argv" | "pyargs"> => {
  const max = options.max ?? 50;
  const json = options.json ?? false;
  return {
    argv: ["logs", "search", pattern, ...(options.task === undefined ? [] : ["--task", options.task]), "--max", String(max),
      ...(json ? ["--json"] : [])],
    pyargs: { command: ["logs", "search"], pattern, task: options.task ?? null, max, json },
  };
};

/** 搜索用的证据：两个任务、三个 attempt，各种后缀（含大小写不同的 .LOG，不搜）。 */
function searchable(repo: string): void {
  const one = runs(repo, "alpha/attempt-001");
  put(one, "summary.md", `# alpha\n找到 needle 了\r\n第三行 Needle\n${"长".repeat(150)}needle${C(0x1f600)}${"尾".repeat(80)}\n`);
  put(one, "checks/01/V01.log", "PASS needle\nFAIL\n");
  put(one, "notes/UPPER.LOG", "needle 不搜（后缀按大小写区分）\n");
  put(one, "data.bin", "needle 不搜（不是文本后缀）\n");
  put(runs(repo, "alpha/attempt-002"), "events.jsonl", [
    '{"type": "tool", "text": "needle one"}', "not json needle", `{"api_key": "needle-secret-0123456789"}`,
    `${"x".repeat(4 * 1024 * 1024 + 1)}`, '{"type": "tool", "text": "needle two"}',
  ].join("\n"));
  put(runs(repo, "beta/attempt-001"), "executor-report.json", { status: "completed", note: `needle ${C(0x4e2d, 0x6587)}`, token: "sk-ABCDEFGHIJKLMNOPQRSTUV" });
}

const show = (target: string, json: boolean): Pick<Case, "argv" | "pyargs"> => ({
  argv: ["logs", "show", target, ...(json ? ["--json"] : [])],
  pyargs: { command: ["logs", "show"], target, json },
});

/** 一个齐全的 attempt：各证据文件都在，值的类型各不相同。 */
function fullAttempt(repo: string, rel: string): void {
  const base = runs(repo, rel);
  put(base, "meta.json", { task_id: "alpha", plan_version: 2, attempt_no: 1 });
  put(base, "state.json", { state: "NEEDS_REVIEW", at: "2026-10-18T06:21:40Z" });
  mkdirSync(join(base, "claim"), { recursive: true });
  put(base, "run.json", { exit_code: 0, wall_seconds: 1719.4 });
  put(base, "events-summary.json", { ok: true, usage: { totalTokens: 4210385 }, cost: { total: 1.25, status: "estimated" } });
  put(base, "scope.json", { violations: ["a", "b"] });
  put(base, "checks/01/checks.json", { mode: "fresh", results: [{ passed: true }, { passed: 0 }, { passed: "yes" }, {}] });
  put(base, "checks/1/checks.json", { mode: "ignored-single-digit" });
  put(base, "verdicts/1.json", { verdict: "REVISE", failure_class: "spec", human_minutes: 3 });
  put(base, "verdicts/10.json", { verdict: "PASS", failure_class: null, human_minutes: 2.5 });
  put(base, "verdicts/2.json", { verdict: "ESCALATE" });
  put(base, "summary.md", `# alpha\n\n中文摘要${C(0x1f600)}\n`);
  // 证据清单按码点排序：U+FF5E 在 U+1F600 之前；按 UTF-16 码元排就反过来（代理项 0xD83D 小于 0xFF5E）
  put(base, `notes/${C(0x1f600)}.md`, "x");
  put(base, `notes/${C(0xff5e)}.md`, "y");
}

const CASES: Case[] = [
  {
    name: "S01 没有 runs 目录：文本与 JSON",
    setup: () => {},
    ...status(null, false),
    check: (py) => expect(text(py).trim()).toBe("没有 attempt 记录。"),
  },
  {
    name: "S02 没有 runs 目录：--json 是空表",
    setup: () => {},
    ...status(null, true),
    check: (py) => expect(text(py).trim()).toBe("[]"),
  },
  {
    name: "S03 齐全的 attempt：检查数、最新的结论（按编号 10 > 2 > 1）、用量与费用",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    ...status(null, true),
    check: (py) => {
      const row = (JSON.parse(text(py)) as Record<string, unknown>[])[0] as Record<string, unknown>;
      expect(row).toMatchObject({ checks: "2/4", check_mode: "fresh", verdict: "PASS", violations: 2, tokens: 4210385, started: true });
    },
  },
  {
    name: "S04 齐全的 attempt：文本表格（按码点对齐，末列也补空格）",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      put(runs(repo, "alpha/attempt-002"), "state.json", { state: "完成了" });
    },
    ...status(null, false),
    check: (py) => expect(text(py)).toContain("完成了"),
  },
  {
    name: "S05 值的类型各异：str() 与真值照 Python（True、0 写成 -、空 verdict 写成 -、状态是数字）",
    setup: (repo) => {
      const base = runs(repo, "beta/attempt-001");
      put(base, "meta.json", { task_id: "中文", plan_version: true, attempt_no: 1.5 });
      put(base, "state.json", { state: 5 });
      put(base, "run.json", { exit_code: [1, "二", null], wall_seconds: 0 });
      put(base, "events-summary.json", { ok: "yes", cost: {} });
      put(base, "scope.json", {});
      put(base, "verdicts/3.json", { verdict: "" });
    },
    ...status(null, false),
    check: (py) => expect(text(py)).toMatch(/\[1, '二', None\]/u),
  },
  {
    name: "S06 JSON 里的孤立代理项：输出时写成 ?（Python 的 errors=replace）",
    setup: (repo) => {
      put(runs(repo, "gamma/attempt-001"), "meta.json", `{"task_id": "a${C(0x5c)}ud800b", "plan_version": 1}`);
      put(runs(repo, "gamma/attempt-001"), "state.json", `${C(0xfeff)}{"state": "BOM"}`);
    },
    ...status(null, true),
    check: (py) => {
      expect(text(py)).toContain('"task_id": "a?b"');
      expect(text(py)).toContain('"state": "UNKNOWN"'); // BOM：json.loads 报错，按读不出
    },
  },
  {
    name: "S07 RUNNING 的 live：工具调用数、上次工具之后的增量数、起跑时间的各种写法",
    setup: (repo) => {
      // 第一条增量在工具调用之前：只数上次工具调用之后的 3 条
      const events = '{"type":"message_update"}\n' + '{"type":"tool_execution_end"}\n'.repeat(2) + '{"type":"message_update"}\n'.repeat(3);
      const starts = ["2026-10-22t08:08:41z", "2026-1-2T3:4:5Z", "2026-02-30T00:00:00Z", "2026-10-22T08:08:60Z",
        "2026-10-22T08:08:41Z ", "2026-10-22 08:08:41Z", "2026-10- 2T08:08:41Z", "0000-10-22T08:08:41Z", ""];
      starts.forEach((start, index) => {
        const base = runs(repo, `run/attempt-${String(index + 1).padStart(3, "0")}`);
        put(base, "state.json", { state: "RUNNING" });
        put(base, "events.jsonl", events);
        put(base, "run-started.json", { started_at: start });
      });
    },
    ...status(null, true),
    elapsed: true,
    check: (py) => {
      const rows = JSON.parse(text(py)) as { live: { elapsed_seconds: number | null; tool_calls: number; deltas_since_last_tool: number } }[];
      expect(rows.map((row) => row.live.elapsed_seconds === null)).toEqual([false, false, true, true, true, true, false, true, true]);
      expect(rows[0]?.live).toMatchObject({ tool_calls: 2, deltas_since_last_tool: 3 });
    },
  },
  {
    name: "S08 RUNNING 的文本：events 一列是 live 片段",
    setup: (repo) => {
      put(runs(repo, "run/attempt-001"), "state.json", { state: "RUNNING" });
      put(runs(repo, "run/attempt-001"), "run-started.json", { started_at: "2026-10-22T08:08:41Z" });
    },
    ...status(null, false),
    elapsed: true,
    check: (py) => expect(text(py)).toMatch(/live:0t \d+s/u),
  },
  {
    name: "S09 目标 task.vN：plan_version 按 Python 的 == 比较，1.0 等于 1，取编号最大的",
    setup: (repo) => {
      put(runs(repo, "delta/attempt-001"), "meta.json", { plan_version: 1 });
      put(runs(repo, "delta/attempt-002"), "meta.json", { plan_version: 2 });
      put(runs(repo, "delta/attempt-003"), "meta.json", '{"plan_version": 1.0}'); // JSON.stringify 会把 1.0 写成 1
    },
    ...status("delta.v1", true),
    check: (py) => expect(text(py)).toContain('"attempt": "delta/attempt-003"'),
  },
  {
    name: "S09b 目标 task.vN：True 也等于 1",
    setup: (repo) => {
      put(runs(repo, "delta/attempt-001"), "meta.json", { plan_version: 1 });
      put(runs(repo, "delta/attempt-002"), "meta.json", { plan_version: true });
    },
    ...status("delta.v1", true),
    check: (py) => expect(text(py)).toContain('"attempt": "delta/attempt-002"'),
  },
  {
    name: "S17 attempt 路径在 runs 之外、只是名字同前缀（.agent/runs2）：报“必须位于 runs 下”",
    setup: (repo) => fullAttempt(repo, "../runs2/alpha/attempt-001"),
    argv: (repo) => ["status", join(repo, ".agent", "runs2", "alpha", "attempt-001")],
    pyargs: (repo) => ({ command: ["status"], task_id: join(repo, ".agent", "runs2", "alpha", "attempt-001"), json: false }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("attempt 目录必须位于"),
  },
  {
    name: "S17b 显式 attempt 路径经过指向 runs 之外的 junction：resolve 之后不在 runs 下，拒绝",
    setup: (repo) => {
      fullAttempt(repo, "../outside/alpha/attempt-001");
      junction(join(repo, ".agent", "outside", "alpha"), runs(repo, "alpha"));
    },
    // 用长名路径：临时目录可能带 8.3 短名，那样不求真实路径也会因字面对不上而拒绝，分不出对错
    argv: (repo) => ["status", join(realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-001")],
    pyargs: (repo) => ({ command: ["status"], task_id: join(realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-001"), json: false }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("attempt 目录必须位于"),
  },
  {
    name: "S18 在 worktree 里运行：Repo.discover 拒绝",
    setup: (repo) => {
      spawnSync("git", ["-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "x"]);
      spawnSync("git", ["-C", repo, "worktree", "add", "-q", join(repo, "wt")]);
    },
    repoAt: (repo) => join(repo, "wt"),
    ...status(null, false),
    check: (py) => {
      expect(py.status).toBe(2);
      expect(py.stderr.toString("utf8")).toContain("请在主工作区运行本工具");
    },
  },
  {
    name: "S19 meta.json 嵌套太深：Python 的 read_json_or 不接 RecursionError（崩溃，只比退出码）",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "meta.json", `${"[".repeat(100000)}${"]".repeat(100000)}`),
    ...status(null, true),
    crash: true,
    check: (py) => expect(py.stderr.toString("utf8")).toContain("RecursionError"),
  },
  {
    name: "S20 checks 的编号并列（001 与 01 都是 1）：取先列出来的那一个",
    setup: (repo) => {
      put(runs(repo, "alpha/attempt-001"), "checks/001/checks.json", { mode: "first", results: [{ passed: true }] });
      put(runs(repo, "alpha/attempt-001"), "checks/01/checks.json", { mode: "second", results: [] });
    },
    ...status(null, true),
    check: (py) => expect(text(py)).toContain('"check_mode": "first"'),
  },
  {
    name: "S21 报错里令牌形状的值遮掉（pi_dispatch 的 ERROR 行过 redact_tokens）",
    setup: () => {},
    ...status("sk-ABCDEFGHIJKLMNOPQRSTUVWX", false),
    check: (py) => {
      expect(py.stderr.toString("utf8")).toContain("ERROR: 找不到 attempt：");
      expect(py.stderr.toString("utf8")).not.toContain("ABCDEFGHIJKLMNOP");
    },
  },
  {
    name: "S10 目标 task/attempt-NNN 与 attempt 路径",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-007"),
    ...status("alpha/attempt-007", false),
    check: (py) => expect(text(py)).toContain("alpha/attempt-007"),
  },
  {
    name: "S11 目标找不到：ERROR 行与退出码 2",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    ...status("alpha.v9", false),
    check: (py) => {
      expect(py.status).toBe(2);
      expect(py.stderr.toString("utf8")).toContain("ERROR: 找不到 attempt：alpha.v9");
    },
  },
  {
    name: "S12 最新的 attempt 是 junction：不跟随，报错",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      fullAttempt(repo, "elsewhere/attempt-001");
      junction(runs(repo, "elsewhere/attempt-001"), runs(repo, "alpha/attempt-002"));
    },
    ...status("alpha", false),
    check: (py) => {
      // task-id 本身走列出全部的分支：junction 当目录照列（is_dir 跟随链接），这里只要求两边一致
      expect(py.status).toBe(0);
    },
  },
  {
    name: "S13 task.vN 经过 junction：报“不跟随”",
    setup: (repo) => {
      fullAttempt(repo, "elsewhere/attempt-001");
      junction(runs(repo, "elsewhere/attempt-001"), runs(repo, "alpha/attempt-001"));
    },
    ...status("alpha.v2", false),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("不跟随"),
  },
  {
    name: "S14 verdicts 里有不是数字的文件名：Python 抛 ValueError（崩溃，只比退出码）",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      put(runs(repo, "alpha/attempt-001"), "verdicts/x.json", {});
    },
    ...status(null, true),
    crash: true,
    check: (py) => {
      expect(py.status).toBe(1);
      expect(py.stderr.toString("utf8")).toContain("ValueError");
    },
  },
  {
    name: "S15 meta.json 是数组：.get 抛 AttributeError（崩溃，只比退出码）",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "meta.json", [1]),
    ...status(null, true),
    crash: true,
    check: (py) => expect(py.stderr.toString("utf8")).toContain("AttributeError"),
  },
  {
    name: "S16 任务目录按码点排序；不是 attempt-NNN 的条目不算；编号按整数",
    setup: (repo) => {
      for (const rel of ["b/attempt-1000", "b/attempt-999", "a-1/attempt-001", "a/attempt-002", "a/attempt-001", "a/notes", "c/attempt-01"]) {
        put(runs(repo, rel), "state.json", { state: rel });
      }
    },
    ...status(null, false),
    check: (py) => {
      expect(text(py).indexOf("a/attempt-001")).toBeLessThan(text(py).indexOf("a-1/attempt-001"));
      expect(text(py).indexOf("b/attempt-999")).toBeLessThan(text(py).indexOf("b/attempt-1000")); // 按整数，不按名字
    },
  },
  // --- logs list ---
  {
    name: "L01 list：证据递归计数、摘要有无、junction 计入跳过的链接",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      put(runs(repo, "alpha/attempt-002"), "state.json", { state: "RUNNING", at: 5 });
      put(runs(repo, "alpha/attempt-002"), "deep/er/x.log", "x".repeat(10));
      put(runs(repo, "alpha/attempt-1000"), "state.json", { state: "LATER" }); // 按整数排在 999 之后
      put(runs(repo, "alpha/attempt-999"), "state.json", { state: "EARLIER" });
      junction(runs(repo, "alpha/attempt-001"), runs(repo, "alpha/attempt-002/linked"));
      junction(runs(repo, "alpha"), runs(repo, "zeta"));
    },
    ...list({}, true),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ skipped_links: 2 }),
  },
  {
    name: "L02 list 的文本：状态时间缺失写“无状态时间”，跳过的链接一行",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      put(runs(repo, "alpha/attempt-002"), "state.json", [1]);
      junction(runs(repo, "alpha/attempt-001"), runs(repo, "alpha/attempt-003"));
    },
    ...list({}, false),
    check: (py) => {
      expect(text(py)).toContain("无状态时间");
      expect(text(py)).toContain("跳过的链接：1");
    },
  },
  {
    name: "L03 list --task 与 --state 过滤：过滤掉的 attempt 里的链接不计数",
    setup: (repo) => {
      fullAttempt(repo, "alpha/attempt-001");
      put(runs(repo, "alpha/attempt-002"), "state.json", { state: "RUNNING" });
      junction(runs(repo, "alpha/attempt-001"), runs(repo, "alpha/attempt-002/linked"));
      fullAttempt(repo, "beta/attempt-001");
    },
    ...list({ task: "alpha", state: "NEEDS_REVIEW" }, true),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ skipped_links: 0, attempts: [{ attempt: "attempt-001" }] }),
  },
  {
    name: "L04 list 没有 attempt",
    setup: () => {},
    ...list({}, false),
    check: (py) => expect(text(py).trim()).toBe("没有 attempt"),
  },
  {
    name: "L05 list --task 不合法：repr 照 Python（含单引号时用双引号）",
    setup: () => {},
    ...list({ task: "a'b" }, true),
    check: (py) => expect(py.stderr.toString("utf8")).toContain(`--task 必须是合法的任务 ID："a'b"`),
  },
  {
    name: "L05b list --task 含制表符：repr 用单引号、制表符写成反斜杠加 t（引号与 JSON 的写法不同）",
    setup: () => {},
    ...list({ task: `A${C(0x9)}b` }, false),
    check: (py) => expect(py.stderr.toString("utf8")).toContain(`--task 必须是合法的任务 ID：'A${C(0x5c)}tb'`),
  },
  // --- logs show ---
  {
    name: "L06 show 的 JSON：摘要、证据清单（按路径码点排序）",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    ...show("alpha", true),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ task: "alpha", attempt: "attempt-001", state: "NEEDS_REVIEW" }),
  },
  {
    name: "L07 show 的文本：摘要超过 64 KiB 截断，截在多字节字符中间写成 U+FFFD",
    setup: (repo) => {
      put(runs(repo, "alpha/attempt-001"), "state.json", { state: "DONE" });
      put(runs(repo, "alpha/attempt-001"), "summary.md", `${"a".repeat(65535)}中尾`);
    },
    ...show("alpha/attempt-001", false),
    check: (py) => {
      expect(text(py)).toContain("，已截断");
      expect(text(py)).toContain(C(0xfffd));
    },
  },
  {
    name: "L08 show task.vN：plan_version 必须是真正的 int（True、1.0 都不算）",
    setup: (repo) => {
      put(runs(repo, "alpha/attempt-001"), "meta.json", { plan_version: 1 });
      put(runs(repo, "alpha/attempt-002"), "meta.json", { plan_version: true });
      put(runs(repo, "alpha/attempt-003"), "meta.json", '{"plan_version": 1.0}');
    },
    ...show("alpha.v1", true),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ attempt: "attempt-001" }),
  },
  {
    name: "L09 show 显式路径（绝对路径，含 ..，按段栈处理）",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    argv: (repo) => ["logs", "show", [realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-002", "..", "attempt-001"].join(sep), "--json"],
    pyargs: (repo) => ({ command: ["logs", "show"], target: [realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-002", "..", "attempt-001"].join(sep), json: true }),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ attempt: "attempt-001" }),
  },
  {
    name: "L09b show 显式路径的盘符小写：Windows 上逐段比较不分大小写",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    argv: (repo) => ["logs", "show", lowerDrive(join(realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-001")), "--json"],
    pyargs: (repo) => ({ command: ["logs", "show"], target: lowerDrive(join(realpathSync.native(repo), ".agent", "runs", "alpha", "attempt-001")), json: true }),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ attempt: "attempt-001" }),
  },
  {
    name: "L10 show 显式路径越出 runs 根",
    setup: (repo) => fullAttempt(repo, "alpha/attempt-001"),
    argv: (repo) => ["logs", "show", [realpathSync.native(repo), ".agent", "runs", "..", "..", "x"].join(sep)],
    pyargs: (repo) => ({ command: ["logs", "show"], target: [realpathSync.native(repo), ".agent", "runs", "..", "..", "x"].join(sep), json: false }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("目标越出 runs 根"),
  },
  {
    name: "L11 show task/attempt-NNN 经过 junction",
    setup: (repo) => {
      fullAttempt(repo, "elsewhere/attempt-001");
      junction(runs(repo, "elsewhere"), runs(repo, "alpha"));
    },
    ...show("alpha/attempt-001", false),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("目标经过链接：alpha"),
  },
  {
    name: "L12 show 目标不存在、任务没有 attempt",
    setup: (repo) => mkdirSync(runs(repo, "alpha"), { recursive: true }),
    ...show("alpha", false),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("任务 alpha 没有 attempt"),
  },
  // --- logs cat（②b1）---
  {
    name: "C01 文本页：一页放不下一行时按片给（part/parts），后面不是换行",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", `${"a".repeat(10)}\n${"b".repeat(25)}${C(0x1f600)}\ntail`),
    ...cat("alpha/attempt-001", "summary.md", { limit: 8 }),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ mode: "text", part: 1, parts: 2, done: false }),
  },
  {
    name: "C02 文本模式：原样写出（不加换行），CRLF 写成 \\r\\r\\n，没读完时 stderr 给游标",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "notes.txt", `one\r\ntwo\r\n${"x".repeat(50)}`),
    ...cat("alpha/attempt-001", "notes.txt", { limit: 12, json: false }),
    check: (py) => {
      expect(py.stdout.includes(Buffer.from("one\r\r\n"))).toBe(true);
      expect(py.stderr.toString("utf8")).toContain("（未完：--cursor t:");
    },
  },
  {
    name: "C03 json 模式：整份能解析时按键名脱敏、带缩进写出",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "executor-report.json", { token: "sk-ABCDEFGHIJKLMNOPQRSTUV", note: `中${C(0x1f600)}`, n: 1.5 }),
    ...cat("alpha/attempt-001", "executor-report.json"),
    check: (py) => {
      expect(text(py)).not.toContain("ABCDEFGHIJKLMNOP");
      expect(JSON.parse(text(py)).text).toContain('{\n  "token": ');
    },
  },
  {
    name: "C04 json 模式：带 BOM 解析不了，整份按文本脱敏",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "meta.json", `${C(0xfeff)}{"password": "hunter2hunter2"}`),
    ...cat("alpha/attempt-001", "meta.json"),
    check: (py) => expect(JSON.parse(text(py)).text.startsWith(C(0xfeff))).toBe(true),
  },
  {
    name: "C05 JSONL：合法行脱敏、坏行与超长行只给占位、空白行写空、孤立代理项写成转义、末行没有换行照给",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", [
      '{"type": "x", "api_key": "abcdefghijklmnop1234"}', "not json", "", ` ${C(0x9)} `,
      `{"a": "x${C(0x5c)}ud800y"}`, `${"x".repeat(4 * 1024 * 1024 + 1)}`, '{"b": 1}',
    ].join("\n")),
    ...cat("alpha/attempt-001", "events.jsonl"),
    check: (py) => {
      const page = JSON.parse(text(py)) as { lines: Record<string, unknown>[] };
      expect(page.lines.map((line) => line["hidden"] ?? "text")).toEqual(["text", "not_json", "text", "text", "text", "too_long", "text"]);
      expect(text(py)).toContain(`x${C(0x5c, 0x5c)}ud800y`);
    },
  },
  {
    name: "C06 JSONL 的文本模式：隐藏的行写说明",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", '{"a": 1}\nnot json\n{"b": 2}\n'),
    ...cat("alpha/attempt-001", "events.jsonl", { json: false }),
    check: (py) => expect(text(py)).toContain("（第 2 行已隐藏：不是合法 JSON）"),
  },
  {
    name: "C07 游标格式不对",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", "x"),
    ...cat("alpha/attempt-001", "summary.md", { cursor: "t:zz" }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("游标格式不对"),
  },
  {
    name: "C07b 游标字段是十六进制字母：过得了格式检查，按十进制解析时拒绝",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", "x"),
    ...cat("alpha/attempt-001", "summary.md", { cursor: "t:a:1:2:3" }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("游标格式不对"),
  },
  {
    name: "C15 扩展名大写的 .JSONL 也按 JSONL 读",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "EVENTS.JSONL", '{"a": 1}\nbad\n'),
    ...cat("alpha/attempt-001", "EVENTS.JSONL"),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ mode: "jsonl" }),
  },
  {
    name: "C08 文本游标对不上文件身份：已变化",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", "x"),
    ...cat("alpha/attempt-001", "summary.md", { cursor: "t:0:1:2:3" }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("游标对应的文件已变化"),
  },
  {
    name: "C09 JSONL 文件给文本游标：格式不对",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", '{"a": 1}\n'),
    ...cat("alpha/attempt-001", "events.jsonl", { cursor: "t:0:0:0:0" }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("游标格式不对"),
  },
  {
    name: "C10 --limit 为 0",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", "x"),
    ...cat("alpha/attempt-001", "summary.md", { limit: 0 }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("--limit 必须在 1 到 262144 之间：0"),
  },
  {
    name: "C11 --limit 超出 JS 数字的精度：报错里原样写出",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", "x"),
    ...cat("alpha/attempt-001", "summary.md", { limit: 99999999999999999999n }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("：99999999999999999999"),
  },
  {
    name: "C12 路径用反斜杠：按斜杠认",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "checks/01/V01.log", "ok\n"),
    ...cat("alpha/attempt-001", `checks${C(0x5c)}01${C(0x5c)}V01.log`),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ path: "checks/01/V01.log", text: "ok\n" }),
  },
  {
    name: "C13 路径不在证据清单里（含经过链接的）",
    setup: (repo) => {
      put(runs(repo, "alpha/attempt-001"), "summary.md", "x");
      put(runs(repo, "elsewhere/attempt-001"), "secret.txt", "y");
      junction(runs(repo, "elsewhere/attempt-001"), runs(repo, "alpha/attempt-001/linked"));
    },
    ...cat("alpha/attempt-001", "linked/secret.txt"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("不在 alpha/attempt-001 的证据清单里：linked/secret.txt"),
  },
  {
    name: "C14 文本超过 64 MiB：不显示",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "big.log", Buffer.alloc(64 * 1024 * 1024 + 1, 0x61)),
    ...cat("alpha/attempt-001", "big.log"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("文件太大（超过上限 67108864 字节）"),
  },
  // --- logs search（②b2）---
  {
    name: "X01 文本：跨任务与 attempt、行号、CRLF 去掉 \\r、长行截到 200 个码点、后缀按大小写区分、隐藏的行不搜",
    setup: searchable,
    ...search("needle"),
    check: (py) => {
      expect(text(py)).toContain("alpha/attempt-001/summary.md:2: 找到 needle 了\r\n");
      expect(text(py)).toContain("alpha/attempt-002/events.jsonl:5: ");
      expect(text(py)).not.toContain("UPPER.LOG");
      expect(text(py)).not.toContain("not json needle");
    },
  },
  {
    name: "X02 JSON：匹配、脱敏之后的文本、不截断",
    setup: searchable,
    ...search("needle", { json: true }),
    check: (py) => {
      const data = JSON.parse(text(py)) as { matches: { path: string; line: number; text: string }[]; truncated: boolean };
      expect(data.truncated).toBe(false);
      expect(data.matches.map((m) => `${m.path}:${m.line}`)).toContain("events.jsonl:1");
      expect(text(py)).not.toContain("needle-secret");
    },
  },
  {
    name: "X03 --max 截断：文本与 JSON",
    setup: searchable,
    ...search("needle", { max: 2 }),
    check: (py) => expect(text(py)).toContain("（已截断：只显示前 2 条匹配）"),
  },
  {
    name: "X04 --max 截断（JSON），--task 只搜一个任务",
    setup: searchable,
    ...search("needle", { max: 1, json: true, task: "alpha" }),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ truncated: true, matches: [{ task: "alpha" }] }),
  },
  {
    name: "X05 Python 正则的语义：(?i) 用简单大小写映射（开尔文符号算 k）、\\w 认中文、\\b、后顾；分支里的 (?a:) 照常",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "notes.txt",
      [`${C(0x212a)}ilo`, "中文word", "a-b", "x=1", `${C(0xb5)}${C(0xfb05)}`, `${C(0x3b9)} ${C(0x3a3)}`, "STRASSE", `stra${C(0xdf)}e`].join("\n")),
    ...search(`(?i:kilo)|^${C(0x5c)}w+word$|${C(0x5c)}ba${C(0x5c)}b|(?<=x=)1|(?a:[^${C(0x5c)}w${C(0x10400)} A-i])|(?i:stra${C(0xdf)}e)`),
    check: (py) => {
      expect(text(py)).toContain(`notes.txt:1: ${C(0x212a)}ilo`);
      expect(text(py)).toContain("notes.txt:2: 中文word");
      expect(text(py)).toContain(`notes.txt:8: stra${C(0xdf)}e`);
      expect(text(py)).toContain(`notes.txt:5: ${C(0xb5)}${C(0xfb05)}`); // 整个模式是分支：没有字符集前缀
      expect(text(py)).not.toContain("STRASSE");
    },
  },
  {
    name: "X05b 整个模式就是 (?a:[^\\w…])：sre 的字符集前缀按整个模式的 Unicode \\w 判定，µ 不算起点",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "notes.txt", [`${C(0xb5)}${C(0xfb05)}`, "-", "b"].join("\n")),
    ...search(`(?s)(?a:[^${C(0x5c)}w${C(0x10400)} A-i])`),
    check: (py) => {
      expect(text(py)).toContain("notes.txt:2: -");
      expect(text(py)).not.toContain(`${C(0xb5)}`);
    },
  },
  {
    name: "X06 空的 PATTERN 匹配每一行（含空行），json 文件按缩进写出之后逐行搜",
    setup: (repo) => put(runs(repo, "alpha/attempt-001"), "meta.json", { a: 1, password: "hunter2hunter2" }),
    ...search("", { json: true }),
    check: (py) => {
      const data = JSON.parse(text(py)) as { matches: { text: string }[] };
      expect(data.matches.map((m) => m.text)).toEqual(["{", '  "a": 1,', '  "password": "<redacted>"', "}", ""]);
    },
  },
  {
    name: "X07 跳过的大文件与链接：计数",
    setup: (repo) => {
      put(runs(repo, "alpha/attempt-001"), "big.log", Buffer.alloc(64 * 1024 * 1024 + 1, 0x61));
      put(runs(repo, "alpha/attempt-001"), "ok.log", "aaa\n");
      put(runs(repo, "elsewhere/attempt-001"), "x.log", "aaa\n");
      junction(runs(repo, "elsewhere"), runs(repo, "linked"));
    },
    ...search("a+"),
    check: (py) => {
      expect(text(py)).toContain("跳过的大文件或读不出来的文件：1");
      expect(text(py)).toContain("跳过的链接：1");
    },
  },
  {
    name: "X08 不合法的 PATTERN：re.error 的原文（位置、行列）",
    setup: searchable,
    ...search(`a${C(0xa)}(b`),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 不是合法的正则表达式：missing ), unterminated subpattern at position 2 (line 2, column 1)"),
  },
  {
    name: "X08b 全局标志不在开头",
    setup: searchable,
    ...search("a(?i)b"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("global flags not at the start of the expression at position 1"),
  },
  {
    name: "X09 反向引用拒绝（在 --max 检查之前）",
    setup: searchable,
    ...search(`(a)${C(0x5c)}1`, { max: 0 }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 不支持反向引用与条件分组"),
  },
  {
    name: "X10 条件分组拒绝",
    setup: searchable,
    ...search("(a)?(?(1)b|c)"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 不支持反向引用与条件分组"),
  },
  {
    name: "X11 括号嵌套超过 100 层",
    setup: searchable,
    ...search(`${"(".repeat(101)}a${")".repeat(101)}`),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 的括号嵌套超过 100 层"),
  },
  {
    name: "X12 重复次数太大（OverflowError）",
    setup: searchable,
    ...search("a{4294967295}"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 不是合法的正则表达式：the repetition number is too large"),
  },
  {
    name: "X13 编译期的错误：后顾不定宽",
    setup: searchable,
    ...search("(?<=a+)b"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("PATTERN 不是合法的正则表达式：look-behind requires fixed-width pattern"),
  },
  {
    name: "X14 (?a)(?u)：Python 不接的 ValueError（崩溃，只比较退出码）",
    setup: searchable,
    ...search("(?a)(?u)x"),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("ValueError"),
    crash: true,
  },
  {
    name: "X15 --max 为 0",
    setup: searchable,
    ...search("needle", { max: 0 }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("--max 必须是不小于 1 的整数：0"),
  },
  {
    name: "X16 --max 超出 JS 数字的精度",
    setup: searchable,
    ...search("needle", { max: 99999999999999999999n, json: true }),
    check: (py) => expect(JSON.parse(text(py))).toMatchObject({ truncated: false }),
  },
  {
    name: "X17 --task 不合法",
    setup: searchable,
    ...search("needle", { task: "../x" }),
    check: (py) => expect(py.stderr.toString("utf8")).toContain("--task 必须是合法的任务 ID"),
  },
  {
    name: "X18 没有匹配、没有 runs 目录",
    setup: () => {},
    ...search("needle"),
    check: (py) => expect(py.stdout.length).toBe(0),
  },
];

/** 同一个仓库里翻页：Python 与 TS 拿同一个游标逐页比较，下一页的游标取自 Python 的输出。 */
function comparePages(setup: (repo: string) => void, target: string, file: string, limit: number, pages: number,
  between?: (repo: string, page: number) => void): number {
  const repo = makeRepo("pg");
  let compared = 0;
  try {
    setup(repo);
    let cursor: string | null = null;
    for (let page = 1; page <= pages; page += 1) {
      between?.(repo, page);
      const python = runPythonCli(["--repo", repo, "logs", "cat", target, file, ...(cursor ? ["--cursor", cursor] : []), "--limit", String(limit), "--json"], repo);
      for (const runtime of RUNTIMES) {
        const other = runTsCli(runtime, { command: ["logs", "cat"], repo, target, path: file, cursor, limit, json: true }, repo);
        expect([other.status, other.stderr.toString("utf8")], `${runtime} 第 ${page} 页`).toEqual([python.status, python.stderr.toString("utf8")]);
        expect(other.stdout.equals(python.stdout), `${runtime} 第 ${page} 页 stdout\n${text(python)}\n---\n${text(other)}`).toBe(true);
      }
      compared += 1;
      if (python.status !== 0) break;
      expect(schemaErrors("logs-cat-v1", JSON.parse(text(python)))).toEqual([]);
      const data = JSON.parse(text(python)) as { done: boolean; next_cursor: string };
      if (data.done) break;
      cursor = data.next_cursor;
    }
    return compared;
  } finally {
    removeDir(repo);
  }
}

describe("第 ②a、②b1、②b2 步：status、logs list、logs show、logs cat、logs search 与 Python 逐字节一致", () => {
  for (const item of CASES) it(item.name, () => compare(item), 120_000);

  it("P01 文本翻页：长行按片、补充平面字符按码点", () => {
    const body = [`${"中".repeat(9)}${C(0x1f600)}${"b".repeat(13)}`, "short", "", `${C(0x1d400)}`.repeat(20), "end"].join("\n");
    expect(comparePages((repo) => put(runs(repo, "alpha/attempt-001"), "summary.md", body), "alpha/attempt-001", "summary.md", 7, 40)).toBeGreaterThan(8);
  }, 300_000);

  it("P02 JSONL 翻页：一行超过一页时按片续读（行内字符位置）", () => {
    const lines = ['{"a": 1}', `{"long": "${"x".repeat(70)}${C(0x1f600)}"}`, '{"b": 2}', "bad", '{"c": 3}'].join("\n") + "\n";
    expect(comparePages((repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", lines), "alpha/attempt-001", "events.jsonl", 20, 40)).toBeGreaterThan(5);
  }, 300_000);

  it("P03 JSONL 翻页途中文件变长：游标照常；之前的字节被改写：已变化", () => {
    const lines = '{"a": 1}\n{"b": 2}\n{"c": 3}\n';
    const file = (repo: string): string => join(runs(repo, "alpha/attempt-001"), "events.jsonl");
    expect(comparePages((repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", lines), "alpha/attempt-001", "events.jsonl", 30, 6,
      (repo, page) => {
        if (page === 2) writeFileSync(file(repo), `${lines}{"d": 4}\n`);
      })).toBeGreaterThan(2);
    expect(comparePages((repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", lines), "alpha/attempt-001", "events.jsonl", 30, 3,
      (repo, page) => {
        if (page === 2) writeFileSync(file(repo), lines.replace('"a"', '"z"'));
      })).toBe(2);
    // 文件变长、之前的字节也被改了：大小与修改时间都说明不了，靠游标之前那一段的哈希
    expect(comparePages((repo) => put(runs(repo, "alpha/attempt-001"), "events.jsonl", lines), "alpha/attempt-001", "events.jsonl", 30, 3,
      (repo, page) => {
        if (page === 2) writeFileSync(file(repo), `${lines.replace('"a"', '"z"')}{"d": 4}\n`);
      })).toBe(2);
  }, 300_000);
});
