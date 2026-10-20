import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SegmentedControl } from '../src/components/SegmentedControl';
import { Tabs } from '../src/components/Tabs';
import { Switch } from '../src/components/Switch';
import { Checkbox } from '../src/components/Checkbox';
import { ConnectionPill } from '../src/components/ConnectionPill';
import { Table } from '../src/components/Table';

afterEach(cleanup);

const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const focusOn = (el: HTMLElement) => { act(() => { el.focus(); }); };

const COLUMNS = [
  { key: 'name', header: '名称' },
  { key: 'n', header: '数量', numeric: true },
  { key: 'id', header: '编号', mono: true },
];
const mk = (keys: string[]) => keys.map((k) => ({ id: k, name: '行' + k, n: 1 }));

function mountTable(keys: string[], props: Record<string, unknown> = {}) {
  const onRowOpen = vi.fn();
  let cur = { ...props };
  const el = (ks: string[]) => (
    <Table aria-label="表" columns={COLUMNS} rows={mk(ks)} rowKey={(r: any) => r.id} onRowOpen={onRowOpen} {...cur} />
  );
  const r = render(el(keys));
  const trs = () => Array.from(r.container.querySelectorAll('tbody tr')) as HTMLElement[];
  const zero = () => trs().filter((t) => t.getAttribute('tabindex') === '0').map((t) => textOf(t.children[2]));
  const rowFor = (k: string) => trs().find((t) => textOf(t.children[2]) === k) as HTMLElement;
  const set = (ks: string[], patch: Record<string, unknown> = {}) => {
    cur = { ...cur, ...patch };
    r.rerender(el(ks));
  };
  return { ...r, trs, zero, rowFor, set, onRowOpen };
}

describe('S2：数字列的表头也带 tt-num', () => {
  it('数字列的 th 带 tt-num，其余列的 th 不带；td 的规则照旧', () => {
    const { container } = mountTable(['a', 'b']);
    const ths = Array.from(container.querySelectorAll('thead th'));
    expect(ths.map((t) => t.classList.contains('tt-num'))).toEqual([false, true, false]);
    expect(ths.map((t) => t.getAttribute('scope'))).toEqual(['col', 'col', 'col']);
    for (const tr of Array.from(container.querySelectorAll('tbody tr'))) {
      expect(Array.from(tr.children).map((td) => td.classList.contains('tt-num'))).toEqual([false, true, false]);
    }
  });
});

