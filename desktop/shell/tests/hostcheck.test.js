"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  isSecretPageUrl,
  isJobId,
  isExternalUrl,
  isRevealLiteralOk,
  resolveReveal,
  createRateLimiter,
  NOTIFY_TEXT,
} = require("../src/hostcheck.js");

const UI_SRC = path.join(__dirname, "..", "..", "..", "ts", "packages", "ui", "src");

const T31 = "AbCdEfGhIjKlMnOpQrStUvWxYz01234";
const T32 = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";
const T33 = T32 + "6";
const TMIX = "abcdefghij" + "-" + "klmnopqrst" + "_" + "uvwxyz0123";
const J42 = "0123456789".repeat(4) + "01";
const J43 = "0123456789".repeat(4) + "012";
const J44 = J43 + "3";
const LINK_TYPE = process.platform === "win32" ? "junction" : "dir";

test("出处对齐：服务一侧的正则与头名字面量还在（服务改了，外壳的校验就该跟着红）", () => {
  const secret = fs.readFileSync(path.join(UI_SRC, "secretentry.ts"), "utf8");
  assert.ok(secret.includes("PAGE_URL_RE = /^http:"), "secretentry.ts 的页面地址正则没了");
  assert.ok(secret.includes("([A-Za-z0-9_-]{32})$/u"), "secretentry.ts 的令牌长度变了");
  assert.ok(secret.includes("(\\d{1,5})"), "secretentry.ts 的端口位数变了");
  assert.ok(secret.includes("PORT_MAX = 65535"), "secretentry.ts 的端口上限变了");
  const jobs = fs.readFileSync(path.join(UI_SRC, "jobs.ts"), "utf8");
  assert.ok(jobs.includes("JOB_ID_RE = /^[A-Za-z0-9_-]{43}$/u"), "jobs.ts 的作业号正则变了");
  const control = fs.readFileSync(path.join(UI_SRC, "localhttp", "control.ts"), "utf8");
  assert.ok(control.includes('"x-themis-control"'), "control.ts 的控制令牌头名变了");
  const routes = fs.readFileSync(path.join(UI_SRC, "routes.ts"), "utf8");
  assert.ok(routes.includes('CONTROL_PATH = "/control/bootstrap"'), "routes.ts 的控制路径变了");
});

test("isSecretPageUrl 正例：端口边界 1 与 65535、大小写与 -_ 令牌", () => {
  assert.equal(isSecretPageUrl("http://127.0.0.1:8080/" + T32), true);
  assert.equal(isSecretPageUrl("http://127.0.0.1:1/" + T32), true);
  assert.equal(isSecretPageUrl("http://127.0.0.1:65535/" + TMIX), true);
});

test("isSecretPageUrl 反例：端口、令牌长度、锚定、主机、协议与非字符串", () => {
  const bad = [
    "http://127.0.0.1:8080/" + T31,
    "http://127.0.0.1:8080/" + T33,
    "http://127.0.0.1:0/" + T32,
    "http://127.0.0.1:65536/" + T32,
    "http://127.0.0.1:8080/",
    "http://127.0.0.1:8080/" + T32 + "/x",
    "http://127.0.0.1:8080/" + T32 + "?q=1",
    "http://127.0.0.1:8080/" + T32 + "\n",
    "http://localhost:8080/" + T32,
    "https://127.0.0.1:8080/" + T32,
    "HTTP://127.0.0.1:8080/" + T32,
    "not a url",
    "",
    123,
    null,
  ];
  for (const url of bad) {
    assert.equal(isSecretPageUrl(url), false, "不该放行：" + JSON.stringify(url));
  }
});

test("isJobId：恰好 43 个 base64url 字符", () => {
  assert.equal(isJobId(J43), true);
  assert.equal(isJobId(J42), false, "42 位");
  assert.equal(isJobId(J44), false, "44 位");
  assert.equal(isJobId(J43.replace("0", "+")), false, "+ 不在字母表");
  assert.equal(isJobId(J43.replace("0", "=")), false, "= 不在字母表");
  assert.equal(isJobId(123), false);
  assert.equal(isJobId(null), false);
});

test("isExternalUrl 正例", () => {
  assert.equal(isExternalUrl("http://x.example/"), true);
  assert.equal(isExternalUrl("https://x.example/a?b=1#c"), true);
  assert.equal(isExternalUrl("HTTPS://X.EXAMPLE/"), true);
});

