// 连接状态（UI 文档 8.5）：与本机服务的连通情况，供胶囊、横幅与 TabBar 的 offline 状态读。
// 本片只做状态源与订阅，页面接线（胶囊、横幅、TabBar 的 offline 状态）归后面的事件流那一片。
import { useSyncExternalStore } from 'react';

export type ConnectionState = 'connected' | 'disconnected';

let state: ConnectionState = 'connected';
const listeners = new Set<() => void>();

export function getConnectionState(): ConnectionState {
  return state;
}

export function setConnectionState(next: ConnectionState): void {
  if (next === state) return;
  state = next;
  for (const listener of [...listeners]) listener();
}

export function subscribeConnectionState(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useConnectionState(): ConnectionState {
  return useSyncExternalStore(subscribeConnectionState, getConnectionState);
}
