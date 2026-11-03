// 第 ⑤h1 片的手写对照（采样那份在 hub-land.contract.test.ts）：临时仓库上搭好场景，三边各自先原地放回再跑，交回值、ts、文件、账本、
// git 状态逐字比（提交作者与时刻钉住，挑上分支的提交 SHA 照样比）。样本没走到的分支、短路条件的两边、themistally-15 列的怪类型在这里：
//   - landing_blockers：标记的各种写法（没有 pid、pid 在、不在、不知道；有 label、只有 task、两样都没有；sweep 标记在 sweeps 真假时；
//     坏 JSON、目录、大写扩展名），调度器记着在跑的 attempt（自己合同的滤掉，正反斜杠都认）；注入的 _running_attempts 报 DispatchError、
//     OSError 时当成空，别的照样崩；pid_alive 交回真、假、None；照样崩的几种；
//   - finalize：verdict 被拒；基准测试挑不上时不再落返工链；integrate 没过时撤回并列出期间先落地的提交；过了之后提交记录，分支在任务
//     期间前进与没前进；
//   - undo_landing：四种结局，记录是怪类型；
//   - commit_records：Windows 上不分大小写、后缀分大小写、前缀相同的别的合同族不算；没东西可提交；add 报错；照样崩的两种；
//   - retire_attempts、remove_workspaces、tidy_finished：各种状态的 attempt、cleanup 失败、worktree remove 失败，照样崩的几种；
//   - land_oracle、land_rework_chain、landing_chain、on_branch、landed_meanwhile：内容相同就不挑、部分相同照挑、files 为空、挑不上、
//     已在分支上（祖先或 cherry-pick -x 的标记）、空提交、提交不存在、run_dir 为空、where 是别的 worktree。
// 不写转义序列。
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, runBatch } from "./harness.ts";
import { AT, C, LF, type Scene, agreeFlow, flow, pd, py, returned, scene, tsAfter } from "./flow-fixtures.ts";
import { git, put, removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const BS = C(92);
const lines = (...items: string[]): string => [...items, ""].join(LF);
const GATE = "tests/test_gate_t001_baseline.py";
const GATE2 = "tests/test_gate_t001_more_baseline.py";
const BASE_FILES = { "src/doc.py": lines("def title():", "    return 'old'") };
const MARKS = ".agent/mailbox/ledger/exec-active";
const RUNS = ".agent/runs/t001-doc";
const NOTHING = { write: {}, delete: [] };
/** 注入的多行输出（各处 tail 的行数都要起作用）：“前缀 1”到“前缀 n”。 */
const many = (prefix: string, count: number): string => Array.from({ length: count }, (_, at) => `${prefix} ${at + 1}`).join(LF);
/** many 的最后 count 行。 */
const lastOf = (prefix: string, total: number, count: number): string => Array.from({ length: count }, (_, at) => `${prefix} ${total - count + at + 1}`).join(LF);

const errorOf = (state: Record<string, unknown> | undefined): unknown => (state?.["result"] as Record<string, unknown>)["error"] ?? null;
/** 注入核对过了（手写的记录与两边的调用对得上）：两边都报 INJECTION_* 时比较也会相同，这里另外拦住。 */
function injectedCleanly(states: readonly Record<string, unknown>[]): void {
  expect(states.map(errorOf).filter((error) => String(error).startsWith("INJECTION_")), "注入的记录与调用对不上").toEqual([]);
}
/** 照样崩的：交回的异常类型与文字（三边比过了，这里钉 Python 的）。 */
const crashOf = (state: Record<string, unknown> | undefined): [unknown, unknown] => {
  const result = state?.["result"] as Record<string, unknown>;
  return [result["error"] ?? null, result["message"] ?? null];
};

/** 在 parent 上提交 files（null 是删掉），交回新提交；HEAD 留在分离的状态，场景最后再切回去。 */
function commitOn(repo: string, parent: string, files: Record<string, string | null>, message: string): string {
  git(repo, "checkout", "-q", "--detach", parent);
  for (const [rel, content] of Object.entries(files)) {
    if (content === null) git(repo, "rm", "-q", rel);
    else put(repo, rel, content);
  }
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "--allow-empty", "-m", message);
  return git(repo, "rev-parse", "HEAD");
}
/** 主分支挪到 sha（工作区跟着）。 */
const branchTo = (repo: string, sha: string): void => {
  git(repo, "checkout", "-q", "master");
  git(repo, "reset", "-q", "--hard", sha);
};

