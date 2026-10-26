// 执行响应 → 显示状态与原因标签（合同第四节）的纯函数自测：映射表逐行、WARN 认法、原因标签、
// 重读之后定终态（退出非 0 且快照不同 → 已部分写入、相同 → 失败、重读失败 → 结果未知；退出 0 且重读失败 →
// 「命令已成功，但重新读取失败」）。这些是 D03–D05 与 M2–M4、M7、M9、M19、M21 的落点。
import { describe, expect, it } from 'vitest';
import type { Envelope, OperationView } from '../src/api';
import {
  classifyTerminal,
  classifyWrite,
  errorText,
  finalFromReread,
  warnLines,
} from '../src/writes/writeOutcome';

function env(over: Partial<Envelope<null>>): Envelope<null> {
  return {
    ok: true,
    exit_code: 0,
    data: null,
    output: [],
    messages: [],
    command: ['config', 'preset', 'use', 'economy'],
    elapsed_ms: 0,
    ...over,
  };
}

function op(over: Partial<OperationView>): OperationView {
  return {
    id: 'op1',
    action: 'preset.use',
    state: 'succeeded',
    reason: null,
    created_ms: 0,
    started_ms: 0,
    finished_ms: 0,
    envelope: null,
    ...over,
  };
}

describe('WARN 行的认法（output 与 messages 都扫）', () => {
  it('output 与 messages 里以 WARN 开头的行都算，保持 output 在前的次序', () => {
    const e = env({
      output: ['WARN stdout 上的一条', '普通输出'],
      messages: ['WARN messages 上的一条', 'ERROR 别的'],
    });
    expect(warnLines(e)).toEqual(['WARN stdout 上的一条', 'WARN messages 上的一条']);
  });

  it('只扫 messages 时会漏掉 stdout 上的 WARN（M21）', () => {
    const stdoutOnly = env({ output: ['WARN 执行端已固定，切换不影响正在运行的 attempt'] });
    expect(warnLines(stdoutOnly)).toHaveLength(1);
    expect(warnLines(env({ output: ['没有 WARN 前缀的一行'] }))).toEqual([]);
    expect(warnLines(null)).toEqual([]);
  });
});

describe('执行响应的归类（第四节的映射表）', () => {
  it('200 ok：没有 WARN 是 success，有 WARN 是 successWarn', () => {
    expect(classifyWrite(200, env({ ok: true }))).toEqual({ kind: 'success' });
    expect(classifyWrite(200, env({ ok: true, messages: ['WARN 有一条'] }))).toEqual({ kind: 'successWarn' });
    expect(classifyWrite(200, env({ ok: true, output: ['WARN 有一条'] }))).toEqual({ kind: 'successWarn' });
  });

  it('200 ok:false：退出 1 或 3 是「内核拒绝」、退出 2 是「用法错误」、其他 N 是「失败（退出 N）」', () => {
    expect(classifyWrite(200, env({ ok: false, exit_code: 1 }))).toEqual({ kind: 'failedExit', reason: '内核拒绝' });
    expect(classifyWrite(200, env({ ok: false, exit_code: 3 }))).toEqual({ kind: 'failedExit', reason: '内核拒绝' });
    expect(classifyWrite(200, env({ ok: false, exit_code: 2 }))).toEqual({ kind: 'failedExit', reason: '用法错误' });
    expect(classifyWrite(200, env({ ok: false, exit_code: 7 }))).toEqual({ kind: 'failedExit', reason: '失败（退出 7）' });
  });

  it('409 的两种：退出 4 是状态已变，exit_code 为 null 是确认已失效（M4）', () => {
    expect(classifyWrite(409, env({ ok: false, exit_code: 4 }))).toEqual({ kind: 'stale' });
    expect(classifyWrite(409, env({ ok: false, exit_code: null }))).toEqual({ kind: 'expired' });
  });

  it('服务端与拒载：503 先查操作、500 与 504 归服务出错与超时、400/401/403/413 是「请求被拒」', () => {
    expect(classifyWrite(503, env({ ok: false }))).toEqual({ kind: 'busy' });
    expect(classifyWrite(500, env({ ok: false }))).toEqual({ kind: 'serverError', reason: '服务出错' });
    expect(classifyWrite(504, env({ ok: false }))).toEqual({ kind: 'timeout', reason: '超时' });
    for (const status of [400, 401, 403, 413]) {
      expect(classifyWrite(status, env({ ok: false }))).toEqual({ kind: 'rejected', reason: '请求被拒' });
    }
  });

  it('其他状态码先查 getOperation', () => {
    expect(classifyWrite(418, env({ ok: false }))).toEqual({ kind: 'checkOperation' });
  });
});

