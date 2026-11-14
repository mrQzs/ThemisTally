// 传输层：本片唯一发浏览器网络请求的地方（同源相对路径，cookie 由浏览器自带，不拼任何凭据头）。
// get 一律 resolve 成七字段信封、绝不 reject，调用方不用补 catch；post 与 getRaw 回 { status, body }
// （状态码原样，写流程靠它分类），拿不到回应时 reject。失败分类的状态码优先于正文
// （≥400 一律不进「不是合法的 JSON」那条）。连接状态报给 connection 的状态源。
import type { Envelope } from '../api';
import type { LiveClient } from './mode';
import { setConnectionState } from './connection';

declare global {
  interface Window {
    themisHost?: { reauth?: () => unknown } | null;
  }
}

// 客户端中止 = 服务端时限 + 5 秒：让服务的 504 信封先到，别被我方中止抢掉。
const TIMEOUT_GRACE_SECONDS = 5;
// 服务端时限没给时的缺省值（readroutes.ts 的 DEFAULT_TIMEOUT）。
const DEFAULT_TIMEOUT_SECONDS = 30;
// 503 的 Retry-After 缺失或不是非负整数时的兜底秒数（与服务的排队下限一致）。
const DEFAULT_RETRY_AFTER_SECONDS = 2;

const MSG_TIMEOUT = (seconds: number) => `ERROR: 请求超时（${seconds} 秒），没有收到服务的回应`;
const MSG_DISCONNECT = 'ERROR: 连不上本机服务（请求没有到达服务）';
const MSG_401 = 'ERROR: 会话已失效';
const MSG_503 = (seconds: number) => `ERROR: 服务繁忙（排队过长），请 ${seconds} 秒后重试`;
const MSG_HTTP = (status: number) => `ERROR: 服务返回 HTTP ${status}`;
const MSG_BAD_JSON = (status: number) => `ERROR: 服务的响应不是合法的 JSON（HTTP ${status}）`;

export interface LiveClientOptions {
  fetch?: typeof fetch;
  host?: { reauth?: () => unknown } | null;
  timeoutMs?: number;
}

