// PyOut 对照（④b3 补，themistally-15 复核 d14ea7c 查出）：Python 的 print 与 TS 的 PyOut({ bufferStdout: true }) 跑同一串
// 操作，stdout 与 stderr 写进同一个文件，比字节。stderr 那一行落在哪里，取决于 stdout 两层缓冲当时的状态（CPython 3.12：
// 文本层攒到 8192 及以上整份交给字节层，字节层容量 8192），所以随机串里 stderr 与 flush 穿插在中间，每写一次 stderr 就照
// 一次两层的状态。Python 一侧照 pi_dispatch.main 先把两个流改成 UTF-8、errors="replace"（孤立代理项写成 ?）。
import { spawnSync } from "node:child_process";
import { closeSync, mkdtempSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { BUN, prng } from "./harness.ts";

const PROBE = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes", "pyout_probe.ts");
const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const LF = String.fromCharCode(10);
const C = (...cps: number[]): string => String.fromCodePoint(...cps);

const PY = [
  "import json, sys",
  "for stream in (sys.stdout, sys.stderr):",
  "    stream.reconfigure(encoding='utf-8', errors='replace')",
  "for op in json.load(open(sys.argv[1], encoding='utf-8')):",
  "    if op[0] == 'print':",
  "        print(op[1], flush=op[2])",
  "    elif op[0] == 'write':",
  "        sys.stdout.write(op[1])",
  "    elif op[0] == 'flush':",
  "        sys.stdout.flush()",
  "    else:",
  "        print(op[1], file=sys.stderr)",
].join(LF);

type Op = ["print", string, boolean] | ["write", string] | ["flush"] | ["err", string];

function run(command: string, args: readonly string[], opsFile: string, dir: string, name: string): Buffer {
  const outFile = join(dir, `${name}.out`);
  const fd = openSync(outFile, "w");
  try {
    const done = spawnSync(command, [...args, opsFile], { stdio: ["ignore", fd, fd], timeout: 120_000 });
    if (done.error || done.status !== 0) throw new Error(`${name} 退出码 ${String(done.status)}：${done.error?.message ?? ""}`);
  } finally {
    closeSync(fd);
  }
  return readFileSync(outFile);
}

/** 第一处不同的字节；相同时为 -1。 */
function firstDiff(left: Buffer, right: Buffer): number {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) if (left[index] !== right[index]) return index;
  return left.length === right.length ? -1 : length;
}

