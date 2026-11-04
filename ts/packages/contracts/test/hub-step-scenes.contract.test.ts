// 第 ⑤i2 片的手写对照（采样那份在 hub-step.contract.test.ts）：临时仓库上摆好信箱与 state.json，三边各自先原地放回再跑，交回值、调用之后的参数、
// 文件、账本、git 状态与剧本里每次调用的参数逐字比（⑤i 设计稿第 6 节）。照剧本交回的只有 Python 用例里也换掉的那几个（runner、ensure_worktree、
// worktree_root、run_exec、rehearse_landing），其余真跑。
//   - 续接：主任务的 runner 锁被另一个进程拿着时 requeue_interrupted 不动（采样里跳过的 2 次就是这一支，themistally-04 要的），另配没人拿锁的对照；
//   - 扣信：限流的协调人回合扣信、在办标记清掉；到点放回：协调人的信放回后接着起回合（另配还没到点的对照），执行端的信放回后阶段回到
//     assigned、接着跑执行端（5360 的形状）。解除时刻正好等于钉住的时刻：Python 比的是 until <= now；
//   - 只测 TS：回合出意外那封信“偏离”的最后一行照生产写类名（三边对照里这一处被 crashNormalized 抹平了）；
//   - 变异补的场景：560 次采样与 30 份跑到静止的剧本都走不到的分支与截断长度（各条 it 的标题里写了对着哪条变异）；X07–X11 是 themistally-04
//     抽查漏掉的 5 条补的。
// 不写转义序列。
import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { DispatchError } from "@themis/dispatcher/repo";
import { COORDINATOR, OWNER } from "@themis/hub/constants";
import { Engine } from "@themis/hub/engine";
import { HubError } from "@themis/hub/errors";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, REPO, runBatch } from "./harness.ts";
import { AT, LF, type Scene, agreeFlow, flow, kernelPython, py, returned, scene, written } from "./flow-fixtures.ts";
import { put, removeCreated, tempDir } from "./repo-fixtures.ts";
import {
  BASE_FILES, BOX, SECONDS, crashNormalized, events, failure, letter, lettersTo, ran, runnerCalls, setStage, stagesAfter, stateAfter, turn, value,
} from "./engine-fixtures.ts";

afterAll(removeCreated);

const MSG = "20261101T000000000000Z-owner-000000";
const EXEC_MSG = "20261101T000000000000Z-coordinator-000000";

const TASKS: Record<string, readonly [string, string]> = { T001: ["doc", "改文档"], T002: ["next", "下一片"] };

/**
 * 建好信箱（同 cmd_run 起步时的 hub.ensure：new、cur 都在；new 不在时 os.rename 报错、被当成“别人已经放回了”吞掉），state.json 里是 edits 列的
 * 几个主任务（各自的 edit 改它），letters 把信放进各信箱。
 */
function tasksScene(edits: Record<string, (ts: PyDict) => void>, letters: (repo: string) => void, more: (repo: string) => void = () => undefined): Scene {
  return scene(BASE_FILES, (repo, _wt, head) => {
    new Hub(repo).ensure();
    const tasks = new Map<string, PyValue>();
    for (const [task, edit] of Object.entries(edits)) {
      const [slug, title] = TASKS[task] as readonly [string, string];
      const ts = newTaskState(task, slug, title, head, true, AT);
      edit(ts);
      tasks.set(task, ts);
    }
    put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map([["tasks", tasks]])));
    letters(repo);
    more(repo);
  });
}

/** state.json 里只有 T001。 */
function taskScene(edit: (ts: PyDict) => void, letters: (repo: string) => void, more: (repo: string) => void = () => undefined): Scene {
  return tasksScene({ T001: edit }, letters, more);
}

/** 协调人的“在办”标记：回合被收掉时留下的样子。 */
const marked = (ts: PyDict): void => void ts.set("coordinator_turn", py({ letters: [`${MSG}.md`], at: "20261101T000000000000Z" }));
const ownerLetter = (box: string) => (repo: string): void => void letter(repo, COORDINATOR, MSG, OWNER, "T001", "回复", box);

/** 另一个进程（真的 Python 子进程，kit_hub.DirLock）拿着 path 这把锁，直到被结束。 */
function holdLock(path: string, into: { child: ChildProcess | null }): void {
  const script = [
    "import sys, time", "sys.path.insert(0, sys.argv[1])", "import kit_hub", "from pathlib import Path",
    "kit_hub.DirLock(Path(sys.argv[2])).__enter__()", "print('held', flush=True)", "time.sleep(600)",
  ].join(LF);
  into.child = spawn(kernelPython(), ["-c", script, join(REPO, "scripts"), path], { stdio: "ignore" });
  for (let waited = 0; !existsSync(join(path, "owner.json")) && waited < 200; waited += 1) sleepSync(100);
}

