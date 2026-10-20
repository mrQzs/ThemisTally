// 页签（组件板 :381–385、UI 文档 7.6）：role=tablist，页签 button role=tab aria-selected；roving tabindex（只当前页签可 Tab 到）。
// 左右方向键循环切换并移焦点、Home/End 到首尾，选中跟着焦点走（自动激活）；点击选中。当前页签 aria-controls 指向面板，
// 面板 role=tabpanel、aria-labelledby 指向当前页签。受控：value + onChange(id)。
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import './Tabs.css';

export interface TabItem {
  id: string;
  label: string;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  'aria-label': string;
  children?: ReactNode;
}

export function Tabs({ items, value, onChange, children, ...rest }: TabsProps) {
  const baseId = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const activeIndex = Math.max(0, items.findIndex((it) => it.id === value));
  const current = items[activeIndex];
  const panelId = `${baseId}-panel`;
  const currentTabId = `${baseId}-tab-${current ? current.id : 'none'}`;

  const focusAndSelect = (i: number) => {
    const it = items[i];
    if (it) onChange(it.id);
    const tabs = listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]');
    tabs?.[i]?.focus();
  };
  const onKeyDown = (e: KeyboardEvent) => {
    const n = items.length;
    if (n === 0) return;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      focusAndSelect((activeIndex + 1) % n);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      focusAndSelect((activeIndex - 1 + n) % n);
    } else if (e.key === 'Home') {
      e.preventDefault();
      focusAndSelect(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      focusAndSelect(n - 1);
    }
  };

  return (
    <div className="tt-tabs">
      <div ref={listRef} className="tt-tabs__list" role="tablist" onKeyDown={onKeyDown} {...rest}>
        {items.map((it) => {
          const selected = it.id === value;
          return (
            <button
              key={it.id}
              type="button"
              role="tab"
              id={`${baseId}-tab-${it.id}`}
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              className="tt-tabs__tab"
              onClick={() => onChange(it.id)}
            >
              {it.label}
            </button>
          );
        })}
      </div>
      <div className="tt-tabs__panel" role="tabpanel" id={panelId} aria-labelledby={currentTabId}>
        {children}
      </div>
    </div>
  );
}
