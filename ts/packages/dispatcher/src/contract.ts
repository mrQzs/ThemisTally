// pi_dispatch 的合同解析与校验（迁移第 ④b1 片）：Markdown 合同的各节（_md_*）、normalize_contract、derive_contract_json、
// validate_contract、invisible_char_warnings、branch_subject。只做纯计算，不读仓库、不起 Git（validate_plan 在 contract-plan）。
// Python 正则逐条译成 JS：\s \d \w \b 用 pyre 的区间表；不带 MULTILINE 的 $ 写成 PY_END（放过末尾的换行），MULTILINE 的
// ^ 写成 (?<![^\n])、$ 写成 (?=\n|$)，\Z 是 JS 的 $；. 只不配 \n。合同里用户写的正则（output_must_match）交给 sre 移植编译。
// 切片与长度一律按码点。
import { PyCrash, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { PyReError, PyValueError, compilePattern } from "@themis/base/pyregex";
import { D, NOT_S, PY_END, S, WB, ci, cmpCodePoints, codePoints, isCf, isDigitChar, pyIntParse, pyLower, pyLstrip, pyRegex, pySplit, pySplitlines, pyStrip } from "@themis/base/pyre";
import { ENV_NAME_RE } from "@themis/base/secrets";
import { ShlexError, shlexSplit } from "@themis/base/pyshlex";
import { pyEq } from "@themis/base/pyvalue";
import { DEFAULT_THINKING, executorClass } from "./executor.ts";
import { compilePatterns, matches, patternError, PROTECTED_PATTERNS } from "./patterns.ts";
import { FALLBACK_THINKING_LEVELS } from "./pi-cli.ts";
import { PLAN_KEY_RE } from "./status.ts";

const BT = "`";
/** MULTILINE 的 ^：开头或 \n 之后。 */
const LINE_START = "(?<![^\\n])";

export const CONTRACT_SCHEMA_VERSION = 1n;
export const SHA_RE = pyRegex(`^(?:[0-9a-f]{40}|[0-9a-f]{64})${PY_END}`);
export const ITEM_ID_RE = pyRegex(`^[A-Z][A-Z0-9_-]{0,31}${PY_END}`);
export const MODEL_TOKEN_RE = pyRegex(`^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}${PY_END}`);
export const PLACEHOLDER_RE = pyRegex("【待填|REPLACE_WITH");
export const ROLE_EXECUTOR_RE = pyRegex(`^role:(execution|contract)${PY_END}`);
export const KNOWN_TOOLS = ["read", "bash", "powershell", "edit", "write", "grep", "find", "ls"];
export const DEFAULT_TOOLS = ["read", "grep", "find", "ls", "edit", "write", "bash"];
export const EXECUTOR_ACTIONS = ["local_edit", "local_test", "local_commit", "network"];
export const INTEGRATION_ACTIONS = ["local_branch", "commit", "push", "open_pr", "merge", "deploy"];
export const RISK_LEVELS = ["low", "medium", "high"];
export const EVIDENCE_TOKENS = ["scope", "review"];
export const EXECUTOR_ROLES = ["execution", "contract"];
export const REQUIRED_MD_SECTIONS = [
  "Identity", "Goal", "Non-goals", "Repository facts", "Scope", "Behavior contract", "Steps", "Validation commands",
  "Definition of done", "Stop conditions", "Budget", "Report back", "Forbidden",
];
/** derive-json 没有 --title、从 Goal 第一行取到的标题超过这个字数时提示改用 --title。 */
export const LONG_TITLE_CHARS = 60;

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isInt = (value: PyValue | undefined): value is bigint => typeof value === "bigint";
/** isinstance(x, int)：bool 也算。 */
const isIntOrBool = (value: PyValue | undefined): boolean => typeof value === "bigint" || typeof value === "boolean";
const isStrList = (value: PyValue | undefined): value is string[] => Array.isArray(value) && value.every((item) => typeof item === "string");
const get = (dict: PyDict, key: string, fallback: PyValue = null): PyValue => (dict.has(key) ? (dict.get(key) as PyValue) : fallback);

/** str.strip(chars) 一类：去掉两头（或一头）属于 chars 的字符，按码点。 */
function stripChars(text: string, chars: string, left = true, right = true): string {
  const set = new Set(codePoints(chars));
  const list = codePoints(text);
  let start = 0;
  let end = list.length;
  if (left) while (start < end && set.has(list[start] as string)) start += 1;
  if (right) while (end > start && set.has(list[end - 1] as string)) end -= 1;
  return list.slice(start, end).join("");
}

/** 一个字面串照 re.escape 之后的匹配：每个码点写成 \u{…} 转义（JS 的 u 正则）。 */
function literal(text: string): string {
  return codePoints(text)
    .map((char) => `${String.fromCharCode(92)}${"u"}{${(char.codePointAt(0) as number).toString(16)}}`)
    .join("");
}

const firstInt = (text: string): bigint => {
  const value = pyIntParse(text);
  if (value === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: ${pyReprValue(text)}`);
  return value;
};

// --- Markdown 的各节 -----------------------------------------------------------------------------

/** _md_section：## 名字（不分大小写）之后到下一个 ## 之前的内容；没有为 null。 */
export function mdSection(md: string, name: string): string | null {
  const pattern = pyRegex(`${LINE_START}##${S}+${ci(name)}${S}*(?=\\n|$)([^]*?)(?=${LINE_START}##${S}|$)`);
  const match = pattern.exec(md);
  return match ? (match[1] as string) : null;
}

const VALUE_NOTE_RE = pyRegex(`${S}*(?:（[^（）]*）|\\([^()]*\\))${S}*${PY_END}`, true);

/** _md_value：去掉反引号与结尾的括号说明。 */
export function mdValue(raw: string): string {
  return stripChars(stripChars(raw, `${BT} `).replace(VALUE_NOTE_RE, ""), `${BT} `);
}

const IDENTITY_LINE_RE = pyRegex(`^${S}*[-*]${S}*([A-Za-z_]+)${S}*:${S}*([^\\n]+?)${S}*${PY_END}`);

export function mdIdentity(md: string): Map<string, string> {
  const identity = new Map<string, string>();
  for (const line of pySplitlines(mdSection(md, "Identity") ?? "")) {
    const match = IDENTITY_LINE_RE.exec(line);
    if (match) identity.set(match[1] as string, mdValue(match[2] as string));
  }
  return identity;
}

const MINUTES_RE = pyRegex(`约${S}*(${D}+)${S}*分钟`, true);

/** _md_time_allocation_minutes：Budget 段“时间分配”条目下各子项“约 N 分钟”的合计；没有为 null。 */
export function mdTimeAllocationMinutes(md: string): bigint | null {
  const lines = pySplitlines(mdSection(md, "Budget") ?? "");
  const start = lines.findIndex((line) => line.includes("时间分配"));
  if (start < 0) return null;
  const indentOf = (line: string): number => codePoints(line).length - codePoints(pyLstrip(line)).length;
  const indent = indentOf(lines[start] as string);
  let total = 0n;
  for (const line of lines.slice(start + 1)) {
    const stripped = pyStrip(line);
    if (!stripped) continue;
    const first = codePoints(stripped)[0] as string;
    if ((first === "-" || first === "*") && indentOf(line) <= indent) break;
    for (const match of line.matchAll(MINUTES_RE)) total += firstInt(match[1] as string);
  }
  return total === 0n ? null : total;
}

const BUDGET_KEYS = ["max_attempts_total", "max_wall_seconds_per_attempt", "max_wall_seconds_total"];

export function mdBudget(md: string): Map<string, string> {
  const section = mdSection(md, "Budget") ?? "";
  const found = new Map<string, string>();
  for (const key of BUDGET_KEYS) {
    const match = pyRegex(`${LINE_START}${S}*[-*]${S}*${key}${S}*:${S}*${BT}?(${D}+)`).exec(section);
    if (match) found.set(key, match[1] as string);
  }
  return found;
}

const SCOPE_LINE_RE = pyRegex(`^[-*]${S}*([a-z_]+)${S}*:${S}*([^\\n]*?)${S}*${PY_END}`);
const SCOPE_ITEM_RE = pyRegex(`^${S}+[-*]${S}*([^\\n]+?)${S}*${PY_END}`);
const SCOPE_SPLIT_RE = pyRegex(`[,，、]${S}*`);

/** _md_scope_lists：`- key: a, b`（同行）或 `- key:` 后跟缩进的 `  - path` 列表；`无` 表示空。 */
export function mdScopeLists(md: string): Map<string, PyValue> {
  const lines = pySplitlines(mdSection(md, "Scope") ?? "");
  const found = new Map<string, PyValue>();
  lines.forEach((line, index) => {
    const match = SCOPE_LINE_RE.exec(line);
    if (!match) return;
    const key = match[1] as string;
    const rest = match[2] as string;
    if (key === "dependency_changes") {
      found.set(key, mdValue(rest));
      return;
    }
    const items: string[] = [];
    const lowered = pyLower(rest);
    if (rest && !rest.startsWith("无") && lowered !== "none" && lowered !== "[]") {
      for (const part of rest.split(SCOPE_SPLIT_RE)) {
        const value = stripChars(part, `${BT} `);
        if (value) items.push(value);
      }
    } else {
      for (const follow of lines.slice(index + 1)) {
        const item = SCOPE_ITEM_RE.exec(follow);
        if (!item) break;
        items.push(stripChars(item[1] as string, `${BT} `));
      }
    }
    found.set(key, items);
  });
  return found;
}

/** _CHECK_LINE_RE。 */
export const CHECK_LINE_RE = pyRegex(
  `^[-*]${S}*(?<id>[A-Z]${D}{2,})(?:（(?<kind>[^）]*)）|\\((?<kind2>[^)]*)\\))?${S}*[:：]${S}*${BT}(?<cmd>[^\\n]+?)${BT}(?<rest>[^\\n]*)${PY_END}`,
);
const CWD_RE = pyRegex(`cwd${S}*[:：]${S}*${BT}?([^·${BT}]+?)${BT}?${S}*(?:·|${PY_END})`);
const TIMEOUT_CN_RE = pyRegex(`超时${S}*[:：]${S}*(${D}+)${S}*s`);
const TIMEOUT_EN_RE = pyRegex(`${ci("timeout")}${S}*[:：]${S}*(${D}+)`);
const EXIT_CODE_RE = pyRegex(`期望退出码${S}*[:：]${S}*(-?${D}+)`);
const MUST_RE = pyRegex(`输出须匹配${S}*[:：]?${S}*([^\\n]*?)(?:[，,]${S}*不得|${PY_END})`);
const MUST_NOT_RE = pyRegex(`不得(?:出现|匹配)${S}*[:：]?${S}*([^\\n]*)${PY_END}`);
const BACKTICKED_RE = pyRegex(`${BT}([^${BT}]+)${BT}`, true);
const PYTHON_C = 'python -c "';

export function mdBaseExpectation(markers: string): string {
  if (markers.includes("基线应失败")) return "fail";
  return markers.includes("基线应通过") ? "pass" : "any";
}

/** _md_command_items：Validation commands（或 Setup）里的命令行。返回（各项，要人工处理的问题）。 */
export function mdCommandItems(md: string, sectionName: string): [PyDict[], string[]] {
  const items: PyDict[] = [];
  const problems: string[] = [];
  for (const line of pySplitlines(mdSection(md, sectionName) ?? "")) {
    const match = CHECK_LINE_RE.exec(pyStrip(line));
    if (!match) continue;
    const groups = match.groups as Record<string, string | undefined>;
    const cid = groups["id"] as string;
    const cmd = groups["cmd"] as string;
    const rest = groups["rest"] as string;
    const kind = groups["kind"] || groups["kind2"] || "";
    let argv: string[];
    if (cmd.startsWith(PYTHON_C) && cmd.endsWith('"')) {
      argv = ["python", "-c", codePoints(cmd).slice(codePoints(PYTHON_C).length, -1).join("")];
    } else {
      try {
        argv = shlexSplit(cmd);
      } catch (error) {
        if (!(error instanceof ShlexError)) throw error;
        problems.push(`${cid} 的命令无法拆分：${error.message}`);
        continue;
      }
      if (!argv.every((token) => line.includes(token))) {
        problems.push(`${cid} 的命令含引号或转义，无法可靠地还原参数；请手写 JSON 中的 argv`);
        continue;
      }
    }
    const item: PyDict = new Map<string, PyValue>([["id", cid], ["argv", argv], ["cwd", "."]]);
    const cwd = CWD_RE.exec(rest);
    if (cwd && !["仓库根", ".", "repo root"].includes(pyStrip(cwd[1] as string))) item.set("cwd", pyStrip(cwd[1] as string));
    const timeout = TIMEOUT_CN_RE.exec(rest) ?? TIMEOUT_EN_RE.exec(rest);
    item.set("timeout_seconds", timeout ? firstInt(timeout[1] as string) : 600n);
    if (sectionName === "Validation commands") item.set("required", !(kind.includes("可选") || pyLower(kind).includes("optional")));
    const code = EXIT_CODE_RE.exec(rest);
    item.set("expected_exit_code", code ? firstInt(code[1] as string) : 0n);
    const must = MUST_RE.exec(rest);
    if (must) item.set("output_must_match", [...(must[1] as string).matchAll(BACKTICKED_RE)].map((found) => found[1] as string));
    const mustNot = MUST_NOT_RE.exec(rest);
    if (mustNot) item.set("output_must_not_match", [...(mustNot[1] as string).matchAll(BACKTICKED_RE)].map((found) => found[1] as string));
    const expectation = mdBaseExpectation(kind + rest);
    if (sectionName === "Validation commands" && expectation !== "any") item.set("expect_on_base", expectation);
    items.push(item);
  }
  return [items, problems];
}

const LOOSE_ID_RE = pyRegex(`^[-*]${S}*${BT}?(?<id>[A-Z][A-Z0-9_-]{0,31})${BT}?(?![A-Za-z0-9_-])`);
const BACKTICK_SPAN_RE = pyRegex(`${BT}[^${BT}]*${BT}`, true);

/** _md_check_base_expectations：Validation commands 中每个检查编号的基线期望（同一编号多行时逐行记录）。 */
export function mdCheckBaseExpectations(validation: string): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const line of pySplitlines(validation)) {
    const text = pyStrip(line);
    let cid: string;
    let markers: string;
    const match = CHECK_LINE_RE.exec(text);
    if (match) {
      const groups = match.groups as Record<string, string | undefined>;
      cid = groups["id"] as string;
      markers = (groups["kind"] || groups["kind2"] || "") + (groups["rest"] as string);
    } else {
      const loose = LOOSE_ID_RE.exec(text);
      if (!loose) continue;
      cid = (loose.groups as Record<string, string>)["id"] as string;
      markers = text.slice(loose[0].length).replace(BACKTICK_SPAN_RE, "");
    }
    const list = found.get(cid) ?? [];
    list.push(mdBaseExpectation(markers));
    found.set(cid, list);
  }
  return found;
}

