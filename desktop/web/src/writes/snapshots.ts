// 写操作的快照投影与比较（第五节）：预览阶段与重读阶段各读一次，投影只留参与比对的字段，
// 会自己变的字段（时间、计数、运行中的 attempt、探测与核验字段、信封的 command/output/messages、整份 history）都不进来。
import type { PluginsData, PresetsData, RolesData } from '../api';

export interface PresetSnapshot {
  active_preset: string;
  presets: Array<{ name: string; active: boolean }>;
  roles: Array<{ role: string; explicit: boolean; binding: unknown }>;
}

export interface PluginSnapshot {
  plugins: Array<{ id: string; enabled: string }>;
}

function byKey<T extends Record<string, unknown>>(key: string) {
  return (a: T, b: T) => String(a[key]).localeCompare(String(b[key]));
}

/** preset.use 的快照：active_preset、presets[].{name,active}（按 name）、roles[].{role,explicit,binding}（按 role）。 */
export function presetSnapshot(presets: PresetsData, roles: RolesData): PresetSnapshot {
  return {
    active_preset: presets.active_preset,
    presets: presets.presets
      .map((p) => ({ name: p.name, active: p.active }))
      .sort(byKey<{ name: string }>('name')),
    roles: roles.roles
      .map((r) => ({ role: r.role, explicit: r.explicit, binding: r.binding }))
      .sort(byKey<{ role: string }>('role')),
  };
}

/** plugin.enable/disable 的快照：plugins[].{id,enabled}（按 id；enabled 是夹具里的字符串）。 */
export function pluginSnapshot(plugins: PluginsData): PluginSnapshot {
  return {
    plugins: (plugins.plugins ?? [])
      .map((p) => ({ id: p.id, enabled: p.enabled }))
      .sort(byKey<{ id: string }>('id')),
  };
}

/** 两个快照是否相同：投影已排序、只含比对字段，JSON 相等即相同（纯函数）。 */
export function sameSnapshot(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
