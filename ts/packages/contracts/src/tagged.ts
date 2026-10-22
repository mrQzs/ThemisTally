// 探针之间传 Python 值的“带标签编码”：普通 JSON 分不清 int 与 float、装不下大整数，dict 的键也只能是字符串。
//   int    → {"t":"int","hex":"-1f"}       十六进制：Python 的 int 与十进制串互转有 4300 位上限，十六进制不受限
//   float  → {"t":"float","bits":"3ff0…"}  IEEE 754 的 8 个字节（大端），-0.0、NaN、±Infinity 原样
//   dict   → {"t":"dict","v":[[键,值],…]}   保持插入顺序；键也带标签
//   str    → {"t":"str","v":"…"}           孤立代理项经 JSON 的 \uXXXX 原样传过去
// Python 一侧的同一套编码在 probes/python_probe.py。
import type { PyKey, PyValue } from "@themis/base/pyjson";

export type Tagged =
  | { readonly t: "none" }
  | { readonly t: "bool"; readonly v: boolean }
  | { readonly t: "int"; readonly hex: string }
  | { readonly t: "float"; readonly bits: string }
  | { readonly t: "str"; readonly v: string }
  | { readonly t: "list"; readonly v: readonly Tagged[] }
  | { readonly t: "dict"; readonly v: readonly (readonly [Tagged, Tagged])[] };

export function floatBits(value: number): string {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value);
  return Buffer.from(view.buffer).toString("hex");
}

export function bitsFloat(bits: string): number {
  // 小的 Buffer 共用 Node 的内存池：.buffer 是整个池，必须带上 byteOffset 读
  const bytes = Buffer.from(bits, "hex");
  return new DataView(bytes.buffer, bytes.byteOffset, 8).getFloat64(0);
}

export function toTagged(value: PyValue): Tagged {
  if (value === null) return { t: "none" };
  if (typeof value === "boolean") return { t: "bool", v: value };
  if (typeof value === "bigint") return { t: "int", hex: (value < 0n ? "-" : "") + (value < 0n ? -value : value).toString(16) };
  if (typeof value === "number") return { t: "float", bits: floatBits(value) };
  if (typeof value === "string") return { t: "str", v: value };
  if (Array.isArray(value)) return { t: "list", v: value.map(toTagged) };
  return { t: "dict", v: [...value.entries()].map(([key, item]) => [toTagged(key), toTagged(item)] as const) };
}

export function fromTagged(tagged: Tagged): PyValue {
  switch (tagged.t) {
    case "none":
      return null;
    case "bool":
      return tagged.v;
    case "int":
      return tagged.hex.startsWith("-") ? -BigInt("0x" + tagged.hex.slice(1)) : BigInt("0x" + tagged.hex);
    case "float":
      return bitsFloat(tagged.bits);
    case "str":
      return tagged.v;
    case "list":
      return tagged.v.map(fromTagged);
    case "dict":
      return new Map(tagged.v.map(([key, item]) => [fromTagged(key) as PyKey, fromTagged(item)]));
  }
}
