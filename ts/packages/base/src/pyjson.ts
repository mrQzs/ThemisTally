// Python 兼容的 JSON：逐字节复刻 Python 3.12 标准库 json.dumps / json.loads（迁移第 ① 步，计划第 1.4 节）。
//
// 现行实现的信件 sha256、合同摘要、内容锁、state.json 都是 json.dumps 写出的字节，TS 版必须写出一模一样的字节；
// 读进来、改完、写回时也不能丢掉 Python 的区别。所以值不用 JSON.parse 的结果表示，而用 PyValue：
//   - Python int ↔ bigint（任意大小），Python float ↔ number（含 -0.0、NaN、±Infinity）；
//   - Python dict ↔ Map（保持插入顺序；JS 对象会把整数样的键提到前面）；键可以是 str、int、float、bool、None；
//   - Python str ↔ string（可以含孤立代理项：Python 到 encode 才报错，见 encodeUtf8）。
// 已知的限制：Map 按 SameValueZero 比较键，-0.0 作键会并成 0.0（Python 的 dict 保留 -0.0）；1 与 1.0、True
// 在 Python 里是同一个键，在 Map 里是三个。现行代码的 dict 键只来自 JSON（都是字符串）或代码自己写定，
// 遇不到这两种情况；契约测试也不覆盖它们。sort_keys 遇到不能比较的键时报 TypeError，类型对了，文字里两个类型名的
// 先后可能与 Python 不同（取决于 CPython 的 Timsort 先比较哪两个元素），同样走不到。
// 行为由 packages/contracts 的 pyjson 契约测试与对照测试约束（Python 实现先过）。

export type PyKey = string | bigint | number | boolean | null;
export type PyValue = null | boolean | bigint | number | string | PyValue[] | PyDict;
export type PyDict = Map<PyKey, PyValue>;

export type PyErrorKind = "TypeError" | "ValueError" | "JSONDecodeError" | "UnicodeEncodeError" | "RecursionError";

/** Python 会抛的异常：kind 是异常类名（JSONDecodeError 在 Python 里是 ValueError 的子类）。 */
export class PyJsonError extends Error {
  readonly kind: PyErrorKind;
  constructor(kind: PyErrorKind, message: string) {
    super(message);
    this.kind = kind;
    this.name = kind;
  }
}

/** json.dumps 的参数，缺省值与 Python 相同：ensure_ascii=True、indent=None、sort_keys=False、allow_nan=True。 */
export interface DumpsOptions {
  readonly ensureAscii?: boolean;
  readonly indent?: number | null;
  readonly separators?: readonly [string, string] | null;
  readonly sortKeys?: boolean;
  readonly allowNan?: boolean;
}

/** Python 3.12 的 sys.int_info.default_max_str_digits：int 与十进制串互转的位数上限。 */
export const INT_MAX_STR_DIGITS = 4300;

const SHORT_ESCAPES: Record<string, string> = {
  '"': '\\"',
  "\\": "\\\\",
  "\b": "\\b",
  "\f": "\\f",
  "\n": "\\n",
  "\r": "\\r",
  "\t": "\\t",
};

function hex4(unit: number): string {
  return "\\u" + unit.toString(16).padStart(4, "0");
}

/** encode_basestring（ensure_ascii=False）：只转义引号、反斜杠与 0x00–0x1f。 */
function encodeString(text: string): string {
  let out = '"';
  for (let index = 0; index < text.length; index += 1) {
    const unit = text.charCodeAt(index);
    const char = text[index] ?? "";
    const short = SHORT_ESCAPES[char];
    if (short !== undefined) out += short;
    else if (unit < 0x20) out += hex4(unit);
    else out += char;
  }
  return out + '"';
}

/** encode_basestring_ascii（ensure_ascii=True）：空格到 ~ 之外的码元一律 \uXXXX（小写），补充平面写成代理对。 */
function encodeStringAscii(text: string): string {
  let out = '"';
  for (let index = 0; index < text.length; index += 1) {
    const unit = text.charCodeAt(index);
    const char = text[index] ?? "";
    const short = SHORT_ESCAPES[char];
    if (short !== undefined) out += short;
    else if (unit < 0x20 || unit > 0x7e) out += hex4(unit);
    else out += char;
  }
  return out + '"';
}

