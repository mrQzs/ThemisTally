"use strict";

const fs = require("node:fs");
const path = require("node:path");

// 缺省设置：文件不存在、或整份读不出合法取值时用它起步。
// 冻结只是防自己人误改，读出去的一律是深拷贝
const DEFAULT_SETTINGS = Object.freeze({
  version: 1,
  repos: [],
  currentRepo: null,
  transcriptDirs: [],
  theme: "dark",
  density: "standard",
  pythonPath: null,
  kitPath: null,
});

// 写盘只写这些键，顺序照此（JSON 的键序跟着这个数组走）
const SETTINGS_FILE_KEYS = [
  "version",
  "repos",
  "currentRepo",
  "transcriptDirs",
  "theme",
  "density",
  "pythonPath",
  "kitPath",
];
const THEME_VALUES = ["system", "light", "dark"];
const DENSITY_VALUES = ["standard", "compact"];
// 设置接口只认这六个键，不接受任何路径：路径只能来自系统选择框
const PATCH_KEYS = ["theme", "density", "removeRepo", "removeTranscriptDir", "resetPython", "resetKit"];

const TMP_SUFFIX = ".tmp";
const BAD_PREFIX = "settings.bad-";
const BAD_SUFFIX = ".json";
const BAD_SEQ_START = 2;

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value) {
  return typeof value === "string";
}

function isTextOrNull(value) {
  return value === null || isText(value);
}

function isRepoEntry(value) {
  return (
    isPlainObject(value) &&
    isText(value.id) &&
    isText(value.name) &&
    isText(value.path) &&
    isTextOrNull(value.lastOpened)
  );
}

function isDirEntry(value) {
  return isPlainObject(value) && isText(value.id) && isText(value.path);
}

// 已知键的合法取值：version 固定为数字 1，两个数组逐项查形状，两个路径是字符串或 null
function isKnownKeyOk(key, value) {
  if (key === "version") return value === 1;
  if (key === "repos") return Array.isArray(value) && value.every(isRepoEntry);
  if (key === "transcriptDirs") return Array.isArray(value) && value.every(isDirEntry);
  if (key === "theme") return THEME_VALUES.includes(value);
  if (key === "density") return DENSITY_VALUES.includes(value);
  return isTextOrNull(value);
}

function pickEntry(value, keys) {
  const out = {};
  for (const key of keys) out[key] = value[key];
  return out;
}

// 只保留已知键的深拷贝：未知键在这一步就被丢掉，下次写盘自然消失
function copySettings(raw) {
  const out = {};
  for (const key of SETTINGS_FILE_KEYS) {
    const value = raw[key] === undefined ? DEFAULT_SETTINGS[key] : raw[key];
    if (key === "repos") out[key] = value.map((entry) => pickEntry(entry, ["id", "name", "path", "lastOpened"]));
    else if (key === "transcriptDirs") out[key] = value.map((entry) => pickEntry(entry, ["id", "path"]));
    else out[key] = value;
  }
  return out;
}

function defaultCopy() {
  return copySettings(DEFAULT_SETTINGS);
}

// 外观对象：只取 theme 与 density 两个字段，返回新对象（不返回入参本身，改返回值不改到入参）
function appearanceOf(settings) {
  return { theme: settings.theme, density: settings.density };
}

function normalizeSettings(raw) {
  if (!isPlainObject(raw)) return { ok: false };
  for (const key of SETTINGS_FILE_KEYS) {
    const value = raw[key] === undefined ? DEFAULT_SETTINGS[key] : raw[key];
    if (!isKnownKeyOk(key, value)) return { ok: false };
  }
  return { ok: true, settings: copySettings(raw) };
}

// UTC 时刻：YYYYMMDDTHHMMSSmmmZ，毫秒在内，同一毫秒的第二个副本靠 -2/-3 分开
function stampOf(date) {
  const pad = (value, width) => String(value).padStart(width, "0");
  return (
    pad(date.getUTCFullYear(), 4) +
    pad(date.getUTCMonth() + 1, 2) +
    pad(date.getUTCDate(), 2) +
    "T" +
    pad(date.getUTCHours(), 2) +
    pad(date.getUTCMinutes(), 2) +
    pad(date.getUTCSeconds(), 2) +
    pad(date.getUTCMilliseconds(), 3) +
    "Z"
  );
}

