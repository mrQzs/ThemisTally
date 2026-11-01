// 第 ⑤e1b 片的契约（迁移计划第 ⑤ 步）：合同与战前门禁里要读仓库、账本与信箱的部分，以及调度器的选择文件。kit_hub.py 的
// contract_paths、scope_missing_prefix、contract_requirements、dod_coverage_problems、budget_problems、answers_question，pi_dispatch.py
// 的 read_kernel_impl、argv_impl（与四张转交名单的键）交给 Python、Node、Bun，逐字比带标签的结果（崩溃比类型；HubError、DispatchError
// 比文字与退出码）。语料：
//   - tests/test_kit_hub.py 里调到前六个函数的 44 条用例：Python 探针记下顶层调用，三边重放；每个函数都要有 Python 重放与当时结果相同的
//     样本（只比得上漂移了的不算）；
//   - 一个真的临时仓库上的手写对照：合同要求的各种写法（Python 的 in 与 set：字符串查子串、字典查键、null 报 TypeError；required 没写
//     算真、写成 null 算假）、Scope 少了目录前缀（含 git 给非 ASCII 路径整条加引号、对不上的那种）、DoD 编号带正则的特殊字符、预算
//     （runs 里有领取过的 attempt）、站主信箱里的提问；
//   - 选择文件的各种坏法（BOM、坏的 UTF-8、出错位置前有 BMP 之外的字符、NaN、里层先收尾的重复键、多键少键、%r 的几种值）与 argv_impl
//     的判定次序（-h 与只有 TS 实现的命令在读选择文件之前）；四张名单的键逐张对照 Python；
//   - 按种子生成的命令行（--repo 的几种写法、-h、各子命令）乘随机的选择。
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { EXECUTOR, OWNER } from "@themis/hub/constants";
import { renderLetter } from "@themis/hub/letters";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, prng, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { newRepo, put, removeCreated } from "./repo-fixtures.ts";

const C = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = C(10);
const BT = C(96);
const DQ = C(34);
const ROOT = scratchDir("contract-repo");
const AT = "2026-11-01T00:00:00Z";
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

function py(value: unknown): PyValue {
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}
const call = (fn: string, args: readonly unknown[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))) });
const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

/** 三边各跑一遍、逐个比；交回 Python 的结果。okShare：至少这一份比例的请求要正常交回。 */
function agree(requests: readonly ProbeRequest[], okShare = 0.5): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  for (const [index, other] of others.entries()) {
    const bad = requests.map((_, at) => at).filter((at) => JSON.stringify(python?.[at]) !== JSON.stringify(other[at]));
    const shown = bad.slice(0, 3).map((at) => ({ at, fn: requests[at]?.["fn"], args: requests[at]?.["args"], python: python?.[at], other: other[at] }));
    expect(shown, `${IMPLS[index + 1]?.name} 与 Python 不同（共 ${bad.length} 处）`).toEqual([]);
  }
  const ok = (python ?? []).filter((result) => result.ok).length;
  expect(ok, JSON.stringify((python ?? []).filter((result) => !result.ok).slice(0, 3))).toBeGreaterThanOrEqual(Math.ceil(requests.length * okShare));
  return python as ProbeResult[];
}

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_a_cut_off_attempt_is_continued_instead_of_restarted", "test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner",
  "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline", "test_a_timed_out_attempt_is_continued_instead_of_restarted",
  "test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner", "test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner",
  "test_an_owner_reply_releases_the_gate_claim_and_long_letters_are_refused", "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base",
  "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch", "test_contract_budget_counts_attempts_of_earlier_versions",
  "test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt", "test_contract_requirements",
  "test_contract_runs_the_earlier_gates_as_regression_checks", "test_contract_title_is_the_registered_task_title",
  "test_contract_with_pending_marks_is_rejected", "test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer",
  "test_dispatched_contract_is_bumped_not_edited", "test_exec_letter_counts_the_candidate_and_names_the_failed_checks",
  "test_exec_recheck_resumes_an_execution_the_hub_was_killed_in", "test_exec_recheck_revisits_the_last_attempt_without_rerunning",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_exec_rework_reports_when_the_rework_base_cannot_be_built",
  "test_exec_rework_stops_at_the_budget", "test_exec_verdict_reads_the_attempt_state_key",
  "test_exec_waits_for_the_landing_lock_by_holding_its_letter", "test_execution_jev_gets_the_objective_fingerprint",
  "test_facts_checked_before_the_plan_is_delivered_says_why", "test_first_review_report_must_map_every_dod",
  "test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report", "test_gate_pre_baseline_must_fail_on_assertions",
  "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff", "test_gate_pre_rejects_a_baseline_that_does_not_collect",
  "test_gate_rework_resets_a_worktree_the_state_lost_track_of", "test_kernel_writes_the_contract_version_and_base_it_assigns",
  "test_owner_raises_the_attempt_budget", "test_retry_after_failed_checks_tells_the_executor_why",
  "test_rework_contract_lets_the_executor_modify_files_added_earlier", "test_scope_notes_are_stripped_and_unparsed_check_ids_are_named",
  "test_scope_paths_missing_the_directory_prefix_are_named", "test_the_executor_letter_says_none_when_nothing_is_pending",
  "test_unsent_contracts_get_the_rostered_executor_line", "test_unverified_external_facts_wait_for_the_owner",
];
/**
 * 当时的结果与 Python 重放对不上的用例（覆盖审计里记 PARTIAL；漂移的调用照样留在三边比的语料里）。重放读的是用例跑完时的合同与 runs：
 * ⑤e2 有了带 .git 的快照记录器之后，这 7 条改用调用当时的快照重放，拿掉；多了少了都要看过再改。
 */
