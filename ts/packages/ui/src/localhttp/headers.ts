// 安全响应头（桌面端设计第 7 版 §5.2、D4）：本机服务发给浏览器的每一份响应都带同一套头——CSP 逐字照合同，
// nosniff 防内容类型嗅探，no-referrer 不带路径（路径里可能有 nonce），Cross-Origin-Resource-Policy: same-origin 让别的
// 站点不能用 no-cors 的方式嵌入这些响应（静态资源不验会话，themistally-15 复核 T015 时建议）。不开 CORS：
// Access-Control-* 一律删掉。
// 新建一个 Response、正文仍用原来的流（不缓冲）：第 3 片的 SSE 要靠它。
/** 内容安全策略，逐字照合同（D4）。 */
export const CSP =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";

export interface SecurityHeaderOptions {
  /** API、引导、控制与所有错误响应：Cache-Control: no-store。 */
  readonly noStore?: boolean;
  /** 静态资源：Cache-Control: no-cache（要能拿到新构建，又不要缓存会话相关的响应）。 */
  readonly cacheControl?: string;
}

/** 给响应套上安全头；正文流原样交给新 Response。 */
export function withSecurityHeaders(response: Response, options: SecurityHeaderOptions = {}): Response {
  const headers = new Headers(response.headers);
  for (const name of [...headers.keys()]) {
    if (name.toLowerCase().startsWith("access-control")) headers.delete(name);
  }
  headers.set("content-security-policy", CSP);
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "no-referrer");
  headers.set("cross-origin-resource-policy", "same-origin");
  if (options.cacheControl !== undefined) headers.set("cache-control", options.cacheControl);
  else if (options.noStore === true) headers.set("cache-control", "no-store");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
