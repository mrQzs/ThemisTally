// 事件流客户端：真实模式下按订阅引用计数建流（第一个订阅者建、最后一个离开关），断线自己排退避
// 重连，重连后靠 snapshot 整份重建。浏览器读不到非 200 响应的状态码与重试头（503 之后 readyState
// 是 CLOSED、不自带重连），所以退避下限写常量、与服务端的 retry 对齐，503 也按普通断线走同一套。
// 连接状态与重连次数写给 connection 的状态源；写入方有两个（传输层与本文件），以最后一次为准，不加仲裁。
import { getConnectionState, setConnectionState, setReconnectCount } from './connection';
import { liveModeIsReal } from './mode';
import type { Envelope, StatusData } from '../api';

export interface LiveStreamEvent {
  readonly type: 'snapshot' | 'update';
  readonly lastEventId: string;
  readonly data: string;
}

export interface LiveStreamHandle {
  addEventListener(type: 'snapshot' | 'update', listener: (event: LiveStreamEvent) => void): void;
  removeEventListener(type: 'snapshot' | 'update', listener: (event: LiveStreamEvent) => void): void;
  close(): void;
}

export interface LiveEventsOptions {
  createStream: () => LiveStreamHandle;
  setTimer?: (fn: () => void, delayMs: number) => unknown;
  clearTimer?: (handle: unknown) => void;
  random?: () => number;
}

export interface LiveEvents {
  subscribe(listener: () => void): () => void;
  getStatus(): StatusData | null;
  getReconnectCount(): number;
}

// 退避下限：服务端的 retry 是同值，503 的 Retry-After（2 秒）也在它之下，不必解析响应头。
const RECONNECT_FLOOR_MS = 3000;
// 指数增长的上限。
const RECONNECT_CEILING_MS = 30000;
// 抖动幅度：只往后加，避免多个客户端同时重连。
const RECONNECT_JITTER_MS = 1000;

// 原生流还有一个 error 事件（断线通知），它不在对外的 LiveStreamHandle 里，内部按宽类型登记。
type WideStream = {
  addEventListener(type: string, listener: (event: LiveStreamEvent) => void): void;
  close(): void;
};

// 一条推送读出来的结果：ok 为真才带 data；undefined 表示 data 不是合法 JSON，整条丢弃。
interface Push {
  ok: boolean;
  data: unknown;
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

function parseEnvelope(data: string): Push | undefined {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data) as unknown;
  } catch {
    return undefined;
  }
  // 不是七字段信封时按 ok:false 处理：服务这一次没读到 status，已显示的数据不动。
  const body = isEnvelope(parsed) ? parsed : null;
  return body != null && body.ok ? { ok: true, data: body.data } : { ok: false, data: null };
}

function parseSeq(raw: string): number | null {
  return /^\d+$/.test(raw) ? Number(raw) : null;
}

export function createLiveEvents(options: LiveEventsOptions): LiveEvents {
  const setTimer = options.setTimer ?? ((fn: () => void, delayMs: number) => setTimeout(fn, delayMs));
  const clearTimer =
    options.clearTimer ?? ((handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>));
  const random = options.random ?? (() => Math.random());

  const listeners = new Set<() => void>();
  let status: StatusData | null = null;
  // 已见的序号基线；null 表示还没收到过 snapshot，此时的 update 一律丢弃。
  let baseline: number | null = null;
  let failures = 0;
  let stream: LiveStreamHandle | null = null;
  let pending: unknown = null;

  function notify(): void {
    for (const listener of [...listeners]) listener();
  }

  function closeStream(): void {
    if (stream === null) return;
    stream.close();
    stream = null;
  }

  function clearPending(): void {
    if (pending === null) return;
    clearTimer(pending);
    pending = null;
  }

  function backoffMs(n: number): number {
    const grown = Math.min(RECONNECT_FLOOR_MS * 2 ** (n - 1), RECONNECT_CEILING_MS);
    return grown + Math.floor(random() * RECONNECT_JITTER_MS);
  }

  function openStream(): void {
    pending = null;
    const handle = options.createStream();
    stream = handle;
    handle.addEventListener('snapshot', onSnapshot);
    handle.addEventListener('update', onUpdate);
    (handle as unknown as WideStream).addEventListener('error', onError);
  }

  function onError(): void {
    // 不论原生流自己是 CLOSED 还是还在 CONNECTING，都关掉它自己排重连，不与浏览器自带的重连叠加。
    closeStream();
    failures += 1;
    setReconnectCount(failures);
    setConnectionState('reconnecting');
    clearPending();
    pending = setTimer(openStream, backoffMs(failures));
  }

  // snapshot 整份替换、不比较序号大小（服务重启后序号变小也照样替换），并重置基线与重连次数。
  function onSnapshot(event: LiveStreamEvent): void {
    const seq = parseSeq(event.lastEventId);
    if (seq === null) return;
    const push = parseEnvelope(event.data);
    if (push === undefined) return;
    baseline = seq;
    failures = 0;
    setReconnectCount(0);
    setConnectionState('connected');
    if (push.ok && push.data != null) {
      status = push.data as StatusData;
      notify();
    }
  }

  function onUpdate(event: LiveStreamEvent): void {
    const seq = parseSeq(event.lastEventId);
    if (seq === null) return;
    if (baseline === null || seq <= baseline) return;
    const push = parseEnvelope(event.data);
    if (push === undefined) return;
    baseline = seq;
    if (push.ok && push.data != null) {
      status = push.data as StatusData;
      notify();
    }
  }

  return {
    subscribe(listener: () => void): () => void {
      listeners.add(listener);
      if (listeners.size === 1) openStream();
      let alive = true;
      return () => {
        if (!alive) return;
        alive = false;
        listeners.delete(listener);
        if (listeners.size > 0) return;
        closeStream();
        clearPending();
        failures = 0;
        setReconnectCount(0);
        // 退订时没有流在维持连接：等待期写的 reconnecting 要收回，否则界面一直说在重连。
        if (getConnectionState() === 'reconnecting') setConnectionState('disconnected');
      };
    },
    getStatus(): StatusData | null {
      return status;
    },
    getReconnectCount(): number {
      return failures;
    },
  };
}

function createDefaultStream(): LiveStreamHandle {
  return new EventSource('/api/v1/events') as unknown as LiveStreamHandle;
}

let injectedFactory: (() => LiveStreamHandle) | undefined;

// 只给包内测试换掉默认实例的建流方式；传 undefined 恢复默认。开关判断不经过它，永远只有 liveModeIsReal()。
export function setEventStreamFactoryForTests(factory: (() => LiveStreamHandle) | undefined): void {
  injectedFactory = factory;
}

const core = createLiveEvents({
  createStream: () => (injectedFactory ?? createDefaultStream)(),
  setTimer: (fn: () => void, delayMs: number) => setTimeout(fn, delayMs),
  clearTimer: (handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  random: () => Math.random(),
});

// 默认实例：夹具模式订阅是空操作（不登记监听者、不建流、不排计时器），真实模式才把订阅交给 core。
export const liveEvents: LiveEvents = {
  subscribe(listener: () => void): () => void {
    if (!liveModeIsReal()) return () => {};
    return core.subscribe(listener);
  },
  getStatus(): StatusData | null {
    return liveModeIsReal() ? core.getStatus() : null;
  },
  getReconnectCount(): number {
    return liveModeIsReal() ? core.getReconnectCount() : 0;
  },
};
