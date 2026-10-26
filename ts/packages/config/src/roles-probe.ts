// kit_roles.py 里会运行本机 CLI 的配置中心命令（迁移第 ③d 片）：runtime scan [--add]、runtime probe、models、
// doctor [--record]。只运行只读探测（--version、--help、--list-models、auth check --no-refresh），不调用模型；子进程的环境
// 是 child_env(config)，经 run_capture 起（@themis/dispatcher/pi-cli）。输出照 Python 的 print 与 "%-Ns" 逐字。
import { statSync } from "node:fs";
import { pyTruthy } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { osPathSplit } from "@themis/base/pypath";
import { codePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pyWhich } from "@themis/base/pyshutil";
import { redactSecrets } from "@themis/base/secrets";
import { ensureArgvSafe } from "@themis/dispatcher/argv";
import { allowedExecutorCheck, bindingRecordRel, loadBindingRecord } from "@themis/dispatcher/executor";
import { REQUIRED_PI_FLAGS, RESOURCE_FLAGS, childEnv, listModelsEmptyReason, listModelsLines, parseHelp, piModelReadiness, runCapture } from "@themis/dispatcher/pi-cli";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE } from "@themis/dispatcher/repo";
import { PLAN_KEY_RE } from "@themis/dispatcher/status";
import { ADAPTERS, adapterOf, shownValue } from "./roles-check.ts";
import { type LocalRepo, runtimeCommand, shownCommand } from "./roles-local.ts";
import { type RolesEnv, mapping, openChecked, padRight, printJson, roleRows, roleText, text } from "./roles-commands.ts";
import { withConfigTransaction } from "./transaction.ts";
import { ConfigError } from "./validate.ts";

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
type Env = ReadonlyMap<string, string>;

interface HelpProbe {
  readonly exit_code: number;
  readonly thinking_levels: string[];
  readonly missing_flags: string[];
}

async function probeVersion(command: readonly string[], env: Env): Promise<[number, string]> {
  ensureArgvSafe(command); // 本机文件给出的批处理包装：参数含特殊字符时不运行（D3）
  const [code, out, err] = await runCapture([...command, "--version"], { env, timeout: 30 });
  const first = pySplitlines(redactSecrets(pyStrip(out || err))); // CLI 的输出照 doctor 脱敏
  return [code, first[0] ?? ""];
}

async function probeHelp(command: readonly string[], env: Env): Promise<HelpProbe> {
  const [code, out, err] = await runCapture([...command, ...RESOURCE_FLAGS, "--help"], { env, timeout: 90 });
  const info = parseHelp(out + err);
  return {
    exit_code: code,
    thinking_levels: info.thinking_levels,
    missing_flags: [...REQUIRED_PI_FLAGS, "--no-context-files"].filter((flag) => !info.flags.includes(flag)),
  };
}

const helpValue = (help: HelpProbe): PyDict =>
  new Map<string, PyValue>([["exit_code", BigInt(help.exit_code)], ["thinking_levels", help.thinking_levels], ["missing_flags", help.missing_flags]]);

// --- runtime scan | probe ----------------------------------------------------------------------------

async function runtimeScan(env: RolesEnv): Promise<number> {
  const { ctx, config } = openChecked(env);
  const [childEnvironment] = childEnv(config);
  const found: PyDict[] = [];
  for (const [adapter, spec] of Object.entries(ADAPTERS)) {
    const path = pyWhich(spec.program); // D3 的既有残余：与 doctor 的查找相同
    const row = new Map<string, PyValue>([["adapter", adapter], ["program", spec.program], ["path", path], ["version", null], ["exit_code", null]]);
    if (path) {
      const [code, version] = await probeVersion([path], childEnvironment); // 只运行 --version（M1）
      row.set("exit_code", BigInt(code));
      row.set("version", version);
    }
    found.push(row);
  }
  const added: string[] = [];
  if (env.args.add) {
    withConfigTransaction(ctx, "runtime.scan", null, { confirm: Boolean(env.args.yes) }, (txn) => {
      const current = txn.config;
      const runtimes = new Map(mapping(current, "runtimes"));
      for (const row of found) {
        const adapter = row.get("adapter") as string;
        if (row.get("path") && !runtimes.has(adapter)) {
          runtimes.set(adapter, new Map([["adapter", adapter]]));
          added.push(adapter);
        }
      }
      if (added.length) {
        current.set("runtimes", runtimes);
        txn.publish(current);
      }
    });
  }
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["found", found], ["added", added]]));
  for (const row of found) {
    const path = row.get("path") as string | null;
    env.out.print(`${padRight(text(row.get("program")), 10)} ${path ? `${path}（${(row.get("version") as string | null) || "版本未知"}）` : "PATH 上没有"}`);
  }
  if (env.args.add) env.out.print(`已登记：${added.length ? added.join("、") : "没有新的"}`);
  return EXIT_OK;
}

