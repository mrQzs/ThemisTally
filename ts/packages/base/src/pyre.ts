// Python re 与 str 语义的构件：把 Python 正则逐条翻译成 JS 时用（迁移第 ① 步 secrets）。
// 判定一律查 pyunicode.ts（由本机 Python 生成的区间表），不用 JS 的 \w、\b、\s、\d、\p{...}，也不用 i、m 标志：
//   - \w \d \s：Python 按 Unicode（与 JS 不同；JS 的 \b 加了 u 标志也只认 ASCII）
//   - \b：(?:(?<=W)(?!W)|(?<!W)(?=W))，W 是 Python 的 \w
//   - re.I：ASCII 字母还匹配 İ ı ſ K（IGNORECASE_EXTRA），JS 的 iu 只多匹配 ſ 与 K，所以把大小写展开成字符类
//   - 不带 MULTILINE 的 $：末尾换行之前也算，写成 (?=\n?$)；\Z 才是 JS 的 $
//   - .（不带 DOTALL）：Python 只不配 \n，JS 还不配 \r、U+2028、U+2029，所以写成 [^\n]
// 所有正则都带 u 标志：按码点匹配（量词按码点计数，孤立代理项也算一个字符），与 Python 的 str 一致。
import {
  CF_CC,
  DIGIT,
  IGNORECASE_EXTRA,
  IS_DIGIT,
  IS_LOWER,
  IS_PRINTABLE,
  IS_SPACE,
  IS_UPPER,
  SPACE,
  UNASSIGNED,
  UNIDATA_VERSION,
  WORD,
} from "./pyunicode.ts";

const BACKSLASH = String.fromCharCode(92);

function escapeCodePoint(cp: number): string {
  return `${BACKSLASH}u{${cp.toString(16)}}`;
}

/** 区间表（[起, 止, 起, 止, …]）拼成 JS 字符类。 */
export function charClass(table: readonly number[], negate = false): string {
  let body = "";
  for (let index = 0; index < table.length; index += 2) {
    const low = table[index] ?? 0;
    const high = table[index + 1] ?? low;
    body += low === high ? escapeCodePoint(low) : `${escapeCodePoint(low)}-${escapeCodePoint(high)}`;
  }
  return `[${negate ? "^" : ""}${body}]`;
}

/** 区间表里有没有这个码点（二分查找）。 */
export function inTable(table: readonly number[], cp: number): boolean {
  let low = 0;
  let high = table.length / 2 - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (cp < (table[middle * 2] ?? 0)) high = middle - 1;
    else if (cp > (table[middle * 2 + 1] ?? 0)) low = middle + 1;
    else return true;
  }
  return false;
}

/** Python 的 \w、\d、\s 与它们的补集，以及 \b。 */
export const W = charClass(WORD);
export const D = charClass(DIGIT);
export const S = charClass(SPACE);
export const NOT_S = charClass(SPACE, true);
export const WB = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;
/** 不带 MULTILINE 的 $。 */
export const PY_END = "(?=\\n?$)";

/** re.I 下 ASCII 字母之外还匹配的字符（全部字母），用在含整个 A-Z 的字符类里。 */
export const IGNORECASE_ALL = Object.values(IGNORECASE_EXTRA)
  .flat()
  .map(escapeCodePoint)
  .join("");

/** re.I 下的字面量：每个 ASCII 字母展开成 [小写大写加 re 文档写明的那几个非 ASCII 字母]，其余字符转义。 */
export function ci(literal: string): string {
  let out = "";
  for (const char of literal) {
    const lower = char.toLowerCase();
    if (/^[a-z]$/.test(lower)) {
      const extra = (IGNORECASE_EXTRA[lower] ?? []).map(escapeCodePoint).join("");
      out += `[${lower}${lower.toUpperCase()}${extra}]`;
    } else {
      out += char.replace(/[\\^$.*+?()[\]{}|/-]/g, (c) => BACKSLASH + c);
    }
  }
  return out;
}

const codePoint = (char: string): number => char.codePointAt(0) ?? 0;

export const isSpace = (char: string): boolean => inTable(IS_SPACE, codePoint(char));
export const isPrintableChar = (char: string): boolean => inTable(IS_PRINTABLE, codePoint(char));
export const isUpper = (char: string): boolean => inTable(IS_UPPER, codePoint(char));
export const isLower = (char: string): boolean => inTable(IS_LOWER, codePoint(char));
export const isDigitChar = (char: string): boolean => inTable(IS_DIGIT, codePoint(char));
export const isCfOrCc = (char: string): boolean => inTable(CF_CC, codePoint(char));

/** 按码点拆成字符（孤立代理项也算一个）。 */
export function codePoints(text: string): string[] {
  return Array.from(text);
}

