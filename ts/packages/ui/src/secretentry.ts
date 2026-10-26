// 凭据录入作业（桌面端 §5.3、U18/U18b）：POST /api/v1/secrets/<name>/entry 起一个作业跑
// config secret set <name> --no-browser --timeout=600，内核把一次性页面地址以一行 JSON 写到 stderr，本片在子进程
// 还活着的时候从 stderr 读它、严格核对形状，地址只活在这一次请求的局部变量里（不挂到 JobRecord 或任何表上，于是
// 作业查询、SSE、messages/command 与访问日志都拿不到它）。作业表与状态机沿用 jobs.ts 的六种状态、五种 reason，
// 只在 kind 上放宽成 JobKind | "secret-entry"，四张 JOB_* 表一项不动。等握手有上限：到点先 settle 成 timed_out
// 再 abort 子进程（次序反了会先落成 interrupted，被映射改成 cancelled，timed_out 就丢了）。保存之后跑一次
// config secret check 作重查（只在收到过合格握手的作业上做），投影进终态信封的 data：{set, check}。
import { type PyValue } from "@themis/base/pyjson";
import { allowEnvName } from "@themis/base/secrets";
import { errorResponse } from "./envelope.ts";
import { displayArgv, elapsedMsOf, envelopeBody, messagesOf, parseJsonData, timeoutEnvelope, type KernelEnvelope } from "./kernelenvelope.ts";
import { KernelRunner, type RunOutcome } from "./kernel.ts";
import { jobView, markRunning, settle, type JobRecord, JobTable } from "./jobs.ts";
import { secretCheckData } from "./readroutes.ts";
import type { Route } from "./routes.ts";

/** 传给内核的页面等待秒数（--timeout 恒为它，不被测试覆盖项改写）。 */
export const SECRET_ENTRY_PAGE_SECONDS = 600;
/** 作业时限的余量：盖住冷启动、关停 0.5 秒、写库与打结果。 */
export const SECRET_ENTRY_MARGIN_SECONDS = 30;
/** 作业时限（600 + 30）。 */
export const SECRET_ENTRY_JOB_SECONDS = SECRET_ENTRY_PAGE_SECONDS + SECRET_ENTRY_MARGIN_SECONDS;
/** 等握手的上限（从请求到达起算，排队时间算在内）。 */
export const SECRET_ENTRY_HANDSHAKE_SECONDS = 15;
/** 重查 config secret check 的时限。 */
export const SECRET_ENTRY_RECHECK_SECONDS = 30;

/** 录入作业的 argv 登记表（示例名 EXAMPLE_KEY）：不带 --verify、不带 --tty，--timeout 恒为页面时限。 */
export const SECRET_ENTRY_ARGV: readonly string[] = ["config", "secret", "set", "EXAMPLE_KEY", "--no-browser", "--timeout=600"];

/** 一次性页面地址的形状：127.0.0.1 锚定、端口 1 到 5 位数字、令牌恰好 32 个字符（两头锚定、整串匹配）。 */
const PAGE_URL_RE = /^http:\/\/127\.0\.0\.1:(\d{1,5})\/([A-Za-z0-9_-]{32})$/u;
/** 端口数值的合法范围。 */
const PORT_MIN = 1;
const PORT_MAX = 65535;
/** set 的 stdout 白名单：只留这几个键里实际出现的（键序照它），内核恒为 null 的那个键丢掉。 */
const SET_KEYS: readonly string[] = ["name", "stored", "backend", "error"];
/** 服务这一侧出错时的一行 ERROR。 */
const SERVICE_MESSAGES: Readonly<Record<"invalid-json" | "spawn-error" | "output-too-large" | "closing", string>> = {
  "invalid-json": "内核输出不是合法的 JSON",
  "spawn-error": "起不了内核子进程",
  "output-too-large": "内核输出超过上限",
  closing: "服务正在关闭",
};

/** 一次录入的结局：最先发生的那一个（握手到达、N 到点、请求断开、子进程结束），后到的不改变结局。 */
type EntryFinish =
  | { readonly kind: "handshake"; readonly url: string }
  | { readonly kind: "timeout" }
  | { readonly kind: "ended" }
  | { readonly kind: "closing" }
  | { readonly kind: "aborted" };

