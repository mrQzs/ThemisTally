// 七端岗位替补候选纯函数测试（合同第 9 步）：hubFallbackCandidates 的边界（主选 quizs → 允许名单去掉 quizs 的
// 那几个；非 quizs、查不到、adapter 非字符串、名单为空都空；候选不含 quizs、不出允许名单），并各点一条确认
// allowedProfiles 与 hubPostName 的既有行为没变。替补候选为空时表单的替补下拉只有「不设替补」一项且禁用
// （Behavior contract），但那是组件的取舍，这里只测纯函数。
import { describe, expect, it } from 'vitest';
import { allowedProfiles, hubFallbackCandidates, hubPostName } from '../src/pages/readonly1/roles-logic';

const PROFILES = [
  { id: 'q1', runtime: 'quizs', adapter: 'quizs', provider: 'a', model: 'm', options: {}, credential_env: [] },
  { id: 'p1', runtime: 'pi', adapter: 'pi', provider: 'b', model: 'm', options: {}, credential_env: [] },
  { id: 'q2', runtime: 'quizs', adapter: 'quizs', provider: 'c', model: 'm', options: {}, credential_env: [] },
  { id: 'p2', runtime: 'pi', adapter: 'pi', provider: 'd', model: 'm', options: {}, credential_env: [] },
  { id: 'x1', runtime: 'codex', adapter: 'codex', provider: 'e', model: 'm', options: {}, credential_env: [] },
  { id: 'n1', runtime: 'ghost', adapter: null, provider: 'f', model: 'm', options: {}, credential_env: [] },
  { id: 'm1', runtime: 'ghost', provider: 'g', model: 'm', options: {}, credential_env: [] },
] as any;

describe('hubFallbackCandidates', () => {
  it('主选是 quizs：候选是允许名单去掉 quizs 的那几个（按输入顺序），不含 quizs、不出允许名单', () => {
    expect(hubFallbackCandidates(PROFILES, ['quizs', 'pi', 'codex'], 'q2')).toEqual(['p1', 'p2', 'x1']);
  });
  it('主选不是 quizs（pi）时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi', 'quizs'], 'p1')).toEqual([]);
  });
  it('主选查不到时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi', 'quizs'], 'zz-none')).toEqual([]);
  });
  it('主选的 adapter 不是字符串（null 或缺键）时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi'], 'n1')).toEqual([]);
    expect(hubFallbackCandidates(PROFILES, ['pi'], 'm1')).toEqual([]);
  });
  it('允许名单为空、或去掉 quizs 后没有候选时为空', () => {
    expect(hubFallbackCandidates(PROFILES, [], 'q1')).toEqual([]);
    expect(hubFallbackCandidates(PROFILES, ['quizs'], 'q1')).toEqual([]);
  });
});

describe('allowedProfiles 既有行为没变', () => {
  it('只留 adapter 非空且在允许名单里的，按输入顺序；名单为空则空', () => {
    expect(allowedProfiles(PROFILES, ['pi'])).toEqual(['p1', 'p2']);
    expect(allowedProfiles(PROFILES, ['quizs', 'pi'])).toEqual(['q1', 'p1', 'q2', 'p2']);
    expect(allowedProfiles(PROFILES, [])).toEqual([]);
  });
});

describe('hubPostName 既有行为没变', () => {
  it('六个中文名，未知码原样', () => {
    expect(hubPostName('coordinator')).toBe('协调人');
    expect(hubPostName('planner')).toBe('规划端');
    expect(hubPostName('contract')).toBe('合同端');
    expect(hubPostName('gate')).toBe('门禁端');
    expect(hubPostName('audit')).toBe('审核端');
    expect(hubPostName('exec')).toBe('执行端');
    expect(hubPostName('zz-9')).toBe('zz-9');
  });
});
