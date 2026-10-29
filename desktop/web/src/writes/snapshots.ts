// 写操作的快照投影与比较（第五节）：预览阶段与重读阶段各读一次，投影只留参与比对的字段，
// 会自己变的字段（时间、计数、运行中的 attempt、探测与核验字段、信封的 command/output/messages、整份 history）都不进来。
import type { PluginsData, PresetsData, ProfilesData, RolesData, RuntimesData } from '../api';

export interface PresetSnapshot {
  active_preset: string;
  presets: Array<{ name: string; active: boolean }>;
  roles: Array<{ role: string; explicit: boolean; binding: unknown }>;
}

export interface PluginSnapshot {
  plugins: Array<{ id: string; enabled: string }>;
}

export interface PresetRemoveSnapshot {
  active_preset: string;
  presets: Array<{ name: string; active: boolean }>;
}

export interface ProfileRemoveSnapshot {
  profiles: Array<{ id: string }>;
}

// profile.add / profile.edit 的快照（第七节）：profiles[].{id,runtime,provider,model,options.thinking,credential_env}（按 id 排序）。
// 排除 adapter（由 runtime 推出）与其余字段；options.thinking 取 options?.thinking ?? null（缺省算 null）。
export interface ProfileSnapshot {
  profiles: Array<{
    id: string;
    runtime: unknown;
    provider: unknown;
    model: unknown;
    thinking: string | null;
    credential_env: unknown;
  }>;
}

export interface RuntimeRemoveSnapshot {
  runtimes: Array<{ id: string; adapter: string }>;
}

export interface RollbackSnapshot {
  roles: Array<{ role: string; explicit: boolean; binding: unknown }>;
  presets: { active_preset: string; presets: Array<{ name: string; active: boolean; roles: readonly string[] }> };
  profiles: Array<{ id: string; runtime: unknown; provider: unknown; model: unknown; options: unknown; credential_env: unknown }>;
  runtimes: Array<{ id: string; adapter: string }>;
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

/** preset.remove 的快照：active_preset、presets[].{name,active}（按 name；排除 description 与 presets[].roles）。 */
export function presetRemoveSnapshot(presets: PresetsData): PresetRemoveSnapshot {
  return {
    active_preset: presets.active_preset,
    presets: presets.presets
      .map((p) => ({ name: p.name, active: p.active }))
      .sort(byKey<{ name: string }>('name')),
  };
}

/** profile.remove 的快照：profiles[].id（按 id；排除 runtime/provider/model/options/credential_env/adapter）。 */
export function profileRemoveSnapshot(profiles: ProfilesData): ProfileRemoveSnapshot {
  return {
    profiles: profiles.profiles
      .map((p) => ({ id: p.id }))
      .sort(byKey<{ id: string }>('id')),
  };
}

/** runtime.remove 的快照：runtimes[].{id,adapter}（按 id；排除 source/notes/command，它们随环境变量、本机文件与 PATH 自己变）。 */
export function runtimeRemoveSnapshot(runtimes: RuntimesData): RuntimeRemoveSnapshot {
  return {
    runtimes: runtimes.runtimes
      .map((r) => ({ id: r.id, adapter: r.adapter }))
      .sort(byKey<{ id: string }>('id')),
  };
}

/** profile.add / profile.edit 的快照：profiles[].{id,runtime,provider,model,options.thinking,credential_env}（按 id；排除 adapter 与其余字段）。 */
export function profileSnapshot(profiles: ProfilesData): ProfileSnapshot {
  return {
    profiles: profiles.profiles
      .map((p) => ({
        id: p.id,
        runtime: p.runtime,
        provider: p.provider,
        model: p.model,
        thinking: p.options?.thinking ?? null,
        credential_env: p.credential_env,
      }))
      .sort(byKey<{ id: string }>('id')),
  };
}

/** config.rollback 的快照：五个读函数并行读后各取参与比对的字段（整份 history、status、usage、secrets 与探测/时间字段都不进来）。 */
export function rollbackSnapshot(
  roles: RolesData,
  presets: PresetsData,
  profiles: ProfilesData,
  runtimes: RuntimesData,
  plugins: PluginsData,
): RollbackSnapshot {
  return {
    roles: roles.roles
      .map((r) => ({ role: r.role, explicit: r.explicit, binding: r.binding }))
      .sort(byKey<{ role: string }>('role')),
    presets: {
      active_preset: presets.active_preset,
      presets: presets.presets
        .map((p) => ({ name: p.name, active: p.active, roles: p.roles }))
        .sort(byKey<{ name: string }>('name')),
    },
    profiles: profiles.profiles
      .map((p) => ({ id: p.id, runtime: p.runtime, provider: p.provider, model: p.model, options: p.options, credential_env: p.credential_env }))
      .sort(byKey<{ id: string }>('id')),
    runtimes: runtimes.runtimes
      .map((r) => ({ id: r.id, adapter: r.adapter }))
      .sort(byKey<{ id: string }>('id')),
    plugins: (plugins.plugins ?? [])
      .map((p) => ({ id: p.id, enabled: p.enabled }))
      .sort(byKey<{ id: string }>('id')),
  };
}

/** 两个快照是否相同：投影已排序、只含比对字段，JSON 相等即相同（纯函数）。 */
export function sameSnapshot(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
