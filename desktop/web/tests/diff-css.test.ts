import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// DiffView.css 的取值自测（合同 §2 样式、门禁 S4/S5 的同向自测）：读 CSS 文本，断言取值与出处注释。
const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const NL = String.fromCharCode(10);
const noComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
const hasRule = (css: string, selectorRe: RegExp, ...decls: RegExp[]) => {
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(noComments(css))) !== null) {
    if (selectorRe.test(m[1].trim().replace(/\s+/g, ' ')) && decls.every((d) => d.test(m[2]))) return true;
  }
  return false;
};

const css = read('src/components/DiffView.css');

describe('DiffView.css 关键取值', () => {
  it('根、工具栏、文件列表宽 260、折叠钮 24、文件头 36、二进制左内边距 40', () => {
    expect(css).toMatch(/\.tt-diff\s*\{[^}]*background:\s*var\(--tt-surface-1\)/);
    expect(css).toMatch(/\.tt-diff\s*\{[^}]*overflow:\s*hidden/);
    expect(css).toMatch(/\.tt-diff__files[^{]*\{[^}]*width:\s*260px/);
    expect(css).toMatch(/\.tt-diff__file-head \.tt-icon-btn[^{]*\{[^}]*width:\s*24px[^}]*height:\s*24px/);
    expect(css).toMatch(/\.tt-diff__file-head[^{]*\{[^}]*height:\s*36px/);
    expect(css).toMatch(/data-binary[^{]*\{[^}]*padding-left:\s*40px/);
  });

  it('两种 grid-template-columns 与行最小宽 560 / 760', () => {
    expect(css).toMatch(/grid-template-columns:\s*44px 44px 18px minmax\(0, 1fr\)/);
    expect(css).toMatch(/grid-template-columns:\s*44px 18px minmax\(0, 1fr\) 44px 18px minmax\(0, 1fr\)/);
    expect(css).toMatch(/min-width:\s*560px/);
    expect(css).toMatch(/min-width:\s*760px/);
  });

  it('换行关 pre、表格 max-content；换行开 pre-wrap 与 break-all', () => {
    expect(css).toMatch(/\.tt-diff__text\s*\{[^}]*white-space:\s*pre/);
    expect(css).toMatch(/\.tt-diff__table\s*\{[^}]*width:\s*max-content[^}]*min-width:\s*100%/);
    expect(css).toMatch(/data-wrap="true"\] \.tt-diff__text\s*\{[^}]*white-space:\s*pre-wrap[^}]*word-break:\s*break-all/);
  });

  it('add、del、hunk、empty 的底色令牌；hunk 文字 text-3；符号颜色与字重', () => {
    expect(css).toMatch(/data-kind="add"\]\s*\{[^}]*background:\s*var\(--tt-diff-add\)/);
    expect(css).toMatch(/data-kind="del"\]\s*\{[^}]*background:\s*var\(--tt-diff-del\)/);
    expect(hasRule(css, /data-kind="hunk"/, /background:\s*var\(--tt-surface-2\)/, /color:\s*var\(--tt-text-3\)/));
    expect(hasRule(css, /data-kind="empty"/, /background:\s*var\(--tt-surface-2\)/));
    expect(hasRule(css, /data-kind="add"\] \.tt-diff__sign/, /color:\s*var\(--tt-tone-success-fg\)/));
    expect(hasRule(css, /data-kind="del"\] \.tt-diff__sign/, /color:\s*var\(--tt-tone-danger-fg\)/));
    expect(css).toMatch(/\.tt-diff__sign\s*\{[^}]*font-weight:\s*600/);
  });

  it('列表路径 rtl 与里层 isolate；左侧文字格右边框；新行号格右边框', () => {
    expect(css).toMatch(/\.tt-diff__file-path\s*\{[^}]*direction:\s*rtl[^}]*text-align:\s*left/);
    expect(css).toMatch(/\.tt-diff__file-path\s*>\s*span\s*\{[^}]*direction:\s*ltr[^}]*unicode-bidi:\s*isolate/);
    expect(css).toMatch(/data-side="left"\]\.tt-diff__text\s*\{[^}]*border-right:\s*1px/);
    expect(css).toMatch(/\.tt-diff__no:nth-child\(2\)\s*\{[^}]*border-right:\s*1px/);
  });

  it('user-select: none 至少 3 条（行号、符号、eof）；eof 的 text-3 与 margin-left', () => {
    const n = (noComments(css).match(/user-select:\s*none/g) || []).length;
    expect(n).toBeGreaterThanOrEqual(3);
    expect(css).toMatch(/\.tt-diff__eof\s*\{[^}]*color:\s*var\(--tt-text-3\)[^}]*margin-left:\s*var\(--tt-space-1\)[^}]*user-select:\s*none/);
  });

  it('折叠钮规则特异性高于 IconButton 单类（.tt-diff__file-head .tt-icon-btn，(0,2,0)）', () => {
    expect(css).toMatch(/\.tt-diff__file-head \.tt-icon-btn\s*\{/);
  });

  it('除 0 与 1px 外的 px 字面量同一行带出处注释', () => {
    const problems: string[] = [];
    const raw = css.split(NL);
    noComments(css).split(NL).forEach((line, i) => {
      for (const m of line.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
        if (Math.abs(Number(m[1])) <= 1) continue;
        if (!/\/\*[^*]*(handoff|画布|领域板|组件板|详情页|Attempt|UI 文档|规划端定)[^*]*\*\//.test(raw[i])) {
          problems.push(`第 ${i + 1} 行的 ${m[0]} 没有出处注释`);
        }
      }
    });
    expect(problems).toEqual([]);
  });

  it('圆角、字体只用令牌', () => {
    for (const r of [/border-radius:\s*4px/, /font:\s*13px/, /font-family:\s*sans-serif/]) {
      expect(css).not.toMatch(r);
    }
  });
});
