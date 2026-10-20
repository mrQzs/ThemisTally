// 根组件：应用框架（合同第 1、6、9 条与 Steps 9）。标题栏 + 内容区（按路由 key 重挂载以滚回顶部）+ 底部 Tab 栏。
// 主题偏好只存内存、缺省暗；快捷键 Ctrl+1…8 与 Ctrl+, 切页；document.title 随页面变；外壳级 getStatus 供 Tab 栏计数；
// 页面框架经 ShellStatusContext 向 Tab 栏上报加载状态。陈列页（#/showcase）不是 Tab，由 ShowcasePage 渲染。
import { useEffect, useState } from 'react';
import { getMetaNow, getStatus } from './api';
import { TABS } from './shell/routes';
import { useHashRoute } from './shell/router';
import { installShortcuts } from './shell/shortcuts';
import { applyTheme, type ThemePref } from './shell/theme';
import { TitleBar } from './shell/TitleBar';
import { TabBar } from './shell/TabBar';
import { ShellStatusProvider, type PageReport } from './shell/ShellStatusContext';
import { countByGroup, type StatusCounts } from './shell/attemptGroups';
import { currentMock } from './mock/scenario';
import { shellConnectionState } from './mock/shell';
import ShowcasePage from './showcase/ShowcasePage';
import './App.css';

export default function App() {
  const [theme, setTheme] = useState<ThemePref>('dark');
  const { route, navigate } = useHashRoute();
  const meta = getMetaNow();
  const [counts, setCounts] = useState<StatusCounts | null>(null);
  const [page, setPage] = useState<PageReport>({ phase: 'loading', at: null });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // 快捷键：Ctrl+1…8 切前 8 个 Tab，Ctrl+, 切设置。
  useEffect(
    () =>
      installShortcuts((tabId) => {
        const tab = TABS.find((t) => t.id === tabId);
        if (tab) navigate(tab.path);
      }),
    [navigate],
  );

  // document.title：页面标题 · Themis Tally；陈列页写 组件陈列 · Themis Tally。
  useEffect(() => {
    const tab = TABS.find((t) => t.id === route.pageId);
    document.title =
      route.pageId === 'showcase' ? '组件陈列 · Themis Tally' : `${tab?.title ?? '总览'} · Themis Tally`;
  }, [route.pageId]);

  // 外壳级 getStatus 计数；随 ?mock= 变化重取，未读到显示 —。
  useEffect(() => {
    let alive = true;
    setCounts(null);
    getStatus().then((env) => {
      if (!alive) return;
      if (env.ok && env.data) setCounts(countByGroup(env.data));
    });
    return () => {
      alive = false;
    };
  }, [route.query]);

  const offline = shellConnectionState(currentMock()) === 'disconnected';
  const routeKey = `${route.pageId}|${route.segments.join('/')}|${route.query}`;

  const renderPage = () => {
    if (route.pageId === 'showcase') return <ShowcasePage />;
    const tab = TABS.find((t) => t.id === route.pageId) ?? TABS[0];
    return <tab.Page />;
  };

  return (
    <ShellStatusProvider value={setPage}>
      <div className="tt-app tt-shell">
        <TitleBar theme={theme} onThemeChange={setTheme} repoName={meta.repo_name} />
        <TabBar
          route={route}
          navigate={navigate}
          counts={counts}
          page={page}
          kitVersion={meta.kit_version}
          repoName={meta.repo_name}
          offline={offline}
        />
        <main className="tt-shell__content tt-content" key={routeKey}>
          {renderPage()}
        </main>
      </div>
    </ShellStatusProvider>
  );
}
