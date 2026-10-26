// B 片四个快照投影的纯函数自测（合同第六节）：只改被排除的字段仍相同（B7），改参与比对的字段就不同。
// preset.remove 排除 description 与 presets[].roles；profile.remove 只比 id；
// runtime.remove 只比 id/adapter（排除 source/command/notes）；config.rollback 五个读各取比对字段、与 history 无关。
import { describe, expect, it } from 'vitest';
import type { PluginsData, PresetsData, ProfilesData, RolesData, RuntimesData } from '../src/api';
import {
  presetRemoveSnapshot,
  profileRemoveSnapshot,
  runtimeRemoveSnapshot,
  rollbackSnapshot,
  sameSnapshot,
} from '../src/writes/snapshots';

function presets(over: Partial<PresetsData> = {}): PresetsData {
  return {
    active_preset: 'default',
    presets: [
      { name: 'default', description: '日常', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
      { name: 'economy', description: '省钱', roles: ['execution'], active: false },
    ],
    ...over,
  } as PresetsData;
}

function profiles(over: Partial<ProfilesData> = {}): ProfilesData {
  return {
    profiles: [
      { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
      { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
    ],
    ...over,
  } as ProfilesData;
}

function runtimes(over: Partial<RuntimesData> = {}): RuntimesData {
  return {
    runtimes: [
      { id: 'pi', adapter: 'pi', source: 'local', command: ['a'], notes: [] },
      { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['b'], notes: [] },
    ],
    ...over,
  } as RuntimesData;
}

function roles(over: Partial<RolesData> = {}): RolesData {
  return {
    active_preset: 'default',
    roles: [
      { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false },
      { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
    ],
    ...over,
  } as RolesData;
}

function plugins(over: Partial<PluginsData> = {}): PluginsData {
  return {
    plugins_root_link: false,
    plugins: [
      { id: 'code-change', version: '1.0.0', enabled: '停用', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
      { id: 'decisions', version: '1.0.0', enabled: '启用', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
    ],
    not_installed: [],
    problems: [],
    ...over,
  } as PluginsData;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

describe('preset.remove 的快照投影', () => {
  it('只留 active_preset 与 presets[].{name,active}，按 name 排序', () => {
    const snap = presetRemoveSnapshot(presets());
    expect(snap.active_preset).toBe('default');
    expect(snap.presets.map((p) => p.name)).toEqual(['default', 'economy']);
    expect(Object.keys(snap.presets[0]).sort()).toEqual(['active', 'name']);
  });

  it('只改被排除的字段仍相同：description 与 presets[].roles', () => {
    const base = presetRemoveSnapshot(presets());
    const drifted = clone(presets());
    drifted.presets[0].description = '改了说明';
    drifted.presets[1].roles = ['execution', 'planning_review'];
    expect(sameSnapshot(base, presetRemoveSnapshot(drifted))).toBe(true);
  });

  it('改 name、active 或 active_preset 就不同', () => {
    const base = presetRemoveSnapshot(presets());
    const moved = clone(presets());
    moved.presets[1].active = true;
    expect(sameSnapshot(base, presetRemoveSnapshot(moved))).toBe(false);
    expect(sameSnapshot(base, presetRemoveSnapshot(presets({ active_preset: 'economy' })))).toBe(false);
  });
});

describe('profile.remove 的快照投影', () => {
  it('只留 profiles[].id，按 id 排序', () => {
    const snap = profileRemoveSnapshot(profiles());
    expect(snap.profiles.map((p) => p.id)).toEqual(['step-high', 'step-low']);
    expect(Object.keys(snap.profiles[0])).toEqual(['id']);
  });

  it('只改被排除的字段仍相同：runtime/provider/model/options/credential_env/adapter', () => {
    const base = profileRemoveSnapshot(profiles());
    const drifted = clone(profiles());
    drifted.profiles[0].runtime = 'claude-code';
    drifted.profiles[0].provider = 'aa';
    drifted.profiles[0].model = 'other';
    drifted.profiles[0].options = { thinking: 'low' };
    drifted.profiles[0].credential_env = ['OTHER'];
    drifted.profiles[0].adapter = 'claude-code';
    expect(sameSnapshot(base, profileRemoveSnapshot(drifted))).toBe(true);
  });

  it('改 id 就不同', () => {
    const base = profileRemoveSnapshot(profiles());
    const moved = clone(profiles());
    moved.profiles[1].id = 'step-mid';
    expect(sameSnapshot(base, profileRemoveSnapshot(moved))).toBe(false);
  });
});

describe('runtime.remove 的快照投影', () => {
  it('只留 runtimes[].{id,adapter}，按 id 排序', () => {
    const snap = runtimeRemoveSnapshot(runtimes());
    expect(snap.runtimes.map((r) => r.id)).toEqual(['claude-code', 'pi']);
    const pi = snap.runtimes.find((r) => r.id === 'pi');
    expect(Object.keys(pi as object).sort()).toEqual(['adapter', 'id']);
  });

  it('只改被排除的字段仍相同：source、notes、command', () => {
    const base = runtimeRemoveSnapshot(runtimes());
    const drifted = clone(runtimes());
    drifted.runtimes[0].source = 'env';
    drifted.runtimes[0].command = ['C:/tools/node/node.exe', 'cli.js'];
    drifted.runtimes[0].notes = ['环境变量已设置'];
    expect(sameSnapshot(base, runtimeRemoveSnapshot(drifted))).toBe(true);
  });

  it('改 adapter 就不同（adapter 参与比对）', () => {
    const base = runtimeRemoveSnapshot(runtimes());
    const moved = clone(runtimes());
    moved.runtimes[0].adapter = 'opencode';
    expect(sameSnapshot(base, runtimeRemoveSnapshot(moved))).toBe(false);
  });
});

describe('config.rollback 的快照投影', () => {
  const base = () => rollbackSnapshot(roles(), presets(), profiles(), runtimes(), plugins());

  it('五个读各取参与比对的字段；与比对无关的字段（含 history）不影响', () => {
    const snap = base();
    expect(snap.roles.map((r) => r.role)).toEqual(['contract', 'execution']);
    expect(snap.presets.active_preset).toBe('default');
    expect(snap.presets.presets.map((p) => p.name)).toEqual(['default', 'economy']);
    expect(snap.profiles.map((p) => p.id)).toEqual(['step-high', 'step-low']);
    expect(snap.runtimes.map((r) => r.id)).toEqual(['claude-code', 'pi']);
    expect(snap.plugins.map((p) => p.id)).toEqual(['code-change', 'decisions']);
    // 整份 getHistory 每次写都变，不进快照：挂个 history 字段应被忽略。
    const withHistory = clone(presets());
    (withHistory as Record<string, unknown>).history = [{ number: 43, at: 'x' }];
    expect(sameSnapshot(snap, rollbackSnapshot(roles(), withHistory, profiles(), runtimes(), plugins()))).toBe(true);
  });

  it('改 roles/presets.roles/profiles 的比对字段就不同；改 runtime 的 source 仍相同', () => {
    const snap = base();
    const movedRoles = clone(roles());
    (movedRoles.roles[0].binding as { profile: string }).profile = 'step-low';
    expect(sameSnapshot(snap, rollbackSnapshot(movedRoles, presets(), profiles(), runtimes(), plugins()))).toBe(false);
    const movedPresetRoles = clone(presets());
    movedPresetRoles.presets[1].roles = ['execution', 'contract'];
    expect(sameSnapshot(snap, rollbackSnapshot(roles(), movedPresetRoles, profiles(), runtimes(), plugins()))).toBe(false);
    const movedProfile = clone(profiles());
    movedProfile.profiles[0].provider = 'aa';
    expect(sameSnapshot(snap, rollbackSnapshot(roles(), presets(), movedProfile, runtimes(), plugins()))).toBe(false);
    const movedRuntimeSource = clone(runtimes());
    movedRuntimeSource.runtimes[0].source = 'env';
    expect(sameSnapshot(snap, rollbackSnapshot(roles(), presets(), profiles(), movedRuntimeSource, plugins())), 'runtime 的 source 会自己变，仍相同').toBe(true);
  });
});
