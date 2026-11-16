// 岗位写路由与预览映射的自测（T044 A 片）：只经 setLiveClientForTests 注入假服务，打交道的是真实的 api.ts。
// 覆盖 hub_changes / running_turns 的逐字段映射与缺键兜底（D01）、unreadable 照旧并入 notes（T037 的既有行为）、
// setHubRole / unsetHubRole 的路由与正文（D03、D11）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  preview,
  setHubRole,
  unsetHubRole,
  type Envelope,
  type HubChangeFallback,
  type HubChangeSide,
  type PreviewData,
} from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const CONF = 'conf-hub-api-1';

function envelope<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

let previewJson: Record<string, unknown> = {};
const posts: Array<{ path: string; body: unknown }> = [];

const fake: LiveClient = {
  get: () => Promise.reject(new Error('本自测没有编排 get')),
  post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const reply = { status: 200, body: envelope({ preview: previewJson, confirmation: CONF }, ['config', 'hub', 'set']) };
      return Promise.resolve(reply as unknown as { status: number; body: Envelope<T> });
    }
    return Promise.resolve({ status: 200, body: envelope(null) as unknown as Envelope<T> });
  },
  getRaw: () => Promise.reject(new Error('本自测没有编排 getRaw')),
};

async function readPreview(args: Record<string, string>): Promise<PreviewData> {
  const reply = await preview('hub.set', args);
  expect(reply.status).toBe(200);
  expect(reply.body.ok).toBe(true);
  expect(reply.body.data).not.toBeNull();
  return reply.body.data as PreviewData;
}

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

describe('预览的 hub_changes 映射（D01）', () => {
  beforeEach(() => {
    posts.length = 0;
    previewJson = {};
    setLiveClientForTests(fake);
  });
  afterEach(() => setLiveClientForTests(undefined));

  it('逐字段对上服务给的形状（post、两侧的 source/六字段/替补）', async () => {
    previewJson = {
      binding_changes: [], resources: [{ resource: 'hub' }], notes: ['note-1'], warnings: [],
      running_attempts: [], needs_yes: true,
      hub_changes: [{ post: 'contract', before: CONTRACT_BEFORE, after: STEP_HIGH_AFTER }],
      running_turns: [],
    };
    const data = await readPreview({ post: 'contract', profile: 'step-high' });
    expect(data.hub_changes).toEqual([{ post: 'contract', before: CONTRACT_BEFORE, after: STEP_HIGH_AFTER }]);
    expect(data.needs_yes).toBe(true);
  });

  it('post 不是字符串的项整项跳过；侧与替补形状不对归 null；running_turns 只留字符串项', async () => {
    previewJson = {
      binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false,
      hub_changes: [
        { post: 7, before: null, after: null },
        { post: 'gate', before: 'not-object', after: { source: 'weird', profile: 1, runtime: 'pi', adapter: 'pi', provider: null, model: null, thinking: null, fallback: 'not-object' } },
      ],
      running_turns: ['审核端（audit）：2 个回合在跑', 5, null],
    };
    const data = await readPreview({ post: 'contract', profile: 'step-high' });
    expect(data.hub_changes).toHaveLength(1);
    expect(data.hub_changes[0]).toEqual({
      post: 'gate',
      before: null,
      after: { source: null, profile: null, runtime: 'pi', adapter: 'pi', provider: null, model: null, thinking: null, fallback: null },
    });
    expect(data.running_turns).toEqual(['审核端（audit）：2 个回合在跑']);
  });

  it('整项不是对象同样跳过；一侧里字段缺失归 null（不崩）', async () => {
    previewJson = {
      binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false,
      hub_changes: [null, 'x', { post: 'audit', before: { source: 'default' } }],
      running_turns: 'not-array',
    };
    const data = await readPreview({ post: 'contract', profile: 'step-high' });
    expect(data.hub_changes).toEqual([
      {
        post: 'audit',
        before: { source: 'default', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null },
        after: null,
      },
    ]);
    expect(data.running_turns).toEqual([]);
  });

  it('缺 hub_changes / running_turns 键时两个字段是空数组，不抛错', async () => {
    previewJson = { binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false };
    const data = await readPreview({ post: 'contract', profile: 'step-high' });
    expect(data.hub_changes).toEqual([]);
    expect(data.running_turns).toEqual([]);
  });

  it('notes 仍并入 unreadable（T037 的既有行为照旧）', async () => {
    previewJson = {
      binding_changes: [], resources: [], notes: ['note-1'], unreadable: ['状态/attempt-9'], warnings: [],
      running_attempts: [], needs_yes: false, hub_changes: [], running_turns: [],
    };
    const data = await readPreview({ post: 'contract', profile: 'step-high' });
    expect(data.notes).toEqual(['note-1', '状态/attempt-9']);
  });
});

describe('岗位写路由与正文（D03、D11）', () => {
  beforeEach(() => {
    posts.length = 0;
    previewJson = {};
    setLiveClientForTests(fake);
  });
  afterEach(() => setLiveClientForTests(undefined));

  it('setHubRole：POST /api/v1/hub/roles/<post>，正文带 profile、fallback 与确认号', async () => {
    await setHubRole({ post: 'contract', profile: 'step-high', fallback: 'step-high' }, 'c1');
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/contract');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', fallback: 'step-high', confirmation: 'c1' });
  });

  it('fallback 没给或是空串时正文里没有这个键', async () => {
    await setHubRole({ post: 'audit', profile: 'step-high' }, 'c2');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: 'c2' });
    await setHubRole({ post: 'gate', profile: 'step-high', fallback: '' }, 'c4');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: 'c4' });
  });

  it('unsetHubRole：POST /api/v1/hub/roles/<post>/unset，正文只有确认号', async () => {
    await unsetHubRole('contract', 'c3');
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/contract/unset');
    expect(posts[posts.length - 1].body).toEqual({ confirmation: 'c3' });
  });
});
