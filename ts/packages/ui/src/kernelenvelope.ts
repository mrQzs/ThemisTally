// 内核路由的信封（桌面端设计第 7 版 §5.3、D06）：七个字段与次序照 envelope.ts 的 ENVELOPE_KEYS——
// ok、exit_code、data、output、messages、command、elapsed_ms。读路由不填 output（缺省为空数组，stdout 不原样回传）；
// 写命令（writeroutes.ts）填 stdout 的非空行进 output，逐行过 redactSecrets。messages 只留 stderr 里以 ERROR 或 WARN 开头
// 的行，逐行过 redactSecrets（其余行一律丢掉，例如 logs cat 的「（未完：--cursor …）」）；command 是显示用的 argv（不含 python、kernel、--repo 与仓库路径，--cursor= 的值换成
// <cursor>、--transcript= 的值换成 <transcript>、--expect-state= 的值换成 <state>），再过 redactSecrets；data 用 pyjson 的 dumps(ensureAscii:false,
// indent:2) 写出；exit_code 原样（超时为 null）；elapsed_ms 是 wall_seconds × 1000 取整。写出时七个字段按次序手工
// 拼：data 可能是任意结构，必须走 pyjson（Python 的 NaN、bigint、键次序都与 JSON.stringify 不同）。
import { dumps, loads, type PyValue } from "@themis/base/pyjson";
import { type AllowList, redactJson, redactSecrets } from "@themis/base/secrets";
import { ENVELOPE_KEYS, errorResponse } from "./envelope.ts";
import type { RunOutcome } from "./kernel.ts";

/** 内核信封：data 由路由决定（解析 stdout 或服务合成），其余六项由本文件填。 */
export interface KernelEnvelope {
  readonly ok: boolean;
  readonly exitCode: number | null;
  readonly data: PyValue | null;
  /** stdout 的非空行（逐行过 redactSecrets）：写命令才有，读路由不填（缺省 []）。 */
  readonly output?: readonly string[];
  readonly messages: readonly string[];
  readonly command: readonly string[];
  readonly elapsedMs: number;
}

/** messages 只留这两种前缀开头的行。 */
const MESSAGE_PREFIXES = ["ERROR", "WARN"] as const;

/** stderr 里以 ERROR 或 WARN 开头的行，逐行过 redactSecrets；其余行一律丢掉。 */
export function messagesOf(stderr: string): string[] {
  const out: string[] = [];
  for (const line of stderr.split(/\r?\n/)) {
    if (line === "") continue;
    if (!MESSAGE_PREFIXES.some((prefix) => line.startsWith(prefix))) continue;
    out.push(redactSecrets(line));
  }
  return out;
}

/** 显示用的 argv：游标与 transcript、expect-state 的值换成占位符，每一项再过 redactSecrets。 */
export function displayArgv(argv: readonly string[]): string[] {
  return argv.map((arg) => {
    let shown = arg;
    if (shown.startsWith("--cursor=")) shown = "--cursor=<cursor>";
    else if (shown.startsWith("--transcript=")) shown = "--transcript=<transcript>";
    else if (shown.startsWith("--expect-state=")) shown = "--expect-state=<state>";
    return redactSecrets(shown);
  });
}

/** wall_seconds × 1000 取整。 */
export function elapsedMsOf(wallSeconds: number): number {
  return Math.round(wallSeconds * 1000);
}

/** 解析 stdout 的 JSON：不合法时为 undefined（与 null 区分开：null 也是合法的 JSON）。 */
export function parseJsonData(stdout: string): PyValue | undefined {
  try {
    return loads(stdout);
  } catch {
    return undefined;
  }
}

/** 七字段按次序手工拼；data 走 pyjson 的 dumps（其余六个是标量或字符串数组）；output 缺省 []（读路由不填）。 */
export function envelopeBody(envelope: KernelEnvelope): string {
  const data = envelope.data === null ? "null" : dumps(envelope.data, { ensureAscii: false, indent: 2 });
  const output = dumps([...(envelope.output ?? [])], { ensureAscii: false });
  const messages = dumps([...envelope.messages], { ensureAscii: false });
  const command = dumps([...envelope.command], { ensureAscii: false });
  const exitCode = envelope.exitCode === null ? "null" : String(envelope.exitCode);
  return `{"ok": ${envelope.ok ? "true" : "false"}, "exit_code": ${exitCode}, "data": ${data}, "output": ${output}, "messages": ${messages}, "command": ${command}, "elapsed_ms": ${Math.round(envelope.elapsedMs)}}`;
}

