// 第 ⑤g1 片的手写对照（采样那份在 hub-exec.contract.test.ts）：这几个函数只读，搭好目录之后三边各读一遍，交回值逐字比，崩溃比类型与文字。
// 样本没走到的在这里：
//   - attempt 目录的各种读法（checks.json、scope.json、执行报告、events-summary.json、report-status.json 的各种形状与坏法）；
//   - 接着改从哪儿来（carry_source、carry_back、rework_source、interrupted_attempt、failed_attempt、attempts_left 的各个分支）；
//   - 返工节与重派节的文字、add_modified_files 的各种写法、门禁有错的说法、JEV 的标注；
//   - returned_blockers 比修改时刻（candidate.patch 的时刻由 Python 用 os.utime(ns=...) 设准，含微秒进位到下一秒）；
//   - empty_commit 用真 git；按种子随机换类型的 attempt 目录。
// 不写转义序列。
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { PYTHON, type ProbeRequest, type ProbeResult, prng, runAgreeing, runProbe } from "./harness.ts";
import { AT, C, CR, LF, py } from "./flow-fixtures.ts";
import { git, newRepo, put, removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const call = (fn: string, args: unknown[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))) });
const agree = (requests: readonly ProbeRequest[]): ProbeResult[] => {
  const { python, mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
};
const valueOf = (result: ProbeResult | undefined): PyValue => (result?.["ok"] ? fromTagged(result["value"] as Tagged) : `${result?.["error"]}: ${result?.["message"]}`);
const lines = (...items: string[]): string => [...items, ""].join(LF);
const state = (name: string): string => JSON.stringify({ state: name });
const BT = "`";

/** 一个 attempt 目录：files 里的值是字符串就原样写，否则写成 JSON。 */
function attemptDir(root: string, name: string, files: Record<string, unknown>): string {
  const dir = join(root, name);
  mkdirSync(dir, { recursive: true });
  for (const [rel, content] of Object.entries(files)) put(dir, rel, typeof content === "string" ? content : JSON.stringify(content));
  return dir;
}

/** 战后之前的主任务状态：contract_task 是 t001-doc，合同是 t001-doc.v1。 */
function taskState(extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", "base0", true, AT);
  ts.set("contract", py({ key: "t001-doc.v1" }) as PyDict);
  for (const [key, value] of Object.entries(extra)) ts.set(key, py(value));
  return ts;
}

const READERS = ["latest_checks", "cut_off", "checks_passed", "unfinished_why", "failed_checks_brief", "failure_lines", "report_leftovers", "unreported_gate_claims"];

describe("第 ⑤g1 片：attempt 目录的读法（手写，三边逐字比）", () => {
  it("checks.json、scope.json、执行报告、events-summary.json、report-status.json 的各种形状与坏法", () => {
    const root = tempDir("exec-read");
    const failed = (id: string, extra: Record<string, unknown> = {}): Record<string, unknown> => ({ id, status: "failed", ...extra });
    const longLog = lines(...Array.from({ length: 50 }, (_, at) => `第 ${at + 1} 行`));
    const astral = `${C(0x1f600)}理由`.repeat(60);
    const dirs = [
      attemptDir(root, "a0", {}),
      attemptDir(root, "a1", { "state.json": state("TIMEOUT"), "candidate.patch": "x", "scope.json": { violations: [] }, "meta.json": {} }),
      attemptDir(root, "a2", {
        "state.json": state("NEEDS_REVIEW"), "candidate.patch": "x", "scope.json": {},
        "checks/20261101T000000Z/checks.json": { results: [{ id: "V01", status: "passed" }, failed("V02", { log: "V02.log", reason: "exit 1" })] },
        "checks/V02.log": longLog,
      }),
      attemptDir(root, "a3", { "state.json": state("NEEDS_REVIEW"), "candidate.patch": "x", "scope.json": {}, "checks/x/checks.json": { results: [{ id: "V01", status: "passed" }] } }),
      attemptDir(root, "a4", { // 最近一次 check 按名字排：Windows 上不分大小写
        "checks/a/checks.json": { results: [failed("V01")] }, "checks/B/checks.json": { results: [{ id: "V01", status: "passed" }] },
      }),
      attemptDir(root, "a5", { "events-summary.json": { final_stop_reason: "length" }, "report-status.json": { status: "missing" } }),
      attemptDir(root, "a6", { "events-summary.json": { final_stop_reason: "stop" }, "report-status.json": ["不看"] }),
      attemptDir(root, "a7", { "events-summary.json": { final_stop_reason: "length" }, "report-status.json": ["要看"] }),
      attemptDir(root, "a8", { "events-summary.json": "{", "executor-report.json": "[1, 2" }),
      attemptDir(root, "a9", { "checks/x/checks.json": { results: "ab" } }),
      attemptDir(root, "a10", { "checks/x/checks.json": { results: [failed("V01", { reason: astral }), failed("V02", { reason: [1, 2, 3] }), failed("V03", { reason: {} }), failed(" V04 ")] } }),
      attemptDir(root, "a11", { "checks/x/checks.json": { results: [failed("V01", { reason: { a: 1 } })] } }),
      attemptDir(root, "a12", { "checks/x/checks.json": { results: [failed("V01", { reason: 5 })] } }),
      attemptDir(root, "a13", { "checks/x/checks.json": { results: [failed("V01", { reason: true })] } }),
      attemptDir(root, "a14", {
        "checks/x/checks.json": { results: [1, 2, 3, 4, 5].map((at) => failed(`V0${at}`, { log: at % 2 ? `V0${at}.log` : 7, reason: at === 3 ? null : "r" })) },
        "checks/V01.log": `一${CR}${LF}二${LF}`, "checks/V03.log": "",
        "scope.json": { violations: [{ path: "a.py", kind: "M", detail: "越界" }, { path: null }] },
      }),
      attemptDir(root, "a15", { "scope.json": { violations: "ab" } }),
      attemptDir(root, "a16", { "scope.json": { violations: { a: 1 } } }),
      attemptDir(root, "a17", {
        "executor-report.json": {
          executor_status: "  部分 完成 ", limitations: ["限制一", { text: "x" }, 5, `很长${"字".repeat(300)}`],
          dod: [{ id: "D1", status: "done" }, { id: "D2", status: "not_done", note: `  多行${LF}  说明  ` }, "x", { id: ["l"], status: null }, { id: "D3", status: "blocked", note: `${C(0x1f600)}`.repeat(301) }],
        },
      }),
      attemptDir(root, "a18", { "executor-report.json": { limitations: "ab", dod: { D1: 1 } } }),
      attemptDir(root, "a19", { "executor-report.json": { dod: Array.from({ length: 12 }, (_, at) => ({ id: `D${at}`, status: "not_done" })) } }),
      attemptDir(root, "a20", { "executor-report.json": [1] }),
      attemptDir(root, "a21", { "events-summary.json": "[1, NaN]" }),
      attemptDir(root, "a22", { "events-summary.json": { interpretation_mentions: { a: 1 }, ambiguity_mentions: "ab" } }),
    ];
    const results = agree(dirs.flatMap((dir) => READERS.map((fn) => call(fn, [dir]))));
    const shown = (dir: number, fn: string): PyValue => valueOf(results[dir * READERS.length + READERS.indexOf(fn)]);
    expect(shown(2, "failed_checks_brief")).toBe("V02（第 50 行）");
    expect(String(shown(2, "failure_lines")).split(LF).filter((line) => line.startsWith("    ")).length).toBe(40);
    expect([shown(4, "checks_passed"), shown(5, "cut_off"), shown(6, "cut_off"), shown(7, "cut_off")])
      .toEqual([true, true, false, "AttributeError: 'list' object has no attribute 'get'"]);
    expect(shown(14, "failure_lines")).toContain("另有 2 条检查没过，日志从略。");
    expect(String(shown(17, "report_leftovers"))).toContain("- D2（not_done）：多行 说明");
    expect(String(shown(19, "report_leftovers"))).toContain("- 另有 4 项从略，见上一轮的执行报告。");
    // 落在不同的地方崩：切片、迭代、取键
    expect([shown(11, "failed_checks_brief"), shown(12, "failed_checks_brief"), shown(13, "failed_checks_brief")])
      .toEqual(["KeyError: slice(None, 160, None)", "TypeError: 'int' object is not subscriptable", "TypeError: 'bool' object is not subscriptable"]); // 3.12 起 slice 能散列
  });

  it("carryable：只认 TIMEOUT 与 NEEDS_REVIEW；补丁为空时基线要是返工提交（集合先散列）；越界不接；收了尾的要内核跑出过检查", () => {
    const root = tempDir("exec-carryable");
    const base = { "candidate.patch": "x", "scope.json": {} };
    const dirs = [
      attemptDir(root, "b0", { ...base, "state.json": state("RUNNING") }),
      attemptDir(root, "b1", { ...base, "state.json": state("TIMEOUT") }),
      attemptDir(root, "b2", { ...base, "state.json": state("NEEDS_REVIEW") }),
      attemptDir(root, "b3", { ...base, "state.json": state("NEEDS_REVIEW"), "checks/x/checks.json": { results: [{ id: "V01", status: "failed" }] } }),
      attemptDir(root, "b4", { "candidate.patch": "", "scope.json": {}, "state.json": state("TIMEOUT"), "meta.json": { base_sha: "r1" } }),
      attemptDir(root, "b5", { "candidate.patch": "", "scope.json": {}, "state.json": state("TIMEOUT"), "meta.json": { base_sha: ["r1"] } }),
      attemptDir(root, "b6", { ...base, "state.json": state("TIMEOUT"), "scope.json": { violations: [{ path: "x" }] } }),
      attemptDir(root, "b7", { "candidate.patch": "x", "state.json": state("TIMEOUT") }),
      attemptDir(root, "b8", { ...base, "state.json": state("NEEDS_REVIEW"), "events-summary.json": { final_stop_reason: "length" } }),
    ];
    const results = agree([...dirs.map((dir) => call("carryable", [dir, ["r1", "r2"]])), call("carryable", [dirs[4], []]), call("carryable", [dirs[4]])]);
    expect(results.map(valueOf)).toEqual([false, true, false, true, true, "TypeError: unhashable type: 'list'", false, false, true, false, false]);
  });
});

describe("第 ⑤g1 片：接着改从哪儿来（手写，三边逐字比）", () => {
  /** 仓库里 .agent/runs/t001-doc 下的几个 attempt。 */
  function runs(attempts: Record<string, Record<string, unknown>>): string {
    const repo = tempDir("exec-runs");
    for (const [name, files] of Object.entries(attempts)) attemptDir(join(repo, ".agent", "runs", "t001-doc"), name, files);
    return repo;
  }
  const timedOut = { "state.json": state("TIMEOUT"), "candidate.patch": "x", "scope.json": {}, "meta.json": { plan_version: 1 } };

  it("carry_source：终审退回执行端、跑满时限、截断、检查没过、上游重新交付；站主停掉的往前找；已有结论、按旧合同做的、越界的都不接", () => {
    const repo = runs({
      "attempt-001": { "state.json": state("REVISE") },
      "attempt-002": timedOut,
      "attempt-003": { "state.json": state("ABANDONED") },
      "attempt-004": { "state.json": state("NEEDS_REVIEW"), "candidate.patch": "x", "scope.json": {}, "checks/x/checks.json": { results: [{ id: "V01", status: "failed" }] } },
      "attempt-005": { "state.json": state("NEEDS_REVIEW"), "candidate.patch": "x", "scope.json": {}, "checks/x/checks.json": { results: [{ id: "V01", status: "passed" }] } },
      "attempt-006": { "state.json": state("NEEDS_REVIEW"), "candidate.patch": "x", "scope.json": {}, "events-summary.json": { final_stop_reason: "length" } },
    });
    const at = (name: string): string => join(repo, ".agent", "runs", "t001-doc", name);
    const blank = runs({ "attempt-001": { "state.json": state("TIMEOUT"), "candidate.patch": "", "scope.json": {}, "meta.json": {} } });
    const audit = (target: unknown): Record<string, unknown> => ({ verdict: "返工", target });
    const results = agree([
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-002") }, audit_post: audit("执行端") })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-002") }, audit_post: audit("门禁端、执行端") })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-002") }, audit_post: audit(["执行端"]) })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-003") } })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-004") } })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-005") } })]),
      call("carry_source", [repo, taskState({ exec: { run_dir: at("attempt-006") } })]),
      call("carry_source", [repo, taskState()]),
      call("carry_back", [repo, taskState(), null]),
      call("carry_back", [repo, taskState({ contract: { key: "k", written_version: 2 } }), "upstream"]),
      call("rework_source", [taskState({ exec: { run_dir: at("attempt-003") }, audit_post: audit("执行端") })]),
      call("rework_source", [taskState({ exec: {}, audit_post: audit("执行端") })]),
      // 补丁为空、meta 没有 base_sha：返工链里没有 commit 的条目不进集合，None 不在里面，不接
      call("carry_source", [blank, taskState({ exec: { run_dir: join(blank, ".agent", "runs", "t001-doc", "attempt-001") }, rework_chain: [{ from: "x" }, { commit: "" }] })]),
    ]);
    const shown = results.map(valueOf);
    // 站主停掉的往前找：先碰到的是截断了的 attempt-006
    expect(shown.slice(0, 8)).toEqual([[at("attempt-002"), "audit"], [at("attempt-002"), "timeout"], "TypeError: unhashable type: 'list'", [at("attempt-006"), "cutoff"],
      [at("attempt-004"), "failed"], null, [at("attempt-006"), "cutoff"], [at("attempt-006"), "upstream"]]);
    expect(shown.slice(8)).toEqual([[at("attempt-006"), "cutoff"], null, null, null, null]);
  });

  it("interrupted_attempt、failed_attempt：没有 attempt、还在办、已有结论、名字的大小写与 Unicode 数字；check_ok 只认 False、写过重派说明的不算", () => {
    const empty = tempDir("exec-none");
    const busy = runs({ "attempt-001": { "state.json": state("PASS") }, "attempt-002": { "state.json": state("RUNNING") } });
    const done = runs({ "attempt-001": { "state.json": state("RUNNING") }, "attempt-002": { "state.json": state("REVISE") } });
    const odd = runs({ "attempt-001": { "state.json": state("PASS") }, "ATTEMPT-002": { "state.json": state("NEEDS_REVIEW") }, "attempt-0003": {}, "attempt-9999": {}, [`attempt-${C(0x661, 0x662, 0x663)}`]: {} });
    const dir = join(odd, ".agent", "runs", "t001-doc", "attempt-001");
    const failed = (exec: Record<string, unknown>, notes?: unknown): PyDict => taskState({ exec, ...(notes === undefined ? {} : { retry_notes: notes }) });
    const results = agree([
      ...[empty, busy, done, odd].map((repo) => call("interrupted_attempt", [repo, taskState()])),
      call("failed_attempt", [failed({ run_dir: dir, check_ok: false })]), call("failed_attempt", [failed({ run_dir: dir, check_ok: 0 })]),
      call("failed_attempt", [failed({ run_dir: dir, check_ok: null })]), call("failed_attempt", [failed({ run_dir: `${dir}-不在`, check_ok: false })]),
      call("failed_attempt", [failed({ run_dir: dir, check_ok: false }, ["attempt-001"])]), call("failed_attempt", [failed({ run_dir: dir, check_ok: false }, "attempt-001 attempt-002")]),
      call("failed_attempt", [failed({ run_dir: dir, check_ok: false }, [1, "attempt-0012"])]), call("failed_attempt", [failed({ check_ok: false })]),
      call("failed_attempt", [failed({ run_dir: dir, check_ok: false }, 5)]), call("failed_attempt", [failed({ run_dir: dir, check_ok: false }, true)]),
    ]);
    const shown = results.map(valueOf);
    expect(String(shown[0])).toBe("HubError: 执行阶段停在 assigned，但 .agent/runs/t001-doc 下没有 attempt：执行端没开始就被打断了，让协调人重发开工");
    expect(String(shown[1]).startsWith("HubError: attempt-002 还是 RUNNING：")).toBe(true);
    expect(shown[2]).toBe("HubError: attempt-002 已经有结论（REVISE），不是被打断的 attempt");
    expect(shown[3]).toBe(join(odd, ".agent", "runs", "t001-doc", process.platform === "win32" ? "ATTEMPT-002" : "attempt-001"));
    expect(shown.slice(4)).toEqual([dir, null, null, null, null, null, dir, null,
      "TypeError: argument of type 'int' is not iterable", "TypeError: argument of type 'bool' is not iterable"]);
  });

  it("attempts_left：合同 JSON 读不出、不是字典、没有 budget、各种类型的 max_attempts_total；无穷照样崩；已领取的 attempt 算进去", () => {
    const repo = runs({ "attempt-001": { "claim/reservation.json": { timeout_seconds: 60 } } });
    const plans = (name: string, content: string | Uint8Array): void => put(repo, `.agent/plans/${name}.json`, content);
    const cases: [string, string | Uint8Array | null][] = [
      ["ok", JSON.stringify({ budget: { max_attempts_total: 3 } })], ["str", JSON.stringify({ budget: { max_attempts_total: " 3 " } })],
      ["float", JSON.stringify({ budget: { max_attempts_total: 3.9 } })], ["bool", JSON.stringify({ budget: { max_attempts_total: true } })],
      ["none", JSON.stringify({ budget: { max_attempts_total: null } })], ["list", JSON.stringify({ budget: { max_attempts_total: [] } })],
      ["word", JSON.stringify({ budget: { max_attempts_total: "x" } })], ["inf", '{"budget": {"max_attempts_total": Infinity}}'],
      ["nobudget", "{}"], ["strbudget", JSON.stringify({ budget: "abc" })], ["array", "[1]"], ["bad", "{"], ["missing", null],
      ["badutf8", Uint8Array.from([0x7b, 0xff, 0x7d])], ["deep", `${"[".repeat(100_000)}${"]".repeat(100_000)}`],
    ];
    for (const [name, content] of cases) if (content !== null) plans(name, content);
    const results = agree(cases.map(([name]) => call("attempts_left", [repo, taskState({ contract: { key: name } })])));
    expect(results.map(valueOf)).toEqual([2n, 2n, 2n, 0n, null, null, null, "OverflowError: cannot convert float infinity to integer", null, null, null, null, null,
      null, "RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string"]); // 坏的 UTF-8 是 ValueError，接住；嵌套太深照样崩
  });
});

