// codekit/decisions.py 的决策记录与回答的可读形式（迁移第 ④b6 片）：write_summary 的“决策”一节用，之后的 decisions 命令与
// hub 也用。读记录的 readRecords 在 metrics.ts（④b2）。
import { PyCrash, pyFixed, pyFloatOf, pyGet, pyIntOf, pyRound, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";

/** pi_dispatch.DECISIONS_RECORD：attempt 目录里的决策记录。 */
export const DECISIONS_RECORD = "decisions.jsonl";

/** latest_by_point：每个决策点最后一条记录的副本；point 不是字符串的跳过。 */
export function latestByPoint(records: readonly PyDict[]): Map<string, PyDict> {
  const latest = new Map<string, PyDict>();
  for (const item of records) {
    const point = item.get("point");
    if (typeof point === "string") latest.set(point, new Map(item));
  }
  return latest;
}

/** noul_confidence：noul 没有 confidence 字段，官方文档建议 |2p-1|。 */
export const noulConfidence = (p: number): number => Math.abs(2.0 * p - 1.0);

/** answer_value：一条回答的可读形式（文本, 置信度）；answer 不是字典、数值转不成 float 时照 Python 抛异常。 */
export function answerValue(answer: PyValue): [string, number] {
  const kind = pyGet(answer, "type");
  if (kind === "noul") {
    const p = pyFloatOf(pyGet(answer, "noul", 0));
    return [`p=${pyFixed(p, 2)}`, noulConfidence(p)];
  }
  if (kind === "choice") return [pyStrValue(pyGet(answer, "choice")), pyFloatOf(pyGet(answer, "confidence", 0))];
  const shown = `${pyFixed(pyFloatOf(pyGet(answer, "score", 0)), 2)}/${pyIntOf(pyGet(answer, "levels", 0n)) - 1n}`;
  return [shown, pyFloatOf(pyGet(answer, "confidence", 0))];
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const dict = (entries: readonly (readonly [string, PyValue])[]): PyDict => new Map(entries);

/** codekit/decisions.PRICE_USD_PER_MILLION_INPUT。 */
const PRICE_USD_PER_MILLION_INPUT = 0.042;

/** usage_totals：调用次数、有答案的次数、输入 token 与估算花费、各无意见原因的次数。 */
export function usageTotals(records: readonly PyDict[]): PyDict {
  const calls = records.length;
  const answered = records.filter((record) => record.get("status") === "answered").length;
  // (r.get("usage") or {}).get("input_tokens")：usage 是真值却不是字典时照 Python 抛 AttributeError
  const inputTokens = (record: PyDict): PyValue | undefined => {
    const usage = record.get("usage") ?? null;
    if (!pyTruthy(usage)) return undefined;
    if (!isDict(usage)) throw new PyCrash("AttributeError", `'${pyTypeName(usage)}' object has no attribute 'get'`);
    return usage.get("input_tokens");
  };
  let tokens = 0n;
  for (const record of records) {
    const value = inputTokens(record);
    if (typeof value === "bigint") tokens += value;
    else if (typeof value === "boolean") tokens += value ? 1n : 0n;
  }
  const reasons = new Map<string, PyValue>();
  for (const record of records) {
    if (record.get("status") === "answered") continue;
    const reason = pyStrValue(record.get("reason") ?? null);
    reasons.set(reason, ((reasons.get(reason) as bigint | undefined) ?? 0n) + 1n);
  }
  return dict([
    ["calls", BigInt(calls)], ["answered", BigInt(answered)], ["no_opinion", BigInt(calls - answered)], ["input_tokens", tokens],
    ["estimated_cost_usd", pyRound((pyFloatOf(tokens) * PRICE_USD_PER_MILLION_INPUT) / 1_000_000, 8)], ["no_opinion_reasons", reasons],
  ]);
}
