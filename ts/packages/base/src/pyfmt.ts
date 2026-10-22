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