describe("第 ⑤g1 片：返工节与重派节的文字（手写，三边逐字比）", () => {
  it("rework_section：每种 why 乘跑满时限、检查过没过、有没有剩余工作、搬没搬过；阻塞项与剩余工作的怪类型", () => {
    const root = tempDir("exec-section");
    const passed = attemptDir(root, "attempt-001", { "checks/x/checks.json": { results: [{ id: "V01", status: "passed" }] } });
    const notRun = attemptDir(root, "attempt-002", {});
    const requests: ProbeRequest[] = [];
    for (const previous of [passed, notRun]) {
      for (const why of ["audit", "timeout", "cutoff", "failed", "upstream", "x"]) {
        for (const timedOut of [false, true]) {
          requests.push(call("rework_section", [previous, "abc123", "  阻塞一  ", 2, why, timedOut, timedOut, timedOut ? "" : `### 剩下的${LF}`]));
        }
      }
    }
    requests.push(call("rework_section", [notRun, "abc", null, 1, "failed", false, false, ""]));
    requests.push(call("rework_section", [notRun, 1, 0, 1, "upstream", false, false, ""]));
    requests.push(call("rework_section", [notRun, "abc", ["x"], 1]));
    requests.push(call("rework_section", [notRun, "abc", "b", 1, "audit", false, false, ["x"]]));
    requests.push(call("rework_section", [notRun, "abc", "b", "2"]));
    const shown = agree(requests).map(valueOf);
    expect(String(shown[3])).toContain("内核随后在这个候选上重跑了合同的全部检查，都过了"); // timeout、跑满时限、检查都过了
    expect(String(shown.at(-3))).toBe("AttributeError: 'list' object has no attribute 'strip'");
    expect(String(shown.at(-2)).startsWith("TypeError: sequence item ")).toBe(true);
    expect(shown.at(-1)).toBe("TypeError: %d format: a real number is required, not str");
  });

  it("retry_section：ts 的执行记录与执行端自述的各种值，附上一轮没过的检查与范围违规", () => {
    const root = tempDir("exec-retry");
    const dir = attemptDir(root, "attempt-003", {
      "checks/x/checks.json": { results: [{ id: "V01", status: "failed", reason: "exit 1" }] }, "scope.json": { violations: [{ path: "x.py", kind: "M", detail: "越界" }] },
      "executor-report.json": { executor_status: "blocked" },
    });
    const bare = attemptDir(root, "attempt-004", { "executor-report.json": { executor_status: 0 } });
    const results = agree([
      call("retry_section", [dir, taskState({ exec: { check_exit: 1, scope_violations: 1, status: "NEEDS_REVIEW" } }), 1]),
      call("retry_section", [bare, taskState({ exec: { check_exit: 1.5, scope_violations: [1], status: null } }), 2]),
      call("retry_section", [bare, taskState({ exec: {} }), true]),
    ]);
    expect(String(valueOf(results[0])).startsWith(`## Retry（重派第 1 次，内核追加）${LF}${LF}- 上一轮 attempt-003 没过内核核验：check --fresh 退出码 1，范围违规 1 条`)).toBe(true);
    expect(String(valueOf(results[1]))).toContain("执行端自述 未知。");
  });

  it("add_modified_files：同行写法（逗号、全角逗号、顿号，后面的空白都吃掉）、列表写法、无与 none 与 []、找不到 Scope 或那一行、CRLF", () => {
    const scope = (row: string, more = ""): string => lines("# TASK", "", "## Scope", row, "- allowed_new_files: x", more, "## Goal", "- allowed_modified_files: 不在 Scope 里");
    const texts = [
      scope(`- allowed_modified_files: a.py, ${BT}b.py${BT}，c.py、${C(9)}d.py,${C(0x3000)}e.py`),
      lines("## Scope", "- allowed_modified_files:", "  - a.py", `  * ${BT}b.py${BT}  `, "-  not a list item", "  - after"),
      scope("- allowed_modified_files: 无"), scope("* allowed_modified_files :  NONE"), scope("- allowed_modified_files: []"), scope("- allowed_modified_files:"),
      lines("## Goal", "- allowed_modified_files: a.py"), lines("##  Scope  ", "- allowed_new_files: x"), lines("## scope", "- allowed_modified_files: a.py"),
      lines("##Scope", "- allowed_modified_files: a.py"), [`## Scope${CR}`, `- allowed_modified_files: a.py, b.py${CR}`, `## Goal${CR}`, ""].join(LF),
      lines("## Scope", "- allowed_modified_files:", `  - a.py${CR}`, `  - b.py${C(0x2028)}`, "- allowed_modified_files: second"),
      lines(`${C(9)}  ## Scope `, "- allowed_modified_files: a.py"),
    ];
    const results = agree(texts.map((text) => call("add_modified_files", [text, ["c.py", "f.py", "f.py"]])));
    const shown = results.map(valueOf) as [string, string[]][];
    expect(shown[0]?.[0]).toContain(lines("- allowed_modified_files:", "  - a.py", "  - b.py", "  - c.py", "  - d.py", "  - e.py", "  - f.py", "  - f.py"));
    expect(shown.at(-1)?.[1]).toEqual([]); // 标题前面的空白先去掉
    expect(shown.slice(6, 10).map((item) => item[1])).toEqual([["合同里找不到 ## Scope 一节"], ["合同 Scope 里找不到 allowed_modified_files"], ["合同里找不到 ## Scope 一节"], ["合同里找不到 ## Scope 一节"]]);
  });
});

