// 写配置的预览、确认号与操作终态（桌面端设计第 7 版 §5.3、D6/D13）：POST /api/v1/preview 起基础 argv 加 --dry-run
// --json 跑内核预览，核对 dry_run/action/state/needs_yes，拿掉 state 令牌、过 PREVIEW_ALLOW 脱敏，签发 43 位确认号；
// 七条写路由（role set、preset use|save|remove、config rollback、plugins enable|disable）用同一个 validateWriteArgs 与
// buildWriteArgv，执行是基础 argv 加 --expect-state=<state>（needs_yes 为真才加 --yes），退出 4 转 409 的 stale，结果落进
// 操作表（GET /api/v1/operations/<id> 可查）。profile/runtime 的五条写路由归 T020，本片只登记在 T020_WRITE_COMMANDS。
// 与读路由、jobRoutes 对称，另建一批、不并进 readRoutes()。服务只校验形状，组合规则交给内核；提示固定、不回显请求里的值。
import { redactJson, TASK_ID_RE } from "@themis/base/secrets";
import { type PyDict, type PyKey, type PyValue } from "@themis/base/pyjson";
import { errorResponse } from "./envelope.ts";
import type { Route, RouteInput } from "./routes.ts";
import { KernelRunner } from "./kernel.ts";
import {
  completedResponse,
  displayArgv,
  elapsedMsOf,
  envelopeStatusResponse,
  messagesOf,
  parseJsonData,
  retryLater,
  runResponse,
  timeoutEnvelope,
  type KernelEnvelope,
} from "./kernelenvelope.ts";
import { PREVIEW_ALLOW } from "./redaction.ts";
import { argvMatches, CONFIRMATION_ID_RE, ConfirmationTable } from "./confirmations.ts";
import {
  envelopeRecord,
  markRunning,
  OperationTable,
  operationFull,
  operationView,
  settle,
  writeEnvelope,
  type OperationRecord,
} from "./operations.ts";

/** 预览的时限（秒）。 */
export const PREVIEW_TIMEOUT = 30;
/** 七条写路由共用的时限（秒）。 */
export const WRITE_TIMEOUT = 90;

/** history 编号的形状（内核的 HISTORY_N_RE）：1 到 9 位数字，不以 0 开头。 */
const HISTORY_N_RE = /^[1-9][0-9]{0,8}$/u;
/** 插件 id 的形状（内核的 PLUGIN_ID_RE）：小写字母开头。 */
const PLUGIN_ID_RE = /^[a-z][a-z0-9-]{0,63}$/u;
/** state 令牌的形状（kit_config.py 的 STATE_RE）。 */
const STATE_RE = /^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$/u;

/** role 的取值（kit_roles.py 的 ROLES）。 */
const ROLES = ["planning_review", "contract", "execution", "scheduler_agent"] as const;
/** target 的三个枚举值（其余是过 TASK_ID_RE 的 profile id）。 */
const TARGET_ENUM = ["manual", "disabled", "interactive_host"] as const;
/** host 的两个取值（kit_config.py）。 */
const HOST_ENUM = ["claude-code", "codex"] as const;

/** 提示原文（固定、不回显请求里的值）。 */
const CONFIRM_409_MESSAGE = "确认号无效、已过期或已用过：请重新预览";
const ARGV_409_MESSAGE = "确认号与这次请求的参数不符：请重新预览";
const OPERATION_404_MESSAGE = "没有这个操作";
const PREVIEW_500_MESSAGE = "内核的预览不合格";

/** 一条 action 的必填键与可选键。 */
interface WriteActionSpec {
  readonly required: readonly string[];
  readonly optional: readonly string[];
}

