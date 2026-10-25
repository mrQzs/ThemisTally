// 内核 CLI 的子进程替身（桌面端 T16 第 2 片）：服务把它当成 `<python> <kernel> --repo <仓库> <argv…>` 起起来，python 是
// 跑测试的这个 Node。两件事：
//   1. 按 FAKE_KERNEL_REPORT（文件路径）逐次报告环境三问——有没有 TYPESAFE_API_KEY（按名字大写后比较）、
//      CODEKIT_ACTOR 的值、有没有 NoDefaultCurrentDirectoryInExePath；连同 argv 与开始/结束时间记一行 JSON。
//      从不输出任何凭据变量的值（T5/D04：服务起的每一个内核子进程都拿不到决策 API 的 key）。
//   2. 按 argv 演对应的只读命令（--version、status、logs list/show/cat/usage、config show/profile show/secret check，
//      其余回显 argv），也可用 FAKE_KERNEL_JSON 直接给定 stdout、FAKE_KERNEL_STDERR 给定 stderr、
//      FAKE_KERNEL_EXIT 给定退出码、FAKE_KERNEL_SLEEP_MS 睡一会儿（时限与取消的用例用它）。
// 第 3 片加 FAKE_KERNEL_PLAN（按 argv 前缀之外再按计划给行为）：
//   - flood：起一个孙进程之后洪泛 stdout（H1 的输出上限边写边看：轮询抓到超限就中止整棵树，孙进程也不在了）；
//   - hang / spawn-grandchild：起一个孙进程（FAKE_KERNEL_PIDFILE）之后一直睡到被杀（取消与超时的进程树用例）；
//   - sleep：睡 FAKE_KERNEL_SLEEP_MS 之后输出 FAKE_KERNEL_JSON（作业的终态用例）；
//   - status 分支认 FAKE_KERNEL_STATUS_FILE：把它的内容当 status --json 的 stdout（SSE 的替身 status 读夹具文件）。
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
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

/** 起一个孙进程并把它的 pid 写进 FAKE_KERNEL_PIDFILE（取消/超时/输出超限的进程树用例用它）。 */
const spawnGrandchild = () => {
  const pidfile = process.env["FAKE_KERNEL_PIDFILE"];
  if (pidfile === undefined || pidfile === "") return;
  const child = spawn(process.execPath, ["-e", "setTimeout(() => {}, 300000)"], { detached: true, stdio: "ignore" });
  child.unref();
  writeFileSync(pidfile, String(child.pid));
};

// FAKE_KERNEL_PLAN：按计划给行为（优先于下面的 argv 分支）
const plan = process.env["FAKE_KERNEL_PLAN"];
if (plan === "flood") {
  // 洪泛 stdout：起孙进程之后一直写，直到轮询抓到超限把整棵树中止（H1）
  spawnGrandchild();
  const chunk = "x".repeat(65536);
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    process.stdout.write(chunk);
    await new Promise((done) => setImmediate(done)); // 让出：中止信号才送得进来
  }
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}
if (plan === "hang" || plan === "spawn-grandchild") {
  // 一直睡到被杀（取消与超时都走这条；起了孙进程的话整棵树一起结束）。用 setTimeout 挂住事件循环，
  // 不要用永不 resolve 的 Promise——那会触发 Node 的「unsettled top-level await」直接退出。
  spawnGrandchild();
  await new Promise((done) => setTimeout(done, 300000));
}
if (plan === "sleep") {
  await new Promise((done) => setTimeout(done, number("FAKE_KERNEL_SLEEP_MS") ?? 1000));
  process.stdout.write(`${process.env["FAKE_KERNEL_JSON"] ?? "{}"}\n`);
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}

const sleepMs = number("FAKE_KERNEL_SLEEP_MS");
if (sleepMs !== null && Number.isFinite(sleepMs) && sleepMs > 0) {
  await new Promise((done) => setTimeout(done, sleepMs));
}

const stderrText = process.env["FAKE_KERNEL_STDERR"];
if (stderrText !== undefined && stderrText !== "") process.stderr.write(`${stderrText}\n`);

const forced = process.env["FAKE_KERNEL_JSON"];
if (forced !== undefined) {
  process.stdout.write(`${forced}\n`);
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}

let payload;
if (argv[0] === "--version") {
  payload = "pi_dispatch 2.12.0";
} else if (argv[0] === "status") {
  // SSE 的替身 status：认 FAKE_KERNEL_STATUS_FILE，把它的内容当 stdout
  const statusFile = process.env["FAKE_KERNEL_STATUS_FILE"];
  if (statusFile !== undefined && statusFile !== "") {
    payload = readFileSync(statusFile, "utf8").replace(/\r?\n$/, "");
  } else {
    payload = JSON.stringify([{ task: "demo-task", attempt: "attempt-001", state: "done" }]);
  }
} else if (argv[0] === "logs" && argv[1] === "cat") {
  payload = JSON.stringify({
    path: argv[3],
    mode: "text",
    text: `第 1 页：${argv[3]}\n`,
    next_cursor: "fake-cursor-0001",
    done: false,
  });
} else if (argv[0] === "logs" && argv[1] === "show") {
  payload = JSON.stringify({ task: argv[2], state: "done", evidence: [] });
} else if (argv[0] === "logs" && argv[1] === "usage") {
  payload = JSON.stringify({ totals: { tokens: 7 }, by_task: [] });
} else if (argv[0] === "config" && argv[1] === "secret" && argv[2] === "check") {
  payload = JSON.stringify({
    name: argv[3],
    source: "env",
    store_mode: "system",
    system_backend: "windows-credential-manager",
    file_dir: "C:/fake-credential-store",
  });
} else if (argv[0] === "config" && argv[1] === "show") {
  payload = JSON.stringify({
    config_path: "C:/fake/.agent/dispatch.config.json",
    exists: true,
    errors: [],
    keys: [
      { key: "env_remove", value: ["KEEP_ONE"], source: "config", default: [], description: "" },
      { key: "decisions", value: { api_key_env: "TYPESAFE_API_KEY" }, source: "config", default: null, description: "" },
    ],
    decisions: {
      mode: "off",
      env_var_name: "TYPESAFE_API_KEY",
      secret: {
        name: "TYPESAFE_API_KEY",
        source: "none",
        store_mode: "off",
        system_backend: null,
        file_dir: "C:/fake",
      },
    },
  });
} else if (argv[0] === "config" && argv[1] === "profile") {
  payload = JSON.stringify({ profiles: [{ id: "execution", credential_env: ["TYPESAFE_API_KEY", "OTHER_KEY"] }] });
} else {
  payload = JSON.stringify({ argv });
}
process.stdout.write(`${payload}\n`);
process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
