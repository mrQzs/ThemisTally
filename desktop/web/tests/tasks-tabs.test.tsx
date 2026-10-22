// 六个页签自测（合同 Steps 8–10、D08–D11）：摘要、补丁、检查、执行报告、事件、全部文件。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AttemptData, Envelope, FileData, StatusData, StatusRow } from '../src/api';

const hoisted = vi.hoisted(() => ({ overrides: {} as Record<string, (...args: unknown[]) => Promise<unknown>> }));

vi.mock('../src/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const out: Record<string, unknown> = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      out[name] = (...args: unknown[]) =>
        hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as (...a: unknown[]) => unknown)(...args);
    }
  }
  return out;
});

const { TabSummary } = await import('../src/pages/tasks/tab-Summary');
const { TabPatch } = await import('../src/pages/tasks/tab-Patch');
const { TabChecks } = await import('../src/pages/tasks/tab-Checks');
const { TabReport } = await import('../src/pages/tasks/tab-Report');
const { TabEvents } = await import('../src/pages/tasks/tab-Events');
const { TabFiles } = await import('../src/pages/tasks/tab-Files');

beforeEach(() => {
  window.location.hash = '#/tasks?mock=data';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
});
afterEach(cleanup);

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element | null, sel: string) => Array.from((root ?? document).querySelectorAll(sel));
const panel = () => qa(document, '[role="tabpanel"]')[0] ?? document.body;

function env(data: unknown, command: string[] = ['gate']): Envelope<never> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 } as unknown as Envelope<never>;
}
function bad(command: string[], code: number, messages: string[]): Envelope<never> {
  return { ok: false, exit_code: code, data: null, output: [], messages, command, elapsed_ms: 0 } as unknown as Envelope<never>;
}
function set(name: string, value: unknown) {
  hoisted.overrides[name] = typeof value === 'function'
    ? (value as (...args: unknown[]) => Promise<unknown>)
    : () => Promise.resolve(value);
}

function attemptEnv(over: Record<string, unknown> = {}): Envelope<AttemptData> {
  return env({
    task: 'logs-cat', attempt: 'attempt-002', state: 'NEEDS_REVIEW', state_at: '2026-10-18T06:21:40Z',
    summary: { bytes: 512, truncated: false, text: '# logs-cat.v2 / attempt-002\n\n<img src=x onerror=alert(1)> 探针\n' },
    evidence: [{ path: 'summary.md', bytes: 512 }, { path: 'candidate.patch', bytes: 18342 },
      { path: 'events.jsonl', bytes: 2841107 }, { path: 'executor-report.md', bytes: 3920 },
      { path: 'checks/01/V01.log', bytes: 1844 }],
    skipped_links: 0,
    ...over,
  }) as unknown as Envelope<AttemptData>;
}

const row = (over: Record<string, unknown> = {}): StatusRow => ({
  attempt: 'logs-cat/attempt-002', task_id: 'logs-cat', plan_version: 2, attempt_no: 2, state: 'NEEDS_REVIEW',
  started: true, exit_code: 0, wall_seconds: 1719.4, events_ok: true, violations: 0, checks: '8/8',
  check_mode: 'fresh', verdict: null, failure_class: null, human_minutes: 0.0, tokens: 4210385, cost: null,
  cost_status: 'unknown',
  ...over,
} as unknown as StatusRow);

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

