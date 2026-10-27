// pi_dispatch 的 mutate（迁移第 ④b5a 片）：变异清单的读取与校验、只插入代码的提示、--check-anchors 的锚点核对与提示。
// 变异轮次、attempt 与 --tree 的整轮运行在 ④b5b。hub 解析 --check-anchors 的 OK、MISMATCH、MISSING 行，并把提示原样转进信里，
// 所以提示里的“最相近的行”、百分比与第一处不同都照 difflib 逐字。
import { statSync } from "node:fs";
import { PyCrash, type PyOut, pyFixed, pyStrValue, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes, pyReadText } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { isWithin, ntIsabs, purePathStr, pyResolve } from "@themis/base/pypath";
import { PY_END, cmpCodePoints, codePoints, pyStrip } from "@themis/base/pyre";
import { SequenceMatcher } from "@themis/base/pydifflib";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE } from "./repo.ts";

const MUTATION_DEFAULT_TIMEOUT = 600n;
const MUTATION_MAX_COMMANDS = 8;
const MUTATION_COMMAND_ID_PATTERN = "^[A-Za-z][A-Za-z0-9_-]{0,31}$";
const MUTATION_COMMAND_ID_RE = new RegExp(`^[A-Za-z][A-Za-z0-9_-]{0,31}${PY_END}`, "u");
/** --check-anchors 的“最相近”提示：相似度不到这个值的行不列出。 */
const ANCHOR_HINT_MIN_RATIO = 0.6;
/** 字符级提示里，不同之处两边各带多少个字符的上下文。 */
const ANCHOR_DIFF_CONTEXT = 12;
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);
const SEP = process.platform === "win32" ? String.fromCharCode(92) : "/";

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isStr = (value: PyValue | undefined): value is string => typeof value === "string";
/** isinstance(value, int) and not isinstance(value, bool) and value > 0。 */
const positiveInt = (value: PyValue | undefined): boolean => typeof value === "bigint" && value > 0n;

/** 清单校验通过后的一条命令（_commands 的一项）。 */
export interface MutationCommand {
  readonly id: string;
  readonly argv: string[];
  readonly cwd: string;
  readonly timeout_seconds: bigint;
}

export interface MutationSpec {
  readonly raw: PyDict;
  readonly commands: MutationCommand[];
  readonly mutations: PyDict[];
}

/** relative_ok：非空字符串，不是绝对路径，各段里没有 ".."。 */
function relativeOk(value: PyValue | undefined): boolean {
  if (!isStr(value) || !value) return false;
  if (process.platform === "win32" ? ntIsabs(value) : value.startsWith("/")) return false;
  return !purePathStr(value).split(SEP).includes("..");
}

const argvOk = (value: PyValue | undefined): boolean => Array.isArray(value) && value.length > 0 && value.every((item) => isStr(item) && item.length > 0);

/**
 * _load_mutation_spec：读取并校验变异清单，交回（清单, 问题列表）；问题的文字与次序照 Python。shown 是 Python 那边
 * str(Path(spec)) 的写法，只用在“读不了”的报错里。
 */
