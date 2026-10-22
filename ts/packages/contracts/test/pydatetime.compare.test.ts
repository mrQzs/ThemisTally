// pydatetime 对照（迁移第 ②c 步）：kit_logs._parse_iso（datetime.fromisoformat 的 C 实现加换成 UTC）与 TS 的 parseIsoUtc
// 逐项一致——解析不了、不带时区、换算溢出都为“不可用”，其余比较换成 UTC 之后的微秒数。随机串照 ISO 8601 的各种写法拼，
// 再随机改一处：日期（扩展、基本、周历）、任意分隔符（含多字节、代理字符、NUL、数字）、时间（时、时分、时分秒、小数的
// 点与逗号、基本写法、多出的冒号）、时区（Z、正负的时、时分、时分秒、带小数、超出 24 小时）。特殊字符一律用码点拼。
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const LONE = String.fromCharCode(0xd800);

const PICKED = [
  "2026-10-22T10:00:00Z", "2026-10-22T10:00:00.123456Z", "2026-10-22T10:00:00.1234567+08:00", "2026-10-22 10:00:00+00:00",
  "2026-10-22T10:00:00", "2026-10-22", "2026-10-22Z", "20261022T100000Z", "2026-W43-4T10:00Z", "2026W434T10Z", "2026-W43T10Z",
  "2026W43T10Z", "2026-W53-1T00Z", "2020-W53-7T00Z", "2026-10-22T10:00:00.Z", "2026-10-22T10:00:00:5Z", "2026-10-22T10:00:00,5Z",
  `2026-10-22T10:00:00Z${C(0)}junk`, `2026-10-22${C(0x4e2d)}10:00Z`, `2026-10-22${LONE}10:00Z`, `2026-10-2${LONE}T10:00Z`,
  "2026-10-22T10:00+00:00:00.5", "2026-10-22T10:00+23:59:59.999999", "2026-10-22T10:00+24:00", "2026-10-22T10:00-24:00",
  "2026-10-22T10:00+00:99", "0001-01-01T00:30:00+01:00", "0001-01-01T00:00:00Z", "9999-12-31T23:59:59.999999Z",
  "9999-12-31T23:30:00-01:00", "2026-02-29T00:00Z", "2024-02-29T00:00Z", "2026-13-01T00:00Z", "2026-10-22T24:00Z",
  "2026-10-22T23:60Z", "2026-10-22T10Z", "2026-10-22T1Z", "2026-10-22T1000Z", "2026-10-22T100000123Z", "2026-10-22T10:00:Z",
  "2026-10-22T10:0000Z", "2026-10-22T-10:00", "2026-10-22T10:00+0530", "2026-10-22T10:00+05", "2026-10-22T10:00+5",
  `${C(0xff12)}026-10-22T10:00Z`, "2026-10-22T10:00z", "2026-1022T10Z", "202610-22T10Z", "abcdefg", "2026-10", "", "1234567",
  // 周历与闰年的边界：没有第 53 周的年份、整百年、四年周期末的 12 月 31 日
  "2025-W53-1T00Z", "2027-W53T00Z", "2020-W53-4T00Z", "1900-02-29T00Z", "2000-02-29T00Z", "2000-W52-7T00Z", "0004-W53-5T00Z",
  // 代理字符不在分隔符上：编码成 UTF-8 失败，整串不可用（换成 U+FFFD 时字节解析会跳过它而照收）
  `2026-10-22T10:00:00.1234567${LONE}Z`, `2026-10-22T10:00:00.1234567${C(0xfffd)}Z`,
];

const DATES = ["2026-10-22", "20261022", "2026-W43", "2026W43", "2026-W43-4", "2026W434", "2024-02-29", "0001-01-01", "9999-12-31",
  "2026-W00", "2026-W53", "2020-W53-7", "2026-00-10", "2026-10-32", "2026-1-22", "0000-01-01"];
const SEPARATORS = ["T", " ", "t", "x", C(0x4e2d), C(0x1f600), LONE, C(0), "1", "-", "", "TT"];
const TIMES = ["10", "10:00", "10:00:00", "1000", "100000", "10:00:00.5", "10:00:00,123", "10:00:00.1234567890", "10:00:00.",
  "10:00:00:5", "10:0000", "23:59:59.999999", "24:00", "00:00", "9", "10:00:0", "10.5", ""];
const ZONES = ["", "Z", "+00:00", "-00:00", "+08:00", "-05:30", "+0530", "+05", "+23:59:59.999999", "+24:00", "-24:00", "+00:00:00.5",
  "-00:00:01", "+1", "Zx", "+08:00x", "z", `Z${C(0)}`, "+99:99"];

function generator(seed: number) {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;
  return (): string => {
    let text = pick(DATES) + (rnd() < 0.85 ? pick(SEPARATORS) + pick(TIMES) + pick(ZONES) : "");
    if (rnd() < 0.3) {
      // 随机改一处：删一个字符、插一个字符或换一个字符
      const chars = Array.from(text);
      const at = int(0, chars.length);
      const extra = pick(["0", "9", ":", "-", "+", "Z", "T", ".", ",", " ", C(0), C(0x660), LONE, "W"]);
      const kind = int(0, 2);
      if (kind === 0) chars.splice(at, 1);
      else if (kind === 1) chars.splice(at, 0, extra);
      else chars.splice(at, 1, extra);
      text = chars.join("");
    }
    return text;
  };
}

function compare(texts: string[]): void {
  const request: ProbeRequest = { op: "pydatetime.parse_iso", texts };
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, [request])[0]);
  const values = python?.["values"] as (string | null)[];
  expect(values.some((value) => value === null) && values.some((value) => value !== null), "Python 那边要有能用的，也要有不可用的").toBe(true);
  for (const other of others) {
    const mismatches = texts.flatMap((text, index) =>
      (other?.["values"] as (string | null)[])[index] === values[index] ? [] : [{ text, python: values[index], other: (other?.["values"] as (string | null)[])[index] }]);
    expect(mismatches.slice(0, 5)).toEqual([]);
  }
}

describe("pydatetime 对照：kit_logs._parse_iso", () => {
  it("手挑的写法", () => compare(PICKED), 60_000);

  it.each([1, 2, 3, 4])("随机，种子 %i：3000 个", (seed) => {
    const next = generator(seed);
    compare(Array.from({ length: 3000 }, next));
  }, 60_000);
});
