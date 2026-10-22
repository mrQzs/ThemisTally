// secrets 的契约：疑似凭据的检测与脱敏（pi_dispatch、codekit.secrets、codekit.decisions 的现行行为）。脱敏结果会进证据，
// 按计划 §3.4 逐字比较。每套实现逐条通过，Python 实现先过。特殊字符一律用 String.fromCodePoint 拼（不写转义，
// 免得编辑工具把它换成实际字符）。
import { describe, expect, it } from "vitest";
import type { Tagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const ESC = C(0x1b);
const LONG_S = C(0x17f); // ſ：re.I 下匹配 s
const KELVIN = C(0x212a); // K：re.I 下匹配 k
const CJK = C(0x4e2d); // 中：Python 的 \w
const ZWSP = C(0x200b); // 零宽空格（Cf）
const BEL = C(0x07);

const S = (v: string): Tagged => ({ t: "str", v });
const I = (n: number): Tagged => ({ t: "int", hex: n.toString(16) });
const L = (...v: Tagged[]): Tagged => ({ t: "list", v });
const D = (...v: [string, Tagged][]): Tagged => ({ t: "dict", v: v.map(([key, value]) => [S(key), value] as const) });

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  readonly expect: ProbeResult;
}

const text = (name: string, fn: string, input: string, output: string, extra: object = {}): Case => ({
  name,
  request: { op: "secrets.call", fn, text: input, ...extra },
  expect: { ok: true, text: output },
});
const flag = (name: string, fn: string, request: object, result: boolean): Case => ({
  name,
  request: { op: "secrets.call", fn, ...request },
  expect: { ok: true, result },
});

