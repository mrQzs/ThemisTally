// 请求管线（桌面端 D02、D05、D12、D16 的进程内部分）：不起服务，直接 app.fetch(new Request(...))。钉住管线次序
// （Host → 方法 → /api/ 会话 → CSRF 与正文 → 处理函数 → 安全头 → 访问记录）、错误信封的形状、静态资源不验会话，
// 以及访问记录里只有路由名。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp } from "../src/app.ts";
import { NONCE_TTL_MS } from "../src/localhttp/session.ts";
import { bootstrapRejected } from "../src/localhttp/session.ts";

const PORT = 53210;
const ORIGIN = `http://127.0.0.1:${PORT}`;

let root = "";
let app: ReturnType<typeof createApp>;

beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), "themis-ui-app-"));
  root = join(dir, "assets");
  mkdirSync(join(root, "assets"), { recursive: true });
  writeFileSync(join(root, "index.html"), "<!doctype html><title>app</title>\n");
  writeFileSync(join(root, "assets", "app.js"), "// app.js\n");
  writeFileSync(join(root, "notes.xyz"), "xyz\n");
  app = createApp({ port: PORT, assets: root, controlToken: "t".repeat(43), nonceTtlMs: NONCE_TTL_MS });
});

afterAll(() => {
  rmSync(join(root, ".."), { recursive: true, force: true });
});

const get = (path: string, headers: Record<string, string> = {}, host = `127.0.0.1:${PORT}`): Promise<Response> =>
  app.fetch(new Request(`http://127.0.0.1:${PORT}${path}`, { headers: { host, ...headers } }));

const post = (path: string, body: string, headers: Record<string, string> = {}): Promise<Response> =>
  app.fetch(
    new Request(`http://127.0.0.1:${PORT}${path}`, {
      method: "POST",
      body,
      headers: { host: `127.0.0.1:${PORT}`, ...headers },
    }),
  );

const postRaw = (path: string, headers: Record<string, string> = {}): Promise<Response> =>
  app.fetch(
    new Request(`http://127.0.0.1:${PORT}${path}`, {
      method: "POST",
      headers: { host: `127.0.0.1:${PORT}`, ...headers },
    }),
  );

const json = async (response: Response): Promise<Record<string, unknown>> => (await response.json()) as Record<string, unknown>;

