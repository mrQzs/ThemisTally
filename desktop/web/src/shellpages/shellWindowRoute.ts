// 外壳窗口的地址钩子（src/shellpages/shellWindowRoute.ts）：parseShellWindow 纯函数 + useShellWindowRoute 钩子。
// 不改 router.ts：parseHash 把 #/first-run 当未知路径归总览，根上的钩子自己读 location.hash（K21）。
// useShellWindowRoute 存地址串（location.hash），shellWindow 由它算出；监听 hashchange，处理函数只把状态设成当前地址；
// navigateShell(path) 先算目标地址（保留查询串、没有 shell 时补当前场景），在函数体里先改状态、再写 location.hash，同步完成。
import { useCallback, useEffect, useState } from 'react';
import { SHELLPAGE_SCENARIO_NAMES } from '../mock/shellpages-scenarios';

export type ShellPage = 'first-run' | 'service-status';

export interface ShellWindowRoute {
  page: ShellPage;
  query: string;
}

const DEFAULT_SCENARIO: Record<ShellPage, string> = { 'first-run': 'ready', 'service-status': 'crash' };

// 第一段是 first-run 或 service-status 时给出 { page, query }（后面的段忽略），别的地址给 null。
export function parseShellWindow(hash: string): ShellWindowRoute | null {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const qIdx = raw.indexOf('?');
  const path = qIdx < 0 ? raw : raw.slice(0, qIdx);
  const query = qIdx < 0 ? '' : raw.slice(qIdx + 1);
  const first = path.split('/').filter((s) => s.length > 0)[0] ?? '';
  if (first === 'first-run' || first === 'service-status') {
    return { page: first, query };
  }
  return null;
}

// 场景：查询串里认得出的 shell= 优先，否则按页面取缺省（首启与设置 ready、服务状态 crash）。
export function scenarioOf(page: string, query: string): string {
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq >= 0 && part.slice(0, eq) === 'shell') {
      const value = part.slice(eq + 1);
      if (SHELLPAGE_SCENARIO_NAMES.includes(value)) return value;
    }
  }
  return DEFAULT_SCENARIO[page as ShellPage] ?? 'ready';
}

export function useShellWindowRoute() {
  const [hash, setHash] = useState<string>(() => (typeof window !== 'undefined' ? window.location.hash : ''));

  // 接住手改地址、后退与前进：只把状态设成当前 location.hash（重复到达不重渲染）。
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const shellWindow = parseShellWindow(hash);

  const navigateShell = useCallback((path: string) => {
    const cur = parseShellWindow(window.location.hash);
    const scenario = cur ? scenarioOf(cur.page, cur.query) : 'ready';
    const params = new URLSearchParams(cur ? cur.query : '');
    if (!params.get('shell')) params.set('shell', scenario);
    const qs = params.toString();
    const next = `#${path}${qs ? `?${qs}` : ''}`;
    setHash(next);
    window.location.hash = next;
  }, []);

  return { shellWindow, navigateShell };
}
