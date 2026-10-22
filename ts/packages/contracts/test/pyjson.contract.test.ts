// pyjson 的行为契约：Python 3.12 标准库 json.dumps / json.loads 的写法，逐字节。每套实现都要逐条通过，
// Python 实现先过（契约描述的就是现行行为）。参数组合取自现行代码（计划第 1.4 节）：
//   CANON   ensure_ascii=False, sort_keys=True               kit_hub.canonical_json、账本每一行
//   STATE   ensure_ascii=False, indent=2, sort_keys=True     kit_hub.canonical_state（state.json）
//   BYTES   ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False，再 encode("utf-8")   codekit 的摘要
//   EVIDENCE ensure_ascii=False, indent=2                    pi_dispatch.write_json（证据目录）
//   DEFAULT 全用缺省值（ensure_ascii=True）
import { describe, expect, it } from "vitest";
import type { Tagged } from "../src/tagged.ts";
import { floatBits } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, runBatch } from "./harness.ts";

const CANON = { ensure_ascii: false, sort_keys: true };
const STATE = { ensure_ascii: false, indent: 2, sort_keys: true };
const BYTES = { ensure_ascii: false, sort_keys: true, separators: [",", ":"], allow_nan: false };
const EVIDENCE = { ensure_ascii: false, indent: 2 };
const DEFAULT = {};

const N: Tagged = { t: "none" };
const B = (v: boolean): Tagged => ({ t: "bool", v });
const I = (v: bigint | number): Tagged => {
  const big = BigInt(v);
  return { t: "int", hex: (big < 0n ? "-" : "") + (big < 0n ? -big : big).toString(16) };
};
const F = (v: number): Tagged => ({ t: "float", bits: floatBits(v) });
const S = (v: string): Tagged => ({ t: "str", v });
const L = (...v: Tagged[]): Tagged => ({ t: "list", v });
const D = (...v: [Tagged | string, Tagged][]): Tagged => ({
  t: "dict",
  v: v.map(([key, value]) => [typeof key === "string" ? S(key) : key, value] as const),
});

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  readonly expect: ProbeResult;
}

const dumps = (name: string, value: Tagged, options: object, text: string): Case => ({
  name,
  request: { op: "pyjson.dumps", value, options },
  expect: { ok: true, text },
});
const dumpsFails = (name: string, value: Tagged, options: object, error: string, encode = false): Case => ({
  name,
  request: { op: "pyjson.dumps", value, options, encode },
  expect: { ok: false, error },
});
const loads = (name: string, text: string, value: Tagged): Case => ({
  name,
  request: { op: "pyjson.loads", text },
  expect: { ok: true, value },
});
const loadsFails = (name: string, text: string, error: string): Case => ({
  name,
  request: { op: "pyjson.loads", text },
  expect: { ok: false, error },
});

// 转义用例的原文：引号、反斜杠、BS、FF、LF、CR、TAB、NUL、US、DEL、空格、é、空格、😀
const TRICKY = '"\\\b\f\n\r\t\u0000\u001f\u007f é 😀';

