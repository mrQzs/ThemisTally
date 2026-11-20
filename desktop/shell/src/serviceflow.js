"use strict";

const { spawn } = require("node:child_process");
const { startService, stopService } = require("./service.js");

const HANDSHAKE_TIMEOUT_MS = 30000;
const STOP_GRACE_MS = 10000;
const ABORT_GRACE_MS = 3000;
// 没有数字码（被信号结束、spawn 失败、外壳自己杀的进程）统一记 -1
const NO_CODE = -1;

// 与 src/service.js 的 defaultSpawn 同形：service.js 以 (command, [], options) 调它
function defaultSpawn(command, args, options) {
  return spawn(command[0], command.slice(1), options);
}

function codeOf(code) {
  return typeof code === "number" ? code : NO_CODE;
}

function hasExited(child) {
  return typeof child.exitCode === "number" || Boolean(child.signalCode);
}

// 等子进程的 exit 事件，最多 timeoutMs；超时就返回（调用方决定怎么收尾）
function waitExit(child, timeoutMs) {
  return new Promise((resolve) => {
    if (hasExited(child)) {
      resolve();
      return;
    }
    const timer = setTimeout(resolve, timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

// 服务状态机：idle → starting → running → exited（只前进不后退）。
// 状态按 run 记：每次 start 开一个新 run，旧 run 的子进程监听、stop/abort 的补发都只在它所属的
// run 仍是当前 run 时才改状态——否则 exited 之后再 start 会被旧回调卡住。
// 子进程借 src/service.js 的 spawn 选项拿到：把注入的 spawn 包一层，在 spawn 的瞬间挂 exit 与 error
// 监听——src/service.js 的签名与行为因此一字不变。
function createServiceFlow(options) {
  const opts = options || {};
  const now = typeof opts.now === "function" ? opts.now : Date.now;
  const timeoutMs = typeof opts.timeoutMs === "number" ? opts.timeoutMs : HANDSHAKE_TIMEOUT_MS;
  const spawnFn = typeof opts.spawn === "function" ? opts.spawn : defaultSpawn;
  const injectedEnv = opts.env === undefined || opts.env === null ? process.env : opts.env;
  const onRunning = typeof opts.onRunning === "function" ? opts.onRunning : null;

  const listeners = new Set();
  let current = { kind: "idle" };
  // run 计数：每次 start 自增，回调靠它认出自己所属的 run 还是不是当前 run
  let run = 0;
  let repo = "";
  let child = null;
  // 「是不是外壳自己结束的」只留在主进程：外壳停服务（stop）或中止（abort）时为真。按 run 算——
  // 新 run 一律重置，上一 run 被 stop 过不继承到下一 run
  let stopping = false;
  let aborting = false;

  // 状态变化通知全部订阅者；info 只带给主进程的订阅者，不进状态、不进事件负载。
  // 只前进不后退：同一个 run 里已经是 exited 就不再变（重复的 exited 不覆盖已有的）。
  // 例外有两个：新 run 的 starting（exited 之后要能再 start），以及 reset（exited → idle，见下面 reset）
  function moveTo(next, newRun) {
    if (current.kind === "exited" && newRun !== true) return;
    // 只有「进过 running 之后的退出」才带 afterRunning: true：服务自己退出、跑起来之后外壳自己 stop、
    // onRunning 失败后的收服务。判据是赋值前那一刻的 current.kind——启动阶段的失败此刻还是 starting，
    // 所以不带这个键（也不是 false）；新 run 先 starting，键天然按 run 算。
    current = next.kind === "exited" && current.kind === "running" ? { ...next, afterRunning: true } : next;
    const info = { byShell: next.kind === "exited" ? stopping || aborting : false };
    for (const listener of [...listeners]) listener(current, info);
  }

  async function start(arg) {
    const o = arg || {};
    const command = o.command;
    // 只有 idle 与 exited 能开新 run：starting/running 一律 busy，不起进程
    if (current.kind !== "idle" && current.kind !== "exited") return { ok: false, reason: "busy" };
    if (!Array.isArray(command) || command.length === 0) return { ok: false, reason: "start-failed" };
    const env = o.env === undefined || o.env === null ? injectedEnv : o.env;

    // 新 run：stopping/aborting/child 一律重置，repo 记本次 start 的仓库
    run += 1;
    const thisRun = run;
    stopping = false;
    aborting = false;
    child = null;
    repo = typeof o.repo === "string" ? o.repo : "";

    let phase = "starting";
    let exitCode = null;
    let spawnFailed = false;

    const wrapped = (cmd, args, spawnOptions) => {
      const spawned = spawnFn(cmd, args, spawnOptions);
      child = spawned;
      spawned.on("exit", (code) => {
        exitCode = typeof code === "number" ? code : null;
        // 旧 run 的子进程什么时候退不定：不是当前 run 就整个丢掉，不改状态、不发事件
        if (thisRun !== run) return;
        // 握手成功后服务自己退出（或被外壳停掉）：running → exited
        if (phase === "running") moveTo({ kind: "exited", repo, exitCode: codeOf(exitCode), at: now() });
      });
      spawned.on("error", () => {
        spawnFailed = true;
      });
      return spawned;
    };

    moveTo({ kind: "starting", repo }, true);

    let started;
    try {
      started = await startService({ command, spawn: wrapped, env, timeoutMs });
    } catch {
      // 起进程之后的失败：先发 exited 再回信封（起进程之前的失败根本不走到这里）
      moveTo({ kind: "exited", repo, exitCode: codeOf(exitCode), at: now() });
      return { ok: false, reason: spawnFailed ? "start-failed" : "handshake-failed" };
    }

    const handshake = started.handshake.value;
    phase = "running";
    moveTo({
      kind: "running",
      repo,
      pid: handshake.pid,
      startedAt: new Date(now()).toISOString(),
    });

    if (onRunning !== null) {
      try {
        // 控制令牌只经这一个实参出去：进 createHost 的闭包，不进状态、不进事件负载、不进信封
        await onRunning({ origin: handshake.origin, control: handshake.control, repo, bootstrap: handshake.bootstrap });
      } catch {
        await stop();
        return { ok: false, reason: "start-failed" };
      }
    }
    return { ok: true, value: null };
  }

  // 干净关停：写 stdin EOF、宽限 10 秒、超时 kill（语义照 src/service.js 的 stopService）
  async function stop() {
    if (child === null) return { exited: false, code: null, signal: null };
    stopping = true;
    const target = child;
    const result = await stopService(target, { graceMs: STOP_GRACE_MS });
    // exit 监听通常已经把状态推到 exited；stopService 经 close 收尾时这里补一次。
    // 只作用于当前 run 的 child：期间换了 run 就不改状态
    if (target === child && (current.kind === "running" || current.kind === "starting")) {
      moveTo({ kind: "exited", repo, exitCode: codeOf(result.code), at: now() });
    }
    return {
      exited: result.exited === true,
      code: typeof result.code === "number" ? result.code : null,
      signal: result.signal === undefined ? null : result.signal,
    };
  }

  // starting 期间中止：立刻 kill（不写 stdin），等它的 exit，最多 3 秒
  async function abort() {
    if (child === null) return;
    aborting = true;
    const target = child;
    try {
      target.kill();
    } catch {
      // 已经没了
    }
    await waitExit(target, ABORT_GRACE_MS);
    if (!hasExited(target)) {
      // 3 秒还不退：再杀一次，不许把子进程留成活着的孤儿
      try {
        target.kill("SIGKILL");
      } catch {
        // 已经没了
      }
      if (target === child && (current.kind === "running" || current.kind === "starting")) {
        moveTo({ kind: "exited", repo, exitCode: NO_CODE, at: now() });
      }
    }
  }

  function state() {
    return current;
  }

  function subscribe(listener) {
    if (typeof listener !== "function") return () => {};
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }

  // reset：第二个例外（exited → idle）。只在 current 是 exited 时置回 idle 并以 {byShell:false} 通知，
  // 不经 moveTo；idle/starting/running 下什么都不做、不发通知。run 计数、child、stopping、aborting
  // 都不动——下一次 start 自己会重置。切换仓库后首次启动页靠它回到 idle 才能自动起新仓库的服务
  function reset() {
    if (current.kind !== "exited") return;
    current = { kind: "idle" };
    for (const listener of [...listeners]) listener(current, { byShell: false });
  }

  return { start, stop, abort, state, subscribe, reset };
}

module.exports = { createServiceFlow };
