// 应用级测试（合同第 9、10 节，过渡）：经 ?mock= 渲染 App 三页的五态、夹具值、点指标卡后路由、写入口个数与可用按钮白名单。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import App from '../src/App';

beforeEach(() => {
  location.hash = '';
});
afterEach(() => {
  cleanup();
  location.hash = '';
});

const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
const h1 = () => document.querySelector('h1')?.textContent;
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function root(page: string): any {
  return document.querySelector(`[data-page="${page}"]`);
}
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mount(hash: string) {
  location.hash = hash;
  const r = render(<App />);
  await flush();
  return r;
}

describe('三页五态（经 ?mock=）', () => {
  it('总览 data/empty/loading/error', async () => {
    await mount('#/overview?mock=data');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(root('overview')).not.toBeNull();
    expect(h1()).toBe('总览');
    cleanup();
    await mount('#/overview?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(text(frame())).toContain('还没有 attempt');
    expect(root('overview')).toBeNull();
    cleanup();
    await mount('#/overview?mock=loading');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
    expect(root('overview')).toBeNull();
    cleanup();
    await mount('#/overview?mock=error');
    expect(frame().getAttribute('data-page-state')).toBe('error');
  });

  it('角色页 ?mock=empty 仍是 data', async () => {
    await mount('#/roles?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(root('roles')).not.toBeNull();
    expect(h1()).toBe('角色与模型');
  });

  it('运行时页 data/empty', async () => {
    await mount('#/runtimes?mock=data');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(root('runtimes')).not.toBeNull();
    expect(h1()).toBe('CLI 运行时');
    cleanup();
    await mount('#/runtimes?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(text(frame())).toContain('还没有登记的 runtime');
  });
});

describe('夹具值与点击导航', () => {
  it('总览指标 1/2/1/1、说明 demo-repo · kit 2.12.0', async () => {
    await mount('#/overview');
    const cards = qa(root('overview'), '[data-metric]');
    expect(cards.map((c: any) => c.querySelector('.tt-num')?.textContent)).toEqual(['1', '2', '1', '1']);
    expect(text(document.querySelector('.tt-page__desc'))).toBe('demo-repo · kit 2.12.0');
  });

  it('点指标卡换到任务页并保留 mock', async () => {
    await mount('#/overview?mock=data');
    fireEvent.click(qa(root('overview'), '[data-metric]')[0]);
    await flush();
    expect(location.hash).toContain('/tasks');
    expect(location.hash).toContain('group=running');
    expect(location.hash).toContain('mock=data');
    expect(h1()).toBe('任务');
  });
});

describe('写入口个数（过渡）', () => {
  const disabled = () => qa(frame(), 'button').filter((b: any) => b.disabled);
  it('角色页 13、运行时页 9、总览 0', async () => {
    await mount('#/roles');
    expect(disabled().length, '角色页').toBe(13);
    cleanup();
    await mount('#/runtimes');
    expect(disabled().length, '运行时页').toBe(9);
    cleanup();
    await mount('#/overview');
    expect(disabled().length, '总览页').toBe(0);
  });
});
