// 只读页面二的源码规则自测（合同 D11）：文件在位、页面接线、源码守卫、夹具只能是 .ts、内联 style 只在占比条。
// common-copy.ts 与 history-ActorTag.tsx 已由 T013 并进 src/components，不在本清单里。
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const R2 = 'src/pages/readonly2';
const MOCK = 'src/mock';
const PAGES = 'src/pages';

const R2_FILES = [
  'common-icons.tsx', 'common-format.ts', 'common-InfoNote.tsx', 'common-styles.css', 'common-readers.ts',
  'secrets-SecretsView.tsx', 'secrets-logic.ts', 'secrets-styles.css',
  'logs-LogsView.tsx', 'logs-SearchPanel.tsx', 'logs-SearchResults.tsx', 'logs-UsagePanel.tsx', 'logs-logic.ts', 'logs-styles.css',
  'plugins-PluginsView.tsx', 'plugins-PluginDrawer.tsx', 'plugins-logic.ts', 'plugins-styles.css',
  'history-HistoryView.tsx', 'history-HistoryDrawer.tsx', 'history-KeyDiff.tsx', 'history-logic.ts',
  'history-styles.css',
];
const MOCK_FILES = ['readonly2-search.ts', 'readonly2-history-entries.ts', 'readonly2-plugin-show.ts'];
const PAGE_FILES = ['SecretsPage.tsx', 'LogsPage.tsx', 'PluginsPage.tsx', 'HistoryPage.tsx'];

const FORBIDDEN = ['dangerouslySetInnerHTML', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function',
  'document.write', 'srcdoc', 'createContextualFragment', 'DOMParser'];
const NETWORK = ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket'];
const HEX = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/;
const COLOR_FUNC = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i;

function stripComments(text: string) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1');
}
const scanned = () => [
  ...R2_FILES.filter((f) => f.endsWith('.ts') || f.endsWith('.tsx')).map((f) => `${R2}/${f}`),
  ...MOCK_FILES.map((f) => `${MOCK}/${f}`),
  ...PAGE_FILES.map((f) => `${PAGES}/${f}`),
];

