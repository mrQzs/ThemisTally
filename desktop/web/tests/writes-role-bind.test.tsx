// 角色卡「改绑定」表单的组件测试（合同第 12 步）：allowedModes/profileIds 的边界、四个角色各自只列允许的
// 模式（中文名照 modeName）、无头时再选 profile 与底部实时预览（命令 + 本角色的前后两侧 + warnings 原文）；
// 真实模式（setLiveClientForTests 注入假客户端）确认发 POST /api/v1/roles/<role>（正文的键恰好、
// cadence_seconds 是 JSON 数字、role 不进正文）、host 与 cadence_seconds 的原样传回、写完重读与 reload；
// 没有已登记的 profile 时 execution 入口禁用（悬停出原因句）、其余三个角色的模式下拉没有「无头」且原因句在
// Select 的 help 里；对话框关着时不渲染候选与多余的按钮。断言打在真实的 RoleBindForm 与 useWriteFlow 上，
// 不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import { allowedModes, modeName, profileIds } from '../src/pages/readonly1/roles-logic';
import { RoleBindAction } from '../src/writes/RoleBindForm';

const CHANGE = '更改…';
const REASON_NO_PROFILES = '没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile';
const ROLES = ['planning_review', 'contract', 'execution', 'scheduler_agent'];
const TITLES: Record<string, string> = {
  planning_review: '规划审核端',
  contract: '合同端',
  execution: '执行端',
  scheduler_agent: '调度代理',
};

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  await flush();
  render(<App />);
  await flush();
}
function card(role: string): any {
  const hit = document.querySelector(`article[data-role="${role}"]`);
  expect(hit, '应有角色卡 ' + role).toBeTruthy();
  return hit;
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
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'select').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 select 应在表单里').toBeTruthy();
  return hit as HTMLSelectElement;
}
function optionValueByLabel(sel: HTMLSelectElement, label: string): string {
  const hit = qa(sel, 'option').find((o: any) => text(o) === label);
  expect(hit, '应有选项「' + label + '」').toBeTruthy();
  return (hit as any).value;
}
function selectedLabel(sel: HTMLSelectElement): string {
  const hit = qa(sel, 'option').find((o: any) => (o as any).selected);
  return hit ? text(hit) : '';
}
async function tipOf(root: HTMLElement, label: string): Promise<string> {
  const btn = qa(root, 'button').find((b: any) => text(b) === label) as HTMLElement;
  const wrap = btn.closest('.tt-tooltip-wrap') as HTMLElement;
  fireEvent.mouseEnter(wrap);
  await sleep(450);
  const tip = document.querySelector('[role="tooltip"]');
  return tip ? text(tip) : '';
}

describe('allowedModes 与 profileIds（纯函数）', () => {
  it('四个角色各自的允许模式（次序照 ROLE_MODES，出自 scripts/kit_roles.py）', () => {
    expect(allowedModes('planning_review')).toEqual(['interactive_host', 'headless']);
    expect(allowedModes('contract')).toEqual(['manual', 'headless']);
    expect(allowedModes('execution')).toEqual(['headless']);
    expect(allowedModes('scheduler_agent')).toEqual(['disabled', 'headless']);
  });

  it('未知角色给 []', () => {
    expect(allowedModes('zz-none')).toEqual([]);
    expect(allowedModes('')).toEqual([]);
  });

  it('profileIds 按输入顺序、滤掉 _ 开头', () => {
    expect(profileIds([{ id: 'b' }, { id: '_x' }, { id: 'a' }, { id: '_y' }] as any)).toEqual(['b', 'a']);
    expect(profileIds([] as any)).toEqual([]);
  });
});

