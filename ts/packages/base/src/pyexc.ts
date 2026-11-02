// Python 异常的类名与继承关系（迁移第 ⑤g 片，themistally-15 定的）：base 里带 Python 类名的几种异常，except 子句照继承关系接。
// 只列 kit_hub 会接到的几支。Node 的文件错误（libuv 报的，带 syscall）照 Python 在 Windows 上抛的归到 OSError 的子类（⑤g2，映射照实测）；
// Node 别的错误（参数错一类的 ERR_*）认不出，交回 null，except 接不住，照原样往外抛。
import { UnicodeDecodeError } from "./fsutil.ts";
import { PyCrash } from "./pyfmt.ts";
import { PyOSError, PyUnicodeDecodeError, pyOSErrorOf } from "./pyio.ts";
import { PyJsonError } from "./pyjson.ts";
import { PyWinError } from "./pyos.ts";
import { PyOverflowError, PyReError, PyValueError } from "./pyregex/search.ts";

/** 子类 → 父类（导出给契约逐对比 __mro__）。 */
export const PY_EXCEPTION_PARENTS: Readonly<Record<string, string>> = {
  JSONDecodeError: "ValueError", UnicodeError: "ValueError", UnicodeDecodeError: "UnicodeError", UnicodeEncodeError: "UnicodeError",
  FileNotFoundError: "OSError", PermissionError: "OSError", FileExistsError: "OSError", IsADirectoryError: "OSError", NotADirectoryError: "OSError",
  BrokenPipeError: "ConnectionError", ConnectionError: "OSError", ChildProcessError: "OSError", BlockingIOError: "OSError",
  KeyError: "LookupError", IndexError: "LookupError",
  RecursionError: "RuntimeError",
  OverflowError: "ArithmeticError", ZeroDivisionError: "ArithmeticError",
  ValueError: "Exception", OSError: "Exception", LookupError: "Exception", RuntimeError: "Exception", ArithmeticError: "Exception",
  TypeError: "Exception", AttributeError: "Exception", error: "Exception",
  TimeoutExpired: "SubprocessError", SubprocessError: "Exception",
};

/** OSError(errno, ...) 照 errno 落到的子类（Windows 的 CRT 错误码）。 */
const OS_ERRORS: Readonly<Record<number, string>> = {
  1: "PermissionError", 2: "FileNotFoundError", 13: "PermissionError", 17: "FileExistsError", 20: "NotADirectoryError", 21: "IsADirectoryError",
};

/** type(exc).__name__：base 里带 Python 类名的异常；别的是 null。 */
export function pyExceptionName(error: unknown): string | null {
  if (error instanceof PyCrash || error instanceof PyJsonError) return error.kind;
  if (error instanceof PyOSError) return OS_ERRORS[error.errno] ?? "OSError";
  if (error instanceof PyWinError) return error.name; // Windows 错误码照 CPython 归的子类
  if (error instanceof PyUnicodeDecodeError || error instanceof UnicodeDecodeError) return "UnicodeDecodeError";
  if (error instanceof PyValueError) return "ValueError";
  if (error instanceof PyOverflowError) return "OverflowError";
  if (error instanceof PyReError) return "error"; // re.error
  return nodeOSErrorName(error);
}

/**
 * Node 的文件错误在 Python 那边是哪一类：删不在的文件 ENOENT 对 FileNotFoundError；把目录当文件读 EISDIR 对 PermissionError [Errno 13]；
 * 删目录 EPERM 对 PermissionError [WinError 5]；EACCES、EBUSY 也是 PermissionError；EEXIST 对 FileExistsError；ENOTDIR 对
 * NotADirectoryError；别的系统错误是 OSError。
 */
function nodeOSErrorName(error: unknown): string | null {
  const failure = error as NodeJS.ErrnoException | undefined;
  if (!(error instanceof Error) || typeof failure?.code !== "string" || typeof failure.syscall !== "string") return null;
  const known = pyOSErrorOf(error, "");
  if (known !== null) return OS_ERRORS[known.errno] ?? "OSError";
  return failure.code === "ENOTDIR" ? "NotADirectoryError" : "OSError";
}

/** except (kinds...)：照继承关系，子类也接得住。 */
export function pyCaught(error: unknown, kinds: readonly string[]): boolean {
  for (let name = pyExceptionName(error); name !== null; name = PY_EXCEPTION_PARENTS[name] ?? null) {
    if (kinds.includes(name)) return true;
  }
  return false;
}
