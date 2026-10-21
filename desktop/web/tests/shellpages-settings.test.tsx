// 执行端测试（D07、D08、D09）：设置页的结构与数据取自桩、仓库/运行环境/用量三组、外观（无 Provider 本地状态）、关于与对话框。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

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
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = (Array.from(root.querySelectorAll('button')) as HTMLButtonElement[]).filter((b) => textOf(b) === text)[0];
  expect(hit, '找不到按钮「' + text + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function btns(root: ParentNode, text: string): HTMLButtonElement[] {
  return (Array.from(root.querySelectorAll('button')) as HTMLButtonElement[]).filter((b) => textOf(b) === text);
}
async function clickSettle(el: Element) {
  fireEvent.click(el);
  await settle();
}
function grp(name: string): HTMLElement {
  return document.querySelector('[data-settings-group="' + name + '"]') as HTMLElement;
}
function repoRows(): HTMLElement[] {
  return Array.from(grp('repos').querySelectorAll('[data-repo-id]')) as HTMLElement[];
}
function alertsIn(root: ParentNode): HTMLElement[] {
  return Array.from(root.querySelectorAll('[role="alert"]')) as HTMLElement[];
}
function radio(group: HTMLElement, label: string, text: string): HTMLButtonElement {
  const g = group.querySelector('[role="radiogroup"][aria-label="' + label + '"]') as HTMLElement;
  const hit = Array.from(g.querySelectorAll('[role="radio"]')).find((b) => textOf(b) === text) as HTMLButtonElement;
  expect(hit, '「' + label + '」里找不到「' + text + '」').toBeTruthy();
  return hit;
}
function checkedOf(group: HTMLElement, label: string): string {
  const g = group.querySelector('[role="radiogroup"][aria-label="' + label + '"]') as HTMLElement;
  const hit = Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true');
  return hit ? textOf(hit) : '';
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
async function openSettings(scn = 'ready', prepare?: (shell: any, spies: any, orig: any) => void) {
  vi.useFakeTimers();
  const hash = '#/settings?shell=' + scn;
  const shell = await grabShell(hash);
  const orig: any = {};
  for (const m of METHODS) orig[m] = shell[m].bind(shell);
  const state = await orig.getState();
  const spies: any = {};
  for (const m of METHODS) spies[m] = vi.spyOn(shell, m);
  if (prepare) prepare(shell, spies, orig);
  window.location.hash = hash;
  const mod: any = await import('../src/pages/SettingsPage');
  const r = render(<mod.default />);
  await settle();
  return { shell, spies, state, unmount: r.unmount };
}

describe('D07 设置页的结构与数据取自桩', () => {
  it('h1「设置」、恰一个 data-page-state=data、根 data-page=settings、五个 section 与 h2', async () => {
    const { spies } = await openSettings('ready');
    expect(document.querySelectorAll('[data-page-state]').length).toBe(1);
    expect((document.querySelector('[data-page-state]') as HTMLElement).getAttribute('data-page-state')).toBe('data');
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    expect(document.querySelectorAll('h1').length).toBe(1);
    const root = document.querySelector('[data-page="settings"]') as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.querySelector('h1')).toBeNull();
    const groups = Array.from(document.querySelectorAll('[data-settings-group]'));
    expect(groups.map((g) => g.getAttribute('data-settings-group'))).toEqual(['repos', 'runtime', 'usage', 'appearance', 'about']);
    expect(groups.map((g) => textOf(g.querySelector('h2')))).toEqual(['仓库', '运行环境', '规划端用量', '外观', '关于']);
    expect(textOf(document.body)).toContain('设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置');
    expect(spies.getState.mock.calls.length).toBe(1);
  });

  it('getState 被拒：通用出错块「没有收到服务的回应」', async () => {
    await openSettings('ready', (_s, sp) => {
      sp.getState.mockRejectedValue(new Error('boom'));
    });
    expect((document.querySelector('[data-page-state]') as HTMLElement).getAttribute('data-page-state')).toBe('error');
    expect(textOf(document.body)).toContain('没有收到服务的回应');
  });
});

describe('D07 仓库组', () => {
  it('表头、两行、当前仓库带「当前」与「现在」、其他用相对时间且 title 写本地时间与 UTC', async () => {
    const { state } = await openSettings('ready');
    const g = grp('repos');
    expect(Array.from(g.querySelectorAll('th')).map((th) => textOf(th))).toEqual(['名称', '路径', '上次打开', '操作']);
    const cur = repoRows().find((r) => r.getAttribute('data-repo-id') === state.settings.currentRepo)!;
    expect(textOf(cur)).toContain('当前');
    expect(textOf(cur)).toContain('现在');
    const other = state.settings.repos.find((r: any) => r.id !== state.settings.currentRepo);
    const orow = repoRows().find((r) => r.getAttribute('data-repo-id') === other.id)!;
    expect(textOf(orow)).toMatch(/(秒|分钟|小时|天)前/);
    const titled = Array.from(orow.querySelectorAll('[title]')).map((e) => e.getAttribute('title') || '');
    expect(titled.some((t) => t.includes('UTC') && t.includes(other.lastOpened))).toBe(true);
  });

  it('当前仓库移除是禁用按钮；其他 [从列表移除] 调 saveSettings({ removeRepo: id })', async () => {
    const { spies, state } = await openSettings('ready');
    const cur = repoRows().find((r) => r.getAttribute('data-repo-id') === state.settings.currentRepo)!;
    const dis = btn(cur, '从列表移除');
    expect(dis.disabled).toBe(true);
    fireEvent.click(dis);
    await settle();
    expect(spies.saveSettings.mock.calls.length).toBe(0);
    const other = state.settings.repos.find((r: any) => r.id !== state.settings.currentRepo);
    await clickSettle(btn(repoRows().find((r) => r.getAttribute('data-repo-id') === other.id)!, '从列表移除'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ removeRepo: other.id }]]);
    expect(repoRows().map((r) => r.getAttribute('data-repo-id'))).toEqual([state.settings.currentRepo]);
  });

  it('[添加仓库…] 调 pickRepo()，saved 表里多一行', async () => {
    const { spies, state } = await openSettings('ready');
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
    const r = await spies.pickRepo.mock.results[0].value;
    expect(r.kind).toBe('saved');
    expect(repoRows().length).toBe(state.settings.repos.length + 1);
  });
});

