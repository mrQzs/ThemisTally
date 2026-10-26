// codekit.protocols.strict_json_loads 的契约（迁移第 ③e 片）：插件的 manifest 与锁经它读，kit_plugins 把错误码写进输出。
// 每条先断言 Python 的结果，再要求 TS 两种运行方式逐字一致；另有按种子生成、再逐字节改坏的对照。
// 转义的反斜杠一律用 String.fromCharCode(92) 拼（源码里不写 \u 转义）。
import { describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, prng, runAgreeing } from "./harness.ts";

const BS = String.fromCharCode(92);
const esc = (hex: string): string => `${BS}u${hex}`;

const strict = (data: Uint8Array | string): ProbeRequest => ({
  op: "protocols.strict",
  data_b64: Buffer.from(typeof data === "string" ? Buffer.from(data, "utf8") : data).toString("base64"),
});

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  /** 期望的错误码；null 表示解析成功。 */
  readonly code: string | null;
}

const ok = (name: string, data: Uint8Array | string): Case => ({ name, request: strict(data), code: null });
const fails = (name: string, data: Uint8Array | string, code: string): Case => ({ name, request: strict(data), code });

function verifyAll(cases: readonly Case[]): void {
  const { python, mismatches } = runAgreeing(cases.map((item) => item.request));
  const wrong = cases.flatMap((item, index) => {
    const result = python[index] as ProbeResult;
    const good = item.code === null ? result.ok === true : result["code"] === item.code;
    return good ? [] : [{ name: item.name, python: JSON.stringify(result) }];
  });
  expect(wrong, "Python 的结果不符合契约").toEqual([]);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
}

const nest = (depth: number, inner = "1"): string => "[".repeat(depth) + inner + "]".repeat(depth);

