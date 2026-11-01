// 第 ⑤e1a 片的契约（迁移计划第 ⑤ 步）：合同与战前门禁里纯文字的部分。kit_hub.py 的 tail、tail_file、normalize_identity、
// normalize_markup、strip_decisions、decisions_section、unparsed_check_ids、external_fact_problems、unverified_facts、pytest_outcomes
// 交给 Python、Node、Bun，逐字比带标签的结果（崩溃比类型）。语料：
//   - tests/test_kit_hub.py 里调到这些函数的 80 条用例：在全部用例上采样一次挑出来的（参数化的与要别的夹具的 19 条采不了，它们走的
//     路径由手写的对照补上）。Python 探针记下顶层调用，三边重放；tail 按（文字的 sha256、行数）去重；每个函数都要有 Python 重放与
//     当时结果相同的样本（只比得上漂移了的不算）；
//   - 手写的对照：尾行的边界（空、恰好 n 行、不以换行结尾、CRLF 与单独的 CR、n 为 0 与负数、按字节截断落在多字节字符中间）；pytest
//     摘要行的各种写法（失败与通过并存、skipped/xfailed/xpassed/warnings/errors/deselected、no tests ran、带时分秒的长用时、有无边框、
//     Unicode 数字）；站主决定、外部事实、检查行编号、Identity 与粗体编号的边界与崩溃；
//   - 按种子生成的合同文字：Identity、粗体编号、Scope 的括号说明、站主决定一节、检查行，掺全角标点、组合字符、希腊字母（词尾的 Σ）、
//     Unicode 数字与空白、BMP 之外的字符。
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, prng, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";

const C = (...codes: number[]): string => String.fromCodePoint(...codes);
const TAB = C(9);
const LF = C(10);
const CR = C(13);
const BT = C(96);
const ROOT = scratchDir("contract");
afterAll(() => removeDir(ROOT));

const sha256 = (text: string): string => createHash("sha256").update(text).digest("hex");
function py(value: unknown): PyValue {
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}
const call = (fn: string, args: readonly unknown[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))) });
const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);
const file = (name: string, content: string | Uint8Array): string => {
  const path = join(ROOT, name);
  mkdirSync(ROOT, { recursive: true });
  writeFileSync(path, content);
  return path;
};

