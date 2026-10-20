import * as React from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Tabs } from '../src/components/Tabs';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const ITEMS = [
  { id: 't1', label: '概览' },
  { id: 't2', label: '日志' },
  { id: 't3', label: '设置' },
];
function Shell({ initial, onChange }: { initial: string; onChange: (id: string) => void }) {
  const [value, setValue] = React.useState(initial);
  return (
    <Tabs aria-label="页签" items={ITEMS} value={value} onChange={(id) => { onChange(id); setValue(id); }}>
      <p data-panel={value}>面板 {value}</p>
    </Tabs>
  );
}
function mount(initial = 't1') {
  const onChange = vi.fn();
  const r = render(<Shell initial={initial} onChange={onChange} />);
  const list = r.container.querySelector('[role="tablist"]') as HTMLElement;
  const tabs = () => Array.from(list.querySelectorAll<HTMLElement>('[role="tab"]'));
  const panel = () => r.container.querySelector('[role="tabpanel"]') as HTMLElement;
  return { ...r, list, tabs, panel, onChange };
}
const key = (k: string) => fireEvent.keyDown(document.activeElement as Element, { key: k });

describe('页签', () => {
  it('tablist、tab、恰一个 tabIndex=0 与 aria-selected=true；面板关联当前页签', () => {
    const { list, tabs, panel, container } = mount('t2');
    expect(list.getAttribute('aria-label')).toBe('页签');
    const all = tabs();
    expect(all.map((el) => el.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false']);
    expect(all.map((el) => el.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    expect(container.querySelectorAll('[role="tabpanel"]').length).toBe(1);
    expect(panel().getAttribute('aria-labelledby')).toBe(all[1].id);
    expect(all[1].getAttribute('aria-controls')).toBe(panel().id);
  });

  it('左右循环切换并移焦点、Home/End 到首尾、preventDefault', () => {
    const { tabs, panel, onChange } = mount('t1');
    act(() => { tabs()[0].focus(); });
    expect(key('ArrowRight')).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('t2');
    expect(document.activeElement).toBe(tabs()[1]);
    expect((panel().textContent || '')).toContain('t2');
    act(() => { tabs()[1].focus(); });
    expect(key('End')).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('t3');
    expect(key('Home')).toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('t1');
    expect(document.activeElement).toBe(tabs()[0]);
  });

  it('点击页签选中', () => {
    const { tabs, onChange } = mount('t1');
    fireEvent.click(tabs()[2]);
    expect(onChange).toHaveBeenCalledWith('t3');
    expect(tabs().map((el) => el.getAttribute('aria-selected'))).toEqual(['false', 'false', 'true']);
  });
});