const DRIFTED: string[] = [
  "test_contract_budget_counts_attempts_of_earlier_versions", // 几次调用之间改写同号合同的预算、领取新的 attempt
  "test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt", // accept_contract 里随后把同号合同的预算改大
  "test_contract_requirements", // 同号合同一次次改写成不同的毛病，重放只读到最后一版
  "test_contract_runs_the_earlier_gates_as_regression_checks", // 调用之后合同补上了回归检查
  "test_contract_with_pending_marks_is_rejected", // 调用之后合同端重交的 md 去掉了未决标注
  "test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer", // 调用之后重交的 md 去掉了未决标注
  "test_scope_notes_are_stripped_and_unparsed_check_ids_are_named", // 调用之后重交的 md 改对了检查行编号
];
const FUNCTIONS = ["contract_paths", "scope_missing_prefix", "contract_requirements", "dod_coverage_problems", "budget_problems", "answers_question"];

describe("第 ⑤e1b 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记到的顶层调用三边重放逐字相同；每个函数都有 Python 重放与当时结果相同的样本", () => {
    const tmp = join(ROOT, "samples");
    mkdirSync(tmp, { recursive: true });
    const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, tmp }, 600_000);
    expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
    const value = valueOf(recorded) as PyDict;
    expect(value.get("skipped")).toEqual([]);
    const calls = (value.get("calls") as PyDict[]).map((item) => ({ test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: item.get("result") as string }));
    const python = agree(calls.map((item) => ({ op: "hub.contract", fn: item.fn, args: item.args.map(toTagged) })), 0.8);
    const same = calls.map((item, at) => JSON.stringify(JSON.parse(item.result)) === JSON.stringify(python[at]));
    expect([...new Set(calls.filter((_, at) => !same[at]).map((item) => item.test))].sort(), "当时的结果与 Python 重放").toEqual(DRIFTED);
    const live = new Set(calls.filter((_, at) => same[at]).map((item) => item.fn));
    expect(FUNCTIONS.filter((fn) => !live.has(fn)), "没有一条比得上当时结果的样本").toEqual([]);
  }, 600_000);
});

// --- 二、临时仓库上的手写对照 ------------------------------------------------------------------------------------

interface Fixture {
  readonly repo: string;
  readonly head: string;
  /** 主任务状态，合同键换成给定的版本号。 */
  readonly ts: (version: number) => PyDict;
  /** 写一份合同（md 与 json），交回它的版本号。 */
  readonly contract: (json: string | Uint8Array, md?: string | Uint8Array) => number;
}

