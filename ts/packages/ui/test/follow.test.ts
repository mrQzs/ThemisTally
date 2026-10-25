// file 路由的「跟随」（桌面端 §5.3、D13，T018 第 4 片）：follow=1 只认字面 1，跟在起子进程之前校验（取值不合格、
// 非 JSONL 都回 400）；跟随的 argv 追加 --complete-lines（内核只给已经写完的行，--cursor= 仍排最后）；跟随时
// next_cursor 一律是句柄（不看 done），空页复用请求带来的那个句柄（句柄表项数不变），有内容才发新句柄（旧句柄留
// 在表里，不 drop）；跟随的 data 末尾追加 poll_after_ms（2000，与 503 的 Retry-After: 2 一致）。409 的情形沿用
// T016（句柄无效、内核报「游标对应的文件已变化」），轮询照样经执行器的并发上限与队列。不起真服务：进程内建 app，
// 内核子进程用替身 runner（照 cursors.test.ts 的写法），能直接断言 argv、页内容、409 与句柄表。
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { CURSOR_CAPACITY, CursorTable } from "../src/cursors.ts";
import type { RunKernel, RunOutcome } from "../src/kernel.ts";
import { FOLLOW_ARGV, FOLLOW_MIN_INTERVAL_MS, readRoutes, type ReadRoutesState } from "../src/readroutes.ts";
import { readReport, startApp } from "./support.ts";

let dir = "";
let app: App;
let state: ReadRoutesState;
let calls: string[][];
let behavior: (argv: readonly string[]) => RunOutcome;

/** 一页 JSONL（内核的 _jsonl_page 给出的形状）。 */
const jsonlPage = (lines: unknown[], cursor: string | null, done: boolean): string =>
  JSON.stringify({ path: "events.jsonl", mode: "jsonl", lines, next_cursor: cursor, done });

/** 一行 JSONL（跟随时给的就是这种）。 */
const line = (n: number, text: string, part?: number, parts?: number): Record<string, unknown> =>
  part === undefined || parts === undefined ? { n, text } : { n, text, part, parts };

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-follow-"));
  calls = [];
  behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([line(1, "{\"a\": 1}")], "fake-cursor-0001", false), stderr: "" });
  const runner: RunKernel = {
    isClosing: false,
    run: async (argv) => {
      calls.push([...argv]);
      return behavior(argv);
    },
  };
  state = { repo: dir, runner, cursors: new CursorTable(), transcript: [] };
  app = createApp({ port: 1, assets: dir, controlToken: "t".repeat(43), extraRoutes: readRoutes(state) });
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

function done(exitCode: number) {
  return {
    exit_code: exitCode, timed_out: false, interrupted: false, spawn_error: null, wall_seconds: 0.01,
    stray_processes: false, kill_method: "job-object", pid: 4242, ctrl_break: null, ctrl_break_winerror: null,
  };
}

const cookie = async (): Promise<string> => {
  const nonce = app.issueBootstrap();
  const booted = await app.fetch(new Request(`http://127.0.0.1:1/bootstrap/${nonce}`, { headers: { host: "127.0.0.1:1" } }));
  return booted.headers.get("set-cookie")?.split(";")[0] ?? "";
};

const get = async (target: string, jar: string): Promise<{ status: number; body: Record<string, unknown> }> => {
  const response = await app.fetch(new Request(`http://127.0.0.1:1${target}`, { headers: { host: "127.0.0.1:1", cookie: jar } }));
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
};

const data = (body: Record<string, unknown>): Record<string, unknown> => (body["data"] as Record<string, unknown>) ?? {};

const FILE = "/api/v1/attempts/demo-task/attempt-001/file";

/** 登记表里的一条跟随 argv（替身收到的 argv 与它逐项相等）。 */
const followArgv = (name: "api.attempts.file.follow" | "api.attempts.file.follow.cursor"): readonly string[] => FOLLOW_ARGV[name] as readonly string[];

describe("跟随的 argv（F1）", () => {
  it("跟随的两条逐项等于 FOLLOW_ARGV；普通翻页的 argv 一条不变", async () => {
    const jar = await cookie();
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    expect(first.status).toBe(200);
    expect(calls[0]).toEqual([...followArgv("api.attempts.file.follow")]);
    const handle = data(first.body)["next_cursor"] as string;
    await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    expect(calls[1]).toEqual([...followArgv("api.attempts.file.follow.cursor")]);

    // 普通翻页：不带 follow，argv 与既有的模板一条不变
    behavior = () => ({ kind: "completed", result: done(0), stdout: JSON.stringify({ path: "a/b.txt", mode: "text", text: "第 1 页\n", next_cursor: "fake-cursor-0001", done: false }), stderr: "" });
    const plain = await get(`${FILE}?path=a/b.txt`, jar);
    expect(plain.status).toBe(200);
    expect(calls[2]).toEqual(["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json"]);
    const plainHandle = data(plain.body)["next_cursor"] as string;
    await get(`${FILE}?path=a/b.txt&cursor=${plainHandle}`, jar);
    expect(calls[3]).toEqual(["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json", "--cursor=fake-cursor-0001"]);
  });
});

