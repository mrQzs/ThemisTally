// 表格（组件板 :411–418、任务页 :367–391、UI 文档 7.9、handoff :142）：滚动容器里一个原生 table，表头吸顶、单元格不换行。
// 行 roving tabindex（起点是选中行，没有就第一行）；上下移动不循环、Home/End 到首尾；Enter 或点击行调一次 onRowOpen(key)。
// 表格与容器本身不进 Tab 序列，单元格里不放可聚焦元素。rowHeight 40/44/52 反映在 table 的 data-row-height 上。
import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import './Table.css';

export interface TableColumn<Row> {
  key: keyof Row & string;
  header: string;
  /** 数字列：右对齐、带 tt-num。 */
  numeric?: boolean;
  /** 等宽列。 */
  mono?: boolean;
}

export interface TableProps<Row> {
  columns: readonly TableColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  rowHeight?: 40 | 44 | 52;
  onRowOpen?: (key: string) => void;
  selectedKey?: string;
  /** 加在滚动容器上的类名（调用方用它限高；不用内联 style）。 */
  className?: string;
  'aria-label': string;
}

export function Table<Row>({
  columns,
  rows,
  rowKey,
  rowHeight = 40,
  onRowOpen,
  selectedKey,
  className,
  'aria-label': ariaLabel,
}: TableProps<Row>) {
  const tableRef = useRef<HTMLTableElement>(null);
  const selectedIndex = selectedKey != null ? rows.findIndex((r) => rowKey(r) === selectedKey) : -1;
  const [active, setActive] = useState(selectedIndex >= 0 ? selectedIndex : 0);
  const [prevSelected, setPrevSelected] = useState(selectedKey);
  if (selectedKey !== prevSelected) {
    setPrevSelected(selectedKey);
    setActive(selectedIndex >= 0 ? selectedIndex : 0);
  }

  const rowEls = () => Array.from(tableRef.current?.querySelectorAll<HTMLElement>('tbody tr') ?? []);
  const moveTo = (i: number) => {
    setActive(i);
    rowEls()[i]?.focus();
  };
  const onRowKeyDown = (e: KeyboardEvent, index: number) => {
    const n = rows.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (index < n - 1) moveTo(index + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (index > 0) moveTo(index - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      moveTo(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      moveTo(n - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      onRowOpen?.(rowKey(rows[index]));
    }
  };

  const wrapClass = className ? `tt-table-wrap ${className}` : 'tt-table-wrap';
  return (
    <div className={wrapClass}>
      <table className="tt-table" data-row-height={rowHeight} aria-label={ariaLabel} ref={tableRef}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col">{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const key = rowKey(row);
            const isSel = selectedKey != null && key === selectedKey;
            const cellCls = (c: TableColumn<Row>) =>
              [c.numeric ? 'tt-num' : '', c.mono ? 'tt-table__mono' : ''].filter(Boolean).join(' ');
            return (
              <tr
                key={key}
                tabIndex={i === active ? 0 : -1}
                data-selected={isSel ? '' : undefined}
                onFocus={() => setActive(i)}
                onClick={() => {
                  setActive(i);
                  onRowOpen?.(key);
                }}
                onKeyDown={(e) => onRowKeyDown(e, i)}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cellCls(col) || undefined}>
                    {row[col.key] as unknown as ReactNode}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
