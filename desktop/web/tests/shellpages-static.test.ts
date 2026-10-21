// 执行端测试（D11、D12）：源码守卫、文件名单、图标路径、样式出处与接线。
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(process.cwd(), 'src');
const SP = join(SRC, 'shellpages');

function read(rel: string): string {
  return readFileSync(join(process.cwd(), rel), 'utf8');
}
function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}
function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/gm, '$1');
}

const NEW_TS = walk(SP).filter((p) => p.endsWith('.ts') || p.endsWith('.tsx'));

describe('D11 源码守卫', () => {
  it('shellpages 下没有网络请求词（整词）', () => {
    const RE = /(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])/;
    const hits: string[] = [];
    for (const f of NEW_TS) {
      readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
        if (RE.test(line)) hits.push(`${relative(process.cwd(), f)}:${i + 1}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it('没有危险 HTML 与禁用调用，不写 data-theme、role=status、内联 style、存储、window.open、themisHost', () => {
    const problems: string[] = [];
    for (const f of NEW_TS) {
      const code = stripComments(readFileSync(f, 'utf8'));
      const label = relative(process.cwd(), f);
      for (const w of ['dangerouslySetInnerHTML', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.write', 'srcdoc', 'DOMParser']) {
        if (code.includes(w)) problems.push(`${label}: ${w}`);
      }
      if (/role\s*[=:]\s*\{?\s*["']status["']/.test(code)) problems.push(`${label}: role=status`);
      for (const c of ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver']) {
        if (new RegExp(`\\b${c}\\b`).test(code)) problems.push(`${label}: ${c}`);
      }
      if (code.includes('data-theme')) problems.push(`${label}: data-theme`);
      if (/\bstyle\s*=\s*[{"']/.test(code)) problems.push(`${label}: 内联 style`);
      for (const w of ['localStorage', 'sessionStorage', 'themisHost', 'ServerIcon']) {
        if (new RegExp(`\\b${w}\\b`).test(code)) problems.push(`${label}: ${w}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it('shellpages 与 SettingsPage 不导入 api 模块', () => {
    const files = [...NEW_TS, join(SRC, 'pages', 'SettingsPage.tsx')].filter(existsSync);
    const problems: string[] = [];
    for (const f of files) {
      const specs = [...stripComments(readFileSync(f, 'utf8')).matchAll(/from\s*['"]([^'"]+)['"]/g)].map((m) => m[1]);
      for (const s of specs) if (/(^|\/)api(\.ts)?$/.test(s)) problems.push(`${relative(process.cwd(), f)}: ${s}`);
    }
    expect(problems).toEqual([]);
  });

  it('shellpages 里不用 *Page.tsx、*Showcase.tsx、DiffView*、LogFollow*；SettingsView 不拆分', () => {
    const problems: string[] = [];
    for (const e of readdirSync(SP)) {
      if (/Page\.tsx$|Showcase\.tsx$|^DiffView|^LogFollow/.test(e)) problems.push(e);
      if (/^SettingsView.+\.tsx?$/.test(e)) problems.push(e);
    }
    expect(problems).toEqual([]);
  });
});

describe('D11 图标路径', () => {
  it('icons.tsx 导出三个新图标，包装含 tt-i、currentColor、aria-hidden', () => {
    const text = read('src/shellpages/icons.tsx');
    for (const name of ['ArrowRightIcon', 'FileTextIcon', 'ExternalLinkIcon']) {
      expect(text, name).toContain(`export const ${name}`);
    }
    expect(text).toContain('tt-i');
    expect(text).toContain('currentColor');
    expect(text).toContain('aria-hidden');
  });
});

describe('D12 样式出处与接线', () => {
  it('每份新 css 的 px 字面量（除 0、1）同一行有出处注释', () => {
    const problems: string[] = [];
    for (const name of ['shell-window.css', 'first-run.css', 'service-status.css', 'settings.css']) {
      const raw = read(`src/shellpages/${name}`);
      let inComment = false;
      raw.split('\n').forEach((line, no) => {
        let code = '';
        let sawComment = inComment;
        let i = 0;
        while (i < line.length) {
          if (inComment) {
            const end = line.indexOf('*/', i);
            if (end < 0) {
              i = line.length;
            } else {
              inComment = false;
              i = end + 2;
            }
            continue;
          }
          if (line.startsWith('/*', i)) {
            inComment = true;
            sawComment = true;
            i += 2;
            continue;
          }
          code += line[i];
          i += 1;
        }
        for (const m of code.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
          if (Math.abs(parseFloat(m[1])) === 0 || Math.abs(parseFloat(m[1])) === 1) continue;
          if (!sawComment) problems.push(`${name}:${no + 1}: ${m[0]}`);
        }
      });
    }
    expect(problems).toEqual([]);
  });

  it('新 css 只用 --tt- 令牌，不写 [data-theme] 选择器，不在 css 里声明 --tt-', () => {
    const defined = new Set([...read('src/styles/tokens.css').matchAll(/(--tt-[A-Za-z0-9_-]+)\s*:/g)].map((m) => m[1]));
    const problems: string[] = [];
    for (const name of ['shell-window.css', 'first-run.css', 'service-status.css', 'settings.css']) {
      const text = read(`src/shellpages/${name}`).replace(/\/\*[\s\S]*?\*\//g, '');
      for (const m of text.matchAll(/(--tt-[A-Za-z0-9_-]+)(\s*:)?/g)) {
        if (m[2]) problems.push(`${name}: 声明 ${m[1]}`);
        else if (!defined.has(m[1])) problems.push(`${name}: 未定义 ${m[1]}`);
      }
      if (/\[\s*data-theme/.test(text)) problems.push(`${name}: [data-theme] 选择器`);
    }
    expect(problems).toEqual([]);
  });

  it('接线：每份新 css 被某个视图 import，各视图 import 自己的 css', () => {
    const own: Record<string, string> = {
      'ShellWindow.tsx': 'shell-window.css',
      'FirstRunView.tsx': 'first-run.css',
      'ServiceStatusView.tsx': 'service-status.css',
      'SettingsView.tsx': 'settings.css',
    };
    const problems: string[] = [];
    for (const [view, css] of Object.entries(own)) {
      const text = read(`src/shellpages/${view}`);
      if (!text.includes(`'./${css}'`)) problems.push(`${view} 没有 import ${css}`);
    }
    expect(problems).toEqual([]);
  });
});
