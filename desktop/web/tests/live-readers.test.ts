// common-readers（合同第 8 步）：searchLogs 真实模式回「检索尚未接通」；转出后的 getHistoryEntry/getPlugin
// 夹具分支与原来逐字一致（command 数组、报错原文、深拷贝）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { getHistoryEntry, getPlugin, searchLogs } from '../src/pages/readonly2/common-readers';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

const fakeClient: LiveClient = {
  get<T>(): Promise<Envelope<T>> {
    return Promise.resolve({
      ok: true,
      exit_code: 0,
      data: null,
      output: [],
      messages: [],
      command: [],
      elapsed_ms: 0,
    }) as Promise<Envelope<T>>;
  },
};

beforeEach(() => {
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('searchLogs 真实模式回「检索尚未接通」', () => {
  it('带 task 与 max：信封逐字段、command 数组照旧', async () => {
    const env = await searchLogs('logs[_ ]cat', 't1', 5);
    expect(env).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索尚未接通'],
      command: ['logs', 'search', 'logs[_ ]cat', '--task', 't1', '--max', '5'],
      elapsed_ms: 0,
    });
  });

  it('task 为 null：command 不带 --task', async () => {
    const env = await searchLogs('q1', null, 3);
    expect(env.command).toEqual(['logs', 'search', 'q1', '--max', '3']);
    expect(env.messages).toEqual(['ERROR: 检索尚未接通']);
  });
});

describe('转出后的 getHistoryEntry/getPlugin：夹具分支与原来逐字一致', () => {
  it('getHistoryEntry：命中夹具、command、报缺原文与深拷贝', async () => {
    setLiveClientForTests(undefined);
    const env = await getHistoryEntry(42);
    expect(env.ok).toBe(true);
    expect(env.command).toEqual(['config', 'history', 'show', '42']);
    expect((env.data as { resource: string }).resource).toBe('config');
    const diff = (env.data as { diff: unknown[] }).diff;
    expect(diff.length).toBe(2);
    diff.push({ key: 'x', old: 1, new: 2 });
    const again = await getHistoryEntry(42);
    expect((again.data as { diff: unknown[] }).diff.length).toBe(2);
    const miss = await getHistoryEntry(7);
    expect(miss.ok).toBe(false);
    expect(miss.exit_code).toBe(2);
    expect(miss.messages).toEqual(['ERROR 夹具里没有这份数据：7']);
    expect(miss.command).toEqual(['config', 'history', 'show', '7']);
  });

  it('getPlugin：命中夹具、command 与报缺原文', async () => {
    setLiveClientForTests(undefined);
    const env = await getPlugin('decisions');
    expect(env.ok).toBe(true);
    expect(env.command).toEqual(['plugins', 'show', 'decisions']);
    const miss = await getPlugin('nope');
    expect(miss.ok).toBe(false);
    expect(miss.messages).toEqual(['ERROR 夹具里没有这份数据：nope']);
    expect(miss.command).toEqual(['plugins', 'show', 'nope']);
  });

  it('searchLogs 夹具模式照旧：SEARCH_PATTERN 命中夹具，empty 返回空 matches', async () => {
    setLiveClientForTests(undefined);
    const env = await searchLogs('logs[_ ]cat', null, 100);
    expect(env.ok).toBe(true);
    const data = env.data as { matches: Array<{ task: string }> };
    expect(data.matches.length).toBeGreaterThanOrEqual(2);
    expect(data.matches[0].task).toBe('logs-cat');
    window.location.hash = '#/logs?mock=empty';
    const empty = await searchLogs('logs[_ ]cat', null, 100);
    expect(empty.ok).toBe(true);
    expect((empty.data as { matches: unknown[] }).matches).toEqual([]);
  });
});
