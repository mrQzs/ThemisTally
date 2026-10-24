// 二道脱敏的白名单（桌面端 §5.3、D07、U22）：响应先过 redactJson，再按路由登记的白名单做约束校验——白名单只放
// 名字与来源这类可枚举的形状。换成令牌形状、枚举之外的值、多出来的键或任意文本都被遮成 <redacted>；不合约束的
// 白名单值照样遮掉；decisions.secret.file_dir 不登记（落在 secret 键下，照样被遮掉）。
import { describe, expect, it } from "vitest";
import { dumps, loads, type PyValue } from "@themis/base/pyjson";
import { redactJson } from "@themis/base/secrets";
import { CONFIG_ALLOW, PROFILES_ALLOW, SECRETS_ALLOW, SECRET_SHOW_ALLOW, usedByShape } from "../src/redaction.ts";

const TOKEN = "sk-abcdefghijklmnopqrstuvwxyz0123456789";

/** 脱敏之后按 pyjson 写出（Map 会正常展开，便于断言里查子串）。 */
const text = (value: PyValue): string => dumps(redactJson(value, CONFIG_ALLOW), { ensureAscii: false });

/** Map/数组递归换成普通对象，便于 toEqual。 */
function plain(value: PyValue): unknown {
  if (value instanceof Map) {
    const out: Record<string, unknown> = {};
    for (const [key, item] of value) out[String(key)] = plain(item);
    return out;
  }
  if (Array.isArray(value)) return value.map(plain);
  return value;
}

describe("usedByShape", () => {
  it("键恰好是 {kind} 或 {kind, id}；kind 只认 profile 与 decisions，id 过 allowId", () => {
    expect(usedByShape(loads('{"kind":"decisions"}'))).toBe(true);
    expect(usedByShape(loads('{"kind":"profile","id":"execution"}'))).toBe(true);
    expect(usedByShape(loads('{"kind":"other"}'))).toBe(false);
    expect(usedByShape(loads('{"kind":"profile","id":"Bad_ID"}'))).toBe(false);
    expect(usedByShape(loads('{"kind":"profile","id":"execution","extra":1}'))).toBe(false);
    expect(usedByShape(loads('{"id":"execution"}'))).toBe(false);
    expect(usedByShape(loads('["profile"]'))).toBe(false);
    expect(usedByShape(loads('"decisions"'))).toBe(false);
  });
});

describe("/config 的白名单", () => {
  it("环境变量名与枚举原样返回", () => {
    const shown = text(
      loads(`{"decisions":{"env_var_name":"TYPESAFE_API_KEY","secret":{"name":"TYPESAFE_API_KEY","source":"env",`
        + `"store_mode":"system","system_backend":"windows-credential-manager","file_dir":"C:/secret/dir"}}}`),
    );
    expect(shown).toContain("TYPESAFE_API_KEY");
    expect(shown).toContain('"source": "env"');
    expect(shown).toContain('"store_mode": "system"');
    expect(shown).toContain("windows-credential-manager");
    expect(shown).not.toContain("C:/secret/dir"); // file_dir 不登记：照样被遮掉
    expect(shown).toContain("<redacted>");
  });

  it("keys 里的 env_remove、env_keep 与 decisions.api_key_env 原样；令牌形状被遮", () => {
    const shown = redactJson(
      loads(`{"keys":[{"key":"env_remove","value":["KEEP_ONE","${TOKEN}"]},`
        + `{"key":"env_keep","value":["ALSO_KEEP"]},{"key":"decisions","value":{"api_key_env":"TYPESAFE_API_KEY"}}]}`),
      CONFIG_ALLOW,
    ) as Map<string, unknown>;
    const rows = [...(shown.get("keys") as unknown[])] as Map<string, unknown>[];
    expect(rows[0]?.get("value")).toEqual(["KEEP_ONE", "<redacted>"]);
    expect(rows[1]?.get("value")).toEqual(["ALSO_KEEP"]);
    expect((rows[2]?.get("value") as Map<string, unknown>).get("api_key_env")).toBe("TYPESAFE_API_KEY");
  });

  it("枚举之外的值换成 <redacted>", () => {
    const shown = text(loads('{"decisions":{"secret":{"source":"magic","store_mode":"cloud","system_backend":"keychain"}}}'));
    expect(shown).toContain("<redacted>");
    expect(shown).not.toContain("magic");
    expect(shown).not.toContain("keychain");
  });

  it("system_backend 为 null 时原样（内核的取值里有 null）", () => {
    const shown = text(loads('{"decisions":{"secret":{"system_backend":null}}}'));
    expect(shown).toContain('"system_backend": null');
  });
});

