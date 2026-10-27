// pi_dispatch 读配置的入口与几张路径表（迁移第 ④b1 片）：Repo.config（有疑似凭据就整份不用）、extra_protected_paths、
// planner_paths、kernel_protected_paths。配置中心（kit_config）读的是同一份文件，报错文字不同，见 @themis/config/validate。
import { statSync } from "node:fs";
import path from "node:path";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { normCase, pyResolve } from "@themis/base/pypath";
import { secretLikePaths } from "@themis/base/secrets";
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
