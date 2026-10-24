// 19 条读路由的会话默认必须验证（桌面端 §5.2、T17、D01）：不带 cookie 一律 401，只有 bootstrap 与
// control.bootstrap 公开；/api/ 下不存在的路径没有会话是 401（不泄露它在不在）；静态资源不验会话。表里必须正好
// 是路由表里的 19 条读路由（一条不多、一条不少），漏一条即失败。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp, type App } from "../src/app.ts";
import { CursorTable } from "../src/cursors.ts";
import type { RunKernel } from "../src/kernel.ts";
import { READ_ROUTE_SPECS, readRoutes } from "../src/readroutes.ts";

const PORT = 53277;

let root = "";
let app: App;

beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-auth-"));
  root = join(dir, "assets");
  mkdirSync(root, { recursive: true });
  writeFileSync(join(root, "index.html"), "<!doctype html><title>auth</title>\n");
  const runner: RunKernel = { isClosing: false, run: async () => ({ kind: "closing" }) };
  app = createApp({
    port: PORT,
    assets: root,
    controlToken: "t".repeat(43),
    extraRoutes: readRoutes({ repo: dir, runner, cursors: new CursorTable(), transcript: [] }),
  });
});

afterAll(() => {
  rmSync(join(root, ".."), { recursive: true, force: true });
});

const get = (target: string, cookie?: string): Promise<Response> =>
  app.fetch(new Request(`http://127.0.0.1:${PORT}${target}`, { headers: { host: `127.0.0.1:${PORT}`, ...(cookie === undefined ? {} : { cookie }) } }));

const session = async (): Promise<string> => {
  const nonce = app.issueBootstrap();
  const booted = await get(`/bootstrap/${nonce}`);
  return booted.headers.get("set-cookie")?.split(";")[0] ?? "";
};

describe("19 条读路由都要会话（T17）", () => {
  it("「路由名 → 示例路径」表正好是路由表里的 19 条读路由", () => {
    const registered = new Set(readRoutes({ repo: root, runner: { isClosing: false, run: async () => ({ kind: "closing" }) }, cursors: new CursorTable(), transcript: [] }).map((route) => route.name));
    const listed = READ_ROUTE_SPECS.map((spec) => spec.name);
    expect(new Set(listed).size).toBe(listed.length); // 表里没有重复
    expect(listed.length).toBe(19);
    for (const name of listed) expect(registered.has(name), name).toBe(true);
    const reads = [...registered].filter((name) => name !== "bootstrap" && name !== "control.bootstrap" && name !== "api.ping.get" && name !== "api.ping.post");
    expect(reads.sort()).toEqual([...listed].sort()); // 一条不多、一条不少
  });

  it("不带 cookie 访问任何一条读路由都是 401", async () => {
    for (const spec of READ_ROUTE_SPECS) {
      const response = await get(spec.path);
      expect(response.status, `${spec.name}（${spec.path}）`).toBe(401);
      const body = (await response.json()) as Record<string, unknown>;
      expect(body["messages"]).toEqual(["ERROR: 未认证"]);
      expect(body["ok"]).toBe(false);
    }
  });

  it("两条公开路由不要会话；/api/ 下不存在的路径没有会话 401、有会话 404；静态资源不验会话", async () => {
    const nonce = app.issueBootstrap();
    expect((await get(`/bootstrap/${nonce}`)).status).toBe(302);
    const control = await app.fetch(
      new Request(`http://127.0.0.1:${PORT}/control/bootstrap`, {
        method: "POST",
        headers: { host: `127.0.0.1:${PORT}`, "x-themis-control": "t".repeat(43) },
      }),
    );
    expect(control.status).toBe(200);
    expect((await get("/api/v1/nope")).status).toBe(401); // 不存在的路径也不泄露它在不在
    const cookie = await session();
    expect((await get("/api/v1/nope", cookie)).status).toBe(404);
    expect((await get("/", cookie)).status).toBe(200);
    // ping 也要会话（只有 bootstrap 与 control.bootstrap 公开）
    expect((await get("/api/v1/ping")).status).toBe(401);
    expect((await get("/api/v1/ping", cookie)).status).toBe(200);
  });

  it("带了会话之后 19 条读路由都过得了会话这一关（替身一律回 closing → 503）", async () => {
    const cookie = await session();
    for (const spec of READ_ROUTE_SPECS) {
      const response = await get(spec.path, cookie);
      expect(response.status, `${spec.name}（${spec.path}）`).toBe(503);
    }
  });
});
