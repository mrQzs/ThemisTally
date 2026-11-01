// 合同与战前门禁（迁移第 ⑤e 片）。⑤e1a 是纯文字的部分：kit_hub.py 的 tail、tail_file、normalize_identity、normalize_markup、
// strip_decisions、decisions_section、unparsed_check_ids、external_fact_problems、unverified_facts、pytest_outcomes（⑤f 的，
// hollow_baseline_problems 要用，提前移植）。文字逐字节照 Python；参数照 Python 收原值，类型不对时照它的异常类型抛。
import { createHash } from "node:crypto";
import { closeSync, fstatSync, openSync, readFileSync, readSync, statSync } from "node:fs";
import { readText } from "@themis/base/fsutil";
import { PyOSError, pyDecodeUtf8Replace, pyOSErrorOf, pyReadTextReplace } from "@themis/base/pyio";
import { PyCrash, pyFloatOf, pyGet, pyIntOf, pyItem, pyIter, pyPercentD, pyPlus, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { purePathParent, purePathStr } from "@themis/base/pypath";
import { D, S, W, cmpCodePoints, pyIntParse, pyRegex, pyRstrip, pySplitlines, pyStrip } from "@themis/base/pyre";
import { compilePy } from "@themis/base/pyregex";
import { pyEq } from "@themis/base/pyvalue";
import { CHECK_LINE_RE, mdSection } from "@themis/dispatcher/contract";
import { reEscape } from "@themis/dispatcher/patterns";
import { CONTRACT_EXECUTOR_LINE, EXECUTOR, MIN_ATTEMPTS_LEFT, OWNER } from "./constants.ts";
import { HubError } from "./errors.ts";
import { git } from "./kernel.ts";
import { parseLetter } from "./letters.ts";
import type { Hub } from "./mailbox.ts";
import { budgetUsage, regressionGates } from "./prompt.ts";
import { gateFile, gatePattern } from "./taskstate.ts";

const LF = String.fromCharCode(10);
const TAB = String.fromCharCode(9);
const BT = String.fromCharCode(96);
/** re.M 的 ^ 只认换行符之后（JS 的 m 标志还认回车、U+2028、U+2029），所以不用 m 标志，写成“前面不是别的字符”。 */
const LINE_START = `(?<![^${LF}])`;
/** re.M 的 $：换行符之前或结尾。 */
const LINE_END = `(?=${LF}|$)`;
const or = (value: PyValue | undefined, fallback: PyValue): PyValue => (pyTruthy(value) ? (value as PyValue) : fallback);

function text(value: PyValue | undefined, what: string): string {
  if (typeof value === "string") return value;
  throw new PyCrash(what === "re" ? "TypeError" : "AttributeError",
    what === "re" ? `expected string or bytes-like object, got '${pyTypeName(value)}'` : `'${pyTypeName(value)}' object has no attribute '${what}'`);
}

/** 切片 [-n:] 的起点：n 是 0 时是整份，负数时从头数（Python 的切片语义）。 */
function lastIndex(length: number, lines: PyValue | undefined): number {
  const n = typeof lines === "boolean" ? Number(lines) : typeof lines === "bigint" ? Number(lines) : lines;
  if (typeof n !== "number" || !Number.isInteger(n)) throw new PyCrash("TypeError", "slice indices must be integers or None or have an __index__ method");
  const start = -n;
  return start < 0 ? Math.max(0, length + start) : Math.min(start, length);
}

export function tail(value: PyValue, lines: PyValue = 30n): string {
  const parts = pySplitlines(pyStrip(text(value, "strip")));
  return parts.slice(lastIndex(parts.length, lines)).join(LF);
}

/** 文件末尾几行：只读最后 limit 字节（输出可能很大）。打开出错照 Python 的 open 报 OSError；Node 打得开目录、读出来是空的，Python 报 errno 13。 */
export function tailFile(path: string, lines: PyValue = 30n, limit: number | bigint = 65536n): string {
  let fd: number;
  try {
    fd = openSync(path, "r");
  } catch (error) {
    throw pyOSErrorOf(error, path) ?? error;
  }
  try {
    const info = fstatSync(fd);
    if (info.isDirectory()) throw new PyOSError(13, "Permission denied", path);
    const start = Math.max(0, info.size - Number(limit));
    const buffer = Buffer.alloc(Math.max(0, info.size - start));
    if (buffer.length) readSync(fd, buffer, 0, buffer.length, start);
    return tail(pyDecodeUtf8Replace(buffer), lines);
  } finally {
    closeSync(fd);
  }
}

// --- 合同的规整 ------------------------------------------------------------------------------------------------

/** 合同 Identity 里由内核决定的两项：版本号与基线。 */
export const IDENTITY_FIELD_RES: ReadonlyArray<readonly [string, RegExp]> = [
  ["plan_version", pyRegex(`${LINE_START}(-[ ${TAB}]*plan_version:[ ${TAB}]*${BT}?)(${D}+)`)],
  ["base_sha", pyRegex(`${LINE_START}(-[ ${TAB}]*base_sha:[ ${TAB}]*${BT}?)([0-9a-f]{7,40})`)],
];

/**
 * 把 Identity 里的版本号与基线写成内核决定的值；交回（改正后的全文，改了的字段 → 合同端原来写的）。
 * Python 用 sub 的模板（第 1 组加值）拼：值里有反斜杠时会被当成转义，内核给的版本号与基线没有反斜杠，这里直接拼。
 */
export function normalizeIdentity(value: PyValue, values: PyValue): [string, PyDict] {
  let out = text(value, "re");
  const changed: PyDict = new Map();
  for (const [field, pattern] of IDENTITY_FIELD_RES) {
    const match = pattern.exec(out);
    if (match === null) continue;
    const wanted = pyItem(values, field);
    if (match[2] === wanted) continue;
    changed.set(field, match[2] as string);
    out = out.slice(0, match.index) + (match[1] as string) + pyStrValue(wanted) + out.slice(match.index + match[0].length);
  }
  return [out, changed];
}

/** Scope 一节的标题行与正文（re.M | re.S：正文到下一个 ## 或文末）。 */
export const SCOPE_SECTION_RE = pyRegex(`(${LINE_START}##[ ${TAB}]+Scope[ ${TAB}]*)${LINE_END}([^]*?)(?=${LINE_START}##[ ${TAB}]|$)`);
/** Scope 列表项末尾的全角括号说明：`- src/a.ts（说明）（另一句）`。 */
export const SCOPE_NOTE_RE = pyRegex(`${LINE_START}([ ${TAB}]*[-*][ ${TAB}]+(?:(?!${S})[^（])+)[ ${TAB}]*(?:（[^（）${LF}]*）[ ${TAB}]*)+${LINE_END}`, true);
/** 看着像检查行的行：编号、可选的（必要…）、冒号、反引号里的命令。 */
export const CHECK_LIKE_RE = pyRegex(`^[-*]${S}*([A-Za-z](?:${W}|-)*)${S}*(?:（[^）]*）|[(][^)]*[)])?${S}*[:：]${S}*${BT}`);
/** DoD 与检查行的编号写成粗体（`- **D01**: …`、`- **V01：**…`）；调度器只认 `- D01：…`。 */
export const BOLD_ITEM_RE = pyRegex(
  `${LINE_START}([ ${TAB}]*[-*][ ${TAB}]*)[*][*]([DV]${D}{2,})(?:[*][*][ ${TAB}]*([:：])|[ ${TAB}]*([:：])[ ${TAB}]*[*][*])[ ${TAB}]*`, true);

/** 把粗体编号改成调度器认得的写法，Scope 列表项末尾的全角括号说明去掉；交回（改正后的全文，改了几处）。 */
export function normalizeMarkup(value: PyValue): [string, bigint] {
  let count = 0;
  let out = text(value, "re").replace(BOLD_ITEM_RE, (_all, lead: string, id: string) => {
    count += 1;
    return `${lead}${id}：`;
  });
  const section = SCOPE_SECTION_RE.exec(out);
  if (section === null) return [out, BigInt(count)];
  const start = section.index + (section[1] as string).length;
  const end = start + (section[2] as string).length;
  const body = (section[2] as string).replace(SCOPE_NOTE_RE, (_all, item: string) => {
    count += 1;
    return item;
  });
  return [out.slice(0, start) + body + out.slice(end), BigInt(count)];
}

// --- 站主决定的原文 --------------------------------------------------------------------------------------------

/** 合同末尾由内核附上的站主决定原文（第 50 轮）。 */
export const DECISIONS_HEADING = "## 站主决定（内核附原文）";
export const DECISIONS_SECTION_RE = pyRegex(`${LINE_START}${DECISIONS_HEADING}[ ${TAB}]*${LINE_END}[^]*?(?=${LINE_START}##[ ${TAB}]|$)`, true);

/** 去掉内核附的站主决定一节：内核的未决标注等检查只看合同端写的正文。 */
export function stripDecisions(value: PyValue): string {
  return text(value, "re").replace(DECISIONS_SECTION_RE, "");
}

/** 站主决定的原文附录：原文逐行引用（`> `），调度器与内核的检查都不会把其中的列表项、标题当成合同条目。 */
export function decisionsSection(decisions: PyValue): string {
  const lines = [DECISIONS_HEADING, "",
    "规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；"
    + "与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。", ""];
  for (const item of pyIter(decisions)) {
    lines.push(`站主来信 ${pyStrValue(pyItem(item, "msg"))}：`, "");
    lines.push(...pySplitlines(pyStrValue(pyItem(item, "text"))).map((line) => pyRstrip(`> ${line}`)), "");
  }
  return `${pyRstrip(lines.join(LF))}${LF}`;
}

// --- 合同里检查行的写法与外部事实 ------------------------------------------------------------------------------------

/** Validation commands 里看着像检查、调度器却认不出的行的编号。 */
export function unparsedCheckIds(md: PyValue): string[] {
  const lines = pySplitlines(mdSection(text(md, "re"), "Validation commands") ?? "");
  return lines.map(pyStrip).filter((line) => CHECK_LIKE_RE.test(line) && !CHECK_LINE_RE.test(line))
    .map((line) => (CHECK_LIKE_RE.exec(line) as RegExpExecArray)[1] as string);
}

/** “没核实”的各种说法：宁可多转给站主，也不放过一条（第 7 轮）。 */
export const UNVERIFIED_RE = pyRegex("(?:未|未能|无法|不能|没|没有)核实");

/** 规划端要交出 external_facts：计划依赖的仓库外事实，每条写出处与核实的命令和结果。 */
export function externalFactProblems(output: PyValue): string[] {
  const facts = pyGet(output, "external_facts");
  if (!Array.isArray(facts)) return ["输出里没有 external_facts（计划依赖的仓库外事实列表，没有就写 []）"];
  const filled = (item: PyDict, key: string): boolean => pyStrip(pyStrValue(or(pyGet(item, key), ""))) !== "";
  const bad = facts.flatMap((item, at) => (!(item instanceof Map) || !filled(item, "fact") || !filled(item, "verified") ? [String(at + 1)] : []));
  if (bad.length) return [`external_facts 第 ${bad.join("、")} 条缺 fact 或 verified（没核实就写“未核实”）`];
  return [];
}

export function unverifiedFacts(facts: PyValue): PyDict[] {
  const out: PyDict[] = [];
  for (const item of pyIter(facts)) {
    if (!UNVERIFIED_RE.test(pyStrValue(pyItem(item, "verified")))) continue;
    out.push(new Map<string, PyValue>([
      ["fact", pyStrip(pyStrValue(pyItem(item, "fact")))], ["source", pyStrip(pyStrValue(or(pyGet(item, "source"), "")))],
    ]));
  }
  return out;
}

// --- pytest 的输出 --------------------------------------------------------------------------------------------

const SUMMARY_INFO_RE = pyRegex("^=+ short test summary info =+$");
export const PYTEST_SUMMARY_RE = pyRegex(`^=*${S}*((?:${D}+ [a-z]+(?:, )?)+) in (?:${D}|[.])+s`);
export const PYTEST_REPORT_RE = pyRegex(`^(FAILED|ERROR) ([^${LF}]+?)(?: - [^${LF}]*)?$`);
const COUNT_NAMES: Record<string, string> = { error: "errors", warning: "warnings" };

/**
 * 读 pytest -q -rfE 的输出：各类结果的计数，以及失败与出错的用例。失败用例只认 short test summary info 之后的行。
 * 照 Python 的文本模式读：UTF-8（坏字节换成 U+FFFD）、通用换行（回车换行与单独的回车都算一行的结尾）。Python 逐行读、不整份读进
 * 内存；这里整份读：读的是一个文件的 pytest -q 输出（门禁的检查日志），不大。
 */
export function pytestOutcomes(logPath: string): [PyDict, string[], string[]] {
  const lines = pyReadTextReplace(logPath).split(LF);
  if (lines.at(-1) === "") lines.pop();
  let counts: PyDict = new Map();
  const failed: string[] = [];
  const errored: string[] = [];
  let inSummary = false;
  for (const line of lines) {
    if (SUMMARY_INFO_RE.test(line)) {
      inSummary = true;
      continue;
    }
    const match = PYTEST_SUMMARY_RE.exec(line);
    if (match) {
      counts = new Map();
      for (const item of (match[1] as string).split(", ")) {
        const at = item.indexOf(" ");
        if (at < 0) throw new PyCrash("ValueError", "not enough values to unpack (expected 2, got 1)");
        const name = item.slice(at + 1);
        counts.set(COUNT_NAMES[name] ?? name, pyIntParse(item.slice(0, at)) as bigint);
      }
      continue;
    }
    const report = inSummary ? PYTEST_REPORT_RE.exec(line) : null;
    if (report) (report[1] === "FAILED" ? failed : errored).push(report[2] as string);
  }
  return [counts, failed, errored];
}

// --- ⑤e1b：要读仓库、账本与信箱的部分 ------------------------------------------------------------------------------

/** item in container：列表比元素、字符串查子串、字典查键；别的照 Python 报 TypeError。 */
function pyIn(item: string, container: PyValue): boolean {
  if (Array.isArray(container)) return container.some((value) => pyEq(value, item));
  if (typeof container === "string") return container.includes(item);
  if (container instanceof Map) return container.has(item);
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(container)}' is not iterable`);
}

