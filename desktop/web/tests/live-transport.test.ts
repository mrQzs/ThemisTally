// 传输层（合同第 8 步）：请求形状、时限、失败分类与连接状态。用注入的假 fetch 观察，不发真请求；
// 每条都断言返回的是七字段信封，而不是 reject。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getConnectionState, setConnectionState } from '../src/live/connection';
import { createLiveClient } from '../src/live/transport';

type Seen = { input: string; init: RequestInit };

function envelope(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 4 };
}

function failureEnvelope(message: string) {
  return { ok: false, exit_code: null, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function textResponse(status: number, body: string, headers: Record<string, string> = {}) {
  const lower: Record<string, string> = {};
  for (const key of Object.keys(headers)) lower[key.toLowerCase()] = headers[key];
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
    headers: {
      get: (name: string) =>
        Object.prototype.hasOwnProperty.call(lower, name.toLowerCase()) ? lower[name.toLowerCase()] : null,
    },
  };
}

function jsonResponse(status: number, body: unknown, headers?: Record<string, string>) {
  return textResponse(status, JSON.stringify(body), headers);
}

function abortError(): Error {
  return Object.assign(new Error('The operation was aborted'), { name: 'AbortError' });
}

function recorder(responder: (seen: Seen) => unknown) {
  const seen: Seen[] = [];
  const fn = (input: unknown, init?: RequestInit) => {
    seen.push({ input: String(input), init: init ?? {} });
    return Promise.resolve(responder(seen[seen.length - 1]));
  };
  return { seen, fn };
}

// 收到 signal 后一直挂起，直到我方中止——超时那条用例用它。
function hanging() {
  const seen: Seen[] = [];
  const fn = (input: unknown, init?: RequestInit) => {
    seen.push({ input: String(input), init: init ?? {} });
    return new Promise((_resolve, reject) => {
      const signal = init?.signal as AbortSignal | undefined;
      if (!signal) return;
      if (signal.aborted) reject(abortError());
      else signal.addEventListener('abort', () => reject(abortError()));
    });
  };
  return { seen, fn };
}

// 响应头已到、响应体读失败：text() 直接 reject（服务在写体途中被关/重启、连接被重置）。
function bodyThrows(error: Error, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: () => null },
    text: () => Promise.reject(error),
  };
}

// 响应头已到、响应体挂起，直到 signal 被中止才 reject——我方超时会连响应体流一起中止。
function bodyHangsOnSignal(signal?: AbortSignal) {
  return {
    status: 200,
    ok: true,
    headers: { get: () => null },
    text: () =>
      new Promise((_resolve, reject) => {
        if (!signal) return;
        if (signal.aborted) reject(abortError());
        else signal.addEventListener('abort', () => reject(abortError()));
      }),
  };
}

beforeEach(() => {
  setConnectionState('connected');
});

afterEach(() => {
  vi.useRealTimers();
  setConnectionState('connected');
});

