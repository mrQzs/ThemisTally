"use strict";

const REQUIRED_FIELDS = ["themis_ui", "bootstrap", "origin", "control", "pid"];
const ORIGIN_RE = /^http:\/\/127\.0\.0\.1:(\d{1,5})$/;

function parseHandshake(line) {
  const text = typeof line === "string" ? line : String(line);
  const firstLine = text.split("\n", 1)[0].replace(/\r$/, "");

  let obj;
  try {
    obj = JSON.parse(firstLine);
  } catch {
    return { ok: false, error: "握手行不是 JSON 对象" };
  }
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return { ok: false, error: "握手行不是 JSON 对象" };
  }

  const missing = REQUIRED_FIELDS.filter((field) => obj[field] === undefined);
  if (missing.length > 0) {
    return { ok: false, error: `握手缺字段：${missing.join("、")}` };
  }

  if (obj.themis_ui !== 1) {
    return { ok: false, error: "握手的协议版本不对" };
  }

  const originMatch = typeof obj.origin === "string" ? ORIGIN_RE.exec(obj.origin) : null;
  const port = originMatch ? Number(originMatch[1]) : 0;
  if (!originMatch || port < 1 || port > 65535) {
    return { ok: false, error: "握手的 origin 不是 http://127.0.0.1:<端口>" };
  }

  let bootstrapUrl;
  try {
    bootstrapUrl = new URL(obj.bootstrap);
  } catch {
    return { ok: false, error: "握手的 bootstrap 不在服务 origin 下" };
  }
  if (bootstrapUrl.origin !== obj.origin) {
    return { ok: false, error: "握手的 bootstrap 不在服务 origin 下" };
  }

  if (typeof obj.control !== "string" || obj.control.length === 0) {
    return { ok: false, error: "握手的 control 不是非空字符串" };
  }

  if (!Number.isInteger(obj.pid) || obj.pid <= 0) {
    return { ok: false, error: "握手的 pid 不是正整数" };
  }

  return {
    ok: true,
    value: {
      themis_ui: obj.themis_ui,
      bootstrap: obj.bootstrap,
      origin: obj.origin,
      control: obj.control,
      pid: obj.pid,
    },
  };
}

module.exports = { parseHandshake };