describe("末尾也发句柄（F2）", () => {
  it("内核回 done: true 并带游标 → 跟随给 43 个字符的句柄；同一份内核输出走非跟随是 null", async () => {
    const jar = await cookie();
    behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([line(1, "{\"a\": 1}")], "fake-cursor-0001", true), stderr: "" });
    const followed = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    expect(data(followed.body)["next_cursor"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(data(followed.body)["done"]).toBe(true);
    expect(data(followed.body)["poll_after_ms"]).toBe(2000);

    // 同一份内核输出（done 为真、带游标）走非跟随：没有下一页，next_cursor 是 null，也不带 --complete-lines
    const plain = await get(`${FILE}?path=events.jsonl`, jar);
    expect(plain.status).toBe(200);
    expect(data(plain.body)["next_cursor"]).toBe(null);
    expect(data(plain.body)["done"]).toBe(true);
    expect(calls[1]).toEqual(["logs", "cat", "demo-task/attempt-001", "events.jsonl", "--json"]);
  });
});

describe("空页复用请求里的句柄（F3/F4）", () => {
  it("带句柄 H 跟随、内核回 lines: [] → next_cursor 原样是 H，表项数不变（连做 5 次）", async () => {
    const jar = await cookie();
    behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([line(1, "{\"a\": 1}")], "fake-cursor-0001", false), stderr: "" });
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    const handle = data(first.body)["next_cursor"] as string;
    const before = state.cursors.size;
    behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([], "fake-cursor-0001", false), stderr: "" });
    for (let round = 0; round < 5; round += 1) {
      const page = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
      expect(page.status).toBe(200);
      expect(data(page.body)["lines"]).toEqual([]);
      expect(data(page.body)["next_cursor"], `第 ${round + 1} 次`).toBe(handle);
      expect(state.cursors.size).toBe(before);
    }
    expect(calls).toHaveLength(6);
  });

  it("不带句柄的跟随空页发一个句柄，之后的轮询一直复用它", async () => {
    const jar = await cookie();
    behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([], "fake-cursor-0001", false), stderr: "" });
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    const handle = data(first.body)["next_cursor"] as string;
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(state.cursors.size).toBe(1);
    for (let round = 0; round < 3; round += 1) {
      const page = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
      expect(data(page.body)["next_cursor"]).toBe(handle);
      expect(state.cursors.size).toBe(1); // 空闲跟随不涨表
    }
  });
});

