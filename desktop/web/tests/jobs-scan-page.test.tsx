// ScanRuntimesAction 端到端（T054 合同第 11 步 (a)–(g)）：真实模式注入假服务，断言入口可点、创建正文、
// 轮询、已用秒数、取消、四种结局、结果表三种行与 [登记…] 的完整写流程；桩模式覆盖 data 与 error 两个开关。
// 等轮询用真实计时器 sleep（照门禁探针的写法）；测真实组件，不 mock 被测组件。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { ScanRuntimesAction } from '../src/writes/RuntimeScan';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const ENTRY = '扫描 PATH';
const JOB_ID = 'scan-page-job-0000000000000000000';

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
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function envOf<T>(data: T): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 0 };
}

let jobState = 'running';
const creates: any[] = [];
const cancels: any[] = [];
const queries: string[] = [];
const posts: Array<{ path: string; body: any }> = [];
let runtimesFail = false;

function scanEnvelope(): any {
  const found = [
    { adapter: 'pi', program: 'pi', path: 'C:/tools/pi/pi.exe', version: '0.1.2', exit_code: 0 },
    { adapter: 'claude-code', program: 'claude', path: 'C:/tools/npm/claude.cmd', version: '1.0.9', exit_code: 0 },
    { adapter: 'codex', program: 'codex', path: 'C:/tools/codex/codex.exe', version: '0.5.0', exit_code: 0 },
    { adapter: 'opencode', program: 'opencode', path: null, version: null, exit_code: null },
    { adapter: 'quizs', program: 'quizs', path: null, version: null, exit_code: null },
  ];
  return { ok: true, exit_code: 0, data: { found, added: [] }, output: [], messages: [], command: ['config', 'runtime', 'scan', '--json'], elapsed_ms: 10 };
}