describe('D07 运行环境与规划端用量', () => {
  it('两个 [更改…] 依次调 pickPython()、pickKit()；[恢复自动检测] 只在 custom 出现', async () => {
    const { spies } = await openSettings('ready');
    expect(textOf(grp('runtime'))).toContain('自动检测 · 3.13.1');
    expect(textOf(grp('runtime'))).toContain('仓库里装好的 · 2.12.0');
    expect(btns(grp('runtime'), '恢复自动检测').length).toBe(0);
    const change = btns(grp('runtime'), '更改…');
    expect(change.length).toBe(2);
    await clickSettle(change[0]);
    expect([spies.pickPython.mock.calls.length, spies.pickKit.mock.calls.length]).toEqual([1, 0]);
  });

  it('custom：[恢复自动检测] 依次调 saveSettings，用返回值更新', async () => {
    const { spies } = await openSettings('custom');
    expect(textOf(grp('runtime'))).toContain('手动指定 · 3.12.4');
    await clickSettle(btns(grp('runtime'), '恢复自动检测')[0]);
    expect(spies.saveSettings.mock.calls).toEqual([[{ resetPython: true }]]);
    expect(btns(grp('runtime'), '恢复自动检测').length).toBe(1);
  });

  it('用量：ready「未设置（可选）」、无输入框；[选择目录…] 调 pickTranscriptDir()', async () => {
    const { spies } = await openSettings('ready');
    expect(textOf(grp('usage'))).toContain('未设置（可选）');
    expect(grp('usage').querySelectorAll('input, textarea, select').length).toBe(0);
    await clickSettle(btn(grp('usage'), '选择目录…'));
    expect(spies.pickTranscriptDir.mock.calls.length).toBe(1);
    expect(textOf(grp('usage'))).not.toContain('未设置（可选）');
  });

  it('保存被拒：本组顶部 danger Banner「没能保存：…」，状态不变', async () => {
    await openSettings('custom', (_s, sp) => {
      sp.saveSettings.mockRejectedValue(new Error('磁盘已满'));
    });
    await clickSettle(btns(grp('runtime'), '恢复自动检测')[0]);
    const a = alertsIn(grp('runtime'));
    expect(a.length).toBe(1);
    expect(textOf(a[0]).startsWith('没能保存：')).toBe(true);
    expect(textOf(grp('runtime'))).toContain('手动指定 · 3.12.4');
  });
});

