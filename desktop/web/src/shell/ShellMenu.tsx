// ShellMenu（合同第 3 条）：触发钮由调用方渲染（children 为渲染函数，拿到 id、aria-haspopup、aria-expanded、
// aria-controls 与 onClick，透传到 IconButton / Button）。面板 role=menu 带 aria-label；项分单选项（menuitemradio 带
// aria-checked）、普通项（menuitem）与禁用项（加 aria-disabled）；分组标题是普通文字、分隔线 role=separator，都不可聚焦。
// 键盘与鼠标照 T004 的 Menu：打开后焦点到第一项，方向键循环、Home/End 到首尾、Enter 或点击选中并还焦点、
// Esc 关并还焦点且 stopPropagation、Tab 关闭、菜单与触发钮之外按下鼠标关闭；禁用项可聚焦但选不中、菜单也不关。
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { CheckIcon } from '../icons';
import './ShellMenu.css';

export type ShellMenuItem =
  | { kind: 'radio'; id: string; label: ReactNode; checked: boolean; disabled?: boolean }
  | { kind: 'item'; id: string; label: ReactNode; icon?: ReactNode; trailing?: ReactNode; disabled?: boolean }
  | { kind: 'group'; label: string }
  | { kind: 'separator' };

export interface ShellMenuTriggerProps {
  id: string;
  'aria-haspopup': 'menu';
  'aria-expanded': boolean;
  'aria-controls': string | undefined;
  onClick: () => void;
}

export interface ShellMenuProps {
  /** 面板的 aria-label。 */
  label: string;
  /** 面板对齐：左（缺省）或右。 */
  align?: 'left' | 'right';
  items: ShellMenuItem[];
  onSelect: (id: string) => void;
  children: (trigger: ShellMenuTriggerProps) => ReactNode;
}

export function ShellMenu({ label, align = 'left', items, onSelect, children }: ShellMenuProps) {
  const [open, setOpen] = useState(false);
  const triggerId = useId();
  const menuId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const focusTrigger = useCallback(() => {
    const trigger = document.getElementById(triggerId);
    if (trigger instanceof HTMLElement) trigger.focus();
  }, [triggerId]);

  // 打开后焦点到第一项（含禁用项，WAI-ARIA 允许聚焦）。
  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitem"], [role="menuitemradio"]');
    first?.focus();
  }, [open]);

  // 菜单与触发钮之外按下鼠标：关闭，不强行还焦点。
  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, [open]);

  const selectItem = (el: HTMLElement) => {
    if (el.getAttribute('aria-disabled') === 'true') return; // 禁用项选不中、菜单也不关
    const id = el.getAttribute('data-id');
    if (id != null) onSelect(id);
    setOpen(false);
    focusTrigger();
  };

  const onMenuKeyDown = (e: KeyboardEvent) => {
    const els = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"], [role="menuitemradio"]') ?? [],
    );
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
        if (current >= 0) selectItem(els[current]);
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
    <span className="tt-shell-menu-wrap" ref={wrapRef}>
      {children({
        id: triggerId,
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        'aria-controls': open ? menuId : undefined,
        onClick: () => setOpen((o) => !o),
      })}
      {open && (
        <div
          className={`tt-shell-menu tt-enter${align === 'right' ? ' tt-shell-menu--right' : ''}`}
          role="menu"
          id={menuId}
          aria-label={label}
          ref={menuRef}
          onKeyDown={onMenuKeyDown}
        >
          {items.map((item, index) => {
            if (item.kind === 'separator') {
              return <div key={`sep-${index}`} className="tt-shell-menu__sep" role="separator" />;
            }
            if (item.kind === 'group') {
              return (
                <div key={`grp-${index}`} className="tt-shell-menu__group">
                  {item.label}
                </div>
              );
            }
            const role = item.kind === 'radio' ? 'menuitemradio' : 'menuitem';
            const disabled = item.disabled === true;
            return (
              <div
                key={item.id}
                className="tt-shell-menu__item"
                role={role}
                tabIndex={-1}
                data-id={item.id}
                aria-checked={item.kind === 'radio' ? item.checked : undefined}
                aria-disabled={disabled || undefined}
                onClick={(e) => selectItem(e.currentTarget)}
              >
                {item.kind === 'radio' ? (
                  <span className="tt-shell-menu__lead" aria-hidden="true">
                    {item.checked && <CheckIcon width={14} height={14} />}
                  </span>
                ) : (
                  item.icon && (
                    <span className="tt-shell-menu__lead" aria-hidden="true">
                      {item.icon}
                    </span>
                  )
                )}
                <span className="tt-shell-menu__label">{item.label}</span>
                {item.kind === 'item' && item.trailing && (
                  <span className="tt-shell-menu__trailing">{item.trailing}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </span>
  );
}
