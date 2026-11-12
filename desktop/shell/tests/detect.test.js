"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const cp = require("node:child_process");

// 在 require detect.js 之前换掉 spawn：记下每次调用的选项，并允许把指定命令改道到夹具脚本，
// 这样既能断言子进程的形状，又能在不装三份 Python 的前提下观察候选顺序
const realSpawn = cp.spawn;
const spawnCalls = [];
let redirect = null;
cp.spawn = function recordedSpawn(command, args, options) {
  spawnCalls.push({ command, args: Array.isArray(args) ? args.slice() : args, options });
  if (redirect) {
    const alt = redirect(command, args);
    if (alt) return realSpawn.call(cp, alt[0], alt[1], options);
  }
  return realSpawn.apply(cp, arguments);
};

const detect = require("../src/detect.js");

const { PYTHON_INFO_CODE, KIT_VERSION_RE, runProcess, checkRepo, probePython, probeKit, detectPython, detectKit } =
  detect;

const NODE = process.execPath;
const FIXTURE = (name) => path.join(__dirname, "fixtures", name);
const INFO = FIXTURE("fake-py-info.js");
const INFO_ONE_LINE = FIXTURE("fake-py-info-oneline.js");
const NO_OUTPUT = FIXTURE("fake-python-ok.js");
const OLD = FIXTURE("fake-python-old.js");
const HANG = FIXTURE("fake-python-hang.js");
const ECHO = FIXTURE("fake-echo-argv.js");
const KIT_VERSION = FIXTURE("fake-kit-version.js");
const KIT_VERSION_STDERR = FIXTURE("fake-kit-version-stderr.js");
const KIT_NO_VERSION = FIXTURE("fake-kit-no-version.js");
const KIT_FAIL = FIXTURE("fake-kit-fail.js");
const KIT_HANG = FIXTURE("fake-kit-hang.js");

const B = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-detect-")));

function makeKit(name, fixture) {
  const kit = path.join(B, name);
  fs.mkdirSync(path.join(kit, "scripts"), { recursive: true });
  fs.copyFileSync(fixture, path.join(kit, "scripts", "pi_dispatch.py"));
  return kit;
}

test.after(() => {
  cp.spawn = realSpawn;
  fs.rmSync(B, { recursive: true, force: true });
});

test("常量：探测代码逐字照合同；版本号正则取 x.y.z", () => {
  assert.equal(
    PYTHON_INFO_CODE,
    "import sys; print(sys.version.split()[0]); print(sys.executable); sys.exit(0 if sys.version_info >= (3, 10) else 1)",
  );
  assert.equal(KIT_VERSION_RE.exec("pi_dispatch 2.12.0")[0], "2.12.0");
  assert.equal(KIT_VERSION_RE.test("no digits here"), false);
});

test("runProcess：正常结束带回 code/stdout/stderr，参数原样到达（不经 shell）", async () => {
  spawnCalls.length = 0;
  redirect = null;
  const args = ["带空格 & echo hacked", "C:/path with space/x.js", "<>|", ";whoami"];
  const r = await runProcess(NODE, [ECHO, ...args], { timeoutMs: 15000 });
  assert.equal(r.code, 0, JSON.stringify(r));
  assert.equal(r.timedOut, false);
  assert.equal(r.error, undefined);
  assert.deepEqual(JSON.parse(r.stdout), args, "经 shell 的话元字符会被解释掉");
  assert.equal(r.stderr, "err-line\n");
  assert.equal(spawnCalls.length, 1);
  const opts = spawnCalls[0].options || {};
  assert.equal(opts.shell, false, "spawn 必须 shell:false");
  assert.equal(opts.windowsHide, true, "spawn 必须 windowsHide:true");
  assert.deepEqual(opts.stdio, ["ignore", "pipe", "pipe"]);
});

test("runProcess：退出码非 0 原样带回", async () => {
  redirect = null;
  const r = await runProcess(NODE, [FIXTURE("fake-python-fail.js")], { timeoutMs: 15000 });
  assert.equal(r.code, 9009);
  assert.equal(r.timedOut, false);
});

test("runProcess：超时杀进程、回 timedOut:true 与 code:null", async () => {
  redirect = null;
  const t0 = Date.now();
  const r = await runProcess(NODE, [HANG], { timeoutMs: 400 });
  assert.equal(r.timedOut, true);
  assert.equal(r.code, null);
  assert.ok(Date.now() - t0 < 8000, "超时要按时限返回，不许挂住");
});

test("runProcess：进程起不来回 error 错误码", async () => {
  redirect = null;
  const r = await runProcess("t028-no-such-cmd-xyz", [], { timeoutMs: 8000 });
  assert.equal(r.code, null);
  assert.equal(r.timedOut, false);
  assert.equal(r.stdout, "");
  assert.equal(r.stderr, "");
  assert.equal(r.error, "ENOENT");
});

test("checkRepo：.git 目录 + .agent 目录 → ok", () => {
  const d = path.join(B, "repo-ok");
  fs.mkdirSync(path.join(d, ".git"), { recursive: true });
  fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
  assert.equal(checkRepo(d), "ok");
});

