// 真实模式下的写流程状态机（T040 第 2 片）：只经 setLiveClientForTests 注入假服务，不断言在副本里——
// 打交道的全是真实的 useWriteFlow、真实的 api.ts 路由与真实的 WriteConfirmDialog 文案。
// 覆盖成功（W3）、状态已变、过期、繁忙、断线后轮询、轮询到 120 秒、服务出错、超时、部分写入、内核拒绝、
// 真实模式门、真实模式下的重读失败与 needs_yes 的三种情形。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, PresetsData, RolesData } from '../src/api';
import presetsJson from '../src/mock/presets.json';
import rolesJson from '../src/mock/roles.json';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { PresetBar } from '../src/pages/readonly1/roles-PresetBar';

// 合同 Behavior contract 逐字写死的原因句（D02）。
const REASON = '有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。';
// 预览签发的确认号：执行正文与操作查询路径都按它断言。
const CONFIRMATION = 'conf-live-1';
// 信封顶层的预览命令：带 --dry-run --json，对话框里要去的正是这两个开关。
const PREVIEW_COMMAND = ['config', 'preset', 'use', 'economy', '--dry-run', '--json'];

const PRESETS = presetsJson as unknown as PresetsData;
const ROLES = rolesJson as unknown as RolesData;

type ExecPlan = { status: number; body: Envelope<null> } | { reject: Error };
// 重读阶段的读：照常 / 快照变 / 信封 ok 为假 / reject / 挂起。
type ReadPlan = 'ok' | 'changed' | 'fail' | 'reject' | 'hang';
type OpPlan = { status: number; body: unknown } | { reject: Error };

interface Call {
  path: string;
  timeoutSeconds: number | undefined;
}

const gets: Call[] = [];
const posts: Array<Call & { body: unknown }> = [];
const raws: Call[] = [];

let afterExec = false;
let execPlan: ExecPlan | null = null;
let readPlan: ReadPlan = 'ok';
let opPlans: OpPlan[] = [{ status: 404, body: null }];
let previewJson: Record<string, unknown> = basePreview(false);
// 挂起的读（重读卡住用）：兑现时逐个 resolve。
const hungReads: Array<(value: unknown) => void> = [];

function basePreview(needsYes: boolean, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [{ role: 'execution', before: 'step-high', after: 'step-low' }],
    changed: true,
    dry_run: true,
    needs_yes: needsYes,
    notes: [],
    resources: [{ resource: 'roles' }],
    running_attempts: [],
    unreadable: [],
    warnings: [],
    ...extra,
  };
}

function envelope<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

function failEnvelope(messages: string[]): Envelope<null> {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

function operationView(state: string, envelopeForOp: Envelope<null> | null = null): Record<string, unknown> {
  return {
    id: CONFIRMATION,
    action: 'preset.use',
    state,
    reason: state === 'failed' ? 'exit' : null,
    created_ms: 0,
    started_ms: 1,
    finished_ms: state === 'running' ? null : 5,
    envelope: envelopeForOp,
  };
}

// 假客户端：get/post/getRaw 都记下路径、正文与时限，并按上面的编排变量给出应答。
const fake: LiveClient = {
  get<T>(path: string, _query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>> {
    gets.push({ path, timeoutSeconds });
    if (afterExec && readPlan !== 'ok') {
      if (readPlan === 'fail') return Promise.resolve(failEnvelope(['ERROR: 状态读不出来']) as unknown as Envelope<T>);
      if (readPlan === 'reject') return Promise.reject(new Error('读不到'));
      // 只有 presets 挂起：roles 照常兑现，卡住的才是重读本身。
      if (readPlan === 'hang' && path === '/api/v1/presets') {
        return new Promise<Envelope<T>>((resolve) => {
          hungReads.push(resolve as (value: unknown) => void);
        });
      }
    }
    if (path === '/api/v1/presets') {
      const active = afterExec && readPlan === 'changed' ? 'economy' : 'default';
      return Promise.resolve(envelope({ ...PRESETS, active_preset: active }) as unknown as Envelope<T>);
    }
    if (path === '/api/v1/roles') return Promise.resolve(envelope(ROLES) as unknown as Envelope<T>);
    return Promise.resolve(failEnvelope([`假服务没有编排 ${path} 的应答`]) as unknown as Envelope<T>);
  },
  post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body, timeoutSeconds });
    if (path === '/api/v1/preview') {
      return Promise.resolve({
        status: 200,
        body: envelope({ preview: previewJson, confirmation: CONFIRMATION }, PREVIEW_COMMAND) as unknown as Envelope<T>,
      });
    }
    afterExec = true;
    if (execPlan && 'reject' in execPlan) return Promise.reject(execPlan.reject);
    const plan: ExecPlan = execPlan ?? { status: 500, body: failEnvelope(['假服务没有编排执行应答']) };
    return Promise.resolve({ status: plan.status, body: plan.body as unknown as Envelope<T> });
  },
  getRaw<T>(path: string, _query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }> {
    raws.push({ path, timeoutSeconds });
    const plan = opPlans[Math.min(raws.length - 1, opPlans.length - 1)];
    if ('reject' in plan) return Promise.reject(plan.reject);
    return Promise.resolve({ status: plan.status, body: plan.body as T });
  },
};

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const toastText = () => text(document.querySelector('.tt-toast'));
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
const countGets = (path: string) => gets.filter((c) => c.path === path).length;

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function releaseHungReads() {
  const waiting = hungReads.splice(0, hungReads.length);
  for (const resolve of waiting) resolve(envelope({ ...PRESETS, active_preset: 'economy' }));
}

