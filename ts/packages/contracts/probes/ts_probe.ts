// 契约探针（TS 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果，与 python_probe.py 收发同样的 JSON。
// 同一份源码由 `node`（类型擦除）与 `bun` 各跑一遍。
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { attemptDirName, auditId, newMsgId, newTurnId, utcCompact, utcNow } from "@themis/base/clock";
import { UnicodeDecodeError, readText, sleepSync, writeTextAtomic } from "@themis/base/fsutil";
import { SAFE_MAX_LINE_BYTES, appendEvent, iterLines, jsonlRecords, linesBefore, readJsonl } from "@themis/base/jsonl";
import { ConfigLock, DirLock, LockBusyError, TaskLock } from "@themis/base/locks";
import { FileLockTimeout, type WinProcessApi, acquireFileLock, initFileAttributes, winProcessApi } from "@themis/base/native";
import { abspath, isWithin, ntNormpath, pyExists, pyResolve } from "@themis/base/pypath";
import { pidAlive } from "@themis/base/process";
import { publishNew } from "@themis/base/publish";
import { PyCrash, type PyOut, pyFixed, pyRepr, pyRound, pyStrValue, pySum } from "@themis/base/pyfmt";
import { type OutputTarget, runSupervised, superviseWith } from "@themis/base/supervise";
import { ensureArgvSafe } from "@themis/dispatcher/argv";
import { ShlexError, shlexQuote, shlexSplit } from "@themis/base/pyshlex";
import { machineSummary, measuredCheckSeconds, renderInstruction, selfCheckCommand, setupFactsText } from "@themis/dispatcher/instruction";
import { contextEvidence, piPreflight } from "@themis/dispatcher/preflight";
import { compilePatterns, globRegexText, matches, patternError, reEscape } from "@themis/dispatcher/patterns";
import { branchSubject, deriveContractJson, invisibleCharWarnings, validateContract } from "@themis/dispatcher/contract";
import { validatePlan } from "@themis/dispatcher/contract-plan";
import { ambiguityDomainWords, ambiguityMentions, extractReport, interpretationMentions, messageText, reviewHints, summarizeEvents } from "@themis/dispatcher/events";
import { cacheDirCleanup, maskPaths, maskedExitMention, matchExcerpt, outsideMentions, pathForms, protectedMentions, tempDirWithoutCleanup } from "@themis/dispatcher/shell-scan";
import { writeSummary } from "@themis/dispatcher/summary";
import { kernelProtectedPaths } from "@themis/dispatcher/kernel-config";
import { PyOverflowError } from "@themis/base/pyregex";
import { childEnv, listModelsEmptyReason, listModelsLines, listModelsRows, parseHelp, runCapture } from "@themis/dispatcher/pi-cli";
import { DispatchError, Repo } from "@themis/dispatcher/repo";
import { allowedExecutorCheck, loadBindingRecord, resolvePiCommand } from "@themis/dispatcher/executor";
import { pyWhich } from "@themis/base/pyshutil";
import { SequenceMatcher } from "@themis/base/pydifflib";
import { checkAnchors, loadMutationSpec } from "@themis/dispatcher/mutate";
import { ProtocolError, strictJsonLoads } from "@themis/base/protocols";
import { readLocal, runtimeCommand } from "@themis/config/roles-local";
import { resolveRoleExecutor } from "@themis/config/roles-binding";
import { cwdRelativeParts } from "@themis/config/roles-probe";
import { parseIsoUtc } from "@themis/base/pydatetime";
import { PyReError, PyValueError, SearchPatternError, compilePy, compileSearch } from "@themis/base/pyregex";
import {
  type AllowList,
  allowEnum,
  allowEnvName,
  allowId,
  decisionsRedact,
  isSensitive,
  looksLikeSecret,
  normalize,
  redactJson,
  redactObj,
  redactSecrets,
  redactState,
  redactTokens,
  secretLikePaths,
  tokenShaped,
} from "@themis/base/secrets";
import { type DumpsOptions, type PyDict, PyJsonError, type PyValue, dumps, encodeUtf8, floatRepr, intRepr, loads, loadsBytes, rawDecode, unitIndex } from "@themis/base/pyjson";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorType, pyReadBytes, pyReadText } from "@themis/base/pyio";
import { cmpCodePoints, codePoints, pyCasefold, pyIntParse, pyLower, pyNfc, pyStrCount, pyStrFind, pyStrReplace } from "@themis/base/pyre";
import { PyValueError as UrlValueError, ipAddressKind, urlHostname, urlPort, urlUserinfo, urlsplit } from "@themis/base/pyurl";
import { pyEq } from "@themis/base/pyvalue";
import { purePathStr } from "@themis/base/pypath";
import {
  type Battery,
  DecisionError,
  QuestionError,
  type Settings,
  batteryLinkProblem,
  checkQuestion,
  checkQuestions,
  loadBatteries,
  loadBattery,
  reportScreenBattery,
  settingsFromConfig,
  verifyBatteryLock,
} from "@themis/config/decisions";
import { Session, checkAnswer, decisionsSession, describe, httpTransport, probe, usageTotals } from "@themis/config/decisions-client";
import { type HealthTracker, assessRun } from "@themis/dispatcher/run-health";
import {
  PluginError,
  canonicalBytes,
  checkPermissionIntersection,
  digest,
  resolvePlugins,
  validateLock,
  validateManifest,
} from "@themis/config/plugin-records";
import { configErrors } from "@themis/config/roles-check";
import { SecretError, checkName, describeSecret, removeSecret, source } from "@themis/config/secret-store";
import { ConfigError, type Kit, kitAt, loadConfig, pluginsFixHint, pluginsSectionError, pricingTable, validateConfig, worktreeRoot } from "@themis/config/validate";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";

type Request = Record<string, unknown> & { op: string; barrier?: string };
type Result = Record<string, unknown>;

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

