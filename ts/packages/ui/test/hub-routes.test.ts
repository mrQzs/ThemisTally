// T031 的替身用例（桌面端 §5.3、D01–D06、U4/U6/U9）：起真的服务进程（Bun，照 write-real-config 的写法用 harness 的
// startService），两个替身各起各自的服务实例。读路由一支的内核子进程走 fake-kernel.mjs，用 FAKE_KERNEL_JSON 给一份
// config hub show 形状的 JSON，核对 argv、401 与 HUB_ROLES_ALLOW 的逐字段脱敏；写路由一支走 fake-write-kernel.mjs，核对
// hub.set/hub.unset 的参数校验（400）、确认号的四种 409、--yes/--expect-state 与令牌不外泄、预览 action 不符回 500。等子进程
// 起来照 kernel-runner.test.ts 的 waitForBegin 写法（不固定睡）；确认号过期经 serve-overrides 的 confirmationTtlMs 把 TTL
// 调短，睡过 TTL 再执行（TTL 的等待，不是等子进程起来的竞态）。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { header, request, startService, type RawResponse } from "./harness.ts";
import { readReport } from "./support.ts";
import { TS_ROOT } from "./harness.ts";

const FAKE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-kernel.mjs");
const FAKE_WRITE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-write-kernel.mjs");
const STATE = `v1;config=${"0".repeat(64)}`;
const CONFIRM_409 = "确认号无效、已过期或已用过：请重新预览";
const ARGV_409 = "确认号与这次请求的参数不符：请重新预览";
const PREVIEW_500 = "内核的预览不合格";

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

/** 等替身报告里出现 count 条 begin 行（子进程真的起来了），照 kernel-runner 的 waitForBegin 写法。 */
async function waitForBegins(report: string, count: number): Promise<void> {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      if (readReport(report).filter((line) => line.event === "begin").length >= count) return;
    } catch {
      // 半行
    }
    await sleep(50);
  }
}

/** config hub show --json 形状的一份 JSON：六个岗位各一行。含缺省行那种 null（row0/1）、一行越界枚举与一行凭据形状的
 * model（row3/4）；另在 row3–5 放几个形状不合法的绑定名/ID（带空格、越界 ID），核对 allowBindingName/allowNullableId 的正则
 * 与 ID 约束把这些遮成 <redacted>（这些值默认脱敏不会遮，是白名单约束杀 M1 的面）。 */
const HUB_POSTS_JSON = JSON.stringify({
  posts: [
    { post: "coordinator", source: "default", allowed_adapters: ["quizs", "pi"], adapter: "quizs", provider: "deepseek", model: "deepseek-flash", thinking: "high", fallback: { adapter: "pi", provider: "dsf", model: "deepseek-flash", thinking: "high" }, profile: null, runtime: null },
    { post: "planner", source: "default", allowed_adapters: ["claude-code"], adapter: "claude-code", provider: null, model: "claude-opus-5-5", thinking: "max", fallback: null, profile: null, runtime: null },
    { post: "contract", source: "config", allowed_adapters: ["pi"], adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "high", profile: "demo-profile", runtime: "demo-runtime", fallback: null },
    { post: "gate", source: "config", allowed_adapters: ["pi"], adapter: "bogus-adapter", provider: "cc-switch-zhipu-glm", model: "bad model", thinking: "high", profile: "demo-profile", runtime: "demo-runtime", fallback: null },
    { post: "audit", source: "config", allowed_adapters: ["pi"], adapter: "pi", provider: "bad provider", model: "sk-abcdefghijklmnopqrstuvwxyz012345", thinking: "max", profile: "Bad_Profile", runtime: "demo-runtime", fallback: null },
    { post: "exec", source: "config", allowed_adapters: ["pi"], adapter: "pi", provider: "cc-switch-step-fun", model: "step-5-preview", thinking: "high", profile: "demo-profile", runtime: "demo-runtime", fallback: { adapter: "pi", provider: "dsf", model: "bad model", thinking: "high", profile: "fb-profile", runtime: "fb-runtime" } },
  ],
});

interface HubService {
  readonly port: number;
  readonly report: string;
  get(target: string): Promise<RawResponse>;
  post(target: string, body: unknown): Promise<RawResponse>;
  dispose(): void;
}