/**
 * int 与十进制串互转的位数上限。两个方向的文字不同（Python 3.12）：
 *   int → str：…for integer string conversion; use sys.set_int_max_str_digits() to increase the limit
 *   str → int：…for integer string conversion: value has <N> digits; use sys.set_int_max_str_digits() to increase the limit
 */
function checkIntDigits(digits: number, parsing = false): void {
  if (digits > INT_MAX_STR_DIGITS) {
    const detail = parsing ? `: value has ${digits} digits;` : ";";
    throw new PyJsonError(
      "ValueError",
      `Exceeds the limit (${INT_MAX_STR_DIGITS} digits) for integer string conversion${detail} use sys.set_int_max_str_digits() to increase the limit`,
    );
  }
}

/** int.__repr__ */
export function intRepr(value: bigint): string {
  const text = value.toString();
  checkIntDigits(text.length - (value < 0n ? 1 : 0));
  return text;
}

/**
 * float.__repr__（'r' 格式）：最短往返的数字串，十进制小数点位置 decpt 不在 (-4, 16] 时写成指数形式，
 * 指数至少两位并带符号（1e+16、1e-05）；定点形式的整数值补 ".0"。
 */
export function floatRepr(value: number): string {
  if (Number.isNaN(value)) return "nan";
  if (value === Infinity) return "inf";
  if (value === -Infinity) return "-inf";
  if (value === 0) return Object.is(value, -0) ? "-0.0" : "0.0";
  const sign = value < 0 ? "-" : "";
  const [mantissa = "", exponentText = "0"] = Math.abs(value).toExponential().split("e"); // 不给位数：最短往返
  const digits = mantissa.replace(".", "");
  const exponent = Number(exponentText);
  const decpt = exponent + 1;
  if (decpt <= -4 || decpt > 16) {
    const body = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
    return `${sign}${body}e${exponent < 0 ? "-" : "+"}${String(Math.abs(exponent)).padStart(2, "0")}`;
  }
  if (decpt <= 0) return `${sign}0.${"0".repeat(-decpt)}${digits}`;
  if (decpt >= digits.length) return `${sign}${digits}${"0".repeat(decpt - digits.length)}.0`;
  return `${sign}${digits.slice(0, decpt)}.${digits.slice(decpt)}`;
}

/** json 模块里 float 的写法：NaN、Infinity、-Infinity（allow_nan=False 时报 ValueError）。 */
function floatJson(value: number, allowNan: boolean): string {
  if (Number.isFinite(value)) return floatRepr(value);
  if (!allowNan) throw new PyJsonError("ValueError", `Out of range float values are not JSON compliant: ${floatRepr(value)}`);
  return Number.isNaN(value) ? "NaN" : value > 0 ? "Infinity" : "-Infinity";
}

function typeName(value: unknown): string {
  if (value === null) return "NoneType";
  if (typeof value === "boolean") return "bool";
  if (typeof value === "bigint") return "int";
  if (typeof value === "number") return "float";
  if (typeof value === "string") return "str";
  if (Array.isArray(value)) return "list";
  if (value instanceof Map) return "dict";
  return typeof value;
}

/** 按码点比较（Python 的 str 比较）；JS 的 < 比较的是 UTF-16 码元，补充平面的字符次序会不同。 */
export function compareCodePoints(left: string, right: string): number {
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    const a = left.codePointAt(i) ?? 0;
    const b = right.codePointAt(j) ?? 0;
    if (a !== b) return a < b ? -1 : 1;
    i += a > 0xffff ? 2 : 1;
    j += b > 0xffff ? 2 : 1;
  }
  return i < left.length ? 1 : j < right.length ? -1 : 0;
}

function isNumeric(key: PyKey): key is bigint | number | boolean {
  return typeof key === "bigint" || typeof key === "number" || typeof key === "boolean";
}

/** 数值键之间的比较（int、float、bool 在 Python 里可以互相比较）。 */
function compareNumeric(left: bigint | number | boolean, right: bigint | number | boolean): number {
  const a = typeof left === "boolean" ? (left ? 1n : 0n) : left;
  const b = typeof right === "boolean" ? (right ? 1n : 0n) : right;
  if (typeof a === "bigint" && typeof b === "bigint") return a < b ? -1 : a > b ? 1 : 0;
  // 一边是 float：Python 精确比较；NaN 与谁都不“小于”
  if (typeof a === "number" && Number.isNaN(a)) return 0;
  if (typeof b === "number" && Number.isNaN(b)) return 0;
  return a < b ? -1 : a > b ? 1 : 0;
}

