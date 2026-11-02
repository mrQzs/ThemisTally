// 第 ⑤g2 片的手写对照（采样那份在 hub-runexec.contract.test.ts）：临时仓库上搭好场景，三边各自先原地放回再跑，交回值、ts、文件、账本、
// git 状态逐字比。样本没走到的分支在这里：
//   - dispatch_attempt：找 attempt 路径的正则（正斜杠、反斜杠、Unicode 数字、两处取第一处、大写）；run 的时限回落 1800 的几种，照样崩的几种；
//   - finish_exec：执行报告、scope.json、observations.json 是怪类型时的文字与崩法；
//   - final_audit_turn 与 write_review：目录的原始次序、同一秒、跳过的几种、照样崩的两种，复审记录已在时加 utc_compact；
//   - rebase_candidate（真 git：没有 tree、差异为空、diff 出错、apply 冲突、超过 1 MiB 的二进制改动）、start_rework、start_retry、
//     ensure_rework_scope、rework_added_files 的各条分支；
//   - run_exec：预算用完；落地锁由另一个进程真的拿着（等锁时限设短）；持有者不在了就接管；收尾删执行标记出错照样吞掉；
//   - run_jev：真会话（传输层换到本机的假端点、只给假 key），钉不住的延时与时刻打占位。
// 不写转义序列。
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, realpathSync, utimesSync } from "node:fs";
import { type IncomingMessage, type ServerResponse, createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { basename, join } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { DEFAULT_MODEL } from "@themis/config/decisions";
import { EXECUTOR } from "@themis/hub/constants";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, type Impl, type ProbeRequest, type ProbeResult, REPO, seededBytes } from "./harness.ts";
import { AT, C, LF, type Scene, agreeFlow, flow, kernelPython, pd, py, returned, scene, scrubResult, text, tsAfter, written } from "./flow-fixtures.ts";
import { git, put, removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const BS = C(92);
const lines = (...items: string[]): string => [...items, ""].join(LF);
const GATE = "tests/test_gate_t001_baseline.py";
const BASE_FILES = { "src/doc.py": lines("def title():", "    return 'old'"), [GATE]: lines("def test_title():", "    assert False") };
const KEY = "t001-doc.v1";
const V1 = { version: 1, key: KEY, md: ".agent/plans/t001-doc.v1.md", json: ".agent/plans/t001-doc.v1.json", written_version: 1 };
const RUN = ".agent/runs/t001-doc/attempt-001";
/** 钉住的时刻（flow-fixtures 的 PIN）照 utc_compact 写出来的样子。 */
const STAMP = "20261101T000000000000Z";
/** 过得了 contract_requirements 的合同 JSON（derive-json 注入时由场景写好）。 */
const PASSING_JSON = JSON.stringify({
  scope: { allowed_modified_files: ["src/doc.py"], forbidden_paths: ["tests/test_gate_t001_*.py"] },
  checks: [{ id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"], expect_on_base: "fail", required: true }],
  executor: { provider: EXECUTOR[0], model: EXECUTOR[1], thinking: EXECUTOR[2] }, authorization: { integration: ["local_branch", "merge"] },
  budget: { max_attempts_total: 6, max_wall_seconds_per_attempt: 600 },
});
const RETRY = (n: number): string[] => [`## Retry（重派第 ${n} 次，内核追加）`, "", `- 第 ${n} 次的失败。`, ""];
function contractMd(head: string, scope: string[] = ["## Scope", "- allowed_modified_files: src/doc.py", "- allowed_new_files: 无", ""], tail: string[] = []): string {
  return lines("# TASK: t001-doc", "", "## Identity", "- plan_version: 1", `- base_sha: ${head}`, "", "## Goal", "title() 交回 new。", "", ...scope, ...tail);
}

function execTs(sc: Scene, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  ts.set("contract", py(V1));
  ts.set("oracle", py({ sha: sc.head, files: [GATE] }));
  for (const [key, value] of Object.entries(extra)) ts.set(key, value instanceof Map ? (value as PyDict) : py(value));
  return ts;
}
/** Python 的 resolve() 把短名展开成长名：调度器拿到的 attempt 目录是解析过的。 */
const resolved = (sc: Scene, rel: string): string => join(realpathSync.native(sc.repo), ...rel.split("/"));
const revalidate = (key = KEY): unknown[] => [pd(["derive-json", key, "--force", "--title", "改文档"], 0, "ok"), pd(["validate", key], 0, "ok")];
const errorOf = (state: Record<string, unknown> | undefined): unknown => (state?.["result"] as Record<string, unknown>)["error"] ?? null;
/** 注入核对过了（手写的记录与两边的调用对得上）：两边都报 INJECTION_* 时比较也会相同，这里另外拦住。 */
function injectedCleanly(states: readonly Record<string, unknown>[]): void {
  expect(states.map(errorOf).filter((error) => String(error).startsWith("INJECTION_")), "注入的记录与调用对不上").toEqual([]);
}

/** 在 parent 上提交 files，交回新提交；HEAD 照旧留在分离的状态，场景最后再切回去。 */
function commitOn(repo: string, parent: string, files: Record<string, string | Uint8Array>, message: string): string {
  git(repo, "checkout", "-q", "--detach", parent);
  for (const [rel, content] of Object.entries(files)) put(repo, rel, content);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "--allow-empty", "-m", message);
  return git(repo, "rev-parse", "HEAD");
}

describe("第 ⑤g2 片：dispatch_attempt（手写）", () => {
  const wall = (value: string): string => `{"budget": {"max_wall_seconds_per_attempt": ${value}}}`;
  const dispatchScene = (contract: string | Uint8Array | null, rel = RUN): Scene => scene(BASE_FILES, (repo) => {
    if (contract !== null) put(repo, ".agent/plans/t001-doc.v1.json", contract);
    put(repo, `${rel}/state.json`, JSON.stringify({ state: "NEEDS_REVIEW" }));
  }, false);
  const dispatched = (sc: Scene, out: string, runTimeout: number | null, rel = RUN, runCode = 0): ProbeRequest => {
    const inner = [pd(["prepare", KEY], 0, out, 1800)];
    if (runTimeout !== null) inner.push(pd(["run", resolved(sc, rel)], runCode, "跑完了", runTimeout), pd(["check", resolved(sc, rel), "--fresh"], 0, "检查通过", 3600));
    return flow("dispatch_attempt", sc, [execTs(sc)], { inner });
  };

  it("找 attempt 路径：正斜杠、反斜杠、混着写、两处取第一处、Unicode 数字、四位数只取前三位；大写与没有路径时是 prepare 失败，退出码非零也是", () => {
    const arabic = `.agent/runs/t001-doc/attempt-${C(0x661, 0x662, 0x663)}`;
    const cases: [string, string, string | null][] = [
      [`attempt 目录：${RUN}${LF}`, RUN, RUN], [`attempt 目录：${RUN.split("/").join(BS)}`, RUN, RUN],
      [`.agent${BS}runs/t001-doc${BS}attempt-001 已就绪`, RUN, RUN], [`${RUN} 与 .agent/runs/t001-doc/attempt-002`, RUN, RUN],
      [`准备好了：${arabic}`, arabic, arabic], [".agent/runs/t001-doc/attempt-0012", RUN, RUN],
      [".agent/runs/T001-doc/attempt-001", RUN, null], ["准备好了", RUN, null],
    ];
    const requests = cases.map(([out, rel, found]) => dispatched(dispatchScene(PASSING_JSON, rel), out, found === null ? null : 1500, found ?? rel));
    const failed = dispatchScene(PASSING_JSON);
    requests.push(flow("dispatch_attempt", failed, [execTs(failed)], { inner: [pd(["prepare", KEY], 1, `${RUN}${LF}预检没过`, 1800)] }));
    const states = agreeFlow(requests);
    injectedCleanly(states);
    expect(states.map((state) => (returned(state) as PyDict).get("摘要"))).toEqual([
      ...cases.map(([, , found]) => (found === null ? "prepare 失败，执行端没有开始" : "执行端自述 未知（没有可读的执行报告）；DoD：（报告没有 DoD）；候选改动 0 个文件")),
      "prepare 失败，执行端没有开始",
    ]);
  }, 600_000);

  it("派遣走通的整条路：prepare 成功、记 exec.started、run 的时限照合同、接着 finish_exec，run 的退出码 0 与非零都记进 run_exit", () => {
    const [ok, killed] = [dispatchScene(PASSING_JSON), dispatchScene(PASSING_JSON)];
    const states = agreeFlow([dispatched(ok, `${RUN}${LF}`, 1500), dispatched(killed, `${RUN}${LF}`, 1500, RUN, 124)]);
    injectedCleanly(states);
    const exec = states.map((state) => tsAfter(state).get("exec") as PyDict);
    expect(exec.map((item) => [item.get("run_dir"), item.get("run_exit"), item.get("check_ok")])).toEqual([
      [resolved(ok, RUN), 0n, true], [resolved(killed, RUN), 124n, true],
    ]);
    const events = (state: Record<string, unknown> | undefined): string[] => Buffer.from(String(state?.["ledger"]), "base64").toString("utf8").split(LF)
      .filter((line) => line).map((line) => String((JSON.parse(line) as Record<string, unknown>)["event"]));
    expect(events(states[0])).toEqual(["exec.started", "exec.finished"]);
    expect((tsAfter(states[0]).get("contract") as PyDict).get("dispatched")).toBe(true);
  }, 600_000);

  it("run 的时限：读不出合同、budget 的各种写法、int() 认与不认的值（ValueError、TypeError 回落 1800）", () => {
    const cases: [string | Uint8Array | null, number][] = [
      [null, 1800], ["{bad", 1800], [Buffer.from([0x7b, 0xff, 0x7d]), 1800], ["{}", 2100], [`{"budget": null}`, 2100], [`{"budget": 0}`, 2100],
      [`{"budget": ""}`, 2100], [`{"budget": {}}`, 2100], [wall("300"), 1200], [wall(`"300"`), 1200], [wall(`" 300 "`), 1200], [wall(`"3_00"`), 1200],
      [wall(`"${C(0xff13, 0xff10, 0xff10)}"`), 1200], [wall("300.7"), 1200], [wall("1e3"), 1900], [wall("true"), 901], [wall("false"), 900], [wall("-1000"), -100],
      [wall(`"abc"`), 1800], [wall("null"), 1800], [wall("[1]"), 1800], [wall(`{"x": 1}`), 1800], [wall("NaN"), 1800], [wall(`"1.5"`), 1800],
    ];
    const states = agreeFlow(cases.map(([contract, budget]) => dispatched(dispatchScene(contract), `${RUN}${LF}`, budget)));
    injectedCleanly(states);
    expect(states.map(errorOf)).toEqual(cases.map(() => null));
  }, 600_000);

  it("照样崩的：合同 JSON 是列表，budget 是字符串、列表、true，时限是 Infinity 或 1e400，嵌套太深；崩之前已经记了派遣过", () => {
    const deep = `{"budget": ${"[".repeat(5000)}${"]".repeat(5000)}}`;
    const cases: [string, string][] = [
      ["[]", "AttributeError"], [`{"budget": "abc"}`, "AttributeError"], [`{"budget": [1]}`, "AttributeError"], [`{"budget": true}`, "AttributeError"],
      [wall("Infinity"), "OverflowError"], [wall("1e400"), "OverflowError"], [deep, "RecursionError"],
    ];
    const states = agreeFlow(cases.map(([contract]) => dispatched(dispatchScene(contract), `${RUN}${LF}`, null)));
    expect(states.map(errorOf)).toEqual(cases.map(([, error]) => error));
    expect(states.map((state) => (tsAfter(state).get("contract") as PyDict).get("dispatched"))).toEqual(cases.map(() => true));
  }, 600_000);
});

describe("第 ⑤g2 片：finish_exec（手写）", () => {
  // 采样已经管着的（hub-runexec.contract.test.ts）：执行报告里说门禁有错（test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner）、
  // 只在思考里说（test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report）、跑满时限一处没改
  // （test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner）、候选没收上来（test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner）、
  // 没过的检查与候选数（test_exec_letter_counts_the_candidate_and_names_the_failed_checks）、没有待决项写“无”
  // （test_the_executor_letter_says_none_when_nothing_is_pending）。这里补它们没走到的边：截到 8 条、每条 600 字，思考摘录取前 3 处、
  // 每处 240 字，输出被截断时的自述，预算读不到，检查过了但有范围违规（用例的 attempt_dir 从没传过违规），以及怪类型。
  it("门禁有错的两种来源截断：报告里 10 条只留 8 条、每条 600 字；思考摘录 5 处只摘 3 处、每处 240 字；输出被截断时的自述；预算是字符串读不到", () => {
    const long = (n: number): string => `第 ${n} 条：门禁有错，${"长".repeat(700)}`;
    const report = JSON.stringify({ limitations: Array.from({ length: 10 }, (_, n) => ({ text: long(n) })), unresolved_questions: ["门禁的问题"] });
    const excerpt = (n: number): Record<string, unknown> => ({ excerpt: `the gate test   is wrong ${n} ${"x".repeat(300)}` });
    const summary = JSON.stringify({ interpretation_mentions: [excerpt(1), "x", excerpt(2), excerpt(3)], ambiguity_mentions: [excerpt(4), { excerpt: "no claim" }, excerpt(5)] });
    const cases: [Record<string, string>, number][] = [
      [{ "executor-report.json": report }, 1],
      [{ "events-summary.json": summary }, 1],
      [{ "events-summary.json": JSON.stringify({ final_stop_reason: "length" }), "report-status.json": JSON.stringify({ status: "truncated" }) }, 1],
    ];
    const requests = cases.map(([files, code], index) => {
      const sc = scene(BASE_FILES, (repo) => {
        put(repo, ".agent/plans/t001-doc.v1.json", index === 2 ? `{"budget": {"max_attempts_total": "abc"}}` : `{"budget": {"max_attempts_total": 4}}`);
        for (const [name, content] of Object.entries(files)) put(repo, `${RUN}/${name}`, content);
      }, false);
      const runDir = join(sc.repo, ...RUN.split("/"));
      return flow("finish_exec", sc, [execTs(sc), runDir, 1], { inner: [pd(["check", runDir, "--fresh"], code, "检查没过", 3600)] });
    });
    const states = agreeFlow(requests);
    injectedCleanly(states);
    const claims = (tsAfter(states[0]).get("exec") as PyDict).get("gate_claims") as string[];
    expect([claims.length, claims.map((claim) => [...claim].length)]).toEqual([8, Array.from({ length: 8 }, () => 600)]);
    const thinking = returned(states[1]) as PyDict;
    expect(String(thinking.get("偏离"))).toContain("执行器没交报告，思考里说门禁有错（共 5 处，摘录前 3 处）：（思考摘录，没写进报告）the gate test is wrong 1 ");
    expect(String((returned(states[2]) as PyDict).get("摘要"))).toContain("执行端自述 没交执行报告（模型最后一条输出被截断：stopReason=length）");
    expect(String((returned(states[2]) as PyDict).get("验证"))).not.toContain("合同预算还剩");
    expect(String((returned(states[0]) as PyDict).get("验证"))).toContain("合同预算还剩");
  }, 600_000);

  it("执行报告、scope.json、observations.json 是怪类型：文字照 Python，崩的照 Python 崩；检查过了但有范围违规不算通过", () => {
    const cases: [Record<string, string>, number, string | null][] = [
      [{ "scope.json": "[]" }, 0, "AttributeError"], [{ "scope.json": `{"violations": 5}` }, 0, "TypeError"], [{ "executor-report.json": "[1]" }, 0, "AttributeError"],
      [{ "observations.json": `{"collect_errors": "abc"}` }, 0, null], [{ "observations.json": `{"collect_errors": {"a": 1}}` }, 0, "KeyError"],
      [{ "observations.json": `{"collect_errors": 5}` }, 0, "TypeError"], [{ "observations.json": `{"collect_errors": [5]}` }, 0, "TypeError"],
      [{ "observations.json": `{"collect_errors": [{"a": 1}]}` }, 0, "KeyError"], [{ "observations.json": `{"collect_errors": [["x", 1]]}` }, 0, null],
      [{ "observations.json": `{"collect_errors": [null]}` }, 0, "TypeError"], [{ "observations.json": JSON.stringify({ collect_errors: ["长".repeat(400)] }) }, 0, null],
      [{
        "executor-report.json": JSON.stringify({
          executor_status: { a: 1 }, interpretations: ["一", { text: "二" }, { text: "" }, 3], limitations: "ab", dod: [{ id: 1, status: "done" }, "x", { id: "D2" }],
          contract_conflicts: [{ text: "矛盾" }], unresolved_questions: [], changed_files: [1, 2],
        }),
        "scope.json": `{"files": "x", "violations": []}`,
      }, 0, null],
      [{ "state.json": `{"state": "TIMEOUT"}`, "scope.json": `{"files": []}` }, 1, null],
      [{ "executor-report.json": "{}", "state.json": `{"state": "NEEDS_REVIEW"}` }, 2, null],
      [{ "state.json": `{"state": "NEEDS_REVIEW"}`, "scope.json": JSON.stringify({ violations: ["src/x.py 不在范围内"], files: [] }) }, 0, null],
    ];
    const requests = cases.map(([files, code], index) => {
      const sc = scene(BASE_FILES, (repo) => {
        if (index === 11) put(repo, ".agent/plans/t001-doc.v1.json", `{"budget": {"max_attempts_total": 3}}`);
        for (const [name, content] of Object.entries(files)) put(repo, `${RUN}/${name}`, content);
      }, false);
      const runDir = join(sc.repo, ...RUN.split("/"));
      return flow("finish_exec", sc, [execTs(sc), runDir, code === 1 ? null : 0], { inner: [pd(["check", runDir, "--fresh"], code, `检查输出 ${code}`, 3600)] });
    });
    const states = agreeFlow(requests);
    injectedCleanly(states);
    expect(states.map(errorOf)).toEqual(cases.map(([, , error]) => error));
    const odd = returned(states[11]) as PyDict;
    expect([odd.get("摘要"), odd.get("验证"), odd.get("偏离"), odd.get("需协调人决定")]).toEqual([
      "执行端自述 {'a': 1}；DoD：1:done、D2:None；候选改动 2 个文件", "内核 check --fresh：通过；范围违规 0 条；attempt 状态 UNKNOWN；合同预算还剩 3 次 attempt",
      "解读：一；二；{'text': ''}；3；局限：a；b", "合同矛盾：矛盾",
    ]);
    expect((returned(states[8]) as PyDict).get("需协调人决定")).toContain("调度器收集出错：['x', 1]");
    expect((returned(states[12]) as PyDict).get("需协调人决定")).toContain("这一轮跑满时限、候选一处没改");
    const violated = tsAfter(states[14]).get("exec") as PyDict;
    expect([violated.get("check_ok"), violated.get("scope_violations"), String((returned(states[14]) as PyDict).get("验证")).includes("范围违规 1 条")])
      .toEqual([false, 1n, true]);
  }, 600_000);
});

describe("第 ⑤g2 片：final_audit_turn 与 write_review（手写）", () => {
  const TURNS = ".agent/mailbox/turns/audit-sonnet";
  /** 补丁的修改时刻钉在 2026-10-31T12:00:00.4Z（避开整秒），since 是 2026-10-31T12:00:00Z。 */
  const MARK = Date.UTC(2026, 9, 31, 12, 0, 0, 400) / 1000;
  const record = (finished: unknown, extra: Record<string, unknown> = {}): string => JSON.stringify({ session_key: "T001-7-audit-post", finished_at: finished, ...extra });
  const turnScene = (turns: Record<string, string | Uint8Array | null>, patch = true, extra: (repo: string) => void = () => undefined): Scene => scene(BASE_FILES, (repo) => {
    for (const [name, content] of Object.entries(turns)) {
      if (content === null) mkdirSync(join(repo, TURNS, name, "result.json"), { recursive: true });
      else put(repo, `${TURNS}/${name}/result.json`, content);
    }
    put(repo, `${RUN}/state.json`, JSON.stringify({ state: "REVISE" }));
    extra(repo);
    if (patch) {
      put(repo, `${RUN}/candidate.patch`, "diff");
      utimesSync(join(repo, ...RUN.split("/"), "candidate.patch"), MARK, MARK);
    }
    // 有补丁时目录的时刻晚一小时：since 只该取补丁的
    utimesSync(join(repo, ...RUN.split("/")), patch ? MARK + 3600 : MARK, patch ? MARK + 3600 : MARK);
  }, false);
  const runDir = (sc: Scene): string => join(sc.repo, ...RUN.split("/"));
  const FULL = {
    t1: record("2026-10-31T11:59:59Z", { turn_id: "t1" }), t2: record("2026-10-31T12:00:00Z", { turn_id: "t2", models: ["m2"] }),
    t3: record("2026-10-31T12:00:00Z", { turn_id: "t3" }), t4: record("2026-10-31T12:00:01Z", { output_error: "x", turn_id: "t4" }),
    t5: record("2026-10-31T12:00:02Z", { violations: ["v"], turn_id: "t5" }), t6: JSON.stringify({ session_key: "T002-7-audit-post", finished_at: "2999-01-01T00:00:00Z" }),
    t7: Buffer.from([0x7b, 0xff, 0x7d]), t8: "{bad", t9: null, ta: record(null, { turn_id: "ta" }),
  };

  it("final_audit_turn：同一秒取先遇到的，晚的胜出；早一秒、输出出错、有违规、别的主任务、坏 UTF-8、坏 JSON、result.json 是目录都不算；没有补丁时看目录的时刻", () => {
    const states = agreeFlow([
      turnScene(FULL), turnScene({ ...FULL, t0: record("2026-10-31T13:00:00Z", { turn_id: "t0" }) }), turnScene({ ...FULL, tb: record(5, { turn_id: "tb" }) }),
      turnScene(FULL, false), turnScene({}), turnScene({ t1: record("2026-10-31T11:59:59Z", { turn_id: "t1" }) }),
    ].map((sc) => flow("final_audit_turn", sc, [execTs(sc), runDir(sc)])));
    expect(states.map((state) => {
      const value = returned(state);
      return value instanceof Map ? value.get("turn_id") : value;
    })).toEqual(["t2", "t0", "tb", "t2", null, null]);
  }, 600_000);

  it("final_audit_turn 照样崩：记录不是字典、嵌套太深", () => {
    const states = agreeFlow([turnScene({ ...FULL, tz: "[1]" }), turnScene({ ...FULL, tz: `${"[".repeat(5000)}${"]".repeat(5000)}` })]
      .map((sc) => flow("final_audit_turn", sc, [execTs(sc), runDir(sc)])));
    expect(states.map(errorOf)).toEqual(["AttributeError", "RecursionError"]);
  }, 600_000);

  it("write_review：没有终审回合；模型列表是字符串、没写；终审报告为空；复审记录已在时文件名加 utc_compact；模型列表里有整数照样崩", () => {
    const report = (repo: string, content: string): void => put(repo, ".agent/mailbox/tasks/T001-7-audit-post/report.md", content);
    const reviewTs = (sc: Scene): PyDict => execTs(sc, {
      gate_post: { whitebox_exit: 0, mutate_exit: 1 }, exec: { check_exit: 0, scope_violations: 0 }, jev: { "3j-jev": { status: "ok" } },
    });
    const scenes = [
      turnScene({}, true, (repo) => put(repo, ".agent/reviews/t001-doc/attempt-001-hub.md", "旧的")),
      turnScene({ t2: record("2026-10-31T12:00:00Z", { turn_id: "t2", models: "ab", effort_requested: "max" }) }, true, (repo) => report(repo, `  终审意见${LF}${LF}`)),
      turnScene({ t2: record("2026-10-31T12:00:00Z", { turn_id: "t2" }) }, true, (repo) => report(repo, `  ${LF}`)),
      turnScene({ t2: record("2026-10-31T12:00:00Z", { turn_id: "t2", models: [1] }) }),
    ];
    const states = agreeFlow(scenes.map((sc) => flow("write_review", sc, [reviewTs(sc), runDir(sc), "REVISE"])));
    expect(states.map(errorOf)).toEqual([null, null, null, "TypeError"]);
    expect(returned(states[0])).toBe(join(scenes[0]?.repo as string, ".agent", "reviews", "t001-doc", `attempt-001-hub-${STAMP}.md`));
    const body = text(states[1], "0/.agent/reviews/t001-doc/attempt-001-hub.md");
    expect(body).toContain("- 复审者：audit-sonnet（a,b，思考档位要求 max、生效 未回报；回合 t2），终审报告如下");
    expect(body).toContain("- JEV：一审前 ok；终审前 None");
    expect(text(states[2], "0/.agent/reviews/t001-doc/attempt-001-hub.md")).toContain(`（None，思考档位要求 None、生效 未回报；回合 t2），终审报告如下${LF}${LF}## 终审报告${LF}${LF}（终审报告为空）`);
  }, 600_000);
});

describe("第 ⑤g2 片：rebase_candidate、start_rework、start_retry、ensure_rework_scope、rework_added_files（手写，真 git）", () => {
  /** A 是基线，B 是门禁热修补之后的基准测试提交，C 是建在 A 上的候选；HEAD 切回 A。 */
  interface Chain { readonly sc: Scene; readonly a: string; readonly b: string; readonly c: string }
  function chain(oracle: Record<string, string>, candidate: Record<string, string | Uint8Array>, extra: (repo: string, ids: { a: string; b: string; c: string }) => void = () => undefined): Chain {
    const ids = { a: "", b: "", c: "" };
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      ids.a = head;
      ids.b = commitOn(repo, head, oracle, "门禁热修补");
      ids.c = commitOn(repo, head, candidate, "候选");
      git(repo, "checkout", "-q", "--detach", head);
      extra(repo, ids);
    }, false);
    return { sc, ...ids };
  }
  const HOTFIX = { [GATE]: lines("def test_title():", "    assert 1 == 2") };
  const previous = (sc: Scene): string => join(sc.repo, ...RUN.split("/"));
  const carryTs = (ch: Chain, extra: Record<string, unknown> = {}): PyDict => execTs(ch.sc, { oracle: { sha: ch.b, files: [GATE] }, ...extra });
  /** scratch_worktree 的 worktree_root 与 mkdtemp 照手写的记录注入：建在固定的名字上。 */
  function scratch(sc: Scene): { inner: unknown[]; made: string } {
    const root = tempDir("runexec-wtroot");
    const prefix = `${basename(sc.repo).slice(0, 16)}-hub-carry-`;
    const made = join(root, `${prefix}fixed`);
    const none = { write: {}, delete: [] };
    return {
      made, inner: [
        { fn: "worktree_root", repo: sc.repo, value: toTagged(root), files: none }, { fn: "mkdtemp", prefix, dir: root, value: toTagged(made), files: none },
      ],
    };
  }
  const tree = (repo: string, commit: string): string => git(repo, "rev-parse", `${commit}^{tree}`);

  it("rebase_candidate：没有 tree、差异为空、diff 出错、apply 冲突（临时 worktree 收掉）、超过 1 MiB 的二进制改动搬过去（基准测试文件不搬）", () => {
    const big = seededBytes(53, 2 * 1024 * 1024);
    const noTree = chain(HOTFIX, { "src/doc.py": lines("def title():", "    return 'new'") }, (repo) => put(repo, `${RUN}/candidate.json`, "{}"));
    const empty = chain(HOTFIX, { "src/doc.py": lines("def title():", "    return 'new'") }, (repo, ids) => put(repo, `${RUN}/candidate.json`, JSON.stringify({ tree: tree(repo, ids.a) })));
    const broken = chain(HOTFIX, { "src/doc.py": "x" }, (repo) => put(repo, `${RUN}/candidate.json`, JSON.stringify({ tree: "f".repeat(40) })));
    const conflict = chain({ "src/doc.py": lines("def title():", "    return 'hotfix'") }, { "src/doc.py": lines("def title():", "    return 'new'") },
      (repo, ids) => put(repo, `${RUN}/candidate.json`, JSON.stringify({ tree: tree(repo, ids.c) })));
    const moved = chain(HOTFIX, { "src/doc.py": lines("def title():", "    return 'new'"), "assets/big.bin": big, [GATE]: lines("def test_title():", "    pass") },
      (repo, ids) => put(repo, `${RUN}/candidate.json`, JSON.stringify({ tree: tree(repo, ids.c) })));
    const [conflictScratch, movedScratch] = [scratch(conflict.sc), scratch(moved.sc)];
    const states = agreeFlow([
      ...[noTree, empty, broken].map((ch) => flow("rebase_candidate", ch.sc, [carryTs(ch), previous(ch.sc), ch.a])),
      flow("rebase_candidate", conflict.sc, [carryTs(conflict), previous(conflict.sc), conflict.a],
        { inner: conflictScratch.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [conflictScratch.made] }),
      flow("rebase_candidate", moved.sc, [carryTs(moved), previous(moved.sc), moved.a], { inner: movedScratch.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [movedScratch.made] }),
    ]);
    injectedCleanly(states);
    const values = states.map((state) => returned(state) as PyValue[]);
    expect(values.slice(0, 2)).toEqual([[null, "attempt-001 的候选记录里没有 tree"], [null, "算不出 attempt-001 的改动：差异为空"]]);
    expect(String(values[2]?.[1])).toContain("算不出 attempt-001 的改动：fatal:");
    expect(values[3]?.[0]).toBe(null);
    expect(String(values[3]?.[1])).toContain(`attempt-001 的候选放不到基准测试 ${conflict.b.slice(0, 10)} 上：${LF}`);
    expect([existsSync(conflictScratch.made), existsSync(movedScratch.made)], "临时 worktree 收掉了").toEqual([false, false]);
    const sha = String(values[4]?.[0]);
    expect([values[4]?.[1], git(moved.sc.repo, "rev-parse", `refs/themis/rework/t001-doc/attempt-001`)]).toEqual(["", sha]);
    expect(git(moved.sc.repo, "diff", "--name-only", moved.b, sha).split(LF)).toEqual(["assets/big.bin", "src/doc.py"]);
    const patchKey = `0/.agent/mailbox/tasks/T001-5-exec/evidence/carry-attempt-001-${STAMP}.patch`;
    expect(Buffer.from(written(states[4])[patchKey] as string, "base64").length, "补丁超过 1 MiB").toBeGreaterThan(1024 * 1024);
  }, 600_000);

  it("start_rework：is-ancestor 退出码 0、1、128；verdict 被拒；branch 失败、没给出提交；空的返工提交照旧从基线改（重派说明删掉）；升版撞上已有的版本；候选要搬时没有 tree", () => {
    const plain = (state: string, extra: (repo: string, ids: { a: string; b: string; c: string }) => void = () => undefined): Chain => chain({}, { "src/doc.py": "x" }, (repo, ids) => {
      put(repo, `${RUN}/state.json`, JSON.stringify({ state }));
      put(repo, `${RUN}/meta.json`, JSON.stringify({ base_sha: ids.a }));
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(ids.a, undefined, [...RETRY(1), "## Budget", "- max_attempts_total: 6", "", ...RETRY(2)]));
      put(repo, ".agent/plans/t001-doc.v1.json", PASSING_JSON);
      extra(repo, ids);
    });
    // oracle 就是 A 的几个：is-ancestor 退出码 0，不用搬
    const sameOracle = (ch: Chain, extra: Record<string, unknown> = {}): PyDict => execTs(ch.sc, { oracle: { sha: ch.a, files: [GATE] }, ...extra });
    const review = (ch: Chain): string => join(ch.sc.repo, ".agent", "reviews", "t001-doc", "attempt-001-hub.md");
    const verdict = (ch: Chain, kind: string, code: number): unknown =>
      pd(["verdict", previous(ch.sc), "--verdict", "REVISE", "--class", kind, "--review", review(ch)], code, code ? "结论被拒" : "ok");
    const rejected = plain("NEEDS_REVIEW");
    const branchFailed = plain("REVISE");
    const noCommit = plain("REVISE");
    let empty = "";
    const emptyRework = plain("TIMEOUT", (repo, ids) => {
      empty = git(repo, "commit-tree", tree(repo, ids.a), "-p", ids.a, "-m", "空的返工提交");
    });
    const bumped = plain("REVISE", (repo, ids) => put(repo, ".agent/plans/t001-doc.v2.md", contractMd(ids.a)));
    const moved = plain("REVISE");
    const unknownOracle = plain("REVISE");
    const audited = plain("REVISE");
    const states = agreeFlow([
      flow("start_rework", rejected.sc, [sameOracle(rejected), previous(rejected.sc), "audit"], { inner: [verdict(rejected, "EXECUTION_ERROR", 1)] }),
      flow("start_rework", branchFailed.sc, [sameOracle(branchFailed), previous(branchFailed.sc), "audit"], { inner: [pd(["branch", previous(branchFailed.sc), "--rework"], 1, "分支已存在")] }),
      flow("start_rework", noCommit.sc, [sameOracle(noCommit), previous(noCommit.sc), "audit"], { inner: [pd(["branch", previous(noCommit.sc), "--rework"], 0, "commit=abc")] }),
      flow("start_rework", emptyRework.sc, [sameOracle(emptyRework), previous(emptyRework.sc), "timeout"], {
        inner: [verdict(emptyRework, "TIMEOUT", 0), pd(["branch", previous(emptyRework.sc), "--rework"], 0, `建好了 commit=${empty}`), ...revalidate()],
      }),
      flow("start_rework", bumped.sc, [sameOracle(bumped, {
        contract: { ...V1, dispatched: true },
        audit_history: [{ stage: "7-audit-post", blockers: "第一条" }, { stage: "4-audit-pre", blockers: "不算" }, { stage: "7-audit-post", blockers: "最后一条" }],
      }), previous(bumped.sc), "audit"], { inner: [pd(["branch", previous(bumped.sc), "--rework"], 0, `commit=${bumped.c}`)] }),
      flow("start_rework", moved.sc, [execTs(moved.sc, { oracle: { sha: moved.b, files: [GATE] } }), previous(moved.sc), "upstream"]),
      // 基准测试提交不存在：is-ancestor 退出码 128，不算“不是祖先”，照旧走 branch --rework
      flow("start_rework", unknownOracle.sc, [execTs(unknownOracle.sc, { oracle: { sha: "f".repeat(40), files: [GATE] } }), previous(unknownOracle.sc), "audit"],
        { inner: [pd(["branch", previous(unknownOracle.sc), "--rework"], 1, "找不到提交")] }),
      // 终审返工没派遣过也升版；阻塞项取最后一条 7-audit-post；新版本校验过了就进返工链
      flow("start_rework", audited.sc, [sameOracle(audited, {
        audit_history: [{ stage: "7-audit-post", blockers: "第一条" }, { stage: "4-audit-pre", blockers: "不算" }, { stage: "7-audit-post", blockers: "最后一条" }],
      }), previous(audited.sc), "audit"], {
        inner: [pd(["branch", previous(audited.sc), "--rework"], 0, `commit=${audited.c}`),
          pd(["derive-json", "t001-doc.v2", "--force", "--title", "改文档"], 0, "ok", null, { "0/.agent/plans/t001-doc.v2.json": PASSING_JSON }), pd(["validate", "t001-doc.v2"], 0, "ok")],
      }),
    ]);
    injectedCleanly(states);
    expect(states.map(returned)).toEqual([
      `verdict REVISE 被调度器拒绝：${LF}结论被拒`, `branch --rework 没有建出返工提交：${LF}分支已存在`, `branch --rework 没有建出返工提交：${LF}commit=abc`,
      null, "返工合同没有建成：t001-doc.v2.md 已存在，合同版本只增不改", "attempt-001 的候选记录里没有 tree", `branch --rework 没有建出返工提交：${LF}找不到提交`, null,
    ]);
    const v2 = text(states[7], "0/.agent/plans/t001-doc.v2.md");
    expect([v2.includes("最后一条"), v2.includes("第一条"), v2.includes("## Rework（返工第 1 轮，内核追加）"), v2.includes(`- base_sha: ${audited.c}`)]).toEqual([true, false, true, true]);
    expect(tsAfter(states[7]).get("rework_chain")).toEqual([py({ from: "attempt-001", commit: audited.c, contract: "t001-doc.v2", at: AT, why: "audit", rebuilt: false })]);
    const md = text(states[3], "0/.agent/plans/t001-doc.v1.md");
    expect([md.includes("## Retry（"), md.includes("## Rework（返工第 1 轮，内核追加）"), md.includes(`- base_sha: ${emptyRework.a}`)]).toEqual([false, true, true]);
    expect(tsAfter(states[3]).has("rework_chain"), "空的返工提交不进返工链").toBe(false);
  }, 600_000);

  it("start_retry：已派遣时升版撞上已有的版本；retry_notes 是字典（写完合同才崩）；正常追加重派说明再校验", () => {
    const retryScene = (extra: (repo: string, head: string) => void = () => undefined): Scene => scene(BASE_FILES, (repo, _wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      put(repo, ".agent/plans/t001-doc.v1.json", PASSING_JSON);
      put(repo, `${RUN}/executor-report.json`, JSON.stringify({ executor_status: "blocked" }));
      extra(repo, head);
    }, false);
    const failedTs = (sc: Scene, extra: Record<string, unknown> = {}): PyDict =>
      execTs(sc, { exec: { run_dir: previous(sc), check_ok: false, check_exit: 1, scope_violations: 2, status: "NEEDS_REVIEW" }, ...extra });
    const bumped = retryScene((repo, head) => put(repo, ".agent/plans/t001-doc.v2.md", contractMd(head)));
    const oddNotes = retryScene();
    const normal = retryScene();
    const states = agreeFlow([
      flow("start_retry", bumped, [failedTs(bumped, { contract: { ...V1, dispatched: true } }), previous(bumped)]),
      flow("start_retry", oddNotes, [failedTs(oddNotes, { retry_notes: { a: 1 } }), previous(oddNotes)]),
      flow("start_retry", normal, [failedTs(normal, { retry_notes: ["attempt-000"] }), previous(normal)], { inner: revalidate() }),
    ]);
    injectedCleanly(states);
    expect(states.map((state) => errorOf(state) ?? returned(state))).toEqual([["t001-doc.v2.md 已存在，合同版本只增不改"], "AttributeError", []]);
    expect(text(states[1], "0/.agent/plans/t001-doc.v1.md")).toContain("## Retry（重派第 2 次，内核追加）");
    expect(tsAfter(states[2]).get("retry_notes")).toEqual(["attempt-000", "attempt-001"]);
  }, 600_000);

  it("ensure_rework_scope 与 rework_added_files：返工提交不在（HubError 变成问题）、新增的文件补进范围、合同没有 Scope、都允许了；返工链是字典、字符串、提交不是字符串", () => {
    const added = chain({}, { "src/new.py": "x" }, (repo, ids) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(ids.a));
      put(repo, ".agent/plans/t001-doc.v1.json", PASSING_JSON);
    });
    const noScope = chain({}, { "src/new.py": "x" }, (repo, ids) => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(ids.a, [])));
    const allowed = chain({}, { "src/new.py": "x" }, (repo, ids) => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(ids.a, ["## Scope", "- allowed_modified_files: src/*.py", ""])));
    const ts = (ch: Chain, commit: unknown): PyDict => execTs(ch.sc, { oracle: { sha: ch.a, files: [GATE] }, rework_chain: [{ commit }] });
    const states = agreeFlow([
      flow("ensure_rework_scope", added.sc, [ts(added, "f".repeat(40))]),
      flow("ensure_rework_scope", added.sc, [ts(added, added.c)], { inner: revalidate() }),
      flow("ensure_rework_scope", noScope.sc, [ts(noScope, noScope.c)]),
      flow("ensure_rework_scope", allowed.sc, [ts(allowed, allowed.c)]),
      flow("rework_added_files", added.sc, [execTs(added.sc, { rework_chain: { a: 1 } })]),
      flow("rework_added_files", added.sc, [execTs(added.sc, { rework_chain: "ab" })]),
      flow("rework_added_files", added.sc, [ts(added, 5)]),
      flow("rework_added_files", added.sc, [ts(added, added.c)]),
    ]);
    injectedCleanly(states);
    expect(states.map((state) => errorOf(state) ?? returned(state))).toEqual([
      expect.arrayContaining([expect.stringContaining("读不出返工基线里新增了哪些文件：git diff")]), [], ["合同里找不到 ## Scope 一节"], [],
      "KeyError", "TypeError", "TypeError", ["src/new.py"],
    ]);
    expect(text(states[1], "0/.agent/plans/t001-doc.v1.md")).toContain(lines("- allowed_modified_files:", "  - src/doc.py", "  - src/new.py"));
  }, 600_000);
});

