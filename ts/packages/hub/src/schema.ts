// 交差 schema 的子集校验器（迁移第 ⑤a 片，kit_hub.py 231–329 行）：schema_problems、_type_ok、js_pattern、schema_errors。
// js_pattern 是 Python 在模拟 JS 的判定（数字、单词、空白类只认 ASCII，$ 只在真正的末尾）：这里照它的写法交给 pyregex，报错文字与
// Python 的 re.error 逐字相同。值的比较（const、enum）照 Python 的 == 与 in。
import { PyCrash, pyLenValue, pyPercentD, pyReprValue, pyStrValue, pyTypeName } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { cmpCodePoints, codePoints } from "@themis/base/pyre";
import { FLAG_ASCII, type PyPattern, PyReError, compilePy } from "@themis/base/pyregex";
import { pyEq } from "@themis/base/pyvalue";

const BS = String.fromCharCode(92);

/** 内核复核 schema 时只认这些关键字（themistally-15 定的子集）。 */
export const SCHEMA_KEYWORDS: ReadonlySet<string> = new Set([
  "type", "properties", "required", "additionalProperties", "enum", "const", "items", "minLength", "maxLength", "pattern", "description",
]);

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** schema 用到了子集之外的关键字：内核复核不了的写法，不许出现在 schemas/ 里。 */
export function schemaProblems(schema: PyValue, where = "$"): string[] {
  if (!isDict(schema)) return [`${where} 不是对象`];
  const extra = [...schema.keys()].map((key) => pyStrValue(key)).filter((key) => !SCHEMA_KEYWORDS.has(key)).sort(cmpCodePoints);
  const problems = extra.map((key) => `${where} 用了子集之外的关键字 ${key}`);
  if (schema.has("additionalProperties") && schema.get("additionalProperties") !== false) {
    problems.push(`${where} 的 additionalProperties 只能写 false`);
  }
  if (schema.has("pattern")) {
    const pattern = pyStrValue(schema.get("pattern") as PyValue);
    if (!codePoints(pattern).every((char) => (char.codePointAt(0) as number) < 0x80)) {
      problems.push(`${where} 的 pattern 只能写 ASCII`);
    } else {
      try {
        jsPattern(pattern);
      } catch (error) {
        if (!(error instanceof PyReError)) throw error;
        problems.push(`${where} 的 pattern 内核编不过（${error.message}）`);
      }
      if (pattern.includes("(?P")) problems.push(`${where} 的 pattern 用了 JS 不认的 (?P…)`);
    }
  }
  for (const [key, sub] of items(orEmpty(schema.get("properties")))) problems.push(...schemaProblems(sub, `${where}.${pyStrValue(key)}`));
  if (schema.has("items")) problems.push(...schemaProblems(schema.get("items") as PyValue, `${where}[]`));
  return problems;
}

/** _type_ok：与 TypeBox 一样，4.0 也算整数；布尔不算数字。 */
export function typeOk(kind: PyValue, value: PyValue): boolean {
  if (typeof value === "boolean" && (kind === "integer" || kind === "number")) return false;
  if (kind === "integer") return typeof value === "bigint" || (typeof value === "number" && Number.isInteger(value));
  if (kind === "number") return typeof value === "bigint" || typeof value === "number";
  if (kind === "object") return isDict(value);
  if (kind === "array") return Array.isArray(value);
  if (kind === "string") return typeof value === "string";
  if (kind === "boolean") return typeof value === "boolean";
  if (kind === "null") return value === null;
  return false;
}

/** js_pattern：字符类之外、没有转义的 $ 换成“只在末尾”的锚点，再按 re.ASCII 编译。 */
export function jsPattern(pattern: string): PyPattern {
  let out = "";
  let escaped = false;
  let inClass = false;
  for (const char of pattern) {
    if (escaped) {
      out += char;
      escaped = false;
    } else if (char === BS) {
      out += char;
      escaped = true;
    } else if (char === "[" && !inClass) {
      inClass = true;
      out += char;
    } else if (char === "]" && inClass) {
      inClass = false;
      out += char;
    } else {
      out += char === "$" && !inClass ? `${BS}Z` : char;
    }
  }
  return compilePy(out, FLAG_ASCII);
}

