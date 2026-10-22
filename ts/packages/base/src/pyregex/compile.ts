// Python re 的编译（迁移第 ②b2 步，logs search 用）：语法树（parser.ts）编成 sre 的字节码，由 engine.ts 照
// sre_lib.h 的 SRE(match)/SRE(search) 执行。不用 JS 正则：JavaScriptCore（Bun）在前瞻里遇到 ^ 会回溯进去，原子组的
// 模拟也与 sre 的“每轮取第一个匹配、空轮即停”不同（实测见 r3 §10 第 ②b2 步）。
//
// 单个字符的匹配器（字面量、字符集、任意字符、类别）照 sre 运行时的判定，算成一个显式的码点集合：
//   - IGNORECASE（Unicode）：字面量 c 有大小写时，匹配“小写等于 lower(c)”的字符，lower(c) 在 _casefix 里时还认
//     那几个额外的；字符集照 _compiler._optimize_charset 把成员小写化（加 _casefix 的），BMP 以外的范围记成
//     RANGE_UNI_IGNORE（x 或 upper(x) 落在范围里都算），匹配时先取 lower(ch) 再查。集合里没有有大小写的成员时不小写化。
//   - IGNORECASE 加 ASCII：只在 ASCII 字母之间折叠。
//   - 大小写用 Python 的简单映射（tables.ts，Unicode 15.0），不用 JS 的 toLowerCase（ICU 的 Unicode 17.0）。
// 编译期的报错照 _compiler._compile 的遍历次序：模板标志下的重复、后顾回看太远、后顾不定宽。
import { DIGIT, SPACE, WORD } from "../pyunicode.ts";
import {
  FLAG_DOTALL,
  FLAG_IGNORECASE,
  FLAG_MULTILINE,
  FLAG_TEMPLATE,
  FLAG_UNICODE,
  type AtCode,
  type Category,
  type Item,
  PyReError,
  type RepeatOp,
  type SetItem,
  type SubPattern,
  TYPE_FLAGS,
} from "./parser.ts";
import { EXTRA_CASES, LOWER, UPPER } from "./tables.ts";

export const MAX_CP = 0x10ffff;
const MAXCODE = 4294967295n;

// --- 码点区间集：按起点排序、互不相交的 [lo, hi] ------------------------------------------------

type Ranges = readonly (readonly [number, number])[];

function normalize(spans: (readonly [number, number])[]): Ranges {
  const sorted = [...spans].sort((a, b) => a[0] - b[0]);
  const out: [number, number][] = [];
  for (const [lo, hi] of sorted) {
    const last = out[out.length - 1];
    if (last && lo <= last[1] + 1) last[1] = Math.max(last[1], hi);
    else out.push([lo, hi]);
  }
  return out;
}

const fromPoints = (points: Iterable<number>): Ranges => normalize([...points].map((cp) => [cp, cp] as const));
const fromTable = (table: readonly number[]): Ranges => {
  const out: [number, number][] = [];
  for (let index = 0; index < table.length; index += 2) out.push([table[index] as number, table[index + 1] as number]);
  return out;
};

function complement(set: Ranges): Ranges {
  const out: [number, number][] = [];
  let next = 0;
  for (const [lo, hi] of set) {
    if (lo > next) out.push([next, lo - 1]);
    next = hi + 1;
  }
  if (next <= MAX_CP) out.push([next, MAX_CP]);
  return out;
}

function contains(set: Ranges, cp: number): boolean {
  let low = 0;
  let high = set.length - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const [lo, hi] = set[mid] as readonly [number, number];
    if (cp < lo) high = mid - 1;
    else if (cp > hi) low = mid + 1;
    else return true;
  }
  return false;
}

/** 去掉若干码点，再加上若干码点。 */
function adjust(set: Ranges, remove: Iterable<number>, add: Iterable<number>): Ranges {
  const drop = fromPoints(remove);
  const kept = complement(normalize([...complement(set), ...drop]));
  return normalize([...kept, ...fromPoints(add)]);
}

// --- 大小写（sre 的 unicode_tolower、Py_UNICODE_TOUPPER、ascii 版） -----------------------------

