// 预览确认号表（桌面端设计第 7 版 §5.3、D6/D13）：预览成功时签发一个 43 位 base64url 的确认号，执行时把它原样带回，
// 服务据此核对「就是这条命令、还没被用过、还没过期」。记录只绑 {action, 基础 argv, state 令牌, needsYes, issued_ms}，
// 不绑会话（界面拿号之后重连、刷新都能用；会话失效不影响已签发但没用过的号）。表只在内存里，服务退出即失效。
// 有效期 CONFIRMATION_TTL_MS（60 秒，从签发算起）；容量 MAX_CONFIRMATIONS（100），满了先清过期的、清完还满就挤掉
// 最早发出还没用的那一个（被挤掉的号与过期等价，界面重新预览即可，不回 503——不停预览的页面不该把自己堵死）。
import { randomBytes } from "node:crypto";

/** 确认号的有效期（毫秒）：从签发算起 60 秒。 */
export const CONFIRMATION_TTL_MS = 60_000;
/** 确认号表的容量。 */
export const MAX_CONFIRMATIONS = 100;
/** 确认号的形状：randomBytes(32) 转 base64url 的 43 个字符。 */
export const CONFIRMATION_ID_RE = /^[A-Za-z0-9_-]{43}$/u;

/** 一条确认号记录：绑定的内容（不含会话）。 */
export interface ConfirmationRecord {
  readonly id: string;
  readonly action: string;
  /** 预览时拼出的基础 argv（执行时与请求拼出的基础 argv 逐项比对）。 */
  readonly argv: readonly string[];
  /** 内核预览给的 state 令牌（执行时原样带进 --expect-state=）。 */
  readonly state: string;
  /** 预览的 needs_yes（执行时真才加 --yes）。 */
  readonly needsYes: boolean;
  /** 签发时刻（毫秒），TTL 从它算起。 */
  readonly issued_ms: number;
}

/** 构造参数：时钟 now 可注入（测试拨过 60 秒）、ttlMs 只给测试入口覆盖（生产路径用缺省值）。 */
export interface ConfirmationTableOptions {
  readonly now?: (() => number) | undefined;
  readonly ttlMs?: number | undefined;
}

/** 只在内存里的确认号表：Map 的插入次序即签发次序。 */
export class ConfirmationTable {
  private readonly records = new Map<string, ConfirmationRecord>();
  private readonly now: () => number;
  private readonly ttlMs: number;

  constructor(options: ConfirmationTableOptions = {}) {
    this.now = options.now ?? Date.now;
    this.ttlMs = options.ttlMs ?? CONFIRMATION_TTL_MS;
  }

  /** 表里多少项（测试观察用）。 */
  get size(): number {
    return this.records.size;
  }

  /** 签发一个确认号（满了先清过期的、再挤最早发出的未用号）。 */
  issue(action: string, argv: readonly string[], state: string, needsYes: boolean): ConfirmationRecord {
    this.makeRoom();
    const record: ConfirmationRecord = {
      id: randomBytes(32).toString("base64url"),
      action,
      argv: [...argv],
      state,
      needsYes,
      issued_ms: this.now(),
    };
    this.records.set(record.id, record);
    return record;
  }

  /** 按号取记录：不在表里或已过期都回 null（过期的一次性清掉）。 */
  get(id: string): ConfirmationRecord | null {
    const record = this.records.get(id);
    if (record === undefined) return null;
    if (this.expired(record)) {
      this.records.delete(id);
      return null;
    }
    return record;
  }

  /** 用掉一个号（从表里拿走）：返回是不是真的拿走了。 */
  consume(id: string): boolean {
    return this.records.delete(id);
  }

  /** 过期判定：从签发算起超过 TTL（正好 TTL 仍有效）。 */
  private expired(record: ConfirmationRecord): boolean {
    return this.now() - record.issued_ms > this.ttlMs;
  }

  /** 腾位置：先清全部过期的；清完还满就挤掉最早发出、还没用的那一个（用过的已不在表里）。 */
  private makeRoom(): void {
    if (this.records.size < MAX_CONFIRMATIONS) return;
    const now = this.now();
    for (const [id, record] of this.records) {
      if (now - record.issued_ms > this.ttlMs) this.records.delete(id);
    }
    if (this.records.size < MAX_CONFIRMATIONS) return;
    let oldestId: string | null = null;
    let oldestTime = Number.POSITIVE_INFINITY;
    for (const [id, record] of this.records) {
      if (record.issued_ms < oldestTime) {
        oldestTime = record.issued_ms;
        oldestId = id;
      }
    }
    if (oldestId !== null) this.records.delete(oldestId);
  }
}

/** 绑定核对：基础 argv 的长度不同或有一项不同即判不符（确认号与这次请求的参数不符）。 */
export function argvMatches(bound: readonly string[], built: readonly string[]): boolean {
  if (bound.length !== built.length) return false;
  return bound.every((part, index) => part === built[index]);
}
