// pi_dispatch 的运行健康判断（迁移第 ④b4b 片，决策点 run-health）：_run_health_state、assess_run、decisions_records_of。
// 决策会话由 cli 从 @themis/config/decisions-client 接进来（本包不能 import config），这里只用它的接口。
import { closeSync, fstatSync, openSync, readSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { PyCrash, pyFixed, pyFloatOf, pyGet, pyIntOf, pyItem, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8Replace, pyReadText } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, encodeUtf8, loads } from "@themis/base/pyjson";
import { cmpCodePoints, codePoints, pyLower, pySplit, pyStrip } from "@themis/base/pyre";
import { mdSection } from "./contract.ts";
import { DECISIONS_RECORD } from "./decision-records.ts";
import { messageText } from "./events.ts";
import { readRecords } from "./metrics.ts";
import { readJsonOr } from "./repo.ts";
import { strptimeUtc } from "./status.ts";

const DECISIONS_TAIL_CHARS = 3000;
const DECISIONS_TAIL_BYTES = 262144;
const RUN_HEALTH_ACTIONS = ["keep_waiting", "prepare_next_contract", "collect"];
const LF = String.fromCharCode(10);

/** 问题清单里调度器读到的部分（阈值）。 */
export interface AssessBattery {
  readonly thresholds: PyDict;
}

/** codekit.decisions.Session 的接口：ask 总是交回结果（answered 或 no_opinion），调用失败不抛。 */
export interface DecisionSession {
  readonly mode: string;
  readonly batteries: ReadonlyMap<string, AssessBattery>;
  ask(battery: AssessBattery, state: PyValue, context: PyDict | null): Promise<PyDict>;
}

/** decisions_session(config, agent_dir, record_path, point)：模式 off、决策点未启用时为 null；配置写错抛 DispatchError。 */
export type SessionFactory = (config: PyValue, agentDir: string | null, recordPath: string | null, point: string | null) => DecisionSession | null;

/** assess_run 在同一次 wait 里跨 tick 记住的东西。 */
export interface HealthTracker {
  fingerprint?: string;
  seen?: string[];
  ticks?: number;
  streak?: Map<string, number>;
}

interface Health {
  readonly state: PyDict;
  readonly fingerprint: string;
  readonly seen: string[];
  readonly quiet: number;
  readonly repeating: boolean;
}

/** read_text_or：读不了、不是 UTF-8 时为空串。 */
function readTextOr(file: string): string {
  try {
    return pyReadText(file);
  } catch (error) {
    if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return "";
    throw error;
  }
}

/** 从 offset 读到文件末尾（Python 的 handle.read()：stat 之后文件又长了的部分也读进来）。 */
function readFrom(file: string, offset: number): Buffer {
  const fd = openSync(file, "r");
  try {
    const chunks: Buffer[] = [];
    let position = offset;
    for (;;) {
      const chunk = Buffer.alloc(Math.max(65536, fstatSync(fd).size - position));
      const count = readSync(fd, chunk, 0, chunk.length, position);
      if (count === 0) break;
      chunks.push(chunk.subarray(0, count));
      position += count;
    }
    return Buffer.concat(chunks);
  } finally {
    closeSync(fd);
  }
}

function splitBytes(data: Buffer): Buffer[] {
  const lines: Buffer[] = [];
  let start = 0;
  for (let at = data.indexOf(10); at >= 0; at = data.indexOf(10, start)) {
    lines.push(data.subarray(start, at));
    start = at + 1;
  }
  lines.push(data.subarray(start));
  return lines;
}

/** _run_health_state：事件尾部的 assistant 文本与最近的工具调用，加上代码算出的事实（静默秒数、是否重复）。 */
export function runHealthState(runDir: string, tracker: HealthTracker): Health | null {
  const eventsPath = path.join(runDir, "events.jsonl");
  let size: number;
  let mtime: number;
  let data: Buffer;
  try {
    const stat = statSync(eventsPath);
    size = stat.size;
    mtime = stat.mtimeMs / 1000;
    data = readFrom(eventsPath, size > DECISIONS_TAIL_BYTES ? size - DECISIONS_TAIL_BYTES : 0);
  } catch {
    return null;
  }
  let rawLines = splitBytes(data);
  if (size > DECISIONS_TAIL_BYTES) rawLines = rawLines.slice(1); // 第一行多半是半截
  const texts: string[] = [];
  const tools: PyDict[] = [];
  for (const raw of rawLines) {
    let event: PyValue;
    try {
      event = loads(pyDecodeUtf8Replace(raw));
    } catch (error) {
      if (error instanceof PyJsonError && error.kind !== "RecursionError") continue;
      throw error;
    }
    if (!(event instanceof Map)) continue;
    const kind = event.get("type");
    if (kind === "message_end") {
      const message = event.get("message") instanceof Map ? (event.get("message") as PyDict) : new Map();
      if (message.get("role") === "assistant") {
        const body = messageText(message);
        if (pyStrip(body)) texts.push(body);
      }
    } else if (kind === "tool_execution_end") {
      tools.push(new Map<string, PyValue>([["tool", event.get("toolName") ?? null], ["error", pyTruthy(event.get("isError") ?? null)]]));
    }
  }
  const recent = codePoints(texts.join(LF)).slice(-DECISIONS_TAIL_CHARS).join("");
  const fingerprint = createHash("sha256").update(encodeUtf8(pySplit(recent).join(" "))).digest("hex");
  const previous = [...(tracker.seen ?? [])];
  const repeating = fingerprint === tracker.fingerprint && previous.filter((item) => item === fingerprint).length >= 2;
  const seen = [...previous, fingerprint].slice(-12);
  const now = Date.now() / 1000;
  const started = pyGet(readJsonOr(path.join(runDir, "run-started.json"), new Map()), "started_at");
  let elapsed: bigint | null = null;
  if (pyTruthy(started)) {
    if (typeof started !== "string") throw new PyCrash("TypeError", "strptime() argument 1 must be str");
    const begin = strptimeUtc(started);
    if (begin !== null) elapsed = BigInt(Math.trunc((Date.now() - begin) / 1000));
  }
  const quiet = Math.max(0, Math.trunc(now - mtime));
  const goal = codePoints(pyStrip(mdSection(readTextOr(path.join(runDir, "plan.md")), "Goal") ?? "")).slice(0, 1500).join("");
  const state = new Map<string, PyValue>([
    ["goal", goal], ["recent_output", recent], ["recent_tools", tools.slice(-10)], ["seconds_since_new_event", BigInt(quiet)],
    ["seconds_running", elapsed], ["tool_calls_recent", BigInt(tools.length)], ["output_is_repeating", repeating],
  ]);
  return { state, fingerprint, seen, quiet, repeating };
}

