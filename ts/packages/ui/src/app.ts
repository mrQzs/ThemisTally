// 请求管线（桌面端设计第 7 版 §5.2、D4、T17）：把筛查、派发、安全头与访问记录按固定次序串起来。次序是安全边界的一部
// 分——Host 先于一切（防 DNS 重绑定），方法先于会话（PUT 不带 cookie 也是 405，不泄露资源在不在），会话默认必须
// 验证：先 findRoute，命中且标了 public（一次性引导地址、控制接口）才不验，其余命中且路径以 /api/ 开头就要会话，
// 没有就 401；没命中且路径以 /api/ 开头也 401（不存在的路径也不泄露它在不在），没命中且不是 /api/ 才是静态资源
// （不验会话，照旧）。会话检查排在 POST 的 CSRF 与读正文之前。最后才交给处理函数，套安全头、记访问记录。这里照
// WHATWG 的 Request/Response 写，不起服务也能测（app.test.ts 直接调 app.fetch）。
import { readFile } from "node:fs/promises";
import {
  AccessLog,
  BootstrapNonces,
  ControlGate,
  Sessions,
  controlOriginAllowed,
  csrfCheck,
  hostAllowed,
  methodAllowed,
  readJsonBody,
  readSessionCookie,
  withSecurityHeaders,
} from "./localhttp/index.ts";
import { NONCE_TTL_MS } from "./localhttp/session.ts";
import { errorResponse } from "./envelope.ts";
import { findRoute, type Route, type RouteState } from "./routes.ts";
import { resolveAsset } from "./static.ts";

export interface AppOptions {
  /** 监听端口（Host 校验与 origin 都要用它）。 */
  readonly port: number;
  /** 前端资源目录（--assets）。 */
  readonly assets: string;
  /** 控制令牌（握手行交给外壳）。 */
  readonly controlToken: string;
  /** 测试用的时钟。 */
  readonly now?: (() => number) | undefined;
  /** 测试用的 nonce 有效期。 */
  readonly nonceTtlMs?: number | undefined;
  /** 第 2、3 片加路由的接缝。 */
  readonly extraRoutes?: readonly Route[] | undefined;
  /** 有请求时调一次（服务层用它推迟空闲退出）。 */
  readonly onActivity?: (() => void) | undefined;
}

export interface App {
  /** 处理一个请求（WHATWG 的 Request 进、Response 出）。 */
  fetch(request: Request): Promise<Response>;
  /** 发一个引导地址用的 nonce。 */
  issueBootstrap(): string;
  /** 本机服务的源，http://127.0.0.1:<port>。 */
  readonly origin: string;
  readonly accessLog: AccessLog;
  /** 进行中的请求数（有请求时不算空闲）。 */
  inflight(): number;
}

/** 静态资源那一类的 reason 到错误提示的映射：只给类别，不给路径。 */
function staticMessage(reason: string): string {
  if (reason === "not-found") return "找不到这个资源";
  if (reason === "directory") return "找不到这个资源";
  if (reason === "type-not-allowed") return "找不到这个资源";
  if (reason === "bad-encoding") return "请求被拒绝";
  return "请求被拒绝";
}

