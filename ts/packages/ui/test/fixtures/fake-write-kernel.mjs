// 写链路用例的内核 CLI 子进程替身（桌面端 T19 第 5 片）：服务把它当成 `<python> <kernel> --repo <仓库> <argv…>` 起起来，
// python 是跑测试的这个 Node。照 fake-kernel.mjs 的做法把每次调用的 argv、环境三问与开始/结束时间记进 FAKE_KERNEL_REPORT
// （同一份报告、同一套字段；另加 expect_state 供 S9 核对令牌）。两支：
//   - 预览一支（argv 里有 --dry-run）：把 FAKE_WRITE_PREVIEW 给的 JSON 打到 stdout（缺省是合同 §2.1 写死的那份，
//     action=role.set、state=v1;config=<64 个 0>、needs_yes=false；用例可经环境变量覆盖成不合格的预览触发 500）。
//   - 执行一支：按 FAKE_WRITE_PLAN 走——ok（退出 0，stdout 一行「已写入」）、stale（退出 4，stderr 一行 ERROR）、
//     audit-fail（退出 1，stdout「已设置…」、stderr 一行 ERROR）、pause（先往 stdout 写 FAKE_WRITE_BEGIN，再等门文件
//     FAKE_WRITE_GATE 出现，然后往 stdout 写 WARN、往 stderr 写 ERROR，退出 FAKE_KERNEL_EXIT，缺省 1）。
import { appendFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";

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

/** config 的两级子命令到 action 的映射（role set、preset use|save|remove、profile add|edit|remove、runtime add|remove）。 */
const SUBACTIONS = {
  role: { set: "role.set" },
  preset: { use: "preset.use", save: "preset.save", remove: "preset.remove" },
  profile: { add: "profile.add", edit: "profile.edit", remove: "profile.remove" },
  runtime: { add: "runtime.add", remove: "runtime.remove" },
};

/** 由预览 argv 推导 action（plugins enable|disable → plugin.enable|disable；config rollback → config.rollback；其余查 SUBACTIONS）。 */
function deriveAction(items) {
  if (items[0] === "plugins") return `plugin.${items[1]}`;
  if (items[0] !== "config") return null;
  if (items[1] === "rollback") return "config.rollback";
  return SUBACTIONS[items[1]]?.[items[2]] ?? null;
}

/** 由种子确定性生成 64 位小写十六进制（每条 action 的每段各不相同，供「令牌不外泄」按段搜）。 */
function hex64(seed) {
  return createHash("sha256").update(seed).digest("hex");
}

/** 每个 action 的 state 令牌：runtime add 带 --command 与 runtime remove 给 config+local 两段，其余只 config 段。 */
function stateFor(action, items) {
  const config = hex64(`config:${action}`);
  const twoSegments = action === "runtime.remove" || (action === "runtime.add" && items.some((part) => part.startsWith("--command=")));
  return twoSegments ? `v1;config=${config};local=${hex64(`local:${action}`)}` : `v1;config=${config}`;
}

// 慢门：FAKE_WRITE_SLOW_GATE 指向的门文件存在时，每次调用先睡 FAKE_WRITE_SLEEP_MS（缺省 15000）毫秒再干活
const slowGate = process.env["FAKE_WRITE_SLOW_GATE"];
const slowMs = number("FAKE_WRITE_SLEEP_MS") ?? 15000;
if (slowGate !== undefined && slowGate !== "" && existsSync(slowGate) && slowMs > 0) sleepSync(slowMs);

// 预览一支：argv 里有 --dry-run
if (argv.includes("--dry-run")) {
  const override = process.env["FAKE_WRITE_PREVIEW"];
  if (override !== undefined) {
    process.stdout.write(`${override}\n`);
  } else {
    const action = deriveAction(argv);
    if (action === "role.set") {
      // role.set 仍用合同 §2.1 写死的默认预览（S14 的放行/被遮断言对着它）
      process.stdout.write(`${DEFAULT_PREVIEW}\n`);
    } else {
      process.stdout.write(`${JSON.stringify({
        dry_run: true, action, changed: true,
        resources: [{ resource: "demo", changed: true, changed_keys: ["demo"] }],
        binding_changes: [], running_attempts: [], unreadable: [],
        needs_yes: false, warnings: [], notes: [], state: stateFor(action, argv),
      })}\n`);
    }
  }
  process.exit(number("FAKE_KERNEL_EXIT") ?? 0);
}

// 读一支：argv 里有 --json 且没有 --dry-run（读路由起的内核子进程）：打一份 JSON 让读路由回 200
if (argv.includes("--json")) {
  process.stdout.write("{}\n");
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