/** thresholds.get(name, fallback)：问题清单里的阈值都已是 float。 */
const threshold = (battery: AssessBattery, name: string, fallback: number): number => pyFloatOf(battery.thresholds.get(name) ?? fallback);

/**
 * assess_run：一次运行健康判断，返回要打印的文字（可能两行），从不停止运行。代码先算免费能算的事实（多久没有新事件、
 * 尾部是否重复），模型只判它判不了的；静默超过 stall_seconds 时即使模型说 keep_waiting 也建议准备下一版合同。连续
 * alert_after 次相同的非 keep_waiting 建议，或一次置信度达到 action 阈值的建议，才算提示（on 模式）。
 */
export async function assessRun(runDir: string, session: DecisionSession, tracker: HealthTracker): Promise<string> {
  const health = runHealthState(runDir, tracker);
  if (health === null) return "";
  tracker.fingerprint = health.fingerprint;
  tracker.seen = health.seen;
  tracker.ticks = (tracker.ticks ?? 0) + 1;
  const battery = session.batteries.get("run-health");
  if (battery === undefined) throw new PyCrash("KeyError", "'run-health'");
  const stall = threshold(battery, "stall_seconds", 180);
  const result = await session.ask(battery, health.state, new Map<string, PyValue>([["tick", BigInt(tracker.ticks)], ["quiet_seconds", BigInt(health.quiet)]]));
  let strong = false;
  let action: string;
  let line: string;
  if (result.get("status") !== "answered") {
    action = health.repeating || health.quiet >= stall ? "prepare_next_contract" : "keep_waiting";
    line = `决策（run-health, ${session.mode}）：无意见（${String(result.get("reason") ?? "None")}），只按活动信号 · 静默 ${health.quiet} 秒 · ` +
      `重复 ${health.repeating ? "是" : "否"} · 建议 ${action}`;
  } else {
    const answers = result.get("answers") as PyDict;
    const chosen = pyItem(answers, "action");
    action = pyItem(chosen, "choice") as string;
    const confidence = pyFloatOf(pyItem(chosen, "confidence"));
    strong = confidence >= threshold(battery, "action", 0.7);
    let note = "";
    if (health.quiet >= stall && action === "keep_waiting") {
      action = "prepare_next_contract";
      note = `；${health.quiet} 秒没有新事件，事实优先于模型`;
    }
    const noul = (name: string): string => pyFixed(pyFloatOf(pyItem(pyItem(answers, name), "noul")), 2);
    line = `决策（run-health, ${session.mode}）：推进 ${noul("progressing")} · 被挡 ${noul("blocked")} · 打转 ${noul("looping")} · ` +
      `完成 ${noul("done")} · 建议 ${action}（置信度 ${pyFixed(confidence, 2)}）${note}`;
  }
  const streak = new Map(tracker.streak ?? []);
  for (const key of RUN_HEALTH_ACTIONS) streak.set(key, action === key ? (streak.get(key) ?? 0) + 1 : 0);
  tracker.streak = streak;
  const alertAfter = Number(pyIntOf(battery.thresholds.get("alert_after") ?? 2n, "int()"));
  if (action !== "keep_waiting") {
    const count = streak.get(action);
    if (count === undefined) throw new PyCrash("KeyError", `'${action}'`);
    if ((count >= alertAfter || strong) && session.mode === "on") {
      line += `${LF}决策模型提示：建议 ${action}（连续 ${count} 次）。运行不会被停止；可以开始准备下一步，结论仍以证据为准`;
    }
  }
  return line;
}

/** decisions_records_of：一个 attempt 的全部决策记录，attempt 目录的 decisions.jsonl 加每轮 mutations/NN/ 的。 */
export function decisionsRecordsOf(runDir: string): PyDict[] {
  const records = readRecords(path.join(runDir, DECISIONS_RECORD));
  const mutations = path.join(runDir, "mutations");
  let names: string[];
  try {
    names = statSync(mutations).isDirectory() ? iterdirSorted(mutations) : [];
  } catch {
    names = [];
  }
  for (const name of names) {
    const sub = path.join(mutations, name);
    let isDirectory = false;
    try {
      isDirectory = statSync(sub).isDirectory();
    } catch {
      isDirectory = false;
    }
    if (isDirectory) records.push(...readRecords(path.join(sub, DECISIONS_RECORD)));
  }
  return records;
}

/** sorted(Path.iterdir())：同一目录下按名字比，Windows 上 Path 先 str.lower() 再按码点比。 */
function iterdirSorted(directory: string): string[] {
  const key = (name: string): string => (process.platform === "win32" ? pyLower(name) : name);
  return readdirSync(directory).sort((left, right) => cmpCodePoints(key(left), key(right)));
}
