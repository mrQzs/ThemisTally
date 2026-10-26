// B 片删除写入口（方案/profile/运行时三种删除）的 api 核对与确认流程自测：确认号与参数核对（409）、
// 标题与变化区摘要、[确认…] 危险样式（A 片 preset.use 仍是 primary）、成功只在重读之后才说（W3）、
// 成功之后行消失、in-use 的内核拒绝与内核原文；并守住入口文件不写标题/轻提示/内核原文。
import { useState } from 'react';
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Envelope, PresetsData, ProfilesData } from '../src/api';
import * as api from '../src/api';

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

const { ProfilesTable } = await import('../src/pages/readonly1/roles-ProfilesTable');
const { PresetsTable } = await import('../src/pages/readonly1/roles-PresetsTable');
const { RuntimesView } = await import('../src/pages/readonly1/runtimes-RuntimesView');
const { PresetBar } = await import('../src/pages/readonly1/roles-PresetBar');

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
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const toastText = () => text(document.querySelector('.tt-toast'));
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
const rowByFirstCell = (first: string) =>
  qa<HTMLElement>('tbody tr').find((tr) => text(tr.querySelector('td')) === first) as HTMLElement;

const PROFILES = [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
] as unknown as ProfilesData['profiles'];
const PRESETS = {
  active_preset: 'default',
  presets: [
    { name: 'default', description: 'd', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: 'e', roles: ['execution'], active: false },
  ],
} as unknown as PresetsData;
const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['a'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['b'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;

function profilesEnv(data: unknown = PROFILES): Envelope<ProfilesData> {
  return { ok: true, exit_code: 0, data: { profiles: data } as ProfilesData, output: [], messages: [], command: ['config', 'profile', 'show'], elapsed_ms: 0 };
}
function emptyDiff() {
  return { ok: true, exit_code: 0, data: { a: 'default', b: 'economy', roles: [] }, output: [], messages: [], command: ['config', 'preset', 'diff', 'default', 'economy'], elapsed_ms: 0 };
}

function ProfilesHarness({ hash, initial, after }: { hash: string; initial: unknown; after: unknown }) {
  const [profiles, setProfiles] = useState(initial);
  window.location.hash = hash;
  const reload = () => {
    setProfiles(after);
    return Promise.resolve();
  };
  return <ProfilesTable profiles={profiles as ProfilesData['profiles']} roles={[]} reload={reload} />;
}

describe('api：删除的确认号与参数核对（B9）', () => {
  it('号不存在、对象不符、action 不符都 409；号与对象都对才 200', async () => {
    window.location.hash = '#/roles?write=ok';
    const ghost = await api.removePreset('economy', 'x'.repeat(43));
    expect(ghost.status).toBe(409);
    expect(ghost.body.exit_code).toBe(null);
    expect(ghost.body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
    const conf = (await api.preview('preset.remove', { name: 'economy' })).body.data!.confirmation;
    expect((await api.removePreset('default', conf)).status, '删错对象 409').toBe(409);
    expect((await api.removePreset('economy', conf)).status, '号与对象都对 200').toBe(200);
    const conf2 = (await api.preview('profile.remove', { profile: 'step-low' })).body.data!.confirmation;
    expect((await api.removeRuntime('pi', conf2)).status, 'action 不符 409').toBe(409);
    expect((await api.removeProfile('step-low', conf2)).status).toBe(200);
  });
});

describe('profile 删除流程', () => {
  it('标题、摘要、危险样式；确认后弹「已删除 profile step-low」', async () => {
    window.location.hash = '#/roles?write=ok';
    render(<ProfilesTable profiles={PROFILES} roles={[]} />);
    await settle();
    fireEvent.click(btn(rowByFirstCell('step-low'), '删除') as HTMLButtonElement);
    await settle();
    const t = dlgText();
    expect(t).toContain('删除 profile step-low？');
    expect(t).toContain('profile 表里去掉 step-low');
    expect(t).toContain('config profile remove step-low');
    expect(t).not.toContain('--dry-run');
    expect(btn(dlg() as HTMLElement, '确认…')?.getAttribute('data-variant'), '删除确认钮用 danger').toBe('danger');
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除 profile step-low');
  });

  it('W3：重读兑现之前整页没有「已删除」、Toast 空（B5）', async () => {
    let hang = false;
    let release!: (v: unknown) => void;
    const gate = new Promise<unknown>((r) => {
      release = r;
    });
    set('getProfiles', () => (hang ? gate : Promise.resolve(profilesEnv())));
    window.location.hash = '#/roles?write=ok';
    render(<ProfilesTable profiles={PROFILES} roles={[]} />);
    await settle();
    fireEvent.click(btn(rowByFirstCell('step-low'), '删除') as HTMLButtonElement);
    await settle();
    hang = true;
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(dlg(), '重读中框还开着').not.toBeNull();
    expect(toastText(), '重读兑现之前 Toast 区域是空的').toBe('');
    expect(bodyText(), '重读兑现之前整页没有「已删除」').not.toContain('已删除');
    release(profilesEnv());
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除 profile step-low');
  });

  it('成功之后 reload：step-low 行从表里消失（B6）', async () => {
    render(<ProfilesHarness hash="#/roles?write=ok" initial={PROFILES} after={PROFILES.filter((p) => p.id !== 'step-low')} />);
    await settle();
    expect(rowByFirstCell('step-low'), '删除前 step-low 在表里').toBeTruthy();
    fireEvent.click(btn(rowByFirstCell('step-low'), '删除') as HTMLButtonElement);
    await settle();
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除 profile step-low');
    expect(rowByFirstCell('step-low'), '成功之后删掉的那一行应消失').toBeFalsy();
  });

  it('in-use：失败带「内核拒绝」与内核原文，不弹轻提示、没有「成功」「已部分写入」（B8）', async () => {
    window.location.hash = '#/roles?write=in-use';
    render(<ProfilesTable profiles={PROFILES} roles={[]} />);
    await settle();
    fireEvent.click(btn(rowByFirstCell('step-low'), '删除') as HTMLButtonElement);
    await settle();
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    const t = dlgText();
    expect(t).toContain('内核拒绝');
    expect(t).toContain('ERROR: profile step-low 被 roles.execution 引用：先改这些绑定或方案');
    expect(toastText(), 'Toast 区域应是空的').toBe('');
    expect(bodyText()).not.toContain('已删除');
    expect(bodyText()).not.toContain('成功');
    expect(bodyText()).not.toContain('已部分写入');
  });
});

describe('方案与运行时删除流程', () => {
  it('方案删除：标题/摘要/危险样式/轻提示；点 [删除…] 不调 onDiff（B2）', async () => {
    const calls: unknown[] = [];
    const onDiff = (a: string, b: string) => {
      calls.push([a, b]);
      return Promise.resolve(emptyDiff());
    };
    window.location.hash = '#/roles?write=ok';
    render(<PresetsTable presets={PRESETS.presets} active="default" totalRoles={4} onDiff={onDiff} />);
    await settle();
    fireEvent.click(btn(rowByFirstCell('economy'), '删除…') as HTMLButtonElement);
    await settle();
    expect(calls.length, '点 [删除…] 不调 onDiff').toBe(0);
    const t = dlgText();
    expect(t).toContain('删除方案 economy？');
    expect(t).toContain('方案表里去掉 economy，角色绑定不变');
    expect(t).toContain('config preset remove economy');
    expect(btn(dlg() as HTMLElement, '确认…')?.getAttribute('data-variant')).toBe('danger');
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除方案 economy');
  });

  it('运行时删除：标题/摘要/危险样式/轻提示', async () => {
    window.location.hash = '#/runtimes?write=ok';
    render(<RuntimesView runtimes={RUNTIMES} />);
    await settle();
    fireEvent.click(btn(rowByFirstCell('opencode'), '删除…') as HTMLButtonElement);
    await settle();
    const t = dlgText();
    expect(t).toContain('删除运行时 opencode？');
    expect(t).toContain('已登记表里去掉 opencode；本机文件里登记的命令一并删去');
    expect(t).toContain('config runtime remove opencode');
    expect(btn(dlg() as HTMLElement, '确认…')?.getAttribute('data-variant')).toBe('danger');
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除运行时 opencode');
  });

  it('A 片 preset.use 的 [确认…] 仍是 primary（B1）', async () => {
    window.location.hash = '#/roles?write=ok';
    render(<PresetBar presets={PRESETS.presets} active="default" />);
    await settle();
    fireEvent.click(qa<HTMLElement>('[role="radio"]').find((r) => text(r) === 'economy') as HTMLElement);
    await settle();
    fireEvent.click(btn(document.body, '切换…') as HTMLButtonElement);
    await settle();
    expect(dlgText()).toContain('切换到方案 economy？');
    expect(btn(dlg() as HTMLElement, '确认…')?.getAttribute('data-variant'), 'A 片照旧 primary').toBe('primary');
  });
});

describe('入口文件不写标题/轻提示/内核原文（B11）', () => {
  it('四个入口文件里没有 13 条动作说明与内核原文', () => {
    const files = [
      'src/pages/readonly1/roles-PresetsTable.tsx',
      'src/pages/readonly1/roles-ProfilesTable.tsx',
      'src/pages/readonly1/runtimes-RuntimesView.tsx',
      'src/pages/readonly2/history-HistoryView.tsx',
    ];
    const forbidden = ['删除方案', '删除 profile', '删除运行时', '回滚配置', '已删除', '已回滚', '先改这些绑定或方案', '先改或删这些 profile', 'config unset active_preset'];
    for (const rel of files) {
      const src = readFileSync(resolve(process.cwd(), rel), 'utf8');
      for (const frag of forbidden) expect(src.includes(frag), `${rel} 出现「${frag}」`).toBe(false);
    }
  });
});
