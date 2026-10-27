// Path.read_bytes() 与 Path.read_text(encoding="utf-8") 的 Python 行为（迁移第 ③ 步）：出错时异常的文字与 Python 逐字相同，
// 配置中心会把 str(exc) 写进输出。
//   - OSError：open() 走 CRT，文字是 "[Errno N] <strerror>: '<路径>'"。只覆盖文件名合法时遇得到的几种：不存在、是目录、
//     没有权限、被别的进程占用。文件名本身非法（含 <>:"|?*、控制字符，或某一段太长）时 Python 报 [Errno 22]，Node 却报
//     ENOENT，从错误码分不出来；配置中心读的都是固定的文件名，遇不到。
//   - UnicodeDecodeError：CPython 的 UTF-8 解码器报的第一个错误，位置与原因照 Objects/stringlib/codecs.h。
//   - 读文本用通用换行（\r\n 与单独的 \r 都换成 \n），开头的 BOM 保留。
import { readFileSync, statSync } from "node:fs";
import { dirname } from "node:path";
import { pyRepr } from "./pyfmt.ts";

const CRT_ERRNO: Readonly<Record<string, readonly [number, string]>> = {
  ENOENT: [2, "No such file or directory"],
  EISDIR: [13, "Permission denied"],
  EACCES: [13, "Permission denied"],
  EPERM: [13, "Permission denied"],
  EBUSY: [13, "Permission denied"],
};

/** Python 的 OSError（CRT 的 open、read 抛出的那一种）：str(exc) 就是 message；read 的报错不带文件名。 */
export class PyOSError extends Error {
  override readonly name = "OSError";
  readonly errno: number;
  readonly strerror: string;
  constructor(errno: number, strerror: string, filename: string | null) {
    super(filename === null ? `[Errno ${errno}] ${strerror}` : `[Errno ${errno}] ${strerror}: ${pyRepr(filename)}`);
    this.errno = errno;
    this.strerror = strerror;
  }
}

/** Python 的 UnicodeDecodeError（ValueError 的子类）：str(exc) 就是 message。 */
export class PyUnicodeDecodeError extends Error {
  override readonly name = "UnicodeDecodeError";
}

/** type(exc).__name__：OSError 按 errno 落到的子类。 */
export function pyOSErrorType(error: PyOSError): string {
  return error.errno === 2 ? "FileNotFoundError" : error.errno === 13 ? "PermissionError" : "OSError";
}

/**
 * Node 的文件错误换成 Python 会抛的 PyOSError；不在表里的错误码为 null，调用方照原样抛。打开之后读的时候出错（例如别的
 * 进程锁住了字节：Node 报 EBUSY、syscall 是 read），Python 的 FileIO.read 报的 OSError 不带文件名。目录例外：Node 打开
 * 目录成功、读的时候才报 EISDIR，Python 在 open 时就拒绝，报错带文件名。
 */
export function pyOSErrorOf(error: unknown, shown: string): PyOSError | null {
  const failure = error as NodeJS.ErrnoException | undefined;
  const known = CRT_ERRNO[failure?.code ?? ""];
  if (known === undefined) return null;
  const whileReading = failure?.syscall === "read" && failure.code !== "EISDIR";
  return new PyOSError(known[0], known[1], whileReading ? null : shown);
}

/** Path(shown).read_bytes()；shown 是 Python 那边 str(path) 的写法，只用在报错文字里。 */
export function pyReadBytes(path: string, shown: string = path): Buffer {
  try {
    return readFileSync(path);
  } catch (error) {
    throw pyOSErrorOf(error, shown) ?? error;
  }
}

/** Path(shown).read_text(encoding="utf-8")。 */
export function pyReadText(path: string, shown: string = path): string {
  return pyDecodeUtf8(pyReadBytes(path, shown)).replace(/\r\n?/gu, "\n");
}

/** bytes.decode("utf-8", "replace")：坏字节换成 U+FFFD（与 CPython 一样按最大有效子段替换），开头的 BOM 留着。 */
export function pyDecodeUtf8Replace(bytes: Uint8Array): string {
  return REPLACE_DECODER.decode(bytes);
}

/** Path(shown).read_text(encoding="utf-8", errors="replace")：宽松解码之后做通用换行。 */
export function pyReadTextReplace(path: string, shown: string = path): string {
  const CR = String.fromCharCode(13);
  const LF = String.fromCharCode(10);
  return pyDecodeUtf8Replace(pyReadBytes(path, shown)).split(CR + LF).join(LF).split(CR).join(LF);
}

const REPLACE_DECODER = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });
const DECODER = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });

/** bytes.decode("utf-8")（strict）：不合法时照 CPython 报第一个错误。 */
export function pyDecodeUtf8(bytes: Uint8Array): string {
  const error = firstUtf8Error(bytes);
  if (error !== null) {
    const [start, end, reason] = error;
    const where =
      end === start + 1
        ? `byte 0x${(bytes[start] ?? 0).toString(16).padStart(2, "0")} in position ${start}`
        : `bytes in position ${start}-${end - 1}`;
    throw new PyUnicodeDecodeError(`'utf-8' codec can't decode ${where}: ${reason}`);
  }
  return DECODER.decode(bytes);
}

const isContinuation = (byte: number | undefined): boolean => byte !== undefined && byte >= 0x80 && byte <= 0xbf;

/** 第一个错误的 [起, 止, 原因]；合法时为 null。 */
function firstUtf8Error(bytes: Uint8Array): [number, number, string] | null {
  const end = bytes.length;
  let index = 0;
  while (index < end) {
    const lead = bytes[index] ?? 0;
    if (lead < 0x80) {
      index += 1;
      continue;
    }
    const length = lead >= 0xc2 && lead < 0xe0 ? 2 : lead >= 0xe0 && lead < 0xf0 ? 3 : lead >= 0xf0 && lead < 0xf5 ? 4 : 0;
    if (length === 0) return [index, index + 1, "invalid start byte"];
    // 第几个字节出错（1 起算）：2 是第一个续字节，与 codecs.h 的 InvalidContinuation1..3 对应
    const bad = badContinuation(bytes, index, lead, length);
    if (bad !== null) return [index, index + bad - 1, "invalid continuation byte"];
    if (end - index < length) return [index, end, "unexpected end of data"];
    index += length;
  }
  return null;
}

function badContinuation(bytes: Uint8Array, index: number, lead: number, length: number): number | null {
  const second = bytes[index + 1];
  if (second === undefined) return null;
  const secondOk =
    isContinuation(second) &&
    !(lead === 0xe0 && second < 0xa0) &&
    !(lead === 0xed && second >= 0xa0) &&
    !(lead === 0xf0 && second < 0x90) &&
    !(lead === 0xf4 && second >= 0x90);
  if (!secondOk) return 2;
  for (let offset = 2; offset < length; offset += 1) {
    const byte = bytes[index + offset];
    if (byte === undefined) return null;
    if (!isContinuation(byte)) return offset + 1;
  }
  return null;
}

