// 作业路由的替身用例（桌面端 §5.3、D13/D14/D16/D19）：严格参数校验每一类失败都回 400 且不起子进程；六个 kind 交给
// 执行器的 argv 与 JOB_ARGV 逐条一致；作业号 43 位随机；不在表里与格式不对回同一个 404；JOB_ALLOW 恰好六项全是
// undefined；doctor 输出里带敏感键的值被遮成 <redacted>。JobTable 的容量与淘汰直接单测（不起子进程）。
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { JOB_ID_RE, JobTable, type JobKind, markRunning, settle } from "../src/jobs.ts";
import { JOB_ALLOW, JOB_ARGV, JOB_KINDS, JOB_TIMEOUTS } from "../src/jobroutes.ts";
import { argvsOf, envelopeOf, readReport, startAppWithHub, type StartedAppWithHub } from "./support.ts";

let started: StartedAppWithHub | null = null;

beforeEach(() => {
  delete process.env["FAKE_KERNEL_JSON"];
  delete process.env["FAKE_KERNEL_STDERR"];
  delete process.env["FAKE_KERNEL_EXIT"];
  delete process.env["FAKE_KERNEL_SLEEP_MS"];
  delete process.env["FAKE_KERNEL_PLAN"];
});

afterEach(async () => {
  for (const name of ["FAKE_KERNEL_JSON", "FAKE_KERNEL_STDERR", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_SLEEP_MS", "FAKE_KERNEL_PLAN"]) {
    delete process.env[name];
  }
  await started?.dispose();
  started = null;
});

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "timed_out"]);

/** 建一个作业并等到终态，返回 GET 到的八键作业对象。 */
async function createAndWait(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const app = started as StartedAppWithHub;
  const created = await app.post("/api/v1/jobs", body);
  const job = (await created.json()) as Record<string, unknown>;
  const id = String(job["id"]);
  for (let i = 0; i < 200; i += 1) {
    const current = (await (await app.get(`/api/v1/jobs/${id}`)).json()) as Record<string, unknown>;
    if (TERMINAL.has(String(current["state"]))) return current;
    await sleep(25);
  }
  throw new Error("作业没有到终态");
}

/** JOB_ARGV 的示例参数（与登记表的示例值一致）。 */
const EXAMPLES: Record<JobKind, Record<string, unknown>> = {
  doctor: { kind: "doctor" },
  "doctor-record": { kind: "doctor-record", record: "demo-task.v1" },
  "runtime-scan": { kind: "runtime-scan" },
  "runtime-probe": { kind: "runtime-probe", runtime: "demo-runtime" },
  models: { kind: "models", runtime: "demo-runtime" },
  search: { kind: "search", pattern: "token", task: "demo-task", max: 50 },
};

describe("严格参数校验：每一类失败都回 400 且不起子进程（D13）", () => {
  it("正文不是对象、kind 不对、键多一个、少必填、类型不对、取值不合格都回 400，且没有起子进程", async () => {
    started = await startAppWithHub();
    const bad: unknown[] = [
      "x", // 字符串
      [1, 2], // 数组
      {}, // 没有 kind
      { kind: "nope" }, // kind 不在六个之内
      { kind: "doctor", extra: 1 }, // 未知键
      { kind: "doctor-record" }, // 少必填键
      { kind: "doctor-record", record: "BAD.v1" }, // record 不合 PLAN_KEY_RE
      { kind: "doctor-record", record: 5 }, // record 类型不对
      { kind: "runtime-probe", runtime: "Bad_Runtime" }, // runtime 不合 TASK_ID_RE
      { kind: "models", runtime: "-x" }, // runtime 以 - 开头
      { kind: "search", pattern: "x", max: true }, // max 是布尔
      { kind: "search", pattern: "x", max: 1.5 }, // max 是小数
      { kind: "search", pattern: "x", max: "5" }, // max 是字符串
      { kind: "search", pattern: "x", max: 0 }, // max 小于 1
      { kind: "search", pattern: "x", max: 1001 }, // max 大于 1000
      { kind: "search", pattern: "a\u0001b" }, // pattern 含控制字符
      { kind: "search", pattern: "x".repeat(513) }, // pattern 超过 512 个码点
      { kind: "search", pattern: "" }, // pattern 为空
      { kind: "search", pattern: "\uD800" }, // pattern 含孤立代理项
      { kind: "search", pattern: "x", task: "Bad_Task" }, // task 不合 TASK_ID_RE
    ];
    for (const body of bad) {
      const response = await started.post("/api/v1/jobs", body);
      expect(response.status, JSON.stringify(body).slice(0, 60)).toBe(400);
      const envelope = await envelopeOf(response);
      expect(envelope["ok"], JSON.stringify(body).slice(0, 60)).toBe(false);
      expect(envelope["exit_code"]).toBe(null);
      expect(envelope["messages"]).toHaveLength(1);
      expect(String((envelope["messages"] as string[])[0]).startsWith("ERROR: ")).toBe(true);
    }
    expect(argvsOf(started.report), "参数不合格不起子进程").toEqual([]);
  });

  it("合法基线：六类 kind 各建一次都成功（201）", async () => {
    started = await startAppWithHub();
    for (const kind of JOB_KINDS) {
      const response = await started.post("/api/v1/jobs", EXAMPLES[kind]);
      expect(response.status, kind).toBe(201);
    }
  });
});

