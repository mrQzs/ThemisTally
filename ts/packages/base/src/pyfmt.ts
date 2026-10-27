// Python 内置函数在 JSON 值上的语义：repr、str、真值、len，以及 print 写 stdout 的字节（迁移第 ② 步）。
// 证据文件里的值来自 json.loads，类型只有 None、bool、int、float、str、list、dict（pyjson 的 PyValue）。
// 不是这些类型能回答的（例如对 int 取 len、对 list 取 .get），Python 会抛异常、打印堆栈；这里抛 PyCrash，
// 由入口按“崩溃”处理（退出码 1，stderr 不逐字比较，见契约）。
import { writeSync } from "node:fs";
import { type PyDict, type PyKey, type PyValue, floatRepr, intRepr } from "./pyjson.ts";
import { codePoints, pyIsPrintable } from "./pyre.ts";

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

/** a + b 在 JSON 值上的语义：int 与 bool 相加仍是 int，有 float 就是 float，其余类型照 Python 抛 TypeError。 */
export function pyAdd(a: PyValue, b: PyValue): bigint | number {
  const asInt = (value: PyValue): bigint | null => (typeof value === "bigint" ? value : typeof value === "boolean" ? (value ? 1n : 0n) : null);
  const left = asInt(a);
  const right = asInt(b);
  if (left !== null && right !== null) return left + right;
  const numeric = (value: PyValue): boolean => typeof value === "number" || asInt(value) !== null;
  if (numeric(a) && numeric(b)) return Number(left ?? a) + Number(right ?? b);
  throw new PyCrash("TypeError", `unsupported operand type(s) for +: '${pyTypeName(a)}' and '${pyTypeName(b)}'`);
}

/** sum(values, start)。 */
export function pySum(values: readonly PyValue[], start: bigint | number = 0n): bigint | number {
  return values.reduce<bigint | number>((total, value) => pyAdd(total, value), start);
}

function writeAll(fd: number, bytes: Buffer): void {
  let offset = 0;
  while (offset < bytes.length) offset += writeSync(fd, bytes, offset, bytes.length - offset);
}

/** 照 Python 的 print 往 stdout、stderr 写（同步写，进程退出前不会丢）。 */
export class PyOut {
  print(text = ""): void {
    writeAll(1, pyTextBytes(`${text}\n`));
  }

  /** sys.stdout.write(text)：不加换行。 */
  write(text: string): void {
    writeAll(1, pyTextBytes(text));
  }

  printErr(text = ""): void {
    writeAll(2, pyTextBytes(`${text}\n`));
  }
}
