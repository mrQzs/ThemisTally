// 第 ⑤e2b 片的契约（迁移计划第 ⑤ 步）：合同与战前门禁里改状态的部分。kit_hub.py 的 accept_contract、revalidate_contract、
// bump_contract_version、set_contract_base、accept_gate_pre、sync_executor_line 交给 Python、Node、Bun，照调用当时比（设计稿第 6 节
// 第 6 条、第 8 节）：交回值，调用之后的 ts，两棵树（hub 仓库、仓库外的门禁 worktree）里新建、改动、删掉的文件，账本新增的部分，
// 用命令读出的 git 状态（HEAD、全部引用、status）。语料：
//   - tests/test_kit_hub.py 里调到这六个函数的 23 条用例：Python 探针在最外层调用时记下调用当时的快照（带 .git）、钉住的时刻、用例
//     当时换掉的 run_pd、contract_requirements、budget_problems、revalidate_contract 的每一次调用（参数、交回值、文件改动、调用之后
//     的 ts），三边先原地放回快照、照记录注入再重放，每一次都要与当时的结果相同；
//   - 只在比较这一步把 pytest 收集失败输出里的用时换成占位（第 6 节第 2 条），实现里不打。
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { CONTRACT_EXECUTOR_LINE } from "@themis/hub/constants";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, runPythonCli, scratchDir } from "./harness.ts";
import {
  AT, BT, C, CR, LF, PIN, type Scene, agreeFlow, flow, pd, py, returned, scene, scrubResult, text, tsAfter, written,
} from "./flow-fixtures.ts";
import { git, newRepo, put, removeCreated, tempDir } from "./repo-fixtures.ts";

const ROOT = scratchDir("contract-flow");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number", "test_a_cut_off_attempt_is_continued_instead_of_restarted",
  "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted", "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline",
  "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline", "test_a_timed_out_attempt_is_continued_instead_of_restarted",
  "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base", "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch",
  "test_bold_item_ids_in_the_contract_are_normalized", "test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt",
  "test_contract_title_is_the_registered_task_title", "test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer",
  "test_dispatched_contract_is_bumped_not_edited", "test_exec_rework_continues_from_the_reviewed_candidate", "test_gate_pre_baseline_must_fail_on_assertions",
  "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff", "test_gate_pre_rejects_a_baseline_that_does_not_collect",
  "test_gate_rework_resets_a_worktree_the_state_lost_track_of", "test_kernel_writes_the_contract_version_and_base_it_assigns", "test_owner_raises_the_attempt_budget",
  "test_retry_after_failed_checks_tells_the_executor_why", "test_rework_contract_lets_the_executor_modify_files_added_earlier",
  "test_unsent_contracts_get_the_rostered_executor_line",
];
const FUNCTIONS = ["accept_contract", "revalidate_contract", "bump_contract_version", "set_contract_base", "accept_gate_pre", "sync_executor_line"];

describe("第 ⑤e2b 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记到的最外层调用放回调用当时的快照、照记录注入后三边重放，交回值、ts、文件、账本、git 状态都与当时的结果相同；每个函数都有样本", () => {
    const python = (valueOf(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })) as string[])[0] as string;
    const tmp = join(ROOT, "samples");
    mkdirSync(tmp, { recursive: true });
    const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, flow_functions: FUNCTIONS, tmp }, 600_000);
    expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
    const value = valueOf(recorded) as PyDict;
    expect(value.get("skipped")).toEqual([]);
    const calls = (value.get("calls") as PyDict[]).map((item) => ({
      test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: JSON.parse(item.get("result") as string) as unknown,
      request: {
        op: "hub.contract_flow", fn: item.get("fn"), args: (item.get("args") as PyValue[]).map(toTagged), restores: JSON.parse(item.get("restores") as string),
        roots: item.get("roots"), pin: Number(item.get("pin")), replaced: item.get("replaced"), inner: JSON.parse(item.get("inner") as string), python,
      } as ProbeRequest,
    }));
    expect(calls.length, "最外层调用的次数").toBe(76);
    const requests = calls.map((item) => item.request);
    for (const impl of IMPLS) {
      const results = runBatch(impl, requests, REPLAY_TIMEOUT);
      const bad = calls.map((_, at) => at).filter((at) => JSON.stringify(scrubResult(results[at]?.["value"])) !== JSON.stringify(scrubResult(calls[at]?.result)));
      const shown = bad.slice(0, 2).map((at) => ({ at, test: calls[at]?.test, fn: calls[at]?.fn, then: calls[at]?.result, replay: results[at] }));
      expect(JSON.stringify(shown).slice(0, 6000), `${impl.name} 与当时的结果不同（共 ${bad.length} 处）`).toBe("[]");
    }
    expect(FUNCTIONS.filter((fn) => !calls.some((item) => item.fn === fn)), "没有顶层调用").toEqual([]);
  }, 1_200_000);
});

