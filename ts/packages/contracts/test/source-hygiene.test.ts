// 源码卫生：ts/packages 与 ts/mutations 里不许有看不见的字符（BOM、不间断空格、控制字符、行分隔符、代理项），
// 一律写成转义。2026-10-22 写 pyjson 时，编辑工具把源码里 U+FEFF、U+00A0 的转义换成了实际字符：行为没变，
// 但变异清单的锚点对不上，人也看不出来。按码点的数值判断，本文件自己不写任何转义，免得再被换掉。
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
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

/**
 * 桌面端本机服务的本机 HTTP 安全基线（桌面端设计 T8）先写在 ts/packages/ui/src/localhttp/，到迁移第 ③d 步由规划端
 * 整体搬进 @themis/base（与 themistally-15 定，2026-10-23）。为了搬家时只是机械地移动文件：localhttp 只许导入
 * node:*、@themis/base/* 与 localhttp 内部的相对路径；不碰 Bun 的全局对象（Bun.serve 只在服务那一层的薄适配里，
 * 接口按 WHATWG 的 Request、Response、Headers 写）。返回违规说明，合规时为空。
 */
export function localhttpViolations(source: string, fileDir: string, localhttpDir: string): string[] {
  const found: string[] = [];
  const pattern = /\b(?:import|export)\b[^;"'`]*?\bfrom\s*(["'])([^"']*)\1|\bimport\s*(["'])([^"']*)\3|\bimport\s*\(\s*([^)]*)\)|\brequire\s*\(\s*([^)]*)\)/gu;
  for (const match of source.matchAll(pattern)) {
    const literal = match[2] ?? match[4];
    const dynamic = match[5] ?? match[6];
    let specifier: string | undefined = literal;
    if (dynamic !== undefined) {
      const quoted = /^(["'])([^"']*)\1$/u.exec(dynamic.trim());
      if (quoted === null) {
        found.push(`动态导入的目标不是字面量：${dynamic.trim()}`);
        continue;
      }
      specifier = quoted[2];
    }
    if (specifier === undefined) continue;
    if (specifier.startsWith("node:") || specifier.startsWith("@themis/base/")) continue;
    if (specifier.startsWith("./") || specifier.startsWith("../")) {
      const target = relative(localhttpDir, resolve(fileDir, specifier));
      if (target !== "" && !target.startsWith("..") && !isAbsolute(target)) continue; // 留在 localhttp 里面
    }
    found.push(`不许导入 ${specifier}`);
  }
  if (/\bBun\s*\./u.test(source)) found.push("不许用 Bun 的全局对象（Bun.serve 只在服务那一层的薄适配里）");
  return found;
}

describe("localhttp 的导入（桌面端 T8，③d 之前留在 ui 包里）", () => {
  const dir = join(ROOT, "packages", "ui", "src", "localhttp");

  it("规则：node:*、@themis/base/* 与 localhttp 内部的相对路径可以，别的不行", () => {
    const sub = join(dir, "sub");
    const ok = [
      'import { createHash } from "node:crypto";',
      'import type { X } from "@themis/base/secrets";',
      'export { a } from "./cookie.ts";',
      'import { b } from "../limits.ts";',
      'const m = await import("node:fs");',
    ].join("\n");
    expect(localhttpViolations(ok, sub, dir)).toEqual([]);
    for (const bad of [
      'import { serve } from "../../server.ts";',
      'import { x } from "@themis/dispatcher/repo";',
      'import "../../main.ts";',
      'const m = await import(name);',
      'const z = require("zlib");',
      'import { y } from "vitest";',
      "Bun.serve({ fetch });",
    ]) {
      expect(localhttpViolations(bad, sub, dir), bad).not.toEqual([]);
    }
  });

  it("ts/packages/ui/src/localhttp 下的源码照规则导入", () => {
    let names: string[] = [];
    try {
      names = files(dir).filter((path) => path.endsWith(".ts"));
    } catch {
      names = []; // 还没建：第 1 片之前
    }
    const found = names.flatMap((path) =>
      localhttpViolations(readFileSync(path, "utf8"), dirname(path), dir).map((problem) => `${relative(ROOT, path)}：${problem}`));
    expect(found).toEqual([]);
  });
});

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
