// pi_dispatch 对执行器 shell 命令的扫描（迁移第 ④b6 片）：路径在命令里的几种写法、主仓库路径、工作副本外的绝对路径、
// 屏蔽 worktree 与运行目录、只删缓存目录的 rm、命中所在的那一行、掩盖退出码的写法、没清理的临时目录、可疑命令。
// 正则原文来自生成的 event-patterns.ts，用 sre 移植编译；单字符集合的判断直接按码点写。下标一律是码点（与 Python 的 str
// 一致）。这是复审线索，不是 shell 解析。
import { lstatSync, statSync } from "node:fs";
import { type PyMatch, type PyPattern, compilePy, fromPoints, toPoints } from "@themis/base/pyregex";
import { purePathStr, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, isSpace, pySplit, pyStrip } from "@themis/base/pyre";
import { CACHE_DIR_NAMES, EVENT_PATTERNS as P, SUSPICIOUS_COMMANDS } from "./event-patterns.ts";
import { reEscape } from "./patterns.ts";

const IS_WINDOWS = process.platform === "win32";
const BS = String.fromCharCode(92);
const NL = String.fromCharCode(10);
const QUOTES = ['"', "'"];
const CASE = IS_WINDOWS ? "(?i)" : "";

const TEMP_PATH = compilePy(P.TEMP_PATH_RE);
const ABS_PATH_START = compilePy(P._ABS_PATH_START_RE);
const DEVICE_PATH = compilePy(P._DEVICE_PATH_RE);
const RM_CALL = compilePy(P._RM_CALL_RE);
const REMOVE_ITEM = compilePy(P.REMOVE_ITEM);
const MASKED_EXIT = compilePy(P.MASKED_EXIT_RE);
const PIPEFAIL = compilePy(P._PIPEFAIL_RE);
const CHECK_COMMAND = compilePy(P._CHECK_COMMAND_RE);
const TEMP_DIR_CREATE = compilePy(P._TEMP_DIR_CREATE_RE);
const TEMP_DIR_CLEANUP = compilePy(P._TEMP_DIR_CLEANUP_RE);
export const DELETE_LABEL = "递归或强制删除";
/** SUSPICIOUS_COMMANDS 按 re.I 编译，次序照 Python：调用方逐条判断，第一个记下的就停。 */
export const SUSPICIOUS: readonly (readonly [PyPattern, string])[] = SUSPICIOUS_COMMANDS.map(([pattern, label]) => [compilePy(`(?i)${pattern}`), label]);

const cpLength = (text: string): number => codePoints(text).length;
const at = (points: Int32Array, index: number): string => (index >= 0 && index < points.length ? String.fromCodePoint(points[index] as number) : "");

/** 从 from 起第一个满足条件的码点下标，没有为 -1。 */
function firstIndex(points: Int32Array, from: number, test: (char: string) => boolean): number {
  for (let index = from; index < points.length; index += 1) if (test(at(points, index))) return index;
  return -1;
}

/** str.find(char, from)。 */
const indexOfChar = (points: Int32Array, char: string, from: number): number => firstIndex(points, from, (item) => item === char);

const oneOf = (chars: string) => (char: string): boolean => isSpace(char) || chars.includes(char);

function stripRight(text: string, chars: string): string {
  const list = codePoints(text);
  while (list.length && chars.includes(list[list.length - 1] as string)) list.pop();
  return list.join("");
}

function realpath(value: string): string {
  try {
    return pyResolve(value);
  } catch {
    return value;
  }
}

