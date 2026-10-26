// 第 ③a1 片给 @themis/base 加的 Python 兼容件的对照：str.lower、str.casefold、NFC（Unicode 15.0，运行时 ICU 更新）、
// bytes.decode("utf-8") 的报错、Path.read_text 的报错、urlsplit 与 ip_address、Python 的 ==。全部与 Python 逐条比较。
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { CASEFOLD, UNASSIGNED } from "@themis/base/pyunicode";
import { type ProbeRequest, prng, removeDir, runAgreeing, scratchDir, seededBytes } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const agree = (requests: readonly ProbeRequest[]): void => {
  const { mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
};

/** 全部码点按每段 4096 个切开（跳过代理项），逐段交给 fn。 */
function chunks(fn: string): ProbeRequest[] {
  const out: ProbeRequest[] = [];
  for (let start = 0; start < 0x110000; start += 4096) {
    const cps: number[] = [];
    for (let cp = start; cp < Math.min(start + 4096, 0x110000); cp += 1) if (cp < 0xd800 || cp > 0xdfff) cps.push(cp);
    out.push({ op: "unicode.call", fn, text: C(...cps) });
  }
  return out;
}

/** Python 眼里未分配、JS 的 ICU 里规范化或大小写会动到的码点（15.0 之后新分配的）。 */
function risky(): number[] {
  const found: number[] = [];
  for (let index = 0; index < UNASSIGNED.length; index += 2) {
    for (let cp = UNASSIGNED[index] ?? 0; cp <= (UNASSIGNED[index + 1] ?? 0); cp += 1) {
      if (cp >= 0xd800 && cp <= 0xdfff) continue;
      const x = C(cp);
      if (x.normalize("NFC") !== x || `a${x}${C(0x316)}`.normalize("NFC") !== `a${x}${C(0x316)}` || x.toLowerCase() !== x || x.toUpperCase() !== x) found.push(cp);
    }
  }
  return found;
}

describe("str.lower、str.casefold、NFC", () => {
  it("lower 改变的全部码点与映射，与 Python 相同", () => agree([{ op: "unicode.call", fn: "lower_table" }]));
  it("lower、casefold、NFC 逐段跑遍全部码点", () => agree([...chunks("lower"), ...chunks("casefold"), ...chunks("nfc")]));
  it("CASEFOLD 表里的每一项都与 Python 的 casefold 相同", () => {
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < CASEFOLD.length; ) requests.push({ op: "unicode.call", fn: "casefold", text: C(CASEFOLD[index] ?? 0) }), (index += 2 + (CASEFOLD[index + 1] ?? 0));
    agree(requests);
  });
  it("Final_Sigma 的各种上下文", () => {
    const sigma = C(0x3a3);
    const contexts = [
      sigma,
      `Α${sigma}`,
      `Α${sigma}Α`,
      `Α${sigma}.`,
      `Α.${sigma}`,
      `Α${sigma}'`,
      `Α'${sigma}`,
      `Α${C(0x301)}${sigma}`,
      `Α${sigma}${C(0x301)}`,
      `A${sigma}`,
      `1${sigma}`,
      `Α${sigma}${C(0xe0001)}`,
      `Α${C(0x37e)}${sigma}`,
      `${sigma}${sigma}${sigma}`,
      `Α${sigma} ${sigma}Α`,
    ];
    agree(contexts.flatMap((text) => [{ op: "unicode.call", fn: "lower", text }]));
  });
  it("15.0 之后新分配的码点放进各种上下文：lower、casefold、NFC 都与 Python 相同", () => {
    const candidates = risky();
    expect(candidates.length).toBeGreaterThan(30);
    const wrap = [(x: string) => x, (x: string) => `a${x}${C(0x316)}`, (x: string) => `Α${x}${C(0x3a3)}`, (x: string) => `Α${C(0x3a3)}${x}`, (x: string) => `e${C(0x301)}${x}${C(0x328)}`];
    agree(candidates.flatMap((cp) => wrap.flatMap((context) => ["lower", "casefold", "nfc"].map((fn) => ({ op: "unicode.call", fn, text: context(C(cp)) })))));
  });
});

describe("bytes.decode 与 Path.read_text 的报错", () => {
  const dir = scratchDir("pyio");
  afterAll(() => removeDir(dir));
  it("随机字节（偏向 UTF-8 的边界字节）解码的结果或报错原文", () => {
    const edges = [0x00, 0x7f, 0x80, 0xbf, 0xc0, 0xc1, 0xc2, 0xdf, 0xe0, 0xed, 0xef, 0xf0, 0xf4, 0xf5, 0xff, 0x9f, 0xa0, 0x8f, 0x90, 0x41];
    const next = prng(31);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 3000; index += 1) {
      const length = Math.floor(next() * 8);
      const bytes = Buffer.from(Array.from({ length }, () => (next() < 0.8 ? (edges[Math.floor(next() * edges.length)] ?? 0) : Math.floor(next() * 256))));
      requests.push({ op: "pyio.call", fn: "decode", b64: bytes.toString("base64") });
    }
    for (let seed = 1; seed <= 200; seed += 1) requests.push({ op: "pyio.call", fn: "decode", b64: Buffer.from(seededBytes(seed, 64)).toString("base64") });
    agree(requests);
  });
  it("读文件：不存在、上级是文件、是目录、BOM 与各种换行", () => {
    const crlf = join(dir, "crlf.txt");
    writeFileSync(crlf, "\uFEFFa\r\nb\rc\n\r\nd\r");
    const bad = join(dir, "bad.txt");
    writeFileSync(bad, Buffer.from([0x61, 0x0d, 0x0a, 0xe2, 0x82]));
    const sub = join(dir, "sub");
    mkdirSync(sub);
    agree([
      { op: "pyio.call", fn: "read_text", path: crlf },
      { op: "pyio.call", fn: "read_bytes", path: crlf },
      { op: "pyio.call", fn: "read_text", path: bad },
      { op: "pyio.call", fn: "read_text", path: join(dir, "absent.txt") },
      { op: "pyio.call", fn: "read_text", path: join(crlf, "below.txt") },
      { op: "pyio.call", fn: "read_bytes", path: sub },
      { op: "pyio.call", fn: "read_text", path: join(dir, "it's (quoted).txt") },
    ]);
    // 不比较：文件名本身非法（含 <>"|?*、控制字符，或某一段太长）时 Python 报 [Errno 22]，Node 报 ENOENT，从错误码分不出来；
    // 配置中心读的都是固定的文件名（见 @themis/base/pyio 的说明）。
  });
});

