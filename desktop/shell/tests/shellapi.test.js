"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createSettingsStore, DEFAULT_SETTINGS } = require("../src/settings.js");
const { createShellApi } = require("../src/shellapi.js");

const HOMEPAGE = "https://github.com/mrQzs/ThemisTally";

function makeHarness(over) {
  const opts = over || {};
  const failingSave = opts.failingSave === true;
  const b = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-api-")));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  const realStore = createSettingsStore({ dir: userData });
  const store = failingSave
    ? {
        dir: realStore.dir,
        filePath: realStore.filePath,
        load: () => realStore.load(),
        save: () => {
          throw new Error("disk full");
        },
      }
    : realStore;
  const chooser = { dir: null, file: null };
  const confirm = { answer: true, throwIt: false, calls: [] };
  const opener = { throwIt: false, calls: [] };
  const probeState = {
    pythonResult: { ok: true, version: "3.12.9", path: "/fake/python-exe" },
    kitResult: { ok: true, version: "2.12.0" },
    autoPython: { status: "ok", source: "auto", path: "/auto/py", version: "3.13.1" },
    pythonCalls: [],
    kitCalls: [],
    autoPythonCalls: [],
    autoKitCalls: [],
  };
  const probe = {
    async probePython(commandArgs) {
      probeState.pythonCalls.push(commandArgs);
      return JSON.parse(JSON.stringify(probeState.pythonResult));
    },
    async probeKit(pythonPath, kitDir) {
      probeState.kitCalls.push([pythonPath, kitDir]);
      return JSON.parse(JSON.stringify(probeState.kitResult));
    },
    async detectPython() {
      probeState.autoPythonCalls.push(true);
      return JSON.parse(JSON.stringify(probeState.autoPython));
    },
    async detectKit(options) {
      probeState.autoKitCalls.push(options);
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
    store,
    chooseDirectory: async () => chooser.dir,
    chooseFile: async () => chooser.file,
    confirmExternal: async (url) => {
      confirm.calls.push(url);
      if (confirm.throwIt) throw new Error("确认框坏了");
      return confirm.answer;
    },
    openExternal: async (url) => {
      opener.calls.push(url);
      if (opener.throwIt) throw new Error("打不开");
    },
    appVersion: "9.9.9",
    probe,
  });
  const gitRepo = (name) => {
    const d = path.join(b, name);
    fs.mkdirSync(path.join(d, ".git"), { recursive: true });
    fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
    return d;
  };
  const plainDir = (name) => {
    const d = path.join(b, name);
    fs.mkdirSync(d, { recursive: true });
    return d;
  };
  const bytes = () => (fs.existsSync(store.filePath) ? fs.readFileSync(store.filePath) : null);
  const writeSettings = (mutate) => {
    const s = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    mutate(s);
    realStore.save(s);
  };
  return { b, api, store, chooser, confirm, opener, probeState, gitRepo, plainDir, bytes, writeSettings };
}

test("getState：信封与缺省设置（五个字段）、app、service、没有 pythonPath/kitPath", async () => {
  const h = makeHarness();
  const r = await h.api.getState();
  assert.deepEqual(Object.keys(r).sort(), ["ok", "value"]);
  assert.equal(r.ok, true);
  const st = r.value;
  assert.deepEqual(st.app, { version: "9.9.9", homepage: HOMEPAGE });
  assert.deepEqual(Object.keys(st.settings).sort(), [
    "currentRepo",
    "density",
    "repos",
    "theme",
    "transcriptDirs",
  ]);
  assert.deepEqual(st.settings, {
    repos: [],
    currentRepo: null,
    transcriptDirs: [],
    theme: "system",
    density: "standard",
  });
  assert.equal(st.currentRepoCheck, null);
  assert.deepEqual(st.service, { kind: "idle" });
});

