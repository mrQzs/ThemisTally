// 就绪检查一节端到端（T056 合同第 9 步）：真实模式注入假服务，断言创建正文、每秒查询、进度、汇总与就绪卡、
// 有 data 的 failed、没有 data 的 failed、取消与超时 600、卸载再挂载、结束后再点、取消后再点新作业的 [取消]；
// 桩模式覆盖 loading 与 error 两个开关。等轮询用真实计时器 sleep；测真实组件，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

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
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return text(id ? document.getElementById(id) : null) === title;
  });
}
function readySection(root: any): any {
  const sec = sectionNamed(root, '就绪检查');
  expect(sec, '应有「就绪检查」一节').toBeTruthy();
  return sec;
}
function valuesOf(root: any, label: string): string[] {
  return qa(root, 'dt').filter((el: any) => text(el) === label).map((el: any) => {
    const dd = el.parentElement ? el.parentElement.querySelector('dd') : null;
    return dd ? text(dd) : '';
  });
}
function errEnv(message: string): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}
function doctorEnv(data: any, ok: boolean): any {
  return { ok, exit_code: ok ? 0 : 1, data, output: [], messages: [], command: ['config', 'doctor', '--json'], elapsed_ms: 1 };
}

// 四个角色照 mock/roles.json：三个非无头角色只有一行 text；执行端是无头行（带八个键值行的字段）。
const PLANNING = { role: 'planning_review', mode: 'interactive_host', problems: [], text: 'interactive_host · claude-code（交互宿主的模型不由 Themis 切换）', ready: true };
const CONTRACT_MANUAL = { role: 'contract', mode: 'manual', problems: [], text: 'manual', ready: true };
const SCHEDULER = { role: 'scheduler_agent', mode: 'disabled', problems: [], text: 'disabled', ready: true };
const HEAD_OK = { role: 'execution', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: ['说明一行（示意）'], allowed: null, credentials: { STEP_API_KEY: true }, ready: true, command: ['node', 'pi.js'], source: 'local', version: '0.1.2', model_listed: true, auth_ready: true, thinking_supported: true };
const HEAD_BAD = { ...HEAD_OK, problems: ['凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY'], credentials: { STEP_API_KEY: false }, ready: false, notes: [] };
const HEAD_MISSING = { role: 'contract', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: [], allowed: null, credentials: {}, ready: true };
const HEAD_REJECT = { role: 'execution', mode: 'headless', problems: ['思考级别 high 不受本机 pi 支持'], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: false, notes: [], allowed: true, credentials: { STEP_API_KEY: false, OTHER_TOKEN: true }, ready: false, command: ['pi'], source: 'path', version: '9.9.9', model_listed: false, auth_ready: false, thinking_supported: false };
const ALL_READY = { ready: true, roles: [PLANNING, CONTRACT_MANUAL, HEAD_OK, SCHEDULER] };
const EXEC_NOT_READY = { ready: false, roles: [PLANNING, CONTRACT_MANUAL, HEAD_BAD, SCHEDULER] };
const PARTIAL = { ready: false, roles: [PLANNING, HEAD_MISSING, HEAD_REJECT, SCHEDULER] };

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let seq = 0;
let jobState = 'running';
let jobEnvelope: any = null;
let createStatus = 201;
const creates: any[] = [];
const cancels: any[] = [];
const queries: string[] = [];

function viewFor(id: string): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(jobState) >= 0;
  return {
    id, kind: 'doctor', state: jobState, reason: null,
    created_ms: 1, started_ms: jobState === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope: jobEnvelope,
  };
}

