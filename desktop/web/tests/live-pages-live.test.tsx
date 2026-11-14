// 页面实时接线（合同第 7 步）：真实模式下总览页与任务页首屏仍一次性读，收到推送后运行中的数字跟着变。
// 用 vi.mock 把 liveModeIsReal 置真、liveClient 置 null（api 走夹具分支，不发真请求），
// 假流经 setEventStreamFactoryForTests 注入。
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import statusJson from '../src/mock/status.json';
import { setEventStreamFactoryForTests, type LiveStreamEvent, type LiveStreamHandle } from '../src/live/events';
import { setConnectionState } from '../src/live/connection';

const RUNNING = 'ui-readonly-api/attempt-001';

vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => true,
  liveClient: () => null,
  setLiveClientForTests: () => {},
}));

class FakeStream {
  listeners = new Map<string, Set<(event: LiveStreamEvent) => void>>();
  closed = false;
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

function livePatch(toolCalls: number, elapsedSeconds: number): Record<string, unknown> {
  return { live: { tool_calls: toolCalls, elapsed_seconds: elapsedSeconds, deltas_since_last_tool: 0, long_idle: false } };
}

function rows(patch: Record<string, unknown>): any[] {
  return (statusJson as any[]).map((r) => (r.attempt === RUNNING ? { ...r, ...patch } : r));
}

let stream: FakeStream | null = null;

function install() {
  stream = null;
  setEventStreamFactoryForTests(() => {
    stream = new FakeStream();
    return stream as unknown as LiveStreamHandle;
  });
}

function push(type: 'snapshot' | 'update', lastEventId: string, data: string) {
  act(() => {
    stream?.emit(type, lastEventId, data);
  });
}

function text(): string {
  return (document.body.textContent || '').replace(/\s+/g, ' ');
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  window.location.hash = '';
  install();
});

afterEach(async () => {
  cleanup();
  setEventStreamFactoryForTests(undefined);
  setConnectionState('connected');
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('页面实时接线', () => {
  it('总览页：首屏一次性读；推送后运行中的数字跟着变；过期与 ok:false 不动', async () => {
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(text()).toContain('工具调用 37 次');
    expect(text()).toContain('已用 19 分 6 秒');
    push('snapshot', '1', envelope(rows(livePatch(41, 1200))));
    expect(text()).toContain('工具调用 41 次');
    expect(text()).toContain('已用 20 分 0 秒');
    push('update', '1', envelope(rows(livePatch(99, 1))));
    expect(text()).toContain('工具调用 41 次');
    push('update', '2', envelope(null, false));
    expect(text()).toContain('工具调用 41 次');
    push('update', '3', envelope(rows(livePatch(45, 1300))));
    expect(text()).toContain('工具调用 45 次');
    expect(text()).toContain('已用 21 分 40 秒');
    expect(text()).not.toContain('工具调用 41 次');
  });

  it('任务页列表：rows 用实时 status 覆盖（运行中的用时跟着变）', async () => {
    window.location.hash = '#/tasks';
    render(<App />);
    await settle();
    expect(text()).toContain('已用');
    push('snapshot', '10', envelope(rows(livePatch(41, 7777))));
    expect(text()).toContain('已用 2 小时 9 分');
    push('update', '11', envelope(rows(livePatch(41, 61))));
    expect(text()).toContain('已用 1 分 1 秒');
    expect(text()).not.toContain('已用 2 小时 9 分');
  });

  it('任务页详情：实时 status 里有同 attempt 的行时覆盖；没有时保留首屏读到的行', async () => {
    window.location.hash = '#/tasks/ui-readonly-api/attempt-001';
    render(<App />);
    await settle();
    expect(text()).not.toContain('5,632,345');
    push('snapshot', '20', envelope(rows({ tokens: 5632345 })));
    expect(text()).toContain('5,632,345');
    push('update', '21', envelope((statusJson as any[]).filter((r: any) => r.attempt !== RUNNING)));
    expect(text()).not.toContain('5,632,345');
  });
});
