// pyregex 对照（迁移第 ②b2 步）：kit_logs._compile_search 加逐行 search，与 TS 的 compileSearch 加 test 逐项一致——
// 编译的结果（能编译、报错原文、ValueError）与每段文本有没有匹配。三类输入：
//   1. 手挑的：实测时撞过的差别（JavaScriptCore 前瞻里的 ^、占有量词里的懒惰重复、(?a:) 的字符集前缀按整个模式的
//      Unicode \w 判定）、大小写与 _casefix、锚点与 \b、\N{…} 的名字；
//   2. 随机一：字符偏向大小写与类别的边界（开尔文符号、长 s、希腊字母、非 BMP），字符集、标志、后顾、原子组；
//   3. 随机二：小字母表、可空的子模式、嵌套重复、懒惰与占有混用（专找回溯次序的差别）。
// 嵌套不超过两层、文本不超过 10 个码点：免得撞上灾难性回溯（Python 也会卡住）。特殊字符一律用码点拼。
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const BS = C(0x5c);

const CASED = ["a", "A", "k", "K", "s", "S", "i", "I", "z", "_", "0", " ", "\n", "-", C(0xb5), C(0xdf), C(0xe9), C(0xc9),
  C(0x130), C(0x131), C(0x17f), C(0x212a), C(0x3bc), C(0x39c), C(0x345), C(0x3b9), C(0x1fbe), C(0x1e9e), C(0x2126), C(0x3c9),
  C(0x4e2d), C(0xff21), C(0x10400), C(0x10428), C(0x1d400), C(0x1f600), C(0x660), C(0x2028), C(0x85), C(0xa0), C(0x3000),
  C(0x1c), C(0xb), C(0x1e9b), C(0x1e61), C(0xfb05), C(0xfb06), C(0x3c2), C(0x3c3), C(0x3a3), C(0x1c80), C(0xab70), C(0x13a0)];
const SMALL = ["a", "b", "A", "B", " ", "\n", "_", "1"];
const SPECIAL = ".^$*+?{}[]()|" + BS;

/** 实测撞过的、以及各条路径上的代表写法。 */
const PICKED: readonly string[] = [
  `(?s)(?a:[^${BS}w${C(0x10400)} A-i])`, `(${BS}A.){,3}+A`, `(?m:[${C(0x3bc)}s${BS}S${BS}-]??){0,2}+[${C(0x3a3)}]`,
  `(?i)(?-i: {,3}?){1,}+x`, "(?:x|){,3}+A", "(.){,3}+A", "(?>(a|ab))c", "(?>a+)ab", "(a+)+b", `(?<=a${BS}b)c`,
  `(?<!${BS}d{2})x`, "^$", `${BS}A${BS}Z`, `(?m)^b$`, `${BS}bfoo${BS}b`, `${BS}B`, `(?a)${BS}w+`, `${BS}w+`, `(?i)${C(0x212a)}`,
  `(?i)${C(0xdf)}`, `(?i)${C(0x3c3)}`, `(?i)[${C(0x3c2)}-${C(0x3c9)}]`, `(?i)[k-m]`, `(?i)[${C(0x10400)}-${C(0x1044f)}]`,
  `(?ia)k`, `(?i)${C(0x130)}`, `(?i)${C(0x131)}`, `(?i)${C(0x345)}`, `[^${BS}W${BS}d]`, `(?x) a b # c`, "a{2,}?b", "a{,2}+",
  `${BS}N{EM DASH}`, `${BS}N{em dash}`, `${BS}N{EMDASH}`, `${BS}N{LATIN CAPITAL LETTER A WITH MACRON AND GRAVE}`,
  `${BS}N{HANGUL SYLLABLE GAG}`, `${BS}N{hangul syllable gag}`, `${BS}N{CJK UNIFIED IDEOGRAPH-4E00}`,
  `${BS}N{CJK UNIFIED IDEOGRAPH-4e00}`, `${BS}N{BYTE ORDER MARK}`, `${BS}N{`, `${BS}N{}`, `${BS}U00110000`, `${BS}x4`,
  "a(?i)b", "(?a)(?u)", "(?L)a", "(?t)a*", "(?t)a", "(?<=a+)b", `${"(".repeat(100)}a${")".repeat(100)}`,
  `${"(".repeat(101)}a${")".repeat(101)}`, `(a)${BS}1`, `((a)${BS}2)`, `(?i:(a)${BS}1)`, "(a)?(?(1)b|c)", "a{4294967295}", "a{4294967294}", "x{2}{3}", "a**",
  `a${C(0xa)}(b`, "[z-a]", "(?P<1a>x)", "(?#comment", "",
  // 变异检验补的：八进制上限、重复下限的溢出、锚点后的量词、非 BMP 范围的 (?i)、ASCII 的 \s
  `${BS}400`, `${BS}377`, `${BS}1000`, "a{4294967295,}", "a{4294967294,}", "^*", `${BS}b+`, `(?i)[${C(0x10400)}-${C(0x1040f)}]`,
  `(?i)[${C(0x10428)}-${C(0x1042f)}]`, `(?a)${BS}s`, `(?a)[${BS}s]`, `${BS}s`, `(?a)${BS}S`,
];

