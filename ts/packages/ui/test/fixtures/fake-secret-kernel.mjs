// 凭据录入用例的内核 CLI 子进程替身（桌面端 T21）：服务把它当成 `<python> <kernel> --repo <仓库> <argv…>` 起起来，python 是
// 跑测试的这个 Node。照 fake-kernel.mjs 的做法把每次调用的 argv 与开始/结束时间记进 FAKE_KERNEL_REPORT（同一份报告、
// 同一套字段），并可以起一个孙进程把 pid 写进 FAKE_KERNEL_PIDFILE（取消与超时之后 pid 不在的用例用它）。两支：
//   - config secret set <name>：先往 stderr 写一行握手 JSON（{"url": …, "note": …}，地址来自 FAKE_SECRET_URL，缺省是
//     一个合格的一性页面地址）并 flush；再等门文件 FAKE_SECRET_GATE 出现（没有这个环境变量就立刻往下；设了就一直等）；
//     最后在 stdout 打一行结果 JSON（name/stored/backend/error 与恒为 null 的 verified，退出码取 FAKE_KERNEL_EXIT）。
//   - config secret check <name>：可以先卡在门文件 FAKE_SECRET_CHECK_GATE 上等放行；输出一行 JSON
//     （name、source、store_mode、system_backend，与内核的一行 JSON 同形状，投影由服务做）。
// 别的 argv 一律回显成 JSON（读路由与 SSE 的 status 走这条）。FAKE_SECRET_SILENT=1 时 secret set 不打握手行
// （「握手之前子进程就结束」的用例用它）。
import { appendFileSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";

const raw = process.argv.slice(2);
const at = raw.indexOf("--repo");
const argv = at >= 0 ? [...raw.slice(0, at), ...raw.slice(at + 2)] : [...raw];

const note = (event, extra) => {
  const path = process.env["FAKE_KERNEL_REPORT"];
  if (path === undefined) return;
  appendFileSync(
    path,
    `${JSON.stringify({
      kind: "run",
      event,
      pid: process.pid,
      argv,
      at: Date.now(),
      has_typesafe_api_key: Object.keys(process.env).some((name) => name.toUpperCase() === "TYPESAFE_API_KEY"),
      codekit_actor: process.env["CODEKIT_ACTOR"] ?? null,
      has_no_cwd_in_path: Object.keys(process.env).includes("NoDefaultCurrentDirectoryInExePath"),
      ...extra,
    })}\n`,
  );
};

note("begin");
process.on("exit", (code) => note("end", { exit: code ?? null }));

const number = (name) => {
  const value = process.env[name];
  return value === undefined || value === "" ? null : Number(value);
};
const sleepSync = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

/** 等门文件出现（设了才等；没有这个环境变量就不等）。 */
const waitFor = (name) => {
  const gate = process.env[name];
  if (gate === undefined || gate === "") return;
  while (!existsSync(gate)) sleepSync(50);
};

/** 起一个孙进程并把它的 pid 写进 FAKE_KERNEL_PIDFILE（进程树的用例用）。 */
const spawnGrandchild = () => {
  const pidfile = process.env["FAKE_KERNEL_PIDFILE"];
  if (pidfile === undefined || pidfile === "") return;
  const child = spawn(process.execPath, ["-e", "setTimeout(() => {}, 300000)"], { detached: true, stdio: "ignore" });
  child.unref();
  appendFileSync(pidfile, `${child.pid}\n`);
};

/** 缺省的合格握手地址：127.0.0.1 加一个随机端口，令牌是 32 个 base64url 字符。 */
const defaultUrl = () => {
  const token = Buffer.from(`t21-fake-secret-${process.pid}-${Date.now()}`).toString("base64url").slice(0, 32);
  return `http://127.0.0.1:${40000 + (process.pid % 20000)}/${token}`;
};

if (argv[0] === "config" && argv[1] === "secret" && argv[2] === "set") {
  const name = argv[3] ?? "EXAMPLE_KEY";
  spawnGrandchild();
  if (process.env["FAKE_SECRET_SILENT"] !== "1") {
    const url = process.env["FAKE_SECRET_URL"] ?? defaultUrl();
    process.stderr.write(`${JSON.stringify({ url, note: "在这台电脑的浏览器里打开，粘贴后保存；只能用一次" })}\n`);
  }
  // 等门文件（设了才等）；没有门文件时停留一会儿再往下——真内核的页面会一直开着，这里让轮询读得到握手行
  const gate = process.env["FAKE_SECRET_GATE"];
  if (gate === undefined || gate === "") sleepSync(600);
  else while (!existsSync(gate)) sleepSync(50);
  const exit = number("FAKE_KERNEL_EXIT") ?? 0;
  if (exit === 0) {
    const forced = process.env["FAKE_SECRET_STDOUT"];
    process.stdout.write(forced ?? `${JSON.stringify({ name, stored: true, backend: "file", verified: null })}\n`);
  } else {
    process.stdout.write(`${JSON.stringify({ name, stored: false, backend: null, error: "timeout", verified: null })}\n`);
    process.stderr.write("ERROR: 等页面超时：什么也没存\n");
  }
  process.exit(exit);
}

if (argv[0] === "config" && argv[1] === "secret" && argv[2] === "check") {
  const name = argv[3] ?? "EXAMPLE_KEY";
  waitFor("FAKE_SECRET_CHECK_GATE");
  process.stdout.write(`${JSON.stringify({ name, source: "file", store_mode: "file", system_backend: null })}\n`);
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}

process.stdout.write(`${JSON.stringify({ argv })}\n`);
process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
