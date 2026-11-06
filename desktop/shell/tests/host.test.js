"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");
const { createHost } = require("../src/host.js");
const { createFakeControlServer } = require("./fixtures/fake-control-server.js");

const TOKEN = "ctrl-tok-" + crypto.randomBytes(12).toString("hex");
const PAGE_TOK = crypto.randomBytes(24).toString("base64url"); // 恰好 32 个 base64url 字符
const LINK_TYPE = process.platform === "win32" ? "junction" : "dir";

// 仓库夹具：.agent 里的普通文件/目录、..foo 文件名、指里/指外/指 root 本身的 junction、没有 .agent 的仓库
const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "t026-host-"));
const REPO = path.join(BASE, "repo");
const AGENT = path.join(REPO, ".agent");
fs.mkdirSync(path.join(AGENT, "a"), { recursive: true });
fs.writeFileSync(path.join(AGENT, "a", "b.txt"), "x");
fs.mkdirSync(path.join(AGENT, "dir"));
fs.writeFileSync(path.join(AGENT, "..foo"), "y");
const OUTSIDE = path.join(BASE, "outside");
fs.mkdirSync(OUTSIDE);
fs.writeFileSync(path.join(OUTSIDE, "x.txt"), "z");
fs.symlinkSync(path.join(AGENT, "dir"), path.join(AGENT, "in-link"), LINK_TYPE);
fs.symlinkSync(OUTSIDE, path.join(AGENT, "out-link"), LINK_TYPE);
fs.symlinkSync(AGENT, path.join(AGENT, "self"), LINK_TYPE);
const REPO_NOAGENT = path.join(BASE, "repo-no-agent");
fs.mkdirSync(REPO_NOAGENT);
test.after(() => fs.rmSync(BASE, { recursive: true, force: true }));

const server = createFakeControlServer();
test.after(() => server.close());

const clock = { at: 0 };
const winCfg = { failLoad: false, hangLoad: false };
const wins = [];
const winArgs = [];
const loadedMain = [];
const confirmCalls = [];
const openedExternal = [];
const shownItems = [];
const shownNotes = [];
let confirmAnswer = true;
let openExternalMode = "ok";

function fakeWindow() {
  const win = new EventEmitter();
  win.focusCalls = 0;
  win.closedByHost = false;
  win.loadCalls = [];
  win.destroyed = false;
  win.isDestroyed = () => win.destroyed;
  win.focus = () => {
    win.focusCalls += 1;
  };
  win.close = () => {
    win.closedByHost = true;
    setImmediate(() => win.emit("closed"));
  };
  win.loadURL = (url) => {
    win.loadCalls.push(url);
    if (winCfg.failLoad) return Promise.reject(new Error("加载失败，地址 " + url));
    if (winCfg.hangLoad) return new Promise(() => {});
    return Promise.resolve();
  };
  return win;
}

function resetAll() {
  server.reset();
  winCfg.failLoad = false;
  winCfg.hangLoad = false;
  wins.length = 0;
  winArgs.length = 0;
  loadedMain.length = 0;
  confirmCalls.length = 0;
  openedExternal.length = 0;
  shownItems.length = 0;
  shownNotes.length = 0;
  confirmAnswer = true;
  openExternalMode = "ok";
  clock.at = 0;
}

function makeHost(over) {
  return createHost(
    Object.assign(
      {
        origin: server.origin,
        control: TOKEN,
        repo: REPO,
        loadMain: async (url) => {
          loadedMain.push(url);
        },
        createSecretWindow: (arg) => {
          winArgs.push(arg);
          const win = fakeWindow();
          wins.push(win);
          return win;
        },
        confirmExternal: async (url) => {
          confirmCalls.push(url);
          return confirmAnswer;
        },
        openExternal: async (url) => {
          openedExternal.push(url);
          if (openExternalMode === "fail") throw new Error("打不开");
        },
        showItem: (fullPath) => {
          shownItems.push(fullPath);
        },
        showNotification: (note) => {
          shownNotes.push(note);
        },
        now: () => clock.at,
        controlTimeoutMs: 5000,
      },
      over || {},
    ),
  );
}

