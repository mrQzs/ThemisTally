"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { SHELL_CHANNELS } = require("../src/shellipc.js");

// 期望成员只来自类型文件 desktop/web/src/shellpages/themisShell.ts（照 tests/shellshape.test.js 的解析写法，
// 这里不另抄一份键表——类型文件改了，这些比对就要红）
const TS_PATH = path.resolve(__dirname, "..", "..", "web", "src", "shellpages", "themisShell.ts");
const TS = fs.readFileSync(TS_PATH, "utf8");

function must(condition, message) {
  if (!condition) throw new Error(message);
}

function interfaceBlock(name) {
  const start = TS.match(new RegExp(`export interface ${name} \\{`));
  must(start !== null, `themisShell.ts 里找不到 export interface ${name}`);
  const rest = TS.slice(start.index + start[0].length);
  const end = rest.search(/\n\}/);
  must(end !== -1, `interface ${name} 没有行首 } 的结束`);
  return rest.slice(0, end);
}

function interfaceNames(name) {
  const names = [];
  for (const line of interfaceBlock(name).split("\n")) {
    let m = line.match(/^\s*(\w+)(\?)?\s*:/);
    if (m === null) m = line.match(/^\s*(\w+)\s*\(/);
    if (m !== null) names.push(m[1]);
  }
  must(names.length > 0, `interface ${name} 解析不出成员——类型文件的格式变了，要报警`);
  return names;
}

// shell-preload 跑在 sandbox 里，只能用注入的 require 载入 electron；测试文件里因此不出现
// 「require electron」这个字面串（T025/T028 门禁扫 tests/**），模块名字面量写成 "electron"。
function runShellPreload() {
  const source = fs.readFileSync(path.join(__dirname, "..", "shell-preload.js"), "utf8");
  const requires = [];
  const exposes = [];
  const invokes = [];
  const syncs = [];
  const listeners = [];
  const sends = [];
  const state = { envelope: { ok: true, value: 42 } };
  const fakeRequire = (name) => {
    requires.push(name);
    if (name !== "electron") throw new Error("shell-preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: {
        exposeInMainWorld: (apiName, api) => exposes.push([apiName, api]),
      },
      ipcRenderer: {
        invoke: async (...args) => {
          invokes.push(args);
          return state.envelope;
        },
        sendSync: (...args) => {
          syncs.push(args);
          return { theme: "dark", density: "compact" };
        },
        on: (...args) => listeners.push(args),
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, syncs, listeners, sends, state };
}

test("只 require electron；恰好一次 exposeInMainWorld 且名字 themisShell", () => {
  const p = runShellPreload();
  assert.deepEqual(p.requires, ["electron"]);
  assert.equal(p.exposes.length, 1, JSON.stringify(p.exposes.map((e) => e[0])));
  assert.equal(p.exposes[0][0], "themisShell");
  assert.equal((p.source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
});

test("成员名集合等于 themisShell.ts 的 interface ThemisShell 加 getAppearance（从 .ts 解析）", () => {
  const p = runShellPreload();
  const expected = interfaceNames("ThemisShell");
  assert.equal(expected.length, 10, "类型文件解析出的成员应当是十个：" + JSON.stringify(expected));
  // 本片外壳侧暴露面十一个：原十个 + getAppearance；T063 片 B 起 themisShell.ts 加 getAppearance 后恢复逐字相等
  assert.deepEqual(Object.keys(p.exposes[0][1]).sort(), [...expected, "getAppearance"].sort());
  assert.equal("themisHost" in p.exposes[0][1], false, "不许暴露 themisHost");
});

test("九个方法各用一条通道，合起来恰好等于 SHELL_CHANNELS；实参只转发声明的个数", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const patch = { theme: "dark" };
  api.getState("EXTRA");
  api.pickRepo("EXTRA");
  api.pickPython("EXTRA");
  api.pickKit("EXTRA");
  api.pickTranscriptDir("EXTRA");
  api.saveSettings(patch, "EXTRA");
  api.startService("repo-x", "EXTRA");
  api.restartService("EXTRA");
  api.openExternal("https://x.example/", "EXTRA");
  const expected = [
    ["themis-shell:get-state"],
    ["themis-shell:pick-repo"],
    ["themis-shell:pick-python"],
    ["themis-shell:pick-kit"],
    ["themis-shell:pick-transcript-dir"],
    ["themis-shell:save-settings", patch],
    ["themis-shell:start-service", "repo-x"],
    ["themis-shell:restart-service"],
    ["themis-shell:open-external", "https://x.example/"],
  ];
  assert.deepEqual(p.invokes, expected);
  const used = p.invokes.map((a) => a[0]).sort();
  assert.deepEqual(used, [...SHELL_CHANNELS].sort());
});

test("信封 ok → resolve value；不 ok → 以带 reason 的 Error reject（reason 只进 message）", async () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  p.state.envelope = { ok: true, value: { a: 1, b: ["deep"] } };
  assert.deepEqual(await api.getState(), { a: 1, b: ["deep"] });
  p.state.envelope = { ok: false, reason: "bad-patch" };
  await assert.rejects(
    api.saveSettings({}),
    (err) =>
      err.message === "bad-patch" &&
      err.reason === undefined &&
      Object.prototype.toString.call(err) === "[object Error]",
  );
});

test("on('service-state')：模块级恰好两个 ipcRenderer.on，service-state 监听只收到 state 一个实参", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  assert.equal(p.listeners.length, 2, "模块级恰好两个 ipcRenderer.on（service-state 与 appearance）");
  const serviceListener = p.listeners.find(([ch]) => ch === "themis-shell:service-state");
  assert.ok(serviceListener, "要有一条 themis-shell:service-state 订阅");
  const [channel, internal] = serviceListener;
  assert.equal(channel, "themis-shell:service-state");
  assert.equal(typeof internal, "function");
  const a = [];
  const b = [];
  api.on("service-state", (...args) => a.push(args));
  api.on("service-state", (...args) => b.push(args));
  const payload = { kind: "running", repo: "repo-x", pid: 7, startedAt: "2026-01-01T00:00:00.000Z" };
  // Electron 把事件对象作为第一个实参传给监听函数，state 在第二个：页面只该拿到 state
  internal({ marker: "electron-event" }, payload);
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  assert.equal(a[0].length, 1, "监听函数只收到 state 一个实参");
  assert.equal(b[0].length, 1, "监听函数只收到 state 一个实参");
  assert.deepEqual(a[0][0], payload);
  assert.deepEqual(b[0][0], payload);
  assert.ok(!JSON.stringify(a[0]).includes("electron-event"), "不许把事件对象交给页面");
});

test("getAppearance：走 sendSync themis-shell:get-appearance、载入时不发、回值原样返回", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  assert.deepEqual(p.syncs, [], "载入时不许发 sendSync");
  const got = api.getAppearance();
  assert.deepEqual(p.syncs, [["themis-shell:get-appearance"]]);
  assert.deepEqual(got, { theme: "dark", density: "compact" }, "回值原样返回");
});

