// Python re 的语法分析：CPython 3.12.10 Lib/re/_parser.py 的逐段移植（迁移第 ②b2 步，logs search 用）。
// 只移植 str 模式（PATTERN 来自命令行，总是 str）；位置、长度一律按码点。报错文字与位置照原样（re.error 的格式，
// 见 PyReError）；_parser 里的 warnings.warn 不移植——kit_logs 编译时静默了警告（r3 §10 第 58 轮补）。
// 语法树的形状照 _parser：每项是 {op, av}，SubPattern 之间按身份比较（与 Python 的元组比较一致）。
import { pyRepr } from "../pyfmt.ts";
import { codePoints, inTable } from "../pyre.ts";
import { lookupName } from "./lookup.ts";
import { ID_CONTINUE, ID_START, IS_ALPHA } from "./tables.ts";

export const MAXREPEAT = 4294967295n;
export const MAXGROUPS = 1073741823;
export const MAXWIDTH = 1n << 64n;

export const FLAG_TEMPLATE = 1;
export const FLAG_IGNORECASE = 2;
export const FLAG_LOCALE = 4;
export const FLAG_MULTILINE = 8;
export const FLAG_DOTALL = 16;
export const FLAG_UNICODE = 32;
export const FLAG_VERBOSE = 64;
export const FLAG_DEBUG = 128;
export const FLAG_ASCII = 256;
export const TYPE_FLAGS = FLAG_ASCII | FLAG_LOCALE | FLAG_UNICODE;
const GLOBAL_FLAGS = FLAG_DEBUG | FLAG_TEMPLATE;
const FLAGS: Readonly<Record<string, number>> = {
  i: FLAG_IGNORECASE, L: FLAG_LOCALE, m: FLAG_MULTILINE, s: FLAG_DOTALL, x: FLAG_VERBOSE, a: FLAG_ASCII,
  t: FLAG_TEMPLATE, u: FLAG_UNICODE,
};

const BS = "\\";
const NL = String.fromCharCode(10);
const SPECIAL_CHARS = ".\\[{()*+?^$|";
const REPEAT_CHARS = "*+?{";
const DIGITS = new Set("0123456789");
const OCTDIGITS = new Set("01234567");
const HEXDIGITS = new Set("0123456789abcdefABCDEF");
const ASCIILETTERS = new Set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ");
const WHITESPACE = new Set([" ", String.fromCharCode(9), NL, String.fromCharCode(13), String.fromCharCode(11), String.fromCharCode(12)]);

/** re.error：msg 是原文；有 pattern 与 pos 时加“ at position N”，pattern 里有换行时再加“ (line L, column C)”。 */
export class PyReError extends Error {
  readonly msg: string;

  constructor(msg: string, pattern: readonly string[] | null = null, pos: number | null = null) {
    let text = msg;
    if (pattern !== null && pos !== null) {
      text = `${msg} at position ${pos}`;
      const before = pattern.slice(0, Math.max(0, pos));
      const lineno = before.filter((char) => char === NL).length + 1;
      const colno = pos - before.lastIndexOf(NL);
      if (pattern.includes(NL)) text = `${text} (line ${lineno}, column ${colno})`;
    }
    super(text);
    this.msg = msg;
  }
}

/** OverflowError（重复次数太大）：kit_logs 与 re.error 一样接住。 */
export class PyOverflowError extends Error {}

/** ValueError（fix_flags 的“ASCII and UNICODE flags are incompatible”）：kit_logs 不接，Python 打堆栈。 */
export class PyValueError extends Error {}

export type Category = "DIGIT" | "NOT_DIGIT" | "SPACE" | "NOT_SPACE" | "WORD" | "NOT_WORD";
export type AtCode = "BEGINNING" | "BEGINNING_STRING" | "BOUNDARY" | "NON_BOUNDARY" | "END" | "END_STRING";
export type SetItem =
  | { readonly op: "LITERAL"; readonly av: number }
  | { readonly op: "RANGE"; readonly av: readonly [number, number] }
  | { readonly op: "CATEGORY"; readonly av: Category }
  | { readonly op: "NEGATE"; readonly av: null };
