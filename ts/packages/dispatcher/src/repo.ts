// pi_dispatch 的仓库发现与 JSON 读取（迁移第 ② 步）：Repo.discover、git、git_env、read_json_or。
import { spawnSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { type PyValue, PyJsonError, loads } from "@themis/base/pyjson";
import { normCase, pyResolve } from "@themis/base/pypath";

export const EXIT_OK = 0;
export const EXIT_FAIL = 1;
export const EXIT_USAGE = 2;
export const EXIT_BLOCKED = 3;

/** pi_dispatch.DispatchError：带退出码的可预期错误，入口写一行 `ERROR: …`。 */
export class DispatchError extends Error {
  readonly code: number;

  constructor(message: string, code: number = EXIT_BLOCKED) {
    super(message);
    this.code = code;
  }
}

/** pi_dispatch.GIT_REDIRECT_VARS：会把 Git 引到别的仓库的变量。 */
const GIT_REDIRECT_VARS = new Set(["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
  "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"]);

/** pi_dispatch.git_env。 */
export function gitEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {};
  for (const [name, value] of Object.entries(process.env)) {
    if (!GIT_REDIRECT_VARS.has(name.toUpperCase())) env[name] = value;
  }
  env["GIT_TERMINAL_PROMPT"] = "0";
  env["GCM_INTERACTIVE"] = "never";
  env["GIT_OPTIONAL_LOCKS"] = "0";
  return env;
}

/** pi_dispatch.git(check=False)：返回退出码与 stdout 的字节。找不到 git 报 DispatchError。 */
export function git(args: readonly string[], cwd: string): { status: number; stdout: Buffer } {
  const result = spawnSync("git", ["-c", "core.fsmonitor=false", "-c", "core.quotepath=off", ...args], {
    cwd,
    env: gitEnv(),
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  if (result.error) {
    if ((result.error as NodeJS.ErrnoException).code === "ENOENT") throw new DispatchError("未找到 git，请先安装 Git。");
    throw result.error;
  }
  return { status: result.status ?? 1, stdout: result.stdout };
}

function isDir(value: string): boolean {
  try {
    return statSync(value).isDirectory();
  } catch {
    return false;
  }
}

/** pi_dispatch.Repo。 */
export class Repo {
  readonly root: string;
  readonly agentDir: string;
  readonly runsDir: string;

  constructor(root: string) {
    this.root = root;
    this.agentDir = path.join(root, ".agent");
    this.runsDir = path.join(this.agentDir, "runs");
  }

  /** Repo.discover：--repo 或当前目录；必须在 Git 仓库的主工作区里。 */
  static discover(start: string | null): Repo {
    const base = pyResolve(start || process.cwd());
    if (!isDir(base)) throw new DispatchError(`--repo 不是目录：${base}`, EXIT_USAGE);
    const proc = git(["rev-parse", "--show-toplevel", "--git-dir", "--git-common-dir"], base);
    if (proc.status !== 0) throw new DispatchError(`当前目录不在 Git 仓库中：${base}`, EXIT_USAGE);
    const [top = "", gitDir = "", common = ""] = proc.stdout.toString("utf8").split(/\r\n|\r|\n/u);
    if (normCase(pyResolve(path.resolve(base, gitDir))) !== normCase(pyResolve(path.resolve(base, common)))) {
      throw new DispatchError(`请在主工作区运行本工具，而不是在 worktree 中：${top}`, EXIT_USAGE);
    }
    return new Repo(pyResolve(top));
  }
}

const STRICT_UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

/**
 * pi_dispatch.read_json_or：读不了（OSError）、不是 UTF-8、不是 JSON 都返回 fallback。BOM 照 Python 算 JSON 错误；
 * 嵌套太深时 Python 抛 RecursionError（read_json_or 不接），这里照样抛出。
 */
export function readJsonOr(file: string, fallback: PyValue): PyValue {
  let text: string;
  try {
    text = STRICT_UTF8.decode(readFileSync(file));
  } catch {
    return fallback;
  }
  try {
    return loads(text);
  } catch (error) {
    if (error instanceof PyJsonError && error.kind !== "RecursionError") return fallback;
    throw error;
  }
}
