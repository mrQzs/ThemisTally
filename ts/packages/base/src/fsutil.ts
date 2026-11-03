// 文本文件的读写：照 kit_hub.read_text / write_text_atomic 的行为（迁移第 ① 步，locks 与 jsonl 都用它）。
//   readText          Python 的 Path.read_text(encoding="utf-8")：\r\n 与单独的 \r 都换成 \n，开头的 BOM 保留，
//                     不是合法 UTF-8 就报 UnicodeDecodeError；共享冲突（别的进程正在替换它）短暂重试，
//                     其余读不到的情况（不存在、是目录）返回空串
//   writeTextAtomic   独立的临时文件 <名字>.<12 位十六进制>.tmp 写完再整份替换，读者只会看到旧版或新版；
//                     替换撞上共享冲突短暂重试，最后还失败就删掉临时文件再报错
import { randomBytes } from "node:crypto";
import { closeSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { win32ErrorMessage } from "./native.ts";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorOf } from "./pyio.ts";
import { PyWinError } from "./pyos.ts";
import { encodeUtf8 } from "./pyjson.ts";

/** kit_hub 的 SHARING_RETRIES、SHARING_PAUSE：40 次，每次隔 50 毫秒。 */
export const SHARING_RETRIES = 40;
export const SHARING_PAUSE_MS = 50;

/** Python 的 UnicodeDecodeError。 */
export class UnicodeDecodeError extends Error {
  override readonly name = "UnicodeDecodeError";
}

/** 同步地睡一会儿（锁与重试都是同步的，与 Python 版一致）。 */
export function sleepSync(milliseconds: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, Math.max(0, milliseconds));
}

/** Python 的 PermissionError 对应的错误码（Windows 上的共享冲突也报成这几种）。 */
export function isPermissionError(error: unknown): boolean {
  const code = (error as NodeJS.ErrnoException | undefined)?.code;
  return code === "EPERM" || code === "EACCES" || code === "EBUSY";
}


/** kit_hub.read_text。 */
export function readText(path: string): string {
  for (let attempt = 0; attempt < SHARING_RETRIES; attempt += 1) {
    let bytes: Buffer;
    try {
      bytes = readFileSync(path);
    } catch (error) {
      if (!isPermissionError(error)) return "";
      if (attempt === SHARING_RETRIES - 1) return "";
      sleepSync(SHARING_PAUSE_MS);
      continue;
    }
    let text: string;
    try {
      text = pyDecodeUtf8(bytes);
    } catch (error) {
      if (!(error instanceof PyUnicodeDecodeError)) throw error;
      throw new UnicodeDecodeError(error.message); // 文字照 CPython 的 str(exc)（⑤f），类照旧
    }
    return text.replace(/\r\n?/g, "\n"); // 通用换行：Python 的文本模式读
  }
  return "";
}

/**
 * 写文本文件（newline="\n"：不转换换行）。exclusive 时目标已存在就报 EEXIST。
 * 与 Python 一样先建文件再编码：有孤立代理项时报 UnicodeEncodeError，留下一个空文件。
 */
export function writeText(path: string, text: string, exclusive = true): void {
  const fd = openSync(path, exclusive ? "wx" : "w");
  try {
    const bytes = encodeUtf8(text);
    let offset = 0;
    while (offset < bytes.length) offset += writeSync(fd, bytes, offset, bytes.length - offset);
  } finally {
    closeSync(fd);
  }
}

/**
 * renameSync 最后一次失败时照 CPython 的 os.replace 报：Windows 上 libuv 的 EPERM、EACCES 是 WinError 5，EBUSY 是 32，文字取
 * FormatMessageW（跟着系统界面的语言），带两个路径（⑤f）。别的平台照 pyOSErrorOf。
 */
export function replaceError(error: unknown, src: string, dst: string): unknown {
  const code = (error as NodeJS.ErrnoException).code;
  const winerror = code === "EBUSY" ? 32 : code === "EPERM" || code === "EACCES" ? 5 : null;
  if (process.platform === "win32" && winerror !== null) return new PyWinError(winerror, win32ErrorMessage(winerror), src, dst);
  return pyOSErrorOf(error, src) ?? error;
}

/** kit_hub.write_text_atomic。 */
export function writeTextAtomic(path: string, text: string): void {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = join(dirname(path), `${basename(path)}.${randomBytes(6).toString("hex")}.tmp`);
  writeText(tmp, text, false);
  for (let attempt = 0; attempt < SHARING_RETRIES; attempt += 1) {
    try {
      renameSync(tmp, path); // 与 os.replace 一样覆盖已有的目标
      return;
    } catch (error) {
      if (!isPermissionError(error)) throw error; // 与 Python 一样：别的错误不删临时文件
      if (attempt === SHARING_RETRIES - 1) {
        rmSync(tmp, { force: true });
        throw replaceError(error, tmp, path);
      }
      sleepSync(SHARING_PAUSE_MS);
    }
  }
}

/**
 * 删掉一次子进程用过的临时目录（⑤h2 从 pi-cli 挪来，runCapture、hub 的门禁回归与 ts/ 重装共用）：子进程树结束之后，还没退干净的进程
 * 可能仍拿着继承来的 stdout、stderr 句柄（Windows 上打开时不带 FILE_SHARE_DELETE），删除报 EPERM、EBUSY：照共享冲突短暂重试，最后还
 * 失败照旧抛出。rmSync 的 maxRetries 在 Node 的同步版与 Bun 上都不管用（Node 24.19、Bun 1.4.2 实测）。
 */
export async function removeTempDir(dir: string): Promise<void> {
  for (let attempt = 1; ; attempt += 1) {
    try {
      rmSync(dir, { recursive: true, force: true });
      return;
    } catch (error) {
      if (!isPermissionError(error) || attempt === SHARING_RETRIES) throw error;
      await new Promise((resolve) => setTimeout(resolve, SHARING_PAUSE_MS));
    }
  }
}
