// 运行时表行内 [模型] 端到端（T055 合同第 10 步）：真实模式注入假服务，断言创建正文、三列结果表与
// 「是 / 否 / 不限制」、表上方说明句、空数组、超时（120 秒）、同类互斥（别的行禁用并悬停写明正在忙谁）、
// 本行重开不再创建、结束后别的行能重新开。等轮询用真实计时器 sleep；测真实组件，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const JOB_ID = 'models-page-job-000000000000000000000';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function rowOf(root: any, id: string): any {
  return qa(root, 'tbody tr').find((tr: any) => text(tr.querySelector('td')) === id);
}
function btnInRow(root: any, id: string, label: string): HTMLButtonElement {
  const row = rowOf(root, id);
  expect(row, '应有行 ' + id).toBeTruthy();
  return btnIn(row, label);
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function errEnv(message: string): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function jobView(state: string, envelope: any): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID, kind: 'models', state, reason: null,
    created_ms: 1, started_ms: state === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope,
  };
}
function modelsEnv(models: any[]): any {
  return { ok: true, exit_code: 0, data: { runtime: 'pi', models, allowed_executors_set: true }, output: [], messages: [], command: [], elapsed_ms: 1 };
}
const FOUR = [
  { provider: 'stepfun', model: 'step-5-preview', allowed: true },
  { provider: 'deepseek', model: 'deepseek-chat', allowed: false },
  { provider: 'anthropic', model: 'claude-x', allowed: null },
  { provider: '<redacted>', model: '<redacted>', allowed: true },
];

// 两个 pi 行（adapter 都是 pi）：同类互斥要能在一个页面上看到「忙于别的行」。
const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'pi-alt', adapter: 'pi', source: 'env', command: ['pi-alt'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let jobState = 'running';
let jobEnvelope: any = null;
const creates: any[] = [];
const queries: string[] = [];

const fake: LiveClient = {
  get(): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0) {
      queries.push(path);
      return Promise.resolve({ status: 200, body: jobView(jobState, jobEnvelope) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      return Promise.resolve({ status: 201, body: jobView('queued', null) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  jobState = 'running';
  jobEnvelope = null;
  creates.length = 0;
  queries.length = 0;
  window.location.hash = '';
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

async function openModels(id: string): Promise<ReturnType<typeof render>> {
  const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
  fireEvent.click(btnInRow(r.container, id, '模型'));
  await flush();
  return r;
}

async function hoverTip(btn: any): Promise<string> {
  fireEvent.mouseEnter(btn.parentElement);
  await act(async () => { await sleep(700); });
  const tip = document.querySelector('[role="tooltip"]');
  return tip ? text(tip) : '';
}

describe('RuntimesView 的 [模型]（真实模式）', () => {
  it('(a) 点 [模型]：创建正文恰 {"kind":"models","runtime":"pi"}；标题「模型 pi」；进度条 aria-label 列模型进行中', async () => {
    const r = await openModels('pi');
    const entry = btnInRow(r.container, 'pi', '模型');
    expect(entry.getAttribute('data-variant'), '入口 ghost').toBe('ghost');
    expect(entry.getAttribute('data-size'), '入口 sm').toBe('sm');
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('模型 pi');
    expect(creates.length).toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'models', runtime: 'pi' });
    expect(Object.keys(creates[0]).length).toBe(2);
    const bar = qa(d, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('列模型进行中');
    await act(async () => { await sleep(1300); });
    expect(queries.every((p) => p === '/api/v1/jobs/' + JOB_ID), '查询同一个作业号').toBe(true);
    expect(qa(rowOf(r.container, 'claude-code'), 'button').map((b: any) => text(b)), 'adapter 不是 pi 的行没有 [模型]').toEqual(['探测', '删除…']);
  }, 20000);

  it('(b) 成功：说明句、三列列头与次序、是/否/不限制、<redacted> 原样', async () => {
    jobState = 'succeeded';
    jobEnvelope = modelsEnv(FOUR);
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    const t = text(d);
    expect(t, '表上方说明句').toContain('模型列表来自 pi --list-models，不调用模型');
    const table = qa(d, 'table')[0];
    expect(qa(table, 'th').map((el: any) => text(el)), '三列列头次序如此').toEqual(['provider', 'model', '是否在允许列表']);
    const rows = qa(table, 'tbody tr');
    expect(rows.length, '四行照 data.models 的次序').toBe(4);
    expect(qa(rows[0], 'td').map((c: any) => text(c))).toEqual(['stepfun', 'step-5-preview', '是']);
    expect(qa(rows[1], 'td').map((c: any) => text(c))).toEqual(['deepseek', 'deepseek-chat', '否']);
    expect(qa(rows[2], 'td').map((c: any) => text(c))).toEqual(['anthropic', 'claude-x', '不限制']);
    expect(qa(rows[3], 'td').map((c: any) => text(c)), '<redacted> 原样显示').toEqual(['<redacted>', '<redacted>', '是']);
    expect(btnIn(d, '重新列出').disabled, '终态后重新列出可点').toBe(false);
  }, 20000);

  it('(c) 空数组：说明句照旧，「没有列出模型」', async () => {
    jobState = 'succeeded';
    jobEnvelope = modelsEnv([]);
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d), '说明句照旧').toContain('模型列表来自 pi --list-models，不调用模型');
    expect(text(d), '空数组一句话').toContain('没有列出模型');
    expect(qa(d, 'table tbody tr').length, '没有模型行').toBe(0);
  }, 20000);

  it('(d) timed_out：超时（超过 120 秒），已停止；重新列出可点并重发', async () => {
    jobState = 'timed_out';
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    expect(text(needDlg())).toContain('超时（超过 120 秒），已停止');
    jobState = 'running';
    fireEvent.click(btnIn(needDlg(), '重新列出'));
    await flush();
    expect(creates.length, '重新列出发新创建').toBe(2);
    expect(creates[1]).toEqual({ kind: 'models', runtime: 'pi' });
  }, 20000);

  it('(e) 同类忙于别的行：pi-alt 的 [模型] 禁用、悬停「正在列 pi 的模型」；结束后别的行能重新开', async () => {
    const r = await openModels('pi');
    const other = btnInRow(r.container, 'pi-alt', '模型');
    expect(other.disabled, '忙于别的行时同类按钮禁用').toBe(true);
    expect(await hoverTip(other), '悬停写明正在忙谁').toBe('正在列 pi 的模型');
    expect(btnInRow(r.container, 'pi', '模型').disabled, '本行不忙').toBe(false);
    jobState = 'succeeded';
    jobEnvelope = modelsEnv(FOUR);
    await act(async () => { await sleep(1300); });
    fireEvent.click(btnInRow(r.container, 'pi-alt', '模型'));
    await flush();
    expect(creates.length, '结束后别的行能重新开').toBe(2);
    expect(creates[1]).toEqual({ kind: 'models', runtime: 'pi-alt' });
  }, 20000);

  it('(f) 关掉再开：不再创建、同一个作业照查', async () => {
    const r = await openModels('pi');
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg()).toBeNull();
    const before = queries.length;
    await act(async () => { await sleep(2200); });
    expect(queries.length, '关着时行内入口的订阅照查').toBeGreaterThan(before);
    fireEvent.click(btnInRow(r.container, 'pi', '模型'));
    await flush();
    expect(creates.length, '再开不再创建').toBe(1);
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);
});