describe("六个 kind 的 argv 与时限（D14）", () => {
  it("每个 kind 交给执行器的 argv 与 JOB_ARGV 逐条一致", async () => {
    started = await startAppWithHub();
    for (const kind of JOB_KINDS) {
      await createAndWait(EXAMPLES[kind]);
    }
    const seen = argvsOf(started.report);
    for (const kind of JOB_KINDS) {
      const want = [...(JOB_ARGV[kind] ?? [])];
      expect(seen.some((argv) => argv.length === want.length && argv.every((part, i) => part === want[i])), `${kind} 的 argv 应是 ${want.join(" ")}`).toBe(true);
    }
  });

  it("JOB_TIMEOUTS 照表（doctor 与 doctor-record 600、runtime-scan/probe 150、models 120、search 180）", () => {
    expect(JOB_TIMEOUTS["doctor"]).toBe(600);
    expect(JOB_TIMEOUTS["doctor-record"]).toBe(600);
    expect(JOB_TIMEOUTS["runtime-scan"]).toBe(150);
    expect(JOB_TIMEOUTS["runtime-probe"]).toBe(150);
    expect(JOB_TIMEOUTS["models"]).toBe(120);
    expect(JOB_TIMEOUTS["search"]).toBe(180);
  });
});

describe("作业号、404 与 409（D16/D18）", () => {
  it("作业号是 43 位 base64url、彼此不同、不连号", async () => {
    started = await startAppWithHub();
    const ids = new Set<string>();
    for (let i = 0; i < 5; i += 1) {
      const job = (await (await started.post("/api/v1/jobs", { kind: "doctor" })).json()) as Record<string, unknown>;
      const id = String(job["id"]);
      expect(id, id).toMatch(JOB_ID_RE);
      ids.add(id);
    }
    expect(ids.size).toBe(5); // 彼此不同
  });

  it("作业号格式不对与不在表里回同一个 404「没有这个作业」", async () => {
    started = await startAppWithHub();
    const badFormat = await started.get("/api/v1/jobs/abc");
    const unknown = await started.get(`/api/v1/jobs/${"B".repeat(43)}`);
    expect(badFormat.status).toBe(404);
    expect(unknown.status).toBe(404);
    const badText = await badFormat.text();
    const unknownText = await unknown.text();
    expect(badText).toBe(unknownText); // 两种 404 响应相同
    const unknownEnvelope = JSON.parse(unknownText) as Record<string, unknown>;
    expect(unknownEnvelope["messages"]).toEqual(["ERROR: 没有这个作业"]);
  });

  it("取消已结束的作业回 409「作业已经结束」", async () => {
    started = await startAppWithHub();
    const job = await createAndWait({ kind: "doctor" });
    const cancelled = await started.post(`/api/v1/jobs/${String(job["id"])}/cancel`, {});
    expect(cancelled.status).toBe(409);
    expect((await envelopeOf(cancelled))["messages"]).toEqual(["ERROR: 作业已经结束"]);
  });
});

describe("JOB_ALLOW 与二道脱敏（D19）", () => {
  it("JOB_ALLOW 恰好六项、全是 undefined", () => {
    expect(Object.keys(JOB_ALLOW).sort()).toEqual([...JOB_KINDS].sort());
    expect(Object.values(JOB_ALLOW).every((value) => value === undefined)).toBe(true);
  });

  it("doctor 输出里带敏感键的值被遮成 <redacted>", async () => {
    started = await startAppWithHub();
    process.env["FAKE_KERNEL_JSON"] = '{"api_key":"sk-secret-value","name":"ok"}';
    const job = await createAndWait({ kind: "doctor" });
    const envelope = job["envelope"] as Record<string, unknown>;
    const data = envelope["data"] as Record<string, unknown>;
    expect(data["api_key"]).toBe("<redacted>"); // 敏感键一律遮
    expect(data["name"]).toBe("ok");
    expect(JSON.stringify(job)).not.toContain("sk-secret-value");
  });
});

describe("JobTable 的容量与淘汰（D16，直接单测）", () => {
  const argv = ["config", "doctor", "--json"];

  it("101 个作业之后最早结束的终态作业被淘汰，表容量保持 100", () => {
    const table = new JobTable();
    const ids: string[] = [];
    for (let i = 0; i < 100; i += 1) {
      const record = table.create("doctor", argv, 600, 1000 + i);
      expect(record).not.toBeNull();
      settle(record as never, "succeeded", null, {}, 2000 + i); // 逐个落到终态
      ids.push((record as { id: string }).id);
    }
    expect(table.size).toBe(100);
    const extra = table.create("doctor", argv, 600, 3000);
    expect(extra).not.toBeNull(); // 满了但淘汰了最早结束的终态作业
    expect(table.size).toBe(100);
    expect(table.get(ids[0] as string)).toBeNull(); // 最早结束的被淘汰
    expect(table.get((extra as { id: string }).id)).not.toBeNull();
  });

  it("没有可淘汰的终态作业时 create 回 null（路由据此回 503）", () => {
    const table = new JobTable();
    for (let i = 0; i < 100; i += 1) {
      const record = table.create("doctor", argv, 600, 1000 + i);
      markRunning(record as never, 1500 + i); // 全部在跑（非终态）
    }
    expect(table.size).toBe(100);
    expect(table.active()).toBe(100);
    expect(table.create("doctor", argv, 600, 4000)).toBeNull(); // 没有终态可淘汰
  });
});
