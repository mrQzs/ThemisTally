"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const settings = require("../src/settings.js");

const {
  DEFAULT_SETTINGS,
  SETTINGS_FILE_KEYS,
  THEME_VALUES,
  DENSITY_VALUES,
  PATCH_KEYS,
  createSettingsStore,
  normalizeSettings,
  applyPatch,
  addRepo,
  addTranscriptDir,
} = settings;

const DEFAULTS = {
  version: 1,
  repos: [],
  currentRepo: null,
  transcriptDirs: [],
  theme: "system",
  density: "standard",
  pythonPath: null,
  kitPath: null,
};

const NOW = new Date(Date.UTC(2026, 0, 2, 3, 4, 5, 678));
const STAMP = "20260102T030405678Z";

function base() {
  return fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-settings-")));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function withRepos() {
  const s = clone(DEFAULT_SETTINGS);
  s.repos = [
    { id: "r1", name: "alpha", path: "C:/nowhere/alpha", lastOpened: null },
    { id: "r2", name: "beta", path: "C:/nowhere/beta", lastOpened: "2026-01-01T00:00:00.000Z" },
  ];
  s.transcriptDirs = [{ id: "d1", path: "C:/nowhere/d1" }];
  s.pythonPath = "C:/py/python.exe";
  s.kitPath = "C:/kit";
  s.currentRepo = "r1";
  return s;
}

function makeStore(dir, now) {
  return createSettingsStore({ dir, now: now || (() => NOW) });
}

test("常量：缺省设置冻结且逐字照合同；四张键表/取值表照顺序", () => {
  assert.ok(Object.isFrozen(DEFAULT_SETTINGS));
  assert.deepEqual(DEFAULT_SETTINGS, DEFAULTS);
  assert.deepEqual(SETTINGS_FILE_KEYS, [
    "version",
    "repos",
    "currentRepo",
    "transcriptDirs",
    "theme",
    "density",
    "pythonPath",
    "kitPath",
  ]);
  assert.deepEqual(THEME_VALUES, ["system", "light", "dark"]);
  assert.deepEqual(DENSITY_VALUES, ["standard", "compact"]);
  assert.deepEqual(PATCH_KEYS, ["theme", "density", "removeRepo", "removeTranscriptDir", "resetPython", "resetKit"]);
});

test("store：dir 与 filePath 就是注入目录下的 settings.json", () => {
  const b = base();
  const store = makeStore(b);
  assert.equal(store.dir, b);
  assert.equal(store.filePath, path.join(b, "settings.json"));
});

test("load：文件不存在 → 缺省设置的深拷贝、badCopy 为 null", () => {
  const b = base();
  const r = makeStore(b).load();
  assert.deepEqual(r.settings, DEFAULTS);
  assert.equal(r.badCopy, null);
  assert.notEqual(r.settings, DEFAULT_SETTINGS);
  assert.notEqual(r.settings.repos, DEFAULT_SETTINGS.repos);
  r.settings.repos.push({ id: "x" });
  assert.deepEqual(DEFAULT_SETTINGS.repos, [], "缺省设置不许被读出去的对象带坏");
});

const BAD_FILES = [
  ["坏 JSON", "{not json"],
  ["顶层是数组", "[1, 2]"],
  ["顶层是字符串", '"hello"'],
  ["theme 取值非法", JSON.stringify(Object.assign({}, DEFAULTS, { theme: "neon" }))],
  ["density 取值非法", JSON.stringify(Object.assign({}, DEFAULTS, { density: "cozy" }))],
  ["version 不是 1", JSON.stringify(Object.assign({}, DEFAULTS, { version: 2 }))],
  ["repos 不是数组", JSON.stringify(Object.assign({}, DEFAULTS, { repos: "x" }))],
  ["repos 条目缺字段", JSON.stringify(Object.assign({}, DEFAULTS, { repos: [{ id: "r" }] }))],
  ["currentRepo 类型不对", JSON.stringify(Object.assign({}, DEFAULTS, { currentRepo: 5 }))],
  ["transcriptDirs 条目缺 path", JSON.stringify(Object.assign({}, DEFAULTS, { transcriptDirs: [{ id: "d" }] }))],
  ["kitPath 类型不对", JSON.stringify(Object.assign({}, DEFAULTS, { kitPath: 7 }))],
];

