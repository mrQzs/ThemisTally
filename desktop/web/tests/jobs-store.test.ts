// 作业状态模块 jobStore（T054 合同第 11 步 (a)–(e)）：注入假客户端，断言在途创建共用、已有作业不重开、
// restartJob 的终态门、每秒轮询与卸载即停、查询 404 按失败处理、查询 reject 保留状态继续查（测真实实现）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { ensureJob, restartJob, resetJobStoreForTests, useJob } from '../src/jobs/jobStore';
import type { Envelope, JobView } from '../src/api';

const JOB_ID = 'store-job-1';
const creates: Array<{ path: string; body: unknown }> = [];
const cancels: Array<{ path: string; body: unknown }> = [];
const queries: string[] = [];
let queryStatus = 200;
let queryState = 'running';
let failNextQuery = false;

function jobView(state: string): JobView {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID,
    kind: 'runtime-scan',
    state: state as JobView['state'],
    reason: null,
    created_ms: 1,
    started_ms: state === 'queued' ? null : 2,
    finished_ms: terminal ? 3 : null,
    envelope: null,
  };
}

const empty: Envelope<unknown> = { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 };

const fakeClient: LiveClient = {
  get<T>(): Promise<Envelope<T>> {
    return Promise.resolve(empty as unknown as Envelope<T>);
  },
  post<T>(): Promise<{ status: number; body: Envelope<T> }> {
    return Promise.resolve({ status: 200, body: empty as unknown as Envelope<T> });
  },
  getRaw<T>(path: string): Promise<{ status: number; body: T }> {
    queries.push(path);
    if (failNextQuery) {
      failNextQuery = false;
      return Promise.reject(new Error('disconnect'));
    }
    if (queryStatus === 404) {
      const err: Envelope<unknown> = { ok: false, exit_code: 1, data: null, output: [], messages: ['没有这个作业'], command: [], elapsed_ms: 0 };
      return Promise.resolve({ status: 404, body: err as unknown as T });
    }
    return Promise.resolve({ status: 200, body: jobView(queryState) as unknown as T });
  },
  postRaw<T>(path: string, body: unknown): Promise<{ status: number; body: T }> {
    if (path === '/api/v1/jobs') {
      creates.push({ path, body });
      return Promise.resolve({ status: 201, body: jobView('queued') as unknown as T });
    }
    if (path.endsWith('/cancel')) {
      cancels.push({ path, body });
      return Promise.resolve({ status: 200, body: jobView('cancelled') as unknown as T });
    }
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
};

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

beforeEach(() => {
  creates.length = 0;
  cancels.length = 0;
  queries.length = 0;
  queryStatus = 200;
  queryState = 'running';
  failNextQuery = false;
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('jobStore：创建共用、重开、轮询与失败处理', () => {
  it('(a) 连点两次 ensureJob 只发一次创建请求', async () => {
    const p1 = ensureJob('runtime-scan');
    const p2 = ensureJob('runtime-scan');
    await Promise.all([p1, p2]);
    expect(creates.length).toBe(1);
    expect(creates[0].body).toEqual({ kind: 'runtime-scan' });
  });

  it('(b) 已有作业时 ensureJob 不再发创建请求', async () => {
    await ensureJob('runtime-scan');
    expect(creates.length).toBe(1);
    await ensureJob('runtime-scan');
    expect(creates.length).toBe(1);
  });

  it('(c) restartJob 未终态不新建，终态后发新创建', async () => {
    await ensureJob('runtime-scan');
    await restartJob('runtime-scan');
    expect(creates.length, 'queued 未终态，restartJob 不新建').toBe(1);
    queryState = 'succeeded';
    const { result } = renderHook(() => useJob('runtime-scan'));
    await act(async () => {
      await sleep(80);
    });
    expect(result.current.job?.state).toBe('succeeded');
    await act(async () => {
      await restartJob('runtime-scan');
    });
    expect(creates.length, '终态后 restartJob 发新创建').toBe(2);
  });

  it('(d) 轮询：挂载后每秒查，卸载后不再查', async () => {
    await ensureJob('runtime-scan');
    expect(queries.length, '没有组件挂着不轮询').toBe(0);
    const { unmount } = renderHook(() => useJob('runtime-scan'));
    await act(async () => {
      await sleep(80);
    });
    const afterFirst = queries.length;
    expect(afterFirst, '挂载后先查一次').toBeGreaterThanOrEqual(1);
    await act(async () => {
      await sleep(1200);
    });
    expect(queries.length, '每秒接着查').toBeGreaterThan(afterFirst);
    unmount();
    const afterUnmount = queries.length;
    await act(async () => {
      await sleep(1200);
    });
    expect(queries.length, '卸载后不再查').toBe(afterUnmount);
  });

  it('(e) 查询 404 按失败处理（状态 failed、错误原文在 job.envelope），并允许重新扫描', async () => {
    await ensureJob('runtime-scan');
    queryStatus = 404;
    const { result } = renderHook(() => useJob('runtime-scan'));
    await act(async () => {
      await sleep(80);
    });
    expect(result.current.job?.state).toBe('failed');
    expect(result.current.job?.envelope?.messages).toEqual(['没有这个作业']);
    queryStatus = 200;
    queryState = 'running';
    await act(async () => {
      await restartJob('runtime-scan');
    });
    expect(creates.length, '404 后允许重新扫描（发新创建）').toBe(2);
  });

  it('(f) 查询 reject：保留原状态，下一秒再查', async () => {
    await ensureJob('runtime-scan');
    const { result } = renderHook(() => useJob('runtime-scan'));
    await act(async () => {
      await sleep(80);
    });
    expect(result.current.job?.state).toBe('running');
    failNextQuery = true;
    const before = queries.length;
    await act(async () => {
      await sleep(1200);
    });
    expect(result.current.job?.state, '断线时保留原状态').toBe('running');
    expect(queries.length, '下一秒接着查').toBeGreaterThan(before);
  });
});
