// 路由表（桌面端设计第 7 版 §5.2、§5.3）：本片只登记四条——一次性引导地址、控制接口的换引导地址、ping 的读与写。
// 第 2、3 片在这张表上加数据路由（meta、status、jobs、SSE），不改这里的形状。路由名是小写点分（api.ping.get），
// 访问记录只记名字，所以 nonce、令牌、正文都进不了日志（T7b）。
import { bootstrapAccepted, bootstrapRejected, type BootstrapNonces, type Sessions } from "./localhttp/session.ts";
import { ControlGate } from "./localhttp/control.ts";
import { errorResponse, envelopeResponse, okEnvelope } from "./envelope.ts";

/** 引导地址的路径模式：nonce 是 base64url，1 到 128 个字符。 */
export const BOOTSTRAP_PATTERN = "^/bootstrap/([A-Za-z0-9_-]{1,128})$";
export const BOOTSTRAP_RE = new RegExp(BOOTSTRAP_PATTERN);
/** 控制接口的路径。 */
export const CONTROL_PATH = "/control/bootstrap";
/** ping 的路径（读与写同一条）。 */
export const PING_PATH = "/api/v1/ping";

/** 路由之间共享的状态：会话、nonce、控制令牌门与那个只在内存里的计数。 */
export interface RouteState {
  /** 本机服务的源，http://127.0.0.1:<port>。 */
  readonly origin: string;
  readonly sessions: Sessions;
  readonly nonces: BootstrapNonces;
  readonly control: ControlGate;
  /** ping 的计数：用来证明 CSRF 被拒时处理函数没有运行。 */
  readonly posts: { value: number };
}

/** 一次派发：请求本身加 POST 时解析过的 JSON 正文（GET 时是 undefined）。 */
export interface RouteInput {
  readonly request: Request;
  readonly body: unknown;
}

export interface Route {
  readonly name: string;
  readonly method: "GET" | "POST";
  readonly pattern: RegExp;
  /** 一次性引导地址与控制接口不验会话（外壳拿它们换会话）；其余路由一律要会话（T17：默认必须验证）。 */
  readonly public?: true;
  readonly handle: (state: RouteState, params: readonly string[], input: RouteInput) => Response | Promise<Response>;
}

export interface RouteMatch {
  readonly route: Route;
  readonly params: readonly string[];
}

/** 一个字面路径的正则（路径里没有元字符，包起来就是精确匹配）。 */
function literal(path: string): RegExp {
  return new RegExp(`^${path.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}$`);
}

/** 本片的四条路由。 */
export const ROUTES: readonly Route[] = [
  {
    name: "bootstrap",
    method: "GET",
    pattern: BOOTSTRAP_RE,
    public: true, // 一次性引导地址：拿它换会话，本身不要会话（T17）
    handle: (state, params) => {
      const nonce = params[0] ?? "";
      if (!state.nonces.consume(nonce)) return bootstrapRejected();
      return bootstrapAccepted(state.sessions.create());
    },
  },
  {
    name: "control.bootstrap",
    method: "POST",
    pattern: literal(CONTROL_PATH),
    public: true, // 控制接口：门是穷举的（Host、Origin、控制令牌），不看会话（T17）
    handle: (state, _params, input) => {
      const verdict = state.control.check(input.request.headers);
      if (!verdict.ok) {
        if (verdict.status === 429) {
          const response = errorResponse(429, "控制令牌失败次数过多");
          response.headers.set("retry-after", String(verdict.retryAfterSeconds));
          return response;
        }
        return errorResponse(403, "请求被拒绝");
      }
      state.sessions.revokeAll();
      state.nonces.revokeAll();
      return envelopeResponse(okEnvelope({ bootstrap: `${state.origin}/bootstrap/${state.nonces.issue()}` }));
    },
  },
  {
    name: "api.ping.get",
    method: "GET",
    pattern: literal(PING_PATH),
    handle: (state) => envelopeResponse(okEnvelope({ posts: state.posts.value })),
  },
  {
    name: "api.ping.post",
    method: "POST",
    pattern: literal(PING_PATH),
    handle: (state, _params, input) => {
      const value = input.body;
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        return errorResponse(400, "请求体必须是 JSON 对象");
      }
      state.posts.value += 1;
      return envelopeResponse(okEnvelope({ posts: state.posts.value }));
    },
  },
];

/** 找路由：方法加路径都要对上；params 是正则的捕获组。 */
export function findRoute(method: string, pathname: string, extra: readonly Route[] = []): RouteMatch | null {
  for (const route of [...ROUTES, ...extra]) {
    if (route.method !== method) continue;
    const matched = route.pattern.exec(pathname);
    if (matched === null) continue;
    return { route, params: matched.slice(1) };
  }
  return null;
}
