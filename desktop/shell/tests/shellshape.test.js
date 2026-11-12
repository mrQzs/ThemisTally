"use strict";

// 形状比对：期望值只来自类型文件 desktop/web/src/shellpages/themisShell.ts 与实现模块的导出，
// 这里不另抄一份键表——类型文件改了，这些比对就要红。

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const settings = require("../src/settings.js");
const { createShellApi } = require("../src/shellapi.js");

const TS_PATH = path.resolve(__dirname, "../../web/src/shellpages/themisShell.ts");
const TS = fs.readFileSync(TS_PATH, "utf8");

function must(condition, message) {
  if (!condition) throw new Error(message);
}

// 接口块：export interface <名字> { 到行首 } 之间
function interfaceBlock(name) {
  const start = TS.match(new RegExp(`export interface ${name} \\{`));
  must(start !== null, `themisShell.ts 里找不到 export interface ${name}`);
  const rest = TS.slice(start.index + start[0].length);
  const end = rest.search(/\n\}/);
  must(end !== -1, `interface ${name} 没有行首 } 的结束`);
  return rest.slice(0, end);
}

// 成员名：^\s*(\w+)(\?)?\s*: 的字段，加上名字后直接跟左括号的方法
function interfaceNames(name) {
  const names = [];
  for (const line of interfaceBlock(name).split("\n")) {
    let m = line.match(/^\s*(\w+)(\?)?\s*:/);
    if (m === null) m = line.match(/^\s*(\w+)\s*\(/);
    if (m !== null) names.push(m[1]);
  }
  must(names.length > 0, `interface ${name} 解析不出成员——类型文件的格式变了，要报警`);
  return names;
}

// 内联对象类型：在该行里再取一次 (\w+)\s*:，外层字段名不算
function inlineFields(owner, field) {
  let line = null;
  for (const candidate of interfaceBlock(owner).split("\n")) {
    if (new RegExp(`^\\s*${field}\\s*:\\s*\\{`).test(candidate)) {
      line = candidate;
      break;
    }
  }
  must(line !== null, `${owner} 里找不到内联字段 ${field}`);
  const inner = line.slice(line.indexOf("{") + 1);
  const names = [...inner.matchAll(/(\w+)\s*:/g)].map((m) => m[1]);
  must(names.length > 0, `${owner}.${field} 的内联字段解析失败`);
  return names;
}

// 类型别名：export type <名字> = 到语句终止分号（大括号配平后的第一个 ;）之间的所有 '…' 字面量
function typeLiterals(name) {
  const start = TS.match(new RegExp(`export type ${name} =`));
  must(start !== null, `themisShell.ts 里找不到 export type ${name}`);
  const rest = TS.slice(start.index);
  let depth = 0;
  let semi = -1;
  for (let i = 0; i < rest.length; i += 1) {
    const c = rest[i];
    if (c === "{") depth += 1;
    else if (c === "}") depth -= 1;
    else if (c === ";" && depth === 0) {
      semi = i;
      break;
    }
  }
  must(semi !== -1, `type ${name} 没有分号结束`);
  const lits = [];
  const re = /'([^']*)'/g;
  let m;
  while ((m = re.exec(rest.slice(0, semi))) !== null) lits.push(m[1]);
  must(lits.length > 0, `type ${name} 解析不出字面量`);
  return lits;
}

// 接口里的字面量字段（theme / density）
function fieldLiterals(owner, field) {
  for (const line of interfaceBlock(owner).split("\n")) {
    if (new RegExp(`^\\s*${field}\\??\\s*:`).test(line)) {
      const lits = [];
      const re = /'([^']*)'/g;
      let m;
      while ((m = re.exec(line)) !== null) lits.push(m[1]);
      must(lits.length > 0, `${owner}.${field} 解析不出字面量`);
      return lits;
    }
  }
  must(false, `${owner} 里找不到字段 ${field}`);
  return [];
}

function makeApi() {
  const b = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-shape-")));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  const chooser = { dir: null, file: null };
  const probe = {
    async probePython() {
      return { ok: true, version: "3.12.9", path: "/fake/python-exe" };
    },
    async probeKit() {
      return { ok: true, version: "2.12.0" };
    },
    async detectPython() {
      return { status: "missing", source: "auto", path: "", version: "" };
    },
    async detectKit(options) {
      const kitDir = (options && (options.kitPath || options.repoPath)) || null;
      if (!kitDir) return { status: "missing", source: "repo", path: "", version: "" };
      return {
        status: "ok",
        source: options.kitPath ? "external" : "repo",
        path: path.join(kitDir, "scripts", "pi_dispatch.py"),
        version: "2.12.0",
      };
    },
  };
  const api = createShellApi({
    store: settings.createSettingsStore({ dir: userData }),
    chooseDirectory: async () => chooser.dir,
    chooseFile: async () => chooser.file,
    confirmExternal: async () => true,
    openExternal: async () => {},
    appVersion: "9.9.9",
    probe,
  });
  return { b, api, chooser };
}

const keys = (o) => Object.keys(o).sort();

