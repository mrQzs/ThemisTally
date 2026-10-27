// kit_config.py 的整份校验（迁移第 ③a2 片）：键的登记表 KEYS、各键的校验（含它们复用的 pi_dispatch 校验函数）、
// plugins 的修复提示、读配置文件。报错句子会进 validate、show 的输出与桌面端的预览，逐字照 Python；检查的先后次序也照 Python。
import { closeSync, openSync, readdirSync, statSync, unlinkSync, writeSync } from "node:fs";
import { randomBytes } from "node:crypto";
import path from "node:path";
import { PyCrash, pyReprValue } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { abspath, isLinkOrJunction, isWithin, pyResolve } from "@themis/base/pypath";
import { D, NOT_S, PY_END, cmpCodePoints, codePoints, pyRegex, pyStrip } from "@themis/base/pyre";
import { ENV_NAME_RE, SECRET_KEY_SHOWN, secretLikePaths } from "@themis/base/secrets";
import { DispatchError, EXIT_FAIL, EXIT_USAGE } from "@themis/dispatcher/repo";
import { patternError } from "@themis/dispatcher/patterns";
import { extraProtectedPaths, plannerPaths } from "@themis/dispatcher/kernel-config";
import { DecisionError, PLUGIN_ID as DECISIONS_PLUGIN_ID, batteryLinkProblem, joinPath, settingsActive, settingsFromConfig, verifyBatteryLock } from "./decisions.ts";
import { PLUGIN_ID } from "./plugin-records.ts";
import { MODEL_TOKEN_RE, THINKING_LEVELS, checkKey } from "./roles-check.ts";
import { secretConfigError } from "./secret-config.ts";

export const CONFIG_NAME = "dispatch.config.json";

/** kit_config.ConfigError：带退出码，入口写一行 `ERROR: …`。 */
export class ConfigError extends Error {
  override readonly name = "ConfigError";
  readonly code: number;
  constructor(message: string, code: number = EXIT_FAIL) {
    super(message);
    this.code = code;
  }
}

/** 这次运行的 kit：启动器经 pyargs 的 context 传来的 kit_root（pd.KIT_ROOT），决策插件在它之下。 */
export interface Kit {
  readonly kitRoot: string;
  readonly decisionsDir: string;
}

export function kitAt(kitRoot: string): Kit {
  return { kitRoot, decisionsDir: joinPath(kitRoot, "plugins", "decisions") };
}

