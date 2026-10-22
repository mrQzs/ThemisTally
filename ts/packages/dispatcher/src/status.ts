// pi_dispatch status（迁移第 ②a 步）：_attempt_row、_live_facts、resolve_run_dir、task_attempts、cmd_status。
// --assess 要调决策模型，留在 Python（启动器不转交带 --assess 的调用）。
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { PyCrash, type PyOut, pyGet, pyLenValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { displayPath, firstLinkComponent, isLinkOrJunction, isWithin, pyResolve } from "@themis/base/pypath";
import { D, PY_END, cmpCodePoints, codePoints, pyIntParse, pyRegex } from "@themis/base/pyre";
import { DispatchError, EXIT_OK, EXIT_USAGE, Repo, readJsonOr } from "./repo.ts";

export const TASK_ID_RE = pyRegex(`^[a-z0-9][a-z0-9-]{0,63}${PY_END}`);
export const ATTEMPT_DIR_RE = pyRegex(`^attempt-(?<n>${D}{3,})${PY_END}`);
export const PLAN_KEY_RE = pyRegex(`^(?<task>[a-z0-9][a-z0-9-]{0,63})\\.v(?<ver>[1-9][0-9]{0,3})${PY_END}`);
const NUMBERED_RE = pyRegex(`^${D}{2,}(?:\\.json|\\.md)?${PY_END}`);
const LEADING_DIGITS_RE = pyRegex(`^(${D}+)`);

/** pi_dispatch.LONG_THINKING_DELTAS。 */
const LONG_THINKING_DELTAS = 6000;

function isDir(value: string): boolean {
  try {
    return statSync(value).isDirectory();
  } catch {
    return false;
  }
}

function isFile(value: string): boolean {
  try {
    return statSync(value).isFile();
  } catch {
    return false;
  }
}

/** Path.iterdir()：目录里的条目，按操作系统给的顺序。 */
function iterdir(directory: string): string[] {
  return readdirSync(directory).map((name) => path.join(directory, name));
}

function intOf(text: string): bigint {
  const value = pyIntParse(text);
  if (value === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: ${JSON.stringify(text)}`);
  return value;
}

/** Python 的 ==：int、float、bool 之间按数值比较。 */
function pyNumberEquals(value: PyValue, wanted: bigint): boolean {
  if (typeof value === "bigint") return value === wanted;
  if (typeof value === "number") return value === Number(wanted);
  if (typeof value === "boolean") return BigInt(value ? 1 : 0) === wanted;
  return false;
}

/** sorted(items, key=…)：稳定排序（Python 的 sorted 也稳定）。 */
function sortedBy<T>(items: readonly T[], key: (item: T) => bigint): T[] {
  return items
    .map((item, index) => ({ item, index, key: key(item) }))
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.index - b.index))
    .map((entry) => entry.item);
}

/** pi_dispatch.get_state。 */
export function getState(runDir: string): string {
  return pyStrValue(pyGet(readJsonOr(path.join(runDir, "state.json"), new Map()), "state", "UNKNOWN"));
}

/** pi_dispatch.task_attempts：attempt-NNN 目录（跟随链接），按编号整数升序。 */
export function taskAttempts(repo: Repo, taskId: string): string[] {
  const base = path.join(repo.runsDir, taskId);
  if (!isDir(base)) return [];
  const found = iterdir(base).filter((entry) => isDir(entry) && ATTEMPT_DIR_RE.test(path.basename(entry)));
  return sortedBy(found, (entry) => intOf(ATTEMPT_DIR_RE.exec(path.basename(entry))?.groups?.["n"] ?? ""));
}

/** pi_dispatch._latest_numbered：名字是两位以上数字（可带 .json、.md）的条目里编号最大的；并列取先遇到的。 */
function latestNumbered(directory: string): string | null {
  if (!isDir(directory)) return null;
  let best: string | null = null;
  let bestNumber = 0n;
  for (const entry of iterdir(directory)) {
    if (!NUMBERED_RE.test(path.basename(entry))) continue;
    const number = intOf(LEADING_DIGITS_RE.exec(path.basename(entry))?.[1] ?? "");
    if (best === null || number > bestNumber) {
      best = entry;
      bestNumber = number;
    }
  }
  return best;
}

/** Path.glob("*.json") 在 Windows 上不分大小写，* 也匹配点开头的名字。 */
function globJson(directory: string): string[] {
  const pattern = process.platform === "win32" ? /\.json$/iu : /\.json$/u;
  return iterdir(directory).filter((entry) => pattern.test(path.basename(entry)));
}

/** Path.stem。 */
function stem(entry: string): string {
  const name = path.basename(entry);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

/** pi_dispatch.latest_verdict。 */
function latestVerdict(runDir: string): PyValue {
  const directory = path.join(runDir, "verdicts");
  if (!isDir(directory)) return new Map();
  const files = sortedBy(globJson(directory), (entry) => intOf(stem(entry)));
  return files.length > 0 ? readJsonOr(files[files.length - 1] as string, new Map()) : new Map();
}

/** pi_dispatch._attempt_row。键的次序就是输出的次序。 */
function attemptRow(repo: Repo, runDir: string): PyDict {
  const meta = readJsonOr(path.join(runDir, "meta.json"), new Map());
  const run = readJsonOr(path.join(runDir, "run.json"), new Map());
  const events = readJsonOr(path.join(runDir, "events-summary.json"), new Map());
  const scope = readJsonOr(path.join(runDir, "scope.json"), new Map());
  const latest = latestNumbered(path.join(runDir, "checks"));
  const checks = latest ? readJsonOr(path.join(latest, "checks.json"), new Map()) : new Map();
  const results = pyGet(checks, "results", []);
  const verdict = latestVerdict(runDir);
  const cost = pyTruthy(pyGet(events, "cost")) ? pyGet(events, "cost") : new Map();
  let checksText = "-";
  if (pyTruthy(results)) {
    const items = iterate(results);
    const passed = items.filter((item) => pyTruthy(pyGet(item, "passed"))).length;
    checksText = `${passed}/${pyLenValue(results)}`;
  }
  const usage = pyTruthy(pyGet(events, "usage")) ? pyGet(events, "usage") : new Map();
  return new Map<string, PyValue>([
    ["attempt", displayPath(runDir, repo.runsDir)],
    ["task_id", pyGet(meta, "task_id")],
    ["plan_version", pyGet(meta, "plan_version")],
    ["attempt_no", pyGet(meta, "attempt_no")],
    ["state", getState(runDir)],
    ["started", isDir(path.join(runDir, "claim"))],
    ["exit_code", pyGet(run, "exit_code")],
    ["wall_seconds", pyGet(run, "wall_seconds")],
    ["events_ok", pyGet(events, "ok")],
    ["violations", pyTruthy(scope) ? BigInt(pyLenValue(pyGet(scope, "violations", []))) : null],
    ["checks", checksText],
    ["check_mode", pyGet(checks, "mode")],
    ["verdict", pyGet(verdict, "verdict")],
    ["failure_class", pyGet(verdict, "failure_class")],
    ["human_minutes", pyGet(verdict, "human_minutes")],
    ["tokens", pyGet(usage, "totalTokens")],
    ["cost", pyGet(cost, "total")],
    ["cost_status", pyTruthy(events) ? pyGet(cost, "status") : null],
  ]);
}

/** for item in value：list 逐项，dict 逐键，str 逐字符；别的类型照 Python 报 TypeError。 */
function iterate(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return value;
  if (value instanceof Map) return [...value.keys()] as PyValue[];
  if (typeof value === "string") return codePoints(value);
  throw new PyCrash("TypeError", `'${typeof value}' object is not iterable`);
}

// --- live ---------------------------------------------------------------------

/** _strptime 对 "%Y-%m-%dT%H:%M:%SZ" 编出的正则（re.IGNORECASE，\d 认 Unicode 数字）。 */
const STRPTIME_RE = new RegExp(
  `^(?<Y>${D}${D}${D}${D})-(?<m>1[0-2]|0[1-9]|[1-9])-(?<d>3[01]|[12]${D}|0[1-9]|[1-9]| [1-9])` +
    `T(?<H>2[0-3]|[0-1]${D}|${D}):(?<M>[0-5]${D}|${D}):(?<S>6[0-1]|[0-5]${D}|${D})Z`,
  "iu",
);

/** datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")，当作 UTC，返回毫秒；不合法（含 datetime 的取值检查）为 null。 */
function strptimeUtc(text: string): number | null {
  const match = STRPTIME_RE.exec(text);
  if (!match || match[0].length !== text.length) return null;
  const part = (name: string): number => Number(intOf(match.groups?.[name] ?? ""));
  const [year, month, day, hour, minute, second] = ["Y", "m", "d", "H", "M", "S"].map(part) as number[];
  if ((year as number) < 1 || (second as number) > 59) return null;
  const date = new Date(0);
  date.setUTCFullYear(year as number, (month as number) - 1, day as number);
  if (date.getUTCMonth() !== (month as number) - 1) return null; // 2 月 30 日之类：datetime 报 ValueError
  date.setUTCHours(hour as number, minute as number, second as number, 0);
  return date.getTime();
}

function countBytes(data: Buffer, needle: Buffer, from = 0): number {
  let count = 0;
  for (let at = data.indexOf(needle, from); at >= 0; at = data.indexOf(needle, at + needle.length)) count += 1;
  return count;
}

/** pi_dispatch._live_facts：只读事件文件、不解析 JSON。 */
function liveFacts(runDir: string): PyDict {
  let data: Buffer;
  try {
    data = readFileSync(path.join(runDir, "events.jsonl"));
  } catch {
    data = Buffer.alloc(0);
  }
  const started = pyGet(readJsonOr(path.join(runDir, "run-started.json"), new Map()), "started_at");
  let elapsed: bigint | null = null;
  if (pyTruthy(started)) {
    if (typeof started !== "string") throw new PyCrash("TypeError", "strptime() argument 1 must be str");
    const begin = strptimeUtc(started);
    if (begin !== null) elapsed = BigInt(Math.trunc((Date.now() - begin) / 1000));
  }
  const marker = Buffer.from('"type":"tool_execution_end"');
  const lastTool = data.lastIndexOf(marker);
  const deltas = countBytes(data, Buffer.from('"type":"message_update"'), lastTool >= 0 ? lastTool : 0);
  return new Map<string, PyValue>([
    ["tool_calls", BigInt(countBytes(data, marker))],
    ["elapsed_seconds", elapsed],
    ["deltas_since_last_tool", BigInt(deltas)],
    ["long_idle", deltas >= LONG_THINKING_DELTAS],
  ]);
}

/** pi_dispatch._live_text。 */
function liveText(facts: PyDict): string {
  const elapsed = facts.get("elapsed_seconds");
  const quiet = facts.get("long_idle") ? ` 长时间没有工具调用（${String(facts.get("deltas_since_last_tool"))} 个增量）` : "";
  return `live:${String(facts.get("tool_calls"))}t${elapsed !== null && elapsed !== undefined ? ` ${String(elapsed)}s` : ""}${quiet}`;
}

// --- 目标解析 -------------------------------------------------------------------

function relPosix(child: string, root: string): string {
  return path.relative(root, child).split(path.sep).join("/");
}

/** pi_dispatch.resolve_run_dir：attempt 路径、task-id/attempt-NNN、task-id 或 task-id.vN（取最新 attempt）。 */
export function resolveRunDir(repo: Repo, value: string): string {
  const candidates = [value, path.resolve(repo.runsDir, value)]; // pathlib 的 /：右边是绝对路径时取右边
  const key = PLAN_KEY_RE.exec(value);
  const taskId = key ? (key.groups?.["task"] ?? null) : TASK_ID_RE.test(value) ? value : null;
  for (const candidate of candidates) {
    if (isFile(path.join(candidate, "meta.json"))) {
      const resolved = pyResolve(candidate);
      if (!isWithin(resolved, repo.runsDir)) throw new DispatchError(`attempt 目录必须位于 ${repo.runsDir} 下`, EXIT_USAGE);
      return resolved;
    }
  }
  if (taskId) {
    let link = firstLinkComponent(repo.runsDir, taskId);
    let attempts = link ? [] : taskAttempts(repo, taskId);
    if (key) {
      link = link ?? attempts.filter((attempt) => isLinkOrJunction(attempt)).map((attempt) => relPosix(attempt, repo.runsDir))[0] ?? null;
      const version = BigInt(key.groups?.["ver"] ?? "0");
      attempts = link
        ? []
        : attempts.filter((attempt) => pyNumberEquals(pyGet(readJsonOr(path.join(attempt, "meta.json"), new Map()), "plan_version"), version));
    } else if (attempts.length > 0 && isLinkOrJunction(attempts[attempts.length - 1] as string)) {
      link = relPosix(attempts[attempts.length - 1] as string, repo.runsDir);
    }
    if (link) throw new DispatchError(`attempt 目录经过链接或 junction，不跟随：${path.join(repo.runsDir, link)}`, EXIT_USAGE);
    if (attempts.length > 0) {
      const resolved = pyResolve(attempts[attempts.length - 1] as string);
      if (!isWithin(resolved, repo.runsDir)) throw new DispatchError(`attempt 目录必须位于 ${repo.runsDir} 下`, EXIT_USAGE);
      return resolved;
    }
  }
  throw new DispatchError(`找不到 attempt：${value}`, EXIT_USAGE);
}

// --- 命令 -----------------------------------------------------------------------

export interface StatusArgs {
  readonly repo: string | null;
  readonly task_id: string | null;
  readonly json: boolean;
}

function formatCost(row: PyDict): string {
  const status = row.get("cost_status") as PyValue;
  if (status === null) return "-";
  const cost = row.get("cost") as PyValue;
  if (cost === null) return "unknown";
  return `${pyStrValue(cost)}(${pyStrValue(status)})`;
}

function ljust(text: string, width: number): string {
  return text + " ".repeat(Math.max(0, width - codePoints(text).length));
}

/** pi_dispatch.cmd_status（不带 --assess）。 */
export function cmdStatus(args: StatusArgs, out: PyOut): number {
  const repo = Repo.discover(args.repo);
  const target = args.task_id;
  let attempts: string[];
  if (target && !TASK_ID_RE.test(target)) {
    attempts = [resolveRunDir(repo, target)];
  } else {
    const tasks = target
      ? [target]
      : isDir(repo.runsDir)
        ? iterdir(repo.runsDir).filter(isDir).map((entry) => path.basename(entry)).sort(cmpCodePoints)
        : [];
    attempts = tasks.flatMap((task) => taskAttempts(repo, task));
  }
  const rows = attempts.map((attempt) => attemptRow(repo, attempt));
  rows.forEach((row, index) => {
    if (row.get("state") === "RUNNING") {
      const facts = liveFacts(attempts[index] as string);
      row.set("events_ok", liveText(facts));
      row.set("live", facts);
    }
  });
  if (args.json) {
    out.print(dumps(rows, { ensureAscii: false, indent: 2 }));
    return EXIT_OK;
  }
  if (rows.length === 0) {
    out.print("没有 attempt 记录。");
    return EXIT_OK;
  }
  const header = ["ATTEMPT", "STATE", "EXIT", "EVENTS", "VIOL", "CHECKS", "VERDICT", "WALL(s)", "COST"];
  const table = [header, ...rows.map((row) => [
    pyStrValue(row.get("attempt") as PyValue),
    pyStrValue(row.get("state") as PyValue),
    pyStrValue(row.get("exit_code") as PyValue),
    pyStrValue(row.get("events_ok") as PyValue),
    pyStrValue(row.get("violations") as PyValue),
    pyStrValue(row.get("checks") as PyValue),
    pyTruthy(row.get("verdict")) ? pyStrValue(row.get("verdict") as PyValue) : "-",
    pyTruthy(row.get("wall_seconds")) ? pyStrValue(row.get("wall_seconds") as PyValue) : "-",
    formatCost(row),
  ])];
  const widths = header.map((_, column) => Math.max(...table.map((line) => codePoints(line[column] as string).length)));
  for (const line of table) out.print(line.map((cell, column) => ljust(cell, widths[column] as number)).join("  "));
  return EXIT_OK;
}