test("checkRepo：.git 是文件（worktree）也算 → ok", () => {
  const d = path.join(B, "repo-file-git");
  fs.mkdirSync(d);
  fs.writeFileSync(path.join(d, ".git"), "gitdir: ../elsewhere\n");
  fs.mkdirSync(path.join(d, ".agent"));
  assert.equal(checkRepo(d), "ok");
});

test("checkRepo：缺 .git、路径不存在 → not-git", () => {
  const d = path.join(B, "repo-no-git");
  fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
  assert.equal(checkRepo(d), "not-git");
  assert.equal(checkRepo(path.join(B, "no-such-dir")), "not-git");
  assert.equal(checkRepo(""), "not-git");
});

test("checkRepo：.agent 缺失或是文件 → no-agent", () => {
  const d1 = path.join(B, "repo-no-agent");
  fs.mkdirSync(path.join(d1, ".git"), { recursive: true });
  assert.equal(checkRepo(d1), "no-agent");
  const d2 = path.join(B, "repo-agent-file");
  fs.mkdirSync(d2);
  fs.writeFileSync(path.join(d2, ".git"), "gitdir: x\n");
  fs.writeFileSync(path.join(d2, ".agent"), "not a dir");
  assert.equal(checkRepo(d2), "no-agent");
});

test("probePython：退出码 0 且至少两行 → ok（version 第一行、path 第二行）", async () => {
  redirect = null;
  const r = await probePython([NODE, INFO], { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: true, version: "3.12.9", path: "/fake/python-exe" });
});

test("probePython：退出码 0 但行数不够 → bad-output", async () => {
  redirect = null;
  assert.deepEqual(await probePython([NODE, INFO_ONE_LINE], { timeoutMs: 15000 }), {
    ok: false,
    reason: "bad-output",
  });
  assert.deepEqual(await probePython([NODE, NO_OUTPUT], { timeoutMs: 15000 }), {
    ok: false,
    reason: "bad-output",
  });
});

test("probePython：退出码非 0 → version-too-old；超时 → timeout；起不来 → no-command", async () => {
  redirect = null;
  assert.deepEqual(await probePython([NODE, OLD], { timeoutMs: 15000 }), { ok: false, reason: "version-too-old" });
  assert.deepEqual(await probePython([NODE, HANG], { timeoutMs: 400 }), { ok: false, reason: "timeout" });
  assert.deepEqual(await probePython(["t028-no-such-cmd-xyz"], { timeoutMs: 8000 }), {
    ok: false,
    reason: "no-command",
  });
});

test("probePython：探测代码以 -c 传给解释器，候选命令原样打头", async () => {
  spawnCalls.length = 0;
  redirect = null;
  await probePython(["py", "-3"], { timeoutMs: 8000 });
  assert.equal(spawnCalls.length, 1);
  assert.equal(spawnCalls[0].command, "py");
  assert.equal(spawnCalls[0].args[0], "-3");
  assert.equal(spawnCalls[0].args[1], "-c");
  assert.equal(spawnCalls[0].args[2], PYTHON_INFO_CODE);
});

test("probePython：options.code 到达 argv，缺省仍是 PYTHON_INFO_CODE", async () => {
  spawnCalls.length = 0;
  redirect = null;
  const custom = "print('marker'); print('second')";
  // 替身只回显一行，探测结果按行数不够判 bad-output；code 是否到达由 spawn 的 argv 断言
  assert.deepEqual(await probePython([NODE, ECHO], { timeoutMs: 15000, code: custom }), {
    ok: false,
    reason: "bad-output",
  });
  assert.equal(spawnCalls.length, 1);
  assert.equal(spawnCalls[0].command, NODE);
  assert.equal(spawnCalls[0].args[0], ECHO);
  assert.equal(spawnCalls[0].args[1], "-c");
  assert.equal(spawnCalls[0].args[2], custom, "调用方按合同传 {code} 时不许被静默忽略");
  spawnCalls.length = 0;
  await probePython([NODE, ECHO], { timeoutMs: 15000 });
  assert.equal(spawnCalls.length, 1);
  assert.equal(spawnCalls[0].args[2], PYTHON_INFO_CODE, "不给 code 时仍是缺省探测代码");
});

test("probeKit：stdout 取版本号 → ok", async () => {
  redirect = null;
  const kit = makeKit("kit-ok", KIT_VERSION);
  assert.deepEqual(await probeKit(NODE, kit, { timeoutMs: 15000 }), { ok: true, version: "2.12.0" });
});

test("probeKit：版本号只在 stderr 也认", async () => {
  redirect = null;
  const kit = makeKit("kit-err", KIT_VERSION_STDERR);
  assert.deepEqual(await probeKit(NODE, kit, { timeoutMs: 15000 }), { ok: true, version: "9.9.9" });
});

