// common-readers（合同第 8 步）：searchLogs 真实模式走服务的 search 作业——建作业（正文键恰好、时限 15），
// 201 之后每 1000 毫秒查一次，终态交回作业的信封或固定文案的报错信封；转出后的 getHistoryEntry/getPlugin
// 夹具分支与原来逐字一致（command 数组、报错原文、深拷贝）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getHistoryEntry, getPlugin, searchLogs } from '../src/pages/readonly2/common-readers';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

interface RawReply {
  status: number;
  body: unknown;
}

interface Scenario {
  create?: RawReply | Error;
  polls?: Array<RawReply | Error>;
}

const log = {
  get: 0,
  post: 0,
  postRaw: [] as Array<{ path: string; body: unknown; timeout?: number }>,
  getRaw: [] as Array<{ path: string; query?: unknown; timeout?: number }>,
};

let scenario: Scenario = {};

// 假客户端写全四个方法：get/post 记数（真实模式一条都不该发），postRaw/getRaw 记下路径、查询、正文与时限。
const fakeClient = {
  get(): Promise<Envelope<unknown>> {
    log.get += 1;
    return Promise.reject(new Error('真实模式不应调用 client.get'));
  },
  post(): Promise<{ status: number; body: Envelope<unknown> }> {
    log.post += 1;
    return Promise.reject(new Error('真实模式不应调用 client.post（不取消）'));
  },
  postRaw(path: string, body: unknown, timeoutSeconds?: number): Promise<RawReply> {
    log.postRaw.push({ path, body, timeout: timeoutSeconds });
    return next(scenario.create);
  },
  getRaw(path: string, query?: unknown, timeoutSeconds?: number): Promise<RawReply> {
    log.getRaw.push({ path, query, timeout: timeoutSeconds });
    const polls = scenario.polls ?? [];
    return next(polls.length > 0 ? polls.shift() : undefined);
  },
};

function next(reply: RawReply | Error | undefined): Promise<RawReply> {
  if (reply instanceof Error) return Promise.reject(reply);
  if (!reply) return Promise.reject(new Error('脚本里没有更多的回应'));
  return Promise.resolve(reply);
}