/** 三边各跑一遍、逐个比；交回 Python 的结果。okShare：至少这一份比例的请求要正常交回（别让两边一样地早早失败也算一致）。 */
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
  "test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number", "test_a_cut_off_attempt_is_continued_instead_of_restarted",
  "test_a_delivery_that_fails_the_check_is_redone_in_the_same_session", "test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner",
  "test_a_failed_ts_reinstall_writes_to_the_owner", "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted",
  "test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline", "test_a_passing_delivery_clears_the_last_check",
  "test_a_rate_limited_worker_turn_is_held_and_resumed", "test_a_redelivery_may_hand_in_a_block_instead",
  "test_a_redelivery_that_still_fails_goes_to_the_coordinator_saying_so", "test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too",
  "test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed", "test_a_timed_out_attempt_is_continued_instead_of_restarted",
  "test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner", "test_a_timed_out_attempt_whose_checks_passed_is_not_told_to_rerun_them",
  "test_a_timed_out_turn_does_not_use_up_the_format_retry", "test_a_timed_out_voided_turn_is_resumed_not_restarted",
  "test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner", "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base",
  "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch", "test_background_sweeps_hold_off_other_landings_while_they_run",
  "test_bold_item_ids_in_the_contract_are_normalized", "test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt",
  "test_contract_requirements", "test_contract_runs_the_earlier_gates_as_regression_checks", "test_contract_title_is_the_registered_task_title",
  "test_contract_with_pending_marks_is_rejected", "test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer",
  "test_each_turn_reads_its_own_copy_and_the_copy_is_gone_afterwards", "test_exec_letter_counts_the_candidate_and_names_the_failed_checks",
  "test_exec_recheck_resumes_an_execution_the_hub_was_killed_in", "test_exec_recheck_revisits_the_last_attempt_without_rerunning",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_exec_rework_reports_when_the_rework_base_cannot_be_built",
  "test_exec_rework_stops_at_the_budget", "test_exec_verdict_reads_the_attempt_state_key",
  "test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed",
  "test_failed_integrate_takes_the_landed_commits_back_off_the_branch", "test_finalize_lands_the_oracle_commit_first_and_can_be_retried",
  "test_finalize_lands_the_rework_chain_before_integrating", "test_finished_tasks_remove_their_stage_worktrees",
  "test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report", "test_gate_post_checks_the_anchors_before_mutating",
  "test_gate_post_judges_mutations_from_the_record", "test_gate_post_may_leave_the_candidate_red_with_evidence",
  "test_gate_post_reads_the_spec_file_and_names_entries_left_unchanged", "test_gate_pre_baseline_must_fail_on_assertions",
  "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff", "test_gate_pre_rejects_a_baseline_that_does_not_collect",
  "test_gate_rework_resets_a_worktree_the_state_lost_track_of", "test_invalid_output_gets_one_retry",
  "test_kernel_writes_the_contract_version_and_base_it_assigns",
  "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it",
  "test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks", "test_landing_rehearsal_reports_commits_that_no_longer_apply",
  "test_landing_skips_an_empty_rework_commit", "test_mutation_verdict_reads_the_record_not_the_exit_code",
  "test_owner_commits_get_a_gate_sweep_and_rehearsals", "test_owner_raises_the_attempt_budget",
  "test_owner_sweeps_reinstall_stale_ts_dependencies_under_the_land_lock", "test_owner_sweeps_start_with_the_ts_reinstall",
  "test_plan_redelivery_replaces_the_external_facts", "test_plan_with_only_verified_facts_goes_straight_to_the_contract",
  "test_pytest_outcomes_reads_the_summary_not_the_captured_output", "test_regression_sweep_runs_every_gate_baseline_on_the_new_tip",
  "test_retry_after_failed_checks_tells_the_executor_why", "test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again",
  "test_rework_contract_lets_the_executor_modify_files_added_earlier", "test_rework_starts_a_clean_session",
  "test_scope_notes_are_stripped_and_unparsed_check_ids_are_named", "test_scope_paths_missing_the_directory_prefix_are_named",
  "test_tail_file_reads_only_the_end", "test_the_executor_letter_says_none_when_nothing_is_pending",
  "test_the_owners_rework_words_reach_the_reworked_stage_verbatim", "test_unverified_external_facts_wait_for_the_owner",
  "test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes", "test_worker_delivery_is_verified_then_forwarded",
];
/** 当时的结果与 Python 重放对不上的用例（第一次跑出来的清单，覆盖审计里记 PARTIAL）；多了少了都要看过再改。 */
// 两条都是 tail_file：读的检查日志用例后来删了，重放时文件已经不在（FileNotFoundError）；tail_file 在别的用例里还有比得上的样本
const DRIFTED: string[] = [
  "test_a_timed_out_attempt_is_continued_instead_of_restarted",
  "test_a_timed_out_attempt_whose_checks_passed_is_not_told_to_rerun_them",
];
const FUNCTIONS = ["tail", "tail_file", "normalize_identity", "normalize_markup", "strip_decisions", "decisions_section", "unparsed_check_ids",
  "external_fact_problems", "unverified_facts", "pytest_outcomes"];

interface Sample {
  readonly test: string;
  readonly fn: string;
  readonly args: PyValue[];
  readonly result: string;
}

function pytestCalls(): Sample[] {
  const tmp = join(ROOT, "samples");
  mkdirSync(tmp, { recursive: true });
  const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, tmp }, 600_000);
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  return (value.get("calls") as PyDict[]).map((item) => ({ test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: item.get("result") as string }));
}

