// kit_plugins.py（迁移第 ③e 片）：list / show / verify 只读，enable / disable 只改 plugins 键。
// 只读核对复用 plugin-records（codekit/plugins）与 decisions 的题库锁；写入经配置中心的写入事务（整份校验、历史与审计）。
// 找仓库用 pi_dispatch 的 Repo.discover（报错是 DispatchError，与 config 命令的“不在 Git 仓库里”不同）。
// 报错照 kit_plugins.main：DispatchError 与 ConfigError 都写一行 `ERROR: ` 加 redact_tokens 之后的文字。
import { createHash } from "node:crypto";
import { lstatSync, readdirSync, statSync } from "node:fs";
import { type PyOut, pyReprValue, pyStrValue } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps } from "@themis/base/pyjson";
import { PyWinError } from "@themis/base/pyos";
import { firstLinkComponent, isLinkOrJunction, isWithin } from "@themis/base/pypath";
import { ProtocolError, strictJsonLoads } from "@themis/base/protocols";
import { ci, cmpCodePoints, pyLower } from "@themis/base/pyre";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo } from "@themis/dispatcher/repo";
import { DecisionError, PLUGIN_ID as DECISIONS_PLUGIN_ID, QuestionError, batteryLinkProblem, joinPath, settingsActive, settingsFromConfig, verifyBatteryLock } from "./decisions.ts";
import { PLUGIN_ID, PluginError, checkPermissionIntersection, validateLock, validateManifest } from "./plugin-records.ts";
import { type ConfigTransaction, type WriteContext, previewNotes, withConfigTransaction } from "./transaction.ts";
import { ConfigError, type Kit, configPath, loadConfig, pluginsFixHint, pluginsSectionError, validateConfig } from "./validate.ts";

// 合同写明的固定词
const OK = "一致";
const DRIFT = "漂移";
const INVALID = "无效";
const LINK = "无效：链接";
const ROOT_LINK = "无效：链接 plugins"; // plugins 根是链接（文字与 --json 都含它）
const UNSUPPORTED = "本轮不支持";
const MISMATCH = "不一致";
const READY = "READY";
const BLOCKED = "BLOCKED";

