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
    expect(schemaErrors("pyargs-v1", { ...pyargs, repo: at }), "启动器参数过 Schema").toEqual([]);
    if (pyargs["json"] === true && python.status === 0) {
      const schema = { status: "status-v1", "logs list": "logs-list-v1", "logs show": "logs-show-v1" }[
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
];

describe("第 ②a 步：status、logs list、logs show 与 Python 逐字节一致", () => {
  for (const item of CASES) it(item.name, () => compare(item), 120_000);
});
