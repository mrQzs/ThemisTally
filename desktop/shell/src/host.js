"use strict";

const { postControl } = require("./control.js");
const {
  isSecretPageUrl,
  isJobId,
  isExternalUrl,
  resolveReveal,
  createRateLimiter,
  NOTIFY_TEXT,
} = require("./hostcheck.js");
const { SHELL_SETTINGS_URL } = require("./shellprotocol.js");
const { THEME_VALUES } = require("./settings.js");

// 控制接口的两条路径（照 routes.ts 的 CONTROL_PATH 与 jobroutes.ts 的 control.jobs.cancel）
const BOOTSTRAP_PATH = "/control/bootstrap";
const CANCEL_PATH = "/control/jobs/";

// 信封只在这里解一次：状态码 200、ok 为 true、data.bootstrap 是非空字符串且在服务 origin 下。
// 解不出来回 null——调用方按 bad-response 处理，不把正文的任何片段带出去
function readBootstrap(response, origin) {
  if (!response || response.status !== 200) return null;
  let parsed;
  try {
    parsed = JSON.parse(response.body);
  } catch {
    return null;
  }
  if (!parsed || parsed.ok !== true) return null;
  const bootstrap = parsed.data ? parsed.data.bootstrap : undefined;
  if (typeof bootstrap !== "string" || bootstrap.length === 0) return null;
  try {
    if (new URL(bootstrap).origin !== origin) return null;
  } catch {
    return null;
  }
  return bootstrap;
}

