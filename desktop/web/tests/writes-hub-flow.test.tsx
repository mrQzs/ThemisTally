// 岗位写流程的自测（T044 A 片，D03、D04、D05、D07、D11、D12）：真实模式只经 setLiveClientForTests 注入假服务，
// 挂载的是真实的 useWriteFlow 与真实的 WriteConfirmDialog；桩情景直接调 api.preview（liveClient() 为 null）。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, HubChangeFallback, HubChangeSide } from '../src/api';
import { preview } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { useWriteFlow, type WriteSpec } from '../src/writes/useWriteFlow';
import { WriteFlow } from '../src/writes/WriteConfirmDialog';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';

// T040 锁定的原因句（D04：一字不改，只放宽出现条件）。
const REASON = '有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。';
// 在跑的回合那一行的后半句（D04）。
const TURNS_NOTE = '在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。';
const RUNNING_TURN = '审核端（audit）：2 个回合在跑';
const SAME_MODEL_WARN = '合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效';

const CONF = 'conf-hub-flow-1';

const side = (o: Partial<HubChangeSide> = {}): HubChangeSide => ({
  source: 'config', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null, ...o,
});
const fb = (o: Partial<HubChangeFallback> = {}): HubChangeFallback => ({
  profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, ...o,
});
const CONTRACT_BEFORE = side({
  source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs',
  provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
  fallback: fb({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
});
const STEP_HIGH_AFTER = side({
  source: 'config', profile: 'step-high', runtime: 'pi', adapter: 'pi',
  provider: 'bb', model: 'step-5-preview', thinking: 'high',
});

function basePreview(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [{ resource: 'hub' }], notes: [], unreadable: [], warnings: [],
    running_attempts: [], running_turns: [], needs_yes: false,
    hub_changes: [{ post: 'contract', before: CONTRACT_BEFORE, after: STEP_HIGH_AFTER }],
    ...over,
  };
}

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;

const gets: string[] = [];
const posts: Array<{ path: string; body: unknown }> = [];
let spec: WriteSpec = { action: 'hub.set', args: { post: 'contract', profile: 'step-high' } };
let previewJson: Record<string, unknown> = basePreview();
let execPlan: { status: number; body: Envelope<null> } | null = null;

const fake: LiveClient = {
  get<T>(path: string): Promise<Envelope<T>> {
    gets.push(path);
    if (path === '/api/v1/hub/roles') {
      return Promise.resolve({ ok: true, exit_code: 0, data: HUB_ROLES_POSTS, output: [], messages: [], command: [], elapsed_ms: 0 } as unknown as Envelope<T>);
    }
    return Promise.resolve({ ok: false, exit_code: 2, data: null, output: [], messages: [`本自测没有编排 ${path} 的应答`], command: [], elapsed_ms: 0 } as unknown as Envelope<T>);
  },
  post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const s = spec.args as Record<string, string>;
      const command = spec.action === 'hub.set'
        ? ['config', 'hub', 'set', s.post, s.profile]
        : ['config', 'hub', 'unset', s.post];
      return Promise.resolve({ status: 200, body: { ok: true, exit_code: 0, data: { preview: previewJson, confirmation: CONF }, output: [], messages: [], command, elapsed_ms: 0 } as unknown as Envelope<T> });
    }
    if (execPlan) return Promise.resolve({ status: execPlan.status, body: execPlan.body as unknown as Envelope<T> });
    return Promise.resolve({ status: 500, body: { ok: false, exit_code: 5, data: null, output: [], messages: ['本自测没有编排执行应答'], command: [], elapsed_ms: 0 } as unknown as Envelope<T> });
  },
  getRaw: () => Promise.resolve({ status: 404, body: null }),
};

