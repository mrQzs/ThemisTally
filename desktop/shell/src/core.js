"use strict";

const { parseShellArgs } = require("./args.js");
const { findPython } = require("./python.js");
const { serviceCommand, startService, stopService } = require("./service.js");

function writeError(io, message) {
  io.stderr.write(`ERROR: ${message}\n`);
}

async function runShell(options) {
  const { argv, io, openWindow, spawn, env } = options;

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

  const win = await openWindow({ bootstrap: handshakeValue.bootstrap, origin: handshakeValue.origin });

  const serviceExit = new Promise((resolve) => {
    child.on("exit", (code, signal) => resolve({ code, signal }));
  });

  const winner = await Promise.race([
    win.closed.then(() => ({ kind: "closed" })),
    serviceExit.then((info) => ({ kind: "exited", info })),
  ]);

  if (winner.kind === "exited") {
    const code = winner.info.code;
    const label = typeof code === "number" ? code : winner.info.signal || "未知";
    writeError(io, `服务意外退出（退出码 ${label}）`);
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