/** 起一个真的服务进程：内核子进程走给定替身，env 合进服务子进程环境（替身据此演命令），overrides 只给测试入口。 */
async function startHubService(kernel: string, env: Readonly<Record<string, string>>, overrides: Readonly<Record<string, unknown>>): Promise<HubService> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-hub-"));
  const report = join(dir, "report.jsonl");
  const assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>hub</title>\n");
  const service = await startService({ repo: dir, assets, python: process.execPath, kernel, entry: "overrides", overrides, env: { FAKE_KERNEL_REPORT: report, ...env } });
  const nonce = service.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(service.port, "GET", `/bootstrap/${nonce}`);
  const cookie = (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
  const port = service.port;
  const withCookie: [string, string][] = [["Cookie", cookie]];
  return {
    port,
    report,
    get: (target) => request(port, "GET", target, withCookie),
    post: (target, body) =>
      request(port, "POST", target, [...withCookie, ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]], Buffer.from(JSON.stringify(body))),
    dispose: () => {
      service.kill();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** 响应正文里的 messages 数组。 */
function messagesOf(res: RawResponse): unknown {
  return (JSON.parse(res.body.toString("utf8")) as Record<string, unknown>)["messages"];
}

/** 执行那一支的 argv（begin 行里带 --expect-state= 的）。 */
function executionArgvs(report: string): string[][] {
  return readReport(report)
    .filter((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state=")))
    .map((line) => [...line.argv]);
}

/** 预览一次并取回确认号（连同预览正文，供令牌不外泄比对）。 */
async function preview(svc: HubService, action: string, args: Record<string, unknown>): Promise<{ status: number; text: string; confirmation: string }> {
  const res = await svc.post("/api/v1/preview", { action, args });
  const text = res.body.toString("utf8");
  const data = (JSON.parse(text) as Record<string, unknown>)["data"] as Record<string, unknown> | null;
  return { status: res.status, text, confirmation: (data?.["confirmation"] as string) ?? "" };
}

let current: HubService | null = null;

afterEach(() => {
  current?.dispose();
  current = null;
});

describe("读路由 GET /api/v1/hub/roles（fake-kernel.mjs 演 config hub show --json）", () => {
  it("argv 恰为 config hub show --json、不带会话 401、白名单把越界值与凭据形状遮成 <redacted>", async () => {
    current = await startHubService(FAKE_KERNEL, { FAKE_KERNEL_JSON: HUB_POSTS_JSON }, {});
    const anon = await request(current.port, "GET", "/api/v1/hub/roles");
    expect(anon.status, "不带会话一律 401").toBe(401);
    const res = await current.get("/api/v1/hub/roles");
    expect(res.status).toBe(200);
    await waitForBegins(current.report, 1);
    const begin = readReport(current.report).filter((line) => line.event === "begin").at(-1);
    expect(begin?.argv, "读路由交出的 argv").toEqual(["config", "hub", "show", "--json"]);
    const posts = ((JSON.parse(res.body.toString("utf8")) as Record<string, unknown>)["data"] as Record<string, unknown>)["posts"] as Record<string, unknown>[];
    expect(posts).toHaveLength(6);
    // 合格的枚举、绑定名、ID 与 null 原样返回
    expect(posts[0]?.["post"]).toBe("coordinator");
    expect(posts[0]?.["adapter"]).toBe("quizs");
    expect(posts[0]?.["allowed_adapters"]).toEqual(["quizs", "pi"]);
    expect(posts[0]?.["profile"]).toBeNull(); // 缺省行 profile 恒为 null
    expect(posts[0]?.["runtime"]).toBeNull();
    expect((posts[0]?.["fallback"] as Record<string, unknown>)["provider"]).toBe("dsf");
    expect(posts[1]?.["provider"]).toBeNull(); // planner 缺省行 provider 是 null
    expect(posts[1]?.["fallback"]).toBeNull();
    expect(posts[2]?.["model"]).toBe("MiniMax-M3.1-Flash");
    expect(posts[2]?.["profile"]).toBe("demo-profile");
    // 约束不成立的值 → <redacted>：越界枚举、形状不合法/凭据形状的绑定名、越界 ID（这些默认脱敏不会遮，是白名单的面）
    expect(posts[3]?.["adapter"], "越界枚举应遮成 <redacted>").toBe("<redacted>");
    expect(posts[3]?.["model"], "带空格的绑定名应遮成 <redacted>").toBe("<redacted>");
    expect(posts[4]?.["provider"], "带空格的绑定名应遮成 <redacted>").toBe("<redacted>");
    expect(posts[4]?.["model"], "凭据形状的 model 应遮成 <redacted>").toBe("<redacted>");
    expect(posts[4]?.["profile"], "越界 ID 应遮成 <redacted>").toBe("<redacted>");
    expect((posts[5]?.["fallback"] as Record<string, unknown>)["model"], "fallback.model 约束").toBe("<redacted>");
    expect((posts[5]?.["fallback"] as Record<string, unknown>)["provider"], "合格的 fallback.provider 原样").toBe("dsf");
    expect(res.body.toString("utf8"), "凭据形状的值整个正文都不出现").not.toContain("sk-abcdefghijklmnopqrstuvwxyz012345");
  });
});

describe("写路由 hub.set / hub.unset（fake-write-kernel.mjs）", () => {
  it("参数不合格一律 400 且不起子进程（岗位/profile/fallback/未知键）", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {}, {});
    const cases: readonly { path: string; body: Record<string, unknown>; message: string }[] = [
      { path: "/api/v1/hub/roles/nope", body: { profile: "demo-profile" }, message: "post 不合法" },
      { path: "/api/v1/hub/roles/coordinator", body: { profile: "-x" }, message: "profile 不合法" },
      { path: "/api/v1/hub/roles/coordinator", body: { profile: "demo-profile", fallback: "-x" }, message: "fallback 不合法" },
      { path: "/api/v1/hub/roles/coordinator", body: { profile: "demo-profile", fallback: "Bad_Fallback" }, message: "fallback 不合法" },
      { path: "/api/v1/hub/roles/coordinator", body: { profile: "demo-profile", bogus: 1 }, message: "参数含有未知键" },
      { path: "/api/v1/hub/roles/nope/unset", body: {}, message: "post 不合法" },
      { path: "/api/v1/hub/roles/coordinator/unset", body: { bogus: 1 }, message: "参数含有未知键" },
    ];
    for (const item of cases) {
      const res = await current.post(item.path, item.body);
      expect(res.status, `${item.path} ${JSON.stringify(item.body)}`).toBe(400);
      expect(messagesOf(res)).toEqual([`ERROR: ${item.message}`]);
    }
    expect(readReport(current.report).filter((line) => line.event === "begin"), "参数不合格不起子进程").toEqual([]);
  });

  it("U6 三种 409：缺号 → 「确认号无效…」；换参数 → 「参数不符」；用第二次只执行一次", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {}, {});
    // 缺号：合格参数但不带 confirmation → 409，不起子进程
    const missing = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile" });
    expect(missing.status).toBe(409);
    expect(messagesOf(missing)).toEqual([`ERROR: ${CONFIRM_409}`]);
    // 换参数：预览 coordinator/demo-profile，执行时换 profile → 409「参数不符」，不消耗号、不起子进程
    const changed = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile" });
    expect(changed.status).toBe(200);
    const wrongArg = await current.post("/api/v1/hub/roles/coordinator", { profile: "other-profile", confirmation: changed.confirmation });
    expect(wrongArg.status).toBe(409);
    expect(messagesOf(wrongArg)).toEqual([`ERROR: ${ARGV_409}`]);
    expect(executionArgvs(current.report), "换参数不起子进程").toEqual([]);
    // 原参数能用（200）；用第二次 → 409，只执行一次
    const right = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile", confirmation: changed.confirmation });
    expect(right.status, "号仍可按原参数用").toBe(200);
    await waitForBegins(current.report, 1);
    const reused = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile", confirmation: changed.confirmation });
    expect(reused.status).toBe(409);
    expect(messagesOf(reused)).toEqual([`ERROR: ${CONFIRM_409}`]);
    expect(executionArgvs(current.report), "只执行一次").toHaveLength(1);
  });

  it("U6 过期：调短确认号 TTL、睡过 TTL 再执行 → 409「确认号无效…」，命令没有运行", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {}, { confirmationTtlMs: 50 });
    const p = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile" });
    expect(p.status).toBe(200);
    await sleep(300); // 睡过 50 毫秒的 TTL：确认号过期（不是等子进程起来的竞态）
    const res = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile", confirmation: p.confirmation });
    expect(res.status).toBe(409);
    expect(messagesOf(res)).toEqual([`ERROR: ${CONFIRM_409}`]);
    expect(executionArgvs(current.report), "过期不起子进程").toEqual([]);
  });

  it("hub.set 带 fallback 与 hub.unset 的执行 argv 逐项；路径参数压正文；--expect-state 与令牌不外泄", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {}, {});
    // hub.set 带 fallback：--fallback= 放最后、--expect-state=<state>、needs_yes 假无 --yes
    const set = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile", fallback: "demo-fallback" });
    const setRes = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile", fallback: "demo-fallback", confirmation: set.confirmation });
    expect(setRes.status).toBe(200);
    await waitForBegins(current.report, 1);
    const setArgv = executionArgvs(current.report)[0] ?? [];
    expect(setArgv.slice(0, setArgv.length - 1), "hub.set 基础 argv 逐项（--fallback= 放最后）").toEqual(["config", "hub", "set", "coordinator", "demo-profile", "--fallback=demo-fallback"]);
    expect(setArgv[setArgv.length - 1]?.startsWith("--expect-state="), "执行 argv 末项带 --expect-state=").toBe(true);
    expect(setArgv.some((part) => part === "--yes"), "needs_yes 假：无 --yes").toBe(false);
    // hub.unset：config hub unset <post>，不带 --post=
    const unset = await preview(current, "hub.unset", { post: "coordinator" });
    const unsetRes = await current.post("/api/v1/hub/roles/coordinator/unset", { confirmation: unset.confirmation });
    expect(unsetRes.status).toBe(200);
    await waitForBegins(current.report, 2);
    const unsetArgv = executionArgvs(current.report)[1] ?? [];
    expect(unsetArgv.slice(0, unsetArgv.length - 1)).toEqual(["config", "hub", "unset", "coordinator"]);
    // 令牌不外泄：替身报告执行那一支的 expect_state（整条令牌）在预览/执行/操作正文里都不出现
    const token = (readReport(current.report).find((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state="))) as unknown as { expect_state: string | null } | undefined)?.expect_state ?? "";
    expect(token).toMatch(/^v1;config=[0-9a-f]{64}$/u);
    const opRes = await current.get(`/api/v1/operations/${set.confirmation}`);
    expect(opRes.status).toBe(200);
    for (const [label, text] of [["预览", set.text], ["执行", setRes.body.toString("utf8")], ["操作", opRes.body.toString("utf8")]] as const) {
      expect(text, `${label}正文不该含整条令牌`).not.toContain(token);
      expect(text, `${label}正文不该含令牌段`).not.toContain(token.slice("v1;config=".length));
    }
    // 路径参数压过正文：正文给错 post 时仍按路径的 coordinator 执行（200，不是 409 参数不符）
    const path = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile" });
    const pathRes = await current.post("/api/v1/hub/roles/coordinator", { post: "gate", profile: "demo-profile", confirmation: path.confirmation });
    expect(pathRes.status, "路径参数压正文：正文的 post 被忽略，按 coordinator 执行").toBe(200);
    await waitForBegins(current.report, 3);
    const pathArgv = executionArgvs(current.report)[2] ?? [];
    expect(pathArgv.slice(0, pathArgv.length - 1), "执行用的是路径里的 coordinator，不是正文里的 gate").toEqual(["config", "hub", "set", "coordinator", "demo-profile"]);
  });

  it("needs_yes 为真时执行 argv 才带 --yes", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {
      FAKE_WRITE_PREVIEW: JSON.stringify({
        dry_run: true, action: "hub.set", changed: false, resources: [], binding_changes: [],
        running_attempts: [], unreadable: [], needs_yes: true, warnings: [], notes: [], state: STATE,
      }),
    }, {});
    const p = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile" });
    expect(p.status).toBe(200);
    const res = await current.post("/api/v1/hub/roles/coordinator", { profile: "demo-profile", confirmation: p.confirmation });
    expect(res.status).toBe(200);
    await waitForBegins(current.report, 1);
    expect(executionArgvs(current.report)[0]?.some((part) => part === "--yes"), "needs_yes 真：带 --yes").toBe(true);
  });

  it("预览的 action 与请求不同 → 500「内核的预览不合格」，不发确认号", async () => {
    current = await startHubService(FAKE_WRITE_KERNEL, {
      FAKE_WRITE_PREVIEW: JSON.stringify({
        dry_run: true, action: "role.set", changed: false, resources: [], binding_changes: [],
        running_attempts: [], unreadable: [], needs_yes: false, warnings: [], notes: [], state: STATE,
      }),
    }, {});
    const p = await preview(current, "hub.set", { post: "coordinator", profile: "demo-profile" });
    expect(p.status).toBe(500);
    expect((JSON.parse(p.text) as Record<string, unknown>)["messages"]).toEqual([`ERROR: ${PREVIEW_500}`]);
  });
});
