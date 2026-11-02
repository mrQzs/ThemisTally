// 第 ⑤f 片的手写对照（采样那份在 hub-gatepost.contract.test.ts）：临时仓库上搭好场景（仓库与仓库外的候选 worktree，带 .git 的快照），
// 三边各自先原地放回再跑，交回值、ts、文件、账本、git 状态逐字比。样本没走到的分支在这里：
//   - accept_gate_post 先挡下的几种；白盒测试的各种结果（run_supervised 照手写的记录注入）；
//   - run_mutations 的清单、锚点核对、mutate 的记录（run_pd 照手写的记录注入），白盒用时 11.8、12.0、20.0 对变异时限与整份时限的影响；
//   - gate_spec、unchanged_mismatches、defect_match_problems 等纯函数的手写边界，以及按种子随机换类型的对照（模型交来的值）；
//   - ensure_worktree、apply_candidate、seed_whitebox 用真 git（worktree_root、mkdtemp 注入固定的名字），add_worktree 真失败三次；
//   - 真跑白盒 pytest、真跑 mutate 各一组：钉不住的照 ⑤f 设计稿第 11.2 节打占位（只在比较这一步打）。
// 不写转义序列。
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, prng, runAgreeing, runProbe } from "./harness.ts";
import {
  AT, C, CR, DURATION, LF, type Scene, agreeFlow, flow, kernelPython, pd, py, returned, scene, text, tsAfter, written,
} from "./flow-fixtures.ts";
import { put, removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const WHITEBOX = "tests/test_gate_t001_whitebox.py";
const SPEC_FILE = "mutation-spec.json";
/** 钉住的时刻（flow-fixtures 的 PIN）照 utc_compact 写出来的样子。 */
const STAMP = "20261101T000000000000Z";
const STAGE_KEY = "0/.agent/mailbox/tasks/T001-6-gate-post";
const lines = (...items: string[]): string => [...items, ""].join(LF);
const BASE_FILES = { "src/doc.py": lines("def title():", "    return 'old'"), "README.md": lines("基线") };
const GOOD_TEST = lines("import sys", "sys.path.insert(0, 'src')", "", "", "def test_title():", "    from doc import title", "    assert title() == 'old'");
const BAD_TEST = lines("def test_bad():", "    assert False");
const b64 = (value: string): string => Buffer.from(value, "utf8").toString("base64");
const stageDir = (sc: Scene): string => join(sc.repo, ".agent", "mailbox", "tasks", "T001-6-gate-post");
const runDir = (sc: Scene): string => join(sc.repo, ".agent", "runs", "t1", "attempt-001");
const specPath = (sc: Scene): string => join(stageDir(sc), `mutation-spec-${STAMP}.json`);
const outDir = (sc: Scene): string => join(stageDir(sc), "evidence", `mutate-${STAMP}`);
const pytestArgv = (): string[] => [kernelPython(), "-m", "pytest", "-p", "no:cacheprovider", WHITEBOX, "-q", "-rfE"];

/** 战后门禁那一刻的主任务状态：attempt 目录在仓库里，候选 worktree 记在 workspaces 里（基线状态是空的）。 */
function postTs(sc: Scene, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  ts.set("exec", py({ run_dir: runDir(sc) }));
  ts.set("oracle", py({ sha: sc.head }));
  ts.set("workspaces", py({ "post-attempt-001": { path: sc.wt, commit: sc.head, baseline_status: [] } }));
  for (const [key, value] of Object.entries(extra)) ts.set(key, value instanceof Map ? (value as PyDict) : py(value));
  return ts;
}

/** 手写的一次白盒 run_supervised：核对的参数照 accept_gate_post；调用期间把 log 写进白盒日志，交回给定的结果（wall_seconds 是浮点）。 */
function supervised(sc: Scene, log: string, result: { exit_code: number | null; timed_out?: boolean; wall_seconds?: number }): unknown {
  const value: PyDict = new Map<string, PyValue>([
    ["exit_code", result.exit_code === null ? null : BigInt(result.exit_code)], ["timed_out", result.timed_out ?? false], ["interrupted", false],
    ["spawn_error", null], ["wall_seconds", result.wall_seconds ?? 1.5], ["stray_processes", false], ["kill_method", null], ["pid", 4242n],
    ["ctrl_break", null], ["ctrl_break_winerror", null],
  ]);
  return {
    fn: "run_supervised", argv: pytestArgv(), cwd: sc.wt, env: true, stdout: [join(stageDir(sc), "evidence", `whitebox-${STAMP}.log`), "create-new"],
    stderr: "stdout", timeout: 1800, grace: 15, handle_signals: true, on_spawn: false, value: toTagged(value),
    files: { write: { [`${STAGE_KEY}/evidence/whitebox-${STAMP}.log`]: b64(log) }, delete: [] },
  };
}
const anchors = (sc: Scene, code: number, out: string): unknown => pd(["mutate", "--tree", sc.wt, "--spec", specPath(sc), "--check-anchors"], code, out);
const mutateCall = (sc: Scene, budget: number, record: unknown, code = 0, out = "变异 2 个：抓住 1，漏掉 0，跳过 0，出错 0"): unknown =>
  pd(["mutate", "--tree", sc.wt, "--spec", specPath(sc), "--out", outDir(sc)], code, out, budget,
    { [`${STAGE_KEY}/evidence/mutate-${STAMP}/mutations.json`]: typeof record === "string" ? record : JSON.stringify(record) });
const ANCHORS_OK = "锚点核对：2 条，0 条不符";

const PASS_LOG = lines(".                                                                        [100%]", "1 passed in 0.05s");
const summary = (...reports: string[]): string[] => ["=========================== short test summary info ===========================", ...reports];
const SOFT_LOG = lines("xs.", "1 passed, 2 skipped, 1 xfailed in 0.05s");
const FAIL_LOG = lines("F.", ...summary(`FAILED ${WHITEBOX}::test_bad - assert False`), "1 failed, 1 passed in 0.05s");
const FAIL2_LOG = lines("FF", ...summary(`FAILED ${WHITEBOX}::test_bad - assert False`, `FAILED ${WHITEBOX}::Case::test_other[1] - x`), "2 failed in 0.05s");
const LONG_LOG = lines(...Array.from({ length: 18 }, (_, at) => `第 ${at + 1} 行输出`), ...summary(`FAILED ${WHITEBOX}::test_bad - assert False`), "1 failed in 0.05s");
const ERROR_LOG = lines("FE", ...summary(`FAILED ${WHITEBOX}::test_bad - assert False`, `ERROR ${WHITEBOX}::test_err - fixture`), "1 failed, 1 error in 0.05s");

const SPEC2 = {
  mutations: [{ name: "改标题", file: "src/doc.py", old: "'old'", new: "'x'" }, { name: "等价", file: "src/doc.py", old: "return", new: "return", equivalent: "同一个字" }],
};
const RECORD_OK = { counts: { caught: 1, missed: 1 }, results: [{ id: "M01", status: "caught", unexpected: [] }, { id: "M02", status: "missed", unexpected: [] }] };
const defect = (test: string): Record<string, string> => ({ test, contract: "合同第 3 条", where: "src/doc.py:2" });
/** attempt 目录里的 scope.json，加上战后门禁阶段的目录（存档的清单写在这里；平时由 accept_gate_post 建 evidence 时一起建）。 */
function attempt(repo: string, files: unknown[]): void {
  put(repo, ".agent/runs/t1/attempt-001/scope.json", JSON.stringify({ files }));
  mkdirSync(join(repo, ".agent", "mailbox", "tasks", "T001-6-gate-post"), { recursive: true });
}

describe("第 ⑤f 片：accept_gate_post（手写）", () => {
  it("先挡下的几种：改了文件、多了别的新文件（排好序、只列前 8 个）；没有新增白盒测试（清单文件可以新增）；上一版锚点对不上的条目跨交付留着", () => {
    const many = scene(BASE_FILES, (_repo, wt) => {
      put(wt, "src/doc.py", lines("def title():", "    return 'changed'"));
      for (const name of ["z", "b", "a", "y", "c", "x", "d", "w", "e"]) put(wt, `notes/${name}.txt`, "x");
      put(wt, WHITEBOX, GOOD_TEST);
    });
    const none = scene(BASE_FILES, (_repo, wt) => put(wt, SPEC_FILE, "{}"));
    const [blocked, missing] = agreeFlow([
      flow("accept_gate_post", many, [postTs(many), many.wt, {}]),
      flow("accept_gate_post", none, [postTs(none, { gate_post: { anchor_mismatch: { 等价: "return" }, ok: true, whitebox_seconds: 3.5 } }), none.wt, {}]),
    ]);
    // （状态，路径）按元组排：“ M”排在“??”前面
    expect(returned(blocked)).toEqual([`战后只能新增 ${WHITEBOX}（只增不改）：src/doc.py, notes/a.txt, notes/b.txt, notes/c.txt, notes/d.txt, notes/e.txt, notes/w.txt, notes/x.txt`]);
    expect(returned(missing)).toEqual([`没有新增 ${WHITEBOX}`]);
    expect([...(tsAfter(missing).get("gate_post") as PyDict).keys()]).toEqual(["ran", "ok", "anchor_mismatch"]);
  });

  it("白盒测试的几种结果（注入 run_supervised）：通过时列了缺陷、没有清单；xfail 与 skip；红的正好是列的缺陷；对不上；出错；超时；缺陷写得不对", () => {
    const sc = scene(BASE_FILES, (_repo, wt) => put(wt, WHITEBOX, GOOD_TEST));
    const run = (log: string, result: Parameters<typeof supervised>[2], output: Record<string, unknown>, extra: unknown[] = []): ProbeRequest =>
      flow("accept_gate_post", sc, [postTs(sc), sc.wt, output], { inner: [supervised(sc, log, result), ...extra], replaced: ["run_supervised", "run_pd"] });
    const results = agreeFlow([
      run(PASS_LOG, { exit_code: 0 }, { candidate_defects: [defect("test_bad"), defect("test_x")] }),
      run(SOFT_LOG, { exit_code: 0 }, {}),
      run(FAIL_LOG, { exit_code: 1 }, { candidate_defects: [defect("test_bad")] }),
      run(FAIL2_LOG, { exit_code: 1 }, { candidate_defects: [defect(`${WHITEBOX}::test_bad`), defect("test_missing")] }),
      run(FAIL2_LOG, { exit_code: 1 }, { candidate_defects: [defect("test_bad"), defect("test_other")] }),
      run(ERROR_LOG, { exit_code: 1 }, { candidate_defects: [defect("test_bad")] }),
      run(FAIL_LOG, { exit_code: null, timed_out: true }, {}), run(LONG_LOG, { exit_code: 1 }, {}),
      run(FAIL_LOG, { exit_code: 1 }, { candidate_defects: "test_bad" }),
      run(FAIL_LOG, { exit_code: 1 }, { candidate_defects: [{ test: " test_bad ", contract: 0, where: [] }, "x", { test: "test_bad", contract: "c", where: "w" }] }),
      run(PASS_LOG, { exit_code: 0 }, { mutation_spec: SPEC2 }, [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, 3600, RECORD_OK)]),
    ]);
    const shown = results.map((state) => returned(state) as string[]);
    expect(shown[0]?.[0]).toBe("candidate_defects 列了 2 条，可白盒测试在候选上全部通过：每处缺陷要有一条红的测试证明");
    expect(shown[1]?.[0]).toContain("白盒测试里有 1 个 xfailed、2 个 skipped");
    expect([shown[2], (tsAfter(results[2]).get("gate_post") as PyDict).get("ok")]).toEqual([[], false]);
    expect(shown[3]).toEqual([`这些用例红了，candidate_defects 却没有列：${WHITEBOX}::Case::test_other[1]（白盒测试自己有错就改测试）`,
      "candidate_defects 列的这些用例没有红：test_missing"]);
    expect(shown[4]).toEqual([]);
    expect(shown[5]?.[0]).toContain("白盒测试在候选上没有全部通过（候选");
    expect(shown[6]?.[0]).toContain("没有全部通过（超时）");
    expect(String(shown[7]?.[0]).split(LF).length).toBe(16); // 问题文字的一行加白盒日志的最后 15 行
    expect(shown[8]?.[0]).toBe(`candidate_defects 要是列表：[{"test", "contract", "where"}]`);
    expect(shown[9]?.slice(0, 2)).toEqual(["candidate_defects 第 1 条缺 contract、where", "candidate_defects 第 2 条缺 test、contract、where"]);
    expect([shown[10], (tsAfter(results[10]).get("gate_post") as PyDict).get("ok")]).toEqual([[], true]);
    expect(Object.keys(written(results[10]))).toContain(`${STAGE_KEY}/evidence/whitebox-${STAMP}.py`);
  });
});