/** 七个写 action 与各自参数的形状（T020 的五条不在这里，请求它们回 400「action 不合法」）。 */
export const WRITE_ACTIONS: Readonly<Record<string, WriteActionSpec>> = {
  "role.set": { required: ["role", "target"], optional: ["host", "cadence_seconds"] },
  "preset.use": { required: ["name"], optional: [] },
  "preset.save": { required: ["name"], optional: ["description", "roles", "force"] },
  "preset.remove": { required: ["name"], optional: [] },
  "config.rollback": { required: ["number"], optional: [] },
  "plugin.enable": { required: ["id"], optional: ["allow_permission"] },
  "plugin.disable": { required: ["id"], optional: [] },
};

/**
 * 七条 action 各一条示例 argv（填示例值：role=execution、target=manual 与 demo-profile、preset=demo-preset、number=1、
 * 插件 id=example-plugin、权限=demo-permission），供真内核与替身用例逐条过内核解析器，写法照 READ_ROUTE_ARGV。位置参数
 * 都由正则保证不以 - 开头；选项的值一律写成 --opt=值；--force 是不取值的开关。
 */
export const WRITE_ARGV: Readonly<Record<string, readonly string[]>> = {
  "role.set": ["config", "role", "set", "execution", "manual"],
  "role.set.profile": ["config", "role", "set", "execution", "demo-profile", "--host=claude-code", "--cadence-seconds=3600"],
  "preset.use": ["config", "preset", "use", "demo-preset"],
  "preset.save": ["config", "preset", "save", "demo-preset", "--description=demo preset", "--roles=contract,execution", "--force"],
  "preset.remove": ["config", "preset", "remove", "demo-preset"],
  "config.rollback": ["config", "rollback", "1"],
  "plugin.enable": ["plugins", "enable", "example-plugin", "--allow-permission=demo-permission"],
  "plugin.disable": ["plugins", "disable", "example-plugin"],
};

/** T020 只登记不实现的五条写命令（profile add|edit|remove、runtime add|remove）；本片不实现，请求回 400。 */
export const T020_WRITE_COMMANDS: readonly (readonly string[])[] = [
  ["config", "profile", "add"],
  ["config", "profile", "edit"],
  ["config", "profile", "remove"],
  ["config", "runtime", "add"],
  ["config", "runtime", "remove"],
];

/** 写路由共用的状态：执行器、确认号表与操作表。 */
export interface WriteRoutesState {
  readonly runner: KernelRunner;
  readonly confirmations: ConfirmationTable;
  readonly operations: OperationTable;
}

/** 校验结果：合格的参数，或一句固定提示。 */
type Verdict = { readonly ok: true; readonly args: Record<string, unknown> } | { readonly ok: false; readonly message: string };

/** 不含控制字符（C0/DEL）与孤立代理项，码点数在 [lo, hi] 之间。 */
function cleanText(value: unknown, lo: number, hi: number): value is string {
  if (typeof value !== "string") return false;
  const points = [...value];
  if (points.length < lo || points.length > hi) return false;
  for (const point of points) {
    const code = point.codePointAt(0) ?? 0;
    if (code <= 0x1f || code === 0x7f) return false;
    if (code >= 0xd800 && code <= 0xdfff) return false;
  }
  return true;
}

/** roles：非空数组、元素互不相同、都在 ROLES 里。 */
function validRoles(value: unknown): boolean {
  if (!Array.isArray(value) || value.length === 0) return false;
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item !== "string" || !(ROLES as readonly string[]).includes(item)) return false;
    if (seen.has(item)) return false;
    seen.add(item);
  }
  return true;
}

/** allow_permission：数组、元素互不相同、每项非空且不超过 256 码点、不含控制字符与孤立代理项。 */
function validAllowPermission(value: unknown): boolean {
  if (!Array.isArray(value)) return false;
  const seen = new Set<string>();
  for (const item of value) {
    if (!cleanText(item, 1, 256)) return false;
    if (seen.has(item as string)) return false;
    seen.add(item as string);
  }
  return true;
}

