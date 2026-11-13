// 取外壳实例的 context（src/shellpages/shellContext.tsx）：ThemisShellProvider 注入实例；useThemisShell 取实例。
// 取实例顺序：Provider 注入 → shellBridge 给的真实例 → 夹具模式的内存桩 → 真实模式的「外壳不可用」实例。
// 没有 Provider、没有真实外壳时，夹具模式按 location.hash 里的 shell= 场景取缓存的桩实例（同一场景同一实例、引用稳定）；
// 真实模式不创建桩、地址里的 shell= 不起作用，改由「外壳不可用」实例承接。resetShellStubs 给测试清桩缓存与计时器。
import { createContext, useContext, type ReactNode } from 'react';
import type { ThemisShell } from './themisShell';
import { createShellStub } from './shellStub';
import { SHELLPAGE_SCENARIO_NAMES } from '../mock/shellpages-scenarios';
import { liveModeIsReal } from '../live/mode';
import { shellBridgeInstance, unavailableShell } from './shellBridge';

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
  const bridged = shellBridgeInstance();
  if (bridged) return bridged;
  if (!liveModeIsReal()) return stubFor(scenarioFromHash(windowDefault));
  return unavailableShell();
}

export function resetShellStubs(): void {
  stubCache.forEach((stub) => {
    const s = stub as { dispose?: () => void };
    if (typeof s.dispose === 'function') s.dispose();
  });
  stubCache.clear();
}