describe("第 ⑤g1 片：门禁有错的说法与 JEV 的标注（手写，三边逐字比）", () => {
  const SAYINGS = [
    "门禁测试有错", "门禁端的缺陷", "门禁用例写错了", "门禁问题", "门禁", "探针泄漏", "探针在第三条用例里有错", "探针里面的第十三个断言之后有错", "任何实现都过不了",
    "所有实现都", "Gate Test Defect", "GATE BUG", "gate  bug", "the gate is wrong", "gate. wrong", "gate my wrong", "gatekeeper is wrong",
    `gate${"x".repeat(60)}wrong`, `gate${"x".repeat(61)}wrong`, "Gate can't pass", "gate cant pass", "gate cannot pass", "gate is buggy", "gate debug",
    "gate the app wrong", "gate the apple wrong", "gate our impl is wrong", "gate implementations wrong", "gate; impossible", "gate contradicts", `gate${LF}wrong`,
  ];

  it("gate_claims：局限、未决问题、合同矛盾里的字符串、带 text 的字典、别的值照 str；字段不是列表时照 Python 迭代", () => {
    const items: unknown[] = [...SAYINGS, { text: "门禁有错" }, { text: "" }, { note: "门禁有错" }, 5, null, ["门禁有错"]];
    const results = agree([
      call("gate_claims", [{ limitations: items, unresolved_questions: SAYINGS.slice(0, 5), contract_conflicts: [{ text: "gate bug" }] }]),
      call("gate_claims", [{ limitations: "门禁有错" }]), call("gate_claims", [{ limitations: { 门禁有错: 1 } }]), call("gate_claims", [{}]),
      call("gate_claims", [{ limitations: 3 }]), call("gate_claims", [[1]]),
    ]);
    expect((valueOf(results[0]) as string[]).includes("{'note': '门禁有错'}")).toBe(true);
    expect(results.slice(1).map(valueOf)).toEqual([[], ["门禁有错"], [], "TypeError: 'int' object is not iterable", "AttributeError: 'list' object has no attribute 'get'"]);
  });

  it("unreported_gate_claims：思考摘录（英文与中文的说法、空白压成一个、不是字典的跳过），读不出就是空", () => {
    const root = tempDir("exec-thinking");
    const mentions = SAYINGS.map((excerpt) => ({ excerpt: `  ${excerpt.replace(" ", `${LF}${C(9)}`)} ` }));
    const dirs = [
      attemptDir(root, "c0", { "events-summary.json": { interpretation_mentions: mentions, ambiguity_mentions: ["x", { excerpt: 5 }, { excerpt: "gate wrong" }, { excerpt: null }] } }),
      attemptDir(root, "c1", { "events-summary.json": "{" }),
      attemptDir(root, "c2", { "events-summary.json": [1] }),
    ];
    const shown = agree(dirs.map((dir) => call("unreported_gate_claims", [dir]))).map(valueOf);
    expect((shown[0] as string[]).at(-1)).toBe("（思考摘录，没写进报告）gate wrong");
    expect(shown.slice(1)).toEqual([[], "AttributeError: 'list' object has no attribute 'get'"]);
  });

  it("jev_flag：noul 与 score 的阈值边界、缺省阈值、判据的几种形状、半数取偶的下标、NaN 与无穷、怪类型", () => {
    const noulQ = { type: "noul", criteria: { true: "改了范围外的文件" } };
    const scoreQ = { type: "score", criteria: ["无", "低", "中", "高"] };
    const thresholds = { review: 0.35, action: 0.7, severity_action: 2 };
    const requests = [
      ...[0.34, 0.35, 0.69, 0.7, Number.NaN, "0.5", true].map((noul) => call("jev_flag", [{ type: "noul", noul }, noulQ, thresholds])),
      call("jev_flag", [{ type: "noul" }, noulQ, thresholds]), call("jev_flag", [{ type: "noul", noul: null }, noulQ, thresholds]),
      call("jev_flag", [{ type: "noul", noul: 0.9 }, noulQ, {}]), call("jev_flag", [{ type: "noul", noul: 0.9 }, noulQ, { action: "x" }]),
      call("jev_flag", [{ type: "noul", noul: 0.9 }, { criteria: { true: "" } }, thresholds]), call("jev_flag", [{ type: "noul", noul: 0.9 }, { criteria: ["a"] }, thresholds]),
      ...[1.0, 2.0, 2.5, 3.5, -0.5, 10.0, "3", Number.NaN, Number.POSITIVE_INFINITY].map((score) => call("jev_flag", [{ type: "score", score }, scoreQ, thresholds])),
      call("jev_flag", [{ type: "score", score: 3.0 }, { criteria: { 3: "x" } }, thresholds]), call("jev_flag", [{ type: "other" }, noulQ, thresholds]),
      call("jev_flag", [[1], noulQ, thresholds]), call("jev_flag", [{ type: "noul", noul: 0.9 }, [1], thresholds]), call("jev_flag", [{ type: "noul", noul: 0.9 }, noulQ, [1]]),
    ];
    const shown = agree(requests).map(valueOf);
    expect(shown.slice(0, 4)).toEqual(["", " ——【留意】判据：改了范围外的文件", " ——【留意】判据：改了范围外的文件", " ——【需关注】判据：改了范围外的文件"]);
    expect(shown.slice(13, 17)).toEqual(["", " ——【需关注】判据：中", " ——【需关注】判据：中", " ——【需关注】"]); // 2.5 取偶落在 2，3.5 落在 4（越界，没有判据）
    expect(shown.slice(20, 22)).toEqual(["ValueError: cannot convert float NaN to integer", "OverflowError: cannot convert float infinity to integer"]);
  });
});

