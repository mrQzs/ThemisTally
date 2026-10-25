// SSE 广播（桌面端设计第 7 版 §5.3、T3、D01–D11、D27–D30）：GET /api/v1/events 是本机服务的实时通道。一个服务一个
// EventHub：第一个订阅者到来才起 status，每轮间隔 STAT_INTERVAL_MS 只 stat 内核名单（watch.ts）察觉变化，去抖
// DEBOUNCE_MS 之后跑一次 status（与读路由共用同一个执行器与并发上限），同一时刻最多一次 status，一次结果交给全部
// 订阅者。流一打开先写 retry 与一个空行，每次订阅第一条是 snapshot（带当时序号），之后只在名单上的输入变了才推一份
// 整份新信封（update），序号按内容不同单调递增。心跳写失败立刻清理；会话作废、服务关停主动关流。连接管理：全局与每
// 会话订阅上限，超限回 503 带 Retry-After 且不挤掉已有订阅。Bun 的连接空闲超时对这一条请求的放宽（server.timeout(req, 0)）
// 在 server.ts 做，本文件只管广播与订阅生命周期。
import { readSessionCookie, type Sessions } from "./localhttp/index.ts";
import { errorResponse } from "./envelope.ts";
import { envelopeBody, statusEnvelope, timeoutEnvelope } from "./kernelenvelope.ts";
import type { RunKernel } from "./kernel.ts";
import { fingerprint } from "./watch.ts";
import type { Route } from "./routes.ts";

/** stat 的轮询间隔（毫秒）：整个服务一个 EventHub，setTimeout 链各轮不重叠。 */
export const STAT_INTERVAL_MS = 2000;
/** 去抖：某一轮发现指纹变了之后等这么久再起 status。 */
export const DEBOUNCE_MS = 300;
/** 心跳间隔（毫秒）：写一行 `: hb`。 */
export const HEARTBEAT_MS = 15000;
/** 告诉客户端的重连等待下限（毫秒）：比 stat 的 2 秒节奏长。 */
export const RETRY_MS = 3000;
/** status 的时限（秒）：与 /api/v1/status 同档。 */
const STATUS_TIMEOUT_SECONDS = 30;
/** 全局同时开着的订阅数上限。 */
export const MAX_SUBSCRIPTIONS = 16;
/** 同一个会话的订阅数上限。 */
export const MAX_SUBSCRIPTIONS_PER_SESSION = 4;
/** 全局超限的提示原文。 */
export const SSE_LIMIT_GLOBAL_MESSAGE = "SSE 订阅数已达上限";
/** 会话级超限的提示原文。 */
export const SSE_LIMIT_SESSION_MESSAGE = "该会话的 SSE 订阅数已达上限";

const ENCODER = new TextEncoder();

/** 一个订阅者：会话令牌、流的写入口、有没有发过 snapshot。 */
interface Subscriber {
  readonly token: string;
  readonly controller: ReadableStreamDefaultController<Uint8Array>;
  sentSnapshot: boolean;
}

export interface EventHubOptions {
  readonly repo: string;
  readonly runner: RunKernel;
  /** stat 轮询间隔覆盖（只给测试入口）。 */
  readonly statIntervalMs?: number;
  /** 去抖覆盖（只给测试入口）。 */
  readonly debounceMs?: number;
  /** 心跳间隔覆盖（只给测试入口）。 */
  readonly heartbeatMs?: number;
  /** status 时限覆盖（秒；只给测试入口）。 */
  readonly statusTimeoutSeconds?: number;
  /** 全局订阅上限覆盖（只给测试入口）。 */
  readonly maxSubscriptions?: number;
  /** 每会话订阅上限覆盖（只给测试入口）。 */
  readonly maxSubscriptionsPerSession?: number;
}