let shared: Fixture | null = null;
/** 基线里有先前一片的门禁基准（回归检查要跑它）、desktop/web 下的页面（Scope 少了前缀时对得上）、一个非 ASCII 的顶层目录。 */
function fixture(): Fixture {
  if (shared !== null) return shared;
  const { repo, head } = newRepo("contract-repo", {
    "tests/test_gate_t007_baseline.py": `def test_x():${LF}    assert True${LF}`,
    "desktop/web/src/pages/readonly1/view.ts": `export const v = 1;${LF}`,
    "桌面/资料/说明.md": `说明${LF}`,
  });
  let version = 0;
  const ts = (n: number): PyDict => {
    const state = newTaskState("T001", "doc", "改文档", head, true, AT);
    state.set("contract", new Map<string, PyValue>([["key", `t001-doc.v${n}`], ["version", BigInt(n)]]));
    return state;
  };
  const contract = (json: string | Uint8Array, md: string | Uint8Array = MD()): number => {
    version += 1;
    put(repo, `.agent/plans/t001-doc.v${version}.json`, json);
    put(repo, `.agent/plans/t001-doc.v${version}.md`, md);
    return version;
  };
  shared = { repo, head, ts, contract };
  return shared;
}

const GATE = ["python", "-m", "pytest", "tests/test_gate_t001_baseline.py", "-q"];
const REGRESSION = ["python", "-m", "pytest", "tests/test_gate_t007_baseline.py", "-q"];
/** 一份过得了内核要求的合同；over 换掉其中的几项。 */
function contractJson(head: string, over: Record<string, unknown> = {}): string {
  return JSON.stringify({
    base_sha: head,
    scope: { allowed_modified_files: ["src/a.ts"], allowed_new_files: [], forbidden_paths: ["tests/test_gate_t001_*.py"] },
    checks: [{ argv: GATE, expect_on_base: "fail", required: true }, { argv: REGRESSION, expect_on_base: "pass", required: true }],
    executor: { provider: EXECUTOR[0], model: EXECUTOR[1], thinking: EXECUTOR[2] },
    authorization: { integration: ["local_branch", "merge"] },
    definition_of_done: [{ id: "D01" }, { id: "D02" }],
    budget: { max_attempts_total: 6, max_wall_seconds_total: 20000, max_wall_seconds_per_attempt: 3600 },
    ...over,
  });
}
function MD(extra: string[] = []): string {
  return ["# TASK: t001-doc", "", "## Validation commands", `- G01（必要，基线应失败）: ${BT}python -m pytest tests/test_gate_t001_baseline.py -q${BT}`, ...extra, ""].join(LF);
}

