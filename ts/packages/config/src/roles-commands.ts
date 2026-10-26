// kit_roles.py 的配置中心命令（迁移第 ③c 片）：runtime list|add|remove、profile show|add|edit|remove、role show|set、
// preset list|show|save|use|diff|remove。写入都经写入事务（配置锁、整份校验、D8 的确认、历史与审计）；读命令先整份校验，
// 不合法就只报错误。输出照 Python 的 print 与 "%-Ns" 逐字。runtime scan|probe、models、doctor 在第 ③d 片。
// 找仓库（kit_config._repo）放在 Python 调它的那一步：参数错与“不在 Git 仓库里”同时出现时，先报哪一个照 Python。
import { readdirSync, statSync } from "node:fs";
import { type PyOut, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { ci, cmpCodePoints, pyLen, pyLower, pyStrip } from "@themis/base/pyre";
import { pyLstatStrerror } from "@themis/base/pyos";
import { pyEq } from "@themis/base/pyvalue";
import { TASK_ID_RE, secretLikePaths } from "@themis/base/secrets";
import { DEFAULT_THINKING, allowedExecutorCheck, executorClass, loadBindingRecord } from "@themis/dispatcher/executor";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE } from "@themis/dispatcher/repo";
import { joinPath } from "./decisions.ts";
import { bindingTuple, effectiveBinding } from "./roles-binding.ts";
import { ADAPTERS, ROLES, adapterOf, entries, idOk, shownValue } from "./roles-check.ts";
import { LOCAL_NAME, LOCAL_REL, type LocalRepo, checkLocal, lexists, localErrors, readLocal, runtimeCommand, shownCommand } from "./roles-local.ts";
import { type ConfigTransaction, type WriteContext, withConfigTransaction, withConfigTransactions } from "./transaction.ts";
import { ConfigError, loadConfig, validateConfig } from "./validate.ts";

/** 转交来的参数（argparse 的 Namespace）。runtime add 的 --command 在 Namespace 里与子命令同名，转交时叫 command_option。 */
export interface RolesArgs {
  readonly command: readonly string[];
  readonly repo?: string | null;
  readonly json?: boolean;
  readonly yes?: boolean;
  readonly force?: boolean;
  readonly runtime_id?: string;
  readonly adapter?: string;
  readonly command_option?: string | null;
  readonly profile_id?: string | null;
  readonly runtime?: string | null;
  readonly model?: string | null;
  readonly thinking?: string | null;
  readonly credential_env?: string[] | null;
  readonly role?: string;
  readonly target?: string;
  readonly host?: string | null;
  readonly cadence_seconds?: bigint | number | null;
  readonly name?: string;
  readonly description?: string | null;
  readonly roles?: string | null;
  readonly a?: string;
  readonly b?: string;
}

export interface RolesEnv {
  readonly args: RolesArgs;
  readonly out: PyOut;
  /** kit_config._repo 加上 kit 与等锁的秒数。 */
  readonly open: () => WriteContext;
}

const MODE_WORDS = ["manual", "disabled", "interactive_host"];

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const text = (value: PyValue | undefined): string => pyStrValue(value ?? null);
const json = (value: PyValue): string => dumps(value, { ensureAscii: false });
/** "%-Ns"：按码点补齐。 */
const padRight = (value: string, width: number): string => value + " ".repeat(Math.max(0, width - pyLen(value)));
/** json.loads(json.dumps(value))。 */
const deepCopy = (value: PyValue): PyValue => loads(dumps(value));

function printJson(out: PyOut, payload: PyValue): number {
  out.print(dumps(payload, { ensureAscii: false, indent: 2 }));
  return EXIT_OK;
}

/** _open：读命令的开头先整份校验；不合法就只报错误、退出 1，不显示取值、不解析命令。 */
function openChecked(env: RolesEnv): { ctx: WriteContext; config: PyDict } {
  const ctx = env.open();
  const config = loadConfig(ctx.repo);
  const errors = validateConfig(config, ctx.repo, ctx.kit);
  if (errors.length) throw new ConfigError(`配置无效，先修好（config validate）：${errors.slice(0, 5).join("；")}`);
  return { ctx, config };
}

/** 配置里一个对象键：缺省或 null 是空对象，其他类型报错。 */
function mapping(config: PyDict, key: string): PyDict {
  const value = config.get(key) ?? null;
  if (value === null) return new Map();
  if (!isDict(value)) throw new ConfigError(`${key} 不是对象：先修好配置（config validate）`);
  return value;
}

