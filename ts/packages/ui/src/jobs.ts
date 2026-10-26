// 作业表（桌面端设计第 7 版 §5.3、D16–D19）：作业路由起的每一次内核命令在内存里登记成一条作业，服务退出就丢，不写
// .agent/。作业号是 crypto.randomBytes(32) 转 base64url 的 43 个字符（随机、不可猜，不含序号或时间，与 cursors 的句柄
// 同一种写法）。容量 MAX_JOBS = 100，插入时满了就淘汰最早结束的终态作业，没有可淘汰的回 503。状态从 queued 到
// running 再到四种终态之一（succeeded / failed / cancelled / timed_out），每一步只走一次。每个作业有自己的
// AbortController（作业比创建它的 POST 请求活得久，不用请求的 signal）。
import { randomBytes } from "node:crypto";

/** 作业表容量。 */
export const MAX_JOBS = 100;
/** 作业号的形状：43 个 base64url 字符。 */
export const JOB_ID_RE = /^[A-Za-z0-9_-]{43}$/u;

/** 六个作业 kind（A6/A7 的现成内核写法）。 */
export type JobKind = "doctor" | "doctor-record" | "runtime-scan" | "runtime-probe" | "models" | "search";

/** 作业状态：queued → running → 四种终态之一，每步只走一次。 */
export type JobState = "queued" | "running" | "succeeded" | "failed" | "cancelled" | "timed_out";

/** failed 的原因：服务这一侧出错记 spawn-error / output-too-large / invalid-json / closing，退出非 0 记 exit。 */
export type JobReason = "exit" | "spawn-error" | "output-too-large" | "invalid-json" | "closing";

/** 四种终态。 */
const TERMINAL: ReadonlySet<JobState> = new Set<JobState>(["succeeded", "failed", "cancelled", "timed_out"]);

/** 是不是终态（取消已结束的作业回 409、空闲判定看非终态数都用它）。 */
export function isTerminal(state: JobState): boolean {
  return TERMINAL.has(state);
}

/** 一条作业的内部记录（暴露给界面的只是 jobView 投影出的八键对象，controller 与 argv 不出去）。 */
export interface JobRecord {
  readonly id: string;
  /** 六个作业 kind，加上凭据录入作业（不并进 JOB_KINDS 四张表）。 */
  readonly kind: JobKind | "secret-entry";
  readonly argv: readonly string[];
  readonly timeoutSeconds: number;
  readonly created_ms: number;
  /** 作业自己的取消信号（取消在跑的执行器整棵树结束）。 */
  readonly controller: AbortController;
  /** 这次运行的 Promise（取消时等它落到终态）。 */
  run: Promise<void>;
  /** 子进程结束就落定的 Promise：六类作业它就是 run，录入作业的子进程一结束就落定（不等重查）。 */
  exited: Promise<void>;
  state: JobState;
  reason: JobReason | null;
  started_ms: number | null;
  finished_ms: number | null;
  envelope: Record<string, unknown> | null;
}

/** 随机不可猜的作业号：32 字节 base64url，43 个字符。 */
export function newJobId(): string {
  return randomBytes(32).toString("base64url");
}

/** queued 变 running（执行器经 hooks.onStart 通知）：只走一次。 */
export function markRunning(record: JobRecord, now: number): void {
  if (record.state === "queued") {
    record.state = "running";
    record.started_ms = now;
  }
}

/** 落到终态：只走一次（重复交代忽略）。 */
export function settle(record: JobRecord, state: JobState, reason: JobReason | null, envelope: Record<string, unknown> | null, now: number): void {
  if (TERMINAL.has(record.state)) return;
  record.state = state;
  record.reason = reason;
  record.envelope = envelope;
  record.finished_ms = now;
}

/** 只在内存里的作业表：Map 的插入次序即创建次序。 */
export class JobTable {
  private readonly records = new Map<string, JobRecord>();

  /**
   * 建一个作业（state=queued）。满了先淘汰最早结束的终态作业；没有可淘汰的终态作业时返回 null（调用方回 503 带
   * Retry-After）。实际上在等加在跑的作业最多只有执行器的 4 加 16 个，100 个满表时总有终态的可以淘汰。
   */
  create(kind: JobKind | "secret-entry", argv: readonly string[], timeoutSeconds: number, now: number): JobRecord | null {
    if (this.records.size >= MAX_JOBS && !this.evictOldestTerminal()) return null;
    const id = newJobId();
    const record: JobRecord = {
      id,
      kind,
      argv,
      timeoutSeconds,
      created_ms: now,
      controller: new AbortController(),
      run: Promise.resolve(),
      exited: Promise.resolve(),
      state: "queued",
      reason: null,
      started_ms: null,
      finished_ms: null,
      envelope: null,
    };
    this.records.set(id, record);
    return record;
  }

  /** 按作业号取记录；不在表里返回 null。 */
  get(id: string): JobRecord | null {
    return this.records.get(id) ?? null;
  }

  /** 表里多少项（测试观察用）。 */
  get size(): number {
    return this.records.size;
  }

  /** 非终态作业数（空闲判定看它：没有在等或在跑的作业才退出）。 */
  active(): number {
    let count = 0;
    for (const record of this.records.values()) if (!TERMINAL.has(record.state)) count += 1;
    return count;
  }

  /** 淘汰最早结束（finished_ms 最小）的终态作业；没有可淘汰的返回 false。 */
  private evictOldestTerminal(): boolean {
    let oldestId: string | null = null;
    let oldestTime = Number.POSITIVE_INFINITY;
    for (const [id, record] of this.records) {
      if (!TERMINAL.has(record.state)) continue;
      if (record.finished_ms !== null && record.finished_ms < oldestTime) {
        oldestTime = record.finished_ms;
        oldestId = id;
      }
    }
    if (oldestId === null) return false;
    this.records.delete(oldestId);
    return true;
  }
}

/** 作业对象暴露给界面的八键投影（D31：创建与查询的正文都是它，不套信封、不套 data；八个键一个不能少，值可 null）。 */
export function jobView(record: JobRecord): Record<string, unknown> {
  return {
    id: record.id,
    kind: record.kind,
    state: record.state,
    reason: record.reason,
    created_ms: record.created_ms,
    started_ms: record.started_ms,
    finished_ms: record.finished_ms,
    envelope: record.envelope,
  };
}
