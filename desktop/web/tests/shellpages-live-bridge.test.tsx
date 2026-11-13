// 执行端测试（D02–D08）：外壳页接真实外壳的行为——假外壳优先于桩、成员不全当作没有、卸载退订、
// 真实模式没有外壳时显示「没有连上外壳」、引用稳定。判定用 vi.mock 局部替换 liveModeIsReal；
// 桩的创建次数用 vi.mock 包住 createShellStub 计数。设置页不在本片断言面内（getState 被拒照旧由
// PageFrame 显示通用出错块，不断言它显示「没有连上外壳」，也不写设置页信封断言）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

const modeState = vi.hoisted(() => ({ real: false }));
const stubCalls = vi.hoisted(() => ({ count: 0 }));

vi.mock('../src/live/mode', async (importOriginal) => {
  const actual: any = await importOriginal();
  return { ...actual, liveModeIsReal: () => modeState.real, liveClient: () => null };
});
vi.mock('../src/shellpages/shellStub', async (importOriginal) => {
  const actual: any = await importOriginal();
  const orig = actual.createShellStub;
  return {
    ...actual,
    createShellStub: (scenario: string) => {
      stubCalls.count += 1;
      return orig(scenario);
    },
  };
});

const MEMBERS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
const MIN_STATE = {
  app: { version: '0.0.0', homepage: 'https://example.com/' },
  settings: { repos: [], currentRepo: null, transcriptDirs: [], theme: 'system', density: 'standard' },
  currentRepoCheck: null,
  python: { status: 'ok', source: 'auto', path: 'C:/Python313/python.exe', version: '3.13.1' },
  kit: { status: 'ok', source: 'repo', path: 'C:/kit', version: '2.12.0' },
  service: { kind: 'idle' },
};

function fakeShell(overrides?: Record<string, unknown>): any {
  const shell: Record<string, unknown> = {
    getState: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => () => {}),
  };
  return Object.assign(shell, overrides ?? {});
}
function fullShell(): any {
  const shell = fakeShell();
  expect(MEMBERS.every((m) => typeof shell[m] === 'function'), '假外壳十成员齐全').toBe(true);
  return shell;
}
async function ctx(): Promise<any> {
  return await import('../src/shellpages/shellContext');
}
async function grabVia(context: any): Promise<any> {
  let got: any = null;
  function Grab() {
    got = context.useThemisShell('ready');
    return null;
  }
  const r = render(<Grab />);
  r.unmount();
  expect(got, 'useThemisShell 应返回实例').toBeTruthy();
  return got;
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
async function drainNav() {
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
}
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const out = render(<mod.default />);
  await settle();
  return out;
}

beforeEach(async () => {
  modeState.real = false;
  stubCalls.count = 0;
  window.location.hash = '';
  await drainNav();
});
afterEach(async () => {
  cleanup();
  delete (window as any).themisShell;
  modeState.real = false;
  stubCalls.count = 0;
  try {
    const sc: any = await import('../src/shellpages/shellContext');
    sc.resetShellStubs();
  } catch {
    // 模块不在时，用例本身已经失败
  }
  try {
    const sb: any = await import('../src/shellpages/shellBridge');
    sb.resetShellBridge();
  } catch {
    // 同上
  }
  vi.useRealTimers();
  window.location.hash = '';
  await drainNav();
});

describe('D04 假外壳优先于桩', () => {
  it('十成员齐全的假外壳：经 App 打开首启页与服务状态页、单独渲染 SettingsPage，都调到假对象，桩一次都没创建', async () => {
    vi.useFakeTimers();
    const fake = fullShell();
    (window as any).themisShell = fake;
    let r = await mountApp('#/first-run?shell=crash');
    expect((fake.getState as any).mock.calls.length, '首启页调的是假对象').toBeGreaterThanOrEqual(1);
    expect(stubCalls.count, '真实例优先，不创建桩').toBe(0);
    expect(document.querySelector('.tt-fr__err[role="alert"]'), '假数据没有错误块').toBeNull();
    r.unmount();
    r = await mountApp('#/service-status?shell=exit-1');
    expect((fake.getState as any).mock.calls.length, '服务状态页也调假对象').toBeGreaterThanOrEqual(2);
    expect(stubCalls.count).toBe(0);
    r.unmount();
    const page: any = await import('../src/pages/SettingsPage');
    const r3 = render(<page.default />);
    await settle();
    expect((fake.getState as any).mock.calls.length, '设置页也调假对象').toBeGreaterThanOrEqual(3);
    expect(stubCalls.count).toBe(0);
    r3.unmount();
  });
});

