// 「按版本记录核验」一节端到端（T057 合同第 9 步）：真实模式注入假服务，断言创建正文恰两个键、每秒查同一个作业号、
// 进度与 [取消]、结果块（标题「版本记录 <record>」+ 就绪卡、不加汇总行）、有 data 的 failed、没有 data 的 failed、
// 缺 record 键写「—」、取消与超时 600、值不合格不发请求、卸载再挂载与同值/换值再点、创建失败 400、两类作业各管各的禁用；
// 桩模式覆盖 logs-cat.v2 的奇偶两支、别的记录落「还没有版本记录」、loading 与 error 两个开关、缺记录值回 400。
// 等轮询用真实计时器 sleep；测真实组件，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { startJob } from '../src/api';

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
function recordInput(sec: any): HTMLInputElement {
  const label = qa(sec, 'label').find((l: any) => text(l) === '按版本记录核验');
  expect(label, '应有「按版本记录核验」的可见 label').toBeTruthy();
  const id = label.getAttribute('for');
  const input = id ? document.getElementById(id) : null;
  expect(input, 'label 应用 htmlFor 关联 input').toBeTruthy();
  return input as HTMLInputElement;
}
function typeRecord(sec: any, value: string): void {
  fireEvent.change(recordInput(sec), { target: { value } });
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

// 无头行的基底：不带 record 键（缺键写「—」的那份就是它）。
const HEAD_BASE = { role: 'execution', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: ['说明一行（示意）'], allowed: null, credentials: { STEP_API_KEY: true }, ready: true, command: ['node', 'pi.js'], source: 'local', version: '0.1.2', model_listed: true, auth_ready: true, thinking_supported: true };
const RECORD_OK = { ...HEAD_BASE, record: '.agent/runs/logs-cat/binding-v2.json' };
const RECORD_BAD = { ...RECORD_OK, ready: false, problems: ['凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY'], credentials: { STEP_API_KEY: false }, notes: [] };
const PLANNING = { role: 'planning_review', mode: 'interactive_host', problems: [], text: 'interactive_host · claude-code（交互宿主的模型不由 Themis 切换）', ready: true };
const CONTRACT_MANUAL = { role: 'contract', mode: 'manual', problems: [], text: 'manual', ready: true };
const SCHEDULER = { role: 'scheduler_agent', mode: 'disabled', problems: [], text: 'disabled', ready: true };
const ALL_READY = { ready: true, roles: [PLANNING, CONTRACT_MANUAL, HEAD_BASE, SCHEDULER] };
function doctorEnv(data: any, ok: boolean): any {
  return { ok, exit_code: ok ? 0 : 1, data, output: [], messages: [], command: ['config', 'doctor', '--json'], elapsed_ms: 1 };
}
function recordEnv(row: any, ready: boolean): any {
  return { ok: ready, exit_code: ready ? 0 : 1, data: { ready, roles: [row] }, output: [], messages: [], command: ['config', 'doctor', '--record=logs-cat.v2', '--json'], elapsed_ms: 1 };
}

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
let envelopeFor: ((job: any) => any) | null = null;
let createStatus = 201;
let creates: any[] = [];
let cancels: any[] = [];
let queries: string[] = [];
const jobMap = new Map<string, { kind: string; record: string | null }>();

function viewFor(id: string): any {
  const job = jobMap.get(id) || { kind: 'doctor-record', record: null };
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(jobState) >= 0;
  const envelope = envelopeFor != null ? envelopeFor(job) : null;
  return {
    id, kind: job.kind, state: jobState, reason: null,
    created_ms: 1, started_ms: 2, finished_ms: terminal ? 3 : null,
    envelope,
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
      const kind = (body as any)?.kind ?? 'doctor-record';
      const id = (kind === 'doctor' ? 'job-doctor-' : 'job-record-') + seq;
      jobMap.set(id, { kind, record: kind === 'doctor-record' ? ((body as any)?.record ?? null) : null });
      return Promise.resolve({ status: 201, body: { id, kind, state: 'queued', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
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
  envelopeFor = null;
  createStatus = 201;
  creates = [];
  cancels = [];
  queries = [];
  jobMap.clear();
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

describe('按版本记录核验（真实模式）', () => {
  it('(a) 空态：核验组在（label 关联 input、不带 list、不预填、等宽），[核验] 可点 secondary/md 无图标，与 [运行就绪检查] 同一行', () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const entries = sec.querySelector('.rd-entries');
    expect(entries, '横排容器 .rd-entries').toBeTruthy();
    expect(entries.contains(btnIn(sec, '运行就绪检查')), '[运行就绪检查] 与核验组同一行').toBe(true);
    const group = sec.querySelector('.rd-record');
    expect(group, '核验组 .rd-record').toBeTruthy();
    const input = recordInput(sec);
    expect(group.contains(input), '文本框在核验组里').toBe(true);
    expect(input.value, '不预填').toBe('');
    expect(input.getAttribute('list'), '不带 list 属性（没有下拉）').toBeNull();
    expect(String(input.className), '等宽字体（mono）').toContain('mono');
    const v = btnIn(sec, '核验');
    expect(group.contains(v), '[核验] 在核验组里').toBe(true);
    expect(v.disabled, '空闲时 [核验] 一直可点').toBe(false);
    expect(v.getAttribute('data-variant')).toBe('secondary');
    expect(v.getAttribute('data-size')).toBe('md');
    expect(v.querySelector('svg'), '[核验] 不带图标').toBeNull();
    expect(sec.querySelector('select, [role="combobox"], [role="listbox"]'), '没有版本记录的下拉').toBeNull();
    expect(qa(sec, '[role="progressbar"]').length, '空闲不渲染作业卡').toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
  });

  it('(b) 填 logs-cat.v2 点 [核验]：创建正文恰两个键，进度与已用秒数与 [取消]，[核验] 禁用，每秒查同一个作业号', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '只发一次创建（restartJob 与 ensureJob 共用在途创建）').toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    expect(Object.keys(creates[0]).length).toBe(2);
    expect(btnIn(sec, '核验').disabled, '作业排队或运行时 [核验] 禁用').toBe(true);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('核验进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '取消'), '有 [取消]').toBeTruthy();
    expect(btnIn(sec, '运行就绪检查').disabled, 'doctor 那一类不受影响，可以同时跑').toBe(false);
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/job-record-1'), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(c) succeeded：结果块标题「版本记录 .agent/runs/logs-cat/binding-v2.json」+ 就绪卡（八个键值行、说明行），不加汇总行', async () => {
    jobState = 'succeeded';
    envelopeFor = () => recordEnv(RECORD_OK, true);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '标题').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, '卡头 ✓ 就绪').toContain('✓ 就绪');
    expect(t, '卡头角色中文名').toContain('执行端');
    expect(t, '卡头 profile').toContain('profile step-high');
    expect(valuesOf(sec, '命令')).toEqual(['node pi.js（来源：本机文件）']);
    expect(valuesOf(sec, '版本')).toEqual(['0.1.2']);
    expect(valuesOf(sec, '模型在列表中')).toEqual(['是']);
    expect(valuesOf(sec, '登录')).toEqual(['是']);
    expect(valuesOf(sec, '思考级别')).toEqual(['high（本机 pi 接受这个档位）']);
    expect(valuesOf(sec, '允许列表')).toEqual(['不限制']);
    expect(valuesOf(sec, '凭据')).toEqual(['STEP_API_KEY 可用']);
    expect(valuesOf(sec, '接通状态')).toEqual(['已接通']);
    expect(t, '说明行').toContain('说明一行（示意）');
    expect(t, '不加汇总行').not.toContain('全部就绪');
    expect(t, '不加汇总行').not.toContain('有未就绪的角色');
    expect(t, 'succeeded 不显示失败标题').not.toContain('核验失败');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(sec, '核验').disabled, '结束后 [核验] 可点').toBe(false);
  }, 20000);

  it('(d) failed 带 data：照样显示结果块（✗ 未就绪、问题列表、凭据不可用），不显示「核验失败」与内核报错', async () => {
    jobState = 'failed';
    envelopeFor = () => recordEnv(RECORD_BAD, false);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '标题').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, '卡头 ✗ 未就绪').toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('核验失败');
    expect(t, '不显示内核报错').not.toContain('内核报错');
    expect(qa(sec, '[role="progressbar"]').length).toBe(0);
    expect(btnIn(sec, '核验').disabled, '终态后 [核验] 可点').toBe(false);
  }, 20000);

  it('(e) failed 没有 data：显示「核验失败」与内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    envelopeFor = () => errEnv('ERROR: 记录核验示意');
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '内核原文照显示').toContain('ERROR: 记录核验示意');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('未就绪');
  }, 20000);

  it('(f) 那一行缺 record 键：标题写「版本记录 —」，其余照常', async () => {
    jobState = 'succeeded';
    envelopeFor = () => recordEnv(HEAD_BASE, true);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '缺键写「—」').toContain('版本记录 —');
    expect(t, '就绪卡照常').toContain('✓ 就绪');
  }, 20000);

  it('(g) 点 [取消] 只发一次（正文恰 {}）；取消后落「已取消」，再点是新作业且 [取消] 可点；超时显示「超时（超过 600 秒），已停止」', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    fireEvent.click(btnIn(sec, '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'running';
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '取消后再点是新作业（只发一次创建）').toBe(2);
    expect(btnIn(sec, '取消').disabled, '新作业的 [取消] 可点（JobCard 按作业号重新挂载）').toBe(false);
    jobState = 'timed_out';
    await act(async () => { await sleep(1300); });
    expect(text(sec), '超时 600').toContain('超时（超过 600 秒），已停止');
  }, 20000);

  it('(h) 值不合格（空、大写、没有 .v、v0、尾空格、超长）点 [核验] 不发请求、出提示且 aria-invalid；改文本框就清掉；合格的值照常起作业', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const input = recordInput(sec);
    for (const value of ['', 'LOGS-CAT.V2', 'logs-cat', 'logs-cat.v0', 'logs-cat.v2 ', `${'a'.repeat(65)}.v1`]) {
      fireEvent.change(input, { target: { value } });
      fireEvent.click(btnIn(sec, '核验'));
      await flush();
      expect(creates.length, `「${value}」不合格，不发创建请求`).toBe(0);
      expect(text(sec), `「${value}」应出提示`).toContain('写成 <task-id>.v<N>，例如 logs-cat.v2');
      expect(input.getAttribute('aria-invalid'), '出错时 aria-invalid 为真').toBe('true');
    }
    expect(queries.length, '没有作业就没有查询').toBe(0);
    fireEvent.change(input, { target: { value: 'logs-cat.v2' } });
    await flush();
    expect(text(sec), '改了文本框就清提示').not.toContain('写成 <task-id>');
    expect(input.getAttribute('aria-invalid'), '清掉后 aria-invalid 不在').toBeNull();
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '合格的值照常起作业').toBe(1);
  }, 20000);

  it('(i) 卸载再挂载看到同一个作业、不再发创建请求；跑完显示结果；结束后同值再点、换值再点都只发一次新的创建请求', async () => {
    const r = mountReady();
    typeRecord(readySection(r.container), 'logs-cat.v2');
    fireEvent.click(btnIn(readySection(r.container), '核验'));
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
    envelopeFor = () => recordEnv(RECORD_OK, true);
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '跑完显示结果').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    // 回来时文本框是空的（不预填、不记住上次的值）：要再点得先把值填回去。
    typeRecord(sec2, 'logs-cat.v2');
    fireEvent.click(btnIn(sec2, '核验'));
    await flush();
    expect(creates.length, '同值再点是新作业（只发一次创建）').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    await act(async () => { await sleep(1300); });
    typeRecord(sec2, 'other-task.v1');
    // 换值后的结局先设好：新作业落 failed 且没有 data，这一节照旧显示内核报错原文（不显示结果块）。
    jobState = 'failed';
    envelopeFor = () => errEnv('ERROR: other-task.v1 还没有版本记录');
    fireEvent.click(btnIn(sec2, '核验'));
    await flush();
    expect(creates.length, '换值再点也是新作业（只发一次创建）').toBe(3);
    expect(creates[2]).toEqual({ kind: 'doctor-record', record: 'other-task.v1' });
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '换值后的失败照显示内核原文').toContain('ERROR: other-task.v1 还没有版本记录');
    // 文本框清空之后再点：空值不合格，只出提示、不发新的创建请求（不记住上次填过的值）。
    fireEvent.change(recordInput(sec2), { target: { value: '' } });
    fireEvent.click(btnIn(sec2, '核验'));
    await flush();
    expect(creates.length, '空值不合格，不发创建请求').toBe(3);
    expect(text(sec2), '空值应出提示').toContain('写成 <task-id>.v<N>，例如 logs-cat.v2');
  }, 20000);

  it('(j) 创建失败 400：显示「核验失败」与错误原文；[核验] 仍可点，点了重建', async () => {
    createStatus = 400;
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length).toBe(1);
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '错误原文').toContain('ERROR 不支持这个作业');
    expect(btnIn(sec, '核验').disabled, '创建失败后 [核验] 可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '点了重建').toBe(2);
  }, 20000);

  it('(k) 两类作业各管各的：doctor 在跑时 [核验] 仍可点、核验在跑时 [运行就绪检查] 仍可点；两条进度条各带自己的名字', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length).toBe(1);
    expect(creates[0]).toEqual({ kind: 'doctor' });
    expect(btnIn(sec, '核验').disabled, 'doctor 在跑不影响 [核验]（各管各的禁用）').toBe(false);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '两类各建一个').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    expect(btnIn(sec, '核验').disabled, '两类同时跑，[核验] 因自己的作业禁用').toBe(true);
    expect(btnIn(sec, '运行就绪检查').disabled, '两类同时跑，[运行就绪检查] 因自己的作业禁用').toBe(true);
    await act(async () => { await sleep(400); });
    const labels = qa(sec, '[role="progressbar"]').map((b: any) => b.getAttribute('aria-label'));
    expect(labels, '两条进度条各带自己的名字').toContain('核验进行中');
    expect(labels).toContain('就绪检查进行中');
    expect(queries.filter((p) => p.indexOf('job-doctor-') >= 0).length, 'doctor 的作业在查').toBeGreaterThan(0);
    expect(queries.filter((p) => p.indexOf('job-record-') >= 0).length, 'record 的作业在查').toBeGreaterThan(0);
    jobState = 'succeeded';
    envelopeFor = (job: any) => job.kind === 'doctor' ? doctorEnv(ALL_READY, true) : recordEnv(RECORD_OK, true);
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, 'doctor 的结果').toContain('全部就绪');
    expect(t, 'record 的结果').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
  }, 20000);

  it('(l) 没点过：不排每秒空转的计时器，也没有作业请求', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    mountReady();
    await act(async () => { await sleep(2600); });
    const perSecond = spy.mock.calls.filter((c: any[]) => c[1] === 1000);
    expect(perSecond.length, '没有作业时不排 1000 毫秒的计时器').toBe(0);
    expect(creates.length).toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
    spy.mockRestore();
  }, 20000);
});