describe("第 ⑤g2 片：run_exec 的落地锁（手写）", () => {
  it("预算用完先于一切；另一个进程拿着落地锁：等满时限报 LandBusy，不留标记；持有者不在了就接管，接着派遣；标记被外面删了，收尾删不到照样吞掉", () => {
    const LAND = ".agent/mailbox/.land";
    const holderScript = [
      "import sys, time", "sys.path.insert(0, sys.argv[1])", "import kit_hub", "from pathlib import Path",
      "kit_hub.DirLock(Path(sys.argv[2])).__enter__()", "print('held', flush=True)", "time.sleep(600)",
    ].join(LF);
    const held: { child: ChildProcess | null } = { child: null };
    try {
      const exhausted = scene(BASE_FILES, (repo) => put(repo, ".agent/plans/t001-doc.v1.json", `{"budget": {"max_attempts_total": 0}}`), false);
      const busy = scene(BASE_FILES, (repo) => {
        held.child = spawn(kernelPython(), ["-c", holderScript, join(REPO, "scripts"), join(repo, ...LAND.split("/"))], { stdio: "ignore" });
        for (let waited = 0; !existsSync(join(repo, ...LAND.split("/"), "owner.json")) && waited < 200; waited += 1) sleepSync(100);
      }, false);
      const dead = spawnSync(process.execPath, ["-e", ""]).pid as number;
      const stale = scene(BASE_FILES, (repo) => put(repo, `${LAND}/owner.json`, `${JSON.stringify({ pid: dead, token: "x", at: AT })}${LF}`), false);
      const unmarked = scene(BASE_FILES, undefined, false);
      const states = agreeFlow([
        flow("run_exec", exhausted, [execTs(exhausted)]),
        { ...flow("run_exec", busy, [execTs(busy)]), land_wait: 0.6 },
        { ...flow("run_exec", stale, [execTs(stale)], { inner: [pd(["prepare", KEY], 1, "预检没过", 1800)] }), land_wait: 0.6 },
        // exec_window 收尾的 except OSError: pass：派遣时执行标记被外面删了（内核自己不删，只有站主手动删、别的进程占着才走到）
        flow("run_exec", unmarked, [execTs(unmarked)], { inner: [pd(["prepare", KEY], 1, "预检没过", 1800, {}, ["0/.agent/mailbox/ledger/exec-active/T001.json"])] }),
      ]);
      injectedCleanly(states);
      expect((returned(states[0]) as PyDict).get("摘要")).toBe("预算用完，执行端没有开始");
      const busyResult = (states[1]?.["result"] as Record<string, unknown>);
      expect([busyResult["error"], busyResult["code"], String(busyResult["message"]).startsWith(`锁被占用：${join(busy.repo, ...LAND.split("/"))}（持有者 {'pid': ${String(held.child?.pid)}`)])
        .toEqual(["LandBusy", 3, true]);
      expect(Object.keys(written(states[1])).filter((key) => key.includes("exec-active")), "没有留下执行标记").toEqual([]);
      expect([(returned(states[2]) as PyDict).get("摘要"), (states[2]?.["files"] as { delete: string[] }).delete]).toEqual([
        "prepare 失败，执行端没有开始", [`0/${LAND}/owner.json`],
      ]);
      expect([(returned(states[3]) as PyDict).get("摘要"), Object.keys(written(states[3])).filter((key) => key.includes("exec-active"))])
        .toEqual(["prepare 失败，执行端没有开始", []]);
    } finally {
      held.child?.kill();
    }
  }, 600_000);
});