async function openConfirm(hash: string) {
  window.location.hash = hash;
  render(<PresetBar presets={PRESETS.presets} active="default" />);
  await settle();
  const radio = Array.from(document.querySelectorAll('[role="radio"]')).find((r) => text(r) === 'economy');
  fireEvent.click(radio as HTMLElement);
  await settle();
  fireEvent.click(btn(document.body, '切换…') as HTMLButtonElement);
  await settle();
  dlgText();
}
async function confirmNow() {
  fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
  await settle();
  await advance(20);
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  gets.length = 0;
  posts.length = 0;
  raws.length = 0;
  hungReads.length = 0;
  afterExec = false;
  execPlan = null;
  readPlan = 'ok';
  opPlans = [{ status: 404, body: null }];
  previewJson = basePreview(false);
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('成功：真实路由与「只在重读之后才说」（W3）', () => {
  it('预览发 POST /api/v1/preview，执行发 POST /api/v1/presets/economy/use（正文只有确认号、时限 90 秒）', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles');
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'preset.use', args: { name: 'economy' } });
    expect(posts[0].timeoutSeconds).toBe(30);
    const before = dlgText();
    expect(before).toContain('将运行的命令');
    expect(before).toContain('config preset use economy');
    expect(before).not.toContain('--dry-run');
    expect(before).not.toContain('--json');
    await confirmNow();
    expect(posts.length).toBe(2);
    expect(posts[1].path).toBe('/api/v1/presets/economy/use');
    expect(posts[1].body).toEqual({ confirmation: CONFIRMATION });
    expect(posts[1].timeoutSeconds).toBe(90);
    expect(dlg(), '重读完成后关框').toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('重读挂起时整页没有「已切换」、Toast 空；兑现之后才说成功', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles');
    readPlan = 'hang';
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(dlg(), '重读中框还开着').not.toBeNull();
    expect(dlgText()).not.toContain('已切换');
    expect(toastText(), '重读兑现之前 Toast 区域是空的').toBe('');
    expect(bodyText(), '重读兑现之前整页没有「已切换」').not.toContain('已切换');
    releaseHungReads();
    await settle();
    await advance(20);
    expect(dlg()).toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });
});

