// Python 内置函数在 JSON 值上的语义：repr、str、真值、len，以及 print 写 stdout 的字节（迁移第 ② 步）。
// 证据文件里的值来自 json.loads，类型只有 None、bool、int、float、str、list、dict（pyjson 的 PyValue）。
// 不是这些类型能回答的（例如对 int 取 len、对 list 取 .get），Python 会抛异常、打印堆栈；这里抛 PyCrash，
// 由入口按“崩溃”处理（退出码 1，stderr 不逐字比较，见契约）。
import { writeSync } from "node:fs";
import { type PyDict, type PyKey, type PyValue, floatRepr, intRepr } from "./pyjson.ts";
import { codePoints, isDigitChar, isSpace, pyIntParse, pyIsPrintable } from "./pyre.ts";

/** Python 运行时异常（AttributeError、TypeError、KeyError…）：照 Python，入口打印一行、退出码 1。 */
export class PyCrash extends Error {
  readonly kind: string;

  constructor(kind: string, message: string) {
    super(message);
    this.kind = kind;
  }
}

function hex(value: number, width: number): string {
  return value.toString(16).padStart(width, "0");
}

/** repr(str)：引号的选法、转义与不可打印字符的写法都照 CPython。 */
export function pyRepr(text: string): string {
  const quote = text.includes("'") && !text.includes('"') ? '"' : "'";
  let out = quote;
  for (const char of codePoints(text)) {
    const cp = char.codePointAt(0) ?? 0;
    if (char === quote || char === "\\") out += `\\${char}`;
    else if (char === "\t") out += "\\t";
    else if (char === "\n") out += "\\n";
    else if (char === "\r") out += "\\r";
    else if (cp < 0x20 || cp === 0x7f) out += `\\x${hex(cp, 2)}`;
    else if (cp < 0x7f) out += char;
    else if (pyIsPrintable(char)) out += char;
    else if (cp <= 0xff) out += `\\x${hex(cp, 2)}`;
    else if (cp <= 0xffff) out += `\\u${hex(cp, 4)}`;
    else out += `\\U${hex(cp, 8)}`;
  }
  return out + quote;
}

function scalarRepr(value: PyKey): string {
  if (typeof value === "string") return pyRepr(value);
  if (typeof value === "bigint") return intRepr(value);
  if (typeof value === "number") return floatRepr(value);
  if (value === true) return "True";
  if (value === false) return "False";
  return "None";
}

/** repr(value)：容器里的字符串用 repr，其余同 str。 */
export function pyReprValue(value: PyValue): string {
  if (Array.isArray(value)) return `[${value.map(pyReprValue).join(", ")}]`;
  if (value instanceof Map) return `{${[...value].map(([key, item]) => `${scalarRepr(key)}: ${pyReprValue(item)}`).join(", ")}}`;
  return scalarRepr(value);
}

/** str(value)：字符串原样，其余同 repr。 */
export function pyStrValue(value: PyValue): string {
  return typeof value === "string" ? value : pyReprValue(value);
}

/** bool(value)。 */
export function pyTruthy(value: PyValue | undefined): boolean {
  if (value === undefined || value === null || value === false) return false;
  if (value === true) return true;
  if (typeof value === "bigint") return value !== 0n;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string" || Array.isArray(value)) return value.length > 0;
  return value.size > 0;
}

/** len(value)：字符串按码点。 */
export function pyLenValue(value: PyValue): number {
  if (typeof value === "string") return codePoints(value).length;
  if (Array.isArray(value)) return value.length;
  if (value instanceof Map) return value.size;
  throw new PyCrash("TypeError", `object of type '${pyTypeName(value)}' has no len()`);
}

export function pyTypeName(value: PyValue | undefined): string {
  if (value === undefined || value === null) return "NoneType";
  if (typeof value === "boolean") return "bool";
  if (typeof value === "bigint") return "int";
  if (typeof value === "number") return "float";
  if (typeof value === "string") return "str";
  return Array.isArray(value) ? "list" : "dict";
}