describe("第 ⑤e1a 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记到的顶层调用三边重放逐字相同；tail 去重；每个函数都有 Python 重放与当时结果相同的样本", () => {
    const seen = new Set<string>();
    let dropped = 0;
    const calls = pytestCalls().filter((item) => {
      if (item.fn !== "tail") return true;
      const key = JSON.stringify([sha256(String(item.args[0])), String(item.args[1])]);
      if (seen.has(key)) {
        dropped += 1;
        return false;
      }
      seen.add(key);
      return true;
    });
    const python = agree(calls.map((item) => ({ op: "hub.contract", fn: item.fn, args: item.args.map(toTagged) })), 0.8);
    const same = calls.map((item, at) => JSON.stringify(JSON.parse(item.result)) === JSON.stringify(python[at]));
    expect([...new Set(calls.filter((_, at) => !same[at]).map((item) => item.test))].sort(), "当时的结果与 Python 重放").toEqual(DRIFTED);
    const live = new Set(calls.filter((_, at) => same[at]).map((item) => item.fn));
    expect(FUNCTIONS.filter((fn) => !live.has(fn)), "没有一条比得上当时结果的样本").toEqual([]);
    // 去掉的条数随用例文字里的时刻与临时路径变（实测 164 条里去掉 118–120 条，写进覆盖审计），只要求真的去过重
    expect(dropped, "tail 去重去掉的条数").toBeGreaterThan(0);
  }, 600_000);
});

// --- 二、手写的对照 -------------------------------------------------------------------------------------------

