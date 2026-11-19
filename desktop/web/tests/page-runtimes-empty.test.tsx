// 空态只替换「已登记」那一节（合同第 4 步 (a)–(f)）：一个 runtime 都没登记时，页面状态仍是 empty、视图根照常
// 渲染，「已登记」一节里是空态（标题与说明两段原文）且该节里没有那张表，「就绪检查」一节与 Quizs 一块
// （提供方档案表与 live 套表）都在视图根里；读失败只写在区块里、不出页面级出错块；页头 [手动登记…] 空态下
// 可点，[刷新] 重读后「已登记」一节换成一张有一行的表。桩模式经 ?mock= / ?quizs= 选情景，注入经 setLiveClientForTests。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import App from '../src/App';
import { setLiveClientForTests } from '../src/live/mode';

const EMPTY_TITLE = '还没有登记的 runtime';
const EMPTY_DESC = '用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）';

beforeEach(() => {
  location.hash = '';
});
afterEach(() => {
  cleanup();
  location.hash = '';
  setLiveClientForTests(undefined);
});

const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mount(hash: string) {
  location.hash = hash;
  const r = render(<App />);
  await flush();
  return r;
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function pageRoot(): any {
  return document.querySelector('[data-page="runtimes"]');
}
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === title : false;
  }) || null;
}
function tableOf(root: any, label: string): any {
  const t = root.querySelector(`table[aria-label="${label}"]`);
  expect(t, `应有表 aria-label=${label}`).toBeTruthy();
  return t;
}
function rowCount(table: any): number {
  return qa(table, 'tbody tr').length;
}
function headerButtons(root: any): any[] {
  const bar = root.querySelector('.tt-page__actions');
  expect(bar, '应有 .tt-page__actions 页头操作区').toBeTruthy();
  return qa(bar, 'button');
}