describe('D08 外观（无 Provider 时退回本地状态）', () => {
  it('主题分段：点击切换 aria-checked、调 saveSettings({ theme })', async () => {
    const { spies } = await openSettings('ready');
    const g = grp('appearance');
    expect(checkedOf(g, '主题')).toBe('暗');
    await clickSettle(radio(g, '主题', '亮'));
    expect(checkedOf(grp('appearance'), '主题')).toBe('亮');
    expect(spies.saveSettings.mock.calls).toEqual([[{ theme: 'light' }]]);
  });

  it('密度：标准/紧凑，点击只调 saveSettings({ density })；caption', async () => {
    const { spies } = await openSettings('ready');
    const g = grp('appearance');
    expect(checkedOf(g, '密度')).toBe('标准');
    expect(textOf(g)).toContain('紧凑：表格行高 32');
    await clickSettle(radio(g, '密度', '紧凑'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ density: 'compact' }]]);
    expect(checkedOf(grp('appearance'), '密度')).toBe('紧凑');
  });
});

describe('D09 关于与外部链接', () => {
  it('版本与 [开源许可清单] 对话框（两项文字，不做链接）', async () => {
    await openSettings('ready');
    const g = grp('about');
    expect(textOf(g)).toContain('版本 0.0.0');
    expect(textOf(g)).toContain('Themis Tally · 参验');
    await clickSettle(btn(g, '开源许可清单'));
    const dlg = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dlg).not.toBeNull();
    const t = textOf(dlg);
    for (const lit of ['Lucide', '1.59.0', 'ISC', 'Sarasa Gothic', '0.36.0', 'SIL OFL 1.1', 'licenses/OFL.txt']) {
      expect(t, lit).toContain(lit);
    }
    expect(dlg.querySelectorAll('a').length).toBe(0);
    fireEvent.keyDown(dlg, { key: 'Escape' });
    await settle();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });

  it('[项目主页]：先确认（openExternal 0 次），[打开] 恰调一次', async () => {
    const { spies, state } = await openSettings('ready');
    const url = state.app.homepage;
    await clickSettle(btn(grp('about'), '项目主页'));
    const dlg = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(textOf(dlg)).toContain('在系统浏览器中打开？');
    expect(textOf(dlg.querySelector('code'))).toBe(url);
    expect(spies.openExternal.mock.calls.length).toBe(0);
    await clickSettle(btn(dlg, '取消'));
    expect(spies.openExternal.mock.calls.length).toBe(0);
    await clickSettle(btn(grp('about'), '项目主页'));
    await clickSettle(btn(document.querySelector('[role="dialog"]') as HTMLElement, '打开'));
    expect(spies.openExternal.mock.calls).toEqual([[url]]);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });

  it('homepage 不是 http(s)：没有 [项目主页] 按钮，网址只作文字', async () => {
    await openSettings('ready', (_s, sp, orig) => {
      sp.getState.mockImplementation(async () => {
        const st = await orig.getState();
        st.app.homepage = 'ftp://example.com/x';
        return st;
      });
    });
    expect(btns(grp('about'), '项目主页').length).toBe(0);
    expect(textOf(grp('about'))).toContain('ftp://example.com/x');
  });
});
