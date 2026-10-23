// 生命周期（桌面端 §5.4、D15 的纯函数部分）：空闲时限的换算与封顶、setTimeout 每段不超过 2^31-1、hold/release
// 的语义、stdin EOF 的读空与一次 onEof、信号的摘除。真进程的部分在 service.test.ts 与 launcher.e2e.test.ts。
import { PassThrough } from "node:stream";
import { describe, expect, it, vi } from "vitest";
import { IDLE_TIMEOUT_SECONDS, MAX_TIMEOUT_MS, IdleTimer, idleMs, timeoutChunk, watchSignals, watchStdinEof } from "../src/lifecycle.ts";

describe("空闲时限", () => {
  it("null 是 1800 秒", () => {
    expect(IDLE_TIMEOUT_SECONDS).toBe(1800);
    expect(idleMs(null)).toBe(1_800_000);
  });

  it("按秒换算，封顶 Number.MAX_SAFE_INTEGER", () => {
    expect(idleMs(30)).toBe(30_000);
    expect(idleMs(30n)).toBe(30_000);
    expect(idleMs(10n ** 30n)).toBe(Number.MAX_SAFE_INTEGER);
    expect(idleMs(Number.MAX_SAFE_INTEGER)).toBe(Number.MAX_SAFE_INTEGER);
  });
});

describe("setTimeout 分段", () => {
  it("每段不超过 2^31-1 毫秒", () => {
    expect(MAX_TIMEOUT_MS).toBe(2147483647);
    expect(timeoutChunk(1000)).toBe(1000);
    expect(timeoutChunk(Number.MAX_SAFE_INTEGER)).toBe(2147483647);
    expect(timeoutChunk(0)).toBe(0);
    expect(timeoutChunk(-5)).toBe(0);
  });
});

describe("空闲计时器", () => {
  it("到点触发一次；touch 之后重新计", async () => {
    vi.useFakeTimers();
    try {
      const onIdle = vi.fn();
      const timer = new IdleTimer(1000, onIdle);
      timer.touch();
      vi.advanceTimersByTime(900);
      expect(onIdle).not.toHaveBeenCalled();
      timer.touch();
      vi.advanceTimersByTime(900);
      expect(onIdle).not.toHaveBeenCalled();
      vi.advanceTimersByTime(100);
      expect(onIdle).toHaveBeenCalledTimes(1);
      timer.stop();
    } finally {
      vi.useRealTimers();
    }
  });

  it("hold 期间不算空闲，release 之后接着算", async () => {
    vi.useFakeTimers();
    try {
      const onIdle = vi.fn();
      const timer = new IdleTimer(1000, onIdle);
      timer.touch();
      vi.advanceTimersByTime(900);
      timer.hold();
      vi.advanceTimersByTime(5000);
      expect(onIdle).not.toHaveBeenCalled();
      timer.release();
      vi.advanceTimersByTime(99); // 暂停时还剩 100 毫秒
      expect(onIdle).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(onIdle).toHaveBeenCalledTimes(1);
      timer.stop();
    } finally {
      vi.useRealTimers();
    }
  });

  it("时限超过 2^31-1 毫秒时分段重设，不会立刻触发", () => {
    const onIdle = vi.fn();
    const timer = new IdleTimer(Number.MAX_SAFE_INTEGER, onIdle);
    timer.touch();
    expect(onIdle).not.toHaveBeenCalled();
    timer.stop();
  });

  it("stop 之后不再触发", () => {
    vi.useFakeTimers();
    try {
      const onIdle = vi.fn();
      const timer = new IdleTimer(1000, onIdle);
      timer.touch();
      timer.stop();
      vi.advanceTimersByTime(5000);
      expect(onIdle).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("stdin EOF", () => {
  it("写端一关就调一次 onEof，数据被丢弃", async () => {
    const stream = new PassThrough();
    const onEof = vi.fn();
    const watching = watchStdinEof(stream, onEof);
    stream.write("外壳写的几行\n");
    await new Promise((done) => setTimeout(done, 20));
    expect(onEof).not.toHaveBeenCalled();
    stream.end();
    await watching;
    expect(onEof).toHaveBeenCalledTimes(1);
  });

  it("读出错也调一次 onEof", async () => {
    const stream = new PassThrough();
    const onEof = vi.fn();
    const watching = watchStdinEof(stream, onEof);
    stream.destroy(new Error("管道断了"));
    await watching;
    expect(onEof).toHaveBeenCalledTimes(1);
  });

  it("没有 stdin 时什么都不做", async () => {
    const onEof = vi.fn();
    await watchStdinEof(null, onEof);
    expect(onEof).not.toHaveBeenCalled();
  });
});

describe("信号", () => {
  it("装上去之后能摘下来，不留监听器", () => {
    const before = process.listenerCount("SIGTERM");
    const detach = watchSignals(() => {});
    expect(process.listenerCount("SIGTERM")).toBe(before + 1);
    detach();
    expect(process.listenerCount("SIGTERM")).toBe(before);
    detach();
    expect(process.listenerCount("SIGTERM")).toBe(before);
  });
});
