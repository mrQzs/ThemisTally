// 作业路由（桌面端设计第 7 版 §5.3、D12–D19）：POST /api/v1/jobs（创建）、GET /api/v1/jobs/<id>（查询）、
// POST /api/v1/jobs/<id>/cancel（取消）。六类 kind 都用现成的内核写法（A6/A7），命令行前面由执行器补上 python、
// kernel、--repo 与仓库。严格参数校验：每一类失败都回 400，提示固定、不回显请求里的值、不起子进程。创建成功回 201，
// 创建与查询的正文都是同一个八键作业对象（不套七字段信封、不套 data）。与读路由、eventRoutes 的做法对称，另建一批、
// 不并进 readRoutes()。
import { redactJson, redactSecrets, TASK_ID_RE, type AllowList } from "@themis/base/secrets";
import { errorResponse } from "./envelope.ts";
import { displayArgv, elapsedMsOf, envelopeBody, parseJsonData, timeoutEnvelope, type KernelEnvelope } from "./kernelenvelope.ts";
import { KernelRunner } from "./kernel.ts";
import {
  isTerminal,
  type JobKind,
  type JobRecord,
  JobTable,
  jobView,
  markRunning,
  settle,
} from "./jobs.ts";
import type { Route } from "./routes.ts";

/** record 的格式（内核的 PLAN_KEY_RE：task.vN）。 */
const PLAN_KEY_RE = /^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]{0,3}$/u;
/** pattern 的码点长度上限。 */
const PATTERN_MAX_CODEPOINTS = 512;
/** max 的取值上界。 */
const MAX_MATCHES_LIMIT = 1000;
/** 作业路由的路径前缀（字面量单独放，路由正则由它拼；创建路由精确匹配它，查询/取消在它后面接捕获组）。 */
export const JOBS_PATH = "/api/v1/jobs";

/** 六个作业 kind。 */
export const JOB_KINDS: readonly JobKind[] = ["doctor", "doctor-record", "runtime-scan", "runtime-probe", "models", "search"];

/**
 * JOB_ARGV 登记表（填示例值：record=demo-task.v1、runtime=demo-runtime、task=demo-task、max=50、pattern=token）：
 * 供真内核用例与替身用例逐条对照，写法照 READ_ROUTE_ARGV。位置参数（record 以外的 runtime 等）都由正则保证不以 -
 * 开头；选项的值一律写成 --opt=值；search 的 pattern 是唯一放在 -- 后面的参数。
 */
export const JOB_ARGV: Readonly<Record<JobKind, readonly string[]>> = {
  doctor: ["config", "doctor", "--json"],
  "doctor-record": ["config", "doctor", "--record=demo-task.v1", "--json"],
  "runtime-scan": ["config", "runtime", "scan", "--json"],
  "runtime-probe": ["config", "runtime", "probe", "demo-runtime", "--json"],
  models: ["config", "models", "demo-runtime", "--json"],
  search: ["logs", "search", "--json", "--task=demo-task", "--max=50", "--", "token"],
};

/** 作业时限表（秒；A8：doctor 与 doctor-record 600，其余照表）。 */
export const JOB_TIMEOUTS: Readonly<Record<JobKind, number>> = {
  doctor: 600,
  "doctor-record": 600,
  "runtime-scan": 150,
  "runtime-probe": 150,
  models: 120,
  search: 180,
};

/** 作业结果的白名单：恰好六项、全是 undefined——六类作业的结果一律不登记白名单，一律遮（站主拍板）。 */
export const JOB_ALLOW: Readonly<Record<JobKind, AllowList | undefined>> = {
  doctor: undefined,
  "doctor-record": undefined,
  "runtime-scan": undefined,
  "runtime-probe": undefined,
  models: undefined,
  search: undefined,
};