/** 校验要用到的仓库：根目录（pd.Repo.root）与 .agent 目录。 */
export interface RepoLike {
  readonly root: string;
  readonly agentDir: string;
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const getOr = (dict: PyDict, key: string, fallback: PyValue): PyValue => (dict.has(key) ? (dict.get(key) as PyValue) : fallback);
const isNumber = (value: PyValue | undefined): value is bigint | number => typeof value === "bigint" || typeof value === "number";
const json = (value: PyValue): string => dumps(value, { ensureAscii: false });

/** float(value)：超出 double 范围的 int 照 Python 抛 OverflowError（没接住，打堆栈）。 */
function toFloat(value: bigint | number): number {
  if (typeof value === "number") return value;
  const result = Number(value);
  if (!Number.isFinite(result)) throw new PyCrash("OverflowError", "int too large to convert to float");
  return result;
}

/** list(value)：str 拆成字符、dict 取键、其余不可迭代的照 Python 抛 TypeError。 */
function pyList(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return [...value];
  if (typeof value === "string") return codePoints(value);
  if (isDict(value)) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", "object is not iterable");
}

// --- pi_dispatch 的几个校验函数 ------------------------------------------------------------------

export { patternError };

const TRAILER_RE = pyRegex(`^[A-Za-z][A-Za-z0-9-]*: ${NOT_S}[^\\n]*${PY_END}`);

/** pi_dispatch.valid_trailer：单行 `Key: value`，不含控制字符。 */
function validTrailer(value: PyValue): boolean {
  return typeof value === "string" && TRAILER_RE.test(value) && !/[\u0000-\u001f\u007f]/u.test(value);
}

export function commitTrailers(config: PyDict): string[] {
  const values = getOr(config, "commit_trailers", []);
  if (!Array.isArray(values) || !values.every(validTrailer)) {
    throw new DispatchError("dispatch.config.json 的 commit_trailers 必须是单行 `Key: value` 字符串数组，不能含回车、换行等控制字符", EXIT_USAGE);
  }
  return [...(values as string[])];
}

const PRICE_FIELDS = ["input", "output", "cache_read", "cache_write"];
const PRICE_DATE_RE = pyRegex(`^${D}{4}-${D}{2}-${D}{2}${PY_END}`);
const CURRENCY_RE = pyRegex(`^[A-Z]{3}${PY_END}`);

/** pi_dispatch.pricing_table：按 <provider>/<model> 给执行模型的单价。 */
export function pricingTable(config: PyDict): PyDict {
  const table = getOr(config, "pricing", new Map());
  const bad = (message: string): never => {
    throw new DispatchError(`dispatch.config.json 的 pricing 无效：${message}`, EXIT_USAGE);
  };
  if (!isDict(table)) bad("必须是对象，键为 <provider>/<model>");
  const out: PyDict = new Map();
  for (const [rawKey, entry] of table as PyDict) {
    const key = rawKey as string;
    const slash = key.indexOf("/");
    const parts = slash < 0 ? [key] : [key.slice(0, slash), key.slice(slash + 1)];
    if (parts.length !== 2 || !parts.every((part) => MODEL_TOKEN_RE.test(part))) bad(`键 ${pyReprValue(key)} 必须是 <provider>/<model>`);
    if (!isDict(entry)) bad(`${key} 必须是对象`);
    const fields = entry as PyDict;
    const unknown = [...fields.keys()].map(String).filter((field) => ![...PRICE_FIELDS, "currency", "per_tokens", "source", "as_of"].includes(field)).sort(cmpCodePoints);
    if (unknown.length) bad(`${key} 有未知字段 ${unknown.join(", ")}`);
    for (const field of PRICE_FIELDS) {
      const value = fields.get(field) ?? null;
      if (value === null && (field === "input" || field === "output")) bad(`${key} 缺少 ${field} 单价`);
      if (value !== null && (!isNumber(value) || !Number.isFinite(toFloat(value)) || value < 0)) bad(`${key}.${field} 必须是非负数`);
    }
    const perTokens = getOr(fields, "per_tokens", 1000000n);
    if (typeof perTokens !== "bigint" || perTokens <= 0n) bad(`${key}.per_tokens 必须是正整数（缺省 1000000）`);
    const currency = getOr(fields, "currency", "USD");
    if (typeof currency !== "string" || !CURRENCY_RE.test(currency)) bad(`${key}.currency 必须是三个大写字母（例如 USD）`);
    const source = fields.get("source");
    if (typeof source !== "string" || !pyStrip(source)) bad(`${key}.source 必须写明价格来源（例如价格页与访问日期）`);
    const asOf = fields.get("as_of");
    if (typeof asOf !== "string" || !PRICE_DATE_RE.test(asOf)) bad(`${key}.as_of 必须是 YYYY-MM-DD`);
    const merged = new Map(fields);
    merged.set("per_tokens", perTokens);
    merged.set("currency", currency);
    out.set(key, merged);
  }
  return out;
}

const RELEASE_PATTERN_NAMES = ["api key", "home path", "private address"];

/** pi_dispatch._release_allow_rules：允许规则 `<glob>:<模式名>`。 */
export function releaseAllowRules(config: PyDict, extra: readonly string[]): [string, string][] {
  const section = config.get("release_check");
  let configured: PyValue = [];
  if (isDict(section)) {
    configured = section.size ? getOr(section, "allow", []) : [];
  }
  const rules: [string, string][] = [];
  for (const rule of [...pyList(configured), ...extra]) {
    if (typeof rule !== "string" || !rule.includes(":")) {
      throw new DispatchError(`release-check 的允许规则要写成 <glob>:<模式名>，例如 tests/fixtures/**:home path：${pyReprValue(rule)}`, EXIT_USAGE);
    }
    const colon = rule.lastIndexOf(":");
    const label = pyStrip(rule.slice(colon + 1));
    if (label !== "*" && !RELEASE_PATTERN_NAMES.includes(label)) {
      throw new DispatchError(`release-check 没有名为 ${pyReprValue(label)} 的模式（可用：${RELEASE_PATTERN_NAMES.join("、")} 或 *）`, EXIT_USAGE);
    }
    rules.push([pyStrip(rule.slice(0, colon)), label]);
  }
  return rules;
}

/** ntpath.expanduser：~ 与 ~user 换成用户目录；拿不到用户目录时原样。 */
export function expanduser(value: string): string {
  if (!value.startsWith("~")) return value;
  if (process.platform !== "win32") {
    const home = process.env["HOME"];
    return home && (value === "~" || value.startsWith("~/")) ? home.replace(/\/+$/u, "") + value.slice(1) || "/" : value;
  }
  let end = 1;
  while (end < value.length && value[end] !== "\\" && value[end] !== "/") end += 1;
  let home: string;
  if (process.env["USERPROFILE"] !== undefined) home = process.env["USERPROFILE"];
  else if (process.env["HOMEPATH"] === undefined) return value;
  else home = path.win32.join(process.env["HOMEDRIVE"] ?? "", process.env["HOMEPATH"]);
  if (end !== 1) {
    const target = value.slice(1, end);
    const current = process.env["USERNAME"];
    if (target !== current) {
      if (current !== path.win32.basename(home)) return value;
      home = path.win32.join(path.win32.dirname(home), target);
    }
  }
  return home + value.slice(end);
}

/** tempfile.gettempdir：TMPDIR、TEMP、TMP 与平台的几个缺省目录里第一个写得进去的（abspath 过）。 */
export function gettempdir(): string {
  const candidates: string[] = [];
  for (const name of ["TMPDIR", "TEMP", "TMP"]) {
    const value = process.env[name];
    if (value) candidates.push(value);
  }
  if (process.platform === "win32") {
    candidates.push(expanduser("~\\AppData\\Local\\Temp"), `${process.env["SYSTEMROOT"] ?? "%SYSTEMROOT%"}\\Temp`, "c:\\temp", "c:\\tmp", "\\temp", "\\tmp");
  } else {
    candidates.push("/tmp", "/var/tmp", "/usr/tmp");
  }
  candidates.push(process.cwd());
  for (const candidate of candidates) {
    const dir = candidate === "." ? candidate : abspath(candidate);
    if (writable(dir)) return dir;
  }
  throw new PyCrash("FileNotFoundError", "No usable temporary directory found");
}

function writable(dir: string): boolean {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const file = path.join(dir, `tmp${randomBytes(4).toString("hex")}`);
    try {
      const fd = openSync(file, "wx", 0o600);
      try {
        writeSync(fd, "blat");
      } finally {
        closeSync(fd);
        unlinkSync(file);
      }
      return true;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "EEXIST") continue;
      if ((code === "EPERM" || code === "EACCES") && process.platform === "win32" && isDirectory(dir)) continue;
      return false;
    }
  }
  return false;
}

