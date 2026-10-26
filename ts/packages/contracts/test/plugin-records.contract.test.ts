// codekit/plugins.py 记录层的契约（迁移第 ③a1 片）：manifest 与内容锁的校验、规范字节与摘要、依赖解析、权限交集。
// 报错文字 "<code> at <path>: <message>" 会进 validate 与 plugins verify 的输出，逐字比较。用例以 plugins/ 下提交的真实
// manifest 与锁为底改出各种坏法；每条先断言 Python 的结果（契约描述的是现行行为），再要求 TS 两种运行方式与 Python 逐字一致。
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { PYTHON, type ProbeRequest, REPO, prng, runAgreeing, runBatch } from "./harness.ts";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

const PLUGINS = readdirSync(join(REPO, "plugins")).sort();
const real = (plugin: string, file: string): string => readFileSync(join(REPO, "plugins", plugin, file), "utf8");
const parsed = (plugin: string, file: string): { [key: string]: Json } => JSON.parse(real(plugin, file)) as { [key: string]: Json };
const MANIFEST = parsed("decisions", "manifest.json");
const LOCK = parsed("decisions", "lock.json");

/** 已经写好的 JSON 文本（要用到 JS 写不出的值：NaN、超出精度的整数、1.0、孤立代理项的转义）。 */
class Raw {
  readonly text: string;
  constructor(text: string) {
    this.text = text;
  }
}
const raw = (jsonText: string): Raw => new Raw(jsonText);
const text = (value: Json): string => JSON.stringify(value);
const call = (fn: string, ...args: (Json | Raw)[]): ProbeRequest => ({
  op: "plugins.call",
  fn,
  json_args: args.map((arg) => (arg instanceof Raw ? arg.text : text(arg))),
});
const manifestWith = (patch: { [key: string]: Json }, drop: string[] = []): Json => {
  const out: { [key: string]: Json } = { ...MANIFEST, ...patch };
  for (const key of drop) delete out[key];
  return out;
};
const resource = (path: string, id = path, sha = "0".repeat(64)): Json => ({ kind: "file", id, path, sha256: sha });
const registry = (...manifests: Json[]): Json =>
  Object.fromEntries(manifests.map((manifest) => [String((manifest as { [key: string]: Json } | null)?.["plugin_id"]), manifest]));
const plugin = (id: string, patch: { [key: string]: Json } = {}): { [key: string]: Json } => ({
  ...MANIFEST,
  plugin_id: id,
  resources: [resource(`plugins/${id}/README.md`, `${id}.readme`)],
  ...patch,
});

/** 锁的行与 manifest 的摘要对得上、资源列表却少了一项：锁自身的摘要用 Python 现算，这样只剩“资源列表要相等”这一条拦得住。 */
function lockWithFewerResources(): Json {
  const row = (LOCK["plugins"] as { [key: string]: Json }[])[0] as { [key: string]: Json };
  const fewer = { ...row, resources: (row["resources"] as Json[]).slice(0, -1) };
  const body = { record_type: LOCK["record_type"] as Json, schema_version: 1, generation: LOCK["generation"] as Json, compiler_sha256: LOCK["compiler_sha256"] as Json, plugins: [fewer] };
  const [result] = runBatch(PYTHON, [call("digest", body)]);
  return { ...body, lock_sha256: (result?.["value"] as { v: string }).v };
}

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  /** Python 的报错原文；undefined 表示应当通过。 */
  readonly error?: string;
}

const fails = (name: string, request: ProbeRequest, error: string): Case => ({ name, request, error });
const passes = (name: string, request: ProbeRequest): Case => ({ name, request });

