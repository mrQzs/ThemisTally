// JSONL 账本的追加与读取（迁移第 ① 步 jsonl）：照 kit_hub.Hub.append_event 与 kit_hub 里读账本的写法。
//   appendEvent  记录 = data 加 at（拿锁之前取）、event；同目录的 .events.lock 文件锁（与 Python 互斥，见 native.ts）；
//                json.dumps(记录, ensure_ascii=False, sort_keys=True) 加换行，以追加方式写，写完 fsync
//   readJsonl    read_text 之后 str.splitlines()，每行 json.loads，读不成的跳过
//   jsonlRecords、stripEol、iterLines、linesBefore  kit_logs 读大文件的原语：按字节从偏移读，单行有上限，内存有上限
// 注意（照现行行为保留）：ensure_ascii=False 不转义 0x85、U+2028、U+2029，而 splitlines 把它们也当行界，
// 所以字段里有这几个字符的那一行，读的时候会被拆坏、整行跳过。要改另开内核轮次（计划第 10 节）。
// 分页、游标与脱敏显示是 logs 命令自己的事，归第 ② 步。
import { closeSync, fsyncSync, mkdirSync, openSync, readSync, writeSync } from "node:fs";
import { dirname, join } from "node:path";
import { utcNow } from "./clock.ts";
import { readText } from "./fsutil.ts";
import { withFileLock } from "./native.ts";
import { type PyDict, PyJsonError, type PyValue, dumps, encodeUtf8, loads } from "./pyjson.ts";
import { pySplitlines } from "./pyre.ts";

/** 一条账本记录写成的那一行（不含换行）。 */
export function eventLine(event: string, data: PyDict, at: string): string {
  const record: PyDict = new Map(data);
  record.set("at", at);
  record.set("event", event);
  return dumps(record, { ensureAscii: false, sortKeys: true });
}

/** kit_hub.Hub.append_event：追加一条记录。 */
export async function appendEvent(path: string, event: string, data: PyDict = new Map()): Promise<void> {
  const line = eventLine(event, data, utcNow());
  mkdirSync(dirname(path), { recursive: true });
  await withFileLock(join(dirname(path), ".events.lock"), (lock) => {
    const fd = openSync(path, "a");
    try {
      const bytes = encodeUtf8(`${line}\n`); // 有孤立代理项时与 Python 一样报 UnicodeEncodeError，什么也不写
      lock.assertHeld();
      let offset = 0;
      while (offset < bytes.length) offset += writeSync(fd, bytes, offset, bytes.length - offset);
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
  });
}

/** kit_logs.SAFE_MAX_LINE_BYTES：JSONL 单行的上限（原始字节）。 */
export const SAFE_MAX_LINE_BYTES = 4 * 1024 * 1024;

const NEWLINE = 0x0a;
const RETURN = 0x0d;

/** kit_logs._strip_eol：去掉行尾的一个 \n，再去掉它前面的一个 \r。 */
export function stripEol(raw: Buffer): Buffer {
  let end = raw.length;
  if (end > 0 && raw[end - 1] === NEWLINE) end -= 1;
  if (end > 0 && raw[end - 1] === RETURN) end -= 1;
  return raw.subarray(0, end);
}

/** 二进制文件的 readline(size)：照 Python 的语义，最多 size 字节，遇到 \n 就停（含 \n），到末尾返回空。 */
class ByteReader {
  private buffer: Buffer = Buffer.alloc(0);
  private eof = false;
  private readonly fd: number;
  private position: number;

  constructor(fd: number, position: number) {
    this.fd = fd;
    this.position = position;
  }

  readline(size: number): Buffer {
    let scanned = 0;
    for (;;) {
      const end = Math.min(this.buffer.length, size);
      const newline = this.buffer.subarray(scanned, end).indexOf(NEWLINE);
      if (newline >= 0) return this.take(scanned + newline + 1);
      if (end >= size) return this.take(size);
      scanned = end;
      if (!this.fill()) return this.take(this.buffer.length);
    }
  }

  private fill(): boolean {
    if (this.eof) return false;
    const chunk = Buffer.allocUnsafe(Math.max(1 << 16, this.buffer.length)); // 按缓冲区翻倍读，长行的拷贝是线性的
    const got = readSync(this.fd, chunk, 0, chunk.length, this.position);
    if (got === 0) {
      this.eof = true;
      return false;
    }
    this.position += got;
    this.buffer = Buffer.concat([this.buffer, chunk.subarray(0, got)]);
    return true;
  }

  private take(count: number): Buffer {
    const out = this.buffer.subarray(0, count);
    this.buffer = this.buffer.subarray(count);
    return out;
  }
}

/**
 * kit_logs._jsonl_records：从原始偏移 start 起逐行读，给出 [行起点, 下一行起点, 行内容或 null]，null 表示这一行超过上限。
 * 每次最多读 limit + 1 字节，超长的行只计长度、不留内容。最后一行没有换行时：final 为真才算写完，否则不给（跟随时它可能还在写）。
 */
export function* jsonlRecords(
  path: string,
  start: number,
  final: boolean,
  limit: number = SAFE_MAX_LINE_BYTES,
): Generator<[number, number, Buffer | null]> {
  const fd = openSync(path, "r");
  try {
    const reader = new ByteReader(fd, start);
    let offset = start;
    for (;;) {
      let line: Buffer = Buffer.alloc(0);
      let length = 0;
      let tooLong = false;
      let ended = false;
      for (;;) {
        const piece = reader.readline(limit + 1);
        if (piece.length === 0) break;
        length += piece.length;
        if (!tooLong) {
          line = Buffer.concat([line, piece]);
          if (stripEol(line).length > limit) {
            tooLong = true;
            line = Buffer.alloc(0);
          }
        }
        if (piece[piece.length - 1] === NEWLINE) {
          ended = true;
          break;
        }
      }
      if (length === 0 || (!ended && !final)) return;
      yield [offset, offset + length, tooLong ? null : stripEol(line)];
      offset += length;
    }
  } finally {
    closeSync(fd);
  }
}

const REPLACE_DECODER = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });

