// 七端岗位页面测试（合同第 10 节）：桩模式下渲染 #/roles，核对七端岗位区块、表结构、六行字段格式、
// 位置（角色卡之后、profile 表之前）、hub 读失败只影响本组、?mock=empty 仍是六行、四个读并行发出。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import App from '../src/App';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

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
function root(page: string): any {
  return document.querySelector(`[data-page="${page}"]`);
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function sectionNamed(rootEl: any, title: string): any {
  return qa(rootEl, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === title : false;
  }) || null;
}
function hubSec(): any {
  return sectionNamed(root('roles'), '七端岗位');
}
function hubTable(): any {
  const sec = hubSec();
  return sec ? sec.querySelector('table[aria-label="七端岗位"]') : null;
}
function hubRows(): Array<Record<string, any>> {
  const t = hubTable();
  if (!t) return [];
  const heads = qa(t, 'thead th').map(text);
  return qa(t, 'tbody tr').map((tr: any) => {
    const o: Record<string, any> = {};
    qa(tr, 'td').forEach((td: any, i: number) => { o[heads[i]] = td; });
    return o;
  });
}
function okEnv(data: any): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 0 };
}
function failEnv(messages: string[], command: string[], exitCode: number): any {
  return { ok: false, exit_code: exitCode, data: null, output: [], messages, command, elapsed_ms: 0 };
}

const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];