/** sorted(dct.items())：只用 <，类型不能比较时与 Python 一样报 TypeError。 */
function compareKeys(left: PyKey, right: PyKey): number {
  if (typeof left === "string" && typeof right === "string") return compareCodePoints(left, right);
  if (isNumeric(left) && isNumeric(right)) return compareNumeric(left, right);
  throw new PyJsonError(
    "TypeError",
    `'<' not supported between instances of '${typeName(right)}' and '${typeName(left)}'`,
  );
}

function keyText(key: PyKey, allowNan: boolean): string {
  if (typeof key === "string") return key;
  if (typeof key === "number") return floatJson(key, allowNan);
  if (key === true) return "true";
  if (key === false) return "false";
  if (key === null) return "null";
  if (typeof key === "bigint") return intRepr(key);
  throw new PyJsonError("TypeError", `keys must be str, int, float, bool or None, not ${typeName(key)}`);
}

/** json.dumps：与 Python 3.12 的 C 编码器逐字节一致。 */
export function dumps(value: PyValue, options: DumpsOptions = {}): string {
  const ensureAscii = options.ensureAscii ?? true;
  const indent = options.indent ?? null;
  const sortKeys = options.sortKeys ?? false;
  const allowNan = options.allowNan ?? true;
  const [itemSeparator, keySeparator] = options.separators ?? (indent === null ? [", ", ": "] : [",", ": "]);
  const encode = ensureAscii ? encodeStringAscii : encodeString;

  const write = (item: PyValue, level: number): string => {
    if (item === null) return "null";
    if (item === true) return "true";
    if (item === false) return "false";
    if (typeof item === "string") return encode(item);
    if (typeof item === "bigint") return intRepr(item);
    if (typeof item === "number") return floatJson(item, allowNan);
    const open = indent === null ? "" : "\n" + " ".repeat(indent * (level + 1));
    const close = indent === null ? "" : "\n" + " ".repeat(indent * level);
    const separator = itemSeparator + open;
    if (Array.isArray(item)) {
      if (item.length === 0) return "[]";
      return "[" + open + item.map((element) => write(element, level + 1)).join(separator) + close + "]";
    }
    if (item instanceof Map) {
      if (item.size === 0) return "{}";
      const entries = [...item.entries()];
      if (sortKeys) entries.sort(([left], [right]) => compareKeys(left, right));
      const parts = entries.map(([key, element]) => encode(keyText(key, allowNan)) + keySeparator + write(element, level + 1));
      return "{" + open + parts.join(separator) + close + "}";
    }
    throw new PyJsonError("TypeError", `Object of type ${typeName(item)} is not JSON serializable`);
  };
  return write(value, 0);
}

/** str.encode("utf-8")：含孤立代理项时与 Python 一样报 UnicodeEncodeError（TextEncoder 会悄悄换成 U+FFFD）。 */
export function encodeUtf8(text: string): Uint8Array {
  if (!text.isWellFormed()) {
    // 文字照 Python：第一个孤立代理项起、连在一起的一串代理项算一处；位置按码点，单个时写出字符的 repr
    let start = 0;
    while (start < text.length && !isLoneSurrogate(text, start)) start += isPairAt(text, start) ? 2 : 1;
    let end = start;
    while (end < text.length && isLoneSurrogate(text, end)) end += 1;
    const from = codePointIndex(text, start);
    const where =
      end - start === 1
        ? `character '\\u${text.charCodeAt(start).toString(16)}' in position ${from}`
        : `characters in position ${from}-${from + (end - start) - 1}`;
    throw new PyJsonError("UnicodeEncodeError", `'utf-8' codec can't encode ${where}: surrogates not allowed`);
  }
  return new TextEncoder().encode(text);
}

function isPairAt(text: string, index: number): boolean {
  const unit = text.charCodeAt(index);
  const next = text.charCodeAt(index + 1);
  return unit >= 0xd800 && unit <= 0xdbff && next >= 0xdc00 && next <= 0xdfff;
}

