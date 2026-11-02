// pi_dispatch 的 sync-adapters（迁移第 ④b2 片）：.agents/skills 是技能的唯一来源，Claude Code 只读 .claude/skills，复制
// 一份给它。不跟随、也不收录符号链接与 junction，跳过 __pycache__；源或副本的路径经过链接时拒绝。照 os.walk：读不了的
// 目录悄悄跳过，读文件出错时 Python 不接、命令崩溃。
import { mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pyWinErrorMessage } from "@themis/base/supervise";
import { PyCrash, type PyOut } from "@themis/base/pyfmt";
import { pyOSErrorOf, pyReadBytes } from "@themis/base/pyio";
import { isLinkOrJunction, normcase, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import { DispatchError, EXIT_FAIL, EXIT_OK, Repo } from "./repo.ts";

export const SKILL_SOURCE_DIR = ".agents/skills";
export const CLAUDE_SKILL_DIR = ".claude/skills";
export const KIT_SKILLS = ["check-pi-env", "plan-task", "dispatch-pi", "review-pi"];

function stat(file: string): ReturnType<typeof statSync> | null {
  try {
    return statSync(file);
  } catch {
    return null;
  }
}

/** _tree_files：目录下全部普通文件的 {相对路径（POSIX）: 字节}；目录不存在或本身是链接时为空。次序照 os.walk。 */
export function treeFiles(root: string): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  if (!stat(root)?.isDirectory() || isLinkOrJunction(root)) return files;
  const walk = (dir: string, rel: string): void => {
    let names: string[];
    try {
      names = readdirSync(dir);
    } catch {
      return; // os.walk 的 onerror 缺省为 None：读不了的目录跳过
    }
    const dirs: string[] = [];
    const plain: string[] = [];
    for (const name of names) (stat(path.join(dir, name))?.isDirectory() ? dirs : plain).push(name);
    for (const name of plain.sort(cmpCodePoints)) {
      const file = path.join(dir, name);
      if (isLinkOrJunction(file) || !stat(file)?.isFile()) continue;
      files.set(rel ? `${rel}/${name}` : name, pyReadBytes(file));
    }
    for (const name of dirs.filter((item) => item !== "__pycache__" && !isLinkOrJunction(path.join(dir, item))).sort(cmpCodePoints)) {
      walk(path.join(dir, name), rel ? `${rel}/${name}` : name);
    }
  };
  walk(root, "");
  return files;
}

/** _repo_local_path：仓库相对路径的真实位置必须就是仓库内的预期位置（它或上级目录不能是链接）。 */
function repoLocalPath(root: string, rel: string, purpose: string): string {
  const local = path.join(root, rel);
  const expected = path.join(pyResolve(root), rel);
  const actual = pyResolve(local);
  if (normcase(actual) !== normcase(expected)) {
    throw new DispatchError(`${rel} 或其上级目录是符号链接或 junction（解析为 ${actual}）：${purpose}。先删去链接，改用真实目录`);
  }
  return local;
}

const skillSource = (root: string, name: string): string =>
  repoLocalPath(root, `${SKILL_SOURCE_DIR}/${name}`, "拒绝读取，以免把链接指向的内容复制进副本");

export const claudeSkillTarget = (root: string, name: string): string =>
  repoLocalPath(root, `${CLAUDE_SKILL_DIR}/${name}`, "拒绝同步，以免写入或删除链接指向的目录");

/** adapter_drift：（源目录中缺少 SKILL.md 的技能, 副本与源逐字节比较的不一致之处）。 */
export function adapterDrift(root: string): [string[], string[]] {
  const missing: string[] = [];
  const drift: string[] = [];
  for (const name of KIT_SKILLS) {
    const source = treeFiles(skillSource(root, name));
    const copyDir = claudeSkillTarget(root, name); // 源缺失时也先校验副本目录
    if (!source.has("SKILL.md")) {
      missing.push(name);
      continue;
    }
    const copy = treeFiles(copyDir);
    for (const rel of [...new Set([...source.keys(), ...copy.keys()])].sort(cmpCodePoints)) {
      if (!copy.has(rel)) drift.push(`${name}/${rel}：副本缺失`);
      else if (!source.has(rel)) drift.push(`${name}/${rel}：副本多出（源中没有）`);
      else if (!(source.get(rel) as Buffer).equals(copy.get(rel) as Buffer)) drift.push(`${name}/${rel}：内容不同`);
    }
  }
  return [missing, drift];
}

const sameTree = (a: Map<string, Buffer>, b: Map<string, Buffer>): boolean =>
  a.size === b.size && [...a].every(([rel, data]) => b.get(rel)?.equals(data) ?? false);

/** sync_adapters：先校验全部目标路径，再把源整目录复制过去；交回实际更新的技能名。 */
export function syncAdapters(root: string): string[] {
  const targets = new Map(KIT_SKILLS.map((name) => [name, claudeSkillTarget(root, name)]));
  const changed: string[] = [];
  for (const name of KIT_SKILLS) {
    const source = treeFiles(skillSource(root, name));
    if (!source.has("SKILL.md")) continue;
    const targetDir = targets.get(name) as string;
    if (sameTree(treeFiles(targetDir), source)) continue;
    const existing = stat(targetDir);
    if (existing) {
      // shutil.rmtree 对文件（不是目录）抛 NotADirectoryError
      if (!existing.isDirectory()) throw new PyCrash("NotADirectoryError", pyWinErrorMessage(267, targetDir)); // scandir 带文件名
      rmSync(targetDir, { recursive: true });
    }
    for (const [rel, data] of source) {
      const target = path.join(targetDir, rel);
      try {
        mkdirSync(path.dirname(target), { recursive: true });
        writeFileSync(target, data);
      } catch (error) {
        throw pyOSErrorOf(error, target) ?? error;
      }
    }
    changed.push(name);
  }
  return changed;
}

export interface SyncAdaptersArgs {
  readonly repo: string | null;
  readonly check: boolean;
}

export function cmdSyncAdapters(args: SyncAdaptersArgs, out: PyOut): number {
  const repo = Repo.discover(args.repo);
  const [missing, drift] = adapterDrift(repo.root);
  if (missing.length === KIT_SKILLS.length) {
    throw new DispatchError(`没有找到 ${SKILL_SOURCE_DIR}/<技能>/SKILL.md：仓库可能仍是 1.x 布局（技能在 .claude/skills），见 README 的升级说明`);
  }
  for (const name of missing) out.print(`WARN  ${SKILL_SOURCE_DIR}/${name} 缺少 SKILL.md，跳过`);
  if (args.check) {
    for (const item of drift) out.print(`DRIFT ${item}`);
    if (drift.length || missing.length) {
      out.print(`Claude Code 的技能副本与 ${SKILL_SOURCE_DIR} 不一致：${drift.length} 处${missing.length ? `；另有 ${missing.length} 个技能缺少源文件` : ""}。` +
        "补齐源文件后运行 bash scripts/dispatch-pi.sh sync-adapters 同步。");
      return EXIT_FAIL;
    }
    out.print(`Claude Code 的技能副本（${CLAUDE_SKILL_DIR}）与 ${SKILL_SOURCE_DIR} 一致。`);
    return EXIT_OK;
  }
  const changed = syncAdapters(repo.root);
  out.print(changed.length ? `已同步到 ${CLAUDE_SKILL_DIR}：${changed.join(", ")}。请一并提交。` : "Claude Code 的技能副本已是最新，没有改动。");
  if (missing.length) {
    out.print(`缺少源文件的技能没有同步：${missing.join(", ")}`);
    return EXIT_FAIL;
  }
  return EXIT_OK;
}