/** value.get(key, default)：value 不是 dict 时照 Python 抛 AttributeError。 */
export function pyGet(value: PyValue | undefined, key: string, fallback: PyValue | undefined = null): PyValue {
  if (!(value instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'get'`);
  return value.has(key) ? (value.get(key) as PyValue) : (fallback ?? null);
}

/** dict.get 但要分清“没有这个键”：返回 undefined。 */
export function pyGetOptional(value: PyDict, key: string): PyValue | undefined {
  return value.get(key);
}

const LONE_SURROGATE = /[\uD800-\uDFFF]/gu;

/**
 * Python 的 print 写出的字节：stdout、stderr 经 reconfigure(encoding="utf-8", errors="replace")，孤立代理项写成 "?"；
 * Windows 上文本模式把 "\n" 写成 "\r\n"。
 */
export function pyTextBytes(text: string, platform: string = process.platform): Buffer {
  const replaced = text.replace(LONE_SURROGATE, "?");
  return Buffer.from(platform === "win32" ? replaced.replace(/\n/gu, "\r\n") : replaced, "utf8");
}

/** 非负有限浮点数的精确值：分子与分母（2 的幂）。 */
function exactRatio(value: number): [bigint, bigint] {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value);
  const bits = view.getBigUint64(0);
  const biased = Number((bits >> 52n) & 0x7ffn);
  let mantissa = bits & ((1n << 52n) - 1n);
  let exponent = -1074;
  if (biased !== 0) {
    mantissa |= 1n << 52n;
    exponent = biased - 1075;
  }
  return exponent >= 0 ? [mantissa << BigInt(exponent), 1n] : [mantissa, 1n << BigInt(-exponent)];
}

/**
 * "%.Nf" % value：按二进制的精确值舍入到 N 位小数，恰在中点时取偶（JS 的 toFixed 在中点向上，1e21 起还改用指数）。
 * -0.0 写成 -0；int 先转成 float（与 Python 一样就近取偶）。
 */
export function pyFixed(value: number | bigint, digits: number): string {
  const x = typeof value === "bigint" ? Number(value) : value;
  if (Number.isNaN(x)) return "nan";
  if (!Number.isFinite(x)) return x > 0 ? "inf" : "-inf";
  const negative = x < 0 || Object.is(x, -0);
  const [num, den] = exactRatio(Math.abs(x));
  const scaled = num * 10n ** BigInt(digits);
  let quotient = scaled / den;
  const twice = 2n * (scaled - quotient * den);
  if (twice > den || (twice === den && quotient % 2n === 1n)) quotient += 1n;
  const text = quotient.toString().padStart(digits + 1, "0");
  const body = digits ? `${text.slice(0, -digits)}.${text.slice(-digits)}` : text;
  return negative ? `-${body}` : body;
}

/** round(value, ndigits)，ndigits ≥ 0：float 是离精确舍入结果最近的那个 float；int 原样交回。 */
export function pyRound(value: number | bigint, digits: number): number | bigint {
  if (typeof value === "bigint" || !Number.isFinite(value)) return value;
  return Number.parseFloat(pyFixed(value, digits));
}

/** a + b 在 JSON 值上的数字语义：int 与 bool 相加仍是 int，有 float 就是 float（int 太大时抛 OverflowError），其余类型照 Python 抛 TypeError。 */
export function pyAdd(a: PyValue, b: PyValue): bigint | number {
  const asInt = (value: PyValue): bigint | null => (typeof value === "bigint" ? value : typeof value === "boolean" ? (value ? 1n : 0n) : null);
  const left = asInt(a);
  const right = asInt(b);
  if (left !== null && right !== null) return left + right;
  const numeric = (value: PyValue): boolean => typeof value === "number" || asInt(value) !== null;
  if (numeric(a) && numeric(b)) return (left === null ? (a as number) : intToFloat(left)) + (right === null ? (b as number) : intToFloat(right));
  throw new PyCrash("TypeError", `unsupported operand type(s) for +: '${pyTypeName(a)}' and '${pyTypeName(b)}'`);
}

/** C 的 long：Windows 上 32 位，其余 64 位（builtin_sum 的快速路径按它判断溢出）。 */
const LONG_BITS = process.platform === "win32" ? 31n : 63n;
const LONG_MAX = (1n << LONG_BITS) - 1n;
const LONG_MIN = -(1n << LONG_BITS);
const fitsLong = (value: bigint): boolean => value >= LONG_MIN && value <= LONG_MAX;
/** PyLong_Check：int 与 bool。 */
const longOf = (value: PyValue): bigint | null => (typeof value === "bigint" ? value : typeof value === "boolean" ? (value ? 1n : 0n) : null);

/**
 * sum(values, start)：照 CPython 3.12 的 builtin_sum（themistally-15 复核 b29ab6c 查出逐个相加差在末位）。
 * 1. 起点是 C long 能装下的 int 时，int 与 bool 精确累加；遇到别的项或要溢出时，把它与当前和按 + 加一次，转入下面。
 * 2. 当前和是 float 时用 Neumaier 补偿累加 float；int 与 bool 装得下 C long 就直接加（不补偿），装不下就先并入补偿量，
 *    之后余下的项按 + 逐个加，不再补偿。结束时补偿量非 0 且有限才并进去（inf、nan 不会被弄成 nan）。
 */
export function pySum(values: readonly PyValue[], start: bigint | number = 0n): bigint | number {
  let result: bigint | number = start;
  let at = 0;
  if (typeof result === "bigint" && fitsLong(result)) {
    let total = result;
    for (; at < values.length; at += 1) {
      const value = longOf(values[at] as PyValue);
      if (value === null || !fitsLong(value) || !fitsLong(total + value)) break;
      total += value;
    }
    if (at === values.length) return total;
    result = pyAdd(total, values[at] as PyValue);
    at += 1;
  }
  if (typeof result === "number") {
    let sum = result;
    let compensation = 0;
    for (; at < values.length; at += 1) {
      const item = values[at] as PyValue;
      if (typeof item === "number") {
        const next = sum + item;
        compensation += Math.abs(sum) >= Math.abs(item) ? sum - next + item : item - next + sum;
        sum = next;
        continue;
      }
      const value = longOf(item);
      if (value === null || !fitsLong(value)) break;
      sum += Number(value);
    }
    if (compensation !== 0 && Number.isFinite(compensation)) sum += compensation;
    if (at === values.length) return sum;
    result = sum;
  }
  for (; at < values.length; at += 1) result = pyAdd(result, values[at] as PyValue);
  return result;
}

/** a + b 的全部语义：数字照 pyAdd，str + str 与 list + list 是拼接，其余照 Python 抛 TypeError。 */
export function pyPlus(a: PyValue, b: PyValue): PyValue {
  if (typeof a === "string") {
    if (typeof b === "string") return a + b;
    throw new PyCrash("TypeError", `can only concatenate str (not "${pyTypeName(b)}") to str`);
  }
  if (Array.isArray(a)) {
    if (Array.isArray(b)) return [...a, ...b];
    throw new PyCrash("TypeError", `can only concatenate list (not "${pyTypeName(b)}") to list`);
  }
  return pyAdd(a, b);
}

/** float(int)：太大时照 Python 抛 OverflowError，不变成无穷。 */
function intToFloat(value: bigint): number {
  const result = Number(value);
  if (!Number.isFinite(result)) throw new PyCrash("OverflowError", "int too large to convert to float");
  return result;
}

/** (value or 0) > 0：不是数字的真值（字符串、列表、字典）照 Python 抛 TypeError。 */
export function pyPositive(value: PyValue | undefined): boolean {
  if (!pyTruthy(value)) return false;
  if (typeof value === "bigint") return value > 0n;
  if (typeof value === "number") return value > 0;
  if (typeof value === "boolean") return value;
  throw new PyCrash("TypeError", `'>' not supported between instances of '${pyTypeName(value)}' and 'int'`);
}

/** "%d" % value：int 原样，bool 是 1 与 0，float 截断，其余照 Python 抛异常。 */
export function pyPercentD(value: PyValue | undefined): string {
  return String(pyIntOf(value === undefined ? null : value, "%d format"));
}

/** int(value)：float 截断（NaN 抛 ValueError，无穷抛 OverflowError），字符串照 int() 解析。 */
export function pyIntOf(value: PyValue, context = "int()"): bigint {
  if (typeof value === "bigint") return value;
  if (typeof value === "boolean") return value ? 1n : 0n;
  if (typeof value === "number") {
    if (Number.isNaN(value)) throw new PyCrash("ValueError", "cannot convert float NaN to integer");
    if (!Number.isFinite(value)) throw new PyCrash("OverflowError", "cannot convert float infinity to integer");
    return BigInt(Math.trunc(value));
  }
  if (typeof value === "string" && context === "int()") {
    const parsed = pyIntParse(value);
    if (parsed === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: ${pyReprValue(value)}`);
    return parsed;
  }
  throw new PyCrash("TypeError", context === "int()"
    ? `int() argument must be a string, a bytes-like object or a real number, not '${pyTypeName(value)}'`
    : `%d format: a real number is required, not ${pyTypeName(value)}`);
}

