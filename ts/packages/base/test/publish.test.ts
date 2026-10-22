// publishNew 的白盒测试：契约观察不到的内部约定（临时文件的位置与命名、O_EXCL、发布之外的错误照样抛出）。
// 外部行为由 packages/contracts 的契约测试与对照测试覆盖。
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { publishNew, tmpPathFor } from "../src/publish.ts";

vi.mock("node:fs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:fs")>();
  return { ...actual, linkSync: vi.fn(actual.linkSync), openSync: vi.fn(actual.openSync), closeSync: vi.fn(actual.closeSync) };
});
vi.mock("node:crypto", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:crypto")>();
  return { ...actual, randomBytes: vi.fn(actual.randomBytes) };
});

const NONCE = Buffer.from("0123456789abcdef", "hex");

function thrown(action: () => unknown): unknown {
  try {
    action();
  } catch (error) {
    return error;
  }
  throw new Error("预期抛错，实际没有");
}

describe("publishNew 的内部约定", () => {
  let dir = "";
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "themis-publish-"));
  });
  afterEach(() => {
    vi.mocked(fs.linkSync).mockRestore();
    vi.mocked(fs.openSync).mockRestore();
    vi.mocked(fs.closeSync).mockRestore();
    vi.mocked(crypto.randomBytes).mockRestore();
    rmSync(dir, { recursive: true, force: true });
  });

  it("临时文件在目标同一目录，名字是 <目标名>.<16 位十六进制>.tmp", () => {
    expect(tmpPathFor(join(dir, "letter.md"), NONCE)).toBe(join(dir, "letter.md.0123456789abcdef.tmp"));
  });

  it("用 8 个随机字节起临时文件名，发布的就是那个临时文件", () => {
    vi.mocked(crypto.randomBytes).mockImplementationOnce(() => NONCE);
    expect(publishNew(join(dir, "letter.md"), new Uint8Array([1, 2, 3]))).toBe(true);
    expect(vi.mocked(crypto.randomBytes)).toHaveBeenCalledWith(8);
    expect(vi.mocked(fs.linkSync)).toHaveBeenCalledWith(join(dir, "letter.md.0123456789abcdef.tmp"), join(dir, "letter.md"));
  });

  it("临时文件名撞上已有文件：报 EEXIST，不碰那个文件，目标也不建", () => {
    vi.mocked(crypto.randomBytes).mockImplementationOnce(() => NONCE);
    const occupied = join(dir, "letter.md.0123456789abcdef.tmp");
    writeFileSync(occupied, "别人的文件");
    expect(thrown(() => publishNew(join(dir, "letter.md"), new Uint8Array([1])))).toMatchObject({ code: "EEXIST" });
    expect(readFileSync(occupied, "utf8")).toBe("别人的文件");
    expect(readdirSync(dir)).toEqual(["letter.md.0123456789abcdef.tmp"]);
  });

  it("发布那一步的其他错误原样抛出，不当成“别人已抢先发布”，临时文件照样删掉", () => {
    vi.mocked(fs.linkSync).mockImplementationOnce(() => {
      throw Object.assign(new Error("EPERM: operation not permitted, link"), { code: "EPERM" });
    });
    expect(thrown(() => publishNew(join(dir, "letter.md"), new Uint8Array([1])))).toMatchObject({ code: "EPERM" });
    expect(readdirSync(dir)).toEqual([]);
  });

  it("临时文件的描述符用完就关：成功、已存在、发布报错三条路都关（hub 每封信发布一次，泄漏会耗尽句柄）", () => {
    const opened = (): unknown[] => vi.mocked(fs.openSync).mock.results.map((result) => result.value);
    const closed = (): unknown[] => vi.mocked(fs.closeSync).mock.calls.map((call) => call[0]);
    publishNew(join(dir, "letter.md"), new Uint8Array([1]));
    publishNew(join(dir, "letter.md"), new Uint8Array([2]));
    vi.mocked(fs.linkSync).mockImplementationOnce(() => {
      throw Object.assign(new Error("EPERM"), { code: "EPERM" });
    });
    thrown(() => publishNew(join(dir, "other.md"), new Uint8Array([3])));
    expect(opened()).toHaveLength(3);
    expect(closed()).toEqual(opened());
  });

  it("发布成功之后不留临时文件；目标已存在时同样不留", () => {
    expect(publishNew(join(dir, "letter.md"), new Uint8Array([1]))).toBe(true);
    expect(publishNew(join(dir, "letter.md"), new Uint8Array([2]))).toBe(false);
    expect(readdirSync(dir)).toEqual(["letter.md"]);
    expect([...readFileSync(join(dir, "letter.md"))]).toEqual([1]);
  });
});