export type RepeatOp = "MAX_REPEAT" | "MIN_REPEAT" | "POSSESSIVE_REPEAT";
export type Item =
  | { readonly op: "LITERAL" | "NOT_LITERAL"; readonly av: number }
  | { readonly op: "ANY"; readonly av: null }
  | { readonly op: "IN"; readonly av: readonly SetItem[] }
  | { readonly op: "AT"; readonly av: AtCode }
  | { readonly op: "BRANCH"; readonly av: readonly [null, readonly SubPattern[]] }
  | { readonly op: "SUBPATTERN"; readonly av: readonly [number | null, number, number, SubPattern] }
  | { readonly op: RepeatOp; readonly av: readonly [bigint, bigint, SubPattern] }
  | { readonly op: "ATOMIC_GROUP"; readonly av: SubPattern }
  | { readonly op: "ASSERT" | "ASSERT_NOT"; readonly av: readonly [number, SubPattern] }
  | { readonly op: "GROUPREF"; readonly av: number }
  | { readonly op: "GROUPREF_EXISTS"; readonly av: readonly [number, SubPattern, SubPattern | null] };

const REPEAT_OPS = new Set<string>(["MIN_REPEAT", "MAX_REPEAT", "POSSESSIVE_REPEAT"]);
const UNIT_OPS = new Set<string>(["ANY", "RANGE", "IN", "LITERAL", "NOT_LITERAL", "CATEGORY"]);

const ESCAPES: Readonly<Record<string, Item>> = {
  [`${BS}a`]: { op: "LITERAL", av: 7 },
  [`${BS}b`]: { op: "LITERAL", av: 8 },
  [`${BS}f`]: { op: "LITERAL", av: 12 },
  [`${BS}n`]: { op: "LITERAL", av: 10 },
  [`${BS}r`]: { op: "LITERAL", av: 13 },
  [`${BS}t`]: { op: "LITERAL", av: 9 },
  [`${BS}v`]: { op: "LITERAL", av: 11 },
  [`${BS}${BS}`]: { op: "LITERAL", av: 92 },
};

const inSet = (category: Category): Item => ({ op: "IN", av: [{ op: "CATEGORY", av: category }] });
const CATEGORIES: Readonly<Record<string, Item>> = {
  [`${BS}A`]: { op: "AT", av: "BEGINNING_STRING" },
  [`${BS}b`]: { op: "AT", av: "BOUNDARY" },
  [`${BS}B`]: { op: "AT", av: "NON_BOUNDARY" },
  [`${BS}d`]: inSet("DIGIT"),
  [`${BS}D`]: inSet("NOT_DIGIT"),
  [`${BS}s`]: inSet("SPACE"),
  [`${BS}S`]: inSet("NOT_SPACE"),
  [`${BS}w`]: inSet("WORD"),
  [`${BS}W`]: inSet("NOT_WORD"),
  [`${BS}Z`]: { op: "AT", av: "END_STRING" },
};

const cpLen = (text: string): number => codePoints(text).length;
const ord = (char: string): number => char.codePointAt(0) ?? 0;
const minBig = (a: bigint, b: bigint): bigint => (a < b ? a : b);
const maxBig = (a: bigint, b: bigint): bigint => (a > b ? a : b);

/** str.isidentifier。 */
function isIdentifier(name: string): boolean {
  const chars = codePoints(name);
  return chars.length > 0 && inTable(ID_START, ord(chars[0] as string)) && chars.slice(1).every((char) => inTable(ID_CONTINUE, ord(char)));
}

/** str.isalpha（非空，每个字符都是字母）。 */
function isAlpha(text: string): boolean {
  const chars = codePoints(text);
  return chars.length > 0 && chars.every((char) => inTable(IS_ALPHA, ord(char)));
}

const isAsciiDecimal = (text: string): boolean => /^[0-9]+$/u.test(text);

class State {
  flags = 0;
  readonly groupdict = new Map<string, number>();
  readonly groupwidths: ([bigint, bigint] | null)[] = [null];
  lookbehindgroups: number | null = null;
  readonly grouprefpos = new Map<number, number>();

  get groups(): number {
    return this.groupwidths.length;
  }

  opengroup(name: string | null): number {
    const gid = this.groups;
    this.groupwidths.push(null);
    if (this.groups > MAXGROUPS) throw new PyReError("too many groups");
    if (name !== null) {
      const ogid = this.groupdict.get(name);
      if (ogid !== undefined) throw new PyReError(`redefinition of group name ${pyRepr(name)} as group ${gid}; was group ${ogid}`);
      this.groupdict.set(name, gid);
    }
    return gid;
  }