function secretUrl(port) {
  return "http://127.0.0.1:" + (port || 8123) + "/" + PAGE_TOK;
}

function jobId(ch) {
  return ch.repeat(43);
}

function cancels() {
  return server.cancels();
}

async function untilCancel(n) {
  for (let i = 0; i < 200; i += 1) {
    if (cancels().length >= n) return;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

test.before(async () => {
  await server.listen();
});

// ---- reauth ----

test("reauth 成功：恰好 {ok:true}、只加载一次、请求带令牌头且无 Origin 无 Cookie", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reauth();
  assert.deepEqual(r, { ok: true }, JSON.stringify(r));
  assert.equal(server.hits.length, 1, JSON.stringify(server.hits));
  assert.equal(server.hits[0].method, "POST");
  assert.equal(server.hits[0].url, "/control/bootstrap");
  assert.equal(server.hits[0].headers["x-themis-control"], TOKEN);
  assert.equal(server.hits[0].headers.origin, undefined);
  assert.equal(server.hits[0].headers.cookie, undefined);
  assert.equal(server.hits[0].body, "");
  assert.deepEqual(loadedMain, [server.bootstrapUrl]);
  assert.ok(!JSON.stringify(r).includes(TOKEN));
  assert.ok(!JSON.stringify(r).includes(server.bootstrapUrl));
});

test("reauth 限速：60 秒内最多 3 次，第 4 次不发请求不加载；窗口滑过去就放行", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.at = 1000;
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.at = 2000;
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.at = 3000;
  assert.deepEqual(await host.reauth(), { ok: false, reason: "rate-limited" });
  assert.equal(server.hits.length, 3, JSON.stringify(server.hits));
  assert.equal(loadedMain.length, 3);
  clock.at = 61000;
  assert.deepEqual(await host.reauth(), { ok: true });
  assert.equal(server.hits.length, 4);
});

test("reauth 失败也占名额：三次 bad-response 之后第 4 次是 rate-limited，服务只收到 3 个请求", async () => {
  resetAll();
  server.state.bootstrapStatus = 500;
  const host = makeHost();
  for (let i = 0; i < 3; i += 1) {
    assert.deepEqual(await host.reauth(), { ok: false, reason: "bad-response" });
  }
  assert.deepEqual(await host.reauth(), { ok: false, reason: "rate-limited" });
  assert.equal(server.hits.length, 3, JSON.stringify(server.hits));
  assert.equal(loadedMain.length, 0);
});

test("reauth 连不上：request-failed，不加载", async () => {
  resetAll();
  const dead = createFakeControlServer();
  const origin = await dead.listen();
  await dead.close();
  const host = makeHost({ origin });
  const r = await host.reauth();
  assert.deepEqual(r, { ok: false, reason: "request-failed" });
  assert.equal(loadedMain.length, 0);
  assert.ok(!JSON.stringify(r).includes(TOKEN));
});

const BAD_RESPONSES = [
  ["状态码 500", () => {
    server.state.bootstrapStatus = 500;
  }],
  ["非 JSON 正文", () => {
    server.state.bootstrapStatus = 200;
    server.state.bootstrapBody = "not json <script>";
  }],
  ["ok 不是 true", () => {
    server.state.bootstrapStatus = 200;
    server.state.bootstrapBody = JSON.stringify({ ok: false });
  }],
  ["data.bootstrap 不是字符串", () => {
    server.state.bootstrapStatus = 200;
    server.state.bootstrapBody = JSON.stringify({ ok: true, data: { bootstrap: 123 } });
  }],
  ["data.bootstrap 在别的 origin", () => {
    server.state.bootstrapStatus = 200;
    server.state.bootstrapBody = JSON.stringify({ ok: true, data: { bootstrap: "http://127.0.0.1:9/bootstrap/other" } });
  }],
  ["data.bootstrap 缺字段", () => {
    server.state.bootstrapStatus = 200;
    server.state.bootstrapBody = JSON.stringify({ ok: true, data: {} });
  }],
];

