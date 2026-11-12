// 模式与注入（合同第 8 步）：测试环境缺省走夹具；显式注入优先于构建模式；注入 null 表示不发请求。
import { afterEach, describe, expect, it } from 'vitest';
import { liveClient, liveModeIsReal, setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

const fakeClient: LiveClient = {
  get<T>(): Promise<Envelope<T>> {
    return Promise.resolve({
      ok: true,
      exit_code: 0,
      data: null,
      output: [],
      messages: [],
      command: [],
      elapsed_ms: 0,
    }) as Promise<Envelope<T>>;
  },
};

afterEach(() => {
  setLiveClientForTests(undefined);
});

describe('live/mode：测试环境缺省走夹具', () => {
  it('liveModeIsReal() 为假、liveClient() 为 null（全部读函数走夹具，零请求）', () => {
    expect(liveModeIsReal()).toBe(false);
    expect(liveClient()).toBe(null);
  });
});

describe('live/mode：显式注入优先于构建模式', () => {
  it('setLiveClientForTests(fake) 后 liveClient() 是 fake，构建模式仍为假', () => {
    setLiveClientForTests(fakeClient);
    expect(liveClient()).toBe(fakeClient);
    expect(liveModeIsReal()).toBe(false);
  });

  it('setLiveClientForTests(null) 表示「不发请求」', () => {
    setLiveClientForTests(fakeClient);
    setLiveClientForTests(null);
    expect(liveClient()).toBe(null);
  });

  it('setLiveClientForTests(undefined) 清除注入，回到缺省', () => {
    setLiveClientForTests(fakeClient);
    setLiveClientForTests(undefined);
    expect(liveClient()).toBe(null);
  });
});