for (const [name, text] of BAD_FILES) {
  test(`load：坏文件（${name}）→ 缺省设置 + 原始字节另存副本`, () => {
    const b = base();
    const raw = Buffer.from(text, "utf8");
    fs.writeFileSync(path.join(b, "settings.json"), raw);
    const r = makeStore(b).load();
    assert.deepEqual(r.settings, DEFAULTS, name);
    assert.equal(r.badCopy, path.join(b, `settings.bad-${STAMP}.json`), name);
    assert.ok(fs.existsSync(r.badCopy), name);
    assert.deepEqual(fs.readFileSync(r.badCopy), raw, `${name}：副本必须是坏文件的原始字节`);
  });
}

test("load：副本名带 UTC 时刻（缺省 now），格式 YYYYMMDDTHHMMSSmmmZ", () => {
  const b = base();
  fs.writeFileSync(path.join(b, "settings.json"), "oops");
  const r = createSettingsStore({ dir: b }).load();
  assert.equal(r.badCopy !== null, true);
  assert.ok(/^settings\.bad-\d{8}T\d{9}Z\.json$/.test(path.basename(r.badCopy)), r.badCopy);
});

test("load：副本同名不覆盖，依次试 -2、-3；已存在的副本一个字节都不动", () => {
  const b = base();
  const raw = Buffer.from("{bad", "utf8");
  fs.writeFileSync(path.join(b, "settings.json"), raw);
  const first = path.join(b, `settings.bad-${STAMP}.json`);
  fs.writeFileSync(first, "PRE-EXISTING");
  const store = makeStore(b);
  const r1 = store.load();
  assert.equal(r1.badCopy, path.join(b, `settings.bad-${STAMP}-2.json`));
  assert.deepEqual(fs.readFileSync(r1.badCopy), raw);
  assert.equal(fs.readFileSync(first, "utf8"), "PRE-EXISTING");
  const r2 = store.load();
  assert.equal(r2.badCopy, path.join(b, `settings.bad-${STAMP}-3.json`));
});

test("load：未知键忽略（不算坏文件）、写盘后消失", () => {
  const b = base();
  const withUnknown = Object.assign({}, DEFAULTS, {
    theme: "dark",
    density: "compact",
    futureKey: { a: 1 },
    another: "x",
  });
  fs.writeFileSync(path.join(b, "settings.json"), `${JSON.stringify(withUnknown, null, 2)}\n`);
  const store = makeStore(b);
  const r = store.load();
  assert.equal(r.badCopy, null);
  assert.deepEqual(r.settings, Object.assign({}, DEFAULTS, { theme: "dark", density: "compact" }));
  store.save(r.settings);
  const written = JSON.parse(fs.readFileSync(store.filePath, "utf8"));
  assert.deepEqual(Object.keys(written), SETTINGS_FILE_KEYS);
  assert.equal("futureKey" in written, false);
  assert.equal("another" in written, false);
});

test("load：合法文件原样读入（含 lastOpened 与两个路径）", () => {
  const b = base();
  const good = withRepos();
  fs.writeFileSync(path.join(b, "settings.json"), `${JSON.stringify(good, null, 2)}\n`);
  const r = makeStore(b).load();
  assert.equal(r.badCopy, null);
  assert.deepEqual(r.settings, good);
});

test("save：内容是 JSON.stringify(obj, null, 2) + 换行、键序照 SETTINGS_FILE_KEYS、只保留这些键", () => {
  const b = base();
  const store = makeStore(b);
  const s = Object.assign({}, DEFAULTS, { theme: "light" }, { junk: "should-not-write" });
  store.save(s);
  const expected = {};
  for (const key of SETTINGS_FILE_KEYS) expected[key] = s[key];
  assert.equal(fs.readFileSync(store.filePath, "utf8"), `${JSON.stringify(expected, null, 2)}\n`);
});

