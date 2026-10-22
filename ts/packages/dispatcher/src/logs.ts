// kit_logs 的 list 与 show（迁移第 ②a 步）。只读：链接（符号链接、junction 与其它重解析点）一律不跟随、计入
// “跳过的链接”。列举失败按层处理（kit_logs 文件头 B11(a)）：runs 根列不出来退出码 1；目标解析中列不出来、目标
// attempt 的证据目录列不出来退出码 2；其余目录跳过且不计数。
import { closeSync, existsSync, lstatSync, openSync, readdirSync, readSync } from "node:fs";
import path from "node:path";
import { type PyOut, pyRepr } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, PyJsonError, dumps, loads } from "@themis/base/pyjson";
import { firstLinkComponent, isLinkOrJunction, isWithin, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, pyIntParse } from "@themis/base/pyre";
import { DispatchError, Repo } from "./repo.ts";
import { ATTEMPT_DIR_RE, PLAN_KEY_RE, TASK_ID_RE } from "./status.ts";

export const LOGS_EXIT_OK = 0;
export const LOGS_EXIT_FAIL = 1;
export const LOGS_EXIT_USAGE = 2;
const MAX_SUMMARY_BYTES = 65536;
const UNKNOWN_STATE = "UNKNOWN";
const NO_ATTEMPT = "没有 attempt";
const WIN = process.platform === "win32";

/** kit_logs.LogsError：一行 `ERROR: …` 到 stderr，按 code 退出。 */
export class LogsError extends Error {
  readonly code: number;

  constructor(message: string, code: number = LOGS_EXIT_FAIL) {
    super(message);
    this.code = code;
  }
}

/** 本命令访问过程中遇到的链接条目数。 */
export class LinkTally {
  count = 0;

  hit(): void {
    this.count += 1;
  }
}

type Entry = [name: string, entryPath: string];

function exists(value: string): boolean {
  try {
    return existsSync(value);
  } catch {
    return false;
  }
}

function lstatKind(value: string): "dir" | "file" | "other" | null {
  try {
    const info = lstatSync(value);
    return info.isDirectory() ? "dir" : info.isFile() ? "file" : "other";
  } catch {
    return null;
  }
}

const isDir = (value: string): boolean => lstatKind(value) === "dir";
const isRegular = (value: string): boolean => lstatKind(value) === "file";

/** kit_logs._scan：直接子项，按名字（码点）排序；列不出来为 null。 */
function scan(directory: string): Entry[] | null {
  let names: string[];
  try {
    names = readdirSync(directory);
  } catch {
    return null;
  }
  return names.sort(cmpCodePoints).map((name) => [name, path.join(directory, name)] as Entry);
}

/** kit_logs._under：root 之下按段拼接。 */
export function under(root: string, parts: readonly string[]): string {
  let text = root;
  for (const part of parts) {
    if (!text.endsWith("\\") && !text.endsWith("/")) text += path.sep;
    text += part;
  }
  return text;
}

/** kit_logs._read_head：最多读 limit 字节（limit < 0 读全部）；读不了为 null。 */
export function readHead(file: string, limit: number): Buffer | null {
  let fd: number;
  try {
    fd = openSync(file, "r");
  } catch {
    return null;
  }
  try {
    const chunks: Buffer[] = [];
    let total = 0;
    for (;;) {
      const want = limit < 0 ? 1 << 20 : Math.min(1 << 20, limit - total);
      if (want <= 0) break;
      const chunk = Buffer.allocUnsafe(want);
      const got = readSync(fd, chunk, 0, want, null);
      if (got === 0) break;
      chunks.push(chunk.subarray(0, got));
      total += got;
    }
    return Buffer.concat(chunks);
  } catch {
    return null;
  } finally {
    closeSync(fd);
  }
}

const STRICT_UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const REPLACE_UTF8 = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });

