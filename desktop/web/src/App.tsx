// 根组件：应用框架（合同第 1、6、9 条与 Steps 9）。标题栏 + 内容区（按路由 key 重挂载以滚回顶部）+ 底部 Tab 栏。
// 快捷键 Ctrl+1…8 与 Ctrl+, 切页；document.title 随页面变；外壳级 getStatus 供 Tab 栏计数；
// 页面框架经 ShellStatusContext 向 Tab 栏上报加载状态。陈列页（#/showcase）不是 Tab，由 ShowcasePage 渲染。
// #/first-run、#/service-status 由根上的外壳窗口整窗渲染，不挂服务窗口；外观（主题与密度）在根上，
// 经 ThemePrefProvider 交给设置页。外观由桌面外壳保存：服务窗口经宿主、外壳页经桥；启动时同步读一次当前值，
// 之后跟着外观广播变；标题栏的主题菜单按宿主 → 桥 → 内存三档保存。
import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { getMeta, getMetaNow, getStatus, type MetaData } from './api';
import { TABS } from './shell/routes';
import { useHashRoute } from './shell/router';
import { installShortcuts } from './shell/shortcuts';
import { applyDensity, applyTheme, type DensityPref, type ThemePref } from './shell/theme';
import { TitleBar } from './shell/TitleBar';
import { TabBar } from './shell/TabBar';
import { useShellConnection } from './shell/useShellConnection';
import { ShellStatusProvider, type PageReport } from './shell/ShellStatusContext';
import { countByGroup, type StatusCounts } from './shell/attemptGroups';
import ShowcasePage from './showcase/ShowcasePage';
import './App.css';
import { ShellWindow, useShellWindowRoute } from './shellpages/ShellWindow';
import { ThemePrefProvider } from './shellpages/themePref';
import { shellAppearanceNow, shellBridgeInstance, shellOnAppearance } from './shellpages/shellBridge';
import { hostGetAppearance, hostOnAppearance, hostSaveTheme } from './live/hostSettings';

// 外观的当前取值与它的来源：宿主（服务窗口）优先，其次外壳桥（设置、首启、服务状态窗口）；
// 同步读与订阅按同一个来源走，免得两种桥同时在时收到重复广播。
interface Appearance {
  theme: ThemePref;
  density: DensityPref;
  source: 'host' | 'shell' | null;
}

// 外观广播的形状与来源无关，在本地写一份（根组件不许出现外壳接口文件的路径字样）。
interface AppearanceEvent {
  theme: 'dark' | 'light' | 'system';
  density: 'standard' | 'compact';
}

// 懒初值：宿主 → 桥 → 缺省暗 + 标准。读外观只在这里做一次。
function initialAppearance(): Appearance {
  const fromHost = hostGetAppearance();
  const appearance = fromHost ?? shellAppearanceNow();
  const source = fromHost !== null ? 'host' : appearance !== null ? 'shell' : null;
  return {
    theme: appearance?.theme ?? 'dark',
    density: appearance?.density ?? 'standard',
    source,
  };
}

export default function App() {
  const [appearance, setAppearance] = useState<Appearance>(initialAppearance);
  const { theme, density, source } = appearance;
  const { shellWindow, navigateShell } = useShellWindowRoute();

  const setTheme = (pref: ThemePref): void => {
    setAppearance((cur) => (cur.theme === pref ? cur : { ...cur, theme: pref }));
  };

  const changeTheme = (pref: ThemePref): void => {
    // 宿主档：保存成功（信封 ok:true）才切；失败或被拒都保持原主题、不重试、不弹提示。
    const hostSave = hostSaveTheme(pref);
    if (hostSave !== null) {
      hostSave.then(
        (envelope) => {
          if (envelope.ok === true) setTheme(pref);
        },
        () => {},
      );
      return;
    }
    // 桥档：外壳的保存兑现后才切。
    const shell = shellBridgeInstance();
    if (shell !== null) {
      shell.saveSettings({ theme: pref }).then(
        () => setTheme(pref),
        () => {},
      );
      return;
    }
    // 内存档：两档都没有，只改当前值。
    setTheme(pref);
  };

  // 外观广播逐字段校验：合法才覆盖，非法字段忽略（不写缺省、不报错）；实参不是对象整个忽略。
  const onAppearance = useCallback((event: AppearanceEvent) => {
    const value: unknown = event;
    if (value === null || typeof value !== 'object') return;
    const raw = value as { theme?: unknown; density?: unknown };
    const nextTheme = raw.theme === 'light' || raw.theme === 'system' || raw.theme === 'dark' ? raw.theme : null;
    const nextDensity = raw.density === 'standard' || raw.density === 'compact' ? raw.density : null;
    if (nextTheme === null && nextDensity === null) return;
    setAppearance((cur) => ({ ...cur, theme: nextTheme ?? cur.theme, density: nextDensity ?? cur.density }));
  }, []);

  useEffect(() => {
    if (source === 'host') return hostOnAppearance(onAppearance);
    if (source === 'shell') return shellOnAppearance(onAppearance);
    return undefined;
  }, [source, onAppearance]);

  // 首帧之前就把主题与密度写好，别用 useEffect（会先渲染一帧旧外观）。
  useLayoutEffect(() => {
    applyTheme(theme);
    applyDensity(density);
  }, [theme, density]);

  return (
    <ThemePrefProvider theme={theme} onThemeChange={setTheme}>
      {shellWindow ? (
        <ShellWindow route={shellWindow} navigate={navigateShell} />
      ) : (
        <ServiceApp theme={theme} changeTheme={changeTheme} />
      )}
    </ThemePrefProvider>
  );
}

interface ServiceAppProps {
  theme: ThemePref;
  changeTheme: (pref: ThemePref) => void;
}

// 真实模式下 meta 未兑现时的占位：首屏不闪夹具里的 demo-repo 与 kit 2.12.0。
const PLACEHOLDER_META: MetaData = { kit_version: '—', repo_name: '—' };

function ServiceApp({ theme, changeTheme }: ServiceAppProps) {
  const { route, navigate } = useHashRoute();
  const { live, state } = useShellConnection();
  const [meta, setMeta] = useState<MetaData>(() => (live ? PLACEHOLDER_META : getMetaNow()));
  const [counts, setCounts] = useState<StatusCounts | null>(null);
  const [page, setPage] = useState<PageReport>({ phase: 'loading', at: null });

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

  // 真实模式下 meta 异步取一次：成功才填，失败保持占位「—」，不报错、不清空。夹具模式一个 getMeta() 都不调。
  useEffect(() => {
    if (!live) return;
    let alive = true;
    getMeta().then((env) => {
      if (alive && env.ok && env.data) setMeta(env.data);
    });
    return () => {
      alive = false;
    };
  }, [live]);

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

  const offline = state === 'disconnected';
  const routeKey = `${route.pageId}|${route.segments.join('/')}|${route.query}`;

  const renderPage = () => {
    if (route.pageId === 'showcase') return <ShowcasePage />;
    const tab = TABS.find((t) => t.id === route.pageId) ?? TABS[0];
    return <tab.Page />;
  };

  return (
    <ShellStatusProvider value={setPage}>
      <div className="tt-app tt-shell">
        <TitleBar theme={theme} onThemeChange={changeTheme} repoName={meta.repo_name} />
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