/** 单个键的取值是否合格（键名已在 WRITE_ACTIONS 里，未知键在此之前已被拒）。 */
function validValue(key: string, value: unknown): boolean {
  if (key === "role") return typeof value === "string" && (ROLES as readonly string[]).includes(value);
  if (key === "target") return typeof value === "string" && ((TARGET_ENUM as readonly string[]).includes(value) || TASK_ID_RE.test(value));
  if (key === "host") return typeof value === "string" && (HOST_ENUM as readonly string[]).includes(value);
  if (key === "cadence_seconds") return typeof value === "number" && Number.isInteger(value) && value >= 60 && value <= 86400;
  if (key === "name") return typeof value === "string" && TASK_ID_RE.test(value);
  if (key === "description") return cleanText(value, 1, 200);
  if (key === "roles") return validRoles(value);
  if (key === "force") return value === true;
  if (key === "number") return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 999999999;
  if (key === "id") return typeof value === "string" && PLUGIN_ID_RE.test(value);
  if (key === "allow_permission") return validAllowPermission(value);
  return false;
}

/**
 * 预览与七条写路由共用的同一个校验函数：正文不是对象 → 400「请求体必须是 JSON 对象」；action 不在登记表里（含 T020 的
 * 五条）→ 400「action 不合法」；args 有未知键 → 400「参数含有未知键」；缺必填键 → 400「参数缺少必填键」；某个值不合格 →
 * 400「<键> 不合法」。提示固定、不回显请求里的值，不合格时不起子进程。
 */
export function validateWriteArgs(action: string, args: unknown): Verdict {
  if (typeof args !== "object" || args === null || Array.isArray(args)) return { ok: false, message: "请求体必须是 JSON 对象" };
  const spec = WRITE_ACTIONS[action];
  if (spec === undefined) return { ok: false, message: "action 不合法" };
  const obj = args as Record<string, unknown>;
  const allowed = new Set<string>([...spec.required, ...spec.optional]);
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) return { ok: false, message: "参数含有未知键" };
  }
  for (const key of spec.required) {
    if (!(key in obj)) return { ok: false, message: "参数缺少必填键" };
  }
  for (const [key, value] of Object.entries(obj)) {
    if (!validValue(key, value)) return { ok: false, message: `${key} 不合法` };
  }
  return { ok: true, args: obj };
}

/** 由校验过的参数拼出基础 argv（选项的值一律 --opt=值；位置参数都由正则保证不以 - 开头）。绝不含 --dry-run/--json/--expect-state/--yes。 */
export function buildWriteArgv(action: string, args: Record<string, unknown>): readonly string[] {
  switch (action) {
    case "role.set": {
      const argv = ["config", "role", "set", String(args["role"]), String(args["target"])];
      if (args["host"] !== undefined) argv.push(`--host=${String(args["host"])}`);
      if (args["cadence_seconds"] !== undefined) argv.push(`--cadence-seconds=${String(args["cadence_seconds"])}`);
      return argv;
    }
    case "preset.use":
      return ["config", "preset", "use", String(args["name"])];
    case "preset.save": {
      const argv = ["config", "preset", "save", String(args["name"])];
      if (args["description"] !== undefined) argv.push(`--description=${String(args["description"])}`);
      if (args["roles"] !== undefined) argv.push(`--roles=${(args["roles"] as string[]).join(",")}`);
      if (args["force"] === true) argv.push("--force");
      return argv;
    }
    case "preset.remove":
      return ["config", "preset", "remove", String(args["name"])];
    case "config.rollback":
      return ["config", "rollback", String(args["number"])];
    case "plugin.enable": {
      const argv = ["plugins", "enable", String(args["id"])];
      for (const permission of (args["allow_permission"] as string[] | undefined) ?? []) argv.push(`--allow-permission=${permission}`);
      return argv;
    }
    case "plugin.disable":
      return ["plugins", "disable", String(args["id"])];
    default:
      return [];
  }
}

/** 一个字面路径的正则（路径里没有元字符，包起来就是精确匹配）。 */
function exact(path: string): RegExp {
  return new RegExp(`^${path.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}$`);
}