describe("第 ⑤e1b 片：临时仓库上的手写对照", () => {
  it("contract_requirements：过得了的、forbidden_paths 与 argv 写成字符串或字典或 null、required 没写与写成 null、integration 写成字符串或带字典的列表", () => {
    const fx = fixture();
    const scope = (forbidden: unknown): Record<string, unknown> => ({ scope: { allowed_modified_files: ["src/a.ts"], forbidden_paths: forbidden } });
    const versions = [
      fx.contract(contractJson(fx.head)),
      fx.contract(contractJson(fx.head, scope("tests/test_gate_t001_*.py 与别的"))),
      fx.contract(contractJson(fx.head, scope("tests/other.py"))),
      fx.contract(contractJson(fx.head, scope({ "tests/test_gate_t001_*.py": 1 }))),
      fx.contract(contractJson(fx.head, scope(null))),
      fx.contract(contractJson(fx.head, { scope: null })),
      fx.contract(contractJson(fx.head, { checks: [{ argv: GATE.join(" "), expect_on_base: "fail" }, { argv: REGRESSION.join(" "), expect_on_base: "pass", required: null }] })),
      fx.contract(contractJson(fx.head, { checks: [{ argv: GATE, expect_on_base: "fail", required: null }] })),
      fx.contract(contractJson(fx.head, { checks: [] })),
      fx.contract(contractJson(fx.head, { checks: null, executor: { provider: EXECUTOR[0], model: "别的模型", thinking: EXECUTOR[2] } })),
      fx.contract(contractJson(fx.head, { executor: null, authorization: { integration: "local_branch, merge" } })),
      fx.contract(contractJson(fx.head, { authorization: { integration: { local_branch: 1, merge: 2 } } })),
      fx.contract(contractJson(fx.head, { authorization: { integration: ["local_branch", { merge: 1 }] } })),
      fx.contract(contractJson(fx.head), MD([`- VG1: ${BT}x${BT}`, "待确认：版本号；待站主拍板；待协调人决定；还是待确认", "## 站主决定（内核附原文）", "> 待确认 不算"])),
      fx.contract("不是 JSON"),
      fx.contract(new Uint8Array([0x7b, 0xff, 0x7d])),
      fx.contract(contractJson(fx.head), new Uint8Array([0x23, 0xff, 0x0a])),
      fx.contract("[1, 2]"),
    ];
    const results = agree(versions.map((n) => call("contract_requirements", [fx.repo, fx.ts(n)])), 0.6);
    expect(valueOf(results[0]), "过得了的合同").toEqual([]);
    expect(results.map((result) => result["error"] ?? null)).toEqual([null, null, null, null, "TypeError", null, null, null, null, null, null, null, "TypeError", null, null, null,
      "UnicodeDecodeError", "AttributeError"]);
  });

  it("scope_missing_prefix：少了目录前缀的对得上基线上的文件；第一段在根下有的、带通配符的、非 ASCII 的（git 整条加了引号）对不上；多于 6 条另计", () => {
    const fx = fixture();
    const entries = ["pages/readonly1/view.ts", "src/a.ts", "web/src/pages/*.ts", "资料/说明.md", "桌面/资料/说明.md", "readonly1/view.ts", "view.ts", "pages/readonly1/none.ts"];
    const many = Array(8).fill("pages/readonly1/view.ts"); // 8 条都对得上：报前 6 条，另有 2 条
    const results = agree([
      call("scope_missing_prefix", [fx.repo, { base_sha: fx.head, scope: { allowed_new_files: entries, forbidden_paths: "pages/x" } }]),
      call("contract_requirements", [fx.repo, fx.ts(fx.contract(contractJson(fx.head, { scope: { allowed_modified_files: many, forbidden_paths: ["tests/test_gate_t001_*.py"] } })))]),
      call("scope_missing_prefix", [fx.repo, { scope: { allowed_new_files: entries } }]),
      call("scope_missing_prefix", [fx.repo, { base_sha: "0".repeat(40), scope: { allowed_new_files: entries } }]),
      call("scope_missing_prefix", [fx.repo, { base_sha: 5 }]),
      call("scope_missing_prefix", [fx.repo, ["不是字典"]]),
    ], 0.5);
    expect(valueOf(results[0])).toEqual(["pages/readonly1/view.ts → desktop/web/src/pages/readonly1/view.ts", "readonly1/view.ts → desktop/web/src/pages/readonly1/view.ts"]);
    expect(results.slice(-2).map((result) => result["error"])).toEqual(["TypeError", "AttributeError"]);
  });

  it("dod_coverage_problems：编号带正则的特殊字符与非 ASCII；报告里漏了的按顺序报；KeyError 交回空、JSON 顶层不是对象与 contract 为 null 时报的异常同型", () => {
    const fx = fixture();
    const ids = ["D01", "D-02", "D 03", "D#04", "D&05", "D~06", "D.07", "D*08", "D+09", "D(10", "D[11", "验收一", "D1"];
    const n = fx.contract(contractJson(fx.head, { definition_of_done: [...ids.map((id) => ({ id })), { id: "" }, { id: 0 }, "不是字典", { id: 12 }] }));
    const report = `D01 已覆盖；D-02、D 03、D#04；XD&05 前面有字母；D~060 后面有数字；D.07；D*08；验收一；D10；D1${LF}`;
    const results = agree([
      call("dod_coverage_problems", [fx.repo, fx.ts(n), report]),
      call("dod_coverage_problems", [fx.repo, fx.ts(n), ids.join(" ") + " 12"]),
      // 报告里是 DX07、没有 D.07：转义过的点号对不上 X，没转义的能对上（DoD 编号不转义的变异在语义上抓得住，不只靠编译不过）
      call("dod_coverage_problems", [fx.repo, fx.ts(n), ids.filter((id) => id !== "D.07").join(" ") + " DX07 12"]),
      call("dod_coverage_problems", [fx.repo, new Map([["task", "T001"]]), report]),
      call("dod_coverage_problems", [fx.repo, fx.ts(fx.contract("不是 JSON")), report]),
      call("dod_coverage_problems", [fx.repo, fx.ts(fx.contract(contractJson(fx.head, { definition_of_done: [] }))), 5]),
      call("dod_coverage_problems", [fx.repo, fx.ts(n), 5]),
      call("dod_coverage_problems", [fx.repo, fx.ts(fx.contract("[1]")), report]),
      call("dod_coverage_problems", [fx.repo, new Map([["contract", null]]), report]),
    ], 0.5);
    expect(valueOf(results[3]), "合同键缺了：KeyError 在 try 里").toEqual([]);
    expect(results.slice(-3).map((result) => result["error"])).toEqual(["TypeError", "AttributeError", "TypeError"]);
  });

  it("budget_problems：runs 里的几种 attempt（有 claim 与 run.json、有 claim 没 run.json、wall_seconds 是 null、没有 claim）；边界；预算的值是字符串、浮点、Unicode 数字、下划线、bool、Infinity、NaN、字符串 inf 与 nan；缺键、读不出、顶层不是对象；KeyError 照样往外抛", () => {
    const fx = fixture();
    // 计入 3 次：001 按墙钟、002 按预留时限、004 的 wall_seconds 是 null 也按预留时限；003 没有 claim 不算。墙钟合计 2134.8125，round 到 2134.812
    put(fx.repo, ".agent/runs/t001-doc/attempt-001/claim/claimed.json", "{}");
    put(fx.repo, ".agent/runs/t001-doc/attempt-001/run.json", JSON.stringify({ wall_seconds: 1234.5625 }));
    put(fx.repo, ".agent/runs/t001-doc/attempt-002/claim/reservation.json", JSON.stringify({ timeout_seconds: 600 }));
    put(fx.repo, ".agent/runs/t001-doc/attempt-003/run.json", JSON.stringify({ wall_seconds: 99 }));
    put(fx.repo, ".agent/runs/t001-doc/attempt-004/claim/reservation.json", JSON.stringify({ timeout_seconds: 300.25 }));
    put(fx.repo, ".agent/runs/t001-doc/attempt-004/run.json", JSON.stringify({ wall_seconds: null }));
    const budget = (attempts: string, total: string, per: string): string =>
      `{${DQ}budget${DQ}: {${DQ}max_attempts_total${DQ}: ${attempts}, ${DQ}max_wall_seconds_total${DQ}: ${total}, ${DQ}max_wall_seconds_per_attempt${DQ}: ${per}}}`;
    const cases = [
      budget("5", "4134.812", "1000"), budget("4", "4134.812", "1000"), budget("5", "4134.811", "1000"), budget("5", "4134.813", "1000"), budget("4", "4134", "1000"),
      budget("6", "20000", "3600"), budget(`${DQ}5${DQ}`, `${DQ}1_0000${DQ}`, `${DQ}${C(0x663)}${C(0x660)}${C(0x660)}${C(0x660)}${DQ}`), budget("5.9", "true", "false"),
      budget("null", "Infinity", "1"), budget("9", "100", "Infinity"), budget("9", "NaN", "NaN"), budget("Infinity", "1", "1"), budget("NaN", "1", "1"),
      budget("9", "100000", `${DQ}inf${DQ}`), budget("9", "100", `${DQ}nan${DQ}`), budget(`${DQ}3.5${DQ}`, "1", "1"), budget("[1]", "1", "1"),
      `{${DQ}budget${DQ}: null}`, "{}", `{${DQ}budget${DQ}: [1]}`, "不是 JSON", "[1]", "null",
    ];
    const results = agree([
      ...cases.map((json) => call("budget_problems", [fx.repo, fx.ts(fx.contract(json))])),
      call("budget_problems", [fx.repo, new Map([["task", "T001"], ["contract_task", "t001-doc"]])]),
    ], 0.4);
    expect(valueOf(results[0]), "两个都恰好够").toEqual([]);
    expect((valueOf(results[4]) as string[]).length, "两条一起报").toBe(2);
    expect(results.slice(11, 14).map((result) => result["error"]), "int(Infinity)、int(NaN)、%d 遇到 inf").toEqual(["OverflowError", "ValueError", "OverflowError"]);
    expect(results.at(-1)).toMatchObject({ ok: false, error: "KeyError" });
  });

  it("answers_question：站主信箱里发出去的是不是提问（new 与 cur 都看）；坏信头交回假；msg_id 是整数照样拼文件名，是假值时两个信箱都不看", () => {
    const fx = fixture();
    const letter = (msgId: string, type: string): string => renderLetter(new Map([["msg-id", msgId], ["from", "womovie-c8"], ["to", OWNER], ["task-id", "T001"], ["in-reply-to", "none"], ["type", type]]),
      new Map<string, PyValue>([["摘要", "x"], ["提交", "无"], ["验证", "无"], ["偏离", "无"], ["需协调人决定", "无"], ["证据", "无"]]));
    const box = (name: string, file: string, content: string): void => put(fx.repo, `.agent/mailbox/inbox/${OWNER}/${name}/${file}`, content);
    box("new", "q-new.md", letter("q-new", "提问"));
    box("cur", "q-cur.md", letter("q-cur", "提问"));
    box("cur", "r-cur.md", letter("r-cur", "回复"));
    box("cur", "bad.md", `没有信头${LF}`);
    box("new", "5.md", letter("5", "提问"));
    box("new", "None.md", letter("None", "提问"));
    agree(["q-new", "q-cur", "r-cur", "bad", "missing", 5, 0, "", null].map((msgId) => call("answers_question", [fx.repo, msgId])), 0.9);
  });

  it("contract_paths：合同键是字符串、带子目录、不是字符串（TypeError）、缺 contract（KeyError）", () => {
    const fx = fixture();
    const ts = (contract: unknown): PyDict => new Map([["contract", py(contract)]]);
    const results = agree([
      call("contract_paths", [fx.repo, ts({ key: "t001-doc.v3" })]), call("contract_paths", [fx.repo, ts({ key: "sub/t001-doc.v3" })]),
      call("contract_paths", [fx.repo, ts({ key: 3 })]), call("contract_paths", [fx.repo, new Map()]),
    ], 0.5);
    expect(results.slice(-2).map((result) => result["error"])).toEqual(["TypeError", "KeyError"]);
  });
});