/** 每个 kind 的必填键与可选键（'kind' 之外）。 */
const SCHEMA: Readonly<Record<JobKind, { readonly required: readonly string[]; readonly optional: readonly string[] }>> = {
  doctor: { required: [], optional: [] },
  "doctor-record": { required: ["record"], optional: [] },
  "runtime-scan": { required: [], optional: [] },
  "runtime-probe": { required: ["runtime"], optional: [] },
  models: { required: ["runtime"], optional: [] },
  search: { required: ["pattern"], optional: ["task", "max"] },
};

/** 提示固定、不回显请求里的值。 */
function badJob(message: string): Response {
  return errorResponse(400, message);
}

/** 没有这个作业：格式不对与不在表里回同一个 404（不泄露作业号在不在）。 */
function jobNotFound(): Response {
  return errorResponse(404, "没有这个作业");
}

/** 取消已结束的作业：409。 */
function jobAlreadyDone(): Response {
  return errorResponse(409, "作业已经结束");
}

/**
 * 取消一个作业（两条取消路由共用）：格式不对或不在表里 404，已终态 409，否则 abort 之后等子进程树结束
 * （await record.exited：六类作业它就是 run，录入作业的子进程一结束就落定，不等重查跑完），回当时的八键作业对象。
 */
export async function cancelJob(table: JobTable, id: string): Promise<Response> {
  const record = table.get(id);
  if (record === null) return jobNotFound();
  if (isTerminal(record.state)) return jobAlreadyDone();
  record.controller.abort(); // 排队中出队、在跑中止信号（整棵树结束）
  await record.exited; // 等它落到 cancelled（录入作业的重查没跑完也回）
  return jobResponse(record, 200);
}

/** 503 带 Retry-After: 2（作业表满、执行器收不了）。 */
function jobRetryLater(message: string): Response {
  const response = errorResponse(503, message);
  response.headers.set("retry-after", "2");
  return response;
}

/** 八键作业对象的 JSON 响应（不套信封）。 */
function jobResponse(record: JobRecord, status: number): Response {
  return new Response(`${JSON.stringify(jobView(record))}\n`, {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

/** pattern：1 到 512 个码点，不含 U+0000–U+001F 与 U+007F，不含孤立的代理项。 */
function validPattern(pattern: unknown): pattern is string {
  if (typeof pattern !== "string") return false;
  const points = [...pattern];
  if (points.length < 1 || points.length > PATTERN_MAX_CODEPOINTS) return false;
  for (const point of points) {
    const code = point.codePointAt(0) ?? 0;
    if (code <= 0x1f || code === 0x7f) return false; // 控制字符
    if (code >= 0xd800 && code <= 0xdfff) return false; // 孤立的代理项
  }
  return true;
}

/** max：1 到 1000 的整数（布尔、小数、字符串都不行）。 */
function validMax(max: unknown): max is number {
  return typeof max === "number" && Number.isInteger(max) && max >= 1 && max <= MAX_MATCHES_LIMIT;
}

/** 校验结果：合格的 kind 与参数，或一句固定提示。 */
type Verdict = { readonly ok: true; readonly kind: JobKind; readonly params: Record<string, unknown> } | { readonly ok: false; readonly message: string };

/** 严格参数校验：正文必须是 JSON 对象、kind 在六个之内、键恰好、类型与取值都合格。 */
function validateJob(body: unknown): Verdict {
  if (typeof body !== "object" || body === null || Array.isArray(body)) return { ok: false, message: "请求体必须是 JSON 对象" };
  const obj = body as Record<string, unknown>;
  const kind = obj["kind"];
  if (typeof kind !== "string" || !JOB_KINDS.includes(kind as JobKind)) return { ok: false, message: "kind 不合法" };
  const schema = SCHEMA[kind as JobKind];
  const allowed = new Set<string>(["kind", ...schema.required, ...schema.optional]);
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) return { ok: false, message: "请求体含有未知键" };
  }
  for (const key of schema.required) {
    if (!(key in obj)) return { ok: false, message: "请求体缺少必填键" };
  }
  const params: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (key === "kind") continue;
    if (key === "record") {
      if (typeof value !== "string" || !PLAN_KEY_RE.test(value)) return { ok: false, message: "record 不合法" };
    } else if (key === "runtime" || key === "task") {
      if (typeof value !== "string" || !TASK_ID_RE.test(value)) return { ok: false, message: `${key} 不合法` };
    } else if (key === "pattern") {
      if (!validPattern(value)) return { ok: false, message: "pattern 不合法" };
    } else if (key === "max") {
      if (!validMax(value)) return { ok: false, message: "max 不合法" };
    }
    params[key] = value;
  }
  return { ok: true, kind: kind as JobKind, params };
}