describe('摘要页签', () => {
  it('文件行与安全 Markdown 内容原样', async () => {
    set('getAttempt', attemptEnv());
    render(<TabSummary task="logs-cat" attempt="attempt-002" attemptEnv={attemptEnv()} />);
    await settle();
    const md = qa(panel(), '.tt-md');
    expect(md.length, '摘要是 SafeMarkdown').toBe(1);
    const t = text(panel());
    expect(t).toContain('summary.md');
    expect(t).toContain('512 B');
    expect(t).toContain('安全 Markdown：原始 HTML 当文字显示');
    expect(qa(panel(), 'svg[width="14"]').length, '文件行 FileTextIcon 14').toBeGreaterThan(0);
    expect(t).toContain('logs-cat.v2 / attempt-002');
    expect(t).toContain('<img src=x onerror=alert(1)> 探针');
    expect(qa(panel(), 'img, script').length, '不可信内容只按文本显示').toBe(0);
  });

  it('截断提示与 [查看全文]', async () => {
    const truncated = attemptEnv({ summary: { bytes: 3000, truncated: true, text: 'x'.repeat(3000) } });
    set('getAttempt', truncated);
    render(<TabSummary task="logs-cat" attempt="attempt-002" attemptEnv={truncated} />);
    await settle();
    expect(text(panel())).toContain('摘要较长，只显示前 2 KB');
    const full = qa(panel(), 'button').filter((b) => text(b) === '查看全文')[0];
    expect(full, '[查看全文]').toBeTruthy();
    fireEvent.click(full);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '查看全文打开文本查看器').toBeGreaterThan(0);
    expect(text(qa(viewer[0], '.tt-viewer__title')[0])).toBe('summary.md');
  });

  it('没有摘要时写「还没有摘要」；外部链接的第二阶段接入提示', async () => {
    const none = attemptEnv({ summary: null });
    set('getAttempt', none);
    render(<TabSummary task="logs-cat" attempt="attempt-002" attemptEnv={none} />);
    await settle();
    expect(text(panel())).toContain('还没有摘要：attempt 结束后才有 summary.md');
    cleanup();
    const linked = attemptEnv({ summary: { bytes: 30, truncated: false, text: '看 [官网](https://example.com/a?b=1)' } });
    set('getAttempt', linked);
    render(<TabSummary task="logs-cat" attempt="attempt-002" attemptEnv={linked} />);
    await settle();
    const link = qa(panel(), '.tt-md__link')[0];
    expect(link, '摘要里的放行链接').toBeTruthy();
    fireEvent.click(link);
    await settle();
    expect(text(panel())).toContain('打开外部链接在第二阶段接入：https://example.com/a?b=1');
    expect(qa(panel(), 'a').length, '页签面板里没有 a 元素').toBe(0);
  });

  it('logs show 读不到时显示行内出错块', async () => {
    const failed = bad(['logs', 'show', 'x/y'], 2, ['ERROR 夹具里没有这份数据：x/y']);
    set('getAttempt', failed);
    render(<TabSummary task="x" attempt="y" attemptEnv={failed} />);
    await settle();
    const t = text(panel());
    expect(t).toContain('没能读到 summary.md');
    expect(t).toContain('返回退出码 2');
    expect(text(qa(panel(), 'pre')[0])).toContain('ERROR 夹具里没有这份数据');
  });
});

