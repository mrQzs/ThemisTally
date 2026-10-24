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

/**
 * 「路由名 → 示例路径」表：合同路由表的 19 条读路由，一条不多、一条不少（漏一条即失败）。表里的路径要能命中
 * 对应路由的正则，401 用例也逐条走这张表——它对不上路由表时就红。
 */
const READ_ROUTE_EXAMPLES: Readonly<Record<string, string>> = {
  "api.meta.get": "/api/v1/meta",
  "api.status.get": "/api/v1/status",
  "api.attempts.list": "/api/v1/attempts?task=demo-task",
  "api.attempts.show": "/api/v1/attempts/demo-task/attempt-001",
  "api.attempts.file": "/api/v1/attempts/demo-task/attempt-001/file?path=notes.txt",
  "api.usage.get": "/api/v1/usage",
  "api.config.get": "/api/v1/config",
  "api.config.validate": "/api/v1/config/validate",
  "api.config.history.list": "/api/v1/config/history",
  "api.config.history.show": "/api/v1/config/history/1",
  "api.roles.get": "/api/v1/roles",
  "api.profiles.get": "/api/v1/profiles",
  "api.presets.list": "/api/v1/presets",
  "api.presets.diff": "/api/v1/presets/base/diff/alt",
  "api.runtimes.get": "/api/v1/runtimes",
  "api.plugins.list": "/api/v1/plugins",
  "api.plugins.show": "/api/v1/plugins/example-plugin",
  "api.secrets.list": "/api/v1/secrets",
  "api.secrets.show": "/api/v1/secrets/EXAMPLE_KEY",
};

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
    const routes = readRoutes({ repo: root, runner: { isClosing: false, run: async () => ({ kind: "closing" }) }, cursors: new CursorTable(), transcript: [] });
    const registered = new Map(routes.map((route) => [route.name, route]));
    const listed = Object.keys(READ_ROUTE_EXAMPLES);
    expect(listed.length).toBe(19); // 19 条，一条不多一条不少
    expect(new Set(listed).size).toBe(listed.length); // 表里没有重复
    for (const [name, example] of Object.entries(READ_ROUTE_EXAMPLES)) {
      const route = registered.get(name);
      expect(route, `${name} 应在读路由表里`).toBeDefined();
      const pathname = example.split("?", 1)[0] ?? "";
      expect(route?.pattern.test(pathname), `${name} 的示例路径应命中它的正则：${example}`).toBe(true);
    }
    const reads = routes
      .map((route) => route.name)
      .filter((name) => name !== "bootstrap" && name !== "control.bootstrap" && name !== "api.ping.get" && name !== "api.ping.post");
    expect([...reads].sort()).toEqual([...listed].sort()); // 一条不多、一条不少
    expect(READ_ROUTE_SPECS.map((spec) => spec.name)).toEqual(listed); // 登记表的顺序与名字和这张表一致
  });

  it("不带 cookie 访问任何一条读路由都是 401", async () => {
    for (const example of Object.values(READ_ROUTE_EXAMPLES)) {
      const response = await get(example);
      expect(response.status, `${example} 应要会话`).toBe(401);
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
    for (const example of Object.values(READ_ROUTE_EXAMPLES)) {
      const response = await get(example, cookie);
      expect(response.status, example).toBe(503);
    }
  });
});