function failure<T>(message: string): Envelope<T> {
  return { ok: false, exit_code: null, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function isStringArray(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

// 七字段齐全才算合法信封：ok 布尔、exit_code 数字或 null、data 任意或 null、三个字符串数组、elapsed_ms 数字。
export function isEnvelope(value: unknown): value is Envelope<unknown> {
  if (typeof value !== 'object' || value === null) return false;
  const body = value as Record<string, unknown>;
  return (
    typeof body.ok === 'boolean' &&
    'exit_code' in body &&
    (body.exit_code === null || typeof body.exit_code === 'number') &&
    'data' in body &&
    isStringArray(body.output) &&
    isStringArray(body.messages) &&
    isStringArray(body.command) &&
    typeof body.elapsed_ms === 'number'
  );
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function retryAfterSeconds(response: { headers: { get(name: string): string | null } }): number {
  const raw = response.headers.get('Retry-After');
  if (raw != null && /^\d+$/.test(raw.trim())) return Number(raw.trim());
  return DEFAULT_RETRY_AFTER_SECONDS;
}

function buildUrl(path: string, query?: Record<string, string | undefined>): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    params.set(key, value);
  }
  const search = params.toString();
  return search === '' ? path : `${path}?${search}`;
}

// 宿主接口在要用它的那一步才读（T027 终审不挡意见 1）：页面挂载早期就建客户端时，宿主接口可能还没出现，
// 创建时取会让重新认证永远失效。显式给的 options.host 仍然优先。
function reauthOf(options: LiveClientOptions): (() => unknown) | undefined {
  const host = options.host !== undefined ? options.host : typeof window === 'undefined' ? null : window.themisHost;
  return host?.reauth;
}

// 公开方法给的请求形状：方法与正文（GET 不带正文，POST 带 JSON 正文与两个头）；
// credentials 与 signal 由内部请求函数补上，只此一处。
type RequestShape = { method: string; headers?: Record<string, string>; body?: string };

// 一次请求的结果：要么拿到 HTTP 响应并读完正文（状态码、解析出的 JSON、Retry-After 秒数），
// 要么没有回应（Error 的文案就是定稿文案；resolve 失败信封还是 reject 由公开方法决定）。
type RequestResult = { status: number; json: unknown; retryAfter: number } | { missed: Error };

// 拿到的响应 → 七字段信封：合法信封原样用，否则按状态码合成失败信封（503 合成繁忙文案）。
function envelopeOf<T>(status: number, json: unknown, retryAfter: number): Envelope<T> {
  if (isEnvelope(json)) return json as Envelope<T>;
  if (status === 503) return failure<T>(MSG_503(retryAfter));
  if (status >= 400) return failure<T>(MSG_HTTP(status));
  return failure<T>(MSG_BAD_JSON(status));
}

export function createLiveClient(options: LiveClientOptions = {}): LiveClient {
  const doFetch: typeof fetch =
    options.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));
  let reauthInFlight: Promise<void> | null = null;

  // 并发 401 只调一次 reauth：在途的那一个大家共用，兑现后清空，下一波 401 再起一次新的。
  // reauth 的返回值与异常都不冒泡（文案只有一个，不区分原因）。
  function runReauth(): Promise<void> {
    if (reauthInFlight !== null) return reauthInFlight;
    const reauth = reauthOf(options);
    const attempt = reauth === undefined ? Promise.resolve() : (async () => reauth())();
    reauthInFlight = (async () => {
      try {
        await attempt;
      } catch {
        // reauth 抛错与回 ok:false 同一句文案，不冒泡给调用方。
      }
    })().finally(() => {
      reauthInFlight = null;
    });
    return reauthInFlight;
  }

  // 内部请求函数：取时限 → AbortController → 发请求 → 读正文 → 写连接状态。
  // get/post/getRaw 三个公开方法都走它：中止判定只有下面两处，超时路径只有一条。
  async function request(
    path: string,
    query: Record<string, string | undefined> | undefined,
    shape: RequestShape,
    timeoutSeconds: number | undefined,
  ): Promise<RequestResult> {
    const timeoutMs = options.timeoutMs ?? ((timeoutSeconds ?? DEFAULT_TIMEOUT_SECONDS) + TIMEOUT_GRACE_SECONDS) * 1000;
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    let response: Response;
    try {
      response = await doFetch(buildUrl(path, query), { ...shape, credentials: 'same-origin', signal: controller.signal });
    } catch (error) {
      clearTimeout(timer);
      setConnectionState('disconnected');
      if (timedOut || (error as Error)?.name === 'AbortError') {
        return { missed: new Error(MSG_TIMEOUT(Math.round(timeoutMs / 1000))) };
      }
      return { missed: new Error(MSG_DISCONNECT) };
    }
    try {
      setConnectionState('connected');
      let json: unknown;
      try {
        json = parseJson(await response.text());
      } catch (error) {
        // 响应头已到、响应体读失败（服务在写体途中被关/重启，或我方超时把响应体流一起中止）：
        // 我方中止/AbortError 走超时文案，其余按第 2 条（≥400 也可按第 5 条），状态置 disconnected。
        setConnectionState('disconnected');
        if (timedOut || (error as Error)?.name === 'AbortError') {
          return { missed: new Error(MSG_TIMEOUT(Math.round(timeoutMs / 1000))) };
        }
        return { missed: new Error(response.status >= 400 ? MSG_HTTP(response.status) : MSG_DISCONNECT) };
      }
      return { status: response.status, json, retryAfter: retryAfterSeconds(response) };
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    async get<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>> {
      const result = await request(path, query, { method: 'GET' }, timeoutSeconds);
      if ('missed' in result) return failure<T>(result.missed.message);
      if (result.status === 401) {
        await runReauth();
        return failure<T>(MSG_401);
      }
      if (result.status === 503) return failure<T>(MSG_503(result.retryAfter));
      if (result.status >= 400) return isEnvelope(result.json) ? (result.json as Envelope<T>) : failure<T>(MSG_HTTP(result.status));
      return isEnvelope(result.json) ? (result.json as Envelope<T>) : failure<T>(MSG_BAD_JSON(result.status));
    },

    // 写路由：状态码原样返回（写流程靠它分类），拿不到回应时 reject（流程转去轮询操作终态）。
    async post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }> {
      const result = await request(
        path,
        undefined,
        { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Themis-UI': '1' }, body: JSON.stringify(body) },
        timeoutSeconds,
      );
      if ('missed' in result) throw result.missed;
      if (result.status === 401) {
        await runReauth();
        return { status: 401, body: failure<T>(MSG_401) };
      }
      return { status: result.status, body: envelopeOf<T>(result.status, result.json, result.retryAfter) };
    },

    // 读原始 JSON（操作终态）：不归成信封，解析出来的正文原样交回去；正文不是合法 JSON 时按状态码合成失败信封。
    async getRaw<T>(
      path: string,
      query?: Record<string, string | undefined>,
      timeoutSeconds?: number,
    ): Promise<{ status: number; body: T }> {
      const result = await request(path, query, { method: 'GET' }, timeoutSeconds);
      if ('missed' in result) throw result.missed;
      if (result.status === 401) {
        await runReauth();
        return { status: 401, body: failure<unknown>(MSG_401) as unknown as T };
      }
      const body = result.json === undefined ? envelopeOf<unknown>(result.status, result.json, result.retryAfter) : result.json;
      return { status: result.status, body: body as T };
    },
  };
}
