// 路由（合同第 1 条 / D01）：parseHash 的解析规则与 useHashRoute 的导航（同步更新状态、写 hash、保留 ?mock=）。
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { parseHash, useHashRoute } from '../src/shell/router';

describe('parseHash', () => {
  it('空、#、#/ 与未知路径都归总览', () => {
    for (const h of ['', '#', '#/', '#/unknown', '#/a/b/c']) {
      const r = parseHash(h);
      expect(r.pageId).toBe('overview');
      expect(r.tabId).toBe('overview');
    }
  });

  it('9 个 Tab 路径各自命中，其余段原样交给页面', () => {
    expect(parseHash('#/overview').tabId).toBe('overview');
    expect(parseHash('#/tasks').tabId).toBe('tasks');
    const deep = parseHash('#/tasks/x/y');
    expect(deep.pageId).toBe('tasks');
    expect(deep.segments).toEqual(['x', 'y']);
    expect(parseHash('#/settings').tabId).toBe('settings');
  });

  it('#/showcase 没有当前项', () => {
    const r = parseHash('#/showcase');
    expect(r.pageId).toBe('showcase');
    expect(r.tabId).toBeNull();
  });

  it('按 ? 切路径与查询', () => {
    const r = parseHash('#/overview?mock=data');
    expect(r.pageId).toBe('overview');
    expect(r.query).toBe('mock=data');
  });
});

describe('useHashRoute', () => {
  it('navigate 先同步更新状态、再写 hash，并保留 ?mock=', () => {
    location.hash = '#/overview?mock=data';
    const { result } = renderHook(() => useHashRoute());
    expect(result.current.route.pageId).toBe('overview');
    act(() => { result.current.navigate('/tasks'); });
    expect(result.current.route.pageId).toBe('tasks');
    expect(location.hash).toBe('#/tasks?mock=data');
  });

  it('监听 hashchange 接住手改地址', () => {
    location.hash = '#/overview';
    const { result } = renderHook(() => useHashRoute());
    act(() => { window.location.hash = '#/plugins'; });
    // hashchange 经 setTimeout(0) 派发；等待一个宏任务。
    return act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    }).then(() => {
      expect(result.current.route.pageId).toBe('plugins');
    });
  });
});