// --- runtime -------------------------------------------------------------------------------------

function runtimeList(env: RolesEnv): number {
  const { ctx, config } = openChecked(env);
  const rows = entries(mapping(config, "runtimes")).map(([runtimeId, spec]) => {
    const { command, source, lines } = runtimeCommand(ctx.repo, config, runtimeId);
    return new Map<string, PyValue>([
      ["id", runtimeId],
      ["adapter", isDict(spec) ? (spec.get("adapter") ?? null) : null],
      ["source", source],
      ["command", shownCommand(command)],
      ["notes", lines],
    ]);
  });
  if (env.args.json) return printJson(env.out, new Map([["runtimes", rows]]));
  if (!rows.length) env.out.print("还没有登记 runtime：config runtime scan --add，或 config runtime add <id> --adapter <适配器>");
  for (const row of rows) {
    const command = row.get("command") as string[] | null;
    env.out.print(`${padRight(text(row.get("id")), 16)} ${padRight(text(row.get("adapter")), 12)} ${padRight(text(row.get("source")), 8)} ${command ? command.join(" ") : "（找不到命令）"}`);
    for (const line of row.get("notes") as string[]) env.out.print(`  ${line}`);
  }
  return EXIT_OK;
}

/** --command 的值：非空的 JSON 字符串数组，不含疑似凭据（嵌套太深的 RecursionError 照抛）。 */
function parseCommand(value: string): string[] {
  let parsed: PyValue = null;
  try {
    parsed = loads(value);
  } catch (error) {
    if (!(error instanceof PyJsonError) || error.kind === "RecursionError") throw error;
  }
  if (!Array.isArray(parsed) || !parsed.length || !parsed.every((part) => typeof part === "string" && part !== "")) {
    throw new ConfigError('--command 必须是非空的 JSON 字符串数组，例如 ["/usr/local/bin/pi"]', EXIT_USAGE);
  }
  if (secretLikePaths(parsed).length) throw new ConfigError("--command 里有疑似凭据：命令里不写凭据，凭据用 config secret set 存", EXIT_USAGE);
  return parsed as string[];
}

/**
 * 写（command 为 null 时删）本机文件里 runtime 的命令：写之前做同样的三项检查，形状与凭据前后各查一次；经写入事务（resource
 * local，历史只存哈希），与配置那一步在同一把锁里。返回是否有变化。
 */
function writeLocal(repo: LocalRepo, open: (resource: string) => ConfigTransaction, runtimeId: string, command: string[] | null): boolean {
  const problems = checkLocal(repo);
  if (problems.length) throw new ConfigError(problems.join("；"));
  const txn = open("local");
  const data = txn.config;
  const before = data.size ? localErrors(data) : [];
  if (before.length) throw new ConfigError(`${before.join("；")}：先修好本机文件`);
  const runtimes = new Map(data.has("runtimes") ? (data.get("runtimes") as PyDict) : new Map());
  if (command === null) {
    if (!runtimes.has(runtimeId)) return false;
    runtimes.delete(runtimeId);
  } else {
    runtimes.set(runtimeId, new Map([["command", [...command]]]));
  }
  const after = new Map(data);
  after.set("runtimes", runtimes);
  const errors = localErrors(after);
  if (errors.length) throw new ConfigError(errors.join("；"));
  return txn.publish(after);
}

function runtimeAdd(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const runtimeId = args.runtime_id as string;
  const adapter = args.adapter as string;
  if (!idOk(runtimeId)) throw new ConfigError(`runtime ID 不合法（小写字母、数字与连字符）：${shownValue(runtimeId)}`, EXIT_USAGE);
  if (!Object.hasOwn(ADAPTERS, adapter)) throw new ConfigError(`--adapter 必须是 ${Object.keys(ADAPTERS).join("、")} 之一`, EXIT_USAGE);
  const command = args.command_option != null ? parseCommand(args.command_option) : null;
  const resources = command !== null ? ["config", "local"] : ["config"];
  withConfigTransactions(ctx, "runtime.add", runtimeId, { confirm: Boolean(args.yes), resources }, (open) => {
    const txn = open("config");
    const config = txn.config;
    const runtimes = new Map(mapping(config, "runtimes"));
    const current = runtimes.get(runtimeId);
    if (isDict(current) && !pyEq(current.get("adapter") ?? null, adapter) && !args.force) {
      throw new ConfigError(`runtime ${runtimeId} 已登记为 ${shownValue(current.get("adapter") ?? null)}；改 adapter 要加 --force`);
    }
    // 原有的说明键留着，adapter 放在它们之后
    const spec: PyDict = new Map(isDict(current) ? [...current].filter(([key]) => String(key).startsWith("_")) : []);
    spec.set("adapter", adapter);
    runtimes.set(runtimeId, spec);
    config.set("runtimes", runtimes);
    const changed = txn.publish(config);
    out.print(`${changed ? "已登记" : "没有变化："} runtime ${runtimeId}（adapter ${adapter}）`);
    if (command !== null) {
      writeLocal(ctx.repo, open, runtimeId, command);
      out.print(`命令写进了 ${LOCAL_REL}（本机文件，不进提交）`);
    }
  });
  return EXIT_OK;
}

