// config 命令行契约的共用部分（迁移第 ③c 片）：临时 Git 仓库、两种实现的运行、比较口径（仓库路径、审计号、txn、时间换成
// 占位符）与一步之后的仓库状态。Python 走真实的 `pi_dispatch.py --repo <仓库> config …`，TS 走 pyargs（带 context）。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { type CliRun, REPO, runConfigLauncherCli, runPythonCli, runTsCli } from "./harness.ts";

/** launcher：选择文件的 config 是 ts，经真的启动器转交（第 ③ 步的切换）。 */
export type Runner = "python" | "node" | "bun" | "launcher";
export const RUNNERS: readonly Runner[] = ["python", "node", "bun", "launcher"];

/** 一条命令：Python 的 argv（config 之后的部分）与 TS 的 pyargs（argparse 解析之后的值）。 */
export interface Command {
  readonly label: string;
  readonly argv: string[];
  readonly args: (repo: string) => Record<string, unknown>;
}

export const CONTEXT = { kit_root: REPO, lock_wait_seconds: 5.0 };

/** 临时 Git 仓库；本机文件、历史、审计、锁与 runs 都被忽略（照 kit_install 的忽略规则）。 */
export function gitRepo(path: string, ignore = true): string {
  mkdirSync(join(path, ".agent"), { recursive: true });
  const done = spawnSync("git", ["init", "-q", path], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr}`);
  if (ignore) {
    const rules = [".agent/config-history/", ".agent/audit/", ".agent/.config.lock/", ".agent/runs/", ".agent/dispatch.local.json", ""];
    spawnSync("git", ["-C", path, "config", "core.autocrlf", "false"]);
    writeFileSync(join(path, ".gitignore"), rules.join(String.fromCharCode(10)));
  }
  return path;
}

export function run(runner: Runner, repo: string, command: Command): CliRun {
  if (runner === "python") return runPythonCli(["--repo", repo, "config", ...command.argv], repo);
  if (runner === "launcher") return runConfigLauncherCli(["--repo", repo, "config", ...command.argv], repo);
  return runTsCli(runner, command.args(repo), repo);
}

/** 比较口径：仓库路径换成 <REPO>；审计号、txn 换成按出现次序编号的占位符，时间换成 <AT>。 */
export function normalize(text: string, repo: string): string {
  const ids = new Map<string, string>();
  const slot =
    (prefix: string) =>
    (match: string): string => {
      if (!ids.has(match)) ids.set(match, `<${prefix}${ids.size}>`);
      return ids.get(match) as string;
    };
  const backslash = String.fromCharCode(92);
  return text
    .replaceAll(repo.replaceAll(backslash, backslash + backslash), "<REPO>")
    .replaceAll(repo, "<REPO>")
    .replace(/aud-[0-9a-f]{32}/gu, slot("aud"))
    .replace(/\.[0-9a-f]{16}\.tmp/gu, ".<tmp>.tmp")
    .replace(/\b[0-9a-f]{32}\b/gu, slot("txn"))
    .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z/gu, "<AT>");
}

export const shown = (result: CliRun, repo: string): Record<string, unknown> => ({
  status: result.status,
  stdout: normalize(result.stdout.toString("utf8"), repo),
  stderr: normalize(result.stderr.toString("utf8"), repo),
});

/** 一步之后的仓库状态：配置、本机文件、快照目录、history --json（经 Python 读）与审计。 */
export function state(repo: string): Record<string, string> {
  const agent = join(repo, ".agent");
  const read = (path: string): string => (existsSync(path) ? readFileSync(path).toString("base64") : "<absent>");
  const historyDir = join(agent, "config-history");
  const snapshots = existsSync(historyDir)
    ? readdirSync(historyDir)
        .sort()
        .map((name) => `${name}:${readFileSync(join(historyDir, name)).toString("base64")}`)
    : [];
  const auditFile = join(agent, "audit", "management.jsonl");
  return {
    config: read(join(agent, "dispatch.config.json")),
    local: read(join(agent, "dispatch.local.json")),
    lock: existsSync(join(agent, ".config.lock")) ? "<left>" : "<none>",
    snapshots: snapshots.join("\n"),
    history: normalize(runPythonCli(["--repo", repo, "config", "history", "--json"], repo).stdout.toString("utf8"), repo),
    audit: normalize(existsSync(auditFile) ? readFileSync(auditFile, "utf8") : "", repo),
  };
}
