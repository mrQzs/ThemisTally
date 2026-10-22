// kit_logs 的 logs usage（迁移第 ②c 步）：执行端各 attempt 的 token 用量（events-summary.json，B7.1），加规划端会话记录
// 里的用量下界（--transcript 给出的 Claude Code 会话记录，B7.2）。计数一律是 Python int（bigint）；时间按
// datetime.fromisoformat 的 C 实现解析（@themis/base/pydatetime）；会话记录逐行读、按消息 id 归组、去重与判冲突，
// 次序与 kit_logs 一致（id 按码点排序，按模型的行先无模型、再按模型名与是否子代理）。
import { readFileSync, statSync } from "node:fs";
import { parseIsoUtc } from "@themis/base/pydatetime";
import { type PyOut, pyRepr } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, PyJsonError, dumps, loads } from "@themis/base/pyjson";
import { isLinkOrJunction } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import {
  LinkTally,
  LogsError,
  LOGS_EXIT_OK,
  LOGS_EXIT_USAGE,
  attemptEntries,
  checkTask,
  emitJson,
  exists,
  isRegular,
  readJson,
  repoOf,
  scan,
  taskEntries,
  under,
} from "./logs.ts";

const USAGE_KEYS = ["input", "output", "cacheRead", "cacheWrite", "totalTokens"] as const;
const TOKEN_KEYS = ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"] as const;
const TRANSCRIPT_SUFFIX = ".jsonl";
const STRICT_UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

type Usage = Record<(typeof USAGE_KEYS)[number], bigint>;
type Status = "known" | "partial" | "unknown";

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isInt = (value: PyValue | undefined): value is bigint => typeof value === "bigint";
const zeroUsage = (): Usage => ({ input: 0n, output: 0n, cacheRead: 0n, cacheWrite: 0n, totalTokens: 0n });
const usageDict = (usage: Usage): PyDict => new Map<string, PyValue>(USAGE_KEYS.map((key) => [key, usage[key]]));

// --- 执行端 ----------------------------------------------------------------------

/** kit_logs._executor_row：(状态, requested_model, usage)；unknown 时 usage 为 null，不计入任何合计。 */
function executorRow(attemptDir: string, links: LinkTally): [Status, string | null, Usage | null] {
  const file = under(attemptDir, ["events-summary.json"]);
  if (isLinkOrJunction(file)) {
    links.hit();
    return ["unknown", null, null];
  }
  if (!isRegular(file)) return ["unknown", null, null];
  const data = readJson(file);
  if (!isDict(data)) return ["unknown", null, null];
  const requested = data.get("requested_model");
  let model: string | null = null;
  if (isDict(requested)) {
    const provider = requested.get("provider");
    const name = requested.get("model");
    if (typeof provider === "string" && typeof name === "string") model = `${provider}/${name}`;
  }
  const usage = data.get("usage");
  if (!isDict(usage)) return ["unknown", model, null];
  const values = zeroUsage();
  for (const key of USAGE_KEYS) {
    const value = usage.get(key);
    if (!isInt(value)) return ["unknown", model, null];
    values[key] = value;
  }
  const errors = data.get("parse_error_lines");
  if (data.get("complete") !== true || data.get("truncated") === true || !(Array.isArray(errors) && errors.length === 0)) {
    return ["partial", model, values];
  }
  return ["known", model, values];
}

function addUsage(target: Usage, values: Usage): void {
  for (const key of USAGE_KEYS) target[key] += values[key];
}

interface ModelGroup {
  readonly model: string | null;
  readonly counts: Record<Status, bigint>;
  readonly usage: Usage;
}

