// 源码规则测试（T013 D01、D02）：四样重复件各只留一份共用件，别处只从 components 引入；
// 三份重复件已删除；index.ts 只在末尾追加；本片碰过的源码没有禁用词、内联 style 与 role=status。
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const COMP = 'src/components';
const RO1 = 'src/pages/readonly1';
const RO2 = 'src/pages/readonly2';
const COPY_TEXT = `${COMP}/copyText.ts`;
const ACTION_TITLE = `${COMP}/actionTitle.ts`;
const ACTOR_TAG = `${COMP}/ActorTag.tsx`;
const RELATIVE_TIME = `${COMP}/RelativeTime.tsx`;
const INDEX = `${COMP}/index.ts`;
const DELETED = [`${RO1}/common-copyText.ts`, `${RO2}/common-copy.ts`, `${RO2}/history-ActorTag.tsx`];
const COPY_RESULT_STRINGS = ['这个环境没有剪贴板接口', '已复制', '复制失败'];
const ACTION_TITLES: Record<string, string> = {
  'config.set': '设置配置键',
  'config.unset': '删除配置键',
  'config.rollback': '回滚配置',
  'preset.use': '切换方案',
  'preset.save': '保存方案',
  'preset.remove': '删除方案',
  'role.set': '修改角色绑定',
  'profile.add': '新建 profile',
  'profile.edit': '修改 profile',
  'profile.remove': '删除 profile',
  'runtime.add': '登记 runtime',
  'runtime.remove': '删除 runtime',
  external: '检测到界面与命令之外的改动',
};
// 本片新建与改过的源码：守卫逐份扫（T014 之后加上共用 CopyNote）。
const TOUCHED = [
  COPY_TEXT, ACTION_TITLE, ACTOR_TAG, RELATIVE_TIME, INDEX, `${COMP}/CopyNote.tsx`,
  `${RO1}/common-CopyNote.tsx`, `${RO1}/overview-MetricCard.tsx`, `${RO1}/overview-AttemptList.tsx`,
  `${RO1}/overview-ConfigChanges.tsx`, `${RO1}/overview-logic.ts`, `${RO1}/roles-PresetsTable.tsx`,
  `${RO2}/history-HistoryView.tsx`, `${RO2}/history-HistoryDrawer.tsx`, `${RO2}/history-logic.ts`,
  `${RO2}/common-format.ts`, `${RO2}/plugins-PluginDrawer.tsx`,
];
const FORBIDDEN = ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket', 'dangerouslySetInnerHTML', 'innerHTML',
  'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.write', 'srcdoc', 'DOMParser', 'ServerIcon',
  'matchMedia', 'scrollIntoView', 'ResizeObserver', 'IntersectionObserver'];

function sourcesUnder(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (full: string, rel: string) => {
    for (const name of readdirSync(full)) {
      const child = resolve(full, name);
      const childRel = rel ? `${rel}/${name}` : name;
      if (statSync(child).isDirectory()) walk(child, childRel);
      else if (/\.tsx?$/.test(name)) out[`src/${childRel}`] = readFileSync(child, 'utf8');
    }
  };
  walk(resolve(process.cwd(), 'src'), '');
  for (const rel of Object.keys(out)) {
    if (!rel.startsWith(`${dir}/`)) delete out[rel];
  }
  return out;
}
const SCANNED: Record<string, string> = { ...sourcesUnder(COMP), ...sourcesUnder(RO1), ...sourcesUnder(RO2) };
const read = (rel: string) => readFileSync(resolve(process.cwd(), rel), 'utf8');
function stripComments(t: string): string {
  return t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
}
function where(files: Record<string, string>, literal: string): string[] {
  return Object.keys(files).filter((rel) => files[rel].includes(literal)).sort();
}

