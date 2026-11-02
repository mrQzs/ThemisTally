// 第 ③a1 片给 @themis/base 加的 Python 兼容件的对照：str.lower、str.casefold、NFC（Unicode 15.0，运行时 ICU 更新）、
// bytes.decode("utf-8") 的报错、Path.read_text 的报错、urlsplit 与 ip_address、Python 的 ==。全部与 Python 逐条比较。
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { CASEFOLD, UNASSIGNED } from "@themis/base/pyunicode";
import { IMPLS, PYTHON, type ProbeRequest, prng, removeDir, runAgreeing, runProbe, scratchDir, seededBytes } from "./harness.ts";

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

describe("Python 的 sorted（第 ⑤f 片搬到 base 的 pySorted）", () => {
  const sorted = (values: string): ProbeRequest => ({ op: "pyset.sorted", values });
  it("指定的边界", () => {
    agree([
      '[[1, 2], [1], [0, 5], [1, 2, 0], []]',
      '[[NaN, 1], [NaN, 0]]',
      '[[true, "b"], [1, "a"], [1.0, "c"]]',
      '[[1, "a"], [1, 2]]',
      '[[{}], [{}]]',
      '[[{"a": 1}], [{"a": 2}]]',
      '[[], [[]], [[], 1], [[1]]]',
      '[1, [1]]',
      '[[1], "a"]',
      '["b", "a", "B", "aa"]',
      '[3, 1.5, true, false, 9007199254740993, 9007199254740992.0, -0.0, 0]',
      '[NaN, 1, NaN, 0]',
      '[null, null]',
      '[null, 1]',
    ].map(sorted));
  });
  it("随机的列表：混着数、字符串、嵌套的列表，偶尔有字典与 null", () => {
    const atoms = ["0", "1", "-0.0", "1.0", "2", "true", "false", "NaN", "Infinity", '"a"', '"b"', '"1"', "9007199254740993", "9007199254740992.0", "[]"];
    const next = prng(7);
    const value = (depth: number): string => {
      const roll = next();
      if (roll < 0.02) return next() < 0.5 ? "{}" : "null";
      if (depth > 1 || roll < 0.55) return atoms[Math.floor(next() * atoms.length)] as string;
      return `[${Array.from({ length: Math.floor(next() * 4) }, () => value(depth + 1)).join(", ")}]`;
    };
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 1500; index += 1) {
      const lists = next() < 0.5;
      const items = Array.from({ length: Math.floor(next() * 9) }, () => (lists ? `[${Array.from({ length: Math.floor(next() * 3) }, () => value(1)).join(", ")}]` : value(0)));
      requests.push(sorted(`[${items.join(", ")}]`));
    }
    agree(requests);
  });
});

describe("Windows 错误的文字（第 ⑤f 片：kernel.ts 找不到 git、turn.ts 回合目录已在）", () => {
  it.runIf(process.platform === "win32")("Python 真触发的 str(exc) 与 pyWinErrorMessage 逐字相同：WinError 2 不带路径，WinError 183 带 repr 的路径", () => {
    const dir = join(scratchDir("winerror"), "已经在的 目录");
    mkdirSync(dir, { recursive: true });
    try {
      const exe = runProbe(PYTHON, { op: "winerror.real", kind: "exe", name: "themis-no-such-program-5f" });
      const made = runProbe(PYTHON, { op: "winerror.real", kind: "mkdir", path: dir });
      expect([exe["error"], made["error"]]).toEqual(["FileNotFoundError", "FileExistsError"]);
      for (const impl of IMPLS.filter((item) => item !== PYTHON)) {
        const texts = [runProbe(impl, { op: "winerror.text", code: 2 })["text"], runProbe(impl, { op: "winerror.text", code: 183, path: dir })["text"]];
        expect(texts, impl.name).toEqual([exe["text"], made["text"]]);
      }
    } finally {
      removeDir(dir);
    }
  });
});

describe("os.replace 失败时的文字（第 ⑤f 片：fsutil 的 writeTextAtomic 最后一次失败时照它报）", () => {
  it.runIf(process.platform === "win32")("Python 真触发的 WinError 32 与 5，与 TS 照 libuv 的错误码（EBUSY；EPERM、EACCES）造的文字逐字相同", () => {
    const dir = scratchDir("replace");
    try {
      const src = join(dir, "state.json.0123456789ab.tmp");
      const dst = join(dir, "state.json");
      writeFileSync(src, "x");
      writeFileSync(dst, "y");
      mkdirSync(join(dir, "目录"));
      const busy = runProbe(PYTHON, { op: "replace.real", kind: "busy", src, dst });
      const denied = runProbe(PYTHON, { op: "replace.real", kind: "denied", src, dst: join(dir, "目录") });
      expect([busy["winerror"], denied["winerror"]]).toEqual([32, 5]);
      for (const impl of IMPLS.filter((item) => item !== PYTHON)) {
        const shown = [["EBUSY", dst], ["EPERM", join(dir, "目录")], ["EACCES", join(dir, "目录")]].map(([code, target]) => {
          const result = runProbe(impl, { op: "replace.error", code, src, dst: target });
          return [result["error"], result["text"]];
        });
        expect(shown, impl.name).toEqual([[busy["error"], busy["text"]], [denied["error"], denied["text"]], [denied["error"], denied["text"]]]);
      }
    } finally {
      removeDir(dir);
    }
  });
});

