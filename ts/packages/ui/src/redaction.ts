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
 * 七端岗位每一回合拿到了什么（scripts/kit_roles.py 的 _hub_turn 与 _hub_last_turn，r3 T047 片一）：内核在每行加
 * turn 与 last_turn 两个对象——turn 是 {timeout_seconds, tools, budgets}（budgets 只在载体是 quizs 的岗位有，
 * 抄 QUIZS_TURN_BUDGETS/QUIZS_VIEW_BUDGETS；不在 HUB_TURN_LIMITS 的岗位整项是 null）；last_turn 从信箱
 * .agent/mailbox/turns/<工人>/<回合>/result.json 读最近一回合（scripts/kit_hub.py:2724-2731 的字段），没有信箱、
 * 没跑完过或读不出时整项是 null。下面四个校验器与 HUB_ROLES_ALLOW 末尾的 15 条路径放行这些值；turn、
 * last_turn、turn.budgets、last_turn.thinking 四层对象本身不登记（T031 只认其下的叶子路径）。
 */

/** 非负整数：null 放行；bigint 与 number 都接（pyjson 把大整数解析成 bigint），number 要是整数且不小于 0。
 * 用于 turn 的 timeout_seconds 与 budgets 的五项字节/次数（scripts/kit_roles.py 的 _hub_turn）。 */
export function allowNonNegativeInt(value: PyValue): boolean {
  if (value === null) return true;
  if (typeof value === "bigint") return value >= 0n;
  if (typeof value !== "number") return false;
  return Number.isInteger(value) && value >= 0;
}

/** 工具名：字母开头、字母数字与 -_ 至多 64 个，可带一段括号参数（如 Bash(npm view:*)）；且不像凭据（tokenShaped 为假）。
 * 照 scripts/kit_roles.py 的 HUB_TURN_LIMITS 里各岗位的工具名单（read/grep/find/ls/edit/write/bash 与 Claude 的
 * Read/Grep/Glob、Bash(npm view:*)）。 */
export function allowToolName(value: PyValue): boolean {
  if (typeof value !== "string") return false;
  return /^[A-Za-z][A-Za-z0-9_-]{0,63}(\([^()\r\n]{1,128}\))?$/u.test(value) && !tokenShaped(value);
}

/** 秒级 ISO 8601 UTC 时刻：null 放行；形如 2026-11-15T08:00:00Z，Z 与 +00:00 两种结尾、不带毫秒
 * （scripts/kit_hub.py 的 utc_now() 是秒级）。 */
export function allowIsoSecondUtc(value: PyValue): boolean {
  return value === null || (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|\+00:00)$/u.test(value));
}

/** 生效档位：null 放行；否则按逗号拆开，每段 trim 后非空且都在七个档位里。审核端的生效档位可能是逗号连起来的
 * 多个（scripts/kit_hub.py:2683 把 effective_levels 用 , 连起来），逐段校验。 */
const EFFORT_LEVELS = new Set(["off", "minimal", "low", "medium", "high", "xhigh", "max"]);
export function allowEffortLevels(value: PyValue): boolean {
  if (value === null) return true;
  if (typeof value !== "string") return false;
  return value.split(",").every((part) => {
    const level = part.trim();
    return level !== "" && EFFORT_LEVELS.has(level);
  });
}

/**
 * /hub/roles 的白名单（config hub show --json 的 {"posts":[…]}）：逐字段登记六个岗位的一行行字段。岗位六个名字抄
 * scripts/kit_roles.py 的 HUB_POST_ADAPTERS（TS 一份在 ts/packages/config/src/roles-check.ts）；适配器名抄同一处的
 * HUB_POST_ADAPTERS 与 ADAPTERS。内核会给 null 的字段（adapter/provider/model/thinking/profile/runtime 及其 fallback 下
 * 同名）校验函数一律接受 null——base 的 allowId 不接受 null、allowEnum 只有把 null 列进 choices 才放行 null，而
 * redactJsonAllowing 命中路径照样拿值调校验函数、不合格就换成 <redacted>。fallback 本身（对象或 null）不登记；内核没给的键
 * （缺省行 coordinator 的 fallback 只有四个键）路径不命中，值照 redactJson 的默认口径走。
 *
 * T047 片一在末尾追加 15 条：turn 的 timeout_seconds、tools 逐个元素、budgets 五项，last_turn 的 at、adapter、
 * models 逐个元素、profile、thinking 三项与 fallback。last_turn.fallback 是退回替补的原因文字，可能带本机路径
 * （scripts/kit_hub.py:2145 的「读不出资格证书 %s」），照 allowNullablePreviewText 放行——界面截断显示、title 给全文。
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
  [["posts", "*", "turn", "timeout_seconds"], allowNonNegativeInt],
  [["posts", "*", "turn", "tools", "*"], allowToolName],
  [["posts", "*", "turn", "budgets", "max_requests"], allowNonNegativeInt],
  [["posts", "*", "turn", "budgets", "max_tool_calls"], allowNonNegativeInt],
  [["posts", "*", "turn", "budgets", "max_input_bytes"], allowNonNegativeInt],
  [["posts", "*", "turn", "budgets", "max_response_bytes"], allowNonNegativeInt],
  [["posts", "*", "turn", "budgets", "max_object_bytes"], allowNonNegativeInt],
  [["posts", "*", "last_turn", "at"], allowIsoSecondUtc],
  [["posts", "*", "last_turn", "adapter"], HUB_ADAPTER_ENUM],
  [["posts", "*", "last_turn", "models", "*"], allowBindingName],
  [["posts", "*", "last_turn", "profile"], allowNullableId],
  [["posts", "*", "last_turn", "thinking", "requested"], HUB_THINKING_ENUM],
  [["posts", "*", "last_turn", "thinking", "mapped"], HUB_THINKING_ENUM],
  [["posts", "*", "last_turn", "thinking", "effective"], allowEffortLevels],
  [["posts", "*", "last_turn", "fallback"], allowNullablePreviewText],
];

/**
 * Quizs 的思考档位（scripts/kit_roles.py 的 Quizs 段与站主核实的 Quizs providers 输出形状）：六个取值。 */