/** 一次录入作业的共享状态：作业、argv、重查用的新信号、已决标志、握手地址与等结局的 Promise。 */
interface EntryAttempt {
  readonly record: JobRecord;
  readonly argv: readonly string[];
  /** 重查用的新信号（不用作业自己那个可能已经 abort 的信号；执行器的关停与时限另走它自己的路）。 */
  readonly recheckController: AbortController;
  decided: boolean;
  url: string | null;
  readonly finished: Promise<EntryFinish>;
  readonly finish: (outcome: EntryFinish) => void;
}

/** 提示固定、不回显请求里的值。 */
function badEntry(message: string): Response {
  return errorResponse(400, message);
}

/** 503 带 Retry-After: 2（执行器收不了、作业表满）。 */
function retryLater(message: string): Response {
  const response = errorResponse(503, message);
  response.headers.set("retry-after", "2");
  return response;
}

/** {job, url} 的响应（不套七字段信封、不套 data；job 一律是 jobView 的八键）。 */
function entryResponse(record: JobRecord, url: string | null, status: number): Response {
  return new Response(`${JSON.stringify({ job: jobView(record), url })}\n`, {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

/** 录入作业的 argv：位置参数是凭据名，--timeout 恒为页面时限。 */
function entryArgv(name: string): readonly string[] {
  return ["config", "secret", "set", name, "--no-browser", `--timeout=${SECRET_ENTRY_PAGE_SECONDS}`];
}

/** 从 stderr 的全文里找第一条合格的握手行：只看完整的行（以 \r?\n 结尾），逐行 JSON.parse，失败就跳过。 */
function handshakeUrl(text: string): string | null {
  const lines = text.split(/\r?\n/);
  const complete = text.endsWith("\n") ? lines : lines.slice(0, -1); // 最后一段可能还没写完：不当完整行
  for (const line of complete) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      continue;
    }
    if (typeof parsed !== "object" || parsed === null) continue;
    const url = (parsed as Record<string, unknown>)["url"];
    if (typeof url !== "string") continue;
    const matched = PAGE_URL_RE.exec(url);
    if (matched === null) continue;
    const port = Number(matched[1]);
    if (!Number.isInteger(port) || port < PORT_MIN || port > PORT_MAX) continue;
    return url;
  }
  return null;
}

/** set 的 stdout 白名单投影：只留实际出现的键，不透出 stdout 的其它内容。 */
function projectSet(parsed: PyValue): Map<string, PyValue> | null {
  if (!(parsed instanceof Map)) return null;
  const out = new Map<string, PyValue>();
  for (const key of SET_KEYS) {
    if (parsed.has(key)) out.set(key, parsed.get(key) as PyValue);
  }
  return out;
}

/** 终态信封：七字段齐全，data 一律是 {set, check}（Map 构造，键序 set、check）。 */
function entryEnvelope(argv: readonly string[], exitCode: number | null, set: Map<string, PyValue> | null, check: Map<string, PyValue> | null, stderr: string, wallSeconds: number): Record<string, unknown> {
  const envelope: KernelEnvelope = {
    ok: exitCode === 0,
    exitCode,
    data: new Map<string, PyValue>([
      ["set", set],
      ["check", check],
    ]),
    messages: messagesOf(stderr),
    command: displayArgv(argv),
    elapsedMs: elapsedMsOf(wallSeconds),
  };
  return JSON.parse(envelopeBody(envelope)) as Record<string, unknown>;
}

/** 服务这一侧出错时的信封：ok=false、data 是 {set, check}、一行 ERROR（exit_code 由调用方给）。 */
function serviceErrorEnvelope(argv: readonly string[], reason: keyof typeof SERVICE_MESSAGES, check: Map<string, PyValue> | null, exitCode: number | null): Record<string, unknown> {
  const envelope: KernelEnvelope = {
    ok: false,
    exitCode,
    data: new Map<string, PyValue>([
      ["set", null],
      ["check", check],
    ]),
    messages: [`ERROR: ${SERVICE_MESSAGES[reason]}`],
    command: displayArgv(argv),
    elapsedMs: 0,
  };
  return JSON.parse(envelopeBody(envelope)) as Record<string, unknown>;
}

/** 超时（服务一侧时限）的信封：照 timeoutEnvelope，只把 data 换成 {set, check}。 */
function timedOutEnvelope(argv: readonly string[], seconds: number, wallSeconds: number, check: Map<string, PyValue> | null): Record<string, unknown> {
  const envelope: KernelEnvelope = { ...timeoutEnvelope(argv, seconds, wallSeconds), data: new Map<string, PyValue>([["set", null], ["check", check]]) };
  return JSON.parse(envelopeBody(envelope)) as Record<string, unknown>;
}

/** 重查：config secret check <name>（不带 --json），投影用 readroutes 的 secretCheckData（不带 file_dir）。 */
async function recheck(runner: KernelRunner, attempt: EntryAttempt): Promise<Map<string, PyValue> | null> {
  const outcome = await runner.run(["config", "secret", "check", attempt.argv[3] ?? ""], SECRET_ENTRY_RECHECK_SECONDS, attempt.recheckController.signal);
  if (outcome.kind !== "completed") return null;
  if (outcome.result.exit_code !== 0) return null;
  const parsed = parseJsonData(outcome.stdout);
  if (parsed === undefined) return null;
  return secretCheckData(parsed);
}

/** 子进程结束而没有先发生别的事：服务一侧时限、关停、其余（握手之前就结束）三种。 */
function finishOf(outcome: RunOutcome): EntryFinish {
  if (outcome.kind === "timeout") return { kind: "timeout" };
  if (outcome.kind === "closing" || outcome.kind === "queue-full") return { kind: "closing" };
  return { kind: "ended" };
}

/** 跑录入作业：等子进程结束，收到过握手才重查，再按结局落终态（settle 只认第一次）。 */
async function runEntry(runner: KernelRunner, attempt: EntryAttempt): Promise<void> {
  const child = runner.run(attempt.argv, attempt.record.timeoutSeconds, attempt.record.controller.signal, {
    onStart: () => markRunning(attempt.record, Date.now()),
    onStderr: (text) => {
      if (attempt.decided) return; // 同一作业只认第一个事件
      const url = handshakeUrl(text);
      if (url === null) return; // 不合格的行一律忽略，继续等
      attempt.decided = true;
      attempt.url = url;
      attempt.finish({ kind: "handshake", url });
    },
  });
  // 子进程结束就落定（不等重查）：控制取消等它，不等重查跑完
  attempt.record.exited = child.then(() => undefined);
  const outcome = await child;
  if (!attempt.decided) {
    attempt.decided = true;
    attempt.finish(finishOf(outcome));
  }
  // 重查只在收到过合格握手的作业上做（没握手就没人拿到过地址，不可能存进值）
  const check = attempt.url === null ? null : await recheck(runner, attempt);
  const now = Date.now();
  if (outcome.kind === "completed") {
    const exitCode = outcome.result.exit_code;
    const parsed = parseJsonData(outcome.stdout);
    if (parsed === undefined && exitCode === 0) {
      // 退出 0 却解析不了 stdout：exit_code 照实是 0，set 为 null
      settle(attempt.record, "failed", "invalid-json", serviceErrorEnvelope(attempt.argv, "invalid-json", check, 0), now);
      return;
    }
    const set = parsed === undefined ? null : projectSet(parsed);
    settle(attempt.record, exitCode === 0 ? "succeeded" : "failed", exitCode === 0 ? null : "exit", entryEnvelope(attempt.argv, exitCode, set, check, outcome.stderr, outcome.result.wall_seconds), now);
    return;
  }
  if (outcome.kind === "timeout") {
    settle(attempt.record, "timed_out", null, timedOutEnvelope(attempt.argv, attempt.record.timeoutSeconds, outcome.result.wall_seconds, check), now);
    return;
  }
  if (outcome.kind === "interrupted") {
    // 取消或客户端断开：终态 cancelled，信封照写（收到过握手才有 check）
    const envelope = entryEnvelope(attempt.argv, null, null, check, "", (now - attempt.record.created_ms) / 1000);
    settle(attempt.record, "cancelled", null, envelope, now);
    return;
  }
  if (outcome.kind === "spawn-error") {
    settle(attempt.record, "failed", "spawn-error", serviceErrorEnvelope(attempt.argv, "spawn-error", check, null), now);
    return;
  }
  if (outcome.kind === "output-too-large") {
    settle(attempt.record, "failed", "output-too-large", serviceErrorEnvelope(attempt.argv, "output-too-large", check, null), now);
    return;
  }
  // queue-full / closing：重查跑不了，check 为 null
  settle(attempt.record, "failed", "closing", serviceErrorEnvelope(attempt.argv, "closing", null, null), now);
}

/** 等握手到点：先 settle 成 timed_out 再 abort 子进程（次序反了会先落成 interrupted，timed_out 就丢了）。 */
function handshakeDeadline(attempt: EntryAttempt, seconds: number): void {
  const started = Date.now();
  const timer = setTimeout(() => {
    if (attempt.decided) return;
    attempt.decided = true;
    const now = Date.now();
    settle(attempt.record, "timed_out", null, timedOutEnvelope(attempt.argv, attempt.record.timeoutSeconds, (now - started) / 1000, null), now);
    attempt.record.controller.abort(); // 排队中出队、在跑整棵树结束（宽限 2 秒）
    attempt.finish({ kind: "timeout" });
  }, seconds * 1000);
  timer.unref?.();
}

/**
 * 建录入路由（server.ts 把它同时并进 extraRoutes 与 kernelAnsweredRoutes：entry 要等握手 N 秒，必须在放宽空闲超时
 * 的那一批里）。timeouts 是测试入口的时限覆盖（job.secret-entry 与 secret-entry.handshake），argv 里的
 * --timeout=600 不可覆盖；CLI 与环境变量碰不到。
 */
export function secretEntryRoutes(runner: KernelRunner, jobs: JobTable, timeouts: Readonly<Record<string, number>> = {}): readonly Route[] {
  const jobSeconds = timeouts["job.secret-entry"] ?? SECRET_ENTRY_JOB_SECONDS;
  const handshakeSeconds = timeouts["secret-entry.handshake"] ?? SECRET_ENTRY_HANDSHAKE_SECONDS;
  return [
    {
      name: "api.secrets.entry",
      method: "POST",
      pattern: /^\/api\/v1\/secrets\/([^/]+)\/entry$/u,
      handle: async (_state, params, input) => {
        const body = input.body;
        if (typeof body !== "object" || body === null || Array.isArray(body)) return badEntry("请求体必须是 JSON 对象");
        if (Object.keys(body).length > 0) return badEntry("请求体含有未知键");
        const name = params[0] ?? "";
        if (!allowEnvName(name)) return badEntry("凭据名不合法");
        if (!runner.canAccept()) return retryLater("服务繁忙，请稍后重试"); // 执行器收不了：503，不建作业
        const argv = entryArgv(name);
        const record = jobs.create("secret-entry", argv, jobSeconds, Date.now());
        if (record === null) return retryLater("作业表已满，请稍后重试"); // 没有可淘汰的终态作业：503
        let finish: (outcome: EntryFinish) => void = () => {};
        const finished = new Promise<EntryFinish>((resolve) => {
          finish = resolve;
        });
        const attempt: EntryAttempt = {
          record,
          argv,
          recheckController: new AbortController(),
          decided: false,
          url: null,
          finished,
          finish,
        };
        record.run = runEntry(runner, attempt); // 后台跑，落到终态
        // 客户端断开：握手还没到就结束作业（终态 cancelled）、不回响应；握手已经到了作业就继续跑（页面还开着）
        const onRequestAbort = (): void => {
          if (attempt.decided) return;
          attempt.decided = true;
          attempt.record.controller.abort();
          attempt.finish({ kind: "aborted" });
        };
        if (input.request.signal.aborted) onRequestAbort();
        else input.request.signal.addEventListener("abort", onRequestAbort, { once: true });
        handshakeDeadline(attempt, handshakeSeconds);
        const outcome = await attempt.finished;
        if (outcome.kind === "handshake") return entryResponse(record, outcome.url, 201);
        if (outcome.kind === "aborted") return errorResponse(503, "请求已取消"); // 客户端已走：不再写响应
        await record.run; // 等作业落到终态之后再回
        if (outcome.kind === "timeout") return entryResponse(record, null, 504);
        if (outcome.kind === "closing") return entryResponse(record, null, 503);
        return entryResponse(record, null, 502);
      },
    },
  ];
}