export interface PluginsArgs {
  readonly command: readonly string[];
  readonly repo?: string | null;
  readonly plugin_id?: string | null;
  readonly json?: boolean;
  readonly allow_permission?: string[] | null;
  readonly dry_run?: boolean;
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const json = (value: PyValue): string => dumps(value, { ensureAscii: false });
const text = (value: PyValue | undefined): string => pyStrValue(value ?? null);

/** Python 会当作 ValueError、OSError 或 DecisionError 接住的异常（kit_plugins 逐插件收集它们）。 */
function caught(error: unknown): error is Error {
  return (
    error instanceof DecisionError ||
    error instanceof PluginError ||
    error instanceof ProtocolError ||
    error instanceof QuestionError ||
    error instanceof PyOSError ||
    error instanceof PyWinError ||
    error instanceof PyUnicodeDecodeError ||
    (error instanceof PyJsonError && error.kind !== "RecursionError")
  );
}

/** Path.is_dir / is_file（跟随链接；看不了当作不是）。 */
function statKind(path: string): "dir" | "file" | null {
  try {
    const status = statSync(path);
    return status.isDirectory() ? "dir" : status.isFile() ? "file" : null;
  } catch {
    return null;
  }
}

/** Windows 上 Path 的排序按小写比较。 */
const pathOrder = (left: string, right: string): number =>
  process.platform === "win32" ? cmpCodePoints(pyLower(left), pyLower(right)) : cmpCodePoints(left, right);

// --- 枚举与读前检查 -----------------------------------------------------------------------------------

const pluginsRoot = (kit: Kit): string => joinPath(kit.kitRoot, "plugins");

/** plugins/ 根本身的问题：是链接，或是目录却列不出来；没有问题时 null。列不出来时枚举为空，不能当作“没有插件”。 */
function rootProblem(kit: Kit): string | null {
  const root = pluginsRoot(kit);
  if (isLinkOrJunction(root)) return ROOT_LINK;
  if (statKind(root) !== "dir") return null;
  try {
    readdirSync(root);
  } catch (error) {
    return `无效：plugins 列不出来：${(error as Error).message}`;
  }
  return null;
}

/** plugins/ 下匹配 PLUGIN_ID 的直接子目录 [(名字, 是否链接)]；链接目录（含悬空的）也列出，普通文件不列。 */
function enumerateEntries(kit: Kit): [string, boolean][] {
  const root = pluginsRoot(kit);
  let names: string[];
  try {
    if (isLinkOrJunction(root) || statKind(root) !== "dir") return [];
    names = readdirSync(root).sort(pathOrder);
  } catch {
    return [];
  }
  const entries: [string, boolean][] = [];
  for (const name of names) {
    if (!PLUGIN_ID.test(name)) continue;
    const child = joinPath(root, name);
    const link = isLinkOrJunction(child);
    if (!link && statKind(child) !== "dir") continue;
    entries.push([name, link]);
  }
  return entries;
}

function requireExists(kit: Kit, pluginId: string): void {
  if (enumerateEntries(kit).some(([name]) => name === pluginId)) return;
  const problem = rootProblem(kit);
  throw new DispatchError(`插件不存在或未安装：${pluginId}${problem ? `（${problem}）` : ""}`, EXIT_USAGE);
}

/** rel 从 kit 根往下第一个链接/junction 那一级；没有为 null，路径非法也当作被挡下。 */
function linkLevel(kitRoot: string, rel: string): string | null {
  try {
    return firstLinkComponent(kitRoot, rel);
  } catch {
    return rel;
  }
}

interface JsonRead {
  readonly value: PyValue | null;
  readonly isLink: boolean;
  readonly message: string | null;
}

/** 读前逐级链接检查、普通文件确认、严格解析。value 为 null 时 isLink 区分“链接/越界”与其他失败。 */
function readJsonFile(kitRoot: string, rel: string): JsonRead {
  const link = linkLevel(kitRoot, rel);
  if (link !== null) return { value: null, isLink: true, message: link };
  const path = joinPath(kitRoot, rel);
  if (isLinkOrJunction(path) || statKind(path) !== "file") return { value: null, isLink: false, message: "不是普通文件" };
  let data: Buffer;
  try {
    data = pyReadBytes(path);
  } catch (error) {
    if (error instanceof PyOSError) return { value: null, isLink: false, message: `读取失败：${error.message}` };
    throw error;
  }
  let value: PyValue;
  try {
    value = strictJsonLoads(data);
  } catch (error) {
    if (error instanceof ProtocolError) return { value: null, isLink: false, message: `解析失败：${error.message}` };
    throw error;
  }
  if (value === null) return { value: null, isLink: false, message: "不是对象（内容是 null）" };
  return { value, isLink: false, message: null };
}

const jsonProblem = (label: string, read: JsonRead): string => (read.isLink ? `${label}：${LINK} ${read.message}` : `${label}：${read.message}`);

// --- 单插件核对 -------------------------------------------------------------------------------------

interface ResourceRow {
  readonly path: PyValue;
  readonly id: PyValue;
  readonly sha256: PyValue;
  status: string;
  detail: string;
}

interface Report {
  readonly pluginId: string;
  lockStatus: string;
  resourceStatus: string | null;
  problems: string[];
  manifest: PyDict | null;
  lock: PyDict | null;
  lockRaw: PyDict | null;
  resourceRows: ResourceRow[];
  permissions: PyValue[];
  dependsOn: PyValue[];
  conflicts: PyValue[];
  missingPermissions: PyValue[];
  permissionReady: boolean;
}

function emptyReport(pluginId: string): Report {
  return {
    pluginId,
    lockStatus: INVALID,
    resourceStatus: null,
    problems: [],
    manifest: null,
    lock: null,
    lockRaw: null,
    resourceRows: [],
    permissions: [],
    dependsOn: [],
    conflicts: [],
    missingPermissions: [],
    permissionReady: true,
  };
}

const sha256 = (data: Uint8Array): string => createHash("sha256").update(data).digest("hex");

/** CRLF 换成 LF 之后的字节。 */
function crlfToLf(data: Buffer): Buffer {
  const out: number[] = [];
  for (let index = 0; index < data.length; index += 1) {
    if (data[index] === 0x0d && data[index + 1] === 0x0a) continue;
    out.push(data[index] as number);
  }
  return Buffer.from(out);
}

interface ResourceCheck {
  readonly lockStatus: string;
  readonly resourceStatus: string | null;
  readonly problems: string[];
  readonly rows: ResourceRow[];
}

/** 核对资源。资源列为 null 表示被链接类失败挡下（list 显示 -）；锁列只在出现读取失败时改“无效”，哈希不符不改锁列。 */
function checkResources(kitRoot: string, pluginId: string, normalizedLock: PyDict): ResourceCheck {
  const prefix = `plugins/${pluginId}`;
  let resources: PyValue[] = [];
  for (const row of (normalizedLock.get("plugins") as PyValue[] | undefined) ?? []) {
    if (isDict(row) && row.get("plugin_id") === pluginId) {
      resources = (row.get("resources") as PyValue[] | undefined) ?? [];
      break;
    }
  }
  const rows: ResourceRow[] = [];
  const problems: string[] = [];
  let readFailed = false;
  for (const ref of resources) {
    const entry = ref as PyDict;
    const rel = entry.get("path") as string;
    const row: ResourceRow = { path: rel, id: entry.get("id") ?? "", sha256: entry.get("sha256") ?? "", status: OK, detail: "" };
    rows.push(row);
    const link = linkLevel(kitRoot, rel);
    if (link !== null) {
      row.status = LINK;
      problems.push(`资源 ${rel}：${LINK} ${link}`);
      return { lockStatus: INVALID, resourceStatus: null, problems, rows };
    }
    if (!isWithin(joinPath(kitRoot, rel), joinPath(kitRoot, prefix))) {
      row.status = LINK;
      problems.push(`资源 ${rel}：${LINK}（路径越出插件目录）`);
      return { lockStatus: INVALID, resourceStatus: null, problems, rows };
    }
    const path = joinPath(kitRoot, rel);
    if (isLinkOrJunction(path) || statKind(path) !== "file") {
      row.status = LINK;
      problems.push(`资源 ${rel}：${LINK}（不是普通文件）`);
      return { lockStatus: INVALID, resourceStatus: null, problems, rows };
    }
    let data: Buffer;
    try {
      data = pyReadBytes(path);
    } catch (error) {
      if (!(error instanceof PyOSError)) throw error;
      row.status = MISMATCH;
      problems.push(`资源读取失败：资源 ${rel}：${error.message}`);
      readFailed = true;
      continue;
    }
    if (sha256(data) === entry.get("sha256")) {
      row.status = OK;
    } else {
      row.status = MISMATCH;
      if (sha256(crlfToLf(data)) === entry.get("sha256")) {
        row.detail = "仅行尾不同（CRLF）";
        problems.push(`资源 ${rel} 不一致：仅行尾不同（CRLF）`);
      } else {
        problems.push(`资源 ${rel} 与锁不一致`);
      }
    }
  }
  return { lockStatus: readFailed ? INVALID : OK, resourceStatus: rows.some((row) => row.status === MISMATCH) ? MISMATCH : OK, problems, rows };
}

/** Path(questions).glob("*.json") 的名字（Windows 上不分大小写，re.IGNORECASE 下 s 还配 ſ）；列目录被拒时为空。 */
const JSON_NAME = process.platform === "win32" ? new RegExp(`^[^]*${ci(".json")}$`, "u") : /^[^]*\.json$/u;

function globJson(directory: string): string[] {
  try {
    return readdirSync(directory).filter((name) => JSON_NAME.test(name));
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "EACCES" || code === "EPERM") return [];
    throw error;
  }
}

