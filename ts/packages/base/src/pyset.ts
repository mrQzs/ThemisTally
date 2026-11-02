// Python 的集合、字典键与排序（迁移第 ⑤c 片写在 hub 的 audit.ts 里，第 ⑤f 片搬到 base，战后门禁也要用）：
// 1、1.0、True 是同一个元素，list、dict 不能散列；sorted 照 CPython 3.12 的 list.sort，比较的先后与 Python 相同。
// 注意：Python 的集合按散列表的槽位迭代，str 的散列每个进程加的盐不同；PySet 按插入次序迭代。只有元素都能互相比较时，
// sorted 出来的结果才与次序无关（混了类型时 Python 自己报的是哪一对也不确定）。
import { PyCrash, pyTypeName } from "./pyfmt.ts";
import type { PyDict, PyKey, PyValue } from "./pyjson.ts";
import { cmpCodePoints } from "./pyre.ts";
import { pyEq } from "./pyvalue.ts";
/** 可散列的 JSON 值在 Python 里的相等类：1、1.0、True 是同一个；json.loads 出来的 NaN 都是同一个对象。 */
export function hashKey(value: PyValue): string {
  if (Array.isArray(value)) throw new PyCrash("TypeError", "unhashable type: 'list'");
  if (value instanceof Map) throw new PyCrash("TypeError", "unhashable type: 'dict'");
  if (value === null) return "N";
  if (typeof value === "string") return `S${value}`;
  if (typeof value === "boolean") return value ? "I1" : "I0";
  if (typeof value === "bigint") return `I${value}`;
  if (Number.isNaN(value)) return "NaN";
  if (Number.isInteger(value)) return `I${BigInt(value)}`;
  return `F${value}`;
}

/** Python 的集合（元素是可散列的 JSON 值）。 */
export class PySet {
  private readonly items = new Map<string, PyValue>();

  constructor(values: Iterable<PyValue> = []) {
    for (const value of values) this.add(value);
  }

  get size(): number {
    return this.items.size;
  }

  add(value: PyValue): void {
    const key = hashKey(value);
    if (!this.items.has(key)) this.items.set(key, value);
  }

  has(value: PyValue): boolean {
    return this.items.has(hashKey(value));
  }

  discard(value: PyValue): void {
    this.items.delete(hashKey(value));
  }

  values(): PyValue[] {
    return [...this.items.values()];
  }

  minus(other: PySet): PySet {
    return new PySet(this.values().filter((value) => !other.has(value)));
  }

  equals(other: PySet): boolean {
    return this.size === other.size && this.values().every((value) => other.has(value));
  }
}

/** Python 的字典（键是可散列的值，按 Python 的相等合并，保留先插入的那个键）。 */
export class PyKeyedDict {
  private readonly keys = new Map<string, PyKey>();
  private readonly values = new Map<string, PyValue>();

  has(key: PyKey): boolean {
    return this.keys.has(hashKey(key));
  }

  get(key: PyKey): PyValue | undefined {
    return this.values.get(hashKey(key));
  }

  set(key: PyKey, value: PyValue): void {
    const hash = hashKey(key);
    if (!this.keys.has(hash)) this.keys.set(hash, key);
    this.values.set(hash, value);
  }

  delete(key: PyKey): void {
    const hash = hashKey(key);
    this.keys.delete(hash);
    this.values.delete(hash);
  }

  toDict(): PyDict {
    return new Map([...this.keys].map(([hash, key]) => [key, this.values.get(hash) as PyValue]));
  }
}

/** Python 的 a < b（JSON 值）：数与数、字符串与字符串、列表与列表（按元素）可比，别的照 Python 抛 TypeError。 */
export function pyLess(a: PyValue, b: PyValue): boolean {
  const numeric = (value: PyValue): value is bigint | number | boolean => typeof value === "bigint" || typeof value === "number" || typeof value === "boolean";
  if (numeric(a) && numeric(b)) return compareNumbers(a, b) < 0;
  if (typeof a === "string" && typeof b === "string") return cmpCodePoints(a, b) < 0;
  if (Array.isArray(a) && Array.isArray(b)) {
    // 列表照 Python 按元素比：先用容器里的 ==（先比身份，json.loads 的 NaN 是同一个对象）找第一对不相等的，再对那一对做 <
    // （报错里的类型也是那一对的）；都相等时短的在前
    for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
      if (!pyEq([a[index] as PyValue], [b[index] as PyValue])) return pyLess(a[index] as PyValue, b[index] as PyValue);
    }
    return a.length < b.length;
  }
  throw new PyCrash("TypeError", `'<' not supported between instances of '${pyTypeName(a)}' and '${pyTypeName(b)}'`);
}

/** 两个数的大小，Python 的整数与浮点精确比较；有 NaN 时交回 NaN（比较都为假）。 */
function compareNumbers(a: bigint | number | boolean, b: bigint | number | boolean): number {
  const int = (value: bigint | number | boolean): bigint | number => (typeof value === "boolean" ? (value ? 1n : 0n) : value);
  const left = int(a);
  const right = int(b);
  if (typeof left === "bigint" && typeof right === "bigint") return left < right ? -1 : left > right ? 1 : 0;
  if (typeof left === "number" && typeof right === "number") return Number.isNaN(left) || Number.isNaN(right) ? Number.NaN : left - right;
  return typeof left === "bigint" ? intFloat(left, right as number) : -intFloat(right as bigint, left as number);
}

function intFloat(int: bigint, float: number): number {
  if (Number.isNaN(float)) return Number.NaN;
  if (float === Number.POSITIVE_INFINITY) return -1;
  if (float === Number.NEGATIVE_INFINITY) return 1;
  const floor = Math.floor(float);
  const whole = BigInt(floor);
  if (int !== whole) return int < whole ? -1 : 1;
  return floor === float ? 0 : -1;
}

/**
 * sorted(values)：照 CPython 3.12 的 list.sort，64 个以内先 count_run、再二分插入，比较的先后与 Python 相同，
 * 混了不能比的值时在同一处抛 TypeError，有 NaN 时排出来的次序也相同。更长的退回稳定的归并排序（全序时结果相同）。
 */
export function pySorted(values: readonly PyValue[]): PyValue[] {
  const items = [...values];
  const n = items.length;
  if (n < 2) return items;
  if (n >= 64) return mergeSort(items);
  let run = 2;
  if (pyLess(items[1] as PyValue, items[0] as PyValue)) {
    while (run < n && pyLess(items[run] as PyValue, items[run - 1] as PyValue)) run += 1;
    items.splice(0, run, ...items.slice(0, run).reverse());
  } else {
    while (run < n && !pyLess(items[run] as PyValue, items[run - 1] as PyValue)) run += 1;
  }
  for (let start = run; start < n; start += 1) {
    const pivot = items[start] as PyValue;
    let low = 0;
    let high = start;
    while (low < high) {
      const middle = low + ((high - low) >> 1);
      if (pyLess(pivot, items[middle] as PyValue)) high = middle;
      else low = middle + 1;
    }
    items.splice(start, 1);
    items.splice(low, 0, pivot);
  }
  return items;
}

function mergeSort(items: PyValue[]): PyValue[] {
  if (items.length < 2) return items;
  const middle = items.length >> 1;
  const left = mergeSort(items.slice(0, middle));
  const right = mergeSort(items.slice(middle));
  const out: PyValue[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) out.push(pyLess(right[j] as PyValue, left[i] as PyValue) ? (right[j++] as PyValue) : (left[i++] as PyValue));
  return [...out, ...left.slice(i), ...right.slice(j)];
}