/** SSE 广播中枢：起停、去抖、共享、序号、心跳、会话检查、连接上限与主动断开。 */
export class EventHub {
  private readonly repo: string;
  private readonly runner: RunKernel;
  private readonly statIntervalMs: number;
  private readonly debounceMs: number;
  private readonly heartbeatMs: number;
  private readonly statusTimeoutSeconds: number;
  private readonly maxSubscriptions: number;
  private readonly maxSubscriptionsPerSession: number;

  private readonly subs = new Set<Subscriber>();
  // 会话池：订阅时由路由处理器交进来（与 control.bootstrap 作废的是同一个实例，A11）
  private sessions: Sessions | null = null;
  // 序号：服务启动后从 0 起，每产生一份内容不同的信封加 1（内容相同不推也不加号）；订阅者归零时不重置
  private seq = 0;
  // 当前缓存的信封正文（订阅者归零时丢掉）；null 表示没有缓存
  private lastBody: string | null = null;
  private lastFingerprint: string | null = null;
  private statTimer: ReturnType<typeof setTimeout> | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private statusController: AbortController | null = null;
  private running = false;
  private dirty = false;
  private retryPending = false;

  constructor(options: EventHubOptions) {
    this.repo = options.repo;
    this.runner = options.runner;
    this.statIntervalMs = options.statIntervalMs ?? STAT_INTERVAL_MS;
    this.debounceMs = options.debounceMs ?? DEBOUNCE_MS;
    this.heartbeatMs = options.heartbeatMs ?? HEARTBEAT_MS;
    this.statusTimeoutSeconds = options.statusTimeoutSeconds ?? STATUS_TIMEOUT_SECONDS;
    this.maxSubscriptions = options.maxSubscriptions ?? MAX_SUBSCRIPTIONS;
    this.maxSubscriptionsPerSession = options.maxSubscriptionsPerSession ?? MAX_SUBSCRIPTIONS_PER_SESSION;
  }

  /** 同时开着的订阅数（空闲判定看它：订阅开着算活动）。 */
  get subscribers(): number {
    return this.subs.size;
  }

  /**
   * 开一条订阅：先查连接上限（全局 / 每会话），超限就不建订阅、回 503 带 Retry-After: 2，不挤掉已有的订阅。通过了
   * 就建流、写 retry、有缓存就立刻发 snapshot，没有缓存就由随后的 status 补上；起心跳与 stat。sessions 与 control.
   * bootstrap 作废的是同一个实例（A11），令牌在订阅时取一次。signal abort 与 cancel 都摘掉订阅者。
   */
  open(sessions: Sessions, token: string | null, signal: AbortSignal): Response {
    this.sessions = sessions;
    const sessionToken = token ?? "";
    const perSession = [...this.subs].filter((sub) => sub.token === sessionToken).length;
    if (this.subs.size >= this.maxSubscriptions) return sseLimit(SSE_LIMIT_GLOBAL_MESSAGE);
    if (perSession >= this.maxSubscriptionsPerSession) return sseLimit(SSE_LIMIT_SESSION_MESSAGE);

    let subscriber: Subscriber | null = null;
    const stream = new ReadableStream<Uint8Array>({
      start: (controller) => {
        const sub: Subscriber = { token: sessionToken, controller, sentSnapshot: false };
        subscriber = sub;
        this.subs.add(sub);
        this.write(sub, `retry: ${RETRY_MS}\n\n`);
        if (this.lastBody !== null) {
          // 有缓存：立刻把当前快照发给这个订阅者（序号沿用缓存的那一个，不加号）
          this.send(sub, "snapshot", this.seq, this.lastBody);
          sub.sentSnapshot = true;
        }
      },
      cancel: () => {
        if (subscriber !== null) this.drop(subscriber); // 客户端断开：摘掉订阅者
      },
    });
    const sub = subscriber as Subscriber | null;
    if (sub === null) return sseLimit(SSE_LIMIT_GLOBAL_MESSAGE); // 理论到不了（ReadableStream 一定调 start）
    const onAbort = (): void => this.drop(sub);
    if (signal.aborted) this.drop(sub);
    else signal.addEventListener("abort", onAbort, { once: true });
    this.ensureHeartbeat();
    this.ensureStat();
    return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream; charset=utf-8" } });
  }