// --- 二、临时仓库上的手写对照 ------------------------------------------------------------------------------------
// 每个场景先在 run/ 下搭好（仓库与仓库外的门禁 worktree），带 .git 原样拷一份到 tpl/；三边各自先原地放回再跑，worktree 里的绝对路径
// 就都还对。样本没走到的分支在这里：假的 run_pd 照手写的记录注入（参数逐次核对），门禁基准测试的走通与收集失败用真调度器。

const GATE = "tests/test_gate_t001_baseline.py";

/** 主任务状态：T001，合同键与版本照给的，门禁草稿 worktree 记在 workspaces 里。 */
function taskState(sc: Scene, contract: Record<string, unknown>, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  ts.set("contract", py(contract));
  ts.set("workspaces", py({ gate: { path: sc.wt } }));
  for (const [key, value] of Object.entries(extra)) ts.set(key, py(value));
  return ts;
}

/** 调度器自己写的证据（只用在真调度器的场景）：baseline/NN/ 下的文件比路径；checks.json 里钉不住的字段换成占位（只换值、不删键），日志不比内容。 */
function evidence(state: Record<string, unknown>): Record<string, unknown> {
  const files = state["files"] as { write: Record<string, string> };
  const write: Record<string, string> = {};
  const stamp = (record: Record<string, unknown>, keys: string[]): void => {
    for (const key of keys) if (key in record) record[key] = "<X>";
  };
  for (const [key, data] of Object.entries(files.write)) {
    if (!/^0[/][.]agent[/]runs[/][^/]+[/]baseline[/]/.test(key)) {
      write[key] = data;
    } else if (key.endsWith("/checks.json")) {
      const record = JSON.parse(Buffer.from(data, "base64").toString("utf8")) as Record<string, unknown>;
      stamp(record, ["started_at", "ended_at", "workspace"]);
      for (const item of record["results"] as Record<string, unknown>[]) stamp(item, ["started_at", "ended_at", "wall_seconds", "pid", "log_sha256", "log_bytes"]);
      write[key] = JSON.stringify(record);
    } else {
      write[key] = "<LOG>";
    }
  }
  return { ...state, files: { ...files, write } };
}

/** 一份过得了 derive-json、validate 与内核要求的合同 md（门禁基准测试在基线上应失败）。 */
function contractMd(head: string, executor: string = CONTRACT_EXECUTOR_LINE): string {
  return [
    "# TASK: t001-doc", "", "## Identity", "- plan_version: 1", "- repository: test", `- base_sha: ${head}`, "- risk_level: low",
    "- authorized_actions: local_edit, local_test", "- integration_actions: local_branch, merge", executor, "",
    "## Goal", "title() 交回 new。", "", "## Non-goals", "- 不改别的模块。", "", "## Repository facts", "- src/doc.py 的 title()。", "",
    "## Scope", "- allowed_modified_files: src/doc.py", "- allowed_new_files: 无", "- allowed_deleted_files: 无",
    "- forbidden_paths: tests/test_gate_t001_*.py", "- dependency_changes: forbidden", "", "## Behavior contract", "- title() == 'new'", "",
    "## Steps", "1. 改 title。", "", "## Validation commands", `- V01（必要，基线应失败）: ${BT}python -m pytest ${GATE} -q${BT}`, "",
    "## Definition of done", "- D01: title 交回 new；证据：V01。", "", "## Stop conditions", "- 要改范围外的文件。", "",
    "## Budget", "- max_attempts_total: 6", "- max_wall_seconds_per_attempt: 600", "- max_wall_seconds_total: 7200", "",
    "## Report back", "- 最后一条消息是执行报告。", "", "## Forbidden", "- 不提交。", "",
  ].join(LF);
}
const GATE_TEST = ["import sys", "sys.path.insert(0, 'src')", "", "", "def test_title():", "    from doc import title", "    assert title() == 'new'", ""].join(LF);
const BASE_FILES = { "src/doc.py": ["def title():", "    return 'old'", ""].join(LF) };
const V1 = { version: 1, key: "t001-doc.v1", md: ".agent/plans/t001-doc.v1.md", json: ".agent/plans/t001-doc.v1.json", written_version: 1 };
const hasCache = (state: Record<string, unknown> | undefined): string[] => Object.keys(written(state)).filter((key) => key.startsWith("1/") && /__pycache__|[.]pytest_cache/.test(key));

