// 访问记录（桌面端 T7b）：只有路由名、状态码与耗时三项，只在内存里；不像名字的路由名记成 invalid-route-name，
// 所以含 nonce 的引导地址、请求正文与 cookie 都进不了记录。
import { describe, expect, it } from "vitest";
import { ACCESS_LOG_MAX, AccessLog } from "../src/localhttp/accesslog.ts";

describe("访问记录", () => {
  it("常量照合同", () => {
    expect(ACCESS_LOG_MAX).toBe(1000);
  });

  it("每条只有路由名、状态码与耗时", () => {
    const log = new AccessLog();
    log.record("api.ping.get", 200, 3);
    log.record("bootstrap", 404, 1);
    expect(log.entries()).toEqual([
      { route: "api.ping.get", status: 200, ms: 3 },
      { route: "bootstrap", status: 404, ms: 1 },
    ]);
  });

  it("路由名不符合 ^[a-z][a-z0-9.-]*$ 记成 invalid-route-name", () => {
    const log = new AccessLog();
    for (const route of ["/bootstrap/-65GN93ffqI3BcI0R4ngHpMdw3vp6T6PDJEFZMiUoh0", "api/v1/ping", "API.ping", " posts", ""]) {
      log.record(route, 200, 0);
    }
    expect(log.entries().every((entry) => entry.route === "invalid-route-name")).toBe(true);
  });

  it("合法的路由名原样记下", () => {
    const log = new AccessLog();
    log.record("api.ping.get", 200, 0);
    log.record("control.bootstrap", 200, 0);
    log.record("static", 200, 0);
    log.record("a-b.c", 200, 0);
    expect(log.entries().map((entry) => entry.route)).toEqual(["api.ping.get", "control.bootstrap", "static", "a-b.c"]);
  });

  it("只留在内存里：超出上限丢最旧的，entries 是副本", () => {
    const log = new AccessLog(3);
    for (const status of [1, 2, 3, 4]) log.record("api.ping.get", status, 0);
    expect(log.entries().map((entry) => entry.status)).toEqual([2, 3, 4]);
    const first = log.entries();
    log.record("api.ping.get", 5, 0);
    expect(first).toHaveLength(3);
  });
});
