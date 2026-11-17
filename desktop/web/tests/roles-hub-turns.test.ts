// 七端岗位「这一回合拿到了什么」的纯逻辑（合同第 11 步）：roles-logic 的九个纯函数逐字口径、normalizeHubPost 的
// turn/lastTurn 归一边界；真实模式（注入只回 posts 的假客户端）确认旧服务缺键时三个新列都是「—」、页面不出现桩的值。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import { createElement } from 'react';
import App from '../src/App';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';
import {
  hubBudgetText,
  hubEffortDiffers,
  hubEffortState,
  hubEffortTriple,
  hubFallbackExcerpt,
  hubLastTurnMark,
  hubLastTurnText,
  hubMib,
  hubTimeoutText,
  normalizeHubPost,
  type HubPostBudgetInfo,
  type HubPostLastTurnInfo,
  type HubPostTurnInfo,
} from '../src/pages/readonly1/roles-logic';

const budgets = (o: Partial<HubPostBudgetInfo> = {}): HubPostBudgetInfo => ({
  max_requests: 32,
  max_tool_calls: 48,
  max_input_bytes: 2097152,
  max_response_bytes: 8388608,
  max_object_bytes: 8388608,
  ...o,
});
const turn = (o: Partial<HubPostTurnInfo> = {}): HubPostTurnInfo => ({
  timeout_seconds: 600,
  tools: ['read', 'grep', 'find', 'ls'],
  budgets: null,
  ...o,
});
const lt = (o: Partial<HubPostLastTurnInfo> = {}): HubPostLastTurnInfo => ({
  at: '2026-11-15T08:00:00Z',
  adapter: 'quizs',
  models: ['deepseek-flash'],
  profile: null,
  thinking: { requested: 'high', mapped: 'high', effective: null },
  fallback: null,
  ...o,
});
const BASE_ROW = {
  post: 'gate',
  source: 'default' as const,
  allowed_adapters: ['pi'],
  adapter: 'pi',
  provider: null,
  model: null,
  thinking: 'high',
  profile: null,
  runtime: null,
  fallback: null,
};

describe('normalizeHubPost 的 turn/lastTurn 归一', () => {
  it('旧服务缺 turn/last_turn 两个键、或值不是对象 → 都按 null', () => {
    expect(normalizeHubPost(BASE_ROW).turn).toBe(null);
    expect(normalizeHubPost(BASE_ROW).lastTurn).toBe(null);
    expect(normalizeHubPost({ ...BASE_ROW, turn: 'x' } as any).turn).toBe(null);
    expect(normalizeHubPost({ ...BASE_ROW, last_turn: 7 } as any).lastTurn).toBe(null);
  });

  it('turn：budgets 缺键 → null；tools 不是数组 → []；timeout 不是数 → null', () => {
    const one = normalizeHubPost({ ...BASE_ROW, turn: { timeout_seconds: 2400, tools: 'no' } } as any);
    expect(one.turn?.timeout_seconds).toBe(2400);
    expect(one.turn?.tools).toEqual([]);
    expect(one.turn?.budgets).toBe(null);
    const two = normalizeHubPost({ ...BASE_ROW, turn: { timeout_seconds: 'x', tools: [], budgets: 'y' } } as any);
    expect(two.turn?.timeout_seconds).toBe(null);
    expect(two.turn?.budgets).toBe(null);
  });

  it('last_turn：models 不是数组 → []；thinking 缺键 → 三个档位都 null；fallback 不是字符串 → null', () => {
    const one = normalizeHubPost({
      ...BASE_ROW,
      last_turn: { at: '2026-11-15T08:00:00Z', adapter: 'pi', models: 'no', profile: 3, thinking: 'x', fallback: 9 },
    } as any);
    expect(one.lastTurn?.models).toEqual([]);
    expect(one.lastTurn?.thinking).toEqual({ requested: null, mapped: null, effective: null });
    expect(one.lastTurn?.fallback).toBe(null);
    expect(one.lastTurn?.profile).toBe(null);
  });
});

