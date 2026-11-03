// 第 ⑤h1 片的契约（迁移计划第 ⑤ 步）：结项与落地、结项后的收尾。kit_hub.py 的 finalize、landing_blockers、retire_attempts、tidy_finished、
// remove_workspaces、commit_records、land_oracle、land_rework_chain、undo_landing、record_pass 照调用当时比（同 ⑤e2b：交回值，调用之后的 ts，
// 几棵树里新建、改动、删掉的文件，账本新增的部分，git 状态；提交作者与时刻钉住，挑上分支的提交 SHA 才比得出）。用例当时换掉的 run_pd、
// 调度器的 _running_attempts，以及 landing_blockers 里的 pid_alive（标记记的是采样进程的 pid）照记录注入（参数逐次核对）。landed_meanwhile、landing_chain、on_branch 放回调用当时的快照之后三边逐字比，
// landing_records 是纯函数。语料只有 tests/test_kit_hub.py 这一个来源：用例清单是挂插件跑一遍全部用例，看谁调到了这些函数定的
// （test_status_shows_the_parallel_runners 要 pytest 的 capsys，采样器不搭，不收）。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("land");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain", "test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too",
  "test_background_sweeps_hold_off_other_landings_while_they_run", "test_exclusive_marks_an_owner_sweep_only_when_head_moves",
  "test_exclusive_runs_the_command_once_executors_are_done", "test_exec_window_marks_the_run_and_waits_for_a_landing",
  "test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed", "test_failed_integrate_takes_the_landed_commits_back_off_the_branch",
  "test_finalize_lands_the_oracle_commit_first_and_can_be_retried", "test_finalize_lands_the_rework_chain_before_integrating",
  "test_finished_tasks_remove_their_stage_worktrees", "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it",
  "test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks", "test_landing_rehearsal_reports_commits_that_no_longer_apply",
  "test_landing_skips_an_empty_rework_commit", "test_landing_waits_for_a_background_gate_sweep", "test_landing_waits_for_other_tasks_executors",
  "test_owner_commits_get_a_gate_sweep_and_rehearsals", "test_owner_takeover_closes_the_task", "test_records_commit_takes_only_the_tasks_plans_and_reviews",
  "test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again",
];
const FLOW = [
  "finalize", "landing_blockers", "retire_attempts", "tidy_finished", "remove_workspaces", "commit_records", "land_oracle", "land_rework_chain", "undo_landing",
  "record_pass",
];
const SNAPSHOT = ["landed_meanwhile", "landing_chain", "on_branch"];
const PURE = ["landing_records"];
/**
 * 重放不出来的几次（用例、函数、在这条用例里是第几次调它）：调用期间改掉的东西在快照与注入之外，三边重放都看不到当时的样子。对应的分支
 * 在 hub-land-scenes 手写（所有路径都在场景的树里）。
 */
const UNREPLAYABLE: Record<string, string> = {
  "test_finished_tasks_remove_their_stage_worktrees/tidy_finished/0": "阶段 worktree 在仓库外，几次调用之间被用例删改，快照不带；见 hub-land-scenes 的“remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在……”",
  "test_finished_tasks_remove_their_stage_worktrees/tidy_finished/1": "同上；见 hub-land-scenes 的“remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在……”",
  "test_finished_tasks_remove_their_stage_worktrees/tidy_finished/2": "同上；见 hub-land-scenes 的“remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在……”",
  "test_finished_tasks_remove_their_stage_worktrees/tidy_finished/3": "同上；见 hub-land-scenes 的“remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在……”",
  "test_finished_tasks_remove_their_stage_worktrees/retire_attempts/1": "meta.json 记的 worktree 在仓库外，调用当时已经删了，重放时又在；见 hub-land-scenes 的“retire_attempts：没开跑且 worktree 干净……”",
  "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it/finalize/0": "假的 integrate 在调用期间 reset --hard 挪了分支，注入只重放文件；见 hub-land-scenes 的“undo_landing 的四种结局……”（直接调 undo_landing：已经不是祖先）",
};

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
  /** 对上了 UNREPLAYABLE 的哪一条。 */
  readonly unreplayable?: string | null;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用）：流程函数照 ⑤e2b 记，其余照 ⑤e2a 记（读仓库的三个带调用当时的快照）。 */
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
    return {
      test: item.get("test") as string, fn, skip: (item.get("skip") as string | undefined) ?? null, result: JSON.parse(item.get("result") as string) as unknown, request,
    };
  });
  const seen = new Map<string, number>();
  sampled = sampled.map((item) => {
    const key = `${item.test}/${item.fn}`;
    const ordinal = seen.get(key) ?? 0;
    seen.set(key, ordinal + 1);
    const hit = `${key}/${ordinal}` in UNREPLAYABLE ? `${key}/${ordinal}` : null;
    return { ...item, skip: item.skip ?? (hit === null ? null : (UNREPLAYABLE[hit] as string)), unreplayable: hit };
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

describe("第 ⑤h1 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("改状态的十个函数：放回调用当时的快照、照记录注入后三边重放，交回值、ts、文件、账本、git 状态都与当时的结果相同", () => {
    const all = samples().filter((item) => FLOW.includes(item.fn));
    const counts = Object.fromEntries(FLOW.map((fn) => [fn, all.filter((item) => item.fn === fn).length]));
    // remove_workspaces、undo_landing、record_pass 没有顶层调用（都在 tidy_finished、finalize 里面），走 TS 自己的实现；没走到的分支在 hub-land-scenes 手写
    expect(counts, "各函数的顶层调用次数").toEqual({
      finalize: 20, landing_blockers: 19, retire_attempts: 4, tidy_finished: 5, remove_workspaces: 0, commit_records: 2, land_oracle: 2, land_rework_chain: 3,
      undo_landing: 0, record_pass: 0,
    });
    // 表里每一条恰好对上一次调用（过期的键会少一条）；采样器自己标的 skip 一条也没有
    expect(all.map((item) => item.unreplayable ?? null).filter((key) => key !== null).sort(), "UNREPLAYABLE 逐条对上").toEqual(Object.keys(UNREPLAYABLE).sort());
    expect(all.filter((item) => item.skip !== null && !item.unreplayable).map((item) => [item.test, item.fn, item.skip]), "采样器标的 skip").toEqual([]);
    const calls = all.filter((item) => item.skip === null);
    const inner = calls.flatMap((item) => item.request["inner"] as { fn: string }[]);
    const injected = Object.fromEntries([...new Set(inner.map((entry) => entry.fn))].sort().map((fn) => [fn, inner.filter((entry) => entry.fn === fn).length]));
    expect(injected, "注入的内层调用").toEqual({ _running_attempts: 19, pid_alive: 10, run_pd: 25 });
    replay(calls);
  }, 1_800_000);
  it("其余四个：放回调用当时的快照之后三边重放，逐字与当时的结果相同", () => {
    const calls = samples().filter((item) => !FLOW.includes(item.fn));
    const counts = Object.fromEntries([...SNAPSHOT, ...PURE].map((fn) => [fn, calls.filter((item) => item.fn === fn).length]));
    expect(counts, "各函数的顶层调用次数").toEqual({ landed_meanwhile: 7, landing_chain: 11, on_branch: 25, landing_records: 2 });
    replay(calls);
  }, 1_800_000);
});
