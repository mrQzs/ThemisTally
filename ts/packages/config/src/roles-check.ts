// kit_roles.py 的登记表与 v3 五个键的校验（迁移第 ③a2 片；命令与绑定解析在第 ③c 片）。报错是给人看的中文句子，会进
// validate 的输出与桌面端的预览，逐字照 Python；提到取值时只显示像 ID、又不像凭据的字符串（D9）。
import { pyReprValue } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { cmpCodePoints } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { ENV_NAME_RE, TASK_ID_RE, secretLikePaths } from "@themis/base/secrets";
import { secretConfigError } from "./secret-config.ts";

/** pi_dispatch.V3_CONFIG_KEYS：第二轮的五个键，加 r3 第 154 轮的 hub_roles（七端各岗位的绑定）。 */
export const V3_KEYS = ["runtimes", "profiles", "roles", "presets", "active_preset", "hub_roles"];
export const ROLES = ["planning_review", "contract", "execution", "scheduler_agent"];
/** 每个角色允许的模式（上位设计 6.3）。 */
export const ROLE_MODES: Readonly<Record<string, readonly string[]>> = {
  planning_review: ["interactive_host", "headless"],
  contract: ["manual", "headless"],
  execution: ["headless"],
  scheduler_agent: ["disabled", "headless"],
};

export interface AdapterSpec {
  readonly program: string;
  readonly headless_roles: readonly string[];
  readonly host: boolean;
  readonly list_models: boolean;
  readonly auth: boolean;
  readonly options: readonly string[];
}

/** 适配器登记表（D2）：静态表，不是插件。 */
export const ADAPTERS: Readonly<Record<string, AdapterSpec>> = {
  pi: { program: "pi", headless_roles: ["execution", "contract"], host: false, list_models: true, auth: true, options: ["thinking"] },
  // r3 第 154 轮：七端的规划端在 claude 上无头运行，档位写在 options.thinking（hub 传给 claude 的 --effort）
  "claude-code": { program: "claude", headless_roles: [], host: true, list_models: false, auth: false, options: ["thinking"] },
  codex: { program: "codex", headless_roles: [], host: true, list_models: false, auth: false, options: [] },
  opencode: { program: "opencode", headless_roles: [], host: false, list_models: false, auth: false, options: [] },
  // r3 第 154 轮：quizs 只承载七端的岗位（hub_roles），不接四个角色的 headless
  quizs: { program: "quizs", headless_roles: [], host: false, list_models: false, auth: false, options: ["thinking"] },
};
const ADAPTER_NAMES = Object.keys(ADAPTERS);
export const HOST_ADAPTERS = ADAPTER_NAMES.filter((name) => ADAPTERS[name]?.host);
const RUNTIME_KEYS = ["adapter"];
const PROFILE_KEYS = ["runtime", "model", "options", "credential_env"];
const PRESET_KEYS = ["description", "roles"];
/** kit_roles.HUB_POST_ADAPTERS：七端的岗位 → 这个岗位现在允许的适配器（只列已经跑过的载体；r3 第 156 轮合同端、审核端加 quizs：工具映射在假提供方上跑过，真实模型的重放跑完之前不绑）。 */
export const HUB_POST_ADAPTERS: Readonly<Record<string, readonly string[]>> = {
  coordinator: ["quizs", "pi"],
  planner: ["claude-code"],
  contract: ["pi", "quizs"],
  gate: ["pi"],
  audit: ["pi", "quizs"],
  exec: ["pi"],
};
export const HUB_POSTS = Object.keys(HUB_POST_ADAPTERS);
export const HUB_BINDING_KEYS = ["profile", "fallback"];
/** kit_roles.HUB_SIDE_FIELDS：预览里岗位一侧的字段（模型配置 §3.4，r3 第 162 轮），另加 source 与替补。 */
export const HUB_SIDE_FIELDS = ["profile", "runtime", "adapter", "provider", "model", "thinking"];

export interface HubDefault {
  readonly adapter: string;
  readonly provider: string | null;
  readonly model: string;
  readonly thinking: string;
  readonly fallback: { readonly adapter: string; readonly provider: string; readonly model: string; readonly thinking: string } | null;
}

