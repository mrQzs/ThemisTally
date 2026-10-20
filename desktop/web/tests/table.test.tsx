import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Table } from '../src/components/Table';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const COLUMNS = [
  { key: 'name', header: '任务' },
  { key: 'dur', header: '用时', numeric: true },
  { key: 'tok', header: 'token', numeric: true },
  { key: 'id', header: '编号', mono: true },
];
const ROWS = [
  { id: 'r1', name: '甲任务', dur: '12.5', tok: '1200' },
  { id: 'r2', name: '乙任务', dur: '8.0', tok: '640' },
  { id: 'r3', name: '丙任务', dur: '31.2', tok: '5120' },
  { id: 'r4', name: '丁任务', dur: '4.4', tok: '300' },
  { id: 'r5', name: '戊任务', dur: '19.9', tok: '2048' },
];
function mount(props: any = {}) {
  const onRowOpen = vi.fn();
  const r = render(
    <Table aria-label="任务表" className="gate-limit" columns={COLUMNS} rows={ROWS}
      rowKey={(row: any) => row.id} onRowOpen={onRowOpen} {...props} />,
  );
  const table = r.container.querySelector('table') as HTMLTableElement;
  const rows = () => Array.from(table.querySelectorAll<HTMLElement>('tbody tr'));
  return { ...r, table, rows, onRowOpen };
}
const zeroIdx = (rows: HTMLElement[]) => rows.map((r, i) => (r.getAttribute('tabindex') === '0' ? i : -1)).filter((i) => i >= 0);
const key = (k: string) => fireEvent.keyDown(document.activeElement as Element, { key: k });

describe('表格', () => {
  it('滚动容器带 className 并包着 table；th scope=col；缺省 data-row-height=40；数字列带 tt-num', () => {
    const { table, rows } = mount();
    expect(table.closest('div.gate-limit')).not.toBeNull();
    const ths = Array.from(table.querySelectorAll('th'));
    expect(ths.map((th) => (th.textContent || '').trim())).toEqual(['任务', '用时', 'token', '编号']);
    expect(ths.every((th) => th.getAttribute('scope') === 'col')).toBe(true);
    expect(table.getAttribute('data-row-height')).toBe('40');
    expect(rows().length).toBe(5);
    const cells = Array.from(rows()[0].children);
    expect(cells[1].classList.contains('tt-num')).toBe(true);
    expect(cells[2].classList.contains('tt-num')).toBe(true);
    expect(cells[0].classList.contains('tt-num')).toBe(false);
    expect((cells[1].textContent || '').trim()).toBe('12.5');
  });

  it('rowHeight 44/52 反映在 data-row-height；恰一行 tabIndex=0，selectedKey 只它带 data-selected', () => {
    expect(mount({ rowHeight: 44 }).table.getAttribute('data-row-height')).toBe('44');
    expect(mount({ rowHeight: 52 }).table.getAttribute('data-row-height')).toBe('52');
    const a = mount();
    expect(zeroIdx(a.rows())).toEqual([0]);
    const b = mount({ selectedKey: 'r3' });
    expect(zeroIdx(b.rows())).toEqual([2]);
    expect(b.rows().map((r) => r.hasAttribute('data-selected'))).toEqual([false, false, true, false, false]);
  });

  it('上下移动不循环、Home/End 到首尾、preventDefault；Enter 调一次 onRowOpen(key)；点击行同', () => {
    const { rows, onRowOpen } = mount();
    act(() => { rows()[0].focus(); });
    expect(key('ArrowDown')).toBe(false);
    expect(document.activeElement).toBe(rows()[1]);
    act(() => { rows()[0].focus(); });
    key('ArrowUp');
    expect(document.activeElement).toBe(rows()[0]);
    expect(key('End')).toBe(false);
    expect(document.activeElement).toBe(rows()[4]);
    key('ArrowDown');
    expect(document.activeElement).toBe(rows()[4]);
    expect(key('Home')).toBe(false);
    expect(document.activeElement).toBe(rows()[0]);
    key('ArrowDown');
    key('ArrowDown');
    expect(key('Enter')).toBe(false);
    expect(onRowOpen).toHaveBeenCalledTimes(1);
    expect(onRowOpen).toHaveBeenCalledWith('r3');
    fireEvent.click(rows()[3]);
    expect(onRowOpen).toHaveBeenLastCalledWith('r4');
    expect(zeroIdx(rows())).toEqual([3]);
  });

  it('表格与容器不进 Tab 序列，单元格里没有可聚焦元素', () => {
    const { table } = mount();
    const box = table.closest('div.gate-limit') as HTMLElement;
    expect(table.getAttribute('tabindex')).not.toBe('0');
    expect(box.getAttribute('tabindex')).not.toBe('0');
    expect(table.querySelectorAll('td a, td button, td input, td [tabindex], th [tabindex]').length).toBe(0);
  });
});
