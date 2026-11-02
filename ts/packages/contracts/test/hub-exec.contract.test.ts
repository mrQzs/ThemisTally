// 第 ⑤g1 片的契约（迁移计划第 ⑤ 步）：执行端代办里只读与纯文字的部分。kit_hub.py 的 interrupted_attempt、attempts_left、rework_source、
// latest_checks、cut_off、carryable、checks_passed、unfinished_why、carry_back、carry_source、returned_blockers、failed_attempt、retry_section、
// failed_checks_brief、failure_lines、report_leftovers、rework_section、unreported_gate_claims、empty_commit 放回调用当时的快照（带 .git，
// 文件与目录的修改时刻照原样）之后三边逐字比；rework_commits、add_modified_files、gate_claims、jev_flag 是纯函数。run_exec 等 ⑤g2 的函数
// 不在采样里，经它们调到的 ⑤g1 函数也算顶层。语料只有 tests/test_kit_hub.py 这一个来源；样本没走到的在 hub-exec-scenes 手写。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("exec");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_jev_report_flags_answers_by_the_battery_thresholds", "test_execution_jev_gets_the_objective_fingerprint",
  "test_requeue_leaves_unread_and_kernel_run_stages_alone", "test_a_stranded_exec_stage_is_reported_to_the_owner_once",
  "test_exec_verdict_reads_the_attempt_state_key", "test_exec_recheck_revisits_the_last_attempt_without_rerunning",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_exec_rework_reports_when_the_rework_base_cannot_be_built",
  "test_rework_contract_lets_the_executor_modify_files_added_earlier", "test_add_modified_files_handles_both_list_forms",
  "test_retry_after_failed_checks_tells_the_executor_why", "test_exec_rework_stops_at_the_budget",
  "test_finalize_lands_the_rework_chain_before_integrating", "test_failed_integrate_takes_the_landed_commits_back_off_the_branch",
  "test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too",
  "test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed",
  "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it",
  "test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again", "test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks",
  "test_landing_skips_an_empty_rework_commit", "test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain",
  "test_landing_rehearsal_reports_commits_that_no_longer_apply", "test_owner_commits_get_a_gate_sweep_and_rehearsals",
  "test_exec_recheck_resumes_an_execution_the_hub_was_killed_in", "test_exec_waits_for_the_landing_lock_by_holding_its_letter",
  "test_a_timed_out_attempt_is_continued_instead_of_restarted", "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted",
  "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base", "test_a_timed_out_attempt_whose_checks_passed_is_not_told_to_rerun_them",
  "test_carry_after_an_upstream_redelivery_finds_the_latest_usable_attempt", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_carried_candidate_gets_only_the_final_review_blockers_raised_after_it", "test_a_cut_off_attempt_is_continued_instead_of_restarted",
  "test_an_abandoned_attempt_is_skipped_when_looking_for_a_candidate", "test_exec_letter_counts_the_candidate_and_names_the_failed_checks",
  "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch", "test_owner_raises_the_attempt_budget",
  "test_an_unchanged_attempt_on_a_rework_base_still_carries_the_work", "test_gate_claims_in_the_executor_report_are_found",
  "test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner", "test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report",
  "test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner", "test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner",
  "test_the_executor_letter_says_none_when_nothing_is_pending",
];
const SNAPSHOT = [
  "interrupted_attempt", "attempts_left", "rework_source", "latest_checks", "cut_off", "carryable", "checks_passed", "unfinished_why", "carry_back",
  "carry_source", "returned_blockers", "failed_attempt", "retry_section", "failed_checks_brief", "failure_lines", "report_leftovers",
  "rework_section", "unreported_gate_claims", "empty_commit",
];
const PURE = ["rework_commits", "add_modified_files", "gate_claims", "jev_flag"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

/** 采一次样：读文件的几个带调用当时的快照（照 ⑤e2a），纯函数只记参数与结果。 */
function samples(): Call[] {
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: [...SNAPSHOT, ...PURE], snapshot_functions: SNAPSHOT, tmp }, 900_000);
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  return (value.get("calls") as PyDict[]).map((item) => {
    const fn = item.get("fn") as string;
    const restores = item.has("restores") ? JSON.parse(item.get("restores") as string) : [];
    const request: ProbeRequest = { op: "hub.contract", fn, args: (item.get("args") as PyValue[]).map(toTagged), restores };
    return { test: item.get("test") as string, fn, result: JSON.parse(item.get("result") as string) as unknown, request };
  });
}

describe("第 ⑤g1 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("放回调用当时的快照之后三边重放，逐字与当时的结果相同；各函数的顶层次数钉住", () => {
    const calls = samples();
    const counts = Object.fromEntries([...SNAPSHOT, ...PURE].map((fn) => [fn, calls.filter((item) => item.fn === fn).length]));
    // rework_source、latest_checks、carryable、checks_passed、unfinished_why、carry_back、rework_commits 没有顶层调用（都在 carry_source 等里面），在 hub-exec-scenes 手写
    expect(counts, "各函数的顶层调用次数").toEqual({
      interrupted_attempt: 6, attempts_left: 56, rework_source: 0, latest_checks: 0, cut_off: 5, carryable: 0, checks_passed: 0, unfinished_why: 0, carry_back: 0, carry_source: 51, returned_blockers: 3, failed_attempt: 15, retry_section: 2, failed_checks_brief: 13, failure_lines: 5, report_leftovers: 2, rework_section: 13, unreported_gate_claims: 5, empty_commit: 44, rework_commits: 0, add_modified_files: 6, gate_claims: 16, jev_flag: 6,
    });
    const requests = calls.map((item) => item.request);
    for (const impl of IMPLS) {
      const results = runBatch(impl, requests, REPLAY_TIMEOUT);
      const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(results[at]) !== JSON.stringify(calls[at]?.result));
      const shown = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
      expect(JSON.stringify(shown).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe("[]");
    }
  }, 1_800_000);
});
