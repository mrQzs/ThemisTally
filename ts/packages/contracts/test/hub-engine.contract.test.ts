// 第 ⑤i1 片的契约（迁移计划第 ⑤ 步）：Engine 的工人一侧与结项。kit_hub.py 的 Engine.escalate、worker_job、auto_jev、stage_workspace、
// verify_delivery、after_delivery、finish_kernel_stage、recheck_exec、worker_turns、redeliver、handle_pass、after_land、after_land_run，
// 模块函数 land、release_dependents，照调用当时比（同 ⑤e2b：交回值、调用之后的 ts、几棵树里的文件、账本新增的部分、git 状态；⑤i 另比
// 调用之后的字典与列表参数）。采样器给本片的每个函数装“只记最外层”的记录器（⑤i 设计稿第 4 节）：Engine 的 runner 一律照记录注入，
// 比 prompt 全文、fresh、session_id、retry_of 与输入目录里的文件；用例当时换掉的内层函数照记录注入，其余真跑；时刻、信编号与
// time.time 钉住；名册的改动、用例改过的常量、读出 state 时的 seen 随样本带上。只读的 Engine.output_problem、resumed_session 放回
// 调用当时的快照之后三边逐字比。用例清单由 scratchpad 的 i_trace2.py、i_classify2.py 从整份 tests/test_kit_hub.py 的追踪里机械得出
// （设计稿第 8 节）：走到 ⑤i1 函数的 72 条；带 parametrize 的 4 条由采样器展开成 15 个“名[i]”。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("engine");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_a_batch_that_is_not_routine_tells_the_coordinator_why", "test_a_clean_slice_runs_from_task_to_pass_without_a_coordinator_turn",
  "test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number", "test_a_coordinator_turn_cut_off_by_a_kill_is_requeued_and_resumed",
  "test_a_coordinator_turn_that_never_finished_restarts_fresh_and_only_once", "test_a_crashed_turn_tells_the_owner_which_letters_were_taken",
  "test_a_crashed_worker_turn_leaves_the_stage_restartable", "test_a_delivery_that_fails_the_check_is_redone_in_the_same_session",
  "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline", "test_a_jev_cut_off_by_a_kill_is_rerun",
  "test_a_partly_routed_batch_records_what_went_out", "test_a_passing_delivery_clears_the_last_check",
  "test_a_rate_limited_coordinator_turn_is_held_and_resumed", "test_a_rate_limited_turn_that_also_broke_the_rules_is_not_held",
  "test_a_task_over_its_spend_cap_is_held_until_the_owner_raises_it",
  "test_a_rate_limited_worker_turn_is_held_and_resumed", "test_a_redelivery_may_hand_in_a_block_instead",
  "test_a_redelivery_that_still_fails_goes_to_the_coordinator_saying_so", "test_a_resumed_turn_without_a_usable_session_starts_fresh",
  "test_a_routine_step_the_guard_refuses_goes_to_the_coordinator_with_the_reason", "test_a_routing_cut_short_is_handed_back_with_its_own_words",
  "test_a_second_hotfix_rework_keeps_the_original_previous_oracle", "test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed",
  "test_a_timed_out_turn_does_not_use_up_the_format_retry", "test_a_timed_out_voided_turn_is_resumed_not_restarted",
  "test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too", "test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint",
  "test_after_land_rehearses_the_other_active_candidates", "test_after_land_reports_the_regression_to_the_owner",
  "test_background_sweeps_hold_off_other_landings_while_they_run", "test_candidate_defects_go_to_the_final_review_which_cannot_pass_them",
  "test_contract_block_or_executor_conflict_can_send_the_work_upstream", "test_coordinator_api_error_is_not_retried",
  "test_coordinator_letters_pass_the_guard_before_delivery", "test_each_turn_reads_its_own_copy_and_the_copy_is_gone_afterwards",
  "test_exec_delivery_carries_the_rehearsal_and_warns_the_owner", "test_exec_recheck_resumes_an_execution_the_hub_was_killed_in",
  "test_exec_recheck_revisits_the_last_attempt_without_rerunning", "test_exec_waits_for_the_landing_lock_by_holding_its_letter",
  "test_finished_tasks_remove_their_stage_worktrees", "test_first_review_report_must_map_every_dod",
  "test_gate_post_workspace_is_seeded_before_the_gate_starts", "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff",
  "test_gate_rework_resets_a_worktree_the_state_lost_track_of", "test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile",
  "test_hotfix_rework_records_the_previous_baseline", "test_info_letters_do_not_wake_workers",
  "test_invalid_output_gets_one_retry", "test_kernel_runs_jev_right_after_a_passing_delivery",
  "test_landing_waits_for_other_tasks_executors", "test_model_api_errors_are_not_retried_and_go_to_the_owner",
  "test_owner_adds_a_dependency_found_in_planning", "test_owner_takeover_closes_the_task",
  "test_passing_and_owner_close_release_the_dependents", "test_paused_worker_stage_can_be_started_again",
  "test_plan_delivery_must_list_its_external_facts", "test_plan_redelivery_replaces_the_external_facts",
  "test_plan_with_only_verified_facts_goes_straight_to_the_contract", "test_release_moves_the_base_once_every_dependency_is_done",
  "test_review_history_survives_rework_and_seals_the_next_round", "test_rework_starts_a_clean_session",
  "test_start_without_brief_is_rejected", "test_the_blocked_letter_says_timed_out_again_only_when_it_did",
  "test_the_coordinator_marker_is_cleared_on_every_way_out_of_the_turn", "test_the_gate_hotfix_turn_carries_the_executors_words",
  "test_the_kernel_leaves_the_last_rework_of_a_stage_to_the_coordinator", "test_the_owners_rework_words_reach_the_reworked_stage_verbatim",
  "test_three_rejected_coordinator_turns_block_the_task", "test_unverified_external_facts_wait_for_the_owner",
  "test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes", "test_worker_delivery_is_verified_then_forwarded",
  "test_worker_retries_stop_when_the_output_stays_invalid", "test_worker_turn_with_violation_is_not_delivered",
];
const FLOW = [
  "Engine.escalate", "Engine.worker_job", "Engine.auto_jev", "Engine.stage_workspace", "Engine.verify_delivery", "Engine.after_delivery", "Engine.finish_kernel_stage",
  "Engine.recheck_exec", "Engine.worker_turns", "Engine.redeliver", "Engine.handle_pass", "Engine.after_land", "Engine.after_land_run", "land", "release_dependents",
];
const SNAPSHOT = ["Engine.output_problem", "resumed_session"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
  readonly stateDiffers: boolean;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

/** 样本里的 seen 与常量是 PyValue（Map、bigint），换回请求里的普通 JSON。 */
function plainJson(value: PyValue | undefined): unknown {
  if (value instanceof Map) return Object.fromEntries([...value].map(([key, item]) => [String(key), plainJson(item)]));
  if (Array.isArray(value)) return value.map(plainJson);
  return typeof value === "bigint" ? Number(value) : value ?? null;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用）：流程函数照 ⑤e2b 记，只读的照 ⑤e2a 记。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW, ...SNAPSHOT], flow_functions: FLOW, snapshot_functions: SNAPSHOT, tmp,
  }, 1_800_000);
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
        inner: JSON.parse(item.get("inner") as string), python, ts_alias: item.get("ts_alias") ?? null, state_seen: plainJson(item.get("state_seen")),
        fake_engine: item.get("fake_engine") ?? null, constants: plainJson(item.get("constants")), ...JSON.parse((item.get("overrides") as string | undefined) ?? "{}"),
      }
      : { op: "hub.contract", fn, args, restores };
    return {
      test: item.get("test") as string, fn, skip: (item.get("skip") as string | undefined) ?? null, stateDiffers: item.get("state_differs") === true,
      result: JSON.parse(item.get("result") as string) as unknown, request,
    };
  });
  return sampled;
}

