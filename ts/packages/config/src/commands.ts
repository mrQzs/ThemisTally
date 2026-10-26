// kit_config.py 的只读命令（迁移第 ③a2 片）：validate、show、history [show N]、secret check|remove。参数是启动器交来的
// pyargs（argparse 解析好的值），输出经 PyOut 照 Python 的 print 写字节。写命令在第 ③b 片，secret set 留在 Python。
import { statSync } from "node:fs";
import { PyOut, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { pyLen } from "@themis/base/pyre";
import { DispatchError, EXIT_OK, EXIT_FAIL, EXIT_USAGE, Repo } from "@themis/dispatcher/repo";
import { DecisionError, batteryLinkProblem, joinPath, loadBatteries, settingsFromConfig, verifyBatteryLock } from "./decisions.ts";
import { STATE_WORDS, SECRET_SHOWN, auditPath, contentNote, entryBytes, findEntry, historyEntries, keyDiff } from "./history.ts";
import { secretConfigError } from "./secret-config.ts";
import { SecretError, checkName, describeSecret, removeSecret, source } from "./secret-store.ts";
import { ConfigError, KEYS, type Kit, type RepoLike, configPath, loadConfig, validateConfig } from "./validate.ts";

/** 每个键的说明与缺省值的文字（kit_config.KEYS）：次序与 KEYS 相同，show 照这个次序列。 */
const KEY_TEXT: ReadonlyMap<string, readonly [string, string]> = new Map<string, readonly [string, string]>([
  ["allowed_executors", ["允许的执行模型 [{provider, model, thinking}]；为空不限制", "[]（不限制）"]],
  ["worktree_root", ["worktree 的父目录（必须在仓库之外）；null 用系统临时目录下的 pi-worktrees/", "null"]],
  ["kill_grace_seconds", ["超时或取消后给进程树的宽限秒数", "15"]],
  ["check_artifact_patterns", ["检查可以产生、不算候选漂移的缓存文件（仓库相对 glob）", "[]"]],
  ["extra_protected_paths", ["本仓库对执行器永远只读的路径（仓库相对模式）", "[]"]],
  ["planner_paths", ["规划端自己会编辑的路径（运行期间变化只记备注）", "内置：.agent/plans/**、reviews/**、design/**、*.md"]],
  ["commit_trailers", ["branch 创建候选提交时追加的尾注 `Key: value`", "[]"]],
  ["env_remove", ["在默认列表之外还要对执行器移除的环境变量名", "[]"]],
  ["env_keep", ["默认移除列表里确实要保留的环境变量名", "[]"]],
  ["release_check", ["release-check 的放过规则 allow（`<glob>:<模式名>`）与拒绝清单路径 denylist", "{}"]],
  [
    "pricing",
    [
      "执行模型单价（2.8.0）：<provider>/<model> → input、output、cache_read、cache_write（每 per_tokens 个 token，缺省一百万）、currency、source、as_of；metrics 用 token 乘单价估算费用。kit 不内置价格，由你填",
      "{}（不估算）",
    ],
  ],
  ["decisions", ["决策模型：mode（off/shadow/on）、api_key_env、base_url、model、timeout_seconds、budget_seconds、max_state_chars、points", "mode off"]],
  ["plugins", ["插件的启用与权限（3.0）：enabled 插件 ID 列表，allowed_permissions 权限名列表；不写的子键表示不限制", "不限制"]],
  ["runtimes", ["登记的 CLI（3.0 第二轮）：{ID: {adapter}}；命令路径只放未提交的 .agent/dispatch.local.json", "无"]],
  ["profiles", ["profile：{ID: {runtime, model: {provider, id}, options, credential_env}}", "无"]],
  ["roles", ["四个角色的绑定：planning_review、contract、execution、scheduler_agent → {mode, profile 或 host}", "execution 由合同决定；contract 为 manual；scheduler_agent 为 disabled"]],
  ["presets", ["方案：{名: {description, roles}}，切换时只覆盖它列出的角色", "无"]],
  ["active_preset", ["当前方案名", "无"]],
]);

const SOURCE_WORDS: Readonly<Record<string, string>> = { env: "环境变量已设置", credential_store: "在系统凭据库里", file: "在 0600 文件里", none: "没有" };

export interface ConfigArgs {
  readonly command: readonly string[];
  readonly repo?: string | null;
  readonly json?: boolean;
  readonly show?: string | null;
  readonly number?: bigint | number | null;
  readonly action?: string;
  readonly name?: string;
}

const json = (value: PyValue): string => dumps(value, { ensureAscii: false });
const indented = (value: PyValue): string => dumps(value, { ensureAscii: false, indent: 2 });
/** "%-Ns"：按码点补齐。 */
const padRight = (text: string, width: number): string => text + " ".repeat(Math.max(0, width - pyLen(text)));
/** "%Nd"。 */
const padLeft = (text: string, width: number): string => " ".repeat(Math.max(0, width - pyLen(text))) + text;

/** kit_config._repo：不在 Git 仓库里是用法错误。 */
export function discoverRepo(path: string | null | undefined): Repo {
  try {
    return Repo.discover(path ?? null);
  } catch (error) {
    if (error instanceof DispatchError) throw new ConfigError(`不在 Git 仓库里：${error.message}`, EXIT_USAGE);
    throw error;
  }
}

function exists(path: string): boolean {
  try {
    statSync(path);
    return true;
  } catch {
    return false;
  }
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

export function cmdValidate(args: ConfigArgs, kit: Kit, out: PyOut): number {
  const repo = discoverRepo(args.repo);
  const errors = validateConfig(loadConfig(repo), repo, kit);
  if (args.json) {
    out.print(indented(new Map<string, PyValue>([["valid", !errors.length], ["errors", errors], ["config_path", configPath(repo)]])));
    return errors.length ? EXIT_FAIL : EXIT_OK;
  }
  for (const error of errors) out.print(`ERROR ${error}`);
  out.print(`配置${errors.length ? `无效（${errors.length} 个错误）` : "有效"}：${configPath(repo)}`);
  return errors.length ? EXIT_FAIL : EXIT_OK;
}

/** 每个键的生效值与来源；疑似凭据的取值不显示。 */
function effective(config: PyDict): PyDict[] {
  return [...KEYS.keys()].map((key) => {
    const [description, fallback] = KEY_TEXT.get(key) as readonly [string, string];
    let value: PyValue = null;
    let from = "default";
    if (config.has(key)) {
      value = secretConfigError(config, key) !== null ? SECRET_SHOWN : (config.get(key) as PyValue);
      from = "config";
    } else if (key === "worktree_root" && process.env["PI_DISPATCH_WORKTREE_ROOT"]) {
      value = process.env["PI_DISPATCH_WORKTREE_ROOT"];
      from = "env:PI_DISPATCH_WORKTREE_ROOT";
    }
    return new Map<string, PyValue>([
      ["key", key],
      ["value", value],
      ["source", from],
      ["default", fallback],
      ["description", description],
    ]);
  });
}

/**
 * config show 的决策摘要（kit_config._decisions_summary 加 pd.describe_decisions、decisions.describe 里用到的部分）；
 * 配置无效时 {"error": 原因}。describe 会读凭据来源、核对题库并读清单：这里照样做一遍，Python 在其中打堆栈的地方这边也照样崩。
 */
async function decisionsSummary(config: PyDict, repo: RepoLike, kit: Kit): Promise<PyDict> {
  const secret = secretConfigError(config, "decisions");
  if (secret !== null) return new Map([["error", secret]]);
  try {
    const settings = settingsFromConfig(config, repo.agentDir, kit.decisionsDir);
    const link = batteryLinkProblem(kit.kitRoot, kit.decisionsDir);
    if (!process.env[settings.api_key_env]) await source(settings.api_key_env);
    let batteryLock: PyValue = null;
    if (link !== null) {
      batteryLock = "link";
    } else if (isDir(joinPath(kit.decisionsDir, "questions"))) {
      try {
        verifyBatteryLock(kit.decisionsDir);
        batteryLock = "ok";
      } catch (error) {
        if (!(error instanceof DecisionError)) throw error;
        batteryLock = "drift";
      }
      try {
        loadBatteries(joinPath(kit.decisionsDir, "questions"));
      } catch (error) {
        if (!(error instanceof DecisionError)) throw error;
      }
    }
    return new Map<string, PyValue>([
      ["mode", settings.mode],
      ["configured_mode", settings.configured_mode],
      ["reason", settings.reason],
      ["marker_present", settings.marker_present],
      ["model", settings.model],
      ["base_url", settings.base_url],
      ["points", settings.points],
      ["env_var_name", settings.api_key_env],
      ["battery_lock", batteryLock],
      ["secret", await describeSecret(settings.api_key_env)],
    ]);
  } catch (error) {
    if (error instanceof DecisionError) return new Map([["error", error.detail]]);
    throw error;
  }
}

export async function cmdShow(args: ConfigArgs, kit: Kit, out: PyOut): Promise<number> {
  const repo = discoverRepo(args.repo);
  const config = loadConfig(repo);
  const errors = validateConfig(config, repo, kit);
  const rows = effective(config);
  const path = configPath(repo);
  const decisions = await decisionsSummary(config, repo, kit);
  if (args.json) {
    out.print(
      indented(
        new Map<string, PyValue>([
          ["config_path", path],
          ["exists", exists(path)],
          ["errors", errors],
          ["keys", rows],
          ["decisions", decisions],
        ]),
      ),
    );
    return errors.length ? EXIT_FAIL : EXIT_OK;
  }
  out.print(`配置文件：${path}${exists(path) ? "" : "（不存在，全部缺省）"}`);
  for (const row of rows) {
    const shown = row.get("source") !== "default" ? json(row.get("value") as PyValue) : `缺省（${row.get("default") as string}）`;
    out.print(`  ${padRight(row.get("key") as string, 24)} ${shown}  [${row.get("source") as string}]`);
    out.print(`  ${padRight("", 24)}   ${row.get("description") as string}`);
  }
  if (decisions.has("error")) {
    out.print(`决策模型：配置无效——${decisions.get("error") as string}`);
  } else {
    const secret = decisions.get("secret") as PyDict;
    out.print(
      `决策模型：生效 ${decisions.get("mode") as string}（配置 ${decisions.get("configured_mode") as string}，原因 ${decisions.get("reason") as string}）` +
        `· 模型 ${decisions.get("model") as string} · 标记文件 ${decisions.get("marker_present") ? "存在" : "无"}`,
    );
    out.print(
      `  凭据 ${decisions.get("env_var_name") as string}：${SOURCE_WORDS[secret.get("source") as string] as string}` +
        `（凭据库模式 ${secret.get("store_mode") as string}，系统后端 ${(secret.get("system_backend") as string | null) || "无"}）`,
    );
  }
  for (const error of errors) out.print(`ERROR ${error}`);
  return errors.length ? EXIT_FAIL : EXIT_OK;
}

const stateWord = (state: PyValue): string => STATE_WORDS.get(state) ?? pyStrValue(state);

export function cmdHistory(args: ConfigArgs, out: PyOut): number {
  const repo = discoverRepo(args.repo);
  const { entries, broken, leadingExternal } = historyEntries(repo);
  if (args.number !== null && args.number !== undefined) return historyShow(repo, entries, BigInt(args.number), Boolean(args.json), out);
  const rows = entries.map((entry) => {
    const [before, after] = entryBytes(repo, entry);
    const diff = entry.resource === "config" ? keyDiff(before, after) : null;
    return new Map<string, PyValue>([
      ["number", BigInt(entry.number)],
      ["resource", entry.resource],
      ["at", entry.at],
      ["action", entry.action],
      ["target", entry.target],
      ["actor", entry.actor],
      ["confirmation", entry.confirmation],
      ["state", entry.state],
      ["resolved", entry.resolved],
      ["changed_keys", diff === null ? null : diff.map((change) => change.key)],
      ["note", contentNote(entry.resource, entry.afterRef, repo)],
      ["external_changes", BigInt(entry.externalAfter)],
    ]);
  });
  if (args.json) {
    out.print(indented(new Map<string, PyValue>([["entries", rows], ["broken_lines", broken.map(BigInt)], ["external_before_first", BigInt(leadingExternal)]])));
    return EXIT_OK;
  }
  if (!rows.length) out.print(`还没有写入记录：${auditPath(repo)}`);
  if (leadingExternal) out.print(`第 1 条之前：配置中心之外已有的内容（记为基线，observed ${leadingExternal} 次）`);
  for (const row of rows) {
    const state = stateWord(row.get("state") as PyValue) + (row.get("resolved") ? "（补判）" : "");
    const changed = row.get("changed_keys") as string[] | null;
    const keys = changed !== null && changed.length ? changed.join("、") : ((row.get("note") as string | null) || "—");
    const target = row.get("target") as PyValue;
    out.print(
      `${padLeft(String(row.get("number")), 4)}  ${pyStrValue(row.get("at") as PyValue)}  ${padRight(pyStrValue(row.get("resource") as PyValue), 6)} ` +
        `${padRight(pyStrValue(row.get("action") as PyValue), 18)} ${padRight(pyTruthy(target) ? pyStrValue(target) : "—", 24)} ` +
        `${state} · ${pyStrValue(row.get("actor") as PyValue)} · 确认 ${pyStrValue(row.get("confirmation") as PyValue)}  [${keys}]`,
    );
    if (row.get("external_changes")) out.print(`      之后发现 ${String(row.get("external_changes"))} 次在配置中心之外的改动（observed）`);
  }
  if (broken.length) out.print(`损坏的记录：第 ${broken.join("、")} 行`);
  return EXIT_OK;
}

function historyShow(repo: RepoLike, entries: Parameters<typeof findEntry>[0], number: bigint, asJson: boolean, out: PyOut): number {
  const entry = findEntry(entries, number);
  if (entry.resource !== "config") {
    const shaOf = (ref: PyValue): PyValue => (ref instanceof Map ? (ref.get("sha256") ?? null) : null);
    const facts = new Map<string, PyValue>([
      ["number", number],
      ["resource", entry.resource],
      ["state", entry.state],
      ["before_sha256", shaOf(entry.beforeRef)],
      ["after_sha256", shaOf(entry.afterRef)],
      ["note", "本机配置只存哈希"],
    ]);
    out.print(
      asJson
        ? indented(facts)
        : `第 ${number} 条（${entry.resource}）：${pyStrValue(facts.get("before_sha256") as PyValue)} → ${pyStrValue(facts.get("after_sha256") as PyValue)}；本机配置只存哈希，没有逐键差异`,
    );
    return EXIT_OK;
  }
  const [before, after] = entryBytes(repo, entry);
  const diff = keyDiff(before, after);
  let note: string | null = null;
  if (diff === null) note = contentNote("config", after === null ? entry.afterRef : entry.beforeRef, repo) ?? "快照缺失";
  if (asJson) {
    const changes = diff === null ? null : diff.map((change) => new Map<string, PyValue>([["key", change.key], ["old", change.old], ["new", change.new]]));
    out.print(indented(new Map<string, PyValue>([["number", number], ["state", entry.state], ["note", note], ["diff", changes]])));
    return EXIT_OK;
  }
  if (diff === null) {
    out.print(`第 ${number} 条：${note as string}，没有逐键差异`);
    return EXIT_OK;
  }
  const target = entry.target;
  out.print(
    `第 ${number} 条：${pyStrValue(entry.action)} ${pyTruthy(target) ? pyStrValue(target) : ""}（${STATE_WORDS.get(entry.state) ?? "None"}）`,
  );
  for (const change of diff) {
    out.print(`  ${change.key}: ${change.old === null ? "未设置" : json(change.old)} → ${change.new === null ? "未设置" : json(change.new)}`);
  }
  return EXIT_OK;
}

export async function cmdSecret(args: ConfigArgs, out: PyOut): Promise<number> {
  const name = args.name ?? "";
  try {
    checkName(name);
  } catch (error) {
    if (error instanceof SecretError) throw new ConfigError(error.detail, EXIT_USAGE);
    throw error;
  }
  if (args.action === "check") {
    out.print(json(await describeSecret(name)));
    return EXIT_OK;
  }
  out.print(json(new Map<string, PyValue>([["name", name], ["removed_from", await removeSecret(name)]])));
  return EXIT_OK;
}