function pairMap(pairs: readonly number[]): Map<number, number> {
  const map = new Map<number, number>();
  for (let index = 0; index < pairs.length; index += 2) map.set(pairs[index] as number, pairs[index + 1] as number);
  return map;
}

const LOWER_MAP = pairMap(LOWER);
const UPPER_MAP = pairMap(UPPER);
const LOWER_KEYS = [...LOWER_MAP.keys()];
const UPPER_KEYS = [...UPPER_MAP.keys()];

const uniLower = (cp: number): number => LOWER_MAP.get(cp) ?? cp;
const uniUpper = (cp: number): number => UPPER_MAP.get(cp) ?? cp;
const uniCased = (cp: number): boolean => LOWER_MAP.has(cp) || UPPER_MAP.has(cp);
const asciiLower = (cp: number): number => (cp >= 0x41 && cp <= 0x5a ? cp + 32 : cp);
const asciiCased = (cp: number): boolean => (cp >= 0x41 && cp <= 0x5a) || (cp >= 0x61 && cp <= 0x7a);

interface CaseRules {
  readonly iscased: (cp: number) => boolean;
  readonly tolower: (cp: number) => number;
  readonly fixes: ReadonlyMap<number, readonly number[]> | null;
  readonly unicode: boolean;
}

function caseRules(flags: number): CaseRules | null {
  if (!(flags & FLAG_IGNORECASE)) return null;
  if (flags & FLAG_UNICODE) return { iscased: uniCased, tolower: uniLower, fixes: EXTRA_CASES, unicode: true };
  return { iscased: asciiCased, tolower: asciiLower, fixes: null, unicode: false };
}

/** 匹配时先对目标字符取小写再查 S 的那些字符：(S 去掉小写会变的) ∪ {小写会变、且小写落在 S 里的}。 */
function lowered(set: Ranges, rules: CaseRules): Ranges {
  if (rules.unicode) {
    return adjust(set, LOWER_KEYS, LOWER_KEYS.filter((cp) => contains(set, uniLower(cp))));
  }
  const upper = Array.from({ length: 26 }, (_, index) => 0x41 + index);
  return adjust(set, upper, upper.filter((cp) => contains(set, cp + 32)));
}

// --- 类别 -------------------------------------------------------------------------------------

const ASCII_DIGIT: Ranges = [[0x30, 0x39]];
const ASCII_SPACE: Ranges = [[0x09, 0x0d], [0x20, 0x20]];
const ASCII_WORD: Ranges = [[0x30, 0x39], [0x41, 0x5a], [0x5f, 0x5f], [0x61, 0x7a]];
const UNI_DIGIT = fromTable(DIGIT);
const UNI_SPACE = fromTable(SPACE);
const UNI_WORD = fromTable(WORD);

function categorySet(category: Category, flags: number): Ranges {
  const unicode = (flags & FLAG_UNICODE) !== 0;
  const base = category.endsWith("DIGIT") ? (unicode ? UNI_DIGIT : ASCII_DIGIT)
    : category.endsWith("SPACE") ? (unicode ? UNI_SPACE : ASCII_SPACE)
      : unicode ? UNI_WORD : ASCII_WORD;
  return category.startsWith("NOT_") ? complement(base) : base;
}

// --- 单个字符的匹配器 ---------------------------------------------------------------------------

/** LITERAL / NOT_LITERAL（_compile 的 LITERAL_CODES 分支）。 */
function literalSet(cp: number, negate: boolean, flags: number): Ranges {
  const rules = caseRules(flags);
  let set: Ranges;
  if (rules === null || !rules.iscased(cp)) {
    set = [[cp, cp]];
  } else {
    const lo = rules.tolower(cp);
    const targets = [lo, ...(rules.fixes?.get(lo) ?? [])];
    set = lowered(fromPoints(targets), rules);
  }
  return negate ? complement(set) : set;
}