  /** 关停：关掉全部流、清全部定时器、中止在跑的 status（server.ts 在 runner.shutdown() 之前调它）。 */
  close(): void {
    for (const sub of [...this.subs]) {
      try {
        sub.controller.close();
      } catch {
        // 已经关了
      }
    }
    this.subs.clear();
    this.stopLoops();
  }

  /** 起心跳定时器（订阅者为 0 时由 stopLoops 停）。 */
  private ensureHeartbeat(): void {
    if (this.heartbeatTimer !== null) return;
    this.heartbeatTimer = setInterval(() => this.heartbeat(), this.heartbeatMs);
    this.heartbeatTimer.unref?.();
  }

  /** 起 stat 循环（第一个订阅者到来时先记基线指纹，再起第一次 status）。 */
  private ensureStat(): void {
    if (this.statTimer !== null) return;
    void this.startLoop();
  }

  /** 先记基线指纹（订阅当下的 runs 状态），再起第一次 status 出快照，然后按间隔轮询。 */
  private async startLoop(): Promise<void> {
    this.lastFingerprint = await fingerprint(this.repo);
    if (this.subs.size === 0) return;
    void this.runStatus();
    this.scheduleTick();
  }

  /** 排下一轮 stat（setTimeout 链，各轮不重叠）。 */
  private scheduleTick(): void {
    if (this.statTimer !== null) return;
    const tick = async (): Promise<void> => {
      if (this.subs.size === 0) {
        this.statTimer = null;
        return;
      }
      const current = await fingerprint(this.repo);
      if (this.subs.size === 0) {
        this.statTimer = null;
        return;
      }
      if (this.retryPending || current !== this.lastFingerprint) {
        this.lastFingerprint = current;
        if (this.running) this.dirty = true; // 在跑期间又有变化：记 dirty，跑完只补跑一次
        else this.scheduleRefresh();
      }
      this.statTimer = setTimeout(() => void tick(), this.statIntervalMs);
    };
    this.statTimer = setTimeout(() => void tick(), this.statIntervalMs);
  }

