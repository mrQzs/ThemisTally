// T042 的两条 Quizs 只读路由（合同 t042-desktop-web-quizs-facts v1）：替身部分照 kernel-runner.test.ts 与 support.ts 的
// startApp 写法（内核子进程走 test/fixtures/fake-kernel.mjs），钉住 argv、信封七字段、两份白名单的遮盖行为、退出非 0 与
// 超时映射；真内核部分起真的内核（scripts/pi_dispatch.py，解释器用 THEMIS_PYTHON，仓库路径从 harness.ts 的 REPO_ROOT
// 推出来，不写死任何机器上的绝对路径），在 git 夹具仓库上把 QUIZS_CMD 指向夹具里的假 Quizs 脚本，覆盖两条路由的 argv、
// 信封、退出 1 与「某一套 live 读不出来」的逐套 problem。QUIZS_CMD 与三个 QUIZS_LIVE_* 用完恢复原状（执行机器上可能
// 本来就设着这三个变量，不清掉会让 live 多出一行来自环境的套）。
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ENVELOPE_KEYS } from "../src/envelope.ts";
import { createApp, type App } from "../src/app.ts";
import { CursorTable } from "../src/cursors.ts";
import { KernelRunner } from "../src/kernel.ts";
import { READ_ROUTE_ARGV, readRoutes } from "../src/readroutes.ts";
import { REPO_ROOT } from "./harness.ts";
import { envelopeOf, readReport, startApp, type StartedApp } from "./support.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py");

/** providers 形状的一份 JSON（替身的 FAKE_KERNEL_JSON）：第一行带越界的 thinking 档位与计费方式、凭据形状的键；第二行是合法基线。 */
const PROVIDERS_JSON = JSON.stringify({
  build_id: "fake-build-2026",
  providers: [
    { provider: "deepseek", id: "deepseek-api", model: "deepseek-chat", thinking: ["off", "high", "turbo"], billing: "monthly", credential_ref: "cred-1", access_tokens: ["t-1"] },
    { provider: "stepfun", model: "step-plan", thinking: ["max"], billing: "step_plan_credits" },
  ],
});

/** live 形状的一份 JSON：第一套合法（三位毫秒的 ISO、毫秒整数、三个文件名）；第二套 state 越界、missing 里塞第四个名字、valid_until 缺毫秒。 */
const LIVE_JSON = JSON.stringify({
  live: [
    { source: "mailbox", provider: "deepseek", live_dir: "/tmp/quizs-live/deepseek", problem: null,
      status: { state: "ready", problem: null, missing: ["plan.json", "profile.json", "qualification.json"],
        certificate: { issued_at_ms: 1789000000000, expires_at_ms: 1790000000000 },
        profile: { id: "deepseek-api", valid_until: "2026-11-14T08:00:00.000Z" } } },
    { source: "mailbox", provider: "minimax", live_dir: "/tmp/quizs-live/minimax", problem: "缺 plan.json",
      status: { state: "Ready", problem: "证书过期", missing: ["plan.json", "notes.txt"],
        certificate: { expires_at_ms: 1790000000000 },
        profile: { valid_until: "2026-11-14T08:00:00Z" } } },
  ],
});

const rows = (data: unknown, key: string): Record<string, unknown>[] => (data as Record<string, unknown>)[key] as Record<string, unknown>[];

/** 真内核那部分起的进程内应用（startApp 只给替身的 python/kernel，这里自己建：内核子进程走 scripts/pi_dispatch.py）。 */
interface RealApp {
  get(target: string): Promise<Response>;
  dispose(): Promise<void>;
}

async function startRealKernel(repo: string, assets: string): Promise<RealApp> {
  const runner = new KernelRunner({ repo, python: PYTHON, kernel: KERNEL });
  const app: App = createApp({
    port: 1,
    assets,
    controlToken: "t".repeat(43),
    extraRoutes: readRoutes({ repo, runner, cursors: new CursorTable(), transcript: [] }, {}),
  });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request("http://127.0.0.1:1/bootstrap/" + nonce, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  return {
    get: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie } })),
    dispose: async () => {
      await runner.shutdown();
    },
  };
}

