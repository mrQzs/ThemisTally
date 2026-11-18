// 两个改绑定表单「每次打开都按当时的绑定预填」的组件测试（本片）：直接渲染入口组件 HubBindAction /
// RoleBindAction（不挂整页 App），用 RTL 的 rerender 换 props 模拟「别的写入口改了绑定、重读之后 props
// 变了」，用 setLiveClientForTests 注入假服务记录预览请求与写请求。断言打在真实的两个表单与 useWriteFlow
// 上，不 mock 被测组件；等 300ms 防抖用真实计时器 sleep(450)。
// 情形 (c) 不能只断言 select.value：受控 select 的 value 不等于任何 option 时 react-dom 会把第一个未禁用
// 的 option 设成 selected，旧代码那样也读得出「对」的值；所以同时断言预览请求的 args 与 [确认…] 可点。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { HubBindAction } from '../src/writes/HubBindForm';
import { RoleBindAction } from '../src/writes/RoleBindForm';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const BIND = '改绑定…';
const CHANGE = '更改…';
const REASON_NO_PROFILES = '没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
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
function lastPreview(): { path: string; body: any } {
  const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
  expect(prev, '应发过预览请求').toBeTruthy();
  return prev!;
}

// ---- 假服务：读名册（写流程预览与重读各读一次）、预览按 action 回命令、写路由回成功信封 ----