/**
 * except ValueError 接得住的：json.loads 的 ValueError 与 JSONDecodeError，以及 read_text 读到不是 UTF-8 的文件时的 UnicodeDecodeError
 * （也是 ValueError 的子类；base 的 fsutil 与 pyio 各有一个，名字相同）。RecursionError 不算。
 */
const isValueError = (error: unknown): boolean =>
  (error instanceof PyJsonError && (error.kind === "ValueError" || error.kind === "JSONDecodeError")) || (error as Error | null)?.name === "UnicodeDecodeError";

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** 合同的 md 与 json：.agent/plans/<键>.md、.json（键照 Python 拼：不是字符串时报 TypeError）。 */
export function contractPaths(hub: Hub, ts: PyValue): [string, string] {
  const key = pyItem(pyItem(ts, "contract"), "key");
  const plans = purePathStr(hub.repo, ".agent", "plans");
  return [purePathStr(plans, pyPlus(key, ".md") as string), purePathStr(plans, pyPlus(key, ".json") as string)];
}

/**
 * Scope 里少了目录前缀的路径（第 46 轮），写成“原文 → 基线上的文件”。只认得出“第一段在仓库根下没有、某个目录下却正好有这个文件”的。
 * 照 Python：git 不加 core.quotepath=off，ls-tree 列出的非 ASCII 路径整条带引号，这样的路径对不上（迁移计划第 10 节）。
 */
