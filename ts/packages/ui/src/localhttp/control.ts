// 控制接口的令牌校验（桌面端设计第 7 版 §5.2、T7c）：换引导地址只能由外壳发起，令牌放在 X-Themis-Control 头里，
// 从不看 cookie（网页拿不到也发不出这个头以外的凭证）。比较恒定时间；连续失败到第 5 次起锁定，锁定时长翻倍、
// 60 秒封顶，锁定期内直接 429（不比较、不计数），成功之后计数清零。
import { constantTimeEqual } from "./tokens.ts";

/** 控制令牌的头名字（从不看 cookie：网页带得上 cookie，带不上这个头）。 */
export const CONTROL_HEADER = "x-themis-control";

/** 连续失败到第几次起锁定。 */
export const CONTROL_MAX_FAILURES = 5;
/** 第一次锁定的毫秒数（之后每次翻倍）。 */
export const CONTROL_LOCK_BASE_MS = 1000;
/** 锁定毫秒数的上限。 */
export const CONTROL_LOCK_MAX_MS = 60000;

export type ControlVerdict =
  | { readonly ok: true }
  | { readonly ok: false; readonly status: 403 }
  | { readonly ok: false; readonly status: 429; readonly retryAfterSeconds: number };

/** 一锤子买卖的令牌门：只管比较与限速，不管请求从哪来（那是 guards.ts 的事）。 */
export class ControlGate {
  private failures = 0;
  private lockedUntil = 0;

  private readonly token: string;
  private readonly now: () => number;

  constructor(token: string, now: () => number = Date.now) {
    this.token = token;
    this.now = now;
  }

  /** 锁定期内直接 429；否则只用恒定时间比较令牌，失败计数、成功清零。 */
  check(headers: Headers): ControlVerdict {
    const now = this.now();
    if (now < this.lockedUntil) {
      return { ok: false, status: 429, retryAfterSeconds: Math.max(1, Math.ceil((this.lockedUntil - now) / 1000)) };
    }
    if (constantTimeEqual(headers.get(CONTROL_HEADER), this.token)) {
      this.failures = 0;
      return { ok: true };
    }
    this.failures += 1;
    if (this.failures >= CONTROL_MAX_FAILURES) {
      const span = CONTROL_LOCK_BASE_MS * 2 ** (this.failures - CONTROL_MAX_FAILURES);
      this.lockedUntil = now + Math.min(span, CONTROL_LOCK_MAX_MS);
    }
    return { ok: false, status: 403 };
  }
}
