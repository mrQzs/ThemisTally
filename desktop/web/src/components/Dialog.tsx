// 对话框（W6）：模态，role=dialog、aria-modal=true，带 tt-enter；遮罩盖满窗口、挂到 body 下的挂载层，点遮罩不关闭。
// 焦点：打开时进框内第一个可聚焦元素，关闭/卸载时还给打开前的元素；困焦点（末元素 Tab 回首、首元素 Shift+Tab 到末），
// Esc 由对话框处理并 stopPropagation。关闭钮在头部。
// 遮罩只在点到自身时阻止 mousedown 默认（防止点遮罩抢走框内焦点、拖选文字）；点到框内（输入框、正文、标题、底栏）不拦，
// 因此框内输入框可聚焦、可拖选（T005 7.1）。
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { IconButton } from './IconButton';
import { XIcon } from '../icons';
import { MountLayer } from './overlay/MountLayer';
import { getFocusable } from './overlay/focusable';
import { useOverlayFocus } from './overlay/useOverlayFocus';
import './Dialog.css';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

export function Dialog({ open, onClose, title, children, footer }: DialogProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  useOverlayFocus(open, dialogRef);

  if (!open) return null;

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key === 'Tab') {
      const root = dialogRef.current;
      if (!root) return;
      const list = getFocusable(root);
      if (list.length === 0) {
        e.preventDefault();
        root.focus();
        return;
      }
      const first = list[0];
      const last = list[list.length - 1];
      const active = document.activeElement;
      if (!e.shiftKey && (active === last || active === root)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault();
        last.focus();
      }
    }
  };

  return (
    <MountLayer>
      <div
        className="tt-dialog-scrim"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) e.preventDefault();
        }}
      >
        <div
          ref={dialogRef}
          className="tt-dialog tt-enter tt-fc"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          tabIndex={-1}
          onKeyDown={onKeyDown}
        >
          <div className="tt-dialog__head">
            <h2 className="tt-dialog__title" id={titleId}>{title}</h2>
            <IconButton label="关闭（Esc）" icon={<XIcon />} size="sm" onClick={onClose} />
          </div>
          <div className="tt-dialog__body">{children}</div>
          {footer && <div className="tt-dialog__footer">{footer}</div>}
        </div>
      </div>
    </MountLayer>
  );
}
