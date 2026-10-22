// kit_logs 读大文件的原语：_jsonl_records（按字节从偏移逐行读，单行有上限）、_iter_lines、_lines_before。
// 契约逐条通过（Python 先过）；对照部分用随机字节文件（长短行、CRLF、单独的 CR、坏 UTF-8、末行没有换行），
// 随机偏移、上限与 final，三套实现逐字一致。文件内容按字节写，不经文本编码。
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, prng, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";

const B = (...parts: (string | number[])[]): Buffer =>
  Buffer.concat(parts.map((part) => (typeof part === "string" ? Buffer.from(part, "utf8") : Buffer.from(part))));
const b64 = (text: string): string => Buffer.from(text, "utf8").toString("base64");
const FFFD = String.fromCodePoint(0xfffd);

function withFile(name: string, data: Buffer, body: (path: string) => void): void {
  const dir = scratchDir(name);
  try {
    const path = join(dir, "events.jsonl");
    writeFileSync(path, data);
    body(path);
  } finally {
    removeDir(dir);
  }
}

describe.each(IMPLS)("jsonl 读取契约 impl=$name", (impl) => {
  const records = (path: string, start: number, final: boolean, limit = 100) =>
    runProbe(impl, { op: "jsonl.records", path, start, final, limit });

  it("R1 逐行给出 [起点, 下一行起点, 去掉行尾的内容]；CRLF 只去一次；末行没有换行：final 才给", () => {
    withFile(`rd1-${impl.name}`, B("a\nbb\r\n\r\r\nccc"), (path) => {
      expect(records(path, 0, true)).toEqual({
        ok: true,
        records: [[0, 2, b64("a")], [2, 6, b64("bb")], [6, 9, b64("\r")], [9, 12, b64("ccc")]],
      });
      expect(records(path, 0, false)).toEqual({ ok: true, records: [[0, 2, b64("a")], [2, 6, b64("bb")], [6, 9, b64("\r")]] });
    });
  });

  it("R2 从行中间的偏移起读；偏移在末尾或更远：没有行", () => {
    withFile(`rd2-${impl.name}`, B("abc\ndef\n"), (path) => {
      expect(records(path, 1, true)).toEqual({ ok: true, records: [[1, 4, b64("bc")], [4, 8, b64("def")]] });
      expect(records(path, 8, true)).toEqual({ ok: true, records: [] });
      expect(records(path, 50, true)).toEqual({ ok: true, records: [] });
    });
  });

  it("R3 超过上限的行只计长度、内容为 null；上限按去掉行尾之后的字节数算", () => {
    withFile(`rd3-${impl.name}`, B("12345\nabcd\r\n", [0xe4, 0xb8, 0xad, 0xe6], "\nxy"), (path) => {
      expect(records(path, 0, true, 4)).toEqual({
        ok: true,
        records: [[0, 6, null], [6, 12, b64("abcd")], [12, 17, Buffer.from([0xe4, 0xb8, 0xad, 0xe6]).toString("base64")], [17, 19, b64("xy")]],
      });
      expect(records(path, 0, true, 3).records).toEqual([[0, 6, null], [6, 12, null], [12, 17, null], [17, 19, b64("xy")]]);
    });
  });

  it("R4 iter_lines：按 \\n 分行，去掉行尾，坏 UTF-8 换成 U+FFFD，BOM 照留；文件不存在：没有行", () => {
    const BOM = [0xef, 0xbb, 0xbf];
    withFile(`rd4-${impl.name}`, B(BOM, "a\r\n", [0xff, 0xfe], "b\n", [0xed, 0xa0, 0x80], "\n", BOM, [0xf0, 0x9f, 0x98], "\rlast"), (path) => {
      const bom = String.fromCodePoint(0xfeff);
      expect(runProbe(impl, { op: "jsonl.iter_lines", path })).toEqual({
        ok: true,
        lines: [`${bom}a`, `${FFFD}${FFFD}b`, `${FFFD}${FFFD}${FFFD}`, `${bom}${FFFD}\rlast`],
      });
      expect(runProbe(impl, { op: "jsonl.iter_lines", path: `${path}.missing` })).toEqual({ ok: true, lines: [] });
    });
  });

  it("R5 lines_before 数偏移之前的换行；偏移超过文件长度按整份数；文件不存在报 ENOENT", () => {
    withFile(`rd5-${impl.name}`, B("a\nb\r\nc"), (path) => {
      expect(runProbe(impl, { op: "jsonl.lines_before", path, position: 0 })).toEqual({ ok: true, count: 0 });
      expect(runProbe(impl, { op: "jsonl.lines_before", path, position: 2 })).toEqual({ ok: true, count: 1 });
      expect(runProbe(impl, { op: "jsonl.lines_before", path, position: 100 })).toEqual({ ok: true, count: 2 });
      expect(runProbe(impl, { op: "jsonl.lines_before", path: `${path}.missing`, position: 1 })).toEqual({ ok: false, error: "ENOENT" });
      expect(records(`${path}.missing`, 0, true)).toEqual({ ok: false, error: "ENOENT" });
    });
  });
});

describe("jsonl 读取对照：随机字节文件", () => {
  const PIECES: (string | number[])[] = [
    "{\"event\": \"a\"}", "中文", "x", "", " ", "\r", "\t", [0xff], [0xc0, 0xaf], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80],
    [0xf0, 0x9f, 0x98], [0xe2, 0x80, 0xa8], [0xef, 0xbb, 0xbf], [0x00], "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  ];
  const ENDS = ["\n", "\r\n", "\r\r\n", "", "\n\n"];

  it.each([1, 2, 3, 4, 5, 6])("种子 %i：40 个文件，每个文件随机偏移、上限、final 各读几遍", (seed) => {
    const rnd = prng(seed);
    const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
    const dir = scratchDir(`rd-compare-${seed}`);
    try {
      const requests: ProbeRequest[] = [];
      for (let index = 0; index < 40; index += 1) {
        const parts: (string | number[])[] = [];
        for (let line = int(0, 12); line > 0; line -= 1) {
          for (let piece = int(0, 5); piece > 0; piece -= 1) parts.push(PIECES[int(0, PIECES.length - 1)] as string | number[]);
          parts.push(ENDS[int(0, ENDS.length - 1)] as string);
        }
        const data = B(...parts);
        const path = join(dir, `f${index}.jsonl`);
        writeFileSync(path, data);
        requests.push({ op: "jsonl.iter_lines", path });
        for (let probe = 0; probe < 4; probe += 1) {
          requests.push({ op: "jsonl.records", path, start: int(0, data.length + 2), final: rnd() < 0.5, limit: int(1, 40) });
          requests.push({ op: "jsonl.lines_before", path, position: int(0, data.length + 2) });
        }
      }
      const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
      for (const other of others) {
        const mismatches = requests.flatMap((request, index) =>
          JSON.stringify(other[index]) === JSON.stringify(python?.[index]) ? [] : [{ request, python: python?.[index], other: other[index] }],
        );
        expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
      }
    } finally {
      removeDir(dir);
    }
  });
});
