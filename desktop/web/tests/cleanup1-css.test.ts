// 样式表测试（T013 D05、D06、D08、D09）：指标卡纵向与色调条贴左缘、四张卡的图标颜色令牌、
// .rt-cmd 的 display block、attempt 行名称的等宽与单行省略；readonly1、readonly2 每份 CSS 都能从 src/main.tsx 到达。
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function css(rel: string): string {
  return readFileSync(resolve(process.cwd(), 'src/pages', rel), 'utf8');
}
const OVERVIEW = css('readonly1/overview-styles.css');
const RUNTIMES = css('readonly1/runtimes-styles.css');

/** 取某个选择器所在规则的声明文本（同一份文件里选择器唯一）。 */
function ruleOf(text: string, selector: string): string {
  const i = text.indexOf(selector);
  expect(i, `${selector} 的规则不在样式表里`).toBeGreaterThanOrEqual(0);
  const open = text.indexOf('{', i);
  const close = text.indexOf('}', open);
  return text.slice(open + 1, close);
}
/** 取文件里所有规则声明文本，按前导选择器里是否含 hook 过滤。 */
function rulesWith(text: string, hook: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(/\{([^{}]*)\}/g)) {
    const start = m.index ?? 0;
    const prelude = text.slice(text.lastIndexOf('}', start) + 1, start);
    if (prelude.includes(hook)) out.push(m[1]);
  }
  return out;
}

const CARD_TOKENS: [string, string][] = [
  ['running', '--tt-tone-info-fg'],
  ['review', '--tt-accent-text'],
  ['decide', '--tt-tone-escalate-fg'],
  ['integrate', '--tt-tone-brand-fg'],
];

describe('指标卡：纵向、色调条贴左缘、图标颜色', () => {
  it('卡片规则是 position relative、display flex、flex-direction column、gap --tt-space-0_5', () => {
    const rule = ruleOf(OVERVIEW, '.ov-metric {');
    expect(rule).toContain('position: relative');
    expect(rule).toContain('display: flex');
    expect(rule).toContain('flex-direction: column');
    expect(rule).toMatch(/gap:\s*var\(--tt-space-0_5\)/);
  });

  it('色调条规则是 position absolute，left/top/bottom 为 0，宽 3px', () => {
    const rule = ruleOf(OVERVIEW, '.ov-metric__bar {');
    expect(rule).toContain('position: absolute');
    expect(rule).toMatch(/left:\s*0/);
    expect(rule).toMatch(/top:\s*0/);
    expect(rule).toMatch(/bottom:\s*0/);
    expect(rule).toMatch(/width:\s*3px/);
  });

  it('四张卡的图标颜色规则各自只引用本卡的色调令牌', () => {
    for (const [metric, token] of CARD_TOKENS) {
      const bodies = rulesWith(OVERVIEW, `data-metric="${metric}"`).filter((b) => /(?:^|;)\s*color:/.test(b));
      expect(bodies.length, `${metric} 应有一条图标颜色规则`).toBeGreaterThan(0);
      const hit = bodies.find((b) => b.includes(`var(${token})`));
      expect(hit, `${metric} 的图标颜色应取 ${token}`).toBeTruthy();
      for (const [_m, other] of CARD_TOKENS) {
        if (other === token) continue;
        expect(hit, `${metric} 的图标颜色不该引用 ${other}`).not.toContain(`var(${other})`);
      }
    }
  });

  it('除 0 与 1px 外的 px 字面量同一行带出处注释', () => {
    for (const line of OVERVIEW.split('\n')) {
      const code = line.replace(/\/\*[^*]*\*\/?/g, '');
      for (const m of code.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
        if (Math.abs(Number(m[1])) === 1) continue;
        expect(line, `px 字面量 ${m[1]} 所在行应有出处注释：${line.trim()}`).toContain('/*');
      }
    }
  });
});

describe('CLI 运行时命令格与 attempt 行名称', () => {
  it('.rt-cmd 同一条规则有 display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm', () => {
    const rule = ruleOf(RUNTIMES, '.rt-cmd {');
    expect(rule).toContain('display: block');
    expect(rule).toContain('max-width: 280px');
    expect(rule).toContain('overflow: hidden');
    expect(rule).toContain('white-space: nowrap');
    expect(rule).toMatch(/font:\s*var\(--tt-mono-sm\)/);
  });

  it('.ov-row__name 用 --tt-mono-md，仍单行省略', () => {
    const rule = ruleOf(OVERVIEW, '.ov-row__name {');
    expect(rule).toMatch(/font:\s*var\(--tt-mono-md\)/);
    expect(rule).toContain('overflow: hidden');
    expect(rule).toContain('white-space: nowrap');
    expect(rule).toContain('text-overflow: ellipsis');
  });
});

const PAGE_CSS = [
  'pages/readonly1/common-section.css', 'pages/readonly1/overview-styles.css', 'pages/readonly1/roles-styles.css', 'pages/readonly1/runtimes-styles.css',
  'pages/readonly2/common-styles.css', 'pages/readonly2/secrets-styles.css', 'pages/readonly2/logs-styles.css', 'pages/readonly2/plugins-styles.css', 'pages/readonly2/history-styles.css',
];
const IMPORT_RE = /(?:\bimport|\bexport)\s*(?:type\s+)?(?:[^'"`;()]*?\bfrom\s*)?['"]([^'"]+)['"]/g;
const SUFFIXES = ['', '.ts', '.tsx', '.css', '/index.ts', '/index.tsx'];

/** src 下所有 .ts/.tsx/.css 的内容，键是相对 src 的路径。 */
function srcFiles(): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (dir: string, prefix: string) => {
    for (const name of readdirSync(dir)) {
      if (name === 'node_modules') continue;
      const full = resolve(dir, name);
      const rel = prefix ? `${prefix}/${name}` : name;
      if (statSync(full).isDirectory()) walk(full, rel);
      else if (/\.(?:ts|tsx|css)$/.test(name)) out[rel] = readFileSync(full, 'utf8');
    }
  };
  walk(resolve(process.cwd(), 'src'), '');
  return out;
}
function posixNormalize(dir: string, spec: string): string {
  const out: string[] = [];
  for (const part of (dir + spec).split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') { out.pop(); continue; }
    out.push(part);
  }
  return out.join('/');
}
/** 从 src/main.tsx 顺 import 能到达的文件（相对 src 的路径）。 */
function reachable(files: Record<string, string>): Set<string> {
  const seen = new Set<string>();
  const todo = ['main.tsx'];
  while (todo.length > 0) {
    const cur = todo.pop() as string;
    if (seen.has(cur) || !(cur in files)) continue;
    seen.add(cur);
    if (cur.endsWith('.css')) continue;
    const text = files[cur].replace(/\/\*[\s\S]*?\*\//g, '');
    for (const m of text.matchAll(IMPORT_RE)) {
      const spec = m[1];
      if (!spec.startsWith('.') || spec.includes('?')) continue;
      const base = posixNormalize(cur.replace(/[^/]*$/, ''), spec);
      for (const suffix of SUFFIXES) {
        if (base + suffix in files) { todo.push(base + suffix); break; }
      }
    }
  }
  return seen;
}

describe('样式表接线', () => {
  it('readonly1、readonly2 下每份 CSS 都能从 src/main.tsx 顺 import 到达', () => {
    const files = srcFiles();
    const reached = reachable(files);
    for (const name of PAGE_CSS) {
      expect(name in files, `${name} 应在 src/pages 下`).toBe(true);
      expect(reached.has(name), `${name} 从 src/main.tsx 出发到不了：样式表没进应用`).toBe(true);
    }
  });
});