function runtimeRemove(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const runtimeId = args.runtime_id as string;
  withConfigTransactions(ctx, "runtime.remove", runtimeId, { confirm: Boolean(args.yes) }, (open) => {
    const txn = open("config");
    const config = txn.config;
    const runtimes = new Map(mapping(config, "runtimes"));
    if (!runtimes.has(runtimeId) || runtimeId.startsWith("_")) throw new ConfigError(`没有登记 runtime ${shownValue(runtimeId)}`);
    const users = entries(mapping(config, "profiles"))
      .filter(([, spec]) => isDict(spec) && pyEq(spec.get("runtime") ?? null, runtimeId))
      .map(([profileId]) => profileId);
    if (users.length) throw new ConfigError(`runtime ${runtimeId} 被 profile ${users.join("、")} 引用：先改或删这些 profile`);
    runtimes.delete(runtimeId);
    if (runtimes.size) config.set("runtimes", runtimes);
    else config.delete("runtimes");
    txn.publish(config);
    out.print(`已删除 runtime ${runtimeId}`);
    let exists: boolean;
    try {
      exists = lexists(joinPath(ctx.repo.agentDir, LOCAL_NAME));
    } catch (error) {
      throw new ConfigError(`${LOCAL_REL} 看不了（${pyLstatStrerror(error)}）：其中 ${runtimeId} 的命令没有删`);
    }
    if (!exists) return;
    const { commands, errors } = readLocal(ctx.repo, config);
    if (errors.length) throw new ConfigError(`${errors.join("；")}：其中 ${runtimeId} 的命令没有删`);
    if (commands?.has(runtimeId) && writeLocal(ctx.repo, open, runtimeId, null)) out.print(`也删去了 ${LOCAL_REL} 里的命令`);
  });
  return EXIT_OK;
}

// --- profile -------------------------------------------------------------------------------------

function splitModel(value: string): [string, string] {
  const slash = value.indexOf("/");
  const provider = slash < 0 ? value : value.slice(0, slash);
  const model = slash < 0 ? "" : value.slice(slash + 1);
  if (!provider || !model) throw new ConfigError(`--model 写成 <provider>/<模型 ID>：${shownValue(value)}`, EXIT_USAGE);
  return [provider, model];
}

function profileShow(env: RolesEnv): number {
  const { config } = openChecked(env);
  const wanted = env.args.profile_id ?? null;
  const items = entries(mapping(config, "profiles")).filter(([profileId]) => wanted === null || profileId === wanted);
  if (wanted !== null && !items.length) throw new ConfigError(`没有 profile ${shownValue(wanted)}`);
  const rows = items.map(([profileId, raw]) => {
    const spec: PyDict = isDict(raw) ? raw : new Map();
    const model = isDict(spec.get("model")) ? (spec.get("model") as PyDict) : new Map();
    const options = isDict(spec.get("options")) ? (spec.get("options") as PyDict) : new Map();
    return new Map<string, PyValue>([
      ["id", profileId],
      ["runtime", spec.get("runtime") ?? null],
      ["adapter", adapterOf(config, spec.get("runtime"))],
      ["provider", model.get("provider") ?? null],
      ["model", model.get("id") ?? null],
      ["options", options],
      ["credential_env", spec.has("credential_env") ? (spec.get("credential_env") as PyValue) : []],
    ]);
  });
  if (env.args.json) return printJson(env.out, new Map([["profiles", rows]]));
  if (!rows.length) env.out.print("还没有 profile：config profile add <id> --runtime <r> --model <provider/模型>");
  for (const row of rows) {
    const options = row.get("options") as PyDict;
    const adapter = row.get("adapter") as string | null;
    const thinking = options.has("thinking") ? (options.get("thinking") as PyValue) : adapter === "pi" ? DEFAULT_THINKING : null;
    const credentials = (row.get("credential_env") as PyValue[]).map((name) => text(name)).join("、");
    env.out.print(
      `${padRight(text(row.get("id")), 16)} runtime ${text(row.get("runtime"))}（${adapter || "未登记"}）  ${text(row.get("provider"))}/${text(row.get("model"))}` +
        `${pyTruthy(thinking) ? ` · thinking ${text(thinking)}` : ""}  凭据变量 ${credentials || "无"}`,
    );
  }
  return EXIT_OK;
}

