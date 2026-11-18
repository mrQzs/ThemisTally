// 运行模式与读函数的取数门槛：生产构建（vite build）走真实服务，dev server 与 vitest 走夹具。
// 开关是 vite.config.ts 的构建期常量 __THEMIS_LIVE_MODE__（只跟 command 走，不跟 NODE_ENV 走）；
// 真实模式的缺省客户端由传输层 createLiveClient() 建（懒建，模块加载时不碰 window）。
import { createLiveClient } from './transport';
import type { Envelope } from '../api';

declare const __THEMIS_LIVE_MODE__: string | undefined;

const BUILD_MODE = typeof __THEMIS_LIVE_MODE__ === 'string' ? __THEMIS_LIVE_MODE__ : 'unknown';

export type LiveClient = {
  get<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>>;
  // 写路由：状态码原样返回，拿不到回应时 reject（写流程靠状态码分类）。
  post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }>;
  // 读原始 JSON（操作终态）：不归成信封，正文原样交回。
  getRaw<T>(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }>;
  // 写原始 JSON（作业对象不是信封）：POST 形状照 post，状态码与正文原样交回，拿不到回应时 reject。
  postRaw<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: T }>;
};

let injected: LiveClient | null | undefined;
let defaultClient: LiveClient | null = null;

export function liveModeIsReal(): boolean {
  return BUILD_MODE === 'themis-live-real';
}

export function liveClient(): LiveClient | null {
  if (injected !== undefined) return injected;
  if (!liveModeIsReal()) return null;
  if (defaultClient === null) defaultClient = createLiveClient();
  return defaultClient;
}

export function setLiveClientForTests(client: LiveClient | null | undefined): void {
  injected = client;
}