describe("文件修改时刻换成秒（第 ⑤g 片：kit_hub 3233、4271 的 fromtimestamp(st_mtime, utc).strftime）", () => {
  it("Python 用 os.utime(ns=...) 把文件设到边界上，两边各自 stat、各自换成秒，逐字相同；小数部分满 1e6 微秒时进到下一秒", () => {
    const dir = scratchDir("mtime");
    try {
      const secs = [1n, 1_000_000_000n, 1_700_000_000n, 1_762_000_123n, 4_000_000_000n];
      const nsecs = [0n, 123_456_789n, 499_999_999n, 500_000_000n, 999_999_499n, 999_999_500n, 999_999_501n, 999_999_999n];
      const files = secs.flatMap((sec) => nsecs.map((nsec) => {
        const path = join(dir, `${sec}-${nsec}.txt`);
        writeFileSync(path, "x");
        return [path, String(sec * 1_000_000_000n + nsec)];
      }));
      const real = runProbe(PYTHON, { op: "mtime.real", files });
      const texts = real["texts"] as string[];
      expect(texts[nsecs.length - 1]).toBe("1970-01-01T00:00:02Z"); // 1.999999999 秒：微秒取整满 1e6，进到下一秒
      for (const impl of IMPLS.filter((item) => item !== PYTHON)) {
        expect(runProbe(impl, { op: "mtime.seconds", paths: files.map(([path]) => path) })["texts"], impl.name).toEqual(texts);
      }
    } finally {
      removeDir(dir);
    }
  });
});

describe("Python 异常的继承关系与类名（第 ⑤g1 片：base 的 pyexc）", () => {
  it.runIf(process.platform === "win32")("pyCaught 照 __mro__ 逐对判；base 的每种异常类，pyExceptionName 与 Python 的 type(exc).__name__ 相同", () => {
    const specs = [...[1, 2, 13, 17, 20, 21, 28].map((errno) => ["oserror", errno]), ...[2, 5, 183, 267, 109, 128, 89, 1].map((winerror) => ["winerror", winerror]),
      ["decode", "fsutil"], ["decode", "pyio"], ["json", null], ["re-error", null], ["re-value", null], ["re-overflow", null], ["crash", "KeyError"], ["crash", "TimeoutExpired"]];
    for (const impl of IMPLS.filter((item) => item !== PYTHON)) {
      const ts = runProbe(impl, { op: "pyexc.call", specs });
      const names = ts["names"] as string[];
      expect(names).toEqual(expect.arrayContaining(["BrokenPipeError", "ConnectionError", "ChildProcessError", "BlockingIOError", "TimeoutExpired", "SubprocessError"]));
      const real = runProbe(PYTHON, { op: "pyexc.real", names, specs });
      const mro = real["mro"] as Record<string, string[]>;
      expect(ts["caught"], impl.name).toEqual(names.map((name) => names.map((kind) => (mro[name] as string[]).includes(kind))));
      expect(ts["made"], impl.name).toEqual(real["names"]);
    }
  });
});

describe("str(PurePath(...))", () => {
  it("盘符、UNC、设备路径、相对路径与各种分隔符", () => {
    const B = String.fromCharCode(92);
    const samples = [
      "C:/x//y/", "C:", "C:x/./y", "//server/share/a", `${B}${B}?${B}C:${B}x`, "/x", "a/../b", "", ".", `${B}${B}.${B}pipe${B}x`,
      "//server", "//server/share", `C:${B}`, `x${B}`, `${B}${B}?${B}UNC${B}s${B}h${B}p`, "😀:x", "c:/Users//me/./.config/", "~", "a/./././b//",
    ];
    const next = prng(17);
    const atoms = ["a", "C:", "/", B, ".", "..", "//", "?", "UNC", "😀", " "];
    for (let index = 0; index < 600; index += 1) {
      samples.push(Array.from({ length: 1 + Math.floor(next() * 6) }, () => atoms[Math.floor(next() * atoms.length)]).join(""));
    }
    agree(samples.flatMap((text) => [{ op: "pypath.pure", text }, { op: "pypath.pure", text, parts: ["code-kit", "secrets"] }]));
  });
});