describe('live/transport：成功路径', () => {
  it('200 + 合法信封原样返回；同源相对路径、GET、same-origin、带 signal、不拼凭据头', async () => {
    const rec = recorder(() => jsonResponse(200, envelope({ v: 7 })));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const env = await client.get('/api/v1/meta');
    expect(env).toEqual(envelope({ v: 7 }));
    expect(rec.seen.length).toBe(1);
    expect(rec.seen[0].input).toBe('/api/v1/meta');
    expect(rec.seen[0].init.method).toBe('GET');
    expect(rec.seen[0].init.credentials).toBe('same-origin');
    const signal = rec.seen[0].init.signal as AbortSignal | undefined;
    expect(signal && typeof signal.aborted === 'boolean').toBe(true);
    expect(rec.seen[0].init.headers).toBeUndefined();
    expect(getConnectionState()).toBe('connected');
  });

  it('查询用 URLSearchParams 拼：undefined 的键不拼，空格成 +，无查询不带 ?', async () => {
    const rec = recorder(() => jsonResponse(200, envelope(null)));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    await client.get('/api/v1/attempts/t1/a1/file', { path: 'a b', cursor: undefined });
    expect(rec.seen[0].input).toBe('/api/v1/attempts/t1/a1/file?path=a+b');
    await client.get('/api/v1/roles');
    expect(rec.seen[1].input).toBe('/api/v1/roles');
  });

  it('时限 = 服务端时限 + 5 秒；成功请求结束后不留守计时器', async () => {
    vi.useFakeTimers();
    const rec = recorder(() => jsonResponse(200, envelope({})));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    await client.get('/api/v1/status', undefined, 30);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('live/transport：失败分类', () => {
  it('超时：中止时刻 = 路由时限 + 5 秒，文案带秒数，状态 disconnected，定时器清掉', async () => {
    vi.useFakeTimers();
    const hang = hanging();
    const client = createLiveClient({ fetch: hang.fn as unknown as typeof fetch });
    const pending = client.get('/api/v1/status', undefined, 30);
    let settled = false;
    pending.then(() => (settled = true), () => (settled = true));
    await vi.advanceTimersByTimeAsync(34999);
    expect(settled).toBe(false);
    expect((hang.seen[0].init.signal as AbortSignal).aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const env = await pending;
    expect(env).toEqual(failureEnvelope('ERROR: 请求超时（35 秒），没有收到服务的回应'));
    expect((hang.seen[0].init.signal as AbortSignal).aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(getConnectionState()).toBe('disconnected');
  });

  it('timeoutMs 选项：本次请求用它当中止时限（文案的秒数跟着它走）', async () => {
    vi.useFakeTimers();
    const hang = hanging();
    const client = createLiveClient({ fetch: hang.fn as unknown as typeof fetch, timeoutMs: 2000 });
    const pending = client.get('/api/v1/status', undefined, 30);
    const env = await vi.advanceTimersByTimeAsync(2000).then(() => pending);
    expect(env.messages).toEqual(['ERROR: 请求超时（2 秒），没有收到服务的回应']);
  });

  it('断线：fetch 抛错且非我方中止 → 固定文案，状态 disconnected', async () => {
    const client = createLiveClient({
      fetch: (() => Promise.reject(new TypeError('Failed to fetch'))) as unknown as typeof fetch,
    });
    const env = await client.get('/api/v1/roles');
    expect(env).toEqual(failureEnvelope('ERROR: 连不上本机服务（请求没有到达服务）'));
    expect(getConnectionState()).toBe('disconnected');
  });

  it('401：并发两个只调一次 reauth，都回同一句；下一波 401 再起一次新的', async () => {
    let reauthCalls = 0;
    const rec = recorder(() => jsonResponse(401, { some: 'body' }));
    const client = createLiveClient({
      fetch: rec.fn as unknown as typeof fetch,
      host: {
        reauth: () => {
          reauthCalls += 1;
          return Promise.resolve({ ok: true });
        },
      },
    });
    const [a, b] = await Promise.all([client.get('/x'), client.get('/y')]);
    expect(reauthCalls).toBe(1);
    expect(a).toEqual(failureEnvelope('ERROR: 会话已失效'));
    expect(b).toEqual(failureEnvelope('ERROR: 会话已失效'));
    await client.get('/z');
    expect(reauthCalls).toBe(2);
    expect(getConnectionState()).toBe('connected');
  });

  it('401：没有宿主 / reauth 抛错 / reauth 回 ok:false，都回同一句且不冒泡', async () => {
    const respond401 = recorder(() => jsonResponse(401, {}));
    const noHost = createLiveClient({ fetch: respond401.fn as unknown as typeof fetch });
    expect((await noHost.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
    const throws = createLiveClient({
      fetch: respond401.fn as unknown as typeof fetch,
      host: {
        reauth: () => {
          throw new Error('boom');
        },
      },
    });
    expect((await throws.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
    const notOk = createLiveClient({
      fetch: respond401.fn as unknown as typeof fetch,
      host: { reauth: () => Promise.resolve({ ok: false }) },
    });
    expect((await notOk.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
  });

  it('503：读 Retry-After；缺失或不是非负整数时 N=2；不自动重试', async () => {
    const withHeader = recorder(() => jsonResponse(503, {}, { 'Retry-After': '7' }));
    const a = createLiveClient({ fetch: withHeader.fn as unknown as typeof fetch });
    expect((await a.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 7 秒后重试']);
    expect(withHeader.seen.length).toBe(1);
    const missing = recorder(() => jsonResponse(503, {}));
    const b = createLiveClient({ fetch: missing.fn as unknown as typeof fetch });
    expect((await b.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 2 秒后重试']);
    const invalid = recorder(() => jsonResponse(503, {}, { 'Retry-After': 'soon' }));
    const c = createLiveClient({ fetch: invalid.fn as unknown as typeof fetch });
    expect((await c.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 2 秒后重试']);
  });

  it('其他 4xx/5xx：正文是合法七字段信封就原样返回（服务自己的提示）', async () => {
    const serverEnvelope = {
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 上游超时'],
      command: ['status'],
      elapsed_ms: 1200,
    };
    const rec = recorder(() => jsonResponse(504, serverEnvelope));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const env = await client.get('/api/v1/status', undefined, 30);
    expect(env).toEqual(serverEnvelope);
    expect(getConnectionState()).toBe('connected');
  });

  it('其他 4xx/5xx：正文不是合法信封（含不是 JSON）→ ERROR: 服务返回 HTTP <状态码>', async () => {
    const rec500 = recorder(() => textResponse(500, 'internal error'));
    const c500 = createLiveClient({ fetch: rec500.fn as unknown as typeof fetch });
    expect((await c500.get('/x')).messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    const recJson500 = recorder(() => jsonResponse(500, { ok: true }));
    const cJson500 = createLiveClient({ fetch: recJson500.fn as unknown as typeof fetch });
    expect((await cJson500.get('/x')).messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    const rec404 = recorder(() => textResponse(404, 'nope'));
    const c404 = createLiveClient({ fetch: rec404.fn as unknown as typeof fetch });
    expect((await c404.get('/x')).messages).toEqual(['ERROR: 服务返回 HTTP 404']);
  });

  it('200 且 ok:false：原样返回（内核报错原文）', async () => {
    const kernelEnvelope = {
      ok: false,
      exit_code: 2,
      data: null,
      output: [],
      messages: ['ERROR 用法错误'],
      command: ['status'],
      elapsed_ms: 9,
    };
    const rec = recorder(() => jsonResponse(200, kernelEnvelope));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    expect(await client.get('/x')).toEqual(kernelEnvelope);
  });

  it('200 + 坏 JSON / JSON 但不是七字段信封 → ERROR: 服务的响应不是合法的 JSON（HTTP 200）', async () => {
    const bad = recorder(() => textResponse(200, 'not-json{'));
    const a = createLiveClient({ fetch: bad.fn as unknown as typeof fetch });
    expect((await a.get('/x')).messages).toEqual(['ERROR: 服务的响应不是合法的 JSON（HTTP 200）']);
    const notEnvelope = recorder(() => jsonResponse(200, { ok: true }));
    const b = createLiveClient({ fetch: notEnvelope.fn as unknown as typeof fetch });
    expect((await b.get('/x')).messages).toEqual(['ERROR: 服务的响应不是合法的 JSON（HTTP 200）']);
  });

  it('信封校验严格：七字段缺一个或类型不对，都按非信封处理', async () => {
    const full = { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 1 };
    const bads: Array<Record<string, unknown>> = [];
    const missingCommand: Record<string, unknown> = { ...full };
    delete missingCommand.command;
    bads.push(missingCommand);
    bads.push({ ...full, ok: 'yes' });
    bads.push({ ...full, exit_code: '2' });
    bads.push({ ...full, messages: 'x' });
    bads.push({ ...full, output: [1] });
    bads.push({ ...full, elapsed_ms: '3' });
    let i = 0;
    const fn = () => {
      const body = JSON.stringify(bads[i]);
      i += 1;
      return Promise.resolve(textResponse(500, body));
    };
    const client = createLiveClient({ fetch: fn as unknown as typeof fetch });
    for (let k = 0; k < bads.length; k += 1) {
      const env = await client.get('/x');
      expect(env.messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    }
  });

  it('读体失败：响应头已到、响应体 reject 且非我方中止 → 连不上本机服务，状态 disconnected，绝不 reject', async () => {
    const rec = recorder(() => bodyThrows(new TypeError('terminated')));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const env = await client.get('/api/v1/status');
    expect(env).toEqual(failureEnvelope('ERROR: 连不上本机服务（请求没有到达服务）'));
    expect(getConnectionState()).toBe('disconnected');
  });

  it('读体失败：状态码 ≥ 400 时按第 5 条回 ERROR: 服务返回 HTTP <状态码>（状态码优先），仍是信封', async () => {
    const rec = recorder(() => bodyThrows(new TypeError('terminated'), 502));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const env = await client.get('/api/v1/status');
    expect(env).toEqual(failureEnvelope('ERROR: 服务返回 HTTP 502'));
    expect(getConnectionState()).toBe('disconnected');
  });

  it('读体期间我方超时到点：中止响应体流 → 超时文案（带中止秒数），状态 disconnected，绝不 reject', async () => {
    vi.useFakeTimers();
    const rec = recorder((seen) => bodyHangsOnSignal(seen.init.signal as AbortSignal | undefined));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const pending = client.get('/api/v1/status', undefined, 30);
    let rejected = false;
    pending.then(
      () => undefined,
      () => {
        rejected = true;
      },
    );
    await vi.advanceTimersByTimeAsync(34999);
    expect((rec.seen[0].init.signal as AbortSignal).aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const env = await pending;
    expect(rejected).toBe(false);
    expect(env).toEqual(failureEnvelope('ERROR: 请求超时（35 秒），没有收到服务的回应'));
    expect((rec.seen[0].init.signal as AbortSignal).aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(getConnectionState()).toBe('disconnected');
  });

  it('连接状态：断线置 disconnected，收到任何 HTTP 响应（哪怕 500）恢复 connected', async () => {
    const dead = createLiveClient({
      fetch: (() => Promise.reject(new TypeError('net down'))) as unknown as typeof fetch,
    });
    await dead.get('/x');
    expect(getConnectionState()).toBe('disconnected');
    const rec500 = recorder(() => jsonResponse(500, 'oops'));
    const c500 = createLiveClient({ fetch: rec500.fn as unknown as typeof fetch });
    await c500.get('/x');
    expect(getConnectionState()).toBe('connected');
    setConnectionState('disconnected');
    const rec200 = recorder(() => jsonResponse(200, envelope({})));
    const c200 = createLiveClient({ fetch: rec200.fn as unknown as typeof fetch });
    await c200.get('/x');
    expect(getConnectionState()).toBe('connected');
  });

  it('宿主接口调用时取：先建客户端、后设 window.themisHost，reauth 仍被调 1 次', async () => {
    const rec = recorder(() => jsonResponse(401, { some: 'body' }));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reauth = vi.fn(() => Promise.resolve({ ok: true }));
    (window as unknown as { themisHost?: unknown }).themisHost = { reauth };
    try {
      const env = await client.get('/x');
      expect(reauth).toHaveBeenCalledTimes(1);
      expect(env).toEqual(failureEnvelope('ERROR: 会话已失效'));
      expect(getConnectionState()).toBe('connected');
    } finally {
      delete (window as unknown as { themisHost?: unknown }).themisHost;
    }
  });
});
