// 七端岗位证书列页面测试（合同第 7 节）：桩模式五个情景与真实模式（注入假服务）的证书格。
// 期望值全是字面量；每份用例自带全部辅助函数，不跨文件共享作用域。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import type { Envelope, QuizsLiveData } from '../src/api';

const HEADERS = ['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '证书', '操作'];
const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];
const NON_QUIZ = ['planner', 'gate', 'audit', 'exec'];
const LIVE_PROBLEM = 'quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));

async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}

async function mount(hash: string) {
  location.hash = hash;
  const r = render(<App />);
  await flush();
  return r;
}

function hubSec(): any {
  return qa(document, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === '七端岗位' : false;
  }) || null;
}

function hubRow(post: string): any {
  const sec = hubSec();
  expect(sec, '应有「七端岗位」区块').toBeTruthy();
  const row = qa(sec, 'tbody tr').find((tr: any) => tr.getAttribute('data-post') === post);
  expect(row, '应有 data-post=' + post + ' 的行').toBeTruthy();
  return row;
}

function cell(row: any, header: string): any {
  const hit = qa(row, 'td')[HEADERS.indexOf(header)];
  expect(hit, '应有「' + header + '」那一格').toBeTruthy();
  return hit;
}

function cert(post: string): any {
  return cell(hubRow(post), '证书');
}

function tagIn(el: any): any {
  return el.querySelector('.tt-tag') || null;
}

function okEnv<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

function failEnv(messages: string[]): Envelope<QuizsLiveData> {
  return { ok: false, exit_code: 2, data: null, output: [], messages, command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0 };
}

beforeEach(() => {
  setLiveClientForTests(undefined);
  setConnectionState('connected');
  location.hash = '';
});

afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  setConnectionState('connected');
  location.hash = '';
});