function profileAdd(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const profileId = args.profile_id as string;
  if (!idOk(profileId)) throw new ConfigError(`profile ID 不合法（小写字母、数字与连字符）：${shownValue(profileId)}`, EXIT_USAGE);
  const [provider, model] = splitModel(args.model as string);
  withConfigTransaction(ctx, "profile.add", profileId, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    const profiles = new Map(mapping(config, "profiles"));
    if (profiles.has(profileId)) throw new ConfigError(`profile ${profileId} 已存在：改用 config profile edit`);
    const spec: PyDict = new Map<string, PyValue>([
      ["runtime", args.runtime ?? null],
      ["model", new Map([["provider", provider], ["id", model]])],
    ]);
    if (args.thinking != null) spec.set("options", new Map([["thinking", args.thinking]]));
    if (args.credential_env?.length) spec.set("credential_env", [...args.credential_env]);
    profiles.set(profileId, spec);
    config.set("profiles", profiles);
    txn.publish(config); // 整份校验（D1）；不运行任何 CLI（M9）
  });
  out.print(`已添加 profile ${profileId}`);
  return EXIT_OK;
}

function profileEdit(env: RolesEnv): number {
  const { args, out } = env;
  if (args.model == null && args.thinking == null && args.credential_env == null && args.runtime == null) {
    throw new ConfigError("profile edit 至少给一项：--model、--thinking、--credential-env 或 --runtime", EXIT_USAGE);
  }
  const ctx = env.open();
  const profileId = args.profile_id as string;
  const changed = withConfigTransaction(ctx, "profile.edit", profileId, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    const profiles = new Map(mapping(config, "profiles"));
    const current = profiles.get(profileId);
    if (!isDict(current) || profileId.startsWith("_")) throw new ConfigError(`没有 profile ${shownValue(profileId)}`);
    const spec = deepCopy(current) as PyDict;
    if (args.runtime != null) spec.set("runtime", args.runtime);
    if (args.model != null) {
      const [provider, model] = splitModel(args.model);
      spec.set("model", new Map([["provider", provider], ["id", model]]));
    }
    if (args.thinking != null) {
      const options = new Map(isDict(spec.get("options")) ? (spec.get("options") as PyDict) : new Map());
      options.set("thinking", args.thinking);
      spec.set("options", options);
    }
    if (args.credential_env != null) spec.set("credential_env", [...args.credential_env]);
    profiles.set(profileId, spec);
    config.set("profiles", profiles);
    return txn.publish(config); // 非法的修改整份校验不过，不写（M4）；改变生效绑定时按 D8 要确认
  });
  out.print(`${changed ? "已修改" : "没有变化："} profile ${profileId}`);
  return EXIT_OK;
}

/** 引用这个 profile 的角色绑定与方案里的绑定。 */
function profileUsers(config: PyDict, profileId: string): string[] {
  const users = entries(mapping(config, "roles"))
    .filter(([, binding]) => isDict(binding) && pyEq(binding.get("profile") ?? null, profileId))
    .map(([role]) => `roles.${role}`);
  for (const [name, spec] of entries(mapping(config, "presets"))) {
    const roles = isDict(spec) && isDict(spec.get("roles")) ? (spec.get("roles") as PyDict) : new Map();
    for (const [role, binding] of entries(roles)) {
      if (isDict(binding) && pyEq(binding.get("profile") ?? null, profileId)) users.push(`presets.${name}.roles.${role}`);
    }
  }
  return users;
}

