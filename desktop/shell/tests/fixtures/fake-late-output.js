// 迟到输出夹具：中间进程（本文件）立刻以 0 退出，孙进程（detached + unref）约 300ms 后
// 才往 stdout 写一行固定文本再退出。孙进程用 stdio:"inherit" 继承中间进程的 stdout，
// 所以中间进程 exit 之后管道仍开着：旧实现（在 exit 取输出）拿到空 stdout，新实现（在
// close 取输出）等管道关闭才给结果，此时输出已收全。用来验证 runProcess 必须在 close 里兑现。
const { spawn } = require("node:child_process");

const LINE = "late-output-from-grandchild\n";

const grandchild = spawn(
  process.execPath,
  ["-e", "setTimeout(() => { process.stdout.write(" + JSON.stringify(LINE) + "); }, 300);"],
  { detached: true, windowsHide: true, stdio: "inherit" },
);
// 让孙进程活过中间进程：detached 让它在自己的进程组里，unref 让父进程的事件轮不等它
grandchild.unref();

// 中间进程立刻退出，不等孙进程
process.exit(0);
