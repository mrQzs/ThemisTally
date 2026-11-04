// 第 ⑤i2 片的契约（迁移计划第 ⑤ 步）：Engine 的选信与协调人一侧、被收掉之后的续接。kit_hub.py 的 Engine.step、fail_stage、coordinator_turn、
// route、deliver_coordinator_letter、write_brief，模块函数 requeue_interrupted、requeue_task、requeue_letters、report_stranded_exec 照调用当时比
// （同 ⑤i1：交回值、调用之后的 ts、几棵树里的文件、账本新增的部分、git 状态、调用之后的字典与列表参数）；只读的 Engine.next_job、finished_turn、
// interrupted_letters、stranded_stages、letters_held、supervisor_busy、runner_may_idle_exit、tasks_with_work、runner_lock 放回调用当时的快照之后
// 三边逐字比（runner_lock 是纯算路径，不存快照）。记录器装 ⑤i 两片的全部函数、只记最外层（⑤i 设计稿第 4 节：装上 step 之后，step 里面的
// worker_job 不再单记），样本只留 ⑤i2 的函数。活锁的跳过只算调用拿过或探过的锁；DirLock 接管时问的 pid_alive 两边都用真的（设计稿第 3 节）。
// 回合出意外那封信照 crashNormalized 比（设计稿第 7 节，样本与三份重放都过它）。用例清单由 scratchpad 的 i_trace2.py、i_classify2.py 从整份
// tests/test_kit_hub.py 的追踪里机械得出（设计稿第 8 节）：走到 ⑤i2 函数的 90 条。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";
import { crashNormalized } from "./engine-fixtures.ts";

