// 事件流客户端纯逻辑（合同第 7 步）：假流与假计时器注入 createLiveEvents，不靠固定等待、不发真请求。
// 序号去重与过期丢弃、服务重启后 snapshot 变小整份替换、退避下限与抖动、重连靠 snapshot 重建、
// 多订阅者只一条流、ok:false 不覆盖数据、夹具模式不建流不起计时器。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import statusJson from '../src/mock/status.json';
import {
  createLiveEvents,
  liveEvents,
  setEventStreamFactoryForTests,
  type LiveStreamEvent,
  type LiveStreamHandle,
} from '../src/live/events';
import { getConnectionState, getReconnectCount, setConnectionState, setReconnectCount } from '../src/live/connection';

const RUNNING = 'ui-readonly-api/attempt-001';

class FakeStream {
  closed = false;
  listeners = new Map<string, Set<(event: LiveStreamEvent) => void>>();
  addEventListener(type: string, listener: (event: LiveStreamEvent) => void): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: (event: LiveStreamEvent) => void): void {
    this.listeners.get(type)?.delete(listener);
  }
  close(): void {
    this.closed = true;
  }
  emit(type: string, lastEventId: string, data: string): void {
    const event = { type, lastEventId, data } as unknown as LiveStreamEvent;
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener(event);
  }
}

function envelope(rows: unknown, ok = true): string {
  return JSON.stringify({
    ok,
    exit_code: ok ? 0 : null,
    data: ok ? rows : null,
    output: [],
    messages: ok ? [] : ['ERROR: 读 status 超时'],
    command: ['status'],
    elapsed_ms: 3,
  });
}

function rows(toolCalls: number, elapsedSeconds = 1146): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === RUNNING
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: elapsedSeconds, deltas_since_last_tool: 0, long_idle: false } }
      : r,
  );
}

function toolCallsOf(status: unknown): unknown {
  const row = (status as any[])?.find((r) => r.attempt === RUNNING);
  return row?.live?.tool_calls ?? 'none';
}

const delays: number[] = [];

function make(randomValue: number) {
  const streams: FakeStream[] = [];
  const options = {
    createStream: () => {
      const stream = new FakeStream();
      streams.push(stream);
      return stream as unknown as LiveStreamHandle;
    },
    setTimer: (fn: () => void, delayMs: number) => {
      delays.push(delayMs);
      return setTimeout(fn, delayMs);
    },
    clearTimer: (handle: unknown) => clearTimeout(handle as any),
    random: () => randomValue,
  };
  return { streams, options };
}

beforeEach(() => {
  delays.length = 0;
  vi.useFakeTimers();
  setConnectionState('connected');
  setReconnectCount(0);
});

afterEach(() => {
  vi.useRealTimers();
  setEventStreamFactoryForTests(undefined);
  setConnectionState('connected');
  setReconnectCount(0);
});