function landTs(sc: Scene, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  ts.set("contract", py({ version: 1, key: "t001-doc.v1", md: ".agent/plans/t001-doc.v1.md", json: ".agent/plans/t001-doc.v1.json" }));
  for (const [key, value] of Object.entries(extra)) ts.set(key, value instanceof Map ? (value as PyDict) : py(value));
  return ts;
}
const runDirOf = (sc: Scene, number = "001"): string => join(sc.repo, ".agent", "runs", "t001-doc", `attempt-${number}`);
/** 注入的 _running_attempts：比仓库根；交回列表或抛出。 */
const running = (sc: Scene, value: string[] | null, raise: [string, string] | null = null): unknown => ({
  fn: "_running_attempts", repo: join(sc.repo), ...(raise === null ? { value: toTagged(value as PyValue) } : { raise }), files: NOTHING,
});
const alive = (pid: number, value: boolean | null): unknown => ({ fn: "pid_alive", pid, value: toTagged(value), files: NOTHING });

/** 不经 hub.contract_flow 的几个（只读仓库）：先放回场景，三边各跑一次逐个比，交回 Python 的结果。 */
function agreeCalls(requests: readonly ProbeRequest[]): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  for (const [index, other] of others.entries()) {
    expect(JSON.stringify(other), `${IMPLS[index + 1]?.name} 与 Python 不同`).toBe(JSON.stringify(python));
  }
  return python as ProbeResult[];
}
const call = (fn: string, sc: Scene, args: unknown[]): ProbeRequest => ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))), restores: sc.restores });
const valueOf = (result: ProbeResult | undefined): PyValue => (result?.["ok"] ? fromTagged(result["value"] as Tagged) : (result?.["error"] as string));