const inboxWrites = (state: Record<string, unknown> | undefined): string[] =>
  Object.keys(written(state)).filter((key) => key.includes(`/inbox/`)).sort();

describe("第 ⑤i2 片：续接（手写）", () => {
  it("主任务的 runner 锁被另一个进程拿着：requeue_interrupted 不动，交回 []，信留在 cur；没人拿锁时照常放回（对照）", () => {
    const held: { child: ChildProcess | null } = { child: null };
    try {
      const free = taskScene(marked, ownerLetter("cur"));
      const locked = taskScene(marked, ownerLetter("cur"), (repo) => holdLock(join(repo, ...`${BOX}/.runners/T001`.split("/")), held));
      const states = agreeFlow([flow("requeue_interrupted", free, [[]]), flow("requeue_interrupted", locked, [[]])], undefined, REPLAY_TIMEOUT);
      expect(states.map((state) => returned(state))).toEqual([["T001"], []]);
      expect(inboxWrites(states[0])).toEqual([`0/${BOX}/inbox/${COORDINATOR}/new/${MSG}.md`]);
      expect(Object.keys(written(states[1])), "拿不到锁：在办标记、信都没动，一个文件也不写").toEqual([]);
    } finally {
      held.child?.kill();
    }
  }, 1_800_000);
});

describe("第 ⑤i2 片：扣信（手写）", () => {
  it("限流的协调人回合：扣信，在办标记清掉，写信告诉站主几点接着做", () => {
    const roots = tempDir("step-inputs");
    const sc = taskScene(() => undefined, ownerLetter("new"));
    const [state] = agreeFlow([{
      ...flow("Engine.step", sc, [null]),
      scripted: {
        runner: [turn("c1", null, { api_error: "rate_limit", rate_limited_until: SECONDS + 600 })], ensure_worktree: [value(sc.wt)], worktree_root: [value(roots)],
      },
    }]);
    const ts = stateAfter(state)["T001"] as Record<string, unknown>;
    expect([returned(state), (ts["held"] as Record<string, unknown>[]).map((item) => item["agent"]), "coordinator_turn" in ts, runnerCalls(state).length])
      .toEqual([true, [COORDINATOR], false, 1]);
  }, 600_000);

  it("到点放回：协调人的信放回 new，接着起协调人的回合；还没到点的不放（对照，step 交回 false）", () => {
    const roots = tempDir("step-inputs");
    const heldUntil = (until: string) => (ts: PyDict): void =>
      void ts.set("held", py([{ agent: COORDINATOR, letters: [`${MSG}.md`], until, suffix: null, turn: "c1" }]));
    const due = taskScene(heldUntil(AT), ownerLetter("cur"));
    const early = taskScene(heldUntil("2026-11-01T00:00:01Z"), ownerLetter("cur"));
    const scripted = (sc: Scene) => ({
      runner: [turn("c2", { letters: [], state: "等合同端" })], ensure_worktree: [value(sc.wt)], worktree_root: [value(roots)],
    });
    const states = agreeFlow([{ ...flow("Engine.step", due, [null]), scripted: scripted(due) }, { ...flow("Engine.step", early, [null]), scripted: scripted(early) }]);
    expect(states.map((state) => returned(state))).toEqual([true, false]);
    expect(events(states[0]).filter((event) => event["event"] === "letters.released").map((event) => event["letters"])).toEqual([[`${MSG}.md`]]);
    expect([(stateAfter(states[0])["T001"] as Record<string, unknown>)["held"], runnerCalls(states[0]).length, runnerCalls(states[1]).length]).toEqual([[], 1, 0]);
  }, 600_000);

  it("到点放回（5360 的形状）：执行端扣着的信放回，阶段从 paused 回到 assigned，接着跑执行端", () => {
    const sc = taskScene((ts) => {
      (ts.get("stages") as PyDict).set("5-exec", py({ status: "paused", assigned_at: AT, kind: "开工", note: "落地锁被占：之后内核把信放回信箱，接着做" }));
      ts.set("exec", py({ check_ok: true }));
      ts.set("held", py([{ agent: "exec-step", letters: [`${EXEC_MSG}.md`], until: AT, suffix: "5-exec", turn: "" }]));
    }, (repo) => void letter(repo, "exec-step", EXEC_MSG, COORDINATOR, "T001-5-exec", "开工", "cur"));
    const [state] = agreeFlow([{ ...flow("Engine.step", sc, [null]), scripted: { run_exec: [value(ran("通过"))], rehearse_landing: [value(null)] } }],
      undefined, REPLAY_TIMEOUT);
    expect([returned(state), stagesAfter(state)["5-exec"]?.["status"]]).toEqual([true, "delivered"]);
    expect(events(state).filter((event) => event["event"] === "letters.released").map((event) => event["agent"])).toEqual(["exec-step"]);
  }, 1_800_000);
});

