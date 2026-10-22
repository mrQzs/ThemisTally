// kit_logs 的 logs cat（迁移第 ②b1 步）：按页读一个证据文件，分页的单位是脱敏之后的文本（kit_logs 的“安全读取”一节）。
//   - JSONL：逐行解析，合法的行按键名脱敏后用 json.dumps 的缺省格式写出；解析不了的、超过上限的行只给占位。
//   - 其余文本：.json 整份能解析时按键名脱敏、带缩进写出，否则整份 redact_secrets；整份超过上限的不显示。
//   - 游标绑定文件的身份：文本要求大小、修改时间（纳秒）、文件号都不变；JSONL 要求文件号不变、文件只增长，
//     偏移是原始行首，偏移之前的一段与读到一半的那一行都没变。
//   - 单行超过一页时按片给出。
// 文本里的偏移、长度、切片都按码点（Python 的 str），不按 UTF-16 码元。
import { createHash } from "node:crypto";
import { closeSync, lstatSync, openSync, readSync } from "node:fs";
import { jsonlRecords, linesBefore, SAFE_MAX_LINE_BYTES } from "@themis/base/jsonl";
import type { PyOut } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, PyJsonError, dumps, loads } from "@themis/base/pyjson";
import { codePoints, pyStrip } from "@themis/base/pyre";
import { redactJson, redactSecrets } from "@themis/base/secrets";
import { LinkTally, LogsError, LOGS_EXIT_OK, LOGS_EXIT_USAGE, emitJson, evidence, readHead, repoOf, resolveTarget, under } from "./logs.ts";

export const SAFE_PAGE_CHARS = 256 * 1024;
export const SAFE_MAX_TEXT_BYTES = 64 * 1024 * 1024;
const HIDDEN_LINE_COST = 32;
const LINE_OVERHEAD = 16;
const CURSOR_WINDOW = 4096;
const REPLACE_UTF8 = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });
const BAD_CURSOR = "游标格式不对（游标只能原样带回）";

/** kit_logs.StaleCursor：游标对应的文件已变化。 */
class StaleCursor extends LogsError {
  constructor() {
    super("游标对应的文件已变化：请从头读取", LOGS_EXIT_USAGE);
  }
}

/** 按码点索引的字符串：记下补充平面字符的位置，码点下标与 UTF-16 下标互换用二分。 */
class CpText {
  readonly text: string;
  private readonly astral: number[] = []; // 每个补充平面字符的 UTF-16 起点
  readonly length: number;

  constructor(text: string) {
    this.text = text;
    for (let index = 0; index < text.length; index += 1) {
      const unit = text.charCodeAt(index);
      if (unit >= 0xd800 && unit <= 0xdbff && index + 1 < text.length) {
        const next = text.charCodeAt(index + 1);
        if (next >= 0xdc00 && next <= 0xdfff) {
          this.astral.push(index);
          index += 1;
        }
      }
    }
    this.length = text.length - this.astral.length;
  }

  /** 码点下标 → UTF-16 下标。 */
  unit(cp: number): number {
    let low = 0;
    let high = this.astral.length;
    // 找满足 astral[k] - k < cp 的个数 k：这些补充平面字符都在 cp 之前
    while (low < high) {
      const mid = (low + high) >> 1;
      if ((this.astral[mid] as number) - mid < cp) low = mid + 1;
      else high = mid;
    }
    return cp + low;
  }

  /** UTF-16 下标 → 码点下标。 */
  cp(unit: number): number {
    let low = 0;
    let high = this.astral.length;
    while (low < high) {
      const mid = (low + high) >> 1;
      if ((this.astral[mid] as number) < unit) low = mid + 1;
      else high = mid;
    }
    return unit - low;
  }

  slice(start: number, end: number = this.length): string {
    return this.text.slice(this.unit(Math.max(0, start)), this.unit(Math.min(end, this.length)));
  }

  /** str.rfind(sub, start, end)。 */
  rfind(sub: string, start: number, end: number): number {
    const from = this.unit(end) - sub.length;
    if (from < 0) return -1; // lastIndexOf 把负的起点当成 0，Python 的 rfind 此时找不到
    const at = this.text.lastIndexOf(sub, from);
    return at >= 0 && at >= this.unit(start) ? this.cp(at) : -1;
  }