// 已存在就不覆盖，依次试 -2、-3……直到撞上一个没人用的名字
function badCopyPath(dir, stamp) {
  let candidate = path.join(dir, `${BAD_PREFIX}${stamp}${BAD_SUFFIX}`);
  let seq = BAD_SEQ_START;
  while (fs.existsSync(candidate)) {
    candidate = path.join(dir, `${BAD_PREFIX}${stamp}-${seq}${BAD_SUFFIX}`);
    seq += 1;
  }
  return candidate;
}

function createSettingsStore(options) {
  const opts = options || {};
  const dir = opts.dir;
  const now = typeof opts.now === "function" ? opts.now : () => new Date();
  const filePath = path.join(dir, "settings.json");

  // 坏文件的原始字节另存一份：内容一字不动，路径带 UTC 时刻，不覆盖已有副本
  function keepBadCopy(raw) {
    const target = badCopyPath(dir, stampOf(now()));
    try {
      fs.writeFileSync(target, raw);
    } catch {
      return null;
    }
    return target;
  }

  function load() {
    let raw;
    try {
      raw = fs.readFileSync(filePath);
    } catch {
      // 没有文件是常态；别的读失败（权限等）也没有字节可留证，一样用缺省设置起步
      return { settings: defaultCopy(), badCopy: null };
    }
    let parsed;
    try {
      parsed = JSON.parse(raw.toString("utf8"));
    } catch {
      return { settings: defaultCopy(), badCopy: keepBadCopy(raw) };
    }
    const normalized = normalizeSettings(parsed);
    if (!normalized.ok) return { settings: defaultCopy(), badCopy: keepBadCopy(raw) };
    return { settings: normalized.settings, badCopy: null };
  }

  // 原子写：先写同名临时文件，再换名覆盖正式文件（Node 的换名在目标已存在时会覆盖它）
  function save(settings) {
    const obj = {};
    for (const key of SETTINGS_FILE_KEYS) {
      obj[key] = settings[key] === undefined ? DEFAULT_SETTINGS[key] : settings[key];
    }
    const data = `${JSON.stringify(obj, null, 2)}\n`;
    const tmpPath = `${filePath}${TMP_SUFFIX}`;
    fs.mkdirSync(dir, { recursive: true });
    try {
      fs.writeFileSync(tmpPath, data);
      fs.renameSync(tmpPath, filePath);
    } catch (err) {
      try {
        fs.unlinkSync(tmpPath);
      } catch {
        // 删不掉（例如临时路径被占了目录）也要把原始错误抛出去
      }
      throw err;
    }
  }

  return { dir, filePath, load, save };
}