describe("替身：两条 Quizs 读路由的 argv、信封与白名单", () => {
  let started: StartedApp | null = null;

  beforeEach(() => {
    delete process.env["FAKE_KERNEL_JSON"];
    delete process.env["FAKE_KERNEL_STDERR"];
    delete process.env["FAKE_KERNEL_SLEEP_MS"];
    delete process.env["FAKE_KERNEL_EXIT"];
  });

  afterEach(async () => {
    delete process.env["FAKE_KERNEL_JSON"];
    delete process.env["FAKE_KERNEL_STDERR"];
    delete process.env["FAKE_KERNEL_SLEEP_MS"];
    delete process.env["FAKE_KERNEL_EXIT"];
    await started?.dispose();
    started = null;
  });

  it("GET /api/v1/quizs/providers：argv 逐字是 config quizs providers --json，信封七字段齐全", async () => {
    started = await startApp();
    const response = await started.get("/api/v1/quizs/providers");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(Object.keys(body)).toEqual([...ENVELOPE_KEYS]);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    expect(body["command"]).toEqual(["config", "quizs", "providers", "--json"]);
    expect(body["command"]).toEqual([...READ_ROUTE_ARGV["api.quizs.providers.get"] ?? []]);
    const begin = readReport(started.report).filter((line) => line.event === "begin").at(-1);
    expect(begin?.argv).toEqual(["config", "quizs", "providers", "--json"]);
    expect(typeof body["elapsed_ms"]).toBe("number");
  });

  it("GET /api/v1/quizs/live：argv 逐字是 config quizs live --json，信封七字段齐全", async () => {
    started = await startApp();
    const response = await started.get("/api/v1/quizs/live");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(Object.keys(body)).toEqual([...ENVELOPE_KEYS]);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    expect(body["command"]).toEqual(["config", "quizs", "live", "--json"]);
    expect(body["command"]).toEqual([...READ_ROUTE_ARGV["api.quizs.live.get"] ?? []]);
    const begin = readReport(started.report).filter((line) => line.event === "begin").at(-1);
    expect(begin?.argv).toEqual(["config", "quizs", "live", "--json"]);
    expect(typeof body["elapsed_ms"]).toBe("number");
  });

  it("providers 的白名单：provider/model 原样，越界的 thinking 档位与 billing 变 <redacted>，凭据形状的键遮掉", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_JSON"] = PROVIDERS_JSON;
    const response = await started.get("/api/v1/quizs/providers");
    expect(response.status).toBe(200);
    const providers = rows((await envelopeOf(response))["data"], "providers");
    expect(providers).toHaveLength(2);
    expect(providers[0]?.["provider"]).toBe("deepseek");
    expect(providers[0]?.["model"]).toBe("deepseek-chat");
    expect(providers[0]?.["thinking"]).toEqual(["off", "high", "<redacted>"]);
    expect(providers[0]?.["billing"]).toBe("<redacted>");
    expect(providers[0]?.["credential_ref"]).toBe("<redacted>");
    expect((providers[0]?.["access_tokens"] as unknown[])[0]).toBe("<redacted>");
    expect(providers[1]?.["provider"]).toBe("stepfun");
    expect(providers[1]?.["thinking"]).toEqual(["max"]);
    expect(providers[1]?.["billing"]).toBe("step_plan_credits");
  });

  it("live 的白名单：放行的字段原样，越界的 state 与第四个 missing 文件名变 <redacted>，problem 透传自由文字", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_JSON"] = LIVE_JSON;
    const response = await started.get("/api/v1/quizs/live");
    expect(response.status).toBe(200);
    const live = rows((await envelopeOf(response))["data"], "live");
    expect(live).toHaveLength(2);
    const ok = live[0] ?? {};
    expect(ok["source"]).toBe("mailbox");
    expect(ok["provider"]).toBe("deepseek");
    expect(ok["problem"]).toBeNull();
    const status = ok["status"] as Record<string, unknown>;
    expect(status["state"]).toBe("ready");
    expect(status["missing"]).toEqual(["plan.json", "profile.json", "qualification.json"]);
    const certificate = status["certificate"] as Record<string, unknown>;
    expect(Number(certificate["expires_at_ms"])).toBe(1790000000000);
    expect((status["profile"] as Record<string, unknown>)["valid_until"]).toBe("2026-11-14T08:00:00.000Z");
    const bad = live[1] ?? {};
    expect(bad["problem"], "逐套 problem 是自由文字，原样透传").toBe("缺 plan.json");
    const badStatus = bad["status"] as Record<string, unknown>;
    expect(badStatus["state"], "越界的 state 应遮成 <redacted>").toBe("<redacted>");
    expect(badStatus["problem"]).toBe("证书过期");
    expect(badStatus["missing"]).toEqual(["plan.json", "<redacted>"]);
  });

  it("内核退出非 0：回 200、ok 为假、exit_code 原样", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_EXIT"] = "1";
    process.env["FAKE_KERNEL_STDERR"] = "ERROR: quizs providers 失败";
    const response = await started.get("/api/v1/quizs/providers");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(1);
    expect(body["messages"]).toEqual(["ERROR: quizs providers 失败"]);
  });

  it("超时：504，exit_code 是 null、messages 只有一行提示原文", async () => {
    started = await startApp({ timeouts: { "api.quizs.live.get": 1 } });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "8000";
    const response = await started.get("/api/v1/quizs/live");
    expect(response.status).toBe(504);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(null);
    expect(body["data"]).toBe(null);
    expect(body["command"]).toEqual(["config", "quizs", "live", "--json"]);
    expect(body["messages"]).toEqual(["ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看"]);
  });
});

