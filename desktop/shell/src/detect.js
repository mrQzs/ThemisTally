"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
// 候选顺序以 python.js 为唯一出处（冻结），这里只读引用
const { DEFAULT_PYTHON_CANDIDATES } = require("./python.js");

// 打印版本与解释器路径，再按版本门槛决定退出码：一次进程同时回答「能不能跑」与「是什么」
const PYTHON_INFO_CODE =
  "import sys; print(sys.version.split()[0]); print(sys.executable); sys.exit(0 if sys.version_info >= (3, 10) else 1)";
const KIT_VERSION_RE = /\d+\.\d+\.\d+/;
const DEFAULT_TIMEOUT_MS = 10000;

function timeoutOf(options) {
  const opts = options || {};
  return typeof opts.timeoutMs === "number" ? opts.timeoutMs : DEFAULT_TIMEOUT_MS;
}

// 末尾的空行不算一行：探测输出靠「至少两行」判断有没有拿到解释器路径
function splitLines(text) {
  const lines = String(text).split(/\r?\n/);
  while (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

// 子进程一律不经 shell：参数原样到达，metacharacter 不会被解释
function runProcess(command, args, options) {
  const timeoutMs = timeoutOf(options);
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(command, args, {
        stdio: ["ignore", "pipe", "pipe"],
        shell: false,
        windowsHide: true,
      });
    } catch (err) {
      resolve({ code: null, stdout: "", stderr: "", timedOut: false, error: errorCodeOf(err) });
      return;
    }
    let stdout = "";
    let stderr = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        child.kill();
      } catch {
        // 已经没了
      }
      resolve({ code: null, stdout, stderr, timedOut: true });
    }, timeoutMs);
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ code: null, stdout: "", stderr: "", timedOut: false, error: errorCodeOf(err) });
    });
    child.on("exit", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ code, stdout, stderr, timedOut: false });
    });
  });
}

function errorCodeOf(err) {
  if (err && typeof err.code === "string") return err.code;
  return String((err && err.message) || err);
}

// 仓库只看文件系统：.git 目录或文件都算（worktree 与子模块是文件），.agent 必须是目录
function checkRepo(repoPath) {
  if (typeof repoPath !== "string" || repoPath.length === 0) return "not-git";
  let git;
  try {
    git = fs.statSync(path.join(repoPath, ".git"));
  } catch {
    return "not-git";
  }
  if (!git.isFile() && !git.isDirectory()) return "not-git";
  let agent;
  try {
    agent = fs.statSync(path.join(repoPath, ".agent"));
  } catch {
    return "no-agent";
  }
  if (!agent.isDirectory()) return "no-agent";
  return "ok";
}

async function probePython(commandArgs, options) {
  if (!Array.isArray(commandArgs) || commandArgs.length === 0) {
    return { ok: false, reason: "no-command" };
  }
  const opts = options || {};
  const code = typeof opts.code === "string" ? opts.code : PYTHON_INFO_CODE;
  const full = [...commandArgs, "-c", code];
  const result = await runProcess(full[0], full.slice(1), { timeoutMs: timeoutOf(options) });
  if (result.error !== undefined) return { ok: false, reason: "no-command" };
  if (result.timedOut) return { ok: false, reason: "timeout" };
  if (result.code !== 0) return { ok: false, reason: "version-too-old" };
  const lines = splitLines(result.stdout);
  if (lines.length < 2) return { ok: false, reason: "bad-output" };
  return { ok: true, version: lines[0], path: lines[1] };
}

// kit 的判据：<kit>/scripts/pi_dispatch.py --version 跑得通，并从输出里取到 x.y.z
async function probeKit(pythonPath, kitDir, options) {
  if (typeof pythonPath !== "string" || pythonPath.length === 0) {
    return { ok: false, reason: "python-unusable" };
  }
  const script = path.join(kitDir, "scripts", "pi_dispatch.py");
  const result = await runProcess(pythonPath, [script, "--version"], { timeoutMs: timeoutOf(options) });
  if (result.error !== undefined) return { ok: false, reason: "no-command" };
  if (result.timedOut) return { ok: false, reason: "timeout" };
  if (result.code !== 0) return { ok: false, reason: "kit-unusable" };
  const match = KIT_VERSION_RE.exec(`${result.stdout}\n${result.stderr}`);
  if (match === null) return { ok: false, reason: "kit-unusable" };
  return { ok: true, version: match[0] };
}

async function detectPython(options) {
  const timeoutMs = timeoutOf(options);
  for (const candidate of DEFAULT_PYTHON_CANDIDATES) {
    const result = await probePython(candidate, { timeoutMs });
    if (result.ok) {
      return { status: "ok", source: "auto", path: result.path, version: result.version };
    }
  }
  return { status: "missing", source: "auto", path: "", version: "" };
}

async function detectKit(options) {
  const opts = options || {};
  const timeoutMs = timeoutOf(opts);
  const kitPath = typeof opts.kitPath === "string" ? opts.kitPath : "";
  const repoPath = typeof opts.repoPath === "string" ? opts.repoPath : "";
  let kitDir;
  let source;
  if (kitPath.length > 0) {
    kitDir = kitPath;
    source = "external";
  } else if (repoPath.length > 0) {
    kitDir = repoPath;
    source = "repo";
  } else {
    // 两处都没有：没有可探测的目标，按仓库口径回 missing（不起子进程）
    return { status: "missing", source: "repo", path: "", version: "" };
  }
  const result = await probeKit(opts.pythonPath, kitDir, { timeoutMs });
  if (!result.ok) return { status: "missing", source, path: "", version: "" };
  return {
    status: "ok",
    source,
    path: path.join(kitDir, "scripts", "pi_dispatch.py"),
    version: result.version,
  };
}

module.exports = {
  PYTHON_INFO_CODE,
  KIT_VERSION_RE,
  runProcess,
  checkRepo,
  probePython,
  probeKit,
  detectPython,
  detectKit,
};