const ROOT = scratchDir("step");
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
  "test_a_rate_limited_worker_turn_is_held_and_resumed", "test_a_redelivery_may_hand_in_a_block_instead",
  "test_a_redelivery_that_still_fails_goes_to_the_coordinator_saying_so", "test_a_routine_step_the_guard_refuses_goes_to_the_coordinator_with_the_reason",
  "test_a_routing_cut_short_is_handed_back_with_its_own_words", "test_a_second_hotfix_rework_keeps_the_original_previous_oracle",
  "test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed", "test_a_stranded_exec_stage_is_reported_to_the_owner_once",
  "test_a_timed_out_turn_does_not_use_up_the_format_retry", "test_a_timed_out_voided_turn_is_resumed_not_restarted",
  "test_a_turn_killed_midway_restarts_in_a_new_session_and_is_requeued_only_once", "test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too",
  "test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint", "test_an_audit_return_is_routed_with_the_blockers",
  "test_contract_block_or_executor_conflict_can_send_the_work_upstream", "test_coordinator_api_error_is_not_retried",
  "test_coordinator_letters_pass_the_guard_before_delivery", "test_each_turn_reads_its_own_copy_and_the_copy_is_gone_afterwards",
  "test_exec_waits_for_the_landing_lock_by_holding_its_letter", "test_finished_tasks_remove_their_stage_worktrees",
  "test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile", "test_hotfix_rework_records_the_previous_baseline",
  "test_info_letters_do_not_wake_workers", "test_interrupted_letters_reads_the_ledger_from_the_assignment_on",
  "test_invalid_output_gets_one_retry", "test_model_api_errors_are_not_retried_and_go_to_the_owner",
  "test_owner_adds_a_dependency_found_in_planning", "test_owner_can_order_a_rework_before_the_first_review",
  "test_owner_commands_only_need_the_task_lock_under_a_supervisor", "test_owner_commands_pause_a_busy_task_runner",
  "test_owner_raises_the_attempt_budget", "test_owner_rebases_a_task_before_its_contract_starts",
  "test_owner_takeover_closes_the_task", "test_owner_unsticks_a_stage_nobody_is_working_on",
  "test_passing_and_owner_close_release_the_dependents", "test_paused_worker_stage_can_be_started_again",
  "test_plan_delivery_must_list_its_external_facts", "test_plan_redelivery_replaces_the_external_facts",
  "test_plan_with_only_verified_facts_goes_straight_to_the_contract", "test_requeue_leaves_unread_and_kernel_run_stages_alone",
  "test_rework_starts_a_clean_session", "test_runner_exits_between_steps_once_the_kernel_changes",
  "test_runner_restarts_on_committed_kernel_changes", "test_serial_hub_requeues_interrupted_stages_when_it_starts",
  "test_serial_hub_stays_while_letters_are_held", "test_serial_runner_refuses_while_task_runners_are_alive",
  "test_stage_reworks_are_capped", "test_start_without_brief_is_rejected",
  "test_status_shows_the_parallel_runners", "test_supervisor_counts_runners_left_by_its_previous_generation",
  "test_supervisor_keeps_going_after_a_bad_tick", "test_supervisor_picks_up_runner_json_changes_while_running",
  "test_supervisor_puts_due_letters_back_and_starts_their_runner", "test_supervisor_requeues_only_tasks_nobody_is_working_on",
  "test_supervisor_restart_keeps_where_parallel_came_from", "test_supervisor_runs_one_runner_per_task_up_to_the_limit",
  "test_supervisor_stays_while_a_runner_works_without_unread_letters", "test_supervisor_stays_while_letters_are_held",
  "test_supervisor_stops_restarting_a_crashing_runner", "test_supervisor_ticks_the_owner_sweep_every_round",
  "test_supervisor_waits_for_a_settled_kernel_before_starting_runners", "test_task_runner_exits_for_the_supervisor_on_kernel_changes",
  "test_task_runner_only_takes_its_own_task_letters", "test_tasks_others_wait_for_get_runners_first",
  "test_the_blocked_letter_says_timed_out_again_only_when_it_did", "test_the_coordinator_marker_is_cleared_on_every_way_out_of_the_turn",
  "test_the_gate_hotfix_turn_carries_the_executors_words", "test_the_kernel_leaves_the_last_rework_of_a_stage_to_the_coordinator",
  "test_the_kernel_routes_a_routine_batch_without_waking_the_coordinator", "test_the_owners_rework_words_reach_the_reworked_stage_verbatim",
  "test_three_rejected_coordinator_turns_block_the_task", "test_unverified_external_facts_wait_for_the_owner",
  "test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes", "test_worker_delivery_is_verified_then_forwarded",
  "test_worker_retries_stop_when_the_output_stays_invalid", "test_worker_turn_with_violation_is_not_delivered",
];
const FLOW_I1 = [
  "Engine.escalate", "Engine.worker_job", "Engine.auto_jev", "Engine.stage_workspace", "Engine.verify_delivery", "Engine.after_delivery", "Engine.finish_kernel_stage",
  "Engine.recheck_exec", "Engine.worker_turns", "Engine.redeliver", "Engine.handle_pass", "Engine.after_land", "Engine.after_land_run", "land", "release_dependents",
];
const SNAPSHOT_I1 = ["Engine.output_problem", "resumed_session"];
const FLOW = [
  "Engine.step", "Engine.report_step_error", "Engine.fail_stage", "Engine.coordinator_turn", "Engine.route", "Engine.deliver_coordinator_letter", "Engine.write_brief",
  "requeue_interrupted", "requeue_task", "requeue_letters", "report_stranded_exec",
];
const SNAPSHOT = [
  "Engine.next_job", "finished_turn", "interrupted_letters", "stranded_stages", "letters_held", "supervisor_busy", "runner_may_idle_exit", "tasks_with_work",
  "runner_lock",
];

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
/** 采一次样（几个 it 共用）：流程函数照 ⑤e2b 记，只读的照 ⑤e2a 记；只留 ⑤i2 的函数。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW_I1, ...FLOW, ...SNAPSHOT_I1, ...SNAPSHOT], flow_functions: [...FLOW_I1, ...FLOW],
    snapshot_functions: [...SNAPSHOT_I1, ...SNAPSHOT].filter((name) => name !== "runner_lock"), tmp,
  }, 1_800_000);
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  sampled = (value.get("calls") as PyDict[]).filter((item) => [...FLOW, ...SNAPSHOT].includes(item.get("fn") as string)).map((item) => {
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

/** 三边重放 calls，每一次都要与当时的结果相同（流程函数两边都过 crashNormalized，再比 JSON 文字，键的次序也算）；交回不同的几处。 */
function replay(calls: readonly Call[]): void {
  const requests = calls.map((item) => item.request);
  const flow = (at: number): boolean => calls[at]?.request["op"] === "hub.contract_flow";
  const shown = (at: number, value: unknown): unknown => (flow(at) ? crashNormalized(value as Record<string, unknown>) : value);
  for (const impl of IMPLS) {
    const results = runBatch(impl, requests, REPLAY_TIMEOUT);
    const now = (at: number): unknown => shown(at, flow(at) ? results[at]?.["value"] : results[at]);
    const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(now(at)) !== JSON.stringify(shown(at, calls[at]?.result)));
    const detail = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
    expect(JSON.stringify(detail).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe("[]");
  }
}

