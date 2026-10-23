// 本机 HTTP 的安全基线（桌面端设计第 7 版 §5.2、T8）。这里只许导入 node:*、@themis/base/* 与 localhttp 内部的
// 相对路径（源码卫生测试 localhttpViolations 强制）：迁移第 ③d 步把整个目录搬进 @themis/base/localhttp 时
// 只是机械地移动文件，一个字样都不用改。Bun 的全局对象一律不碰：起服务的那一层在 src/server.ts。
export { AccessLog, ACCESS_LOG_MAX, type AccessEntry, ROUTE_NAME_RE } from "./accesslog.ts";
export { MAX_BODY_BYTES, readBodyLimited, readJsonBody, type BodyResult, type JsonResult } from "./body.ts";
export { SESSION_COOKIE, readSessionCookie, sessionSetCookie } from "./cookie.ts";
export {
  CONTROL_HEADER,
  CONTROL_LOCK_BASE_MS,
  CONTROL_LOCK_MAX_MS,
  CONTROL_MAX_FAILURES,
  ControlGate,
  type ControlVerdict,
} from "./control.ts";
export {
  type Rejection,
  UI_HEADER,
  allowedHost,
  controlOriginAllowed,
  csrfCheck,
  hostAllowed,
  methodAllowed,
  originAllowed,
  originOf,
} from "./guards.ts";
export { CSP, type SecurityHeaderOptions, withSecurityHeaders } from "./headers.ts";
export {
  BootstrapNonces,
  NONCE_TTL_MS,
  Sessions,
  bootstrapAccepted,
  bootstrapRejected,
} from "./session.ts";
export { TOKEN_BYTES, constantTimeEqual, randomToken } from "./tokens.ts";
