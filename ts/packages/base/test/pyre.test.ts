// pyre 的白盒测试：构件本身的规则（契约与对照测的是拼出来的正则与函数）。
import { describe, expect, it } from "vitest";
import { W, WB, ci, pyLen, pyNfkc, pyRegex, pyRstrip, pySplitlines, pyStrip } from "../src/pyre.ts";
import { IGNORECASE_EXTRA, UNIDATA_VERSION } from "../src/pyunicode.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);

describe("pyre 的构件", () => {
  it("re.I 的扩展字符正是 re 文档写明的 İ ı ſ K", () => {
    expect(IGNORECASE_EXTRA).toEqual({ i: [0x130, 0x131], k: [0x212a], s: [0x17f] });
    const secret = pyRegex(`^${ci("secret")}$`);
    expect(secret.test(`${C(0x17f)}ECRET`)).toBe(true);
    expect(secret.test("SeCrEt")).toBe(true);
    expect(pyRegex(`^${ci("kit")}$`).test(`${C(0x212a)}${C(0x130)}t`)).toBe(true);
  });

  it("\\w 与 \\b 按 Python 的 Unicode 规则：中文、补充平面字母是单词字符", () => {
    expect(pyRegex(`^${W}+$`).test(`a${C(0x4e2d)}${C(0x1d400)}_1`)).toBe(true);
    expect(pyRegex(`${WB}sk`).test(`${C(0x4e2d)}sk`)).toBe(false);
    expect(pyRegex(`${WB}sk`).test(" sk")).toBe(true);
    expect(pyRegex(`${WB}%`).test("a%")).toBe(true); // 非单词字符前的 \b：前一个必须是单词字符
    expect(pyRegex(`${WB}%`).test(" %")).toBe(false);
  });

  it("strip 与长度按码点、按 str.isspace", () => {
    expect(pyStrip(`${C(0x1c)} a ${C(0x85)}`)).toBe("a"); // 0x1c、0x85 是 Python 的空白
    expect(pyStrip(`${C(0xfeff)}a`)).toBe(`${C(0xfeff)}a`); // BOM 不是
    expect(pyRstrip(" a \n")).toBe(" a");
    expect(pyLen(`${C(0x1d400)}a`)).toBe(2);
  });

  it("splitlines 认 Python 的全部行界，末尾的行界之后不多出空行", () => {
    const breaks = [0x0a, 0x0d, 0x0b, 0x0c, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029];
    for (const cp of breaks) expect(pySplitlines(`a${C(cp)}b${C(cp)}`)).toEqual(["a", "b"]);
    expect(pySplitlines("a\r\nb\n\r")).toEqual(["a", "b", ""]);
    expect(pySplitlines("")).toEqual([]);
    expect(pySplitlines(`a${C(0x1f)}b`)).toEqual([`a${C(0x1f)}b`]); // 0x1f 不是行界
  });

  it("pyNfkc：未分配码点用的占位符避开输入里已有的私用区字符；运行时比 Python 旧时拒绝", () => {
    const unassigned = C(0x897); // Python 15.0 里未分配
    const pua = C(0xf0000);
    expect(pyNfkc(`${pua}${unassigned}${pua}`)).toBe(`${pua}${unassigned}${pua}`);
    expect(pyNfkc(`${C(0xff41)}${unassigned}`)).toBe(`a${unassigned}`);
    expect(() => pyNfkc("a", "14.0")).toThrow(/拒绝脱敏/);
    expect(pyNfkc("a", UNIDATA_VERSION)).toBe("a");
  });
});