function isDirectory(value: string): boolean {
  try {
    return statSync(value).isDirectory();
  } catch {
    return false;
  }
}

/** pi_dispatch.Repo.worktree_root：配置的 worktree_root 或 PI_DISPATCH_WORKTREE_ROOT，缺省是系统临时目录下的 pi-worktrees。 */
export function worktreeRoot(config: PyDict, repo: RepoLike): string {
  const configured = config.get("worktree_root");
  const chosen = typeof configured === "string" && configured ? configured : (process.env["PI_DISPATCH_WORKTREE_ROOT"] ?? "");
  const root = pyResolve(chosen ? expanduser(chosen) : path.join(gettempdir(), "pi-worktrees"));
  if (isWithin(root, repo.root)) throw new DispatchError(`worktree_root 不能位于仓库内部：${root}`, EXIT_USAGE);
  return root;
}

// --- kit_config 的各键校验 -------------------------------------------------------------------------

type Check = (config: PyDict, repo: RepoLike | null, kit: Kit) => void;

function checkAllowedExecutors(config: PyDict): void {
  const value = config.get("allowed_executors") ?? null;
  if (value === null) return;
  if (!Array.isArray(value)) throw new ConfigError("allowed_executors 必须是数组");
  value.forEach((item, index) => {
    if (!isDict(item) || typeof item.get("provider") !== "string" || typeof item.get("model") !== "string") {
      throw new ConfigError(`allowed_executors[${index}] 必须是 {provider, model[, thinking]}`);
    }
    for (const field of ["provider", "model"]) {
      const text = item.get(field) as string;
      if (!MODEL_TOKEN_RE.test(text)) throw new ConfigError(`allowed_executors[${index}].${field} 不是合法的标识：${pyReprValue(text)}`);
    }
    const thinking = item.get("thinking") ?? null;
    if (thinking !== null && !(typeof thinking === "string" && THINKING_LEVELS.includes(thinking))) {
      throw new ConfigError(`allowed_executors[${index}].thinking 必须是 ${THINKING_LEVELS.join("/")} 之一`);
    }
    const unknown = [...item.keys()].map(String).filter((key) => !["provider", "model", "thinking"].includes(key)).sort(cmpCodePoints);
    if (unknown.length) throw new ConfigError(`allowed_executors[${index}] 有未知键：${unknown.join(", ")}`);
  });
}

