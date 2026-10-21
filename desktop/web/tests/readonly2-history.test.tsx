// 历史与审计页自测（合同 D06、D07）：十列表格各行取值；差异抽屉的五种键级差异情形、KeyDiff 符号与 footer。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoryView } from '../src/pages/readonly2/history-HistoryView';
import type { HistoryData } from '../src/api';

const NOW = '2026-10-18T03:00:00Z';

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const entry = (n: number, o: Record<string, unknown>) => ({
  number: n, resource: 'config', at: '2026-10-18T02:30:00Z', action: 'config.set', target: 'pricing',
  actor: 'user-ui', confirmation: 'none', state: 'published', resolved: false, changed_keys: [], note: null,
  external_changes: 0, ...o,
});

const HIST = {
  entries: [
    entry(1, { resource: 'weird-res', at: '2026-10-18T00:00:00Z', actor: 'something' }),
    entry(2, { at: 'not-a-time', action: 'role.set', target: 'execution', actor: 'undeclared', confirmation: 'flag', state: null, changed_keys: null, note: '疑似凭据，不显示' }),
    entry(3, { at: '2026-10-18T02:59:30Z', action: 'custom.act', target: '', actor: 'agent:planning_review', state: 'unknown', changed_keys: null, note: '（含疑似凭据，不显示）' }),
    entry(4, { resource: 'local', at: '2026-10-17T03:00:00Z', action: 'runtime.add', target: 'pi', actor: 'user', state: 'aborted', changed_keys: null, note: '本机文件不存快照' }),
    entry(5, { at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default', actor: 'user-ui', confirmation: 'flag', resolved: true, changed_keys: ['active_preset', 'roles'], external_changes: 2 }),
    entry(6, { at: '2026-10-18T02:30:00Z', action: 'external', target: '', changed_keys: ['k'] }),
    entry(7, { at: '2026-10-18T02:40:00Z', action: 'config.unset', target: 'x', changed_keys: null }),
    entry(8, { at: '2026-10-18T02:50:00Z', action: 'config.set', target: 'pricing', changed_keys: ['pricing', 'roles'], note: '（含疑似凭据，不显示）' }),
  ],
  broken_lines: ['bad1', 'bad2'],
  external_before_first: 3,
} as unknown as HistoryData;

const DETAIL: Record<number, unknown> = {
  1: { number: 1, state: 'published', note: null, diff: [] },
  2: { number: 2, state: null, note: '疑似凭据，不显示', diff: null },
  3: { number: 3, state: 'unknown', note: '（含疑似凭据，不显示）', diff: null },
  4: { number: 4, resource: 'local', state: 'aborted', before_sha256: 'a'.repeat(64), after_sha256: 'b'.repeat(64), note: '本机文件不存快照' },
  5: { number: 5, state: 'published', note: null, diff: [
    { key: 'active_preset', old: 'default', new: 'economy' },
    { key: 'roles.x', old: null, new: 5 },
    { key: 'enabled_flag', old: true, new: { a: 1 } },
    { key: 'secret.k', old: '<redacted>', new: '（值不显示）' },
  ] },
  6: { number: 6, state: 'published', note: '快照太旧', diff: null },
  7: { number: 7, state: 'published', note: null, diff: null },
  8: { number: 8, state: 'published', note: '（含疑似凭据，不显示）', diff: null },
};
const ok = (data: unknown, command: string[]) => ({ ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 });
const reader = (n: number) => Promise.resolve(DETAIL[n] ? ok(DETAIL[n], ['config', 'history', 'show', String(n)]) : { ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 夹具里没有这份数据'], command: ['config', 'history', 'show', String(n)], elapsed_ms: 0 });

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const table = () => document.querySelector('table[aria-label="配置历史"]') as HTMLTableElement;
const rows = () => Array.from(table().querySelectorAll('tbody tr'));
const cells = (row: Element) => Array.from(row.querySelectorAll('td'));
const rowN = (n: number) => rows().find((r) => text(cells(r)[0]) === `#${n}`) as HTMLElement;
const cellN = (n: number, i: number) => cells(rowN(n))[i];
const dialog = () => document.querySelector('[role="dialog"]') as HTMLElement | null;
const closeBtn = () => dialog()!.querySelector('button[aria-label="关闭（Esc）"]') as HTMLElement;
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function mount(data: HistoryData = HIST) {
  const out = render(<HistoryView data={data} getHistoryEntry={reader as never} />);
  await settle();
  return out;
}
async function open(n: number) {
  const row = rowN(n);
  act(() => { row.focus(); });
  fireEvent.keyDown(row, { key: 'Enter' });
  await settle();
  return dialog() as HTMLElement;
}
async function reopen(n: number) {
  if (dialog()) {
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    await settle();
  }
  return open(n);
}
const titleOf = (el: Element) => {
  if (el.hasAttribute('title')) return el.getAttribute('title');
  const inner = el.querySelector('[title]');
  return inner ? inner.getAttribute('title') : null;
};

describe('历史与审计：表', () => {
  it('十列、倒序、编号带 tt-num、相对时间与 title', async () => {
    await mount();
    const t = table();
    expect(Array.from(t.querySelectorAll('thead th')).map((x) => text(x)))
      .toEqual(['编号', '时间', '资源', '动作', '对象', '执行者', '确认', '状态', '改动的键', '外部改动']);
    expect(t.getAttribute('data-row-height')).toBe('40');
    expect(rows().map((r) => text(cells(r)[0]))).toEqual(['#8', '#7', '#6', '#5', '#4', '#3', '#2', '#1']);
    for (const r of rows()) expect(cells(r)[0].classList.contains('tt-num')).toBe(true);
    expect(text(cellN(5, 1))).toBe('57 分钟前');
    expect(titleOf(cellN(5, 1))).toMatch(/（UTC 02:02:11）$/);
    expect(text(cellN(4, 1))).toBe('1 天前');
    expect(text(cellN(3, 1))).toBe('30 秒前');
    expect(text(cellN(2, 1))).toBe('not-a-time');
    expect(titleOf(cellN(2, 1))).toBeNull();
  });

  it('资源、动作中文 title、对象、执行者、确认、状态', async () => {
    await mount();
    expect(text(cellN(5, 2))).toBe('配置');
    expect(text(cellN(4, 2))).toBe('本机文件');
    expect(text(cellN(1, 2))).toBe('weird-res');
    for (const [n, action] of [[5, 'preset.use'], [4, 'runtime.add'], [6, 'external'], [2, 'role.set']]) {
      expect(text(cellN(n, 3))).toBe(action);
      expect(titleOf(cellN(n, 3))).toMatch(/[一-鿿]/);
    }
    expect(text(cellN(3, 3))).toBe('custom.act');
    expect(titleOf(cellN(3, 3))).toBeNull();
    expect(text(cellN(5, 4))).toBe('default');
    expect(text(cellN(3, 4))).toBe('—');
    const tones: [number, string][] = [[5, 'brand'], [4, 'neutral'], [3, 'info'], [2, 'warning'], [1, 'neutral']];
    for (const [n, tone] of tones) {
      const tag = cellN(n, 5).querySelector('[data-tone]') as HTMLElement;
      expect(tag.getAttribute('data-tone'), `#${n}`).toBe(tone);
    }
    expect(text(cellN(5, 6))).toBe('flag');
    expect(text(cellN(5, 7)).replace(/\s+/g, '')).toBe('已发布（补判）');
    expect(titleOf(cellN(5, 7))).toBe('published');
    expect(text(cellN(4, 7))).toBe('已中止');
    expect(text(cellN(3, 7))).toBe('未知');
    expect(text(cellN(2, 7))).toBe('进行中或已中断');
  });

  it('改动的键与遮蔽 note；外部改动标签', async () => {
    await mount();
    expect(Array.from(cellN(5, 8).querySelectorAll('[data-tone]')).map((t) => text(t))).toEqual(['active_preset', 'roles']);
    const masked = cellN(3, 8).querySelector('span.tt-masked') as HTMLElement;
    expect(text(masked)).toBe('（含疑似凭据，不显示）');
    expect(masked.getAttribute('title')).toBe('内核已遮蔽');
    expect(text(cellN(2, 8))).toBe('疑似凭据，不显示');
    expect(cellN(2, 8).querySelector('.tt-masked')).toBeNull();
    expect(text(cellN(4, 8))).toBe('本机文件不存快照');
    expect(text(cellN(1, 8))).toBe('—');
    const tag = cellN(5, 9).querySelector('[data-tone]') as HTMLElement;
    expect(text(tag)).toBe('检测到外部改动');
    expect(tag.getAttribute('data-tone')).toBe('warning');
    expect(titleOf(cellN(5, 9)) || '').toContain('2');
    expect(text(cellN(4, 9))).toBe('—');
  });

  it('两行注记与 broken_lines 提示条；视图根不写 data-page-state', async () => {
    await mount();
    const root = document.querySelector('[data-page="history"]') as HTMLElement;
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('h1')).toBeNull();
    const below = Array.from(root.querySelectorAll('*')).find(
      (e) => text(e) === '时间显示相对时间，悬停显示本地时间与 UTC；动作悬停显示中文说明。',
    ) as HTMLElement;
    expect(below).toBeTruthy();
    expect(table().compareDocumentPosition(below) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const above = Array.from(root.querySelectorAll('*')).find(
      (e) => text(e) === '第 1 条之前：配置中心之外已有的内容（记为基线，发现 3 次）',
    ) as HTMLElement;
    expect(above).toBeTruthy();
    expect(table().compareDocumentPosition(above) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
    const banner = Array.from(document.querySelectorAll('.tt-banner[data-tone="warning"]'))
      .find((b) => text(b).includes('历史里有 2 行读不出来'));
    expect(banner).toBeTruthy();
    expect(banner?.querySelector('button')).toBeNull();
    cleanup();
    await mount({ ...HIST, broken_lines: [], external_before_first: 0 } as HistoryData);
    expect(text(document.body)).not.toContain('读不出来');
    expect(text(document.body)).not.toContain('第 1 条之前');
    expect(text(document.body)).toContain('时间显示相对时间');
    expect(rows()).toHaveLength(8);
  });
});

describe('历史与审计：差异抽屉', () => {
  it('标题、dl、外部改动提示条', async () => {
    await mount();
    const d = await open(5);
    expect(text(d.querySelector('h2'))).toBe('#5 · preset.use default');
    expect(d.querySelector('[data-drawer="history"]')).not.toBeNull();
    const dts = Array.from(d.querySelectorAll('dl dt')).map((x) => text(x));
    expect(dts).toEqual(expect.arrayContaining(['时间', '动作', '执行者', '确认', '状态']));
    const dd = (label: string) => {
      const dt = Array.from(d.querySelectorAll('dt')).find((x) => text(x) === label) as HTMLElement;
      return dt.nextElementSibling as HTMLElement;
    };
    expect(text(dd('时间'))).toMatch(/（UTC 02:02:11）$/);
    expect(text(dd('动作'))).toContain('preset.use');
    expect(text(dd('动作'))).toContain('切换方案');
    expect(text(dd('执行者'))).toBe('user-ui');
    expect(text(dd('确认'))).toBe('flag');
    expect(text(dd('状态'))).toContain('已发布');
    const banner = Array.from(d.querySelectorAll('.tt-banner[data-tone="warning"]'))
      .find((b) => text(b).includes('这条之后检测到 2 次界面与命令之外的改动。'));
    expect(banner).toBeTruthy();
    const d8 = await reopen(8);
    expect(text(d8.querySelector('h2'))).toBe('#8 · config.set pricing');
    expect(d8.querySelector('.tt-banner')).toBeNull();
  });

  it('情形二：KeyDiff 的符号、未设置、JSON 与遮蔽值', async () => {
    await mount();
    const d = await open(5);
    const keyRow = (k: string) => {
      const leaf = Array.from(d.querySelectorAll('*')).find((e) => e.children.length === 0 && text(e) === k) as HTMLElement;
      let el = leaf;
      while (el.parentElement && el.parentElement.children.length < 3) el = el.parentElement;
      return Array.from((el.parentElement as HTMLElement).children) as HTMLElement[];
    };
    const a = keyRow('active_preset');
    expect(text(a[1])[0]).toBe(String.fromCharCode(0x2212));
    expect(text(a[1])).toMatch(/^−\s*default$/);
    expect(text(a[2])).toMatch(/^\+\s*economy$/);
    expect(text(keyRow('roles.x')[1])).toBe('未设置');
    expect(text(keyRow('roles.x')[2])).toMatch(/^\+\s*5$/);
    expect(text(keyRow('enabled_flag')[1])).toMatch(/^−\s*true$/);
    expect(JSON.parse(text(keyRow('enabled_flag')[2]).replace(/^\+\s*/, ''))).toEqual({ a: 1 });
    const m = keyRow('secret.k');
    expect(text(m[1].querySelector('.tt-masked'))).toBe('<redacted>');
    expect(text(m[2].querySelector('.tt-masked'))).toBe('（值不显示）');
    expect(text(d)).not.toContain('没有改动的键');
    expect(text(d)).not.toContain('快照里有疑似凭据');
  });

  it('情形一、三、五；情形四的两个分支', async () => {
    await mount();
    let t = text(await reopen(4));
    expect(t).toContain('本机文件不存快照，这一条只有审计记录，不能回滚。');
    expect(t).not.toContain('之前');
    t = text(await reopen(1));
    expect(t).toContain('没有改动的键');
    t = text(await reopen(6));
    expect(t).toContain('快照太旧');
    expect(t).not.toContain('快照里有疑似凭据');
    t = text(await reopen(7));
    expect(t).toContain('快照缺失，没有逐键差异');
    // 情形四：占位 note 且列表有改动的键 → 逐键两格 MaskedValue
    const d8 = await reopen(8);
    for (const k of ['pricing', 'roles']) {
      const leaf = Array.from(d8.querySelectorAll('*')).find((e) => e.children.length === 0 && text(e) === k) as HTMLElement;
      let el = leaf;
      while (el.parentElement && el.parentElement.children.length < 3) el = el.parentElement;
      const row = Array.from((el.parentElement as HTMLElement).children) as HTMLElement[];
      expect(text(row[1].querySelector('.tt-masked'))).toBe('（含疑似凭据，不显示）');
      expect(text(row[2].querySelector('.tt-masked'))).toBe('（含疑似凭据，不显示）');
    }
    expect(text(d8)).toContain('快照里有疑似凭据，只存了哈希。');
    expect(Array.from(d8.querySelectorAll('svg')).some((s) => s.getAttribute('width') === '12')).toBe(true);
    // 情形四：changed_keys 为空 → 只显示 note 原文
    const d2 = await reopen(2);
    expect(text(d2)).toContain('疑似凭据，不显示');
    expect(text(d2)).toContain('快照里有疑似凭据，只存了哈希。');
    expect(text(d2)).not.toContain('之前');
    const d3 = await reopen(3);
    expect(text(d3)).toContain('（含疑似凭据，不显示）');
    expect(text(d3)).toContain('快照里有疑似凭据，只存了哈希。');
  });

  it('footer：两种说明与禁用的 [回滚到这一条之后]', async () => {
    await mount();
    let d = await open(8);
    expect(text(d)).toContain('这是最新的一条，回滚后没有变化');
    const btn = Array.from(d.querySelectorAll('button')).find((b) => text(b) === '回滚到这一条之后') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('md');
    expect(btn.querySelector('svg')?.getAttribute('width')).toBe('16');
    d = await reopen(4);
    expect(text(d)).toContain('本机文件不存快照，不能回滚');
    expect(text(d)).not.toContain('这是最新的一条');
    d = await reopen(5);
    expect(text(d)).not.toContain('这是最新的一条');
    expect(text(d)).not.toContain('本机文件不存快照，不能回滚');
  });

  it('焦点与 Esc 同 D05：提示出现后第一次 Esc 只关提示；焦点在抽屉外 Esc 不关、点抽屉外不关', async () => {
    await mount();
    const d = await open(5);
    act(() => { vi.advanceTimersByTime(400); });
    expect(document.querySelector('[role="tooltip"]')).not.toBeNull();
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
    expect(dialog(), '第一次 Esc 不关抽屉').not.toBeNull();
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(dialog()).toBeNull();
    // 焦点在抽屉外按 Esc 不关；点抽屉外也不关。
    const d2 = await open(5);
    const other = rowN(6);
    act(() => { other.focus(); });
    fireEvent.keyDown(other, { key: 'Escape' });
    expect(dialog(), '焦点在抽屉外按 Esc 不关').not.toBeNull();
    const root = document.querySelector('[data-page="history"]') as HTMLElement;
    fireEvent.click(root);
    fireEvent.mouseDown(root);
    await settle();
    expect(dialog(), '点抽屉外不关').not.toBeNull();
    expect(text(dialog()!.querySelector('h2'))).toBe('#5 · preset.use default');
  });

  it('读取中与出错', async () => {
    let resolve!: (v: unknown) => void;
    const r = render(<HistoryView data={HIST} getHistoryEntry={((): Promise<unknown> => new Promise((res) => { resolve = res; })) as never} />);
    await settle();
    const row = rowN(5);
    act(() => { row.focus(); });
    fireEvent.keyDown(row, { key: 'Enter' });
    await settle();
    expect(text(dialog())).toContain('正在读取…');
    await act(async () => {
      resolve({ ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR x <b>y</b>'], command: ['config', 'history', 'show', '5'], elapsed_ms: 0 });
    });
    const d = dialog() as HTMLElement;
    expect(text(d)).toContain('没能读到详情：命令（config history show 5）返回退出码 2。');
    expect(d.querySelector('pre')?.textContent).toContain('ERROR x <b>y</b>');
    expect(text(d)).not.toContain('正在读取…');
    r.unmount();
  });

  it('只认最后一次请求：旧回应丢弃', async () => {
    const first = new Promise<unknown>(() => {});
    let second!: (v: unknown) => void;
    const pending2 = new Promise<unknown>((res) => { second = res; });
    let n = 0;
    const r = render(<HistoryView data={HIST} getHistoryEntry={((num: number) => (++n === 1 ? first : pending2)) as never} />);
    await settle();
    const row5 = rowN(5);
    act(() => { row5.focus(); });
    fireEvent.keyDown(row5, { key: 'Enter' });
    await settle();
    fireEvent.click(rowN(6));
    await settle();
    await act(async () => { second(ok(DETAIL[6], ['config', 'history', 'show', '6'])); });
    await act(async () => { (first as Promise<unknown>); });
    const d = dialog() as HTMLElement;
    expect(text(d)).toContain('快照太旧');
    expect(text(d)).not.toContain('active_preset');
    r.unmount();
  });
});