describe("第 ⑤e2b 片：临时仓库上的手写对照", () => {
  it("门禁基准测试：真调度器走通（收集、提交、挂引用、改 base_sha、derive-json、validate、baseline）；收集失败；KERNEL_PYTEST 不在 worktree 里留缓存", () => {
    // PYTHONDONTWRITEBYTECODE 设成 0：调度器的 child_env 看见它在就不补 1，kernel_pytest_env 不显式设 1 时 pytest 真会写 __pycache__
    const env = { PI_DISPATCH_WORKTREE_ROOT: tempDir("flow-wtroot"), PYTHONDONTWRITEBYTECODE: "0" };
    const plan = (repo: string, head: string): void => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
    const ok = scene(BASE_FILES, (repo, wt, head) => {
      plan(repo, head);
      put(wt, GATE, GATE_TEST);
    });
    const broken = scene(BASE_FILES, (repo, wt, head) => {
      plan(repo, head);
      put(wt, GATE, `def test_title(:${LF}    pass${LF}`);
    });
    const [passed, failed] = agreeFlow([
      flow("accept_gate_pre", ok, [taskState(ok, V1), ok.wt], { env }), flow("accept_gate_pre", broken, [taskState(broken, V1), broken.wt], { env }),
    ], evidence);
    expect(returned(passed)).toEqual([]);
    const oracle = tsAfter(passed).get("oracle") as PyDict;
    expect([oracle.get("locked"), oracle.get("baseline_exit"), oracle.get("ref")]).toEqual([true, 0n, "refs/themis/oracle/t001-doc/v1"]);
    expect(Object.keys(written(passed)).filter((key) => key.includes("/baseline/")).sort()).toEqual([
      "0/.agent/runs/t001-doc/baseline/01/V01.log", "0/.agent/runs/t001-doc/baseline/01/checks.json",
    ]);
    expect(String((returned(failed) as string[])[0])).toContain("收集失败（pytest --collect-only 退出码 2");
    expect([hasCache(passed), hasCache(failed)], "worktree 里没有 __pycache__ 与 .pytest_cache").toEqual([[], []]);
  }, 600_000);

  it("accept_gate_pre：没有新增文件；改动超过 8 条只列前 8 条；已派遣时升版撞上已有的版本；合同里没有 base_sha 行；baseline 不符合预期（输出只留末 20 行）", () => {
    const plain = scene(BASE_FILES, (repo, _wt, head) => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head)));
    const many = scene(BASE_FILES, (repo, wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      put(wt, "src/doc.py", `def title():${LF}    return 'x'${LF}`);
      for (let n = 1; n <= 9; n += 1) put(wt, `extra/f${n}.txt`, `${n}${LF}`);
    });
    const bumped = scene(BASE_FILES, (repo, wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      put(repo, ".agent/plans/t001-doc.v2.md", contractMd(head));
      put(wt, GATE, GATE_TEST);
    });
    const noBase = scene(BASE_FILES, (repo, wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head).replace(`- base_sha: ${head}${LF}`, ""));
      put(wt, GATE, GATE_TEST);
    });
    const longTail = scene(BASE_FILES, (repo, wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      expect(runPythonCli(["--repo", repo, "derive-json", "t001-doc.v1", "--title", "改文档"], repo).status, "搭场景时的 derive-json").toBe(0);
      put(wt, GATE, GATE_TEST);
    });
    const lockHash = scene(BASE_FILES, (repo, wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      expect(runPythonCli(["--repo", repo, "derive-json", "t001-doc.v1", "--title", "改文档"], repo).status, "搭场景时的 derive-json").toBe(0);
      put(wt, GATE, GATE_TEST);
    });
    const record = JSON.stringify({ results: [{ id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"], log: "01/V01.log", exit_code: 1, timed_out: false, interrupted: false, spawn_error: null }] });
    const lockInner = [
      pd(["derive-json", "t001-doc.v1", "--force", "--title", "改文档"], 0, "ok"), pd(["validate", "t001-doc.v1"], 0, "ok"),
      pd(["baseline", "t001-doc.v1"], 0, `基线检查记录：.agent/runs/t001-doc/baseline/01/checks.json${LF}`, 1800, {
        "0/.agent/runs/t001-doc/baseline/01/checks.json": record, "0/.agent/runs/t001-doc/baseline/01/V01.log": `1 failed in 0.01s${LF}`,
        "0/.agent/plans/t001-doc.v1.json": `${readFileSync(join(lockHash.repo, ".agent/plans/t001-doc.v1.json"), "utf8")}${LF}`,
      }),
    ];
    const baselineOut = Array.from({ length: 25 }, (_, n) => `第 ${n + 1} 行`).join(LF);
    const longInner = [
      pd(["derive-json", "t001-doc.v1", "--force", "--title", "改文档"], 0, "ok"), pd(["validate", "t001-doc.v1"], 0, "ok"),
      pd(["baseline", "t001-doc.v1"], 1, baselineOut, 1800),
    ];
    const results = agreeFlow([
      flow("accept_gate_pre", plain, [taskState(plain, V1), plain.wt]), flow("accept_gate_pre", many, [taskState(many, V1), many.wt]),
      flow("accept_gate_pre", bumped, [taskState(bumped, { ...V1, dispatched: true }), bumped.wt]), flow("accept_gate_pre", noBase, [taskState(noBase, V1), noBase.wt]),
      flow("accept_gate_pre", longTail, [taskState(longTail, V1), longTail.wt], { inner: longInner }),
      flow("accept_gate_pre", lockHash, [taskState(lockHash, V1), lockHash.wt], { inner: lockInner }),
    ]);
    expect(results.map(returned)).toEqual([
      [`门禁草稿 worktree 里没有新增文件：要新增 ${GATE}`],
      [`只能新增 ${GATE}，不能改动别的文件：src/doc.py, extra/f1.txt, extra/f2.txt, extra/f3.txt, extra/f4.txt, extra/f5.txt, extra/f6.txt, extra/f7.txt`],
      ["t001-doc.v2.md 已存在，合同版本只增不改"], ["合同 Identity 里找不到唯一的“- base_sha:”行"],
      [`baseline 不符合预期（基准测试应在基线上失败，其余检查按合同）：${LF}${baselineOut.split(LF).slice(5).join(LF)}`], [],
    ]);
    const oracle = tsAfter(results[4]).get("oracle") as PyDict;
    expect([oracle.get("baseline_exit"), oracle.get("baseline_tail")]).toEqual([1n, baselineOut.split(LF).slice(5).join(LF)]);
    // baseline 那次调用改了合同 JSON：锁定时重算的哈希是改过之后的（三边一比就看出锁定时有没有重算）
    expect([returned(results[5]), (tsAfter(results[5]).get("oracle") as PyDict).get("locked")]).toEqual([[], true]);
  }, 300_000);

  it("revalidate_contract：带标题时 derive-json 带 --title；derive-json 自己失败；validate 过了之后内核要求报问题（假的 run_pd 写出合同 JSON）", () => {
    const sc = scene(BASE_FILES, (repo, _wt, head) => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head)), false);
    const json = JSON.stringify({ scope: { forbidden_paths: [] }, checks: [], executor: null, authorization: { integration: [] } });
    const derive = (title: boolean): string[] => ["derive-json", "t001-doc.v1", "--force", ...(title ? ["--title", "改文档"] : [])];
    const results = agreeFlow([
      flow("revalidate_contract", sc, [taskState(sc, V1)], { inner: [pd(derive(true), 1, `ERROR 第一行${LF}ERROR 第二行${LF}`)] }),
      flow("revalidate_contract", sc, [taskState(sc, V1, { title: "" })], {
        inner: [pd(derive(false), 0, "ok", null, { "0/.agent/plans/t001-doc.v1.json": json }), pd(["validate", "t001-doc.v1"], 0, "ok")],
      }),
    ]);
    expect(results.map(returned)[0]).toEqual([`derive-json 失败：${LF}ERROR 第一行${LF}ERROR 第二行`]);
    expect((returned(results[1]) as string[]).length, "内核要求的问题").toBeGreaterThan(2);
    expect((tsAfter(results[1]).get("contract") as PyDict).get("validated")).toBe(false);
  }, 300_000);

  it("注入核对：参数对不上、多调一次、记录里多出来没调到的，各自报错（不拿记录里的答案糊过去）", () => {
    const sc = scene(BASE_FILES, (repo, _wt, head) => put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head)), false);
    const derive = ["derive-json", "t001-doc.v1", "--force", "--title", "改文档"];
    const results = agreeFlow([
      flow("revalidate_contract", sc, [taskState(sc, V1)], { inner: [pd(["derive-json", "t001-doc.v1", "--force"], 1, "x")] }),
      flow("revalidate_contract", sc, [taskState(sc, V1)], { inner: [pd(derive, 0, "ok")] }),
      flow("revalidate_contract", sc, [taskState(sc, V1)], { inner: [pd(derive, 1, "x"), pd(["validate", "t001-doc.v1"], 0, "ok")] }),
    ]);
    expect(results.map(returned)).toEqual(["INJECTION_MISMATCH", "INJECTION_MISMATCH", "INJECTION_LEFTOVER"]);
  }, 300_000);

  it("accept_contract：没有 contract_md、不是字符串、首行不对（前面有空行也认）；新版本已存在；同号重交的旧稿进 evidence（文件名带钉住的时刻）", () => {
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      put(repo, ".agent/plans/t001-doc.v1.md", contractMd(head));
      put(repo, ".agent/plans/t001-doc.v1.json", "{}");
      put(repo, ".agent/plans/t001-doc.v2.md", contractMd(head));
    }, false);
    const md = contractMd(sc.head);
    const inner = [pd(["derive-json", "t001-doc.v1", "--force", "--title", "改文档"], 1, "ERROR 坏了")];
    const results = agreeFlow([
      flow("accept_contract", sc, [taskState(sc, {}), {}]), flow("accept_contract", sc, [taskState(sc, {}), { contract_md: 5 }]),
      flow("accept_contract", sc, [taskState(sc, {}), { contract_md: `${LF}  ${LF}# TASK: t001-other${LF}` }]),
      flow("accept_contract", sc, [taskState(sc, { ...V1, validated: true }), { contract_md: md }]),
      flow("accept_contract", sc, [taskState(sc, V1), { contract_md: `${LF}${md}` }], { inner }),
      flow("accept_contract", sc, [taskState(sc, {}), { contract_md: `${LF}  ${CR}${LF}` }]),
      flow("accept_contract", sc, [taskState(sc, { version: 2, dispatched: true }), { contract_md: `${md}${C(0xd800)}` }], { replaced: ["run_pd"] }),
    ]);
    expect(results.slice(0, 4).map(returned)).toEqual([
      ["输出里没有 contract_md（合同 Markdown 全文）"], ["输出里没有 contract_md（合同 Markdown 全文）"], ["合同第一行必须是“# TASK: t001-doc”"],
      ["t001-doc.v2.md 已存在，合同版本只增不改"],
    ]);
    expect(returned(results[5]), "只有空白").toEqual(["输出里没有 contract_md（合同 Markdown 全文）"]);
    // 末尾有孤立代理项：写合同时照 Python 报 UnicodeEncodeError、留下空的 v3.md，账本里只有 identity_normalized（不往下调 run_pd）
    expect([returned(results[6]), written(results[6])["0/.agent/plans/t001-doc.v3.md"]]).toEqual(["UnicodeEncodeError", ""]);
    const events = Buffer.from(results[6]?.["ledger"] as string, "base64").toString("utf8").split(LF).filter(Boolean);
    expect(events.map((line) => (JSON.parse(line) as { event: string }).event)).toEqual(["contract.identity_normalized"]);
    expect(Object.keys(written(results[4])).filter((key) => key.includes("rejected")).sort()).toEqual([
      "0/.agent/mailbox/tasks/T001-2-contract/evidence/t001-doc.v1.rejected-20261101T000000000000Z.json",
      "0/.agent/mailbox/tasks/T001-2-contract/evidence/t001-doc.v1.rejected-20261101T000000000000Z.md",
    ]);
  }, 300_000);

  it("bump_contract_version：plan_version 行后面接空行（照抄 Python：空白跨行，吃掉一个换行）、没有这一行、有两行、Unicode 数字、版本号是字符串", () => {
    const md = (identity: string[]): string => ["# TASK: t001-doc", "", "## Identity", ...identity, "- base_sha: x", "", "## Goal", "g", ""].join(LF);
    const cases = [
      ["- plan_version: 1", "", "- repository: test"], ["- repository: test"], ["- plan_version: 1", "- plan_version: 1"], [`- plan_version: ${C(0x661)}`],
      ["- plan_version: 1   "],
    ];
    const scenes = cases.map((identity) => scene(BASE_FILES, (repo) => put(repo, ".agent/plans/t001-doc.v1.md", md(identity)), false));
    const results = agreeFlow([
      ...scenes.map((sc) => flow("bump_contract_version", sc, [taskState(sc, { ...V1, dispatched: true })])),
      flow("bump_contract_version", scenes[0] as Scene, [taskState(scenes[0] as Scene, { ...V1, version: "1" })]),
    ]);
    expect(results.map(returned)).toEqual([[], ["合同 Identity 里找不到唯一的“- plan_version:”行"], ["合同 Identity 里找不到唯一的“- plan_version:”行"], [], [], []]);
    expect(text(results[0], "0/.agent/plans/t001-doc.v2.md")).toContain(`## Identity${LF}- plan_version: 2${LF}- repository: test`);
  }, 300_000);

  it("set_contract_base：没有 base_sha 行、有两行、后面接空行、是最后一行（行尾的空白吃掉换行）；sync_executor_line：已派遣、已经是名册那行（行尾带空白）、没有这一行、md 不在、CRLF、两行只换第一行", () => {
    const md = (lines: string[], newline = LF): string => ["# TASK: t001-doc", "", "## Identity", "- plan_version: 1", ...lines, "", "## Goal", "g", ""].join(newline);
    const one = (lines: string[], newline = LF): Scene => scene(BASE_FILES, (repo) => put(repo, ".agent/plans/t001-doc.v1.md", md(lines, newline)), false);
    const noBase = one(["- repository: test"]);
    const twoBase = one(["- base_sha: a", "- base_sha: b"]);
    const blankAfter = one(["- base_sha: x"]);
    const lastLine = scene(BASE_FILES, (repo) => put(repo, ".agent/plans/t001-doc.v1.md", ["# TASK: t001-doc", "", "## Identity", "- base_sha: x", ""].join(LF)), false);
    const derive = [pd(["derive-json", "t001-doc.v1", "--force", "--title", "改文档"], 1, "x")];
    const syncCases = [
      one([`- executor: x/y · thinking high`]), one([`${CONTRACT_EXECUTOR_LINE}   `]), one(["- repository: test"]), one(["- executor: x/y · thinking high"], CR + LF),
      one(["- executor: a/b · thinking low", "- executor: c/d · thinking low"]),
    ];
    const missing = scene(BASE_FILES, () => undefined, false);
    const results = agreeFlow([
      flow("set_contract_base", noBase, [taskState(noBase, V1), "abc"]), flow("set_contract_base", twoBase, [taskState(twoBase, V1), "abc"]),
      flow("sync_executor_line", syncCases[0] as Scene, [taskState(syncCases[0] as Scene, { ...V1, dispatched: true })]),
      ...syncCases.map((sc) => flow("sync_executor_line", sc, [taskState(sc, V1)])), flow("sync_executor_line", missing, [taskState(missing, V1)]),
      flow("set_contract_base", blankAfter, [taskState(blankAfter, V1), "abc"], { inner: derive }),
      flow("set_contract_base", lastLine, [taskState(lastLine, V1), "abc"], { inner: derive }),
    ]);
    expect(results.map(returned)).toEqual([
      ["合同 Identity 里找不到唯一的“- base_sha:”行"], ["合同 Identity 里找不到唯一的“- base_sha:”行"], null, "- executor: x/y · thinking high", null, null,
      "- executor: x/y · thinking high", "- executor: a/b · thinking low", null, [`derive-json 失败：${LF}x`], [`derive-json 失败：${LF}x`],
    ]);
    // 行尾的空白也匹配换行：后面的空行没了；最后一行的话文件末尾的换行没了（10.1 节记着，切换后在 TS 上改）
    expect(text(results[9], "0/.agent/plans/t001-doc.v1.md")).toContain(`- base_sha: abc${LF}## Goal`);
    expect(text(results[10], "0/.agent/plans/t001-doc.v1.md").endsWith(`## Identity${LF}- base_sha: abc`)).toBe(true);
    // CRLF：read_text 是通用换行，读进来就没有回车了；写回时整份都是 LF（不只换掉的那一行）
    const crlf = text(results[6], "0/.agent/plans/t001-doc.v1.md");
    expect([crlf.includes(CR), crlf.includes(`- plan_version: 1${LF}${CONTRACT_EXECUTOR_LINE}${LF}${LF}## Goal`)]).toEqual([false, true]);
    expect(text(results[7], "0/.agent/plans/t001-doc.v1.md")).toContain(`${CONTRACT_EXECUTOR_LINE}${LF}- executor: c/d · thinking low`);
  }, 300_000);
});