describe("有内容发新句柄、旧句柄仍可用（F5）", () => {
  it("新句柄不是 H、表 +1；带 H 再请求一次不是 409", async () => {
    const jar = await cookie();
    behavior = () => ({ kind: "completed", result: done(0), stdout: jsonlPage([line(1, "{\"a\": 1}")], "fake-cursor-0001", false), stderr: "" });
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    const handle = data(first.body)["next_cursor"] as string;
    const second = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    const fresh = data(second.body)["next_cursor"] as string;
    expect(fresh).not.toBe(handle);
    expect(state.cursors.size).toBe(2); // 旧句柄留在表里（站主 Q1：不 drop）
    const again = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    expect(again.status).toBe(200);
    expect(data(again.body)["next_cursor"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
  });
});

describe("内核报「游标对应的文件已变化」（F6）", () => {
  it("退出 2 且 stderr 含这句 → 409，句柄被丢掉；再用它 409 且不起子进程", async () => {
    const jar = await cookie();
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    const handle = data(first.body)["next_cursor"] as string;
    behavior = () => ({ kind: "completed", result: done(2), stdout: "", stderr: "ERROR: 游标对应的文件已变化：请从头读取\n" });
    const stale = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    expect(stale.status).toBe(409);
    expect(stale.body["messages"]).toEqual(["ERROR: 游标无效或文件已变化，请从头读取"]);
    expect(calls).toHaveLength(2);
    const again = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    expect(again.status).toBe(409);
    expect(calls).toHaveLength(2); // 句柄已经不在表里：不再起子进程
  });
});

describe("两种 400 在起子进程之前（F7/F8）", () => {
  it("notes.txt、a.json、a.jſonl 带 follow=1 → 400，替身没有被调用；LOG.JSONL 放行", async () => {
    const jar = await cookie();
    for (const path of ["notes.txt", "a.json", "a.jſonl"]) {
      const result = await get(`${FILE}?path=${encodeURIComponent(path)}&follow=1`, jar);
      expect(result.status, path).toBe(400);
      expect(result.body["messages"], path).toEqual(["ERROR: 只有 JSONL 文件支持跟随"]);
    }
    expect(calls).toEqual([]);
    const upper = await get(`${FILE}?path=LOG.JSONL&follow=1`, jar); // 大小写不敏感
    expect(upper.status).toBe(200);
    expect(calls).toHaveLength(1);
  });

  it("follow=0、follow=true、follow=（空串）→ 400，替身没有被调用", async () => {
    const jar = await cookie();
    for (const value of ["0", "true", ""]) {
      const result = await get(`${FILE}?path=events.jsonl&follow=${value}`, jar);
      expect(result.status, `follow=${value}`).toBe(400);
      expect(result.body["messages"], `follow=${value}`).toEqual(["ERROR: follow 参数不合格（只接受 1）"]);
    }
    expect(calls).toEqual([]);
  });
});

describe("轮询下限（F9）", () => {
  it("跟随的 data 有 poll_after_ms 且值是 2000；非跟随的 data 里没有这个键", async () => {
    const jar = await cookie();
    const followed = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    expect(data(followed.body)["poll_after_ms"]).toBe(FOLLOW_MIN_INTERVAL_MS);
    expect(FOLLOW_MIN_INTERVAL_MS).toBe(2000);
    behavior = () => ({ kind: "completed", result: done(0), stdout: JSON.stringify({ path: "a/b.txt", mode: "text", text: "第 1 页\n", next_cursor: "fake-cursor-0001", done: false }), stderr: "" });
    const plain = await get(`${FILE}?path=a/b.txt`, jar);
    expect(plain.status).toBe(200);
    expect("poll_after_ms" in data(plain.body)).toBe(false);
  });
});

describe("轮询照样经执行器（F10）", () => {
  it("队列满 → 503 且带 retry-after: 2；之后带同一个句柄重试成功", async () => {
    const started = await startApp({ maxConcurrent: 1, maxQueue: 0 });
    try {
      process.env["FAKE_KERNEL_JSON"] = jsonlPage([line(1, "{\"a\": 1}")], "fake-cursor-0001", false);
      process.env["FAKE_KERNEL_SLEEP_MS"] = "600";
      const target = `${FILE}?path=events.jsonl&follow=1`;
      const first = await started.get(target);
      expect(first.status).toBe(200);
      const handle = data((await first.json()) as Record<string, unknown>)["next_cursor"] as string;
      const polled = `${target}&cursor=${handle}`;
      // 靠在途计数：等在跑的那一个真的起了子进程，再发下一个（队列为 0，名额被占满就立刻 503）
      const inflight = started.get(polled);
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline && readReport(started.report).filter((row) => row.event === "begin").length === 0) {
        await new Promise((settle) => setTimeout(settle, 20));
      }
      const busy = await started.get(polled);
      expect(busy.status).toBe(503);
      expect(busy.headers.get("retry-after")).toBe("2");
      expect(((await busy.json()) as Record<string, unknown>)["messages"]).toEqual(["ERROR: 服务繁忙，请稍后重试"]);
      await inflight; // 在跑的那个正常收尾
      const retried = await started.get(polled);
      expect(retried.status).toBe(200);
      expect(data((await retried.json()) as Record<string, unknown>)["next_cursor"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    } finally {
      delete process.env["FAKE_KERNEL_JSON"];
      delete process.env["FAKE_KERNEL_SLEEP_MS"];
      await started.dispose();
    }
  });
});

describe("句柄表有上界（F11）", () => {
  it(`发满 CURSOR_CAPACITY（${CURSOR_CAPACITY}）个句柄之后，最早那个跟随句柄回 409`, async () => {
    const jar = await cookie();
    const handles: string[] = [];
    for (let index = 0; index <= CURSOR_CAPACITY; index += 1) {
      const page = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
      expect(page.status).toBe(200);
      handles.push(data(page.body)["next_cursor"] as string);
    }
    expect(state.cursors.size).toBe(CURSOR_CAPACITY);
    expect(calls).toHaveLength(CURSOR_CAPACITY + 1);
    const evicted = await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handles[0]}`, jar);
    expect(evicted.status).toBe(409); // 被 LRU 淘汰：按既有约定从头读
    expect(calls).toHaveLength(CURSOR_CAPACITY + 1); // 不起子进程
  });
});

describe("分片接着给（F12）", () => {
  it("part 1/2、done 为假的一页发新句柄，下一次请求的 argv 带它的内核游标", async () => {
    const jar = await cookie();
    let round = 0;
    behavior = () => {
      round += 1;
      return { kind: "completed", result: done(0), stdout: jsonlPage([line(1, "第 1 片", 1, 2)], `fake-cursor-part-${round}`, false), stderr: "" };
    };
    const first = await get(`${FILE}?path=events.jsonl&follow=1`, jar);
    expect(data(first.body)["lines"]).toEqual([{ n: 1, text: "第 1 片", part: 1, parts: 2 }]);
    expect(data(first.body)["done"]).toBe(false);
    const handle = data(first.body)["next_cursor"] as string;
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    await get(`${FILE}?path=events.jsonl&follow=1&cursor=${handle}`, jar);
    expect(calls[1]).toEqual([...followArgv("api.attempts.file.follow"), "--cursor=fake-cursor-part-1"]);
  });
});
