// 真实模式下的应用接线（合同第 7 节，T034 第 2 片）：经 setLiveClientForTests 注入假客户端，观察 App 的
// meta 占位与回填、四种页面状态、断线与恢复、外壳页路由零请求。不发真请求，不 mock 被测模块——
// 断言打在真实的 api 读函数、PageFrame 与连接状态源上。
import * as React from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import statusJson from '../src/mock/status.json';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

function okEnv(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['status'], elapsed_ms: 3 };
}
function failEnv(messages: string[]) {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const calls: string[] = [];
let responders: Record<string, () => unknown> = {};

function install(overrides: Record<string, () => unknown> = {}) {
  calls.length = 0;
  responders = {
    '/api/v1/meta': () => okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' }),
    '/api/v1/status': () => okEnv(statusJson),
    '/api/v1/config/history': () => okEnv({ entries: [], broken_lines: 0, external_before_first: 0 }),
    ...overrides,
  };
  const client = {
    get(path: string) {
      calls.push(path);
      const respond = responders[path] ?? (() => okEnv(null));
      return Promise.resolve().then(() => respond() as any);
    },
  };
  setLiveClientForTests(client as any);
}

function bodyText(): string {
  return (document.body.textContent || '').replace(/\s+/g, ' ');
}
function repoButton(): HTMLElement {
  return document.querySelector('button[title="切换仓库"]') as HTMLElement;
}
function statusText(): string {
  const el = document.querySelector('.tt-tabbar__status');
  return (el && el.textContent) || '';
}
function pillState(): string | null {
  const el = document.querySelector('.tt-pill');
  return el ? el.getAttribute('data-state') : null;
}
function pillText(): string {
  const el = document.querySelector('.tt-pill__text');
  return (el && el.textContent) || '';
}
function pageState(): string | null {
  const el = document.querySelector('[data-page-state]');
  return el ? el.getAttribute('data-page-state') : null;
}
function reconnectButton(): HTMLButtonElement | undefined {
  return (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).find(
    (b) => (b.textContent || '').trim() === '重新连接',
  );
}
function count(path: string): number {
  return calls.filter((p) => p === path).length;
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(async () => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('外壳页路由：不挂服务窗口，零请求、零横幅', () => {
  it('#/first-run 与 #/service-status：假客户端一次都没被调用，也没有离线横幅', async () => {
    install();
    setConnectionState('disconnected');
    for (const win of ['first-run', 'service-status']) {
      cleanup();
      window.location.hash = '#/' + win;
      render(<App />);
      await settle();
      expect(calls.length, win).toBe(0);
      expect(bodyText(), win).not.toContain('与本机服务的连接断开');
      expect(document.querySelector('.tt-pill'), win).toBeNull();
    }
  });
});

describe('meta：真实模式先占位「—」，getMeta() 兑现后填服务给的值', () => {
  it('首屏标题栏仓库名与 Tab 栏 kit 都是「—」，兑现后是服务给的值', async () => {
    const fills: Array<(v: any) => void> = [];
    install({ '/api/v1/meta': () => new Promise((res) => { fills.push(res); }) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(fills.length, '真实模式下 meta 只经 getMeta() 取').toBeGreaterThan(0);
    expect((repoButton().textContent || '')).toContain('—');
    expect(statusText()).toContain('kit —');
    expect(bodyText()).not.toContain('demo-repo');
    expect(bodyText()).not.toContain('kit 2.12.0');
    await act(async () => {
      fills.forEach((res) => res(okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' })));
    });
    await settle();
    expect((repoButton().textContent || '')).toContain('live-repo');
    expect(statusText()).toContain('kit 9.9.9');
  });

  it('getMeta() 失败保持「—」，不报错、不清空', async () => {
    install({ '/api/v1/meta': () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect((repoButton().textContent || '')).toContain('—');
    expect(statusText()).toContain('kit —');
  });

  it('总览页说明首屏是单个「—」，兑现后是「仓库名 · kit 版本」', async () => {
    const fills: Array<(v: any) => void> = [];
    install({ '/api/v1/meta': () => new Promise((res) => { fills.push(res); }) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    const desc = document.querySelector('.tt-page__desc') as HTMLElement;
    expect((desc.textContent || '').trim()).toBe('—');
    await act(async () => {
      fills.forEach((res) => res(okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' })));
    });
    await settle();
    const after = document.querySelector('.tt-page__desc') as HTMLElement;
    expect((after.textContent || '').trim()).toBe('live-repo · kit 9.9.9');
  });
});

describe('断线与恢复：横幅、胶囊与下一次成功', () => {
  it('断线出 danger 横幅与「已断开」，恢复后横幅消失、胶囊回「已连接」', async () => {
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    act(() => { setConnectionState('disconnected'); });
    expect(bodyText()).toContain('与本机服务的连接断开');
    expect(bodyText()).toContain('可能已过期');
    expect(document.querySelector('[data-stale]')).not.toBeNull();
    expect(pillState()).toBe('disconnected');
    expect(pillText()).toBe('已断开');
    act(() => { setConnectionState('connected'); });
    expect(bodyText()).not.toContain('与本机服务的连接断开');
    expect(pillState()).toBe('connected');
    expect(pillText()).toBe('已连接');
  });

  it('[重新连接] 在真实模式可点并重跑本页 load', async () => {
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    act(() => { setConnectionState('disconnected'); });
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    expect(btn!.disabled).toBe(false);
    const before = count('/api/v1/status');
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(count('/api/v1/status')).toBeGreaterThan(before);
  });

  it('已有数据时刷新失败且已断开：保留旧数据与原 phase、不出错块', async () => {
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('data');
    act(() => { setConnectionState('disconnected'); });
    responders['/api/v1/status'] = () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']);
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(pageState()).toBe('data');
    expect(document.querySelector('[data-page="overview"]')).not.toBeNull();
    expect(bodyText()).not.toContain('没能读到数据');
    expect(bodyText()).not.toContain('读取失败');
  });
});

describe('四种页面状态各一例', () => {
  it('加载中：请求不兑现时是骨架与 loading', async () => {
    install({ '/api/v1/status': () => new Promise(() => undefined) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('loading');
  });

  it('出错：200 + ok:false 的合成信封只列 messages，不写「命令（…）返回退出码」', async () => {
    install({ '/api/v1/status': () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('error');
    expect(bodyText()).toContain('没能读到数据');
    expect(bodyText()).toContain('ERROR: 连不上本机服务（请求没有到达服务）');
    expect(bodyText()).not.toContain('返回退出码');
  });

  it('离线：disconnected 时是 danger 横幅加 data-stale', async () => {
    setConnectionState('disconnected');
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(bodyText()).toContain('与本机服务的连接断开');
    expect(document.querySelector('[data-stale]')).not.toBeNull();
    expect(pillText()).toBe('已断开');
  });

  it('空：/api/v1/status 回空数组 → 「还没有 attempt」', async () => {
    install({ '/api/v1/status': () => okEnv([]) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('empty');
    expect(bodyText()).toContain('还没有 attempt');
  });
});

describe('夹具模式：不注入时照旧', () => {
  it('首屏是夹具 meta、胶囊 connected、没有离线横幅，也不调 getMeta', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect((repoButton().textContent || '')).toContain('demo-repo');
    expect(statusText()).toContain('kit 2.12.0');
    expect(pillState()).toBe('connected');
    expect(bodyText()).not.toContain('与本机服务的连接断开');
  });
});
