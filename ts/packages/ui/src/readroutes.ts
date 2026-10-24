// 19 条只读数据路由（桌面端设计第 7 版 §5.3、D05/D11/D12/D13）：每条起一个内核子进程跑只读 CLI，全部 GET、全部要
// 会话（T17），查询参数与路径参数在起子进程之前校验，不合格回 400。命令行是 [python, kernel, "--repo", repo, ...argv]
// （组装在 kernel.ts），argv 是列表、不经 shell；选项的值一律写成 --opt=值；所有位置参数都由正则保证不以 - 开头。
// 响应先过 redactJson，再按路由登记的白名单做约束校验（redaction.ts）；file 路由给界面的是随机不透明句柄，内核
// 游标只存在服务内存里（cursors.ts）。合成的 /secrets 先跑 config show 与 config profile show 收名单，再逐条串行跑
// config secret check（每条 30 秒、整条 120 秒），任何一条失败就停下并回那一条子命令的信封。
import { basename } from "node:path";
import { dumps, type PyValue } from "@themis/base/pyjson";
import { ENV_NAME_RE, TASK_ID_RE, type AllowList, allowEnvName } from "@themis/base/secrets";
import { errorResponse } from "./envelope.ts";
import type { Route, RouteInput } from "./routes.ts";
import { CursorTable, validHandle } from "./cursors.ts";
import type { RunKernel, RunOutcome } from "./kernel.ts";
import {
  completedResponse,
  envelopeStatusResponse,
  parseJsonData,
  runResponse,
  timeoutEnvelope,
} from "./kernelenvelope.ts";
import { CONFIG_ALLOW, EVIDENCE_ALLOW, PROFILES_ALLOW, SECRETS_ALLOW, SECRET_SHOW_ALLOW } from "./redaction.ts";

/** meta 的时限（秒）。 */
export const META_TIMEOUT = 15;
/** 一般读路由的时限（秒）。 */
export const DEFAULT_TIMEOUT = 30;
/** file 路由（证据分页）的时限（秒）。 */
export const FILE_TIMEOUT = 60;
/** usage 路由的时限（秒）。 */
export const USAGE_TIMEOUT = 120;
/** 合成的 /secrets 里每一条 config secret check 的时限（秒）。 */
export const SECRET_ITEM_TIMEOUT = 30;
/** 合成的 /secrets 整条路由的时限（秒）。 */
export const SECRETS_TOTAL_TIMEOUT = 120;

/** attempt 目录名：attempt- 加至少三位编号（内核的 ATTEMPT_DIR_RE）。 */
const ATTEMPT_RE = /^attempt-[0-9]{3,}$/u;
/** history 的编号：1 到 9 位数字，不以 0 开头。 */
const HISTORY_N_RE = /^[1-9][0-9]{0,8}$/u;
/** 插件 id（内核的 PLUGIN_ID_RE）。 */
const PLUGIN_ID_RE = /^[a-z][a-z0-9-]{0,63}$/u;
/** 控制字符（含 NUL）。 */
const CONTROL_CHAR_RE = /[\u0000-\u001f\u007f]/u;
/** 内核报游标失效时的提示（stderr 里含它）。 */
export const STALE_CURSOR_TEXT = "游标对应的文件已变化";
/** file 路由 409 的提示原文。 */
export const CURSOR_409_MESSAGE = "游标无效或文件已变化，请从头读取";
/** 证据路径的长度上限（字符）。 */
const PATH_MAX_CHARS = 1024;

/** 读路由共用的状态：仓库、执行器、句柄表与用量路由的会话记录。 */
export interface ReadRoutesState {
  readonly repo: string;
  readonly runner: RunKernel;
  readonly cursors: CursorTable;
  readonly transcript: readonly string[];
}

/** 一条读路由的登记项（名字、示例路径、时限）：测试与被锁定的用例逐条对照用。 */
export interface ReadRouteSpec {
  readonly name: string;
  readonly path: string;
  readonly timeoutSeconds: number;
}