test("save：目录不存在也能写，成功后不留临时文件", () => {
  const b = base();
  const dir = path.join(b, "nested", "userData");
  const store = makeStore(dir);
  store.save(clone(DEFAULTS));
  assert.ok(fs.statSync(path.join(dir, "settings.json")).isFile());
  assert.equal(fs.existsSync(path.join(dir, "settings.json.tmp")), false);
});

test("save：原子写——先写 <filePath>.tmp 再换名覆盖正式文件", () => {
  const b = base();
  const store = makeStore(b);
  store.save(Object.assign({}, DEFAULTS, { theme: "dark" }));
  const realRename = fs.renameSync;
  const seen = [];
  fs.renameSync = (from, to) => {
    seen.push([from, to]);
    return realRename(from, to);
  };
  try {
    store.save(Object.assign({}, DEFAULTS, { theme: "light" }));
  } finally {
    fs.renameSync = realRename;
  }
  assert.equal(seen.length, 1, "一次保存只换名一次");
  assert.equal(seen[0][0], `${store.filePath}.tmp`, "换名的来源必须是临时文件");
  assert.equal(seen[0][1], store.filePath);
  assert.equal(JSON.parse(fs.readFileSync(store.filePath, "utf8")).theme, "light", "换名要覆盖已有的正式文件");
});

test("save：写临时文件失败 → 抛错且原文件不动", () => {
  const b = base();
  const store = makeStore(b);
  store.save(Object.assign({}, DEFAULTS, { theme: "dark" }));
  const before = fs.readFileSync(store.filePath);
  fs.mkdirSync(`${store.filePath}.tmp`);
  assert.throws(() => store.save(Object.assign({}, DEFAULTS, { theme: "light" })));
  assert.deepEqual(fs.readFileSync(store.filePath), before);
});

test("save：换名失败 → 抛错且临时文件被清掉", () => {
  const b = base();
  fs.mkdirSync(path.join(b, "settings.json"));
  const store = makeStore(b);
  assert.throws(() => store.save(clone(DEFAULTS)));
  assert.equal(fs.existsSync(`${store.filePath}.tmp`), false);
  assert.ok(fs.statSync(store.filePath).isDirectory());
});

test("normalizeSettings：合法整包 ok 且丢掉未知键；已知键非法 ok:false", () => {
  assert.equal(normalizeSettings(withRepos()).ok, true);
  const nr = normalizeSettings(Object.assign(withRepos(), { future: 1 }));
  assert.equal(nr.ok, true);
  assert.equal("future" in nr.settings, false);
  for (const [key, value] of [
    ["theme", "neon"],
    ["density", "cozy"],
    ["version", 2],
    ["currentRepo", 5],
    ["kitPath", 7],
    ["pythonPath", 7],
    ["repos", "x"],
  ]) {
    assert.equal(normalizeSettings(Object.assign(withRepos(), { [key]: value })).ok, false, `${key}=${value}`);
  }
  assert.equal(normalizeSettings(null).ok, false);
  assert.equal(normalizeSettings([1]).ok, false);
});