describe('桩下角色页：四张卡的 [更改…] 与模式选项', () => {
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

  it('四张卡的 [更改…] 都可点，是 secondary/sm；对话框关着时没有下拉与多余的按钮', async () => {
    await mountApp('#/roles');
    for (const role of ROLES) {
      const b = btnIn(card(role), CHANGE);
      expect(b.disabled, role + ' 的 [更改…] 可点').toBe(false);
      expect(b.getAttribute('data-variant'), role + ' secondary').toBe('secondary');
      expect(b.getAttribute('data-size'), role + ' sm').toBe('sm');
      expect(qa(card(role), 'select').length, role + ' 对话框关着不渲染表单字段').toBe(0);
      expect(qa(card(role), 'button').length, role + ' 对话框关着只有一个入口按钮').toBe(1);
    }
  });

  it('四个角色各自只列允许的模式（中文名照 modeName）且预填现有模式；无头时才有 profile 下拉', async () => {
    for (const role of ROLES) {
      cleanup();
      await mountApp('#/roles');
      fireEvent.click(btnIn(card(role), CHANGE));
      await flush();
      const d = needDlg();
      expect(text(d), role + ' 对话框标题').toContain('改绑定：' + TITLES[role]);
      const mode = selectByLabel(d, '模式');
      expect(qa(mode, 'option').map(text), role + ' 的模式选项').toEqual(allowedModes(role).map(modeName));
      const profileSelects = qa(d, 'select').filter((el: any) => {
        const label = qa(d, 'label').find((l: any) => (l as any).getAttribute('for') === el.id);
        return label && text(label) === 'profile';
      });
      if (role === 'execution') {
        expect(profileSelects.length, 'execution 只允许无头 → 有 profile 下拉').toBe(1);
        expect(selectedLabel(mode), 'execution 现有模式是无头').toBe('无头');
        expect(qa(profileSelects[0], 'option').map((o: any) => o.value), '候选是全部已登记 profile 的 id').toEqual(['step-high', 'step-low']);
        expect(profileSelects[0].value, '现有 profile 在候选里 → 预填它').toBe('step-high');
      } else {
        expect(profileSelects.length, role + ' 不是无头 → 没有 profile 下拉').toBe(0);
      }
      fireEvent.click(btnIn(d, '取消'));
      await flush();
      expect(dlg(), '取消后表单对话框应关上').toBeNull();
    }
  });

  it('scheduler_agent 切到无头：profile 下拉出现并预填第一个候选', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(card('scheduler_agent'), CHANGE));
    await flush();
    const mode = selectByLabel(needDlg(), '模式');
    expect(selectedLabel(mode), '预填现有模式（关闭）').toBe('关闭');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '无头') } });
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    expect(profile.value, '现有绑定没有 profile → 预填第一个候选').toBe('step-high');
  });
});

// ---- 真实模式（注入假服务）----

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

const REAL_ROLES = { active_preset: 'default', roles: [
  { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'scheduler_agent', explicit: true, binding: { mode: 'headless', profile: 'step-high', cadence_seconds: 3600 }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
] };
const REAL_PROFILES = { profiles: [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: [] },
  { id: '_internal', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'm0', options: {}, credential_env: [] },
] };
const EMPTY_PROFILES = { profiles: [] };
const PRESETS = { active_preset: 'default', presets: [{ name: 'default', description: '日常', roles: ['execution'], active: true }] };

let rolesData: any = REAL_ROLES;
let profilesData: any = REAL_PROFILES;
let gets: string[] = [];
let posts: Array<{ path: string; body: any }> = [];
let previewBody: Record<string, unknown> = {};
let previewCommand: string[] = [];
let previewFail = false;

const fake: LiveClient = {
  get(path: string): Promise<any> {
    gets.push(path);
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES_POSTS, ['config', 'hub', 'show', '--json']));
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(rolesData));
    if (path === '/api/v1/profiles') return Promise.resolve(okEnv(profilesData));
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
      return Promise.resolve({ status: 200, body: okEnv({ preview: previewBody, confirmation: 'c-real-1' }, previewCommand) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'role', 'set']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function basePreview(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [{ resource: 'roles' }], notes: [], unreadable: [], warnings: [],
    running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [], ...over,
  };
}

async function openForm(role: string) {
  fireEvent.click(btnIn(card(role), CHANGE));
  await flush();
  return needDlg();
}

async function confirmWrite(role: string) {
  fireEvent.click(btnIn(needDlg(), '确认…'));
  await flush();
  const cd = needDlg();
  expect(text(cd), '写确认框标题').toContain('改角色绑定 ' + role + '？');
  fireEvent.click(btnIn(cd, '确认…'));
  await flush();
  await sleep(120);
  await flush();
}

