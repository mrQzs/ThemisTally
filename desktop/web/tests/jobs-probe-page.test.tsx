// 运行时表行内 [探测] 端到端（T055 合同第 10 步）：真实模式注入假服务，断言创建正文、每秒查询、进度条
// aria-label、成功的结果块、ok 为假的 failed（结果块照旧 + 点明没过的那一项）、没有 data 的 failed、
// 取消与超时（150 秒）、关掉再开同一个作业；桩模式覆盖 loading 与 error 两个开关。
// 等轮询用真实计时器 sleep；测真实组件，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const JOB_ID = 'probe-page-job-00000000000000000000';

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
    id: JOB_ID, kind: 'runtime-probe', state, reason: null,
    created_ms: 1, started_ms: state === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope,
  };
}
function probeEnv(data: any): any {
  return { ok: data && data.ok, exit_code: data && data.ok ? 0 : 1, data, output: [], messages: data && data.ok ? [] : ['ERROR: 探测示意'], command: [], elapsed_ms: 1 };
}
const PI_OK = {
  runtime: 'pi', adapter: 'pi', source: 'local', command: ['node', 'pi.js'], version_exit_code: 0, version: '3.9.4',
  help: { exit_code: 0, missing_flags: [], thinking_levels: ['off', 'low', 'high'] }, ok: true,
};
const PI_BAD = {
  runtime: 'pi', adapter: 'pi', source: 'local', command: null, version_exit_code: 1, version: '',
  help: { exit_code: 1, missing_flags: ['--no-context-files'], thinking_levels: [] }, ok: false,
};

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let jobState = 'running';
let jobEnvelope: any = null;
let createStatus = 201;
const creates: any[] = [];
const cancels: any[] = [];
const queries: string[] = [];

