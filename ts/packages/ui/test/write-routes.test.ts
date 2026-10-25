// 写路由的替身用例（桌面端 §5.3、D03–D13）：进程内建 app（照 support.ts 的写法），内核子进程走替身 fake-write-kernel.mjs。
// 覆盖预览成功/不合格/失败、确认号的核对次序（缺号/过期/用第二次/参数不符/并发/表满/503 不消耗）、needs_yes、令牌、
// 断开不取消、超时、stale 终态与预览内容的二道脱敏（§2.1）。时钟用可注入的 now 拨过 60 秒（S2）。
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { KernelRunner } from "../src/kernel.ts";
import { writeRoutes } from "../src/writeroutes.ts";
import { ConfirmationTable } from "../src/confirmations.ts";
import { OperationTable } from "../src/operations.ts";
import { argvsOf, readReport } from "./support.ts";
import { TS_ROOT } from "./harness.ts";

const FAKE_WRITE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-write-kernel.mjs");
const STATE = `v1;config=${"0".repeat(64)}`;
const CONFIRM_409 = "ERROR: 确认号无效、已过期或已用过：请重新预览";
const ARGV_409 = "ERROR: 确认号与这次请求的参数不符：请重新预览";
const PREVIEW_500 = "ERROR: 内核的预览不合格";
const FAKE_VARS = ["FAKE_WRITE_PREVIEW", "FAKE_WRITE_PLAN", "FAKE_WRITE_GATE", "FAKE_WRITE_BEGIN", "FAKE_KERNEL_EXIT"];

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

/** 响应正文里的 messages 数组（信封七字段之一）。 */
async function messagesOf(res: Response): Promise<unknown> {
  return ((await res.json()) as Record<string, unknown>)["messages"];
}

interface WriteApp {
  readonly app: App;
  readonly runner: KernelRunner;
  readonly confirmations: ConfirmationTable;
  readonly operations: OperationTable;
  readonly report: string;
  readonly dir: string;
  advanceClock(ms: number): void;
  get(target: string): Promise<Response>;
  post(target: string, body: unknown): Promise<Response>;
  postAbortable(target: string, body: unknown): { promise: Promise<Response>; controller: AbortController };
  dispose(): Promise<void>;
}

interface WriteOverrides {
  readonly maxConcurrent?: number;
  readonly maxQueue?: number;
  readonly timeouts?: Readonly<Record<string, number>>;
}

