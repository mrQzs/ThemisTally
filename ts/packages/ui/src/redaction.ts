// 二道脱敏的白名单（桌面端设计第 7 版 §5.3、D07）：响应先过 redactJson，再按路由登记的白名单做约束校验——
// 白名单只放名字与来源这类可枚举的形状，绝不放凭据值。约束不成立的值换成 <redacted>（base 的 redactJson 语义：
// 路径最后一段上的校验函数作用在该路径的值上，命中白名单的值不再按敏感键遮）。file 路由（证据）不登记任何白名单。
import { type PyValue } from "@themis/base/pyjson";
import { type AllowList, allowEnum, allowEnvName, allowId } from "@themis/base/secrets";

/** 内核的 SOURCES（codekit/secrets.py）：凭据的来源。 */
export const SOURCE_ENUM = allowEnum("env", "credential_store", "file", "none");
/** 内核的 STORE_MODES（codekit/secrets.py）：凭据的存放方式。 */
export const STORE_MODE_ENUM = allowEnum("system", "file", "off");
/** 系统后端的名字（codekit/secrets.py）：windows-credential-manager 与 file；没有系统后端时是 null。 */
export const SYSTEM_BACKEND_ENUM = allowEnum("windows-credential-manager", "file", null);

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
