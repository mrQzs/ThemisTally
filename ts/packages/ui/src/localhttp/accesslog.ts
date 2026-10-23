// 访问记录（桌面端设计第 7 版 §5.2、T7b）：只记路由名、状态码与耗时，只存在内存里，进程结束即丢。路由名不符合
// ^[a-z][a-z0-9.-]*$ 的一律记成 invalid-route-name——含 nonce 的引导地址、请求正文、cookie 都进不了记录，
// 令牌不会从日志流出去。
/** 内存里最多留多少条。 */
export const ACCESS_LOG_MAX = 1000;

/** 路由名的形状：小写字母开头，之后是小写字母、数字、点与连字符。 */
export const ROUTE_NAME_RE = /^[a-z][a-z0-9.-]*$/;

/** 一条记录：只有三项。 */
export interface AccessEntry {
  readonly route: string;
  readonly status: number;
  readonly ms: number;
}

/** 环形的内存记录：超出 ACCESS_LOG_MAX 就丢最旧的。 */
export class AccessLog {
  private readonly items: AccessEntry[] = [];

  private readonly max: number;

  constructor(max: number = ACCESS_LOG_MAX) {
    this.max = max;
  }

  /** 记一条；路由名不像名字时记成 invalid-route-name。 */
  record(route: string, status: number, ms: number): void {
    this.items.push({ route: ROUTE_NAME_RE.test(route) ? route : "invalid-route-name", status, ms });
    while (this.items.length > this.max) this.items.shift();
  }

  /** 副本（调用方改不动里面）。 */
  entries(): readonly AccessEntry[] {
    return [...this.items];
  }
}