function profileRemove(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const profileId = args.profile_id as string;
  withConfigTransaction(ctx, "profile.remove", profileId, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    const profiles = new Map(mapping(config, "profiles"));
    if (!profiles.has(profileId) || profileId.startsWith("_")) throw new ConfigError(`没有 profile ${shownValue(profileId)}`);
    const users = profileUsers(config, profileId);
    if (users.length) throw new ConfigError(`profile ${profileId} 被 ${users.join("、")} 引用：先改这些绑定或方案`);
    profiles.delete(profileId);
    if (profiles.size) config.set("profiles", profiles);
    else config.delete("profiles");
    txn.publish(config);
  });
  out.print(`已删除 profile ${profileId}`);
  return EXIT_OK;
}

// --- role ----------------------------------------------------------------------------------------

function activePreset(config: PyDict): string | null {
  const active = config.get("active_preset");
  return typeof active === "string" ? active : null;
}

function roleRows(config: PyDict): PyDict[] {
  const explicit = mapping(config, "roles");
  const active = activePreset(config);
  const presets = mapping(config, "presets");
  const spec = active ? presets.get(active) : undefined;
  const listed = isDict(spec) ? (spec.has("roles") ? spec.get("roles") : new Map()) : new Map();
  const presetRoles: PyDict = isDict(listed) ? listed : new Map();
  return ROLES.map((role) => {
    const binding = effectiveBinding(config, role);
    const row = new Map<string, PyValue>([
      ["role", role],
      ["explicit", explicit.has(role)],
      ["binding", binding],
      ["differs_from_preset", presetRoles.has(role) && !pyEq(presetRoles.get(role) ?? null, explicit.get(role) ?? null)],
    ]);
    if (binding !== null && binding.get("mode") === "headless") {
      const [, profileId, runtime, adapter, provider, model, thinking] = bindingTuple(config, role) as (string | null)[];
      row.set("profile", profileId ?? null);
      row.set("runtime", runtime ?? null);
      row.set("adapter", adapter ?? null);
      row.set("provider", provider ?? null);
      row.set("model", model ?? null);
      row.set("thinking", thinking ?? null);
      row.set("connected", adapter != null && Boolean(ADAPTERS[adapter]?.headless_roles.includes(role)));
    }
    return row;
  });
}

function roleText(row: PyDict): string {
  const binding = row.get("binding");
  if (!isDict(binding)) return `由合同决定（没有写 roles.${text(row.get("role"))}）`;
  const mode = binding.get("mode") ?? null;
  if (mode === "headless") {
    return (
      `headless · profile ${text(row.get("profile"))}（runtime ${text(row.get("runtime"))}，${(row.get("adapter") as string | null) || "未登记"}）` +
      `${text(row.get("provider"))}/${text(row.get("model"))} · thinking ${text(row.get("thinking"))}${row.get("connected") ? "" : " · 本轮未接通"}`
    );
  }
  if (mode === "interactive_host") {
    const host = binding.get("host") ?? null;
    return `interactive_host${pyTruthy(host) ? ` · ${text(host)}` : ""}（交互宿主的模型不由 Themis 切换）`;
  }
  return text(mode);
}

function roleShow(env: RolesEnv): number {
  const { config } = openChecked(env);
  const rows = roleRows(config);
  const active = activePreset(config);
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["active_preset", active], ["roles", rows]]));
  env.out.print(`当前方案：${active || "无"}`);
  for (const row of rows) {
    env.out.print(`${padRight(text(row.get("role")), 16)} ${roleText(row)}${row.get("differs_from_preset") ? `  ← 与方案 ${text(active)} 不一致` : ""}`);
  }
  return EXIT_OK;
}

/** role set 之后的提示（不阻止写入）：适配器本轮没有接通这个角色；执行模型不在 allowed_executors 里。 */
function bindingWarnings(config: PyDict, role: string): string[] {
  const binding = effectiveBinding(config, role);
  if (binding === null || binding.get("mode") !== "headless") return [];
  const [, profileId, , adapter, provider, model, thinking] = bindingTuple(config, role) as (string | null)[];
  const warnings: string[] = [];
  if (adapter == null || !ADAPTERS[adapter]?.headless_roles.includes(role)) {
    warnings.push(`${role} 绑定到 ${adapter || "未登记的 runtime"}：这个适配器本轮没有接通 ${role}，按角色写的合同不会派遣`);
  }
  // 与内核同一个判定（闸二总复核 S3）
  const problem = role === "execution" || role === "contract" ? allowedExecutorCheck(config, provider ?? null, model ?? null, thinking ?? null) : null;
  if (problem !== null && problem[0] === "missing") {
    warnings.push(`profile ${text(profileId)} 的 ${text(provider)}/${text(model)} 不在 allowed_executors 里，prepare 会拒绝`);
  } else if (problem !== null) {
    warnings.push(`allowed_executors 把 ${text(provider)}/${text(model)} 的思考级别固定为 ${text(problem[1])}，profile ${text(profileId)} 是 ${text(thinking)}，prepare 会拒绝`);
  }
  return warnings;
}