/** 由校验后的参数拼出交给执行器的 argv（选项的值一律 --opt=值；search 的 pattern 放 -- 之后）。 */
function buildArgv(kind: JobKind, params: Record<string, unknown>): readonly string[] {
  switch (kind) {
    case "doctor":
      return ["config", "doctor", "--json"];
    case "doctor-record":
      return ["config", "doctor", `--record=${String(params["record"])}`, "--json"];
    case "runtime-scan":
      return ["config", "runtime", "scan", "--json"];
    case "runtime-probe":
      return ["config", "runtime", "probe", String(params["runtime"]), "--json"];
    case "models":
      return ["config", "models", String(params["runtime"]), "--json"];
    case "search": {
      const argv = ["logs", "search", "--json"];
      if (typeof params["task"] === "string") argv.push(`--task=${params["task"] as string}`);
      if (typeof params["max"] === "number") argv.push(`--max=${String(params["max"])}`);
      argv.push("--", String(params["pattern"]));
      return argv;
    }
  }
}

/** 服务这一侧出错时的信封（failed 的 reason 对应）：ok=false、exit_code=null、data=null、一行 ERROR。 */
function serviceErrorEnvelope(argv: readonly string[], message: string): Record<string, unknown> {
  return { ok: false, exit_code: null, data: null, output: [], messages: [`ERROR: ${message}`], command: displayArgv(argv), elapsed_ms: 0 };
}

/** messages 只留 stderr 里以 ERROR 或 WARN 开头的行，逐行过 redactSecrets（与读路由同一套二道脱敏）。 */
function jobMessages(stderr: string): string[] {
  const out: string[] = [];
  for (const line of stderr.split(/\r?\n/)) {
    if (line === "") continue;
    if (!line.startsWith("ERROR") && !line.startsWith("WARN")) continue;
    out.push(redactSecrets(line));
  }
  return out;
}

/** 把一次运行的结果落到作业的终态（状态机每一步只走一次）。 */
async function runJob(runner: KernelRunner, record: JobRecord, argv: readonly string[], allow: AllowList | undefined): Promise<void> {
  const outcome = await runner.run(argv, record.timeoutSeconds, record.controller.signal, {
    onStart: () => markRunning(record, Date.now()),
  });
  const now = Date.now();
  if (outcome.kind === "completed") {
    // data 过 redactJson（六类作业的白名单全是 undefined，一律遮敏感键）；command 是显示用的 argv（search 的
    // pattern 也在里面，由 displayArgv 逐项过 redactSecrets）；退出 0 却解析不了 stdout 记 invalid-json。
    const parsed = parseJsonData(outcome.stdout);
    if (parsed === undefined && outcome.result.exit_code === 0) {
      settle(record, "failed", "invalid-json", serviceErrorEnvelope(argv, "内核输出不是合法的 JSON"), now);
    } else {
      const envelope: KernelEnvelope = {
        ok: outcome.result.exit_code === 0,
        exitCode: outcome.result.exit_code,
        data: parsed === undefined ? null : redactJson(parsed, allow),
        messages: jobMessages(outcome.stderr),
        command: displayArgv(argv),
        elapsedMs: elapsedMsOf(outcome.result.wall_seconds),
      };
      const settled = JSON.parse(envelopeBody(envelope)) as Record<string, unknown>;
      settle(record, outcome.result.exit_code === 0 ? "succeeded" : "failed", outcome.result.exit_code === 0 ? null : "exit", settled, now);
    }
  } else if (outcome.kind === "timeout") {
    settle(record, "timed_out", null, JSON.parse(envelopeBody(timeoutEnvelope(argv, record.timeoutSeconds, outcome.result.wall_seconds))) as Record<string, unknown>, now);
  } else if (outcome.kind === "interrupted") {
    // 用户取消（作业自己的 controller 被 abort）：终态 cancelled，信封为 null
    settle(record, "cancelled", null, null, now);
  } else if (outcome.kind === "spawn-error") {
    settle(record, "failed", "spawn-error", serviceErrorEnvelope(argv, "起不了内核子进程"), now);
  } else if (outcome.kind === "output-too-large") {
    settle(record, "failed", "output-too-large", serviceErrorEnvelope(argv, "内核输出超过上限"), now);
  } else {
    // queue-full / closing
    settle(record, "failed", "closing", serviceErrorEnvelope(argv, "服务正在关闭"), now);
  }
}