/** 三边重放 calls，每一次都要与当时的结果相同（JSON 文字逐字，键的次序也算）；交回不同的几处（最多两处，截断）。 */
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

const tally = (items: readonly string[]): Record<string, number> =>
  Object.fromEntries([...new Set(items)].sort().map((key) => [key, items.filter((item) => item === key).length]));

describe("第 ⑤i1 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("采样：各函数的最外层调用、跳过的调用、注入的内层调用、state 当场核对与 parametrize 展开", () => {
    const all = samples();
    expect(tally(all.map((item) => item.fn)), "各函数的最外层调用次数").toEqual({
      "Engine.after_delivery": 4,
      "Engine.after_land": 6,
      "Engine.auto_jev": 5,
      "Engine.escalate": 3,
      "Engine.handle_pass": 2,
      "Engine.recheck_exec": 6,
      "Engine.stage_workspace": 4,
      "Engine.verify_delivery": 4,
      "Engine.worker_job": 62,
      "Engine.worker_turns": 2,
      "land": 2,
      "release_dependents": 6,
      "resumed_session": 53,
    });
    // 只跳调用当时目录锁有活的持有者的（设计稿第 4 节）：5360 由用例自己拿着落地锁，由 hub-engine-scenes 的手写场景覆盖
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([["test_exec_waits_for_the_landing_lock_by_holding_its_letter", "Engine.worker_job", "调用当时有活的持有者：.land"]]);
    const inner = all.filter((item) => item.skip === null).flatMap((item) => (item.request["inner"] as { fn: string }[] | undefined) ?? []);
    expect(tally(inner.map((entry) => entry.fn)), "注入的内层调用").toEqual({
      "Engine.auto_jev": 2,
      "Engine.verify_delivery": 7,
      "_running_attempts": 2,
      "apply_candidate": 4,
      "budget_problems": 1,
      "engine.after_land": 1,
      "engine.handle_pass": 1,
      "ensure_worktree": 49,
      "finalize": 2,
      "pid_alive": 3,
      "regression_sweep": 2,
      "rehearse_landing": 7,
      "revalidate_contract": 2,
      "role_prompt": 78,
      "run_exec": 6,
      "run_jev": 5,
      "run_pd": 10,
      "runner": 78,
      "seed_whitebox": 2,
      "tidy_finished": 1,
      "worktree_root": 64,
    });
    // 传进来的 state 与调用当时的 state.json 不同的（用例在内存里改过、没存盘），重放照记下的 state 传
    expect(tally(all.filter((item) => item.stateDiffers).map((item) => `${item.test} ${item.fn}`)), "state 当场核对").toEqual({
      "test_finished_tasks_remove_their_stage_worktrees Engine.handle_pass": 1,
      "test_kernel_runs_jev_right_after_a_passing_delivery Engine.auto_jev": 5,
      "test_owner_adds_a_dependency_found_in_planning release_dependents": 1,
      "test_owner_takeover_closes_the_task release_dependents": 1,
      "test_release_moves_the_base_once_every_dependency_is_done release_dependents": 3,
    });
    expect([...new Set(all.map((item) => item.test).filter((test) => test.includes("[")))].sort(), "parametrize 展开的样本").toEqual([
      "test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too[0]",
      "test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too[1]",
      "test_plan_delivery_must_list_its_external_facts[0]",
      "test_plan_delivery_must_list_its_external_facts[1]",
      "test_plan_delivery_must_list_its_external_facts[2]",
      "test_plan_delivery_must_list_its_external_facts[3]",
      "test_plan_delivery_must_list_its_external_facts[4]",
      "test_the_blocked_letter_says_timed_out_again_only_when_it_did[0]",
      "test_the_blocked_letter_says_timed_out_again_only_when_it_did[1]",
      "test_the_blocked_letter_says_timed_out_again_only_when_it_did[2]",
      "test_the_blocked_letter_says_timed_out_again_only_when_it_did[3]",
      "test_the_blocked_letter_says_timed_out_again_only_when_it_did[4]",
      "test_worker_retries_stop_when_the_output_stays_invalid[0]",
      "test_worker_retries_stop_when_the_output_stays_invalid[1]",
      "test_worker_retries_stop_when_the_output_stays_invalid[2]",
    ]);
  }, 1_800_000);
  it("改状态的 Engine 方法与 land、release_dependents：放回调用当时的快照、照记录注入后三边重放，与当时的结果相同", () => {
    replay(samples().filter((item) => FLOW.includes(item.fn) && item.skip === null));
  }, 3_600_000);
  it("只读的 resumed_session（output_problem 只在流程里被调到）：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => SNAPSHOT.includes(item.fn));
    expect(calls.length, "顶层调用次数").toBe(53);
    replay(calls);
  }, 1_800_000);
});
