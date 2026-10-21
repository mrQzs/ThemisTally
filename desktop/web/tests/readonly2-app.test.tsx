// 四页经 ?mock= 的 App 级自测（合同 D08、D09 的过渡部分）：五态、出错块的命令与报错原文、写入口个数。
import { cleanup, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import App from '../src/App';

afterEach(() => {
  cleanup();
  window.location.hash = '';
});

const PAGES = [
  { id: 'secrets', title: '凭据', cmd: 'config show', empty: '还没有要检查的凭据变量', refresh: '重新检查' },
  { id: 'logs', title: '日志与用量', cmd: 'logs usage', empty: null, refresh: '刷新' },
  { id: 'plugins', title: '插件', cmd: 'plugins list', empty: '还没有插件', refresh: '刷新' },
  { id: 'history', title: '历史与审计', cmd: 'config history', empty: '还没有配置历史', refresh: '刷新' },
];

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const out = render(<App />);
  await settle();
  return out;
}
function pageRoot() {
  const nodes = document.querySelectorAll('[data-page-state]');
  expect(nodes.length, '整页恰一个 data-page-state').toBe(1);
  return nodes[0] as HTMLElement;
}
function disabledWrites() {
  return Array.from(document.querySelectorAll('main button:disabled, [role="dialog"] button:disabled'))
    .filter((b) => text(b) !== '重新连接');
}

describe('四页五态（经 ?mock=）', () => {
  it('data：四页都是 data，视图根在，整页恰一个 data-page-state', async () => {
    for (const p of PAGES) {
      await mountApp(`#/${p.id}?mock=data`);
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('data');
      expect(text(document.querySelector('h1'))).toBe(p.title);
      expect(document.querySelector(`[data-page="${p.id}"]`), p.id).toBeTruthy();
      expect(document.querySelectorAll('[data-page]').length).toBe(1);
      cleanup();
    }
  }, 60000);

  it('empty：凭据、插件、历史显示各自的空态标题；日志与用量仍是 data', async () => {
    for (const p of PAGES) {
      await mountApp(`#/${p.id}?mock=empty`);
      if (p.empty) {
        expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('empty');
        expect(text(document.body)).toContain(p.empty);
        expect(document.querySelector('[data-page]'), p.id).toBeNull();
      } else {
        expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('data');
        expect(document.querySelector('[data-page="logs"]')).toBeTruthy();
      }
      cleanup();
    }
  }, 60000);

  it('error：出错块写命令、退出码 2 与报错原文；没有视图与页签', async () => {
    for (const p of PAGES) {
      await mountApp(`#/${p.id}?mock=error`);
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('error');
      const t = text(document.body);
      expect(t).toContain('没能读到数据');
      expect(t).toContain(p.cmd);
      expect(t).toMatch(/返回退出码\s*2/);
      expect(document.querySelector('pre')?.textContent).toContain('Permission denied');
      expect(document.querySelector('[data-page]'), p.id).toBeNull();
      expect(document.querySelector('[role="tablist"]')).toBeNull();
      cleanup();
    }
  }, 60000);

  it('offline：数据照常，role=alert 提示条、可能已过期、data-stale=true', async () => {
    for (const p of PAGES) {
      await mountApp(`#/${p.id}?mock=offline`);
      const root = pageRoot();
      expect(root.getAttribute('data-page-state'), p.id).toBe('data');
      expect(root.getAttribute('data-stale')).toBe('true');
      expect(document.querySelectorAll('[role="alert"]').length).toBe(1);
      expect(text(document.body)).toContain('可能已过期');
      expect(document.querySelector(`[data-page="${p.id}"]`), p.id).toBeTruthy();
      cleanup();
    }
  }, 60000);

  it('刷新钮文字：凭据叫重新检查，其余叫刷新', async () => {
    for (const p of PAGES) {
      await mountApp(`#/${p.id}?mock=data`);
      const names = Array.from(document.querySelectorAll('main button:not(:disabled)')).map((b) => text(b));
      expect(names, p.id).toContain(p.refresh);
      if (p.refresh === '刷新') expect(names).not.toContain('重新检查');
      cleanup();
    }
  }, 60000);
});

describe('夹具下的写入口（过渡）', () => {
  it('凭据 2、日志 0、插件 3（抽屉开 4）、历史 0（抽屉开 1），每个都禁用', async () => {
    await mountApp('#/secrets?mock=data');
    expect(disabledWrites().map((b) => text(b))).toEqual(['录入…', '录入…']);
    cleanup();
    await mountApp('#/logs?mock=data');
    expect(disabledWrites()).toHaveLength(0);
    cleanup();
    await mountApp('#/plugins?mock=data');
    expect(disabledWrites().map((b) => text(b)).sort()).toEqual(['停用…', '启用…', '核对全部'].sort());
    const rows = Array.from(document.querySelectorAll('main tbody tr')) as HTMLElement[];
    act(() => { rows[2].focus(); });
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.keyDown(rows[2], { key: 'Enter' });
    await settle();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
    expect(disabledWrites().map((b) => text(b)).sort()).toEqual(['停用…', '启用…', '核对全部', '重新核对'].sort());
    cleanup();
    await mountApp('#/history?mock=data');
    expect(disabledWrites()).toHaveLength(0);
    const rows2 = Array.from(document.querySelectorAll('main tbody tr')) as HTMLElement[];
    act(() => { rows2[0].focus(); });
    fireEvent.keyDown(rows2[0], { key: 'Enter' });
    await settle();
    expect(disabledWrites().map((b) => text(b))).toEqual(['回滚到这一条之后']);
  }, 60000);

  it('各页可用按钮只在白名单内，可用链接只有 [去设置]', async () => {
    const allowed = ['刷新', '重新检查', '重试', '检索', '关闭（Esc）', '复制 lock_sha256', '(tab)'];
    const problems: string[] = [];
    for (const mock of ['data', 'error']) {
      for (const p of PAGES) {
        await mountApp(`#/${p.id}?mock=${mock}`);
        const enabled = Array.from(document.querySelectorAll('main button:not(:disabled), [role="dialog"] button:not(:disabled)'))
          .map((b) => (b.getAttribute('role') === 'tab' ? '(tab)' : b.getAttribute('aria-label') || text(b)));
        for (const n of enabled) if (!allowed.includes(n)) problems.push(`${p.id} ${mock}：${n}`);
        for (const a of Array.from(document.querySelectorAll('main a[href], [role="dialog"] a[href]'))) {
          if (text(a) !== '去设置') problems.push(`${p.id} ${mock} 链接：${text(a)}`);
        }
        cleanup();
      }
    }
    expect(problems).toEqual([]);
  }, 60000);
});
