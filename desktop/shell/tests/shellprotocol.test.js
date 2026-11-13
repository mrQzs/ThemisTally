"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const proto = require("../src/shellprotocol.js");

// CSP 的唯一出处是 ts/packages/ui/src/localhttp/headers.ts 的 CSP 常量（逐字相等，不另抄一份）
const HEADERS_TS = path.resolve(__dirname, "..", "..", "..", "ts", "packages", "ui", "src", "localhttp", "headers.ts");
const cpm = fs.readFileSync(HEADERS_TS, "utf8").match(/export const CSP =\s*"([^"]+)"/);
assert.ok(cpm, "headers.ts 里解析不出 CSP 常量");
const CSP = cpm[1];

function makeRoot() {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t030-proto-")));
  const root = path.join(base, "root");
  fs.mkdirSync(path.join(root, "assets"), { recursive: true });
  fs.mkdirSync(path.join(root, "licenses"), { recursive: true });
  fs.writeFileSync(path.join(root, "index.html"), "<!doctype html><html>shell-index</html>\n");
  fs.writeFileSync(path.join(root, "assets", "app.js"), "console.log(1);\n");
  fs.writeFileSync(path.join(root, "assets", "app.css"), "body{color:red}\n");
  fs.writeFileSync(path.join(root, "assets", "f.woff2"), Buffer.from([0, 0, 1, 2]));
  fs.writeFileSync(path.join(root, "assets", "i.svg"), "<svg/>");
  fs.writeFileSync(path.join(root, "assets", "l.png"), Buffer.from([137, 80, 78, 71]));
  fs.writeFileSync(path.join(root, "assets", "fav.ico"), Buffer.from([0, 1, 2]));
  fs.writeFileSync(path.join(root, "data.json"), "{}\n");
  fs.writeFileSync(path.join(root, "licenses", "readme.txt"), "license text\n");
  fs.writeFileSync(path.join(base, "secret.txt"), "SECRET-OUTSIDE");
  return { base, root };
}

function headerOf(headers, name) {
  const target = name.toLowerCase();
  for (const k of Object.keys(headers || {})) {
    if (k.toLowerCase() === target) return headers[k];
  }
  return undefined;
}

function assertInside(rootReal, p) {
  assert.ok(typeof p === "string" && path.isAbsolute(p), "200 的 path 必须是绝对路径：" + JSON.stringify(p));
  const rel = path.relative(rootReal, p);
  assert.ok(
    rel !== "" && rel !== ".." && !rel.startsWith(".." + path.sep) && !path.isAbsolute(rel),
    "读到的文件要在 root 之内：" + p + "（root=" + rootReal + "）",
  );
}

test("常量逐字：SHELL_SCHEME / SHELL_HOST / SHELL_START_URL / SHELL_STATUS_URL", () => {
  assert.equal(proto.SHELL_SCHEME, "themis-shell");
  assert.equal(proto.SHELL_HOST, "app");
  assert.equal(proto.SHELL_START_URL, "themis-shell://app/index.html#/first-run");
  assert.equal(proto.SHELL_STATUS_URL, "themis-shell://app/index.html#/service-status");
  assert.equal(proto.isShellPageUrl(proto.SHELL_START_URL), true);
  assert.equal(proto.isShellPageUrl(proto.SHELL_STATUS_URL), true, "服务状态页也是外壳页地址");
});

test("isShellPageUrl 正例", () => {
  for (const u of [
    "themis-shell://app/",
    "themis-shell://app/index.html",
    "themis-shell://app/index.html#/first-run",
    "themis-shell://app/index.html#/service-status",
    "themis-shell://app/assets/app.js",
  ]) {
    assert.equal(proto.isShellPageUrl(u), true, u);
  }
});

test("isShellPageUrl 反例（协议/主机/端口/userinfo/抛错或解析到别处的输入）", () => {
  for (const u of [
    "",
    "javascript:alert(1)",
    "http://app/",
    "https://app/",
    "file:///C:/x/index.html",
    "themis-shell://other/index.html",
    "themis-shell://app:8080/index.html",
    "themis-shell://user@app/index.html",
    "themis-shell://user:pass@app/index.html",
    "themis-shell://app\\@evil/",
  ]) {
    assert.equal(proto.isShellPageUrl(u), false, u);
  }
});