export function loadMutationSpec(file: string): [MutationSpec | null, string[]] {
  let raw: PyValue;
  try {
    raw = loads(pyReadText(file, purePathStr(file)));
  } catch (error) {
    const reason = readFailure(error);
    if (reason === null) throw error;
    return [null, [`变异清单无法读取或不是合法 JSON：${reason}`]];
  }
  if (!isDict(raw)) return [null, ["变异清单必须是 JSON 对象"]];
  const spec = raw;
  const problems: string[] = [];
  const get = (key: string, fallback: PyValue): PyValue => (spec.has(key) ? (spec.get(key) as PyValue) : fallback);
  if (!relativeOk(get("cwd", "."))) problems.push("cwd 必须是工作副本内的相对路径");
  const timeout = get("timeout_seconds", MUTATION_DEFAULT_TIMEOUT);
  if (!positiveInt(timeout)) problems.push("timeout_seconds 必须是正整数");
  const commands: { id: PyValue; argv: PyValue; cwd: PyValue; timeout_seconds: PyValue }[] = [];
  if (spec.has("commands") && spec.has("command")) {
    problems.push("command 与 commands 只能写一个（commands 是 2.8.0 的多条命令）");
  } else if (spec.has("commands")) {
    let rawCommands = spec.get("commands") as PyValue;
    if (!(Array.isArray(rawCommands) && rawCommands.length >= 1 && rawCommands.length <= MUTATION_MAX_COMMANDS)) {
      problems.push(`commands 必须是 1 到 ${MUTATION_MAX_COMMANDS} 个对象的数组`);
      rawCommands = [];
    }
    (rawCommands as PyValue[]).forEach((entry, index) => {
      const label = `commands[${index + 1}]`;
      if (!isDict(entry) || [...entry.keys()].some((key) => !["id", "argv", "cwd", "timeout_seconds"].includes(key as string))) {
        problems.push(`${label} 必须是只含 id、argv、cwd、timeout_seconds 的对象`);
        return;
      }
      const cid = entry.get("id") ?? null;
      if (!isStr(cid) || !MUTATION_COMMAND_ID_RE.test(cid)) {
        problems.push(`${label}.id 必须匹配 ${MUTATION_COMMAND_ID_PATTERN}（会写进日志文件名）`);
      } else if (commands.some((command) => command.id === cid)) {
        problems.push(`${label}.id 重复：${cid}`);
      }
      if (!argvOk(entry.get("argv"))) problems.push(`${label}.argv 必须是非空的字符串数组（argv，不经过 shell）`);
      const cwd = entry.has("cwd") ? (entry.get("cwd") as PyValue) : get("cwd", ".");
      if (!relativeOk(cwd)) problems.push(`${label}.cwd 必须是工作副本内的相对路径`);
      const own = entry.has("timeout_seconds") ? (entry.get("timeout_seconds") as PyValue) : timeout;
      if (!positiveInt(own)) problems.push(`${label}.timeout_seconds 必须是正整数`);
      commands.push({ id: cid, argv: entry.get("argv") ?? null, cwd, timeout_seconds: own });
    });
  } else if (!argvOk(spec.get("command"))) {
    problems.push("command 必须是非空的字符串数组（argv，不经过 shell）；多条命令写 commands（2.8.0）");
  } else {
    commands.push({ id: "main", argv: spec.get("command") as PyValue, cwd: get("cwd", "."), timeout_seconds: timeout });
  }
  // {c["id"] for c in commands}：id 是列表或字典时 Python 在这里就崩（不可哈希）
  const unhashable = commands.find((command) => Array.isArray(command.id) || isDict(command.id));
  if (unhashable) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(unhashable.id)}'`);
  const knownIds = new Set(commands.map((command) => command.id));
  let mutations = spec.get("mutations");
  if (!(Array.isArray(mutations) && mutations.length)) {
    problems.push("mutations 必须是非空数组");
    mutations = [];
  }
  const names = new Set<string>();
  (mutations as PyValue[]).forEach((item, index) => {
    const label = `mutations[${index + 1}]`;
    if (!isDict(item)) {
      problems.push(`${label} 必须是对象`);
      return;
    }
    const name = item.get("name");
    if (!isStr(name) || !pyStrip(name)) problems.push(`${label}.name 必须是非空字符串`);
    else if (names.has(name)) problems.push(`${label}.name 重复：${name}`);
    else names.add(name);
    if (!relativeOk(item.get("file"))) problems.push(`${label}.file 必须是工作副本内的相对路径`);
    const [old, replacement] = [item.get("old"), item.get("new")];
    if (!isStr(old) || !old) problems.push(`${label}.old 必须是非空字符串`);
    if (!isStr(replacement)) problems.push(`${label}.new 必须是字符串`);
    else if (replacement === old) problems.push(`${label}.new 与 old 相同，不构成变异`);
    if (!positiveInt(item.has("count") ? (item.get("count") as PyValue) : 1n)) problems.push(`${label}.count 必须是正整数`);
    const expectMissed = item.get("expect_missed") ?? null;
    if (expectMissed !== null) {
      if (!(Array.isArray(expectMissed) && expectMissed.length && expectMissed.every(isStr) && new Set(expectMissed).size === expectMissed.length)) {
        problems.push(`${label}.expect_missed 必须是不重复的命令 id 数组`);
      } else {
        const unknown = [...new Set(expectMissed as string[])].filter((id) => !knownIds.has(id)).sort(cmpCodePoints);
        if (unknown.length) problems.push(`${label}.expect_missed 里有清单没有的命令：${unknown.join(", ")}`);
      }
    }
    const equivalent = item.get("equivalent") ?? null;
    if (equivalent !== null) {
      if (!isStr(equivalent) || !pyStrip(equivalent)) problems.push(`${label}.equivalent 必须是写明等价理由的非空字符串`);
      else if (expectMissed !== null) problems.push(`${label} 同时写了 equivalent 与 expect_missed：等价已表示每条命令都预期漏掉`);
    }
  });
  if (problems.length) return [null, problems];
  return [{ raw: spec, commands: commands as unknown as MutationCommand[], mutations: mutations as PyDict[] }, problems];
}

