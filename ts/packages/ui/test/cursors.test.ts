// file 路由的句柄与 409（桌面端 §5.3、D11、U14f）：句柄是 43 个字符的随机不透明句柄，内核游标只存在服务内存里；
// 伪造的句柄、服务重启之前的句柄、换了 task/attempt/path 的句柄、被淘汰的句柄都回 409 且不起子进程；内核报
// 「游标对应的文件已变化」也回 409 并丢掉那个句柄。
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { CURSOR_CAPACITY, CursorTable, validHandle } from "../src/cursors.ts";
import type { RunKernel, RunOutcome } from "../src/kernel.ts";
import { readRoutes, type ReadRoutesState } from "../src/readroutes.ts";

let dir = "";
let app: App;
let state: ReadRoutesState;
let calls: string[][];
let behavior: () => RunOutcome;

const page = (cursor: string | null): string =>
  JSON.stringify({ path: "a/b.txt", mode: "text", text: "第 1 页\n", next_cursor: cursor, done: cursor === null });

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-cursor-"));
  calls = [];
  behavior = () => ({ kind: "completed", result: done(0), stdout: page("fake-cursor-0001"), stderr: "" });
  const runner: RunKernel = {
    isClosing: false,
    run: async (argv) => {
      calls.push([...argv]);
      return behavior();
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

describe("句柄表", () => {
  it("句柄是 43 个字符的随机不透明句柄，不含内核游标", () => {
    const table = new CursorTable();
    const handle = table.issue({ task: "demo-task", attempt: "attempt-001", path: "a/b.txt", cursor: "t:1:2:3" });
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(validHandle(handle)).toBe(true);
    expect(handle).not.toContain("t:1:2:3");
    expect(table.size).toBe(1);
    expect(table.take(handle)).toEqual({ task: "demo-task", attempt: "attempt-001", path: "a/b.txt", cursor: "t:1:2:3" });
    expect(table.take(handle)).not.toBeNull(); // 取一次还在（读一页不消耗句柄）
    table.drop(handle);
    expect(table.take(handle)).toBeNull();
  });

  it("用一次就挪到末尾，超容量淘汰最旧的一个", () => {
    const table = new CursorTable();
    const handles: string[] = [];
    for (let index = 0; index < CURSOR_CAPACITY; index += 1) {
      handles.push(table.issue({ task: "t", attempt: "attempt-001", path: "a", cursor: `c${index}` }));
    }
    expect(table.size).toBe(CURSOR_CAPACITY);
    expect(table.take(handles[0] as string)).not.toBeNull(); // 用一次：挪到 Map 末尾
    const extra = table.issue({ task: "t", attempt: "attempt-001", path: "a", cursor: "c-extra" });
    expect(table.size).toBe(CURSOR_CAPACITY); // 超容量只淘汰最旧的一个
    expect(table.take(handles[0] as string)).not.toBeNull(); // 刚用过：保住了
    expect(table.take(handles[1] as string)).toBeNull(); // 现在最旧的被淘汰
    expect(table.take(extra)).not.toBeNull();
  });
});

describe("409 的四种不起子进程的情形", () => {
  it("伪造的句柄（43 个字符但不在表里）→ 409，替身没有被调用", async () => {
    const jar = await cookie();
    const forged = "A".repeat(43);
    expect(validHandle(forged)).toBe(true);
    const result = await get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${forged}`, jar);
    expect(result.status).toBe(409);
    expect(result.body["messages"]).toEqual(["ERROR: 游标无效或文件已变化，请从头读取"]);
    expect(calls).toEqual([]);
  });

  it("句柄格式不对 → 409", async () => {
    const jar = await cookie();
    const result = await get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=short", jar);
    expect(result.status).toBe(409);
    expect(calls).toEqual([]);
  });

  it("换了 task、attempt 或 path 的句柄 → 409，替身没有被调用", async () => {
    const jar = await cookie();
    const first = await get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", jar);
    const handle = ((first.body["data"] as Record<string, unknown>)["next_cursor"] as string) ?? "";
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    for (const target of [
      `/api/v1/attempts/other-task/attempt-001/file?path=a/b.txt&cursor=${handle}`,
      `/api/v1/attempts/demo-task/attempt-002/file?path=a/b.txt&cursor=${handle}`,
      `/api/v1/attempts/demo-task/attempt-001/file?path=a/c.txt&cursor=${handle}`,
    ]) {
      const result = await get(target, jar);
      expect(result.status, target).toBe(409);
    }
    expect(calls).toHaveLength(1); // 只有第一次读起了子进程
  });

  it("服务重启之前的句柄（新表里没有）→ 409", async () => {
    const jar = await cookie();
    const first = await get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", jar);
    const handle = ((first.body["data"] as Record<string, unknown>)["next_cursor"] as string) ?? "";
    state.cursors.drop(handle); // 换一张表等于服务重启：旧句柄全部失效
    const result = await get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${handle}`, jar);
    expect(result.status).toBe(409);
  });
});

describe("内核报「游标对应的文件已变化」", () => {
  it("退出 2 且 stderr 含这句 → 409，句柄被丢掉（再用一次还是 409）", async () => {
    const jar = await cookie();
    const first = await get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", jar);
    const handle = ((first.body["data"] as Record<string, unknown>)["next_cursor"] as string) ?? "";
    behavior = () => ({
      kind: "completed",
      result: done(2),
      stdout: "",
      stderr: "ERROR: 游标对应的文件已变化：请从头读取\n",
    });
    const stale = await get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${handle}`, jar);
    expect(stale.status).toBe(409);
    expect(calls).toHaveLength(2);
    const again = await get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${handle}`, jar);
    expect(again.status).toBe(409);
    expect(calls).toHaveLength(2); // 句柄已经不在表里：不再起子进程
  });
});

describe("next_cursor 是句柄", () => {
  it("内核游标换成句柄；没有下一页时是 null", async () => {
    const jar = await cookie();
    const first = await get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", jar);
    const data = (first.body["data"] as Record<string, unknown>) ?? {};
    expect(data["next_cursor"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(JSON.stringify(first.body)).not.toContain("fake-cursor-0001");
    // 第二页把真游标原样交给内核
    expect(calls[0]).toEqual(["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json"]);
    behavior = () => ({ kind: "completed", result: done(0), stdout: page(null), stderr: "" });
    const handle = data["next_cursor"] as string;
    const second = await get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${handle}`, jar);
    const secondData = (second.body["data"] as Record<string, unknown>) ?? {};
    expect(secondData["next_cursor"]).toBe(null);
    expect(secondData["done"]).toBe(true);
    expect(calls[1]).toEqual(["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json", "--cursor=fake-cursor-0001"]);
  });
});

