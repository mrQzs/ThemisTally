import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Menu } from '../src/components/Menu';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const ITEMS = [{ id: 'a', label: '甲' }, { id: 'b', label: '乙' }, { id: 'c', label: '丙' }];
function menuEl() { return document.querySelector('[role="menu"]'); }
function itemEls() { const m = menuEl(); return m ? Array.from(m.querySelectorAll('[role="menuitem"]')) : []; }
function key(k: string, init: Record<string, unknown> = {}) {
  return fireEvent.keyDown(document.activeElement as Element, { key: k, ...init });
}
function mount() {
  const onSelect = vi.fn();
  const r = render(<Menu label="更多操作" items={ITEMS} onSelect={onSelect} />);
  const trigger = r.container.querySelector('button[aria-haspopup="menu"]') as HTMLButtonElement;
  return { ...r, trigger, onSelect };
}
function open(trigger: HTMLElement) {
  act(() => { trigger.focus(); });
  fireEvent.click(trigger);
}

describe('Menu', () => {
  it('点触发按钮开合，aria-expanded / aria-controls / aria-labelledby 正确，焦点在第一项', () => {
    const { trigger } = mount();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(menuEl()).toBeNull();
    open(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    const menu = menuEl()!;
    expect(trigger.getAttribute('aria-controls')).toBe(menu.id);
    expect(menu.getAttribute('aria-labelledby')).toBe(trigger.id);
    expect(menu.classList.contains('tt-fc')).toBe(true);
    expect(itemEls().map((el) => (el.textContent || '').trim())).toEqual(['甲', '乙', '丙']);
    for (const el of itemEls()) expect(el.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(itemEls()[0]);
    fireEvent.click(trigger);
    expect(menuEl()).toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('方向键移动并循环、Home/End 到首尾、Enter 选中并还焦点', () => {
    const { trigger, onSelect } = mount();
    open(trigger);
    const items = itemEls();
    key('ArrowDown'); expect(document.activeElement).toBe(items[1]);
    key('ArrowDown'); expect(document.activeElement).toBe(items[2]);
    key('ArrowDown'); expect(document.activeElement).toBe(items[0]);
    key('ArrowUp'); expect(document.activeElement).toBe(items[2]);
    key('End'); expect(document.activeElement).toBe(items[2]);
    key('Home'); expect(document.activeElement).toBe(items[0]);
    key('ArrowDown'); key('Enter');
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('b');
    expect(menuEl()).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('Esc 关闭、还焦点、不选中', () => {
    const { trigger, onSelect } = mount();
    open(trigger);
    key('Escape');
    expect(menuEl()).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('菜单外 mousedown 关闭，菜单内 mousedown 不关', () => {
    const { trigger } = mount();
    open(trigger);
    fireEvent.mouseDown(itemEls()[1]);
    expect(menuEl()).not.toBeNull();
    fireEvent.mouseDown(document.body);
    expect(menuEl()).toBeNull();
  });
});
