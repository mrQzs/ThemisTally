// codekit/plugins.py 的记录层（迁移第 ③a1 片）：插件 manifest 与内容锁的严格校验、规范字节与摘要。
// 报错文字 "<code> at <path>: <message>" 会经 str(exc) 进 validate、plugins verify 的输出，逐字照 Python；
// 检查的先后次序决定先报哪一条，也照 Python。值是 pyjson 读出的 PyValue（dict 是 Map，int 是 bigint）。
import { createHash } from "node:crypto";
import { pyReprValue } from "@themis/base/pyfmt";
import { type PyDict, PyJsonError, type PyValue, dumps, encodeUtf8 } from "@themis/base/pyjson";
import { cmpCodePoints, codePoints, pyCasefold, pyLen, pyLower, pyNfc } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";

const VERSION_RE = /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/u;
const HEX64 = /^[0-9a-f]{64}$/u;
export const PLUGIN_ID = /^[a-z][a-z0-9-]{0,63}$/u;
// 指向会变动的引用而不是固定的插件身份：注册表的键、依赖名与锁里的行一律拒绝
const MUTABLE_ALIASES = ["latest", "head", "current", "stable", "default", "main", "master", "dev", "tip"];
const MAX_DEPTH = 64;
const MAX_ARRAY_ITEMS = 512;
const MAX_BYTES = 1_048_576;
const MAX_SAFE_INTEGER = 2n ** 53n - 1n;
const UNSAFE_TEXT = /[\u0000-\u001f\u007f\ud800-\udfff]/u;

export class PluginError extends Error {
  override readonly name = "PluginError";
  readonly code: string;
  readonly path: string;
  constructor(code: string, path: string, message: string) {
    super(`${code} at ${path}: ${message}`);
    this.code = code;
    this.path = path;
  }
}