export function scopeMissingPrefix(hub: Hub, data: PyValue): string[] {
  const base = pyGet(data, "base_sha");
  if (!pyTruthy(base)) return [];
  if (typeof base !== "string") throw new PyCrash("TypeError", `expected str, bytes or os.PathLike object, not ${pyTypeName(base)}`);
  let files: string[];
  try {
    files = pySplitlines(git(["ls-tree", "-r", "--name-only", base], hub.repo));
  } catch (error) {
    if (error instanceof HubError) return [];
    throw error;
  }
  const roots = new Set(files.map((path) => path.split("/")[0]));
  const scope = or(pyGet(data, "scope"), new Map());
  const out: string[] = [];
  for (const name of ["allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"]) {
    for (const entry of pyIter(or(pyGet(scope, name), [])).map(pyStrValue)) {
      if (!entry.includes("/") || roots.has(entry.split("/")[0]) || [..."*?["].some((char) => entry.includes(char))) continue;
      const found = files.find((path) => path.endsWith(`/${entry}`));
      if (found !== undefined) out.push(`${entry} → ${found}`);
    }
  }
  return out;
}

/** 合同里的未决标注：T001 的合同端把待站主确认的问题写成 13 处标注留在正文里。 */
export const PENDING_MARK_RE = pyRegex("待(?:站主|协调人)?(?:确认|拍板|决定)", true);

