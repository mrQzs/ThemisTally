// 被收掉之后的续接（迁移第 ⑤i2 片）：kit_hub.py 的 finished_turn、interrupted_letters、stranded_stages、requeue_interrupted、requeue_task、
// requeue_letters、report_stranded_exec，以及 letters_held、supervisor_busy、runner_may_idle_exit、tasks_with_work、runner_lock。
// deps 只给契约用：report_stranded_exec 问执行标记里的 pid 还活着没有，用例换掉的照记录注入；生产调用方不传。
// 账本事件、状态与信头里的容器照 Python 取键；标量照内核实际写出的类型（letters 是文字的列表之类）。
import { statSync } from "node:fs";
import { dirname } from "node:path";
import { utcNow } from "@themis/base/clock";
import { readText } from "@themis/base/fsutil";
import { pyCaught } from "@themis/base/pyexc";
import { pyRename } from "@themis/base/pyos";
import { PyCrash, pyGet, pyIntOf, pyItem, pyIter, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { purePathName, purePathStr } from "@themis/base/pypath";
import { pidAlive } from "@themis/base/process";
import { cmpCodePoints, codePoints } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { COORDINATOR, EXIT_BLOCKED, KERNEL, OWNER, ROSTER, type RosterSpec, STAGE_WORKER } from "./constants.ts";
import { HubError } from "./errors.ts";
import { interruptedAttempt } from "./exec.ts";
import { parseLetter } from "./letters.ts";
import { DirLock, type Hub, ledgerEvents, letterMain } from "./mailbox.ts";
import { execMarks } from "./runexec.ts";
import { stageBusy } from "./taskstate.ts";

/** 用例当时换掉、契约照记录注入的：执行标记里的 pid 还活着没有（同 LandDeps.pidAlive）。缺省是真的。 */
export interface RequeueDeps {
  readonly pidAlive: (pid: number) => boolean | null;
}

export const REAL_REQUEUE_DEPS: RequeueDeps = { pidAlive };

/**
 * since（utc_compact）之后开始的这个会话最后一个跑完的回合：输出合格、没违规的交回回合号，否则 null。
 * 第 95 轮：按回合号比（它以开始时刻的 utc_compact 开头，到微秒），不按事件的 at（只到秒）。
 */
export function finishedTurn(events: readonly PyValue[], agent: string, sessionKey: string, since: string): PyValue {
  let turn: PyValue = null;
  for (const event of events) {
    if (pyEq(pyGet(event, "event"), "turn.finished") && pyEq(pyGet(event, "agent"), agent) && pyEq(pyGet(event, "session_key"), sessionKey)
      && cmpCodePoints(pyStrValue(or(pyGet(event, "turn_id"), "")), since) > 0) {
      turn = pyTruthy(pyGet(event, "output_ok")) && !pyTruthy(pyGet(event, "violations")) ? pyGet(event, "turn_id") : null;
    }
  }
  return turn;
}

/**
 * 一个阶段被读掉、工人还没回信的信（cur 里的文件名），以及读信之后跑完、输出合格的最后一个回合。
 * 只含告知类、工人没被唤醒的信（worker.not_woken）与扣着的信（ts["held"]）不算：不是被打断的那一批。
 */
export function interruptedLetters(hub: Hub, events: readonly PyValue[], agent: string, stageId: string, since: string,
  held: readonly PyValue[] = []): [string[], PyValue] {
  let taken: string[] = [];
  let turn: PyValue = null;
  for (const event of events) {
    if (cmpCodePoints(pyStrValue(or(pyGet(event, "at"), "")), since) < 0) continue;
    const kind = pyGet(event, "event");
    const name = `${pyStrValue(pyGet(event, "msg_id"))}.md`;
    if (pyEq(kind, "letter.taken") && pyEq(pyGet(event, "agent"), agent) && !taken.includes(name)) {
      taken.push(name); // 放回去又读一次的，只算一封
    } else if (pyEq(kind, "worker.not_woken") && pyEq(pyGet(event, "agent"), agent)) {
      const dropped = pyIter(or(pyGet(event, "letters"), []));
      taken = taken.filter((item) => !dropped.some((other) => pyEq(other, item)));
    } else if (pyEq(kind, "letter.delivered") && pyEq(pyGet(event, "sender"), agent) && pyEq(pyGet(event, "task_id"), stageId)) {
      taken = []; // 工人回过信：之前读的信办完了
      turn = null;
    } else if (pyEq(kind, "turn.finished") && pyEq(pyGet(event, "session_key"), stageId) && taken.length > 0) {
      turn = pyTruthy(pyGet(event, "output_ok")) && !pyTruthy(pyGet(event, "violations")) ? pyGet(event, "turn_id") : null;
    }
  }
  const box = purePathStr(dirname(hub.inbox(agent)), "cur");
  const names = taken.filter((name) => !held.some((item) => pyEq(item, name)) && isFile(purePathStr(box, name))
    && parseLetter(readText(purePathStr(box, name)))[0].get("task-id") === stageId);
  return [names, names.length > 0 ? turn : null];
}

/** 停在“已经开工”、工人信箱里却没有它的未读信的阶段（JEV、执行端也在内，第 94 轮）。 */
export function strandedStages(hub: Hub, ts: PyDict): string[] {
  const stages: string[] = [];
  const all = pyItem(ts, "stages");
  if (!(all instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(all)}' object has no attribute 'items'`);
  for (const [suffix, stage] of all) {
    const agent = Object.hasOwn(STAGE_WORKER, String(suffix)) ? STAGE_WORKER[String(suffix)] as string : null;
    if (agent === null || !stageBusy(stage)) continue;
    const stageId = `${pyStrValue(pyItem(ts, "task"))}-${String(suffix)}`;
    if (!hub.unread(agent).some((path) => parseLetter(readText(path))[0].get("task-id") === stageId)) stages.push(String(suffix));
  }
  return stages;
}

/**
 * runner 办到一半被收掉（第 93 轮）：阶段停在 assigned，工人的信已经读掉，没有未读信，supervisor 不起 runner。这里把读掉的信放回 new、
 * 记下 resume，接着做；协调人的回合（“在办”标记还在）、协调人开工的 JEV 同样放回；执行端不自己重跑，写信给站主（第 94 轮）。
 * 主任务的 runner 锁有人拿着就不动，搬信时自己拿着这把锁。交回放回了哪些主任务的信。
 */
export async function requeueInterrupted(hub: Hub, skip: readonly PyValue[] = [], deps: RequeueDeps = REAL_REQUEUE_DEPS): Promise<string[]> {
  const requeued: string[] = [];
  const tasks = hub.loadState().tasks();
  for (const task of [...tasks.keys()].map(String).sort(cmpCodePoints)) {
    const ts = tasks.get(task) as PyDict;
    if (!pyEq(pyGet(ts, "status"), "active") || skip.some((item) => pyEq(item, task))
      || !(pyTruthy(pyGet(ts, "coordinator_turn")) || strandedStages(hub, ts).length > 0)) continue;
    try {
      const lock = new DirLock(runnerLock(hub, task), 0).acquire(); // 持有者活着就拿不到；已经不在了才接管
      try {
        if (await requeueTask(hub, task, deps)) requeued.push(task);
      } finally {
        lock.release();
      }
    } catch (error) {
      if (!(error instanceof HubError) || error.code !== EXIT_BLOCKED) throw error; // 有人在办：不动，下一轮再看
    }
  }
  return requeued;
}

/** 拿着主任务的 runner 锁、重新核对之后放回信。交回放回了没有。 */
export async function requeueTask(hub: Hub, task: string, deps: RequeueDeps = REAL_REQUEUE_DEPS): Promise<boolean> {
  const state = hub.loadState();
  const ts = pyGet(state.tasks(), task) as PyDict | null;
  if (ts === null || !pyEq(pyGet(ts, "status"), "active")) return false;
  const events = ledgerEvents(hub);
  const held = pyIter(or(pyGet(ts, "held"), [])).flatMap((item) => pyIter(or(pyGet(item, "letters"), [])));
  let changed = false;
  let movedAny = false;
  const marker = popKey(ts, "coordinator_turn");
  if (pyTruthy(marker)) {
    changed = true;
    const box = purePathStr(dirname(hub.inbox(COORDINATOR)), "cur");
    const names = pyIter(or(pyGet(marker, "letters"), []))
      .filter((name) => !held.some((item) => pyEq(item, name)) && isFile(purePathStr(box, pyStrValue(name))));
    const turn = finishedTurn(events, COORDINATOR, task, pyStrValue(or(pyGet(marker, "at"), "")));
    const moved = names.length > 0 ? await requeueLetters(hub, ts, events, COORDINATOR, task, names, turn, "协调人") : null;
    if (moved !== null && moved.length > 0) {
      const resume = new Map<string, PyValue>([["at", utcNow()], ["turn", turn], ["letters", names]]);
      if (pyTruthy(pyGet(marker, "routing"))) resume.set("routing", true); // 第 112 轮：被收掉的是内核代办，不是协调人的回合
      ts.set("coordinator_resume", resume);
      movedAny = true;
    }
  }
  for (const suffix of pyEq(pyGet(ts, "status"), "active") ? strandedStages(hub, ts) : []) {
    const agent = STAGE_WORKER[suffix] as string;
    const stage = pyItem(pyItem(ts, "stages"), suffix) as PyDict;
    const stageId = `${task}-${suffix}`;
    const [names, turn] = interruptedLetters(hub, events, agent, stageId, pyStrValue(or(pyGet(stage, "assigned_at"), "")), held);
    if (names.length === 0) continue; // 找不到读掉的信：留给站主的 task unstick
    if (rosterSpec(agent).adapter === "dispatcher") {
      changed = (await reportStrandedExec(hub, ts, stage, names, deps)) || changed;
      continue;
    }
    const moved = await requeueLetters(hub, ts, events, agent, stageId, names, turn, stageId);
    if (moved === null) { // requeue_letters 不再续接时刚往 notes 里加了一条
      const notes = pyItem(ts, "notes") as PyValue[];
      stage.set("status", "failed").set("note", head(pyStrValue(pyItem(notes[notes.length - 1] as PyValue, "text")), 600));
    } else if (moved.length > 0) {
      stage.set("resume", new Map<string, PyValue>([["at", utcNow()], ["turn", turn], ["letters", moved]]));
      movedAny = true;
    }
    changed = true;
  }
  if (changed) await hub.saveState(state);
  return movedAny;
}

/**
 * 把一批读掉的信从 cur 放回 new，交回放回了哪些（不再续接时交回 null）。同一封信只续接一次：放回过又被打断，多半是这个回合自己就
 * 把机器顶到了内存回收，再放回只会一遍遍花钱重跑。这时主任务转 blocked，写信给站主，附两次的回合号（工人的阶段由调用方标 failed）。
 */
export async function requeueLetters(hub: Hub, ts: PyDict, events: readonly PyValue[], agent: string, key: string, names: readonly PyValue[],
  turn: PyValue, label: string): Promise<PyValue[] | null> {
  const task = pyItem(ts, "task");
  const before = events.filter((event) => pyEq(pyGet(event, "event"), "letters.requeued") && pyEq(pyGet(event, "task"), task)
    && pyEq(pyGet(event, "agent"), agent) && pyIter(or(pyGet(event, "letters"), [])).some((item) => names.some((name) => pyEq(item, name))));
  const last = before.at(-1);
  if (last !== undefined) {
    const turns = [pyGet(last, "turn"), turn].map((item) => (pyTruthy(item) ? pyStrValue(item) : "没跑完")).join("、");
    const text = `${label}（${agent}）的回合续接之后又被打断（回合 ${turns}），内核不再放回它的信${agent === COORDINATOR ? "" : "，阶段已标为 failed"}。`
      + `多半是回合里跑的东西把机器顶到了内存回收：查明之后用 kit_hub.py send ${pyStrValue(task)} --type 回复 恢复，再让协调人重新安排`;
    const notes = pyItem(ts, "notes");
    if (!Array.isArray(notes)) throw new PyCrash("AttributeError", `'${pyTypeName(notes)}' object has no attribute 'append'`);
    notes.push(new Map<string, PyValue>([["at", utcNow()], ["text", text]]));
    ts.set("status", "blocked");
    await hub.appendEvent("letters.requeue_refused", [["task", task], ["agent", agent], ["key", key], ["letters", [...names]],
      ["turns", [pyGet(last, "turn"), turn]]]);
    await hub.deliver(letterMeta(KERNEL, OWNER, task, "阻塞"), new Map<string, PyValue>([
      ["摘要", `${label} 的回合两次被打断，内核不再续接`], ["提交", "无"], ["验证", "内核"], ["偏离", text],
      ["需协调人决定", `请站主处理后用 kit_hub.py send ${pyStrValue(task)} --type 回复 恢复`], ["证据", ".agent/mailbox/ledger/events.jsonl（letters.requeued）"],
    ]));
    return null;
  }
  const box = hub.inbox(agent);
  const moved: PyValue[] = [];
  for (const name of names) {
    try {
      pyRename(purePathStr(dirname(box), "cur", pyStrValue(name)), purePathStr(box, pyStrValue(name)));
      moved.push(name);
    } catch (error) {
      if (!pyCaught(error, ["OSError"])) throw error; // 挪不动：当别人已经放回了
    }
  }
  if (moved.length > 0) await hub.appendEvent("letters.requeued", [["task", task], ["agent", agent], ["key", key], ["letters", moved], ["turn", turn]]);
  return moved;
}

/**
 * 执行端读了信、阶段停在 assigned、没人在办（第 94 轮）：执行端不自己重跑（一次几十分钟、要花钱），写信给站主点明怎么接上，
 * 同一批信只报一次。执行还在跑（runner 被收掉、调度器的子进程还活着）就先不报。交回报了没有。
 */
export async function reportStrandedExec(hub: Hub, ts: PyDict, stage: PyDict, names: readonly PyValue[],
  deps: RequeueDeps = REAL_REQUEUE_DEPS): Promise<boolean> {
  if (pyEq(pyGet(stage, "stranded_notice"), [...names])) return false;
  const task = pyItem(ts, "task");
  const mark = purePathStr(execMarks(hub), `${pyStrValue(task)}.json`);
  const pid = isFile(mark) ? pyGet(loads(readText(mark) || "{}"), "pid") : null;
  if (pyTruthy(pid) && deps.pidAlive(Number(pyIntOf(pid))) !== false) return false;
  let how: string;
  try {
    const attempt = interruptedAttempt(hub, ts);
    how = `${purePathName(attempt)} 跑完了、还没有结论：用 kit_hub.py exec-recheck ${pyStrValue(task)} 重新核验（不重跑执行端）`;
  } catch (error) {
    if (!(error instanceof HubError)) throw error;
    how = `${error.message}。没开始就被打断的，用 kit_hub.py task unstick ${pyStrValue(task)} 5-exec --reason … 标成 failed，再让协调人重发开工`;
  }
  stage.set("stranded_notice", [...names]);
  await hub.appendEvent("exec.stranded", [["task", task], ["letters", [...names]]]);
  await hub.deliver(letterMeta(KERNEL, OWNER, task, "阻塞"), new Map<string, PyValue>([
    ["摘要", `${pyStrValue(task)} 的执行端读了信、没人在办（runner 被收掉了）`], ["提交", "无"], ["验证", "内核"], ["偏离", head(how, 1500)],
    ["需协调人决定", "请站主照“偏离”里写的接上"], ["证据", head(names.map((name) => pyStrValue(name)).join("、"), 600)],
  ]));
  return true;
}

/** 还有扣着、没到点的信：supervisor 与串行的 hub 不能因为空闲退出，否则到点没人放回。 */
export function lettersHeld(hub: Hub): boolean {
  return [...hub.loadState().tasks().values()].some((ts) => pyTruthy(pyGet(ts, "held")));
}

export function supervisorBusy(hub: Hub, pending: readonly PyValue[], live: PyValue): boolean {
  return pending.length > 0 || pyTruthy(live) || lettersHeld(hub);
}

/** 主任务 runner 空闲了可以退：到点由 supervisor 再起；串行的 hub 有扣着的信就不退。 */
export function runnerMayIdleExit(hub: Hub, task: string | null): boolean {
  return task !== null || !lettersHeld(hub);
}

/**
 * 有未读信（站主的信箱不算）的进行中主任务。别的主任务在等它结项的排前面（第 23 轮），其余按最早那封信的先后。
 */
export function tasksWithWork(hub: Hub): string[] {
  const tasks = hub.loadState().tasks();
  const first = new Map<string, string>();
  for (const agent of Object.keys(ROSTER)) {
    for (const path of hub.unread(agent)) {
      const main = letterMain(path);
      if (main && pyEq(pyGet(or(pyGet(tasks, main), new Map()), "status"), "active")) {
        const name = purePathName(path);
        const seen = first.get(main);
        first.set(main, seen !== undefined && cmpCodePoints(seen, name) <= 0 ? seen : name);
      }
    }
  }
  const awaited: PyValue[] = [];
  for (const ts of tasks.values()) {
    if (pyEq(pyGet(ts, "status"), "active") && !pyTruthy(pyGet(ts, "after_released"))) awaited.push(...pyIter(or(pyGet(ts, "after"), [])));
  }
  const waiting = (main: string): boolean => awaited.some((item) => pyEq(item, main));
  return [...first.keys()].sort((left, right) => (waiting(left) === waiting(right)
    ? cmpCodePoints(first.get(left) as string, first.get(right) as string) : waiting(left) ? -1 : 1));
}

export function runnerLock(hub: Hub, task: string | null): string {
  return task === null ? purePathStr(hub.root, ".runner") : purePathStr(hub.root, ".runners", task);
}

// -- 小工具（engine.ts 里有同名的几样，那边不导出） -------------------------------------------------------------------------

const head = (text: string, size: number): string => codePoints(text).slice(0, size).join("");

const or = (value: PyValue | undefined, fallback: PyValue): PyValue => (pyTruthy(value) ? value as PyValue : fallback);

/** dict.pop(key, None)。 */
function popKey(map: PyDict, key: string): PyValue {
  const value = map.has(key) ? map.get(key) as PyValue : null;
  map.delete(key);
  return value;
}

function rosterSpec(agent: string): RosterSpec {
  if (!Object.hasOwn(ROSTER, agent)) throw new PyCrash("KeyError", pyRepr(agent));
  return (ROSTER as Readonly<Record<string, RosterSpec>>)[agent] as RosterSpec;
}

function letterMeta(sender: string, to: string, taskId: PyValue, kind: string): Map<string, string> {
  return new Map([["from", sender], ["to", to], ["task-id", pyStrValue(taskId)], ["in-reply-to", "none"], ["type", kind]]);
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
