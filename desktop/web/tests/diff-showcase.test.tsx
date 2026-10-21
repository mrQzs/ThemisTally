import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Showcase from '../src/showcase/DiffShowcase';

// 第 7 片演示（合同 §6、过渡断言 P9）：渲染 DiffShowcase，只看结构、文字与计时，不挂到陈列页。
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  delete (navigator as unknown as { clipboard?: unknown }).clipboard;
});

const ESC = '\u001b';
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const buttonsByText = (root: ParentNode, text: string) =>
  Array.from(root.querySelectorAll('button')).filter((b) => textOf(b) === text) as HTMLButtonElement[];
const rowCount = (root: HTMLElement) => root.querySelectorAll('.tt-viewer__row').length;
async function expandAll(sec: HTMLElement) {
  for (let i = 0; i < 30; i += 1) {
    const closed = Array.from(sec.querySelectorAll('.tt-diff__file-head button[aria-expanded="false"]')) as HTMLElement[];
    if (closed.length === 0) return;
    await act(async () => { fireEvent.click(closed[0]); });
  }
}

describe('DiffShowcase', () => {
  it('两节，data-demo 依次为 diff-view、log-follow，各一个 h2.showcase__h2', () => {
    render(<Showcase />);
    const found = Array.from(document.querySelectorAll('[data-demo]')).map((e) => e.getAttribute('data-demo'));
    expect(found).toEqual(['diff-view', 'log-follow']);
    for (const name of ['diff-view', 'log-follow']) {
      const sec = document.querySelector(`[data-demo="${name}"]`) as HTMLElement;
      expect(sec.tagName).toBe('SECTION');
      expect(sec.classList.contains('showcase__section')).toBe(true);
      const h2s = sec.querySelectorAll('h2.showcase__h2');
      expect(h2s.length).toBe(1);
      expect(textOf(h2s[0])).not.toBe('');
      expect(textOf(h2s[0])).not.toMatch(/Button/);
    }
  });

  it('不渲染 role=status、对话框、菜单；没有文字的按钮都有 aria-label；按钮文字避开主题字样', () => {
    render(<Showcase />);
    expect(document.querySelector('[role="status"]')).toBeNull();
    expect(document.querySelectorAll('[role="dialog"], [role="menu"], [aria-modal]').length).toBe(0);
    const bad = Array.from(document.querySelectorAll('button')).filter((b) => textOf(b) === '' && !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
    for (const b of Array.from(document.querySelectorAll('button'))) expect(textOf(b)).not.toMatch(/亮|暗|跟随系统/);
  });

  it('diff-view：有改动、新增（折叠）、删除（-- 行）、改名、二进制、超长行、No newline', async () => {
    render(<Showcase />);
    const sec = document.querySelector('[data-demo="diff-view"]') as HTMLElement;
    const view = sec.querySelector('.tt-diff') as HTMLElement;
    expect(textOf(view.querySelector('.tt-diff__summary'))).toMatch(/^candidate\.patch · \d+ 个文件 · \+\d+ −\d+$/);
    const secs = Array.from(view.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
    const statuses = secs.map((s) => s.getAttribute('data-status'));
    for (const want of ['modified', 'added', 'deleted', 'renamed']) expect(statuses).toContain(want);
    expect(secs.some((s) => s.getAttribute('data-status') === 'added' && s.getAttribute('data-binary') !== 'true' && s.getAttribute('data-collapsed') === 'true')).toBe(true);
    expect(secs.some((s) => s.getAttribute('data-binary') === 'true' && textOf(s).includes('二进制文件，不显示内容'))).toBe(true);
    await expandAll(sec);
    const all = Array.from(view.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
    expect(all.filter((s) => s.getAttribute('data-status') === 'modified' && s.getAttribute('data-binary') !== 'true')
      .some((s) => s.querySelectorAll('.tt-diff__row[data-kind="hunk"]').length >= 2)).toBe(true);
    expect(all.filter((s) => s.getAttribute('data-status') === 'deleted')
      .some((s) => Array.from(s.querySelectorAll('.tt-diff__row[data-kind="del"] .tt-diff__text')).some((t) => (t.textContent || '').startsWith('--')))).toBe(true);
    const longest = Math.max(...Array.from(view.querySelectorAll('.tt-diff__text')).map((t) => (t.textContent || '').length));
    expect(longest).toBeGreaterThanOrEqual(2000);
    expect(view.querySelectorAll('.tt-diff__eof').length).toBeGreaterThan(0);
  });

  it('W1 样例只是文字：没有 img/script/a；没有 ESC 与 [31m', async () => {
    render(<Showcase />);
    await expandAll(document.querySelector('[data-demo="diff-view"]') as HTMLElement);
    expect(document.body.querySelectorAll('img, script, a, iframe, object, embed, style, link').length).toBe(0);
    expect(document.body.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const diffText = (document.querySelector('[data-demo="diff-view"]') as HTMLElement).textContent || '';
    expect(diffText).toContain('<script>alert(1)</script>');
    expect(diffText).toContain('<img src=x onerror=alert(1)>');
    expect((document.body.textContent || '').includes(ESC)).toBe(false);
    expect((document.body.textContent || '').includes('[31m')).toBe(false);
  });

  it('log-follow：LogFollow 标题、隐藏行、分片、三个按钮', async () => {
    render(<Showcase />);
    const sec = document.querySelector('[data-demo="log-follow"]') as HTMLElement;
    expect(sec.querySelector('.tt-log')).not.toBeNull();
    expect(textOf(sec.querySelector('.tt-viewer__title'))).toBe('ui-readonly-api / events.jsonl');
    expect(textOf(sec)).toMatch(/第\s*1\/2\s*片/);
    for (let i = 0; i < 12; i += 1) {
      const more = buttonsByText(sec, '继续加载');
      if (more.length === 0) break;
      await act(async () => { fireEvent.click(more[0]); });
      for (let j = 0; j < 40 && buttonsByText(sec, '正在加载…').length > 0; j += 1) {
        await act(async () => { await new Promise((r) => setTimeout(r, 25)); });
      }
    }
    expect(textOf(sec)).toContain('这一行不是合法 JSON，已隐藏');
    expect(textOf(sec)).toContain('这一行超过 4 MiB，已隐藏');
    expect(textOf(sec)).toMatch(/第\s*2\/2\s*片/);
    expect(rowCount(sec)).toBeGreaterThanOrEqual(20);
    for (const label of ['开始追加', '停止追加', '模拟 attempt 已结束']) expect(buttonsByText(sec, label).length).toBe(1);
  });

  it('挂载后没有计时器；[开始追加] 每 400ms 追加一行；[停止追加] 停下；卸载后清空', async () => {
    vi.useFakeTimers();
    const r = render(<Showcase />);
    expect(vi.getTimerCount()).toBe(0);
    const sec = document.querySelector('[data-demo="log-follow"]') as HTMLElement;
    const n0 = rowCount(sec);
    await act(async () => { fireEvent.click(buttonsByText(sec, '开始追加')[0]); });
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    act(() => { vi.advanceTimersByTime(400 * 3); });
    expect(rowCount(sec)).toBe(n0 + 3);
    await act(async () => { fireEvent.click(buttonsByText(sec, '停止追加')[0]); });
    act(() => { vi.advanceTimersByTime(400 * 5); });
    expect(rowCount(sec)).toBe(n0 + 3);
    r.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('[模拟 attempt 已结束] 切换 disabled 与原因', async () => {
    render(<Showcase />);
    const sec = document.querySelector('[data-demo="log-follow"]') as HTMLElement;
    const status = () => sec.querySelector('.tt-log__status') as HTMLElement;
    expect(status().getAttribute('data-follow')).toBe('following');
    await act(async () => { fireEvent.click(buttonsByText(sec, '模拟 attempt 已结束')[0]); });
    expect(status().getAttribute('data-follow')).toBe('disabled');
    expect(textOf(status())).toBe('attempt 已结束，没有新事件');
    await act(async () => { fireEvent.click(buttonsByText(sec, '模拟 attempt 已结束')[0]); });
    expect(status().getAttribute('data-follow')).toBe('following');
  });

  it('复制三种结果文字，不用轻提示', async () => {
    const first = render(<Showcase />);
    await act(async () => { fireEvent.click((first.container.querySelector('[data-demo="log-follow"] button[aria-label="复制已显示的文字"]') as HTMLElement)); });
    for (let i = 0; i < 40 && !textOf(document.querySelector('[data-demo="log-follow"]')).includes('这个环境没有剪贴板接口'); i += 1) {
      await act(async () => { await new Promise((r) => setTimeout(r, 25)); });
    }
    expect(textOf(document.querySelector('[data-demo="log-follow"]'))).toContain('这个环境没有剪贴板接口');
    first.unmount();
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: write }, configurable: true });
    const second = render(<Showcase />);
    await act(async () => { fireEvent.click((second.container.querySelector('[data-demo="log-follow"] button[aria-label="复制已显示的文字"]') as HTMLElement)); });
    for (let i = 0; i < 40 && !/已复制\s*\d+\s*个字符/.test(textOf(document.querySelector('[data-demo="log-follow"]'))); i += 1) {
      await act(async () => { await new Promise((r) => setTimeout(r, 25)); });
    }
    expect(write).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll('.tt-toast, [role="status"]').length).toBe(0);
  });
});
