// 作业接口的桩（T054）：模块级作业表 + ?mock= 五开关的状态机，不用计时器（每次调用都回已兑现的 Promise）。
// loading 一直 running、error 第一次查询就落 failed、data/offline/empty 第一次查询 running 第二次 succeeded；
// 取消没结束回 200 并落 cancelled、已结束回 409；查不存在的作业号回 404。本片只实现 runtime-scan 一类。
import { currentMock } from './scenario';
import type { Envelope, HttpReply, JobKind, JobState, JobView } from '../api';

// 扫描夹具一行（照 scripts/kit_roles.py 的 _runtime_scan --json 形状；PATH 上没有的适配器三项都是 null）。
interface Found {
  adapter: string;
  program: string;
  path: string | null;
  version: string | null;
  exit_code: number | null;
}

function foundFixture(): Found[] {
  return [
    { adapter: 'pi', program: 'pi', path: 'C:/tools/pi/pi.exe', version: '0.1.2', exit_code: 0 },
    { adapter: 'claude-code', program: 'claude', path: 'C:/tools/npm/claude.cmd', version: '1.0.9', exit_code: 0 },
    { adapter: 'codex', program: 'codex', path: 'C:/tools/codex/codex.exe', version: '0.5.0', exit_code: 0 },
    { adapter: 'opencode', program: 'opencode', path: null, version: null, exit_code: null },
    { adapter: 'quizs', program: 'quizs', path: null, version: null, exit_code: null },
  ];
}

// succeeded 的扫描信封：data 是 { found, added }（added 恒空，登记由单独的 runtime.add 写流程做）。
function scanEnvelope(): Envelope<unknown> {
  return {
    ok: true,
    exit_code: 0,
    data: { found: foundFixture(), added: [] },
    output: [],
    messages: [],
    command: ['config', 'runtime', 'scan', '--json'],
    elapsed_ms: 0,
  };
}

// error 开关的失败信封：一行示意原文。
function scanFailedEnvelope(): Envelope<unknown> {
  return {
    ok: false,
    exit_code: 1,
    data: null,
    output: [],
    messages: ['ERROR 扫描失败：内核报错（示意）'],
    command: ['config', 'runtime', 'scan', '--json'],
    elapsed_ms: 0,
  };
}

function jobEnvelope(view: JobView): Envelope<JobView> {
  return { ok: true, exit_code: 0, data: view, output: [], messages: [], command: [], elapsed_ms: 0 };
}

function errEnvelope(message: string): Envelope<JobView> {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function isTerminalState(state: JobState): boolean {
  return state === 'succeeded' || state === 'failed' || state === 'cancelled' || state === 'timed_out';
}

interface MockJob {
  view: JobView;
  queries: number;
}

const jobs = new Map<string, MockJob>();
let seq = 0;

export function mockStartJob(kind: JobKind): Promise<HttpReply<JobView>> {
  if (kind !== 'runtime-scan') return Promise.resolve({ status: 400, body: errEnvelope('这个桩只接 runtime-scan') });
  seq += 1;
  const view: JobView = {
    id: `mock-job-${seq}`,
    kind,
    state: 'queued',
    reason: null,
    created_ms: Date.now(),
    started_ms: null,
    finished_ms: null,
    envelope: null,
  };
  jobs.set(view.id, { view, queries: 0 });
  return Promise.resolve({ status: 201, body: jobEnvelope(view) });
}

export function mockGetJob(id: string): Promise<HttpReply<JobView>> {
  const job = jobs.get(id);
  if (job == null) return Promise.resolve({ status: 404, body: errEnvelope('没有这个作业') });
  job.queries += 1;
  // 取消过的作业保持 cancelled（终态，不再随开关变）。
  if (job.view.state === 'cancelled') return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  const mode = currentMock();
  if (mode === 'loading') {
    job.view = { ...job.view, state: 'running', started_ms: job.view.started_ms ?? Date.now() };
    return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  }
  if (mode === 'error') {
    job.view = { ...job.view, state: 'failed', finished_ms: Date.now(), envelope: scanFailedEnvelope() };
    return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  }
  // data / offline / empty：第一次查询 running，第二次 succeeded。
  if (job.queries === 1) {
    job.view = { ...job.view, state: 'running', started_ms: job.view.started_ms ?? Date.now() };
    return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  }
  job.view = { ...job.view, state: 'succeeded', finished_ms: Date.now(), envelope: scanEnvelope() };
  return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
}

export function mockCancelJob(id: string): Promise<HttpReply<JobView>> {
  const job = jobs.get(id);
  if (job == null) return Promise.resolve({ status: 404, body: errEnvelope('没有这个作业') });
  if (isTerminalState(job.view.state)) return Promise.resolve({ status: 409, body: errEnvelope('作业已经结束') });
  job.view = { ...job.view, state: 'cancelled', finished_ms: Date.now(), envelope: null };
  return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
}
