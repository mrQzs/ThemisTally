"use strict";

const { parseShellArgs } = require("./args.js");
const { findPython } = require("./python.js");
const { serviceCommand, startService, stopService } = require("./service.js");

function writeError(io, message) {
  io.stderr.write(`ERROR: ${message}\n`);
}

function readExit(child) {
  if (typeof child.exitCode === "number") {
    return { code: child.exitCode, signal: child.signalCode || null };
  }
  if (child.signalCode) {
    return { code: null, signal: child.signalCode };
  }
  return null;
}

// 开窗口之前就挂服务退出监听，并立刻查一次：握手成功后、开窗口完成前退出的服务不能漏掉——
// 漏掉的后果是既不报「服务意外退出」、也不关窗口、更不以 1 退出
function watchServiceExit(child) {
  const already = readExit(child);
  let resolveExit;
  const exited = new Promise((resolve) => {
    resolveExit = resolve;
  });
  const finish = (code, signal) => {
    resolveExit({ code: code === undefined ? null : code, signal: signal === undefined ? null : signal });
  };
  if (already) {
    finish(already.code, already.signal);
  } else {
    child.on("exit", (code, signal) => finish(code, signal));
  }
  return { exited, already };
}

function exitLabel(info) {
  if (typeof info.code === "number") {
    return info.code;
  }
  return info.signal || "未知";
}

async function runShell(options) {
  const {
    argv,
    io = { stdout: process.stdout, stderr: process.stderr },
    openWindow,
    spawn,
    env,
  } = options;

  const parsed = parseShellArgs(argv);
  if (!parsed.ok) {
    writeError(io, parsed.error);
    return 2;
  }
  const { repo, kit, assets, python, transcripts } = parsed.value;

  const pythonResult = await findPython({ python });
  if (!pythonResult.ok) {
    writeError(io, pythonResult.error);
    return 1;
  }

  const command = serviceCommand({
    python: pythonResult.command,
    kit,
    repo,
    assets,
    transcripts,
  });

  let started;
  try {
    started = await startService({ command, spawn, env });
  } catch (err) {
    writeError(io, err && err.message ? err.message : String(err));
    return 1;
  }
  const { child, handshake } = started;
  const handshakeValue = handshake.value;

  const serviceExit = watchServiceExit(child);

  if (serviceExit.already) {
    // 开窗口之前服务就已经没了：还没有窗口可关，照「服务意外退出」写一行 ERROR 并以 1 退出
    writeError(io, `服务意外退出（退出码 ${exitLabel(serviceExit.already)}）`);
    return 1;
  }

  let win;
  try {
    win = await openWindow({ bootstrap: handshakeValue.bootstrap, origin: handshakeValue.origin });
  } catch (err) {
    // 开窗口期间服务死了（loadURL 会随之 reject）时，根因是服务退出，优先报它
    const gone = readExit(child);
    if (gone) {
      writeError(io, `服务意外退出（退出码 ${exitLabel(gone)}）`);
      return 1;
    }
    writeError(io, "打开窗口失败");
    await stopService(child);
    return 1;
  }

  const winner = await Promise.race([
    win.closed.then(() => ({ kind: "closed" })),
    serviceExit.exited.then((info) => ({ kind: "exited", info })),
  ]);

  if (winner.kind === "exited") {
    writeError(io, `服务意外退出（退出码 ${exitLabel(winner.info)}）`);
    try {
      win.close();
    } catch {
      // 窗口已经没了
    }
    return 1;
  }

  const stop = await stopService(child);
  if (stop.exited && stop.code === 0) {
    return 0;
  }
  writeError(io, "服务没有以 0 正常退出");
  return 1;
}

module.exports = { runShell };