describe("第 ⑤i2 片：回合出意外那封信的类名（只测 TS）", () => {
  // 三边对照里“偏离”只比最后一行、开头的“kit_hub.”去掉（用例 import kit_hub），抓不住 TS 写错模块名；这里直接看 TS 写的那封信与账本：生产上 kit_hub
  // 当脚本跑（__main__），HubError 不带模块名；别的模块的类带（pi_dispatch.DispatchError），CPython 3.12.10 实测（themistally-04 要的）
  it("HubError 写成“HubError: …”，调度器的 DispatchError 写成“pi_dispatch.DispatchError: …”；“验证”一栏与账本里 step.error 的 error 只写类名（X07）", async () => {
    const deviationOf = (text: string): string => {
      const lines = text.split(LF);
      const start = lines.findIndex((line) => line.startsWith("偏离: "));
      let end = start + 1;
      while (end < lines.length && (lines[end] as string).startsWith("  ")) end += 1;
      return end - 1 > start ? (lines[end - 1] as string).slice(2) : (lines[start] as string).slice("偏离: ".length);
    };
    /** 写给站主的那封信，与账本里 step.error 的 error（Python 5037 写 type(exc).__name__，不带模块）。 */
    const letterAfter = async (error: unknown): Promise<[string, unknown]> => {
      const repo = tempDir("step-crash");
      const hub = new Hub(repo);
      hub.ensure();
      await new Engine(hub).reportStepError("planner-opus", [], error);
      const box = hub.inbox(OWNER);
      const ledger = readFileSync(join(repo, ...`${BOX}/ledger/events.jsonl`.split("/")), "utf8").split(LF).filter(Boolean)
        .map((line) => JSON.parse(line) as Record<string, unknown>);
      return [readFileSync(join(box, readdirSync(box)[0] as string), "utf8"), ledger.find((event) => event["event"] === "step.error")?.["error"]];
    };
    const [hubError, hubEvent] = await letterAfter(new HubError("git worktree add 失败", 1));
    const [dispatchError, dispatchEvent] = await letterAfter(new DispatchError("调度器报错"));
    expect([deviationOf(hubError), deviationOf(dispatchError)]).toEqual(["HubError: git worktree add 失败", "pi_dispatch.DispatchError: 调度器报错"]);
    expect([hubError.includes(`${LF}验证: HubError: git worktree add 失败${LF}`), dispatchError.includes(`${LF}验证: DispatchError: 调度器报错${LF}`)])
      .toEqual([true, true]);
    expect([hubEvent, dispatchEvent]).toEqual(["HubError: git worktree add 失败", "DispatchError: 调度器报错"]);
  }, 120_000);
});

const NOTHING = { write: {}, delete: [] };
/** 第 index 封信的编号：时刻按秒错开（信箱里按文件名排，就是按时刻）。 */
const msgAt = (index: number, from = "owner"): string => `20261101T0000${String(index).padStart(2, "0")}000000Z-${from}-000000`;
/** 账本里先有的几条事件（每行一个 JSON 对象）。 */
const ledgerOf = (repo: string, items: readonly Record<string, unknown>[]): void =>
  put(repo, `${BOX}/ledger/events.jsonl`, items.map((item) => `${JSON.stringify(item)}${LF}`).join(""));
const taken = (agent: string, msgId: string): Record<string, unknown> => ({ at: AT, event: "letter.taken", agent, msg_id: msgId });
const assigned = (suffix: string) => (ts: PyDict): void => setStage(ts, suffix, py({ status: "assigned", assigned_at: AT, kind: "开工" }));
/** 注入一次 pid_alive（采样的写法：问的 pid、交回值）。 */
const alive = (pid: number, answer: boolean | null): unknown => ({ fn: "pid_alive", pid, value: toTagged(answer), files: NOTHING });
/** 信里一栏的全文：续行去掉开头两个空格接回去。 */
function fieldOf(text: string, name: string): string {
  const lines = text.split(LF);
  const start = lines.findIndex((line) => line.startsWith(`${name}: `));
  let end = start + 1;
  while (end < lines.length && (lines[end] as string).startsWith("  ")) end += 1;
  return [(lines[start] as string).slice(name.length + 2), ...lines.slice(start + 1, end).map((line) => line.slice(2))].join(LF);
}

