// 会话 cookie 的读写（桌面端设计第 7 版 §5.2）：名字固定 themis_session，属性逐字固定——HttpOnly 让网页读不到、
// SameSite=Strict 让别的站点带不上、Path=/ 覆盖整个服务。没有 Max-Age（会话只在内存里，进程结束即丢），
// 也没有 Secure（只绑 127.0.0.1 的纯 HTTP，加了 Secure 浏览器根本不发）。
export const SESSION_COOKIE = "themis_session";

/** Set-Cookie 的那一串，逐字照合同（D4）。 */
export function sessionSetCookie(token: string): string {
  return `${SESSION_COOKIE}=${token}; HttpOnly; SameSite=Strict; Path=/`;
}

/** 只在 Cookie 头里恰好有一个 themis_session 时返回它的值；没有、重复、空名都返回 null。 */
export function readSessionCookie(headers: Headers): string | null {
  const header = headers.get("cookie");
  if (header === null) return null;
  let found: string | null = null;
  for (const part of header.split(";")) {
    const at = part.indexOf("=");
    if (at < 0) continue;
    if (part.slice(0, at).trim() !== SESSION_COOKIE) continue;
    if (found !== null) return null; // 重复：不猜哪一个
    found = part.slice(at + 1).trim();
  }
  return found;
}