describe("第 ⑤f 片：run_mutations（手写，注入 run_pd）", () => {
  const scope = { files: [{ path: "src/doc.py", status: "M" }, { path: "lib/x.bin", status: "A" }, { path: "tests/test_a.py", status: "A" },
    { path: "src/gone.py", status: "D" }, { path: "web/a.test.ts", status: "M" }] };
  const MULTI = { commands: [{ id: "W1", argv: ["x"] }, { id: "W2", argv: ["y"] }], mutations: SPEC2.mutations };
  const SPEC30 = { mutations: Array.from({ length: 30 }, (_, at) => ({ name: `M${at + 1}`, file: "src/doc.py", old: "return", new: "return" })) };

  it("时限：白盒用时 11.8、12.0、20.0 秒，没有用时，门禁端写了时限，写了个假的时限；整份的时限按条数放宽", () => {
    const sc = scene(BASE_FILES, (repo) => attempt(repo, []));
    const run = (seconds: number | null, spec: Record<string, unknown>, budget: number): ProbeRequest => {
      const gate = new Map<string, PyValue>([["ran", true], ["ok", false], ["whitebox_seconds", seconds]]);
      return flow("run_mutations", sc, [postTs(sc, { gate_post: gate }), sc.wt, stageDir(sc), { mutation_spec: spec }],
        { inner: [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, budget, RECORD_OK)] });
    };
    const results = agreeFlow([
      run(11.8, SPEC2, 3600), run(12.0, SPEC2, 3600), run(20.0, SPEC30, 3731), run(null, SPEC2, 3600), run(12.0, { ...SPEC2, timeout_seconds: 2000 }, 6600),
      run(12.0, { timeout_seconds: 0, ...SPEC2 }, 3600), run(20.0, { commands: MULTI.commands, mutations: SPEC30.mutations }, 6862), run(null, SPEC30, 19200),
    ]);
    const gate = (at: number): PyDict => tsAfter(results[at]).get("gate_post") as PyDict;
    expect(results.map((_, at) => gate(at).get("mutant_timeout"))).toEqual([60n, 61n, 101n, null, 2000n, 61n, 101n, null]);
    expect(results.map((state) => returned(state))).toEqual([[], [], [], [], [], [], [], []]);
    const archived = JSON.parse(text(results[5], `${STAGE_KEY}/mutation-spec-${STAMP}.json`)) as Record<string, unknown>;
    expect(Object.keys(archived)).toEqual(["timeout_seconds", "mutations"]); // 已有的键换值不挪位置
    expect(gate(0).get("equivalent")).toEqual(["等价：同一个字"]);
  });

  it("清单：没有、空的、列满 expect_missed、交文件、孤立代理项（写存档时报 UnicodeEncodeError、留下空文件）", () => {
    const sc = scene(BASE_FILES, (repo, wt) => {
      attempt(repo, []);
      put(wt, SPEC_FILE, JSON.stringify(SPEC2, null, 2));
    });
    const gate = { ran: true, ok: false, whitebox_seconds: 12.5 };
    const run = (output: Record<string, unknown>, inner: unknown[] = []): ProbeRequest =>
      flow("run_mutations", sc, [postTs(sc, { gate_post: gate }), sc.wt, stageDir(sc), output], { inner, replaced: ["run_pd"] });
    const everywhere = { commands: [{ id: "W1" }, { id: "W2" }], mutations: [{ name: "全漏", expect_missed: ["W2", "W1"] }, { name: "只漏一条", expect_missed: ["W2"] }] };
    const partly = { commands: [{ id: "W1" }, { id: "W2" }, { id: "W3" }], mutations: [
      { name: "改标题", file: "src/doc.py", old: "'old'", new: "'x'", expect_missed: ["W1", "W2"] },
      { name: "改返回", file: "src/doc.py", old: "return", new: "return ", expect_missed: ["W3", 1] }] };
    const results = agreeFlow([
      run({}), run({ mutation_spec: { mutations: [] } }), run({ mutation_spec: [1] }), run({ mutation_spec: everywhere }),
      run({ mutation_spec_file: SPEC_FILE }, [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, 3600, RECORD_OK)]),
      run({ mutation_spec: { mutations: [{ name: `等价${C(0xd800)}`, file: "src/doc.py", old: "a", new: "b" }] } }),
      run({ mutation_spec: partly }, [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, 3600, RECORD_OK)]),
    ]);
    const shown = results.map((state) => returned(state));
    expect(shown[0]).toEqual(["输出里没有 mutation_spec（mutate --spec 的格式，至少一条变异），也没有 mutation_spec_file"]);
    expect(shown[1]).toEqual(shown[0]);
    expect(shown[2]).toEqual(shown[0]);
    expect(String((shown[3] as string[])[0])).toContain("等于声明等价：全漏。");
    expect(shown[4]).toEqual([]);
    expect(shown[5]).toBe("UnicodeEncodeError");
    expect(text(results[5], `${STAGE_KEY}/mutation-spec-${STAMP}.json`)).toBe("");
    // 两项以上、又没列满每一条命令：按“、”连，不是字符串的照 str
    expect((tsAfter(results[6]).get("gate_post") as PyDict).get("expect_missed")).toEqual(["改标题：W1、W2", "改返回：W3、1"]);
  });

  it("锚点核对没过：记下对不上的（编号可以是 Unicode 数字）；下一版一字没改就点名；核对过了就清掉", () => {
    const sc = scene(BASE_FILES, (repo) => attempt(repo, []));
    const failed = lines("OK       M01 改标题  出现 1 次", `MISMATCH M${C(0x660, 0x662)} 等价  出现 0 次，期望 1 次`, "         最相近 L2（88%）：return 'old'",
      "MISSING  M09 不存在的  文件不在", "锚点核对：2 条，1 条不符");
    const run = (gate: Record<string, unknown>, inner: unknown[], spec: Record<string, unknown> = SPEC2): ProbeRequest =>
      flow("run_mutations", sc, [postTs(sc, { gate_post: { ran: true, ok: false, whitebox_seconds: 2.5, ...gate } }), sc.wt, stageDir(sc), { mutation_spec: spec }],
        { inner });
    // 名字不是字符串：一条没有 name、一条 name 是 true
    const odd = { mutations: [{ file: "src/doc.py", old: "a", new: "b" }, { name: true, file: "src/doc.py", old: "c", new: "d" }] };
    const oddOut = lines("MISMATCH M01 None  出现 0 次，期望 1 次", "MISMATCH M02 True  出现 0 次，期望 1 次", "锚点核对：2 条，2 条不符");
    const results = agreeFlow([
      run({}, [anchors(sc, 1, failed)]),
      run({ anchor_mismatch: { 等价: "return" } }, [anchors(sc, 1, failed)]),
      run({ anchor_mismatch: { 等价: "retur" } }, [anchors(sc, 1, failed)]),
      run({ anchor_mismatch: { 等价: "return" } }, [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, 3600, RECORD_OK)]),
      run({}, [anchors(sc, 1, oddOut)], odd),
      run({ anchor_mismatch: { None: "a", True: "c" } }, [anchors(sc, 1, oddOut)], odd),
    ]);
    const shown: string[] = results.map((state) => (returned(state) as string[])[0] ?? "");
    expect(String(shown[0]).startsWith("变异清单没有通过锚点核对")).toBe(true);
    expect(shown[0]).toContain(`MISMATCH M${C(0x660, 0x662)} 等价`);
    expect((tsAfter(results[0]).get("gate_post") as PyDict).get("anchor_mismatch")).toEqual(new Map([["等价", "return"]]));
    expect(String(shown[1]).startsWith("这几条与上一版清单一字不差：上次就对不上，这次没有改：等价。")).toBe(true);
    expect(String(shown[2]).startsWith("变异清单没有通过锚点核对")).toBe(true);
    expect([shown[3], (tsAfter(results[3]).get("gate_post") as PyDict).has("anchor_mismatch")]).toEqual(["", false]);
    // 键照 str(name)；下一版原样交上来时 unchanged_mismatches 拿原值查键（None、True 查不到“None”“True”），不点名
    expect((tsAfter(results[4]).get("gate_post") as PyDict).get("anchor_mismatch")).toEqual(new Map([["None", "a"], ["True", "c"]]));
    expect(String(shown[5]).startsWith("变异清单没有通过锚点核对")).toBe(true);
  });

  it("mutate 的记录：多条命令里漏网的按命令说、一条都没抓住的命令；没生效与出错；基线就红；记录读不出；超时", () => {
    const sc = scene(BASE_FILES, (repo) => attempt(repo, []));
    const gate = { ran: true, ok: false, whitebox_seconds: 12.0 };
    const run = (spec: Record<string, unknown>, budget: number, record: unknown, code = 0, out?: string): ProbeRequest =>
      flow("run_mutations", sc, [postTs(sc, { gate_post: gate }), sc.wt, stageDir(sc), { mutation_spec: spec }],
        { inner: [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, budget, record, code, out)] });
    const multi = {
      commands: [{ id: "W1" }, { id: "W2" }],
      results: [{ id: "M01", status: "caught", commands: { W1: { status: "caught" }, W2: { status: "missed" } }, unexpected: ["W2"] },
        { id: "M02", status: "missed", commands: { W1: { status: "missed" }, W2: { status: "missed" } }, unexpected: ["W1", "W2"] }],
    };
    const broken = { results: [{ id: "M01", status: "skipped", unexpected: [] }, { id: "M02", status: "error", unexpected: [] }] };
    // 30 行输出，前后带空行，第 15 行夹一个 U+2028（tail 先 strip、再按 splitlines 分）
    const long = ["", "", ...Array.from({ length: 30 }, (_, at) => (at === 14 ? `第 15 行${C(0x2028)}续` : `第 ${at + 1} 行`)), "", ""].join(LF);
    const results = agreeFlow([
      run(MULTI, 3600, multi), run(SPEC2, 3600, broken), run(SPEC2, 3600, { aborted: "baseline_failed", baseline: {} }, 1, "MUTATE baseline ... 失败"),
      run(SPEC2, 3600, "{"), run(SPEC2, 3600, RECORD_OK, 124, "超时（3600 秒）：mutate"),
      run(SPEC2, 3600, RECORD_OK, 0, long), run(SPEC2, 3600, "{", 0, long),
    ]);
    const shown = results.map((state) => returned(state) as string[]);
    expect(shown[0]).toEqual(["2 条变异漏网、也没有声明等价：M01、M02（按命令：W1 漏掉 M02；W2 漏掉 M01、M02）", expect.stringContaining("命令 W2 一条变异都没抓住。")]);
    expect(shown[1]).toEqual(["2 条变异没有生效或运行出错（skipped / error；old 片段要在文件里逐字出现）：M01、M02", "没有一条变异被抓住：变异检查什么也没证明"]);
    expect(shown[2]?.[0]).toContain("基线就红了");
    expect(shown[3]?.[0]).toBe(`变异检查没有跑完（退出码 0）：${LF}变异 2 个：抓住 1，漏掉 0，跳过 0，出错 0`);
    expect(shown[4]?.[0]).toContain("（退出码 124）");
    // mutate_tail 与“没有跑完”后面都正好 25 行：31 行里的最后 25 行
    const kept = (tsAfter(results[5]).get("gate_post") as PyDict).get("mutate_tail") as string;
    expect([kept.split(LF).length, kept.split(LF)[0], kept.split(LF).at(-1), kept.includes(C(0x2028))]).toEqual([25, "第 7 行", "第 30 行", false]);
    expect(shown[6]?.[0]).toBe(`变异检查没有跑完（退出码 0）：${LF}${kept}`);
  });

  it("变异要打在改动的文件上：测试文件与删掉的不算；unmutated 写了理由的放过，只记改动里的那几条", () => {
    const sc = scene(BASE_FILES, (repo) => attempt(repo, scope.files));
    const gate = { ran: true, ok: false, whitebox_seconds: 1.0 };
    const run = (output: Record<string, unknown>, inner: unknown[] = []): ProbeRequest =>
      flow("run_mutations", sc, [postTs(sc, { gate_post: gate }), sc.wt, stageDir(sc), { mutation_spec: SPEC2, ...output }], { inner, replaced: ["run_pd"] });
    const unmutated = [{ file: "lib/x.bin", reason: " 二进制 " }, { file: "other.py", reason: "不在改动里" }, { file: "src/doc.py", reason: "" }, "x"];
    const results = agreeFlow([run({}), run({ unmutated }, [anchors(sc, 0, ANCHORS_OK), mutateCall(sc, 3600, RECORD_OK)])]);
    expect(returned(results[0])).toEqual([`执行端改动了这些文件，变异清单却一条也没打在上面：lib/x.bin。每个改动的文件至少一条变异；确实没法变异的`
      + `（例如二进制文件），在输出的 unmutated 里写 {"file": ..., "reason": ...}，终审会复核`]);
    expect([returned(results[1]), (tsAfter(results[1]).get("gate_post") as PyDict).get("unmutated")]).toEqual([[], ["lib/x.bin：二进制"]]);
  });
});

