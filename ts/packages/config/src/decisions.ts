// codekit/decisions.py 里配置中心用到的部分（迁移第 ③a1 片）：问题的形状、问题清单与内容锁、配置的解析与生效模式，
// 以及 pi_dispatch.battery_link_problem。报错文字会经 validate、show 进输出，逐字照 Python；检查的先后次序也照 Python。
// 路径参数都是 Python 那边 str(Path) 的写法（Windows 上用反斜杠），报错里原样出现。
import { existsSync, readdirSync, statSync } from "node:fs";
import { PyCrash, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyReadBytes, pyReadText } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { isLinkOrJunction, firstLinkComponent } from "@themis/base/pypath";
import { NOT_W, PY_END, ci, cmpCodePoints, codePoints, pyLen, pyLower, pyStrip } from "@themis/base/pyre";
import { PyValueError, urlHostname, urlPort, urlsplit, urlUserinfo } from "@themis/base/pyurl";
import { createHash } from "node:crypto";
import { PluginError, validateLock } from "./plugin-records.ts";

export const DEFAULT_BASE_URL = "https://api.typesafe.ai";
export const DEFAULT_MODEL = "jev-1.13.0";
export const DEFAULT_API_KEY_ENV = "TYPESAFE_API_KEY";
const DEFAULT_TIMEOUT_SECONDS = 4.0;
const DEFAULT_BUDGET_SECONDS = 20.0;
const DEFAULT_MAX_STATE_CHARS = 20000n;
const MAX_CHOICE_OPTIONS = 255;
const SCORE_LEVELS = [2, 10] as const;
const QUESTION_TYPES = ["choice", "score", "noul"];
export const MODES = ["off", "shadow", "on"];
export const OFF_MARKER = "DECISIONS_OFF";
export const POINTS = ["report-screen", "mutation-equivalence", "run-health"];
export const PLUGIN_ID = "decisions";
export const PERMISSION = "network-decisions";
const BATTERY_ID_PATTERN = "^[a-z][a-z0-9-]{0,63}$";
const BATTERY_ID_RE = new RegExp(`^[a-z][a-z0-9-]{0,63}${PY_END}`, "u");
const VERSION_RE = new RegExp(`^[0-9]+\\.[0-9]+\\.[0-9]+${PY_END}`, "u");
const ENV_NAME_RE = new RegExp(`^[A-Za-z_][A-Za-z0-9_]{0,127}${PY_END}`, "u");
const MODEL_RE = new RegExp(`^[A-Za-z0-9][A-Za-z0-9._:/~-]{0,99}${PY_END}`, "u");
const SEP = process.platform === "win32" ? "\\" : "/";

/** 任何“不要信、不要用这个结果”的情况；code 是机器可读的原因，str(exc) 是 "code: detail"。 */
export class DecisionError extends Error {
  override readonly name = "DecisionError";
  readonly code: string;
  readonly detail: string;
  constructor(code: string, detail = "") {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;
    this.detail = detail;
  }
}

/** check_question 抛的 ValueError（调用方的 bug）。 */
export class QuestionError extends Error {
  override readonly name = "ValueError";
}

