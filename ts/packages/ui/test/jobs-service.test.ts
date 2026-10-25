// 作业路由的进程内用例（桌面端 §5.3、D17/D18/D31）：四种终态各一例、search 超时终态是 timed_out、取消在跑的结束
// 整棵进程树（孙进程也不在了）、取消排队中的不起子进程、执行器收不了回 503、创建回 201 与创建/查询的八键正文
// （不套信封、不套 data）。内核子进程走替身 fake-kernel.mjs（FAKE_KERNEL_PLAN=hang 起孙进程之后睡）。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pidAlive } from "@themis/base/process";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { JOB_ID_RE } from "../src/jobs.ts";
import { readReport, startAppWithHub, type StartedAppWithHub } from "./support.ts";

const JOB_KEYS = ["id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope"];
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "timed_out"]);

/** 等替身内核真的起了子进程（报告里出现 count 条 begin），再往下取消——running 态先于起子进程。 */
async function waitBegins(count: number, timeoutMs = 10_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const begins = readReport((started as StartedAppWithHub).report).filter((line) => line.event === "begin");
    if (begins.length >= count) return;
    if (Date.now() > deadline) throw new Error(`没等到 ${count} 个 begin（现有 ${begins.length}）`);
    await sleep(30);
  }
}

let started: StartedAppWithHub | null = null;
let dir = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-jobs-svc-"));
  for (const name of ["FAKE_KERNEL_JSON", "FAKE_KERNEL_STDERR", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_SLEEP_MS", "FAKE_KERNEL_PLAN", "FAKE_KERNEL_PIDFILE"]) {
    delete process.env[name];
  }
});

afterEach(async () => {
  for (const name of ["FAKE_KERNEL_JSON", "FAKE_KERNEL_STDERR", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_SLEEP_MS", "FAKE_KERNEL_PLAN", "FAKE_KERNEL_PIDFILE"]) {
    delete process.env[name];
  }
  await started?.dispose();
  started = null;
  rmSync(dir, { recursive: true, force: true });
});

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

async function createJob(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await (started as StartedAppWithHub).post("/api/v1/jobs", body);
  return (await response.json()) as Record<string, unknown>;
}

async function getJob(id: string): Promise<Record<string, unknown>> {
  return (await (await (started as StartedAppWithHub).get(`/api/v1/jobs/${id}`)).json()) as Record<string, unknown>;
}

async function waitTerminal(id: string, timeoutMs = 30_000): Promise<Record<string, unknown>> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const job = await getJob(id);
    if (TERMINAL.has(String(job["state"]))) return job;
    if (Date.now() > deadline) throw new Error(`作业没到终态：${JSON.stringify(job)}`);
    await sleep(30);
  }
}

async function waitState(id: string, state: string, timeoutMs = 10_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (String((await getJob(id))["state"]) === state) return;
    if (Date.now() > deadline) throw new Error(`作业没到 ${state}`);
    await sleep(20);
  }
}

async function waitDead(pid: number, timeoutMs = 10_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && pidAlive(pid) !== false) await sleep(150);
}