function envelopeOf(messages: string[]): unknown {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

function jobOf(state: string, envelope: unknown, id = 'j1'): unknown {
  return { id, kind: 'search', state, reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope };
}

// 建作业到排下一条计时器只差几个微任务：把链上的 then 全部推进，再去看调用与计时器。
async function drain(): Promise<void> {
  for (let i = 0; i < 12; i += 1) await Promise.resolve();
}

function inject(step: Scenario): void {
  scenario = step;
}

beforeEach(() => {
  log.get = 0;
  log.post = 0;
  log.postRaw.length = 0;
  log.getRaw.length = 0;
  window.location.hash = '';
  setLiveClientForTests(fakeClient as unknown as LiveClient);
  vi.useFakeTimers();
});

afterEach(() => {
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('searchLogs 真实模式：建 search 作业并轮询到终态', () => {
  it('带 task 与 max：正文恰好四键、时限 15；queued→running→succeeded 原样交回信封；终态后计时器归零', async () => {
    const kernel = {
      ok: true,
      exit_code: 0,
      data: { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 },
      output: [],
      messages: [],
      command: ['logs', 'search', 'logs[_ ]cat', '--task', 't1', '--max', '5'],
      elapsed_ms: 33,
    };
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [
        { status: 200, body: jobOf('queued', null) },
        { status: 200, body: jobOf('running', null) },
        { status: 200, body: jobOf('succeeded', kernel) },
      ],
    });
    const pending = searchLogs('logs[_ ]cat', 't1', 5);
    await drain();
    expect(log.postRaw).toEqual([{
      path: '/api/v1/jobs',
      body: { kind: 'search', pattern: 'logs[_ ]cat', max: 5, task: 't1' },
      timeout: 15,
    }]);
    expect(log.getRaw.length, '201 之后、到 1000 毫秒之前不应查询').toBe(0);
    expect(vi.getTimerCount(), '首次查询应排在 201 之后 1000 毫秒').toBe(1);
    await vi.advanceTimersByTimeAsync(999);
    expect(log.getRaw.length, '999 毫秒时还没有到首查时刻').toBe(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(log.getRaw).toEqual([{ path: '/api/v1/jobs/j1', query: undefined, timeout: 15 }]);
    expect(vi.getTimerCount(), 'queued 不是终态，应再排一次 1000 毫秒').toBe(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(log.getRaw.length, 'running 也不是终态，继续查').toBe(2);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(log.getRaw.length).toBe(3);
    expect(await pending).toEqual(kernel);
    expect(vi.getTimerCount(), '终态之后不再排计时器').toBe(0);
    expect(log.post, '全程没有取消请求').toBe(0);
    expect(log.get, '全程没有 client.get').toBe(0);
  });

  it('task 为 null：正文恰好三键、没有 task 键；id 经 encodeURIComponent 编码', async () => {
    const kernel = {
      ok: true,
      exit_code: 0,
      data: { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 },
      output: [],
      messages: [],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 7,
    };
    inject({
      create: { status: 201, body: jobOf('running', null, 'zz 9') },
      polls: [{ status: 200, body: jobOf('succeeded', kernel, 'zz 9') }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    expect(log.postRaw[0].body).toEqual({ kind: 'search', pattern: 'q1', max: 3 });
    expect(Object.keys(log.postRaw[0].body as object)).toEqual(['kind', 'pattern', 'max']);
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual(kernel);
    expect(log.getRaw[0].path, 'id 里的空格应编码成 %20').toBe('/api/v1/jobs/zz%209');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('failed 且 envelope 是合法信封：原样交回内核信封（不拷贝、不改字段）', async () => {
    const kernel = {
      ok: false,
      exit_code: 1,
      data: null,
      output: ['boom'],
      messages: ['ERROR: 检索失败'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 9,
    };
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('failed', kernel) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual(kernel);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('cancelled 且 envelope 为 null：固定信封逐字「ERROR: 检索作业已取消」', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [{ status: 200, body: jobOf('cancelled', null) }],
    });
    const pending = searchLogs('logs[_ ]cat', 't1', 5);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业已取消'],
      command: ['logs', 'search', 'logs[_ ]cat', '--task', 't1', '--max', '5'],
      elapsed_ms: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('timed_out 且 envelope 为 null：固定信封逐字「ERROR: 检索作业超时」', async () => {
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('timed_out', null) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业超时'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('succeeded 但 envelope 不合法：固定信封逐字「ERROR: 检索作业没有交回结果」', async () => {
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('succeeded', { ok: 1 }) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业没有交回结果'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('searchLogs 真实模式：建作业与查询的报错', () => {
  it('建作业回 400（正文是信封）：messages 是服务那句，没有查询、没有计时器', async () => {
    inject({ create: { status: 400, body: envelopeOf(['ERROR: task 不合法']) } });
    const env = await searchLogs('q1', 't9', 5);
    expect(env).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: task 不合法'],
      command: ['logs', 'search', 'q1', '--task', 't9', '--max', '5'],
      elapsed_ms: 0,
    });
    expect(log.getRaw.length, '建作业不是 201 就不该有查询').toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('建作业回 503（正文是信封）：messages 取回应信封的 messages，照样立即停', async () => {
    inject({ create: { status: 503, body: envelopeOf(['ERROR: 服务繁忙（排队过长），请 4 秒后重试']) } });
    const env = await searchLogs('q1', null, 3);
    expect(env.messages).toEqual(['ERROR: 服务繁忙（排队过长），请 4 秒后重试']);
    expect(env.command).toEqual(['logs', 'search', 'q1', '--max', '3']);
    expect(env.elapsed_ms).toBe(0);
    expect(log.getRaw.length).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('建作业回 500（正文不是信封）：messages 是「ERROR: 服务返回 HTTP 500」', async () => {
    inject({ create: { status: 500, body: { note: 'boom' } } });
    const env = await searchLogs('q1', 't1', 5);
    expect(env.messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    expect(log.getRaw.length).toBe(0);
  });

  it('查询回 404：报错信封带「ERROR: 没有这个作业」，之后不再查', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [{ status: 404, body: envelopeOf(['ERROR: 没有这个作业']) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 没有这个作业'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
    await vi.advanceTimersByTimeAsync(5000);
    expect(log.getRaw.length, '查询不是 200 就立即停，不再查').toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('searchLogs 真实模式：断线往外抛', () => {
  it('getRaw reject：searchLogs 跟着 reject，不留计时器、不再排下一次查询', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [new Error('查询断线')],
    });
    const pending = searchLogs('q1', null, 3);
    const thrown = expect(pending).rejects.toThrow('查询断线');
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    await thrown;
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(5000);
    expect(log.getRaw.length).toBe(1);
  });

  it('postRaw reject：searchLogs 跟着 reject（不重试、不吞、不发查询）', async () => {
    inject({ create: new Error('建作业断线') });
    await expect(searchLogs('q1', null, 3)).rejects.toThrow('建作业断线');
    expect(log.getRaw.length).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
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