test("getState：appVersion 与 homepage 的缺省值", async () => {
  const h = makeHarness();
  const api = createShellApi({
    store: createSettingsStore({ dir: path.join(h.b, "other") }),
    chooseDirectory: async () => null,
    chooseFile: async () => null,
    confirmExternal: async () => true,
    openExternal: async () => {},
  });
  const st = (await api.getState()).value;
  assert.deepEqual(st.app, { version: "", homepage: HOMEPAGE });
});

test("getState：设置里的 pythonPath 非空 → probePython([该路径])、source custom；kit 走 external", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("mykit");
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
    s.kitPath = kitDir;
  });
  const st = (await h.api.getState()).value;
  assert.deepEqual(h.probeState.pythonCalls, [[process.execPath]]);
  assert.deepEqual(st.python, { status: "ok", source: "custom", path: "/fake/python-exe", version: "3.12.9" });
  assert.equal(st.kit.status, "ok");
  assert.equal(st.kit.source, "external");
  assert.equal(st.kit.version, "2.12.0");
  assert.equal(path.resolve(st.kit.path), path.resolve(path.join(kitDir, "scripts", "pi_dispatch.py")));
  assert.equal(h.probeState.kitCalls.length, 1);
  assert.equal(h.probeState.kitCalls[0][0], "/fake/python-exe", "probeKit 要用探测到的解释器");
  assert.equal(h.probeState.kitCalls[0][1], kitDir);
});

test("getState：pythonPath 为空 → 自动检测直通（source auto）", async () => {
  const h = makeHarness();
  const st = (await h.api.getState()).value;
  assert.equal(h.probeState.autoPythonCalls.length, 1);
  assert.equal(h.probeState.pythonCalls.length, 0);
  assert.deepEqual(st.python, { status: "ok", source: "auto", path: "/auto/py", version: "3.13.1" });
  assert.equal(st.kit.status, "missing", "既没有 kitPath 也没有当前仓库时 kit 必须 missing");
});

test("getState：自定义 Python 不可用 → missing(custom)；external kit 没有可用 Python → missing", async () => {
  const h = makeHarness();
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
    s.kitPath = h.plainDir("k");
  });
  h.probeState.pythonResult = { ok: false, reason: "version-too-old" };
  h.probeState.autoPython = { status: "missing", source: "auto", path: "", version: "" };
  const st = (await h.api.getState()).value;
  assert.deepEqual(st.python, { status: "missing", source: "custom", path: "", version: "" });
  assert.equal(st.kit.status, "missing");
  assert.equal(st.kit.source, "external");
  assert.equal(h.probeState.kitCalls.length, 0, "没有可用 Python 时不许探测 kit");
});

test("getState：currentRepoCheck 按 checkRepo 判（ok / not-git / no-agent），id 找不到为 null", async () => {
  const mk = async (make) => {
    const h = makeHarness();
    const repo = make(h);
    h.writeSettings((s) => {
      s.repos = [{ id: "r", name: "r", path: repo, lastOpened: null }];
      s.currentRepo = "r";
    });
    return (await h.api.getState()).value.currentRepoCheck;
  };
  assert.equal(await mk((h) => h.gitRepo("good")), "ok");
  assert.equal(await mk((h) => h.plainDir("plain")), "not-git");
  assert.equal(
    await mk((h) => {
      const d = path.join(h.b, "noagent");
      fs.mkdirSync(path.join(d, ".git"), { recursive: true });
      return d;
    }),
    "no-agent",
  );
  const h = makeHarness();
  h.writeSettings((s) => {
    s.repos = [];
    s.currentRepo = "ghost";
  });
  assert.equal((await h.api.getState()).value.currentRepoCheck, null);
});

test("pickRepo：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  assert.deepEqual(await h.api.pickRepo(), { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickRepo：不是 Git 仓库 → rejected(not-git)，不写盘", async () => {
  const h = makeHarness();
  const d = h.plainDir("plain");
  h.chooser.dir = d;
  assert.deepEqual(await h.api.pickRepo(), {
    ok: true,
    value: { kind: "rejected", problem: "not-git", path: d },
  });
  assert.equal(h.bytes(), null);
});