/** kit_logs._executor_stats。 */
function executorStats(runs: string, task: string | null): PyDict {
  const links = new LinkTally();
  const attempts: PyDict[] = [];
  const totals = zeroUsage();
  const counts: Record<Status, bigint> = { known: 0n, partial: 0n, unknown: 0n };
  const groups = new Map<string | null, ModelGroup>();
  for (const [name, taskDir] of taskEntries(runs, links)) {
    if (task !== null && name !== task) continue;
    for (const [attempt, , attemptDir] of attemptEntries(taskDir, links)) {
      const [status, model, values] = executorRow(attemptDir, links);
      counts[status] += 1n;
      if (values !== null) addUsage(totals, values);
      attempts.push(new Map<string, PyValue>([
        ["task", name],
        ["attempt", attempt],
        ["requested_model", model],
        ["status", status],
        ["usage", values === null ? null : usageDict(values)],
      ]));
      let group = groups.get(model);
      if (group === undefined) {
        group = { model, counts: { known: 0n, partial: 0n, unknown: 0n }, usage: zeroUsage() };
        groups.set(model, group);
      }
      group.counts[status] += 1n;
      if (values !== null) addUsage(group.usage, values);
    }
  }
  const byModel = [...groups.values()].sort((a, b) =>
    a.model === null || b.model === null ? Number(a.model !== null) - Number(b.model !== null) : cmpCodePoints(a.model, b.model));
  return new Map<string, PyValue>([
    ["attempts", attempts],
    ["totals", usageDict(totals)],
    ["counts", new Map<string, PyValue>([["known", counts.known], ["partial", counts.partial], ["unknown", counts.unknown]])],
    ["by_model", byModel.map((group) => new Map<string, PyValue>([
      ["requested_model", group.model],
      ["known", group.counts.known],
      ["partial", group.counts.partial],
      ["unknown", group.counts.unknown],
      ["usage", usageDict(group.usage)],
    ]))],
    ["skipped_links", BigInt(links.count)],
  ]);
}

// --- 规划端 ----------------------------------------------------------------------

/** 一条候选会话记录的规范值。计数缺失记 undefined（与 JSON 的 null 区分开）。 */
interface TranscriptRecord {
  readonly identifier: string;
  readonly final: boolean;
  readonly counts: readonly (PyValue | undefined)[];
  readonly model: string | null;
  readonly sidechain: boolean;
  readonly time: bigint | null;
}

type SkipReason = "bad_json" | "not_object" | "not_candidate";

/** kit_logs._canonical：计数按 json.dumps(sort_keys=True) 的文本比较（1 与 1.0 不同，null 与缺失不同）。 */
const canonical = (value: PyValue | undefined): string => (value === undefined ? "\0missing" : dumps(value, { sortKeys: true, ensureAscii: false }));

/** bytes.strip() 之后为空：只看 ASCII 的空白（空格、\t、\n、\r、\v、\f）。 */
function blank(line: Buffer): boolean {
  return line.every((byte) => byte === 0x20 || (byte >= 0x09 && byte <= 0x0d));
}

/** kit_logs._classify：一行 → (跳过原因, 记录)；空白行两样都是 null，不计入任何计数。 */
function classify(raw: Buffer): [SkipReason | null, TranscriptRecord | null] {
  let line = raw;
  if (line.at(-1) === 0x0a) line = line.subarray(0, -1);
  if (line.at(-1) === 0x0d) line = line.subarray(0, -1);
  if (blank(line)) return [null, null];
  let text: string;
  try {
    text = STRICT_UTF8.decode(line);
  } catch {
    return ["bad_json", null];
  }
  let obj: PyValue;
  try {
    obj = loads(text);
  } catch (error) {
    if (error instanceof PyJsonError) return ["bad_json", null]; // 深嵌套的一行同样是坏行（B11(c)）
    throw error;
  }
  if (!isDict(obj)) return ["not_object", null];
  const message = obj.get("message");
  if (!isDict(message)) return ["not_candidate", null];
  const identifier = message.get("id");
  if (typeof identifier !== "string" || identifier === "") return ["not_candidate", null];
  const usage = message.get("usage");
  if (!isDict(usage)) return ["not_candidate", null];
  const stop = message.get("stop_reason");
  const model = message.get("model");
  return [null, {
    identifier,
    final: typeof stop === "string" && stop !== "",
    counts: TOKEN_KEYS.map((key) => (usage.has(key) ? usage.get(key) : undefined)),
    model: typeof model === "string" ? model : null,
    sidechain: obj.get("isSidechain") === true,
    time: parseIsoUtc(obj.get("timestamp")),
  }];
}