describe("第 ⑤f 片：纯函数的手写边界（三边逐字比，报错比类型与文字）", () => {
  const call = (fn: string, args: PyValue[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map(toTagged) });
  const agree = (requests: readonly ProbeRequest[]): ProbeResult[] => {
    const { python, mismatches } = runAgreeing(requests);
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    return python;
  };
  const valueOf = (result: ProbeResult | undefined): PyValue => (result?.["ok"] ? fromTagged(result["value"] as Tagged) : `${result?.["error"]}: ${result?.["message"]}`);

  it("gate_spec：内联、两样都给、名字不对（各种类型）、不在或不是文件、不是 UTF-8、BOM、坏 JSON、字符串里的 CR、嵌套太深、不是字典", () => {
    const dir = (content?: string | Uint8Array, asDir = false): string => {
      const root = tempDir("gate-spec");
      if (asDir) mkdirSync(join(root, SPEC_FILE));
      else if (content !== undefined) writeFileSync(join(root, SPEC_FILE), content);
      return root;
    };
    const named = (value: PyValue): PyDict => new Map([["mutation_spec_file", value]]);
    const plain = dir("{}");
    const results = agree([
      call("gate_spec", [plain, new Map()]), call("gate_spec", [plain, py({ mutation_spec: { mutations: [] } })]),
      call("gate_spec", [plain, py({ mutation_spec_file: SPEC_FILE, mutation_spec: {} })]), call("gate_spec", [plain, py({ mutation_spec_file: SPEC_FILE, mutation_spec: null })]),
      ...["x.json", `${SPEC_FILE} `, 1n, 1.5, Number.NaN, true, false, [SPEC_FILE], new Map([["a", 1n]]), `it's`].map((value) => call("gate_spec", [plain, named(value as PyValue)])),
      call("gate_spec", [dir(), named(SPEC_FILE)]), call("gate_spec", [dir(undefined, true), named(SPEC_FILE)]),
      call("gate_spec", [dir(Buffer.from([0x7b, 0xff, 0x7d])), named(SPEC_FILE)]), call("gate_spec", [dir(`${C(0xfeff)}{}`), named(SPEC_FILE)]),
      call("gate_spec", [dir("{"), named(SPEC_FILE)]), call("gate_spec", [dir(`{"a": "x${CR}y"}`), named(SPEC_FILE)]),
      call("gate_spec", [dir(`${CR}${LF}{${CR}"a": 1,,}`), named(SPEC_FILE)]),
      call("gate_spec", [dir(`${"[".repeat(100_000)}${"]".repeat(100_000)}`), named(SPEC_FILE)]),
      call("gate_spec", [dir("[1, NaN]"), named(SPEC_FILE)]), call("gate_spec", [dir(JSON.stringify(SPEC2)), named(SPEC_FILE)]),
      call("gate_spec", [dir(`${'{"a": '.repeat(100_000)}1${"}".repeat(100_000)}`), named(SPEC_FILE)]),
    ]);
    const shown = results.map(valueOf);
    expect(shown[0]).toEqual([null, null]);
    expect(shown[2]).toEqual([null, "mutation_spec 与 mutation_spec_file 只给一样（建议只给文件）"]);
    expect(shown[4]).toEqual([null, `mutation_spec_file 只能是工作目录根下的 ${SPEC_FILE}，收到的是 'x.json'`]);
    expect(shown[13]).toEqual([null, `mutation_spec_file 只能是工作目录根下的 ${SPEC_FILE}，收到的是 "it's"`]);
    expect(shown[14]).toEqual([null, `mutation_spec_file 指的 ${SPEC_FILE} 不在工作目录根下，或者不是普通文件`]);
    expect(shown[15]).toEqual(shown[14]);
    expect(String((shown[16] as PyValue[])[1])).toContain("不是合法的 UTF-8 JSON：'utf-8' codec can't decode byte 0xff in position 1");
    expect(String((shown[17] as PyValue[])[1])).toContain("Unexpected UTF-8 BOM");
    expect(String(shown[21])).toMatch(/^RecursionError: .* decoding a JSON array /);
    expect(String(shown.at(-1))).toMatch(/^RecursionError: .* decoding a JSON object /);
  });

  it("unchanged_mismatches、defect_match_problems、defect_matches、mutant_timeout、expected_missed_everywhere、candidate_defects、attempt_base 的边界", () => {
    const gateTs = (before: PyValue): PyDict => py({ gate_post: before === undefined ? {} : { anchor_mismatch: before } }) as PyDict;
    const mutations = (...items: unknown[]): PyDict => new Map([["mutations", py(items)]]);
    const failed = Array.from({ length: 12 }, (_, at) => `t.py::test_${at}`);
    const runs = (meta?: string | Uint8Array): string => {
      const root = tempDir("attempt-base");
      if (meta !== undefined) writeFileSync(join(root, "meta.json"), meta);
      return root;
    };
    const oracle = py({ oracle: { sha: "o" } }) as PyDict;
    const results = agree([
      call("unchanged_mismatches", [gateTs(py({ 甲: "a", 乙: "b" })), mutations({ name: "甲", old: "a" }, { name: "乙", old: "c" }, { name: "丙", old: "a" }, "x", { old: "a" })]),
      call("unchanged_mismatches", [gateTs(py({ "1": "a" })), mutations({ name: 1, old: "a" })]),
      call("unchanged_mismatches", [gateTs(py({ 甲: "a" })), mutations({ name: ["甲"], old: "a" })]),
      call("unchanged_mismatches", [gateTs(py({ 甲: Number.NaN })), mutations({ name: "甲", old: Number.NaN })]),
      call("unchanged_mismatches", [gateTs(py({})), new Map([["mutations", 5n]])]), call("unchanged_mismatches", [gateTs(py({ 甲: "a" })), new Map([["mutations", "甲"]])]),
      call("unchanged_mismatches", [py({ gate_post: {} }) as PyDict, mutations({ name: "甲", old: "a" })]),
      call("defect_match_problems", [py([{ test: "test_0" }, { test: "t.py::test_1" }, { test: "nope" }]), failed]),
      call("defect_match_problems", [py(Array.from({ length: 12 }, (_, at) => ({ test: `missing_${at}` }))), []]),
      call("defect_match_problems", [py([]), failed]),
      ...[["test_x", "t.py::test_x[1]"], ["Case::test_x[1]", "t.py::Case::test_x[1]"], ["test_x[1]", "t.py::test_x[1]"], ["x", "t.py::test_xx"], ["t.py::test_x", "t.py::test_x"],
        ["test_x", "test_x"], ["", "t.py::"]].map((pair) => call("defect_matches", pair)),
      ...[11.8, 11.79, 12.0, 12.2, "12", Number.NaN, Number.POSITIVE_INFINITY, 0n, null, true, 1e308, "x"].map((seconds) => call("mutant_timeout", [new Map(), seconds as PyValue])),
      call("mutant_timeout", [py({ timeout_seconds: 5 }), 30.0]), call("mutant_timeout", [py({ timeout_seconds: 0 }), 30.0]), call("mutant_timeout", [[], 30.0]),
      call("expected_missed_everywhere", [py({ commands: [], mutations: [{ name: "空命令表", expect_missed: [] }] })]),
      call("expected_missed_everywhere", [py({ commands: "x", mutations: [{ name: "单条", expect_missed: ["main"] }, { name: "别的", expect_missed: ["W1"] }] })]),
      call("expected_missed_everywhere", [py({ commands: [{ id: 1 }, "x"], mutations: [{ name: "数", expect_missed: [1.0] }, { name: "真", expect_missed: [true] }] })]),
      call("expected_missed_everywhere", [py({ commands: [{ id: [1] }], mutations: [{ name: "a", expect_missed: [] }] })]),
      call("expected_missed_everywhere", [py({ commands: [{ id: "W1" }], mutations: [{ name: "a", expect_missed: [["W1"]] }] })]),
      call("expected_missed_everywhere", [py({ mutations: 3 })]), call("expected_missed_everywhere", [py({ mutations: { a: 1 } })]),
      ...[null, [], "x", 0n, [{}], [{ test: 1, contract: true, where: 1.5 }], [{ test: ["a"], contract: { b: 1 }, where: "  " }]].map((items) =>
        call("candidate_defects", [new Map([["candidate_defects", py(items)]])])),
      call("candidate_defects", [[]]),
      ...[undefined, "{", "[]", JSON.stringify({ base_sha: "" }), JSON.stringify({ base_sha: "abc" }), JSON.stringify({ base_sha: 1 }), Buffer.from([0xff])].map((meta) =>
        call("attempt_base", [oracle, runs(meta)])),
      call("attempt_base", [py({ oracle: {} }) as PyDict, runs(JSON.stringify({ base_sha: "abc" }))]), call("attempt_base", [py({ oracle: {} }) as PyDict, runs("{")]),
      call("mutation_problems", [0n, py({ commands: [{ id: "W1" }, { id: "W2" }], results: [{ id: "M01", status: "missed", unexpected: "W1W2" }] }), ""]),
      call("mutation_problems", [0n, py({ results: [{ id: "M01", status: [1], commands: { W1: { status: "caught" } }, unexpected: [] }] }), ""]),
      call("mutation_problems", [0n, py({ commands: [{ id: "W1" }], results: [{ id: "M01", status: "missed", unexpected: ["W1"] }] }), ""]),
    ]);
    const shown = results.map(valueOf);
    expect(shown[0]).toEqual(["甲"]);
    expect(shown.at(-3)).toEqual(["1 条变异漏网、也没有声明等价：M01（按命令：W1 漏掉 M01；W2 漏掉 M01）", expect.stringContaining("命令 W1、W2 一条变异都没抓住。"),
      "没有一条变异被抓住：变异检查什么也没证明"]);
    expect(shown.at(-1)).toEqual(["1 条变异漏网、也没有声明等价：M01", "没有一条变异被抓住：变异检查什么也没证明"]); // 只有一条命令：不按命令拆，也不说“一条都没抓住”
    expect(shown.at(-2)).toBe("TypeError: unhashable type: 'list'");
    expect(String(shown[2])).toBe("TypeError: unhashable type: 'list'");
    expect(String(shown[4])).toBe("TypeError: 'int' object is not iterable");
    expect(shown[7]).toEqual(["这些用例红了，candidate_defects 却没有列：t.py::test_2、t.py::test_3、t.py::test_4、t.py::test_5、t.py::test_6、t.py::test_7、t.py::test_8、t.py::test_9、t.py::test_10、t.py::test_11（白盒测试自己有错就改测试）",
      "candidate_defects 列的这些用例没有红：nope"]);
    expect(String(shown[9])).toContain("没有列：t.py::test_0、t.py::test_1、t.py::test_2、t.py::test_3、t.py::test_4、t.py::test_5、t.py::test_6、t.py::test_7、t.py::test_8、t.py::test_9（"); // 12 条只列前 10 条
    expect(shown.slice(17, 29)).toEqual([60n, 60n, 61n, expect.anything(), 61n, "ValueError: cannot convert float NaN to integer", "OverflowError: cannot convert float infinity to integer", null, null, 60n,
      expect.anything(), "ValueError: could not convert string to float: 'x'"]);
  });

  it("按种子随机换类型：清单、unmutated、candidate_defects、mutate 的记录、清单文件的名字都可以是任何 JSON 值（三边比交回值，崩溃比类型与文字）", () => {
    const next = prng(51);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
    const ATOMS: PyValue[] = [null, true, false, 0n, 1n, -1n, 2n ** 70n, 1.5, 0.0, Number.NaN, "", "x", "main", "W1", "W2", "M01", "src/doc.py", "tests/t.py", [], new Map()];
    const value = (depth = 0): PyValue => {
      const roll = next();
      if (depth > 1 || roll < 0.6) return pick(ATOMS);
      if (roll < 0.8) return Array.from({ length: Math.floor(next() * 3) }, () => value(depth + 1));
      return new Map(["id", "status", "name", "file"].filter(() => next() < 0.5).map((key) => [key, value(depth + 1)]));
    };
    const maybe = (fallback: () => PyValue, odd = 0.2): PyValue => (next() < odd ? value() : fallback());
    const dict = (entries: [string, () => PyValue][], keep = 0.7): PyDict => new Map(entries.filter(() => next() < keep).map(([key, make]) => [key, make()]));
    const mutation = (): PyValue => maybe(() => dict([["name", () => maybe(() => pick(["M1", "M2", "甲"]))], ["file", () => maybe(() => pick(["src/doc.py", "lib/x.bin"]))],
      ["old", () => maybe(() => pick(["return", "a"]))], ["expect_missed", () => maybe(() => Array.from({ length: Math.floor(next() * 3) }, () => pick<PyValue>(["W1", "W2", "main", 1n, 1.0, [1n]])), 0.3)],
      ["equivalent", () => maybe(() => pick(["同一个", ""]))]]), 0.1);
    const spec = (): PyValue => maybe(() => dict([["mutations", () => maybe(() => Array.from({ length: Math.floor(next() * 4) }, mutation), 0.15)],
      ["commands", () => maybe(() => Array.from({ length: Math.floor(next() * 3) }, () => maybe(() => new Map([["id", pick<PyValue>(["W1", "W2", 1n, null, [1n]])]]), 0.2)), 0.3)],
      ["timeout_seconds", () => pick<PyValue>([0n, 5n, 300n, 1.5, "60", null, true])]], 0.6), 0.1);
    const run = (): PyValue => maybe(() => dict([["status", () => pick<PyValue>(["caught", "missed", "skipped", "error", null, 1n])], ["id", () => pick<PyValue>(["M01", "M02", 3n, null])],
      ["commands", () => maybe(() => new Map(["W1", "W2"].filter(() => next() < 0.6).map((cid) => [cid, maybe(() => new Map([["status", pick<PyValue>(["caught", "missed", [1n]])]]), 0.15)])), 0.25)],
      ["unexpected", () => maybe(() => Array.from({ length: Math.floor(next() * 3) }, () => pick<PyValue>(["W1", "W2", "main", "", [1n]])), 0.25)]], 0.8), 0.1);
    const record = (): PyValue => maybe(() => dict([["results", () => maybe(() => Array.from({ length: Math.floor(next() * 4) }, run), 0.15)],
      ["commands", () => maybe(() => Array.from({ length: Math.floor(next() * 3) }, () => maybe(() => new Map([["id", pick<PyValue>(["W1", "W2", 1n])]]), 0.2)), 0.2)],
      ["aborted", () => pick<PyValue>(["baseline_failed", null, "x"])]], 0.7), 0.1);
    const scopes = [[], [{ path: "src/doc.py", status: "M" }, { path: "lib/x.bin", status: "A" }], [{ path: 1, status: "M" }], [{ path: "tests/t.py" }, "x", { path: "", status: "D" }]].map((files) => {
      const root = tempDir("random-scope");
      writeFileSync(join(root, "scope.json"), JSON.stringify({ files }));
      return root;
    });
    const workspace = tempDir("random-spec");
    writeFileSync(join(workspace, SPEC_FILE), JSON.stringify(SPEC2));
    const call = (fn: string, args: PyValue[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map(toTagged) });
    const requests: ProbeRequest[] = [];
    for (let at = 0; at < 160; at += 1) {
      requests.push(call("expected_missed_everywhere", [spec()]));
      requests.push(call("mutant_timeout", [spec(), pick<PyValue>([null, 0n, 11.8, 12.0, "12", Number.NaN, true, "x", 2n ** 70n])]));
      requests.push(call("unchanged_mismatches", [py({ gate_post: { anchor_mismatch: dict([["M1", value], ["甲", value]]) } }) as PyDict, spec()]));
      requests.push(call("candidate_defects", [maybe(() => dict([["candidate_defects", () => maybe(() => Array.from({ length: Math.floor(next() * 3) },
        () => maybe(() => dict([["test", value], ["contract", value], ["where", value]]))), 0.3)]]), 0.1)]));
      requests.push(call("mutation_problems", [pick<PyValue>([0n, 1n, 124n, 0.0]), record(), pick(["", "变异 2 个", lines("a", "b")])]));
      requests.push(call("unmutated_problems", [py({ exec: { run_dir: pick(scopes) }, gate_post: {} }) as PyDict, spec(),
        maybe(() => dict([["unmutated", () => maybe(() => Array.from({ length: Math.floor(next() * 3) }, () => maybe(() => dict([["file", value], ["reason", value]]))), 0.3)]]), 0.1)]));
      requests.push(call("gate_spec", [workspace, maybe(() => dict([["mutation_spec_file", () => maybe(() => SPEC_FILE, 0.5)], ["mutation_spec", () => maybe(() => null, 0.5)]]), 0.1)]));
    }
    const { python, mismatches } = runAgreeing(requests);
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    const crashed = python.filter((result) => !result.ok);
    expect(python.length - crashed.length, "不是一路崩到底").toBeGreaterThan(400);
    expect(new Set(crashed.map((result) => result["error"])).size, "崩溃的种类").toBeGreaterThan(3);
  });
});

