// 传输层：本片唯一发浏览器网络请求的地方（同源相对路径，GET，cookie 由浏览器自带，不拼任何凭据头）。
// 一律 resolve 成七字段信封、绝不 reject，调用方不用补 catch；失败分类的状态码优先于正文
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
function isEnvelope(value: unknown): value is Envelope<unknown> {
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

export function createLiveClient(options: LiveClientOptions = {}): LiveClient {
  const doFetch: typeof fetch =
    options.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));
  const host = options.host !== undefined ? options.host : (typeof window === 'undefined' ? null : window.themisHost);
  let reauthInFlight: Promise<void> | null = null;

  // 并发 401 只调一次 reauth：在途的那一个大家共用，兑现后清空，下一波 401 再起一次新的。
  // reauth 的返回值与异常都不冒泡（文案只有一个，不区分原因）。
  function runReauth(): Promise<void> {
    if (reauthInFlight !== null) return reauthInFlight;
    const reauth = host?.reauth;
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

  return {
    async get<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>> {
      const timeoutMs = options.timeoutMs ?? ((timeoutSeconds ?? DEFAULT_TIMEOUT_SECONDS) + TIMEOUT_GRACE_SECONDS) * 1000;
      const controller = new AbortController();
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
      let response: Response;
      try {
        response = await doFetch(buildUrl(path, query), {
          method: 'GET',
          credentials: 'same-origin',
          signal: controller.signal,
        });
      } catch (error) {
        clearTimeout(timer);
        setConnectionState('disconnected');
        if (timedOut || (error as Error)?.name === 'AbortError') {
          return failure<T>(MSG_TIMEOUT(Math.round(timeoutMs / 1000)));
        }
        return failure<T>(MSG_DISCONNECT);
      }
      try {
        setConnectionState('connected');
        if (response.status === 401) {
          await runReauth();
          return failure<T>(MSG_401);
        }
        if (response.status === 503) {
          return failure<T>(MSG_503(retryAfterSeconds(response)));
        }
        const body = parseJson(await response.text());
        if (response.status >= 400) {
          return isEnvelope(body) ? (body as Envelope<T>) : failure<T>(MSG_HTTP(response.status));
        }
        return isEnvelope(body) ? (body as Envelope<T>) : failure<T>(MSG_BAD_JSON(response.status));
      } finally {
        clearTimeout(timer);
      }
    },
  };
}
