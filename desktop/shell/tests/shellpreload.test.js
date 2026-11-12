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
        on: (...args) => listeners.push(args),
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, listeners, sends, state };
}

test("只 require electron；恰好一次 exposeInMainWorld 且名字 themisShell", () => {
  const p = runShellPreload();
  assert.deepEqual(p.requires, ["electron"]);
  assert.equal(p.exposes.length, 1, JSON.stringify(p.exposes.map((e) => e[0])));
  assert.equal(p.exposes[0][0], "themisShell");
  assert.equal((p.source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
});

test("成员名集合等于 themisShell.ts 的 interface ThemisShell（从 .ts 解析）", () => {
  const p = runShellPreload();
  const expected = interfaceNames("ThemisShell");
  assert.equal(expected.length, 10, "类型文件解析出的成员应当是十个：" + JSON.stringify(expected));
  assert.deepEqual(Object.keys(p.exposes[0][1]).sort(), [...expected].sort());
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

test("on 同步返回退订函数：不发 IPC、不注册监听；退订函数也不发 IPC", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const before = p.invokes.length;
  const off = api.on("service-state", () => {});
  assert.equal(typeof off, "function", "on 要同步返回一个函数");
  off();
  assert.equal(p.invokes.length, before, "on/退订都不许发 IPC");
  assert.equal(p.listeners.length, 0, "本片不许注册 ipcRenderer 监听");
});

test("自包含：没有 ipcRenderer 的 send/on 调用、不 require 相对路径或 node: 模块", () => {
  const p = runShellPreload();
  assert.equal(p.sends.length, 0);
  assert.equal(p.listeners.length, 0);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(p.source), "不许有 ipcRenderer 的发送");
  assert.ok(!/ipcRenderer\s*\.\s*on\s*\(/.test(p.source), "不许有 ipcRenderer 的监听");
  assert.ok(!/require\(\s*['"]\./.test(p.source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(p.source), "不许 require node: 模块");
});