const ACTION_RE = pyRegex("[a-z_]+", true);

/** _md_action_list：保留书写顺序并去重（生成 JSON 用）。 */
export function mdActionList(value: string | null | undefined): string[] {
  const out: string[] = [];
  for (const match of (value ?? "").matchAll(ACTION_RE)) {
    const token = match[0];
    if (token !== "none" && !out.includes(token)) out.push(token);
  }
  return out;
}

/** _md_action_set：none、无、空都是空集合；没写为 null。 */
export function mdActionSet(value: string | null | undefined): Set<string> | null {
  if (value == null) return null;
  return new Set([...value.matchAll(ACTION_RE)].map((match) => match[0]).filter((token) => token !== "none"));
}

/** branch_subject：分支提交的主题行。 */
export function branchSubject(taskId: string, title: PyValue, planVersion: PyValue, attemptNo: bigint): string {
  if (typeof title === "string" && pyStrip(title)) {
    const text = pySplit(title).join(" ");
    const after = codePoints(text).slice(codePoints(taskId).length, codePoints(taskId).length + 1).join("");
    if (text.startsWith(taskId) && [":", "：", " "].includes(after)) return text;
    return `${taskId}: ${text}`;
  }
  // %03d：负号算在宽度里（-1 是 -01）
  const sign = attemptNo < 0n ? "-" : "";
  const digits = String(attemptNo < 0n ? -attemptNo : attemptNo).padStart(3 - sign.length, "0");
  return `${taskId}: Pi 候选 v${pyStrValue(planVersion)} attempt ${sign}${digits}`;
}

