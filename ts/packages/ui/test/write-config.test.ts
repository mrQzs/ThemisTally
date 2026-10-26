// T020 的替身用例：五条新写路由（profile add|edit|remove、runtime add|remove）与 credential_env 的三种写法、command 的 JSON
// 序列化、预览正文的顶层键，以及「令牌不外泄」的 12 行 × 4 查法。进程内建 app（照 write-routes.test.ts 的写法），内核子进程
// 走替身 fake-write-kernel.mjs；替身对每个 action 给一份确定性预览（state 每行不同），执行那一支把 --expect-state 记进报告。
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { KernelRunner } from "../src/kernel.ts";
import { buildWriteArgv, writeRoutes } from "../src/writeroutes.ts";
import { ConfirmationTable } from "../src/confirmations.ts";
import { OperationTable } from "../src/operations.ts";
import { argvsOf, readReport } from "./support.ts";
import { TS_ROOT } from "./harness.ts";

const FAKE_WRITE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-write-kernel.mjs");
const FAKE_VARS = ["FAKE_WRITE_PREVIEW", "FAKE_WRITE_PLAN", "FAKE_WRITE_GATE", "FAKE_WRITE_BEGIN", "FAKE_KERNEL_EXIT", "FAKE_WRITE_SLOW_GATE", "FAKE_WRITE_SLEEP_MS"];

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

interface WriteApp {
  readonly app: App;
  readonly runner: KernelRunner;
  readonly confirmations: ConfirmationTable;
  readonly operations: OperationTable;
  readonly report: string;
  get(target: string): Promise<Response>;
  post(target: string, body: unknown): Promise<Response>;
  dispose(): Promise<void>;
}

async function startApp(): Promise<WriteApp> {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-write-config-"));
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_REPORT"] = report;
  const runner = new KernelRunner({ repo: TS_ROOT, python: process.execPath, kernel: FAKE_WRITE_KERNEL });
  const confirmations = new ConfirmationTable();
  const operations = new OperationTable();
  const app = createApp({ port: 1, assets: dir, controlToken: "t".repeat(43), extraRoutes: writeRoutes({ runner, confirmations, operations }) });
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  const cookie = booted.headers.get("set-cookie")?.split(";")[0] ?? "";
  const withCookie = { host: "127.0.0.1:1", cookie };
  return {
    app,
    runner,
    confirmations,
    operations,
    report,
    get: (target) => app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie } })),
    post: (target, body) =>
      app.fetch(
        new Request(`http://127.0.0.1:1${target}`, {
          method: "POST",
          headers: { ...withCookie, origin: "http://127.0.0.1:1", "x-themis-ui": "1", "content-type": "application/json" },
          body: JSON.stringify(body),
        }),
      ),
    dispose: async () => {
      delete process.env["FAKE_KERNEL_REPORT"];
      await runner.shutdown();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}