/** decisions 的题库：（锁列或 null，资源列或 null，问题）；null 表示不改动对应列。 */
function checkBattery(kit: Kit, pluginId: string): [string | null, string | null, string[]] {
  const rel = `plugins/${pluginId}/questions`;
  const link = linkLevel(kit.kitRoot, rel);
  if (link !== null) return [INVALID, null, [`questions 目录：${LINK} ${link}`]];
  const questions = joinPath(kit.kitRoot, rel);
  if (isLinkOrJunction(questions) || statKind(questions) !== "dir") return [INVALID, null, [`questions 目录：${LINK}（不是普通目录）`]];
  let names: string[];
  try {
    names = globJson(questions).sort(cmpCodePoints);
  } catch (error) {
    return [null, MISMATCH, [`题库与内容锁不一致：questions 列举失败：${(error as Error).message}`]];
  }
  for (const name of names) {
    const fileLink = linkLevel(kit.kitRoot, `plugins/${pluginId}/questions/${name}`);
    if (fileLink !== null) return [INVALID, null, [`题库 ${name}：${LINK} ${fileLink}`]];
    const entry = joinPath(kit.kitRoot, `plugins/${pluginId}/questions/${name}`);
    if (isLinkOrJunction(entry) || statKind(entry) !== "file") return [INVALID, null, [`题库 ${name}：${LINK}（不是普通文件）`]];
  }
  try {
    verifyBatteryLock(kit.decisionsDir);
  } catch (error) {
    if (!caught(error)) throw error;
    return [null, MISMATCH, [`题库与内容锁不一致：${error.message}`]];
  }
  return [null, null, []];
}

