// App 的外观接线自测（T063 片 B）：桩模式照旧、服务窗口用宿主给的外观起步并跟着事件变、
// 外壳页（设置/首启/服务状态）经桥读外观、标题栏三档保存、卸载退订。
// 不 mock 被测模块：装的是假宿主 / 假外壳对象，断言打在真实的外观写入口（html 属性）与标题栏上。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import App from '../src/App';
import { resetShellBridge } from '../src/shellpages/shellBridge';

function fakeShell(): Record<string, unknown> {
  return {
    getState: vi.fn(() => Promise.resolve({})),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve({})),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => () => {}),
  };
}

// 假宿主：getAppearance 同步回外观，onAppearance 同步回退订，saveTheme 回信封。saveAnswer 为 null 表示没有保存能力。
function makeHost(appearance: unknown, saveAnswer: unknown) {
  const listeners: Array<(a: unknown) => void> = [];
  const saveCalls: unknown[][] = [];
  const offCalls = { count: 0 };
  const host: Record<string, unknown> = {
    getAppearance: appearance === null ? undefined : () => appearance,
    onAppearance: (fn: (a: unknown) => void) => {
      listeners.push(fn);
      return () => {
        offCalls.count += 1;
        listeners.length = 0;
      };
    },
    saveTheme:
      saveAnswer === null
        ? undefined
        : (...args: unknown[]) => {
            saveCalls.push(args);
            return saveAnswer instanceof Error ? Promise.reject(saveAnswer) : Promise.resolve(saveAnswer);
          },
    reauth: () => {},
  };
  return {
    host,
    listeners,
    saveCalls,
    offCalls,
    deliver: (a: unknown) => {
      for (const fn of listeners.slice()) fn(a);
    },
  };
}

function resetRoot() {
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('data-density');
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

function themeTrigger(): HTMLButtonElement {
  const hit = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).filter(
    (b) => (b.getAttribute('aria-label') || '').indexOf('主题：') === 0,
  )[0];
  expect(hit, '找不到主题菜单钮').toBeTruthy();
  return hit as HTMLButtonElement;
}

function themeLabel(): string {
  return (themeTrigger().getAttribute('aria-label') || '').slice('主题：'.length);
}

function pickTheme(label: string) {
  fireEvent.click(themeTrigger());
  const item = (Array.from(document.querySelectorAll('[role="menuitemradio"]')) as HTMLElement[]).filter(
    (el) => ((el.textContent || '').replace(/\s+/g, '')).indexOf(label) !== -1,
  )[0];
  expect(item, `菜单里找不到「${label}」`).toBeTruthy();
  fireEvent.click(item as HTMLElement);
}

beforeEach(async () => {
  window.location.hash = '';
  resetRoot();
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});
afterEach(async () => {
  cleanup();
  delete (window as unknown as { themisShell?: unknown }).themisShell;
  delete (window as unknown as { themisHost?: unknown }).themisHost;
  resetShellBridge();
  resetRoot();
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('桩模式（既没有宿主也没有外壳）照旧', () => {
  it('缺省暗 + 标准：根元素不多属性；标题栏只改内存；不写存储', async () => {
    const r = render(<App />);
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(themeLabel()).toBe('暗');
    pickTheme('亮');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(localStorage.length + sessionStorage.length).toBe(0);
    r.unmount();
  });
});

describe('服务窗口（假宿主给亮 + 紧凑）', () => {
  it('render 一返回就是宿主给的外观（首帧之前写好），标题栏「主题：亮」', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, { ok: true, value: { theme: 'light', density: 'compact' } });
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(themeLabel()).toBe('亮');
    r.unmount();
  });

  it('外观事件逐字段覆盖：合法字段生效，非法字段忽略，实参不是对象整个忽略', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, null);
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    await act(async () => {
      h.deliver({ theme: 'dark', density: 'standard' });
    });
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(themeLabel()).toBe('暗');
    await act(async () => {
      h.deliver({ theme: 'light', density: 'neon' });
    });
    expect(document.documentElement.getAttribute('data-theme'), 'density 非法只忽略那一个字段').toBe('light');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    await act(async () => {
      h.deliver({ theme: 5, density: 'compact' });
    });
    expect(document.documentElement.getAttribute('data-theme'), 'theme 非法只忽略那一个字段').toBe('light');
    expect(document.documentElement.getAttribute('data-density'), '合法的 density 仍生效').toBe('compact');
    await act(async () => {
      h.deliver('nope');
    });
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    r.unmount();
  });

  it('标题栏保存·宿主档 ok:true：saveTheme 恰好一次且只转交 pref，然后才切', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, { ok: true, value: { theme: 'light', density: 'standard' } });
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    pickTheme('亮');
    await settle();
    expect(h.saveCalls).toEqual([['light']]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(themeLabel()).toBe('亮');
    r.unmount();
  });

  it('标题栏保存·宿主档 ok:false：保持原主题、不重试、不弹提示', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, { ok: false, reason: 'write-failed' });
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    pickTheme('亮');
    await settle();
    expect(h.saveCalls.length, '失败不重试').toBe(1);
    expect(document.documentElement.hasAttribute('data-theme'), '保持原主题（暗）').toBe(false);
    expect(themeLabel()).toBe('暗');
    expect((document.body.textContent || '').indexOf('write-failed')).toBe(-1);
    r.unmount();
  });

  it('标题栏保存·宿主档 Promise 被拒：保持原主题', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, new Error('boom'));
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    pickTheme('亮');
    await settle();
    expect(h.saveCalls.length).toBe(1);
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    r.unmount();
  });

  it('宿主没有 saveTheme（旧宿主）：保存落到内存档，不抛错', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, null);
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    pickTheme('亮');
    await settle();
    expect(h.saveCalls.length).toBe(0);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    r.unmount();
  });

  it('卸载退订：退订被调，之后的事件不再到达', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, null);
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    expect(h.offCalls.count).toBe(0);
    r.unmount();
    expect(h.offCalls.count, '卸载时要退订').toBe(1);
    await act(async () => {
      h.deliver({ theme: 'light', density: 'compact' });
    });
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
  });
});

