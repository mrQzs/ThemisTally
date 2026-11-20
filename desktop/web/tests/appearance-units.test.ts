// 外观单元自测（T063 片 B）：applyDensity 的属性写法、Table.css 三条紧凑规则、
// 外壳桥与宿主的外观三件套（能力判据、逐字段校验、退订真的能退）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { applyDensity } from '../src/shell/theme';
import {
  SHELL_MEMBERS,
  resetShellBridge,
  shellAppearanceNow,
  shellBridgeInstance,
  shellOnAppearance,
} from '../src/shellpages/shellBridge';
import { hostGetAppearance, hostOnAppearance, hostSaveTheme } from '../src/live/hostSettings';

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

beforeEach(() => {
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('data-density');
});
afterEach(() => {
  delete (window as unknown as { themisShell?: unknown }).themisShell;
  delete (window as unknown as { themisHost?: unknown }).themisHost;
  resetShellBridge();
});

describe('applyDensity', () => {
  it('紧凑写 compact、标准去掉属性；重复写幂等', () => {
    applyDensity('compact');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    applyDensity('compact');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    applyDensity('standard');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    applyDensity('standard');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
  });

  it('只碰 html 的这一个属性：不加类、不写内联样式、不动 body、不写存储', () => {
    applyDensity('compact');
    expect(document.documentElement.getAttribute('style')).toBeNull();
    expect(document.documentElement.className).toBe('');
    expect(document.body.hasAttribute('data-density')).toBe(false);
    expect(document.body.getAttribute('style')).toBeNull();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});

describe('Table.css 紧凑规则', () => {
  const css = readFileSync(join(process.cwd(), 'src/components/Table.css'), 'utf8');
  const compactLines = css.split(/\r?\n/).filter((l) => l.indexOf(':root[data-density="compact"]') !== -1);

  it('恰好三条紧凑规则：40/44/52 各降 8 到 32/36/44', () => {
    expect(compactLines.length).toBe(3);
    const want = ['40', '44', '52'];
    const px = ['32px', '36px', '44px'];
    compactLines.forEach((line, i) => {
      expect(line).toMatch(
        new RegExp(
          `:root\\[data-density="compact"\\]\\s*\\.tt-table\\[data-row-height="${want[i]}"\\]\\s*td\\s*\\{\\s*height:\\s*${px[i]};`,
        ),
      );
    });
  });

  it('每条同一行带出处注释，且只作用于 td（不碰表头）', () => {
    for (const line of compactLines) {
      expect(line, '同一行要带非空的出处注释').toMatch(/\/\*[^*]+\*\//);
      expect(line.split('{')[0], '不许匹配表头 th').not.toMatch(/\bth\b/);
    }
  });

  it('紧凑规则加在现有三条行高规则之后；标准规则照旧', () => {
    expect(css.indexOf('.tt-table[data-row-height="40"] td { height: 40px; }')).toBeGreaterThanOrEqual(0);
    expect(css.indexOf(':root[data-density="compact"]')).toBeGreaterThan(
      css.indexOf('.tt-table[data-row-height="40"] td'),
    );
    for (const h of ['40px', '44px', '52px']) {
      expect(css).toContain(`height: ${h};`);
    }
  });
});

describe('shellAppearanceNow / shellOnAppearance', () => {
  it('十成员齐全且 getAppearance 是函数：同步读透传，订阅经原对象的 on(appearance)，退订真的能退', () => {
    const shell = fakeShell();
    const getAppearance = vi.fn(() => ({ theme: 'light', density: 'compact' }));
    const listeners: Array<(a: unknown) => void> = [];
    const on = vi.fn((event: string, fn: (a: unknown) => void) => {
      listeners.push(fn);
      return () => {
        const at = listeners.indexOf(fn);
        if (at >= 0) listeners.splice(at, 1);
      };
    });
    shell.getAppearance = getAppearance;
    shell.on = on;
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    expect(shellAppearanceNow()).toEqual({ theme: 'light', density: 'compact' });
    expect(getAppearance.mock.calls.length).toBe(1);
    const heard: unknown[] = [];
    const off = shellOnAppearance((a) => heard.push(a));
    expect(on.mock.calls.length).toBe(1);
    expect(on.mock.calls[0][0]).toBe('appearance');
    expect(listeners.length, '原对象上真的挂上了监听').toBe(1);
    listeners.slice().forEach((fn) => fn({ theme: 'dark', density: 'standard' }));
    expect(heard).toEqual([{ theme: 'dark', density: 'standard' }]);
    off();
    expect(listeners.length, '退订时原对象上的监听被摘掉').toBe(0);
    listeners.slice().forEach((fn) => fn({ theme: 'light', density: 'compact' }));
    expect(heard.length, '退订之后不再收').toBe(1);
  });

  it('退订之后监听不再收到事件：底层 on 回的是空退订也不漏', () => {
    const shell = fakeShell();
    const listeners: Array<(a: unknown) => void> = [];
    shell.getAppearance = () => ({ theme: 'dark', density: 'standard' });
    shell.on = (_event: string, fn: (a: unknown) => void) => {
      listeners.push(fn);
      return () => {};
    };
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    const heard: unknown[] = [];
    const off = shellOnAppearance((a) => heard.push(a));
    listeners.slice().forEach((fn) => fn({ theme: 'light', density: 'compact' }));
    off();
    listeners.slice().forEach((fn) => fn({ theme: 'dark', density: 'standard' }));
    expect(heard).toEqual([{ theme: 'light', density: 'compact' }]);
  });

  it('只有十个成员的旧外壳：仍算有外壳，外观能力按没有处理', () => {
    const shell = fakeShell();
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    expect(shellBridgeInstance(), '十成员齐全的旧壳仍被认作有外壳').not.toBeNull();
    expect(shellAppearanceNow()).toBeNull();
    const off = shellOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(shell.on.mock.calls.length, '没有能力就不调 on').toBe(0);
    expect(() => off()).not.toThrow();
  });

  it('getAppearance 存在但不是函数：不调，回 null / 空退订', () => {
    const shell = fakeShell();
    shell.getAppearance = 42;
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    expect(shellAppearanceNow()).toBeNull();
    expect(typeof shellOnAppearance(() => {})).toBe('function');
  });

  it('getAppearance 抛错：同步读回 null，不抛到调用方', () => {
    const shell = fakeShell();
    shell.getAppearance = () => {
      throw new Error('boom');
    };
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    expect(shellAppearanceNow()).toBeNull();
  });

  it('回值不是对象回 null；字段非法只把那一个字段取缺省', () => {
    for (const bad of [() => null, () => undefined, () => 'x', () => 5]) {
      const shell = fakeShell();
      shell.getAppearance = bad;
      (window as unknown as { themisShell?: unknown }).themisShell = shell;
      expect(shellAppearanceNow()).toBeNull();
      resetShellBridge();
    }
    const neon = fakeShell();
    neon.getAppearance = () => ({ theme: 'neon' });
    (window as unknown as { themisShell?: unknown }).themisShell = neon;
    expect(shellAppearanceNow()).toEqual({ theme: 'dark', density: 'standard' });
    resetShellBridge();
    const noDensity = fakeShell();
    noDensity.getAppearance = () => ({ theme: 'light', density: null });
    (window as unknown as { themisShell?: unknown }).themisShell = noDensity;
    expect(shellAppearanceNow()).toEqual({ theme: 'light', density: 'standard' });
  });

  it('on(appearance) 抛错：回空退订函数，不抛', () => {
    const shell = fakeShell();
    shell.getAppearance = () => ({ theme: 'dark', density: 'standard' });
    shell.on = () => {
      throw new Error('no-events');
    };
    (window as unknown as { themisShell?: unknown }).themisShell = shell;
    const off = shellOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(() => off()).not.toThrow();
  });

  it('一个成员都没有时：不算有外壳，外观能力也没有', () => {
    expect(shellBridgeInstance()).toBeNull();
    expect(shellAppearanceNow()).toBeNull();
    expect(typeof shellOnAppearance(() => {})).toBe('function');
    expect(SHELL_MEMBERS.length).toBe(10);
  });
});

describe('hostGetAppearance / hostOnAppearance / hostSaveTheme', () => {
  function installHost(host: Record<string, unknown>) {
    (window as unknown as { themisHost?: unknown }).themisHost = host;
  }

  it('三个函数齐全：读透传、订阅可退订、保存恰好转交 pref 一个实参且信封原样', async () => {
    const saveCalls: unknown[][] = [];
    const offs: unknown[] = [];
    const heard: unknown[] = [];
    installHost({
      getAppearance: () => ({ theme: 'system', density: 'compact' }),
      onAppearance: (fn: unknown) => {
        offs.push(fn);
        return () => {
          offs.length = 0;
        };
      },
      saveTheme: (...args: unknown[]) => {
        saveCalls.push(args);
        return Promise.resolve({ ok: true, value: { theme: args[0], density: 'standard' } });
      },
    });
    expect(hostGetAppearance()).toEqual({ theme: 'system', density: 'compact' });
    const off = hostOnAppearance((a) => heard.push(a));
    expect(offs.length).toBe(1);
    (offs[0] as (a: unknown) => void)({ theme: 'dark', density: 'compact' });
    expect(heard).toEqual([{ theme: 'dark', density: 'compact' }]);
    off();
    const saved = hostSaveTheme('light');
    expect(saved).toBeInstanceOf(Promise);
    expect(await saved).toEqual({ ok: true, value: { theme: 'light', density: 'standard' } });
    expect(saveCalls).toEqual([['light']]);
  });

  it('旧宿主（只有 reauth）：读回 null、订阅空退订、保存回 null，都不被调', () => {
    const reauth = vi.fn();
    installHost({ reauth });
    expect(hostGetAppearance()).toBeNull();
    const off = hostOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(() => off()).not.toThrow();
    expect(hostSaveTheme('dark')).toBeNull();
    expect(reauth.mock.calls.length).toBe(0);
  });

  it('getAppearance 缺/不是函数/抛错/回非对象/字段非法：分别回 null 或缺省', () => {
    installHost({ openSettings: () => {} });
    expect(hostGetAppearance()).toBeNull();
    installHost({ getAppearance: 42 });
    expect(hostGetAppearance()).toBeNull();
    installHost({
      getAppearance: () => {
        throw new Error('boom');
      },
    });
    expect(hostGetAppearance()).toBeNull();
    installHost({ getAppearance: () => 'nope' });
    expect(hostGetAppearance()).toBeNull();
    installHost({ getAppearance: () => ({ theme: 'neon', density: 'compact' }) });
    expect(hostGetAppearance()).toEqual({ theme: 'dark', density: 'compact' });
    installHost({ getAppearance: () => ({ theme: 'light', density: 9 }) });
    expect(hostGetAppearance()).toEqual({ theme: 'light', density: 'standard' });
  });

  it('saveTheme 抛错回 null；onAppearance 回的不是函数或抛错都回空退订', async () => {
    installHost({
      saveTheme: () => {
        throw new Error('boom');
      },
    });
    expect(hostSaveTheme('dark')).toBeNull();
    installHost({ onAppearance: () => 42 });
    expect(typeof hostOnAppearance(() => {})).toBe('function');
    installHost({
      onAppearance: () => {
        throw new Error('boom');
      },
    });
    expect(typeof hostOnAppearance(() => {})).toBe('function');
    installHost({ saveTheme: () => Promise.reject(new Error('later')) });
    const saved = hostSaveTheme('dark');
    expect(saved).toBeInstanceOf(Promise);
    await expect(saved).rejects.toThrow('later');
  });
});