describe('hubTimeoutText', () => {
  it('600 → 10 分钟、2400 → 40 分钟、45 → 45 秒；null 与 timeout 为 null 都是 —', () => {
    expect(hubTimeoutText(turn())).toBe('10 分钟 · read、grep、find、ls');
    expect(hubTimeoutText(turn({ timeout_seconds: 2400 }))).toBe('40 分钟 · read、grep、find、ls');
    expect(hubTimeoutText(turn({ timeout_seconds: 45 }))).toBe('45 秒 · read、grep、find、ls');
    expect(hubTimeoutText(null)).toBe('—');
    expect(hubTimeoutText(turn({ timeout_seconds: null }))).toBe('—');
  });

  it('工具为空数组时只给时限那一段', () => {
    expect(hubTimeoutText(turn({ tools: [] }))).toBe('10 分钟');
    expect(hubTimeoutText(turn({ timeout_seconds: 2400, tools: [] }))).toBe('40 分钟');
    expect(hubTimeoutText(turn({ timeout_seconds: 45, tools: [] }))).toBe('45 秒');
  });
});

describe('hubMib 与 hubBudgetText', () => {
  it('hubMib：2097152 → 2、8388608 → 8、null → —', () => {
    expect(hubMib(2097152)).toBe('2');
    expect(hubMib(8388608)).toBe('8');
    expect(hubMib(null)).toBe('—');
  });

  it('hubBudgetText：null → —；整句逐字；任一项 null 时该项写 —', () => {
    expect(hubBudgetText(null)).toBe('—');
    expect(hubBudgetText(budgets())).toBe('请求 32 · 工具调用 48 · 2 / 8 / 8 MiB');
    expect(hubBudgetText(budgets({ max_requests: 128, max_tool_calls: 128 }))).toBe('请求 128 · 工具调用 128 · 2 / 8 / 8 MiB');
    expect(hubBudgetText(budgets({ max_requests: null, max_input_bytes: null }))).toBe('请求 — · 工具调用 48 · — / 8 / 8 MiB');
  });
});

describe('hubEffortTriple / hubEffortDiffers / hubEffortState', () => {
  it('三值逐字；effective 是逗号连起来的多个档位时用「、」连', () => {
    expect(hubEffortTriple(null)).toBe('—');
    expect(hubEffortTriple(lt())).toBe('要求 high · 映射 high · 生效 —');
    expect(hubEffortTriple(lt({ thinking: { requested: 'max', mapped: null, effective: 'max' } }))).toBe('要求 max · 映射 — · 生效 max');
    expect(hubEffortTriple(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high,medium' } })))
      .toBe('要求 high · 映射 high · 生效 high、medium');
    expect(hubEffortTriple(lt({ thinking: { requested: 'high', mapped: null, effective: '' } })))
      .toBe('要求 high · 映射 — · 生效 —');
  });

  it('hubEffortDiffers：requested 为 null 不判；effective 任一段不同即不同；无段时看 mapped', () => {
    expect(hubEffortDiffers(lt({ thinking: { requested: null, mapped: 'max', effective: null } }))).toBe(false);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high,medium' } }))).toBe(true);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high' } }))).toBe(false);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'max', effective: null } }))).toBe(true);
  });

  it('hubEffortState：none / unknown / same / differs', () => {
    expect(hubEffortState(null)).toBe('none');
    expect(hubEffortState(lt({ thinking: { requested: null, mapped: null, effective: null } }))).toBe('none');
    expect(hubEffortState(lt())).toBe('unknown');
    expect(hubEffortState(lt({ thinking: { requested: 'max', mapped: null, effective: 'max' } }))).toBe('same');
    expect(hubEffortState(lt({ thinking: { requested: 'high', mapped: null, effective: 'high,medium' } }))).toBe('differs');
  });
});

