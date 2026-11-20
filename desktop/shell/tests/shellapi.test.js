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
  const ops = { captured: null, calls: 0 };
  const api = createShellApi({
    store,
    initialSettings: opts.initialSettings,
    onAppearanceChange: opts.onAppearanceChange,
    onRepoOps: (handed) => { ops.captured = handed; ops.calls += 1; },
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
  return { b, api, store, chooser, confirm, opener, probeState, gitRepo, plainDir, bytes, writeSettings, ops };
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
    theme: "dark",
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

test("缓存：saveSettings({resetKit:true}) 之后 kit 缓存刷新", async () => {
  const h = makeHarness();
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
    s.kitPath = h.plainDir("kitdir");
    s.repos = [{ id: "r", name: "rr", path: h.gitRepo("rr"), lastOpened: null }];
    s.currentRepo = "r";
  });
  await h.api.getState();
  await h.api.getState();
  const kitProbes = () => h.probeState.kitCalls.length + h.probeState.autoKitCalls.length;
  assert.equal(kitProbes(), 1, "两次 getState 只许探测一次 kit");
  const r = await h.api.saveSettings({ resetKit: true });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.kit.source, "repo", "resetKit 之后 kitPath 已清空，改按当前仓库探测");
  await h.api.getState();
  assert.equal(kitProbes(), 2, "saveSettings(resetKit) 之后要重新探测 kit");
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
  assert.equal(st.settings.theme, "dark");
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

test("openExternal：非 http/https、控制字符、首尾空白 → bad-url，不进确认框", async () => {
  const h = makeHarness();
  const bad = [
    "ftp://example.com/a",
    "javascript:alert(1)",
    `file:///C:/windows`,
    "https://example.com/a\n",
    "https://example.com/a\u0000b",
    "  https://example.com  ",
    "example.com",
    "",
    42,
    null,
    undefined,
  ];
  for (const url of bad) {
    assert.deepEqual(await h.api.openExternal(url), { ok: false, reason: "bad-url" }, JSON.stringify(url));
  }
  assert.equal(h.confirm.calls.length, 0, "bad-url 不许进确认框");
  assert.equal(h.opener.calls.length, 0, "bad-url 不许打开");
});

test("openExternal：确认框回 false → cancelled，不打开", async () => {
  const h = makeHarness();
  h.confirm.answer = false;
  const url = "https://example.com/a";
  assert.deepEqual(await h.api.openExternal(url), { ok: false, reason: "cancelled" });
  assert.deepEqual(h.confirm.calls, [url], "确认框要拿到待打开的地址");
  assert.equal(h.opener.calls.length, 0, "用户没确认不许打开");
});

test("openExternal：确认框抛错 → internal；打开抛错 → open-failed", async () => {
  const h = makeHarness();
  h.confirm.throwIt = true;
  assert.deepEqual(await h.api.openExternal("https://example.com/"), { ok: false, reason: "internal" });
  assert.equal(h.opener.calls.length, 0);
  const h2 = makeHarness();
  h2.opener.throwIt = true;
  assert.deepEqual(await h2.api.openExternal("https://example.com/"), { ok: false, reason: "open-failed" });
  assert.deepEqual(h2.opener.calls, ["https://example.com/"]);
});

test("openExternal：用户确认 → {ok:true, value:null}，地址交给注入的 opener", async () => {
  const h = makeHarness();
  const url = "https://github.com/mrQzs/ThemisTally";
  assert.deepEqual(await h.api.openExternal(url), { ok: true, value: null });
  assert.deepEqual(h.confirm.calls, [url]);
  assert.deepEqual(h.opener.calls, [url]);
});

test("写盘失败 → write-failed、内存状态回滚（pickRepo 与 saveSettings 都不抛错）", async () => {
  const h = makeHarness({ failingSave: true });
  h.chooser.dir = h.gitRepo("alpha");
  assert.deepEqual(await h.api.pickRepo(), { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.repos.length, 0, "写盘失败不许改内存状态");
  assert.deepEqual(await h.api.saveSettings({ theme: "light" }), { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.theme, "dark", "写盘失败后内存要回滚");
});

test("startService 按仓库 id 真起服务；restartService 按当前设置重启；on 真订阅", async () => {
  const h = makeHarness();
  const alpha = h.gitRepo("alpha");
  const beta = h.gitRepo("beta");
  const kitDir = h.plainDir("mykit");
  const logs = h.plainDir("logs");
  // 每个场景都从同一份设置起步：当前仓库是 alpha，要起的是 beta
  const setup = (kitPath) =>
    h.writeSettings((s) => {
      s.repos = [
        { id: "alpha", name: "alpha", path: alpha, lastOpened: null },
        { id: "beta", name: "beta", path: beta, lastOpened: null },
      ];
      s.currentRepo = "alpha";
      s.transcriptDirs = [{ id: "dir", path: logs }];
      s.kitPath = kitPath;
    });
  setup(kitDir);
  // 假的 probe 与假的控制器：现场记录 kit 是按哪个目录探测的
  const kitCalls = [];
  const autoPython = { status: "ok", source: "auto", path: "/auto/py", version: "3.13.1" };
  const kitResult = { ok: true, version: "2.12.0" };
  const probe = {
    async probePython() {
      return { ok: true, version: "3.12.9", path: "/fake/python-exe" };
    },
    async probeKit(pythonPath, kitDir) {
      kitCalls.push([pythonPath, kitDir]);
      return JSON.parse(JSON.stringify(kitResult));
    },
    async detectPython() {
      return JSON.parse(JSON.stringify(autoPython));
    },
    async detectKit() {
      return { status: "missing", source: "repo", path: "", version: "" };
    },
  };
  const listeners = new Set();
  const ctl = {
    starts: [],
    currentState: { kind: "idle" },
    nextStart: { ok: true, value: null },
    start(arg) {
      ctl.starts.push(JSON.parse(JSON.stringify(arg)));
      return Promise.resolve(ctl.nextStart);
    },
    stop() {
      return Promise.resolve({ exited: true, code: 0, signal: null });
    },
    abort() {
      return Promise.resolve();
    },
    state() {
      return ctl.currentState;
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => {
        listeners.delete(fn);
      };
    },
    emit(state) {
      for (const fn of [...listeners]) fn(state, { byShell: false });
    },
  };
  // 每个场景一个 api：探测结果有缓存，混用一个 api 会串味
  const makeApi = (over) =>
    createShellApi(
      Object.assign(
        {
          store: h.store,
          service: ctl,
          assets: "/assets/root",
          chooseDirectory: async () => null,
          chooseFile: async () => null,
          confirmExternal: async () => true,
          openExternal: async () => {},
          appVersion: "9.9.9",
          probe,
        },
        over,
      ),
    );
  // 命令形状与带参数那条路同一个 serviceCommand（同一个模块、同一份产物）
  const { serviceCommand } = require("../src/service.js");

  // 仓库 id 不在设置列表 → unknown-repo，控制器没被调用（没起进程）、状态不变
  assert.deepEqual(await makeApi().startService("ghost"), { ok: false, reason: "unknown-repo" });
  assert.equal(ctl.starts.length, 0, "id 不在设置列表不许起进程");
  assert.deepEqual((await makeApi().getState()).value.service, { kind: "idle" });

  // Python 不可用 → python-missing，不起进程、不探测 kit
  autoPython.status = "missing";
  autoPython.path = "";
  autoPython.version = "";
  kitCalls.length = 0;
  assert.deepEqual(await makeApi().startService("beta"), { ok: false, reason: "python-missing" });
  assert.equal(ctl.starts.length, 0);
  assert.equal(kitCalls.length, 0, "没有可用 Python 时不许探测 kit");
  autoPython.status = "ok";
  autoPython.path = "/auto/py";
  autoPython.version = "3.13.1";

  // kit 不可用 → kit-missing；kit 按目标仓库算（当前仓库是 alpha，起的是 beta）
  kitResult.ok = false;
  assert.deepEqual(await makeApi().startService("beta"), { ok: false, reason: "kit-missing" });
  assert.equal(ctl.starts.length, 0);
  assert.equal(kitCalls.length, 1, "现场探测 kit 只许一次");
  assert.deepEqual(kitCalls[0], ["/auto/py", kitDir], "kitPath 非空时按它探测");
  setup(null);
  kitResult.ok = false;
  kitCalls.length = 0;
  assert.deepEqual(await makeApi().startService("beta"), { ok: false, reason: "kit-missing" });
  assert.deepEqual(kitCalls[0], ["/auto/py", beta], "kitPath 为空时按目标仓库的 path 探测");
  assert.equal(kitCalls[0][1] === alpha, false, "不许用当前仓库的目录");
  kitResult.ok = true;

  // 别的仓库正忙 → busy；同一个仓库正忙 → 幂等 ok。两者都不再起进程
  ctl.currentState = { kind: "starting", repo: "alpha" };
  assert.deepEqual(await makeApi().startService("beta"), { ok: false, reason: "busy" });
  ctl.currentState = { kind: "running", repo: "beta", pid: 4242, startedAt: "2026-01-01T00:00:00.000Z" };
  assert.deepEqual(await makeApi().startService("beta"), { ok: true, value: null });
  assert.equal(ctl.starts.length, 0, "幂等与忙都不许再起进程");

  // 成功：命令形状与带参数那条路一致，控制器的信封原样回传
  ctl.currentState = { kind: "idle" };
  assert.deepEqual(await makeApi().startService("beta"), { ok: true, value: null });
  assert.equal(ctl.starts.length, 1);
  const arg = ctl.starts[0];
  assert.equal(arg.repo, "beta", "交给控制器的是目标仓库的 id");
  assert.deepEqual(
    arg.command,
    serviceCommand({
      python: ["/auto/py"],
      kit: beta,
      repo: beta,
      assets: "/assets/root",
      transcripts: [logs],
    }),
  );
  // env 用 process.env（假控制器存的是深拷贝，逐键比对，不把整份环境打印出来）
  const sameEnv = (value) => {
    if (value === null || typeof value !== "object") return false;
    const keys = Object.keys(process.env);
    if (Object.keys(value).length !== keys.length) return false;
    return keys.every((key) => value[key] === process.env[key]);
  };
  assert.ok(arg.env === process.env || sameEnv(arg.env), "env 用 process.env");
  ctl.nextStart = { ok: false, reason: "handshake-failed" };
  assert.deepEqual(await makeApi().startService("beta"), { ok: false, reason: "handshake-failed" });

  // 没有注入控制器或产物目录 → no-service 兜底
  const bare = createShellApi({ store: h.store });
  assert.deepEqual(await bare.startService("beta"), { ok: false, reason: "no-service" });
  assert.deepEqual((await bare.getState()).value.service, { kind: "idle" });

  // getState 的 service 取控制器的当前状态
  ctl.currentState = { kind: "exited", repo: "beta", exitCode: 3, at: 12345 };
  assert.deepEqual((await makeApi().getState()).value.service, {
    kind: "exited",
    repo: "beta",
    exitCode: 3,
    at: 12345,
  });

  // restartService：idle（含没有控制器）→ no-previous，不起进程
  ctl.currentState = { kind: "idle" };
  ctl.nextStart = { ok: true, value: null };
  const startsBefore = ctl.starts.length;
  assert.deepEqual(await makeApi().restartService(), { ok: false, reason: "no-previous" });
  assert.equal(ctl.starts.length, startsBefore, "idle 时 restartService 不许起进程");
  assert.deepEqual(await bare.restartService(), { ok: false, reason: "no-previous" });

  // starting / running → 幂等回 ok，不起进程
  ctl.currentState = { kind: "starting", repo: "beta" };
  assert.deepEqual(await makeApi().restartService(), { ok: true, value: null });
  ctl.currentState = { kind: "running", repo: "beta", pid: 4242, startedAt: "2026-01-01T00:00:00.000Z" };
  assert.deepEqual(await makeApi().restartService(), { ok: true, value: null });
  assert.equal(ctl.starts.length, startsBefore, "starting/running 时 restartService 不许起进程");

  // exited 且仓库已从设置里移除 → unknown-repo，不起进程
  setup(kitDir);
  ctl.currentState = { kind: "exited", repo: "ghost", exitCode: 3, at: 1 };
  assert.deepEqual(await makeApi().restartService(), { ok: false, reason: "unknown-repo" });
  assert.equal(ctl.starts.length, startsBefore, "unknown-repo 不许起进程");

  // exited 且条件齐 → 走 startService(exited 里那个 repo)，命令按当前设置算
  ctl.currentState = { kind: "exited", repo: "beta", exitCode: 3, at: 1 };
  assert.deepEqual(await makeApi().restartService(), { ok: true, value: null });
  assert.equal(ctl.starts.length, startsBefore + 1, "exited 之后 restartService 要真的起一次进程");
  const restartArg = ctl.starts[ctl.starts.length - 1];
  assert.equal(restartArg.repo, "beta", "重启的是 exited 状态里那个 repo id");
  assert.deepEqual(
    restartArg.command,
    serviceCommand({
      python: ["/auto/py"],
      kit: kitDir,
      repo: beta,
      assets: "/assets/root",
      transcripts: [logs],
    }),
  );

  // on：真订阅状态变化，只传 state 一个实参；退订后不再收到；别的事件名回空退订函数
  const api = makeApi();
  const got = [];
  const off = api.on("service-state", (...args) => got.push(args));
  assert.equal(typeof off, "function", "on 必须同步返回退订函数");
  ctl.emit({ kind: "running", repo: "beta", pid: 5, startedAt: "t" });
  assert.equal(got.length, 1);
  assert.equal(got[0].length, 1, "页面监听只收到 state 一个实参（info 不外传）");
  assert.deepEqual(got[0][0], { kind: "running", repo: "beta", pid: 5, startedAt: "t" });
  assert.ok(!JSON.stringify(got[0]).includes("byShell"), "byShell 不许外传");
  ctl.emit({ kind: "exited", repo: "beta", exitCode: 0, at: 1 });
  assert.equal(got.length, 2);
  off();
  assert.doesNotThrow(() => off(), "重复退订不抛错");
  ctl.emit({ kind: "idle" });
  assert.equal(got.length, 2, "退订后不再收到");
  let other = 0;
  const offOther = api.on("whatever", () => {
    other += 1;
  });
  assert.equal(typeof offOther, "function");
  assert.doesNotThrow(() => offOther());
  assert.equal(other, 0, "别的事件名不许调 listener");
  let fired = 0;
  const offBare = bare.on("service-state", () => {
    fired += 1;
  });
  assert.equal(typeof offBare, "function");
  assert.doesNotThrow(() => offBare());
  assert.equal(fired, 0, "没有控制器时 on 同步回空退订函数");
});

test("onAppearanceChange：改 theme 且写盘成功 → 恰好调一次、实参是只含新值的 {theme,density}", async () => {
  const seen = [];
  const h = makeHarness({ onAppearanceChange: (a) => seen.push(a) });
  const r = await h.api.saveSettings({ theme: "light" });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(seen, [{ theme: "light", density: "standard" }], "一次、两个字段都是新值");
});

test("onAppearanceChange：一次同时改 theme 与 density → 仍只调一次，两字段都是新值", async () => {
  const seen = [];
  const h = makeHarness({ onAppearanceChange: (a) => seen.push(a) });
  await h.api.saveSettings({ theme: "system", density: "compact" });
  assert.deepEqual(seen, [{ theme: "system", density: "compact" }]);
});

test("onAppearanceChange：写盘失败 → 不调、回 write-failed", async () => {
  const seen = [];
  const h = makeHarness({ failingSave: true, onAppearanceChange: (a) => seen.push(a) });
  assert.deepEqual(await h.api.saveSettings({ theme: "light" }), { ok: false, reason: "write-failed" });
  assert.deepEqual(seen, [], "写盘失败不广播");
});

test("onAppearanceChange：外观没变（同值重写、空补丁）→ 不调", async () => {
  const seen = [];
  const h = makeHarness({ onAppearanceChange: (a) => seen.push(a) });
  assert.equal((await h.api.saveSettings({ theme: "dark" })).ok, true, "缺省就是 dark，同值重写");
  assert.equal((await h.api.saveSettings({})).ok, true, "空补丁");
  assert.equal((await h.api.saveSettings({ theme: "dark", density: "standard" })).ok, true, "同值");
  assert.deepEqual(seen, []);
});

test("onAppearanceChange：只改仓库（pickTranscriptDir 加目录）→ 不调", async () => {
  const seen = [];
  const h = makeHarness({ onAppearanceChange: (a) => seen.push(a) });
  h.chooser.dir = h.plainDir("logs");
  const r = await h.api.pickTranscriptDir();
  assert.equal(r.ok, true, "夹具本身要成功：" + JSON.stringify(r));
  assert.deepEqual(seen, []);
});

test("onAppearanceChange：回调抛错 → 不影响 saveSettings 的返回值", async () => {
  const h = makeHarness({ onAppearanceChange: () => {
    throw new Error("boom");
  } });
  const r = await h.api.saveSettings({ theme: "light" });
  assert.equal(r.ok, true);
  assert.equal(r.value.settings.theme, "light");
});

test("initialSettings：当内存初值（深拷贝）、一次 store.load() 都不调", async () => {
  const initial = {
    version: 1, repos: [], currentRepo: null, transcriptDirs: [],
    theme: "light", density: "compact", pythonPath: null, kitPath: null,
  };
  let loads = 0;
  const api = createShellApi({
    store: {
      load: () => {
        loads += 1;
        return { settings: Object.assign({}, DEFAULT_SETTINGS), badCopy: null };
      },
      save: () => {},
    },
    initialSettings: initial,
    probe: {
      probePython: async () => null,
      probeKit: async () => null,
      detectPython: async () => ({ status: "missing", path: "", version: "" }),
      detectKit: async () => null,
    },
  });
  const r = await api.getState();
  assert.equal(r.value.settings.theme, "light", "用注入值当内存初值");
  assert.equal(r.value.settings.density, "compact");
  initial.theme = "dark"; // 深拷贝：api 的内存与注入的对象不共用同一份
  const again = await api.getState();
  assert.equal(again.value.settings.theme, "light", "改注入的对象不许影响 api 的内存");
  assert.equal(loads, 0, "给了 initialSettings 就不该 store.load()");
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

test("onRepoOps：建好时同步调一次、恰好一次，交出 {listRepos, selectRepo} 两个函数（D03）", () => {
  const h = makeHarness();
  assert.equal(h.ops.calls, 1, "createShellApi 建好时同步调一次");
  assert.deepEqual(Object.keys(h.ops.captured).sort(), ["listRepos", "selectRepo"]);
  for (const name of Object.keys(h.ops.captured)) {
    assert.equal(typeof h.ops.captured[name], "function", name + " 必须是函数");
  }
});

function twoRepos(h) {
  h.writeSettings((s) => {
    s.repos = [
      { id: "a", name: "alpha", path: "/x/a", lastOpened: null },
      { id: "b", name: "beta", path: "/x/b", lastOpened: null },
    ];
    s.currentRepo = "a";
  });
}

test("listRepos：只回 {id,name,current}、不带 path，只有 runningId 那一条 current 为 true", async () => {
  const h = makeHarness();
  twoRepos(h);
  const repos = await h.ops.captured.listRepos("a");
  assert.deepEqual(repos, [
    { id: "a", name: "alpha", current: true },
    { id: "b", name: "beta", current: false },
  ]);
  assert.ok(!repos.some((entry) => "path" in entry), "不许带 path");
  const flipped = await h.ops.captured.listRepos("b");
  assert.equal(flipped.find((e) => e.id === "b").current, true);
  assert.equal(flipped.find((e) => e.id === "a").current, false);
});

test("listRepos：runningId 不是字符串 → 没有哪一条 current 为 true", async () => {
  const h = makeHarness();
  twoRepos(h);
  for (const weird of [null, undefined, 123, {}, ""]) {
    const repos = await h.ops.captured.listRepos(weird);
    assert.ok(repos.every((entry) => entry.current === false), "runningId=" + JSON.stringify(weird));
  }
});

test("selectRepo 依次拒：bad-args → unknown-repo → current-repo，都不写盘", async () => {
  const h = makeHarness();
  twoRepos(h);
  const before = h.bytes();
  assert.deepEqual(await h.ops.captured.selectRepo(undefined, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await h.ops.captured.selectRepo("", "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await h.ops.captured.selectRepo(123, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await h.ops.captured.selectRepo({}, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await h.ops.captured.selectRepo("ghost", "a", 1), { ok: false, reason: "unknown-repo" });
  assert.deepEqual(await h.ops.captured.selectRepo("a", "a", 1), { ok: false, reason: "current-repo" });
  assert.deepEqual(h.bytes(), before, "拒绝都不写盘");
});

test("selectRepo 成功：存盘 currentRepo 与 lastOpened、回 {ok:true}、内存换成新的、缓存已清", async () => {
  const h = makeHarness();
  twoRepos(h);
  await h.api.getState();
  const detectsBefore = h.probeState.autoPythonCalls.length;
  const at = 1765830000456;
  assert.deepEqual(await h.ops.captured.selectRepo("b", "a", at), { ok: true });
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.currentRepo, "b", "存盘写的是新 currentRepo");
  assert.equal(onDisk.repos.find((e) => e.id === "b").lastOpened, new Date(at).toISOString());
  const after = await h.api.getState();
  assert.equal(after.value.settings.currentRepo, "b", "内存设置也换成新的");
  assert.equal(h.probeState.autoPythonCalls.length, detectsBefore + 1, "成功之后下次 getState 重新探测（dropCache）");
});

test("selectRepo 写盘失败：回 write-failed，内存里的 currentRepo 仍是旧值", async () => {
  const h = makeHarness({ failingSave: true });
  twoRepos(h);
  assert.deepEqual(await h.ops.captured.selectRepo("b", "a", 1765830000456), { ok: false, reason: "write-failed" });
  const after = await h.api.getState();
  assert.equal(after.value.settings.currentRepo, "a", "写盘失败后内存还是旧值");
});

test("selectRepo 的 at 不是有限数字 → 用 Date.now() 兜底", async () => {
  const h = makeHarness();
  twoRepos(h);
  const realNow = Date.now;
  const fixed = 1765840000789;
  Date.now = () => fixed;
  try {
    for (const weird of [null, "not-a-number", NaN, Infinity]) {
      const r = await h.ops.captured.selectRepo("b", "a", weird);
      assert.equal(r.ok, true, "at=" + JSON.stringify(weird));
    }
    const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
    assert.equal(onDisk.repos.find((e) => e.id === "b").lastOpened, new Date(fixed).toISOString());
  } finally {
    Date.now = realNow;
  }
});
