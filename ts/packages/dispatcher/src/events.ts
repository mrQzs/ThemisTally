// pi_dispatch 的事件流摘要（迁移第 ④b6 片）：summarize_events、extract_report、review_hints 与它们的小助手。
// 三份输出的 JSON 字节是 Python 与 TS 之间的契约（混合期 hub 仍是 Python，读这些文件）：键的次序、int 与 float 之分、
// 码点下标、按码点排序都照 Python。正则原文来自生成的 event-patterns.ts。
import { closeSync, openSync, readSync } from "node:fs";
import path from "node:path";
import { pyAdd, pyGet, pyItem, pyJoinStrings, pyPositive, pyRepr, pyReprValue, pyRound, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorOf, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { expanduser, isWithin, purePathIsAbsolute, purePathStr, pyExists, pyResolve } from "@themis/base/pypath";
import { compilePy, toPoints } from "@themis/base/pyregex";
import { cmpCodePoints, codePoints, isSpace, pyLower, pySplit, pySplitlines, pyStrip } from "@themis/base/pyre";
import { redactSecrets, stripAnsi } from "@themis/base/secrets";
import { EVENT_PATTERNS as P, STDERR_WARNING_PATTERNS } from "./event-patterns.ts";
import { writeJson, writeText } from "./evidence.ts";
import {
  DELETE_LABEL,
  SUSPICIOUS,
  cacheDirCleanup,
  isCheckCommand,
  maskPaths,
  maskedExitMention,
  matchExcerpt,
  outsideMentions,
  pathForms,
  protectedMentions,
  tempDirWithoutCleanup,
  tempPathMatches,
} from "./shell-scan.ts";

export const USAGE_KEYS = ["input", "output", "cacheRead", "cacheWrite", "totalTokens"] as const;
const WORK_EVENTS = ["agent_start", "turn_start", "message_start", "tool_execution_start"];
const NL = String.fromCharCode(10);
const CR = String.fromCharCode(13);
/** review_hints 最多读这么多字节；读满（恰好等于也算）就标截断。 */
const HINT_LIMIT = 20 * 1024 * 1024;

const AMBIGUITY = compilePy(P.AMBIGUITY_RE);
const NEGATION = compilePy(P.AMBIGUITY_NEGATION_RE);
const DOUBLE_NEGATION = compilePy(P.AMBIGUITY_DOUBLE_NEGATION_RE);
const RESOLVED = compilePy(P.AMBIGUITY_RESOLVED_RE);
const CONTEXT = compilePy(P.AMBIGUITY_CONTEXT_RE);
const INTERPRETATION = compilePy(P.INTERPRETATION_RE);
const SKIP_HEADING = compilePy(P.SKIP_HEADING);
const TEXTUAL_TOOL_CALL = compilePy(P.TEXTUAL_TOOL_CALL_RE);
const SKIP_MARKER = compilePy(P.SKIP_MARKER_RE);
const ASSERT = compilePy(P.ASSERT_RE);
const STDERR_FLAGS = STDERR_WARNING_PATTERNS.map(([name, pattern]) => [name, compilePy(pattern)] as const);
/** 不带 BOM 处理的宽松解码：bytes.decode("utf-8", "replace")（开头的 BOM 照 Python 留成 U+FEFF）。 */
const REPLACE_DECODER = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const get = (dict: PyDict, key: string): PyValue => dict.get(key) ?? null;
const dictOr = (value: PyValue): PyDict => (isDict(value) ? value : new Map());
const isNumber = (value: PyValue): value is bigint | number | boolean =>
  typeof value === "bigint" || typeof value === "number" || typeof value === "boolean";
const firstPoints = (text: string, count: number): string => codePoints(text).slice(0, count).join("");
const record = (pairs: [string, PyValue][]): PyDict => new Map(pairs);

/** _add_usage：int、float 与 bool 都累加（bool 是 int）；有正的费用就加进 cost_total，否则有 token 的记一次“没有价格”。 */
function addUsage(totals: PyDict, usage: PyValue): void {
  if (!isDict(usage)) return;
  for (const key of USAGE_KEYS) {
    const value = get(usage, key);
    if (isNumber(value)) totals.set(key, pyAdd(totals.get(key) as PyValue, value));
  }
  const cost = get(usage, "cost");
  const total = isDict(cost) ? get(cost, "total") : null;
  if (isNumber(total) && pyPositive(total)) totals.set("cost_total", pyAdd(totals.get("cost_total") as PyValue, total));
  else if (pyPositive(get(usage, "totalTokens"))) totals.set("priced_missing", (totals.get("priced_missing") as bigint) + 1n);
}

/** _message_text：content 是字符串时就是它；是列表时把 type 为 text 的块的 text 用换行连起来。 */
export function messageText(message: PyDict): string {
  const content = get(message, "content");
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  const parts = content.filter((part) => isDict(part) && get(part, "type") === "text").map((part) => pyGet(part, "text", ""));
  return pyJoinStrings(NL, parts);
}

/** re.split(r"(?m)^(?=## )", text)：在行首的 "## " 前切开；开头就是时先交出一个空段（Python 3.7 起的空匹配切分）。 */
function headingSections(text: string): string[] {
  const sections: string[] = [];
  let last = 0;
  for (let index = 0; index + 3 <= text.length; index += 1) {
    if ((index === 0 || text[index - 1] === NL) && text.startsWith("## ", index)) {
      sections.push(text.slice(last, index));
      last = index;
    }
  }
  sections.push(text.slice(last));
  return sections;
}

/** ambiguity_domain_words：停止条件与禁止事项之外出现两次及以上的“歧义”类词，算合同自己的领域用语。 */
export function ambiguityDomainWords(planText: string): string[] {
  const body = headingSections(planText).filter((section) => SKIP_HEADING.match(section) === null).join(NL);
  const counts = new Map<string, number>();
  for (const match of AMBIGUITY.finditer(body)) {
    const key = pyLower(match.group);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts].filter(([, count]) => count >= 2).map(([key]) => key).sort(cmpCodePoints);
}

/** 一条消息里要扫的正文与推理：（块的 type, 文字）。content 是字符串时当作一个 text 块。 */
function messageBodies(message: PyDict): [string, string][] {
  const content = get(message, "content");
  const blocks = typeof content === "string" ? [record([["type", "text"], ["text", content]])] : content;
  if (!Array.isArray(blocks)) return [];
  const bodies: [string, string][] = [];
  for (const block of blocks) {
    if (!isDict(block)) continue;
    const kind = get(block, "type");
    const body = kind === "text" ? get(block, "text") : kind === "thinking" ? get(block, "thinking") : null;
    if (typeof body === "string") bodies.push([kind as string, body]);
  }
  return bodies;
}

function mention(lineNo: number, kind: string, keyword: string, points: Int32Array, start: number, end: number): PyDict {
  const excerpt = firstPoints(pySplit(String.fromCodePoint(...points.subarray(start, end))).join(" "), 260);
  return record([["line", BigInt(lineNo)], ["kind", kind], ["keyword", keyword], ["excerpt", excerpt]]);
}

/** ambiguity_mentions：正文与推理里“歧义 / 矛盾”一类说法的摘录；否定的、紧跟否定答案的、附近不提合同的、领域用语都不算。 */
export function ambiguityMentions(message: PyDict, lineNo: number, skipWords: readonly string[] = []): PyDict[] {
  const skip = new Set(skipWords.map((word) => pyLower(word)));
  const found: PyDict[] = [];
  for (const [kind, body] of messageBodies(message)) {
    const points = toPoints(body);
    const slice = (start: number, end: number): Int32Array => points.subarray(Math.max(0, start), Math.min(points.length, end));
    let covered = -1;
    for (const match of AMBIGUITY.finditer(points)) {
      if (match.start < covered || skip.has(pyLower(match.group))) continue;
      const negated =
        NEGATION.search(slice(match.start - 24, match.start)) !== null && DOUBLE_NEGATION.search(slice(match.start - 80, match.start)) === null;
      if (negated || RESOLVED.search(slice(match.end, match.end + 80)) !== null) continue;
      if (CONTEXT.search(slice(match.start - 240, match.end + 240)) === null) continue;
      const start = Math.max(0, match.start - 100);
      const end = Math.min(points.length, match.end + 140);
      covered = end;
      found.push(mention(lineNo, kind, match.group, points, start, end));
    }
  }
  return found;
}

/** interpretation_mentions：执行器自己宣布裁定的短语；同一段里相邻的只记一次。 */
export function interpretationMentions(message: PyDict, lineNo: number): PyDict[] {
  const found: PyDict[] = [];
  for (const [kind, body] of messageBodies(message)) {
    const points = toPoints(body);
    let covered = -1;
    for (const match of INTERPRETATION.finditer(points)) {
      if (match.start < covered) continue;
      const start = Math.max(0, match.start - 100);
      const end = Math.min(points.length, match.end + 140);
      covered = end;
      found.push(mention(lineNo, kind, match.group, points, start, end));
    }
  }
  return found;
}

/** data.split(b"\n")。 */
function splitBytes(data: Buffer): Buffer[] {
  const parts: Buffer[] = [];
  let start = 0;
  for (let index = data.indexOf(10); index !== -1; index = data.indexOf(10, start)) {
    parts.push(data.subarray(start, index));
    start = index + 1;
  }
  parts.push(data.subarray(start));
  return parts;
}

/** bytes.strip() 之后为空：只认 ASCII 空白（空格与 0x09–0x0D）。 */
const blankBytes = (raw: Buffer): boolean => raw.every((byte) => byte === 0x20 || (byte >= 0x09 && byte <= 0x0d));

/** raw.rstrip(b"\r")。 */
function rstripCr(raw: Buffer): Buffer {
  let end = raw.length;
  while (end > 0 && raw[end - 1] === 13) end -= 1;
  return raw.subarray(0, end);
}

/** command.count("\n", 0, end)，end 是码点下标。 */
function countNewlines(points: Int32Array, end = points.length): number {
  let count = 0;
  for (let index = 0; index < end; index += 1) if (points[index] === 10) count += 1;
  return count;
}

/** sorted(set(values))：按码点排序。 */
const uniqueSorted = (values: readonly string[]): string[] => [...new Set(values)].sort(cmpCodePoints);

/** 元组列表的 repr：[('p', 'm'), …]。 */
const pairsRepr = (pairs: readonly (readonly [string, string])[]): string => `[${pairs.map(([a, b]) => `(${pyRepr(a)}, ${pyRepr(b)})`).join(", ")}]`;

/** Path.read_text(encoding="utf-8", errors="replace")：坏字节换成 U+FFFD，再做通用换行。 */
function readTextReplace(file: string): string {
  return REPLACE_DECODER.decode(pyReadBytes(file)).split(CR + NL).join(NL).split(CR).join(NL);
}

export interface SummarizeOptions {
  readonly stderrPath?: string | null;
  /** 三态：true、false 或 null（不知道）；只有 false 才放宽成按 agent_end 判断。 */
  readonly expectsSettled?: PyValue;
  readonly allowedOutside?: readonly string[];
  readonly planText?: string;
  readonly protectedRoots?: readonly string[];
}

/**
 * summarize_events：解析 JSONL 事件流，交回（摘要, 最终 assistant 文本）。路径参数都是 Python 那边 str(Path) 的写法。
 * 进程退出码不代表任务成功；摘要只是证据与线索。
 */
export function summarizeEvents(eventsPath: string, workDir: string, executor: PyDict, options: SummarizeOptions = {}): [PyDict, string] {
  const allowedOutside = options.allowedOutside ?? [];
  const protectedRoots = options.protectedRoots ?? [];
  const expectsSettled = options.expectsSettled ?? null;
  const data = pyExists(eventsPath) ? pyReadBytes(eventsPath) : Buffer.alloc(0);
  const ownForms = pathForms([workDir, ...allowedOutside]);
  const protectedForms = pathForms(protectedRoots);
  const protectedResolved = protectedRoots.map(pyResolve);
  const lines = splitBytes(data);
  const counts: PyDict = new Map();
  const parseErrors: number[] = [];
  let header: PyDict | null = null;
  const assistant: PyDict[] = [];
  const totals: PyDict = new Map<string, PyValue>([...USAGE_KEYS.map((key): [string, PyValue] => [key, 0n]), ["cost_total", 0], ["priced_missing", 0n]]);
  const toolCounts: PyDict = new Map();
  let toolErrors = 0;
  const commands: string[] = [];
  const suspicious: PyDict[] = [];
  const tempPaths: PyDict[] = [];
  const maskedExits: PyDict[] = [];
  const tempLeaks: PyDict[] = [];
  const interpretations: PyDict[] = [];
  const cacheCleanups: PyDict[] = [];
  const outsidePaths: PyDict[] = [];
  const outsideByCall = new Map<string, PyDict[]>();
  const shellOutside = new Map<string, PyDict>();
  const ownRunPaths: PyDict[] = [];
  let mentions: PyDict[] = [];
  const domainWords = ambiguityDomainWords(options.planText ?? "");
  const allowedRoots = allowedOutside.map(pyResolve);
  const retries: PyDict[] = [];
  let compactions = 0;
  let systemSections: string[] = [];
  let agentEndCount = 0;
  let settledCount = 0;
  let lastWillRetry: boolean | null = null;
  let pendingWork = false;
  const workRoot = pyResolve(workDir);
  const remember = (event: PyDict, item: PyDict): void => {
    const callId = get(event, "toolCallId");
    if (typeof callId === "string") outsideByCall.set(callId, [...(outsideByCall.get(callId) ?? []), item]);
  };
  lines.forEach((raw, index) => {
    const number = index + 1;
    if (blankBytes(raw)) return;
    const event = parseLine(raw);
    if (!isDict(event)) {
      parseErrors.push(number);
      return;
    }
    const kind = pyStrValue(get(event, "type"));
    counts.set(kind, ((counts.get(kind) as bigint | undefined) ?? 0n) + 1n);
    if (WORK_EVENTS.includes(kind)) pendingWork = true;
    if (kind === "session" && header === null) {
      header = record(["version", "id", "timestamp", "cwd"].map((key): [string, PyValue] => [key, get(event, key)]));
    } else if (kind === "message_end") {
      const message = dictOr(get(event, "message"));
      const role = get(message, "role");
      if (role === "assistant") {
        for (const item of ambiguityMentions(message, number, domainWords)) mentions.push(item.set("message", BigInt(assistant.length)));
        for (const item of interpretationMentions(message, number)) interpretations.push(item.set("message", BigInt(assistant.length)));
        assistant.push(message);
        addUsage(totals, get(message, "usage"));
      } else if (role === "toolResult") {
        addUsage(totals, get(message, "usage"));
      } else if (role === "system" && isDict(get(message, "sections"))) {
        systemSections = ([...(get(message, "sections") as PyDict).keys()] as string[]).sort(cmpCodePoints);
      }
    } else if (kind === "entry_appended") {
      const entry = dictOr(get(event, "entry"));
      if (get(entry, "type") === "usage") addUsage(totals, get(entry, "usage"));
    } else if (kind === "compaction_end") {
      compactions += 1;
      addUsage(totals, get(dictOr(get(event, "result")), "usage"));
    } else if (kind === "tool_execution_start") {
      const name = pyStrValue(get(event, "toolName"));
      toolCounts.set(name, ((toolCounts.get(name) as bigint | undefined) ?? 0n) + 1n);
      const args = dictOr(get(event, "args"));
      if (name === "bash" || name === "powershell") {
        const command = pyStrValue(pyGet(args, "command", ""));
        const points = toPoints(command);
        commands.push(firstPoints(command, 500));
        const masked = maskedExitMention(command);
        if (masked) maskedExits.push(record([["event_line", BigInt(number)], ["match", masked], ["check", isCheckCommand(command)]]));
        const leak = tempDirWithoutCleanup(command);
        if (leak) tempLeaks.push(record([["event_line", BigInt(number)], ["match", leak]]));
        const scan = maskPaths(command, ownForms);
        // 主仓库里的路径逐条命令记录（G2 据此判不通过）；其他工作副本外的路径同一处只记第一次出现的行号，并计数
        const shellPaths: [string, boolean][] = [
          ...protectedMentions(scan, protectedForms).map((excerpt): [string, boolean] => [excerpt, true]),
          ...outsideMentions(scan, protectedForms).map((excerpt): [string, boolean] => [excerpt, false]),
        ];
        for (const [excerpt, inMainRepo] of shellPaths) {
          const first = inMainRepo ? undefined : shellOutside.get(excerpt);
          if (first !== undefined) {
            first.set("occurrences", (first.get("occurrences") as bigint) + 1n);
            continue;
          }
          const item = record([
            ["tool", name],
            ["path", firstPoints(excerpt, 300)],
            ["exists", null],
            ["failed", null],
            ["main_repo", inMainRepo],
            ["event_line", BigInt(number)],
          ]);
          if (!inMainRepo) {
            item.set("occurrences", 1n);
            shellOutside.set(excerpt, item);
          }
          outsidePaths.push(item);
          remember(event, item);
        }
        for (const [matchLine, excerpt] of tempPathMatches(pySplitlines(scan))) {
          tempPaths.push(record([["event_line", BigInt(number)], ["match", excerpt], ["match_line", BigInt(matchLine)]]));
        }
        for (const [pattern, label] of SUSPICIOUS) {
          const found = pattern.search(points);
          if (found === null) continue;
          if (label === DELETE_LABEL) {
            const cleanup = cacheDirCleanup(command);
            if (cleanup) {
              cacheCleanups.push(record([["event_line", BigInt(number)], ["command", firstPoints(cleanup, 200)]]));
              continue;
            }
          }
          // 记下命中所在的行：长命令的开头往往看不出问题在哪里
          suspicious.push(
            record([
              ["label", label],
              ["command", firstPoints(command, 300)],
              ["event_line", BigInt(number)],
              ["match", matchExcerpt(command, found.start, found.end)],
              ["match_line", BigInt(countNewlines(points, found.start) + 1)],
              ["command_lines", BigInt(countNewlines(points) + 1)],
            ]),
          );
          break;
        }
      }
      for (const key of ["path", "file_path"]) {
        const value = get(args, key);
        if (typeof value !== "string" || !pyStrip(value)) continue;
        const candidate = purePathStr(expanduser(pyStrip(value)));
        const resolved = pyResolve(purePathIsAbsolute(candidate) ? candidate : purePathStr(workRoot, candidate));
        if (isWithin(resolved, workRoot)) continue;
        if (allowedRoots.some((root) => isWithin(resolved, root))) {
          ownRunPaths.push(record([["tool", name], ["path", firstPoints(value, 300)]]));
          continue;
        }
        const item = record([
          ["tool", name],
          ["path", firstPoints(value, 300)],
          ["exists", pyExists(resolved)],
          ["failed", null],
          ["main_repo", protectedResolved.some((root) => isWithin(resolved, root))],
        ]);
        outsidePaths.push(item);
        remember(event, item);
      }
    } else if (kind === "tool_execution_end") {
      if (pyTruthy(get(event, "isError"))) toolErrors += 1;
      const key = pyStrValue(get(event, "toolCallId"));
      const pending = outsideByCall.get(key) ?? [];
      outsideByCall.delete(key);
      for (const item of pending) item.set("failed", pyTruthy(get(event, "isError")));
    } else if (kind === "agent_end") {
      agentEndCount += 1;
      lastWillRetry = pyTruthy(get(event, "willRetry"));
      if (!lastWillRetry && settledCount === 0) pendingWork = false;
    } else if (kind === "agent_settled") {
      settledCount += 1;
      pendingWork = false;
    } else if (kind === "auto_retry_start") {
      retries.push(record([["attempt", get(event, "attempt")], ["error", firstPoints(redactSecrets(pyStrValue(pyGet(event, "errorMessage", ""))), 300)]]));
    } else if (kind === "auto_retry_end" && !pyTruthy(get(event, "success"))) {
      retries.push(record([["final_error", firstPoints(redactSecrets(pyStrValue(pyGet(event, "finalError", ""))), 300)]]));
    }
  });

  const truncated = data.length > 0 && data[data.length - 1] !== 10;
  let terminal: string | null = null;
  let complete = false;
  if (settledCount) {
    terminal = "agent_settled";
    complete = !pendingWork;
  } else if (agentEndCount) {
    terminal = "agent_end";
    // 支持 agent_settled 的版本必须以它结束；只在明确不支持时才用 agent_end 降级判断
    complete = expectsSettled === false && !pendingWork && lastWillRetry === false;
  }
  const final: PyDict = assistant.length ? (assistant[assistant.length - 1] as PyDict) : new Map();
  const finalText = final.size ? messageText(final) : "";
  // 最后一条消息的正文就是执行报告：报告里写到的矛盾由 contract_conflicts 等字段承载，不算“未声明的提及”
  mentions = mentions.filter((item) => !(item.get("message") === BigInt(assistant.length - 1) && item.get("kind") === "text"));
  const requested: [PyValue, PyValue] = [get(executor, "provider"), get(executor, "model")];
  const actualKeys = new Map<string, [string, string]>();
  for (const message of assistant) {
    const pair: [string, string] = [pyStrValue(get(message, "provider")), pyStrValue(get(message, "model"))];
    actualKeys.set(JSON.stringify(pair), pair);
  }
  const actual = [...actualKeys.values()].sort((a, b) => cmpCodePoints(a[0], b[0]) || cmpCodePoints(a[1], b[1]));
  const reported = (key: string): string[] =>
    uniqueSorted(assistant.filter((message) => pyTruthy(get(message, key))).map((message) => pyStrValue(get(message, key))));
  const responseModels = reported("responseModel");
  const providerLevels = reported("providerThinkingLevel");
  const modelMatch = assistant.length > 0 && actual.every(([provider, model]) => provider === requested[0] && model === requested[1]);
  let stderrFlags: string[] = [];
  if (options.stderrPath != null && pyExists(options.stderrPath)) {
    const stderrText = stripAnsi(readTextReplace(options.stderrPath));
    stderrFlags = STDERR_FLAGS.filter(([, pattern]) => pattern.search(stderrText) !== null).map(([name]) => name);
  }
  const stopReason = final.size ? get(final, "stopReason") : null;
  const costTotal = totals.get("cost_total") as number;
  const pricedMissing = totals.get("priced_missing") as bigint;
  let costStatus = "unknown";
  if (assistant.length && costTotal > 0) costStatus = pricedMissing === 0n && compactions === 0 ? "estimated" : "partial";
  const requestedThinking = get(executor, "thinking");
  const problems: string[] = [];
  if (!data.length) problems.push("事件流为空");
  if (parseErrors.length) problems.push(`事件流有 ${parseErrors.length} 行无法解析`);
  if (truncated) problems.push("事件流最后一行不完整（可能被截断）");
  if (!complete) {
    if (agentEndCount && !settledCount && expectsSettled !== false) {
      problems.push("没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断");
    } else {
      problems.push("没有观察到完整的结束事件（agent_settled / agent_end）");
    }
  }
  const mismatchedLevels = providerLevels.filter((level) => level !== requestedThinking);
  if (mismatchedLevels.length) {
    problems.push(`提供商报告的思考级别 ${pyReprValue(mismatchedLevels)} 与要求的 ${pyStrValue(requestedThinking)} 不一致`);
  }
  if (stopReason !== "stop") problems.push(`最终 assistant stopReason=${pyStrValue(stopReason)}`);
  if (pyTruthy(get(final, "errorMessage"))) {
    problems.push(`最终 assistant 错误：${firstPoints(redactSecrets(pyStrValue(get(final, "errorMessage"))), 300)}`);
  }
  const textualCall = TEXTUAL_TOOL_CALL.search(finalText);
  if (textualCall !== null) {
    problems.push(
      `最终 assistant 消息的正文里有未执行的工具调用（${textualCall.group}）：模型把工具调用写成了文本，Pi 没有执行，` +
        "回合随之结束，运行没有做完",
    );
  }
  if (!modelMatch) problems.push(`实际模型 ${pairsRepr(actual)} 与要求 ${requested.map(pyStrValue).join("/")} 不一致或缺失`);
  for (const flag of ["custom_model_id", "invalid_thinking", "unknown_option"]) {
    if (stderrFlags.includes(flag)) problems.push(`stderr 出现 ${flag} 警告`);
  }
  const ints = (values: readonly number[]): bigint[] => values.map((value) => BigInt(value));
  const summary = record([
    ["lines", BigInt(lines.filter((line) => !blankBytes(line)).length)],
    ["event_counts", counts],
    ["parse_error_lines", ints(parseErrors.slice(0, 50))],
    ["truncated", truncated],
    ["session_header", header],
    ["terminal_event", terminal],
    ["complete", complete],
    ["final_stop_reason", stopReason],
    ["final_error", final.size && pyTruthy(get(final, "errorMessage")) ? redactSecrets(pyStrValue(pyItem(final, "errorMessage"))) : null],
    ["requested_model", record([["provider", requested[0]], ["model", requested[1]], ["thinking", requestedThinking]])],
    ["actual_models", actual.map(([provider, model]) => record([["provider", provider], ["model", model]]))],
    ["response_models", responseModels],
    ["provider_thinking_levels", providerLevels],
    [
      "thinking_evidence",
      providerLevels.length
        ? "provider_reported"
        : "not_reported：该协议或配置不回报 providerThinkingLevel，只能确认请求的级别；" +
          "实际发送形式取决于协议（例如 anthropic-messages 预算模式把 high 映射为 thinking 预算）",
    ],
    ["model_match", modelMatch],
    ["assistant_messages", BigInt(assistant.length)],
    ["tool_calls", toolCounts],
    ["tool_errors", BigInt(toolErrors)],
    ["auto_retries", retries],
    ["compactions", BigInt(compactions)],
    ["system_prompt_sections", systemSections],
    ["usage", record(USAGE_KEYS.map((key): [string, PyValue] => [key, totals.get(key) as PyValue]))],
    // 未知费用记为 null 而不是 0；partial 时 total 只是已知部分的下界
    [
      "cost",
      record([
        ["total", costStatus !== "unknown" ? pyRound(costTotal, 6) : null],
        ["status", costStatus],
        ["unpriced_messages", pricedMissing],
        ["note", "Pi 按模型目录价格估算；以提供商或网关账单为准"],
      ]),
    ],
    ["stderr_flags", stderrFlags],
    ["shell_commands", commands.slice(0, 200)],
    ["suspicious_commands", suspicious.slice(0, 100)],
    ["temp_path_uses", tempPaths.slice(0, 50)],
    ["temp_path_use_count", BigInt(tempPaths.length)],
    ["cache_dir_cleanups", cacheCleanups.slice(0, 50)],
    ["outside_worktree_paths", outsidePaths.slice(0, 100)],
    ["own_run_paths", ownRunPaths.slice(0, 50)],
    ["ambiguity_mention_count", BigInt(mentions.length)],
    ["ambiguity_domain_words", domainWords],
    ["ambiguity_mentions", mentions.slice(0, 20)],
    ["interpretation_mention_count", BigInt(interpretations.length)],
    ["interpretation_mentions", interpretations.slice(0, 20)],
    ["masked_exit_commands", maskedExits.slice(0, 50)],
    ["temp_dirs_without_cleanup", tempLeaks.slice(0, 50)],
    ["problems", problems],
    ["ok", !problems.length],
  ]);
  return [summary, finalText];
}

/** 一行事件：去掉行尾的 \r，严格按 UTF-8 解码再 json.loads；解不了为 undefined（记解析错误）。嵌套太深照 Python 抛出。 */
function parseLine(raw: Buffer): PyValue | undefined {
  try {
    return loads(pyDecodeUtf8(rstripCr(raw)));
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError || (error instanceof PyJsonError && error.kind !== "RecursionError")) return undefined;
    throw error;
  }
}

