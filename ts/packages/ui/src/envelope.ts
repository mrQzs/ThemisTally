// 错误与成功的信封（桌面端设计第 7 版 §5.3）：七个字段、次序固定——ok、exit_code、data、output、messages、
// command、elapsed_ms。服务自己产生的错误（拒绝、超限、内部错误）一律走同一个形状：ok 为 false、exit_code 为
// null、data 为 null、output 与 command 是空数组、messages 只有一行固定的 ERROR: … 文字。第 2、3 片起子进程
// 的路由在这个形状上填 output、command 与 elapsed_ms。
/** 信封的七个字段，次序照合同。 */
export const ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"] as const;

/** 信封：data 的类型由路由决定，这里先当未知。 */
export interface Envelope {
  readonly ok: boolean;
  readonly exit_code: number | null;
  readonly data: unknown;
  readonly output: readonly string[];
  readonly messages: readonly string[];
  readonly command: readonly string[];
  readonly elapsed_ms: number;
}

/** 成功的信封。 */
export function okEnvelope(data: unknown): Envelope {
  return { ok: true, exit_code: null, data, output: [], messages: [], command: [], elapsed_ms: 0 };
}

/** 服务自己产生的错误信封：一行固定的 ERROR: … ，不回显请求里的任何值。 */
export function errorEnvelope(message: string): Envelope {
  return {
    ok: false,
    exit_code: null,
    data: null,
    output: [],
    messages: [`ERROR: ${message}`],
    command: [],
    elapsed_ms: 0,
  };
}

/** 信封转成 JSON 响应（调用方套安全头）。 */
export function envelopeResponse(envelope: Envelope, status = 200): Response {
  return new Response(JSON.stringify(envelope) + "\n", {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

/** 错误信封转成响应。 */
export function errorResponse(status: number, message: string): Response {
  return envelopeResponse(errorEnvelope(message), status);
}
