// TS 实现的入口（迁移第 ② 步）。参数由 Python 启动器的 argparse 解析（-h 与用法错误都由 Python 回答），解析好之后
// 经 `--pyargs-b64 <base64>` 交给这里：内容是应用默认值之后的完整参数，加上子命令路径 command（契约见
// contracts/schemas/pyargs-v1.schema.json）。stdin、stdout、stderr 由启动器原样交给本进程继承，退出码原样交回。
//
// 报错照两边各自的写法：调度器的命令（status）写 `ERROR: ` 加 redact_tokens 之后的消息；kit_logs 的命令写
// `ERROR: ` 加原消息，嵌套太深之类写 `ERROR: <类型>: <消息>`。Python 会打堆栈的地方（证据文件的类型不对等），
// 这里写一行“崩溃”，退出码 1，契约只比较退出码。
import { initFileAttributes } from "@themis/base/native";
import { PyCrash, PyOut } from "@themis/base/pyfmt";
import { PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { redactTokens } from "@themis/base/secrets";
import { LogsError, type ListArgs, type ShowArgs, cmdList, cmdShow } from "@themis/dispatcher/logs";
import { type CatArgs, cmdCat } from "@themis/dispatcher/logs-cat";
import { DispatchError } from "@themis/dispatcher/repo";
import { type StatusArgs, cmdStatus } from "@themis/dispatcher/status";

interface PyArgs {
  readonly command: readonly string[];
}

const EXIT_CRASH = 1;

/** pyjson 的值换成普通对象：dict 成对象，list 成数组，int 保持 bigint。 */
function plain(value: PyValue): unknown {
  if (value instanceof Map) return Object.fromEntries([...value].map(([key, item]) => [String(key), plain(item)]));
  if (Array.isArray(value)) return value.map(plain);
  return value;
}

function crash(out: PyOut, error: unknown): number {
  const kind = error instanceof PyCrash || error instanceof PyJsonError ? error.kind : "Error";
  out.printErr(`崩溃（Python 在这里会打印堆栈）：${kind}: ${(error as Error).message}`);
  return EXIT_CRASH;
}

function runDispatcher(out: PyOut, body: () => number): number {
  try {
    return body();
  } catch (error) {
    if (error instanceof DispatchError) {
      out.printErr(`ERROR: ${redactTokens(error.message)}`);
      return error.code;
    }
    return crash(out, error);
  }
}

function runLogs(out: PyOut, body: () => number): number {
  try {
    return body();
  } catch (error) {
    if (error instanceof LogsError) {
      out.printErr(`ERROR: ${error.message}`);
      return error.code;
    }
    if (error instanceof PyJsonError && error.kind === "RecursionError") {
      out.printErr(`ERROR: RecursionError: ${error.message}`);
      return 1;
    }
    return crash(out, error);
  }
}

export async function main(argv: readonly string[]): Promise<number> {
  const out = new PyOut();
  const at = argv.indexOf("--pyargs-b64");
  const encoded = at >= 0 ? argv[at + 1] : undefined;
  if (encoded === undefined) {
    out.printErr("ERROR: TS 入口只接受 --pyargs-b64 <base64>（由 Python 启动器给出）");
    return 2;
  }
  // 用 pyjson 解析：Python 的 int 可能超出 JS 数字的精度（例如 --limit 给了一个很大的数，报错里要原样写出）
  const args = plain(loads(Buffer.from(encoded, "base64").toString("utf8"))) as PyArgs & Record<string, unknown>;
  await initFileAttributes();
  switch (args.command.join(" ")) {
    case "status":
      return runDispatcher(out, () => cmdStatus(args as unknown as StatusArgs, out));
    case "logs list":
      return runLogs(out, () => cmdList(args as unknown as ListArgs, out));
    case "logs show":
      return runLogs(out, () => cmdShow(args as unknown as ShowArgs, out));
    case "logs cat":
      return runLogs(out, () => cmdCat(args as unknown as CatArgs, out));
    default:
      out.printErr(`ERROR: TS 实现还没有这条命令：${args.command.join(" ")}`);
      return 2;
  }
}

process.exitCode = await main(process.argv.slice(2));
