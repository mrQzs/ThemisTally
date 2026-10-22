// jsonl 的契约：账本 .agent/mailbox/ledger/events.jsonl 的追加与读取（kit_hub.Hub.append_event 与读账本的写法）。
// 每套实现逐条通过，Python 实现先过。对照部分：两套实现同时往同一份账本追加，行不交错、不丢、各自的次序不乱。
// 特殊字符用 String.fromCodePoint 拼。
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import type { Tagged } from "../src/tagged.ts";
import { IMPLS, type Impl, removeDir, runProbe, scratchDir, startProbe } from "./harness.ts";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const ledgerOf = (repo: string): string => join(repo, ".agent", "mailbox", "ledger", "events.jsonl");
const S = (v: string): Tagged => ({ t: "str", v });
const D = (...v: [string, Tagged][]): Tagged => ({ t: "dict", v: v.map(([key, value]) => [S(key), value] as const) });

describe.each(IMPLS)("jsonl 契约 impl=$name", (impl) => {
  it("J1 一行一条：键排序、不转义非 ASCII、带 at 与 event、末尾换行；文件与目录不存在就建，已有的接着追加", () => {
    const repo = scratchDir(`jsonl-${impl.name}`);
    try {
      const data = D(["at", S("调用方给的 at 会被盖掉")], ["zeta", { t: "int", hex: "1" }], ["alpha", S(`中${C(0x1f600)}`)], ["nested", D(["b", { t: "float", bits: "3ff8000000000000" }], ["a", { t: "none" }])]);
      expect(runProbe(impl, { op: "jsonl.append", repo, event: "letter.delivered", data })).toMatchObject({ ok: true });
      expect(runProbe(impl, { op: "jsonl.append", repo, event: "letter.taken" })).toMatchObject({ ok: true });
      const lines = readFileSync(ledgerOf(repo), "utf8").split("\n");
      expect(lines).toHaveLength(3);
      expect(lines[2]).toBe("");
      expect(lines[0]).toMatch(
        new RegExp(`^\\{"alpha": "中${C(0x1f600)}", "at": "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z", "event": "letter.delivered", "nested": \\{"a": null, "b": 1.5\\}, "zeta": 1\\}$`, "u"),
      );
      expect(lines[1]).toMatch(/^\{"at": "[^"]+", "event": "letter.taken"\}$/);
    } finally {
      removeDir(repo);
    }
  });

  it("J2 读账本：read_text 之后 splitlines、逐行解析，坏行跳过；U+2028 也被当成行界（现行行为，拆坏的那行跳过）", () => {
    const repo = scratchDir(`jsonl-read-${impl.name}`);
    try {
      const path = ledgerOf(repo);
      mkdirSync(join(repo, ".agent", "mailbox", "ledger"), { recursive: true });
      const text =
        '{"event": "a", "n": 1}\r\n' +
        "这一行坏了\n" +
        `{"event": "b", "x": "前${C(0x2028)}后"}\n` +
        `{"event": "c"}${C(0x85)}{"event": "d"}\n` +
        "\n" +
        '{"event": "e", "big": 9007199254740993}';
      writeFileSync(path, text);
      const result = runProbe(impl, { op: "jsonl.read", path });
      expect(result["ok"]).toBe(true);
      const events = (result["value"] as { v: { v: [Tagged, Tagged][] }[] }).v.map((item) =>
        item.v.find(([key]) => (key as { v: string }).v === "event")?.[1],
      );
      expect(events).toEqual([S("a"), S("c"), S("d"), S("e")]);
    } finally {
      removeDir(repo);
    }
  });

  it("J3 值里有孤立代理项：与 Python 一样写不出去，账本里什么也不多", () => {
    const repo = scratchDir(`jsonl-bad-${impl.name}`);
    try {
      runProbe(impl, { op: "jsonl.append", repo, event: "ok" });
      const before = readFileSync(ledgerOf(repo), "utf8");
      const result = runProbe(impl, { op: "jsonl.append", repo, event: "bad", data: D(["x", S(`a${String.fromCharCode(0xd800)}`)]) });
      expect(result).toMatchObject({ ok: false, error: "UnicodeEncodeError" });
      expect(readFileSync(ledgerOf(repo), "utf8")).toBe(before);
    } finally {
      removeDir(repo);
    }
  });

  it("J4 别的进程拿着 .events.lock 时，追加等它放手才写（持锁的是另一套实现）", async () => {
    const repo = scratchDir(`jsonl-wait-${impl.name}`);
    const lockPath = join(repo, ".agent", "mailbox", "ledger", ".events.lock");
    mkdirSync(dirname(lockPath), { recursive: true });
    const other = IMPLS.find((candidate) => candidate.name !== impl.name) as Impl;
    const holder = startProbe(other, { op: "filelock.run", path: lockPath, hold_ms: 1500, signal: true });
    try {
      await holder.ready;
      const appended = runProbe(impl, { op: "jsonl.append", repo, event: "waited" });
      const held = await holder.result;
      expect(appended["ok"]).toBe(true);
      expect(Number(appended["done_ms"])).toBeGreaterThanOrEqual(Number(held["released_ms"]));
      expect(readFileSync(ledgerOf(repo), "utf8").split("\n").filter(Boolean)).toHaveLength(1);
    } finally {
      holder.stop();
      removeDir(repo);
    }
  }, 60_000);

  it("J5 账本不存在读出空表；嵌套极深的一行与 Python 一样报 RecursionError，不当坏行跳过", () => {
    const repo = scratchDir(`jsonl-deep-${impl.name}`);
    try {
      expect(runProbe(impl, { op: "jsonl.read", path: ledgerOf(repo) })).toEqual({ ok: true, value: { t: "list", v: [] } });
      mkdirSync(dirname(ledgerOf(repo)), { recursive: true });
      writeFileSync(ledgerOf(repo), `{"event": "a"}\n${"[".repeat(100_000)}${"]".repeat(100_000)}\n`);
      expect(runProbe(impl, { op: "jsonl.read", path: ledgerOf(repo) })).toEqual({ ok: false, error: "RecursionError" });
    } finally {
      removeDir(repo);
    }
  });
});

describe("jsonl 对照：两套实现同时往一份账本追加", () => {
  it("Python、Node、Bun 各两个进程同时各追加 40 条：一共 240 行，每行都完整，各自的次序不乱，读出来三套实现一样", async () => {
    const repo = scratchDir("jsonl-race");
    const barrier = `${repo}.go`;
    const writers = IMPLS.flatMap((impl) => [0, 1].map((slot) => ({ impl, id: `${impl.name}-${slot}` })));
    const probes = writers.map(({ impl, id }) =>
      startProbe(impl, { op: "jsonl.append", repo, event: "race", data: D(["writer", S(id)]), count: 40, barrier }),
    );
    try {
      await Promise.all(probes.map((probe) => probe.ready));
      writeFileSync(barrier, "");
      const results = await Promise.all(probes.map((probe) => probe.result));
      expect(results.every((result) => result.ok)).toBe(true);
      const lines = readFileSync(ledgerOf(repo), "utf8").split("\n").filter(Boolean);
      expect(lines).toHaveLength(240);
      const seqs = new Map<string, number[]>();
      for (const line of lines) {
        const record = JSON.parse(line) as { writer: string; seq: number; event: string };
        expect(record.event).toBe("race");
        seqs.set(record.writer, [...(seqs.get(record.writer) ?? []), record.seq]);
      }
      for (const { id } of writers) expect(seqs.get(id)).toEqual(Array.from({ length: 40 }, (_, index) => index));
      const reads = IMPLS.map((impl: Impl) => JSON.stringify(runProbe(impl, { op: "jsonl.read", path: ledgerOf(repo) })));
      expect(new Set(reads).size).toBe(1);
    } finally {
      for (const probe of probes) probe.stop();
      removeDir(barrier);
      removeDir(repo);
    }
  }, 120_000);
});
