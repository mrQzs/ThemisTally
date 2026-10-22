// publish_new 对照测试：同一输入、两套实现（Python 与 TS；TS 再分 Node、Bun 两种运行方式）。
// 每个场景在各自的新目录里按同样的初始状态跑一遍，返回结果与目录里的全部字节都要逐字节一致。
// 场景按种子生成，失败时种子写在用例名里，可以单独重放。
import { chmodSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  IMPLS,
  type Impl,
  type ProbeResult,
  b64,
  removeDir,
  runProbe,
  scratchDir,
  seededBytes,
  snapshot,
  startProbe,
} from "./harness.ts";

const KINDS = ["absent", "exists", "readonly", "directory", "missing-parent"] as const;
type Kind = (typeof KINDS)[number];

interface Scenario {
  readonly seed: number;
  readonly kind: Kind;
  readonly data: Uint8Array;
  readonly old: Uint8Array;
}

function scenario(seed: number): Scenario {
  const sizes = seededBytes(seed * 7919, 4);
  const kind = KINDS[seed % KINDS.length] ?? "absent";
  const length = ((sizes[0] ?? 0) * 256 + (sizes[1] ?? 0)) % 8193; // 0–8192 字节，含空数据
  return { seed, kind, data: seededBytes(seed, length), old: seededBytes(seed + 100_000, (sizes[2] ?? 0) + 1) };
}

/** 按场景布置一个新目录，交给一套实现发布，返回它的结果与目录快照。 */
function runScenario(impl: Impl, item: Scenario): { result: ProbeResult; files: Record<string, string> } {
  const dir = scratchDir(`cmp-${impl.name}`);
  const target = item.kind === "missing-parent" ? join(dir, "missing", "letter.md") : join(dir, "letter.md");
  try {
    if (item.kind === "exists" || item.kind === "readonly") writeFileSync(target, item.old);
    if (item.kind === "readonly") chmodSync(target, 0o444);
    if (item.kind === "directory") mkdirSync(target);
    const result = runProbe(impl, { op: "publish_new", path: target, data_b64: b64(item.data) });
    return { result, files: snapshot(dir) };
  } finally {
    if (item.kind === "readonly" && existsSync(target)) chmodSync(target, 0o666);
    removeDir(dir);
  }
}

describe("publish_new 对照：同一输入，各实现的结果与磁盘字节一致", () => {
  const scenarios = Array.from({ length: 24 }, (_, index) => scenario(index + 1));
  it.each(scenarios.map((item) => [item.seed, item.kind, item] as const))("种子 %i（%s）", (_seed, _kind, item) => {
    const [first, ...rest] = IMPLS.map((impl) => ({ impl: impl.name, ...runScenario(impl, item) }));
    for (const other of rest) {
      expect({ impl: other.impl, result: other.result, files: other.files }).toEqual({
        impl: other.impl,
        result: first?.result,
        files: first?.files,
      });
    }
  });

  it("五种初始状态都覆盖到了", () => {
    expect(new Set(scenarios.map((item) => item.kind))).toEqual(new Set(KINDS));
  });
});

describe("publish_new 对照：两套实现混在一起抢同一个文件", () => {
  it.each([1, 2, 3])("第 %i 轮：九个进程（每套三个）只有一个发布成功，文件是它的数据", async (round) => {
    const dir = scratchDir(`race-${round}`);
    const barrier = `${dir}.go`;
    const racers = IMPLS.flatMap((impl) => [0, 1, 2].map((slot) => ({ impl, data: seededBytes(round * 100 + slot * 10 + impl.name.length, 1500) })));
    const probes = racers.map(({ impl, data }) =>
      startProbe(impl, { op: "publish_new", path: join(dir, "letter.md"), data_b64: b64(data), barrier }),
    );
    try {
      await Promise.all(probes.map((probe) => probe.ready));
      writeFileSync(barrier, "");
      const results = await Promise.all(probes.map((probe) => probe.result));
      expect(results.every((result) => result.ok)).toBe(true);
      const winners = results.flatMap((result, index) => (result.ok && result.published ? [index] : []));
      expect(winners).toHaveLength(1);
      expect(snapshot(dir)).toEqual({ "letter.md": b64(racers[winners[0] ?? -1]?.data ?? new Uint8Array()) });
    } finally {
      for (const probe of probes) probe.stop();
      removeDir(barrier);
      removeDir(dir);
    }
  });
});