/** kit_logs._iter_lines：逐行读，按 \n 分行，去掉行尾的 \n 与 \r，UTF-8 解码（errors=replace）。读不出来就没有行。 */
export function* iterLines(path: string): Generator<string> {
  let fd: number;
  try {
    fd = openSync(path, "r");
  } catch {
    return;
  }
  try {
    const reader = new ByteReader(fd, 0);
    for (;;) {
      let raw: Buffer;
      try {
        raw = reader.readline(Number.POSITIVE_INFINITY);
      } catch {
        return; // 读到一半出错：已经给出的行照旧，后面没有了
      }
      if (raw.length === 0) return;
      yield REPLACE_DECODER.decode(stripEol(raw));
    }
  } finally {
    closeSync(fd);
  }
}

/** kit_logs._lines_before：偏移之前有多少个换行（每次读 1 MiB）。 */
export function linesBefore(path: string, position: number): number {
  const fd = openSync(path, "r");
  try {
    const chunk = Buffer.allocUnsafe(1 << 20);
    let count = 0;
    let offset = 0;
    while (offset < position) {
      const got = readSync(fd, chunk, 0, Math.min(chunk.length, position - offset), offset);
      if (got === 0) break;
      for (let index = 0; index < got; index += 1) if (chunk[index] === NEWLINE) count += 1;
      offset += got;
    }
    return count;
  } finally {
    closeSync(fd);
  }
}

/** kit_hub 读账本：read_text、splitlines、逐行 json.loads，读不成的跳过。 */
export function readJsonl(path: string): PyValue[] {
  const out: PyValue[] = [];
  for (const line of pySplitlines(readText(path))) {
    try {
      out.push(loads(line));
    } catch (error) {
      // 只跳过 ValueError（含 JSONDecodeError）；RecursionError 与 Python 一样照样抛出
      if (error instanceof PyJsonError && (error.kind === "JSONDecodeError" || error.kind === "ValueError")) continue;
      throw error;
    }
  }
  return out;
}
