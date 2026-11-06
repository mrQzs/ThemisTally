"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { EventEmitter } = require("node:events");
const { PassThrough } = require("node:stream");
const { spawn } = require("node:child_process");
const { serviceCommand, startService, stopService } = require("../src/service.js");

const NODE = process.execPath;
const SVC = path.join(__dirname, "fixtures", "fake-service.js");
const HANDSHAKE_LINE = JSON.stringify({
  themis_ui: 1,
  bootstrap: "http://127.0.0.1:8123/bootstrap/nonceABC",
  origin: "http://127.0.0.1:8123",
  control: "ctrl-tok-XYZ",
  pid: 4242,
}) + "\n";

function svcOptions(mode, extra) {
  return Object.assign({
    command: [NODE, SVC],
    timeoutMs: 5000,
    env: Object.assign({}, process.env, { FAKE_SERVICE_MODE: mode }),
  }, extra || {});
}

test("serviceCommand：参数列表、空格 & \" % 原样、--repo 在 ui 之前", () => {
  const python = ["py", "-3"];
  const kit = "C:/Kit Dir";
  const repo = "C:/My Repo&a";
  const assets = "C:/As\"sets%";
  const argv = serviceCommand({ python, kit, repo, assets, transcripts: ["t one", "t&two", "q\"uote%"] });
  assert.ok(Array.isArray(argv));
  assert.deepEqual(argv.slice(0, 2), python);
  assert.equal(path.normalize(argv[2]), path.normalize(path.join(kit, "scripts", "pi_dispatch.py")));
  assert.equal(argv[3], "--repo");
  assert.equal(argv[4], repo);
  assert.equal(argv[5], "ui");
  assert.equal(argv[6], "--desktop");
  assert.equal(argv[7], "--assets");
  assert.equal(argv[8], assets);
  assert.deepEqual(argv.slice(9), ["--transcript", "t one", "--transcript", "t&two", "--transcript", "q\"uote%"]);
});

test("serviceCommand：没有 transcripts 就没有 --transcript 项", () => {
  const argv = serviceCommand({ python: ["python"], kit: "K", repo: "R", assets: "A", transcripts: [] });
  assert.ok(!argv.includes("--transcript"));
});

test("startService 用 spawn(command, [], options) 的形状、不经 shell", async () => {
  let captured = null;
  const fakeSpawn = (command, args, options) => {
    captured = { command, args, options };
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stdin = new PassThrough();
    child.kill = () => {};
    child.stdout.write(HANDSHAKE_LINE);
    return child;
  };
  const { handshake } = await startService({ command: [NODE, "x.js"], spawn: fakeSpawn, timeoutMs: 1000 });
  assert.ok(Array.isArray(captured.command));
  assert.equal(captured.command[0], NODE);
  assert.deepEqual(captured.args, []);
  assert.equal(captured.options.shell, false);
  assert.deepEqual(captured.options.stdio, ["pipe", "pipe", "inherit"]);
  assert.equal(captured.options.windowsHide, true);
  assert.equal(handshake.value.control, "ctrl-tok-XYZ");
});

test("正常握手与干净关停（stdin 一个字节都不写，退出 0）", async () => {
  const { child, handshake } = await startService(svcOptions("ok"));
  const hs = handshake.value ?? handshake;
  assert.equal(hs.control, "ctrl-tok-XYZ");
  assert.equal(hs.origin, "http://127.0.0.1:8123");
  const r = await stopService(child, { graceMs: 4000 });
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.code, 0, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
});

test("握手分两段写也能拼成一行", async () => {
  const { child, handshake } = await startService(svcOptions("split"));
  const hs = handshake.value ?? handshake;
  assert.equal(hs.control, "ctrl-tok-XYZ");
  await stopService(child, { graceMs: 4000 });
});

test("握手行不合法被拒", async () => {
  await assert.rejects(
    () => startService(svcOptions("bad")),
    (e) => String(e).includes("握手行不是 JSON 对象"),
  );
});