async function startApp(overrides: WriteOverrides = {}): Promise<WriteApp> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-write-"));
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_REPORT"] = report;
  const runner = new KernelRunner({
    repo: TS_ROOT,
    python: process.execPath,
    kernel: FAKE_WRITE_KERNEL,
    ...(overrides.maxConcurrent === undefined ? {} : { maxConcurrent: overrides.maxConcurrent }),
    ...(overrides.maxQueue === undefined ? {} : { maxQueue: overrides.maxQueue }),
  });
  let clock = 1000;
  const confirmations = new ConfirmationTable({ now: () => clock });
  const operations = new OperationTable();
  const app = createApp({
    port: 1,
    assets: dir,
    controlToken: "t".repeat(43),
    extraRoutes: writeRoutes({ runner, confirmations, operations }, overrides.timeouts ?? {}),
  });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  const headers = { host: "127.0.0.1:1", cookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" };
  return {
    app,
    runner,
    confirmations,
    operations,
    report,
    dir,
    advanceClock: (ms) => {
      clock += ms;
    },
    get: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie } })),
    post: (target, body) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { method: "POST", headers, body: JSON.stringify(body) })),
    postAbortable: (target, body) => {
      const controller = new AbortController();
      const promise = app.fetch(new Request(`http://127.0.0.1:1${target}`, { method: "POST", headers, body: JSON.stringify(body), signal: controller.signal }));
      return { promise, controller };
    },
    dispose: async () => {
      delete process.env["FAKE_KERNEL_REPORT"];
      await runner.shutdown();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** 执行一支的 argv（含 --expect-state=，去重保持次序）。 */
function executionArgvs(report: string): string[][] {
  return readReport(report)
    .filter((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state=")))
    .map((line) => [...line.argv]);
}

/** 执行次数（begin 行里有 --expect-state= 的条数，不去重）。 */
function executionCount(report: string): number {
  return readReport(report).filter((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state="))).length;
}

/** 预览一次 role.set 并取回确认号。 */
async function previewConfirmation(app: WriteApp, action = "role.set", args: Record<string, unknown> = { role: "execution", target: "manual" }): Promise<string> {
  const res = await app.post("/api/v1/preview", { action, args });
  expect(res.status).toBe(200);
  const body = (await res.json()) as Record<string, unknown>;
  return (body["data"] as Record<string, unknown>)["confirmation"] as string;
}

/** 等操作到终态，返回八键操作对象。 */
async function waitForOperation(app: WriteApp, id: string, states: readonly string[]): Promise<Record<string, unknown>> {
  for (let i = 0; i < 400; i += 1) {
    const res = await app.get(`/api/v1/operations/${id}`);
    if (res.status === 200) {
      const op = (await res.json()) as Record<string, unknown>;
      if (states.includes(String(op["state"]))) return op;
    }
    await sleep(25);
  }
  throw new Error(`操作 ${id} 没有到终态 ${states.join("/")}`);
}

/** 等执行次数达到 count（替身已被起了这么多次）。 */
async function waitForExecutions(report: string, count: number): Promise<void> {
  for (let i = 0; i < 400; i += 1) {
    if (executionCount(report) >= count) return;
    await sleep(25);
  }
  throw new Error(`没有等到 ${count} 次执行`);
}

let started: WriteApp | null = null;

beforeEach(() => {
  for (const name of FAKE_VARS) delete process.env[name];
});

afterEach(async () => {
  for (const name of FAKE_VARS) delete process.env[name];
  await started?.dispose();
  started = null;
});

describe("S1–S4：确认号的核对次序（缺号/过期/用第二次/参数不符）", () => {
  it("S1：缺号、不是字符串、格式不对、不在表里 → 409「确认号无效、已过期或已用过」，替身没有执行记录", async () => {
    started = await startApp();
    const cases: unknown[] = [undefined, 5, "short", "C".repeat(43)];
    for (const value of cases) {
      const body: Record<string, unknown> = { target: "manual" };
      if (value !== undefined) body["confirmation"] = value;
      const res = await started.post("/api/v1/roles/execution", body);
      expect(res.status, JSON.stringify(value)).toBe(409);
      expect(await messagesOf(res), JSON.stringify(value)).toEqual([CONFIRM_409]);
    }
    expect(argvsOf(started.report), "确认号不合格不起子进程").toEqual([]);
  });

  it("S2：注入的时钟拨过 60 秒 → 409，替身没有执行记录", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    started.advanceClock(60_001);
    const res = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(res.status).toBe(409);
    expect(await messagesOf(res)).toEqual([CONFIRM_409]);
    expect(executionArgvs(started.report)).toEqual([]);
  });

  it("S3：同一个号用第二次 → 409，替身只执行一次", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    expect((await started.post("/api/v1/roles/execution", { target: "manual", confirmation })).status).toBe(200);
    const second = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(second.status).toBe(409);
    expect(await messagesOf(second)).toEqual([CONFIRM_409]);
    expect(executionCount(started.report), "只执行一次").toBe(1);
  });

  it("S4：同一个号换参数（argv 不符）→ 409「参数不符」，号仍可按原参数用", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    const wrong = await started.post("/api/v1/roles/execution", { target: "disabled", confirmation });
    expect(wrong.status).toBe(409);
    expect(await messagesOf(wrong)).toEqual([ARGV_409]);
    expect(executionArgvs(started.report), "参数不符不消耗号、不起子进程").toEqual([]);
    const right = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(right.status, "号仍可按原参数用").toBe(200);
    expect(executionCount(started.report)).toBe(1);
  });
});

describe("S5–S7：并发、503 不消耗、表满", () => {
  it("S5：同一个号同时发两个请求 → 一个 200、一个 409，替身只执行一次", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    const [a, b] = await Promise.all([
      started.post("/api/v1/roles/execution", { target: "manual", confirmation }),
      started.post("/api/v1/roles/execution", { target: "manual", confirmation }),
    ]);
    expect([a.status, b.status].sort()).toEqual([200, 409]);
    expect(executionCount(started.report), "并发只接受一个").toBe(1);
  });

  it("S6：maxConcurrent=1、maxQueue=0，pause 占名额 → 第二个写 503 带 retry-after；放行后同一个号重试成功", async () => {
    const gate = join((started = await startApp({ maxConcurrent: 1, maxQueue: 0 })).dir, "gate-s6");
    process.env["FAKE_WRITE_GATE"] = gate;
    process.env["FAKE_WRITE_PLAN"] = "pause";
    process.env["FAKE_KERNEL_EXIT"] = "0";
    const a = await previewConfirmation(started);
    const b = await previewConfirmation(started);
    const w1 = started.post("/api/v1/roles/execution", { target: "manual", confirmation: a });
    await waitForExecutions(started.report, 1); // pause 占住名额
    const w2 = await started.post("/api/v1/roles/execution", { target: "manual", confirmation: b });
    expect(w2.status, "队列满且关停中回 503").toBe(503);
    expect(w2.headers.get("retry-after")).toBe("2");
    writeFileSync(gate, "go"); // 放行 pause
    expect((await w1).status).toBe(200);
    const retry = await started.post("/api/v1/roles/execution", { target: "manual", confirmation: b });
    expect(retry.status, "503 没有消耗确认号，重试成功").toBe(200);
  });

  it("S7：发 101 个确认号 → 第 1 个回 409，第 101 个能用", async () => {
    started = await startApp();
    const confirmations: string[] = [];
    for (let i = 0; i < 101; i += 1) confirmations.push(await previewConfirmation(started));
    const first = await started.post("/api/v1/roles/execution", { target: "manual", confirmation: confirmations[0] });
    expect(first.status, "表满挤掉最早发出的未用号").toBe(409);
    const last = await started.post("/api/v1/roles/execution", { target: "manual", confirmation: confirmations[100] });
    expect(last.status, "第 101 个能用").toBe(200);
  });
});

describe("S8–S11：needs_yes、令牌、预览不合格/失败", () => {
  it("S8：needs_yes 为假时执行 argv 没有 --yes；为真时有", async () => {
    started = await startApp();
    const c1 = await previewConfirmation(started);
    await started.post("/api/v1/roles/execution", { target: "manual", confirmation: c1 });
    expect(executionArgvs(started.report)[0]?.some((part) => part === "--yes"), "needs_yes 假：无 --yes").toBe(false);
    process.env["FAKE_WRITE_PREVIEW"] = JSON.stringify({
      dry_run: true, action: "role.set", changed: false, resources: [], binding_changes: [],
      running_attempts: [], unreadable: [], needs_yes: true, warnings: [], notes: [], state: STATE,
    });
    const c2 = await previewConfirmation(started);
    await started.post("/api/v1/roles/execution", { target: "manual", confirmation: c2 });
    expect(executionArgvs(started.report)[1]?.some((part) => part === "--yes"), "needs_yes 真：带 --yes").toBe(true);
  });

  it("S9：执行 argv 的 --expect-state 与预览逐字相同；预览信封没有 state；command 是 --expect-state=<state>", async () => {
    started = await startApp();
    const previewRes = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" } });
    const previewText = await previewRes.text();
    const previewBody = JSON.parse(previewText) as Record<string, unknown>;
    const confirmation = (previewBody["data"] as Record<string, unknown>)["confirmation"] as string;
    expect((previewBody["data"] as Record<string, unknown>)["preview"]).not.toHaveProperty("state");
    expect(previewText, "预览正文里不出现令牌原文").not.toContain(STATE);
    const execRes = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    const execBody = JSON.parse(await execRes.text()) as Record<string, unknown>;
    expect(executionArgvs(started.report)[0]).toContain(`--expect-state=${STATE}`);
    expect(execBody["command"]).toContain("--expect-state=<state>");
    expect(JSON.stringify(execBody["command"]), "command 里是占位，不是令牌").not.toContain(STATE);
  });

  it("S10：预览 action 不同或 state 形状不对 → 500「内核的预览不合格」，不发确认号", async () => {
    started = await startApp();
    process.env["FAKE_WRITE_PREVIEW"] = JSON.stringify({
      dry_run: true, action: "preset.use", changed: false, resources: [], binding_changes: [],
      running_attempts: [], unreadable: [], needs_yes: false, warnings: [], notes: [], state: STATE,
    });
    const wrongAction = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" } });
    expect(wrongAction.status).toBe(500);
    expect(await messagesOf(wrongAction)).toEqual([PREVIEW_500]);
    process.env["FAKE_WRITE_PREVIEW"] = JSON.stringify({
      dry_run: true, action: "role.set", changed: false, resources: [], binding_changes: [],
      running_attempts: [], unreadable: [], needs_yes: false, warnings: [], notes: [], state: "bad-token",
    });
    const badState = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" } });
    expect(badState.status).toBe(500);
    expect(started.confirmations.size, "预览不合格不发确认号").toBe(0);
    expect(started.operations.size).toBe(0);
  });

  it("S11：预览退出 1 → 200、ok 假、data 里没有 confirmation；确认号表与操作表都不变", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_EXIT"] = "1";
    const res = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" } });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(1);
    const data = body["data"] as Record<string, unknown> | null;
    expect(data === null || data["confirmation"] === undefined, "data 里没有 confirmation").toBe(true);
    expect(started.confirmations.size).toBe(0);
    expect(started.operations.size).toBe(0);
  });
});