describe('补丁与执行报告', () => {
  it('补丁：DiffView 收到拼好的补丁，title 是 candidate.patch', async () => {
    set('readFile', () => Promise.resolve(env({
      path: 'candidate.patch', mode: 'text', done: true, next_cursor: null,
      text: 'diff --git a/src/x.ts b/src/x.ts\n--- a/src/x.ts\n+++ b/src/x.ts\n@@ -1 +1 @@\n-a\n+b \u001b[31mRED\u001b[0m <script>alert(1)</script>\n',
    }, ['logs', 'cat', 'logs-cat/attempt-002', 'candidate.patch'])));
    render(<TabPatch task="logs-cat" attempt="attempt-002" />);
    await settle();
    const diff = qa(panel(), '.tt-diff');
    expect(diff.length, '补丁页签是差异视图').toBe(1);
    expect(text(qa(diff[0], '.tt-diff__summary-title')[0])).toBe('candidate.patch');
    const t = text(diff[0]);
    expect(t).toContain('src/x.ts');
    expect(t).toContain('RED');
    expect(t).toContain('<script>alert(1)</script>');
    expect(t.indexOf('\u001b')).toBe(-1);
    expect(t.indexOf('[31m')).toBe(-1);
    expect(qa(diff[0], 'script, img').length).toBe(0);
  });

  it('补丁没读完：[继续加载] 带游标再读一页，接在后面', async () => {
    let calls = 0;
    set('readFile', (_t: unknown, _a: unknown, path: unknown, cursor?: unknown) => {
      calls += 1;
      const first = calls === 1 && cursor == null;
      return Promise.resolve(env({
        path, mode: 'text', done: !first, next_cursor: first ? 'c1-next' : null,
        text: first
          ? 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n'
          : 'diff --git a/src/b.ts b/src/b.ts\n--- a/src/b.ts\n+++ b/src/b.ts\n@@ -1 +1 @@\n-c\n+d\n',
      }, ['logs', 'cat', 'logs-cat/attempt-002', 'candidate.patch']));
    });
    render(<TabPatch task="logs-cat" attempt="attempt-002" />);
    await settle();
    expect(text(qa(panel(), '.tt-diff')[0])).toContain('src/a.ts');
    const more = qa(panel(), 'button').filter((b) => text(b) === '继续加载')[0];
    expect(more, '没读完时有 [继续加载]').toBeTruthy();
    fireEvent.click(more);
    await settle();
    expect(calls).toBe(2);
    expect(text(qa(panel(), '.tt-diff')[0])).toContain('src/b.ts');
  });

  it('执行报告：warning 提示条加文本查看器，内容原样', async () => {
    set('getAttempt', attemptEnv());
    render(<TabReport task="logs-cat" attempt="attempt-002" />);
    await settle();
    const banner = qa(panel(), '.tt-banner')[0];
    expect(banner, '执行报告顶部提示条').toBeTruthy();
    expect(banner.getAttribute('data-tone')).toBe('warning');
    expect(text(banner)).toBe('以下是执行器的自述，不是证据。');
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '执行报告用文本查看器').toBeGreaterThan(0);
    expect(text(qa(viewer[0], '.tt-viewer__title')[0])).toBe('executor-report.md');
    const t = text(viewer[0]);
    expect(t).toContain('<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字');
    expect(qa(viewer[0], 'img, script').length).toBe(0);
    expect(t.indexOf('\u001b')).toBe(-1);
    expect(t.indexOf('[31m')).toBe(-1);
  });
});

describe('检查页签', () => {
  it('汇总行、日志表与整行打开', async () => {
    set('getAttempt', attemptEnv());
    render(<TabChecks task="logs-cat" attempt="attempt-002" row={row()} evidence={[
      { path: 'summary.md', bytes: 512 }, { path: 'checks/01/V01.log', bytes: 1844 },
    ]} />);
    await settle();
    const t = text(panel());
    expect(t).toContain('检查 8/8（fresh）');
    expect(t).toContain('每条检查的结果要等 logs show 给出');
    const table = qa(panel(), 'table[aria-label="检查日志"]')[0];
    expect(table, '检查日志表').toBeTruthy();
    const rows = qa(table, 'tbody tr');
    expect(rows.length).toBe(1);
    expect(text(qa(rows[0], 'td')[0])).toBe('checks/01/V01.log');
    expect(text(qa(rows[0], 'td')[qa(rows[0], 'td').length - 1])).toMatch(/1\.8\s*KB/);
    fireEvent.click(rows[0]);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '点一行在表下用文本查看器打开').toBeGreaterThan(0);
    expect(text(qa(viewer[0], '.tt-viewer__title')[0])).toBe('checks/01/V01.log');
  });

  it('checks 为「-」与没有检查日志两种文字', async () => {
    set('getAttempt', attemptEnv());
    render(<TabChecks task="logs-cat" attempt="attempt-002" row={row({ checks: '-', check_mode: null })} evidence={[]} attemptFailure={null} />);
    await settle();
    expect(text(panel())).toContain('还没有检查结果');
    cleanup();
    render(<TabChecks task="logs-cat" attempt="attempt-002" row={row()} evidence={[{ path: 'summary.md', bytes: 512 }]} attemptFailure={null} />);
    await settle();
    expect(text(panel())).toContain('这个 attempt 没有检查日志');
  });

  it('logs show 读不到：只显示行内出错块，不写「没有检查日志」', async () => {
    set('getAttempt', attemptEnv());
    const failure = { command: ['logs', 'show', 'logs-cat/attempt-002'], exit_code: 2, messages: ['ERROR 夹具里没有这份数据'] };
    render(<TabChecks task="logs-cat" attempt="attempt-002" row={row()} evidence={[]} attemptFailure={failure} />);
    await settle();
    const t = text(panel());
    expect(t).toContain('没能读到 logs-cat/attempt-002');
    expect(t).toContain('命令（logs show logs-cat/attempt-002）返回退出码 2');
    expect(t, '读不到时不写没有检查日志').not.toContain('这个 attempt 没有检查日志');
    const pre = qa(panel(), 'pre')[0];
    expect(pre, 'messages 在 pre 里').toBeTruthy();
    expect(text(pre)).toContain('ERROR 夹具里没有这份数据');
    expect(qa(panel(), 'table').length, '读不到时不列表').toBe(0);
  });
});