/** except (OSError, ValueError) as exc：读不出、不是 UTF-8、不是合法 JSON；RecursionError 不在其中，照抛。 */
function readFailure(error: unknown): string | null {
  if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return error.message;
  if (error instanceof PyJsonError && error.kind !== "RecursionError") return error.message;
  return null;
}

/** _insertion_only：new 包含完整的 old，原代码仍在，只插入了新代码。 */
export function insertionOnly(item: PyDict): boolean {
  const [old, replacement] = [item.get("old"), item.get("new")];
  return isStr(old) && isStr(replacement) && old.length > 0 && replacement.includes(old);
}

/** _mutation_spec_warnings：不阻止运行的清单提示。 */
export function mutationSpecWarnings(spec: MutationSpec): string[] {
  return spec.mutations.flatMap((item, index) =>
    insertionOnly(item)
      ? [`M${String(index + 1).padStart(2, "0")} ${pyStrValue(item.get("name") ?? null)}：new 包含完整的 old，原代码仍在，只插入了新代码。` +
          "插入的代码不改变被测行为时，漏掉不说明缺少测试；确认它确实改变了行为（例如提前返回、改写结果）"]
      : []);
}

// --- 锚点 ---------------------------------------------------------------------

const cpSlice = (text: string, start: number, end?: number): string => codePoints(text).slice(start, end).join("");

/** 文件按 UTF-8 读、CRLF 先换成 LF；不是 UTF-8 时抛 PyUnicodeDecodeError。 */
const lfText = (file: string): string => pyDecodeUtf8(pyReadBytes(file)).replaceAll(CRLF, LF);

/** _anchor_count：old 在文件里的出现次数，按 _apply_mutation 的口径（文件与 old 的 CRLF 都先按 LF 比对）。 */
export function anchorCount(file: string, old: string): number {
  return lfText(file).split(old.replaceAll(CRLF, LF)).length - 1;
}

