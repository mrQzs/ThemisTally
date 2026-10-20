// 外壳示意数据：连接状态与最近仓库列表。这两样不在接口一览（8.9）的信封里，是桌面外壳自己的事
// （架构文档 D10 的宿主接口 window.themisShell），此处用固定值示意。
import type { ConnectionState } from '../components';
import type { MockMode } from './scenario';

export const SHELL_PID = 18244;
export const SHELL_STARTED_AT = '2026-10-18 09:41:07';
export const SHELL_RECENT_REPOS: readonly string[] = ['demo-repo', 'docs-site'];
export const SHELL_STREAM_SUBSCRIBED = '已订阅 /api/v1/events';
export const SHELL_STREAM_DISCONNECTED = '已断开';

/** offline 时连接状态 disconnected，其余 connected（合同第 7 条）。 */
export function shellConnectionState(mock: MockMode): ConnectionState {
  return mock === 'offline' ? 'disconnected' : 'connected';
}

/** 事件流那一行：断开时写「已断开」，否则写「已订阅 /api/v1/events」。 */
export function shellStreamText(state: ConnectionState): string {
  return state === 'disconnected' ? SHELL_STREAM_DISCONNECTED : SHELL_STREAM_SUBSCRIBED;
}