/** 信封转成响应（安全头由调用方的管线套上；这里只给正文与状态）。 */
export function envelopeStatusResponse(envelope: KernelEnvelope, status: number): Response {
  return new Response(`${envelopeBody(envelope)}\n`, {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

/** 超时（504）的信封：ok=false、exit_code=null、command 是显示 argv、messages 只有一行、data 为 null。 */
export function timeoutEnvelope(argv: readonly string[], seconds: number, wallSeconds: number): KernelEnvelope {
  return {
    ok: false,
    exitCode: null,
    data: null,
    messages: [`ERROR: 命令超时（${seconds} 秒），子进程已结束；请改用 CLI 查看`],
    command: displayArgv(argv),
    elapsedMs: elapsedMsOf(wallSeconds),
  };
}

/** 503（队列满或服务正在关闭）：带 Retry-After: 2。安全头由请求管线统一套。 */
export function retryLater(message: string): Response {
  const response = errorResponse(503, message);
  response.headers.set("retry-after", "2");
  return response;
}

/** 一次跑完的运行怎么回：completed 照信封，其余按错误映射（400/409/500/503/504 由路由与本文件分工）。 */
export interface CompletedRun {
  readonly argv: readonly string[];
  readonly exitCode: number | null;
  readonly wallSeconds: number;
  readonly stdout: string;
  readonly stderr: string;
  /** stdout 要解析成 data 吗（--json 的命令与 config secret check）；meta 与合成的 /secrets 给 synthetic。 */
  readonly json: boolean;
  /** 服务合成的 data（给了它就不解析 stdout）。 */
  readonly synthetic?: PyValue | null;
  /** 这一路由登记的白名单（证据路由不登记）。 */
  readonly allow?: AllowList | undefined;
  /** 服务合成的整条路由（合成的 /secrets）：ok 恒 true、command 是空数组。 */
  readonly composed?: boolean;
}

/** 跑完了（退出码可能非 0）：回 200；要 JSON 而退出 0 却解析不了 → 500。 */
export function completedResponse(run: CompletedRun): Response {
  let data: PyValue | null = null;
  if (run.synthetic !== undefined) {
    data = run.synthetic;
  } else if (run.json) {
    const parsed = parseJsonData(run.stdout);
    if (parsed === undefined) {
      if (run.exitCode === 0) return errorResponse(500, "内核输出不是合法的 JSON");
      data = null; // 退出非 0：stdout 不是合法 JSON 时 data 为 null
    } else {
      data = parsed;
    }
  }
  const redacted = data === null ? null : redactJson(data, run.allow);
  return envelopeStatusResponse(
    {
      ok: run.composed === true ? true : run.exitCode === 0,
      exitCode: run.exitCode,
      data: redacted,
      messages: messagesOf(run.stderr),
      command: run.composed === true ? [] : displayArgv(run.argv),
      elapsedMs: elapsedMsOf(run.wallSeconds),
    },
    200,
  );
}

/** 一次 run 的结果怎么回：路由拿到它直接当处理函数的返回值。 */
export function runResponse(argv: readonly string[], outcome: RunOutcome, timeoutSeconds: number): Response {
  switch (outcome.kind) {
    case "closing":
      return retryLater("服务正在关闭");
    case "queue-full":
      return retryLater("服务繁忙，请稍后重试");
    case "spawn-error":
      return errorResponse(500, "起不了内核子进程");
    case "output-too-large":
      return errorResponse(500, "内核输出超过上限");
    case "timeout":
      return envelopeStatusResponse(timeoutEnvelope(argv, timeoutSeconds, outcome.result.wall_seconds), 504);
    case "interrupted":
      // 客户端断开或服务关停：连接已经没了，不再写响应；给一个不带头部的 503 占位
      return errorResponse(503, "请求已取消");
    case "completed":
      return completedResponse({
        argv,
        exitCode: outcome.result.exit_code,
        wallSeconds: outcome.result.wall_seconds,
        stdout: outcome.stdout,
        stderr: outcome.stderr,
        json: true,
      });
  }
}

/** 七个字段的名字（照 envelope.ts；这里再导出一次，方便信封的自查与测试）。 */
export { ENVELOPE_KEYS };

/**
 * status --json 的一次跑完（completed）拼成七字段信封：/api/v1/status 与 SSE 共用这一个函数，保证两条通道的
 * 信封逐字节一致（D03）。退出 0 却解析不了 stdout 时给 invalid-json（调用方回 500，与既有的读路由口径一致）；
 * 退出非 0 时 stdout 不是合法 JSON 就当 data 为 null。data 过 redactJson（status 不登记白名单，一律遮敏感键）。
 */
export function statusEnvelope(
  outcome: Extract<RunOutcome, { kind: "completed" }>,
  argv: readonly string[],
): { readonly kind: "envelope"; readonly envelope: KernelEnvelope } | { readonly kind: "invalid-json" } {
  return completedEnvelope(outcome, argv, undefined);
}

/**
 * 一次跑完（completed）拼成七字段信封：data 解析 stdout 的 JSON 并过 redactJson（allow 是该路由登记的白名单；作业
 * 六类全是 undefined，一律遮）。退出 0 却解析不了 stdout → invalid-json（调用方自行决定回 500 或记 failed）。
 * status 与作业共用这一个函数，脱敏口径只有一套（D03/D19）。
 */
export function completedEnvelope(
  outcome: Extract<RunOutcome, { kind: "completed" }>,
  argv: readonly string[],
  allow: AllowList | undefined,
): { readonly kind: "envelope"; readonly envelope: KernelEnvelope } | { readonly kind: "invalid-json" } {
  const parsed = parseJsonData(outcome.stdout);
  if (parsed === undefined && outcome.result.exit_code === 0) return { kind: "invalid-json" };
  const data = parsed === undefined ? null : redactJson(parsed, allow);
  return {
    kind: "envelope",
    envelope: {
      ok: outcome.result.exit_code === 0,
      exitCode: outcome.result.exit_code,
      data,
      messages: messagesOf(outcome.stderr),
      command: displayArgv(argv),
      elapsedMs: elapsedMsOf(outcome.result.wall_seconds),
    },
  };
}
