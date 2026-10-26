// 执行响应 → 显示状态与原因标签（第四节）：纯函数，供 useWriteFlow 的状态机调用。
// WARN 行的认法照 ts/packages/ui/src/kernelenvelope.ts 的 MESSAGE_PREFIXES：output 或 messages 里以 WARN 开头的行
// （role set、preset use 的 WARN 打在 stdout 上，所以 output 也要扫）。
import type { Envelope, OperationView } from '../api';

export type WriteClass =
  | { kind: 'success' }
  | { kind: 'successWarn' }
  | { kind: 'failedExit'; reason: string }
  | { kind: 'stale' }
  | { kind: 'expired' }
  | { kind: 'timeout'; reason: string }
  | { kind: 'serverError'; reason: string }
  | { kind: 'busy' }
  | { kind: 'rejected'; reason: string }
  | { kind: 'checkOperation' }
  | { kind: 'threw' };

export type FinalState =
  | { phase: 'done' }
  | { phase: 'doneWithWarning'; warnings: string[] }
  | { phase: 'failed'; error: string; reason: string | null }
  | { phase: 'partiallyWritten'; error: string; reason: string | null }
  | { phase: 'unknown' }
  | { phase: 'rereadFailed'; warnings: string[] };

/** output 或 messages 里以 WARN 开头的行（保持出现次序，output 在前）。 */
export function warnLines(envelope: Envelope<unknown> | null | undefined): string[] {
  if (!envelope) return [];
  return [...(envelope.output ?? []), ...(envelope.messages ?? [])].filter((line) => line.startsWith('WARN'));
}

/** 内核报错原文（纯文本）：优先 messages 里的行，否则 output，再否则占位。 */
export function errorText(envelope: Envelope<unknown> | null | undefined): string {
  const msgs = envelope?.messages ?? [];
  if (msgs.length > 0) return msgs.join('\n');
  const out = envelope?.output ?? [];
  if (out.length > 0) return out.join('\n');
  return '（内核没有给出报错原文）';
}

function exitReason(exitCode: number): string {
  if (exitCode === 1 || exitCode === 3) return '内核拒绝';
  if (exitCode === 2) return '用法错误';
  return `失败（退出 ${exitCode}）`;
}

/** 一次执行响应（状态码 + 信封）归成哪一类（第四节的映射表，写请求已兑现时用）。 */
export function classifyWrite(status: number, body: Envelope<null>): WriteClass {
  if (status === 409) return body.exit_code === 4 ? { kind: 'stale' } : { kind: 'expired' };
  if (status === 503) return { kind: 'busy' };
  if (status === 400 || status === 401 || status === 403 || status === 413) return { kind: 'rejected', reason: '请求被拒' };
  if (status === 504) return { kind: 'timeout', reason: '超时' };
  if (status === 500) return { kind: 'serverError', reason: '服务出错' };
  if (status === 200) {
    if (body.ok) return warnLines(body).length > 0 ? { kind: 'successWarn' } : { kind: 'success' };
    return { kind: 'failedExit', reason: exitReason(body.exit_code ?? 0) };
  }
  return { kind: 'checkOperation' };
}

/** getOperation 查到的终态按信封归成哪一类（succeeded→200 ok、failed/exit→按退出码、stale→状态已变、timed_out→504、其余 failed→服务出错）。 */
export function classifyTerminal(op: OperationView): WriteClass {
  switch (op.state) {
    case 'succeeded':
      return warnLines(op.envelope).length > 0 ? { kind: 'successWarn' } : { kind: 'success' };
    case 'failed':
      if (op.reason === 'exit') return { kind: 'failedExit', reason: exitReason(op.envelope?.exit_code ?? 0) };
      return { kind: 'serverError', reason: '服务出错' };
    case 'stale':
      return { kind: 'stale' };
    case 'timed_out':
      return { kind: 'timeout', reason: '超时' };
    default:
      return { kind: 'checkOperation' };
  }
}

export function reasonOf(cls: WriteClass): string | null {
  if (cls.kind === 'failedExit' || cls.kind === 'timeout' || cls.kind === 'serverError' || cls.kind === 'rejected') {
    return cls.reason;
  }
  return null;
}

/** 重读之后定终态：成功类看重读成不成；失败类看快照变没变（退出非 0 且快照不同→已部分写入，相同→失败，重读失败→结果未知）。 */
export function finalFromReread(
  cls: WriteClass,
  rereadOk: boolean,
  snapshotChanged: boolean,
  envelope: Envelope<null> | null,
): FinalState {
  if (cls.kind === 'success') {
    return rereadOk ? { phase: 'done' } : { phase: 'rereadFailed', warnings: [] };
  }
  if (cls.kind === 'successWarn') {
    const warnings = warnLines(envelope);
    return rereadOk ? { phase: 'doneWithWarning', warnings } : { phase: 'rereadFailed', warnings };
  }
  if (!rereadOk) return { phase: 'unknown' };
  const error = errorText(envelope);
  const reason = reasonOf(cls);
  return snapshotChanged ? { phase: 'partiallyWritten', error, reason } : { phase: 'failed', error, reason };
}