/** _first_difference：第一处不同在第几个字符、两边各是什么；old 可以只是这一行的一段，行首行尾多出来的不算不同。 */
function firstDifference(wanted: string, actual: string, where = "old 首行"): string[] {
  const wantedLength = codePoints(wanted).length;
  for (const [tag, i1, i2, j1, j2] of new SequenceMatcher(wanted, actual, false).getOpcodes()) {
    if (tag === "equal" || (tag === "insert" && (i1 === 0 || i1 === wantedLength))) continue;
    const what = tag === "insert" ? `文件里多了「${cpSlice(cpSlice(actual, j1, j2), 0, 40)}」`
      : tag === "delete" ? `old 里多了「${cpSlice(cpSlice(wanted, i1, i2), 0, 40)}」`
        : `old 是「${cpSlice(cpSlice(wanted, i1, i2), 0, 40)}」，文件是「${cpSlice(cpSlice(actual, j1, j2), 0, 40)}」`;
    return [`  第一处不同在 ${where}（去掉首尾空白）第 ${i1 + 1} 个字符：${what}；old …${cpSlice(wanted, Math.max(0, i1 - ANCHOR_DIFF_CONTEXT), i2 + ANCHOR_DIFF_CONTEXT)}…，` +
      `文件 …${cpSlice(actual, Math.max(0, j1 - ANCHOR_DIFF_CONTEXT), j2 + ANCHOR_DIFF_CONTEXT)}…`];
  }
  return [];
}

/** _later_difference：首行在文件第 number 行对上了，逐行比 old 的后续行与文件里接着的行。 */
function laterDifference(old: string, lines: string[], number: number): string[] {
  let rest = old.split(LF);
  while (rest.length && !pyStrip(rest[0] as string)) rest.shift();
  rest = rest.slice(1);
  while (rest.length && !pyStrip(rest[rest.length - 1] as string)) rest.pop();
  const end = lines.length && lines[lines.length - 1] === "" ? lines.length - 1 : lines.length;
  for (const [index0, wanted] of rest.entries()) {
    const offset = index0 + 1;
    const index = number - 1 + offset;
    if (index >= end) return [`  首行对上了；文件在 L${end} 就结束了，old 还多 ${rest.length - offset + 1} 行`];
    const [want, have] = [pyStrip(wanted), pyStrip(lines[index] as string)];
    if (want === have || (offset === rest.length && have.startsWith(want))) continue;
    return [`  首行对上了，old 第 ${offset + 1} 行与文件 L${index + 1} 不同`, ...firstDifference(want, have, `old 第 ${offset + 1} 行`)];
  }
  return ["  逐行去掉首尾空白之后都对上了：差在缩进、行尾空白或换行"];
}

