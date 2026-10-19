// 抽屉：非模态，role=dialog、aria-modal=false，带 tt-drawer-in；没有遮罩、不困焦点（Tab 不拦），点抽屉外不关闭。
// 打开时焦点进入、关闭后回触发元素；焦点在抽屉里按 Esc 关闭并 stopPropagation。靠右、只有左侧两角圆角、底边让位标签栏。
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { IconButton } from './IconButton';
import { XIcon } from '../icons';
import { MountLayer } from './overlay/MountLayer';
import { useOverlayFocus } from './overlay/useOverlayFocus';
import './Drawer.css';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

export function Drawer({ open, onClose, title, children, footer }: DrawerProps) {
  const titleId = useId();
  const drawerRef = useRef<HTMLDivElement>(null);
  useOverlayFocus(open, drawerRef);

  if (!open) return null;

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
    }
  };

  return (
    <MountLayer>
      <div
        ref={drawerRef}
        className="tt-drawer tt-drawer-in tt-fc"
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
      >
        <div className="tt-drawer__head">
          <h2 className="tt-drawer__title" id={titleId}>{title}</h2>
          <IconButton label="关闭（Esc）" icon={<XIcon />} size="sm" onClick={onClose} />
        </div>
        <div className="tt-drawer__body">{children}</div>
        {footer && <div className="tt-drawer__footer">{footer}</div>}
      </div>
    </MountLayer>
  );
}
