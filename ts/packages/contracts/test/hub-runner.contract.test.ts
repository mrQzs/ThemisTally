// 第 ⑤j2 片的契约（迁移计划第 ⑤ 步）：进程模型。kit_hub.py 的 cmd_run、cmd_owner_sweep、cmd_exclusive、supervise_tick、owner_sweep_tick、
// spawn_runner、spawn_task_runner、refuse_dirty_kernel、pause_requested 照调用当时比（同 ⑤j1：交回值、文件、账本新增的部分、git 状态、
// stdout、stderr，另比调用之后的字典与列表参数）；只读的 kernel_files、code_fingerprint、kernel_dirty、kernel_changes 放回调用当时的快照之后
// 逐字比。用例换上的进程对象记成编号与 pid，它的 poll 记成内层调用 proc.poll（⑤j 设计稿第 3 节）；账本里进程自己的 pid 照 pidNormalized
// 换成占位（themistally-04 定：只换等于进程自己的 pid 的值）。
// 用例清单由 scratchpad 的 j2_tests.py 从 j_class.md（整份 tests/test_kit_hub.py 的追踪）机械得出：走到这 13 个函数的 31 条。
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type Impl, type ProbeRequest, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";
import { pidNormalized } from "./runner-fixtures.ts";

const ROOT = scratchDir("runner");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: Record<string, unknown> | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_exclusive_marks_an_owner_sweep_only_when_head_moves", "test_exclusive_runs_the_command_once_executors_are_done",
  "test_fingerprint_survives_a_file_being_swapped", "test_kernel_changes_counts_a_git_error_as_changed",
  "test_kernel_changes_lists_uncommitted_kernel_files", "test_kernel_dirty_reads_git_status",
  "test_landing_waits_for_a_background_gate_sweep", "test_owner_commands_pause_a_busy_task_runner",
  "test_pi_workers_load_the_guard_with_the_kernel_roots", "test_runner_exits_between_steps_once_the_kernel_changes",
  "test_runner_restarts_on_committed_kernel_changes", "test_serial_hub_requeues_interrupted_stages_when_it_starts",
  "test_serial_hub_stays_while_letters_are_held", "test_serial_runner_refuses_while_task_runners_are_alive",
  "test_spawn_runner_returns_while_the_new_hub_runs", "test_supervisor_counts_runners_left_by_its_previous_generation",
  "test_supervisor_keeps_going_after_a_bad_tick", "test_supervisor_picks_up_runner_json_changes_while_running",
  "test_supervisor_puts_due_letters_back_and_starts_their_runner", "test_supervisor_requeues_only_tasks_nobody_is_working_on",
  "test_supervisor_restart_keeps_where_parallel_came_from", "test_supervisor_runs_one_runner_per_task_up_to_the_limit",
  "test_supervisor_starts_one_owner_sweep_at_a_time", "test_supervisor_stays_while_a_runner_works_without_unread_letters",
  "test_supervisor_stays_while_letters_are_held", "test_supervisor_stops_restarting_a_crashing_runner",
  "test_supervisor_ticks_the_owner_sweep_every_round", "test_supervisor_waits_for_a_settled_kernel_before_starting_runners",
  "test_task_runner_exits_for_the_supervisor_on_kernel_changes", "test_the_hub_refuses_to_start_on_a_changed_kernel",
  "test_the_supervisor_passes_the_override_on_to_task_runners",
];
const FLOW = [
  "cmd_run", "cmd_owner_sweep", "cmd_exclusive", "supervise_tick", "owner_sweep_tick", "spawn_runner", "spawn_task_runner", "refuse_dirty_kernel",
  "pause_requested",
];
const SNAPSHOT = ["kernel_files", "code_fingerprint", "kernel_dirty", "kernel_changes"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用）：流程函数照 ⑤j1 记（另记采样那个进程的 pid），只读的照 ⑤e2a 记。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW, ...SNAPSHOT], flow_functions: FLOW,
    snapshot_functions: SNAPSHOT.filter((name) => name !== "kernel_files"), tmp,
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
        inner: JSON.parse(item.get("inner") as string), python, self_pid: Number(item.get("self_pid")),
        ...JSON.parse((item.get("overrides") as string | undefined) ?? "{}"),
      }
      : { op: "hub.contract", fn, args, restores };
    return { test: item.get("test") as string, fn, skip: (item.get("skip") as string | undefined) ?? null, result: JSON.parse(item.get("result") as string) as unknown, request };
  });
  return sampled;
}

