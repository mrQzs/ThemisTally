"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { EventEmitter } = require("node:events");
const { PassThrough } = require("node:stream");
const { runShell } = require("../src/core.js");

const ORIGIN = "http://127.0.0.1:8123";
const TOKEN = "ctrl-tok-XYZ";
const NONCE = "nonceABC";
const HS = JSON.stringify({
  themis_ui: 1,
  bootstrap: ORIGIN + "/bootstrap/" + NONCE,
  origin: ORIGIN,
  control: TOKEN,
  pid: 4242,
}) + "\n";

function makeDirs(t) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-core-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo);
  fs.mkdirSync(kit);
  fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  fs.writeFileSync(path.join(assets, "index.html"), "");
  return { repo, kit, assets };
}

function fakeSpawn(opts) {
  const calls = [];
  const fn = (command, args) => {
    assert.ok(Array.isArray(command), "spawn 第一个参数必须是完整 argv 数组");
    assert.deepEqual(args, [], "spawn 第二个参数必须恒为 []");
    calls.push(command);
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stdin = new PassThrough();
    child.pid = 424242;
    child.spawnargs = command;
    child.kill = () => {
      child.killed = true;
      setImmediate(() => {
        child.emit("exit", null, "SIGTERM");
        child.emit("close", null, "SIGTERM");
      });
    };
    let ended = false;
    const onEnd = () => {
      if (ended || opts.exitOnStdinEnd === undefined) return;
      ended = true;
      setTimeout(() => {
        child.exitCode = opts.exitOnStdinEnd;
        child.emit("exit", opts.exitOnStdinEnd, null);
        child.emit("close", opts.exitOnStdinEnd, null);
      }, 30);
    };
    child.stdin.on("finish", onEnd);
    child.stdin.on("close", onEnd);
    child.stdout.write(HS);
    if (opts.exitAfter !== undefined) {
      setTimeout(() => {
        child.exitCode = opts.exitAfter;
        child.emit("exit", opts.exitAfter, null);
        child.emit("close", opts.exitAfter, null);
      }, 80);
    }
    return child;
  };
  fn.calls = calls;
  return fn;
}

function makeIo() {
  const out = [];
  const err = [];
  return {
    io: {
      stdout: { write: (chunk) => out.push(String(chunk)) },
      stderr: { write: (chunk) => err.push(String(chunk)) },
    },
    all: () => out.join("") + err.join(""),
    errors: () => err.join(""),
  };
}

function makeWindow(opts) {
  const w = {
    calls: [],
    closeCalled: false,
    openWindow: async (arg) => {
      w.calls.push(arg);
      return {
        closed: opts && opts.closed ? opts.closed : new Promise(() => {}),
        close: () => { w.closeCalled = true; },
      };
    },
  };
  return w;
}

function assertNoSecrets(io, w) {
  const text = io.all();
  assert.ok(!text.includes(TOKEN), "输出里出现了控制令牌：" + text);
  assert.ok(!text.includes(NONCE), "输出里出现了 nonce：" + text);
  for (const arg of w.calls) {
    assert.ok(!JSON.stringify(arg).includes(TOKEN), "openWindow 的参数里出现了控制令牌");
  }
}

test("参数错：退出码 2、不开窗口、不起服务", async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--assets", d.assets],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 2);
  assert.equal(w.calls.length, 0);
  assert.equal(spawn.calls.length, 0);
  assert.ok(io.errors().includes("ERROR: "), io.errors());
});

test("指定的 Python 不可用：退出码 1、不起服务、不开窗口", async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "t025-no-such-python-xyz"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.equal(spawn.calls.length, 0);
  assert.equal(w.calls.length, 0);
  assert.ok(io.errors().includes("ERROR: "), io.errors());
});

test("正常流程：关窗口、服务以 0 退出 → 0；openWindow 只收 bootstrap 与 origin", async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow({ closed: Promise.resolve() });
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 0, io.all());
  assert.equal(w.calls.length, 1);
  assert.deepEqual(Object.keys(w.calls[0]).sort(), ["bootstrap", "origin"]);
  assert.equal(w.calls[0].origin, ORIGIN);
  assertNoSecrets(io, w);
});

test("服务意外退出：退出码 1、stderr 有退出码、窗口被关掉", async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitAfter: 3 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.ok(io.errors().includes("服务意外退出（退出码 3）"), io.errors());
  assert.equal(w.closeCalled, true);
  assertNoSecrets(io, w);
});

test("关窗口后服务以 7 退出：退出码 1", async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow({ closed: Promise.resolve() });
  const spawn = fakeSpawn({ exitOnStdinEnd: 7 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.ok(io.errors().includes("服务没有以 0 正常退出"), io.errors());
  assertNoSecrets(io, w);
});
