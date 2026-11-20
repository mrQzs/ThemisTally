"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHostRelay } = require("../src/hostrelay.js");
const { registerHostIpc } = require("../src/ipc.js");
const { createServiceFlow } = require("../src/serviceflow.js");

const FAKE = path.join(__dirname, "fixtures", "fake-service.js");
const FAKE_EXIT = path.join(__dirname, "fixtures", "fake-service-exit.js");

const METHODS = ["reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme", "listRepos", "switchRepo", "addRepo"];

function makeHost(tag) {
  const calls = {};
  const host = {};
  for (const name of METHODS) {
    calls[name] = [];
    host[name] = async (...args) => {
      calls[name].push(args);
      return { ok: true, value: tag + ":" + name };
    };
  }
  return { host, calls };
}

function envWith(extra) {
  return Object.assign({}, process.env, extra);
}

// 等状态：轮询，不固定等几百毫秒
async function waitFor(what, predicate, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 8000);
  for (;;) {
    if (predicate()) return;
    if (Date.now() > deadline) throw new Error("等不到：" + what);
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

test("形状：{host, senderAllowed, use, clear}，host 是那十个方法", () => {
  const relay = createHostRelay();
  assert.deepEqual(Object.keys(relay).sort(), ["clear", "host", "senderAllowed", "use"]);
  assert.deepEqual(Object.keys(relay.host).sort(), [...METHODS].sort());
});

test("没有当前 host：十个方法都回 forbidden 不抛错；senderAllowed 为 false", async () => {
  const relay = createHostRelay();
  for (const name of METHODS) {
    assert.deepEqual(await relay.host[name]("a", 2), { ok: false, reason: "forbidden" }, name + " 不许抛错");
  }
  assert.equal(relay.senderAllowed({}), false);
});

test("use 替换不叠加：实参原样转给当前 host；clear 之后回到 forbidden", async () => {
  const relay = createHostRelay();
  const a = makeHost("A");
  const b = makeHost("B");
  relay.use(a.host, (event) => event.tag === "a");
  assert.deepEqual(await relay.host.reveal("p/q"), { ok: true, value: "A:reveal" });
  assert.deepEqual(a.calls.reveal[0], ["p/q"], "实参要原样转发");
  assert.equal(relay.senderAllowed({ tag: "a" }), true);
  assert.equal(relay.senderAllowed({ tag: "b" }), false);
  relay.use(b.host, (event) => event.tag === "b");
  assert.deepEqual(await relay.host.reveal("x"), { ok: true, value: "B:reveal" });
  assert.equal(a.calls.reveal.length, 1, "换成新 host 之后旧 host 不再被调");
  assert.equal(b.calls.reveal.length, 1);
  assert.equal(relay.senderAllowed({ tag: "a" }), false, "来源检查也要换成新的");
  // 实参个数不丢：openSecretWindow 收两个、notify 收一个、saveTheme 收一个
  await relay.host.openSecretWindow("http://x/y", "job-7");
  await relay.host.notify("attempt-finished");
  await relay.host.saveTheme("dark");
  assert.deepEqual(b.calls.openSecretWindow[0], ["http://x/y", "job-7"]);
  assert.deepEqual(b.calls.notify[0], ["attempt-finished"]);
  assert.deepEqual(b.calls.saveTheme[0], ["dark"], "saveTheme 只转交这一个实参");
  relay.clear();
  assert.deepEqual(await relay.host.notify("attempt-finished"), { ok: false, reason: "forbidden" });
  assert.deepEqual(await relay.host.saveTheme("dark"), { ok: false, reason: "forbidden" }, "clear 之后 saveTheme 也回 forbidden");
  assert.equal(relay.senderAllowed({ tag: "b" }), false);
  assert.equal(a.calls.notify.length, 0, "clear 之后的调用不进旧 host");
  assert.equal(b.calls.notify.length, 1, "clear 之后的调用不进当前 host（计数不涨）");
});

test("三个新方法（T064）转给当前 host、实参照传；没有当前 host 回 forbidden", async () => {
  const relay = createHostRelay();
  assert.deepEqual(await relay.host.listRepos(), { ok: false, reason: "forbidden" }, "没有当前 host 不抛错");
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: false, reason: "forbidden" });
  assert.deepEqual(await relay.host.addRepo(), { ok: false, reason: "forbidden" });
  const calls = [];
  relay.use({
    listRepos: async () => { calls.push("listRepos"); return { ok: true, repos: [{ id: "a", name: "a", current: true }] }; },
    switchRepo: async (id) => { calls.push(["switch", id]); return { ok: true }; },
    addRepo: async () => { calls.push("addRepo"); return { ok: false, reason: "cancelled" }; },
  }, () => true);
  assert.deepEqual(await relay.host.listRepos(), { ok: true, repos: [{ id: "a", name: "a", current: true }] });
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: true });
  assert.deepEqual(await relay.host.addRepo(), { ok: false, reason: "cancelled" });
  assert.deepEqual(calls, ["listRepos", ["switch", "b"], "addRepo"], "实参原样转给当前 host");
  relay.clear();
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: false, reason: "forbidden" }, "clear 之后回到没有 host");
});