describe('getOperation 查到的终态', () => {
  it('succeeded 照 200 ok 处理（有 WARN 时也算）', () => {
    expect(classifyTerminal(op({ state: 'succeeded' }))).toEqual({ kind: 'success' });
    expect(classifyTerminal(op({ state: 'succeeded', envelope: env({ messages: ['WARN x'] }) }))).toEqual({
      kind: 'successWarn',
    });
  });

  it('failed/exit 照信封的退出码分；stale 是状态已变；timed_out 是超时', () => {
    expect(classifyTerminal(op({ state: 'failed', reason: 'exit', envelope: env({ ok: false, exit_code: 1 }) }))).toEqual({
      kind: 'failedExit',
      reason: '内核拒绝',
    });
    expect(classifyTerminal(op({ state: 'failed', reason: 'exit', envelope: env({ ok: false, exit_code: 2 }) }))).toEqual({
      kind: 'failedExit',
      reason: '用法错误',
    });
    expect(classifyTerminal(op({ state: 'stale' }))).toEqual({ kind: 'stale' });
    expect(classifyTerminal(op({ state: 'timed_out' }))).toEqual({ kind: 'timeout', reason: '超时' });
  });

  it('failed/closing、spawn-error、output-too-large 都当服务出错', () => {
    for (const reason of ['closing', 'spawn-error', 'output-too-large']) {
      expect(classifyTerminal(op({ state: 'failed', reason }))).toEqual({ kind: 'serverError', reason: '服务出错' });
    }
  });
});

describe('重读之后定终态（D05：部分写入的判定）', () => {
  const failExit = { kind: 'failedExit', reason: '内核拒绝' } as const;

  it('退出非 0：快照不同 → 已部分写入，相同 → 失败，重读失败 → 结果未知（M2/M3/M19）', () => {
    expect(finalFromReread(failExit, true, true, env({ ok: false, exit_code: 1, messages: ['ERROR 内核拒绝'] }))).toEqual({
      phase: 'partiallyWritten',
      error: 'ERROR 内核拒绝',
      reason: '内核拒绝',
    });
    expect(finalFromReread(failExit, true, false, env({ ok: false, exit_code: 1, messages: ['ERROR 内核拒绝'] }))).toEqual({
      phase: 'failed',
      error: 'ERROR 内核拒绝',
      reason: '内核拒绝',
    });
    expect(finalFromReread(failExit, false, false, env({ ok: false, exit_code: 1 }))).toEqual({ phase: 'unknown' });
  });

  it('超时与服务出错也按快照分（M7：500 不重读就判失败是错的）', () => {
    for (const cls of [
      { kind: 'timeout', reason: '超时' } as const,
      { kind: 'serverError', reason: '服务出错' } as const,
    ]) {
      expect(finalFromReread(cls, true, true, env({ ok: false, exit_code: null, messages: ['ERROR x'] }))).toEqual({
        phase: 'partiallyWritten',
        error: 'ERROR x',
        reason: cls.reason,
      });
      expect(finalFromReread(cls, true, false, env({ ok: false, exit_code: null }))).toEqual({
        phase: 'failed',
        error: '（内核没有给出报错原文）',
        reason: cls.reason,
      });
    }
  });

  it('退出 0：重读成功 → 完成；重读失败 → 「命令已成功，但重新读取失败」，WARN 行也列出（M9/M17）', () => {
    expect(finalFromReread({ kind: 'success' }, true, true, null)).toEqual({ phase: 'done' });
    expect(finalFromReread({ kind: 'success' }, false, false, null)).toEqual({ phase: 'rereadFailed', warnings: [] });
    const warnEnv = env({ ok: true, messages: ['WARN 有一条'], output: ['WARN stdout 上有一条'] });
    expect(finalFromReread({ kind: 'successWarn' }, true, true, warnEnv)).toEqual({
      phase: 'doneWithWarning',
      warnings: ['WARN stdout 上有一条', 'WARN 有一条'],
    });
    expect(finalFromReread({ kind: 'successWarn' }, false, false, warnEnv)).toEqual({
      phase: 'rereadFailed',
      warnings: ['WARN stdout 上有一条', 'WARN 有一条'],
    });
  });
});

describe('报错原文按纯文本给出', () => {
  it('优先 messages，其次 output，再否则占位；<b>x</b> 原样留在文字里', () => {
    expect(errorText(env({ messages: ['ERROR a <b>x</b>'], output: ['OUT <b>y</b>'] }))).toBe('ERROR a <b>x</b>');
    expect(errorText(env({ messages: [], output: ['OUT <b>y</b>'] }))).toBe('OUT <b>y</b>');
    expect(errorText(env({ messages: [], output: [] }))).toBe('（内核没有给出报错原文）');
  });
});

describe('预览自己的失败（不重读）', () => {
  // 状态机把这些响应显示成「预览失败」加 [重新预览] [关闭]，重读根本不发生；预览阶段的快照读取失败时
  // 同一状态机的提示是「读取当前状态失败」。这里断言归类本身：它们都不是 success 类。
  it('200 ok:false 退出 2 归「用法错误」；500/504 归服务出错与超时', () => {
    expect(classifyWrite(200, env({ ok: false, exit_code: 2, messages: ['ERROR 预览不合格'] }))).toEqual({
      kind: 'failedExit',
      reason: '用法错误',
    });
    expect(classifyWrite(500, env({ ok: false, exit_code: null }))).toEqual({ kind: 'serverError', reason: '服务出错' });
    expect(classifyWrite(504, env({ ok: false, exit_code: null }))).toEqual({ kind: 'timeout', reason: '超时' });
  });
});