const DUMPS: readonly Case[] = [
  dumps(
    "J01 float 的 repr：最短往返，decpt 不在 (-4, 16] 时写指数，指数至少两位",
    L(F(1), F(-0), F(0), F(1e16), F(1e15), F(1e-5), F(0.0001), F(1.5e300), F(5e-324), F(0.1), F(123456789012345680), F(1.7976931348623157e308)),
    CANON,
    "[1.0, -0.0, 0.0, 1e+16, 1000000000000000.0, 1e-05, 0.0001, 1.5e+300, 5e-324, 0.1, 1.2345678901234568e+17, 1.7976931348623157e+308]",
  ),
  dumps("J02 NaN 与无穷：缺省 allow_nan=True", L(F(NaN), F(Infinity), F(-Infinity)), CANON, "[NaN, Infinity, -Infinity]"),
  dumpsFails("J03 allow_nan=False 时 NaN 报 ValueError", L(F(NaN)), BYTES, "ValueError"),
  dumps("J04 大整数原样写出", L(I(2n ** 53n + 1n), I(-(2n ** 64n)), I(0)), CANON, "[9007199254740993, -18446744073709551616, 0]"),
  dumpsFails("J05 超过 4300 位的整数报 ValueError", I(10n ** 4300n), CANON, "ValueError"),
  dumps(
    "J06 sort_keys 按码点排：U+FF5E 在 U+1F600 之前（按 UTF-16 码元排就反了）",
    D(["😀", I(3)], ["～", I(2)], ["a", I(1)]),
    CANON,
    '{"a": 1, "～": 2, "😀": 3}',
  ),
  dumps("J07 sort_keys 按原始的键排：整数键 9 在 10 之前，排完才转成字符串", D([I(10), S("a")], [I(9), S("b")]), CANON, '{"9": "b", "10": "a"}'),
  dumpsFails("J08 sort_keys 遇到 str 与 int 混用的键报 TypeError", D(["a", I(1)], [I(1), I(2)]), CANON, "TypeError"),
  dumps(
    "J09 非字符串键的写法：float 的 repr、true、null、int（-0.0 作键不在契约里，见 pyjson.ts 的说明）",
    D([F(1.5), N], [B(true), N], [N, N], [I(-3), N], [F(-2.5e-7), N]),
    DEFAULT,
    '{"1.5": null, "true": null, "null": null, "-3": null, "-2.5e-07": null}',
  ),
  dumps(
    "J10 不排序时保持插入顺序（JS 对象会把整数样的键提前）；indent 下项分隔符是 \",\"",
    D(["b", I(1)], ["a", I(2)], ["10", I(3)], ["2", I(4)]),
    EVIDENCE,
    '{\n  "b": 1,\n  "a": 2,\n  "10": 3,\n  "2": 4\n}',
  ),
  dumps(
    "J11 indent 下的空容器写成 [] 与 {}",
    D(["l", L()], ["d", D()], ["n", L(L(), D())]),
    EVIDENCE,
    '{\n  "l": [],\n  "d": {},\n  "n": [\n    [],\n    {}\n  ]\n}',
  ),
  dumps(
    "J12 state.json 的写法：indent=2 加排序，逐层缩进",
    D(["b", D(["y", I(1)], ["x", L(I(1), I(2))])], ["a", S("x")]),
    STATE,
    '{\n  "a": "x",\n  "b": {\n    "x": [\n      1,\n      2\n    ],\n    "y": 1\n  }\n}',
  ),
  dumps("J13 缺省分隔符是 \", \" 与 \": \"", D(["a", L(I(1), I(2))], ["b", B(false)]), DEFAULT, '{"a": [1, 2], "b": false}'),
  dumps(
    "J14 ensure_ascii=False：只转义引号、反斜杠与 0x00–0x1f；DEL 与非 ASCII 原样",
    S(TRICKY),
    CANON,
    '"' + '\\"' + "\\\\" + "\\b" + "\\f" + "\\n" + "\\r" + "\\t" + "\\u0000" + "\\u001f" + "\u007f" + " é 😀" + '"',
  ),
  dumps(
    "J15 ensure_ascii=True：空格到 ~ 之外一律 \\uXXXX（小写），补充平面写成代理对",
    S(TRICKY),
    DEFAULT,
    '"' + '\\"' + "\\\\" + "\\b" + "\\f" + "\\n" + "\\r" + "\\t" + "\\u0000" + "\\u001f" + "\\u007f" + " \\u00e9 \\ud83d\\ude00" + '"',
  ),
  dumps("J16 孤立代理项：ensure_ascii=False 时原样留在字符串里", S("a\ud800b"), CANON, '"a\ud800b"'),
  dumps("J17 孤立代理项：ensure_ascii=True 时写成 \\ud800", S("a\ud800b"), DEFAULT, '"a\\ud800b"'),
  dumpsFails("J18 孤立代理项：encode(\"utf-8\") 时报 UnicodeEncodeError", S("a\ud800b"), BYTES, "UnicodeEncodeError", true),
  dumps("J19 紧凑分隔符", D(["b", L(I(1), F(2.5))], ["a", S("中")]), BYTES, '{"a":"中","b":[1,2.5]}'),
  dumps("J20 true、false、null", L(B(true), B(false), N), DEFAULT, "[true, false, null]"),
  dumpsFails("J21 编码报错的位置按码点数（前面的补充平面字符算一个）", S("😀" + String.fromCharCode(0xd800)), BYTES, "UnicodeEncodeError", true),
  dumpsFails("J22 连着几个孤立代理项报一个范围", S("a" + String.fromCharCode(0xd800, 0xd800)), BYTES, "UnicodeEncodeError", true),
];