test("200 用例：九种扩展名的 Content-Type、CSP 逐字、nosniff、body 逐字节、path 在 root 内", () => {
  const { root } = makeRoot();
  const rootReal = fs.realpathSync(root);
  const mime = [
    ["index.html", "text/html"],
    ["assets/app.js", "text/javascript"],
    ["assets/app.css", "text/css"],
    ["assets/f.woff2", "font/woff2"],
    ["assets/i.svg", "image/svg+xml"],
    ["assets/l.png", "image/png"],
    ["assets/fav.ico", "image/x-icon"],
    ["data.json", "application/json"],
    ["licenses/readme.txt", "text/plain"],
  ];
  for (const [rel, contentType] of mime) {
    const r = proto.resolveShellAsset(root, "themis-shell://app/" + rel);
    assert.equal(r.status, 200, rel + " → " + JSON.stringify(r.status));
    assert.equal(typeof r.status, "number");
    assert.ok(r.headers && typeof r.headers === "object" && !Array.isArray(r.headers));
    assert.equal(headerOf(r.headers, "Content-Type"), contentType, rel);
    assert.equal(headerOf(r.headers, "Content-Security-Policy"), CSP, rel + " 的 CSP 要逐字等于 headers.ts");
    assert.equal(headerOf(r.headers, "X-Content-Type-Options"), "nosniff", rel);
    assert.ok(Buffer.isBuffer(r.body), rel + " 的 body 要是 Buffer");
    assert.deepEqual(r.body, fs.readFileSync(path.join(root, rel)), rel + " 的 body 逐字节相等");
    assertInside(rootReal, r.path);
    assert.equal(r.path, path.join(rootReal, ...rel.split("/")), rel);
  }
  const start = proto.resolveShellAsset(root, proto.SHELL_START_URL);
  assert.equal(start.status, 200);
  assert.equal(headerOf(start.headers, "Content-Type"), "text/html");
});

test("404 用例：一律 404、无正文细节、path 为 null", () => {
  const { root } = makeRoot();
  const cases = [
    ["未知扩展名", "themis-shell://app/notes.xyz"],
    ["目录（不带斜杠）", "themis-shell://app/assets"],
    ["目录（带尾斜杠）", "themis-shell://app/assets/"],
    ["不存在的文件", "themis-shell://app/missing.js"],
    ["http 协议", "http://app/index.html"],
    ["别的主机", "themis-shell://other/index.html"],
    ["带端口", "themis-shell://app:8080/index.html"],
    ["带 userinfo", "themis-shell://user@app/index.html"],
    ["反斜杠（%5c）", "themis-shell://app/a%5cb.js"],
    ["NUL（%00）", "themis-shell://app/a%00b.js"],
    ["解码后的冒号（%3a）", "themis-shell://app/a%3ab.js"],
    ["裸冒号", "themis-shell://app/C:/x.js"],
    ["%252e（解码一次后仍含 %）", "themis-shell://app/%252e.js"],
    ["%252e%252e（二次解码防护）", "themis-shell://app/%252e%252e/secret.txt"],
  ];
  for (const [what, url] of cases) {
    const r = proto.resolveShellAsset(root, url);
    assert.equal(r.status, 404, what + " → " + JSON.stringify(r.status));
    assert.equal(r.path, null, what + " 的 path 要是 null");
    assert.ok(
      r.body === null || r.body === undefined || (Buffer.isBuffer(r.body) && r.body.length === 0),
      what + " 不许带正文细节",
    );
  }
});

test("越界用例按性质断言：回 200 的读到的文件都在 root 之内", () => {
  const { root } = makeRoot();
  const rootReal = fs.realpathSync(root);
  const urls = [
    "themis-shell://app/../secret.txt",
    "themis-shell://app/%2e%2e/secret.txt",
    "themis-shell://app/a/../../secret.txt",
    "themis-shell://app/assets/../index.html",
    "themis-shell://app/./index.html",
  ];
  for (const url of urls) {
    const r = proto.resolveShellAsset(root, url);
    if (r.status === 200) {
      assertInside(rootReal, r.path);
      assert.notEqual(String(r.body), "SECRET-OUTSIDE", url + " 不许读到 root 外的 secret.txt");
    } else {
      assert.equal(r.status, 404, url);
      assert.equal(r.path, null, url);
    }
  }
});

test("目录链接（junction）指向 root 外 → 404（系统不给建链接就跳过）", () => {
  const { base, root } = makeRoot();
  const outside = path.join(base, "outside");
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "leak.txt"), "LEAK");
  let linked = false;
  try {
    fs.symlinkSync(outside, path.join(root, "linked"), "junction");
    linked = true;
  } catch {
    linked = false;
  }
  if (linked) {
    const r = proto.resolveShellAsset(root, "themis-shell://app/linked/leak.txt");
    assert.equal(r.status, 404, "链接越出 root 的文件必须 404：" + JSON.stringify(r.status));
    assert.equal(r.path, null);
  } else {
    // 没有链接权限（非 Windows 或未提权）：跳过这一条
    assert.ok(true, "系统不允许建 junction，跳过链接用例");
  }
});
