// 菜单：由触发按钮（复用 Button 样式，Button 没有 forwardRef，用 id 找回节点）开关；打开后焦点到第一项，
// 方向键移动并循环、Home/End 到首尾、Enter 选中并还焦点、Esc 关闭并还焦点且不选中、Tab 关闭焦点照常移走；
// 在菜单与触发按钮之外按下鼠标关闭。面板原地绝对定位，role=menu / role=menuitem，用真实焦点移动。
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Button } from './Button';
import './Menu.css';

export interface MenuItem {
  id: string;
  label: ReactNode;
}

export interface MenuProps {
  /** 触发按钮文字。 */
  label: ReactNode;
  /** 菜单项。 */
  items: MenuItem[];
  /** 选中回调，传入该项 id。 */
  onSelect: (id: string) => void;
}

export function Menu({ label, items, onSelect }: MenuProps) {
  const [open, setOpen] = useState(false);
  const triggerId = useId();
  const menuId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const focusTrigger = useCallback(() => {
    const trigger = document.getElementById(triggerId);
    if (trigger instanceof HTMLElement) trigger.focus();
  }, [triggerId]);

  // 打开后焦点到第一项。
  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
    first?.focus();
  }, [open]);

  // 在菜单与触发按钮之外按下鼠标：关闭，不强行还焦点。
  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, [open]);

  const toggle = () => {
    if (open) {
      setOpen(false);
      focusTrigger();
    } else {
      setOpen(true);
    }
  };

  const selectItem = (index: number) => {
    const item = items[index];
    if (item) onSelect(item.id);
    setOpen(false);
    focusTrigger();
  };

  const onMenuKeyDown = (e: KeyboardEvent) => {
    const els = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    const current = els.indexOf(document.activeElement as HTMLElement);
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        els[(current < 0 ? 0 : (current + 1) % els.length)]?.focus();
        break;
      case 'ArrowUp':
        e.preventDefault();
        els[(current <= 0 ? els.length - 1 : current - 1)]?.focus();
        break;
      case 'Home':
        e.preventDefault();
        els[0]?.focus();
        break;
      case 'End':
        e.preventDefault();
        els[els.length - 1]?.focus();
        break;
      case 'Enter':
        e.preventDefault();
        selectItem(current < 0 ? 0 : current);
        break;
      case 'Escape':
        e.stopPropagation();
        setOpen(false);
        focusTrigger();
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        break;
    }
  };

  return (
    <span className="tt-menu-wrap" ref={wrapRef}>
      <Button
        id={triggerId}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={toggle}
      >
        {label}
      </Button>
      {open && (
        <div
          className="tt-menu tt-fc"
          role="menu"
          id={menuId}
          aria-labelledby={triggerId}
          ref={menuRef}
          onKeyDown={onMenuKeyDown}
        >
          {items.map((item, index) => (
            <div
              key={item.id}
              className="tt-menu__item"
              role="menuitem"
              tabIndex={-1}
              onClick={() => selectItem(index)}
            >
              {item.label}
            </div>
          ))}
        </div>
      )}
    </span>
  );
}
