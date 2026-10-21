import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// 第 7 片静态自测（合同公共约定、门禁 S1–S5 的同向自测）：读源码与 CSS 文本，不渲染组件。
const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const stripComments = (text: string): string => {
  const noBlocks = text.replace(/\/\*[\s\S]*?\*\//g, '');
  return noBlocks.split('\n').filter((line) => !/^\s*\/\//.test(line)).join('\n');
};
const SRC = join(process.cwd(), 'src');
function walk(dir: string, exts: string[]): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(p, exts));
    else if (exts.some((e) => entry.name.endsWith(e))) out.push(p);
  }
  return out;
}
const FORBIDDEN_WORDS = ['dangerouslySetInnerHTML', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function',
  'document.write', 'srcdoc', 'createContextualFragment', 'DOMParser'];
const FORBIDDEN_CALLS = ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver'];
const NEW_SOURCES = ['src/components/DiffView.tsx', 'src/components/LogFollow.tsx',
  'src/components/diff/parseDiff.ts', 'src/components/diff/splitPairs.ts'];

describe('S2：src 全文没有禁用词', () => {
  it('所有 ts/tsx 都不出现禁用词', () => {
    const problems: string[] = [];
    for (const path of [...walk(join(SRC, 'components'), ['.ts', '.tsx']), ...walk(join(SRC, 'icons'), ['.ts', '.tsx']), ...walk(join(SRC, 'showcase'), ['.ts', '.tsx'])]) {
      const text = readFileSync(path, 'utf8');
      for (const word of FORBIDDEN_WORDS) if (text.includes(word)) problems.push(`${path} 出现 ${word}`);
    }
    expect(problems).toEqual([]);
  });
});

