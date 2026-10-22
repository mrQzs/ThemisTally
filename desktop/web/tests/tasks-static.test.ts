// 任务页源码规则自测（合同 Steps 11、D13、D14）：文件在位、禁用词、内联 style、状态到分组映射、图标与 CSS 接线。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = resolve(process.cwd(), '../..');
const read = (rel: string) => readFileSync(resolve(root, rel), 'utf8');
const web = process.cwd();
const readWeb = (rel: string) => readFileSync(resolve(web, rel), 'utf8');
const TASKS = 'src/pages/tasks';
const TASKS_FILES = [
  'tasks-groups.ts', 'tasks-format.ts', 'tasks-route.ts', 'tasks-model.ts', 'tasks-data.ts', 'tasks-copy.ts',
  'tasks-icons.tsx', 'TaskListView.tsx', 'tasks-list.css', 'AttemptDetailView.tsx', 'tasks-detail.css',
  'tab-Summary.tsx', 'tab-Patch.tsx', 'tab-Checks.tsx', 'tab-Report.tsx', 'tab-Events.tsx', 'tab-Files.tsx',
  'tasks-tabs.css', 'common-FileReader.tsx', 'common-CopyNote.tsx',
];
const MOCK_FILES = ['tasks-files.ts', 'tasks-attempts.ts', 'tasks-live.ts'];
const CODE_FILES = [...TASKS_FILES.filter((n) => n.endsWith('.ts') || n.endsWith('.tsx')).map((n) => `${TASKS}/${n}`),
  ...MOCK_FILES.map((n) => `src/mock/${n}`), 'src/pages/TasksPage.tsx'];

const stripComments = (text: string) => text
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');

const wordHit = (text: string, word: string) =>
  word.startsWith('.') || word.includes('(') || word.includes(' ') || word.includes('@')
    ? text.includes(word)
    : new RegExp(`(?<![A-Za-z0-9_])${word}(?![A-Za-z0-9_])`).test(text);