const RUNTIMES_OK = {
  runtimes: [
    { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
    { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
    { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
  ],
};

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/runtimes') {
      if (runtimesFail) return Promise.resolve({ ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 读不出'], command: [], elapsed_ms: 0 });
      return Promise.resolve(envOf(RUNTIMES_OK));
    }
    return Promise.resolve(envOf(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const preview = { binding_changes: [], resources: [{ resource: 'runtimes' }], notes: [], warnings: [], running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [] };
      return Promise.resolve({ status: 200, body: envOf({ preview, confirmation: 'c-scan-1' }) });
    }
    return Promise.resolve({ status: 200, body: envOf(null) });
  },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0) {
      queries.push(path);
      const terminal = jobState !== 'queued' && jobState !== 'running';
      const envelope = jobState === 'succeeded' ? scanEnvelope() : jobState === 'failed' ? { ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR: 内核扫描失败（示意）'], command: [], elapsed_ms: 5 } : null;
      return Promise.resolve({ status: 200, body: { id: JOB_ID, kind: 'runtime-scan', state: jobState, reason: null, created_ms: 1, started_ms: 2, finished_ms: terminal ? 3 : null, envelope } });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      return Promise.resolve({ status: 201, body: { id: JOB_ID, kind: 'runtime-scan', state: 'queued', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
    }
    if (path.indexOf('/api/v1/jobs/') === 0 && path.endsWith('/cancel')) {
      cancels.push(body);
      jobState = 'cancelled';
      return Promise.resolve({ status: 200, body: { id: JOB_ID, kind: 'runtime-scan', state: 'cancelled', reason: null, created_ms: 1, started_ms: 2, finished_ms: 3, envelope: null } });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  jobState = 'running';
  creates.length = 0;
  cancels.length = 0;
  queries.length = 0;
  posts.length = 0;
  runtimesFail = false;
  window.location.hash = '';
  setLiveClientForTests(fake);
});

afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('ScanRuntimesAction：端到端（真实模式）', () => {
  it('(a) 入口 secondary/md/带 svg/一直可点；创建正文恰 {"kind":"runtime-scan"}；每秒查同一个作业号', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled).toBe(false);
    expect(entry.getAttribute('data-variant')).toBe('secondary');
    expect(entry.getAttribute('data-size')).toBe('md');
    expect(entry.querySelector('svg')).toBeTruthy();
    fireEvent.click(entry);
    await flush();
    expect(creates.length).toBe(1);
    expect(creates[0]).toEqual({ kind: 'runtime-scan' });
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
    await act(async () => { await sleep(1300); });
    expect(queries.length).toBeGreaterThanOrEqual(1);
    expect(queries.every((p) => p === '/api/v1/jobs/' + JOB_ID)).toBe(true);
  }, 20000);

  it('(b) 运行中显示「已用 N 秒」并随时间增加；[取消] 发 POST .../cancel，随后「已取消」', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const d = needDlg();
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    expect(cancels.length).toBe(1);
    expect(cancels[0]).toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(needDlg())).toContain('已取消');
    expect(qa(needDlg(), '[role="progressbar"]').length).toBe(0);
  }, 20000);

  it('(c) failed「扫描失败」+ 内核原文；重新扫描后 timed_out「超时（超过 150 秒），已停止」', async () => {
    jobState = 'failed';
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d)).toContain('扫描失败');
    expect(text(d)).toContain('ERROR: 内核扫描失败（示意）');
    jobState = 'timed_out';
    fireEvent.click(btnIn(d, '重新扫描'));
    await flush();
    expect(creates.length).toBe(2);
    await act(async () => { await sleep(1300); });
    expect(text(needDlg())).toContain('超时（超过 150 秒），已停止');
  }, 20000);

  it('(d) 结果表：四列列头、五种行（已登记无按钮 / 登记… / 没找到 — 无按钮）', async () => {
    jobState = 'succeeded';
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(qa(d, 'table th').map((el: any) => text(el))).toEqual(['适配器', '路径', '版本', '操作']);
    const rows = qa(d, 'table tbody tr');
    expect(rows.length).toBe(5);
    const cellsOf = (row: any) => qa(row, 'td').map((c: any) => text(c));
    expect(cellsOf(rows[0])).toEqual(['pi', 'C:/tools/pi/pi.exe', '0.1.2', '已登记']);
    expect(qa(rows[0], 'button').length).toBe(0);
    expect(btnIn(rows[2], '登记…').disabled).toBe(false);
    expect(cellsOf(rows[3])).toEqual(['opencode', '—', '—', '']);
    expect(qa(rows[3], 'button').length).toBe(0);
  }, 20000);

  it('(e) [登记…] 先关扫描框再开确认框；预览 args 恰 runtime+adapter；执行正文 adapter+confirmation；reload', async () => {
    jobState = 'succeeded';
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<ScanRuntimesAction reload={reload} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    fireEvent.click(btnIn(needDlg(), '登记…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '扫描框已关、确认框标题').toContain('登记运行时 codex？');
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect((prev!.body as any).action).toBe('runtime.add');
    expect((prev!.body as any).args).toEqual({ runtime: 'codex', adapter: 'codex' });
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await act(async () => { await sleep(300); });
    const writes = posts.filter((x) => x.path === '/api/v1/runtimes/codex/add');
    expect(writes.length).toBe(1);
    expect(Object.keys(writes[0].body).sort()).toEqual(['adapter', 'confirmation']);
    expect(text(document.body)).toContain('已登记运行时 codex');
    expect(reload).toHaveBeenCalled();
  }, 20000);

  it('(f) 关掉再开：接着同一个作业，不再发创建请求', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(creates.length).toBe(1);
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg()).toBeNull();
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(creates.length, '再开不再创建').toBe(1);
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);
});

describe('ScanRuntimesAction：桩模式', () => {
  it('(g-data) data：先 running 后 succeeded，结果表出现（列头四列、codex 给登记…）', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=data';
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
    await act(async () => { await sleep(2300); });
    const d = needDlg();
    expect(qa(d, 'table th').map((el: any) => text(el))).toEqual(['适配器', '路径', '版本', '操作']);
    const rows = qa(d, 'table tbody tr');
    expect(rows.length).toBe(5);
    expect(btnIn(rows[2], '登记…')).toBeTruthy();
  }, 20000);

  it('(g-error) error：第一次查询就落 failed，显示「扫描失败」与示意原文', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/runtimes?mock=error';
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d)).toContain('扫描失败');
    expect(text(d)).toContain('ERROR 扫描失败：内核报错（示意）');
  }, 20000);
});
