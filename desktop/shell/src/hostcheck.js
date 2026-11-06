"use strict";

const fs = require("node:fs");
const path = require("node:path");

// 一次性页面地址的形状，照 ts/packages/ui/src/secretentry.ts 的 PAGE_URL_RE 与 PORT_MIN/PORT_MAX：
// 127.0.0.1 锚定、端口 1 到 5 位数字、令牌恰好 32 个 base64url 字符（两头锚定、整串匹配）
const SECRET_PAGE_RE = /^http:\/\/127\.0\.0\.1:(\d{1,5})\/([A-Za-z0-9_-]{32})$/u;
const PORT_MIN = 1;
const PORT_MAX = 65535;

// 作业号的形状，照 ts/packages/ui/src/jobs.ts 的 JOB_ID_RE：43 个 base64url 字符
const JOB_ID_RE = /^[A-Za-z0-9_-]{43}$/u;

// 外链先过正则再交给 new URL：new URL 会吞掉首尾空白与内部换行，也会把 http:\\x 解析成 http://x/，
// 而打开时传出去的是原串——校验与打开必须看同一个东西
const EXTERNAL_URL_RE = /^https?:\/\/[^\s]+$/i;

// NUL 与 0x1f 以下、DEL：正则的 \s 盖不住这些，单独扫一遍（两个校验共用）
const CONTROL_LIMIT = 0x1f;
const DELETE_CODE = 0x7f;

// 通知文案表：键用 Map 查，constructor、__proto__、toString 这类键不会命中
const NOTIFY_TEXT = new Map([
  ["attempt-finished", { title: "ThemisTally", body: "attempt 已结束" }],
  ["awaiting-review", { title: "ThemisTally", body: "有 attempt 等待验收" }],
]);

function hasControlChar(text) {
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code <= CONTROL_LIMIT || code === DELETE_CODE) return true;
  }
  return false;
}

function isSecretPageUrl(url) {
  if (typeof url !== "string") return false;
  const match = SECRET_PAGE_RE.exec(url);
  if (match === null) return false;
  const port = Number(match[1]);
  return port >= PORT_MIN && port <= PORT_MAX;
}

function isJobId(id) {
  return typeof id === "string" && JOB_ID_RE.test(id);
}

function isExternalUrl(url) {
  if (typeof url !== "string") return false;
  if (!EXTERNAL_URL_RE.test(url)) return false;
  if (hasControlChar(url)) return false;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:";
}

function isRevealLiteralOk(relPath) {
  if (typeof relPath !== "string" || relPath.length === 0) return false;
  if (hasControlChar(relPath)) return false;
  if (relPath.includes("\\")) return false;
  if (relPath.includes(":")) return false;
  const segments = relPath.split("/");
  for (const segment of segments) {
    if (segment.length === 0) return false;
    if (segment === "." || segment === "..") return false;
    if (segment.endsWith(".")) return false;
    if (segment.endsWith(" ")) return false;
  }
  return true;
}

// full 是不是确实在 root 里面（不是 root 本身，也不是它的上级），照 ts/packages/ui/src/static.ts 的 isWithin：
// 用 path.relative 逐段比，不用字符串前缀——..foo 这样的合法文件名会被前缀比较误判
function isWithin(root, full) {
  const rel = path.relative(path.resolve(root), path.resolve(full));
  return rel !== "" && !rel.startsWith(`..${path.sep}`) && rel !== ".." && !path.isAbsolute(rel);
}

// relPath 相对 <仓库>/.agent/。任何一步抛错都按拒绝处理
function resolveReveal(options) {
  const {
    repo,
    relPath,
    realpath = fs.realpathSync.native,
    stat = fs.statSync,
  } = options;
  if (!isRevealLiteralOk(relPath)) return null;
  let root;
  let full;
  try {
    root = realpath(path.join(repo, ".agent"));
    full = realpath(path.join(root, relPath));
  } catch {
    return null;
  }
  if (!isWithin(root, full)) return null;
  let info;
  try {
    info = stat(full);
  } catch {
    return null;
  }
  if (!info.isFile() && !info.isDirectory()) return null;
  return full;
}

// 滑动窗口限速：被拒的调用不计数（不占名额），第 1 次之后正好 windowMs 毫秒放行
function createRateLimiter(options) {
  const { max = 3, windowMs = 60000, now = Date.now } = options || {};
  const stamps = [];
  return {
    take() {
      const at = now();
      while (stamps.length > 0 && at - stamps[0] >= windowMs) {
        stamps.shift();
      }
      if (stamps.length >= max) return false;
      stamps.push(at);
      return true;
    },
  };
}

module.exports = {
  isSecretPageUrl,
  isJobId,
  isExternalUrl,
  isRevealLiteralOk,
  resolveReveal,
  createRateLimiter,
  NOTIFY_TEXT,
};