function checkPlugin(kit: Kit, pluginId: string, allowed: PyValue[] | null): Report {
  const report = emptyReport(pluginId);
  const manifestRead = readJsonFile(kit.kitRoot, `plugins/${pluginId}/manifest.json`);
  if (manifestRead.value === null) {
    report.problems.push(jsonProblem("manifest.json", manifestRead));
    return report;
  }
  const lockRead = readJsonFile(kit.kitRoot, `plugins/${pluginId}/lock.json`);
  if (lockRead.value === null) {
    report.problems.push(jsonProblem("lock.json", lockRead));
    return report;
  }
  const manifest = manifestRead.value;
  const lock = lockRead.value;
  report.lockRaw = isDict(lock) ? lock : null;
  if (!isDict(manifest) || manifest.get("plugin_id") !== pluginId) {
    const pid = isDict(manifest) ? text(manifest.get("plugin_id")) : "（非对象）";
    report.problems.push(`目录名与 plugin_id 不一致：目录 ${pluginId}，plugin_id ${pid}`);
    return report;
  }
  let normalizedManifest: PyDict;
  try {
    normalizedManifest = validateManifest(manifest);
  } catch (error) {
    if (!(error instanceof PluginError)) throw error;
    report.problems.push(`manifest.json 无效：${error.message}`);
    return report;
  }
  report.manifest = normalizedManifest;
  report.permissions = [...((normalizedManifest.get("permissions") as PyValue[] | undefined) ?? [])];
  report.dependsOn = [...((normalizedManifest.get("depends_on") as PyValue[] | undefined) ?? [])];
  report.conflicts = [...((normalizedManifest.get("conflicts") as PyValue[] | undefined) ?? [])];
  if (allowed !== null) {
    try {
      const result = checkPermissionIntersection(normalizedManifest, allowed, null);
      report.missingPermissions = [...((result.get("missing_permissions") as PyValue[] | undefined) ?? [])];
      report.permissionReady = result.get("status") === READY;
    } catch (error) {
      // 核对不了就按不满足处理，不放行
      if (!(error instanceof PluginError)) throw error;
      report.permissionReady = false;
      report.problems.push(`权限核对失败：${error.message}`);
    }
  }
  if (!isDict(lock)) {
    report.problems.push("lock.json：不是对象");
    return report;
  }
  if (report.dependsOn.length || report.conflicts.length) {
    report.lockStatus = UNSUPPORTED;
    report.problems.push("带 depends_on 或 conflicts 的插件本轮不支持");
    return report;
  }
  let normalizedLock: PyDict;
  try {
    normalizedLock = validateLock(lock, new Map([[pluginId, normalizedManifest]]));
  } catch (error) {
    if (!(error instanceof PluginError)) throw error;
    report.lockStatus = error.code === "E_PLUGIN_LOCK_DRIFT" || error.code === "E_PLUGIN_LOCK_BINDING" ? DRIFT : INVALID;
    report.problems.push(`lock.json：${error.message}`);
    return report;
  }
  report.lock = normalizedLock;
  const resources = checkResources(kit.kitRoot, pluginId, normalizedLock);
  report.resourceRows = resources.rows;
  report.lockStatus = resources.lockStatus;
  if (resources.resourceStatus !== null) report.resourceStatus = resources.resourceStatus;
  report.problems.push(...resources.problems);
  if (resources.resourceStatus === null) return report; // 链接类资源失败：停止，不核对题库
  if (pluginId === DECISIONS_PLUGIN_ID) {
    const [batteryLock, batteryResource, batteryProblems] = checkBattery(kit, pluginId);
    if (batteryLock !== null) report.lockStatus = batteryLock;
    if (batteryResource !== null) report.resourceStatus = batteryResource;
    report.problems.push(...batteryProblems);
  }
  return report;
}

/** 逐插件收集 ValueError、OSError、DecisionError：记“无效”，不拖垮命令。 */
function checkPluginSafe(kit: Kit, pluginId: string, allowed: PyValue[] | null): Report {
  try {
    return checkPlugin(kit, pluginId, allowed);
  } catch (error) {
    if (!caught(error)) throw error;
    return { ...emptyReport(pluginId), problems: [`核对失败：${error.message}`] };
  }
}

const isConsistent = (report: Report): boolean => report.lockStatus === OK && report.resourceStatus === OK;

// --- 配置视图 -------------------------------------------------------------------------------------

interface View {
  readonly enabledPresent: boolean;
  readonly enabledValue: PyValue;
  readonly allowedPresent: boolean;
  readonly allowedValue: PyValue;
}

function pluginsView(config: PyDict): View {
  const section = config.get("plugins");
  const dict = isDict(section);
  return {
    enabledPresent: dict && section.has("enabled"),
    enabledValue: dict ? (section.get("enabled") ?? null) : null,
    allowedPresent: dict && section.has("allowed_permissions"),
    allowedValue: dict ? (section.get("allowed_permissions") ?? null) : null,
  };
}

/** 限制时的 allowed_permissions 列表；不限制或不是列表时 null（此时不做权限核对）。 */
const allowedList = (view: View): PyValue[] | null => (view.allowedPresent && Array.isArray(view.allowedValue) ? view.allowedValue : null);

function isEnabled(view: View, pluginId: string): boolean {
  if (!view.enabledPresent) return true; // 不限制：全部算启用
  return Array.isArray(view.enabledValue) && view.enabledValue.includes(pluginId);
}

const enabledLabel = (view: View, pluginId: string): string => (!view.enabledPresent ? "不限制" : isEnabled(view, pluginId) ? "是" : "否");

/** enabled 里不在枚举结果（含链接目录）中的 ID。 */
function notInstalled(config: PyDict, entries: [string, boolean][]): PyValue[] {
  const view = pluginsView(config);
  if (!view.enabledPresent || !Array.isArray(view.enabledValue)) return [];
  const present = new Set(entries.map(([name]) => name));
  return view.enabledValue.filter((name) => !(typeof name === "string" && present.has(name)));
}

// --- list / show / verify -------------------------------------------------------------------------

function listRow(report: Report, view: View): PyDict {
  const version = report.manifest ? (report.manifest.get("version") ?? null) : "-";
  const missing = report.missingPermissions;
  const lockOk = report.lockStatus === OK;
  const resourceOk = report.resourceStatus === OK;
  let status: string;
  let reason: string;
  if (lockOk && resourceOk && report.permissionReady) {
    [status, reason] = [READY, ""];
  } else {
    status = BLOCKED;
    if (!lockOk) {
      // 原因带上首条问题：链接类失败因此含“无效：链接”，漂移等词照旧可见
      reason = report.problems.length ? `${report.lockStatus}：${report.problems[0]}` : report.lockStatus;
    } else if (!resourceOk) {
      reason = `资源${report.resourceStatus || "未核对"}`;
    } else if (missing.length) {
      reason = `缺 ${missing.map(text).join("、")}`;
    } else {
      reason = report.problems[0] ?? "权限未满足";
    }
  }
  return new Map<string, PyValue>([
    ["id", report.pluginId],
    ["version", version],
    ["enabled", enabledLabel(view, report.pluginId)],
    ["lock", report.lockStatus],
    ["resource", report.resourceStatus || "-"],
    ["missing", missing],
    ["status", status],
    ["reason", reason],
  ]);
}