async function runtimeProbe(env: RolesEnv): Promise<number> {
  const { ctx, config } = openChecked(env);
  const runtimeId = env.args.runtime_id as string;
  const adapter = adapterOf(config, runtimeId);
  if (adapter === null) throw new ConfigError(`没有登记 runtime ${shownValue(runtimeId)}（或它的 adapter 无效）`);
  const { command, source, lines } = runtimeCommand(ctx.repo, config, runtimeId);
  for (const line of lines) env.out.printErr(line);
  if (command === null) throw new ConfigError(`找不到 runtime ${runtimeId} 的命令`);
  const [childEnvironment] = childEnv(config);
  const [code, version] = await probeVersion(command, childEnvironment);
  const result = new Map<string, PyValue>([
    ["runtime", runtimeId],
    ["adapter", adapter],
    ["source", source],
    ["command", shownCommand(command)],
    ["version_exit_code", BigInt(code)],
    ["version", version],
  ]);
  let help: HelpProbe | null = null;
  if (adapter === "pi") {
    help = await probeHelp(command, childEnvironment); // pi 另加 --help，报缺少的参数（M3）
    result.set("help", helpValue(help));
  }
  const ok = code === 0 && (help === null || (help.exit_code === 0 && !help.missing_flags.length));
  if (env.args.json) {
    printJson(env.out, new Map([...result, ["ok", ok]]));
  } else {
    env.out.print(`${runtimeId}（${adapter}，来源 ${source}）：${version || "版本未知"}`);
    if (help !== null) {
      env.out.print(`  缺少的参数：${help.missing_flags.length ? help.missing_flags.join("、") : "无"}`);
      env.out.print(`  思考级别：${help.thinking_levels.join("、")}`);
    }
  }
  return ok ? EXIT_OK : EXIT_FAIL;
}

// --- models -------------------------------------------------------------------------------------------

async function models(env: RolesEnv): Promise<number> {
  const { ctx, config } = openChecked(env);
  const runtime = env.args.runtime as string;
  const adapter = adapterOf(config, runtime);
  if (adapter === null) throw new ConfigError(`没有登记 runtime ${shownValue(runtime)}（或它的 adapter 无效）`);
  if (!ADAPTERS[adapter]?.list_models) throw new ConfigError(`${adapter} 适配器列不出模型（本轮只有 pi 支持 --list-models）`);
  const { command, lines } = runtimeCommand(ctx.repo, config, runtime);
  for (const line of lines) env.out.printErr(line);
  if (command === null) throw new ConfigError(`找不到 runtime ${runtime} 的命令`);
  ensureArgvSafe(command);
  const [childEnvironment] = childEnv(config);
  const [code, out, err] = await runCapture([...command, ...RESOURCE_FLAGS, "--list-models"], { env: childEnvironment, timeout: 90 });
  if (code !== 0) throw new ConfigError(`${runtime} --list-models 退出码 ${code}：${codePoints(redactSecrets(pyStrip(err || out))).slice(0, 200).join("")}`);
  const listed = config.get("allowed_executors");
  const allowed = Array.isArray(listed) ? listed.filter(isDict) : [];
  // CLI 的输出按整行判断疑似凭据，跨列的写法也算：有就整行遮掉；允许列表仍按原值比较（闸二第 4 片 B2）
  const rows = listModelsLines(out).map(([provider, model, secret]) => new Map<string, PyValue>([
    ["provider", secret ? "<redacted>" : provider],
    ["model", secret ? "<redacted>" : model],
    ["allowed", allowed.length ? allowed.some((entry) => entry.get("provider") === provider && entry.get("model") === model) : null],
  ]));
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["runtime", runtime], ["models", rows], ["allowed_executors_set", allowed.length > 0]]));
  if (!rows.length) env.out.print(`没有可用的模型（${listModelsEmptyReason(out) ?? "输出里没有表格"}）`);
  for (const row of rows) {
    const mark = row.get("allowed") === null ? "不限制" : row.get("allowed") ? "在允许列表" : "不在允许列表";
    env.out.print(`${padRight(text(row.get("provider")), 20)} ${padRight(text(row.get("model")), 36)} ${mark}`);
  }
  return EXIT_OK;
}