/** index 处是不是孤立的代理项（不是代理对的一半）。 */
function isLoneSurrogate(text: string, index: number): boolean {
  const unit = text.charCodeAt(index);
  if (unit < 0xd800 || unit > 0xdfff) return false;
  if (isPairAt(text, index)) return false;
  return !(unit >= 0xdc00 && index > 0 && isPairAt(text, index - 1));
}

// ---------------------------------------------------------------------------
// json.loads
// ---------------------------------------------------------------------------

const NUMBER_RE = /(-?(?:0|[1-9]\d*))(\.\d+)?([eE][-+]?\d+)?/y;
const WHITESPACE_RE = /[ \t\n\r]*/y;
const HEX4_RE = /^[0-9a-fA-F]{4}$/;
const SIMPLE_ESCAPES: Record<string, string> = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };

const BOM = String.fromCharCode(0xfeff);

/**
 * text 的前 units 个 UTF-16 码元里有几个码点（Python 的 str 下标按码点）。
 * 超出末尾的部分照原样外推：rawDecode("abc", 10) 与 Python 一样报 char 10。
 */
export function codePointIndex(text: string, units: number): number {
  let count = Math.max(0, units - text.length);
  for (let index = 0; index < units && index < text.length; index += 1) {
    const unit = text.charCodeAt(index);
    // 代理对算一个码点：高代理项后面紧跟低代理项时，低的那个不再计数
    if (unit >= 0xdc00 && unit <= 0xdfff && index > 0) {
      const previous = text.charCodeAt(index - 1);
      if (previous >= 0xd800 && previous <= 0xdbff) continue;
    }
    count += 1;
  }
  return count;
}

/** 第 codePoints 个码点在 text 里的 UTF-16 下标（codePointIndex 的反函数；超出末尾的照原样外推）。 */
export function unitIndex(text: string, codePoints: number): number {
  let index = 0;
  let count = 0;
  for (; count < codePoints && index < text.length; count += 1) {
    const unit = text.charCodeAt(index);
    const next = text.charCodeAt(index + 1);
    index += unit >= 0xd800 && unit <= 0xdbff && next >= 0xdc00 && next <= 0xdfff ? 2 : 1;
  }
  return index + (codePoints - count);
}

/**
 * json.JSONDecodeError：文字与 Python 相同，"<msg>: line <行> column <列> (char <位置>)"，位置按码点数。
 * 这些文字会经 str(exc) 写进报错、证据与信件（pi_dispatch、kit_hub、kit_install、decisions 共 9 处）。
 */
export class PyJsonDecodeError extends PyJsonError {
  readonly msg: string;
  readonly pos: number;
  readonly lineno: number;
  readonly colno: number;
  constructor(msg: string, text: string, units: number) {
    const pos = codePointIndex(text, units);
    const lineno = text.slice(0, units).split("\n").length;
    const lastNewline = text.lastIndexOf("\n", units - 1);
    const colno = units === 0 || lastNewline < 0 ? pos + 1 : pos - codePointIndex(text, lastNewline);
    super("JSONDecodeError", `${msg}: line ${lineno} column ${colno} (char ${pos})`);
    this.msg = msg;
    this.pos = pos;
    this.lineno = lineno;
    this.colno = colno;
  }
}

/** units 是出错位置的 UTF-16 下标。 */
function decodeError(text: string, message: string, units: number): PyJsonDecodeError {
  return new PyJsonDecodeError(message, text, units);
}

function skipWhitespace(text: string, index: number): number {
  WHITESPACE_RE.lastIndex = index;
  WHITESPACE_RE.exec(text);
  return WHITESPACE_RE.lastIndex;
}

/**
 * json.decoder.scanstring（CPython 3.12 的 _json.c，strict=True）：end 指向开头引号之后。
 * 返回（字符串，收尾引号之后的位置）。报错的位置与条件逐条照 C 版本：
 *   - 引号、反斜杠之前遇到 0x00–0x1f：Invalid control character at（那个字符）
 *   - 到结尾也没有引号，或反斜杠是最后一个字符：Unterminated string starting at（开头的引号）
 *   - 不认识的转义：Invalid \escape（反斜杠）
 *   - \u 后面四位之后必须还有字符，四位里有非十六进制：Invalid \uXXXX escape（那个 u）
 *   - 高代理项后面还剩超过 6 个字符、紧跟反斜杠加 u 时才试着配对；第二个转义的四位不是十六进制同样报错
 *     （指向第二个 u），不是低代理项就不配对、留给下一轮当单独的转义
 */