describe("第 ⑤f 片：建 worktree、打候选补丁、接上一轮的白盒测试（真 git）", () => {
  const PATCH = lines("diff --git a/src/doc.py b/src/doc.py", "--- a/src/doc.py", "+++ b/src/doc.py", "@@ -1,2 +1,2 @@", " def title():", "-    return 'old'", "+    return 'new'");
  /** worktree_root 与 mkdtemp 的手写记录：根目录给定，mkdtemp 交回 prefix 加固定的 8 个字符。 */
  function made(sc: Scene, kind: string): { root: string; path: string; inner: unknown[] } {
    const root = tempDir("post-root");
    const prefix = `${basename(sc.repo).slice(0, 16)}-hub-t001-${kind}-`;
    const path = join(root, `${prefix}fixed123`);
    const none = { write: {}, delete: [] };
    return { root, path, inner: [{ fn: "worktree_root", repo: sc.repo, value: toTagged(root), files: none }, { fn: "mkdtemp", prefix, dir: root, value: toTagged(path), files: none }] };
  }

  it("ensure_worktree：记下的还在、提交相同就复用；不在或提交不同就新建（事件、ts 记下）", () => {
    const sc = scene(BASE_FILES);
    const fresh = made(sc, "post-attempt-001");
    const other = made(sc, "post-attempt-001");
    const workspaces = (record: Record<string, unknown>): PyDict => postTs(sc, { workspaces: { "post-attempt-001": record } });
    const results = agreeFlow([
      flow("ensure_worktree", sc, [workspaces({ path: sc.wt, commit: sc.head }), "post-attempt-001", sc.head]),
      flow("ensure_worktree", sc, [postTs(sc, { workspaces: {} }), "post-attempt-001", sc.head], { inner: fresh.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [fresh.path] }),
      flow("ensure_worktree", sc, [workspaces({ path: sc.wt, commit: "0".repeat(40) }), "post-attempt-001", sc.head],
        { inner: other.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [other.path] }),
    ]);
    expect(results.map((state) => returned(state))).toEqual([sc.wt, fresh.path, other.path]);
    const record = (tsAfter(results[1]).get("workspaces") as PyDict).get("post-attempt-001") as PyDict;
    expect([...record.keys()]).toEqual(["path", "commit", "created_at"]);
    expect(Object.keys(written(results[1]))).toContain("2/src/doc.py");
  });

  it("apply_candidate：照 meta.json 的基线建 worktree、打补丁、记基线状态；已经打过就不再打；meta.json 坏了用基准测试的提交", () => {
    const sc = scene(BASE_FILES, (repo) => {
      put(repo, ".agent/runs/t1/attempt-001/candidate.patch", PATCH);
      put(repo, ".agent/runs/t1/attempt-001/meta.json", "{");
    });
    const good = scene(BASE_FILES, (repo, _wt, head) => {
      put(repo, ".agent/runs/t1/attempt-001/candidate.patch", PATCH);
      put(repo, ".agent/runs/t1/attempt-001/meta.json", JSON.stringify({ base_sha: head }));
    });
    const first = made(good, "post-attempt-001");
    const broken = made(sc, "post-attempt-001");
    const results = agreeFlow([
      flow("apply_candidate", good, [postTs(good, { workspaces: {} })], { inner: first.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [first.path] }),
      flow("apply_candidate", good, [postTs(good, { workspaces: { "post-attempt-001": { path: good.wt, commit: good.head, patched: true } } })]),
      flow("apply_candidate", sc, [postTs(sc, { workspaces: {} })], { inner: broken.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [broken.path] }),
    ]);
    expect(text(results[0], "2/src/doc.py")).toBe(lines("def title():", "    return 'new'"));
    const record = (tsAfter(results[0]).get("workspaces") as PyDict).get("post-attempt-001") as PyDict;
    expect(record.get("baseline_status")).toEqual([[" M", "src/doc.py"]]);
    expect(returned(results[1])).toBe(good.wt);
    expect(((tsAfter(results[2]).get("workspaces") as PyDict).get("post-attempt-001") as PyDict).get("commit")).toBe(sc.head);
  });

  it("seed_whitebox：放最新的一份（Windows 上 glob 与排序都不分大小写）；目标已在、已经放过、没有存档都不放", () => {
    const evidence = ".agent/mailbox/tasks/T001-6-gate-post/evidence";
    const sc = scene(BASE_FILES, (repo) => {
      put(repo, `${evidence}/whitebox-20260101T000000000000Z.py`, "A");
      put(repo, `${evidence}/WHITEBOX-20260102T000000000000Z.PY`, "B");
      put(repo, `${evidence}/whitebox-20260103T000000000000Z.txt`, "C");
    });
    const placed = scene(BASE_FILES, (_repo, wt) => put(wt, WHITEBOX, "mine"));
    const bare = scene(BASE_FILES);
    const record = (sc_: Scene, extra: Record<string, unknown> = {}): PyDict => postTs(sc_, { workspaces: { "post-attempt-001": { path: sc_.wt, ...extra } } });
    const results = agreeFlow([
      flow("seed_whitebox", sc, [record(sc), sc.wt]), flow("seed_whitebox", placed, [record(placed), placed.wt]),
      flow("seed_whitebox", sc, [record(sc, { whitebox_seeded: "x" }), sc.wt]), flow("seed_whitebox", bare, [record(bare), bare.wt]),
    ]);
    const isWindows = process.platform === "win32";
    expect(returned(results[0])).toBe(isWindows ? `${evidence}/WHITEBOX-20260102T000000000000Z.PY` : `${evidence}/whitebox-20260101T000000000000Z.py`);
    expect(text(results[0], `1/${WHITEBOX}`)).toBe(isWindows ? "B" : "A");
    expect(results.slice(1).map((state) => returned(state))).toEqual([null, null, null]);
  });

  it("add_worktree：git worktree add 一直失败，三边都重试三次（等 1 秒、2 秒）、报同一条 HubError；只在这一次调用期间开 GIT_TRACE，数到 worktree add 正好 3 次", () => {
    const sc = scene(BASE_FILES);
    const fresh = made(sc, "post-attempt-001");
    const traces = tempDir("git-trace");
    const outcomes = IMPLS.map((impl) => {
      const trace = join(traces, `${impl.name}.log`);
      const request = flow("ensure_worktree", sc, [postTs(sc, { workspaces: {} }), "post-attempt-001", "f".repeat(40)],
        { inner: fresh.inner, replaced: ["worktree_root", "mkdtemp"], fresh: [fresh.path], env: { GIT_TRACE: trace } });
      const started = Date.now();
      const result = runProbe(impl, request, 120_000);
      const seconds = (Date.now() - started) / 1000;
      const adds = existsSync(trace) ? readFileSync(trace, "utf8").split(LF).filter((line) => / git worktree add /.test(line)).length : 0;
      return { impl: impl.name, value: result["value"] as Record<string, unknown>, seconds, adds };
    });
    for (const outcome of outcomes.slice(1)) expect(outcome.value, outcome.impl).toEqual(outcomes[0]?.value);
    expect(outcomes.map((outcome) => [outcome.adds, outcome.seconds >= 2.9])).toEqual(IMPLS.map(() => [3, true]));
    const result = outcomes[0]?.value["result"] as Record<string, unknown>;
    expect([result["error"], String(result["message"]).startsWith(`git worktree add --detach ${fresh.path} ${"f".repeat(40)} 失败：fatal: invalid reference`)])
      .toEqual(["HubError", true]);
  }, 120_000);
});

