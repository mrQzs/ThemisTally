// 进程是否还在：pi_dispatch.pid_alive 的 TS 实现（迁移第 ① 步，目录锁的接管判断用它）。
//   pid 为 0 或没有：null（不知道）
//   Windows：tasklist /FI "PID eq <pid>" /NH，输出里有这个编号就是 true；tasklist 跑不起来或非 0 退出为 null
//   POSIX：kill(pid, 0)，ESRCH 为 false，EPERM（进程在、只是没权限）为 true
import { spawnSync } from "node:child_process";

export function pidAlive(pid: number | null | undefined): boolean | null {
  if (!pid) return null;
  if (process.platform === "win32") {
    const done = spawnSync("tasklist", ["/FI", `PID eq ${pid}`, "/NH"], { encoding: "utf8", timeout: 20_000 });
    if (done.error || done.status !== 0) return null;
    return done.stdout.split(/\s+/).includes(String(pid));
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}
