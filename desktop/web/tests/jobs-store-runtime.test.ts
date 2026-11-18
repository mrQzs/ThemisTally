// 作业状态模块 jobStore 的 runtime 槽位（T055 合同第 10 步 (a)–(g)）：注入假客户端，断言按 kind 存槽、
// 槽里记 runtime、同类同时只一个、同 runtime 重开不另建、终态后别的 runtime 能建、没有作业时不排计时器、
// 对话框关着时靠行内入口的订阅照查到底、restartJob 的终态门（测真实实现，不把业务逻辑抄进测试）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { ensureJob, resetJobStoreForTests, restartJob, useBusyRuntime, useJob } from '../src/jobs/jobStore';
import type { JobView } from '../src/api';

const JOB_ID = 'store-runtime-job-1';
const creates: Array<{ path: string; body: unknown }> = [];
const queries: string[] = [];
let queryState = 'running';

function jobView(state: string): JobView {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID,
    kind: 'runtime-probe',
    state: state as JobView['state'],
    reason: null,
    created_ms: 1,
    started_ms: state === 'queued' ? null : 2,
    finished_ms: terminal ? 3 : null,
    envelope: null,
  };
}

const fakeClient: LiveClient = {
  get<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
  post<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
  getRaw<T>(path: string): Promise<{ status: number; body: T }> {
    queries.push(path);
    return Promise.resolve({ status: 200, body: jobView(queryState) as unknown as T });
  },
  postRaw<T>(path: string, body: unknown): Promise<{ status: number; body: T }> {
    if (path === '/api/v1/jobs') {
      creates.push({ path, body });
      return Promise.resolve({ status: 201, body: jobView('queued') as unknown as T });
    }
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
};

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

beforeEach(() => {
  creates.length = 0;
  queries.length = 0;
  queryState = 'running';
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('jobStore：按 kind 存槽、槽里记 runtime', () => {
  it('(a) ensureJob 发创建请求，正文恰 {"kind":"runtime-probe","runtime":"pi"}', async () => {
    const view = await ensureJob('runtime-probe', 'pi');
    expect(creates.length).toBe(1);
    expect(creates[0].path).toBe('/api/v1/jobs');
    expect(creates[0].body).toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    expect(Object.keys(creates[0].body as object).length).toBe(2);
    expect(view?.state).toBe('queued');
  });

  it('(b) 同类忙着时，别的 runtime 不建（返回 null、不发请求）', async () => {
    await ensureJob('runtime-probe', 'pi');
    const other = await ensureJob('runtime-probe', 'claude-code');
    expect(other, '槽里是别的 runtime 的未终态作业，store 再挡一道').toBeNull();
    expect(creates.length, '不另发创建请求').toBe(1);
  });

  it('(c) 同一个 runtime 重开 ensureJob 不另建', async () => {
    await ensureJob('runtime-probe', 'pi');
    const again = await ensureJob('runtime-probe', 'pi');
    expect(again?.id).toBe(JOB_ID);
    expect(creates.length).toBe(1);
  });

  it('(d) 作业终态后，别的 runtime 能建（旧的被替换、新的 t0）', async () => {
    await ensureJob('runtime-probe', 'pi');
    queryState = 'succeeded';
    const hook = renderHook(() => useJob('runtime-probe', 'pi'));
    await act(async () => { await sleep(80); });
    expect(hook.result.current.job?.state).toBe('succeeded');
    await ensureJob('runtime-probe', 'claude-code');
    expect(creates.length, '终态后换一个 runtime 能建').toBe(2);
    expect(creates[1].body).toEqual({ kind: 'runtime-probe', runtime: 'claude-code' });
    hook.unmount();
  });

  it('(e) 没有作业时不排计时器：行内入口挂着也不每秒发查询', async () => {
    const entry = renderHook(() => useBusyRuntime('runtime-probe'));
    expect(entry.result.current, '没有作业时不忙于任何 runtime').toBeNull();
    await act(async () => { await sleep(1300); });
    expect(queries.length, '订阅着但没有作业，不每秒空转').toBe(0);
    entry.unmount();
  });

  it('(f) 对话框卸载后，行内入口的订阅仍查到终态', async () => {
    await ensureJob('runtime-probe', 'pi');
    const entry = renderHook(() => useBusyRuntime('runtime-probe'));
    await act(async () => { await sleep(80); });
    expect(entry.result.current, '作业在跑时忙于这个 runtime').toBe('pi');
    const dialog = renderHook(() => useJob('runtime-probe', 'pi'));
    await act(async () => { await sleep(80); });
    dialog.unmount();
    const before = queries.length;
    queryState = 'succeeded';
    await act(async () => { await sleep(1300); });
    expect(queries.length, '对话框关着时行内入口的订阅照查').toBeGreaterThan(before);
    expect(entry.result.current, '终态后不再忙于这个 runtime').toBeNull();
    entry.unmount();
  });

  it('(g) restartJob 未终态不新建、终态后可新建；终态但换了 runtime 不新建', async () => {
    await ensureJob('runtime-probe', 'pi');
    await restartJob('runtime-probe', 'pi');
    expect(creates.length, 'queued 未终态，restartJob 不新建').toBe(1);
    queryState = 'succeeded';
    const hook = renderHook(() => useJob('runtime-probe', 'pi'));
    await act(async () => { await sleep(80); });
    expect(hook.result.current.job?.state).toBe('succeeded');
    await restartJob('runtime-probe', 'claude-code');
    expect(creates.length, '终态但槽里是别的 runtime，不新建').toBe(1);
    await act(async () => { await restartJob('runtime-probe', 'pi'); });
    expect(creates.length, '终态后 restartJob 发新创建').toBe(2);
    expect(creates[1].body).toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    hook.unmount();
  });
});
