// clock 的白盒测试：给定时刻的写法逐字核对（契约只能核对格式与范围）。
import { describe, expect, it, vi } from "vitest";
import { SENDER_ALIAS, attemptDirName, auditId, makeClock, newMsgId, newTurnId, nowMicros, utcCompact, utcNow } from "../src/clock.ts";

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

  it("utcNow() 跟的是系统时钟：与同一时刻的 new Date() 相差不超过 1 秒", () => {
    const before = Date.now();
    const text = utcNow();
    const after = Date.now();
    expect(Date.parse(text)).toBeGreaterThanOrEqual(Math.floor(before / 1000) * 1000 - 1000);
    expect(Date.parse(text)).toBeLessThanOrEqual(after + 1000);
  });

  it("时钟以系统毫秒为准、高精度时钟只补微秒位；系统时钟往回调也不倒退", () => {
    let wall = 1_000_000;
    let fine = 5.25;
    const clock = makeClock(
      () => wall,
      () => fine,
    );
    expect(clock()).toBe(1_000_000_250); // 毫秒取 wall，微秒位取 fine 的小数部分
    wall = 1_000_001;
    fine = 9.999;
    expect(clock()).toBe(1_000_001_999);
    wall = 999_000; // 系统时钟往回调了一秒
    expect(clock()).toBe(1_000_002_000);
    expect(clock()).toBe(1_000_002_001); // 同一时刻连取：严格递增
    wall = 2_000_000;
    fine = 3;
    expect(clock()).toBe(2_000_000_000); // 追上之后又以系统时钟为准
  });

  // 放在最后：进程内的单调夹紧会让之后的取值一直停在 2030 年之后
  it("当前时刻跟着系统时钟走（系统时间被校正到 2030 年，utcNow 也跟着变）", () => {
    const spy = vi.spyOn(Date, "now").mockReturnValue(Date.UTC(2030, 0, 1, 12, 0, 0));
    try {
      expect(utcNow()).toBe("2030-01-01T12:00:00Z");
      expect(newMsgId("站主")).toMatch(/^20300101T120000\d{6}Z-owner-/);
    } finally {
      spy.mockRestore();
    }
  });
});
