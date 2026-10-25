// SSE 与监视器的单元用例（桌面端 §5.3、T3、D04/D05/D06）：四个常量由一条用例钉住；watch.ts 的指纹只 stat 内核名单上
// 的输入——名单之外的变化不触发、名单上的变化触发、根目录是重解析点时整轮是固定一行。不起真服务，直接调纯函数。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  DEBOUNCE_MS,
  HEARTBEAT_MS,
  MAX_SUBSCRIPTIONS,
  MAX_SUBSCRIPTIONS_PER_SESSION,
  RETRY_MS,
  STAT_INTERVAL_MS,
} from "../src/events.ts";
import { fingerprint } from "../src/watch.ts";

let dir = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-events-"));
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

const runs = (): string => join(dir, ".agent", "runs");

/** 建一个 attempt 目录并写文件。 */
function attempt(task: string, name: string): string {
  const path = join(runs(), task, name);
  mkdirSync(path, { recursive: true });
  return path;
}

function put(rel: string, content: string): void {
  const path = join(runs(), rel);
  mkdirSync(join(path, ".."), { recursive: true });
  writeFileSync(path, content, "utf8");
}

describe("SSE 的四个常量（D04）", () => {
  it("STAT_INTERVAL_MS=2000、DEBOUNCE_MS=300、HEARTBEAT_MS=15000、RETRY_MS=3000 被钉住", () => {
    expect(STAT_INTERVAL_MS).toBe(2000);
    expect(DEBOUNCE_MS).toBe(300);
    expect(HEARTBEAT_MS).toBe(15000);
    expect(RETRY_MS).toBe(3000); // retry 一行恒为 3000
  });

  it("订阅上限：全局 16、每会话 4", () => {
    expect(MAX_SUBSCRIPTIONS).toBe(16);
    expect(MAX_SUBSCRIPTIONS_PER_SESSION).toBe(4);
  });
});

describe("watch 的指纹只 stat 名单上的输入（D05/D06）", () => {
  it("一个已结束的 attempt：基础指纹稳定，重复跑相同", async () => {
    const a = attempt("demo-task", "attempt-001");
    writeFileSync(join(a, "state.json"), '{"state":"PASS"}', "utf8");
    mkdirSync(join(a, "checks", "01"), { recursive: true });
    writeFileSync(join(a, "checks", "01", "checks.json"), "{}", "utf8");
    mkdirSync(join(a, "verdicts"), { recursive: true });
    writeFileSync(join(a, "verdicts", "1.json"), "{}", "utf8");
    mkdirSync(join(a, "claim"), { recursive: true });
    const first = await fingerprint(dir);
    const second = await fingerprint(dir);
    expect(second).toBe(first);
    expect(first).not.toBe("");
  });

  it("名单之外的变化不触发：_tmp/x、attempt 下的 notes.txt、verdicts 下的 readme.txt、非 attempt-NNN 的目录", async () => {
    const a = attempt("demo-task", "attempt-001");
    writeFileSync(join(a, "state.json"), '{"state":"PASS"}', "utf8");
    mkdirSync(join(runs(), "_tmp"), { recursive: true }); // _tmp 先是名单里的一个 task
    const base = await fingerprint(dir);
    put("_tmp/x", "临时"); // _tmp 下的文件：不是 attempt-NNN，不进指纹
    put("demo-task/attempt-001/notes.txt", "名单之外");
    put("demo-task/attempt-001/verdicts/readme.txt", "名单之外");
    mkdirSync(join(runs(), "demo-task", "attempt-x"), { recursive: true }); // 不是 attempt-NNN
    mkdirSync(join(runs(), "demo-task", "notes"), { recursive: true });
    const after = await fingerprint(dir);
    expect(after).toBe(base);
  });

  it("名单上的变化触发：checks 下新增 02/checks.json、verdicts 下新增 1.json、claim 出现、state.json 变长", async () => {
    const a = attempt("demo-task", "attempt-001");
    const base = await fingerprint(dir);
    mkdirSync(join(a, "checks", "02"), { recursive: true });
    writeFileSync(join(a, "checks", "02", "checks.json"), "{}", "utf8");
    expect(await fingerprint(dir)).not.toBe(base);
    const afterChecks = await fingerprint(dir);
    mkdirSync(join(a, "verdicts"), { recursive: true });
    writeFileSync(join(a, "verdicts", "1.json"), "{}", "utf8");
    expect(await fingerprint(dir)).not.toBe(afterChecks);
    const afterVerdicts = await fingerprint(dir);
    mkdirSync(join(a, "claim"), { recursive: true });
    expect(await fingerprint(dir)).not.toBe(afterVerdicts);
    const afterClaim = await fingerprint(dir);
    writeFileSync(join(a, "state.json"), '{"state":"RUNNING","more":true}', "utf8");
    expect(await fingerprint(dir)).not.toBe(afterClaim);
  });

  it("read_when_running 的 events.jsonl 变长也触发", async () => {
    const a = attempt("demo-task", "attempt-001");
    const base = await fingerprint(dir);
    writeFileSync(join(a, "events.jsonl"), '{"type":"a"}\n', "utf8");
    const after1 = await fingerprint(dir);
    expect(after1).not.toBe(base);
    writeFileSync(join(a, "events.jsonl"), '{"type":"a"}\n{"type":"b"}\n', "utf8");
    expect(await fingerprint(dir)).not.toBe(after1);
  });

  it("attempt_pattern 只认 attempt-NNN：attempt-01、attempt-x 不进指纹", async () => {
    mkdirSync(join(runs(), "demo-task"), { recursive: true }); // task 先在基线里
    const base = await fingerprint(dir);
    mkdirSync(join(runs(), "demo-task", "attempt-01"), { recursive: true }); // 少于三位
    mkdirSync(join(runs(), "demo-task", "attempt-x"), { recursive: true });
    expect(await fingerprint(dir)).toBe(base);
    mkdirSync(join(runs(), "demo-task", "attempt-001"), { recursive: true }); // 三位，进
    expect(await fingerprint(dir)).not.toBe(base);
  });
});