function checkWorktreeRoot(config: PyDict, repo: RepoLike | null): void {
  const value = config.get("worktree_root") ?? null;
  if (value !== null && typeof value !== "string") throw new ConfigError("worktree_root 必须是路径字符串或 null");
  if (repo === null) return;
  try {
    worktreeRoot(config, repo);
  } catch (error) {
    if (error instanceof DispatchError) throw new ConfigError(error.message);
    throw error;
  }
}

function checkKillGrace(config: PyDict): void {
  const value = getOr(config, "kill_grace_seconds", 15n);
  if (!isNumber(value) || !(0 < toFloat(value) && toFloat(value) <= 600)) throw new ConfigError("kill_grace_seconds 必须是 0 到 600 之间的秒数");
}

function checkPatterns(key: string): Check {
  return (config) => {
    const value = getOr(config, key, []);
    if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item)) throw new ConfigError(`${key} 必须是仓库相对 glob 的数组`);
    for (const item of value as string[]) {
      const problem = patternError(item);
      if (problem) throw new ConfigError(`${key} 的 ${pyReprValue(item)}：${problem}`);
    }
  };
}

function checkVia(fn: (config: PyDict) => unknown): Check {
  return (config) => {
    try {
      fn(config);
    } catch (error) {
      if (error instanceof DispatchError) throw new ConfigError(error.message);
      throw error;
    }
  };
}

function checkEnvNames(key: string): Check {
  return (config) => {
    const value = getOr(config, key, []);
    if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !ENV_NAME_RE.test(item))) throw new ConfigError(`${key} 必须是环境变量名的数组`);
  };
}

function checkRelease(config: PyDict): void {
  const value = config.get("release_check") ?? null;
  if (value === null) return;
  if (!isDict(value) || [...value.keys()].some((key) => key !== "allow" && key !== "denylist")) {
    throw new ConfigError("release_check 只能有 allow（规则数组）与 denylist（路径）两个键");
  }
  if (value.has("denylist") && typeof value.get("denylist") !== "string") throw new ConfigError("release_check.denylist 必须是路径字符串");
  try {
    releaseAllowRules(config, []);
  } catch (error) {
    if (error instanceof DispatchError) throw new ConfigError(error.message);
    throw error;
  }
}

function checkDecisions(config: PyDict, repo: RepoLike | null, kit: Kit): void {
  let settings;
  try {
    settings = settingsFromConfig(config, repo === null ? null : repo.agentDir, kit.decisionsDir);
  } catch (error) {
    if (error instanceof DecisionError) throw new ConfigError(`decisions 无效：${error.detail}`);
    throw error;
  }
  if (!settingsActive(settings)) return;
  // 生效时问题清单必须与插件内容锁一致；读之前先查链接，不跟随它去读
  const link = batteryLinkProblem(kit.kitRoot, kit.decisionsDir);
  if (link !== null) throw new ConfigError(`decisions 的问题清单经过链接（无效：链接 ${link}），没有读取`);
  try {
    verifyBatteryLock(kit.decisionsDir);
  } catch (error) {
    if (error instanceof DecisionError) throw new ConfigError(`decisions 的问题清单与插件内容锁不符：${error.detail}`);
    throw error;
  }
}

const PLUGINS_SUBKEYS = ["enabled", "allowed_permissions"];