/** 二进制模式的 readlines：每行带着结尾的换行（最后一行可以没有）。 */
function readLines(data: Buffer): Buffer[] {
  const lines: Buffer[] = [];
  let start = 0;
  while (start < data.length) {
    const at = data.indexOf(0x0a, start);
    const end = at < 0 ? data.length : at + 1;
    lines.push(data.subarray(start, end));
    start = end;
  }
  return lines;
}

/** kit_logs._read_transcript：读不出来时整个文件都不计入，返回 false。 */
function readTranscript(file: string, groups: Map<string, TranscriptRecord[]>, skipped: Record<SkipReason, bigint>): boolean {
  let data: Buffer;
  try {
    data = readFileSync(file);
  } catch {
    return false;
  }
  const local: Record<SkipReason, bigint> = { bad_json: 0n, not_object: 0n, not_candidate: 0n };
  const pending = new Map<string, TranscriptRecord[]>();
  for (const raw of readLines(data)) {
    const [reason, record] = classify(raw);
    if (reason !== null) {
      local[reason] += 1n;
    } else if (record !== null) {
      const list = pending.get(record.identifier);
      if (list === undefined) pending.set(record.identifier, [record]);
      else list.push(record);
    }
  }
  for (const key of ["bad_json", "not_object", "not_candidate"] as const) skipped[key] += local[key];
  for (const [identifier, records] of pending) {
    const list = groups.get(identifier);
    if (list === undefined) groups.set(identifier, [...records]);
    else list.push(...records);
  }
  return true;
}

/** os.path.isdir：跟随链接。 */
function isDirFollow(value: string): boolean {
  try {
    return statSync(value).isDirectory();
  } catch {
    return false;
  }
}

/** kit_logs._transcript_files：目录只取直接一层的 .jsonl，否则读路径本身；目录列不出来为 null（B11(b)）。 */
function transcriptFiles(target: string, links: { count: bigint }): string[] | null {
  if (!isDirFollow(target)) return [target];
  const entries = scan(target);
  if (entries === null) return null;
  const found: string[] = [];
  for (const [name, child] of entries) {
    if (!name.endsWith(TRANSCRIPT_SUFFIX)) continue;
    if (isLinkOrJunction(child)) {
      links.count += 1n;
      continue;
    }
    if (!isRegular(child)) continue;
    found.push(child);
  }
  return found;
}

/** kit_logs._conflicted：组内任意两条的 model 或 sidechain 不同；或最终记录之间四个计数任一不同。 */
function conflicted(records: readonly TranscriptRecord[], finals: readonly TranscriptRecord[]): boolean {
  for (let index = 0; index < records.length; index += 1) {
    for (const other of records.slice(index + 1)) {
      const record = records[index] as TranscriptRecord;
      if (record.model !== other.model || record.sidechain !== other.sidechain) return true;
    }
  }
  for (let index = 0; index < finals.length; index += 1) {
    for (const other of finals.slice(index + 1)) {
      const record = finals[index] as TranscriptRecord;
      if (record.counts.some((value, at) => canonical(value) !== canonical(other.counts[at]))) return true;
    }
  }
  return false;
}

interface PlannerRow {
  readonly model: string | null;
  readonly sidechain: boolean;
  messages: bigint;
  readonly tokens: bigint[];
}

