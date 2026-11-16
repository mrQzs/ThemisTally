// 角色与模型纯函数（合同第 5、8 节）：角色名/模式名、角色卡字段归一、profile 被引用、方案角色名标题、差异绑定文字；
// 七端岗位的中文名、可录用 profile 筛选与岗位行归一。
import type { HubPostRow, ProfilesData, RolesData } from '../../api';

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

// 七端岗位的中文名（站主来信 20261113）：coordinator 协调人、planner 规划端、contract 合同端、
// gate 门禁端、audit 审核端、exec 执行端；未知岗位码原样返回。
const HUB_POST_NAMES: Record<string, string> = {
  coordinator: '协调人',
  planner: '规划端',
  contract: '合同端',
  gate: '门禁端',
  audit: '审核端',
  exec: '执行端',
};

export function hubPostName(code: string): string {
  return HUB_POST_NAMES[code] ?? code;
}

type LooseProfile = { id: string; adapter?: string | null };

/** 只留 adapter 非空且在允许名单里的 profile，按输入顺序返回它们的 id；名单为空则结果为空。 */
export function allowedProfiles(
  profiles: readonly ProfilesData['profiles'][number][],
  allowedAdapters: readonly string[],
): string[] {
  const allowed = new Set(allowedAdapters);
  return profiles
    .map((p) => p as unknown as LooseProfile)
    .filter((p) => typeof p.adapter === 'string' && allowed.has(p.adapter))
    .map((p) => p.id);
}

// 替补候选（内核硬规则 scripts/kit_roles.py:331-333）：只有主选适配器是 quizs 时才谈得上替补，替补自己不能是
// quizs，且替补也要在该岗位的允许名单里。主选不是 quizs、查不到或 adapter 非字符串、允许名单去掉 quizs 后为
// 空时，都没有替补候选。
export function hubFallbackCandidates(
  profiles: readonly ProfilesData['profiles'][number][],
  allowedAdapters: readonly string[],
  mainProfileId: string,
): string[] {
  const main = profiles.map((p) => p as unknown as LooseProfile).find((p) => p.id === mainProfileId);
  if (main == null || main.adapter !== 'quizs') return [];
  return allowedProfiles(profiles, allowedAdapters.filter((a) => a !== 'quizs'));
}

export interface HubPostFallbackInfo {
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile: string | null;
  runtime: string | null;
}

export interface HubPostInfo {
  post: string;
  source: 'default' | 'config';
  allowedAdapters: string[];
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile: string | null;
  runtime: string | null;
  fallback: HubPostFallbackInfo | null;
}

type RawFallback = {
  adapter?: unknown;
  provider?: unknown;
  model?: unknown;
  thinking?: unknown;
  profile?: unknown;
  runtime?: unknown;
};

// 替补归一：adapter/provider/model/thinking 之外，缺 profile/runtime 键时补成 null（四键替补 → 六键）。
function normalizeFallback(fb: RawFallback): HubPostFallbackInfo {
  return {
    adapter: typeof fb.adapter === 'string' ? fb.adapter : null,
    provider: typeof fb.provider === 'string' ? fb.provider : null,
    model: typeof fb.model === 'string' ? fb.model : null,
    thinking: typeof fb.thinking === 'string' ? fb.thinking : null,
    profile: typeof fb.profile === 'string' ? fb.profile : null,
    runtime: typeof fb.runtime === 'string' ? fb.runtime : null,
  };
}

type RawHubPost = {
  post?: unknown;
  source?: unknown;
  allowed_adapters?: unknown;
  adapter?: unknown;
  provider?: unknown;
  model?: unknown;
  thinking?: unknown;
  profile?: unknown;
  runtime?: unknown;
  fallback?: unknown;
};

/** 把 api 的七端岗位行归一成固定字段，缺键按 null 处理；替补缺 profile/runtime 键也归一成 null。 */
export function normalizeHubPost(raw: HubPostRow): HubPostInfo {
  const r = raw as unknown as RawHubPost;
  const fb = r.fallback;
  return {
    post: typeof r.post === 'string' ? r.post : '',
    source: r.source === 'config' ? 'config' : 'default',
    allowedAdapters: Array.isArray(r.allowed_adapters)
      ? r.allowed_adapters.filter((a): a is string => typeof a === 'string')
      : [],
    adapter: typeof r.adapter === 'string' ? r.adapter : null,
    provider: typeof r.provider === 'string' ? r.provider : null,
    model: typeof r.model === 'string' ? r.model : null,
    thinking: typeof r.thinking === 'string' ? r.thinking : null,
    profile: typeof r.profile === 'string' ? r.profile : null,
    runtime: typeof r.runtime === 'string' ? r.runtime : null,
    fallback: fb != null && typeof fb === 'object' ? normalizeFallback(fb as RawFallback) : null,
  };
}
