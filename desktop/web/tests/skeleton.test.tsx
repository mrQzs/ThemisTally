import * as React from 'react';
import { cleanup, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Skeleton } from '../src/components/Skeleton';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function advance(ms: number) { act(() => { vi.advanceTimersByTime(ms); }); }
function bars(root: ParentNode) { return Array.from(root.querySelectorAll('.tt-skel')); }

describe('骨架屏', () => {
  it('299ms 什么都不渲染、300ms 出现 4 条 tt-skel（aria-hidden）与 aria-busy 容器', () => {
    const { container } = render(<Skeleton />);
    expect(container.innerHTML).toBe('');
    advance(299);
    expect(container.innerHTML).toBe('');
    advance(1);
    const list = bars(container);
    expect(list.length).toBe(4);
    expect(list.every((el) => el.getAttribute('aria-hidden') === 'true')).toBe(true);
    const busy = container.querySelector('[aria-busy="true"]');
    expect(busy).not.toBeNull();
    expect(list.every((el) => busy!.contains(el))).toBe(true);
  });

  it('300ms 前卸载清计时器、什么都不出现；StrictMode 计时幂等；重新挂载重新计时', () => {
    const base = vi.getTimerCount();
    const r = render(<Skeleton />);
    advance(200);
    r.unmount();
    expect(vi.getTimerCount()).toBe(base);
    advance(1000);
    expect(document.querySelector('.tt-skel')).toBeNull();

    const s = render(<React.StrictMode><Skeleton /></React.StrictMode>);
    advance(299);
    expect(s.container.innerHTML).toBe('');
    advance(1);
    expect(bars(s.container).length).toBe(4);
    s.unmount();

    const again = render(<Skeleton />);
    advance(299);
    expect(again.container.innerHTML).toBe('');
    advance(1);
    expect(bars(again.container).length).toBe(4);
  });
});
