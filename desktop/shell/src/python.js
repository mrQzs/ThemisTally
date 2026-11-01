"use strict";

const { spawn } = require("node:child_process");

const PYTHON_PROBE_CODE = "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)";
const DEFAULT_PYTHON_CANDIDATES = [["python3"], ["python"], ["py", "-3"]];

function spawnProbe(command, timeoutMs) {
  return new Promise((resolve) => {
    const full = [...command, "-c", PYTHON_PROBE_CODE];
    let settled = false;
    let child;
    try {
      child = spawn(full[0], full.slice(1), {
        stdio: ["ignore", "ignore", "ignore"],
        windowsHide: true,
        shell: false,
      });
    } catch (err) {
      resolve({ ok: false, reason: err && err.code === "ENOENT" ? "命令不存在" : "启动失败" });
      return;
    }
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        child.kill();
      } catch {
        // 已经没了
      }
      resolve({ ok: false, reason: "超时" });
    }, timeoutMs);
    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: false, reason: err && err.code === "ENOENT" ? "命令不存在" : `启动失败：${err && err.code}` });
    });
    child.on("exit", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(code === 0 ? { ok: true, reason: "" } : { ok: false, reason: `退出码 ${code}` });
    });
  });
}

async function findPython(options) {
  const opts = options || {};
  const timeoutMs = opts.timeoutMs !== undefined ? opts.timeoutMs : 10000;
  const probe = opts.probe || spawnProbe;

  let candidates;
  let summaryError;
  if (opts.python !== undefined && opts.python !== null) {
    candidates = [[opts.python]];
    summaryError = `指定的 Python 不可用：${opts.python}`;
  } else {
    candidates = opts.candidates || DEFAULT_PYTHON_CANDIDATES;
    summaryError = "找不到可用的 Python（要求 ≥ 3.10）";
  }

  const tried = [];
  for (const candidate of candidates) {
    const result = await probe(candidate, timeoutMs);
    if (result && result.ok) {
      return { ok: true, command: candidate };
    }
    tried.push({ command: candidate, reason: (result && result.reason) || "" });
  }
  return { ok: false, error: summaryError, tried };
}

module.exports = { PYTHON_PROBE_CODE, DEFAULT_PYTHON_CANDIDATES, findPython };
