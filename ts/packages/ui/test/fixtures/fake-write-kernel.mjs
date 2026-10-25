// 写链路用例的内核 CLI 子进程替身（桌面端 T19 第 5 片）：服务把它当成 `<python> <kernel> --repo <仓库> <argv…>` 起起来，
// python 是跑测试的这个 Node。照 fake-kernel.mjs 的做法把每次调用的 argv、环境三问与开始/结束时间记进 FAKE_KERNEL_REPORT
// （同一份报告、同一套字段；另加 expect_state 供 S9 核对令牌）。两支：
//   - 预览一支（argv 里有 --dry-run）：把 FAKE_WRITE_PREVIEW 给的 JSON 打到 stdout（缺省是合同 §2.1 写死的那份，
//     action=role.set、state=v1;config=<64 个 0>、needs_yes=false；用例可经环境变量覆盖成不合格的预览触发 500）。
//   - 执行一支：按 FAKE_WRITE_PLAN 走——ok（退出 0，stdout 一行「已写入」）、stale（退出 4，stderr 一行 ERROR）、
//     audit-fail（退出 1，stdout「已设置…」、stderr 一行 ERROR）、pause（先往 stdout 写 FAKE_WRITE_BEGIN，再等门文件
//     FAKE_WRITE_GATE 出现，然后往 stdout 写 WARN、往 stderr 写 ERROR，退出 FAKE_KERNEL_EXIT，缺省 1）。
import { appendFileSync, existsSync } from "node:fs";

const raw = process.argv.slice(2);
const at = raw.indexOf("--repo");
const argv = at >= 0 ? [...raw.slice(0, at), ...raw.slice(at + 2)] : [...raw];

const expectState = argv.find((part) => part.startsWith("--expect-state=")) ?? null;

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
      expect_state: expectState === null ? null : expectState.slice("--expect-state=".length),
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

/** 合同 §2.1 写死的预览 JSON（role.set；含该放行的名字、该遮的令牌形状与敏感键 api_key）。 */
const DEFAULT_PREVIEW = JSON.stringify({
  dry_run: true,
  action: "role.set",
  changed: true,
  resources: [{ resource: "config/roles/execution", changed: true, changed_keys: ["binding"] }],
  binding_changes: [
    {
      role: "execution",
      before: { mode: "manual", profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null },
      after: { mode: "manual", profile: "demo-profile", runtime: null, adapter: "claude-code", provider: "demo-provider", model: "demo-model", thinking: null },
    },
    {
      role: "contract",
      before: { mode: "manual", profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null },
      after: { mode: "manual", profile: "sk-abcdefghijklmnopqrstuvwxyz012345", runtime: null, adapter: null, provider: null, model: null, thinking: null },
    },
  ],
  running_attempts: [],
  unreadable: [],
  needs_yes: false,
  warnings: ["demo warning"],
  notes: ["demo note", "sk-abcdefghijklmnopqrstuvwxyz012345"],
  api_key: "sk-abcdefghijklmnopqrstuvwxyz012345",
  state: `v1;config=${"0".repeat(64)}`,
});

// 预览一支：argv 里有 --dry-run
if (argv.includes("--dry-run")) {
  process.stdout.write(`${process.env["FAKE_WRITE_PREVIEW"] ?? DEFAULT_PREVIEW}\n`);
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}

// 执行一支：按 FAKE_WRITE_PLAN 走
const plan = process.env["FAKE_WRITE_PLAN"] ?? "ok";
if (plan === "stale") {
  // 内核报「在预览之后被改过」：退出码 4（EXIT_STALE），stderr 一行 ERROR
  process.stderr.write("ERROR: 配置在预览之后被改过：什么也没写，重新预览\n");
  process.exit(4);
}
if (plan === "audit-fail") {
  // 写成功了但审计记录不全：退出 1，stdout「已设置…」、stderr 一行 ERROR（U19）
  process.stdout.write("已设置 execution = manual\n");
  process.stderr.write("ERROR: 已写入配置，但审计记录不全\n");
  process.exit(1);
}
if (plan === "pause") {
  // 先往 stdout 写 FAKE_WRITE_BEGIN，再等门文件 FAKE_WRITE_GATE 出现（断开不取消与队列占位的用例用它）
  process.stdout.write(`${process.env["FAKE_WRITE_BEGIN"] ?? "FAKE_WRITE_BEGIN"}\n`);
  const gate = process.env["FAKE_WRITE_GATE"];
  if (gate !== undefined && gate !== "") {
    while (!existsSync(gate)) sleepSync(50);
  }
  process.stdout.write("WARN  已写入 execution = manual\n");
  process.stderr.write("ERROR: 审计记录不全\n");
  process.exit(number("FAKE_KERNEL_EXIT") ?? 1);
}
// ok（默认）：退出 0，stdout 一行「已写入」
process.stdout.write("已写入 execution = manual\n");
process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
