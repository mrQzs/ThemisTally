"use strict";

const path = require("node:path");
const { applyPatch, addRepo, addTranscriptDir } = require("./settings.js");
const { checkRepo, probePython, probeKit, detectPython, detectKit } = require("./detect.js");
const { isExternalUrl } = require("./hostcheck.js");

const HOMEPAGE = "https://github.com/mrQzs/ThemisTally";
const KIT_SCRIPT = path.join("scripts", "pi_dispatch.py");

function copyEntry(entry) {
  return Object.assign({}, entry);
}

// 写盘前的副本：写失败了内存里还是补丁前的值
function cloneSettings(source) {
  return {
    version: source.version,
    repos: source.repos.map(copyEntry),
    currentRepo: source.currentRepo,
    transcriptDirs: source.transcriptDirs.map(copyEntry),
    theme: source.theme,
    density: source.density,
    pythonPath: source.pythonPath,
    kitPath: source.kitPath,
  };
}

function createShellApi(options) {
  const opts = options || {};
  const store = opts.store;
  const chooseDirectory = typeof opts.chooseDirectory === "function" ? opts.chooseDirectory : async () => null;
  const chooseFile = typeof opts.chooseFile === "function" ? opts.chooseFile : async () => null;
  const confirmExternal =
    typeof opts.confirmExternal === "function" ? opts.confirmExternal : async () => false;
  const openExternalUrl = typeof opts.openExternal === "function" ? opts.openExternal : async () => {};
  const appVersion = typeof opts.appVersion === "string" ? opts.appVersion : "";
  const homepage = typeof opts.homepage === "string" ? opts.homepage : HOMEPAGE;
  const probe = Object.assign({}, { probePython, probeKit, detectPython, detectKit }, opts.probe || {});

  // 内存设置第一次用到时从存盘读入；写盘成功后才更新它
  let settings = null;
  // 检测结果缓存：getState 不重复起子进程，选择与保存之后清掉
  let cache = null;

  function current() {
    if (settings === null) settings = store.load().settings;
    return settings;
  }

  function dropCache() {
    cache = null;
  }

  // pythonPath 与 kitPath 只留在设置文件里，不出现在 state 里
  function settingsView(source) {
    return {
      repos: source.repos.map(copyEntry),
      currentRepo: source.currentRepo,
      transcriptDirs: source.transcriptDirs.map(copyEntry),
      theme: source.theme,
      density: source.density,
    };
  }

  function currentEntry(source) {
    if (source.currentRepo === null || source.currentRepo === undefined) return null;
    return source.repos.find((entry) => entry.id === source.currentRepo) || null;
  }

  function repoCheck(source) {
    const entry = currentEntry(source);
    if (entry === null) return null;
    return checkRepo(entry.path);
  }

  async function pythonInfo(source) {
    if (cache !== null && cache.python !== undefined) return cache.python;
    let info;
    const custom = typeof source.pythonPath === "string" ? source.pythonPath : "";
    if (custom.length > 0) {
      const result = await probe.probePython([custom]);
      info =
        result && result.ok
          ? { status: "ok", source: "custom", path: result.path, version: result.version }
          : { status: "missing", source: "custom", path: "", version: "" };
    } else {
      const result = await probe.detectPython();
      info = {
        status: result && result.status === "ok" ? "ok" : "missing",
        source: "auto",
        path: (result && result.path) || "",
        version: (result && result.version) || "",
      };
    }
    cache = cache || {};
    cache.python = info;
    return info;
  }

  async function kitInfo(source, python) {
    if (cache !== null && cache.kit !== undefined) return cache.kit;
    let info;
    const external = typeof source.kitPath === "string" ? source.kitPath : "";
    const entry = currentEntry(source);
    const kitDir = external.length > 0 ? external : entry === null ? "" : entry.path;
    const sourceName = external.length > 0 ? "external" : "repo";
    if (kitDir.length === 0 || python.status !== "ok") {
      info = { status: "missing", source: sourceName, path: "", version: "" };
    } else {
      const result = await probe.probeKit(python.path, kitDir);
      info =
        result && result.ok
          ? { status: "ok", source: sourceName, path: path.join(kitDir, KIT_SCRIPT), version: result.version }
          : { status: "missing", source: sourceName, path: "", version: "" };
    }
    cache = cache || {};
    cache.kit = info;
    return info;
  }

  async function stateView() {
    const source = current();
    const python = await pythonInfo(source);
    const kit = await kitInfo(source, python);
    return {
      app: { version: appVersion, homepage },
      settings: settingsView(source),
      currentRepoCheck: repoCheck(source),
      python,
      kit,
      service: { kind: "idle" },
    };
  }

  // 写盘失败：内存状态保持原样（调用方拿到 write-failed 自己决定怎么办）
  async function persist(next) {
    try {
      store.save(next);
    } catch {
      return { ok: false, reason: "write-failed" };
    }
    settings = next;
    return { ok: true };
  }

  async function getState() {
    return { ok: true, value: await stateView() };
  }

  function cancelled() {
    return { ok: true, value: { kind: "cancelled" } };
  }

  function rejected(problem, chosen) {
    return { ok: true, value: { kind: "rejected", problem, path: chosen } };
  }

  async function saved(chosen, id) {
    const value = id === undefined ? { kind: "saved", path: chosen } : { kind: "saved", path: chosen, id };
    value.state = await stateView();
    return { ok: true, value };
  }

  async function pickRepo() {
    const chosen = await chooseDirectory({ title: "选择仓库" });
    if (chosen === null || chosen === undefined) return cancelled();
    const check = checkRepo(chosen);
    if (check !== "ok") return rejected(check, chosen);
    const added = addRepo(current(), chosen);
    const written = await persist(added.settings);
    if (!written.ok) return written;
    return saved(chosen, added.id);
  }

  async function pickPython() {
    dropCache();
    const chosen = await chooseFile({ title: "选择 Python" });
    if (chosen === null || chosen === undefined) return cancelled();
    const result = await probe.probePython([chosen]);
    if (!result || !result.ok) return rejected("python-unusable", chosen);
    const next = cloneSettings(current());
    next.pythonPath = chosen;
    const written = await persist(next);
    if (!written.ok) return written;
    return saved(chosen);
  }

  async function pickKit() {
    dropCache();
    const chosen = await chooseDirectory({ title: "选择 ThemisTally 目录" });
    if (chosen === null || chosen === undefined) return cancelled();
    const python = await pythonInfo(current());
    if (python.status !== "ok") return rejected("python-unusable", chosen);
    const result = await probe.probeKit(python.path, chosen);
    if (!result || !result.ok) return rejected("kit-unusable", chosen);
    const next = cloneSettings(current());
    next.kitPath = chosen;
    const written = await persist(next);
    if (!written.ok) return written;
    return saved(chosen);
  }

  async function pickTranscriptDir() {
    const chosen = await chooseDirectory({ title: "选择会话记录目录" });
    if (chosen === null || chosen === undefined) return cancelled();
    const added = addTranscriptDir(current(), chosen);
    const written = await persist(added.settings);
    if (!written.ok) return written;
    return saved(chosen, added.id);
  }

  async function saveSettings(patch) {
    const applied = applyPatch(current(), patch);
    if (!applied.ok) return { ok: false, reason: applied.reason };
    dropCache();
    const written = await persist(applied.settings);
    if (!written.ok) return written;
    return { ok: true, value: await stateView() };
  }

  async function openExternal(url) {
    if (!isExternalUrl(url)) return { ok: false, reason: "bad-url" };
    let confirmed;
    try {
      confirmed = await confirmExternal(url);
    } catch {
      return { ok: false, reason: "internal" };
    }
    if (!confirmed) return { ok: false, reason: "cancelled" };
    try {
      await openExternalUrl(url);
    } catch {
      return { ok: false, reason: "open-failed" };
    }
    return { ok: true, value: null };
  }

  // 三个占位：服务与事件订阅由后面的片接真行为
  async function startService() {
    return { ok: false, reason: "not-implemented" };
  }

  async function restartService() {
    return { ok: false, reason: "not-implemented" };
  }

  // 页面挂载时就调它：同步回退订函数，不抛错、不调 listener
  function on() {
    return () => {};
  }

  return {
    getState,
    pickRepo,
    pickPython,
    pickKit,
    pickTranscriptDir,
    saveSettings,
    startService,
    restartService,
    openExternal,
    on,
  };
}

module.exports = { createShellApi };
