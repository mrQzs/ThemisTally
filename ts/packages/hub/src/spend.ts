// 回合的花费与 token 用量（第 135、136 轮）：kit_hub.py 的 USAGE_PROMPT_KEYS、turn_metrics、spend_cap_problem、check_spend_cap、
// describe_spend_cap。metrics 的表与任务的花费上限都从这里取；turn_metrics 原在 commands.ts，引擎要用，挪到这里免得互相引用。
import { readdirSync, statSync } from "node:fs";
import { PyCrash, pyFixed, pyFloatOf, pyGet, pyItem, pyRound, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { PyUnicodeDecodeError, pyReadText } from "@themis/base/pyio";
import { purePathStr } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { EXIT_USAGE } from "./constants.ts";
import { HubError } from "./errors.ts";
import { stageOf } from "./letters.ts";
import type { Hub } from "./mailbox.ts";

/**
 * 回合读进去的上下文：每次模型调用的新输入、缓存读、缓存写之和（pi 的 usage 键名）。pi 岗位不回报花费，配额花在哪只看得到这几项；
 * claude 回合的记录里没有 usage，记为没有。
 */
const USAGE_PROMPT_KEYS = ["input", "cacheRead", "cacheWrite", "cacheWrite1h"];

/** 有一个就交回 null 的 dict.get：值不是 dict 时照 Python 抛 AttributeError。 */
function getOf(value: PyValue, key: string): PyValue {
  if (!(value instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'get'`);
  return pyGet(value, key);
}

/** 每个工人回合一行：主任务、工人、用时、这一回合的花费（第 16 轮之前的 claude 记录按会话依次相减换算回这一回合的）、token 用量。 */
export function turnMetrics(hub: Hub): PyDict[] {
  const records: PyValue[] = [];
  for (const path of resultFiles(purePathStr(hub.root, "turns"))) {
    try {
      records.push(loads(pyReadText(path)));
    } catch (error) {
      if (error instanceof PyJsonError || error instanceof PyUnicodeDecodeError) continue; // 都是 ValueError
      throw error;
    }
  }
  const keyOf = (record: PyValue): string => { const id = getOf(record, "turn_id"); return pyTruthy(id) ? pyStrValue(id) : ""; };
  const keys = records.map(keyOf); // 先算全部的键：record.get 报错照 Python 在排序之前抛
  const order = records.map((_, index) => index).sort((a, b) => cmpCodePoints(keys[a] as string, keys[b] as string) || a - b);
  const lastTotal = new Map<string, number>();
  const rows: PyDict[] = [];
  for (const record of order.map((index) => records[index] as PyDict)) {
    let cost = pyGet(record, "cost_usd");
    const legacy = !record.has("session_cost_usd");
    if (legacy && cost !== null) {
      const total = pyFloatOf(cost);
      const session = pyStrValue(pyGet(record, "session_id"));
      const previous = lastTotal.get(session);
      cost = previous === undefined || total < previous ? total : pyRound(total - previous, 6);
      lastTotal.set(session, total);
    }
    const sessionKey = pyGet(record, "session_key");
    const wall = pyGet(record, "wall_seconds");
    const usage = pyGet(record, "usage");
    const tokens = (...keys: string[]): PyValue => usage instanceof Map
      ? keys.map((key) => usage.get(key)).filter((value): value is bigint => typeof value === "bigint").reduce((a, b) => a + b, 0n)
      : null;
    rows.push(new Map<string, PyValue>([
      ["task", stageOf(pyTruthy(sessionKey) ? pyStrValue(sessionKey) : "")[0] || "?"], ["agent", pyGet(record, "agent")],
      ["seconds", pyFloatOf(pyTruthy(wall) ? wall : 0n)], ["cost_usd", cost], ["deliver_refusals", pyGet(record, "deliver_refusals")],
      ["thinking_chars", pyGet(record, "thinking_chars")], ["thinking_tokens", pyGet(record, "thinking_tokens")],
      ["prompt_tokens", tokens(...USAGE_PROMPT_KEYS)], ["cache_read_tokens", tokens("cacheRead")], ["output_tokens", tokens("output")],
    ]));
  }
  return rows;
}

/** turns 下两层目录里的 result.json（Python 用两层通配的 glob 找），照 sorted(Path)：逐段比，Windows 上每段先转小写。 */
function resultFiles(turns: string): string[] {
  const found: string[][] = [];
  for (const agent of listDir(turns)) {
    for (const turn of listDir(purePathStr(turns, agent))) {
      if (isFile(purePathStr(turns, agent, turn, "result.json"))) found.push([agent, turn]);
    }
  }
  const fold = (part: string): string => (process.platform === "win32" ? part.toLowerCase() : part);
  found.sort((a, b) => cmpCodePoints(fold(a[0] as string), fold(b[0] as string)) || cmpCodePoints(fold(a[1] as string), fold(b[1] as string)));
  return found.map(([agent, turn]) => purePathStr(turns, agent as string, turn as string, "result.json"));
}

function listDir(path: string): string[] {
  try {
    return statSync(path).isDirectory() ? readdirSync(path) : [];
  } catch {
    return [];
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** Python 的 x or 0：None、0、0.0 都当 0。 */
const orZero = (value: PyValue): number => (pyTruthy(value) ? pyFloatOf(value) : 0);

/**
 * 任务的花费上限（第 136 轮）：已知花费加上这一回合的预占（同一工人在这个主任务里花得最多的一回合）超过上限时交回说明，否则 null。
 * 美元只有 claude 回合回报，token 只有 pi 回合回报；执行端（调度器 run）的花费不在回合记录里。没设上限的主任务不读回合记录。
 */
export function spendCapProblem(hub: Hub, ts: PyDict, agent: string): string | null {
  const cap = pyGet(ts, "spend_cap");
  if (!(cap instanceof Map)) return null;
  const rows = turnMetrics(hub).filter((row) => pyEq(pyItem(row, "task"), pyItem(ts, "task")));
  const usd = rows.map((row) => orZero(pyItem(row, "cost_usd")));
  const tokens = rows.map((row) => orZero(pyItem(row, "prompt_tokens")) + orZero(pyItem(row, "output_tokens")));
  const mine = rows.map((row, index) => (pyEq(pyItem(row, "agent"), agent) ? index : -1)).filter((index) => index >= 0);
  const reserveUsd = mine.reduce((most, index) => Math.max(most, usd[index] as number), 0);
  const reserveTokens = mine.reduce((most, index) => Math.max(most, tokens[index] as number), 0);
  const spentUsd = usd.reduce((total, value) => total + value, 0);
  const spentTokens = tokens.reduce((total, value) => total + value, 0);
  const capUsd = pyGet(cap, "usd");
  const capTokens = pyGet(cap, "tokens");
  const over: string[] = [];
  if (capUsd !== null && spentUsd + reserveUsd > pyFloatOf(capUsd)) {
    over.push(`美元：已知 ${pyFixed(spentUsd, 2)}，这一回合预占 ${pyFixed(reserveUsd, 2)}，上限 ${pyFixed(pyFloatOf(capUsd), 2)}`);
  }
  if (capTokens !== null && spentTokens + reserveTokens > pyFloatOf(capTokens)) {
    over.push(`token：已用 ${pyFixed(spentTokens / 10000, 1)} 万，这一回合预占 ${pyFixed(reserveTokens / 10000, 1)} 万，`
      + `上限 ${pyFixed(pyFloatOf(capTokens) / 10000, 1)} 万`);
  }
  return over.length > 0 ? over.join("；") : null;
}

/** 花费上限要大于 0；不设就不给（第 136 轮）。 */
export function checkSpendCap(usd: PyValue, tokens: PyValue): void {
  if ((usd !== null && pyFloatOf(usd) <= 0) || (tokens !== null && pyFloatOf(tokens) <= 0)) throw new HubError("花费上限要大于 0", EXIT_USAGE);
}

export function describeSpendCap(cap: PyDict): string {
  const usd = pyGet(cap, "usd");
  const tokens = pyGet(cap, "tokens");
  return `美元 ${usd !== null ? pyFixed(pyFloatOf(usd), 2) : "不设"}、token ${tokens !== null ? `${pyFixed(pyFloatOf(tokens) / 10000, 1)} 万` : "不设"}`;
}
