// 骨架屏（组件板 :474–480、handoff :154）：挂载后 300ms 内不渲染，满 300ms 出现 4 条 tt-skel；卸载清计时器。
// 计时用 setTimeout + 具名常量（不用 rAF、performance，fake timers 推不动）；不写动画、过渡、渐变，用 base.css 现成的 tt-pulse。
import { useEffect, useState } from 'react';
import './Skeleton.css';

// 挂载到出现的时延（组件板 :474）。
const SHOW_DELAY = 300;

// 条高 14/20/20/20、宽 40%/100%/82%/64%（组件板 :474–480）。
const BARS: ReadonlyArray<{ h: number; w: string }> = [
  { h: 14, w: '40%' },
  { h: 20, w: '100%' },
  { h: 20, w: '82%' },
  { h: 20, w: '64%' },
];

export interface SkeletonProps {
  /** 追加到容器上的类名。 */
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setShown(true), SHOW_DELAY);
    return () => clearTimeout(timer);
  }, []);
  if (!shown) return null;
  return (
    <div className={className ? `tt-skeleton ${className}` : 'tt-skeleton'} aria-busy="true">
      {BARS.map((bar) => (
        <div key={bar.w} className="tt-skel" aria-hidden="true" style={{ height: bar.h, width: bar.w }} />
      ))}
    </div>
  );
}
