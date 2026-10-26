// 凭据录入作业的进程内用例（桌面端 §5.3、U18）：照 write-routes.test.ts 的写法自己建 KernelRunner 与 createApp（不用
// support.ts 的 startApp，它把内核替身写死成 fake-kernel.mjs），内核子进程走替身 fake-secret-kernel.mjs。覆盖 argv 逐字
// 对照、校验三类 400、两种 503、握手正例与全部反例、等握手的上限（到点/排队占位/请求断开）、终态映射与重查、地址
// 不外泄的五处、onStderr 钩子与四张表仍是六项。计时一律用门文件卡先后，不靠睡眠时长或墙钟。
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pidAlive } from "@themis/base/process";
import { allowEnvName } from "@themis/base/secrets";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { EventHub, eventRoutes } from "../src/events.ts";
import { JOB_ALLOW, JOB_ARGV, JOB_KINDS, JOB_TIMEOUTS, jobRoutes } from "../src/jobroutes.ts";
import { jobView, type JobRecord, JobTable } from "../src/jobs.ts";
import { KernelRunner } from "../src/kernel.ts";
import { SECRET_ENTRY_ARGV, secretEntryRoutes } from "../src/secretentry.ts";
import { TS_ROOT } from "./harness.ts";
import { type ReportLine, readReport } from "./support.ts";

const FAKE_SECRET_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-secret-kernel.mjs");
const JOB_KEYS = ["id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope"];
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "timed_out"]);
const ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"];
/** 替身认的环境变量（每个用例前后清干净，免得串味）。 */
const FAKE_VARS = ["FAKE_SECRET_URL", "FAKE_SECRET_GATE", "FAKE_SECRET_CHECK_GATE", "FAKE_SECRET_SILENT", "FAKE_SECRET_STDOUT", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_PIDFILE"];

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

interface SecretApp {
  readonly app: App;
  readonly runner: KernelRunner;
  readonly hub: EventHub;
  readonly jobs: JobTable;
  readonly report: string;
  readonly dir: string;
  readonly cookie: string;
  post(target: string, body: unknown): Promise<Response>;
  postAbortable(target: string, body: unknown): { promise: Promise<Response>; controller: AbortController };
  get(target: string): Promise<Response>;
  /** 起一次录入（正文一律是空 JSON 对象）。 */
  entry(name: string): Promise<Response>;
  dispose(): Promise<void>;
}

async function startApp(overrides: { maxConcurrent?: number; maxQueue?: number; timeouts?: Readonly<Record<string, number>> } = {}): Promise<SecretApp> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-secret-"));
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_REPORT"] = report;
  const runner = new KernelRunner({
    repo: TS_ROOT,
    python: process.execPath,
    kernel: FAKE_SECRET_KERNEL,
    ...(overrides.maxConcurrent === undefined ? {} : { maxConcurrent: overrides.maxConcurrent }),
    ...(overrides.maxQueue === undefined ? {} : { maxQueue: overrides.maxQueue }),
  });
  const hub = new EventHub({ repo: TS_ROOT, runner });
  const jobs = new JobTable();
  const timeouts = overrides.timeouts ?? {};
  const app = createApp({
    port: 1,
    assets: dir,
    controlToken: "t".repeat(43),
    extraRoutes: [...eventRoutes(hub), ...jobRoutes(runner, jobs, timeouts), ...secretEntryRoutes(runner, jobs, timeouts)],
  });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  const headers = { host: "127.0.0.1:1", cookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" };
  return {
    app,
    runner,
    hub,
    jobs,
    report,
    dir,
    cookie,
    post: (target, body) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { method: "POST", headers, body: JSON.stringify(body) })),
    postAbortable: (target, body) => {
      const controller = new AbortController();
      const promise = app.fetch(new Request(`http://127.0.0.1:1${target}`, { method: "POST", headers, body: JSON.stringify(body), signal: controller.signal }));
      return { promise, controller };
    },
    get: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie } })),
    entry: (name) => app.fetch(new Request(`http://127.0.0.1:1/api/v1/secrets/${name}/entry`, { method: "POST", headers, body: "{}" })),
    dispose: async () => {
      delete process.env["FAKE_KERNEL_REPORT"];
      hub.close();
      await runner.shutdown();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

let started: SecretApp | null = null;

beforeEach(() => {
  for (const name of FAKE_VARS) delete process.env[name];
});

afterEach(async () => {
  for (const name of FAKE_VARS) delete process.env[name];
  await started?.dispose();
  started = null;
});

/** 替身起过几次子进程（begin 行）。 */
function begins(report: string): ReportLine[] {
  return readReport(report).filter((line) => line.event === "begin");
}

/** 某一次 begin 行的 argv。 */
function argvOf(report: string, index: number): readonly string[] {
  const line = begins(report)[index];
  if (line === undefined) throw new Error(`报告里没有第 ${index} 次 begin`);
  return line.argv;
}

/** 等作业到终态，返回八键作业对象。 */
async function waitTerminal(jobs: JobTable, id: string, timeoutMs = 30_000): Promise<Record<string, unknown>> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const record = jobs.get(id);
    if (record !== null && TERMINAL.has(record.state)) return jobView(record) as Record<string, unknown>;
    if (Date.now() > deadline) throw new Error(`作业没到终态：${record === null ? "不在表里" : record.state}`);
    await sleep(25);
  }
}

