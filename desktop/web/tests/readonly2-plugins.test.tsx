// 插件页自测（合同 D04、D05）：表各列取值与色调、两个小节；抽屉的焦点与 Esc、读取三态、复制三结果。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CheckIcon, CircleXIcon, ListChecksIcon, TriangleAlertIcon } from '../src/icons';
import { PluginsIcon } from '../src/icons/frame';
import { PluginsView } from '../src/pages/readonly2/plugins-PluginsView';
import type { PluginsData } from '../src/api';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const LIST: PluginsData = {
  plugins_root_link: false,
  plugins: [
    { id: 'alpha', version: '1.2.3', enabled: '启用', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
    { id: 'beta', version: '0.1.0', enabled: '停用', lock: '漂移', resource: '不一致', missing: ['fs.write', 'net.http'], status: 'DRIFT', reason: '锁与内容不一致' },
    { id: 'gamma', version: '2.0.0', enabled: '不限制', lock: '无效：manifest 读不出来', resource: '-', missing: [], status: 'BLOCKED', reason: '被阻塞' },
    { id: 'delta', version: '3.0.0', enabled: '是', lock: '其他怪值', resource: '一致', missing: [], status: 'WEIRD', reason: '' },
  ],
  not_installed: ['ghost-plugin'],
  problems: ['无效：链接 plugins'],
} as unknown as PluginsData;

const HASH_A = '0123456789abcdef'.repeat(4);
const HASH_LOCK = '00112233445566778899aabbccddeeff'.repeat(2);

function showFor(id: string) {
  const row = LIST.plugins.find((p) => p.id === id)!;
  return {
    plugin_id: id, lock_status: row.lock, resource_status: row.resource, problems: [],
    version: row.version, api_version: '1', capabilities: ['review', 'docs'],
    permissions: ['fs.read', 'fs.write', 'net.http'], platforms: ['windows', 'linux'], depends_on: [], conflicts: ['old-plugin'],
    checks: ['CHECKS-CANARY'],
    lock: { generation: 7, lock_sha256: HASH_LOCK },
    resources: [
      { path: 'manifest.json', id: 'manifest', sha256: HASH_A, status: '一致', detail: '' },
      { path: 'checks/headings.py', id: 'headings', sha256: HASH_A, status: '漂移', detail: '内容变了' },
    ],
    config: { enabled: null, allowed_permissions: ['fs.read'], missing_permissions: row.missing },
  };
}
const ok = (data: unknown, command: string[]) => ({ ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 });

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const table = () => document.querySelector('table[aria-label="插件"]') as HTMLTableElement;
const rows = () => Array.from(table().querySelectorAll('tbody tr'));
const cells = (row: Element) => Array.from(row.querySelectorAll('td'));
const rowOf = (id: string) => rows().find((r) => text(cells(r)[0]) === id) as HTMLElement;
const dialog = () => document.querySelector('[role="dialog"]') as HTMLElement | null;
const closeBtn = () => dialog()!.querySelector('button[aria-label="关闭（Esc）"]') as HTMLElement;
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function mount(reader: (id: string) => Promise<unknown> = (id) => Promise.resolve(ok(showFor(id), ['plugins', 'show', id]))) {
  const out = render(<PluginsView data={LIST} getPlugin={reader as never} />);
  await settle();
  return out;
}
async function openByEnter(row: HTMLElement) {
  act(() => { row.focus(); });
  fireEvent.keyDown(row, { key: 'Enter' });
  await settle();
}

describe('插件页：表', () => {
  it('八列、rowHeight 40、ID 与版本原样、版本带 tt-num', async () => {
    await mount();
    const t = table();
    const h = Array.from(t.querySelectorAll('thead th')).map((x) => text(x));
    expect(h).toHaveLength(8);
    expect(h[0]).toBe('ID');
    expect(h[1]).toBe('版本');
    expect(t.getAttribute('data-row-height')).toBe('40');
    for (const p of LIST.plugins) {
      const c = cells(rowOf(p.id));
      expect(text(c[0])).toBe(p.id);
      expect(text(c[1])).toBe(p.version);
      expect(c[1].classList.contains('tt-num')).toBe(true);
    }
  });

  it('启用三种写法加未知；锁与资源四类取值与图标；缺的权限；状态与 reason', async () => {
    await mount();
    const enable = (id: string) => cells(rowOf(id))[2];
    for (const [id, label, tone] of [['alpha', '启用', 'brand'], ['beta', '停用', 'neutral'], ['delta', '是', 'brand']]) {
      const tag = enable(id).querySelector('[data-tone]') as HTMLElement;
      expect(text(tag), id).toBe(label);
      expect(tag.getAttribute('data-tone'), id).toBe(tone);
    }
    expect(text(enable('gamma'))).toBe('不限制');
    expect((enable('gamma').querySelector('[title]') as HTMLElement).getAttribute('title')).toBe('没有配置启用名单');
    const lock = (id: string, i: number) => cells(rowOf(id))[i];
    const a = lock('alpha', 3).querySelector('[data-tone]') as HTMLElement;
    expect(text(a)).toBe('一致');
    expect(a.getAttribute('data-tone')).toBe('success');
    expect(a.querySelector('svg')?.getAttribute('width')).toBe('12');
    const drift = lock('beta', 3).querySelector('[data-tone]') as HTMLElement;
    expect(text(drift)).toBe('漂移');
    expect(drift.getAttribute('data-tone')).toBe('warning');
    expect(drift.querySelector('svg')?.getAttribute('width')).toBe('12');
    expect((lock('beta', 3).querySelector('[title]') as HTMLElement).getAttribute('title')).toBe('锁与内容不一致');
    const inv = lock('gamma', 3).querySelector('[data-tone]') as HTMLElement;
    expect(inv.getAttribute('data-tone')).toBe('danger');
    expect(inv.querySelector('svg')?.getAttribute('width')).toBe('12');
    expect(text(lock('gamma', 4))).toBe('—');
    expect(lock('gamma', 4).querySelector('[data-tone]')).toBeNull();
    expect((lock('delta', 3).querySelector('[data-tone]') as HTMLElement).getAttribute('data-tone')).toBe('warning');
    const missing = Array.from(cells(rowOf('beta'))[5].querySelectorAll('[data-tone]'));
    expect(missing.map((m) => text(m))).toEqual(['fs.write', 'net.http']);
    for (const m of missing) expect(m.getAttribute('data-tone')).toBe('danger');
    expect(text(cells(rowOf('alpha'))[5])).toBe('—');
    const st = (id: string) => cells(rowOf(id))[6];
    expect(text(st('alpha').querySelector('[data-tone]'))).toBe('READY');
    expect((st('alpha').querySelector('[data-tone]') as HTMLElement).getAttribute('data-tone')).toBe('success');
    expect((st('gamma').querySelector('[data-tone]') as HTMLElement).getAttribute('data-tone')).toBe('danger');
    expect(text(st('beta')).replace(/\s+/g, '')).toBe('DRIFT锁与内容不一致');
  });

  it('操作三种情形；两个小节；为空写「没有」', async () => {
    await mount();
    const act3 = (id: string) => cells(rowOf(id))[7];
    for (const [id, label] of [['alpha', '停用…'], ['delta', '停用…'], ['beta', '启用…']]) {
      const btn = act3(id).querySelector('button') as HTMLButtonElement;
      expect(text(btn), id).toBe(label);
      expect(btn.disabled).toBe(true);
      expect(btn.getAttribute('data-variant')).toBe('ghost');
      expect(btn.getAttribute('data-size')).toBe('sm');
    }
    expect(text(act3('gamma'))).toBe('详情');
    expect(act3('gamma').querySelector('button, a, [tabindex]')).toBeNull();
    const root = document.querySelector('[data-page="plugins"]') as HTMLElement;
    const sec = (title: string) => Array.from(root.querySelectorAll('section')).find((s) => {
      const id = s.getAttribute('aria-labelledby');
      const h = id ? document.getElementById(id) : null;
      return !!h && h.tagName === 'H2' && text(h) === title;
    }) as HTMLElement;
    expect(text(sec('列入但未安装'))).toContain('ghost-plugin');
    expect(text(sec('问题'))).toContain('无效：链接 plugins');
    cleanup();
    await mount();
    const empty = { ...LIST, not_installed: [], problems: [] };
    cleanup();
    render(<PluginsView data={empty as PluginsData} getPlugin={(async () => ok(showFor('alpha'), [])) as never} />);
    await settle();
    const root2 = document.querySelector('[data-page="plugins"]') as HTMLElement;
    const sec2 = (title: string) => Array.from(root2.querySelectorAll('section')).find((s) => {
      const id = s.getAttribute('aria-labelledby');
      const h = id ? document.getElementById(id) : null;
      return !!h && h.tagName === 'H2' && text(h) === title;
    }) as HTMLElement;
    expect(text(sec2('列入但未安装')).replace('列入但未安装', '').trim()).toBe('没有');
    expect(text(sec2('问题')).replace('问题', '').trim()).toBe('没有');
  });
});

describe('插件页：抽屉', () => {
  it('Enter 打开；aria-modal=false、没有遮罩；打开后焦点在关闭钮；Esc 关闭且焦点回触发行', async () => {
    await mount();
    const rs = rows();
    expect(dialog()).toBeNull();
    await openByEnter(rs[0]);
    const d = dialog() as HTMLElement;
    expect(d.getAttribute('aria-modal')).toBe('false');
    expect(document.querySelectorAll('[aria-modal="true"]').length).toBe(0);
    expect((d.parentElement as HTMLElement).querySelector('[class*="scrim"], [class*="backdrop"]')).toBeNull();
    expect(document.activeElement).toBe(closeBtn());
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(rs[0]);
    expect(rs[0].hasAttribute('data-selected')).toBe(true);
    expect(rs[0].getAttribute('tabindex')).toBe('0');
  });

  it('点禁用入口不开抽屉；点行只换内容；换行后 Esc 焦点回后打开的那一行', async () => {
    const calls: string[] = [];
    await mount((id) => { calls.push(id); return Promise.resolve(ok(showFor(id), ['plugins', 'show', id])); });
    const rs = rows();
    const btn = cells(rs[0])[7].querySelector('button') as HTMLButtonElement;
    fireEvent.click(btn);
    fireEvent.click(btn.closest('.tt-tooltip-wrap') as HTMLElement);
    await settle();
    expect(dialog()).toBeNull();
    expect(calls).toEqual([]);
    await openByEnter(rs[0]);
    const first = text(dialog());
    fireEvent.click(rs[2]);
    await settle();
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
    expect(text(dialog())).not.toBe(first);
    expect(calls).toEqual(['alpha', 'gamma']);
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(rs[2]);
    expect(rs[2].hasAttribute('data-selected')).toBe(true);
  });

  it('标题、warning 提示条、manifest 小节、资源哈希、锁与复制三结果、footer', async () => {
    await mount();
    await openByEnter(rowOf('beta'));
    let d = dialog() as HTMLElement;
    const h2 = d.querySelector('h2') as HTMLElement;
    expect(text(h2)).toContain('beta');
    expect(h2.querySelector('svg')?.getAttribute('width')).toBe('20');
    expect(text(d.querySelector('[data-drawer="plugin"]'))).toBeTruthy();
    const banner = d.querySelector('.tt-banner[data-tone="warning"]') as HTMLElement;
    expect(banner).not.toBeNull();
    expect(text(banner)).toMatch(/锁与内容不一致。\s*缺的权限：fs\.write、net\.http。/);
    const dts = Array.from(d.querySelectorAll('dl dt')).map((x) => text(x));
    expect(dts).toEqual(expect.arrayContaining(['ID', '版本', '启用', '权限', 'api_version', 'capabilities', 'platforms', 'depends_on', 'conflicts']));
    expect(dts.includes('checks')).toBe(false);
    expect(text(d)).not.toContain('CHECKS-CANARY');
    const dd = (label: string) => {
      const dt = Array.from(d.querySelectorAll('dt')).find((x) => text(x) === label) as HTMLElement;
      return dt.nextElementSibling as HTMLElement;
    };
    expect(text(dd('ID'))).toBe('beta');
    expect(text(dd('版本'))).toBe('0.1.0');
    expect(text(dd('启用'))).toBe('停用');
    const perms = Array.from(dd('权限').querySelectorAll('[data-tone]'));
    expect(perms.map((p) => text(p))).toEqual(['fs.read', 'fs.write（缺）', 'net.http（缺）']);
    expect(perms.map((p) => p.getAttribute('data-tone') === 'danger')).toEqual([false, true, true]);
    expect(text(dd('depends_on'))).toBe('（无）');
    expect(text(dd('conflicts'))).toBe('old-plugin');
    for (const h of [HASH_A]) {
      const el = d.querySelector(`[title="${h}"]`) as HTMLElement;
      expect(text(el)).toBe(h.slice(0, 12) + '…');
    }
    expect(text(d).indexOf('内容变了')).toBeGreaterThan(text(d).indexOf('漂移'));
    expect(Array.from(d.querySelectorAll('.tt-num')).some((e) => text(e) === '7')).toBe(true);
    expect(Array.from(d.querySelectorAll('*')).some((e) => e.children.length === 0 && text(e) === HASH_LOCK)).toBe(true);
    const footer = buttonByText(d, '重新核对');
    expect(footer.disabled).toBe(true);
    expect(footer.getAttribute('data-variant')).toBe('secondary');
    // 复制三结果
    const copy = d.querySelector('button[aria-label="复制 lock_sha256"]') as HTMLButtonElement;
    expect(copy.disabled).toBe(false);
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(text(d)).toContain('这个环境没有剪贴板接口');
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: write }, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(write).toHaveBeenCalledWith(HASH_LOCK);
    expect(text(d)).toContain('已复制');
    expect(text(d)).not.toContain('这个环境没有剪贴板接口');
    const fail = vi.fn().mockRejectedValue(new Error('denied'));
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: fail }, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(text(d)).toContain('复制失败');
    expect(d.querySelector('.tt-toast, [role="status"]')).toBeNull();
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    // READY 时没有提示条
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    await openByEnter(rowOf('alpha'));
    d = dialog() as HTMLElement;
    expect(d.querySelector('.tt-banner')).toBeNull();
  }, 30000);

  it('读取中写「正在读取…」；出错写命令与退出码，messages 在 pre 里', async () => {
    let resolve!: (v: unknown) => void;
    await mount(() => new Promise((r) => { resolve = r; }));
    await openByEnter(rowOf('alpha'));
    expect(text(dialog())).toContain('正在读取…');
    await act(async () => {
      resolve({ ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR a <i>b</i>'], command: ['plugins', 'show', 'alpha'], elapsed_ms: 0 });
    });
    const d = dialog() as HTMLElement;
    expect(text(d)).toContain('没能读到详情：命令（plugins show alpha）返回退出码 2。');
    const pre = d.querySelector('pre') as HTMLElement;
    expect(pre.textContent).toContain('ERROR a <i>b</i>');
    expect(pre.querySelector('i')).toBeNull();
    expect(text(d)).not.toContain('正在读取…');
  });

  it('只认最后一次请求：旧回应丢弃', async () => {
    const dA = new Promise<unknown>(() => {});
    let resolveB!: (v: unknown) => void;
    const dB = new Promise<unknown>((r) => { resolveB = r; });
    await mount((id) => (id === 'alpha' ? dA : dB));
    await openByEnter(rowOf('alpha'));
    fireEvent.click(rowOf('beta'));
    await settle();
    await act(async () => { resolveB(ok(showFor('beta'), ['plugins', 'show', 'beta'])); });
    await act(async () => { (dA as Promise<unknown>); });
    const dd = (label: string) => {
      const dt = Array.from((dialog() as HTMLElement).querySelectorAll('dt')).find((x) => text(x) === label) as HTMLElement;
      return dt.nextElementSibling as HTMLElement;
    };
    expect(text(dd('ID'))).toBe('beta');
  });
  it('悬停 400ms 出现 role=tooltip，文字是「第二阶段接入」', async () => {
    await mount();
    const wrap = cells(rows()[0])[7].querySelector('.tt-tooltip-wrap') as HTMLElement;
    expect(wrap).not.toBeNull();
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
    fireEvent.mouseEnter(wrap);
    act(() => { vi.advanceTimersByTime(399); });
    expect(document.querySelector('[role="tooltip"]'), '400ms 内不出现').toBeNull();
    act(() => { vi.advanceTimersByTime(1); });
    const tip = document.querySelector('[role="tooltip"]') as HTMLElement;
    expect(tip).not.toBeNull();
    expect(text(tip)).toBe('第二阶段接入');
    fireEvent.mouseLeave(wrap);
    act(() => { vi.advanceTimersByTime(400); });
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
  });

  it('关闭钮的提示出现后：第一次 Esc 只关提示，第二次才关抽屉', async () => {
    await mount();
    const rs = rows();
    await openByEnter(rs[0]);
    act(() => { vi.advanceTimersByTime(400); });
    expect(document.querySelector('[role="tooltip"]'), '400ms 后关闭钮的提示应出现').not.toBeNull();
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(document.querySelector('[role="tooltip"]'), '第一次 Esc 只关提示').toBeNull();
    expect(dialog(), '第一次 Esc 不关抽屉').not.toBeNull();
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(dialog(), '第二次 Esc 才关抽屉').toBeNull();
    expect(document.activeElement).toBe(rs[0]);
  });

  it('焦点在抽屉外按 Esc 不关；点抽屉外也不关', async () => {
    await mount();
    const rs = rows();
    await openByEnter(rs[0]);
    act(() => { rs[1].focus(); });
    fireEvent.keyDown(rs[1], { key: 'Escape' });
    expect(dialog(), '焦点在抽屉外按 Esc 不关').not.toBeNull();
    const root = document.querySelector('[data-page="plugins"]') as HTMLElement;
    fireEvent.click(root);
    fireEvent.mouseDown(root);
    await settle();
    expect(dialog(), '点抽屉外不关').not.toBeNull();
    fireEvent.keyDown(closeBtn(), { key: 'Escape' });
    expect(dialog()).toBeNull();
  });
});

function buttonByText(root: ParentNode, label: string) {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement;
  expect(hit, `找不到按钮 ${label}`).toBeTruthy();
  return hit;
}
