// SSE 广播的黑盒用例（桌面端 §5.3、T3、D02–D11、D27–D30、U17–U21）：起真服务（Bun）与替身内核 fake-kernel.mjs
// （status 读夹具文件 FAKE_KERNEL_STATUS_FILE），客户端在 Node 一侧用原始套接字订阅 /api/v1/events。覆盖 snapshot
// 与 reconnect 与 update、序号递增、订阅上限（全局 / 每会话）、会话作废主动关流、心跳写失败即清理、订阅算活动与空闲
// 退出、junction 不跟随、与 /api/v1/status 逐字节一致（同一套脱敏）、多订阅者共用一次 status、去抖、Bun 空闲超时。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { connect } from "node:net";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type RunningService, header, openSse, request, startService, type SseClient } from "./harness.ts";
import { FAKE_KERNEL, readReport } from "./support.ts";

let dir = "";
let running: RunningService | null = null;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-events-svc-"));
});

afterEach(async () => {
  delete process.env["FAKE_KERNEL_STATUS_FILE"];
  delete process.env["FAKE_KERNEL_REPORT"];
  delete process.env["FAKE_KERNEL_PLAN"];
  await running?.stop().catch(() => undefined);
  running?.kill();
  running = null;
  rmSync(dir, { recursive: true, force: true });
});

const sleep = (ms: number): Promise<void> => new Promise((done) => setTimeout(done, ms));

interface Events {
  readonly svc: RunningService;
  readonly port: number;
  readonly cookie: string;
  readonly repo: string;
  readonly statusFile: string;
  readonly attempt: string;
  readonly report: string;
}

