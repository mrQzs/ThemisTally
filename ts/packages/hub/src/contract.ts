// 合同与战前门禁（迁移第 ⑤e 片）。⑤e1a 是纯文字的部分：kit_hub.py 的 tail、tail_file、normalize_identity、normalize_markup、
// strip_decisions、decisions_section、unparsed_check_ids、external_fact_problems、unverified_facts、pytest_outcomes（⑤f 的，
// hollow_baseline_problems 要用，提前移植）。文字逐字节照 Python；参数照 Python 收原值，类型不对时照它的异常类型抛。
import { closeSync, fstatSync, openSync, readSync } from "node:fs";
import { PyOSError, pyDecodeUtf8Replace, pyOSErrorOf, pyReadTextReplace } from "@themis/base/pyio";
import { PyCrash, pyGet, pyItem, pyIter, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyValue } from "@themis/base/pyjson";
import { D, S, W, pyIntParse, pyRegex, pyRstrip, pySplitlines, pyStrip } from "@themis/base/pyre";
import { CHECK_LINE_RE, mdSection } from "@themis/dispatcher/contract";

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