describe("urlsplit、port、hostname 与 ip_address", () => {
  it("按片段拼出的 URL", () => {
    const schemes = ["https://", "http://", "HTTP://", "ftp://", "https:", "//", "", "1http://", "ht~tp://", " \t\nhttps://"];
    const users = ["", "user@", ":@", "u:p@", "@", "a@b@"];
    const hosts = ["example.com", "EXAMPLE.com", "127.0.0.1", "localhost", "[::1]", "[::1", "::1]", "[127.0.0.1]", "[v1.x]", "[vz.x]", "[fe80::1%25eth0]", "[fe80::1%]", "ex℀ample", "exémple", "[::ffff:1.2.3.4]", "[1:2:3:4:5:6:7:8:9]", "[::1]x", "", "İ"];
    const ports = ["", ":", ":0", ":80", ":65535", ":65536", ":8o", ":８", ":-1", ":+1"];
    const tails = ["", "/", "//", "/v1", "?q", "#f", "/a?b#c", "\t/"];
    const next = prng(7);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 2500; index += 1) {
      requests.push({ op: "pyurl.call", fn: "split", text: `${pick(schemes)}${pick(users)}${pick(hosts)}${pick(ports)}${pick(tails)}` });
    }
    agree(requests);
  });
  it("ip_address 认不认", () => {
    const parts = ["", "0", "00", "1", "255", "256", "1a", "ffff", "fffff", "g", "::", ":", ".", "%", "%eth0", "%%", "1.2.3.4", "01.2.3.4", "١", "/"];
    const next = prng(11);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 3000; index += 1) {
      const count = 1 + Math.floor(next() * 9);
      const text = Array.from({ length: count }, () => parts[Math.floor(next() * parts.length)]).join(next() < 0.5 ? ":" : ".");
      requests.push({ op: "pyurl.call", fn: "ip_kind", text });
    }
    for (const text of ["1:2:3:4::5:6:7:8", "::1:2:3:4:5:6:7:8", "1:2:3:4:5:6:7:8::", "1::", "::1", "1:2:3:4:5:6:7:8", "1:2:3:4:5:6:7::", "::2:3:4:5:6:7:8", "1:2:3:4:5:6:1.2.3.4", "::1.2.3.4", "1::2::3", ":1::", "1:::2", "fe80::1%eth0", "fe80::1%", "1.2.3.4%x"]) {
      requests.push({ op: "pyurl.call", fn: "ip_kind", text });
    }
    agree(requests);
  });
});

describe("Python 的 ==", () => {
  const eq = (a: string, b: string, nested = false): ProbeRequest => ({ op: "pyvalue.eq", a, b, nested });
  it("指定的边界", () => {
    const pairs: [string, string][] = [
      ["9007199254740993", "9007199254740992.0"],
      ["9007199254740992", "9007199254740992.0"],
      ["-0.0", "0"],
      ["NaN", "NaN"],
      ["[NaN]", "[NaN]"],
      ['{"a": NaN}', '{"a": NaN}'],
      ["true", "1"],
      ["true", "1.0"],
      ["false", "-0.0"],
      ["[1, 2]", "[2, 1]"],
      ['{"a": 1, "b": 2}', '{"b": 2, "a": 1.0}'],
      ["Infinity", "Infinity"],
      ["1e400", "Infinity"],
      ["10000000000000000000000", "1e22"],
      ["null", "0"],
      ['"1"', "1"],
      ["[]", "{}"],
      ["[[1]]", "[[true]]"],
    ];
    agree(pairs.flatMap(([a, b]) => [eq(a, b), eq(a, b, true)]));
  });
  it("随机的 JSON 值两两比较", () => {
    const atoms = ["0", "1", "-0.0", "1.0", "true", "false", "null", "NaN", "Infinity", '"a"', '"1"', "9007199254740993", "9007199254740992.0", "[]", "{}"];
    const next = prng(5);
    const value = (depth = 0): string => {
      const roll = next();
      if (depth > 2 || roll < 0.5) return atoms[Math.floor(next() * atoms.length)] as string;
      if (roll < 0.75) return `[${Array.from({ length: Math.floor(next() * 3) }, () => value(depth + 1)).join(", ")}]`;
      const keys = ["a", "b", "c"].filter(() => next() < 0.6);
      return `{${keys.map((key) => `"${key}": ${value(depth + 1)}`).join(", ")}}`;
    };
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 2000; index += 1) {
      const a = value();
      const b = next() < 0.3 ? a : value();
      requests.push(eq(a, b, next() < 0.5));
    }
    agree(requests);
  });
});