// --- doctor -------------------------------------------------------------------------------------------

/** cwd_relative_parts：命令里不是绝对路径、却在当前目录下存在的部分（第一项不带路径分隔符时是程序名，按 PATH 找，不算）。 */
export function cwdRelativeParts(command: readonly string[]): string[] {
  return command.filter((part, index) => !pyIsAbs(part) && pathExists(part) && (index > 0 || osPathSplit(part)[0] !== ""));
}

/** Python 3.12 的 os.path.isabs：Windows 上前三个字符里的 / 换成 \ 之后以 \ 开头，或第二、三个字符是 :\。 */
function pyIsAbs(path: string): boolean {
  if (process.platform !== "win32") return path.startsWith("/");
  const head = codePoints(path).slice(0, 3).join("").replaceAll("/", "\\");
  return head.startsWith("\\") || codePoints(head).slice(1).join("") === ":\\";
}

/** os.path.exists：stat 成功（跟随链接）；任何错误都算不存在。 */
function pathExists(path: string): boolean {
  try {
    statSync(path);
    return true;
  } catch {
    return false;
  }
}

const yesNo = (value: PyValue | undefined): string => (value == null ? "不适用" : value ? "是" : "否");

/** D9：名字出现在 child_env(config) 里（按大写比较）且值非空才算可用；只判断，不输出值。 */
function credentialReady(env: Env, names: PyValue | undefined): PyDict {
  const ready: PyDict = new Map();
  if (!Array.isArray(names)) return ready;
  const present = new Map([...env].map(([name, value]) => [name.toUpperCase(), value]));
  for (const name of names) if (typeof name === "string") ready.set(name, Boolean(present.get(name.toUpperCase())));
  return ready;
}

interface RuntimeProbe {
  readonly command: string[] | null;
  readonly source: string;
  readonly notes: string[];
  version: string | null;
  versionExitCode: number | null;
  help?: HelpProbe;
}

/** 版本与 --help 按 runtime 缓存，模型列表与 auth check 按（runtime, provider, model）缓存（D10）。 */
interface Caches {
  readonly byRuntime: Map<string, RuntimeProbe>;
  readonly byModel: Map<string, [PyDict, string[]]>;
}

async function probeRuntime(repo: LocalRepo, config: PyDict, env: Env, runtime: string, adapter: string): Promise<RuntimeProbe> {
  const { command, source, lines } = runtimeCommand(repo, config, runtime, adapter);
  const probe: RuntimeProbe = { command, source, notes: lines, version: null, versionExitCode: null };
  if (command !== null) {
    [probe.versionExitCode, probe.version] = await probeVersion(command, env);
    if (adapter === "pi") probe.help = await probeHelp(command, env);
  }
  return probe;
}

