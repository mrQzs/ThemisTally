// secrets 对照测试：同一批输入交给 Python 与 TS（Node、Bun），脱敏结果逐字一致。
// 随机文本偏向边界：凭据片段（键名、令牌前缀、AKIA、JWT、邮箱、电话、长十六进制、高熵串、PEM、嵌着凭据的 JSON、
// ANSI）紧贴各种边界字符（İ ı ſ K、0x1c–0x1f、0x85、BOM、U+2028/2029、补充平面字母、组合符、全角数字、中文）
// 与分隔符（: = 空白 换行 引号 反斜杠）。特殊字符一律用码点拼。
import { describe, expect, it } from "vitest";
import type { Tagged } from "../src/tagged.ts";
import { IMPLS, type ProbeRequest, type ProbeResult, prng, runBatch } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);

const BOUNDARY = [
  C(0x130), C(0x131), C(0x17f), C(0x212a), C(0x1c), C(0x1d), C(0x1e), C(0x1f), C(0x85), C(0xfeff), C(0x2028), C(0x2029),
  C(0x1d400), C(0x301), C(0xff11), C(0x4e2d), C(0x0), C(0x7), C(0xa0), C(0x200b), C(0xe9), "_", "-", ".", "/", "+", "=",
];
const SEPARATORS = [":", "=", " ", "  ", "\t", "\n", "\n  ", "\r\n", '"', "'", "\\", '\\"', ": ", " = ", ",", "{", "}", "[", "]"];
const KEYS = ["token", "password", "api_key", "API-KEY", "secret", "Authorization", "auth_token", "private key", "passwd", "credential",
  "x-api-key", "tokenCount", "hasApiKey", "MY_SECRET_KEY", "client_secret", "session_cookie", "Bearer"];
const WORDS = ["hello", "INFO", "[2026-09-23 12:34:56]", "value", "abc", "x", "ok", "null", "true", "123", "1.5e3"];

function generator(seed: number) {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;
  const run = (alphabet: string, length: number): string => Array.from({ length }, () => alphabet[int(0, alphabet.length - 1)]).join("");
  const ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const fragment = (): string => {
    switch (int(0, 15)) {
      case 0:
        return `${pick(KEYS)}${pick([":", "=", ": ", " = ", '": "', "':'"])}${run(ALNUM, int(0, 20))}`;
      case 1:
        return `Bearer ${run(ALNUM + "._~+/=-", int(4, 30))}`;
      case 2:
        return `${pick(["sk", "pk", "rk", "ghp", "gho", "github_pat", "xoxb", "SK", "Ghp"])}${pick(["-", "_"])}${run(ALNUM + "_-", int(4, 40))}`;
      case 3:
        return pick(["AKIA", "AIza", "apikey_", "eyJ"]) + run(ALNUM, int(10, 40)) + (rnd() < 0.3 ? `.${run(ALNUM, 12)}.${run(ALNUM, 8)}` : "");
      case 4:
        return `${run("abcdef0123456789", int(30, 50))}`;
      case 5:
        return `${run(ALNUM + "+/_-", int(30, 50))}${pick(["", "=", "=="])}`;
      case 6:
        return `${run("abc.def", int(1, 8))}@${run("example", int(1, 7))}.${pick(["com", "io", "c"])}`;
      case 7:
        return `+${int(1, 999)}${pick([" ", "-", ".", ""])}${run("0123456789 -.", int(5, 16))}${int(0, 9)}`;
      case 8:
        return pick(["-----BEGIN RSA PRIVATE KEY-----\nMIIB", "-----END RSA PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----"]);
      case 9:
        return pick([
          '{"api_key": "zz", "n": 1}',
          '{"tokenCount": 3}',
          '[1, "sk-ABCDEFGHIJKLMNOPQRST"]',
          '{"a": {"password": ["x", 2]}, "a": "dup"}',
          '{"k": "' + C(0x5c) + 'ud800"}',
          "[2026-09-23 12:34:56]",
          '{"x": [1, 2',
        ]);
      case 10:
        return `${C(0x1b)}[${int(0, 99)}m`;
      case 11:
        return pick(["|", ">", "|-", ">+", "|2-", "| # c"]);
      case 12:
        return pick(WORDS);
      case 13:
        return pick(BOUNDARY);
      default:
        return pick(SEPARATORS);
    }
  };
  const textOf = (): string => Array.from({ length: int(1, 14) }, fragment).join(rnd() < 0.5 ? "" : pick(SEPARATORS));
  const value = (depth = 0): Tagged => {
    const roll = rnd();
    if (depth < 3 && roll < 0.25) {
      const used = new Set<string>();
      const entries: (readonly [Tagged, Tagged])[] = [];
      for (let index = 0; index < int(0, 4); index += 1) {
        const key = rnd() < 0.6 ? pick([...KEYS, "credential_env", "api_key_env", "profiles", "decisions", "env_keep"]) : textOf();
        if (used.has(key)) continue;
        used.add(key);
        entries.push([{ t: "str", v: key }, value(depth + 1)]);
      }
      return { t: "dict", v: entries };
    }
    if (depth < 3 && roll < 0.4) return { t: "list", v: Array.from({ length: int(0, 3) }, () => value(depth + 1)) };
    if (roll < 0.85) return { t: "str", v: rnd() < 0.3 ? pick(["", "MY_KEY", "ok", "a-b-c"]) : textOf() };
    if (roll < 0.92) return { t: "int", hex: int(0, 999).toString(16) };
    return rnd() < 0.5 ? { t: "bool", v: rnd() < 0.5 } : { t: "none" };
  };
  return { textOf, value, int, rnd };
}