function scanString(text: string, end: number): [string, number] {
  const begin = end - 1;
  let out = "";
  let index = end;
  for (;;) {
    if (index >= text.length) throw decodeError(text, "Unterminated string starting at", begin);
    const char = text[index] ?? "";
    const unit = text.charCodeAt(index);
    if (char === '"') return [out, index + 1];
    if (char !== "\\") {
      if (unit < 0x20) throw decodeError(text, "Invalid control character at", index);
      out += char;
      index += 1;
      continue;
    }
    const escape = text[index + 1];
    if (escape === undefined) throw decodeError(text, "Unterminated string starting at", begin);
    if (escape !== "u") {
      const simple = SIMPLE_ESCAPES[escape];
      if (simple === undefined) throw decodeError(text, "Invalid \\escape", index);
      out += simple;
      index += 2;
      continue;
    }
    const u = index + 1;
    let after = u + 5; // 四位十六进制之后
    if (after >= text.length) throw decodeError(text, "Invalid \\uXXXX escape", u);
    const first = text.slice(u + 1, after);
    if (!HEX4_RE.test(first)) throw decodeError(text, "Invalid \\uXXXX escape", u);
    let codePoint = parseInt(first, 16);
    if (codePoint >= 0xd800 && codePoint <= 0xdbff && after + 6 < text.length && text[after] === "\\" && text[after + 1] === "u") {
      const second = text.slice(after + 2, after + 6);
      if (!HEX4_RE.test(second)) throw decodeError(text, "Invalid \\uXXXX escape", after + 1);
      const low = parseInt(second, 16);
      if (low >= 0xdc00 && low <= 0xdfff) {
        codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + (low - 0xdc00);
        after += 6;
      }
    }
    out += String.fromCodePoint(codePoint);
    index = after;
  }
}

/**
 * 解析出来的值怎么组装：json.loads 的 object_pairs_hook、parse_int、parse_float、parse_constant 四个钩子。
 * 文法与报错由同一个扫描器负责，各种用法只换组装方式。
 */
export interface JsonBuilder<V> {
  object(pairs: [string, V][]): V;
  array(items: V[]): V;
  string(value: string): V;
  literal(value: null | boolean): V;
  /** NaN、Infinity、-Infinity。 */
  constant(raw: string): V;
  /** 数的原文；isFloat 时有小数点或指数。 */
  number(raw: string, isFloat: boolean): V;
}

/** json.loads 缺省的组装：dict、list、int（bigint）与 float（number）。 */
const PY_BUILDER: JsonBuilder<PyValue> = {
  object(pairs) {
    const out: PyDict = new Map();
    for (const [key, value] of pairs) out.set(key, value); // 重复的键：Python 的 dict 保留第一次出现的位置、最后一次的值，Map.set 同样
    return out;
  },
  array: (items) => items,
  string: (value) => value,
  literal: (value) => value,
  constant: (raw) => (raw === "NaN" ? NaN : raw === "Infinity" ? Infinity : -Infinity),
  number(raw, isFloat) {
    if (isFloat) return Number(raw);
    checkIntDigits(raw.length - (raw.startsWith("-") ? 1 : 0), true);
    return BigInt(raw);
  },
};

function parseNumber<V>(text: string, index: number, builder: JsonBuilder<V>): [V, number] | null {
  NUMBER_RE.lastIndex = index;
  const match = NUMBER_RE.exec(text);
  if (match === null) return null;
  const [whole, , fraction, exponent] = match;
  return [builder.number(whole, fraction !== undefined || exponent !== undefined), index + whole.length];
}