const CASES: readonly Case[] = [
  text("S01 键值对：值遮到行尾", "redact_secrets", "token: abc123secret\nnext line", "token: <redacted>\nnext line"),
  text("S02 Bearer 先按令牌遮，键再遮一次", "redact_secrets", "Authorization: Bearer abcdefghijklmnop", "Authorization: <redacted>"),
  text(
    "S03 PEM 私钥整块遮掉",
    "redact_secrets",
    "x\n-----BEGIN RSA PRIVATE KEY-----\nMIIBabc\n-----END RSA PRIVATE KEY-----\ny",
    "x\n<redacted>\ny",
  ),
  text("S04 PEM 没有结束行：遮到结尾", "redact_secrets", "a -----BEGIN PRIVATE KEY-----\nabc\ndef", "a <redacted>"),
  text(
    "S05 嵌着的 JSON 按结构脱敏后重新写出，计数类的字段不动",
    "redact_secrets",
    'resp {"tokenCount": 5, "api_key": "zzz", "nested": {"password": ["a", 1]}} end',
    'resp {"tokenCount": 5, "api_key": "<redacted>", "nested": {"password": ["<redacted>", 1]}} end',
  ),
  text("S06 值在本行结束不了：遮掉这条输出的其余部分", "redact_secrets", "password: {\n  a\n}\nmore", "password: <redacted>"),
  text("S07 先去掉 ANSI 样式", "redact_secrets", `${ESC}[31mtoken=abc${ESC}[0m`, "token=<redacted>"),
  text("S08 常见令牌前缀", "redact_secrets", "use sk-ABCDEFGHIJKLMNOPQRSTUV now", "use <redacted> now"),
  text("S09 Python 的 \\b 按 Unicode：中文紧贴令牌时没有词边界，不遮", "redact_secrets", `${CJK}sk-12345678abcd`, `${CJK}sk-12345678abcd`),
  text("S10 re.I 下 ſ 匹配 s：ſecret 也算凭据键", "redact_secrets", `${LONG_S}ecret: hunter2`, `${LONG_S}ecret: <redacted>`),
  text("S11 re.I 下开尔文符号匹配 k", "redact_secrets", `api_${KELVIN}ey: abc`, `api_${KELVIN}ey: <redacted>`),
  text("S12 只遮令牌形状、不动键值对", "redact_tokens", "password: x and ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcd", "password: x and <redacted>"),
  text(
    "S13 decisions：邮箱、国际电话、长十六进制",
    "decisions_redact",
    `mail a.b@example.com call +1 415 555 0100 hash ${"a".repeat(40)}`,
    "mail [email] call [phone] hash [hex]",
  ),
  text("S14 decisions：赋值保留变量名", "decisions_redact", "MY_API_KEY = abc123", "MY_API_KEY=[secret]"),
  text("S15 decisions：NFKC 折叠全角，去掉 Cf、Cc 字符", "normalize", `${C(0xff46, 0xff55, 0xff4c, 0xff4c)}${ZWSP}width${BEL}`, "fullwidth"),
  text("S16 decisions：超过上限按码点取头尾", "decisions_redact", "abcdefghijklmnop", "abcde\n[...]\nlmnop", { limit: 10 }),
  flag("S17 looks_like_secret：去掉两头空白后 8 个可打印字符", "looks_like_secret", { value: S("  abcdefgh  ") }, true),
  flag("S18 looks_like_secret：中间有空白不算", "looks_like_secret", { value: S("abcd efgh ij") }, false),
  flag("S19 looks_like_secret：不是字符串不算", "looks_like_secret", { value: I(123456789) }, false),
  flag("S20 is_sensitive", "is_sensitive", { text: "Authorization: x" }, true),
  {
    name: "S21 secret_like_paths：凭据键、令牌形状的值；credential_env 只放变量名，不算",
    request: {
      op: "secrets.call",
      fn: "secret_like_paths",
      value: D(["profiles", D(["p1", D(["credential_env", S("MY_KEY")], ["token", S("x")])])], ["list", L(S("sk-ABCDEFGHIJKLMNOPQRST"))]),
    },
    expect: { ok: true, paths: ["profiles.p1.token", "list.0"] },
  },
  {
    name: "S22 redact_json 的白名单：登记过的位置通过校验就原样保留",
    request: {
      op: "secrets.call",
      fn: "redact_json",
      value: D(["decisions", D(["api_key_env", S("JEV_KEY")])], ["password", S("p")]),
      allow: [{ path: ["decisions", "api_key_env"], check: { kind: "env_name" } }],
    },
    expect: { ok: true, value: D(["decisions", D(["api_key_env", S("JEV_KEY")])], ["password", S("<redacted>")]) },
  },
  {
    name: "S23 redact_json：键名本身像令牌，连键一起遮",
    request: { op: "secrets.call", fn: "redact_json", value: D(["sk-ABCDEFGHIJKLMNOPQRST", I(1)], ["ok", S("fine")]) },
    expect: { ok: true, value: D(["<redacted>", I(1)], ["ok", S("fine")]) },
  },
  {
    name: "S24 Python 的 $（不带 MULTILINE）在末尾换行之前也算：键名 token 加换行也是凭据键",
    request: { op: "secrets.call", fn: "redact_json", value: D(["token\n", S("x")]) },
    expect: { ok: true, value: D(["token\n", S("<redacted>")]) },
  },
  flag("S25 Python 的 \\s 含 0x1c：Bearer 加 0x1c 加令牌也算", "token_shaped", { text: `Bearer${C(0x1c)}abcdefghij` }, true),
  text("S26 截断按码点：补充平面字符不切成两半", "decisions_redact", C(0x1f600).repeat(8), `${C(0x1f600, 0x1f600)}\n[...]\n${C(0x1f600, 0x1f600)}`, { limit: 4 }),
  text("S27 截断上限为 1：Python 的 out[-0:] 是整串", "decisions_redact", "abc", "\n[...]\nabc", { limit: 1 }),
  text("S28 YAML 块标记：值在后面几行，遮掉其余部分", "redact_secrets", "token: |\n  line1\nnext", "token: <redacted>"),
  text(
    "S29 嵌着的 JSON 里的孤立代理项：重新写出时恢复成转义",
    "redact_secrets",
    `{"k": "${C(0x5c)}ud800"}`,
    `{"k": "${C(0x5c)}ud800"}`,
  ),
  flag("S30 looks_like_secret 按码点数：7 个补充平面字符不到 8", "looks_like_secret", { value: S(C(0x1f600).repeat(7)) }, false),
  flag("S31 looks_like_secret：有不可打印的字符不算", "looks_like_secret", { value: S(`abcdefgh${C(0x07)}`) }, false),
  text("S32 高熵串只遮大写、小写、数字都有的", "decisions_redact", `x ${"g".repeat(40)}`, `x ${"g".repeat(40)}`),
  text("S33 邮箱前面是 +：Python 的 \\b 要求前一个是单词字符，+ 留下", "decisions_redact", " +a@b.com", " +[email]"),
  text("S34 键值对的值连同缩进的续行一起遮", "redact_secrets", "token: a\n  b\nc", "token: <redacted>\nc"),
];

describe.each(IMPLS)("secrets 契约 impl=$name", (impl) => {
  it("逐条与 Python 的脱敏结果一致", () => {
    const results = runBatch(
      impl,
      CASES.map((item) => item.request),
    );
    expect(Object.fromEntries(CASES.map((item, index) => [item.name, results[index]]))).toEqual(
      Object.fromEntries(CASES.map((item) => [item.name, item.expect])),
    );
  });
});
