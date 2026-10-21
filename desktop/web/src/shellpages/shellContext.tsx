// 取桩的 context（src/shellpages/shellContext.tsx）：ThemisShellProvider 注入实例；useThemisShell 取实例。
// 没有 Provider 时按 location.hash 里的 shell= 场景取缓存的桩实例（同一场景同一实例、引用稳定）；
// resetShellStubs 给测试清缓存与计时器。本片不接真实外壳，全部走内存桩。
import { createContext, useContext, type ReactNode } from 'react';
import type { ThemisShell } from './themisShell';
import { createShellStub } from './shellStub';
import { SHELLPAGE_SCENARIO_NAMES } from '../mock/shellpages-scenarios';

const ShellContext = createContext<ThemisShell | null>(null);

const stubCache = new Map<string, ThemisShell>();

export interface ThemisShellProviderProps {
  shell: ThemisShell;
  children: ReactNode;
}

export function ThemisShellProvider({ shell, children }: ThemisShellProviderProps) {
  return <ShellContext.Provider value={shell}>{children}</ShellContext.Provider>;
}

function scenarioFromHash(windowDefault: string): string {
  const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
  const q = hash.indexOf('?');
  if (q >= 0) {
    for (const part of hash.slice(q + 1).split('&')) {
      const eq = part.indexOf('=');
      if (eq >= 0 && part.slice(0, eq) === 'shell') {
        const value = part.slice(eq + 1);
        if (SHELLPAGE_SCENARIO_NAMES.includes(value)) return value;
      }
    }
  }
  return SHELLPAGE_SCENARIO_NAMES.includes(windowDefault) ? windowDefault : 'ready';
}

function stubFor(scenario: string): ThemisShell {
  let stub = stubCache.get(scenario);
  if (!stub) {
    stub = createShellStub(scenario);
    stubCache.set(scenario, stub);
  }
  return stub;
}

export function useThemisShell(windowDefault: string): ThemisShell {
  const provided = useContext(ShellContext);
  if (provided) return provided;
  return stubFor(scenarioFromHash(windowDefault));
}

export function resetShellStubs(): void {
  stubCache.forEach((stub) => {
    const s = stub as { dispose?: () => void };
    if (typeof s.dispose === 'function') s.dispose();
  });
  stubCache.clear();
}
