// 起真进程的服务黑盒（桌面端 T10、D01–D16）：服务在单独的 Bun 进程里，客户端在 Node 一侧用原始套接字发请求。
// 覆盖握手与绑定、Host、会话与引导地址、CSRF、方法白名单、静态资源与只解码一次、请求体上限、安全头矩阵、控制接口
// 与限速、日志里没有令牌、用法错误与已有服务、生命周期与锁。关进程一律靠关 stdin（stdin EOF）或 kill，不发控制台信号。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type RunningService, chunkedWatch, cliArgv, header, request, requestNoBody, runBrief, startService } from "./harness.ts";

let dir = "";
let assets = "";
let outside = "";
let canary = "";
let bodyCanary = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-svc-"));
  assets = join(dir, "assets");
  outside = join(dir, "outside");
  mkdirSync(join(assets, "assets"), { recursive: true });
  mkdirSync(join(assets, "sub"), { recursive: true });
  mkdirSync(outside, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>T015</title><p>T015-INDEX-MARKER</p>\n");
  writeFileSync(join(assets, "assets", "app.js"), "// T015-APP-JS-MARKER\nconsole.log('t015');\n");
  writeFileSync(join(assets, "notes.xyz"), "T015-NOTES-XYZ\n");
  canary = `T015-CANARY-${Math.random().toString(16).slice(2)}`;
  writeFileSync(join(outside, "secret.txt"), `${canary}\n`);
  bodyCanary = `T015-BODY-${Math.random().toString(16).slice(2)}`;
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

const repoOf = (name: string): string => {
  const repo = join(dir, name);
  mkdirSync(repo, { recursive: true });
  return repo;
};

const cookieOf = (response: { headers: Map<string, string> }): string => {
  const value = header(response as never, "set-cookie") ?? "";
  return value.split(";")[0] ?? "";
};

/** 发一个声明 Content-Length 超过上限（65537）的 POST：服务一个字节也不读，直接回 413。 */
const declaredOverLimit = (port: number, headers: readonly [string, string][]): Promise<{ status: number; headers: Map<string, string>; body: Buffer }> =>
  new Promise((done, fail) => {
    const net = require("node:net") as typeof import("node:net");
    const socket = net.connect(port, "127.0.0.1", () => {
      const lines = [
        "POST /api/v1/ping HTTP/1.1",
        `Host: 127.0.0.1:${port}`,
        "Connection: close",
        "Content-Length: 65537",
        ...headers.map(([name, value]) => `${name}: ${value}`),
      ];
      socket.end(`${lines.join("\r\n")}\r\n\r\n`, "latin1");
    });
    socket.setTimeout(15_000, () => socket.destroy(new Error("超时")));
    let buffer = Buffer.alloc(0);
    socket.on("data", (chunk: Buffer) => {
      buffer = Buffer.concat([buffer, chunk]);
    });
    const finish = (): void => {
      const text = buffer.toString("latin1");
      const at = text.indexOf("\r\n\r\n");
      if (at < 0) {
        fail(new Error("响应没有头"));
        return;
      }
      const head = new Map<string, string>();
      const status = Number(text.slice(0, at).split("\r\n")[0]?.split(" ")[1]);
      for (const line of text.slice(0, at).split("\r\n").slice(1)) {
        const colon = line.indexOf(":");
        if (colon > 0) head.set(line.slice(0, colon).trim(), line.slice(colon + 1).trim());
      }
      done({ status, headers: head, body: buffer.subarray(at + 4) });
    };
    socket.once("end", finish);
    socket.once("error", fail);
  });

const envelope = async (response: { body: Buffer }): Promise<Record<string, unknown>> =>
  JSON.parse(response.body.toString("utf8")) as Record<string, unknown>;

describe("服务", () => {
  let service: RunningService | null = null;
  const open = async (options: { repo?: string; idleTimeout?: number | null; entry?: "cli" | "serve-entry" } = {}): Promise<RunningService> => {
    service = await startService({
      repo: options.repo ?? repoOf("repo"),
      assets,
      ...(options.idleTimeout === undefined ? {} : { idleTimeout: options.idleTimeout }),
      ...(options.entry === undefined ? {} : { entry: options.entry }),
    });
    return service;
  };

  it("D01 握手与绑定：stdout 只有一行 JSON，字段与次序照合同，只绑 127.0.0.1", async () => {
    const running = await open();
    const handshake = running.handshake;
    expect(Object.keys(handshake)).toEqual(["themis_ui", "bootstrap", "origin", "control", "pid"]);
    expect(handshake.origin).toBe(`http://127.0.0.1:${running.port}`);
    expect(handshake.bootstrap).toBe(`http://127.0.0.1:${running.port}/bootstrap/${handshake.bootstrap.split("/").pop()}`);
    expect(handshake.control).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(handshake.pid).toBe(running.child.pid);
    const lines = running.stdout().split("\n").filter((line) => line.trim() !== "");
    expect(lines).toHaveLength(1);
    const index = await request(running.port, "GET", "/");
    expect(index.status).toBe(200);
  });

  it("D04 Host 校验：只认 127.0.0.1 与 localhost，引导地址没有被消耗", async () => {
    const running = await open();
    const port = running.port;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    for (const host of [`evil.example:${port}`, `127.0.0.1:${port + 1}`, "127.0.0.1", "localhost", `localhost.:${port}`]) {
      for (const target of ["/", "/api/v1/ping", path]) {
        const response = await request(port, "GET", target, [], undefined, host);
        expect(response.status, `${host} ${target}`).toBe(403);
      }
    }
    expect((await request(port, "GET", "/", [], undefined, `localhost:${port}`)).status).toBe(200);
    const accepted = await request(port, "GET", path);
    expect(accepted.status).toBe(302);
    expect(header(accepted, "location")).toBe("/");
    expect(header(accepted, "set-cookie")).toMatch(/^themis_session=[A-Za-z0-9_-]{43}; HttpOnly; SameSite=Strict; Path=\/$/u);
  });

  it("D02 会话与引导地址：401/404、Set-Cookie 逐字、只能用一次", async () => {
    const running = await open();
    const port = running.port;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    for (const method of ["GET", "POST"]) {
      const response = await request(port, method, "/api/v1/ping", [["Content-Type", "application/json"]]);
      expect(response.status, method).toBe(401);
      const body = await envelope(response);
      expect(body["ok"]).toBe(false);
      expect(body["data"]).toBeNull();
      expect(body["messages"]).toEqual(["ERROR: 未认证"]);
    }
    for (const value of ["themis_session=wrong", "themis_session=a; themis_session=b"]) {
      expect((await request(port, "GET", "/api/v1/ping", [["Cookie", value]])).status).toBe(401);
    }
    const accepted = await request(port, "GET", path);
    const cookie = cookieOf(accepted);
    expect(cookie).toMatch(/^themis_session=[A-Za-z0-9_-]{43}$/u);
    const again = await request(port, "GET", path);
    expect(again.status).toBe(404);
    expect(header(again, "set-cookie")).toBeNull();
    expect(again.body.toString("utf8")).toBe("引导地址无效\n");
    const unknown = await request(port, "GET", `/bootstrap/${"z".repeat(43)}`);
    expect(unknown.status).toBe(404);
    expect(unknown.body.equals(again.body)).toBe(true);
    const heads = (response: { headers: Map<string, string> }): Record<string, string> =>
      Object.fromEntries([...response.headers].filter(([key]) => !["date", "connection"].includes(key.toLowerCase())));
    expect(heads(again)).toEqual(heads(unknown));
    expect((await request(port, "GET", "/api/v1/nope")).status).toBe(401);
    expect((await request(port, "GET", "/api/v1/nope", [["Cookie", cookie]])).status).toBe(404);
    const ping = await request(port, "GET", "/api/v1/ping", [["Cookie", cookie]]);
    expect(ping.status).toBe(200);
    expect((await envelope(ping))["data"]).toEqual({ posts: 0 });
  });

  it("D05 CSRF：三种拒绝分别 403、403、415，处理函数没有运行", async () => {
    const running = await open();
    const port = running.port;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const cookie = cookieOf(await request(port, "GET", path));
    const base: [string, string][] = [
      ["Cookie", cookie],
      ["Origin", `http://127.0.0.1:${port}`],
      ["Content-Type", "application/json"],
    ];
    const post = (extra: readonly [string, string][]): Promise<{ status: number; body: Buffer }> =>
      request(port, "POST", "/api/v1/ping", [...base, ...extra], Buffer.from("{}", "utf8"));
    expect((await post([])).status).toBe(403); // 缺 X-Themis-UI
    expect((await post([["X-Themis-UI", "1"]])).status).toBe(200);
    expect((await post([["Origin", "https://evil.example"], ["X-Themis-UI", "1"]])).status).toBe(403);
    expect((await post([["X-Themis-UI", "1"]])).status).toBe(200);
    const noOrigin = base.filter(([name]) => name.toLowerCase() !== "origin");
    expect((await request(port, "POST", "/api/v1/ping", [...noOrigin, ["X-Themis-UI", "1"] as [string, string]], Buffer.from("{}", "utf8"))).status).toBe(403);
    for (const ctype of ["text/plain", "application/jsonp", "text/json"]) {
      const response = await post([["X-Themis-UI", "1"], ["Content-Type", ctype]]);
      expect(response.status, ctype).toBe(415);
    }
    // 三种拒绝下处理函数没有运行：posts 仍是上面两次成功的 2
    const ping = await request(port, "GET", "/api/v1/ping", [["Cookie", cookie]]);
    expect((await envelope(ping))["data"]).toEqual({ posts: 2 });
  });

  it("D16 只有 GET 与 POST：PUT、DELETE、OPTIONS、HEAD 都是 405 且带 Allow", async () => {
    const running = await open();
    for (const method of ["PUT", "DELETE", "OPTIONS", "HEAD"]) {
      const response = await request(running.port, method, "/");
      expect(response.status, method).toBe(405);
      expect(header(response, "allow")).toBe("GET, POST");
      expect(header(response, "content-security-policy")).toContain("default-src 'none'");
      expect(header(response, "access-control-allow-origin")).toBeNull();
      const api = await request(running.port, method, "/api/v1/ping");
      expect(api.status, `${method} api`).toBe(405);
    }
  });

  it("D09/D10 静态资源与只解码一次", async () => {
    const running = await open();
    const port = running.port;
    const index = await request(port, "GET", "/");
    expect(index.status).toBe(200);
    expect(header(index, "content-type")).toBe("text/html; charset=utf-8");
    expect(index.body.toString("utf8")).toContain("T015-INDEX-MARKER");
    expect(header(index, "cache-control")).toBe("no-cache");
    const js = await request(port, "GET", "/assets/app.js");
    expect(js.status).toBe(200);
    expect(header(js, "content-type")).toBe("text/javascript; charset=utf-8");
    for (const path of ["/missing.txt", "/notes.xyz", "/sub"]) {
      expect((await request(port, "GET", path)).status, path).toBe(404);
    }
    for (const [target, expected] of [
      ["/..%2f..%2fsecret.txt", 400],
      ["/%2e%2e%2fsecret.txt", 400],
      ["/x%5c..%5csecret.txt", 400],
      ["/secret%00.txt", 400],
      ["/%252e%252e%252fsecret.txt", 404],
    ] as const) {
      const response = await request(port, "GET", target);
      expect(response.status, target).toBe(expected);
      expect(response.body.toString("utf8"), target).not.toContain(canary);
      if (expected === 400) {
        expect(header(response, "content-security-policy")).toContain("default-src 'none'");
        expect(header(response, "x-content-type-options")).toBe("nosniff");
      }
    }
    for (const target of ["/../secret.txt", "/x\\..\\..\\secret.txt"]) {
      const response = await request(port, "GET", target);
      expect(response.body.toString("utf8"), target).not.toContain(canary);
    }
  });

  it("D11 请求体上限：分块 65537 提前 413、65536 收下、声明超限不读、坏正文 400 不回显", async () => {
    const running = await open();
    const port = running.port;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const cookie = cookieOf(await request(port, "GET", path));
    const base: [string, string][] = [
      ["Cookie", cookie],
      ["Origin", `http://127.0.0.1:${port}`],
      ["X-Themis-UI", "1"],
      ["Content-Type", "application/json"],
    ];
    const watched = await chunkedWatch(port, "POST", "/api/v1/ping", base, 65537 + 8192);
    expect(watched.response.status).toBe(413);
    expect(watched.early).toBe(true);
    expect(watched.sent).toBeLessThan(65537 + 8192);
    expect(watched.heldBack).toBe(true); // 停发时收到了头：结尾块没发，413 先于读完正文回来
    const pad = "x".repeat(65536 - '{"pad":""}'.length);
    const exact = await request(port, "POST", "/api/v1/ping", base, Buffer.from(`{"pad":"${pad}"}`, "utf8"));
    expect(exact.status).toBe(200);
    // 声明超过上限：一个字节也不读（只发头）
    const declared = await new Promise<{ status: number }>((done, fail) => {
      const net = require("node:net") as typeof import("node:net");
      const socket = net.connect(port, "127.0.0.1", () => {
        const lines = [
          "POST /api/v1/ping HTTP/1.1",
          `Host: 127.0.0.1:${port}`,
          "Connection: close",
          "Content-Length: 65537",
          ...base.map(([name, value]) => `${name}: ${value}`),
        ];
        socket.end(`${lines.join("\r\n")}\r\n\r\n`, "latin1");
      });
      socket.setTimeout(15_000, () => socket.destroy(new Error("超时")));
      let buffer = "";
      socket.on("data", (chunk: Buffer) => {
        buffer += chunk.toString("latin1");
        const at = buffer.indexOf("\r\n\r\n");
        if (at >= 0) {
          done({ status: Number(buffer.slice(0, at).split(" ")[1]) });
          socket.destroy();
        }
      });
      socket.once("error", fail);
    });
    expect(declared.status).toBe(413);
    for (const body of [Buffer.from([0xff, 0xfe, 0xff, 0xfe]), Buffer.from(`${bodyCanary} not json`, "utf8"), Buffer.alloc(0)]) {
      const response = await request(port, "POST", "/api/v1/ping", base, body);
      expect(response.status).toBe(400);
      if (body.byteLength > 0) expect(response.body.toString("utf8")).not.toContain(bodyCanary);
    }
  });

  it("D12 安全头矩阵：200、401、403、404、405、413、415、302、静态 200 与 404 都带同一套头", async () => {
    const running = await open();
    const port = running.port;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const accepted = await request(port, "GET", path);
    const cookie = cookieOf(accepted);
    const samples: [string, { status: number; headers: Map<string, string>; body: Buffer }][] = [
      ["302-bootstrap", accepted],
      ["200-ping", await request(port, "GET", "/api/v1/ping", [["Cookie", cookie]])],
      ["401-nocookie", await request(port, "GET", "/api/v1/ping")],
      ["403-badhost", await request(port, "GET", "/", [], undefined, `evil.example:${port}`)],
      ["404-api-noroute", await request(port, "GET", "/api/v1/nope", [["Cookie", cookie]])],
      ["405-put", await request(port, "PUT", "/")],
      ["static-200-index", await request(port, "GET", "/")],
      ["static-404-missing", await request(port, "GET", "/missing.txt")],
    ];
    const chunked = await chunkedWatch(
      port,
      "POST",
      "/api/v1/ping",
      [
        ["Origin", `http://127.0.0.1:${port}`],
        ["X-Themis-UI", "1"],
        ["Content-Type", "application/json"],
        ["Cookie", cookie],
      ] as [string, string][],
      65537 + 8192,
    );
    samples.push(["413-chunked", chunked.response]);
    // 声明 Content-Length 65537 的 413：一个字节也不读，与分块 413 带同一套安全头
    samples.push([
      "413-content-length",
      await declaredOverLimit(port, [["Cookie", cookie], ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]]),
    ]);
    samples.push(["415-content-type", await request(port, "POST", "/api/v1/ping", [["Cookie", cookie], ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "text/plain"]], Buffer.from("{}", "utf8"))]);
    samples.push(["403-control-no-token", await request(port, "POST", "/control/bootstrap", [["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]], Buffer.from("{}", "utf8"))]);
    for (const [label, response] of samples) {
      expect(header(response, "content-security-policy"), label).toBe(
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
      );
      expect(header(response, "x-content-type-options"), label).toBe("nosniff");
      expect(header(response, "referrer-policy"), label).toBe("no-referrer");
      expect([...response.headers.keys()].filter((name) => name.toLowerCase().startsWith("access-control")), label).toEqual([]);
      const cache = header(response, "cache-control");
      if (label.startsWith("static-200")) expect(cache, label).toBe("no-cache");
      else if (!label.startsWith("static-")) expect(cache, label).toBe("no-store");
    }
  });

  it("D06/D07 控制接口与限速", async () => {
    const running = await open();
    const port = running.port;
    const token = running.handshake.control;
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const cookie = cookieOf(await request(port, "GET", path));
    const ctrl = async (value: string | null, origin = `http://127.0.0.1:${port}`): Promise<{ status: number; body: Buffer; headers: Map<string, string> }> => {
      const headers: [string, string][] = [["Origin", origin], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]];
      if (value !== null) headers.push(["X-Themis-Control", value]);
      return request(port, "POST", "/control/bootstrap", headers, Buffer.from("{}", "utf8"));
    };
    const fresh = async (response: { body: Buffer }): Promise<string> => {
      const body = await envelope(response);
      const value = (body["data"] as Record<string, unknown>)["bootstrap"];
      return String(value).replace(`http://127.0.0.1:${port}`, "");
    };
    expect((await ctrl(null)).status).toBe(403);
    expect((await ctrl("wrong-token")).status).toBe(403);
    const onlyCookie = await request(
      port,
      "POST",
      "/control/bootstrap",
      [
        ["Cookie", cookie],
        ["Origin", `http://127.0.0.1:${port}`],
        ["X-Themis-UI", "1"],
        ["Content-Type", "application/json"],
      ] as [string, string][],
      Buffer.from("{}", "utf8"),
    );
    expect(onlyCookie.status).toBe(403);
    const ok = await ctrl(token);
    expect(ok.status).toBe(200);
    const freshPath = await fresh(ok);
    expect(freshPath).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
    expect((await request(port, "GET", "/api/v1/ping", [["Cookie", cookie]])).status).toBe(401);
    expect((await request(port, "GET", path)).status).toBe(404);
    const newCookie = cookieOf(await request(port, "GET", freshPath));
    expect(newCookie).not.toBe("");
    // Origin 是别的站点：403 且不计入限速
    for (let index = 0; index < 6; index += 1) {
      expect((await ctrl(token, "https://evil.example")).status).toBe(403);
    }
    expect((await ctrl(token)).status).toBe(200);
    // 连续 5 次失败锁 1 秒；锁定期内对的令牌也 429 且带 Retry-After
    for (let index = 0; index < 5; index += 1) {
      expect((await ctrl(`wrong-${index}`)).status).toBe(403);
    }
    const locked = await ctrl(token);
    expect(locked.status).toBe(429);
    expect(Number(header(locked, "retry-after"))).toBeGreaterThanOrEqual(1);
    await new Promise((done) => setTimeout(done, 1400));
    expect((await ctrl(token)).status).toBe(200);
  });

  it("D06 控制接口不读正文：只带对令牌就 200，豁免不外溢到 API", async () => {
    const running = await open();
    const port = running.port;
    const token = running.handshake.control;
    const bootstrapOf = async (response: { body: Buffer }): Promise<string> =>
      String(((await envelope(response))["data"] as Record<string, unknown>)["bootstrap"]).replace(`http://127.0.0.1:${port}`, "");
    let freshPath = "";
    // 只带对令牌：正文、Content-Type、X-Themis-UI、Origin、cookie 有没有都一律 200（穷举门，不读正文）
    const headerSets: [string, readonly [string, string][]][] = [
      ["什么都不带", [["X-Themis-Control", token]]],
      ["只带同源 Origin", [["X-Themis-Control", token], ["Origin", `http://127.0.0.1:${port}`]]],
      ["只带 X-Themis-UI", [["X-Themis-Control", token], ["X-Themis-UI", "1"]]],
      ["Content-Type 不是 JSON", [["X-Themis-Control", token], ["Content-Type", "text/plain"]]],
      ["Content-Type 是 jsonp", [["X-Themis-Control", token], ["Content-Type", "application/jsonp"]]],
      ["只带会话 cookie", [["X-Themis-Control", token], ["Cookie", "themis_session=nope"]]],
      ["全套头", [["X-Themis-Control", token], ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]]],
    ];
    for (const [label, headers] of headerSets) {
      const response = await requestNoBody(port, "POST", "/control/bootstrap", headers);
      expect(response.status, label).toBe(200);
      const fresh = await bootstrapOf(response);
      expect(fresh, label).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
      // 新给出的引导地址真的能建会话
      const accepted = await request(port, "GET", fresh);
      expect(accepted.status, label).toBe(302);
      expect(header(accepted, "set-cookie"), label).toMatch(/^themis_session=[A-Za-z0-9_-]{43}; HttpOnly; SameSite=Strict; Path=\/$/u);
    }
    // 带坏正文、空正文、合法 JSON 对象正文：一样 200（正文被忽略）
    for (const [label, body] of [
      ["坏 JSON", Buffer.from("not json", "utf8")],
      ["空正文", Buffer.alloc(0)],
      ["合法对象", Buffer.from('{"a":1}', "utf8")],
    ] as const) {
      const response = await request(port, "POST", "/control/bootstrap", [["X-Themis-Control", token]], body);
      expect(response.status, label).toBe(200);
      freshPath = await bootstrapOf(response);
      expect(freshPath, label).toMatch(/^\/bootstrap\/[A-Za-z0-9_-]{43}$/u);
    }
    // 豁免没有外溢到 API：POST /api/v1/ping 仍要 CSRF 三查与 JSON 正文（会话要在上面几次成功的换引导地址之后重新拿）
    const session = cookieOf(await request(port, "GET", freshPath));
    expect(session).not.toBe("");
    const apiBase: [string, string][] = [["Cookie", session], ["Origin", `http://127.0.0.1:${port}`], ["Content-Type", "application/json"]];
    expect((await request(port, "POST", "/api/v1/ping", apiBase, Buffer.from("{}", "utf8"))).status).toBe(403); // 缺 X-Themis-UI
    const noOrigin = apiBase.filter(([name]) => name.toLowerCase() !== "origin");
    expect((await request(port, "POST", "/api/v1/ping", [...noOrigin, ["X-Themis-UI", "1"]], Buffer.from("{}", "utf8"))).status).toBe(403);
    expect((await request(port, "POST", "/api/v1/ping", [...apiBase, ["X-Themis-UI", "1"], ["Content-Type", "text/plain"]], Buffer.from("{}", "utf8"))).status).toBe(415);
    // 门还是令牌：令牌错、不带令牌、只带 cookie 都是 403
    const full: [string, string][] = [["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]];
    expect((await request(port, "POST", "/control/bootstrap", full, Buffer.from("{}", "utf8"))).status).toBe(403);
    expect((await request(port, "POST", "/control/bootstrap", [...full, ["X-Themis-Control", "wrong"]], Buffer.from("{}", "utf8"))).status).toBe(403);
    // 握手行那个 nonce 已经被上面几次换引导地址作废了，用刚拿到的会话 cookie 证明门不看 cookie
    const cookie = session;
    expect(cookie).not.toBe("");
    expect((await request(port, "POST", "/control/bootstrap", [...full, ["Cookie", cookie]], Buffer.from("{}", "utf8"))).status).toBe(403);
    // 外来 Origin：403 且不计入限速（6 次之后对的令牌仍 200）
    for (let index = 0; index < 6; index += 1) {
      const foreign = await requestNoBody(port, "POST", "/control/bootstrap", [
        ["X-Themis-Control", token],
        ["Origin", "https://evil.example"],
      ]);
      expect(foreign.status).toBe(403);
    }
    const afterForeign = await requestNoBody(port, "POST", "/control/bootstrap", [["X-Themis-Control", token]]);
    expect(afterForeign.status).toBe(200);
    // 连续 5 次失败之后锁 1 秒：锁定期内对的令牌也 429 且带 Retry-After
    for (let index = 0; index < 5; index += 1) {
      const failed = await requestNoBody(port, "POST", "/control/bootstrap", [["X-Themis-Control", `wrong-${index}`]]);
      expect(failed.status).toBe(403);
    }
    const locked = await requestNoBody(port, "POST", "/control/bootstrap", [["X-Themis-Control", token]]);
    expect(locked.status).toBe(429);
    expect(Number(header(locked, "retry-after"))).toBeGreaterThanOrEqual(1);
  });

  it("D08 日志里没有令牌：stdout 只有握手一行，stderr 里没有令牌、cookie、nonce 与正文", async () => {
    const running = await open();
    const nonce = running.handshake.bootstrap.split("/").pop() ?? "";
    const path = `/bootstrap/${nonce}`;
    const cookie = cookieOf(await request(running.port, "GET", path));
    await request(running.port, "POST", "/api/v1/ping", [["Cookie", cookie], ["Origin", running.handshake.origin], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]], Buffer.from(`{"x":"${bodyCanary}"}`, "utf8"));
    const lines = running.stdout().split("\n").filter((line) => line.trim() !== "");
    expect(lines).toHaveLength(1);
    const rest = running.stdout().replace(lines[0] ?? "", "");
    for (const secret of [running.handshake.control, cookie, nonce, bodyCanary]) {
      expect(running.stderr()).not.toContain(secret);
      expect(rest).not.toContain(secret);
    }
  });

  it("D14 用法错误与已有服务：退出 2 提示原文、退出 1 报 pid 与端口", async () => {
    const repo = repoOf("repo-usage");
    const running = await open({ repo });
    const busy = await runBrief(cliArgv({ repo, assets }), 60_000);
    expect(busy.code).toBe(1);
    expect(busy.stderr).toMatch(/本仓库已有本机服务在运行（pid \d+，端口 \d+）/u);
    expect(busy.stderr).toContain(String(running.child.pid));
    expect(busy.stderr).toContain(String(running.port));
    expect(busy.stdout).toBe("");
    expect((await request(running.port, "GET", "/")).status).toBe(200);

    const plain = repoOf("repo-plain");
    const noDesktop = await runBrief(cliArgv({ repo: plain, assets, desktop: false }), 60_000);
    expect(noDesktop.code).toBe(2);
    expect(noDesktop.stderr).toBe("ERROR: 管理台只由桌面应用启动\n");
    expect(noDesktop.stdout).toBe("");

    const missing = await runBrief(cliArgv({ repo: plain, assets: join(dir, "missing-assets") }), 60_000);
    expect(missing.code).toBe(2);
    expect(missing.stderr.startsWith("ERROR: 找不到前端资源目录：")).toBe(true);
    expect(missing.stderr).toContain("missing-assets");
    expect(missing.stdout).toBe("");

    const zero = await runBrief(cliArgv({ repo: plain, assets, idleTimeout: 0 }), 60_000);
    expect(zero.code).toBe(2);
    expect(zero.stderr.startsWith("ERROR: --idle-timeout 必须是正整数：0")).toBe(true);
    expect(zero.stdout).toBe("");
  });

  it("D15 生命周期：--idle-timeout 1 空闲退出 0 且锁被清除；stdin EOF 退出 0", async () => {
    const idle = await open({ repo: repoOf("repo-idle"), idleTimeout: 1 });
    const outcome = await idle.stop(15_000);
    expect(outcome.timedOut).toBe(false);
    expect(outcome.code).toBe(0);
    expect(existsSync(join(repoOf("repo-idle"), ".agent", ".ui.lock"))).toBe(false);
    const eof = await open({ repo: repoOf("repo-eof") });
    const closed = await eof.stop(15_000);
    expect(closed.timedOut).toBe(false);
    expect(closed.code).toBe(0);
    expect(existsSync(join(repoOf("repo-eof"), ".agent", ".ui.lock"))).toBe(false);
    expect(eof.stdout().split("\n").filter((line) => line.trim() !== "")).toHaveLength(1);
  });

  it("D15 有请求就推迟空闲退出", async () => {
    const running = await open({ repo: repoOf("repo-defer"), idleTimeout: 3 });
    const start = Date.now();
    while (Date.now() - start < 4500) {
      if (running.child.exitCode !== null) break;
      await request(running.port, "GET", "/");
      await new Promise((done) => setTimeout(done, 600));
    }
    expect(running.child.exitCode).toBeNull();
    const outcome = await running.stop(15_000);
    expect(outcome.timedOut).toBe(false);
    expect(outcome.code).toBe(0);
    expect(existsSync(join(repoOf("repo-defer"), ".agent", ".ui.lock"))).toBe(false);
  });

  it("D03 nonce 的 60 秒：TTL 1.5 秒时过期拒绝、用过拒绝走同一个响应", async () => {
    const running = await open({ repo: repoOf("repo-ttl"), entry: "serve-entry" });
    const path = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const accepted = await request(running.port, "GET", path);
    expect(accepted.status).toBe(302);
    const used = await request(running.port, "GET", path);
    await new Promise((done) => setTimeout(done, 1700));
    const freshPath = `/bootstrap/${running.handshake.bootstrap.split("/").pop()}`;
    const expired = await request(running.port, "GET", freshPath);
    expect(used.status).toBe(404);
    expect(expired.status).toBe(404);
    expect(expired.body.equals(used.body)).toBe(true);
    const outcome = await running.stop(15_000);
    expect(outcome.code).toBe(0);
  });

  it("D15 锁：pid 已不在时接管，owner.json 缺失且锁目录新建时 busy", async () => {
    const stale = repoOf("repo-stale");
    const lock = join(stale, ".agent", ".ui.lock");
    mkdirSync(lock, { recursive: true });
    const busy = await runBrief(cliArgv({ repo: stale, assets }), 30_000);
    expect(busy.code).toBe(1);
    expect(busy.stderr).toContain("本仓库已有本机服务正在启动（.agent/.ui.lock）");
    rmSync(lock, { recursive: true, force: true });
    const dead = repoOf("repo-dead");
    mkdirSync(join(dead, ".agent", ".ui.lock"), { recursive: true });
    writeFileSync(join(dead, ".agent", ".ui.lock", "owner.json"), JSON.stringify({ pid: 999_999, port: 1, token: "stale", at: 1 }));
    const taken = await open({ repo: dead });
    expect(taken.port).toBeGreaterThan(0);
    const outcome = await taken.stop(15_000);
    expect(outcome.code).toBe(0);
    expect(existsSync(join(dead, ".agent", ".ui.lock"))).toBe(false);
  });

  it("D15 释放只删自己的锁：owner.json 的令牌被换掉时锁目录留着", async () => {
    const repo = repoOf("repo-tamper");
    const running = await open({ repo });
    const owner = join(repo, ".agent", ".ui.lock", "owner.json");
    const payload = JSON.parse(readFileSync(owner, "utf8")) as Record<string, unknown>;
    payload["token"] = "someone-else";
    writeFileSync(owner, JSON.stringify(payload));
    const outcome = await running.stop(15_000);
    expect(outcome.timedOut).toBe(false);
    expect(outcome.code).toBe(0);
    expect(existsSync(join(repo, ".agent", ".ui.lock"))).toBe(true);
    rmSync(join(repo, ".agent"), { recursive: true, force: true });
  });
});
