// 按码点的 str.find、str.count、str.replace 对照（迁移第 ④b5b 片）：pyStrFind、pyStrCount、pyStrReplace 与 Python 逐项一致。
// mutate 用它们数锚点、套用变异、找决策上下文的位置。要害是 UTF-16 与码点的差别：孤立的代理项只对得上补充平面字符的半边，
// Python 按码点比对不上；跨过补充平面字符的 old 照常对上。另有空串（count 是码点数加一，replace 插在每个码点之前与末尾）
// 与 replace 的次数上限。find 的起点与结果按码点交换，TS 一侧在探针里换算。
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const FACE = C(0x1f600);
const HIGH = String.fromCharCode(0xd83d);
const LOW = String.fromCharCode(0xde00);

function compare(items: ProbeRequest[]): void {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, items));
  for (const other of others) {
    const mismatches = (other ?? []).flatMap((result, index) =>
      JSON.stringify(result) === JSON.stringify(python?.[index]) ? [] : [{ request: items[index], python: python?.[index], other: result }],
    );
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  }
}

const call = (text: string, sub: string, start = 0, replacement = "<>", limit = -1): ProbeRequest => ({ op: "pystr.call", text, sub, start, new: replacement, limit });

const PICKED: ProbeRequest[] = [
  call(`a${FACE}b`, LOW), call(`a${FACE}b`, HIGH), call(`${FACE}${FACE}`, `${LOW}${HIGH}`), call(FACE, LOW, 1), call(FACE, HIGH, 0),
  call(`x${FACE}y${FACE}`, `${FACE}y`), call(`${FACE}a${FACE}a`, `a${FACE}`, 1), call(`${LOW}x`, LOW), call(`x${HIGH}`, HIGH),
  call("", ""), call("abc", ""), call(`a${FACE}`, ""), call(`a${FACE}`, "", 2), call(`a${FACE}`, "", 1, "-", 1), call("abc", "", 3, "-", 0),
  call("abc", "", 0, "-", 10), call("aaaa", "aa"), call("aaaa", "aa", 1, "b", 1), call("aaa", "a", 0, "", 2), call("abc", "x", 3),
  call("abc", "", 4), call(FACE, "", 2), call("abc", "c", 5),
  call(`${C(0x4e2d)}${FACE}${C(0x4e2d)}`, C(0x4e2d), 1, FACE),
];

describe("按码点的 str.find、count、replace", () => {
  it("手挑的边界", () => compare(PICKED));

  it.each([71, 72, 73])("随机，种子 %i：1000 条", (seed) => {
    const rnd = prng(seed);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const alphabet = ["a", "b", FACE, C(0x1f601), C(0x4e2d)];
    const word = (length: number): string => Array.from({ length }, () => pick(alphabet)).join("");
    compare(Array.from({ length: 1000 }, () => {
      const text = word(Math.floor(rnd() * 12));
      const points = Array.from(text);
      const from = Math.floor(rnd() * (points.length + 1));
      const sub = rnd() < 0.15 ? "" : rnd() < 0.3 ? pick([HIGH, LOW, `${LOW}a`, `a${HIGH}`, `${LOW}${HIGH}`]) : rnd() < 0.6
        ? points.slice(from, from + 1 + Math.floor(rnd() * 3)).join("") || "a" : word(1 + Math.floor(rnd() * 2));
      return call(text, sub, Math.floor(rnd() * (points.length + 3)), pick(["", "-", FACE]), pick([-1, -1, 0, 1, 2, 5]));
    }));
  }, 120_000);
});