/** kit_logs._read_json：缺失、不可读、不是 UTF-8、不是 JSON、嵌套太深都为 null（undefined 表示 None）。 */
function readJson(file: string): PyValue | undefined {
  const raw = readHead(file, -1);
  if (raw === null) return undefined;
  try {
    return loads(STRICT_UTF8.decode(raw));
  } catch (error) {
    if (error instanceof PyJsonError || error instanceof TypeError) return undefined;
    throw error;
  }
}

// --- 枚举 -----------------------------------------------------------------------

function taskEntries(runs: string, links: LinkTally): Entry[] {
  if (!exists(runs)) return [];
  const entries = scan(runs);
  if (entries === null) throw new LogsError(`无法列出 ${runs}`, LOGS_EXIT_FAIL);
  return entries.filter(([name, entry]) => {
    if (!TASK_ID_RE.test(name)) return false;
    if (isLinkOrJunction(entry)) {
      links.hit();
      return false;
    }
    return isDir(entry);
  });
}

type AttemptEntry = [name: string, number: bigint, entryPath: string];

function attemptEntries(taskDir: string, links: LinkTally): AttemptEntry[] {
  const entries = scan(taskDir);
  if (entries === null) return [];
  const found: AttemptEntry[] = [];
  for (const [name, entry] of entries) {
    const match = ATTEMPT_DIR_RE.exec(name);
    if (!match) continue;
    if (isLinkOrJunction(entry)) {
      links.hit();
      continue;
    }
    if (!isDir(entry)) continue;
    found.push([name, pyIntParse(match.groups?.["n"] ?? "") ?? 0n, entry]);
  }
  return found
    .map((item, index) => ({ item, index }))
    .sort((a, b) => (a.item[1] < b.item[1] ? -1 : a.item[1] > b.item[1] ? 1 : a.index - b.index))
    .map(({ item }) => item);
}

function attemptsOf(runs: string, task: string, links: LinkTally): AttemptEntry[] {
  const taskDir = path.join(runs, task);
  if (isLinkOrJunction(taskDir) || !isDir(taskDir)) return [];
  return attemptEntries(taskDir, links);
}

/** kit_logs._evidence：attempt 之下递归的普通文件 [(POSIX 相对路径, 字节数)]；attempt 目录列不出来为 null。 */
export function evidence(attemptDir: string, links: LinkTally): [string, number][] | null {
  const entries = scan(attemptDir);
  if (entries === null) return null;
  const found: [string, number][] = [];
  const pending: [string, Entry[]][] = [["", entries]];
  while (pending.length > 0) {
    const [rel, here] = pending.pop() as [string, Entry[]];
    for (const [name, entry] of here) {
      const child = rel ? `${rel}/${name}` : name;
      if (isLinkOrJunction(entry)) {
        links.hit();
        continue;
      }
      let info;
      try {
        info = lstatSync(entry);
      } catch {
        continue;
      }
      if (info.isDirectory()) {
        const nested = scan(entry);
        if (nested !== null) pending.push([child, nested]);
      } else if (info.isFile()) {
        found.push([child, info.size]);
      }
    }
  }
  return found.sort((a, b) => cmpCodePoints(a[0], b[0]));
}

// --- 状态与摘要 -------------------------------------------------------------------

function readState(attemptDir: string): [string, string | null] {
  const file = path.join(attemptDir, "state.json");
  if (isLinkOrJunction(file) || !isRegular(file)) return [UNKNOWN_STATE, null];
  const data = readJson(file);
  if (!(data instanceof Map)) return [UNKNOWN_STATE, null];
  const state = data.get("state");
  const at = data.get("at");
  return [typeof state === "string" ? state : UNKNOWN_STATE, typeof at === "string" ? at : null];
}

interface Summary {
  readonly bytes: number;
  readonly truncated: boolean;
  readonly text: string;
}

