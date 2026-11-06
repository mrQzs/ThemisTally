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

// 五个宿主函数的编排：系统能力与本机服务全部由注入物承担，控制令牌只在这个闭包里
function createHost(options) {
  const {
    origin,
    control,
    repo,
    loadMain,
    createSecretWindow,
    confirmExternal,
    openExternal,
    showItem,
    showNotification,
    now,
    controlTimeoutMs,
  } = options;

  const limiter = createRateLimiter({ now });
  // 凭据窗口的占位：最多一个。在第一个 await 之前同步记下，一上来并发也开不出第二个窗口
  let current = null;

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

  return {
    reauth,
    openSecretWindow,
    openExternal: openExternalUrl,
    reveal,
    notify,
  };
}

module.exports = { createHost };