describe('真实模式：底部预览与 [确认…] 门控', () => {
  beforeEach(() => {
    gets = []; posts = []; previewFail = false;
    rolesData = REAL_ROLES;
    profilesData = REAL_PROFILES;
    previewBody = basePreview();
    previewCommand = ['config', 'role', 'set', 'execution', 'step-low', '--dry-run', '--json'];
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('execution 选无头再选 profile：底部有命令、本角色的前后两侧与 warnings 原文', async () => {
    previewBody = basePreview({
      binding_changes: [{ role: 'execution', before: { mode: 'headless', profile: 'step-high' }, after: { mode: 'headless', profile: 'step-low' } }],
      warnings: ['WARN 执行端已固定，切换不影响正在运行的 attempt'],
    });
    await mountApp('#/roles');
    await openForm('execution');
    const profile = selectByLabel(needDlg(), 'profile');
    fireEvent.change(profile, { target: { value: optionValueByLabel(profile, 'step-low') } });
    await flush();
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t, '将运行的命令').toContain('config role set execution step-low');
    expect(t.replace(/\s+/g, ''), '本角色的前后一行（对空白不敏感）').toContain('step-high→step-low');
    expect(t, 'warnings 原文').toContain('WARN 执行端已固定，切换不影响正在运行的 attempt');
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
  });

  it('预览失败：底部显示错误原文，确认…不可点', async () => {
    previewFail = true;
    await mountApp('#/roles');
    await openForm('execution');
    await sleep(450);
    await flush();
    const d = needDlg();
    expect(text(d), '错误原文').toContain('ERROR 预览不合格：参数不符合组合规则');
    expect(btnIn(d, '确认…').disabled).toBe(true);
  });
});

describe('真实模式：确认发 POST /api/v1/roles/<role>', () => {
  beforeEach(() => {
    gets = []; posts = []; previewFail = false;
    rolesData = REAL_ROLES;
    profilesData = REAL_PROFILES;
    previewBody = basePreview();
    previewCommand = ['config', 'role', 'set', 'execution', 'step-low', '--dry-run', '--json'];
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('execution 换 profile：正文恰好 target + confirmation，role 不进正文；写完重读', async () => {
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    await openForm('execution');
    const profile = selectByLabel(needDlg(), 'profile');
    fireEvent.change(profile, { target: { value: optionValueByLabel(profile, 'step-low') } });
    await flush();
    await sleep(450);
    await flush();
    await confirmWrite('execution');
    const writes = posts.filter((p) => p.path === '/api/v1/roles/execution');
    expect(writes.length, '只发一次角色写路由').toBe(1);
    expect(writes[0].body, '正文恰好 target + confirmation').toEqual({ target: 'step-low', confirmation: 'c-real-1' });
    expect(text(document.body)).toContain('已改角色绑定 execution');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '写完重读（getRoles 次数增加）').toBeGreaterThan(rolesBefore);
  });

  it('scheduler_agent 保持无头：cadence_seconds 原样传回且是 JSON 数字；变化摘要带间隔', async () => {
    await mountApp('#/roles');
    await openForm('scheduler_agent');
    await sleep(450);
    await flush();
    const prev = posts.find((p) => p.path === '/api/v1/preview');
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).args, '预览与执行同一份参数规则').toEqual({ role: 'scheduler_agent', target: 'step-high', cadence_seconds: 3600 });
    await confirmWrite('scheduler_agent');
    const writes = posts.filter((p) => p.path === '/api/v1/roles/scheduler_agent');
    expect(writes[0].body).toEqual({ target: 'step-high', cadence_seconds: 3600, confirmation: 'c-real-1' });
    expect(typeof (writes[0].body as any).cadence_seconds, 'cadence_seconds 是 JSON 数字').toBe('number');
    expect(text(document.body)).toContain('已改角色绑定 scheduler_agent');
  });

  it('planning_review 保持交互式宿主带 host；切到无头不带 host，target 是预填的第一个候选', async () => {
    await mountApp('#/roles');
    await openForm('planning_review');
    await sleep(450);
    await flush();
    await confirmWrite('planning_review');
    let writes = posts.filter((p) => p.path === '/api/v1/roles/planning_review');
    expect(writes[0].body, '仍选交互式宿主 → 带上现有 host').toEqual({ target: 'interactive_host', host: 'claude-code', confirmation: 'c-real-1' });
    await openForm('planning_review');
    const mode = selectByLabel(needDlg(), '模式');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '无头') } });
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    expect(qa(profile, 'option').map((o: any) => o.value), '候选按输入顺序、滤掉 _ 开头').toEqual(['step-high', 'step-low']);
    expect(profile.value, '现有绑定没有 profile → 预填第一个候选').toBe('step-high');
    await sleep(450);
    await flush();
    await confirmWrite('planning_review');
    writes = posts.filter((p) => p.path === '/api/v1/roles/planning_review');
    expect(writes[1].body, '切到无头不带 host').toEqual({ target: 'step-high', confirmation: 'c-real-1' });
  });

  it('scheduler_agent 切到关闭：不带 cadence_seconds', async () => {
    await mountApp('#/roles');
    await openForm('scheduler_agent');
    const mode = selectByLabel(needDlg(), '模式');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '关闭') } });
    await flush();
    await sleep(450);
    await flush();
    await confirmWrite('scheduler_agent');
    const writes = posts.filter((p) => p.path === '/api/v1/roles/scheduler_agent');
    expect(writes[0].body, '切到别的模式不带 cadence_seconds').toEqual({ target: 'disabled', confirmation: 'c-real-1' });
  });
});

