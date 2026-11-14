// 重活车道（第 155 轮，信箱演进第 1 步）：kit_hub.py 的 HEAVY_WAIT_SECONDS、LAND_TRY_SECONDS、FAILED_TEST_RE、LaneBusy、heavy_lane、heavy_holder、
// regression_check_ids、failed_test_names、baseline_mismatches、check_mismatches、checked_in_lane、checked_with_one_rerun。
// 内核自己起的、会把全部旧门禁跑一遍的活（基线检查、执行检查、落地检查、变异检查、后台回归与落地预演）一次只跑一份；只有全量回归不符时
// 原样重跑一次。锁目录 .heavy 与 Python 的是同一把（owner.json 的格式两边一样），站主用 Python 起的命令与 TS 的 hub 互相排队。
// LaneDeps 只给契约用（排队与试落地锁的时限、pid 活没活、哪几条是全量回归）：并进 ContractDeps 与 GatePostDeps，生产调用方不传。
import { randomBytes } from "node:crypto";
import { statSync, unlinkSync } from "node:fs";
import { utcCompact, utcNow } from "@themis/base/clock";
import { readText, sleepSync, writeTextAtomic } from "@themis/base/fsutil";
import { pidAlive } from "@themis/base/process";
import { pyGet, pyItem, pyIter, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { purePathName, purePathParent, purePathStr } from "@themis/base/pypath";
import { NOT_S, cmpCodePoints, pyRegex } from "@themis/base/pyre";
import { globPaths } from "@themis/dispatcher/instruction";
import { comparePaths } from "./audit.ts";
import { EXIT_BLOCKED } from "./constants.ts";
import { BASELINE_RECORD_RE, contractPaths, tailFile } from "./contract.ts";
import { HubError } from "./errors.ts";
import { latestChecks } from "./exec.ts";
import { DirLock, type Hub, dirLockAlive } from "./mailbox.ts";
import { regressionGates } from "./prompt.ts";

const LF = String.fromCharCode(10);
const LINE_START = `(?<![^${LF}])`;

/** 重活车道排队的上限：一份全量检查约 20 分钟，前面排着几份也就一两个小时。 */
export const HEAVY_WAIT_SECONDS = 4 * 3600;
/** 落地在车道里试落地锁的时限：拿不到就让出车道、下一轮再试，不拿着车道干等。 */
export const LAND_TRY_SECONDS = 15;
/** 重活车道的号牌（第 160 轮）：排车道先在这里取号，排在最前的活着的号才去拿锁。原来谁先轮询到 mkdir 谁拿到，11-13 一天插队 84 次。 */
export const HEAVY_QUEUE = ".heavy-queue";
/** 看号牌的间隔：每看一次要问一遍排在前面那张的进程还在不在。 */
const HEAVY_TICKET_POLL_SECONDS = 1;
const FAILED_TEST_RE = pyRegex(`${LINE_START}FAILED (${NOT_S}+)`, true);

/** 重活车道排到上限也没排到：这份检查没有跑，不是检查不过。 */
export class LaneBusy extends HubError {}

export type RunPd = (hub: Hub, args: readonly string[], timeout?: number) => Promise<[number, string]>;
/** 不符的检查编号，连同它们的日志。 */
export type Mismatches = [string[], string[]];

export interface LaneDeps {
  readonly heavyWaitSeconds: number;
  readonly landTrySeconds: number;
  readonly pidAlive: (pid: number) => boolean | null;
  readonly regressionCheckIds: (hub: Hub, ts: PyDict) => Set<string>;
}

export const REAL_LANE_DEPS: LaneDeps = {
  heavyWaitSeconds: HEAVY_WAIT_SECONDS, landTrySeconds: LAND_TRY_SECONDS, pidAlive, regressionCheckIds: (hub, ts) => regressionCheckIds(hub, ts),
};

const or = (value: PyValue | undefined, fallback: PyValue): PyValue => (pyTruthy(value) ? value as PyValue : fallback);
/** Python 的 except ValueError 接得住的：json.loads 的报错，与读到不是 UTF-8 的文件。 */
const isValueError = (error: unknown): boolean => error instanceof PyJsonError || (error as Error | null)?.name === "UnicodeDecodeError";

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** json.loads(read_text(path) or "{}")，读不出来（ValueError）给空 dict。 */
function readJson(path: string): PyValue {
  try {
    return loads(readText(path) || "{}");
  } catch (error) {
    if (!isValueError(error)) throw error;
    return new Map();
  }
}

/** 重活车道里现在是谁（给 status 看）；空着是 null。锁目录在、持有者进程不在了算空着（同 lock_alive）。 */
export function heavyHolder(hub: Hub, lane: Pick<LaneDeps, "pidAlive"> = REAL_LANE_DEPS): string | null {
  const path = purePathStr(hub.root, ".heavy");
  if (!dirLockAlive(path, lane.pidAlive)) return null;
  return laneLabel(readJson(purePathStr(path, "label.json")));
}

/** 车道里或排着车道的那一份怎么称呼：“T001 的基线检查”，站主的不带主任务。 */
function laneLabel(data: PyValue): string {
  const task = pyGet(data, "task");
  return `${pyTruthy(task) ? `${pyStrValue(task)} 的` : ""}${pyStrValue(or(pyGet(data, "label"), "重检查"))}`;
}

/** 第 160 轮：排车道先取号。号牌名以取号时刻打头（utcCompact 定长），按名字排就是先后；后面带进程号与两字节随机数，同一时刻取号也不重名。 */
function takeLaneTicket(hub: Hub, label: string, task: PyValue): string {
  const path = purePathStr(hub.root, HEAVY_QUEUE, `${utcCompact()}-${process.pid}-${randomBytes(2).toString("hex")}.json`);
  const data = new Map<string, PyValue>([["pid", BigInt(process.pid)], ["label", label], ["task", task], ["at", utcNow()]]);
  writeTextAtomic(path, `${dumps(data, { ensureAscii: false })}${LF}`);
  return path;
}

function dropLaneTicket(path: string): void {
  try {
    unlinkSync(path);
  } catch {
    // 已经不在了（Python 的 except OSError: pass）
  }
}

/** 号牌按先后排好（按名字的码位排，与 Python 一样），带上内容；读不出来的内容是空 dict。 */
function laneTickets(hub: Hub): [string, PyValue][] {
  const queue = purePathStr(hub.root, HEAVY_QUEUE);
  if (!isDirectory(queue)) return [];
  return globPaths(queue, ["*.json"]).sort((left, right) => cmpCodePoints(purePathName(left), purePathName(right))).map((path) => {
    const data = readJson(path);
    return [path, data instanceof Map ? data : new Map()];
  });
}

/** 号牌的持有者进程还在（查不清也算在）；没写进程号的号牌不是内核写的，算不在。 */
function ticketAlive(data: PyValue, lane: Pick<LaneDeps, "pidAlive">): boolean {
  const pid = pyGet(data, "pid");
  return typeof pid === "bigint" && pid > 0n && lane.pidAlive(Number(pid)) !== false;
}

/** 号牌里排在最前的活着的是不是自己。排在前面、持有者已经不在的号牌顺手删掉；自己的号牌被别人删了也算排到。 */
function firstInLaneQueue(hub: Hub, ticket: string, lane: Pick<LaneDeps, "pidAlive">): boolean {
  for (const [path, data] of laneTickets(hub)) {
    if (purePathName(path) === purePathName(ticket)) return true;
    if (ticketAlive(data, lane)) return false;
    dropLaneTicket(path);
  }
  return true;
}

/** 等到自己的号牌排在最前；到了时限还没排到交回 false。 */
function waitInLaneQueue(hub: Hub, ticket: string, deadline: number, lane: Pick<LaneDeps, "pidAlive">): boolean {
  while (!firstInLaneQueue(hub, ticket, lane)) {
    if (performance.now() >= deadline) return false;
    sleepSync(HEAVY_TICKET_POLL_SECONDS * 1000);
  }
  return true;
}

/** 排着车道的（给 status 与“排不到”的说明看）：持有者还在的号牌，按先后。只读，不删号牌。 */
export function laneQueue(hub: Hub, lane: Pick<LaneDeps, "pidAlive"> = REAL_LANE_DEPS): string[] {
  return laneTickets(hub).filter(([, data]) => ticketAlive(data, lane)).map(([, data]) => laneLabel(data));
}

/** 排不到车道时说明当时的情形：车道里是谁；车道空着就说排在最前的是谁。 */
function laneWhereabouts(hub: Hub, lane: Pick<LaneDeps, "pidAlive">): string {
  const holder = heavyHolder(hub, lane);
  if (holder) return `车道里是 ${holder}`;
  const queue = laneQueue(hub, lane);
  return queue.length ? `车道空着，排在前面的是 ${queue[0]}` : "车道里是 不明";
}

/**
 * 在重活车道里做 fn。在起子进程之前拿锁，各条检查自己的时限不算排队的时间。拿锁的次序：.sweep → .heavy → .land；拿着 .land 不等 .heavy
 * （落地先排车道、再试落地锁，试不到就让出车道），否则站主的 exclusive 拿着落地锁等执行端、执行端的检查等车道、落地拿着车道等落地锁，
 * 三方互等。等了多久、跑了多久不记进事件：看 heavy.queued、heavy.entered、heavy.left 三条的时刻。
 */
export async function withHeavyLane<T>(hub: Hub, label: string, task: PyValue, fn: () => Promise<T>, lane: LaneDeps = REAL_LANE_DEPS): Promise<T> {
  const ahead = heavyHolder(hub, lane);
  if (ahead) await hub.appendEvent("heavy.queued", [["task", task], ["label", label], ["behind", ahead]]);
  // 第 160 轮：先取号，排到最前才去拿锁；取的号不管拿没拿到锁都撤掉（拿到了就不算排着，没拿到就不排了）
  const deadline = performance.now() + lane.heavyWaitSeconds * 1000;
  const ticket = takeLaneTicket(hub, label, task);
  let taken: DirLock | null = null;
  try {
    if (waitInLaneQueue(hub, ticket, deadline, lane)) {
      const lock = new DirLock(purePathStr(hub.root, ".heavy"), Math.max(0, (deadline - performance.now()) / 1000));
      try {
        taken = lock.acquire();
      } catch (error) {
        if (!(error instanceof HubError)) throw error;
      }
    }
  } finally {
    dropLaneTicket(ticket);
  }
  if (taken === null) {
    throw new LaneBusy(`重活车道排到上限（${Math.trunc(lane.heavyWaitSeconds)} 秒）也没排到（${laneWhereabouts(hub, lane)}）：`
      + `${label} 没有跑，不是检查不过`, EXIT_BLOCKED);
  }
  const lock = taken;
  try {
    const mark = new Map<string, PyValue>([["label", label], ["task", task], ["at", utcNow()]]);
    writeTextAtomic(purePathStr(lock.path, "label.json"), `${dumps(mark, { ensureAscii: false })}${LF}`);
    await hub.appendEvent("heavy.entered", [["task", task], ["label", label]]);
    try {
      return await fn();
    } finally {
      await hub.appendEvent("heavy.left", [["task", task], ["label", label]]);
    }
  } finally {
    lock.release();
  }
}

/** 合同里跑先前各片门禁基准的那几条检查的编号（contract_requirements 要求必须有的全量回归）。 */
export function regressionCheckIds(hub: Hub, ts: PyDict): Set<string> {
  const gates = new Set(regressionGates(hub, ts));
  let data: PyValue;
  try {
    data = loads(readText(contractPaths(hub, ts)[1]) || "{}");
  } catch (error) {
    if (!isValueError(error)) throw error;
    return new Set();
  }
  const ids = new Set<string>();
  for (const check of pyIter(or(pyGet(data, "checks"), []))) {
    if (pyIter(or(pyGet(check, "argv"), [])).some((item) => typeof item === "string" && gates.has(item))) ids.add(pyStrValue(pyGet(check, "id")));
  }
  return ids;
}

/** 检查日志末尾 pytest 汇总里红的用例名。 */
export function failedTestNames(logs: readonly string[]): string[] {
  const names: string[] = [];
  for (const log of logs) {
    if (isFile(log)) for (const match of tailFile(log, 200n).matchAll(FAILED_TEST_RE)) names.push(match[1] as string);
  }
  return names;
}

/** 基线检查的记录里与预期不符的检查编号，连同它们的日志；记录读不出来给空。 */
export function baselineMismatches(hub: Hub, out: string): Mismatches {
  const match = BASELINE_RECORD_RE.exec(out);
  const recordPath = match ? purePathStr(hub.repo, match[1] as string) : null;
  if (recordPath === null || !isFile(recordPath)) return [[], []];
  const data = readJson(recordPath);
  const ids = pyIter(or(pyGet(data, "mismatches"), [])).map(pyStrValue);
  const logs = pyIter(or(pyGet(data, "results"), []))
    .filter((item) => ids.includes(pyStrValue(pyGet(item, "id"))) && pyTruthy(pyGet(item, "log")))
    .map((item) => purePathStr(purePathParent(purePathParent(recordPath)), pyStrValue(pyGet(item, "log"))));
  return [ids, logs];
}

/** attempt 最近一次 check 没过的检查编号，连同它们的日志。 */
export function checkMismatches(runDir: string): Mismatches {
  const checks = globPaths(purePathStr(runDir, "checks"), ["*", "checks.json"]).map((path) => purePathStr(path)).sort(comparePaths);
  const failed = pyIter(latestChecks(runDir)).filter((item) => pyGet(item, "status") !== "passed");
  const last = checks.at(-1);
  const logs = last === undefined ? [] : failed.filter((item) => pyTruthy(pyGet(item, "log")))
    .map((item) => purePathStr(purePathParent(purePathParent(last)), pyStrValue(pyGet(item, "log"))));
  return [failed.map((item) => pyStrValue(pyGet(item, "id"))), logs];
}

/**
 * 在重活车道里跑一次调度器的检查。没过、而且不符的只有全量回归那几条时，原样重跑一次：第二次相符照通过处理，账本记 regression.flaky
 * （带第一次红的用例名），输出末尾写明；第二次仍不符照旧判失败。本片自己的检查不符不重跑。车道排到上限也没排到：照“没跑成”给出退出码
 * 与说明，不让异常从验收的半道上穿出去。
 */
export async function checkedInLane(hub: Hub, ts: PyDict, label: string, args: readonly string[], timeout: number,
  mismatched: (out: string) => Mismatches, runPd: RunPd, lane: LaneDeps = REAL_LANE_DEPS): Promise<[number, string]> {
  try {
    return await withHeavyLane(hub, label, pyItem(ts, "task"), () => checkedWithOneRerun(hub, ts, label, args, timeout, mismatched, runPd, lane), lane);
  } catch (error) {
    if (!(error instanceof LaneBusy)) throw error;
    return [EXIT_BLOCKED, error.message];
  }
}

async function checkedWithOneRerun(hub: Hub, ts: PyDict, label: string, args: readonly string[], timeout: number,
  mismatched: (out: string) => Mismatches, runPd: RunPd, lane: LaneDeps): Promise<[number, string]> {
  let [code, out] = await runPd(hub, args, timeout);
  if (code === 0) return [code, out];
  const [ids, logs] = mismatched(out);
  if (!ids.length) return [code, out];
  const regression = lane.regressionCheckIds(hub, ts);
  if (!ids.every((id) => regression.has(id))) return [code, out];
  const names = failedTestNames(logs).slice(0, 20);
  const sorted = [...ids].sort(cmpCodePoints);
  const task = pyItem(ts, "task");
  [code, out] = await runPd(hub, args, timeout);
  await hub.appendEvent("regression.rerun", [["task", task], ["label", label], ["checks", sorted], ["failed", names], ["exit", BigInt(code)]]);
  if (code !== 0) return [code, out];
  if (!ts.has("flaky")) ts.set("flaky", []);
  (ts.get("flaky") as PyValue[]).push(new Map<string, PyValue>([["at", utcNow()], ["label", label], ["checks", sorted], ["failed", names]]));
  await hub.appendEvent("regression.flaky", [["task", task], ["label", label], ["checks", sorted], ["failed", names]]);
  return [code, `${out}${LF}（第一次只有全量回归 ${sorted.join("、")} 不符，红的用例：${names.slice(0, 8).join("、") || "没读出来"}；原样重跑一次，相符）`];
}