function formatListRow(row: PyDict): string {
  const missing = row.get("missing") as PyValue[];
  const permission = missing.length ? `缺 ${missing.map(text).join("、")}` : "无缺失";
  const reason = row.get("reason") as string;
  return `${text(row.get("id"))}  ${text(row.get("version"))}  启用:${text(row.get("enabled"))}  锁:${text(row.get("lock"))}  资源:${text(row.get("resource"))}  权限:${permission}  状态:${text(row.get("status"))}${reason ? `（${reason}）` : ""}`;
}

/** verify 标题行的词：锁列非一致用锁列值；锁一致而资源不一致用“资源不一致”；都一致用“一致”。 */
function verifyWord(report: Report): string {
  if (report.lockStatus !== OK) return report.lockStatus;
  if (report.resourceStatus !== OK) return `资源${report.resourceStatus || "未核对"}`;
  return OK;
}

export interface PluginsEnv {
  readonly args: PluginsArgs;
  readonly kit: Kit;
  readonly lockWaitSeconds: number;
  readonly out: PyOut;
}

/** plugins 段格式校验：不合法就拒绝（退出 1），附修复提示，不写配置。 */
function requirePluginsSection(config: PyDict, repo: Repo, kit: Kit): void {
  const error = pluginsSectionError(config);
  if (error === null) return;
  const hint = pluginsFixHint(config, repo, kit);
  throw new ConfigError(hint ? `${error}；修复：${hint}` : error, EXIT_FAIL);
}

function validateId(pluginId: PyValue | undefined): string {
  if (typeof pluginId !== "string" || !PLUGIN_ID.test(pluginId)) throw new DispatchError(`插件 ID 不合法：${pyReprValue(pluginId ?? null)}`, EXIT_USAGE);
  return pluginId;
}

const discover = (args: PluginsArgs): Repo => Repo.discover(args.repo ?? null);

function cmdList(env: PluginsEnv): number {
  const { args, kit, out } = env;
  const repo = discover(args);
  const config = loadConfig(repo);
  requirePluginsSection(config, repo, kit);
  const view = pluginsView(config);
  const allowed = allowedList(view);
  const entries = enumerateEntries(kit);
  const problem = rootProblem(kit);
  const rows = entries.map(([name, link]) =>
    link
      ? new Map<string, PyValue>([
          ["id", name],
          ["version", "-"],
          ["enabled", enabledLabel(view, name)],
          ["lock", INVALID],
          ["resource", "-"],
          ["missing", []],
          ["status", BLOCKED],
          ["reason", `${LINK} plugins/${name}`],
        ])
      : listRow(checkPluginSafe(kit, name, allowed), view),
  );
  const missing = notInstalled(config, entries);
  if (args.json) {
    out.print(json(new Map<string, PyValue>([["plugins_root_link", problem === ROOT_LINK], ["plugins", rows], ["not_installed", missing], ["problems", problem ? [problem] : []]])));
    return EXIT_OK;
  }
  if (problem) out.print(problem);
  for (const row of rows) out.print(formatListRow(row));
  for (const name of missing) out.print(`${text(name)} 未安装`);
  return EXIT_OK;
}