test("probeKit：跑得通但没有版本号 → kit-unusable", async () => {
  redirect = null;
  const kit = makeKit("kit-noversion", KIT_NO_VERSION);
  assert.deepEqual(await probeKit(NODE, kit, { timeoutMs: 15000 }), { ok: false, reason: "kit-unusable" });
});

test("probeKit：--version 跑不通、脚本缺失 → kit-unusable；超时 → timeout", async () => {
  redirect = null;
  const fail = makeKit("kit-fail", KIT_FAIL);
  assert.deepEqual(await probeKit(NODE, fail, { timeoutMs: 15000 }), { ok: false, reason: "kit-unusable" });
  const empty = path.join(B, "kit-missing-script");
  fs.mkdirSync(empty, { recursive: true });
  assert.deepEqual(await probeKit(NODE, empty, { timeoutMs: 15000 }), { ok: false, reason: "kit-unusable" });
  const hang = makeKit("kit-hang", KIT_HANG);
  assert.deepEqual(await probeKit(NODE, hang, { timeoutMs: 400 }), { ok: false, reason: "timeout" });
});

test("probeKit：没有 pythonPath → python-unusable，且不起子进程", async () => {
  spawnCalls.length = 0;
  redirect = null;
  assert.deepEqual(await probeKit(null, makeKit("kit-nopy", KIT_VERSION), { timeoutMs: 15000 }), {
    ok: false,
    reason: "python-unusable",
  });
  assert.equal(spawnCalls.length, 0);
});

test("detectPython：按 python3 → python → py -3 的顺序，第一个成功即停", async () => {
  spawnCalls.length = 0;
  redirect = (command, args) => {
    assert.equal(args[0], "-c", "探测代码必须以 -c 传给解释器");
    assert.equal(args[1], PYTHON_INFO_CODE, "缺省探测代码就是 PYTHON_INFO_CODE");
    if (command === "python3") return [NODE, [OLD]];
    if (command === "python") return [NODE, [INFO]];
    return null;
  };
  const r = await detectPython({ timeoutMs: 15000 });
  assert.deepEqual(r, { status: "ok", source: "auto", path: "/fake/python-exe", version: "3.12.9" });
  assert.deepEqual(spawnCalls.map((c) => c.command), ["python3", "python"]);
});

test("detectPython：全失败 → missing、path/version 为空，三个候选都试过", async () => {
  spawnCalls.length = 0;
  redirect = () => [NODE, [OLD]];
  assert.deepEqual(await detectPython({ timeoutMs: 15000 }), {
    status: "missing",
    source: "auto",
    path: "",
    version: "",
  });
  assert.deepEqual(spawnCalls.map((c) => c.command), ["python3", "python", "py"]);
});

test("detectKit：kitPath 优先（external），path 是被验证的 pi_dispatch.py", async () => {
  redirect = null;
  const ext = makeKit("kit-ext", KIT_VERSION);
  const repo = makeKit("kit-repo", KIT_VERSION);
  const r = await detectKit({ pythonPath: NODE, kitPath: ext, repoPath: repo, timeoutMs: 15000 });
  assert.equal(r.status, "ok", JSON.stringify(r));
  assert.equal(r.source, "external");
  assert.equal(r.version, "2.12.0");
  assert.equal(path.resolve(r.path), path.resolve(path.join(ext, "scripts", "pi_dispatch.py")));
});

test("detectKit：没有 kitPath 时按 repo 探测（source repo）", async () => {
  redirect = null;
  const repo = makeKit("kit-repo2", KIT_VERSION);
  const r = await detectKit({ pythonPath: NODE, repoPath: repo, timeoutMs: 15000 });
  assert.equal(r.status, "ok");
  assert.equal(r.source, "repo");
  assert.equal(r.version, "2.12.0");
  assert.equal(path.resolve(r.path), path.resolve(path.join(repo, "scripts", "pi_dispatch.py")));
});

test("detectKit：探测失败 → missing、path/version 为空", async () => {
  redirect = null;
  const empty = path.join(B, "kit-empty");
  fs.mkdirSync(empty, { recursive: true });
  assert.deepEqual(await detectKit({ pythonPath: NODE, repoPath: empty, timeoutMs: 15000 }), {
    status: "missing",
    source: "repo",
    path: "",
    version: "",
  });
  assert.deepEqual(await detectKit({ pythonPath: null, kitPath: empty, timeoutMs: 15000 }), {
    status: "missing",
    source: "external",
    path: "",
    version: "",
  });
});

test("detectKit：kitPath 与 repoPath 都没有 → missing，不起子进程", async () => {
  spawnCalls.length = 0;
  redirect = null;
  const r = await detectKit({ pythonPath: NODE, timeoutMs: 15000 });
  assert.equal(r.status, "missing");
  assert.equal(spawnCalls.length, 0);
});

test("子进程时限默认 10 秒", async () => {
  redirect = null;
  const t0 = Date.now();
  const r = await runProcess(NODE, [HANG]);
  assert.equal(r.timedOut, true);
  assert.ok(Date.now() - t0 >= 9000, "不给 timeoutMs 时要用 10 秒");
});