test("on('appearance')：恰好两个 ipcRenderer.on 各一频道；监听只收外观一个实参；退订只删自己那条", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const channels = p.listeners.map(([ch]) => ch).sort();
  assert.deepEqual(channels, ["themis-shell:appearance", "themis-shell:service-state"], "两个频道各一个 on");
  const internal = p.listeners.find(([ch]) => ch === "themis-shell:appearance")[1];
  const seen1 = [];
  const seen2 = [];
  const off1 = api.on("appearance", (...args) => seen1.push(args));
  assert.equal(typeof off1, "function", "同步返回退订函数");
  api.on("appearance", (...args) => seen2.push(args));
  internal({ marker: "electron-event" }, { theme: "light", density: "standard" });
  assert.deepEqual(seen1, [[{ theme: "light", density: "standard" }]], "监听只收外观对象一个实参");
  assert.deepEqual(seen2, [[{ theme: "light", density: "standard" }]]);
  assert.ok(!JSON.stringify(seen1[0]).includes("electron-event"), "不许把事件对象交给页面");
  off1();
  internal({}, { theme: "dark", density: "compact" });
  assert.equal(seen1.length, 1, "退订之后不再收");
  assert.equal(seen2.length, 2, "另一条订阅不受影响");
});

test("on：退订只删自己那条、可重复退订；别的事件名同步回空退订函数；on 与退订都不发 IPC", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const [channel, internal] = p.listeners[0];
  assert.equal(channel, "themis-shell:service-state");
  const a = [];
  const b = [];
  const offA = api.on("service-state", (...args) => a.push(args));
  const offB = api.on("service-state", (...args) => b.push(args));
  internal({}, { kind: "starting", repo: "r" });
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  offA();
  assert.doesNotThrow(() => offA(), "重复退订不抛错");
  internal({}, { kind: "running", repo: "r", pid: 1, startedAt: "t" });
  assert.equal(a.length, 1, "退订之后不再收到");
  assert.equal(b.length, 2, "别的订阅照常收到");
  offB();
  internal({}, { kind: "idle" });
  assert.equal(a.length, 1);
  assert.equal(b.length, 2, "全部退订之后再发谁都不收");
  // 别的事件名：不注册、不抛错、不调 listener
  const before = p.listeners.length;
  const invokesBefore = p.invokes.length;
  const sendsBefore = p.sends.length;
  let fired = 0;
  const off = api.on("other-event", () => {
    fired += 1;
  });
  assert.equal(typeof off, "function", "要同步返回函数");
  assert.doesNotThrow(() => off());
  assert.equal(fired, 0);
  assert.equal(p.listeners.length, before, "别的事件名不许再注册监听");
  // on 与退订都不发 IPC
  const off2 = api.on("service-state", () => {});
  off2();
  assert.equal(p.invokes.length, invokesBefore, "on/退订不许发 invoke");
  assert.equal(p.sends.length, sendsBefore, "on/退订不许发 send");
});

test("自包含：只 require electron，没有 ipcRenderer 的发送，不 require 相对路径或 node: 模块", () => {
  const p = runShellPreload();
  assert.deepEqual(p.requires, ["electron"]);
  assert.equal(p.sends.length, 0);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(p.source), "不许有 ipcRenderer 的发送");
  assert.ok(!/require\(\s*['"]\./.test(p.source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(p.source), "不许 require node: 模块");
  assert.equal((p.source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
  assert.equal(Object.keys(p.exposes[0][1]).length, 11, "暴露面共十一个成员（原十个 + getAppearance）");
});
