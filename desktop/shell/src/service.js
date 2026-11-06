"use strict";

const { spawn } = require("node:child_process");
const path = require("node:path");
const { parseHandshake } = require("./handshake.js");

function serviceCommand(options) {
  const { python, kit, repo, assets, transcripts } = options;
  const argv = [
    ...python,
    path.join(kit, "scripts", "pi_dispatch.py"),
    "--repo", repo,
    "ui",
    "--desktop",
    "--assets", assets,
  ];
  for (const transcript of transcripts || []) {
    argv.push("--transcript", transcript);
  }
  return argv;
}

function defaultSpawn(command, args, options) {
  return spawn(command[0], command.slice(1), options);
}

function startService(options) {
  const { command, timeoutMs = 30000, spawn: spawnFn = defaultSpawn, env } = options;
  return new Promise((resolve, reject) => {
    const child = spawnFn(command, [], {
      stdio: ["pipe", "pipe", "inherit"],
      windowsHide: true,
      shell: false,
      env,
    });

    let settled = false;
    let buffer = "";
    let timer = setTimeout(() => {
      finishError("握手超时");
    }, timeoutMs);

    function finishError(message) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(message));
      try {
        child.kill();
      } catch {
        // 已经没了
      }
    }

    child.on("error", (err) => {
      finishError(`服务启动失败：${err && err.code ? err.code : String(err)}`);
    });

    child.on("exit", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(`服务在握手前退出（退出码 ${code === null ? "未知" : code}）`));
    });

    child.stdout.on("data", (chunk) => {
      if (settled) return;
      buffer += chunk.toString("utf8");
      const newline = buffer.indexOf("\n");
      if (newline === -1) return;
      const line = buffer.slice(0, newline);
      buffer = "";
      const result = parseHandshake(line);
      settled = true;
      clearTimeout(timer);
      if (!result.ok) {
        reject(new Error(result.error));
        try {
          child.kill();
        } catch {
          // 已经没了
        }
        return;
      }
      resolve({ child, handshake: result });
    });
  });
}

function stopService(child, options) {
  const graceMs = options && options.graceMs !== undefined ? options.graceMs : 10000;
  return new Promise((resolve) => {
    // 已经退出的子进程：事件早就发完了，等下去永远等不到——立即兑现，不碰 stdin、不等宽限期
    if (typeof child.exitCode === "number" || child.signalCode) {
      resolve({
        exited: true,
        code: typeof child.exitCode === "number" ? child.exitCode : null,
        signal: child.signalCode ? child.signalCode : null,
        killed: false,
      });
      return;
    }

    let done = false;
    // end 与子进程退出撞车时会往 stdin 抛 EPIPE：先接住，别让它变成未捕获的错误
    try {
      child.stdin.on("error", () => {});
    } catch {
      // stdin 已经没了
    }
    try {
      child.stdin.end();
    } catch {
      // stdin 已经没了
    }

    const graceTimer = setTimeout(() => {
      if (done) return;
      done = true;
      try {
        child.kill();
      } catch {
        // 已经没了
      }
      const onKilled = (code, signal) => {
        resolve({ exited: false, code: null, signal: signal === undefined ? null : signal, killed: true });
      };
      child.once("exit", onKilled);
      child.once("close", onKilled);
    }, graceMs);

    const onGone = (code, signal) => {
      if (done) return;
      done = true;
      clearTimeout(graceTimer);
      resolve({
        exited: true,
        code: code === undefined ? null : code,
        signal: signal === undefined ? null : signal,
        killed: false,
      });
    };
    child.once("exit", onGone);
    child.once("close", onGone);
  });
}

module.exports = { serviceCommand, startService, stopService };