describe("S12：断开不取消与 audit-fail（U19/U21）", () => {
  it("S12-U19：audit-fail → ok 假，output 与 messages 都在", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    process.env["FAKE_WRITE_PLAN"] = "audit-fail";
    const res = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body["ok"]).toBe(false);
    expect(body["output"]).toEqual(["已设置 execution = manual"]);
    expect(body["messages"]).toEqual(["ERROR: 已写入配置，但审计记录不全"]);
  });

  it("S12-U21：断开不取消——读到 begin 行后断开，子进程不被杀，终态照记；查不存在的号 404", async () => {
    started = await startApp();
    const gate = join(started.dir, "gate-u21");
    process.env["FAKE_WRITE_GATE"] = gate;
    process.env["FAKE_WRITE_PLAN"] = "pause";
    const confirmation = await previewConfirmation(started);
    const { promise, controller } = started.postAbortable("/api/v1/roles/execution", { target: "manual", confirmation });
    await waitForExecutions(started.report, 1);
    controller.abort(); // 断开（不靠计时）
    writeFileSync(gate, "go"); // 放行 pause
    await promise;
    const op = await waitForOperation(started, confirmation, ["failed"]);
    expect(op["state"]).toBe("failed");
    const envelope = op["envelope"] as Record<string, unknown>;
    expect(envelope["output"]).toContain("WARN  已写入 execution = manual");
    expect(envelope["messages"]).toContain("ERROR: 审计记录不全");
    expect(readReport(started.report).some((line) => line.event === "end"), "子进程没被杀：报告里有 end 行").toBe(true);
    const notFound = await started.get(`/api/v1/operations/${"D".repeat(43)}`);
    expect(notFound.status).toBe(404);
    expect(await messagesOf(notFound)).toEqual(["ERROR: 没有这个操作"]);
  });
});