describe("第 ⑤h1 片：landing_blockers（手写）", () => {
  const me = process.pid;
  const marked = (): Scene => scene(BASE_FILES, (repo) => {
    const mark = (name: string, body: string): void => put(repo, `${MARKS}/${name}`, body);
    mark("T001.json", JSON.stringify({ pid: me, task: "T001" })); // 自己的：跳过
    mark("T002.json", JSON.stringify({ pid: me, task: "T002", label: "T002 正在执行（标签）" })); // 进程在：挡着，用 label
    mark("T003.json", JSON.stringify({ pid: 999999999, task: "T003" })); // 进程不在：标记作废
    mark("T004.json", JSON.stringify({ task: "T004" })); // 没有 pid：照样挡着
    mark("T005.json", JSON.stringify({ pid: "0", task: "T005", label: "" })); // int("0") 是 0，pid_alive 交回 None：照样挡着
    mark("T006.json", JSON.stringify({ pid: 999999999.5, task: "T006" })); // 截成整数，不在
    mark("T007.json", JSON.stringify({ pid: true, task: "T007" })); // int(True) 是 1
    mark("orphan.json", "{}"); // 两样都没有：用文件名
    mark("_under.json", JSON.stringify({ task: "T010" })); // 排序照小写之后的码点：_ 在 a 之前；NTFS 列目录照大写，_ 在 A 之后
    mark("a-first.json", JSON.stringify({ task: "T011" }));
    mark("broken.json", "{不是 JSON"); // 读不出：当成 {}
    put(repo, `${MARKS}/latin.json`, new Uint8Array([0xff, 0xfe, 0x7b])); // 不是 UTF-8：UnicodeDecodeError 也是 ValueError
    mark("owner-sweep.json", JSON.stringify({ pid: me, task: "owner-sweep", label: "站主提交之后的门禁回归", sweep: true }));
    mark("yes.json", JSON.stringify({ sweep: "yes", label: 7 })); // sweep 按真值；label 不是字符串照原样交回
    mark("Upper.JSON", JSON.stringify({ task: null, label: null })); // Windows 上 glob 不分大小写
    mark("note.txt", "不是 .json");
    mkdirSync(join(repo, ...MARKS.split("/"), "dir.json"), { recursive: true }); // 目录：read_text 交回空串
    put(repo, `${RUNS}/attempt-001/state.json`, JSON.stringify({ state: "RUNNING" })); // 自己合同的：滤掉
    put(repo, ".agent/runs/t002-x/attempt-001/state.json", JSON.stringify({ state: "COLLECTING" }));
    put(repo, ".agent/runs/t002-x/attempt-002/state.json", JSON.stringify({ state: "PASS" }));
  }, false);

  it("标记的各种写法与调度器记着在跑的 attempt：sweeps 为真、为假、为别的真值与假值；pid 照真的 pid_alive 判断", () => {
    const sc = marked();
    const ts = landTs(sc);
    const states = agreeFlow([true, false, "yes", 0].map((sweeps) => flow("landing_blockers", sc, [ts, sweeps])));
    const t2 = "attempt t002-x/attempt-001"; // display_path 用正斜杠
    const common = ["T010 的执行端", "T011 的执行端", "broken 的执行端", "dir 的执行端", "latin 的执行端", "orphan 的执行端"];
    const tail = ["T002 正在执行（标签）", "T004 的执行端", "T005 的执行端", "Upper 的执行端"];
    expect(states.map(returned)).toEqual([
      [...common, "站主提交之后的门禁回归", ...tail, 7n, t2], [...common, ...tail, t2], [...common, "站主提交之后的门禁回归", ...tail, 7n, t2], [...common, ...tail, t2],
    ]);
  }, 600_000);

  it("注入的调度器与 pid_alive：自己合同的 attempt 滤掉（正反斜杠都认，前缀相同的别的合同不算）；DispatchError、OSError 当成空，别的照样崩", () => {
    const sc = scene(BASE_FILES, (repo) => {
      put(repo, `${MARKS}/A.json`, JSON.stringify({ pid: 12345, task: "T002" }));
      put(repo, `${MARKS}/B.json`, JSON.stringify({ pid: 23456, task: "T003" }));
      put(repo, `${MARKS}/C.json`, JSON.stringify({ pid: 34567, task: "T004" }));
    }, false);
    const ts = landTs(sc);
    const pids = [alive(12345, true), alive(23456, null), alive(34567, false)];
    const given = (inner: unknown[]): ProbeRequest => flow("landing_blockers", sc, [ts, true], { inner: [...pids, ...inner], replaced: ["_running_attempts", "pid_alive"] });
    const listed = ["t001-doc/attempt-002", `t001-doc${BS}attempt-003`, `t002-y${BS}attempt-001`, "t001-docx/attempt-001"];
    const states = agreeFlow([
      given([running(sc, listed)]), given([running(sc, null, ["DispatchError", "调度器说不清"])]), given([running(sc, null, ["OSError", "读不了 runs"])]),
      given([running(sc, null, ["ValueError", "别的错"])]),
    ]);
    injectedCleanly(states);
    const marks = ["T002 的执行端", "T003 的执行端"];
    expect(states.map(returned)).toEqual([[...marks, `attempt t002-y${BS}attempt-001`, "attempt t001-docx/attempt-001"], marks, marks, "ValueError"]);
  }, 600_000);

  it("照样崩的：pid 不是数、标记不是字典、合同族名不是字符串、ts 没有 task", () => {
    const one = (body: string): Scene => scene(BASE_FILES, (repo) => put(repo, `${MARKS}/X.json`, body), false);
    const [abc, list, plain] = [one(JSON.stringify({ pid: "abc", task: "T009" })), one("[1, 2]"), scene(BASE_FILES, () => undefined, false)];
    const noTask = landTs(abc);
    noTask.delete("task");
    const states = agreeFlow([
      flow("landing_blockers", abc, [landTs(abc), true]), flow("landing_blockers", list, [landTs(list), true]),
      flow("landing_blockers", plain, [landTs(plain, { contract_task: 5 }), true]), flow("landing_blockers", abc, [noTask, true]),
    ]);
    expect(states.map(crashOf)).toEqual([
      ["ValueError", "invalid literal for int() with base 10: 'abc'"], ["AttributeError", "'list' object has no attribute 'get'"],
      ["TypeError", "unsupported operand type(s) for +: 'int' and 'str'"], ["KeyError", "'task'"],
    ]);
  }, 600_000);
});

