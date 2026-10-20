import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// 第 4 片修补（T005 终审 S3、S4a、S4b、S6）的 CSS 侧自测：读 CSS 文本，断言取值与注释。
const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const NL = String.fromCharCode(10);
/** 去掉块注释（保留换行以维持行号），与门禁的 strip_comments 同向。 */
const noComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
const rules = (css: string) => {
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
};
const hasRule = (css: string, selectorRe: RegExp, ...decls: RegExp[]) =>
  rules(css).some((r) => selectorRe.test(r.selector) && decls.every((d) => d.test(r.body)));

describe('S3：表格焦点环（Table.css）', () => {
  const css = read('src/components/Table.css');

  it('数字列表头右对齐，特异性压得过 .tt-table th', () => {
    expect(css).toMatch(/\.tt-table th\.tt-num\s*\{\s*text-align:\s*right/);
    expect(css).toMatch(/\.tt-table th\s*\{[^}]*text-align:\s*left/);
  });

  it('容器 scroll-padding-top 32px，同一行注释写明表头高 32', () => {
    expect(css).toMatch(/\.tt-table-wrap\s*\{[^}]*scroll-padding-top:\s*32px/);
    const line = css.split(NL).find((l) => l.includes('scroll-padding-top:'));
    expect(line).toBeTruthy();
    expect(line!).toMatch(/表头高\s*32/);
  });

  it('行 focus-visible 去掉 outline，由单元格画 2px --tt-focus inset 阴影（首格加左、末格加右、只有一格画四边）', () => {
    expect(css).toMatch(/\.tt-table tbody tr:focus-visible\s*\{\s*outline:\s*none/);
    expect(hasRule(css, /\.tt-table tbody tr:focus-visible td$/,
      /box-shadow:[^;]*inset 0 2px 0 var\(--tt-focus\)[^;]*inset 0 -2px 0 var\(--tt-focus\)/));
    expect(hasRule(css, /\.tt-table tbody tr:focus-visible td:first-child$/, /inset 2px 0 0 var\(--tt-focus\)/));
    expect(hasRule(css, /\.tt-table tbody tr:focus-visible td:last-child$/, /inset -2px 0 0 var\(--tt-focus\)/));
    expect(hasRule(css, /\.tt-table tbody tr:focus-visible td:only-child$/, /inset 0 0 0 2px var\(--tt-focus\)/));
  });

  it('强制颜色模式的兜底；选中行的左 2px 主色留在 tr 上', () => {
    expect(css).toMatch(/@media\s*\(forced-colors:\s*active\)\s*\{[\s\S]*?tr:focus-visible\s*\{[^}]*outline:\s*2px solid Highlight[^}]*outline-offset:\s*-2px/);
    expect(hasRule(css, /data-selected/, /box-shadow:\s*inset 2px 0 0 var\(--tt-primary\)/));
  });

  it('带 px 的每一行都有同一行注释', () => {
    const problems: string[] = [];
    const raw = css.split(NL);
    noComments(css).split(NL).forEach((line, i) => {
      for (const m of line.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
        if (Math.abs(Number(m[1])) <= 1) continue;
        if (!/\/\*[^*]*\*\//.test(raw[i])) problems.push(`第 ${i + 1} 行的 ${m[0]} 没有同一行注释`);
      }
    });
    expect(problems).toEqual([]);
  });

  it('Table.tsx 不调 scrollIntoView，也不用下标 state 记当前行', () => {
    const tsx = read('src/components/Table.tsx');
    expect(tsx).not.toMatch(/\bscrollIntoView\b/);
    expect(tsx).not.toMatch(/useState\(\s*selectedIndex/);
  });
});

describe('S4a、S4b、S6：陈列页演示的 CSS', () => {
  const css = read('src/showcase/showcase-forms.css');

  it('表格容器限高仍在、限宽改成 280px，两项都注释「演示自定」，280 那项写明小于自然宽度（约 330）', () => {
    expect(hasRule(css, /\.showcase-table$/, /max-height:\s*240px/, /max-width:\s*280px/));
    const line = css.split(NL).find((l) => /max-width:\s*280px/.test(l));
    expect(line).toBeTruthy();
    expect(line!).toContain('演示自定');
    expect(line!).toContain('330');
    const height = css.split(NL).find((l) => /max-height:\s*240px/.test(l));
    expect(height!).toContain('演示自定');
  });

  it('输入框定宽 240px 带注释；胶囊行 justify-content: flex-end', () => {
    const field = css.split(NL).find((l) => /width:\s*240px/.test(l));
    expect(field).toBeTruthy();
    expect(field!).toMatch(/\/\*[^*]*(演示自定|画布|组件板|领域板|handoff|UI 文档)[^*]*\*\//);
    expect(hasRule(css, /\.showcase-pill-row$/, /justify-content:\s*flex-end/));
  });

  it('showcase-evidence.css 的 px 字面量都带同一行注释，摘要最大宽 880 注释写 handoff :165', () => {
    const evid = read('src/showcase/showcase-evidence.css');
    const problems: string[] = [];
    const raw = evid.split(NL);
    noComments(evid).split(NL).forEach((line, i) => {
      const m = /(?<![\w.#-])(-?\d*\.?\d+)px\b/.exec(line);
      if (m && Math.abs(Number(m[1])) > 1 && !/\/\*[^*]*(演示自定|handoff|领域板|组件板|Attempt|UI 文档)[^*]*\*\//.test(raw[i])) {
        problems.push(`第 ${i + 1} 行的 ${m[0]} 没有出处注释`);
      }
    });
    expect(problems).toEqual([]);
    const line = evid.split(NL).find((l) => /880px/.test(l));
    expect(line).toBeTruthy();
    expect(line!).toMatch(/handoff\s*:?\s*165/);
  });

  it('两份演示 CSS 的圆角、字体、阴影、层级只用令牌', () => {
    const problems: string[] = [];
    for (const rel of ['src/showcase/showcase-forms.css', 'src/showcase/showcase-evidence.css']) {
      for (const r of rules(read(rel))) {
        for (const d of r.body.split(';').map((x) => x.trim()).filter(Boolean)) {
          const idx = d.indexOf(':');
          if (idx < 0) continue;
          const prop = d.slice(0, idx).trim();
          const v = d.slice(idx + 1).replace(/\s+/g, '').toLowerCase();
          if (prop === 'z-index' && !v.startsWith('var(--tt-z-')) problems.push(`${rel}: ${r.selector} 的 z-index`);
          if (prop === 'border-radius' && !/^(var\(--tt-radius-[\w-]+\)|0|0px)+$|^inherit$/.test(v)) problems.push(`${rel}: ${r.selector} 的圆角`);
          if (prop === 'font' && !v.startsWith('var(--tt-')) problems.push(`${rel}: ${r.selector} 的字体`);
          if (prop === 'box-shadow' && v !== 'none' && !v.includes('var(--tt-')) problems.push(`${rel}: ${r.selector} 的阴影`);
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it('App.tsx 不引用 EvidenceShowcase（演示不挂到陈列页）', () => {
    expect(read('src/App.tsx')).not.toContain('EvidenceShowcase');
  });
});
