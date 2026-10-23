// 令牌、一次性引导地址与会话（桌面端 T7a、T7c 的纯函数部分）：随机令牌的形状、恒定时间比较的同一条路、nonce 的
// 一次性与 60 秒、会话的 null 与空串、cookie 的逐字与重复拒绝、两种拒绝的同一个响应。
import { describe, expect, it } from "vitest";
import { BootstrapNonces, NONCE_TTL_MS, Sessions, bootstrapAccepted, bootstrapRejected } from "../src/localhttp/session.ts";
import { constantTimeEqual, randomToken } from "../src/localhttp/tokens.ts";
import { SESSION_COOKIE, readSessionCookie, sessionSetCookie } from "../src/localhttp/cookie.ts";
import { TOKEN_BYTES } from "../src/localhttp/tokens.ts";

describe("随机令牌", () => {
  it("32 字节随机数的 base64url：43 个字符，没有填充，两次不一样", () => {
    const one = randomToken();
    const two = randomToken();
    expect(one).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(two).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(one).not.toBe(two);
    expect(TOKEN_BYTES).toBe(32);
  });
});

describe("恒定时间比较", () => {
  const expected = randomToken();

  it("相同为 true，长度不同与缺头都不抛错、都为 false", () => {
    expect(constantTimeEqual(expected, expected)).toBe(true);
    expect(constantTimeEqual("", expected)).toBe(false);
    expect(constantTimeEqual("x", expected)).toBe(false);
    expect(constantTimeEqual(`${expected}x`, expected)).toBe(false);
    expect(constantTimeEqual(null, expected)).toBe(false);
    expect(constantTimeEqual(expected, "")).toBe(false);
  });
});

describe("一次性的引导地址", () => {
  it("只能用一次：第二次（以及从不存在的）都 false", () => {
    const nonces = new BootstrapNonces(() => 0);
    const nonce = nonces.issue();
    expect(nonces.consume(nonce)).toBe(true);
    expect(nonces.consume(nonce)).toBe(false);
    expect(nonces.consume("/bootstrap/nope")).toBe(false);
  });

  it("59999 毫秒可用、60000 毫秒拒绝", () => {
    let now = 1_000;
    const nonces = new BootstrapNonces(() => now);
    const nonce = nonces.issue();
    now += NONCE_TTL_MS - 1;
    expect(nonces.consume(nonce)).toBe(true);
    now = 5_000;
    const other = nonces.issue();
    now += NONCE_TTL_MS;
    expect(nonces.consume(other)).toBe(false);
    expect(NONCE_TTL_MS).toBe(60_000);
  });

  it("revokeAll 之后全部作废；过期项会被顺手清理", () => {
    let now = 0;
    const nonces = new BootstrapNonces(() => now);
    const first = nonces.issue();
    now += 10;
    const second = nonces.issue();
    nonces.revokeAll();
    expect(nonces.consume(first)).toBe(false);
    expect(nonces.consume(second)).toBe(false);
    now += NONCE_TTL_MS * 2;
    const third = nonces.issue();
    expect(nonces.consume(third)).toBe(true);
  });
});

describe("会话", () => {
  it("建出来的令牌有效；null 与空串无效；revokeAll 之后失效", () => {
    const sessions = new Sessions();
    const token = sessions.create();
    expect(sessions.valid(token)).toBe(true);
    expect(sessions.valid(null)).toBe(false);
    expect(sessions.valid("")).toBe(false);
    expect(sessions.valid("wrong")).toBe(false);
    sessions.revokeAll();
    expect(sessions.valid(token)).toBe(false);
  });
});

describe("会话 cookie", () => {
  it("Set-Cookie 逐字照合同", () => {
    expect(sessionSetCookie("abc")).toBe("themis_session=abc; HttpOnly; SameSite=Strict; Path=/");
    expect(SESSION_COOKIE).toBe("themis_session");
  });

  it("Cookie 头里恰好有一个才返回它的值；没有、重复、别的名字都返回 null", () => {
    const one = (value: string): Headers => new Headers({ cookie: value });
    expect(readSessionCookie(one("themis_session=abc"))).toBe("abc");
    expect(readSessionCookie(one("other=1; themis_session=abc"))).toBe("abc");
    expect(readSessionCookie(one("themis_session=a; themis_session=b"))).toBeNull();
    expect(readSessionCookie(one("other=1"))).toBeNull();
    expect(readSessionCookie(new Headers())).toBeNull();
  });
});

describe("引导地址的两种结局", () => {
  it("成功：302 到 /，Set-Cookie 逐字", async () => {
    const response = bootstrapAccepted("tok");
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("/");
    expect(response.headers.get("set-cookie")).toBe("themis_session=tok; HttpOnly; SameSite=Strict; Path=/");
  });

  it("失败：404、纯文本、正文固定", async () => {
    const response = bootstrapRejected();
    expect(response.status).toBe(404);
    expect(response.headers.get("content-type")).toBe("text/plain; charset=utf-8");
    expect(await response.text()).toBe("引导地址无效\n");
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
