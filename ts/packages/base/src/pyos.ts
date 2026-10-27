// os.replace、os.rename 与 Path.mkdir 的 Python 行为（迁移第 ③ 步补，themistally-15 复核查出）：配置中心把它们的
// str(exc) 原样写进输出（“写入失败：…”“审计写不进去（…）”“快照存不下（…）”）。CPython 在 Windows 上直接调 Win32，
// 文字是 [WinError N] 加 FormatMessageW；这里同样直接调（native.ts 的 win32FileOp），不经 libuv 的错误码映射。
// 非 Windows 照 Node 的 fs 做，报错照 CRT 的 [Errno N]（pyio 的映射）。
import { randomBytes } from "node:crypto";
import { closeSync, constants, mkdirSync, openSync, renameSync, rmSync, statSync, writeSync } from "node:fs";
import { dirname } from "node:path";
import { win32ErrorMessage, win32FileOp } from "./native.ts";
import { PyOSError, pyOSErrorOf } from "./pyio.ts";
import { pyRepr } from "./pyfmt.ts";
import { publishNew, tmpPathFor } from "./publish.ts";
import { windowsOSError } from "./supervise.ts";

const WIN = process.platform === "win32";

/** CPython 用 Windows 错误码构造的 OSError：str(exc) 就是 message。 */
export class PyWinError extends Error {
  override readonly name: string;
  readonly winerror: number;
  readonly strerror: string;
  constructor(winerror: number, text: string, filename: string, filename2?: string) {
    const { name, strerror } = windowsOSError(winerror, text);
    super(`[WinError ${winerror}] ${strerror}: ${pyRepr(filename)}${filename2 === undefined ? "" : ` -> ${pyRepr(filename2)}`}`);
    this.name = name;
    this.winerror = winerror;
    this.strerror = strerror;
  }
}

/**
 * os.lstat、os.listdir 一类抛的 OSError 的 strerror（配置中心只把它放进输出）。拒绝访问（EACCES、EPERM）在 Windows 上是
 * 5 号错误，文字取 FormatMessageW（跟着系统界面的语言，去掉末尾的句点）；其余错误码 libuv 反推不回，文字不保证与
 * Python 一致（契约说明里写明）。
 */
export function pyLstatStrerror(error: unknown): string {
  const code = (error as NodeJS.ErrnoException).code;
  if (code === "EACCES" || code === "EPERM") return WIN ? windowsOSError(5, win32ErrorMessage(5)).strerror : "Permission denied";
  return (error as Error).message;
}

function move(src: string, dst: string, replace: boolean): void {
  if (!WIN) {
    try {
      renameSync(src, dst);
    } catch (error) {
      throw pyOSErrorOf(error, src) ?? error;
    }
    return;
  }
  const failure = win32FileOp({ op: replace ? "replace" : "rename", src, dst });
  if (failure !== null) throw new PyWinError(failure.winerror, failure.message, src, dst);
}

/** os.replace(src, dst)：目标存在就覆盖。 */
export function pyReplace(src: string, dst: string): void {
  move(src, dst, true);
}

/** os.rename(src, dst)：Windows 上目标存在时报 FileExistsError（[WinError 183]），不覆盖。 */
export function pyRename(src: string, dst: string): void {
  move(src, dst, false);
}

/**
 * pi_dispatch.publish_new 照 Python 在 Windows 上的写法：同一目录写完独立的临时文件（O_EXCL），再用 os.rename 换上去
 * （目标存在时报 FileExistsError，不覆盖）。目标已存在返回 false；其余错误原样抛出：open 照 CRT 的 [Errno N]，rename
 * 照 Win32。base 的 publishNew 用 linkSync，失败时的文字与 Python 不同；只在报错会进输出的地方（配置快照）用这一份。
 * POSIX 上 Python 用 os.link，与 publishNew 相同。
 */
export function pyPublishNew(path: string, data: Uint8Array): boolean {
  if (!WIN) return publishNew(path, data);
  const tmp = tmpPathFor(path, randomBytes(8));
  let fd: number;
  try {
    fd = openSync(tmp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL, 0o666);
  } catch (error) {
    throw pyOSErrorOf(error, tmp) ?? error;
  }
  try {
    try {
      let offset = 0;
      while (offset < data.length) offset += writeSync(fd, data, offset, data.length - offset);
    } finally {
      closeSync(fd);
    }
    try {
      pyRename(tmp, path);
    } catch (error) {
      if (error instanceof PyWinError && error.name === "FileExistsError") return false; // 只有发布这一步的“已存在”才算别人抢先发布
      throw error;
    }
    return true;
  } finally {
    rmSync(tmp, { force: true });
  }
}

/** os.mkdir(path, mode)。 */
export function osMkdir(path: string, mode = 0o777): void {
  if (!WIN) {
    try {
      mkdirSync(path, mode);
    } catch (error) {
      throw pyOSErrorOf(error, path) ?? error;
    }
    return;
  }
  const failure = win32FileOp({ op: "mkdir", path });
  if (failure !== null) throw new PyWinError(failure.winerror, failure.message, path);
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Path(path).mkdir(parents=…, exist_ok=…)（Python 3.12 的 pathlib）：父目录不在（FileNotFoundError）且 parents 时先建
 * 父目录再试；其余错误在 exist_ok 而且它已经是目录时放过（不靠 EEXIST，系统可能先报别的错）。
 */
export function pathMkdir(path: string, parents: boolean, existOk: boolean): void {
  try {
    osMkdir(path);
  } catch (error) {
    const missing = error instanceof PyWinError ? error.name === "FileNotFoundError" : error instanceof PyOSError && error.errno === 2;
    if (missing) {
      const parent = dirname(path);
      if (!parents || parent === path) throw error;
      pathMkdir(parent, true, true);
      pathMkdir(path, false, existOk);
      return;
    }
    if (!existOk || !isDir(path)) throw error;
  }
}