  /** str.find(sub, start)。 */
  find(sub: string, start: number): number {
    const at = this.text.indexOf(sub, this.unit(start));
    return at >= 0 ? this.cp(at) : -1;
  }
}

/** kit_logs.safe_mode。 */
function safeMode(rel: string): "jsonl" | "json" | "text" {
  const lower = rel.toLowerCase();
  if (lower.endsWith(".jsonl")) return "jsonl";
  if (lower.endsWith(".json")) return "json";
  return "text";
}

/** kit_logs.file_identity：（大小, 修改时间纳秒, 文件号）。 */
function fileIdentity(file: string): [bigint, bigint, bigint] {
  const info = lstatSync(file, { bigint: true });
  return [info.size, info.mtimeNs, info.ino];
}

const LONE_SURROGATE = /[\uD800-\uDFFF]/gu;

/** kit_logs._dump：孤立的代理字符写成 \uXXXX（小写），免得输出时编码失败。 */
function dumpJson(value: PyValue, indent: number | null = null): string {
  return dumps(value, { ensureAscii: false, indent }).replace(
    LONE_SURROGATE,
    (char) => `\\u${(char.charCodeAt(0)).toString(16).padStart(4, "0")}`,
  );
}

function jsonOrRecursion(error: unknown): boolean {
  return error instanceof PyJsonError && (error.kind === "JSONDecodeError" || error.kind === "ValueError" || error.kind === "RecursionError");
}

/** kit_logs.redacted_text：整份读出并脱敏（json 与 text 模式）。最多读上限加 1 字节。 */
function redactedText(file: string, name: string, mode: "json" | "text"): string {
  const raw = readHead(file, SAFE_MAX_TEXT_BYTES + 1);
  if (raw === null) throw new LogsError(`读不出来：${name}`, LOGS_EXIT_USAGE);
  if (raw.length > SAFE_MAX_TEXT_BYTES) {
    throw new LogsError(`文件太大（超过上限 ${SAFE_MAX_TEXT_BYTES} 字节），不在这里显示；请直接查看文件`, LOGS_EXIT_USAGE);
  }
  const text = REPLACE_UTF8.decode(raw);
  if (mode === "json") {
    try {
      return `${dumpJson(redactJson(loads(text)), 2)}\n`;
    } catch (error) {
      if (!jsonOrRecursion(error)) throw error;
    }
  }
  return redactSecrets(text);
}

type JsonlEntry = { text: string } | { hidden: "too_long" | "not_json" };

/** kit_logs._jsonl_entry。 */
function jsonlEntry(raw: Buffer | null): JsonlEntry {
  if (raw === null) return { hidden: "too_long" };
  const line = REPLACE_UTF8.decode(raw);
  if (!pyStrip(line)) return { text: "" };
  try {
    return { text: dumpJson(redactJson(loads(line))) };
  } catch (error) {
    if (jsonOrRecursion(error)) return { hidden: "not_json" };
    throw error;
  }
}

function cursorOf(kind: string, ...fields: (bigint | number | string)[]): string {
  return [kind, ...fields.map(String)].join(":");
}

/** kit_logs._cursor_fields。 */
function cursorFields(cursor: string, kind: string, count: number): string[] {
  const parts = cursor.split(":");
  if (parts.length !== count + 1 || parts[0] !== kind || !parts.slice(1).every((part) => /^[0-9a-f]{1,64}$/u.test(part))) {
    throw new LogsError(BAD_CURSOR, LOGS_EXIT_USAGE);
  }
  return parts.slice(1);
}

/** kit_logs._decimal。 */
function decimal(field: string): bigint {
  if (!/^[0-9]+$/u.test(field)) throw new LogsError(BAD_CURSOR, LOGS_EXIT_USAGE);
  return BigInt(field);
}

function digest(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex").slice(0, 16);
}

/** kit_logs._window：游标之前的一段原始字节（最多 CURSOR_WINDOW）。 */
function windowBefore(file: string, position: number): Buffer {
  const start = Math.max(0, position - CURSOR_WINDOW);
  const fd = openSync(file, "r");
  try {
    const buffer = Buffer.alloc(position - start);
    let got = 0;
    while (got < buffer.length) {
      const read = readSync(fd, buffer, got, buffer.length - got, start + got);
      if (read === 0) break;
      got += read;
    }
    return buffer.subarray(0, got);
  } finally {
    closeSync(fd);
  }
}

