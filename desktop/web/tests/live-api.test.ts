// api.ts 的真实分支（合同第 8 步）：注入 fake client，逐个读函数断言请求的路径、查询与服务端时限；
// 归一化（kit_version、resource/diff、allowed_permissions）；写函数与 getOperation 走真实路由
// （预览、执行、操作终态，桩分支由 mock/writes.ts 的 ?write= 情景负责）；
// 真实模式下 ?mock= 不生效，夹具分支逐字不变。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

type Call = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };
type PostCall = { path: string; body: unknown; timeoutSeconds: number | undefined };
type RawCall = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };
const calls: Call[] = [];
const posts: PostCall[] = [];
const raws: RawCall[] = [];
let nextData: unknown = { v: 0 };
let nextPost: { status: number; body: Envelope<unknown> } | null = null;
let nextRaw: { status: number; body: unknown } | null = null;
let postError: Error | null = null;

const fakeClient: LiveClient = {
  get<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>> {
    calls.push({ path, query, timeoutSeconds });
    return Promise.resolve({
      ok: true,
      exit_code: 0,
      data: nextData,
      output: [],
      messages: [],
      command: [],
      elapsed_ms: 3,
    }) as Promise<Envelope<T>>;
  },
  post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body, timeoutSeconds });
    if (postError) return Promise.reject(postError);
    const want = nextPost as { status: number; body: Envelope<T> };
    return Promise.resolve({ status: want.status, body: want.body });
  },
  getRaw<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }> {
    raws.push({ path, query, timeoutSeconds });
    const want = nextRaw as { status: number; body: T };
    return Promise.resolve({ status: want.status, body: want.body });
  },
};