/** kit_roles.HUB_DEFAULTS：各岗位没配时 hub 用的缺省，与 hub 名册的同名字段逐项相同（契约里有一条核对）。 */
export const HUB_DEFAULTS: Readonly<Record<string, HubDefault>> = {
  coordinator: {
    adapter: "quizs", provider: "deepseek", model: "deepseek-flash", thinking: "high",
    fallback: { adapter: "pi", provider: "dsf", model: "deepseek-flash", thinking: "high" },
  },
  planner: { adapter: "claude-code", provider: null, model: "claude-opus-5-5", thinking: "max", fallback: null },
  contract: { adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "high", fallback: null },
  gate: { adapter: "pi", provider: "cc-switch-zhipu-glm", model: "glm-5.3", thinking: "high", fallback: null },
  audit: { adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "max", fallback: null },
  exec: { adapter: "pi", provider: "cc-switch-step-fun", model: "step-5-preview", thinking: "high", fallback: null },
};
/** claude 的 --effort 取值（claude --help，2026-11-12 核对）。 */
export const CLAUDE_EFFORTS = ["low", "medium", "high", "xhigh", "max"];
/** pi_dispatch.FALLBACK_THINKING_LEVELS。 */
export const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];
/** pi_dispatch.MODEL_TOKEN_RE（re.match 加 $：末尾的换行照样放过）。 */
export const MODEL_TOKEN_RE = /^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}(?=\n?$)/u;
/** pi_dispatch.PLACEHOLDER_RE（search）。 */
export const PLACEHOLDER_RE = /【待填|REPLACE_WITH/u;

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
/** str(key)：配置读出来的键都是字符串。 */
const keyText = (key: unknown): string => String(key);

export function hasV3Keys(config: PyValue): boolean {
  return isDict(config) && V3_KEYS.some((key) => config.has(key));
}

export function idOk(value: PyValue | undefined): boolean {
  return typeof value === "string" && TASK_ID_RE.test(value);
}

export function extraKeys(obj: PyDict, allowed: readonly string[]): string[] {
  return [...obj.keys()].map(keyText).filter((key) => !key.startsWith("_") && !allowed.includes(key)).sort(cmpCodePoints);
}

/** {ID: 对象} 这一层的条目；下划线开头的是说明键。 */
export function entries(mapping: PyDict): [string, PyValue][] {
  return [...mapping].filter(([key]) => !keyText(key).startsWith("_")).map(([key, value]) => [keyText(key), value]);
}

/** 错误里要提到的值：只有像 ID、又不像凭据的字符串才原样显示（repr），其余隐去。 */
export function shownValue(value: PyValue | undefined): string {
  if (typeof value === "string" && TASK_ID_RE.test(value) && secretLikePaths(new Map([["v", value]])).length === 0) return pyReprValue(value);
  return "（值不显示）";
}

function modelErrors(where: string, model: PyValue | undefined): string[] {
  if (!isDict(model)) return [`${where}.model 必须是 {provider, id}`];
  const extra = extraKeys(model, ["provider", "id"]);
  const errors = extra.length ? [`${where}.model 有未知键：${extra.join("、")}`] : [];
  for (const field of ["provider", "id"]) {
    const value = model.get(field);
    if (typeof value !== "string" || !MODEL_TOKEN_RE.test(value) || PLACEHOLDER_RE.test(value)) errors.push(`${where}.model.${field} 必须是精确的 ID`);
  }
  return errors;
}

export function adapterOf(config: PyDict, runtimeId: PyValue | undefined): string | null {
  const runtimes = config.get("runtimes");
  if (typeof runtimeId !== "string" || runtimeId.startsWith("_") || !isDict(runtimes) || !isDict(runtimes.get(runtimeId))) return null;
  const adapter = (runtimes.get(runtimeId) as PyDict).get("adapter");
  return typeof adapter === "string" && ADAPTER_NAMES.includes(adapter) ? adapter : null;
}

function checkRuntimes(config: PyDict): string[] {
  const runtimes = config.get("runtimes");
  if (!isDict(runtimes)) return ["runtimes 必须是对象 {ID: {adapter}}"];
  const errors: string[] = [];
  for (const [runtimeId, spec] of entries(runtimes)) {
    const where = `runtimes.${runtimeId}`;
    if (!idOk(runtimeId)) errors.push(`${where}：ID 不合法`);
    if (!isDict(spec)) {
      errors.push(`${where} 必须是对象`);
      continue;
    }
    const extra = extraKeys(spec, RUNTIME_KEYS);
    if (extra.length) errors.push(`${where} 只接受 adapter，不能写 ${extra.join("、")}（命令路径放 .agent/dispatch.local.json）`);
    const adapter = spec.get("adapter");
    if (typeof adapter !== "string" || !ADAPTER_NAMES.includes(adapter)) errors.push(`${where}.adapter 必须是 ${ADAPTER_NAMES.join("、")} 之一`);
  }
  return errors;
}