const div = (a: number, b: number): number => Math.floor(a / b);
const ceilDiv = (a: number, b: number): number => -Math.floor(-a / b);

/** kit_logs._text_page。 */
function textPage(file: string, name: string, rel: string, mode: "json" | "text", cursor: string | null, limit: number): PyDict {
  const [size, mtime, ino] = fileIdentity(file);
  let offset = 0n;
  if (cursor !== null) {
    const [o, cSize, cMtime, cIno] = cursorFields(cursor, "t", 4).map(decimal) as [bigint, bigint, bigint, bigint];
    if (cSize !== size || cMtime !== mtime || cIno !== ino) throw new StaleCursor();
    offset = o;
  }
  const text = new CpText(redactedText(file, name, mode));
  if (offset > BigInt(text.length)) throw new StaleCursor();
  const at = Number(offset);
  let piece: string;
  let after: number;
  if (at + limit >= text.length) {
    piece = text.slice(at);
    after = text.length;
  } else {
    const window = new CpText(text.slice(at, at + limit));
    const cut = window.rfind("\n", 0, window.length);
    [piece, after] = cut >= 0 ? [window.slice(0, cut + 1), at + cut + 1] : [window.text, at + limit];
  }
  const page: PyDict = new Map<string, PyValue>([
    ["path", rel],
    ["mode", "text"],
    ["text", piece],
    ["next_cursor", cursorOf("t", after, size, mtime, ino)],
    ["done", after >= text.length],
  ]);
  const lineStart = text.rfind("\n", 0, at) + 1;
  let lineEnd = text.find("\n", lineStart);
  lineEnd = lineEnd < 0 ? text.length : lineEnd;
  if ((lineStart < at && at < lineEnd) || (!piece.endsWith("\n") && after < text.length)) {
    const part = div(at - lineStart, limit) + 1;
    page.set("part", BigInt(part));
    page.set("parts", BigInt(Math.max(part, ceilDiv(lineEnd - lineStart, limit))));
  }
  return page;
}

/** kit_logs._jsonl_resume：核对 JSONL 游标，返回（原始偏移, 行内字符位置）。 */
function jsonlResume(file: string, cursor: string, size: bigint, mtime: bigint, ino: bigint, final: boolean): [number, number] {
  const fields = cursorFields(cursor, "j", 7);
  const [position, char, cIno, cSize, cMtime] = fields.slice(0, 5).map(decimal) as [bigint, bigint, bigint, bigint, bigint];
  const windowDigest = fields[5] as string;
  const lineDigest = fields[6] as string;
  if (cIno !== ino || size < cSize || position > size || (size === cSize && mtime !== cMtime)) throw new StaleCursor();
  const window = windowBefore(file, Number(position));
  const unchangedEnd = position === size && size === cSize;
  if ((position > 0n && window[window.length - 1] !== 0x0a && !unchangedEnd) || digest(window) !== windowDigest) {
    throw new StaleCursor();
  }
  if (char !== 0n) {
    const first = jsonlRecords(file, Number(position), final).next();
    const record = first.done ? null : first.value;
    if (record === null || record[2] === null || digest(record[2]) !== lineDigest) throw new StaleCursor();
  }
  return [Number(position), Number(char)];
}

function jsonlCursor(file: string, position: number, char: number, line: Buffer | null, size: bigint, mtime: bigint, ino: bigint): string {
  return cursorOf("j", position, char, ino, size, mtime, digest(windowBefore(file, position)),
    char !== 0 && line !== null ? digest(line) : "0");
}