beforeEach(() => {
  calls.length = 0;
  posts.length = 0;
  raws.length = 0;
  nextData = { v: 0 };
  nextPost = null;
  nextRaw = null;
  postError = null;
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

type Row = {
  name: string;
  run: () => Promise<Envelope<unknown>>;
  path: string;
  timeout: number;
  query?: Record<string, string | undefined>;
};

const ROWS: Row[] = [
  { name: 'getMeta', run: () => api.getMeta(), path: '/api/v1/meta', timeout: 15 },
  { name: 'getStatus', run: () => api.getStatus(), path: '/api/v1/status', timeout: 30 },
  {
    name: 'getAttempt',
    run: () => api.getAttempt('a/b', 'x?y'),
    path: '/api/v1/attempts/a%2Fb/x%3Fy',
    timeout: 30,
  },
  {
    name: 'readFile(不带 cursor)',
    run: () => api.readFile('t1', 'a1', 'p.md'),
    path: '/api/v1/attempts/t1/a1/file',
    query: { path: 'p.md' },
    timeout: 60,
  },
  {
    name: 'readFile(带 cursor)',
    run: () => api.readFile('t1', 'a1', 'p.md', 'c-1'),
    path: '/api/v1/attempts/t1/a1/file',
    query: { path: 'p.md', cursor: 'c-1' },
    timeout: 60,
  },
  { name: 'getRoles', run: () => api.getRoles(), path: '/api/v1/roles', timeout: 30 },
  { name: 'getProfiles', run: () => api.getProfiles(), path: '/api/v1/profiles', timeout: 30 },
  { name: 'getPresets', run: () => api.getPresets(), path: '/api/v1/presets', timeout: 30 },
  { name: 'getHubRoles', run: () => api.getHubRoles(), path: '/api/v1/hub/roles', timeout: 30 },
  {
    name: 'diffPresets',
    run: () => api.diffPresets('x y', 'z'),
    path: '/api/v1/presets/x%20y/diff/z',
    timeout: 30,
  },
  { name: 'getRuntimes', run: () => api.getRuntimes(), path: '/api/v1/runtimes', timeout: 30 },
  { name: 'getPlugins', run: () => api.getPlugins(), path: '/api/v1/plugins', timeout: 30 },
  { name: 'getHistory', run: () => api.getHistory(), path: '/api/v1/config/history', timeout: 30 },
  { name: 'getUsage', run: () => api.getUsage(), path: '/api/v1/usage', timeout: 120 },
  { name: 'listSecrets', run: () => api.listSecrets(), path: '/api/v1/secrets', timeout: 120 },
  {
    name: 'getHistoryEntry',
    run: () => api.getHistoryEntry(41),
    path: '/api/v1/config/history/41',
    timeout: 30,
  },
  { name: 'getPlugin', run: () => api.getPlugin('docs-checks'), path: '/api/v1/plugins/docs-checks', timeout: 30 },
];

describe('api.ts 的 16 个读函数（注入 fake client）', () => {
  for (const row of ROWS) {
    it(`${row.name} → GET ${row.path}，服务端时限 ${row.timeout}`, async () => {
      const env = await row.run();
      expect(calls.length).toBe(1);
      expect(calls[0].path).toBe(row.path);
      expect(calls[0].timeoutSeconds).toBe(row.timeout);
      if (row.query) {
        expect(calls[0].query).toEqual(row.query);
      } else {
        const query = calls[0].query;
        expect(query == null || Object.keys(query).length === 0).toBe(true);
      }
      if (row.name === 'readFile(不带 cursor)') {
        expect(calls[0].query && calls[0].query.cursor).toBeUndefined();
      }
      expect(env.ok).toBe(true);
    });
  }
});

describe('api.ts 真实分支的归一化', () => {
  it('getMeta：version 带 pi_dispatch 前缀 → kit_version 去掉前缀', async () => {
    nextData = { version: 'pi_dispatch 2.12.0', repo_name: 'demo-repo' };
    const env = await api.getMeta();
    expect(env.data).toEqual({ kit_version: '2.12.0', repo_name: 'demo-repo' });
  });

  it('getMeta：对不上 pi_dispatch 前缀就原样放进 kit_version', async () => {
    nextData = { version: '3.1', repo_name: 'r' };
    const env = await api.getMeta();
    expect(env.data).toEqual({ kit_version: '3.1', repo_name: 'r' });
  });

  it('getHistoryEntry：resource 缺省 config、diff 缺省 null；本机文件条目带 sha', async () => {
    nextData = { number: 7, state: 'published', note: 'n1' };
    const a = await api.getHistoryEntry(7);
    expect(a.data).toEqual({ number: 7, resource: 'config', state: 'published', note: 'n1', diff: null });
    nextData = {
      number: 8,
      resource: 'local',
      state: 'published',
      note: null,
      diff: null,
      before_sha256: 'A',
      after_sha256: 'B',
    };
    const b = await api.getHistoryEntry(8);
    expect(b.data).toEqual({
      number: 8,
      resource: 'local',
      state: 'published',
      note: null,
      diff: null,
      before_sha256: 'A',
      after_sha256: 'B',
    });
  });

  it('getPlugin：allowed_permissions 为 null 时归一化成 []', async () => {
    nextData = { plugin_id: 'x', config: { enabled: null, allowed_permissions: null, missing_permissions: [] } };
    const env = await api.getPlugin('x');
    expect((env.data as { config: { allowed_permissions: string[] } }).config.allowed_permissions).toEqual([]);
  });

  it('真实模式下 ?mock= 的取值一律不生效（注入优先，不读夹具）', async () => {
    window.location.hash = '#/status?mock=error';
    const env = await api.getStatus();
    expect(env.ok).toBe(true);
    expect(calls.length).toBe(1);
    window.location.hash = '#/status?mock=empty';
    const env2 = await api.getStatus();
    expect(env2.ok).toBe(true);
    expect(env2.data).toEqual({ v: 0 });
  });
});

// 服务的内核预览 JSON（键集合照 tests/test_kit_roles.py 钉死的那套）：binding_changes 是
// {role, before, after}，resources 是 {resource, changed, changed_keys}，warnings 已去前缀，另有 unreadable；
// command 不在预览 JSON 里，在信封顶层。
const SERVICE_PREVIEW = {
  action: 'preset.use',
  binding_changes: [
    {
      role: 'execution',
      before: null,
      after: { mode: 'ask', profile: 'step-high', runtime: 'r1', adapter: 'a1', provider: 'prov', model: 'm1', thinking: '' },
    },
    {
      role: 'review',
      before: { mode: 'ask', profile: '', runtime: '', adapter: '', provider: 'Anthropic', model: 'claude-x', thinking: '' },
      after: { mode: 'plan', profile: '', runtime: '', adapter: '', provider: '', model: '', thinking: '' },
    },
    {
      role: 'tools',
      before: { mode: 'ask', profile: '', runtime: '', adapter: '', provider: '', model: 'gpt-x', thinking: '' },
      after: null,
    },
  ],
  changed: true,
  dry_run: true,
  needs_yes: true,
  notes: ['note-1'],
  resources: [
    { resource: 'roles', changed: true, changed_keys: ['execution'] },
    { resource: 'config', changed: true, changed_keys: [] },
    { resource: 'roles', changed: false, changed_keys: [] },
  ],
  running_attempts: ['ui-readonly-api/attempt-001'],
  unreadable: ['读取不到 roles/build'],
  warnings: ['模型 claude-x 不在 pi --list-models 的列表里'],
};

const PREVIEW_COMMAND = ['config', 'preset', 'use', 'default', '--dry-run', '--json'];

function okEnvelopeOf(data: unknown, command: string[] = []): Envelope<unknown> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 7 };
}

