"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createServiceFlow } = require("../src/serviceflow.js");

const FAKE = path.join(__dirname, "fixtures", "fake-service.js");
const FAKE_EXIT = path.join(__dirname, "fixtures", "fake-service-exit.js");

// 借 spawn 选项拿到子进程的引用：createServiceFlow 会把它包一层再传给 src/service.js，
// 这里再包一层只为了记录 child（与被测的包装层互不干扰）
function recordingSpawn() {
  const children = [];
  const fn = (command, args, options) => {
    const child = spawn(command[0], command.slice(1), options);
    children.push(child);
    return child;
  };
  return { fn, children };
}

function envWith(extra) {
  return Object.assign({}, process.env, extra);
}

// 等子进程或等状态：轮询，不固定等几百毫秒
async function waitFor(what, predicate, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 8000);
  for (;;) {
    if (predicate()) return;
    if (Date.now() > deadline) throw new Error("等不到：" + what);
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

function hasToken(value) {
  return JSON.stringify(value).includes("ctrl-tok");
}

function collect() {
  const states = [];
  const infos = [];
  const subscribe = (flow) =>
    flow.subscribe((state, info) => {
      states.push(JSON.parse(JSON.stringify(state)));
      infos.push(info);
    });
  return { states, infos, subscribe };
}

test("start：starting → running，pid 取握手、startedAt 是 ISO 串", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  let onRunningArg = null;
  const flow = createServiceFlow({
    spawn: rec.fn,
    onRunning: (arg) => {
      onRunningArg = arg;
    },
  });
  seen.subscribe(flow);
  assert.deepEqual(flow.state(), { kind: "idle" }, "初始状态是 idle");
  const envelope = await flow.start({
    repo: "repo-id-1",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.deepEqual(seen.states, [
    { kind: "starting", repo: "repo-id-1" },
    { kind: "running", repo: "repo-id-1", pid: 4242, startedAt: seen.states[1].startedAt },
  ]);
  assert.ok(Number.isFinite(Date.parse(seen.states[1].startedAt)), "startedAt 要是 ISO 串");
  assert.deepEqual(flow.state(), seen.states[1], "getState 与事件一致");
  // 控制令牌只进 onRunning 的实参
  assert.equal(onRunningArg.control, "ctrl-tok-XYZ");
  assert.equal(onRunningArg.repo, "repo-id-1");
  assert.equal(typeof onRunningArg.origin, "string");
  for (const state of seen.states) assert.ok(!hasToken(state), JSON.stringify(state));
  assert.ok(!hasToken(flow.state()));
  await flow.stop();
});

test("stop：干净关停 → exited、退出码 0、byShell 为真", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn });
  seen.subscribe(flow);
  await flow.start({
    repo: "repo-stop",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  const stop = await flow.stop();
  assert.equal(stop.exited, true, JSON.stringify(stop));
  assert.equal(stop.code, 0, JSON.stringify(stop));
  assert.equal(stop.signal, null, JSON.stringify(stop));
  await waitFor("stop 之后的 exited", () => seen.states.length >= 3 && seen.states[2].kind === "exited");
  assert.equal(seen.states[2].repo, "repo-stop");
  assert.equal(seen.states[2].exitCode, 0);
  assert.equal(typeof seen.states[2].at, "number", "at 是数字毫秒");
  assert.equal(seen.infos[2].byShell, true, "外壳停服务触发的 exited，byShell 要为真");
  assert.equal(flow.state().kind, "exited");
});

test("握手前退出（exit2）→ exited 带数字码 2、回 handshake-failed", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  const envelope = await flow.start({
    repo: "r-exit2",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  assert.deepEqual(seen.states, [
    { kind: "starting", repo: "r-exit2" },
    { kind: "exited", repo: "r-exit2", exitCode: 2, at: seen.states[1].at },
  ]);
  assert.equal(typeof seen.states[1].at, "number");
});

test("坏握手（bad）→ exited exitCode -1、handshake-failed", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  const envelope = await flow.start({
    repo: "r-bad",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "bad" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  assert.equal(seen.states[1].kind, "exited");
  assert.equal(seen.states[1].exitCode, -1, "被外壳杀掉的进程没有数字码 → -1");
  assert.equal(flow.state().kind, "exited");
});

test("握手超时（silent + 短 timeoutMs）→ exited exitCode -1、handshake-failed", async () => {
  const seen = collect();
  const flow = createServiceFlow({ timeoutMs: 700 });
  seen.subscribe(flow);
  const envelope = await flow.start({
    repo: "r-silent",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  assert.equal(flow.state().kind, "exited");
  assert.equal(flow.state().exitCode, -1, "超时被杀的进程没有数字码 → -1");
});

test("spawn 失败（ENOENT）→ exited exitCode -1、回 start-failed", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  const envelope = await flow.start({ repo: "r-enoent", command: ["themistally-no-such-bin-xyz", "arg"] });
  assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
  assert.equal(seen.states[1].kind, "exited");
  assert.equal(seen.states[1].exitCode, -1);
  assert.equal(flow.state().kind, "exited");
});

test("握手成功后服务自己退出 → exited 带数字码、byShell 为假", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  const envelope = await flow.start({ repo: "r-self-exit", command: [process.execPath, FAKE_EXIT] });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.equal(seen.states[1].kind, "running");
  await waitFor("服务自己退出", () => seen.states.length >= 3 && seen.states[2].kind === "exited", 8000);
  assert.equal(seen.states[2].repo, "r-self-exit");
  assert.equal(seen.states[2].exitCode, 3, "FAKE_SERVICE_EXIT_CODE 缺省 3");
  assert.equal(seen.infos[2].byShell, false, "服务自己退出的 byShell 要为假");
  assert.equal(flow.state().kind, "exited");
  for (const state of seen.states) assert.ok(!hasToken(state), JSON.stringify(state));
});

test("starting 期间 abort()：子进程真的退出（不留孤儿）、状态 exited、byShell 为真", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 8000 });
  seen.subscribe(flow);
  const startPromise = flow.start({
    repo: "r-abort",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting 状态", () => seen.states.length >= 1 && seen.states[0].kind === "starting");
  await flow.abort();
  assert.equal(rec.children.length, 1, "spawn 只被调一次");
  const child = rec.children[0];
  // 轮询子进程状态，不固定等几百毫秒
  await waitFor("子进程退出", () => child.exitCode !== null || child.signalCode !== null, 5000);
  await waitFor("abort 之后的 exited", () => seen.states.length >= 2 && seen.states[1].kind === "exited", 5000);
  assert.equal(seen.states[1].exitCode, -1, "被杀掉的进程没有数字码 → -1");
  assert.equal(seen.infos[1].byShell, true, "外壳中止的退出 byShell 要为真");
  assert.equal(flow.state().kind, "exited");
  let late;
  const settled = await Promise.race([
    startPromise,
    new Promise((_, reject) => {
      late = setTimeout(() => reject(new Error("abort 之后 start 的信封没有兑现")), 8000);
    }),
  ]);
  clearTimeout(late);
  assert.equal(typeof settled.ok, "boolean", "start 的信封要兑现，不 reject");
});

test("订阅相互独立：退订只删自己那条、可重复退订", async () => {
  const seen = collect();
  const other = [];
  const flow = createServiceFlow({});
  const offSeen = seen.subscribe(flow);
  const offOther = flow.subscribe((state) => other.push(JSON.parse(JSON.stringify(state))));
  await flow.start({
    repo: "r-sub",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.equal(seen.states.length, 2);
  assert.equal(other.length, 2);
  offSeen();
  assert.doesNotThrow(() => offSeen(), "重复退订不抛错");
  await flow.stop();
  await waitFor("stop 之后的 exited", () => other.length >= 3, 8000);
  assert.equal(seen.states.length, 2, "退订之后不再收到");
  assert.equal(other.length, 3, "别的订阅照常收到");
  assert.equal(other[2].kind, "exited");
  offOther();
});

test("onRunning 抛错 → 收服务、状态置 exited、回 start-failed", async () => {
  const seen = collect();
  const flow = createServiceFlow({
    onRunning: () => {
      throw new Error("窗口开不了");
    },
  });
  seen.subscribe(flow);
  const envelope = await flow.start({
    repo: "r-onrun-fail",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
  assert.equal(seen.states[1].kind, "running", "running 先发，onRunning 之后才轮到失败处理");
  await waitFor("收服务之后的 exited", () => seen.states.length >= 3 && seen.states[2].kind === "exited", 8000);
  assert.equal(seen.states[2].exitCode, 0, "收服务走 stop 的语义（stdin EOF），假服务以 0 退出");
  assert.equal(flow.state().kind, "exited");
});

test("不是 idle 时再 start → busy，不起第二个进程", async () => {
  const rec = recordingSpawn();
  const flow = createServiceFlow({ spawn: rec.fn });
  await flow.start({
    repo: "r-busy",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(await flow.start({ repo: "r-busy", command: [process.execPath, FAKE] }), {
    ok: false,
    reason: "busy",
  });
  assert.equal(rec.children.length, 1, "busy 不许再起进程");
  await flow.stop();
});