/**
 * re.findall(r"```json\s*\n(.*?)\n```", text, re.S)：贪婪的空白先吃满，再从最后一个换行往前退，每退到一个换行就找它之后第一个
 * "\n```"；找到就是一块，从块尾接着找。这些位置上的字符都在基本平面里，按 UTF-16 下标切不会切开代理对。
 */
function jsonBlocks(text: string): string[] {
  const blocks: string[] = [];
  const fence = "```";
  let from = 0;
  for (let start = text.indexOf(`${fence}json`, from); start !== -1; start = text.indexOf(`${fence}json`, from)) {
    const head = start + 7;
    let spaceEnd = head;
    while (spaceEnd < text.length && isSpace(text[spaceEnd] as string)) spaceEnd += 1;
    from = start + 1;
    for (let newline = spaceEnd - 1; newline >= head; newline -= 1) {
      if (text[newline] !== NL) continue;
      const close = text.indexOf(NL + fence, newline + 1);
      if (close === -1) continue;
      blocks.push(text.slice(newline + 1, close));
      from = close + 4;
      break;
    }
  }
  return blocks;
}

/** extract_report：最终消息存成 executor-report.md；最后一个 ```json 块解析成 executor-report.json，交回报告状态。 */
export function extractReport(finalText: string, runDir: string): PyDict {
  if (!pyStrip(finalText)) return record([["status", "missing"]]);
  writeText(path.join(runDir, "executor-report.md"), finalText.endsWith(NL) ? finalText : finalText + NL, false);
  const blocks = jsonBlocks(finalText);
  if (!blocks.length) return record([["status", "no_json"], ["path", "executor-report.md"]]);
  let data: PyValue;
  try {
    data = loads(blocks[blocks.length - 1] as string);
  } catch (error) {
    if (error instanceof PyJsonError && error.kind !== "RecursionError") {
      return record([["status", "json_invalid"], ["error", error.message], ["path", "executor-report.md"]]);
    }
    throw error;
  }
  writeJson(path.join(runDir, "executor-report.json"), data);
  const fields = dictOr(data);
  const counted = ["contract_conflicts", "unresolved_questions", "interpretations"].map((key): [string, PyValue] => {
    const value = get(fields, key);
    return [key, Array.isArray(value) ? BigInt(value.length) : 0n];
  });
  const result = record([["status", "json_ok"], ["executor_status", get(fields, "executor_status")], ["path", "executor-report.json"], ...counted]);
  // 2.10.0 起报告格式里有自定解读的列表；缺失或不是列表（旧执行器、格式偏差）时摘要写一句备注
  if (!Array.isArray(get(fields, "interpretations"))) result.set("interpretations_missing", true);
  return result;
}

