"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { parseShellArgs } = require("../src/args.js");

function scaffold(t) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const dirs = {
    base,
    repo: path.join(base, "repo"),
    kit: path.join(base, "kit"),
    assets: path.join(base, "assets"),
  };
  fs.mkdirSync(dirs.repo);
  fs.mkdirSync(dirs.kit);
  fs.mkdirSync(dirs.assets);
  fs.mkdirSync(path.join(dirs.kit, "scripts"));
  fs.writeFileSync(path.join(dirs.kit, "scripts", "pi_dispatch.py"), "");
  fs.writeFileSync(path.join(dirs.assets, "index.html"), "");
  return dirs;
}

test("缺三个必需项：按 repo、kit、assets 次序用「、」连接", (t) => {
  const r = parseShellArgs([]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "缺少必需参数：--repo、--kit、--assets");
});

test("缺两个必需项", (t) => {
  const d = scaffold(t);
  const r = parseShellArgs(["--repo", d.repo]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "缺少必需参数：--kit、--assets");
});

test("未知选项", (t) => {
  const d = scaffold(t);
  const r = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--foo", "1"]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "未知参数：--foo");
});

test("多余的位置参数", (t) => {
  const d = scaffold(t);
  const r = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "extra-arg"]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "不接受位置参数：extra-arg");
});

test("--repo 不是目录（不存在的路径）", (t) => {
  const d = scaffold(t);
  const nope = path.join(d.base, "nope");
  const r = parseShellArgs(["--repo", nope, "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--repo 不是目录：" + nope);
});

test("--repo 指向文件也算不是目录", (t) => {
  const d = scaffold(t);
  const file = path.join(d.base, "afile");
  fs.writeFileSync(file, "x");
  const r = parseShellArgs(["--repo", file, "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--repo 不是目录：" + file);
});

test("--kit 不是目录", (t) => {
  const d = scaffold(t);
  const nope = path.join(d.base, "nok");
  const r = parseShellArgs(["--repo", d.repo, "--kit", nope, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--kit 不是目录：" + nope);
});

test("--kit 下没有 scripts/pi_dispatch.py", (t) => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo);
  fs.mkdirSync(kit);
  fs.mkdirSync(assets);
  fs.writeFileSync(path.join(assets, "index.html"), "");
  const r = parseShellArgs(["--repo", repo, "--kit", kit, "--assets", assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--kit 下没有 scripts/pi_dispatch.py：" + kit);
});

test("--assets 不是目录", (t) => {
  const d = scaffold(t);
  const nope = path.join(d.base, "noa");
  const r = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", nope]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--assets 不是目录：" + nope);
});

test("--assets 下没有 index.html", (t) => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo);
  fs.mkdirSync(kit);
  fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  const r = parseShellArgs(["--repo", repo, "--kit", kit, "--assets", assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--assets 下没有 index.html：" + assets);
});

test("成功：绝对路径、--python 原样、transcripts 保序", (t) => {
  const d = scaffold(t);
  const r = parseShellArgs([
    "--repo", d.repo, "--kit", d.kit, "--assets", d.assets,
    "--python", "C:/Tools/py 3.exe",
    "--transcript", "t one", "--transcript", "t&two", "--transcript", "q\"uote%",
  ]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.repo, path.resolve(d.repo));
  assert.equal(r.value.kit, path.resolve(d.kit));
  assert.equal(r.value.assets, path.resolve(d.assets));
  assert.equal(r.value.python, "C:/Tools/py 3.exe");
  assert.deepEqual(r.value.transcripts, ["t one", "t&two", "q\"uote%"]);
});

test("相对路径转绝对；--python 没给是 null；transcripts 没给是空", (t) => {
  const d = scaffold(t);
  const r = parseShellArgs(["--repo", ".", "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.repo, path.resolve("."));
  assert.equal(r.value.python, null);
  assert.deepEqual(r.value.transcripts ?? [], []);
});
