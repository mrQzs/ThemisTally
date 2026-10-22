// 任务页数据层自测（合同 Steps 3、D02）：五个开关下 readAttempt、readAttemptFile 与 loadAttemptDetail 的结果。
import { afterEach, describe, expect, it } from 'vitest';
import { isAttemptMissing, loadAttemptDetail, readAttempt, readAttemptFile } from '../src/pages/tasks/tasks-data';

afterEach(() => {
  window.location.hash = '';
});

function at(mock: string) {
  window.location.hash = `#/tasks?mock=${mock}`;
}

describe('data 开关', () => {
  it('data：api.ts 有的原样返回，command 沿用 api.ts，每次都深拷贝', async () => {
    at('data');
    const first = await readAttempt('logs-cat', 'attempt-002');
    expect(first.ok).toBe(true);
    expect(first.command).toEqual(['logs', 'show', 'logs-cat/attempt-002']);
    expect(first.data?.state).toBe('NEEDS_REVIEW');
    first.data!.state = '已改坏';
    const second = await readAttempt('logs-cat', 'attempt-002');
    expect(second.data?.state, '每次都深拷贝').toBe('NEEDS_REVIEW');
    const report = await readAttemptFile('logs-cat', 'attempt-002', 'executor-report.md');
    expect(report.ok).toBe(true);
    expect(report.command).toEqual(['logs', 'cat', 'logs-cat/attempt-002', 'executor-report.md']);
    expect(report.data && 'text' in report.data ? report.data.text : '').toContain('执行报告');
  });

  it('loading：api.ts 永不兑现，包装也一直等着', async () => {
    at('loading');
    let done = 0;
    void readAttempt('logs-cat', 'attempt-002').then(() => { done += 1; }, () => { done += 1; });
    void readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch').then(() => { done += 1; }, () => { done += 1; });
    await new Promise((r) => setTimeout(r, 30));
    expect(done, 'loading 下一直挂起').toBe(0);
  });

  it('error：返回内核报错原文，不被本片夹具盖住', async () => {
    at('error');
    const a = await readAttempt('logs-cat', 'attempt-002');
    expect(a.ok).toBe(false);
    expect(a.command).toEqual(['logs', 'show', 'logs-cat/attempt-002']);
    expect(a.messages.join('')).toContain('Permission denied');
    const b = await readAttempt('ui-readonly-api', 'attempt-001');
    expect(b.ok, 'error 开关不去取夹具').toBe(false);
    expect(b.messages.join('')).toContain('Permission denied');
    const c = await readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch');
    expect(c.ok).toBe(false);
    expect(c.messages.join('')).toContain('Permission denied');
  });

  it('offline 与 empty：api.ts 有的照常返回', async () => {
    at('offline');
    const a = await readAttempt('logs-cat', 'attempt-002');
    expect(a.ok, 'offline 同 data').toBe(true);
    at('empty');
    const b = await readAttempt('logs-cat', 'attempt-002');
    expect(b.ok, 'empty 时 logs show 照常').toBe(true);
  });
});

describe('loadAttemptDetail', () => {
  it('并行读 getStatus 与 readAttempt；row 与 attemptEnv 都在', async () => {
    at('data');
    const d = await loadAttemptDetail('logs-cat', 'attempt-002');
    expect(d.ok).toBe(true);
    expect(d.data?.task).toBe('logs-cat');
    expect(d.data?.attempt).toBe('attempt-002');
    expect(d.data?.row?.state).toBe('NEEDS_REVIEW');
    expect(d.data?.attemptEnv.ok).toBe(true);
    expect(isAttemptMissing(d.data!)).toBe(false);
  });

  it('找不到：getStatus 没失败就还是 ok 信封，row 为 null 且 attemptEnv 不 ok', async () => {
    at('data');
    const miss = await loadAttemptDetail('x', 'y');
    expect(miss.ok).toBe(true);
    expect(miss.data?.row).toBeNull();
    expect(miss.data?.attemptEnv.ok).toBe(false);
    expect(isAttemptMissing(miss.data!)).toBe(true);
  });

  it('getStatus 失败时返回它的信封', async () => {
    at('error');
    const e = await loadAttemptDetail('logs-cat', 'attempt-002');
    expect(e.ok).toBe(false);
    expect(e.command).toEqual(['status']);
  });
});

describe('本片夹具兜底', () => {
  it('api.ts 报缺时才取夹具：运行中的 attempt、补丁、检查日志、事件第 2 页', async () => {
    at('data');
    const live = await readAttempt('ui-readonly-api', 'attempt-001');
    expect(live.ok, '夹具里有这个 attempt').toBe(true);
    expect(live.command).toEqual(['logs', 'show', 'ui-readonly-api/attempt-001']);
    expect(live.data?.state).toBe('RUNNING');
    expect(live.data?.summary).toBeNull();
    const patch = await readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch');
    expect(patch.ok, '补丁在本片夹具里').toBe(true);
    expect(patch.data && 'text' in patch.data ? patch.data.text : '').toContain('diff --git');
    const log = await readAttemptFile('logs-cat', 'attempt-002', 'checks/01/V01.log');
    expect(log.ok, '检查日志在本片夹具里').toBe(true);
    const page2 = await readAttemptFile('logs-cat', 'attempt-002', 'events.jsonl', 'c1-0001a2f3');
    expect(page2.ok, '事件第 2 页按游标取自本片夹具').toBe(true);
    expect(page2.data?.mode).toBe('jsonl');
    expect(Array.isArray(page2.data && 'lines' in page2.data ? page2.data.lines : null)).toBe(true);
    const liveEvents = await readAttemptFile('ui-readonly-api', 'attempt-001', 'events.jsonl');
    expect(liveEvents.ok, '运行中 attempt 的事件第 1 页在本片夹具里').toBe(true);
    const missing = await readAttemptFile('logs-cat', 'attempt-002', 'no-such.file');
    expect(missing.ok, '夹具里也没有的返回 api.ts 的原信封').toBe(false);
    expect(missing.messages.join('')).toContain('夹具里没有这份数据');
  });

  it('offline 与 empty 下照样取本片夹具', async () => {
    at('offline');
    const a = await readAttempt('ui-readonly-api', 'attempt-001');
    expect(a.ok, 'offline 下照样取夹具').toBe(true);
    at('empty');
    const c = await readAttempt('ui-readonly-api', 'attempt-001');
    expect(c.ok, 'empty 下包装照样处理夹具').toBe(true);
  });

  it('补丁夹具：一个改动文件带两个片段、一个新文件、一个二进制新文件', async () => {
    at('data');
    const patch = await readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch');
    const text = patch.data && 'text' in patch.data ? patch.data.text : '';
    expect(text).toContain('diff --git a/src/pages/tasks/tasks-route.ts');
    expect(text.match(/^@@ /gm)?.length).toBeGreaterThanOrEqual(3);
    expect(text).toContain('new file mode 100644');
    expect(text).toContain('Binary files');
    expect(text).toContain('<script>alert(1)</script>');
  });
});