for (const [name, set] of BAD_RESPONSES) {
  test("reauth bad-response：" + name + "，不加载、不外泄", async () => {
    resetAll();
    set();
    const host = makeHost();
    const r = await host.reauth();
    assert.deepEqual(r, { ok: false, reason: "bad-response" }, name + "：" + JSON.stringify(r));
    assert.equal(loadedMain.length, 0, name);
    assert.ok(!JSON.stringify(r).includes(TOKEN), name);
    assert.ok(!JSON.stringify(r).includes(server.bootstrapUrl), name);
  });
}

test("reauth 加载失败：load-failed，拒绝消息里的地址不外传", async () => {
  resetAll();
  const host = makeHost({
    loadMain: async () => {
      throw new Error("加载失败 " + server.bootstrapUrl);
    },
  });
  const r = await host.reauth();
  assert.deepEqual(r, { ok: false, reason: "load-failed" });
  assert.ok(!JSON.stringify(r).includes(server.bootstrapUrl));
  assert.ok(!JSON.stringify(r).includes(TOKEN));
});

// ---- openSecretWindow ----

test("openSecretWindow 参数不合格：bad-args，不开窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("a");
  const badUrls = [
    "http://127.0.0.1:8123/" + PAGE_TOK.slice(0, 31),
    "http://127.0.0.1:8123/" + PAGE_TOK + "x",
    "http://127.0.0.1:0/" + PAGE_TOK,
    "http://127.0.0.1:65536/" + PAGE_TOK,
    "http://127.0.0.1:8123/",
    "http://127.0.0.1:8123/" + PAGE_TOK + "/x",
    "http://127.0.0.1:8123/" + PAGE_TOK + "?q=1",
    "http://127.0.0.1:8123/" + PAGE_TOK + "\n",
    "http://localhost:8123/" + PAGE_TOK,
    "https://127.0.0.1:8123/" + PAGE_TOK,
    "not a url",
    123,
    null,
  ];
  for (const url of badUrls) {
    const r = await host.openSecretWindow(url, j);
    assert.deepEqual(r, { ok: false, reason: "bad-args" }, "url=" + JSON.stringify(url));
  }
  const badJobs = ["a".repeat(42), "a".repeat(44), "a".repeat(43) + "!", 5, null];
  for (const bad of badJobs) {
    const r = await host.openSecretWindow(secretUrl(), bad);
    assert.deepEqual(r, { ok: false, reason: "bad-args" }, "jobId=" + JSON.stringify(bad));
  }
  assert.equal(wins.length, 0);
  assert.equal(server.hits.length, 0);
});

test("openSecretWindow 正常：开窗，origin 是该 url 自己的，loadURL 收到原 url", async () => {
  resetAll();
  const host = makeHost();
  const url = secretUrl();
  const r = await host.openSecretWindow(url, jobId("b"));
  assert.deepEqual(r, { ok: true }, JSON.stringify(r));
  assert.equal(wins.length, 1);
  assert.equal(winArgs.length, 1);
  assert.equal(winArgs[0] && winArgs[0].origin, "http://127.0.0.1:8123");
  assert.deepEqual(wins[0].loadCalls, [url]);
  assert.equal(server.hits.length, 0);
});

test("同一 jobId 再调：{ok:true} 且聚焦，不开新窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("c");
  await host.openSecretWindow(secretUrl(), j);
  const r = await host.openSecretWindow(secretUrl(), j);
  assert.deepEqual(r, { ok: true });
  assert.equal(wins.length, 1);
  assert.equal(wins[0].focusCalls, 1);
  assert.equal(server.hits.length, 0);
});

test("别的 jobId：busy 且聚焦，不开新窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  await host.openSecretWindow(secretUrl(), jobId("d"));
  const r = await host.openSecretWindow(secretUrl(9999), jobId("e"));
  assert.deepEqual(r, { ok: false, reason: "busy" });
  assert.equal(wins.length, 1);
  assert.equal(wins[0].focusCalls, 1);
  assert.equal(server.hits.length, 0);
});

