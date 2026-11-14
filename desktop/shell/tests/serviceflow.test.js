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

test("starting/running 时再 start → busy，不起第二个进程", async () => {
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

test("exited 之后能再 start：run1 意外退出（码 3）→ run2 starting → running", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn });
  seen.subscribe(flow);
  // run1：握手成功后 60ms 以码 3 自己退出（不是外壳停的）
  assert.deepEqual(await flow.start({ repo: "run-1", command: [process.execPath, FAKE_EXIT] }), {
    ok: true,
    value: null,
  });
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(flow.state().exitCode, 3);
  assert.equal(seen.states.length, 3);
  // run2：exited 之后还能再 start（状态不被旧 run 卡住）
  assert.deepEqual(
    await flow.start({
      repo: "run-2",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "ok" }),
    }),
    { ok: true, value: null },
  );
  assert.equal(rec.children.length, 2, "第二次 start 要真的起进程");
  assert.deepEqual(seen.states[3], { kind: "starting", repo: "run-2" });
  assert.equal(seen.states[4].kind, "running");
  assert.equal(seen.states[4].repo, "run-2");
  assert.deepEqual(flow.state(), seen.states[4]);
  await flow.stop();
  await waitFor("run2 exited", () => flow.state().kind === "exited" && flow.state().exitCode === 0, 8000);
});

test("byShell 按 run 算：run1 被 stop（true），run2 意外退出仍是 false", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  assert.deepEqual(
    await flow.start({
      repo: "s-1",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "ok" }),
    }),
    { ok: true, value: null },
  );
  await flow.stop();
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(seen.infos[2].byShell, true, "run1 是外壳停的");
  // run2：服务自己退出 → 上一 run 的 stopping 不许继承
  assert.deepEqual(await flow.start({ repo: "s-2", command: [process.execPath, FAKE_EXIT] }), {
    ok: true,
    value: null,
  });
  await waitFor("run2 exited", () => seen.states.length >= 6 && seen.states[5].kind === "exited", 8000);
  assert.equal(seen.states[5].exitCode, 3);
  assert.equal(seen.infos[5].byShell, false, "run2 的意外退出不是外壳结束的，标志不许继承");
});

test("旧 run 的子进程退出不许把新 run 改成 exited", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 700 });
  seen.subscribe(flow);
  // run1：握手超时 → exited(-1)；子进程已被 kill，它的 exit 什么时候派发不定
  assert.deepEqual(
    await flow.start({
      repo: "old-1",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "silent" }),
    }),
    { ok: false, reason: "handshake-failed" },
  );
  assert.equal(flow.state().kind, "exited");
  assert.equal(rec.children.length, 1);
  // run2：立刻再起，握手成功
  assert.deepEqual(
    await flow.start({
      repo: "new-2",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "ok" }),
    }),
    { ok: true, value: null },
  );
  assert.equal(flow.state().kind, "running");
  await waitFor(
    "旧子进程退出",
    () => rec.children[0].exitCode !== null || rec.children[0].signalCode !== null,
    5000,
  );
  await new Promise((resolve) => setTimeout(resolve, 250));
  assert.equal(flow.state().kind, "running", "旧 run 的 exit 回调不许把新 run 改成 exited");
  assert.equal(seen.states.length, 4, JSON.stringify(seen.states));
  await flow.stop();
  await waitFor("run2 exited", () => flow.state().kind === "exited", 8000);
});

test("跑起来之后服务自己退出（退出码 1）→ exited 带 afterRunning: true、byShell 为假", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  assert.deepEqual(
    await flow.start({
      repo: "r-self-1",
      command: [process.execPath, FAKE_EXIT],
      env: envWith({ FAKE_SERVICE_EXIT_CODE: "1" }),
    }),
    { ok: true, value: null },
  );
  assert.equal("afterRunning" in seen.states[0], false, "starting 不带键");
  assert.equal("afterRunning" in seen.states[1], false, "running 不带键");
  await waitFor("服务自己退出", () => seen.states.length >= 3 && seen.states[2].kind === "exited", 8000);
  assert.equal(seen.states[2].exitCode, 1, "跑起来之后的退出码 1 也原样给出");
  assert.equal(seen.states[2].afterRunning, true, "跑起来之后的退出带 afterRunning: true（与退出码无关）");
  assert.equal(seen.infos[2].byShell, false, "服务自己退出的 byShell 照旧为假");
  assert.equal(flow.state().afterRunning, true, "getState 与事件负载是同一个对象");
});

test("跑起来之后外壳 stop() → exited 带 afterRunning: true、byShell 为真", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  assert.deepEqual(
    await flow.start({
      repo: "r-stop-key",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "ok" }),
    }),
    { ok: true, value: null },
  );
  const stop = await flow.stop();
  assert.equal(stop.exited, true, JSON.stringify(stop));
  await waitFor("stop 之后的 exited", () => seen.states.length >= 3 && seen.states[2].kind === "exited");
  assert.equal(seen.states[2].afterRunning, true, "跑起来之后被外壳停掉也带 afterRunning: true");
  assert.equal(seen.infos[2].byShell, true, "外壳停服务触发的 exited，byShell 照旧为真");
});

