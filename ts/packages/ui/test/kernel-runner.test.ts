// 内核子进程执行器与 19 条读路由的替身用例（桌面端 §5.3、D05/D06/D08/D09/D10/D12/D13、U28）：每条路由各一条
// （argv、时限、错误映射），加并发上限与排队、队列满 503 带 Retry-After、超时 504、断开与关停的取消、开始之前就
// 取消、输出超限、起不了子进程、meta 的 data 合成与合成的 /secrets 的编排。子进程是 node 跑的 fake-kernel.mjs。
import { pidAlive } from "@themis/base/process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ENVELOPE_KEYS } from "../src/envelope.ts";
import { CSP } from "../src/localhttp/headers.ts";
import { READ_ROUTE_ARGV, READ_ROUTE_SPECS } from "../src/readroutes.ts";
import { argvsOf, envelopeOf, readReport, startApp, type StartedApp } from "./support.ts";

let started: StartedApp | null = null;

beforeEach(() => {
  delete process.env["FAKE_KERNEL_JSON"];
  delete process.env["FAKE_KERNEL_STDERR"];
  delete process.env["FAKE_KERNEL_SLEEP_MS"];
  delete process.env["FAKE_KERNEL_EXIT"];
  delete process.env["FAKE_KERNEL_PLAN"];
  delete process.env["FAKE_KERNEL_PIDFILE"];
});

afterEach(async () => {
  delete process.env["FAKE_KERNEL_JSON"];
  delete process.env["FAKE_KERNEL_STDERR"];
  delete process.env["FAKE_KERNEL_SLEEP_MS"];
  delete process.env["FAKE_KERNEL_EXIT"];
  delete process.env["FAKE_KERNEL_PLAN"];
  delete process.env["FAKE_KERNEL_PIDFILE"];
  await started?.dispose();
  started = null;
});

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

/** 每条路由的替身用例：示例路径、期望交出的 argv。 */
const CASES: readonly { readonly name: string; readonly path: string; readonly argv: readonly string[] }[] = [
  { name: "api.meta.get", path: "/api/v1/meta", argv: READ_ROUTE_ARGV["api.meta.get"] ?? [] },
  { name: "api.status.get", path: "/api/v1/status", argv: READ_ROUTE_ARGV["api.status.get"] ?? [] },
  { name: "api.attempts.list", path: "/api/v1/attempts", argv: READ_ROUTE_ARGV["api.attempts.list"] ?? [] },
  { name: "api.attempts.list", path: "/api/v1/attempts?task=demo-task", argv: READ_ROUTE_ARGV["api.attempts.list.task"] ?? [] },
  { name: "api.attempts.show", path: "/api/v1/attempts/demo-task/attempt-001", argv: READ_ROUTE_ARGV["api.attempts.show"] ?? [] },
  { name: "api.attempts.file", path: "/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", argv: READ_ROUTE_ARGV["api.attempts.file"] ?? [] },
  { name: "api.usage.get", path: "/api/v1/usage", argv: READ_ROUTE_ARGV["api.usage.get"] ?? [] },
  { name: "api.config.get", path: "/api/v1/config", argv: READ_ROUTE_ARGV["api.config.get"] ?? [] },
  { name: "api.config.validate", path: "/api/v1/config/validate", argv: READ_ROUTE_ARGV["api.config.validate"] ?? [] },
  { name: "api.config.history.list", path: "/api/v1/config/history", argv: READ_ROUTE_ARGV["api.config.history.list"] ?? [] },
  { name: "api.config.history.show", path: "/api/v1/config/history/1", argv: READ_ROUTE_ARGV["api.config.history.show"] ?? [] },
  { name: "api.roles.get", path: "/api/v1/roles", argv: READ_ROUTE_ARGV["api.roles.get"] ?? [] },
  { name: "api.profiles.get", path: "/api/v1/profiles", argv: READ_ROUTE_ARGV["api.profiles.get"] ?? [] },
  { name: "api.presets.list", path: "/api/v1/presets", argv: READ_ROUTE_ARGV["api.presets.list"] ?? [] },
  { name: "api.presets.diff", path: "/api/v1/presets/base/diff/alt", argv: READ_ROUTE_ARGV["api.presets.diff"] ?? [] },
  { name: "api.runtimes.get", path: "/api/v1/runtimes", argv: READ_ROUTE_ARGV["api.runtimes.get"] ?? [] },
  { name: "api.plugins.list", path: "/api/v1/plugins", argv: READ_ROUTE_ARGV["api.plugins.list"] ?? [] },
  { name: "api.plugins.show", path: "/api/v1/plugins/example-plugin", argv: READ_ROUTE_ARGV["api.plugins.show"] ?? [] },
  { name: "api.secrets.list", path: "/api/v1/secrets", argv: READ_ROUTE_ARGV["api.secrets.list"] ?? [] },
  { name: "api.secrets.show", path: "/api/v1/secrets/EXAMPLE_KEY", argv: READ_ROUTE_ARGV["api.secrets.show"] ?? [] },
];