describe('四样重复件各只留一份', () => {
  it('copyText 只有一处导出定义，三条结果文字只在 copyText.ts', () => {
    const defs = Object.keys(SCANNED).filter((rel) =>
      /export\s+(?:async\s+)?function\s+copyText\b|export\s+const\s+copyText\b/.test(stripComments(SCANNED[rel])));
    expect(defs).toEqual([COPY_TEXT]);
    for (const s of COPY_RESULT_STRINGS) expect(where(SCANNED, s), s).toEqual([COPY_TEXT]);
  });

  it('13 条动作说明只在 actionTitle.ts', () => {
    for (const text of Object.values(ACTION_TITLES)) expect(where(SCANNED, text)).toEqual([ACTION_TITLE]);
  });

  it('ActorTag 组件只有一处定义，带引号的 undeclared 只在 ActorTag.tsx', () => {
    const defs = Object.keys(SCANNED).filter((rel) =>
      /export\s+(?:function|const)\s+ActorTag\b/.test(stripComments(SCANNED[rel])));
    expect(defs).toEqual([ACTOR_TAG]);
    expect(where(SCANNED, "'undeclared'").concat(where(SCANNED, '"undeclared"')).sort()).toEqual([ACTOR_TAG]);
  });

  it('「（UTC 」拼写只在 RelativeTime.tsx', () => {
    expect(where(SCANNED, '（UTC ')).toEqual([RELATIVE_TIME]);
  });

  it('三份重复件已删除，且没有文件再从它们引入', () => {
    for (const rel of DELETED) expect(existsSync(resolve(process.cwd(), rel)), `${rel} 应已删除`).toBe(false);
    const bad = Object.keys(SCANNED).filter((rel) =>
      /from\s+['"](?:\.\.?\/)*(?:common-copyText|common-copy|history-ActorTag)['"]/.test(stripComments(SCANNED[rel])));
    expect(bad).toEqual([]);
  });

  it('用到这几样时只从 components 引入', () => {
    const wants: [string, string[]][] = [
      ['copyText', [`${RO1}/overview-AttemptList.tsx`, `${RO2}/plugins-PluginDrawer.tsx`]],
      ['COPY_RESULT_TEXT', [`${COMP}/CopyNote.tsx`, `${RO2}/plugins-PluginDrawer.tsx`]],
      ['actionTitle', [`${RO1}/overview-ConfigChanges.tsx`, `${RO2}/history-HistoryView.tsx`, `${RO2}/history-HistoryDrawer.tsx`]],
      ['ActorTag', [`${RO1}/overview-ConfigChanges.tsx`, `${RO2}/history-HistoryView.tsx`]],
      ['RelativeTime', [`${RO1}/overview-ConfigChanges.tsx`, `${RO2}/history-HistoryView.tsx`]],
      ['formatLocalUtc', [`${RO2}/history-HistoryDrawer.tsx`]],
    ];
    for (const [name, files] of wants) {
      for (const rel of files) {
        const code = stripComments(read(rel));
        const srcs = Array.from(code.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['"]([^'"]+)['"]/g))
          .filter((m) => m[1].split(',').map((p) => p.trim().replace(/^type\s+/, '')).includes(name))
          .map((m) => m[2]);
        expect(srcs.length, `${rel} 应引入 ${name}`).toBeGreaterThan(0);
        for (const s of srcs) expect(s, `${rel} 的 ${name} 应来自 components`).toMatch(/components/);
      }
    }
  });
});

describe('components/index.ts 只在末尾追加', () => {
  it('文件头注释与既有导出不动，末尾追加的只涉及四个共用件模块', () => {
    const text = read(INDEX);
    expect(text).toContain('共五片');
    const marker = '第 8 片（T009）：相对时间与执行者标签';
    const i = text.indexOf(marker);
    expect(i, 'index.ts 应保留第 8 片的导出块').toBeGreaterThanOrEqual(0);
    const appended = text.slice(text.indexOf('第 9 片'));
    const modules = Array.from(appended.matchAll(/from\s+'\.\/([^']+)'/g)).map((m) => m[1]);
    expect(new Set(modules).size, '末尾追加的导出只涉及四个共用件模块').toBe(4);
    expect(new Set(modules)).toEqual(new Set(['copyText', 'actionTitle', 'ActorTag', 'RelativeTime']));
    const names = Array.from(appended.matchAll(/export\s+(?:type\s+)?\{([^}]*)\}/g))
      .flatMap((m) => m[1].split(',').map((p) => p.trim().replace(/^type\s+/, '')).filter(Boolean));
    expect(new Set(names)).toEqual(new Set(['copyText', 'COPY_RESULT_TEXT', 'CopyResult', 'ACTION_TITLES', 'actionTitle', 'actorTone', 'formatLocalUtc']));
    // 追加的内容在文件末尾：后面不再有别的内容。
    expect(text.trimEnd().endsWith("export { formatLocalUtc } from './RelativeTime';")).toBe(true);
  });
});

describe('本片源码的守卫', () => {
  it('没有禁用词、没有内联 style、没有 role=status', () => {
    for (const rel of TOUCHED) {
      const raw = read(rel);
      for (const w of FORBIDDEN) expect(raw.includes(w), `${rel} 出现 ${w}`).toBe(false);
      const code = stripComments(raw);
      expect(/\bstyle\s*=\s*(?:\{|["'])/.test(code), `${rel} 写了内联 style`).toBe(false);
      expect(/role\s*[=:]\s*\{?\s*["']status["']/.test(code), `${rel} 渲染了 role=status`).toBe(false);
    }
  });

  it('新增的共用件与指标卡源码不写死颜色', () => {
    for (const rel of [COPY_TEXT, ACTION_TITLE, ACTOR_TAG, RELATIVE_TIME, `${COMP}/CopyNote.tsx`, `${RO1}/overview-MetricCard.tsx`, `${RO1}/roles-PresetsTable.tsx`]) {
      const raw = read(rel);
      expect(/#(?:[0-9a-fA-F]{3,8})(?![0-9a-fA-F])/.test(raw), `${rel} 写死了颜色`).toBe(false);
      expect(/\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i.test(raw), `${rel} 用了颜色函数`).toBe(false);
    }
  });
});