// --- 三、选择文件与 argv_impl -------------------------------------------------------------------------------------

const IMPL_KEYS = ["readonly", "config", "dispatcher", "hub"];
const implJson = (values: Record<string, unknown>, version: unknown = 1): string => JSON.stringify({ schema_version: version, ...Object.fromEntries(IMPL_KEYS.map((key) => [key, values[key] ?? "python"])) });

describe("第 ⑤e1b 片：选择文件与 argv_impl", () => {
  const dir = join(ROOT, "impl");
  const file = (name: string, content: string | Uint8Array): string => {
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, name), content);
    return join(dir, name);
  };

  it("read_kernel_impl：不存在算全部 python；是目录、BOM、坏的 UTF-8、出错位置前有 BMP 之外的字符、NaN、里层先收尾的重复键、多键少键（按码点排）、%r 的几种值，报错逐字相同", () => {
    const head = `{${DQ}schema_version${DQ}: 1, ${DQ}readonly${DQ}: ${DQ}python${DQ}, ${DQ}config${DQ}: ${DQ}python${DQ}, ${DQ}dispatcher${DQ}: ${DQ}python${DQ}`;
    const files = [
      join(dir, "missing.json"),
      dir,
      file("bom.json", C(0xfeff) + implJson({})),
      file("bad-utf8.json", new Uint8Array([0x7b, 0xff, 0x7d])),
      file("emoji.json", `${head}, ${DQ}hub${DQ}: ${DQ}${C(0x1f600)}${DQ} ${DQ}x${DQ}}`),
      file("nan.json", implJson({}).replace("1", "NaN")),
      file("dup.json", `{${DQ}a${DQ}: 1, ${DQ}a${DQ}: 2, ${DQ}b${DQ}: {${DQ}c${DQ}: 1, ${DQ}c${DQ}: 2}}`),
      file("list.json", "[1]"),
      file("keys.json", JSON.stringify({ schema_version: 1, readonly: "python", [C(0xff01)]: 1, [C(0x1f600)]: 2, hub: "python" })),
      ...[true, 1.5, "1", null].map((version, at) => file(`version-${at}.json`, implJson({}, version))),
      file("version-float.json", implJson({}).replace(`${DQ}schema_version${DQ}:1,`, `${DQ}schema_version${DQ}:1.0,`)),
      file("version-big.json", implJson({}).replace(`${DQ}schema_version${DQ}:1,`, `${DQ}schema_version${DQ}:1e+100,`)),
      file("version-huge.json", implJson({}).replace(`${DQ}schema_version${DQ}:1,`, `${DQ}schema_version${DQ}:1000000000000000000000000000000,`)),
      file("values.json", implJson({ readonly: "TS", config: `py${DQ}thon`, dispatcher: `t${C(7)}s`, hub: true })),
      file("valid.json", implJson({ readonly: "ts", config: "ts", dispatcher: "ts" })),
    ];
    const results = agree(files.map((path) => call("read_kernel_impl", [path])), 0.1);
    expect(valueOf(results[0])).toEqual(new Map(IMPL_KEYS.map((key) => [key, "python"])));
    expect(results.slice(1, -1).map((result) => result["error"] ?? "ok")).toEqual(Array(results.length - 2).fill("DispatchError"));
    expect(String(results[6]?.["message"])).toContain("'c' 重复");
  });

  it("argv_impl：-h 与只有 TS 实现的命令在读选择文件之前判定（选择文件坏了照样交回）；别的命令才读、才报错", () => {
    const bad = file("argv-bad.json", "坏的");
    const results = agree([
      call("argv_impl", [["--repo", "x", "status", "-h"], null, bad]), call("argv_impl", [["ui", "--desktop"], null, bad]),
      call("argv_impl", [["status"], null, bad]), call("argv_impl", [["logs", "list"], null, join(dir, "argv-missing.json")]),
      call("argv_impl", [["status"], null, file("argv-ts.json", implJson({ readonly: "ts" }))]),
    ], 0.6);
    expect(results.map((result) => result["error"] ?? valueOf(result))).toEqual(["python", "ts", "DispatchError", "python", "ts"]);
  });

  // tests/test_kernel_impl.py 里调到这两个函数的 8 条用例，argv、impl 与 15 种坏写法原样照抄（themistally-15 复核 ⑤e1b 时对出缺的几样）
  const ALL_PYTHON = { readonly: "python", config: "python", dispatcher: "python", hub: "python" };
  const READONLY_TS = { ...ALL_PYTHON, readonly: "ts" };
  const CONFIG_TS = { ...READONLY_TS, config: "ts" };
  const DISPATCHER_TS = { ...CONFIG_TS, dispatcher: "ts" };
  /** json.dumps 的写法：键与值之间“: ”，项之间“, ”。 */
  const dumps = (pairs: [string, string][]): string => `{${pairs.map(([name, raw]) => `${DQ}${name}${DQ}: ${raw}`).join(", ")}}`;
  const q = (text: string): string => `${DQ}${text}${DQ}`;
  const impl = (over: Record<string, string> = {}, version = "1"): string =>
    dumps([["schema_version", version], ...IMPL_KEYS.map((name): [string, string] => [name, over[name] ?? q("python")])]);

  it("test_kernel_impl.py：缺的、读得出的、15 种坏写法、读不了的选择文件", () => {
    const broken = [
      "", "not json", C(0xfeff) + impl(), "[]", dumps(IMPL_KEYS.map((name): [string, string] => [name, q("python")])),
      dumps([["schema_version", "1"], ["extra", q("python")], ...IMPL_KEYS.map((name): [string, string] => [name, q("python")])]),
      dumps([["schema_version", "1"], ["readonly", q("python")], ["config", q("python")], ["dispatcher", q("python")]]),
      impl({}, "2"), impl({}, "true"), impl({}, "1.0"), impl({}, q("1")), impl({ readonly: q("TS") }), impl({ hub: "null" }), impl({ config: `[${q("ts")}]` }),
      dumps([["schema_version", "1"], ["readonly", q("python")], ["readonly", q("ts")], ["config", q("python")], ["dispatcher", q("python")], ["hub", q("python")]]),
    ];
    const results = agree([
      call("read_kernel_impl", [join(dir, "ki-missing.json")]), call("read_kernel_impl", [file("ki-valid.json", impl({ readonly: q("ts") }))]),
      ...broken.map((text, at) => call("read_kernel_impl", [file(`ki-broken-${at}.json`, text)])),
    ], 0.1);
    expect(results.slice(2).map((result) => result["error"])).toEqual(Array(15).fill("DispatchError"));
  });

  it("test_kernel_impl.py：同一份名单、ui 不看选择（ui 带 -h 交回 python）、跟着 config 与 dispatcher 的开关", () => {
    const cases: [string[], Record<string, string>][] = [
      [["status", "--json"], ALL_PYTHON],
      ...[["status"], ["status", "--json", "t"], ["--repo", "x", "status"], ["--repo=x", "logs", "search", "p"], ["logs", "usage", "--task", "t"]]
        .map((argv): [string[], Record<string, string>] => [argv, READONLY_TS]),
      ...[["status", "--assess"], ["status", "-h"], ["logs", "--help"], ["logs"], ["prepare", "t.v1"], ["run", "x"], ["config", "show"]]
        .map((argv): [string[], Record<string, string>] => [argv, READONLY_TS]),
      ...[ALL_PYTHON, READONLY_TS].flatMap((chosen) => [["ui"], ["ui", "--desktop", "--assets", "w"], ["--repo", "x", "ui"], ["--repo=x", "ui"], ["ui", "-h"], ["status"]]
        .map((argv): [string[], Record<string, string>] => [argv, chosen])),
      ...[ALL_PYTHON, READONLY_TS].flatMap((chosen) => [["config", "show"], ["plugins", "list"], ["--repo", "x", "config", "doctor"]]
        .map((argv): [string[], Record<string, string>] => [argv, chosen])),
      ...[["config", "show"], ["config", "runtime", "add", "pi"], ["config", "secret", "check", "X"], ["plugins", "enable", "x"], ["--repo", "x", "config", "doctor", "--json"],
        ["--repo=x", "plugins", "list"], ["config", "secret", "set", "X"], ["config", "-h"], ["plugins", "--help"], ["config"], ["config", "nope"], ["plugins"],
        ["config", "runtime"], ["status"]].map((argv): [string[], Record<string, string>] => [argv, CONFIG_TS]),
      ...[["prepare", "t.v1"], ["--repo", "R", "run", "t"], ["status", "--assess"], ["decisions", "replay"], ["integrate", "t"]]
        .flatMap((argv): [string[], Record<string, string>][] => [[argv, CONFIG_TS], [argv, DISPATCHER_TS]]),
      [["status"], { ...DISPATCHER_TS, readonly: "python" }], [["run", "-h"], DISPATCHER_TS],
    ];
    const results = agree(cases.map(([argv, chosen]) => call("argv_impl", [argv, chosen, join(dir, "unused.json")])), 1);
    expect(results.map(valueOf).filter((value) => value === "ts").length, "交给 ts 的不止一两条").toBeGreaterThan(20);
  });

  it("四张转交名单的键与 Python 逐张相同", () => {
    agree([call("kernel_impl_tables", [])], 1);
  });

  it.each([1, 2, 3])("种子 %i：随机的命令行乘随机的选择（--repo 的几种写法、-h、config 的路径与 secret set、status 带不带 --assess、logs 的子命令）", (seed) => {
    const rnd = prng(seed * 104729);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const heads = [[], ["--repo", "C:/r"], ["--repo=C:/r"], ["--repo", "a", "--repo=b"], ["--repo"]];
    const bodies = [["status"], ["status", "--assess"], ["status", "T001", "--json"], ["logs", "list"], ["logs", "cat", "x"], ["logs", "nope"], ["logs"],
      ["config", "show"], ["config", "secret", "set", "K"], ["config", "secret", "check", "K"], ["config", "runtime", "add", "pi"], ["config", "runtime"],
      ["config", "role", "set", "execution"], ["config", "nope"], ["config"], ["plugins", "list"], ["plugins", "nope"], ["ui"], ["doctor"], ["check", "d"],
      ["decisions", "replay"], ["mutate", "--help"], ["run", "-h"], ["metrics"], ["integrate"], ["nope"], []];
    const values = ["python", "ts", "TS", null];
    const requests = Array.from({ length: 150 }, () => {
      const impl = Object.fromEntries(IMPL_KEYS.map((key) => [key, pick(values)]));
      if (rnd() < 0.1) delete (impl as Record<string, unknown>)[pick(IMPL_KEYS)];
      return call("argv_impl", [[...pick(heads), ...pick(bodies)], impl, join(dir, "unused.json")]);
    });
    agree(requests, 0.8);
  });
});
