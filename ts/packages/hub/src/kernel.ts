// 内核目录与内核的 git 调用（迁移第 ⑤d 片）：kit_hub.py 的 HERE、TEMPLATE_DIR、DELIVER_EXTENSION、GUARD_EXTENSION、SCHEMA_DIR 与 git()。
// 路径照 Path(__file__).resolve() 解析到真实路径（8.3 短名展开、联接跟随）：hub 从短名或联接起，写进提示词、命令行的内核路径两边照样一样。
// 模板、schema、扩展仍是 scripts/hub 下那一份，两套实现读同一份（第 1.2 节：数据与模板照原样沿用）。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PyCrash, pyReprValue } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { pyResolve } from "@themis/base/pypath";
import { pyStrip } from "@themis/base/pyre";
import { pyWinErrorMessage } from "@themis/base/supervise";
import { HubError } from "./errors.ts";

/** kit_hub 的 HERE（scripts 目录）。这份源码在 ts/packages/hub/src 下，往上四层是仓库根。 */
export const SCRIPTS_DIR = pyResolve(join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "scripts"));
/** HERE.parent：内核自己的仓库（engineering_rules 在这里读已提交的 AGENTS.md），不一定是 hub 管的仓库。 */
export const KERNEL_ROOT = dirname(SCRIPTS_DIR);
export const TEMPLATE_DIR = join(SCRIPTS_DIR, "hub");
/** 交差工具（第 90 轮）与守卫扩展（第 106 轮）：pi 工人进程里跑的内核文件。 */
export const DELIVER_EXTENSION = join(TEMPLATE_DIR, "deliver.ts");
export const GUARD_EXTENSION = join(TEMPLATE_DIR, "guard.ts");
export const SCHEMA_DIR = join(TEMPLATE_DIR, "schemas");
/** kit_hub 的 HUB_SHA256：kit_hub.py 的 sha256，本进程载入时算（result.json 记它；切换之后它该指什么归 ⑤j 或切换再定）。 */
export const HUB_SHA256 = createHash("sha256").update(readFileSync(join(SCRIPTS_DIR, "kit_hub.py"))).digest("hex");

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/**
 * kit_hub 的 git()：参数原样（不像调度器那样加 -c core.quotepath=off，ls-tree 列出的非 ASCII 文件名照 Git 的缺省加引号转义），
 * 输出按 utf-8 加 replace 解码；check 时退出码不是 0 就抛 HubError，带 stderr 去掉两头空白后的前 400 个码点。
 */
export function git(args: readonly string[], cwd: string, check = true, timeout = 120): string {
  const done = spawnSync("git", [...args], { cwd, timeout: timeout * 1000, maxBuffer: 1024 * 1024 * 1024, windowsHide: true });
  if (done.error) {
    const code = (done.error as NodeJS.ErrnoException).code;
    if (code === "ETIMEDOUT") throw new PyCrash("TimeoutExpired", `Command '${pyReprValue(["git", ...args])}' timed out after ${timeout} seconds`); // str(TimeoutExpired)
    if (code === "ENOENT") {
      // Windows 上 cwd 不存在时 Python 抛的是 NotADirectoryError（WinError 267），不是“找不到 git”（照调度器的 repo.ts）
      if (process.platform === "win32" && !isDir(cwd)) throw new PyCrash("NotADirectoryError", pyWinErrorMessage(267)); // CreateProcess 失败，不带路径
      throw new PyCrash("FileNotFoundError", pyWinErrorMessage(2)); // CreateProcess 找不到 git，不带路径
    }
    throw done.error;
  }
  const out = pyDecodeUtf8Replace(done.stdout);
  if (check && done.status !== 0) {
    const err = [...pyStrip(pyDecodeUtf8Replace(done.stderr))].slice(0, 400).join("");
    throw new HubError(`git ${args.join(" ")} 失败：${err}`);
  }
  return out;
}

/**
 * kit_hub 的 workspace_status（迁移第 ⑤e2a 片）：git status --porcelain=v1 -z 的各项，切成（两个字符的状态，路径）。按码点切，与
 * Python 的切片一样。照抄 Python 的毛病（迁移计划第 10.1 节）：-z 时改名与复制写成“XY 新路径、NUL、旧路径”，旧路径前没有状态码，
 * 这里照样把旧路径的前两个字符当状态、第四个字符起当路径；旧路径不超过 3 个字符时整项丢掉。
 */
export function workspaceStatus(path: string): [string, string][] {
  const out = git(["status", "--porcelain=v1", "--untracked-files=all", "-z"], path);
  const entries: [string, string][] = [];
  for (const item of out.split(String.fromCharCode(0))) {
    const points = [...item];
    if (points.length > 3) entries.push([points.slice(0, 2).join(""), points.slice(3).join("")]);
  }
  return entries;
}
