// 第 155 轮（信箱演进第 1 步）的手写对照：重活车道与“只有全量回归不符时原样重跑一次”。临时仓库上搭好场景，三边各自先原地放回再跑，
// 交回值、ts、文件、账本、git 状态逐字比：
//   - finish_exec：只有全量回归（R01）不符时重跑一次，第二次相符照通过、ts 记 flaky、账本记 regression.rerun 与 regression.flaky；第二次仍不符
//     照旧判失败；本片自己的检查也不符时不重跑；车道由另一个进程拿着（排队时限设短）时照“没跑成”给出退出码 3，不调调度器；
//   - land：车道里试落地锁，落地锁由另一个进程拿着（试锁时限设短）时让出车道、信留在 new；车道由另一个进程拿着时交回“重活车道排不到”。
// 拿锁的“另一个进程”是跑这份测试的 vitest 进程自己（owner.json 写它的 pid，三边的探针都认它活着）。不写转义序列。
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { CONTRACT_EXECUTOR_LINE, COORDINATOR, EXECUTOR } from "@themis/hub/constants";
import { canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { BASE_FILES, BOX, GATE, events, letter, taskState } from "./engine-fixtures.ts";
import { AT, BT, CR, LF, type Scene, agreeFlow, flow, pd, py, returned, scene, tsAfter } from "./flow-fixtures.ts";
import { put, removeCreated } from "./repo-fixtures.ts";

afterAll(removeCreated);

const lines = (...items: string[]): string => [...items, ""].join(LF);
const OLD_GATE = "tests/test_gate_t000_baseline.py";
const FILES = { ...BASE_FILES, [OLD_GATE]: lines("def test_old():", "    assert True") };
const KEY = "t001-doc.v1";
const V1 = { version: 1, key: KEY, md: ".agent/plans/t001-doc.v1.md", json: ".agent/plans/t001-doc.v1.json", written_version: 1 };
const RUN = ".agent/runs/t001-doc/attempt-001";
/** 合同的两条检查：V01 跑本片的门禁基准，R01 跑先前各片的（全量回归）。 */
const CONTRACT = JSON.stringify({
  budget: { max_attempts_total: 4 },
  checks: [{ id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"] }, { id: "R01", argv: ["python", "-m", "pytest", OLD_GATE, "-q"] }],
});
const RED = "tests/test_gate_t000_baseline.py::test_old";
const errorOf = (state: Record<string, unknown> | undefined): unknown => (state?.["result"] as Record<string, unknown>)["error"] ?? null;
const kinds = (state: Record<string, unknown> | undefined, prefix: string): unknown[][] =>
  events(state).filter((event) => String(event["event"]).startsWith(prefix)).map((event) => [event["event"], event["label"], event["exit"] ?? null]);

/** 一次 check：checks/<nn>/checks.json 照给的结果写（没过的那几条带日志）。 */
function checked(runDir: string, nn: string, code: number, failed: string[], limit = 3600): unknown {
  const results = ["V01", "R01"].map((id) => (failed.includes(id) ? { id, status: "failed", log: `${nn}/${id}.log` } : { id, status: "passed" }));
  const write: Record<string, string> = { [`0/${RUN}/checks/${nn}/checks.json`]: JSON.stringify({ results }) };
  // 日志是 CRLF、汇总行不带“ - 原因”：用例名取到空白为止
  for (const id of failed) write[`0/${RUN}/checks/${nn}/${id}.log`] = ["....F", `FAILED ${id === "R01" ? RED : `${GATE}::test_title`}`, "1 failed, 3 passed", ""].join(`${CR}${LF}`);
  return pd(["check", runDir, "--fresh"], code, code === 0 ? "检查通过" : `检查没过：${failed.join("、")}`, limit, write);
}

/** .agent/mailbox 下的一把锁由跑这份测试的进程拿着。 */
function held(repo: string, name: string, label: Record<string, string> | null): void {
  put(repo, `${BOX}/${name}/owner.json`, `${JSON.stringify({ pid: process.pid, token: "holder", at: AT })}${LF}`);
  if (label) put(repo, `${BOX}/${name}/label.json`, `${JSON.stringify({ ...label, at: AT })}${LF}`);
}

function execScene(more: (repo: string) => void = () => undefined): { sc: Scene; runDir: string } {
  const sc = scene(FILES, (repo) => {
    put(repo, V1.json, CONTRACT);
    put(repo, `${RUN}/state.json`, JSON.stringify({ state: "NEEDS_REVIEW" }));
    more(repo);
  }, false);
  return { sc, runDir: join(sc.repo, ...RUN.split("/")) };
}
function execTs(sc: Scene): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  ts.set("contract", py(V1));
  ts.set("oracle", py({ sha: sc.head, files: [GATE] }));
  return ts;
}
/** 先前一次检查记过的 flaky：这一次的交付信不写它。 */
function withOldFlaky(ts: PyDict): PyDict {
  ts.set("flaky", py([{ at: AT, label: "基线检查", checks: ["R01"], failed: ["tests/test_gate_t000_baseline.py::test_older"] }]));
  return ts;
}

describe("第 155 轮：执行检查只有全量回归不符时原样重跑一次（手写）", () => {
  it("第二次相符照通过并记 flaky；第二次仍不符照旧判失败；本片的检查也不符、读不出哪条不符都不重跑；车道被占照没跑成交回 3、不调调度器", () => {
    const flaky = execScene();
    const twice = execScene();
    const own = execScene();
    const busy = execScene((repo) => held(repo, ".heavy", { label: "执行检查", task: "T009" }));
    const unread = execScene();
    const states = agreeFlow([
      flow("finish_exec", flaky.sc, [execTs(flaky.sc), flaky.runDir, 0], { inner: [checked(flaky.runDir, "01", 1, ["R01"]), checked(flaky.runDir, "02", 0, [])] }),
      flow("finish_exec", twice.sc, [execTs(twice.sc), twice.runDir, 0], { inner: [checked(twice.runDir, "01", 1, ["R01"]), checked(twice.runDir, "02", 1, ["R01"])] }),
      flow("finish_exec", own.sc, [withOldFlaky(execTs(own.sc)), own.runDir, 0], { inner: [checked(own.runDir, "01", 1, ["V01", "R01"])] }),
      { ...flow("finish_exec", busy.sc, [execTs(busy.sc), busy.runDir, 0], { inner: [], replaced: ["run_pd"] }), heavy_wait: 1 },
      flow("finish_exec", unread.sc, [execTs(unread.sc), unread.runDir, 0], { inner: [pd(["check", unread.runDir, "--fresh"], 2, "调度器自己出错", 3600)] }),
    ]);
    expect(states.map(errorOf)).toEqual([null, null, null, null, null]);
    const exec = states.map((state) => tsAfter(state).get("exec") as PyDict);
    expect(exec.map((item) => [item.get("check_exit"), item.get("check_ok")])).toEqual([[0n, true], [1n, false], [1n, false], [3n, false], [2n, false]]);
    expect(kinds(states[4], "regression.")).toEqual([]);
    const [first] = tsAfter(states[0]).get("flaky") as PyDict[];
    expect([first?.get("label"), first?.get("checks"), first?.get("failed"), first?.get("at")]).toEqual(["执行检查", ["R01"], [RED], AT]);
    expect(String(exec[0]?.get("check_tail"))).toContain(`（第一次只有全量回归 R01 不符，红的用例：${RED}；原样重跑一次，相符）`);
    expect(String((returned(states[0]) as PyDict).get("验证"))).toContain(`内核 check --fresh：通过；范围违规 0 条；attempt 状态 NEEDS_REVIEW；全量回归 R01 第一次红（${RED}），内核原样重跑一次相符`);
    expect([1, 2].map((at) => String((returned(states[at]) as PyDict).get("验证")).includes("第一次红"))).toEqual([false, false]);
    expect(kinds(states[0], "regression.")).toEqual([["regression.rerun", "执行检查", 0], ["regression.flaky", "执行检查", null]]);
    expect(kinds(states[1], "regression.")).toEqual([["regression.rerun", "执行检查", 1]]);
    expect([tsAfter(states[1]).has("flaky"), kinds(states[2], "regression."), (tsAfter(states[2]).get("flaky") as PyDict[]).length]).toEqual([false, [], 1]);
    expect(kinds(states[0], "heavy.")).toEqual([["heavy.entered", "执行检查", null], ["heavy.left", "执行检查", null]]);
    const queued = events(states[3]).filter((event) => String(event["event"]).startsWith("heavy."));
    expect(queued.map((event) => [event["event"], event["task"], event["behind"]])).toEqual([["heavy.queued", "T001", "T009 的执行检查"]]);
    expect(String(exec[3]?.get("check_tail"))).toContain("重活车道排到上限（1 秒）也没排到（车道里是 T009 的执行检查）：执行检查 没有跑，不是检查不过");
  }, 600_000);

  it("第 177 轮：外层时限是合同里准备命令与各条检查的时限之和加 600 秒，不少于 3600；不是整数的时限、不是对象的条目不算，合同读不出来照 3600", () => {
    const big = JSON.stringify({
      budget: { max_attempts_total: 4 }, setup: [{ id: "S01", timeout_seconds: 900 }, { id: "S02", timeout_seconds: true }],
      checks: [{ id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"], timeout_seconds: 600 },
        { id: "R01", argv: ["python", "-m", "pytest", OLD_GATE, "-q"], timeout_seconds: 2700 }, { id: "V02", timeout_seconds: "600" }, "V03"],
    });
    const scenes = [big, "[]", JSON.stringify({ checks: 5 }), "{"].map((plan) => execScene((repo) => put(repo, V1.json, plan)));
    const states = agreeFlow(scenes.map(({ sc, runDir }, index) =>
      flow("finish_exec", sc, [execTs(sc), runDir, 0], { inner: [checked(runDir, "01", 0, [], index === 0 ? 4800 : 3600)] })));
    expect(states.map(errorOf)).toEqual([null, null, null, null]);
    expect(states.map((state) => (tsAfter(state).get("exec") as PyDict).get("check_ok"))).toEqual([true, true, true, true]);
  }, 600_000);
});

describe("第 160 轮：重活车道按号排队（手写）", () => {
  // 号牌名以取号时刻打头：场景里先放的号牌写更早的时刻，排在探针自己取的号前面
  const ticket = (repo: string, name: string, text: string): void => put(repo, `${BOX}/.heavy-queue/${name}`, text);
  it("车道空着、排在前面的号牌的进程还在：照没跑成交回 3、不调调度器；排在前面的号牌读不出来：删掉、照常检查", () => {
    const ahead = execScene((repo) => ticket(repo, `20261031T000000000000Z-${process.pid}-0000.json`,
      `${JSON.stringify({ pid: process.pid, label: "执行检查", task: "T009", at: AT })}${LF}`));
    const garbage = execScene((repo) => ticket(repo, "20261031T000000000000Z-0-0000.json", "不是 JSON"));
    const states = agreeFlow([
      { ...flow("finish_exec", ahead.sc, [execTs(ahead.sc), ahead.runDir, 0], { inner: [], replaced: ["run_pd"] }), heavy_wait: 1 },
      { ...flow("finish_exec", garbage.sc, [execTs(garbage.sc), garbage.runDir, 0], { inner: [checked(garbage.runDir, "01", 0, [])] }), heavy_wait: 1 },
    ]);
    expect(states.map(errorOf)).toEqual([null, null]);
    const exec = states.map((state) => tsAfter(state).get("exec") as PyDict);
    expect(exec.map((item) => [item.get("check_exit"), item.get("check_ok")])).toEqual([[3n, false], [0n, true]]);
    expect(String(exec[0]?.get("check_tail"))).toContain("重活车道排到上限（1 秒）也没排到（车道空着，排在前面的是 T009 的执行检查）：执行检查 没有跑，不是检查不过");
    expect(kinds(states[0], "heavy.")).toEqual([]);
    expect(kinds(states[1], "heavy.")).toEqual([["heavy.entered", "执行检查", null], ["heavy.left", "执行检查", null]]);
  }, 600_000);
});

describe("第 155 轮：落地先排车道、再在车道里试落地锁（手写）", () => {
  const meta = { "msg-id": "20261101T000000000000Z-coordinator-000000", from: COORDINATOR, to: "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none", type: "通过" };
  function landScene(more: (repo: string) => void): { sc: Scene; path: string } {
    const box = { path: "" };
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map<string, PyValue>([["tasks", new Map([["T001", taskState(head, "5-exec")]])]])));
      box.path = letter(repo, "exec-step", meta["msg-id"], COORDINATOR, "T001-5-exec", "通过");
      more(repo);
    });
    return { sc, path: box.path };
  }

  it("落地锁被另一个进程拿着：让出车道，信留在 new；车道被另一个进程拿着：交回“重活车道排不到”；有人挡着时不进车道；别的主任务的执行端不挡（第 174 轮）", () => {
    const locked = landScene((repo) => held(repo, ".land", null));
    const queued = landScene((repo) => held(repo, ".heavy", { label: "基线检查", task: "T009" }));
    const blocked = landScene((repo) => {
      const mark = { task: "T009-after-land", label: "T009 合入后的门禁回归与落地预演", sweep: true };
      put(repo, `${BOX}/ledger/exec-active/T009-after-land.json`, `${JSON.stringify(mark)}${LF}`);
    });
    const both = landScene((repo) => { // 第 174 轮：别的主任务的执行端不挡结项，后台回归照样挡
      put(repo, `${BOX}/ledger/exec-active/T002.json`, `${JSON.stringify({ task: "T002" })}${LF}`);
      const mark = { task: "T009-after-land", label: "T009 合入后的门禁回归与落地预演", sweep: true };
      put(repo, `${BOX}/ledger/exec-active/T009-after-land.json`, `${JSON.stringify(mark)}${LF}`);
    });
    const states = agreeFlow([
      { ...flow("land", locked.sc, [null, locked.path, meta]), land_try: 1 },
      { ...flow("land", queued.sc, [null, queued.path, meta]), heavy_wait: 1 },
      flow("land", blocked.sc, [null, blocked.path, meta]),
      flow("land", both.sc, [null, both.path, meta]),
    ]);
    expect(states.map(errorOf)).toEqual([null, null, null, null]);
    expect(states.map((state) => returned(state))).toEqual([
      ["落地锁被占"], ["重活车道排不到"], ["T009 合入后的门禁回归与落地预演"], ["T009 合入后的门禁回归与落地预演"],
    ]);
    expect(kinds(states[0], "heavy.")).toEqual([["heavy.entered", "落地检查", null], ["heavy.left", "落地检查", null]]);
    expect(events(states[1]).map((event) => [event["event"], event["task"], event["behind"]])).toEqual([["heavy.queued", "T001", "T009 的基线检查"]]);
    expect(kinds(states[2], "heavy.")).toEqual([]);
    expect(kinds(states[3], "heavy.")).toEqual([]);
  }, 600_000);
});