// 校验顺序固定：形状与未知键 → id 存在性 → 是不是当前仓库。任一项不合格就整体拒绝
function applyPatch(settings, patch) {
  if (!isPlainObject(patch)) return { ok: false, reason: "bad-patch" };
  for (const key of Object.keys(patch)) {
    if (!PATCH_KEYS.includes(key)) return { ok: false, reason: "bad-patch" };
  }
  if (patch.theme !== undefined && !THEME_VALUES.includes(patch.theme)) {
    return { ok: false, reason: "bad-patch" };
  }
  if (patch.density !== undefined && !DENSITY_VALUES.includes(patch.density)) {
    return { ok: false, reason: "bad-patch" };
  }
  if (patch.resetPython !== undefined && patch.resetPython !== true) {
    return { ok: false, reason: "bad-patch" };
  }
  if (patch.resetKit !== undefined && patch.resetKit !== true) {
    return { ok: false, reason: "bad-patch" };
  }
  if (patch.removeRepo !== undefined && !isText(patch.removeRepo)) {
    return { ok: false, reason: "bad-patch" };
  }
  if (patch.removeTranscriptDir !== undefined && !isText(patch.removeTranscriptDir)) {
    return { ok: false, reason: "bad-patch" };
  }
  const next = copySettings(settings);
  if (patch.removeRepo !== undefined && !next.repos.some((entry) => entry.id === patch.removeRepo)) {
    return { ok: false, reason: "unknown-id" };
  }
  if (
    patch.removeTranscriptDir !== undefined &&
    !next.transcriptDirs.some((entry) => entry.id === patch.removeTranscriptDir)
  ) {
    return { ok: false, reason: "unknown-id" };
  }
  if (patch.removeRepo !== undefined && patch.removeRepo === next.currentRepo) {
    return { ok: false, reason: "current-repo" };
  }
  if (patch.theme !== undefined) next.theme = patch.theme;
  if (patch.density !== undefined) next.density = patch.density;
  if (patch.removeRepo !== undefined) {
    next.repos = next.repos.filter((entry) => entry.id !== patch.removeRepo);
  }
  if (patch.removeTranscriptDir !== undefined) {
    next.transcriptDirs = next.transcriptDirs.filter((entry) => entry.id !== patch.removeTranscriptDir);
  }
  if (patch.resetPython !== undefined) next.pythonPath = null;
  if (patch.resetKit !== undefined) next.kitPath = null;
  return { ok: true, settings: next };
}

// Windows 下路径不分大小写，别的平台区分：resolve 之后再转小写
function pathKey(value) {
  const resolved = path.resolve(value);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function baseName(value) {
  const name = path.basename(String(value).replace(/[\\/]+$/, ""));
  return name.length > 0 ? name : "repo";
}

function uniqueId(entries, base) {
  const taken = new Set(entries.map((entry) => entry.id));
  if (!taken.has(base)) return base;
  let seq = BAD_SEQ_START;
  while (taken.has(`${base}-${seq}`)) seq += 1;
  return `${base}-${seq}`;
}

function findByPath(entries, value) {
  const key = pathKey(value);
  return entries.find((entry) => pathKey(entry.path) === key) || null;
}

function addEntry(settings, listKey, value, idBase, makeEntry) {
  const next = copySettings(settings);
  const existing = findByPath(next[listKey], value);
  if (existing !== null) return { ok: true, settings: next, id: existing.id, reused: true };
  const id = uniqueId(next[listKey], idBase);
  next[listKey].push(makeEntry(id, value));
  return { ok: true, settings: next, id, reused: false };
}

function addRepo(settings, repoPath) {
  const added = addEntry(settings, "repos", repoPath, baseName(repoPath), (id, value) => ({
    id,
    name: baseName(value),
    path: value,
    lastOpened: null,
  }));
  // 只有还没有当前仓库时，新仓库才成为当前仓库
  if (!added.reused && added.settings.currentRepo === null) added.settings.currentRepo = added.id;
  return added;
}

function addTranscriptDir(settings, dirPath) {
  return addEntry(settings, "transcriptDirs", dirPath, "dir", (id, value) => ({ id, path: value }));
}

// 切换当前仓库的纯函数：只改 currentRepo 与目标条目的 lastOpened，其余一字不动。
// id 不是非空字符串或不在 repos 里 → unknown-repo，入参不被修改；at 是毫秒数，纯函数不读当前时间
function selectRepo(settings, id, at) {
  if (typeof id !== "string" || !settings.repos.some((entry) => entry.id === id)) {
    return { ok: false, reason: "unknown-repo" };
  }
  const next = copySettings(settings);
  next.currentRepo = id;
  next.repos.find((entry) => entry.id === id).lastOpened = new Date(at).toISOString();
  return { ok: true, settings: next };
}

module.exports = {
  DEFAULT_SETTINGS,
  SETTINGS_FILE_KEYS,
  THEME_VALUES,
  DENSITY_VALUES,
  PATCH_KEYS,
  appearanceOf,
  createSettingsStore,
  normalizeSettings,
  applyPatch,
  addRepo,
  addTranscriptDir,
  selectRepo,
};