const tally = (items: readonly string[]): Record<string, number> =>
  Object.fromEntries([...new Set(items)].sort().map((key) => [key, items.filter((item) => item === key).length]));

describe("第 ⑤i2 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("采样：各函数的最外层调用、跳过的调用、注入的内层调用、state 当场核对与 parametrize 展开", () => {
    const all = samples();
    expect(tally(all.map((item) => item.fn)), "各函数的最外层调用次数").toEqual({
      "Engine.deliver_coordinator_letter": 8,
      "Engine.fail_stage": 3,
      "Engine.next_job": 3,
      "Engine.step": 127,
      "interrupted_letters": 7,
      "letters_held": 2,
      "requeue_interrupted": 62,
      "requeue_task": 1,
      "runner_lock": 264,
      "runner_may_idle_exit": 7,
      "supervisor_busy": 39,
      "tasks_with_work": 40,
    });
    // 只跳调用当时有活的持有者、这次调用又拿过或探过的锁（themistally-04 要的收窄）：5360 的 .land 由 ⑤i1 的场景覆盖，.runners/T001 的
    // 两次由 hub-step-scenes 的“runner 锁被另一个进程拿着”覆盖
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([
      ["test_a_coordinator_turn_cut_off_by_a_kill_is_requeued_and_resumed", "requeue_interrupted", "调用当时有活的持有者：.runners/T001"],
      ["test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed", "requeue_interrupted", "调用当时有活的持有者：.runners/T001"],
      ["test_exec_waits_for_the_landing_lock_by_holding_its_letter", "Engine.step", "调用当时有活的持有者：.land"],
    ]);
    const inner = all.filter((item) => item.skip === null).flatMap((item) => (item.request["inner"] as { fn: string }[] | undefined) ?? []);
    expect(tally(inner.map((entry) => entry.fn)), "注入的内层调用").toEqual({
      "Engine.auto_jev": 2,
      "Engine.verify_delivery": 7,
      "apply_candidate": 2,
      "budget_problems": 1,
      "ensure_worktree": 99,
      "pid_alive": 1,
      "rehearse_landing": 2,
      "release_held": 3,
      "revalidate_contract": 2,
      "role_prompt": 126,
      "run_exec": 3,
      "run_jev": 3,
      "run_pd": 6,
      "runner": 126,
      "seed_whitebox": 1,
      "worktree_root": 114,
    });
    expect(tally(all.filter((item) => item.stateDiffers).map((item) => `${item.test} ${item.fn}`)), "state 当场核对").toEqual({
      "test_stage_reworks_are_capped Engine.deliver_coordinator_letter": 5,
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
  it("改状态的：step、协调人一侧与续接一族放回调用当时的快照、照记录注入后三边重放，与当时的结果相同", () => {
    replay(samples().filter((item) => FLOW.includes(item.fn) && item.skip === null));
  }, 3_600_000);
  it("只读的：next_job、续接与 supervisor 用的几个判断放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => SNAPSHOT.includes(item.fn));
    expect(calls.length, "顶层调用次数").toBe(362);
    replay(calls);
  }, 1_800_000);
});