/** 按 SCHEMA_KEYWORDS 那个子集校验：pi 的 TypeBox 先校验过一遍，这里是内核的复核。 */
export function schemaErrors(schema: PyDict, value: PyValue, where = "$"): string[] {
  const kinds = schema.get("type") ?? null;
  if (kinds !== null && !(Array.isArray(kinds) ? kinds : [kinds]).some((kind) => typeOk(kind, value))) {
    return [`${where} 应当是 ${pyStrValue(kinds)}`];
  }
  const errors: string[] = [];
  if (schema.has("const") && !pyEq(value, schema.get("const") as PyValue)) errors.push(`${where} 应当等于 ${pyReprValue(schema.get("const") as PyValue)}`);
  if (schema.has("enum")) {
    const options = schema.get("enum") as PyValue;
    if (!pyIn(value, options)) errors.push(`${where} 只能是 ${iterate(options).map(pyStrValue).join("、")} 之一`);
  }
  if (typeof value === "string") {
    if (schema.has("minLength") && lessThan(pyLenValue(value), schema.get("minLength") as PyValue)) {
      errors.push(`${where} 至少 ${pyPercentD(schema.get("minLength"))} 个字符`);
    }
    if (schema.has("maxLength") && lessThan(schema.get("maxLength") as PyValue, pyLenValue(value))) {
      errors.push(`${where} 至多 ${pyPercentD(schema.get("maxLength"))} 个字符`);
    }
    if (schema.has("pattern")) {
      const pattern = schema.get("pattern") as PyValue;
      if (typeof pattern !== "string") throw new PyCrash("TypeError", `'${pyTypeName(pattern)}' object is not iterable`);
      if (jsPattern(pattern).search(value) === null) errors.push(`${where} 不符合 ${pattern}`);
    }
  }
  if (isDict(value)) {
    const properties = orEmpty(schema.get("properties"));
    for (const key of iterate(orEmptyList(schema.get("required")))) {
      if (!dictHas(value, key)) errors.push(`${where} 缺 ${pyStrValue(key)}`);
    }
    if (schema.get("additionalProperties") === false) {
      for (const key of value.keys()) if (!pyIn(key, properties)) errors.push(`${where} 多了 ${pyStrValue(key)}`);
    }
    for (const [key, sub] of items(properties)) {
      if (dictHas(value, key)) {
        if (!isDict(sub)) throw new PyCrash("AttributeError", `'${pyTypeName(sub)}' object has no attribute 'get'`);
        const found = [...value].find(([item]) => pyEq(item as PyValue, key)) as [unknown, PyValue];
        errors.push(...schemaErrors(sub, found[1], `${where}.${pyStrValue(key)}`));
      }
    }
  }
  const itemSchema = schema.get("items");
  if (Array.isArray(value) && isDict(itemSchema)) {
    value.forEach((item, index) => errors.push(...schemaErrors(itemSchema, item, `${where}[${index}]`)));
  }
  return errors;
}

/** `x or {}`：假值换成空 dict。 */
function orEmpty(value: PyValue | undefined): PyValue {
  return value === undefined || !truthy(value) ? new Map() : value;
}

function orEmptyList(value: PyValue | undefined): PyValue {
  return value === undefined || !truthy(value) ? [] : value;
}

function truthy(value: PyValue): boolean {
  if (value === null || value === false || value === "" || value === 0n || value === 0) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (value instanceof Map) return value.size > 0;
  return true;
}

/** dict.items()：不是 dict 照 Python 报 AttributeError。 */
function items(value: PyValue): [PyValue, PyValue][] {
  if (!isDict(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'items'`);
  return [...value].map(([key, item]) => [key as PyValue, item]);
}

/** for x in value：list 照元素、dict 照键、str 照码点；其余照 Python 报不可迭代。 */
function iterate(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return value;
  if (isDict(value)) return [...value.keys()].map((key) => key as PyValue);
  if (typeof value === "string") return codePoints(value);
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not iterable`);
}

/** value in container（list、dict 的键、str 的子串）。 */
function pyIn(value: PyValue, container: PyValue): boolean {
  if (typeof container === "string") {
    if (typeof value !== "string") throw new PyCrash("TypeError", `'in <string>' requires string as left operand, not ${pyTypeName(value)}`);
    return container.includes(value);
  }
  if (isDict(container)) return dictHas(container, value);
  return iterate(container).some((item) => pyEq(value, item));
}

/** key in dict：键照 Python 的 == 比（1 与 1.0 与 True 是同一个键）。 */
function dictHas(dict: PyDict, key: PyValue): boolean {
  if (Array.isArray(key) || isDict(key)) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(key)}'`);
  return [...dict.keys()].some((item) => pyEq(item as PyValue, key));
}

/** a < b，照 Python 比较数字；不能比的照 Python 报 TypeError。 */
function lessThan(a: PyValue, b: PyValue): boolean {
  const number = (value: PyValue): number | bigint => {
    if (typeof value === "boolean") return value ? 1n : 0n;
    if (typeof value === "bigint" || typeof value === "number") return value;
    throw new PyCrash("TypeError", `'<' not supported between instances of '${pyTypeName(a)}' and '${pyTypeName(b)}'`);
  };
  const left = number(a);
  const right = number(b);
  if (typeof left === "bigint" && typeof right === "bigint") return left < right;
  return Number(left) < Number(right);
}
