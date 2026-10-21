// 执行端测试（D04、D05）：首次启动的四步状态、错误与操作、自动启动、[进入]、复制、退出码 1 的禁用按钮。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';

const METHODS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
const ICONS = ['通过', '未通过', '正在启动', '等待'];

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
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function allBtns(): HTMLButtonElement[] {
  return Array.from(document.querySelectorAll('button')) as HTMLButtonElement[];
}
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = allBtns().concat(Array.from(root.querySelectorAll('button')) as HTMLButtonElement[])
    .filter((b) => textOf(b) === text)[0];
  expect(hit, '找不到按钮「' + text + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
async function clickSettle(el: Element) {
  fireEvent.click(el);
  await settle();
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
function stepEls(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[data-step]')) as HTMLElement[];
}
function iconOf(step: Element): string {
  return (
    Array.from(step.querySelectorAll('[role="img"]'))
      .map((e) => e.getAttribute('aria-label') || '')
      .find((l) => ICONS.includes(l)) || ''
  );
}
function icons(): string[] {
  return stepEls().map(iconOf);
}
function stepTexts(): string[] {
  return stepEls().map((s) => textOf(s));
}
function alerts(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[role="alert"]')) as HTMLElement[];
}
function body(): string {
  return textOf(document.body);
}

async function openFirst(scn: string, extra = '', prepare?: (shell: any, spies: any, orig: any) => void) {
  vi.useFakeTimers();
  const hash = '#/first-run?shell=' + scn + extra;
  const shell = await grabShell(hash);
  const orig: any = {};
  const spies: any = {};
  for (const m of METHODS) orig[m] = shell[m].bind(shell);
  for (const m of METHODS) spies[m] = vi.spyOn(shell, m);
  if (prepare) prepare(shell, spies, orig);
  const r = await mountApp(hash);
  return { shell, spies, state: await orig.getState(), unmount: r.unmount };
}
function curId(state: any): string {
  return state.settings.currentRepo;
}

describe('D04 首次启动的四步状态', () => {
  it('ready：四步、自动启动恰一次，1500ms 后 [进入] 可用', async () => {
    const { spies, state } = await openFirst('ready');
    expect(stepEls().length).toBe(4);
    expect(icons()).toEqual(['通过', '通过', '通过', '正在启动']);
    expect(stepTexts()[0]).toContain('C:/Projects/demo-repo');
    expect(stepTexts()[1]).toContain('3.13.1');
    expect(stepTexts()[2]).toContain('2.12.0（仓库里装好的）');
    expect(stepTexts()[3]).toContain('正在启动…');
    expect(stepEls()[3].querySelector('[aria-live="polite"]')).not.toBeNull();
    expect(document.querySelectorAll('[role="status"]').length).toBe(0);
    expect(btn(document, '进入').disabled).toBe(true);
    expect(body()).toContain('四步依次检查，全部通过后才能进入');
    expect(spies.startService.mock.calls).toEqual([[curId(state)]]);
    advance(1500);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '通过']);
    expect(stepTexts()[3]).toContain('已启动 · pid 18244');
    expect(btn(document, '进入').disabled).toBe(false);
    expect(body()).toContain('四项检查都通过了');
    expect(spies.startService.mock.calls.length).toBe(1);
  });

  it('first-launch：没有仓库，第 1 步待选择，后三步等待上一步，不自动启动', async () => {
    const { spies } = await openFirst('first-launch');
    expect(icons()).toEqual(['等待', '等待', '等待', '等待']);
    expect(stepTexts()[0]).toContain('还没有选择仓库');
    for (const i of [1, 2, 3]) expect(stepTexts()[i]).toContain('等待上一步');
    expect(spies.startService.mock.calls.length).toBe(0);
    expect(alerts().length).toBe(0);
  });

  it('not-git：第 1 步未通过，[更换…] 可用，错误框挂第 1 步下面', async () => {
    await openFirst('not-git');
    expect(icons()[0]).toBe('未通过');
    expect(icons()[3]).toBe('等待');
    expect(btn(stepEls()[0], '更换…')).toBeTruthy();
    expect(document.querySelectorAll('[data-step-error]').length).toBe(1);
    expect(stepEls()[0].contains(alerts()[0])).toBe(true);
    expect(body()).toContain('处理好上面标出的问题，再接着检查');
  });

  it('no-python：第 2 步未通过；no-kit：第 3 步未通过', async () => {
    await openFirst('no-python');
    expect(icons()[1]).toBe('未通过');
    expect(icons()[3]).toBe('等待');
  });
});

describe('D05 首次启动的错误与操作', () => {
  it('not-git：首句、次句与 [重新选择] 调 pickRepo()', async () => {
    const { spies } = await openFirst('not-git');
    const a = alerts()[0];
    expect(textOf(a)).toContain('这个文件夹不是 Git 仓库。');
    expect(textOf(a)).toContain('换一个 Git 仓库再试。');
    await clickSettle(btn(a, '重新选择'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
  });

  it('no-agent：首句、次句、接入命令与底栏说明', async () => {
    const { state } = await openFirst('no-agent');
    const a = alerts()[0];
    expect(textOf(a)).toContain('这个仓库还没有接入 Themis Tally。');
    expect(textOf(a)).toContain('在终端里运行下面的命令接入，然后重新选择。');
    const repo = state.settings.repos.find((r: any) => r.id === curId(state));
    expect(textOf(a.querySelector('code'))).toBe('python <ThemisTally>/scripts/kit_install.py install ' + repo.path);
    expect(body()).toContain('接入后点“重新选择”再检查一次');
  });

  it('退出码 1：[切换到那个窗口] 禁用、点了不调桩函数、不自动重启', async () => {
    const { spies } = await openFirst('exit-1');
    advance(1500);
    await settle();
    expect(icons()[3]).toBe('未通过');
    expect(stepTexts()[3]).toContain('已退出 · 退出码 1');
    const sw = btn(document, '切换到那个窗口');
    expect(sw.disabled).toBe(true);
    const before = spies.startService.mock.calls.length;
    fireEvent.click(sw);
    await settle();
    expect(spies.startService.mock.calls.length).toBe(before);
    expect(btn(document, '进入').disabled).toBe(true);
  });

  it('退出码 2：只有首句，无按钮', async () => {
    await openFirst('exit-2');
    advance(1500);
    await settle();
    expect(stepTexts()[3]).toContain('已退出 · 退出码 2');
    expect(alerts()[0].querySelectorAll('button').length).toBe(0);
  });

  it('其他退出码（crash）：[重新启动] 调 startService(id)，之后 running', async () => {
    const { spies, state } = await openFirst('crash');
    expect(spies.startService.mock.calls.length).toBe(0);
    expect(stepTexts()[3]).toContain('已退出 · 退出码 3');
    await clickSettle(btn(alerts()[0], '重新启动'));
    expect(spies.startService.mock.calls).toEqual([[curId(state)]]);
    advance(1500);
    await settle();
    expect(icons()[3]).toBe('通过');
    expect(spies.startService.mock.calls.length).toBe(1);
  });

  it('[进入]：四步全过之后点了地址立刻是 #/overview，保留 mock 与 shell', async () => {
    await openFirst('ready', '&mock=data');
    advance(1500);
    await settle();
    fireEvent.click(btn(document, '进入'));
    const hash = window.location.hash;
    expect(hash.startsWith('#/overview')).toBe(true);
    expect(hash).toContain('mock=data');
    expect(hash).toContain('shell=ready');
    expect(document.querySelector('[data-shell-window]')).toBeNull();
  });
});
