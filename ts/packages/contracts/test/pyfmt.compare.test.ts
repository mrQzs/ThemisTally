// pyfmt 对照：repr(str)、str(任意 JSON 值)、int(str) 与 Python 逐字一致（第 ② 步的报错与文本输出都靠它们）。
// 随机输入偏向边界：引号与反斜杠、控制字符、C1、软连字符与零宽字符（Cf）、行分隔符、私用区与未分配码点、
// 孤立代理项、补充平面字符、各种十进制数字与空白、下划线。特殊字符一律用码点拼。
import { describe, expect, it } from "vitest";
import { type Tagged, floatBits } from "../src/tagged.ts";
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

/**
 * sum()（④b4a 补，themistally-15 复核 b29ab6c 查出）：CPython 3.12 的 builtin_sum 对 float 做 Neumaier 补偿求和，int 走 C long
 * 的快速路径（Windows 上 32 位），溢出或遇到装不下的 int 就退回普通加法。float、int、bool 混着来，含 -0.0、inf、nan、
 * 会吃掉小数的 1e16 与超出 float 范围的 int。
 */
describe("pyfmt 对照：sum", () => {
  const FLOATS = [0.1, 0.2, 0.3, 0.7, 0.97, 2.5, 1, -0, 1e16, -1e16, 1e-17, 1e308, -1e308, Infinity, -Infinity, Number.NaN];
  const INTS = [0n, 1n, -3n, 2n ** 31n - 1n, 2n ** 31n, -(2n ** 31n), -(2n ** 31n) - 1n, 2n ** 62n, 2n ** 63n, 10n ** 30n, 2n ** 1100n];
  const int = (value: bigint): Tagged => ({ t: "int", hex: (value < 0n ? "-" : "") + (value < 0n ? -value : value).toString(16) });
  it.each([41, 42, 43])("种子 %i：400 串", (seed) => {
    const rnd = prng(seed);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const item = (): Tagged => {
      const roll = rnd();
      if (roll < 0.6) return { t: "float", bits: floatBits(rnd() < 0.5 ? pick(FLOATS) : (rnd() - 0.5) * 10 ** Math.floor(rnd() * 6)) };
      if (roll < 0.85) return int(rnd() < 0.7 ? BigInt(Math.floor(rnd() * 200) - 100) : pick(INTS));
      return { t: "bool", v: rnd() < 0.5 };
    };
    const items: ProbeRequest[] = Array.from({ length: 400 }, () => ({
      op: "pyfmt.call", fn: "sum", value: { t: "list", v: Array.from({ length: Math.floor(rnd() * 14) }, item) },
    }));
    // 累加和过了 2**31 还留在 int 路径（Py_ssize_t），到 2.0 才转进有补偿的 float 路径（themistally-15 复核 cf99239 的那一串）
    const f = (value: number): Tagged => ({ t: "float", bits: floatBits(value) });
    items.push({ op: "pyfmt.call", fn: "sum", value: { t: "list", v: [{ t: "bool", v: true }, int(2147483647n), f(2.0), f(-0.2), f(2.0), f(11.0), { t: "bool", v: false }, f(7e-6), f(-0.009373147144156338)] } });
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, items));
    for (const other of others) {
      const mismatches = (other ?? []).flatMap((result, index) =>
        JSON.stringify(result) === JSON.stringify(python?.[index]) ? [] : [{ value: items[index]?.["value"], python: python?.[index], other: result }],
      );
      expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    }
  }, 120_000);
});
