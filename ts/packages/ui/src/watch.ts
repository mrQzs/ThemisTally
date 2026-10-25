// status --json 的输入监视（桌面端设计第 7 版 §5.3、T3、D05/D06）：本机服务只 stat 内核名单上的路径察觉变化，有变化才
// 跑一次 status --json。名单从 @themis/contracts/status-inputs.json 这一份文件取（A1：一个字都不抄进 ui 包，抄了就会
// 与内核名单漂移），守卫测试 contracts/test/status-inputs.test.ts 保证 Python 与 TS 的 status 实际碰过的路径与名单双向
// 一致。每一层的条目先过 static.ts 的 isReparsePoint，是重解析点（junction、符号链接）就当它不存在，不进去也不 stat 它
// 的目标；根目录本身是重解析点时整轮指纹记成固定一行。fs 一律用 node:fs/promises 的异步调用，各轮不重叠（hub 负责）。
import { readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { isReparsePoint } from "./static.ts";
import STATUS_INPUTS from "@themis/contracts/status-inputs.json" with { type: "json" };

/** task 目录下的 attempt 名（内核的 attempt_pattern：^attempt-\d{3,}$）。 */
const ATTEMPT_RE = new RegExp(STATUS_INPUTS.attempt_pattern, "u");
/** checks 下的编号条目（内核的 numbered_pattern：目录 01 或文件 01.json 都算）。 */
const NUMBERED_RE = new RegExp(STATUS_INPUTS.numbered_pattern, "u");

/** 名单认识的四种占位（''、<task>、<attempt>、<n>）；遇到不认识的占位或段就抛错让服务起不来（不悄悄跳过）。 */
const PLACEHOLDERS = new Set(["<task>", "<attempt>", "<n>"]);

/** 校验一份路径模板只由这四种占位与普通字面段组成（占位可嵌在段里，如 <n>.json）；不认识的占位抛错。 */
function checkPlaceholders(template: string): void {
  for (const segment of template.split("/")) {
    for (const match of segment.matchAll(/<[^>]*>/g)) {
      if (!PLACEHOLDERS.has(match[0])) {
        throw new Error(`status-inputs 名单里有不认识的占位或段：${JSON.stringify(match[0])}（模板 ${JSON.stringify(template)}）`);
      }
    }
  }
}

// 模块装载时就把名单里的每一条路径模板校验一遍（名单是定死的，合法；谁改坏了这里就让服务起不来）。
for (const group of [STATUS_INPUTS.list, STATUS_INPUTS.exists, STATUS_INPUTS.read, STATUS_INPUTS.read_when_running]) {
  for (const template of group) checkPlaceholders(template);
}

/** 是不是目录（跟随符号链接；取不到就当不是）。 */
async function isDir(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isDirectory();
  } catch {
    return false;
  }
}

/** 在不在（任何类型；两态）。 */
async function present(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

/** 列一个目录的名字（取不到当空）。 */
async function names(path: string): Promise<string[]> {
  try {
    return await readdir(path);
  } catch {
    return [];
  }
}

/** 一条 read/read_when_running 的 stat 指纹：size、mtimeNs、ino（bigint）；不在时记 absent。 */
async function readStamp(lines: string[], path: string, label: string): Promise<void> {
  try {
    const info = await stat(path, { bigint: true });
    lines.push(`R ${label} ${info.size} ${info.mtimeNs} ${info.ino}`);
  } catch {
    lines.push(`R ${label} absent`);
  }
}

/** 展开一条 read 路径模板并 stat：无 <n> 的直接取；有 <n> 的按 checks（只对目录）与 verdicts（每项）展开。 */
async function expandRead(
  lines: string[],
  root: string,
  task: string,
  attempt: string,
  template: string,
  checks: readonly string[],
  verdicts: readonly string[],
): Promise<void> {
  const rest = template.split("/").slice(2); // 去掉 <task> 与 <attempt> 两级
  if (!rest.some((segment) => segment.includes("<n>"))) {
    await readStamp(lines, join(root, task, attempt, ...rest), `${task}/${attempt}/${rest.join("/")}`);
    return;
  }
  if (rest[0] === "checks") {
    // checks/<n>/checks.json：只对 checks 下是目录的 <n> 取
    for (const name of checks) {
      const dir = join(root, task, attempt, "checks", name);
      if (!(await isDir(dir))) continue;
      await readStamp(lines, join(dir, "checks.json"), `${task}/${attempt}/checks/${name}/checks.json`);
    }
  } else if (rest[0] === "verdicts") {
    // verdicts/<n>.json：对 verdicts 列表里的每一项取（条目已收成 .json）
    for (const name of verdicts) {
      await readStamp(lines, join(root, task, attempt, "verdicts", name), `${task}/${attempt}/verdicts/${name}`);
    }
  }
}

/**
 * 跑一轮指纹：根目录是 <repo>/.agent/runs。根本身是重解析点 → 固定一行 root-reparse。否则按名单四类取法收集：
 * 列根目录收 task（目录且非重解析点）、列每个 task 收 attempt（attempt_pattern 且目录且非重解析点）、列 checks 与
 * verdicts、claim 的两态、read 与 read_when_running 的 stat。深度只到名单写的那几层，不递归。返回排序后的多行文本。
 */
export async function fingerprint(repo: string): Promise<string> {
  const root = join(repo, ".agent", "runs");
  if (isReparsePoint(root)) return "root-reparse";
  const lines: string[] = [];
  const tasks = (await names(root))
    .filter((name) => name !== "")
    .sort();
  for (const task of tasks) {
    const taskDir = join(root, task);
    if (!(await isDir(taskDir))) continue; // 只收目录
    if (isReparsePoint(taskDir)) continue; // 重解析点当它不存在
    lines.push(`T ${task}`);
    const attempts = (await names(taskDir)).filter((name) => ATTEMPT_RE.test(name)).sort();
    for (const attempt of attempts) {
      const attemptDir = join(taskDir, attempt);
      if (!(await isDir(attemptDir))) continue;
      if (isReparsePoint(attemptDir)) continue;
      lines.push(`A ${task}/${attempt}`);
      const checksDir = join(attemptDir, "checks");
      const checks = (await names(checksDir)).filter((name) => NUMBERED_RE.test(name) && !isReparsePoint(join(checksDir, name))).sort();
      for (const name of checks) lines.push(`C ${task}/${attempt}/checks/${name}`);
      const verdictsDir = join(attemptDir, "verdicts");
      const verdicts = (await names(verdictsDir)).filter((name) => name.endsWith(".json") && !isReparsePoint(join(verdictsDir, name))).sort();
      for (const name of verdicts) lines.push(`V ${task}/${attempt}/verdicts/${name}`);
      lines.push(`claim ${task}/${attempt} ${(await present(join(attemptDir, "claim"))) ? 1 : 0}`);
      for (const template of STATUS_INPUTS.read) await expandRead(lines, root, task, attempt, template, checks, verdicts);
      for (const template of STATUS_INPUTS.read_when_running) await expandRead(lines, root, task, attempt, template, checks, verdicts);
    }
  }
  lines.sort();
  return lines.join("\n");
}
