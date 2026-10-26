// Python 的 == 与 != 作用在 json.loads 读出的值上（迁移第 ③ 步：key_diff、preset 的比较、binding_tuple、插件锁的绑定）。
//   - bool、int、float 之间按数值比：True == 1 == 1.0；int 与 float 按精确值比（2**53+1 != 2.0**53），-0.0 == 0；
//   - NaN：单独比较时不等于自身；在 list、dict 里面时 Python 先比身份，而 json.loads 读出的 NaN 都是 json.decoder 里同一个
//     常量对象，所以容器里的 NaN 与 NaN 相等；
//   - dict 相等不看键序，list 要看次序；其余类型之间都不相等。
import type { PyDict, PyValue } from "./pyjson.ts";

/** a == b（顶层）。 */
export function pyEq(a: PyValue, b: PyValue): boolean {
  return equal(a, b, false);
}

function equal(a: PyValue, b: PyValue, nested: boolean): boolean {
  if (isNumber(a) && isNumber(b)) return numbersEqual(a, b, nested);
  if (a === null || b === null) return a === b;
  if (typeof a === "string" || typeof b === "string") return a === b;
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((item, index) => equal(item, b[index] as PyValue, true));
  }
  if (a instanceof Map && b instanceof Map) return dictsEqual(a, b);
  return false;
}

function dictsEqual(a: PyDict, b: PyDict): boolean {
  if (a.size !== b.size) return false;
  for (const [key, value] of a) {
    if (!b.has(key)) return false;
    if (!equal(value, b.get(key) as PyValue, true)) return false;
  }
  return true;
}

function isNumber(value: PyValue): value is boolean | bigint | number {
  return typeof value === "boolean" || typeof value === "bigint" || typeof value === "number";
}

function numbersEqual(a: boolean | bigint | number, b: boolean | bigint | number, nested: boolean): boolean {
  const left = typeof a === "boolean" ? BigInt(a) : a;
  const right = typeof b === "boolean" ? BigInt(b) : b;
  if (typeof left === "number" && typeof right === "number") return left === right || (nested && Number.isNaN(left) && Number.isNaN(right));
  if (typeof left === "bigint" && typeof right === "bigint") return left === right;
  const float = (typeof left === "number" ? left : right) as number;
  const int = (typeof left === "bigint" ? left : right) as bigint;
  return Number.isInteger(float) && BigInt(float) === int;
}
