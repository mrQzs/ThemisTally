// pi_dispatch 的 validate_plan 一层与 validate、derive-json 两条命令（迁移第 ④b1 片）：按固定字节读合同对、planner-v2 的
// 发布门禁（codekit.planner.validate_publication_receipt 加内核自己的核对）、基线与角色绑定的提示、plan_key_from_arg。
// 读仓库、起 git；纯计算在 contract.ts。kit_roles 在 Python 里是惰性导入的可选模块，这里由调用方经 PlanContext 交进来：
// @themis/config 依赖本包，反过来导入会成环。
import { createHash } from "node:crypto";
import { lstatSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { PyCrash, type PyOut, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { displayPath, normCase, pyResolve } from "@themis/base/pypath";
import { codePoints, pyRegex, pySplitlines, pyStrip } from "@themis/base/pyre";
import { ProtocolError, strictJsonLoads } from "@themis/base/protocols";
import { TASK_ID_RE } from "@themis/base/secrets";
import { pyEq } from "@themis/base/pyvalue";
import {
  EXECUTOR_ROLES, LONG_TITLE_CHARS, SHA_RE, deriveContractJson, invisibleCharWarnings, mdIdentity, mdSection, validateContract,
} from "./contract.ts";
import { BindingRecordError, executorClass, loadBindingRecord } from "./executor.ts";
import { extraProtectedPaths, kernelProtectedPaths, plannerPaths, repoConfig } from "./kernel-config.ts";
import { compilePatterns, matches } from "./patterns.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_OK, EXIT_USAGE, Repo, git, gitText } from "./repo.ts";
import { PLAN_KEY_RE } from "./status.ts";

const NL = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const BT = "`";
export const NOTE_PREFIX = "NOTE：";

/** kit_roles 里 validate 用到的那一个函数（@themis/config/roles-binding 的 resolveRoleExecutor）。 */
export interface KitRoles {
  resolveRoleExecutor(config: PyDict, role: PyValue): [PyDict | null, { readonly message: string } | null];
}

/** 启动器经 context 交来的 kit 根与选择文件，加上调用方交进来的 kit_roles（Python 找不到它时是 None）。 */
export interface PlanContext {
  readonly kitRoot: string;
  readonly kernelImpl: Readonly<Record<string, string>>;
  readonly roles: KitRoles | null;
}

export type PlanResult = [PyDict | null, string[], string[]];

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const get = (dict: PyDict, key: string): PyValue => (dict.has(key) ? (dict.get(key) as PyValue) : null);

/** Path.exists、is_file：stat 跟随链接，出错一律当不是。 */
function exists(file: string): boolean {
  try {
    statSync(file);
    return true;
  } catch {
    return false;
  }
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

function isSymlink(file: string): boolean {
  try {
    return lstatSync(file).isSymbolicLink();
  } catch {
    return false;
  }
}

/** resolve_commit：解析成提交的完整 ID，不是提交时 null。 */
export function resolveCommit(root: string, sha: string): string | null {
  const proc = git(["rev-parse", "--verify", "--quiet", `${sha}^{commit}`], root);
  return proc.status === 0 ? pyStrip(proc.stdout.toString("utf8")) : null;
}

/** repo_protected_paths：配置的 extra_protected_paths 加上现算的内核 TS 禁区。 */
export function repoProtectedPaths(repo: Repo, ctx: PlanContext): string[] {
  return [...extraProtectedPaths(repoConfig(repo)), ...kernelProtectedPaths(repo.root, ctx.kitRoot, ctx.kernelImpl)];
}

/** plan_key_from_arg：计划标识，或 .agent/plans/ 下合同文件的路径（.md 或 .json）。 */
export function planKeyFromArg(repo: Repo, value: string): string {
  const text = pyStrip(value);
  if (PLAN_KEY_RE.test(text)) return text;
  const name = pathName(text);
  let stem = name;
  for (const suffix of [".md", ".json"]) {
    if (stem.endsWith(suffix)) {
      stem = stem.slice(0, -suffix.length);
      break;
    }
  }
  if (stem !== name && PLAN_KEY_RE.test(stem)) {
    const resolved = pyResolve(path.resolve(process.cwd(), text));
    if (normCase(path.dirname(resolved)) === normCase(pyResolve(repo.plansDir))) return stem;
    throw new DispatchError(`合同文件必须位于 ${displayPath(repo.plansDir, repo.root)} 下：${text}`, EXIT_USAGE);
  }
  throw new DispatchError(
    `计划标识不合法：${text}（格式 task-id.vN，例如 normalize-query.v1；也可以写成 .agent/plans/<task-id>.vN.md）`,
    EXIT_USAGE,
  );
}

const SEPARATORS = new RegExp(`[/${String.fromCharCode(92, 92)}]`, "u");

/** PureWindowsPath.name：去掉盘符，按斜杠分段后最后一段非空、非 . 的部分。 */
function pathName(text: string): string {
  const body = /^[A-Za-z]:/u.test(text) ? text.slice(2) : text;
  const parts = body.split(SEPARATORS).filter((part) => part !== "" && part !== ".");
  return parts[parts.length - 1] ?? "";
}

// --- validate_plan -------------------------------------------------------------------------------

/** validate_plan：读合同对的固定字节再校验，加上只在仓库里才看得出来的提示。 */
export function validatePlan(repo: Repo, planKey: string, ctx: PlanContext): PlanResult {
  if (!PLAN_KEY_RE.test(planKey)) return [null, [`计划标识不合法：${planKey}（格式 task-id.vN，例如 normalize-query.v1）`], []];
  const mdPath = path.join(repo.plansDir, `${planKey}.md`);
  const jsonPath = path.join(repo.plansDir, `${planKey}.json`);
  const missing: string[] = [];
  for (const file of [mdPath, jsonPath]) {
    if (!exists(file)) missing.push(`缺少文件：${displayPath(file, repo.root)}`);
    else if (isSymlink(file)) missing.push(`合同不能是符号链接：${displayPath(file, repo.root)}`);
  }
  if (missing.length) return [null, missing, []];
  let mdBytes: Buffer;
  let jsonBytes: Buffer;
  try {
    mdBytes = pyReadBytes(mdPath);
    jsonBytes = pyReadBytes(jsonPath);
  } catch (error) {
    if (error instanceof PyOSError) return [null, [`合同文件无法按固定字节读取：${error.message}`], []];
    throw error;
  }
  // 旧的边界：Markdown 不是 UTF-8 时 Python 不接，命令崩溃（锁定的 CLI 夹具靠它）
  const mdText = pyDecodeUtf8(mdBytes);
  const warnings: string[] = [];
  let loaded: [PyDict | null, string[], PyValue];
  try {
    loaded = loadFixedContractPair(repo, planKey, mdBytes, jsonBytes, mdText, warnings, ctx);
  } catch (error) {
    if (jsonParseError(error)) return [null, [`JSON 合同解析失败：${(error as Error).message}`], []];
    throw error;
  }
  let [contract] = loaded;
  const [, errors, raw] = loaded;
  warnings.push(...invisibleCharWarnings(mdText, "Markdown"));
  // 与 Python 的 decode("utf-8", "replace") 同义：开头的 BOM 留着，坏字节换成 U+FFFD（themistally-15 复核 ④b1 时建议）
  warnings.push(...invisibleCharWarnings(new TextDecoder("utf-8", { ignoreBOM: true }).decode(jsonBytes), "JSON"));
  const base = isDict(raw) ? get(raw, "base_sha") : null;
  if (typeof base === "string" && SHA_RE.test(base)) {
    if (resolveCommit(repo.root, base) !== base) {
      errors.push(`base_sha 在本仓库中不存在或不是提交：${base}`);
      contract = null;
    } else {
      if (git(["cat-file", "-e", `${base}:AGENTS.md`], repo.root).status !== 0) {
        warnings.push("基线提交中没有 AGENTS.md：worktree 基于基线创建，执行器将看不到执行规则");
      }
      const head = gitText(["rev-parse", "HEAD"], repo.root);
      if (head !== base) warnings.push(baseBehindHeadMessage(repo, base, head));
      warnings.push(...missingFactPathWarnings(repo, mdText, raw, base));
    }
  }
  warnings.push(...roleBindingWarnings(repo, raw, ctx));
  if (git(["check-ignore", "-q", ".agent/runs/probe"], repo.root).status !== 0) {
    warnings.push(".agent/runs/ 尚未被 .gitignore 忽略；prepare 会拒绝运行");
  }
  return [contract, errors, warnings];
}

/** validate_plan 的 `except (ValueError, UnicodeDecodeError)`：JSON 文法、UTF-8 与 planner-v2 严格解码的错误。 */
function jsonParseError(error: unknown): boolean {
  if (error instanceof PyJsonError) return error.kind !== "RecursionError";
  if (error instanceof PyCrash) return error.kind === "ValueError" || error.kind === "UnicodeDecodeError";
  return error instanceof PyUnicodeDecodeError || error instanceof ProtocolError;
}

/** _load_fixed_contract_pair：解析并校验已经读出来的这一对字节；planner-v2 先按家族认出来，再严格解码同一份字节。 */
export function loadFixedContractPair(
  repo: Repo, planKey: string, mdBytes: Buffer, jsonBytes: Buffer, mdText: string, warningsOut: string[], ctx: PlanContext,
): [PyDict | null, string[], PyValue] {
  let raw = loads(pyDecodeUtf8(jsonBytes));
  const plannerV2 = (value: PyValue): boolean => isDict(value) && pyEq(get(value, "contract_family"), "planner-v2");
  if (plannerV2(raw)) raw = strictJsonLoads(jsonBytes);
  let [contract, errors, contractWarnings] = validateContract(mdText, raw, planKey, repoProtectedPaths(repo, ctx));
  warningsOut.push(...contractWarnings);
  if (plannerV2(raw)) {
    errors = [...errors, ...verifyPlannerPublication(repo, planKey, mdBytes, jsonBytes)];
    if (errors.length) contract = null;
  }
  return [contract, errors, raw];
}

/** role_binding_warnings：按角色写的合同，这个版本还没有记录、当前绑定又用不了时提醒（prepare 会拒绝）。 */
export function roleBindingWarnings(repo: Repo, raw: PyValue, ctx: PlanContext): string[] {
  const executor = isDict(raw) ? get(raw, "executor") : null;
  if (executorClass(executor) !== "role" || !EXECUTOR_ROLES.some((role) => pyEq(role, get(executor as PyDict, "role")))) return [];
  const taskId = get(raw as PyDict, "task_id");
  const version = get(raw as PyDict, "plan_version");
  if (!(typeof taskId === "string" && TASK_ID_RE.test(taskId)) || typeof version !== "bigint") return [];
  try {
    if (loadBindingRecord(repo.root, taskId, version) !== null) return [];
  } catch (error) {
    if (error instanceof BindingRecordError) return [error.message];
    throw error;
  }
  if (ctx.roles === null) return ["合同按角色写 executor，但 scripts/kit_roles.py 不在本工具旁边：prepare 会拒绝"];
  let config: PyDict;
  try {
    config = repoConfig(repo);
  } catch (error) {
    if (error instanceof DispatchError) return [`读不出配置（${error.message}）：prepare 会拒绝`];
    throw error;
  }
  const role = get(executor as PyDict, "role");
  const [, problem] = ctx.roles.resolveRoleExecutor(config, role);
  if (problem !== null) return [`合同按角色写 executor（${pyStrValue(role)}），这个版本还没有记录、当前绑定也用不了：${problem.message}`];
  return [];
}

// Repository facts 里用反引号写的仓库相对文件：至少一个 /，以扩展名结尾，不含通配符；可以从点目录开始
const FACT_PATH_RE = pyRegex(`${BT}([.]?[A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+[.][A-Za-z0-9]{1,8})${BT}`, true);

/** missing_fact_path_warnings：Repository facts 点名的文件在基线里不存在时提示规划端。 */
export function missingFactPathWarnings(repo: Repo, mdText: string, raw: PyValue, base: string): string[] {
  const section = mdSection(mdText, "Repository facts") ?? "";
  const newFiles = allowedNewFiles(raw);
  const candidates: string[] = [];
  for (const match of section.matchAll(FACT_PATH_RE)) {
    const file = match[1] as string;
    if (candidates.includes(file) || newFiles.has(file) || [..."*?{}"].some((char) => file.includes(char))) continue;
    candidates.push(file);
  }
  // 合同常把路径写成相对项目子目录（检查的 cwd）的形式：除仓库根外，也按每个 cwd 找一遍
  const roots = ["."];
  if (isDict(raw)) {
    for (const item of [...pyList(get(raw, "checks")), ...pyList(get(raw, "setup"))]) {
      const cwd = isDict(item) ? get(item, "cwd") : null;
      if (typeof cwd !== "string") continue;
      const trimmed = trimSlashes(cwd);
      if (trimmed !== "" && trimmed !== "." && !roots.includes(trimmed)) roots.push(trimmed);
    }
  }
  const existsInBase = (file: string): boolean =>
    roots.some((root) => git(["cat-file", "-e", `${base}:${root === "." ? file : `${root}/${file}`}`], repo.root).status === 0);
  const absent = candidates.filter((file) => !existsInBase(file));
  const plannerFiles = absent.filter((file) => file.startsWith(".agent/"));
  const others = absent.filter((file) => !plannerFiles.includes(file));
  const short = codePoints(base).slice(0, 12).join("");
  const warnings: string[] = [];
  if (others.length) {
    warnings.push(`Repository facts 提到的文件在基线 ${short} 中不存在：${others.slice(0, 8).join("、")}——若它由同批的另一份合同产出，` +
      "等那份集成后再以新 HEAD 为基线");
  }
  if (plannerFiles.length) {
    warnings.push(`Repository facts 提到的规划文件在基线 ${short} 中不存在：${plannerFiles.slice(0, 8).join("、")}——执行器的 worktree 按基线创建，` +
      "读不到它们，也不得去主仓库读：改用包含它们的提交作为基线，或把需要的内容写进合同");
  }
  return warnings;
}

const trimSlashes = (text: string): string => text.replace(/^[/]+|[/]+$/gu, "");

/** set(scope.get("allowed_new_files") or [])：字符串拆成字符，字典取键，列表里有列表或字典、数字不可迭代时照 Python 抛 TypeError。 */
function allowedNewFiles(raw: PyValue): Set<PyValue> {
  const scope = isDict(raw) ? get(raw, "scope") : null;
  if (!isDict(scope)) return new Set();
  const items = pyList(get(scope, "allowed_new_files"));
  for (const item of items) if (Array.isArray(item) || isDict(item)) throw new PyCrash("TypeError", `unhashable type: '${Array.isArray(item) ? "list" : "dict"}'`);
  return new Set(items);
}

/** list(value or [])。 */
function pyList(value: PyValue): PyValue[] {
  if (!pyTruthy(value)) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") return codePoints(value);
  if (isDict(value)) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", `'${typeof value === "number" ? "float" : typeof value === "boolean" ? "bool" : "int"}' object is not iterable`);
}

/** base_behind_head_message：差异只在规划路径时降为 NOTE，碰到其他路径时是 WARN。 */
export function baseBehindHeadMessage(repo: Repo, base: string, head: string): string {
  const proc = git(["diff", "--name-only", base, head, "--"], repo.root);
  const short = codePoints(head).slice(0, 12).join("");
  if (proc.status === 0) {
    const changed = pySplitlines(proc.stdout.toString("utf8")).map(pyStrip).filter((line) => line);
    const compiled = compilePatterns(plannerPaths(repoConfig(repo)), process.platform === "win32");
    if (changed.length && changed.every((file) => matches(compiled, file))) {
      return `${NOTE_PREFIX}base_sha 不是当前 HEAD（${short}），但差异只在规划路径（${changed.slice(0, 5).join("、")}${changed.length > 5 ? "…" : ""}）：` +
        "按「先提交合同再派遣」的流程属正常";
    }
  }
  return `base_sha 不是当前 HEAD（${short}）；确认这是有意选择的输入版本`;
}

// --- planner-v2 的发布门禁 -----------------------------------------------------------------------

const RECEIPT_FIELDS = ["record_type", "schema_version", "publication_id", "candidate_id", "task_id", "plan_version", "members",
  "review_ref", "idempotency_key", "generation", "state", "outbox_seq"];
const IDENTITY_RE = /^[a-z0-9][a-z0-9._:-]{0,127}$/u;
const TASK_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/u;
const HEX64 = /^[0-9a-f]{64}$/u;
const RECEIPT_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/u;

/** codekit.planner.PlannerError：str(exc) 是 `<码> at <字段>: <说明>`。 */
class PlannerError extends Error {
  constructor(code: string, message: string, field = "/") {
    super(`${code} at ${field}: ${message}`);
  }
}

const sameKeys = (dict: PyDict, keys: readonly string[]): boolean => dict.size === keys.length && keys.every((key) => dict.has(key));
const isExactInt = (value: PyValue): value is bigint => typeof value === "bigint";

/** planner._text：非空、不超过 256 个字符的文字，不含控制字符与孤立代理项，给了 pattern 就要整串匹配。 */
function plannerText(value: PyValue, field: string, pattern?: RegExp): void {
  if (typeof value !== "string" || !value || codePoints(value).length > 256) throw new PlannerError("E_SCHEMA_FIELDS", "non-empty text required", field);
  const bad = codePoints(value).some((char) => {
    const code = char.codePointAt(0) as number;
    return code < 0x20 || (code >= 0x7f && code <= 0x9f) || (code >= 0xd800 && code <= 0xdfff);
  });
  if (bad) throw new PlannerError("E_JSON_UNICODE", "Unicode scalar text required", field);
  if (pattern && !pattern.test(value)) throw new PlannerError("E_ID_SYNTAX", "invalid identifier", field);
}

/**
 * codekit.planner.validate_publication_receipt 的判定部分。末尾的 _json_value（check_json_value，1 MiB 的字节下界）对这里
 * 不可能失败：回执是 strict_json_loads 从不超过 1 MiB 的原文解出来的，每类值的下界都不超过它在原文里的字节数，深度上限也相同。
 * 前提：value 必须是缺省上限（1 MiB、64 层）的 strictJsonLoads 的结果。以后（第 ⑤ 步）要用在别处来的值上，先移植这道检查
 * （themistally-15 复核 ④b1 时核对过这条论证）。
 */
export function validatePublicationReceipt(value: PyValue): void {
  if (!isDict(value)) throw new PlannerError("E_SCHEMA_TYPE", "publication receipt object required");
  if (!sameKeys(value, RECEIPT_FIELDS)) throw new PlannerError("E_SCHEMA_FIELDS", "publication receipt fields must be closed");
  if (!pyEq(get(value, "record_type"), "publication-receipt") || !pyEq(get(value, "schema_version"), 1n)) {
    throw new PlannerError("E_SCHEMA_VERSION", "publication-receipt v1 required");
  }
  for (const key of ["publication_id", "candidate_id", "idempotency_key"]) plannerText(get(value, key), `/${key}`, IDENTITY_RE);
  plannerText(get(value, "task_id"), "/task_id", TASK_RE);
  const planVersion = get(value, "plan_version");
  if (!isExactInt(planVersion) || planVersion < 1n) throw new PlannerError("E_SCHEMA_FIELDS", "positive plan version required", "/plan_version");
  const members = get(value, "members");
  if (!isDict(members) || !sameKeys(members, ["markdown_sha256", "json_sha256"])) throw new PlannerError("E_SCHEMA_FIELDS", "both member hashes required", "/members");
  plannerText(get(members, "markdown_sha256"), "/members/markdown_sha256", HEX64);
  plannerText(get(members, "json_sha256"), "/members/json_sha256", HEX64);
  const review = get(value, "review_ref");
  if (!isDict(review) || !pyEq(get(review, "decision"), "APPROVED")) throw new PlannerError("E_REVIEW_BINDING", "approved review reference required", "/review_ref");
  if (!review.has("approval_id") && !review.has("approval_ref")) throw new PlannerError("E_REVIEW_BINDING", "approval reference required", "/review_ref");
  if (review.has("candidate_id") && !pyEq(get(review, "candidate_id"), get(value, "candidate_id"))) {
    throw new PlannerError("E_REVIEW_BINDING", "review candidate id does not match receipt", "/review_ref/candidate_id");
  }
  const approvalRef = get(review, "approval_ref");
  if (approvalRef !== null) {
    if (!isDict(approvalRef) || !sameKeys(approvalRef, ["scope", "generation", "sha256"])) {
      throw new PlannerError("E_REVIEW_BINDING", "approval_ref must be a closed currentness proof", "/review_ref/approval_ref");
    }
    plannerText(get(approvalRef, "scope"), "/review_ref/approval_ref/scope", IDENTITY_RE);
    const generation = get(approvalRef, "generation");
    if (!isExactInt(generation) || generation < 1n) throw new PlannerError("E_REVIEW_BINDING", "approval_ref generation required", "/review_ref/approval_ref/generation");
    plannerText(get(approvalRef, "sha256"), "/review_ref/approval_ref/sha256", HEX64);
  }
  const generation = get(value, "generation");
  if (!isExactInt(generation) || generation < 1n) throw new PlannerError("E_SCHEMA_FIELDS", "positive generation required", "/generation");
  const outboxSeq = get(value, "outbox_seq");
  if (!pyEq(get(value, "state"), "PUBLISHED") || !isExactInt(outboxSeq) || outboxSeq < 1n) {
    throw new PlannerError("E_SCHEMA_FIELDS", "published state and positive outbox sequence required");
  }
}

/** bytes.splitlines()：只认 LF、CR 与 CRLF。 */
function byteLines(raw: Buffer): Buffer[] {
  const lines: Buffer[] = [];
  let start = 0;
  for (let at = 0; at < raw.length; at += 1) {
    const byte = raw[at] as number;
    if (byte !== 10 && byte !== 13) continue;
    lines.push(raw.subarray(start, at));
    if (byte === 13 && raw[at + 1] === 10) at += 1;
    start = at + 1;
  }
  if (start < raw.length) lines.push(raw.subarray(start));
  return lines;
}

const sha256 = (raw: Uint8Array): string => createHash("sha256").update(raw).digest("hex");

/** 读回执、outbox 时 Python 的 `except Exception`：交回 str(exc)；认不出的异常照样抛出。 */
function failureText(error: unknown): string {
  if (error instanceof PyOSError || error instanceof ProtocolError || error instanceof PyCrash) return error.message;
  throw error;
}

/** verify_planner_publication：planner-v2 合同要有登记回执，回执要与固定的合同字节和持久 outbox 对上。 */
export function verifyPlannerPublication(repo: Repo, planKey: string, mdBytes: Buffer, jsonBytes: Buffer): string[] {
  const at = planKey.lastIndexOf(".v");
  const taskId = planKey.slice(0, at);
  const version = planKey.slice(at + 2);
  const root = path.join(repo.root, ".agent", "publications");
  const receiptPath = path.join(root, `${taskId}.v${version}.json`);
  if (!isFile(receiptPath) || isSymlink(receiptPath)) {
    return [`planner-v2 合同缺少登记回执：${displayPath(receiptPath, repo.root)}（旧人工 v1 需移除 contract_family 或走显式兼容登记）`];
  }
  let receipt: PyValue;
  try {
    receipt = strictJsonLoads(pyReadBytes(receiptPath));
  } catch (error) {
    return [`planner-v2 发布回执解析失败：${failureText(error)}`];
  }
  if (!isDict(receipt)) return ["planner-v2 发布回执必须是对象"];
  try {
    validatePublicationReceipt(receipt);
  } catch (error) {
    if (error instanceof PlannerError) return [`planner-v2 发布回执严格校验失败：${error.message}`];
    throw error;
  }
  return receiptProblems(receipt, taskId, BigInt(version), mdBytes, jsonBytes, root);
}

/** 回执过了 validate_publication_receipt 之后，内核自己再核对的几项（多数已被它挡下，照 Python 保留）。 */
function receiptProblems(receipt: PyDict, taskId: string, version: bigint, mdBytes: Buffer, jsonBytes: Buffer, root: string): string[] {
  if (!sameKeys(receipt, RECEIPT_FIELDS)) return ["planner-v2 发布回执字段不完整"];
  if (!pyEq(get(receipt, "record_type"), "publication-receipt") || !pyEq(get(receipt, "schema_version"), 1n)) return ["planner-v2 发布回执类型或版本不受支持"];
  if (!pyEq(get(receipt, "state"), "PUBLISHED")) return [`planner-v2 发布回执不是当前登记状态：${pyReprValue(get(receipt, "state"))}`];
  if (!pyEq(get(receipt, "task_id"), taskId) || !pyEq(get(receipt, "plan_version"), version)) return ["planner-v2 发布回执的任务或版本不匹配"];
  for (const field of ["publication_id", "candidate_id", "idempotency_key"]) {
    const value = get(receipt, field);
    if (typeof value !== "string" || !RECEIPT_ID_RE.test(value)) return [`planner-v2 发布回执 ${field} 标识无效`];
  }
  const generation = get(receipt, "generation");
  const outboxSeq = get(receipt, "outbox_seq");
  if (!isExactInt(generation) || generation < 1n || !isExactInt(outboxSeq) || outboxSeq < 1n) return ["planner-v2 发布回执缺少登记 generation/outbox 序号"];
  const review = get(receipt, "review_ref");
  if (!isDict(review) || !pyEq(get(review, "decision"), "APPROVED")) return ["planner-v2 发布回执缺少当前 APPROVED 审核绑定"];
  if (!review.has("approval_id") && !review.has("approval_ref")) return ["planner-v2 发布回执缺少 approval_id/approval_ref"];
  const reviewCandidate = get(review, "candidate_id");
  if (reviewCandidate !== null && !pyEq(reviewCandidate, get(receipt, "candidate_id"))) return ["planner-v2 发布回执 candidate_id 与审核绑定不一致"];
  const approvalRef = get(review, "approval_ref");
  if (approvalRef !== null) {
    if (!isDict(approvalRef) || !sameKeys(approvalRef, ["scope", "generation", "sha256"])) return ["planner-v2 发布回执 approval_ref 不完整"];
    const refGeneration = get(approvalRef, "generation");
    const scope = get(approvalRef, "scope");
    if (!isExactInt(refGeneration) || refGeneration < 1n || typeof scope !== "string" || !RECEIPT_ID_RE.test(scope) ||
        !HEX64.test(pyStrValue(get(approvalRef, "sha256")))) {
      return ["planner-v2 发布回执 approval_ref currentness proof 无效"];
    }
  }
  const members = get(receipt, "members");
  if (!isDict(members)) return ["planner-v2 发布回执缺少双格式成员摘要"];
  for (const [key, digest] of [["markdown_sha256", sha256(mdBytes)], ["json_sha256", sha256(jsonBytes)]] as const) {
    if (!pyEq(get(members, key), digest)) return [`planner-v2 发布回执的 ${key} 与固定合同字节不一致`];
  }
  // 回执是投影；持久 outbox 里那一条才是登记的证明，手写的回执没有它，进不了任何执行入口
  const outboxPath = path.join(root, "outbox.jsonl");
  if (!isFile(outboxPath) || isSymlink(outboxPath)) return ["planner-v2 发布回执缺少持久 outbox 登记"];
  const ledgerMatches: PyValue[] = [];
  try {
    for (const line of byteLines(pyReadBytes(outboxPath))) {
      if (!line.length) continue;
      const item = strictJsonLoads(line);
      if (isDict(item) && pyEq(get(item, "publication_id"), get(receipt, "publication_id"))) ledgerMatches.push(item);
    }
  } catch (error) {
    return [`planner-v2 持久 outbox 无法解析：${failureText(error)}`];
  }
  if (ledgerMatches.length !== 1 || !pyEq(ledgerMatches[0] as PyValue, receipt)) return ["planner-v2 回执与持久 outbox 登记不一致"];
  return [];
}

// --- 命令 ----------------------------------------------------------------------------------------

export interface ValidateArgs {
  readonly repo: string | null;
  readonly plan_key: string;
}

export interface DeriveJsonArgs extends ValidateArgs {
  readonly title: string | null;
  readonly force: boolean;
  readonly print_only: boolean;
}

/** _print_messages：以 NOTE： 开头的警告写成 NOTE，其余写成 WARN，然后是错误。 */
export function printMessages(out: PyOut, errors: readonly string[], warnings: readonly string[]): void {
  for (const warning of warnings) {
    out.print(warning.startsWith(NOTE_PREFIX) ? `NOTE  ${warning.slice(NOTE_PREFIX.length)}` : `WARN  ${warning}`);
  }
  for (const error of errors) out.print(`ERROR ${error}`);
}

function report(out: PyOut, key: string, errors: readonly string[], warnings: readonly string[]): boolean {
  printMessages(out, errors, warnings);
  if (errors.length) {
    out.print(`合同无效：${errors.length} 个错误，${warnings.length} 个警告。`);
    return false;
  }
  out.print(`合同有效：${key}（${warnings.length} 个警告）。`);
  return true;
}

export function cmdValidate(args: ValidateArgs, out: PyOut, ctx: PlanContext): number {
  const repo = Repo.discover(args.repo);
  const key = planKeyFromArg(repo, args.plan_key);
  const [, errors, warnings] = validatePlan(repo, key, ctx);
  return report(out, key, errors, warnings) ? EXIT_OK : EXIT_USAGE;
}

/** derive-json：由 .agent/plans/<plan-key>.md 生成同名 .json，然后立即校验两者是否一致。 */
export function cmdDeriveJson(args: DeriveJsonArgs, out: PyOut, ctx: PlanContext): number {
  const repo = Repo.discover(args.repo);
  const key = planKeyFromArg(repo, args.plan_key);
  const mdPath = path.join(repo.plansDir, `${key}.md`);
  const jsonPath = path.join(repo.plansDir, `${key}.json`);
  if (!isFile(mdPath)) throw new DispatchError(`缺少文件：${displayPath(mdPath, repo.root)}`, EXIT_USAGE);
  const mdText = pyDecodeUtf8(pyReadBytes(mdPath));
  if (pyEq(mdIdentity(mdText).get("contract_family") ?? null, "planner-v2")) {
    throw new DispatchError("planner-v2 合同必须由发布登记入口冻结，derive-json 不得降级生成 v1 JSON；请使用显式兼容登记或重新生成候选", EXIT_BLOCKED);
  }
  if (isFile(jsonPath) && declaresPlannerV2(pyReadBytes(jsonPath))) {
    throw new DispatchError("现有 JSON 已声明 planner-v2，derive-json 不得用 v1 输出覆盖登记合同", EXIT_BLOCKED);
  }
  const [contract, problems] = deriveContractJson(mdText, args.title);
  for (const problem of problems) out.print(`WARN  ${problem}`);
  const title = get(contract, "title");
  const derivedTitle = typeof title === "string" ? title : "";
  if (!args.title && codePoints(derivedTitle).length > LONG_TITLE_CHARS) {
    out.print(`NOTE  标题取自 Goal 第一行（${codePoints(derivedTitle).length} 字），会成为分支提交的主题行，也显示在 status 与指标里；` +
      "较长时用 --title 指定一句短标题（加 --force 覆盖已生成的 JSON）");
  }
  const text = dumps(contract, { ensureAscii: false, indent: 2 });
  if (args.print_only) {
    out.print(text);
    return problems.length ? EXIT_USAGE : EXIT_OK;
  }
  if (exists(jsonPath) && !args.force) throw new DispatchError(`${displayPath(jsonPath, repo.root)} 已存在；确认要覆盖时加 --force`, EXIT_USAGE);
  // write_text 是文本模式：Windows 上换行写成 CRLF
  writeFileSync(jsonPath, `${text}${NL}`.split(NL).join(process.platform === "win32" ? CR + NL : NL), "utf8");
  out.print(`已写入 ${displayPath(jsonPath, repo.root)}`);
  const [, errors, warnings] = validatePlan(repo, key, ctx);
  if (!report(out, key, errors, warnings)) return EXIT_USAGE;
  return problems.length ? EXIT_USAGE : EXIT_OK;
}

/** 现有 JSON 声明了 planner-v2：读不出 UTF-8、不是 JSON 都算没声明；嵌套太深时 Python 不接，照样抛出。 */
function declaresPlannerV2(raw: Buffer): boolean {
  let value: PyValue;
  try {
    value = loads(pyDecodeUtf8(raw));
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError || (error instanceof PyJsonError && error.kind !== "RecursionError")) return false;
    throw error;
  }
  return isDict(value) && pyEq(get(value, "contract_family"), "planner-v2");
}
