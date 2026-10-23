// helper.test.ts 的取消场景，单独一个 Node 进程：由测试以 CREATE_NO_WINDOW 起，有自己的（不显示窗口的）控制台。
// 进程监督有毛病时（例如子进程没有另起进程组），CTRL_BREAK 会广播给整个控制台：放在自己的控制台里，波及的只是本进程，
// 不会打到跑测试的 vitest 与外层的 mutate、shell（第 72 轮的起因）。结果以一行 JSON 写到 stdout。
import { join } from "node:path";
import { runSupervised } from "../../src/supervise.ts";

const [dir, py] = process.argv.slice(2) as [string, string];
const before = process.listenerCount("SIGINT");
const controller = new AbortController();
let during = -1;
const env = Object.entries(process.env).filter((pair): pair is [string, string] => typeof pair[1] === "string");
const started = performance.now();
const result = await runSupervised([py, "-c", "import time\nfor _ in range(1200): time.sleep(0.1)"], {
  cwd: dir, env, timeout: 20, grace: 2, signal: controller.signal, handleSignals: false,
  stdout: { path: join(dir, "out"), how: "create-new" }, stderr: { path: join(dir, "err"), how: "create-new" },
  onSpawn: () => {
    during = process.listenerCount("SIGINT");
    setTimeout(() => controller.abort(), 300);
  },
});
process.stdout.write(`${JSON.stringify({ result, before, during, elapsed: performance.now() - started })}\n`);