/** x in seq（seq 里都是字符串）：只有字符串才可能相等。 */
const among = (value: PyValue | undefined, items: readonly string[]): boolean => typeof value === "string" && items.includes(value);

function checkProfiles(config: PyDict): string[] {
  const profiles = config.get("profiles");
  if (!isDict(profiles)) return ["profiles 必须是对象 {ID: {runtime, model, options, credential_env}}"];
  const errors: string[] = [];
  for (const [profileId, spec] of entries(profiles)) {
    const where = `profiles.${profileId}`;
    if (!idOk(profileId)) errors.push(`${where}：ID 不合法`);
    if (!isDict(spec)) {
      errors.push(`${where} 必须是对象`);
      continue;
    }
    const extra = extraKeys(spec, PROFILE_KEYS);
    if (extra.length) errors.push(`${where} 有未知键：${extra.join("、")}`);
    const adapter = adapterOf(config, spec.get("runtime"));
    if (adapter === null) errors.push(`${where}.runtime ${shownValue(spec.get("runtime") ?? null)} 没有登记（或它的 adapter 无效）`);
    errors.push(...modelErrors(where, spec.get("model")));
    const options = spec.has("options") ? spec.get("options") : new Map();
    if (!isDict(options)) {
      errors.push(`${where}.options 必须是对象`);
    } else if (adapter !== null) {
      const optionExtra = extraKeys(options, ADAPTERS[adapter]?.options ?? []);
      if (optionExtra.length) errors.push(`${where}.options 有 ${adapter} 不接受的键：${optionExtra.join("、")}`);
      const levels = adapter === "claude-code" ? CLAUDE_EFFORTS : THINKING_LEVELS;
      if (options.has("thinking") && !among(options.get("thinking"), levels)) {
        errors.push(`${where}.options.thinking 必须是 ${levels.join("、")} 之一`);
      }
    }
    const names = spec.has("credential_env") ? spec.get("credential_env") : [];
    if (!Array.isArray(names) || names.some((name) => typeof name !== "string" || !ENV_NAME_RE.test(name))) {
      errors.push(`${where}.credential_env 必须是环境变量名的数组`);
    }
  }
  return errors;
}

function bindingErrors(config: PyDict, where: string, role: string, binding: PyValue | undefined): string[] {
  if (!isDict(binding)) return [`${where} 必须是对象 {mode, …}`];
  const mode = binding.get("mode");
  const modes = ROLE_MODES[role] ?? [];
  if (typeof mode !== "string" || !modes.includes(mode)) return [`${where}.mode 必须是 ${modes.join("、")} 之一（当前 ${shownValue(mode ?? null)}）`];
  const allowed: Record<string, readonly string[]> = {
    interactive_host: ["mode", "host"],
    headless: role === "scheduler_agent" ? ["mode", "profile", "cadence_seconds"] : ["mode", "profile"],
    manual: ["mode"],
    disabled: ["mode"],
  };
  const extra = extraKeys(binding, allowed[mode] ?? []);
  const errors = extra.length ? [`${where} 有未知键：${extra.join("、")}`] : [];
  if (mode === "interactive_host" && binding.has("host") && !among(binding.get("host"), HOST_ADAPTERS)) {
    errors.push(`${where}.host 必须是 ${HOST_ADAPTERS.join("、")} 之一`);
  }
  if (mode === "headless") {
    const profiles = config.get("profiles");
    const known = isDict(profiles) ? profiles : new Map();
    const profile = binding.get("profile");
    if (typeof profile !== "string" || profile.startsWith("_") || !known.has(profile)) errors.push(`${where}.profile ${shownValue(profile ?? null)} 没有登记`);
    // 写了就必须合法，null 也不行
    if (binding.has("cadence_seconds")) {
      const cadence = binding.get("cadence_seconds");
      if (typeof cadence !== "bigint" || cadence < 60n) errors.push(`${where}.cadence_seconds 必须是至少 60 的整数`);
    }
  }
  return errors;
}

