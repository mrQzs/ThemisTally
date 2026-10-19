import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Toast } from '../src/components/Toast';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function advance(ms: number) { act(() => { vi.advanceTimersByTime(ms); }); }
function statusEl() { return document.querySelector('[role="status"]') as HTMLElement; }
function textSpan() { return document.querySelector('[role="status"] .tt-toast__text') as HTMLElement; }

describe('Toast', () => {
  it('常驻 role=status、aria-live=polite 区域，空时没有按钮', () => {
    render(<Toast open={false} onClose={() => {}}>x</Toast>);
    const status = statusEl();
    expect(status).not.toBeNull();
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect((status.textContent || '').trim()).toBe('');
    expect(status.querySelector('button')).toBeNull();
  });

  it('可见时：图标 aria-hidden、文字、关闭钮「关闭提示」，挂到 body 下带 tt-fc', () => {
    const { container } = render(<Toast open onClose={() => {}}>已复制</Toast>);
    const status = statusEl();
    expect(status.textContent).toContain('已复制');
    expect(status.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');
    expect(status.querySelector('button[aria-label="关闭提示"]')).not.toBeNull();
    expect(container.contains(status)).toBe(false);
    expect(document.body.contains(status)).toBe(true);
    expect(status.matches('.tt-fc') || status.querySelector('.tt-fc') !== null).toBe(true);
  });

  it('4999ms 时 onClose 没调、5000ms 调一次、之后不重复', () => {
    const onClose = vi.fn();
    render(<Toast open onClose={onClose}>已复制</Toast>);
    advance(4999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    advance(20000);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('悬停暂停：第 3000ms 移入再推 10000ms 不调；移出后按剩余 2000ms 接着走', () => {
    const onClose = vi.fn();
    render(<Toast open onClose={onClose}>已复制</Toast>);
    advance(3000);
    fireEvent.mouseEnter(textSpan());
    advance(10000);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseLeave(textSpan());
    advance(1999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('关闭钮立即调 onClose', () => {
    const onClose = vi.fn();
    render(<Toast open onClose={onClose}>已复制</Toast>);
    fireEvent.click(statusEl().querySelector('button[aria-label="关闭提示"]') as Element);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('卸载清计时器', () => {
    const onClose = vi.fn();
    const { unmount } = render(<Toast open onClose={onClose}>已复制</Toast>);
    advance(1000);
    unmount();
    advance(10000);
    expect(onClose).not.toHaveBeenCalled();
  });
});
