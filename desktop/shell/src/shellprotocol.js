"use strict";

const fs = require("node:fs");
const path = require("node:path");

const SHELL_SCHEME = "themis-shell";
const SHELL_HOST = "app";
const SHELL_START_URL = "themis-shell://app/index.html#/first-run";

// CSP 逐字等于 ts/packages/ui/src/localhttp/headers.ts 的 CSP 常量（服务页同一套，这里硬编码同一份字面量）
const CSP =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";

// 扩展名 → Content-Type；不在这张表里的一律 404
const MIME = {
  html: "text/html",
  js: "text/javascript",
  css: "text/css",
  woff2: "font/woff2",
  svg: "image/svg+xml",
  png: "image/png",
  ico: "image/x-icon",
  json: "application/json",
  txt: "text/plain",
};

// 协议、主机、userinfo、端口逐项核，不比 origin（Node 对非特殊协议的 origin 是 "null"）；
// host 含端口时 host 是 "app:8080"，自然过不了；host 含反斜杠时 new URL 会抛，接住回 false
function isShellPageUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return (
    parsed.protocol === "themis-shell:" &&
    parsed.host === "app" &&
    parsed.username === "" &&
    parsed.password === ""
  );
}

function notFound() {
  return { status: 404, headers: {}, body: null, path: null };
}

// 读一个产物文件并套上安全头；任何不合格都回 404 且不带正文细节
function resolveShellAsset(root, url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return notFound();
  }
  if (parsed.protocol !== "themis-shell:" || parsed.host !== "app" || parsed.username !== "" || parsed.password !== "") {
    return notFound();
  }

  // 只解码一次；解码后仍含 % 说明是二次编码（%252e 之类），拒绝
  let decoded;
  try {
    decoded = decodeURIComponent(parsed.pathname);
  } catch {
    return notFound();
  }
  if (decoded.includes("%")) return notFound();
  // 反斜杠、冒号、NUL 一律拒绝
  if (/[:\\\u0000]/.test(decoded)) return notFound();

  // 去掉开头的一根根斜杠再分段：空段、. 段、.. 段都拒绝（Node 已消掉大部分点段，这里是第二道）
  const trimmed = decoded.startsWith("/") ? decoded.slice(1) : decoded;
  const segments = trimmed.split("/");
  for (const seg of segments) {
    if (seg === "" || seg === "." || seg === "..") return notFound();
  }

  let rootReal;
  try {
    rootReal = fs.realpathSync(root);
  } catch {
    return notFound();
  }

  // realpath 必须逐字等于 rootReal 拼上同一串相对段：路径上任一级的链接/junction 都会被这道拦下
  let real;
  try {
    real = fs.realpathSync(path.resolve(root, ...segments));
  } catch {
    return notFound();
  }
  if (real !== path.join(rootReal, ...segments)) return notFound();

  // 双保险：解析结果必须落在 root 之内
  const inside = path.relative(rootReal, real);
  if (inside === "" || inside === ".." || inside.startsWith(".." + path.sep) || path.isAbsolute(inside)) {
    return notFound();
  }

  const ext = path.extname(real).slice(1).toLowerCase();
  const contentType = MIME[ext];
  if (contentType === undefined) return notFound();

  let body;
  try {
    body = fs.readFileSync(real);
  } catch {
    return notFound();
  }
  // 只服务普通文件：stat 用 lstat 前的 realpath 已消链接，这里确认不是目录/设备等
  let stat;
  try {
    stat = fs.statSync(real);
  } catch {
    return notFound();
  }
  if (!stat.isFile()) return notFound();

  return {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Security-Policy": CSP,
      "X-Content-Type-Options": "nosniff",
    },
    body,
    path: real,
  };
}

module.exports = {
  SHELL_SCHEME,
  SHELL_HOST,
  SHELL_START_URL,
  CSP,
  MIME,
  isShellPageUrl,
  resolveShellAsset,
};