/** 19 条读路由的登记表：一条不多、一条不少（顺序即路由表顺序）。 */
export const READ_ROUTE_SPECS: readonly ReadRouteSpec[] = [
  { name: "api.meta.get", path: "/api/v1/meta", timeoutSeconds: META_TIMEOUT },
  { name: "api.status.get", path: "/api/v1/status", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.attempts.list", path: "/api/v1/attempts", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.attempts.show", path: "/api/v1/attempts/demo-task/attempt-001", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.attempts.file", path: "/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt", timeoutSeconds: FILE_TIMEOUT },
  { name: "api.usage.get", path: "/api/v1/usage", timeoutSeconds: USAGE_TIMEOUT },
  { name: "api.config.get", path: "/api/v1/config", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.config.validate", path: "/api/v1/config/validate", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.config.history.list", path: "/api/v1/config/history", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.config.history.show", path: "/api/v1/config/history/1", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.roles.get", path: "/api/v1/roles", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.profiles.get", path: "/api/v1/profiles", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.presets.list", path: "/api/v1/presets", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.presets.diff", path: "/api/v1/presets/base/diff/alt", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.runtimes.get", path: "/api/v1/runtimes", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.plugins.list", path: "/api/v1/plugins", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.plugins.show", path: "/api/v1/plugins/example-plugin", timeoutSeconds: DEFAULT_TIMEOUT },
  { name: "api.secrets.list", path: "/api/v1/secrets", timeoutSeconds: SECRETS_TOTAL_TIMEOUT },
  { name: "api.secrets.show", path: "/api/v1/secrets/EXAMPLE_KEY", timeoutSeconds: DEFAULT_TIMEOUT },
];

/**
 * 每条读路由的 argv 模板（示例参数填在里头）：真内核的 argv-templates 用例拿它逐条过内核真正的解析器，
 * kernel-runner 用例核对处理器实际交出的 argv 与它一致（ drift 会被用例抓住）。示例值——task=demo-task、
 * attempt=attempt-001、path=a/b.txt、history 编号=1、方案名=base 与 alt、插件 id=example-plugin、
 * 凭据名=EXAMPLE_KEY、游标=fake-cursor-0001、会话记录=transcript.jsonl。
 */
export const READ_ROUTE_ARGV: Readonly<Record<string, readonly string[]>> = {
  "api.meta.get": ["--version"],
  "api.status.get": ["status", "--json"],
  "api.attempts.list": ["logs", "list", "--json"],
  "api.attempts.list.task": ["logs", "list", "--json", "--task=demo-task"],
  "api.attempts.show": ["logs", "show", "demo-task/attempt-001", "--json"],
  "api.attempts.file": ["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json"],
  "api.attempts.file.cursor": ["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json", "--cursor=fake-cursor-0001"],
  "api.usage.get": ["logs", "usage", "--json", "--transcript=transcript.jsonl"],
  "api.config.get": ["config", "show", "--json"],
  "api.config.validate": ["config", "validate", "--json"],
  "api.config.history.list": ["config", "history", "--json"],
  "api.config.history.show": ["config", "history", "show", "1", "--json"],
  "api.roles.get": ["config", "role", "show", "--json"],
  "api.profiles.get": ["config", "profile", "show", "--json"],
  "api.presets.list": ["config", "preset", "list", "--json"],
  "api.presets.diff": ["config", "preset", "diff", "base", "alt", "--json"],
  "api.runtimes.get": ["config", "runtime", "list", "--json"],
  "api.plugins.list": ["plugins", "list", "--json"],
  "api.plugins.show": ["plugins", "show", "example-plugin", "--json"],
  "api.secrets.list": ["config", "show", "--json"],
  "api.secrets.list.profiles": ["config", "profile", "show", "--json"],
  "api.secrets.list.check": ["config", "secret", "check", "EXAMPLE_KEY"],
  "api.secrets.show": ["config", "secret", "check", "EXAMPLE_KEY"],
};

/** 一个字面路径的正则（路径里没有元字符，包起来就是精确匹配）。 */
function exact(path: string): RegExp {
  return new RegExp(`^${path.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}$`);
}

/** 参数不合格：400，不起子进程（提示不给攻击者反馈，不回显请求里的值）。 */
function badParam(message: string): Response {
  return errorResponse(400, message);
}

/** file 路由的 409：句柄无效或文件已变化（提示同一句）。 */
function cursorConflict(): Response {
  return errorResponse(409, CURSOR_409_MESSAGE);
}

/** 证据路径：1 到 1024 个字符，不以 - 或 / 开头，不含控制字符与反斜杠。 */
function validPath(path: string): boolean {
  const length = [...path].length;
  if (length < 1 || length > PATH_MAX_CHARS) return false;
  if (path.startsWith("-") || path.startsWith("/")) return false;
  return !CONTROL_CHAR_RE.test(path) && !path.includes("\\");
}

/** 一条普通的 --json 路由：跑完照信封回（退出非 0 也回 200）。 */
async function jsonRoute(
  state: ReadRoutesState,
  argv: readonly string[],
  timeoutSeconds: number,
  input: RouteInput,
  allow: AllowList | undefined,
): Promise<Response> {
  const outcome = await state.runner.run(argv, timeoutSeconds, input.request.signal);
  if (outcome.kind !== "completed") return runResponse(argv, outcome, timeoutSeconds);
  return completedResponse({
    argv,
    exitCode: outcome.result.exit_code,
    wallSeconds: outcome.result.wall_seconds,
    stdout: outcome.stdout,
    stderr: outcome.stderr,
    json: true,
    allow,
  });
}

/** config secret check 的一行 JSON → {name, source, store_mode, system_backend}（不带 file_dir）。 */
function secretCheckData(parsed: PyValue): Map<string, PyValue> | null {
  if (!(parsed instanceof Map)) return null;
  const out = new Map<string, PyValue>();
  for (const key of ["name", "source", "store_mode", "system_backend"]) {
    if (parsed.has(key)) out.set(key, parsed.get(key) as PyValue);
  }
  return out;
}

/** config secret check 的响应（/secrets/<name> 与合成 /secrets 里逐条失败时共用）。 */
function secretCheckResponse(argv: readonly string[], outcome: Extract<RunOutcome, { kind: "completed" }>, timeoutSeconds: number): Response {
  const parsed = parseJsonData(outcome.stdout);
  let data: PyValue | null = null;
  if (parsed === undefined) {
    if (outcome.result.exit_code === 0) return errorResponse(500, "内核输出不是合法的 JSON");
  } else {
    data = secretCheckData(parsed);
  }
  return completedResponse({
    argv,
    exitCode: outcome.result.exit_code,
    wallSeconds: outcome.result.wall_seconds,
    stdout: outcome.stdout,
    stderr: outcome.stderr,
    json: false,
    synthetic: data,
    allow: SECRET_SHOW_ALLOW,
  });
}

/** 合成 /secrets 用的收集命令：跑完给出解析后的 data，或直接给出该回的响应。 */
type Collected = { readonly ok: true; readonly data: PyValue } | { readonly ok: false; readonly response: Response };

async function collect(state: ReadRoutesState, argv: readonly string[], signal: AbortSignal): Promise<Collected> {
  const outcome = await state.runner.run(argv, SECRET_ITEM_TIMEOUT, signal);
  if (outcome.kind !== "completed") return { ok: false, response: runResponse(argv, outcome, SECRET_ITEM_TIMEOUT) };
  const parsed = parseJsonData(outcome.stdout);
  if (parsed === undefined) {
    if (outcome.result.exit_code === 0) return { ok: false, response: errorResponse(500, "内核输出不是合法的 JSON") };
    return {
      ok: false,
      response: completedResponse({
        argv,
        exitCode: outcome.result.exit_code,
        wallSeconds: outcome.result.wall_seconds,
        stdout: outcome.stdout,
        stderr: outcome.stderr,
        json: true,
      }),
    };
  }
  return { ok: true, data: parsed };
}

/** 合成 /secrets：先收名单（decisions 在前，再按 profile 次序），再逐条串行跑 config secret check。 */
async function secretsListRoute(state: ReadRoutesState, input: RouteInput): Promise<Response> {
  const signal = input.request.signal;
  const started = Date.now();
  const deadline = started + SECRETS_TOTAL_TIMEOUT * 1000;
  const showArgv = ["config", "show", "--json"];
  const show = await collect(state, showArgv, signal);
  if (!show.ok) return show.response;
  const profileArgv = ["config", "profile", "show", "--json"];
  const profiles = await collect(state, profileArgv, signal);
  if (!profiles.ok) return profiles.response;

  // 名单：decisions 的名字在前，再按 profile 在 config profile show 里的次序收集 credential_env 的名字；
  // 只收过 allowEnvName 的名字，去重且保持出现次序。used_by 随收集一起记下。
  const order: string[] = [];
  const usedBy = new Map<string, PyValue[]>();
  const addUse = (name: string, entry: PyValue): void => {
    let list = usedBy.get(name);
    if (list === undefined) {
      list = [];
      usedBy.set(name, list);
      order.push(name);
    }
    // 同一个名字在两个位置都出现时只记一次（decisions 一条、每个 profile 一条）
    if (list.some((item) => dumps(item, { ensureAscii: false }) === dumps(entry, { ensureAscii: false }))) return;
    list.push(entry);
  };
  // 名单的第一处：config show 的决策摘要（decisions.env_var_name；摘要报错时退回 keys 里的
  // decisions.api_key_env——内核的 config show --json 两个位置都带这把 key 的名字）
  const decisions = show.data instanceof Map ? show.data.get("decisions") : undefined;
  const summaryName = decisions instanceof Map ? decisions.get("env_var_name") : undefined;
  if (typeof summaryName === "string" && allowEnvName(summaryName)) {
    addUse(summaryName, new Map<string, PyValue>([["kind", "decisions"]]));
  }
  const keyRows = show.data instanceof Map ? show.data.get("keys") : undefined;
  if (Array.isArray(keyRows)) {
    for (const row of keyRows) {
      if (!(row instanceof Map) || row.get("key") !== "decisions") continue;
      const value = row.get("value");
      const raw = value instanceof Map ? value.get("api_key_env") : undefined;
      if (typeof raw === "string" && allowEnvName(raw)) {
        addUse(raw, new Map<string, PyValue>([["kind", "decisions"]]));
      }
    }
  }
  const profileRows = profiles.data instanceof Map ? profiles.data.get("profiles") : undefined;
  if (Array.isArray(profileRows)) {
    for (const profile of profileRows) {
      if (!(profile instanceof Map)) continue;
      const id = profile.get("id");
      if (typeof id !== "string") continue;
      const names = profile.get("credential_env");
      if (!Array.isArray(names)) continue;
      for (const name of names) {
        if (typeof name !== "string" || !allowEnvName(name)) continue;
        addUse(name, new Map<string, PyValue>([["kind", "profile"], ["id", id]]));
      }
    }
  }

  const items: PyValue[] = [];
  for (const name of order) {
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) {
      // 整条超时：504，N 是整条路由的时限
      const argv = ["config", "secret", "check", name];
      return envelopeStatusResponse(
        timeoutEnvelope(argv, SECRETS_TOTAL_TIMEOUT, (Date.now() - started) / 1000),
        504,
      );
    }
    const seconds = Math.min(SECRET_ITEM_TIMEOUT, Math.max(0.001, remainingMs / 1000));
    const argv = ["config", "secret", "check", name];
    const outcome = await state.runner.run(argv, seconds, signal);
    if (outcome.kind !== "completed") return runResponse(argv, outcome, Math.ceil(seconds));
    if (outcome.result.exit_code !== 0) return secretCheckResponse(argv, outcome, Math.ceil(seconds));
    const parsed = parseJsonData(outcome.stdout);
    if (parsed === undefined) return errorResponse(500, "内核输出不是合法的 JSON");
    const base = secretCheckData(parsed);
    if (base === null) return errorResponse(500, "内核输出不是合法的 JSON");
    const item = new Map<string, PyValue>(base);
    item.set("used_by", usedBy.get(name) ?? []);
    items.push(item);
  }
  const data = new Map<string, PyValue>([["secrets", items]]);
  return completedResponse({
    argv: [],
    exitCode: 0,
    wallSeconds: (Date.now() - started) / 1000,
    stdout: "",
    stderr: "",
    json: false,
    synthetic: data,
    allow: SECRETS_ALLOW,
    composed: true,
  });
}

