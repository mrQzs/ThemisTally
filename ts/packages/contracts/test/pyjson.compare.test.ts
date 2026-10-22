// pyjson 对照测试：同一批输入交给 Python 与 TS（Node、Bun）三种运行方式，结果逐个一致。
// 输入按种子生成（失败时种子在用例名里）：随机的 64 位浮点比特、跨 2^53 的整数、含控制字符与补充平面与
// 孤立代理项的字符串、三种键（全字符串、全整数、两者混用）、现行代码用到的六种参数组合。
// loads 的输入取 Python dumps 的输出，再随机插删字符做出非法的 JSON。
import { describe, expect, it } from "vitest";
import { type Tagged, floatBits } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, prng, runBatch } from "./harness.ts";

const OPTIONS: readonly (readonly [object, boolean])[] = [
  [{ ensure_ascii: false, sort_keys: true }, false],
  [{ ensure_ascii: false, indent: 2, sort_keys: true }, false],
  [{ ensure_ascii: false, sort_keys: true, separators: [",", ":"], allow_nan: false }, true],
  [{ ensure_ascii: false, indent: 2 }, false],
  [{}, false],
  [{ ensure_ascii: true, separators: [",", ":"] }, false],
];

function generator(seed: number): { value: () => Tagged; text: () => string } {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;

  const codePoint = (): number => {
    const roll = rnd();
    if (roll < 0.45) return int(0x20, 0x7e);
    if (roll < 0.55) return int(0x00, 0x1f);
    if (roll < 0.6) return pick([0x22, 0x5c, 0x7f, 0x2f]);
    if (roll < 0.75) return pick([int(0xa0, 0x2ff), int(0x4e00, 0x9fff), int(0xff00, 0xffff), 0x2028, 0x2029]);
    if (roll < 0.9) return int(0x10000, 0x10ffff);
    if (roll < 0.95) return int(0xd800, 0xdfff); // 孤立代理项（偶尔恰好拼成一对，两边看到的照样相同）
    return int(0x80, 0x9f);
  };
  const text = (): string => {
    const length = int(0, 12);
    let out = "";
    for (let index = 0; index < length; index += 1) out += String.fromCodePoint(codePoint());
    return out;
  };
  const bigint = (): bigint => {
    const roll = rnd();
    let magnitude: bigint;
    if (roll < 0.4) magnitude = BigInt(int(0, 1000));
    else if (roll < 0.7) magnitude = 2n ** 53n + BigInt(int(-5, 5));
    else magnitude = BigInt("0x" + Array.from({ length: int(1, 50) }, () => int(0, 15).toString(16)).join(""));
    return rnd() < 0.5 ? -magnitude : magnitude;
  };
  const float = (): number => {
    const roll = rnd();
    if (roll < 0.35) {
      const view = new DataView(new ArrayBuffer(8));
      for (let index = 0; index < 8; index += 1) view.setUint8(index, int(0, 255));
      const value = view.getFloat64(0);
      return Number.isNaN(value) ? NaN : value; // NaN 统一成规范的比特
    }
    if (roll < 0.65) return int(-1_000_000, 1_000_000) / 10 ** int(0, 8);
    if (roll < 0.8) return int(-1000, 1000) * 10 ** int(-30, 30);
    if (roll < 0.9) return pick([0, -0, 0.1, 1e16, 1e15, 1e-5, 1e-4, 5e-324, 1.7976931348623157e308, 2 ** 53]);
    return pick([NaN, Infinity, -Infinity, int(-50, 50)]);
  };
  const key = (kind: "str" | "int" | "mixed", used: Set<string>): Tagged => {
    for (;;) {
      const asInt = kind === "int" || (kind === "mixed" && rnd() < 0.5);
      const tagged: Tagged = asInt ? { t: "int", hex: BigInt(int(-20, 20)).toString(16) } : { t: "str", v: text() };
      const id = JSON.stringify(tagged);
      if (!used.has(id)) {
        used.add(id);
        return tagged;
      }
    }
  };
  const value = (depth = 0): Tagged => {
    const roll = rnd();
    if (depth < 3 && roll < 0.15) return { t: "list", v: Array.from({ length: int(0, 4) }, () => value(depth + 1)) };
    if (depth < 3 && roll < 0.35) {
      const kind = pick(["str", "str", "str", "int", "mixed"] as const);
      const used = new Set<string>();
      return { t: "dict", v: Array.from({ length: int(0, 4) }, () => [key(kind, used), value(depth + 1)] as const) };
    }
    if (roll < 0.5) return { t: "str", v: text() };
    if (roll < 0.65) return { t: "int", hex: ((n) => (n < 0n ? "-" + (-n).toString(16) : n.toString(16)))(bigint()) };
    if (roll < 0.9) return { t: "float", bits: floatBits(float()) };
    if (roll < 0.95) return { t: "bool", v: rnd() < 0.5 };
    return { t: "none" };
  };
  return { value: () => value(0), text };
}

