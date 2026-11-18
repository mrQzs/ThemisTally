// api.ts 作业接口的真实分支（T054 合同第 11 步 (a)–(e)）：注入假客户端断言创建/查询/取消的路径、正文与时限；
// 201/200 成功信封包八键作业视图，404/409 错误信封原样交回；(e) 用 createLiveClient({ fetch }) 直接调 postRaw，
// 断言作业对象不被归成信封、请求正文恰 {"kind":"runtime-scan"}（测真实实现，不把业务逻辑抄进测试）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { createLiveClient } from '../src/live/transport';
import type { Envelope } from '../src/api';

type PostRawCall = { path: string; body: unknown; timeoutSeconds: number | undefined };
type GetRawCall = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };
const postRaws: PostRawCall[] = [];
const getRaws: GetRawCall[] = [];
let nextPostRaw: { status: number; body: unknown } | null = null;
let nextGetRaw: { status: number; body: unknown } | null = null;

const emptyEnvelope: Envelope<unknown> = { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 };

const fakeClient: LiveClient = {
  get<T>(): Promise<Envelope<T>> {
    return Promise.resolve(emptyEnvelope as unknown as Envelope<T>);
  },
  post<T>(): Promise<{ status: number; body: Envelope<T> }> {
    return Promise.resolve({ status: 200, body: emptyEnvelope as unknown as Envelope<T> });
  },
  getRaw<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }> {
    getRaws.push({ path, query, timeoutSeconds });
    const want = nextGetRaw as { status: number; body: T };
    return Promise.resolve({ status: want.status, body: want.body });
  },
  postRaw<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: T }> {
    postRaws.push({ path, body, timeoutSeconds });
    const want = nextPostRaw as { status: number; body: T };
    return Promise.resolve({ status: want.status, body: want.body });
  },
};

const JOB_KEYS = ['created_ms', 'envelope', 'finished_ms', 'id', 'kind', 'reason', 'started_ms', 'state'];

function queuedJob(): Record<string, unknown> {
  return { id: 'j1', kind: 'runtime-scan', state: 'queued', reason: null, created_ms: 0, started_ms: null, finished_ms: null, envelope: null };
}

beforeEach(() => {
  postRaws.length = 0;
  getRaws.length = 0;
  nextPostRaw = null;
  nextGetRaw = null;
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('api.ts 作业接口（真实分支）', () => {
  it('(a) startJob 发 POST /api/v1/jobs，正文恰 {"kind":"runtime-scan"}，时限 15 秒，201 包八键作业', async () => {
    nextPostRaw = { status: 201, body: queuedJob() };
    const reply = await api.startJob('runtime-scan');
    expect(postRaws.length).toBe(1);
    expect(postRaws[0].path).toBe('/api/v1/jobs');
    expect(postRaws[0].body).toEqual({ kind: 'runtime-scan' });
    expect(Object.keys(postRaws[0].body as object).length).toBe(1);
    expect(postRaws[0].timeoutSeconds).toBe(15);
    expect(reply.status).toBe(201);
    expect(reply.body.ok).toBe(true);
    expect(Object.keys(reply.body.data as object).sort()).toEqual(JOB_KEYS);
    expect(reply.body.data).toEqual(queuedJob());
  });

  it('(b) getJob 发 GET /api/v1/jobs/<id>，时限 15 秒，200 包八键作业', async () => {
    nextGetRaw = { status: 200, body: queuedJob() };
    const reply = await api.getJob('job-42');
    expect(getRaws.length).toBe(1);
    expect(getRaws[0].path).toBe('/api/v1/jobs/job-42');
    expect(getRaws[0].timeoutSeconds).toBe(15);
    expect(reply.status).toBe(200);
    expect(reply.body.data).toEqual(queuedJob());
  });

  it('(c) cancelJob 发 POST /api/v1/jobs/<id>/cancel，正文恰 {}，时限 30 秒', async () => {
    nextPostRaw = { status: 200, body: { ...queuedJob(), state: 'cancelled', finished_ms: 9 } };
    const reply = await api.cancelJob('job-42');
    expect(postRaws.length).toBe(1);
    expect(postRaws[0].path).toBe('/api/v1/jobs/job-42/cancel');
    expect(postRaws[0].body).toEqual({});
    expect(Object.keys(postRaws[0].body as object).length).toBe(0);
    expect(postRaws[0].timeoutSeconds).toBe(30);
    expect(reply.status).toBe(200);
    expect(reply.body.data?.state).toBe('cancelled');
  });

  it('(d) 404/409 错误信封原样交回（状态码与 messages 逐字）', async () => {
    const err404: Envelope<unknown> = { ok: false, exit_code: 1, data: null, output: [], messages: ['没有这个作业'], command: [], elapsed_ms: 0 };
    nextGetRaw = { status: 404, body: err404 };
    const q = await api.getJob('missing');
    expect(q.status).toBe(404);
    expect(q.body).toEqual(err404);
    expect(q.body.messages).toEqual(['没有这个作业']);

    const err409: Envelope<unknown> = { ok: false, exit_code: 1, data: null, output: [], messages: ['作业已经结束'], command: [], elapsed_ms: 0 };
    nextPostRaw = { status: 409, body: err409 };
    const c = await api.cancelJob('job-42');
    expect(c.status).toBe(409);
    expect(c.body).toEqual(err409);
    expect(c.body.messages).toEqual(['作业已经结束']);
  });

  it('(e) postRaw：201 body 原样（不归成信封）、404 错误信封原样、请求正文恰 {"kind":"runtime-scan"}', async () => {
    const job = queuedJob();
    let seenBody: string | undefined;
    const fakeFetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
      seenBody = init?.body as string | undefined;
      return { status: 201, headers: { get: () => null }, text: async () => JSON.stringify(job) };
    }) as unknown as typeof fetch;
    const client = createLiveClient({ fetch: fakeFetch });
    const reply = await client.postRaw('/api/v1/jobs', { kind: 'runtime-scan' }, 15);
    expect(reply.status).toBe(201);
    expect(reply.body).toEqual(job);
    expect((reply.body as { kind: string }).kind).toBe('runtime-scan');
    expect(seenBody).toBe(JSON.stringify({ kind: 'runtime-scan' }));

    const err: Envelope<unknown> = { ok: false, exit_code: 1, data: null, output: [], messages: ['没有这个作业'], command: [], elapsed_ms: 0 };
    const fakeFetch404 = (async () => ({
      status: 404,
      headers: { get: () => null },
      text: async () => JSON.stringify(err),
    })) as unknown as typeof fetch;
    const client404 = createLiveClient({ fetch: fakeFetch404 });
    const reply404 = await client404.postRaw('/api/v1/jobs', { kind: 'runtime-scan' }, 15);
    expect(reply404.status).toBe(404);
    expect(reply404.body).toEqual(err);
  });
});