describe("第 ⑤g2 片：run_jev 的真会话（手写，本机假端点、假 key）", () => {
  const FAKE_KEY = "fake-jev-key-0000";
  const REPORT_SCREEN = {
    id: "report-screen", version: "1.0.0", description: "", state_fields: [], sha256: "0".repeat(64), path: "report-screen.json",
    questions: { scope_creep: { type: "noul", criteria: { true: "改了范围外的文件", false: "没有" } }, quality: { type: "score", criteria: ["低", "中", "高", "严重"] } },
    labels: { scope_creep: "超出范围", quality: "质量风险" }, thresholds: { review: 0.35, action: 0.7, severity_action: 2.5 },
  };

  /** 一个请求交给一个探针（异步起进程，假端点在本进程里才答得上）；环境里去掉官方的 key 名（不分大小写），凭据库关掉。 */
  function probeAsync(impl: Impl, request: ProbeRequest): Promise<ProbeResult> {
    const [command, ...args] = impl.argv;
    // off：只认环境变量（两边的凭据库都认这个开关；拼错了会按 system 处理）
    const env: Record<string, string | undefined> = { ...process.env, CODEKIT_SECRET_STORE: "off" };
    for (const name of Object.keys(env)) if (name.toUpperCase() === "TYPESAFE_API_KEY") delete env[name];
    return new Promise((done, fail) => {
      const child = spawn(command ?? "", args, { env, stdio: ["pipe", "pipe", "pipe"] });
      let out = "";
      let err = "";
      child.stdout.setEncoding("utf8").on("data", (chunk: string) => (out += chunk));
      child.stderr.setEncoding("utf8").on("data", (chunk: string) => (err += chunk));
      child.on("error", fail);
      child.on("close", (code) => (code === 0 ? done(JSON.parse(out) as ProbeResult) : fail(new Error(`${impl.name} 探针退出码 ${String(code)}：${err}`))));
      child.stdin.end(JSON.stringify(request));
    });
  }
  /** 延时与决策记录里的时刻钉不住：只在比较这一步换成占位。 */
  function placeholders(state: Record<string, unknown>): unknown {
    const files = state["files"] as { write: Record<string, string>; delete: string[] };
    const write: Record<string, string> = { ...files.write };
    const ledger = "0/.agent/mailbox/ledger/decisions.jsonl";
    if (ledger in write) {
      const records = Buffer.from(write[ledger] as string, "base64").toString("utf8").split(LF).filter((line) => line).map((line) => {
        const record = JSON.parse(line) as Record<string, unknown>;
        for (const name of ["at", "latency_ms"]) if (name in record) record[name] = `<${name}>`;
        return record;
      });
      write[ledger] = JSON.stringify(records);
    }
    const result = state["result"] as Record<string, unknown>;
    const value = result["ok"] ? (fromTagged(result["value"] as Tagged) as PyDict) : null;
    if (value !== null) value.set("验证", String(value.get("验证")).replace(/[0-9]+ ms$/u, "<ms> ms"));
    return scrubResult({ ...state, files: { ...files, write }, result: value === null ? result : { ok: true, value: toTagged(value) } });
  }

  it("一审前（题库读模板目录，端点答 401：无意见）与终审前（题库照记录注入，端点答两题：标出要留意的）；只发往假端点，带的是假 key", async () => {
    /** 收到的请求只记路径与 Authorization 对不对，收到的头不进任何输出。 */
    const requests: { path: string; authorized: boolean }[] = [];
    const replies: (() => [number, string])[] = [];
    const server = createServer((request: IncomingMessage, response: ServerResponse) => {
      const chunks: Buffer[] = [];
      request.on("data", (chunk: Buffer) => chunks.push(chunk));
      request.on("end", () => {
        requests.push({ path: `${String(request.method)} ${String(request.url)}`, authorized: request.headers["authorization"] === `Bearer ${FAKE_KEY}` });
        const [status, body] = (replies[0] as () => [number, string])();
        response.writeHead(status, { "Content-Type": "application/json" }).end(body);
      });
    });
    await new Promise<void>((ready) => server.listen(0, "127.0.0.1", () => ready()));
    const endpoint = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
    try {
      const jevScene = (): Scene => scene(BASE_FILES, (repo, _wt, head) => {
        put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
        put(repo, ".agent/plans/t001-doc.v1.json", JSON.stringify({ title: "改文档", scope: { allowed_modified_files: ["src/doc.py"] }, definition_of_done: ["D01"] }));
        put(repo, ".agent/mailbox/tasks/T001-1-plan/report.md", "规划：title() 交回 new。");
        put(repo, `${RUN}/scope.json`, JSON.stringify({ files: [{ path: "src/doc.py", status: "M" }, "x"] }));
        put(repo, `${RUN}/observations.json`, JSON.stringify({ review_hints: { assertion_lines_removed: 1 } }));
      }, false);
      const jevTs = (sc: Scene): PyDict => execTs(sc, {
        stages: { "2-contract": { fields: { 摘要: "合同摘要", 验证: "校验过了" } }, "5-exec": { fields: { 摘要: "执行摘要", 偏离: "无" } } },
        exec: { run_dir: previous(sc), check_exit: 0, scope_violations: 0 }, gate_post: { whitebox_exit: 0, mutation_counts: { caught: 2 } }, jev: {},
      });
      const previous = (sc: Scene): string => join(sc.repo, ...RUN.split("/"));
      const before = jevScene();
      const after = jevScene();
      const jev = { endpoint, key: FAKE_KEY };
      const none = { write: {}, delete: [] };
      const cases: [ProbeRequest, () => [number, string]][] = [
        [{ ...flow("run_jev", before, [jevTs(before), "3j-jev"]), jev }, () => [401, "{}"]],
        [{
          ...flow("run_jev", after, [jevTs(after), "6j-jev"], {
            replaced: ["load_locked_batteries"],
            inner: [{ fn: "load_locked_batteries", path: join(after.repo, "plugins", "decisions"), value: toTagged(py({ "report-screen": REPORT_SCREEN })), files: none }],
          }),
          jev,
        }, () => [200, JSON.stringify({ answers: { scope_creep: { type: "noul", noul: 0.8 }, quality: { type: "score", score: 3.0 } }, usage: { input_tokens: 31, output_tokens: 5 }, model: DEFAULT_MODEL })]],
      ];
      const shown: unknown[][] = [];
      for (const impl of IMPLS) {
        const row: unknown[] = [];
        for (const [request, reply] of cases) {
          replies.splice(0, replies.length, reply);
          const result = await probeAsync(impl, request);
          row.push(placeholders(result["value"] as Record<string, unknown>));
        }
        shown.push(row);
      }
      const [python, ...others] = shown;
      for (const [index, other] of others.entries()) expect(JSON.stringify(other).slice(0, 6000), `${IMPLS[index + 1]?.name} 与 Python 不同`).toBe(JSON.stringify(python).slice(0, 6000));
      const states = (python as Record<string, unknown>[]).map((state) => ({ ...state, result: (state["result"] as Record<string, unknown>) }));
      injectedCleanly(states);
      expect(requests.length, "每边两次请求").toBe(2 * IMPLS.length);
      expect(requests.map((item) => item.path), "只发往假端点的 System One 路径").toEqual(Array.from({ length: requests.length }, () => "POST /v1/systemone"));
      expect(requests.every((item) => item.authorized), "Authorization 与假 key 不符").toBe(true);
      expect(states.map(errorOf), JSON.stringify(states.map((state) => state["result"])).slice(0, 3000)).toEqual([null, null]);
      const after6 = fromTagged((states[1]?.["result"] as Record<string, unknown>)["value"] as Tagged) as PyDict;
      expect(String(after6.get("摘要"))).toContain("超出范围：");
      expect(String(after6.get("摘要"))).toContain("【需关注】");
      const before3 = fromTagged((states[0]?.["result"] as Record<string, unknown>)["value"] as Tagged) as PyDict;
      expect(String(before3.get("摘要"))).toContain("无意见（");
    } finally {
      await new Promise<void>((closed) => server.close(() => closed()));
    }
  }, 600_000);
});