function roleBinding(args: RolesArgs): PyDict {
  const role = args.role as string;
  const target = args.target as string;
  if (MODE_WORDS.includes(target)) {
    const binding: PyDict = new Map([["mode", target]]);
    if (args.host != null) {
      if (target !== "interactive_host") throw new ConfigError("--host 只用于 interactive_host", EXIT_USAGE);
      binding.set("host", args.host);
    }
    if (args.cadence_seconds != null) throw new ConfigError("--cadence-seconds 只用于 scheduler_agent 的 headless 绑定", EXIT_USAGE);
    return binding;
  }
  if (args.host != null) throw new ConfigError("--host 只用于 interactive_host", EXIT_USAGE);
  const binding: PyDict = new Map([["mode", "headless"], ["profile", target]]);
  if (args.cadence_seconds != null) {
    if (role !== "scheduler_agent") throw new ConfigError("--cadence-seconds 只用于 scheduler_agent", EXIT_USAGE);
    binding.set("cadence_seconds", BigInt(args.cadence_seconds));
  }
  return binding;
}

function roleSet(env: RolesEnv): number {
  const { args, out } = env;
  const role = args.role as string;
  if (!ROLES.includes(role)) throw new ConfigError(`角色只能是 ${ROLES.join("、")} 之一`, EXIT_USAGE);
  const binding = roleBinding(args);
  const ctx = env.open();
  let config: PyDict = new Map();
  const changed = withConfigTransaction(ctx, "role.set", role, { confirm: Boolean(args.yes) }, (txn) => {
    config = txn.config;
    const roles = new Map(mapping(config, "roles"));
    roles.set(role, binding);
    config.set("roles", roles);
    return txn.publish(config); // 模式与角色是否相配、profile 是否登记都在整份校验里（D1）
  });
  out.print(`${changed ? "已设置" : "没有变化："} roles.${role} = ${json(binding)}`);
  for (const warning of bindingWarnings(config, role)) out.print(`WARN  ${warning}`);
  return EXIT_OK;
}

// --- preset --------------------------------------------------------------------------------------

/** 方案里列出的 {角色: 绑定}；没有这个方案（或它的 roles 不是对象）报错。 */
function presetRoles(presets: PyDict, name: string): Map<string, PyValue> {
  const spec = name.startsWith("_") ? null : (presets.get(name) ?? null);
  if (!isDict(spec) || !isDict(spec.get("roles"))) throw new ConfigError(`没有方案 ${shownValue(name)}`);
  return new Map(entries(spec.get("roles") as PyDict));
}

function presetList(env: RolesEnv): number {
  const { config } = openChecked(env);
  const active = config.get("active_preset") ?? null;
  const rows = entries(mapping(config, "presets")).map(([name, spec]) => {
    const roles = isDict(spec) && isDict(spec.get("roles")) ? entries(spec.get("roles") as PyDict).map(([role]) => role).sort(cmpCodePoints) : [];
    return new Map<string, PyValue>([
      ["name", name],
      ["description", isDict(spec) ? (spec.get("description") ?? null) : null],
      ["roles", roles],
      ["active", pyEq(name, active)],
    ]);
  });
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["active_preset", active], ["presets", rows]]));
  if (!rows.length) env.out.print("还没有方案：config preset save <名>");
  for (const row of rows) {
    const description = row.get("description") ?? null;
    env.out.print(`${row.get("active") ? "*" : " "} ${padRight(text(row.get("name")), 16)} ${(row.get("roles") as string[]).join("、")}  ${pyTruthy(description) ? text(description) : ""}`);
  }
  return EXIT_OK;
}

function presetShow(env: RolesEnv): number {
  const { config } = openChecked(env);
  const name = env.args.name as string;
  const roles = presetRoles(mapping(config, "presets"), name);
  const current = mapping(config, "roles");
  const active = pyEq(config.get("active_preset") ?? null, name);
  const rows = [...roles]
    .sort(([left], [right]) => cmpCodePoints(left, right))
    .map(([role, binding]) => new Map<string, PyValue>([
      ["role", role],
      ["binding", binding],
      ["current", current.get(role) ?? null],
      ["differs", !pyEq(current.get(role) ?? null, binding)],
    ]));
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["name", name], ["active", active], ["roles", rows]]));
  env.out.print(`方案 ${name}${active ? "（当前在用）" : ""}`);
  for (const row of rows) {
    env.out.print(`  ${padRight(text(row.get("role")), 16)} ${json(row.get("binding") as PyValue)}${row.get("differs") && active ? "  ← 当前绑定与它不一致" : ""}`);
  }
  return EXIT_OK;
}