describe("第 ⑤f 片：真跑（不注入）", () => {
  /** 真跑白盒 pytest 时钉不住的（⑤f 设计稿第 11.2 节）：whitebox_seconds 换成 <SECONDS>，日志、whitebox_tail 与问题里的用时照 DURATION 换。 */
  function whiteboxRun(state: Record<string, unknown>): unknown {
    const ts = fromTagged(state["ts"] as Tagged) as PyDict;
    const gate = ts.get("gate_post") as PyDict;
    if (gate.has("whitebox_seconds")) gate.set("whitebox_seconds", "<SECONDS>");
    if (typeof gate.get("whitebox_tail") === "string") gate.set("whitebox_tail", (gate.get("whitebox_tail") as string).replace(DURATION, " in <DURATION>"));
    const files = state["files"] as { write: Record<string, string>; delete: string[] };
    const write = Object.fromEntries(Object.entries(files.write).map(([key, data]) => [key,
      key.endsWith(".log") ? b64(Buffer.from(data, "base64").toString("utf8").replace(DURATION, " in <DURATION>")) : data]));
    return { ...state, ts: toTagged(ts), files: { ...files, write } };
  }

  it("白盒 pytest 真跑：通过（清单写明时限，变异照注入）与不通过；用时打占位；worktree 里不留缓存", () => {
    const pass = scene(BASE_FILES, (_repo, wt) => put(wt, WHITEBOX, GOOD_TEST));
    const fail = scene(BASE_FILES, (_repo, wt) => put(wt, WHITEBOX, BAD_TEST));
    const env = { PYTHONDONTWRITEBYTECODE: "0" }; // kernel_pytest_env 不显式设 1 时 pytest 真会写 __pycache__
    const results = agreeFlow([
      flow("accept_gate_post", pass, [postTs(pass), pass.wt, { mutation_spec: { ...SPEC2, timeout_seconds: 300 } }],
        { inner: [anchors(pass, 0, ANCHORS_OK), mutateCall(pass, 3600, RECORD_OK)], env }),
      flow("accept_gate_post", fail, [postTs(fail), fail.wt, {}], { replaced: ["run_pd"], env }),
    ], whiteboxRun);
    expect(returned(results[0])).toEqual([]);
    expect(String((returned(results[1]) as string[])[0])).toContain("1 failed in");
    for (const state of results) expect(Object.keys(written(state)).filter((key) => key.startsWith("1/") && /__pycache__|[.]pytest_cache/.test(key))).toEqual([]);
    expect((tsAfter(results[0]).get("gate_post") as PyDict).get("mutant_timeout")).toBe(300n);
  }, 300_000);

  it("mutate 真跑（白盒照注入）：调度器的证据里起止时刻、pid、用时与日志打占位", () => {
    const sc = scene(BASE_FILES, (repo, wt) => {
      put(wt, WHITEBOX, GOOD_TEST);
      put(repo, ".agent/runs/t1/attempt-001/scope.json", JSON.stringify({ files: [{ path: "src/doc.py", status: "M" }] }));
    });
    const spec = { commands: [{ id: "W1", argv: [kernelPython(), "-m", "pytest", "-q", "-p", "no:cacheprovider", WHITEBOX] }],
      mutations: [{ name: "改标题", file: "src/doc.py", old: "'old'", new: "'new'" }], timeout_seconds: 120 };
    const stamp = (record: Record<string, unknown>, keys: string[]): void => {
      for (const key of keys) if (key in record) record[key] = "<X>";
    };
    const evidence = (state: Record<string, unknown>): unknown => {
      const files = state["files"] as { write: Record<string, string>; delete: string[] };
      const write = Object.fromEntries(Object.entries(files.write).map(([key, data]) => {
        if (!key.startsWith(`${STAGE_KEY}/evidence/mutate-`)) return [key, data];
        if (key.endsWith(".log")) return [key, "<LOG>"];
        if (!key.endsWith("/mutations.json")) return [key, data];
        const record = JSON.parse(Buffer.from(data, "base64").toString("utf8")) as Record<string, unknown>;
        stamp(record, ["started_at", "ended_at"]);
        const baseline = record["baseline"];
        for (const item of (Array.isArray(baseline) ? baseline : [baseline]) as Record<string, unknown>[]) {
          if (item) stamp(item, ["started_at", "ended_at", "pid", "wall_seconds", "log_sha256", "log_bytes"]);
        }
        return [key, JSON.stringify(record)];
      }));
      return { ...state, files: { ...files, write } };
    };
    const [state] = agreeFlow([
      flow("accept_gate_post", sc, [postTs(sc), sc.wt, { mutation_spec: spec }],
        { inner: [supervised(sc, PASS_LOG, { exit_code: 0 })], replaced: ["run_supervised"], env: { PYTHONDONTWRITEBYTECODE: "1" } }),
    ], evidence);
    expect(returned(state)).toEqual([]);
    expect(((tsAfter(state).get("gate_post") as PyDict).get("mutation_counts") as PyDict).get("caught")).toBe(1n);
  }, 300_000);
});