const CASES: readonly Case[] = [
  passes("真实的 decisions manifest", call("validate_manifest", MANIFEST)),
  passes("真实的 decisions 锁绑定 manifest", call("validate_lock", LOCK, registry(MANIFEST))),
  passes("规范字节", call("canonical_bytes", MANIFEST)),
  passes("摘要", call("digest", LOCK)),
  fails("manifest 不是对象", call("validate_manifest", [1]), "E_PLUGIN_SCHEMA at /: manifest must be an object"),
  fails("未知字段按码点排序（UTF-16 的排法会把 Ａ 排到 😀 后面）", call("validate_manifest", manifestWith({ "Ａ": 1, "😀": 1 })), "E_PLUGIN_UNKNOWN_FIELD at /: unknown fields: ['Ａ', '😀']"),
  fails("未知字段按码点排序列出", call("validate_manifest", manifestWith({ zeta: 1, "😀": 1, alpha: 1 })), "E_PLUGIN_UNKNOWN_FIELD at /: unknown fields: ['alpha', 'zeta', '😀']"),
  fails("缺字段", call("validate_manifest", manifestWith({}, ["roles", "checks"])), "E_PLUGIN_SCHEMA at /: missing fields: ['checks', 'roles']"),
  fails("plugin_id 是空串", call("validate_manifest", manifestWith({ plugin_id: "" })), "E_PLUGIN_SCHEMA at /plugin_id: non-empty string required"),
  fails("schema_version 是 true", call("validate_manifest", manifestWith({ schema_version: true })), "E_PLUGIN_VERSION at /record_type: manifest schema version 1 required"),
  fails("schema_version 是 1.0", call("validate_manifest", raw(text(manifestWith({})).replace('"schema_version":1', '"schema_version":1.0'))), "E_PLUGIN_VERSION at /record_type: manifest schema version 1 required"),
  fails("plugin_id 是会变动的别名", call("validate_manifest", manifestWith({ plugin_id: "latest" })), "E_PLUGIN_IDENTITY at /plugin_id: lowercase plugin id required"),
  fails("plugin_id 末尾有换行（fullmatch）", call("validate_manifest", manifestWith({ plugin_id: "decisions\n" })), "E_PLUGIN_IDENTITY at /plugin_id: lowercase plugin id required"),
  fails("version 不是三段", call("validate_manifest", manifestWith({ version: "1.0" })), "E_PLUGIN_VERSION at /version: exact semantic version required"),
  fails("api_version 含别名（大小写不论）", call("validate_manifest", manifestWith({ api_version: "v1-LATEST" })), "E_PLUGIN_VERSION at /version: mutable aliases are forbidden"),
  passes("api_version 的别名紧贴字母数字不算", call("validate_manifest", manifestWith({ api_version: "latest2" }))),
  fails("roles 有重复", call("validate_manifest", manifestWith({ roles: ["a", "a"] })), "E_PLUGIN_SCHEMA at /roles: duplicate value"),
  fails("capabilities 有 257 个码点的项（补充平面字符按一个算）", call("validate_manifest", manifestWith({ capabilities: ["😀".repeat(257)] })), "E_PLUGIN_SCHEMA at /capabilities: unique non-empty string array required"),
  passes("capabilities 的项正好 256 个码点", call("validate_manifest", manifestWith({ capabilities: ["😀".repeat(256)] }))),
  fails("depends_on 里有别名", call("validate_manifest", manifestWith({ depends_on: ["ok", "main"] })), "E_PLUGIN_IDENTITY at /depends_on/1: lowercase plugin id required"),
  fails("资源路径穿越", call("validate_manifest", manifestWith({ resources: [resource("plugins/../x")] })), "E_PLUGIN_PATH at /resources/0/path: absolute and traversal paths are forbidden"),
  fails("资源路径带盘符", call("validate_manifest", manifestWith({ resources: [resource("C:x")] })), "E_PLUGIN_PATH at /resources/0/path: absolute and traversal paths are forbidden"),
  fails("资源路径第二个码点是冒号（第一个是补充平面字符）", call("validate_manifest", manifestWith({ resources: [resource("😀:x")] })), "E_PLUGIN_PATH at /resources/0/path: absolute and traversal paths are forbidden"),
  fails("资源路径反斜杠开头", call("validate_manifest", manifestWith({ resources: [resource("\\x")] })), "E_PLUGIN_PATH at /resources/0/path: absolute and traversal paths are forbidden"),
  fails("资源路径以 ./ 开头", call("validate_manifest", manifestWith({ resources: [resource("./x")] })), "E_PLUGIN_PATH at /resources/0/path: absolute and traversal paths are forbidden"),
  passes("资源路径照 NFC 规整（分解的 é 写成组合的）", call("validate_manifest", manifestWith({ resources: [resource("a/é.md")] }))),
  passes("资源路径的反斜杠换成斜杠", call("validate_manifest", manifestWith({ resources: [resource("plugins\\x\\y.md")] }))),
  fails("资源路径大小写不同算同一个", call("validate_manifest", manifestWith({ resources: [resource("a/B.md", "1"), resource("a/b.md", "2")] })), "E_PLUGIN_RESOURCE at /resources/1/path: resource path aliases entry 0"),
  fails("资源路径 ſ 与 s 折叠后相同", call("validate_manifest", manifestWith({ resources: [resource("a/ſ.md", "1"), resource("a/s.md", "2")] })), "E_PLUGIN_RESOURCE at /resources/1/path: resource path aliases entry 0"),
  fails("资源路径 ß 与 ss 折叠后相同", call("validate_manifest", manifestWith({ resources: [resource("a/ß.md", "1"), resource("a/ss.md", "2")] })), "E_PLUGIN_RESOURCE at /resources/1/path: resource path aliases entry 0"),
  fails("资源路径组合与分解的 é 规范化后相同", call("validate_manifest", manifestWith({ resources: [resource("a/\u00e9.md", "1"), resource("a/e\u0301.md", "2")] })), "E_PLUGIN_RESOURCE at /resources/1/path: resource path aliases entry 0"),
  fails("资源的 kind 与 id 重复", call("validate_manifest", manifestWith({ resources: [resource("a/1.md", "x"), resource("a/2.md", "x")] })), "E_PLUGIN_RESOURCE at /resources: duplicate resource identity"),
  fails("资源的 sha256 是大写", call("validate_manifest", manifestWith({ resources: [resource("a/1.md", "x", "A".repeat(64))] })), "E_PLUGIN_RESOURCE at /resources/0/sha256: lowercase SHA-256 required"),
  fails("资源多一个键", call("validate_manifest", manifestWith({ resources: [{ kind: "file", id: "x", path: "a", sha256: "0".repeat(64), more: 1 }] })), "E_PLUGIN_RESOURCE at /resources/0: closed ResourceRef required"),
  fails("资源的 id 含控制字符", call("validate_manifest", manifestWith({ resources: [resource("a/1.md", "x\u0007")] })), "E_PLUGIN_RESOURCE at /resources/0/id: non-empty string required"),
  fails("检查命令联网", call("validate_manifest", manifestWith({ checks: [{ id: "c", command: ["curl", "HTTPS://x"], deterministic: true }] })), "E_PLUGIN_CHECK at /checks/0/command: dynamic import, network and mutable alias are forbidden"),
  fails("检查命令含别名", call("validate_manifest", manifestWith({ checks: [{ id: "c", command: ["git", "checkout", "Master"], deterministic: true }] })), "E_PLUGIN_CHECK at /checks/0/command: dynamic import, network and mutable alias are forbidden"),
  fails("检查不是封闭的三个键", call("validate_manifest", manifestWith({ checks: [{ id: "c", command: ["x"] }] })), "E_PLUGIN_CHECK at /checks/0: closed id/command/deterministic check required"),
  fails("检查 id 重复", call("validate_manifest", manifestWith({ checks: [{ id: "c", command: ["x"], deterministic: true }, { id: "c", command: ["y"], deterministic: true }] })), "E_PLUGIN_CHECK at /checks: duplicate check id"),
  fails("没有角色的插件要求确定性的检查", call("validate_manifest", manifestWith({ checks: [{ id: "c", command: ["x"], deterministic: false }] })), "E_PLUGIN_CHECK at /checks: role-free plugins require explicit deterministic checks"),
  fails("检查不是对象", call("validate_manifest", manifestWith({ checks: ["c"] })), "E_PLUGIN_SCHEMA at /checks: check descriptor array required"),
  fails("重复的键取最后一个值（capabilities 成了整数列表）", call("validate_manifest", raw(text(manifestWith({})).replace('"conflicts":[]', '"conflicts":[],"capabilities":[9007199254740992]'))), "E_PLUGIN_SCHEMA at /capabilities: unique non-empty string array required"),
  fails("NaN 进规范字节", call("canonical_bytes", raw('{"a":[1,NaN]}')), "E_PLUGIN_JSON at /a/1/: finite JSON number required"),
  fails("孤立代理项进规范字节", call("canonical_bytes", raw('{"a":"\\ud800"}')), "E_PLUGIN_JSON at /a/: safe Unicode text required"),
  fails("键含控制字符", call("canonical_bytes", { "a\u0001": 1 }), "E_PLUGIN_JSON at /: safe Unicode object keys required"),
  fails("大整数进规范字节", call("canonical_bytes", raw("[9007199254740992]")), "E_PLUGIN_JSON at /0/: integer exceeds exact JSON range"),
  fails("负的大整数进规范字节", call("canonical_bytes", raw("[-9007199254740992]")), "E_PLUGIN_JSON at /0/: integer exceeds exact JSON range"),
  passes("最大的安全整数可以", call("canonical_bytes", raw("[9007199254740991, -9007199254740991, 1e300, -0.0, 0.1]"))),
  fails("嵌套超过 64 层", call("canonical_bytes", raw("[".repeat(66) + "]".repeat(66))), `E_PLUGIN_JSON at /${"0/".repeat(65)}: maximum JSON depth exceeded`),
  fails("数组超过 512 项", call("canonical_bytes", { a: Array.from({ length: 513 }, () => 1) }), "E_PLUGIN_SCHEMA at /a/: array exceeds limit"),
  fails("锁的头不对", call("validate_lock", { ...LOCK, generation: 0 }), "E_PLUGIN_LOCK at /: invalid lock header"),
  fails("锁多一个键", call("validate_lock", { ...LOCK, extra: 1 }), "E_PLUGIN_LOCK at /: closed plugin lock required"),
  fails("锁的摘要对不上", call("validate_lock", { ...LOCK, lock_sha256: "1".repeat(64) }), "E_PLUGIN_LOCK_DRIFT at /lock_sha256: lock bytes do not match"),
  fails("锁的 compiler_sha256 不是十六进制", call("validate_lock", { ...LOCK, compiler_sha256: "x" }), "E_PLUGIN_LOCK at /compiler_sha256: lowercase SHA-256 required"),
  fails("锁的 generation 超出精确范围（摘要时才查出）", call("validate_lock", raw(text(LOCK).replace('"generation":1', '"generation":9007199254740993'))), "E_PLUGIN_JSON at /generation/: integer exceeds exact JSON range"),
  fails("锁的资源列表与 manifest 不同（摘要都对得上）", call("validate_lock", lockWithFewerResources(), registry(MANIFEST)), "E_PLUGIN_LOCK_BINDING at /plugins/decisions: lock is not bound to manifest bytes"),
  fails("锁与 manifest 的版本不符", call("validate_lock", LOCK, registry({ ...MANIFEST, version: "1.0.1" })), "E_PLUGIN_LOCK_BINDING at /plugins/decisions: lock is not bound to manifest bytes"),
  fails("锁与 manifest 的插件集合不符", call("validate_lock", LOCK, registry(MANIFEST, plugin("other"))), "E_PLUGIN_LOCK_BINDING at /plugins: lock plugin set does not match manifests"),
  fails("锁的行不是封闭的四个键", call("validate_lock", { ...LOCK, plugins: [{ plugin_id: "decisions" }] }), "E_PLUGIN_LOCK at /plugins/0: closed plugin lock row required"),
  fails("锁里的资源不按 (kind, id) 排", call("validate_lock", { ...LOCK, plugins: [{ ...(LOCK["plugins"] as { [key: string]: Json }[])[0], resources: [...((LOCK["plugins"] as { [key: string]: Json[] }[])[0]?.["resources"] ?? [])].reverse() }] }), "E_PLUGIN_LOCK at /plugins/0/resources: resources must be in canonical order"),
  fails("锁里的插件不按 id 排", call("validate_lock", { ...LOCK, plugins: [{ plugin_id: "zz", version: "1.0.0", manifest_sha256: "0".repeat(64), resources: [] }, { plugin_id: "aa", version: "1.0.0", manifest_sha256: "0".repeat(64), resources: [] }] }), "E_PLUGIN_LOCK at /plugins: plugins must be in canonical order"),
  fails("锁里两个插件的资源路径冲突", call("validate_lock", { ...LOCK, plugins: [{ plugin_id: "aa", version: "1.0.0", manifest_sha256: "0".repeat(64), resources: [resource("x/A")] }, { plugin_id: "bb", version: "1.0.0", manifest_sha256: "0".repeat(64), resources: [resource("x/a")] }] }), "E_PLUGIN_RESOURCE at /plugins/1/resources/0/path: resource path collides with aa/resources/0"),
  fails("依赖成环", call("resolve_plugins", registry(plugin("aa", { depends_on: ["bb"] }), plugin("bb", { depends_on: ["aa"] })), ["aa"]), "E_PLUGIN_CYCLE at /depends_on: dependency cycle includes aa"),
  fails("缺依赖", call("resolve_plugins", registry(plugin("aa", { depends_on: ["zz"] })), ["aa"]), "E_PLUGIN_DEPENDENCY at /plugins/aa/depends_on: missing dependency zz"),
  fails("启用了没登记的插件", call("resolve_plugins", registry(plugin("aa")), ["bb"]), "E_PLUGIN_DEPENDENCY at /enabled/bb: plugin is not registered"),
  fails("注册表的键与 plugin_id 不同", call("resolve_plugins", { xx: plugin("aa") }, ["xx"]), "E_PLUGIN_IDENTITY at /plugins/xx/plugin_id: registry key must match plugin_id"),
  fails("启用的插件互相冲突", call("resolve_plugins", registry(plugin("aa", { conflicts: ["cc", "bb"] }), plugin("bb"), plugin("cc")), ["aa", "bb", "cc"]), "E_PLUGIN_CONFLICT at /plugins/aa/conflicts: enabled conflict ['bb', 'cc']"),
  fails("两个插件的资源路径大小写不同算冲突", call("resolve_plugins", registry(plugin("aa", { resources: [resource("p/X.md")] }), plugin("bb", { resources: [resource("p/x.md")] })), ["aa", "bb"]), "E_PLUGIN_RESOURCE at /plugins/bb/resources/0/path: resource path collides with aa/resources/0"),
  passes("启用的插件按名字排序后依次解析", call("resolve_plugins", registry(plugin("bb"), plugin("aa")), ["bb", "aa"])),
  passes("依赖排在前面", call("resolve_plugins", registry(plugin("cc", { depends_on: ["bb"] }), plugin("bb", { depends_on: ["aa"] }), plugin("aa")), ["cc"])),
  passes("权限与平台都满足", call("check_permission_intersection", MANIFEST, ["network-decisions"], "windows")),
  passes("缺权限、平台不支持", call("check_permission_intersection", MANIFEST, [], "beos")),
  fails("权限列表有重复", call("check_permission_intersection", MANIFEST, ["a", "a"]), "E_PLUGIN_POLICY at /allowed_permissions: permission list must be unique"),
  fails("权限列表不是列表", call("check_permission_intersection", MANIFEST, "network-decisions"), "E_PLUGIN_POLICY at /allowed_permissions: permission list required"),
  fails("平台名是空串", call("check_permission_intersection", MANIFEST, [], ""), "E_PLUGIN_POLICY at /platform_name: platform name must be non-empty text"),
];