function checkRoles(config: PyDict): string[] {
  const roles = config.get("roles");
  if (!isDict(roles)) return ["roles 必须是对象 {角色: {mode, …}}"];
  const extra = extraKeys(roles, ROLES);
  const errors = extra.length ? [`roles 有未知角色：${extra.join("、")}（只有 ${ROLES.join("、")}）`] : [];
  for (const role of ROLES) if (roles.has(role)) errors.push(...bindingErrors(config, `roles.${role}`, role, roles.get(role)));
  return errors;
}

function checkPresets(config: PyDict): string[] {
  const presets = config.get("presets");
  if (!isDict(presets)) return ["presets 必须是对象 {名: {description, roles}}"];
  const errors: string[] = [];
  for (const [name, spec] of entries(presets)) {
    const where = `presets.${name}`;
    if (!idOk(name)) errors.push(`${where}：名字不合法`);
    if (!isDict(spec)) {
      errors.push(`${where} 必须是对象`);
      continue;
    }
    const extra = extraKeys(spec, PRESET_KEYS);
    if (extra.length) errors.push(`${where} 有未知键：${extra.join("、")}`);
    if (spec.has("description") && typeof spec.get("description") !== "string") errors.push(`${where}.description 必须是字符串`);
    const roles = spec.get("roles");
    if (!isDict(roles) || ![...roles.keys()].some((role) => !keyText(role).startsWith("_"))) {
      errors.push(`${where}.roles 至少写一个角色`);
      continue;
    }
    const unknown = extraKeys(roles, ROLES);
    if (unknown.length) errors.push(`${where}.roles 有未知角色：${unknown.join("、")}`);
    for (const role of ROLES) if (roles.has(role)) errors.push(...bindingErrors(config, `${where}.roles.${role}`, role, roles.get(role)));
  }
  return errors;
}

function checkActivePreset(config: PyDict): string[] {
  const name = config.get("active_preset");
  const presets = config.get("presets");
  const known = isDict(presets) ? presets : new Map();
  if (typeof name !== "string" || name.startsWith("_") || !known.has(name)) return [`active_preset ${shownValue(name ?? null)} 不是已有的方案`];
  return [];
}

/** kit_roles._check_hub_roles：七端的岗位绑定 {岗位: {profile, fallback}}。fallback 只用于 quizs 上的岗位，替补自己不能是 quizs。 */
function checkHubRoles(config: PyDict): string[] {
  const hubRoles = config.get("hub_roles");
  if (!isDict(hubRoles)) return ["hub_roles 必须是对象 {岗位: {profile, fallback}}"];
  const extra = extraKeys(hubRoles, HUB_POSTS);
  const errors = extra.length ? [`hub_roles 有未知岗位：${extra.join("、")}（只有 ${HUB_POSTS.join("、")}）`] : [];
  const listed = config.get("profiles");
  const profiles: PyDict = isDict(listed) ? listed : new Map();
  for (const post of HUB_POSTS) {
    if (!hubRoles.has(post)) continue;
    const where = `hub_roles.${post}`;
    const binding = hubRoles.get(post);
    if (!isDict(binding)) {
      errors.push(`${where} 必须是对象 {profile, fallback}`);
      continue;
    }
    const unknown = extraKeys(binding, HUB_BINDING_KEYS);
    if (unknown.length) errors.push(`${where} 有未知键：${unknown.join("、")}`);
    const allowed = HUB_POST_ADAPTERS[post] ?? [];
    const adapters = new Map<string, string | null>();
    for (const field of HUB_BINDING_KEYS) {
      if (field === "fallback" && !binding.has(field)) continue;
      const profile = binding.get(field);
      const spec = typeof profile === "string" ? profiles.get(profile) : undefined;
      if (typeof profile !== "string" || profile.startsWith("_") || !isDict(spec)) {
        errors.push(`${where}.${field} ${shownValue(profile ?? null)} 没有登记`);
        continue;
      }
      const adapter = adapterOf(config, spec.get("runtime"));
      adapters.set(field, adapter);
      if (adapter !== null && !allowed.includes(adapter)) {
        errors.push(`${where}.${field} 的适配器 ${adapter} 不能用在 ${post} 岗位（允许：${allowed.join("、")}）`);
      }
    }
    if (adapters.has("fallback") && (adapters.get("profile") !== "quizs" || adapters.get("fallback") === "quizs")) {
      errors.push(`${where}.fallback 只用于 quizs 上的岗位，替补自己不能是 quizs`);
    }
  }
  return errors;
}

