// 角色与模型纯函数（合同第 5、8 节）：角色名/模式名、角色卡字段归一、profile 被引用、方案角色名标题、差异绑定文字；
// 七端岗位的中文名、可录用 profile 筛选与岗位行归一。
import type { Envelope, HubPostRow, ProfilesData, QuizsLiveData, QuizsLiveRow, RolesData } from '../../api';

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
  turn: HubPostTurnInfo | null;
  lastTurn: HubPostLastTurnInfo | null;
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
  turn?: unknown;
  last_turn?: unknown;
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
    turn: normalizeTurn(r.turn),
    lastTurn: normalizeLastTurn(r.last_turn),
  };
}

// 每回合拿到了什么（scripts/kit_roles.py 的 _hub_turn 与 _hub_last_turn）：时限与工具、绑在 quizs 上时才有的
// 预算，以及信箱里最近一个跑完的回合。缺键、类型不对或不是对象一律按 null；tools/models 不是数组时是空数组。
export interface HubPostBudgetInfo {
  max_requests: number | null;
  max_tool_calls: number | null;
  max_input_bytes: number | null;
  max_response_bytes: number | null;
  max_object_bytes: number | null;
}
export interface HubPostTurnInfo {
  timeout_seconds: number | null;
  tools: string[];
  budgets: HubPostBudgetInfo | null;
}
export interface HubPostLastTurnThinkingInfo {
  requested: string | null;
  mapped: string | null;
  effective: string | null;
}
export interface HubPostLastTurnInfo {
  at: string | null;
  adapter: string | null;
  models: string[];
  profile: string | null;
  thinking: HubPostLastTurnThinkingInfo;
  fallback: string | null;
}

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

