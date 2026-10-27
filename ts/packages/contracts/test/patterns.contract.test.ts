// pi_dispatch 路径模式的契约（迁移第 ④b1 片）：re.escape、glob_regex 拼出的正则文字、matches（fullmatch，可选不分大小写）、
// pattern_error。每条先由 Python 回答，Node、Bun 逐字一致；matches 另有按种子拼出来的路径与模式，专门混进 Python 的
// IGNORECASE 才认的大小写等价字符（ſ、K、İ、ı、É、ß）、正则特殊字符与末尾的换行。不写转义序列，特殊字符用 ch() 拼。
import { describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, prng, runAgreeing } from "./harness.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const BS = ch(92);
const LF = ch(10);
const call = (fn: string, fields: Record<string, unknown>): ProbeRequest => ({ op: "patterns.call", fn, ...fields });

function agree(requests: readonly ProbeRequest[]): ProbeResult[] {
  const { python, mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
}

// ſ（U+017F）、K（U+212A）、İ（U+0130）、ı（U+0131）、É、é、ß、ẞ（U+1E9E）、全角 Ａ
const FOLDS = [ch(0x17f), ch(0x212a), ch(0x130), ch(0x131), ch(0xc9), ch(0xe9), ch(0xdf), ch(0x1e9e), ch(0xff21)];

describe("路径模式", () => {
  it("re.escape、glob 的正则文字、pattern_error", () => {
    const special = `()[]{}?*+-|^$.&~# ${ch(9)}${LF}${ch(13)}${ch(11)}${ch(12)}${BS}"'/:;,<=>@_!%`;
    const python = agree([
      call("re_escape", { text: special }),
      call("re_escape", { text: `abc文字${FOLDS.join("")}` }),
      ...["src/**", "**/AGENTS.md", "a/*/b?.ts", "**", "a**b", "x/**/y/**/*.js", `a.b(c)[d]{e}+f|g^h$i`, "日本/*.md", ""].map((pattern) => call("glob_text", { pattern })),
      ...[null, "", "a", "a/b", `a${BS}b`, "/abs", "C:x", "~x", "a//b", "./a", "a/../b", "*", "**", "**/*", `a${ch(1)}`, `a${ch(127)}`, 3, ["a"]].map((value) =>
        call("pattern_error", { value_json: JSON.stringify(value) }),
      ),
    ]);
    expect(python[0]?.["value"]).toContain(`${BS}(`);
  });

  it("matches：手写的用例", () => {
    const python = agree([
      call("matches", { patterns: [".agent/**", "**/AGENTS.md", "scripts/pi_dispatch.py"], ignore_case: true, paths: [".AGENT/x", ".agent", ".agent/", "sub/agents.MD", "AGENTS.md", `scripts/Pi_Dispatch.py`, `AGENTS.md${LF}`, `.agent/a${LF}b`] }),
      call("matches", { patterns: ["**/k.md", "s/**"], ignore_case: true, paths: [`x/${ch(0x212a)}.md`, `${ch(0x17f)}/a`, "S/a", `x/K.MD`] }),
      call("matches", { patterns: ["**/k.md", "s/**"], ignore_case: false, paths: [`x/${ch(0x212a)}.md`, `${ch(0x17f)}/a`, "S/a", "x/k.md"] }),
      call("matches", { patterns: [`${ch(0xc9)}t${ch(0xe9)}/**`, `stra${ch(0xdf)}e.txt`], ignore_case: true, paths: [`${ch(0xe9)}T${ch(0xc9)}/x`, "STRASSE.txt", `STRA${ch(0x1e9e)}E.TXT`, `stra${ch(0x1e9e)}e.txt`] }),
      call("matches", { patterns: ["src/*.ts", "src/**/*.ts", "a?c"], ignore_case: false, paths: ["src/a.ts", "src/x/a.ts", "src/.ts", "abc", "a/c", `a${LF}c`, "ac"] }),
    ]);
    // 末两条：fullmatch 不放过末尾的换行；** 译成 .*，Python 的 . 不配换行
    expect(python[0]?.["value"]).toEqual([true, false, true, true, true, true, false, false]);
  });

  it("matches：按种子拼出来的路径与模式，每个种子 300 组", () => {
    const pieces = ["a", "B", "/", "*", "**", "?", ".", "-", "x/", "src/", ".agent/", ...FOLDS, "s", "k", "i", "e", "E", "I", "K", "S", `${LF}`, "(", "[", "+", "$", "^", "{", "|", "~", "#", " "];
    const requests: ProbeRequest[] = [];
    for (const seed of [61, 62, 63]) {
      const next = prng(seed);
      const word = (): string => Array.from({ length: 1 + Math.floor(next() * 6) }, () => pieces[Math.floor(next() * pieces.length)] as string).join("");
      for (let index = 0; index < 300; index += 1) {
        const patterns = Array.from({ length: 1 + Math.floor(next() * 3) }, word);
        const paths = Array.from({ length: 6 }, () => word().replaceAll("*", "x").replaceAll("?", "y"));
        requests.push(call("matches", { patterns, ignore_case: next() < 0.5, paths }));
      }
    }
    const python = agree(requests);
    // 两种结局都有：真有匹配上的，也有不匹配的
    const flat = python.flatMap((result) => result["value"] as boolean[]);
    expect(flat.includes(true) && flat.includes(false)).toBe(true);
  });
});