/** IN（_optimize_charset 加 sre 的 charset 判定）。 */
function inSet(items: readonly SetItem[], flags: number): Ranges {
  const rules = caseRules(flags);
  const fixup = rules?.tolower ?? null;
  const fixes = rules?.fixes ?? null;
  let mapSize = 256;
  const charmap = new Set<number>();
  const tail: (SetItem | { op: "RANGE_UNI_IGNORE"; av: readonly [number, number] })[] = [];
  let negate = false;
  let hascased = false;
  const mark = (cp: number): boolean => {
    if (cp >= mapSize) {
      if (mapSize === 256) {
        mapSize = 65536;
        return false; // Python 把 charmap 扩到 65536 之后，从这一项的开头重来
      }
      throw new RangeError("non-BMP");
    }
    charmap.add(cp);
    return true;
  };
  for (const item of items) {
    for (;;) {
      try {
        if (item.op === "LITERAL") {
          if (fixup) {
            const av = fixup(item.av);
            // 额外等价也可能超过 255（例如 k 的开尔文符号 K）：Python 扩表之后从这一项的开头重来
            if (!mark(av) || !(fixes?.get(av) ?? []).every(mark)) continue;
            if (!hascased && rules?.iscased(av)) hascased = true;
          } else if (!mark(item.av)) continue;
        } else if (item.op === "RANGE") {
          const [lo, hi] = item.av;
          let restart = false;
          for (let cp = lo; cp <= hi && !restart; cp += 1) {
            const value = fixup ? fixup(cp) : cp;
            if (!mark(value) || (fixup !== null && fixes !== null && !(fixes.get(value) ?? []).every(mark))) restart = true;
          }
          if (restart) continue;
          if (fixup && !hascased) {
            for (let cp = lo; cp <= hi; cp += 1) {
              if (rules?.iscased(cp)) {
                hascased = true;
                break;
              }
            }
          }
        } else if (item.op === "NEGATE") {
          negate = true;
        } else {
          tail.push(item);
        }
      } catch (error) {
        if (!(error instanceof RangeError)) throw error;
        // 字符集里有 BMP 以外的码点（范围的 BMP 部分已经记进 charmap）
        if (fixup) {
          if (item.op === "RANGE") {
            hascased = true;
            tail.push(fixes ? { op: "RANGE_UNI_IGNORE", av: item.av } : item);
            break;
          }
          const av = fixup((item as { av: number }).av);
          if (!hascased && rules?.iscased(av)) hascased = true;
          tail.push({ op: "LITERAL", av });
          break;
        }
        tail.push(item);
      }
      break;
    }
  }
  // 集合本身（charset 判定为真的 x）
  const spans: (readonly [number, number])[] = [...fromPoints(charmap)];
  for (const item of tail) {
    if (item.op === "LITERAL") spans.push([item.av, item.av]);
    else if (item.op === "RANGE") spans.push(item.av);
    else if (item.op === "CATEGORY") spans.push(...categorySet(item.av, flags));
    else if (item.op === "RANGE_UNI_IGNORE") {
      const [lo, hi] = item.av;
      spans.push(item.av);
      for (const cp of UPPER_KEYS) {
        const up = uniUpper(cp);
        if (up >= lo && up <= hi) spans.push([cp, cp]);
      }
    }
  }
  let set = normalize(spans);
  if (negate) set = complement(set);
  if (rules === null || !hascased) return set; // IN：不小写化
  return lowered(set, rules); // IN_IGNORE / IN_UNI_IGNORE
}

// --- 字节码（_compiler._compile 的移植） --------------------------------------------------------
// 布局与 sre 一致（跳转偏移、SUCCESS 的位置都照搬），只有两处不同：单个字符的匹配器一律编成 CHAR <集合编号>
// （集合即上面算出的判定结果，与 LITERAL/IN/ANY 及各自的 IGNORE 变体逐字符等价）；不发 MARK（没有反向引用，
// 捕获的位置不影响有没有匹配）。

export const Op = {
  FAILURE: 0, // BRANCH 的结束标记靠它是 0
  SUCCESS: 1,
  CHAR: 2,
  AT: 3,
  BRANCH: 4,
  JUMP: 5,
  REPEAT_ONE: 6,
  MIN_REPEAT_ONE: 7,
  POSSESSIVE_REPEAT_ONE: 8,
  REPEAT: 9,
  MAX_UNTIL: 10,
  MIN_UNTIL: 11,
  POSSESSIVE_REPEAT: 12,
  ATOMIC_GROUP: 13,
  ASSERT: 14,
  ASSERT_NOT: 15,
} as const;
export type Op = (typeof Op)[keyof typeof Op];