const FLOAT_WORDS = new Map<string, number>([["inf", Infinity], ["infinity", Infinity], ["nan", Number.NaN]]);

/** float(value)：int 转成最近的 float（太大抛 OverflowError），字符串照 float() 解析（两头的空白、数字间的单个下划线、Unicode 十进制数字、inf 与 nan）。 */
export function pyFloatOf(value: PyValue): number {
  if (typeof value === "number") return value;
  if (typeof value === "boolean") return value ? 1 : 0;
  if (typeof value === "bigint") return intToFloat(value);
  if (typeof value !== "string") throw new PyCrash("TypeError", `float() argument must be a string or a real number, not '${pyTypeName(value)}'`);
  const parsed = parseFloatText(value);
  if (parsed === null) throw new PyCrash("ValueError", `could not convert string to float: ${pyReprValue(value)}`);
  return parsed;
}

function parseFloatText(text: string): number | null {
  // 先照 CPython 把 Unicode 十进制数字换成 ASCII、空白换成空格，再去掉两头的空格
  let ascii = "";
  for (const char of text) {
    if (isSpace(char)) ascii += " ";
    else if (isDigitChar(char) && pyIntParse(char) !== null) ascii += String(pyIntParse(char));
    else if ((char.codePointAt(0) as number) < 128) ascii += char;
    else return null;
  }
  const body = ascii.trim();
  const sign = body.startsWith("-") ? -1 : 1;
  const unsigned = body.startsWith("-") || body.startsWith("+") ? body.slice(1) : body;
  const word = FLOAT_WORDS.get(unsigned.toLowerCase());
  if (word !== undefined) return sign * word;
  if (!FLOAT_SYNTAX.test(unsigned)) return null;
  return sign * Number(unsigned.split("_").join(""));
}