/** open(path, "rb").read(limit)：打开失败照 Python 的 OSError 抛出。 */
function readPrefix(file: string, limit: number): Buffer {
  let fd: number;
  try {
    fd = openSync(file, "r");
  } catch (error) {
    throw pyOSErrorOf(error, file) ?? error;
  }
  try {
    const buffer = Buffer.alloc(limit);
    let size = 0;
    for (;;) {
      const count = readSync(fd, buffer, size, limit - size, null);
      if (count === 0 || size + count >= limit) return buffer.subarray(0, size + count);
      size += count;
    }
  } catch (error) {
    throw pyOSErrorOf(error, file) ?? error;
  } finally {
    closeSync(fd);
  }
}

/** review_hints：补丁里新增的跳过/聚焦标记，新增与删除的含断言行数；只读前 20 MiB。 */
export function reviewHints(patchPath: string): PyDict {
  const data = readPrefix(patchPath, HINT_LIMIT);
  const added: string[] = [];
  const removed: string[] = [];
  for (const line of pySplitlines(REPLACE_DECODER.decode(data))) {
    if (line.startsWith("+") && !line.startsWith("+++")) added.push(line.slice(1));
    else if (line.startsWith("-") && !line.startsWith("---")) removed.push(line.slice(1));
  }
  const asserting = (lines: readonly string[]): bigint => BigInt(lines.filter((line) => ASSERT.search(line) !== null).length);
  return record([
    ["skip_markers_added", added.filter((line) => SKIP_MARKER.search(line) !== null).map((line) => firstPoints(pyStrip(line), 200)).slice(0, 50)],
    ["assertion_lines_added", asserting(added)],
    ["assertion_lines_removed", asserting(removed)],
    ["patch_truncated_for_hints", data.length >= HINT_LIMIT],
  ]);
}