test("onRunning 抛错 → 收服务（stop 语义）之后的 exited 带 afterRunning: true", async () => {
  const seen = collect();
  const flow = createServiceFlow({
    onRunning: () => {
      throw new Error("窗口开不了");
    },
  });
  seen.subscribe(flow);
  assert.deepEqual(
    await flow.start({
      repo: "r-onrun-key",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "ok" }),
    }),
    { ok: false, reason: "start-failed" },
  );
  assert.equal(seen.states[1].kind, "running", "running 先发，onRunning 之后才轮到失败处理");
  await waitFor("收服务之后的 exited", () => seen.states.length >= 3 && seen.states[2].kind === "exited", 8000);
  assert.equal(seen.states[2].exitCode, 0, "收服务走 stop 的语义（stdin EOF），假服务以 0 退出");
  assert.equal(seen.states[2].afterRunning, true, "跑起来之后的收服务也带 afterRunning: true");
});

test("启动阶段的 exited 一律不带 afterRunning 键（exit2、坏握手、握手超时、spawn 失败）", async () => {
  {
    const seen = collect();
    const flow = createServiceFlow({});
    seen.subscribe(flow);
    const envelope = await flow.start({
      repo: "r-exit2-key",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
    });
    assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
    assert.equal(seen.states[1].kind, "exited");
    assert.equal(seen.states[1].exitCode, 2);
    assert.equal("afterRunning" in seen.states[1], false, "握手前退出（启动阶段）不带键");
    assert.equal(seen.infos[1].byShell, false);
    assert.deepEqual(flow.state(), { kind: "exited", repo: "r-exit2-key", exitCode: 2, at: seen.states[1].at }, "启动失败的 exited 仍只认 4 个键");
  }
  {
    const seen = collect();
    const flow = createServiceFlow({});
    seen.subscribe(flow);
    const envelope = await flow.start({
      repo: "r-bad-key",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "bad" }),
    });
    assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
    assert.equal(seen.states[1].exitCode, -1, "被外壳杀掉的进程没有数字码 → -1");
    assert.equal("afterRunning" in seen.states[1], false, "坏握手（启动阶段）不带键");
  }
  {
    const seen = collect();
    const flow = createServiceFlow({ timeoutMs: 700 });
    seen.subscribe(flow);
    const envelope = await flow.start({
      repo: "r-silent-key",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "silent" }),
    });
    assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
    assert.equal(seen.states[1].exitCode, -1);
    assert.equal("afterRunning" in seen.states[1], false, "握手超时（启动阶段）不带键");
  }
  {
    const seen = collect();
    const flow = createServiceFlow({});
    seen.subscribe(flow);
    const envelope = await flow.start({ repo: "r-enoent-key", command: ["themistally-no-such-bin-xyz", "arg"] });
    assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
    assert.equal(seen.states[1].exitCode, -1);
    assert.equal("afterRunning" in seen.states[1], false, "spawn 失败（启动阶段）不带键");
  }
});

test("starting 期间 abort() 的 exited 不带 afterRunning 键（此刻还不是 running）", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 8000 });
  seen.subscribe(flow);
  const startPromise = flow.start({
    repo: "r-abort-key",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting 状态", () => seen.states.length >= 1 && seen.states[0].kind === "starting");
  await flow.abort();
  await waitFor("abort 之后的 exited", () => seen.states.length >= 2 && seen.states[1].kind === "exited", 5000);
  assert.equal(seen.states[1].exitCode, -1);
  assert.equal("afterRunning" in seen.states[1], false, "starting 期间 abort（启动阶段）不带键");
  assert.equal(seen.infos[1].byShell, true, "外壳中止的退出 byShell 照旧为真");
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

test("afterRunning 按 run 算：run1 跑起来之后退出（带键），run2 启动阶段失败（不带键）", async () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  assert.deepEqual(
    await flow.start({
      repo: "key-run-1",
      command: [process.execPath, FAKE_EXIT],
      env: envWith({ FAKE_SERVICE_EXIT_CODE: "1" }),
    }),
    { ok: true, value: null },
  );
  await waitFor("run1 退出", () => seen.states.length >= 3 && seen.states[2].kind === "exited", 8000);
  assert.equal(seen.states[2].exitCode, 1);
  assert.equal(seen.states[2].afterRunning, true, "run1 是跑起来之后退出的，要带键");
  assert.equal(seen.states.length, 3, JSON.stringify(seen.states.map((s) => s.kind)));
  const envelope2 = await flow.start({
    repo: "key-run-2",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
  });
  assert.deepEqual(envelope2, { ok: false, reason: "handshake-failed" });
  const run2 = seen.states.slice(3);
  assert.equal(run2.length, 2, JSON.stringify(seen.states.map((s) => s.kind)));
  assert.equal(run2[0].kind, "starting", "新 run 先进 starting");
  assert.equal(run2[1].kind, "exited");
  assert.equal(run2[1].exitCode, 2);
  assert.equal("afterRunning" in run2[1], false, "run2 是启动阶段的失败，不继承上一 run 的键");
});