describe("创建与查询的响应形状（D31）", () => {
  it("POST /api/v1/jobs 成功回 201，正文是顶层八键作业对象（不套信封、不套 data）", async () => {
    started = await startAppWithHub();
    const response = await started.post("/api/v1/jobs", { kind: "doctor" });
    expect(response.status).toBe(201);
    const job = (await response.json()) as Record<string, unknown>;
    expect(Object.keys(job).sort()).toEqual([...JOB_KEYS].sort()); // 八键一个不能少
    expect("data" in job).toBe(false); // 不套 data
    expect("ok" in job).toBe(false); // 不套七字段信封
    expect(String(job["id"])).toMatch(JOB_ID_RE);
    expect(job["kind"]).toBe("doctor");
    expect(job["state"]).toBe("queued"); // 创建成功的当下是 queued
    expect(job["reason"]).toBe(null);
    expect(job["started_ms"]).toBe(null);
    expect(job["finished_ms"]).toBe(null);
    expect(job["envelope"]).toBe(null);
    expect(typeof job["created_ms"]).toBe("number");
  });

  it("GET /api/v1/jobs/<id> 是同一个八键对象，跑到终态后 state 落在四种之内", async () => {
    started = await startAppWithHub();
    const created = await createJob({ kind: "doctor" });
    const job = await waitTerminal(String(created["id"]));
    expect(Object.keys(job).sort()).toEqual([...JOB_KEYS].sort());
    expect("data" in job).toBe(false);
    expect(TERMINAL.has(String(job["state"]))).toBe(true);
    expect(job["state"]).toBe("succeeded");
    expect(typeof job["started_ms"]).toBe("number");
    expect(typeof job["finished_ms"]).toBe("number");
    const envelope = job["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(true);
    expect(envelope["command"]).toEqual(["config", "doctor", "--json"]);
  });
});

describe("四种终态（D17）", () => {
  it("succeeded：退出 0", async () => {
    started = await startAppWithHub();
    const created = await createJob({ kind: "doctor" });
    const job = await waitTerminal(String(created["id"]));
    expect(job["state"]).toBe("succeeded");
    expect(job["reason"]).toBe(null);
  });

  it("failed：退出非 0，reason 为 exit，信封 ok 为 false、exit_code 原样", async () => {
    started = await startAppWithHub();
    process.env["FAKE_KERNEL_EXIT"] = "3";
    process.env["FAKE_KERNEL_JSON"] = '{"partial":true}';
    const created = await createJob({ kind: "doctor" });
    const job = await waitTerminal(String(created["id"]));
    expect(job["state"]).toBe("failed");
    expect(job["reason"]).toBe("exit");
    const envelope = job["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(false);
    expect(envelope["exit_code"]).toBe(3);
  });

  it("cancelled：取消在跑的作业，终态 cancelled、信封为 null、孙进程也不在了", async () => {
    const pidfile = join(dir, "gc.pid");
    process.env["FAKE_KERNEL_PIDFILE"] = pidfile;
    process.env["FAKE_KERNEL_PLAN"] = "hang"; // 起孙进程之后一直睡
    started = await startAppWithHub();
    const created = await createJob({ kind: "doctor" });
    const id = String(created["id"]);
    await waitState(id, "running");
    const deadline = Date.now() + 10_000;
    while (!existsSync(pidfile) && Date.now() < deadline) await sleep(30);
    expect(existsSync(pidfile), "孙进程的 pid 文件应已写出（替身真的起了子进程）").toBe(true);
    const response = await started.post(`/api/v1/jobs/${id}/cancel`, {});
    expect(response.status).toBe(200);
    const job = (await response.json()) as Record<string, unknown>;
    expect(job["state"]).toBe("cancelled");
    expect(job["envelope"]).toBe(null);
    const grandchild = Number(readFileSync(pidfile, "utf8").trim());
    expect(grandchild).toBeGreaterThan(0);
    await waitDead(grandchild);
    expect(pidAlive(grandchild), `孙进程 ${grandchild} 应该已经不在了`).toBe(false);
  });

  it("timed_out：search 卡住时终态是 timed_out，messages 是超时那一行、没有匹配", async () => {
    const pidfile = join(dir, "gc2.pid");
    process.env["FAKE_KERNEL_PIDFILE"] = pidfile;
    process.env["FAKE_KERNEL_PLAN"] = "hang"; // 平方级耗时卡住
    started = await startAppWithHub({ timeouts: { "job.search": 1 } });
    const created = await createJob({ kind: "search", pattern: "token" });
    const job = await waitTerminal(String(created["id"]), 15_000);
    expect(job["state"]).toBe("timed_out");
    const envelope = job["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(false);
    expect(envelope["exit_code"]).toBe(null);
    expect(envelope["data"]).toBe(null);
    expect(envelope["messages"]).toEqual(["ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看"]);
    expect((envelope["command"] as string[]).includes("search")).toBe(true);
    const grandchild = Number(readFileSync(pidfile, "utf8").trim());
    await waitDead(grandchild);
    expect(pidAlive(grandchild), `孙进程 ${grandchild} 应该已经不在了`).toBe(false);
  });
});

describe("取消排队中与 503（D16/D18）", () => {
  it("取消排队中的作业：不起子进程，终态 cancelled", async () => {
    process.env["FAKE_KERNEL_PLAN"] = "hang";
    started = await startAppWithHub({ maxConcurrent: 1, maxQueue: 4 });
    const running = await createJob({ kind: "doctor" }); // 立刻在跑
    await waitState(String(running["id"]), "running");
    await waitBegins(1); // 等第一个作业真的起了子进程
    const queued = await createJob({ kind: "doctor" }); // 排队
    const response = await started.post(`/api/v1/jobs/${String(queued["id"])}/cancel`, {});
    expect(response.status).toBe(200);
    const job = (await response.json()) as Record<string, unknown>;
    expect(job["state"]).toBe("cancelled");
    // 排队中的没起子进程：报告里只有第一个作业的 begin
    const begins = readReport(started.report).filter((line) => line.event === "begin");
    expect(begins).toHaveLength(1);
  });

  it("执行器收不了时回 503 带 Retry-After 且不建作业", async () => {
    process.env["FAKE_KERNEL_PLAN"] = "hang";
    started = await startAppWithHub({ maxConcurrent: 1, maxQueue: 0 });
    const running = await createJob({ kind: "doctor" });
    await waitState(String(running["id"]), "running"); // 名额占满
    const response = await started.post("/api/v1/jobs", { kind: "doctor" });
    expect(response.status).toBe(503);
    expect(response.headers.get("retry-after")).toBe("2");
    // 不建作业：随便一个 43 位号都查不到（没有可查的 id，503 是错误信封）
    const body = (await response.json()) as Record<string, unknown>;
    expect(body["ok"]).toBe(false);
  });
});