/** 并发用例：先报“就绪”，等测试建好起跑文件再一起动手。 */
function waitFor(barrier: string): void {
  process.stderr.write("ready\n");
  const pause = new Int32Array(new SharedArrayBuffer(4));
  while (!existsSync(barrier)) Atomics.wait(pause, 0, 0, 1);
}

/** 请求里的参数用 Python 的名字（ensure_ascii、sort_keys…），换成 TS 的。 */
function dumpsOptions(raw: unknown): DumpsOptions {
  const options = (raw ?? {}) as Record<string, unknown>;
  const out: { -readonly [K in keyof DumpsOptions]: DumpsOptions[K] } = {};
  if ("ensure_ascii" in options) out.ensureAscii = options["ensure_ascii"] as boolean;
  if ("indent" in options) out.indent = options["indent"] as number | null;
  if ("sort_keys" in options) out.sortKeys = options["sort_keys"] as boolean;
  if ("allow_nan" in options) out.allowNan = options["allow_nan"] as boolean;
  if (options["separators"] != null) out.separators = options["separators"] as [string, string];
  return out;
}

function textResult(text: string, encode: unknown): Result {
  return encode ? { ok: true, b64: Buffer.from(encodeUtf8(text)).toString("base64") } : { ok: true, text };
}

function allowList(raw: unknown): AllowList | undefined {
  const items = (raw ?? []) as { path: string[]; check: { kind: string; choices?: Tagged[] } }[];
  if (items.length === 0) return undefined;
  return items.map((item) => {
    const kind = item.check.kind;
    const check = kind === "env_name" ? allowEnvName : kind === "id" ? allowId : allowEnum(...(item.check.choices ?? []).map(fromTagged));
    return [item.path, check] as const;
  });
}

function secretsCall(request: Request): Result {
  const text = String(request["text"] ?? "");
  const value = "value" in request ? fromTagged(request["value"] as Tagged) : null;
  switch (request["fn"]) {
    case "redact_secrets":
      return { ok: true, text: redactSecrets(text) };
    case "redact_tokens":
      return { ok: true, text: redactTokens(text) };
    case "redact_obj":
      return { ok: true, value: toTagged(redactObj(value)) };
    case "redact_json":
      return { ok: true, value: toTagged(redactJson(value, allowList(request["allow"]))) };
    case "secret_like_paths":
      return { ok: true, paths: secretLikePaths(value) };
    case "token_shaped":
      return { ok: true, result: tokenShaped(text) };
    case "looks_like_secret":
      return { ok: true, result: looksLikeSecret(value) };
    case "normalize":
      return { ok: true, text: normalize(text) };
    case "is_sensitive":
      return { ok: true, result: isSensitive(text) };
    case "decisions_redact":
      return { ok: true, text: decisionsRedact(text, Number(request["limit"] ?? 4000)) };
    case "redact_state": {
      const [result, changed] = redactState(value, Number(request["limit"] ?? 6000));
      return { ok: true, value: toTagged(result), changed };
    }
    default:
      return { ok: false, error: "UNKNOWN_FN" };
  }
}

// --- 第 ③ 步：配置中心（与 python_probe.py 同名的 op）---------------------------------

