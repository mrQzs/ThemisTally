// publish_new 的行为契约（来源：pi_dispatch.py 的 publish_new 说明，3.0 第二轮 D5）：
// 原子发布、从不覆盖。目标已存在（哪怕只读）返回 false、字节不变；其余错误原样抛出；
// 正式文件只会从“不存在”变成“完整”，不留临时文件。每一套实现都要逐条通过。
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { IMPLS, b64, removeDir, runProbe, scratchDir, seededBytes, snapshot, startProbe } from "./harness.ts";

const ALL_BYTES = Uint8Array.from({ length: 256 }, (_, index) => index);
const OLD = new TextEncoder().encode("已经发布的版本\n");

describe.each(IMPLS)("publish_new 契约 impl=$name", (impl) => {
  let dir = "";
  beforeEach(() => {
    dir = scratchDir(impl.name);
  });
  afterEach(() => {
    const target = join(dir, "letter.md");
    if (existsSync(target)) chmodSync(target, 0o666); // Windows 上只读文件删不掉
    removeDir(dir);
  });

  it("C1 目标不存在：返回 true，字节原样，不留临时文件", () => {
    const data = new TextEncoder().encode("第一封信\n");
    expect(runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(data) })).toEqual({
      ok: true,
      published: true,
    });
    expect(snapshot(dir)).toEqual({ "letter.md": b64(data) });
  });

  it("C2 目标已存在：返回 false，原字节不变，不留临时文件", () => {
    writeFileSync(join(dir, "letter.md"), OLD);
    const result = runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(ALL_BYTES) });
    expect(result).toEqual({ ok: true, published: false });
    expect(snapshot(dir)).toEqual({ "letter.md": b64(OLD) });
  });

  it("C3 目标是只读文件：返回 false，原字节不变", () => {
    writeFileSync(join(dir, "letter.md"), OLD);
    chmodSync(join(dir, "letter.md"), 0o444);
    const result = runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(ALL_BYTES) });
    expect(result).toEqual({ ok: true, published: false });
    expect(snapshot(dir)).toEqual({ "letter.md": b64(OLD) });
  });

  it("C4 目录不存在：报 ENOENT，什么也不建", () => {
    const result = runProbe(impl, { op: "publish_new", path: join(dir, "missing", "letter.md"), data_b64: b64(OLD) });
    expect(result).toEqual({ ok: false, error: "ENOENT" });
    expect(snapshot(dir)).toEqual({});
  });

  it("C5 空数据：返回 true，建出空文件", () => {
    expect(runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: "" })).toEqual({
      ok: true,
      published: true,
    });
    expect(snapshot(dir)).toEqual({ "letter.md": "" });
  });

  it("C6 任意字节原样写入：0–255 全部字节、CRLF、NUL 都不转换", () => {
    const data = new Uint8Array([...ALL_BYTES, 13, 10, 0, 10, 13]);
    runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(data) });
    expect(new Uint8Array(readFileSync(join(dir, "letter.md")))).toEqual(data);
  });

  it("C7 目标是目录：返回 false，目录不变", () => {
    mkdirSync(join(dir, "letter.md"));
    const result = runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(OLD) });
    expect(result).toEqual({ ok: true, published: false });
    expect(snapshot(dir)).toEqual({ "letter.md": "<dir>" });
    expect(snapshot(join(dir, "letter.md"))).toEqual({});
  });

  it("C8 并发发布：恰好一个返回 true，文件是它的数据，不留临时文件", async () => {
    const barrier = join(dir, "..", `${dir.split(/[\\/]/).pop() ?? "x"}.go`);
    const datas = Array.from({ length: 6 }, (_, index) => seededBytes(index + 1, 2000 + index));
    const probes = datas.map((data) =>
      startProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(data), barrier }),
    );
    try {
      await Promise.all(probes.map((probe) => probe.ready));
      writeFileSync(barrier, "");
      const results = await Promise.all(probes.map((probe) => probe.result));
      const winners = results.flatMap((result, index) => (result.ok && result.published ? [index] : []));
      expect(results.every((result) => result.ok)).toBe(true);
      expect(winners).toHaveLength(1);
      expect(snapshot(dir)).toEqual({ "letter.md": b64(datas[winners[0] ?? -1] ?? new Uint8Array()) });
    } finally {
      for (const probe of probes) probe.stop();
      removeDir(barrier);
    }
  });

  it("C9 大数据（4 MiB）完整写入", () => {
    const data = seededBytes(42, 4 * 1024 * 1024);
    expect(runProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(data) })).toEqual({
      ok: true,
      published: true,
    });
    expect(Buffer.from(readFileSync(join(dir, "letter.md"))).equals(Buffer.from(data))).toBe(true);
  });
});
