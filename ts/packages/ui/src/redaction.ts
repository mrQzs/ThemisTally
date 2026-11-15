// 二道脱敏的白名单（桌面端设计第 7 版 §5.3、D07）：响应先过 redactJson，再按路由登记的白名单做约束校验——
// 白名单只放名字与来源这类可枚举的形状，绝不放凭据值。约束不成立的值换成 <redacted>（base 的 redactJson 语义：
// 路径最后一段上的校验函数作用在该路径的值上，命中白名单的值不再按敏感键遮）。file 路由（证据）不登记任何白名单。
import { type PyValue } from "@themis/base/pyjson";
import { type AllowList, allowEnum, allowEnvName, allowId, redactSecrets, tokenShaped } from "@themis/base/secrets";

/** 内核的 SOURCES（codekit/secrets.py）：凭据的来源。 */
export const SOURCE_ENUM = allowEnum("env", "credential_store", "file", "none");
/** 内核的 STORE_MODES（codekit/secrets.py）：凭据的存放方式。 */
export const STORE_MODE_ENUM = allowEnum("system", "file", "off");
/** 系统后端的名字（codekit/secrets.py）：windows-credential-manager 与 file；没有系统后端时是 null。 */
export const SYSTEM_BACKEND_ENUM = allowEnum("windows-credential-manager", "file", null);
/** 岗位绑定用的适配器名（scripts/kit_roles.py 的 HUB_POST_ADAPTERS 与 ADAPTERS；TS 一份在 ts/packages/config/src/roles-check.ts）：
 * 五个载体 quizs 只承载七端岗位，runtime.add 的 ADAPTERS 也是这五个（ts/packages/ui/src/writeroutes.ts）；runtime 没登记时内核给 null，枚举带上 null 才放行。 */
const HUB_ADAPTER_ENUM = allowEnum("pi", "claude-code", "codex", "opencode", "quizs", null);
/** 岗位绑定用的思考档位（scripts/pi_dispatch.py 的 FALLBACK_THINKING_LEVELS）：七个取值；可空，枚举带上 null。 */
const HUB_THINKING_ENUM = allowEnum("off", "minimal", "low", "medium", "high", "xhigh", "max", null);

/** 允许 null 的 id：内核没配的岗位，profile 与 runtime 就是 null（base 的 allowId 不放行 null）。 */
export function allowNullableId(value: PyValue): boolean {
  return value === null || allowId(value);
}

/** 岗位绑定的 provider/model 名：null 放行；否则是字符串，过这个正则且不像凭据（比 allowPreviewName 宽，带 @ 与 +）。 */
export function allowBindingName(value: PyValue): boolean {
  if (value === null) return true;
  if (typeof value !== "string") return false;
  return /^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$/u.test(value) && !tokenShaped(value);
}

/** used_by 的形状：键恰好是 {kind} 或 {kind, id}；kind 只认 profile 与 decisions，有 id 时过 allowId。 */
export function usedByShape(value: PyValue): boolean {
  if (!(value instanceof Map)) return false;
  const keys = [...value.keys()];
  const kind = value.get("kind");
  if (kind !== "profile" && kind !== "decisions") return false;
  if (keys.length === 1) return keys[0] === "kind";
  if (keys.length === 2) return keys.includes("kind") && keys.includes("id") && allowId(value.get("id") ?? null);
  return false;
}

/**
 * /config 的白名单（config show --json）：只放环境变量名与枚举。decisions.secret.file_dir 故意不登记——它会泄露
 * 路径，而且它落在 secret 键下，照样被遮掉。
 */
export const CONFIG_ALLOW: AllowList = [
  [["decisions", "env_var_name"], allowEnvName],
  [["decisions", "secret", "name"], allowEnvName],
  [["decisions", "secret", "source"], SOURCE_ENUM],
  [["decisions", "secret", "store_mode"], STORE_MODE_ENUM],
  [["decisions", "secret", "system_backend"], SYSTEM_BACKEND_ENUM],
  [["keys", "[key=env_remove]", "value", "*"], allowEnvName],
  [["keys", "[key=env_keep]", "value", "*"], allowEnvName],
  [["keys", "[key=decisions]", "value", "api_key_env"], allowEnvName],
];

