// codekit/decisions.py 的决策记录与回答的可读形式（迁移第 ④b6 片）：write_summary 的“决策”一节用，之后的 decisions 命令与
// hub 也用。读记录的 readRecords 在 metrics.ts（④b2）。
import { pyFixed, pyFloatOf, pyGet, pyIntOf, pyStrValue } from "@themis/base/pyfmt";
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