function checkPlugins(config: PyDict): void {
  if (!config.has("plugins")) return;
  const value = config.get("plugins") as PyValue;
  if (!isDict(value)) throw new ConfigError(`plugins 必须是对象（子键 enabled、allowed_permissions），现在是 ${json(value)}`);
  const unknown = [...value.keys()]
    .filter((key) => !(typeof key === "string" && (PLUGINS_SUBKEYS.includes(key) || key.startsWith("_"))))
    .map(String)
    .sort(cmpCodePoints);
  if (unknown.length) throw new ConfigError(`plugins 有未知子键：${unknown.join(", ")}（只允许 enabled、allowed_permissions 与下划线开头的说明）`);
  for (const key of PLUGINS_SUBKEYS) {
    if (value.has(key) && !Array.isArray(value.get(key))) throw new ConfigError(`plugins.${key} 必须是列表，现在是 ${json(value.get(key) as PyValue)}；不写这个子键表示不限制`);
  }
  (getOr(value, "enabled", []) as PyValue[]).forEach((item, index) => {
    if (typeof item !== "string" || !PLUGIN_ID.test(item)) throw new ConfigError(`plugins.enabled[${index}] 不是合法的插件 ID：${json(item)}`);
  });
  (getOr(value, "allowed_permissions", []) as PyValue[]).forEach((item, index) => {
    if (typeof item !== "string" || !item) throw new ConfigError(`plugins.allowed_permissions[${index}] 必须是非空字符串：${json(item)}`);
  });
  for (const key of PLUGINS_SUBKEYS) {
    const items = getOr(value, key, []) as string[];
    const duplicates = [...new Set(items.filter((item) => items.indexOf(item) !== items.lastIndexOf(item)))].sort(cmpCodePoints);
    if (duplicates.length) throw new ConfigError(`plugins.${key} 有重复项：${duplicates.join(", ")}`);
  }
}

/** kit_config.plugins_section_error：plugins 段的格式错误（与 validate 报的同一句，不带修复提示）；合法或缺省时为 null。 */
export function pluginsSectionError(config: PyDict): string | null {
  const secret = secretConfigError(config, "plugins");
  if (secret !== null) return secret;
  try {
    checkPlugins(config);
  } catch (error) {
    if (error instanceof ConfigError) return error.message;
    throw error;
  }
  return null;
}

function checkV3(key: string): Check {
  return (config) => {
    if (!config.has(key)) return;
    const errors = checkKey(config, key);
    if (errors.length) throw new ConfigError(errors.join("；"));
  };
}

/** 键 → 校验函数；次序就是 show 的次序（说明与缺省值在 show 里）。 */
export const KEYS: ReadonlyMap<string, Check> = new Map<string, Check>([
  ["allowed_executors", checkAllowedExecutors],
  ["worktree_root", checkWorktreeRoot],
  ["kill_grace_seconds", checkKillGrace],
  ["check_artifact_patterns", checkPatterns("check_artifact_patterns")],
  ["extra_protected_paths", checkVia(extraProtectedPaths)],
  ["planner_paths", checkVia(plannerPaths)],
  ["commit_trailers", checkVia(commitTrailers)],
  ["env_remove", checkEnvNames("env_remove")],
  ["env_keep", checkEnvNames("env_keep")],
  ["release_check", checkRelease],
  ["pricing", checkVia(pricingTable)],
  ["decisions", checkDecisions],
  ["plugins", checkPlugins],
  ["runtimes", checkV3("runtimes")],
  ["profiles", checkV3("profiles")],
  ["roles", checkV3("roles")],
  ["presets", checkV3("presets")],
  ["active_preset", checkV3("active_preset")],
]);

/** kit_config.validate_config：整份校验，返回错误列表（空表示有效）。hints 为真时 plugins 的错误后面附修复命令。 */
export function validateConfig(config: PyDict, repo: RepoLike | null, kit: Kit, hints = true): string[] {
  const errors: string[] = [];
  const add = (message: string): void => {
    if (!errors.includes(message)) errors.push(message);
  };
  for (const key of config.keys()) {
    if (typeof key !== "string") {
      errors.push("键必须是字符串");
    } else if (key.startsWith("_")) {
      // 说明键只免形状检查，不免凭据检查
      const secret = secretConfigError(config, key);
      if (secret !== null) add(secret);
    } else if (!KEYS.has(key)) {
      const shown = secretLikePaths(new Map([[key, null]])).length ? SECRET_KEY_SHOWN : pyReprValue(key);
      errors.push(`未知键 ${shown}（已知：${[...KEYS.keys()].join(", ")}）`);
    }
  }
  for (const [key, check] of KEYS) {
    const secret = secretConfigError(config, key);
    if (secret !== null) {
      // 只报键路径，不跑这个键自己的检查：那些错误可能把取值带进输出
      add(secret);
      continue;
    }
    try {
      check(config, repo, kit);
    } catch (error) {
      if (!(error instanceof ConfigError)) throw error;
      let message = error.message;
      if (key === "plugins" && hints) {
        const hint = pluginsFixHint(config, repo, kit);
        if (hint) message += `；修复：${hint}`;
      }
      add(message);
    }
  }
  return errors;
}