function scanValue<V>(text: string, index: number, depth: number, builder: JsonBuilder<V>): [V, number] {
  // 嵌套极深时 Python 报 RecursionError；具体在第几层取决于解释器的递归上限，这里固定在 1000 层。两边报错层数不同的
  // 窗口（strict_json_loads 的错误码、深配置的报错文字）记在迁移文档第 10 节，契约不比较
  if (depth > 1000) throw new PyJsonError("RecursionError", "maximum recursion depth exceeded while decoding a JSON object");
  const char = text[index];
  if (char === undefined) throw decodeError(text, "Expecting value", index);
  if (char === '"') {
    const [value, end] = scanString(text, index + 1);
    return [builder.string(value), end];
  }
  if (char === "{") return scanObject(text, index + 1, depth + 1, builder);
  if (char === "[") return scanArray(text, index + 1, depth + 1, builder);
  if (char === "n" && text.startsWith("null", index)) return [builder.literal(null), index + 4];
  if (char === "t" && text.startsWith("true", index)) return [builder.literal(true), index + 4];
  if (char === "f" && text.startsWith("false", index)) return [builder.literal(false), index + 5];
  for (const constant of ["NaN", "Infinity", "-Infinity"]) {
    if (char === constant[0] && text.startsWith(constant, index)) return [builder.constant(constant), index + constant.length];
  }
  const number = parseNumber(text, index, builder);
  if (number === null) throw decodeError(text, "Expecting value", index);
  return number;
}

function scanObject<V>(text: string, index: number, depth: number, builder: JsonBuilder<V>): [V, number] {
  const pairs: [string, V][] = [];
  let position = skipWhitespace(text, index);
  if (text[position] === "}") return [builder.object(pairs), position + 1];
  for (;;) {
    if (text[position] !== '"') throw decodeError(text, "Expecting property name enclosed in double quotes", position);
    const [key, afterKey] = scanString(text, position + 1);
    position = skipWhitespace(text, afterKey);
    if (text[position] !== ":") throw decodeError(text, "Expecting ':' delimiter", position);
    position = skipWhitespace(text, position + 1);
    const [value, afterValue] = scanValue(text, position, depth, builder);
    pairs.push([key, value]);
    position = skipWhitespace(text, afterValue);
    if (text[position] === "}") return [builder.object(pairs), position + 1];
    if (text[position] !== ",") throw decodeError(text, "Expecting ',' delimiter", position);
    position = skipWhitespace(text, position + 1);
  }
}

function scanArray<V>(text: string, index: number, depth: number, builder: JsonBuilder<V>): [V, number] {
  const items: V[] = [];
  let position = skipWhitespace(text, index);
  if (text[position] === "]") return [builder.array(items), position + 1];
  for (;;) {
    const [value, afterValue] = scanValue(text, position, depth, builder);
    items.push(value);
    position = skipWhitespace(text, afterValue);
    if (text[position] === "]") return [builder.array(items), position + 1];
    if (text[position] !== ",") throw decodeError(text, "Expecting ',' delimiter", position);
    position = skipWhitespace(text, position + 1);
  }
}

/** json.loads(str, 钩子…)：整份文本是一个值（前后可有空白），开头的 BOM 与尾随的内容照 Python 报错。 */
export function loadsWith<V>(text: string, builder: JsonBuilder<V>): V {
  if (text.startsWith(BOM)) throw decodeError(text, "Unexpected UTF-8 BOM (decode using utf-8-sig)", 0);
  const [value, end] = scanValue(text, skipWhitespace(text, 0), 0, builder);
  const tail = skipWhitespace(text, end);
  if (tail !== text.length) throw decodeError(text, "Extra data", tail);
  return value;
}

/** json.loads(str)：与 Python 3.12 一致，接受 NaN、Infinity、-Infinity；整数与浮点分开（bigint / number）。 */
export function loads(text: string): PyValue {
  return loadsWith(text, PY_BUILDER);
}

/**
 * json.loads(bytes)（④b4，决策端点的回复）：照 json.detect_encoding 认出 UTF-8（带不带 BOM）、UTF-16、UTF-32，按
 * surrogatepass 解码再解析。解不了码时抛 ValueError（Python 的 UnicodeDecodeError 是它的子类）。
 */
export function loadsBytes(data: Uint8Array): PyValue {
  return loads(decodeDetected(data));
}

function detectEncoding(b: Uint8Array): string {
  const starts = (...prefix: number[]): boolean => prefix.every((byte, index) => b[index] === byte);
  if (starts(0x00, 0x00, 0xfe, 0xff) || starts(0xff, 0xfe, 0x00, 0x00)) return "utf-32";
  if (starts(0xfe, 0xff) || starts(0xff, 0xfe)) return "utf-16";
  if (starts(0xef, 0xbb, 0xbf)) return "utf-8-sig";
  if (b.length >= 4) {
    if (!b[0]) return b[1] ? "utf-16-be" : "utf-32-be";
    if (!b[1]) return b[2] || b[3] ? "utf-16-le" : "utf-32-le";
  } else if (b.length === 2) {
    if (!b[0]) return "utf-16-be";
    if (!b[1]) return "utf-16-le";
  }
  return "utf-8";
}

