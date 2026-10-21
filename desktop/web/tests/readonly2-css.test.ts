// 只读页面二的 CSS 取值自测（合同 D10）：宽表最小宽、占比条、mark、KeyDiff、抽屉 dl 与资源表、检索表单与结果区，
// 以及令牌与 px 注释、内联 style 只在占比条、Drawer.css 的 top。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const R2 = 'src/pages/readonly2';
const CSS_FILES = [
  `${R2}/common-styles.css`,
  `${R2}/secrets-styles.css`,
  `${R2}/logs-styles.css`,
  `${R2}/plugins-styles.css`,
  `${R2}/history-styles.css`,
];
const NL = String.fromCharCode(10);
const noComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));

function rules(css: string) {
  const out: { selector: string; body: string }[] = [];
  const stripped = noComments(css);
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(stripped)) !== null) {
    const selector = m[1].trim().replace(/\s+/g, ' ');
    if (selector.startsWith('@')) continue;
    out.push({ selector, body: m[2] });
  }
  return out;
}
const all = CSS_FILES.map((f) => read(f)).join(NL);
const hasRule = (selectorRe: RegExp, ...decls: RegExp[]) =>
  rules(all).some((r) => selectorRe.test(r.selector) && decls.every((d) => d.test(r.body)));

describe('D10 样式取值', () => {
  it('宽表最小宽 720/860/900/1000 写在 .tt-table 上', () => {
    for (const width of [720, 860, 900, 1000]) {
      expect(hasRule(/\.tt-table(?![\w-])/, new RegExp(`min-width:\\s*${width}px`)), String(width)).toBe(true);
    }
  });

  it('占比条：轨道高 8、radius-full、surface-3 底、最小宽 60；填充 navy-500；百分比文字宽 44', () => {
    expect(hasRule(/./, /height:\s*8px/, /border-radius:\s*var\(--tt-radius-full\)/, /background:\s*var\(--tt-surface-3\)/, /min-width:\s*60px/)).toBe(true);
    expect(hasRule(/./, /background:\s*var\(--tt-navy-500\)/)).toBe(true);
    expect(hasRule(/./, /width:\s*44px/)).toBe(true);
  });

  it('mark：highlight 底、text-1 字、radius-sm、内边距 0 1px', () => {
    expect(hasRule(/(?<![\w.#-])mark(?![\w-])/, /background:\s*var\(--tt-highlight\)/, /color:\s*var\(--tt-text-1\)/,
      /border-radius:\s*var\(--tt-radius-sm\)/, /padding:\s*0\s+1px/)).toBe(true);
  });

  it('KeyDiff：del/add 底色、值块 mono-sm + radius-sm + 1px space-1、键 break-all', () => {
    expect(hasRule(/./, /background:\s*var\(--tt-diff-del\)/)).toBe(true);
    expect(hasRule(/./, /background:\s*var\(--tt-diff-add\)/)).toBe(true);
    expect(hasRule(/./, /font:\s*var\(--tt-mono-sm\)/, /border-radius:\s*var\(--tt-radius-sm\)/,
      /padding:\s*1px\s+var\(--tt-space-1\)/)).toBe(true);
    expect(hasRule(/./, /word-break:\s*break-all/)).toBe(true);
  });

  it('抽屉 dl 两列 96px minmax(0, 1fr)、间距 space-1 space-3；资源表三列、表头 32、行 36', () => {
    expect(hasRule(/./, /grid-template-columns:\s*96px\s+minmax\(0,\s*1fr\)/, /gap:\s*var\(--tt-space-1\)\s+var\(--tt-space-3\)/)).toBe(true);
    expect(hasRule(/./, /grid-template-columns:\s*minmax\(0,\s*1fr\)\s+120px\s+64px/)).toBe(true);
    expect(hasRule(/./, /(height|min-height):\s*32px/)).toBe(true);
    expect(hasRule(/./, /(height|min-height):\s*36px/)).toBe(true);
  });

  it('小节卡、检索表单卡、结果头与组头、摘录、合计数字、说明条、带图标的标签', () => {
    expect(hasRule(/./, /background:\s*var\(--tt-surface-1\)/, /border:\s*1px\s+solid\s+var\(--tt-border\)/,
      /border-radius:\s*var\(--tt-radius-lg\)/, /padding:\s*var\(--tt-space-3\)\s+var\(--tt-space-4\)/)).toBe(true);
    expect(hasRule(/./, /font:\s*var\(--tt-title-sm\)/)).toBe(true);
    expect(hasRule(/./, /display:\s*flex/, /flex-wrap:\s*wrap/, /gap:\s*var\(--tt-space-3\)/,
      /padding:\s*var\(--tt-space-3\)\s+var\(--tt-space-4\)/)).toBe(true);
    expect(hasRule(/./, /flex:\s*1\s+1\s+320px/)).toBe(true);
    expect(hasRule(/./, /width:\s*200px/)).toBe(true);
    expect(hasRule(/./, /width:\s*96px/)).toBe(true);
    expect(hasRule(/./, /padding:\s*var\(--tt-space-2\)\s+var\(--tt-space-4\)/)).toBe(true);
    expect(hasRule(/./, /(height|min-height):\s*32px/, /background:\s*var\(--tt-surface-2\)/)).toBe(true);
    expect(hasRule(/./, /font:\s*var\(--tt-mono-md\)/, /white-space:\s*pre/)).toBe(true);
    expect(hasRule(/./, /text-overflow:\s*ellipsis/)).toBe(true);
    expect(hasRule(/./, /font:\s*var\(--tt-mono-sm\)/, /color:\s*var\(--tt-text-2\)/)).toBe(true);
    expect(hasRule(/./, /min-width:\s*0/)).toBe(true);
    expect(hasRule(/./, /font:\s*var\(--tt-display\)/)).toBe(true);
    expect(hasRule(/./, /background:\s*var\(--tt-tone-info-bg\)/, /color:\s*var\(--tt-tone-info-fg\)/,
      /border-radius:\s*var\(--tt-radius-md\)/)).toBe(true);
    expect(hasRule(/./, /gap:\s*var\(--tt-space-1\)/)).toBe(true);
  });

  it('grid 里没有裸的 1fr', () => {
    for (const f of CSS_FILES) {
      for (const r of rules(read(f))) {
        if (!/grid-template/.test(r.body)) continue;
        expect(r.body.replace(/minmax\(0,\s*1fr\)/g, ''), `${f} ${r.selector}`).not.toContain('1fr');
      }
    }
  });

  it('除 0 与 1px 外的 px 字面量同一行带出处注释；没有写死颜色与颜色函数', () => {
    for (const f of CSS_FILES) {
      const raw = read(f);
      raw.split(NL).forEach((line, i) => {
        const code = noComments(line);
        const sawComment = line !== code;
        for (const m of code.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
          if (Math.abs(parseFloat(m[1])) === 0 || Math.abs(parseFloat(m[1])) === 1) continue;
          expect(sawComment, `${f}:${i + 1} ${m[0]} 没有出处注释`).toBe(true);
        }
        expect(code, `${f}:${i + 1}`).not.toMatch(/#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/);
        expect(code, `${f}:${i + 1}`).not.toMatch(/\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i);
      });
    }
  });

  it('z-index、圆角、阴影、字体只用令牌', () => {
    for (const f of CSS_FILES) {
      for (const r of rules(read(f))) {
        for (const decl of r.body.split(';')) {
          const idx = decl.indexOf(':');
          if (idx < 0) continue;
          const name = decl.slice(0, idx).trim().toLowerCase();
          const value = decl.slice(idx + 1).trim().toLowerCase();
          if (name === 'z-index') expect(value.startsWith('var(--tt-z-'), `${f} ${r.selector}`).toBe(true);
          if (name === 'border-radius') {
            expect(value.replace(/var\(--tt-radius-[\w-]+\)|0|0px/g, '').trim(), `${f} ${r.selector}`).toBe('');
          }
          if (name === 'box-shadow' && value !== 'none') expect(value).toContain('var(--tt-');
          if (['font', 'font-family', 'font-size'].includes(name)) {
            expect(value.startsWith('var(--tt-') || value === 'inherit', `${f} ${r.selector} ${name}`).toBe(true);
          }
        }
      }
    }
  });
});

describe('Q3 Drawer.css 的 top', () => {
  it('top 为 40px 且同一行带出处注释；文件头写出 40、不再写「顶边取 0」', () => {
    const raw = read('src/components/Drawer.css');
    const rule = rules(raw).find((r) => r.selector === '.tt-drawer');
    expect(rule).toBeTruthy();
    expect(rule!.body).toMatch(/top:\s*40px/);
    expect(rule!.body).toMatch(/position:\s*fixed/);
    expect(rule!.body).toMatch(/right:\s*0/);
    expect(rule!.body).toMatch(/bottom:\s*var\(--tt-tabbar-height\)/);
    expect(rule!.body).toMatch(/width:\s*520px/);
    expect(rule!.body).toMatch(/max-width:\s*60%/);
    expect(rule!.body).toMatch(/z-index:\s*var\(--tt-z-drawer\)/);
    const topLine = raw.split(NL).find((l) => /^\s*top\s*:/.test(l)) as string;
    expect(topLine).toContain('40px');
    expect(topLine).toMatch(/\/\*.+\*\//);
    const header = raw.split(/^\.tt-drawer\s*\{/m)[0];
    expect(header).not.toContain('顶边取 0');
    expect(header).not.toContain('本片没有标题栏');
    expect(header).toContain('40');
  });
});