/** KIT_ROOT/plugins/ 下的插件目录名（匹配插件 ID、不是链接），按名字排序；plugins/ 是目录却列不出来时为 null。 */
function installedPluginIds(kit: Kit): string[] | null {
  const root = joinPath(kit.kitRoot, "plugins");
  if (isLinkOrJunction(root) || !isDirectory(root)) return [];
  try {
    return readdirSync(root)
      .filter((name) => PLUGIN_ID.test(name) && isDirectory(joinPath(root, name)) && !isLinkOrJunction(joinPath(root, name)))
      .sort(cmpCodePoints);
  } catch {
    return null;
  }
}

/** json.dumps(ensure_ascii=True, 紧凑分隔符)，再把单引号写成 \u0027：整段放进单引号，bash 与 PowerShell 都能原样执行。 */
function shellJson(value: PyValue): string {
  return dumps(value, { ensureAscii: true, separators: [",", ":"] }).replaceAll("'", "\\u0027");
}

const deepCopy = (value: PyDict): PyDict => loads(dumps(value)) as PyDict;

/**
 * kit_config.plugins_fix_hint：plugins 有非列表的子键（或 plugins 本身不是对象）时，给出一条执行后能通过整份校验的命令；
 * 候选依次是删掉非法的子键、换成“已安装插件减去 decisions”的合法对象，每个先用 validateConfig(hints=false) 模拟。
 */
export function pluginsFixHint(config: PyDict, repo: RepoLike | null, kit: Kit): string | null {
  if (!config.has("plugins")) return null;
  const section = config.get("plugins") as PyValue;
  let bad: string[];
  if (isDict(section)) {
    bad = PLUGINS_SUBKEYS.filter((key) => section.has(key) && !Array.isArray(section.get(key)));
    if (!bad.length) return null;
  } else {
    bad = [...PLUGINS_SUBKEYS];
  }
  const candidates: [string, PyDict][] = [];
  const removed = deepCopy(config);
  if (isDict(section) && bad.length === 1) {
    const plugins = removed.get("plugins") as PyDict;
    plugins.delete(bad[0] as string);
    if (!plugins.size) removed.delete("plugins");
    candidates.push([`config unset plugins.${bad[0] as string}`, removed]);
  } else {
    removed.delete("plugins");
    candidates.push(["config unset plugins", removed]);
  }
  const replacement: PyDict = new Map();
  if (isDict(section)) {
    for (const [key, value] of section) {
      if ((key as string).startsWith("_") || (PLUGINS_SUBKEYS.includes(key as string) && Array.isArray(value))) replacement.set(key, value);
    }
  }
  // 已有合法的 enabled 列表：保持原样只去掉 decisions；缺省或非法（都等于不限制）：全部已安装插件减去 decisions
  const kept = replacement.get("enabled");
  const base = Array.isArray(kept) ? kept : installedPluginIds(kit);
  if (base !== null) {
    replacement.set("enabled", (base as PyValue[]).filter((name) => name !== DECISIONS_PLUGIN_ID));
    const replaced = deepCopy(config);
    replaced.set("plugins", replacement);
    candidates.push([`config set plugins '${shellJson(replacement)}'`, replaced]);
  }
  for (const [command, candidate] of candidates) {
    if (!validateConfig(candidate, repo, kit, false).length) return command;
  }
  return null;
}

// --- 读配置文件 --------------------------------------------------------------------------------------

export function configPath(repo: RepoLike): string {
  return joinPath(repo.agentDir, CONFIG_NAME);
}

/** kit_config.load_config：文件不存在为空对象；读不出、解析不了或顶层不是对象都是 ConfigError。 */
export function loadConfig(repo: RepoLike): PyDict {
  const file = configPath(repo);
  let raw: Buffer;
  try {
    statSync(file);
  } catch {
    return new Map();
  }
  try {
    raw = pyReadBytes(file);
  } catch (error) {
    if (error instanceof PyOSError) throw new ConfigError(`无法解析 ${file}：${error.message}`);
    throw error;
  }
  return parseObject(file, raw);
}

/** kit_config._parse_object：配置文件的字节 → 顶层对象。 */
export function parseObject(file: string, raw: Uint8Array): PyDict {
  let data: PyValue;
  try {
    data = loads(pyDecodeUtf8(raw));
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError) throw new ConfigError(`无法解析 ${file}：${error.message}`);
    if (error instanceof PyJsonError) throw new ConfigError(`无法解析 ${file}：${error.kind === "RecursionError" ? "RecursionError" : error.message}`);
    throw error;
  }
  if (!isDict(data)) throw new ConfigError(`${file} 顶层必须是对象`);
  return data;
}
