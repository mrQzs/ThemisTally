// 执行端测试（D06）：服务状态页的内容、重启与跳转、退出码说明共用 exitCodes。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';

const METHODS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];

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
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = (Array.from(root.querySelectorAll('button')) as HTMLButtonElement[]).filter((b) => textOf(b) === text)[0];
  expect(hit, '找不到按钮「' + text + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function h1s(): string[] {
  return Array.from(document.querySelectorAll('h1')).map((h) => textOf(h));
}
function exitCodeEl(): HTMLElement {
  return document.querySelector('[data-exit-code]') as HTMLElement;
}
function body(): string {
  return textOf(document.body);
}
function kindOf(e: any): string {
  const s = e && e.service && typeof e.service === 'object' ? e.service : e;
  return s && typeof s === 'object' && typeof s.kind === 'string' ? s.kind : '';
}
async function grabShell(hash: string, def = 'ready'): Promise<any> {
  window.location.hash = hash;
  const ctx: any = await import('../src/shellpages/shellContext');
  let got: any = null;
  function Grab() {
    got = ctx.useThemisShell(def);
    return null;
  }
  const r = render(<Grab />);
  r.unmount();
  return got;
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const out = render(<App />);
  await settle();
  return out;
}
async function openService(scn: string, extra = '') {
  vi.useFakeTimers();
  const hash = '#/service-status?shell=' + scn + extra;
  const shell = await grabShell(hash);
  let state = await shell.getState();
  if (kindOf(state) !== 'exited' && scn !== 'ready') {
    await shell.restartService();
    vi.advanceTimersByTime(1500);
    state = await shell.getState();
  }
  const spies: any = {};
  for (const m of METHODS) spies[m] = vi.spyOn(shell, m);
  const r = await mountApp(hash);
  return { shell, spies, state, unmount: r.unmount };
}

describe('D06 服务状态页的内容', () => {
  it('退出码 1、2、3 逐个查：h1、data-exit-code、说明、两个按钮、title、不设 role=alert', async () => {
    const ctx: any = await import('../src/shellpages/shellContext');
    const want: Array<[string, number, string]> = [
      ['exit-1', 1, '这个仓库已经在另一个窗口里打开了。'],
      ['exit-2', 2, '应用文件不完整，请重新安装。'],
      ['crash', 3, '本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。'],
    ];
    for (const [scn, code, desc] of want) {
      ctx.resetShellStubs();
      const { unmount } = await openService(scn);
      expect(h1s(), scn).toEqual(['本机服务已停止']);
      expect(textOf(exitCodeEl()), scn).toBe(String(code));
      expect(exitCodeEl().tagName.toLowerCase()).toBe('code');
      expect(body(), scn).toMatch(new RegExp('退出码 ' + code + ' · \\d\\d:\\d\\d:\\d\\d。重启后会重新读取数据。'));
      expect(body(), scn).toContain(desc);
      expect(document.querySelector('svg[width="32"][aria-hidden="true"]'), scn).not.toBeNull();
      expect(btn(document, '重启服务')).toBeTruthy();
      expect(btn(document, '打开设置')).toBeTruthy();
      expect(document.querySelectorAll('[role="alert"]').length, scn).toBe(0);
      expect(document.title).toBe('本机服务已停止 · Themis Tally');
      unmount();
    }
  });

  it('service 不是 exited 时退出码写「—」', async () => {
    await openService('ready');
    expect(textOf(exitCodeEl())).toBe('—');
  });
});

describe('D06 重启与跳转', () => {
  it('[重启服务] 进入加载态，收到 running 才跳回 #/overview', async () => {
    const { spies } = await openService('crash', '&mock=data');
    expect(spies.restartService.mock.calls.length).toBe(0);
    fireEvent.click(btn(document, '重启服务'));
    expect(spies.restartService.mock.calls.length).toBe(1);
    await settle();
    const loading = btn(document, '正在重启…');
    expect(loading.disabled).toBe(true);
    expect(loading.getAttribute('aria-busy')).toBe('true');
    advance(1499);
    await settle();
    expect(window.location.hash.startsWith('#/service-status')).toBe(true);
    advance(1);
    const hash = window.location.hash;
    expect(hash.startsWith('#/overview')).toBe(true);
    expect(hash).toContain('mock=data');
    expect(hash).toContain('shell=crash');
  });

  it('重启后仍是 exited（exit-1）：留在本页，退出码与按钮恢复', async () => {
    await openService('exit-1');
    fireEvent.click(btn(document, '重启服务'));
    await settle();
    advance(1500);
    await settle();
    expect(window.location.hash.startsWith('#/service-status')).toBe(true);
    expect(textOf(exitCodeEl())).toBe('1');
    expect(btn(document, '重启服务').disabled).toBe(false);
  });

  it('[打开设置]：点了地址立刻是 #/settings，保留 mock 与 shell', async () => {
    await openService('exit-1', '&mock=data');
    fireEvent.click(btn(document, '打开设置'));
    const hash = window.location.hash;
    expect(hash.startsWith('#/settings')).toBe(true);
    expect(hash).toContain('mock=data');
    expect(hash).toContain('shell=exit-1');
    expect(h1s()).toEqual(['设置']);
  });
});