/** 内核另外要求的几项：门禁测试路径禁改、门禁检查在基线上失败、回归检查、执行模型与集成授权；合同里不能留未决标注。 */
export function contractRequirements(hub: Hub, ts: PyDict): string[] {
  const [md, js] = contractPaths(hub, ts);
  let data: PyValue;
  try {
    data = loads(readText(js));
  } catch (error) {
    if (isValueError(error)) return ["合同 JSON 读不出来"];
    throw error;
  }
  const problems: string[] = [];
  const written = stripDecisions(readText(md)); // 内核附的站主原文不算合同端写的
  const unparsed = unparsedCheckIds(written);
  if (unparsed.length) {
    problems.push(`Validation commands 里这几行调度器认不出、等于没写：${unparsed.join("、")}。检查编号要是一个大写字母加至少两位数字，例如 G01、R01（DoD 的“证据”里跟着改）`);
  }
  const pending = written.match(PENDING_MARK_RE) ?? [];
  if (pending.length) {
    problems.push(`合同里还有 ${pending.length} 处未决标注（${[...new Set(pending)].sort(cmpCodePoints).join("、")}）：拿不准的事先发“提问”，等站主或协调人答复后再交合同，合同里只写已经定下的做法`);
  }
  const missing = scopeMissingPrefix(hub, data);
  if (missing.length) {
    problems.push(`Scope 的路径要从仓库根写起，这几条少了目录前缀（原文 → 基线上的文件）：${missing.slice(0, 6).join("；")}${missing.length > 6 ? `；另有 ${missing.length - 6} 条` : ""}`);
  }
  if (!pyIn(gatePattern(ts), pyGet(or(pyGet(data, "scope"), new Map()), "forbidden_paths", []))) problems.push(`Scope 的 forbidden_paths 要包含 ${gatePattern(ts)}`);
  const baselineFile = gateFile(ts, "baseline");
  const checks = (): PyValue[] => pyIter(or(pyGet(data, "checks"), []));
  const gateChecks = checks().filter((check) => pyIn(baselineFile, or(pyGet(check, "argv"), [])));
  if (!gateChecks.length) problems.push(`Validation commands 要有一条运行 ${baselineFile} 的必要检查`);
  else if (!gateChecks.some((check) => pyEq(pyGet(check, "expect_on_base"), "fail") && pyTruthy(pyGet(check, "required", true)))) {
    problems.push(`运行 ${baselineFile} 的检查要标“必要”与“基线应失败”`);
  }
  const guarded = regressionGates(hub, ts).filter((path) => !checks().some((check) =>
    pyIn(path, or(pyGet(check, "argv"), [])) && pyEq(pyGet(check, "expect_on_base"), "pass") && pyTruthy(pyGet(check, "required", true))));
  if (guarded.length) problems.push(`Validation commands 要有一条必要、基线应通过的回归检查，跑先前各片的门禁基准测试：${guarded.join("、")}`);
  const executor = or(pyGet(data, "executor"), new Map());
  const declared = [pyGet(executor, "provider"), pyGet(executor, "model"), pyGet(executor, "thinking")];
  if (!declared.every((value, at) => pyEq(value, EXECUTOR[at] as string))) problems.push(`执行模型要写成：${CONTRACT_EXECUTOR_LINE}`);
  const integration = pyIter(or(pyGet(or(pyGet(data, "authorization"), new Map()), "integration"), []));
  const unhashable = integration.find((item) => Array.isArray(item) || item instanceof Map);
  if (unhashable !== undefined) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(unhashable)}'`); // set(...)
  if (!["local_branch", "merge"].every((name) => integration.some((item) => pyEq(item, name)))) problems.push("integration_actions 要写 local_branch, merge");
  return problems;
}