function cmdShow(env: PluginsEnv): number {
  const { args, kit, out } = env;
  const repo = discover(args);
  const pluginId = validateId(args.plugin_id);
  requireExists(kit, pluginId);
  const config = loadConfig(repo);
  requirePluginsSection(config, repo, kit);
  const view = pluginsView(config);
  const report = checkPluginSafe(kit, pluginId, allowedList(view));
  const manifest = report.manifest;
  const lockRaw = report.lockRaw;
  const missing = report.missingPermissions;
  const field = (key: string, fallback: PyValue): PyValue => (manifest ? (manifest.has(key) ? (manifest.get(key) as PyValue) : fallback) : fallback);
  if (args.json) {
    const rows = report.resourceRows.map((row) => new Map<string, PyValue>([["path", row.path], ["id", row.id], ["sha256", row.sha256], ["status", row.status], ["detail", row.detail]]));
    const payload = new Map<string, PyValue>([
      ["plugin_id", pluginId],
      ["lock_status", report.lockStatus],
      ["resource_status", report.resourceStatus],
      ["problems", report.problems],
      ["version", manifest ? (manifest.get("version") ?? null) : null],
      ["api_version", manifest ? (manifest.get("api_version") ?? null) : null],
      ["capabilities", field("capabilities", [])],
      ["permissions", report.permissions],
      ["platforms", field("platforms", [])],
      ["depends_on", report.dependsOn],
      ["conflicts", report.conflicts],
      ["checks", field("checks", [])],
      ["lock", new Map<string, PyValue>([["generation", lockRaw ? (lockRaw.get("generation") ?? null) : null], ["lock_sha256", lockRaw ? (lockRaw.get("lock_sha256") ?? null) : null]])],
      ["resources", rows],
      ["config", new Map<string, PyValue>([["enabled", enabledLabel(view, pluginId)], ["allowed_permissions", view.allowedPresent ? view.allowedValue : null], ["missing_permissions", missing]])],
    ]);
    out.print(json(payload));
    return EXIT_OK;
  }
  out.print(`插件 ${pluginId}`);
  if (manifest !== null) {
    // manifest 没通过核对时没有这些字段；锁、启用、权限、状态与问题照常输出
    out.print(`版本 ${text(manifest.get("version"))}`);
    out.print(`api_version ${text(manifest.get("api_version"))}`);
    out.print(`capabilities ${(field("capabilities", []) as PyValue[]).map(text).join("、")}`);
    out.print(`permissions ${report.permissions.map(text).join("、")}`);
    out.print(`platforms ${(field("platforms", []) as PyValue[]).map(text).join("、")}`);
    out.print(`depends_on ${report.dependsOn.length ? report.dependsOn.map(text).join("、") : "（无）"}`);
    out.print(`conflicts ${report.conflicts.length ? report.conflicts.map(text).join("、") : "（无）"}`);
    out.print(`checks ${json(field("checks", []))}`);
  }
  if (lockRaw !== null) {
    out.print(`锁 generation ${text(lockRaw.get("generation"))}`);
    out.print(`锁 lock_sha256 ${text(lockRaw.get("lock_sha256"))}`);
  }
  for (const row of report.resourceRows) out.print(`资源 ${text(row.path)} ${row.status}${row.detail ? `（${row.detail}）` : ""}`);
  out.print(`启用 ${enabledLabel(view, pluginId)}`);
  out.print(`权限 ${missing.length ? `缺 ${missing.map(text).join("、")}` : "无缺失"}`);
  out.print(`状态 ${report.lockStatus}${report.resourceStatus === null || report.resourceStatus === OK ? "" : `／资源${report.resourceStatus}`}`);
  for (const problem of report.problems) out.print(`问题：${problem}`);
  return EXIT_OK;
}

function cmdVerify(env: PluginsEnv): number {
  const { args, kit, out } = env;
  const repo = discover(args);
  let targets: string[] = [];
  const single = args.plugin_id != null;
  if (single) {
    const pluginId = validateId(args.plugin_id);
    requireExists(kit, pluginId);
    targets = [pluginId];
  }
  const config = loadConfig(repo);
  requirePluginsSection(config, repo, kit);
  const allowed = allowedList(pluginsView(config));
  const problem = single ? null : rootProblem(kit);
  let missing: PyValue[] = [];
  if (!single) {
    const entries = enumerateEntries(kit);
    targets = entries.map(([name]) => name);
    missing = notInstalled(config, entries);
  }
  const reports = targets.map((name) => checkPluginSafe(kit, name, allowed));
  const problematic = Boolean(problem) || missing.length > 0 || reports.some((report) => !isConsistent(report));
  if (args.json) {
    const plugins = reports.map((report) => new Map<string, PyValue>([["id", report.pluginId], ["lock", report.lockStatus], ["resource", report.resourceStatus], ["problems", report.problems]]));
    out.print(json(new Map<string, PyValue>([["ok", !problematic], ["plugins_root_link", problem === ROOT_LINK], ["plugins", plugins], ["not_installed", missing], ["problems", problem ? [problem] : []]])));
    return problematic ? EXIT_FAIL : EXIT_OK;
  }
  if (problem) out.print(problem);
  for (const report of reports) {
    out.print(`${report.pluginId} ${verifyWord(report)}`);
    if (!isConsistent(report)) for (const item of report.problems) out.print(`  ${item}`);
  }
  for (const name of missing) out.print(`${text(name)} 未安装`);
  return problematic ? EXIT_FAIL : EXIT_OK;
}

// --- enable / disable -------------------------------------------------------------------------------

/** 授予权限后因此满足权限条件的其它插件，以及它们读取时的问题（不静默跳过，含链接目录）。 */
function permissionImpact(kit: Kit, pluginId: string, oldAllowed: Set<PyValue>, newAllowed: Set<PyValue>): [string[], string[]] {
  const granted = new Set([...newAllowed].filter((item) => !oldAllowed.has(item)));
  const impact: string[] = [];
  const problems: string[] = [];
  for (const [name] of enumerateEntries(kit)) {
    if (name === pluginId) continue;
    let read: JsonRead;
    try {
      read = readJsonFile(kit.kitRoot, `plugins/${name}/manifest.json`);
    } catch (error) {
      if (!caught(error)) throw error;
      problems.push(`${name} ${INVALID}：核对失败：${error.message}`);
      continue;
    }
    if (read.value === null) {
      problems.push(read.isLink ? `${name} ${LINK} ${read.message}` : `${name} ${INVALID}：${read.message}`);
      continue;
    }
    let normalized: PyDict;
    try {
      normalized = validateManifest(read.value);
    } catch (error) {
      if (!(error instanceof PluginError)) throw error;
      problems.push(`${name} ${INVALID}：${error.message}`);
      continue;
    }
    const required = new Set((normalized.get("permissions") as PyValue[] | undefined) ?? []);
    if ([...required].some((item) => granted.has(item)) && [...required].every((item) => newAllowed.has(item))) impact.push(name);
  }
  return [impact, problems];
}

