"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
const lock = JSON.parse(fs.readFileSync(path.join(ROOT, "package-lock.json"), "utf8"));

test("package.json 的字段与精确依赖", () => {
  assert.equal(pkg.name, "themistally-desktop-shell");
  assert.equal(pkg.private, true);
  assert.equal(pkg.version, "0.0.0");
  assert.equal(pkg.type, "commonjs");
  assert.equal(pkg.main, "main.js");
  assert.equal(pkg.scripts.start, "electron .");
  assert.ok(pkg.dependencies === undefined || Object.keys(pkg.dependencies).length === 0);
  assert.deepEqual(pkg.devDependencies, { electron: "44.9.0" });
});

test("package-lock.json 里 electron 是 44.9.0", () => {
  assert.equal(lock.packages[""].devDependencies.electron, "44.9.0");
  assert.equal(lock.packages["node_modules/electron"].version, "44.9.0");
});

test("scripts.test 带 --test-reporter=tap 且开关在文件清单之前", () => {
  const testCmd = pkg.scripts.test;
  assert.ok(testCmd.includes("node --test"));
  const tapAt = testCmd.indexOf("--test-reporter=tap");
  assert.notEqual(tapAt, -1, testCmd);
  const filesAt = testCmd.indexOf("tests/");
  assert.ok(filesAt === -1 || tapAt < filesAt, testCmd);
});

test("scripts.test 显式列出 tests/ 下每一个 *.test.js", () => {
  const testCmd = pkg.scripts.test;
  const listed = new Set((testCmd.match(/tests[/\\][\w.-]+\.test\.js/g) || []));
  const actual = new Set(
    fs.readdirSync(path.join(ROOT, "tests"))
      .filter((name) => name.endsWith(".test.js"))
      .map((name) => "tests/" + name),
  );
  assert.ok(actual.size > 0);
  const missing = [...actual].filter((f) => !listed.has(f));
  assert.deepEqual(missing, []);
});