export const At = {
  BEGINNING: 0,
  BEGINNING_LINE: 1,
  BEGINNING_STRING: 2,
  BOUNDARY: 3,
  NON_BOUNDARY: 4,
  END: 5,
  END_LINE: 6,
  END_STRING: 7,
  UNI_BOUNDARY: 8,
  UNI_NON_BOUNDARY: 9,
} as const;
export type At = (typeof At)[keyof typeof At];

/** 码点区间集压平成 [lo0, hi0, lo1, hi1, …]，匹配时二分查找。 */
export type FlatSet = Int32Array;

export interface Program {
  readonly code: readonly number[];
  readonly sets: readonly FlatSet[];
  /** 信息块的最小宽度（上限 MAXCODE）；0 表示没有前缀与字符集信息。 */
  readonly minWidth: number;
  /** 字面量前缀（_get_literal_prefix）：只在这些码点开头的位置尝试。 */
  readonly prefix: readonly number[];
  /** 字符集前缀（_get_charset_prefix，按整个模式的标志编译）：起点字符要在其中。 */
  readonly charset: FlatSet | null;
  /** 字节码开头（跳过零宽的 AT）第一个字符要落在其中的集合：只用来少试注定失败的起点，不改变结果。 */
  readonly leading: FlatSet | null;
}

const flatten = (set: Ranges): FlatSet => Int32Array.from(set.flat());

export function flatContains(set: FlatSet, cp: number): boolean {
  const size = set.length;
  if (size <= 8) {
    // 段数少时顺序比较
    for (let index = 0; index < size; index += 2) {
      if (cp < (set[index] as number)) return false;
      if (cp <= (set[index + 1] as number)) return true;
    }
    return false;
  }
  let low = 0;
  let high = (set.length >> 1) - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (cp < (set[2 * mid] as number)) high = mid - 1;
    else if (cp > (set[2 * mid + 1] as number)) low = mid + 1;
    else return true;
  }
  return false;
}

const NOT_NEWLINE = complement([[10, 10]]);
const EVERYTHING: Ranges = [[0, MAX_CP]];

/** _compiler._combine_flags。 */
function combineFlags(flags: number, addFlags: number, delFlags: number): number {
  const base = addFlags & TYPE_FLAGS ? flags & ~TYPE_FLAGS : flags;
  return (base | addFlags) & ~delFlags;
}

/** _compiler._simple。 */
function simple(pattern: SubPattern): boolean {
  if (pattern.data.length !== 1) return false;
  const item = pattern.data[0] as Item;
  if (item.op === "SUBPATTERN") return item.av[0] === null && simple(item.av[3]);
  return item.op === "LITERAL" || item.op === "NOT_LITERAL" || item.op === "ANY" || item.op === "IN";
}

function atCode(code: AtCode, flags: number): At {
  const multiline = (flags & FLAG_MULTILINE) !== 0;
  const unicode = (flags & FLAG_UNICODE) !== 0;
  switch (code) {
    case "BEGINNING":
      return multiline ? At.BEGINNING_LINE : At.BEGINNING;
    case "BEGINNING_STRING":
      return At.BEGINNING_STRING;
    case "END":
      return multiline ? At.END_LINE : At.END;
    case "END_STRING":
      return At.END_STRING;
    case "BOUNDARY":
      return unicode ? At.UNI_BOUNDARY : At.BOUNDARY;
    case "NON_BOUNDARY":
      return unicode ? At.UNI_NON_BOUNDARY : At.NON_BOUNDARY;
  }
}

const REPEAT_CODES: Readonly<Record<RepeatOp, readonly [Op, Op, Op]>> = {
  MIN_REPEAT: [Op.REPEAT, Op.MIN_UNTIL, Op.MIN_REPEAT_ONE],
  MAX_REPEAT: [Op.REPEAT, Op.MAX_UNTIL, Op.REPEAT_ONE],
  POSSESSIVE_REPEAT: [Op.POSSESSIVE_REPEAT, Op.SUCCESS, Op.POSSESSIVE_REPEAT_ONE],
};

class CodeGen {
  readonly code: number[] = [];
  readonly sets: FlatSet[] = [];
  private readonly setIndex = new Map<string, number>();