test("占位在第一个 await 之前：第一个窗口还没加载完，并发调用就被拒/聚焦", async () => {
  resetAll();
  winCfg.hangLoad = true;
  const host = makeHost();
  const pending = host.openSecretWindow(secretUrl(), jobId("f")); // loadURL 永远挂起
  const r = await host.openSecretWindow(secretUrl(), jobId("g"));
  assert.deepEqual(r, { ok: false, reason: "busy" });
  assert.equal(wins.length, 1, "不许开出第二个窗口");
  const same = await host.openSecretWindow(secretUrl(), jobId("f"));
  assert.deepEqual(same, { ok: true });
  assert.equal(wins[0].focusCalls, 2, "两种被拒/复用都要聚焦：busy 一次 + 同 jobId 一次");
  wins[0].emit("closed");
  await untilCancel(1);
  assert.equal(wins[0].loadCalls.length, 1, "只开了一个窗口、只加载了一次");
  void pending;
});

test("关窗取消：恰好一次、路径与头都对；再触发 closed 不重发；关掉后能再开", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("h");
  const url = secretUrl();
  await host.openSecretWindow(url, j);
  wins[0].emit("closed");
  await untilCancel(1);
  assert.equal(cancels().length, 1, JSON.stringify(server.hits));
  assert.equal(cancels()[0].method, "POST");
  assert.equal(cancels()[0].url, "/control/jobs/" + j + "/cancel");
  assert.equal(cancels()[0].headers["x-themis-control"], TOKEN);
  wins[0].emit("closed");
  await new Promise((resolve) => setTimeout(resolve, 60));
  assert.equal(cancels().length, 1, "once 不许重复发取消");
  const again = await host.openSecretWindow(url, j);
  assert.deepEqual(again, { ok: true });
  assert.equal(wins.length, 2, "关掉之后要能再开");
});

test("取消的结果一律吞掉：404 / 409 / 500 / 断连，不崩、没有未处理的拒绝", async () => {
  for (const cfg of [404, 409, 500, "destroy"]) {
    resetAll();
    if (cfg === "destroy") server.state.cancelDestroy = true;
    else server.state.cancelStatus = cfg;
    const host = makeHost();
    await host.openSecretWindow(secretUrl(), jobId("i"));
    wins[0].emit("closed");
    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(cancels().length, 1, "cfg=" + String(cfg) + "：" + JSON.stringify(server.hits));
  }
});

test("loadURL 失败：load-failed、关窗，closed 照常触发取消；页面令牌不外泄", async () => {
  resetAll();
  winCfg.failLoad = true;
  const host = makeHost();
  const j = jobId("j");
  const r = await host.openSecretWindow(secretUrl(), j);
  assert.deepEqual(r, { ok: false, reason: "load-failed" });
  assert.ok(!JSON.stringify(r).includes(PAGE_TOK));
  assert.equal(wins[0].closedByHost, true, "失败时窗口还在就要 close()");
  await untilCancel(1);
  assert.equal(cancels().length, 1);
  assert.equal(cancels()[0].url, "/control/jobs/" + j + "/cancel");
});

// ---- openExternal ----

test("openExternal 非法地址：bad-url 且确认框不弹", async () => {
  resetAll();
  const host = makeHost();
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
    const r = await host.openExternal(url);
    assert.deepEqual(r, { ok: false, reason: "bad-url" }, "url=" + JSON.stringify(url));
  }
  assert.equal(confirmCalls.length, 0, "校验不过不许弹确认框");
  assert.equal(openedExternal.length, 0);
});

test("openExternal 确认取消：cancelled 且打开函数没被调用", async () => {
  resetAll();
  confirmAnswer = false;
  const host = makeHost();
  const r = await host.openExternal("https://x.example/page");
  assert.deepEqual(r, { ok: false, reason: "cancelled" });
  assert.deepEqual(confirmCalls, ["https://x.example/page"]);
  assert.equal(openedExternal.length, 0);
});

test("openExternal 确认打开：参数原样传一次，{ok:true}", async () => {
  resetAll();
  const host = makeHost();
  const url = "https://x.example/a?q=1#h";
  const r = await host.openExternal(url);
  assert.deepEqual(r, { ok: true });
  assert.deepEqual(confirmCalls, [url]);
  assert.deepEqual(openedExternal, [url]);
});