// --- derive-json -----------------------------------------------------------------------------------

const TASK_LINE_RE = pyRegex(`^#${S}*TASK:${S}*([a-z0-9][a-z0-9-]*)${S}*${PY_END}`);
const EXEC_RE = pyRegex(`^((?:(?!/)${NOT_S})+)/(${NOT_S}+)${S}*·${S}*thinking${S}+(${NOT_S}+)`);
const DOD_LINE_RE = pyRegex(`^${S}*[-*]${S}*(D${D}{2,})${S}*[:：]${S}*([^\\n]+?)${S}*${PY_END}`);
const INTENT_RE = pyRegex(`[；;]${S}*目的${S}*[:：]${S}*([^；;]+)`);
const EVIDENCE_LABELLED_RE = pyRegex(`[；;]${S}*证据${S}*[:：]`, true);
const EVIDENCE_LOOSE_RE = pyRegex(`[；;]${S}*证据`);
const EVIDENCE_REF_RE = pyRegex(`(?<![A-Za-z0-9])([A-Z]${D}{2,}|scope|review)(?![A-Za-z0-9])`, true);

/** str.isdigit（整串）。 */
const isDigits = (text: string): boolean => text.length > 0 && codePoints(text).every(isDigitChar);

/** derive_contract_json：由 Markdown 合同生成机器合同。返回（合同，要人工处理的问题）。 */
export function deriveContractJson(md: string, title: string | null = null): [PyDict, string[]] {
  const problems: string[] = [];
  const identity = mdIdentity(md);
  const first = md ? (pySplitlines(md)[0] ?? "") : "";
  const taskMatch = TASK_LINE_RE.exec(first);
  if (!taskMatch) problems.push("第一行必须是 `# TASK: <task-id>`");
  const executor = identity.get("executor") ?? "";
  const roleMatch = ROLE_EXECUTOR_RE.exec(pyStrip(executor));
  const execMatch = roleMatch ? null : EXEC_RE.exec(executor);
  if (!execMatch && !roleMatch) problems.push("Identity 的 executor 应写成 `provider/model · thinking <级别>`");
  const goal = pySplitlines(pyStrip(mdSection(md, "Goal") ?? ""));
  const derivedTitle = title || (goal.filter((line) => pyStrip(line)).map((line) => pyStrip(stripChars(line, "-* ")))[0] ?? "");
  if (!derivedTitle) problems.push("没有标题：请用 --title 指定，或在 Goal 第一行写一句话概括");
  const [checks, checkProblems] = mdCommandItems(md, "Validation commands");
  const [setup, setupProblems] = mdCommandItems(md, "Setup");
  problems.push(...checkProblems, ...setupProblems);
  const dod: PyDict[] = [];
  for (const line of pySplitlines(mdSection(md, "Definition of done") ?? "")) {
    const match = DOD_LINE_RE.exec(line);
    if (!match) continue;
    let body = match[2] as string;
    let intent: string | null = null;
    const intentMatch = INTENT_RE.exec(body);
    if (intentMatch) {
      intent = stripChars(pyStrip(intentMatch[1] as string), "。．. ", false, true);
      body = pyStrip(body.slice(0, intentMatch.index) + body.slice(intentMatch.index + intentMatch[0].length));
    }
    const labelled = [...body.matchAll(EVIDENCE_LABELLED_RE)];
    const separator = labelled.length ? (labelled[labelled.length - 1] as RegExpMatchArray) : EVIDENCE_LOOSE_RE.exec(body);
    let text: string;
    let evidenceText: string;
    if (separator) {
      const at = separator.index as number;
      text = body.slice(0, at);
      evidenceText = body.slice(at + separator[0].length);
    } else {
      const at = body.indexOf("证据");
      text = at < 0 ? body : body.slice(0, at);
      evidenceText = at < 0 ? "" : body.slice(at + "证据".length);
    }
    const evidence: string[] = [];
    for (const ref of evidenceText.matchAll(EVIDENCE_REF_RE)) if (!evidence.includes(ref[1] as string)) evidence.push(ref[1] as string);
    const item: PyDict = new Map<string, PyValue>([["id", match[1] as string], ["text", stripChars(text, "；;，, ", false, true)], ["evidence", evidence]]);
    if (intent) item.set("intent", intent);
    dod.push(item);
  }
  const scope = mdScopeLists(md);
  const budget = mdBudget(md);
  for (const key of BUDGET_KEYS) if (!budget.has(key)) problems.push(`Budget 缺少 ${key}`);
  const planVersion = identity.get("plan_version") ?? "";
  const role = roleMatch ? (roleMatch[1] as string) : null;
  const executorSpec: PyDict = role
    ? new Map<string, PyValue>([["role", role], ["tools", [...DEFAULT_TOOLS]], ["context_files", "project"]])
    : new Map<string, PyValue>([
        ["provider", execMatch ? (execMatch[1] as string) : null],
        ["model", execMatch ? (execMatch[2] as string) : null],
        ["thinking", execMatch ? (execMatch[3] as string) : DEFAULT_THINKING],
        ["tools", [...DEFAULT_TOOLS]],
        ["context_files", "project"],
      ]);
  const budgetSpec: PyDict = new Map<string, PyValue>([...budget].map(([key, value]) => [key, firstInt(value)]));
  budgetSpec.set("cost_budget", null);
  const contract: PyDict = new Map<string, PyValue>([
    ["schema_version", 1n],
    ["task_id", taskMatch ? (taskMatch[1] as string) : null],
    ["plan_version", isDigits(planVersion) ? firstInt(planVersion) : null],
    ["title", codePoints(derivedTitle).slice(0, 120).join("")],
    ["repository", identity.get("repository") ?? null],
    ["base_sha", identity.get("base_sha") ?? null],
    ["risk_level", identity.get("risk_level") ?? null],
    ["authorization", new Map<string, PyValue>([["executor", mdActionList(identity.get("authorized_actions"))], ["integration", mdActionList(identity.get("integration_actions"))]])],
    ["executor", executorSpec],
    ["scope", new Map<string, PyValue>([
      ["allowed_modified_files", scope.get("allowed_modified_files") ?? []],
      ["allowed_new_files", scope.get("allowed_new_files") ?? []],
      ["allowed_deleted_files", scope.get("allowed_deleted_files") ?? []],
      ["forbidden_paths", scope.get("forbidden_paths") ?? []],
      ["dependency_changes", scope.has("dependency_changes") ? (scope.get("dependency_changes") as PyValue) : "forbidden"],
    ])],
    ["setup", setup],
    ["checks", checks],
    ["definition_of_done", dod],
    ["budget", budgetSpec],
  ]);
  return [contract, problems];
}

