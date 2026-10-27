// TS 实现的入口（迁移第 ② 步）。参数由 Python 启动器的 argparse 解析（-h 与用法错误都由 Python 回答），解析好之后
// 经 `--pyargs-b64 <base64>` 交给这里：内容是应用默认值之后的完整参数，加上子命令路径 command（契约见
// contracts/schemas/pyargs-v1.schema.json）。stdin、stdout、stderr 由启动器原样交给本进程继承，退出码原样交回。
//
// 报错照两边各自的写法：调度器的命令（status）写 `ERROR: ` 加 redact_tokens 之后的消息；kit_logs 的命令写
// `ERROR: ` 加原消息，嵌套太深之类写 `ERROR: <类型>: <消息>`。Python 会打堆栈的地方（证据文件的类型不对等），
// 这里写一行“崩溃”，退出码 1，契约只比较退出码。
import "@themis/base/harden"; // 第一个 import：赶在其他模块的顶层代码之前设上，按名字起程序不查当前目录（第 77 轮）
import { initFileAttributes } from "@themis/base/native";
import { PyCrash, PyOut } from "@themis/base/pyfmt";
import { PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { redactTokens } from "@themis/base/secrets";
import { LogsError, type ListArgs, type ShowArgs, cmdList, cmdShow } from "@themis/dispatcher/logs";
import { type CatArgs, cmdCat } from "@themis/dispatcher/logs-cat";
import { type SyncAdaptersArgs, cmdSyncAdapters } from "@themis/dispatcher/adapters";
import { type CleanupArgs, type MarkArgs, type WaitArgs, cmdCleanup, cmdMark, cmdWait } from "@themis/dispatcher/attempt-commands";
import { type BaselineArgs, type CheckArgs, type VerdictArgs, cmdBaseline, cmdCheck, cmdVerdict } from "@themis/dispatcher/check-commands";
import { type MetricsArgs, cmdMetrics } from "@themis/dispatcher/metrics";
import { type ReleaseCheckArgs, cmdReleaseCheck } from "@themis/dispatcher/release-check";
import { type DeriveJsonArgs, type PlanContext, type ValidateArgs, cmdDeriveJson, cmdValidate } from "@themis/dispatcher/contract-plan";
import { type SearchArgs, cmdSearch } from "@themis/dispatcher/logs-search";
import { type UsageArgs, cmdUsage } from "@themis/dispatcher/logs-usage";
import { DispatchError } from "@themis/dispatcher/repo";
import { type StatusArgs, cmdStatus } from "@themis/dispatcher/status";
import { type DecisionsArgs, cmdDecisions } from "@themis/dispatcher/decisions-replay";
import { type MutateArgs, cmdMutate } from "@themis/dispatcher/mutate";
import { type PrepareArgs, type PrepareContext, cmdPrepare } from "@themis/dispatcher/prepare";
import type { SessionFactory } from "@themis/dispatcher/run-health";
import { decisionsSession } from "@themis/config/decisions-client";
import { CONFIG_COMMANDS, runConfig } from "@themis/config/cli";
import { bindingTuple, resolveRoleExecutor } from "@themis/config/roles-binding";
import { configErrors } from "@themis/config/roles-check";
import type { UiArgs } from "@themis/ui/main"; // 只有类型，运行时不加载（ui 走下面的动态导入）

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

/** 调度器命令的报错：DispatchError 写 `ERROR: ` 加遮过令牌的消息，其余按崩溃。 */
function dispatchFailure(out: PyOut, error: unknown): number {
  if (error instanceof DispatchError) {
    out.printErr(`ERROR: ${redactTokens(error.message)}`);
    return error.code;
  }
  return crash(out, error);
}

function runDispatcher(out: PyOut, body: () => number): number {
  try {
    return body();
  } catch (error) {
    return dispatchFailure(out, error);
  }
}

/** 决策会话（④b4b，wait --assess、status --assess）：config 包的 decisionsSession，kit 根取启动器的 context。 */
function sessionsFor(args: Record<string, unknown>, out: PyOut): SessionFactory {
  return (config, agentDir, recordPath, point) => decisionsSession(config, agentDir, recordPath, point, { kitRoot: planContext(args).kitRoot, out });
}

async function runDispatcherAsync(out: PyOut, body: () => Promise<number>): Promise<number> {
  try {
    return await body();
  } catch (error) {
    return dispatchFailure(out, error);
  }
}

/**
 * 第 ④b3 片的命令（check、baseline、verdict）：标准输出照 Python 块缓冲，报错与崩溃先写进标准错误，退出前才冲出标准输出
 * （Python 在解释器退出时冲出）。hub 把两路并在一起读，次序要照。
 */
async function runBuffered(body: (out: PyOut) => Promise<number>): Promise<number> {
  const out = new PyOut({ bufferStdout: true });
  try {
    return await body(out);
  } catch (error) {
    return dispatchFailure(out, error);
  } finally {
    out.flush();
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

/** 调度器命令的 context：启动器交来 kit 根与选择文件（Python 的 KERNEL_TS_ROOT.parent 与 read_kernel_impl()）；kit_roles 在这里交进去。 */
function planContext(args: Record<string, unknown>): PlanContext {
  const context = (args["context"] ?? {}) as { kit_root?: string; kernel_impl?: Record<string, string> };
  if (typeof context.kit_root !== "string" || typeof context.kernel_impl !== "object") throw new Error("pyargs 缺少 context.kit_root 或 context.kernel_impl");
  return { kitRoot: context.kit_root, kernelImpl: context.kernel_impl, roles: { resolveRoleExecutor } };
}

/** prepare 的 context：再加本机的 platform.platform() 与 platform.python_version()，写进 meta.json（迁移计划 D1）。 */
function prepareContext(args: Record<string, unknown>): PrepareContext {
  const context = (args["context"] ?? {}) as { python?: unknown };
  if (typeof context.python !== "string") throw new Error("pyargs 缺少 context.python");
  return { ...planContext(args), roles: { resolveRoleExecutor, configErrors, bindingTuple }, platform: hostPlatform(args), python: context.python };
}

/** 本机的 platform.platform()：attempt_origin_notes 比较系统名用（迁移计划 D1，TS 拿不到 Python 的值）。 */
function hostPlatform(args: Record<string, unknown>): string {
  const context = (args["context"] ?? {}) as { platform?: unknown };
  if (typeof context.platform !== "string") throw new Error("pyargs 缺少 context.platform");
  return context.platform;
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
  if (CONFIG_COMMANDS.includes(args.command.join(" "))) {
    try {
      return await runConfig(args as unknown as Parameters<typeof runConfig>[0], out);
    } catch (error) {
      return crash(out, error);
    }
  }
  switch (args.command.join(" ")) {
    case "status":
      return runDispatcherAsync(out, () => cmdStatus(args as unknown as StatusArgs, out, sessionsFor(args, out)));
    case "validate":
      return runDispatcher(out, () => cmdValidate(args as unknown as ValidateArgs, out, planContext(args)));
    case "derive-json":
      return runDispatcher(out, () => cmdDeriveJson(args as unknown as DeriveJsonArgs, out, planContext(args)));
    case "mark":
      return runDispatcher(out, () => cmdMark(args as unknown as MarkArgs, out));
    case "cleanup":
      return runDispatcher(out, () => cmdCleanup(args as unknown as CleanupArgs, out));
    case "wait":
      return runDispatcherAsync(out, () => cmdWait(args as unknown as WaitArgs, out, sessionsFor(args, out)));
    case "decisions":
    case "decisions replay":
      return runDispatcher(out, () => cmdDecisions(args as unknown as DecisionsArgs, out));
    case "check":
      return runBuffered((buffered) => cmdCheck(args as unknown as CheckArgs, buffered, hostPlatform(args)));
    case "baseline":
      return runBuffered((buffered) => cmdBaseline(args as unknown as BaselineArgs, buffered, planContext(args)));
    case "mutate":
      return runBuffered((buffered) => cmdMutate(args as unknown as MutateArgs, buffered, sessionsFor(args, buffered)));
    case "prepare":
      return runBuffered((buffered) => {
        const ctx = prepareContext(args);
        const strict = (config: PyValue, agentDir: string): void => void decisionsSession(config, agentDir, null, null, { kitRoot: ctx.kitRoot, out: buffered }, true);
        return cmdPrepare(args as unknown as PrepareArgs, buffered, ctx, strict);
      });
    case "verdict":
      return runBuffered((buffered) => cmdVerdict(args as unknown as VerdictArgs, buffered, hostPlatform(args)));
    case "metrics":
      return runDispatcher(out, () => cmdMetrics(args as unknown as MetricsArgs, out));
    case "release-check":
      return runDispatcher(out, () => cmdReleaseCheck(args as unknown as ReleaseCheckArgs, out, planContext(args).kitRoot));
    case "sync-adapters":
      return runDispatcher(out, () => cmdSyncAdapters(args as unknown as SyncAdaptersArgs, out));
    case "logs list":
      return runLogs(out, () => cmdList(args as unknown as ListArgs, out));
    case "logs show":
      return runLogs(out, () => cmdShow(args as unknown as ShowArgs, out));
    case "logs cat":
      return runLogs(out, () => cmdCat(args as unknown as CatArgs, out));
    case "logs search":
      return runLogs(out, () => cmdSearch(args as unknown as SearchArgs, out));
    case "logs usage":
      return runLogs(out, () => cmdUsage(args as unknown as UsageArgs, out));
    case "ui":
      // 只有 TS 实现的命令（桌面端第 7 版 T6，调度器第 73 轮无条件转交）。动态导入：@themis/ui 不在内核禁区里、经 hub
      // 派给执行器，静态导入的话它一坏，status、logs 也跟着起不来
      try {
        const { runUi } = await import("@themis/ui/main");
        return await runUi(args as unknown as UiArgs);
      } catch (error) {
        return crash(out, error);
      }
    default:
      out.printErr(`ERROR: TS 实现还没有这条命令：${args.command.join(" ")}`);
      return 2;
  }
}

process.exitCode = await main(process.argv.slice(2));