describe('外壳页（十成员假外壳加外观成员）', () => {
  function shellWithAppearance(appearance: unknown) {
    const shell = fakeShell();
    const listeners: Array<(a: unknown) => void> = [];
    shell.getAppearance = () => appearance;
    shell.on = (event: string, fn: (a: unknown) => void) => {
      if (event === 'appearance') listeners.push(fn);
      return () => {
        const at = listeners.indexOf(fn);
        if (at >= 0) listeners.splice(at, 1);
      };
    };
    return {
      shell,
      deliver: (a: unknown) => {
        for (const fn of listeners.slice()) fn(a);
      },
      appearanceListeners: listeners,
    };
  }

  it('初值来自桥；标题栏经 saveSettings({ theme }) 保存一次；事件对齐', async () => {
    const s = shellWithAppearance({ theme: 'dark', density: 'standard' });
    (window as unknown as { themisShell?: unknown }).themisShell = s.shell;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    pickTheme('亮');
    await settle();
    expect((s.shell.saveSettings as ReturnType<typeof vi.fn>).mock.calls).toEqual([[{ theme: 'light' }]]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    await act(async () => {
      s.deliver({ theme: 'dark', density: 'compact' });
    });
    expect(document.documentElement.hasAttribute('data-theme'), '事件以事件里的值为准').toBe(false);
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(s.appearanceListeners.length, '卸载前订阅还在').toBe(1);
    r.unmount();
    expect(s.appearanceListeners.length, '卸载后退订').toBe(0);
  });

  it('旧外壳（只有十个成员）：仍算有外壳、仍走桥档保存，外观能力按没有处理', async () => {
    const shell = fakeShell();
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    pickTheme('亮');
    await settle();
    expect((shell.saveSettings as ReturnType<typeof vi.fn>).mock.calls).toEqual([[{ theme: 'light' }]]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(
      (shell.on as ReturnType<typeof vi.fn>).mock.calls.filter((c: unknown[]) => c[0] === 'appearance').length,
      '没有外观能力就不订',
    ).toBe(0);
    r.unmount();
  });

  it('宿主与外壳同时在：初值、订阅、保存都取宿主，桥那边零次', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, { ok: true, value: { theme: 'dark', density: 'compact' } });
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    const s = shellWithAppearance({ theme: 'dark', density: 'standard' });
    (window as unknown as { themisShell?: unknown }).themisShell = s.shell;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    expect(document.documentElement.getAttribute('data-theme'), '初值取宿主给的 light').toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(s.appearanceListeners.length, '订阅走宿主，不订桥').toBe(0);
    pickTheme('暗');
    await settle();
    expect(h.saveCalls).toEqual([['dark']]);
    expect((s.shell.saveSettings as ReturnType<typeof vi.fn>).mock.calls.length, '桥的保存零次').toBe(0);
    expect(document.documentElement.hasAttribute('data-theme'), 'ok:true 才切（暗是去掉属性）').toBe(false);
    r.unmount();
  });

  it('宿主读回的不是对象：初值落到桥给的外观', async () => {
    const h = makeHost('nope', { ok: true, value: { theme: 'dark', density: 'standard' } });
    (window as unknown as { themisHost?: unknown }).themisHost = h.host;
    const s = shellWithAppearance({ theme: 'light', density: 'compact' });
    (window as unknown as { themisShell?: unknown }).themisShell = s.shell;
    window.location.hash = '#/overview';
    const r = render(<App />);
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(s.appearanceListeners.length, '宿主读不到就订桥').toBe(1);
    r.unmount();
  });
});

describe('静态断言', () => {
  const source = readFileSync(join(process.cwd(), 'src/App.tsx'), 'utf8');

  it('用 useLayoutEffect 写属性，里面同时有 applyTheme 与 applyDensity', () => {
    expect(source).toMatch(/useLayoutEffect\([\s\S]*?applyTheme\([\s\S]*?applyDensity\(/);
  });

  it('原文（含注释）不出现两个属性名与各类禁词', () => {
    for (const bad of ['data-theme', 'data-density', 'themisHost', 'themisShell', 'declare global', 'localStorage', 'sessionStorage']) {
      expect(source.indexOf(bad), `不许出现 ${bad}`).toBe(-1);
    }
    for (const bad of ['window.open', 'window.confirm', 'ServerIcon', 'liveModeIsReal', 'liveClient']) {
      expect(source.indexOf(bad), `不许出现 ${bad}`).toBe(-1);
    }
  });
});