function presetSave(env: RolesEnv): number {
  const { args, out } = env;
  const name = args.name as string;
  if (!idOk(name)) throw new ConfigError(`方案名不合法（小写字母、数字与连字符）：${shownValue(name)}`, EXIT_USAGE);
  const ctx = env.open();
  let selected: string[] = [];
  withConfigTransaction(ctx, "preset.save", name, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    const roles = mapping(config, "roles");
    selected = args.roles
      ? args.roles.split(",").map((role) => pyStrip(role)).filter(Boolean)
      : ROLES.filter((role) => roles.has(role));
    const unknown = selected.filter((role) => !ROLES.includes(role));
    if (unknown.length) throw new ConfigError(`未知角色：${unknown.map((role) => shownValue(role)).join("、")}（只有 ${ROLES.join("、")}）`, EXIT_USAGE);
    const missing = selected.filter((role) => !roles.has(role));
    if (missing.length) throw new ConfigError(`这些角色还没有写出绑定：${missing.join("、")}（先 config role set）`);
    if (!selected.length) throw new ConfigError("roles 里还没有绑定可存：先 config role set");
    const presets = new Map(mapping(config, "presets"));
    if (presets.has(name) && !args.force) throw new ConfigError(`方案 ${name} 已存在：要覆盖加 --force`);
    const spec: PyDict = new Map([["roles", new Map(selected.map((role) => [role, deepCopy(roles.get(role) as PyValue)]))]]);
    if (args.description != null) spec.set("description", args.description);
    presets.set(name, spec);
    config.set("presets", presets);
    txn.publish(config);
  });
  out.print(`已保存方案 ${name}：${selected.join("、")}`);
  return EXIT_OK;
}

/** Path(plans).glob("*.v*.json")：Windows 上不分大小写（re.IGNORECASE 下 s 还配 ſ），列目录被拒时为空。 */
const PLAN_NAME = process.platform === "win32" ? new RegExp(`^[^]*${ci(".v")}[^]*${ci(".json")}$`, "u") : /^[^]*\.v[^]*\.json$/u;

function planFiles(plans: string): string[] {
  let names: string[];
  try {
    names = readdirSync(plans);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "EACCES" || code === "EPERM") return [];
    throw error;
  }
  // Windows 上 Path 的排序按小写比较
  const key = (name: string): string => (process.platform === "win32" ? pyLower(name) : name);
  return names.filter((name) => PLAN_NAME.test(name)).sort((left, right) => cmpCodePoints(key(left), key(right)));
}

/** 按角色写的合同版本与它们的记录状态（D8 的影响说明）：[(task.vN（角色）, 状态)]。只读合同与记录。 */
function roleContractVersions(repo: LocalRepo): [string, string][] {
  const plans = joinPath(repo.agentDir, "plans");
  const rows: [string, string][] = [];
  let names: string[];
  try {
    names = statSync(plans).isDirectory() ? planFiles(plans) : [];
  } catch {
    return rows;
  }
  for (const name of names) {
    let raw: PyValue;
    try {
      raw = loads(pyDecodeUtf8(pyReadBytes(joinPath(plans, name))));
    } catch (error) {
      if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError || (error instanceof PyJsonError && error.kind !== "RecursionError")) continue;
      throw error;
    }
    const executor = isDict(raw) ? (raw.get("executor") ?? null) : null;
    const taskId = isDict(raw) ? (raw.get("task_id") ?? null) : null;
    const version = isDict(raw) ? (raw.get("plan_version") ?? null) : null;
    if (executorClass(executor) !== "role" || typeof taskId !== "string" || !TASK_ID_RE.test(taskId) || typeof version !== "bigint") continue;
    let status: string;
    try {
      status = loadBindingRecord(repo.root, taskId, version) !== null ? "沿用版本记录" : "还没有记录，会用新绑定";
    } catch (error) {
      if (!(error instanceof DispatchError)) throw error;
      status = "版本记录无效";
    }
    rows.push([`${taskId}.v${version}（${text((executor as PyDict).get("role"))}）`, status]);
  }
  return rows;
}