function Harness() {
  const { start, flow } = useWriteFlow();
  return (
    <>
      <button onClick={() => start(spec)}>go</button>
      <WriteFlow flow={flow} />
    </>
  );
}

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
async function openFlow() {
  render(<Harness />);
  await settle();
  fireEvent.click(btn(document.body, 'go') as HTMLButtonElement);
  await settle();
  dlgText();
}
async function confirmNow() {
  fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
  await settle();
  await advance(30);
  await settle();
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  gets.length = 0;
  posts.length = 0;
  execPlan = null;
  previewJson = basePreview();
  spec = { action: 'hub.set', args: { post: 'contract', profile: 'step-high' } };
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('岗位写路由（D03、D11）', () => {
  it('hub.set：预览与快照读走 getHubRoles，确认发岗位路由，没有插件启停的路由', async () => {
    execPlan = { status: 200, body: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: ['config', 'hub', 'set', 'contract', 'step-high'], elapsed_ms: 0 } };
    await openFlow();
    expect(gets).toContain('/api/v1/hub/roles');
    expect(gets).not.toContain('/api/v1/plugins');
    expect(dlgText()).toContain('改绑定 contract？');
    await confirmNow();
    const paths = posts.map((p) => p.path);
    expect(paths.filter((p) => p !== '/api/v1/preview')).toEqual(['/api/v1/hub/roles/contract']);
    expect(paths.some((p) => p.startsWith('/api/v1/plugins/'))).toBe(false);
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: CONF });
    expect(bodyText()).toContain('已改绑定 contract');
  });

  it('hub.set 带替补：正文带 fallback', async () => {
    spec = { action: 'hub.set', args: { post: 'contract', profile: 'step-high', fallback: 'step-high' } };
    execPlan = { status: 200, body: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 } };
    await openFlow();
    await confirmNow();
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/contract');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', fallback: 'step-high', confirmation: CONF });
  });

  it('hub.unset：确认发 .../unset，正文只有确认号', async () => {
    spec = { action: 'hub.unset', args: { post: 'contract' } };
    execPlan = { status: 200, body: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 } };
    await openFlow();
    expect(dlgText()).toContain('恢复缺省 contract？');
    await confirmNow();
    const paths = posts.map((p) => p.path);
    expect(paths.filter((p) => p !== '/api/v1/preview')).toEqual(['/api/v1/hub/roles/contract/unset']);
    expect(posts[posts.length - 1].body).toEqual({ confirmation: CONF });
    expect(bodyText()).toContain('已恢复缺省 contract');
  });

  it('getHubRoles 读失败：预览阶段显示「读取当前状态失败」，不进可确认状态', async () => {
    const broken: LiveClient = {
      ...fake,
      get: <T,>(path: string) => {
        gets.push(path);
        return Promise.resolve({ ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 读不出来'], command: [], elapsed_ms: 0 } as unknown as Envelope<T>);
      },
    };
    setLiveClientForTests(broken);
    await openFlow();
    expect(dlgText()).toContain('读取当前状态失败');
    expect(posts.filter((p) => p.path !== '/api/v1/preview')).toEqual([]);
  });
});

describe('变化一节的岗位前后对比（D05）', () => {
  it('小标题加四行对比；changes 空且 hubChanges 非空时不显示「预览没有列出变化」', async () => {
    await openFlow();
    const t = dlgText();
    expect(t).toContain('合同端（contract）');
    expect(t).toContain('运行时：quizs · quizs → pi · pi');
    expect(t).toContain('模型：minimax/MiniMax-M3.1-Flash → bb/step-5-preview');
    expect(t).toContain('思考档位：high → high');
    expect(t).toContain('替补：step-high → —');
    expect(t).not.toContain('预览没有列出变化');
  });

  it('缺省一侧标「（默认）」，该侧四行都带', async () => {
    previewJson = basePreview({
      hub_changes: [{
        post: 'exec',
        before: STEP_HIGH_AFTER,
        after: { source: 'default', profile: null, runtime: null, adapter: 'pi', provider: 'cc-switch-step-fun', model: 'step-5-preview', thinking: 'high', fallback: null },
      }],
    });
    await openFlow();
    const t = dlgText();
    expect(t).toContain('执行端（exec）');
    expect(t).toContain('运行时：pi · pi → — · pi（默认）');
    expect(t).toContain('模型：bb/step-5-preview → cc-switch-step-fun/step-5-preview（默认）');
    expect(t).toContain('思考档位：high → high（默认）');
    expect(t).toContain('替补：— → —（默认）');
  });

  it('岗位块用 wf-hub 前缀的类名', async () => {
    await openFlow();
    const d = dlg() as HTMLElement;
    expect(d.querySelector('.wf-hub')).not.toBeNull();
    expect(d.querySelector('.wf-hub__post')?.textContent).toBe('合同端（contract）');
    expect(Array.from(d.querySelectorAll('.wf-hub__line')).length).toBe(4);
  });
});