describe("/profiles 的白名单", () => {
  it("credential_env 里的环境变量名原样；令牌形状遮掉", () => {
    const shown = redactJson(loads(`{"profiles":[{"id":"execution","credential_env":["TYPESAFE_API_KEY","${TOKEN}"]}]}`), PROFILES_ALLOW) as Map<string, unknown>;
    const rows = [...(shown.get("profiles") as unknown[])] as Map<string, unknown>[];
    expect(rows[0]?.get("credential_env")).toEqual(["TYPESAFE_API_KEY", "<redacted>"]);
  });
});

describe("/secrets 的白名单", () => {
  it("name、source、store_mode、system_backend、used_by 原样；不含 file_dir", () => {
    const shown = redactJson(
      loads('{"secrets":[{"name":"TYPESAFE_API_KEY","source":"env","store_mode":"system",'
        + '"system_backend":"windows-credential-manager","used_by":[{"kind":"decisions"},{"kind":"profile","id":"execution"}]}]}'),
      SECRETS_ALLOW,
    ) as Map<string, unknown>;
    const rows = [...(shown.get("secrets") as unknown[])] as Map<string, unknown>[];
    expect(rows[0]?.get("name")).toBe("TYPESAFE_API_KEY");
    expect(rows[0]?.get("source")).toBe("env");
    expect(plain(rows[0]?.get("used_by") as PyValue)).toEqual([{ kind: "decisions" }, { kind: "profile", id: "execution" }]);
    expect(rows[0]?.has("file_dir")).toBe(false);
  });

  it("used_by 多一个键或任意文本：换成 <redacted>", () => {
    const shown = redactJson(
      loads('{"secrets":[{"name":"A_KEY","used_by":[{"kind":"profile","id":"execution","note":"x"}]},'
        + '{"name":"B_KEY","used_by":["decisions"]}]}'),
      SECRETS_ALLOW,
    ) as Map<string, unknown>;
    const rows = [...(shown.get("secrets") as unknown[])] as Map<string, unknown>[];
    expect(plain(rows[0]?.get("used_by") as PyValue)).toEqual(["<redacted>"]);
    expect(plain(rows[1]?.get("used_by") as PyValue)).toEqual(["<redacted>"]);
  });

  it("名字换成令牌形状：遮掉", () => {
    const shown = redactJson(loads(`{"secrets":[{"name":"${TOKEN}"}]}`), SECRETS_ALLOW) as Map<string, unknown>;
    const rows = [...(shown.get("secrets") as unknown[])] as Map<string, unknown>[];
    expect(rows[0]?.get("name")).toBe("<redacted>");
  });
});

describe("/secrets/<name> 的白名单", () => {
  it("name、source、store_mode、system_backend 原样；file_dir 不在数据里", () => {
    const shown = redactJson(
      loads('{"name":"TYPESAFE_API_KEY","source":"none","store_mode":"off","system_backend":null,"file_dir":"C:/secret/dir"}'),
      SECRET_SHOW_ALLOW,
    ) as Map<string, unknown>;
    expect(shown.get("name")).toBe("TYPESAFE_API_KEY");
    expect(shown.get("store_mode")).toBe("off");
    expect(shown.get("system_backend")).toBe(null);
    expect(shown.get("file_dir")).toBe("C:/secret/dir"); // 顶层且不在白名单：服务不把它放进 data（见 readroutes）
  });
});
