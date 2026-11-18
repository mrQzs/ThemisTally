// 七端岗位写入口与「改绑定」表单的组件测试（合同第 9 步）：入口按钮的 textContent/禁用/悬停原因句/onStart；
// 表单候选与替补联动、底部实时预览（命令 + 前后对比四行 + warnings + running_turns + 报错原文）；真实模式
// （setLiveClientForTests 注入假客户端）确认发岗位写路由（带/不带 fallback）与恢复缺省…，成功后 reload；
// 桩下角色页禁用按钮实测 11（构成见注释）。断言打在真实的 HubBindForm 与 useWriteFlow 上，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import { hubChangeLines } from '../src/writes/hubChangeLines';
import { HubBindAction, HubUnsetAction } from '../src/writes/HubBindForm';

const BIND = '改绑定…';
const UNSET = '恢复缺省…';
const REASON_NO_CANDIDATES = '没有能用在这个岗位的 profile：先在「CLI 运行时」页登记运行时，再新建 profile';
const REASON_UNSET_DEFAULT = '这个岗位现在用的是内核缺省，没有要恢复的配置';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  render(<App />);
  await flush();
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function hubSec(): any {
  return qa(document, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === '七端岗位' : false;
  }) || null;
}
function hubRow(post: string): any {
  const sec = hubSec();
  const row = qa(sec, 'tbody tr').find((tr: any) => tr.getAttribute('data-post') === post);
  expect(row, '应有 data-post=' + post + ' 的行').toBeTruthy();
  return row;
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function selectByLabel(d: HTMLElement, labelText: string): HTMLSelectElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  const hit = qa(d, 'select').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 select 应在表单里').toBeTruthy();
  return hit as HTMLSelectElement;
}
async function tipOf(root: HTMLElement, label: string): Promise<string> {
  const btn = qa(root, 'button').find((b: any) => text(b) === label) as HTMLElement;
  const wrap = btn.closest('.tt-tooltip-wrap') as HTMLElement;
  fireEvent.mouseEnter(wrap);
  await sleep(450);
  const tip = document.querySelector('[role="tooltip"]');
  return tip ? text(tip) : '';
}

// ---- 入口组件（直接渲染，桩模式）----