/** _path_forms：路径在命令里可能出现的写法（原样、正斜杠、Git Bash 的 /c/…、解析后的长路径），按长度从长到短，等长的按码点（第 124 轮）。 */
export function pathForms(paths: readonly string[]): string[] {
  const forms = new Set<string>();
  for (const path of paths) {
    const shown = purePathStr(path);
    for (const text of new Set([shown, realpath(shown)])) {
      const slash = stripRight(text.split(BS).join("/"), "/");
      forms.add(stripRight(text, `${BS}/`));
      forms.add(slash);
      if (/^[A-Za-z]:[/]/u.test(slash)) forms.add(`/${(slash[0] as string).toLowerCase()}${codePoints(slash).slice(2).join("")}`);
    }
  }
  return [...forms].filter((form) => cpLength(form) > 3).sort((a, b) => cpLength(b) - cpLength(a) || cmpCodePoints(a, b));
}

/** _escapes：目录之后的相对部分规范化之后是否跳出这个目录。 */
export function escapes(rest: string): boolean {
  let depth = 0;
  for (const part of rest.split(BS).join("/").split("/")) {
    if (part === "..") {
      depth -= 1;
      if (depth < 0) return true;
    } else if (part !== "" && part !== ".") depth += 1;
  }
  return false;
}

const compiled = new Map<string, PyPattern>();

/** 按写法拼出来的模式：同一条在每条命令上都要用，编译一次。 */
function cached(source: string): PyPattern {
  let pattern = compiled.get(source);
  if (pattern === undefined) {
    pattern = compilePy(source);
    compiled.set(source, pattern);
  }
  return pattern;
}

const formPattern = (form: string): PyPattern => cached(`${CASE}${P.LEFT_EDGE}${reEscape(form)}`);