  closegroup(gid: number, p: SubPattern): void {
    this.groupwidths[gid] = p.getwidth();
  }

  checkgroup(gid: number): boolean {
    return gid < this.groups && this.groupwidths[gid] != null;
  }

  checklookbehindgroup(gid: number, source: Tokenizer): void {
    if (this.lookbehindgroups !== null) {
      if (!this.checkgroup(gid)) throw source.error("cannot refer to an open group");
      if (gid >= this.lookbehindgroups) throw source.error("cannot refer to group defined in the same lookbehind subpattern");
    }
  }
}

export class SubPattern {
  readonly state: State;
  data: Item[];
  private width: [bigint, bigint] | null = null;

  constructor(state: State, data: Item[] = []) {
    this.state = state;
    this.data = data;
  }

  /** SubPattern.getwidth：(最少, 最多) 个字符，上限 MAXWIDTH。 */
  getwidth(): [bigint, bigint] {
    if (this.width !== null) return this.width;
    let lo = 0n;
    let hi = 0n;
    for (const item of this.data) {
      if (item.op === "BRANCH") {
        let i = MAXWIDTH;
        let j = 0n;
        for (const sub of item.av[1]) {
          const [l, h] = sub.getwidth();
          i = minBig(i, l);
          j = maxBig(j, h);
        }
        lo += i;
        hi += j;
      } else if (item.op === "ATOMIC_GROUP") {
        const [i, j] = item.av.getwidth();
        lo += i;
        hi += j;
      } else if (item.op === "SUBPATTERN") {
        const [i, j] = item.av[3].getwidth();
        lo += i;
        hi += j;
      } else if (REPEAT_OPS.has(item.op)) {
        const [min, max, sub] = item.av as readonly [bigint, bigint, SubPattern];
        const [i, j] = sub.getwidth();
        lo += i * min;
        if (max === MAXREPEAT && j) hi = MAXWIDTH;
        else hi += j * max;
      } else if (UNIT_OPS.has(item.op)) {
        lo += 1n;
        hi += 1n;
      } else if (item.op === "GROUPREF") {
        const [i, j] = this.state.groupwidths[item.av] as [bigint, bigint];
        lo += i;
        hi += j;
      } else if (item.op === "GROUPREF_EXISTS") {
        let [i, j] = item.av[1].getwidth();
        if (item.av[2] !== null) {
          const [l, h] = item.av[2].getwidth();
          i = minBig(i, l);
          j = maxBig(j, h);
        } else {
          i = 0n;
        }
        lo += i;
        hi += j;
      }
    }
    this.width = [minBig(lo, MAXWIDTH), minBig(hi, MAXWIDTH)];
    return this.width;
  }
}

class Tokenizer {
  readonly string: string[];
  index = 0;
  next: string | null = null;

  constructor(pattern: string) {
    this.string = codePoints(pattern);
    this.advance();
  }

  private advance(): void {
    const index = this.index;
    const char = this.string[index];
    if (char === undefined) {
      this.next = null;
      return;
    }
    if (char === BS) {
      const following = this.string[index + 1];
      if (following === undefined) throw new PyReError("bad escape (end of pattern)", this.string, this.string.length - 1);
      this.index = index + 2;
      this.next = char + following;
      return;
    }
    this.index = index + 1;
    this.next = char;
  }

  match(char: string): boolean {
    if (char === this.next) {
      this.advance();
      return true;
    }
    return false;
  }

  get(): string | null {
    const current = this.next;
    this.advance();
    return current;
  }

  getwhile(n: number, charset: ReadonlySet<string>): string {
    let result = "";
    for (let count = 0; count < n; count += 1) {
      const c = this.next;
      if (c === null || !charset.has(c)) break;
      result += c;
      this.advance();
    }
    return result;
  }

  getuntil(terminator: string, name: string): string {
    let result = "";
    for (;;) {
      const c = this.next;
      this.advance();
      if (c === null) {
        if (!result) throw this.error(`missing ${name}`);
        throw this.error(`missing ${terminator}, unterminated name`, cpLen(result));
      }
      if (c === terminator) {
        if (!result) throw this.error(`missing ${name}`, 1);
        break;
      }
      result += c;
    }
    return result;
  }