function summaryOf(attemptDir: string): Summary | null {
  const file = path.join(attemptDir, "summary.md");
  if (isLinkOrJunction(file) || !isRegular(file)) return null;
  let size: number;
  try {
    size = lstatSync(file).size;
  } catch {
    return null;
  }
  const raw = readHead(file, MAX_SUMMARY_BYTES);
  if (raw === null) return null;
  return { bytes: size, truncated: size > MAX_SUMMARY_BYTES, text: REPLACE_UTF8.decode(raw) };
}

// --- 目标解析 -------------------------------------------------------------------

type Target = [task: string, attempt: string, attemptDir: string];

function checkWithinRuns(runs: string, target: string): void {
  if (!isWithin(pyResolve(target), pyResolve(runs))) throw new LogsError(`目标不在 runs 根之下：${target}`, LOGS_EXIT_USAGE);
}

function byPlanKey(runs: string, task: string, version: bigint): Target {
  let best: AttemptEntry | null = null;
  for (const item of attemptsOf(runs, task, new LinkTally())) {
    const meta = path.join(item[2], "meta.json");
    if (isLinkOrJunction(meta) || !isRegular(meta)) continue;
    const data = readJson(meta);
    if (!(data instanceof Map)) continue;
    const value = data.get("plan_version");
    if (typeof value !== "bigint" || value !== version) continue; // bool、float 都不算
    if (best === null || item[1] > best[1]) best = item;
  }
  if (best === null) throw new LogsError(`找不到 ${task}.v${version} 对应的 attempt`, LOGS_EXIT_USAGE);
  return [task, best[0], best[2]];
}

function byTask(runs: string, task: string): Target {
  const entries = attemptsOf(runs, task, new LinkTally());
  if (entries.length === 0) throw new LogsError(`任务 ${task} 没有 attempt（或不存在、是链接）`, LOGS_EXIT_USAGE);
  const [name, , entry] = entries[entries.length - 1] as AttemptEntry;
  return [task, name, entry];
}

function byTaskAttempt(runs: string, task: string, attempt: string): Target {
  const relative = `${task}/${attempt}`;
  const linked = firstLinkComponent(runs, relative);
  if (linked !== null) throw new LogsError(`目标经过链接：${linked}`, LOGS_EXIT_USAGE);
  const target = path.join(runs, task, attempt);
  if (isLinkOrJunction(target) || !isDir(target)) throw new LogsError(`目标不是目录：${relative}`, LOGS_EXIT_USAGE);
  return [task, attempt, target];
}