/** _protected_mentions：命令里位于受保护目录（主仓库）之内的路径参数，去重后的片段。 */
export function protectedMentions(command: string, forms: readonly string[]): string[] {
  const points = toPoints(command);
  const found: string[] = [];
  const taken: [number, number][] = [];
  for (const form of forms) {
    for (const match of formPattern(form).finditer(points)) {
      const start = match.start;
      if (taken.some(([lo, hi]) => lo <= start && start < hi)) continue;
      // 右边界：目录之后必须是路径分隔符、空白、引号、命令分隔符或参数结束
      const following = at(points, match.end);
      if (following && !oneOf(`/${BS};|&)<>"'`)(following)) continue;
      const quote = start > 0 && QUOTES.includes(at(points, start - 1)) ? at(points, start - 1) : "";
      let end: number;
      if (quote) {
        end = indexOfChar(points, quote, match.end);
        if (end < 0) end = points.length;
      } else {
        const tail = firstIndex(points, match.end, oneOf(`;|&)<>"'`));
        end = tail < 0 ? points.length : tail;
      }
      taken.push([start, end]);
      const excerpt = fromPoints(points, start, end);
      if (!found.includes(excerpt)) found.push(excerpt);
    }
  }
  return found;
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function lexists(path: string): boolean {
  try {
    lstatSync(path);
    return true;
  } catch {
    return false;
  }
}

/** _root_entry_exists：绝对路径的第一段（/usr、盘符根、Git Bash 的 /c）在本机是否存在；~ 总是存在。 */
export function rootEntryExists(text: string): boolean {
  if (text.startsWith("~")) return true;
  const chars = codePoints(text);
  if (/^[A-Za-z]$/u.test(chars[0] ?? "") && chars[1] === ":" && (chars[2] === BS || chars[2] === "/")) {
    return IS_WINDOWS && isDir(`${chars[0] as string}:${BS}`);
  }
  if (chars[0] !== "/") return false;
  let end = 1;
  while (end < chars.length && chars[end] !== "/" && chars[end] !== BS) end += 1;
  if (end === 1) return false;
  const first = chars.slice(1, end).join("");
  if (IS_WINDOWS && end === 2) return isDir(`${first}:${BS}`);
  return lexists(`/${first}`);
}

/** _outside_mentions：命令里出现的工作副本外绝对路径（系统目录、家目录、其他仓库或 worktree）。 */
export function outsideMentions(command: string, skipForms: readonly string[]): string[] {
  const points = toPoints(command);
  const found: string[] = [];
  const skips = skipForms.map((form) => cached(`${CASE}${reEscape(form)}${P.PATH_TAIL}`));
  for (const match of ABS_PATH_START.finditer(points)) {
    const start = match.start;
    const quote = start > 0 && QUOTES.includes(at(points, start - 1)) ? at(points, start - 1) : "";
    let end: number;
    if (quote) {
      // 只认开引号：引号前面还连着别的内容（例如 "$T"/x 的结束引号）时不是绝对路径
      if (start >= 2 && !oneOf("=(;|&<>,`")(at(points, start - 2))) continue;
      end = indexOfChar(points, quote, start);
      if (end < 0) end = points.length;
    } else {
      const tail = firstIndex(points, start, oneOf(`;|&()<>,"'` + "`"));
      end = tail < 0 ? points.length : tail;
    }
    const excerpt = fromPoints(points, start, end);
    if (!excerpt || DEVICE_PATH.match(excerpt) || TEMP_PATH.search(excerpt)) continue;
    if (skips.some((pattern) => pattern.match(excerpt))) continue;
    if (rootEntryExists(excerpt) && !found.includes(excerpt)) found.push(excerpt);
  }
  return found;
}

/** _mask_paths：命令中位于这些目录之内、认得准的完整路径参数换成 <worktree>；认不准的保留原文。 */
export function maskPaths(command: string, forms: readonly string[]): string {
  let current = command;
  for (const form of forms) {
    const points = toPoints(current);
    const pieces: string[] = [];
    let last = 0;
    for (const match of formPattern(form).finditer(points)) {
      const { start, end } = match;
      const quote = start > 0 && QUOTES.includes(at(points, start - 1)) ? at(points, start - 1) : "";
      let rest: string;
      let after: string;
      if (quote) {
        // 开引号前面还连着同一个参数、或结束的引号是转义的，都认不准
        if (start >= 2 && !oneOf("=(;|&")(at(points, start - 2))) continue;
        const close = indexOfChar(points, quote, end);
        if (close < 0 || at(points, close - 1) === BS) continue;
        rest = fromPoints(points, end, close);
        after = fromPoints(points, close + 1, Math.min(close + 2, points.length));
      } else {
        const stop = firstIndex(points, end, oneOf(`;|&)"'` + "`"));
        const close = stop < 0 ? points.length : stop;
        rest = fromPoints(points, end, close);
        after = fromPoints(points, close, Math.min(close + 1, points.length));
        if (rest.endsWith(BS)) continue; // 反斜杠转义了空白：参数还没结束
      }
      const first = codePoints(rest)[0];
      if ((after && !oneOf(";|&)")(after)) || (rest && first !== BS && first !== "/") || rest.includes("$") || rest.includes("`") || escapes(rest)) continue;
      pieces.push(`${fromPoints(points, last, start)}<worktree>`);
      last = end;
    }
    current = pieces.join("") + fromPoints(points, last, points.length);
  }
  return current;
}

/** _RM_CALL_RE 的第 2 组：rm 之后贪婪地吃掉“-选项 空白”的重复，剩下到匹配终点的是删除目标。 */
function rmTargets(points: Int32Array, call: PyMatch): string {
  let index = call.start + 2;
  while (index < call.end && isSpace(at(points, index))) index += 1;
  for (;;) {
    if (at(points, index) !== "-") break;
    let letters = index + 1;
    while (letters < call.end && /^[A-Za-z-]$/u.test(at(points, letters))) letters += 1;
    if (letters === index + 1) break;
    let spaces = letters;
    while (spaces < call.end && isSpace(at(points, spaces))) spaces += 1;
    if (spaces === letters) break;
    index = spaces;
  }
  return fromPoints(points, index, call.end);
}

const CACHE_DIR_PART = /^[A-Za-z0-9_.-]+$/u;

/**
 * _CACHE_TARGET_RE.match(target) 的第 2 组（最后一段之前的目录部分），不匹配为 null。原式带反向引用（sre 移植不收），
 * 这里按步骤照它：开头是引号时结尾必须是同一个引号；去掉引号之后是若干“[A-Za-z0-9_.-]+/”、一个缓存目录名、可有可无的
 * 一个 /。target 来自 split()，没有空白，$ 放过的结尾换行不会出现。形状由 gen_event_patterns.py 钉住。
 */
function cacheTargetDirs(target: string): string | null {
  const chars = codePoints(target);
  let body = chars;
  if (QUOTES.includes(chars[0] ?? "")) {
    if (chars.length < 2 || chars[chars.length - 1] !== chars[0]) return null;
    body = chars.slice(1, -1);
  }
  const parts = body.join("").split("/");
  if (parts.length > 1 && parts[parts.length - 1] === "") parts.pop();
  const name = parts.pop() as string;
  if (!CACHE_DIR_NAMES.includes(name) || !parts.every((part) => CACHE_DIR_PART.test(part))) return null;
  return parts.map((part) => `${part}/`).join("");
}

/** _cache_dir_cleanup：递归或强制删除只删工作副本内的缓存目录时，第一个 rm 调用的原文；否则 null。 */
export function cacheDirCleanup(command: string): string | null {
  if (REMOVE_ITEM.search(command)) return null;
  const points = toPoints(command);
  const calls = RM_CALL.finditer(points);
  if (!calls.length) return null;
  for (const call of calls) {
    const targets = pySplit(rmTargets(points, call));
    if (!targets.length) return null;
    for (const target of targets) {
      const dirs = cacheTargetDirs(target);
      if (dirs === null || dirs.split("/").includes("..")) return null;
    }
  }
  return pyStrip((calls[0] as PyMatch).group);
}

/** _match_excerpt：命中位置所在的那一行；超过 width 时截取命中附近的一段。 */
export function matchExcerpt(text: string, start: number, end: number, width = 160): string {
  const chars = codePoints(text);
  const lineStart = start > 0 ? chars.lastIndexOf(NL, start - 1) + 1 : 0;
  const found = chars.indexOf(NL, end);
  let line = chars.slice(lineStart, found !== -1 ? found : chars.length);
  if (line.length > width) {
    const low = Math.max(0, Math.min(start - lineStart - Math.floor(width / 3), line.length - width));
    line = [...(low ? ["…"] : []), ...line.slice(low, low + width), ...(low + width < line.length ? ["…"] : [])];
  }
  return pyStrip(line.join(""));
}

/** _masked_exit_mention：第一处掩盖退出码的写法的摘录；没有，或命令自己处理了管道退出码时为空。 */
export function maskedExitMention(command: string): string {
  if (PIPEFAIL.search(command)) return "";
  const found = MASKED_EXIT.search(command);
  return found ? matchExcerpt(command, found.start, found.end) : "";
}

export const isCheckCommand = (command: string): boolean => CHECK_COMMAND.search(command) !== null;

/** _temp_dir_without_cleanup：创建了临时目录、同一条命令里却没有清理时，创建处的摘录。 */
export function tempDirWithoutCleanup(command: string): string {
  const found = TEMP_DIR_CREATE.search(command);
  if (!found || TEMP_DIR_CLEANUP.search(command)) return "";
  return matchExcerpt(command, found.start, found.end);
}

/** scan.splitlines() 的每一行里 TEMP_PATH_RE 的命中：（行号, 摘录），同一行里相同的摘录只记一次。 */
export function tempPathMatches(lines: readonly string[]): [number, string][] {
  const out: [number, string][] = [];
  lines.forEach((line, index) => {
    const seen = new Set<string>();
    for (const match of TEMP_PATH.finditer(line)) {
      const excerpt = matchExcerpt(line, match.start, match.end);
      if (seen.has(excerpt)) continue;
      seen.add(excerpt);
      out.push([index + 1, excerpt]);
    }
  });
  return out;
}