/** 一审报告要有“DoD → 测试 → 断言”映射：合同里每个 DoD 的 id 都要在报告里出现。编号照 re.escape 转义，交给移植的 sre。 */
export function dodCoverageProblems(hub: Hub, ts: PyDict, report: PyValue): string[] {
  let dod: PyValue;
  try {
    dod = or(pyGet(loads(readText(contractPaths(hub, ts)[1])), "definition_of_done"), []);
  } catch (error) {
    if (isValueError(error) || (error instanceof PyCrash && error.kind === "KeyError")) return [];
    throw error;
  }
  const ids = pyIter(dod).filter((item) => item instanceof Map && pyTruthy(pyGet(item, "id"))).map((item) => pyStrValue(pyGet(item, "id")));
  const missing = ids.filter((id) => compilePy(`(?<![A-Za-z0-9])${reEscape(id)}(?![0-9])`).search(text(report, "re")) === null);
  if (missing.length) {
    return [`一审报告的“DoD → 测试 → 断言”映射表漏了 ${missing.join("、")}（每条 DoD 都要写由哪条测试的哪个断言证明，或者写明“只能人工审阅”）`];
  }
  return [];
}

/** T002：v2 照抄 v1 的 2 次，可 v1 已经用掉 1 次，v2 只剩 1 次、失败了就没有返工余量（第 8 轮）。只接 ValueError：contract_paths 的 KeyError 照样往外抛。 */
export function budgetProblems(hub: Hub, ts: PyDict): string[] {
  let budget: PyValue;
  try {
    budget = or(pyGet(loads(readText(contractPaths(hub, ts)[1])), "budget"), new Map());
  } catch (error) {
    if (isValueError(error)) return ["合同 JSON 读不出来"];
    throw error;
  }
  const used = budgetUsage(hub, ts);
  const perAttempt = pyFloatOf(or(pyGet(budget, "max_wall_seconds_per_attempt"), 0n));
  const attemptsLeft = pyIntOf(or(pyGet(budget, "max_attempts_total"), 0n)) - BigInt(used.attempts_started);
  const wallLeft = pyFloatOf(or(pyGet(budget, "max_wall_seconds_total"), 0n)) - used.wall_seconds_used;
  const problems: string[] = [];
  if (attemptsLeft < BigInt(MIN_ATTEMPTS_LEFT)) {
    problems.push(`max_attempts_total=${pyStrValue(pyGet(budget, "max_attempts_total"))}，本任务各版本已用掉 ${used.attempts_started} 次，这一版只剩 ${attemptsLeft} 次：至少留 ${MIN_ATTEMPTS_LEFT} 次`);
  }
  if (wallLeft < MIN_ATTEMPTS_LEFT * perAttempt) {
    problems.push(`max_wall_seconds_total=${pyStrValue(pyGet(budget, "max_wall_seconds_total"))}，已用掉 ${pyPercentD(used.wall_seconds_used)} 秒，`
      + `只剩 ${pyPercentD(wallLeft)} 秒：至少留 ${MIN_ATTEMPTS_LEFT} 次单次时限（${pyPercentD(MIN_ATTEMPTS_LEFT * perAttempt)} 秒）`);
  }
  return problems;
}

