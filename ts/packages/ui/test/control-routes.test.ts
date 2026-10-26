// 控制门与两条取消路由的进程内用例（桌面端 §5.3、U18b、D09/D10/D11）：门只按 Route.control 判断（app.ts 一处），
// 表里所有 control === true 的路由逐条过令牌错、只带 cookie、外来 Origin 三种拒绝，第 6 次令牌错起 429 带
// Retry-After，外来 Origin 不计限速；控制路由免 CSRF、不读正文。另覆盖 cancelJob 共用的 404/409/200、控制取消不等
// 重查（M15）与取消之后子进程已经不在（M20）。计时用门文件卡先后，不靠睡眠时长或墙钟。
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pidAlive } from "@themis/base/process";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { EventHub } from "../src/events.ts";
import { jobRoutes } from "../src/jobroutes.ts";
import { jobView, type JobRecord, JobTable } from "../src/jobs.ts";
import { KernelRunner } from "../src/kernel.ts";
import { ROUTES, type Route } from "../src/routes.ts";
import { secretEntryRoutes } from "../src/secretentry.ts";
import { TS_ROOT } from "./harness.ts";
import { type ReportLine, readReport } from "./support.ts";

const FAKE_SECRET_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-secret-kernel.mjs");
const CONTROL_TOKEN = "c".repeat(43);
const CONTROL_HEADER = "x-themis-control";
const PROBE_PATH = "/control/probe";
const SAMPLE_JOB_ID = "A".repeat(43);
/** 每条 control 路由的示例路径（表驱动与「都在 /control/ 下」都用它）。 */
const SAMPLES: Readonly<Record<string, string>> = {
  "control.bootstrap": "/control/bootstrap",
  "control.jobs.cancel": `/control/jobs/${SAMPLE_JOB_ID}/cancel`,
  "control.probe": PROBE_PATH,
};
const FAKE_VARS = ["FAKE_SECRET_URL", "FAKE_SECRET_GATE", "FAKE_SECRET_CHECK_GATE", "FAKE_SECRET_SILENT", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_PIDFILE"];

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

interface ControlApp {
  readonly app: App;
  readonly runner: KernelRunner;
  readonly jobs: JobTable;
  readonly report: string;
  readonly dir: string;
  readonly cookie: string;
  /** 表里所有 control === true 的路由（与交给 createApp 的是同一批对象）。 */
  readonly controlRoutes: readonly Route[];
  readonly probeRan: { value: boolean };
  post(target: string, body: unknown): Promise<Response>;
  entry(name: string): Promise<Response>;
  control(path: string, headers: Readonly<Record<string, string>>): Promise<Response>;
  advance(ms: number): void;
  dispose(): Promise<void>;
}

async function startApp(): Promise<ControlApp> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-control-"));
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_REPORT"] = report;
  let clock = 1_000_000;
  const runner = new KernelRunner({ repo: TS_ROOT, python: process.execPath, kernel: FAKE_SECRET_KERNEL });
  const hub = new EventHub({ repo: TS_ROOT, runner });
  const jobs = new JobTable();
  const probeRan = { value: false };
  const probe: Route = {
    name: "control.probe",
    method: "POST",
    pattern: new RegExp(`^${PROBE_PATH}$`, "u"),
    control: true, // 探针路由：证明门只按 control 标记判，不按路由名特判（M21）
    handle: () => {
      probeRan.value = true;
      return new Response('{"ok":true}\n', { status: 200, headers: { "content-type": "application/json; charset=utf-8" } });
    },
  };
  const jobRouteList = jobRoutes(runner, jobs);
  const entryRouteList = secretEntryRoutes(runner, jobs);
  const extraRoutes = [...jobRouteList, ...entryRouteList, probe];
  const app = createApp({
    port: 1,
    assets: dir,
    controlToken: CONTROL_TOKEN,
    now: () => clock, // 注入时钟：限速的锁定与放行都看得见
    extraRoutes,
  });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  const controlRoutes = [...ROUTES, ...jobRouteList, ...entryRouteList, probe].filter((route) => route.control === true);
  return {
    app,
    runner,
    jobs,
    report,
    dir,
    cookie,
    controlRoutes,
    probeRan,
    post: (target, body) =>
      app.fetch(
        new Request(`http://127.0.0.1:1${target}`, {
          method: "POST",
          headers: { host: "127.0.0.1:1", cookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" },
          body: JSON.stringify(body),
        }),
      ),
    entry: (name) =>
      app.fetch(
        new Request(`http://127.0.0.1:1/api/v1/secrets/${name}/entry`, {
          method: "POST",
          headers: { host: "127.0.0.1:1", cookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" },
          body: "{}",
        }),
      ),
    // 控制请求：只带头（正文一律不发，控制路由也不读正文）
    control: (path, headers) =>
      app.fetch(new Request(`http://127.0.0.1:1${path}`, { method: "POST", headers: { host: "127.0.0.1:1", ...headers } })),
    advance: (ms) => {
      clock += ms;
    },
    dispose: async () => {
      delete process.env["FAKE_KERNEL_REPORT"];
      hub.close();
      await runner.shutdown();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

let started: ControlApp | null = null;

beforeEach(() => {
  for (const name of FAKE_VARS) delete process.env[name];
});

afterEach(async () => {
  for (const name of FAKE_VARS) delete process.env[name];
  await started?.dispose();
  started = null;
});

function begins(report: string): ReportLine[] {
  return readReport(report).filter((line) => line.event === "begin");
}

async function waitTerminal(jobs: JobTable, id: string, timeoutMs = 30_000): Promise<Record<string, unknown>> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const record = jobs.get(id);
    if (record !== null && ["succeeded", "failed", "cancelled", "timed_out"].includes(record.state)) return jobView(record) as Record<string, unknown>;
    if (Date.now() > deadline) throw new Error(`作业没到终态：${record === null ? "不在表里" : record.state}`);
    await sleep(25);
  }
}

async function waitDead(pid: number, timeoutMs = 15_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && pidAlive(pid) !== false) await sleep(120);
  expect(pidAlive(pid), `pid ${pid} 应已不在`).toBe(false);
}

describe("控制门按 Route.control 统一判断（D09）", () => {
  it("表里所有 control === true 的路由：令牌错、只带 cookie、外来 Origin 都回 403，处理函数都没跑", async () => {
    started = await startApp();
    expect(started.controlRoutes.map((route) => route.name).sort()).toEqual(["control.bootstrap", "control.jobs.cancel", "control.probe"]);
    for (const route of started.controlRoutes) {
      const path = SAMPLES[route.name] ?? "";
      expect(path, `${route.name} 应有示例路径`).not.toBe("");
      const wrongToken = await started.control(path, { [CONTROL_HEADER]: "w".repeat(43) });
      expect(wrongToken.status, `${route.name} 令牌错`).toBe(403);
      expect((await wrongToken.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 请求被拒绝"]);
      started.advance(61_000); // 过掉限速锁定：这一条只断言 403
      const cookieOnly = await started.control(path, { cookie: started.cookie });
      expect(cookieOnly.status, `${route.name} 只带 cookie`).toBe(403);
      started.advance(61_000);
      const foreignOrigin = await started.control(path, { origin: "http://evil.example", [CONTROL_HEADER]: CONTROL_TOKEN });
      expect(foreignOrigin.status, `${route.name} 外来 Origin`).toBe(403);
      started.advance(61_000);
    }
    expect(started.probeRan.value, "门没过处理函数就没跑").toBe(false);
  });

  it("/control/ 开头的路由都是 control，control 路由都在 /control/ 下", async () => {
    started = await startApp();
    const all = [...ROUTES, ...started.controlRoutes];
    for (const route of all) {
      const source = [...route.pattern.source].filter((ch) => ch !== String.fromCharCode(92)).join(""); // 正则源里 / 是转义写法
      const underControl = source.startsWith("^/control/");
      if (underControl) expect(route.control, `${route.name} 在 /control/ 下，应标 control`).toBe(true);
      if (route.control === true) expect(underControl, `${route.name} 标了 control，应在 /control/ 下`).toBe(true);
    }
  });

  it("连续 5 次令牌错之后第 6 次回 429 带 Retry-After；过掉锁定之后对的令牌又能用", async () => {
    started = await startApp();
    for (let i = 0; i < 5; i += 1) {
      const response = await started.control("/control/bootstrap", { [CONTROL_HEADER]: "w".repeat(43) });
      expect(response.status, `第 ${i + 1} 次令牌错`).toBe(403);
    }
    const limited = await started.control("/control/bootstrap", { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(limited.status).toBe(429);
    expect(limited.headers.get("retry-after")).toBe("1");
    expect((await limited.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 控制令牌失败次数过多"]);
    started.advance(61_000);
    const ok = await started.control("/control/bootstrap", { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(ok.status).toBe(200);
  });

  it("外来 Origin 的失败不计入令牌限速", async () => {
    started = await startApp();
    for (let i = 0; i < 6; i += 1) {
      const response = await started.control("/control/bootstrap", { origin: "http://evil.example", [CONTROL_HEADER]: "w".repeat(43) });
      expect(response.status, `第 ${i + 1} 次外来 Origin`).toBe(403);
    }
    const ok = await started.control("/control/bootstrap", { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(ok.status, "外来 Origin 不计限速：对的令牌照旧 200").toBe(200);
    const body = (await ok.json()) as Record<string, unknown>;
    expect(typeof (body["data"] as Record<string, unknown>)["bootstrap"]).toBe("string");
  });

  it("control.bootstrap 只带令牌、不带正文也回 200（免 CSRF、不读正文）", async () => {
    started = await startApp();
    const response = await started.control("/control/bootstrap", { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(response.status).toBe(200);
    const body = (await response.json()) as Record<string, unknown>;
    const bootstrap = String((body["data"] as Record<string, unknown>)["bootstrap"]);
    expect(bootstrap.startsWith("http://127.0.0.1:1/bootstrap/")).toBe(true);
    // 换了引导地址之后旧会话作废：拿不到新 cookie 的请求一律 401
    expect((await started.app.fetch(new Request("http://127.0.0.1:1/api/v1/ping", { headers: { host: "127.0.0.1:1", cookie: started.cookie } }))).status).toBe(401);
  });
});

describe("两条取消路由共用 cancelJob（D10/D11）", () => {
  it("不存在的作业 404；已终态 409；正常取消回 200 与当时的八键作业对象", async () => {
    started = await startApp();
    const missing = await started.control(`/control/jobs/${SAMPLE_JOB_ID}/cancel`, { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(missing.status).toBe(404);
    expect((await missing.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 没有这个作业"]);
    const done = started.jobs.create("secret-entry", ["config", "secret", "set", "EXAMPLE_KEY"], 30, Date.now());
    if (done === null) throw new Error("建不出作业");
    done.state = "succeeded";
    done.finished_ms = Date.now();
    const conflict = await started.control(`/control/jobs/${done.id}/cancel`, { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(conflict.status).toBe(409);
    expect((await conflict.json() as Record<string, unknown>)["messages"]).toEqual(["ERROR: 作业已经结束"]);
  });

  it("控制取消不等重查：响应先到、作业仍 running，放行之后 cancelled 且 check 不为 null、子进程已经不在", async () => {
    started = await startApp();
    process.env["FAKE_SECRET_CHECK_GATE"] = join(started.dir, "check-gate");
    const created = await started.entry("EXAMPLE_KEY");
    expect(created.status).toBe(201);
    const body = (await created.json()) as Record<string, unknown>;
    const jobId = String((body["job"] as Record<string, unknown>)["id"]);
    const pid = begins(started.report)[0]?.pid ?? 0;
    const cancelled = await started.control(`/control/jobs/${jobId}/cancel`, { [CONTROL_HEADER]: CONTROL_TOKEN });
    expect(cancelled.status).toBe(200);
    const view = (await cancelled.json()) as Record<string, unknown>;
    expect(Object.keys(view).sort()).toEqual(["created_ms", "envelope", "finished_ms", "id", "kind", "reason", "started_ms", "state"]);
    expect(view["state"], "取消不等重查：响应里作业仍在跑").toBe("running");
    expect(begins(started.report).length, "重查还没放行：只有 secret set 那一个子进程").toBe(1);
    expect(pidAlive(pid), "取消之后子进程已经不在").toBe(false);
    writeFileSync(join(started.dir, "check-gate"), "go"); // 放行重查
    const terminal = await waitTerminal(started.jobs, jobId);
    expect(terminal["state"]).toBe("cancelled");
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect((envelope["data"] as Record<string, unknown>)["check"]).not.toBeNull();
    await waitDead(pid);
  });
});
