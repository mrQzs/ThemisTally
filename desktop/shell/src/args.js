"use strict";

const { parseArgs } = require("node:util");
const fs = require("node:fs");
const path = require("node:path");

const OPTIONS = {
  repo: { type: "string" },
  kit: { type: "string" },
  assets: { type: "string" },
  python: { type: "string" },
  transcript: { type: "string", multiple: true },
};

const REQUIRED = ["repo", "kit", "assets"];

function isDirectory(target) {
  try {
    return fs.statSync(target).isDirectory();
  } catch {
    return false;
  }
}

function isFile(target) {
  try {
    return fs.statSync(target).isFile();
  } catch {
    return false;
  }
}

function parseShellArgs(argv) {
  let parsed;
  try {
    parsed = parseArgs({ args: argv, options: OPTIONS, strict: true, allowPositionals: false });
  } catch (err) {
    const quoted = /'([^']+)'/.exec(err && err.message ? err.message : "");
    const token = quoted ? quoted[1] : "";
    if (err && err.code === "ERR_PARSE_ARGS_UNKNOWN_OPTION") {
      return { ok: false, error: `未知参数：${token}` };
    }
    if (err && err.code === "ERR_PARSE_ARGS_UNEXPECTED_POSITIONAL") {
      return { ok: false, error: `不接受位置参数：${token}` };
    }
    return { ok: false, error: `参数解析失败：${token}` };
  }

  const values = parsed.values;

  const missing = REQUIRED.filter((name) => values[name] === undefined);
  if (missing.length > 0) {
    return { ok: false, error: `缺少必需参数：${missing.map((name) => `--${name}`).join("、")}` };
  }

  const repo = path.resolve(values.repo);
  if (!isDirectory(repo)) {
    return { ok: false, error: `--repo 不是目录：${repo}` };
  }

  const kit = path.resolve(values.kit);
  if (!isDirectory(kit)) {
    return { ok: false, error: `--kit 不是目录：${kit}` };
  }
  if (!isFile(path.join(kit, "scripts", "pi_dispatch.py"))) {
    return { ok: false, error: `--kit 下没有 scripts/pi_dispatch.py：${kit}` };
  }

  const assets = path.resolve(values.assets);
  if (!isDirectory(assets)) {
    return { ok: false, error: `--assets 不是目录：${assets}` };
  }
  if (!isFile(path.join(assets, "index.html"))) {
    return { ok: false, error: `--assets 下没有 index.html：${assets}` };
  }

  return {
    ok: true,
    value: {
      repo,
      kit,
      assets,
      python: values.python !== undefined ? values.python : null,
      transcripts: values.transcript !== undefined ? values.transcript : [],
    },
  };
}

module.exports = { parseShellArgs };