describe('桩模式：证书列的逐格（合同第 7 节第 1—3 条）', () => {
  it('列头十一列，「证书」在「最近一回合」与「操作」之间；coordinator 是 Tag「就绪」、contract 是纯文字「没有 live 文件」、其余四行「—」', async () => {
    await mount('#/roles');
    const table = hubSec().querySelector('table[aria-label="七端岗位"]');
    expect(qa(table, 'thead th').map(text), '列头逐字是十一列').toEqual(HEADERS);
    const tag = tagIn(cert('coordinator'));
    expect(tag, 'coordinator 对上的那一套是 Tag').toBeTruthy();
    expect(text(tag)).toBe('就绪');
    expect(tag.getAttribute('data-tone')).toBe('success');
    const contractCell = cert('contract');
    expect(text(contractCell), 'contract 对不上任何一套').toBe('没有 live 文件');
    expect(tagIn(contractCell), '纯文字格没有 .tt-tag').toBe(null);
    expect(qa(contractCell, '[title]').length, '「没有 live 文件」不带 title').toBe(0);
    for (const post of NON_QUIZ) {
      expect(text(cert(post)), post + ' 非 quizs 岗位是「—」').toBe('—');
      expect(tagIn(cert(post)), post + ' 没有 Tag').toBe(null);
    }
  });

  it('?quizs=expired：coordinator 是 Tag「已过期」（danger）；contract 仍是「没有 live 文件」', async () => {
    await mount('#/roles?quizs=expired');
    const tag = tagIn(cert('coordinator'));
    expect(tag, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('已过期');
    expect(tag.getAttribute('data-tone')).toBe('danger');
    expect(text(cert('contract'))).toBe('没有 live 文件');
  });

  it('?quizs=missing：coordinator 是 Tag「缺文件」（warning）且 title 是「缺 qualification.json」', async () => {
    await mount('#/roles?quizs=missing');
    const tag = tagIn(cert('coordinator'));
    expect(tag, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('缺文件');
    expect(tag.getAttribute('data-tone')).toBe('warning');
    expect(tag.getAttribute('title')).toBe('缺 qualification.json');
    expect(text(cert('contract'))).toBe('没有 live 文件');
  });

  it('?quizs=broken：coordinator 是 Tag「读不出」（danger），title 是 problem 原文；contract 仍是「没有 live 文件」', async () => {
    await mount('#/roles?quizs=broken');
    const tag = tagIn(cert('coordinator'));
    expect(tag, 'coordinator 对上的那一套 status 为 null，仍是 Tag').toBeTruthy();
    expect(text(tag)).toBe('读不出');
    expect(tag.getAttribute('data-tone')).toBe('danger');
    expect(tag.getAttribute('title')).toBe(LIVE_PROBLEM);
    expect(text(cert('contract'))).toBe('没有 live 文件');
  });

  it('?quizs=empty：两套都没有，coordinator 与 contract 都是纯文字「没有 live 文件」', async () => {
    await mount('#/roles?quizs=empty');
    for (const post of ['coordinator', 'contract']) {
      expect(text(cert(post)), post + ' 对不上任何一套').toBe('没有 live 文件');
      expect(tagIn(cert(post)), post + ' 没有 Tag').toBe(null);
    }
  });

  it('证书格里没有可聚焦元素、没有 role 属性、没有内联 style', async () => {
    await mount('#/roles');
    for (const post of POSTS) {
      const e = cert(post);
      expect(qa(e, 'button, a, [tabindex]').length, post + ' 证书格不该有可聚焦元素').toBe(0);
      expect(qa(e, '[role]').length, post + ' 证书格不该有 role 属性').toBe(0);
      expect(qa(e, '[style]').length, post + ' 证书格不该有内联 style').toBe(0);
    }
  });
});

// ---- 真实模式（注入假服务）----

const ROLES = { active_preset: 'default', roles: [
  { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' }, differs_from_preset: false },
] };
const PROFILES = { profiles: [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };
const HUB_ROWS = [
  { post: 'coordinator', source: 'default', allowed_adapters: ['quizs', 'pi'], adapter: 'quizs', provider: 'deepseek', model: null, thinking: 'high', profile: null, runtime: null, fallback: null },
  { post: 'planner', source: 'default', allowed_adapters: ['claude-code'], adapter: 'claude-code', provider: null, model: null, thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'contract', source: 'config', allowed_adapters: ['pi', 'quizs'], adapter: 'quizs', provider: 'minimax', model: null, thinking: 'high', profile: 'quizs-m3', runtime: 'quizs', fallback: null },
  { post: 'gate', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null, model: null, thinking: 'high', profile: null, runtime: null, fallback: null },
  { post: 'audit', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null, model: null, thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'exec', source: 'config', allowed_adapters: ['pi'], adapter: 'pi', provider: 'bb', model: null, thinking: 'high', profile: 'step-high', runtime: 'pi', fallback: null },
];

function makeFake(live: () => Promise<Envelope<unknown>>, calls: string[] = []): LiveClient {
  return {
    get<T>(path: string): Promise<Envelope<T>> {
      calls.push(path);
      if (path === '/api/v1/quizs/live') return live() as Promise<Envelope<T>>;
      if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv({ posts: HUB_ROWS }, ['config', 'hub', 'show', '--json']) as Envelope<T>);
      if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES) as Envelope<T>);
      if (path === '/api/v1/profiles') return Promise.resolve(okEnv(PROFILES) as Envelope<T>);
      if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS) as Envelope<T>);
      if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }) as Envelope<T>);
      return Promise.resolve(okEnv(null) as Envelope<T>);
    },
    post<T>(): Promise<{ status: number; body: Envelope<T> }> {
      return Promise.resolve({ status: 200, body: okEnv(null) as Envelope<T> });
    },
    getRaw<T>(): Promise<{ status: number; body: T }> {
      return Promise.resolve({ status: 404, body: null as unknown as T });
    },
  };
}

