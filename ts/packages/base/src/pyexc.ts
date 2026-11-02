// Python 异常的类名与继承关系（迁移第 ⑤g 片，themistally-15 定的）：base 里带 Python 类名的几种异常，except 子句照继承关系接。
// 只列 kit_hub 会接到的几支；Node 自己的错误（没有照 Python 包过的）认不出，交回 null，except 接不住，照原样往外抛。
import { UnicodeDecodeError } from "./fsutil.ts";
import { PyCrash } from "./pyfmt.ts";
import { PyOSError, PyUnicodeDecodeError } from "./pyio.ts";
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
  return null;
}

/** except (kinds...)：照继承关系，子类也接得住。 */
export function pyCaught(error: unknown, kinds: readonly string[]): boolean {
  for (let name = pyExceptionName(error); name !== null; name = PY_EXCEPTION_PARENTS[name] ?? null) {
    if (kinds.includes(name)) return true;
  }
  return false;
}