const LOADS: readonly Case[] = [
  loads("K01 整数与浮点分开：1 是 int，1.0、1e5、1E+2 是 float", "[1, 1.0, 1e5, 1E+2]", L(I(1), F(1), F(1e5), F(100))),
  loads("K02 -0 是 int 0，-0.0 是 float -0.0", "[-0, -0.0]", L(I(0), F(-0))),
  loads("K03 大整数不丢精度；1e400 读成 inf", "[9007199254740993, 1e400]", L(I(2n ** 53n + 1n), F(Infinity))),
  loads("K04 接受 NaN、Infinity、-Infinity", "[NaN, Infinity, -Infinity]", L(F(NaN), F(Infinity), F(-Infinity))),
  loads("K05 重复的键：保留第一次出现的位置、最后一次的值", '{"a": 1, "b": 2, "a": 3}', D(["a", I(3)], ["b", I(2)])),
  loads("K06 \\u 转义：代理对合成一个字符，孤立代理项照留，十六进制大小写都认", '["\\ud83d\\ude00", "\\ud800", "\\ud800\\u0041", "\\u00E9"]', L(S("😀"), S("\ud800"), S("\ud800A"), S("é"))),
  loads("K07 空白只认空格、TAB、CR、LF", " \t\n\r[ 1 , 2 ]\r\n", L(I(1), I(2))),
  loads("K08 字符串里的 DEL 与非 ASCII 原样", '"\u007f中"', S("\u007f中")),
  loadsFails("K09 开头的 BOM 报 JSONDecodeError", "\ufeff{}", "JSONDecodeError"),
  loadsFails("K10 前导零", "01", "JSONDecodeError"),
  loadsFails("K11 小数点后没有数字", "1.", "JSONDecodeError"),
  loadsFails("K12 以小数点开头", ".5", "JSONDecodeError"),
  loadsFails("K13 正号", "+1", "JSONDecodeError"),
  loadsFails("K14 字符串里的原始换行（strict）", '"a\nb"', "JSONDecodeError"),
  loadsFails("K15 不认识的转义", '"\\x41"', "JSONDecodeError"),
  loadsFails("K16 \\u 后不足四位", '"\\u12"', "JSONDecodeError"),
  loadsFails("K17 不间断空格不算空白", "\u00a0[]", "JSONDecodeError"),
  loadsFails("K18 数组的尾逗号", "[1,]", "JSONDecodeError"),
  loadsFails("K19 对象的尾逗号", '{"a": 1,}', "JSONDecodeError"),
  loadsFails("K20 超过 4300 位的整数报 ValueError", "1" + "0".repeat(4300), "ValueError"),
  loadsFails("K21 空串", "", "JSONDecodeError"),
  loadsFails("K22 多余的数据", "[1] x", "JSONDecodeError"),
  loadsFails("K23 键不是字符串", "{1: 2}", "JSONDecodeError"),
];

const ROUNDTRIP: readonly Case[] = [
  {
    name: "R01 读进来再按 state.json 的写法写回：1.0、大整数、-0.0 都还原",
    request: { op: "pyjson.roundtrip", text: '{"b": 1.0, "a": 9007199254740993, "c": -0.0}', options: STATE },
    expect: { ok: true, text: '{\n  "a": 9007199254740993,\n  "b": 1.0,\n  "c": -0.0\n}' },
  },
  {
    name: "R02 读进来按证据目录的写法写回：键的顺序不变，中文不转义",
    request: { op: "pyjson.roundtrip", text: '{"状态":"NEEDS_REVIEW","2":[],"1":{}}', options: EVIDENCE },
    expect: { ok: true, text: '{\n  "状态": "NEEDS_REVIEW",\n  "2": [],\n  "1": {}\n}' },
  },
  {
    name: "R03 读进来按摘要的写法写成字节：UTF-8",
    request: { op: "pyjson.roundtrip", text: '{"b": 2.50, "a": "中"}', options: BYTES, encode: true },
    expect: { ok: true, b64: Buffer.from('{"a":"中","b":2.5}', "utf8").toString("base64") },
  },
];

