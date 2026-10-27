// difflib.SequenceMatcher 对照（迁移第 ④b5a 片）：同一对字符串，Python 与 TS（Node、Bun）的 ratio（按 float 的位比）、
// 匹配块与 opcodes 逐项一致。mutate --check-anchors 拿它挑“最相近的行”、算百分比、找第一处不同。
// 随机串的字母表很小（匹配多、并列多），b 的长度跨过 200（autojunk 的门槛），autojunk 开与关都比。
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);

function compare(items: ProbeRequest[]): void {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, items));
  for (const other of others) {
    const mismatches = (other ?? []).flatMap((result, index) =>
      JSON.stringify(result) === JSON.stringify(python?.[index]) ? [] : [{ a: items[index]?.["a"], b: items[index]?.["b"], python: python?.[index], other: result }],
    );
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  }
}

const PICKED: [string, string][] = [
  ["", ""], ["abc", ""], ["", "abc"], ["abcd", "bcde"], ["qabxcd", "abycdf"],
  ["private Thread currentThread;", "private volatile Thread currentThread;"],
  ["const value = compute(input);", "const value = compute(input) ?? fallback;"],
  [`${C(0x4e2d, 0x6587)}的锚点`, `${C(0x4e2d, 0x6587)}锚点${C(0x1f600)}`],
  ["    if (x) {", "if (x) {"],
  ["a".repeat(199), `${"a".repeat(150)}b${"a".repeat(48)}`],
  ["a".repeat(120), `${"a".repeat(150)}${"b".repeat(50)}`],
  ["ab".repeat(60), `${"ab".repeat(100)}c`],
  [`${"x".repeat(10)}ab${"x".repeat(10)}`, `${"x".repeat(150)}ab${"x".repeat(51)}`],
  // b 恰好 200 个元素，q 恰好出现 n//100+1 = 3 次：要超过才算 popular，这里 q 照样能匹配。q 不放开头：从 (0, 0) 起往后
  // 扩展也会把它扩进来，那样看不出它算不算 popular
  ["q", `xqqq${Array.from({ length: 196 }, (_, index) => C(0x4e00 + index)).join("")}`],
];

describe("difflib 对照：SequenceMatcher", () => {
  it("手挑的几对 × autojunk 开、关", () => {
    compare(PICKED.flatMap(([a, b]) => [true, false].map((autojunk) => ({ op: "pydifflib.call", a, b, autojunk }))));
  });

  it.each([51, 52, 53])("随机，种子 %i：400 对", (seed) => {
    const rnd = prng(seed);
    const alphabets = ["ab", "abc ", `ab${C(0x4e2d)}${C(0x1f600)} `, "abcdefghij", "a"];
    const text = (alphabet: string[], length: number): string => Array.from({ length }, () => alphabet[Math.floor(rnd() * alphabet.length)]).join("");
    const items: ProbeRequest[] = Array.from({ length: 400 }, () => {
      const alphabet = Array.from(alphabets[Math.floor(rnd() * alphabets.length)] as string);
      const long = rnd() < 0.4;
      const length = (): number => (long ? 150 + Math.floor(rnd() * 110) : Math.floor(rnd() * 30));
      return { op: "pydifflib.call", a: text(alphabet, length()), b: text(alphabet, length()), autojunk: rnd() < 0.8 };
    });
    compare(items);
  }, 120_000);

  // 像 --check-anchors 实际比的：old 的首行对文件的一行。在真实代码行上做只差空白、改一个字符、插 astral 字符的变体，
  // 另有超过 200 字符、大量重复字符的长行（autojunk 的 popular 生效）
  it.each([61, 62])("代码行的变体，种子 %i：400 对", (seed) => {
    const rnd = prng(seed);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const LINES = [
      "const total = compute(input, options) ?? fallback;", "if (!isFile(reviewPath) || statSync(reviewPath).size === 0) throw error;",
      "    return [absolute ? purePathStr(program) : purePathStr(cwd, program), ...argv.slice(1)];",
      "} else if (code.startsWith('ERR_SSL_') || code === 'EPROTO') {",
      `${"=".repeat(120)} ${"-".repeat(100)}`, `${"ab ".repeat(80)}end`, `const face = "${C(0x1f600)}${C(0x4e2d, 0x6587)}";`,
    ];
    const vary = (line: string): string => {
      const chars = Array.from(line);
      const at = Math.floor(rnd() * (chars.length + 1));
      switch (Math.floor(rnd() * 6)) {
        case 0: return `  ${line}  `;
        case 1: return chars.filter((_, index) => index !== at).join("");
        case 2: return [...chars.slice(0, at), pick([" ", "x", C(0x1f601), C(9)]), ...chars.slice(at)].join("");
        case 3: return line.replace(/ /gu, "  ");
        case 4: return [...chars.slice(0, at), ...chars.slice(at).reverse()].join("");
        default: return line;
      }
    };
    compare(Array.from({ length: 400 }, () => {
      const line = pick(LINES);
      return { op: "pydifflib.call", a: vary(line).trim(), b: vary(rnd() < 0.7 ? line : pick(LINES)).trim(), autojunk: rnd() < 0.85 };
    }));
  }, 120_000);
});