/** _anchor_hints：出现 0 次时列出最相近的至多 3 行与第一处不同；出现多次时列出每一处的行号与锚点之后的下一行。 */
export function anchorHints(file: string, oldRaw: string, found: number): string[] {
  const lines = lfText(file).split(LF);
  const old = oldRaw.replaceAll(CRLF, LF);
  if (found === 0) {
    const first = old.split(LF).map(pyStrip).find((line) => line) ?? "";
    if (!first) return [];
    const scored = lines
      .map((line, index) => [new SequenceMatcher(first, pyStrip(line)).ratio(), index + 1, line] as const)
      .filter(([, , line]) => pyStrip(line))
      .sort((x, y) => y[0] - x[0] || x[1] - y[1]);
    const near = scored.slice(0, 3).filter(([ratio]) => ratio >= ANCHOR_HINT_MIN_RATIO)
      .map(([ratio, number, line]) => `最相近 L${number}（${pyFixed(ratio * 100, 0)}%）：${cpSlice(pyStrip(line), 0, 160)}`);
    if (!near.length) return ["文件里没有相近的行"];
    const best = scored[0] as (typeof scored)[number];
    const difference = firstDifference(first, pyStrip(best[2]));
    return [...near.slice(0, 1), ...(difference.length ? difference : laterDifference(old, lines, best[1])), ...near.slice(1)];
  }
  const text = lines.join(LF);
  const hints: string[] = [];
  for (let start = text.indexOf(old); start !== -1 && hints.length < 5; start = text.indexOf(old, start + 1)) {
    const lineNo = text.slice(0, start).split(LF).length;
    const endLine = text.slice(0, start + old.length).split(LF).length;
    const following = endLine < lines.length ? (lines[endLine] as string) : "";
    hints.push(`出现在 L${lineNo}；锚点之后的下一行：${cpSlice(pyStrip(following), 0, 160) || "（空行）"}`);
  }
  return hints;
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** _check_anchors：只核对每条 old 的出现次数，不运行命令，不写任何文件。 */
export function checkAnchors(tree: string, spec: MutationSpec, out: PyOut): number {
  let mismatched = 0;
  spec.mutations.forEach((item, index) => {
    const mid = `M${String(index + 1).padStart(2, "0")}`;
    const count = Number(item.has("count") ? (item.get("count") as bigint) : 1n);
    const file = purePathStr(tree, item.get("file") as string);
    let status: string;
    let detail: string;
    let hints: string[] = [];
    if (!isFile(file) || !isWithin(pyResolve(file), tree)) {
      [status, detail] = ["MISSING", "文件不存在或位于树之外"];
    } else {
      let found: number | null = null;
      try {
        found = anchorCount(file, item.get("old") as string);
      } catch (error) {
        if (!(error instanceof PyUnicodeDecodeError)) throw error;
      }
      if (found === null) {
        [status, detail] = ["MISSING", "文件不是 UTF-8 文本"];
      } else {
        status = found === count ? "OK" : "MISMATCH";
        detail = found === count ? `出现 ${found} 次` : `出现 ${found} 次，期望 ${count} 次`;
        if (found !== count) hints = anchorHints(file, item.get("old") as string, found);
      }
    }
    if (status !== "OK") mismatched += 1;
    out.print(`${status.padEnd(8)} ${mid} ${pyStrValue(item.get("name") ?? null)}  ${detail}`, { flush: true });
    for (const hint of hints) out.print(`         ${hint}`, { flush: true });
  });
  out.print(`锚点核对：${spec.mutations.length} 条，${mismatched} 条不符`);
  return mismatched ? EXIT_FAIL : EXIT_OK;
}

export interface MutateArgs {
  readonly repo: string | null;
  readonly run_dir: string | null;
  readonly spec: string;
  readonly keep_workspace: boolean;
  readonly tree: string | null;
  readonly out: string | null;
  readonly check_anchors: boolean;
}

/**
 * cmd_mutate 与 _mutate_tree 的开头（④b5a 只接 --tree --check-anchors，整轮运行在 ④b5b）：参数的组合、树与清单的检查。
 * 清单的问题照 Python 先打到标准输出（ERROR 加一行），再报“变异清单无效”。
 */
export function cmdMutate(args: MutateArgs, out: PyOut): number {
  if (!args.tree) {
    if (!args.run_dir) throw new DispatchError("缺少 run_dir：对 attempt 给 run_dir，对草稿树用 --tree <路径>", EXIT_USAGE);
    if (args.out || args.check_anchors) throw new DispatchError("--out 与 --check-anchors 只在 --tree 模式下有效", EXIT_USAGE);
    throw new DispatchError("TS 实现还没有这条命令：mutate <run_dir>（④b5b）", EXIT_USAGE);
  }
  if (args.run_dir) throw new DispatchError("--tree 与 run_dir 二选一：对 attempt 用 run_dir，对草稿树用 --tree", EXIT_USAGE);
  const tree = pyResolve(purePathStr(args.tree));
  if (!isDirectory(tree)) throw new DispatchError(`--tree 不是目录：${tree}`, EXIT_USAGE);
  const [spec, problems] = loadMutationSpec(args.spec);
  if (spec === null) {
    for (const problem of problems) out.print(`ERROR ${problem}`);
    throw new DispatchError(`变异清单无效：${problems.length} 个问题`, EXIT_USAGE);
  }
  if (args.check_anchors) return checkAnchors(tree, spec, out);
  throw new DispatchError("TS 实现还没有这条命令：mutate --tree（不带 --check-anchors，④b5b）", EXIT_USAGE);
}

function isDirectory(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