// --- 校验 ------------------------------------------------------------------------------------------

/** normalize_contract：补齐可选字段的缺省值，返回新字典；类型错误的字段原样保留，交给校验报告。 */
export function normalizeContract(raw: PyDict): PyDict {
  const contract = loads(dumps(raw)) as PyDict;
  const defaults: [string, [string, PyValue][]][] = [
    ["executor", [["thinking", DEFAULT_THINKING], ["tools", [...DEFAULT_TOOLS]], ["context_files", "project"]]],
    ["scope", [["allowed_modified_files", []], ["allowed_new_files", []], ["allowed_deleted_files", []], ["forbidden_paths", []], ["dependency_changes", "forbidden"]]],
    ["authorization", [["executor", ["local_edit", "local_test"]], ["integration", []]]],
    ["budget", [["max_attempts_total", 2n], ["max_wall_seconds_per_attempt", 1200n], ["max_wall_seconds_total", 2400n], ["cost_budget", null]]],
  ];
  for (const [section, values] of defaults) {
    if (!contract.has(section)) contract.set(section, new Map());
    const target = contract.get(section);
    if (isDict(target)) for (const [key, value] of values) if (!target.has(key)) target.set(key, value);
  }
  for (const section of ["setup", "checks", "definition_of_done"]) if (!contract.has(section)) contract.set(section, []);
  for (const [section, values] of [
    ["checks", [["cwd", "."], ["required", true], ["expected_exit_code", 0n]]],
    ["setup", [["cwd", "."], ["expected_exit_code", 0n]]],
  ] as [string, [string, PyValue][]][]) {
    const list = contract.get(section);
    if (!Array.isArray(list)) continue;
    for (const item of list) if (isDict(item)) for (const [key, value] of values) if (!item.has(key)) item.set(key, value);
  }
  return contract;
}

