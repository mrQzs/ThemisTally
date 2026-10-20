import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

beforeEach(() => { location.hash = '#/showcase'; vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const DEMOS = ['text-field', 'form-dialog', 'segmented', 'switch-checkbox', 'tabs', 'table',
  'key-value', 'empty-state', 'skeleton', 'connection', 'breadcrumb'];
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
function demo(name: string): HTMLElement {
  const nodes = document.querySelectorAll(`[data-demo="${name}"]`);
  expect(nodes.length, `应恰有一个 data-demo="${name}"`).toBe(1);
  return nodes[0] as HTMLElement;
}
function buttonByText(root: Element, text: string) {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text);
  expect(hit, `找不到「${text}」`).toBeTruthy();
  return hit as HTMLButtonElement;
}
const key = (k: string) => fireEvent.keyDown(document.activeElement as Element, { key: k });
function advance(ms: number) { act(() => { vi.advanceTimersByTime(ms); }); }

describe('陈列页的 11 节表单与数据演示', () => {
  it('11 个 data-demo 节都在、顺序对、都在轻提示之后，复用 showcase__section/h2', () => {
    render(<App />);
    const toast = demo('toast');
    const secs = DEMOS.map(demo);
    for (let i = 0; i < secs.length; i += 1) {
      const before = i === 0 ? toast : secs[i - 1];
      expect(before.compareDocumentPosition(secs[i]) & Node.DOCUMENT_POSITION_FOLLOWING, DEMOS[i]).toBeTruthy();
      expect(secs[i].classList.contains('showcase__section')).toBe(true);
      const h2 = secs[i].querySelector('h2.showcase__h2');
      expect(h2).not.toBeNull();
      expect(textOf(h2)).not.toMatch(/Button/);
    }
  });

  it('整页只有轻提示一个 role=status；新演示无主题字样按钮；文字按钮都有 aria-label', () => {
    render(<App />);
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '' && !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
    expect(document.querySelectorAll('[role="status"]').length).toBe(1);
    for (const name of DEMOS) {
      const sec = demo(name);
      expect(textOf(sec)).not.toContain('跟随系统');
      const themed = Array.from(sec.querySelectorAll('button')).filter((b) => ['亮', '暗', '跟随系统'].includes(textOf(b)));
      expect(themed.length).toBe(0);
    }
  });

  it('表单对话框：输入框与下拉有 label、mousedown 不被阻止、能聚焦；遮罩仍被阻止', () => {
    render(<App />);
    const sec = demo('form-dialog');
    act(() => { buttonByText(sec, '打开表单对话框').focus(); });
    fireEvent.click(buttonByText(sec, '打开表单对话框'));
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const input = dialog.querySelector('input') as HTMLInputElement;
    expect(input.labels && input.labels.length).toBeGreaterThan(0);
    expect(dialog.querySelector('[aria-haspopup], [aria-expanded], [role="menu"]')).toBeNull();
    expect(fireEvent.mouseDown(input)).toBe(true);
    act(() => { input.focus(); });
    expect(document.activeElement).toBe(input);
    expect(fireEvent.mouseDown(document.querySelector('.tt-dialog-scrim') as HTMLElement)).toBe(false);
  });

  it('表格：切 40/44/52；用时/token 数字列；Enter/点击后「上次打开」变化', () => {
    render(<App />);
    const sec = demo('table');
    const radios = Array.from(sec.querySelectorAll<HTMLElement>('[role="radiogroup"] [role="radio"]'));
    expect(radios.length).toBe(3);
    ['40', '44', '52'].forEach((n, i) => {
      expect(textOf(radios[i])).toContain(n);
      fireEvent.click(radios[i]);
      expect((sec.querySelector('table') as HTMLElement).getAttribute('data-row-height')).toBe(n);
    });
    const table = sec.querySelector('table') as HTMLElement;
    const heads = Array.from(table.querySelectorAll('th')).map(textOf);
    expect(heads.some((h) => h.includes('用时'))).toBe(true);
    expect(heads.some((h) => /token/i.test(h))).toBe(true);
    expect(table.querySelectorAll('td.tt-num').length).toBeGreaterThan(0);
    expect(table.querySelectorAll('tr[tabindex="0"]').length).toBe(1);
    const rows = () => Array.from(sec.querySelectorAll<HTMLElement>('tbody tr'));
    const current = rows().find((r) => r.getAttribute('tabindex') === '0') as HTMLElement;
    act(() => { current.focus(); });
    key('Enter');
    const afterEnter = textOf(sec).split('上次打开：')[1];
    expect((afterEnter || '').trim().length).toBeGreaterThan(0);
    fireEvent.click(rows()[rows().length - 1]);
    expect(textOf(sec).split('上次打开：')[1]).not.toBe(afterEnter);
  });

  it('骨架屏：加载 2 秒 299ms 无、300ms 有、2 秒后消失；加载 0.2 秒全程不出现', () => {
    render(<App />);
    const sec = demo('skeleton');
    const two = buttonByText(sec, '加载 2 秒');
    const fast = buttonByText(sec, '加载 0.2 秒');
    act(() => { two.focus(); });
    fireEvent.click(two);
    advance(299);
    expect(sec.querySelector('.tt-skel')).toBeNull();
    advance(1);
    expect(sec.querySelectorAll('.tt-skel').length).toBeGreaterThan(0);
    advance(1200);
    expect(sec.querySelector('.tt-skel')).not.toBeNull();
    advance(700);
    expect(sec.querySelector('.tt-skel')).toBeNull();
    fireEvent.click(fast);
    for (let i = 0; i < 20; i += 1) {
      advance(50);
      expect(sec.querySelector('.tt-skel')).toBeNull();
    }
  });

  it('连接胶囊三态并排、各能点开浮层（含 pid 与启动于）', () => {
    render(<App />);
    const sec = demo('connection');
    const states = Array.from(sec.querySelectorAll('[data-state]')).map((el) => el.getAttribute('data-state'));
    for (const s of ['connected', 'reconnecting', 'disconnected']) expect(states).toContain(s);
    const pills = Array.from(sec.querySelectorAll<HTMLElement>('button[aria-expanded]'));
    expect(pills.length).toBe(3);
    for (const pill of pills) {
      fireEvent.click(pill);
      expect(pill.getAttribute('aria-expanded')).toBe('true');
      const pop = document.getElementById(pill.getAttribute('aria-controls') || '');
      expect(textOf(pop)).toContain('pid');
      expect(textOf(pop)).toContain('启动于');
      fireEvent.click(pill);
      expect(pill.getAttribute('aria-expanded')).toBe('false');
    }
  });
});