/** 等 pid 真的不在（取消与超时都要把整棵树结束干净）。 */
async function waitDead(pid: number, timeoutMs = 15_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && pidAlive(pid) !== false) await sleep(120);
  expect(pidAlive(pid), `pid ${pid} 应已不在`).toBe(false);
}

/** 一次性页面地址里的令牌（最后一段）。 */
function tokenOf(url: string): string {
  return url.slice(url.lastIndexOf("/") + 1);
}

/** 录入响应的正文。 */
async function entryBody(response: Response): Promise<Record<string, unknown>> {
  return (await response.json()) as Record<string, unknown>;
}

/** 发一个带自定义正文的录入请求（校验次序的用例用：cookie 由 started 带着）。 */
function postRaw(target: string, body: string): Promise<Response> {
  const app = started as SecretApp;
  return app.app.fetch(
    new Request(`http://127.0.0.1:1${target}`, {
      method: "POST",
      headers: { host: "127.0.0.1:1", cookie: app.cookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" },
      body,
    }),
  );
}

describe("argv 与路由表（D01/D02/D07）", () => {
  it("argv 逐字等于 SECRET_ENTRY_ARGV：无 --verify、无 --tty，--timeout 恒 600", async () => {
    started = await startApp();
    const response = await started.entry("EXAMPLE_KEY");
    expect(response.status).toBe(201);
    const expected = [...SECRET_ENTRY_ARGV.slice(0, 3), "EXAMPLE_KEY", ...SECRET_ENTRY_ARGV.slice(4)];
    expect(argvOf(started.report, 0)).toEqual([...expected]);
    expect(SECRET_ENTRY_ARGV).toEqual(["config", "secret", "set", "EXAMPLE_KEY", "--no-browser", "--timeout=600"]);
    expect(SECRET_ENTRY_ARGV.some((part) => part === "--no-browser")).toBe(true);
  });

  it("kind=secret-entry 回 400「kind 不合法」；四张表仍是六项、jobView 仍是八键", async () => {
    started = await startApp();
    const response = await started.post("/api/v1/jobs", { kind: "secret-entry" });
    expect(response.status).toBe(400);
    const body = (await response.json()) as Record<string, unknown>;
    expect(body["messages"]).toEqual(["ERROR: kind 不合法"]);
    expect(begins(started.report), "kind 不合法不起子进程").toEqual([]);
    expect(JOB_KINDS.length).toBe(6);
    expect(Object.keys(JOB_ARGV).length).toBe(6);
    expect(Object.keys(JOB_TIMEOUTS).length).toBe(6);
    expect(Object.keys(JOB_ALLOW).length).toBe(6);
    for (const table of [JOB_KINDS, Object.keys(JOB_ARGV), Object.keys(JOB_TIMEOUTS), Object.keys(JOB_ALLOW)]) {
      expect(table).not.toContain("secret-entry");
    }
    const record = {
      id: "x",
      kind: "doctor",
      argv: [],
      timeoutSeconds: 1,
      created_ms: 0,
      controller: new AbortController(),
      run: Promise.resolve(),
      exited: Promise.resolve(),
      state: "queued",
      reason: null,
      started_ms: null,
      finished_ms: null,
      envelope: null,
    } as unknown as JobRecord;
    expect(Object.keys(jobView(record))).toEqual(JOB_KEYS);
  });
});

describe("校验次序（D01）：任何一关不过都不起子进程", () => {
  it("正文不是对象 → 400「请求体必须是 JSON 对象」", async () => {
    started = await startApp();
    for (const body of ["[]", '"text"', "5", "null"]) {
      const response = await postRaw("/api/v1/secrets/EXAMPLE_KEY/entry", body);
      expect(response.status, body).toBe(400);
      expect((await response.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 请求体必须是 JSON 对象"]);
    }
    expect(begins(started.report), "正文不合格不起子进程").toEqual([]);
  });

  it("正文带任何键 → 400「请求体含有未知键」；凭据名不合法 → 400「凭据名不合法」", async () => {
    started = await startApp();
    // 合法基线先验证：这几个名字过得了 allowEnvName，坏的才回 400（不是另一条规则提前拒绝）
    expect(allowEnvName("EXAMPLE_KEY")).toBe(true);
    expect(allowEnvName("THEMIS_UI_TEST_KEY")).toBe(true);
    for (const name of ["9bad", "bad-name", "bad name", `sk_${"a".repeat(24)}`]) {
      expect(allowEnvName(name), `${name} 应过不了 allowEnvName`).toBe(false);
    }
    const withKey = await postRaw("/api/v1/secrets/EXAMPLE_KEY/entry", '{"name":"X"}');
    expect(withKey.status).toBe(400);
    expect((await withKey.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 请求体含有未知键"]);
    for (const name of ["9bad", "bad-name", "bad name", `sk_${"a".repeat(24)}`]) {
      const response = await postRaw(`/api/v1/secrets/${name}/entry`, "{}");
      expect(response.status, name).toBe(400);
      expect((await response.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 凭据名不合法"]);
    }
    expect(begins(started.report), "校验不过不起子进程").toEqual([]);
  });
});

describe("两种 503（D01）：都不建作业，都带 Retry-After: 2", () => {
  it("执行器收不了 → 503「服务繁忙，请稍后重试」", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 0 });
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "busy-gate"); // 永不放行：占住唯一的名额
    const first = await started.entry("EXAMPLE_KEY");
    expect(first.status).toBe(201);
    expect(started.runner.canAccept(), "名额被占满，执行器收不了").toBe(false);
    const second = await started.entry("EXAMPLE_KEY");
    expect(second.status).toBe(503);
    expect(second.headers.get("retry-after")).toBe("2");
    expect((await second.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 服务繁忙，请稍后重试"]);
    expect(started.jobs.size, "收不了不建作业").toBe(1);
  });

  it("作业表满 → 503「作业表已满，请稍后重试」", async () => {
    started = await startApp();
    for (let i = 0; i < 100; i += 1) {
      expect(started.jobs.create("secret-entry", ["config"], 1, Date.now()), `第 ${i} 个应能建`).not.toBeNull();
    }
    expect(started.jobs.create("secret-entry", ["config"], 1, Date.now()), "表满且没有终态可淘汰").toBeNull();
    const response = await started.entry("EXAMPLE_KEY");
    expect(response.status).toBe(503);
    expect(response.headers.get("retry-after")).toBe("2");
    expect((await response.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 作业表已满，请稍后重试"]);
    expect(begins(started.report), "表满不起子进程").toEqual([]);
  });
});

describe("握手：严格核对（D03）", () => {
  it("合格的握手行 → 201，正文是 {job, url}，job 是八键且 state 为 running", async () => {
    started = await startApp();
    const response = await started.entry("EXAMPLE_KEY");
    expect(response.status).toBe(201);
    const body = await entryBody(response);
    expect(Object.keys(body).sort()).toEqual(["job", "url"]);
    const job = body["job"] as Record<string, unknown>;
    expect(Object.keys(job).sort()).toEqual([...JOB_KEYS].sort());
    expect(job["kind"]).toBe("secret-entry");
    expect(job["state"]).toBe("running");
    expect(String(body["url"])).toMatch(/^http:\/\/127\.0\.0\.1:\d{1,5}\/[A-Za-z0-9_-]{32}$/u);
    expect(tokenOf(String(body["url"])).length).toBe(32);
  });

  it("全部反例都不回 201：@ 别处、? 与 #、多一段路径、31/33 个字符、localhost、端口 0、65536、99999", async () => {
    started = await startApp({ maxConcurrent: 8, maxQueue: 16, timeouts: { "secret-entry.handshake": 1 } });
    const gate = join(started.dir, "never-gate"); // 永不出现：子进程一直活着，轮询读得到握手行
    process.env["FAKE_SECRET_GATE"] = gate;
    const token32 = "a".repeat(32);
    const bad: readonly string[] = [
      `http://127.0.0.1:80@evil.example/${token32}`,
      `http://127.0.0.1:8080/${token32}?x=1`,
      `http://127.0.0.1:8080/${token32}#frag`,
      `http://127.0.0.1:8080/${token32}/extra`,
      `http://127.0.0.1:8080/${"a".repeat(31)}`,
      `http://127.0.0.1:8080/${"a".repeat(33)}`,
      `http://localhost:8080/${token32}`,
      `http://127.0.0.1:0/${token32}`,
      `http://127.0.0.1:65536/${token32}`,
      `http://127.0.0.1:99999/${token32}`,
    ];
    for (const url of bad) {
      process.env["FAKE_SECRET_URL"] = url;
      const response = await started.entry("EXAMPLE_KEY");
      expect(response.status, url).not.toBe(201);
      const body = await entryBody(response);
      expect(body["url"], url).toBeNull();
    }
    expect(begins(started.report).length, "每个反例都真的起了子进程").toBe(bad.length);
    // 正面对照：同一个应用、同一条读链路，合格的地址照样 201（证明反例不是「根本没读到」）
    process.env["FAKE_SECRET_URL"] = `http://127.0.0.1:8123/${token32}`;
    const ok = await started.entry("EXAMPLE_KEY");
    expect(ok.status).toBe(201);
    expect(String((await entryBody(ok))["url"])).toBe(`http://127.0.0.1:8123/${token32}`);
  });
});

describe("等握手的上限与三种结束（D05）", () => {
  it("不打握手行 → 504，作业 timed_out，子进程已经不在", async () => {
    started = await startApp({ timeouts: { "secret-entry.handshake": 1 } });
    process.env["FAKE_SECRET_SILENT"] = "1";
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "silent-gate");
    const response = await started.entry("EXAMPLE_KEY");
    expect(response.status).toBe(504);
    const body = await entryBody(response);
    expect(body["url"]).toBeNull();
    const job = body["job"] as Record<string, unknown>;
    expect(job["state"]).toBe("timed_out");
    await waitDead(begins(started.report)[0]?.pid ?? 0);
    const terminal = await waitTerminal(started.jobs, String(job["id"]));
    expect(terminal["state"]).toBe("timed_out");
  });

  it("排队没轮到 → 504 且子进程从没起来", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 1, timeouts: { "secret-entry.handshake": 1 } });
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "queue-gate"); // 占住唯一名额
    const first = await started.entry("EXAMPLE_KEY");
    expect(first.status).toBe(201);
    const second = await started.entry("EXAMPLE_KEY");
    expect(second.status).toBe(504);
    const body = await entryBody(second);
    const queued = body["job"] as Record<string, unknown>;
    expect(queued["state"]).toBe("timed_out");
    expect(queued["started_ms"], "排队占位：从没起过子进程").toBeNull();
    expect(begins(started.report).length, "只有一个子进程起来过").toBe(1);
  });

  it("请求先断开 → 不回响应，作业 cancelled，子进程已经不在", async () => {
    started = await startApp();
    process.env["FAKE_SECRET_SILENT"] = "1"; // 不打握手行：断开之前响应还没回去
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "abort-gate");
    const { promise, controller } = started.postAbortable("/api/v1/secrets/EXAMPLE_KEY/entry", {});
    const deadline = Date.now() + 10_000;
    while (begins(started.report).length === 0 && Date.now() < deadline) await sleep(20);
    const pid = begins(started.report)[0]?.pid ?? 0;
    expect(pidAlive(pid), "断开之前子进程在跑").not.toBe(false);
    controller.abort(); // 客户端断开（不靠计时）
    const response = await promise;
    expect(response.status).toBe(503); // 客户端已走：占位响应
    const id = [...(started.jobs as unknown as { readonly records: Map<string, JobRecord> }).records.keys()][0] ?? "";
    const terminal = await waitTerminal(started.jobs, id);
    expect(terminal["state"]).toBe("cancelled");
    await waitDead(pid);
  });
});

describe("终态与重查（D06）", () => {
  it("保存成功 → succeeded；data 是 {set, check}；set 是白名单投影（没有 verified）；check 不带 file_dir", async () => {
    started = await startApp();
    const response = await started.entry("THEMIS_UI_TEST_KEY");
    expect(response.status).toBe(201);
    const created = await entryBody(response);
    const jobId = String((created["job"] as Record<string, unknown>)["id"]);
    const terminal = await waitTerminal(started.jobs, jobId);
    expect(terminal["state"]).toBe("succeeded");
    expect(terminal["reason"]).toBeNull();
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect(Object.keys(envelope)).toEqual(ENVELOPE_KEYS);
    expect(envelope["ok"]).toBe(true);
    expect(envelope["exit_code"]).toBe(0);
    const data = envelope["data"] as Record<string, unknown>;
    expect(Object.keys(data)).toEqual(["set", "check"]);
    const set = data["set"] as Record<string, unknown>;
    expect(Object.keys(set).every((key) => ["name", "stored", "backend"].includes(key))).toBe(true);
    expect("verified" in set).toBe(false);
    expect(set["stored"]).toBe(true);
    expect(set["name"]).toBe("THEMIS_UI_TEST_KEY");
    const check = data["check"] as Record<string, unknown>;
    expect(Object.keys(check).sort()).toEqual(["name", "source", "store_mode", "system_backend"]);
    expect(check["source"]).toBe("file");
    expect(check["store_mode"]).toBe("file");
    expect(check["system_backend"]).toBeNull();
    expect(envelope["command"]).toEqual(["config", "secret", "set", "THEMIS_UI_TEST_KEY", "--no-browser", "--timeout=600"]);
  });

  it("握手之前子进程就结束（退出 1）→ 502，作业 failed/exit，set 的 stored 是 false 且带 error", async () => {
    started = await startApp();
    process.env["FAKE_SECRET_SILENT"] = "1";
    process.env["FAKE_KERNEL_EXIT"] = "1";
    const response = await started.entry("EXAMPLE_KEY");
    expect(response.status).toBe(502);
    const body = await entryBody(response);
    expect(body["url"]).toBeNull();
    const job = body["job"] as Record<string, unknown>;
    expect(job["state"]).toBe("failed");
    expect(job["reason"]).toBe("exit");
    const envelope = job["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(false);
    expect(envelope["exit_code"]).toBe(1);
    const data = envelope["data"] as Record<string, unknown>;
    expect(data["set"]).not.toBeNull();
    const set = data["set"] as Record<string, unknown>;
    expect(set["stored"]).toBe(false);
    expect(typeof set["error"]).toBe("string");
    expect("verified" in set).toBe(false);
    expect(data["check"], "没收到握手就不重查").toBeNull();
    const messages = envelope["messages"] as string[];
    expect(messages.length).toBe(1);
    expect(messages[0]).toContain("ERROR");
  });

  it("取消不等重查：取消响应先到、作业仍 running，放行之后 cancelled 且 check 不为 null", async () => {
    started = await startApp();
    process.env["FAKE_SECRET_CHECK_GATE"] = join(started.dir, "check-gate"); // 重查卡在门文件上
    const created = await started.entry("EXAMPLE_KEY");
    expect(created.status).toBe(201);
    const jobId = String(((await entryBody(created))["job"] as Record<string, unknown>)["id"]);
    const cancelled = await started.post(`/api/v1/jobs/${jobId}/cancel`, {});
    expect(cancelled.status).toBe(200);
    const view = (await cancelled.json()) as Record<string, unknown>;
    expect(view["state"], "取消不等重查：响应里作业仍在跑").toBe("running");
    expect(begins(started.report).length, "重查还没放行：只有 secret set 那一个子进程").toBe(1);
    writeFileSync(join(started.dir, "check-gate"), "go"); // 放行重查
    const terminal = await waitTerminal(started.jobs, jobId);
    expect(terminal["state"]).toBe("cancelled");
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect((envelope["data"] as Record<string, unknown>)["check"]).not.toBeNull();
  });

  it("退出 0 但 stdout 解析不了 → failed/invalid-json，exit_code 是 0、set 为 null", async () => {
    started = await startApp();
    process.env["FAKE_SECRET_STDOUT"] = "这不是 JSON";
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "invalid-json-gate");
    const created = await started.entry("EXAMPLE_KEY");
    expect(created.status).toBe(201);
    const jobId = String(((await entryBody(created))["job"] as Record<string, unknown>)["id"]);
    writeFileSync(join(started.dir, "invalid-json-gate"), "go"); // 放行：子进程打一行不是 JSON 的 stdout 后退出 0
    const terminal = await waitTerminal(started.jobs, jobId);
    expect(terminal["state"]).toBe("failed");
    expect(terminal["reason"]).toBe("invalid-json");
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(false);
    expect(envelope["exit_code"]).toBe(0);
    expect((envelope["data"] as Record<string, unknown>)["set"]).toBeNull();
    expect((envelope["data"] as Record<string, unknown>)["check"]).not.toBeNull();
    expect(envelope["messages"]).toEqual(["ERROR: 内核输出不是合法的 JSON"]);
  });

  it("服务一侧超时 → timed_out 且 check 不为 null", async () => {
    started = await startApp({ timeouts: { "job.secret-entry": 1, "secret-entry.handshake": 30 } });
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "job-timeout-gate");
    const created = await started.entry("EXAMPLE_KEY");
    expect(created.status).toBe(201);
    const jobId = String(((await entryBody(created))["job"] as Record<string, unknown>)["id"]);
    const terminal = await waitTerminal(started.jobs, jobId);
    expect(terminal["state"]).toBe("timed_out");
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(false);
    expect(envelope["exit_code"]).toBeNull();
    expect((envelope["messages"] as string[]).length).toBe(1);
    expect((envelope["data"] as Record<string, unknown>)["check"]).not.toBeNull();
    await waitDead(begins(started.report)[0]?.pid ?? 0);
  });
});

