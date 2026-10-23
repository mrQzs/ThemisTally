// 控制令牌门（桌面端 T7c）：恒定时间比较走 timingSafeEqual 的两份 32 字节摘要（用 vi.mock 包住 node:crypto，断言
// 调用次数），长度不同与缺头都走同一条路；连续 5 次失败锁 1 秒、翻倍、60 秒封顶；锁定期内对的令牌也 429 且不计数；
// 成功之后计数清零。
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ timingSafeEqual: 0 }));

vi.mock("node:crypto", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:crypto")>();
  return {
    ...actual,
    timingSafeEqual: (a: Uint8Array, b: Uint8Array): boolean => {
      state.timingSafeEqual += 1;
      return actual.timingSafeEqual(a as never, b as never);
    },
  };
});

const { ControlGate, CONTROL_LOCK_BASE_MS, CONTROL_LOCK_MAX_MS, CONTROL_MAX_FAILURES } = await import(
  "../src/localhttp/control.ts"
);

const TOKEN = "x".repeat(43);
const CONTROL_HEADER = "x-themis-control";

const headers = (value: string | null): Headers => {
  const made = new Headers();
  if (value !== null) made.set(CONTROL_HEADER, value);
  return made;
};

describe("控制令牌门", () => {
  beforeEach(() => {
    state.timingSafeEqual = 0;
  });

  it("常量照合同", () => {
    expect(CONTROL_MAX_FAILURES).toBe(5);
    expect(CONTROL_LOCK_BASE_MS).toBe(1000);
    expect(CONTROL_LOCK_MAX_MS).toBe(60000);
  });

  it("对的令牌通过，失败计数清零；错的 403", () => {
    const gate = new ControlGate(TOKEN, () => 0);
    expect(gate.check(headers(TOKEN))).toEqual({ ok: true });
    expect(gate.check(headers("wrong"))).toEqual({ ok: false, status: 403 });
    expect(state.timingSafeEqual).toBe(2);
    expect(gate.check(headers(TOKEN))).toEqual({ ok: true });
  });

  it("比较走 timingSafeEqual，缺头与长度不同都走同一条路", () => {
    const gate = new ControlGate(TOKEN, () => 0);
    expect(gate.check(headers(null))).toEqual({ ok: false, status: 403 });
    expect(gate.check(headers("x"))).toEqual({ ok: false, status: 403 });
    expect(state.timingSafeEqual).toBe(2);
    expect(gate.check(headers(`${TOKEN}pad`))).toEqual({ ok: false, status: 403 });
    expect(state.timingSafeEqual).toBe(3);
  });

  it("连续 5 次失败之后锁 1 秒：锁定期内对的令牌也 429 且带 Retry-After，且不计数", () => {
    let now = 10_000;
    const gate = new ControlGate(TOKEN, () => now);
    for (let index = 0; index < CONTROL_MAX_FAILURES; index += 1) {
      expect(gate.check(headers(`wrong-${index}`))).toEqual({ ok: false, status: 403 });
    }
    now += 500;
    expect(gate.check(headers(TOKEN))).toEqual({ ok: false, status: 429, retryAfterSeconds: 1 });
    now += 499;
    expect(gate.check(headers(TOKEN))).toEqual({ ok: false, status: 429, retryAfterSeconds: 1 });
    now += 1;
    expect(gate.check(headers(TOKEN))).toEqual({ ok: true }); // 1001 毫秒之后放开
  });

  it("锁定时长翻倍，60 秒封顶", () => {
    let now = 0;
    const gate = new ControlGate(TOKEN, () => now);
    for (let index = 0; index < CONTROL_MAX_FAILURES; index += 1) gate.check(headers("wrong"));
    expect(gate.check(headers(TOKEN))).toEqual({ ok: false, status: 429, retryAfterSeconds: 1 });
    now += 1001;
    expect(gate.check(headers("wrong"))).toEqual({ ok: false, status: 403 }); // 第 6 次失败
    expect(gate.check(headers(TOKEN))).toEqual({ ok: false, status: 429, retryAfterSeconds: 2 }); // 翻倍
    now += 2001;
    expect(gate.check(headers(TOKEN))).toEqual({ ok: true }); // 成功：计数清零
    // 每次都比上一段锁定久，才能一路失败到第 11 次：1000 * 2^6 封顶到 60 秒
    for (let index = 0; index < 11; index += 1) {
      now += 70_000;
      expect(gate.check(headers("wrong"))).toEqual({ ok: false, status: 403 });
    }
    expect(gate.check(headers(TOKEN))).toEqual({ ok: false, status: 429, retryAfterSeconds: 60 });
  });
});
