"use strict";

const path = require("node:path");
const { applyPatch, addRepo, addTranscriptDir, appearanceOf, selectRepo: selectRepoSettings } = require("./settings.js");
const { checkRepo, probePython, probeKit, detectPython, detectKit } = require("./detect.js");
const { isExternalUrl } = require("./hostcheck.js");
// 起服务的命令形状只此一处：外壳页与带参数那条路用同一个 serviceCommand
const { serviceCommand } = require("./service.js");

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
  // 服务控制器与外壳页产物根：都没有注入时 startService 回 no-service（探针不注入新项也不能红）
  const service = opts.service || null;
  const assets = typeof opts.assets === "string" ? opts.assets : "";
  // 外观变化回调：saveSettings 写盘成功且 theme/density 变了才调一次；不注入就不调
  const onAppearanceChange = typeof opts.onAppearanceChange === "function" ? opts.onAppearanceChange : null;
  // 仓库操作回调：建好时同步调一次，把 listRepos/selectRepo 两个内部函数交出去（不进返回对象、不进外壳 IPC）
  const onRepoOps = typeof opts.onRepoOps === "function" ? opts.onRepoOps : null;

  // 内存设置：给了 initialSettings 就用它当初值（深拷贝，一次都不再 store.load 起步），
  // 否则第一次用到时从存盘读入；写盘成功后才更新它
  let settings = opts.initialSettings !== undefined ? cloneSettings(opts.initialSettings) : null;
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

  // 控制器的当前状态；没有注入控制器时仍是 idle
  function serviceState() {
    if (service === null || typeof service.state !== "function") return { kind: "idle" };
    const state = service.state();
    return state === null || state === undefined ? { kind: "idle" } : state;
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
      service: serviceState(),
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
    const source = current();
    const applied = applyPatch(source, patch);
    if (!applied.ok) return { ok: false, reason: applied.reason };
    dropCache();
    const written = await persist(applied.settings);
    if (!written.ok) return written;
    // 写盘成功且 theme/density 与写之前不同 → 回调一次外观变化（两个字段都是新值）；
    // 外观没变、写盘失败、只改仓库等情况不调；回调抛错不影响返回值
    if (
      onAppearanceChange !== null &&
      (applied.settings.theme !== source.theme || applied.settings.density !== source.density)
    ) {
      try {
        onAppearanceChange(appearanceOf(applied.settings));
      } catch {
        // 广播回调自己抛错：吞掉，saveSettings 照常回 {ok:true,value}
      }
    }
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

  // 起服务：按仓库 id 查设置 → Python → kit（按目标仓库算）→ 拼命令 → 交控制器。
  // 起进程之前的失败只回 reason，不起进程、不改状态；起进程之后的失败由控制器先发 exited 再回信封。
  async function startService(repoId) {
    const source = current();
    const entry = source.repos.find((item) => item.id === repoId) || null;
    if (entry === null) return { ok: false, reason: "unknown-repo" };
    const state = serviceState();
    if (state.kind === "starting" || state.kind === "running") {
      // 同一个仓库正在起或正在跑 → 幂等；别的仓库正忙 → busy。两者都不再起进程
      if (state.repo === entry.id) return { ok: true, value: null };
      return { ok: false, reason: "busy" };
    }
    if (service === null || assets.length === 0) return { ok: false, reason: "no-service" };
    const python = await pythonInfo(source);
    if (python.status !== "ok") return { ok: false, reason: "python-missing" };
    // kit 按目标仓库算：设置里的 kitPath 优先，否则用目标仓库的 path——不看当前仓库的缓存结果
    const external = typeof source.kitPath === "string" ? source.kitPath : "";
    const kitDir = external.length > 0 ? external : entry.path;
    const kit = await probe.probeKit(python.path, kitDir);
    if (!kit || !kit.ok) return { ok: false, reason: "kit-missing" };
    const command = serviceCommand({
      python: [python.path],
      kit: kitDir,
      repo: entry.path,
      assets,
      transcripts: source.transcriptDirs.map((item) => item.path),
    });
    return service.start({ repo: entry.id, command, env: process.env });
  }

  // 重启：按当前状态决定，不新增控制器方法（假控制器只有 start/stop/abort/state/subscribe）
  async function restartService() {
    const state = serviceState();
    // 服务已经退了：按 exited 里那个 repo 重走 startService，命令按当前设置重新拼
    if (state.kind === "exited") return startService(state.repo);
    // 正在起或正在跑：幂等，什么也不做
    if (state.kind === "starting" || state.kind === "running") return { ok: true, value: null };
    // idle（含没有注入控制器）：没有可重启的对象
    return { ok: false, reason: "no-previous" };
  }

  // 页面挂载时就调它：同步回退订函数。只认 service-state，且只把 state 交给 listener
  //（控制器订阅回调里的 info 是主进程内部的事，不外传）
  function on(event, listener) {
    if (event !== "service-state" || typeof listener !== "function") return () => {};
    if (service === null || typeof service.subscribe !== "function") return () => {};
    return service.subscribe((state) => {
      listener(state);
    });
  }

  // 仓库列表（不带路径）：current 为 id === runningId；runningId 不是字符串时没有哪一条 current 为 true
  function listRepos(runningId) {
    const source = current();
    const running = typeof runningId === "string" ? runningId : null;
    return source.repos.map((entry) => ({ id: entry.id, name: entry.name, current: entry.id === running }));
  }

  // 切换当前仓库：依次 bad-args → unknown-repo → current-repo → 纯函数 → 清缓存 → 存盘。
  // 写盘失败内存保持原样（persist 只在成功时更新内存设置）；at 不是有限数字用 Date.now() 兜底
  async function selectRepo(id, runningId, at) {
    if (typeof id !== "string" || id.length === 0) return { ok: false, reason: "bad-args" };
    const source = current();
    if (!source.repos.some((entry) => entry.id === id)) return { ok: false, reason: "unknown-repo" };
    if (id === runningId) return { ok: false, reason: "current-repo" };
    const at2 = Number.isFinite(at) ? at : Date.now();
    const applied = selectRepoSettings(source, id, at2);
    if (!applied.ok) return { ok: false, reason: "unknown-repo" };
    dropCache();
    const written = await persist(applied.settings);
    if (!written.ok) return { ok: false, reason: "write-failed" };
    return { ok: true };
  }

  // 建好时同步交出两个内部函数（调用方据此接到 main.js 的切换编排）；不注入就不调
  if (onRepoOps !== null) onRepoOps({ listRepos, selectRepo });

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