test("类型文件读得到，且解析出的块都不是空的", () => {
  must(TS.length > 0, `${TS_PATH} 读出来是空的`);
  for (const name of ["ThemisShell", "ShellState", "ShellSettings", "RepoEntry", "TranscriptDirEntry", "SettingsPatch"]) {
    assert.ok(interfaceNames(name).length > 0, name);
  }
  for (const name of ["RepoCheck", "PickProblem", "ServiceState"]) {
    assert.ok(typeLiterals(name).length > 0, name);
  }
});

test("成员名与键表：十个成员与四张表逐项来自 themisShell.ts", () => {
  const h = makeApi();
  assert.deepEqual(keys(h.api), [...interfaceNames("ThemisShell")].sort());
  assert.deepEqual([...settings.PATCH_KEYS].sort(), [...interfaceNames("SettingsPatch")].sort());
  assert.deepEqual([...settings.THEME_VALUES].sort(), [...fieldLiterals("ShellSettings", "theme")].sort());
  assert.deepEqual([...settings.DENSITY_VALUES].sort(), [...fieldLiterals("ShellSettings", "density")].sort());
  for (const field of interfaceNames("ShellSettings")) {
    assert.ok(settings.SETTINGS_FILE_KEYS.includes(field), `SETTINGS_FILE_KEYS 缺 ShellSettings 的字段 ${field}`);
  }
});

test("返回值形状：ShellState 各层键与枚举取值逐项来自 themisShell.ts", async () => {
  const h = makeApi();
  const repoDir = path.join(h.b, "arepo");
  fs.mkdirSync(path.join(repoDir, ".git"), { recursive: true });
  fs.mkdirSync(path.join(repoDir, ".agent"), { recursive: true });
  h.chooser.dir = repoDir;
  const picked = await h.api.pickRepo();
  assert.equal(picked.ok, true, JSON.stringify(picked));
  assert.equal(picked.value.kind, "saved", JSON.stringify(picked));
  const logsDir = path.join(h.b, "logs");
  fs.mkdirSync(logsDir);
  h.chooser.dir = logsDir;
  const pickedDir = await h.api.pickTranscriptDir();
  assert.equal(pickedDir.value.kind, "saved", JSON.stringify(pickedDir));

  const r = await h.api.getState();
  assert.deepEqual(keys(r), ["ok", "value"]);
  const st = r.value;
  assert.deepEqual(keys(st), [...interfaceNames("ShellState")].sort());
  assert.deepEqual(keys(st.app), [...inlineFields("ShellState", "app")].sort());
  assert.deepEqual(keys(st.settings), [...interfaceNames("ShellSettings")].sort());
  must(st.settings.repos.length >= 1, "要有一个仓库条目才能比对 RepoEntry");
  assert.deepEqual(keys(st.settings.repos[0]), [...interfaceNames("RepoEntry")].sort());
  must(st.settings.transcriptDirs.length >= 1, "要有一个会话目录条目才能比对 TranscriptDirEntry");
  assert.deepEqual(keys(st.settings.transcriptDirs[0]), [...interfaceNames("TranscriptDirEntry")].sort());
  assert.deepEqual(keys(st.python), [...inlineFields("ShellState", "python")].sort());
  assert.deepEqual(keys(st.kit), [...inlineFields("ShellState", "kit")].sort());
  assert.ok(typeLiterals("ServiceState").includes(st.service.kind), JSON.stringify(st.service));
  assert.ok(
    typeLiterals("RepoCheck").includes(st.currentRepoCheck),
    `合法仓库的 currentRepoCheck 必须是 RepoCheck 里的取值：${JSON.stringify(st.currentRepoCheck)}`,
  );
  assert.ok(fieldLiterals("ShellSettings", "theme").includes(st.settings.theme), st.settings.theme);
  assert.ok(fieldLiterals("ShellSettings", "density").includes(st.settings.density), st.settings.density);

  const plain = path.join(h.b, "plain");
  fs.mkdirSync(plain);
  h.chooser.dir = plain;
  const rej = await h.api.pickRepo();
  assert.equal(rej.value.kind, "rejected", JSON.stringify(rej));
  assert.ok(typeLiterals("PickProblem").includes(rej.value.problem), rej.value.problem);
});

test("currentRepoCheck 可以是 null；service.kind 恒为 idle 也在 ServiceState 里", async () => {
  const h = makeApi();
  const st = (await h.api.getState()).value;
  assert.equal(st.currentRepoCheck, null);
  assert.ok(typeLiterals("RepoCheck").concat([null]).includes(st.currentRepoCheck));
  assert.equal(st.service.kind, "idle");
});

test("存盘文件里的键覆盖 SETTINGS_FILE_KEYS，读回来的 settings 只有 ShellSettings 的字段", async () => {
  const h = makeApi();
  h.chooser.dir = path.join(h.b, "arepo");
  fs.mkdirSync(path.join(h.b, "arepo", ".git"), { recursive: true });
  fs.mkdirSync(path.join(h.b, "arepo", ".agent"), { recursive: true });
  await h.api.pickRepo();
  const onDisk = JSON.parse(fs.readFileSync(path.join(h.b, "userData", "settings.json"), "utf8"));
  assert.deepEqual([...Object.keys(onDisk)].sort(), [...settings.SETTINGS_FILE_KEYS].sort());
  const st = (await h.api.getState()).value;
  for (const field of Object.keys(st.settings)) {
    assert.ok(interfaceNames("ShellSettings").includes(field), field);
  }
});
