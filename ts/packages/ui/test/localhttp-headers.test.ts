// 安全响应头（桌面端 D12）：CSP 逐字、nosniff、no-referrer，no-store 与 no-cache 两种 Cache-Control，以及不开 CORS
// （Access-Control-* 一律删掉，加上通配来源也不行）。正文仍是原来的流，不缓冲。
import { describe, expect, it } from "vitest";
import { CSP, withSecurityHeaders } from "../src/localhttp/headers.ts";

describe("安全响应头", () => {
  it("CSP 逐字照合同", () => {
    expect(CSP).toBe(
      "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; " +
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    );
  });

  it("三个安全头恒定带上，Access-Control-* 被删掉", () => {
    const response = withSecurityHeaders(new Response("hi", { headers: { "access-control-allow-origin": "*" } }));
    expect(response.headers.get("content-security-policy")).toBe(CSP);
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(response.headers.get("access-control-allow-origin")).toBeNull();
    expect([...response.headers.keys()].filter((name) => name.startsWith("access-control"))).toEqual([]);
  });

  it("noStore 时带 Cache-Control: no-store；不传则不动 Cache-Control", () => {
    expect(withSecurityHeaders(new Response("x"), { noStore: true }).headers.get("cache-control")).toBe("no-store");
    expect(withSecurityHeaders(new Response("x")).headers.get("cache-control")).toBeNull();
    expect(withSecurityHeaders(new Response("x"), { cacheControl: "no-cache" }).headers.get("cache-control")).toBe("no-cache");
    const kept = withSecurityHeaders(new Response("x", { headers: { "cache-control": "max-age=5" } }));
    expect(kept.headers.get("cache-control")).toBe("max-age=5");
  });

  it("正文仍是原来的流：不缓冲，状态与状态文字照抄", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("流式正文"));
        controller.close();
      },
    });
    const response = withSecurityHeaders(new Response(stream, { status: 302, statusText: "Found" }), { noStore: true });
    expect(response.status).toBe(302);
    expect(response.statusText).toBe("Found");
    expect(response.body).not.toBeNull();
    expect(await response.text()).toBe("流式正文");
  });
});