describe("真内核：QUIZS_CMD 指向夹具里的假 Quizs 脚本", () => {
  let dir = "";
  let repo = "";
  let real: RealApp | null = null;
  /** 这台机器上可能本来就设着 QUIZS_*（用例里删掉、用完还原）。 */
  const ambient = new Map<string, string | undefined>();
  const QUIZS_ENV = ["QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"];

  beforeEach(() => {
    for (const name of QUIZS_ENV) {
      ambient.set(name, process.env[name]);
      delete process.env[name];
    }
    dir = mkdtempSync(join(tmpdir(), "themis-ui-quizs-real-"));
    repo = join(dir, "repo");
    mkdirSync(repo, { recursive: true });
    for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
      const done = spawnSync("git", args, { encoding: "utf8" });
      if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
    }
    writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
    writeFileSync(join(repo, ".gitignore"), ".agent/\n");
    // 信箱里放一套 live 文件：内核据此列出 source 是 mailbox 的一套（目录名就是提供方）
    const liveDir = join(repo, ".agent", "mailbox", "quizs-live", "deepseek");
    mkdirSync(liveDir, { recursive: true });
    for (const name of ["plan.json", "profile.json", "qualification.json"]) {
      writeFileSync(join(liveDir, name), '{"schema_version": "quizs.fixture.v1"}\n', "utf8");
    }
    spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
    spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
    // 假 Quizs 脚本：内核按 QUIZS_CMD 起它，argv 是 providers list 或 live status --live-dir <目录>；按第一参数分两支打印
    // 带 schema_version 的 JSON，FAKE_QUIZS_FAIL=1 时那一支退出 1 并往 stderr 写一行（providers 整条失败、live 只记问题）
    const quizsScript = join(dir, "fake-quizs.mjs");
    writeFileSync(
      quizsScript,
      [
        "const args = process.argv.slice(2);",
        "const fail = process.env['FAKE_QUIZS_FAIL'] === '1';",
        "const say = (payload) => { process.stdout.write(`${JSON.stringify(payload)}\\n`); process.exit(0); };",
        "if (args[0] === 'providers') {",
        "  if (fail) { process.stderr.write('ERROR: fake quizs providers 失败\\n'); process.exit(1); }",
        "  say({ schema_version: 'quizs.providers.v1', build_id: 'fake-build-2026',",
        "        providers: [{ provider: 'deepseek', id: 'deepseek-api', model: 'deepseek-chat', thinking: ['off', 'high'], billing: 'step_plan_credits' }] });",
        "}",
        "if (args[0] === 'live') {",
        "  if (fail) { process.stderr.write('ERROR: fake quizs live status 失败\\n'); process.exit(1); }",
        "  say({ schema_version: 'quizs.live-status.v1', state: 'ready',",
        "        certificate: { issued_at_ms: 1789000000000, expires_at_ms: 1790000000000 },",
        "        profile: { id: 'deepseek-api', valid_until: '2026-11-14T08:00:00.000Z' } });",
        "}",
        "process.stderr.write('ERROR: fake quizs 不认得这个参数\\n');",
        "process.exit(2);",
      ].join("\n"),
      "utf8",
    );
    process.env["QUIZS_CMD"] = JSON.stringify([process.execPath, quizsScript]);
  });

  afterEach(async () => {
    await real?.dispose();
    real = null;
    delete process.env["FAKE_QUIZS_FAIL"];
    for (const [name, value] of ambient) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
    ambient.clear();
    if (dir !== "") rmSync(dir, { recursive: true, force: true });
    dir = "";
  });

  it("GET /api/v1/quizs/providers：真内核跑通，argv 与 data 逐字段一致", async () => {
    real = await startRealKernel(repo, dir);
    const response = await real.get("/api/v1/quizs/providers");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    expect(body["command"]).toEqual(["config", "quizs", "providers", "--json"]);
    const providers = rows(body["data"], "providers");
    expect(providers).toHaveLength(1);
    expect(providers[0]?.["provider"]).toBe("deepseek");
    expect(providers[0]?.["model"]).toBe("deepseek-chat");
    expect(providers[0]?.["thinking"]).toEqual(["off", "high"]);
    expect(providers[0]?.["billing"]).toBe("step_plan_credits");
  });

  it("GET /api/v1/quizs/live：信箱那一套 state 是 ready，证书到期毫秒与 valid_until 原样", async () => {
    real = await startRealKernel(repo, dir);
    const response = await real.get("/api/v1/quizs/live");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    expect(body["command"]).toEqual(["config", "quizs", "live", "--json"]);
    const live = rows(body["data"], "live");
    const mailbox = live.find((row) => row["source"] === "mailbox");
    expect(mailbox, "信箱里应有一套").toBeDefined();
    expect(mailbox?.["provider"]).toBe("deepseek");
    const status = mailbox?.["status"] as Record<string, unknown>;
    expect(status["state"]).toBe("ready");
    const certificate = status["certificate"] as Record<string, unknown>;
    expect(Number(certificate["expires_at_ms"])).toBe(1790000000000);
    expect((status["profile"] as Record<string, unknown>)["valid_until"]).toBe("2026-11-14T08:00:00.000Z");
  });

  it("假 Quizs 对 providers 退出 1：仍回 200、ok 为假、exit_code 是 1、messages 带内核的 ERROR: 原文", async () => {
    real = await startRealKernel(repo, dir);
    process.env["FAKE_QUIZS_FAIL"] = "1";
    const response = await real.get("/api/v1/quizs/providers");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(1);
    const messages = body["messages"] as string[];
    expect(messages.some((line) => line.startsWith("ERROR:")), `messages 应含内核原文：${JSON.stringify(messages)}`).toBe(true);
  });

  it("假 Quizs 对 live 退出非 0：整条路由回 200、ok 为真，那一行的 problem 有内容", async () => {
    real = await startRealKernel(repo, dir);
    process.env["FAKE_QUIZS_FAIL"] = "1";
    const response = await real.get("/api/v1/quizs/live");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    const live = rows(body["data"], "live");
    const mailbox = live.find((row) => row["source"] === "mailbox");
    expect(mailbox, "信箱里应有一套").toBeDefined();
    expect(typeof mailbox?.["problem"], "内核只在该行写原因").toBe("string");
    expect((mailbox?.["problem"] as string).length).toBeGreaterThan(0);
    expect(mailbox?.["status"], "读不出来的那一套没有 status").toBeNull();
  });
});