describe("strict_json_loads", () => {
  it("每个错误码与先后次序", () => {
    verifyAll([
      ok("普通对象", '{"a": [1, 2.5, "x", true, null], "b": {}}'),
      ok("前后空白", " \t\r\n{}\n "),
      ok("顶层是标量", '"text"'),
      ok("顶层是 null", "null"),
      fails("空输入", "", "E_JSON_LIMIT"),
      fails("超过 1 MiB", `"${"x".repeat(1_048_575)}"`, "E_JSON_LIMIT"),
      ok("正好 1 MiB", `"${"x".repeat(1_048_574)}"`),
      fails("BOM", Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from("{}")]), "E_JSON_BOM"),
      fails("不是 UTF-8", Buffer.from([0x7b, 0x22, 0xff, 0x22, 0x3a, 0x31, 0x7d]), "E_JSON_ENCODING"),
      fails("UTF-8 编的代理项", Buffer.from([0x22, 0xed, 0xa0, 0x80, 0x22]), "E_JSON_ENCODING"),
      fails("BOM 先于编码错误", Buffer.from([0xef, 0xbb, 0xbf, 0xff]), "E_JSON_BOM"),
      fails("文法错误", '{"a": }', "E_JSON_SYNTAX"),
      fails("尾随第二个文档", "{} {}", "E_JSON_SYNTAX"),
      fails("字符串里的控制字符", `"a${String.fromCharCode(1)}"`, "E_JSON_SYNTAX"),
      fails("单引号", "{'a': 1}", "E_JSON_SYNTAX"),
      fails("尾随逗号", "[1,]", "E_JSON_SYNTAX"),
      fails("NaN", "[NaN]", "E_JSON_NON_FINITE"),
      fails("Infinity", '{"a": Infinity}', "E_JSON_NON_FINITE"),
      fails("-Infinity", "-Infinity", "E_JSON_NON_FINITE"),
      fails("浮点溢出", "1e400", "E_JSON_NON_FINITE"),
      fails("负的浮点溢出", "[-1e400]", "E_JSON_NON_FINITE"),
      ok("最小的次正规数", "5e-324"),
      ok("下溢成 0", "1e-400"),
      ok("2^53-1", "9007199254740991"),
      ok("-(2^53-1)", "-9007199254740991"),
      fails("2^53", "9007199254740992", "E_INTEGER_RANGE"),
      fails("-2^53", "-9007199254740992", "E_INTEGER_RANGE"),
      fails("17 位", "10000000000000000", "E_INTEGER_RANGE"),
      fails("很长的整数", "1".repeat(5000), "E_INTEGER_RANGE"),
      ok("16 位的负数", "-1000000000000000"),
      ok("2^53 写成浮点", "9007199254740992.0"),
      ok("-0", "-0"),
      fails("重复的键", '{"a": 1, "a": 2}', "E_JSON_DUPLICATE_KEY"),
      fails("转义之后相同的键", `{"a": 1, "${esc("0061")}": 2}`, "E_JSON_DUPLICATE_KEY"),
      fails("嵌套里的重复键", '{"x": [{"b": 1, "b": 1}]}', "E_JSON_DUPLICATE_KEY"),
      fails("键里的孤立代理项", `{"${esc("d800")}": 1}`, "E_JSON_UNICODE"),
      fails("值里的孤立代理项", `["${esc("dc00")}"]`, "E_JSON_UNICODE"),
      ok("成对的代理项", `["${esc("d83d")}${esc("de00")}"]`),
      fails("高代理项后面不是低代理项", `["${esc("d83d")}${esc("0041")}"]`, "E_JSON_UNICODE"),
      ok("嵌套 64 层", nest(64)),
      fails("嵌套 65 层", nest(65), "E_JSON_LIMIT"),
      fails("嵌套很深（解码器递归超限）", nest(5000), "E_JSON_LIMIT"),
      ok("字符串里的括号不算嵌套（外面一层加里面 63 层）", `[${nest(63, '"[[[[[[[["')}, ${nest(2)}]`),
      fails("外面一层加里面 64 层", `[${nest(64, '"x"')}]`, "E_JSON_LIMIT"),
      ok("字符串里的括号不算嵌套（63 层）", nest(63, '"[[[[[[[[[[[[[["')),
      fails("先遇到的是重复键", '[{"a": 1, "a": 2}, NaN]', "E_JSON_DUPLICATE_KEY"),
      fails("先遇到的是非有限数", '[NaN, {"a": 1, "a": 2}]', "E_JSON_NON_FINITE"),
      fails("重复的键先于它的值", '{"a": 1, "a": NaN}', "E_JSON_DUPLICATE_KEY"),
      fails("值先于后面的重复键", '{"a": NaN, "a": 1}', "E_JSON_NON_FINITE"),
      fails("深度先于里面的坏数", nest(65, "NaN"), "E_JSON_LIMIT"),
      fails("整数范围先于后面的代理项", `[10000000000000000, "${esc("d800")}"]`, "E_INTEGER_RANGE"),
      fails("文法错误先于非有限数", "[NaN,]", "E_JSON_SYNTAX"),
    ]);
  });

  it("按种子生成的文档逐字节改坏：每个种子 600 份", () => {
    const atoms = ["0", "-0", "1.5", "1e400", "9007199254740991", "9007199254740992", "NaN", "true", "null", '"x"', `"${esc("d800")}"`, '"ſK"', '""'];
    for (const seed of [31, 32, 33]) {
      const next = prng(seed);
      const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
      const value = (depth: number): string => {
        const roll = next();
        if (depth > 4 || roll < 0.45) return pick(atoms);
        if (roll < 0.7) return `[${Array.from({ length: Math.floor(next() * 4) }, () => value(depth + 1)).join(", ")}]`;
        const keys = Array.from({ length: Math.floor(next() * 4) }, () => pick(["a", "b", "c", esc("0061"), esc("d800")]));
        return `{${keys.map((key) => `"${key}": ${value(depth + 1)}`).join(", ")}}`;
      };
      const requests: ProbeRequest[] = [];
      for (let index = 0; index < 600; index += 1) {
        const bytes = Buffer.from(value(0), "utf8");
        // 一半原样，一半改一个字节、删一个字节或插一个字节
        if (next() < 0.5 && bytes.length) {
          const at = Math.floor(next() * bytes.length);
          const roll = next();
          const mutated = roll < 0.4 ? Buffer.from(bytes) : roll < 0.7 ? Buffer.concat([bytes.subarray(0, at), bytes.subarray(at + 1)]) : Buffer.concat([bytes.subarray(0, at), Buffer.from([Math.floor(next() * 256)]), bytes.subarray(at)]);
          if (roll < 0.4) mutated[at] = Math.floor(next() * 256);
          requests.push(strict(mutated));
        } else {
          requests.push(strict(bytes));
        }
      }
      const { mismatches } = runAgreeing(requests);
      expect(mismatches.slice(0, 3), `种子 ${seed}：共 ${mismatches.length} 条不一致`).toEqual([]);
    }
  });
});