describe('事件页签', () => {
  it('已结束的 attempt：跟随开关禁用与原因文字', async () => {
    set('getAttempt', attemptEnv());
    render(<TabEvents task="logs-cat" attempt="attempt-002" state="NEEDS_REVIEW" />);
    await settle();
    const log = qa(panel(), '.tt-log');
    expect(log.length, '事件页签是日志跟随').toBe(1);
    const sw = qa(log[0], '[role="switch"]')[0];
    expect(sw, '跟随开关').toBeTruthy();
    expect(sw.getAttribute('aria-disabled') === 'true' || sw.hasAttribute('disabled')).toBe(true);
    expect(text(qa(log[0], '.tt-log__status')[0])).toContain('attempt 已结束，没有新事件');
    expect(qa(log[0], 'input[aria-label="过滤事件"]').length, '自带过滤框').toBe(1);
  });

  it('运行中的 attempt：跟随可用，假计时器每 1000ms 多一行、到上限停', async () => {
    vi.useFakeTimers();
    try {
      render(<TabEvents task="ui-readonly-api" attempt="attempt-001" state="RUNNING" />);
      await settle();
      const log = qa(panel(), '.tt-log')[0];
      expect(log, '运行中 attempt 的事件页签').toBeTruthy();
      const sw = qa(log, '[role="switch"]')[0];
      expect(sw.getAttribute('aria-disabled') === 'true' || sw.hasAttribute('disabled')).toBe(false);
      const count = () => qa(qa(panel(), '.tt-log')[0], '.tt-viewer__row').length;
      const base = count();
      expect(base, '夹具第 1 页有行').toBeGreaterThan(0);
      act(() => { vi.advanceTimersByTime(1000); });
      expect(count(), '推进 1000ms 多一行').toBe(base + 1);
      act(() => { vi.advanceTimersByTime(4000); });
      expect(count(), '按 1000ms 的节奏追加').toBe(base + 5);
      act(() => { vi.advanceTimersByTime(120000); });
      const capped = count();
      act(() => { vi.advanceTimersByTime(10000); });
      expect(count(), '到上限后不再追加').toBe(capped);
      cleanup();
      act(() => { vi.advanceTimersByTime(30000); });
      expect(vi.getTimerCount(), '卸载后没有挂起的计时器').toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('全部文件页签', () => {
  it('三列与大小格式、禁用入口、整行打开与 caption', async () => {
    set('getAttempt', attemptEnv());
    const evidence = [
      { path: 'summary.md', bytes: 512 }, { path: 'candidate.patch', bytes: 18342 },
      { path: 'events.jsonl', bytes: 2841107 }, { path: 'executor-report.md', bytes: 3920 },
      { path: 'checks/01/V01.log', bytes: 1844 },
    ];
    render(<TabFiles task="logs-cat" attempt="attempt-002" evidence={evidence} skippedLinks={0} attemptFailure={null} />);
    await settle();
    const table = qa(panel(), 'table[aria-label="证据文件"]')[0];
    expect(table, '证据文件表').toBeTruthy();
    expect(qa(table, 'thead th').length).toBe(3);
    const rows = qa(table, 'tbody tr');
    expect(rows.length).toBe(5);
    const paths = rows.map((r) => text(qa(r, 'td')[0]));
    expect(paths.slice().sort()).toEqual(['candidate.patch', 'checks/01/V01.log', 'events.jsonl',
      'executor-report.md', 'summary.md']);
    const sizeAt = qa(table, 'thead th').length - 2;
    expect(text(qa(rows[0], 'td')[sizeAt])).toBe('512 B');
    expect(text(qa(rows[1], 'td')[sizeAt])).toMatch(/17\.9\s*KB/);
    expect(text(qa(rows[2], 'td')[sizeAt])).toBe('2.7 MB');
    const reveals = qa(table, 'button').filter((b) => text(b) === '在资源管理器中显示');
    expect(reveals.length, '每行一个禁用入口').toBe(5);
    reveals.forEach((b) => expect((b as HTMLButtonElement).disabled).toBe(true));
    fireEvent.click(rows[2]);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '点一行按段打开').toBeGreaterThan(0);
    expect(text(qa(viewer[0], '.tt-viewer__title')[0])).toBe('events.jsonl');
    expect(text(viewer[0])).toContain('这一行不是合法 JSON，已隐藏');
    expect(text(viewer[0])).toContain('这一行超过 4 MiB，已隐藏');
    expect(text(panel())).toContain('点一行按段打开');
    expect(text(panel())).toContain('跳过的链接 0 个');
  });

  it('「在资源管理器中显示」悬停 400ms 出现提示「第二阶段接入」', async () => {
    vi.useFakeTimers();
    try {
      set('getAttempt', attemptEnv());
      render(<TabFiles task="logs-cat" attempt="attempt-002" evidence={[{ path: 'summary.md', bytes: 512 }]} skippedLinks={0} attemptFailure={null} />);
      await settle();
      const b = qa(panel(), 'button').filter((x) => text(x) === '在资源管理器中显示')[0];
      fireEvent.mouseEnter(b.parentElement!);
      act(() => { vi.advanceTimersByTime(399); });
      expect(qa(document, '[role="tooltip"]').length, '399ms 没有提示').toBe(0);
      act(() => { vi.advanceTimersByTime(1); });
      const tip = qa(document, '[role="tooltip"]')[0];
      expect(tip, '400ms 出现提示').toBeTruthy();
      expect(text(tip)).toBe('第二阶段接入');
    } finally {
      vi.useRealTimers();
    }
  });

  it('logs show 读不到：只显示行内出错块，不列证据文件', async () => {
    set('getAttempt', attemptEnv());
    const failure = { command: ['logs', 'show', 'logs-cat/attempt-002'], exit_code: 2, messages: ['ERROR 夹具里没有这份数据'] };
    render(<TabFiles task="logs-cat" attempt="attempt-002" evidence={[{ path: 'summary.md', bytes: 512 }]} skippedLinks={0} attemptFailure={failure} />);
    await settle();
    const t = text(panel());
    expect(t).toContain('没能读到 logs-cat/attempt-002');
    expect(t).toContain('命令（logs show logs-cat/attempt-002）返回退出码 2');
    expect(text(qa(panel(), 'pre')[0])).toContain('ERROR 夹具里没有这份数据');
    expect(qa(panel(), 'table').length, '读不到时不列表').toBe(0);
    expect(t, '读不到时不写跳过的链接').not.toContain('跳过的链接');
  });
});

describe('页签内的读取态', () => {
  it('出错写「没能读到 <路径>」，messages 进 pre', async () => {
    set('readFile', (_t: unknown, _a: unknown, path: unknown) =>
      Promise.resolve(bad(['logs', 'cat', 'logs-cat/attempt-002', String(path)], 2, ['ERROR 夹具里没有这份数据'])));
    render(<TabReport task="logs-cat" attempt="attempt-002" />);
    await settle();
    const t = text(panel());
    expect(t).toContain('没能读到 executor-report.md');
    expect(t).toContain('命令（logs cat logs-cat/attempt-002 executor-report.md）返回退出码 2');
    expect(text(qa(panel(), 'pre')[0])).toContain('ERROR 夹具里没有这份数据');
  });
});

// 供类型收窄用：避免未使用的导入被 tree-shaking 掉后类型报错
export type _Keep = StatusData | FileData;