/** 不经 hub.contract_flow 的只读调用：先放回场景，三边各跑一次逐个比，交回 Python 的值（同 hub-land-scenes）。 */
function agreeCalls(requests: readonly ProbeRequest[]): PyValue[] {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  for (const [index, other] of others.entries()) {
    expect(JSON.stringify(other), `${IMPLS[index + 1]?.name} 与 Python 不同`).toBe(JSON.stringify(python));
  }
  return (python as ProbeResult[]).map((result) => (result["ok"] ? fromTagged(result["value"] as Tagged) : (result["error"] as string)));
}
const call = (fn: string, sc: Scene | null, args: unknown[]): ProbeRequest =>
  ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))), restores: sc === null ? [] : sc.restores });

describe("第 ⑤i2 片：变异补的场景（手写）", () => {
  it("回合出意外：信都读不出主任务时写 T000、摘要截 600 字（R01、R05）；出错文字为空时最后一行只写类名（R08）；工人回合出错的 note 截 200 字、验证截 300 字（R04、R06）", () => {
    const names = Array.from({ length: 20 }, (_, index) => `${msgAt(index)}.md`);
    const unreadable = taskScene(() => undefined, (repo) => names.forEach((name) => put(repo, `${BOX}/inbox/${COORDINATOR}/new/${name}`, `不是信${LF}`)));
    const silent = taskScene(() => undefined, ownerLetter("new"));
    const worker = taskScene(assigned("1-plan"), (repo) => void letter(repo, "planner-opus", EXEC_MSG, COORDINATOR, "T001-1-plan", "开工"));
    const fail = (message: string) => ({ ensure_worktree: [{ raise: ["HubError", message, 1] }] });
    const [first, second, third] = agreeFlow([
      flow("Engine.step", unreadable, [null]), { ...flow("Engine.step", silent, [null]), scripted: fail("") },
      { ...flow("Engine.step", worker, [null]), scripted: fail("甲".repeat(400)) },
    ], crashNormalized);
    const [crash] = lettersTo(first, OWNER);
    expect([crash?.includes(`${LF}task-id: T000${LF}`), fieldOf(crash as string, "摘要")])
      .toEqual([true, `${COORDINATOR} 的回合出了意外，这几封信读了还没办：${names.join("、").slice(0, 600)}`]);
    expect(fieldOf(lettersTo(second, OWNER)[0] as string, "偏离").split(LF).filter(Boolean).at(-1), "Python 的 format_exception：文字为空只写类名").toBe("kit_hub.HubError");
    expect([stagesAfter(third)["1-plan"]?.["note"], fieldOf(lettersTo(third, OWNER)[0] as string, "验证")])
      .toEqual([`回合出错：HubError: ${"甲".repeat(200)}`, `HubError: ${"甲".repeat(300)}`]);
  }, 600_000);

  it("协调人的信：没登记的主任务、不是进行中的主任务都跳过（C01、C03）；一回合只办最早那封所属主任务的信，别的留在 new（C02）；没有拒收时拒收计数清零（C20）；回合进行中 state.json 里有在办标记（C06）", () => {
    const roots = tempDir("step-inputs");
    const unregistered = taskScene(() => undefined, (repo) => void letter(repo, COORDINATOR, MSG, OWNER, "T009", "回复"));
    const blocked = taskScene((ts) => void ts.set("status", "blocked"), ownerLetter("new"));
    const two = tasksScene({ T001: (ts) => void ts.set("coordinator_rejections", 2n), T002: () => undefined }, (repo) => {
      letter(repo, COORDINATOR, msgAt(1), OWNER, "T001", "回复");
      letter(repo, COORDINATOR, msgAt(2), OWNER, "T002", "回复");
    });
    const peek = { ...(turn("c1", { letters: [], state: "等站主" }) as object), peek: `0/${BOX}/ledger/state.json` };
    const [first, second, third] = agreeFlow([
      flow("Engine.step", unregistered, [null]), flow("Engine.step", blocked, [null]),
      { ...flow("Engine.step", two, [null]), scripted: { runner: [peek], ensure_worktree: [value(two.wt)], worktree_root: [value(roots)] } },
    ]);
    const skipped = (state: Record<string, unknown> | undefined): unknown[] =>
      events(state).filter((event) => event["event"] === "coordinator.skipped").map((event) => event["reason"]);
    expect([skipped(first), skipped(second)]).toEqual([["信里没有登记过的主任务"], ["主任务 T001 状态为 blocked"]]);
    expect(inboxWrites(third).filter((key) => key.includes(`/${COORDINATOR}/`))).toEqual([`0/${BOX}/inbox/${COORDINATOR}/cur/${msgAt(1)}.md`]);
    expect((stateAfter(third)["T001"] as Record<string, unknown>)["coordinator_rejections"]).toBe(0);
    const during = JSON.parse(runnerCalls(third)[0]?.["peek"] as string) as { tasks: Record<string, Record<string, unknown>> };
    expect(during.tasks["T001"]?.["coordinator_turn"]).toEqual({ letters: [`${msgAt(1)}.md`], at: "20261101T000000000000Z" });
  }, 600_000);

  it("协调人回合作废：限流又违规的作废、不扣信，违规用分号连（C10、C11）；两次都没有输出、也没写原因时写“没有输出”（C12）", () => {
    const roots = tempDir("step-inputs");
    const scripted = (sc: Scene, runner: unknown[]) => ({ runner, ensure_worktree: [value(sc.wt)], worktree_root: [value(roots)] });
    const limited = taskScene(() => undefined, ownerLetter("new"));
    const empty = taskScene(() => undefined, ownerLetter("new"));
    const [first, second] = agreeFlow([
      { ...flow("Engine.step", limited, [null]), scripted: scripted(limited, [turn("c1", null, { violations: ["越界读了 a", "越界读了 b"], api_error: "rate_limit", rate_limited_until: SECONDS + 600 })]) },
      { ...flow("Engine.step", empty, [null]), scripted: scripted(empty, [turn("c1", null, { output_error: null }), turn("c2", null, { output_error: null })]) },
    ]);
    const blocked = (state: Record<string, unknown> | undefined): unknown[] => {
      const ts = stateAfter(state)["T001"] as Record<string, unknown>;
      return [ts["status"], "held" in ts ? ts["held"] : null, (ts["notes"] as Record<string, unknown>[]).at(-1)?.["text"]];
    };
    expect([blocked(first), blocked(second)]).toEqual([
      ["blocked", null, "协调人回合作废：越界读了 a；越界读了 b（回合 c1）"], ["blocked", null, "协调人回合作废：没有输出（回合 c2）"],
    ]);
  }, 600_000);

  it("协调人的信被拒收：不是对象（D01）、几处问题用分号连（D05）、正文正好 40 行能投、41 行拒收（D04）；续接的回合里拒收的不是 BUSY_GUARD 照样算拒收（C15）；拒收信的偏离截 1500 字（C21）", () => {
    const roots = tempDir("step-inputs");
    const sc = taskScene((ts) => void ts.set("coordinator_resume", py({ at: AT, turn: "20261101T000000000000Z-c0", letters: [`${MSG}.md`] })), ownerLetter("new"));
    const report = (lines: number) => ({
      to: OWNER, type: "汇报", task_id: "T001", 摘要: `偏离写 ${lines} 行`, 偏离: Array.from({ length: lines }, (_, at) => `第 ${at + 1} 行`).join(LF),
    });
    // 不是对象的信 coordinator_turn 自己就走不下去（拒收原因要取 item.get），只有直接调 deliver_coordinator_letter 看得到它的拒收原因
    const letters = [{}, report(35), report(36), { to: "planner-opus", type: "丑".repeat(1600), task_id: "T001-1-plan" }];
    const [state, direct] = agreeFlow([{
      ...flow("Engine.step", sc, [null]),
      scripted: { runner: [turn("c1", { letters, state: "等站主" })], ensure_worktree: [value(sc.wt)], worktree_root: [value(roots)] },
    }, flow("Engine.deliver_coordinator_letter", taskScene(() => undefined, () => undefined), [null, py({ tasks: {} }), "不是对象", COORDINATOR])]);
    expect(returned(direct)).toBe("信不是对象");
    const [notice] = lettersTo(state, COORDINATOR);
    const deviation = fieldOf(notice as string, "偏离");
    expect([fieldOf(notice as string, "摘要"), [...deviation].length]).toEqual(["你上一回合有 3 封信被内核拒收，1 封已投递", 1500]);
    expect(deviation.split(LF).slice(0, 2).map((line) => line.split("：").slice(1).join("：")))
      .toEqual([expect.stringContaining("头部缺 to；头部缺 task-id；"), "正文 41 行，超过 40 行：细节放进 report.md"]);
    expect(lettersTo(state, OWNER).map((item) => fieldOf(item, "摘要"))).toEqual(["偏离写 35 行"]);
    expect(events(state).filter((event) => event["event"] === "coordinator.resent")).toEqual([]);
  }, 600_000);

  it("内核代办：执行端已经返工两次，第三次返工照样代办（T03，只有别的阶段的最后一次返工留给协调人）", () => {
    const sc = taskScene((ts) => {
      setStage(ts, "5-exec", py({ status: "failed", assigned_at: AT, kind: "开工", note: "执行端没过" }));
      ts.set("reworks", py({ "5-exec": 2 }));
    }, (repo) => void letter(repo, COORDINATOR, msgAt(1, "audit-sonnet"), "audit-sonnet", "T001-7-audit-post", "交付", "new",
      { 结论: "返工", 退回: "执行端", 阻塞项: "1. 改回去", 内核核验: "通过" }));
    const [state] = agreeFlow([flow("Engine.step", sc, [null])]);
    const ts = stateAfter(state)["T001"] as Record<string, unknown>;
    expect([events(state).filter((event) => event["event"] === "route.kernel").length, stagesAfter(state)["5-exec"]?.["status"], ts["reworks"]])
      .toEqual([1, "assigned", { "5-exec": 3 }]);
  }, 600_000);

  it("续接：扣着的协调人信不放回（Q13）；续接过的是别的信照样放回（X04）；拒绝续接时阶段的 note 截 600 字（Q16）；搬信时别的 HubError 照样抛（Q11）；主任务不是进行中时 requeue_task 不动（Q12）", () => {
    const heldToo = taskScene((ts) => {
      marked(ts);
      ts.set("held", py([{ agent: COORDINATOR, letters: [`${MSG}.md`], until: "2026-11-01T00:10:00Z", suffix: null, turn: "c1" }]));
    }, ownerLetter("cur"));
    const other = taskScene(marked, ownerLetter("cur"), (repo) => ledgerOf(repo, [
      { at: AT, event: "letters.requeued", task: "T001", agent: COORDINATOR, key: "T001", letters: [`${msgAt(9)}.md`], turn: null },
    ]));
    const refused = taskScene(assigned("1-plan"), (repo) => void letter(repo, "planner-opus", EXEC_MSG, COORDINATOR, "T001-1-plan", "开工", "cur"),
      (repo) => ledgerOf(repo, [taken("planner-opus", EXEC_MSG), {
        at: AT, event: "letters.requeued", task: "T001", agent: "planner-opus", key: "T001-1-plan", letters: [`${EXEC_MSG}.md`], turn: "回".repeat(700),
      }]));
    const garbled = taskScene(assigned("1-plan"), (repo) => put(repo, `${BOX}/inbox/planner-opus/cur/${EXEC_MSG}.md`, `不是信${LF}`),
      (repo) => ledgerOf(repo, [taken("planner-opus", EXEC_MSG)]));
    const stopped = taskScene((ts) => {
      marked(ts);
      ts.set("status", "blocked");
    }, ownerLetter("cur"));
    const states = agreeFlow([
      flow("requeue_interrupted", heldToo, [[]]), flow("requeue_interrupted", other, [[]]), flow("requeue_interrupted", refused, [[]]),
      flow("requeue_interrupted", garbled, [[]]), flow("requeue_task", stopped, ["T001"]),
    ], undefined, REPLAY_TIMEOUT);
    expect([returned(states[0]), returned(states[1]), returned(states[2]), failure(states[3])[0], returned(states[4])])
      .toEqual([[], ["T001"], [], "HubError", false]);
    expect([inboxWrites(states[0]), inboxWrites(states[1])]).toEqual([[], [`0/${BOX}/inbox/${COORDINATOR}/new/${MSG}.md`]]);
    const note = stagesAfter(states[2])["1-plan"]?.["note"] as string;
    expect([stagesAfter(states[2])["1-plan"]?.["status"], [...note].length]).toEqual(["failed", 600]);
    expect(Object.keys(written(states[4])), "主任务停了：一个文件也不写").toEqual([]);
  }, 1_800_000);

  it("执行端读了信没人在办：执行标记的进程问不出死活时先不报（Q23）；跑完没结论的 attempt 写 exec-recheck（Q24）；证据截 600 字（Q26）", () => {
    const exec = (count: number, more: (repo: string) => void) => {
      const ids = Array.from({ length: count }, (_, index) => msgAt(index, "coordinator"));
      return taskScene(assigned("5-exec"), (repo) => ids.forEach((id) => void letter(repo, "exec-step", id, COORDINATOR, "T001-5-exec", "开工", "cur")),
        (repo) => {
          ledgerOf(repo, ids.map((id) => taken("exec-step", id)));
          more(repo);
        });
    };
    const unknown = exec(1, (repo) => put(repo, `${BOX}/ledger/exec-active/T001.json`, JSON.stringify({ pid: 4242, task: "T001" })));
    const finished = exec(15, (repo) => put(repo, ".agent/runs/t001-doc/attempt-001/state.json", JSON.stringify({ state: "NEEDS_REVIEW" })));
    const [first, second] = agreeFlow([
      flow("requeue_interrupted", unknown, [[]], { inner: [alive(4242, null)], replaced: ["pid_alive"] }), flow("requeue_interrupted", finished, [[]]),
    ], undefined, REPLAY_TIMEOUT);
    expect([returned(first), Object.keys(written(first))]).toEqual([[], []]);
    const [notice] = lettersTo(second, OWNER);
    const names = Array.from({ length: 15 }, (_, index) => `${msgAt(index, "coordinator")}.md`);
    expect([fieldOf(notice as string, "偏离"), fieldOf(notice as string, "证据")])
      .toEqual(["attempt-001 跑完了、还没有结论：用 kit_hub.py exec-recheck T001 重新核验（不重跑执行端）", names.join("、").slice(0, 600)]);
  }, 1_800_000);

  it("只读的几个：next_job 取各信箱最早那封（X01）；tasks_with_work 按各主任务最早那封排（Q29）；finished_turn 只认 since 之后开始、没违规的回合（Q01、Q02）", () => {
    const early = taskScene(() => undefined, (repo) => {
      letter(repo, COORDINATOR, msgAt(9), OWNER, "T001", "回复");
      letter(repo, "planner-opus", msgAt(1, "coordinator"), COORDINATOR, "T001-1-plan", "开工");
    });
    const two = tasksScene({ T001: assigned("1-plan"), T002: () => undefined }, (repo) => {
      letter(repo, COORDINATOR, msgAt(5), OWNER, "T002", "回复");
      letter(repo, COORDINATOR, msgAt(9), OWNER, "T001", "回复");
      letter(repo, "planner-opus", msgAt(1, "coordinator"), COORDINATOR, "T001-1-plan", "开工");
    });
    const since = "20261101T000000000000Z";
    const finished = (turnId: string, violations: string[]) =>
      [{ event: "turn.finished", agent: COORDINATOR, session_key: "T001", turn_id: turnId, output_ok: true, violations }];
    const values = agreeCalls([
      call("Engine.next_job", early, [early.repo, null]), call("tasks_with_work", two, [two.repo]),
      call("finished_turn", null, [finished(since, []), COORDINATOR, "T001", since]),
      call("finished_turn", null, [finished("20261101T000001000000Z-c1", ["越界"]), COORDINATOR, "T001", since]),
      call("finished_turn", null, [finished("20261101T000001000000Z-c1", []), COORDINATOR, "T001", since]),
    ]);
    expect([(values[0] as PyValue[])[0], values[1], values[2], values[3], values[4]])
      .toEqual(["planner-opus", ["T001", "T002"], null, null, "20261101T000001000000Z-c1"]);
  }, 600_000);

  // 代办途中 state.json 里的“在办”标记带 routing：进程死在代办中途时，requeue_task 据此把续接记成代办（第 112 轮）。代办办完就清掉，step 交回后
  // 看不到；探针的 peek_deliver 在投信那一刻读一次 state.json（T06）
  it("内核代办投信那一刻，在办标记是 letters、at、routing（T06）", () => {
    const sc = taskScene(() => undefined, (repo) => void letter(repo, COORDINATOR, MSG, OWNER, "T001", "任务"));
    const [state] = agreeFlow([{ ...flow("Engine.step", sc, [null]), peek_deliver: `0/${BOX}/ledger/state.json` }]);
    const peeks = (state?.["deliver_peeks"] as string[]).map((item) =>
      (JSON.parse(item) as { tasks: Record<string, Record<string, unknown>> }).tasks["T001"]?.["coordinator_turn"]);
    expect(peeks).toEqual([{ letters: [`${MSG}.md`], at: "20261101T000000000000Z", routing: true }]);
  }, 600_000);

  it("协调人的信：某栏只有空白时写“无”照投（X08）；返工门禁前以外的阶段不起热修补（X09）", () => {
    const roots = tempDir("step-inputs");
    const scripted = (sc: Scene, item: unknown) =>
      ({ runner: [turn("c1", { letters: [item], state: "等站主" })], ensure_worktree: [value(sc.wt)], worktree_root: [value(roots)] });
    const blank = taskScene(() => undefined, ownerLetter("new"));
    // 执行端报了合同矛盾（hotfix_reason 有原因），合同端又核验没过：_guard_rework 见 failed 就放行，轮不到看热修补
    const contract = taskScene((ts) => {
      (ts.get("exec") as PyDict).set("conflicts", 2n);
      setStage(ts, "2-contract", py({ status: "failed", assigned_at: AT, kind: "开工", note: "合同核验没过" }));
    }, ownerLetter("new"));
    const [first, second] = agreeFlow([
      { ...flow("Engine.step", blank, [null]), scripted: scripted(blank, { to: OWNER, type: "汇报", task_id: "T001", 摘要: "进展", 偏离: "   " }) },
      { ...flow("Engine.step", contract, [null]), scripted: scripted(contract, { to: "contract-glm", type: "返工", task_id: "T001-2-contract", 摘要: "照执行端的矛盾改合同", brief: "# 合同返工" }) },
    ]);
    expect(lettersTo(first, OWNER).map((item) => fieldOf(item, "偏离"))).toEqual(["无"]);
    const ts = stateAfter(second)["T001"] as Record<string, unknown>;
    expect(["hotfix" in ts, events(second).filter((event) => event["event"] === "hotfix.started").length, stagesAfter(second)["2-contract"]?.["status"], ts["reworks"]])
      .toEqual([false, 0, "assigned", { "2-contract": 1 }]);
  }, 600_000);

  it("续接：协调人的信放回过一次、不再续接，主任务转 blocked，停住的工人阶段不再动（X10）；阶段只放回 assigned_at 之后读掉的信（X11）", () => {
    const [older, newer] = [msgAt(1, "coordinator"), msgAt(2, "coordinator")];
    const takenAt = (msgId: string, at: string): Record<string, unknown> => ({ ...taken("planner-opus", msgId), at });
    const twice = taskScene((ts) => {
      marked(ts);
      assigned("1-plan")(ts);
    }, (repo) => {
      ownerLetter("cur")(repo);
      letter(repo, "planner-opus", EXEC_MSG, COORDINATOR, "T001-1-plan", "开工", "cur");
    }, (repo) => ledgerOf(repo, [
      { at: AT, event: "letters.requeued", task: "T001", agent: COORDINATOR, key: "T001", letters: [`${MSG}.md`], turn: null },
      taken("planner-opus", EXEC_MSG),
    ]));
    // 回合出意外、阶段标成 failed，旧的开工信留在 cur 没人回；协调人重新开工（assigned_at 更新），工人读了新信之后被收掉
    const reissued = taskScene((ts) => setStage(ts, "1-plan", py({ status: "assigned", assigned_at: "2026-11-01T00:00:05Z", kind: "开工" })), (repo) => {
      letter(repo, "planner-opus", older, COORDINATOR, "T001-1-plan", "开工", "cur");
      letter(repo, "planner-opus", newer, COORDINATOR, "T001-1-plan", "开工", "cur");
    }, (repo) => ledgerOf(repo, [takenAt(older, AT), takenAt(newer, "2026-11-01T00:00:10Z")]));
    const [first, second] = agreeFlow([flow("requeue_interrupted", twice, [[]]), flow("requeue_interrupted", reissued, [[]])], undefined, REPLAY_TIMEOUT);
    const plan = stagesAfter(first)["1-plan"] as Record<string, unknown>;
    expect([returned(first), stateAfter(first)["T001"]?.["status"], plan["status"], "resume" in plan, lettersTo(first, OWNER).length])
      .toEqual([[], "blocked", "assigned", false, 1]);
    expect(inboxWrites(first).filter((key) => key.includes("/planner-opus/")), "工人的信留在 cur").toEqual([]);
    expect([returned(second), inboxWrites(second), (stagesAfter(second)["1-plan"]?.["resume"] as Record<string, unknown>)["letters"]])
      .toEqual([["T001"], [`0/${BOX}/inbox/planner-opus/new/${newer}.md`], [`${newer}.md`]]);
  }, 1_800_000);
});
