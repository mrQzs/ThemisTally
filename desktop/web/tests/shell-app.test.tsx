// 应用框架装配（合同第 1、9 条 / D01、D10、P10、P12）：默认空 hash 是总览；点 Tab 与快捷键切页后地址、h1、
// document.title 同步变；未知路由回总览；#/showcase 渲染陈列页且没有当前 Tab；页面占位显示夹具数据与条数。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';

beforeEach(() => { location.hash = ''; });
afterEach(cleanup);

async function flush() { await act(async () => { await Promise.resolve(); }); }
const h1 = () => document.querySelector('h1')?.textContent;

describe('应用框架', () => {
  it('默认空 hash 渲染总览，标题栏与 Tab 栏都在', async () => {
    location.hash = '';
    render(<App />);
    await flush();
    expect(h1()).toBe('总览');
    expect(document.querySelector('svg.tt-logo')).not.toBeNull();
    expect(document.querySelector('nav[aria-label="主导航"]')).not.toBeNull();
    expect(document.title).toBe('总览 · Themis Tally');
  });

  it('#/tasks 渲染任务页', async () => {
    location.hash = '#/tasks';
    render(<App />);
    await flush();
    expect(h1()).toBe('任务');
    expect(document.title).toBe('任务 · Themis Tally');
  });

  it('总览占位显示夹具数据与条数', async () => {
    location.hash = '#/overview';
    render(<App />);
    await flush();
    expect(document.body.textContent).toContain('夹具数据已读到：getStatus，7 条');
  });

  it('Ctrl+2 切到任务页（地址、h1 同步变）', async () => {
    location.hash = '#/overview';
    render(<App />);
    await flush();
    fireEvent.keyDown(window, { key: '2', ctrlKey: true });
    expect(location.hash).toBe('#/tasks');
    expect(h1()).toBe('任务');
  });

  it('Ctrl+, 切到设置页', async () => {
    location.hash = '#/overview';
    render(<App />);
    await flush();
    fireEvent.keyDown(window, { key: ',', ctrlKey: true });
    expect(location.hash).toBe('#/settings');
    expect(h1()).toBe('设置');
  });

  it('点 Tab 链接切页', async () => {
    location.hash = '#/overview';
    const { container } = render(<App />);
    await flush();
    fireEvent.click(container.querySelector('[data-tab="plugins"]') as HTMLElement);
    expect(location.hash).toBe('#/plugins');
    expect(h1()).toBe('插件');
  });

  it('未知路由回总览但不改写地址', async () => {
    location.hash = '#/nonsense';
    render(<App />);
    await flush();
    expect(h1()).toBe('总览');
    expect(location.hash).toBe('#/nonsense');
  });

  it('#/tasks/x/y 归任务页', async () => {
    location.hash = '#/tasks/x/y';
    render(<App />);
    await flush();
    expect(h1()).toBe('任务');
  });

  it('#/showcase 渲染陈列页、没有当前 Tab、title 为组件陈列', async () => {
    location.hash = '#/showcase';
    const { container } = render(<App />);
    await flush();
    expect(container.querySelector('.showcase')).not.toBeNull();
    expect(h1()).toBe('组件陈列');
    expect(container.querySelector('[data-tab][aria-current="page"]')).toBeNull();
    expect(document.title).toBe('组件陈列 · Themis Tally');
  });

  it('主题经标题栏菜单切换，data-theme 跟着变', async () => {
    location.hash = '#/overview';
    const { getByLabelText, container } = render(<App />);
    await flush();
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false); // 缺省暗
    fireEvent.click(getByLabelText('主题：暗'));
    fireEvent.click(container.querySelector('[role="menuitemradio"]:not([aria-checked="true"])') as HTMLElement);
    expect(['light', 'system']).toContain(document.documentElement.getAttribute('data-theme'));
  });
});
