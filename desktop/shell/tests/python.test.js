"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { PYTHON_PROBE_CODE, DEFAULT_PYTHON_CANDIDATES, findPython } = require("../src/python.js");

const NODE = process.execPath;
const FIXTURE = (name) => path.join(__dirname, "fixtures", name);
const OK = FIXTURE("fake-python-ok.js");
const OLD = FIXTURE("fake-python-old.js");
const FAIL = FIXTURE("fake-python-fail.js");
const HANG = FIXTURE("fake-python-hang.js");

test("探测代码与默认候选逐字照合同（版本门槛 3.10）", () => {
  assert.equal(PYTHON_PROBE_CODE, "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)");
  assert.deepEqual(DEFAULT_PYTHON_CANDIDATES, [["python3"], ["python"], ["py", "-3"]]);
});

test("注入 probe：按候选次序试、第一个可用即赢、时限参数传到 probe", async () => {
  const calls = [];
  const probe = async (command, timeoutMs) => {
    calls.push([command, timeoutMs]);
    return command[0] === "python" ? { ok: true, reason: "" } : { ok: false, reason: "命令不存在" };
  };
  const r = await findPython({ probe, timeoutMs: 123 });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["python"]);
  assert.equal(calls.length, 2, JSON.stringify(calls));
  assert.deepEqual(calls[0][0], ["python3"]);
  assert.deepEqual(calls[1][0], ["python"]);
  assert.equal(calls[1][1], 123);
});

test("注入 probe：全失败给 tried 与总结错误", async () => {
  const probe = async () => ({ ok: false, reason: "退出码 1" });
  const r = await findPython({ probe });
  assert.equal(r.ok, false);
  assert.equal(r.error, "找不到可用的 Python（要求 ≥ 3.10）");
  assert.equal(r.tried.length, 3);
  assert.deepEqual(r.tried.map((x) => x.command), [["python3"], ["python"], ["py", "-3"]]);
  for (const entry of r.tried) {
    assert.equal(typeof entry.reason, "string");
    assert.ok(entry.reason.length > 0);
  }
});

test("给了 python 选项就只试它一个、失败不回退、错误含命令本身", async () => {
  const calls = [];
  const probe = async (command) => {
    calls.push(command);
    return { ok: false, reason: "退出码 1" };
  };
  const r = await findPython({ python: "my-py 3", probe, timeoutMs: 500 });
  assert.equal(r.ok, false, JSON.stringify(r));
  assert.ok(r.error.includes("指定的 Python 不可用"), JSON.stringify(r));
  assert.ok(r.error.includes("my-py 3"), JSON.stringify(r));
  assert.equal(calls.length, 1, JSON.stringify(calls));
  assert.deepEqual(calls[0], ["my-py 3"]);
  assert.equal(r.tried.length, 1);
  assert.deepEqual(r.tried[0].command, ["my-py 3"]);
});

test("python 选项可用时也只试它一个", async () => {
  const calls = [];
  const probe = async (command) => {
    calls.push(command);
    return { ok: true, reason: "" };
  };
  const r = await findPython({ python: "py9", probe });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["py9"]);
  assert.equal(calls.length, 1);
});

test("python 为 null 时走默认候选", async () => {
  const probe = async () => ({ ok: true, reason: "" });
  const r = await findPython({ python: null, probe });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["python3"]);
});

test("注入 probe：单个候选失败不回退到别的候选", async () => {
  const probe = async () => ({ ok: false, reason: "命令不存在" });
  const r = await findPython({ candidates: [["my-python"]], probe });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
});

test("真起进程：ok 夹具可用", async () => {
  const r = await findPython({ candidates: [[NODE, OK]], timeoutMs: 8000 });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, [NODE, OK]);
});

test("真起进程：old（退出 1）与 fail（退出 9009）都算不可用", async () => {
  const rOld = await findPython({ candidates: [[NODE, OLD]], timeoutMs: 8000 });
  assert.equal(rOld.ok, false);
  assert.ok(rOld.tried[0].reason.includes("退出码"), JSON.stringify(rOld.tried));
  const rFail = await findPython({ candidates: [[NODE, FAIL]], timeoutMs: 8000 });
  assert.equal(rFail.ok, false);
  assert.ok(rFail.tried[0].reason.includes("退出码"), JSON.stringify(rFail.tried));
});

test("真起进程：命令不存在被跳过", async () => {
  const r = await findPython({ candidates: [["t025-no-such-cmd-xyz"]], timeoutMs: 8000 });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
  assert.ok(r.tried[0].reason.includes("存在"), JSON.stringify(r.tried));
});

test("真起进程：超时算不可用", async () => {
  const r = await findPython({ candidates: [[NODE, HANG]], timeoutMs: 400 });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
  assert.ok(r.tried[0].reason.includes("超时"), JSON.stringify(r.tried));
});

test("真起进程：第一个候选即赢（old 失败后 ok 成功）", async () => {
  const r = await findPython({ candidates: [[NODE, OLD], [NODE, OK]], timeoutMs: 8000 });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, [NODE, OK]);
});
