// Tab 栏（合同第 4 条 / D03）：9 项顺序与 data-tab、历史与设置之间分隔线、当前项 aria-current=page；
// 计数胶囊只在任务一项、为 0 或未读时不渲染、为 3 时文字是 3 且链接 aria-label 写明数量；
// 状态段两个计数、上次更新随页面状态、kit 版本；点链接调 navigate。
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TabBar } from '../src/shell/TabBar';
import type { Route } from '../src/shell/router';
import type { PageReport } from '../src/shell/ShellStatusContext';

afterEach(cleanup);

function route(partial: Partial<Route> = {}): Route {
  return { tabId: 'overview', pageId: 'overview', segments: [], query: '', ...partial };
}

function setup(props: Partial<React.ComponentProps<typeof TabBar>> = {}) {
  const navigate = vi.fn();
  const utils = render(
    <TabBar
      route={route()}
      navigate={navigate}
      counts={{ running: 1, needJudge: 3 }}
      page={{ phase: 'data', at: Date.now() }}
      kitVersion="2.12.0"
      repoName="demo-repo"
      offline={false}
      {...props}
    />,
  );
  return { navigate, ...utils };
}

describe('Tab 栏', () => {
  it('9 项顺序、data-tab 与文字正确，历史与设置之间有分隔线', () => {
    const { container } = setup();
    const tabs = Array.from(container.querySelectorAll('[data-tab]')).map((el) => el.getAttribute('data-tab'));
    expect(tabs).toEqual(['overview', 'tasks', 'roles', 'runtimes', 'secrets', 'logs', 'plugins', 'history', 'settings']);
    const labels = Array.from(container.querySelectorAll('[data-tab] .tt-tabbar__label')).map((el) => el.textContent);
    expect(labels).toEqual(['总览', '任务', '角色与模型', 'CLI 运行时', '凭据', '日志与用量', '插件', '历史与审计', '设置']);
    expect(container.querySelector('[data-tab-divider]')).not.toBeNull();
    // 分隔线在 history 与 settings 之间
    const all = Array.from(container.querySelector('[aria-label="主导航"]')!.children);
    const divIdx = all.findIndex((el) => el.getAttribute('data-tab-divider'));
    const settingsIdx = all.findIndex((el) => el.getAttribute('data-tab') === 'settings');
    const historyIdx = all.findIndex((el) => el.getAttribute('data-tab') === 'history');
    expect(divIdx).toBeGreaterThan(historyIdx);
    expect(divIdx).toBeLessThan(settingsIdx);
  });

  it('当前项 aria-current=page', () => {
    const { container } = setup({ route: route({ tabId: 'tasks', pageId: 'tasks' }) });
    expect(container.querySelector('[data-tab="tasks"]')?.getAttribute('aria-current')).toBe('page');
    expect(container.querySelector('[data-tab="overview"]')?.getAttribute('aria-current')).toBeNull();
  });

  it('计数为 3：data-tab-count 文字是 3、链接 aria-label 写明数量', () => {
    const { container } = setup();
    const count = container.querySelector('[data-tab-count]');
    expect(count?.textContent).toBe('3');
    expect(container.querySelector('[data-tab="tasks"]')?.getAttribute('aria-label')).toBe('任务（3 项需要你判断）');
  });

  it('计数为 0 或未读时不渲染计数胶囊', () => {
    const zero = setup({ counts: { running: 0, needJudge: 0 } });
    expect(zero.container.querySelector('[data-tab-count]')).toBeNull();
    const unread = setup({ counts: null });
    expect(unread.container.querySelector('[data-tab-count]')).toBeNull();
  });

  it('状态段：运行中与需要你判断、kit 版本；未读显示 —', () => {
    const { container } = setup();
    const status = container.querySelector('.tt-tabbar__status') as HTMLElement;
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect(status.textContent).toContain('运行中');
    expect(status.textContent).toContain('需要你判断');
    expect(status.textContent).toContain('kit 2.12.0');
    const unread = setup({ counts: null });
    expect((unread.container.querySelector('.tt-tabbar__status') as HTMLElement).textContent).toContain('—');
  });

  it('上次更新随页面状态；陈列页不渲染这一项', () => {
    const loading = setup({ page: { phase: 'loading', at: null } });
    expect((loading.container.querySelector('.tt-tabbar__status') as HTMLElement).textContent).toContain('正在读取…');
    const err = setup({ page: { phase: 'error', at: Date.now() } });
    expect((err.container.querySelector('.tt-tabbar__status') as HTMLElement).textContent).toContain('读取失败 ·');
    const showcase = setup({ route: route({ tabId: null, pageId: 'showcase' }) });
    const text = (showcase.container.querySelector('.tt-tabbar__status') as HTMLElement).textContent ?? '';
    expect(text).not.toContain('上次更新');
    expect(text).not.toContain('正在读取');
  });

  it('点 Tab 链接调 navigate；带修饰键不 navigate', () => {
    const { container, navigate } = setup();
    fireEvent.click(container.querySelector('[data-tab="plugins"]') as HTMLElement);
    expect(navigate).toHaveBeenCalledWith('/plugins');
    navigate.mockClear();
    fireEvent.click(container.querySelector('[data-tab="logs"]') as HTMLElement, { ctrlKey: true });
    expect(navigate).not.toHaveBeenCalled();
  });
});
