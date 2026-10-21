// 角色与模型纯函数（合同第 5 节）：角色名/模式名、角色卡字段归一、profile 被引用、方案角色名标题、差异绑定文字。
import type { RolesData } from '../../api';

const ROLE_NAMES: Record<string, string> = {
  planning_review: '规划审核端',
  contract: '合同端',
  execution: '执行端',
  scheduler_agent: '调度代理',
};

export function roleName(code: string): string {
  return ROLE_NAMES[code] ?? code;
}

const MODE_NAMES: Record<string, string> = {
  headless: '无头',
  interactive_host: '交互式宿主',
  manual: '手工',
  disabled: '关闭',
};

export function modeName(mode: string): string {
  return MODE_NAMES[mode] ?? mode;
}

type RawRole = {
  role: string;
  explicit?: boolean;
  binding?: { mode?: string; host?: string; profile?: string };
  differs_from_preset?: boolean;
  profile?: string | null;
  runtime?: string | null;
  adapter?: string | null;
  provider?: string | null;
  model?: string | null;
  thinking?: string | null;
  connected?: boolean | null;
  effort_effective?: string | null;
};

export interface RoleInfo {
  role: string;
  explicit: boolean;
  differs: boolean;
  mode: string;
  host: string | null;
  bindingProfile: string | null;
  profile: string | null;
  runtime: string | null;
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  connected: boolean;
  effortEffective: string | null;
}

/** 把 api 的角色行（联合类型）归一成固定字段，本地收窄。 */
export function normalizeRole(raw: RolesData['roles'][number]): RoleInfo {
  const r = raw as unknown as RawRole;
  const binding = r.binding ?? {};
  return {
    role: r.role,
    explicit: r.explicit === true,
    differs: r.differs_from_preset === true,
    mode: typeof binding.mode === 'string' ? binding.mode : '',
    host: typeof binding.host === 'string' ? binding.host : null,
    bindingProfile: typeof binding.profile === 'string' ? binding.profile : null,
    profile: typeof r.profile === 'string' ? r.profile : null,
    runtime: typeof r.runtime === 'string' ? r.runtime : null,
    adapter: typeof r.adapter === 'string' ? r.adapter : null,
    provider: typeof r.provider === 'string' ? r.provider : null,
    model: typeof r.model === 'string' ? r.model : null,
    thinking: typeof r.thinking === 'string' ? r.thinking : null,
    connected: r.connected === true,
    effortEffective: typeof r.effort_effective === 'string' ? r.effort_effective : null,
  };
}

/** 无头角色解析出的 profile：role.profile 否则 binding.profile。 */
export function resolvedProfile(role: RoleInfo): string | null {
  return role.profile ?? role.bindingProfile;
}

/** 引用某 profile 的当前无头角色名，用、连；没有返回「—」。 */
export function profileRefs(roles: readonly RoleInfo[], profileId: string): string {
  const names = roles
    .filter((r) => r.mode === 'headless' && resolvedProfile(r) === profileId)
    .map((r) => roleName(r.role));
  return names.length > 0 ? names.join('、') : '—';
}

/** 方案「包含的角色」title：角色码映射中文名，用、连。 */
export function presetRoleTitle(codes: readonly string[]): string {
  return codes.map(roleName).join('、');
}

/** 差异面板里的绑定文字：无头 · <profile>、交互式宿主 · <host>、手工、关闭、未知原样、缺失「—」。 */
export function bindingText(binding: unknown): string {
  if (binding == null || typeof binding !== 'object') return '—';
  const o = binding as { mode?: string; host?: string; profile?: string };
  if (typeof o.mode !== 'string') return '—';
  if (o.mode === 'headless') return `无头 · ${o.profile ?? '—'}`;
  if (o.mode === 'interactive_host') return `交互式宿主 · ${o.host ?? '—'}`;
  if (o.mode === 'manual') return '手工';
  if (o.mode === 'disabled') return '关闭';
  return o.mode;
}