function stringsOrEmpty(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function normalizeBudgets(raw: unknown): HubPostBudgetInfo | null {
  if (raw == null || typeof raw !== 'object') return null;
  const b = raw as { max_requests?: unknown; max_tool_calls?: unknown; max_input_bytes?: unknown; max_response_bytes?: unknown; max_object_bytes?: unknown };
  return {
    max_requests: numberOrNull(b.max_requests),
    max_tool_calls: numberOrNull(b.max_tool_calls),
    max_input_bytes: numberOrNull(b.max_input_bytes),
    max_response_bytes: numberOrNull(b.max_response_bytes),
    max_object_bytes: numberOrNull(b.max_object_bytes),
  };
}

function normalizeTurn(raw: unknown): HubPostTurnInfo | null {
  if (raw == null || typeof raw !== 'object') return null;
  const t = raw as { timeout_seconds?: unknown; tools?: unknown; budgets?: unknown };
  return {
    timeout_seconds: numberOrNull(t.timeout_seconds),
    tools: stringsOrEmpty(t.tools),
    budgets: normalizeBudgets(t.budgets),
  };
}

function normalizeLastTurnThinking(raw: unknown): HubPostLastTurnThinkingInfo {
  if (raw == null || typeof raw !== 'object') return { requested: null, mapped: null, effective: null };
  const t = raw as { requested?: unknown; mapped?: unknown; effective?: unknown };
  return { requested: textOrNull(t.requested), mapped: textOrNull(t.mapped), effective: textOrNull(t.effective) };
}

function normalizeLastTurn(raw: unknown): HubPostLastTurnInfo | null {
  if (raw == null || typeof raw !== 'object') return null;
  const t = raw as { at?: unknown; adapter?: unknown; models?: unknown; profile?: unknown; thinking?: unknown; fallback?: unknown };
  return {
    at: textOrNull(t.at),
    adapter: textOrNull(t.adapter),
    models: stringsOrEmpty(t.models),
    profile: textOrNull(t.profile),
    thinking: normalizeLastTurnThinking(t.thinking),
    fallback: textOrNull(t.fallback),
  };
}

/** 生效档位拆成段：逗号分开、去空白、滤掉空段（内核的 effective 可能是逗号连起来的多个档位）。 */
function effortSegments(effective: string | null): string[] {
  if (effective == null) return [];
  return effective
    .split(',')
    .map((level) => level.trim())
    .filter((level) => level !== '');
}

// 时限与工具格：能被 60 整除写「N 分钟」，否则「N 秒」；工具非空时在后面接「 · 」与用「、」连起来的工具名。
export function hubTimeoutText(turn: HubPostTurnInfo | null): string {
  if (turn == null || turn.timeout_seconds == null) return '—';
  const seconds = turn.timeout_seconds;
  const limit = seconds % 60 === 0 ? `${seconds / 60} 分钟` : `${seconds} 秒`;
  return turn.tools.length === 0 ? limit : `${limit} · ${turn.tools.join('、')}`;
}

/** 字节数换算成整数 MiB（Math.round(字节 / 1048576)）；null 写「—」。 */
export function hubMib(bytes: number | null): string {
  return bytes == null ? '—' : String(Math.round(bytes / 1048576));
}

// 预算格：请求数、工具调用数与入/出/对象三个字节数（各自换算成 MiB，null 的项写「—」）。
export function hubBudgetText(budgets: HubPostBudgetInfo | null): string {
  if (budgets == null) return '—';
  const requests = budgets.max_requests == null ? '—' : String(budgets.max_requests);
  const calls = budgets.max_tool_calls == null ? '—' : String(budgets.max_tool_calls);
  const input = hubMib(budgets.max_input_bytes);
  const output = hubMib(budgets.max_response_bytes);
  const object = hubMib(budgets.max_object_bytes);
  return `请求 ${requests} · 工具调用 ${calls} · ${input} / ${output} / ${object} MiB`;
}

// 思考档位三值：要求 · 映射 · 生效；生效是逗号连起来的多个档位时拆开用「、」连，没有段写「—」。
export function hubEffortTriple(lastTurn: HubPostLastTurnInfo | null): string {
  if (lastTurn == null) return '—';
  const thinking = lastTurn.thinking;
  const effective = effortSegments(thinking.effective);
  return `要求 ${thinking.requested ?? '—'} · 映射 ${thinking.mapped ?? '—'} · 生效 ${effective.length === 0 ? '—' : effective.join('、')}`;
}

// 生效档位与要求是否不同：生效有段时任一段不等于要求即不同；没有段时看映射（非 null 且与要求不同）。
export function hubEffortDiffers(lastTurn: HubPostLastTurnInfo | null): boolean {
  if (lastTurn == null) return false;
  const thinking = lastTurn.thinking;
  const requested = thinking.requested;
  if (requested == null) return false;
  const effective = effortSegments(thinking.effective);
  if (effective.length > 0) return effective.some((level) => level !== requested);
  return thinking.mapped != null && thinking.mapped !== requested;
}

export function hubEffortState(lastTurn: HubPostLastTurnInfo | null): 'none' | 'unknown' | 'same' | 'differs' {
  if (lastTurn == null || lastTurn.thinking.requested == null) return 'none';
  if (effortSegments(lastTurn.thinking.effective).length === 0) return 'unknown';
  return hubEffortDiffers(lastTurn) ? 'differs' : 'same';
}

// 最近一回合格：时刻 · 实际载体 · 模型（空数组写「—」）；时刻原样显示内核给的秒级 UTC 原文，不换算相对时间。
export function hubLastTurnText(lastTurn: HubPostLastTurnInfo | null): string {
  if (lastTurn == null) return '—';
  const models = lastTurn.models.length === 0 ? '—' : lastTurn.models.join('、');
  return `${lastTurn.at ?? '—'} · ${lastTurn.adapter ?? '—'} · ${models}`;
}

// 最近一回合格的标记：退回替补（有 fallback 原因）优先，其次实际载体与当前绑定不同。
export function hubLastTurnMark(
  lastTurn: HubPostLastTurnInfo | null,
  boundAdapter: string | null
): '退回替补' | '与当前绑定不同' | null {
  if (lastTurn == null) return null;
  if (lastTurn.fallback != null) return '退回替补';
  if (lastTurn.adapter != null && boundAdapter != null && lastTurn.adapter !== boundAdapter) return '与当前绑定不同';
  return null;
}

/** 退回替补原因文字的截断显示：超过 20 个字截断加「…」，full 给全文（界面 title 用）。 */
export function hubFallbackExcerpt(text: string | null): { shown: string; full: string; } {
  if (text == null) return { shown: '', full: '' };
  if (text.length <= 20) return { shown: text, full: text };
  return { shown: `${text.slice(0, 20)}…`, full: text };
}

// 证书列（合同第 4、5 节）：岗位绑在 quizs 上时，找出它对上的那一套 live。行序即服务端给的顺序（信箱在前、
// env 在后），所以 provider 同名时信箱那一套优先；对不上时退回 env 那一套（provider 认不出是谁家的，hub 自己
// 也会退回去用它）。都没有就返回 null（界面上写「没有 live 文件」）。
export function matchLiveRow(rows: readonly QuizsLiveRow[], provider: string | null): QuizsLiveRow | null {
  if (provider !== null) {
    const hit = rows.find((row) => row.provider === provider);
    if (hit) return hit;
  }
  return rows.find((row) => row.source === 'env' && row.provider === null) ?? null;
}

// 证书格的三种形态：纯文字（tagged 为假，state 为 null）、Tag（tagged 为真，state 是该套的 state 原样，
// 可能仍是 null）、以及 Tag/纯文字都可能带的 title（说明文字，没有就是 null）。
export interface HubCertInfo {
  text: string;
  state: string | null;
  tagged: boolean;
  title: string | null;
}

function nonEmpty(text: string | null): string | null {
  return typeof text === 'string' && text !== '' ? text : null;
}

// 证书格（合同第 5 节的表逐条）：只有 adapter 是 quizs 的岗位才谈得上 live 证书，其余写「—」；live 还没
// 回来写「读取中」；信封层读不出（ok 为假、data 为 null 或 data.live 不是数组）写「读不出」，title 是
// messages；对不上任何一套写「没有 live 文件」；只有对上的那一套用 Tag，state 原样透传给界面。
export function hubCertInfo(post: HubPostInfo, live: Envelope<QuizsLiveData> | null): HubCertInfo {
  if (post.adapter !== 'quizs') return { text: '—', state: null, tagged: false, title: null };
  if (live == null) return { text: '读取中', state: null, tagged: false, title: null };
  const envelopeProblem = live.messages.length === 0 ? null : live.messages.join('\n');
  if (!live.ok || live.data == null) return { text: '读不出', state: null, tagged: false, title: envelopeProblem };
  if (!Array.isArray(live.data.live)) return { text: '读不出', state: null, tagged: false, title: envelopeProblem };
  const row = matchLiveRow(live.data.live, post.provider);
  if (row == null) return { text: '没有 live 文件', state: null, tagged: false, title: null };
  const status = row.status;
  const missing = status == null ? [] : status.missing;
  const missingTitle = missing.length > 0 ? '缺 ' + missing.join('、') : null;
  const title = nonEmpty(row.problem) ?? missingTitle ?? nonEmpty(status?.problem ?? null);
  return { text: '', state: status?.state ?? null, tagged: true, title };
}
