// 命令行契约用的临时 Git 仓库（迁移第 ④b2 片起）：固定作者与时间，三份实现各建一份时提交号相同；写文件；比较口径
// （仓库与工作树的路径、时间换成占位符）；一步之后的目录快照。不写转义序列。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { type CliRun, REPO, removeDir, runPythonCli, runTsCli, scratchDir } from "./harness.ts";

export const LF = String.fromCharCode(10);
const SLASH = String.fromCharCode(92);
export const CONTEXT = { kit_root: REPO, kernel_impl: { readonly: "python", config: "python", dispatcher: "python", hub: "python" } };
const GIT_ENV = {
  ...process.env, GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-01T00:00:00+00:00",
};

const created: string[] = [];

/** 用完的临时目录（各测试文件的 afterAll 里调）。 */
export function removeCreated(): void {
  for (const dir of created.splice(0)) removeDir(dir);
}

export function tempDir(prefix: string): string {
  const dir = scratchDir(prefix);
  created.push(dir);
  return dir;
}

export function git(cwd: string, ...args: string[]): string {
  const done = spawnSync("git", args, { cwd, env: GIT_ENV, encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  return done.stdout.trim();
}

export function put(root: string, rel: string, content: string | Uint8Array): void {
  mkdirSync(dirname(join(root, rel)), { recursive: true });
  writeFileSync(join(root, rel), content);
}

/** 一个提交了 files 的临时仓库（.agent/runs/ 被忽略）；交回仓库路径与 HEAD。 */
export function newRepo(prefix: string, files: Record<string, string> = {}): { repo: string; head: string } {
  const repo = tempDir(prefix);
  git(repo, "init", "-q");
  git(repo, "config", "core.autocrlf", "false");
  put(repo, ".gitignore", `.agent/runs/${LF}`);
  for (const [rel, content] of Object.entries({ "AGENTS.md": `# AGENTS${LF}`, "src/a.ts": `export const a = 1;${LF}`, ...files })) put(repo, rel, content);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "-m", "base");
  return { repo, head: git(repo, "rev-parse", "HEAD") };
}

/** 比较口径：给出的几个路径（短名与解析出来的长路径都算，连同 JSON 里转义过的写法）换成占位符，ISO 时间换成 <AT>。 */
export function normalize(text: string, paths: Record<string, string>): string {
  let out = text;
  const pairs = Object.entries(paths).flatMap(([label, value]) => [[label, value], [label, longPath(value)]] as [string, string][]);
  for (const [label, value] of pairs.sort(([, a], [, b]) => b.length - a.length)) {
    out = out.replaceAll(value.replaceAll(SLASH, SLASH + SLASH), label).replaceAll(value, label);
  }
  return out.replace(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/gu, "<AT>");
}

/** 目录下全部文件（相对路径 → 文字，二进制按 base64），用来比较一步之后的证据。 */
export function snapshotDir(root: string, paths: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  if (!existsSync(root)) return out;
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else out[relative(root, full).split(SLASH).join("/")] = normalize(readFileSync(full).toString("utf8"), paths);
    }
  };
  walk(root);
  return out;
}

/** 存在的路径解析成长路径（8.3 短名展开）；不存在的原样。 */
function longPath(value: string): string {
  try {
    return realpathSync.native(value);
  } catch {
    return value;
  }
}

export type Runner = "python" | "node" | "bun";
export const RUNNERS: readonly Runner[] = ["python", "node", "bun"];

/** 一条命令：Python 的 argv（--repo 之后）与 TS 的 pyargs。 */
export function runCommand(runner: Runner, repo: string, argv: readonly string[], args: Record<string, unknown>, cwd = repo): CliRun {
  if (runner === "python") return runPythonCli(["--repo", repo, ...argv], cwd);
  return runTsCli(runner, { repo, ...args }, cwd);
}

export interface Shown {
  readonly status: number;
  readonly stdout: string;
  readonly stderr: string;
}

/** 输出的比较口径；crash 时只比退出码（Python 打堆栈，TS 写一行“崩溃”）。 */
export function shownOf(result: CliRun, paths: Record<string, string>, crash = false): Shown {
  if (crash) return { status: result.status, stdout: "", stderr: "" };
  return { status: result.status, stdout: normalize(result.stdout.toString("utf8"), paths), stderr: normalize(result.stderr.toString("utf8"), paths) };
}
