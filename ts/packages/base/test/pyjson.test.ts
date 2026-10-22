// pyjson 的白盒测试：契约与对照之外，钉住几处内部规则与已知的限制。外部行为由 packages/contracts 覆盖。
import { describe, expect, it } from "vitest";
import { INT_MAX_STR_DIGITS, PyJsonError, compareCodePoints, dumps, encodeUtf8, floatRepr, intRepr, loads } from "../src/pyjson.ts";

function kind(action: () => unknown): string {
  try {
    action();
  } catch (error) {
    return error instanceof PyJsonError ? error.kind : String(error);
  }
  return "没有报错";
}

describe("pyjson 的内部规则", () => {
  it("floatRepr：指数门槛的两侧", () => {
    expect([1e16, 9999999999999998, 1e-4, 9.99e-5, 123.0, 1.5].map(floatRepr)).toEqual([
      "1e+16",
      "9999999999999998.0",
      "0.0001",
      "9.99e-05",
      "123.0",
      "1.5",
    ]);
    expect([1e100, 1.25e-300, -2e-7].map(floatRepr)).toEqual(["1e+100", "1.25e-300", "-2e-07"]);
    expect([NaN, Infinity, -Infinity, -0, 0].map(floatRepr)).toEqual(["nan", "inf", "-inf", "-0.0", "0.0"]);
  });

  it("compareCodePoints 按码点而不是 UTF-16 码元比较", () => {
    expect(compareCodePoints("￿", "😀")).toBe(-1);
    expect("￿" < "😀").toBe(false); // JS 的 < 正好相反
    expect(compareCodePoints("a", "ab")).toBe(-1);
    expect(compareCodePoints("ab", "a")).toBe(1);
    expect(compareCodePoints("😀", "😀")).toBe(0);
  });

  it("int 的位数上限只数数字，不数负号", () => {
    expect(intRepr(-(10n ** BigInt(INT_MAX_STR_DIGITS - 1)))).toHaveLength(INT_MAX_STR_DIGITS + 1);
    expect(kind(() => intRepr(10n ** BigInt(INT_MAX_STR_DIGITS)))).toBe("ValueError");
    expect(kind(() => loads("-" + "9".repeat(INT_MAX_STR_DIGITS)))).toBe("没有报错");
  });

  it("encodeUtf8 遇到孤立代理项报 UnicodeEncodeError，不像 TextEncoder 那样换成 U+FFFD", () => {
    expect(kind(() => encodeUtf8("a\udc00"))).toBe("UnicodeEncodeError");
    expect([...encodeUtf8("中😀")]).toEqual([...new TextEncoder().encode("中😀")]);
  });

  it("缺省参数与 Python 一样：ensure_ascii=True、分隔符 \", \" 与 \": \"", () => {
    expect(dumps(new Map([["é", [1n, 2.0]]]))).toBe('{"\\u00e9": [1, 2.0]}');
  });

  it("已知的限制：Map 把 -0.0 键并成 0.0（契约不覆盖，见 pyjson.ts 的说明）", () => {
    expect(dumps(new Map([[-0, null]]))).toBe('{"0.0": null}');
  });
});