/** len(text)：码点数。 */
export function pyLen(text: string): number {
  let count = 0;
  for (const _char of text) count += 1;
  return count;
}

/** str.strip() / str.rstrip()：去掉 str.isspace 认的空白。 */
export function pyStrip(text: string): string {
  return pyRstrip(pyLstrip(text));
}

export function pyLstrip(text: string): string {
  const chars = codePoints(text);
  let start = 0;
  while (start < chars.length && isSpace(chars[start] ?? "")) start += 1;
  return chars.slice(start).join("");
}

export function pyRstrip(text: string): string {
  const chars = codePoints(text);
  let end = chars.length;
  while (end > 0 && isSpace(chars[end - 1] ?? "")) end -= 1;
  return chars.slice(0, end).join("");
}

/** str.splitlines() 认的行界：\r\n，以及 \n \r \v \f 0x1c 0x1d 0x1e 0x85 U+2028 U+2029。 */
const LINE_BREAK_RE = new RegExp(
  `${BACKSLASH}r${BACKSLASH}n|[${[0x0a, 0x0d, 0x0b, 0x0c, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029].map(escapeCodePoint).join("")}]`,
  "u",
);

/** str.splitlines()（不保留行尾）：末尾的行界之后不再多出空行；空串为 []。 */
export function pySplitlines(text: string): string[] {
  const lines: string[] = [];
  let rest = text;
  while (rest.length > 0) {
    const match = LINE_BREAK_RE.exec(rest);
    if (match === null) {
      lines.push(rest);
      break;
    }
    lines.push(rest.slice(0, match.index));
    rest = rest.slice(match.index + match[0].length);
  }
  return lines;
}

/** str.isprintable()：空串为 true。 */
export function pyIsPrintable(text: string): boolean {
  return codePoints(text).every(isPrintableChar);
}

function versionAtLeast(actual: string, wanted: string): boolean {
  const [a = 0, b = 0] = actual.split(".").map(Number);
  const [x = 0, y = 0] = wanted.split(".").map(Number);
  return a > x || (a === x && b >= y);
}

/** 第 15、16 平面的私用区：组合类为 0、没有分解、不参与组合，行为正好等于 Python 眼里的“未分配”。 */
function* privateUse(): Generator<number> {
  for (let cp = 0xf0000; cp <= 0xffffd; cp += 1) yield cp;
  for (let cp = 0x100000; cp <= 0x10fffd; cp += 1) yield cp;
}

/**
 * unicodedata.normalize("NFKC", text)，与 Python 的 Unicode 版本（UNIDATA_VERSION）一致。
 * JS 的 normalize 用的是运行时自带 ICU 的 Unicode 版本（Node 24.19、Bun 1.4.2 都是 17.0），比 Python 3.12 的 15.0 新：
 * 15.0 之后新分配的字符可能有了分解或非零组合类。按 Unicode 的规范化稳定性政策，只要文本里全是旧版本已分配的字符，
 * 两边结果相同；所以先把 Python 眼里未分配（Cn）的码点换成输入里没有的私用区占位符，规范化之后再换回来
 * （themistally-15 用 825,345 个码点验证过零差异）。运行时比 Python 的版本还旧时拒绝：反方向的差异兜不住。
 */
export function pyNfkc(text: string, runtime: string = process.versions.unicode ?? "0.0"): string {
  if (!versionAtLeast(runtime, UNIDATA_VERSION)) {
    throw new Error(`运行时的 Unicode ${runtime} 比 Python 参照版本 ${UNIDATA_VERSION} 旧，NFKC 的结果无法保证一致，拒绝脱敏`);
  }
  const chars = codePoints(text);
  const present = new Set(chars.map(codePoint));
  const placeholders = new Map<number, string>();
  const originals = new Map<number, string>();
  const spare = privateUse();
  const swapped = chars.map((char) => {
    const cp = codePoint(char);
    if (!inTable(UNASSIGNED, cp)) return char;
    let placeholder = placeholders.get(cp);
    if (placeholder === undefined) {
      let next = spare.next();
      while (!next.done && present.has(next.value)) next = spare.next();
      if (next.done) throw new Error("文本里未分配的码点太多，私用区的占位符不够用");
      placeholder = String.fromCodePoint(next.value);
      placeholders.set(cp, placeholder);
      originals.set(next.value, char);
    }
    return placeholder;
  });
  const normalized = swapped.join("").normalize("NFKC");
  if (originals.size === 0) return normalized;
  return codePoints(normalized)
    .map((char) => originals.get(codePoint(char)) ?? char)
    .join("");
}

/** 带 u 标志编译；需要全局替换时加 g。 */
export function pyRegex(source: string, global = false): RegExp {
  return new RegExp(source, global ? "gu" : "u");
}