/** _validate_command：setup、checks 的一项。 */
function validateCommand(item: PyValue, group: string, seen: Map<string, string>, errors: string[]): void {
  const where = `${group} 项`;
  if (!isDict(item)) {
    errors.push(`${where} 必须是对象`);
    return;
  }
  let cid: string;
  const rawId = get(item, "id");
  if (typeof rawId !== "string" || !ITEM_ID_RE.test(rawId)) {
    errors.push(`${where} 的 id 不合法：${pyReprValue(rawId)}（例如 V01、S01）`);
    cid = pyStrValue(rawId);
  } else {
    cid = rawId;
    if (seen.has(cid)) errors.push(`id 重复：${cid}`);
  }
  seen.set(cid, group);
  const argv = get(item, "argv");
  if (!Array.isArray(argv) || !argv.length || !argv.every((part) => typeof part === "string" && part)) errors.push(`${cid} argv 必须是非空字符串数组`);
  else if ((argv as string[]).some((part) => part.includes(String.fromCharCode(0)))) errors.push(`${cid} argv 含 NUL 字符`);
  const cwd = get(item, "cwd", ".");
  if (cwd !== "." && patternError(cwd)) errors.push(`${cid} cwd 不合法：${patternError(cwd) as string}`);
  const timeout = get(item, "timeout_seconds");
  if (!isInt(timeout) || timeout < 1n || timeout > 86400n) errors.push(`${cid} timeout_seconds 必须是 1..86400 的整数`);
  if (!isIntOrBool(get(item, "expected_exit_code", 0n))) errors.push(`${cid} expected_exit_code 必须是整数`);
  if (group === "checks" && typeof get(item, "required", true) !== "boolean") errors.push(`${cid} required 必须是布尔值`);
  if (group === "checks" && !["any", "fail", "pass"].some((value) => pyEq(value, get(item, "expect_on_base", "any")))) {
    errors.push(`${cid} expect_on_base 只能是 fail、pass 或 any`);
  }
  for (const key of ["output_must_match", "output_must_not_match"]) {
    const patterns = get(item, key, []);
    if (!isStrList(patterns)) {
      errors.push(`${cid} ${key} 必须是字符串数组`);
      continue;
    }
    for (const pattern of patterns) {
      try {
        compilePattern(pattern);
      } catch (error) {
        if (!(error instanceof PyReError)) throw error;
        errors.push(`${cid} ${key} 正则无效：${error.message}`);
      }
    }
  }
  // 同一条正则既要匹配又不许出现：任何输出都过不了（第 76 轮）。只比字面相同
  const must = get(item, "output_must_match", []);
  const mustNot = get(item, "output_must_not_match", []);
  if (Array.isArray(must) && Array.isArray(mustNot)) {
    const left = new Set(must.filter((pattern): pattern is string => typeof pattern === "string"));
    const both = [...new Set(mustNot.filter((pattern): pattern is string => typeof pattern === "string" && left.has(pattern)))].sort(cmpCodePoints);
    for (const pattern of both) errors.push(`${cid} 同一条正则既在 output_must_match 又在 output_must_not_match 里，任何输出都过不了：${pattern}`);
  }
  const env = get(item, "env", new Map());
  if (!isDict(env) || ![...env].every(([key, value]) => typeof key === "string" && ENV_NAME_RE.test(key) && typeof value === "string")) {
    errors.push(`${cid} env 必须是 {变量名: 字符串}`);
  }
}

/** _argv_in_line：argv 的各个参数按顺序出现在同一行；程序名只比较文件名主干（忽略目录与扩展名）。 */
export function argvInLine(argv: readonly string[], line: string): boolean {
  const parts = (argv[0] as string).split(/[\\/]/u);
  const program = (parts[parts.length - 1] as string).replace(pyRegex(`\\.(?:${ci("exe")}|${ci("cmd")}|${ci("bat")})${PY_END}`, true), "");
  const lineChars = codePoints(line);
  let position = findCodePoints(codePoints(pyLower(line)), codePoints(pyLower(program)), 0);
  if (position < 0) return false;
  position += codePoints(program).length;
  for (const token of argv.slice(1)) {
    const found = findCodePoints(lineChars, codePoints(token), position);
    if (found < 0) return false;
    position = found + codePoints(token).length;
  }
  return true;
}

/** str.find(sub, start) 按码点。 */
function findCodePoints(hay: readonly string[], needle: readonly string[], start: number): number {
  if (start > hay.length) return -1;
  outer: for (let at = start; at + needle.length <= hay.length; at += 1) {
    for (let index = 0; index < needle.length; index += 1) if (hay[at + index] !== needle[index]) continue outer;
    return at;
  }
  return -1;
}

export type ValidateResult = [PyDict | null, string[], string[]];

/** validate_contract：结构异常（Python 的 TypeError、AttributeError、ValueError、KeyError）一律按合同错误报告。 */
export function validateContract(mdText: string, raw: PyValue, planKey: string, extraProtected: readonly string[] = []): ValidateResult {
  try {
    return checkContract(mdText, raw, planKey, extraProtected);
  } catch (error) {
    if (error instanceof PyValueError) return [null, [`合同结构无效：ValueError: ${error.message}`], []];
    if (error instanceof PyCrash && ["TypeError", "AttributeError", "ValueError", "KeyError"].includes(error.kind)) {
      return [null, [`合同结构无效：${error.kind}: ${error.message}`], []];
    }
    throw error;
  }
}

const TITLE_RE = pyRegex(`${LINE_START}#${S}+TASK:${S}*${BT}?([a-z0-9-]+)`);
const DEPENDENCY_LINE_RE = pyRegex(`dependency_changes${S}*:${S}*${BT}?([a-z]+)`);
const EXPECTATION_LABELS: Record<string, string> = { fail: "基线应失败", pass: "基线应通过", any: "未标注" };

