// NFKC 对照：decisions.normalize 里的 unicodedata.normalize("NFKC") 跟 Python 的 Unicode 15.0 走，
// 而 Node、Bun 的 ICU 是 Unicode 17.0。风险只在 15.0 之后新分配的字符（Python 眼里的 Cn）：先找出 JS 规范化时
// 会动到的那些（单独规范化会变，或放进 a + X + U+0316 里会变），再放进各种上下文与 Python 逐个比较。
import { describe, expect, it } from "vitest";
import { UNASSIGNED } from "@themis/base/pyunicode";
import { IMPLS, type ProbeRequest, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);

function risky(): number[] {
  const found: number[] = [];
  for (let index = 0; index < UNASSIGNED.length; index += 2) {
    for (let cp = UNASSIGNED[index] ?? 0; cp <= (UNASSIGNED[index + 1] ?? 0); cp += 1) {
      if (cp >= 0xd800 && cp <= 0xdfff) continue;
      const x = C(cp);
      const probe = `a${x}${C(0x316)}`;
      if (x.normalize("NFKC") !== x || probe.normalize("NFKC") !== probe) found.push(cp);
    }
  }
  return found;
}

const CONTEXTS: readonly ((x: string) => string)[] = [
  (x) => x,
  (x) => `a${x}${C(0x316)}`,
  (x) => `${x}${C(0x301)}`,
  (x) => `e${C(0x301)}${x}${C(0x328)}`,
  (x) => `${C(0x1100)}${x}${C(0x1161)}`, // 韩文字母之间
  (x) => `${C(0xff21)}${x}${C(0xff11)}`, // 全角
  (x) => `${x}${C(0xfb01)}${x}`, // 连字
  (x) => `token: ${x}abc${C(0x1d400)}`,
];

describe("NFKC 对照：15.0 之后新分配的字符", () => {
  const candidates = risky();

  it("JS 的 ICU 确实比 Python 新：找得到规范化时会被动到的未分配码点", () => {
    expect(candidates.length).toBeGreaterThan(30);
  });

  it("这些码点放进各种上下文，normalize 与 decisions.redact 的结果都与 Python 一致", () => {
    const requests: ProbeRequest[] = candidates.flatMap((cp) =>
      CONTEXTS.flatMap((context) => [
        { op: "secrets.call", fn: "normalize", text: context(C(cp)) },
        { op: "secrets.call", fn: "decisions_redact", text: context(C(cp)) },
      ]),
    );
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
    for (const other of others) {
      const mismatches = requests.flatMap((request, index) =>
        JSON.stringify(other[index]) === JSON.stringify(python?.[index]) ? [] : [{ request, python: python?.[index], other: other[index] }],
      );
      expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
    }
  });
});
