// 回合的只读输入目录（迁移第 ⑤d 片，kit_hub.py 的 worktree_root、input_sources、_input_files、stage_inputs、remove_inputs）：
// worktree 根目录下的 <仓库名>-hub-inputs/<键>，每回合复制、回合结束删除。只复制，不用硬链接或联接：工人写进去的东西回不到证据里。
// INPUTS.json 照 Path.write_text 的缺省换行，Windows 上是 CRLF；SKIPPED.md 写 LF。
import { chmodSync, copyFileSync, lstatSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { pyItem, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { isLinkOrJunction, purePathName, purePathRelativePosix, purePathStr } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import { worktreeRoot as dispatcherWorktreeRoot } from "@themis/dispatcher/command-runner";
import { configWithBytes } from "@themis/dispatcher/kernel-config";
import { Repo } from "@themis/dispatcher/repo";
import { globPaths } from "@themis/dispatcher/instruction";
import { comparePaths } from "./audit.ts";
import { INPUTS_DIR, INPUTS_INDEX, INPUT_FILE_LIMIT } from "./constants.ts";
import type { Hub } from "./mailbox.ts";

const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);
const READ_ONLY = 0o444;
const WRITABLE = 0o666;

/** 调度器的 worktree 根目录（配置或 PI_DISPATCH_WORKTREE_ROOT，缺省是系统临时目录下的 pi-worktrees），没有就建。 */
export function worktreeRoot(repo: string): string {
  const pdRepo = new Repo(repo);
  const root = dispatcherWorktreeRoot(pdRepo, configWithBytes(pdRepo)[0]);
  mkdirSync(root, { recursive: true });
  return root;
}

/** 复制进输入目录的主工作区路径：本主任务各阶段的信箱目录、合同的各个版本、调度器的执行证据，都照相对仓库的原样摆放。 */
export function inputSources(hub: Hub, ts: PyDict): string[] {
  const task = pyStrValue(pyItem(ts, "task"));
  const tasks = join(hub.root, "tasks");
  const sources = globPaths(tasks, [`${task}*`]).sort(comparePaths)
    .filter((path) => isDir(path) && (purePathName(path) === task || purePathName(path).startsWith(`${task}-`)));
  const contractTask = ts.get("contract_task");
  if (pyTruthy(contractTask)) {
    const name = pyStrValue(contractTask as PyValue);
    const plans = join(hub.repo, ".agent", "plans");
    sources.push(...globPaths(plans, [`${name}.v*.md`]).sort(comparePaths), ...globPaths(plans, [`${name}.v*.json`]).sort(comparePaths));
    const runs = join(hub.repo, ".agent", "runs", name);
    if (isDir(runs)) sources.push(runs);
  }
  return sources;
}

/**
 * source 下的普通文件（os.walk 自上而下：先交出这一层排好序的文件，再按列目录的次序进各个子目录），不顺着链接与联接走。
 * 链接的判断用 base 的 isLinkOrJunction（符号链接与一切重解析点；Python 的 isjunction 只认联接，别的重解析点证据目录里不会有）。
 */
function inputFiles(source: string): string[] {
  const own = lstatOrNull(source);
  if (own?.isFile()) return [source];
  const found: string[] = [];
  const walk = (folder: string): void => {
    let names: string[];
    try {
      names = readdirSync(folder);
    } catch {
      return; // os.walk 列不出的目录跳过
    }
    const dirs: string[] = [];
    const files: string[] = [];
    for (const name of names) (statOrNull(join(folder, name))?.isDirectory() ? dirs : files).push(name);
    for (const name of files.sort(cmpCodePoints)) if (!lstatOrNull(join(folder, name))?.isSymbolicLink()) found.push(join(folder, name));
    for (const name of dirs) if (!isLinkOrJunction(join(folder, name))) walk(join(folder, name));
  };
  if (statOrNull(source)?.isDirectory()) walk(source);
  return found;
}

/**
 * 建这一回合的只读输入目录（第 88 轮）：照 inputSources 复制，文件设成只读；交回（目录，清单）。
 * options 只给契约的采样重放用：对应用例里 monkeypatch 掉的 worktree_root 与 INPUT_FILE_LIMIT（inputs_fixture）。
 */
export function stageInputs(hub: Hub, ts: PyDict, key: string, options: { readonly root?: string; readonly limit?: number } = {}): [string, PyDict] {
  const limit = options.limit ?? INPUT_FILE_LIMIT;
  const parent = join(options.root ?? worktreeRoot(hub.repo), INPUTS_DIR.replace("%s", purePathName(hub.repo)));
  // 第 89 轮：runner 被系统收掉、没走到 finally 时输入目录会留下；开新回合时清掉这个主任务留下的旧目录
  for (const stale of isDir(parent) ? globPaths(parent, [`${pyStrValue(pyItem(ts, "task"))}-*`]) : []) removeInputs(stale);
  const target = join(parent, key);
  removeInputs(target);
  mkdirSync(target, { recursive: true });
  const files: PyDict[] = [];
  const skipped: PyDict[] = [];
  for (const source of inputSources(hub, ts)) {
    for (const path of inputFiles(source)) {
      const rel = purePathRelativePosix(path, hub.repo) as string;
      const size = statSync(path).size;
      if (size > limit) {
        skipped.push(new Map<string, PyValue>([["path", rel], ["bytes", BigInt(size)]]));
        continue;
      }
      const dest = join(target, ...rel.split("/"));
      mkdirSync(join(dest, ".."), { recursive: true });
      copyFileSync(path, dest);
      chmodSync(dest, READ_ONLY);
      files.push(new Map<string, PyValue>([["path", rel], ["bytes", BigInt(size)]]));
    }
  }
  const index = new Map<string, PyValue>([["files", files], ["skipped", skipped]]);
  const text = `${dumps(index, { ensureAscii: false, indent: 1 })}${LF}`;
  writeFileSync(join(target, INPUTS_INDEX), process.platform === "win32" ? text.split(LF).join(CRLF) : text);
  chmodSync(join(target, INPUTS_INDEX), READ_ONLY);
  if (skipped.length) {
    const note = [`# 没有复制进来的文件（超过 ${limit} 字节）`, "", ...skipped.map((item) => `- ${pyStrValue(item.get("path") as PyValue)}（${pyStrValue(item.get("bytes") as PyValue)} 字节）`)];
    writeFileSync(join(target, "SKIPPED.md"), `${note.join(LF)}${LF}`);
  }
  const total = files.reduce((sum, item) => sum + (item.get("bytes") as bigint), 0n);
  return [target, new Map<string, PyValue>([["dir", purePathStr(target)], ["files", BigInt(files.length)], ["bytes", total], ["skipped", skipped]])];
}

/** 删掉一个输入目录：文件是只读的，先改回可写再删（rmtree 的 onexc）。 */
export function removeInputs(path: string | null): void {
  if (path === null || !statOrNull(path)) return;
  const writable = (dir: string): void => {
    for (const name of readdirSync(dir)) {
      const child = join(dir, name);
      const info = lstatOrNull(child);
      if (info?.isDirectory()) writable(child);
      else if (info && !info.isSymbolicLink()) chmodSync(child, WRITABLE);
    }
  };
  if (lstatOrNull(path)?.isDirectory()) writable(path);
  rmSync(path, { recursive: true, force: true });
}

function isDir(path: string): boolean {
  return statOrNull(path)?.isDirectory() ?? false;
}

function statOrNull(path: string): ReturnType<typeof statSync> | null {
  try {
    return statSync(path);
  } catch {
    return null;
  }
}

function lstatOrNull(path: string): ReturnType<typeof lstatSync> | null {
  try {
    return lstatSync(path);
  } catch {
    return null;
  }
}
