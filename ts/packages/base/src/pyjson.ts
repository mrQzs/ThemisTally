// Python 兼容的 JSON：逐字节复刻 Python 3.12 标准库 json.dumps / json.loads（迁移第 ① 步，计划第 1.4 节）。
//
// 现行实现的信件 sha256、合同摘要、内容锁、state.json 都是 json.dumps 写出的字节，TS 版必须写出一模一样的字节；
// 读进来、改完、写回时也不能丢掉 Python 的区别。所以值不用 JSON.parse 的结果表示，而用 PyValue：
//   - Python int ↔ bigint（任意大小），Python float ↔ number（含 -0.0、NaN、±Infinity）；
//   - Python dict ↔ Map（保持插入顺序；JS 对象会把整数样的键提到前面）；键可以是 str、int、float、bool、None；
//   - Python str ↔ string（可以含孤立代理项：Python 到 encode 才报错，见 encodeUtf8）。
// 已知的限制：Map 按 SameValueZero 比较键，-0.0 作键会并成 0.0（Python 的 dict 保留 -0.0）；1 与 1.0、True
// 在 Python 里是同一个键，在 Map 里是三个。现行代码的 dict 键只来自 JSON（都是字符串）或代码自己写定，
// 遇不到这两种情况；契约测试也不覆盖它们。
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

function checkIntDigits(digits: number): void {
  if (digits > INT_MAX_STR_DIGITS) {
    throw new PyJsonError(
      "ValueError",
      `Exceeds the limit (${INT_MAX_STR_DIGITS} digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit`,
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
    throw new PyJsonError("UnicodeEncodeError", "'utf-8' codec can't encode character: surrogates not allowed");
  }
  return new TextEncoder().encode(text);
}

// ---------------------------------------------------------------------------
// json.loads
// ---------------------------------------------------------------------------

const NUMBER_RE = /(-?(?:0|[1-9]\d*))(\.\d+)?([eE][-+]?\d+)?/y;
const WHITESPACE_RE = /[ \t\n\r]*/y;
const HEX4_RE = /^[0-9a-fA-F]{4}$/;
const SIMPLE_ESCAPES: Record<string, string> = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };

function decodeError(message: string, position: number): PyJsonError {
  return new PyJsonError("JSONDecodeError", `${message}: char ${position}`);
}

function skipWhitespace(text: string, index: number): number {
  WHITESPACE_RE.lastIndex = index;
  WHITESPACE_RE.exec(text);
  return WHITESPACE_RE.lastIndex;
}

/** json.decoder.scanstring（strict=True）：end 指向开头引号之后。返回（字符串，收尾引号之后的位置）。 */
function scanString(text: string, end: number): [string, number] {
  const begin = end - 1;
  let out = "";
  let index = end;
  for (;;) {
    if (index >= text.length) throw decodeError("Unterminated string starting at", begin);
    const char = text[index] ?? "";
    const unit = text.charCodeAt(index);
    if (char === '"') return [out, index + 1];
    if (char !== "\\") {
      if (unit < 0x20) throw decodeError("Invalid control character at", index);
      out += char;
      index += 1;
      continue;
    }
    const escape = text[index + 1];
    if (escape === undefined) throw decodeError("Unterminated string starting at", begin);
    if (escape !== "u") {
      const simple = SIMPLE_ESCAPES[escape];
      if (simple === undefined) throw decodeError("Invalid \\escape", index);
      out += simple;
      index += 2;
      continue;
    }
    const first = text.slice(index + 2, index + 6);
    if (!HEX4_RE.test(first)) throw decodeError("Invalid \\uXXXX escape", index + 1);
    let codePoint = parseInt(first, 16);
    index += 6;
    if (codePoint >= 0xd800 && codePoint <= 0xdbff && text.slice(index, index + 2) === "\\u") {
      const second = text.slice(index + 2, index + 6);
      if (!HEX4_RE.test(second)) throw decodeError("Invalid \\uXXXX escape", index + 1);
      const low = parseInt(second, 16);
      if (low >= 0xdc00 && low <= 0xdfff) {
        codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + (low - 0xdc00);
        index += 6;
      }
    }
    out += String.fromCodePoint(codePoint);
  }
}