const undecodable = (encoding: string): PyJsonError => new PyJsonError("ValueError", `'${encoding}' codec can't decode the reply`);

function decodeDetected(b: Uint8Array): string {
  const encoding = detectEncoding(b);
  if (encoding === "utf-8" || encoding === "utf-8-sig") return utf8SurrogatePass(encoding === "utf-8" ? b : b.subarray(3));
  const width = encoding.startsWith("utf-16") ? 2 : 4;
  let little = encoding.endsWith("-le");
  let body = b;
  if (encoding === "utf-16" || encoding === "utf-32") {
    little = b[0] === 0xff;
    body = b.subarray(width);
  }
  if (body.length % width) throw undecodable(encoding);
  const units: number[] = [];
  for (let index = 0; index < body.length; index += width) {
    const at = (offset: number): number => body[little ? index + offset : index + width - 1 - offset] ?? 0;
    const value = width === 2 ? at(0) | (at(1) << 8) : (at(0) | (at(1) << 8) | (at(2) << 16) | (at(3) << 24)) >>> 0;
    if (value > 0x10ffff) throw undecodable(encoding);
    if (width === 2 || value < 0x10000) units.push(value);
    else units.push(0xd800 + ((value - 0x10000) >> 10), 0xdc00 + ((value - 0x10000) & 0x3ff));
  }
  return fromUnits(units);
}

/** UTF-8 照 CPython 的严格规则，只多收 ED A0–BF 开头的三字节代理项（surrogatepass）。 */
function utf8SurrogatePass(b: Uint8Array): string {
  const units: number[] = [];
  const cont = (index: number, low = 0x80, high = 0xbf): number => {
    const byte = b[index];
    if (byte === undefined || byte < low || byte > high) throw undecodable("utf-8");
    return byte & 0x3f;
  };
  let index = 0;
  while (index < b.length) {
    const lead = b[index] as number;
    if (lead < 0x80) {
      units.push(lead);
      index += 1;
    } else if (lead >= 0xc2 && lead <= 0xdf) {
      units.push(((lead & 0x1f) << 6) | cont(index + 1));
      index += 2;
    } else if (lead >= 0xe0 && lead <= 0xef) {
      const second = cont(index + 1, lead === 0xe0 ? 0xa0 : 0x80, 0xbf);
      units.push(((lead & 0x0f) << 12) | (second << 6) | cont(index + 2));
      index += 3;
    } else if (lead >= 0xf0 && lead <= 0xf4) {
      const second = cont(index + 1, lead === 0xf0 ? 0x90 : 0x80, lead === 0xf4 ? 0x8f : 0xbf);
      const value = ((lead & 0x07) << 18) | (second << 12) | (cont(index + 2) << 6) | cont(index + 3);
      units.push(0xd800 + ((value - 0x10000) >> 10), 0xdc00 + ((value - 0x10000) & 0x3ff));
      index += 4;
    } else {
      throw undecodable("utf-8");
    }
  }
  return fromUnits(units);
}

function fromUnits(units: readonly number[]): string {
  let out = "";
  for (let index = 0; index < units.length; index += 8192) out += String.fromCharCode(...units.slice(index, index + 8192));
  return out;
}

/** rawDecode 的结果：end 按码点（Python 的 str 下标，kit_hub 把它写进“第 %d 个字符处”），endUnits 按 UTF-16 下标。 */
export interface RawDecoded {
  readonly value: PyValue;
  readonly end: number;
  readonly endUnits: number;
}

/**
 * json.JSONDecoder().raw_decode(text, idx)：从 index（UTF-16 下标）处解析一个值，后面可以跟别的内容。
 * 不跳过开头的空白，也不查 BOM（kit_hub.py:1117、1142 与 pi_dispatch.py:2641 在用）。
 */
export function rawDecode(text: string, index = 0): RawDecoded {
  const [value, endUnits] = scanValue(text, index, 0, PY_BUILDER);
  return { value, end: codePointIndex(text, endUnits), endUnits };
}
