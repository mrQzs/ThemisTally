// 岗位快照与前后对比纯逻辑的自测（T044 A 片，D02、D06）：hubSnapshot 的投影与排序、hubChangeLines 的四行文案
// （替补文字、兜底、「默认」标记按侧生效）、hubPostLabel 的六个岗位名与未知码。全部是纯函数，不碰 DOM。
import { describe, expect, it } from 'vitest';
import type { HubChange, HubChangeFallback, HubChangeSide, HubPostRow, HubRolesData } from '../src/api';
import { hubChangeLines, hubPostLabel } from '../src/writes/hubChangeLines';
import { hubSnapshot } from '../src/writes/snapshots';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';

const side = (o: Partial<HubChangeSide> = {}): HubChangeSide => ({
  source: 'config', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null, ...o,
});
const fb = (o: Partial<HubChangeFallback> = {}): HubChangeFallback => ({
  profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, ...o,
});

function row(post: string, over: Partial<HubPostRow> = {}): HubPostRow {
  return {
    post,
    source: 'default',
    allowed_adapters: ['pi'],
    adapter: 'pi',
    provider: 'bb',
    model: 'step-5-preview',
    thinking: 'high',
    profile: null,
    runtime: null,
    fallback: null,
    ...over,
  };
}

describe('hubSnapshot（D02）', () => {
  it('投影只有四字段、按 post 排序、替补的 profile 取不到时是 null', () => {
    const hub: HubRolesData = {
      posts: [
        row('exec', { source: 'config', profile: 'step-high', fallback: null }),
        row('contract', {
          source: 'config', profile: 'quizs-m3',
          fallback: { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' },
        }),
        row('coordinator', { fallback: { adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high' } }),
      ],
    };
    const snap = hubSnapshot(hub);
    expect(snap.posts.map((p) => p.post)).toEqual(['contract', 'coordinator', 'exec']);
    expect(Object.keys(snap.posts[0]).sort()).toEqual(['fallback_profile', 'post', 'profile', 'source']);
    expect(snap.posts[0]).toEqual({ post: 'contract', source: 'config', profile: 'quizs-m3', fallback_profile: 'step-high' });
    // 缺省行的替补只有四键：取不到 profile，按 null 算（不当成空串）。
    expect(snap.posts[1].fallback_profile).toBeNull();
    expect(snap.posts[2]).toEqual({ post: 'exec', source: 'config', profile: 'step-high', fallback_profile: null });
  });

  it('夹具六行的投影与排序照旧（exec 的替补是 null）', () => {
    const snap = hubSnapshot(HUB_ROLES_POSTS);
    expect(snap.posts.map((p) => p.post)).toEqual(['audit', 'contract', 'coordinator', 'exec', 'gate', 'planner']);
    const byPost = Object.fromEntries(snap.posts.map((p) => [p.post, p]));
    expect(byPost.contract.fallback_profile).toBe('step-high');
    expect(byPost.exec.fallback_profile).toBeNull();
    expect(byPost.coordinator.profile).toBeNull();
  });
});

describe('hubChangeLines（D06）', () => {
  const before = side({
    source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs',
    provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
    fallback: fb({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
  });
  const after = side({
    source: 'config', profile: 'step-high', runtime: 'pi', adapter: 'pi',
    provider: 'bb', model: 'step-5-preview', thinking: 'high',
  });

  it('恰好四行、次序固定：运行时/模型/思考档位/替补', () => {
    const lines = hubChangeLines({ post: 'contract', before, after });
    expect(lines).toEqual([
      '运行时：quizs · quizs → pi · pi',
      '模型：minimax/MiniMax-M3.1-Flash → bb/step-5-preview',
      '思考档位：high → high',
      '替补：step-high → —',
    ]);
  });

  it('一侧为 null：该侧全是占位符，且不标「默认」', () => {
    const lines = hubChangeLines({
      post: 'gate',
      before: null,
      after: side({ runtime: 'pi', adapter: 'pi', provider: 'cc-switch-zhipu-glm', model: 'glm-5.3', thinking: 'high' }),
    });
    expect(lines).toEqual([
      '运行时：— · — → pi · pi',
      '模型：—/— → cc-switch-zhipu-glm/glm-5.3',
      '思考档位：— → high',
      '替补：— → —',
    ]);
  });

  it('缺省一侧标「（默认）」：该侧四行都带，含替补行', () => {
    const lines = hubChangeLines({
      post: 'exec',
      before: after,
      after: { source: 'default', profile: null, runtime: null, adapter: 'pi', provider: 'cc-switch-step-fun', model: 'step-5-preview', thinking: 'high', fallback: null },
    });
    expect(lines).toEqual([
      '运行时：pi · pi → — · pi（默认）',
      '模型：bb/step-5-preview → cc-switch-step-fun/step-5-preview（默认）',
      '思考档位：high → high（默认）',
      '替补：— → —（默认）',
    ]);
  });

  it('替补没有 profile 时按 runtime · provider/model 拼，各字段缺就补占位符', () => {
    const lines = hubChangeLines({
      post: 'coordinator',
      before: side({ fallback: fb({ runtime: 'pi', provider: 'dsf', model: 'deepseek-flash' }) }),
      after: side({ fallback: fb({ profile: 'step-high' }) }),
    });
    expect(lines[3]).toBe('替补：pi · dsf/deepseek-flash → step-high');
  });

  it('替补一行两侧都缺：两侧都是占位符', () => {
    const lines = hubChangeLines({ post: 'planner', before: side({ fallback: fb({}) }), after: side({ fallback: null }) });
    expect(lines[3]).toBe('替补：— · —/— → —');
  });
});

describe('hubPostLabel（D06）', () => {
  it('六个岗位给「中文名（岗位码）」', () => {
    expect(hubPostLabel('coordinator')).toBe('协调人（coordinator）');
    expect(hubPostLabel('planner')).toBe('规划端（planner）');
    expect(hubPostLabel('contract')).toBe('合同端（contract）');
    expect(hubPostLabel('gate')).toBe('门禁端（gate）');
    expect(hubPostLabel('audit')).toBe('审核端（audit）');
    expect(hubPostLabel('exec')).toBe('执行端（exec）');
  });

  it('未知岗位码原样返回（不加括号）', () => {
    expect(hubPostLabel('zz-9')).toBe('zz-9');
  });
});