describe('S3：新组件与 diff/ 源码的禁区', () => {
  it('不出现 href、src=、target=，不渲染 role=status，不调四个禁用接口', () => {
    const problems: string[] = [];
    for (const rel of NEW_SOURCES) {
      const raw = read(rel);
      for (const word of ['href', 'src=', 'target=']) if (raw.includes(word)) problems.push(`${rel} 出现 ${word}`);
      const code = stripComments(raw);
      if (/role\s*[=:]\s*\{?\s*["']status["']/.test(code)) problems.push(`${rel} 渲染 role=status`);
      for (const name of FORBIDDEN_CALLS) if (new RegExp(`\\b${name}\\b`).test(code)) problems.push(`${rel} 调用 ${name}`);
    }
    const show = stripComments(read('src/showcase/DiffShowcase.tsx'));
    if (/role\s*[=:]\s*\{?\s*["']status["']/.test(show)) problems.push('DiffShowcase 渲染 role=status');
    for (const name of FORBIDDEN_CALLS) if (new RegExp(`\\b${name}\\b`).test(show)) problems.push(`DiffShowcase 调用 ${name}`);
    expect(problems).toEqual([]);
  });

  it('DiffView 用 useId、折叠用 hidden、不拼随机 id；补丁文字不自己写 ANSI', () => {
    const view = stripComments(read('src/components/DiffView.tsx'));
    expect(view).toMatch(/\buseId\b/);
    expect(view).toMatch(/\bhidden\b/);
    expect(view).not.toMatch(/Math\.random|Date\.now|new Date/);
    for (const rel of NEW_SOURCES) {
      expect(stripComments(read(rel)), rel).not.toMatch(/\\u001b|\\x1b|\\u009b|\\x9b|\\033/i);
    }
  });

  it('LogFollow 只用 setTimeout 计时、用 useLayoutEffect、不设 aria-live，常量 40 与 150 带 7.15 :910 注释', () => {
    const raw = read('src/components/LogFollow.tsx');
    const code = stripComments(raw);
    for (const word of ['requestAnimationFrame', 'performance.now', 'setInterval', 'aria-live']) expect(code).not.toContain(word);
    for (const word of ['setTimeout', 'clearTimeout', 'useLayoutEffect']) expect(code).toContain(word);
    for (const n of [40, 150]) {
      expect(raw, `常量 ${n} 应带 UI 文档 7.15 :910 注释`).toMatch(new RegExp(`\\b${n}\\b[^\\n]*(?://|/\\*)[^\\n]*7\\.15[^\\n]*910`));
    }
  });
});

describe('S1：模块导出与依赖', () => {
  it('parseDiff、splitPairs 是纯函数；DiffView、LogFollow 的导出与依赖', () => {
    expect(stripComments(read('src/components/diff/parseDiff.ts'))).toMatch(/export\s+function\s+parseDiff\b/);
    expect(stripComments(read('src/components/diff/splitPairs.ts'))).toMatch(/export\s+function\s+splitPairs\b/);
    for (const rel of ['src/components/diff/parseDiff.ts', 'src/components/diff/splitPairs.ts']) {
      expect(stripComments(read(rel)), rel).not.toMatch(/from\s+['"]react/);
    }
    const view = read('src/components/DiffView.tsx');
    expect(view).toMatch(/export\s+function\s+DiffView\b/);
    expect(view).toMatch(/export\s+interface\s+DiffViewProps\b/);
    expect(view).toContain('./diff/parseDiff');
    expect(view).toContain('./diff/splitPairs');
    expect(view).toMatch(/from\s+['"]\.\/evidence\/ansi['"]/);
    const log = read('src/components/LogFollow.tsx');
    expect(log).toMatch(/export\s+function\s+LogFollow\b/);
    expect(log).toMatch(/export\s+interface\s+LogFollowProps\b/);
    expect(log).toMatch(/from\s+['"]\.\/TextViewer['"]/);
  });

  it('index.ts 追加四个新导出、保持「共五片」；TextViewer 的 6 个可选属性都在', () => {
    const idx = read('src/components/index.ts');
    expect(idx).toContain('共五片');
    expect(idx).toContain('第 7 片：差异视图（7.14）与日志跟随（7.15）');
    for (const n of ['DiffView', 'DiffViewProps', 'LogFollow', 'LogFollowProps']) expect(idx).toContain(n);
    const props = /export\s+interface\s+TextViewerProps\s*\{([\s\S]*?)\n\}/.exec(stripComments(read('src/components/TextViewer.tsx')))!;
    for (const n of ['bodyRef', 'onBodyScroll', 'bodyClassName', 'headerExtra', 'bottomBar', 'filter']) {
      expect(props[1], n).toMatch(new RegExp(`\\b${n}\\?\\s*:`));
    }
  });
});

describe('S2：三个新图标', () => {
  const icons = read('src/icons/index.tsx');
  it('PauseIcon、FilterIcon、FileDiffIcon 的属性等于画布；追加段带「路径照画布」', () => {
    expect(icons).toContain('export const PauseIcon');
    expect(icons).toContain('export const FilterIcon');
    expect(icons).toContain('export const FileDiffIcon');
    const pause = icons.slice(icons.indexOf('export const PauseIcon'), icons.indexOf('export const FilterIcon'));
    expect(pause).toContain('<rect width="4" height="14" x="6" y="5" rx="1" />');
    expect(pause).toContain('<rect width="4" height="14" x="14" y="5" rx="1" />');
    const filter = icons.slice(icons.indexOf('export const FilterIcon'), icons.indexOf('export const FileDiffIcon'));
    expect(filter).toContain('points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"');
    const fd = icons.slice(icons.indexOf('export const FileDiffIcon'));
    expect(fd).toContain('d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"');
    expect(icons).toContain('路径照画布');
  });
});

describe('S5：新 CSS 只用令牌、px 字面量带注释', () => {
  const cssFiles = ['src/components/DiffView.css', 'src/components/LogFollow.css', 'src/showcase/showcase-diff.css'];
  it('圆角、字体、阴影、层级只用 --tt-* 令牌', () => {
    const problems: string[] = [];
    for (const rel of cssFiles) {
      for (const m of read(rel).matchAll(/([a-zA-Z-]+)\s*:\s*([^;{}]+)/g)) {
        const prop = m[1];
        const value = m[2].replace(/\s+/g, '').toLowerCase();
        if (prop === 'z-index' && !value.startsWith('var(--tt-z-')) problems.push(`${rel} z-index`);
        if (prop === 'border-radius' && !/^(var\(--tt-radius-[\w-]+\)|0|0px)+$|^inherit$/.test(value)) problems.push(`${rel} border-radius`);
        if (prop === 'box-shadow' && value !== 'none' && !value.includes('var(--tt-')) problems.push(`${rel} box-shadow`);
        if ((prop === 'font' || prop === 'font-family' || prop === 'font-size') && !(value.startsWith('var(--tt-') || value === 'inherit')) problems.push(`${rel} ${prop}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it('除 0 与 1px 外的 px 字面量同一行带注释', () => {
    const problems: string[] = [];
    for (const rel of cssFiles) {
      read(rel).split('\n').forEach((line, i) => {
        const code = line.replace(/\/\*[\s\S]*?\*\//g, '');
        for (const m of code.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
          if (Math.abs(Number(m[1])) <= 1) continue;
          if (!/\/\*[^*]*\*\//.test(line)) problems.push(`${rel}:${i + 1} 的 ${m[0]} 没有注释`);
        }
      });
    }
    expect(problems).toEqual([]);
  });
});

describe('W4 的坑', () => {
  it('新源码与 CSS 里没有十六进制颜色、颜色函数、拼接 --tt- 令牌名', () => {
    const hex = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/;
    const colorFn = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i;
    const files = [...NEW_SOURCES, 'src/components/DiffView.css', 'src/components/LogFollow.css',
      'src/showcase/DiffShowcase.tsx', 'src/showcase/showcase-diff.css'];
    const problems: string[] = [];
    for (const rel of files) {
      const text = read(rel).replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
      if (hex.test(text)) problems.push(`${rel} 有十六进制颜色`);
      if (colorFn.test(text)) problems.push(`${rel} 有颜色函数`);
      if (/[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{/.test(text)) problems.push(`${rel} 拼接 --tt- 令牌名`);
    }
    expect(problems).toEqual([]);
  });
});