/** kit_logs._planner_stats。 */
function plannerStats(paths: readonly string[], since: bigint | null, until: bigint | null): PyDict {
  const skipped: Record<SkipReason, bigint> = { bad_json: 0n, not_object: 0n, not_candidate: 0n };
  const links = { count: 0n };
  let unreadable = 0n;
  const groups = new Map<string, TranscriptRecord[]>();
  for (const target of paths) {
    const files = transcriptFiles(target, links);
    if (files === null) {
      unreadable += 1n; // 目录型参数列不出来：不中止，计入不可读文件并标部分（B11(b)）
      continue;
    }
    for (const file of files) {
      if (!readTranscript(file, groups, skipped)) unreadable += 1n;
    }
  }
  const n = { duplicate: 0n, conflictIds: 0n, conflictRecords: 0n, incomplete: 0n, intermediate: 0n, unusable: 0n, noTime: 0n,
    outside: 0n, nonInteger: 0n, included: 0n };
  const rows = new Map<string, PlannerRow>();
  for (const identifier of [...groups.keys()].sort(cmpCodePoints)) {
    const records = groups.get(identifier) as TranscriptRecord[];
    const finals = records.filter((record) => record.final);
    n.intermediate += BigInt(records.length - finals.length);
    n.unusable += BigInt(records.filter((record) => record.time === null).length);
    if (conflicted(records, finals)) {
      n.conflictIds += 1n;
      n.conflictRecords += BigInt(records.length);
      continue;
    }
    if (finals.length === 0) {
      n.incomplete += 1n;
      continue;
    }
    n.duplicate += BigInt(finals.length - 1);
    const times = records.flatMap((record) => (record.time === null ? [] : [record.time]));
    if (times.length === 0) {
      n.noTime += 1n;
      continue;
    }
    const moment = times.reduce((a, b) => (b < a ? b : a));
    if ((since !== null && moment < since) || (until !== null && moment >= until)) {
      n.outside += 1n;
      continue;
    }
    n.included += 1n;
    const first = finals[0] as TranscriptRecord;
    const key = `${first.model === null ? "0" : `1${first.model}`}\0${first.sidechain ? 1 : 0}`;
    let row = rows.get(key);
    if (row === undefined) {
      row = { model: first.model, sidechain: first.sidechain, messages: 0n, tokens: TOKEN_KEYS.map(() => 0n) };
      rows.set(key, row);
    }
    row.messages += 1n;
    first.counts.forEach((value, at) => {
      if (isInt(value)) row.tokens[at] = (row.tokens[at] as bigint) + value;
      else n.nonInteger += 1n;
    });
  }
  const byModel = [...rows.values()].sort((a, b) => {
    if ((a.model === null) !== (b.model === null)) return a.model === null ? -1 : 1;
    const byName = cmpCodePoints(a.model ?? "", b.model ?? "");
    return byName !== 0 ? byName : Number(a.sidechain) - Number(b.sidechain);
  });
  return new Map<string, PyValue>([
    ["lower_bound", true],
    ["partial", Boolean(n.conflictIds || n.incomplete || unreadable)],
    ["included_messages", n.included],
    ["by_model", byModel.map((row) => new Map<string, PyValue>([
      ["model", row.model],
      ["sidechain", row.sidechain],
      ["messages", row.messages],
      ...TOKEN_KEYS.map((key, at) => [key, row.tokens[at] as bigint] as [string, PyValue]),
    ]))],
    ["skipped_lines", new Map<string, PyValue>([["bad_json", skipped.bad_json], ["not_object", skipped.not_object], ["not_candidate", skipped.not_candidate]])],
    ["skipped_links", links.count],
    ["unreadable_files", unreadable],
    ["duplicate_records", n.duplicate],
    ["conflict_ids", n.conflictIds],
    ["conflict_records", n.conflictRecords],
    ["incomplete_ids", n.incomplete],
    ["intermediate_records", n.intermediate],
    ["unusable_timestamps", n.unusable],
    ["ids_without_time", n.noTime],
    ["outside_window_ids", n.outside],
    ["non_integer_fields", n.nonInteger],
  ]);
}

// --- 命令 ------------------------------------------------------------------------

/** kit_logs._cli_time。 */
function cliTime(text: string, option: string): bigint {
  const moment = parseIsoUtc(text);
  if (moment === null) {
    throw new LogsError(`${option} 需要带时区的 ISO 8601 时间（例如 2026-10-17T10:00:00Z）：${pyRepr(text)}`, LOGS_EXIT_USAGE);
  }
  return moment;
}

export interface UsageArgs {
  readonly repo: string | null;
  readonly task: string | null;
  readonly transcript: readonly string[] | null;
  readonly since: string | null;
  readonly until: string | null;
  readonly json: boolean;
}

const get = (dict: PyDict, key: string): PyValue => dict.get(key) as PyValue;
const num = (dict: PyDict, key: string): string => String(get(dict, key));
const usageText = (usage: PyDict): string =>
  `input=${num(usage, "input")} output=${num(usage, "output")} cacheRead=${num(usage, "cacheRead")} cacheWrite=${
    num(usage, "cacheWrite")} totalTokens=${num(usage, "totalTokens")}`;

