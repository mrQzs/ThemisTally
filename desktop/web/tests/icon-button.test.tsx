import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IconButton } from '../src/components/IconButton';
import { XIcon } from '../src/icons';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function advance(ms: number) { act(() => { vi.advanceTimersByTime(ms); }); }
function tooltipEl() { return document.querySelector('[role="tooltip"]'); }
function mount(props: Record<string, unknown> = {}) {
  const r = render(<IconButton label="关闭" icon={<XIcon />} {...props} />);
  return { ...r, button: r.container.querySelector('button') as HTMLButtonElement };
}

describe('IconButton', () => {
  it('label 渲染成 aria-label、type=button、图标 aria-hidden、按钮里没有文字', () => {
    const { button } = mount();
    expect(button.getAttribute('aria-label')).toBe('关闭');
    expect(button.getAttribute('type')).toBe('button');
    const svg = button.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    expect((button.textContent || '').trim()).toBe('');
  });

  it('悬停 399ms 没有提示、400ms 出现并带 aria-describedby、移开立即消失', () => {
    const { button } = mount();
    expect(tooltipEl()).toBeNull();
    fireEvent.mouseEnter(button);
    advance(399);
    expect(tooltipEl()).toBeNull();
    advance(1);
    const tip = tooltipEl();
    expect(tip).not.toBeNull();
    expect((tip!.textContent || '').trim()).toBe('关闭');
    expect(button.getAttribute('aria-describedby')).toBe(tip!.id);
    fireEvent.mouseLeave(button);
    expect(tooltipEl()).toBeNull();
    expect(button.hasAttribute('aria-describedby')).toBe(false);
  });

  it('聚焦 400ms 出现，失焦立即消失', () => {
    const { button } = mount();
    fireEvent.focus(button);
    advance(399);
    expect(tooltipEl()).toBeNull();
    advance(1);
    expect(tooltipEl()).not.toBeNull();
    fireEvent.blur(button);
    expect(tooltipEl()).toBeNull();
  });

  it('可见时按 Esc 消失且不再出现，重新悬停才再出现', () => {
    const { button } = mount();
    fireEvent.mouseEnter(button);
    advance(400);
    expect(tooltipEl()).not.toBeNull();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(tooltipEl()).toBeNull();
    advance(1000);
    expect(tooltipEl()).toBeNull();
    fireEvent.mouseLeave(button);
    fireEvent.mouseEnter(button);
    advance(400);
    expect(tooltipEl()).not.toBeNull();
  });

  it('tooltip 属性与名称不同时提示用 tooltip，aria-label 仍是 label', () => {
    const { button } = mount({ label: '复制', tooltip: '复制到剪贴板' });
    expect(button.getAttribute('aria-label')).toBe('复制');
    fireEvent.mouseEnter(button);
    advance(400);
    expect((tooltipEl()!.textContent || '').trim()).toBe('复制到剪贴板');
  });

  it('边长 28 / 32 为字面量（读 CSS 文本）', () => {
    const css = readFileSync(join(process.cwd(), 'src/components/IconButton.css'), 'utf8');
    expect(css).toMatch(/\.tt-icon-btn--sm\s*\{[^}]*width:\s*28px/);
    expect(css).toMatch(/\.tt-icon-btn--md\s*\{[^}]*width:\s*32px/);
  });
});
