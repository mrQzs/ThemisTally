// 主题 context（src/shellpages/themePref.tsx）：主题偏好放在根上（App），经 ThemePrefProvider 交给设置页。
// value 用 useMemo；useThemePref 返回 { theme, setTheme }；没有 Provider 时退回组件内本地状态，不抛错。
// 本片只有设置页用它；写主题属性仍只经 theme.ts 的 applyTheme。
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { ThemePref } from '../shell/theme';

interface ThemePrefValue {
  theme: ThemePref;
  setTheme: (pref: ThemePref) => void;
}

const ThemePrefContext = createContext<ThemePrefValue | null>(null);

export interface ThemePrefProviderProps {
  theme: ThemePref;
  onThemeChange: (pref: ThemePref) => void;
  children: ReactNode;
}

export function ThemePrefProvider({ theme, onThemeChange, children }: ThemePrefProviderProps) {
  const value = useMemo<ThemePrefValue>(() => ({ theme, setTheme: onThemeChange }), [theme, onThemeChange]);
  return <ThemePrefContext.Provider value={value}>{children}</ThemePrefContext.Provider>;
}

export function useThemePref(): ThemePrefValue {
  const ctx = useContext(ThemePrefContext);
  const [local, setLocal] = useState<ThemePref>('dark');
  if (ctx) return ctx;
  return { theme: local, setTheme: setLocal };
}
