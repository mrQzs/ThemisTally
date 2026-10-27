// shlex.split（posix，不认注释）的契约（迁移第 ④b1 片）：合同检查行的命令照它拆成 argv，报错原文进 derive-json 的提示。
// 每条先由 Python 回答，Node、Bun 逐字一致；另有按种子拼出来的文字。转义的反斜杠用 String.fromCharCode(92) 拼。
import { describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, prng, runAgreeing } from "./harness.ts";

const BS = String.fromCharCode(92);
const NBSP = String.fromCharCode(0xa0);
const IDEO = String.fromCharCode(0x3000);
const split = (text: string): ProbeRequest => ({ op: "pyshlex.split", text });

function agree(requests: readonly ProbeRequest[]): ProbeResult[] {
  const { python, mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
}

describe("shlex.split", () => {
  it("手写的用例", () => {
    const python = agree([
      split("npm run test -- --runInBand"),
      split("  leading   and\ttrailing  "),
      split(""),
      split("   "),
      split(`python -c "print('x')"`),
      split(`a'b c'd`),
      split(`''`),
      split(`"" ''`),
      split(`a${BS} b`),
      split(`"a${BS}"b"`),
      split(`"a${BS}${BS}b"`),
      split(`"a${BS}nb"`),
      split(`'a${BS}nb'`),
      split(`${BS}${BS}`),
      split(`x${BS}`),
      split(`"open`),
      split(`'open`),
      split(`"a${BS}`),
      split(`a#b # c`),
      split("line1\nline2\r\nline3"),
      split(`a${NBSP}b${IDEO}c`),
      split("é ß ÀÞ 文字 x-y.z/w*?="),
      split(`pytest "tests/test x.py" -k 'a and b'`),
      split(`--flag="a b" --other='c d'`),
    ]);
    expect(python[0]?.["argv"]).toEqual(["npm", "run", "test", "--", "--runInBand"]);
    expect(python[6]?.["argv"]).toEqual([""]);
    expect([python[15]?.["message"], python[17]?.["message"], python[14]?.["message"]]).toEqual(["No closing quotation", "No escaped character", "No escaped character"]);
  });

  it("按种子拼出来的文字：每个种子 500 段", () => {
    const pieces = ["a", "bc", " ", "  ", "\t", "\n", "\r", "'", '"', BS, "#", "x y", "é", "文", NBSP, IDEO, "-", "=", "''", '""', `${BS}"`, `${BS}'`, `${BS}${BS}`];
    const requests: ProbeRequest[] = [];
    for (const seed of [51, 52, 53]) {
      const next = prng(seed);
      for (let index = 0; index < 500; index += 1) {
        const size = Math.floor(next() * 12);
        requests.push(split(Array.from({ length: size }, () => pieces[Math.floor(next() * pieces.length)] as string).join("")));
      }
    }
    const python = agree(requests);
    // 三种结局都走到了：拆开、引号没收尾、转义没收尾
    const messages = new Set(python.map((result) => (result.ok ? "ok" : String(result["message"]))));
    expect([...messages].sort()).toEqual(["No closing quotation", "No escaped character", "ok"]);
  });
});