function compare(ops: readonly Op[]): void {
  const dir = mkdtempSync(join(tmpdir(), "themis-pyout-"));
  try {
    const opsFile = join(dir, "ops.json");
    writeFileSync(opsFile, JSON.stringify(ops), "utf8");
    const python = run(PYTHON, ["-c", PY], opsFile, dir, "python");
    for (const [name, command] of [["node", "node"], ["bun", BUN]] as const) {
      const ts = run(command, [PROBE], opsFile, dir, name);
      const at = firstDiff(python, ts);
      const around = (bytes: Buffer): string => bytes.subarray(Math.max(0, at - 40), at + 40).toString("latin1");
      expect(at === -1 ? null : { impl: name, at, python: around(python), ts: around(ts), lengths: [python.length, ts.length] }).toBeNull();
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const lines = (count: number, width: number): Op[] => Array.from({ length: count }, (_, index) => ["print", String(index % 10).repeat(width), false]);

/** 手挑的：themistally-15 实测的那几组，加上字节层恰好攒满 8192 时被 flush、write 不带换行、空的 print 与 write。 */
const PICKED: [string, Op[]][] = [
  ["30、60、100、160、400 行（每行 151 字节）之后报错", [30, 60, 100, 160, 400].flatMap((count): Op[] => [...lines(count, 149), ["err", `E${count}`]])],
  ["8190 加换行恰好 8192：交给字节层留着，再写 98", [["print", "a".repeat(8190), false], ["print", "b".repeat(98), false], ["err", "E"]]],
  ["8190 之后 8298：字节层放不下，先写出手上的", [["print", "a".repeat(8190), false], ["print", "b".repeat(8298), false], ["err", "E"]]],
  ["4998 与 5000：换行之前就过了 8192", [["print", "a".repeat(4998), false], ["print", "b".repeat(5000), false], ["err", "E"]]],
  ["一行 10000、一行 8191", [["print", "a".repeat(10000), false], ["err", "E1"], ["print", "a".repeat(8191), false], ["err", "E2"]]],
  ["两行 6000", [["print", "a".repeat(6000), false], ["print", "b".repeat(6000), false], ["err", "E"]]],
  // 一次 write 本身就有 8192 字节及以上：pending 先单独交出去，只有恰好 8192 时看得出（按字节数，不按字符数）
  ["先写 5 字节、再写恰好 8192 字节", [
    ["write", "a".repeat(5)], ["write", "b".repeat(8192)], ["err", "E1"],
    ["write", "c".repeat(3000)], ["write", `${C(0x4e2d).repeat(2730)}ab`], ["err", "E2"],
    ["print", "d".repeat(7), false], ["write", `${"e".repeat(8190)}${LF}`], ["err", "E3"],
    ["write", "f".repeat(5000)], ["write", "g".repeat(8191)], ["err", "E4"],
  ]],
  ["字节层恰好 8192 时 flush 与 print(flush=True)", [
    ["print", "a".repeat(8190), false], ["err", "E1"], ["flush"], ["err", "E2"],
    ["print", "b".repeat(8190), false], ["print", "c", true], ["err", "E3"],
  ]],
  ["write 不带换行、空的 print 与 write", [
    ["write", "a".repeat(8191)], ["write", ""], ["print", "", false], ["err", "E1"], ["write", "b"], ["err", "E2"], ["write", ""], ["flush"], ["err", "E3"],
  ]],
  ["多字节与正文里的换行按换算之后的字节计", [
    ["print", C(0x4e2d).repeat(2730), false], ["err", "E1"], ["print", `${"a".repeat(4094)}${LF}${"b".repeat(4094)}`, false], ["err", "E2"],
    ["print", `${C(0x1f600).repeat(2047)}${String.fromCharCode(0xd800)}`, false], ["err", "E3"],
  ]],
];

/** 边界附近的长度与几种字节宽度：1（a）、2（é）、3（中）、4（补充平面）、孤立代理项（写成 ? 是 1）、换行（CRLF 是 2）。 */
const LENGTHS = [0, 1, 2, 3, 97, 98, 4094, 4096, 4998, 5000, 8188, 8189, 8190, 8191, 8192, 8193, 8194, 10000, 16382, 16384, 20000];
const CHARS = ["a", C(0xe9), C(0x4e2d), C(0x1f600), String.fromCharCode(0xd800), LF];

function randomOps(seed: number, count: number): Op[] {
  const rnd = prng(seed);
  const int = (low: number, high: number): number => low + Math.floor(rnd() * (high - low + 1));
  const pick = <T>(items: readonly T[]): T => items[int(0, items.length - 1)] as T;
  const text = (): string => {
    const length = rnd() < 0.5 ? pick(LENGTHS) : int(0, 3000);
    if (rnd() < 0.6) return "x".repeat(length);
    const mix = Array.from({ length: int(1, 3) }, () => pick(CHARS));
    return Array.from({ length }, () => pick(mix)).join("");
  };
  return Array.from({ length: count }, (_, index): Op => {
    const r = rnd();
    if (r < 0.55) return ["print", text(), rnd() < 0.1];
    if (r < 0.75) return ["write", text()];
    if (r < 0.82) return ["flush"];
    return ["err", `E${index}`];
  });
}

describe("PyOut 对照：stdout 两层缓冲与 stderr 的次序", () => {
  for (const [label, ops] of PICKED) it(label, () => compare(ops), 120_000);

  it.each([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])("随机，种子 %i：300 步，stderr 与 flush 穿插", (seed) => compare(randomOps(seed, 300)), 120_000);
});
