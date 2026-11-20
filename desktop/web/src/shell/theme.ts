// 主题与密度：只改 html 元素的 data-theme（暗去掉属性、亮写 light、跟随系统写 system）与 data-density
// （标准去掉属性、紧凑写 compact）。applyTheme 是唯一写 data-theme 的地方，applyDensity 是唯一写 data-density 的地方。
// 偏好由桌面外壳保存（服务窗口经宿主、外壳页经桥），页面只持有当前值；缺省暗 + 标准密度（合同第 6 条）。
export type ThemePref = 'dark' | 'light' | 'system';
export type DensityPref = 'standard' | 'compact';

export function applyTheme(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === 'dark') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', pref);
  }
}

export function applyDensity(pref: DensityPref): void {
  const root = document.documentElement;
  if (pref === 'standard') {
    root.removeAttribute('data-density');
  } else {
    root.setAttribute('data-density', 'compact');
  }
}