/** /profiles 的白名单：每个 profile 的 credential_env 里的环境变量名。 */
export const PROFILES_ALLOW: AllowList = [[["profiles", "*", "credential_env", "*"], allowEnvName]];

/** 合成的 /secrets 的白名单：名字、来源与 used_by（kind/id）。 */
export const SECRETS_ALLOW: AllowList = [
  [["secrets", "*", "name"], allowEnvName],
  [["secrets", "*", "source"], SOURCE_ENUM],
  [["secrets", "*", "store_mode"], STORE_MODE_ENUM],
  [["secrets", "*", "system_backend"], SYSTEM_BACKEND_ENUM],
  [["secrets", "*", "used_by", "*"], usedByShape],
];

/** /secrets/<name> 的白名单（config secret check 的一行 JSON；file_dir 不登记，服务也不把它放进 data）。 */
export const SECRET_SHOW_ALLOW: AllowList = [
  [["name"], allowEnvName],
  [["source"], SOURCE_ENUM],
  [["store_mode"], STORE_MODE_ENUM],
  [["system_backend"], SYSTEM_BACKEND_ENUM],
];

/** 证据（file 路由）不登记任何白名单：data 原样过 redactJson。 */
export const EVIDENCE_ALLOW: AllowList | undefined = undefined;

/** 预览里绑定字段的名字形状：null 或 1 到 128 个码点、只含 A-Za-z0-9._:/-、且不像凭据（tokenShaped 为假）。 */
const PREVIEW_NAME_RE = /^[A-Za-z0-9._:/-]{1,128}$/u;
export function allowPreviewName(value: PyValue): boolean {
  if (value === null) return true; // 绑定原来就没有（before 里的 null）
  if (typeof value !== "string") return false;
  return PREVIEW_NAME_RE.test(value) && !tokenShaped(value);
}

/** 预览里的自由文字：字符串，且本来就不像凭据（过 redactSecrets 原样不变才放行）。 */
export function allowPreviewText(value: PyValue): boolean {
  return typeof value === "string" && redactSecrets(value) === value;
}

/**
 * /hub/roles 的白名单（config hub show --json 的 {"posts":[…]}）：逐字段登记六个岗位的一行行字段。岗位六个名字抄
 * scripts/kit_roles.py 的 HUB_POST_ADAPTERS（TS 一份在 ts/packages/config/src/roles-check.ts）；适配器名抄同一处的
 * HUB_POST_ADAPTERS 与 ADAPTERS。内核会给 null 的字段（adapter/provider/model/thinking/profile/runtime 及其 fallback 下
 * 同名）校验函数一律接受 null——base 的 allowId 不接受 null、allowEnum 只有把 null 列进 choices 才放行 null，而
 * redactJsonAllowing 命中路径照样拿值调校验函数、不合格就换成 <redacted>。fallback 本身（对象或 null）不登记；内核没给的键
 * （缺省行 coordinator 的 fallback 只有四个键）路径不命中，值照 redactJson 的默认口径走。
 */
export const HUB_ROLES_ALLOW: AllowList = [
  [["posts", "*", "post"], allowEnum("coordinator", "planner", "contract", "gate", "audit", "exec")],
  [["posts", "*", "source"], allowEnum("default", "config")],
  [["posts", "*", "allowed_adapters", "*"], HUB_ADAPTER_ENUM],
  [["posts", "*", "adapter"], HUB_ADAPTER_ENUM],
  [["posts", "*", "provider"], allowBindingName],
  [["posts", "*", "model"], allowBindingName],
  [["posts", "*", "thinking"], HUB_THINKING_ENUM],
  [["posts", "*", "profile"], allowNullableId],
  [["posts", "*", "runtime"], allowNullableId],
  [["posts", "*", "fallback", "adapter"], HUB_ADAPTER_ENUM],
  [["posts", "*", "fallback", "provider"], allowBindingName],
  [["posts", "*", "fallback", "model"], allowBindingName],
  [["posts", "*", "fallback", "thinking"], HUB_THINKING_ENUM],
  [["posts", "*", "fallback", "profile"], allowNullableId],
  [["posts", "*", "fallback", "runtime"], allowNullableId],
];