describe("请求管线", () => {
  it("错误信封的形状：七个字段、次序、messages 一行 ERROR: …", async () => {
    const response = await get("/api/v1/ping");
    expect(response.status).toBe(401);
    const body = await json(response);
    expect(Object.keys(body)).toEqual(["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"]);
    expect(body).toMatchObject({ ok: false, exit_code: null, data: null, output: [], command: [] });
    expect(body["messages"]).toEqual(["ERROR: 未认证"]);
  });

  it("成功信封的形状：ok 为 true，data 是路由给的", async () => {
    const response = await get("/api/v1/ping", { cookie: "themis_session=nope" });
    expect(response.status).toBe(401);
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const accepted = await get(path);
    expect(accepted.status).toBe(302);
    const cookie = accepted.headers.get("set-cookie")?.split(";")[0] ?? "";
    const ping = await get("/api/v1/ping", { cookie });
    expect(ping.status).toBe(200);
    expect(await json(ping)).toMatchObject({ ok: true, data: { posts: 0 } });
    expect(ping.headers.get("cache-control")).toBe("no-store");
  });

  it("Host 不对一律 403：静态、引导、控制都不例外", async () => {
    const path = `/bootstrap/${app.issueBootstrap()}`;
    for (const host of [`evil.example:${PORT}`, `127.0.0.1:${PORT + 1}`, "127.0.0.1", `localhost.:${PORT}`]) {
      expect((await get("/", {}, host)).status, host).toBe(403);
      expect((await get(path, {}, host)).status, host).toBe(403);
      expect((await get("/api/v1/ping", {}, host)).status, host).toBe(403);
    }
    // Host 不对时引导地址没有被消耗：换回正确的 Host 仍可用
    expect((await get(path, {}, `localhost:${PORT}`)).status).toBe(302);
    const control = await post("/control/bootstrap", "{}", {
      origin: ORIGIN,
      "x-themis-ui": "1",
      "content-type": "application/json",
      "x-themis-control": "t".repeat(43),
    });
    expect(control.status).toBe(200);
  });

  it("方法白名单先于会话：PUT /api/v1/ping 不带 cookie 也是 405 且带 Allow", async () => {
    const response = await app.fetch(
      new Request(`http://127.0.0.1:${PORT}/api/v1/ping`, { method: "PUT", headers: { host: `127.0.0.1:${PORT}` } }),
    );
    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("GET, POST");
    for (const method of ["DELETE", "OPTIONS", "HEAD"]) {
      const other = await app.fetch(
        new Request(`http://127.0.0.1:${PORT}/`, { method, headers: { host: `127.0.0.1:${PORT}` } }),
      );
      expect(other.status, method).toBe(405);
      expect(other.headers.get("allow")).toBe("GET, POST");
    }
  });

  it("/api/ 下不存在的路径：没有会话 401，有会话 404", async () => {
    expect((await get("/api/v1/nope")).status).toBe(401);
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const cookie = (await get(path)).headers.get("set-cookie")?.split(";")[0] ?? "";
    expect((await get("/api/v1/nope", { cookie })).status).toBe(404);
    expect((await get("/api/v1/ping", { cookie })).status).toBe(200);
  });

  it("CSRF 被拒时处理函数没有运行：三种拒绝分别 403、403、415", async () => {
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const cookie = (await get(path)).headers.get("set-cookie")?.split(";")[0] ?? "";
    const base = { cookie, origin: ORIGIN, "content-type": "application/json" };
    expect((await post("/api/v1/ping", "{}", { ...base, "x-themis-ui": "0" })).status).toBe(403);
    expect((await post("/api/v1/ping", "{}", { ...base, origin: "https://evil.example" })).status).toBe(403);
    const missing = { ...base } as Record<string, string>;
    delete missing["origin"];
    expect((await post("/api/v1/ping", "{}", missing)).status).toBe(403);
    expect((await post("/api/v1/ping", "{}", { ...base, "x-themis-ui": "1", "content-type": "text/plain" })).status).toBe(415);
    expect((await get("/api/v1/ping", { cookie })).status).toBe(200);
    expect((await json(await get("/api/v1/ping", { cookie })))["data"]).toEqual({ posts: 0 });
    const ok = await post("/api/v1/ping", "{}", { ...base, "x-themis-ui": "1" });
    expect(ok.status).toBe(200);
    expect((await json(ok))["data"]).toEqual({ posts: 1 });
  });

  it("请求体：超限 413、空正文与坏 JSON 400、正文必须是对象", async () => {
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const cookie = (await get(path)).headers.get("set-cookie")?.split(";")[0] ?? "";
    const base = { cookie, origin: ORIGIN, "x-themis-ui": "1", "content-type": "application/json" };
    expect((await post("/api/v1/ping", "x".repeat(65537), base)).status).toBe(413);
    expect((await post("/api/v1/ping", "", base)).status).toBe(400);
    expect((await post("/api/v1/ping", "not json", base)).status).toBe(400);
    expect((await post("/api/v1/ping", "[]", base)).status).toBe(400);
    expect((await post("/api/v1/ping", '"text"', base)).status).toBe(400);
    expect((await post("/api/v1/ping", "{}", base)).status).toBe(200);
  });

  it("静态资源不验会话，只验 Host；/ 给 index.html", async () => {
    const index = await get("/");
    expect(index.status).toBe(200);
    expect(index.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(index.headers.get("cache-control")).toBe("no-cache");
    expect(index.headers.get("content-security-policy")).toContain("default-src 'none'");
    const js = await get("/assets/app.js");
    expect(js.status).toBe(200);
    expect(js.headers.get("content-type")).toBe("text/javascript; charset=utf-8");
    expect((await get("/notes.xyz")).status).toBe(404);
    expect((await get("/missing.txt")).status).toBe(404);
    expect((await get("/..%2f..%2fsecret.txt")).status).toBe(400);
    expect((await get("/", {}, `evil.example:${PORT}`)).status).toBe(403);
  });

  it("控制接口：不带令牌、令牌错、只带 cookie 都是 403；对的令牌换引导地址并作废旧会话", async () => {
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const cookie = (await get(path)).headers.get("set-cookie")?.split(";")[0] ?? "";
    const base = { origin: ORIGIN, "x-themis-ui": "1", "content-type": "application/json" };
    const token = "t".repeat(43);
    expect((await post("/control/bootstrap", "{}", base)).status).toBe(403);
    expect((await post("/control/bootstrap", "{}", { ...base, "x-themis-control": "wrong" })).status).toBe(403);
    expect((await post("/control/bootstrap", "{}", { ...base, cookie })).status).toBe(403);
    const ok = await post("/control/bootstrap", "{}", { ...base, "x-themis-control": token });
    expect(ok.status).toBe(200);
    const body = await json(ok);
    const fresh = String((body["data"] as Record<string, unknown>)["bootstrap"]).replace(ORIGIN, "");
    expect(fresh).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
    expect((await get("/api/v1/ping", { cookie })).status).toBe(401);
    expect((await get(path)).status).toBe(404);
    expect((await get(fresh)).status).toBe(302);
  });

  it("控制接口的 Origin 是别的站点：403 且不计入限速", async () => {
    const base = { origin: "https://evil.example", "x-themis-ui": "1", "content-type": "application/json" };
    for (let index = 0; index < 7; index += 1) {
      expect((await post("/control/bootstrap", "{}", base)).status).toBe(403);
    }
    const ok = await post("/control/bootstrap", "{}", {
      origin: ORIGIN,
      "x-themis-ui": "1",
      "content-type": "application/json",
      "x-themis-control": "t".repeat(43),
    });
    expect(ok.status).toBe(200);
  });

  it("控制接口不读正文：只带对令牌就 200，正文与 CSRF 头全都无关", async () => {
    const token = "t".repeat(43);
    const bootstrapOf = async (response: Response): Promise<string> => {
      const body = await json(response);
      return String((body["data"] as Record<string, unknown>)["bootstrap"]).replace(ORIGIN, "");
    };
    // 只带对令牌：正文、Content-Type、X-Themis-UI、Origin、cookie 有没有都一律 200（穷举门，不读正文）
    const headerSets: Record<string, string>[] = [
      { "x-themis-control": token },
      { "x-themis-control": token, origin: ORIGIN },
      { "x-themis-control": token, "x-themis-ui": "1" },
      { "x-themis-control": token, "content-type": "application/json" },
      { "x-themis-control": token, "content-type": "text/plain" },
      { "x-themis-control": token, "content-type": "application/jsonp" },
      { "x-themis-control": token, cookie: "themis_session=nope" },
      { "x-themis-control": token, origin: ORIGIN, "x-themis-ui": "1", "content-type": "application/json" },
    ];
    for (const headers of headerSets) {
      const response = await postRaw("/control/bootstrap", headers);
      expect(response.status, JSON.stringify(headers)).toBe(200);
      const fresh = await bootstrapOf(response);
      expect(fresh, JSON.stringify(headers)).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
      // 新给出的引导地址真的能建会话
      const accepted = await get(fresh);
      expect(accepted.status).toBe(302);
      expect(accepted.headers.get("set-cookie")).toMatch(/^themis_session=[A-Za-z0-9_-]{43}; HttpOnly; SameSite=Strict; Path=\/$/u);
    }
    // 带坏正文、空正文、合法 JSON 对象正文：一样 200（正文被忽略）
    for (const body of ["not json", "", "[]", '{"a":1}']) {
      const response = await post("/control/bootstrap", body, { "x-themis-control": token });
      expect(response.status, body).toBe(200);
      expect(await bootstrapOf(response), body).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
    }
    // 门还是令牌：令牌错、不带令牌、只带 cookie 都是 403
    const full = { origin: ORIGIN, "x-themis-ui": "1", "content-type": "application/json" };
    expect((await post("/control/bootstrap", "{}", full)).status).toBe(403);
    expect((await post("/control/bootstrap", "{}", { ...full, "x-themis-control": "wrong" })).status).toBe(403);
    const path = `/bootstrap/${app.issueBootstrap()}`;
    const cookie = (await get(path)).headers.get("set-cookie")?.split(";")[0] ?? "";
    expect((await post("/control/bootstrap", "{}", { ...full, cookie })).status).toBe(403);
    // 外来 Origin：403 且不计入限速（6 次之后对的令牌仍 200）
    for (let index = 0; index < 6; index += 1) {
      expect((await postRaw("/control/bootstrap", { "x-themis-control": token, origin: "https://evil.example" })).status).toBe(403);
    }
    expect((await postRaw("/control/bootstrap", { "x-themis-control": token })).status).toBe(200);
    // 连续 5 次失败之后锁 1 秒：锁定期内对的令牌也 429 且带 Retry-After
    for (let index = 0; index < 5; index += 1) {
      expect((await postRaw("/control/bootstrap", { "x-themis-control": `wrong-${index}` })).status).toBe(403);
    }
    const locked = await postRaw("/control/bootstrap", { "x-themis-control": token });
    expect(locked.status).toBe(429);
    expect(Number(locked.headers.get("retry-after"))).toBeGreaterThanOrEqual(1);
    // 豁免没有外溢到 API：POST /api/v1/ping 仍要 CSRF 三查与 JSON 正文
    const session = (await get(`/bootstrap/${app.issueBootstrap()}`)).headers.get("set-cookie")?.split(";")[0] ?? "";
    const api = { cookie: session, origin: ORIGIN, "content-type": "application/json" };
    expect((await post("/api/v1/ping", "{}", { ...api, "x-themis-ui": "0" })).status).toBe(403);
    const noOrigin = { ...api } as Record<string, string>;
    delete noOrigin["origin"];
    expect((await post("/api/v1/ping", "{}", noOrigin)).status).toBe(403);
    expect((await post("/api/v1/ping", "{}", { ...api, "x-themis-ui": "1", "content-type": "text/plain" })).status).toBe(415);
    expect((await post("/api/v1/ping", "not json", { ...api, "x-themis-ui": "1" })).status).toBe(400);
  });

  it("访问记录只有路由名、状态码与耗时；引导地址进不了记录", async () => {
    const path = `/bootstrap/${app.issueBootstrap()}`;
    await get(path);
    await get("/api/v1/ping");
    await get("/", {}, `evil.example:${PORT}`);
    await get("/nope.txt");
    const routes = app.accessLog.entries().map((entry) => entry.route);
    expect(routes).toContain("bootstrap");
    expect(routes).toContain("static");
    expect(routes).toContain("rejected");
    expect(routes).toContain("unmatched");
    for (const entry of app.accessLog.entries()) {
      expect(Object.keys(entry)).toEqual(["route", "status", "ms"]);
      expect(entry.route).toMatch(/^[a-z][a-z0-9.-]*$/u);
      expect(JSON.stringify(entry)).not.toContain("bootstrap/");
    }
  });

  it("引导地址过期与用过走同一个响应", async () => {
    const fresh = createApp({ port: PORT, assets: root, controlToken: "t".repeat(43), nonceTtlMs: 0 });
    const path = `/bootstrap/${fresh.issueBootstrap()}`;
    const expired = await fresh.fetch(new Request(`http://127.0.0.1:${PORT}${path}`, { headers: { host: `127.0.0.1:${PORT}` } }));
    const missing = await fresh.fetch(
      new Request(`http://127.0.0.1:${PORT}/bootstrap/zzzz`, { headers: { host: `127.0.0.1:${PORT}` } }),
    );
    expect(expired.status).toBe(404);
    expect(missing.status).toBe(404);
    expect(await expired.text()).toBe(await missing.text());
    expect(expired.headers.get("set-cookie")).toBeNull();
    expect(bootstrapRejected().status).toBe(404);
  });

  it("inflight：请求进行中记 1，结束之后回 0", async () => {
    const pending = app.fetch(new Request(`http://127.0.0.1:${PORT}/`, { headers: { host: `127.0.0.1:${PORT}` } }));
    expect(app.inflight()).toBe(1);
    await pending;
    expect(app.inflight()).toBe(0);
  });
});
