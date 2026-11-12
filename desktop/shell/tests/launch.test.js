"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { launchMode } = require("../src/launch.js");

test("空数组 → shell", () => {
  assert.equal(launchMode([]), "shell");
});

test("带齐三项 → service", () => {
  assert.equal(launchMode(["--repo", "r", "--kit", "k", "--assets", "a"]), "service");
});

test("--repo=… → service", () => {
  assert.equal(launchMode(["--repo=x"]), "service");
});

test("--repo 在任意位置（含前面有 electron 与 . 的真实形状，或不带值）→ service", () => {
  assert.equal(launchMode(["electron.exe", ".", "--repo", "r"]), "service");
  assert.equal(launchMode(["--kit", "k", "--repo"]), "service");
});

test("只有别的参数 → shell", () => {
  assert.equal(launchMode(["--kit", "k"]), "shell");
  assert.equal(launchMode(["--assets", "a", "--python", "py"]), "shell");
  assert.equal(launchMode(["--repox"]), "shell");
  assert.equal(launchMode(["--repo-x", "1"]), "shell");
});

test("非数组按空数组处理 → shell", () => {
  for (const v of [null, undefined, "x", 123, {}]) {
    assert.equal(launchMode(v), "shell", JSON.stringify(v));
  }
});