/** 服务这一侧出错时的信封：ok=false、exit_code=null、data 与 output 为空、一行 ERROR。 */
function serviceErrorEnvelope(argv: readonly string[], message: string): KernelEnvelope {
  return {
    ok: false,
    exitCode: null,
    data: null,
    output: [],
    messages: [`ERROR: ${message}`],
    command: displayArgv(argv),
    elapsedMs: 0,
  };
}

/** 内核的预览 JSON 是否合格：dry_run 为真、action 与请求相同、state 过形状、needs_yes 是布尔。 */
function checkPreview(parsed: PyDict, action: string): { state: string; needsYes: boolean } | null {
  if (parsed.get("dry_run") !== true) return null;
  if (parsed.get("action") !== action) return null;
  const state = parsed.get("state");
  if (typeof state !== "string" || !STATE_RE.test(state)) return null;
  const needsYes = parsed.get("needs_yes");
  if (typeof needsYes !== "boolean") return null;
  return { state, needsYes };
}

/** 拿掉顶层的 state 令牌（令牌只留在确认号记录里；预览对象里任何层级都不再有 state 键）。 */
function dropState(parsed: PyDict): PyDict {
  const out = new Map<PyKey, PyValue>();
  for (const [key, value] of parsed) {
    if (key === "state") continue;
    out.set(key, value);
  }
  return out;
}

/** 从正文取确认号（正文不是对象时是 undefined）。 */
function confirmationOf(body: unknown): unknown {
  if (typeof body === "object" && body !== null && !Array.isArray(body)) return (body as Record<string, unknown>)["confirmation"];
  return undefined;
}

/** 路径参数与正文（去掉 confirmation）合成 args；路径参数压正文（role/name/id/number 以路径为准）。 */
function mergeArgs(pathArgs: Record<string, unknown>, body: unknown): Record<string, unknown> {
  const args: Record<string, unknown> = {};
  if (typeof body === "object" && body !== null && !Array.isArray(body)) {
    for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
      if (key === "confirmation") continue;
      args[key] = value;
    }
  }
  for (const [key, value] of Object.entries(pathArgs)) args[key] = value;
  return args;
}

/** 预览路由：POST /api/v1/preview。 */
async function previewRoute(state: WriteRoutesState, timeoutSeconds: number, input: RouteInput): Promise<Response> {
  const body = input.body;
  if (typeof body !== "object" || body === null || Array.isArray(body)) return errorResponse(400, "请求体必须是 JSON 对象");
  const obj = body as Record<string, unknown>;
  const action = typeof obj["action"] === "string" ? obj["action"] : "";
  const verdict = validateWriteArgs(action, obj["args"]);
  if (!verdict.ok) return errorResponse(400, verdict.message);
  const baseArgv = buildWriteArgv(action, verdict.args);
  const previewArgv = [...baseArgv, "--dry-run", "--json"];
  const outcome = await state.runner.run(previewArgv, timeoutSeconds, input.request.signal);
  if (outcome.kind !== "completed") return runResponse(previewArgv, outcome, timeoutSeconds);
  if (outcome.result.exit_code !== 0) {
    // 内核退出非 0：回 200、ok 为假、data 尽量解析、messages 带 ERROR 行，不发确认号
    return completedResponse({
      argv: previewArgv,
      exitCode: outcome.result.exit_code,
      wallSeconds: outcome.result.wall_seconds,
      stdout: outcome.stdout,
      stderr: outcome.stderr,
      json: true,
    });
  }
  const parsed = parseJsonData(outcome.stdout);
  if (!(parsed instanceof Map)) return errorResponse(500, PREVIEW_500_MESSAGE);
  const check = checkPreview(parsed, action);
  if (check === null) return errorResponse(500, PREVIEW_500_MESSAGE);
  const redacted = redactJson(dropState(parsed), PREVIEW_ALLOW);
  const confirmation = state.confirmations.issue(action, baseArgv, check.state, check.needsYes);
  const data = new Map<string, PyValue>([
    ["preview", redacted],
    ["confirmation", confirmation.id],
  ]);
  return envelopeStatusResponse(
    {
      ok: true,
      exitCode: 0,
      data,
      messages: messagesOf(outcome.stderr),
      command: displayArgv(previewArgv),
      elapsedMs: elapsedMsOf(outcome.result.wall_seconds),
    },
    200,
  );
}

