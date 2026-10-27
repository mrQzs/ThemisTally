// pi_dispatch 读配置的入口与几张路径表（迁移第 ④b1 片）：Repo.config（有疑似凭据就整份不用）、extra_protected_paths、
// planner_paths、kernel_protected_paths。配置中心（kit_config）读的是同一份文件，报错文字不同，见 @themis/config/validate。
import { statSync } from "node:fs";
import path from "node:path";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { PyCrash, pyReprValue } from "@themis/base/pyfmt";
import { normCase, pyResolve } from "@themis/base/pypath";
import { D, PY_END, cmpCodePoints, codePoints, pyRegex, pyStrip } from "@themis/base/pyre";
import { secretLikePaths } from "@themis/base/secrets";
import { MODEL_TOKEN_RE } from "./contract.ts";
import { KERNEL_TS_PROTECTED, patternError } from "./patterns.ts";
import { DispatchError, EXIT_USAGE, type Repo } from "./repo.ts";

export class ConfigSecretError extends DispatchError {}

export const CONFIG_FILE = "dispatch.config.json";
export const DEFAULT_PLANNER_PATHS = [".agent/plans/**", ".agent/reviews/**", ".agent/design/**", ".agent/publications/**", ".agent/*.md"];

/** Path.exists：stat 跟随链接，出错一律当不存在。 */
function exists(file: string): boolean {
  try {
    statSync(file);
    return true;
  } catch {
    return false;
  }
}

/** Repo.config_with_bytes：配置与读到的原始字节（文件不存在时为空对象与 null）。读不出文件、嵌套太深时 Python 不接，照样抛出。 */
export function configWithBytes(repo: Repo): [PyDict, Buffer | null] {
  const file = path.join(repo.agentDir, CONFIG_FILE);
  if (!exists(file)) return [new Map(), null];
  const raw = pyReadBytes(file);
  let data: PyValue;
  try {
    data = loads(pyDecodeUtf8(raw));
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError || (error instanceof PyJsonError && error.kind !== "RecursionError")) {
      throw new DispatchError(`无法解析 ${file}：${error.message}`, EXIT_USAGE);
    }
    throw error;
  }
  if (!(data instanceof Map)) throw new DispatchError(`${file} 顶层必须是对象`, EXIT_USAGE);
  const suspicious = secretLikePaths(data);
  if (suspicious.length) {
    throw new ConfigSecretError(
      `${file} 里有疑似凭据（${suspicious.slice(0, 5).join("、")}）：配置里只写环境变量名，凭据的值用 config secret set 存；` +
        "改好之前调度器不读这份配置（config show 列出位置）",
      EXIT_USAGE,
    );
  }
  return [data, raw];
}

export const repoConfig = (repo: Repo): PyDict => configWithBytes(repo)[0];

function patternList(config: PyDict, key: string, fallback: PyValue): string[] {
  const values = config.has(key) ? (config.get(key) as PyValue) : fallback;
  if (!Array.isArray(values) || !values.every((value) => typeof value === "string" && !patternError(value))) {
    throw new DispatchError(`dispatch.config.json 的 ${key} 必须是仓库相对路径模式的数组`, EXIT_USAGE);
  }
  return [...(values as string[])];
}

export const extraProtectedPaths = (config: PyDict): string[] => patternList(config, "extra_protected_paths", []);
export const plannerPaths = (config: PyDict): string[] => patternList(config, "planner_paths", [...DEFAULT_PLANNER_PATHS]);

/** same_dir：解析真实路径之后按平台的大小写规则比较。 */
export const sameDir = (a: string, b: string): boolean => normCase(pyResolve(a)) === normCase(pyResolve(b));

/**
 * kernel_protected_paths：被检查的仓库就是内核自己所在的仓库、选择文件至少有一项是 ts 时，加上内核 TS 的禁区。
 * kit 根与选择文件由启动器经 context 交来（Python 的 KERNEL_TS_ROOT.parent 与 read_kernel_impl()）。
 */
export function kernelProtectedPaths(root: string, kitRoot: string, kernelImpl: Readonly<Record<string, string>>): string[] {
  if (!sameDir(root, kitRoot)) return [];
  return Object.values(kernelImpl).includes("ts") ? [...KERNEL_TS_PROTECTED] : [];
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const getOr = (dict: PyDict, key: string, fallback: PyValue): PyValue => (dict.has(key) ? (dict.get(key) as PyValue) : fallback);
const isNumber = (value: PyValue | undefined): value is bigint | number => typeof value === "bigint" || typeof value === "number";

/** float(value)：超出 double 范围的 int 照 Python 抛 OverflowError（没接住，打堆栈）。 */
function toFloat(value: bigint | number): number {
  if (typeof value === "number") return value;
  const result = Number(value);
  if (!Number.isFinite(result)) throw new PyCrash("OverflowError", "int too large to convert to float");
  return result;
}

/** list(value)：字符串拆成字符，字典取键，其余不可迭代的照 Python 抛 TypeError。 */
function pyList(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return [...value];
  if (typeof value === "string") return codePoints(value);
  if (isDict(value)) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", "object is not iterable");
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