/** 取消的正文必须是 JSON 对象（可以是空对象）。 */
function isJsonObject(body: unknown): boolean {
  return typeof body === "object" && body !== null && !Array.isArray(body);
}

/**
 * 建作业路由（server.ts 把 readRoutes、eventRoutes、jobRoutes 三批合成一批交给 createApp）。timeouts 是测试入口的
 * 时限覆盖（job.<kind> 作键），CLI 与环境变量碰不到。
 */
export function jobRoutes(runner: KernelRunner, table: JobTable, timeouts: Readonly<Record<string, number>> = {}): readonly Route[] {
  const at = (kind: JobKind): number => timeouts[`job.${kind}`] ?? JOB_TIMEOUTS[kind];
  return [
    {
      name: "api.jobs.create",
      method: "POST",
      pattern: new RegExp(`^${JOBS_PATH}$`, "u"),
      handle: (_state, _params, input) => {
        const verdict = validateJob(input.body);
        if (!verdict.ok) return badJob(verdict.message);
        if (!runner.canAccept()) return jobRetryLater("服务繁忙，请稍后重试"); // 执行器收不了：503，不建作业
        const argv = buildArgv(verdict.kind, verdict.params);
        const timeoutSeconds = at(verdict.kind);
        const record = table.create(verdict.kind, argv, timeoutSeconds, Date.now());
        if (record === null) return jobRetryLater("作业表已满，请稍后重试"); // 没有可淘汰的终态作业：503
        const created = jobResponse(record, 201); // 创建成功的当下 state=queued
        const allow = JOB_ALLOW[verdict.kind];
        record.run = runJob(runner, record, argv, allow); // 后台跑，落到终态
        record.exited = record.run; // 六类作业的 exited 就是 run（取消等它落到终态）
        void record.run;
        return created;
      },
    },
    {
      name: "api.jobs.get",
      method: "GET",
      pattern: new RegExp(`^${JOBS_PATH}/([^/]+)$`, "u"),
      handle: (_state, params) => {
        const id = params[0] ?? "";
        const record = table.get(id);
        if (record === null) return jobNotFound(); // 格式不对与不在表里同一个 404
        return jobResponse(record, 200);
      },
    },
    {
      name: "api.jobs.cancel",
      method: "POST",
      pattern: new RegExp(`^${JOBS_PATH}/([^/]+)/cancel$`, "u"),
      handle: async (_state, params, input) => {
        if (!isJsonObject(input.body)) return badJob("请求体必须是 JSON 对象");
        return await cancelJob(table, params[0] ?? "");
      },
    },
    {
      // 控制取消（U18b）：外壳在凭据小窗口关掉时调它。门只在 app.ts 一处（control: true），这里不读正文、
      // 不做 CSRF、也不再调 control.check；只带对令牌、别的什么都没有也要能取消。
      name: "control.jobs.cancel",
      method: "POST",
      pattern: new RegExp("^/control/jobs/([^/]+)/cancel$", "u"),
      control: true,
      handle: async (_state, params) => await cancelJob(table, params[0] ?? ""),
    },
  ];
}