describe("codekit/plugins.py 的记录层：契约", () => {
  const { python, mismatches } = runAgreeing(CASES.map((item) => item.request));

  it("每条用例 Python 的结果符合契约", () => {
    const wrong = CASES.flatMap((item, index) => {
      const result = python[index];
      const ok = item.error === undefined ? result?.ok === true : result?.ok === false && result["message"] === item.error;
      return ok ? [] : [{ name: item.name, result }];
    });
    expect(wrong).toEqual([]);
  });

  it("TS 两种运行方式与 Python 逐字一致", () => {
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  });

  it("plugins/ 下提交的全部 manifest 与锁：校验结果、规范字节与摘要逐字一致", () => {
    const requests = PLUGINS.flatMap((name) => {
      const manifest = real(name, "manifest.json");
      const lock = real(name, "lock.json");
      return [call("validate_manifest", raw(manifest)), call("validate_lock", raw(lock), raw(`{"${name}": ${manifest}}`)), call("canonical_bytes", raw(manifest)), call("digest", raw(lock))];
    });
    const result = runAgreeing(requests);
    expect(result.python.every((item) => item.ok)).toBe(true);
    expect(result.mismatches.slice(0, 3), `共 ${result.mismatches.length} 条不一致`).toEqual([]);
  });
});