const REJECTS = [
  ["null", null, "bad-patch"],
  ["数组", [1], "bad-patch"],
  ["字符串", "theme=dark", "bad-patch"],
  ["数字", 42, "bad-patch"],
  ["布尔", true, "bad-patch"],
  ["undefined", undefined, "bad-patch"],
  ["未知键", { foo: "x" }, "bad-patch"],
  ["theme 非法", { theme: "neon" }, "bad-patch"],
  ["theme 非字符串", { theme: 3 }, "bad-patch"],
  ["theme null", { theme: null }, "bad-patch"],
  ["density 非法", { density: "cozy" }, "bad-patch"],
  ["resetPython 是字符串", { resetPython: "true" }, "bad-patch"],
  ["resetPython false", { resetPython: false }, "bad-patch"],
  ["resetKit 是数字", { resetKit: 1 }, "bad-patch"],
  ["removeRepo 非字符串", { removeRepo: 12 }, "bad-patch"],
  ["removeTranscriptDir 非字符串", { removeTranscriptDir: {} }, "bad-patch"],
  ["removeRepo 指向不存在的 id", { removeRepo: "ghost" }, "unknown-id"],
  ["removeTranscriptDir 指向不存在的 id", { removeTranscriptDir: "ghost" }, "unknown-id"],
  ["removeRepo 指向当前仓库", { removeRepo: "r1" }, "current-repo"],
  ["路径值当 removeRepo", { removeRepo: "C:/nowhere/alpha" }, "unknown-id"],
];

for (const [name, patch, reason] of REJECTS) {
  test(`applyPatch 拒绝：${name} → ${reason}`, () => {
    const r = applyPatch(withRepos(), patch);
    assert.equal(r.ok, false, name);
    assert.equal(r.reason, reason, `${name}：${JSON.stringify(r)}`);
  });
}

test("applyPatch 校验顺序：形状 → id 存在性 → 当前仓库", () => {
  const s = withRepos();
  assert.equal(applyPatch(s, { removeRepo: "ghost", theme: "neon" }).reason, "bad-patch");
  assert.equal(applyPatch(s, { removeRepo: "r1", density: "cozy" }).reason, "bad-patch");
  assert.equal(applyPatch(s, { removeTranscriptDir: "ghost", removeRepo: "r1" }).reason, "unknown-id");
});

test("applyPatch：拒绝与成功都不改入参；整包合格才应用", () => {
  const s = withRepos();
  const snap = clone(s);
  for (const patch of [{ foo: 1 }, { removeRepo: "r1" }, { removeRepo: "ghost" }]) {
    assert.equal(applyPatch(s, patch).ok, false);
    assert.deepEqual(s, snap, JSON.stringify(patch));
  }
  const ok = applyPatch(s, {
    theme: "dark",
    density: "compact",
    removeRepo: "r2",
    removeTranscriptDir: "d1",
    resetPython: true,
    resetKit: true,
  });
  assert.equal(ok.ok, true, JSON.stringify(ok));
  assert.notEqual(ok.settings, s);
  assert.deepEqual(s, snap);
  assert.equal(ok.settings.theme, "dark");
  assert.equal(ok.settings.density, "compact");
  assert.deepEqual(ok.settings.repos.map((x) => x.id), ["r1"]);
  assert.deepEqual(ok.settings.transcriptDirs, []);
  assert.equal(ok.settings.pythonPath, null);
  assert.equal(ok.settings.kitPath, null);
  assert.equal(ok.settings.currentRepo, "r1");
});

test("applyPatch：空补丁合格，设置原样但是新对象", () => {
  const s = withRepos();
  const r = applyPatch(s, {});
  assert.equal(r.ok, true);
  assert.deepEqual(r.settings, s);
  assert.notEqual(r.settings, s);
});

test("saveSettings 的六类拒绝：文件字节不变（经 store 走一遍）", () => {
  const b = base();
  const store = makeStore(b);
  const s = withRepos();
  store.save(s);
  const before = fs.readFileSync(store.filePath);
  for (const [name, patch, reason] of REJECTS) {
    const r = applyPatch(store.load().settings, patch);
    assert.equal(r.ok, false, name);
    assert.equal(r.reason, reason, name);
    assert.deepEqual(fs.readFileSync(store.filePath), before, `${name} 之后文件字节必须不变`);
  }
});

