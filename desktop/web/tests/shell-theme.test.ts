// 主题（合同第 6 条 / D05）：applyTheme 只改 html 的 data-theme（暗去掉属性、亮 light、跟随系统 system），
// 不加类、不写内联样式、不动 body。
import { afterEach, describe, expect, it } from 'vitest';
import { applyTheme } from '../src/shell/theme';

describe('主题', () => {
  afterEach(() => { document.documentElement.removeAttribute('data-theme'); });

  it('暗去掉属性、亮写 light、跟随系统写 system', () => {
    applyTheme('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    applyTheme('system');
    expect(document.documentElement.getAttribute('data-theme')).toBe('system');
    applyTheme('dark');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
  });

  it('不改 body、不加类、不写内联样式', () => {
    applyTheme('light');
    expect(document.body.getAttribute('data-theme')).toBeNull();
    expect(document.body.getAttribute('style')).toBeNull();
    expect(document.documentElement.getAttribute('style')).toBeNull();
    expect(document.documentElement.className).toBe('');
  });
});