// --- 对照：从真实的 manifest 出发，按种子随机改坏 ------------------------------------------------

const ODD_STRINGS = ["", "a", "LATEST", "x/../y", "C:\\x", "😀:", "ſ", "ß", "\u00e9", "e\u0301", "\u0130", "\u212a", "a\u0000", "\u03a3", "dev-1", "\t", "x".repeat(300)];
const ODD_VALUES: Json[] = [null, true, false, 0, 1, -1, 1.5, [], {}, ["a"], { a: 1 }, ...ODD_STRINGS];

function mutate(base: Json, next: () => number, depth = 0): Json {
  const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
  if (depth > 3 || next() < 0.3) return pick(ODD_VALUES);
  if (Array.isArray(base)) {
    const copy = [...base];
    const roll = next();
    if (roll < 0.25 && copy.length) copy.splice(Math.floor(next() * copy.length), 1);
    else if (roll < 0.5) copy.push(pick(ODD_VALUES));
    else if (roll < 0.65 && copy.length) copy.push(copy[0] as Json);
    else if (copy.length) {
      const index = Math.floor(next() * copy.length);
      copy[index] = mutate(copy[index] as Json, next, depth + 1);
    }
    return copy;
  }
  if (base !== null && typeof base === "object") {
    const copy = { ...base };
    const keys = Object.keys(copy);
    const roll = next();
    if (roll < 0.2 && keys.length) delete copy[pick(keys)];
    else if (roll < 0.3) copy[pick(ODD_STRINGS)] = pick(ODD_VALUES);
    else if (keys.length) {
      const key = pick(keys);
      copy[key] = mutate(copy[key] as Json, next, depth + 1);
    }
    return copy;
  }
  return pick(ODD_VALUES);
}

describe("codekit/plugins.py 的记录层：随机对照", () => {
  for (const seed of [1, 2, 3]) {
    it(`种子 ${seed}：600 份改坏的 manifest 与锁，三种运行方式逐字一致`, () => {
      const next = prng(seed);
      const requests: ProbeRequest[] = [];
      for (let index = 0; index < 300; index += 1) {
        const manifest = mutate(MANIFEST, next);
        requests.push(call("validate_manifest", manifest));
        requests.push(next() < 0.5 ? call("validate_lock", mutate(LOCK, next)) : call("validate_lock", LOCK, registry(manifest)));
      }
      const { mismatches } = runAgreeing(requests);
      expect(mismatches.slice(0, 3), `种子 ${seed}：共 ${mismatches.length} 条不一致`).toEqual([]);
    });
  }
});
