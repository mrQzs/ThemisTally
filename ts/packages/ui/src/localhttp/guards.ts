// 请求的第一道筛查（桌面端设计第 7 版 §5.2、D4）：方法白名单、Host 校验（防 DNS 重绑定）、Origin 与 CSRF
// 校验（防别的站点借外壳的浏览器发写请求）。都不碰 Bun 的全局对象，照 WHATWG 的 Headers/Request 写，
// 迁移第 ③d 步整体搬进 @themis/base 时不用改。这里只判「过不过」，错误响应的形状由服务层统一成错误信封。
/** 前端自报身份的请求头（CSRF 的一半：网页发不出自定义头）。 */
export const UI_HEADER = "x-themis-ui";

/** 只认 GET 与 POST：PUT、DELETE、OPTIONS、HEAD 一律 405（照 D4；HEAD 也不例外是规划端代定的，T015 的事实核实）。 */
export function methodAllowed(method: string): boolean {
  return method === "GET" || method === "POST";
}

/** 本机服务认得的 Host：ASCII 小写之后整串等于 127.0.0.1:<port> 或 localhost:<port>。 */
export function allowedHost(port: number, host: string): string | null {
  const value = host.trim().toLowerCase();
  return value === `127.0.0.1:${port}` || value === `localhost:${port}` ? value : null;
}

/** Host 必须整串（ASCII 小写之后）等于 127.0.0.1:<port> 或 localhost:<port>；缺 Host 也不认。 */
export function hostAllowed(headers: Headers, port: number): boolean {
  const host = headers.get("host");
  return host !== null && allowedHost(port, host) !== null;
}

/** 本机服务的源：Host 校验过之后的 http://<host>；Host 不在认得的集合里时为 null。 */
export function originOf(headers: Headers): string | null {
  const host = headers.get("host");
  if (host === null) return null;
  const value = host.trim().toLowerCase();
  const at = value.lastIndexOf(":");
  if (at < 0) return null;
  const name = value.slice(0, at);
  const port = Number(value.slice(at + 1));
  if (name !== "127.0.0.1" && name !== "localhost") return null;
  if (!Number.isInteger(port) || port <= 0 || port > 65535) return null;
  return `http://${value}`;
}

/** Origin 必须等于 http:// 加上已经过校验的 Host：缺 Origin、字面 null、端口不同都不认。 */
export function originAllowed(headers: Headers): boolean {
  const origin = headers.get("origin");
  const expected = originOf(headers);
  if (origin === null || origin === "" || origin === "null" || expected === null) return false;
  return origin.toLowerCase() === expected;
}

/** 控制接口的 Origin：没有 Origin 或同源都放行（外壳两种情况都有），别的站点拒绝（不计入限速）。 */
export function controlOriginAllowed(headers: Headers): boolean {
  const origin = headers.get("origin");
  if (origin === null || origin === "" || origin === "null") return true;
  return originAllowed(headers);
}

/** 一次拒绝：状态码加一句不给攻击者反馈的说明（正文由服务层统一成错误信封）。 */
export interface Rejection {
  readonly status: 403 | 415;
  readonly message: string;
}

/** 写请求的 CSRF 三查，次序固定：Origin 不对 403，X-Themis-UI 不是 1 则 403，媒体类型不是 JSON 则 415。 */
export function csrfCheck(request: Request): Rejection | null {
  if (!originAllowed(request.headers)) return { status: 403, message: "请求被拒绝" };
  if (request.headers.get(UI_HEADER) !== "1") return { status: 403, message: "请求被拒绝" };
  const contentType = request.headers.get("content-type") ?? "";
  const media = (contentType.split(";")[0] ?? "").trim().toLowerCase();
  if (media !== "application/json") return { status: 415, message: "请求体只收 application/json" };
  return null;
}
