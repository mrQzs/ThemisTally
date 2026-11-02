// 第 ⑤g2 片的契约（迁移计划第 ⑤ 步）：执行端的代办里改状态的部分。kit_hub.py 的 run_exec、finish_exec、write_review、run_jev、ensure_rework_scope
// 照调用当时比（同 ⑤e2b、⑤f：交回值，调用之后的 ts，几棵树里新建、改动、删掉的文件，账本新增的部分，git 状态）。用例当时换掉的 run_pd、
// contract_requirements、rework_added_files、worktree_root、决策端的 Session（记它的 ask）与 load_locked_batteries，以及 rebase_candidate 建临时
// worktree 的 mkdtemp 照记录注入（参数逐次核对）。落地锁被占的那一条（用例自己在同一个进程里拿着锁）不重放，契约钉住只跳这一条。
// dispatch_attempt、start_rework、rebase_candidate、start_retry、rework_added_files、final_audit_turn、exec_window、scratch_worktree 只在
// 里面被调到，手写场景另管（hub-runexec-scenes）。语料只有 tests/test_kit_hub.py 这一个来源。
import { mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { removeCreated } from "./repo-fixtures.ts";

const ROOT = scratchDir("runexec");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

const TESTS = [
  "test_a_cut_off_attempt_is_continued_instead_of_restarted", "test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner",
  "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_a_kernel_revise_without_an_audit_says_so", "test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too",
  "test_a_timed_out_attempt_is_continued_instead_of_restarted", "test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner",
  "test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner", "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base",
  "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch", "test_exec_letter_counts_the_candidate_and_names_the_failed_checks",
  "test_exec_recheck_resumes_an_execution_the_hub_was_killed_in", "test_exec_recheck_revisits_the_last_attempt_without_rerunning",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_exec_rework_reports_when_the_rework_base_cannot_be_built", "test_exec_rework_stops_at_the_budget",
  "test_exec_verdict_reads_the_attempt_state_key", "test_exec_waits_for_the_landing_lock_by_holding_its_letter", "test_execution_jev_gets_the_objective_fingerprint",
  "test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed", "test_failed_integrate_takes_the_landed_commits_back_off_the_branch",
  "test_finalize_lands_the_oracle_commit_first_and_can_be_retried", "test_finalize_lands_the_rework_chain_before_integrating",
  "test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report", "test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it",
  "test_retry_after_failed_checks_tells_the_executor_why", "test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again",
  "test_rework_contract_lets_the_executor_modify_files_added_earlier", "test_the_executor_letter_says_none_when_nothing_is_pending",
  "test_the_review_record_names_the_model_of_the_final_audit_turn",
];
const FLOW = ["run_exec", "finish_exec", "write_review", "run_jev", "ensure_rework_scope"];

interface Call {
  readonly test: string;
  readonly fn: string;
  readonly skip: string | null;
  readonly result: unknown;
  readonly request: ProbeRequest;
}

let sampled: Call[] | null = null;
/** 采一次样（几个 it 共用），照 ⑤e2b 的流程函数记。 */
function samples(): Call[] {
  if (sampled !== null) return sampled;
  const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
  mkdirSync(ROOT, { recursive: true });
  const tmp = mkdtempSync(join(ROOT, "samples-")); // 每次新建：上一次采到一半失败时留下的只读 git 对象不挡路
  const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FLOW, flow_functions: FLOW, tmp }, 900_000);
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  sampled = (value.get("calls") as PyDict[]).map((item) => ({
    test: item.get("test") as string, fn: item.get("fn") as string, skip: (item.get("skip") as string | undefined) ?? null,
    result: JSON.parse(item.get("result") as string) as unknown,
    request: {
      op: "hub.contract_flow", fn: item.get("fn"), args: (item.get("args") as PyValue[]).map(toTagged), restores: JSON.parse(item.get("restores") as string),
      roots: item.get("roots"), fresh: item.get("fresh"), pin: Number(item.get("pin")), replaced: item.get("replaced"), inner: JSON.parse(item.get("inner") as string), python,
    },
  }));
  return sampled;
}

/** 三边重放 calls，每一次都要与当时的结果相同；交回不同的几处（最多两处，截断）。 */
function replay(calls: readonly Call[]): void {
  const requests = calls.map((item) => item.request);
  for (const impl of IMPLS) {
    const results = runBatch(impl, requests, REPLAY_TIMEOUT);
    const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(results[at]?.["value"]) !== JSON.stringify(calls[at]?.result));
    const shown = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
    expect(JSON.stringify(shown).slice(0, 8000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe("[]");
  }
}

describe("第 ⑤g2 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("改状态的五个函数：放回调用当时的快照、照记录注入后三边重放，交回值、ts、文件、账本、git 状态都与当时的结果相同；只跳落地锁被占的那一条", () => {
    const all = samples();
    const counts = Object.fromEntries(FLOW.map((fn) => [fn, all.filter((item) => item.fn === fn).length]));
    expect(counts, "各函数的顶层调用次数").toEqual({ run_exec: 27, finish_exec: 25, write_review: 9, run_jev: 1, ensure_rework_scope: 1 });
    expect(all.filter((item) => item.skip !== null).map((item) => [item.test, item.fn, item.skip]), "不重放的").toEqual([
      ["test_exec_waits_for_the_landing_lock_by_holding_its_letter", "run_exec", "EXEC_LAND_WAIT_SECONDS=0.2"],
    ]);
    const calls = all.filter((item) => item.skip === null);
    // 注入确实走到了：各内层调用记下的次数，新建 worktree 的次数
    const inner = calls.flatMap((item) => item.request["inner"] as { fn: string }[]);
    const injected = Object.fromEntries([...new Set(inner.map((entry) => entry.fn))].sort().map((fn) => [fn, inner.filter((entry) => entry.fn === fn).length]));
    expect({ injected, fresh: calls.filter((item) => (item.request["fresh"] as string[]).length).length }, "注入的内层调用").toEqual({
      injected: { ask: 1, contract_requirements: 12, load_locked_batteries: 1, mkdtemp: 2, rework_added_files: 10, run_pd: 86, worktree_root: 2 }, fresh: 2,
    });
    // 当时的结果都是正常交回（用例只验正常的信；出错的分支在手写场景里）
    const failed = calls.filter((item) => !(item.result as { result: { ok: boolean } }).result.ok).map((item) => [item.test, item.fn]);
    expect(failed, "当时就出错的").toEqual([]);
    replay(calls);
  }, 1_800_000);
});