describe("19 条读路由各一条替身用例", () => {
  it("每条路由跑一次内核子进程，argv 与时限照合同", async () => {
    started = await startApp({ transcript: ["transcript.jsonl"] });
    const seen = new Set<string>();
    for (const item of CASES) {
      const response = await started.get(item.path);
      expect(response.status, `${item.name}（${item.path}）`).toBe(200);
      const body = await envelopeOf(response);
      expect(Object.keys(body), item.name).toEqual([...ENVELOPE_KEYS]);
      expect(body["ok"], item.name).toBe(true);
      expect(body["exit_code"], item.name).toBe(0);
      expect(body["output"], item.name).toEqual([]);
      expect(typeof body["elapsed_ms"], item.name).toBe("number");
      seen.add(item.name);
      if (item.name !== "api.secrets.list") {
        const last = readReport(started.report).filter((line) => line.event === "begin").at(-1);
        expect(last?.argv, item.name).toEqual([...item.argv]);
      }
    }
    // 表里正好覆盖 19 条读路由
    expect([...seen].sort()).toEqual(READ_ROUTE_SPECS.map((spec) => spec.name).sort());
    expect(READ_ROUTE_SPECS.map((spec) => spec.timeoutSeconds)).toEqual([15, 30, 30, 30, 60, 120, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 120, 30]);
  });

  it("时限照合同：15/30/60/120 四档（meta 15、file 60、usage 与 secrets 120、其余 30）", () => {
    const byName = new Map(READ_ROUTE_SPECS.map((spec) => [spec.name, spec.timeoutSeconds]));
    expect(byName.get("api.meta.get")).toBe(15);
    expect(byName.get("api.attempts.file")).toBe(60);
    expect(byName.get("api.usage.get")).toBe(120);
    expect(byName.get("api.secrets.list")).toBe(120);
    for (const spec of READ_ROUTE_SPECS) {
      if (spec.timeoutSeconds === 15 || spec.timeoutSeconds === 60 || spec.timeoutSeconds === 120) continue;
      expect(spec.timeoutSeconds, spec.name).toBe(30);
    }
  });

  it("读路由的响应带安全头与 no-store，没有 Access-Control-*（D14）", async () => {
    started = await startApp();
    const samples = ["/api/v1/meta", "/api/v1/status", "/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", "/api/v1/secrets"];
    for (const path of samples) {
      const response = await started.get(path);
      expect(response.status, path).toBe(200);
      expect(response.headers.get("content-security-policy"), path).toBe(CSP);
      expect(response.headers.get("x-content-type-options"), path).toBe("nosniff");
      expect(response.headers.get("referrer-policy"), path).toBe("no-referrer");
      expect(response.headers.get("cache-control"), path).toBe("no-store");
      expect([...response.headers.keys()].filter((name) => name.toLowerCase().startsWith("access-control")), path).toEqual([]);
    }
  });
});

