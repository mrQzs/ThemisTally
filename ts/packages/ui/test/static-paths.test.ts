// 静态资源的目录边界（桌面端 T13、D09、D10）：每一类拒绝都有自己的 reason，逐类钉住；路径只解码一次，双重编码的
// %252e%252e 解码一次是字面文件名、回 404。junction 一路在 Node 下（lstat）与 Bun 下（GetFileAttributesW）各测一次。
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync, type Stats } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { CONTENT_TYPES, INDEX_FILE, isReparsePoint, isWithin, rawPathOf, resolveAsset } from "../src/static.ts";
import { RESOLVE_ASSET_PROBE, bunPath } from "./harness.ts";

let root = "";
let outside = "";
let canary = "";

beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-static-"));
  root = join(dir, "assets");
  outside = join(dir, "outside");
  mkdirSync(join(root, "assets"), { recursive: true });
  mkdirSync(join(root, "sub"), { recursive: true });
  mkdirSync(outside, { recursive: true });
  writeFileSync(join(root, INDEX_FILE), "<!doctype html><title>T015</title>\n");
  writeFileSync(join(root, "assets", "app.js"), "// T015-APP-JS-MARKER\n");
  writeFileSync(join(root, "notes.xyz"), "T015-NOTES-XYZ\n");
  writeFileSync(join(root, "icon.PNG"), "png-bytes");
  canary = `T015-CANARY-${Math.random().toString(16).slice(2)}`;
  writeFileSync(join(outside, "secret.txt"), `${canary}\n`);
  // junction：assets 里面一个指向目录外的重解析点
  symlinkSync(outside, join(root, "link"), "junction");
});

afterAll(() => {
  rmSync(join(root, ".."), { recursive: true, force: true });
});

const reasonOf = (pathname: string): string => {
  const result = resolveAsset(root, pathname);
  if (result.ok) throw new Error(`${pathname} 竟然解析成功了：${result.path}`);
  return result.reason;
};

const statusOf = (pathname: string): number => {
  const result = resolveAsset(root, pathname);
  return result.ok ? 200 : result.status;
};

describe("Content-Type 白名单", () => {
  it("白名单照合同，/ 映射到 index.html", () => {
    expect(INDEX_FILE).toBe("index.html");
    expect(CONTENT_TYPES["html"]).toBe("text/html; charset=utf-8");
    expect(CONTENT_TYPES["js"]).toBe("text/javascript; charset=utf-8");
    expect(CONTENT_TYPES["mjs"]).toBe("text/javascript; charset=utf-8");
    expect(CONTENT_TYPES["css"]).toBe("text/css; charset=utf-8");
    expect(CONTENT_TYPES["json"]).toBe("application/json; charset=utf-8");
    expect(CONTENT_TYPES["txt"]).toBe("text/plain; charset=utf-8");
    expect(CONTENT_TYPES["woff2"]).toBe("font/woff2");
    expect(CONTENT_TYPES["woff"]).toBe("font/woff");
    expect(CONTENT_TYPES["svg"]).toBe("image/svg+xml");
    expect(CONTENT_TYPES["png"]).toBe("image/png");
    expect(CONTENT_TYPES["ico"]).toBe("image/x-icon");
  });

  it("后缀不分大小写；不在表里的一律 type-not-allowed", () => {
    const upper = resolveAsset(root, "/icon.PNG");
    expect(upper).toMatchObject({ ok: true, contentType: "image/png" });
    expect(reasonOf("/notes.xyz")).toBe("type-not-allowed");
    expect(reasonOf("/assets/app.js.bak")).toBe("not-found"); // 不存在：先判存在，再判后缀
  });
});