test("pickRepo：没有 .agent 目录 → rejected(no-agent)，不写盘", async () => {
  const h = makeHarness();
  const d = path.join(h.b, "noagent");
  fs.mkdirSync(path.join(d, ".git"), { recursive: true });
  h.chooser.dir = d;
  assert.deepEqual(await h.api.pickRepo(), {
    ok: true,
    value: { kind: "rejected", problem: "no-agent", path: d },
  });
  assert.equal(h.bytes(), null);
});

test("pickRepo：合法仓库 → saved（id 与 state）、写盘、currentRepo 为空时设当前", async () => {
  const h = makeHarness();
  const d = h.gitRepo("alpha");
  h.chooser.dir = d;
  const r = await h.api.pickRepo();
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.kind, "saved");
  assert.equal(r.value.path, d);
  assert.equal(r.value.id, "alpha");
  assert.deepEqual(r.value.state.settings.repos, [
    { id: "alpha", name: "alpha", path: d, lastOpened: null },
  ]);
  assert.equal(r.value.state.settings.currentRepo, "alpha");
  assert.equal(r.value.state.currentRepoCheck, "ok");
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.currentRepo, "alpha");
  assert.deepEqual(onDisk.repos.map((x) => x.id), ["alpha"]);
  assert.deepEqual(Object.keys(onDisk).sort(), [
    "currentRepo",
    "density",
    "kitPath",
    "pythonPath",
    "repos",
    "theme",
    "transcriptDirs",
    "version",
  ]);
});

test("pickRepo：currentRepo 已有时不换；同一路径沿用原 id、条目不增", async () => {
  const h = makeHarness();
  const a = h.gitRepo("alpha");
  const beta = h.gitRepo("beta");
  h.chooser.dir = a;
  await h.api.pickRepo();
  h.chooser.dir = beta;
  const r2 = await h.api.pickRepo();
  assert.equal(r2.value.id, "beta");
  assert.equal(r2.value.state.settings.currentRepo, "alpha");
  h.chooser.dir = a;
  const r3 = await h.api.pickRepo();
  assert.equal(r3.value.kind, "saved");
  assert.equal(r3.value.id, "alpha");
  assert.equal(r3.value.state.settings.repos.length, 2);
  assert.equal(r3.value.state.settings.currentRepo, "alpha");
});

test("pickPython：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.file = null;
  assert.deepEqual(await h.api.pickPython(), { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickPython：探测失败 → rejected(python-unusable)，不写盘", async () => {
  const h = makeHarness();
  h.chooser.file = "C:/nowhere/py.exe";
  h.probeState.pythonResult = { ok: false, reason: "version-too-old" };
  assert.deepEqual(await h.api.pickPython(), {
    ok: true,
    value: { kind: "rejected", problem: "python-unusable", path: "C:/nowhere/py.exe" },
  });
  assert.equal(h.bytes(), null);
  assert.deepEqual(h.probeState.pythonCalls, [["C:/nowhere/py.exe"]]);
});

test("pickPython：成功 → saved 没有 id 字段、pythonPath 写盘", async () => {
  const h = makeHarness();
  h.chooser.file = process.execPath;
  const r = await h.api.pickPython();
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.kind, "saved");
  assert.equal(r.value.path, process.execPath);
  assert.equal("id" in r.value, false, "pickPython 的 saved 没有 id 字段");
  assert.equal(r.value.state.python.status, "ok");
  assert.equal(r.value.state.python.source, "custom");
  assert.equal(JSON.parse(fs.readFileSync(h.store.filePath, "utf8")).pythonPath, process.execPath);
});

test("pickKit：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  assert.deepEqual(await h.api.pickKit(), { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickKit：没有可用 Python → rejected(python-unusable)，不写盘", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit1");
  h.chooser.dir = kitDir;
  h.probeState.autoPython = { status: "missing", source: "auto", path: "", version: "" };
  assert.deepEqual(await h.api.pickKit(), {
    ok: true,
    value: { kind: "rejected", problem: "python-unusable", path: kitDir },
  });
  assert.equal(h.bytes(), null);
});