describe('createLiveEvents：序号', () => {
  it('snapshot 整份替换并重置基线；update 序号不大于基线或还没 snapshot 时丢弃', () => {
    const { streams, options } = make(0.5);
    const events = createLiveEvents(options);
    let notified = 0;
    const off = events.subscribe(() => {
      notified += 1;
    });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', envelope(rows(37)));
    expect(toolCallsOf(events.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '5', envelope(rows(99)));
    stream.emit('update', '3', envelope(rows(98)));
    expect(toolCallsOf(events.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', envelope(rows(41)));
    expect(toolCallsOf(events.getStatus())).toBe(41);
    expect(notified).toBe(2);
    off();

    const fresh = make(0.5);
    const other = createLiveEvents(fresh.options);
    let notifiedOther = 0;
    other.subscribe(() => {
      notifiedOther += 1;
    });
    fresh.streams[0]!.emit('update', '9', envelope(rows(77)));
    expect(other.getStatus()).toBeNull();
    expect(notifiedOther).toBe(0);
  });

  it('服务重启后 snapshot 序号变小：照样整份替换并把基线重置', () => {
    const { streams, options } = make(0.5);
    const events = createLiveEvents(options);
    events.subscribe(() => {});
    const stream = streams[0]!;
    stream.emit('snapshot', '100', envelope(rows(37)));
    stream.emit('snapshot', '2', envelope(rows(41)));
    expect(toolCallsOf(events.getStatus())).toBe(41);
    stream.emit('update', '3', envelope(rows(45)));
    expect(toolCallsOf(events.getStatus())).toBe(45);
    stream.emit('update', '2', envelope(rows(99)));
    expect(toolCallsOf(events.getStatus())).toBe(45);
  });

  it('序号解析不出非负整数：丢弃（不改数据、不推进基线、不通知）', () => {
    const { streams, options } = make(0.5);
    const events = createLiveEvents(options);
    let notified = 0;
    events.subscribe(() => {
      notified += 1;
    });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', envelope(rows(37)));
    stream.emit('update', 'abc', envelope(rows(50)));
    stream.emit('update', '-1', envelope(rows(51)));
    stream.emit('update', '', envelope(rows(52)));
    expect(toolCallsOf(events.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', envelope(rows(53)));
    expect(toolCallsOf(events.getStatus())).toBe(53);
    expect(notified).toBe(2);
  });

  it('data 不是合法 JSON：丢弃；不是七字段信封：按 ok:false 处理（不覆盖、序号照常推进）', () => {
    const { streams, options } = make(0.5);
    const events = createLiveEvents(options);
    let notified = 0;
    events.subscribe(() => {
      notified += 1;
    });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', envelope(rows(37)));
    stream.emit('update', '6', '{not json');
    expect(toolCallsOf(events.getStatus())).toBe(37);
    stream.emit('update', '6', JSON.stringify({ foo: 1 }));
    expect(toolCallsOf(events.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', envelope(rows(60)));
    expect(toolCallsOf(events.getStatus())).toBe(37);
    stream.emit('update', '7', envelope(rows(61)));
    expect(toolCallsOf(events.getStatus())).toBe(61);
    expect(notified).toBe(2);
  });

  it('ok:false 的推送不覆盖已显示的数据，也不通知订阅者', () => {
    const { streams, options } = make(0.5);
    const events = createLiveEvents(options);
    let notified = 0;
    events.subscribe(() => {
      notified += 1;
    });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', envelope(rows(37)));
    const seen = events.getStatus();
    stream.emit('update', '6', envelope(null, false));
    expect(events.getStatus()).toBe(seen);
    expect(notified).toBe(1);
  });
});

describe('createLiveEvents：退避与重连', () => {
  it('error 后关掉原生流并自己排重连：下限 3000、指数增长、上限 30000、抖动只往后加', () => {
    const { streams, options } = make(0);
    const events = createLiveEvents(options);
    events.subscribe(() => {});
    const first = streams[0]!;
    first.emit('snapshot', '5', envelope(rows(37)));
    first.emit('error', '', '');
    expect(first.closed).toBe(true);
    expect(delays[0]).toBe(3000);
    expect(events.getReconnectCount()).toBe(1);
    expect(getConnectionState()).toBe('reconnecting');
    expect(getReconnectCount()).toBe(1);
    vi.advanceTimersByTime(3000);
    expect(streams.length).toBe(2);
    streams[1]!.emit('error', '', '');
    expect(delays[1]).toBe(6000);
    expect(events.getReconnectCount()).toBe(2);
    vi.advanceTimersByTime(6000);
    streams[2]!.emit('error', '', '');
    expect(delays[2]).toBe(12000);
    vi.advanceTimersByTime(12000);
    streams[3]!.emit('error', '', '');
    expect(delays[3]).toBe(24000);
    vi.advanceTimersByTime(24000);
    streams[4]!.emit('error', '', '');
    expect(delays[4]).toBe(30000);
    vi.advanceTimersByTime(30000);
    streams[5]!.emit('error', '', '');
    expect(delays[5]).toBe(30000);

    const jittered = make(0.9999);
    const other = createLiveEvents(jittered.options);
    other.subscribe(() => {});
    jittered.streams[0]!.emit('error', '', '');
    expect(delays.at(-1)).toBe(3999);
  });

  it('重连后靠 snapshot 重建（整份替换，不合并旧数据），次数清零', () => {
    const { streams, options } = make(0);
    const events = createLiveEvents(options);
    events.subscribe(() => {});
    streams[0]!.emit('snapshot', '5', envelope(rows(37)));
    streams[0]!.emit('error', '', '');
    expect(events.getReconnectCount()).toBe(1);
    vi.advanceTimersByTime(3000);
    streams[1]!.emit('snapshot', '9', envelope(rows(41)));
    expect(toolCallsOf(events.getStatus())).toBe(41);
    expect(events.getReconnectCount()).toBe(0);
    expect(getConnectionState()).toBe('connected');
    expect(getReconnectCount()).toBe(0);
  });

  it('多订阅者只一条流；最后一个离开关流、清掉待跑的重连计时器、次数清零；退订可重复调用', () => {
    const { streams, options } = make(0);
    const events = createLiveEvents(options);
    const off1 = events.subscribe(() => {});
    const off2 = events.subscribe(() => {});
    expect(streams.length).toBe(1);
    streams[0]!.emit('snapshot', '5', envelope(rows(37)));
    streams[0]!.emit('error', '', '');
    off1();
    expect(vi.getTimerCount()).toBeGreaterThanOrEqual(1);
    vi.advanceTimersByTime(31000);
    expect(streams.length).toBe(2);
    streams[1]!.emit('error', '', '');
    off2();
    expect(streams[1]!.closed).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(events.getReconnectCount()).toBe(0);
    const before = streams.length;
    vi.advanceTimersByTime(61000);
    expect(streams.length).toBe(before);
    expect(() => {
      off2();
      off2();
    }).not.toThrow();
  });
});

describe('默认实例：夹具模式', () => {
  it('订阅是空操作：不建流、不排计时器、getStatus 为空；退订可重复调用', () => {
    let created = 0;
    setEventStreamFactoryForTests(() => {
      created += 1;
      return new FakeStream() as unknown as LiveStreamHandle;
    });
    const off = liveEvents.subscribe(() => {});
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
    expect(liveEvents.getStatus()).toBeNull();
    expect(typeof off).toBe('function');
    off();
    expect(() => off()).not.toThrow();
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });
});