const fake: LiveClient = {
  get(): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(): Promise<any> { return Promise.resolve({ status: 200, body: errEnv('不该调写路由') }); },
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
      if (createStatus !== 201) return Promise.resolve({ status: createStatus, body: errEnv('ERROR 不支持这个作业') });
      return Promise.resolve({ status: 201, body: jobView('queued', null) });
    }
    if (path.indexOf('/api/v1/jobs/') === 0 && path.endsWith('/cancel')) {
      cancels.push(body);
      jobState = 'cancelled';
      return Promise.resolve({ status: 200, body: jobView('cancelled', null) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  jobState = 'running';
  jobEnvelope = null;
  createStatus = 201;
  creates.length = 0;
  cancels.length = 0;
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

async function openProbe(id: string): Promise<ReturnType<typeof render>> {
  const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
  fireEvent.click(btnInRow(r.container, id, '探测'));
  await flush();
  return r;
}

describe('RuntimesView 的 [探测]（真实模式）', () => {
  it('(a) 点 [探测]：创建正文恰 {"kind":"runtime-probe","runtime":"pi"}；标题「探测 pi」；进度与每秒查询', async () => {
    const r = await openProbe('pi');
    const entry = btnInRow(r.container, 'pi', '探测');
    expect(entry.getAttribute('data-variant'), '入口 ghost').toBe('ghost');
    expect(entry.getAttribute('data-size'), '入口 sm').toBe('sm');
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('探测 pi');
    expect(creates.length, '只发一次创建').toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    expect(Object.keys(creates[0]).length).toBe(2);
    const bar = qa(d, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('探测进行中');
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(d, '重新探测').disabled, '运行中重新探测禁用').toBe(true);
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/' + JOB_ID), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(b) 成功：版本、命令来源、命令；pi 的缺少的参数（无）与思考级别', async () => {
    jobState = 'succeeded';
    jobEnvelope = probeEnv(PI_OK);
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t, '版本').toContain('3.9.4');
    expect(t, '命令来源').toContain('本机文件');
    expect(t, '命令').toContain('node pi.js');
    expect(t, 'pi 的缺少的参数').toContain('缺少的参数');
    expect(t, '没有缺少的参数写无').toContain('无');
    expect(t, '思考级别').toContain('思考级别');
    expect(t, '思考级别用、连').toContain('low、high');
    expect(qa(needDlg(), '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
  }, 20000);

  it('(c) ok 为假的 failed：结果块照旧（版本未知）并点明没过的项，且在内核原文之前', async () => {
    jobState = 'failed';
    jobEnvelope = probeEnv(PI_BAD);
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    const t = text(d);
    expect(t, '失败标题').toContain('探测失败');
    expect(t, '结果块照旧：空版本写版本未知').toContain('版本未知');
    expect(t, '命令是 null 写 —').toContain('—');
    expect(t, '点明版本命令退出码').toContain('版本命令退出码 1');
    expect(t, '点明 --help 退出码').toContain('pi --help 退出码 1');
    expect(t, '点明缺少的参数').toContain('pi 缺少参数：--no-context-files');
    expect(t.indexOf('版本命令退出码 1'), '没过项在内核原文之前').toBeLessThan(t.indexOf('ERROR: 探测示意'));
    expect(t, '内核原文照显示').toContain('ERROR: 探测示意');
    expect(btnIn(d, '重新探测').disabled, '终态后重新探测可点').toBe(false);
  }, 20000);

  it('(d) 没有 data 的 failed：只显示内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    jobEnvelope = errEnv('ERROR: 内核报错（探测示意）');
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t, '内核原文照显示').toContain('ERROR: 内核报错（探测示意）');
    expect(t, '没有结果块：不写版本未知').not.toContain('版本未知');
    expect(t, '没有没过项').not.toContain('版本命令退出码');
    expect(t, '没有结果块行标签').not.toContain('命令来源');
  }, 20000);

  it('(e) 取消：正文恰 {}，随后「已取消」', async () => {
    await openProbe('pi');
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(needDlg()), '取消后落已取消').toContain('已取消');
    expect(qa(needDlg(), '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
  }, 20000);

  it('(f) timed_out：超时（超过 150 秒），已停止；重新探测可点，点了发第二次创建', async () => {
    jobState = 'timed_out';
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    expect(text(needDlg())).toContain('超时（超过 150 秒），已停止');
    jobState = 'running';
    fireEvent.click(btnIn(needDlg(), '重新探测'));
    await flush();
    expect(creates.length, '重新探测发新创建').toBe(2);
    expect(creates[1]).toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    expect(qa(needDlg(), '[role="progressbar"]').length, '新作业在跑').toBeGreaterThanOrEqual(1);
  }, 20000);

  it('(g) 创建失败 400：显示报错原文与探测失败；重新探测可点并重发', async () => {
    createStatus = 400;
    await openProbe('pi');
    await act(async () => { await sleep(300); });
    const d = needDlg();
    expect(text(d), '创建失败的报错原文').toContain('ERROR 不支持这个作业');
    expect(text(d), '失败标题').toContain('探测失败');
    expect(btnIn(d, '重新探测').disabled, '创建失败后重新探测可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(d, '重新探测'));
    await flush();
    expect(creates.length, '重发创建').toBe(2);
  }, 20000);

  it('(h) 关掉再开：同一个作业、不再发创建请求；关着时 DOM 里没有作业卡', async () => {
    const r = await openProbe('pi');
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg(), '关掉后对话框不在').toBeNull();
    expect(document.querySelector('[role="progressbar"]'), 'DOM 里没有作业卡').toBeNull();
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    expect(creates.length, '再开不再创建').toBe(1);
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);
});

describe('RuntimesView 的 [探测]（桩模式）', () => {
  it('(i-loading) loading：一直 running，[取消] 落「已取消」', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=loading';
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    await act(async () => { await sleep(2200); });
    const d = needDlg();
    expect(qa(d, '[role="progressbar"]').length, 'loading 一直 running').toBeGreaterThanOrEqual(1);
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    await act(async () => { await sleep(1300); });
    expect(text(needDlg()), '取消后落已取消').toContain('已取消');
  }, 20000);

  it('(j-error) error：第一次查询就落 failed，显示「探测失败」与示意原文，不显示结果块', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=error';
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t, '落 failed').toContain('探测失败');
    expect(t, '示意原文').toContain('ERROR 探测失败：内核报错（示意）');
    expect(t, '没有 data：不写版本未知').not.toContain('版本未知');
    expect(t, '没有结果块行标签').not.toContain('命令来源');
  }, 20000);
});
