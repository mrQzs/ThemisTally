import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Toast } from '../src/components/Toast';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function advance(ms: number) { act(() => { vi.advanceTimersByTime(ms); }); }
function tipEl(): HTMLElement | null { return document.querySelector('[role="tooltip"]'); }
function closeBtn(): HTMLButtonElement {
  return document.querySelector('button[aria-label="关闭提示"]') as HTMLButtonElement;
}
function mount(onClose: () => void = vi.fn()) {
  const r = render(<Toast open onClose={onClose}>已复制</Toast>);
  return { ...r, onClose };
}

describe('轻提示关闭钮的工具提示（T005 7.2）', () => {
  it('悬停 399ms 没有、400ms 出现「关闭提示」，aria-describedby 指向它，移开立即消失', () => {
    mount();
    const btn = closeBtn();
    expect(btn).not.toBeNull();
    expect(tipEl()).toBeNull();
    fireEvent.mouseEnter(btn);
    advance(399);
    expect(tipEl(), '399ms 时还不该出现').toBeNull();
    advance(1);
    const tip = tipEl();
    expect(tip, '400ms 时应出现 role=tooltip').not.toBeNull();
    expect((tip!.textContent || '').trim()).toBe('关闭提示');
    expect(btn.getAttribute('aria-describedby')).toBe(tip!.id);
    fireEvent.mouseLeave(btn);
    expect(tipEl(), '移开应立即消失').toBeNull();
    expect(btn.hasAttribute('aria-describedby')).toBe(false);
  });

  it('聚焦同样 400ms 出现，失焦立即消失；点一下立即调一次 onClose；5000ms 自动关闭照旧', () => {
    const { onClose } = mount();
    const btn = closeBtn();
    fireEvent.focus(btn);
    advance(399);
    expect(tipEl()).toBeNull();
    advance(1);
    expect(tipEl()).not.toBeNull();
    fireEvent.blur(btn);
    expect(tipEl()).toBeNull();
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('5000ms 自动关闭：4999ms 没调、5000ms 调一次', () => {
    const { onClose } = mount();
    advance(4999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
