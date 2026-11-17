// 二道脱敏的白名单（桌面端 §5.3、D07、U22）：响应先过 redactJson，再按路由登记的白名单做约束校验——白名单只放
// 名字与来源这类可枚举的形状。换成令牌形状、枚举之外的值、多出来的键或任意文本都被遮成 <redacted>；不合约束的
// 白名单值照样遮掉；decisions.secret.file_dir 不登记（落在 secret 键下，照样被遮掉）。
import { describe, expect, it } from "vitest";
import { dumps, loads, type PyValue } from "@themis/base/pyjson";
import { redactJson } from "@themis/base/secrets";
import {
  CONFIG_ALLOW, HUB_ROLES_ALLOW, PREVIEW_ALLOW, PROFILES_ALLOW, SECRETS_ALLOW, SECRET_SHOW_ALLOW, usedByShape,
} from "../src/redaction.ts";

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

describe("/preview 的白名单：七端岗位的前后（r3 第 162 轮）", () => {
  it("岗位名、两侧的 source、六个绑定字段与替补的字段放行；不像名字的值与令牌形状遮掉", () => {
    const before = `{"source":"default","profile":null,"runtime":null,"adapter":"pi","provider":"minimax","model":"MiniMax-M3.1-Flash",`
      + `"thinking":"high","fallback":null}`;
    const after = `{"source":"config","profile":"qz-mm","runtime":"qz","adapter":"quizs","provider":"minimax","model":"two words",`
      + `"thinking":"high","fallback":{"profile":"pi-mm","runtime":"pi","adapter":"pi","provider":"${TOKEN}","model":"MiniMax-M3.1-Flash",`
      + `"thinking":"max"}}`;
    const shown = plain(redactJson(loads(`{"hub_changes":[{"post":"contract","before":${before},"after":${after}}]}`), PREVIEW_ALLOW));
    expect(shown).toEqual({
      hub_changes: [{
        post: "contract",
        before: { source: "default", profile: null, runtime: null, adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "high", fallback: null },
        // 有空格的值不是名字的形状：过 allowPreviewName 才会被遮（不登记时只过 redactSecrets，会原样留下）
        after: {
          source: "config", profile: "qz-mm", runtime: "qz", adapter: "quizs", provider: "minimax", model: "<redacted>", thinking: "high",
          fallback: { profile: "pi-mm", runtime: "pi", adapter: "pi", provider: "<redacted>", model: "MiniMax-M3.1-Flash", thinking: "max" },
        },
      }],
    });
  });
});

describe("/preview 的白名单：改到的岗位此刻在跑的回合（r3 第 163 轮）", () => {
  it("running_turns 的每一句照预览的自由文字放行，带凭据形状的那一句整句遮掉", () => {
    // 不登记时只过 redactSecrets，只遮句子里的那一段（「前缀 <redacted> 后缀」）
    const shown = plain(redactJson(loads(`{"running_turns":["审核端（audit）：2 个回合在跑","前缀 ${TOKEN} 后缀"]}`), PREVIEW_ALLOW));
    expect(shown).toEqual({ running_turns: ["审核端（audit）：2 个回合在跑", "<redacted>"] });
  });
});

