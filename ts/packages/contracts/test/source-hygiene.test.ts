// 源码卫生：ts/packages 与 ts/mutations 里不许有看不见的字符（BOM、不间断空格、控制字符、行分隔符、代理项），
// 一律写成转义。2026-10-22 写 pyjson 时，编辑工具把源码里 U+FEFF、U+00A0 的转义换成了实际字符：行为没变，
// 但变异清单的锚点对不上，人也看不出来。按码点的数值判断，本文件自己不写任何转义，免得再被换掉。
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const SCANNED = /\.(ts|py|json|md)$/;

/**
 * 看不见或会弄乱行的码元。TAB 与行尾的 CR 不算。代理项不查：按 UTF-8 读出来的不会有孤立代理项，成对的是
 * 补充平面的正常字符；孤立代理项的转义要是被写坏，读出来是替换字符 U+FFFD，所以查它。
 */
export function invisible(unit: number): boolean {
  return (
    unit <= 0x08 ||
    (unit >= 0x0b && unit <= 0x1f) ||
    unit === 0x7f ||
    unit === 0xa0 ||
    unit === 0xad ||
    (unit >= 0x200b && unit <= 0x200f) ||
    unit === 0x2028 ||
    unit === 0x2029 ||
    unit === 0x2060 ||
    unit === 0xfeff ||
    unit === 0xfffd
  );
}

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (name === "node_modules") return [];
    return statSync(path).isDirectory() ? files(path) : SCANNED.test(name) ? [path] : [];
  });
}

function hits(path: string): string[] {
  return readFileSync(path, "utf8")
    .split("\n")
    .flatMap((raw, index) => {
      const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
      for (let at = 0; at < line.length; at += 1) {
        const unit = line.charCodeAt(at);
        if (invisible(unit)) return [`${relative(ROOT, path)}:${index + 1} U+${unit.toString(16).padStart(4, "0")}`];
      }
      return [];
    });
}

describe("源码卫生", () => {
  it("判断规则认得出 BOM、不间断空格、控制字符、行分隔符与替换字符，放过补充平面字符的代理对", () => {
    expect([0xfeff, 0xa0, 0x00, 0x1b, 0x2028, 0xfffd].every(invisible)).toBe(true);
    expect([0x09, 0x20, 0x41, 0x4e2d, 0x7e, 0xd83d, 0xde00].some(invisible)).toBe(false);
  });

  it("ts/packages 与 ts/mutations 里没有看不见的字符", () => {
    const found = [...files(join(ROOT, "packages")), ...files(join(ROOT, "mutations"))].flatMap(hits);
    expect(found).toEqual([]);
  });
});
