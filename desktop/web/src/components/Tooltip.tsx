// 工具提示：悬停或聚焦 400ms 后出现，移开/失焦立即消失，可见或计时中按 Esc 消失且不再出现（直到重新悬停/聚焦）。
// 挂到 body 下的挂载层，固定定位在包裹元素正上方居中；aria-describedby 用 cloneElement 加到子元素，不要求子元素转发 ref。
import { cloneElement, useEffect, useId, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { MountLayer } from './overlay/MountLayer';

// 悬停/聚焦到出现的时延（UI 文档 7.23）。
const SHOW_DELAY = 400;

export interface TooltipProps {
  /** 提示文字（可以是节点）。 */
  content: ReactNode;
  /** 单个可聚焦元素；aria-describedby 会 clone 到它上面。 */
  children: ReactElement;
}

export function Tooltip({ content, children }: TooltipProps) {
  const tipId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hoveringRef = useRef(false);
  const focusedRef = useRef(false);
  const suppressedRef = useRef(false);
  const visibleRef = useRef(false);
  const [visible, setVisible] = useState(false);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };
  const show = () => {
    visibleRef.current = true;
    setVisible(true);
  };
  const hide = () => {
    clearTimer();
    visibleRef.current = false;
    setVisible(false);
  };
  const startTimer = () => {
    clearTimer();
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      show();
    }, SHOW_DELAY);
  };

  const onMouseEnter = () => {
    hoveringRef.current = true;
    suppressedRef.current = false;
    if (!visibleRef.current) startTimer();
  };
  const onMouseLeave = () => {
    hoveringRef.current = false;
    if (!focusedRef.current) hide();
  };
  const onFocus = () => {
    focusedRef.current = true;
    suppressedRef.current = false;
    if (!visibleRef.current) startTimer();
  };
  const onBlur = () => {
    focusedRef.current = false;
    if (!hoveringRef.current) hide();
  };

  // Esc：可见或计时中则消失并抑制（直到重新悬停/聚焦）。聚焦时走 React 合成事件（子元素 keydown 冒泡到包裹元素），可见时消费掉；
  // 只悬停没聚焦时 keydown 不会经过包裹元素，改在 document 上监听。
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Escape') return;
    const wasVisible = visibleRef.current;
    if (wasVisible || timerRef.current !== null) {
      hide();
      suppressedRef.current = true;
      if (wasVisible) e.stopPropagation();
    }
  };
  useEffect(() => {
    const onDocKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (hoveringRef.current && !focusedRef.current && (visibleRef.current || timerRef.current !== null)) {
        hide();
        suppressedRef.current = true;
      }
    };
    document.addEventListener('keydown', onDocKeyDown);
    return () => document.removeEventListener('keydown', onDocKeyDown);
  }, []);

  // 卸载时清计时器，避免卸载后触发。
  useEffect(() => clearTimer, []);

  const rect = wrapRef.current?.getBoundingClientRect();
  const top = rect ? rect.top : 0;
  const left = rect ? rect.left + rect.width / 2 : 0;

  const trigger = cloneElement(children, {
    'aria-describedby': visible ? tipId : undefined,
  });

  return (
    <span
      ref={wrapRef}
      className="tt-tooltip-wrap"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onFocus={onFocus}
      onBlur={onBlur}
      onKeyDown={onKeyDown}
    >
      {trigger}
      {visible && (
        <MountLayer>
          <div className="tt-tooltip tt-fc" role="tooltip" id={tipId} style={{ top, left }}>
            {content}
          </div>
        </MountLayer>
      )}
    </span>
  );
}