describe("第 ⑤h1 片：finalize 与 undo_landing（手写）", () => {
  /** B0（场景的 head）上分出基准测试 O；主分支在 B0 上前进了一个“并行主任务”的提交 M；attempt 的状态与 run_dir。 */
  interface Landing { readonly sc: Scene; readonly oracle: string; readonly meanwhile: string }
  const landing = (state: string, advance: "none" | "meanwhile" | "conflict", plans = false, more: (repo: string, head: string) => void = () => undefined): Landing => {
    let oracle = "";
    let meanwhile = "";
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      oracle = commitOn(repo, head, { [GATE]: lines("def test_title():", "    assert False") }, "门禁基准测试");
      more(repo, head);
      meanwhile = advance === "none" ? head
        : commitOn(repo, head, advance === "conflict" ? { [GATE]: lines("# 站主先放了一份") } : { "src/other.py": lines("x = 1") }, "并行主任务先落地");
      branchTo(repo, meanwhile);
      put(repo, `${RUNS}/attempt-001/state.json`, JSON.stringify({ state }));
      if (plans) put(repo, ".agent/plans/t001-doc.v1.md", lines("# TASK: t001-doc"));
    }, false);
    return { sc, oracle, meanwhile };
  };
  const ts = (item: Landing, extra: Record<string, unknown> = {}): PyDict => landTs(item.sc, {
    oracle: { sha: item.oracle, files: [GATE] }, exec: { run_dir: runDirOf(item.sc), check_ok: true }, ...extra,
  });
  const integrate = (item: Landing, code: number, out: string): unknown => pd(["integrate", runDirOf(item.sc)], code, out, 3600);

  it("verdict 被拒：复审记录照写，交回问题；基准测试挑不上：不再落返工链，分支不动", () => {
    const rejected = landing("NEEDS_REVIEW", "none");
    const review = join(rejected.sc.repo, ".agent", "reviews", "t001-doc", "attempt-001-hub.md");
    let side = "";
    const conflict = landing("PASS", "conflict", false, (repo, head) => {
      side = commitOn(repo, head, { "src/rework.py": lines("r = 1") }, "返工的一轮");
      put(repo, `${RUNS}/attempt-001/meta.json`, JSON.stringify({ base_sha: side }));
    });
    const link = { from: "attempt-001", commit: side, contract: "t001-doc.v1", at: AT, why: "audit", rebuilt: false };
    const states = agreeFlow([
      flow("finalize", rejected.sc, [ts(rejected)], { inner: [pd(["verdict", runDirOf(rejected.sc), "--verdict", "PASS", "--review", review], 2, many("verdict 被拒", 22))] }),
      flow("finalize", conflict.sc, [ts(conflict, { rework_chain: [link] })], { inner: [] }),
    ]);
    injectedCleanly(states);
    expect(returned(states[0])).toEqual([false, `verdict PASS 被门禁拒绝：${LF}${lastOf("verdict 被拒", 22, 20)}`]);
    const [ok, problem] = returned(states[1]) as [boolean, string];
    expect([ok, problem.startsWith(`基准测试提交 ${conflict.oracle.slice(0, 12)} 既不能 ff，也不能干净地挑到当前分支：`)]).toEqual([false, true]);
    expect(((tsAfter(states[1]).get("rework_chain") as PyValue[])[0] as PyDict).has("landed_at"), "返工链没有落").toBe(false);
  }, 600_000);

  it("integrate 没过：列出期间先落地的提交，撤回挑上去的基准测试、记录恢复原样；过了：提交合同、分支前进时记回归待跑，没前进时不记", () => {
    const failed = landing("PASS", "meanwhile");
    const passed = landing("PASS", "meanwhile", true);
    const still = landing("PASS", "none");
    const states = agreeFlow([
      flow("finalize", failed.sc, [ts(failed)], { inner: [integrate(failed, 1, many("CHECK 没过", 17))] }),
      flow("finalize", passed.sc, [ts(passed)], { inner: [integrate(passed, 0, many("integrated", 8))] }),
      flow("finalize", still.sc, [ts(still)], { inner: [integrate(still, 0, many("integrated", 8))] }),
    ]);
    injectedCleanly(states);
    const [ok, problem] = returned(states[0]) as [boolean, string];
    expect([ok, problem.includes("并行主任务先落地"), problem.includes("已把这次带上分支的基准测试与返工提交撤回")]).toEqual([false, true, true]);
    expect((tsAfter(states[0]).get("oracle") as PyDict).has("landed_at"), "记录恢复原样").toBe(false);
    expect(tsAfter(states[1]).get("regression"), "分支前进了").toEqual(py({ pending: true, head_before: passed.meanwhile }));
    expect(String((returned(states[1]) as PyValue[])[1])).toContain("合同与复审记录已提交");
    expect([tsAfter(states[2]).has("regression"), String((returned(states[2]) as PyValue[])[1]).includes("合同与复审记录没有新改动")]).toEqual([false, true]);
  }, 600_000);

  it("undo_landing 的四种结局：末端没动、已经不是祖先、reset --keep 被本地改动挡住、撤回并恢复记录；记录是列表时撤回之后照样崩", () => {
    let side = "";
    let landed = "";
    const make = (dirty: boolean): Scene => scene(BASE_FILES, (repo, _wt, head) => {
      side = commitOn(repo, head, { "src/side.py": lines("y = 2") }, "别处的提交");
      landed = commitOn(repo, head, { "src/doc.py": lines("def title():", "    return 'landed'") }, "挑上来的基准测试");
      branchTo(repo, landed);
      // 放回快照会换掉 ctime 与 inode，索引里记的 stat 对不上，reset --keep 会当成文件改过：照 mtime 与大小判断（放回时 mtime 照原样）
      git(repo, "config", "core.checkStat", "minimal");
      git(repo, "config", "core.trustctime", "false");
      if (dirty) put(repo, "src/doc.py", lines("def title():", "    return '站主手上的改动'"));
    }, false);
    const clean = make(false);
    const [cleanSide, cleanLanded, base] = [side, landed, clean.head];
    const dirty = make(true);
    const before = [py({ sha: "o" }), py({ commit: "r" })];
    const records = (sc: Scene): PyDict => landTs(sc, { oracle: { sha: "o", landed_at: AT }, rework_chain: [{ commit: "r", landed_at: AT }] });
    const states = agreeFlow([
      flow("undo_landing", clean, [records(clean), cleanLanded, before]), flow("undo_landing", clean, [records(clean), cleanSide, before]),
      flow("undo_landing", dirty, [records(dirty), dirty.head, before]), flow("undo_landing", clean, [records(clean), base, before]),
      flow("undo_landing", clean, [landTs(clean, { oracle: [["sha", "o"]] }), base, [py({ sha: "o" })]]),
    ]);
    expect(returned(states[0])).toBe("");
    expect(returned(states[1])).toBe(`${LF}分支已经不在结项开始时的末端 ${cleanSide.slice(0, 12)} 之上，这次带上分支的提交没有撤回（站主处理）`);
    expect(String(returned(states[2]))).toContain(`${LF}这次带上分支的提交没能撤回（站主处理）：git reset -q --keep ${dirty.head} 失败：`);
    expect(returned(states[3])).toBe(`${LF}已把这次带上分支的基准测试与返工提交撤回（${cleanLanded.slice(0, 12)} → ${base.slice(0, 12)}）：分支上不留半截的结项`);
    expect(tsAfter(states[3]).get("oracle")).toEqual(py({ sha: "o" }));
    expect(crashOf(states[4])).toEqual(["AttributeError", "'list' object has no attribute 'update'"]);
  }, 600_000);
});