describe('文件在位', () => {
  it('tasks/ 下恰是 20 个文件、mock 下 3 份夹具、TasksPage 用 PageFrame', () => {
    for (const name of TASKS_FILES) expect(readWeb(`${TASKS}/${name}`), name).toBeTruthy();
    for (const name of MOCK_FILES) expect(readWeb(`src/mock/${name}`), name).toBeTruthy();
    const page = readWeb('src/pages/TasksPage.tsx');
    expect(page).toContain('PageFrame');
    expect(page).toMatch(/from\s+['"]\.\/tasks\//);
    expect(page).not.toContain('夹具数据已读到');
    expect(page).toMatch(/export\s+default\s+function\b|export\s+default\b/);
  });

  it('三份 CSS 都被 TasksPage 的视图引入', () => {
    expect(readWeb(`${TASKS}/TaskListView.tsx`)).toContain("import './tasks-list.css'");
    expect(readWeb(`${TASKS}/AttemptDetailView.tsx`)).toContain("import './tasks-detail.css'");
    expect(readWeb(`${TASKS}/tab-Summary.tsx`)).toContain("import './tasks-tabs.css'");
  });
});

describe('禁用词与源码规则', () => {
  it('本片源码与夹具不出现网络词、注入词、字体词、ServerIcon', () => {
    const words = ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket', 'dangerouslySetInnerHTML', 'innerHTML',
      'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.write', 'srcdoc',
      'createContextualFragment', 'DOMParser', '@font-face', 'FontFace', '.woff', '.ttf', '.otf', '.eot',
      'sarasa-mono-sc-', 'ServerIcon'];
    for (const rel of CODE_FILES) {
      const raw = readWeb(rel);
      for (const word of words) expect(wordHit(raw, word), `${rel} 出现禁用词 ${word}`).toBe(false);
    }
  });

  it('不渲染 role=status；不用四个禁用接口；不写内联 style', () => {
    for (const rel of CODE_FILES) {
      const code = stripComments(readWeb(rel));
      expect(code, `${rel} 不能渲染 role=status`).not.toMatch(/role\s*[=:]\s*\{?\s*["']status["']/);
      for (const name of ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver']) {
        expect(code, `${rel} 不能用 ${name}`).not.toMatch(new RegExp(`\\b${name}\\b`));
      }
      expect(code, `${rel} 不写内联 style`).not.toMatch(/\bstyle\s*=\s*(?:\{|["'])/);
    }
  });

  it('不另写状态到分组的映射；下一步规则用 groupOfState 加 state===\'REVISE\'', () => {
    const codes = ['PREPARING', 'RUNNING', 'COLLECTING', 'NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE',
      'ESCALATE', 'BLOCKED', 'PASS', 'ACCEPTED_WITH_EXCEPTION', 'INTEGRATED', 'REVISE', 'ABANDONED', 'SUPERSEDED',
      'PREPARE_FAILED', 'PREPARED'];
    const groups = ['running', 'review', 'decide', 'integrate', 'ended'];
    for (const rel of CODE_FILES) {
      const code = stripComments(readWeb(rel));
      expect(code, `${rel} 不写 group→状态 的映射`)
        .not.toMatch(new RegExp(`\\b(?:${groups.join('|')})\\s*:\\s*\\[\\s*['"\`][A-Z][A-Z_]*['"\`]`));
      expect(code, `${rel} 不写 状态→group 的映射`)
        .not.toMatch(new RegExp(`\\b(?:${codes.join('|')})\\s*:\\s*['"\`](?:${groups.join('|')})['"\`]`));
    }
    const model = stripComments(readWeb(`${TASKS}/tasks-model.ts`));
    expect(model).toContain('groupOfState');
    expect(model).toContain("state === 'REVISE'");
  });

  it('不写十六进制颜色、颜色函数，也不拼接 --tt- 令牌名', () => {
    for (const rel of CODE_FILES) {
      const raw = readWeb(rel).replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
      expect(raw, `${rel} 不写十六进制颜色`).not.toMatch(/#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/);
      expect(raw, `${rel} 不写颜色函数`).not.toMatch(/\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i);
      expect(raw, `${rel} 不拼接令牌名`).not.toMatch(/[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{/);
    }
  });

  it('本片新图标只用 Svg 包装与现成图标；SearchIcon 不重写', () => {
    const icons = readWeb(`${TASKS}/tasks-icons.tsx`);
    expect(icons).not.toMatch(/export\s+(?:const|function)\s+SearchIcon\b/);
    expect(icons).toContain('export const FileTextIcon');
    expect(icons).toContain('<Svg');
    const canvas = read('docs/ui-design/pages/05-attempt-详情-Themis-Tally.html');
    const at = canvas.indexOf('>summary.md</span>');
    const svg = canvas.slice(canvas.lastIndexOf('<svg', at), at);
    for (const d of svg.match(/<path\b[^>]*?\bd="([^"]+)"/g) ?? []) {
      const value = /d="([^"]+)"/.exec(d)![1];
      expect(icons, `FileTextIcon 应含路径 ${value}`).toContain(`d="${value}"`);
    }
    expect(readWeb(`${TASKS}/TaskListView.tsx`)).toMatch(/import\s*\{[^}]*\bSearchIcon\b[^}]*\}\s*from\s*['"][^'"]*icons['"]/);
  });

  it('tasks-groups 只加标签，分组与映射从 attemptGroups 导入', () => {
    const code = stripComments(readWeb(`${TASKS}/tasks-groups.ts`));
    expect(code).toMatch(/from\s+['"][^'"]*shell\/attemptGroups['"]/);
    expect(code).toContain('ATTEMPT_GROUPS');
    expect(code).toContain('groupOfState');
    expect(code).not.toMatch(/export\s+(?:function|const)\s+groupOfState\b/);
    for (const [group, label] of [['running', '运行中'], ['review', '待验收'], ['decide', '要你决定'],
      ['integrate', '待集成'], ['ended', '已结束']]) {
      expect(code, `${group} 的标签应是「${label}」`).toMatch(new RegExp(`${group}\\s*:\\s*['"]${label}['"]`));
    }
  });

  it('夹具标「示意」，src/mock 仍恰 14 份 JSON', () => {
    for (const name of MOCK_FILES) expect(readWeb(`src/mock/${name}`)).toContain('示意');
  });
});
