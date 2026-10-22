// 合并后的渲染测试（T013 D03、D04）：总览与历史、插件两侧改用共用件后，渲染与合并前一致。
// 总览配置变更的动作 title、执行者五色、相对时间文字与 title、复制三结果；历史表的时间格换成带 dateTime 的 time、
// 执行者五色与动作 title；抽屉 dl 的时间；插件抽屉的复制三结果。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import type { StatusRow } from '../src/api';
import { OverviewView } from '../src/pages/readonly1/overview-OverviewView';
import { AttemptList } from '../src/pages/readonly1/overview-AttemptList';
import { HistoryView } from '../src/pages/readonly2/history-HistoryView';
import { HistoryDrawer } from '../src/pages/readonly2/history-HistoryDrawer';
import { PluginDrawer } from '../src/pages/readonly2/plugins-PluginDrawer';
import { COPY_RESULT_TEXT, copyText } from '../src/components/copyText';
import { ACTION_TITLES } from '../src/components/actionTitle';
import { formatLocalUtc } from '../src/components/RelativeTime';

afterEach(cleanup);

// 相对时间的文字取决于当前时刻：固定系统时间，断言才稳定。
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
  vi.useRealTimers();
});

const NOW = '2026-10-18T03:00:00Z';
const noNav = () => {};
const text = (el: Element | null | undefined) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element, sel: string) => Array.from(root.querySelectorAll(sel));

function row(over: Record<string, unknown>): StatusRow {
  return Object.assign({ attempt: 't/attempt-001', task_id: 't', plan_version: 1, state: 'RUNNING', wall_seconds: null, checks: '-' }, over) as StatusRow;
}
const ROWS: StatusRow[] = [
  row({ attempt: 'rev-a/attempt-002', task_id: 'rev-a', plan_version: 2, state: 'NEEDS_REVIEW', wall_seconds: 1719.4, checks: '8/8' }),
  row({ attempt: 'run-a/attempt-003', task_id: 'run-a', state: 'RUNNING', live: { tool_calls: 37, elapsed_seconds: 1146, long_idle: false } }),
];
function historyEnv(entries: unknown[]): any {
  return { ok: true, exit_code: 0, data: { entries, broken_lines: [], external_before_first: 0 }, output: [], messages: [], command: ['config', 'history'], elapsed_ms: 0 };
}
function sectionNamed(root: Element, title: string): Element | undefined {
  return qa(root, 'section').find((s) => {
    const id = s.getAttribute('aria-labelledby');
    const h = id ? document.getElementById(id) : null;
    return text(h) === title;
  });
}

/** 临时把 navigator.clipboard 换成给定值，跑完还原。 */
async function withNavigatorClipboard(clip: unknown, run: () => Promise<unknown>): Promise<void> {
  const desc = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', { value: clip, configurable: true, writable: true });
  try {
    await run();
  } finally {
    if (desc) Object.defineProperty(navigator, 'clipboard', desc);
    else delete (navigator as { clipboard?: unknown }).clipboard;
  }
}
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}