export const QUIZS_THINKING_ENUM = allowEnum("off", "low", "medium", "high", "xhigh", "max");
/** Quizs 的计费方式（站主核实的 Quizs providers 输出形状）：三个取值。 */
export const QUIZS_BILLING_ENUM = allowEnum("none_test_only", "step_plan_credits", "deepseek_prepaid_balance");
/** live 一套的来源（scripts/kit_roles.py 的 _quizs_live_sets）：信箱目录下的与三个环境变量给的那一套。 */
export const QUIZS_LIVE_SOURCE_ENUM = allowEnum("mailbox", "env");
/** live status 的 state（scripts/kit_roles.py 的 QUIZS_LIVE_STATES）：五个取值。 */
export const QUIZS_LIVE_STATE_ENUM = allowEnum("ready", "expired", "build_mismatch", "invalid", "missing");
/** live status 的 missing 里的文件名（scripts/kit_roles.py 的 QUIZS_LIVE_NAMES）：三个名字。 */
export const QUIZS_LIVE_FILE_ENUM = allowEnum("plan.json", "profile.json", "qualification.json");

/** live 的逐套 problem：null 放行（那一套没有问题）；否则沿用 allowPreviewText 的口径（本来就不像凭据的自由文字）。 */
export function allowNullablePreviewText(value: PyValue): boolean {
  return value === null || allowPreviewText(value);
}

/** live 的证书到期毫秒：null 放行；bigint 与 number 都接（pyjson 把大整数解析成 bigint），number 要是整数且不小于 0。 */
export function allowNonNegativeMs(value: PyValue): boolean {
  if (value === null) return true;
  if (typeof value === "bigint") return value >= 0n;
  if (typeof value !== "number") return false;
  return Number.isInteger(value) && value >= 0;
}

/** 带毫秒的 ISO 8601 UTC 字符串：null 放行；形如 2026-11-14T08:00:00.000Z，Z 与 +00:00 两种结尾、三位毫秒。 */
const ISO_MS_UTC_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(?:Z|\+00:00)$/u;
export function allowIsoMsUtc(value: PyValue): boolean {
  return value === null || (typeof value === "string" && ISO_MS_UTC_RE.test(value));
}

/**
 * /quizs/providers 的白名单（config quizs providers --json 的 {"build_id": …, "providers": […]}）：逐字段只放四个能显示的
 * 字段——提供方与模型（名字形状，内核会给 null）用 allowBindingName，思考档位与计费方式过枚举；取值抄自
 * scripts/kit_roles.py 的 Quizs 段与站主核实的 Quizs 输出形状。build_id、id、credential_*、*_tokens 一类键不登记，照
 * redactJson 的默认口径走（键名像凭据的一律 <redacted>）。
 */
export const QUIZS_PROVIDERS_ALLOW: AllowList = [
  [["providers", "*", "provider"], allowBindingName],
  [["providers", "*", "model"], allowBindingName],
  [["providers", "*", "thinking", "*"], QUIZS_THINKING_ENUM],
  [["providers", "*", "billing"], QUIZS_BILLING_ENUM],
];

/**
 * /quizs/live 的白名单（config quizs live --json 的 {"live": […]}）：每一套的来源、提供方、逐套 problem，以及 status 的
 * problem、state、missing、证书到期毫秒与 profile 的 valid_until；取值抄自 scripts/kit_roles.py 的 QUIZS_LIVE_* 与站主
 * 核实的 live 输出形状。live_dir、plan.*、implementation_digest、capabilities 不登记，照默认口径走。
 */
export const QUIZS_LIVE_ALLOW: AllowList = [
  [["live", "*", "source"], QUIZS_LIVE_SOURCE_ENUM],
  [["live", "*", "provider"], allowBindingName],
  [["live", "*", "problem"], allowNullablePreviewText],
  [["live", "*", "status", "problem"], allowNullablePreviewText],
  [["live", "*", "status", "state"], QUIZS_LIVE_STATE_ENUM],
  [["live", "*", "status", "missing", "*"], QUIZS_LIVE_FILE_ENUM],
  [["live", "*", "status", "certificate", "expires_at_ms"], allowNonNegativeMs],
  [["live", "*", "status", "profile", "valid_until"], allowIsoMsUtc],
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