describe('hubLastTurnText / hubLastTurnMark', () => {
  it('文本：时刻 · 实际载体 · 模型；models 空数组写 —；null 段写 —', () => {
    expect(hubLastTurnText(null)).toBe('—');
    expect(hubLastTurnText(lt())).toBe('2026-11-15T08:00:00Z · quizs · deepseek-flash');
    expect(hubLastTurnText(lt({ models: [] }))).toBe('2026-11-15T08:00:00Z · quizs · —');
    expect(hubLastTurnText(lt({ at: null, adapter: null }))).toBe('— · — · deepseek-flash');
  });

  it('标记：有 fallback → 退回替补；载体与绑定不同 → 与当前绑定不同；其余 null', () => {
    expect(hubLastTurnMark(null, 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt({ fallback: '读不出资格证书' }), 'quizs')).toBe('退回替补');
    expect(hubLastTurnMark(lt(), 'pi')).toBe('与当前绑定不同');
    expect(hubLastTurnMark(lt(), 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt({ adapter: null }), 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt(), null)).toBe(null);
  });
});

describe('hubFallbackExcerpt', () => {
  it('null → 两段空串；短句原样；长句 shown 是前 20 个字加 …、full 是全文', () => {
    expect(hubFallbackExcerpt(null)).toEqual({ shown: '', full: '' });
    expect(hubFallbackExcerpt('读不出资格证书')).toEqual({ shown: '读不出资格证书', full: '读不出资格证书' });
    const long = '读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json';
    expect(hubFallbackExcerpt(long)).toEqual({ shown: `${long.slice(0, 20)}…`, full: long });
  });
});

// ---- 真实模式（注入假服务）：旧服务没有 turn/last_turn 两个键 ----

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
async function flush(): Promise<void> {
  for (let i = 0; i < 12; i += 1) await act(async () => {
    await Promise.resolve();
  });
}
function okEnv(data: any): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 0 };
}
function hubTable(): any {
  const page = document.querySelector('[data-page="roles"]');
  const sec = qa(page, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === '七端岗位' : false;
  });
  return sec ? sec.querySelector('table[aria-label="七端岗位"]') : null;
}
function hubCells(): Record<string, Record<string, any>> {
  const table = hubTable();
  const heads = qa(table, 'thead th').map(text);
  const out: Record<string, Record<string, any>> = {};
  qa(table, 'tbody tr').forEach((tr: any) => {
    const post = tr.getAttribute('data-post');
    out[post] = {};
    qa(tr, 'td').forEach((td: any, i: number) => {
      out[post][heads[i]] = td;
    });
  });
  return out;
}

const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];
const THINK: Record<string, string> = {
  coordinator: 'high', planner: 'max', contract: 'high', gate: 'high', audit: 'max', exec: 'high',
};
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
  location.hash = '';
});

describe('真实模式：旧服务缺 turn/last_turn', () => {
  it('三个新列都是 —、思考档位仍是 EffortPair 的 unknown、页面不出现桩的值', async () => {
    const rows = POSTS.map((post) => ({
      post,
      source: 'default',
      allowed_adapters: ['pi'],
      adapter: 'pi',
      provider: null,
      model: null,
      thinking: THINK[post],
      profile: null,
      runtime: null,
      fallback: null,
    }));
    const client = {
      get(path: string) {
        if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv({ posts: rows }));
        if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES));
        if (path === '/api/v1/profiles') return Promise.resolve(okEnv(PROFILES));
        if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS));
        if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }));
        return Promise.resolve(okEnv(null));
      },
    };
    setLiveClientForTests(client as any);
    location.hash = '#/roles';
    render(createElement(App));
    await flush();
    const cells = hubCells();
    for (const post of POSTS) {
      expect(text(cells[post]['时限与工具']), post + ' 时限与工具').toBe('—');
      expect(text(cells[post]['预算']), post + ' 预算').toBe('—');
      expect(text(cells[post]['最近一回合']), post + ' 最近一回合').toBe('—');
      const effort = cells[post]['思考档位'].querySelector('.tt-effort');
      expect(effort.getAttribute('data-state'), post + ' data-state').toBe('unknown');
      expect(text(effort), post + ' EffortPair 文字').toBe('要求 ' + THINK[post] + ' · 生效 未知');
    }
    const page = text(document.body);
    expect(page).not.toContain('10 分钟');
    expect(page).not.toContain('请求 32');
    expect(page).not.toContain('2026-11-15T08:00:00Z');
  });
});