/** 执行那一支的 argv（begin 行里有 --expect-state= 的，去重保持次序）。 */
function executionArgvs(report: string): string[][] {
  return readReport(report)
    .filter((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state=")))
    .map((line) => [...line.argv]);
}

/** 预览一次并取回确认号。 */
async function previewConfirmation(app: WriteApp, action: string, args: Record<string, unknown>): Promise<string> {
  const res = await app.post("/api/v1/preview", { action, args });
  expect(res.status, `${action} 预览应 200`).toBe(200);
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

const messagesOf = async (res: Response): Promise<unknown> => ((await res.json()) as Record<string, unknown>)["messages"];

/** 五条新路由的预览参数、执行路径与正文（路径参数压正文同名键，照 mergeArgs）。 */
const NEW_ROWS: readonly { action: string; args: Record<string, unknown>; path: string; body: Record<string, unknown> }[] = [
  { action: "profile.add", args: { profile: "demo-profile", runtime: "demo-runtime", model: "demo-provider/demo-model" }, path: "/api/v1/profiles/demo-profile/add", body: { runtime: "demo-runtime", model: "demo-provider/demo-model" } },
  { action: "profile.edit", args: { profile: "demo-profile", model: "demo-provider/demo-model" }, path: "/api/v1/profiles/demo-profile/edit", body: { model: "demo-provider/demo-model" } },
  { action: "profile.remove", args: { profile: "demo-profile" }, path: "/api/v1/profiles/demo-profile/remove", body: {} },
  { action: "runtime.add", args: { runtime: "demo-runtime", adapter: "pi", command: ["C:/tools/pi.exe", "--flag"] }, path: "/api/v1/runtimes/demo-runtime/add", body: { adapter: "pi", command: ["C:/tools/pi.exe", "--flag"] } },
  { action: "runtime.remove", args: { runtime: "demo-runtime" }, path: "/api/v1/runtimes/demo-runtime/remove", body: {} },
];

let started: WriteApp | null = null;

beforeEach(() => {
  for (const name of FAKE_VARS) delete process.env[name];
});

afterEach(async () => {
  for (const name of FAKE_VARS) delete process.env[name];
  await started?.dispose();
  started = null;
});

describe("五条新路由：预览 → 执行 → 操作记录", () => {
  for (const row of NEW_ROWS) {
    it(`${row.action}：能预览、带确认号执行、操作记 succeeded`, async () => {
      started = await startApp();
      const confirmation = await previewConfirmation(started, row.action, row.args);
      expect(confirmation).toMatch(/^[A-Za-z0-9_-]{43}$/u);
      const res = await started.post(row.path, { ...row.body, confirmation });
      expect(res.status, `${row.action} 执行应 200`).toBe(200);
      const op = await waitForOperation(started, confirmation, ["succeeded"]);
      expect(op["action"]).toBe(row.action);
      expect(op["state"]).toBe("succeeded");
    });
  }
});

describe("credential_env 的三种写法与空数组", () => {
  it("缺省：argv 不带 --credential-env", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started, "profile.add", { profile: "demo-profile", runtime: "demo-runtime", model: "a/b" });
    await started.post("/api/v1/profiles/demo-profile/add", { runtime: "demo-runtime", model: "a/b", confirmation });
    const argv = executionArgvs(started.report)[0] ?? [];
    expect(argv.some((part) => part.startsWith("--credential-env=")), "缺省不该有 --credential-env").toBe(false);
  });

  it("非空数组：每项一个 --credential-env=<名>，保持请求次序", async () => {
    started = await startApp();
    const confirmation = await previewConfirmation(started, "profile.add", { profile: "demo-profile", runtime: "demo-runtime", model: "a/b", credential_env: ["DEMO_API_KEY", "OTHER_KEY"] });
    await started.post("/api/v1/profiles/demo-profile/add", { runtime: "demo-runtime", model: "a/b", credential_env: ["DEMO_API_KEY", "OTHER_KEY"], confirmation });
    const argv = executionArgvs(started.report)[0] ?? [];
    expect(argv).toContain("--credential-env=DEMO_API_KEY");
    expect(argv).toContain("--credential-env=OTHER_KEY");
    expect(argv.indexOf("--credential-env=DEMO_API_KEY")).toBeLessThan(argv.indexOf("--credential-env=OTHER_KEY"));
  });

  it("空数组 → 400「credential_env 不合法」，不起子进程", async () => {
    started = await startApp();
    const res = await started.post("/api/v1/preview", { action: "profile.add", args: { profile: "demo-profile", runtime: "demo-runtime", model: "a/b", credential_env: [] } });
    expect(res.status).toBe(400);
    expect(await messagesOf(res)).toEqual(["ERROR: credential_env 不合法"]);
    expect(argvsOf(started.report), "空数组不起子进程").toEqual([]);
  });

  it("令牌形状的 credential_env → 400「credential_env 不合法」，不起子进程", async () => {
    started = await startApp();
    const res = await started.post("/api/v1/preview", { action: "profile.add", args: { profile: "demo-profile", runtime: "demo-runtime", model: "a/b", credential_env: ["apikey_0123456789abcdefghijklmnopqrst"] } });
    expect(res.status).toBe(400);
    expect(await messagesOf(res)).toEqual(["ERROR: credential_env 不合法"]);
    expect(argvsOf(started.report), "令牌形状不起子进程").toEqual([]);
  });
});

describe("command 的 JSON 序列化", () => {
  it("argv 恰为 --command= 加 JSON.stringify(command)，JSON.parse 逐项相等（含空格、反斜杠、以 - 开头的项）", async () => {
    started = await startApp();
    const command = ["C:/a b/pi.exe", "--flag", "-x"];
    const confirmation = await previewConfirmation(started, "runtime.add", { runtime: "demo-runtime", adapter: "pi", command });
    await started.post("/api/v1/runtimes/demo-runtime/add", { adapter: "pi", command, confirmation });
    const argv = executionArgvs(started.report)[0] ?? [];
    const element = argv.find((part) => part.startsWith("--command="));
    expect(element, "argv 里应有 --command=").toBe(`--command=${JSON.stringify(command)}`);
    expect(JSON.parse((element ?? "").slice("--command=".length))).toEqual(command);
  });
});

describe("预览正文的顶层键", () => {
  it("多出顶层键 → 400「参数含有未知键」，不起子进程", async () => {
    started = await startApp();
    const res = await started.post("/api/v1/preview", { action: "role.set", args: { role: "execution", target: "manual" }, extra: 1 });
    expect(res.status).toBe(400);
    expect(await messagesOf(res)).toEqual(["ERROR: 参数含有未知键"]);
    expect(argvsOf(started.report), "多出顶层键不起子进程").toEqual([]);
  });

  it("缺 action / 缺 args 的两条提示原样保留", async () => {
    started = await startApp();
    const noArgs = await started.post("/api/v1/preview", { action: "role.set" });
    expect(await messagesOf(noArgs)).toEqual(["ERROR: 请求体必须是 JSON 对象"]);
    const noAction = await started.post("/api/v1/preview", { args: { role: "execution", target: "manual" } });
    expect(await messagesOf(noAction)).toEqual(["ERROR: action 不合法"]);
  });
});

describe("令牌不外泄：12 行 × 4 查法", () => {
  /** 十二条命令的预览参数、执行路径与正文；runtime.add 带 --command、runtime.remove 给 config+local 两段。 */
  const ROWS: readonly { action: string; args: Record<string, unknown>; path: string; body: Record<string, unknown> }[] = [
    { action: "role.set", args: { role: "execution", target: "manual" }, path: "/api/v1/roles/execution", body: { target: "manual" } },
    { action: "preset.use", args: { name: "demo-preset" }, path: "/api/v1/presets/demo-preset/use", body: {} },
    { action: "preset.save", args: { name: "demo-preset" }, path: "/api/v1/presets/demo-preset/save", body: {} },
    { action: "preset.remove", args: { name: "demo-preset" }, path: "/api/v1/presets/demo-preset/remove", body: {} },
    { action: "config.rollback", args: { number: 1 }, path: "/api/v1/config/rollback/1", body: {} },
    { action: "plugin.enable", args: { id: "example-plugin" }, path: "/api/v1/plugins/example-plugin/enable", body: {} },
    { action: "plugin.disable", args: { id: "example-plugin" }, path: "/api/v1/plugins/example-plugin/disable", body: {} },
    { action: "profile.add", args: { profile: "demo-profile", runtime: "demo-runtime", model: "demo-provider/demo-model" }, path: "/api/v1/profiles/demo-profile/add", body: { runtime: "demo-runtime", model: "demo-provider/demo-model" } },
    { action: "profile.edit", args: { profile: "demo-profile", model: "demo-provider/demo-model" }, path: "/api/v1/profiles/demo-profile/edit", body: { model: "demo-provider/demo-model" } },
    { action: "profile.remove", args: { profile: "demo-profile" }, path: "/api/v1/profiles/demo-profile/remove", body: {} },
    { action: "runtime.add", args: { runtime: "demo-runtime", adapter: "pi", command: ["C:/tools/pi.exe", "--flag"] }, path: "/api/v1/runtimes/demo-runtime/add", body: { adapter: "pi", command: ["C:/tools/pi.exe", "--flag"] } },
    { action: "runtime.remove", args: { runtime: "demo-runtime" }, path: "/api/v1/runtimes/demo-runtime/remove", body: {} },
  ];

  it("每行的预览/执行/操作正文都不出现令牌段，替身的 expect_state 与整条令牌逐字相同", async () => {
    started = await startApp();
    const tokens: string[] = [];
    const segments: string[] = [];
    for (const row of ROWS) {
      const previewRes = await started.post("/api/v1/preview", { action: row.action, args: row.args });
      expect(previewRes.status, `${row.action} 预览应 200`).toBe(200);
      const previewText = await previewRes.text();
      const confirmation = ((JSON.parse(previewText) as Record<string, unknown>)["data"] as Record<string, unknown>)["confirmation"] as string;
      // 整条令牌：服务在确认号记录里存下的 preview state（执行之前读，执行后已被消费）
      const token = started.confirmations.get(confirmation)?.state ?? "";
      expect(token, `${row.action} 应拿到 state 令牌`).toMatch(/^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$/u);
      tokens.push(token);
      segments.push(...(token.match(/[0-9a-f]{64}/gu) ?? []));

      const execRes = await started.post(row.path, { ...row.body, confirmation });
      expect(execRes.status, `${row.action} 执行应 200`).toBe(200);
      const execText = await execRes.text();
      const opRes = await started.get(`/api/v1/operations/${confirmation}`);
      expect(opRes.status).toBe(200);
      const opText = await opRes.text();

      // 查 1/2/3：三份正文里令牌的每一段与整条令牌都不出现
      for (const [label, text] of [["预览", previewText], ["执行", execText], ["操作", opText]] as const) {
        expect(text, `${row.action} ${label}正文不该含整条令牌`).not.toContain(token);
        for (const segment of token.match(/[0-9a-f]{64}/gu) ?? []) {
          expect(text, `${row.action} ${label}正文不该含令牌段 ${segment.slice(0, 8)}…`).not.toContain(segment);
        }
      }
    }
    // 查 4：替身报告里执行那一支的 expect_state 与整条令牌逐字相同（杀「只带 config」）
    const expectStates = readReport(started.report)
      .filter((line) => line.event === "begin" && line.argv.some((part) => part.startsWith("--expect-state=")))
      .map((line) => (line as unknown as { expect_state: string | null }).expect_state);
    expect(expectStates).toEqual(tokens);
    // 12 行的令牌两两不同、令牌段也两两不同（否则「搜不到」没有意义）
    expect(new Set(tokens).size).toBe(ROWS.length);
    expect(new Set(segments).size).toBe(segments.length);
  });

  it("buildWriteArgv 与预览 argv 一致：执行 argv 以基础 argv 开头（路径参数压正文）", async () => {
    started = await startApp();
    for (const row of NEW_ROWS) {
      const base = buildWriteArgv(row.action, row.args);
      const confirmation = await previewConfirmation(started, row.action, row.args);
      await started.post(row.path, { ...row.body, confirmation });
      const argv = executionArgvs(started.report).find((item) => item.slice(0, base.length).every((part, index) => part === base[index]) && item.length > base.length);
      expect(argv, `${row.action} 应有执行 argv`).toBeDefined();
    }
  });
});