describe('真实模式：证书格照 live 的实况（合同第 7 节第 4—7 条）', () => {
  it('失败信封 → 两个 quizs 格都是纯文字「读不出」，title 是 messages；整表六行、四张角色卡、profile 表照常', async () => {
    setLiveClientForTests(makeFake(() => Promise.resolve(failEnv(['读不到 live', '第二行']))));
    await mount('#/roles');
    for (const post of ['coordinator', 'contract']) {
      const e = cert(post);
      expect(text(e), post + ' 失败信封是纯文字').toBe('读不出');
      expect(tagIn(e), post + ' 没有 Tag').toBe(null);
      const titled = e.querySelector('[title]');
      expect(titled, post + ' 应带 title').toBeTruthy();
      expect(titled.getAttribute('title')).toBe('读不到 live\n第二行');
    }
    for (const post of NON_QUIZ) {
      expect(text(cert(post)), post + ' 非 quizs 岗位仍是「—」').toBe('—');
    }
    expect(qa(hubSec(), 'tbody tr').length, '六行照常').toBe(6);
    expect(qa(document, 'article[data-role]').length, '四张角色卡照常').toBe(4);
    expect(qa(document, '[data-page-state]')[0].getAttribute('data-page-state'), '整页 data 态').toBe('data');
  });

  it('live 一直挂起 → 两个 quizs 格都是「读取中」，整张表照常渲染', async () => {
    setLiveClientForTests(makeFake(() => new Promise<Envelope<unknown>>(() => {})));
    await mount('#/roles');
    expect(text(cert('coordinator'))).toBe('读取中');
    expect(text(cert('contract'))).toBe('读取中');
    expect(qa(hubSec(), 'tbody tr').length, '六行照常').toBe(6);
  });

  it('带记号的行 → coordinator Tag「就绪」、contract 用 env 兑底是 Tag「已过期」、其余四行「—」；/api/v1/quizs/live 只请求一次', async () => {
    const calls: string[] = [];
    const rows = { live: [
      { source: 'mailbox', provider: 'deepseek', problem: null, status: { state: 'ready', problem: null, missing: [], certificate: null, profile: null } },
      { source: 'env', provider: null, problem: null, status: { state: 'expired', problem: null, missing: [], certificate: null, profile: null } },
    ] };
    setLiveClientForTests(makeFake(() => Promise.resolve(okEnv(rows)), calls));
    await mount('#/roles');
    const tagC = tagIn(cert('coordinator'));
    expect(tagC, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tagC)).toBe('就绪');
    expect(tagC.getAttribute('data-tone')).toBe('success');
    const tagK = tagIn(cert('contract'));
    expect(tagK, 'contract（minimax）对不上，用 env 兑底').toBeTruthy();
    expect(text(tagK)).toBe('已过期');
    expect(tagK.getAttribute('data-tone')).toBe('danger');
    for (const post of NON_QUIZ) {
      expect(text(cert(post)), post + ' 非 quizs 岗位是「—」').toBe('—');
    }
    expect(calls.filter((p) => p === '/api/v1/quizs/live').length, 'live 只在挂载时读一次').toBe(1);
  });

  it('hub 读失败 → 照旧是失败块，没有「证书」列头也没有证书格；整页仍是 data 态', async () => {
    const client = makeFake(() => Promise.resolve(okEnv({ live: [] })));
    const orig = client.get.bind(client);
    (client as any).get = (path: string) => (path === '/api/v1/hub/roles'
      ? Promise.resolve({ ok: false, exit_code: 2, data: null, output: [], messages: ['内核没有 config hub'], command: ['config', 'hub', 'show', '--json'], elapsed_ms: 0 })
      : (orig as any)(path));
    setLiveClientForTests(client);
    await mount('#/roles');
    const sec = hubSec();
    expect(text(sec)).toContain('没能读到七端岗位');
    expect(qa(sec, 'table').length, '失败时这一组不出表').toBe(0);
    expect(qa(sec, 'thead th').length, '失败时没有列头').toBe(0);
    expect(text(sec), '失败块里没有「证书」').not.toContain('证书');
    expect(qa(sec, 'tbody tr').length, '失败时这一组不渲染表格行').toBe(0);
    expect(qa(sec, 'button').length, '失败时不出重试钮').toBe(0);
    expect(qa(sec, '[role="status"]').length, '失败块里不用 role=status').toBe(0);
    expect(qa(hubSec(), '[role="status"]').length, '七端岗位一组不用 role=status').toBe(0);
    expect(qa(document, '[data-page-state]')[0].getAttribute('data-page-state'), '整页仍是 data 态').toBe('data');
  });
});