/** kit_logs._segments：按分隔符切段，空段与 . 忽略，.. 保留。 */
function segments(raw: string): string[] {
  return raw.split(WIN ? /[\\/]/u : /\//u).filter((part) => part !== "" && part !== ".");
}

function samePrefix(parts: readonly string[], rootParts: readonly string[]): boolean {
  if (parts.length < rootParts.length) return false;
  return rootParts.every((expected, index) => {
    const actual = parts[index] as string;
    return actual === expected || (WIN && actual.toLowerCase() === expected.toLowerCase());
  });
}

/** ntpath.join(a, b) 与 posixpath.join(a, b)（两段）。 */
function osJoin(a: string, b: string): string {
  if (!WIN) return b.startsWith("/") ? b : a.endsWith("/") ? a + b : `${a}/${b}`;
  const split = (value: string): [string, string, string] => {
    const drive = /^[A-Za-z]:/u.exec(value)?.[0] ?? (/^[\\/]{2}[^\\/]+[\\/]+[^\\/]+/u.exec(value)?.[0] ?? "");
    const rest = value.slice(drive.length);
    const root = /^[\\/]/u.test(rest) ? rest.slice(0, 1) : "";
    return [drive, root, rest.slice(root.length)];
  };
  let [drive, root, tail] = split(a);
  const [pDrive, pRoot, pTail] = split(b);
  if (pRoot) {
    if (pDrive || !drive) drive = pDrive;
    root = pRoot;
    tail = pTail;
  } else if (pDrive && pDrive !== drive) {
    if (pDrive.toLowerCase() !== drive.toLowerCase()) {
      drive = pDrive;
      root = pRoot;
      tail = pTail;
    } else {
      drive = pDrive;
      if (tail && !/[\\/]$/u.test(tail)) tail += "\\";
      tail += pTail;
    }
  } else {
    if (tail && !/[\\/]$/u.test(tail)) tail += "\\";
    tail += pTail;
  }
  if (tail && !root && drive && !drive.endsWith(":")) return `${drive}\\${tail}`;
  return drive + root + tail;
}

function byExplicitPath(runs: string, target: string): Target {
  const raw = path.isAbsolute(target) ? target : osJoin(process.cwd(), target);
  const parts = segments(raw);
  const rootParts = segments(runs);
  if (!samePrefix(parts, rootParts)) throw new LogsError(`目标不在 runs 根之下：${target}`, LOGS_EXIT_USAGE);
  const stack: string[] = [];
  for (const part of parts.slice(rootParts.length)) {
    if (part === "..") {
      if (stack.length === 0) throw new LogsError(`目标越出 runs 根：${target}`, LOGS_EXIT_USAGE);
      stack.pop();
      continue;
    }
    stack.push(part);
    if (isLinkOrJunction(under(runs, stack))) throw new LogsError(`目标经过链接：${stack.join("/")}`, LOGS_EXIT_USAGE);
  }
  if (stack.length !== 2 || !TASK_ID_RE.test(stack[0] as string) || !ATTEMPT_DIR_RE.test(stack[1] as string)) {
    throw new LogsError(`目标不是 <任务>/<attempt-NNN>：${target}`, LOGS_EXIT_USAGE);
  }
  const attemptDir = under(runs, stack);
  if (isLinkOrJunction(attemptDir) || !isDir(attemptDir)) throw new LogsError(`目标不是目录：${target}`, LOGS_EXIT_USAGE);
  return [stack[0] as string, stack[1] as string, attemptDir];
}

function resolveForms(runs: string, target: string): Target {
  if (target.includes("\0")) throw new LogsError(`目标不是合法的 attempt：${pyRepr(target)}`, LOGS_EXIT_USAGE);
  const key = PLAN_KEY_RE.exec(target);
  if (key) return byPlanKey(runs, key.groups?.["task"] ?? "", BigInt(key.groups?.["ver"] ?? "0"));
  if (TASK_ID_RE.test(target)) return byTask(runs, target);
  if (target.split("/").length === 2 && !target.includes("\\")) {
    const [head = "", tail = ""] = target.split("/");
    if (TASK_ID_RE.test(head) && ATTEMPT_DIR_RE.test(tail)) return byTaskAttempt(runs, head, tail);
  }
  return byExplicitPath(runs, target);
}

/** kit_logs._resolve_target。 */
export function resolveTarget(runs: string, target: string): Target {
  const found = resolveForms(runs, target);
  checkWithinRuns(runs, found[2]);
  return found;
}

// --- 命令 -----------------------------------------------------------------------

export function repoOf(value: string | null): Repo {
  try {
    return Repo.discover(value);
  } catch (error) {
    if (error instanceof DispatchError) throw new LogsError(error.message, error.code);
    throw error;
  }
}

function checkTask(task: string | null): string | null {
  if (task === null) return null;
  if (!TASK_ID_RE.test(task)) throw new LogsError(`--task 必须是合法的任务 ID：${pyRepr(task)}`, LOGS_EXIT_USAGE);
  return task;
}

export const emitJson = (out: PyOut, value: PyValue): void => out.print(dumps(value, { ensureAscii: false, indent: 2 }));
const skippedLinksLine = (count: number): string => `跳过的链接：${count}`;

export interface ListArgs {
  readonly repo: string | null;
  readonly task: string | null;
  readonly state: string | null;
  readonly json: boolean;
}

/** kit_logs.cmd_list。 */
export function cmdList(args: ListArgs, out: PyOut): number {
  const repo = repoOf(args.repo);
  const links = new LinkTally();
  const task = checkTask(args.task);
  const rows: PyDict[] = [];
  for (const [name, taskDir] of taskEntries(repo.runsDir, links)) {
    if (task !== null && name !== task) continue;
    for (const [attempt, , attemptDir] of attemptEntries(taskDir, links)) {
      const [state, stateAt] = readState(attemptDir);
      if (args.state !== null && state !== args.state) continue; // 先过滤再列举：过滤掉的不扫证据、链接不计数
      const files = evidence(attemptDir, links);
      if (files === null) continue;
      const summary = path.join(attemptDir, "summary.md");
      rows.push(new Map<string, PyValue>([
        ["task", name],
        ["attempt", attempt],
        ["state", state],
        ["state_at", stateAt],
        ["evidence_files", BigInt(files.length)],
        ["evidence_bytes", BigInt(files.reduce((sum, [, size]) => sum + size, 0))],
        ["has_summary", !isLinkOrJunction(summary) && isRegular(summary)],
      ]));
    }
  }
  if (args.json) {
    emitJson(out, new Map<string, PyValue>([["attempts", rows], ["skipped_links", BigInt(links.count)]]));
    return LOGS_EXIT_OK;
  }
  if (rows.length === 0) out.print(NO_ATTEMPT);
  for (const row of rows) {
    out.print(`${row.get("task") as string}/${row.get("attempt") as string}  ${row.get("state") as string}  ${
      (row.get("state_at") as string | null) || "无状态时间"}  证据 ${String(row.get("evidence_files"))} 个文件 / ${
      String(row.get("evidence_bytes"))} 字节  摘要：${row.get("has_summary") ? "有" : "无"}`);
  }
  if (links.count > 0) out.print(skippedLinksLine(links.count));
  return LOGS_EXIT_OK;
}

export interface ShowArgs {
  readonly repo: string | null;
  readonly target: string;
  readonly json: boolean;
}

/** kit_logs.cmd_show。 */
export function cmdShow(args: ShowArgs, out: PyOut): number {
  const repo = repoOf(args.repo);
  const [task, attempt, attemptDir] = resolveTarget(repo.runsDir, args.target);
  const links = new LinkTally();
  const [state, stateAt] = readState(attemptDir);
  const summary = summaryOf(attemptDir);
  const files = evidence(attemptDir, links);
  if (files === null) throw new LogsError(`无法列出 ${attemptDir}`, LOGS_EXIT_USAGE);
  if (args.json) {
    emitJson(out, new Map<string, PyValue>([
      ["task", task],
      ["attempt", attempt],
      ["state", state],
      ["state_at", stateAt],
      ["summary", summary === null ? null : new Map<string, PyValue>([
        ["bytes", BigInt(summary.bytes)],
        ["truncated", summary.truncated],
        ["text", summary.text],
      ])],
      ["evidence", files.map(([rel, size]) => new Map<string, PyValue>([["path", rel], ["bytes", BigInt(size)]]))],
      ["skipped_links", BigInt(links.count)],
    ]));
    return LOGS_EXIT_OK;
  }
  out.print(`${task}/${attempt}  状态 ${state}  状态时间 ${stateAt || "无"}`);
  if (summary === null) {
    out.print("摘要：无");
  } else {
    out.print(`摘要（${summary.bytes} 字节${summary.truncated ? "，已截断" : ""}）：`);
    out.print(summary.text);
    if (summary.truncated) out.print(`已截断：只显示前 ${MAX_SUMMARY_BYTES} 字节，共 ${summary.bytes} 字节`);
  }
  out.print(`证据 ${files.length} 个文件 / ${files.reduce((sum, [, size]) => sum + size, 0)} 字节：`);
  for (const [rel, size] of files) out.print(`  ${rel}  ${size} 字节`);
  if (links.count > 0) out.print(skippedLinksLine(links.count));
  return LOGS_EXIT_OK;
}