// 报错文字也是契约：Python 会经 str(exc) 把它写进报错、证据与信件（themistally-15 审阅时数出 9 处）。
// JSONDecodeError 的格式是 "<msg>: line <行> column <列> (char <位置>)"，位置按码点数。
// 按用例编号查；没列的报错（只有 TypeError）只比较异常类型。
const MESSAGES: Record<string, string> = {
  J03: "Out of range float values are not JSON compliant: nan",
  J05: "Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit",
  J18: "'utf-8' codec can't encode character '\\ud800' in position 2: surrogates not allowed",
  J21: "'utf-8' codec can't encode character '\\ud800' in position 2: surrogates not allowed",
  J22: "'utf-8' codec can't encode characters in position 2-3: surrogates not allowed",
  K09: "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)",
  K10: "Extra data: line 1 column 2 (char 1)",
  K11: "Extra data: line 1 column 2 (char 1)",
  K12: "Expecting value: line 1 column 1 (char 0)",
  K13: "Expecting value: line 1 column 1 (char 0)",
  K14: "Invalid control character at: line 1 column 3 (char 2)",
  K15: "Invalid \\escape: line 1 column 2 (char 1)",
  K16: "Invalid \\uXXXX escape: line 1 column 3 (char 2)",
  K17: "Expecting value: line 1 column 1 (char 0)",
  K18: "Expecting value: line 1 column 4 (char 3)",
  K19: "Expecting property name enclosed in double quotes: line 1 column 9 (char 8)",
  K20: "Exceeds the limit (4300 digits) for integer string conversion: value has 4301 digits; use sys.set_int_max_str_digits() to increase the limit",
  K21: "Expecting value: line 1 column 1 (char 0)",
  K22: "Extra data: line 1 column 5 (char 4)",
  K23: "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
  K24: "Invalid \\uXXXX escape: line 1 column 3 (char 2)",
  K25: "Invalid \\uXXXX escape: line 1 column 9 (char 8)",
  K26: "Extra data: line 1 column 5 (char 4)",
  K27: "Expecting ':' delimiter: line 3 column 7 (char 18)",
  K28: "Extra data: line 2 column 2 (char 5)",
  K29: "Unterminated string starting at: line 1 column 2 (char 1)",
  K30: "Invalid \\uXXXX escape: line 1 column 9 (char 8)",
  P01: "Expecting value: line 1 column 1 (char 0)",
};

const POSITIONS: readonly Case[] = [
  loadsFails("K24 \\u 后四位正好到结尾：Python 要求后面还有字符", '"\\u0041', "JSONDecodeError"),
  loadsFails("K25 代理对的第二个转义不是十六进制：指向第二个 u", '"\\ud800\\uZZZZ"', "JSONDecodeError"),
  loadsFails("K26 位置按码点数：补充平面字符算一个", '"😀" x', "JSONDecodeError"),
  loadsFails("K27 行号与列号", '{\n  "a": 1,\n  "b" 2\n}', "JSONDecodeError"),
  loadsFails("K28 换行之后的列号也按码点数", '"😀"\n x', "JSONDecodeError"),
  loadsFails("K29 反斜杠是最后一个字符", '["\\', "JSONDecodeError"),
  loadsFails("K30 高代理项后面剩下的不够一个转义：不配对，第二个转义自己报错", '"\\ud800\\udc00', "JSONDecodeError"),
];

const BOM = String.fromCharCode(0xfeff);
const RAW: readonly Case[] = [
  { name: "P01 raw_decode 不跳过开头的空白", request: { op: "pyjson.raw_decode", text: '  {"a": 1}', index: 0 }, expect: { ok: false, error: "JSONDecodeError" } },
  { name: "P02 raw_decode 从中间开始、后面可以跟别的", request: { op: "pyjson.raw_decode", text: 'xx{"a": 1} tail', index: 2 }, expect: { ok: true, value: D(["a", I(1)]), end: 10 } },
  { name: "P03 raw_decode 的下标与 end 都按码点", request: { op: "pyjson.raw_decode", text: '😀😀[1, "😀"] rest', index: 2 }, expect: { ok: true, value: L(I(1), S("😀")), end: 10 } },
  { name: "P04 raw_decode 不查 BOM", request: { op: "pyjson.raw_decode", text: BOM + "[1]", index: 1 }, expect: { ok: true, value: L(I(1)), end: 4 } },
];

describe.each(IMPLS)("pyjson 契约 impl=$name", (impl) => {
  it.each([
    ["dumps", DUMPS],
    ["loads", LOADS],
    ["报错位置", POSITIONS],
    ["raw_decode", RAW],
    ["读改写", ROUNDTRIP],
  ] as const)("%s：逐条与 Python 3.12 的写法与报错文字一致", (_label, cases) => {
    const results = runBatch(
      impl,
      cases.map((item) => item.request),
    );
    const got = Object.fromEntries(cases.map((item, index) => [item.name, results[index]]));
    const want = Object.fromEntries(
      cases.map((item) => {
        if (item.expect.ok) return [item.name, item.expect];
        const id = item.name.split(" ")[0] ?? "";
        return [item.name, { ...item.expect, message: MESSAGES[id] ?? expect.any(String) }];
      }),
    );
    expect(got).toEqual(want);
  });
});