  private char(set: Ranges): void {
    const key = set.map(([lo, hi]) => `${lo}-${hi}`).join(",");
    let index = this.setIndex.get(key);
    if (index === undefined) {
      index = this.sets.length;
      this.sets.push(flatten(set));
      this.setIndex.set(key, index);
    }
    this.code.push(Op.CHAR, index);
  }

  compile(pattern: SubPattern, flags: number): void {
    const code = this.code;
    for (const item of pattern.data) {
      switch (item.op) {
        case "LITERAL":
        case "NOT_LITERAL":
          this.char(literalSet(item.av, item.op === "NOT_LITERAL", flags));
          break;
        case "IN":
          this.char(inSet(item.av, flags));
          break;
        case "ANY":
          this.char(flags & FLAG_DOTALL ? EVERYTHING : NOT_NEWLINE);
          break;
        case "MAX_REPEAT":
        case "MIN_REPEAT":
        case "POSSESSIVE_REPEAT": {
          if (flags & FLAG_TEMPLATE) throw new PyReError(`internal: unsupported template operator ${item.op}`); // %r 是常量名
          const [min, max, sub] = item.av;
          const [repeatOp, untilOp, oneOp] = REPEAT_CODES[item.op];
          const single = simple(sub);
          code.push(single ? oneOp : repeatOp);
          const skip = code.length;
          code.push(0, Number(min), Number(max));
          this.compile(sub, flags);
          if (single) {
            code.push(Op.SUCCESS);
            code[skip] = code.length - skip;
          } else {
            code[skip] = code.length - skip;
            code.push(untilOp);
          }
          break;
        }
        case "SUBPATTERN": {
          const [, addFlags, delFlags, sub] = item.av;
          this.compile(sub, combineFlags(flags, addFlags, delFlags));
          break;
        }
        case "ATOMIC_GROUP": {
          code.push(Op.ATOMIC_GROUP);
          const skip = code.length;
          code.push(0);
          this.compile(item.av, flags);
          code.push(Op.SUCCESS);
          code[skip] = code.length - skip;
          break;
        }
        case "ASSERT":
        case "ASSERT_NOT": {
          const [dir, sub] = item.av;
          code.push(item.op === "ASSERT" ? Op.ASSERT : Op.ASSERT_NOT);
          const skip = code.length;
          code.push(0);
          if (dir >= 0) {
            code.push(0); // 前瞻
          } else {
            const [lo, hi] = sub.getwidth();
            if (lo > MAXCODE) throw new PyReError("looks too much behind");
            if (lo !== hi) throw new PyReError("look-behind requires fixed-width pattern");
            code.push(Number(lo)); // 后顾
          }
          this.compile(sub, flags);
          code.push(Op.SUCCESS);
          code[skip] = code.length - skip;
          break;
        }
        case "AT":
          code.push(Op.AT, atCode(item.av, flags));
          break;
        case "BRANCH": {
          code.push(Op.BRANCH);
          const tails: number[] = [];
          for (const sub of item.av[1]) {
            const skip = code.length;
            code.push(0);
            this.compile(sub, flags);
            code.push(Op.JUMP);
            tails.push(code.length);
            code.push(0);
            code[skip] = code.length - skip;
          }
          code.push(Op.FAILURE); // 分支结束
          for (const tail of tails) code[tail] = code.length - tail;
          break;
        }
        case "GROUPREF":
        case "GROUPREF_EXISTS":
          throw new Error("反向引用与条件分组在编译之前就该拒绝（kit_logs 第 58 轮）");
      }
    }
  }
}

// --- 信息块（_compiler._compile_info） ---------------------------------------------------------

/** _get_literal_prefix：(前缀, 是否整段都是字面量)。prefix_skip 只影响从哪一条指令接着匹配，不影响结果。 */
function literalPrefix(pattern: SubPattern, flags: number): [number[], boolean] {
  const iscased = caseRules(flags)?.iscased ?? null;
  const prefix: number[] = [];
  for (const item of pattern.data) {
    if (item.op === "LITERAL") {
      if (iscased?.(item.av)) return [prefix, false];
      prefix.push(item.av);
    } else if (item.op === "SUBPATTERN") {
      const [, addFlags, delFlags, sub] = item.av;
      const [inner, gotAll] = literalPrefix(sub, combineFlags(flags, addFlags, delFlags));
      prefix.push(...inner);
      if (!gotAll) return [prefix, false];
    } else {
      return [prefix, false];
    }
  }
  return [prefix, true];
}