function failEnvelopeOf(messages: string[], exitCode: number | null = null): Envelope<unknown> {
  return { ok: false, exit_code: exitCode, data: null, output: [], messages, command: [], elapsed_ms: 3 };
}

describe('api.ts 真实分支：写操作接真实路由（T037）', () => {
  it('preview：POST /api/v1/preview，正文 {action, args}，服务端时限 30 秒', async () => {
    nextPost = { status: 200, body: okEnvelopeOf({ preview: SERVICE_PREVIEW, confirmation: 'c12345' }, PREVIEW_COMMAND) };
    const reply = await api.preview('preset.use', { name: 'default' });
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'preset.use', args: { name: 'default' } });
    expect(posts[0].timeoutSeconds).toBe(30);
    expect(calls.length).toBe(0);
    expect(reply.status).toBe(200);
  });

  it('preview 的参数整理：number 转 JSON 数字（转不成原样传）、空串与空数组不传、数组按顺序原样', async () => {
    nextPost = { status: 200, body: okEnvelopeOf({ preview: SERVICE_PREVIEW, confirmation: 'c2' }, PREVIEW_COMMAND) };
    await api.preview('config.rollback', { number: '41' });
    expect(posts[0].body).toEqual({ action: 'config.rollback', args: { number: 41 } });
    expect(typeof (posts[0].body as { args: { number: unknown } }).args.number).toBe('number');
    await api.preview('config.rollback', { number: 'x4?' });
    expect(posts[1].body).toEqual({ action: 'config.rollback', args: { number: 'x4?' } });
    await api.preview('profile.edit', { profile: 'p1', model: '', thinking: '', credential_env: [] });
    expect(posts[2].body).toEqual({ action: 'profile.edit', args: { profile: 'p1' } });
    await api.preview('profile.add', { profile: 'p2', runtime: 'r', model: 'm', credential_env: ['A', 'B'] });
    expect(posts[3].body).toEqual({
      action: 'profile.add',
      args: { profile: 'p2', runtime: 'r', model: 'm', credential_env: ['A', 'B'] },
    });
    await api.preview('hub.set', { post: 'build', profile: 'step-high', fallback: '' });
    expect(posts[4].body).toEqual({ action: 'hub.set', args: { post: 'build', profile: 'step-high' } });
  });

  it('preview 成功：PreviewData 的映射（from/to 显示格式、resources 不去重、notes 并入 unreadable、command 取信封顶层）', async () => {
    nextPost = { status: 200, body: okEnvelopeOf({ preview: SERVICE_PREVIEW, confirmation: 'c12345' }, PREVIEW_COMMAND) };
    const reply = await api.preview('preset.use', { name: 'default' });
    expect(reply.body.ok).toBe(true);
    const data = reply.body.data as Record<string, unknown>;
    expect(data.binding_changes).toEqual([
      { role: 'execution', from: '—', to: 'step-high' },
      { role: 'review', from: 'Anthropic/claude-x', to: 'plan' },
      { role: 'tools', from: 'gpt-x', to: '—' },
    ]);
    expect(data.resources).toEqual(['roles', 'config', 'roles']);
    expect(data.notes).toEqual(['note-1', '读取不到 roles/build']);
    expect(data.warnings).toEqual(['模型 claude-x 不在 pi --list-models 的列表里']);
    expect(data.running_attempts).toEqual(['ui-readonly-api/attempt-001']);
    expect(data.needs_yes).toBe(true);
    expect(data.command).toEqual(PREVIEW_COMMAND);
    expect(data.confirmation).toBe('c12345');
  });

  it('preview 不成：400/500/503 与 200-ok:false 的信封原样透传，不签发确认号、不改写成 501', async () => {
    const bad400 = failEnvelopeOf(['ERROR: model 不合法']);
    nextPost = { status: 400, body: bad400 };
    const r400 = await api.preview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' });
    expect(r400.status).toBe(400);
    expect(r400.body).toEqual(bad400);
    const bad500 = failEnvelopeOf(['ERROR 内核的预览不合格']);
    nextPost = { status: 500, body: bad500 };
    const r500 = await api.preview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' });
    expect(r500.status).toBe(500);
    expect(r500.body).toEqual(bad500);
    const busy = failEnvelopeOf(['ERROR 服务繁忙，请稍后重试']);
    nextPost = { status: 503, body: busy };
    const r503 = await api.preview('preset.use', { name: 'default' });
    expect(r503.status).toBe(503);
    expect(r503.body).toEqual(busy);
    const kernelFail = {
      ok: false,
      exit_code: 2,
      data: null,
      output: [],
      messages: ['ERROR 预览不合格：参数不符合组合规则'],
      command: PREVIEW_COMMAND,
      elapsed_ms: 9,
    };
    nextPost = { status: 200, body: kernelFail };
    const r200 = await api.preview('preset.use', { name: 'default' });
    expect(r200.status).toBe(200);
    expect(r200.body).toEqual(kernelFail);
  });

  it('preview：200 且 ok 但 data 缺 confirmation → 信封原样透传（不签发确认号）', async () => {
    const env = okEnvelopeOf({ preview: SERVICE_PREVIEW }, PREVIEW_COMMAND);
    nextPost = { status: 200, body: env };
    const reply = await api.preview('preset.use', { name: 'default' });
    expect(reply.status).toBe(200);
    expect(reply.body).toEqual(env);
  });

  it('preview 没有回应：reject（「预览失败：服务没有回应」的那条路）', async () => {
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    await expect(api.preview('preset.use', { name: 'default' })).rejects.toThrow('连不上本机服务');
  });

  it('getOperation：GET /api/v1/operations/<编码后的号>、时限 30 秒；200 包成 ok 信封、data 是八键视图', async () => {
    const opBody = {
      id: 'op 1/x',
      action: 'config rollback',
      state: 'succeeded',
      reason: null,
      created_ms: 1,
      started_ms: 2,
      finished_ms: 3,
      envelope: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: ['config', 'rollback', '41'], elapsed_ms: 5 },
    };
    nextRaw = { status: 200, body: opBody };
    const reply = await api.getOperation('op 1/x');
    expect(raws.length).toBe(1);
    expect(raws[0].path).toBe('/api/v1/operations/op%201%2Fx');
    expect(raws[0].timeoutSeconds).toBe(30);
    expect(posts.length).toBe(0);
    expect(reply.status).toBe(200);
    expect(reply.body.ok).toBe(true);
    expect(reply.body.exit_code).toBe(0);
    expect(reply.body.messages).toEqual([]);
    expect(reply.body.data).toEqual(opBody);
  });

  it('getOperation：envelope 不是合法七字段信封取 null；正文不是对象或缺 state 时 data 取 null', async () => {
    nextRaw = {
      status: 200,
      body: { id: 'o2', action: 'x', state: 'failed', reason: 'exit', created_ms: 1, started_ms: 2, finished_ms: 3, envelope: { foo: 1 } },
    };
    const a = await api.getOperation('o2');
    expect(a.status).toBe(200);
    const view = a.body.data as Record<string, unknown>;
    expect(view.id).toBe('o2');
    expect(view.state).toBe('failed');
    expect(view.reason).toBe('exit');
    expect(view.envelope).toBeNull();
    nextRaw = { status: 200, body: 'plain' };
    const b = await api.getOperation('o3');
    expect(b.status).toBe(200);
    expect(b.body.ok).toBe(true);
    expect(b.body.data).toBeNull();
    nextRaw = { status: 200, body: { id: 'o4', action: 'x' } };
    const c = await api.getOperation('o4');
    expect(c.body.data).toBeNull();
  });

  it('getOperation 404：状态码与信封原样透传（「结果未知」与「过期」分得开）', async () => {
    const nf = failEnvelopeOf(['ERROR: 没有这个操作']);
    nextRaw = { status: 404, body: nf };
    const reply = await api.getOperation('gone');
    expect(reply.status).toBe(404);
    expect(reply.body).toEqual(nf);
    expect(raws.length).toBe(1);
  });

  const WRITE_ROWS: Array<{ name: string; run: () => Promise<{ status: number; body: Envelope<unknown> }>; path: string; body: unknown }> = [
    { name: 'usePreset', run: () => api.usePreset('economy', 'c1'), path: '/api/v1/presets/economy/use', body: { confirmation: 'c1' } },
    { name: 'setPluginEnabled(true)', run: () => api.setPluginEnabled('decisions', true, 'c1'), path: '/api/v1/plugins/decisions/enable', body: { confirmation: 'c1' } },
    { name: 'setPluginEnabled(false)', run: () => api.setPluginEnabled('decisions', false, 'c1'), path: '/api/v1/plugins/decisions/disable', body: { confirmation: 'c1' } },
    { name: 'removePreset（路径段编码）', run: () => api.removePreset('a b/c', 'c1'), path: '/api/v1/presets/a%20b%2Fc/remove', body: { confirmation: 'c1' } },
    { name: 'removeProfile', run: () => api.removeProfile('p1', 'c1'), path: '/api/v1/profiles/p1/remove', body: { confirmation: 'c1' } },
    { name: 'removeRuntime', run: () => api.removeRuntime('r1', 'c1'), path: '/api/v1/runtimes/r1/remove', body: { confirmation: 'c1' } },
    { name: 'rollback', run: () => api.rollback(41, 'c1'), path: '/api/v1/config/rollback/41', body: { confirmation: 'c1' } },
    {
      name: 'addProfile（空串与空数组不传）',
      run: () => api.addProfile({ profile: 'p2', runtime: 'r', model: 'm', thinking: '', credential_env: [] }, 'c1'),
      path: '/api/v1/profiles/p2/add',
      body: { confirmation: 'c1', runtime: 'r', model: 'm' },
    },
    {
      name: 'editProfile（数组按顺序原样）',
      run: () => api.editProfile({ profile: 'p1', model: 'm2', credential_env: ['A', 'B'] }, 'c1'),
      path: '/api/v1/profiles/p1/edit',
      body: { confirmation: 'c1', model: 'm2', credential_env: ['A', 'B'] },
    },
    {
      name: 'setHubRole',
      run: () => api.setHubRole({ post: 'build', profile: 'step-high', fallback: 'step-low' }, 'c1'),
      path: '/api/v1/hub/roles/build',
      body: { confirmation: 'c1', profile: 'step-high', fallback: 'step-low' },
    },
    {
      name: 'setHubRole（不带 fallback）',
      run: () => api.setHubRole({ post: 'review', profile: 'step-high' }, 'c1'),
      path: '/api/v1/hub/roles/review',
      body: { confirmation: 'c1', profile: 'step-high' },
    },
    { name: 'unsetHubRole', run: () => api.unsetHubRole('build', 'c1'), path: '/api/v1/hub/roles/build/unset', body: { confirmation: 'c1' } },
    {
      name: 'addRuntime（命令留空不带 command）',
      run: () => api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, 'c1'),
      path: '/api/v1/runtimes/demo-run/add',
      body: { adapter: 'quizs', confirmation: 'c1' },
    },
    {
      name: 'addRuntime（命令按数组原样）',
      run: () => api.addRuntime({ runtime: 'r1', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] }, 'c1'),
      path: '/api/v1/runtimes/r1/add',
      body: { adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'], confirmation: 'c1' },
    },
  ];

  for (const row of WRITE_ROWS) {
    it(`${row.name} → POST ${row.path}，正文 ${JSON.stringify(row.body)}，时限 90 秒，不再回 501`, async () => {
      nextPost = { status: 200, body: okEnvelopeOf(null) };
      const reply = await row.run();
      expect(reply.status).toBe(200);
      expect(posts.length).toBe(1);
      expect(posts[0].path).toBe(row.path);
      expect(posts[0].body).toEqual(row.body);
      expect(posts[0].timeoutSeconds).toBe(90);
      expect(calls.length).toBe(0);
    });
  }

  it('执行回 409 且 exit_code null（确认号无效/过期/参数不符）→ 原样透传；没有回应 → reject', async () => {
    nextPost = { status: 409, body: failEnvelopeOf(['ERROR 确认号无效、已过期或已用过：请重新预览']) };
    const reply = await api.removePreset('old', 'c1');
    expect(reply.status).toBe(409);
    expect(reply.body.ok).toBe(false);
    expect(reply.body.exit_code).toBeNull();
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    await expect(api.usePreset('economy', 'c1')).rejects.toThrow('连不上本机服务');
  });
});