const ROLES = { active_preset: 'default', roles: [
  { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' }, differs_from_preset: false },
] };
const PROFILES = { profiles: [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };

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

describe('七端岗位（桩模式渲染 #/roles）', () => {
  it('区块标题「七端岗位」、表 aria-label「七端岗位」、七列列头末尾是「操作」', async () => {
    await mount('#/roles');
    const sec = hubSec();
    expect(sec, '应有标题为「七端岗位」的 section').not.toBeNull();
    expect(sec.querySelector('h2')).toBeTruthy();
    expect(qa(sec, '.common-section__desc').length, '不加次级说明').toBe(0);
    const table = hubTable();
    expect(table, '表应带 aria-label="七端岗位"').not.toBeNull();
    expect(qa(table, 'thead th').map(text)).toEqual(['岗位', '运行时', '模型', '思考档位', '来源', '替补', '操作']);
  });

  it('操作列每行两个入口：改绑定…/恢复缺省…；planner 改绑定…禁用；contract/exec 恢复缺省…可点、其余禁用', async () => {
    await mount('#/roles');
    const rows = hubRows();
    expect(rows.length).toBe(6);
    const bind = '改绑定…';
    const unset = '恢复缺省…';
    POSTS.forEach((post, i) => {
      const buttons = qa(rows[i]['操作'], 'button');
      expect(buttons.length, post + ' 行有两个入口').toBe(2);
      expect(text(buttons[0]), post + ' 主入口恰为「改绑定…」').toBe(bind);
      expect(text(buttons[1]), post + ' 次入口恰为「恢复缺省…」').toBe(unset);
    });
    expect(qa(rows[1]['操作'], 'button')[0].disabled, 'planner 改绑定…禁用').toBe(true);
    for (const i of [0, 2, 3, 4, 5]) {
      expect(qa(rows[i]['操作'], 'button')[0].disabled, POSTS[i] + ' 改绑定…可点').toBe(false);
    }
    expect(qa(rows[2]['操作'], 'button')[1].disabled, 'contract 恢复缺省…可点').toBe(false);
    expect(qa(rows[5]['操作'], 'button')[1].disabled, 'exec 恢复缺省…可点').toBe(false);
    for (const i of [0, 1, 3, 4]) {
      expect(qa(rows[i]['操作'], 'button')[1].disabled, POSTS[i] + ' 恢复缺省…禁用').toBe(true);
    }
  });

  it('六行的 data-post 依次是 coordinator、planner、contract、gate、audit、exec', async () => {
    await mount('#/roles');
    const trs = qa(hubTable(), 'tbody tr');
    expect(trs.length).toBe(6);
    expect(trs.map((tr: any) => tr.getAttribute('data-post'))).toEqual(POSTS);
  });

  it('逐行核对字段格式（岗位、运行时、模型、替补、思考档位、来源）', async () => {
    await mount('#/roles');
    const rows = hubRows();
    expect(rows.length).toBe(6);
    const names = ['协调人', '规划端', '合同端', '门禁端', '审核端', '执行端'];
    const runtimes = ['—（quizs）', '—（claude-code）', 'quizs（quizs）', '—（pi）', '—（pi）', 'pi（pi）'];
    const models = ['deepseek/deepseek-flash', '—/claude-opus-5-5', 'minimax/MiniMax-M3.1-Flash', 'cc-switch-zhipu-glm/glm-5.3', 'minimax/MiniMax-M3.1-Flash', 'bb/step-5-preview'];
    const fallbacks = ['—（pi） · dsf/deepseek-flash', '—', 'step-high · pi（pi） · bb/step-5-preview', '—', '—', '—'];
    const think = ['high', 'max', 'high', 'high', 'max', 'high'];
    POSTS.forEach((post, i) => {
      const row = rows[i];
      expect(text(row['岗位']), post + ' 岗位名').toBe(names[i]);
      expect(text(row['运行时']), post + ' 运行时').toBe(runtimes[i]);
      expect(text(row['模型']), post + ' 模型').toBe(models[i]);
      expect(text(row['替补']), post + ' 替补').toBe(fallbacks[i]);
      const effort = row['思考档位'].querySelector('.tt-effort');
      expect(effort, post + ' 思考档位经 EffortPair').not.toBeNull();
      expect(effort.getAttribute('data-state'), post + ' data-state').toBe('unknown');
      expect(text(effort), post + ' 思考档位文字').toBe('要求 ' + think[i] + ' · 生效 未知');
      const cell = row['来源'];
      if (i === 2 || i === 5) {
        expect(qa(cell, '.tt-tag').length, post + ' 配置行来源不是 Tag').toBe(0);
        expect(text(cell), post + ' 配置行来源是 profile id').toBe(i === 2 ? 'quizs-m3' : 'step-high');
      } else {
        const tag = cell.querySelector('.tt-tag');
        expect(tag, post + ' 缺省行来源是 Tag「默认」').not.toBeNull();
        expect(text(tag)).toBe('默认');
        expect(tag.getAttribute('data-tone')).toBe('neutral');
      }
    });
  });

  it('位置：这一组在角色卡网格之后、profile 表之前', async () => {
    await mount('#/roles');
    const r = root('roles');
    const grid = r.querySelector('.rl-grid');
    const sec = hubSec();
    const prof = sectionNamed(r, 'profile');
    expect(grid && sec && prof).toBeTruthy();
    expect(grid.compareDocumentPosition(sec) & Node.DOCUMENT_POSITION_FOLLOWING, '七端岗位在角色卡网格之后').toBeTruthy();
    expect(sec.compareDocumentPosition(prof) & Node.DOCUMENT_POSITION_FOLLOWING, '七端岗位在 profile 表之前').toBeTruthy();
  });

  it('?mock=empty 仍是六行、整页仍是 data 态', async () => {
    await mount('#/roles?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(qa(hubTable(), 'tbody tr').map((tr: any) => tr.getAttribute('data-post'))).toEqual(POSTS);
  });
});

describe('hub 读失败只影响本组', () => {
  it('只有七端岗位显示失败信封与 messages 的 pre；四张角色卡、profile 表照常；整页仍是 data 态', async () => {
    const client = {
      get(path: string) {
        if (path === '/api/v1/hub/roles') return Promise.resolve(failEnv(['内核没有 config hub', '第二行'], ['config', 'hub', 'show', '--json'], 2));
        if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES));
        if (path === '/api/v1/profiles') return Promise.resolve(okEnv(PROFILES));
        if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS));
        if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }));
        return Promise.resolve(okEnv(null));
      },
    };
    setLiveClientForTests(client as any);
    await mount('#/roles');
    expect(frame().getAttribute('data-page-state'), 'hub 失败不改整页状态').toBe('data');
    const r = root('roles');
    expect(qa(r, 'article[data-role]').length, '四张角色卡照常').toBe(4);
    expect(sectionNamed(r, 'profile'), 'profile 表照常').not.toBeNull();
    const sec = hubSec();
    expect(text(sec)).toContain('没能读到七端岗位：命令 config hub show --json 返回退出码 2。');
    const pre = sec.querySelector('pre');
    expect(pre, 'messages 放进 pre').not.toBeNull();
    expect(text(pre)).toContain('内核没有 config hub');
    expect(qa(sec, 'tbody tr').length, '失败时这一组不渲染表格行').toBe(0);
    expect(qa(sec, 'button').length, '失败时不出重试钮').toBe(0);
  });
});

describe('四个读并行发出', () => {
  it('getRoles 挂起时 getProfiles、getPresets、getHubRoles 也都已发出', async () => {
    const paths: string[] = [];
    const client = {
      get(path: string) {
        paths.push(path);
        if (path === '/api/v1/roles') return new Promise(() => {});
        return Promise.resolve(okEnv(null));
      },
    };
    setLiveClientForTests(client as any);
    await mount('#/roles');
    expect(paths).toContain('/api/v1/roles');
    expect(paths).toContain('/api/v1/profiles');
    expect(paths).toContain('/api/v1/presets');
    expect(paths).toContain('/api/v1/hub/roles');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
  });
});