/** 照 impls 重放 calls，每一次都要与当时的结果相同（比 JSON 文字，键的次序也算；流程函数先过 pidNormalized）。 */
function replay(calls: readonly Call[], impls: readonly Impl[]): void {
  const requests = calls.map((item) => item.request);
  const flow = (at: number): boolean => calls[at]?.request["op"] === "hub.contract_flow";
  const sampledPid = (at: number): Set<number> => new Set([Number(calls[at]?.request["self_pid"])]);
  const then = (at: number): unknown => (flow(at) ? pidNormalized(calls[at]?.result, sampledPid(at)) : calls[at]?.result);
  for (const impl of impls) {
    const results = runBatch(impl, requests, REPLAY_TIMEOUT);
    const now = (at: number): unknown => {
      if (!flow(at)) return results[at];
      const value = results[at]?.["value"] as Record<string, unknown> | undefined;
      return pidNormalized(value, new Set([...sampledPid(at), Number(value?.["self_pid"])]));
    };
    const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(now(at)) !== JSON.stringify(then(at)));
    // 每处不同先列出哪几栏不同（流程函数的 result、files、ledger、git、args_after、stdout、stderr），再附前两处的全文
    const fields = (at: number): string[] => {
      const before = (then(at) ?? {}) as Record<string, unknown>;
      const replayed = (now(at) ?? {}) as Record<string, unknown>;
      return [...new Set([...Object.keys(before), ...Object.keys(replayed)])].filter((key) => JSON.stringify(before[key]) !== JSON.stringify(replayed[key]));
    };
    const where = bad.map((at) => `${at} ${calls[at]?.test} ${calls[at]?.fn}：${fields(at).join("、")}`);
    const detail = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: then(at), replay: results[at] }));
    const dump = process.env["THEMIS_REPLAY_DUMP"]; // 查不同时用：全部不同处的当时与重放写进这个文件
    if (dump !== undefined && bad.length > 0) {
      writeFileSync(`${dump}-${impl.name}.json`, JSON.stringify(bad.map((at) => ({
        at, test: calls[at]?.test, fn: calls[at]?.fn, then: then(at), replay: results[at], request: calls[at]?.request,
      }))));
    }
    expect(JSON.stringify({ where, detail }).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe(JSON.stringify({ where: [], detail: [] }));
  }
}

const tally = (items: readonly string[]): Record<string, number> =>
  Object.fromEntries([...new Set(items)].sort().map((key) => [key, items.filter((item) => item === key).length]));

describe("第 ⑤j2 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("采样：各函数的最外层调用、跳过的调用与注入的内层调用", () => {
    const all = samples();
    expect(tally(all.map((item) => item.fn)), "各函数的最外层调用次数").toEqual({
      cmd_exclusive: 7,
      cmd_run: 20,
      code_fingerprint: 10,
      kernel_dirty: 4,
      kernel_files: 9, // 第 146 轮：内核文件用例另测 hub 是 ts、python 两种
      owner_sweep_tick: 6,
      pause_requested: 4,
      refuse_dirty_kernel: 3,
      spawn_runner: 1,
      spawn_task_runner: 2,
      supervise_tick: 5,
    });
    // 真起子进程的一条，与调用当时有活的持有者、这次调用又探过的锁（同 ⑤i2）：由手写场景覆盖
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([
      ["test_serial_runner_refuses_while_task_runners_are_alive", "cmd_run", "调用当时有活的持有者：.runners/T002"],
      ["test_spawn_runner_returns_while_the_new_hub_runs", "spawn_runner", "起真子进程"],
      ["test_supervisor_counts_runners_left_by_its_previous_generation", "cmd_run", "调用当时有活的持有者：.runners/T001"],
      ["test_supervisor_starts_one_owner_sweep_at_a_time", "owner_sweep_tick", "调用当时有活的持有者：.owner-sweep"],
      ["test_supervisor_stays_while_a_runner_works_without_unread_letters", "cmd_run", "调用当时有活的持有者：.runners/T001"],
    ]);
    const inner = all.filter((item) => item.skip === null).flatMap((item) => (item.request["inner"] as { fn: string }[] | undefined) ?? []);
    expect(tally(inner.map((entry) => entry.fn)), "注入的内层调用").toEqual({
      "Engine.step": 6,
      Popen: 4,
      _running_attempts: 6,
      code_fingerprint: 20,
      kernel_changes: 20,
      kernel_dirty: 29,
      kernel_settled: 2,
      owner_sweep_tick: 2,
      pid_alive: 7,
      "proc.poll": 26,
      release_held: 3,
      requeue_interrupted: 1,
      sleep: 3,
      spawn_runner: 3,
      spawn_task_runner: 19,
      tasks_with_work: 8,
    });
  }, 1_800_000);
  it("进程模型：放回调用当时的快照、照记录注入后三边重放，交回值、文件、账本、git 状态、调用之后的参数与 stdout、stderr 都与当时的结果相同", () => {
    replay(samples().filter((item) => FLOW.includes(item.fn) && item.skip === null), IMPLS);
  }, 3_600_000);
  it("只读的：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => SNAPSHOT.includes(item.fn));
    expect(calls.length, "顶层调用次数").toBe(23);
    replay(calls, IMPLS);
  }, 1_800_000);
});