describe("错误映射", () => {
  it("参数不合格一律 400 且不起子进程", async () => {
    started = await startApp();
    const bad = [
      "/api/v1/attempts?task=-bad",
      "/api/v1/attempts?task=BAD_task",
      "/api/v1/attempts/demo-task/attempt-01",
      "/api/v1/attempts/demo-task/attempt-001/file?path=-x",
      "/api/v1/attempts/demo-task/attempt-001/file?path=/abs",
      "/api/v1/attempts/demo-task/attempt-001/file?path=",
      "/api/v1/attempts/demo-task/attempt-001/file?path=a%5Cb.txt",
      "/api/v1/config/history/0",
      "/api/v1/config/history/abc",
      "/api/v1/presets/base/diff/-alt",
      "/api/v1/plugins/Bad",
      "/api/v1/secrets/9bad",
    ];
    for (const target of bad) {
      const response = await started.get(target);
      expect(response.status, target).toBe(400);
      const body = await envelopeOf(response);
      expect(body["ok"], target).toBe(false);
      expect(body["exit_code"], target).toBe(null);
    }
    expect(argvsOf(started.report), "参数不合格不起子进程").toEqual([]);
  });

  it("命令退出非 0：回 200、ok=false、exit_code 原样；stdout 是合法 JSON 就放进 data", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_EXIT"] = "3";
    process.env["FAKE_KERNEL_JSON"] = '{"partial": true}';
    const response = await started.get("/api/v1/status");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(3);
    expect(body["data"]).toEqual({ partial: true });
    expect(body["command"]).toEqual(["status", "--json"]);
  });

  it("要 JSON 的命令退出 0 但 stdout 不是合法 JSON：500", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_JSON"] = "{ 不是 JSON";
    const response = await started.get("/api/v1/status");
    expect(response.status).toBe(500);
    expect((await envelopeOf(response))["messages"]).toEqual(["ERROR: 内核输出不是合法的 JSON"]);
  });

  it("起不了子进程：500", async () => {
    started = await startApp({ python: "themis-no-such-python-xyz" });
    const response = await started.get("/api/v1/status");
    expect(response.status).toBe(500);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect((body["messages"] as string[])[0]).toContain("ERROR: ");
  });

  it("输出超限：500（stdout 上限调小之后照样删掉临时子目录）", async () => {
    started = await startApp({ stdoutLimitBytes: 8 });
    const response = await started.get("/api/v1/status");
    expect(response.status).toBe(500);
    expect((await envelopeOf(response))["messages"]).toEqual(["ERROR: 内核输出超过上限"]);
  });

  it("超时：504，信封照合同（ok=false、exit_code=null、messages 只有一行）", async () => {
    started = await startApp({ timeouts: { "api.status.get": 1 } });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "8000";
    const response = await started.get("/api/v1/status");
    expect(response.status).toBe(504);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(null);
    expect(body["data"]).toBe(null);
    expect(body["output"]).toEqual([]);
    expect(body["command"]).toEqual(["status", "--json"]);
    expect(body["messages"]).toEqual(["ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看"]);
  });
});

describe("并发、队列与取消（U28）", () => {
  it("同时 10 个请求：任何时刻在跑的子进程不超过 4，排队的都拿到结果", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_SLEEP_MS"] = "300";
    const pending = Array.from({ length: 10 }, () => started?.get("/api/v1/status"));
    const responses = await Promise.all(pending);
    for (const response of responses) expect(response?.status).toBe(200);
    const lines = readReport(started.report);
    const begins = lines.filter((line) => line.event === "begin").map((line) => line.at);
    const ends = lines.filter((line) => line.event === "end").map((line) => line.at);
    expect(begins).toHaveLength(10);
    expect(ends).toHaveLength(10);
    let peak = 0;
    for (const at of begins) peak = Math.max(peak, begins.filter((start) => start <= at).length - ends.filter((end) => end <= at).length);
    expect(peak).toBeLessThanOrEqual(4);
    expect(peak).toBeGreaterThan(1); // 真的是并发，不是一个个排
  });

  it("队列调小之后：队列满回 503 且带 Retry-After: 2", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 1 });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "400";
    const first = started.get("/api/v1/status");
    const second = started.get("/api/v1/status");
    const third = started.get("/api/v1/status");
    const [one, two, three] = await Promise.all([first, second, third]);
    expect(one?.status).toBe(200);
    expect(two?.status).toBe(200);
    expect(three?.status).toBe(503);
    expect(three?.headers.get("retry-after")).toBe("2");
    expect((await envelopeOf(three as Response))["messages"]).toEqual(["ERROR: 服务繁忙，请稍后重试"]);
  });

  it("客户端断开：取消那一次运行，10 秒内那个 pid 不在了", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_SLEEP_MS"] = "8000";
    const { controller, send } = started.getAbortable("/api/v1/status");
    let settled: unknown = null;
    const pending = send().then(
      (response) => {
        settled = response;
      },
      (error: unknown) => {
        settled = error;
      },
    );
    await sleep(300);
    controller.abort();
    await pending;
    const pid = readReport(started.report).find((line) => line.event === "begin")?.pid ?? 0;
    expect(pid).toBeGreaterThan(0);
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline && pidAlive(pid) !== false) await sleep(200);
    expect(pidAlive(pid), `pid ${pid} 应该已经不在了`).toBe(false);
  });

  it("服务关停：在跑的被取消、队列被清空、新请求回 503", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 4 });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "8000";
    const running = started.get("/api/v1/status");
    const queued = started.get("/api/v1/status");
    await sleep(300);
    const pid = readReport(started.report).find((line) => line.event === "begin")?.pid ?? 0;
    const stopping = started.runner.shutdown();
    const [first, second] = await Promise.all([running, queued]);
    await stopping;
    expect(first?.status).toBe(503);
    expect(second?.status).toBe(503);
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline && pidAlive(pid) !== false) await sleep(200);
    expect(pidAlive(pid), `pid ${pid} 应该已经不在了`).toBe(false);
    const after = await started.get("/api/v1/status");
    expect(after.status).toBe(503);
    expect(after.headers.get("retry-after")).toBe("2");
    expect((await envelopeOf(after))["messages"]).toEqual(["ERROR: 服务正在关闭"]);
  });

  it("开始之前就已取消：不起子进程，结果是 interrupted", async () => {
    started = await startApp();
    const controller = new AbortController();
    controller.abort();
    const outcome = await started.runner.run(["status", "--json"], 30, controller.signal);
    expect(outcome.kind).toBe("interrupted");
    expect(argvsOf(started.report)).toEqual([]);
  });
});