describe('入口组件（直接渲染）', () => {
  beforeEach(() => {
    setLiveClientForTests(undefined);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('「改绑定…」有候选时可点、textContent 恰为「改绑定…」', () => {
    const r = render(
      <HubBindAction post="exec" postLabel="执行端" mainCandidates={['step-high']} fallbackCandidatesFor={() => []} source="config" mainProfile="step-high" fallbackProfile={null} />,
    );
    const btn = btnIn(r.container, BIND);
    expect(btn.textContent, '按钮里不放岗位名').toBe(BIND);
    expect(btn.disabled).toBe(false);
  });

  it('「改绑定…」没有候选时禁用，悬停出原因句', async () => {
    const r = render(
      <HubBindAction post="planner" postLabel="规划端" mainCandidates={[]} fallbackCandidatesFor={() => []} source="default" mainProfile={null} fallbackProfile={null} />,
    );
    expect(btnIn(r.container, BIND).disabled).toBe(true);
    expect(await tipOf(r.container as HTMLElement, BIND)).toBe(REASON_NO_CANDIDATES);
  });

  it('「恢复缺省…」配置行可点，点击走 hub.unset', () => {
    const onStart = vi.fn();
    const r = render(<HubUnsetAction post="exec" source="config" onStart={onStart} />);
    const btn = btnIn(r.container, UNSET);
    expect(btn.textContent).toBe(UNSET);
    expect(btn.disabled).toBe(false);
    fireEvent.click(btn);
    expect(onStart).toHaveBeenCalledWith({ action: 'hub.unset', args: { post: 'exec' } });
  });

  it('「恢复缺省…」缺省行禁用，悬停出原因句', async () => {
    const r = render(<HubUnsetAction post="gate" source="default" onStart={vi.fn()} />);
    expect(btnIn(r.container, UNSET).disabled).toBe(true);
    expect(await tipOf(r.container as HTMLElement, UNSET)).toBe(REASON_UNSET_DEFAULT);
  });
});

// ---- 真实模式（注入假服务）----

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

const ROLES = { active_preset: 'default', roles: [
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
] };
const PRESETS = { active_preset: 'default', presets: [ { name: 'default', description: '日常', roles: ['execution'], active: true } ] };
const REAL_PROFILES = { profiles: [
  { id: 'quizs-m9', runtime: 'quizs', adapter: 'quizs', provider: 'minimax', model: 'MiniMax-M3.1-Flash', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: [] },
] };

const before = { source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs', provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high', fallback: { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' } };
const after = { source: 'config', profile: 'quizs-m9', runtime: 'quizs', adapter: 'quizs', provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high', fallback: { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' } };

let gets: string[] = [];
let posts: Array<{ path: string; body: any }> = [];
let previewBody: Record<string, unknown> = {};
let previewFail = false;

const fake: LiveClient = {
  get(path: string): Promise<any> {
    gets.push(path);
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES_POSTS, ['config', 'hub', 'show', '--json']));
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES));
    if (path === '/api/v1/profiles') return Promise.resolve(okEnv(REAL_PROFILES));
    if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS));
    if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      if (previewFail) {
        return Promise.resolve({ status: 200, body: { ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 预览不合格：参数不符合组合规则'], command: [], elapsed_ms: 0 } });
      }
      const command = ['config', 'hub', 'set', 'contract', 'quizs-m9', '--fallback=step-high', '--dry-run', '--json'];
      return Promise.resolve({ status: 200, body: okEnv({ preview: previewBody, confirmation: 'c-real-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'hub', 'set']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function basePreview(): Record<string, unknown> {
  return {
    binding_changes: [], resources: [], notes: [], warnings: ['WARN 合同端与审核端用的是同一个模型'],
    running_attempts: [], running_turns: ['审核端（audit）：2 个回合在跑'], needs_yes: false,
    hub_changes: [{ post: 'contract', before, after }],
  };
}

describe('真实模式：表单候选、替补联动与底部预览', () => {
  beforeEach(() => {
    gets = []; posts = []; previewBody = basePreview(); previewFail = false;
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('contract 行：主选候选只有允许名单里的 profile；主选 quizs → 替补可选且预填现有替补；换非 quizs → 替补清空禁用', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    const d = needDlg();
    expect(text(d)).toContain('改绑定：合同端');
    const main = selectByLabel(d, '主绑定');
    expect(qa(main, 'option').map((o: any) => o.value)).toEqual(['quizs-m9', 'step-high', 'step-low']);
    expect(main.value, 'quizs-m3 不在候选 → 预填第一个候选（quizs 的）').toBe('quizs-m9');
    const fb = selectByLabel(d, '替补');
    expect(fb.disabled, '主选是 quizs → 替补可选').toBe(false);
    expect(qa(fb, 'option').map((o: any) => o.value), '首项是「不设替补」').toEqual(['', 'step-high', 'step-low']);
    expect(qa(fb, 'option').map(text)[0]).toBe('不设替补');
    expect(fb.value, '现有替补 step-high 在候选里 → 预填它').toBe('step-high');
    fireEvent.change(main, { target: { value: 'step-high' } });
    await flush();
    expect(fb.disabled, '主选换成 pi → 替补禁用').toBe(true);
    expect(fb.value, '替补清空').toBe('');
  });

  it('底部：命令（去掉 --dry-run/--json）+ 前后对比四行（与 hubChangeLines 一致）+ warnings + running_turns', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config hub set contract quizs-m9 --fallback=step-high');
    for (const line of hubChangeLines({ post: 'contract', before, after } as any)) {
      expect(t, '底部应含前后对比行：' + line).toContain(line);
    }
    expect(t).toContain('WARN 合同端与审核端用的是同一个模型');
    expect(t).toContain('审核端（audit）：2 个回合在跑');
  });

  it('预览失败：底部显示报错原文，确认…不可点', async () => {
    previewFail = true;
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    await sleep(450);
    await flush();
    const d = needDlg();
    expect(text(d)).toContain('ERROR 预览不合格：参数不符合组合规则');
    expect(btnIn(d, '确认…').disabled).toBe(true);
  });
});

describe('真实模式：确认发岗位写路由与 reload', () => {
  beforeEach(() => {
    gets = []; posts = []; previewBody = basePreview(); previewFail = false;
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('改绑定：确认发 POST /api/v1/hub/roles/contract（带 profile 与 fallback），成功后 reload', async () => {
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    await sleep(450);
    await flush();
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const hubPosts = posts.filter((p) => p.path.indexOf('/api/v1/hub/roles/') === 0);
    expect(hubPosts.length, '只发一次岗位写路由').toBe(1);
    expect(hubPosts[0].path).toBe('/api/v1/hub/roles/contract');
    expect(hubPosts[0].body.profile).toBe('quizs-m9');
    expect(hubPosts[0].body.fallback).toBe('step-high');
    expect(typeof hubPosts[0].body.confirmation).toBe('string');
    const previewActions = posts.filter((p) => p.path === '/api/v1/preview').map((p) => (p.body as any).action);
    expect(previewActions, '表单底部与写流程都按 hub.set 预览').toContain('hub.set');
    expect(text(document.body)).toContain('已改绑定 contract');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '成功之后 reload').toBeGreaterThan(rolesBefore);
  });

  it('恢复缺省…（exec 配置行）：确认发 POST /api/v1/hub/roles/exec/unset，正文只有确认号；成功后 reload', async () => {
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    fireEvent.click(btnIn(hubRow('exec'), UNSET));
    await flush();
    expect(text(needDlg())).toContain('恢复缺省 exec？');
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const unsetPosts = posts.filter((p) => p.path === '/api/v1/hub/roles/exec/unset');
    expect(unsetPosts.length).toBe(1);
    expect(Object.keys(unsetPosts[0].body).sort()).toEqual(['confirmation']);
    expect(text(document.body)).toContain('已恢复缺省 exec');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '成功之后 reload').toBeGreaterThan(rolesBefore);
  });
});

// ---- 桩下角色页禁用按钮实测值（page-app 的口径）----

describe('桩下角色页禁用按钮实测 6', () => {
  beforeEach(() => {
    setLiveClientForTests(undefined);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('整页 button[disabled] 是 6（方案条 [切换…] 1 + planner 改绑定… 1 + 4 个缺省行恢复缺省…）', async () => {
    await mountApp('#/roles');
    const disabled = qa(document, 'button[disabled]');
    // 构成：方案条的「切换…」1；
    // planner 只许 claude-code、无 profile 候选 → 「改绑定…」1；
    // coordinator/planner/gate/audit 是缺省行 → 「恢复缺省…」4。合计 6。
    expect(disabled.length, '桩下角色页禁用按钮实测').toBe(6);
    const bindDisabled = qa(hubSec(), 'button[disabled]').filter((b: any) => text(b) === BIND).length;
    const unsetDisabled = qa(hubSec(), 'button[disabled]').filter((b: any) => text(b) === UNSET).length;
    expect(bindDisabled, '七端岗位组里禁用的「改绑定…」（planner）').toBe(1);
    expect(unsetDisabled, '七端岗位组里禁用的「恢复缺省…」（四个缺省行）').toBe(4);
  });
});
