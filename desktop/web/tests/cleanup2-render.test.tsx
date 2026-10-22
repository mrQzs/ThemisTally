// 合并后的渲染自测（T014 D02、D04）：四处图标的 svg 属性与 path 列表和合并前相同；
// 五处复制（任务列表、详情页头、执行报告页签、总览、首启页）的三种结果文字等于 COPY_RESULT_TEXT。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';
import { ArrowRightIcon, ExternalLinkIcon, FileTextIcon } from '../src/icons';
import { COPY_RESULT_TEXT, copyText, type CopyResult } from '../src/components/copyText';
import { AttemptList } from '../src/pages/readonly1/overview-AttemptList';
import { TaskListView } from '../src/pages/tasks/TaskListView';
import { AttemptDetailView } from '../src/pages/tasks/AttemptDetailView';
import { FirstRunView } from '../src/shellpages/FirstRunView';
import type { AttemptData, Envelope, StatusRow } from '../src/api';
import type { ShellState, ThemisShell } from '../src/shellpages/themisShell';

// tab-Report 只读一个证据文件：这里给一份固定的 ok 信封，避免依赖夹具与网络。
vi.mock('../src/pages/tasks/tasks-data', () => ({
  readAttemptFile: () => Promise.resolve({
    ok: true, exit_code: 0, output: [], messages: [], elapsed_ms: 0,
    command: ['files', 'read'],
    data: { mode: 'text', text: '执行报告正文', done: true },
  }),
}));

const { TabReport } = await import('../src/pages/tasks/tab-Report');

afterEach(cleanup);

const read = (rel: string) => readFileSync(resolve(process.cwd(), rel), 'utf8');
const text = (el: Element | null | undefined) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: ParentNode, sel: string) => Array.from(root.querySelectorAll(sel));

/** 临时把 navigator.clipboard 换成给定值，跑完还原（jsdom 里默认没有剪贴板接口）。 */
async function withNavigatorClipboard(clip: unknown, run: () => Promise<void>): Promise<void> {
  const desc = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', { value: clip, configurable: true, writable: true });
  try {
    await run();
  } finally {
    if (desc) Object.defineProperty(navigator, 'clipboard', desc);
    else delete (navigator as { clipboard?: unknown }).clipboard;
  }
}