/** meta 的 data 由服务合成：{version, repo_name}。 */
async function metaRoute(state: ReadRoutesState, timeoutSeconds: number, input: RouteInput): Promise<Response> {
  const argv = ["--version"];
  const outcome = await state.runner.run(argv, timeoutSeconds, input.request.signal);
  if (outcome.kind !== "completed") return runResponse(argv, outcome, timeoutSeconds);
  const version = outcome.stdout.replace(/\r?\n$/u, "");
  const data = new Map<string, PyValue>([
    ["version", version],
    ["repo_name", basename(state.repo)],
  ]);
  return completedResponse({
    argv,
    exitCode: outcome.result.exit_code,
    wallSeconds: outcome.result.wall_seconds,
    stdout: outcome.stdout,
    stderr: outcome.stderr,
    json: false,
    synthetic: data,
  });
}

/** file 路由：证据分页；next_cursor 换成句柄，内核游标只在服务内存里。 */
async function fileRoute(state: ReadRoutesState, timeoutSeconds: number, params: readonly string[], input: RouteInput): Promise<Response> {
  const task = params[0] ?? "";
  const attempt = params[1] ?? "";
  const url = new URL(input.request.url);
  const path = url.searchParams.get("path") ?? "";
  const handle = url.searchParams.get("cursor");
  if (!TASK_ID_RE.test(task)) return badParam("任务 ID 不合法");
  if (!ATTEMPT_RE.test(attempt)) return badParam("attempt 编号不合法");
  if (!validPath(path)) return badParam("证据路径不合法");
  let cursor: string | null = null;
  if (handle !== null) {
    // 句柄格式不对、不在表里、绑定与本次请求不一致：409，不起子进程
    if (!validHandle(handle)) return cursorConflict();
    const binding = state.cursors.take(handle);
    if (binding === null) return cursorConflict();
    if (binding.task !== task || binding.attempt !== attempt || binding.path !== path) return cursorConflict();
    cursor = binding.cursor;
  }
  const argv = ["logs", "cat", `${task}/${attempt}`, path, "--json", ...(cursor === null ? [] : [`--cursor=${cursor}`])];
  const outcome = await state.runner.run(argv, timeoutSeconds, input.request.signal);
  if (outcome.kind !== "completed") return runResponse(argv, outcome, timeoutSeconds);
  if (handle !== null && outcome.result.exit_code === 2 && outcome.stderr.includes(STALE_CURSOR_TEXT)) {
    state.cursors.drop(handle); // 内核报「游标对应的文件已变化」：丢掉这个句柄
    return cursorConflict();
  }
  const parsed = parseJsonData(outcome.stdout);
  if (parsed === undefined) {
    if (outcome.result.exit_code === 0) return errorResponse(500, "内核输出不是合法的 JSON");
    return completedResponse({
      argv,
      exitCode: outcome.result.exit_code,
      wallSeconds: outcome.result.wall_seconds,
      stdout: outcome.stdout,
      stderr: outcome.stderr,
      json: false,
      synthetic: null,
      allow: EVIDENCE_ALLOW,
    });
  }
  const data = withHandle(state, task, attempt, path, parsed);
  return completedResponse({
    argv,
    exitCode: outcome.result.exit_code,
    wallSeconds: outcome.result.wall_seconds,
    stdout: outcome.stdout,
    stderr: outcome.stderr,
    json: false,
    synthetic: data,
    allow: EVIDENCE_ALLOW,
  });
}