describe("第 ⑤h1 片：commit_records（手写）", () => {
  const records = (prepare: (repo: string) => void): Scene => scene(BASE_FILES, (repo) => prepare(repo), false);

  it("Windows 上不分大小写、后缀分大小写、前缀相同的别的合同族不算，复审记录目录一起提交；没东西可提交、什么都没有时交回两个 None", () => {
    const odd = records((repo) => {
      for (const name of ["t001-doc.v1.md", "t001-doc.v1.json", "T001-DOC.v2.md", "t001-doc.v3.MD", "t001-doc.v4.txt", "t001-docx.v1.md", "t002-doc.v1.md"]) {
        put(repo, `.agent/plans/${name}`, lines(`# ${name}`));
      }
      put(repo, ".agent/reviews/t001-doc/attempt-001-hub.md", lines("Verdict: PASS"));
      put(repo, "src/staged.py", lines("s = 1")); // 站主暂存了别的文件：--only 不带上它
      git(repo, "add", "src/staged.py");
    });
    const committed = records((repo) => {
      put(repo, ".agent/plans/t001-doc.v1.md", lines("# 已提交"));
      git(repo, "add", "-A");
      git(repo, "commit", "-q", "-m", "合同");
    });
    const empty = records(() => undefined);
    const staged = records((repo) => { // 没有记录、站主暂存了别的文件：照样交回两个 None，不走到 git commit --only --
      put(repo, "src/staged.py", lines("s = 1"));
      git(repo, "add", "src/staged.py");
    });
    const states = agreeFlow([
      flow("commit_records", odd, [landTs(odd)]), flow("commit_records", committed, [landTs(committed)]),
      flow("commit_records", empty, [landTs(empty)]), flow("commit_records", staged, [landTs(staged)]),
    ]);
    const [sha, problem] = returned(states[0]) as [string, PyValue];
    expect([typeof sha, problem]).toEqual(["string", null]);
    expect(returned(states[1])).toEqual([null, null]);
    expect(returned(states[2])).toEqual([null, null]);
    expect(returned(states[3])).toEqual([null, null]);
  }, 600_000);

  it("add 报错交回问题；合同族名不是字符串、ts 没有 title 照样崩（后者 add 已经做了）", () => {
    const ignored = records((repo) => {
      put(repo, ".gitignore", lines(".agent/runs/", ".agent/plans/t001-doc.v9.md"));
      git(repo, "add", "-A");
      git(repo, "commit", "-q", "-m", "忽略一份合同");
      put(repo, ".agent/plans/t001-doc.v1.md", lines("# v1"));
      put(repo, ".agent/plans/t001-doc.v9.md", lines("# v9"));
    });
    const plain = records((repo) => put(repo, ".agent/plans/t001-doc.v1.md", lines("# v1")));
    const noTitle = landTs(plain);
    noTitle.delete("title");
    const states = agreeFlow([
      flow("commit_records", ignored, [landTs(ignored)]), flow("commit_records", plain, [landTs(plain, { contract_task: 5 })]), flow("commit_records", plain, [noTitle]),
    ]);
    const [sha, problem] = returned(states[0]) as [PyValue, string];
    expect([sha, problem.startsWith("合同与复审记录没有提交成（站主手动提交）：git add -- ")]).toEqual([null, true]);
    expect(crashOf(states[1])).toEqual(["TypeError", "unsupported operand type(s) for /: 'WindowsPath' and 'int'"]);
    expect(crashOf(states[2])).toEqual(["KeyError", "'title'"]);
  }, 600_000);
});