  tell(): number {
    return this.index - (this.next === null ? 0 : cpLen(this.next));
  }

  seek(index: number): void {
    this.index = index;
    this.advance();
  }

  error(msg: string, offset = 0): PyReError {
    return new PyReError(msg, this.string, this.tell() - offset);
  }

  checkgroupname(name: string, offset: number): void {
    if (!isIdentifier(name)) throw this.error(`bad character in group name ${pyRepr(name)}`, cpLen(name) + offset);
  }
}

/** int(text, 16) 再 chr()：超出码点范围时 Python 抛 ValueError（落到“bad escape”）。 */
function hexCode(text: string): number {
  return Number.parseInt(text, 16);
}

/** 字符类里的转义（_class_escape）。 */
function classEscape(source: Tokenizer, escapeIn: string): Item {
  let escape = escapeIn;
  const code = ESCAPES[escape];
  if (code) return code;
  const category = CATEGORIES[escape];
  if (category && category.op === "IN") return category;
  const c = codePoints(escape)[1] ?? "";
  bad: {
    if (c === "x") {
      escape += source.getwhile(2, HEXDIGITS);
      if (cpLen(escape) !== 4) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: hexCode(escape.slice(2)) };
    }
    if (c === "u") {
      escape += source.getwhile(4, HEXDIGITS);
      if (cpLen(escape) !== 6) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: hexCode(escape.slice(2)) };
    }
    if (c === "U") {
      escape += source.getwhile(8, HEXDIGITS);
      if (cpLen(escape) !== 10) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      const value = hexCode(escape.slice(2));
      if (value > 0x10ffff) break bad; // chr() 抛 ValueError
      return { op: "LITERAL", av: value };
    }
    if (c === "N") {
      return { op: "LITERAL", av: namedEscape(source) };
    }
    if (OCTDIGITS.has(c)) {
      escape += source.getwhile(2, OCTDIGITS);
      const value = Number.parseInt(escape.slice(1), 8);
      if (value > 0o377) throw source.error(`octal escape value ${escape} outside of range 0-0o377`, cpLen(escape));
      return { op: "LITERAL", av: value };
    }
    if (DIGITS.has(c)) break bad;
    if (cpLen(escape) === 2) {
      if (ASCIILETTERS.has(c)) throw source.error(`bad escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: ord(c) };
    }
  }
  throw source.error(`bad escape ${escape}`, cpLen(escape));
}

/** \N{name}。 */
function namedEscape(source: Tokenizer): number {
  if (!source.match("{")) throw source.error("missing {");
  const charname = source.getuntil("}", "character name");
  const value = lookupName(charname);
  if (value === null) throw source.error(`undefined character name ${pyRepr(charname)}`, cpLen(charname) + 4);
  return value;
}

/** 字符类之外的转义（_escape）。 */
function escapeItem(source: Tokenizer, escapeIn: string, state: State): Item {
  let escape = escapeIn;
  const category = CATEGORIES[escape];
  if (category) return category;
  const code = ESCAPES[escape];
  if (code) return code;
  const c = codePoints(escape)[1] ?? "";
  bad: {
    if (c === "x") {
      escape += source.getwhile(2, HEXDIGITS);
      if (cpLen(escape) !== 4) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: hexCode(escape.slice(2)) };
    }
    if (c === "u") {
      escape += source.getwhile(4, HEXDIGITS);
      if (cpLen(escape) !== 6) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: hexCode(escape.slice(2)) };
    }
    if (c === "U") {
      escape += source.getwhile(8, HEXDIGITS);
      if (cpLen(escape) !== 10) throw source.error(`incomplete escape ${escape}`, cpLen(escape));
      const value = hexCode(escape.slice(2));
      if (value > 0x10ffff) break bad;
      return { op: "LITERAL", av: value };
    }
    if (c === "N") {
      return { op: "LITERAL", av: namedEscape(source) };
    }
    if (c === "0") {
      escape += source.getwhile(2, OCTDIGITS);
      return { op: "LITERAL", av: Number.parseInt(escape.slice(1), 8) };
    }
    if (DIGITS.has(c)) {
      // 八进制转义，或者十进制的组引用
      if (source.next !== null && DIGITS.has(source.next)) {
        escape += source.get() as string;
        const chars = codePoints(escape);
        if (OCTDIGITS.has(chars[1] as string) && OCTDIGITS.has(chars[2] as string) && source.next !== null && OCTDIGITS.has(source.next)) {
          escape += source.get() as string;
          const value = Number.parseInt(escape.slice(1), 8);
          if (value > 0o377) throw source.error(`octal escape value ${escape} outside of range 0-0o377`, cpLen(escape));
          return { op: "LITERAL", av: value };
        }
      }
      const group = Number.parseInt(escape.slice(1), 10);
      if (group < state.groups) {
        if (!state.checkgroup(group)) throw source.error("cannot refer to an open group", cpLen(escape));
        state.checklookbehindgroup(group, source);
        return { op: "GROUPREF", av: group };
      }
      throw source.error(`invalid group reference ${group}`, cpLen(escape) - 1);
    }
    if (cpLen(escape) === 2) {
      if (ASCIILETTERS.has(c)) throw source.error(`bad escape ${escape}`, cpLen(escape));
      return { op: "LITERAL", av: ord(c) };
    }
  }
  throw source.error(`bad escape ${escape}`, cpLen(escape));
}

/** 两项（op, av）按值相等；SubPattern 按身份（Python 的元组比较里 SubPattern 没有 __eq__）。 */
function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a instanceof SubPattern || b instanceof SubPattern) return false;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((value, index) => same(value, b[index]));
  if (a !== null && b !== null && typeof a === "object" && typeof b === "object") {
    const left = a as { op: unknown; av: unknown };
    const right = b as { op: unknown; av: unknown };
    return left.op === right.op && same(left.av, right.av);
  }
  return false;
}

const setKey = (item: SetItem): string => `${item.op}:${JSON.stringify(item.av)}`;

/** _uniq：去重，保留第一次出现的次序。 */
function uniq(items: readonly SetItem[]): SetItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = setKey(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function parseSub(source: Tokenizer, state: State, verboseIn: boolean, nested: number): SubPattern {
  let verbose = verboseIn;
  const items: SubPattern[] = [];
  for (;;) {
    items.push(parse_(source, state, verbose, nested + 1, !nested && items.length === 0));
    if (!source.match("|")) break;
    if (!nested) verbose = (state.flags & FLAG_VERBOSE) !== 0;
  }
  if (items.length === 1) return items[0] as SubPattern;
  const subpattern = new SubPattern(state);
  // 各分支有共同的前缀：提到分支外面
  for (;;) {
    let prefix: Item | null = null;
    let common = true;
    for (const item of items) {
      if (item.data.length === 0) {
        common = false;
        break;
      }
      if (prefix === null) prefix = item.data[0] as Item;
      else if (!same(item.data[0], prefix)) {
        common = false;
        break;
      }
    }
    if (!common || prefix === null) break;
    for (const item of items) item.data.splice(0, 1);
    subpattern.data.push(prefix);
  }
  // 每个分支都是单个字符：并成一个字符集
  const set: SetItem[] = [];
  let allSingle = true;
  for (const item of items) {
    if (item.data.length !== 1) {
      allSingle = false;
      break;
    }
    const only = item.data[0] as Item;
    if (only.op === "LITERAL") set.push({ op: "LITERAL", av: only.av });
    else if (only.op === "IN" && only.av[0]?.op !== "NEGATE") set.push(...only.av);
    else {
      allSingle = false;
      break;
    }
  }
  if (allSingle) {
    subpattern.data.push({ op: "IN", av: uniq(set) });
    return subpattern;
  }
  subpattern.data.push({ op: "BRANCH", av: [null, items] });
  return subpattern;
}

function parseFlags(source: Tokenizer, state: State, charIn: string): [number, number] | null {
  let char: string | null = charIn;
  let addFlags = 0;
  let delFlags = 0;
  if (char !== "-") {
    for (;;) {
      const flag = FLAGS[char as string] as number;
      if (char === "L") throw source.error("bad inline flags: cannot use 'L' flag with a str pattern");
      addFlags |= flag;
      if ((flag & TYPE_FLAGS) && (addFlags & TYPE_FLAGS) !== flag) {
        throw source.error("bad inline flags: flags 'a', 'u' and 'L' are incompatible");
      }
      char = source.get();
      if (char === null) throw source.error("missing -, : or )");
      if (char === ")" || char === "-" || char === ":") break;
      if (!Object.hasOwn(FLAGS, char)) {
        throw source.error(isAlpha(char) ? "unknown flag" : "missing -, : or )", cpLen(char));
      }
    }
  }
  if (char === ")") {
    state.flags |= addFlags;
    return null;
  }
  if (addFlags & GLOBAL_FLAGS) throw source.error("bad inline flags: cannot turn on global flag", 1);
  if (char === "-") {
    char = source.get();
    if (char === null) throw source.error("missing flag");
    if (!Object.hasOwn(FLAGS, char)) throw source.error(isAlpha(char) ? "unknown flag" : "missing flag", cpLen(char));
    for (;;) {
      const flag = FLAGS[char as string] as number;
      if (flag & TYPE_FLAGS) throw source.error("bad inline flags: cannot turn off flags 'a', 'u' and 'L'");
      delFlags |= flag;
      char = source.get();
      if (char === null) throw source.error("missing :");
      if (char === ":") break;
      if (!Object.hasOwn(FLAGS, char)) throw source.error(isAlpha(char) ? "unknown flag" : "missing :", cpLen(char));
    }
  }
  if (delFlags & GLOBAL_FLAGS) throw source.error("bad inline flags: cannot turn off global flag", 1);
  if (addFlags & delFlags) throw source.error("bad inline flags: flag turned on and off", 1);
  return [addFlags, delFlags];
}

function parse_(source: Tokenizer, state: State, verboseIn: boolean, nested: number, first = false): SubPattern {
  let verbose = verboseIn;
  const subpattern = new SubPattern(state);
  for (;;) {
    let current: string | null = source.next;
    if (current === null) break;
    if (current === "|" || current === ")") break;
    source.get();

    if (verbose) {
      if (WHITESPACE.has(current)) continue;
      if (current === "#") {
        for (;;) {
          current = source.get();
          if (current === null || current === NL) break;
        }
        continue;
      }
    }

    if (current.startsWith(BS)) {
      subpattern.data.push(escapeItem(source, current, state));
    } else if (!SPECIAL_CHARS.includes(current)) {
      subpattern.data.push({ op: "LITERAL", av: ord(current) });
    } else if (current === "[") {
      const here = source.tell() - 1;
      let set: SetItem[] = [];
      const negate = source.match("^");
      for (;;) {
        const thisOne = source.get();
        if (thisOne === null) throw source.error("unterminated character set", source.tell() - here);
        if (thisOne === "]" && set.length > 0) break;
        let code1: Item | SetItem;
        if (thisOne.startsWith(BS)) code1 = classEscape(source, thisOne);
        else code1 = { op: "LITERAL", av: ord(thisOne) };
        if (source.match("-")) {
          const that = source.get();
          if (that === null) throw source.error("unterminated character set", source.tell() - here);
          if (that === "]") {
            if (code1.op === "IN") code1 = (code1.av as readonly SetItem[])[0] as SetItem;
            set.push(code1 as SetItem);
            set.push({ op: "LITERAL", av: 45 });
            break;
          }
          const code2: Item = that.startsWith(BS) ? classEscape(source, that) : { op: "LITERAL", av: ord(that) };
          if (code1.op !== "LITERAL" || code2.op !== "LITERAL") {
            throw source.error(`bad character range ${thisOne}-${that}`, cpLen(thisOne) + 1 + cpLen(that));
          }
          const lo = code1.av as number;
          const hi = code2.av as number;
          if (hi < lo) throw source.error(`bad character range ${thisOne}-${that}`, cpLen(thisOne) + 1 + cpLen(that));
          set.push({ op: "RANGE", av: [lo, hi] });
        } else {
          if (code1.op === "IN") code1 = (code1.av as readonly SetItem[])[0] as SetItem;
          set.push(code1 as SetItem);
        }
      }
      set = uniq(set);
      if (set.length === 1 && set[0]?.op === "LITERAL") {
        subpattern.data.push(negate ? { op: "NOT_LITERAL", av: set[0].av } : { op: "LITERAL", av: set[0].av });
      } else {
        if (negate) set.unshift({ op: "NEGATE", av: null });
        subpattern.data.push({ op: "IN", av: set });
      }
    } else if (REPEAT_CHARS.includes(current)) {
      const here = source.tell();
      let min: bigint;
      let max: bigint;
      if (current === "?") [min, max] = [0n, 1n];
      else if (current === "*") [min, max] = [0n, MAXREPEAT];
      else if (current === "+") [min, max] = [1n, MAXREPEAT];
      else {
        if (source.next === "}") {
          subpattern.data.push({ op: "LITERAL", av: ord(current) });
          continue;
        }
        [min, max] = [0n, MAXREPEAT];
        let lo = "";
        let hi = "";
        while (source.next !== null && DIGITS.has(source.next)) lo += source.get() as string;
        if (source.match(",")) {
          while (source.next !== null && DIGITS.has(source.next)) hi += source.get() as string;
        } else {
          hi = lo;
        }
        if (!source.match("}")) {
          subpattern.data.push({ op: "LITERAL", av: ord(current) });
          source.seek(here);
          continue;
        }
        if (lo) {
          min = BigInt(lo);
          if (min >= MAXREPEAT) throw new PyOverflowError("the repetition number is too large");
        }
        if (hi) {
          max = BigInt(hi);
          if (max >= MAXREPEAT) throw new PyOverflowError("the repetition number is too large");
          if (max < min) throw source.error("min repeat greater than max repeat", source.tell() - here);
        }
      }
      const last = subpattern.data[subpattern.data.length - 1];
      if (last === undefined || last.op === "AT") throw source.error("nothing to repeat", source.tell() - here + cpLen(current));
      if (REPEAT_OPS.has(last.op)) throw source.error("multiple repeat", source.tell() - here + cpLen(current));
      let item = new SubPattern(state, [last]);
      if (last.op === "SUBPATTERN") {
        const [group, addFlags, delFlags, p] = last.av;
        if (group === null && !addFlags && !delFlags) item = p;
      }
      const op: RepeatOp = source.match("?") ? "MIN_REPEAT" : source.match("+") ? "POSSESSIVE_REPEAT" : "MAX_REPEAT";
      subpattern.data[subpattern.data.length - 1] = { op, av: [min, max, item] };
    } else if (current === ".") {
      subpattern.data.push({ op: "ANY", av: null });
    } else if (current === "(") {
      const start = source.tell() - 1;
      let capture = true;
      let atomic = false;
      let name: string | null = null;
      let addFlags = 0;
      let delFlags = 0;
      if (source.match("?")) {
        let char = source.get();
        if (char === null) throw source.error("unexpected end of pattern");
        if (char === "P") {
          if (source.match("<")) {
            name = source.getuntil(">", "group name");
            source.checkgroupname(name, 1);
          } else if (source.match("=")) {
            name = source.getuntil(")", "group name");
            source.checkgroupname(name, 1);
            const gid = state.groupdict.get(name);
            if (gid === undefined) throw source.error(`unknown group name ${pyRepr(name)}`, cpLen(name) + 1);
            if (!state.checkgroup(gid)) throw source.error("cannot refer to an open group", cpLen(name) + 1);
            state.checklookbehindgroup(gid, source);
            subpattern.data.push({ op: "GROUPREF", av: gid });
            continue;
          } else {
            char = source.get();
            if (char === null) throw source.error("unexpected end of pattern");
            throw source.error(`unknown extension ?P${char}`, cpLen(char) + 2);
          }
        } else if (char === ":") {
          capture = false;
        } else if (char === "#") {
          for (;;) {
            if (source.next === null) throw source.error("missing ), unterminated comment", source.tell() - start);
            if (source.get() === ")") break;
          }
          continue;
        } else if (char === "=" || char === "!" || char === "<") {
          let dir = 1;
          let lookbehindgroups: number | null = null;
          if (char === "<") {
            char = source.get();
            if (char === null) throw source.error("unexpected end of pattern");
            if (char !== "=" && char !== "!") throw source.error(`unknown extension ?<${char}`, cpLen(char) + 2);
            dir = -1;
            lookbehindgroups = state.lookbehindgroups;
            if (lookbehindgroups === null) state.lookbehindgroups = state.groups;
          }
          const p = parseSub(source, state, verbose, nested + 1);
          if (dir < 0 && lookbehindgroups === null) state.lookbehindgroups = null;
          if (!source.match(")")) throw source.error("missing ), unterminated subpattern", source.tell() - start);
          subpattern.data.push({ op: char === "=" ? "ASSERT" : "ASSERT_NOT", av: [dir, p] });
          continue;
        } else if (char === "(") {
          const condname = source.getuntil(")", "group name");
          let condgroup: number;
          if (!isAsciiDecimal(condname)) {
            source.checkgroupname(condname, 1);
            const gid = state.groupdict.get(condname);
            if (gid === undefined) throw source.error(`unknown group name ${pyRepr(condname)}`, cpLen(condname) + 1);
            condgroup = gid;
          } else {
            const value = BigInt(condname);
            if (!value) throw source.error("bad group number", cpLen(condname) + 1);
            if (value >= BigInt(MAXGROUPS)) throw source.error(`invalid group reference ${value}`, cpLen(condname) + 1);
            condgroup = Number(value);
            if (!state.grouprefpos.has(condgroup)) state.grouprefpos.set(condgroup, source.tell() - cpLen(condname) - 1);
          }
          state.checklookbehindgroup(condgroup, source);
          const itemYes = parse_(source, state, verbose, nested + 1);
          let itemNo: SubPattern | null = null;
          if (source.match("|")) {
            itemNo = parse_(source, state, verbose, nested + 1);
            if (source.next === "|") throw source.error("conditional backref with more than two branches");
          }
          if (!source.match(")")) throw source.error("missing ), unterminated subpattern", source.tell() - start);
          subpattern.data.push({ op: "GROUPREF_EXISTS", av: [condgroup, itemYes, itemNo] });
          continue;
        } else if (char === ">") {
          capture = false;
          atomic = true;
        } else if (Object.hasOwn(FLAGS, char) || char === "-") {
          const flags = parseFlags(source, state, char);
          if (flags === null) {
            if (!first || subpattern.data.length > 0) {
              throw source.error("global flags not at the start of the expression", source.tell() - start);
            }
            verbose = (state.flags & FLAG_VERBOSE) !== 0;
            continue;
          }
          [addFlags, delFlags] = flags;
          capture = false;
        } else {
          throw source.error(`unknown extension ?${char}`, cpLen(char) + 1);
        }
      }
      let group: number | null = null;
      if (capture) {
        try {
          group = state.opengroup(name);
        } catch (error) {
          if (error instanceof PyReError) throw source.error(error.msg, cpLen(name ?? "") + 1);
          throw error;
        }
      }
      const subVerbose = (verbose || (addFlags & FLAG_VERBOSE) !== 0) && !(delFlags & FLAG_VERBOSE);
      const p = parseSub(source, state, subVerbose, nested + 1);
      if (!source.match(")")) throw source.error("missing ), unterminated subpattern", source.tell() - start);
      if (group !== null) state.closegroup(group, p);
      if (atomic) subpattern.data.push({ op: "ATOMIC_GROUP", av: p });
      else subpattern.data.push({ op: "SUBPATTERN", av: [group, addFlags, delFlags, p] });
    } else if (current === "^") {
      subpattern.data.push({ op: "AT", av: "BEGINNING" });
    } else if (current === "$") {
      subpattern.data.push({ op: "AT", av: "END" });
    }
  }
  // 拆开不带标志的非捕获组
  for (let index = subpattern.data.length - 1; index >= 0; index -= 1) {
    const item = subpattern.data[index] as Item;
    if (item.op === "SUBPATTERN") {
      const [group, addFlags, delFlags, p] = item.av;
      if (group === null && !addFlags && !delFlags) subpattern.data.splice(index, 1, ...p.data);
    }
  }
  return subpattern;
}

/** fix_flags（str 模式）。 */
function fixFlags(flags: number): number {
  if (flags & FLAG_LOCALE) throw new PyValueError("cannot use LOCALE flag with a str pattern");
  if (!(flags & FLAG_ASCII)) return flags | FLAG_UNICODE;
  if (flags & FLAG_UNICODE) throw new PyValueError("ASCII and UNICODE flags are incompatible");
  return flags;
}

/** re._parser.parse(pattern)（flags=0）。 */
export function parse(pattern: string): SubPattern {
  const source = new Tokenizer(pattern);
  const state = new State();
  const p = parseSub(source, state, false, 0);
  state.flags = fixFlags(state.flags);
  if (source.next !== null) throw source.error("unbalanced parenthesis");
  for (const [group, pos] of state.grouprefpos) {
    if (group >= state.groups) throw new PyReError(`invalid group reference ${group}`, source.string, pos);
  }
  return p;
}
