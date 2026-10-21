// CSS 取值测试（合同第 9 节）：§8 关键取值在位、只用令牌、没有写死颜色。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function css(name: string): string {
  return readFileSync(resolve(process.cwd(), 'src/pages/readonly1', name), 'utf8');
}
const ALL = ['common-section.css', 'overview-styles.css', 'roles-styles.css', 'runtimes-styles.css'].map(css).join('\n');

describe('CSS 取值', () => {
  it('§8 关键取值在位', () => {
    expect(ALL).toContain('repeat(4, minmax(0, 1fr))');
    expect(ALL).toContain('repeat(2, minmax(0, 1fr))');
    expect(ALL).toContain('min-width: 860px');
    expect(ALL).toContain('min-width: 760px');
    expect(ALL).toContain('min-width: 900px');
    expect(ALL).toContain('max-width: 280px');
    expect(ALL).toContain('104px minmax(0, 1fr) auto auto');
    expect(ALL).toContain('48px 92px 120px minmax(0, 1fr) auto');
    expect(ALL).toContain('96px minmax(0, 1fr) 24px minmax(0, 1fr)');
    expect(ALL).toContain('3px solid var(--tt-accent)');
    expect(ALL).toContain('var(--tt-diff-del)');
    expect(ALL).toContain('var(--tt-diff-add)');
    expect(ALL).toContain('1px dashed var(--tt-border-strong)');
    expect(ALL).toContain('var(--tt-tone-info-fg)');
    expect(ALL).toContain('var(--tt-tone-escalate-fg)');
    expect(ALL).toContain('var(--tt-tone-brand-fg)');
  });

  it('只用令牌，没有写死颜色', () => {
    expect(/#[0-9a-fA-F]{3,8}(?![0-9a-fA-F])/.test(ALL)).toBe(false);
    expect(/\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i.test(ALL)).toBe(false);
    for (const decl of ALL.match(/border-radius:\s*[^;]+/g) ?? []) {
      expect(/var\(--tt-radius-|:\s*0\b|inherit/.test(decl), decl).toBe(true);
    }
  });
});