function checkContract(mdText: string, raw: PyValue, planKey: string, extraProtected: readonly string[]): ValidateResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const keyMatch = PLAN_KEY_RE.exec(planKey);
  if (!keyMatch) return [null, [`计划标识不合法：${planKey}（格式 task-id.vN）`], warnings];
  if (!isDict(raw)) return [null, ["机器合同顶层必须是 JSON 对象"], warnings];
  const taskId = (keyMatch.groups as Record<string, string>)["task"] as string;
  const version = BigInt((keyMatch.groups as Record<string, string>)["ver"] as string);
  const contract = normalizeContract(raw);
  for (const section of ["executor", "scope", "authorization", "budget"]) if (!isDict(contract.get(section))) errors.push(`${section} 必须是对象`);
  for (const section of ["setup", "checks", "definition_of_done"]) if (!Array.isArray(contract.get(section))) errors.push(`${section} 必须是数组`);
  if (errors.length) return [null, errors, warnings];
  if (!pyEq(get(contract, "schema_version"), CONTRACT_SCHEMA_VERSION)) errors.push(`schema_version 必须为 ${CONTRACT_SCHEMA_VERSION}`);
  if (!pyEq(get(contract, "task_id"), taskId)) errors.push(`task_id 应为 ${taskId}，实际为 ${pyReprValue(get(contract, "task_id"))}`);
  if (!pyEq(get(contract, "plan_version"), version)) errors.push(`plan_version 应为 ${version}，实际为 ${pyReprValue(get(contract, "plan_version"))}`);
  const base = get(contract, "base_sha");
  if (typeof base !== "string" || !SHA_RE.test(base)) errors.push("base_sha 必须是完整的 40/64 位小写提交 ID");
  if (!RISK_LEVELS.some((level) => pyEq(level, get(contract, "risk_level")))) errors.push(`risk_level 必须是 ${RISK_LEVELS.join("/")} 之一`);

  const authorization = contract.get("authorization") as PyDict;
  let executorActions: string[] | null = null;
  const rawExecutorActions = get(authorization, "executor");
  if (!isStrList(rawExecutorActions) || !rawExecutorActions.every((action) => EXECUTOR_ACTIONS.includes(action))) {
    errors.push(`authorization.executor 只能包含：${EXECUTOR_ACTIONS.join(", ")}`);
  } else {
    executorActions = rawExecutorActions;
    if (!executorActions.includes("local_edit")) errors.push("authorization.executor 必须包含 local_edit");
  }
  let integration: string[] | null = null;
  const rawIntegration = get(authorization, "integration");
  if (!isStrList(rawIntegration) || !rawIntegration.every((action) => INTEGRATION_ACTIONS.includes(action))) {
    errors.push(`authorization.integration 只能包含：${INTEGRATION_ACTIONS.join(", ")}`);
  } else integration = rawIntegration;

  const executor = contract.get("executor") as PyDict;
  // 按角色写：只看 raw 合同——normalize 会补 thinking=high，不能拿它判断“混用”
  const rawExecutor: PyDict = isDict(raw.get("executor")) ? (raw.get("executor") as PyDict) : new Map();
  const roleBound = executorClass(rawExecutor) === "role";
  if (roleBound) {
    const role = rawExecutor.get("role");
    if (typeof role !== "string" || !EXECUTOR_ROLES.includes(role)) errors.push(`executor.role 只能是 ${EXECUTOR_ROLES.join("、")} 之一`);
    const mixed = ["provider", "model", "thinking"].filter((field) => rawExecutor.has(field));
    if (mixed.length) errors.push(`executor.role 不能与 ${mixed.join("、")} 同时写：按角色写时执行模型来自角色绑定`);
    if (pyEq(get(raw, "contract_family"), "planner-v2")) errors.push("planner-v2 合同不支持按角色写 executor");
  }
  for (const field of ["provider", "model"]) {
    const value = get(executor, field);
    if (value !== null && (typeof value !== "string" || !MODEL_TOKEN_RE.test(value))) errors.push(`executor.${field} 不合法：${pyReprValue(value)}`);
  }
  const thinking = get(executor, "thinking");
  if (typeof thinking !== "string" || !FALLBACK_THINKING_LEVELS.includes(thinking)) errors.push(`executor.thinking 必须是 ${FALLBACK_THINKING_LEVELS.join(", ")} 之一`);
  const tools = get(executor, "tools");
  if (!isStrList(tools) || !tools.length || !tools.every((tool) => KNOWN_TOOLS.includes(tool))) {
    errors.push(`executor.tools 必须是非空字符串数组，且只含：${KNOWN_TOOLS.join(", ")}`);
  } else if (executorActions && executorActions.includes("local_test") && !tools.some((tool) => tool === "bash" || tool === "powershell")) {
    warnings.push("授权了 local_test 但工具集没有 bash/powershell：执行器无法自检，检查将只由验收端运行");
  }
  if (!["project", "none"].some((value) => pyEq(value, get(executor, "context_files")))) errors.push("executor.context_files 必须是 project 或 none");

  const scope = contract.get("scope") as PyDict;
  const protectedPatterns = compilePatterns([...PROTECTED_PATTERNS, ...extraProtected], true);
  const allAllowed: string[] = [];
  const forbiddenList: string[] = [];
  for (const field of ["allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"]) {
    const values = get(scope, field);
    if (!Array.isArray(values)) {
      errors.push(`scope.${field} 必须是数组`);
      continue;
    }
    for (const pattern of values) {
      const problem = patternError(pattern);
      if (problem) errors.push(`scope.${field} 中的 ${pyReprValue(pattern)} ${problem}`);
      else if (field === "forbidden_paths") forbiddenList.push(pattern as string);
      else {
        allAllowed.push(pattern as string);
        if (matches(protectedPatterns, pattern as string)) errors.push(`scope.${field} 包含受保护路径 ${pattern as string}（合同、代理规则与调度器不得委派修改）`);
      }
    }
  }
  if (!pyTruthy(get(scope, "allowed_modified_files")) && !pyTruthy(get(scope, "allowed_new_files"))) errors.push("scope 至少要允许修改或新增一个文件");
  const forbidden = compilePatterns(forbiddenList);
  for (const pattern of allAllowed) if (!pattern.includes("*") && matches(forbidden, pattern)) errors.push(`路径 ${pattern} 同时出现在允许集合与 forbidden_paths`);
  if (!["forbidden", "allowed"].some((value) => pyEq(value, get(scope, "dependency_changes")))) errors.push("scope.dependency_changes 必须是 forbidden 或 allowed");

  const seen = new Map<string, string>();
  for (const group of ["setup", "checks"]) for (const item of contract.get(group) as PyValue[]) validateCommand(item, group, seen, errors);
  const checks = (contract.get("checks") as PyValue[]).filter((check): check is PyDict => isDict(check) && typeof check.get("id") === "string");
  if (!checks.some((check) => get(check, "required", true) === true)) errors.push("至少需要一个 required 为 true 的检查：没有可独立运行的检查，验收门禁无法通过");
  const checkIds = new Set(checks.map((check) => check.get("id") as string));
  const dod = contract.get("definition_of_done") as PyValue[];
  const referenced = new Set<string>();
  const dodIds: string[] = [];
  if (!dod.length) errors.push("definition_of_done 必须是非空数组");
  for (const item of dod) {
    if (!isDict(item)) {
      errors.push("definition_of_done 项必须是对象");
      continue;
    }
    const rawDid = get(item, "id");
    let did: string;
    if (typeof rawDid !== "string" || !ITEM_ID_RE.test(rawDid) || dodIds.includes(rawDid) || checkIds.has(rawDid)) {
      errors.push(`DoD id 不合法或重复：${pyReprValue(rawDid)}`);
      did = pyStrValue(rawDid);
    } else did = rawDid;
    dodIds.push(did);
    if (typeof get(item, "text") !== "string" || !get(item, "text")) errors.push(`${did} 缺少 text`);
    if (item.has("intent")) {
      const intent = item.get("intent") as PyValue;
      if (typeof intent !== "string" || !pyStrip(intent)) errors.push(`${did} 的 intent（目的）必须是非空字符串`);
    }
    const evidence = get(item, "evidence");
    if (!isStrList(evidence) || !evidence.length) {
      errors.push(`${did} 的 evidence 必须是非空字符串数组（检查 id、scope 或 review）`);
      continue;
    }
    for (const ref of evidence) {
      if (checkIds.has(ref)) referenced.add(ref);
      else if (!EVIDENCE_TOKENS.includes(ref)) errors.push(`${did} 的证据 ${pyReprValue(ref)} 不是已定义的检查 id，也不是 scope/review`);
    }
  }
  for (const check of checks) {
    const id = check.get("id") as string;
    if (pyTruthy(get(check, "required", true)) && !referenced.has(id)) warnings.push(`必要检查 ${id} 没有被任何 DoD 引用`);
  }

  const budget = contract.get("budget") as PyDict;
  const attempts = get(budget, "max_attempts_total");
  let perAttempt: PyValue = get(budget, "max_wall_seconds_per_attempt");
  const total = get(budget, "max_wall_seconds_total");
  if (!isInt(attempts) || attempts < 1n || attempts > 20n) errors.push("budget.max_attempts_total 必须是 1..20 的整数");
  if (!isInt(perAttempt) || perAttempt < 60n || perAttempt > 86400n) {
    errors.push("budget.max_wall_seconds_per_attempt 必须是 60..86400 的整数");
    perAttempt = null;
  }
  if (!isInt(total) || (perAttempt !== null && total < (perAttempt as bigint))) errors.push("budget.max_wall_seconds_total 必须是整数且不小于单轮上限");
  const cost = get(budget, "cost_budget");
  if (cost !== null) {
    const amount = isDict(cost) ? get(cost, "amount") : null;
    const amountOk = (typeof amount === "bigint" && amount >= 0n) || (typeof amount === "number" && amount >= 0);
    if (!(isDict(cost) && amountOk && typeof get(cost, "currency") === "string")) errors.push("budget.cost_budget 必须为 null 或 {amount, currency}");
  }

  // ---- Markdown 与 JSON：Pi 读 Markdown，调度器执行 JSON，与执行相关的内容必须一致 ----
  const rawText = dumps(raw, { ensureAscii: false });
  if (PLACEHOLDER_RE.test(mdText)) errors.push("Markdown 合同仍包含占位符（【待填…】或 REPLACE_WITH…）");
  if (PLACEHOLDER_RE.test(rawText)) errors.push("JSON 合同仍包含占位符（【待填…】或 REPLACE_WITH…）");
  for (const section of REQUIRED_MD_SECTIONS) if (mdSection(mdText, section) === null) errors.push(`Markdown 缺少章节：## ${section}`);
  const title = TITLE_RE.exec(mdText);
  if (!title || title[1] !== taskId) errors.push(`Markdown 标题应为 '# TASK: ${taskId}'`);
  const identity = mdIdentity(mdText);
  for (const [field, expected] of [["plan_version", String(version)], ["base_sha", base], ["risk_level", get(contract, "risk_level")]] as [string, PyValue][]) {
    const declared = identity.get(field) ?? null;
    if (!pyEq(declared, expected)) errors.push(`Markdown Identity 的 ${field}（${pyReprValue(declared)}）与 JSON（${pyReprValue(expected)}）不一致`);
  }
  for (const [field, expectedList] of [["authorized_actions", executorActions], ["integration_actions", integration]] as [string, string[] | null][]) {
    const declared = mdActionSet(identity.get(field));
    if (declared === null) errors.push(`Markdown Identity 缺少 ${field}`);
    else if (expectedList !== null && !sameSet(declared, new Set(expectedList))) {
      errors.push(`Markdown Identity 的 ${field}（${[...declared].sort(cmpCodePoints).join(", ") || "none"}）与 JSON（${[...expectedList].sort(cmpCodePoints).join(", ") || "none"}）不一致`);
    }
  }
  const provider = get(executor, "provider");
  const model = get(executor, "model");
  const declaredExecutor = identity.get("executor") ?? "";
  const declaredRole = ROLE_EXECUTOR_RE.exec(pyStrip(declaredExecutor));
  if (roleBound || declaredRole) {
    if (!(roleBound && declaredRole && pyEq(declaredRole[1] as string, get(rawExecutor, "role")))) {
      errors.push(
        "Markdown Identity 的 executor 与 JSON 的 executor.role 不一致：按角色写时两边都写，Markdown 为 `- executor: role:<角色>`，JSON 为 {\"role\": \"<角色>\"}",
      );
    }
  } else {
    if (pyTruthy(provider) && pyTruthy(model) && !declaredExecutor.includes(`${pyStrValue(provider)}/${pyStrValue(model)}`)) {
      errors.push(`Markdown Identity 的 executor 应写明 ${pyStrValue(provider)}/${pyStrValue(model)}`);
    }
    if (typeof thinking === "string" && !pyRegex(`thinking${S}+${literal(thinking)}${WB}`).test(declaredExecutor)) {
      errors.push(`Markdown Identity 的 executor 应写明 thinking ${thinking}`);
    }
  }
  for (const pattern of [...allAllowed, ...forbiddenList]) if (!mdText.includes(pattern)) errors.push(`Markdown 未列出 JSON 中的路径：${pattern}`);
  const dependencyLine = DEPENDENCY_LINE_RE.exec(mdSection(mdText, "Scope") ?? "");
  if (!dependencyLine || !pyEq(dependencyLine[1] as string, get(scope, "dependency_changes"))) {
    errors.push(`Markdown Scope 的 dependency_changes 与 JSON（${pyStrValue(get(scope, "dependency_changes"))}）不一致`);
  }
  const mdBudgetValues = mdBudget(mdText);
  for (const [key, value] of [["max_attempts_total", attempts], ["max_wall_seconds_per_attempt", perAttempt], ["max_wall_seconds_total", total]] as [string, PyValue][]) {
    const declared = mdBudgetValues.get(key) ?? null;
    if (declared !== pyStrValue(value)) errors.push(`Markdown Budget 的 ${key}（${pyStrValue(declared)}）与 JSON（${pyStrValue(value)}）不一致`);
  }
  // 时间分配合计超过单轮上限的 70% 时警告（2.5.0）
  const allocation = mdTimeAllocationMinutes(mdText);
  if (perAttempt !== null && pyTruthy(perAttempt) && allocation !== null && Number(allocation * 60n) > Number(perAttempt as bigint) * 0.7) {
    warnings.push(
      `Budget 的时间分配合计 ${allocation} 分钟，是单轮上限 ${perAttempt as bigint} 秒的 ${(allocation * 60n * 100n) / (perAttempt as bigint)}%：超过 70% 时执行器没有余量写报告；` +
        "压缩清单或提高 max_wall_seconds_per_attempt",
    );
  }
  const validation = mdSection(mdText, "Validation commands") ?? "";
  const validationLines = pySplitlines(validation);
  for (const check of checks) {
    const id = check.get("id") as string;
    const idRe = pyRegex(`${WB}${literal(id)}${WB}`);
    const lines = validationLines.filter((line) => idRe.test(line));
    const argv = get(check, "argv");
    if (!lines.length) errors.push(`Markdown Validation commands 未列出 ${id}`);
    else if (isStrList(argv) && argv.length && !lines.some((line) => argvInLine(argv, line))) errors.push(`Markdown 中 ${id} 的命令与 JSON argv 不一致：${argv.join(" ")}`);
  }
  // 基线期望（2.4.0）：Markdown 写了而 JSON 不同是错误；只有 JSON 写了是警告
  const declaredExpectations = mdCheckBaseExpectations(validation);
  for (const check of checks) {
    const id = check.get("id") as string;
    const declared = declaredExpectations.get(id);
    const expected = get(check, "expect_on_base", "any");
    if (!declared) continue;
    // expected not in labels：列表、对象不可哈希，Python 在这里抛 TypeError（由 validate_contract 报成合同结构无效）
    if (Array.isArray(expected) || isDict(expected)) throw new PyCrash("TypeError", `unhashable type: '${Array.isArray(expected) ? "list" : "dict"}'`);
    if (typeof expected !== "string" || !Object.hasOwn(EXPECTATION_LABELS, expected)) continue;
    if (new Set(declared).size > 1) {
      errors.push(`Markdown 中 ${id} 的检查行对基线期望说法不一：${declared.map((value) => EXPECTATION_LABELS[value]).join("、")}`);
    } else if (declared[0] !== "any" && declared[0] !== expected) {
      errors.push(
        `Markdown 中 ${id} 的基线期望（${EXPECTATION_LABELS[declared[0] as string]}）与 JSON 的 expect_on_base（${expected}）不一致；改了 Markdown 的标注时，` +
          "用 derive-json --force 重新生成 JSON，或手工同步",
      );
    } else if (declared[0] !== expected) {
      warnings.push(
        `JSON 中 ${id} 的 expect_on_base 是 ${expected}，Markdown 的检查行没有写“${EXPECTATION_LABELS[expected]}”：baseline 照常核对，` +
          "但执行器读 plan.md 看不到；按约定两处都写",
      );
    }
  }
  for (const itemId of dodIds) if (!pyRegex(`${WB}${literal(itemId)}${WB}`).test(mdText)) errors.push(`Markdown 未出现 JSON 中的编号：${itemId}`);
  return [errors.length ? null : contract, errors, warnings];
}

