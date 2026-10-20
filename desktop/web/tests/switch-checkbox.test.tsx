import * as React from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Switch } from '../src/components/Switch';
import { Checkbox } from '../src/components/Checkbox';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function Shell({ Comp, initial, disabled, onChange }: any) {
  const [on, setOn] = React.useState(!!initial);
  return (
    <Comp label="自动刷新" checked={on} disabled={!!disabled}
      onChange={(next: any) => { onChange(next); setOn(typeof next === 'boolean' ? next : !on); }} />
  );
}
function mount(Comp: any, role: string, props: any = {}) {
  const onChange = vi.fn();
  const r = render(<Shell Comp={Comp} onChange={onChange} {...props} />);
  const el = r.getByRole(role, { name: /自动刷新/ }) as HTMLElement;
  return { ...r, el, onChange };
}
const key = (k: string, init: any = {}, target: Element | null = document.activeElement) =>
  fireEvent.keyDown(target as Element, { key: k, ...init });

describe.each([
  ['开关', 'switch', Switch],
  ['复选框', 'checkbox', Checkbox],
])('%s', (_label, role, Comp) => {
  it('span、aria-checked=false、tabIndex=0、名称来自文字、无内嵌 button/input', () => {
    const { el } = mount(Comp, role);
    expect(el.tagName).toBe('SPAN');
    expect(el.getAttribute('aria-checked')).toBe('false');
    expect(el.getAttribute('tabindex')).toBe('0');
    expect(el.querySelector('button, input')).toBeNull();
    expect((el.textContent || '').trim()).toBe('自动刷新');
  });

  it('checked 为真时 aria-checked=true', () => {
    const { el } = mount(Comp, role, { initial: true });
    expect(el.getAttribute('aria-checked')).toBe('true');
  });

  it('空格切换一次、preventDefault、repeat 不切换', () => {
    const { el, onChange } = mount(Comp, role);
    act(() => { el.focus(); });
    expect(key(' ')).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(el.getAttribute('aria-checked')).toBe('true');
    key(' ');
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(el.getAttribute('aria-checked')).toBe('false');
    key(' ', { repeat: true });
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it('点击整个控件切换', () => {
    const { el, onChange } = mount(Comp, role);
    fireEvent.click(el);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(el.getAttribute('aria-checked')).toBe('true');
    for (const child of Array.from(el.children)) fireEvent.click(child);
    expect(onChange).toHaveBeenCalledTimes(1 + el.children.length);
  });

  it('禁用时 aria-disabled=true、不可聚焦、不切换', () => {
    const { el, onChange } = mount(Comp, role, { disabled: true });
    expect(el.getAttribute('aria-disabled')).toBe('true');
    act(() => { el.focus(); });
    expect(document.activeElement).not.toBe(el);
    fireEvent.click(el);
    key(' ', {}, el);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('复选框只认空格，不认 Enter', () => {
    const { el, onChange } = mount(Comp, role);
    act(() => { el.focus(); });
    key('Enter', {}, el);
    if (role === 'checkbox') {
      expect(onChange).not.toHaveBeenCalled();
    }
  });
});