/** pathlib 的 base / part 写法（base 已是规整过的 str(Path)）。 */
export function joinPath(base: string, ...parts: string[]): string {
  return parts.reduce((left, part) => (left.endsWith(SEP) ? left + part : left + SEP + part), base);
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isContent = (value: PyValue | undefined): boolean => typeof value === "string" || isDict(value) || Array.isArray(value);
const reprSorted = (values: Iterable<string>): string => pyReprValue([...values].sort(cmpCodePoints));
const NON_WORD_RUN = new RegExp(`(?:${NOT_W}|_)+`, "gu");

function identifierText(text: string): string {
  return pyStrip(pyLower(text).replace(NON_WORD_RUN, " "));
}

function shown(value: PyValue): string {
  const text = typeof value === "string" ? value : dumps(value, { ensureAscii: false });
  return pyLen(text) <= 80 ? text : `${codePoints(text).slice(0, 77).join("")}...`;
}

/** 一个问题的线上形状；不合的以 ValueError 指出是哪个问题、缺什么。 */
export function checkQuestion(name: string, question: PyValue | undefined): PyDict {
  const who = shown(name);
  if (!isDict(question)) throw new QuestionError(`question "${who}" must be an object like {"type": ..., "instructions": ...}`);
  const unknown = [...question.keys()].filter((key) => !["type", "instructions", "criteria", "label"].includes(key as string)) as string[];
  if (unknown.length) throw new QuestionError(`question "${who}" has unknown keys ${reprSorted(unknown)}`);
  const kind = question.get("type") ?? null;
  if (typeof kind !== "string" || !QUESTION_TYPES.includes(kind)) {
    throw new QuestionError(`question "${who}" has type ${pyReprValue(kind)}; use one of ${QUESTION_TYPES.join(", ")}`);
  }
  const text = question.get("instructions");
  if (typeof text !== "string" || !pyStrip(text)) throw new QuestionError(`question "${who}" has no instructions: the text of the question, as a string`);
  if (identifierText(text) === identifierText(name)) throw new QuestionError(`question "${who}" asks nothing: its instructions only repeat its own name`);
  const criteria = question.get("criteria") ?? null;
  if (kind === "noul") {
    const out = new Map<string, PyValue>([
      ["type", "noul"],
      ["instructions", text],
    ]);
    if (criteria === null) return out;
    if (!isDict(criteria) || [...criteria.keys()].some((key) => key !== "true" && key !== "false") || !criteria.size) {
      throw new QuestionError(`question "${who}" is a noul: criteria can only be {"true": ..., "false": ...}`);
    }
    if ([...criteria.values()].some((value) => !isContent(value))) throw new QuestionError(`question "${who}": noul criteria must be text, objects or arrays`);
    out.set("criteria", new Map(criteria));
    return out;
  }
  if (kind === "choice") {
    if (!isDict(criteria) || criteria.size < 2) throw new QuestionError(`question "${who}": a choice needs an object of at least two options`);
    if (criteria.size > MAX_CHOICE_OPTIONS) throw new QuestionError(`question "${who}": a choice takes at most ${MAX_CHOICE_OPTIONS} options`);
    if ([...criteria].some(([key, value]) => typeof key !== "string" || !key || (value !== null && !isContent(value)))) {
      throw new QuestionError(`question "${who}": choice options map names to descriptions (or null)`);
    }
    return new Map<string, PyValue>([
      ["type", "choice"],
      ["instructions", text],
      ["criteria", new Map(criteria)],
    ]);
  }
  if (!Array.isArray(criteria) || criteria.length < SCORE_LEVELS[0] || criteria.length > SCORE_LEVELS[1]) {
    throw new QuestionError(`question "${who}": a score needs a list of ${SCORE_LEVELS[0]} to ${SCORE_LEVELS[1]} levels, lowest first`);
  }
  if (criteria.some((level) => !isContent(level))) throw new QuestionError(`question "${who}": score levels must be text, objects or arrays`);
  return new Map<string, PyValue>([
    ["type", "score"],
    ["instructions", text],
    ["criteria", [...criteria]],
  ]);
}

export function checkQuestions(questions: PyValue | undefined): PyDict {
  if (!isDict(questions) || !questions.size) throw new QuestionError("questions must be a non-empty mapping of {name: question}");
  return new Map([...questions].map(([name, question]) => [name, checkQuestion(name as string, question)]));
}

/** float(value)：超出 double 范围的 int 照 Python 抛 OverflowError（Python 在这里没接住，打堆栈）。 */
function toFloat(value: bigint | number): number {
  if (typeof value === "number") return value;
  const result = Number(value);
  if (!Number.isFinite(result)) throw new PyCrash("OverflowError", "int too large to convert to float");
  return result;
}

const isNumeric = (value: PyValue | undefined): value is bigint | number => typeof value === "bigint" || typeof value === "number";

/** json.loads(Path(shown).read_text(encoding="utf-8"))：OSError 与 ValueError（含 UnicodeDecodeError）交给调用方，其余照抛。 */
function loadJsonFile(path: string): PyValue {
  return loads(pyReadText(path));
}

/** except (OSError, ValueError)：读不出、不是合法 UTF-8 或 JSON；RecursionError 不在其中，照抛（Python 打堆栈）。 */
function readFailure(error: unknown): string | null {
  if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return error.message;
  if (error instanceof PyJsonError && error.kind !== "RecursionError") return error.message;
  return null;
}

export interface Battery {
  readonly id: string;
  readonly version: string;
  readonly description: PyValue;
  readonly state_fields: PyValue[];
  readonly questions: PyDict;
  readonly labels: PyDict;
  readonly thresholds: PyDict;
  readonly sha256: string;
  readonly path: string;
}

/** load_battery 交回的字典（键的次序照 Python）：执行端的 JEV 照字典取题库（⑤g2）。 */
export function batteryDict(battery: Battery): PyDict {
  return new Map<string, PyValue>([
    ["id", battery.id], ["version", battery.version], ["description", battery.description], ["state_fields", battery.state_fields],
    ["questions", battery.questions], ["labels", battery.labels], ["thresholds", battery.thresholds], ["sha256", battery.sha256], ["path", battery.path],
  ]);
}

/** list(value)：str 拆成字符、dict 取键、其余不可迭代的照 Python 抛 TypeError。 */
function pyList(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return [...value];
  if (typeof value === "string") return codePoints(value);
  if (isDict(value)) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", `'${value === null ? "NoneType" : typeof value}' object is not iterable`);
}

/** 读一份问题清单：id、version、questions（线上形状）、thresholds（非负数）、给人看的 label。 */
export function loadBattery(path: string): Battery {
  let raw: PyValue;
  try {
    raw = loadJsonFile(path);
  } catch (error) {
    const reason = readFailure(error);
    if (reason === null) throw error;
    throw new DecisionError("battery_unreadable", `${path}: ${reason}`);
  }
  if (!isDict(raw)) throw new DecisionError("battery_invalid", `${path}: top level must be an object`);
  const allowed = ["id", "version", "description", "state_fields", "questions", "thresholds"];
  const unknown = [...raw.keys()].filter((key) => !allowed.includes(key as string)) as string[];
  if (unknown.length) throw new DecisionError("battery_invalid", `${path}: unknown keys ${reprSorted(unknown)}`);
  const id = raw.get("id");
  if (typeof id !== "string" || !BATTERY_ID_RE.test(id)) throw new DecisionError("battery_invalid", `${path}: id must match ${BATTERY_ID_PATTERN}`);
  const version = raw.get("version");
  if (typeof version !== "string" || !VERSION_RE.test(version)) {
    throw new DecisionError("battery_invalid", `${path}: version must be an exact semantic version`);
  }
  let questions: PyDict;
  try {
    questions = checkQuestions(raw.get("questions"));
  } catch (error) {
    if (!(error instanceof QuestionError)) throw error;
    throw new DecisionError("battery_invalid", `${path}: ${error.message}`);
  }
  const thresholds = raw.has("thresholds") ? (raw.get("thresholds") as PyValue) : new Map();
  const badThreshold = (key: PyValue, value: PyValue): boolean =>
    typeof key !== "string" || !isNumeric(value) || !Number.isFinite(toFloat(value)) || toFloat(value) < 0;
  if (!isDict(thresholds) || [...thresholds].some(([key, value]) => badThreshold(key as PyValue, value))) {
    throw new DecisionError("battery_invalid", `${path}: thresholds must map names to non-negative numbers`);
  }
  const labels = new Map(
    [...(raw.get("questions") as PyDict)].map(([name, question]) => {
      const label = (question as PyDict).get("label") ?? null;
      return [name, pyStrValue(pyTruthy(label) ? label : (name as string))];
    }),
  );
  return {
    id,
    version,
    description: raw.has("description") ? (raw.get("description") as PyValue) : "",
    state_fields: pyList(raw.has("state_fields") ? (raw.get("state_fields") as PyValue) : []),
    questions,
    labels,
    thresholds: new Map([...thresholds].map(([key, value]) => [key, toFloat(value as bigint | number)])),
    sha256: createHash("sha256").update(pyReadBytes(path)).digest("hex"),
    path,
  };
}

const JSON_NAME = new RegExp(`^[^]*${ci(".json")}$`, "u");

/**
 * Path(directory).glob("*.json") 的文件名（Windows 上不分大小写，re.IGNORECASE 下 s 还配 ſ）：目录不存在或不是目录时为空，
 * 列目录被拒（PermissionError）时也为空。
 */
function globJson(directory: string): string[] {
  if (!isDir(directory)) return [];
  let names: string[];
  try {
    names = readdirSync(directory);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "EACCES" || code === "EPERM") return [];
    throw error;
  }
  return names.filter((name) => (process.platform === "win32" ? JSON_NAME : /^[^]*\.json$/u).test(name));
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** Path.stem：最后一个点之前的部分；点在开头或结尾时没有后缀。 */
function stem(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 && dot < name.length - 1 ? name.slice(0, dot) : name;
}

/**
 * pi_dispatch._decisions_summary 用的 report-screen 清单：kit 的 plugins/decisions/questions 下那一份；读不了（DecisionError）
 * 或没有这一份时为 null。write_summary 的 SummaryContext.reportScreen 接它（dispatcher 不能 import 本包）。
 */
export function reportScreenBattery(kitRoot: string): Battery | null {
  try {
    return loadBatteries(joinPath(joinPath(joinPath(kitRoot, "plugins"), "decisions"), "questions")).get("report-screen") ?? null;
  } catch (error) {
    if (error instanceof DecisionError) return null;
    throw error;
  }
}

/** 目录下全部清单，按 id 索引；文件名必须等于 id。Windows 上 Path 的排序按小写比较。 */
export function loadBatteries(root: string): Map<string, Battery> {
  if (!isDir(root)) throw new DecisionError("plugin_missing", `no battery directory at ${root}`);
  const sortKey = (name: string): string => (process.platform === "win32" ? pyLower(name) : name);
  const found = new Map<string, Battery>();
  for (const name of globJson(root).sort((left, right) => cmpCodePoints(sortKey(left), sortKey(right)))) {
    const path = joinPath(root, name);
    const battery = loadBattery(path);
    if (battery.id !== stem(name)) throw new DecisionError("battery_invalid", `${path}: file name must equal the battery id ${battery.id}`);
    found.set(battery.id, battery);
  }
  return found;
}

const CRLF_NOTE = " only in line endings (checked out with CRLF; .gitattributes keeps plugins/decisions/** -text)";

/** 问题清单与插件的 manifest、lock 一致（2.8.0）：返回 {清单文件名: sha256}；不符时抛 DecisionError("battery_drift")。 */
export function verifyBatteryLock(pluginDir: string): Map<string, string> {
  let manifest: PyValue;
  let lock: PyValue;
  try {
    manifest = loadJsonFile(joinPath(pluginDir, "manifest.json"));
    lock = loadJsonFile(joinPath(pluginDir, "lock.json"));
  } catch (error) {
    const reason = readFailure(error);
    if (reason === null) throw error;
    throw new DecisionError("battery_drift", `plugin manifest or lock unreadable: ${reason}`);
  }
  if (!isDict(manifest) || typeof manifest.get("plugin_id") !== "string") throw new DecisionError("battery_drift", "plugin manifest has no plugin_id");
  const pluginId = manifest.get("plugin_id") as string;
  try {
    validateLock(lock, new Map([[pluginId, manifest]]));
  } catch (error) {
    if (!(error instanceof PluginError)) throw error;
    throw new DecisionError("battery_drift", `lock does not verify: ${error.message}`);
  }
  const prefix = `plugins/${pluginId}/questions/`;
  const locked = new Map<string, string>();
  for (const ref of manifest.get("resources") as PyDict[]) {
    const refPath = ref.get("path") as string;
    if (ref.get("kind") === "file" && refPath.startsWith(prefix)) locked.set(refPath.slice(prefix.length), ref.get("sha256") as string);
  }
  const questionsDir = joinPath(pluginDir, "questions");
  const present = globJson(questionsDir).sort(cmpCodePoints);
  const problems = [
    ...present.filter((name) => !locked.has(name)).map((name) => `${name} is not in the lock`),
    ...[...locked.keys()].sort(cmpCodePoints).filter((name) => !present.includes(name)).map((name) => `${name} is locked but missing`),
  ];
  for (const name of present) {
    const expected = locked.get(name);
    if (expected === undefined) continue;
    let data: Buffer;
    try {
      data = pyReadBytes(joinPath(questionsDir, name));
    } catch (error) {
      if (!(error instanceof PyOSError)) throw error;
      problems.push(`${name} cannot be read: ${error.message}`);
      continue;
    }
    if (createHash("sha256").update(data).digest("hex") !== expected) {
      const lf = Buffer.from(data.toString("latin1").replaceAll("\r\n", "\n"), "latin1");
      const onlyEol = createHash("sha256").update(lf).digest("hex") === expected;
      problems.push(`${name} differs from the locked bytes${onlyEol ? CRLF_NOTE : ""}`);
    }
  }
  if (problems.length) {
    throw new DecisionError(
      "battery_drift",
      `${problems.join("; ")}; after a reviewed change run: python scripts/codekit/decisions.py --write-lock ${pluginDir}`,
    );
  }
  return locked;
}

/** load_locked_batteries：运行时的入口（2.8.0）：先核对内容锁，再读清单，读到的字节也要等于锁里的。 */
export function loadLockedBatteries(pluginDir: string): Map<string, Battery> {
  const locked = verifyBatteryLock(pluginDir);
  const batteries = loadBatteries(joinPath(pluginDir, "questions"));
  for (const battery of batteries.values()) {
    const name = battery.path.slice(battery.path.lastIndexOf(SEP) + 1);
    if (locked.get(name) !== battery.sha256) throw new DecisionError("battery_drift", `${name} changed while it was being read`);
  }
  return batteries;
}

/** dispatch.config.json 的 decisions 对象解析后的结果，加上实际生效的模式与原因。 */
export interface Settings {
  mode: string;
  configured_mode: string;
  reason: string;
  api_key_env: string;
  base_url: string;
  model: string;
  timeout_seconds: number;
  budget_seconds: number;
  max_state_chars: bigint;
  points: string[];
  marker_present: boolean;
}

export const settingsActive = (settings: Settings): boolean => settings.mode !== "off";
export const settingsOfficial = (settings: Settings): boolean => settings.base_url === DEFAULT_BASE_URL;

function checkBaseUrl(value: string): string {
  let hostname: string | null;
  let port: number | null;
  let parsed;
  try {
    parsed = urlsplit(value);
    port = urlPort(parsed);
    hostname = urlHostname(parsed);
  } catch (error) {
    if (!(error instanceof PyValueError)) throw error;
    throw new DecisionError("config", "decisions.base_url is not a URL");
  }
  const { username, password } = urlUserinfo(parsed);
  const loopback = hostname === "127.0.0.1" || hostname === "::1" || hostname === "localhost";
  if (
    (parsed.scheme !== "http" && parsed.scheme !== "https") ||
    !hostname ||
    username ||
    password ||
    parsed.query ||
    parsed.fragment ||
    (parsed.path !== "" && parsed.path !== "/") ||
    port === 0 ||
    (parsed.scheme === "http" && !loopback)
  ) {
    throw new DecisionError("config", "decisions.base_url must be https://host[:port] or http://127.0.0.1:port");
  }
  return value.replace(/\/+$/u, "");
}

/**
 * 解析配置并判定生效的模式；配置写错是 DecisionError("config")。生效模式的判定次序：标记文件存在 → off（marker）；
 * plugins.enabled 存在却没有 decisions，或 plugins.allowed_permissions 存在却没有 network-decisions → off；
 * 插件目录没有 questions/ → off（plugin_missing）；否则就是配置的模式。
 */
export function settingsFromConfig(config: PyValue, agentDir: string | null = null, pluginDir: string | null = null): Settings {
  const settings: Settings = {
    mode: "off",
    configured_mode: "off",
    reason: "not_configured",
    api_key_env: DEFAULT_API_KEY_ENV,
    base_url: DEFAULT_BASE_URL,
    model: DEFAULT_MODEL,
    timeout_seconds: DEFAULT_TIMEOUT_SECONDS,
    budget_seconds: DEFAULT_BUDGET_SECONDS,
    max_state_chars: DEFAULT_MAX_STATE_CHARS,
    points: [...POINTS],
    marker_present: false,
  };
  let raw = isDict(config) ? (config.get("decisions") ?? null) : null;
  const configured = raw !== null;
  if (raw === null) raw = new Map();
  if (!isDict(raw)) throw new DecisionError("config", "decisions must be an object");
  const known = ["mode", "api_key_env", "base_url", "model", "timeout_seconds", "budget_seconds", "max_state_chars", "points"];
  const unknown = [...raw.keys()].filter((key) => !known.includes(key as string)) as string[];
  if (unknown.length) throw new DecisionError("config", `decisions has unknown keys ${reprSorted(unknown)}`);
  const get = (key: string, fallback: PyValue): PyValue => (raw as PyDict).has(key) ? ((raw as PyDict).get(key) as PyValue) : fallback;
  const mode = get("mode", "off");
  if (typeof mode !== "string" || !MODES.includes(mode)) throw new DecisionError("config", `decisions.mode must be one of ${MODES.join(", ")}`);
  settings.configured_mode = mode;
  const envName = get("api_key_env", DEFAULT_API_KEY_ENV);
  if (typeof envName !== "string" || !ENV_NAME_RE.test(envName)) throw new DecisionError("config", "decisions.api_key_env must be an environment variable name");
  settings.api_key_env = envName;
  const base = get("base_url", DEFAULT_BASE_URL);
  if (typeof base !== "string") throw new DecisionError("config", "decisions.base_url must be a string");
  settings.base_url = checkBaseUrl(base);
  // 自定义端点不得收到官方凭据；不区分大小写：Windows 的环境变量与默认 NTFS 上的凭据文件都不区分
  if (!settingsOfficial(settings) && settings.api_key_env.toUpperCase() === DEFAULT_API_KEY_ENV) {
    throw new DecisionError("config", `a custom decisions.base_url needs its own decisions.api_key_env (never the official ${DEFAULT_API_KEY_ENV})`);
  }
  const model = get("model", DEFAULT_MODEL);
  if (typeof model !== "string" || !MODEL_RE.test(model)) throw new DecisionError("config", "decisions.model is not a model id");
  settings.model = model;
  for (const [key, fallback, low, high] of [
    ["timeout_seconds", DEFAULT_TIMEOUT_SECONDS, 0.5, 60.0],
    ["budget_seconds", DEFAULT_BUDGET_SECONDS, 1.0, 600.0],
  ] as const) {
    const value = get(key, fallback);
    if (!isNumeric(value) || !(low <= toFloat(value) && toFloat(value) <= high)) {
      throw new DecisionError("config", `decisions.${key} must be a number between ${low.toFixed(1)} and ${high.toFixed(1)}`);
    }
    settings[key] = toFloat(value);
  }
  const chars = get("max_state_chars", DEFAULT_MAX_STATE_CHARS);
  if (typeof chars !== "bigint" || chars < 500n || chars > 120000n) {
    throw new DecisionError("config", "decisions.max_state_chars must be an integer between 500 and 120000");
  }
  settings.max_state_chars = chars;
  const points = get("points", [...POINTS]);
  if (!Array.isArray(points) || points.some((point) => typeof point !== "string" || !POINTS.includes(point)) || new Set(points).size !== points.length) {
    throw new DecisionError("config", `decisions.points must list distinct names from ${POINTS.join(", ")}`);
  }
  settings.points = [...(points as string[])];
  settings.mode = mode;
  settings.reason = mode !== "off" ? "configured" : configured ? "configured_off" : "not_configured";
  if (agentDir !== null && existsSync(joinPath(agentDir, OFF_MARKER))) {
    settings.marker_present = true;
    settings.mode = "off";
    settings.reason = "marker";
    return settings;
  }
  const plugins = isDict(config) ? config.get("plugins") : undefined;
  if (isDict(plugins)) {
    const enabled = plugins.get("enabled");
    if (Array.isArray(enabled) && !enabled.includes(PLUGIN_ID)) {
      settings.mode = "off";
      settings.reason = "plugin_disabled";
      return settings;
    }
    const allowed = plugins.get("allowed_permissions");
    if (Array.isArray(allowed) && !allowed.includes(PERMISSION)) {
      settings.mode = "off";
      settings.reason = "permission_missing";
      return settings;
    }
  }
  if (settings.mode !== "off" && pluginDir !== null && !isDir(joinPath(pluginDir, "questions"))) {
    settings.mode = "off";
    settings.reason = "plugin_missing";
  }
  return settings;
}

/**
 * pi_dispatch.battery_link_problem：决策插件的问题清单读之前的链接检查，返回第一个链接或 junction 的那一级，没有为 null。
 * 从 kitRoot 往下逐级查，按字面求相对路径、不 resolve；次序与 verifyBatteryLock 读的次序相同。
 */
export function batteryLinkProblem(kitRoot: string, pluginDir: string): string | null {
  const base = relativeTo(pluginDir, kitRoot);
  const firstLink = (rel: string): string | null => {
    if (base === null) {
      for (const path of [pluginDir, joinPath(pluginDir, ...rel.split("/"))]) {
        if (isLinkOrJunction(path)) return path;
      }
      return null;
    }
    return firstLinkComponent(kitRoot, `${base}/${rel}`);
  };
  for (const rel of ["manifest.json", "lock.json", "questions"]) {
    const link = firstLink(rel);
    if (link !== null) return link;
  }
  let names: string[];
  try {
    names = globJson(joinPath(pluginDir, "questions")).sort(cmpCodePoints);
  } catch {
    return null; // 列不出来交给 verifyBatteryLock 报 battery_drift
  }
  for (const name of names) {
    const link = firstLink(`questions/${name}`);
    if (link !== null) return link;
  }
  return null;
}

/** PurePath.relative_to(...).as_posix()：Windows 上按 normcase 比较各段；不在其下时为 null。 */
function relativeTo(path: string, root: string): string | null {
  const parts = (value: string): string[] => value.split(SEP).filter((part) => part !== "");
  const norm = (value: string): string => (process.platform === "win32" ? pyLower(value) : value);
  const child = parts(path);
  const parent = parts(root);
  if (parent.length > child.length || parent.some((part, index) => norm(part) !== norm(child[index] as string))) return null;
  return child.slice(parent.length).join("/");
}
