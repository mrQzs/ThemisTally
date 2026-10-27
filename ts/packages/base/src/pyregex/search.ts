// logs search 的 PATTERN（kit_logs._compile_search 的 TS 版，第 58 轮的次序写死）：
//   (a) 括号嵌套按字面扫描，超过 100 层报固定的错；
//   (b) parse，re.error 与 OverflowError 报“PATTERN 不是合法的正则表达式：<原文>”；
//   (c) 有反向引用或条件分组报固定的错；
//   (d) 编译（编译期的 re.error 同 (b) 的写法）。
// 报错是 kit_logs 的 LogsError（退出码 2），这里抛 SearchPatternError；ValueError（例如 (?a)(?u)）Python 不接、
// 打堆栈退出，这里原样抛 PyValueError，入口按崩溃处理。
import { codePoints } from "../pyre.ts";
import { type Program, WORD_SETS, compileProgram } from "./compile.ts";
import { matchSpan, search, searchSpan } from "./engine.ts";
import { type Item, PyOverflowError, PyReError, type SubPattern, parse } from "./parser.ts";

export { PyOverflowError, PyReError, PyValueError } from "./parser.ts";

export const SEARCH_MAX_NESTING = 100;
export const SEARCH_NO_REFS = "PATTERN 不支持反向引用与条件分组（logs search 只做逐行匹配）";
export const SEARCH_TOO_DEEP = `PATTERN 的括号嵌套超过 ${SEARCH_MAX_NESTING} 层`;

export class SearchPatternError extends Error {}

/** kit_logs._paren_depth：反斜杠连同后一个字符跳过，字符类里的不算（[ 或 [^ 之后紧跟的 ] 是字面字符）。 */
export function parenDepth(pattern: string): number {
  const chars = codePoints(pattern);
  let depth = 0;
  let deepest = 0;
  let index = 0;
  let inClass = false;
  while (index < chars.length) {
    const char = chars[index];
    if (char === "\\") {
      index += 2;
      continue;
    }
    if (inClass) {
      inClass = char !== "]";
    } else if (char === "[") {
      inClass = true;
      index += 1;
      if (chars[index] === "^") index += 1;
      if (chars[index] === "]") index += 1;
      continue;
    } else if (char === "(") {
      depth += 1;
      deepest = Math.max(deepest, depth);
    } else if (char === ")") {
      depth = Math.max(0, depth - 1);
    }
    index += 1;
  }
  return deepest;
}

function itemUsesRefs(item: Item): boolean {
  switch (item.op) {
    case "GROUPREF":
    case "GROUPREF_EXISTS":
      return true;
    case "SUBPATTERN":
      return usesRefs(item.av[3]);
    case "BRANCH":
      return item.av[1].some(usesRefs);
    case "MAX_REPEAT":
    case "MIN_REPEAT":
    case "POSSESSIVE_REPEAT":
      return usesRefs(item.av[2]);
    case "ATOMIC_GROUP":
      return usesRefs(item.av);
    case "ASSERT":
    case "ASSERT_NOT":
      return usesRefs(item.av[1]);
    default:
      return false;
  }
}

/** kit_logs._uses_refs。 */
export function usesRefs(pattern: SubPattern): boolean {
  return pattern.data.some(itemUsesRefs);
}

/** 字符串按码点写进 Int32Array（成对的代理项合成一个，落单的照原样），与 Python 的 str 下标一致。 */
export function toPoints(text: string): Int32Array {
  const points = new Int32Array(text.length);
  let size = 0;
  for (let index = 0; index < text.length; index += 1) {
    let unit = text.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff && index + 1 < text.length) {
      const low = text.charCodeAt(index + 1);
      if (low >= 0xdc00 && low <= 0xdfff) {
        unit = ((unit - 0xd800) << 10) + (low - 0xdc00) + 0x10000;
        index += 1;
      }
    }
    points[size] = unit;
    size += 1;
  }
  return points.subarray(0, size);
}

/** 码点下标 [start, end) 的那一段（落单的代理项照原样）。 */
export function fromPoints(points: Int32Array, start = 0, end = points.length): string {
  let out = "";
  for (let index = start; index < end; index += 1) out += String.fromCodePoint(points[index] as number);
  return out;
}

/** 一处匹配：起止位置是码点下标（与 Python 的 match.start()、match.end() 一致），group 是 match.group(0)。 */
export interface PyMatch {
  readonly start: number;
  readonly end: number;
  readonly group: string;
}

/** re.compile 之后的 search、match、finditer（不记捕获组：只交回整段匹配的位置）。 */
export class PyPattern {
  private readonly program: Program;

