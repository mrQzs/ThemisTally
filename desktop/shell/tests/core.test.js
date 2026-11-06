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
  const state = { stdinEnded: false, exit: null };
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
      state.stdinEnded = true;
      setTimeout(() => {
        state.exit = opts.exitOnStdinEnd;
        child.exitCode = opts.exitOnStdinEnd;
        child.emit("exit", opts.exitOnStdinEnd, null);
        child.emit("close", opts.exitOnStdinEnd, null);
      }, 30);
    };
    child.stdin.on("finish", onEnd);
    child.stdin.on("close", onEnd);
    child.stdout.write(HS);
    if (opts.exitAfterHandshake !== undefined) {
      // 握手行写完立刻退出：服务在开窗口完成之前就已经没了
      setImmediate(() => {
        state.exit = opts.exitAfterHandshake;
        child.exitCode = opts.exitAfterHandshake;
        child.emit("exit", opts.exitAfterHandshake, null);
        child.emit("close", opts.exitAfterHandshake, null);
      });
    }
    if (opts.exitAfter !== undefined) {
      setTimeout(() => {
        state.exit = opts.exitAfter;
        child.exitCode = opts.exitAfter;
        child.emit("exit", opts.exitAfter, null);
        child.emit("close", opts.exitAfter, null);
      }, 80);
    }
    return child;
  };
  fn.calls = calls;
  fn.state = state;
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

test("窗口在 openWindow 返回前就关了：仍走「关窗口」收尾，退出码 0", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  let resolveClosed;
  const closed = new Promise((resolve) => {
    resolveClosed = resolve;
  });
  let closeCalled = false;
  const openWindow = async () => {
    // 页面还在加载，用户就关了窗口：closed 在 openWindow 返回之前兑现
    await new Promise((resolve) => setTimeout(resolve, 20));
    resolveClosed();
    await new Promise((resolve) => setTimeout(resolve, 20));
    return {
      closed,
      close: () => {
        closeCalled = true;
      },
    };
  };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
  });
  assert.equal(code, 0, io.all());
  assert.equal(spawn.state.stdinEnded, true, "关窗口后必须关 stdin 收服务");
  assert.equal(spawn.state.exit, 0);
  assert.equal(closeCalled, false, "窗口已经关了，不必再 close");
  assert.ok(!io.all().includes(TOKEN) && !io.all().includes(NONCE), io.all());
});

test("服务在握手后、开窗口完成前以 3 退出：退出码 1、stderr 有退出码、窗口被关掉", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  let closeCalled = false;
  const openWindow = async () => {
    // 开窗口要花时间（真机上 loadURL 如此）：服务在这段时间里退出，'exit' 不许漏掉
    await new Promise((resolve) => setTimeout(resolve, 40));
    return {
      closed: new Promise(() => {}),
      close: () => {
        closeCalled = true;
      },
    };
  };
  const spawn = fakeSpawn({ exitAfterHandshake: 3 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1, io.all());
  assert.ok(io.errors().includes("服务意外退出（退出码 3）"), io.errors());
  assert.equal(closeCalled, true);
  assert.ok(!io.all().includes(TOKEN) && !io.all().includes(NONCE), io.all());
});

test("服务在开窗口之前就已经没了：一行 ERROR、不开窗口、退出码 1", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const w = makeWindow();
  const child = new EventEmitter();
  child.stdout = new PassThrough();
  child.stdin = new PassThrough();
  child.kill = () => {};
  const spawn = (command, args) => {
    assert.ok(Array.isArray(command) && Array.isArray(args) && args.length === 0);
    // 握手行与退出都在 spawn 里同步发生：core 注册监听时服务已经没了
    child.stdout.write(HS);
    child.exitCode = 5;
    child.emit("exit", 5, null);
    return child;
  };
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1, io.all());
  assert.ok(io.errors().includes("服务意外退出（退出码 5）"), io.errors());
  assert.equal(w.calls.length, 0, "服务已死就不该开窗口");
  assert.equal(w.closeCalled, false);
  assertNoSecrets(io, w);
});

