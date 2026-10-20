// 轻提示：常驻一个 role=status、aria-live=polite 的区域（没有轻提示时也渲染，空的）；可见时里面是图标、文字与关闭钮（24）。
// 计时：open 变 true 起 5000ms 到点调一次 onClose；鼠标移入暂停并记剩余时间，移出后按剩余时间接着走（不是重新计 5 秒）；
// 关闭钮立即调 onClose；卸载与重新打开都清计时器。挂到 body 下的挂载层，右下固定定位，tt-enter 入场。
import { useEffect, useRef, type ReactNode } from 'react';
import { CircleCheckIcon, InfoIcon, XIcon } from '../icons';
import { Tooltip } from './Tooltip';
import { MountLayer } from './overlay/MountLayer';
import './Toast.css';

// 自动关闭时长（写操作页 :419）。
const AUTO_CLOSE = 5000;

export type ToastTone = 'success' | 'info';

export interface ToastProps {
  open: boolean;
  onClose: () => void;
  /** 提示文字。 */
  children: ReactNode;
  /** 只管图标颜色，缺省 success（circle-check）。 */
  tone?: ToastTone;
}

export function Toast({ open, onClose, children, tone = 'success' }: ToastProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deadlineRef = useRef(0);
  const remainingRef = useRef<number | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const clear = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };
  const fire = () => {
    timerRef.current = null;
    onCloseRef.current();
  };
  const start = (delay: number) => {
    clear();
    deadlineRef.current = Date.now() + delay;
    timerRef.current = setTimeout(fire, delay);
  };
  const pause = () => {
    if (timerRef.current === null) return;
    const remaining = deadlineRef.current - Date.now();
    clear();
    remainingRef.current = remaining > 0 ? remaining : 0;
  };
  const resume = () => {
    if (timerRef.current !== null) return;
    const remaining = remainingRef.current;
    remainingRef.current = null;
    if (remaining != null) start(remaining);
  };

  useEffect(() => {
    if (!open) {
      clear();
      remainingRef.current = null;
      return;
    }
    start(AUTO_CLOSE);
    return () => {
      clear();
      remainingRef.current = null;
    };
  }, [open]);

  const Icon = tone === 'info' ? InfoIcon : CircleCheckIcon;

  return (
    <MountLayer>
      <div className="tt-toast-region" role="status" aria-live="polite">
        {open && (
          <div className="tt-toast tt-enter tt-fc" data-tone={tone} onMouseEnter={pause} onMouseLeave={resume}>
            <Icon className="tt-toast__icon" width={16} height={16} />
            <span className="tt-toast__text">{children}</span>
            <Tooltip content="关闭提示">
              <button
                type="button"
                className="tt-toast__close"
                aria-label="关闭提示"
                onClick={() => {
                  clear();
                  onClose();
                }}
              >
                <XIcon width={16} height={16} />
              </button>
            </Tooltip>
          </div>
        )}
      </div>
    </MountLayer>
  );
}