/** 数字部分：数字之间可以有单个下划线；小数点前后至少一边有数字；指数可选。 */
const DIGITS = "[0-9](?:_?[0-9])*";
const FLOAT_SYNTAX = new RegExp(`^(?:${DIGITS}(?:[.](?:${DIGITS})?)?|[.]${DIGITS})(?:[eE][+-]?${DIGITS})?$`);

/** iter(value) 交出的项：列表原样，字符串拆成码点，字典取键，其余照 Python 抛 TypeError。 */
export function pyIter(value: PyValue | undefined): PyValue[] {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") return codePoints(value);
  if (value instanceof Map) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not iterable`);
}

/** value[key]（字符串键）：不是字典、没有这个键时照 Python 抛异常。 */
export function pyItem(value: PyValue | undefined, key: string): PyValue {
  if (value instanceof Map) {
    if (!value.has(key)) throw new PyCrash("KeyError", pyRepr(key));
    return value.get(key) as PyValue;
  }
  if (typeof value === "string") throw new PyCrash("TypeError", "string indices must be integers, not 'str'");
  if (Array.isArray(value)) throw new PyCrash("TypeError", "list indices must be integers or slices, not str");
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
}

/** sep.join(value)：value 先照 iter 展开，每一项都必须是字符串。 */
export function pyJoin(sep: string, value: PyValue | undefined): string {
  let items: PyValue[];
  try {
    items = pyIter(value);
  } catch (error) {
    if (error instanceof PyCrash) throw new PyCrash("TypeError", "can only join an iterable");
    throw error;
  }
  return pyJoinStrings(sep, items);
}

/** sep.join(items)：不是字符串的项照 Python 报出它的序号与类型。 */
export function pyJoinStrings(sep: string, items: readonly PyValue[]): string {
  items.forEach((item, index) => {
    if (typeof item !== "string") throw new PyCrash("TypeError", `sequence item ${index}: expected str instance, ${pyTypeName(item)} found`);
  });
  return items.join(sep);
}

function writeAll(fd: number, bytes: Buffer): void {
  let offset = 0;
  while (offset < bytes.length) offset += writeSync(fd, bytes, offset, bytes.length - offset);
}

/** sys.stdout 的文本层与字节层各自的容量（io.DEFAULT_BUFFER_SIZE；Windows 上没有 st_blksize，就是它）。 */
const STDOUT_CHUNK = 8192;

/** 照 Python 的 print 往 stdout、stderr 写（同步写，进程退出前不会丢）。 */
export class PyOut {
  /**
   * stdout 块缓冲（④b3）：照 Python 的 sys.stdout 不是终端时的写法；stderr 照写不误（Python 3.9 起 stderr 总是行缓冲）。
   * hub 把 stderr 并进 stdout 读，报错路径上 ERROR: 会排在还没冲出的 NOTE、GATE 前面，次序要照到字节。缺省不缓冲（已经
   * 切换的命令照旧）；打开的命令在退出前要调 flush()。
   *
   * CPython 3.12 是两层（themistally-15 复核 d14ea7c 实测）：一次 print 是两次 write，正文一次、换行一次（按换成 CRLF
   * 之后的 UTF-8 字节计）。文本层把每次 write 的字节攒进 pending，到 8192 及以上时整份交给字节层；一次 write 本身就有
   * 8192 字节及以上时，先把手上的 pending 单独交出去（④b3 补实测：先写 5 字节、再写恰好 8192 字节，那 5 字节先落盘）。
   * 字节层容量 8192：交来的放得下就留着；放不下就先把手上的写出去，再看交来的，超过 8192 直接写出，否则留着。flush 先交
   * pending，再写出字节层。
   */
  private readonly buffered: boolean;
  private pending: Buffer[] = [];
  private pendingBytes = 0;
  private held: Buffer | null = null;

  constructor(options: { readonly bufferStdout?: boolean } = {}) {
    this.buffered = options.bufferStdout === true;
  }

  print(text = "", options: { readonly flush?: boolean } = {}): void {
    if (!this.buffered) {
      writeAll(1, pyTextBytes(`${text}\n`));
      return;
    }
    this.textWrite(pyTextBytes(text));
    this.textWrite(pyTextBytes("\n"));
    if (options.flush === true) this.flush();
  }

  /** sys.stdout.write(text)：不加换行。 */
  write(text: string): void {
    if (this.buffered) this.textWrite(pyTextBytes(text));
    else writeAll(1, pyTextBytes(text));
  }

  printErr(text = ""): void {
    writeAll(2, pyTextBytes(`${text}\n`));
  }

  /** sys.stdout.flush()。 */
  flush(): void {
    if (this.pendingBytes) this.handOver();
    if (this.held) writeAll(1, this.held);
    this.held = null;
  }

  private textWrite(bytes: Buffer): void {
    if (bytes.length >= STDOUT_CHUNK && this.pendingBytes) this.handOver();
    this.pending.push(bytes);
    this.pendingBytes += bytes.length;
    if (this.pendingBytes >= STDOUT_CHUNK) this.handOver();
  }

  /** 文本层的 pending 交给字节层（BufferedWriter.write）。 */
  private handOver(): void {
    const data = Buffer.concat(this.pending);
    this.pending = [];
    this.pendingBytes = 0;
    const held = this.held ?? Buffer.alloc(0);
    if (data.length <= STDOUT_CHUNK - held.length) {
      this.held = Buffer.concat([held, data]);
      return;
    }
    if (held.length) writeAll(1, held);
    this.held = null;
    if (data.length > STDOUT_CHUNK) writeAll(1, data);
    else this.held = data;
  }
}
