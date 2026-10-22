// clock 的契约：时间与编号的格式（值随时间与随机数变，契约比较格式、取值范围与次序）。每套实现逐条通过，
// Python 实现先过。两套实现会同时往同一个信箱发信，所以还要求：混着生成的编号，按文件名排序就是按时间排序。
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeResult, runProbe } from "./harness.ts";

const SENDERS = ["站主", "内核", "womovie-c8", "exec-step"];
const ALIAS: Record<string, string> = { 站主: "owner", 内核: "kernel", "womovie-c8": "womovie-c8", "exec-step": "exec-step" };
const COMPACT = "\\d{8}T\\d{12}Z";

function sample(impl: (typeof IMPLS)[number], count: number): { result: ProbeResult; before: number; after: number } {
  const before = Date.now();
  const result = runProbe(impl, { op: "clock.sample", count, senders: SENDERS, attempts: [1, 7, 42, 999, 1000, 12345] });
  return { result, before, after: Date.now() };
}

/** 20261022T010203123456Z → 毫秒时间戳（截到毫秒）。 */
function compactMillis(text: string): number {
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})\d{3}Z/.exec(text);
  if (!match) return NaN;
  const [, y, mo, d, h, mi, s, ms] = match.map(Number) as number[];
  return Date.UTC(y ?? 0, (mo ?? 1) - 1, d ?? 1, h ?? 0, mi ?? 0, s ?? 0, ms ?? 0);
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

describe.each(IMPLS)("clock 契约 impl=$name", (impl) => {
  it("T01 utc_now：YYYY-MM-DDTHH:MM:SSZ，取的是当时的 UTC 时间（秒，截断）", () => {
    const { result, before, after } = sample(impl, 3);
    const values = [...strings(result["utc_now"]), ...strings(result["pd_utc_now"])];
    expect(values).toHaveLength(6);
    for (const value of values) {
      expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
      const at = Date.parse(value);
      expect(at).toBeGreaterThanOrEqual(Math.floor(before / 1000) * 1000);
      expect(at).toBeLessThanOrEqual(after);
    }
  });

  it("T02 utc_compact：YYYYMMDDTHHMMSS 加六位微秒加 Z，取的是当时的 UTC 时间，次序不倒退", () => {
    const { result, before, after } = sample(impl, 50);
    const values = strings(result["utc_compact"]);
    expect(values).toHaveLength(50);
    for (const value of values) {
      expect(value).toMatch(new RegExp(`^${COMPACT}$`));
      expect(compactMillis(value)).toBeGreaterThanOrEqual(before - 1);
      expect(compactMillis(value)).toBeLessThanOrEqual(after);
    }
    expect([...values].sort()).toEqual(values);
  });

  it("T03 信件编号：<utc_compact>-<发信人>-<6 位十六进制>，站主写 owner、内核写 kernel，一个进程里不重复", () => {
    const { result } = sample(impl, 100);
    const ids = result["msg_ids"] as Record<string, string[]>;
    for (const sender of SENDERS) {
      expect(ids[sender]).toHaveLength(100);
      for (const id of ids[sender] ?? []) expect(id).toMatch(new RegExp(`^${COMPACT}-${ALIAS[sender]}-[0-9a-f]{6}$`));
    }
    const all = Object.values(ids).flat();
    expect(new Set(all).size).toBe(all.length);
  });

  it("T04 回合编号：<utc_compact>-<4 位十六进制>；审计编号：aud-<32 位十六进制>", () => {
    const { result } = sample(impl, 20);
    for (const id of strings(result["turn_ids"])) expect(id).toMatch(new RegExp(`^${COMPACT}-[0-9a-f]{4}$`));
    for (const id of strings(result["audit_ids"])) expect(id).toMatch(/^aud-[0-9a-f]{32}$/);
    expect(strings(result["turn_ids"])).toHaveLength(20);
    expect(new Set(strings(result["audit_ids"])).size).toBe(20);
  });

  it("T05 attempt 目录名：attempt-%03d，满 1000 照写", () => {
    const { result } = sample(impl, 1);
    expect(result["attempt_dirs"]).toEqual(["attempt-001", "attempt-007", "attempt-042", "attempt-999", "attempt-1000", "attempt-12345"]);
  });
});

describe("clock 对照：两套实现混着发信", () => {
  // 信箱按文件名排序。同一微秒里生成的编号靠随机后缀分先后，哪一套实现都不保证次序；
  // 要保证的是时间前缀不倒退：后生成的信，前缀不比先生成的小，不管是哪一套实现写的。
  it("轮流用三种运行方式各生成信件编号，时间前缀按生成的次序不倒退", () => {
    const generated: string[] = [];
    for (let round = 0; round < 3; round += 1) {
      for (const impl of IMPLS) {
        const ids = (sample(impl, 2).result["msg_ids"] as Record<string, string[]>)["womovie-c8"] ?? [];
        generated.push(...ids);
      }
    }
    expect(generated).toHaveLength(18);
    const prefixes = generated.map((id) => id.slice(0, 22));
    expect([...prefixes].sort()).toEqual(prefixes);
  });
});
