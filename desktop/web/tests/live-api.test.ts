// api.ts 的真实分支（合同第 8 步）：注入 fake client，逐个读函数断言请求的路径、查询与服务端时限；
// 归一化（kit_version、resource/diff、allowed_permissions）；写函数与 getOperation 回 501；
// 真实模式下 ?mock= 不生效，夹具分支逐字不变。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

type Call = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };
const calls: Call[] = [];
let nextData: unknown = { v: 0 };

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
};

beforeEach(() => {
  calls.length = 0;
  nextData = { v: 0 };
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

describe('api.ts 的 15 个读函数（注入 fake client）', () => {
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

describe('api.ts 的写函数与 getOperation（真实模式）', () => {
  const WRITES: Array<{ name: string; run: () => Promise<{ status: number; body: Envelope<unknown> }> }> = [
    { name: 'preview', run: () => api.preview('preset.use', { name: 'default' }) },
    { name: 'getOperation', run: () => api.getOperation('op-1') },
    { name: 'usePreset', run: () => api.usePreset('default', 'c1') },
    { name: 'setPluginEnabled', run: () => api.setPluginEnabled('decisions', true, 'c1') },
    { name: 'removePreset', run: () => api.removePreset('default', 'c1') },
    { name: 'removeProfile', run: () => api.removeProfile('p1', 'c1') },
    { name: 'removeRuntime', run: () => api.removeRuntime('r1', 'c1') },
    { name: 'rollback', run: () => api.rollback(41, 'c1') },
    { name: 'addProfile', run: () => api.addProfile({ profile: 'p2', runtime: 'r', model: 'm' }, 'c1') },
    { name: 'editProfile', run: () => api.editProfile({ profile: 'p1', model: 'm2' }, 'c1') },
  ];

  for (const row of WRITES) {
    it(`${row.name} → status 501 + 固定信封，不发读请求`, async () => {
      const reply = await row.run();
      expect(reply.status).toBe(501);
      expect(reply.body).toEqual({
        ok: false,
        exit_code: null,
        data: null,
        output: [],
        messages: ['ERROR: 写操作尚未接通'],
        command: [],
        elapsed_ms: 0,
      });
      expect(calls.length).toBe(0);
    });
  }
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
