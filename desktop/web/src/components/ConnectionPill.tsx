// 连接胶囊（组件板 :435–437、断线页 :289–298、:448–450、UI 文档 7.20）：三态胶囊 + 点开的详情浮层。
// 胶囊是 button type=button，带 aria-expanded、aria-controls；里面圆点（aria-hidden）与状态文字（aria-live=polite）。
// 点一下打开、再点关闭；Esc 关闭并 stopPropagation、焦点留胶囊；胶囊与浮层之外按下鼠标关闭；浮层紧跟胶囊、无可聚焦元素。
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import './ConnectionPill.css';

export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected';

export interface ConnectionPillProps {
  state: ConnectionState;
  /** 重连第几次（重连中时显示）。 */
  attempt?: number;
  pid?: number;
  /** 已格式化的启动时间文字。 */
  startedAt?: string;
  /** 事件流那一行。 */
  stream?: string;
}

function statusText(state: ConnectionState, attempt: number | undefined): string {
  if (state === 'connected') return '已连接';
  if (state === 'disconnected') return '已断开';
  return attempt != null ? `重连中（第 ${attempt} 次）` : '重连中';
}

export function ConnectionPill({ state, attempt, pid, startedAt, stream }: ConnectionPillProps) {
  const [open, setOpen] = useState(false);
  const popId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);

  // 在胶囊与浮层之外按下鼠标：关闭。
  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (wrapRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, [open]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && open) {
      e.stopPropagation();
      setOpen(false);
    }
  };

  const show = (v: string | number | undefined) => (v == null ? '未知' : String(v));

  return (
    <span className="tt-pill-wrap" ref={wrapRef}>
      <button
        type="button"
        className="tt-pill"
        data-state={state}
        aria-expanded={open}
        aria-controls={popId}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onKeyDown}
      >
        <span className="tt-pill__dot" aria-hidden="true" />
        <span className="tt-pill__text" aria-live="polite">{statusText(state, attempt)}</span>
      </button>
      {open && (
        <div className="tt-pill-pop tt-enter" id={popId}>
          <dl className="tt-pill-pop__list">
            <dt>pid</dt>
            <dd className="tt-pill-pop__pid tt-num">{show(pid)}</dd>
            <dt>启动于</dt>
            <dd>{show(startedAt)}</dd>
            <dt>事件流</dt>
            <dd>{show(stream)}</dd>
          </dl>
        </div>
      )}
    </span>
  );
}