describe("S13–S15：超时、预览内容变换、stale 终态", () => {
  it("S13：时限 1 秒、替身挂住 → 504，操作记 timed_out", async () => {
    started = await startApp({ timeouts: { "api.write": 1 } });
    process.env["FAKE_WRITE_GATE"] = join(started.dir, "never-gate"); // 永不放行，挂到超时
    process.env["FAKE_WRITE_PLAN"] = "pause";
    const confirmation = await previewConfirmation(started);
    const res = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(res.status).toBe(504);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body["exit_code"]).toBeNull();
    const op = await waitForOperation(started, confirmation, ["timed_out"]);
    expect(op["state"]).toBe("timed_out");
  });

  it("S14：预览内容变换——该放行的放行、该遮的遮、令牌原文不出现、无 state、43 位确认号", async () => {
    started = await startApp();
    const res = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" } });
    expect(res.status).toBe(200);
    const text = await res.text();
    const body = JSON.parse(text) as Record<string, unknown>;
    const preview = (body["data"] as Record<string, unknown>)["preview"] as Record<string, any>;
    const binding = preview["binding_changes"] as any[];
    // (a) 该放行的放行
    expect(binding[0].after.model).toBe("demo-model");
    expect(binding[0].after.profile).toBe("demo-profile");
    expect(binding[0].before.profile).toBeNull();
    expect((preview["resources"] as any[])[0].changed_keys[0]).toBe("binding");
    expect((preview["notes"] as string[])[0]).toBe("demo note");
    expect((preview["warnings"] as string[])[0]).toBe("demo warning");
    // (b) 该遮的遮
    expect(binding[1].after.profile).toBe("<redacted>");
    expect((preview["notes"] as string[])[1]).toBe("<redacted>");
    expect(preview["api_key"]).toBe("<redacted>");
    // (c) 令牌原文在整个正文里一次都不出现
    expect(text).not.toContain("sk-abcdefghijklmnopqrstuvwxyz012345");
    expect(text).not.toContain(STATE);
    // (d) 任何层级都没有 state 键；confirmation 是 43 位
    expect(JSON.stringify(preview)).not.toContain('"state"');
    expect((body["data"] as Record<string, unknown>)["confirmation"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
  });

  it("S15：stale 计划（退出 4）→ 409 七字段信封，exit_code 4，操作记 stale", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started);
    process.env["FAKE_WRITE_PLAN"] = "stale";
    const res = await started.post("/api/v1/roles/execution", { target: "manual", confirmation });
    expect(res.status).toBe(409);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body["exit_code"], "七字段信封：exit_code 是 4").toBe(4);
    expect(body["ok"]).toBe(false);
    expect(body["messages"]).toEqual(["ERROR: 配置在预览之后被改过：什么也没写，重新预览"]);
    expect(body["command"], "七字段信封：command 是显示 argv（不是 errorResponse 的空数组）").toContain("--expect-state=<state>");
    const op = await waitForOperation(started, confirmation, ["stale"]);
    expect(op["state"]).toBe("stale");
    expect(op["reason"]).toBeNull();
  });
});
