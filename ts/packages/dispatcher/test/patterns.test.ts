// globRegex 的编译缓存（TS 启动开销那一片）：同一个 glob 先后按区分与不区分大小写编译，各自照自己的标志匹配。
// collect、contract 里受保护的路径不区分大小写，合同 Scope 的清单区分大小写，两边可能写着同一个 glob：缓存要是混用，
// 受保护路径的检查就会按区分大小写匹配，换个大小写就绕过去了。
import { describe, expect, it } from "vitest";
import { globRegex } from "../src/patterns.ts";

describe("globRegex 的编译缓存", () => {
  it("先区分大小写、再不区分：不沿用前一份", () => {
    expect(globRegex("scripts/Pi_*.py").test("scripts/pi_dispatch.py")).toBe(false);
    expect(globRegex("scripts/Pi_*.py", true).test("scripts/pi_dispatch.py")).toBe(true);
  });

  it("先不区分、再区分：同样不沿用", () => {
    expect(globRegex("docs/Readme*.md", true).test("docs/README.md")).toBe(true);
    expect(globRegex("docs/Readme*.md").test("docs/README.md")).toBe(false);
  });
});