describe("第 ⑤h1 片：retire_attempts、remove_workspaces、tidy_finished（手写）", () => {
  const REASON = "T001 已结项：这一轮没有复审结论";
  const attempt = (repo: string, number: string, state: string | null, meta: unknown, started = false): void => {
    const dir = `${RUNS}/attempt-${number}`;
    if (state !== null) put(repo, `${dir}/state.json`, JSON.stringify({ state }));
    if (meta !== undefined) put(repo, `${dir}/meta.json`, typeof meta === "string" ? meta : JSON.stringify(meta));
    if (started) put(repo, `${dir}/run-started.json`, "{}");
    mkdirSync(join(repo, ...dir.split("/")), { recursive: true });
  };

  it("retire_attempts：没开跑且 worktree 干净（记 ABANDONED、cleanup --force）、没开跑但不干净（不带 --force）、PREPARED 已开跑与 RUNNING 不动、mark 失败、有结论的只清 worktree 且 cleanup 失败、没有 worktree、目录名大写", () => {
    const dirtyWt = join(tempDir("land-wt-dirty"), "wt");
    const sc = scene(BASE_FILES, (repo, wt) => {
      attempt(repo, "001", "PREPARED", { worktree: wt });
      attempt(repo, "002", "PREPARED", { worktree: wt }, true);
      attempt(repo, "003", "NEEDS_REVIEW", { worktree: join(repo, "src") }); // mark 失败：worktree 照旧不清
      attempt(repo, "004", "PASS", { worktree: join(repo, "src") });
      attempt(repo, "005", "RUNNING", {});
      attempt(repo, "006", "NEEDS_REVIEW", {});
      put(repo, ".agent/runs/t001-doc/ATTEMPT-007/meta.json", JSON.stringify({ worktree: join(repo, "gone") }));
      git(repo, "worktree", "add", "-q", "--detach", dirtyWt, git(repo, "rev-parse", "HEAD"));
      put(dirtyWt, "src/dirty.py", "x");
      attempt(repo, "008", "PREPARED", { worktree: dirtyWt }); // 没开跑但 worktree 不干净：cleanup 不带 --force
    });
    const run = (number: string): string => runDirOf(sc, number);
    const states = agreeFlow([flow("retire_attempts", sc, [landTs(sc), REASON], {
      inner: [
        pd(["mark", run("001"), "ABANDONED", "--reason", REASON], 0, "ok"), pd(["cleanup", run("001"), "--force"], 0, "ok"),
        pd(["mark", run("003"), "ABANDONED", "--reason", REASON], 1, many("标记不了", 5)), pd(["cleanup", run("004")], 1, many("会丢改动", 5)),
        pd(["mark", run("006"), "ABANDONED", "--reason", REASON], 0, "ok"),
        pd(["mark", run("008"), "ABANDONED", "--reason", REASON], 0, "ok"), pd(["cleanup", run("008")], 0, "ok"),
      ],
    })]);
    injectedCleanly(states);
    expect(returned(states[0])).toEqual([
      "attempt-002 还处在 PREPARED，没有动", `attempt-003 没能记成 ABANDONED：${lastOf("标记不了", 5, 3)}`, `attempt-004 的 worktree 没删掉：${lastOf("会丢改动", 5, 3)}`,
      "attempt-005 还处在 RUNNING，没有动",
    ]);
  }, 600_000);

  it("retire_attempts 照样崩的：meta.json 不是字典、不是 JSON，worktree 不是字符串，没开跑的 worktree 不是 git 目录", () => {
    const outside = tempDir("land-not-git");
    const one = (state: string, meta: unknown): Scene => scene(BASE_FILES, (repo) => attempt(repo, "001", state, meta), false);
    const cases = [one("PASS", [1]), one("PASS", "{坏"), one("PASS", { worktree: 5 }), one("PREPARED", { worktree: outside })];
    const states = agreeFlow(cases.map((sc, index) => flow("retire_attempts", sc, [landTs(sc), REASON], {
      inner: index === 3 ? [pd(["mark", runDirOf(sc), "ABANDONED", "--reason", REASON], 0, "ok")] : [],
    })));
    injectedCleanly(states);
    expect(states.map((state) => crashOf(state)[0])).toEqual(["AttributeError", "JSONDecodeError", "TypeError", "HubError"]);
  }, 600_000);

  it("remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在、空路径与已删过的跳过、不是 worktree 的目录删不掉（stderr 去空白取前 200 个字）", () => {
    const sc = scene(BASE_FILES, (repo) => attempt(repo, "001", "NEEDS_REVIEW", {}));
    const workspaces = { // 键不按字母序插入：处理照 kind 排序，账本里 workspace.removed 的先后才看得出
      "e-plain": { path: join(sc.repo, "src") }, "d-done": { path: sc.wt, removed_at: AT }, "c-empty": { path: "" }, "b-audit": { path: join(sc.repo, "gone") },
      "a-gate-pre": { path: sc.wt },
    };
    const states = agreeFlow([
      flow("remove_workspaces", sc, [landTs(sc, { workspaces })]),
      flow("tidy_finished", sc, [landTs(sc, { workspaces }), REASON], { inner: [pd(["mark", runDirOf(sc), "ABANDONED", "--reason", REASON], 0, "ok")] }),
    ]);
    injectedCleanly(states);
    for (const state of states) {
      const problems = returned(state) as string[];
      expect([problems.length, problems[0]?.startsWith(`${join(sc.repo, "src")}：`)]).toEqual([1, true]);
      const kinds = tsAfter(state).get("workspaces") as PyDict;
      expect(["a-gate-pre", "b-audit", "e-plain"].map((kind) => (kinds.get(kind) as PyDict).has("removed_at"))).toEqual([true, true, false]);
    }
  }, 600_000);

  it("remove_workspaces 照样崩的：workspaces 不是字典、记录不是字典、路径不是字符串", () => {
    const sc = scene(BASE_FILES, () => undefined, false);
    const states = agreeFlow([[1], { a: "x" }, { a: { path: 5 } }].map((workspaces) => flow("remove_workspaces", sc, [landTs(sc, { workspaces })])));
    expect(states.map(crashOf)).toEqual([
      ["AttributeError", "'list' object has no attribute 'items'"], ["AttributeError", "'str' object has no attribute 'get'"],
      ["TypeError", "argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'int'"],
    ]);
  }, 600_000);
});