test("pickKit：探测失败 → rejected(kit-unusable)，文件字节不变", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit2");
  h.chooser.dir = kitDir;
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
  });
  const before = h.bytes();
  h.probeState.kitResult = { ok: false, reason: "kit-unusable" };
  assert.deepEqual(await h.api.pickKit(), {
    ok: true,
    value: { kind: "rejected", problem: "kit-unusable", path: kitDir },
  });
  assert.deepEqual(h.bytes(), before);
});

test("pickKit：成功 → saved 没有 id 字段、kitPath 写盘", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit3");
  h.chooser.dir = kitDir;
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
  });
  const r = await h.api.pickKit();
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.kind, "saved");
  assert.equal(r.value.path, kitDir);
  assert.equal("id" in r.value, false, "pickKit 的 saved 没有 id 字段");
  assert.equal(JSON.parse(fs.readFileSync(h.store.filePath, "utf8")).kitPath, kitDir);
});

test("pickTranscriptDir：取消 → cancelled，不写盘；同路径沿用 id 不重复", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  assert.deepEqual(await h.api.pickTranscriptDir(), { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
  const d1 = h.plainDir("logs");
  const d2 = h.plainDir("other");
  h.chooser.dir = d1;
  const r1 = await h.api.pickTranscriptDir();
  assert.equal(r1.value.kind, "saved");
  assert.equal(r1.value.id, "dir");
  assert.deepEqual(r1.value.state.settings.transcriptDirs, [{ id: "dir", path: d1 }]);
  h.chooser.dir = d2;
  assert.equal((await h.api.pickTranscriptDir()).value.id, "dir-2");
  h.chooser.dir = d1;
  const r3 = await h.api.pickTranscriptDir();
  assert.equal(r3.value.kind, "saved", "pickTranscriptDir 不回 rejected");
  assert.equal(r3.value.id, "dir");
  assert.equal(r3.value.state.settings.transcriptDirs.length, 2);
});

test("缓存：getState 不重复探测；pickPython 与 saveSettings(resetPython) 之后刷新", async () => {
  const h = makeHarness();
  await h.api.getState();
  await h.api.getState();
  assert.equal(h.probeState.autoPythonCalls.length, 1, "两次 getState 只许探测一次 Python");
  h.chooser.file = null;
  await h.api.pickPython();
  await h.api.getState();
  assert.equal(h.probeState.autoPythonCalls.length, 2, "pickPython 之后要重新探测（取消也算）");
  await h.api.getState();
  assert.equal(h.probeState.autoPythonCalls.length, 2);
  const r = await h.api.saveSettings({ resetPython: true });
  assert.equal(r.ok, true, JSON.stringify(r));
  await h.api.getState();
  assert.equal(h.probeState.autoPythonCalls.length, 3, "saveSettings(resetPython) 之后要重新探测");
});

test("缓存：有当前仓库时 pickKit 之后 kit 缓存刷新", async () => {
  const h = makeHarness();
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
    s.repos = [{ id: "r", name: "rr", path: h.gitRepo("rr"), lastOpened: null }];
    s.currentRepo = "r";
  });
  await h.api.getState();
  await h.api.getState();
  const kitProbes = () => h.probeState.kitCalls.length + h.probeState.autoKitCalls.length;
  assert.equal(kitProbes(), 1, "两次 getState 只许探测一次 kit");
  h.chooser.dir = null;
  await h.api.pickKit();
  await h.api.getState();
  assert.equal(kitProbes(), 2, "pickKit 之后要重新探测（取消也算）");
});