describe('执行后的分支（真实模式下 ?write= 一个都不认）', () => {
  it('状态已变（409 退出码 4）：「配置在你确认之前被改动了，请重新预览」，不再重读', async () => {
    execPlan = { status: 409, body: { ...failEnvelope(['ERROR 在预览之后配置被改动了，请重新预览']), exit_code: 4 } };
    await openConfirm('#/roles?write=reread-fail');
    const readsBefore = countGets('/api/v1/presets');
    await confirmNow();
    expect(dlgText()).toContain('配置在你确认之前被改动了，请重新预览');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(toastText()).toBe('');
    expect(countGets('/api/v1/presets'), '状态已变不重读').toBe(readsBefore);
    expect(bodyText()).not.toContain('已切换');
  });

  it('过期（409、退出码为 null）：「确认已失效（过期、已用过或参数不符），请重新预览」', async () => {
    execPlan = { status: 409, body: failEnvelope(['ERROR 确认号无效、已过期或已用过：请重新预览']) };
    await openConfirm('#/roles');
    await confirmNow();
    const t = dlgText();
    expect(t).toContain('确认已失效（过期、已用过或参数不符），请重新预览');
    expect(t).not.toContain('配置在你确认之前被改动了');
  });

  it('繁忙（503 且查不到操作）：回到可确认，提示「服务繁忙，请稍后再确认」', async () => {
    execPlan = { status: 503, body: failEnvelope(['ERROR 服务繁忙，请稍后重试']) };
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('服务繁忙，请稍后再确认');
    expect(btn(dlg() as HTMLElement, '确认…'), '回到可确认应有 [确认…]').toBeTruthy();
    expect(raws.length).toBe(1);
    expect(raws[0].path).toBe(`/api/v1/operations/${encodeURIComponent(CONFIRMATION)}`);
    expect(toastText()).toBe('');
  });

  it('断线后轮询：执行 reject →「连接中断，正在确认结果…」，[取消] 禁用；轮询到 succeeded 后重读完成、弹轻提示', async () => {
    execPlan = { reject: new Error('连接中断') };
    opPlans = [
      { status: 200, body: operationView('running') },
      { status: 200, body: operationView('succeeded', envelope(null, ['config', 'preset', 'use', 'economy'])) },
    ];
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('连接中断，正在确认结果…');
    expect((btn(dlg() as HTMLElement, '取消') as HTMLButtonElement).disabled, '确认结果中不能取消').toBe(true);
    expect(raws.length).toBe(0);
    await advance(1000);
    expect(raws.length).toBe(1);
    expect(raws[0].path).toBe(`/api/v1/operations/${encodeURIComponent(CONFIRMATION)}`);
    expect(dlgText(), '操作还在 running').toContain('连接中断，正在确认结果…');
    await advance(1000);
    expect(raws.length).toBe(2);
    expect(dlg(), '轮询到终态并重读完成后关框').toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('轮询到 120 秒：119 秒仍不下结论，120 秒进「结果未知，请在历史与审计里核对」', async () => {
    execPlan = { reject: new Error('连接中断') };
    opPlans = [{ status: 200, body: operationView('running') }];
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('连接中断');
    await advance(119000);
    expect(dlgText(), '119 秒仍是 running 时不下结论').toContain('连接中断，正在确认结果…');
    expect(dlgText()).not.toContain('结果未知');
    await advance(1000);
    expect(dlgText(), '120 秒上限到了进「结果未知」，不是失败').toContain('结果未知，请在历史与审计里核对');
    expect(dlgText()).not.toContain('内核拒绝');
    expect(btn(dlg() as HTMLElement, '打开历史')).toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('服务出错（500）：重读后显示失败横幅，原因「服务出错」', async () => {
    execPlan = { status: 500, body: failEnvelope(['ERROR 起不了内核子进程']) };
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('服务出错');
    expect(dlgText()).toContain('起不了内核子进程');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(bodyText()).not.toContain('已切换');
  });

  it('超时（504）：重读后显示失败横幅，原因「超时」', async () => {
    execPlan = { status: 504, body: failEnvelope(['ERROR: 命令超时（90 秒），子进程已结束']) };
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('超时');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(bodyText()).not.toContain('已切换');
  });

  it('部分写入（200 ok:false 退出 1，重读后快照变了）：「已部分写入，结果待核实」', async () => {
    execPlan = { status: 200, body: { ...failEnvelope(['ERROR 内核拒绝：profile step-low 不存在']), exit_code: 1 } };
    readPlan = 'changed';
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('已部分写入，结果待核实');
    expect(btn(dlg() as HTMLElement, '查看历史')).toBeTruthy();
    expect(dlgText()).not.toContain('成功');
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });

  it('内核拒绝（200 ok:false 退出 1，重读后快照没变）：失败横幅，原因「内核拒绝」', async () => {
    execPlan = { status: 200, body: { ...failEnvelope(['ERROR 内核拒绝：profile step-low 不存在']), exit_code: 1 } };
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('内核拒绝');
    expect(dlgText()).not.toContain('已部分写入');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });
});

describe('真实模式门与真实模式下的重读失败', () => {
  it('hash 带 ?write=reread-fail：执行成功照常重读并出轻提示，不出现「重新读取失败」', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles?write=reread-fail');
    await confirmNow();
    expect(bodyText()).toContain('已切换到方案 economy');
    expect(bodyText()).not.toContain('重新读取失败');
    expect(toastText()).toContain('已切换到方案 economy');
  });

  it('hash 带 ?write=reread-fail-exit1：同样照常重读', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles?write=reread-fail-exit1');
    await confirmNow();
    expect(bodyText()).toContain('已切换到方案 economy');
    expect(bodyText()).not.toContain('重新读取失败');
  });

  it('重读的读 reject：「命令已成功，但重新读取失败，请刷新」，不弹轻提示', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    readPlan = 'reject';
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('命令已成功，但重新读取失败，请刷新');
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });

  it('重读的读回 ok:false：同样是「命令已成功，但重新读取失败，请刷新」', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    readPlan = 'fail';
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('命令已成功，但重新读取失败，请刷新');
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });
});

describe('needs_yes：确认框说明为什么要确认（走 notes 一栏）', () => {
  it('有状态读不出来：原因句逐字排在原样路径行之前', async () => {
    previewJson = basePreview(true, { unreadable: ['roles/build（权限不够，读不到）'] });
    await openConfirm('#/roles');
    const notes = Array.from((dlg() as HTMLElement).querySelectorAll('.wf-note')).map((el) => text(el));
    expect(notes.length).toBe(2);
    expect(notes[0]).toBe(REASON);
    expect(notes[1]).toContain('roles/build');
    expect(dlgText()).toContain('影响与风险');
  });

  it('有正在运行的 attempt：只有 running 那行，不加原因句', async () => {
    previewJson = basePreview(true, { running_attempts: ['ui-readonly-api/attempt-001'] });
    await openConfirm('#/roles');
    const t = dlgText();
    expect(t).toContain('有 attempt 正在运行：ui-readonly-api/attempt-001');
    expect(t).toContain('这次改动需要你确认');
    expect(t).not.toContain(REASON);
    expect((dlg() as HTMLElement).querySelectorAll('.wf-note').length).toBe(0);
  });

  it('needs_yes 为假：不出现原因句', async () => {
    previewJson = basePreview(false);
    await openConfirm('#/roles');
    const t = dlgText();
    expect(t).not.toContain(REASON);
    expect(t).not.toContain('影响与风险');
  });
});
