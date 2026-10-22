// clock 的白盒测试：给定时刻的写法逐字核对（契约只能核对格式与范围）。
import { describe, expect, it } from "vitest";
import { SENDER_ALIAS, attemptDirName, auditId, newMsgId, newTurnId, nowMicros, utcCompact, utcNow } from "../src/clock.ts";

// 2026-10-22T01:02:03.123456Z
const AT = Date.UTC(2026, 9, 22, 1, 2, 3, 123) * 1000 + 456;

describe("clock 的写法", () => {
  it("utcNow 截断到秒，不进位", () => {
    expect(utcNow(AT)).toBe("2026-10-22T01:02:03Z");
    expect(utcNow(Date.UTC(2026, 11, 31, 23, 59, 59, 999) * 1000 + 999)).toBe("2026-12-31T23:59:59Z");
    expect(utcNow(Date.UTC(2026, 0, 2, 3, 4, 5) * 1000)).toBe("2026-01-02T03:04:05Z");
  });

  it("utcCompact 写到微秒，各段补零", () => {
    expect(utcCompact(AT)).toBe("20261022T010203123456Z");
    expect(utcCompact(Date.UTC(2026, 0, 2, 3, 4, 5) * 1000 + 7)).toBe("20260102T030405000007Z");
  });

  it("信件编号与回合编号都以 utcCompact 开头，随机部分分别是 6 位与 4 位十六进制", () => {
    expect(newMsgId("站主", AT)).toMatch(/^20261022T010203123456Z-owner-[0-9a-f]{6}$/);
    expect(newMsgId("内核", AT)).toMatch(/^20261022T010203123456Z-kernel-[0-9a-f]{6}$/);
    expect(newMsgId("gate-sonnet", AT)).toMatch(/^20261022T010203123456Z-gate-sonnet-[0-9a-f]{6}$/);
    expect(newTurnId(AT)).toMatch(/^20261022T010203123456Z-[0-9a-f]{4}$/);
    expect(SENDER_ALIAS).toEqual({ 站主: "owner", 内核: "kernel" });
  });

  it("attempt 目录名补到三位，再大照写；负数与非整数拒收", () => {
    expect([1, 10, 100, 1000].map(attemptDirName)).toEqual(["attempt-001", "attempt-010", "attempt-100", "attempt-1000"]);
    expect(() => attemptDirName(-1)).toThrow(RangeError);
    expect(() => attemptDirName(1.5)).toThrow(RangeError);
  });

  it("取的是 UTC，不受本机时区影响（在 UTC 的机器上，误用本地时间也查得出来）", () => {
    const saved = process.env["TZ"];
    process.env["TZ"] = "Asia/Shanghai";
    try {
      expect(new Date(0).getHours()).toBe(8); // 时区确实换了
      expect(utcNow(AT)).toBe("2026-10-22T01:02:03Z");
      expect(utcCompact(AT)).toBe("20261022T010203123456Z");
    } finally {
      if (saved === undefined) delete process.env["TZ"];
      else process.env["TZ"] = saved;
    }
  });

  it("审计编号 aud- 加 32 位十六进制；当前时刻按微秒取，与 Date.now 相差不到一秒", () => {
    expect(auditId()).toMatch(/^aud-[0-9a-f]{32}$/);
    expect(Math.abs(nowMicros() / 1000 - Date.now())).toBeLessThan(1000);
  });
});