describe('真实模式：没有已登记的 profile', () => {
  beforeEach(() => {
    gets = []; posts = []; previewFail = false;
    rolesData = REAL_ROLES;
    profilesData = EMPTY_PROFILES;
    previewBody = basePreview();
    previewCommand = ['config', 'role', 'set', 'planning_review', 'interactive_host', '--dry-run', '--json'];
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('execution 只允许无头 → 入口禁用并悬停出原因句；其余三个角色模式下拉没有无头，原因句在 help 里', async () => {
    await mountApp('#/roles');
    const b = btnIn(card('execution'), CHANGE);
    expect(b.disabled, 'execution 只允许无头、无候选 → 入口禁用').toBe(true);
    expect(await tipOf(card('execution') as HTMLElement, CHANGE), '悬停出原因句（逐字）').toBe(REASON_NO_PROFILES);
    for (const role of ['planning_review', 'contract', 'scheduler_agent']) {
      expect(btnIn(card(role), CHANGE).disabled, role + ' 仍可切到非无头模式 → 入口可点').toBe(false);
      const d = await openForm(role);
      const mode = selectByLabel(d, '模式');
      expect(qa(mode, 'option').map(text), role + ' 的模式下拉没有无头').toEqual(allowedModes(role).filter((m) => m !== 'headless').map(modeName));
      expect(text(d), role + ' 原因句可见（Select 的 help）').toContain(REASON_NO_PROFILES);
      expect(mode.getAttribute('aria-describedby'), 'help 接到 aria-describedby').toBeTruthy();
      fireEvent.click(btnIn(d, '取消'));
      await flush();
    }
  });
});

describe('reload 传到表单（写完重读整页）', () => {
  beforeEach(() => {
    gets = []; posts = []; previewFail = false;
    rolesData = REAL_ROLES;
    profilesData = REAL_PROFILES;
    previewBody = basePreview();
    previewCommand = ['config', 'role', 'set', 'execution', 'step-high', '--dry-run', '--json'];
    setLiveClientForTests(fake);
    setConnectionState('connected');
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });

  it('成功后调 reload（roles 与 profiles 一起刷新）', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(
      <RoleBindAction
        role="execution"
        roleLabel="执行端"
        modes={[{ value: 'headless', label: '无头' }]}
        candidates={['step-high', 'step-low']}
        binding={{ mode: 'headless', profile: 'step-high', host: null, cadenceSeconds: null }}
        reload={reload}
      />,
    );
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok → 可确认').toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    await sleep(120);
    await flush();
    expect(reload, '成功后 reload').toHaveBeenCalled();
    expect(text(document.body)).toContain('已改角色绑定 execution');
  });
});