// 十个宿主函数的编排：系统能力与本机服务全部由注入物承担，控制令牌只在这个闭包里
function createHost(options) {
  const {
    origin,
    control,
    repo,
    loadMain,
    createSecretWindow,
    createSettingsWindow,
    confirmExternal,
    openExternal,
    showItem,
    showNotification,
    now,
    controlTimeoutMs,
    saveTheme: saveThemeImpl,
    listRepos: listReposImpl,
    switchRepo: switchRepoImpl,
    addRepo: addRepoImpl,
  } = options;

  const limiter = createRateLimiter({ now });
  // 凭据窗口的占位：最多一个。在第一个 await 之前同步记下，一上来并发也开不出第二个窗口
  let current = null;
  // 设置窗口的占位：最多一个。同样在第一个 await 之前同步记下
  let settingsWindow = null;

  function cancelJob(jobId) {
    // 404（没有这个作业）、409（已经结束）都是常态，结果与错误一律吞掉
    postControl({
      origin,
      control,
      path: `${CANCEL_PATH}${jobId}/cancel`,
      timeoutMs: controlTimeoutMs,
    }).then(
      () => {},
      () => {},
    );
  }

  async function reauth() {
    // 占名额发生在发请求之前，失败的也占名额
    if (!limiter.take()) return { ok: false, reason: "rate-limited" };
    let response;
    try {
      response = await postControl({
        origin,
        control,
        path: BOOTSTRAP_PATH,
        timeoutMs: controlTimeoutMs,
      });
    } catch {
      return { ok: false, reason: "request-failed" };
    }
    const bootstrap = readBootstrap(response, origin);
    if (bootstrap === null) return { ok: false, reason: "bad-response" };
    try {
      await loadMain(bootstrap);
    } catch {
      return { ok: false, reason: "load-failed" };
    }
    return { ok: true };
  }

  async function openSecretWindow(url, jobId) {
    if (!isSecretPageUrl(url) || !isJobId(jobId)) {
      return { ok: false, reason: "bad-args" };
    }
    if (current !== null) {
      current.win.focus();
      if (current.jobId === jobId) return { ok: true };
      return { ok: false, reason: "busy" };
    }
    const win = createSecretWindow({ origin: new URL(url).origin });
    current = { win, jobId };
    // once 不用 on：再触发一次不重发取消
    win.once("closed", () => {
      current = null;
      cancelJob(jobId);
    });
    try {
      await win.loadURL(url);
    } catch {
      if (!win.isDestroyed()) win.close();
      return { ok: false, reason: "load-failed" };
    }
    return { ok: true };
  }

  async function openExternalUrl(url) {
    if (!isExternalUrl(url)) return { ok: false, reason: "bad-url" };
    let confirmed;
    try {
      confirmed = await confirmExternal(url);
    } catch {
      return { ok: false, reason: "internal" };
    }
    if (!confirmed) return { ok: false, reason: "cancelled" };
    try {
      await openExternal(url);
    } catch {
      return { ok: false, reason: "open-failed" };
    }
    return { ok: true };
  }

  async function reveal(relPath) {
    const full = resolveReveal({ repo, relPath });
    if (full === null) return { ok: false, reason: "bad-path" };
    showItem(full);
    return { ok: true };
  }

  async function notify(kind) {
    const text = NOTIFY_TEXT.get(kind);
    if (text === undefined) return { ok: false, reason: "bad-kind" };
    showNotification({ title: text.title, body: text.body });
    return { ok: true };
  }

  async function openSettings() {
    // 没有注入建窗函数（带参数起服务的那条分支：没有外壳页、没有外壳 IPC）→ 假装能开
    if (typeof createSettingsWindow !== "function") return { ok: false, reason: "unavailable" };
    if (settingsWindow !== null) {
      // 已经开着：最小化先还原再聚焦，不另开第二个窗口
      if (settingsWindow.isMinimized()) settingsWindow.restore();
      settingsWindow.focus();
      return { ok: true };
    }
    const win = createSettingsWindow();
    // 占位在第一个 await 之前同步记下：并发两次调用只建一个窗口
    settingsWindow = win;
    // once 不用 on：只清自己的那一个，迟到的旧窗口 closed 不误伤新窗口
    win.once("closed", () => {
      if (settingsWindow === win) settingsWindow = null;
    });
    try {
      await win.loadURL(SHELL_SETTINGS_URL);
    } catch {
      if (!win.isDestroyed()) win.close();
      return { ok: false, reason: "load-failed" };
    }
    return { ok: true };
  }

  // 保存主题：顺序固定为 bad-args → unavailable → 转交 → 注入抛错回 internal。
  // 注入实现是 api.saveSettings({ theme: pref }) 转成的信封，转交时只传 pref 这一个实参。
  async function saveTheme(pref) {
    if (!THEME_VALUES.includes(pref)) return { ok: false, reason: "bad-args" };
    if (typeof saveThemeImpl !== "function") return { ok: false, reason: "unavailable" };
    try {
      return await saveThemeImpl(pref);
    } catch {
      return { ok: false, reason: "internal" };
    }
  }

  // 仓库列表：注入项不是函数 → unavailable；否则调注入项，只取 {id,name,current} 三键（带了 path 也剥掉）。
  // 注入项回非 ok 信封（main.js 里 repoOps 为 null 时）原样回，不另外包成 internal
  async function listRepos() {
    if (typeof listReposImpl !== "function") return { ok: false, reason: "unavailable" };
    const result = await listReposImpl();
    if (result.ok !== true) return result;
    return { ok: true, repos: result.repos.map((entry) => ({ id: entry.id, name: entry.name, current: entry.current })) };
  }

  // 切换仓库：id 不是非空字符串 → bad-args（不进注入项）；注入项不是函数 → unavailable；
  // 否则原样回注入项的结果（{ok:true} 或 {ok:false, reason}）。注入项抛错不在这里包
  async function switchRepo(id) {
    if (typeof id !== "string" || id.length === 0) return { ok: false, reason: "bad-args" };
    if (typeof switchRepoImpl !== "function") return { ok: false, reason: "unavailable" };
    return switchRepoImpl(id);
  }

  // 添加仓库：注入项不是函数 → unavailable；否则把外壳信封的四种内层形状映射成宿主信封，
  // 不认识的回 internal。注入项抛错不在这里包（src/ipc.js 的外层会回 internal）
  async function addRepo() {
    if (typeof addRepoImpl !== "function") return { ok: false, reason: "unavailable" };
    const result = await addRepoImpl();
    if (result.kind === "cancelled") return { ok: false, reason: "cancelled" };
    if (result.kind === "rejected") return { ok: false, reason: result.problem };
    if (result.ok === false && result.reason === "write-failed") return result;
    if (result.kind === "saved") return { ok: true, id: result.id };
    return { ok: false, reason: "internal" };
  }

  return {
    reauth,
    openSecretWindow,
    openExternal: openExternalUrl,
    reveal,
    notify,
    openSettings,
    saveTheme,
    listRepos,
    switchRepo,
    addRepo,
  };
}

module.exports = { createHost };