describe("第 ⑤e1a 片：手写的对照", () => {
  it("tail：去两头的空白、按 Python 的 splitlines 切、n 为 0 时整份、负数从头数；不是字符串、n 不是整数时报的异常同型", () => {
    const text = `  ${LF}一${LF}二${CR}${LF}三${CR}四${C(0x2028)}五${C(0x85)}六${C(0x3000)}${LF}`;
    const results = agree([
      ...[0, 1, 2, 3, 7, 100, -1, -3, -100].map((n) => call("tail", [text, n])),
      call("tail", [text]), call("tail", ["", 3]), call("tail", [`${LF}${LF}`, 1]), call("tail", ["单行", true]),
      call("tail", [5, 1]), call("tail", [text, 1.5]), call("tail", [null, 1]),
    ], 0.6);
    expect(results.slice(-3).map((result) => result["error"])).toEqual(["AttributeError", "TypeError", "AttributeError"]);
  });

  it("tail_file：只读最后 limit 字节（截在多字节字符中间时换成 U+FFFD）、CRLF、单独的 CR、不以换行结尾、空文件；文件不在、是目录时报的异常同型", () => {
    const lines = Array.from({ length: 40 }, (_, at) => `第 ${at} 行 ${C(0x1f600)}`);
    const cut = file("tail-cut.log", lines.join(LF));
    const results = agree([
      call("tail_file", [file("tail-empty.log", ""), 30, 65536]),
      call("tail_file", [file("tail-three.log", ["一", "二", "三", ""].join(LF)), 3, 65536]),
      call("tail_file", [file("tail-open.log", ["一", "二", "三"].join(LF)), 2, 65536]),
      call("tail_file", [file("tail-crlf.log", lines.join(CR + LF)), 5, 65536]),
      call("tail_file", [file("tail-cr.log", lines.join(CR)), 5, 65536]),
      ...[1, 2, 3, 5, 7, 50].map((limit) => call("tail_file", [cut, 30, limit])),
      call("tail_file", [file("tail-bad.log", new Uint8Array([0x61, 0xff, 0x0a, 0xe4, 0xb8, 0x0a, 0x62])), 30, 65536]),
      call("tail_file", [join(ROOT, "no-such.log"), 30, 65536]),
      call("tail_file", [ROOT, 30, 65536]),
    ], 0.6);
    expect(results.slice(-2).map((result) => result["error"])).toEqual(["FileNotFoundError", "PermissionError"]);
  });

  it("pytest_outcomes：摘要行的各种写法、失败与出错的用例只认 short test summary info 之后的行、通用换行；拆不开、读不到时报的异常同型", () => {
    const summary = "=========================== short test summary info ===========================";
    const logs: [string, string | Uint8Array][] = [
      ["mixed.log", ["FAILED tests/a.py::t0 - 用例自己打印的，不算", "....F", summary, "FAILED tests/a.py::test_one - AssertionError: assert 1 == 2",
        "FAILED tests/a.py::test_two", "ERROR tests/b.py::test_three - fixture 'x' not found", "===== 1 failed, 2 passed, 1 error in 0.12s =====", ""].join(LF)],
      ["kinds.log", `3 passed, 1 skipped, 2 xfailed, 1 xpassed, 4 warnings, 1 error, 2 deselected in 1.50s${LF}`],
      ["no-tests.log", `no tests ran in 0.01s${LF}`],
      ["long.log", `=================== 5 passed in 62.00s (0:01:02) ===================${LF}`],
      ["short.log", "5 passed in 0.10s"],
      ["twice.log", ["1 failed in 0.1s", "2 passed in 0.2s"].join(LF)],
      ["crlf.log", ["=== short test summary info ===", "FAILED t.py::x - e", "1 failed in 0.1s"].join(CR + LF)],
      ["cr.log", ["=== short test summary info ===", "ERROR t.py::y", "1 error in 0.1s"].join(CR)],
      ["digits.log", `${C(0x661)}${C(0x662)} passed in 0.1s${LF}`],
      ["bad-bytes.log", new Uint8Array([0x31, 0x20, 0x70, 0x61, 0x73, 0x73, 0x65, 0x64, 0xff, 0x0a, 0x32, 0x20, 0x66, 0x61, 0x69, 0x6c, 0x65, 0x64, 0x20, 0x69, 0x6e, 0x20, 0x30, 0x73, 0x0a])],
      ["warning.log", `2 passed, 1 warning in 0.1s${LF}`],
      ["empty.log", ""],
      ["unpack.log", `1 passed,  in 0.1s${LF}`],
    ];
    const results = agree([...logs.map(([name, content]) => call("pytest_outcomes", [file(name, content)])), call("pytest_outcomes", [join(ROOT, "gone.log")])], 0.6);
    expect(results.slice(-2).map((result) => result["error"])).toEqual(["ValueError", "FileNotFoundError"]);
  });

  it("站主决定：附录的原文逐行引用（行尾空白去掉）；去掉附录（文末、中间、两份、标题后有空白、标题不在行首、CRLF）；崩溃同型", () => {
    const decisions = [{ msg: "20261101T000000000001Z-owner-000001", text: `Q1：用 ScaleIcon  ${LF}${LF}  - 列表项${TAB}${LF}## 标题也照引` },
      { msg: 7, text: 42 }, { msg: ["a"], text: `${C(0x2028)}分隔` }];
    const section = `## 站主决定（内核附原文）${LF}${LF}> 原文${LF}`;
    const results = agree([
      call("decisions_section", [[]]), call("decisions_section", [decisions]),
      ...[`正文${LF}${section}`, `正文${LF}${section}## 下一节${LF}内容${LF}`, `${section}${LF}中间${LF}${section}`, `正文${LF}## 站主决定（内核附原文）  ${TAB}${LF}x${LF}`,
        `正文 ## 站主决定（内核附原文）${LF}x`, `正文${CR}${LF}## 站主决定（内核附原文）${CR}${LF}x${CR}${LF}`, ""].map((text) => call("strip_decisions", [text])),
      call("decisions_section", [[{ text: "缺 msg" }]]), call("decisions_section", [["不是字典"]]), call("decisions_section", [{ msg: "字典本身" }]),
      call("decisions_section", [5]), call("strip_decisions", [null]),
    ], 0.5);
    expect(results.slice(-5).map((result) => result["error"])).toEqual(["KeyError", "TypeError", "TypeError", "TypeError", "TypeError"]);
  });

  it("检查行编号：调度器认得的不算，认不出的按顺序交回编号（小写、两个字母、全角冒号、括号说明、缩进；没有反引号的不像检查）", () => {
    const md = (lines: string[]): string => ["# TASK: x", "", "## Validation commands", ...lines, "", "## Definition of Done", `- VX9: ${BT}不在这一节${BT}`, ""].join(LF);
    const results = agree([
      call("unparsed_check_ids", [md([`- V01: ${BT}npm test${BT}`, `- VG1: ${BT}npm test${BT}`, `- v01：${BT}x${BT}`, `- G01（必要，基线应失败）: ${BT}pytest${BT}`,
        `* R01 (required): ${BT}y${BT}`, "- D01: 没有反引号", `  - V02：${BT}缩进的${BT}`, `  - VG2: ${BT}缩进的认不出${BT}`, `- AB-12: ${BT}z${BT}`, `- ${C(0x661)}01: ${BT}u${BT}`])]),
      call("unparsed_check_ids", ["没有这一节"]), call("unparsed_check_ids", [md([])]), call("unparsed_check_ids", [3]),
    ], 0.5);
    expect(valueOf(results[0]), "编号与括号之间隔了空格的调度器也认不出").toEqual(["VG1", "v01", "R01", "VG2", "AB-12"]);
  });

  it("外部事实：缺列表、不是列表、缺 fact 或 verified 的条目（空串、只有空白、0、不是字典）；输出不是字典时报 AttributeError", () => {
    const results = agree([
      ...[{}, { external_facts: "x" }, { external_facts: null }, { external_facts: [] }, { external_facts: [{ fact: "a", verified: "npm view a" }] },
        { external_facts: [{ fact: "", verified: "b" }, "字符串", { fact: 0, verified: 1 }, { fact: `${C(0x3000)} `, verified: "x" }, { fact: "f", verified: [] }, { fact: "g", verified: "h" }] }]
        .map((output) => call("external_fact_problems", [output])),
      call("external_fact_problems", [["不是字典"]]),
    ], 0.5);
    expect(results.at(-1)).toMatchObject({ ok: false, error: "AttributeError" });
  });

  it("没核实的事实：几种说法都算、已核实的不算；fact 与 source 去两头空白、source 缺了是空串；缺 verified、fact 时报 KeyError", () => {
    const facts = [{ fact: " a ", verified: "未核实", source: " s " }, { fact: "b", verified: "无法核实（离线）" }, { fact: "c", verified: "已核实：npm view" },
      { fact: "d", verified: "没有核实", source: null }, { fact: "e", verified: 0, source: 0 }, { fact: 5, verified: "不能核实", source: ["x"] }];
    const results = agree([call("unverified_facts", [facts]), call("unverified_facts", [[]]), call("unverified_facts", [[{ fact: "x" }]]),
      call("unverified_facts", [[{ verified: "未核实" }]])], 0.5);
    expect(results.slice(-2).map((result) => result["error"])).toEqual(["KeyError", "KeyError"]);
  });

  it("Identity：版本号与基线改成内核给的值，交回改了的字段与原来写的；值是整数也照样写；行首不是“-”的、大写十六进制的不改；崩溃同型", () => {
    const md = (version: string, base: string): string => ["# TASK: x", "", "## Identity", `- plan_version: ${version}`, `- base_sha: ${BT}${base}${BT}`, "- executor: x", ""].join(LF);
    const sha = "0123456789abcdef0123456789abcdef01234567";
    const results = agree([
      call("normalize_identity", [md("3", sha), { plan_version: "3", base_sha: sha }]),
      call("normalize_identity", [md("2", "abc1234"), { plan_version: "4", base_sha: sha }]),
      call("normalize_identity", [md("4", sha), { plan_version: 4, base_sha: sha }]),
      call("normalize_identity", [md(C(0x663), sha), { plan_version: "3", base_sha: sha }]),
      call("normalize_identity", [md("3", "ABC1234"), { plan_version: "3", base_sha: sha }]),
      call("normalize_identity", [`- plan_version:${TAB}${BT}7${BT}${LF}  - base_sha: deadbee${LF}`, { plan_version: "8", base_sha: "x" }]),
      call("normalize_identity", ["没有这两行", {}]),
      call("normalize_identity", [md("1", sha), { base_sha: sha }]),
      call("normalize_identity", [md("1", sha), "不是字典"]),
      call("normalize_identity", [9, {}]),
    ], 0.5);
    expect(results.slice(-3).map((result) => result["error"])).toEqual(["KeyError", "TypeError", "TypeError"]);
  });

  it("粗体编号与 Scope 的括号说明：几种粗体写法改成调度器认得的，括号说明去掉（嵌套的、不在行尾的、Scope 之外的不动）；交回改了几处", () => {
    const scope = ["## Scope", "- allowed_modified_files:", "  - src/a.ts（说明）（另一句）", "  - src/b.ts （带空格的说明）  ", "  - tests/c.py（a（b）c）", "  - src/f.ts（外（内）",
      "  - src/d.ts（说明）后面还有字", `* src/e.ts（${C(0x1f600)}）`, "", "## Definition of Done"].join(LF);
    const results = agree([
      call("normalize_markup", [["- **D01**: 一", "- **V01：** 二", "* **D12** ：三", "  - **D001**:四", "- **X01**: 不是 D 或 V", "- **D1**: 一位数字",
        `- **D${C(0x661)}${C(0x662)}**: Unicode 数字`].join(LF)]),
      call("normalize_markup", [`${scope}${LF}- **D01**: 一${LF}- src/x.ts（Scope 之外）${LF}`]),
      call("normalize_markup", [scope.split(LF).join(CR + LF)]),
      call("normalize_markup", [`## scope${LF}- a（小写的标题不算）${LF}`]),
      call("normalize_markup", [`## Scope${LF}- a（在文末）`]),
      call("normalize_markup", [""]), call("normalize_markup", [null]),
    ], 0.5);
    expect(results.at(-1)).toMatchObject({ ok: false, error: "TypeError" });
  });
});

