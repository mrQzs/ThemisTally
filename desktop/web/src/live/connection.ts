// 连接状态（UI 文档 8.5）：与本机服务的连通情况，供胶囊、横幅与 TabBar 的 offline 状态读。
// reconnecting 由事件流那一片写入：断线自己排重连的等待期。重连次数同属事件流，UI 只从这里读。
import { useSyncExternalStore } from 'react';

export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

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

let reconnects = 0;
const reconnectListeners = new Set<() => void>();

export function getReconnectCount(): number {
  return reconnects;
}

export function setReconnectCount(next: number): void {
  if (next === reconnects) return;
  reconnects = next;
  for (const listener of [...reconnectListeners]) listener();
}

export function subscribeReconnectCount(listener: () => void): () => void {
  reconnectListeners.add(listener);
  return () => {
    reconnectListeners.delete(listener);
  };
}
