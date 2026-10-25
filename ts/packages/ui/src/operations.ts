// 操作记录表（桌面端设计第 7 版 §5.3、D6/D10/D11）：七条写路由每执行一次就在内存里登记一条操作，服务退出就丢，不写
// .agent/。记录 id 就是那次预览签发的确认号（43 位 base64url）。状态机 queued → running → succeeded | failed | stale |
// timed_out，每一步只走一次（照 jobs.ts 的 markRunning/settle）。failed 的 reason：exit（退出非 0 且不是 4）、
// spawn-error、output-too-large、closing。容量 MAX_OPERATIONS = 100，插入时满了就淘汰最早结束的终态记录，没有可淘汰的
// 回 503（调用方据此在不消耗确认号的前提下回绝）。记录里存完整信封（已脱敏），operationView 是暴露给界面的八键投影。
import { redactSecrets } from "@themis/base/secrets";
import { errorResponse } from "./envelope.ts";
import { type RunOutcome } from "./kernel.ts";
import { displayArgv, elapsedMsOf, envelopeBody, messagesOf, type KernelEnvelope } from "./kernelenvelope.ts";

/** 操作表容量。 */
export const MAX_OPERATIONS = 100;
/** 操作号的形状：就是确认号，43 位 base64url。 */
export const OPERATION_ID_RE = /^[A-Za-z0-9_-]{43}$/u;

/** 操作状态：queued → running → 四种终态之一，每步只走一次。 */
export type OperationState = "queued" | "running" | "succeeded" | "failed" | "stale" | "timed_out";

/** failed 的原因：退出非 0 且不是 4 记 exit；服务这一侧出错记 spawn-error / output-too-large / closing。 */
export type OperationReason = "exit" | "spawn-error" | "output-too-large" | "closing";

/** 四种终态。 */
const TERMINAL: ReadonlySet<OperationState> = new Set(["succeeded", "failed", "stale", "timed_out"]);

/** 是不是终态（空闲判定与淘汰都看它）。 */
export function isTerminal(state: OperationState): boolean {
  return TERMINAL.has(state);
}

/** 一条操作的内部记录（暴露给界面的只是 operationView 投影出的八键对象，response 与 run 不出去）。 */
export interface OperationRecord {
  readonly id: string;
  readonly action: string;
  readonly argv: readonly string[];
  readonly timeoutSeconds: number;
  created_ms: number;
  state: OperationState;
  reason: OperationReason | null;
  started_ms: number | null;
  finished_ms: number | null;
  envelope: Record<string, unknown> | null;
  /** 这次运行的 Promise（处理函数 await 它再回响应；断开不取消，终态照记）。 */
  run: Promise<void>;
  /** 处理函数要回的响应（终态落定后由运行方填；断开时写了也没人收，但不影响记录）。 */
  response: Response | null;
}

/** queued 变 running（执行器经 hooks.onStart 通知）：只走一次。 */
export function markRunning(record: OperationRecord, now: number): void {
  if (record.state === "queued") {
    record.state = "running";
    record.started_ms = now;
  }
}

/** 落到终态：只走一次（重复交代忽略）。 */
export function settle(
  record: OperationRecord,
  state: OperationState,
  reason: OperationReason | null,
  envelope: Record<string, unknown> | null,
  now: number,
): void {
  if (TERMINAL.has(record.state)) return;
  record.state = state;
  record.reason = reason;
  record.envelope = envelope;
  record.finished_ms = now;
}

/** 只在内存里的操作表：Map 的插入次序即创建次序。 */
export class OperationTable {
  private readonly records = new Map<string, OperationRecord>();

  /**
   * 建一条操作（state=queued，id 就是确认号）。满了先淘汰最早结束的终态记录；没有可淘汰的终态记录时返回 null
   * （调用方回 503 且不消耗确认号——顺序固定：先看操作表能不能收，再拿确认号）。
   */
  create(id: string, action: string, argv: readonly string[], timeoutSeconds: number, now: number): OperationRecord | null {
    if (this.records.size >= MAX_OPERATIONS && !this.evictOldestTerminal()) return null;
    const record: OperationRecord = {
      id,
      action,
      argv,
      timeoutSeconds,
      created_ms: now,
      state: "queued",
      reason: null,
      started_ms: null,
      finished_ms: null,
      envelope: null,
      run: Promise.resolve(),
      response: null,
    };
    this.records.set(id, record);
    return record;
  }

  /** 按操作号取记录；不在表里返回 null。 */
  get(id: string): OperationRecord | null {
    return this.records.get(id) ?? null;
  }

  /** 表里多少项（测试观察用）。 */
  get size(): number {
    return this.records.size;
  }

  /** 非终态操作数（空闲判定看它：有写在跑时服务不因空闲退出）。 */
  active(): number {
    let count = 0;
    for (const record of this.records.values()) if (!TERMINAL.has(record.state)) count += 1;
    return count;
  }

  /** 淘汰最早结束（finished_ms 最小）的终态记录；没有可淘汰的返回 false。 */
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

/** 操作对象暴露给界面的八键投影（创建与查询的正文都是它，不套信封、不套 data；八个键一个不能少，值可 null）。 */
export function operationView(record: OperationRecord): Record<string, unknown> {
  return {
    id: record.id,
    action: record.action,
    state: record.state,
    reason: record.reason,
    created_ms: record.created_ms,
    started_ms: record.started_ms,
    finished_ms: record.finished_ms,
    envelope: record.envelope,
  };
}

/** 操作表满且没有可淘汰的终态记录：503 带 Retry-After: 2（调用方据此回绝，且不消耗确认号）。 */
export function operationFull(): Response {
  const response = errorResponse(503, "操作表已满，请稍后重试");
  response.headers.set("retry-after", "2");
  return response;
}

/** 完整信封转成可 JSON 序列化的普通对象（记进操作记录；写出时七字段按次序手工拼）。 */
export function envelopeRecord(envelope: KernelEnvelope): Record<string, unknown> {
  return JSON.parse(envelopeBody(envelope)) as Record<string, unknown>;
}

/** stdout 的非空行、逐行过 redactSecrets（写命令的 output）。 */
export function outputOf(stdout: string): string[] {
  const out: string[] = [];
  for (const line of stdout.split(/\r?\n/)) {
    if (line === "") continue;
    out.push(redactSecrets(line));
  }
  return out;
}

/** 一次跑完（completed）拼成写命令的七字段信封：data 恒为 null，output 是 stdout 的非空行。 */
export function writeEnvelope(argv: readonly string[], outcome: Extract<RunOutcome, { kind: "completed" }>): KernelEnvelope {
  return {
    ok: outcome.result.exit_code === 0,
    exitCode: outcome.result.exit_code,
    data: null,
    output: outputOf(outcome.stdout),
    messages: messagesOf(outcome.stderr),
    command: displayArgv(argv),
    elapsedMs: elapsedMsOf(outcome.result.wall_seconds),
  };
}