describe("逐类的拒绝", () => {
  it(".. 段：dot-segment", () => {
    expect(reasonOf("/../secret.txt")).toBe("dot-segment");
    expect(reasonOf("/assets/../../secret.txt")).toBe("dot-segment");
    expect(reasonOf("/..")).toBe("dot-segment");
  });

  it("编码过的点与分隔符（不分大小写）：encoded-dot-or-separator", () => {
    expect(reasonOf("/..%2f..%2fsecret.txt")).toBe("encoded-dot-or-separator");
    expect(reasonOf("/%2e%2e%2fsecret.txt")).toBe("encoded-dot-or-separator");
    expect(reasonOf("/x%5c..%5csecret.txt")).toBe("encoded-dot-or-separator");
    expect(reasonOf("/..%2F..%2Fsecret.txt")).toBe("encoded-dot-or-separator");
    expect(reasonOf("/%2E%2E%2Fsecret.txt")).toBe("encoded-dot-or-separator");
    expect(reasonOf("/x%5C..%5Csecret.txt")).toBe("encoded-dot-or-separator");
  });

  it("%00 与其余控制字符：control-char", () => {
    expect(reasonOf("/secret%00.txt")).toBe("control-char");
    expect(reasonOf("/a%01b.txt")).toBe("control-char");
    expect(reasonOf("/a%7fb.txt")).toBe("control-char");
  });

  it("坏编码：bad-encoding", () => {
    expect(reasonOf("/%zz.txt")).toBe("bad-encoding");
    expect(reasonOf("/%e4%b8")).toBe("bad-encoding");
  });

  it("反斜杠：backslash", () => {
    expect(reasonOf("/x\\..\\secret.txt")).toBe("backslash");
    expect(reasonOf("/a\\b.txt")).toBe("backslash");
  });

  it("盘符：drive-letter", () => {
    expect(reasonOf("/C:/windows/win.ini")).toBe("drive-letter");
    expect(reasonOf("/c:secret.txt")).toBe("drive-letter");
  });

  it("UNC 的空段：empty-segment", () => {
    expect(reasonOf("//server/share")).toBe("empty-segment");
    expect(reasonOf("/a//b.txt")).toBe("empty-segment");
  });

  it("冒号（ADS）：colon", () => {
    expect(reasonOf("/index.html:stream")).toBe("colon");
    expect(reasonOf("/dir/a:b.txt")).toBe("colon"); // 非首段的冒号（ADS）
  });

  it("末尾的点或空格：trailing-dot-or-space", () => {
    expect(reasonOf("/index.html.")).toBe("trailing-dot-or-space");
    expect(reasonOf("/assets/app.js ")).toBe("trailing-dot-or-space");
    expect(reasonOf("/sub.")).toBe("trailing-dot-or-space");
  });

  it("junction：reparse-point", () => {
    expect(reasonOf("/link/secret.txt")).toBe("reparse-point");
    expect(reasonOf("/link")).toBe("reparse-point");
    expect(isReparsePoint(join(root, "link"))).toBe(true);
  });

  it("目录外：outside-root（isWithin 为假）", () => {
    expect(isWithin(root, join(root, "index.html"))).toBe(true);
    expect(isWithin(root, join(root, "assets", "app.js"))).toBe(true);
    expect(isWithin(root, join(root, "..", "outside", "secret.txt"))).toBe(false);
    expect(isWithin(root, join(root, ".."))).toBe(false);
    expect(isWithin(root, root)).toBe(false);
  });

  it("目录：directory", () => {
    expect(reasonOf("/sub")).toBe("directory");
  });

  it("不存在：not-found", () => {
    expect(reasonOf("/missing.txt")).toBe("not-found");
    expect(reasonOf("/assets/missing.js")).toBe("not-found");
  });
});

describe("只解码一次", () => {
  it("原始 pathname 上的 %2f、%5c、%2e、%00 先于解码被拒绝", () => {
    expect(statusOf("/..%2f..%2fsecret.txt")).toBe(400);
    expect(statusOf("/%2e%2e%2fsecret.txt")).toBe(400);
    expect(statusOf("/x%5c..%5csecret.txt")).toBe(400);
    expect(statusOf("/secret%00.txt")).toBe(400);
  });

  it("双重编码的 %252e%252e 只解码一次：字面文件名，回 404", () => {
    expect(reasonOf("/%252e%252e%252fsecret.txt")).toBe("not-found");
    expect(statusOf("/%252e%252e%252fsecret.txt")).toBe(404);
  });

  it("正常路径解析成目录内的文件", () => {
    expect(resolveAsset(root, "/")).toMatchObject({ ok: true, contentType: "text/html; charset=utf-8" });
    const app = resolveAsset(root, "/assets/app.js");
    expect(app.ok && app.contentType).toBe("text/javascript; charset=utf-8");
    expect(app.ok && app.path).toBe(join(root, "assets", "app.js"));
  });

  it("rawPathOf 不做规范化：%2f 原样留下，反斜杠换成 / 是 HTTP 层已经做过的事", () => {
    expect(rawPathOf(new URL("http://127.0.0.1:1/..%2f..%2fsecret.txt"))).toBe("/..%2f..%2fsecret.txt");
    expect(rawPathOf(new Request("http://127.0.0.1:1/assets/app.js"))).toBe("/assets/app.js");
    expect(rawPathOf("http://127.0.0.1:1/")).toBe("/");
  });
});

describe("Bun 下的重解析点", () => {
  it("GetFileAttributesW 认得 junction（探针在 Bun 里跑）", () => {
    const out = execFileSync(bunPath(), [RESOLVE_ASSET_PROBE, root, "/link/secret.txt"], { encoding: "utf8" });
    expect(JSON.parse(out)).toEqual({ ok: false, status: 403, reason: "reparse-point" });
    const ok = execFileSync(bunPath(), [RESOLVE_ASSET_PROBE, root, "/assets/app.js"], { encoding: "utf8" });
    expect(JSON.parse(ok)).toMatchObject({ ok: true, contentType: "text/javascript; charset=utf-8" });
  });
});

describe("只读普通文件（T18）", () => {
  it("注入的 stat 说不是普通文件：404 not-a-file；目录仍记 directory，普通文件照常解析", () => {
    const notFile = { isDirectory: () => false, isFile: () => false } as unknown as Stats;
    expect(resolveAsset(root, "/assets/app.js", { stat: () => notFile })).toEqual({
      ok: false,
      status: 404,
      reason: "not-a-file",
    });
    const directory = { isDirectory: () => true, isFile: () => false } as unknown as Stats;
    expect(resolveAsset(root, "/assets/app.js", { stat: () => directory })).toEqual({
      ok: false,
      status: 404,
      reason: "directory",
    });
    const file = { isDirectory: () => false, isFile: () => true } as unknown as Stats;
    expect(resolveAsset(root, "/assets/app.js", { stat: () => file })).toMatchObject({
      ok: true,
      contentType: "text/javascript; charset=utf-8",
    });
  });
});
