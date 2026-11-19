// 执行端测试（T060）：服务窗口的「设置」页签在有宿主接口时走新分支（挂载开一次、[打开设置] 再开一次、
// 不调 getState、失败 role=alert 带 reason、没有「没有收到服务的回应」）；没有宿主接口时照旧渲染旧设置页。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

let hostCalls = 0;
let hostAnswer: any = { ok: true };

function installHost() {
  (window as unknown as { themisHost?: unknown }).themisHost = {
    openSettings: async () => {
      hostCalls += 1;
      return hostAnswer;
    },
  };
}
function dropHost() {
  delete (window as unknown as { themisHost?: unknown }).themisHost;
}

beforeEach(async () => {
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
  hostCalls = 0;
  hostAnswer = { ok: true };
});
afterEach(async () => {
  cleanup();
  const sc: any = await import('../src/shellpages/shellContext');
  sc.resetShellStubs();
  dropHost();
  window.location.hash = '';
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
function openSettingsBtn(): HTMLButtonElement {
  const hit = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).filter(
    (b) => textOf(b).indexOf('打开设置') === 0,
  )[0];
  expect(hit, '找不到以「打开设置」开头的按钮').toBeTruthy();
  return hit as HTMLButtonElement;
}

async function renderSettingsPage() {
  const hash = '#/settings?shell=ready';
  window.location.hash = hash;
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
  const ctx: any = await import('../src/shellpages/shellContext');
  let shell: any = null;
  function Grab() {
    shell = ctx.useThemisShell('ready');
    return null;
  }
  const g = render(<Grab />);
  g.unmount();
  const getState = vi.spyOn(shell, 'getState');
  window.location.hash = hash;
  const mod: any = await import('../src/pages/SettingsPage');
  const r = render(<mod.default />);
  await settle();
  return { getState, unmount: r.unmount };
}

describe('T060 有宿主接口：设置页签走新分支', () => {
  it('挂载调一次 openSettings；getState 一次不调；没有「没有收到服务的回应」', async () => {
    installHost();
    const { getState } = await renderSettingsPage();
    expect(hostCalls, '挂载时要调一次 openSettings').toBe(1);
    expect(getState.mock.calls.length, '新分支不调 getState').toBe(0);
    expect(document.body.textContent || '').not.toContain('没有收到服务的回应');
  });

  it('h1 仍是「设置」；点 [打开设置] 再调一次', async () => {
    installHost();
    await renderSettingsPage();
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    fireEvent.click(openSettingsBtn());
    await settle();
    expect(hostCalls).toBe(2);
  });

  it('返回 { ok: false, reason: "unavailable" }：一行 role=alert 带 reason，getState 仍不调', async () => {
    hostAnswer = { ok: false, reason: 'unavailable' };
    installHost();
    const { getState } = await renderSettingsPage();
    const alerts = Array.from(document.querySelectorAll('[role="alert"]')) as HTMLElement[];
    const hit = alerts.filter((a) => (a.textContent || '').indexOf('unavailable') !== -1);
    expect(hit.length, '要有带 reason 的 alert').toBeGreaterThanOrEqual(1);
    expect(getState.mock.calls.length).toBe(0);
    expect(document.body.textContent || '').not.toContain('没有收到服务的回应');
  });
});

describe('T060 没有宿主接口：照旧渲染旧设置页', () => {
  it('h1「设置」、五组 data-settings-group、getState 调一次', async () => {
    dropHost();
    const { getState } = await renderSettingsPage();
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    const groups = Array.from(document.querySelectorAll('[data-settings-group]')).map((g) =>
      g.getAttribute('data-settings-group'),
    );
    expect(groups).toEqual(['repos', 'runtime', 'usage', 'appearance', 'about']);
    expect(getState.mock.calls.length).toBe(1);
  });
});
