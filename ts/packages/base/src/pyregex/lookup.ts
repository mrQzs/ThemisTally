// unicodedata.lookup(name) 在 re 的 \N{...} 里的用法：查得到单个字符就是它的码点，查不到或是具名序列（多个字符）为 null。
// 照 CPython 3.12 Modules/unicodedata.c 的 _getcode：
//   1. "HANGUL SYLLABLE " 开头（区分大小写）：按初声、中声、终声的短名拼（各取能匹配的最长那个，区分大小写），
//      必须正好用完；拼不成就是查不到，不再查表。
//   2. "CJK UNIFIED IDEOGRAPH-" 开头（区分大小写）：后面正好 4 或 5 位大写十六进制，且落在统一表意文字的区段里。
//   3. 其余查名字表（名字与别名），不分大小写，必须完全一致（不容许多余或缺少空格）。
import { gunzipSync } from "node:zlib";
import { inTable } from "../pyre.ts";
import { NAMES_GZ_B64 } from "./names.ts";
import { CJK_UNIFIED } from "./tables.ts";

const L_NAMES = ["G", "GG", "N", "D", "DD", "R", "M", "B", "BB", "S", "SS", "", "J", "JJ", "C", "K", "T", "P", "H"];
const V_NAMES = ["A", "AE", "YA", "YAE", "EO", "E", "YEO", "YE", "O", "WA", "WAE", "OE", "YO", "U", "WEO", "WE", "WI", "YU",
  "EU", "YI", "I"];
const T_NAMES = ["", "G", "GG", "GS", "N", "NJ", "NH", "D", "L", "LG", "LM", "LB", "LS", "LT", "LP", "LH", "M", "B", "BS",
  "S", "SS", "NG", "J", "C", "K", "T", "P", "H"];
const S_BASE = 0xac00;

/** unicodedata.c 的 find_syllable：取能匹配的最长短名；一个也没有时长度为 0、序号为 -1。 */
function findSyllable(text: string, names: readonly string[]): [length: number, index: number] {
  let length = -1;
  let index = -1;
  names.forEach((name, at) => {
    if (name.length <= length) return;
    if (text.startsWith(name)) {
      length = name.length;
      index = at;
    }
  });
  return [Math.max(length, 0), index];
}

function hangul(rest: string): number | null {
  let pos = 0;
  const [lLength, l] = findSyllable(rest.slice(pos), L_NAMES);
  pos += lLength;
  const [vLength, v] = findSyllable(rest.slice(pos), V_NAMES);
  pos += vLength;
  const [tLength, t] = findSyllable(rest.slice(pos), T_NAMES);
  pos += tLength;
  if (l < 0 || v < 0 || t < 0 || pos !== rest.length) return null;
  return S_BASE + (l * V_NAMES.length + v) * T_NAMES.length + t;
}

let table: Map<string, number> | null = null;

function names(): Map<string, number> {
  if (table === null) {
    table = new Map();
    for (const line of gunzipSync(Buffer.from(NAMES_GZ_B64, "base64")).toString("ascii").split("\n")) {
      const at = line.indexOf(";");
      if (at > 0) table.set(line.slice(at + 1).toUpperCase(), Number.parseInt(line.slice(0, at), 16));
    }
  }
  return table;
}

/** \N{name} 的字符；查不到（含具名序列）为 null。 */
export function lookupName(name: string): number | null {
  if (name.startsWith("HANGUL SYLLABLE ")) return hangul(name.slice(16));
  if (name.startsWith("CJK UNIFIED IDEOGRAPH-")) {
    const hex = name.slice(22);
    if ((hex.length !== 4 && hex.length !== 5) || !/^[0-9A-F]+$/u.test(hex)) return null;
    const cp = Number.parseInt(hex, 16);
    return inTable(CJK_UNIFIED, cp) ? cp : null;
  }
  if (!/^[\x20-\x7e]*$/u.test(name)) return null; // 名字都是 ASCII
  return names().get(name.toUpperCase()) ?? null;
}
