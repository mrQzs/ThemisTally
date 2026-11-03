// 第 ⑤h2 片的契约（迁移计划第 ⑤ 步）：后台回归与落地预演。kit_hub.py 的 regression_sweep、rehearse_landing、rehearsal_letter、
// mark_owner_moved、owner_sweep、ts_install_if_stale 照调用当时比（同 ⑤e2b：交回值，调用之后的 ts，几棵树里新建、改动、删掉的文件，账本新增的
// 部分，git 状态）。sweep_gates 与建临时 worktree 的 mkdtemp 在 regression_sweep、rehearse_landing、owner_sweep 里一律照记录注入（门禁基准不在
// 重放里真跑，真跑在 hub-sweep-scenes）；用例当时换掉的 worktree_root、rehearse_landing、ts_install_if_stale 与调度器的 find_bun、
// read_kernel_impl 照记录注入。ts_install_if_stale 的 runner 给了时，采样换成录制包装、按内层的 run_supervised（内层名 ts_runner）注入，样本里
// runner 记成 None：stdout、stderr 是文件对象时记成 <temporary> 与 same，环境与各自的 kernel_env() 比，输出记原始字节、重放时原样写进 stdout。
// read_owner_sweep 放回调用当时的快照之后三边逐字比。语料只有 tests/test_kit_hub.py 这一个来源：用例清单是 ⑤h1 挂插件跑全部用例时记下的。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("sweep");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_a_failed_ts_reinstall_writes_to_the_owner", "test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain",
  "test_after_land_rehearses_the_other_active_candidates", "test_after_land_reports_the_regression_to_the_owner",
  "test_background_sweeps_hold_off_other_landings_while_they_run", "test_exclusive_marks_an_owner_sweep_only_when_head_moves",
  "test_exec_delivery_carries_the_rehearsal_and_warns_the_owner", "test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks",
  "test_landing_rehearsal_reports_commits_that_no_longer_apply", "test_landing_skips_an_empty_rework_commit",
  "test_no_ts_reinstall_while_everything_runs_on_python", "test_owner_commits_get_a_gate_sweep_and_rehearsals",
  "test_owner_sweeps_reinstall_stale_ts_dependencies_under_the_land_lock", "test_owner_sweeps_start_with_the_ts_reinstall",
  "test_regression_sweep_runs_every_gate_baseline_on_the_new_tip", "test_supervisor_counts_runners_left_by_its_previous_generation",
  "test_supervisor_keeps_going_after_a_bad_tick", "test_supervisor_picks_up_runner_json_changes_while_running",
  "test_supervisor_runs_one_runner_per_task_up_to_the_limit", "test_supervisor_starts_one_owner_sweep_at_a_time",
  "test_supervisor_stays_while_a_runner_works_without_unread_letters", "test_supervisor_stays_while_letters_are_held",
  "test_supervisor_stops_restarting_a_crashing_runner", "test_supervisor_waits_for_a_settled_kernel_before_starting_runners",
];
const FLOW = ["regression_sweep", "rehearse_landing", "rehearsal_letter", "mark_owner_moved", "owner_sweep", "ts_install_if_stale"];
const SNAPSHOT = ["read_owner_sweep"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用）：流程函数照 ⑤e2b 记，read_owner_sweep 照 ⑤e2a 记。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, {
    op: "hub.audit_samples", tests: TESTS, functions: [...FLOW, ...SNAPSHOT], flow_functions: FLOW, snapshot_functions: SNAPSHOT, tmp,
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
    return {
      test: item.get("test") as string, fn, skip: (item.get("skip") as string | undefined) ?? null, result: JSON.parse(item.get("result") as string) as unknown, request,
    };
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

describe("第 ⑤h2 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("改状态的六个函数：放回调用当时的快照、照记录注入后三边重放，交回值、ts、文件、账本、git 状态都与当时的结果相同", () => {
    const all = samples().filter((item) => FLOW.includes(item.fn));
    const counts = Object.fromEntries(FLOW.map((fn) => [fn, all.filter((item) => item.fn === fn).length]));
    expect(counts, "各函数的顶层调用次数").toEqual({ regression_sweep: 2, rehearse_landing: 15, rehearsal_letter: 2, mark_owner_moved: 7, owner_sweep: 6, ts_install_if_stale: 7 });
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([]);
    const inner = all.flatMap((item) => item.request["inner"] as { fn: string }[]);
    const injected = Object.fromEntries([...new Set(inner.map((entry) => entry.fn))].sort().map((fn) => [fn, inner.filter((entry) => entry.fn === fn).length]));
    expect(injected, "注入的内层调用").toEqual({
      find_bun: 4, mkdtemp: 16, read_kernel_impl: 6, rehearse_landing: 1, sweep_gates: 14, ts_install_if_stale: 1, ts_runner: 3, worktree_root: 15,
    });
    replay(all);
  }, 1_800_000);
  it("read_owner_sweep：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => !FLOW.includes(item.fn));
    expect(calls.length, "顶层调用次数").toBe(43);
    replay(calls);
  }, 1_800_000);
});