describe('S1：当前行按 key 记', () => {
  it('缺省第一行；有 selectedKey 时是选中行；selectedKey 不在 rows 里时回到第一行；恰一行 tabIndex=0', () => {
    expect(mountTable(['a', 'b', 'c']).zero()).toEqual(['a']);
    const b = mountTable(['a', 'b', 'c'], { selectedKey: 'c' });
    expect(b.zero()).toEqual(['c']);
    expect(b.trs().map((r) => r.hasAttribute('data-selected'))).toEqual([false, false, true]);
    b.unmount();
    expect(mountTable(['a', 'b'], { selectedKey: 'zz' }).zero()).toEqual(['a']);
  });

  it('rows 变少：当前行没了，回到选中行；没有选中行回到第一行', () => {
    const a = mountTable(['a', 'b', 'c', 'd']);
    focusOn(a.rowFor('d'));
    expect(a.zero()).toEqual(['d']);
    a.set(['a', 'b']);
    expect(a.zero()).toEqual(['a']);
    a.unmount();
    const b = mountTable(['a', 'b', 'c', 'd'], { selectedKey: 'b' });
    focusOn(b.rowFor('d'));
    expect(b.zero()).toEqual(['d']);
    b.set(['a', 'b']);
    expect(b.zero()).toEqual(['b']);
  });

  it('rows 晚于 selectedKey 到达：先是空表，rows 到了之后选中行是当前行', () => {
    const { trs, zero, set, container } = mountTable([], { selectedKey: 'c' });
    expect(trs().length).toBe(0);
    expect(zero()).toEqual([]);
    expect(container.querySelectorAll('thead th').length).toBe(3);
    set(['a', 'b', 'c']);
    expect(zero()).toEqual(['c']);
    expect(trs().length).toBe(3);
  });

  it('排序或插入：当前行跟着 key 走，不跟下标走', () => {
    const { zero, set, rowFor } = mountTable(['a', 'b', 'c']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['c', 'b', 'a']);
    expect(zero()).toEqual(['c']);
    set(['x', 'c', 'b', 'a']);
    expect(zero()).toEqual(['c']);
    set(['x', 'b', 'a']);
    expect(zero()).toEqual(['x']);
  });

  it('selectedKey 变化时清掉当前 key；变成 undefined 回到第一行', () => {
    const { zero, set, rowFor } = mountTable(['a', 'b', 'c']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['a', 'b', 'c'], { selectedKey: 'b' });
    expect(zero()).toEqual(['b']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['a', 'b', 'c'], { selectedKey: undefined });
    expect(zero()).toEqual(['a']);
  });

  it('键盘按 key 走：重新排序之后 ArrowDown 去新顺序里的下一行', () => {
    const { zero, set, rowFor } = mountTable(['a', 'b', 'c']);
    focusOn(rowFor('b'));
    set(['c', 'b', 'a']);
    expect(zero()).toEqual(['b']);
    expect(fireEvent.keyDown(rowFor('b'), { key: 'ArrowDown' })).toBe(false);
    expect(zero()).toEqual(['a']);
    expect(document.activeElement).toBe(rowFor('a'));
  });

  it('点击行：调 onRowOpen(key)，被点的行成为当前行；Enter 同样', () => {
    const { zero, rowFor, onRowOpen } = mountTable(['a', 'b', 'c']);
    fireEvent.click(rowFor('c'));
    expect(onRowOpen).toHaveBeenCalledTimes(1);
    expect(onRowOpen).toHaveBeenCalledWith('c');
    expect(zero()).toEqual(['c']);
    focusOn(rowFor('b'));
    fireEvent.keyDown(rowFor('b'), { key: 'Enter' });
    expect(onRowOpen).toHaveBeenCalledTimes(2);
    expect(onRowOpen).toHaveBeenLastCalledWith('b');
  });

  it('rows 为空时没有行，也不抛错', () => {
    const { trs, zero } = mountTable([]);
    expect(trs().length).toBe(0);
    expect(zero()).toEqual([]);
  });
});