describe("第 155 轮：基线检查只有全量回归不符时原样重跑一次（手写）", () => {
  const GATE_TEST = lines("import sys", "sys.path.insert(0, 'src')", "", "", "def test_title():", "    from doc import title", "    assert title() == 'new'");
  /** 过得了 contract_requirements 的合同：V01 跑本片的门禁基准（必要、基线应失败），R01 跑先前各片的（必要、基线应通过）。 */
  const md = (head: string): string => lines(
    "# TASK: t001-doc", "", "## Identity", "- plan_version: 1", "- repository: test", `- base_sha: ${head}`, "- risk_level: low",
    "- authorized_actions: local_edit, local_test", "- integration_actions: local_branch, merge", CONTRACT_EXECUTOR_LINE, "",
    "## Goal", "title() 交回 new。", "", "## Scope", "- allowed_modified_files: src/doc.py", "- allowed_new_files: 无", "- forbidden_paths: tests/test_gate_t001_*.py", "",
    "## Validation commands", `- V01（必要，基线应失败）: ${BT}python -m pytest ${GATE} -q${BT}`, `- R01（必要，基线应通过）: ${BT}python -m pytest ${OLD_GATE} -q${BT}`, "",
    "## Definition of done", "- D01: title 交回 new；证据：V01、R01。", "");
  const json = JSON.stringify({
    scope: { allowed_modified_files: ["src/doc.py"], forbidden_paths: ["tests/test_gate_t001_*.py"] },
    checks: [
      { id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"], expect_on_base: "fail", required: true },
      { id: "R01", argv: ["python", "-m", "pytest", OLD_GATE, "-q"], expect_on_base: "pass", required: true },
    ],
    executor: { provider: EXECUTOR[0], model: EXECUTOR[1], thinking: EXECUTOR[2] }, authorization: { integration: ["local_branch", "merge"] },
    budget: { max_attempts_total: 6, max_wall_seconds_per_attempt: 600 },
  });
  const item = (id: string, gate: string, code: number, nn: string): Record<string, unknown> =>
    ({ id, argv: ["python", "-m", "pytest", gate, "-q"], log: `${nn}/${id}.log`, exit_code: code, timed_out: false, interrupted: false, spawn_error: null });
  const baseline = (nn: string, code: number, mismatches: string[], r01: number, r01Log: string, limit = 1800): unknown => {
    const dir = `.agent/runs/t001-doc/baseline/${nn}`;
    return pd(["baseline", KEY], code, `基线检查记录：${dir}/checks.json${LF}`, limit, {
      [`0/${dir}/checks.json`]: JSON.stringify({ mismatches, results: [item("V01", GATE, 1, nn), item("R01", OLD_GATE, r01, nn)] }),
      [`0/${dir}/V01.log`]: lines("1 failed in 0.01s"), [`0/${dir}/R01.log`]: r01Log,
    });
  };

  it("第一次只有 R01 不符：原样重跑，第二次相符照通过（基准测试锁定、ts 记 flaky、账本记重跑）", () => {
    const sc = scene({ "src/doc.py": FILES["src/doc.py"], [OLD_GATE]: FILES[OLD_GATE] }, (repo, wt, head) => {
      put(repo, V1.md, md(head));
      put(repo, V1.json, json);
      put(wt, GATE, GATE_TEST);
    });
    const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
    ts.set("contract", py(V1));
    ts.set("workspaces", py({ gate: { path: sc.wt } }));
    const inner = [
      pd(["derive-json", KEY, "--force", "--title", "改文档"], 0, "ok"), pd(["validate", KEY], 0, "ok"),
      baseline("01", 1, ["R01"], 1, lines(`FAILED ${RED} - AssertionError`, "1 failed in 0.01s")),
      baseline("02", 0, [], 0, lines("1 passed in 0.01s")),
    ];
    const [state] = agreeFlow([flow("accept_gate_pre", sc, [ts, sc.wt], { inner })]);
    expect([errorOf(state), returned(state)]).toEqual([null, []]);
    const after = tsAfter(state);
    expect([(after.get("oracle") as PyDict).get("locked"), (after.get("oracle") as PyDict).get("baseline_exit")]).toEqual([true, 0n]);
    const [first] = after.get("flaky") as PyDict[];
    expect([first?.get("label"), first?.get("checks"), first?.get("failed")]).toEqual(["基线检查", ["R01"], [RED]]);
    expect(kinds(state, "regression.")).toEqual([["regression.rerun", "基线检查", 0], ["regression.flaky", "基线检查", null]]);
  }, 600_000);

  it("第 177 轮：基线检查的外层时限是合同里准备命令与各条检查的时限之和加 600 秒（这份是 4800），不少于 1800", () => {
    const timed = JSON.stringify({ ...JSON.parse(json), setup: [{ id: "S01", argv: ["npm", "ci"], timeout_seconds: 900 }],
      checks: JSON.parse(json).checks.map((check: Record<string, unknown>) => ({ ...check, timeout_seconds: check["id"] === "R01" ? 2700 : 600 })) });
    const sc = scene({ "src/doc.py": FILES["src/doc.py"], [OLD_GATE]: FILES[OLD_GATE] }, (repo, wt, head) => {
      put(repo, V1.md, md(head));
      put(repo, V1.json, timed);
      put(wt, GATE, GATE_TEST);
    });
    const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
    ts.set("contract", py(V1));
    ts.set("workspaces", py({ gate: { path: sc.wt } }));
    const inner = [
      pd(["derive-json", KEY, "--force", "--title", "改文档"], 0, "ok"), pd(["validate", KEY], 0, "ok"),
      baseline("01", 0, [], 0, lines("1 passed in 0.01s"), 4800),
    ];
    const [state] = agreeFlow([flow("accept_gate_pre", sc, [ts, sc.wt], { inner })]);
    expect([errorOf(state), returned(state)]).toEqual([null, []]);
    expect((tsAfter(state).get("oracle") as PyDict).get("baseline_exit")).toBe(0n);
  }, 600_000);
});