/** kit_logs.cmd_usage。 */
export function cmdUsage(args: UsageArgs, out: PyOut): number {
  const repo = repoOf(args.repo);
  const task = checkTask(args.task);
  const since = args.since !== null ? cliTime(args.since, "--since") : null;
  const until = args.until !== null ? cliTime(args.until, "--until") : null;
  if (since !== null && until !== null && since > until) throw new LogsError("--since 晚于 --until", LOGS_EXIT_USAGE);
  const transcripts = [...(args.transcript ?? [])];
  for (const text of transcripts) {
    if (!exists(text)) throw new LogsError(`--transcript 路径不存在：${text}`, LOGS_EXIT_USAGE);
  }
  const executor = executorStats(repo.runsDir, task);
  const planner = transcripts.length > 0 ? plannerStats(transcripts, since, until) : null;
  if (args.json) {
    emitJson(out, new Map<string, PyValue>([["executor", executor], ["planner", planner]]));
    return LOGS_EXIT_OK;
  }
  const attempts = get(executor, "attempts") as PyDict[];
  const counts = get(executor, "counts") as PyDict;
  out.print(`执行端：attempt ${attempts.length} 个 · known ${num(counts, "known")} · partial ${num(counts, "partial")} · unknown ${
    num(counts, "unknown")} · 跳过的链接 ${num(executor, "skipped_links")}`);
  for (const row of attempts) {
    const usage = get(row, "usage");
    const detail = usage === null ? "unknown（没有可用的 usage）" : `${get(row, "status") as string}  ${usageText(usage as PyDict)}`;
    out.print(`  ${get(row, "task") as string}/${get(row, "attempt") as string}  ${(get(row, "requested_model") as string | null) || "（无模型）"}  ${detail}`);
  }
  out.print(`  合计 ${usageText(get(executor, "totals") as PyDict)}`);
  out.print("  按模型：");
  for (const group of get(executor, "by_model") as PyDict[]) {
    out.print(`    ${(get(group, "requested_model") as string | null) || "（无模型）"}  known=${num(group, "known")} partial=${
      num(group, "partial")} unknown=${num(group, "unknown")}  ${usageText(get(group, "usage") as PyDict)}`);
  }
  if (planner === null) {
    out.print("规划端：未给 --transcript，未统计规划端");
    return LOGS_EXIT_OK;
  }
  const skipped = get(planner, "skipped_lines") as PyDict;
  out.print(`规划端（下界：只统计命令行给出的会话记录，只数会话记录里有的调用）${
    get(planner, "partial") ? "，部分（有冲突、未完成或读不出的文件）" : ""}：计入消息 ${num(planner, "included_messages")} · 重复最终记录 ${
    num(planner, "duplicate_records")} · 中间记录 ${num(planner, "intermediate_records")}`);
  out.print(`  冲突 ${num(planner, "conflict_ids")} 组 / ${num(planner, "conflict_records")} 条 · 未完成 ${num(planner, "incomplete_ids")} 组 · 无可用时间 ${
    num(planner, "ids_without_time")} · 窗口外 ${num(planner, "outside_window_ids")} · 非整数字段 ${num(planner, "non_integer_fields")} · 不可读文件 ${
    num(planner, "unreadable_files")} · 跳过的链接 ${num(planner, "skipped_links")}`);
  out.print(`  坏行 ${num(skipped, "bad_json")} · 不是对象 ${num(skipped, "not_object")} · 不是候选记录 ${num(skipped, "not_candidate")} · 不可用时间戳 ${
    num(planner, "unusable_timestamps")}`);
  out.print("  按模型：");
  for (const row of get(planner, "by_model") as PyDict[]) {
    out.print(`    ${(get(row, "model") as string | null) || "（无模型）"}  ${get(row, "sidechain") ? "子代理" : "主线"}  messages=${
      num(row, "messages")}  input_tokens=${num(row, "input_tokens")} cache_creation_input_tokens=${
      num(row, "cache_creation_input_tokens")} cache_read_input_tokens=${num(row, "cache_read_input_tokens")} output_tokens=${
      num(row, "output_tokens")}`);
  }
  return LOGS_EXIT_OK;
}
