// 内核调调度器与门禁的 pytest（迁移第 ⑤e2a 片）：kit_hub.py 的 run_pd、kernel_env、kernel_pytest_env、KERNEL_PYTEST。
// Python 用自己的 sys.executable；TS 的 hub 没有这个值，由入口设定（照 ui 的先例：启动器转交时带 python=sys.executable，⑤j 接），没设就
// 抛错，不猜（设计稿第 2 节第 1 条）。
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PyCrash, pyPercentD } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { purePathStr } from "@themis/base/pypath";
import { runSupervised } from "@themis/base/supervise";
import { argvImpl } from "@themis/dispatcher/kernel-impl";
import { pyEnviron } from "@themis/dispatcher/pi-cli";
import { TOOL_VERSION } from "@themis/dispatcher/prepare";
import { DispatchError } from "@themis/dispatcher/repo";
import { DECISIONS_KEY_ENV } from "./constants.ts";
import { workerEnv } from "./delivery.ts";
import { SCRIPTS_DIR } from "./kernel.ts";
import type { Hub } from "./mailbox.ts";

/** pi_dispatch 的 KERNEL_IMPL_PATH：内核目录下的选择文件，不是 hub 管的仓库下的（待办第 26 项）。 */
export const KERNEL_IMPL_PATH = purePathStr(SCRIPTS_DIR, "kernel-impl.json");

let python: string | null = null;

/** 设定 run_pd 与 KERNEL_PYTEST 用的 Python（kit_hub 的 sys.executable）。 */
export function setKernelPython(path: string): void {
  python = path;
}

export function kernelPython(): string {
  if (python === null) throw new Error("没有设定内核用的 Python（run_pd、KERNEL_PYTEST 要用）：由 hub 的入口设定");
  return python;
}

/** KERNEL_PYTEST：-p no:cacheprovider，同一个 worktree 连着收集几次也不留 .pytest_cache。 */
export const kernelPytest = (): string[] => [kernelPython(), "-m", "pytest", "-p", "no:cacheprovider"];

/** 内核调起的调度器子进程：dict(os.environ)（Windows 上名字是大写），只去掉决策 API 的 key（调度器自己的决策提问本来就是 off）。 */
export function kernelEnv(): Map<string, string> {
  const env = pyEnviron();
  for (const name of [...env.keys()]) if (name.toUpperCase() === DECISIONS_KEY_ENV) env.delete(name);
  return env;
}

/** 门禁测试的 pytest：工人的环境，另加 PYTHONDONTWRITEBYTECODE（断言改写不留 __pycache__）。 */
export function kernelPytestEnv(): Map<string, string> {
  const env = workerEnv();
  env.set("PYTHONDONTWRITEBYTECODE", "1");
  return env;
}

/**
 * run_pd：在仓库里跑一条调度器命令，交回（退出码，标准输出与标准错误合在一起的文字）。超时交回 124，不记账本（Python 在记之前就
 * return 了）；Python 在 Windows 上超时后还会等所有握着管道的进程退出，这里经 runSupervised 用 Job 结束整棵树、按时交回（设计稿第 2 节
 * 第 3 条，迁移计划第 10 节）。stdin 接空设备（runSupervised 的做法；调度器的这几条命令不读 stdin）。implPath 只给契约用：换一个坏的
 * 选择文件，看账本记成 invalid。
 */
export async function runPd(hub: Hub, args: readonly string[], timeout = 600, implPath = KERNEL_IMPL_PATH): Promise<[number, string]> {
  const cmd = [kernelPython(), purePathStr(SCRIPTS_DIR, "pi_dispatch.py"), "--repo", purePathStr(hub.repo), ...args];
  const dir = mkdtempSync(join(tmpdir(), "themis-run-pd-"));
  const out = join(dir, "output");
  let code: number;
  let text: string;
  try {
    const result = await runSupervised(cmd, {
      cwd: hub.repo, env: [...kernelEnv()], stdout: { path: out, how: "create-new" }, stderr: "stdout", timeout, grace: 0, handleSignals: false,
    });
    if (result.timed_out) return [124, `超时（${pyPercentD(timeout)} 秒）：${args.join(" ")}`];
    if (result.spawn_error !== null) throw new PyCrash("OSError", result.spawn_error);
    code = result.exit_code as number;
    text = pyDecodeUtf8Replace(readFileSync(out));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  let impl: string;
  try { // 第 64 轮：记下是哪一套实现回答的；选择文件坏了时调度器自己就拒绝运行
    impl = argvImpl(args, null, implPath);
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    impl = "invalid";
  }
  await hub.appendEvent("dispatcher.called", [["args", [...args]], ["exit_code", BigInt(code)], ["impl", impl], ["tool_version", TOOL_VERSION]]);
  return [code, text];
}