describe("地址只活在这一次请求里（D04）", () => {
  it("作业查询、SSE、messages、command 与访问日志五处都搜不到那 32 个字符", async () => {
    started = await startApp();
    const sse = await openEvents(started);
    const created = await started.entry("EXAMPLE_KEY");
    expect(created.status).toBe(201);
    const body = await entryBody(created);
    const url = String(body["url"]);
    const token = tokenOf(url);
    expect(token.length).toBe(32);
    const jobId = String((body["job"] as Record<string, unknown>)["id"]);
    const terminal = await waitTerminal(started.jobs, jobId);
    const envelope = terminal["envelope"] as Record<string, unknown>;
    const queryText = await (await started.get(`/api/v1/jobs/${jobId}`)).text();
    expect(queryText, "作业查询").not.toContain(token);
    expect(sse.text(), "SSE").not.toContain(token);
    expect(JSON.stringify(envelope["messages"]), "messages").not.toContain(token);
    expect(JSON.stringify(envelope["command"]), "command").not.toContain(token);
    expect(JSON.stringify(started.app.accessLog.entries()), "访问日志").not.toContain(token);
    expect(started.app.accessLog.entries().some((entry) => entry.route === "api.secrets.entry")).toBe(true);
    sse.close();
  });
});

describe("kernel.ts 的 onStderr 钩子（D01）", () => {
  it("子进程还活着时就收到 stderr 的那一行，退出之后不再有新文本", async () => {
    started = await startApp();
    const seen: string[] = [];
    process.env["FAKE_SECRET_GATE"] = join(started.dir, "hook-gate");
    const running = started.runner.run(["config", "secret", "set", "EXAMPLE_KEY", "--no-browser", "--timeout=600"], 30, new AbortController().signal, {
      onStderr: (text) => seen.push(text),
    });
    const deadline = Date.now() + 10_000;
    while (seen.length === 0 && Date.now() < deadline) await sleep(20);
    expect(seen.length, "子进程退出之前钩子就收到了 stderr").toBeGreaterThan(0);
    expect(seen[0]).toContain('"url"');
    const pid = begins(started.report)[0]?.pid ?? 0;
    expect(pidAlive(pid), "收到钩子时子进程还在跑").not.toBe(false);
    expect(readReport(started.report).some((line) => line.event === "end"), "还没放行：子进程没退出").toBe(false);
    writeFileSync(join(started.dir, "hook-gate"), "go");
    const outcome = await running;
    expect(outcome.kind).toBe("completed");
  });

  it("不传钩子时行为照旧（completed、stdout 照读）", async () => {
    started = await startApp();
    const outcome = await started.runner.run(["config", "secret", "set", "EXAMPLE_KEY", "--no-browser", "--timeout=600"], 30, new AbortController().signal);
    expect(outcome.kind).toBe("completed");
    if (outcome.kind !== "completed") return;
    expect(outcome.result.exit_code).toBe(0);
    expect((JSON.parse(outcome.stdout) as Record<string, unknown>)["stored"]).toBe(true);
  });
});

/** 开一条进程内的 SSE 订阅（hub 也在这一批 extraRoutes 里），把收到的文本攒起来。 */
async function openEvents(app: SecretApp): Promise<{ text(): string; close(): void }> {
  const controller = new AbortController();
  const response = await app.app.fetch(
    new Request("http://127.0.0.1:1/api/v1/events", { headers: { host: "127.0.0.1:1", cookie: app.cookie }, signal: controller.signal }),
  );
  expect(response.status).toBe(200);
  const reader = response.body?.getReader();
  let text = "";
  void (async () => {
    try {
      for (;;) {
        const chunk = await reader?.read();
        if (chunk === undefined || chunk.done) break;
        text += new TextDecoder().decode(chunk.value);
      }
    } catch {
      // 订阅被关：不再收
    }
  })();
  return { text: () => text, close: () => controller.abort() };
}