describe("第 ⑤g1 片：修改时刻与真 git", () => {
  it("returned_blockers：candidate.patch 的修改时刻换成秒（同一秒算、前一秒不算、微秒进到下一秒）；只认终审退回执行端的；阻塞项的怪类型", () => {
    const root = tempDir("exec-blockers");
    const sec = 1_767_323_045n; // 2026-01-02T03:04:05Z
    const previous = (name: string, nsec: bigint): string => {
      const dir = attemptDir(root, name, { "candidate.patch": "x" });
      const real = runProbe(PYTHON, { op: "mtime.real", files: [[join(dir, "candidate.patch"), String(sec * 1_000_000_000n + nsec)]] });
      expect(real.ok).toBe(true);
      return dir;
    };
    const plain = previous("attempt-001", 250_000_000n);
    const carried = previous("attempt-002", 999_999_900n); // 微秒取整满 1e6：进到 03:04:06
    const entry = (at: unknown, blockers: unknown, extra: Record<string, unknown> = {}): Record<string, unknown> =>
      ({ stage: "7-audit-post", verdict: "返工", target: "执行端", at, blockers, ...extra });
    const history = (items: unknown): PyDict => taskState({ audit_history: items });
    const all = [entry("2026-01-02T03:04:04Z", "前一秒"), entry("2026-01-02T03:04:05Z", "同一秒"), entry("2026-01-02T03:04:06Z", "后一秒"),
      entry("2026-01-02T03:04:07Z", "不退执行端", { target: "门禁端" }), entry("2026-01-02T03:04:08Z", "一审", { stage: "4-audit-pre" })];
    const requests = [
      call("returned_blockers", [history(all), plain]), call("returned_blockers", [history(all.slice(0, 2)), plain]), call("returned_blockers", [history(all.slice(0, 2)), carried]),
      call("returned_blockers", [history(all.slice(0, 1)), plain]), call("returned_blockers", [history([entry("2026-01-02T03:04:09Z", null)]), plain]),
      call("returned_blockers", [history([entry("2026-01-02T03:04:09Z", ["x"])]), plain]), call("returned_blockers", [history([entry(null, "没时刻")]), plain]),
      call("returned_blockers", [history([entry("2026-01-02T03:04:09Z", "两处", { target: "门禁端、执行端" })]), plain]),
      call("returned_blockers", [history("ab"), plain]), call("returned_blockers", [taskState(), plain]),
    ];
    const shown = agree(requests).map(valueOf);
    expect(shown.slice(0, 4)).toEqual(["后一秒", "同一秒", "", ""]);
    expect(shown.slice(4)).toEqual(["", ["x"], "", "两处", "AttributeError: 'str' object has no attribute 'get'", ""]);
  });

  it("empty_commit：同树的单父提交才算；根提交、合并提交、正常提交、不存在的提交都不算", () => {
    const { repo, head } = newRepo("exec-empty", { "a.txt": "a" });
    git(repo, "commit", "-q", "--allow-empty", "-m", "空的");
    const empty = git(repo, "rev-parse", "HEAD");
    put(repo, "b.txt", "b");
    git(repo, "add", "b.txt");
    git(repo, "commit", "-q", "-m", "加 b");
    const normal = git(repo, "rev-parse", "HEAD");
    git(repo, "checkout", "-q", "-b", "side", head);
    put(repo, "c.txt", "c");
    git(repo, "add", "c.txt");
    git(repo, "commit", "-q", "-m", "加 c");
    git(repo, "checkout", "-q", "-");
    git(repo, "merge", "-q", "--no-edit", "side");
    const merge = git(repo, "rev-parse", "HEAD");
    const shown = agree([head, empty, normal, merge, "0".repeat(40), "nope"].map((sha) => call("empty_commit", [repo, sha]))).map(valueOf);
    expect(shown).toEqual([false, true, false, false, false, false]);
  });
});

