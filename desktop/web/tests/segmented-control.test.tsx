import * as React from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SegmentedControl } from '../src/components/SegmentedControl';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const OPTIONS = [
  { value: 'a', label: '甲' },
  { value: 'b', label: '乙' },
  { value: 'c', label: '丙' },
];
function Shell({ initial, onChange }: { initial: string; onChange: (v: string) => void }) {
  const [value, setValue] = React.useState(initial);
  return (
    <SegmentedControl aria-label="分段" options={OPTIONS} value={value}
      onChange={(next) => { onChange(next); setValue(next); }} />
  );
}
function mount(initial = 'a') {
  const onChange = vi.fn();
  const r = render(<Shell initial={initial} onChange={onChange} />);
  const group = r.container.querySelector('[role="radiogroup"]') as HTMLElement;
  const radios = () => Array.from(group.querySelectorAll<HTMLElement>('[role="radio"]'));
  return { ...r, group, radios, onChange };
}
const key = (k: string) => fireEvent.keyDown(document.activeElement as Element, { key: k });

describe('分段选择', () => {
  it('radiogroup、段 role=radio、恰一个 tabIndex=0、aria-checked 只选中段为 true', () => {
    const { group, radios } = mount('b');
    expect(group.getAttribute('aria-label')).toBe('分段');
    const list = radios();
    expect(list.map((el) => el.tagName)).toEqual(['BUTTON', 'BUTTON', 'BUTTON']);
    expect(list.map((el) => el.getAttribute('type'))).toEqual(['button', 'button', 'button']);
    expect(list.map((el) => el.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    expect(list.map((el) => el.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
  });

  it('ArrowRight / ArrowLeft 选中相邻段并移焦点、到头循环、preventDefault', () => {
    const { radios, onChange } = mount('a');
    act(() => { radios()[0].focus(); });
    expect(key('ArrowRight')).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('b');
    expect(document.activeElement).toBe(radios()[1]);
    expect(radios().map((el) => el.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    act(() => { radios()[2].focus(); });
    fireEvent.click(radios()[2]);
    expect(key('ArrowRight')).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('a');
    expect(document.activeElement).toBe(radios()[0]);
  });

  it('只处理左右键；点击选中', () => {
    const { radios, onChange } = mount('b');
    act(() => { radios()[1].focus(); });
    for (const k of ['ArrowUp', 'ArrowDown', 'Home', 'End']) key(k);
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(radios()[2]);
    expect(onChange).toHaveBeenCalledWith('c');
    expect(radios().map((el) => el.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true']);
  });
});
