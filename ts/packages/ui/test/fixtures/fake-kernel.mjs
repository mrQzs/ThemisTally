// 内核 CLI 的子进程替身（桌面端 T16 第 2 片）：服务把它当成 `<python> <kernel> --repo <仓库> <argv…>` 起起来，python 是
// 跑测试的这个 Node。两件事：
//   1. 按 FAKE_KERNEL_REPORT（文件路径）逐次报告环境三问——有没有 TYPESAFE_API_KEY（按名字大写后比较）、
//      CODEKIT_ACTOR 的值、有没有 NoDefaultCurrentDirectoryInExePath；连同 argv 与开始/结束时间记一行 JSON。
//      从不输出任何凭据变量的值（T5/D04：服务起的每一个内核子进程都拿不到决策 API 的 key）。
//   2. 按 argv 演对应的只读命令（--version、status、logs list/show/cat/usage、config show/profile show/secret check，
//      其余回显 argv），也可用 FAKE_KERNEL_JSON 直接给定 stdout、FAKE_KERNEL_STDERR 给定 stderr、
//      FAKE_KERNEL_EXIT 给定退出码、FAKE_KERNEL_SLEEP_MS 睡一会儿（时限与取消的用例用它）。
import { appendFileSync } from "node:fs";

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
  payload = JSON.stringify([{ task: "demo-task", attempt: "attempt-001", state: "done" }]);
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