const RUNTIMES_EMPTY = { runtimes: [] };
const RUNTIMES_ONE = { runtimes: [{ id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: [] }] };
const PROVIDERS = {
  providers: [
    { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
    { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
  ],
};
const LIVE = {
  live: [
    { source: 'mailbox', provider: 'deepseek', problem: null, status: { state: 'ready', problem: null, missing: [], certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' } } },
    { source: 'env', provider: 'deepseek', problem: null, status: { state: 'ready', problem: null, missing: [], certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' } } },
  ],
};

function envelope(data: unknown, command: string[], ok = true, exitCode: number | null = 0, messages: string[] = []): any {
  return { ok, exit_code: exitCode, data, output: [], messages, command, elapsed_ms: 0 };
}

// 替身 client：按路径给信封，over 里的路径换成指定信封；未列出的路径给 ok 夹具（runtimes 缺省空数组）。
function injectClient(over: Record<string, () => Promise<any>>) {
  const client = {
    get(path: string) {
      const hit = over[path];
      if (hit) return hit();
      if (path === '/api/v1/runtimes') return Promise.resolve(envelope(RUNTIMES_EMPTY, ['config', 'runtime', 'list']));
      if (path === '/api/v1/quizs/providers') return Promise.resolve(envelope(PROVIDERS, ['config', 'quizs', 'providers', '--json']));
      if (path === '/api/v1/quizs/live') return Promise.resolve(envelope(LIVE, ['config', 'quizs', 'live', '--json']));
      return Promise.resolve(envelope(null, []));
    },
    post() { return Promise.resolve({ status: 200, body: envelope(null, []) }); },
    getRaw() { return Promise.resolve({ status: 200, body: null }); },
  };
  setLiveClientForTests(client as any);
}

// 空态支下共有的三点：视图根在、「已登记」一节里是空态且没有那张表、Quizs 一块在视图根里。
function expectRegisteredEmpty(root: any) {
  expect(root, '空态下视图根照常渲染（页面状态仍是 empty）').toBeTruthy();
  const sec = sectionNamed(root, '已登记');
  expect(sec, '「已登记」一节在视图根里').toBeTruthy();
  const empty = sec.querySelector('.tt-empty');
  expect(empty, '「已登记」一节里应有空态（替换那张表）').toBeTruthy();
  expect(text(empty.querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
  expect(text(empty.querySelector('.tt-empty__desc'))).toBe(EMPTY_DESC);
  expect(sec.querySelector('table[aria-label="已登记的 runtime"]'), '空态时「已登记」一节里没有那张表').toBeNull();
}

// 空态支下「就绪检查」一节照常：两钮都在且可点、「按版本记录核验」文本框在。
function expectReadySection(root: any) {
  const ready = sectionNamed(root, '就绪检查');
  expect(ready, '「就绪检查」一节在视图根里').toBeTruthy();
  const labels = qa(ready, 'button').map((b: any) => text(b));
  expect(labels, '「就绪检查」一节里应有 [运行就绪检查] 与 [核验]').toEqual(['运行就绪检查', '核验']);
  qa(ready, 'button').forEach((b: any) => expect((b as HTMLButtonElement).disabled, '空闲时 ' + text(b) + ' 可点').toBe(false));
  expect(qa(ready, 'label').map(text), '「按版本记录核验」的可见 label 在').toContain('按版本记录核验');
  expect(ready.querySelector('input.tt-field__input'), '「按版本记录核验」的文本框在').toBeTruthy();
}

// 空态支下 Quizs 一块在视图根里：两张表各 2 行。
function expectQuizsInRoot(root: any) {
  const quizs = sectionNamed(root, 'Quizs');
  expect(quizs, 'Quizs 一块在视图根里').toBeTruthy();
  expect(quizs.closest('[data-page="runtimes"]'), 'Quizs 一块在视图根里').toBe(root);
  expect(rowCount(tableOf(quizs, 'Quizs 提供方档案')), '提供方档案表两行').toBe(2);
  expect(rowCount(tableOf(quizs, 'Quizs live 套')), 'live 套表两行').toBe(2);
}

describe('空态只替换「已登记」一节：?mock=empty', () => {
  it('(a) 空态：状态 empty、视图根在；「已登记」一节里是空态（标题与说明原文）且没有那张表；就绪检查一节与 Quizs 一块都在视图根里；页头三钮照旧', async () => {
    await mount('#/runtimes?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    const root = pageRoot();
    expectRegisteredEmpty(root);
    expectReadySection(root);
    expectQuizsInRoot(root);
    expect(frame().querySelector('.tt-page__error'), '空态没有页面级出错块').toBeNull();
    const buttons = headerButtons(frame());
    expect(buttons.map((b) => text(b))).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect((buttons[0] as HTMLButtonElement).disabled, '[扫描 PATH] 照旧禁用').toBe(false);
    expect((buttons[1] as HTMLButtonElement).disabled, '空态下 [手动登记…] 可点').toBe(false);
  });

  it('(b) ?mock=empty&quizs=broken：状态仍 empty、视图根在、标题与说明仍在；区块写「Quizs 跑不起来」与 live 的「读不出」；没有页面级出错块', async () => {
    await mount('#/runtimes?mock=empty&quizs=broken');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    const root = pageRoot();
    expectRegisteredEmpty(root);
    expectReadySection(root);
    const sec = sectionNamed(root, 'Quizs');
    expect(text(sec), 'providers 失败只写在区块里').toContain('Quizs 跑不起来');
    const lt = tableOf(sec, 'Quizs live 套');
    qa(lt, 'tbody tr').forEach((tr: any) => expect(text(tr), 'live 每套读不出').toContain('读不出'));
    expect(frame().querySelector('.tt-page__error'), '读失败只写在区块里，没有页面级出错块').toBeNull();
  });
});

describe('空态下的 Quizs 失败只写在区块里', () => {
  it('(c) 注入替身（runtimes 空数组、providers 失败）：状态 empty，视图根在，失败只在区块里，没有页面级出错块', async () => {
    injectClient({
      '/api/v1/runtimes': () => Promise.resolve(envelope(RUNTIMES_EMPTY, ['config', 'runtime', 'list'])),
      '/api/v1/quizs/providers': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'providers', '--json'], false, 3, ['E-ONE', 'E-TWO'])),
    });
    await mount('#/runtimes');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    const root = pageRoot();
    expectRegisteredEmpty(root);
    expectReadySection(root);
    const t = text(sectionNamed(root, 'Quizs'));
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('E-ONE');
    expect(frame().querySelector('.tt-page__error'), 'providers 失败不整页出错').toBeNull();
  });
});

describe('空态不是死路：重读之后按有运行时的样子显示', () => {
  it('(d) runtimes 先空后有一条：点 [刷新] 之后状态变 data、「已登记」一节换成一张有一行的表、空态消失，Quizs 一块仍在视图根里', async () => {
    let reads = 0;
    injectClient({
      '/api/v1/runtimes': () => {
        reads += 1;
        return Promise.resolve(
          reads === 1
            ? envelope(RUNTIMES_EMPTY, ['config', 'runtime', 'list'])
            : envelope(RUNTIMES_ONE, ['config', 'runtime', 'list']),
        );
      },
    });
    await mount('#/runtimes');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    const before = pageRoot();
    expectRegisteredEmpty(before);
    expectQuizsInRoot(before);
    const refresh = headerButtons(frame()).find((b) => text(b) === '刷新');
    expect(refresh, '应有 [刷新] 钮').toBeTruthy();
    await act(async () => { fireEvent.click(refresh); });
    await flush();
    expect(frame().getAttribute('data-page-state'), '重读后按有运行时的样子显示').toBe('data');
    const root = pageRoot();
    expect(root, '重读后视图根还在').toBeTruthy();
    const sec = sectionNamed(root, '已登记');
    expect(sec, '重读后「已登记」一节在').toBeTruthy();
    expect(sec.querySelector('.tt-empty'), '重读后空态消失').toBeNull();
    expect(rowCount(tableOf(sec, '已登记的 runtime')), '重读后「已登记」一节里是一张有一行的表').toBe(1);
    expectQuizsInRoot(root);
  });
});

describe('loading / error 态没有 Quizs 一块', () => {
  it('(e) ?mock=loading 挂起；?mock=error 整页出错（有页面级出错块）', async () => {
    await mount('#/runtimes?mock=loading');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
    expect(sectionNamed(frame(), 'Quizs'), 'loading 态没有 Quizs 一块').toBeNull();
    cleanup();
    await mount('#/runtimes?mock=error');
    expect(frame().getAttribute('data-page-state')).toBe('error');
    expect(frame().querySelector('.tt-page__error'), 'error 态有页面级出错块').toBeTruthy();
    expect(sectionNamed(frame(), 'Quizs'), 'error 态没有 Quizs 一块').toBeNull();
  });
});

describe('初始标题', () => {
  it('(f) index.html 的初始标题逐字是 <title>Themis Tally</title>，文件里不再有「组件陈列」', async () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    expect(html).toContain('<title>Themis Tally</title>');
    expect(html, '不再闪出陈列页标题').not.toContain('组件陈列');
  });
});