function pluginsCall(request: Request): Result {
  const args = ((request["json_args"] ?? []) as string[]).map((text) => loads(text));
  try {
    switch (request["fn"]) {
      case "validate_manifest":
        return { ok: true, value: toTagged(validateManifest(args[0])) };
      case "validate_lock":
        return { ok: true, value: toTagged(args.length > 1 ? validateLock(args[0], args[1]) : validateLock(args[0])) };
      case "resolve_plugins":
        return { ok: true, value: toTagged(resolvePlugins(args[0], args[1])) };
      case "check_permission_intersection":
        return { ok: true, value: toTagged(checkPermissionIntersection(args[0] as PyValue, args[1] as PyValue, args[2] ?? null)) };
      case "canonical_bytes":
        return { ok: true, b64: Buffer.from(canonicalBytes(args[0] as PyValue)).toString("base64") };
      case "digest":
        return { ok: true, value: toTagged(digest(args[0] as PyValue)) };
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
  } catch (error) {
    if (error instanceof PluginError) return { ok: false, error: "PluginError", message: error.message };
    throw error;
  }
}

function batteryValue(battery: Battery): PyValue {
  return new Map<string, PyValue>([
    ["id", battery.id],
    ["version", battery.version],
    ["description", battery.description],
    ["state_fields", battery.state_fields],
    ["questions", battery.questions],
    ["labels", battery.labels],
    ["thresholds", battery.thresholds],
    ["sha256", battery.sha256],
    ["path", battery.path],
  ]);
}

function settingsValue(settings: Settings): PyValue {
  return new Map<string, PyValue>([
    ["mode", settings.mode],
    ["configured_mode", settings.configured_mode],
    ["reason", settings.reason],
    ["api_key_env", settings.api_key_env],
    ["base_url", settings.base_url],
    ["model", settings.model],
    ["timeout_seconds", settings.timeout_seconds],
    ["budget_seconds", settings.budget_seconds],
    ["max_state_chars", settings.max_state_chars],
    ["points", settings.points],
    ["marker_present", settings.marker_present],
  ]);
}

function decisionsValue(request: Request): PyValue {
  switch (request["fn"]) {
    case "check_question":
      return checkQuestion(String(request["name"]), loads(String(request["question"])));
    case "check_questions":
      return checkQuestions(loads(String(request["questions"])));
    case "load_battery":
      return batteryValue(loadBattery(String(request["path"])));
    case "load_batteries":
      return new Map([...loadBatteries(String(request["root"]))].map(([id, battery]) => [id, batteryValue(battery)]));
    case "verify_battery_lock":
      return verifyBatteryLock(String(request["plugin_dir"]));
    case "settings_from_config": {
      const agentDir = (request["agent_dir"] as string | undefined) || null;
      const pluginDir = (request["plugin_dir"] as string | undefined) || null;
      return settingsValue(settingsFromConfig(loads(String(request["config"])), agentDir, pluginDir));
    }
    case "battery_link_problem":
      return batteryLinkProblem(String(request["kit_root"]), String(request["plugin_dir"]));
    default:
      throw new Error("UNKNOWN_FN");
  }
}

function decisionsCall(request: Request): Result {
  try {
    return { ok: true, value: toTagged(decisionsValue(request)) };
  } catch (error) {
    if (error instanceof DecisionError) return { ok: false, error: "DecisionError", code: error.code, detail: error.detail };
    if (error instanceof QuestionError) return { ok: false, error: "ValueError", message: error.message };
    if (error instanceof PyCrash) return { ok: false, error: error.kind };
    throw error;
  }
}

/** 与 python_probe.op_decisions_client 相同（④b4a）：值按 json.dumps 交回。 */
async function decisionsClient(request: Request): Promise<Result> {
  const text = (value: PyValue): string => dumps(value, { ensureAscii: false });
  const settings = (pluginDir: string | null = null): Settings => settingsFromConfig(loads(String(request["config"])), null, pluginDir);
  const optional = (key: string): string | null => (request[key] ? String(request[key]) : null);
  try {
    switch (request["fn"]) {
      case "transport": {
        const raw = await httpTransport(Buffer.from(String(request["body"]), "base64"), request["headers"] as [string, string][], Number(request["timeout"]), String(request["url"]));
        return { ok: true, raw: raw.toString("base64") };
      }
      case "check_answer":
        return { ok: true, value: text(checkAnswer(String(request["name"]), loads(String(request["question"])) as PyDict, loads(String(request["answer"])))) };
      case "ask": {
        const raw = loads(String(request["battery"])) as PyDict;
        const battery = { id: raw.get("id") as string, version: raw.get("version") as string, sha256: raw.get("sha256") as string, questions: checkQuestions(raw.get("questions")), thresholds: new Map() };
        const session = new Session(settings(), optional("record"));
        const context = request["context"] ? (loads(String(request["context"])) as PyDict) : null;
        const results: PyValue[] = [];
        for (const state of request["states"] as string[]) results.push(await session.ask(battery, loads(state), context));
        return { ok: true, value: text(new Map<string, PyValue>([["results", results], ["calls", BigInt(session.calls)], ["answered", BigInt(session.answered)], ["input_tokens", BigInt(session.inputTokens)]])) };
      }
      case "usage_totals":
        return { ok: true, value: text(usageTotals(loads(String(request["records"])) as PyDict[])) };
      case "describe":
        return { ok: true, value: text(await describe(settings(optional("plugin_dir")), optional("plugin_dir"))) };
      case "probe":
        return { ok: true, value: text(await probe(settings())) };
      case "session": {
        const printed: string[] = [];
        const out = { print: (line = ""): void => void printed.push(`${line}${String.fromCharCode(10)}`) };
        try {
          const session = decisionsSession(loads(String(request["config"])), optional("agent_dir"), optional("record"), optional("point"), { kitRoot: String(request["kit_root"]), out }, Boolean(request["strict"]));
          const value: PyValue = session === null ? null : new Map<string, PyValue>([["mode", session.mode], ["batteries", [...session.batteries.keys()].sort(cmpCodePoints)]]);
          return { ok: true, value: text(value), stdout: printed.join("") };
        } catch (error) {
          if (error instanceof DispatchError) return { ok: false, error: "DispatchError", message: error.message, code: error.code, stdout: printed.join("") };
          throw error;
        }
      }
      case "assess": {
        const out = { print: (): void => undefined };
        const session = decisionsSession(loads(String(request["config"])), null, String(request["record"]), "run-health", { kitRoot: String(request["kit_root"]), out });
        if (session === null) throw new Error("assess 的用例要一个会话");
        const tracker: HealthTracker = {};
        const lines: PyValue[] = [];
        for (let tick = 0; tick < Number(request["ticks"]); tick += 1) lines.push(await assessRun(String(request["run_dir"]), session, tracker));
        const streak = tracker.streak === undefined ? null : new Map([...tracker.streak].map(([key, count]) => [key, BigInt(count)]));
        return { ok: true, value: text(new Map<string, PyValue>([["lines", lines], ["ticks", tracker.ticks === undefined ? null : BigInt(tracker.ticks)], ["streak", streak]])) };
      }
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
  } catch (error) {
    if (error instanceof DecisionError) return { ok: false, error: "DecisionError", code: error.code, detail: error.detail };
    if (error instanceof PyCrash) return { ok: false, error: error.kind };
    if (error instanceof PyJsonError) return { ok: false, error: error.kind === "JSONDecodeError" ? "ValueError" : error.kind };
    throw error;
  }
}

function configValue(request: Request, kit: Kit): PyValue {
  const repo = request["repo"] ? { root: String(request["repo"]), agentDir: join(String(request["repo"]), ".agent") } : null;
  const config = (request["config"] === undefined ? null : loads(String(request["config"]))) as PyDict;
  switch (request["fn"]) {
    case "validate_config":
      return validateConfig(config, repo, kit, request["hints"] !== false);
    case "plugins_fix_hint":
      return pluginsFixHint(config, repo, kit);
    case "plugins_section_error":
      return pluginsSectionError(config);
    case "load_config":
      return loadConfig(repo as NonNullable<typeof repo>);
    case "config_errors":
      return configErrors(config);
    case "pricing_table":
      return pricingTable(config);
    case "worktree_root":
      return worktreeRoot(config, repo as NonNullable<typeof repo>);
    default:
      throw new Error("UNKNOWN_FN");
  }
}

/** 与 python_probe.op_config_call 相同：env 里的变量在这次调用期间设上（null 表示删掉），调用完还原。 */
function configCall(request: Request): Result {
  const env = (request["env"] ?? {}) as Record<string, string | null>;
  const saved = Object.fromEntries(Object.keys(env).map((name) => [name, process.env[name]]));
  for (const [name, value] of Object.entries(env)) {
    if (value === null) delete process.env[name];
    else process.env[name] = value;
  }
  try {
    return { ok: true, value: toTagged(configValue(request, kitAt(String(request["kit_root"])))) };
  } catch (error) {
    if (error instanceof ConfigError) return { ok: false, error: "ConfigError", message: error.message, code: error.code };
    if (error instanceof DispatchError) return { ok: false, error: "DispatchError", message: error.message, code: error.code };
    if (error instanceof PyCrash) return { ok: false, error: error.kind };
    throw error;
  } finally {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

function rolesValue(request: Request): PyValue {
  const repo = request["repo"] ? new Repo(String(request["repo"])) : null;
  const config = (request["config"] !== undefined ? loads(String(request["config"])) : new Map()) as PyDict;
  switch (request["fn"]) {
    case "which":
      return pyWhich(String(request["name"]));
    case "resolve_pi_command":
      return resolvePiCommand();
    case "read_local": {
      const { commands, errors, warnings } = readLocal(repo as Repo, config);
      return new Map<string, PyValue>([["commands", commands], ["errors", errors], ["warnings", warnings]]);
    }
    case "runtime_command": {
      const adapter = request["adapter"] === undefined || request["adapter"] === null ? null : String(request["adapter"]);
      const { command, source, lines } = runtimeCommand(repo as Repo, config, String(request["runtime"]), adapter);
      return new Map<string, PyValue>([["command", command], ["source", source], ["lines", lines]]);
    }
    case "resolve_role_executor": {
      const [value, error] = resolveRoleExecutor(config, request["role"] as PyValue);
      const shownError = error === null ? null : new Map<string, PyValue>([["message", error.message], ["code", BigInt(error.code)]]);
      return new Map<string, PyValue>([["value", value], ["error", shownError]]);
    }
    case "allowed_executor_check": {
      const [provider, model, thinking] = loads(String(request["args"])) as PyValue[];
      return allowedExecutorCheck(config, provider ?? null, model ?? null, thinking ?? null);
    }
    case "load_binding_record":
      return loadBindingRecord((repo as Repo).root, String(request["task"]), BigInt(request["version"] as number));
    default:
      throw new Error("UNKNOWN_FN");
  }
}

/** 与 python_probe.op_roles_call 相同。 */
function rolesCall(request: Request): Result {
  const env = (request["env"] ?? {}) as Record<string, string | null>;
  const saved = Object.fromEntries(Object.keys(env).map((name) => [name, process.env[name]]));
  const cwd = process.cwd();
  for (const [name, value] of Object.entries(env)) {
    if (value === null) delete process.env[name];
    else process.env[name] = value;
  }
  if (request["cwd"]) process.chdir(String(request["cwd"]));
  try {
    return { ok: true, value: toTagged(rolesValue(request)) };
  } catch (error) {
    if (error instanceof DispatchError) return { ok: false, error: "DispatchError", message: error.message, code: error.code };
    if (error instanceof Error && error.message === "UNKNOWN_FN") return { ok: false, error: "UNKNOWN_FN" };
    throw error;
  } finally {
    process.chdir(cwd);
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

/** 与 python_probe.op_secret_store_call 相同。 */
async function secretStoreCall(request: Request): Promise<Result> {
  const env = (request["env"] ?? {}) as Record<string, string | null>;
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  for (const [key, value] of Object.entries(env)) {
    if (value === null) delete process.env[key];
    else process.env[key] = value;
  }
  const name = String(request["name"]);
  try {
    switch (request["fn"]) {
      case "source":
        return { ok: true, value: toTagged(await source(name)) };
      case "describe":
        return { ok: true, value: toTagged(await describeSecret(name)) };
      case "remove":
        return { ok: true, value: toTagged(await removeSecret(name)) };
      case "check_name":
        return { ok: true, value: toTagged(checkName(name)) };
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
  } catch (error) {
    if (error instanceof SecretError) return { ok: false, error: "SecretError", code: error.code, detail: error.detail };
    if (error instanceof PyCrash) return { ok: false, error: error.kind };
    throw error;
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function unicodeCall(request: Request): Result {
  if (request["fn"] === "lower_table") {
    const table: [number, string][] = [];
    for (let cp = 0; cp < 0x110000; cp += 1) {
      if (cp >= 0xd800 && cp <= 0xdfff) continue;
      const char = String.fromCodePoint(cp);
      const lowered = pyLower(char);
      if (lowered !== char) table.push([cp, lowered]);
    }
    return { ok: true, table };
  }
  const text = String(request["text"]);
  if (request["fn"] === "lower") return { ok: true, text: pyLower(text) };
  if (request["fn"] === "casefold") return { ok: true, text: pyCasefold(text) };
  if (request["fn"] === "nfc") return { ok: true, text: pyNfc(text) };
  return { ok: false, error: "UNKNOWN_FN" };
}

function pyioCall(request: Request): Result {
  try {
    if (request["fn"] === "read_text") return { ok: true, text: pyReadText(String(request["path"])) };
    if (request["fn"] === "read_bytes") return { ok: true, b64: pyReadBytes(String(request["path"])).toString("base64") };
    if (request["fn"] === "decode") return { ok: true, text: pyDecodeUtf8(Buffer.from(String(request["b64"]), "base64")) };
  } catch (error) {
    if (error instanceof PyOSError) return { ok: false, error: "OSError", message: error.message };
    if (error instanceof PyUnicodeDecodeError) return { ok: false, error: "UnicodeDecodeError", message: error.message };
    throw error;
  }
  return { ok: false, error: "UNKNOWN_FN" };
}

function pyurlCall(request: Request): Result {
  const text = String(request["text"]);
  if (request["fn"] === "ip_kind") return { ok: true, kind: ipAddressKind(text) };
  try {
    const parts = urlsplit(text);
    const port = urlPort(parts);
    const { username, password } = urlUserinfo(parts);
    return { ok: true, ...parts, port, hostname: urlHostname(parts), username, password };
  } catch (error) {
    if (error instanceof UrlValueError) return { ok: false, error: "ValueError" };
    throw error;
  }
}

const OPS: Record<string, (request: Request) => Result | Promise<Result>> = {
  "plugins.call": pluginsCall,
  "protocols.strict": (request) => {
    try {
      return { ok: true, value: toTagged(strictJsonLoads(Buffer.from(String(request["data_b64"]), "base64"))) };
    } catch (error) {
      if (error instanceof ProtocolError) return { ok: false, error: "ProtocolError", code: error.code };
      throw error;
    }
  },
  "decisions.call": decisionsCall,
  "decisions.client": decisionsClient,
  "config.call": configCall,
  "roles.call": rolesCall,
  "secret_store.call": secretStoreCall,
  "unicode.call": unicodeCall,
  "pyio.call": pyioCall,
  "pyurl.call": pyurlCall,
  "pypath.pure": (request) => ({ ok: true, text: purePathStr(String(request["text"]), ...((request["parts"] ?? []) as string[])) }),
  "pyvalue.eq": (request) => {
    const left = loads(String(request["a"]));
    const right = loads(String(request["b"]));
    return { ok: true, result: request["nested"] ? pyEq([left], [right]) : pyEq(left, right) };
  },
  "secrets.call": secretsCall,
  "jsonl.append": async (request) => {
    const path = join(String(request["repo"]), ".agent", "mailbox", "ledger", "events.jsonl");
    const data = "data" in request ? (fromTagged(request["data"] as Tagged) as PyDict) : new Map();
    const count = Number(request["count"] ?? 1);
    for (let seq = 0; seq < count; seq += 1) {
      const extra: PyDict = new Map(data);
      if (count > 1) extra.set("seq", BigInt(seq));
      await appendEvent(path, String(request["event"]), extra);
    }
    return { ok: true, done_ms: Date.now() };
  },
  "jsonl.read": (request) => ({ ok: true, value: toTagged(readJsonl(String(request["path"]))) }),
  "pyfmt.call": (request) => {
    switch (request["fn"]) {
      case "repr":
        return { ok: true, text: pyRepr(String(request["text"])) };
      case "str":
        return { ok: true, text: pyStrValue(fromTagged(request["value"] as Tagged)) };
      case "sum":
        try {
          return { ok: true, value: toTagged(pySum(fromTagged(request["value"] as Tagged) as PyValue[])) };
        } catch (error) {
          if (error instanceof PyCrash) return { ok: false, error: error.kind };
          throw error;
        }
      case "int": {
        const value = pyIntParse(String(request["text"]));
        return value === null ? { ok: false, error: "ValueError" } : { ok: true, text: value.toString() };
      }
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
  },
  "pydatetime.parse_iso": (request) => ({
    ok: true,
    values: (request["texts"] as string[]).map((text) => parseIsoUtc(text)?.toString() ?? null),
  }),
  "pyregex.search": (request) => {
    let pattern;
    try {
      pattern = compileSearch(String(request["pattern"]));
    } catch (error) {
      if (error instanceof SearchPatternError) return { ok: true, outcome: "error", message: error.message };
      if (error instanceof PyValueError) return { ok: true, outcome: "crash", error: "ValueError" };
      throw error;
    }
    return { ok: true, outcome: "match", hits: (request["texts"] as string[]).map((text) => pattern.test(text)) };
  },
  "pyregex.search_flags": (request) => {
    let pattern;
    try {
      pattern = compilePy(String(request["pattern"]), Number(request["flags"]));
    } catch (error) {
      if (error instanceof PyReError) return { ok: true, outcome: "error", message: error.message };
      if (error instanceof PyValueError) return { ok: true, outcome: "crash", error: "ValueError" };
      if (error instanceof PyOverflowError) return { ok: true, outcome: "crash", error: "OverflowError" };
      throw error;
    }
    return {
      ok: true, outcome: "match",
      spans: (request["texts"] as string[]).map((text) => {
        const found = pattern.search(text);
        return found === null ? null : [found.start, found.end];
      }),
    };
  },
  "jsonl.records": (request) => ({
    ok: true,
    records: [
      ...jsonlRecords(
        String(request["path"]),
        Number(request["start"]),
        Boolean(request["final"]),
        Number(request["limit"] ?? SAFE_MAX_LINE_BYTES),
      ),
    ].map(([start, end, raw]) => [start, end, raw === null ? null : raw.toString("base64")]),
  }),
  "jsonl.iter_lines": (request) => ({ ok: true, lines: [...iterLines(String(request["path"]))] }),
  "jsonl.lines_before": (request) => ({ ok: true, count: linesBefore(String(request["path"]), Number(request["position"])) }),
  // ④a：挂起创建之后、恢复之前，子进程一条指令也不执行（只在 Bun 下：要真的 Win32 调用）。在加入 Job 之前停 1 秒，
  // 记下子进程一启动就写的标记文件这时在不在
  "supervise.suspended_check": async (request) => {
    const api = await winProcessApi();
    const marker = String(request["marker"]);
    let beforeResume: boolean | null = null;
    const wrapped: WinProcessApi = {
      ...api,
      assign: (job, child) => {
        sleepSync(1000);
        beforeResume = existsSync(marker);
        return api.assign(job, child);
      },
    };
    const result = await superviseWith(wrapped, request["cmd"] as string[], {
      cwd: String(request["cwd"]), env: request["env"] as [string, string][], timeout: 30,
      stdout: request["stdout"] as OutputTarget, stderr: request["stderr"] as OutputTarget,
    });
    return { ok: true, before_resume: beforeResume, after: existsSync(marker), result };
  },
  "pyfmt.number": (request) => {
    let value: number | bigint;
    if (typeof request["bits"] === "string") {
      const view = new DataView(new ArrayBuffer(8));
      view.setBigUint64(0, BigInt(`0x${request["bits"]}`));
      value = view.getFloat64(0);
    } else value = BigInt(String(request["int"]));
    const digits = Number(request["digits"]);
    const rounded = pyRound(value, digits);
    return { ok: true, fixed: pyFixed(value, digits), round: typeof rounded === "bigint" ? intRepr(rounded) : floatRepr(rounded) };
  },
  "pypath.call": (request) => {
    const value = String(request["path"]);
    try {
      switch (request["fn"]) {
        case "abspath":
          return { ok: true, value: abspath(value) };
        case "normpath":
          return { ok: true, value: ntNormpath(value) };
        case "resolve":
          return { ok: true, value: pyResolve(purePathStr(value)) };
        case "exists":
          return { ok: true, value: pyExists(purePathStr(value)) };
        case "is_within":
          return { ok: true, value: isWithin(purePathStr(value), purePathStr(String(request["root"]))) };
        default:
          return { ok: false, error: "UNKNOWN_FN" };
      }
    } catch (error) {
      if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
      throw error;
    }
  },
  "events.call": (request) => {
    const text = (key: string): string => String(request[key]);
    try {
      switch (request["fn"]) {
        case "summarize": {
          const [summary, finalText] = summarizeEvents(text("events"), text("work_dir"), fromTagged(request["executor"] as Tagged) as PyDict, {
            stderrPath: request["stderr"] ? text("stderr") : null,
            expectsSettled: (request["expects_settled"] ?? null) as PyValue,
            allowedOutside: (request["allowed_outside"] ?? []) as string[],
            planText: String(request["plan_text"] ?? ""),
            protectedRoots: (request["protected_roots"] ?? []) as string[],
          });
          return { ok: true, summary: toTagged(summary), final_text: finalText };
        }
        case "extract_report":
          return { ok: true, value: toTagged(extractReport(text("text"), text("run_dir"))) };
        case "review_hints":
          return { ok: true, value: toTagged(reviewHints(text("patch"))) };
        case "write_summary": {
          writeSummary(text("run_dir"), new Repo(text("root")), { reportScreen: () => reportScreenBattery(text("kit_root")) });
          return { ok: true };
        }
        case "message_text":
          return { ok: true, value: messageText(fromTagged(request["message"] as Tagged) as PyDict) };
        case "mentions": {
          const message = fromTagged(request["message"] as Tagged) as PyDict;
          const line = request["line"] as number;
          return {
            ok: true,
            ambiguity: toTagged(ambiguityMentions(message, line, (request["skip"] ?? []) as string[])),
            interpretation: toTagged(interpretationMentions(message, line)),
          };
        }
        case "domain_words":
          return { ok: true, value: ambiguityDomainWords(text("text")) };
        case "scan": {
          const command = text("command");
          const scan = maskPaths(command, request["own"] as string[]);
          return {
            ok: true,
            masked: scan,
            protected: protectedMentions(scan, request["protected"] as string[]),
            outside: outsideMentions(scan, request["protected"] as string[]),
            cache: cacheDirCleanup(command),
            exit: maskedExitMention(command),
            leak: tempDirWithoutCleanup(command),
          };
        }
        case "path_forms":
          return { ok: true, value: pathForms(request["paths"] as string[]) };
        case "excerpt":
          return { ok: true, value: matchExcerpt(text("text"), request["start"] as number, request["end"] as number) };
        default:
          return { ok: false, error: "UNKNOWN_FN" };
      }
    } catch (error) {
      if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyJsonError) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyOSError) return { ok: false, error: pyOSErrorType(error), message: error.message };
      if (error instanceof PyUnicodeDecodeError) return { ok: false, error: "UnicodeDecodeError", message: error.message };
      throw error;
    }
  },
  "contract.call": (request) => {
    try {
      switch (request["fn"]) {
        case "derive": {
          const [contract, problems] = deriveContractJson(String(request["md"]), (request["title"] as string | null | undefined) ?? null);
          return { ok: true, contract: toTagged(contract), problems };
        }
        case "validate": {
          const raw = loads(String(request["json_text"]));
          const [contract, errors, warnings] = validateContract(String(request["md"]), raw, String(request["plan_key"]), (request["extra_protected"] as string[] | undefined) ?? []);
          return { ok: true, contract: contract === null ? null : toTagged(contract), errors, warnings };
        }
        case "kernel_protected":
          return { ok: true, value: kernelProtectedPaths(String(request["root"]), String(request["kit_root"]), request["kernel_impl"] as Record<string, string>) };
        case "validate_plan": {
          const ctx = { kitRoot: String(request["kit_root"]), kernelImpl: request["kernel_impl"] as Record<string, string>, roles: { resolveRoleExecutor } };
          const [contract, errors, warnings] = validatePlan(new Repo(String(request["root"])), String(request["plan_key"]), ctx);
          return { ok: true, contract: contract === null ? null : toTagged(contract), errors, warnings };
        }
        case "branch_subject":
          return {
            ok: true,
            value: branchSubject(String(request["task_id"]), loads(String(request["title_json"])), loads(String(request["plan_version_json"])),
              BigInt(request["attempt_no"] as number)),
          };
        case "invisible":
          return { ok: true, value: invisibleCharWarnings(String(request["text"]), String(request["label"])) };
        default:
          return { ok: false, error: "UNKNOWN_FN" };
      }
    } catch (error) {
      if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyJsonError) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyOverflowError) return { ok: false, error: "OverflowError", message: error.message };
      if (error instanceof DispatchError) return { ok: false, error: error.constructor.name, message: error.message };
      if (error instanceof PyOSError) return { ok: false, error: pyOSErrorType(error), message: error.message };
      if (error instanceof PyUnicodeDecodeError) return { ok: false, error: "UnicodeDecodeError", message: error.message };
      throw error;
    }
  },
  "patterns.call": (request) => {
    switch (request["fn"]) {
      case "re_escape":
        return { ok: true, value: reEscape(String(request["text"])) };
      case "glob_text":
        return { ok: true, value: globRegexText(String(request["pattern"])) };
      case "matches": {
        const compiled = compilePatterns(request["patterns"] as string[], Boolean(request["ignore_case"]));
        return { ok: true, value: (request["paths"] as string[]).map((path) => matches(compiled, path)) };
      }
      case "pattern_error":
        return { ok: true, value: patternError(loads(String(request["value_json"]))) };
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
  },
  "pyshlex.split": (request) => {
    try {
      return { ok: true, argv: shlexSplit(String(request["text"])) };
    } catch (error) {
      if (error instanceof ShlexError) return { ok: false, error: "ValueError", message: error.message };
      throw error;
    }
  },
  "argv.ensure_safe": (request) => {
    try {
      ensureArgvSafe(request["cmd"] as string[]);
    } catch (error) {
      if (error instanceof DispatchError) return { ok: false, error: "DispatchError", message: error.message, code: error.code };
      throw error;
    }
    return { ok: true };
  },
  "dispatch.child_env": (request) => {
    const extra = request["extra"] == null ? null : new Map(request["extra"] as [string, string][]);
    const [env, removed] = childEnv(loads(String(request["config_json"])) as PyDict, extra);
    const last = new Map<string, [string, string]>();
    for (const [key, value] of env) {
      last.delete(key.toUpperCase());
      last.set(key.toUpperCase(), [key, value]);
    }
    const byKey = (a: [string, string], b: [string, string]): number => cmpCodePoints(a[0], b[0]) || cmpCodePoints(a[1], b[1]);
    return { ok: true, items: [...env].sort(byKey), effective: [...last.values()].sort(byKey), removed };
  },
  "roles.cwd_relative": (request) => {
    process.chdir(String(request["cwd"]));
    return { ok: true, parts: cwdRelativeParts(request["command"] as string[]) };
  },
  "dispatch.run_capture": async (request) => {
    const env = request["env"] == null ? null : new Map(request["env"] as [string, string][]);
    const [code, stdout, stderr] = await runCapture(request["cmd"] as string[], { cwd: (request["cwd"] as string | null) || null, env, timeout: Number(request["timeout"]) });
    return { ok: true, code, stdout, stderr };
  },
  "dispatch.parse_cli": (request) => {
    const text = String(request["text"]);
    return { ok: true, help: parseHelp(text), lines: listModelsLines(text), rows: listModelsRows(text), empty_reason: listModelsEmptyReason(text) };
  },
  "run.call": async (request) => {
    const tagged = (key: string): PyValue => (request[key] == null ? null : fromTagged(request[key] as Tagged));
    const measured = (): Map<string, bigint> | null => tagged("measured") as Map<string, bigint> | null;
    const strings = (key: string): string[] => (request[key] ?? []) as string[];
    try {
      switch (request["fn"]) {
        case "shlex_quote":
          return { ok: true, value: shlexQuote(String(request["text"])) };
        case "render":
          return { ok: true, value: renderInstruction(tagged("meta"), tagged("contract"), tagged("executor"), tagged("timeout"), strings("extra"), tagged("setup") ?? [], measured()) };
        case "setup_facts":
          return { ok: true, value: setupFactsText(tagged("setup")) };
        case "self_check":
          return { ok: true, value: selfCheckCommand(tagged("check"), strings("tools")) };
        case "machine_summary":
          return { ok: true, value: machineSummary(tagged("contract"), strings("extra"), strings("tools"), measured()) };
        case "measured":
          return { ok: true, value: toTagged(measuredCheckSeconds(String(request["runs"]), tagged("checks"))) };
        case "context_evidence":
          if (request["agent_dir"] == null) delete process.env["PI_CODING_AGENT_DIR"];
          else process.env["PI_CODING_AGENT_DIR"] = String(request["agent_dir"]);
          return { ok: true, value: toTagged(contextEvidence(String(request["work_dir"]), String(request["mode"]))) };
        case "preflight": {
          const env = new Map(request["env"] as [string, string][]);
          return { ok: true, value: toTagged(await piPreflight(strings("pi_cmd"), String(request["cwd"]), tagged("executor"), String(request["out_dir"]), env)) };
        }
        default:
          return { ok: false, error: "UNKNOWN_FN" };
      }
    } catch (error) {
      if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyJsonError) return { ok: false, error: error.kind, message: error.message };
      if (error instanceof PyOSError) return { ok: false, error: pyOSErrorType(error), message: error.message };
      throw error;
    }
  },
  "supervise.run": async (request) => {
    try {
      const result = await runSupervised(request["cmd"] as string[], {
        cwd: String(request["cwd"]),
        env: request["env"] as [string, string][],
        stdout: request["stdout"] as OutputTarget,
        stderr: request["stderr"] as OutputTarget,
        timeout: (request["timeout"] as number | null | undefined) ?? null,
        grace: Number(request["grace"] ?? 15),
        onSpawn: (pid) => void process.stderr.write(`spawned ${pid}\n`),
      });
      return { ok: true, result };
    } catch (error) {
      if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
      throw error;
    }
  },
  "filelock.run": async (request) => {
    const path = String(request["path"]);
    let lock;
    try {
      lock = await acquireFileLock(path, Number(request["wait"] ?? 60));
    } catch (error) {
      if (error instanceof FileLockTimeout) return { ok: false, error: "timeout", message: error.message };
      throw error;
    }
    const acquired = Date.now();
    if (request["signal"]) process.stderr.write("ready\n");
    await new Promise((done) => setTimeout(done, Number(request["hold_ms"] ?? 0)));
    lock.assertHeld();
    const released = Date.now();
    await lock.release();
    return { ok: true, acquired_ms: acquired, released_ms: released };
  },
  publish_new: (request) => ({
    ok: true,
    published: publishNew(String(request["path"]), Buffer.from(String(request["data_b64"]), "base64")),
  }),
  "pyjson.dumps": (request) =>
    textResult(dumps(fromTagged(request["value"] as Tagged), dumpsOptions(request["options"])), request["encode"]),
  "pyjson.loads": (request) => ({ ok: true, value: toTagged(loads(String(request["text"]))) }),
  "mutate.check_anchors": (request) => {
    const tree = pyResolve(String(request["tree"]));
    const results = (request["specs"] as string[]).map((specPath) => {
      const [spec, problems] = loadMutationSpec(specPath);
      if (spec === null) return { problems };
      let text = "";
      const code = checkAnchors(tree, spec, { print: (line = "") => void (text += `${line}${String.fromCharCode(10)}`) } as unknown as PyOut);
      return { code, out: text };
    });
    return { ok: true, results };
  },
  "pystr.call": (request) => {
    // start 与 find 的结果按码点交换：TS 一侧在 UTF-16 下标与码点下标之间换算（超过末尾的部分原样加上）
    const [text, sub] = [String(request["text"]), String(request["sub"])];
    const points = codePoints(text);
    const start = Number(request["start"]);
    const unitStart = points.slice(0, start).join("").length + Math.max(0, start - points.length);
    const at = pyStrFind(text, sub, unitStart);
    return {
      ok: true, find: at === -1 ? -1 : codePoints(text.slice(0, at)).length, count: pyStrCount(text, sub),
      replace: pyStrReplace(text, sub, String(request["new"]), Number(request["limit"])),
    };
  },
  "pydifflib.call": (request) => {
    const matcher = new SequenceMatcher(String(request["a"]), String(request["b"]), request["autojunk"] !== false);
    return { ok: true, ratio: toTagged(matcher.ratio()), blocks: matcher.getMatchingBlocks().map((block) => [...block]), opcodes: matcher.getOpcodes().map((code) => [...code]) };
  },
  "pyjson.loads_bytes": (request) => {
    try {
      return { ok: true, value: toTagged(loadsBytes(Buffer.from(String(request["data"]), "base64"))) };
    } catch (error) {
      if (error instanceof PyJsonError && (error.kind === "ValueError" || error.kind === "JSONDecodeError")) return { ok: false, error: error.kind === "ValueError" ? "decode" : "json" };
      throw error;
    }
  },
  "pyjson.raw_decode": (request) => {
    const text = String(request["text"]);
    const decoded = rawDecode(text, unitIndex(text, Number(request["index"] ?? 0)));
    return { ok: true, value: toTagged(decoded.value), end: decoded.end };
  },
  "fs.read_text": (request) => ({ ok: true, text: readText(String(request["path"])) }),
  "fs.write_text_atomic": (request) => {
    writeTextAtomic(String(request["path"]), String(request["text"]));
    return { ok: true };
  },
  pid_alive: (request) => ({ ok: true, alive: pidAlive(request["pid"] as number | null) }),
  "lock.run": (request) => {
    const wait = Number(request["wait"] ?? 5);
    const lock =
      request["kind"] === "dir"
        ? new DirLock(String(request["path"]), wait)
        : request["kind"] === "task"
          ? new TaskLock(String(request["root"]), String(request["task"]), wait, Number(request["stale"] ?? 300))
          : new ConfigLock(String(request["root"]), wait);
    try {
      lock.acquire();
    } catch (error) {
      // 配置锁的报错文字要与 Python 逐字一致（第 ③b 片），另外两把锁只比较“被占用”
      if (error instanceof LockBusyError) return request["kind"] === "config" ? { ok: false, error: "busy", message: error.message } : { ok: false, error: "busy" };
      throw error;
    }
    const acquired = Date.now();
    const owner = readFileSync(join(lock.path, "owner.json"));
    sleepSync(Number(request["hold_ms"] ?? 0));
    if (request["tamper"]) writeFileSync(join(lock.path, "owner.json"), '{"pid": 1, "token": "someone-else"}\n');
    lock.release();
    return { ok: true, owner_b64: owner.toString("base64"), acquired_ms: acquired, released_ms: Date.now(), left: existsSync(lock.path) };
  },
  "clock.sample": (request) => {
    const senders = request["senders"] as string[];
    const out = {
      utc_now: [] as string[],
      pd_utc_now: [] as string[],
      utc_compact: [] as string[],
      turn_ids: [] as string[],
      audit_ids: [] as string[],
      msg_ids: Object.fromEntries(senders.map((sender) => [sender, [] as string[]])),
    };
    for (let index = 0; index < Number(request["count"] ?? 1); index += 1) {
      out.utc_now.push(utcNow());
      out.pd_utc_now.push(utcNow());
      out.utc_compact.push(utcCompact());
      out.turn_ids.push(newTurnId());
      out.audit_ids.push(auditId());
      for (const sender of senders) out.msg_ids[sender]?.push(newMsgId(sender));
    }
    return { ok: true, ...out, attempt_dirs: (request["attempts"] as number[]).map(attemptDirName) };
  },
  "pyjson.roundtrip": (request) =>
    textResult(dumps(loads(String(request["text"])), dumpsOptions(request["options"])), request["encode"]),
};

async function runOne(request: Request): Promise<Result> {
  if (request.barrier) waitFor(request.barrier);
  const handler = OPS[request.op];
  if (handler === undefined) return { ok: false, error: "UNKNOWN_OP" };
  try {
    return await handler(request);
  } catch (error) {
    if (error instanceof PyJsonError) {
      // pyjson 的报错文字是契约的一部分（Python 会经 str(exc) 写进输出）
      return request.op.startsWith("pyjson.") ? { ok: false, error: error.kind, message: error.message } : { ok: false, error: error.kind };
    }
    if (error instanceof UnicodeDecodeError) return { ok: false, error: "UnicodeDecodeError" };
    return { ok: false, error: (error as NodeJS.ErrnoException).code ?? "EUNKNOWN" };
  }
}

await initFileAttributes(); // 与生产入口一样先绑好原生调用（Bun 下的 GetFullPathNameW 等）
const request = JSON.parse(await readStdin()) as Request;
let result: Result;
if (request.op === "batch") {
  const results: Result[] = [];
  for (const item of request["items"] as Request[]) results.push(await runOne(item));
  result = { ok: true, results };
} else {
  result = await runOne(request);
}
process.stdout.write(JSON.stringify(result));