test("isExternalUrl 反例：协议、空白换行、反斜杠与单斜杠写法、非字符串", () => {
  const bad = [
    "javascript:alert(1)",
    "file:///C:/x",
    "data:text/html,hi",
    "ftp://x.example/",
    "mailto:a@b.example",
    " http://x.example/",
    "http://x.example/ ",
    "http://x.exa\nmple/",
    "http:\\\\x.example/",
    "http:/x.example/",
    "//x.example/",
    "x.example/",
    "",
    123,
    null,
  ];
  for (const url of bad) {
    assert.equal(isExternalUrl(url), false, "不该放行：" + JSON.stringify(url));
  }
});

test("isRevealLiteralOk 正例：普通段、..foo 文件名、点与空格在段中间", () => {
  assert.equal(isRevealLiteralOk("a"), true);
  assert.equal(isRevealLiteralOk("a/b.txt"), true);
  assert.equal(isRevealLiteralOk("..foo"), true);
  assert.equal(isRevealLiteralOk("a.b"), true);
  assert.equal(isRevealLiteralOk("x y"), true);
  assert.equal(isRevealLiteralOk("a b/c"), true);
});

test("isRevealLiteralOk 反例：绝对、盘符、UNC、单点段、反斜杠、冒号、段尾点或空格、空段、控制字符", () => {
  const bad = [
    "",
    "/a",
    "a/",
    "a//b",
    ".",
    "..",
    "a/..",
    "../a",
    "a/./b",
    "C:/x",
    "C:\\x",
    "\\\\srv\\s",
    "a:b",
    "a\\b",
    "a.",
    "a..",
    "a ",
    "a\u0000b",
    "a\u001fb",
    "a\nb",
    "a\tb",
    123,
    null,
  ];
  for (const relPath of bad) {
    assert.equal(isRevealLiteralOk(relPath), false, "不该放行：" + JSON.stringify(relPath));
  }
});

test("resolveReveal：字面检查不过时根本不碰 realpath 与 stat", () => {
  const calls = [];
  const r = resolveReveal({
    repo: "C:/repo",
    relPath: "..",
    realpath: (p) => {
      calls.push(p);
      return p;
    },
    stat: () => ({ isFile: () => true, isDirectory: () => false }),
  });
  assert.ok(!r, "拒绝时必须返回假值：" + JSON.stringify(r));
  assert.deepEqual(calls, [], "字面检查不过就不许碰文件系统");
});

test("resolveReveal：通过时返回 realpath 之后的完整路径；目录放行", () => {
  const repo = "C:/repo";
  const root = "C:/real/.agent";
  const full = path.join(root, "a.txt");
  const dir = path.join(root, "d");
  const map = new Map([
    [path.join(repo, ".agent"), root],
    [full, full],
    [dir, dir],
  ]);
  const realpath = (p) => {
    if (!map.has(p)) throw new Error("unexpected realpath " + p);
    return map.get(p);
  };
  const asFile = () => ({ isFile: () => true, isDirectory: () => false });
  assert.equal(resolveReveal({ repo, relPath: "a.txt", realpath, stat: asFile }), full);
  assert.equal(
    resolveReveal({ repo, relPath: "d", realpath, stat: () => ({ isFile: () => false, isDirectory: () => true }) }),
    dir,
  );
});

test("resolveReveal：经 realpath 跑出 root、落在 root 本身、..foo 不被误判", () => {
  const repo = "C:/repo";
  const root = "C:/real/.agent";
  const outside = "C:/real/elsewhere";
  const foo = path.join(root, "..foo");
  const map = new Map([
    [path.join(repo, ".agent"), root],
    [path.join(root, "esc"), outside],
    [path.join(root, "self"), root],
    [foo, foo],
  ]);
  const realpath = (p) => {
    if (!map.has(p)) throw new Error("unexpected realpath " + p);
    return map.get(p);
  };
  const asFile = () => ({ isFile: () => true, isDirectory: () => false });
  assert.ok(!resolveReveal({ repo, relPath: "esc", realpath, stat: asFile }), "解析到 .agent 之外必须拒绝");
  assert.ok(!resolveReveal({ repo, relPath: "self", realpath, stat: asFile }), "落在 root 本身必须拒绝");
  assert.equal(resolveReveal({ repo, relPath: "..foo", realpath, stat: asFile }), foo, "..foo 是合法文件名");
});

