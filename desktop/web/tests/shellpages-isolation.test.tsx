// 执行端测试（D10 隔离）：外壳窗口与设置页运行时不读 api 模块、不发网络请求、不调 window.open。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import * as api from '../src/api';

vi.mock('../src/api', async (importOriginal) => {
  const actual: any = await importOriginal();
  const out: any = {};
  for (const k of Object.keys(actual)) {
    out[k] = typeof actual[k] === 'function' ? vi.fn(actual[k]) : actual[k];
  }
  return out;
});

const SCEN = ['ready', 'checking', 'first-launch', 'not-git', 'no-agent', 'no-python', 'no-kit', 'exit-1', 'exit-2', 'crash', 'custom'];
const SKIP = ['进入', '打开设置'];

beforeEach(async () => {
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});
afterEach(async () => {
  cleanup();
  const sc: any = await import('../src/shellpages/shellContext');
  sc.resetShellStubs();
  vi.useRealTimers();
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function apiCalled(): string[] {
  return Object.keys(api).filter((k) => vi.isMockFunction((api as any)[k]) && (api as any)[k].mock.calls.length > 0);
}
function clearApi() {
  Object.keys(api).forEach((k) => {
    if (vi.isMockFunction((api as any)[k])) (api as any)[k].mockClear();
  });
}
function inShell(): boolean {
  return /^#\/(first-run|service-status)(\/|\?|$)/.test(window.location.hash);
}
const netCalls: string[] = [];
const saved: Array<[any, string, PropertyDescriptor | undefined]> = [];
function stubAt(target: any, name: string, value: any) {
  saved.push([target, name, Object.getOwnPropertyDescriptor(target, name)]);
  Object.defineProperty(target, name, { value, configurable: true, writable: true });
}
function installNet() {
  netCalls.length = 0;
  for (const n of ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket']) {
    const stub: any = function () {
      netCalls.push(n);
      return n === 'fetch' ? new Promise(() => {}) : undefined;
    };
    stubAt(globalThis, n, stub);
  }
  stubAt(window, 'open', () => {
    netCalls.push('window.open');
    return null;
  });
}
function restoreNet() {
  while (saved.length > 0) {
    const [target, name, desc] = saved.pop() as [any, string, PropertyDescriptor | undefined];
    if (desc) Object.defineProperty(target, name, desc);
    else delete target[name];
  }
}
async function pressAll() {
  const done = new Set<Element>();
  for (let i = 0; i < 4; i += 1) {
    const todo = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).filter(
      (b) => !b.disabled && !done.has(b) && !SKIP.includes(textOf(b)),
    );
    if (todo.length === 0) return;
    for (const b of todo) {
      if (!inShell()) return;
      done.add(b);
      if (!document.body.contains(b)) continue;
      fireEvent.click(b);
      await settle();
    }
  }
}

describe('D10 外壳窗口运行时不读 api 也不连网', () => {
  it('经 App 打开 #/first-run 与 #/service-status 的全部场景：api 与网络替身都是 0 次', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      for (const win of ['first-run', 'service-status']) {
        for (const scn of SCEN) {
          clearApi();
          netCalls.length = 0;
          window.location.hash = '#/' + win + '?shell=' + scn;
          const mod: any = await import('../src/App');
          const r = render(<mod.default />);
          await settle();
          expect(apiCalled(), win + ' ' + scn + ' 挂载后').toEqual([]);
          await pressAll();
          advance(1500);
          await settle();
          await pressAll();
          advance(5000);
          await settle();
          expect(netCalls, win + ' ' + scn + ' 网络替身').toEqual([]);
          r.unmount();
          window.location.hash = '';
        }
      }
    } finally {
      restoreNet();
    }
  }, 120000);

  it('单独渲染 SettingsPage 点遍控件：api 替身 0 次、网络替身 0 次', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      for (const scn of ['ready', 'custom', 'first-launch', 'no-python', 'no-kit']) {
        clearApi();
        netCalls.length = 0;
        window.location.hash = '#/settings?shell=' + scn;
        const mod: any = await import('../src/pages/SettingsPage');
        const r = render(<mod.default />);
        await settle();
        for (let round = 0; round < 3; round += 1) {
          for (const b of Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]) {
            if (!document.body.contains(b)) continue;
            fireEvent.click(b);
            await settle();
          }
        }
        advance(5000);
        await settle();
        expect(apiCalled(), '设置页 ' + scn).toEqual([]);
        expect(netCalls, '设置页 ' + scn + ' 网络替身').toEqual([]);
        r.unmount();
        window.location.hash = '';
      }
    } finally {
      restoreNet();
    }
  }, 120000);

  it('经 App 打开 #/settings：api 只被 getMetaNow、getStatus 调用，没有 getMeta', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      clearApi();
      window.location.hash = '#/settings?shell=ready';
      const mod: any = await import('../src/App');
      render(<mod.default />);
      advance(2000);
      await settle();
      const called = apiCalled();
      expect(called).not.toContain('getMeta');
      for (const k of called) expect(['getMetaNow', 'getStatus']).toContain(k);
      expect(netCalls).toEqual([]);
    } finally {
      restoreNet();
    }
  });
});