/** 写入前：新配置里决策插件若仍生效，先核对题库；不一致就拒绝并给恢复顺序。 */
function batteryGate(repo: Repo, kit: Kit, newConfig: PyDict): void {
  let settings;
  try {
    settings = settingsFromConfig(newConfig, repo.agentDir, kit.decisionsDir);
  } catch (error) {
    if (error instanceof DecisionError) return; // 配置错误交给整份校验报告
    throw error;
  }
  if (!settingsActive(settings)) return;
  try {
    const link = batteryLinkProblem(kit.kitRoot, kit.decisionsDir); // 读之前先查链接，经过链接就不读
    if (link !== null) throw new DecisionError("battery_drift", `${LINK} ${link}`);
    verifyBatteryLock(kit.decisionsDir);
  } catch (error) {
    if (!caught(error)) throw error;
    throw new ConfigError(
      "决策插件生效且问题清单与内容锁不一致，未写入。恢复顺序：先 `plugins disable decisions` 或 `config decisions off`" +
        `（写入后决策插件不再生效、不再触发题库核对，可以落盘），修好题库后再启用。（${error.message}）`,
    );
  }
}

/** 每个发生变化的 plugins 子键一行：`plugins.<键>: <旧> → <新>`（不存在写“未设置”）。 */
function changeLines(oldConfig: PyDict, newConfig: PyDict): string[] {
  const oldSection = isDict(oldConfig.get("plugins")) ? (oldConfig.get("plugins") as PyDict) : new Map();
  const newSection = isDict(newConfig.get("plugins")) ? (newConfig.get("plugins") as PyDict) : new Map();
  const lines: string[] = [];
  for (const key of ["enabled", "allowed_permissions"]) {
    if (!oldSection.has(key) && !newSection.has(key)) continue;
    const oldText = oldSection.has(key) ? json(oldSection.get(key) as PyValue) : "未设置";
    const newText = newSection.has(key) ? json(newSection.get(key) as PyValue) : "未设置";
    if (oldText !== newText) lines.push(`plugins.${key}: ${oldText} → ${newText}`);
  }
  return lines;
}

interface Mutation {
  readonly messages: string[];
  readonly impact: string[];
  readonly grantProblems: string[];
}

function finishMutation(env: PluginsEnv, repo: Repo, txn: ConfigTransaction, oldConfig: PyDict, newConfig: PyDict, mutation: Mutation): number {
  const { args, kit, out } = env;
  const lines = changeLines(oldConfig, newConfig);
  const changed = lines.length > 0;
  batteryGate(repo, kit, newConfig); // 无变化与写入共用：先题库门禁
  if (changed) {
    if (args.dry_run && txn.preview === null) throw new ConfigError("内部错误：--dry-run 没有进预览");
    try {
      txn.publish(newConfig);
    } catch (error) {
      if (error instanceof PyOSError || error instanceof PyWinError) throw new ConfigError(`写入失败：${error.message}`);
      throw error;
    }
  } else {
    const errors = validateConfig(newConfig, repo, kit);
    if (errors.length) throw new ConfigError(`没有写入：${errors.join("；")}`);
  }
  // 到这里就是成功（写入、dry-run 或无变化）
  const impactLines = mutation.impact.length ? [`以下插件也将满足权限条件：${mutation.impact.join("、")}`] : [];
  previewNotes([...lines, ...mutation.grantProblems, ...impactLines, ...mutation.messages]);
  for (const line of [...lines, ...mutation.grantProblems, ...impactLines, ...mutation.messages]) out.print(line);
  if (!changed) {
    out.print("没有变化");
    return EXIT_OK;
  }
  if (args.dry_run) {
    out.print("plugins 段（dry-run，未写入）：");
    out.print(dumps((newConfig.get("plugins") as PyValue | undefined) ?? new Map(), { ensureAscii: false, indent: 2 }));
  } else {
    out.print(`已写入 ${configPath(repo)}`);
  }
  return EXIT_OK;
}

function deepCopy(value: PyValue): PyValue {
  if (isDict(value)) return new Map([...value].map(([key, item]) => [key, deepCopy(item)]));
  if (Array.isArray(value)) return value.map(deepCopy);
  return value;
}

/** dict.setdefault("plugins", {})。 */
function pluginsSection(config: PyDict): PyDict {
  if (!config.has("plugins")) config.set("plugins", new Map());
  return config.get("plugins") as PyDict;
}

const sortedStrings = (items: Iterable<PyValue>): string[] => [...new Set(items)].map((item) => item as string).sort(cmpCodePoints);

