// 连接状态（合同第 8 步）：初值、变化通知、没变不通知、退订后不再通知，以及 useConnectionState 钩子。
import * as React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  getConnectionState,
  setConnectionState,
  subscribeConnectionState,
  useConnectionState,
} from '../src/live/connection';

function Probe() {
  const state = useConnectionState();
  // 本文件是 .ts（合同的新建清单里没有 .tsx），用 createElement 渲染。
  return React.createElement('span', { 'data-testid': 'tt-live-conn' }, state);
}

describe('live/connection：状态与订阅', () => {
  it('初值是 connected', () => {
    setConnectionState('connected');
    expect(getConnectionState()).toBe('connected');
  });

  it('订阅者：变化时被通知、值没变时不通知、退订后不再通知', () => {
    setConnectionState('connected');
    let calls = 0;
    const off = subscribeConnectionState(() => {
      calls += 1;
    });
    setConnectionState('disconnected');
    expect(calls).toBe(1);
    expect(getConnectionState()).toBe('disconnected');
    setConnectionState('disconnected');
    expect(calls).toBe(1);
    setConnectionState('connected');
    expect(calls).toBe(2);
    off();
    setConnectionState('disconnected');
    expect(calls).toBe(2);
    setConnectionState('connected');
  });

  it('useConnectionState：状态变化时组件跟着重渲染', () => {
    setConnectionState('connected');
    cleanup();
    render(React.createElement(Probe));
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('connected');
    act(() => {
      setConnectionState('disconnected');
    });
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('disconnected');
    act(() => {
      setConnectionState('connected');
    });
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('connected');
    cleanup();
  });
});