/** msg_id 是不是发给站主的“提问”。文件名照 Python 拼（"%s.md"）；msg_id 是假值时两个信箱都不看。 */
export function answersQuestion(hub: Hub, msgId: PyValue): boolean {
  for (const box of ["new", "cur"]) {
    const path = purePathStr(hub.inbox(OWNER, box), `${pyStrValue(msgId)}.md`);
    if (!pyTruthy(msgId) || !isFile(path)) continue;
    try {
      return pyEq(parseLetter(readText(path))[0].get("type") ?? null, "提问");
    } catch (error) {
      if (error instanceof HubError) return false;
      throw error;
    }
  }
  return false;
}

// --- ⑤e2a：合同的哈希与战前门禁的基线核对 ----------------------------------------------------------------------------

/** sha256_file：读不了（不在、是目录）时是 null。 */
function sha256File(path: string): string | null {
  try {
    return createHash("sha256").update(readFileSync(path)).digest("hex");
  } catch {
    return null;
  }
}

/** 合同 md 与 json 的合并哈希：两个文件各自的 sha256（读不了算空串）连起来再取一次。 */
export function contractDigest(hub: Hub, ts: PyValue): string {
  const [md, js] = contractPaths(hub, ts);
  return createHash("sha256").update(Buffer.from((sha256File(md) ?? "") + (sha256File(js) ?? ""), "utf8")).digest("hex");
}