// --- 三、按种子生成的合同文字 -----------------------------------------------------------------------------------

const PIECES = ["- plan_version: 3", `- plan_version: ${BT}12${BT}`, `- base_sha: ${BT}abcdef1${BT}`, "- base_sha: 0123456789abcdef0123456789abcdef01234567",
  "## Identity", "## Scope", "## Validation commands", "## 站主决定（内核附原文）", "## Definition of Done", "- **D01**: 完成", "- **V02：** 检查", "* **D03** ：x",
  "- src/a.ts（说明）", "  - tests/t.py（禁止碰）（第二句）", `- V01: ${BT}npm test${BT}`, `- VG1: ${BT}x${BT}`, `- g01（必要）: ${BT}y${BT}`, "> 引用", "",
  "全角，标点：；", `e${C(0x301)}${C(0x301)}`, "ΣΑΣ σας ΟΔΟΣ", `${C(0x661)}${C(0x662)}${C(0x663)}`, `${C(0x3000)}${C(0xa0)}`, C(0x1f600), C(0x1d49c),
  C(0x2028), C(0x85), TAB, `- plan_version: ${C(0x661)}`];

describe("第 ⑤e1a 片：按种子生成的合同文字", () => {
  it.each([1, 2, 3])("种子 %i：Identity、粗体编号、Scope 的括号说明、站主决定一节、检查行、尾行", (seed) => {
    const rnd = prng(seed * 7919);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const texts = Array.from({ length: 40 }, () => Array.from({ length: 4 + Math.floor(rnd() * 12) }, () => pick(PIECES)).join(pick([LF, LF, LF, CR + LF, CR, ""])));
    const values = { plan_version: pick(["3", "12", C(0x663)]), base_sha: pick(["abcdef1", "0123456789abcdef0123456789abcdef01234567"]) };
    agree(texts.flatMap((text) => [
      call("normalize_identity", [text, values]), call("normalize_markup", [text]), call("strip_decisions", [text]),
      call("unparsed_check_ids", [`## Validation commands${LF}${text}`]), call("tail", [text, Math.floor(rnd() * 6) - 1]),
    ]), 0.9);
  });
});