function enable(env: PluginsEnv, repo: Repo, txn: ConfigTransaction, pluginId: string): number {
  const { args, kit } = env;
  const config = txn.config;
  requirePluginsSection(config, repo, kit);
  const view = pluginsView(config);
  const report = checkPluginSafe(kit, pluginId, allowedList(view));
  if (!isConsistent(report)) throw new ConfigError(`无法启用 ${pluginId}：${rejectReason(report)}`);
  const supplied = [...(args.allow_permission ?? [])];
  const newConfig = deepCopy(config) as PyDict;
  const messages: string[] = [];
  if (!view.enabledPresent) {
    messages.push("当前不限制，所有插件都算启用");
  } else if (Array.isArray(view.enabledValue) && !view.enabledValue.includes(pluginId)) {
    pluginsSection(newConfig).set("enabled", sortedStrings([...view.enabledValue, pluginId]));
  }
  let impact: string[] = [];
  let grantProblems: string[] = [];
  if (view.allowedPresent && Array.isArray(view.allowedValue)) {
    const missing = report.missingPermissions;
    const suppliedSet = new Set<PyValue>(supplied);
    if (missing.length) {
      const sameSet = suppliedSet.size === new Set(missing).size && missing.every((item) => suppliedSet.has(item));
      if (!sameSet) {
        throw new DispatchError(
          `启用 ${pluginId} 缺权限 ${missing.map(text).join("、")}，--allow-permission 必须一个不多一个不少地给出（收到 ${sortedStrings(supplied).join("、") || "无"}）`,
          EXIT_USAGE,
        );
      }
      const newAllowed = sortedStrings([...view.allowedValue, ...supplied]);
      pluginsSection(newConfig).set("allowed_permissions", newAllowed);
      [impact, grantProblems] = permissionImpact(kit, pluginId, new Set(view.allowedValue), new Set(newAllowed));
    } else if (supplied.length) {
      throw new DispatchError("没有缺失的权限，不需要 --allow-permission", EXIT_USAGE);
    }
  } else if (supplied.length) {
    throw new DispatchError("当前不限制权限，不需要 --allow-permission", EXIT_USAGE);
  }
  return finishMutation(env, repo, txn, config, newConfig, { messages, impact, grantProblems });
}

function disable(env: PluginsEnv, repo: Repo, txn: ConfigTransaction, pluginId: string): number {
  const { kit } = env;
  const config = txn.config;
  requirePluginsSection(config, repo, kit);
  const view = pluginsView(config);
  const newConfig = deepCopy(config) as PyDict;
  const messages: string[] = [];
  if (!view.enabledPresent) {
    const enabled = enumerateEntries(kit)
      .filter(([name, link]) => !link && name !== pluginId)
      .map(([name]) => name)
      .sort(cmpCodePoints);
    pluginsSection(newConfig).set("enabled", enabled);
    messages.push("从不限制改为显式列表，之后新增的插件不会自动启用");
  } else if (Array.isArray(view.enabledValue) && view.enabledValue.includes(pluginId)) {
    pluginsSection(newConfig).set("enabled", view.enabledValue.filter((name) => name !== pluginId).map((name) => name as string).sort(cmpCodePoints));
  }
  // 否则不在列表里：无变化
  if (pluginId === DECISIONS_PLUGIN_ID && isEnabled(view, DECISIONS_PLUGIN_ID) && !isEnabled(pluginsView(newConfig), DECISIONS_PLUGIN_ID)) {
    messages.push("决策插件会因此变为 off");
  }
  return finishMutation(env, repo, txn, config, newConfig, { messages, impact: [], grantProblems: [] });
}

function rejectReason(report: Report): string {
  const parts: string[] = [];
  if (report.lockStatus !== OK) parts.push(`锁${report.lockStatus}`);
  if (report.resourceStatus !== null && report.resourceStatus !== OK) parts.push(`资源${report.resourceStatus}`);
  parts.push(...report.problems);
  return parts.length ? parts.join("；") : MISMATCH;
}

function mutate(env: PluginsEnv, action: "enable" | "disable"): number {
  const repo = discover(env.args);
  const pluginId = validateId(env.args.plugin_id);
  requireExists(env.kit, pluginId);
  const ctx: WriteContext = { repo, kit: env.kit, lockWaitSeconds: env.lockWaitSeconds, out: env.out };
  // 读改写都在配置锁内
  return withConfigTransaction(ctx, `plugin.${action}`, pluginId, {}, (txn) => (action === "enable" ? enable(env, repo, txn, pluginId) : disable(env, repo, txn, pluginId)));
}

const HANDLERS: Readonly<Record<string, (env: PluginsEnv) => number>> = {
  list: cmdList,
  show: cmdShow,
  verify: cmdVerify,
  enable: (env) => mutate(env, "enable"),
  disable: (env) => mutate(env, "disable"),
};

/** 已移植的 plugins 子命令。 */
export const PLUGINS_ACTIONS = Object.keys(HANDLERS);

export function runPluginsCommand(action: string, env: PluginsEnv): number {
  const handler = HANDLERS[action];
  if (handler === undefined) throw new ConfigError(`内部错误：TS 实现还没有 plugins ${action}`, EXIT_USAGE);
  return handler(env);
}
