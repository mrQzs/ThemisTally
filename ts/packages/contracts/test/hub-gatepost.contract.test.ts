// 第 ⑤f 片的契约（迁移计划第 ⑤ 步）：战后门禁与变异。kit_hub.py 的 apply_candidate、ensure_worktree、seed_whitebox、accept_gate_post、
// run_mutations 照调用当时比（同 ⑤e2b：交回值，调用之后的 ts，几棵树里新建、改动、删掉的文件，账本新增的部分，git 状态）；mkdtemp 建出的
// worktree 是新的一棵树，重放前先删掉。用例当时换掉的 run_pd、worktree_root，以及白盒测试那一次 run_supervised 与建 worktree 的 mkdtemp
// 照记录注入（参数逐次核对；run_supervised 的环境变量各自与当场的 kernel_pytest_env() 整份比，值不进记录）。attempt_base、mutant_timeout、
// unmutated_problems、gate_spec、unchanged_mismatches、expected_missed_everywhere、candidate_defects、defect_matches、defect_match_problems、
// mutation_problems 放回调用当时的快照之后三边逐字比。语料只有 tests/test_kit_hub.py 这一个来源。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("gatepost");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_a_cut_off_attempt_is_continued_instead_of_restarted", "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted",
  "test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_a_gate_turn_hands_in_through_deliver", "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline",
  "test_a_kernel_revise_without_an_audit_says_so", "test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too",
  "test_a_timed_out_attempt_is_continued_instead_of_restarted", "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_exec_rework_reports_when_the_rework_base_cannot_be_built",
  "test_expect_missed_on_every_command_is_an_undeclared_equivalence",
  "test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed",
  "test_failed_integrate_takes_the_landed_commits_back_off_the_branch", "test_finalize_lands_the_oracle_commit_first_and_can_be_retried",
  "test_finalize_lands_the_rework_chain_before_integrating", "test_finished_tasks_remove_their_stage_worktrees",
  "test_gate_post_checks_the_anchors_before_mutating", "test_gate_post_judges_mutations_from_the_record",
  "test_gate_post_may_leave_the_candidate_red_with_evidence", "test_gate_post_reads_the_spec_file_and_names_entries_left_unchanged",
  "test_gate_pre_baseline_must_fail_on_assertions", "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff",
  "test_gate_pre_rejects_a_baseline_that_does_not_collect", "test_gate_rework_resets_a_worktree_the_state_lost_track_of",
  "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it",
  "test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks", "test_landing_rehearsal_reports_commits_that_no_longer_apply",
  "test_landing_skips_an_empty_rework_commit", "test_multi_command_mutation_verdict_splits_by_command_and_names_the_idle_one",
  "test_mutant_timeout_follows_the_whitebox_time", "test_mutation_verdict_reads_the_record_not_the_exit_code",
  "test_mutations_must_cover_the_changed_files", "test_new_attempt_gate_post_starts_from_the_previous_whitebox",
  "test_owner_commits_get_a_gate_sweep_and_rehearsals", "test_owner_takeover_closes_the_task",
  "test_post_gate_worktree_starts_from_the_attempt_base", "test_pytest_outcomes_reads_the_summary_not_the_captured_output",
  "test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again", "test_the_review_record_names_the_model_of_the_final_audit_turn",
];
const FLOW = ["apply_candidate", "ensure_worktree", "seed_whitebox", "accept_gate_post", "run_mutations"];
const SNAPSHOT = ["attempt_base", "unmutated_problems", "gate_spec"];
const PURE = ["mutant_timeout", "unchanged_mismatches", "expected_missed_everywhere", "candidate_defects", "defect_matches", "defect_match_problems", "mutation_problems"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用）：流程函数照 ⑤e2b 记，其余照 ⑤e2a 记（读文件的三个带调用当时的快照）。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW, ...SNAPSHOT, ...PURE], flow_functions: FLOW, snapshot_functions: SNAPSHOT, tmp,
  }, 900_000);
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  sampled = (value.get("calls") as PyDict[]).map((item) => {
    const fn = item.get("fn") as string;
    const args = (item.get("args") as PyValue[]).map(toTagged);
    const restores = item.has("restores") ? JSON.parse(item.get("restores") as string) : [];
    const request: ProbeRequest = FLOW.includes(fn)
      ? {
        op: "hub.contract_flow", fn, args, restores, roots: item.get("roots"), fresh: item.get("fresh"), pin: Number(item.get("pin")), replaced: item.get("replaced"),
        inner: JSON.parse(item.get("inner") as string), python,
      }
      : { op: "hub.contract", fn, args, restores };
    return { test: item.get("test") as string, fn, result: JSON.parse(item.get("result") as string) as unknown, request };
  });
  return sampled;
}

/** 三边重放 calls，每一次都要与当时的结果相同；交回不同的几处（最多两处，截断）。 */
function replay(calls: readonly Call[]): void {
  const requests = calls.map((item) => item.request);
  for (const impl of IMPLS) {
    const results = runBatch(impl, requests, REPLAY_TIMEOUT);
    const shownOf = (at: number): unknown => (calls[at]?.request["op"] === "hub.contract_flow" ? results[at]?.["value"] : results[at]);
    const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(shownOf(at)) !== JSON.stringify(calls[at]?.result));
    const shown = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
    expect(JSON.stringify(shown).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe("[]");
  }
}

describe("第 ⑤f 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("改状态的五个函数：放回调用当时的快照、照记录注入后三边重放，交回值、ts、文件、账本、git 状态都与当时的结果相同；每个函数都有样本", () => {
    const calls = samples().filter((item) => FLOW.includes(item.fn));
    const counts = Object.fromEntries(FLOW.map((fn) => [fn, calls.filter((item) => item.fn === fn).length]));
    expect(counts, "各函数的顶层调用次数").toEqual({ apply_candidate: 1, ensure_worktree: 16, seed_whitebox: 4, accept_gate_post: 25, run_mutations: 2 });
    // 注入确实走到了：各内层调用记下的次数，新建 worktree（第三棵树）的次数；白盒那一次的环境变量两边都与当场的 kernel_pytest_env() 相同
    const inner = calls.flatMap((item) => item.request["inner"] as { fn: string; env?: unknown }[]);
    const injected = Object.fromEntries([...new Set(inner.map((entry) => entry.fn))].sort().map((fn) => [fn, inner.filter((entry) => entry.fn === fn).length]));
    expect({ injected, fresh: calls.filter((item) => (item.request["fresh"] as string[]).length).length }, "注入的内层调用").toEqual({
      injected: { mkdtemp: 13, run_pd: 24, run_supervised: 25, worktree_root: 13 }, fresh: 13,
    });
    expect(inner.filter((entry) => entry.fn === "run_supervised" && entry.env !== true).length, "白盒那一次的环境变量").toBe(0);
    replay(calls);
  }, 1_800_000);
  it("其余十个：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => !FLOW.includes(item.fn));
    const counts = Object.fromEntries([...SNAPSHOT, ...PURE].map((fn) => [fn, calls.filter((item) => item.fn === fn).length]));
    // gate_spec、unchanged_mismatches、defect_match_problems 没有顶层调用（都在 run_mutations、accept_gate_post 里面），在第二部分手写
    expect(counts, "各函数的顶层调用次数").toEqual({
      attempt_base: 74, unmutated_problems: 3, gate_spec: 0, mutant_timeout: 4, unchanged_mismatches: 0, expected_missed_everywhere: 3, candidate_defects: 1,
      defect_matches: 8, defect_match_problems: 0, mutation_problems: 14,
    });
    replay(calls);
  }, 1_800_000);
});