/** 跑一次写执行：服务私有的 AbortController（永远不 abort），request.signal 不传给它（断开不取消）。 */
async function runWrite(state: WriteRoutesState, op: OperationRecord, runArgv: readonly string[], timeoutSeconds: number): Promise<void> {
  const controller = new AbortController();
  const outcome = await state.runner.run(runArgv, timeoutSeconds, controller.signal, {
    onStart: () => markRunning(op, Date.now()),
  });
  const now = Date.now();
  if (outcome.kind === "completed") {
    const envelope = writeEnvelope(runArgv, outcome);
    const record = envelopeRecord(envelope);
    const exitCode = outcome.result.exit_code;
    if (exitCode === 0) {
      settle(op, "succeeded", null, record, now);
      op.response = envelopeStatusResponse(envelope, 200);
    } else if (exitCode === 4) {
      // 内核报「在预览之后被改过」：409 的七字段信封（界面从 exit_code 认出要重新预览）
      settle(op, "stale", null, record, now);
      op.response = envelopeStatusResponse(envelope, 409);
    } else {
      settle(op, "failed", "exit", record, now);
      op.response = envelopeStatusResponse(envelope, 200);
    }
  } else if (outcome.kind === "timeout") {
    const envelope = timeoutEnvelope(runArgv, timeoutSeconds, outcome.result.wall_seconds);
    settle(op, "timed_out", null, envelopeRecord(envelope), now);
    op.response = envelopeStatusResponse(envelope, 504);
  } else if (outcome.kind === "spawn-error") {
    const envelope = serviceErrorEnvelope(runArgv, "起不了内核子进程");
    settle(op, "failed", "spawn-error", envelopeRecord(envelope), now);
    op.response = envelopeStatusResponse(envelope, 500);
  } else if (outcome.kind === "output-too-large") {
    const envelope = serviceErrorEnvelope(runArgv, "内核输出超过上限");
    settle(op, "failed", "output-too-large", envelopeRecord(envelope), now);
    op.response = envelopeStatusResponse(envelope, 500);
  } else {
    // interrupted（服务关停）/ queue-full / closing
    const envelope = serviceErrorEnvelope(runArgv, "服务正在关闭");
    settle(op, "failed", "closing", envelopeRecord(envelope), now);
    op.response = envelopeStatusResponse(envelope, 503);
  }
}

/** 七条写路由共用的执行链：校验 → 确认号核对 → argv 绑定 → canAccept → 操作表 → 拿号 → 跑。 */
async function executeWrite(
  state: WriteRoutesState,
  action: string,
  args: Record<string, unknown>,
  confirmation: unknown,
  timeoutSeconds: number,
): Promise<Response> {
  const verdict = validateWriteArgs(action, args);
  if (!verdict.ok) return errorResponse(400, verdict.message);
  const argv = buildWriteArgv(action, verdict.args);
  // 确认号缺失、不是字符串、格式不对、不在表里、已过期 → 409（不起子进程）
  if (typeof confirmation !== "string" || !CONFIRMATION_ID_RE.test(confirmation)) return errorResponse(409, CONFIRM_409_MESSAGE);
  const record = state.confirmations.get(confirmation);
  if (record === null) return errorResponse(409, CONFIRM_409_MESSAGE);
  // 基础 argv 与绑定的不同 → 409，不算用掉（不是那条命令）
  if (!argvMatches(record.argv, argv)) return errorResponse(409, ARGV_409_MESSAGE);
  // 队列满或关停中 → 503，不算用掉
  if (!state.runner.canAccept()) return retryLater("服务繁忙，请稍后重试");
  // 先看操作表能不能收（满了且没有可淘汰的终态 → 503，不消耗确认号），能收才拿号入队
  const op = state.operations.create(confirmation, action, argv, timeoutSeconds, Date.now());
  if (op === null) return operationFull();
  state.confirmations.consume(confirmation);
  const runArgv = [...argv, `--expect-state=${record.state}`, ...(record.needsYes ? ["--yes"] : [])];
  op.run = runWrite(state, op, runArgv, timeoutSeconds);
  await op.run;
  return op.response ?? envelopeStatusResponse(serviceErrorEnvelope(runArgv, "服务正在关闭"), 503);
}