test("openExternal 打开失败：open-failed", async () => {
  resetAll();
  openExternalMode = "fail";
  const host = makeHost();
  const r = await host.openExternal("https://x.example/");
  assert.deepEqual(r, { ok: false, reason: "open-failed" });
});

// ---- reveal ----

test("reveal 字面不合格：bad-path 且不调显示函数", async () => {
  resetAll();
  const host = makeHost();
  const bad = [
    "", "/a", "a/", "a//b", ".", "..", "a/..", "../a", "a/./b",
    "C:/x", "C:\\x", "\\\\srv\\s", "a:b", "a\\b", "a.", "a..", "a ",
    "a\u0000b", "a\u001fb", "a\nb", "a\tb",
    123, null,
  ];
  for (const relPath of bad) {
    const r = await host.reveal(relPath);
    assert.deepEqual(r, { ok: false, reason: "bad-path" }, "relPath=" + JSON.stringify(relPath));
  }
  assert.equal(shownItems.length, 0);
});

test("reveal 通过：显示函数被调一次，参数是 realpath 之后的绝对路径", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reveal("a/b.txt");
  assert.deepEqual(r, { ok: true });
  assert.equal(shownItems.length, 1);
  assert.equal(shownItems[0], fs.realpathSync.native(path.join(AGENT, "a", "b.txt")));
});

test("reveal 目录放行；..foo 文件名不被误判", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("dir"), { ok: true });
  assert.deepEqual(await host.reveal("..foo"), { ok: true });
  assert.equal(shownItems.length, 2);
  assert.equal(shownItems[1], fs.realpathSync.native(path.join(AGENT, "..foo")));
});

test("reveal 指到 .agent 之外的 junction：它本身与经它的路径都拒绝", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("out-link"), { ok: false, reason: "bad-path" });
  assert.deepEqual(await host.reveal("out-link/x.txt"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 0);
});

test("reveal 指到 .agent 内部的 junction 放行；解析到 root 本身拒绝", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reveal("in-link");
  assert.deepEqual(r, { ok: true });
  assert.equal(shownItems.length, 1);
  assert.equal(shownItems[0], fs.realpathSync.native(path.join(AGENT, "dir")));
  assert.deepEqual(await host.reveal("self"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 1);
});

test("reveal 不存在、.agent 缺失：bad-path", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("nope.txt"), { ok: false, reason: "bad-path" });
  const other = makeHost({ repo: REPO_NOAGENT });
  assert.deepEqual(await other.reveal("a/b.txt"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 0);
});

// ---- notify ----

test("notify 两类：标题与正文逐字写死", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.notify("attempt-finished"), { ok: true });
  assert.deepEqual(await host.notify("awaiting-review"), { ok: true });
  assert.deepEqual(shownNotes, [
    { title: "ThemisTally", body: "attempt 已结束" },
    { title: "ThemisTally", body: "有 attempt 等待验收" },
  ]);
});

test("notify 其余类型：bad-kind 且不发通知；渲染进程给的额外参数不进文案", async () => {
  resetAll();
  const host = makeHost();
  for (const kind of ["constructor", "__proto__", "toString", "", "other", 123, null, {}]) {
    const r = await host.notify(kind);
    assert.deepEqual(r, { ok: false, reason: "bad-kind" }, "kind=" + JSON.stringify(kind));
  }
  assert.equal(shownNotes.length, 0);
  assert.deepEqual(await host.notify("attempt-finished", "额外参数"), { ok: true });
  assert.deepEqual(shownNotes, [{ title: "ThemisTally", body: "attempt 已结束" }]);
});

// ---- 令牌不外泄 ----

test("控制令牌与引导地址不进宿主对象的 JSON", () => {
  resetAll();
  const host = makeHost();
  assert.ok(!JSON.stringify(host).includes(TOKEN), JSON.stringify(host));
  assert.ok(!JSON.stringify(host).includes(server.bootstrapUrl));
});
