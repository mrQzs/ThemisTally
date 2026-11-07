// 第 ⑤j1 片的契约（迁移计划第 ⑤ 步）：站主命令。kit_hub.py 的 cmd_task_new、close、rebase、after、unstick、budget、cleanup，cmd_send、
// cmd_exec_recheck、cmd_take、cmd_status、cmd_metrics、cmd_init 照调用当时比（同 ⑤i 的流程函数：交回值、文件、账本新增的部分、git 状态；
// 另比调用期间写出的 stdout、stderr，标准输入照采样时读到的交回）；只读的 uncommitted_references、turn_metrics、exec_metrics、
// configured_parallel、recorded_sum 放回调用当时的快照之后逐字比。命令的参数是 argparse 的 Namespace，记成仓库与各键（⑤j 设计稿第 3 节）。
// 用例清单由 scratchpad 的 j1_tests.py 从 i_trace2.json（整份 tests/test_kit_hub.py 的追踪）机械得出：走到这 18 个函数的 35 条。
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type Impl, type ProbeRequest, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("commands");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: Record<string, unknown> | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_an_owner_reply_releases_the_gate_claim_and_long_letters_are_refused", "test_answers_to_questions_before_the_contract_are_recorded_as_decisions",
  "test_facts_checked_before_the_plan_is_delivered_says_why", "test_finished_tasks_remove_their_stage_worktrees",
  "test_ledger_session_and_decision_records_with_u2028_are_read_back", "test_metrics_reports_per_turn_costs_and_converts_legacy_session_totals",
  "test_owner_adds_a_dependency_found_in_planning", "test_owner_can_order_a_rework_before_the_first_review",
  "test_owner_raises_the_attempt_budget", "test_owner_rebases_a_task_before_its_contract_starts",
  "test_owner_reply_piped_on_a_non_utf8_console_keeps_its_text", "test_owner_rework_records_the_letter_text",
  "test_owner_takeover_closes_the_task", "test_owner_unsticks_a_stage_nobody_is_working_on",
  "test_parallel_comes_from_the_flag_or_runner_json", "test_passing_and_owner_close_release_the_dependents",
  "test_runner_exits_between_steps_once_the_kernel_changes", "test_runner_restarts_on_committed_kernel_changes",
  "test_serial_hub_requeues_interrupted_stages_when_it_starts", "test_serial_hub_stays_while_letters_are_held",
  "test_serial_runner_refuses_while_task_runners_are_alive", "test_status_shows_the_parallel_runners",
  "test_supervisor_counts_runners_left_by_its_previous_generation", "test_supervisor_keeps_going_after_a_bad_tick",
  "test_supervisor_picks_up_runner_json_changes_while_running", "test_supervisor_restart_keeps_where_parallel_came_from",
  "test_supervisor_runs_one_runner_per_task_up_to_the_limit", "test_supervisor_stays_while_a_runner_works_without_unread_letters",
  "test_supervisor_stays_while_letters_are_held", "test_supervisor_stops_restarting_a_crashing_runner",
  "test_supervisor_ticks_the_owner_sweep_every_round", "test_supervisor_waits_for_a_settled_kernel_before_starting_runners",
  "test_task_brief_must_not_reference_uncommitted_paths", "test_task_new_records_only_unfinished_dependencies",
  "test_unverified_external_facts_wait_for_the_owner", "test_a_task_over_its_spend_cap_is_held_until_the_owner_raises_it",
];
const FLOW = [
  "cmd_init", "cmd_task_new", "cmd_task_close", "cmd_task_rebase", "cmd_task_after", "cmd_task_unstick", "cmd_task_budget", "cmd_task_cap",
  "cmd_task_cleanup", "cmd_send", "cmd_exec_recheck", "cmd_take", "cmd_status", "cmd_metrics",
];
const SNAPSHOT = ["uncommitted_references", "turn_metrics", "exec_metrics", "configured_parallel", "recorded_sum"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
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
/** 采一次样（几个 it 共用）：站主命令照 ⑤i 的流程函数记，只读的照 ⑤e2a 记。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW, ...SNAPSHOT], flow_functions: FLOW,
    snapshot_functions: SNAPSHOT.filter((name) => name !== "recorded_sum"), tmp,
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
        inner: JSON.parse(item.get("inner") as string), python, stdin: item.get("stdin") ?? null, inputs: plainJson(item.get("inputs")), absent: item.get("absent"),
        constants: plainJson(item.get("constants")),
        ...JSON.parse((item.get("overrides") as string | undefined) ?? "{}"),
      }
      : { op: "hub.contract", fn, args, restores };
    return { test: item.get("test") as string, fn, skip: (item.get("skip") as string | undefined) ?? null, result: JSON.parse(item.get("result") as string) as unknown, request };
  });
  return sampled;
}

/** 照 impls 重放 calls，每一次都要与当时的结果相同（比 JSON 文字，键的次序也算）。 */
function replay(calls: readonly Call[], impls: readonly Impl[]): void {
  const requests = calls.map((item) => item.request);
  const flow = (at: number): boolean => calls[at]?.request["op"] === "hub.contract_flow";
  for (const impl of impls) {
    const results = runBatch(impl, requests, REPLAY_TIMEOUT);
    const now = (at: number): unknown => (flow(at) ? results[at]?.["value"] : results[at]);
    const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(now(at)) !== JSON.stringify(calls[at]?.result));
    // 每处不同先列出哪几栏不同（流程函数的 result、files、ledger、git、stdout、stderr），再附前两处的全文
    const fields = (at: number): string[] => {
      const then = (calls[at]?.result ?? {}) as Record<string, unknown>;
      const replayed = (now(at) ?? {}) as Record<string, unknown>;
      return [...new Set([...Object.keys(then), ...Object.keys(replayed)])].filter((key) => JSON.stringify(then[key]) !== JSON.stringify(replayed[key]));
    };
    const where = bad.map((at) => `${at} ${calls[at]?.test} ${calls[at]?.fn}：${fields(at).join("、")}`);
    const detail = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
    const dump = process.env["THEMIS_REPLAY_DUMP"]; // 查不同时用：全部不同处的当时与重放写进这个文件
    if (dump !== undefined && bad.length > 0) {
      writeFileSync(`${dump}-${impl.name}.json`, JSON.stringify(bad.map((at) => ({
        at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at], request: calls[at]?.request,
      }))));
    }
    expect(JSON.stringify({ where, detail }).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe(JSON.stringify({ where: [], detail: [] }));
  }
}