/** baseline 交回的文字里，检查记录那一行（re.M：行尾的空白不算进路径）。 */
export const BASELINE_RECORD_RE = pyRegex(`${LINE_START}基线检查记录：([^${LF}]+?)${S}*${LINE_END}`);

/**
 * 基准测试在基线上要“在断言上失败”（第 14 轮）：baseline 只看退出码是不是 0，超时、pytest 退出码 2–5、用例在 setup 出错都算“在基线上
 * 失败”，测试其实没跑起来。读 baseline 写下的检查记录逐条核对。
 */
export function hollowBaselineProblems(hub: Hub, out: PyValue, expected: PyValue): string[] {
  const match = BASELINE_RECORD_RE.exec(text(out, "re"));
  const recordPath = match ? purePathStr(hub.repo, match[1] as string) : null;
  if (recordPath === null || !isFile(recordPath)) return ["baseline 没有留下检查记录，核对不了基准测试在基线上是怎样失败的"];
  const results = or(pyGet(loads(readText(recordPath) || "{}"), "results"), []);
  // expected in “argv 拼成的文字”：照 Python 的求值次序，先拼文字，再查（expected 不是字符串时这时才报 TypeError）
  const runs = (item: PyValue): boolean => {
    const argv = pyIter(or(pyGet(item, "argv"), [])).map(pyStrValue).join(" ");
    if (typeof expected !== "string") throw new PyCrash("TypeError", `'in <string>' requires string as left operand, not ${pyTypeName(expected)}`);
    return argv.includes(expected);
  };
  const gate = pyIter(results).filter(runs);
  if (!gate.length) return [`baseline 的检查记录里没有跑 ${pyStrValue(expected)} 的检查`];
  const problems: string[] = [];
  for (const item of gate) {
    const name = pyStrValue(or(pyGet(item, "id"), "?"));
    if (pyTruthy(pyGet(item, "timed_out")) || pyTruthy(pyGet(item, "interrupted")) || pyTruthy(pyGet(item, "spawn_error"))) {
      problems.push(`${name} 在基线上超时或没有跑起来：卡住的测试也算“失败”，但什么也没证明`);
      continue;
    }
    if (!pyEq(pyGet(item, "exit_code"), 1n)) {
      problems.push(`${name} 在基线上的 pytest 退出码是 ${pyStrValue(pyGet(item, "exit_code"))}：只有 1 是用例失败（2 中断、3 内部错误、4 用法错误、`
        + "5 没有用例）");
      continue;
    }
    const log = purePathStr(purePathParent(purePathParent(recordPath)), pyStrValue(or(pyGet(item, "log"), "")));
    const counts = isFile(log) ? pytestOutcomes(log)[0] : new Map<string, PyValue>();
    if (pyTruthy(counts.get("errors"))) {
      problems.push(`${name} 在基线上有 ${pyPercentD(counts.get("errors") as PyValue)} 个用例出错（setup 或夹具失败），不是断言失败：夹具在基线上做不成的事，`
        + "把原因记下来，让用例断言它");
    } else if (counts.size && !pyTruthy(counts.get("failed"))) {
      problems.push(`${name} 在基线上没有失败的用例`);
    }
  }
  return problems;
}

