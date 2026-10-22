// pyfmt 对照：repr(str)、str(任意 JSON 值)、int(str) 与 Python 逐字一致（第 ② 步的报错与文本输出都靠它们）。
// 随机输入偏向边界：引号与反斜杠、控制字符、C1、软连字符与零宽字符（Cf）、行分隔符、私用区与未分配码点、
// 孤立代理项、补充平面字符、各种十进制数字与空白、下划线。特殊字符一律用码点拼。
import { describe, expect, it } from "vitest";
import type { Tagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);

const CHARS = [
  "a", "Z", "0", " ", "'", '"', C(0x5c), "\t", "\n", "\r", C(0x0), C(0x1b), C(0x1f), C(0x7f), C(0x80), C(0x9f), C(0xa0), C(0xad),
  C(0xe9), C(0x200b), C(0x2028), C(0x3000), C(0x4e2d), C(0xe000), C(0xffff), C(0xfffd), C(0x1f600), C(0x10ffff), C(0x301),
  C(0x378), String.fromCharCode(0xd800), String.fromCharCode(0xdfff),
];
const DIGITS = ["0", "1", "9", C(0x660), C(0x669), C(0xff11), C(0x1d7ce), C(0x1d7ff), C(0xb2), C(0x2155), "_", "+", "-", " ", C(0x3000), C(0x1c), "a", "."];

function generator(seed: number) {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;
  const text = (pool: readonly string[], max: number): string => Array.from({ length: int(0, max) }, () => pick(pool)).join("");
  const value = (depth: number): Tagged => {
    switch (int(0, depth > 2 ? 4 : 6)) {
      case 0:
        return { t: "none" };
      case 1:
        return { t: "bool", v: rnd() < 0.5 };
      case 2:
        return { t: "int", hex: (BigInt(int(0, 1 << 30)) * (rnd() < 0.3 ? -1n : 1n)).toString(16) };
      case 3: {
        const bits = Buffer.alloc(8);
        bits.writeDoubleBE(pick([0, -0, 1.5, 1e16, 1e-7, 0.1, 123456789.125, 1 / 3]));
        return { t: "float", bits: bits.toString("hex") };
      }
      case 4:
        return { t: "str", v: text(CHARS, 6) };
      case 5:
        return { t: "list", v: Array.from({ length: int(0, 3) }, () => value(depth + 1)) };
      default:
        return { t: "dict", v: Array.from({ length: int(0, 3) }, () => [{ t: "str", v: text(CHARS, 4) }, value(depth + 1)] as const) };
    }
  };
  return { text, value, int };
}

describe("pyfmt 对照：repr、str、int", () => {
  it.each([1, 2, 3, 4])("种子 %i：repr 300 个、str 200 个、int 300 个", (seed) => {
    const { text, value } = generator(seed);
    const requests: ProbeRequest[] = [
      ...Array.from({ length: 300 }, () => ({ op: "pyfmt.call", fn: "repr", text: text(CHARS, 12) })),
      ...Array.from({ length: 200 }, () => ({ op: "pyfmt.call", fn: "str", value: value(0) })),
      ...Array.from({ length: 300 }, () => ({ op: "pyfmt.call", fn: "int", text: text(DIGITS, 6) })),
    ];
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
    const parsed = python?.filter((result) => result.ok).length ?? 0;
    expect(parsed, "Python 那边要有一部分 int 解析成功、一部分失败").toBeGreaterThan(500);
    for (const other of others) {
      const mismatches = requests.flatMap((request, index) =>
        JSON.stringify(other[index]) === JSON.stringify(python?.[index]) ? [] : [{ request, python: python?.[index], other: other[index] }],
      );
      expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    }
  });
});
