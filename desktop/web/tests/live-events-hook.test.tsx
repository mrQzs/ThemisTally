// 实时 status 钩子（合同第 7 步）：夹具模式原样返回 initial 且不订阅；真实模式收到推送后返回最新 status。
// 真实模式的开关用 vi.mock 把 liveModeIsReal 置真（api 仍走夹具分支，不发真请求）。
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import statusJson from '../src/mock/status.json';
import {
  liveEvents,
  setEventStreamFactoryForTests,
  type LiveStreamEvent,
  type LiveStreamHandle,
} from '../src/live/events';
import { useLiveStatus } from '../src/live/useLiveStatus';

const RUNNING = 'ui-readonly-api/attempt-001';
const mode = { real: false };

vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => mode.real,
  liveClient: () => null,
  setLiveClientForTests: () => {},
}));

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

function rows(toolCalls: number): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === RUNNING
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: 1146, deltas_since_last_tool: 0, long_idle: false } }
      : r,
  );
}

function Probe({ initial }: { initial: any[] }) {
  const status = useLiveStatus(initial);
  const row = status.find((r: any) => r.attempt === RUNNING);
  return <span data-testid="tt-live">{String(row?.live?.tool_calls ?? 'none')}</span>;
}

let stream: FakeStream | null = null;
let created = 0;

function install() {
  stream = null;
  created = 0;
  setEventStreamFactoryForTests(() => {
    created += 1;
    stream = new FakeStream();
    return stream as unknown as LiveStreamHandle;
  });
}

function push(type: 'snapshot' | 'update', lastEventId: string, data: string) {
  act(() => {
    stream?.emit(type, lastEventId, data);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  mode.real = false;
  install();
});

afterEach(() => {
  cleanup();
  setEventStreamFactoryForTests(undefined);
  vi.useRealTimers();
});

describe('useLiveStatus：夹具模式', () => {
  it('原样返回 initial 且不订阅：换 initial 用新值，不建流、不排计时器', () => {
    const first = render(<Probe initial={rows(99)} />);
    expect(first.getByTestId('tt-live').textContent).toBe('99');
    first.rerender(<Probe initial={rows(77)} />);
    expect(first.getByTestId('tt-live').textContent).toBe('77');
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
    expect(liveEvents.getStatus()).toBeNull();
  });
});

describe('useLiveStatus：真实模式', () => {
  it('收到 ok:true 推送返回最新；ok:false 不覆盖；重复与过期丢弃', () => {
    mode.real = true;
    const view = render(<Probe initial={rows(99)} />);
    expect(view.getByTestId('tt-live').textContent).toBe('99');
    expect(created).toBe(1);
    push('snapshot', '5', envelope(rows(41)));
    expect(view.getByTestId('tt-live').textContent).toBe('41');
    push('update', '6', envelope(null, false));
    expect(view.getByTestId('tt-live').textContent).toBe('41');
    push('update', '6', envelope(rows(60)));
    expect(view.getByTestId('tt-live').textContent).toBe('41');
    push('update', '7', envelope(rows(50)));
    expect(view.getByTestId('tt-live').textContent).toBe('50');
  });

  it('卸载后最后一个订阅者离开：流被关掉', () => {
    mode.real = true;
    const view = render(<Probe initial={rows(99)} />);
    expect(stream).not.toBeNull();
    view.unmount();
    expect((stream as FakeStream).closed).toBe(true);
  });
});