/** _get_charset_prefix：起点字符的集合成员，或 null。 */
function charsetPrefix(patternIn: SubPattern, flagsIn: number): SetItem[] | null {
  let pattern = patternIn;
  let flags = flagsIn;
  for (;;) {
    const first = pattern.data[0];
    if (first === undefined) return null;
    if (first.op !== "SUBPATTERN") break;
    const [, addFlags, delFlags, sub] = first.av;
    pattern = sub;
    flags = combineFlags(flags, addFlags, delFlags);
  }
  const iscased = caseRules(flags)?.iscased ?? null;
  const first = pattern.data[0] as Item;
  if (first.op === "LITERAL") {
    if (iscased?.(first.av)) return null;
    return [{ op: "LITERAL", av: first.av }];
  }
  if (first.op === "BRANCH") {
    const charset: SetItem[] = [];
    for (const sub of first.av[1]) {
      const head = sub.data[0];
      if (head === undefined) return null;
      if (head.op === "LITERAL" && !iscased?.(head.av)) charset.push({ op: "LITERAL", av: head.av });
      else return null;
    }
    return charset;
  }
  if (first.op === "IN") {
    if (iscased) {
      for (const member of first.av) {
        if (member.op === "LITERAL" && iscased(member.av)) return null;
        if (member.op === "RANGE") {
          const [lo, hi] = member.av;
          if (hi > 0xffff) return null;
          for (let cp = lo; cp <= hi; cp += 1) if (iscased(cp)) return null;
        }
      }
    }
    return [...first.av];
  }
  return null;
}

/** _compiler._code：信息块加字节码，末尾一条 SUCCESS。flags 是 parse 之后的 state.flags。 */
export function compileProgram(pattern: SubPattern, flags: number): Program {
  let minWidth = 0;
  let prefix: number[] = [];
  let charset: FlatSet | null = null;
  const [lo] = pattern.getwidth();
  if (lo > 0n) {
    minWidth = Number(lo < MAXCODE ? lo : MAXCODE);
    prefix = literalPrefix(pattern, flags)[0];
    if (prefix.length === 0) {
      const items = charsetPrefix(pattern, flags);
      // 信息块里的字符集按原样判定（不小写化），类别按整个模式的 ASCII/Unicode——而不是开头那个组合并之后的
      // 标志：(?a:[^\w]) 的前缀按 Unicode 的 \w 判定，µ 不会被当成起点（CPython 3.12 的行为，照搬）
      if (items !== null) charset = flatten(inSet(items, flags & ~FLAG_IGNORECASE));
    }
  }
  const gen = new CodeGen();
  gen.compile(pattern, flags);
  gen.code.push(Op.SUCCESS);
  return { code: gen.code, sets: gen.sets, minWidth, prefix, charset, leading: leadingSet(gen.code, gen.sets) };
}

/** 开头的 CHAR，或至少重复一次的单字符重复（<op> <skip> <min> <max> CHAR <集合>）；前面的 AT 不占字符，跳过。 */
function leadingSet(code: readonly number[], sets: readonly FlatSet[]): FlatSet | null {
  let pc = 0;
  while (code[pc] === Op.AT) pc += 2;
  const op = code[pc];
  if (op === Op.CHAR) return sets[code[pc + 1] as number] as FlatSet;
  const repeatsOne = op === Op.REPEAT_ONE || op === Op.MIN_REPEAT_ONE || op === Op.POSSESSIVE_REPEAT_ONE;
  if (repeatsOne && (code[pc + 2] as number) >= 1) return sets[code[pc + 5] as number] as FlatSet;
  return null;
}

/** SRE_IS_WORD（ASCII）与 SRE_UNI_IS_WORD（\b、\B 用）。 */
export const WORD_SETS = { ascii: flatten(ASCII_WORD), unicode: flatten(UNI_WORD) } as const;
