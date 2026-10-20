import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// 静态检查（合同公共约定、门禁 S2–S5 的同向自测）：读源码与 CSS 文本，不渲染组件。
const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
/** 去块注释与整行 // 注释（保留换行以维持行号），与门禁的 strip_ts_comments 同向。 */
function stripComments(text: string): string {
  const noBlocks = text.replace(/\/\*[\s\S]*?\*\//g, '');
  const lines = noBlocks.split('\n').filter((line) => !/^\s*\/\//.test(line));
  return lines.join('\n');
}
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

const NEW_COMPONENTS = ['TextViewer', 'SafeMarkdown', 'EffortPair', 'MaskedValue', 'CommandLine', 'NextStep'];
const OLD_COMPONENTS = ['Button', 'Tag', 'StatusTag', 'Card', 'Banner', 'IconButton', 'Tooltip', 'Menu', 'Dialog', 'Drawer',
  'Toast', 'SegmentedControl', 'Switch', 'Checkbox', 'Tabs', 'TextField', 'Select', 'Table', 'KeyValueList', 'EmptyState',
  'Skeleton', 'ConnectionPill', 'Breadcrumb'];
const FORBIDDEN_WORDS = ['dangerouslySetInnerHTML', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function',
  'document.write', 'srcdoc', 'createContextualFragment', 'DOMParser'];
const FORBIDDEN_CALLS = ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver'];

function tsFiles() {
  return [...walk(join(SRC, 'components'), ['.ts', '.tsx']), ...walk(join(SRC, 'icons'), ['.ts', '.tsx']),
    ...walk(join(SRC, 'showcase'), ['.ts', '.tsx'])];
}

describe('S2：src 全文没有禁用词', () => {
  it('八个新文件与既有源码都不出现禁用词', () => {
    const problems: string[] = [];
    for (const path of tsFiles()) {
      const text = readFileSync(path, 'utf8');
      for (const word of FORBIDDEN_WORDS) {
        if (text.includes(word)) problems.push(`${path} 出现 ${word}`);
      }
    }
    expect(problems).toEqual([]);
  });
});

describe('S3：新组件与 evidence/ 源码的禁区', () => {
  const files = [...NEW_COMPONENTS.flatMap((n) => [join(SRC, 'components', `${n}.tsx`), join(SRC, 'components', `${n}.css`)]),
    join(SRC, 'components', 'evidence', 'ansi.ts'), join(SRC, 'components', 'evidence', 'viewerLines.ts'),
    join(SRC, 'components', 'evidence', 'markdown.ts')];

  it('六个新组件与 evidence/ 的源码都在', () => {
    for (const path of files) expect(() => statSync(path)).not.toThrow();
  });

  it('不出现 href、src=、target=，不渲染 role=status，不调四个禁用接口', () => {
    const problems: string[] = [];
    for (const path of files) {
      if (!path.endsWith('.tsx') && !path.endsWith('.ts')) continue;
      const raw = readFileSync(path, 'utf8');
      const label = path.split('src')[1];
      for (const word of ['href', 'src=', 'target=']) {
        if (raw.includes(word)) problems.push(`${label} 出现 ${word}`);
      }
      const code = stripComments(raw);
      if (/role\s*[=:]\s*\{?\s*["']status["']/.test(code)) problems.push(`${label} 渲染了 role=status`);
      for (const name of FORBIDDEN_CALLS) {
        if (new RegExp(`\\b${name}\\b`).test(code)) problems.push(`${label} 调用了 ${name}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it('evidence/markdown.ts 不引入 React，导出 parseMarkdown；ansi.ts 导出 stripAnsi', () => {
    const md = stripComments(read('src/components/evidence/markdown.ts'));
    expect(md).not.toMatch(/from\s+['"]react/);
    expect(md).toMatch(/export\s+function\s+parseMarkdown\b/);
    expect(read('src/components/evidence/ansi.ts')).toMatch(/export\s+function\s+stripAnsi\b/);
  });

  it('W4 的坑：新源码里没有十六进制颜色形态、颜色函数形态，也不拼接 --tt- 令牌名', () => {
    const hex = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/;
    const colorFn = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i;
    const problems: string[] = [];
    for (const path of files) {
      const text = readFileSync(path, 'utf8').replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
      const label = path.split('src')[1];
      if (hex.test(text)) problems.push(`${label} 有十六进制颜色形态`);
      if (colorFn.test(text)) problems.push(`${label} 有颜色函数形态`);
      if (/[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{/.test(text)) problems.push(`${label} 拼接了 --tt- 令牌名`);
    }
    expect(problems).toEqual([]);
  });
});

describe('S1：index.ts 的导出', () => {
  const text = stripComments(read('src/components/index.ts'));
  const names = new Set<string>();
  for (const m of text.matchAll(/export\s+(?:type\s+)?\{([^}]*)\}/g)) {
    for (const part of m[1].split(',')) {
      const p = part.replace(/^\s*type\s+/, '').trim();
      if (p) names.add(p.split(' as ').pop()!.trim());
    }
  }

  it('导出六个新组件与两个函数，原来的 23 个组件与 Props 类型仍在', () => {
    for (const comp of [...OLD_COMPONENTS, ...NEW_COMPONENTS]) {
      expect(names.has(comp), comp).toBe(true);
      expect(names.has(`${comp}Props`), `${comp}Props`).toBe(true);
    }
    expect(names.has('isMaskedPlaceholder')).toBe(true);
    expect(names.has('dispatchCommand')).toBe(true);
  });

  it('文件头注释写成五片；不导出内部模块 overlay/ 与 evidence/ 的纯函数', () => {
    const raw = read('src/components/index.ts');
    expect(raw).toMatch(/共五片/);
    expect(text).not.toMatch(/overlay/);
    expect(text).not.toMatch(/evidence\/|ansi|viewerLines/);
    expect(text).not.toMatch(/stripAnsi|parseMarkdown|pagesToLines/);
  });
});

describe('S4：三个新图标的路径', () => {
  const icons = read('src/icons/index.tsx');
  const block = (name: string) => {
    const m = new RegExp(`export\\s+const\\s+${name}\\b`).exec(icons);
    expect(m, name).not.toBeNull();
    const nxt = new RegExp('\\nexport\\s+(?:const|function|type|interface)\\b').exec(icons.slice(m!.index + 1));
    return icons.slice(m!.index, m!.index + 1 + (nxt ? nxt.index : icons.length - m!.index - 1));
  };

  it('LockIcon、CopyIcon 的 rect 属性与 path d 等于领域板 :404、:409；EyeOffIcon 四条 path', () => {
    const lock = block('LockIcon');
    expect(lock).toContain('<rect width="18" height="11" x="3" y="11" rx="2" ry="2" />');
    expect(lock).toContain('d="M7 11V7a5 5 0 0 1 10 0v4"');
    const copy = block('CopyIcon');
    expect(copy).toContain('<rect width="14" height="14" x="8" y="8" rx="2" ry="2" />');
    expect(copy).toContain('d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"');
    const eye = block('EyeOffIcon');
    expect(eye).not.toContain('<rect');
    const ds = [...eye.matchAll(/d="([^"]*)"/g)].map((m) => m[1]);
    expect(ds).toEqual([
      'M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49',
      'M14.084 14.158a3 3 0 0 1-4.242-4.242',
      'M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143',
      'm2 2 20 20',
    ]);
    for (const name of ['LockIcon', 'CopyIcon', 'EyeOffIcon']) expect(block(name)).toContain('<Svg');
  });
});

describe('S5：新 CSS 只用令牌，px 字面量带同一行注释', () => {
  const cssFiles = NEW_COMPONENTS.map((n) => `src/components/${n}.css`);

  it('层级、圆角、阴影、字体只用 --tt-* 令牌', () => {
    const problems: string[] = [];
    for (const rel of cssFiles) {
      const css = read(rel);
      for (const m of css.matchAll(/([a-zA-Z-]+)\s*:\s*([^;{}]+)/g)) {
        const prop = m[1];
        const value = m[2].replace(/\s+/g, '').toLowerCase();
        if (prop === 'z-index' && !value.startsWith('var(--tt-z-')) problems.push(`${rel} 的 z-index 用了 ${m[2]}`);
        if (prop === 'border-radius' && !/^(var\(--tt-radius-[\w-]+\)|0|0px)+$|^inherit$/.test(value)) {
          problems.push(`${rel} 的 border-radius 用了 ${m[2]}`);
        }
        if (prop === 'box-shadow' && value !== 'none' && !value.includes('var(--tt-')) problems.push(`${rel} 的 box-shadow 用了 ${m[2]}`);
        if ((prop === 'font' || prop === 'font-family' || prop === 'font-size') && !(value.startsWith('var(--tt-') || value === 'inherit')) {
          problems.push(`${rel} 的 ${prop} 用了 ${m[2]}`);
        }
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
          if (!/\/\*[^*]*\*\//.test(line)) problems.push(`${rel}:${i + 1} 的 ${m[0]} 没有同一行注释`);
        }
      });
    }
    expect(problems).toEqual([]);
  });
});
