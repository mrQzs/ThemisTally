// 任务页 App 级自测（合同 Steps 5、11、D04、D06、D12）：经 ?mock= 的两页五态、地址与夹具值、不可信内容与写入口。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import App from '../src/App';

afterEach(() => {
  cleanup();
  window.location.hash = '';
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element | null, sel: string) => Array.from((root ?? document).querySelectorAll(sel));
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
  const nodes = qa(document, '[data-page-state]');
  expect(nodes.length, '整页恰一个 data-page-state').toBe(1);
  return nodes[0] as HTMLElement;
}
const options = () => qa(document, 'li[role="option"]');
const capsules = () => qa(document, '[role="group"][aria-label="按状态分组筛选"] button');
const optionTask = (el: Element) => text(el).replace(/\s+attempt-[\s\S]*$/, '').trim();
const attemptTable = (task: string) => document.querySelector(`table[aria-label="${task} 的 attempt"]`);
const tabs = () => qa(document, '[role="tab"]');
const selectedTab = () => tabs().filter((t) => t.getAttribute('aria-selected') === 'true')[0];
const hashParams = () => {
  const raw = window.location.hash.replace(/^#/, '');
  const q = raw.indexOf('?');
  const out: Record<string, string> = {};
  if (q >= 0) new URLSearchParams(raw.slice(q + 1)).forEach((v, k) => { out[k] = v; });
  return { path: q < 0 ? raw : raw.slice(0, q), params: out };
};

describe('两页五态（经 ?mock=）', () => {
  it('列表页：五态逐个渲染', async () => {
    for (const mock of ['data', 'loading', 'empty', 'error', 'offline']) {
      await mountApp(`#/tasks?mock=${mock}`);
      const state = pageRoot().getAttribute('data-page-state');
      if (mock === 'loading') expect(state).toBe('loading');
      else if (mock === 'empty') {
        expect(state).toBe('empty');
        expect(text(document.body)).toContain('还没有 attempt');
      } else if (mock === 'error') {
        expect(state).toBe('error');
        expect(text(document.body)).toContain('命令（status）返回退出码 2');
      } else if (mock === 'offline') {
        expect(state).toBe('data');
        expect(pageRoot().getAttribute('data-stale')).toBe('true');
        expect(text(document.body)).toContain('可能已过期');
      } else {
        expect(state).toBe('data');
        expect(text(document.querySelector('h1'))).toBe('任务');
        expect(qa(document, '[data-page]').length).toBe(1);
      }
      cleanup();
    }
  }, 60000);

  it('详情页：五态逐个渲染，#/tasks/x/y 进空态且地址不变', async () => {
    for (const mock of ['data', 'loading', 'empty', 'error', 'offline']) {
      await mountApp(`#/tasks/logs-cat/attempt-002?mock=${mock}`);
      const state = pageRoot().getAttribute('data-page-state');
      if (mock === 'loading') expect(state).toBe('loading');
      else if (mock === 'empty') expect(state, 'empty 时 logs show 照常').toBe('data');
      else if (mock === 'error') expect(state).toBe('error');
      else expect(state).toBe('data');
      cleanup();
    }
    await mountApp('#/tasks/x/y?mock=data');
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(text(document.querySelector('h1'))).toBe('任务');
    expect(text(document.body)).toContain('找不到这个 attempt');
    expect(text(document.body)).toContain('x/y 不在 status 里，logs show 也没有读到。回到任务列表重新选一个。');
    expect(window.location.hash).toBe('#/tasks/x/y?mock=data');
  }, 60000);
});

describe('夹具下的具体值', () => {
  it('列表：6 个任务、计数 1/2/1/1/1、缺省选中 ui-readonly-api', async () => {
    await mountApp('#/tasks?mock=data');
    expect(options().length).toBe(6);
    expect(capsules().map((b) => text(b).replace(/[^\d]/g, ''))).toEqual(['1', '2', '1', '1', '1']);
    const sel = options().filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(optionTask(sel[0])).toBe('ui-readonly-api');
    const table = attemptTable('ui-readonly-api');
    expect(table).not.toBeNull();
    expect(qa(table, 'tbody tr').length).toBe(1);
  });

  it('分组地址：指标卡导航到 #/tasks?group=<组>，对应胶囊按下', async () => {
    await mountApp('#/overview?mock=data');
    const card = qa(document, 'a[data-metric="review"]')[0];
    expect(card, 'T009 的指标卡').toBeTruthy();
    fireEvent.click(card);
    await settle();
    const p = hashParams();
    expect(p.path).toBe('/tasks');
    expect(p.params.group).toBe('review');
    expect(p.params.mock).toBe('data');
    expect(options().map(optionTask)).toEqual(['logs-cat', 'plugin-verify-json']);
    expect(text(capsules().filter((b) => b.getAttribute('data-group') === 'review')[0]).replace(/[^\d]/g, '')).toBe('2');
    expect(qa(document, 'a[data-metric="ended"]').length, '指标卡只有前四个分组').toBe(0);
  });

  it('详情页头与全部文件页签', async () => {
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    expect(text(document.querySelector('h1'))).toBe('logs-cat · attempt-002');
    const dl: Record<string, string> = {};
    qa(document, 'dt').forEach((dt) => { dl[text(dt)] = text(dt.nextElementSibling); });
    expect(dl['版本']).toBe('v2');
    expect(dl['用时']).toBe('28 分 39 秒');
    expect(dl['token']).toBe('4,210,385');
    expect(dl['检查']).toBe('8/8（fresh）');
    expect(dl['越界']).toBe('0');
    fireEvent.click(tabs().filter((t) => text(t) === '全部文件')[0]);
    await settle();
    const table = qa(document, 'table[aria-label="证据文件"]')[0];
    expect(qa(table, 'tbody tr').length).toBe(5);
    expect(qa(table, 'button').filter((b) => text(b) === '在资源管理器中显示').length).toBe(5);
    fireEvent.click(tabs().filter((t) => text(t) === '补丁')[0]);
    await settle();
    expect(qa(document, '.tt-diff').length, '补丁取自本片夹具').toBe(1);
  });
});

describe('地址与写入口', () => {
  it('点胶囊只改受管的 group 参数；点行进详情；页签写进地址', async () => {
    await mountApp('#/tasks?mock=offline&keep=1');
    const len = window.history.length;
    const h1 = document.querySelector('h1');
    fireEvent.click(capsules().filter((b) => b.getAttribute('data-group') === 'review')[0]);
    await settle();
    let p = hashParams();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ mock: 'offline', keep: '1', group: 'review' });
    expect(window.history.length, 'replaceState 不加历史项').toBe(len);
    expect(document.querySelector('h1'), '页内改地址不重挂载').toBe(h1);
    fireEvent.click(qa(attemptTable('logs-cat')!, 'tbody tr')[0]);
    await settle();
    p = hashParams();
    expect(p.path).toBe('/tasks/logs-cat/attempt-002');
    expect(p.params.mock).toBe('offline');
    expect(p.params.tab).toBe('summary');
    expect(text(document.querySelector('h1'))).toBe('logs-cat · attempt-002');
    fireEvent.click(tabs().filter((t) => text(t) === '补丁')[0]);
    await settle();
    expect(hashParams().params.tab).toBe('patch');
    expect(selectedTab() && text(selectedTab())).toBe('补丁');
  }, 60000);

  it('两页上没有派遣、验收、合并、试跑字样的可用按钮；禁用入口只有「在资源管理器中显示」', async () => {
    const bad: string[] = [];
    for (const hash of ['#/tasks?mock=data', '#/tasks/logs-cat/attempt-002?mock=data']) {
      await mountApp(hash);
      for (const label of ['摘要', '补丁', '检查', '执行报告', '事件', '全部文件']) {
        const tab = tabs().filter((t) => text(t) === label)[0];
        if (tab) {
          fireEvent.click(tab);
          await settle();
        }
        qa(document, 'main button').forEach((b) => {
          if ((b as HTMLButtonElement).disabled) return;
          if (['派遣', '合并', '试跑'].some((w) => text(b).includes(w))) bad.push(`${hash} ${label}：${text(b)}`);
        });
      }
      cleanup();
    }
    expect(bad).toEqual([]);
    await mountApp('#/tasks/logs-cat/attempt-002?tab=files&mock=data');
    const others = qa(document.querySelector('main'), 'button')
      .filter((b) => (b as HTMLButtonElement).disabled && text(b) !== '在资源管理器中显示');
    expect(others.map(text), '两页上没有别的写入口').toEqual([]);
  }, 60000);

  it('不可信内容只按文本显示', async () => {
    await mountApp('#/tasks/logs-cat/attempt-002?tab=summary&mock=data');
    const panel = qa(document, '[role="tabpanel"]')[0];
    expect(text(panel)).toContain('logs-cat.v2 / attempt-002');
    expect(qa(panel, 'img, script').length).toBe(0);
    expect(qa(panel, 'a').length, '页签面板里没有 a 元素').toBe(0);
    fireEvent.click(tabs().filter((t) => text(t) === '执行报告')[0]);
    await settle();
    const viewer = qa(document, '.tt-viewer')[0];
    expect(text(viewer)).toContain('<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字');
    expect(qa(viewer, 'img, script').length).toBe(0);
    expect(text(viewer).indexOf('\u001b')).toBe(-1);
  });
});
