// 空闲超时修复（D6/M9–M11）：真 Bun 服务走生产 Bun.serve 选项（不传 bunIdleTimeoutSeconds 与 timeouts），由内核子进程应答的
// 三条并发请求（读路由、预览、写路由）都睡 15 秒——超过 Bun 缺省连接空闲超时（实测第 8 到 12 秒之间断开）。服务对命中
// readRoutes()/writeRoutes() 的请求调 server.timeout(req, 0) 放宽这一条连接，三条都拿到完整响应、替身三次调用都有 end 且退出 0。
// 「去掉修复」时这条用例必须红（替身睡 15 秒 > 空闲超时的断开点）。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type RunningService, header, request, startService, TS_ROOT } from "./harness.ts";
import { readReport } from "./support.ts";

const FAKE_WRITE_KERNEL = join(TS_ROOT, "packages", "ui", "test", "fixtures", "fake-write-kernel.mjs");
const SLEEP_MS = 15000; // > Bun 缺省空闲超时的断开点，留 3 秒余量
const ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"];

let dir = "";
let repo = "";
let assets = "";
let report = "";
let gate = "";
let service: RunningService | null = null;
let cookie = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-slow-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(repo, { recursive: true });
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>slow</title>\n");
  report = join(dir, "report.jsonl");
  gate = join(dir, "gate"); // 先预览时还不存在（不睡）；建好之后三条并发才睡
});

afterEach(() => {
  service?.kill();
  service = null;
  if (dir !== "") rmSync(dir, { recursive: true, force: true });
  dir = "";
});

describe("空闲超时：读路由/预览/写路由在生产 Bun.serve 选项下都拿到完整响应", () => {
  it("三条并发慢请求都 200、七字段信封；替身三次调用都有 end 且退出 0", async () => {
    service = await startService({
      repo,
      assets,
      python: process.execPath,
      kernel: FAKE_WRITE_KERNEL,
      entry: "overrides",
      overrides: {}, // 不传 bunIdleTimeoutSeconds 与 timeouts：走生产的 Bun.serve 选项
      env: { FAKE_KERNEL_REPORT: report, FAKE_WRITE_SLOW_GATE: gate, FAKE_WRITE_SLEEP_MS: String(SLEEP_MS) },
    });
    const port = service.port;
    const nonce = service.handshake.bootstrap.split("/").pop() ?? "";
    const booted = await request(port, "GET", `/bootstrap/${nonce}`);
    expect(booted.status).toBe(302);
    cookie = (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
    const csrf: [string, string][] = [["Cookie", cookie], ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]];

    // 先预览拿确认号（门文件还不存在，不睡）
    const previewed = await request(port, "POST", "/api/v1/preview", csrf, Buffer.from(JSON.stringify({ action: "role.set", args: { role: "execution", target: "manual" } })));
    expect(previewed.status).toBe(200);
    const confirmation = ((JSON.parse(previewed.body.toString("utf8")) as Record<string, unknown>)["data"] as Record<string, unknown>)["confirmation"] as string;

    writeFileSync(gate, "go"); // 建门文件：之后每次内核调用先睡 SLEEP_MS

    // 三条并发：读路由、预览、写路由（都睡 15 秒）
    const [readRes, previewRes, writeRes] = await Promise.all([
      request(port, "GET", "/api/v1/roles", [["Cookie", cookie]]),
      request(port, "POST", "/api/v1/preview", csrf, Buffer.from(JSON.stringify({ action: "role.set", args: { role: "execution", target: "manual" } }))),
      request(port, "POST", "/api/v1/roles/execution", csrf, Buffer.from(JSON.stringify({ target: "manual", confirmation }))),
    ]);

    for (const [label, res] of [["读路由", readRes], ["预览", previewRes], ["写路由", writeRes]] as const) {
      expect(res.status, `${label} 应拿到完整响应（状态 200）`).toBe(200);
      const body = JSON.parse(res.body.toString("utf8")) as Record<string, unknown>;
      expect(Object.keys(body), `${label} 的信封应含七个字段`).toEqual(ENVELOPE_KEYS);
    }

    // 替身报告：每次调用的 begin 都有对应的 end、退出码 0（没被空闲超时取消）
    const lines = readReport(report);
    const ends = new Map(lines.filter((line) => line.event === "end").map((line) => [line.pid, line]));
    const begins = lines.filter((line) => line.event === "begin");
    expect(begins.length, "应有四次内核调用（一次先预览 + 三条并发）").toBe(4);
    for (const begin of begins) {
      const end = ends.get(begin.pid);
      expect(end, `pid ${begin.pid} 应有 end（子进程没被取消）`).toBeDefined();
      expect((end as unknown as { exit: number | null }).exit, `pid ${begin.pid} 退出码应为 0`).toBe(0);
    }
  }, 90_000);
});
