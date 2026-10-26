// kit_roles.py 的登记表与 v3 五个键的校验（迁移第 ③a2 片；命令与绑定解析在第 ③c 片）。报错是给人看的中文句子，会进
// validate 的输出与桌面端的预览，逐字照 Python；提到取值时只显示像 ID、又不像凭据的字符串（D9）。
import { pyReprValue } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { cmpCodePoints } from "@themis/base/pyre";
import { ENV_NAME_RE, TASK_ID_RE, secretLikePaths } from "@themis/base/secrets";
import { secretConfigError } from "./secret-config.ts";

export const V3_KEYS = ["runtimes", "profiles", "roles", "presets", "active_preset"];
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
  "claude-code": { program: "claude", headless_roles: [], host: true, list_models: false, auth: false, options: [] },
  codex: { program: "codex", headless_roles: [], host: true, list_models: false, auth: false, options: [] },
  opencode: { program: "opencode", headless_roles: [], host: false, list_models: false, auth: false, options: [] },
};
const ADAPTER_NAMES = Object.keys(ADAPTERS);
export const HOST_ADAPTERS = ADAPTER_NAMES.filter((name) => ADAPTERS[name]?.host);
const RUNTIME_KEYS = ["adapter"];
const PROFILE_KEYS = ["runtime", "model", "options", "credential_env"];
const PRESET_KEYS = ["description", "roles"];
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

function idOk(value: PyValue | undefined): boolean {
  return typeof value === "string" && TASK_ID_RE.test(value);
}

function extraKeys(obj: PyDict, allowed: readonly string[]): string[] {
  return [...obj.keys()].map(keyText).filter((key) => !key.startsWith("_") && !allowed.includes(key)).sort(cmpCodePoints);
}

/** {ID: 对象} 这一层的条目；下划线开头的是说明键。 */
function entries(mapping: PyDict): [string, PyValue][] {
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
      if (options.has("thinking") && !among(options.get("thinking"), THINKING_LEVELS)) {
        errors.push(`${where}.options.thinking 必须是 ${THINKING_LEVELS.join("、")} 之一`);
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

const CHECKS: Readonly<Record<string, (config: PyDict) => string[]>> = {
  runtimes: checkRuntimes,
  profiles: checkProfiles,
  roles: checkRoles,
  presets: checkPresets,
  active_preset: checkActivePreset,
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