describe('S5：value 无效时第一项可 Tab 到', () => {
  it('SegmentedControl：value 不在选项里 → 恰一个 tabIndex=0 且是第一项，aria-checked 全为 false', () => {
    const options = [{ value: 'a', label: '甲' }, { value: 'b', label: '乙' }, { value: 'c', label: '丙' }];
    const mkSeg = (value: string) =>
      render(<SegmentedControl aria-label="分段" options={options} value={value} onChange={() => {}} />);
    const a = mkSeg('zz');
    const radios = () => Array.from(document.querySelectorAll('[role="radio"]')) as HTMLElement[];
    expect(radios().map((r) => r.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
    expect(radios().map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'false', 'false']);
    a.unmount();
    const b = mkSeg('b');
    expect(radios().map((r) => r.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    expect(radios().map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    b.unmount();
    const empty = render(<SegmentedControl aria-label="空" options={[]} value="" onChange={() => {}} />);
    expect(empty.container.querySelectorAll('[role="radio"]').length).toBe(0);
  });

  it('Tabs：value 不在页签里 → 恰一个 tabIndex=0 且是第一个页签，aria-selected 全为 false', () => {
    const items = [{ id: 't1', label: '一' }, { id: 't2', label: '二' }, { id: 't3', label: '三' }];
    const mkTabs = (value: string) =>
      render(<Tabs aria-label="页签" items={items} value={value} onChange={() => {}}>内容</Tabs>);
    const a = mkTabs('nope');
    const tabs = () => Array.from(document.querySelectorAll('[role="tab"]')) as HTMLElement[];
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
    expect(tabs().map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'false', 'false']);
    a.unmount();
    const b = mkTabs('t2');
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    expect(tabs().map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false']);
  });
});

describe('缺口 1：每个页签的 aria-controls 都指向同一个面板', () => {
  it('value 有效与无效两种情形下都等于面板的 id，面板存在', () => {
    const items = [{ id: 't1', label: '一' }, { id: 't2', label: '二' }, { id: 't3', label: '三' }];
    for (const value of ['t1', 't3', 'nope']) {
      const { unmount } = render(<Tabs aria-label="页签" items={items} value={value} onChange={() => {}}>内容</Tabs>);
      const panel = document.querySelector('[role="tabpanel"]') as HTMLElement;
      expect(panel, value).not.toBeNull();
      expect(panel.id).not.toBe('');
      const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
      expect(tabs.length).toBe(3);
      for (const t of tabs) expect(t.getAttribute('aria-controls'), value).toBe(panel.id);
      expect(document.getElementById(panel.getAttribute('aria-labelledby') || '')).not.toBeNull();
      unmount();
    }
  });
});

describe('缺口 2：空格带 repeat', () => {
  it('Switch：repeat 的空格照样 preventDefault 但不切换；普通空格切换一次；别的键不处理', () => {
    const onChange = vi.fn();
    const { container } = render(<Switch checked={false} onChange={onChange} label="开关" />);
    const el = container.querySelector('[role="switch"]') as HTMLElement;
    focusOn(el);
    expect(fireEvent.keyDown(el, { key: ' ', repeat: true })).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
    expect(fireEvent.keyDown(el, { key: ' ' })).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(true);
    expect(fireEvent.keyDown(el, { key: 'Enter' })).toBe(true);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('Checkbox：同上', () => {
    const onChange = vi.fn();
    const { container } = render(<Checkbox checked={true} onChange={onChange} label="复选" />);
    const el = container.querySelector('[role="checkbox"]') as HTMLElement;
    focusOn(el);
    expect(fireEvent.keyDown(el, { key: ' ', repeat: true })).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
    expect(fireEvent.keyDown(el, { key: ' ' })).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(false);
    expect(fireEvent.keyDown(el, { key: 'Enter' })).toBe(true);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe('缺口 3：关闭态胶囊按 Esc 放过', () => {
  it('关着时 Esc 既不 stopPropagation 也不 preventDefault；打开时关闭、不往外传、焦点留在胶囊', () => {
    const outer = vi.fn();
    const doc = vi.fn();
    document.addEventListener('keydown', doc);
    try {
      const { container } = render(
        <div onKeyDown={outer}>
          <ConnectionPill state="connected" pid={1} startedAt="2026-10-20" stream="正常" />
        </div>,
      );
      const btn = container.querySelector('button.tt-pill') as HTMLElement;
      focusOn(btn);
      expect(btn.getAttribute('aria-expanded')).toBe('false');
      expect(fireEvent.keyDown(btn, { key: 'Escape' })).toBe(true);
      expect(outer).toHaveBeenCalledTimes(1);
      expect(doc).toHaveBeenCalledTimes(1);
      fireEvent.click(btn);
      expect(btn.getAttribute('aria-expanded')).toBe('true');
      fireEvent.keyDown(btn, { key: 'Escape' });
      expect(btn.getAttribute('aria-expanded')).toBe('false');
      expect(outer).toHaveBeenCalledTimes(1);
      expect(doc).toHaveBeenCalledTimes(1);
      expect(document.activeElement).toBe(btn);
    } finally {
      document.removeEventListener('keydown', doc);
    }
  });
});