function sameEverywhere(items: readonly ProbeRequest[], label: string): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => ({ impl: impl.name, results: runBatch(impl, items) }));
  for (const other of others) {
    const mismatches = items.flatMap((item, index) =>
      JSON.stringify(other.results[index]) === JSON.stringify(python?.results[index])
        ? []
        : [{ index, request: item, python: python?.results[index], [other.impl]: other.results[index] }],
    );
    expect(mismatches.slice(0, 3), `${label}：${other.impl} 与 python 不一致的条目（共 ${mismatches.length} 条）`).toEqual([]);
  }
  return python?.results ?? [];
}

const TEXT_FNS = ["redact_secrets", "redact_tokens", "token_shaped", "normalize", "is_sensitive", "decisions_redact"] as const;

describe("secrets 对照：同一输入，各实现的脱敏结果逐字一致", () => {
  it.each([1, 2, 3, 4, 5, 6])("种子 %i：文本 400 段 × 6 个函数，结构 120 个 × 4 个函数", (seed) => {
    const gen = generator(seed);
    const texts = Array.from({ length: 400 }, () => gen.textOf());
    const textRequests: ProbeRequest[] = texts.flatMap((input) =>
      TEXT_FNS.map((fn) => ({
        op: "secrets.call",
        fn,
        text: input,
        ...(fn === "decisions_redact" ? { limit: gen.rnd() < 0.2 ? gen.int(0, 12) : 4000 } : {}),
      })),
    );
    const results = sameEverywhere(textRequests, `种子 ${seed} 文本`);
    const changed = results.filter((result, index) => typeof result["text"] === "string" && result["text"] !== textRequests[index]?.["text"]);
    expect(changed.length, "要有相当一部分输入真的被改写，对照才不是空的").toBeGreaterThan(300);

    const looks = texts.map((input) => ({ op: "secrets.call", fn: "looks_like_secret", value: { t: "str", v: input } }));
    sameEverywhere(looks, `种子 ${seed} looks_like_secret`);

    const values = Array.from({ length: 120 }, () => gen.value());
    const structured: ProbeRequest[] = values.flatMap((value) => [
      { op: "secrets.call", fn: "redact_json", value },
      {
        op: "secrets.call",
        fn: "redact_json",
        value,
        allow: [
          { path: ["decisions", "api_key_env"], check: { kind: "env_name" } },
          { path: ["profiles", "*"], check: { kind: "id" } },
          { path: ["*", "[token=ok]"], check: { kind: "enum", choices: [{ t: "str", v: "ok" }, { t: "none" }] } },
        ],
      },
      { op: "secrets.call", fn: "redact_obj", value },
      { op: "secrets.call", fn: "secret_like_paths", value },
      { op: "secrets.call", fn: "redact_state", value, limit: 6000 },
    ]);
    sameEverywhere(structured, `种子 ${seed} 结构`);
  });
});