const PICKED_TEXTS = ["", "a", "AKA", "aa", "ab", "aab", "aaab", "b", "x", "foo bar", "foobar", "a\nb", `${C(0x212a)}`, "k",
  `${C(0xb5)}${C(0xfb05)}${C(0xab70)}`, `${C(0x3b9)} ${C(0x3a3)}`, `${C(0x1e9e)}`, `${C(0x3c2)}`, `${C(0x10428)}`, "i", "I",
  `${C(0x130)}`, `${C(0x2014)}`, `${C(0x100)}${C(0x300)}`, `${C(0xac01)}`, `${C(0x4e00)}`, `${C(0xfeff)}`, "  x", " A",
  "1a2", "_", "A1", "x=1", "STRASSE", `stra${C(0xdf)}e`, C(0x1c), C(0x85), C(0x3000), C(0xff), `${C(0x10400)}`];

function generators(seed: number) {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;
  const lit = (pool: readonly string[]): string => {
    const char = pick(pool);
    return SPECIAL.includes(char) ? BS + char : char;
  };
  const cls = (pool: readonly string[]): string => {
    const parts = Array.from({ length: int(1, 3) }, () => {
      const r = rnd();
      if (r < 0.3) return pick(["a-z", "A-Z", "0-9", "K-k", `${C(0x370)}-${C(0x3ff)}`, `${C(0x10400)}-${C(0x1044f)}`, `${C(0x100)}-${C(0x17f)}`]);
      if (r < 0.5) return BS + pick(["d", "D", "s", "S", "w", "W"]);
      const char = pick(pool);
      return `${BS}]^-[`.includes(char) ? BS + char : char;
    });
    return `[${rnd() < 0.3 ? "^" : ""}${parts.join("")}]`;
  };
  const quant = (): string => (rnd() < 0.5 ? "" : pick(["*", "+", "?", "{2}", "{0,2}", "{1,3}", "{,2}", "{2,}", "{0}"]) + pick(["", "", "?", "+"]));
  const ZERO = ["^", "$", `${BS}A`, `${BS}Z`, `${BS}b`, `${BS}B`];
  const atom = (pool: readonly string[], depth: number): string => {
    const r = rnd();
    if (r < 0.35 || depth >= 2) return rnd() < 0.7 ? lit(pool) : cls(pool) + quant();
    if (r < 0.45) return pick(ZERO);
    if (r < 0.5) return "." + quant();
    const inner = seq(pool, depth + 1);
    const kind = rnd();
    if (kind < 0.25) return `(${inner})${quant()}`;
    if (kind < 0.45) return `(?:${inner}|${seq(pool, depth + 1)})${quant()}`;
    if (kind < 0.55) return `(?:${inner}|)${quant()}`;
    if (kind < 0.7) return `(?>${inner})${quant()}`;
    if (kind < 0.8) return `(?${pick(["=", "!"])}${inner})`;
    if (kind < 0.88) return `(?<${pick(["=", "!"])}${Array.from({ length: int(1, 2) }, () => lit(pool)).join("")})`;
    return `(?${pick(["i", "-i", "m", "s", "a", "x"])}:${inner})${quant()}`;
  };
  const seq = (pool: readonly string[], depth: number): string =>
    Array.from({ length: int(1, 3) }, () => {
      const item = atom(pool, depth);
      return ZERO.includes(item) || item.startsWith("(?=") || item.startsWith("(?!") || item.startsWith("(?<") ? item : item + quant();
    }).join("");
  const pattern = (pool: readonly string[]): string => {
    const body = rnd() < 0.3 ? `${seq(pool, 0)}|${seq(pool, 0)}` : seq(pool, 0);
    return pick(["", "", "", "(?i)", "(?m)", "(?s)", "(?a)", "(?ia)", "(?im)"]) + body;
  };
  const text = (pool: readonly string[]): string => Array.from({ length: int(0, 10) }, () => pick(pool)).join("");
  return { pattern, text };
}

function compare(requests: ProbeRequest[]): void {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  const outcomes = new Set(python?.map((result) => String(result["outcome"])));
  expect(outcomes.has("match") && outcomes.has("error"), "Python 那边既要有能编译的，也要有报错的").toBe(true);
  for (const other of others) {
    const mismatches = requests.flatMap((request, index) =>
      JSON.stringify(other[index]) === JSON.stringify(python?.[index]) ? [] : [{ pattern: request["pattern"], python: python?.[index], other: other[index] }],
    );
    expect(mismatches.slice(0, 5)).toEqual([]);
  }
}

describe("pyregex 对照：编译结果与逐行匹配", () => {
  it("手挑的写法", () => {
    compare(PICKED.map((pattern) => ({ op: "pyregex.search", pattern, texts: PICKED_TEXTS })));
  }, 120_000);

  it.each([1, 2, 3])("随机一（大小写与类别的边界），种子 %i：400 个模式", (seed) => {
    const { pattern, text } = generators(seed);
    compare(Array.from({ length: 400 }, () => ({ op: "pyregex.search", pattern: pattern(CASED), texts: Array.from({ length: 10 }, () => text(CASED)) })));
  }, 120_000);

  it.each([11, 12, 13])("随机二（可空、嵌套、懒惰与占有），种子 %i：400 个模式", (seed) => {
    const { pattern, text } = generators(seed);
    compare(Array.from({ length: 400 }, () => ({ op: "pyregex.search", pattern: pattern(SMALL), texts: Array.from({ length: 12 }, () => text(SMALL)) })));
  }, 120_000);
});