test("addRepo：新条目 id 取目录名、lastOpened 为 null、currentRepo 为空时设当前", () => {
  const b = base();
  const repo = path.join(b, "alpha");
  fs.mkdirSync(repo);
  const s = clone(DEFAULTS);
  const r = addRepo(s, repo);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.id, "alpha");
  assert.equal(r.reused, false);
  assert.deepEqual(r.settings.repos, [{ id: "alpha", name: "alpha", path: repo, lastOpened: null }]);
  assert.equal(r.settings.currentRepo, "alpha");
  assert.deepEqual(s, clone(DEFAULTS), "入参不许被改");
});

test("addRepo：相同路径 reused 沿用原 id、条目不增；Windows 下不分大小写", () => {
  const b = base();
  const repo = path.join(b, "alpha");
  fs.mkdirSync(repo);
  let s = addRepo(clone(DEFAULTS), repo).settings;
  const variant = process.platform === "win32" ? repo.split(path.sep).join("/") : repo;
  const r2 = addRepo(s, variant);
  assert.equal(r2.reused, true, JSON.stringify(r2));
  assert.equal(r2.id, "alpha");
  assert.equal(r2.settings.repos.length, 1);
  if (process.platform === "win32") {
    const r3 = addRepo(s, repo.toUpperCase());
    assert.equal(r3.reused, true, "Windows 下路径比较要转小写");
    assert.equal(r3.id, "alpha");
    assert.equal(r3.settings.repos.length, 1);
  }
});

test("addRepo：id 撞了依次 -2、-3", () => {
  const b = base();
  const a1 = path.join(b, "one", "alpha");
  const a2 = path.join(b, "two", "alpha");
  const a3 = path.join(b, "three", "alpha");
  fs.mkdirSync(a1, { recursive: true });
  fs.mkdirSync(a2, { recursive: true });
  fs.mkdirSync(a3, { recursive: true });
  let s = addRepo(clone(DEFAULTS), a1).settings;
  const r2 = addRepo(s, a2);
  assert.equal(r2.id, "alpha-2");
  const r3 = addRepo(r2.settings, a3);
  assert.equal(r3.id, "alpha-3");
  assert.equal(r3.settings.repos.length, 3);
  assert.deepEqual(r3.settings.repos.map((x) => x.name), ["alpha", "alpha", "alpha"]);
});

test("addRepo：currentRepo 已有时不换", () => {
  const b = base();
  const a = path.join(b, "alpha");
  const beta = path.join(b, "beta");
  fs.mkdirSync(a);
  fs.mkdirSync(beta);
  let s = addRepo(clone(DEFAULTS), a).settings;
  const r2 = addRepo(s, beta);
  assert.equal(r2.id, "beta");
  assert.equal(r2.settings.currentRepo, "alpha");
});

test("addRepo：基名为空（盘根）时 name 用 repo", () => {
  const root = path.parse(process.cwd()).root;
  const r = addRepo(clone(DEFAULTS), root);
  assert.equal(r.ok, true);
  assert.equal(r.id, "repo");
  assert.equal(r.settings.repos[0].name, "repo");
});

test("addTranscriptDir：id 基名 dir、撞了 -2、同路径 reused", () => {
  const b = base();
  const d1 = path.join(b, "logs1");
  const d2 = path.join(b, "logs2");
  fs.mkdirSync(d1);
  fs.mkdirSync(d2);
  const r1 = addTranscriptDir(clone(DEFAULTS), d1);
  assert.equal(r1.ok, true, JSON.stringify(r1));
  assert.equal(r1.id, "dir");
  assert.equal(r1.reused, false);
  assert.deepEqual(r1.settings.transcriptDirs, [{ id: "dir", path: d1 }]);
  const r2 = addTranscriptDir(r1.settings, d2);
  assert.equal(r2.id, "dir-2");
  const r3 = addTranscriptDir(r2.settings, d1);
  assert.equal(r3.reused, true);
  assert.equal(r3.id, "dir");
  assert.equal(r3.settings.transcriptDirs.length, 2);
  assert.equal(addTranscriptDir(r2.settings, d1).settings.currentRepo, null, "加目录不动 currentRepo");
});