/**
 * /preview 的白名单（内核预览 JSON，state 令牌在进白名单之前就被拿掉）：只放 binding_changes.*.before|after 的六个绑定
 * 字段（profile/runtime/adapter/provider/model/thinking；mode 是枚举，不进白名单，照 redactSecrets 处理）、
 * hub_changes.*（岗位名，两侧的 source、六个绑定字段与替补的六个字段；r3 第 162 轮）、
 * resources.*.changed_keys.*、notes.*、warnings.*、running_attempts.*、running_turns.*（改到的岗位此刻在跑的回合，r3 第 163 轮）。
 * 白名单不为任何凭据值开口子；unreadable 不进
 * 白名单（内核的报错文字，照 messages 逐项过 redactSecrets）。放行的值原样保留，该遮的位置（凭据形状、敏感键下的值）
 * 一律变成 <redacted>。
 */
export const PREVIEW_ALLOW: AllowList = [
  [["binding_changes", "*", "before", "profile"], allowPreviewName],
  [["binding_changes", "*", "before", "runtime"], allowPreviewName],
  [["binding_changes", "*", "before", "adapter"], allowPreviewName],
  [["binding_changes", "*", "before", "provider"], allowPreviewName],
  [["binding_changes", "*", "before", "model"], allowPreviewName],
  [["binding_changes", "*", "before", "thinking"], allowPreviewName],
  [["binding_changes", "*", "after", "profile"], allowPreviewName],
  [["binding_changes", "*", "after", "runtime"], allowPreviewName],
  [["binding_changes", "*", "after", "adapter"], allowPreviewName],
  [["binding_changes", "*", "after", "provider"], allowPreviewName],
  [["binding_changes", "*", "after", "model"], allowPreviewName],
  [["binding_changes", "*", "after", "thinking"], allowPreviewName],
  [["hub_changes", "*", "post"], allowPreviewName],
  [["hub_changes", "*", "before", "source"], allowPreviewName],
  [["hub_changes", "*", "after", "source"], allowPreviewName],
  [["hub_changes", "*", "before", "profile"], allowPreviewName],
  [["hub_changes", "*", "before", "runtime"], allowPreviewName],
  [["hub_changes", "*", "before", "adapter"], allowPreviewName],
  [["hub_changes", "*", "before", "provider"], allowPreviewName],
  [["hub_changes", "*", "before", "model"], allowPreviewName],
  [["hub_changes", "*", "before", "thinking"], allowPreviewName],
  [["hub_changes", "*", "after", "profile"], allowPreviewName],
  [["hub_changes", "*", "after", "runtime"], allowPreviewName],
  [["hub_changes", "*", "after", "adapter"], allowPreviewName],
  [["hub_changes", "*", "after", "provider"], allowPreviewName],
  [["hub_changes", "*", "after", "model"], allowPreviewName],
  [["hub_changes", "*", "after", "thinking"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "profile"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "runtime"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "adapter"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "provider"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "model"], allowPreviewName],
  [["hub_changes", "*", "before", "fallback", "thinking"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "profile"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "runtime"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "adapter"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "provider"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "model"], allowPreviewName],
  [["hub_changes", "*", "after", "fallback", "thinking"], allowPreviewName],
  [["resources", "*", "changed_keys", "*"], allowPreviewName],
  [["notes", "*"], allowPreviewText],
  [["warnings", "*"], allowPreviewText],
  [["running_attempts", "*"], allowPreviewText],
  [["running_turns", "*"], allowPreviewText],
];