  /** 排一次刷新：去抖 DEBOUNCE_MS 之后再起 status（一阵连续写入只惊动一次）。 */
  private scheduleRefresh(): void {
    if (this.debounceTimer !== null) return;
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      void this.runStatus();
    }, this.debounceMs);
    this.debounceTimer.unref?.();
  }

  /** 跑一次 status：同一时刻最多一次；queue-full / closing 不推送、记 retryPending；timeout 推超时信封。 */
  private async runStatus(): Promise<void> {
    if (this.running || this.subs.size === 0) return;
    this.running = true;
    const controller = new AbortController();
    this.statusController = controller;
    const argv = ["status", "--json"];
    let outcome;
    try {
      outcome = await this.runner.run(argv, this.statusTimeoutSeconds, controller.signal);
    } finally {
      this.statusController = null;
      this.running = false;
    }
    if (controller.signal.aborted || this.subs.size === 0) return; // 被取消或订阅者归零：不推送
    if (outcome.kind === "completed") {
      const built = statusEnvelope(outcome, argv);
      if (built.kind === "envelope") {
        this.retryPending = false;
        this.push(envelopeBody(built.envelope));
      }
      // 退出 0 却解析不了：保留旧快照，不推送
    } else if (outcome.kind === "timeout") {
      this.retryPending = false;
      this.push(envelopeBody(timeoutEnvelope(argv, this.statusTimeoutSeconds, outcome.result.wall_seconds)));
    } else if (outcome.kind === "queue-full" || outcome.kind === "closing") {
      this.retryPending = true; // 队列满或服务正在关闭：不推送，下一轮即使指纹没变也重试
    } else {
      this.retryPending = true; // spawn-error / output-too-large / interrupted：也不推送，保留旧快照
    }
    if (this.dirty) {
      this.dirty = false;
      void this.runStatus();
    }
  }

  /** 产生一份新信封：内容与缓存不同才推（推的是整份新信封），序号加 1；相同就不推也不加号。 */
  private push(body: string): void {
    if (body === this.lastBody) return;
    this.seq += 1;
    this.lastBody = body;
    for (const sub of [...this.subs]) {
      this.send(sub, sub.sentSnapshot ? "update" : "snapshot", this.seq, body);
      sub.sentSnapshot = true;
    }
  }

  /** 给一个订阅者写一份事件（id + event + data 行）；会话失效或写失败都清掉这个订阅者。 */
  private send(sub: Subscriber, event: string, seq: number, body: string): void {
    if (this.sessions !== null && !this.sessions.valid(sub.token)) {
      this.drop(sub); // 会话作废（revokeAll 之后 valid 为 false，含换发引导地址那条路）
      return;
    }
    const lines = [`id: ${seq}`, `event: ${event}`];
    for (const line of body.split("\n")) lines.push(`data: ${line}`);
    if (!this.write(sub, `${lines.join("\n")}\n\n`)) this.drop(sub); // 写失败（客户端消失）：立刻清理
  }

  /** 给全部订阅者写心跳：每次写之前查会话，失效或写失败都清掉那个订阅者。 */
  private heartbeat(): void {
    for (const sub of [...this.subs]) {
      if (this.sessions !== null && !this.sessions.valid(sub.token)) {
        this.drop(sub);
        continue;
      }
      if (!this.write(sub, ": hb\n\n")) this.drop(sub); // 心跳写失败：立刻清理，不等空闲超时
    }
  }

  /** 往一个订阅者的流里写文本：失败（流已关/客户端消失）返回 false。 */
  private write(sub: Subscriber, text: string): boolean {
    try {
      sub.controller.enqueue(ENCODER.encode(text));
      return true;
    } catch {
      return false;
    }
  }

  /** 摘掉一个订阅者：关流、清它占用的名额，订阅者归零就停 stat、心跳并取消在跑的 status、丢缓存。 */
  private drop(sub: Subscriber): void {
    if (!this.subs.delete(sub)) return;
    try {
      sub.controller.close();
    } catch {
      // 已经关了
    }
    if (this.subs.size === 0) this.stopLoops();
  }

  /** 停掉全部定时器、中止在跑的 status、丢掉缓存的快照与指纹（序号不重置）。 */
  private stopLoops(): void {
    if (this.statTimer !== null) {
      clearTimeout(this.statTimer);
      this.statTimer = null;
    }
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.statusController !== null) {
      this.statusController.abort(); // 取消在跑的那次 status（hub 自己的 AbortController）
      this.statusController = null;
    }
    this.lastBody = null;
    this.lastFingerprint = null;
    this.dirty = false;
    this.retryPending = false;
  }
}

/** 订阅超限的 503：服务自己的错误信封，带 Retry-After: 2。 */
function sseLimit(message: string): Response {
  const response = errorResponse(503, message);
  response.headers.set("retry-after", "2");
  return response;
}

/**
 * SSE 的路由（与 jobRoutes 的做法对称，另建一批、不并进 readRoutes()）：路由名 api.events、方法 GET、路径
 * /api/v1/events、不标 public（照 T17 走会话检查，没有会话 cookie 由管线回 401）。响应头由既有管线照常套上。
 */
export function eventRoutes(hub: EventHub): readonly Route[] {
  return [
    {
      name: "api.events",
      method: "GET",
      pattern: /^\/api\/v1\/events$/u,
      handle: (state, _params, input) => hub.open(state.sessions, readSessionCookie(input.request.headers), input.request.signal),
    },
  ];
}
