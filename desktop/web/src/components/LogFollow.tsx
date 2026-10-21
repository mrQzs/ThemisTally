// 日志跟随（UI 文档 7.15、详情页 :634–639、领域板 :380）：建在 T007 的 TextViewer 上，加过滤框、跟随开关与底部状态。
// 跟随状态机：贴底（d ≤ 40）时跟随最新内容；往上滚且离底超过 40 暂停，暂停中停 150ms 内回到底部就恢复；
// 计时只用 setTimeout（不用 requestAnimationFrame 与 performance.now），卸载时清掉；滚到底用 useLayoutEffect。
// 不可信文字只按文本节点显示（TextViewer 负责）；不设 role、不设 aria-live。
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { FilterIcon, PauseIcon } from '../icons';
import { Button } from './Button';
import { Switch } from './Switch';
import { TextViewer, type TextViewerProps } from './TextViewer';
import './LogFollow.css';

const NEAR_BOTTOM = 40; // 贴底阈值，UI 文档 7.15 :910
const RESUME_MS = 150; // 暂停后恢复计时，UI 文档 7.15 :910

type FollowState = 'following' | 'paused' | 'off' | 'disabled';

export interface LogFollowProps
  extends Omit<TextViewerProps, 'bodyRef' | 'onBodyScroll' | 'bodyClassName' | 'headerExtra' | 'bottomBar' | 'filter'> {
  /** 初始是否跟随，缺省开。 */
  defaultFollow?: boolean;
  /** 非空时跟随不可用（例如 attempt 已结束）；变回空回到 following。 */
  followDisabledReason?: string;
}

export function LogFollow({ defaultFollow = true, followDisabledReason, className, ...rest }: LogFollowProps) {
  const [switchOn, setSwitchOn] = useState(defaultFollow);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState('');
  const bodyRef = useRef<HTMLDivElement>(null);
  const followRef = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastTopRef = useRef(0);

  const disabled = followDisabledReason != null && followDisabledReason !== '';
  const [prevDisabled, setPrevDisabled] = useState(disabled);
  // 从 disabled 变回可用时回到 following（站主 Q1 甲：清掉原因即恢复跟随）。
  if (disabled !== prevDisabled) {
    setPrevDisabled(disabled);
    if (!disabled) {
      setSwitchOn(true);
      setPaused(false);
    }
  }

  const followState: FollowState = disabled ? 'disabled' : !switchOn ? 'off' : paused ? 'paused' : 'following';
  const switchChecked = !disabled && switchOn;

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };
  const scheduleResume = () => {
    clearTimer();
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      const body = bodyRef.current;
      if (!body) return;
      const d = body.scrollHeight - body.scrollTop - body.clientHeight;
      if (d <= NEAR_BOTTOM) setPaused(false);
    }, RESUME_MS);
  };

  const handleScroll = () => {
    const body = bodyRef.current;
    if (!body) return;
    const top = body.scrollTop;
    const d = body.scrollHeight - top - body.clientHeight;
    if (followState === 'following') {
      // 看方向：scrollTop 比上次记下的小（往上滚）且离底超过 40 才暂停。
      if (top < lastTopRef.current && d > NEAR_BOTTOM) {
        lastTopRef.current = top;
        setPaused(true);
        scheduleResume();
        return;
      }
    } else if (followState === 'paused') {
      lastTopRef.current = top;
      scheduleResume();
      return;
    }
    lastTopRef.current = top;
  };

  // 进入 following，以及 following 中 pages 或过滤变化之后，滚到底。
  useLayoutEffect(() => {
    if (followState !== 'following') return;
    const body = bodyRef.current;
    if (!body) return;
    body.scrollTop = body.scrollHeight;
    lastTopRef.current = body.scrollTop;
  }, [followState, rest.pages, filter]);

  useEffect(() => () => clearTimer(), []);

  const onFollowToggle = (next: boolean) => {
    clearTimer();
    setSwitchOn(next);
    if (next) setPaused(false);
  };
  const onBackToBottom = () => {
    setPaused(false);
    const body = bodyRef.current;
    if (body) {
      body.scrollTop = body.scrollHeight;
      lastTopRef.current = body.scrollTop;
    }
    const sw = followRef.current?.querySelector('[role="switch"]') as HTMLElement | null;
    sw?.focus();
  };

  const headerExtra = (
    <>
      <label className="tt-log__filter">
        <FilterIcon width={14} height={14} />
        <input
          className="tt-log__filter-input"
          type="text"
          aria-label="过滤事件"
          placeholder="按文字包含过滤…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </label>
      <span className="tt-log__follow" ref={followRef} title={disabled ? followDisabledReason : undefined}>
        <Switch label="跟随" checked={switchChecked} disabled={disabled} onChange={onFollowToggle} />
      </span>
    </>
  );

  const statusBody = () => {
    if (followState === 'paused') {
      return (
        <>
          <PauseIcon width={16} height={16} />
          <span>已暂停跟随：你在往上看</span>
          <Button variant="secondary" size="sm" onClick={onBackToBottom}>
            回到底部
          </Button>
        </>
      );
    }
    if (followState === 'disabled') return <span>{followDisabledReason}</span>;
    if (followState === 'off') return <span>已关闭跟随</span>;
    return <span>正在跟随最新内容</span>;
  };

  return (
    <TextViewer
      {...rest}
      className={['tt-log', className].filter(Boolean).join(' ')}
      bodyRef={bodyRef}
      onBodyScroll={handleScroll}
      bodyClassName="tt-log__body"
      headerExtra={headerExtra}
      bottomBar={
        <div className="tt-log__status" data-follow={followState}>
          {statusBody()}
        </div>
      }
      filter={filter}
    />
  );
}