/** config.rollback 的路径参数：过 HISTORY_N_RE 再转整数，否则给个过不了校验的值。 */
function rollbackArgs(param: string): Record<string, unknown> {
  return { number: HISTORY_N_RE.test(param) ? Number(param) : Number.NaN };
}

/**
 * 建写路由（server.ts 把 readRoutes、eventRoutes、jobRoutes、writeRoutes 四批合成一批交给 createApp）。timeouts 是测试
 * 入口的时限覆盖（api.preview 与 api.write 作键），CLI 与环境变量碰不到。
 */
export function writeRoutes(state: WriteRoutesState, timeouts: Readonly<Record<string, number>> = {}): readonly Route[] {
  const previewAt = timeouts["api.preview"] ?? PREVIEW_TIMEOUT;
  const writeAt = timeouts["api.write"] ?? WRITE_TIMEOUT;
  const run = (action: string, pathArgs: Record<string, unknown>, input: RouteInput): Promise<Response> =>
    executeWrite(state, action, mergeArgs(pathArgs, input.body), confirmationOf(input.body), writeAt);
  return [
    {
      name: "api.preview",
      method: "POST",
      pattern: exact("/api/v1/preview"),
      handle: (_state, _params, input) => previewRoute(state, previewAt, input),
    },
    {
      name: "api.roles.set",
      method: "POST",
      pattern: /^\/api\/v1\/roles\/([^/]+)$/u,
      handle: (_state, params, input) => run("role.set", { role: params[0] ?? "" }, input),
    },
    {
      name: "api.presets.use",
      method: "POST",
      pattern: /^\/api\/v1\/presets\/([^/]+)\/use$/u,
      handle: (_state, params, input) => run("preset.use", { name: params[0] ?? "" }, input),
    },
    {
      name: "api.presets.save",
      method: "POST",
      pattern: /^\/api\/v1\/presets\/([^/]+)\/save$/u,
      handle: (_state, params, input) => run("preset.save", { name: params[0] ?? "" }, input),
    },
    {
      name: "api.presets.remove",
      method: "POST",
      pattern: /^\/api\/v1\/presets\/([^/]+)\/remove$/u,
      handle: (_state, params, input) => run("preset.remove", { name: params[0] ?? "" }, input),
    },
    {
      name: "api.config.rollback",
      method: "POST",
      pattern: /^\/api\/v1\/config\/rollback\/([^/]+)$/u,
      handle: (_state, params, input) => run("config.rollback", rollbackArgs(params[0] ?? ""), input),
    },
    {
      name: "api.plugins.enable",
      method: "POST",
      pattern: /^\/api\/v1\/plugins\/([^/]+)\/enable$/u,
      handle: (_state, params, input) => run("plugin.enable", { id: params[0] ?? "" }, input),
    },
    {
      name: "api.plugins.disable",
      method: "POST",
      pattern: /^\/api\/v1\/plugins\/([^/]+)\/disable$/u,
      handle: (_state, params, input) => run("plugin.disable", { id: params[0] ?? "" }, input),
    },
    {
      name: "api.operations.get",
      method: "GET",
      pattern: /^\/api\/v1\/operations\/([^/]+)$/u,
      handle: (_state, params) => {
        const record = state.operations.get(params[0] ?? "");
        if (record === null) return errorResponse(404, OPERATION_404_MESSAGE); // 格式不对与不在表里同一个 404
        return new Response(`${JSON.stringify(operationView(record))}\n`, {
          status: 200,
          headers: { "content-type": "application/json; charset=utf-8" },
        });
      },
    },
  ];
}