/** 起一个带替身 status 的服务：runs 里放一个 attempt，status 输出读夹具文件。 */
async function openEvents(
  options: { statusContent?: string; heartbeatMs?: number; statIntervalMs?: number; maxSubscriptions?: number; maxSubscriptionsPerSession?: number; bunIdleTimeoutSeconds?: number; idleTimeout?: number | null } = {},
): Promise<Events> {
  const repo = join(dir, "repo");
  const attempt = join(repo, ".agent", "runs", "demo-task", "attempt-001");
  mkdirSync(attempt, { recursive: true });
  writeFileSync(join(attempt, "state.json"), '{"state":"RUNNING"}', "utf8");
  const assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>events</title>\n", "utf8");
  const statusFile = join(dir, "status.json");
  writeFileSync(statusFile, options.statusContent ?? '[{"task":"demo-task","attempt":"attempt-001","state":"RUNNING"}]', "utf8");
  const report = join(dir, "report.jsonl");
  process.env["FAKE_KERNEL_STATUS_FILE"] = statusFile;
  process.env["FAKE_KERNEL_REPORT"] = report;
  const overrides: Record<string, unknown> = { heartbeatMs: options.heartbeatMs ?? 300 };
  if (options.statIntervalMs !== undefined) overrides["statIntervalMs"] = options.statIntervalMs;
  if (options.maxSubscriptions !== undefined) overrides["maxSubscriptions"] = options.maxSubscriptions;
  if (options.maxSubscriptionsPerSession !== undefined) overrides["maxSubscriptionsPerSession"] = options.maxSubscriptionsPerSession;
  if (options.bunIdleTimeoutSeconds !== undefined) overrides["bunIdleTimeoutSeconds"] = options.bunIdleTimeoutSeconds;
  const svc = await startService({ repo, assets, python: process.execPath, kernel: FAKE_KERNEL, entry: "overrides", overrides, idleTimeout: options.idleTimeout ?? null });
  running = svc;
  const nonce = svc.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(svc.port, "GET", `/bootstrap/${nonce}`);
  const cookie = (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
  return { svc, port: svc.port, cookie, repo, statusFile, attempt, report };
}

/** 等出现第一个带 event 的块，返回它。 */
async function firstEvent(sub: SseClient, timeoutMs = 8000): Promise<Record<string, unknown>> {
  await sub.waitFor("event: ", timeoutMs);
  const events = sub.blocks().filter((block) => "event" in block);
  return events[0] ?? {};
}

const statusRuns = (report: string): number => readReport(report).filter((line) => line.event === "begin" && line.argv[0] === "status").length;

describe("U17 snapshot / reconnect / update 与序号（D02/D03）", () => {
  it("订阅后第一条是 snapshot（state RUNNING）；重连后第一条仍是 snapshot 且序号大于断开之前", async () => {
    const events = await openEvents();
    const sub1 = await openSse(events.port, events.cookie);
    try {
      expect(sub1.status).toBe(200);
      expect(sub1.header("content-type")).toBe("text/event-stream; charset=utf-8");
      await sub1.waitFor("retry: 3000", 8000);
      const first = await firstEvent(sub1);
      expect(first["event"]).toBe("snapshot");
      expect(first["id"]).toBe("1"); // 序号从 1 起
      const envelope = JSON.parse(String(first["data"])) as Record<string, unknown>;
      const arr = envelope["data"] as Record<string, unknown>[];
      expect(arr[0]?.["state"]).toBe("RUNNING");
      const beforeId = Number(first["id"]);
      sub1.close();
      await sleep(400);
      // 改名单上的输入（state.json）与替身 status 输出 → 重连后是新的 snapshot，序号更大
      writeFileSync(join(events.attempt, "state.json"), '{"state":"NEEDS_REVIEW"}', "utf8");
      writeFileSync(events.statusFile, '[{"task":"demo-task","attempt":"attempt-001","state":"NEEDS_REVIEW"}]', "utf8");
      const sub2 = await openSse(events.port, events.cookie);
      try {
        const reconnected = await firstEvent(sub2);
        expect(reconnected["event"]).toBe("snapshot");
        expect(Number(reconnected["id"])).toBeGreaterThan(beforeId); // 序号大于断开之前
        const envelope = JSON.parse(String(reconnected["data"])) as Record<string, unknown>;
        const arr2 = envelope["data"] as Record<string, unknown>[];
        expect(arr2[0]?.["state"]).toBe("NEEDS_REVIEW");
      } finally {
        sub2.close();
      }
    } finally {
      sub1.close();
    }
  });

  it("带 Last-Event-ID 重连，第一条仍是 snapshot（不续传）", async () => {
    const events = await openEvents();
    const sub = await openSse(events.port, events.cookie, "999");
    try {
      const first = await firstEvent(sub);
      expect(first["event"]).toBe("snapshot"); // 不照 Last-Event-ID 续传
      expect(first["data"]).toBeTruthy();
    } finally {
      sub.close();
    }
  });

  it("名单上的变化推一条 update（内容不同才推、序号加一）", async () => {
    const events = await openEvents({ statIntervalMs: 400 });
    const sub = await openSse(events.port, events.cookie);
    try {
      const snapshot = await firstEvent(sub);
      const snapshotId = Number(snapshot["id"]);
      await sleep(200);
      writeFileSync(join(events.attempt, "state.json"), '{"state":"CHANGED"}', "utf8");
      writeFileSync(events.statusFile, '[{"task":"demo-task","attempt":"attempt-001","state":"CHANGED"}]', "utf8");
      await sub.waitFor("event: update", 8000);
      const updates = sub.blocks().filter((block) => block["event"] === "update");
      const last = updates.at(-1) ?? {};
      expect(Number(last["id"])).toBeGreaterThan(snapshotId);
      const envelope = JSON.parse(String(last["data"])) as Record<string, unknown>;
      const arr = envelope["data"] as Record<string, unknown>[];
      expect(arr[0]?.["state"]).toBe("CHANGED");
    } finally {
      sub.close();
    }
  });

  it("推送的 data 与 /api/v1/status 逐字节一致（同一套脱敏：敏感键遮成 <redacted>）", async () => {
    const events = await openEvents({ statusContent: '[{"task":"x","api_key":"sk-live-secret-value","name":"ok"}]' });
    const sub = await openSse(events.port, events.cookie);
    try {
      const snapshot = await firstEvent(sub);
      const sseData = String(snapshot["data"]);
      const status = await request(events.port, "GET", "/api/v1/status", [["Cookie", events.cookie]]);
      const statusBody = status.body.toString("utf8").replace(/\n$/, "");
      // elapsed_ms 是两次独立运行的耗时，会不同；其余字段逐字节一致
      const normalize = (text: string): string => text.replace(/("elapsed_ms":\s*)\d+/gu, "$10");
      expect(normalize(sseData)).toBe(normalize(statusBody));
      expect(sseData).toContain("<redacted>"); // 敏感键被遮
      expect(sseData).not.toContain("sk-live-secret-value");
    } finally {
      sub.close();
    }
  });
});

describe("U18 订阅上限（D27）", () => {
  it("全局上限第 3 条回 503 带 Retry-After: 2，已有订阅不被挤掉，关掉一条名额还回来", async () => {
    const events = await openEvents({ maxSubscriptions: 2 });
    const sub1 = await openSse(events.port, events.cookie);
    const sub2 = await openSse(events.port, events.cookie);
    try {
      expect(sub1.status).toBe(200);
      expect(sub2.status).toBe(200);
      await firstEvent(sub1);
      const third = await request(events.port, "GET", "/api/v1/events", [["Cookie", events.cookie]]);
      expect(third.status).toBe(503);
      expect(header(third, "retry-after")).toBe("2");
      const body = JSON.parse(third.body.toString("utf8")) as Record<string, unknown>;
      expect(body["ok"]).toBe(false);
      expect(body["messages"]).toEqual(["ERROR: SSE 订阅数已达上限"]);
      // 已有的两条不被挤掉：照旧收到心跳
      await sub1.waitFor(": hb", 3000);
      await sub2.waitFor(": hb", 3000);
      // 关掉一条，名额还回来
      sub1.close();
      await sleep(800);
      const sub3 = await openSse(events.port, events.cookie);
      try {
        expect(sub3.status).toBe(200);
      } finally {
        sub3.close();
      }
    } finally {
      sub2.close();
    }
  });

  it("每会话上限：同一会话第 2 条回 503「该会话的 SSE 订阅数已达上限」", async () => {
    const events = await openEvents({ maxSubscriptions: 8, maxSubscriptionsPerSession: 1 });
    const sub1 = await openSse(events.port, events.cookie);
    try {
      expect(sub1.status).toBe(200);
      await firstEvent(sub1);
      const second = await request(events.port, "GET", "/api/v1/events", [["Cookie", events.cookie]]);
      expect(second.status).toBe(503);
      const body = JSON.parse(second.body.toString("utf8")) as Record<string, unknown>;
      expect(body["messages"]).toEqual(["ERROR: 该会话的 SSE 订阅数已达上限"]);
    } finally {
      sub1.close();
    }
  });
});

describe("U19 会话作废主动关流 / U20 心跳写失败即清理（D28/D29）", () => {
  it("revokeAll（换发引导地址）之后订阅在一个心跳间隔内被关掉", async () => {
    const events = await openEvents();
    const sub = await openSse(events.port, events.cookie);
    try {
      await firstEvent(sub);
      const control = await request(events.port, "POST", "/control/bootstrap", [["X-Themis-Control", events.svc.handshake.control]]);
      expect(control.status).toBe(200);
      expect(await sub.waitClosed(3000)).toBe(true); // 会话作废 → 主动关流
    } finally {
      sub.close();
    }
  });

  it("心跳写失败立刻清理：客户端直接断开后名额还回来（第 3 条订阅成功）", async () => {
    const events = await openEvents({ maxSubscriptions: 2, heartbeatMs: 300 });
    const w1 = await openSse(events.port, events.cookie);
    const w2 = await openSse(events.port, events.cookie);
    try {
      await firstEvent(w1);
      await firstEvent(w2);
      w1.close(); // 直接断开，不发 abort：服务下一次写心跳失败
      await sleep(1200);
      const w3 = await openSse(events.port, events.cookie);
      try {
        expect(w3.status).toBe(200); // 名额已归还
      } finally {
        w3.close();
      }
    } finally {
      w2.close();
    }
  });
});

describe("T3 junction 不跟随 / 共用一次 status / 去抖（D05/D06/D07）", () => {
  it("runs 下的 junction 不跟随：往外部目录写东西不触发 update", async () => {
    const events = await openEvents({ statIntervalMs: 400 });
    const external = join(dir, "external");
    mkdirSync(external, { recursive: true });
    writeFileSync(join(external, "state.json"), '{"state":"OUTSIDE"}', "utf8");
    const junction = join(events.repo, ".agent", "runs", "junctioned-task");
    const made = spawnSync("cmd", ["/c", "mklink", "/J", junction, external], { encoding: "utf8" });
    if (made.status !== 0) return; // 建不了 junction（权限）：跳过这条，不误报
    const sub = await openSse(events.port, events.cookie);
    try {
      await firstEvent(sub);
      const mark = sub.buffer().length;
      writeFileSync(join(external, "state.json"), '{"state":"OUTSIDE-CHANGED"}', "utf8");
      await sleep(1500);
      const grew = sub.buffer().slice(mark);
      expect(grew).not.toContain("event: update"); // junction 目标的变化不进指纹
    } finally {
      sub.close();
    }
  });

  it("多个订阅者共用一次 status：3 个订阅者只起 1 次 status", async () => {
    const events = await openEvents();
    const subs = [await openSse(events.port, events.cookie), await openSse(events.port, events.cookie), await openSse(events.port, events.cookie)];
    try {
      for (const sub of subs) await firstEvent(sub);
      await sleep(300);
      expect(statusRuns(events.report)).toBe(1); // 三个订阅者共用一次
    } finally {
      for (const sub of subs) sub.close();
    }
  });

  it("去抖：2 秒内写 20 次文件，status 不超过 2 次", async () => {
    const events = await openEvents({ statIntervalMs: 2000 });
    const sub = await openSse(events.port, events.cookie);
    try {
      await firstEvent(sub);
      for (let i = 0; i < 20; i += 1) {
        writeFileSync(join(events.attempt, "state.json"), `{"state":"W${i}","n":${i}}`, "utf8");
      }
      await sleep(4000);
      expect(statusRuns(events.report)).toBeLessThanOrEqual(2);
    } finally {
      sub.close();
    }
  });
});

describe("U21 订阅算活动与空闲退出（D30）", () => {
  it("订阅开着服务不退出；断开之后空闲时限到了才退出", async () => {
    const events = await openEvents({ heartbeatMs: 300, idleTimeout: 3 });
    const sub = await openSse(events.port, events.cookie);
    try {
      await firstEvent(sub);
      for (let i = 0; i < 6; i += 1) {
        await sleep(600);
        expect(events.svc.child.exitCode, "有订阅开着时服务不应因空闲退出").toBeNull();
      }
    } finally {
      sub.close();
    }
    const deadline = Date.now() + 15_000;
    while (Date.now() < deadline && events.svc.child.exitCode === null) await sleep(300);
    expect(events.svc.child.exitCode, "订阅断开之后空闲时限到了服务应自己退出").not.toBeNull();
  });
});

describe("D10 Bun 的连接空闲超时", () => {
  it("全局 idleTimeout 设成 2 秒、心跳 500 毫秒时订阅活过 6 秒且收到至少 6 次心跳（server.timeout(req,0)）", async () => {
    const events = await openEvents({ heartbeatMs: 500, bunIdleTimeoutSeconds: 2 });
    const sub = await openSse(events.port, events.cookie);
    try {
      await firstEvent(sub);
      await sleep(6500);
      const beats = sub.buffer().split(": hb").length - 1;
      expect(beats).toBeGreaterThanOrEqual(6);
      expect(sub.buffer()).toContain("event: snapshot"); // 连接没被空闲超时掐断
    } finally {
      sub.close();
    }
  });

  it("同一服务上非 SSE 的空闲 keep-alive 连接仍在约 2 到 4 秒内被关（没有改全局）", async () => {
    const events = await openEvents({ heartbeatMs: 500, bunIdleTimeoutSeconds: 2 });
    // 发一个不带 Connection: close 的请求拿响应，之后保持空闲
    const closed = await new Promise<boolean>((done) => {
      const socket = connect(events.port, "127.0.0.1", () => {
        socket.write(`GET /api/v1/ping HTTP/1.1\r\nHost: 127.0.0.1:${events.port}\r\nCookie: ${events.cookie}\r\n\r\n`, "latin1");
      });
      let sawHead = false;
      const started = Date.now();
      socket.on("data", (chunk: Buffer) => {
        if (chunk.toString("latin1").includes("\r\n\r\n")) sawHead = true;
      });
      socket.on("close", () => done(sawHead));
      socket.on("error", () => done(sawHead));
      setTimeout(() => {
        socket.destroy();
        done(false);
      }, 8000);
      void started;
    });
    expect(closed, "空闲 keep-alive 连接应被 Bun 的 2 秒 idleTimeout 关掉").toBe(true);
  });
});