function parseNumber(text: string, index: number): [bigint | number, number] | null {
  NUMBER_RE.lastIndex = index;
  const match = NUMBER_RE.exec(text);
  if (match === null) return null;
  const [whole, integer = "", fraction, exponent] = match;
  const end = index + whole.length;
  if (fraction !== undefined || exponent !== undefined) return [Number(whole), end];
  checkIntDigits(integer.length - (integer.startsWith("-") ? 1 : 0));
  return [BigInt(integer), end];
}

function scanValue(text: string, index: number, depth: number): [PyValue, number] {
  // 嵌套极深时 Python 报 RecursionError；具体在第几层取决于解释器的递归上限，契约不比较这个层数
  if (depth > 1000) throw new PyJsonError("RecursionError", "maximum recursion depth exceeded while decoding a JSON object");
  const char = text[index];
  if (char === undefined) throw decodeError("Expecting value", index);
  if (char === '"') return scanString(text, index + 1);
  if (char === "{") return scanObject(text, index + 1, depth + 1);
  if (char === "[") return scanArray(text, index + 1, depth + 1);
  if (char === "n" && text.startsWith("null", index)) return [null, index + 4];
  if (char === "t" && text.startsWith("true", index)) return [true, index + 4];
  if (char === "f" && text.startsWith("false", index)) return [false, index + 5];
  if (char === "N" && text.startsWith("NaN", index)) return [NaN, index + 3];
  if (char === "I" && text.startsWith("Infinity", index)) return [Infinity, index + 8];
  if (char === "-" && text.startsWith("-Infinity", index)) return [-Infinity, index + 9];
  const number = parseNumber(text, index);
  if (number === null) throw decodeError("Expecting value", index);
  return number;
}

function scanObject(text: string, index: number, depth: number): [PyDict, number] {
  const out: PyDict = new Map();
  let position = skipWhitespace(text, index);
  if (text[position] === "}") return [out, position + 1];
  for (;;) {
    if (text[position] !== '"') throw decodeError("Expecting property name enclosed in double quotes", position);
    const [key, afterKey] = scanString(text, position + 1);
    position = skipWhitespace(text, afterKey);
    if (text[position] !== ":") throw decodeError("Expecting ':' delimiter", position);
    position = skipWhitespace(text, position + 1);
    const [value, afterValue] = scanValue(text, position, depth);
    out.set(key, value); // 重复的键：Python 的 dict 保留第一次出现的位置、最后一次的值，Map.set 同样
    position = skipWhitespace(text, afterValue);
    if (text[position] === "}") return [out, position + 1];
    if (text[position] !== ",") throw decodeError("Expecting ',' delimiter", position);
    position = skipWhitespace(text, position + 1);
  }
}

function scanArray(text: string, index: number, depth: number): [PyValue[], number] {
  const out: PyValue[] = [];
  let position = skipWhitespace(text, index);
  if (text[position] === "]") return [out, position + 1];
  for (;;) {
    const [value, afterValue] = scanValue(text, position, depth);
    out.push(value);
    position = skipWhitespace(text, afterValue);
    if (text[position] === "]") return [out, position + 1];
    if (text[position] !== ",") throw decodeError("Expecting ',' delimiter", position);
    position = skipWhitespace(text, position + 1);
  }
}

/** json.loads(str)：与 Python 3.12 一致，接受 NaN、Infinity、-Infinity；整数与浮点分开（bigint / number）。 */
export function loads(text: string): PyValue {
  if (text.startsWith("\ufeff")) throw decodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)", 0);
  const [value, end] = scanValue(text, skipWhitespace(text, 0), 0);
  const tail = skipWhitespace(text, end);
  if (tail !== text.length) throw decodeError("Extra data", tail);
  return value;
}