describe('needs_yes 的两种说法（D04）', () => {
  it('unreadable 有值：原因句逐字排在 notes 第一条', async () => {
    previewJson = basePreview({ needs_yes: true, unreadable: ['状态/attempt-9'], notes: ['另一条说明'] });
    await openFlow();
    const notes = Array.from(document.querySelectorAll('.wf-note')).map((el) => text(el));
    expect(notes.length).toBeGreaterThan(0);
    expect(notes[0]).toBe(REASON);
    expect(dlgText()).toContain('影响与风险');
  });

  it('running_turns 有值：不出原因句，影响与风险逐行显示那句确认话', async () => {
    previewJson = basePreview({ needs_yes: true, running_turns: [RUNNING_TURN] });
    await openFlow();
    const t = dlgText();
    expect(t).not.toContain(REASON);
    expect(t).toContain(`${RUNNING_TURN}。${TURNS_NOTE}`);
    expect(t).toContain('影响与风险');
  });

  it('running_attempts 有值：既有的 attempt 说法照旧，也不出原因句', async () => {
    previewJson = basePreview({ needs_yes: true, running_attempts: ['ui-readonly-api/attempt-001'] });
    await openFlow();
    const t = dlgText();
    expect(t).not.toContain(REASON);
    expect(t).toContain('有 attempt 正在运行：ui-readonly-api/attempt-001。它不受影响，但这次改动需要你确认。');
  });
});

describe('桩的四个岗位情景（D07、D12）', () => {
  beforeEach(() => {
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });
  afterEach(() => {
    window.location.hash = '';
  });

  it('hub-ok 与 hub-unset：与缺省 ok 的行为一致（显式别名）', async () => {
    window.location.hash = '#/p?write=hub-ok';
    const okData = await preview('hub.set', { post: 'contract', profile: 'step-high' });
    expect(okData.status).toBe(200);
    expect(okData.body.data?.hub_changes).toHaveLength(1);
    expect(okData.body.data?.needs_yes).toBe(false);
    expect(okData.body.data?.warnings).toEqual([]);
    window.location.hash = '#/p?write=hub-unset';
    const unsetData = await preview('hub.unset', { post: 'contract' });
    expect(unsetData.body.data?.hub_changes[0].after?.source).toBe('default');
    expect(unsetData.body.data?.hub_changes[0].after?.profile).toBeNull();
  });

  it('hub-warn：warnings 有那条同模型警告', async () => {
    window.location.hash = '#/p?write=hub-warn';
    const data = await preview('hub.set', { post: 'contract', profile: 'step-high' });
    expect(data.body.data?.warnings).toEqual([SAME_MODEL_WARN]);
  });

  it('hub-running：running_turns 有一句且 needs_yes 为真', async () => {
    window.location.hash = '#/p?write=hub-running';
    const data = await preview('hub.set', { post: 'contract', profile: 'step-high' });
    expect(data.body.data?.running_turns).toEqual([RUNNING_TURN]);
    expect(data.body.data?.needs_yes).toBe(true);
  });

  it('hub.unset 的 after 是内核缺省；新写的桩数据里不出现 step-low', async () => {
    window.location.hash = '#/p';
    const data = await preview('hub.unset', { post: 'contract' });
    const after = data.body.data?.hub_changes[0].after;
    expect(after?.source).toBe('default');
    expect(after?.profile).toBeNull();
    expect(after?.adapter).toBe('pi');
    expect(after?.model).toBe('MiniMax-M3.1-Flash');
    expect(JSON.stringify(data.body.data)).not.toContain('step-low');
  });

  it('岗位不在夹具六行里 → hub_changes 是空数组（不崩）', async () => {
    window.location.hash = '#/p';
    const data = await preview('hub.set', { post: 'nope', profile: 'step-high' });
    expect(data.body.data?.hub_changes).toEqual([]);
  });
});