/** 一个 headless 绑定（当前绑定或版本记录）的就绪事实与问题（D10）。 */
async function headlessReadiness(repo: LocalRepo, config: PyDict, env: Env, caches: Caches, row: PyDict): Promise<PyDict> {
  const field = (key: string): PyValue => row.get(key) ?? null;
  const problems: string[] = [];
  const out = new Map<string, PyValue>([["role", field("role")], ["mode", "headless"], ["problems", problems]]);
  for (const key of ["profile", "runtime", "adapter", "provider", "model", "thinking", "connected"]) out.set(key, field(key));
  if (!pyTruthy(field("connected"))) problems.push(`适配器 ${(field("adapter") as string | null) || "未登记"} 本轮没有接通 ${text(field("role"))}`);
  const runtime = field("runtime");
  let probe = runtime !== null ? caches.byRuntime.get(runtime as string) : undefined;
  if (probe === undefined && runtime !== null && field("adapter") !== null) {
    probe = await probeRuntime(repo, config, env, runtime as string, field("adapter") as string);
    caches.byRuntime.set(runtime as string, probe);
  }
  if (probe === undefined || probe.command === null) {
    problems.push(`找不到 runtime ${text(runtime)} 的命令`);
  } else {
    out.set("command", shownCommand(probe.command));
    out.set("source", probe.source);
    out.set("version", probe.version);
    const relative = cwdRelativeParts(probe.command);
    if (relative.length) {
      problems.push(
        `命令里有相对路径（${(shownCommand(relative) ?? []).join("、")}）：run 在 attempt 的 worktree 里运行它，这里在当前目录探测，结果代表不了 run；写成绝对路径`,
      );
    }
    if (probe.versionExitCode !== 0) problems.push(`${text(runtime)} --version 退出码 ${probe.versionExitCode}`);
    if (field("adapter") === "pi" && pyTruthy(field("provider")) && pyTruthy(field("model"))) {
      const help = probe.help as HelpProbe;
      const key = JSON.stringify([runtime, field("provider"), field("model")]);
      let readiness = caches.byModel.get(key);
      if (readiness === undefined) {
        readiness = await piModelReadiness(probe.command, field("provider") as string, field("model") as string, null, help.thinking_levels, env);
        caches.byModel.set(key, readiness);
      }
      const [facts, found] = readiness;
      out.set("model_listed", facts.get("executor_model_listed") ?? null);
      const auth = facts.get("executor_auth_check");
      out.set("auth_ready", isDict(auth) && auth.get("exit_code") === 0n);
      const thinkingSupported = help.thinking_levels.includes(field("thinking") as string);
      out.set("thinking_supported", thinkingSupported);
      problems.push(...found);
      if (!thinkingSupported) problems.push(`思考级别 ${text(field("thinking"))} 不受本机 pi 支持`); // 逐个角色判断，不进缓存的键
      if (help.exit_code !== 0) problems.push(`${text(runtime)} --help 退出码 ${help.exit_code}`);
      if (help.missing_flags.length) problems.push(`pi 缺少参数：${help.missing_flags.join("、")}`);
    }
  }
  out.set("notes", probe?.notes ?? []);
  if ((field("role") === "execution" || field("role") === "contract") && pyTruthy(config.get("allowed_executors"))) {
    // 与内核同一个判定，含固定的 thinking（闸二总复核 S3）
    const problem = allowedExecutorCheck(config, field("provider"), field("model"), field("thinking"));
    out.set("allowed", problem === null);
    if (problem !== null && problem[0] === "missing") {
      problems.push(`${text(field("provider"))}/${text(field("model"))} 不在 allowed_executors 里`);
    } else if (problem !== null) {
      problems.push(`allowed_executors 把 ${text(field("provider"))}/${text(field("model"))} 的思考级别固定为 ${text(problem[1])}，profile 是 ${text(field("thinking"))}`);
    }
  } else {
    out.set("allowed", null);
  }
  const profiles = mapping(config, "profiles");
  const profile = field("profile");
  const spec = typeof profile === "string" ? profiles.get(profile) : undefined;
  const credentials = credentialReady(env, isDict(spec) ? (spec.has("credential_env") ? spec.get("credential_env") : []) : []);
  out.set("credentials", credentials);
  const missing = [...credentials].filter(([, ready]) => !ready).map(([name]) => String(name));
  if (missing.length) problems.push(`凭据变量不可用（被移除、没有设置或为空）：${missing.join("、")}`);
  out.set("ready", !problems.length);
  return out;
}

/** 一个合同版本的执行模型记录能不能跑：命令按 run 的顺序解析（runtime 不必仍在配置里登记），模型列表、登录与思考级别都用
 * 记录里的值与 child_env(config)；允许列表按当前配置判断。 */
async function recordReadiness(repo: LocalRepo, config: PyDict, env: Env, caches: Caches, planKey: string): Promise<PyDict> {
  const match = PLAN_KEY_RE.exec(planKey);
  if (match === null) throw new ConfigError(`--record 写成 <task-id>.v<N>：${shownValue(planKey)}`, EXIT_USAGE);
  const taskId = match.groups?.["task"] as string;
  const version = BigInt(match.groups?.["ver"] as string);
  const record = loadBindingRecord(repo.root, taskId, version);
  if (record === null) throw new ConfigError(`${planKey} 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor`);
  const entry: PyDict = new Map(["role", "profile", "runtime", "adapter", "provider", "model", "thinking"].map((key) => [key, record.get(key) ?? null]));
  const adapter = ADAPTERS[record.get("adapter") as string];
  entry.set("connected", Object.hasOwn(ADAPTERS, record.get("adapter") as string) && Boolean(adapter?.headless_roles.includes(record.get("role") as string)));
  const out = await headlessReadiness(repo, config, env, caches, entry);
  out.set("record", bindingRecordRel(taskId, version));
  return out;
}