function presetUse(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const name = args.name as string;
  let config: PyDict = new Map();
  let listed = new Map<string, PyValue>();
  const changed = withConfigTransaction(ctx, "preset.use", name, { confirm: Boolean(args.yes) }, (txn) => {
    config = txn.config;
    listed = presetRoles(mapping(config, "presets"), name);
    const roles = new Map(mapping(config, "roles"));
    for (const [role, binding] of listed) roles.set(role, deepCopy(binding)); // 只覆盖方案里列出的角色（D8）
    config.set("roles", roles);
    config.set("active_preset", name);
    out.print("影响（写入之前）：运行中与已准备的 attempt 不受影响（执行模型在 prepare 时已固定）");
    for (const [version, status] of roleContractVersions(ctx.repo)) out.print(`  ${version}：${status}`);
    return txn.publish(config);
  });
  const sorted = [...listed.keys()].sort(cmpCodePoints);
  out.print(`${changed ? "已切换到" : "没有变化："} 方案 ${name}（覆盖 ${sorted.join("、")}）`);
  for (const role of sorted) for (const warning of bindingWarnings(config, role)) out.print(`WARN  ${warning}`); // 与 role set 相同的提示
  return EXIT_OK;
}

function presetDiff(env: RolesEnv): number {
  const { config } = openChecked(env);
  const presets = mapping(config, "presets");
  const [nameA, nameB] = [env.args.a as string, env.args.b as string];
  const left = presetRoles(presets, nameA);
  const right = presetRoles(presets, nameB);
  const rows = ROLES.filter((role) => left.has(role) || right.has(role)).map((role) => new Map<string, PyValue>([
    ["role", role],
    ["a", left.get(role) ?? null],
    ["b", right.get(role) ?? null],
    ["same", pyEq(left.get(role) ?? null, right.get(role) ?? null)],
  ]));
  if (env.args.json) return printJson(env.out, new Map<string, PyValue>([["a", nameA], ["b", nameB], ["roles", rows]]));
  const shown = (value: PyValue): string => (value !== null ? json(value) : "未列出");
  for (const row of rows) {
    const difference = `${nameA}：${shown(row.get("a") as PyValue)}  |  ${nameB}：${shown(row.get("b") as PyValue)}`;
    env.out.print(`${padRight(text(row.get("role")), 16)} ${row.get("same") ? "相同" : difference}`);
  }
  return EXIT_OK;
}

function presetRemove(env: RolesEnv): number {
  const { args, out } = env;
  const ctx = env.open();
  const name = args.name as string;
  withConfigTransaction(ctx, "preset.remove", name, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    const presets = new Map(mapping(config, "presets"));
    presetRoles(presets, name);
    if (pyEq(config.get("active_preset") ?? null, name)) throw new ConfigError(`方案 ${name} 正在用：先 preset use 别的方案，或 config unset active_preset`);
    presets.delete(name);
    if (presets.size) config.set("presets", presets);
    else config.delete("presets");
    txn.publish(config);
  });
  out.print(`已删除方案 ${name}`);
  return EXIT_OK;
}

const HANDLERS: Readonly<Record<string, (env: RolesEnv) => number>> = {
  "runtime list": runtimeList,
  "runtime add": runtimeAdd,
  "runtime remove": runtimeRemove,
  "profile show": profileShow,
  "profile add": profileAdd,
  "profile edit": profileEdit,
  "profile remove": profileRemove,
  "role show": roleShow,
  "role set": roleSet,
  "preset list": presetList,
  "preset show": presetShow,
  "preset save": presetSave,
  "preset use": presetUse,
  "preset diff": presetDiff,
  "preset remove": presetRemove,
};

/** 已移植的 kit_roles 子命令（config 之后的两段）。 */
export const ROLES_COMMANDS = Object.keys(HANDLERS);

/** kit_roles._run：调度器的错误转成配置中心的错误（一行 ERROR，不冒堆栈）。 */
export function runRolesCommand(path: string, env: RolesEnv): number {
  const handler = HANDLERS[path];
  if (handler === undefined) throw new ConfigError(`内部错误：TS 实现还没有 config ${path}`, EXIT_USAGE);
  try {
    return handler(env);
  } catch (error) {
    if (error instanceof DispatchError) throw new ConfigError(error.message, error.code === EXIT_FAIL || error.code === EXIT_USAGE ? error.code : EXIT_FAIL);
    throw error;
  }
}
