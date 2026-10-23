// Host、Origin、CSRF 与控制接口的 Origin（桌面端 D4、D5 的纯函数部分）：Host 整串相等、方法白名单、CSRF 三查的
// 次序、控制接口有无 Origin 都放行。
import { describe, expect, it } from "vitest";
import {
  controlOriginAllowed,
  csrfCheck,
  hostAllowed,
  methodAllowed,
  originAllowed,
  UI_HEADER,
} from "../src/localhttp/guards.ts";

const PORT = 53123;
const ORIGIN = `http://127.0.0.1:${PORT}`;

const head = (entries: Record<string, string>): Headers => new Headers(entries);

describe("方法白名单", () => {
  it("只认 GET 与 POST：PUT、DELETE、OPTIONS、HEAD 与小写一律不认", () => {
    expect(methodAllowed("GET")).toBe(true);
    expect(methodAllowed("POST")).toBe(true);
    for (const method of ["PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "get", ""]) {
      expect(methodAllowed(method), method).toBe(false);
    }
  });
});

describe("Host 校验", () => {
  it("只认 127.0.0.1:<port> 与 localhost:<port>", () => {
    expect(hostAllowed(head({ host: `127.0.0.1:${PORT}` }), PORT)).toBe(true);
    expect(hostAllowed(head({ host: `localhost:${PORT}` }), PORT)).toBe(true);
    expect(hostAllowed(head({ host: `LOCALHOST:${PORT}` }), PORT)).toBe(true);
    expect(hostAllowed(head({ host: `localhost:${PORT + 1}` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `127.0.0.1:${PORT + 1}` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: "127.0.0.1" }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: "localhost" }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `localhost.:${PORT}` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `localhost:${PORT}.` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `[::1]:${PORT}` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `evil.example:${PORT}` }), PORT)).toBe(false);
    expect(hostAllowed(head({ host: `127.0.0.1:${PORT}, 127.0.0.1:${PORT}` }), PORT)).toBe(false);
    expect(hostAllowed(new Headers(), PORT)).toBe(false);
  });
});

describe("Origin 校验", () => {
  it("必须等于 http:// 加上已经过校验的 Host", () => {
    expect(originAllowed(head({ host: `127.0.0.1:${PORT}`, origin: ORIGIN }))).toBe(true);
    expect(originAllowed(head({ host: `localhost:${PORT}`, origin: `http://localhost:${PORT}` }))).toBe(true);
    expect(originAllowed(head({ host: `127.0.0.1:${PORT}`, origin: "null" }))).toBe(false);
    expect(originAllowed(head({ host: `127.0.0.1:${PORT}`, origin: `http://127.0.0.1:${PORT + 1}` }))).toBe(false);
    expect(originAllowed(head({ host: `127.0.0.1:${PORT}`, origin: "https://evil.example" }))).toBe(false);
    expect(originAllowed(head({ host: `127.0.0.1:${PORT}` }))).toBe(false);
    expect(originAllowed(head({ origin: ORIGIN }))).toBe(false);
    expect(originAllowed(head({ host: "127.0.0.1", origin: "http://127.0.0.1" }))).toBe(false);
  });

  it("控制接口：没有 Origin 或同源都放行，别的站点拒绝", () => {
    expect(controlOriginAllowed(new Headers())).toBe(true);
    expect(controlOriginAllowed(head({ host: `127.0.0.1:${PORT}`, origin: ORIGIN }))).toBe(true);
    expect(controlOriginAllowed(head({ host: `127.0.0.1:${PORT}`, origin: "https://evil.example" }))).toBe(false);
  });
});

describe("CSRF 三查", () => {
  const post = (entries: Record<string, string>): Request =>
    new Request(`http://127.0.0.1:${PORT}/api/v1/ping`, { method: "POST", headers: entries, body: "{}" });
  const good: Record<string, string> = {
    host: `127.0.0.1:${PORT}`,
    origin: ORIGIN,
    [UI_HEADER]: "1",
    "content-type": "application/json",
  };

  it("合格请求不拒绝", () => {
    expect(csrfCheck(post(good))).toBeNull();
    expect(csrfCheck(post({ ...good, "content-type": "application/json; charset=utf-8" }))).toBeNull();
    expect(csrfCheck(post({ ...good, "content-type": "APPLICATION/JSON" }))).toBeNull();
  });

  it("Origin 不对或缺 403（优先于其余两项）", () => {
    expect(csrfCheck(post({ ...good, origin: "https://evil.example" }))).toEqual({ status: 403, message: "请求被拒绝" });
    expect(csrfCheck(post({ ...good, origin: "https://evil.example", [UI_HEADER]: "0", "content-type": "text/plain" }))).toEqual({
      status: 403,
      message: "请求被拒绝",
    });
    const missing = { ...good } as Record<string, string>;
    delete missing["origin"];
    expect(csrfCheck(post(missing))).toEqual({ status: 403, message: "请求被拒绝" });
  });

  it("X-Themis-UI 不是 1 则 403（优先于 Content-Type）", () => {
    expect(csrfCheck(post({ ...good, [UI_HEADER]: "0" }))).toEqual({ status: 403, message: "请求被拒绝" });
    expect(csrfCheck(post({ ...good, [UI_HEADER]: "0", "content-type": "text/plain" }))).toEqual({
      status: 403,
      message: "请求被拒绝",
    });
    const missing = { ...good } as Record<string, string>;
    delete missing[UI_HEADER];
    expect(csrfCheck(post(missing))).toEqual({ status: 403, message: "请求被拒绝" });
  });

  it("只认 application/json：jsonp、text/json、缺 Content-Type 都是 415", () => {
    expect(csrfCheck(post({ ...good, "content-type": "application/jsonp" }))).toEqual({
      status: 415,
      message: "请求体只收 application/json",
    });
    expect(csrfCheck(post({ ...good, "content-type": "text/json" }))?.status).toBe(415);
    const missing = { ...good } as Record<string, string>;
    delete missing["content-type"];
    expect(csrfCheck(post(missing))?.status).toBe(415);
  });
});