describe('D04 成员不全当作没有', () => {
  it('缺一个成员或某个成员不是函数：回到夹具桩（createShellStub 被调用），页面显示桩的内容', async () => {
    vi.useFakeTimers();
    const bad1 = fullShell();
    delete bad1.on;
    (window as any).themisShell = bad1;
    let r = await mountApp('#/first-run?shell=exit-2');
    expect(stubCalls.count, '缺成员回到桩').toBeGreaterThanOrEqual(1);
    expect(textOf(document.querySelector('h1'))).toContain('欢迎使用 Themis Tally');
    r.unmount();
    const bad2 = fullShell();
    bad2.saveSettings = 'not-a-function';
    (window as any).themisShell = bad2;
    stubCalls.count = 0;
    r = await mountApp('#/service-status?shell=crash');
    expect(stubCalls.count, '非函数成员也回到桩').toBeGreaterThanOrEqual(1);
    expect(textOf(document.querySelector('[data-exit-code]'))).toBe('3');
    r.unmount();
  });
});

describe('D08 卸载退订', () => {
  it('首启页与服务状态页卸载时，on 返回的退订函数各被调用一次', async () => {
    const { FirstRunView } = await import('../src/shellpages/FirstRunView');
    const { ServiceStatusView } = await import('../src/shellpages/ServiceStatusView');
    const off1 = vi.fn();
    const r1 = render(<FirstRunView shell={fakeShell({ on: vi.fn(() => off1) })} navigate={() => {}} />);
    await settle();
    r1.unmount();
    expect(off1, '首启页卸载退订一次').toHaveBeenCalledTimes(1);
    const off2 = vi.fn();
    const r2 = render(<ServiceStatusView shell={fakeShell({ on: vi.fn(() => off2) })} navigate={() => {}} />);
    await settle();
    r2.unmount();
    expect(off2, '服务状态页卸载退订一次').toHaveBeenCalledTimes(1);
  });
});

describe('D04 真实模式没有外壳', () => {
  it('不创建桩、地址里的 shell= 不起作用，首启页与服务状态页显示「没有连上外壳」', async () => {
    vi.useFakeTimers();
    modeState.real = true;
    delete (window as any).themisShell;
    let r = await mountApp('#/first-run?shell=crash');
    expect(stubCalls.count, '真实模式不创建桩').toBe(0);
    const err = document.querySelector('.tt-fr__err[role="alert"]');
    expect(err, '首启页显示错误块').not.toBeNull();
    expect(textOf(err)).toBe('没有连上外壳');
    expect(document.querySelector('[data-step]'), '桩的步骤列表不渲染').toBeNull();
    r.unmount();
    r = await mountApp('#/service-status?shell=exit-1');
    expect(stubCalls.count).toBe(0);
    expect(textOf(document.querySelector('.tt-ss__note')), '说明行位置显示错误').toContain('没有连上外壳');
    expect(textOf(document.querySelector('[data-exit-code]')), 'shell= 不起作用，不是 exit-1 场景').toBe('—');
    r.unmount();
  });
});

describe('D03 引用稳定', () => {
  it('同一个假对象两次取到同一引用，换对象换引用；真实模式下「外壳不可用」两次取到也是同一引用', async () => {
    const context = await ctx();
    const fake = fullShell();
    (window as any).themisShell = fake;
    const a = await grabVia(context);
    const b = await grabVia(context);
    expect(a, '同一对象同一包装引用').toBe(b);
    const other = fullShell();
    (window as any).themisShell = other;
    const c = await grabVia(context);
    expect(c, '不同对象不同包装').not.toBe(a);
    modeState.real = true;
    delete (window as any).themisShell;
    const u1 = await grabVia(context);
    const u2 = await grabVia(context);
    expect(u1, '外壳不可用是模块级单例').toBe(u2);
    expect(u1).not.toBe(a);
  });
});