describe("第 ⑤g1 片：按种子随机换类型（三边比交回值，崩溃比类型与文字）", () => {
  it("attempt 目录里的执行报告、scope.json、checks.json、events-summary.json、report-status.json、meta.json、state.json 可以是任何 JSON 值", () => {
    const next = prng(57);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
    const ATOMS: unknown[] = [null, true, false, 0, 1, -1, 1.5, "", "x", "passed", "failed", "done", "length", "json_ok", "门禁有错", "gate bug", [], {}];
    const value = (depth = 0): unknown => {
      const roll = next();
      if (depth > 1 || roll < 0.55) return pick(ATOMS);
      if (roll < 0.78) return Array.from({ length: Math.floor(next() * 3) }, () => value(depth + 1));
      return Object.fromEntries(["id", "status", "log", "reason", "text", "note", "excerpt", "path", "kind", "detail"].filter(() => next() < 0.35).map((key) => [key, value(depth + 1)]));
    };
    const maybe = (fallback: () => unknown, odd = 0.2): unknown => (next() < odd ? value() : fallback());
    const record = (keys: [string, () => unknown][]): unknown => maybe(() => Object.fromEntries(keys.filter(() => next() < 0.7).map(([key, make]) => [key, make()])), 0.1);
    const list = (item: () => unknown): (() => unknown) => () => maybe(() => Array.from({ length: Math.floor(next() * 4) }, item), 0.2);
    const root = tempDir("exec-random");
    const requests: ProbeRequest[] = [];
    for (let at = 0; at < 60; at += 1) {
      const files: Record<string, unknown> = {
        "state.json": record([["state", () => pick(["TIMEOUT", "NEEDS_REVIEW", "RUNNING", 1])]]),
        "scope.json": record([["violations", list(() => record([["path", value], ["kind", value], ["detail", value]]))], ["files", value]]),
        "executor-report.json": record([["executor_status", value], ["dod", list(() => record([["id", value], ["status", () => pick(["done", "not_done", null])], ["note", value]]))],
          ["limitations", list(value)], ["unresolved_questions", list(value)], ["contract_conflicts", list(value)]]),
        "events-summary.json": record([["final_stop_reason", () => pick(["length", "stop", null])], ["interpretation_mentions", list(() => record([["excerpt", value]]))],
          ["ambiguity_mentions", list(value)]]),
        "report-status.json": record([["status", () => pick(["json_ok", "missing", 0])]]),
        "meta.json": record([["base_sha", value], ["plan_version", value]]),
      };
      if (next() < 0.7) files["checks/x/checks.json"] = record([["results", list(() => record([["id", value], ["status", () => pick(["passed", "failed", null])], ["reason", value], ["log", value]]))]]);
      if (next() < 0.7) files["candidate.patch"] = next() < 0.5 ? "" : "x";
      const dir = attemptDir(root, `r${at}`, files);
      for (const fn of READERS) requests.push(call(fn, [dir]));
      requests.push(call("carryable", [dir, ["x", "r1"]]));
      requests.push(call("retry_section", [dir, taskState({ exec: { check_exit: 1 } }), at]));
      requests.push(call("gate_claims", [files["executor-report.json"]]));
    }
    const { python, mismatches } = runAgreeing(requests);
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    const crashed = python.filter((result) => !result.ok);
    expect(python.length - crashed.length, "不是一路崩到底").toBeGreaterThan(300);
    expect(new Set(crashed.map((result) => result["error"])).size, "崩溃的种类").toBeGreaterThan(2);
  });
});
