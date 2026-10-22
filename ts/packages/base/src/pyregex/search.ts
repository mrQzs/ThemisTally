// logs search 的 PATTERN（kit_logs._compile_search 的 TS 版，第 58 轮的次序写死）：
//   (a) 括号嵌套按字面扫描，超过 100 层报固定的错；
//   (b) parse，re.error 与 OverflowError 报“PATTERN 不是合法的正则表达式：<原文>”；
//   (c) 有反向引用或条件分组报固定的错；
//   (d) 编译（编译期的 re.error 同 (b) 的写法）。
// 报错是 kit_logs 的 LogsError（退出码 2），这里抛 SearchPatternError；ValueError（例如 (?a)(?u)）Python 不接、
// 打堆栈退出，这里原样抛 PyValueError，入口按崩溃处理。
import { codePoints } from "../pyre.ts";
import { type Program, WORD_SETS, compileProgram } from "./compile.ts";
import { search } from "./engine.ts";
import { type Item, PyOverflowError, PyReError, type SubPattern, parse } from "./parser.ts";

export { PyValueError } from "./parser.ts";

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