const fake: LiveClient = {
  get(): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0 && path.indexOf('/cancel') < 0) {
      queries.push(path);
      const id = path.slice('/api/v1/jobs/'.length);
      return Promise.resolve({ status: 200, body: viewFor(id) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      if (createStatus !== 201) return Promise.resolve({ status: createStatus, body: errEnv('ERROR 不支持这个作业') });
      seq += 1;
      return Promise.resolve({ status: 201, body: { id: 'job-doctor-' + seq, kind: 'doctor', state: 'queued', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
    }
    if (path.indexOf('/api/v1/jobs/') === 0 && path.endsWith('/cancel')) {
      cancels.push(body);
      jobState = 'cancelled';
      const id = path.slice('/api/v1/jobs/'.length, path.length - '/cancel'.length);
      return Promise.resolve({ status: 200, body: viewFor(id) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  seq = 0;
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

function mountReady(): ReturnType<typeof render> {
  return render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
}

describe('就绪检查（真实模式）', () => {
  it('(a) 点 [运行就绪检查]：创建正文恰 {"kind":"doctor"}、每秒查同一个作业号；进度与 [取消] 与离开页那句、运行中按钮禁用', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const b = btnIn(sec, '运行就绪检查');
    expect(b.disabled, '还没跑过时按钮可点').toBe(false);
    expect(b.getAttribute('data-variant')).toBe('secondary');
    expect(b.getAttribute('data-size')).toBe('md');
    expect(b.querySelector('svg'), 'PlayIcon').not.toBeNull();
    fireEvent.click(b);
    await flush();
    expect(creates.length, '只发一次创建').toBe(1);
    expect(creates[0], '创建正文恰一个键').toEqual({ kind: 'doctor' });
    expect(Object.keys(creates[0]).length).toBe(1);
    const again = btnIn(sec, '运行就绪检查');
    expect(again.textContent, '运行中只禁用不换字').toBe('运行就绪检查');
    expect(again.disabled, '运行中按钮禁用').toBe(true);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label')).toBe('就绪检查进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(text(sec), '运行中那句提示').toContain('离开这个页面作业也会继续，回来时显示结果。');
    expect(btnIn(sec, '取消'), '有 [取消]').toBeTruthy();
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/job-doctor-1'), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(b) succeeded：汇总全部就绪；就绪卡八个键值行与凭据可用/允许列表不限制/思考档位、说明行；其他角色各一行', async () => {
    jobState = 'succeeded';
    jobEnvelope = doctorEnv(ALL_READY, true);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总').toContain('全部就绪');
    expect(t, '卡头 ✓ 就绪').toContain('✓ 就绪');
    expect(t, '卡头有角色中文名').toContain('执行端');
    expect(t, '卡头有 profile').toContain('profile step-high');
    expect(valuesOf(sec, '命令')).toEqual(['node pi.js（来源：本机文件）']);
    expect(valuesOf(sec, '版本')).toEqual(['0.1.2']);
    expect(valuesOf(sec, '模型在列表中')).toEqual(['是']);
    expect(valuesOf(sec, '登录')).toEqual(['是']);
    expect(valuesOf(sec, '思考级别')).toEqual(['high（本机 pi 接受这个档位）']);
    expect(valuesOf(sec, '允许列表')).toEqual(['不限制']);
    expect(valuesOf(sec, '凭据')).toEqual(['STEP_API_KEY 可用']);
    expect(valuesOf(sec, '接通状态')).toEqual(['已接通']);
    expect(t, '说明行').toContain('说明一行（示意）');
    expect(t, 'problems 为空不渲染问题列表').not.toContain('凭据变量不可用');
    expect(t, '其他角色一行：规划审核端').toContain('✓ 规划审核端');
    expect(t).toContain('interactive_host · claude-code（交互宿主的模型不由 Themis 切换）');
    expect(t, '其他角色一行：合同端').toContain('✓ 合同端');
    expect(t, '合同端的内核行').toContain('manual');
    expect(t, '其他角色一行：调度代理').toContain('✓ 调度代理');
    expect(t, '调度代理的内核行').toContain('disabled');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(sec, '运行就绪检查').disabled, '结束后按钮可点').toBe(false);
  }, 20000);

  it('(c) failed 带 data：照样显示结果块，汇总有未就绪的角色（1 个），问题列表与凭据不可用在，不显示就绪检查失败', async () => {
    jobState = 'failed';
    jobEnvelope = doctorEnv(EXEC_NOT_READY, false);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总带个数').toContain('有未就绪的角色（1 个）');
    expect(t, '卡头 ✗ 未就绪').toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('就绪检查失败');
    expect(t, '不显示内核报错').not.toContain('内核报错');
    expect(qa(sec, '[role="progressbar"]').length).toBe(0);
    expect(btnIn(sec, '运行就绪检查').disabled, '终态后按钮可点').toBe(false);
  }, 20000);

  it('(d) 无头行缺键写「—」；凭据为空写「无」；思考不支持写不接受这个档位；允许列表真写「是」；两个凭据变量用「、」连', async () => {
    jobState = 'failed';
    jobEnvelope = doctorEnv(PARTIAL, false);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总按未就绪的个数').toContain('有未就绪的角色（1 个）');
    expect(valuesOf(sec, '命令'), '缺键写「—」').toContain('—');
    expect(valuesOf(sec, '命令'), '在列表的那行照常带来源').toContain('pi（来源：PATH）');
    expect(valuesOf(sec, '版本')).toContain('—');
    expect(valuesOf(sec, '版本')).toContain('9.9.9');
    expect(valuesOf(sec, '模型在列表中')).toContain('—');
    expect(valuesOf(sec, '模型在列表中')).toContain('否');
    expect(valuesOf(sec, '登录')).toContain('—');
    expect(valuesOf(sec, '登录')).toContain('否');
    expect(valuesOf(sec, '思考级别')).toContain('—');
    expect(valuesOf(sec, '思考级别'), '不接受这个档位').toContain('high（本机 pi 不接受这个档位）');
    expect(valuesOf(sec, '允许列表')).toContain('不限制');
    expect(valuesOf(sec, '允许列表'), '真写「是」').toContain('是');
    expect(valuesOf(sec, '凭据'), '空写「无」').toContain('无');
    expect(valuesOf(sec, '凭据'), '两个变量用「、」连').toContain('STEP_API_KEY 不可用、OTHER_TOKEN 可用');
    expect(valuesOf(sec, '接通状态')).toContain('已接通');
    expect(valuesOf(sec, '接通状态')).toContain('未接通');
    expect(t, '两行卡头：✓ 与 ✗').toContain('✓ 就绪');
    expect(t).toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('思考级别 high 不受本机 pi 支持');
  }, 20000);

  it('(e) failed 没有 data：显示就绪检查失败与内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    jobEnvelope = errEnv('ERROR: 就绪检查示意');
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(readySection(r.container));
    expect(t, '失败标题').toContain('就绪检查失败');
    expect(t, '内核原文照显示').toContain('ERROR: 就绪检查示意');
    expect(t, '没有汇总').not.toContain('全部就绪');
    expect(t, '没有结果块').not.toContain('有未就绪的角色');
    expect(t, '没有就绪卡').not.toContain('profile ');
  }, 20000);

  it('(f) 已取消显示「已取消」；结束后再点是新作业，超时显示「超时（超过 600 秒），已停止」', async () => {
    jobState = 'cancelled';
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'timed_out';
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '结束后再点是新作业').toBe(2);
    await act(async () => { await sleep(1300); });
    expect(text(sec), '超时 600').toContain('超时（超过 600 秒），已停止');
  }, 20000);

  it('(g) 卸载再挂载看到同一个作业、不再发创建请求；跑完显示结果；结束后再点发新的创建请求', async () => {
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    cleanup();
    const r2 = mountReady();
    const sec2 = readySection(r2.container);
    expect(creates.length, '重挂载不再创建').toBe(1);
    expect(qa(sec2, '[role="progressbar"]').length, '回来还是同一个作业（在跑）').toBeGreaterThanOrEqual(1);
    const q = queries.length;
    await act(async () => { await sleep(1300); });
    expect(queries.length, '回来后照查').toBeGreaterThan(q);
    jobState = 'succeeded';
    jobEnvelope = doctorEnv(ALL_READY, true);
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '跑完显示结果').toContain('全部就绪');
    fireEvent.click(btnIn(sec2, '运行就绪检查'));
    await flush();
    expect(creates.length, '结束后再点是重新检查（新作业）').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor' });
  }, 20000);

  it('(h) 点 [取消] 只发一次（正文恰 {}）；取消之后再点 [运行就绪检查]，新作业的 [取消] 一出来就可点', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    fireEvent.click(btnIn(sec, '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'running';
    jobEnvelope = null;
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '再点是新作业').toBe(2);
    const cancel2 = btnIn(sec, '取消');
    expect(cancel2.disabled, '新作业的 [取消] 可点（JobCard 按作业号重新挂载）').toBe(false);
  }, 20000);

  it('(i) 创建失败 400：显示就绪检查失败与错误原文；按钮可点，点了重建', async () => {
    createStatus = 400;
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length).toBe(1);
    const t = text(sec);
    expect(t, '失败标题').toContain('就绪检查失败');
    expect(t, '错误原文').toContain('ERROR 不支持这个作业');
    expect(btnIn(sec, '运行就绪检查').disabled, '创建失败后按钮可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '点了重建').toBe(2);
  }, 20000);
});

describe('就绪检查（桩模式）', () => {
  it('(j-loading) loading：一直 running，按钮禁用', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=loading';
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(2200); });
    expect(qa(sec, '[role="progressbar"]').length, 'loading 一直 running').toBeGreaterThanOrEqual(1);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar.getAttribute('aria-label')).toBe('就绪检查进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '运行就绪检查').disabled, '运行中按钮禁用').toBe(true);
  }, 20000);

  it('(j-error) error：落 failed 且没有 data，显示就绪检查失败，不显示结果块', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=error';
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '落 failed').toContain('就绪检查失败');
    expect(t, '没有汇总').not.toContain('全部就绪');
    expect(t, '没有结果块').not.toContain('有未就绪的角色');
    expect(t, '没有就绪卡').not.toContain('profile ');
  }, 20000);
});