test("openWindow 失败：一行 ERROR、收干净子进程、退出码 1", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const openWindow = async () => {
    // 真机上 loadURL 的拒绝里带着整条引导地址（含 nonce），外壳不许把它回显出来
    const err = new Error(`ERR_FAILED (-2) loading ${ORIGIN}/bootstrap/${NONCE}`);
    throw err;
  };
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1, io.all());
  const lines = io.errors().split("\n").filter((line) => line.startsWith("ERROR: "));
  assert.equal(lines.length, 1, io.errors());
  assert.ok(io.errors().includes("打开窗口失败"), io.errors());
  assert.equal(spawn.state.stdinEnded, true, "失败也要关 stdin 收服务");
  assert.equal(spawn.state.exit, 0);
  assert.ok(!io.all().includes(NONCE), io.all());
  assert.ok(!io.all().includes("/bootstrap/"), io.all());
});

test("开窗口期间服务退出导致 openWindow 失败：报的是服务意外退出，退出码 1", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const child = new EventEmitter();
  child.stdout = new PassThrough();
  child.stdin = new PassThrough();
  child.kill = () => {};
  const spawn = (command, args) => {
    assert.ok(Array.isArray(command) && Array.isArray(args) && args.length === 0);
    child.stdout.write(HS);
    setTimeout(() => {
      child.exitCode = 4;
      child.emit("exit", 4, null);
      child.emit("close", 4, null);
    }, 10);
    return child;
  };
  const openWindow = async () => {
    await new Promise((resolve) => setTimeout(resolve, 25));
    throw new Error(`ERR_FAILED (-2) loading ${ORIGIN}/bootstrap/${NONCE}`);
  };
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1, io.all());
  assert.ok(io.errors().includes("服务意外退出（退出码 4）"), io.errors());
  assert.ok(!io.all().includes(NONCE), io.all());
});

test("不传 io：参数错时用默认的 process.stderr 写一行 ERROR，退出码 2", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const chunks = [];
  const original = process.stderr.write.bind(process.stderr);
  process.stderr.write = (chunk) => {
    chunks.push(String(chunk));
    return true;
  };
  t.after(() => {
    process.stderr.write = original;
  });
  const w = makeWindow();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--assets", d.assets],
    openWindow: w.openWindow,
    spawn,
    env: process.env,
  });
  assert.equal(code, 2);
  assert.equal(w.calls.length, 0);
  assert.equal(spawn.calls.length, 0);
  assert.ok(chunks.join("").includes("ERROR: "), chunks.join(""));
});

test("onServiceReady 在 openWindow 之前调用，收到恰好 origin、control、repo 三键", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const events = [];
  const openWindow = async (arg) => {
    events.push(["openWindow", arg]);
    return { closed: Promise.resolve(), close: () => {} };
  };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
    onServiceReady: (arg) => { events.push(["onServiceReady", arg]); },
  });
  assert.equal(code, 0, io.all());
  assert.equal(events.length, 2, JSON.stringify(events.map((e) => e[0])));
  assert.equal(events[0][0], "onServiceReady", "onServiceReady 必须在 openWindow 之前");
  assert.equal(events[1][0], "openWindow");
  assert.deepEqual(Object.keys(events[0][1]).sort(), ["control", "origin", "repo"]);
  assert.equal(events[0][1].origin, ORIGIN);
  assert.equal(events[0][1].control, TOKEN);
  assert.equal(events[0][1].repo, path.resolve(d.repo));
  // 令牌绝不进 openWindow
  assert.ok(!JSON.stringify(events[1][1]).includes(TOKEN));
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(spawn.state.stdinEnded, true, "关窗后要收服务（stdin 结束）");
  assertNoSecrets(io, { calls: [] });
});

test("onServiceReady 抛错：一行 ERROR、不开窗口、收服务、退出码 1", { timeout: 5000 }, async (t) => {
  const d = makeDirs(t);
  const io = makeIo();
  const openCalls = [];
  const openWindow = async (arg) => { openCalls.push(arg); return { closed: Promise.resolve(), close: () => {} }; };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
    onServiceReady: () => { throw new Error("令牌侧出问题"); },
  });
  assert.equal(code, 1);
  assert.equal(openCalls.length, 0);
  const lines = io.errors().split("\n").filter((line) => line.trim().length > 0);
  assert.equal(lines.length, 1, "必须只写一行 ERROR：" + JSON.stringify(lines));
  assert.ok(lines[0].startsWith("ERROR: "), JSON.stringify(lines));
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(spawn.state.stdinEnded, true, "抛错也要收服务");
  assert.ok(!io.all().includes(TOKEN), io.all());
});

test("不传 onServiceReady：一切照旧，openWindow 仍只收 bootstrap 与 origin", { timeout: 5000 }, async (t) => {
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