/** 把同一批请求交给每一套实现，断言结果逐个与第一套（Python）相同；返回 Python 的结果。 */
function sameEverywhere(items: readonly ProbeRequest[], label: string): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => ({ impl: impl.name, results: runBatch(impl, items) }));
  for (const other of others) {
    const mismatches = items.flatMap((item, index) =>
      JSON.stringify(other.results[index]) === JSON.stringify(python?.results[index])
        ? []
        : [{ index, request: item, python: python?.results[index], [other.impl]: other.results[index] }],
    );
    expect(mismatches.slice(0, 5), `${label}：${other.impl} 与 python 不一致的条目（共 ${mismatches.length} 条）`).toEqual([]);
  }
  return python?.results ?? [];
}

describe("pyjson 对照：同一输入，各实现逐字节一致", () => {
  it.each([1, 2, 3, 4])("种子 %i：dumps 600 个值、loads 其输出与变形、读改写", (seed) => {
    const gen = generator(seed);
    const rnd = prng(seed * 7 + 1);
    const values = Array.from({ length: 600 }, () => gen.value());
    const dumps = values.map((value, index) => {
      const [options, encode] = OPTIONS[index % OPTIONS.length] ?? [{}, false];
      return { op: "pyjson.dumps", value, options, encode };
    });
    const dumped = sameEverywhere(dumps, `种子 ${seed} dumps`);
    const errors = new Set(dumped.filter((result) => !result.ok).map((result) => result.error));
    expect([...errors].sort(), "生成的值要覆盖到几种报错").toEqual(expect.arrayContaining(["TypeError", "ValueError"]));
    expect(dumped.filter((result) => result.ok).length, "大部分值要能写出来，对照才不是空的").toBeGreaterThan(400);

    const texts = dumped.flatMap((result) => (typeof result["text"] === "string" ? [result["text"]] : []));
    const broken = texts.slice(0, 300).map((text) => {
      const at = Math.floor(rnd() * (text.length + 1));
      return rnd() < 0.5
        ? text.slice(0, at) + gen.text().slice(0, 1) + text.slice(at)
        : text.slice(0, at) + text.slice(at + 1);
    });
    const parsed = sameEverywhere(
      [...texts, ...broken].map((text) => ({ op: "pyjson.loads", text })),
      `种子 ${seed} loads`,
    );
    const failures = parsed.filter((result) => !result.ok).length;
    expect(failures, "变形的输入里要有读不了的").toBeGreaterThan(50);
    expect(parsed.length - failures, "也要有读得了的").toBeGreaterThan(texts.length);
    sameEverywhere(
      texts.slice(0, 300).map((text, index) => {
        const [options, encode] = OPTIONS[(index + 1) % OPTIONS.length] ?? [{}, false];
        return { op: "pyjson.roundtrip", text, options, encode };
      }),
      `种子 ${seed} 读改写`,
    );
  });
});
