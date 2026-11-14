// 七端岗位纯函数测试（合同第 10 节）：hubPostName 的六个中文名与未知岗位、allowedProfiles 的边界
// （adapter 为 null 不算、不在允许名单不算、允许名单为空则空）、normalizeHubPost 的缺键归 null。
import { describe, expect, it } from 'vitest';
import { allowedProfiles, hubPostName, normalizeHubPost } from '../src/pages/readonly1/roles-logic';

describe('hubPostName', () => {
  it('六个中文名，未知岗位码原样', () => {
    expect(hubPostName('coordinator')).toBe('协调人');
    expect(hubPostName('planner')).toBe('规划端');
    expect(hubPostName('contract')).toBe('合同端');
    expect(hubPostName('gate')).toBe('门禁端');
    expect(hubPostName('audit')).toBe('审核端');
    expect(hubPostName('exec')).toBe('执行端');
    expect(hubPostName('unknown-post')).toBe('unknown-post');
  });
});

describe('allowedProfiles', () => {
  const profiles = [
    { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: {}, credential_env: [] },
    { id: 'quiz-one', runtime: 'quizs', adapter: 'quizs', provider: 'deepseek', model: 'deepseek-flash', options: {}, credential_env: [] },
    { id: 'no-adapter', runtime: 'ghost', adapter: null, provider: 'x', model: 'y', options: {}, credential_env: [] },
    { id: 'cc-one', runtime: 'cc', adapter: 'claude-code', provider: 'z', model: 'w', options: {}, credential_env: [] },
  ] as any;

  it('coordinator 同时许 quizs 与 pi（按输入顺序）', () => {
    expect(allowedProfiles(profiles, ['quizs', 'pi'])).toEqual(['step-high', 'quiz-one']);
  });
  it('planner 只许 claude-code', () => {
    expect(allowedProfiles(profiles, ['claude-code'])).toEqual(['cc-one']);
  });
  it('adapter 为 null（runtime 没登记）不算', () => {
    expect(allowedProfiles([profiles[2]], ['pi'])).toEqual([]);
  });
  it('不在允许名单不算', () => {
    expect(allowedProfiles(profiles, ['codex'])).toEqual([]);
  });
  it('允许名单为空则结果为空', () => {
    expect(allowedProfiles(profiles, [])).toEqual([]);
  });
});

describe('normalizeHubPost', () => {
  it('缺键按 null 归一', () => {
    const n: any = normalizeHubPost({ post: 'gate', source: 'default', allowed_adapters: ['pi'] } as any);
    expect(n.post).toBe('gate');
    expect(n.source).toBe('default');
    expect(n.allowedAdapters).toEqual(['pi']);
    ['adapter', 'provider', 'model', 'thinking', 'profile', 'runtime', 'fallback'].forEach((k) => {
      expect(n[k], k + ' 缺键应归 null').toBeNull();
    });
  });
  it('四键替补归一后补出 profile/runtime 两个 null', () => {
    const n: any = normalizeHubPost({
      post: 'coordinator', source: 'default', allowed_adapters: ['quizs', 'pi'], adapter: 'quizs',
      provider: 'deepseek', model: 'deepseek-flash', thinking: 'high', profile: null, runtime: null,
      fallback: { adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high' },
    } as any);
    expect(n.fallback).toEqual({ adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high', profile: null, runtime: null });
  });
  it('六键替补原样保留', () => {
    const fb = { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' };
    const n: any = normalizeHubPost({
      post: 'contract', source: 'config', allowed_adapters: ['pi', 'quizs'], adapter: 'quizs',
      provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high', profile: 'quizs-m3', runtime: 'quizs', fallback: fb,
    } as any);
    expect(n.fallback).toEqual(fb);
    expect(n.profile).toBe('quizs-m3');
    expect(n.runtime).toBe('quizs');
  });
});