describe("第 ⑤h1 片：land_oracle、land_rework_chain、landing_chain、on_branch、landed_meanwhile（手写）", () => {
  const gate = lines("def test_title():", "    assert False");

  it("land_oracle：末端上内容相同就不挑、部分相同照挑、files 为空直接 ff、sha 为空、分支上有 cherry-pick -x 的标记", () => {
    const shas: Record<string, string> = {};
    const make = (kind: string): Scene => scene(BASE_FILES, (repo, _wt, head) => {
      const oracle = commitOn(repo, head, { [GATE]: gate, [GATE2]: gate }, "门禁基准测试");
      shas[kind] = oracle;
      if (kind === "same") branchTo(repo, commitOn(repo, head, { [GATE]: gate, [GATE2]: gate }, "站主先放了同样的"));
      else if (kind === "partial") branchTo(repo, commitOn(repo, head, { [GATE]: gate }, "站主先放了一份"));
      else if (kind === "marker") branchTo(repo, commitOn(repo, head, { "src/x.py": "x" }, `别的提交${LF}${LF}(cherry picked from commit ${oracle})`));
      else branchTo(repo, head);
    }, false);
    const kinds = ["same", "partial", "empty", "nosha", "marker"];
    const scenes = kinds.map(make);
    const oracleOf = (kind: string): Record<string, unknown> => (kind === "nosha" ? { sha: "", files: [GATE] }
      : { sha: shas[kind], files: kind === "empty" ? [] : [GATE, GATE2] });
    const states = agreeFlow(scenes.map((sc, at) => flow("land_oracle", sc, [landTs(sc, { oracle: oracleOf(kinds[at] as string) })])));
    expect(states.map(returned)).toEqual([null, null, null, null, null]);
    expect(states.map((state) => (tsAfter(state).get("oracle") as PyDict).get("landed_by") ?? null)).toEqual([null, "cherry-pick", "ff", null, null]);
  }, 600_000);

  it("land_rework_chain：已落地的跳过、在分支上记 already、空提交记 empty、能 ff 就 ff、不能就挑、挑不上停下；run_dir 为空不筛，给了按基线筛、提交不存在照挑并报错", () => {
    const shas: Record<string, string> = {};
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      shas["l1"] = commitOn(repo, head, { "src/l1.py": "1" }, "第一轮");
      shas["l2"] = commitOn(repo, shas["l1"], { "src/l2.py": "2" }, "第二轮");
      shas["empty"] = commitOn(repo, shas["l2"], {}, "空的一轮");
      shas["ff"] = commitOn(repo, shas["l2"], { "src/l3.py": "3" }, "第三轮");
      shas["pick"] = commitOn(repo, head, { "src/l4.py": "4" }, "另起的一轮");
      shas["clash"] = commitOn(repo, head, { "src/l3.py": "冲突" }, "撞上的一轮");
      branchTo(repo, shas["l2"]);
      put(repo, `${RUNS}/attempt-002/meta.json`, JSON.stringify({ base_sha: shas["l2"] }));
    }, false);
    const link = (key: string, landed = false): Record<string, unknown> => ({ from: `attempt-${key}`, commit: shas[key] ?? key, ...(landed ? { landed_at: AT } : {}) });
    const chain = [link("l1", true), link("l2"), link("empty"), link("ff"), link("pick"), link("clash")];
    const missing = "0123456789012345678901234567890123456789";
    const states = agreeFlow([
      flow("land_rework_chain", sc, [landTs(sc, { rework_chain: chain, exec: { run_dir: null } })]),
      flow("land_rework_chain", sc, [landTs(sc, { rework_chain: [link("l1"), link("ff"), link(missing)], exec: { run_dir: runDirOf(sc, "002") } })]),
    ]);
    const first = returned(states[0]) as string;
    expect(first.startsWith(`返工提交 ${(shas["clash"] as string).slice(0, 12)}（attempt-clash 的候选）既不能 ff，也不能干净地挑到当前分支：`)).toBe(true);
    const how = (state: Record<string, unknown> | undefined): PyValue[] => (tsAfter(state).get("rework_chain") as PyDict[]).map((item) => item.get("landed_by") ?? null);
    expect(how(states[0])).toEqual([null, "already", "empty", "ff", "cherry-pick", null]);
    expect(String(returned(states[1]))).toContain(`返工提交 ${missing.slice(0, 12)}（attempt-${missing} 的候选）既不能 ff`);
    expect(how(states[1])).toEqual(["already", null, null]);
  }, 600_000);

  it("on_branch、landing_chain、landed_meanwhile 直接调：where 为空用 hub 的仓库、给了用那个 worktree；run_dir 为空照原样；check 没过不列；超过十个只列十个", () => {
    const shas: string[] = [];
    const sc = scene(BASE_FILES, (repo, wt, head) => {
      let tip = head;
      for (let index = 1; index <= 12; index += 1) {
        tip = commitOn(repo, tip, { [`src/m${index}.py`]: String(index) }, `期间的第 ${index} 个提交`);
        shas.push(tip);
      }
      branchTo(repo, tip);
      git(wt, "checkout", "-q", "--detach", head);
    });
    const meanwhile = landTs(sc, { exec: { check_ok: true } });
    const results = agreeCalls([
      call("on_branch", sc, [sc.repo, shas[11], null]), call("on_branch", sc, [sc.repo, shas[11], sc.wt]), call("on_branch", sc, [sc.repo, 5, null]),
      call("landing_chain", sc, [sc.repo, landTs(sc, { rework_chain: { a: 1 } }), null]),
      call("landed_meanwhile", sc, [sc.repo, meanwhile, shas[11]]), call("landed_meanwhile", sc, [sc.repo, landTs(sc, { exec: { check_ok: false } }), shas[11]]),
    ]);
    expect(results.slice(0, 4).map(valueOf)).toEqual([true, false, "TypeError", ["a"]]);
    const listed = String(valueOf(results[4])).split(LF);
    expect([listed.length, listed.at(-1)]).toEqual([13, "  …"]);
    expect(valueOf(results[5])).toBe("");
  }, 600_000);
});