describe('D11 文件在位与页面接线', () => {
  it('readonly2 下 23 个源码与样式、mock 下 3 份夹具都在；没有子目录、没有 Page.tsx 文件名', () => {
    for (const f of [...R2_FILES, ...MOCK_FILES]) expect(existsSync(join(process.cwd(), R2, f)) || existsSync(join(process.cwd(), MOCK, f)), f).toBe(true);
    const entries = readdirSync(join(process.cwd(), R2), { withFileTypes: true });
    expect(entries.filter((e) => e.isDirectory())).toEqual([]);
    expect(entries.filter((e) => e.name.endsWith('Page.tsx'))).toEqual([]);
  });

  it('四个页面文件各含 PageFrame、默认导出、从 ./readonly2/ 引入视图，没有占位行', () => {
    const needs: Record<string, string> = { LogsPage: 'searchLogs', PluginsPage: 'getPlugin', HistoryPage: 'getHistoryEntry' };
    for (const name of PAGE_FILES) {
      const raw = read(`${PAGES}/${name}`);
      expect(raw, name).toContain('PageFrame');
      expect(raw, name).toMatch(/export\s+default\s+function\b|export\s+default\b/);
      expect(raw, name).toMatch(/from\s+['"]\.\/readonly2\//);
      expect(raw, name).not.toContain('夹具数据已读到');
      const stem = name.replace('Page.tsx', '');
      if (needs[stem]) {
        expect(raw, name).toContain(needs[stem]);
        expect(raw, name).toMatch(/['"]\.\/readonly2\/common-readers['"]/);
      }
    }
  });

  it('PageFrame 的 load 与 isEmpty 是模块级标识符；日志页不传 isEmpty；凭据页刷新钮叫重新检查', () => {
    const loads: Record<string, string> = {
      Secrets: 'listSecrets', Logs: 'getUsage', Plugins: 'getPlugins', History: 'getHistory',
    };
    for (const [stem, fn] of Object.entries(loads)) {
      const code = stripComments(read(`${PAGES}/${stem}Page.tsx`));
      const m = code.match(/\bload=\{\s*(\w+)\s*\}/);
      expect(m?.[1], stem).toBe(fn);
      const empty = code.match(/\bisEmpty=\{([^}]*)\}/);
      if (stem === 'Logs') {
        expect(empty, 'LogsPage 不传 isEmpty').toBeNull();
      } else {
        expect(empty, stem).toBeTruthy();
        expect(empty![1].trim(), stem).toMatch(/^[A-Za-z_]\w*$/);
      }
    }
    expect(read(`${PAGES}/SecretsPage.tsx`)).toMatch(/refreshLabel=(?:"重新检查"|'重新检查')/);
  });

  it('src/mock/ 仍恰有 14 份 JSON；src/pages/ 顶层仍恰有 9 个 *Page.tsx', () => {
    const jsons = readdirSync(join(process.cwd(), MOCK)).filter((f) => f.endsWith('.json'));
    expect(jsons).toHaveLength(14);
    const pages = readdirSync(join(process.cwd(), PAGES)).filter((f) => f.endsWith('Page.tsx'));
    expect(pages).toHaveLength(9);
  });
});

describe('D11 源码守卫', () => {
  it('禁用词、整词网络接口、role=status、禁用调用、ServerIcon、字体引用都不出现', () => {
    for (const rel of scanned()) {
      const raw = read(rel);
      const code = stripComments(raw);
      for (const w of FORBIDDEN) expect(raw.includes(w), `${rel} 出现 ${w}`).toBe(false);
      for (const w of NETWORK) {
        expect(new RegExp(`\\b${w}\\b`).test(raw), `${rel} 整词出现 ${w}`).toBe(false);
      }
      expect(/role\s*[=:]\s*\{?\s*["']status["']/.test(code), `${rel} role=status`).toBe(false);
      for (const name of ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver']) {
        expect(new RegExp(`\\b${name}\\b`).test(code), `${rel} 用了 ${name}`).toBe(false);
      }
      expect(raw.includes('ServerIcon'), `${rel} ServerIcon`).toBe(false);
      expect(raw, `${rel} 字体扩展名`).not.toMatch(/\.(?:woff2?|ttf|otf|eot|ttc|otc)\b/i);
      expect(raw.includes('sarasa-mono-sc-'), `${rel} 随包字体`).toBe(false);
      expect(raw.includes('@font-face'), `${rel} @font-face`).toBe(false);
      expect(raw, `${rel} FontFace`).not.toMatch(/\bFontFace\b|document\.fonts/);
      const body = raw.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
      body.split('\n').forEach((line, i) => {
        expect(HEX.test(line), `${rel}:${i + 1} 井号加十六进制`).toBe(false);
        expect(COLOR_FUNC.test(line), `${rel}:${i + 1} 颜色函数`).toBe(false);
      });
    }
  });

  it('readonly2 的源码不写 data-page-state、不渲染 h1、不用 Intl、对 api.ts 只 import type', () => {
    for (const f of R2_FILES) {
      if (!f.endsWith('.ts') && !f.endsWith('.tsx')) continue;
      const rel = `${R2}/${f}`;
      const code = stripComments(read(rel));
      expect(/\bdata-page-state\s*=|["']data-page-state["']\s*:/.test(code), `${rel} data-page-state`).toBe(false);
      expect(/<h1\b/.test(code), `${rel} h1`).toBe(false);
      expect(/\btoLocaleString\b|\bIntl\./.test(code), `${rel} Intl`).toBe(false);
      for (const m of code.matchAll(/import\s+([^;]*?)\s+from\s+['"]((?:\.\.\/)+api)['"]/g)) {
        const spec = m[1].trim();
        const items = spec.startsWith('{') ? spec.trim('{} \n').split(',').map((s) => s.trim()).filter(Boolean) : [];
        const typeOnly = spec.startsWith('type ') || (items.length > 0 && items.every((s) => s.startsWith('type ')));
        expect(typeOnly, `${rel} 直接调 api.ts：${m[0].slice(0, 60)}`).toBe(true);
      }
    }
    const readers = stripComments(read(`${R2}/common-readers.ts`));
    for (const name of ['searchLogs', 'getHistoryEntry', 'getPlugin']) {
      expect(readers, name).toMatch(new RegExp(`export\\s+(?:async\\s+)?(?:function|const)\\s+${name}\\b`));
    }
  });

  it('夹具标「示意」；common-icons 的 fill 与 stroke 只用 none 与 currentColor', () => {
    for (const f of MOCK_FILES) expect(read(`${MOCK}/${f}`)).toContain('示意');
    const icons = read(`${R2}/common-icons.tsx`);
    expect(icons).toMatch(/export\s+(?:const|function)\s+ExternalLinkIcon\b/);
    const bad = Array.from(icons.matchAll(/\b(?:fill|stroke)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']([^"']*)["']\s*\})/g))
      .map((m) => m[1] || m[2] || m[3])
      .filter((v) => v !== 'none' && v !== 'currentColor');
    expect(bad).toEqual([]);
  });

  it('内联 style 只出现在 logs-UsagePanel.tsx', () => {
    for (const rel of scanned()) {
      const code = stripComments(read(rel));
      if (/\bstyle\s*=/.test(code)) expect(rel.endsWith('logs-UsagePanel.tsx'), rel).toBe(true);
    }
    expect(/\bstyle\s*=/.test(stripComments(read(`${R2}/logs-UsagePanel.tsx`)))).toBe(true);
  });
});
