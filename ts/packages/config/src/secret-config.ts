// pi_dispatch.secret_config_error（迁移第 ③a2 片）：配置的某个键之下有疑似凭据时报的那一句，只列位置、不带取值（D9）。
// 配置中心拿某个键的取值去校验、摘要、列表之前都先过这一关。
import type { PyValue } from "@themis/base/pyjson";
import { SECRET_KEY_SHOWN, secretLikePaths, tokenShaped } from "@themis/base/secrets";

export function secretConfigError(config: PyValue, key: string): string | null {
  if (!(config instanceof Map) || !config.has(key)) return null;
  const suspicious = secretLikePaths(new Map([[key, config.get(key) as PyValue]]));
  if (!suspicious.length) return null;
  // 下划线说明键的名字可以是任意文字：像令牌的键名不回显
  const shown = tokenShaped(key) ? SECRET_KEY_SHOWN : key;
  return `${shown} 里有疑似凭据（${suspicious.slice(0, 5).join("、")}）：配置里只写环境变量名，凭据的值用 config secret set 存`;
}
