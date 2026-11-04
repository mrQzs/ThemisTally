// hub 命令的 TS 一侧入口（迁移第 ⑤j3 片）：选择文件的 hub 是 ts 时，kit_hub.py 的 main 把 argparse 解析好的参数经 cli/src/main.ts 交到
// 这里。pyargs 的 command 是 ["hub", 子命令路径…]，namespace 是 Namespace 去掉 func，context 是启动器给的 Python 与 kit_hub.py 的路径。
// 报错照 kit_hub.main：HubError、DispatchError 打印“ERROR: ”加消息，交回它的 code；别的异常交给 main.ts 按崩溃处理。
import type { PyOut } from "@themis/base/pyfmt";
import { DispatchError } from "@themis/dispatcher/repo";
import {
  type CommandArgs, type CommandOut, cmdExecRecheck, cmdInit, cmdMetrics, cmdSend, cmdStatus, cmdTake, cmdTaskAfter, cmdTaskBudget,
  cmdTaskCleanup, cmdTaskClose, cmdTaskNew, cmdTaskRebase, cmdTaskUnstick,
} from "./commands.ts";
import { HubError } from "./errors.ts";
import { cmdExclusive, cmdOwnerSweep, cmdRun, setKitHub } from "./runner.ts";
import { setKernelPython } from "./runpd.ts";

type HubCommand = (args: CommandArgs, out: CommandOut) => number | Promise<number>;

/** kit_hub.HUB_COMMANDS 的子命令路径（空格连起来）→ 命令函数；契约核两边的路径一致。 */
export const HUB_COMMANDS: ReadonlyMap<string, HubCommand> = new Map<string, HubCommand>([
  ["init", cmdInit],
  ["task new", cmdTaskNew],
  ["task close", cmdTaskClose],
  ["task rebase", cmdTaskRebase],
  ["task after", cmdTaskAfter],
  ["task unstick", cmdTaskUnstick],
  ["task budget", cmdTaskBudget],
  ["task cleanup", cmdTaskCleanup],
  ["send", cmdSend],
  ["exec-recheck", cmdExecRecheck],
  ["take", cmdTake],
  ["metrics", cmdMetrics],
  ["status", cmdStatus],
  ["run", cmdRun],
  ["exclusive", cmdExclusive],
  ["owner-sweep", cmdOwnerSweep],
]);

/** 启动器给的 context 里 hub 要用的两项：起换代、主任务 runner、owner-sweep 的 Python（sys.executable）与 kit_hub.py 的路径。 */
export interface HubContext {
  readonly executable: string;
  readonly kit_hub: string;
}

/** 换代、主任务 runner、owner-sweep 照启动器给的这两项起（runHub 先调；契约不经启动器时直接调）。 */
export function useLauncherContext(context: HubContext): void {
  setKernelPython(context.executable);
  setKitHub(context.kit_hub);
}

export async function runHub(path: readonly string[], namespace: CommandArgs, context: HubContext, out: PyOut): Promise<number> {
  const command = HUB_COMMANDS.get(path.join(" "));
  if (command === undefined) {
    out.printErr(`ERROR: TS 实现还没有这条命令：hub ${path.join(" ")}`);
    return 2;
  }
  useLauncherContext(context);
  try {
    return await command(namespace, out);
  } catch (error) {
    if (!(error instanceof HubError || error instanceof DispatchError)) throw error;
    out.printErr(`ERROR: ${error.message}`);
    return error.code;
  }
}