test("saveSettings：垃圾输入与各类拒绝都回信封、文件字节与内存状态都不变", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  const before = h.bytes();
  const pathLikeId = `C:${path.sep}some${path.sep}path`;
  const cases = [
    [null, "bad-patch"],
    [undefined, "bad-patch"],
    [123, "bad-patch"],
    ["theme=dark", "bad-patch"],
    [[], "bad-patch"],
    [true, "bad-patch"],
    [false, "bad-patch"],
    [{ theme: "dark", extra: 1 }, "bad-patch"],
    [{ theme: "neon" }, "bad-patch"],
    [{ density: "cozy" }, "bad-patch"],
    [{ resetPython: "yes" }, "bad-patch"],
    [{ removeRepo: 5 }, "bad-patch"],
    [{ removeRepo: "ghost" }, "unknown-id"],
    [{ removeTranscriptDir: "ghost" }, "unknown-id"],
    [{ removeRepo: "alpha" }, "current-repo"],
    [{ removeRepo: pathLikeId }, "unknown-id"],
  ];
  for (const [patch, reason] of cases) {
    assert.deepEqual(await h.api.saveSettings(patch), { ok: false, reason }, JSON.stringify(patch));
    assert.deepEqual(h.bytes(), before, "拒绝后文件字节必须不变");
  }
  const st = (await h.api.getState()).value;
  assert.equal(st.settings.repos.length, 1, "拒绝后内存状态也不变");
  assert.equal(st.settings.theme, "system");
});

test("saveSettings：校验顺序 bad-patch → unknown-id → current-repo", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  assert.deepEqual(await h.api.saveSettings({ removeRepo: "ghost", theme: "neon" }), {
    ok: false,
    reason: "bad-patch",
  });
  assert.deepEqual(await h.api.saveSettings({ removeTranscriptDir: "ghost", removeRepo: "alpha" }), {
    ok: false,
    reason: "unknown-id",
  });
});

test("saveSettings：整包合格才应用并写盘，回新的 ShellState", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.gitRepo("beta");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  h.chooser.file = process.execPath;
  await h.api.pickPython();
  const r = await h.api.saveSettings({
    theme: "dark",
    density: "compact",
    removeRepo: "beta",
    removeTranscriptDir: "dir",
    resetPython: true,
  });
  assert.deepEqual(Object.keys(r).sort(), ["ok", "value"]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.settings.theme, "dark");
  assert.equal(r.value.settings.density, "compact");
  assert.deepEqual(r.value.settings.repos.map((x) => x.id), ["alpha"]);
  assert.deepEqual(r.value.settings.transcriptDirs, []);
  assert.equal(r.value.settings.currentRepo, "alpha");
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.theme, "dark");
  assert.equal(onDisk.pythonPath, null);
  assert.deepEqual(onDisk.repos.map((x) => x.id), ["alpha"]);
});

test("写盘失败 → write-failed、内存状态回滚（pickRepo 与 saveSettings 都不抛错）", async () => {
  const h = makeHarness({ failingSave: true });
  h.chooser.dir = h.gitRepo("alpha");
  assert.deepEqual(await h.api.pickRepo(), { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.repos.length, 0, "写盘失败不许改内存状态");
  assert.deepEqual(await h.api.saveSettings({ theme: "dark" }), { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.theme, "system", "写盘失败后内存要回滚");
});

test("占位：startService/restartService 回 not-implemented；on 同步返回退订函数且不抛错", async () => {
  const h = makeHarness();
  assert.deepEqual(await h.api.startService("C:/repo"), { ok: false, reason: "not-implemented" });
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "not-implemented" });
  let fired = 0;
  const off = h.api.on("service-state", () => {
    fired += 1;
  });
  assert.equal(typeof off, "function", "on 必须同步返回退订函数");
  assert.equal(fired, 0, "on 不许调用 listener");
  assert.doesNotThrow(() => off());
});

test("十个成员：名字与个数照合同", () => {
  const h = makeHarness();
  assert.deepEqual(Object.keys(h.api), [
    "getState",
    "pickRepo",
    "pickPython",
    "pickKit",
    "pickTranscriptDir",
    "saveSettings",
    "startService",
    "restartService",
    "openExternal",
    "on",
  ]);
});