/** 建一个应用：状态全在内存里，进程结束即丢。 */
export function createApp(options: AppOptions): App {
  const now = options.now ?? Date.now;
  const origin = `http://127.0.0.1:${options.port}`;
  const nonces = new BootstrapNonces(now, options.nonceTtlMs ?? NONCE_TTL_MS);
  const sessions = new Sessions();
  const control = new ControlGate(options.controlToken, now);
  const accessLog = new AccessLog();
  const state: RouteState = { origin, sessions, nonces, control, posts: { value: 0 } };
  const extra = options.extraRoutes ?? [];
  let inflightCount = 0;

  const serveStatic = async (
    pathname: string,
    respond: (name: string, response: Response, cache?: "no-store" | "no-cache") => Response,
  ): Promise<Response> => {
    const result = resolveAsset(options.assets, pathname);
    if (!result.ok) return respond("static", errorResponse(result.status, staticMessage(result.reason)));
    const bytes = await readFile(result.path);
    return respond("static", new Response(bytes, { headers: { "content-type": result.contentType } }), "no-cache");
  };

  const fetch = async (request: Request): Promise<Response> => {
    const startedAt = Date.now();
    let routeName = "unmatched";
    const respond = (name: string, response: Response, cache: "no-store" | "no-cache" = "no-store"): Response => {
      const secured = withSecurityHeaders(response, cache === "no-cache" ? { cacheControl: "no-cache" } : { noStore: true });
      accessLog.record(name, secured.status, Date.now() - startedAt);
      return secured;
    };
    inflightCount += 1;
    options.onActivity?.();
    try {
      const url = new URL(request.url);
      const pathname = url.pathname;
      const method = request.method.toUpperCase();
      // 1. Host 不对：对所有路径一律 403（静态、引导、控制都不例外）
      if (!hostAllowed(request.headers, options.port)) {
        return respond("rejected", errorResponse(403, "请求被拒绝"));
      }
      // 2. 方法白名单
      if (!methodAllowed(method)) {
        const response = errorResponse(405, "只支持 GET 与 POST");
        response.headers.set("allow", "GET, POST");
        return respond("rejected", response);
      }
      // 3. 会话默认必须验证（T17）：先 findRoute，public 的不验，其余 /api/ 要会话，/api/ 下没命中的也 401
      const match = findRoute(method, pathname, extra);
      if (match === null) {
        if (pathname.startsWith("/api/")) {
          // 不存在的 /api/ 路径：没有会话 401（不泄露它在不在），有会话才 404
          if (!sessions.valid(readSessionCookie(request.headers))) return respond("unmatched", errorResponse(401, "未认证"));
          return respond("unmatched", errorResponse(404, "没有这个接口"));
        }
        return await serveStatic(pathname, respond);
      }
      if (match.route.public !== true && pathname.startsWith("/api/")) {
        if (!sessions.valid(readSessionCookie(request.headers))) return respond("unmatched", errorResponse(401, "未认证"));
      }
      routeName = match.route.name;
      if (match.route.name === "control.bootstrap" && !controlOriginAllowed(request.headers)) {
        return respond(routeName, errorResponse(403, "请求被拒绝"));
      }
      // 4. POST：CSRF 三查，再读正文（超限 413、坏正文 400）。control.bootstrap 不在这两步里——它的门是穷举的
      // （Host、controlOriginAllowed、ControlGate 三道），不看正文也不看 CSRF 头：外壳发请求时带不带正文、
      // Content-Type、X-Themis-UI 都没有核实过（站主记录 F9），豁免之后两种外壳都能 reauth。
      let body: unknown;
      if (method === "POST" && match.route.name !== "control.bootstrap") {
        const rejection = csrfCheck(request);
        if (rejection !== null) return respond(routeName, errorResponse(rejection.status, rejection.message));
        const parsed = await readJsonBody(request);
        if (!parsed.ok) {
          const message = parsed.status === 413 ? "请求体超过 64 KiB" : "请求体不是合法的 JSON";
          return respond(routeName, errorResponse(parsed.status, message));
        }
        body = parsed.value;
      }
      // 5. 处理函数（API、引导、控制与错误都带 no-store）
      const response = await match.route.handle(state, match.params, { request, body });
      return respond(routeName, response);
    } catch (error) {
      process.stderr.write(`处理请求时出错（${routeName}）：${error instanceof Error ? error.name : "未知错误"}\n`);
      return respond(routeName, errorResponse(500, "服务内部错误"));
    } finally {
      inflightCount -= 1;
    }
  };

  return {
    fetch,
    issueBootstrap: () => nonces.issue(),
    origin,
    accessLog,
    inflight: () => inflightCount,
  };
}