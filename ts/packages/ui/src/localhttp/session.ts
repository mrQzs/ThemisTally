// 一次性引导地址与会话（桌面端设计第 7 版 §5.2、§5.3）：外壳从握手行拿到 http://127.0.0.1:<port>/bootstrap/<nonce>，
// 在用户的浏览器里打开它；这一步消耗 nonce、建会话、302 到 / 并带上会话 cookie。之后浏览器只认 cookie，引导地址
// 本身再也用不了第二次（D03）。过期与用过、不存在三种拒绝返回同一个响应，探测者分不出差别。
import { randomToken } from "./tokens.ts";
import { sessionSetCookie } from "./cookie.ts";

/** 引导地址的有效期：60 秒。 */
export const NONCE_TTL_MS = 60000;

/** 一次性的引导地址池：issue 发一个，consume 消耗一个（先查、无条件删、再判有效期）。 */
export class BootstrapNonces {
  private readonly issued = new Map<string, number>();

  private readonly now: () => number;
  private readonly ttlMs: number;

  constructor(now: () => number = Date.now, ttlMs: number = NONCE_TTL_MS) {
    this.now = now;
    this.ttlMs = ttlMs;
  }

  /** 发一个新 nonce，顺带清理过期项。 */
  issue(): string {
    this.sweep();
    const nonce = randomToken();
    this.issued.set(nonce, this.now());
    return nonce;
  }

  /** 消耗一个 nonce：用过、不存在、过期都返回 false；59999 毫秒可用，60000 毫秒拒绝。 */
  consume(nonce: string): boolean {
    this.sweep();
    const issuedAt = this.issued.get(nonce);
    this.issued.delete(nonce);
    if (issuedAt === undefined) return false;
    return this.now() - issuedAt < this.ttlMs;
  }

  /** 全部作废（控制接口换引导地址时用）。 */
  revokeAll(): void {
    this.issued.clear();
  }

  private sweep(): void {
    const now = this.now();
    for (const [nonce, issuedAt] of [...this.issued]) {
      if (now - issuedAt >= this.ttlMs) this.issued.delete(nonce);
    }
  }
}

/** 会话池：只在内存里，进程结束即丢。 */
export class Sessions {
  private readonly live = new Set<string>();

  /** 建一个会话，返回令牌。 */
  create(): string {
    const token = randomToken();
    this.live.add(token);
    return token;
  }

  /** null 与空串都不是有效会话。 */
  valid(token: string | null): boolean {
    return token !== null && token !== "" && this.live.has(token);
  }

  /** 全部作废。 */
  revokeAll(): void {
    this.live.clear();
  }
}

/** 引导成功：302 到 /，带上会话 cookie（不带 Max-Age、不带 Secure）。 */
export function bootstrapAccepted(token: string): Response {
  return new Response(null, {
    status: 302,
    headers: { location: "/", "set-cookie": sessionSetCookie(token) },
  });
}

/** 引导失败：404、纯文本、正文固定。过期、用过、不存在三种情况共用这一个响应。 */
export function bootstrapRejected(): Response {
  return new Response("引导地址无效\n", {
    status: 404,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
