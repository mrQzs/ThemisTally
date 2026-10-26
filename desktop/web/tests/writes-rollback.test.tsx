// B 片回滚写入口（历史抽屉 [回滚到这一条之后]）的自测：标题/命令/危险样式、成功只在重读之后才说（W3）、
// 回滚成功后抽屉仍开仍是同一条（D12）、确认框里不出现「没有变化」而抽屉底栏照旧（W3b/D09）、
// 本机文件条目禁用、最新一条可点、Esc 只关确认框。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, HistoryData, RolesData } from '../src/api';

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

const { HistoryView } = await import('../src/pages/readonly2/history-HistoryView');

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = <T extends Element>(sel: string) => Array.from(document.querySelectorAll(sel)) as T[];
const bodyText = () => text(document.body);
const toastText = () => text(document.querySelector('.tt-toast'));
const confirmDialog = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const drawer = () => document.querySelector('[role="dialog"][aria-modal="false"]') as HTMLElement | null;
const dlgText = () => {
  const d = confirmDialog();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function set(name: string, value: (...args: unknown[]) => Promise<unknown>) {
  hoisted.overrides[name] = value;
}

const HIST = {
  entries: [
    { number: 42, resource: 'config', at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default', actor: 'user-ui', confirmation: 'none', state: 'published', resolved: false, changed_keys: ['active_preset', 'roles'], note: null, external_changes: 0 },
    { number: 41, resource: 'local', at: '2026-10-18T01:47:03Z', action: 'runtime.add', target: 'pi', actor: 'user', confirmation: 'none', state: 'published', resolved: false, changed_keys: null, note: '本机文件不存快照', external_changes: 0 },
    { number: 40, resource: 'config', at: '2026-10-17T13:20:45Z', action: 'config.set', target: 'pricing', actor: 'agent:planning_review', confirmation: 'none', state: 'published', resolved: false, changed_keys: ['pricing'], note: '（含疑似凭据，不显示）', external_changes: 1 },
  ],
  broken_lines: [],
  external_before_first: 0,
} as unknown as HistoryData;

const DETAIL: Record<number, unknown> = {
  42: { number: 42, state: 'published', note: null, diff: [] },
  41: { number: 41, resource: 'local', state: 'published', before_sha256: 'a'.repeat(64), after_sha256: 'b'.repeat(64), note: '本机文件不存快照' },
  40: { number: 40, state: 'published', note: null, diff: [] },
};
const reader = (n: number) =>
  Promise.resolve({ ok: true, exit_code: 0, data: DETAIL[n], output: [], messages: [], command: ['config', 'history', 'show', String(n)], elapsed_ms: 0 });

function rolesEnv(): Envelope<RolesData> {
  return { ok: true, exit_code: 0, data: { active_preset: 'default', roles: [] } as RolesData, output: [], messages: [], command: ['config', 'role', 'show'], elapsed_ms: 0 };
}

const rowByNumber = (n: number) => qa<HTMLElement>('tbody tr').find((tr) => text(tr.querySelector('td')) === `#${n}`) as HTMLElement;
const rollbackBtn = () => {
  const d = drawer();
  expect(d, '抽屉应开着').not.toBeNull();
  return Array.from((d as HTMLElement).querySelectorAll('button')).find((b) => text(b) === '回滚到这一条之后') as HTMLButtonElement;
};
async function openHistory(n: number) {
  const row = rowByNumber(n);
  act(() => {
    row.focus();
  });
  fireEvent.keyDown(row, { key: 'Enter' });
  await settle();
}

describe('回滚流程', () => {
  it('#42：标题/命令/危险样式；确认后弹「已回滚到 #42 之后」，抽屉仍开仍是同一条（D12）', async () => {
    window.location.hash = '#/history?write=ok';
    render(<HistoryView data={HIST} getHistoryEntry={reader as never} />);
    await settle();
    await openHistory(42);
    expect(text(drawer() as HTMLElement), '抽屉底栏照旧写「没有变化」').toContain('这是最新的一条，回滚后没有变化');
    fireEvent.click(rollbackBtn());
    await settle();
    const t = dlgText();
    expect(t).toContain('回滚到 #42 之后？');
    expect(t).toContain('config rollback 42');
    expect(t).toContain('预览没有列出变化');
    expect(t, 'W3b：确认框里不出现「没有变化」这个子串').not.toContain('没有变化');
    expect(btn(confirmDialog() as HTMLElement, '确认…')?.getAttribute('data-variant'), '回滚确认钮用 danger').toBe('danger');
    fireEvent.click(btn(confirmDialog() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已回滚到 #42 之后');
    expect(confirmDialog(), '回滚成功后确认框关闭').toBeNull();
    expect(drawer(), '回滚成功后抽屉仍开着').not.toBeNull();
    expect(text((drawer() as HTMLElement).querySelector('h2')), '抽屉仍是同一条').toBe('#42 · preset.use default');
  });

  it('W3：重读兑现之前整页没有「已回滚」、Toast 空；兑现之后才说成功', async () => {
    let hang = false;
    let release!: (v: unknown) => void;
    const gate = new Promise<unknown>((r) => {
      release = r;
    });
    set('getRoles', () => (hang ? gate : Promise.resolve(rolesEnv())));
    window.location.hash = '#/history?write=ok';
    render(<HistoryView data={HIST} getHistoryEntry={reader as never} />);
    await settle();
    await openHistory(42);
    fireEvent.click(rollbackBtn());
    await settle();
    hang = true;
    fireEvent.click(btn(confirmDialog() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(confirmDialog(), '重读中确认框还开着').not.toBeNull();
    expect(toastText(), '重读兑现之前 Toast 区域是空的').toBe('');
    expect(bodyText(), '重读兑现之前整页没有「已回滚」').not.toContain('已回滚');
    release(rolesEnv());
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已回滚到 #42 之后');
  });
});

describe('回滚入口的禁用与最新一条', () => {
  it('本机文件 #41：回滚钮禁用，底栏说明「本机文件不存快照，不能回滚」（B3）', async () => {
    window.location.hash = '#/history?write=ok';
    render(<HistoryView data={HIST} getHistoryEntry={reader as never} />);
    await settle();
    await openHistory(41);
    expect(rollbackBtn().disabled, '本机文件条目不能回滚').toBe(true);
    expect(text(drawer() as HTMLElement)).toContain('本机文件不存快照，不能回滚');
  });

  it('最新一条 #42：回滚钮可点（B4）', async () => {
    window.location.hash = '#/history?write=ok';
    render(<HistoryView data={HIST} getHistoryEntry={reader as never} />);
    await settle();
    await openHistory(42);
    expect(rollbackBtn().disabled, '最新一条不是空操作，可回滚').toBe(false);
  });

  it('Esc 只关确认框，抽屉不关、条目不变（B2）', async () => {
    window.location.hash = '#/history?write=ok';
    render(<HistoryView data={HIST} getHistoryEntry={reader as never} />);
    await settle();
    await openHistory(42);
    fireEvent.click(rollbackBtn());
    await settle();
    expect(confirmDialog()).not.toBeNull();
    fireEvent.keyDown(confirmDialog() as HTMLElement, { key: 'Escape' });
    await settle();
    expect(confirmDialog(), 'Esc 只关确认框').toBeNull();
    expect(drawer(), '抽屉不该被 Esc 关掉').not.toBeNull();
    expect(text((drawer() as HTMLElement).querySelector('h2'))).toBe('#42 · preset.use default');
  });
});