test("senderAllowed 的检查抛错按 false", () => {
  const relay = createHostRelay();
  relay.use(makeHost("C").host, () => {
    throw new Error("boom");
  });
  assert.equal(relay.senderAllowed({}), false);
});

// 重入：同一个外壳进程里第二次起服务。宿主 IPC 只注册一次，否则 Electron 对同一通道第二次
// handle 会抛错——假 im 的 handle 遇到重复通道就抛错，照 Electron 的行为
test("重入：第一次意外退出、第二次起服务成功，注册次数仍是 10、调用进第二个 host", async () => {
  const handlers = new Map();
  let registrations = 0;
  const im = {
    handle: (channel, fn) => {
      if (handlers.has(channel)) throw new Error("通道被重复注册：" + channel);
      handlers.set(channel, fn);
      registrations += 1;
    },
  };
  const relay = createHostRelay();
  registerHostIpc(im, relay.host, relay.senderAllowed);
  assert.equal(registrations, 10, "registerHostIpc 注册十条通道");
  assert.equal(handlers.size, 10);
  // 还没有当前 host：调用经来源检查回 forbidden
  assert.deepEqual(await handlers.get("themis-host:notify")({ tag: "x" }, "attempt-finished"), {
    ok: false,
    reason: "forbidden",
  });

  const first = makeHost("host1");
  const second = makeHost("host2");
  let runCount = 0;
  const flow = createServiceFlow({
    onRunning: async () => {
      runCount += 1;
      if (runCount === 1) relay.use(first.host, () => true);
      else relay.use(second.host, () => true);
    },
  });

  // 第一次：握手成功后服务自己退出（意外退出）
  assert.deepEqual(await flow.start({ repo: "r1", command: [process.execPath, FAKE_EXIT] }), {
    ok: true,
    value: null,
  });
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(flow.state().exitCode, 3);
  const event = { tag: "run1" };
  assert.deepEqual(await handlers.get("themis-host:notify")(event, "attempt-finished"), {
    ok: true,
    value: "host1:notify",
  });

  // 第二次：真起服务成功（exited 之后能再 start）
  assert.deepEqual(
    await flow.start({ repo: "r2", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: true, value: null },
  );
  assert.equal(flow.state().kind, "running");
  // 没有第二次注册（否则 im.handle 早就抛错了）
  assert.equal(registrations, 10, "第二次起服务不许再注册宿主 IPC");
  assert.equal(handlers.size, 10);
  assert.deepEqual(await handlers.get("themis-host:reveal")(event, "runs/x/summary.md"), {
    ok: true,
    value: "host2:reveal",
  });
  assert.equal(second.calls.reveal.length, 1);
  assert.deepEqual(second.calls.reveal[0], ["runs/x/summary.md"]);
  assert.equal(first.calls.reveal.length, 0, "旧 host 不再被调");
  assert.equal(relay.senderAllowed(event), true, "来源检查转给当前那份");
  await flow.stop();
  await waitFor("run2 exited", () => flow.state().kind === "exited" && flow.state().exitCode === 0, 8000);
});
