// 执行端测试（D03 App 级、D08 主题同步）：两个外壳页整窗渲染、服务窗口不挂载、navigateShell 同步、主题经 App 与标题栏同步。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';

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
  document.documentElement.removeAttribute('data-theme');
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
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
function nav(): HTMLElement | null {
  return document.querySelector('nav[aria-label="主导航"]');
}
function shellWin(): HTMLElement | null {
  return document.querySelector('[data-shell-window]');
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const out = render(<App />);
  await settle();
  return out;
}
function hashTo(hash: string) {
  window.location.hash = hash;
  act(() => {
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

describe('D03 外壳窗口整窗渲染', () => {
  it('#/first-run 与 #/service-status：没有主导航、data-tab 与切换仓库钮，恰一个 h1，Ctrl+1 地址不变', async () => {
    vi.useFakeTimers();
    const cases = [
      { hash: '#/first-run', page: 'first-run', h1: '欢迎使用 Themis Tally', title: '首次启动 · Themis Tally' },
      { hash: '#/service-status', page: 'service-status', h1: '本机服务已停止', title: '本机服务已停止 · Themis Tally' },
    ];
    for (const c of cases) {
      const r = await mountApp(c.hash);
      expect(nav(), c.hash).toBeNull();
      expect(document.querySelector('[data-tab]'), c.hash).toBeNull();
      expect(document.querySelector('button[title="切换仓库"]'), c.hash).toBeNull();
      expect(h1s(), c.hash).toEqual([c.h1]);
      expect(document.title, c.hash).toBe(c.title);
      const win = shellWin();
      expect(win).not.toBeNull();
      expect((win as HTMLElement).getAttribute('data-shell-window')).toBe(c.page);
      const before = window.location.hash;
      fireEvent.keyDown(window, { key: '1', ctrlKey: true });
      await settle();
      expect(window.location.hash, 'Ctrl+1 地址不变').toBe(before);
      expect(shellWin()).not.toBeNull();
      r.unmount();
    }
    vi.useRealTimers();
  });

  it('#/settings 仍是 Tab；#/nope 与 #/first-run-x 仍归总览', async () => {
    let r = await mountApp('#/settings?shell=ready');
    expect(h1s()).toEqual(['设置']);
    expect(document.querySelector('nav[aria-label="主导航"] a[data-tab][aria-current="page"]')).not.toBeNull();
    expect(shellWin()).toBeNull();
    r.unmount();
    for (const hash of ['#/nope', '#/first-run-x', '#/service-status-x']) {
      const rr = await mountApp(hash);
      expect(h1s(), hash).toEqual(['总览']);
      expect(shellWin(), hash).toBeNull();
      rr.unmount();
    }
  });

  it('两种窗口之间手改地址（手动派发 HashChangeEvent），同一地址连派两次不重挂', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview?mock=data');
    const main = document.querySelector('main');
    hashTo('#/overview?mock=data');
    hashTo('#/overview?mock=data');
    expect(document.querySelector('main')).toBe(main);
    hashTo('#/first-run?shell=checking');
    await settle();
    expect(shellWin()).not.toBeNull();
    expect(nav()).toBeNull();
    const win = shellWin();
    hashTo('#/first-run?shell=checking');
    expect(shellWin()).toBe(win);
    hashTo('#/service-status?shell=exit-1');
    await settle();
    expect(shellWin()?.getAttribute('data-shell-window')).toBe('service-status');
    expect(h1s()).toEqual(['本机服务已停止']);
    vi.useRealTimers();
  });
});

describe('D08 主题经 App 与标题栏同步', () => {
  it('在设置页选亮：标题栏触发钮变「主题：亮」、data-theme 为 light、saveSettings({ theme: light }) 恰一次', async () => {
    vi.useFakeTimers();
    const shell = await (async () => {
      window.location.hash = '#/settings?shell=ready';
      const ctx: any = await import('../src/shellpages/shellContext');
      let got: any = null;
      function Grab() {
        got = ctx.useThemisShell('ready');
        return null;
      }
      const r = render(<Grab />);
      r.unmount();
      return got;
    })();
    const spy = vi.spyOn(shell, 'saveSettings');
    await mountApp('#/settings?shell=ready&mock=data');
    const trigger = document.querySelector('header button[aria-haspopup="menu"][aria-label^="主题："]') as HTMLElement;
    expect(trigger.getAttribute('aria-label')).toBe('主题：暗');
    expect(document.documentElement.getAttribute('data-theme')).toBeNull();
    const themeRadio = Array.from(
      (grpAppearance().querySelector('[role="radiogroup"][aria-label="主题"]') as HTMLElement).querySelectorAll('[role="radio"]'),
    ).find((b) => textOf(b) === '亮') as HTMLElement;
    fireEvent.click(themeRadio);
    await settle();
    expect(trigger.getAttribute('aria-label')).toBe('主题：亮');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(spy.mock.calls).toEqual([[{ theme: 'light' }]]);
    function grpAppearance(): HTMLElement {
      return document.querySelector('[data-settings-group="appearance"]') as HTMLElement;
    }
  });

  it('去过 #/first-run 再回 #/settings 主题不变，不写存储', async () => {
    vi.useFakeTimers();
    await mountApp('#/settings?shell=ready&mock=data');
    const trigger = document.querySelector('header button[aria-haspopup="menu"][aria-label^="主题："]') as HTMLElement;
    fireEvent.click(trigger);
    const menu = document.querySelector('[role="menu"]') as HTMLElement;
    const light = Array.from(menu.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')).find((i) => textOf(i) === '亮') as HTMLElement;
    fireEvent.click(light);
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    hashTo('#/first-run?shell=checking');
    await settle();
    expect(shellWin()).not.toBeNull();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    hashTo('#/settings?shell=ready&mock=data');
    await settle();
    expect(shellWin()).toBeNull();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });
});