describe('按版本记录核验（桩模式）', () => {
  it('(m) logs-cat.v2 的奇偶两支：第奇数份没就绪（failed 带 data、不显示核验失败），第偶数份就绪（✓ 就绪、凭据可用）', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=data';
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    let t = text(sec);
    expect(t, '奇数份的结果块').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, '奇数份没就绪（failed 带 data）').toContain('✗ 未就绪');
    expect(t, '不显示笼统的失败标题').not.toContain('核验失败');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    t = text(sec);
    expect(t, '偶数份就绪').toContain('✓ 就绪');
    expect(t, '凭据可用').toContain('STEP_API_KEY 可用');
    expect(t, '没有未就绪的卡头').not.toContain('✗ 未就绪');
    expect(btnIn(sec, '核验').disabled, '终态后 [核验] 可点').toBe(false);
  }, 20000);

  it('(n) 别的记录落 failed 且没有 data：显示「核验失败」与内核那句原文，不显示结果块', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=data';
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'other-task.v1');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '还没有版本记录那句').toContain('ERROR: other-task.v1 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('✗ 未就绪');
  }, 20000);

  it('(o) loading 开关：一直 running（进度条与已用秒数），[核验] 一直禁用，doctor 空闲不受影响', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=loading';
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2200); });
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, 'loading 一直 running').toBeTruthy();
    expect(bar.getAttribute('aria-label')).toBe('核验进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '核验').disabled, '运行中 [核验] 禁用').toBe(true);
    expect(btnIn(sec, '运行就绪检查').disabled, 'doctor 空闲不受影响').toBe(false);
  }, 20000);

  it('(p) error 开关：落 failed 且没有 data，显示「核验失败」，不显示结果块', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=error';
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '落 failed').toContain('核验失败');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('✓ 就绪');
    expect(t).not.toContain('✗ 未就绪');
  }, 20000);

  it('(q) 两类作业可以同时跑：doctor 与 doctor-record 各建一个、两条进度条各带自己的名字', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=loading';
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(btnIn(sec, '核验').disabled, 'doctor 在跑不影响 [核验]').toBe(false);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(btnIn(sec, '核验').disabled, '自己的作业在跑，[核验] 禁用').toBe(true);
    expect(btnIn(sec, '运行就绪检查').disabled, 'doctor 自己的作业在跑').toBe(true);
    await act(async () => { await sleep(1200); });
    const labels = qa(sec, '[role="progressbar"]').map((b: any) => b.getAttribute('aria-label'));
    expect(labels).toContain('核验进行中');
    expect(labels).toContain('就绪检查进行中');
  }, 20000);

  it('(r) startJob 缺记录值回 400，带 logs-cat.v2 放行（201）', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=data';
    const bad = await startJob('doctor-record');
    expect(bad.status, '缺记录值应回 400（与服务同样的规则）').toBe(400);
    const ok = await startJob('doctor-record', 'logs-cat.v2');
    expect(ok.status, '带记录值放行').toBe(201);
  }, 20000);
});
