import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConnectionPill } from '../src/components/ConnectionPill';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function mountPill(props: any = {}, outer?: (e: any) => void) {
  const ui = <ConnectionPill state="connected" {...props} />;
  const r = render(outer ? <div onKeyDown={outer}>{ui}</div> : ui);
  const pill = r.container.querySelector('button[aria-expanded]') as HTMLButtonElement;
  return { ...r, pill };
}
function popoverOf(pill: HTMLElement): HTMLElement | null {
  const id = pill.getAttribute('aria-controls');
  if (!id) return null;
  const el = document.getElementById(id);
  if (!el) return null;
  return el as HTMLElement;
}
const key = (k: string) => fireEvent.keyDown(document.activeElement as Element, { key: k });
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();

describe('连接胶囊', () => {
  it('三态文字与 data-state；圆点 aria-hidden、文字 aria-live=polite', () => {
    const c = mountPill({ state: 'connected' });
    expect(textOf(c.pill)).toBe('已连接');
    expect(c.container.querySelector('[data-state="connected"]')).not.toBeNull();
    expect(c.pill.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(c.pill.querySelector('[aria-live="polite"]')).not.toBeNull();
    c.unmount();
    const rc = mountPill({ state: 'reconnecting', attempt: 3 });
    expect(textOf(rc.pill)).toMatch(/^重连中（第\s*3\s*次）$/);
    expect(rc.container.querySelector('[data-state="reconnecting"]')).not.toBeNull();
    rc.unmount();
    const d = mountPill({ state: 'disconnected' });
    expect(textOf(d.pill)).toBe('已断开');
    expect(d.container.querySelector('[data-state="disconnected"]')).not.toBeNull();
  });

  it('点一下打开、再点关闭；浮层紧跟胶囊、里面 pid/启动于/事件流、没给的值未知、无可聚焦元素', () => {
    const { pill } = mountPill({ pid: 4242, startedAt: '2026-10-20 10:00', stream: '事件流正常' });
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(popoverOf(pill)).toBeNull();
    fireEvent.click(pill);
    expect(pill.getAttribute('aria-expanded')).toBe('true');
    const pop = popoverOf(pill) as HTMLElement;
    expect(pop).not.toBeNull();
    expect(pop.previousElementSibling === pill).toBe(true);
    expect(Array.from(pop.querySelectorAll('dt')).map(textOf)).toEqual(['pid', '启动于', '事件流']);
    expect(Array.from(pop.querySelectorAll('dd')).map(textOf)).toEqual(['4242', '2026-10-20 10:00', '事件流正常']);
    expect(pop.querySelectorAll('a[href], button, input, select, textarea, [tabindex]').length).toBe(0);
    fireEvent.click(pill);
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(popoverOf(pill)).toBeNull();
  });

  it('没给的值显示「未知」', () => {
    const { pill } = mountPill({ state: 'connected' });
    fireEvent.click(pill);
    const pop = popoverOf(pill) as HTMLElement;
    expect(Array.from(pop.querySelectorAll('dd')).map(textOf)).toEqual(['未知', '未知', '未知']);
  });

  it('Esc 关闭并 stopPropagation、焦点留胶囊；点外面关闭、点浮层或胶囊不关', () => {
    const outer = vi.fn();
    const { pill } = mountPill({ pid: 1 }, outer);
    act(() => { pill.focus(); });
    fireEvent.click(pill);
    key('Escape');
    expect(popoverOf(pill)).toBeNull();
    expect(document.activeElement).toBe(pill);
    expect(outer.mock.calls.filter((c: any[]) => c[0] && c[0].key === 'Escape').length).toBe(0);
    fireEvent.click(pill);
    const pop = popoverOf(pill) as HTMLElement;
    fireEvent.mouseDown(pop);
    expect(popoverOf(pill)).not.toBeNull();
    fireEvent.mouseDown(pill);
    expect(popoverOf(pill)).not.toBeNull();
    fireEvent.mouseDown(document.body);
    expect(popoverOf(pill)).toBeNull();
    expect(pill.getAttribute('aria-expanded')).toBe('false');
  });
});