const tally = (items: readonly string[]): Record<string, number> =>
  Object.fromEntries([...new Set(items)].sort().map((key) => [key, items.filter((item) => item === key).length]));

describe("第 ⑤j1 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("采样：各函数的最外层调用、跳过的调用与注入的内层调用", () => {
    const all = samples();
    expect(tally(all.map((item) => item.fn)), "各函数的最外层调用次数").toEqual({
      cmd_metrics: 1,
      cmd_send: 20,
      cmd_status: 1,
      cmd_task_after: 10,
      cmd_task_budget: 10,
      cmd_task_cap: 4,
      cmd_task_cleanup: 4,
      cmd_task_close: 6,
      cmd_task_new: 7,
      cmd_task_rebase: 7,
      cmd_task_unstick: 8,
      configured_parallel: 69,
      exec_metrics: 2,
      turn_metrics: 6,
    });
    // 只跳调用当时有活的持有者、这次调用又探过的锁（同 ⑤i2）：用例自己拿着 T002 的 runner 锁看 status，由手写场景覆盖
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([
      ["test_status_shows_the_parallel_runners", "cmd_status", "调用当时有活的持有者：.runners/T002"],
    ]);
    const inner = all.filter((item) => item.skip === null).flatMap((item) => (item.request["inner"] as { fn: string }[] | undefined) ?? []);
    expect(tally(inner.map((entry) => entry.fn)), "注入的内层调用").toEqual({
      contract_requirements: 1,
      pid_alive: 2,
      run_pd: 4,
      tidy_finished: 1,
    });
  }, 1_800_000);
  it("站主命令：放回调用当时的快照、照记录注入后三边重放，交回值、文件、账本、git 状态与 stdout、stderr 都与当时的结果相同", () => {
    replay(samples().filter((item) => FLOW.includes(item.fn) && item.skip === null), IMPLS);
  }, 3_600_000);
  it("只读的：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => SNAPSHOT.includes(item.fn));
    expect(calls.length, "顶层调用次数").toBe(77);
    replay(calls, IMPLS);
  }, 1_800_000);
});
