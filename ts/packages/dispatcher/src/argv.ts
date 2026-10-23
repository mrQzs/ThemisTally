// pi_dispatch.ensure_argv_safe 与 BATCH_UNSAFE_CHARS 的逐字节移植（迁移计划第 8.2 节第 3 条）：进程监督
// （@themis/base/supervise）本身不拒绝 .cmd、.bat，调用方先过这一关。Windows 的批处理包装经 cmd.exe 解析参数，
// 参数里的这些字符能拼出别的命令（BatBadBut 一类，CVE-2024-24576）。
//
// argv[0] 的小写：Python 是 str.lower()，这里用 toLowerCase。判断的只是结尾是不是 ".cmd" 或 ".bat"，两者在这里结论
// 相同（没有别的字符会小写成这几个 ASCII 字母，多字符展开也只发生在 İ 这类字符上，展开结果不以它们结尾）；
// contracts 里有一组含特殊字符的语料与 Python 逐个比对。
import { pyRepr } from "@themis/base/pyfmt";
import { DispatchError, EXIT_USAGE } from "./repo.ts";

/** pi_dispatch.BATCH_UNSAFE_CHARS */
export const BATCH_UNSAFE_CHARS: ReadonlySet<string> = new Set('&|<>^%!"\r\n');

/** pi_dispatch.ensure_argv_safe：Windows 批处理包装会经 cmd.exe 解析参数；含特殊字符时拒绝执行。 */
export function ensureArgvSafe(cmd: readonly string[]): void {
  const program = cmd[0];
  if (process.platform !== "win32" || program === undefined) return;
  const lowered = program.toLowerCase();
  if (!lowered.endsWith(".cmd") && !lowered.endsWith(".bat")) return;
  for (const arg of cmd.slice(1)) {
    if ([...arg].some((char) => BATCH_UNSAFE_CHARS.has(char))) {
      throw new DispatchError(
        `参数 ${pyRepr(arg)} 含批处理特殊字符，不能安全传给 ${program}；请改用 PI_DISPATCH_PI_CMD 指向 node 与入口脚本`,
        EXIT_USAGE,
      );
    }
  }
}
