// Tab 栏（合同第 4 条，照 handoff :65–70 与 Main 画布 :40–58）：nav 主导航，高 tabbar-height、sidebar 底、
// 上边框 sidebar-hover、左右 space-2；DOM 顺序放在内容区之前，用 order 排到最下。9 项图标在上文字在下，
// 每项 <a href=#/id data-tab=id>；当前项 aria-current=page 加 3px 金条；计数胶囊只在任务一项；最右状态段
// aria-live=polite。链接无修饰键左键点击先 preventDefault 再自己导航，保留当前 ?mock=。
import { Fragment, useEffect, useState, type MouseEvent } from 'react';
import { TABS } from './routes';
import type { Route } from './router';
import type { StatusCounts } from './attemptGroups';
import type { PageReport } from './ShellStatusContext';
import { relativeTime, clockTime } from './relativeTime';
import './TabBar.css';

export interface TabBarProps {
  route: Route;
  navigate: (path: string) => void;
  /** 外壳级 getStatus 的计数；null 表示未读到（显示 —）。 */
  counts: StatusCounts | null;
  /** 当前页面框架上报的状态，用于「上次更新」。 */
  page: PageReport;
  kitVersion: string;
  repoName: string;
  offline: boolean;
}

function lastUpdateText(page: PageReport, offline: boolean, now: number): string {
  if (page.phase === 'loading') return '正在读取…';
  if (page.phase === 'error') return `读取失败 · ${clockTime(page.at ?? now)}`;
  const base = `上次更新 ${relativeTime(page.at ?? now, now)}`;
  return offline ? `${base} · 可能已过期` : base;
}

export function TabBar({ route, navigate, counts, page, kitVersion, repoName, offline }: TabBarProps) {
  const [now, setNow] = useState(() => Date.now());

  // 「上次更新 X 前」的 X 每秒刷新；只在有数据时跑计时器。
  useEffect(() => {
    if (page.phase !== 'data') return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [page.phase]);

  const onLinkClick = (e: MouseEvent, path: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // 带修饰键走默认行为
    e.preventDefault();
    navigate(path);
  };

  const needJudge = counts ? counts.needJudge : 0;
  const q = route.query ? `?${route.query}` : '';

  return (
    <nav className="tt-tabbar" aria-label="主导航">
      {TABS.map((tab) => {
        const current = route.tabId === tab.id;
        const count = tab.id === 'tasks' ? needJudge : 0;
        const showCount = tab.id === 'tasks' && count > 0;
        return (
          <Fragment key={tab.id}>
            {tab.id === 'settings' && <span className="tt-tabbar__divider" data-tab-divider aria-hidden="true" />}
            <a
              href={`#${tab.path}${q}`}
              className={`tt-tabbar__tab${current ? ' is-current' : ''}`}
              data-tab={tab.id}
              aria-current={current ? 'page' : undefined}
              aria-label={showCount ? `${tab.title}（${count} 项需要你判断）` : undefined}
              title={`${tab.title}（Ctrl+${tab.shortcut}）`}
              onClick={(e) => onLinkClick(e, tab.path)}
            >
              {current && <span className="tt-tabbar__indicator" aria-hidden="true" />}
              <tab.Icon width={18} height={18} aria-hidden="true" />
              <span className="tt-tabbar__label">{tab.title}</span>
              {showCount && (
                <span className="tt-tabbar__count" data-tab-count aria-hidden="true">
                  {count}
                </span>
              )}
            </a>
          </Fragment>
        );
      })}
      <div className="tt-tabbar__spacer" />
      <div className="tt-tabbar__status" aria-live="polite" title={`kit ${kitVersion} · ${repoName}`}>
        <a href={`#/tasks${q}`} className="tt-tabbar__stat tt-tabbar__stat--link" onClick={(e) => onLinkClick(e, '/tasks')}>
          <span className="tt-tabbar__dot tt-tabbar__dot--info" aria-hidden="true" />
          运行中 <span className="tt-num">{counts ? counts.running : '—'}</span>
        </a>
        <a href={`#/tasks${q}`} className="tt-tabbar__stat tt-tabbar__stat--link" onClick={(e) => onLinkClick(e, '/tasks')}>
          <span className="tt-tabbar__dot tt-tabbar__dot--accent" aria-hidden="true" />
          需要你判断 <span className="tt-num">{counts ? counts.needJudge : '—'}</span>
        </a>
        {route.pageId !== 'showcase' && (
          <span className="tt-tabbar__status-text tt-hide-narrow" aria-live="off">
            {lastUpdateText(page, offline, now)}
          </span>
        )}
        <span className="tt-tabbar__status-text tt-hide-narrow">kit {kitVersion}</span>
      </div>
    </nav>
  );
}
