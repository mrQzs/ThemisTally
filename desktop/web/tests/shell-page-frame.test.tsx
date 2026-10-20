// 页面框架（合同第 8 条 / D09）：五态（299ms 无骨架、300ms 有；有数据、空、出错）；出错块的命令、退出码、
// 报错原文都是纯文本、点重试再调一次；Promise 被拒只写「没有收到服务的回应」；断线时保留数据、role=alert Banner、
// 「可能已过期」、data-stale=true；刷新保留数据、按钮 aria-busy；先发后回的结果被丢弃。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PageFrame } from '../src/shell/PageFrame';
import type { Envelope } from '../src/api';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function env<T>(data: T, overrides: Partial<Envelope<T>> = {}): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['x'], elapsed_ms: 0, ...overrides };
}
async function flush() { await act(async () => { await Promise.resolve(); }); }
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}
function state() {
  return document.querySelector('[data-page-state]')?.getAttribute('data-page-state');
}

describe('页面框架', () => {
  it('加载态：299ms 无骨架、300ms 有', () => {
    render(<PageFrame title="t" load={() => new Promise<Envelope<unknown>>(() => {})}>{() => <p>d</p>}</PageFrame>);
    expect(document.querySelector('.tt-skeleton')).toBeNull();
    act(() => { vi.advanceTimersByTime(299); });
    expect(document.querySelector('.tt-skeleton')).toBeNull();
    act(() => { vi.advanceTimersByTime(1); });
    expect(document.querySelectorAll('.tt-skel').length).toBeGreaterThan(0);
  });

  it('有数据渲染 children、data-page-state=data', async () => {
    render(<PageFrame<{ n: number }> title="t" load={() => Promise.resolve(env({ n: 5 }))}>{(d) => <p>读到 {d.n}</p>}</PageFrame>);
    await flush();
    expect(state()).toBe('data');
    expect(document.body.textContent).toContain('读到 5');
  });

  it('isEmpty 真渲染空态', async () => {
    render(
      <PageFrame<string[]> title="t" load={() => Promise.resolve(env([] as string[]))} isEmpty={(d) => d.length === 0} empty={{ title: '空的', description: '说明文字' }}>
        {() => <p>读到</p>}
      </PageFrame>,
    );
    await flush();
    expect(state()).toBe('empty');
    expect(document.querySelector('.tt-empty')?.textContent).toContain('空的');
    expect(document.querySelector('.tt-empty')?.textContent).toContain('说明文字');
  });

  it('ok 假渲染出错块（命令、退出码、报错原文纯文本），点重试再调一次', async () => {
    const load = vi.fn(() => Promise.resolve(env(null, { ok: false, exit_code: 2, messages: ['ERROR 炸了 <img>'], command: ['status'] })));
    render(<PageFrame title="t" load={load}>{() => <p>d</p>}</PageFrame>);
    await flush();
    expect(state()).toBe('error');
    expect(document.body.textContent).toContain('没能读到数据');
    expect(document.body.textContent).toContain('命令（status）返回退出码 2');
    expect(document.body.textContent).toContain('内核报错如下（纯文本，已脱敏）');
    const msg = document.querySelector('.tt-page__error-msg') as HTMLElement;
    expect(msg.textContent).toContain('ERROR 炸了 <img>');
    expect(msg.querySelector('img')).toBeNull(); // 纯文本，不渲染 img
    expect(load).toHaveBeenCalledTimes(1);
    fireEvent.click(document.querySelector('.tt-page__error button') as HTMLElement);
    await flush();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('Promise 被拒只写「没有收到服务的回应」', async () => {
    render(<PageFrame title="t" load={() => Promise.reject(new Error('boom'))}>{() => <p>d</p>}</PageFrame>);
    await flush();
    expect(state()).toBe('error');
    expect(document.body.textContent).toContain('没有收到服务的回应');
    expect(document.querySelector('.tt-page__error-msg')).toBeNull();
  });

  it('断线：role=alert Banner、「可能已过期」Tag、data-stale=true，数据照常', async () => {
    location.hash = '#/overview?mock=offline';
    render(<PageFrame<{ n: number }> title="t" load={() => Promise.resolve(env({ n: 1 }))}>{(d) => <p>读到 {d.n}</p>}</PageFrame>);
    await flush();
    expect(document.querySelector('[data-page-state]')?.getAttribute('data-stale')).toBe('true');
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('与本机服务的连接断开');
    expect(document.body.textContent).toContain('可能已过期');
    expect(document.body.textContent).toContain('读到 1');
  });

  it('刷新保留数据、按钮 aria-busy', async () => {
    let call = 0;
    const load = vi.fn(() => {
      call += 1;
      return call === 1 ? Promise.resolve(env({ n: 1 })) : new Promise<Envelope<{ n: number }>>(() => {});
    });
    render(<PageFrame<{ n: number }> title="t" load={load}>{(d) => <p>读到 {d.n}</p>}</PageFrame>);
    await flush();
    expect(document.body.textContent).toContain('读到 1');
    fireEvent.click(document.querySelector('.tt-page__actions button') as HTMLElement);
    const btn = document.querySelector('.tt-page__actions button') as HTMLElement;
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(document.body.textContent).toContain('读到 1'); // 数据保留
    expect(load).toHaveBeenCalledTimes(2);
  });

  it('只认最近一次请求：先发后回的结果被丢弃', async () => {
    const defs = [deferred<Envelope<{ n: number }>>(), deferred<Envelope<{ n: number }>>()];
    let i = 0;
    const load = vi.fn(() => defs[Math.min(i++, 1)].promise);
    render(<PageFrame<{ n: number }> title="t" load={load}>{(d) => <p>值 {d.n}</p>}</PageFrame>);
    await flush(); // 挂载请求 pending（defs[0]）
    fireEvent.click(document.querySelector('.tt-page__actions button') as HTMLElement); // 刷新请求 defs[1]
    await flush();
    await act(async () => { defs[1].resolve(env({ n: 2 })); await Promise.resolve(); });
    expect(document.body.textContent).toContain('值 2');
    await act(async () => { defs[0].resolve(env({ n: 1 })); await Promise.resolve(); }); // 过期，丢弃
    expect(document.body.textContent).toContain('值 2');
  });
});
