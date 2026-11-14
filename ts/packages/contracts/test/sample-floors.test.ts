// 采样计数与用例名单的下限（r3 第 161 轮）：shortOf、missingOf 是十一份按 pytest 采样的 hub 契约共用的两道检查。
import { describe, expect, it } from "vitest";
import { missingOf, shortOf } from "./harness.ts";

describe("采样计数的下限", () => {
  it("次数够下限、多出来的函数都算过；少了一次、整个函数没记到都报出来", () => {
    expect(shortOf({ a: 3, b: 1, extra: 5 }, { a: 3, b: 0 })).toEqual([]);
    expect(shortOf({ a: 2 }, { a: 3, b: 1 })).toEqual(["a 2 < 3", "b 0 < 1"]);
  });

  it("名单里的都记到了就算过，多记到的不管；没记到的照名单的顺序报", () => {
    expect(missingOf(["t2", "t1", "t3"], ["t1", "t2"])).toEqual([]);
    expect(missingOf(["t1"], ["t2", "t1", "t3"])).toEqual(["t2", "t3"]);
  });
});