/** 一页证据：next_cursor 换成句柄（没有下一页时是 null），其余字段原样。 */
function withHandle(state: ReadRoutesState, task: string, attempt: string, path: string, page: PyValue): PyValue {
  if (!(page instanceof Map)) return page;
  const next = page.get("next_cursor");
  const handle = typeof next === "string" && next !== "" ? state.cursors.issue({ task, attempt, path, cursor: next }) : null;
  const out = new Map<string, PyValue>();
  for (const [key, value] of page) out.set(typeof key === "string" ? key : String(key), value);
  out.set("next_cursor", handle);
  return out;
}

/**
 * 建 19 条读路由（server.ts 把它们接进 createApp 的 extraRoutes）。timeouts 是测试入口的时限覆盖
 * （路由名 → 秒），CLI 与环境变量碰不到。
 */
export function readRoutes(state: ReadRoutesState, timeouts: Readonly<Record<string, number>> = {}): readonly Route[] {
  const at = (name: string, fallback: number): number => timeouts[name] ?? fallback;
  return [
    {
      name: "api.meta.get",
      method: "GET",
      pattern: exact("/api/v1/meta"),
      handle: (_state, _params, input) => metaRoute(state, at("api.meta.get", META_TIMEOUT), input),
    },
    {
      name: "api.status.get",
      method: "GET",
      pattern: exact("/api/v1/status"),
      handle: (_state, _params, input) => jsonRoute(state, ["status", "--json"], at("api.status.get", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.attempts.list",
      method: "GET",
      pattern: exact("/api/v1/attempts"),
      handle: async (_state, _params, input) => {
        const task = new URL(input.request.url).searchParams.get("task");
        if (task !== null && !TASK_ID_RE.test(task)) return badParam("任务 ID 不合法");
        const argv = ["logs", "list", "--json", ...(task === null ? [] : [`--task=${task}`])];
        return jsonRoute(state, argv, at("api.attempts.list", DEFAULT_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.attempts.show",
      method: "GET",
      pattern: /^\/api\/v1\/attempts\/([^/]+)\/([^/]+)$/u,
      handle: async (_state, params, input) => {
        const task = params[0] ?? "";
        const attempt = params[1] ?? "";
        if (!TASK_ID_RE.test(task)) return badParam("任务 ID 不合法");
        if (!ATTEMPT_RE.test(attempt)) return badParam("attempt 编号不合法");
        const argv = ["logs", "show", `${task}/${attempt}`, "--json"];
        return jsonRoute(state, argv, at("api.attempts.show", DEFAULT_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.attempts.file",
      method: "GET",
      pattern: /^\/api\/v1\/attempts\/([^/]+)\/([^/]+)\/file$/u,
      handle: (_state, params, input) => fileRoute(state, at("api.attempts.file", FILE_TIMEOUT), params, input),
    },
    {
      name: "api.usage.get",
      method: "GET",
      pattern: exact("/api/v1/usage"),
      handle: (_state, _params, input) => {
        const argv = ["logs", "usage", "--json", ...state.transcript.map((item) => `--transcript=${item}`)];
        return jsonRoute(state, argv, at("api.usage.get", USAGE_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.config.get",
      method: "GET",
      pattern: exact("/api/v1/config"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "show", "--json"], at("api.config.get", DEFAULT_TIMEOUT), input, CONFIG_ALLOW),
    },
    {
      name: "api.config.validate",
      method: "GET",
      pattern: exact("/api/v1/config/validate"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "validate", "--json"], at("api.config.validate", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.config.history.list",
      method: "GET",
      pattern: exact("/api/v1/config/history"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "history", "--json"], at("api.config.history.list", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.config.history.show",
      method: "GET",
      pattern: /^\/api\/v1\/config\/history\/([^/]+)$/u,
      handle: async (_state, params, input) => {
        const n = params[0] ?? "";
        if (!HISTORY_N_RE.test(n)) return badParam("历史编号不合法");
        const argv = ["config", "history", "show", n, "--json"];
        return jsonRoute(state, argv, at("api.config.history.show", DEFAULT_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.roles.get",
      method: "GET",
      pattern: exact("/api/v1/roles"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "role", "show", "--json"], at("api.roles.get", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.profiles.get",
      method: "GET",
      pattern: exact("/api/v1/profiles"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "profile", "show", "--json"], at("api.profiles.get", DEFAULT_TIMEOUT), input, PROFILES_ALLOW),
    },
    {
      name: "api.presets.list",
      method: "GET",
      pattern: exact("/api/v1/presets"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "preset", "list", "--json"], at("api.presets.list", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.presets.diff",
      method: "GET",
      pattern: /^\/api\/v1\/presets\/([^/]+)\/diff\/([^/]+)$/u,
      handle: async (_state, params, input) => {
        const a = params[0] ?? "";
        const b = params[1] ?? "";
        if (!TASK_ID_RE.test(a) || !TASK_ID_RE.test(b)) return badParam("方案名不合法");
        const argv = ["config", "preset", "diff", a, b, "--json"];
        return jsonRoute(state, argv, at("api.presets.diff", DEFAULT_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.runtimes.get",
      method: "GET",
      pattern: exact("/api/v1/runtimes"),
      handle: (_state, _params, input) => jsonRoute(state, ["config", "runtime", "list", "--json"], at("api.runtimes.get", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.plugins.list",
      method: "GET",
      pattern: exact("/api/v1/plugins"),
      handle: (_state, _params, input) => jsonRoute(state, ["plugins", "list", "--json"], at("api.plugins.list", DEFAULT_TIMEOUT), input, undefined),
    },
    {
      name: "api.plugins.show",
      method: "GET",
      pattern: /^\/api\/v1\/plugins\/([^/]+)$/u,
      handle: async (_state, params, input) => {
        const id = params[0] ?? "";
        if (!PLUGIN_ID_RE.test(id)) return badParam("插件 ID 不合法");
        const argv = ["plugins", "show", id, "--json"];
        return jsonRoute(state, argv, at("api.plugins.show", DEFAULT_TIMEOUT), input, undefined);
      },
    },
    {
      name: "api.secrets.list",
      method: "GET",
      pattern: exact("/api/v1/secrets"),
      handle: (_state, _params, input) => secretsListRoute(state, input),
    },
    {
      name: "api.secrets.show",
      method: "GET",
      pattern: /^\/api\/v1\/secrets\/([^/]+)$/u,
      handle: async (_state, params, input) => {
        const name = params[0] ?? "";
        if (!ENV_NAME_RE.test(name)) return badParam("凭据名不合法");
        const argv = ["config", "secret", "check", name];
        const timeoutSeconds = at("api.secrets.show", DEFAULT_TIMEOUT);
        const outcome = await state.runner.run(argv, timeoutSeconds, input.request.signal);
        if (outcome.kind !== "completed") return runResponse(argv, outcome, timeoutSeconds);
        return secretCheckResponse(argv, outcome, timeoutSeconds);
      },
    },
  ];
}