describe("/hub/roles 的白名单：每行的 turn 与 last_turn（T047 片一）", () => {
  // 退回替补的原因文字带本机路径（scripts/kit_hub.py:2145 的「读不出资格证书 %s」）：JSON 里经 stringify 转义
  const FALLBACK = "读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json";
  const row = (extra: string): Map<string, unknown> =>
    redactJson(loads(`{"posts":[${extra}]}`), HUB_ROLES_ALLOW) as Map<string, unknown>;
  const first = (extra: string): Map<string, unknown> =>
    ((row(extra).get("posts") as unknown[])[0] as Map<string, unknown>);

  it("合格值原样放行：时限、工具（含 Bash(npm view:*)）、预算五项、秒级时刻、多档位生效、带本机路径的 fallback", () => {
    const one = first(
      `{"post":"coordinator","source":"default","allowed_adapters":["quizs","pi"],"adapter":"quizs",`
      + `"provider":"deepseek","model":"deepseek-flash","thinking":"high","profile":null,"runtime":null,"fallback":null,`
      + `"turn":{"timeout_seconds":600,"tools":["read","grep","find","ls","edit","write","bash","Read","Grep",`
      + `"Glob","Bash(npm view:*)"],"budgets":{"max_requests":32,"max_tool_calls":48,"max_input_bytes":2097152,`
      + `"max_response_bytes":8388608,"max_object_bytes":8388608}},`
      + `"last_turn":{"at":"2026-11-15T08:00:00Z","adapter":"quizs","models":["deepseek-flash"],"profile":null,`
      + `"thinking":{"requested":"high","mapped":"high","effective":"high,medium"},`
      + `"fallback":${JSON.stringify(FALLBACK)}}}`,
    );
    const turn = one.get("turn") as Map<string, unknown>;
    expect(Number(turn.get("timeout_seconds"))).toBe(600);
    expect(turn.get("tools")).toEqual(["read", "grep", "find", "ls", "edit", "write", "bash", "Read", "Grep", "Glob", "Bash(npm view:*)"]);
    const budgets = turn.get("budgets") as Map<string, unknown>;
    expect(Number(budgets.get("max_requests"))).toBe(32);
    expect(Number(budgets.get("max_tool_calls"))).toBe(48);
    expect(Number(budgets.get("max_input_bytes"))).toBe(2097152);
    expect(Number(budgets.get("max_response_bytes"))).toBe(8388608);
    expect(Number(budgets.get("max_object_bytes"))).toBe(8388608);
    const lastTurn = one.get("last_turn") as Map<string, unknown>;
    expect(lastTurn.get("at")).toBe("2026-11-15T08:00:00Z");
    expect(lastTurn.get("adapter")).toBe("quizs");
    expect(lastTurn.get("models")).toEqual(["deepseek-flash"]);
    expect(lastTurn.get("profile")).toBe(null);
    const thinking = lastTurn.get("thinking") as Map<string, unknown>;
    expect(thinking.get("requested")).toBe("high");
    expect(thinking.get("mapped")).toBe("high");
    expect(thinking.get("effective"), "逗号连起来的多个档位逐段放行").toBe("high,medium");
    expect(lastTurn.get("fallback"), "带本机路径的原因文字照 allowNullablePreviewText 放行")
      .toBe("读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json");
    expect(dumps(one as unknown as PyValue, { ensureAscii: false })).not.toContain("<redacted>");
  });

  it("+00:00 结尾的秒级时刻同样放行", () => {
    const one = first(
      `{"post":"planner","source":"default","allowed_adapters":["claude-code"],"adapter":"claude-code",`
      + `"provider":null,"model":"claude-opus-5-5","thinking":"max","profile":null,"runtime":null,"fallback":null,`
      + `"turn":null,"last_turn":{"at":"2026-11-15T08:00:00+00:00","adapter":"claude-code",`
      + `"models":["claude-opus-5-5"],"profile":null,"thinking":{"requested":"max","mapped":null,`
      + `"effective":"max"},"fallback":null}}`,
    );
    expect((one.get("last_turn") as Map<string, unknown>).get("at")).toBe("2026-11-15T08:00:00+00:00");
  });

  it("不合格值换成 <redacted>：负数与小数时限、带毫秒的时刻、非法档位、像凭据的工具名", () => {
    const one = first(
      `{"post":"gate","source":"default","allowed_adapters":["pi"],"adapter":"pi","provider":null,"model":null,`
      + `"thinking":"high","profile":null,"runtime":null,"fallback":null,`
      + `"turn":{"timeout_seconds":-1,"tools":["read","${TOKEN}"],"budgets":{"max_requests":1.5,`
      + `"max_tool_calls":48,"max_input_bytes":2097152,"max_response_bytes":8388608,"max_object_bytes":8388608}},`
      + `"last_turn":{"at":"2026-11-15T08:00:00.000Z","adapter":"pi","models":["glm-5.3"],"profile":null,`
      + `"thinking":{"requested":"high","mapped":null,"effective":"high,bogus"},"fallback":null}}`,
    );
    const turn = one.get("turn") as Map<string, unknown>;
    expect(turn.get("timeout_seconds")).toBe("<redacted>");
    expect(turn.get("tools")).toEqual(["read", "<redacted>"]);
    expect((turn.get("budgets") as Map<string, unknown>).get("max_requests")).toBe("<redacted>");
    const lastTurn = one.get("last_turn") as Map<string, unknown>;
    expect(lastTurn.get("at")).toBe("<redacted>");
    expect((lastTurn.get("thinking") as Map<string, unknown>).get("effective")).toBe("<redacted>");
    expect((lastTurn.get("thinking") as Map<string, unknown>).get("requested")).toBe("high");
  });

  it("HUB_ROLES_ALLOW 原有 15 条路径一条不少（逐条比对路径元组），四层对象本身不登记", () => {
    const paths = HUB_ROLES_ALLOW.map(([path]) => path);
    const has = (...segments: string[]): boolean => paths.some((path) => path.length === segments.length && path.every((seg, i) => seg === segments[i]));
    for (const path of [
      ["posts", "*", "post"], ["posts", "*", "source"], ["posts", "*", "allowed_adapters", "*"],
      ["posts", "*", "adapter"], ["posts", "*", "provider"], ["posts", "*", "model"],
      ["posts", "*", "thinking"], ["posts", "*", "profile"], ["posts", "*", "runtime"],
      ["posts", "*", "fallback", "adapter"], ["posts", "*", "fallback", "provider"],
      ["posts", "*", "fallback", "model"], ["posts", "*", "fallback", "thinking"],
      ["posts", "*", "fallback", "profile"], ["posts", "*", "fallback", "runtime"],
    ]) {
      expect(has(...path), `既有路径 ${path.join(".")} 应仍在白名单里`).toBe(true);
    }
    // T031 只认 turn/last_turn 之下的叶子路径：这四层对象登记了会被判成「别的路径」
    for (const layer of [
      ["posts", "*", "turn"], ["posts", "*", "last_turn"], ["posts", "*", "turn", "budgets"], ["posts", "*", "last_turn", "thinking"],
    ]) {
      expect(has(...layer), `对象层 ${layer.join(".")} 不许登记`).toBe(false);
    }
    expect(paths).toHaveLength(30);
  });
});