  constructor(program: Program) {
    this.program = program;
  }

  search(text: string | Int32Array, pos = 0): PyMatch | null {
    const points = typeof text === "string" ? toPoints(text) : text;
    return matchOf(points, searchSpan(this.program, points, WORD_SETS, pos));
  }

  match(text: string | Int32Array, pos = 0): PyMatch | null {
    const points = typeof text === "string" ? toPoints(text) : text;
    return matchOf(points, matchSpan(this.program, points, WORD_SETS, pos));
  }

  /** finditer：只移植非空匹配；遇到空匹配直接报错（④b6 用到的模式都不会空匹配，空匹配的推进规则另有讲究）。 */
  finditer(text: string | Int32Array): PyMatch[] {
    const points = typeof text === "string" ? toPoints(text) : text;
    const found: PyMatch[] = [];
    let pos = 0;
    for (;;) {
      const span = searchSpan(this.program, points, WORD_SETS, pos);
      if (span === null) return found;
      if (span[1] === span[0]) throw new Error("PyPattern.finditer：空匹配没有移植");
      found.push(matchOf(points, span) as PyMatch);
      pos = span[1];
    }
  }
}

function matchOf(points: Int32Array, span: [number, number] | null): PyMatch | null {
  return span === null ? null : { start: span[0], end: span[1], group: fromPoints(points, span[0], span[1]) };
}

/** re.compile(pattern)：报错照 Python 原样抛（PyReError 的 message 就是 str(re.error)）。 */
export function compilePy(pattern: string): PyPattern {
  const tree = parse(pattern);
  return new PyPattern(compileProgram(tree, tree.state.flags));
}

const invalid = (error: Error): SearchPatternError => new SearchPatternError(`PATTERN 不是合法的正则表达式：${error.message}`);

/** 编译好的 PATTERN：test(line) 即 Python 的 pattern.search(line) is not None。 */
export class SearchPattern {
  private readonly program: Program;
  private buffer = new Int32Array(256);

  constructor(program: Program) {
    this.program = program;
  }

  test(line: string): boolean {
    // 按码点（与 Python 的 str 一致：成对的代理项合成一个，落单的照原样）写进复用的缓冲区
    if (this.buffer.length < line.length) this.buffer = new Int32Array(Math.max(line.length, this.buffer.length * 2));
    const buffer = this.buffer;
    let size = 0;
    for (let index = 0; index < line.length; index += 1) {
      let unit = line.charCodeAt(index);
      if (unit >= 0xd800 && unit <= 0xdbff && index + 1 < line.length) {
        const low = line.charCodeAt(index + 1);
        if (low >= 0xdc00 && low <= 0xdfff) {
          unit = ((unit - 0xd800) << 10) + (low - 0xdc00) + 0x10000;
          index += 1;
        }
      }
      buffer[size] = unit;
      size += 1;
    }
    return search(this.program, buffer.subarray(0, size), WORD_SETS);
  }
}

/**
 * re.compile(pattern) 再 search：报错照 Python 原样抛，PyReError 的 message 就是 str(re.error)，OverflowError、ValueError
 * 同理（迁移第 ④ 步：合同的 output_must_match 校验与检查日志的匹配、路径模式都用它）。不加 logs search 的那几条限制。
 */
/**
 * 合同 output_must_match、output_must_not_match 的校验（第 129 轮）：照 re.compile 解析加编译（报错照原样抛），再交回
 * 有没有反向引用或条件分组（判据同 kit_logs._uses_refs）。只编不跑。
 */
export function patternUsesRefs(pattern: string): boolean {
  const tree = parse(pattern);
  compileProgram(tree, tree.state.flags, true);
  return usesRefs(tree);
}

export function compilePattern(pattern: string): SearchPattern {
  const tree = parse(pattern);
  return new SearchPattern(compileProgram(tree, tree.state.flags));
}

/** kit_logs._compile_search。 */
export function compileSearch(pattern: string): SearchPattern {
  if (parenDepth(pattern) > SEARCH_MAX_NESTING) throw new SearchPatternError(SEARCH_TOO_DEEP);
  let tree: SubPattern;
  try {
    tree = parse(pattern);
  } catch (error) {
    if (error instanceof PyReError || error instanceof PyOverflowError) throw invalid(error);
    throw error;
  }
  if (usesRefs(tree)) throw new SearchPatternError(SEARCH_NO_REFS);
  try {
    return new SearchPattern(compileProgram(tree, tree.state.flags));
  } catch (error) {
    if (error instanceof PyReError || error instanceof PyOverflowError) throw invalid(error);
    throw error;
  }
}