describe('api.ts 的夹具分支（未注入）', () => {
  it('getAttempt 命中夹具；getHistoryEntry/getPlugin 的 command、报错原文与深拷贝', async () => {
    setLiveClientForTests(undefined);
    const a = await api.getAttempt('logs-cat', 'attempt-002');
    expect(a.ok).toBe(true);
    const e = await api.getHistoryEntry(42);
    expect(e.ok).toBe(true);
    expect(e.command).toEqual(['config', 'history', 'show', '42']);
    expect((e.data as { resource: string }).resource).toBe('config');
    const firstDiff = (e.data as { diff: unknown[] }).diff;
    expect(firstDiff.length).toBe(2);
    firstDiff.push({ key: 'x', old: 1, new: 2 });
    const e2 = await api.getHistoryEntry(42);
    expect((e2.data as { diff: unknown[] }).diff.length).toBe(2);
    const miss = await api.getHistoryEntry(7);
    expect(miss.ok).toBe(false);
    expect(miss.exit_code).toBe(2);
    expect(miss.messages).toEqual(['ERROR 夹具里没有这份数据：7']);
    expect(miss.command).toEqual(['config', 'history', 'show', '7']);
    const p = await api.getPlugin('decisions');
    expect(p.ok).toBe(true);
    expect(p.command).toEqual(['plugins', 'show', 'decisions']);
    const pmiss = await api.getPlugin('nope');
    expect(pmiss.messages).toEqual(['ERROR 夹具里没有这份数据：nope']);
    expect(pmiss.command).toEqual(['plugins', 'show', 'nope']);
  });

  it('error 开关照旧：报错原文信封', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/status?mock=error';
    const env = await api.getStatus();
    expect(env.ok).toBe(false);
    expect(env.exit_code).toBe(2);
    expect(env.messages).toEqual(['ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied']);
    expect(env.command).toEqual(['status']);
  });

  it('getMetaNow 一字未改：同步返回夹具，不受注入影响', () => {
    const before = api.getMetaNow();
    setLiveClientForTests(fakeClient);
    const after = api.getMetaNow();
    expect(after).toEqual({ kit_version: '2.12.0', repo_name: 'demo-repo' });
    expect(after).toEqual(before);
  });
});
