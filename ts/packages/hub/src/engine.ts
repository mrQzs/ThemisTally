// 调度循环的 Engine（迁移第 ⑤i 片）：kit_hub.py 的 Engine 全部方法，模块函数 resumed_session、release_dependents、land，常数 REDELIVER_TEXT。
// ⑤i1 是工人一侧与结项（escalate、worker_job 一族、recheck_exec、handle_pass、after_land）；⑤i2 是选信与协调人一侧（next_job、step、
// report_step_error、fail_stage、coordinator_turn、route、deliver_coordinator_letter、write_brief）。续接一族在 requeue.ts。
// deps 只给契约用（⑤i 设计稿第 2、3 节）：用例当时换掉的内层函数照记录注入，各片的 deps 原样往下传；生产调用方不传。
// 一步之内严格串行 await，次序与 Python 的同步调用一致。ts、state、回合的结果与工人的输出里，容器的取键与报错照 Python；标量照内核与
// 回合实际写出的类型（violations 是文字的列表、rate_limited_until 是整数之类），别的类型不照 Python 处理。
import { existsSync, mkdirSync, statSync } from "node:fs";
import { nowMicros, utcCompact, utcNow } from "@themis/base/clock";
import { readText, writeTextAtomic } from "@themis/base/fsutil";
import { pyCaught, pyExceptionName } from "@themis/base/pyexc";
import { PyCrash, pyGet, pyIntOf, pyItem, pyIter, pyLenValue, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { purePathName, purePathStr } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyRstrip, pySplit, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { pathArg } from "@themis/dispatcher/evidence";
import { DispatchError } from "@themis/dispatcher/repo";
import { acceptContract, acceptGatePre } from "./accept.ts";
import {
  AUTO_JEV, BUSY_GUARD, COORDINATOR, EXIT_USAGE, FIELDS, INFO_TYPES, INPUT_FILE_LIMIT, KERNEL, MAX_STAGE_REWORKS, OWNER, PAUSE_TYPES, ROSTER,
  type RosterSpec, STAGE_WORKER, VERDICTS, WORKER_RETRIES_AFTER_TIMEOUT, WORKERS,
} from "./constants.ts";
import { dodCoverageProblems, externalFactProblems, unverifiedFacts } from "./contract.ts";
import { HubError } from "./errors.ts";
import { interruptedAttempt } from "./exec.ts";
import { type GatePostDeps, REAL_GATE_POST_DEPS, acceptGatePost, applyCandidate, ensureWorktree, seedWhitebox } from "./gatepost.ts";
import { removeInputs, stageInputs } from "./inputs.ts";
import { git } from "./kernel.ts";
import { type LandDeps, REAL_LAND_DEPS, finalize, landingBlockers, tidyFinished } from "./land.ts";
import { letterErrors, parseLetter, renderLetter, stageOf } from "./letters.ts";
import { DirLock, type Hub, HubState, holdLetters, keepPrevious, letterMain, releaseHeld } from "./mailbox.ts";
import { letterFromOutput, rolePrompt, turnPrompt } from "./prompt.ts";
import { EXEC_LAND_RETRY_SECONDS, LandBusy, finishExec, runExec, runJev } from "./runexec.ts";
import { REAL_SWEEP_DEPS, type SweepDeps, regressionSweep, rehearsalLetter, withSweepWindow } from "./sweep.ts";
import { guard, guardStart, hotfixReason, invalidateAfter, moveBase, renderRoutineBrief, routineMoves, stageBusy } from "./taskstate.ts";
import { TurnRunner } from "./turn.ts";

const LF = String.fromCharCode(10);

/** 第 108 轮：交付没过内核核验时，同一会话里当场重交那一回合收到的话（%s 是核验的问题，一行一条）。 */
export const REDELIVER_TEXT = `内核核验没过（交付已收到，同一会话里当场重交一次）：${LF}%s${LF}${LF}照这些改，在这一回合里重新交差。`
  + "要协调人或站主定、你自己改不了的，交“阻塞”信说明原因，不要原样重交。";

/** Engine 用到的 runner：TurnRunner.run 的签名。 */
export interface EngineRunner {
  run(agent: string, sessionKey: string, workspace: string, rolePrompt: string, prompt: string,
    retryOf?: string | null, fresh?: boolean, inputs?: string | null, sessionId?: string | null): Promise<PyDict>;
}

/** 用例当时换掉、契约照记录注入的函数，连同各片 deps 的并集；缺省是真的。Engine 调下去时把自己的 deps 原样传下去。 */
export interface EngineDeps extends SweepDeps, LandDeps, GatePostDeps {
  readonly ensureWorktree: (hub: Hub, ts: PyDict, kind: string, commit: PyValue, deps: EngineDeps) => Promise<string>;
  readonly applyCandidate: (hub: Hub, ts: PyDict, deps: EngineDeps) => Promise<string>;
  readonly seedWhitebox: (hub: Hub, ts: PyDict, workspace: string) => Promise<string | null>;
  readonly rolePrompt: (agent: string) => string;
  readonly runExec: (hub: Hub, ts: PyDict, deps: EngineDeps) => Promise<PyDict>;
  readonly runJev: (hub: Hub, ts: PyDict, suffix: string, deps: EngineDeps) => Promise<PyDict>;
  readonly finalize: (hub: Hub, ts: PyDict, deps: EngineDeps) => Promise<[boolean, string]>;
  readonly tidyFinished: (hub: Hub, ts: PyDict, reason: string, deps: EngineDeps) => Promise<string[]>;
  readonly regressionSweep: (hub: Hub, ts: PyDict, deps: EngineDeps) => Promise<[boolean, string]>;
  /** ⑤i2：step 每一步先放回到点的扣信（4778 的 hold_until_called 换掉它）。 */
  readonly releaseHeld: (hub: Hub) => Promise<string[]>;
  /** INPUT_FILE_LIMIT（inputs_fixture 改成 64）：交给 stageInputs 的 options.limit。 */
  readonly inputFileLimit: number;
}

export const REAL_ENGINE_DEPS: EngineDeps = {
  ...REAL_GATE_POST_DEPS,
  ...REAL_LAND_DEPS,
  ...REAL_SWEEP_DEPS,
  ensureWorktree: (hub, ts, kind, commit, deps) => ensureWorktree(hub, ts, kind, commit, deps),
  applyCandidate: (hub, ts, deps) => applyCandidate(hub, ts, deps),
  seedWhitebox: (hub, ts, workspace) => seedWhitebox(hub, ts, workspace),
  rolePrompt: (agent) => rolePrompt(agent),
  runExec: (hub, ts, deps) => runExec(hub, ts, deps),
  runJev: (hub, ts, suffix, deps) => runJev(hub, ts, suffix, deps),
  finalize: (hub, ts, deps) => finalize(hub, ts, deps),
  tidyFinished: (hub, ts, reason, deps) => tidyFinished(hub, ts, reason, deps),
  regressionSweep: (hub, ts, deps) => regressionSweep(hub, ts, deps),
  releaseHeld: (hub) => releaseHeld(hub),
  inputFileLimit: INPUT_FILE_LIMIT,
};

/** load_state 读出来的（三方合并写），或者用例手搭的字典（整份写）。 */
export type StateLike = HubState | PyDict;

/** land 用到的那两个方法：用例可以给一个只有这两个方法的假 Engine（4001）。 */
export interface Landing {
  handlePass(state: StateLike, meta: ReadonlyMap<string, string>): Promise<void>;
  afterLand(main: string): Promise<void>;
}

export class Engine implements Landing {
  readonly hub: Hub;
  runner: EngineRunner;
  /** 第 20 轮：每个主任务一个 runner 进程，只办这个主任务的信。 */
  readonly onlyTask: string | null;
  readonly deps: EngineDeps;

  constructor(hub: Hub, runner: EngineRunner | null = null, onlyTask: string | null = null, deps: EngineDeps = REAL_ENGINE_DEPS) {
    this.hub = hub;
    this.runner = runner ?? new TurnRunner(hub);
    this.onlyTask = onlyTask;
    this.deps = deps;
  }

  // -- 选下一件事（⑤i2） ----------------------------------------------------------------------------------------------------
  /** 最早那封未读信属于谁：协调人交回它的全部未读信；工人只交回与最早那封同一个阶段任务的。 */
  nextJob(): [string, string[]] | null {
    let best: [string, string, string[]] | null = null;
    for (const agent of Object.keys(ROSTER)) {
      let letters = this.hub.unread(agent);
      if (this.onlyTask !== null) letters = letters.filter((path) => letterMain(path) === this.onlyTask);
      const first = letters[0];
      if (first !== undefined && (best === null || cmpCodePoints(purePathName(first), best[1]) < 0)) best = [agent, purePathName(first), letters];
    }
    if (best === null) return null;
    const [agent, , letters] = best;
    if (agent === COORDINATOR) return [agent, letters];
    const taskIdOf = (path: string): string => parseLetter(readText(path))[0].get("task-id") ?? "";
    const taskId = taskIdOf(letters[0] as string);
    return [agent, letters.filter((path) => taskIdOf(path) === taskId)];
  }

  async step(): Promise<boolean> {
    await this.deps.releaseHeld(this.hub);
    const job = this.nextJob();
    if (job === null) return false;
    const [agent, paths] = job;
    const state = this.hub.loadState();
    try {
      if (agent === COORDINATOR) await this.coordinatorTurn(state, paths);
      else await this.workerJob(state, agent, paths);
    } catch (error) {
      await this.reportStepError(agent, paths, error);
    }
    return true;
  }

  /**
   * 第 26 轮：回合先收信、后干活，中途出了意外，信已经挪进 cur、没人再办，这个主任务就悄悄停住了。写一封阻塞信给站主：哪几封信读了没办、
   * 错在哪，站主修好后回一封“回复”就能接着走。“偏离”是堆栈的最后 1500 个字符：这里写 JS 的栈帧，最后一行照 Python 的 format_exception
   * 写成“类名: 文字”、结尾带换行，按码点切（⑤i 设计稿第 7 节，契约只比最后一行）。
   */
  async reportStepError(agent: string, paths: readonly string[], error: unknown): Promise<void> {
    const names = paths.map((path) => purePathName(path));
    const mains: (string | null)[] = [];
    for (const path of paths) { // 信多半已经挪进 cur
      const copy = existsSync(path) ? path : purePathStr(this.hub.inbox(agent, "cur"), purePathName(path));
      try {
        mains.push(letterMain(copy));
      } catch (caught) {
        if (!(caught instanceof HubError)) throw caught;
        mains.push(null);
      }
    }
    const main = mains.find((item) => item) || "T000";
    const [kind, qualified] = pyErrorNames(error);
    const text = error instanceof Error ? error.message : String(error);
    const frames = (error instanceof Error ? error.stack ?? "" : "").split(LF).filter((line) => line.startsWith("    at "));
    const detail = codePoints([...frames, text ? `${qualified}: ${text}` : qualified].join(LF) + LF).slice(-1500).join("");
    await this.hub.appendEvent("step.error", [["agent", agent], ["letters", names], ["error", `${kind}: ${text}`]]);
    if (agent === COORDINATOR) { // 第 94 轮：这几封信下面写信报给了站主，“在办”标记清掉，不再放回
      const state = this.hub.loadState();
      if (popKey(dict(pyGet(state.tasks(), main, new Map()), "pop"), "coordinator_turn") !== null) await this.hub.saveState(state);
    }
    const stuck = await this.failStage(agent, paths, `回合出错：${kind}: ${head(text, 200)}`);
    await this.hub.deliver(letterMeta(KERNEL, OWNER, main, "阻塞"), new Map<string, PyValue>([
      ["摘要", `${agent} 的回合出了意外，这几封信读了还没办：${head(names.join("、"), 600)}`], ["提交", "无"], ["验证", `${kind}: ${head(text, 300)}`],
      ["偏离", detail],
      ["需协调人决定", `请站主看错误、处理好之后用 kit_hub.py send ${main} --type 回复 恢复${stuck ? `（阶段 ${stuck} 已标成 failed，协调人可以照原信重新开工或返工）` : ""}`],
      ["证据", ".agent/mailbox/ledger/events.jsonl（step.error）"],
    ]));
  }

  /**
   * 第 35 轮：工人的回合出了意外，阶段还停在 assigned，站主回信后协调人重发开工，内核以“已经开工、还没交付”拒收。标成 failed，开工、返工都能
   * 再发。交回标了哪个阶段。
   */
  async failStage(agent: string, paths: readonly string[], note: string): Promise<string | null> {
    if (agent === COORDINATOR) return null;
    const state = this.hub.loadState();
    for (const path of paths) {
      const copy = existsSync(path) ? path : purePathStr(this.hub.inbox(agent, "cur"), purePathName(path));
      const [main, suffix] = existsSync(copy) ? stageOf(parseLetter(readText(copy))[0].get("task-id") ?? "") : [null, null];
      const ts = pyGet(state.tasks(), main || "") as PyDict | null;
      if (ts !== null && suffix && stageBusy(pyItem(pyItem(ts, "stages"), suffix))) {
        dict(pyItem(pyItem(ts, "stages"), suffix), "update").set("status", "failed").set("note", note);
        await this.hub.saveState(state);
        return `${main}-${suffix}`;
      }
    }
    return null;
  }

  // -- 协调人（⑤i2） --------------------------------------------------------------------------------------------------------
  /** 协调人一个回合只处理一个主任务的信（最早那封所属的主任务）；别的主任务的信留在 new 里。 */
  async coordinatorTurn(state: StateLike, paths: readonly string[]): Promise<void> {
    const mains = paths.map((path) => stageOf(parseLetter(readText(path))[0].get("task-id") ?? "")[0]);
    if (mains.length === 0) indexError();
    const main = mains[0] as string | null;
    const tasks = tasksOf(state);
    if (main === null || !contains(tasks, main)) {
      const taken = await this.hub.take(paths[0] as string);
      await this.hub.appendEvent("coordinator.skipped", [["reason", "信里没有登记过的主任务"], ["letters", [purePathName(taken)]]]);
      return;
    }
    const mine = paths.filter((_path, index) => mains[index] === main);
    const texts = mine.map((path) => readText(path));
    for (const path of mine) await this.hub.take(path);
    const names = mine.map((path) => purePathName(path));
    let ts = pyItem(tasks, main) as PyDict;
    if (!pyEq(pyGet(ts, "status"), "active")) {
      await this.hub.appendEvent("coordinator.skipped", [["reason", `主任务 ${main} 状态为 ${pyStrValue(pyGet(ts, "status"))}`], ["letters", names]]);
      return;
    }
    let routingNote: string | null = null;
    if (rosterSpec(COORDINATOR).routing === "kernel" && !pyTruthy(pyGet(ts, "coordinator_resume"))) {
      const [routed, note] = await this.route(state, ts, mine, texts);
      if (routed) return;
      routingNote = note;
    }
    const workspace = await this.deps.ensureWorktree(this.hub, ts, "base", pyItem(ts, "base_head"), this.deps);
    // 第 94 轮：“在办”标记，回合办完（三个出口）或进程内出了意外（report_step_error）时清掉。runner 被收掉，标记就留着：
    // requeue_interrupted 拿得到锁、看到它，就把这几封信放回去
    ts.set("coordinator_turn", new Map<string, PyValue>([["letters", names], ["at", utcCompact()]]));
    const resume = popKey(ts, "coordinator_resume");
    await this.hub.saveState(state);
    const sessionId = resumedSession(this.hub, COORDINATOR, resume, workspace);
    const [inputs] = await this.stage(ts, `${main}-${utcCompact()}`); // 第 88 轮
    let turn: PyDict;
    try {
      let prompt = turnPrompt(this.hub, ts, COORDINATOR, main, texts, workspace, null, inputs, withSession(resume, sessionId), routingNote);
      turn = await this.runner.run(COORDINATOR, main, workspace, this.deps.rolePrompt(COORDINATOR), prompt, null, resume !== null && sessionId === null,
        inputs, sessionId);
      if (pyItem(turn, "output") === null && !pyTruthy(pyItem(turn, "violations")) && !pyTruthy(pyGet(turn, "api_error"))) {
        prompt = turnPrompt(this.hub, ts, COORDINATOR, main, texts, workspace, pyItem(turn, "output_error"), inputs, null, routingNote);
        turn = await this.runner.run(COORDINATOR, main, workspace, this.deps.rolePrompt(COORDINATOR), prompt, pyItem(turn, "turn_id") as string, false,
          inputs, null);
      }
    } finally {
      removeInputs(inputs);
    }
    const current = this.hub.loadState();
    ts = pyItem(current.tasks(), main) as PyDict;
    if (pyTruthy(pyGet(turn, "rate_limited_until")) && !pyTruthy(pyItem(turn, "violations"))) {
      popKey(ts, "coordinator_turn");
      await holdLetters(this.hub, ts, COORDINATOR, names, Number(pyItem(turn, "rate_limited_until")), null, pyStrValue(pyItem(turn, "turn_id")));
      await this.hub.saveState(current);
      return;
    }
    if (pyTruthy(pyItem(turn, "violations")) || pyItem(turn, "output") === null) {
      popKey(ts, "coordinator_turn");
      const reason = pyIter(pyItem(turn, "violations")).map((item) => pyStrValue(item)).join("；") || problemText(pyItem(turn, "output_error")) || "没有输出";
      await this.escalate(ts, `协调人回合作废：${reason}（回合 ${pyStrValue(pyItem(turn, "turn_id"))}）`);
      await this.hub.saveState(current);
      return;
    }
    const output = pyItem(turn, "output");
    if (typeof pyGet(output, "state") === "string") writeTextAtomic(purePathStr(this.hub.taskDir(main), "state.md"), pyGet(output, "state") as string);
    const rejected: string[] = [];
    let delivered = 0;
    for (const item of pyIter(or(pyGet(output, "letters"), []))) {
      const reason = await this.deliverCoordinatorLetter(current, item);
      if (reason && pyTruthy(resume) && (pyTruthy(pyGet(resume, "turn")) || pyTruthy(pyGet(resume, "routing"))) && reason.includes(BUSY_GUARD)) {
        // 第 94 轮：上一回合跑完了、投递做到一半，续接的回合照原样重发了已经投递的开工、返工：不算协调人出错、不发核验信
        await this.hub.appendEvent("coordinator.resent", [["task", main], ["to", pyGet(item, "to")], ["task_id", pyGet(item, "task_id")]]);
      } else if (reason) {
        rejected.push(`${pyStrValue(pyGet(item, "type"))} → ${pyStrValue(pyGet(item, "to"))}（${pyStrValue(pyGet(item, "task_id"))}）：${reason}`);
      } else {
        delivered += 1;
      }
    }
    ts = pyItem(current.tasks(), main) as PyDict;
    popKey(ts, "coordinator_turn");
    popKey(ts, "routed"); // 第 112 轮：内核代办记录这一回合看过了
    if (rejected.length > 0) {
      const count = pyIntOf(pyGet(ts, "coordinator_rejections", 0n)) + 1n;
      ts.set("coordinator_rejections", count);
      if (count >= 3n) {
        await this.escalate(ts, `协调人连续 ${count} 个回合的信被内核拒收：${LF}${rejected.join(LF)}`);
      } else {
        await this.hub.deliver(letterMeta(KERNEL, COORDINATOR, main, "核验"), new Map<string, PyValue>([
          ["摘要", `你上一回合有 ${rejected.length} 封信被内核拒收，${delivered} 封已投递`], ["提交", "无"], ["验证", "内核按状态机核对"],
          ["偏离", head(rejected.join(LF), 1500)], ["需协调人决定", "按“内核此刻允许的下一步”改发"], ["证据", pyItem(turn, "turn_dir")],
        ]));
      }
    } else {
      ts.set("coordinator_rejections", 0n);
    }
    await this.hub.saveState(current);
  }

  /**
   * 第 112 轮：这批信全是例行信、每一步都过 guard 时，由内核代办，不起协调人的回合。交回（代办了没有, 给协调人的话）：内核想代办、却被
   * guard 或“最后一次返工留给协调人”拦下时，告诉协调人本想发什么、为什么没发。信已经由调用方 take 走；中途被收掉时，“在办”标记（带 routing）
   * 让 requeue_interrupted 把信放回去，下一回合直接起协调人的续接回合。
   */
  async route(state: StateLike, ts: PyDict, paths: readonly string[], texts: readonly string[]): Promise<[boolean, string | null]> {
    const [moves, why] = routineMoves(texts);
    if (why) return [false, `这批信不是例行流转：${why}`]; // 第 117 轮：叫醒协调人时说清为什么
    const items: PyDict[] = [];
    for (const move of moves) {
      const suffix = pyStrValue(pyItem(move, "suffix"));
      const worker = STAGE_WORKER[suffix] as string;
      const taskId = `${pyStrValue(pyItem(ts, "task"))}-${suffix}`;
      const kind = pyStrValue(pyItem(move, "type"));
      let reason = guard(ts, new Map([["type", kind], ["to", worker], ["task-id", taskId]]));
      const done = pyIntOf(pyGet(or(pyGet(ts, "reworks"), new Map()), suffix, 0n));
      if (!reason && kind === "返工" && suffix !== "5-exec" && done + 1n >= BigInt(MAX_STAGE_REWORKS)) {
        // themistally-15 指出：代办与协调人共用返工计数，机械核验没过时内核会把返工一路用完
        reason = `这一步是 ${suffix} 的最后一次返工（已经返工 ${done} 次），留给协调人定：返工、热修补还是问站主`;
      }
      if (reason) return [false, `内核本想代办“${kind} → ${worker}（${taskId}）”，没有发：${reason}`];
      items.push(new Map<string, PyValue>([["to", worker], ["type", pyItem(move, "type")], ["task_id", taskId], ["in_reply_to", pyItem(move, "reply_to")],
        ["摘要", `例行流转（内核代办）：${pyStrValue(pyItem(move, "from_task"))} 之后的下一步`], ["证据", `任务书：.agent/mailbox/tasks/${taskId}/brief.md`],
        ["brief", renderRoutineBrief(this.hub.repo, ts, move)]]));
    }
    const names = paths.map((path) => purePathName(path));
    ts.set("coordinator_turn", new Map<string, PyValue>([["letters", names], ["at", utcCompact()], ["routing", true]]));
    await this.hub.saveState(state);
    const doneMoves: string[] = [];
    let refused: string | null = null;
    for (const item of items) {
      const reason = await this.deliverCoordinatorLetter(state, item, KERNEL);
      const shown = `${pyStrValue(pyItem(item, "type"))} → ${pyStrValue(pyItem(item, "to"))}（${pyStrValue(pyItem(item, "task_id"))}）`;
      if (reason) { // 前一封改了状态、后一封撞上 guard（同一批里几步互相影响）：剩下的交给协调人
        refused = `内核代办到一半，“${shown}”没有发：${reason}`;
        break;
      }
      doneMoves.push(shown);
    }
    popKey(ts, "coordinator_turn");
    if (doneMoves.length > 0) { // 投出去的几步都记下，代办到一半时协调人也看得到（themistally-15 指出）
      if (!ts.has("routed")) ts.set("routed", []);
      appendTo(ts.get("routed") as PyValue, new Map<string, PyValue>([["at", utcNow()], ["letters", names], ["moves", doneMoves]]));
      await this.hub.appendEvent("route.kernel", [["task", pyItem(ts, "task")], ["letters", names], ["moves", doneMoves], ["partial", refused !== null]]);
    }
    await this.hub.saveState(state);
    return [refused === null, refused];
  }

  /**
   * 协调人一封信的投递：形状、guard、brief 落盘、返工计数、热修补、站主指定的返工。第 112 轮起内核代办例行流转也走这里（sender 是内核）。
   * 交回拒收的原因，投递了交回 null。
   */
  async deliverCoordinatorLetter(state: StateLike, item: PyValue, sender: string = COORDINATOR): Promise<string | null> {
    if (!(item instanceof Map)) return "信不是对象";
    const text = (key: string, fallback: string): string => pyStrValue(or(pyGet(item, key), fallback));
    const meta = new Map<string, string>([["from", sender], ["to", text("to", "")], ["task-id", text("task_id", "")],
      ["in-reply-to", text("in_reply_to", "none")], ["type", text("type", "")]]);
    const fields = new Map<string, PyValue>(FIELDS.map((key) => [key, pyStrip(pyStrValue(pyGet(item, key, ""))) || "无"]));
    const bodyLines = pySplitlines(renderLetter(new Map([...meta, ["msg-id", "x"]]), fields)).length - 8;
    const errors = letterErrors(meta, fields, bodyLines);
    if (errors.length > 0) return errors.join("；");
    const [main, suffix] = stageOf(meta.get("task-id"));
    const ts = pyGet(tasksOf(state), main || "") as PyDict | null;
    const reason = guard(ts, meta);
    if (reason) {
      await this.hub.appendEvent("letter.rejected", [["sender", sender], ["to", meta.get("to") as string], ["type", meta.get("type") as string],
        ["task_id", meta.get("task-id") as string], ["reason", reason]]);
      return reason;
    }
    const kind = meta.get("type") as string;
    const to = meta.get("to") as string;
    if ((kind === "开工" || kind === "返工") && WORKERS.includes(to)) {
      const live = ts as PyDict; // guard 放行了开工、返工，主任务一定登记过
      const stage = suffix as string;
      const brief = pyGet(item, "brief");
      if (rosterSpec(to).adapter === "claude" || rosterSpec(to).adapter === "pi") {
        if (typeof brief !== "string" || !pyStrip(brief)) return "开工、返工要附 brief（下一阶段任务书的 Markdown 全文）";
        this.writeBrief(meta.get("task-id") as string, brief);
      }
      if (kind === "返工" && stage === "3-gate-pre" && hotfixReason(live)) {
        // 第 108 轮（themistally-15 指出）：热修补交付提交了、却没锁定（baseline 没过）时 ts.oracle.sha 是那个失败的提交；再发返工要沿用
        // 最早那份，一审拿到的差异才对着执行端用过的基准测试
        const earlier = pyGet(or(pyGet(live, "hotfix"), new Map()), "previous_oracle");
        const previous = pyTruthy(earlier) ? earlier : pyGet(pyItem(live, "oracle"), "sha"); // 照 Python 的 or：用到时才读 oracle
        const hotfix = new Map<string, PyValue>([["reason", hotfixReason(live)], ["at", utcNow()], ["previous_oracle", previous]]);
        live.set("hotfix", hotfix);
        if (pyTruthy(pyGet(pyItem(live, "exec"), "gate_claims"))) { // 门禁端重新交付时 ts["exec"] 会清空：原话与 attempt 先存下
          hotfix.set("claims", pyItem(pyItem(live, "exec"), "gate_claims")).set("run_dir", pyGet(pyItem(live, "exec"), "run_dir"));
        }
        await this.hub.appendEvent("hotfix.started", [["task", pyItem(live, "task")], ["reason", pyItem(hotfix, "reason")]]);
      }
      if (kind === "返工" && pyEq(pyGet(or(pyGet(live, "owner_rework"), new Map()), "suffix"), stage)) {
        const record = popKey(live, "owner_rework") as PyDict;
        if (pyTruthy(pyGet(record, "text"))) {
          const words = new Map<string, PyValue>([["msg", pyItem(record, "msg")], ["text", popKey(record, "text")]]);
          dict(pyItem(pyItem(live, "stages"), stage), "[]=").set("owner_text", words);
        }
        await this.hub.appendEvent("owner_rework.used", [["task", pyItem(live, "task")], ...[...record].map(([key, value]) => [String(key), value] as const)]);
      } else if (kind === "返工") { // 站主指定的不算：站主是最终拍板人
        if (!live.has("reworks")) live.set("reworks", new Map());
        const reworks = dict(live.get("reworks") as PyValue, "get"); // reworks[suffix] = reworks.get(suffix, 0) + 1：先算右边
        reworks.set(stage, pyIntOf(pyGet(reworks, stage, 0n)) + 1n);
      }
      const target = dict(pyItem(pyItem(live, "stages"), stage), "[]=");
      target.set("status", "assigned");
      target.set("assigned_at", utcNow());
      target.set("kind", kind);
      target.delete("last_letter"); // stage_busy 靠它认旧状态里停下的阶段
    }
    await this.hub.deliver(meta, fields);
    await this.hub.saveState(state);
    return null;
  }

  writeBrief(taskId: string, brief: string): void {
    const directory = this.hub.taskDir(taskId);
    mkdirSync(directory, { recursive: true });
    const current = purePathStr(directory, "brief.md");
    keepPrevious(current);
    writeTextAtomic(current, `${pyRstrip(brief)}${LF}`);
  }

  /**
   * 协调人自己出了问题（回合作废，或连续三个回合的信都被拒收）：主任务转为 blocked，写信给站主。
   * 站主发“回复”之后恢复为 active。
   */
  async escalate(ts: PyDict, text: string): Promise<void> {
    appendTo(pyItem(ts, "notes"), new Map<string, PyValue>([["at", utcNow()], ["text", head(text, 2000)]]));
    ts.set("status", "blocked");
    const task = pyItem(ts, "task");
    await this.hub.deliver(letterMeta(KERNEL, OWNER, task, "阻塞"), new Map<string, PyValue>([
      ["摘要", head(firstLine(text), 200)], ["提交", "无"], ["验证", "内核"], ["偏离", head(text, 1500)],
      ["需协调人决定", `请站主处理后用 kit_hub.py send ${pyStrValue(task)} --type 回复 恢复`], ["证据", ".agent/mailbox/ledger/events.jsonl"],
    ]));
  }

  // -- 工人 -----------------------------------------------------------------
  async workerJob(state: StateLike, agent: string, paths: readonly string[]): Promise<void> {
    const texts = paths.map((path) => readText(path));
    const metas = texts.map((text) => parseLetter(text)[0]);
    const first = metas[0];
    if (first === undefined) throw new PyCrash("IndexError", "list index out of range");
    const taskId = first.get("task-id") ?? "";
    const [main, suffix] = stageOf(taskId);
    let ts = pyGet(tasksOf(state), main || "") as PyDict | null;
    const taken: string[] = [];
    for (const path of paths) taken.push(await this.hub.take(path));
    const kinds = new Set(metas.map((meta) => meta.get("type") ?? null));
    if (ts === null || suffix === null || [...kinds].every((kind) => kind !== null && (INFO_TYPES as readonly string[]).includes(kind))) {
      await this.hub.appendEvent("worker.not_woken", [["agent", agent], ["task_id", taskId], ["kinds", sortedStrings(kinds)],
        ["letters", taken.map((path) => purePathName(path))]]);
      return;
    }
    // 第 93、94 轮：被打断的阶段，信由 requeue_interrupted 放回（JEV 没有会话，照常重跑）；执行端的报告用过了
    const stageNow = dict(pyItem(pyItem(ts, "stages"), suffix), "pop");
    const resume = popKey(stageNow, "resume");
    popKey(stageNow, "stranded_notice");
    const adapter = rosterSpec(agent).adapter;
    if (adapter === "dispatcher") {
      let fields: PyDict;
      try {
        fields = await this.deps.runExec(this.hub, ts, this.deps);
      } catch (error) {
        if (!(error instanceof LandBusy)) throw error;
        const until = Math.floor(nowMicros() / 1_000_000) + EXEC_LAND_RETRY_SECONDS;
        await holdLetters(this.hub, ts, agent, taken.map((path) => purePathName(path)), until, suffix, "",
          `落地锁被占（${head(error.message, 160)}）`);
        await this.hub.saveState(state);
        return;
      }
      const rehearsed = await this.deps.rehearseLanding(this.hub, ts); // 执行窗口外：不挡别的主任务落地
      if (rehearsed !== null) {
        fields.set("落地预演", rehearsed[0] ? `通过：${rehearsed[1]}` : `没过，已写信给站主，站主处理之前别结项：${head(rehearsed[1], 600)}`);
        if (!rehearsed[0]) await rehearsalLetter(this.hub, ts, rehearsed[1], "执行端交付时");
      }
      await this.finishKernelStage(state, ts, agent, suffix, fields, pyGet(pyItem(ts, "exec"), "check_ok", false));
      return;
    }
    if (adapter === "jev") {
      const fields = await this.deps.runJev(this.hub, ts, suffix, this.deps);
      await this.finishKernelStage(state, ts, agent, suffix, fields, true);
      return;
    }
    const workspace = await this.stageWorkspace(ts, agent, suffix);
    await this.hub.saveState(state);
    const [inputs] = await this.stage(ts, `${taskId}-${utcCompact()}`); // 第 88 轮
    let turn: PyDict;
    let error: string | null;
    let timeouts: number;
    try {
      [turn, error, timeouts] = await this.workerTurns(agent, taskId, ts, texts, workspace, kinds, inputs, resume);
    } finally {
      removeInputs(inputs);
    }
    let retried: { first: string; firstTurn: PyValue } | null = null; // 第 108 轮：核验没过、在同一会话里当场重交过一次
    let current: StateLike = state;
    let meta = new Map<string, string>();
    let fields: PyDict = new Map();
    let problems: string[] = [];
    let output: PyValue = null;
    for (;;) {
      current = this.hub.loadState();
      ts = pyItem(tasksOf(current), main as string) as PyDict;
      if (pyTruthy(pyGet(turn, "rate_limited_until")) && !pyTruthy(pyItem(turn, "violations")) && retried === null) {
        await holdLetters(this.hub, ts, agent, taken.map((path) => purePathName(path)), Number(pyItem(turn, "rate_limited_until")), suffix,
          pyStrValue(pyItem(turn, "turn_id")));
        await this.hub.saveState(current);
        return;
      }
      if (pyTruthy(pyItem(turn, "violations")) || error || pyTruthy(pyGet(turn, "rate_limited_until"))) {
        break; // 回合作废（重交的回合撞上限流也算：放回原信会从头重跑一整个回合）
      }
      output = pyItem(turn, "output");
      const directory = this.hub.taskDir(taskId);
      if (typeof pyGet(output, "report") === "string") {
        keepPrevious(purePathStr(directory, "report.md")); // 返工前的报告留着：上一轮的意见不丢
        writeTextAtomic(purePathStr(directory, "report.md"), pyGet(output, "report") as string);
      }
      if (typeof pyGet(output, "state") === "string") writeTextAtomic(purePathStr(directory, "state.md"), pyGet(output, "state") as string);
      [meta, fields] = letterFromOutput(agent, taskId, output);
      problems = [];
      if (isDelivery(meta.get("type"))) problems = await this.verifyDelivery(ts, agent, suffix, output, fields);
      if (problems.length === 0 || retried !== null) break;
      // 摘要压成一行：derive-json 的报错是多行的，信的正文有行数上限
      retried = { first: head(pySplit(problems.join("；")).join(" "), 300), firstTurn: pyItem(turn, "turn_id") };
      [turn, error] = await this.redeliver(current, ts, agent, taskId, suffix, texts, workspace, problems, turn);
    }
    if (pyTruthy(pyItem(turn, "violations")) || error || pyTruthy(pyGet(turn, "rate_limited_until"))) {
      await this.voided(current, ts, agent, taskId, suffix, turn, error, timeouts, retried);
      return;
    }
    if (retried !== null) {
      await this.hub.appendEvent("delivery.retried", [["task", pyItem(ts, "task")], ["stage", suffix], ["first", retried.first],
        ["first_turn", retried.firstTurn], ["turn", pyItem(turn, "turn_id")], ["kind", pyItem(meta, "type")],
        ["ok", isDelivery(meta.get("type")) && problems.length === 0]]);
      fields.set("验证", `（第一次交付内核核验没过：${head(retried.first, 200)}；同一会话里当场重交了一次）${pyStrValue(pyGet(fields, "验证", ""))}`);
    }
    const stage = dict(pyItem(pyItem(ts, "stages"), suffix), "[]=");
    stage.set("fields", fields);
    stage.delete("timed_out"); // 这一回合交出了信：上一回合超时的提醒用过了
    stage.set("last_letter", pyItem(meta, "type")); // 合同端发“阻塞”指出规划有缺陷时，协调人能退回规划端（第 15 轮）
    if (isDelivery(meta.get("type"))) {
      if (problems.length > 0) {
        // 第 112 轮：核验的全文另存（信里截到 1200 字、note 截到 600 字），内核写返工的任务书照它的原话
        stage.set("status", "failed").set("note", head(problems.join("；"), 600)).set("problems", problems).set("redelivered", retried !== null);
        fields.set("内核核验", `未通过${retried !== null ? "（同一会话里已经当场重交过一次）" : ""}：${head(problems.join("；"), 1200)}`);
      } else {
        stage.set("status", "delivered").set("note", "").set("delivered_at", utcNow());
        for (const key of ["owner_text", "problems", "redelivered"]) stage.delete(key); // 站主的返工要求、上一次核验的原话都办完了
        fields.set("内核核验", "通过");
        invalidateAfter(ts, suffix);
        await this.afterDelivery(ts, suffix, fields, output);
      }
    } else if ((PAUSE_TYPES as readonly string[]).includes(meta.get("type") ?? "")) {
      stage.set("status", "paused").set("paused_at", utcNow());
    }
    await this.hub.saveState(current);
    await this.hub.deliver(meta, letterFields(fields));
    if (pyEq(pyItem(stage, "status"), "delivered")) await this.autoJev(current, ts, suffix);
  }

  /** worker_job 里回合作废的那一段：阶段标 failed，接口报错交给站主，其余写阻塞信给协调人。 */
  private async voided(state: StateLike, ts: PyDict, agent: string, taskId: string, suffix: string, turn: PyDict, error: string | null,
    timeouts: number, retried: { first: string; firstTurn: PyValue } | null): Promise<void> {
    const violations = pyIter(pyItem(turn, "violations")).map((item) => pyStrValue(item)).join("；");
    let reason = violations || error || `接口限流（到 ${pyStrValue(pyItem(turn, "rate_limited_until"))}）`;
    if (retried !== null) {
      await this.hub.appendEvent("delivery.retried", [["task", pyItem(ts, "task")], ["stage", suffix], ["first", retried.first],
        ["first_turn", retried.firstTurn], ["turn", pyItem(turn, "turn_id")], ["ok", false]]);
      reason += `（这是核验没过之后的当场重交；第一次核验：${retried.first}）`;
    }
    // timed_out：下一回合的输入提醒它工作目录里的改动还在，接着做（第 53 轮）
    dict(pyItem(pyItem(ts, "stages"), suffix), "update").set("status", "failed").set("note", `回合作废：${reason}`)
      .set("timed_out", pyTruthy(pyGet(turn, "timed_out")));
    if (pyTruthy(pyGet(turn, "api_error")) && !pyTruthy(pyItem(turn, "violations")) && !pyTruthy(pyGet(turn, "rate_limited_until"))) {
      // 环境问题（例如 2026-10-19 旧机器上的 403）：协调人也会遇到同样的错，直接交给站主。带着 rate_limited_until 走到这里的只有
      // 当场重交的回合（第 108 轮）：限流过后协调人照常能返工，交给它
      await this.escalate(ts, `${agent} 的回合遇到模型接口报错，阶段已标为 failed：${pyStrValue(pyItem(turn, "api_error"))}（回合 ${pyStrValue(pyItem(turn, "turn_id"))}）`);
      await this.hub.saveState(state);
      return;
    }
    await this.hub.saveState(state);
    // 第 83 轮：之前确实超时过（timeouts）才这样说；“格式错、续上的回合超时”只超时了一次
    const decide = pyTruthy(pyGet(turn, "timed_out")) && timeouts
      ? "超时之后续接的回合又超时了，内核没有再续：发“返工”会开新会话，只带任务书、state 与返工信；返工信里写清卡在哪里（阶段已标为 failed）"
      : "可以发“返工”让它重做（阶段已标为 failed）";
    await this.hub.deliver(letterMeta(KERNEL, COORDINATOR, taskId, "阻塞"), new Map<string, PyValue>([
      ["摘要", `${agent} 的回合作废，信没有投递`], ["提交", "无"], ["验证", "内核审计与校验"], ["偏离", head(reason, 1500)],
      ["需协调人决定", decide], ["证据", pyItem(turn, "turn_dir")],
    ]));
  }

  /**
   * JEV 由内核接着跑（用户 2026-10-19 同意）：上游交付通过、前置条件满足时直接调决策 API，
   * 不为它单独唤醒协调人；交付信与 JEV 的信一起进协调人信箱，协调人一个回合处理。
   */
  async autoJev(state: StateLike, ts: PyDict, suffix: string): Promise<void> {
    const jev = Object.hasOwn(AUTO_JEV, suffix) ? AUTO_JEV[suffix] as string : null;
    if (!jev || !pyTruthy(pyGet(ts, "jev_enabled")) || guardStart(ts, jev) !== null) return;
    dict(pyItem(pyItem(ts, "stages"), jev), "update").set("status", "assigned").set("assigned_at", utcNow()).set("kind", "内核自动");
    await this.hub.appendEvent("jev.auto", [["task", pyItem(ts, "task")], ["stage", jev]]);
    await this.finishKernelStage(state, ts, "jev-judge", jev, await this.deps.runJev(this.hub, ts, jev, this.deps), true);
  }

  outputProblem(agent: string, taskId: string, turn: PyDict): PyValue {
    if (pyItem(turn, "output") === null) return or(pyGet(turn, "output_error"), "没有输出");
    const [meta, fields] = letterFromOutput(agent, taskId, pyItem(turn, "output"));
    const errors = letterErrors(meta, fields, pySplitlines(renderLetter(new Map([...meta, ["msg-id", "x"]]), fields)).length - 8);
    return errors.length > 0 ? errors.join("；") : null;
  }

  async stageWorkspace(ts: PyDict, agent: string, suffix: string): Promise<string> {
    const baseHead = (): PyValue => pyItem(ts, "base_head"); // 照 Python 只在用到的分支里读
    if (suffix === "3-gate-pre") {
      const record = or(pyGet(pyItem(ts, "workspaces"), "gate"), new Map()) as PyDict;
      const path = pyGet(record, "path");
      if (pyTruthy(path) && isDirectory(pathArg(path))) {
        // 第 93 轮：也看 worktree 实际的 HEAD。内核提交了基准测试、还没写状态就被收掉（T017）：记录里还是
        // 基线，worktree 却停在基准测试的提交上，不退回的话重交时“没有新增文件”
        const headSha = pyStrip(git(["rev-parse", "HEAD"], pathArg(path), false));
        if (!pyEq(pyGet(record, "commit"), baseHead()) || (headSha && !pyEq(headSha, baseHead()))) {
          // 返工：退回基线、保留文件（基准测试回到“新增”状态），工作目录不变，门禁端的会话才能续接
          git(["reset", "-q", "--mixed", pyStrValue(baseHead())], pathArg(path));
          record.set("commit", baseHead());
        }
      }
      return this.deps.ensureWorktree(this.hub, ts, "gate", baseHead(), this.deps);
    }
    if (suffix === "4-audit-pre") {
      if (pyTruthy(pyGet(pyItem(ts, "oracle"), "sha"))) return this.deps.ensureWorktree(this.hub, ts, "gate", pyItem(pyItem(ts, "oracle"), "sha"), this.deps);
      return this.deps.ensureWorktree(this.hub, ts, "base", baseHead(), this.deps);
    }
    if (suffix === "6-gate-post" || suffix === "7-audit-post") {
      const workspace = await this.deps.applyCandidate(this.hub, ts, this.deps);
      if (suffix === "6-gate-post") await this.deps.seedWhitebox(this.hub, ts, workspace);
      return workspace;
    }
    return this.deps.ensureWorktree(this.hub, ts, "base", baseHead(), this.deps);
  }

  async verifyDelivery(ts: PyDict, agent: string, suffix: string, output: PyValue, fields: PyDict): Promise<string[]> {
    if (suffix === "1-plan") {
      return [...(pyStrip(pyStrValue(or(pyGet(output, "report"), ""))) ? [] : ["规划端的 report 为空"]), ...externalFactProblems(output)];
    }
    if (suffix === "2-contract") return acceptContract(this.hub, ts, output, this.deps);
    if (suffix === "3-gate-pre") return acceptGatePre(this.hub, ts, pathArg(pyItem(pyItem(pyItem(ts, "workspaces"), "gate"), "path")), this.deps);
    if (suffix === "6-gate-post") {
      const key = `post-${purePathName(pathArg(pyItem(pyItem(ts, "exec"), "run_dir")))}`;
      return acceptGatePost(this.hub, ts, pathArg(pyItem(pyItem(pyItem(ts, "workspaces"), key), "path")), output, this.deps);
    }
    if (suffix === "4-audit-pre" || suffix === "7-audit-post") {
      const verdict = pyGet(fields, "结论");
      if (!(VERDICTS as readonly PyValue[]).some((item) => pyEq(item, verdict))) return ["审核结论缺失"];
      if (suffix === "4-audit-pre") return dodCoverageProblems(this.hub, ts, pyStrValue(or(pyGet(output, "report"), "")));
      const defects = (): PyValue => pyGet(pyItem(ts, "gate_post"), "defects"); // 照 Python 短路：结论不是“通过”就不读
      if (pyEq(verdict, "通过") && pyTruthy(defects())) {
        return [`战后门禁举证了 ${pyLenValue(defects())} 处候选缺陷，不能判通过：成立的退回执行端，不成立（白盒测试误读合同）的退回战后门禁`];
      }
    }
    return [];
  }

  async afterDelivery(ts: PyDict, suffix: string, fields: PyDict, output: PyValue = null): Promise<void> {
    if (suffix === "1-plan") {
      const items = pyIter(or(pyGet(or(output, new Map()), "external_facts"), [])).map((item) => new Map<string, PyValue>(
        ["fact", "source", "verified"].map((key) => [key, pyStrip(pyStrValue(or(pyGet(item, key), "")))])));
      const pending = unverifiedFacts(items);
      ts.set("external_facts", new Map<string, PyValue>([["items", items], ["pending", pending], ["at", utcNow()]]));
      if (pending.length > 0) {
        // 只有站主能联网核实；核实之前 _guard_start 不放合同端开工
        const task = pyItem(ts, "task");
        const listed = pending.map((item) => {
          const source = pyItem(item, "source");
          return `- ${pyStrValue(pyItem(item, "fact"))}（出处：${pyTruthy(source) ? pyStrValue(source) : "未写"}）`;
        }).join(LF);
        await this.hub.deliver(letterMeta(KERNEL, OWNER, task, "提问"), new Map<string, PyValue>([
          ["摘要", `规划依赖 ${pending.length} 条没核实的仓库外事实，核实之前内核不放合同端开工`], ["提交", "无"],
          ["验证", "内核读规划端的 external_facts"], ["偏离", head(listed, 1500)],
          ["需协调人决定", `请站主逐条核实，用 kit_hub.py send ${pyStrValue(task)} --type 回复 --facts-checked 写明每条的结果`],
          ["证据", `.agent/mailbox/tasks/${pyStrValue(task)}-1-plan/report.md`],
        ]));
      }
    }
    if (suffix === "6-gate-post" && pyTruthy(pyGet(pyItem(ts, "gate_post"), "defects"))) {
      fields.set("内核核验", `通过：门禁端举证了 ${pyLenValue(pyItem(pyItem(ts, "gate_post"), "defects"))} 处候选缺陷，白盒测试正好红在这几条上；`
        + "变异检查没跑（候选是红的）。下一步照常开工终审，由终审裁定并一次列全阻塞项");
    }
    if (suffix === "4-audit-pre" || suffix === "7-audit-post") {
      // 不随 invalidate_after 清掉：返工之后的下一轮审核要拿上一轮的阻塞项来复核（复审封板）
      if (!ts.has("audit_history")) ts.set("audit_history", []);
      appendTo(ts.get("audit_history") as PyValue, new Map<string, PyValue>([["stage", suffix], ["verdict", pyGet(fields, "结论")],
        ["target", pyGet(fields, "退回")], ["blockers", pyGet(fields, "阻塞项", "")], ["at", utcNow()]]));
    }
    if (suffix === "4-audit-pre") {
      const auditPre = dict(pyItem(ts, "audit_pre"), "update");
      auditPre.set("verdict", pyGet(fields, "结论")).set("target", pyGet(fields, "退回"))
        .set("contract_sha256", pyGet(pyItem(ts, "contract"), "sha256")).set("oracle_sha", pyGet(pyItem(ts, "oracle"), "sha"));
      if (pyEq(pyGet(fields, "结论"), "返工")) auditPre.set("fails", pyIntOf(pyGet(auditPre, "fails", 0n)) + 1n);
    }
    if (suffix === "7-audit-post") dict(pyItem(ts, "audit_post"), "update").set("verdict", pyGet(fields, "结论")).set("target", pyGet(fields, "退回"));
  }

  async finishKernelStage(state: StateLike, ts: PyDict, agent: string, suffix: string, fields: PyDict, ok: PyValue): Promise<void> {
    const stage = dict(pyItem(pyItem(ts, "stages"), suffix), "[]=");
    stage.set("fields", fields);
    if (pyTruthy(ok)) {
      stage.set("status", "delivered").set("delivered_at", utcNow()).set("note", "");
      invalidateAfter(ts, suffix);
    } else {
      stage.set("status", "failed").set("note", head(pyStrValue(pyGet(fields, "验证", "")), 300));
      if (suffix === "5-exec") invalidateAfter(ts, suffix);
    }
    fields.set("内核核验", pyTruthy(ok) ? "通过" : "未通过（短路：只能返工给执行端）");
    await this.hub.saveState(state);
    await this.hub.deliver(letterMeta(agent, COORDINATOR, `${pyStrValue(pyItem(ts, "task"))}-${suffix}`, "交付"), letterFields(fields));
  }

  /**
   * 站主命令 exec-recheck：对最近一次 attempt 重新核验，不重跑执行端、不占新的尝试次数。
   * 只在执行阶段判为失败、attempt 目录还在时可用；结果照常作为执行端的交付信送给协调人。
   */
  async recheckExec(main: string): Promise<PyValue> {
    const state = this.hub.loadState();
    const ts = pyGet(state.tasks(), main) as PyDict | null;
    if (ts === null) throw new HubError(`没有登记主任务 ${main}`, EXIT_USAGE);
    let runDir = pyGet(pyItem(ts, "exec"), "run_dir");
    let runExit = pyGet(pyItem(ts, "exec"), "run_exit");
    const status = pyItem(pyItem(pyItem(ts, "stages"), "5-exec"), "status");
    if (pyEq(status, "assigned") && !pyTruthy(runDir)) {
      // 第 27 轮：hub 在执行端跑完、内核核验做到一半时被杀（系统内存紧张，后台进程被收掉）：
      // attempt 已经跑完，开工信早已读掉，阶段停在 assigned，没人再办。接着做核验，不重跑执行端
      const found = interruptedAttempt(this.hub, ts);
      runDir = found;
      runExit = pyGet(loads(readText(purePathStr(found, "state.json")) || "{}"), "exit_code");
      dict(pyItem(ts, "contract"), "[]=").set("dispatched", true);
      await this.hub.appendEvent("exec.resumed", [["task", main], ["run_dir", runDir]]);
    } else if (!pyEq(status, "failed") || !pyTruthy(runDir) || !isDirectory(pathArg(runDir))) {
      throw new HubError("只有执行阶段判为失败、attempt 目录还在时，或者执行被打断、停在 assigned 时，才能重新核验"
        + `（现在：${pyStrValue(status)}）`, EXIT_USAGE);
    }
    const fields = await finishExec(this.hub, ts, pathArg(runDir), runExit as bigint | null, this.deps);
    fields.set("验证", `（站主 exec-recheck 重新核验，没有重跑执行端）${pyStrValue(pyItem(fields, "验证"))}`);
    const exec = pyItem(ts, "exec");
    await this.hub.appendEvent("exec.rechecked", [["task", main], ["run_dir", runDir], ["check_ok", pyItem(exec, "check_ok")]]);
    await this.finishKernelStage(state, ts, "exec-step", "5-exec", fields, pyItem(exec, "check_ok"));
    return pyItem(ts, "exec");
  }

  /**
   * 一次开工或返工的回合，连同超时续接与格式重试（第 32、82 轮）；输入目录由调用方建、删（第 88 轮）。
   * resume：被打断之后接着做（第 93 轮）。交回（最后一个回合，它的输出问题，超时过几次）。
   */
  async workerTurns(agent: string, taskId: string, ts: PyDict, texts: readonly string[], workspace: string, kinds: Iterable<PyValue>,
    inputs: string | null, resume: PyValue = null): Promise<[PyDict, string | null, number]> {
    const sessionId = resumedSession(this.hub, agent, resume, workspace);
    let prompt = turnPrompt(this.hub, ts, agent, taskId, texts, workspace, null, inputs, withSession(resume, sessionId));
    // 返工：干净重启，只带任务书、state 与这封返工信（用户评审建议 2）。
    // 被打断的（第 93 轮）：交过的续接那个回合的会话（返工也不重开）；没跑完的开新会话
    const fresh = ([...kinds].some((kind) => kind === "返工") || resume !== null) && sessionId === null;
    let turn = await this.runner.run(agent, taskId, workspace, this.deps.rolePrompt(agent), prompt, null, fresh, inputs, sessionId);
    let error = problemText(this.outputProblem(agent, taskId, turn));
    let timeouts = 0;
    for (let retry = 0; retry < WORKER_RETRIES_AFTER_TIMEOUT; retry += 1) {
      if (!error || pyTruthy(pyItem(turn, "violations")) || pyTruthy(pyGet(turn, "api_error"))) break; // 接口报错重试也没用
      if (retry && !timeouts) break; // 输出不合格只重试一次
      // 第 82 轮：超时只续一次。续上的回合又超时就停，交给协调人，返工开新会话。T016 的合同端在一个卡住的
      // 会话里续了两次，又白等 80 分钟；换新会话 7 分钟就交了。账本里超时后的第一次续接 7 次成了 5 次
      if (retry && pyTruthy(pyGet(turn, "timed_out"))) break;
      // 第 32 轮：超时的回合没机会把格式写对，不占这一次。T010 的规划第一回合 40 分钟超时，续上的回合
      // 把 JSON 写错了，没有再改的机会，协调人只好返工、从头规划
      timeouts += pyTruthy(pyGet(turn, "timed_out")) ? 1 : 0;
      prompt = turnPrompt(this.hub, ts, agent, taskId, texts, workspace, error, inputs);
      turn = await this.runner.run(agent, taskId, workspace, this.deps.rolePrompt(agent), prompt, pyItem(turn, "turn_id") as string, false, inputs, null);
      error = problemText(this.outputProblem(agent, taskId, turn));
    }
    return [turn, error, timeouts];
  }

  /**
   * 第 108 轮：交付没过内核核验，在同一会话里当场重交一次，只跑一个回合（不套格式重试与超时续接）。
   * 账本里约 45 次交付被核验退回，每次多走一圈：核验信 → 协调人一回合 → 返工开新会话 → 工人从头读。
   * 阶段保持 assigned、不写 last_letter：协调人这期间发来的开工、返工照样被 stage_busy 挡下，hub 被收掉时
   * requeue 按“被打断”放回原信。战前门禁的核验先提交、后跑 baseline，没过时提交还在：照返工的做法退回基线、
   * 保留文件。交回（重交的回合, 它的输出问题）。
   */
  async redeliver(state: StateLike, ts: PyDict, agent: string, taskId: string, suffix: string, texts: readonly string[], workspace: string,
    problems: readonly string[], turn: PyDict): Promise<[PyDict, string | null]> {
    let where = workspace;
    if (suffix === "3-gate-pre") where = await this.stageWorkspace(ts, agent, suffix);
    await this.hub.saveState(state); // 核验的副作用（合同已写入、门禁记录）先存下
    const [inputs] = await this.stage(ts, `${taskId}-${utcCompact()}`);
    let again: PyDict;
    try {
      const listed = problems.map((problem) => `- ${pyStrValue(problem)}`).join(LF);
      const prompt = turnPrompt(this.hub, ts, agent, taskId, texts, where, REDELIVER_TEXT.replace("%s", () => listed), inputs);
      again = await this.runner.run(agent, taskId, where, this.deps.rolePrompt(agent), prompt, pyItem(turn, "turn_id") as string, false, inputs, null);
    } finally {
      removeInputs(inputs);
    }
    return [again, problemText(this.outputProblem(agent, taskId, again))];
  }

  /** 协调人对执行端发“通过”：结项（verdict PASS 与 integrate）。 */
  async handlePass(state: StateLike, meta: ReadonlyMap<string, string>): Promise<void> {
    const [main] = stageOf(pyItem(meta as PyDict, "task-id") as string);
    const ts = pyItem(tasksOf(state), main as string) as PyDict;
    const [ok, detail] = await this.deps.finalize(this.hub, ts, this.deps);
    ts.set("status", ok ? "done" : pyItem(ts, "status"));
    if (ok) await releaseDependents(this.hub, state, main as string);
    const leftover = ok
      ? await this.deps.tidyFinished(this.hub, ts, `${main} 已由 hub 结项（${purePathName(pathArg(pyItem(pyItem(ts, "exec"), "run_dir")))} 通过并合入）：`
        + "这一轮没有复审结论，由后面的 attempt 取代", this.deps)
      : [];
    await this.hub.saveState(state);
    const lines = detail ? pySplitlines(detail) : [];
    await this.hub.deliver(letterMeta(KERNEL, OWNER, main, ok ? "核验" : "阻塞"), new Map<string, PyValue>([
      ["摘要", `${main} 结项${ok ? "：verdict PASS，已 integrate" : "失败"}`],
      ["提交", detail ? head(lines[lines.length - 1] ?? indexError(), 200) : "无"], ["验证", "内核 verdict 与 integrate"],
      ["偏离", ok ? (leftover.length > 0 ? head(`结项收尾没做完：${leftover.join("；")}`, 1500) : "无") : head(detail, 1500)],
      ["需协调人决定", ok ? "无" : "请站主处理"], ["证据", `.agent/reviews/${pyStrValue(pyItem(ts, "contract_task"))}/`],
    ]));
  }

  /**
   * 结项时记下要跑的合入后门禁回归：在落地锁外跑，结果写信告诉站主（第 20 轮）。
   * 第 30 轮：落地之后，别的主任务手上已经过了检查的候选，在新末端上各做一次落地预演，撞上了马上写信。
   * 第 62 轮：两样都跑全部门禁基准，挂着后台回归的标记跑，别的主任务的结项等它跑完。
   */
  async afterLand(main: string): Promise<void> {
    await withSweepWindow(this.hub, `${main}-after-land`, `${main} 合入后的门禁回归与落地预演`, () => this.afterLandRun(main), this.deps);
  }

  async afterLandRun(main: string): Promise<void> {
    let state = this.hub.loadState();
    const ts = pyGet(state.tasks(), main) as PyDict | null;
    if (pyTruthy(ts) && pyTruthy(pyGet(or(pyGet(ts, "regression"), new Map()), "pending"))) {
      const [ok, summary] = await this.deps.regressionSweep(this.hub, ts as PyDict, this.deps);
      await this.hub.saveState(state);
      await this.hub.deliver(letterMeta(KERNEL, OWNER, main, ok ? "核验" : "阻塞"), new Map<string, PyValue>([
        ["摘要", `${main} 合入后的门禁回归${ok ? "通过" : "没过"}`], ["提交", "无"], ["验证", head(summary, 1500)], ["偏离", "无"],
        ["需协调人决定", ok ? "无" : "请站主处理：合入的几个主任务互相打破了门禁"],
        ["证据", `.agent/mailbox/ledger/state.json（${main} 的 regression）；全文在 .agent/mailbox/tasks/${main}/regression-sweep.log`],
      ]));
    }
    if (!pyTruthy(ts) || !pyEq(pyGet(ts, "status"), "done")) return; // 没落地：末端没动，别的候选不用重新预演
    for (const other of [...state.tasks().keys()].map(String).sort(cmpCodePoints)) {
      state = this.hub.loadState(); // 每次现读：预演一次要几分钟，别的 runner 这期间照常写
      const otherTs = pyItem(state.tasks(), other) as PyDict;
      if (!pyEq(pyGet(otherTs, "status"), "active")) continue; // 刚落地的这一片已经是 done
      const rehearsed = await this.deps.rehearseLanding(this.hub, otherTs);
      if (rehearsed === null) continue;
      await this.hub.saveState(state);
      if (!rehearsed[0]) await rehearsalLetter(this.hub, otherTs, rehearsed[1], `${main} 刚落地`);
    }
  }

  /** 建这一回合的只读输入目录：worktree 的根目录与 INPUT_FILE_LIMIT 走 deps（用例换掉的照记录注入）。 */
  private async stage(ts: PyDict, key: string): Promise<[string, PyDict]> {
    const root = await this.deps.worktreeRoot(this.hub.repo);
    return stageInputs(this.hub, ts, key, { root, limit: this.deps.inputFileLimit });
  }
}

/**
 * 被打断的阶段续接哪个会话（第 93 轮）：回合已经跑完、交了合格输出的，取它 result.json 里的会话（不假定是
 * 记录里最新的那个）。回合本身没跑完（会话可能停在半截的工具调用上），或者工作目录换了（claude 按目录找会话），
 * 交回 null：开新会话。
 */
export function resumedSession(hub: Hub, agent: string, resume: PyValue, workspace: string): string | null {
  if (!pyTruthy(resume) || !pyTruthy(pyGet(resume, "turn"))) return null;
  let record: PyValue;
  try {
    record = loads(readText(purePathStr(hub.root, "turns", agent, pyStrValue(pyItem(resume, "turn")), "result.json")) || "{}");
  } catch (error) {
    if (!pyCaught(error, ["ValueError"])) throw error;
    return null;
  }
  if (!pyEq(pyGet(record, "workspace"), purePathStr(workspace)) || pyTruthy(pyGet(record, "output_error")) || pyTruthy(pyGet(record, "violations"))) {
    return null;
  }
  const session = pyGet(record, "session_id");
  return pyTruthy(session) ? session as string : null;
}

/**
 * 一个主任务结项之后，放行登记时依赖它的主任务（第 21 轮）：依赖都结项了，就把它的基线挪到当前末端，
 * 阶段 worktree 换新（旧的留到结项一并清掉），写信叫协调人开工合同端。依赖前一片的切片可以先规划：
 * T005 的规划占了 49 分钟，链式依赖的每一片都能省下这一段。交回放行了哪些主任务。
 */
export async function releaseDependents(hub: Hub, state: StateLike, done: string): Promise<PyValue[]> {
  const released: PyValue[] = [];
  const headSha = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const tasks = tasksOf(state);
  if (!(tasks instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(tasks)}' object has no attribute 'values'`);
  for (const ts of tasks.values()) {
    const after = or(pyGet(ts, "after"), []);
    if (!pyEq(pyGet(ts, "status"), "active") || !pyIter(after).some((item) => pyEq(item, done)) || pyTruthy(pyGet(ts, "after_released"))) continue;
    if (pyIter(after).some((item) => !pyEq(pyGet(or(pyGet(tasks, pyStrValue(item)), new Map()), "status"), "done"))) continue;
    const previous = moveBase(ts as PyDict, headSha);
    (ts as PyDict).set("after_released", new Map<string, PyValue>([["at", utcNow()], ["head", headSha], ["previous", previous], ["after", after]]));
    const task = pyItem(ts, "task");
    await hub.appendEvent("dependency.released", [["task", task], ["head", headSha], ["previous", previous], ["after", after]]);
    const names = pyIter(after).map((item) => pyStrValue(item)).join("、");
    await hub.deliver(letterMeta(KERNEL, COORDINATOR, task, "核验"), new Map<string, PyValue>([
      ["摘要", `依赖 ${names} 都已结项：基线从 ${head(pyStrValue(previous), 10)} 挪到 ${head(headSha, 10)}，可以开工合同端`], ["提交", headSha],
      ["验证", `内核读主任务状态（${names} 都已结项）`], ["偏离", "无"],
      ["需协调人决定", "开工 contract-glm。brief 里提醒合同端：规划报告是在旧基线上写的，依赖落地后的文件"
        + "与接口以新基线为准，规划引用的路径与接口逐条在新基线上核对，对不上的写进合同的事实一节"],
      ["证据", `.agent/mailbox/tasks/${pyStrValue(task)}-1-plan/report.md`],
    ]));
    released.push(task);
  }
  return released;
}

/** 持落地锁结项；别的主任务的执行端还在跑时不动，交回挡着的是谁（信留在 new 里，下一轮再试）。 */
export async function land(hub: Hub, engine: Landing, letter: string, meta: ReadonlyMap<string, string>, deps: EngineDeps = REAL_ENGINE_DEPS): Promise<PyValue[]> {
  let main: string | null;
  const lock = new DirLock(purePathStr(hub.root, ".land"), deps.landLockWaitSeconds).acquire();
  try {
    const state = hub.loadState();
    main = stageOf(pyItem(meta as PyDict, "task-id") as string)[0];
    const ts = main ? pyGet(state.tasks(), main) as PyDict | null : null;
    const blockers = pyTruthy(ts) ? landingBlockers(hub, ts as PyDict, true, deps) : [];
    if (blockers.length > 0) return blockers;
    await hub.take(letter);
    await engine.handlePass(state, meta);
  } finally {
    lock.release();
  }
  if (main) await engine.afterLand(main);
  return [];
}

// -- 小工具 -----------------------------------------------------------------

const head = (text: string, size: number): string => codePoints(text).slice(0, size).join("");

const or = (value: PyValue | undefined, fallback: PyValue): PyValue => (pyTruthy(value) ? value as PyValue : fallback);

const indexError = (): never => {
  throw new PyCrash("IndexError", "list index out of range");
};

const firstLine = (text: string): string => pySplitlines(text)[0] ?? indexError();

const isDelivery = (kind: string | undefined): boolean => kind === "交付" || kind === "返工完成";

/** output_problem 交回的：None、文字，或者回合记下的 output_error（任何值，照 Python 当真假用）。 */
const problemText = (value: PyValue): string | null => (pyTruthy(value) ? pyStrValue(value) : null);

/** state["tasks"]：不检查，交给后面的 pyGet、pyItem 照各自的操作报错。 */
function tasksOf(state: StateLike): PyValue {
  return state instanceof HubState ? state.tasks() : pyItem(state, "tasks");
}

/**
 * 对一个该是字典的值做 op：项赋值（"[]="）照 Python 报 TypeError，调方法照 Python 报没有这个属性的 AttributeError。列表例外：字符串键的
 * 项赋值报下标类型不对；列表有 pop，报的是参数个数（这里的 pop 都是 Python 的两参数 pop(key, None)）。
 */
function dict(value: PyValue, op: string): PyDict {
  if (value instanceof Map) return value;
  if (Array.isArray(value) && op === "[]=") throw new PyCrash("TypeError", "list indices must be integers or slices, not str");
  if (Array.isArray(value) && op === "pop") throw new PyCrash("TypeError", "pop expected at most 1 argument, got 2");
  if (op === "[]=") throw new PyCrash("TypeError", `'${pyTypeName(value)}' object does not support item assignment`);
  throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute '${op}'`);
}

/** key in container（state["tasks"] 一类）：字典查键、列表逐个比、字符串查子串，别的照 Python 报 not iterable。 */
function contains(container: PyValue, key: string): boolean {
  if (container instanceof Map) return container.has(key);
  if (Array.isArray(container)) return container.some((item) => pyEq(item, key));
  if (typeof container === "string") return container.includes(key);
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(container)}' is not iterable`);
}

/**
 * traceback 最后一行的类名带模块名的几样（CPython 3.12.10 实测，themistally-04 复核时指出）：只列 TS 这边真抛得出来的。内置的不带；kit_hub
 * 在生产上当脚本跑（__main__），它自己的 HubError、LandBusy 也不带。
 */
const QUALIFIED: Readonly<Record<string, string>> = {
  JSONDecodeError: "json.decoder.JSONDecodeError", error: "re.error", DispatchError: "pi_dispatch.DispatchError",
};

/** step 接住的异常在 Python 里叫什么：交回（type(exc).__name__, traceback 最后一行写的类名）。认不出来的用 JS 的 name。 */
export function pyErrorNames(error: unknown): [string, string] {
  const name = error instanceof LandBusy ? "LandBusy" : error instanceof HubError ? "HubError" : error instanceof DispatchError ? "DispatchError"
    : pyExceptionName(error) ?? (error instanceof Error ? error.name : "Exception");
  return [name, QUALIFIED[name] ?? name];
}

function appendTo(list: PyValue, item: PyValue): void {
  if (!Array.isArray(list)) throw new PyCrash("AttributeError", `'${pyTypeName(list)}' object has no attribute 'append'`);
  list.push(item);
}

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

/**
 * sorted(kinds)：信的类型照码点排。有一封缺 type（None）、又有别的类型时 Python 比较不了，抛 TypeError（step 接住、写阻塞信给站主）；
 * 集合的次序每个进程都不同，报错里两个类型名的先后不固定，照 ⑤f 的口径只比类型与文字的框架。
 */
function sortedStrings(kinds: ReadonlySet<string | null>): PyValue[] {
  if (kinds.has(null) && kinds.size > 1) throw new PyCrash("TypeError", "'<' not supported between instances of 'str' and 'NoneType'");
  return [...kinds].map((kind) => kind as PyValue).sort((a, b) => cmpCodePoints(String(a), String(b)));
}

/**
 * dict(resume, session=session_id) if resume else None。resume 是内核自己写进阶段的字典，只认字典；不是字典时不照 Python（Python 对数报
 * not iterable、对字符串报 ValueError、对二元组的列表照样建出字典），这里一律报 TypeError。
 */
function withSession(resume: PyValue, sessionId: string | null): PyValue {
  if (!pyTruthy(resume)) return null;
  if (!(resume instanceof Map)) throw new PyCrash("TypeError", `'${pyTypeName(resume)}' object is not iterable`);
  return new Map([...resume, ["session", sessionId]]);
}

/** 信的字段交给 deliver：来自 letter_from_output、run_exec 一类与内核自己写的几栏，键只会是字符串（JSON 对象的键）。 */
const letterFields = (fields: PyDict): ReadonlyMap<string, PyValue> => fields as ReadonlyMap<unknown, PyValue> as ReadonlyMap<string, PyValue>;

function letterMeta(sender: string, to: string, taskId: PyValue, kind: string): Map<string, string> {
  return new Map([["from", sender], ["to", to], ["task-id", pyStrValue(taskId)], ["in-reply-to", "none"], ["type", kind]]);
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}
