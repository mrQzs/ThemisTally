// 源码规则测试（合同第 9 节）：本片新源码没有两组禁用词、ServerIcon、role=status、内联 style、四个禁用接口；
// 不出现 3.4 分组状态码字面量（分组只来自 attemptGroups）。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const FILES = [
  'pages/readonly1/common-Section.tsx',
  'pages/readonly1/common-links.ts',
  'pages/readonly1/common-CopyNote.tsx',
  'pages/readonly1/overview-OverviewView.tsx',
  'pages/readonly1/overview-MetricCard.tsx',
  'pages/readonly1/overview-AttemptList.tsx',
  'pages/readonly1/overview-ConfigChanges.tsx',
  'pages/readonly1/overview-logic.ts',
  'pages/readonly1/roles-RolesView.tsx',
  'pages/readonly1/roles-RoleCard.tsx',
  'pages/readonly1/roles-PresetBar.tsx',
  'pages/readonly1/roles-ProfilesTable.tsx',
  'pages/readonly1/roles-PresetsTable.tsx',
  'pages/readonly1/roles-PresetDiff.tsx',
  'pages/readonly1/roles-logic.ts',
  'pages/readonly1/runtimes-RuntimesView.tsx',
  'pages/readonly1/runtimes-logic.ts',
  'components/RelativeTime.tsx',
  'components/ActorTag.tsx',
  'components/copyText.ts',
  'components/actionTitle.ts',
];
const STATE_CODES = ['PREPARING', 'RUNNING', 'COLLECTING', 'NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE', 'ESCALATE', 'BLOCKED', 'PASS', 'ACCEPTED_WITH_EXCEPTION', 'INTEGRATED', 'REVISE', 'ABANDONED', 'SUPERSEDED', 'PREPARE_FAILED'];
const FORBIDDEN = ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket', 'dangerouslySetInnerHTML', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.write', 'srcdoc', 'DOMParser', 'ServerIcon'];

function src(rel: string): string {
  return readFileSync(resolve(process.cwd(), 'src', rel), 'utf8');
}
function stripComments(t: string): string {
  return t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
}

describe('源码规则', () => {
  it('没有 role=status、内联 style、四个禁用接口', () => {
    for (const f of FILES) {
      const code = stripComments(src(f));
      expect(/role\s*[=:]\s*\{?\s*["']status["']/.test(code), f).toBe(false);
      expect(/\bstyle\s*=\s*(?:\{|["'])/.test(code), f).toBe(false);
      for (const name of ['matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver']) {
        expect(new RegExp(`\\b${name}\\b`).test(code), `${f} ${name}`).toBe(false);
      }
    }
  });

  it('不出现 3.4 分组状态码字面量', () => {
    for (const f of FILES) {
      const code = stripComments(src(f));
      for (const s of STATE_CODES) {
        expect(new RegExp(`["'\`]${s}["'\`]`).test(code), `${f} ${s}`).toBe(false);
      }
    }
  });

  it('没有两组禁用词与 ServerIcon', () => {
    for (const f of FILES) {
      const t = src(f);
      for (const w of FORBIDDEN) {
        expect(t.includes(w), `${f} ${w}`).toBe(false);
      }
    }
  });
});