describe('总览：配置变更与复制', () => {
  const entries = [
    { number: 7, at: '2026-10-18T02:40:00Z', action: 'config.unset', target: 'x', actor: 'agent:planning_review', external_changes: 0 },
    { number: 9, at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default', actor: 'undeclared', external_changes: 2 },
    { number: 3, at: 'not-a-time', action: 'custom.act', target: 'y', actor: 'user', external_changes: 0 },
  ];

  it('动作 title 取共用件的 13 条中文说明，表外不带 title', () => {
    const { container } = render(<OverviewView status={ROWS} history={historyEnv(entries)} navigate={noNav} />);
    const lis = qa(sectionNamed(container, '最近的配置变更') as Element, 'li');
    // topChanges 按 number 倒序取前 5：9、7、3。
    expect(lis.map((li) => qa(li, '.ov-change__no')[0].textContent)).toEqual(['#9', '#7', '#3']);
    expect(qa(lis[0], '.ov-change__action')[0].getAttribute('title')).toBe(ACTION_TITLES['preset.use']);
    expect(qa(lis[1], '.ov-change__action')[0].getAttribute('title')).toBe(ACTION_TITLES['config.unset']);
    expect(qa(lis[2], '.ov-change__action')[0].getAttribute('title')).toBeNull();
    expect(qa(lis[0], '.ov-change__action')[0].textContent).toBe('preset.use');
  });

  it('执行者五色与合并前相同；相对时间的文字与 title 与合并前相同', () => {
    const { container } = render(<OverviewView status={ROWS} history={historyEnv(entries)} navigate={noNav} />);
    const lis = qa(sectionNamed(container, '最近的配置变更') as Element, 'li');
    const tones = lis.map((li) => qa(li, '.ov-change__tags [data-tone]').map((t) => t.getAttribute('data-tone')));
    // 第 9 条有外部改动（warning 标签）加 undeclared（warning）；第 7 条 agent:（info）；第 3 条 user（neutral）。
    expect(tones).toEqual([['warning', 'warning'], ['info'], ['neutral']]);
    const time = lis[0].querySelector('time') as HTMLElement;
    expect(time.textContent).toBe('57 分钟前');
    expect(time.getAttribute('dateTime')).toBe('2026-10-18T02:02:11Z');
    expect(time.getAttribute('title')).toBe(formatLocalUtc('2026-10-18T02:02:11Z'));
    const bad = lis[2].querySelector('.ov-change__time') as HTMLElement;
    expect(bad.textContent).toBe('not-a-time');
    expect(bad.getAttribute('title')).toBeNull();
    expect(bad.tagName).toBe('SPAN');
  });

  it('复制三结果的文字与合并前相同（缺省走 navigator.clipboard）', async () => {
    const results: string[] = [];
    for (const [clip, want] of [
      [{ writeText: async () => {} }, COPY_RESULT_TEXT.copied],
      [{}, COPY_RESULT_TEXT.unavailable],
      [{ writeText: async () => { throw new Error('x'); } }, COPY_RESULT_TEXT.failed],
    ] as [unknown, string][]) {
      const { container, unmount } = render(
        <AttemptList title="待集成" rows={ROWS} linkKind="evidence" infoKind="checks" next={{ text: '集成在规划端会话里进行：', command: '/review-pi x' }} navigate={noNav} />,
      );
      const copyBtn = qa(container, 'button').find((b) => b.getAttribute('aria-label') === '复制命令') as HTMLElement;
      await withNavigatorClipboard(clip, async () => {
        fireEvent.click(copyBtn);
        await flush();
      });
      expect(text(container.querySelector('.common-copy-note'))).toBe(want);
      expect(await copyText('a', clip as { writeText?: (t: string) => Promise<void> })).toBe(
        want === COPY_RESULT_TEXT.copied ? 'copied' : want === COPY_RESULT_TEXT.unavailable ? 'unavailable' : 'failed',
      );
      results.push(text(container.querySelector('.common-copy-note')));
      unmount();
    }
    expect(results).toEqual([COPY_RESULT_TEXT.copied, COPY_RESULT_TEXT.unavailable, COPY_RESULT_TEXT.failed]);
  });
});

const histEntry = (n: number, o: Record<string, unknown>) => ({
  number: n, resource: 'config', at: '2026-10-18T02:30:00Z', action: 'config.set', target: 'pricing',
  actor: 'user-ui', confirmation: 'none', state: 'published', resolved: false, changed_keys: [], note: null,
  external_changes: 0, ...o,
});
const HIST = {
  entries: [
    histEntry(1, { at: 'not-a-time', action: 'custom.act', actor: 'something', changed_keys: null }),
    histEntry(2, { at: '2026-10-18T02:59:30Z', action: 'role.set', actor: 'undeclared', state: null, changed_keys: null }),
    histEntry(3, { at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default', actor: 'agent:planning_review', external_changes: 2 }),
    histEntry(4, { at: '2026-10-18T00:00:00Z', action: 'runtime.add', target: 'pi', actor: 'user', state: 'aborted' }),
  ],
  broken_lines: [],
  external_before_first: 0,
} as unknown as Parameters<typeof HistoryView>[0]['data'];

describe('历史表：时间格换成 time、执行者五色、动作 title', () => {
  it('时间格是带 dateTime 的 time，title 是本地加 UTC；解析不了原样且无 title', () => {
    const { container } = render(<HistoryView data={HIST} getHistoryEntry={(async () => ({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 })) as never} />);
    const rows = qa(container, 'tbody tr');
    // 行按编号倒序：4、3、2、1。
    expect(rows.map((r) => text(r.children[0]))).toEqual(['#4', '#3', '#2', '#1']);
    const at = (i: number) => rows[i].children[1] as HTMLElement;
    expect(at(1).querySelector('time')?.getAttribute('dateTime')).toBe('2026-10-18T02:02:11Z');
    expect(text(at(1))).toBe('57 分钟前');
    expect(at(1).querySelector('time')?.getAttribute('title')).toBe(formatLocalUtc('2026-10-18T02:02:11Z'));
    expect(at(0).querySelector('time')?.getAttribute('dateTime')).toBe('2026-10-18T00:00:00Z');
    expect(text(at(0))).toBe('3 小时前');
    expect(at(2).querySelector('time')?.getAttribute('dateTime')).toBe('2026-10-18T02:59:30Z');
    expect(text(at(2))).toBe('30 秒前');
    expect(at(3).textContent).toBe('not-a-time');
    expect(at(3).querySelector('time')).toBeNull();
    expect(at(3).getAttribute('title')).toBeNull();
  });

  it('执行者五色与动作 title 与合并前相同', () => {
    const { container } = render(<HistoryView data={HIST} getHistoryEntry={(async () => ({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 })) as never} />);
    const rows = qa(container, 'tbody tr');
    expect(rows.map((r) => (r.children[5].querySelector('[data-tone]') as HTMLElement).getAttribute('data-tone')))
      .toEqual(['neutral', 'info', 'warning', 'neutral']);
    expect(rows.map((r) => text(r.children[5]))).toEqual(['user', 'agent:planning_review', 'undeclared', 'something']);
    expect(rows[1].children[3].querySelector('[title]')?.getAttribute('title')).toBe(ACTION_TITLES['preset.use']);
    expect(rows[3].children[3].querySelector('[title]')).toBeNull();
  });
});

describe('抽屉与插件抽屉：时间与复制', () => {
  it('历史抽屉 dl 的时间是本地加 UTC，解析不了回落到原文', () => {
    const load = (async () => ({ ok: true, exit_code: 0, data: { number: 3, state: 'published', note: null, diff: [] }, output: [], messages: [], command: [], elapsed_ms: 0 })) as never;
    const { container } = render(<HistoryDrawer entry={histEntry(3, { at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default' }) as never} load={load} />);
    const dts = qa(container, 'dt');
    const dd = dts.find((dt) => text(dt) === '时间')!.nextElementSibling as HTMLElement;
    expect(text(dd)).toBe(formatLocalUtc('2026-10-18T02:02:11Z'));
    const action = dts.find((dt) => text(dt) === '动作')!.nextElementSibling as HTMLElement;
    expect(text(action)).toContain(ACTION_TITLES['preset.use']);
  });

  it('插件抽屉复制 lock_sha256 后显示三结果文字', async () => {
    const pluginRow = { id: 'demo', name: 'demo', version: '1.0.0', status: 'READY', enabled: '启用', reason: '', missing: [] } as never;
    const load = (async () => ({
      ok: true, exit_code: 0,
      data: {
        plugin_id: 'demo', version: '1.0.0', api_version: '1', capabilities: ['x'], platforms: ['y'],
        depends_on: [], conflicts: [], permissions: ['fs.write'],
        config: { missing_permissions: [] },
        resources: [{ path: 'a.py', sha256: 'a'.repeat(64), status: '一致', detail: '' }],
        lock: { generation: 3, lock_sha256: 'b'.repeat(64) },
      },
      output: [], messages: [], command: [], elapsed_ms: 0,
    })) as never;
    for (const [clip, want] of [
      [{ writeText: async () => {} }, COPY_RESULT_TEXT.copied],
      [{}, COPY_RESULT_TEXT.unavailable],
      [{ writeText: () => Promise.reject(new Error('x')) }, COPY_RESULT_TEXT.failed],
    ] as [unknown, string][]) {
      const { container, unmount } = render(<PluginDrawer row={pluginRow} load={load} />);
      await flush();
      const btn = qa(container, 'button').find((b) => b.getAttribute('aria-label') === '复制 lock_sha256') as HTMLElement;
      await withNavigatorClipboard(clip, async () => {
        fireEvent.click(btn);
        await flush();
      });
      expect(text(container.querySelector('.r2-copy-result'))).toBe(want);
      unmount();
    }
  });
});
