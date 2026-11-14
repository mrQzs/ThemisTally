// 真实模式下的底部实时预览（T040 第 2 片）：只经 setLiveClientForTests 注入假服务，断言打在真实的
// useLivePreview 与真实的 api.ts 上——300ms 防抖、命令去掉 --dry-run 与 --json、400 信封显示 messages
// 原文、post reject 显示「预览失败：服务没有回应」。
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, PreviewData } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { useLivePreview } from '../src/writes/useLivePreview';

interface PostCall {
  path: string;
  body: unknown;
  timeoutSeconds: number | undefined;
}

const posts: PostCall[] = [];
let postReply: { status: number; body: Envelope<PreviewData> } | null = null;
let postError: Error | null = null;

function envelope<T>(data: T, command: string[]): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

function failEnvelope(messages: string[]): Envelope<PreviewData> {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const fake: LiveClient = {
  get() {
    return Promise.resolve(envelope(null, []));
  },
  post(path: string, body: unknown, timeoutSeconds?: number) {
    posts.push({ path, body, timeoutSeconds });
    return postError ? Promise.reject(postError) : Promise.resolve(postReply as { status: number; body: Envelope<PreviewData> });
  },
  getRaw() {
    return Promise.resolve({ status: 404, body: null });
  },
};

const ARGS = { profile: 'p1', runtime: 'r', model: 'm' };

async function settlePreview() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(301);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  posts.length = 0;
  postReply = null;
  postError = null;
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('useLivePreview 真实模式（注入假服务）', () => {
  it('300ms 防抖：299ms 不发，到 300ms 恰好发一次 POST /api/v1/preview；命令去掉两个开关', async () => {
    postReply = {
      status: 200,
      body: envelope(
        { preview: { dry_run: true }, confirmation: 'c1' },
        ['config', 'profile', 'add', 'p1', '--dry-run', '--json'],
      ),
    };
    const { result } = renderHook(() => useLivePreview('profile.add', ARGS, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(299);
    });
    expect(posts.length, '299ms 时还没有预览请求').toBe(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(posts.length, '300ms 时恰好发一次').toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'profile.add', args: ARGS });
    expect(posts[0].timeoutSeconds).toBe(30);
    expect(result.current.current).toBe(true);
    expect(result.current.result?.command).toEqual(['config', 'profile', 'add', 'p1']);
  });

  it('400 错误信封：错误行显示 messages 原文，不算成功', async () => {
    postReply = { status: 400, body: failEnvelope(['ERROR: model 不在 pi --list-models 的列表里']) };
    const { result } = renderHook(() => useLivePreview('profile.add', ARGS, true));
    await settlePreview();
    expect(posts.length).toBe(1);
    expect(result.current.result?.ok).toBe(false);
    expect(result.current.result?.error).toBe('ERROR: model 不在 pi --list-models 的列表里');
  });

  it('没有回应：post reject → 错误行是「预览失败：服务没有回应」', async () => {
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    const { result } = renderHook(() => useLivePreview('profile.add', ARGS, true));
    await settlePreview();
    expect(posts.length).toBe(1);
    expect(result.current.result?.ok).toBe(false);
    expect(result.current.result?.error).toBe('预览失败：服务没有回应');
  });
});