const HUB_ROLES = { posts: [{ post: 'contract', source: 'config', profile: 'quizs-m9', fallback: { profile: 'step-high' } }] };
const ROLES = { roles: [{ role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' } }] };
const HUB_PREVIEW_COMMAND = ['config', 'hub', 'set', 'contract', 'quizs-m9', '--fallback=step-high', '--dry-run', '--json'];
const ROLE_PREVIEW_COMMAND = ['config', 'role', 'set', 'execution', 'step-high', '--dry-run', '--json'];

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

let posts: Array<{ path: string; body: any }> = [];

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES));
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const action = (body as any).action;
      const command = action === 'hub.set' ? HUB_PREVIEW_COMMAND : ROLE_PREVIEW_COMMAND;
      const preview = {
        binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [],
        running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: okEnv({ preview, confirmation: 'c-real-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'hub', 'set']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  posts = [];
  setLiveClientForTests(fake);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

// ---- HubBindForm：每次打开都按当时的 props 重新预填 ----

function hubProps(over: Record<string, unknown> = {}): any {
  return {
    post: 'contract',
    postLabel: '合同端',
    mainCandidates: ['quizs-m9', 'step-high', 'step-low'],
    fallbackCandidatesFor: (m: string) => (m === 'quizs-m9' ? ['step-high', 'step-low'] : []),
    source: 'config',
    mainProfile: 'quizs-m9',
    fallbackProfile: 'step-high',
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

describe('HubBindForm：每次打开都按当时的绑定预填', () => {
  it('(a) 改主选为非 quizs、点取消、再开 → 主选与替补回到现有绑定，替补可选', async () => {
    const r = render(<HubBindAction {...hubProps()} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const main = selectByLabel(needDlg(), '主绑定');
    expect(main.value, '预填现有主绑定').toBe('quizs-m9');
    fireEvent.change(main, { target: { value: 'step-high' } });
    await flush();
    const fb = selectByLabel(needDlg(), '替补');
    expect(fb.disabled, '主选换成非 quizs → 替补禁用（既有行为）').toBe(true);
    expect(fb.value, '替补随之清空（既有行为）').toBe('');
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '主绑定').value, '再开 → 主选回到现有绑定（未保存取值已丢弃）').toBe('quizs-m9');
    const fb2 = selectByLabel(d, '替补');
    expect(fb2.disabled, '主选仍是 quizs → 替补可选').toBe(false);
    expect(fb2.value, '再开 → 替补回到现有绑定').toBe('step-high');
  });

  it('(b) rerender 换了主绑定再开 → 按新绑定预填，预览请求的 args 是新绑定', async () => {
    const p = hubProps();
    const r = render(<HubBindAction {...p} />);
    r.rerender(<HubBindAction {...p} mainProfile="step-high" fallbackProfile={null} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '主绑定').value, 'props 变了再开 → 预填新主绑定').toBe('step-high');
    expect(selectByLabel(d, '替补').value, '新绑定没有替补 → 空').toBe('');
    await sleep(450);
    await flush();
    const prev = lastPreview();
    expect((prev.body as any).args.profile, '预览请求的 args 按新绑定').toBe('step-high');
    expect((prev.body as any).args.fallback, '替补为空不带 fallback').toBeUndefined();
  });

  it('(c) 现有主绑定不在候选里（预填第一个），rerender 加进候选后再开 → 预填现有主绑定；预览 args 与确认…可点', async () => {
    const p = hubProps({ mainCandidates: ['step-high', 'step-low'], fallbackProfile: null });
    const r = render(<HubBindAction {...p} />);
    r.rerender(<HubBindAction {...p} mainCandidates={['quizs-m9', 'step-high', 'step-low']} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '现有主绑定进了候选 → 预填它').toBe('quizs-m9');
    await sleep(450);
    await flush();
    const prev = lastPreview();
    expect((prev.body as any).args.profile, '预览请求的 args 是现有主绑定').toBe('quizs-m9');
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
  });

  it('(d) 确认：先关表单再开写确认框，发 POST /api/v1/hub/roles/contract，成功轻提示与 reload；再开按新绑定预填', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<HubBindAction {...hubProps({ reload })} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok → 表单里的确认… 可点').toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '表单已关上，写确认框开上').toContain('改绑定 contract？');
    expect(qa(cd, 'select').length, '写确认框里没有表单字段').toBe(0);
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = posts.filter((x) => x.path.indexOf('/api/v1/hub/roles/') === 0);
    expect(writes.length, '只发一次岗位写路由').toBe(1);
    expect(writes[0].path).toBe('/api/v1/hub/roles/contract');
    expect(writes[0].body.profile).toBe('quizs-m9');
    expect(writes[0].body.fallback).toBe('step-high');
    expect(typeof writes[0].body.confirmation).toBe('string');
    expect(text(document.body), '成功轻提示').toContain('已改绑定 contract');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    r.rerender(<HubBindAction {...hubProps({ reload, mainProfile: 'step-low', fallbackProfile: null })} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '写完重读后再开 → 按新绑定预填').toBe('step-low');
  });

  it('(e) 再开时底部先「预览中…」、确认… 灰着；新预览回来才可点；预览请求多一次', async () => {
    const r = render(<HubBindAction {...hubProps()} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled, '第一次打开：新预览回来后可点').toBe(false);
    const before = posts.filter((x) => x.path === '/api/v1/preview').length;
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(text(d), '再开先显示预览中…（不显示上一次的预览）').toContain('预览中…');
    expect(btnIn(d, '确认…').disabled, '新预览回来之前确认… 灰着').toBe(true);
    await sleep(450);
    await flush();
    expect(text(needDlg()), '新预览回来').toContain('config hub set contract quizs-m9 --fallback=step-high');
    expect(btnIn(needDlg(), '确认…').disabled, '新预览回来后可点').toBe(false);
    expect(posts.filter((x) => x.path === '/api/v1/preview').length, '再开又发一次预览').toBe(before + 1);
  });

  it('表单开着时 props 变了：不重置用户正在改的字段', async () => {
    const p = hubProps();
    const r = render(<HubBindAction {...p} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    fireEvent.change(selectByLabel(needDlg(), '主绑定'), { target: { value: 'step-low' } });
    await flush();
    r.rerender(<HubBindAction {...p} mainProfile="step-high" />);
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '用户正在改的主选不被重置').toBe('step-low');
  });
});

// ---- RoleBindForm：同形五条 ----

function roleProps(over: Record<string, unknown> = {}): any {
  return {
    role: 'execution',
    roleLabel: '执行端',
    modes: [{ value: 'headless', label: '无头' }],
    candidates: ['step-high', 'step-low'],
    binding: { mode: 'headless', profile: 'step-high', host: null, cadenceSeconds: null },
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

function planningProps(over: Record<string, unknown> = {}): any {
  return {
    role: 'planning_review',
    roleLabel: '规划审核端',
    modes: [{ value: 'interactive_host', label: '交互式宿主' }, { value: 'headless', label: '无头' }],
    candidates: [],
    binding: { mode: 'interactive_host', profile: null, host: 'claude-code', cadenceSeconds: null },
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

describe('RoleBindForm：每次打开都按当时的绑定预填', () => {
  it('(a) execution 改 profile、点取消、再开 → 回到现有 profile', async () => {
    const r = render(<RoleBindAction {...roleProps()} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('改绑定：执行端');
    expect(selectByLabel(d, 'profile').value, '预填现有 profile').toBe('step-high');
    fireEvent.change(selectByLabel(d, 'profile'), { target: { value: 'step-low' } });
    await flush();
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '再开 → 回到现有 profile（未保存取值已丢弃）').toBe('step-high');
  });

  it('(a2) planning_review 切无头、点取消、再开 → 回到交互式宿主（没有 profile 下拉）', async () => {
    const p = planningProps({ candidates: ['step-high', 'step-low'] });
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const mode = selectByLabel(needDlg(), '模式');
    expect(mode.value, '预填现有模式').toBe('interactive_host');
    fireEvent.change(mode, { target: { value: 'headless' } });
    await flush();
    expect(qa(needDlg(), 'select').length, '无头 → 有 profile 下拉').toBe(2);
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '模式').value, '再开 → 回到交互式宿主').toBe('interactive_host');
    expect(qa(d, 'select').length, '不是无头 → 没有 profile 下拉').toBe(1);
  });

  it('(b) rerender 换了 binding.profile 再开 → 按新绑定预填，预览请求的 target 是新 profile', async () => {
    const p = roleProps();
    const r = render(<RoleBindAction {...p} />);
    r.rerender(
      <RoleBindAction {...p} binding={{ mode: 'headless', profile: 'step-low', host: null, cadenceSeconds: null }} />,
    );
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, 'props 变了再开 → 预填新 profile').toBe('step-low');
    await sleep(450);
    await flush();
    const prev = lastPreview();
    expect((prev.body as any).args.target, '预览请求的 target 是新 profile').toBe('step-low');
    expect((prev.body as any).args.role).toBe('execution');
    expect((prev.body as any).args.host, '现有绑定 host 为 null → 不带 host').toBeUndefined();
  });

  it('(c) 起初没有候选（无头拿掉、help 是原因句）；给候选后再开选无头 → target 是第一个候选，确认…可点', async () => {
    const p = planningProps();
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const first = needDlg();
    expect(qa(selectByLabel(first, '模式'), 'option').map((o: any) => o.value), '没有候选 → 无头拿掉').toEqual(['interactive_host']);
    expect(text(first), '原因句在 Select 的 help 里').toContain(REASON_NO_PROFILES);
    fireEvent.click(btnIn(first, '取消'));
    await flush();
    r.rerender(<RoleBindAction {...p} candidates={['quizs-m9', 'step-high']} />);
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const mode = selectByLabel(needDlg(), '模式');
    expect(mode.value, '再开仍预填现有模式').toBe('interactive_host');
    expect(qa(mode, 'option').map((o: any) => o.value), '有候选 → 无头回来了').toEqual(['interactive_host', 'headless']);
    fireEvent.change(mode, { target: { value: 'headless' } });
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, 'profile 预填第一个候选').toBe('quizs-m9');
    await sleep(450);
    await flush();
    const prev = lastPreview();
    expect((prev.body as any).args.target, '预览请求的 target 是第一个候选').toBe('quizs-m9');
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
  });

  it('(d) 确认：先关表单再开写确认框，发 POST /api/v1/roles/execution，成功轻提示与 reload；再开按新绑定预填', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<RoleBindAction {...roleProps({ reload })} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok → 表单里的确认… 可点').toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '表单已关上，写确认框开上').toContain('改角色绑定 execution？');
    expect(qa(cd, 'select').length, '写确认框里没有表单字段').toBe(0);
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = posts.filter((x) => x.path === '/api/v1/roles/execution');
    expect(writes.length, '只发一次角色写路由').toBe(1);
    expect(writes[0].body, '正文恰好 target + confirmation').toEqual({ target: 'step-high', confirmation: 'c-real-1' });
    expect(text(document.body), '成功轻提示').toContain('已改角色绑定 execution');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    r.rerender(
      <RoleBindAction
        {...roleProps({ reload, binding: { mode: 'headless', profile: 'step-low', host: null, cadenceSeconds: null } })}
      />,
    );
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '写完重读后再开 → 按新绑定预填').toBe('step-low');
  });

  it('(e) 再开时底部先「预览中…」、确认… 灰着；新预览回来才可点；预览请求多一次', async () => {
    const r = render(<RoleBindAction {...roleProps()} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled, '第一次打开：新预览回来后可点').toBe(false);
    const before = posts.filter((x) => x.path === '/api/v1/preview').length;
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(text(d), '再开先显示预览中…（不显示上一次的预览）').toContain('预览中…');
    expect(btnIn(d, '确认…').disabled, '新预览回来之前确认… 灰着').toBe(true);
    await sleep(450);
    await flush();
    expect(text(needDlg()), '新预览回来').toContain('config role set execution step-high');
    expect(btnIn(needDlg(), '确认…').disabled, '新预览回来后可点').toBe(false);
    expect(posts.filter((x) => x.path === '/api/v1/preview').length, '再开又发一次预览').toBe(before + 1);
  });

  it('表单开着时 props 变了：不重置用户正在改的字段', async () => {
    const p = roleProps();
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    fireEvent.change(selectByLabel(needDlg(), 'profile'), { target: { value: 'step-low' } });
    await flush();
    r.rerender(<RoleBindAction {...p} candidates={['quizs-m9', 'step-high', 'step-low']} />);
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '用户正在改的 profile 不被重置').toBe('step-low');
  });
});