// 合并前（画布）的 path d：FileTextIcon 五条、ExternalLinkIcon 三条、ArrowRightIcon 两条。
const FILE_TEXT_PATHS = [
  'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z',
  'M14 2v4a2 2 0 0 0 2 2h4',
  'M10 9H8',
  'M16 13H8',
  'M16 17H8',
];
const EXTERNAL_LINK_PATHS = ['M15 3h6v6', 'M10 14 21 3', 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'];
const ARROW_RIGHT_PATHS = ['M5 12h14', 'm12 5 7 7-7 7'];

describe('四处图标渲染属性与 path 列表和合并前相同', () => {
  // 四处调用方（合同 D02）：文件、大小与合并前一致；引入都指向共用件 src/icons。
  const SITES = [
    { site: 'src/pages/tasks/tab-Summary.tsx', name: 'FileTextIcon', size: 14, paths: FILE_TEXT_PATHS },
    { site: 'src/shellpages/SettingsView.tsx', name: 'FileTextIcon', size: 16, paths: FILE_TEXT_PATHS },
    { site: 'src/shellpages/SettingsView.tsx', name: 'ExternalLinkIcon', size: 16, paths: EXTERNAL_LINK_PATHS },
    { site: 'src/pages/readonly2/secrets-SecretsView.tsx', name: 'ExternalLinkIcon', size: 14, paths: EXTERNAL_LINK_PATHS },
    { site: 'src/shellpages/FirstRunView.tsx', name: 'ArrowRightIcon', size: 16, paths: ARROW_RIGHT_PATHS },
  ];

  it('调用方仍按原尺寸渲染，且都从 src/icons 引入', () => {
    for (const { site, name, size } of SITES) {
      const code = read(site);
      expect(code, `${site} 应从 src/icons 引入 ${name}`)
        .toMatch(new RegExp(`import\\s*\\{[^}]*\\b${name}\\b[^}]*\\}\\s*from\\s*['"][^'"]*icons['"]`));
      expect(code, `${site} 渲染 ${name} 应是 width/height 都是 ${size}`)
        .toContain(`<${name} width={${size}} height={${size}} />`);
    }
  });

  it('共用图标的 svg 属性与 path 列表和合并前相同', () => {
    const drawn = [
      [FileTextIcon, FILE_TEXT_PATHS], [ExternalLinkIcon, EXTERNAL_LINK_PATHS], [ArrowRightIcon, ARROW_RIGHT_PATHS],
    ] as [(props: { width: number; height: number }) => ReactElement, string[]][];
    for (const [Icon, paths] of drawn) {
      for (const size of [14, 16]) {
        const { container, unmount } = render(<Icon width={size} height={size} />);
        const svg = container.querySelector('svg') as SVGElement;
        expect(svg.getAttribute('width')).toBe(String(size));
        expect(svg.getAttribute('height')).toBe(String(size));
        expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
        expect(svg.getAttribute('class')).toBe('tt-i');
        expect(svg.getAttribute('fill')).toBe('none');
        expect(svg.getAttribute('stroke')).toBe('currentColor');
        expect(svg.getAttribute('stroke-width')).toBe('1.75');
        expect(svg.getAttribute('aria-hidden')).toBe('true');
        expect(qa(svg, 'path').map((p) => p.getAttribute('d'))).toEqual(paths);
        unmount();
      }
    }
  });
});

// 五处复制调用方：前三处与总览渲染 <CopyNote result=…>，首启页照旧渲染 span.tt-fr__copyres（Q2-A）。
const row = (over: Record<string, unknown>): StatusRow => ({
  attempt: 'alpha/attempt-003', task_id: 'alpha', plan_version: 2, attempt_no: 3, state: 'NEEDS_REVIEW',
  started: true, exit_code: null, wall_seconds: 1719.4, events_ok: true, violations: 0, checks: '8/8',
  check_mode: 'fresh', verdict: null, failure_class: null, human_minutes: null, tokens: 4210385, cost: null,
  cost_status: 'unknown', effort_requested: 'max', effort_effective: 'high',
  ...over,
} as unknown as StatusRow);

function attemptEnv(): Envelope<AttemptData> {
  return {
    ok: true, exit_code: 0, output: [], messages: [], elapsed_ms: 0, command: ['attempt', 'show'],
    data: {
      task: 'alpha', attempt: 'attempt-003', state: 'NEEDS_REVIEW', state_at: '2026-10-18T06:21:40Z',
      summary: { bytes: 512, truncated: false, text: '# 标题\n\n正文' },
      evidence: [{ path: 'summary.md', bytes: 512 }], skipped_links: 0,
    } as unknown as AttemptData,
  };
}

function shellState(): ShellState {
  return {
    app: { version: '0.0.0', homepage: 'https://example.invalid' },
    settings: {
      repos: [{ id: 'demo-repo', name: 'demo-repo', path: 'C:/Projects/demo-repo', lastOpened: null }],
      currentRepo: 'demo-repo', transcriptDirs: [], theme: 'system', density: 'standard',
    },
    currentRepoCheck: 'no-agent',
    python: { status: 'ok', source: 'auto', path: 'C:/Python313/python.exe', version: '3.13.1' },
    kit: { status: 'ok', source: 'repo', path: '.agent/kit', version: '2.12.0' },
    service: { kind: 'idle' },
  } as unknown as ShellState;
}

function stubShell(): ThemisShell {
  const state = shellState();
  return {
    getState: () => Promise.resolve(state),
    pickRepo: () => Promise.resolve({ kind: 'cancelled' }),
    pickPython: () => Promise.resolve({ kind: 'cancelled' }),
    pickKit: () => Promise.resolve({ kind: 'cancelled' }),
    pickTranscriptDir: () => Promise.resolve({ kind: 'cancelled' }),
    saveSettings: () => Promise.resolve(state),
    startService: () => Promise.resolve(),
    restartService: () => Promise.resolve(),
    openExternal: () => Promise.resolve(),
    on: () => () => {},
  } as unknown as ThemisShell;
}

/** 给定剪贴板，点开渲染树里的复制钮，返回复制结果那一行的文字。 */
async function copyTextOf(container: HTMLElement, clip: unknown, label = '复制命令'): Promise<string> {
  let shown = '';
  await withNavigatorClipboard(clip, async () => {
    const btn = qa(container, `[aria-label="${label}"]`)[0] as HTMLElement;
    expect(btn, '应有一个复制钮').toBeTruthy();
    await act(async () => {
      fireEvent.click(btn);
      for (let i = 0; i < 8; i += 1) await Promise.resolve();
    });
    shown = text(container.querySelector('.tt-copy-note') ?? container.querySelector('.tt-fr__copyres'));
  });
  return shown;
}

const CLIPS: [unknown, string][] = [
  [{ writeText: async () => {} }, COPY_RESULT_TEXT.copied],
  [{}, COPY_RESULT_TEXT.unavailable],
  [{ writeText: async () => { throw new Error('x'); } }, COPY_RESULT_TEXT.failed],
];

describe('五处复制的三结果文字等于 COPY_RESULT_TEXT', () => {
  it('任务列表的复制结果', async () => {
    for (const [clip, want] of CLIPS) {
      const { container, unmount } = render(
        <TaskListView
          rows={[row()]}
          selectedTask="alpha"
          groups={[]}
          onSelectTask={() => {}}
          onGroupsChange={() => {}}
          onOpenAttempt={() => {}}
          mock=""
          navigate={() => {}}
        />,
      );
      expect(await copyTextOf(container, clip)).toBe(want);
      unmount();
    }
  });

  it('详情页头的复制结果', async () => {
    for (const [clip, want] of CLIPS) {
      const { container, unmount } = render(
        <AttemptDetailView
          task="alpha"
          attempt="attempt-003"
          row={row()}
          attemptEnv={attemptEnv()}
          tab="report"
          onTabChange={() => {}}
          mock=""
          navigate={() => {}}
        />,
      );
      expect(await copyTextOf(container, clip)).toBe(want);
      unmount();
    }
  });

  it('执行报告页签的复制结果', async () => {
    for (const [clip, want] of CLIPS) {
      const { container, unmount } = render(<TabReport task="alpha" attempt="attempt-003" />);
      expect(await copyTextOf(container, clip, '复制已显示的文字')).toBe(want);
      unmount();
    }
  });

  it('总览 attempt 表的复制结果', async () => {
    for (const [clip, want] of CLIPS) {
      const { container, unmount } = render(
        <AttemptList
          title="待验收"
          rows={[row()]}
          linkKind="evidence"
          infoKind="checks"
          next={{ text: '验收在规划端会话里进行：', command: '/review-pi .agent/runs/alpha/attempt-003' }}
          navigate={() => {}}
        />,
      );
      expect(await copyTextOf(container, clip)).toBe(want);
      unmount();
    }
  });

  it('首启页的复制结果（span.tt-fr__copyres 照旧，只改引入）', async () => {
    for (const [clip, want] of CLIPS) {
      const { container, unmount } = render(<FirstRunView shell={stubShell()} navigate={() => {}} />);
      await act(async () => {
        for (let i = 0; i < 8; i += 1) await Promise.resolve();
      });
      expect(await copyTextOf(container, clip)).toBe(want);
      // 首启页不借用 CopyNote：结果文字仍写在 span.tt-fr__copyres 里。
      expect(container.querySelector('.tt-copy-note')).toBeNull();
      expect(container.querySelector('.tt-fr__copyres')).not.toBeNull();
      unmount();
    }
  });
});