const sameSet = (a: Set<string>, b: Set<string>): boolean => a.size === b.size && [...a].every((item) => b.has(item));

/** invisible_char_warnings：合同中的不可见格式字符（Unicode 类别 Cf）。 */
export function invisibleCharWarnings(text: string, label: string, limit = 5): string[] {
  const found: string[] = [];
  pySplitlines(text).some((line, index) => {
    const chars = [...new Set(codePoints(line).filter(isCf))].sort(cmpCodePoints);
    if (chars.length) {
      const codes = chars.map((char) => `U+${(char.codePointAt(0) as number).toString(16).toUpperCase().padStart(4, "0")}`).join("、");
      found.push(`${label} 第 ${index + 1} 行含不可见格式字符 ${codes}：如果本意是写转义序列，请改回转义文本（或在探针里用 chr()）`);
    }
    return found.length >= limit;
  });
  return found;
}

/** require_authorized_action 的判定部分（报错由调用方抛 DispatchError）。 */
export function authorizationProblem(contract: PyValue, action: string, integration = false): string | null {
  const section = integration ? "integration" : "executor";
  const authorization = isDict(contract) ? contract.get("authorization") : undefined;
  const actions = isDict(authorization) ? authorization.get(section) : undefined;
  if (!isStrList(actions)) return `合同授权无效：authorization.${section} 必须是字符串数组`;
  if (!actions.includes(action)) return `合同未授权动作：authorization.${section} 缺少 ${action}`;
  return null;
}