/** kit_logs._jsonl_page。 */
function jsonlPage(file: string, rel: string, cursor: string | null, limit: number, final: boolean): PyDict {
  const [size, mtime, ino] = fileIdentity(file);
  const [position, char] = cursor === null ? [0, 0] : jsonlResume(file, cursor, size, mtime, ino, final);
  let number = linesBefore(file, position) + 1;
  const lines: PyDict[] = [];
  let used = 0;
  let after = position;
  let afterChar = char;
  let afterLine: Buffer | null = null;
  for (const [start, end, raw] of jsonlRecords(file, position, final)) {
    const entry = jsonlEntry(raw);
    const body = "text" in entry ? entry.text : null;
    if (body !== null && (char !== 0 || codePoints(body).length > limit)) {
      if (lines.length > 0) break; // 先交出已有的行；下一页从这条长行开始
      const chars = codePoints(body);
      if (char > chars.length) throw new StaleCursor();
      lines.push(new Map<string, PyValue>([
        ["n", BigInt(number)],
        ["text", chars.slice(char, char + limit).join("")],
        ["part", BigInt(div(char, limit) + 1)],
        ["parts", BigInt(ceilDiv(chars.length, limit))],
      ]));
      if (char + limit < chars.length) {
        [after, afterChar, afterLine] = [start, char + limit, raw];
      } else {
        [after, afterChar] = [end, 0];
      }
      break;
    }
    const cost = body !== null ? codePoints(body).length + LINE_OVERHEAD : HIDDEN_LINE_COST;
    if (lines.length > 0 && used + cost > limit) break;
    lines.push(new Map<string, PyValue>([["n", BigInt(number)], ...Object.entries(entry)] as [string, PyValue][]));
    used += cost;
    number += 1;
    [after, afterChar] = [end, 0];
  }
  return new Map<string, PyValue>([
    ["path", rel],
    ["mode", "jsonl"],
    ["lines", lines],
    ["next_cursor", jsonlCursor(file, after, afterChar, afterLine, size, mtime, ino)],
    ["done", BigInt(after) >= size && afterChar === 0],
  ]);
}

/** kit_logs.safe_page。读文件的系统错误报“读不出来”（Python 的报错原文这里写不出，契约不比较这一行的文字）。 */
export function safePage(file: string, name: string, rel: string, cursor: string | null, limit: bigint, final = true): PyDict {
  if (!(limit >= 1n && limit <= BigInt(SAFE_PAGE_CHARS))) {
    throw new LogsError(`--limit 必须在 1 到 ${SAFE_PAGE_CHARS} 之间：${limit}`, LOGS_EXIT_USAGE);
  }
  const chars = Number(limit);
  try {
    const mode = safeMode(rel);
    return mode === "jsonl" ? jsonlPage(file, rel, cursor, chars, final) : textPage(file, name, rel, mode, cursor, chars);
  } catch (error) {
    if (error instanceof LogsError) throw error;
    const code = (error as NodeJS.ErrnoException).code;
    if (typeof code === "string") throw new LogsError(`读不出来：${(error as Error).message}`, LOGS_EXIT_USAGE);
    throw error;
  }
}

export interface CatArgs {
  readonly repo: string | null;
  readonly target: string;
  readonly path: string;
  readonly cursor: string | null;
  readonly limit: bigint;
  readonly json: boolean;
}

/** kit_logs.cmd_cat。 */
export function cmdCat(args: CatArgs, out: PyOut): number {
  const repo = repoOf(args.repo);
  const [task, attempt, attemptDir] = resolveTarget(repo.runsDir, args.target);
  const files = evidence(attemptDir, new LinkTally());
  if (files === null) throw new LogsError(`无法列出 ${attemptDir}`, LOGS_EXIT_USAGE);
  const rel = args.path.replaceAll("\\", "/");
  if (!files.some(([item]) => item === rel)) throw new LogsError(`不在 ${task}/${attempt} 的证据清单里：${rel}`, LOGS_EXIT_USAGE);
  const parts = rel.split("/");
  const page = safePage(under(attemptDir, parts), parts[parts.length - 1] as string, rel, args.cursor, args.limit);
  if (args.json) {
    emitJson(out, page);
    return LOGS_EXIT_OK;
  }
  if (page.get("mode") === "text") {
    out.write(page.get("text") as string);
  } else {
    for (const line of page.get("lines") as PyDict[]) {
      out.print(line.has("text") ? (line.get("text") as string)
        : `（第 ${String(line.get("n"))} 行已隐藏：${line.get("hidden") === "not_json" ? "不是合法 JSON" : `超过 ${SAFE_MAX_LINE_BYTES} 字节`}）`);
    }
  }
  if (!page.get("done")) out.printErr(`（未完：--cursor ${page.get("next_cursor") as string}）`);
  return LOGS_EXIT_OK;
}
