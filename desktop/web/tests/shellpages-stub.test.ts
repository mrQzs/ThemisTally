// 执行端测试（D02）：内存桩的方法、深拷贝、不经计时器兑现、saveSettings 只认约定键、start/restart 幂等与事件、dispose、openExternal。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { render, cleanup } from '@testing-library/react';
import { createShellStub } from '../src/shellpages/shellStub';
import { ThemisShellProvider, resetShellStubs, useThemisShell } from '../src/shellpages/shellContext';
import { SHELL_PID, SHELL_STARTED_AT } from '../src/mock/shell';

const METHODS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(async () => {
  cleanup();
  resetShellStubs();
  vi.useRealTimers();
  window.location.hash = '';
  await new Promise((r) => setTimeout(r, 0));
});

async function rejects(p: Promise<unknown>): Promise<boolean> {
  try {
    await p;
    return false;
  } catch {
    return true;
  }
}
function record(shell: any) {
  const events: any[] = [];
  const off = shell.on('service-state', (e: any) => events.push(e));
  return { events, off };
}
function kindOf(e: any): string {
  const s = e && e.service && typeof e.service === 'object' ? e.service : e;
  if (!s || typeof s !== 'object') return '';
  for (const k of ['kind', 'status', 'state', 'phase', 'type']) {
    if (typeof s[k] === 'string' && ['idle', 'starting', 'running', 'exited'].includes(s[k])) return s[k];
  }
  return '';
}
function kinds(events: any[]): string[] {
  return events.map(kindOf);
}
async function grabShell(hash: string, def = 'ready'): Promise<any> {
  window.location.hash = hash;
  const ctx: any = await import('../src/shellpages/shellContext');
  let got: any = null;
  function Grab() {
    got = ctx.useThemisShell(def);
    return null;
  }
  const r = render(createElement(Grab));
  r.unmount();
  return got;
}

describe('D02 桩的方法、深拷贝与创建时不排计时器', () => {
  it('十个成员加 dispose 都是函数', () => {
    const s = createShellStub('ready');
    for (const m of METHODS.concat(['dispose'])) expect(typeof (s as any)[m], m).toBe('function');
  });

  it('创建与 getState 不排计时器；各方法返回已兑现或已被拒的 Promise', async () => {
    const base = vi.getTimerCount();
    const s = createShellStub('ready');
    expect(vi.getTimerCount()).toBe(base);
    await expect(s.getState()).resolves.toBeTruthy();
    expect(vi.getTimerCount()).toBe(base);
    await expect(s.saveSettings({ theme: 'dark' })).resolves.toBeTruthy();
    await expect(s.saveSettings({ pythonPath: 'C:/x' } as any)).rejects.toBeTruthy();
    await expect(s.openExternal('javascript:alert(1)')).rejects.toBeTruthy();
    expect(vi.getTimerCount(), '读取、保存、被拒之后仍没有计时器').toBe(base);
  });

  it('getState 深拷贝：改返回值不影响桩里的状态', async () => {
    const s = createShellStub('ready');
    const s1 = await s.getState();
    const snap = JSON.parse(JSON.stringify(s1));
    s1.settings.repos[0].name = 'CHANGED';
    s1.settings.repos.pop();
    const s2 = await s.getState();
    expect(s2).not.toBe(s1);
    expect(s2).toEqual(snap);
  });

  it('同一场景同一实例，resetShellStubs 之后换新实例', async () => {
    const a = await grabShell('#/first-run?shell=ready');
    const again = await grabShell('#/first-run?shell=ready');
    expect(again).toBe(a);
    const other = await grabShell('#/first-run?shell=custom');
    expect(other).not.toBe(a);
    resetShellStubs();
    const fresh = await grabShell('#/first-run?shell=ready');
    expect(fresh).not.toBe(a);
  });
});

describe('D02 桩的 saveSettings 只认约定键', () => {
  it('路径键、取值不对、不存在的 id、移除当前仓库都被拒，状态不变', async () => {
    const s = createShellStub('ready');
    const s0 = await s.getState();
    const cur = s0.settings.currentRepo;
    const other = s0.settings.repos.find((r: any) => r.id !== cur)!;
    const bad: any[] = [
      { pythonPath: 'C:/x' },
      { theme: 'blue' },
      { density: 'huge' },
      { removeRepo: 'no-such-id' },
      { removeRepo: other.path },
      { removeRepo: cur },
      { removeTranscriptDir: 'no-such-dir' },
      { resetPython: false },
      { theme: 'light', pythonPath: 'C:/x' },
    ];
    for (const patch of bad) {
      expect(await rejects(s.saveSettings(patch)), JSON.stringify(patch)).toBe(true);
      expect(await s.getState()).toEqual(s0);
    }
  });

  it('约定键保存成功并返回新状态', async () => {
    const s = createShellStub('ready');
    const r1 = await s.saveSettings({ theme: 'light' });
    expect(r1.settings.theme).toBe('light');
    const r2 = await s.saveSettings({ density: 'compact' });
    expect(r2.settings.density).toBe('compact');
    expect(r2.settings.theme).toBe('light');
  });
});

describe('D02 桩的启动、事件与 dispose', () => {
  it('startService 不在列表里的 id 被拒；同步发 starting，1500ms 后 running，幂等', async () => {
    const s = createShellStub('ready');
    const id = (await s.getState()).settings.currentRepo!;
    expect(await rejects(s.startService('no-such-repo'))).toBe(true);
    const { events } = record(s);
    const p1 = s.startService(id);
    expect(kinds(events)).toEqual(['starting']);
    const p2 = s.startService(id);
    await Promise.all([p1, p2]);
    expect(kinds(events)).toEqual(['starting']);
    vi.advanceTimersByTime(1499);
    expect(kinds(events)).toEqual(['starting']);
    vi.advanceTimersByTime(1);
    expect(kinds(events)).toEqual(['starting', 'running']);
    const run = events[1] as any;
    expect(run.pid).toBe(SHELL_PID);
    expect(run.startedAt).toBe(SHELL_STARTED_AT);
  });

  it('取消订阅之后不再收到事件；别的订阅者不受影响', async () => {
    const s = createShellStub('ready');
    const id = (await s.getState()).settings.currentRepo!;
    const a = record(s);
    const b = record(s);
    a.off();
    await s.startService(id);
    vi.advanceTimersByTime(1500);
    expect(a.events).toEqual([]);
    expect(kinds(b.events)).toEqual(['starting', 'running']);
  });

  it('dispose 清掉计时器与监听：之后推进时间也没有新事件', async () => {
    const s = createShellStub('ready');
    const id = (await s.getState()).settings.currentRepo!;
    const { events } = record(s);
    await s.startService(id);
    s.dispose();
    vi.advanceTimersByTime(5000);
    expect(kinds(events)).toEqual(['starting']);
  });

  it('openExternal 只认 http 与 https', async () => {
    const s = createShellStub('ready');
    expect(await rejects(s.openExternal('https://example.com/a'))).toBe(false);
    for (const url of ['javascript:alert(1)', 'ftp://example.com/', 'example.com', '']) {
      expect(await rejects(s.openExternal(url)), url).toBe(true);
    }
  });
});

describe('D01 ThemisShellProvider 与模块导出', () => {
  it('Provider 注入的实例经 useThemisShell 取到', () => {
    const s = createShellStub('ready');
    let got: any = null;
    function C() {
      got = useThemisShell('ready');
      return null;
    }
    render(createElement(ThemisShellProvider, { shell: s }, createElement(C)));
    expect(got).toBe(s);
  });
});
