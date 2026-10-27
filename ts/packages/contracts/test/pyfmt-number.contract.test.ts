// Python 的 "%.Nf" 与 round(x, N) 的契约（迁移第 ④b2 片，metrics 的百分比、价格与耗时）。按二进制的精确值舍入，恰在中点
// 时取偶（JS 的 toFixed 在中点向上，1e21 起改用指数）；-0.0 保留负号；int 的 round 仍是 int。浮点数按 64 位的位模式交给
// 两边，每条先由 Python 回答，Node、Bun 逐字一致。
import { describe, expect, it } from "vitest";
import { type ProbeRequest, prng, runAgreeing } from "./harness.ts";

function bitsOf(value: number): string {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value);
  return view.getBigUint64(0).toString(16).padStart(16, "0");
}

const DIGITS = [0, 1, 2, 4, 6, 8];
const float = (value: number, digits: number): ProbeRequest => ({ op: "pyfmt.number", bits: bitsOf(value), digits });
const int = (value: string, digits: number): ProbeRequest => ({ op: "pyfmt.number", int: value, digits });

describe("%.Nf 与 round", () => {
  it("手写的：恰在中点、负零、很大很小、非有限、int", () => {
    const values = [0, -0, 0.5, 1.5, 2.5, -0.5, -2.5, 12.5, 0.125, 0.03125, 0.0000005, 1e-7, 123456789.125, 1e21, 1e22, 2 ** 70 + 0.5,
      5e-324, 1.7976931348623157e308, Number.NaN, Infinity, -Infinity, 0.1, 0.7, 1 / 3, 2.675, 1.005, 0.000123455, 99.995];
    const requests = [
      ...values.flatMap((value) => DIGITS.map((digits) => float(value, digits))),
      ...["0", "-7", "12", "123456789012345678901234567890"].flatMap((value) => DIGITS.map((digits) => int(value, digits))),
    ];
    const { python, mismatches } = runAgreeing(requests);
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    const fixed = (index: number): unknown => python[index]?.["fixed"];
    // 12.5 是恰在中点的二进制值：Python 写 12，JS 的 toFixed 写 13
    expect(fixed(values.indexOf(12.5) * DIGITS.length)).toBe("12");
    expect(fixed(values.indexOf(0.03125) * DIGITS.length + 3)).toBe("0.0312");
  });

  it("按种子：随机的位模式与 k/2^m 这类中点值，每个种子 600 条", () => {
    const requests: ProbeRequest[] = [];
    for (const seed of [81, 82]) {
      const next = prng(seed);
      for (let index = 0; index < 600; index += 1) {
        const digits = DIGITS[Math.floor(next() * DIGITS.length)] as number;
        let value: number;
        if (next() < 0.5) value = (Math.floor(next() * 2 ** 20) + 0.5) / 2 ** Math.floor(next() * 12);
        else value = (next() - 0.5) * 10 ** Math.floor(next() * 30 - 12);
        requests.push(float(next() < 0.3 ? -value : value, digits));
      }
    }
    const { mismatches } = runAgreeing(requests);
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  });
});
