// 快照投影与比较（合同第五节）的纯函数自测：只改被排除的字段仍相同（M8），改 active_preset / binding / enabled 则不同。
import { describe, expect, it } from 'vitest';
import type { PluginsData, PresetsData, RolesData } from '../src/api';
import { pluginSnapshot, presetSnapshot, sameSnapshot } from '../src/writes/snapshots';

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

function roles(over: Partial<RolesData> = {}): RolesData {
  return {
    active_preset: 'default',
    roles: [
      {
        role: 'execution',
        explicit: true,
        binding: { mode: 'headless', profile: 'step-high' },
        differs_from_preset: false,
        profile: 'step-high',
        runtime: 'pi',
        adapter: 'pi',
        provider: 'bb',
        model: 'step-5-preview',
        thinking: 'high',
        connected: true,
        effort_effective: null,
        checked_at: '2026-10-26T00:00:00Z',
      },
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

describe('preset.use 的快照投影', () => {
  it('只留 active_preset、presets[].{name,active} 与 roles[].{role,explicit,binding}，按 key 排序', () => {
    const snap = presetSnapshot(presets(), roles());
    expect(snap.active_preset).toBe('default');
    expect(snap.presets.map((p) => p.name)).toEqual(['default', 'economy']);
    expect(snap.roles.map((r) => r.role)).toEqual(['contract', 'execution']);
    expect(Object.keys(snap.presets[0]).sort()).toEqual(['active', 'name']);
    expect(Object.keys(snap.roles[0]).sort()).toEqual(['binding', 'explicit', 'role']);
  });

  it('源数据换序不影响比较（投影自己按 key 排序）', () => {
    const swappedRoles = roles({ roles: [roles().roles[1], roles().roles[0]] });
    expect(sameSnapshot(presetSnapshot(presets(), roles()), presetSnapshot(presets(), swappedRoles))).toBe(true);
    const swappedPresets = presets({ presets: [presets().presets[1], presets().presets[0]] });
    expect(sameSnapshot(presetSnapshot(presets(), roles()), presetSnapshot(swappedPresets, roles()))).toBe(true);
  });

  it('改 active_preset 或 binding 就不同', () => {
    const base = presetSnapshot(presets(), roles());
    expect(sameSnapshot(base, presetSnapshot(presets({ active_preset: 'economy' }), roles()))).toBe(false);
    const moved = clone(roles());
    (moved.roles[0].binding as { profile: string }).profile = 'step-low';
    expect(sameSnapshot(base, presetSnapshot(presets(), moved))).toBe(false);
  });

  it('只改被排除的字段仍相同：时间、计数、探测与核验字段、信封字段、整份 history（M8）', () => {
    const base = presetSnapshot(presets(), roles());
    const drifted = clone(roles());
    for (const r of drifted.roles) {
      (r as Record<string, unknown>).connected = false;
      (r as Record<string, unknown>).effort_effective = 'high';
      (r as Record<string, unknown>).checked_at = '2026-10-27T00:00:00Z';
      (r as Record<string, unknown>).external_changes = 3;
    }
    const driftedPresets = clone(presets());
    (driftedPresets as Record<string, unknown>).history = [{ id: 1, at: 'x' }];
    (driftedPresets as Record<string, unknown>).updated_ms = 99;
    expect(sameSnapshot(base, presetSnapshot(driftedPresets, drifted))).toBe(true);
  });
});

describe('plugin.enable / plugin.disable 的快照投影', () => {
  it('只留 id 与 enabled（字符串），按 id 排序', () => {
    const snap = pluginSnapshot(plugins());
    expect(snap.plugins.map((p) => p.id)).toEqual(['code-change', 'decisions']);
    expect(snap.plugins.map((p) => p.enabled)).toEqual(['停用', '启用']);
    expect(Object.keys(snap.plugins[0]).sort()).toEqual(['enabled', 'id']);
  });

  it('改 enabled 就不同；只改 lock、version、status、reason 仍相同（M8）', () => {
    const base = pluginSnapshot(plugins());
    const flipped = plugins({
      plugins: plugins().plugins.map((p) => (p.id === 'code-change' ? { ...p, enabled: '启用' } : p)),
    });
    expect(sameSnapshot(base, pluginSnapshot(flipped))).toBe(false);
    const noisy = plugins({
      plugins: plugins().plugins.map((p) => ({
        ...p,
        lock: '漂移',
        version: '2.0.0',
        status: 'DRIFT',
        reason: '锁与内容不一致',
        resource: '不一致',
        missing: ['fs.write'],
      })),
    });
    expect(sameSnapshot(base, pluginSnapshot(noisy))).toBe(true);
  });

  it('插件表为空时投影也是空数组，与「有插件但都被排除字段变化」不混', () => {
    expect(sameSnapshot(pluginSnapshot(plugins({ plugins: [] })), pluginSnapshot(plugins({ plugins: [] })))).toBe(true);
    expect(sameSnapshot(pluginSnapshot(plugins({ plugins: [] })), pluginSnapshot(plugins()))).toBe(false);
  });
});
