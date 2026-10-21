// 自写 hash 路由（合同第 1 条）：不装 react-router。解析 location.hash，提供 navigate 与 hashchange 监听。
import { useCallback, useEffect, useState } from 'react';
import { TABS } from './routes';

export const SHOWCASE_ID = 'showcase';

export interface Route {
  /** 当前 Tab 的 id；陈列页或未命中 Tab 时为 null。 */
  tabId: string | null;
  /** 实际渲染的页面 id：某个 Tab id 或 showcase。 */
  pageId: string;
  /** 第一段之后的路径段，原样交给页面。 */
  segments: string[];
  /** 查询串（? 之后，不含 ?）；导航时保留。 */
  query: string;
}

function mockOfQuery(query: string): string {
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq >= 0 && part.slice(0, eq) === 'mock') return part.slice(eq + 1);
  }
  return '';
}

// 去掉开头 #，按 ? 切路径与查询；第一段决定页面，空/#/#/ 与未知路径都归总览（不改写地址）。
export function parseHash(hash: string): Route {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const qIdx = raw.indexOf('?');
  const path = qIdx < 0 ? raw : raw.slice(0, qIdx);
  const query = qIdx < 0 ? '' : raw.slice(qIdx + 1);
  const segments = path.split('/').filter((s) => s.length > 0);
  const first = segments[0] ?? '';
  if (first === SHOWCASE_ID) {
    return { tabId: null, pageId: SHOWCASE_ID, segments: segments.slice(1), query };
  }
  const tab = TABS.find((t) => t.id === first);
  if (tab) {
    return { tabId: tab.id, pageId: tab.id, segments: segments.slice(1), query };
  }
  // 空、#、#/ 与未知路径都显示总览，但不改写地址。
  return { tabId: 'overview', pageId: 'overview', segments: [], query };
}

// 当前挂载路由的 navigate：useHashRoute 挂载时经 effect 登记，useAppNavigate 委托它同步换路由。
let activeNavigate: ((path: string) => void) | null = null;

// 由 path 与当前 query 拼出下一个 hash：path 自带 ?query 时合并（保留 mock 与其他参数，path 的覆盖同名），
// 否则整段保留当前 query（与现状完全相同）。
function buildHash(path: string, currentQuery: string): string {
  const qIdx = path.indexOf('?');
  if (qIdx < 0) return `#${path}${currentQuery ? `?${currentQuery}` : ''}`;
  const pathname = path.slice(0, qIdx);
  const merged = new URLSearchParams(currentQuery);
  new URLSearchParams(path.slice(qIdx + 1)).forEach((v, k) => merged.set(k, v));
  const qs = merged.toString();
  return `#${pathname}${qs ? `?${qs}` : ''}`;
}

export function useHashRoute() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  // 接住后退、前进与手改地址（jsdom 里 hashchange 经 setTimeout(0) 异步派发）。
  useEffect(() => {
    const onHashChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // 先同步更新路由状态，再写 location.hash；path 可自带 ?query，与当前 query 合并（保留 mock）。
  const navigate = useCallback(
    (path: string) => {
      setRoute((prev) => {
        const next = buildHash(path, prev.query);
        if (window.location.hash !== next) window.location.hash = next;
        return parseHash(next);
      });
    },
    [],
  );

  // 登记为当前挂载路由的 navigate（useAppNavigate 委托它）；卸载时让位。
  useEffect(() => {
    activeNavigate = navigate;
    return () => {
      if (activeNavigate === navigate) activeNavigate = null;
    };
  }, [navigate]);

  return { route, navigate };
}

// 供页面组件（不接 props）同步换路由：返回稳定回调，委托当前挂载路由的 navigate（调用时读，effect 已登记）。
export function useAppNavigate() {
  return useCallback((path: string) => {
    activeNavigate?.(path);
  }, []);
}

export { mockOfQuery };