test("不写握手：超时被拒且子进程被结束", async () => {
  await assert.rejects(
    () => startService(svcOptions("silent", { timeoutMs: 700 })),
    (e) => String(e).includes("握手超时"),
  );
});

test("握手前以 2 退出：错误里有退出码", async () => {
  await assert.rejects(
    () => startService(svcOptions("exit2")),
    (e) => String(e).includes("服务在握手前退出（退出码 2）"),
  );
});

test("服务忽略 EOF：宽限期一到被结束、进程真的没了", async () => {
  const { child } = await startService(svcOptions("ignore-eof"));
  const r = await stopService(child, { graceMs: 500 });
  assert.equal(r.killed, true, JSON.stringify(r));
  assert.equal(r.exited, false, JSON.stringify(r));
  assert.equal(r.code, null, JSON.stringify(r));
});

test("EOF 后服务以 7 退出：exited 与 code 如实报告", async () => {
  const { child } = await startService(svcOptions("exit7"));
  const r = await stopService(child, { graceMs: 4000 });
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.code, 7, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
});

test("握手后的第二行（带标记）被抽干丢弃，不进握手、不泄漏", async () => {
  const { child, handshake } = await startService(svcOptions("after"));
  const hs = handshake.value ?? handshake;
  assert.equal(hs.control, "ctrl-tok-XYZ");
  // 等第二行写出来并被抽干，再断言它没进握手
  await new Promise((resolve) => setTimeout(resolve, 200));
  assert.ok(!JSON.stringify(handshake).includes("MARKER"), JSON.stringify(handshake));
  await stopService(child, { graceMs: 4000 });
});

test("不经 shell 起服务：参数里的空格 & \" % 原样到达", async (t) => {
  const td = fs.mkdtempSync(path.join(os.tmpdir(), "t025-svc-argv-"));
  t.after(() => fs.rmSync(td, { recursive: true, force: true }));
  const argvFile = path.join(td, "argv.json");
  const command = [NODE, SVC, "--repo", "C:/My Repo&a", "--assets", "C:/As\"sets%", "--transcript", "t one"];
  const { child } = await startService({
    command,
    timeoutMs: 5000,
    env: Object.assign({}, process.env, { FAKE_SERVICE_MODE: "ok", FAKE_SERVICE_ARGV_FILE: argvFile }),
  });
  await stopService(child, { graceMs: 4000 });
  const received = JSON.parse(fs.readFileSync(argvFile, "utf8"));
  assert.deepEqual(received, ["--repo", "C:/My Repo&a", "--assets", "C:/As\"sets%", "--transcript", "t one"]);
});

test("真子进程已经退出：stopService 立即兑现，不等宽限期", { timeout: 5000 }, async () => {
  const child = spawn(process.execPath, ["-e", "process.exit(3)"], { stdio: ["pipe", "pipe", "inherit"] });
  await new Promise((resolve) => child.on("exit", resolve));
  const started = Date.now();
  const r = await stopService(child, { graceMs: 10000 });
  assert.ok(Date.now() - started < 3000, "已退出的子进程上 stopService 挂住了（旧实现的毛病）");
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
  assert.equal(r.code, 3, JSON.stringify(r));
});

test("假子进程的 stdin 发 EPIPE：不抛、照常等退出", { timeout: 5000 }, async () => {
  const child = new EventEmitter();
  child.stdin = new EventEmitter();
  child.stdin.end = () => {
    setImmediate(() => child.stdin.emit("error", Object.assign(new Error("write EPIPE"), { code: "EPIPE" })));
  };
  setTimeout(() => {
    child.exitCode = 0;
    child.emit("exit", 0, null);
    child.emit("close", 0, null);
  }, 50);
  const r = await stopService(child, { graceMs: 8000 });
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
  assert.equal(r.code, 0, JSON.stringify(r));
});