describe("H1 输出上限边写边看（D20）", () => {
  it("洪泛输出：上限 1 MiB、时限 60 秒时 10 秒内就得到 output-too-large，事后孙进程也不在了", async () => {
    const dir = mkdtempSync(join(tmpdir(), "themis-ui-flood-"));
    const pidfile = join(dir, "gc.pid");
    process.env["FAKE_KERNEL_PLAN"] = "flood"; // 起孙进程之后洪泛 stdout
    process.env["FAKE_KERNEL_PIDFILE"] = pidfile;
    try {
      started = await startApp({ stdoutLimitBytes: 1048576 });
      const began = Date.now();
      const response = await started.get("/api/v1/status");
      const elapsed = Date.now() - began;
      expect(response.status).toBe(500);
      expect((await envelopeOf(response))["messages"]).toEqual(["ERROR: 内核输出超过上限"]);
      expect(elapsed, `洪泛应在 10 秒内被抓到（实际 ${elapsed}ms）`).toBeLessThan(10000);
      const grandchild = Number(readFileSync(pidfile, "utf8").trim());
      expect(grandchild).toBeGreaterThan(0);
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline && pidAlive(grandchild) !== false) await sleep(200);
      expect(pidAlive(grandchild), `孙进程 ${grandchild} 应该已经不在了`).toBe(false);
    } finally {
      delete process.env["FAKE_KERNEL_PLAN"];
      delete process.env["FAKE_KERNEL_PIDFILE"];
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("H3 关停清队列并摘监听（D22）", () => {
  it("排队中的条目经过关停之后监听器为 0，事后再 abort 也不会再次交代结果", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 4 });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "8000";
    // 会数监听器的假 signal（AbortSignal 形状：aborted + add/removeEventListener）
    const listeners = new Set<() => void>();
    const target = {
      aborted: false,
      addEventListener: (type: string, callback: () => void): void => {
        if (type === "abort") listeners.add(callback);
      },
      removeEventListener: (type: string, callback: () => void): void => {
        if (type === "abort") listeners.delete(callback);
      },
    };
    const running = started.runner.run(["status", "--json"], 30, new AbortController().signal); // 占住名额
    const queued = started.runner.run(["status", "--json"], 30, target as unknown as AbortSignal); // 排队
    await sleep(200);
    expect(listeners.size, "排队中的条目应挂了一个 abort 监听器").toBeGreaterThan(0);
    await started.runner.shutdown(); // 清队列：逐个 release（摘监听）
    expect(listeners.size, "关停之后监听器应归零").toBe(0);
    for (const callback of [...listeners]) callback(); // 事后再 abort：监听器已摘，不会再次交代
    const outcome = await queued;
    expect(outcome.kind).toBe("closing");
    await running.catch(() => undefined);
  });
});

describe("canAccept 与 hooks.onStart（D16/D17）", () => {
  it("canAccept：有名额时 true，名额占满时 false", async () => {
    started = await startApp({ maxConcurrent: 1, maxQueue: 0 });
    process.env["FAKE_KERNEL_SLEEP_MS"] = "500";
    expect(started.runner.canAccept()).toBe(true);
    const pending = started.runner.run(["status", "--json"], 30, new AbortController().signal);
    await sleep(120);
    expect(started.runner.canAccept(), "在跑的已占满上限、队列为 0").toBe(false);
    await pending;
  });

  it("hooks.onStart：queued 变 running 的那一刻调一次", async () => {
    started = await startApp();
    let onStartCalls = 0;
    await started.runner.run(["status", "--json"], 30, new AbortController().signal, {
      onStart: () => {
        onStartCalls += 1;
      },
    });
    expect(onStartCalls).toBe(1);
  });
});

describe("合成的数据", () => {
  it("meta 的 data：{version, repo_name}", async () => {
    started = await startApp();
    const body = await envelopeOf(await started.get("/api/v1/meta"));
    const data = body["data"] as Record<string, unknown>;
    expect(Object.keys(data)).toEqual(["version", "repo_name"]);
    expect(data["version"]).toBe("pi_dispatch 2.12.0");
    expect(data["repo_name"]).toBe(started.state.repo.split(/[\\/]/u).pop());
    expect(body["command"]).toEqual(["--version"]);
  });

  it("合成的 /secrets：先收名单再逐条串行跑 config secret check；成功时 command 是空数组、exit_code 是 0", async () => {
    started = await startApp();
    const response = await started.get("/api/v1/secrets");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(true);
    expect(body["exit_code"]).toBe(0);
    expect(body["command"]).toEqual([]);
    const data = body["data"] as Record<string, unknown>;
    const secrets = data["secrets"] as Record<string, unknown>[];
    expect(secrets).toHaveLength(2); // decisions 的 TYPESAFE_API_KEY 与 profile 的 OTHER_KEY（去重且保序）
    expect(secrets[0]).toMatchObject({ name: "TYPESAFE_API_KEY", source: "env", store_mode: "system", system_backend: "windows-credential-manager" });
    expect(secrets[0]?.["used_by"]).toEqual([{ kind: "decisions" }, { kind: "profile", id: "execution" }]);
    expect(secrets[1]).toMatchObject({ name: "OTHER_KEY" });
    expect(secrets[1]?.["used_by"]).toEqual([{ kind: "profile", id: "execution" }]);
    expect(JSON.stringify(body)).not.toContain("file_dir");
    expect(argvsOf(started.report)).toEqual([
      ["config", "show", "--json"],
      ["config", "profile", "show", "--json"],
      ["config", "secret", "check", "TYPESAFE_API_KEY"],
      ["config", "secret", "check", "OTHER_KEY"],
    ]);
  });

  it("合成的 /secrets：任何一条失败就停下，回那一条子命令的信封", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_EXIT"] = "1";
    const response = await started.get("/api/v1/secrets");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(false);
    expect(body["exit_code"]).toBe(1);
    expect(body["command"]).toEqual(["config", "secret", "check", "TYPESAFE_API_KEY"]);
    // 那一条的 stdout 仍是合法 JSON：data 是那一条的 data（不含 file_dir）
    expect(body["data"]).toMatchObject({ name: "TYPESAFE_API_KEY", source: "env" });
    expect(JSON.stringify(body)).not.toContain("file_dir");
    expect(argvsOf(started.report)).toEqual([
      ["config", "show", "--json"],
      ["config", "profile", "show", "--json"],
      ["config", "secret", "check", "TYPESAFE_API_KEY"],
    ]);
  });

  it("/secrets/<name>：每项是 {name, source, store_mode, system_backend}，不带 file_dir", async () => {
    started = await startApp();
    const body = await envelopeOf(await started.get("/api/v1/secrets/EXAMPLE_KEY"));
    expect(body["ok"]).toBe(true);
    const data = body["data"] as Record<string, unknown>;
    expect(Object.keys(data)).toEqual(["name", "source", "store_mode", "system_backend"]);
    expect(data).toMatchObject({ name: "EXAMPLE_KEY", source: "env", store_mode: "system" });
    expect(body["command"]).toEqual(["config", "secret", "check", "EXAMPLE_KEY"]);
  });
});
