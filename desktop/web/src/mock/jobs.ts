// 作业接口的桩（T054，T055 加 runtime-probe 与 models 两类）：模块级作业表 + ?mock= 五开关的状态机，
// 不用计时器（每次调用都回已兑现的 Promise）。loading 一直 running、error 第一次查询就落 failed、
// data/offline/empty 第一次查询 running 第二次 succeeded；取消没结束回 200 并落 cancelled、已结束回 409；
// 查不存在的作业号回 404。runtime-scan 那一路与 T054 一字不改。
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

// 探测夹具的 pi 两份（照 scripts/kit_roles.py 的 _runtime_probe --json）：第奇数次 ok 为假（内核退出码 1，
// 作业落 failed 但 data 里仍有探测到的东西），第偶数次正常。非 pi 的 runtime 只有不带 help 的正常一份。
function probeData(runtime: string, odd: boolean): Record<string, unknown> {
  if (runtime !== 'pi') {
    return { runtime, adapter: runtime, source: 'path', command: [runtime], version_exit_code: 0, version: '1.0.9', ok: true };
  }
  if (odd) {
    return {
      runtime: 'pi', adapter: 'pi', source: 'local', command: null, version_exit_code: 1, version: '',
      help: { exit_code: 1, missing_flags: ['--no-context-files'], thinking_levels: [] }, ok: false,
    };
  }
  return {
    runtime: 'pi', adapter: 'pi', source: 'local', command: ['node', 'pi.js'], version_exit_code: 0, version: '0.1.2',
    help: { exit_code: 0, missing_flags: [], thinking_levels: ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'] }, ok: true,
  };
}

function probeEnvelope(runtime: string, odd: boolean): Envelope<unknown> {
  const data = probeData(runtime, odd);
  const ok = data.ok === true;
  return {
    ok,
    exit_code: ok ? 0 : 1,
    data,
    output: [],
    messages: ok ? [] : ['ERROR 探测失败：内核报错（示意）'],
    command: ['config', 'runtime', 'probe', runtime, '--json'],
    elapsed_ms: 0,
  };
}

// 列模型夹具（照 scripts/kit_roles.py 的 _models --json）：四行里一行不在允许列表、一行疑似凭据被遮。
function modelsEnvelope(runtime: string): Envelope<unknown> {
  return {
    ok: true,
    exit_code: 0,
    data: {
      runtime,
      models: [
        { provider: 'stepfun', model: 'step-5-preview', allowed: true },
        { provider: 'deepseek', model: 'deepseek-chat', allowed: false },
        { provider: 'anthropic', model: 'claude-x', allowed: null },
        { provider: '<redacted>', model: '<redacted>', allowed: true },
      ],
      allowed_executors_set: true,
    },
    output: [],
    messages: [],
    command: ['config', 'models', runtime, '--json'],
    elapsed_ms: 0,
  };
}

// 就绪检查夹具（照内核 config doctor --json 与 roles.json 的四个角色）：执行端是无头行，其余三个角色只有一行 text。
// 第奇数次执行端没就绪（凭据不可用、data.ready 为假、退出码 1，作业落 failed 但 data 照给），第偶数次全部就绪。
function doctorHeadlessRow(ready: boolean): Record<string, unknown> {
  return {
    role: 'execution', mode: 'headless', ready,
    profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high',
    connected: true, command: ['node', 'pi.js'], source: 'local', version: '0.1.2',
    model_listed: true, auth_ready: true, thinking_supported: true, allowed: true,
    credentials: { STEP_API_KEY: ready },
    problems: ready ? [] : ['凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY'],
    notes: [],
  };
}

function doctorEnvelope(odd: boolean): Envelope<unknown> {
  const ready = !odd;
  const roles = [
    { role: 'planning_review', mode: 'interactive_host', problems: [], text: 'interactive_host · claude-code（交互宿主的模型不由 Themis 切换）', ready: true },
    { role: 'contract', mode: 'manual', problems: [], text: 'manual', ready: true },
    doctorHeadlessRow(ready),
    { role: 'scheduler_agent', mode: 'disabled', problems: [], text: 'disabled', ready: true },
  ];
  return {
    ok: ready,
    exit_code: ready ? 0 : 1,
    data: odd ? { ready: false, roles } : { ready: true, roles },
    output: [],
    messages: [],
    command: ['config', 'doctor', '--json'],
    elapsed_ms: 0,
  };
}

// error 开关对两类新作业的失败信封：没有 data，一行示意原文。
function kindFailedEnvelope(kind: JobKind, runtime: string | null): Envelope<unknown> {
  if (kind === 'runtime-probe') {
    return { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 探测失败：内核报错（示意）'], command: ['config', 'runtime', 'probe', runtime ?? '', '--json'], elapsed_ms: 0 };
  }
  if (kind === 'doctor') {
    return { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 就绪检查失败：内核报错（示意）'], command: ['config', 'doctor', '--json'], elapsed_ms: 0 };
  }
  return { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 列模型失败：内核报错（示意）'], command: ['config', 'models', runtime ?? '', '--json'], elapsed_ms: 0 };
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
  // 槽里这个作业是哪个 runtime 的（探测与列模型用）。
  runtime: string | null;
  // 探测夹具的奇偶份：同一个 runtime 的第奇数次探测 ok 为假、第偶数次正常。
  probeOdd: boolean;
  // 就绪检查夹具的奇偶份：第奇数次执行端没就绪（落 failed 带 data）、第偶数次全部就绪。
  doctorOdd: boolean;
}

const jobs = new Map<string, MockJob>();
let seq = 0;
// 每个 runtime 建过几个探测作业（奇偶份按它算）。
const probeCounts = new Map<string, number>();
// 建过几个 doctor 作业（奇偶份按作业次序算，不看 runtime——doctor 没有 runtime）。
const doctorCounts = new Map<string, number>();

export function mockStartJob(kind: JobKind, runtime?: string): Promise<HttpReply<JobView>> {
  // 探测与列模型必须带 runtime（服务要扁平正文里的 runtime 键，缺了回 400）；doctor 不带 runtime（正文只有 kind）。
  if ((kind === 'runtime-probe' || kind === 'models') && (runtime == null || runtime === '')) {
    return Promise.resolve({ status: 400, body: errEnvelope('runtime-probe 与 models 要带 runtime') });
  }
  seq += 1;
  let probeOdd = false;
  if (kind === 'runtime-probe') {
    const n = (probeCounts.get(runtime as string) ?? 0) + 1;
    probeCounts.set(runtime as string, n);
    probeOdd = n % 2 === 1;
  }
  let doctorOdd = false;
  if (kind === 'doctor') {
    const n = (doctorCounts.get('doctor') ?? 0) + 1;
    doctorCounts.set('doctor', n);
    doctorOdd = n % 2 === 1;
  }
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
  jobs.set(view.id, { view, queries: 0, runtime: runtime ?? null, probeOdd, doctorOdd });
  return Promise.resolve({ status: 201, body: jobEnvelope(view) });
}

// 终态信封：扫描恒 succeeded；探测照奇偶份（ok 为假时落 failed 但 data 照给）；列模型恒 succeeded；就绪检查照奇偶份。
function terminalEnvelope(job: MockJob): Envelope<unknown> {
  if (job.view.kind === 'runtime-probe') return probeEnvelope(job.runtime ?? '', job.probeOdd);
  if (job.view.kind === 'models') return modelsEnvelope(job.runtime ?? 'pi');
  if (job.view.kind === 'doctor') return doctorEnvelope(job.doctorOdd);
  return scanEnvelope();
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
    job.view = { ...job.view, state: 'failed', finished_ms: Date.now(), envelope: job.view.kind === 'runtime-scan' ? scanFailedEnvelope() : kindFailedEnvelope(job.view.kind, job.runtime) };
    return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  }
  // data / offline / empty：第一次查询 running，第二次 succeeded（探测的 ok 为假那份落 failed）。
  if (job.queries === 1) {
    job.view = { ...job.view, state: 'running', started_ms: job.view.started_ms ?? Date.now() };
    return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
  }
  const envelope = terminalEnvelope(job);
  job.view = { ...job.view, state: envelope.ok ? 'succeeded' : 'failed', finished_ms: Date.now(), envelope };
  return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
}

export function mockCancelJob(id: string): Promise<HttpReply<JobView>> {
  const job = jobs.get(id);
  if (job == null) return Promise.resolve({ status: 404, body: errEnvelope('没有这个作业') });
  if (isTerminalState(job.view.state)) return Promise.resolve({ status: 409, body: errEnvelope('作业已经结束') });
  job.view = { ...job.view, state: 'cancelled', finished_ms: Date.now(), envelope: null };
  return Promise.resolve({ status: 200, body: jobEnvelope(job.view) });
}