test("resolveReveal：stat 只认文件或目录、stat 抛错、realpath 抛错都拒绝", () => {
  const repo = "C:/repo";
  const root = "C:/real/.agent";
  const target = path.join(root, "x");
  const map = new Map([
    [path.join(repo, ".agent"), root],
    [target, target],
  ]);
  const realpath = (p) => {
    if (!map.has(p)) throw new Error("unexpected realpath " + p);
    return map.get(p);
  };
  assert.ok(
    !resolveReveal({ repo, relPath: "x", realpath, stat: () => ({ isFile: () => false, isDirectory: () => false }) }),
    "设备/管道等不该放行",
  );
  assert.ok(
    !resolveReveal({
      repo,
      relPath: "x",
      realpath,
      stat: () => {
        throw new Error("no");
      },
    }),
    "stat 抛错要拒绝",
  );
  assert.ok(
    !resolveReveal({
      repo,
      relPath: "gone",
      realpath: () => {
        throw new Error("ENOENT");
      },
      stat: () => ({ isFile: () => true, isDirectory: () => false }),
    }),
    "realpath 抛错要拒绝",
  );
});

test("createRateLimiter：窗口内 max 次、被拒的调用不计数", () => {
  let at = 0;
  const limiter = createRateLimiter({ max: 3, windowMs: 60000, now: () => at });
  assert.equal(limiter.take(), true);
  assert.equal(limiter.take(), true);
  assert.equal(limiter.take(), true);
  at = 1;
  assert.equal(limiter.take(), false, "第 4 次必须被拒");
  at = 60000;
  assert.equal(limiter.take(), true);
  assert.equal(limiter.take(), true);
  assert.equal(limiter.take(), true, "被拒的那次不许占名额");
  assert.equal(limiter.take(), false);
});

test("createRateLimiter：第 1 次之后正好 60000 毫秒放行", () => {
  let at = 0;
  const limiter = createRateLimiter({ max: 1, windowMs: 60000, now: () => at });
  assert.equal(limiter.take(), true);
  at = 59999;
  assert.equal(limiter.take(), false, "差 1 毫秒也不放行");
  at = 60000;
  assert.equal(limiter.take(), true, "正好 60000 毫秒必须放行");
});

test("NOTIFY_TEXT：只认两个类型名，constructor 这类键不命中", () => {
  assert.deepEqual(NOTIFY_TEXT.get("attempt-finished"), { title: "ThemisTally", body: "attempt 已结束" });
  assert.deepEqual(NOTIFY_TEXT.get("awaiting-review"), { title: "ThemisTally", body: "有 attempt 等待验收" });
  for (const key of ["constructor", "__proto__", "toString", "hasOwnProperty", "", "other"]) {
    assert.equal(NOTIFY_TEXT.get(key), undefined, key + " 不该命中");
  }
  assert.equal(NOTIFY_TEXT.get(123), undefined);
  assert.equal(NOTIFY_TEXT.get(null), undefined);
  assert.equal(NOTIFY_TEXT.get({}), undefined);
});

test("resolveReveal 真文件系统：.agent 里放行、指到外面与经它的路径都拒绝、指到里面放行", (t) => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t026-hc-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const repo = path.join(base, "repo");
  const agent = path.join(repo, ".agent");
  const outside = path.join(base, "outside");
  fs.mkdirSync(path.join(agent, "a"), { recursive: true });
  fs.writeFileSync(path.join(agent, "a", "b.txt"), "x");
  fs.mkdirSync(path.join(agent, "dir"));
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "x.txt"), "z");
  fs.symlinkSync(path.join(agent, "dir"), path.join(agent, "in-link"), LINK_TYPE);
  fs.symlinkSync(outside, path.join(agent, "out-link"), LINK_TYPE);
  fs.symlinkSync(agent, path.join(agent, "self"), LINK_TYPE);

  assert.equal(resolveReveal({ repo, relPath: "a/b.txt" }), fs.realpathSync.native(path.join(agent, "a", "b.txt")));
  assert.equal(resolveReveal({ repo, relPath: "dir" }), fs.realpathSync.native(path.join(agent, "dir")));
  assert.equal(resolveReveal({ repo, relPath: "in-link" }), fs.realpathSync.native(path.join(agent, "dir")));
  assert.ok(!resolveReveal({ repo, relPath: "out-link" }), "指到 .agent 之外的 junction 要拒绝");
  assert.ok(!resolveReveal({ repo, relPath: "out-link/x.txt" }), "经它出去的路径也要拒绝");
  assert.ok(!resolveReveal({ repo, relPath: "self" }), "解析到 root 本身要拒绝");
  assert.ok(!resolveReveal({ repo, relPath: "nope.txt" }), "不存在要拒绝");
  assert.ok(!resolveReveal({ repo: path.join(base, "no-agent"), relPath: "a/b.txt" }), ".agent 缺失要拒绝");
});
