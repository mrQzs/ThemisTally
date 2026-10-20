// 主题：只改 html 元素的 data-theme（暗去掉属性、亮写 light、跟随系统写 system）。
// applyTheme 是唯一写 data-theme 的地方；偏好只存内存，缺省暗（合同第 6 条）。
export type ThemePref = 'dark' | 'light' | 'system';

export function applyTheme(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === 'dark') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', pref);
  }
}