function fail(code: string, path: string, message: string): never {
  throw new PluginError(code, path, message);
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
/** dict.get(key, default)：键在、值为 None 时得到 None，不是 default。 */
const getOr = (dict: PyDict, key: string, fallback: PyValue): PyValue => (dict.has(key) ? (dict.get(key) as PyValue) : fallback);
const isList = (value: PyValue | undefined): value is PyValue[] => Array.isArray(value);
const isStr = (value: PyValue | undefined): value is string => typeof value === "string";
const sortedStrings = (values: Iterable<string>): string[] => [...values].sort(cmpCodePoints);
const reprList = (values: Iterable<string>): string => pyReprValue(sortedStrings(values));

function strictJson(value: PyValue, path = "/", depth = 0): void {
  if (depth > MAX_DEPTH) fail("E_PLUGIN_JSON", path, "maximum JSON depth exceeded");
  if (value === null || typeof value === "boolean") return;
  if (typeof value === "bigint") {
    if ((value < 0n ? -value : value) > MAX_SAFE_INTEGER) fail("E_PLUGIN_JSON", path, "integer exceeds exact JSON range");
    return;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail("E_PLUGIN_JSON", path, "finite JSON number required");
    return;
  }
  if (typeof value === "string") {
    if (UNSAFE_TEXT.test(value)) fail("E_PLUGIN_JSON", path, "safe Unicode text required");
    return;
  }
  if (isDict(value)) {
    for (const [key, child] of value) {
      if (typeof key !== "string") fail("E_PLUGIN_JSON", path, "string object keys required");
      if (UNSAFE_TEXT.test(key)) fail("E_PLUGIN_JSON", path, "safe Unicode object keys required");
      strictJson(child, `${path}${key}/`, depth + 1);
    }
    return;
  }
  if (value.length > MAX_ARRAY_ITEMS) fail("E_PLUGIN_SCHEMA", path, "array exceeds limit");
  value.forEach((child, index) => strictJson(child, `${path}${index}/`, depth + 1));
}

/** json.dumps(sort_keys, 紧凑分隔符, ensure_ascii=False, allow_nan=False) 加换行的 UTF-8 字节。 */
export function canonicalBytes(value: PyValue): Uint8Array {
  strictJson(value);
  let raw: Uint8Array;
  try {
    raw = encodeUtf8(`${dumps(value, { ensureAscii: false, sortKeys: true, separators: [",", ":"], allowNan: false })}\n`);
  } catch (error) {
    if (error instanceof PyJsonError) fail("E_PLUGIN_JSON", "/", error.message);
    throw error;
  }
  if (raw.length > MAX_BYTES) fail("E_PLUGIN_SCHEMA", "/", "canonical plugin record exceeds byte limit");
  return raw;
}

export function digest(value: PyValue | Uint8Array): string {
  return createHash("sha256")
    .update(value instanceof Uint8Array ? value : canonicalBytes(value))
    .digest("hex");
}

function identifier(value: PyValue | undefined, path: string): void {
  if (!isStr(value) || !PLUGIN_ID.test(value) || MUTABLE_ALIASES.includes(pyLower(value))) {
    fail("E_PLUGIN_IDENTITY", path, "lowercase plugin id required");
  }
}

function exactVersion(value: PyValue | undefined, path: string): void {
  if (!isStr(value) || !VERSION_RE.test(value)) fail("E_PLUGIN_VERSION", path, "exact semantic version required");
}

function containsMutableAlias(value: string): boolean {
  const lowered = pyLower(value);
  return MUTABLE_ALIASES.some((alias) => new RegExp(`(?<![a-z0-9])${alias}(?![a-z0-9])`, "u").test(lowered));
}

function strings(value: PyValue | undefined, path: string): void {
  if (
    !isList(value) ||
    value.length > MAX_ARRAY_ITEMS ||
    value.some((item) => !isStr(item) || !item || pyLen(item) > 256 || UNSAFE_TEXT.test(item))
  ) {
    fail("E_PLUGIN_SCHEMA", path, "unique non-empty string array required");
  }
  if (new Set(value).size !== value.length) fail("E_PLUGIN_SCHEMA", path, "duplicate value");
}

/** ntpath.splitdrive(name)[0] 非空：name 里已经没有反斜杠、也不以 / 开头，只剩“第二个字符是冒号”这一种。 */
function hasDrive(name: string): boolean {
  return codePoints(name)[1] === ":";
}

export function resourceRef(value: PyValue | undefined, path: string): PyDict {
  const keys = ["kind", "id", "path", "sha256"];
  if (!isDict(value) || value.size !== keys.length || !keys.every((key) => value.has(key))) {
    fail("E_PLUGIN_RESOURCE", path, "closed ResourceRef required");
  }
  for (const key of ["kind", "id", "path"]) {
    const text = value.get(key);
    if (!isStr(text) || !text || UNSAFE_TEXT.test(text)) fail("E_PLUGIN_RESOURCE", `${path}/${key}`, "non-empty string required");
  }
  // 资源路径写进锁的字节：先做 Unicode 规范化再查穿越，规范等价的名字绕不过同一路径的规则
  const kind = pyNfc(value.get("kind") as string);
  const resourceId = pyNfc(value.get("id") as string);
  const name = pyNfc((value.get("path") as string).replaceAll("\\", "/"));
  if (
    name.startsWith("/") ||
    hasDrive(name) ||
    name.startsWith("./") ||
    name.split("/").some((part) => part === "" || part === "." || part === "..") ||
    /[\u0000-\u001f\u007f]/u.test(name)
  ) {
    fail("E_PLUGIN_PATH", `${path}/path`, "absolute and traversal paths are forbidden");
  }
  const sha = value.get("sha256");
  if (!isStr(sha) || !HEX64.test(sha)) fail("E_PLUGIN_RESOURCE", `${path}/sha256`, "lowercase SHA-256 required");
  return new Map<string, PyValue>([
    ["kind", kind],
    ["id", resourceId],
    ["path", name],
    ["sha256", sha],
  ]);
}

/** 跨平台保守的路径身份：Windows 与 macOS 常按大小写不敏感比较路径（macOS 还会做 Unicode 规范化）。只用来查冲突。 */
function resourcePathKey(ref: PyDict): string {
  return pyCasefold(pyNfc(ref.get("path") as string));
}

function rejectResourcePathCollisions(refs: readonly PyDict[], path: string): void {
  const seen = new Map<string, number>();
  refs.forEach((ref, index) => {
    const key = resourcePathKey(ref);
    const previous = seen.get(key);
    if (previous !== undefined) fail("E_PLUGIN_RESOURCE", `${path}/${index}/path`, `resource path aliases entry ${previous}`);
    seen.set(key, index);
  });
}

const identityOf = (ref: PyDict): string => JSON.stringify([ref.get("kind"), ref.get("id")]);

function cmpIdentity(left: PyDict, right: PyDict): number {
  return cmpCodePoints(left.get("kind") as string, right.get("kind") as string) || cmpCodePoints(left.get("id") as string, right.get("id") as string);
}

const MANIFEST_FIELDS = [
  "record_type",
  "schema_version",
  "plugin_id",
  "version",
  "api_version",
  "roles",
  "capabilities",
  "entrypoints",
  "resources",
  "depends_on",
  "conflicts",
  "checks",
  "platforms",
  "permissions",
];
const REQUIRED_FIELDS = ["record_type", "schema_version", "plugin_id", "version", "api_version", "roles", "capabilities", "resources", "checks"];
const CHECK_FIELDS = ["id", "command", "deterministic"];
const FORBIDDEN_TOKENS = ["importlib", "__import__", "eval(", "exec(", "http://", "https://"];

export function validateManifest(manifest: PyValue | undefined): PyDict {
  if (!isDict(manifest)) fail("E_PLUGIN_SCHEMA", "/", "manifest must be an object");
  const present = [...manifest.keys()] as string[];
  const unknown = present.filter((key) => !MANIFEST_FIELDS.includes(key));
  if (unknown.length) fail("E_PLUGIN_UNKNOWN_FIELD", "/", `unknown fields: ${reprList(unknown)}`);
  const missing = REQUIRED_FIELDS.filter((key) => !manifest.has(key));
  if (missing.length) fail("E_PLUGIN_SCHEMA", "/", `missing fields: ${reprList(missing)}`);
  for (const field of ["record_type", "plugin_id", "version", "api_version"]) {
    const value = manifest.get(field);
    if (!isStr(value) || !value) fail("E_PLUGIN_SCHEMA", `/${field}`, "non-empty string required");
  }
  if (manifest.get("record_type") !== "builtin-task-plugin-manifest" || manifest.get("schema_version") !== 1n) {
    fail("E_PLUGIN_VERSION", "/record_type", "manifest schema version 1 required");
  }
  identifier(manifest.get("plugin_id"), "/plugin_id");
  exactVersion(manifest.get("version"), "/version");
  if (containsMutableAlias(manifest.get("api_version") as string)) fail("E_PLUGIN_VERSION", "/version", "mutable aliases are forbidden");
  for (const field of ["roles", "capabilities", "depends_on", "conflicts", "platforms", "permissions"]) {
    if (manifest.has(field)) strings(manifest.get(field), `/${field}`);
  }
  for (const field of ["depends_on", "conflicts"]) {
    (getOr(manifest, field, []) as PyValue[]).forEach((name, index) => identifier(name, `/${field}/${index}`));
  }
  const resources = getOr(manifest, "resources", []);
  if (!isList(resources) || resources.length > MAX_ARRAY_ITEMS) fail("E_PLUGIN_SCHEMA", "/resources", "resource array required");
  const refs = resources.map((value, index) => resourceRef(value, `/resources/${index}`));
  if (new Set(refs.map(identityOf)).size !== refs.length) fail("E_PLUGIN_RESOURCE", "/resources", "duplicate resource identity");
  rejectResourcePathCollisions(refs, "/resources");
  strings(getOr(manifest, "entrypoints", []), "/entrypoints");
  const checks = getOr(manifest, "checks", []);
  if (!isList(checks) || checks.some((check) => !isDict(check))) fail("E_PLUGIN_SCHEMA", "/checks", "check descriptor array required");
  (checks as PyDict[]).forEach((check, index) => {
    if (!closedCheck(check)) fail("E_PLUGIN_CHECK", `/checks/${index}`, "closed id/command/deterministic check required");
    const flat = (check.get("command") as string[]).join(" ");
    const lowered = pyLower(flat);
    if (FORBIDDEN_TOKENS.some((token) => lowered.includes(token)) || containsMutableAlias(flat)) {
      fail("E_PLUGIN_CHECK", `/checks/${index}/command`, "dynamic import, network and mutable alias are forbidden");
    }
  });
  if (new Set((checks as PyDict[]).map((check) => check.get("id"))).size !== checks.length) {
    fail("E_PLUGIN_CHECK", "/checks", "duplicate check id");
  }
  const roles = manifest.get("roles") as PyValue[];
  if (!roles.length && (!checks.length || (checks as PyDict[]).some((check) => !check.get("deterministic")))) {
    fail("E_PLUGIN_CHECK", "/checks", "role-free plugins require explicit deterministic checks");
  }
  // ResourceRef 的路径是身份字节的一部分：返回与算摘要的都是 resourceRef 规整过的写法，锁绑定的与使用方用的是同一种
  const normalized = deepCopy(manifest) as PyDict;
  normalized.set("resources", refs);
  canonicalBytes(normalized);
  return normalized;
}

function closedCheck(check: PyDict): boolean {
  if (check.size !== CHECK_FIELDS.length || !CHECK_FIELDS.every((key) => check.has(key))) return false;
  const id = check.get("id");
  if (!isStr(id) || !id || pyLen(id) > 256 || UNSAFE_TEXT.test(id)) return false;
  const command = check.get("command");
  if (!isList(command) || !command.length || command.length > MAX_ARRAY_ITEMS) return false;
  if (command.some((arg) => !isStr(arg) || !arg || pyLen(arg) > 4096 || UNSAFE_TEXT.test(arg))) return false;
  return typeof check.get("deterministic") === "boolean";
}

/** 按依赖排好序的已启用插件（依赖在前）；冲突、缺依赖、环与跨插件的资源路径冲突都拒绝。 */
export function resolvePlugins(manifests: PyValue | undefined, enabled: PyValue | undefined): PyDict[] {
  if (!isDict(manifests)) fail("E_PLUGIN_SCHEMA", "/plugins", "manifest registry required");
  strings(enabled, "/enabled");
  const normalized = new Map<string, PyDict>();
  for (const [name, value] of manifests) normalized.set(name as string, validateManifest(value));
  for (const [name, value] of normalized) {
    if (value.get("plugin_id") !== name) fail("E_PLUGIN_IDENTITY", `/plugins/${name}/plugin_id`, "registry key must match plugin_id");
  }
  const names = enabled as string[];
  for (const name of names) {
    if (!normalized.has(name)) fail("E_PLUGIN_DEPENDENCY", `/enabled/${name}`, "plugin is not registered");
  }
  const result: PyDict[] = [];
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const visit = (name: string): void => {
    if (visiting.has(name)) fail("E_PLUGIN_CYCLE", "/depends_on", `dependency cycle includes ${name}`);
    if (visited.has(name)) return;
    visiting.add(name);
    const manifest = normalized.get(name) as PyDict;
    for (const dependency of sortedStrings(getOr(manifest, "depends_on", []) as string[])) {
      if (!normalized.has(dependency)) fail("E_PLUGIN_DEPENDENCY", `/plugins/${name}/depends_on`, `missing dependency ${dependency}`);
      visit(dependency);
    }
    visiting.delete(name);
    visited.add(name);
    result.push(manifest);
  };
  for (const name of sortedStrings(names)) visit(name);
  const ids = new Set(result.map((manifest) => manifest.get("plugin_id") as string));
  for (const manifest of result) {
    const conflict = (getOr(manifest, "conflicts", []) as string[]).filter((name) => ids.has(name));
    if (conflict.length) {
      fail("E_PLUGIN_CONFLICT", `/plugins/${manifest.get("plugin_id") as string}/conflicts`, `enabled conflict ${reprList(new Set(conflict))}`);
    }
  }
  // 解析出的插件共用一个命名空间：大小写或 Unicode 等价的两个路径会让使用次序决定结果，一律拒绝
  const paths = new Map<string, [string, number]>();
  for (const manifest of result) {
    const pluginId = manifest.get("plugin_id") as string;
    (getOr(manifest, "resources", []) as PyDict[]).forEach((ref, index) => {
      const key = resourcePathKey(ref);
      const other = paths.get(key);
      if (other !== undefined) {
        fail("E_PLUGIN_RESOURCE", `/plugins/${pluginId}/resources/${index}/path`, `resource path collides with ${other[0]}/resources/${other[1]}`);
      }
      paths.set(key, [pluginId, index]);
    });
  }
  return result;
}

const LOCK_FIELDS = ["record_type", "schema_version", "generation", "compiler_sha256", "plugins", "lock_sha256"];
const ROW_FIELDS = ["plugin_id", "version", "manifest_sha256", "resources"];

function closedDict(value: PyValue | undefined, keys: readonly string[]): value is PyDict {
  return isDict(value) && value.size === keys.length && keys.every((key) => value.has(key));
}

export function validateLock(lock: PyValue | undefined, manifests?: PyValue): PyDict {
  if (!closedDict(lock, LOCK_FIELDS)) fail("E_PLUGIN_LOCK", "/", "closed plugin lock required");
  const generation = lock.get("generation");
  if (
    lock.get("record_type") !== "plugin-lock" ||
    lock.get("schema_version") !== 1n ||
    typeof generation !== "bigint" ||
    generation < 1n
  ) {
    fail("E_PLUGIN_LOCK", "/", "invalid lock header");
  }
  for (const field of ["compiler_sha256", "lock_sha256"]) {
    const value = lock.get(field);
    if (!isStr(value) || !HEX64.test(value)) fail("E_PLUGIN_LOCK", `/${field}`, "lowercase SHA-256 required");
  }
  const plugins = lock.get("plugins");
  if (!isList(plugins)) fail("E_PLUGIN_LOCK", "/plugins", "plugin array required");
  const seen = new Set<string>();
  const order: string[] = [];
  const rows: PyDict[] = [];
  const resourcePaths = new Map<string, [string, number]>();
  plugins.forEach((row, index) => {
    const path = `/plugins/${index}`;
    if (!closedDict(row, ROW_FIELDS)) fail("E_PLUGIN_LOCK", path, "closed plugin lock row required");
    identifier(row.get("plugin_id"), `${path}/plugin_id`);
    const pluginId = row.get("plugin_id") as string;
    if (seen.has(pluginId)) fail("E_PLUGIN_LOCK", path, "duplicate plugin id");
    seen.add(pluginId);
    order.push(pluginId);
    const version = row.get("version");
    if (!isStr(version) || !VERSION_RE.test(version)) fail("E_PLUGIN_LOCK", `${path}/version`, "exact semantic version required");
    const manifestSha = row.get("manifest_sha256");
    if (!isStr(manifestSha) || !HEX64.test(manifestSha)) fail("E_PLUGIN_LOCK", `${path}/manifest_sha256`, "lowercase SHA-256 required");
    const resources = row.get("resources");
    if (!isList(resources)) fail("E_PLUGIN_LOCK", `${path}/resources`, "resource array required");
    const refs = resources.map((value, position) => resourceRef(value, `${path}/resources/${position}`));
    if (new Set(refs.map(identityOf)).size !== refs.length) fail("E_PLUGIN_LOCK", `${path}/resources`, "duplicate resource identity");
    rejectResourcePathCollisions(refs, `${path}/resources`);
    refs.forEach((ref, position) => {
      const key = resourcePathKey(ref);
      const other = resourcePaths.get(key);
      if (other !== undefined) {
        fail("E_PLUGIN_RESOURCE", `${path}/resources/${position}/path`, `resource path collides with ${other[0]}/resources/${other[1]}`);
      }
      resourcePaths.set(key, [pluginId, position]);
    });
    const canonical = [...refs].sort(cmpIdentity);
    if (refs.some((ref, position) => cmpIdentity(ref, canonical[position] as PyDict) !== 0)) {
      fail("E_PLUGIN_LOCK", `${path}/resources`, "resources must be in canonical order");
    }
    rows.push(
      new Map<string, PyValue>([
        ["plugin_id", pluginId],
        ["version", version],
        ["manifest_sha256", manifestSha],
        ["resources", refs],
      ]),
    );
  });
  const sortedOrder = sortedStrings(order);
  if (order.some((name, index) => name !== sortedOrder[index])) fail("E_PLUGIN_LOCK", "/plugins", "plugins must be in canonical order");
  const expected = new Map<string, PyValue>([
    ["record_type", lock.get("record_type") as PyValue],
    ["schema_version", lock.get("schema_version") as PyValue],
    ["generation", generation],
    ["compiler_sha256", lock.get("compiler_sha256") as PyValue],
    ["plugins", rows],
  ]);
  if (lock.get("lock_sha256") !== digest(expected)) fail("E_PLUGIN_LOCK_DRIFT", "/lock_sha256", "lock bytes do not match");
  if (manifests !== undefined) bindLock(rows, plugins as PyDict[], manifests);
  const result = deepCopy(lock) as PyDict;
  result.set("plugins", rows);
  return result;
}

function bindLock(rows: readonly PyDict[], plugins: readonly PyDict[], manifests: PyValue): void {
  if (!isDict(manifests)) fail("E_PLUGIN_LOCK_BINDING", "/plugins", "manifest registry required");
  const normalized = new Map<string, PyDict>();
  for (const [name, value] of manifests) normalized.set(name as string, validateManifest(value));
  resolvePlugins(normalized as PyDict, [...normalized.keys()]);
  const locked = new Set(plugins.map((row) => row.get("plugin_id") as string));
  if (locked.size !== normalized.size || [...locked].some((name) => !normalized.has(name))) {
    fail("E_PLUGIN_LOCK_BINDING", "/plugins", "lock plugin set does not match manifests");
  }
  for (const row of rows) {
    const pluginId = row.get("plugin_id") as string;
    const manifest = normalized.get(pluginId) as PyDict;
    const resources = [...(getOr(manifest, "resources", []) as PyDict[])].sort(cmpIdentity);
    if (row.get("version") !== manifest.get("version") || row.get("manifest_sha256") !== digest(manifest) || !pyEq(row.get("resources") as PyValue, resources)) {
      fail("E_PLUGIN_LOCK_BINDING", `/plugins/${pluginId}`, "lock is not bound to manifest bytes");
    }
  }
}

/** 一个插件的离线权限结论：manifest 只能声明要什么权限、支持哪些平台，给不了；缺一样就 BLOCKED。 */
export function checkPermissionIntersection(manifest: PyValue, allowedPermissions: PyValue, platformName: PyValue = null): PyDict {
  const normalized = validateManifest(manifest);
  if (!isList(allowedPermissions)) fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list required");
  if (allowedPermissions.some((value) => !isStr(value) || !value)) {
    fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list must contain non-empty strings");
  }
  if (new Set(allowedPermissions).size !== allowedPermissions.length) fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list must be unique");
  if (platformName !== null && (!isStr(platformName) || !platformName)) fail("E_PLUGIN_POLICY", "/platform_name", "platform name must be non-empty text");
  const allowed = new Set(allowedPermissions as string[]);
  const required = sortedStrings(new Set(getOr(normalized, "permissions", []) as string[]));
  const missing = required.filter((permission) => !allowed.has(permission));
  const supported = getOr(normalized, "platforms", []) as string[];
  const platformBlocked = platformName !== null && supported.length > 0 && !supported.includes(platformName as string);
  return new Map<string, PyValue>([
    ["plugin_id", normalized.get("plugin_id") as PyValue],
    ["required_permissions", required],
    ["missing_permissions", missing],
    ["platform", platformName],
    ["platform_blocked", platformBlocked],
    ["status", !missing.length && !platformBlocked ? "READY" : "BLOCKED"],
    ["dispatch_eligibility", "not_evaluated"],
  ]);
}

function deepCopy(value: PyValue): PyValue {
  if (isList(value)) return value.map(deepCopy);
  if (isDict(value)) return new Map([...value].map(([key, item]) => [key, deepCopy(item)]));
  return value;
}