/** kit_roles.hub_binding：七端某个岗位在配置里的绑定，解析成 hub 要的字段；没写这个岗位时 null（hub 用内核里的缺省）。 */
export function hubBinding(config: PyDict, post: string): PyDict | null {
  const hubRoles = config.get("hub_roles");
  const binding = isDict(hubRoles) ? hubRoles.get(post) : undefined;
  if (!isDict(binding)) return null;
  const listed = config.get("profiles");
  const profiles: PyDict = isDict(listed) ? listed : new Map();
  const resolved = (profileId: PyValue | undefined): PyDict | null => {
    const profile = typeof profileId === "string" ? profiles.get(profileId) : undefined;
    if (!isDict(profile)) return null;
    const modelValue = profile.get("model");
    const model: PyDict = isDict(modelValue) ? modelValue : new Map();
    const optionsValue = profile.get("options");
    const options: PyDict = isDict(optionsValue) ? optionsValue : new Map();
    const runtimeValue = profile.get("runtime");
    const runtime = typeof runtimeValue === "string" ? runtimeValue : null;
    return new Map<string, PyValue>([
      ["profile", profileId as string],
      ["runtime", runtime],
      ["adapter", adapterOf(config, runtime)],
      ["provider", model.get("provider") ?? null],
      ["model", model.get("id") ?? null],
      ["thinking", options.has("thinking") ? (options.get("thinking") ?? null) : "high"],
    ]);
  };
  const primary = resolved(binding.get("profile"));
  if (primary === null) return null;
  primary.set("fallback", binding.has("fallback") ? resolved(binding.get("fallback")) : null);
  return primary;
}

/** kit_roles.hub_side：预览里一个岗位生效绑定的一侧；没配这个岗位时取内核缺省，与 config hub show 的一行一致。 */
export function hubSide(config: PyDict, post: string): PyDict {
  const binding = hubBinding(config, post);
  const preset = HUB_DEFAULTS[post];
  const spec: PyDict = binding ?? new Map<string, PyValue>([
    ["adapter", preset?.adapter ?? null],
    ["provider", preset?.provider ?? null],
    ["model", preset?.model ?? null],
    ["thinking", preset?.thinking ?? null],
    ["fallback", preset?.fallback ? new Map<string, PyValue>(Object.entries(preset.fallback)) : null],
  ]);
  const fallback = spec.get("fallback");
  const side = new Map<string, PyValue>([["source", binding === null ? "default" : "config"]]);
  for (const field of HUB_SIDE_FIELDS) side.set(field, spec.get(field) ?? null);
  side.set("fallback", isDict(fallback) ? new Map<string, PyValue>(HUB_SIDE_FIELDS.map((field) => [field, fallback.get(field) ?? null])) : null);
  return side;
}

/** kit_roles.hub_changes：这次写入改变了哪些岗位的生效绑定，前后不同的岗位各一项 {post, before, after}。 */
export function hubChanges(oldConfig: PyDict, newConfig: PyDict): PyValue[] {
  const changes: PyValue[] = [];
  for (const post of HUB_POSTS) {
    const before = hubSide(oldConfig, post);
    const after = hubSide(newConfig, post);
    if (!pyEq(before, after)) changes.push(new Map<string, PyValue>([["post", post], ["before", before], ["after", after]]));
  }
  return changes;
}

const CHECKS: Readonly<Record<string, (config: PyDict) => string[]>> = {
  runtimes: checkRuntimes,
  profiles: checkProfiles,
  roles: checkRoles,
  presets: checkPresets,
  active_preset: checkActivePreset,
  hub_roles: checkHubRoles,
};

/** kit_roles.check_key：先查这个键之下疑似凭据的位置，有就只报这一条。 */
export function checkKey(config: PyDict, key: string): string[] {
  const secret = secretConfigError(config, key);
  if (secret !== null) return [secret];
  return (CHECKS[key] as (config: PyDict) => string[])(config);
}

/** kit_roles.config_errors：配置里出现的 v3 键逐个校验的错误。 */
export function configErrors(config: PyDict): string[] {
  return V3_KEYS.filter((key) => config.has(key)).flatMap((key) => checkKey(config, key));
}