function printDoctor(env: RolesEnv, rows: PyDict[]): void {
  const ready = rows.every((row) => row.get("ready"));
  if (env.args.json) {
    printJson(env.out, new Map<string, PyValue>([["ready", ready], ["roles", rows]]));
    return;
  }
  for (const row of rows) {
    const get = (key: string): PyValue => row.get(key) ?? null;
    if (row.has("text")) {
      env.out.print(`${padRight(text(get("role")), 16)} ${text(get("text"))}`);
      continue;
    }
    if (pyTruthy(get("record"))) env.out.print(`版本记录 ${text(get("record"))}`);
    const command = (get("command") as string[] | null) ?? [];
    env.out.print(
      `${padRight(text(get("role")), 16)} ${get("ready") ? "就绪" : "未就绪"} · profile ${text(get("profile"))} · runtime ${text(get("runtime"))}` +
        `（${text(get("adapter"))}，${row.has("source") ? text(get("source")) : "missing"} ${command.join(" ")}）· ${(get("version") as string | null) || ""}`,
    );
    const credentials = [...(get("credentials") as PyDict)].map(([name, isReady]) => `${String(name)} ${isReady ? "可用" : "不可用"}`).join("、");
    env.out.print(
      `${padRight("", 16)} 模型 ${text(get("provider"))}/${text(get("model"))} · thinking ${text(get("thinking"))} · 模型列表 ${yesNo(row.get("model_listed"))}` +
        ` · 登录 ${yesNo(row.get("auth_ready"))} · 思考级别 ${yesNo(row.get("thinking_supported"))}` +
        ` · 允许列表 ${get("allowed") === null ? "不限制" : yesNo(get("allowed"))} · 凭据 ${credentials || "无"} · ${pyTruthy(get("connected")) ? "已接通" : "未接通"}`,
    );
    for (const note of (row.get("notes") as string[] | undefined) ?? []) env.out.print(`  ${note}`);
    for (const problem of get("problems") as string[]) env.out.print(`  - ${problem}`);
  }
  env.out.print(ready ? "全部就绪" : "有未就绪的角色");
}

async function doctor(env: RolesEnv): Promise<number> {
  const { ctx, config } = openChecked(env);
  const [childEnvironment] = childEnv(config);
  const caches: Caches = { byRuntime: new Map(), byModel: new Map() };
  const rows: PyDict[] = [];
  // 按版本记录核验：与 run 用同一条命令、同一个模型与思考级别（闸二总复核第 2 轮 S4）
  if (env.args.record) rows.push(await recordReadiness(ctx.repo, config, childEnvironment, caches, env.args.record));
  for (const row of env.args.record ? [] : roleRows(config)) {
    const binding = row.get("binding");
    if (!isDict(binding) || binding.get("mode") !== "headless") {
      const mode = isDict(binding) && binding.size ? (binding.get("mode") ?? null) : null;
      rows.push(new Map<string, PyValue>([["role", row.get("role") ?? null], ["mode", mode], ["problems", []], ["text", roleText(row)], ["ready", true]]));
      continue;
    }
    rows.push(await headlessReadiness(ctx.repo, config, childEnvironment, caches, row));
  }
  printDoctor(env, rows);
  return rows.every((row) => row.get("ready")) ? EXIT_OK : EXIT_FAIL;
}

const HANDLERS: Readonly<Record<string, (env: RolesEnv) => Promise<number>>> = {
  "runtime scan": runtimeScan,
  "runtime probe": runtimeProbe,
  models,
  doctor,
};

/** 会运行本机 CLI 的 kit_roles 子命令（config 之后的部分）。 */
export const PROBE_COMMANDS = Object.keys(HANDLERS);

/** kit_roles._run：调度器的错误（找不到 pi、批处理参数不安全等）转成配置中心的错误。 */
export async function runProbeCommand(path: string, env: RolesEnv): Promise<number> {
  const handler = HANDLERS[path];
  if (handler === undefined) throw new ConfigError(`内部错误：TS 实现还没有 config ${path}`, EXIT_USAGE);
  try {
    return await handler(env);
  } catch (error) {
    if (error instanceof DispatchError) throw new ConfigError(error.message, error.code === EXIT_FAIL || error.code === EXIT_USAGE ? error.code : EXIT_FAIL);
    throw error;
  }
}
