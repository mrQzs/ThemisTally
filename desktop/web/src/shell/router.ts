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

export function useHashRoute() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  // 接住后退、前进与手改地址（jsdom 里 hashchange 经 setTimeout(0) 异步派发）。
  useEffect(() => {
    const onHashChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // 先同步更新路由状态，再写 location.hash；保留当前 ?mock=。
  const navigate = useCallback(
    (path: string) => {
      setRoute((prev) => {
        const next = `#${path}${prev.query ? `?${prev.query}` : ''}`;
        if (window.location.hash !== next) window.location.hash = next;
        return parseHash(next);
      });
    },
    [],
  );

  return { route, navigate };
}

export { mockOfQuery };
